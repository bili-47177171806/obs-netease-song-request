import { EventEmitter } from "node:events";

const SEQUENTIAL_MODES = new Set(["playOrder", "playCycle"]);

export class PlaybackModeGuard extends EventEmitter {
  constructor(service) {
    super();
    this.service = service;
    this.poolSize = 0;
    this.restoreMode = null;
    this.lastManualVersion = 0;
    this.correcting = false;
    this.restoring = false;
  }

  noteInsertion(result) {
    const previous = result?.previousPlayingMode;
    if (result?.playingModeChanged && previous && !SEQUENTIAL_MODES.has(previous)) {
      this.restoreMode = previous;
      this.emit("remembered", previous);
    }
  }

  handlePoolChanged(size) {
    const previousSize = this.poolSize;
    this.poolSize = size;
    if (previousSize > 0 && size === 0 && this.restoreMode) {
      const mode = this.restoreMode;
      this.restoreMode = null;
      void this.#restore(mode);
    }
  }

  handleNowPlaying(current) {
    const manualVersion = Number(current?.manualModeVersion || 0);
    if (manualVersion > this.lastManualVersion) {
      this.lastManualVersion = manualVersion;
      if (this.poolSize > 0 && current.manualPlayingMode) {
        if (SEQUENTIAL_MODES.has(current.manualPlayingMode)) {
          this.restoreMode = null;
          this.emit("cleared", current.manualPlayingMode);
        } else {
          this.restoreMode = current.manualPlayingMode;
          this.emit("remembered", current.manualPlayingMode);
        }
      }
    }

    const mode = current?.playingMode;
    if (this.poolSize > 0 && mode && !SEQUENTIAL_MODES.has(mode)) {
      void this.#correct(mode);
    }
  }

  /**
   * 管理面板切换播放模式：等同于用户的一次手动选择。
   * 选顺序类就清掉待恢复目标；选随机/单曲循环则记下来，池清空后恢复。
   */
  async setUserMode(mode) {
    if (!mode) throw new Error("需要播放模式");
    const result = await this.service.setPlayingMode(mode);
    if (SEQUENTIAL_MODES.has(mode)) {
      this.restoreMode = null;
      this.emit("cleared", mode);
    } else if (this.poolSize > 0) {
      this.restoreMode = mode;
      this.emit("remembered", mode);
    }
    return result;
  }

  async #correct(fromMode) {
    if (this.correcting) return;
    this.correcting = true;
    try {
      const result = await this.service.ensureOrderMode();
      this.emit("corrected", fromMode, result.playingMode);
    } catch (error) {
      this.emit("guardError", "correct", error);
    } finally {
      this.correcting = false;
    }
  }

  async #restore(mode) {
    if (this.restoring) return;
    this.restoring = true;
    try {
      await this.service.setPlayingMode(mode);
      this.emit("restored", mode);
    } catch (error) {
      this.emit("guardError", "restore", error);
    } finally {
      this.restoring = false;
    }
  }
}
