import test from "node:test";
import assert from "node:assert/strict";
import http from "node:http";
import { once } from "node:events";
import WebSocket from "ws";
import {
  NowPlayingCompatServer,
  ProgressClock,
  currentLineIndex,
  parseLyricLines,
  toCompatibleLyric,
  toCompatibleState,
} from "../src/compat/now-playing-service.js";

const current = {
  songId: "2623481920",
  name: "命に嫌われている。",
  artists: ["初音ミク", "25時、ナイトコードで。"],
  album: "SEKAI ALBUM",
  coverUrl: "http://example.test/cover.jpg",
  durationMs: 243_800,
  currentPositionMs: 42_250,
  sampledAt: 10_000,
  playingState: 2,
  playingMode: "playCycle",
  volumePercent: 0.33,
};

/** 连接后立刻挂上收集器，避免漏掉服务端在握手后马上推送的初始消息。 */
function collect(client) {
  const messages = [];
  const waiters = [];
  client.on("message", (raw) => {
    messages.push(JSON.parse(raw.toString()));
    for (const resume of waiters.splice(0)) resume();
  });
  const count = (event) => messages.filter((message) => message.event === event).length;
  return {
    messages,
    count,
    events: () => messages.map((message) => message.event),
    async waitFor(event, total = 1, timeoutMs = 2_000) {
      const deadline = Date.now() + timeoutMs;
      while (count(event) < total) {
        if (Date.now() > deadline) {
          throw new Error(`等待 ${event} 第 ${total} 条超时，已收到 ${JSON.stringify(this.events())}`);
        }
        await new Promise((resolve) => {
          const timer = setTimeout(resolve, 20);
          waiters.push(() => {
            clearTimeout(timer);
            resolve();
          });
        });
      }
      return messages.filter((message) => message.event === event).at(-1);
    },
  };
}

async function waitUntil(predicate, timeoutMs = 2_000) {
  const deadline = Date.now() + timeoutMs;
  while (!predicate()) {
    if (Date.now() > deadline) throw new Error("等待条件成立超时");
    await new Promise((resolve) => setTimeout(resolve, 20));
  }
}

test("maps CDP now-playing state to Widdit query entities", () => {
  const result = toCompatibleState(current, 10_750);
  assert.deepEqual(result.player, {
    hasSong: true,
    isPaused: false,
    volumePercent: 0.33,
    seekbarCurrentPosition: 43,
    seekbarCurrentPositionHuman: "0:43",
    statePercent: 43 / 243,
    likeStatus: "INDIFFERENT",
    repeatType: "ALL",
  });
  assert.equal(result.track.author, "初音ミク / 25時、ナイトコードで。");
  assert.equal(result.track.duration, 243);
  assert.equal(result.track.durationHuman, "4:03");
  assert.equal(result.track.url, "https://music.163.com/song?id=2623481920");
  assert.deepEqual(result.progress, { progress: 43_000 });
});

test("maps NetEase lyric payload to Widdit Lyric fields", () => {
  const lyric = toCompatibleLyric(current, {
    lrc: { lyric: "[00:01.00]原文" },
    tlyric: { lyric: "[00:01.00]译文" },
    yrc: { lyric: "[00:01.00](0,500,0)原文" },
  });
  assert.deepEqual(lyric, {
    source: "netease",
    title: current.name,
    author: "初音ミク / 25時、ナイトコードで。",
    duration: 243,
    hasLyric: true,
    hasTranslatedLyric: true,
    hasKaraokeLyric: true,
    lrc: "[00:01.00]原文",
    translatedLyric: "[00:01.00]译文",
    karaokeLyric: "[00:01.00](0,500,0)原文",
  });
});

test("serves the common Now Playing API aliases and CORS", async () => {
  let lyricCalls = 0;
  const compat = new NowPlayingCompatServer(() => ({ ...current, sampledAt: Date.now() }), {
    port: 0,
    lyricFetcher: async () => {
      lyricCalls += 1;
      return toCompatibleLyric(current, { lrc: { lyric: "[00:01.00]原文" } });
    },
  });
  await compat.start();
  try {
    const query = await fetch(`${compat.url}/api/query`);
    assert.equal(query.status, 200);
    assert.equal(query.headers.get("access-control-allow-origin"), "*");
    const queryBody = await query.json();
    assert.deepEqual(Object.keys(queryBody), ["player", "track"]);
    assert.equal(queryBody.track.id, current.songId);

    assert.equal((await (await fetch(`${compat.url}/query/player`)).json()).hasSong, true);
    assert.equal((await (await fetch(`${compat.url}/api/query/track`)).json()).title, current.name);
    assert.equal(typeof (await (await fetch(`${compat.url}/query/progress`)).json()).progress, "number");
    assert.deepEqual(await (await fetch(`${compat.url}/api/query/hasSong`)).json(), { data: true });
    const lyric = await (await fetch(`${compat.url}/api/lyric`)).json();
    assert.equal(lyric.hasLyric, true);
    assert.equal(lyric.lrc, "[00:01.00]原文");
    assert.equal((await (await fetch(`${compat.url}/lyric`)).json()).title, current.name);
    assert.equal(lyricCalls, 1);
  } finally {
    await compat.close();
  }
});

test("进度时钟吸收进度条滞后噪声，读数只会前进", () => {
  const clock = new ProgressClock();
  const song = { songId: "1", durationMs: 240_000, playingState: 2 };
  clock.update({ ...song, currentPositionMs: 30_000, sampledAt: 1_000 }, 1_000);
  assert.equal(clock.read(1_000), 30_000);

  // 客户端进度条这一秒还没刷新，读数原地不动；时钟按真实时间继续走。
  clock.update({ ...song, currentPositionMs: 30_000, sampledAt: 2_000 }, 2_000);
  assert.equal(clock.read(2_000), 31_000);

  // 读数一次补了两格，说明这次采样更新鲜，立即向前校准。
  clock.update({ ...song, currentPositionMs: 32_400, sampledAt: 3_000 }, 3_000);
  assert.equal(clock.read(3_000), 32_400);

  // 读数比本地时钟落后 600ms，属于刷新滞后，不能让歌词退回上一句。
  clock.update({ ...song, currentPositionMs: 32_800, sampledAt: 3_400 }, 3_400);
  assert.equal(clock.read(3_400), 32_800);
  clock.update({ ...song, currentPositionMs: 33_000, sampledAt: 4_400 }, 4_400);
  assert.equal(clock.read(4_400), 33_800);
  assert.equal(clock.seekCount, 0);
});

test("进度时钟对切歌、暂停和拖动分别重新起算", () => {
  const clock = new ProgressClock();
  const song = { songId: "1", durationMs: 240_000, playingState: 2 };
  clock.update({ ...song, currentPositionMs: 60_000, sampledAt: 1_000 }, 1_000);

  clock.update({ ...song, songId: "2", currentPositionMs: 0, sampledAt: 2_000 }, 2_000);
  assert.equal(clock.read(2_000), 0);
  assert.equal(clock.seekCount, 0);

  const other = { ...song, songId: "2" };
  clock.update({ ...other, currentPositionMs: 5_000, sampledAt: 7_000 }, 7_000);
  // 暂停后不再随真实时间前进。
  clock.update({ ...other, playingState: 1, currentPositionMs: 5_000, sampledAt: 8_000 }, 8_000);
  assert.equal(clock.read(20_000), 5_000);

  // 拖动到别处：回退超过阈值才算真实跳转。
  clock.update({ ...other, currentPositionMs: 120_000, sampledAt: 21_000 }, 21_000);
  clock.update({ ...other, currentPositionMs: 10_000, sampledAt: 22_000 }, 22_000);
  assert.equal(clock.read(22_000), 10_000);
  assert.equal(clock.seekCount, 1);
});

test("进度时钟忽略重复读到的同一次采样", () => {
  const clock = new ProgressClock();
  const sample = { songId: "1", durationMs: 240_000, playingState: 2, currentPositionMs: 50_000, sampledAt: 1_000 };
  clock.update(sample, 1_000);
  // 多个接口在同一秒内反复读取，不能被这条读数的滞后量一次次拉回去。
  for (const now of [1_200, 1_400, 1_600, 1_800]) clock.update(sample, now);
  assert.equal(clock.read(1_800), 50_800);
});

test("进度时钟把读数限制在歌曲时长内", () => {
  const clock = new ProgressClock();
  clock.update({ songId: "1", durationMs: 10_000, playingState: 2, currentPositionMs: 9_000, sampledAt: 1_000 }, 1_000);
  assert.equal(clock.read(30_000), 10_000);
});

const lyricWithLines = toCompatibleLyric(current, {
  lrc: {
    lyric: [
      "[00:00.000]作词: 須田景凪",
      "[00:21.400]途方もない時間だけ",
      "[00:24.78]また過ぎていく",
      "[01:07.5]呆れる程に傍にいて",
      "[00:10.000]",
    ].join("\n"),
  },
  tlyric: { lyric: "[00:21.400]只有漫无边际的时间\n[00:24.78]又流逝而过" },
});

test("按时间戳解析逐行歌词并对齐翻译", () => {
  const lines = parseLyricLines(lyricWithLines);
  assert.deepEqual(lines, [
    { index: 0, time: 0, text: "作词: 須田景凪", translation: "" },
    { index: 1, time: 21_400, text: "途方もない時間だけ", translation: "只有漫无边际的时间" },
    { index: 2, time: 24_780, text: "また過ぎていく", translation: "又流逝而过" },
    { index: 3, time: 67_500, text: "呆れる程に傍にいて", translation: "" },
  ]);
});

test("没有歌词时逐行解析返回空数组", () => {
  assert.deepEqual(parseLyricLines(toCompatibleLyric(current, null)), []);
  assert.deepEqual(parseLyricLines(null), []);
});

test("按播放位置定位当前行", () => {
  const lines = parseLyricLines(lyricWithLines);
  assert.equal(currentLineIndex(lines, -1), -1);
  assert.equal(currentLineIndex(lines, 0), 0);
  assert.equal(currentLineIndex(lines, 21_399), 0);
  assert.equal(currentLineIndex(lines, 21_400), 1);
  assert.equal(currentLineIndex(lines, 30_000), 2);
  assert.equal(currentLineIndex(lines, 999_999), 3);
  assert.equal(currentLineIndex([], 5_000), -1);
});

test("逐行歌词接口返回全部行和当前行", async () => {
  const compat = new NowPlayingCompatServer(() => ({ ...current, currentPositionMs: 24_900, sampledAt: Date.now() }), {
    port: 0,
    lyricFetcher: async () => lyricWithLines,
  });
  await compat.start();
  try {
    const all = await (await fetch(`${compat.url}/api/lyric/lines`)).json();
    assert.equal(all.songId, current.songId);
    assert.equal(all.lines.length, 4);
    assert.equal(all.lines[1].translation, "只有漫无边际的时间");

    const line = await (await fetch(`${compat.url}/lyric/line`)).json();
    assert.equal(line.lineCount, 4);
    assert.equal(line.lineIndex, 2);
    assert.equal(line.line.text, "また過ぎていく");
    assert.equal(line.next.text, "呆れる程に傍にいて");
    assert.equal(typeof line.progress, "number");
  } finally {
    await compat.close();
  }
});

test("当前行变化时通过 WebSocket 推送 LyricLine", async () => {
  const live = { ...current, currentPositionMs: 0, sampledAt: Date.now() };
  const compat = new NowPlayingCompatServer(() => live, {
    port: 0,
    progressSyncMs: 20,
    lyricFetcher: async () => lyricWithLines,
  });
  await compat.start();
  const client = new WebSocket(compat.lyricSocketUrl);
  const feed = collect(client);
  try {
    await once(client, "open");
    // 初始那条排在原协议四条之后，且此时歌词还没解析出来。
    assert.equal(feed.events()[4], "LyricLine");
    assert.equal(feed.messages[4].data.lineIndex, -1);

    // 歌词取回后第一次算出行号：位置 0 命中第 0 行。
    assert.equal((await feed.waitFor("LyricLine", 2)).data.line.text, "作词: 須田景凪");

    Object.assign(live, { currentPositionMs: 24_800, sampledAt: Date.now() });
    const moved = await feed.waitFor("LyricLine", 3);
    assert.equal(moved.data.lineIndex, 2);
    assert.equal(moved.data.line.text, "また過ぎていく");
    assert.equal(moved.data.line.translation, "又流逝而过");
    assert.equal(moved.data.next.text, "呆れる程に傍にいて");
  } finally {
    client.close();
    await compat.close();
  }
});

test("pushes the initial lyric WebSocket events in the documented order", async () => {
  const compat = new NowPlayingCompatServer(() => ({ ...current, sampledAt: Date.now() }), {
    port: 0,
    progressSyncMs: 20,
    lyricFetcher: async () => toCompatibleLyric(current, { lrc: { lyric: "[00:01.00]原文" } }),
  });
  await compat.start();
  const client = new WebSocket(compat.lyricSocketUrl);
  const feed = collect(client);
  try {
    await once(client, "open");
    await feed.waitFor("PlayerProgress");
    assert.deepEqual(feed.events().slice(0, 4), ["Track", "Lyric", "PlayerPauseState", "PlayerProgress"]);
    assert.equal(feed.messages[0].data.id, current.songId);
    assert.equal(feed.messages[0].data.title, current.name);
    // 歌词尚未缓存时先给完整的空结构，取回后再补一条 Lyric。
    assert.equal(feed.messages[1].data.hasLyric, false);
    assert.equal(feed.messages[2].data.isPaused, false);
    assert.equal(typeof feed.messages[3].data.progress, "number");
    assert.equal((await feed.waitFor("Lyric", 2)).data.lrc, "[00:01.00]原文");
  } finally {
    client.close();
    await compat.close();
  }
});

test("pushes track, lyric, pause and replay changes over the lyric WebSocket", async () => {
  const live = { ...current, sampledAt: Date.now() };
  const compat = new NowPlayingCompatServer(() => live, {
    port: 0,
    progressSyncMs: 20,
    lyricFetcher: async (song) => toCompatibleLyric(song, { lrc: { lyric: `[00:01.00]${song.name}` } }),
  });
  await compat.start();
  const client = new WebSocket(compat.lyricSocketUrl);
  const feed = collect(client);
  try {
    await once(client, "open");
    await feed.waitFor("Lyric", 2);

    Object.assign(live, {
      songId: "1911300549",
      name: "被生命所厌恶",
      artists: ["黑柿子"],
      durationMs: 200_000,
      currentPositionMs: 0,
      sampledAt: Date.now(),
    });
    assert.equal((await feed.waitFor("Track", 2)).data.id, "1911300549");
    assert.equal((await feed.waitFor("Lyric", 3)).data.lrc, "[00:01.00]被生命所厌恶");

    live.playingState = 1;
    live.sampledAt = Date.now();
    assert.equal((await feed.waitFor("PlayerPauseState", 2)).data.isPaused, true);

    Object.assign(live, { playingState: 2, currentPositionMs: 120_000, sampledAt: Date.now() });
    await feed.waitFor("PlayerProgress", feed.count("PlayerProgress") + 1);
    Object.assign(live, { currentPositionMs: 0, sampledAt: Date.now() });
    assert.ok((await feed.waitFor("PlayerProgressReplay")).data.progress < 1_500);
  } finally {
    client.close();
    await compat.close();
  }
});

test("only samples the player while a lyric client stays connected", async () => {
  const compat = new NowPlayingCompatServer(() => ({ ...current, sampledAt: Date.now() }), {
    port: 0,
    progressSyncMs: 20,
    lyricFetcher: async () => toCompatibleLyric(current, null),
  });
  await compat.start();
  try {
    assert.equal(compat.syncTimer, null);
    const client = new WebSocket(compat.lyricSocketUrl);
    const feed = collect(client);
    await once(client, "open");
    await feed.waitFor("PlayerProgress", 2);
    assert.notEqual(compat.syncTimer, null);
    client.close();
    await once(client, "close");
    await waitUntil(() => compat.syncTimer === null);
  } finally {
    await compat.close();
  }
});

test("rejects WebSocket upgrades outside the lyric endpoint", async () => {
  const compat = new NowPlayingCompatServer(() => null, { port: 0 });
  await compat.start();
  try {
    const client = new WebSocket(`ws://127.0.0.1:${compat.port}/api/ws/other`);
    const [error] = await once(client, "error");
    assert.match(error.message, /404/);
  } finally {
    await compat.close();
  }
});

test("converts a remote cover to the expected data URL response", async () => {
  const image = Buffer.from([0x89, 0x50, 0x4e, 0x47]);
  const imageServer = http.createServer((req, res) => {
    res.writeHead(200, { "Content-Type": "image/png", "Content-Length": image.length });
    res.end(image);
  });
  imageServer.listen(0, "127.0.0.1");
  await once(imageServer, "listening");
  const imageUrl = `http://127.0.0.1:${imageServer.address().port}/cover.png`;
  const compat = new NowPlayingCompatServer(() => null, { port: 0 });
  await compat.start();
  try {
    const response = await fetch(`${compat.url}/api/cover/convert`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ cover_url: imageUrl }),
    });
    assert.deepEqual(await response.json(), {
      base64Img: `data:image/png;base64,${image.toString("base64")}`,
    });
  } finally {
    await compat.close();
    await new Promise((resolve) => imageServer.close(resolve));
  }
});
