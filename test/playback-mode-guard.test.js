import test from "node:test";
import assert from "node:assert/strict";
import { once } from "node:events";
import { PlaybackModeGuard } from "../src/bot/playback-mode-guard.js";

test("初始随机模式在点歌池结束后恢复", async () => {
  const restored = [];
  const service = {
    async ensureOrderMode() { return { ok: true, playingMode: "playOrder" }; },
    async setPlayingMode(mode) { restored.push(mode); return { ok: true, playingMode: mode }; },
  };
  const guard = new PlaybackModeGuard(service);
  guard.noteInsertion({
    playingModeChanged: true,
    previousPlayingMode: "playRandom",
    playingMode: "playOrder",
  });
  guard.handlePoolChanged(1);
  const done = once(guard, "restored");
  guard.handlePoolChanged(0);
  await done;

  assert.deepEqual(restored, ["playRandom"]);
});

test("用户最后手动选择顺序模式时不恢复随机", async () => {
  const restored = [];
  const service = {
    async ensureOrderMode() { return { ok: true, playingMode: "playOrder" }; },
    async setPlayingMode(mode) { restored.push(mode); return { ok: true, playingMode: mode }; },
  };
  const guard = new PlaybackModeGuard(service);
  guard.noteInsertion({ playingModeChanged: true, previousPlayingMode: "playRandom" });
  guard.handlePoolChanged(1);
  guard.handleNowPlaying({
    playingMode: "playOrder",
    manualPlayingMode: "playOrder",
    manualModeVersion: 1,
  });
  guard.handlePoolChanged(0);
  await new Promise((resolve) => setImmediate(resolve));

  assert.deepEqual(restored, []);
});

test("池中手动切到随机时临时纠正并在结束后恢复", async () => {
  const calls = [];
  const service = {
    async ensureOrderMode() { calls.push("correct"); return { ok: true, playingMode: "playOrder" }; },
    async setPlayingMode(mode) { calls.push(`restore:${mode}`); return { ok: true, playingMode: mode }; },
  };
  const guard = new PlaybackModeGuard(service);
  guard.handlePoolChanged(1);
  const corrected = once(guard, "corrected");
  guard.handleNowPlaying({
    playingMode: "playRandom",
    manualPlayingMode: "playRandom",
    manualModeVersion: 1,
  });
  await corrected;
  const restored = once(guard, "restored");
  guard.handlePoolChanged(0);
  await restored;

  assert.deepEqual(calls, ["correct", "restore:playRandom"]);
});
