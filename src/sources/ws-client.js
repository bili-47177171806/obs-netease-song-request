import { EventEmitter } from "node:events";
import WebSocket from "ws";

export class WebSocketClient extends EventEmitter {
  #socket = null;

  constructor(url, { handshakeTimeoutMs = 10_000 } = {}) {
    super();
    this.url = new URL(url);
    if (this.url.protocol !== "ws:" && this.url.protocol !== "wss:") {
      throw new Error(`WebSocket 地址必须使用 ws:// 或 wss://：${url}`);
    }
    this.handshakeTimeoutMs = handshakeTimeoutMs;
  }

  get connected() {
    return this.#socket?.readyState === WebSocket.OPEN;
  }

  connect() {
    if (this.#socket) return;
    const socket = new WebSocket(this.url, {
      handshakeTimeout: this.handshakeTimeoutMs,
    });
    this.#socket = socket;

    socket.on("open", () => this.emit("open"));
    socket.on("message", (data, isBinary) => {
      if (isBinary) this.emit("binary", data);
      else this.emit("message", data.toString("utf8"));
    });
    socket.on("pong", (data) => this.emit("pong", data));
    socket.on("error", (error) => this.emit("error", error));
    socket.on("close", (code, reason) => {
      if (this.#socket === socket) this.#socket = null;
      this.emit("close", code, reason);
    });
  }

  send(text) {
    if (this.connected) this.#socket.send(String(text));
  }

  ping(payload = "") {
    if (this.connected) this.#socket.ping(payload);
  }

  close(code = 1000) {
    const socket = this.#socket;
    if (!socket) return;
    if (socket.readyState === WebSocket.CONNECTING) socket.terminate();
    else if (socket.readyState === WebSocket.OPEN) socket.close(code);
  }

  destroy() {
    this.#socket?.terminate();
  }
}
