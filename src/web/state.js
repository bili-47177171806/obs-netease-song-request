import { EventEmitter } from "node:events";

const MAX_LOG = 60;
// 这些字段每次都是完整对象，必须整体替换：合并会让上一首的封面/歌手残留下来。
const REPLACE_KEYS = new Set(["nowPlaying"]);

/**
 * 前端要看的全部状态集中在这里：当前播放、点歌池、弹幕连接、开关和最近日志。
 * 点歌姬各模块只管 patch，广播和去重由这里负责。
 */
export class BotState extends EventEmitter {
  constructor() {
    super();
    this.nowPlaying = null;
    this.queue = [];
    this.accepting = true;
    this.danmaku = { connected: false, mock: false, url: "" };
    this.backend = { ok: false };
    this.log = [];
    this.startedAt = new Date().toISOString();
  }

  patch(partial) {
    let changed = false;
    for (const [key, value] of Object.entries(partial)) {
      const mergeable = value
        && typeof value === "object"
        && !Array.isArray(value)
        && !REPLACE_KEYS.has(key);
      const next = mergeable ? { ...this[key], ...value } : value;
      if (JSON.stringify(this[key]) === JSON.stringify(next)) continue;
      this[key] = next;
      changed = true;
    }
    if (changed) this.emit("change", this.snapshot());
    return changed;
  }

  /** 追加一条给管理面板看的日志，同时触发广播。 */
  note(level, text) {
    this.log = [
      ...this.log.slice(-(MAX_LOG - 1)),
      { at: new Date().toISOString(), level, text },
    ];
    this.emit("change", this.snapshot());
  }

  snapshot() {
    return {
      nowPlaying: this.nowPlaying,
      queue: this.queue,
      accepting: this.accepting,
      danmaku: this.danmaku,
      backend: this.backend,
      log: this.log,
      startedAt: this.startedAt,
    };
  }
}
