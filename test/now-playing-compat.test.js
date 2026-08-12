import test from "node:test";
import assert from "node:assert/strict";
import http from "node:http";
import { once } from "node:events";
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
