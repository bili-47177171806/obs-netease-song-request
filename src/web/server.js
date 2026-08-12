import http from "node:http";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const PUBLIC_DIR = path.join(path.dirname(fileURLToPath(import.meta.url)), "public");
const HEARTBEAT_MS = 15_000;

const STATIC_FILES = {
  "/": "index.html",
  "/panel": "panel.html",
  "/now-playing": "now-playing.html",
  "/admin": "admin.html",
  "/assets/fonts/maoken.ttf": "assets/fonts/maoken.ttf",
};

const CONTENT_TYPES = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".svg": "image/svg+xml",
  ".ttf": "font/ttf",
};

function sendJson(res, code, body) {
  const data = JSON.stringify(body);
  res.writeHead(code, {
    "Content-Type": "application/json; charset=utf-8",
    "Cache-Control": "no-store",
  });
  res.end(data);
}

async function readBody(req) {
  const chunks = [];
  for await (const chunk of req) chunks.push(chunk);
  if (!chunks.length) return {};
  try {
    return JSON.parse(Buffer.concat(chunks).toString("utf8"));
  } catch {
    throw new Error("请求体不是合法 JSON");
  }
}

/**
 * 给 OBS 用的本地小服务：三个页面 + 一条 SSE 状态流 + 管理面板要用的操作接口。
 * 只监听回环地址，管理面板不做鉴权。
 */
export class WebServer {
  #clients = new Set();
  #heartbeat = null;

  constructor(state, actions = {}, {
    port = Number(process.env.WEB_PORT || 8899),
    host = process.env.WEB_HOST || "127.0.0.1",
  } = {}) {
    this.state = state;
    this.actions = actions;
    this.port = port;
    this.host = host;
    this.server = http.createServer((req, res) => void this.#handle(req, res));
    this.#onChange = (snapshot) => this.broadcast(snapshot);
  }

  #onChange;

  get url() {
    return `http://${this.host}:${this.port}`;
  }

  async start() {
    await new Promise((resolve, reject) => {
      this.server.once("error", reject);
      this.server.listen(this.port, this.host, () => {
        this.server.off("error", reject);
        resolve();
      });
    });
    this.port = this.server.address().port;
    this.state.on("change", this.#onChange);
    this.#heartbeat = setInterval(() => {
      for (const client of this.#clients) client.write(": ping\n\n");
    }, HEARTBEAT_MS);
    this.#heartbeat.unref?.();
    return this;
  }

  broadcast(snapshot = this.state.snapshot()) {
    const frame = `data: ${JSON.stringify(snapshot)}\n\n`;
    for (const client of this.#clients) {
      try {
        client.write(frame);
      } catch {
        this.#clients.delete(client);
      }
    }
  }

  async close() {
    clearInterval(this.#heartbeat);
    this.state.off("change", this.#onChange);
    for (const client of this.#clients) client.end();
    this.#clients.clear();
    await new Promise((resolve) => this.server.close(resolve));
  }

  async #handle(req, res) {
    const url = new URL(req.url, this.url);
    const route = url.pathname.replace(/\/+$/, "") || "/";
    try {
      if (req.method === "GET" && route === "/api/events") return this.#stream(req, res);
      if (req.method === "GET" && route === "/api/state") {
        return sendJson(res, 200, this.state.snapshot());
      }
      if (route.startsWith("/api/")) return await this.#api(req, res, route);
      if (req.method === "GET") return await this.#static(res, route);
      sendJson(res, 405, { ok: false, err: "method not allowed" });
    } catch (error) {
      sendJson(res, 500, { ok: false, err: error.message });
    }
  }

  #stream(req, res) {
    res.writeHead(200, {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-store",
      Connection: "keep-alive",
    });
    res.write(`data: ${JSON.stringify(this.state.snapshot())}\n\n`);
    this.#clients.add(res);
    req.on("close", () => this.#clients.delete(res));
  }

  async #api(req, res, route) {
    const call = async (name, ...args) => {
      const action = this.actions[name];
      if (typeof action !== "function") {
        return sendJson(res, 501, { ok: false, err: `未接入操作 ${name}` });
      }
      try {
        const result = await action(...args);
        sendJson(res, 200, { ok: true, ...(result && typeof result === "object" ? result : {}) });
      } catch (error) {
        sendJson(res, 400, { ok: false, err: error.message });
      }
    };

    const removeMatch = route.match(/^\/api\/songs\/(\d+)$/);
    if (removeMatch && req.method === "DELETE") {
      return call("removeSong", Number(removeMatch[1]));
    }

    if (req.method !== "POST") {
      return sendJson(res, 404, { ok: false, err: "not found" });
    }

    const body = await readBody(req);
    switch (route) {
      case "/api/songs":
        return call("addSong", body);
      case "/api/songs/clear":
        return call("clearSongs");
      case "/api/play-mode":
        return call("setPlayMode", String(body.mode || ""));
      case "/api/jump":
        return call("jump", body);
      case "/api/accepting":
        return call("setAccepting", Boolean(body.accepting));
      default:
        return sendJson(res, 404, { ok: false, err: "not found" });
    }
  }

  async #static(res, route) {
    const file = STATIC_FILES[route];
    if (!file) {
      res.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
      return res.end("not found");
    }
    const body = await readFile(path.join(PUBLIC_DIR, file));
    res.writeHead(200, {
      "Content-Type": CONTENT_TYPES[path.extname(file)] || "application/octet-stream",
      "Cache-Control": "no-store",
    });
    res.end(body);
  }
}
