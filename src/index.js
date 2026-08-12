import { buildSongCommand, parseSongCommand } from "./bot/command-parser.js";
import { canUseCommand, getFanLevel } from "./bot/access-control.js";
import { NowPlayingMonitor } from "./bot/now-playing-monitor.js";
import { PlaybackModeGuard } from "./bot/playback-mode-guard.js";
import { SongQueue } from "./bot/song-queue.js";
import { SongService } from "./cloudmusic/song-service.js";
import { NowPlayingCompatServer } from "./compat/now-playing-service.js";
import { CoverOutput } from "./outputs/cover-output.js";
import { showNowPlayingToast, showSongToast } from "./outputs/toast.js";
import { BilibiliDanmakuSource } from "./sources/bilibili-danmaku.js";
import { MockDanmakuSource } from "./sources/mock-danmaku.js";
import { BotState } from "./web/state.js";
import { WebServer } from "./web/server.js";

const service = new SongService();
const queue = new SongQueue(service);
const monitor = new NowPlayingMonitor(service);
const modeGuard = new PlaybackModeGuard(service);
const coverOutput = new CoverOutput();
const state = new BotState();
const danmakuSourceMode = String(process.env.DANMAKU_SOURCE || "bilibili").toLowerCase();
const source = danmakuSourceMode === "mock"
  ? new MockDanmakuSource()
  : new BilibiliDanmakuSource();
const webEnabled = process.env.WEB_UI !== "false";
const web = webEnabled ? new WebServer(state, buildActions()) : null;
const compatEnabled = process.env.NOW_PLAYING_COMPAT === "true";
const compat = compatEnabled ? new NowPlayingCompatServer(() => monitor.current) : null;
let shuttingDown = false;
let nowPlayingRequester = "";

function commandLabel(command) {
  const label = command.kind === "id" ? `ID ${command.value}` : `《${command.value}》`;
  return command.priority ? `插队 ${label}` : label;
}

/** 控制台照旧输出，同时把这条也送给管理面板。 */
function report(level, text) {
  if (level === "error") console.error(text);
  else console.log(text);
  state.note(level, text);
}

function syncQueue() {
  state.patch({ queue: queue.fullSnapshot() });
}

/** 管理面板能做的操作，全部走点歌姬内部同一套逻辑。 */
function buildActions() {
  return {
    async addSong({ value, priority = false, strategy = "first", user = "" } = {}) {
      const command = buildSongCommand({ value, priority, searchStrategy: strategy });
      if (!command) throw new Error("请填写歌名或歌曲 ID");
      const item = queue.enqueue(command, {
        user: String(user || "").trim() || "主播",
        fanLevel: Number.MAX_SAFE_INTEGER,
      });
      return { id: item.id };
    },
    async removeSong(id) {
      const result = await queue.remove(id);
      if (!result.removed) throw new Error("这首已经不在点歌池里了");
      report("ok", `[管理] 已移除 ${result.item.user} 的 ${commandLabel(result.item.command)}`);
      return { inserted: result.inserted };
    },
    async clearSongs() {
      const result = await queue.clear();
      report("ok", `[管理] 已清空点歌池（删除 ${result.pooled} 首，丢弃 ${result.dropped} 首待处理）`);
      return result;
    },
    async setPlayMode(mode) {
      const result = await modeGuard.setUserMode(mode);
      report("ok", `[管理] 播放模式已切换为 ${mode}`);
      return result;
    },
    async jump({ flag = null, songId = null } = {}) {
      const result = await service.jump({ flag, songId });
      report("ok", songId ? "[管理] 已切到指定歌曲" : `[管理] 已${flag === -1 ? "回到上" : "切到下"}一首`);
      return result;
    },
    async setAccepting(accepting) {
      state.patch({ accepting });
      report("ok", `[管理] ${accepting ? "恢复" : "暂停"}接收弹幕点歌`);
      return { accepting };
    },
  };
}

queue.on("queued", (item, position) => {
  modeGuard.handlePoolChanged(queue.totalSize);
  syncQueue();
  if (item.priority) {
    report("ok", `[插队] ${item.user}（粉丝团 ${item.fanLevel}）的 ${commandLabel(item.command)} 已加入插队池第 ${position} 位`);
  } else {
    report("ok", `[点歌] ${item.user} 的 ${commandLabel(item.command)} 已入池，前面 ${position - 1} 首`);
  }
});
queue.on("processing", (item) => {
  syncQueue();
  console.log(`[点歌] 正在处理 ${item.user} 的 ${commandLabel(item.command)}`);
});
queue.on("success", (item, result) => {
  const mode = result.searchMode ? `，搜索方式 ${result.searchMode}` : "";
  const fallback = result.possessiveFallback ? `，改查“${result.searchQuery}”` : "";
  report("ok", `[点歌] 成功：${result.name || item.command.value}（ID ${result.songId}${mode}${fallback}）`);
  modeGuard.noteInsertion(result);
  void showSongToast(result);
});
queue.on("failure", (item, error) => {
  syncQueue();
  report("error", `[点歌] 失败：${commandLabel(item.command)}，${error.message}`);
});
queue.on("poolChanged", (pool) => {
  modeGuard.handlePoolChanged(queue.totalSize);
  syncQueue();
  const text = pool.length
    ? pool.map((item, index) => `${index + 1}. ${item.name}`).join(" | ")
    : (queue.pending > 0 ? `等待插入 ${queue.pending} 首` : "空");
  console.log(`[点歌池] ${text}`);
});
queue.on("idle", () => {
  modeGuard.handlePoolChanged(queue.totalSize);
  syncQueue();
});

modeGuard.on("remembered", (mode) => {
  console.log(`[点歌池] 已记住用户播放模式 ${mode}，池结束后恢复`);
});
modeGuard.on("cleared", () => {
  console.log("[点歌池] 用户最后手动选择了顺序模式，不再恢复旧模式");
});
modeGuard.on("corrected", (from, to) => {
  console.log(`[点歌池] 已从 ${from} 临时切换到 ${to}`);
});
modeGuard.on("restored", (mode) => {
  console.log(`[点歌池] 已恢复用户播放模式 ${mode}`);
});
modeGuard.on("guardError", (action, error) => {
  console.error(`[点歌池] ${action === "restore" ? "恢复" : "纠正"}播放模式失败：${error.message}`);
});

monitor.on("change", (current, previous) => {
  modeGuard.handleNowPlaying(current);
  const songChanged = !previous || previous.songId !== current.songId;
  if (!current.songId) nowPlayingRequester = "";
  if (songChanged) {
    const requested = queue.markPlaying(current.songId);
    nowPlayingRequester = requested?.user || "";
  }
  state.patch({
    nowPlaying: { ...current, requester: nowPlayingRequester },
    backend: { ok: true },
  });
  if (!current.songId) return;
  if (songChanged) {
    const artists = (current.artists || []).join(" / ");
    console.log(`[NOW PLAYING] ${current.name || current.songId}${artists ? ` - ${artists}` : ""}`);
    void showNowPlayingToast(current);
    void coverOutput.update(current).then((result) => {
      if (result.written && result.fallback) {
        console.log(`[封面] 目标目录无写入权限，已改写 ${result.path}`);
      } else if (result.written) {
        console.log(`[封面] 已写入 ${result.path}`);
      }
      if (result.circle?.written) {
        console.log(`[封面] 已生成 ${result.circle.path}（${coverOutput.circleSize}×${coverOutput.circleSize}）`);
      } else if (result.circle?.error) {
        console.error(`[封面] 圆形尺寸版本写入失败：${result.circle.error}`);
      }
    }).catch((error) => {
      console.error(`[封面] 写入失败：${error.message}`);
    });
  }
});
monitor.on("error", (error) => {
  state.patch({ backend: { ok: false } });
  console.error(`[NOW PLAYING] 读取失败：${error.message}`);
});

monitor.on("recovered", () => {
  state.patch({ backend: { ok: true } });
  console.log("[NOW PLAYING] 读取已恢复");
});

source.on("message", (message) => {
  console.log(`[弹幕] ${message.user}: ${message.text}`);
  const command = parseSongCommand(message.text);
  if (!command) return;
  if (!state.accepting) {
    report("error", `[点歌] 已暂停接收，忽略 ${message.user} 的 ${commandLabel(command)}`);
    return;
  }
  if (!canUseCommand(command, message)) {
    report("error", `[插队] 已拒绝：${message.user} 粉丝团等级 ${getFanLevel(message)}，需要 11 级`);
    return;
  }
  queue.enqueue(command, message);
});
source.on("connected", ({ url, mock }) => {
  state.patch({ danmaku: { connected: true, mock, url } });
  report("ok", `[弹幕] 已连接 ${url}（${mock ? "模拟数据" : "B站真实数据"}）`);
});
source.on("disconnected", ({ retryInMs }) => {
  state.patch({ danmaku: { connected: false } });
  report("error", `[弹幕] 连接已断开，${Math.ceil(retryInMs / 1000)} 秒后重连`);
});
source.on("error", (error) => {
  state.patch({ danmaku: { connected: false } });
  console.error(`[弹幕] 连接错误：${error.message}`);
});

async function shutdown(exitCode = 0) {
  if (shuttingDown) return;
  shuttingDown = true;
  source.close();
  monitor.stop();
  await web?.close();
  await compat?.close();
  await coverOutput.close();
  await queue.waitForIdle();
  service.stop();
  process.exitCode = exitCode;
}

source.once("close", () => void shutdown());
process.once("SIGINT", () => void shutdown());
process.once("SIGTERM", () => void shutdown());

try {
  const status = await service.ensureAvailable();
  console.log(status.started ? "[点歌姬] 注入服务已自动启动" : "[点歌姬] 已连接注入服务");
  state.patch({ backend: { ok: true } });
  if (web) {
    try {
      await web.start();
      console.log(`[前端] 面板 ${web.url}/panel ｜ 当前播放 ${web.url}/now-playing ｜ 管理 ${web.url}/admin`);
    } catch (error) {
      // 端口被占等问题不该拖垮点歌本体。
      console.error(`[前端] 启动失败：${error.message}`);
    }
  }
  if (compat) {
    try {
      await compat.start();
      console.log(`[兼容服务] Now Playing API ${compat.url}/api/query`);
    } catch (error) {
      // 兼容端口冲突不影响点歌和 OBS 页面。
      console.error(`[兼容服务] 启动失败：${error.message}`);
    }
  }
  if (danmakuSourceMode === "mock") {
    console.log("[点歌姬] 模拟弹幕已就绪，输入 点歌[歌名]；用 :fan 11 模拟粉丝团等级；输入 :quit 退出");
  } else {
    console.log(`[点歌姬] 正在连接弹幕服务 ${source.url}`);
  }
  monitor.start();
  source.start();
} catch (error) {
  console.error(`[点歌姬] 启动失败：${error.message}`);
  service.stop();
  process.exitCode = 1;
}
