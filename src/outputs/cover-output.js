import { mkdir, rename, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import sharp from "sharp";

export const DEFAULT_COVER_PATH = "C:\\Program Files\\Now Playing\\Outputs\\cover.jpg";
const MAX_COVER_BYTES = 20 * 1024 * 1024;

export class CoverOutput {
  #revision = 0;
  #controller = null;
  #active = null;

  constructor({
    outputPath = process.env.NOW_PLAYING_COVER_PATH || DEFAULT_COVER_PATH,
    circlePath = process.env.NOW_PLAYING_COVER_CIRCLE_PATH || path.resolve(process.cwd(), "cover-circle.jpg"),
    circleSize = Number(process.env.NOW_PLAYING_COVER_CIRCLE_SIZE || 288),
    fetchImpl = globalThis.fetch,
    imageProcessor = sharp,
    timeoutMs = 15_000,
  } = {}) {
    this.outputPath = path.resolve(outputPath);
    this.circlePath = circlePath ? path.resolve(circlePath) : null;
    this.circleSize = Number.isInteger(circleSize) && circleSize > 0 ? circleSize : 288;
    this.fetchImpl = fetchImpl;
    this.imageProcessor = imageProcessor;
    this.timeoutMs = timeoutMs;
  }

  async update(track) {
    const revision = ++this.#revision;
    this.#controller?.abort();
    const coverUrl = String(track?.coverUrl || "").trim();
    if (!coverUrl) return { written: false, reason: "no-cover" };

    const url = new URL(coverUrl);
    if (url.protocol !== "http:" && url.protocol !== "https:") {
      throw new Error(`不支持的封面地址：${url.protocol}`);
    }

    const controller = new AbortController();
    this.#controller = controller;
    const job = this.#download(url, revision, controller);
    this.#active = job;
    try {
      return await job;
    } finally {
      if (this.#controller === controller) this.#controller = null;
      if (this.#active === job) this.#active = null;
    }
  }

  async close() {
    this.#revision += 1;
    this.#controller?.abort();
    try {
      await this.#active;
    } catch {
      // Shutdown should not fail because a cover request was cancelled.
    }
  }

  async #download(url, revision, controller) {
    const timeout = setTimeout(() => controller.abort(), this.timeoutMs);
    timeout.unref?.();
    try {
      const response = await this.fetchImpl(url, { signal: controller.signal });
      if (!response.ok) throw new Error(`下载封面失败：HTTP ${response.status}`);
      const bytes = Buffer.from(await response.arrayBuffer());
      if (revision !== this.#revision) return { written: false, reason: "superseded" };
      if (bytes.length > MAX_COVER_BYTES) {
        throw new Error(`封面文件过大：${bytes.length} 字节`);
      }

      const result = await this.#writeWithFallback(bytes, revision);
      if (!this.circlePath || !result.written || revision !== this.#revision) return result;

      try {
        const circleBytes = await this.imageProcessor(bytes)
          .resize(this.circleSize, this.circleSize, { fit: "cover", position: "centre" })
          .jpeg()
          .toBuffer();
        return {
          ...result,
          circle: await this.#writeOutput(circleBytes, this.circlePath, revision),
        };
      } catch (error) {
        return { ...result, circle: { written: false, error: error.message } };
      }
    } catch (error) {
      if (controller.signal.aborted && revision !== this.#revision) {
        return { written: false, reason: "superseded" };
      }
      if (controller.signal.aborted) throw new Error(`下载封面超时：${this.timeoutMs}ms`);
      if (error?.code === "EACCES" || error?.code === "EPERM") {
        const permissionError = new Error(
          `没有权限写入 ${this.outputPath}；请以管理员身份启动点歌姬，或授予输出目录写入权限`,
          { cause: error },
        );
        permissionError.code = error.code;
        throw permissionError;
      }
      throw error;
    } finally {
      clearTimeout(timeout);
    }
  }

  async #writeWithFallback(bytes, revision) {
    try {
      return await this.#writeOutput(bytes, this.outputPath, revision);
    } catch (error) {
      if (error?.code !== "EACCES" && error?.code !== "EPERM") throw error;
      const fallbackPath = path.resolve(process.cwd(), "cover.jpg");
      if (fallbackPath === this.outputPath) throw error;
      const result = await this.#writeOutput(bytes, fallbackPath, revision);
      return { ...result, fallback: true, requestedPath: this.outputPath };
    }
  }

  async #writeOutput(bytes, outputPath, revision) {
    if (revision !== this.#revision) return { written: false, reason: "superseded" };
    await mkdir(path.dirname(outputPath), { recursive: true });
    const temporaryPath = `${outputPath}.${process.pid}.${revision}.tmp`;
    try {
      await writeFile(temporaryPath, bytes);
      if (revision !== this.#revision) return { written: false, reason: "superseded" };
      await rename(temporaryPath, outputPath);
      return { written: true, path: outputPath, bytes: bytes.length };
    } finally {
      await rm(temporaryPath, { force: true }).catch(() => {});
    }
  }
}
