import http from "node:http";

const MAX_COVER_BYTES = 12 * 1024 * 1024;
const MAX_LYRIC_CACHE = 32;
const PLAYING_STATE = 2;

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
  } = {}) {
    this.getCurrent = getCurrent;
    this.port = port;
    this.host = host;
    this.lyricFetcher = lyricFetcher;
    this.lyricCache = new Map();
    this.server = http.createServer((req, res) => void this.#handle(req, res));
  }

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
    return this;
  }

  async close() {
    if (!this.server.listening) return;
    await new Promise((resolve) => this.server.close(resolve));
  }

  async #handle(req, res) {
    const route = new URL(req.url, this.url).pathname.replace(/\/+$/, "") || "/";
    if (req.method === "OPTIONS") {
      res.writeHead(204, corsHeaders());
      return res.end();
    }

    try {
      const state = toCompatibleState(this.getCurrent?.() || null);
      if (req.method === "GET") {
        if (["/lyric", "/api/lyric"].includes(route)) {
          const current = this.getCurrent?.() || null;
          const songId = current?.songId ? String(current.songId) : "";
          if (!songId) return sendJson(res, 200, emptyLyric(current));
          if (!this.lyricCache.has(songId)) {
            const pending = Promise.resolve().then(() => this.lyricFetcher(current));
            this.lyricCache.set(songId, pending);
            pending.catch(() => this.lyricCache.delete(songId));
            while (this.lyricCache.size > MAX_LYRIC_CACHE) {
              this.lyricCache.delete(this.lyricCache.keys().next().value);
            }
          }
          try {
            return sendJson(res, 200, await this.lyricCache.get(songId));
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
}
