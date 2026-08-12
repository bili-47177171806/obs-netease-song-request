import test from "node:test";
import assert from "node:assert/strict";
import { BotState } from "../src/web/state.js";
import { WebServer } from "../src/web/server.js";

async function withServer(actions, run) {
  const state = new BotState();
  const web = new WebServer(state, actions, { port: 0 });
  await web.start();
  // port 0 由系统分配，取回真实端口。
  const { port } = web.server.address();
  const base = `http://127.0.0.1:${port}`;
  try {
    await run({ state, base });
  } finally {
    await web.close();
  }
}

const post = (base, path, body) => fetch(base + path, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body ?? {}),
}).then(async (response) => ({ status: response.status, body: await response.json() }));

test("三个页面和状态接口都能访问", async () => {
  await withServer({}, async ({ base }) => {
    for (const path of ["/", "/panel", "/now-playing", "/admin"]) {
      const response = await fetch(base + path);
      assert.equal(response.status, 200, path);
      assert.match(response.headers.get("content-type"), /text\/html/);
      assert.match(await response.text(), /<html/i);
    }
    const state = await (await fetch(`${base}/api/state`)).json();
    assert.deepEqual(state.queue, []);
    assert.equal(state.accepting, true);
    const font = await fetch(`${base}/assets/fonts/maoken.ttf`);
    assert.equal(font.status, 200);
    assert.match(font.headers.get("content-type"), /font\/ttf/);
    assert.ok(Number(font.headers.get("content-length") || 0) > 0 || (await font.arrayBuffer()).byteLength > 0);
    assert.equal((await fetch(`${base}/nope`)).status, 404);
  });
});

test("SSE 先推当前状态再推变更", async () => {
  await withServer({}, async ({ state, base }) => {
    const response = await fetch(`${base}/api/events`);
    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    const first = decoder.decode((await reader.read()).value);
    assert.match(first, /^data: /);
    assert.equal(JSON.parse(first.slice(6)).queue.length, 0);

    state.patch({ queue: [{ id: 1, name: "春を告げる", user: "阿房", state: "queued" }] });
    const second = JSON.parse(decoder.decode((await reader.read()).value).slice(6));
    assert.equal(second.queue[0].name, "春を告げる");

    await reader.cancel();
  });
});

test("管理接口把请求转给对应操作", async () => {
  const calls = [];
  const actions = {
    addSong: (body) => { calls.push(["addSong", body]); return { id: 9 }; },
    removeSong: (id) => { calls.push(["removeSong", id]); return {}; },
    clearSongs: () => { calls.push(["clearSongs"]); return { pooled: 3 }; },
    setPlayMode: (mode) => { calls.push(["setPlayMode", mode]); return {}; },
    jump: (body) => { calls.push(["jump", body]); return {}; },
    setAccepting: (value) => { calls.push(["setAccepting", value]); return {}; },
  };

  await withServer(actions, async ({ base }) => {
    assert.deepEqual(await post(base, "/api/songs", { value: "IF Else", priority: true }),
      { status: 200, body: { ok: true, id: 9 } });
    assert.equal((await post(base, "/api/songs/clear")).body.pooled, 3);
    await post(base, "/api/play-mode", { mode: "playRandom" });
    await post(base, "/api/jump", { flag: 1 });
    await post(base, "/api/accepting", { accepting: false });

    const deleted = await fetch(`${base}/api/songs/42`, { method: "DELETE" });
    assert.equal(deleted.status, 200);
  });

  assert.deepEqual(calls, [
    ["addSong", { value: "IF Else", priority: true }],
    ["clearSongs"],
    ["setPlayMode", "playRandom"],
    ["jump", { flag: 1 }],
    ["setAccepting", false],
    ["removeSong", 42],
  ]);
});

test("操作抛错返回 400 并带上原因", async () => {
  const actions = {
    addSong() {
      throw new Error("请填写歌名或歌曲 ID");
    },
  };
  await withServer(actions, async ({ base }) => {
    const result = await post(base, "/api/songs", {});
    assert.equal(result.status, 400);
    assert.deepEqual(result.body, { ok: false, err: "请填写歌名或歌曲 ID" });

    // 没接入的操作要说清楚，而不是假装成功。
    const missing = await post(base, "/api/jump", { flag: 1 });
    assert.equal(missing.status, 501);
  });
});

test("nowPlaying 整体替换，不残留上一首的字段", () => {
  const state = new BotState();
  state.patch({ nowPlaying: { songId: "1", name: "甲", coverUrl: "http://x/a.jpg" } });
  state.patch({ nowPlaying: { songId: "2", name: "乙" } });
  assert.deepEqual(state.nowPlaying, { songId: "2", name: "乙" });
});

test("danmaku 之类的状态支持局部更新", () => {
  const state = new BotState();
  state.patch({ danmaku: { connected: true, mock: false, url: "ws://127.0.0.1:8766/" } });
  state.patch({ danmaku: { connected: false } });
  assert.deepEqual(state.danmaku, { connected: false, mock: false, url: "ws://127.0.0.1:8766/" });
});

test("状态没变化时不广播", () => {
  const state = new BotState();
  let changes = 0;
  state.on("change", () => { changes += 1; });
  assert.equal(state.patch({ accepting: true }), false);
  assert.equal(state.patch({ accepting: false }), true);
  assert.equal(changes, 1);
});
