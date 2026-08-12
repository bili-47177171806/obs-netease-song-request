import test from "node:test";
import assert from "node:assert/strict";
import http from "node:http";
import { once } from "node:events";
import WebSocket from "ws";
import { NowPlayingCompatServer, toCompatibleLyric, toCompatibleState } from "../src/compat/now-playing-service.js";

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
