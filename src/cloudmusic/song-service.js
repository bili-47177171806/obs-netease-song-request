import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";

const PROJECT_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function readJson(response) {
  const text = await response.text();
  try {
    return text ? JSON.parse(text) : {};
  } catch {
    throw new Error(`服务返回了无效 JSON: ${text.slice(0, 200)}`);
  }
}

export class SongService {
  constructor({
    baseUrl = process.env.CLOUDMUSIC_API_URL || "http://127.0.0.1:8866",
    timeoutMs = 60_000,
    autoStart = process.env.CLOUDMUSIC_AUTO_START !== "false",
    python = process.env.PYTHON_BIN || "python",
  } = {}) {
    this.baseUrl = new URL(baseUrl);
    this.timeoutMs = timeoutMs;
    this.autoStart = autoStart;
    this.python = python;
    this.child = null;
    this.startupError = null;
  }

  async health(timeoutMs = 1_500) {
    try {
      const response = await fetch(new URL("/health", this.baseUrl), {
        signal: AbortSignal.timeout(timeoutMs),
      });
      if (!response.ok) return null;
      const body = await readJson(response);
      return body.ok ? body : null;
    } catch {
      return null;
    }
  }

  async nowPlaying(timeoutMs = 10_000) {
    const response = await fetch(new URL("/now-playing", this.baseUrl), {
      signal: AbortSignal.timeout(timeoutMs),
    });
    const result = await readJson(response);
    if (!response.ok || !result.ok) {
      throw new Error(result.err || `读取当前播放失败: HTTP ${response.status}`);
    }
    return result;
  }

  async ensureOrderMode(timeoutMs = 10_000) {
    const response = await fetch(new URL("/play-mode/order", this.baseUrl), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
      signal: AbortSignal.timeout(timeoutMs),
    });
    const result = await readJson(response);
    if (!response.ok || !result.ok) {
      throw new Error(result.err || `切换顺序播放失败: HTTP ${response.status}`);
    }
    return result;
  }

  async setPlayingMode(mode, timeoutMs = 10_000) {
    const response = await fetch(new URL("/play-mode", this.baseUrl), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mode }),
      signal: AbortSignal.timeout(timeoutMs),
    });
    const result = await readJson(response);
    if (!response.ok || !result.ok) {
      throw new Error(result.err || `恢复播放模式失败: HTTP ${response.status}`);
    }
    return result;
  }

  async ensureAvailable() {
    const health = await this.health();
    if (health) return { started: false, health };

    if (!this.autoStart) {
      throw new Error(`点歌服务不可用: ${this.baseUrl.href}`);
    }
    if (!["127.0.0.1", "localhost"].includes(this.baseUrl.hostname)) {
      throw new Error("仅支持自动启动本机点歌服务");
    }

    const port = this.baseUrl.port || "80";
    this.child = spawn(this.python, ["-m", "backend.cloudmusic.server", "--port", port], {
      cwd: PROJECT_ROOT,
      stdio: ["ignore", "pipe", "pipe"],
      windowsHide: true,
    });
    this.startupError = null;
    this.child.once("error", (error) => {
      this.startupError = error;
    });
    this.child.stdout.on("data", (chunk) => {
      process.stdout.write(`[注入服务] ${chunk}`);
    });
    this.child.stderr.on("data", (chunk) => {
      process.stderr.write(`[注入服务] ${chunk}`);
    });

    const deadline = Date.now() + 45_000;
    while (Date.now() < deadline) {
      if (this.startupError) {
        throw new Error(`点歌服务启动失败: ${this.startupError.message}`);
      }
      if (this.child.exitCode !== null) {
        throw new Error(`点歌服务启动失败，退出码 ${this.child.exitCode}`);
      }
      const current = await this.health(1_000);
      if (current) return { started: true, health: current };
      await delay(500);
    }
    this.stop();
    throw new Error("等待点歌服务启动超时");
  }

  async insert(command, { afterSongId = null } = {}) {
    const payload = { ...command.payload };
    if (afterSongId) payload.afterSongId = String(afterSongId);
    const response = await fetch(this.baseUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(this.timeoutMs),
    });
    const result = await readJson(response);
    if (!response.ok || !result.ok) {
      throw new Error(result.err || `点歌请求失败: HTTP ${response.status}`);
    }
    return result;
  }

  async remove(songIds, timeoutMs = 30_000) {
    const ids = (Array.isArray(songIds) ? songIds : [songIds])
      .map((id) => String(id || "").trim())
      .filter(Boolean);
    if (!ids.length) throw new Error("没有要删除的歌曲");
    const response = await fetch(new URL("/remove", this.baseUrl), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids }),
      signal: AbortSignal.timeout(timeoutMs),
    });
    const result = await readJson(response);
    if (!response.ok || !result.ok) {
      throw new Error(result.err || `删除歌曲失败: HTTP ${response.status}`);
    }
    return result;
  }

  async jump({ flag = null, songId = null } = {}, timeoutMs = 30_000) {
    const body = songId ? { id: String(songId) } : { flag: Number(flag) || 1 };
    const response = await fetch(new URL("/jump", this.baseUrl), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(timeoutMs),
    });
    const result = await readJson(response);
    if (!response.ok || !result.ok) {
      throw new Error(result.err || `切歌失败: HTTP ${response.status}`);
    }
    return result;
  }

  stop() {
    if (this.child && this.child.exitCode === null) {
      try {
        this.child.kill();
      } catch {
        // 子进程可能已在错误事件和清理之间退出。
      }
    }
    this.child = null;
    this.startupError = null;
  }
}
