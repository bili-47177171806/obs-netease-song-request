import notifier from "node-notifier";

export function showSongToast(result, { enabled = process.env.CLOUDMUSIC_TOAST !== "false" } = {}) {
  if (!enabled || process.platform !== "win32") return Promise.resolve(false);

  const songName = result.name || result.songId || "歌曲";
  const mode = result.searchMode === "api" ? "API 搜索" : "已匹配";

  return new Promise((resolve) => {
    notifier.notify({
      title: "网易云点歌",
      message: `已加入下一首：${songName}`,
      subtitle: `${mode} · ID ${result.songId || "未知"}`,
      sound: false,
      wait: false,
      timeout: 5,
    }, (error) => {
      if (error) {
        console.error(`[Toast] 发送失败：${error.message || error}`);
        resolve(false);
        return;
      }
      resolve(true);
    });
  });
}

export function showNowPlayingToast(track, { enabled = process.env.CLOUDMUSIC_TOAST !== "false" } = {}) {
  if (!enabled || process.platform !== "win32" || !track?.songId) return Promise.resolve(false);

  const artists = (track.artists || []).join(" / ");
  return new Promise((resolve) => {
    notifier.notify({
      title: "NOW PLAYING",
      message: `${track.name || "未知歌曲"}${artists ? ` - ${artists}` : ""}`,
      sound: false,
      wait: false,
      timeout: 5,
    }, (error) => resolve(!error));
  });
}
