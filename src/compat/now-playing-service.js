import http from "node:http";
import { WebSocketServer } from "ws";

const MAX_COVER_BYTES = 12 * 1024 * 1024;
const MAX_LYRIC_CACHE = 32;
const PLAYING_STATE = 2;
const LYRIC_WS_ROUTES = ["/api/ws/lyric", "/ws/lyric"];
// 同一首歌进度明显回退，说明用户重播或往前拖动，歌词端需要重置自己的计时器。
const REPLAY_BACKWARD_MS = 1_500;

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function formatDuration(seconds) {
  const value = Math.max(0, Math.floor(Number(seconds) || 0));
  return `${Math.floor(value / 60)}:${String(value % 60).padStart(2, "0")}`;
}

function durationSeconds(current) {
  return Math.max(0, Math.floor((Number(current?.durationMs) || 0) / 1000));
}

function sampledProgressMs(current, now = Date.now()) {
  if (!current?.songId) return 0;
  const durationMs = Math.max(0, Number(current.durationMs) || 0);
  const sampled = Math.max(0, Number(current.currentPositionMs) || 0);
  const sampledAt = Number(current.sampledAt) || now;
  const elapsed = current.playingState === PLAYING_STATE ? Math.max(0, now - sampledAt) : 0;
  return Math.round(clamp(sampled + elapsed, 0, durationMs || Number.MAX_SAFE_INTEGER));
}

function repeatType(playingMode) {
  if (playingMode === "playOneCycle") return "ONE";
  if (playingMode === "playCycle") return "ALL";
  return "NONE";
}

function emptyLyric(current = null) {
  return {
    source: "netease",
    title: current?.name ? String(current.name) : "",
    author: Array.isArray(current?.artists) ? current.artists.filter(Boolean).join(" / ") : "",
    duration: durationSeconds(current),
    hasLyric: false,
    hasTranslatedLyric: false,
    hasKaraokeLyric: false,
    lrc: "",
    translatedLyric: "",
    karaokeLyric: "",
  };
}

export function toCompatibleLyric(current, payload = null) {
  const result = emptyLyric(current);
  const lrc = String(payload?.lrc?.lyric || "");
  const translatedLyric = String(payload?.tlyric?.lyric || "");
  const karaokeLyric = String(payload?.yrc?.lyric || payload?.klyric?.lyric || "");
  result.lrc = lrc;
  result.translatedLyric = translatedLyric;
  result.karaokeLyric = karaokeLyric;
  result.hasLyric = Boolean(lrc.trim());
  result.hasTranslatedLyric = Boolean(translatedLyric.trim());
  result.hasKaraokeLyric = Boolean(karaokeLyric.trim());
  return result;
}

async function fetchNeteaseLyric(current) {
  if (!current?.songId) return emptyLyric(current);
  const url = new URL("https://music.163.com/api/song/lyric");
  url.search = new URLSearchParams({
    id: String(current.songId),
    lv: "1",
    kv: "1",
    tv: "-1",
  });
  const response = await fetch(url, { signal: AbortSignal.timeout(10_000) });
  if (!response.ok) throw new Error(`lyric request failed: HTTP ${response.status}`);
  return toCompatibleLyric(current, await response.json());
}

export function toCompatibleState(current, now = Date.now()) {
  const hasSong = Boolean(current?.songId);
  const duration = durationSeconds(current);
  const progressMs = hasSong ? sampledProgressMs(current, now) : 0;
  const progress = Math.floor(progressMs / 1000);
  const isPaused = !hasSong || current.playingState !== PLAYING_STATE;
  const player = {
    hasSong,
    isPaused,
    volumePercent: clamp(Number(current?.volumePercent) || 0, 0, 1),
    seekbarCurrentPosition: progress,
    seekbarCurrentPositionHuman: formatDuration(progress),
    statePercent: duration > 0 ? clamp(progress / duration, 0, 1) : 0,
    likeStatus: "INDIFFERENT",
    repeatType: repeatType(current?.playingMode),
  };
  const track = {
    author: hasSong ? (current.artists || []).filter(Boolean).join(" / ") : "",
    title: hasSong ? String(current.name || "") : "",
    album: hasSong ? String(current.album || "") : "",
    cover: hasSong ? String(current.coverUrl || "") : "",
    duration: hasSong ? duration : 0,
    durationHuman: formatDuration(hasSong ? duration : 0),
    url: hasSong ? `https://music.163.com/song?id=${encodeURIComponent(current.songId)}` : "",
    id: hasSong ? String(current.songId) : "",
    isVideo: false,
    isAdvertisement: false,
    inLibrary: false,
  };
  return { player, track, progress: { progress: progressMs } };
}

function normalizeRoute(url, base) {
  return new URL(url, base).pathname.replace(/\/+$/, "") || "/";
}

/** WebSocket 消息一律是 `{ event, data }`，与原项目 WebSocketMessage 一致。 */
function sendEvent(client, event, data) {
  if (client.readyState !== client.OPEN) return;
  // 传回调可以让 ws 把发送异常交给回调，而不是抛到事件链上。
  client.send(JSON.stringify({ event, data }), () => {});
}

function corsHeaders() {
  return {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Cache-Control": "no-store",
  };
}

function sendJson(res, status, body) {
  res.writeHead(status, {
    ...corsHeaders(),
    "Content-Type": "application/json; charset=utf-8",
  });
  res.end(JSON.stringify(body));
}

async function readJson(req) {
  const chunks = [];
  let size = 0;
  for await (const chunk of req) {
    size += chunk.length;
    if (size > 64 * 1024) throw new Error("request body too large");
    chunks.push(chunk);
  }
  if (!chunks.length) return {};
  return JSON.parse(Buffer.concat(chunks).toString("utf8"));
}

async function coverAsDataUrl(value) {
  const url = new URL(String(value || ""));
  if (!["http:", "https:"].includes(url.protocol)) throw new Error("unsupported cover URL");
  const response = await fetch(url, { signal: AbortSignal.timeout(10_000) });
  if (!response.ok) throw new Error(`cover request failed: HTTP ${response.status}`);
  const declaredLength = Number(response.headers.get("content-length")) || 0;
  if (declaredLength > MAX_COVER_BYTES) throw new Error("cover is too large");
  const bytes = Buffer.from(await response.arrayBuffer());
  if (bytes.length > MAX_COVER_BYTES) throw new Error("cover is too large");
  const contentType = response.headers.get("content-type")?.split(";")[0] || "image/jpeg";
  return `data:${contentType};base64,${bytes.toString("base64")}`;
}

/**
 * Widdit/now-playing-service 的常用只读 API 兼容层。
 * 数据仍来自本项目的网易云 CDP 读取，不启动原项目的 Java/C# 后端。
 */
export class NowPlayingCompatServer {
  constructor(getCurrent, {
    port = Number(process.env.NOW_PLAYING_COMPAT_PORT || 9863),
    host = process.env.NOW_PLAYING_COMPAT_HOST || "127.0.0.1",
    lyricFetcher = fetchNeteaseLyric,
    progressSyncMs = Number(process.env.NOW_PLAYING_COMPAT_SYNC_MS || 1000),
  } = {}) {
    this.getCurrent = getCurrent;
    this.port = port;
    this.host = host;
    this.lyricFetcher = lyricFetcher;
    this.progressSyncMs = progressSyncMs;
    this.lyricCache = new Map();
    this.sockets = new WebSocketServer({ noServer: true });
    this.syncTimer = null;
    this.lastSnapshot = null;
    this.server = http.createServer((req, res) => void this.#handle(req, res));
    this.server.on("upgrade", (req, socket, head) => this.#upgrade(req, socket, head));
  }

  get url() {
    return `http://${this.host}:${this.port}`;
  }

  get lyricSocketUrl() {
    return `ws://${this.host}:${this.port}${LYRIC_WS_ROUTES[0]}`;
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
    return this;
  }

  async close() {
    this.#stopSampling();
    for (const client of this.sockets.clients) client.terminate();
    await new Promise((resolve) => this.sockets.close(() => resolve()));
    if (!this.server.listening) return;
    await new Promise((resolve) => this.server.close(resolve));
  }

  async #handle(req, res) {
    const route = normalizeRoute(req.url, this.url);
    if (req.method === "OPTIONS") {
      res.writeHead(204, corsHeaders());
      return res.end();
    }

    try {
      const state = toCompatibleState(this.getCurrent?.() || null);
      if (req.method === "GET") {
        if (["/lyric", "/api/lyric"].includes(route)) {
          const current = this.getCurrent?.() || null;
          if (!current?.songId) return sendJson(res, 200, emptyLyric(current));
          try {
            return sendJson(res, 200, await this.#lyricEntry(current).promise);
          } catch {
            return sendJson(res, 200, emptyLyric(current));
          }
        }
        if (["/query", "/api/query"].includes(route)) {
          return sendJson(res, 200, { player: state.player, track: state.track });
        }
        if (["/query/player", "/api/query/player"].includes(route)) return sendJson(res, 200, state.player);
        if (["/query/track", "/api/query/track"].includes(route)) return sendJson(res, 200, state.track);
        if (["/query/progress", "/api/query/progress"].includes(route)) return sendJson(res, 200, state.progress);
        if (route === "/api/query/hasSong") return sendJson(res, 200, { data: state.player.hasSong });
        if (route === "/api/query/isConnected") return sendJson(res, 200, { data: state.player.hasSong });
      }
      if (req.method === "POST" && ["/cover/convert", "/api/cover/convert"].includes(route)) {
        const body = await readJson(req);
        return sendJson(res, 200, { base64Img: await coverAsDataUrl(body.cover_url) });
      }
      sendJson(res, 404, { error: "not found" });
    } catch (error) {
      sendJson(res, 400, { error: error.message });
    }
  }

  /**
   * 每首歌只请求一次歌词，HTTP 与 WebSocket 共用同一条缓存。
   * `value` 只在请求成功后写入，用于连接建立时同步取用而不必等待网络。
   */
  #lyricEntry(current) {
    const songId = String(current.songId);
    const cached = this.lyricCache.get(songId);
    if (cached) return cached;
    const entry = { value: null, promise: null };
    entry.promise = Promise.resolve().then(() => this.lyricFetcher(current));
    entry.promise.then(
      (value) => { entry.value = value; },
      // 失败的歌词不留在缓存里，下一次请求可以重试。
      () => this.lyricCache.delete(songId),
    );
    this.lyricCache.set(songId, entry);
    while (this.lyricCache.size > MAX_LYRIC_CACHE) {
      this.lyricCache.delete(this.lyricCache.keys().next().value);
    }
    return entry;
  }

  #upgrade(req, socket, head) {
    if (!LYRIC_WS_ROUTES.includes(normalizeRoute(req.url, this.url))) {
      socket.write("HTTP/1.1 404 Not Found\r\nConnection: close\r\nContent-Length: 0\r\n\r\n");
      return socket.destroy();
    }
    this.sockets.handleUpgrade(req, socket, head, (client) => this.#openLyricSocket(client));
  }

  /** 连接建立后按原项目顺序补齐初始状态：Track、Lyric、PlayerPauseState、PlayerProgress。 */
  #openLyricSocket(client) {
    client.on("error", () => client.close());
    client.on("close", () => this.#syncSampling());
    const current = this.getCurrent?.() || null;
    const state = toCompatibleState(current);
    const lyric = current?.songId ? this.#lyricEntry(current).value : null;
    sendEvent(client, "Track", state.track);
    sendEvent(client, "Lyric", lyric || emptyLyric(current));
    sendEvent(client, "PlayerPauseState", state.player);
    sendEvent(client, "PlayerProgress", state.progress);
    // 歌词还没取回来时先给空结构，取回后再补一条 Lyric，避免阻塞其余三条初始消息。
    if (current?.songId && !lyric) void this.#refreshLyric(current);
    this.#syncSampling();
  }

  /** 只有存在歌词连接时才轮询状态，和原项目的 fetchLyricEnabled 一致。 */
  #syncSampling() {
    const active = this.sockets.clients.size > 0;
    if (active && !this.syncTimer) {
      this.lastSnapshot = toCompatibleState(this.getCurrent?.() || null);
      this.syncTimer = setInterval(() => this.#tick(), this.progressSyncMs);
      this.syncTimer.unref?.();
    } else if (!active && this.syncTimer) {
      this.#stopSampling();
    }
  }

  #stopSampling() {
    clearInterval(this.syncTimer);
    this.syncTimer = null;
    this.lastSnapshot = null;
  }

  #tick() {
    const current = this.getCurrent?.() || null;
    const state = toCompatibleState(current);
    const previous = this.lastSnapshot;
    this.lastSnapshot = state;
    if (!previous) return;

    const trackChanged = previous.track.id !== state.track.id;
    if (trackChanged) {
      this.#broadcast("Track", state.track);
      this.#broadcast("PlayerProgress", state.progress);
      void this.#refreshLyric(current);
    }
    if (previous.player.isPaused !== state.player.isPaused) {
      this.#broadcast("PlayerPauseState", state.player);
    }
    if (trackChanged || !state.track.id) return;

    if (state.progress.progress < previous.progress.progress - REPLAY_BACKWARD_MS) {
      // 歌词不变，只需要让对端重置进度基准。
      this.#broadcast("PlayerProgressReplay", state.progress);
    } else if (state.progress.progress !== previous.progress.progress) {
      // 暂停时进度不动，没必要每秒重复推同一个值，对端自己走本地计时器。
      this.#broadcast("PlayerProgress", state.progress);
    }
  }

  /** 歌词就绪后推送，顺序与原项目的 LyricChangedEvent 相同。 */
  async #refreshLyric(current) {
    const songId = current?.songId ? String(current.songId) : "";
    if (!songId) return this.#broadcast("Lyric", emptyLyric(current));
    const entry = this.#lyricEntry(current);
    let lyric = entry.value;
    if (!lyric) {
      try {
        lyric = await entry.promise;
      } catch {
        lyric = emptyLyric(current);
      }
    }
    const latest = this.getCurrent?.() || null;
    // 期间已经切歌，这份歌词对现在的听众没有意义。
    if (String(latest?.songId || "") !== songId) return;
    this.#broadcast("Lyric", lyric);
    this.#broadcast("PlayerProgress", toCompatibleState(latest).progress);
  }

  #broadcast(event, data) {
    for (const client of this.sockets.clients) sendEvent(client, event, data);
  }
}
