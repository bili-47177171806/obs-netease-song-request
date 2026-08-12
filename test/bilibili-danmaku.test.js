import test from "node:test";
import assert from "node:assert/strict";
import { once } from "node:events";
import { WebSocketServer } from "ws";
import { BilibiliDanmakuSource, mapDanmaku } from "../src/sources/bilibili-danmaku.js";

test("maps Bilibili message fields to the song bot message", () => {
  const receivedAt = new Date("2026-08-11T08:00:00Z");
  const message = mapDanmaku({
    type: "message",
    uid: 123,
    openId: "open-123",
    uname: "测试观众",
    face: "https://example.com/face.png",
    fansMedalName: "测试团",
    fansMedalLevel: 12,
    guardLevel: 3,
    guardIcon: "https://example.com/guard.png",
    isAnchor: false,
    isModerator: true,
    emojiImgUrl: "https://example.com/emoji.png",
    color: "#ffffff",
    message: "点歌誰にもなれない私だから",
  }, receivedAt);

  assert.deepEqual(message, {
    user: "测试观众",
    text: "点歌誰にもなれない私だから",
    fanLevel: 12,
    fansMedalName: "测试团",
    guardLevel: 3,
    guardIcon: "https://example.com/guard.png",
    isAnchor: false,
    isModerator: true,
    uid: "123",
    openId: "open-123",
    face: "https://example.com/face.png",
    emojiImgUrl: "https://example.com/emoji.png",
    color: "#ffffff",
    source: "bilibili",
    receivedAt,
  });
});

test("ignores non-message events and blank messages", () => {
  assert.equal(mapDanmaku({ type: "gift", message: "点歌测试" }), null);
  assert.equal(mapDanmaku({ type: "message", message: "   " }), null);
  assert.equal(mapDanmaku({ sys: "connected", mock: false }), null);
});

test("receives connection state and messages from the local WebSocket service", async (t) => {
  const server = new WebSocketServer({ host: "127.0.0.1", port: 0 });
  await once(server, "listening");
  t.after(() => server.close());

  server.on("connection", (socket) => {
    socket.send(JSON.stringify({ sys: "connected", mock: false }));
    socket.send(JSON.stringify({
      type: "message",
      uname: "直播观众",
      fansMedalLevel: 11,
      message: "插队千本桜",
    }));
  });

  const address = server.address();
  const source = new BilibiliDanmakuSource({
    url: `ws://127.0.0.1:${address.port}/`,
    heartbeatMs: 1_000,
    idleTimeoutMs: 5_000,
  });
  source.on("error", () => {});
  t.after(() => source.close());

  const connected = once(source, "connected");
  const incoming = once(source, "message");
  source.start();

  assert.deepEqual(await connected, [{ url: source.url, mock: false }]);
  const [message] = await incoming;
  assert.equal(message.user, "直播观众");
  assert.equal(message.fanLevel, 11);
  assert.equal(message.text, "插队千本桜");
});
