import test from "node:test";
import assert from "node:assert/strict";
import { once } from "node:events";
import { PlaybackModeGuard } from "../src/bot/playback-mode-guard.js";
import { SongQueue } from "../src/bot/song-queue.js";

test("点歌请求严格串行并保持入队顺序", async () => {
  const calls = [];
  let active = 0;
  let maxActive = 0;
  const service = {
    async insert(command) {
      active += 1;
      maxActive = Math.max(maxActive, active);
      calls.push(command.value);
      await new Promise((resolve) => setTimeout(resolve, 10));
      active -= 1;
      return { ok: true, songId: command.value, name: command.value };
    },
  };
  const queue = new SongQueue(service);

  queue.enqueue({ kind: "id", value: "1", payload: { id: "1" } });
  queue.enqueue({ kind: "id", value: "2", payload: { id: "2" } });
  queue.enqueue({ kind: "id", value: "3", payload: { id: "3" } });
  await queue.waitForIdle();

  assert.deepEqual(calls, ["1", "2", "3"]);
  assert.equal(maxActive, 1);
  assert.equal(queue.pending, 0);
  assert.deepEqual(queue.snapshot().map((item) => item.songId), ["1", "2", "3"]);
});

test("单个请求失败不会阻塞后续点歌", async () => {
  const succeeded = [];
  const failed = [];
  const service = {
    async insert(command) {
      if (command.value === "bad") throw new Error("failed");
      return { ok: true, songId: command.value };
    },
  };
  const queue = new SongQueue(service);
  queue.on("success", (item) => succeeded.push(item.command.value));
  queue.on("failure", (item) => failed.push(item.command.value));

  queue.enqueue({ kind: "song", value: "bad", payload: { song: "bad" } });
  queue.enqueue({ kind: "id", value: "2", payload: { id: "2" } });
  await queue.waitForIdle();

  assert.deepEqual(failed, ["bad"]);
  assert.deepEqual(succeeded, ["2"]);
});

test("普通点歌锚定池尾，插队插到池首", async () => {
  const calls = [];
  const service = {
    async insert(command, placement) {
      calls.push({ value: command.value, afterSongId: placement.afterSongId });
      await new Promise((resolve) => setTimeout(resolve, 5));
      return { ok: true, songId: command.value, name: command.value };
    },
  };
  const queue = new SongQueue(service);

  queue.enqueue({ kind: "id", value: "A", payload: { id: "A" } });
  queue.enqueue({ kind: "id", value: "B", payload: { id: "B" } });
  queue.enqueue({ kind: "id", value: "C", priority: true, payload: { id: "C" } });
  await queue.waitForIdle();

  assert.deepEqual(calls, [
    { value: "A", afterSongId: null },
    { value: "C", afterSongId: null },
    { value: "B", afterSongId: "A" },
  ]);
  assert.deepEqual(queue.snapshot().map((item) => item.songId), ["C", "A", "B"]);

  assert.equal(queue.markPlaying("C").result.songId, "C");
  assert.deepEqual(queue.snapshot().map((item) => item.songId), ["A", "B"]);
});

test("多个插队在插队池内保持先来先播", async () => {
  const calls = [];
  const service = {
    async insert(command, placement) {
      calls.push({ value: command.value, afterSongId: placement.afterSongId });
      await new Promise((resolve) => setTimeout(resolve, 5));
      return { ok: true, songId: command.value, name: command.value };
    },
  };
  const queue = new SongQueue(service);

  queue.enqueue({ kind: "id", value: "A", payload: { id: "A" } });
  queue.enqueue({ kind: "id", value: "B", payload: { id: "B" } });
  queue.enqueue({ kind: "id", value: "C", priority: true, payload: { id: "C" } });
  queue.enqueue({ kind: "id", value: "D", priority: true, payload: { id: "D" } });
  await queue.waitForIdle();

  assert.deepEqual(calls, [
    { value: "A", afterSongId: null },
    { value: "C", afterSongId: null },
    { value: "D", afterSongId: "C" },
    { value: "B", afterSongId: "A" },
  ]);
  assert.deepEqual(queue.snapshot().map((item) => item.songId), ["C", "D", "A", "B"]);
});

test("processing request keeps the pool active after its anchor starts playing", async () => {
  let releaseSecond;
  let secondStartedResolve;
  const secondStarted = new Promise((resolve) => { secondStartedResolve = resolve; });
  const secondBlocked = new Promise((resolve) => { releaseSecond = resolve; });
  const placements = [];
  const service = {
    async insert(command, placement) {
      placements.push({ value: command.value, afterSongId: placement.afterSongId });
      if (command.value === "B") {
        secondStartedResolve();
        await secondBlocked;
      }
      return command.value === "A"
        ? {
            ok: true,
            songId: "A",
            name: "A",
            playingModeChanged: true,
            previousPlayingMode: "playRandom",
            playingMode: "playOrder",
          }
        : { ok: true, songId: "B", name: "B" };
    },
    async setPlayingMode(mode) {
      return { ok: true, playingMode: mode };
    },
  };
  const queue = new SongQueue(service);
  const guard = new PlaybackModeGuard(service);
  const restored = [];

  queue.on("queued", () => guard.handlePoolChanged(queue.totalSize));
  queue.on("success", (_item, result) => guard.noteInsertion(result));
  queue.on("poolChanged", () => guard.handlePoolChanged(queue.totalSize));
  queue.on("idle", () => guard.handlePoolChanged(queue.totalSize));
  guard.on("restored", (mode) => restored.push(mode));

  queue.enqueue({ kind: "id", value: "A", payload: { id: "A" } });
  queue.enqueue({ kind: "id", value: "B", payload: { id: "B" } });
  await secondStarted;

  assert.deepEqual(placements, [
    { value: "A", afterSongId: null },
    { value: "B", afterSongId: "A" },
  ]);
  assert.equal(queue.markPlaying("A").result.songId, "A");
  assert.equal(queue.poolSize, 0);
  assert.equal(queue.pending, 1);
  assert.equal(queue.totalSize, 1);
  await new Promise((resolve) => setImmediate(resolve));
  assert.deepEqual(restored, []);

  releaseSecond();
  await queue.waitForIdle();
  const restoredEvent = once(guard, "restored");
  assert.equal(queue.markPlaying("B").result.songId, "B");
  await restoredEvent;
  assert.deepEqual(restored, ["playRandom"]);
});

test("移除已插入的歌会真正从网易云队列删除", async () => {
  const removed = [];
  const service = {
    async insert(command) {
      return { ok: true, songId: command.value, name: command.value };
    },
    async remove(ids) {
      removed.push(ids);
      return { ok: true, removed: ids, verified: true };
    },
  };
  const queue = new SongQueue(service);
  queue.enqueue({ kind: "id", value: "A", payload: { id: "A" } });
  queue.enqueue({ kind: "id", value: "B", payload: { id: "B" } });
  await queue.waitForIdle();

  const target = queue.snapshot().find((item) => item.songId === "A");
  const result = await queue.remove(target.id);

  assert.equal(result.removed, true);
  assert.equal(result.inserted, true);
  assert.deepEqual(removed, [["A"]]);
  assert.deepEqual(queue.snapshot().map((item) => item.songId), ["B"]);
});

test("移除还没轮到的请求不会调用网易云删除", async () => {
  let removeCalls = 0;
  const service = {
    async insert(command) {
      await new Promise((resolve) => setTimeout(resolve, 20));
      return { ok: true, songId: command.value };
    },
    async remove() {
      removeCalls += 1;
      return { ok: true };
    },
  };
  const queue = new SongQueue(service);
  queue.enqueue({ kind: "id", value: "1", payload: { id: "1" } });
  const waiting = queue.enqueue({ kind: "id", value: "2", payload: { id: "2" } });

  const result = await queue.remove(waiting.id);
  await queue.waitForIdle();

  assert.equal(result.removed, true);
  assert.equal(result.inserted, false);
  assert.equal(removeCalls, 0);
  assert.deepEqual(queue.snapshot().map((item) => item.songId), ["1"]);
});

test("删除失败时点歌池保持不变", async () => {
  const service = {
    async insert(command) {
      return { ok: true, songId: command.value };
    },
    async remove() {
      throw new Error("CDP 不可用");
    },
  };
  const queue = new SongQueue(service);
  queue.enqueue({ kind: "id", value: "A", payload: { id: "A" } });
  await queue.waitForIdle();

  const target = queue.snapshot()[0];
  await assert.rejects(() => queue.remove(target.id), /CDP 不可用/);
  assert.deepEqual(queue.snapshot().map((item) => item.songId), ["A"]);
});

test("按 songId 删除时同步移除池中的重复点歌", async () => {
  const removed = [];
  const service = {
    async insert(command) {
      return { ok: true, songId: command.value, name: command.value };
    },
    async remove(ids) {
      removed.push(ids);
      return { ok: true, removed: ids };
    },
  };
  const queue = new SongQueue(service);
  queue.enqueue({ kind: "id", value: "A", payload: { id: "A" } });
  queue.enqueue({ kind: "id", value: "A", payload: { id: "A" } });
  queue.enqueue({ kind: "id", value: "B", payload: { id: "B" } });
  await queue.waitForIdle();

  const result = await queue.remove(queue.snapshot()[0].id);

  assert.deepEqual(removed, [["A"]]);
  assert.equal(result.removedItems.length, 2);
  assert.deepEqual(queue.snapshot().map((item) => item.songId), ["B"]);
});

test("清空点歌池会一次性删除所有已插入歌曲", async () => {
  const removed = [];
  const service = {
    async insert(command) {
      return { ok: true, songId: command.value };
    },
    async remove(ids) {
      removed.push(ids);
      return { ok: true };
    },
  };
  const queue = new SongQueue(service);
  queue.enqueue({ kind: "id", value: "A", payload: { id: "A" } });
  queue.enqueue({ kind: "id", value: "B", payload: { id: "B" } });
  await queue.waitForIdle();

  const result = await queue.clear();

  assert.equal(result.pooled, 2);
  assert.deepEqual(removed, [["A", "B"]]);
  assert.deepEqual(queue.snapshot(), []);
});

test("fullSnapshot 把待处理请求排在已入池之后", async () => {
  const service = {
    async insert(command) {
      await new Promise((resolve) => setTimeout(resolve, 15));
      return { ok: true, songId: command.value, name: command.value };
    },
  };
  const queue = new SongQueue(service);
  queue.enqueue({ kind: "id", value: "1", payload: { id: "1" } });
  queue.enqueue({ kind: "id", value: "2", payload: { id: "2" } });
  queue.enqueue({ kind: "id", value: "3", payload: { id: "3" } });

  const pending = queue.fullSnapshot();
  assert.deepEqual(pending.map((item) => item.state), ["processing", "waiting", "waiting"]);

  await queue.waitForIdle();
  const settled = queue.fullSnapshot();
  assert.deepEqual(settled.map((item) => item.state), ["queued", "queued", "queued"]);
});
