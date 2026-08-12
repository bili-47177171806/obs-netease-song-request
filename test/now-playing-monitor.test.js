import test from "node:test";
import assert from "node:assert/strict";
import { NowPlayingMonitor } from "../src/bot/now-playing-monitor.js";

test("NOW PLAYING 只在歌曲或状态变化时发出事件", { timeout: 2_000 }, async () => {
  const tracks = [
    { ok: true, songId: "1", name: "One", playingState: 2 },
    { ok: true, songId: "1", name: "One", playingState: 2 },
    { ok: true, songId: "2", name: "Two", playingState: 2 },
  ];
  let index = 0;
  const service = {
    async nowPlaying() {
      return tracks[Math.min(index++, tracks.length - 1)];
    },
  };
  const monitor = new NowPlayingMonitor(service, { intervalMs: 5 });
  const seen = [];

  await new Promise((resolve, reject) => {
    monitor.on("change", (current) => {
      seen.push(current.songId);
      if (seen.length === 2) resolve();
    });
    monitor.on("error", reject);
    monitor.start();
  });
  monitor.stop();

  assert.deepEqual(seen, ["1", "2"]);
});

test("NOW PLAYING single timeout retries silently and keeps current track", { timeout: 2_000 }, async () => {
  const timeout = Object.assign(new Error("The operation was aborted due to timeout"), {
    name: "TimeoutError",
  });
  const tracks = [
    { ok: true, songId: "1", name: "One", playingState: 2 },
    timeout,
    { ok: true, songId: "1", name: "One", playingState: 2 },
  ];
  let index = 0;
  const service = {
    async nowPlaying() {
      const value = tracks[Math.min(index++, tracks.length - 1)];
      if (value instanceof Error) throw value;
      return value;
    },
  };
  const monitor = new NowPlayingMonitor(service, {
    intervalMs: 5,
    retryMs: 1,
    timeoutErrorThreshold: 3,
  });
  const errors = [];
  monitor.on("error", (error) => errors.push(error));
  monitor.start();
  await new Promise((resolve) => setTimeout(resolve, 30));
  monitor.stop();

  assert.equal(monitor.current.songId, "1");
  assert.equal(errors.length, 0);
});

test("NOW PLAYING reports repeated timeouts and emits recovered", { timeout: 2_000 }, async () => {
  const timeout = () => Object.assign(
    new Error("The operation was aborted due to timeout"),
    { name: "TimeoutError" },
  );
  const results = [timeout(), timeout(), timeout(), {
    ok: true,
    songId: "1",
    name: "One",
    playingState: 2,
  }];
  let index = 0;
  const service = {
    async nowPlaying() {
      const value = results[Math.min(index++, results.length - 1)];
      if (value instanceof Error) throw value;
      return value;
    },
  };
  const monitor = new NowPlayingMonitor(service, {
    intervalMs: 5,
    retryMs: 1,
    timeoutErrorThreshold: 3,
  });

  const errors = [];
  await new Promise((resolve) => {
    monitor.on("error", (error) => errors.push(error));
    monitor.on("recovered", resolve);
    monitor.start();
  });
  monitor.stop();

  assert.equal(errors.length, 1);
  assert.equal(monitor.current.songId, "1");
});
