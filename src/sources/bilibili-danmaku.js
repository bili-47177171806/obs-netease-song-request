import { EventEmitter } from "node:events";
import { WebSocketClient } from "./ws-client.js";

// 本地弹幕接收器（D:\livehime\danmaku）广播的字段名，与点歌姬内部字段不同：
// uname -> user、message -> text、fansMedalLevel -> fanLevel。
export function mapDanmaku(payload, receivedAt = new Date()) {
  if (!payload || typeof payload !== "object") return null;
  const event = payload.data && typeof payload.data === "object" && !Array.isArray(payload.data)
    ? { ...payload, ...payload.data }
    : payload;
  const eventType = String(event.type || event.eventType || event.event || "").toLowerCase();
  if (eventType !== "message") return null;
  const text = typeof event.message === "string" ? event.message : "";
  if (!text.trim()) return null;

  return {
    user: String(event.uname || "观众"),
    text,
    fanLevel: Number(event.fansMedalLevel) || 0,
    fansMedalName: String(event.fansMedalName || ""),
    guardLevel: Number(event.guardLevel) || 0,
    guardIcon: String(event.guardIcon || ""),
    isAnchor: Boolean(event.isAnchor),
    isModerator: Boolean(event.isModerator),
    uid: String(event.uid ?? ""),
    openId: String(event.openId ?? ""),
    face: String(event.face || ""),
    emojiImgUrl: String(event.emojiImgUrl || ""),
    color: String(event.color || ""),
    source: "bilibili",
    receivedAt,
  };
}

export class BilibiliDanmakuSource extends EventEmitter {
  #client = null;
  #reconnectTimer = null;
  #heartbeatTimer = null;
  #attempt = 0;
  #stopped = false;
  #lastActivityAt = 0;

  constructor({
    url = process.env.DANMAKU_WS_URL || "ws://127.0.0.1:8766/",
    reconnectDelayMs = 1_000,
    maxReconnectDelayMs = 30_000,
    heartbeatMs = 30_000,
    idleTimeoutMs = 90_000,
  } = {}) {
    super();
    this.url = url;
    this.reconnectDelayMs = reconnectDelayMs;
    this.maxReconnectDelayMs = maxReconnectDelayMs;
    this.heartbeatMs = heartbeatMs;
    this.idleTimeoutMs = idleTimeoutMs;
    this.mock = null;
  }

  get connected() {
    return Boolean(this.#client?.connected);
  }

  start() {
    if (this.#stopped) return;
    this.#connect();
  }

  close() {
    if (this.#stopped) return;
    this.#stopped = true;
    clearTimeout(this.#reconnectTimer);
    clearInterval(this.#heartbeatTimer);
    this.#reconnectTimer = null;
    this.#heartbeatTimer = null;
    this.#client?.close();
    this.#client = null;
    this.emit("close");
  }

  #connect() {
    let client;
    try {
      client = new WebSocketClient(this.url);
    } catch (error) {
      this.emit("error", error);
      this.#scheduleReconnect();
      return;
    }

    this.#client = client;
    client.on("open", () => {
      this.#attempt = 0;
      this.#lastActivityAt = Date.now();
      this.#startHeartbeat();
    });
    client.on("message", (raw) => this.#onMessage(raw));
    client.on("pong", () => {
      this.#lastActivityAt = Date.now();
    });
    client.on("error", (error) => {
      if (this.#stopped || this.#client !== client) return;
      this.emit("error", error);
    });
    client.on("close", () => {
      if (this.#client !== client) return;
      this.#client = null;
      clearInterval(this.#heartbeatTimer);
      this.#heartbeatTimer = null;
      this.mock = null;
      if (this.#stopped) return;
      this.#scheduleReconnect();
    });

    client.connect();
  }

  #startHeartbeat() {
    clearInterval(this.#heartbeatTimer);
    this.#heartbeatTimer = setInterval(() => {
      const client = this.#client;
      if (!client) return;
      // 弹幕服务端只回应 ping，不会主动发心跳，所以由客户端探活。
      if (Date.now() - this.#lastActivityAt > this.idleTimeoutMs) {
        this.emit("error", new Error(`弹幕连接 ${Math.round(this.idleTimeoutMs / 1000)} 秒无数据，重新连接`));
        client.destroy();
        return;
      }
      client.ping();
    }, this.heartbeatMs);
  }

  #scheduleReconnect() {
    if (this.#stopped || this.#reconnectTimer) return;
    const delay = Math.min(this.reconnectDelayMs * 2 ** this.#attempt, this.maxReconnectDelayMs);
    this.#attempt += 1;
    this.emit("disconnected", { retryInMs: delay, attempt: this.#attempt });
    this.#reconnectTimer = setTimeout(() => {
      this.#reconnectTimer = null;
      this.#connect();
    }, delay);
  }

  #onMessage(raw) {
    this.#lastActivityAt = Date.now();
    let payload;
    try {
      payload = JSON.parse(raw);
    } catch {
      this.emit("error", new Error(`弹幕服务返回了无效 JSON: ${String(raw).slice(0, 120)}`));
      return;
    }

    if (payload?.sys === "connected") {
      this.mock = Boolean(payload.mock);
      this.emit("connected", { url: this.url, mock: this.mock });
      return;
    }

    const message = mapDanmaku(payload);
    if (message) {
      this.emit("message", message);
      return;
    }
    if (payload?.type) this.emit("event", payload);
  }
}
