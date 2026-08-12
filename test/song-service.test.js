import test from "node:test";
import assert from "node:assert/strict";
import http from "node:http";
import { once } from "node:events";
import { SongService } from "../src/cloudmusic/song-service.js";

test("检查健康状态并发送点歌 JSON", async (t) => {
  let received = null;
  const server = http.createServer((request, response) => {
    response.setHeader("Content-Type", "application/json; charset=utf-8");
    if (request.method === "GET" && request.url === "/health") {
      response.end(JSON.stringify({ ok: true, service: "cloudmusic-cdp" }));
      return;
    }
    if (request.method === "GET" && request.url === "/now-playing") {
      response.end(JSON.stringify({
        ok: true,
        songId: "999",
        name: "Now Playing",
        artists: ["Singer"],
        playingState: 2,
        playingMode: "playOrder",
      }));
      return;
    }
    if (request.method === "POST" && request.url === "/play-mode/order") {
      response.end(JSON.stringify({ ok: true, playingMode: "playOrder", changed: true }));
      return;
    }
    if (request.method === "POST" && request.url === "/play-mode") {
      response.end(JSON.stringify({ ok: true, playingMode: "playRandom", changed: true }));
      return;
    }

    let raw = "";
    request.setEncoding("utf8");
    request.on("data", (chunk) => { raw += chunk; });
    request.on("end", () => {
      received = JSON.parse(raw);
      response.end(JSON.stringify({ ok: true, songId: "123", name: "Test" }));
    });
  });
  server.listen(0, "127.0.0.1");
  await once(server, "listening");
  t.after(() => server.close());

  const address = server.address();
  const service = new SongService({
    baseUrl: `http://127.0.0.1:${address.port}`,
    autoStart: false,
  });

  assert.equal((await service.health()).service, "cloudmusic-cdp");
  assert.equal((await service.nowPlaying()).songId, "999");
  assert.equal((await service.ensureOrderMode()).playingMode, "playOrder");
  assert.equal((await service.setPlayingMode("playRandom")).playingMode, "playRandom");
  const result = await service.insert({
    kind: "id",
    value: "123",
    payload: { id: "123" },
  }, { afterSongId: "999" });

  assert.deepEqual(received, { id: "123", afterSongId: "999" });
  assert.equal(result.name, "Test");
});
