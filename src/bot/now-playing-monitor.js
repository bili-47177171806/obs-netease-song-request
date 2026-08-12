import { EventEmitter } from "node:events";

function isTimeoutError(error) {
  return error?.name === "TimeoutError"
    || error?.name === "AbortError"
    || /aborted due to timeout|timed?\s*out|超时/i.test(String(error?.message || ""));
}

export class NowPlayingMonitor extends EventEmitter {
  constructor(service, {
    intervalMs = 1_000,
    retryMs = 500,
    timeoutErrorThreshold = 3,
  } = {}) {
    super();
    this.service = service;
    this.intervalMs = intervalMs;
    this.retryMs = retryMs;
    this.timeoutErrorThreshold = timeoutErrorThreshold;
    this.running = false;
    this.timer = null;
    this.current = null;
    this.lastError = null;
    this.consecutiveTimeouts = 0;
    this.errorReported = false;
  }

  start() {
    if (this.running) return;
    this.running = true;
    void this.#poll();
  }

  stop() {
    this.running = false;
    clearTimeout(this.timer);
    this.timer = null;
  }

  async #poll() {
    let nextPollMs = this.intervalMs;
    try {
      const next = await this.service.nowPlaying();
      const sampledAt = Date.now();
      const previousSample = this.current;
      if ((next.currentPositionMs == null || !Number.isFinite(Number(next.currentPositionMs)))
          && previousSample?.songId === next.songId
          && previousSample.currentPositionMs != null
          && Number.isFinite(Number(previousSample.currentPositionMs))) {
        const elapsed = previousSample.playingState === 2
          ? Math.max(0, sampledAt - (Number(previousSample.sampledAt) || sampledAt))
          : 0;
        const duration = Number(next.durationMs) || Number.MAX_SAFE_INTEGER;
        next.currentPositionMs = Math.min(Number(previousSample.currentPositionMs) + elapsed, duration);
      }
      if (next.currentPositionMs == null || !Number.isFinite(Number(next.currentPositionMs))) {
        next.currentPositionMs = 0;
      }
      next.sampledAt = sampledAt;
      const recovered = this.errorReported;
      this.lastError = null;
      this.consecutiveTimeouts = 0;
      this.errorReported = false;
      const previous = this.current;
      const changed = !previous
        || previous.songId !== next.songId
        || previous.playingState !== next.playingState
        || previous.playingMode !== next.playingMode;
      this.current = next;
      if (changed) this.emit("change", next, previous);
      if (recovered) this.emit("recovered", next);
    } catch (error) {
      const timeout = isTimeoutError(error);
      this.consecutiveTimeouts = timeout ? this.consecutiveTimeouts + 1 : 0;
      nextPollMs = timeout ? this.retryMs : this.intervalMs;
      const shouldReport = !timeout || this.consecutiveTimeouts >= this.timeoutErrorThreshold;
      if (shouldReport && error.message !== this.lastError) {
        this.lastError = error.message;
        this.errorReported = true;
        this.emit("error", error);
      }
    } finally {
      if (this.running) {
        this.timer = setTimeout(() => void this.#poll(), nextPollMs);
      }
    }
  }
}
