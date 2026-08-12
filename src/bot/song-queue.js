import { EventEmitter } from "node:events";

export class SongQueue extends EventEmitter {
  #items = [];
  #priorityPool = [];
  #normalPool = [];
  #processing = false;
  #currentItem = null;
  #nextId = 1;
  #idleWaiters = [];

  constructor(service) {
    super();
    this.service = service;
  }

  enqueue(command, context = {}) {
    const item = {
      id: this.#nextId++,
      command,
      priority: Boolean(command.priority),
      user: context.user || "未知用户",
      fanLevel: Number(context.fanLevel || 0),
      receivedAt: context.receivedAt || new Date(),
    };
    if (item.priority) {
      const lastPriority = this.#items.findLastIndex((pending) => pending.priority);
      this.#items.splice(lastPriority + 1, 0, item);
    } else {
      this.#items.push(item);
    }

    const position = item.priority
      ? this.#priorityPool.length + 1
      : this.poolSize + this.#items.length + (this.#processing ? 1 : 0);
    this.emit("queued", item, position);
    void this.#drain();
    return item;
  }

  get pending() {
    return this.#items.length + (this.#currentItem ? 1 : 0);
  }

  get poolSize() {
    return this.#priorityPool.length + this.#normalPool.length;
  }

  get totalSize() {
    return this.poolSize + this.pending;
  }

  snapshot() {
    return [...this.#priorityPool, ...this.#normalPool].map((item) => ({
      id: item.id,
      user: item.user,
      priority: item.priority,
      songId: String(item.result.songId),
      name: item.result.name || item.command.value,
      artists: item.result.artists || [],
    }));
  }

  /** 尚未插入网易云队列的请求：正在处理的排最前，其余按入队顺序。 */
  pendingSnapshot() {
    const describe = (item, state) => ({
      id: item.id,
      user: item.user,
      priority: item.priority,
      songId: null,
      name: item.command.value,
      state,
    });
    const waiting = this.#items.map((item) => describe(item, "waiting"));
    return this.#currentItem
      ? [describe(this.#currentItem, "processing"), ...waiting]
      : waiting;
  }

  /** 点歌池 + 待插入，供前端一次性渲染。 */
  fullSnapshot() {
    return [
      ...this.snapshot().map((entry) => ({ ...entry, state: "queued" })),
      ...this.pendingSnapshot(),
    ];
  }

  #findPool(id) {
    for (const pool of [this.#priorityPool, this.#normalPool]) {
      const index = pool.findIndex((item) => item.id === id);
      if (index >= 0) return { pool, index };
    }
    return null;
  }

  /**
   * 按点歌 id 移除。已插入网易云队列的会真正从队列删除；
   * 还没轮到处理的直接丢弃。正在处理中的那首无法中途撤销。
   */
  async remove(id) {
    const wanted = Number(id);
    const waitingIndex = this.#items.findIndex((item) => item.id === wanted);
    if (waitingIndex >= 0) {
      const [item] = this.#items.splice(waitingIndex, 1);
      this.emit("removed", item, { inserted: false });
      this.emit("poolChanged", this.snapshot());
      return { removed: true, inserted: false, item };
    }

    const found = this.#findPool(wanted);
    if (!found) {
      if (this.#currentItem?.id === wanted) {
        throw new Error("这首正在插入，等它完成后再删");
      }
      return { removed: false };
    }

    const item = found.pool[found.index];
    const result = await this.service.remove([item.result.songId]);
    // 网易云按 songId 删除，重复点了同一首时会一起被删；内存池必须同步移除。
    const songId = String(item.result.songId);
    const removedItems = [];
    for (const pool of [this.#priorityPool, this.#normalPool]) {
      for (let index = pool.length - 1; index >= 0; index -= 1) {
        if (String(pool[index].result.songId) === songId) {
          removedItems.unshift(...pool.splice(index, 1));
        }
      }
    }
    this.emit("removed", item, { inserted: true, result, removedItems });
    this.emit("poolChanged", this.snapshot());
    return { removed: true, inserted: true, item, removedItems, result };
  }

  /** 清空点歌池：已插入的从网易云队列删掉，等待中的直接丢弃。 */
  async clear() {
    const dropped = this.#items.splice(0);
    const pooled = [...this.#priorityPool, ...this.#normalPool];
    let result = null;
    if (pooled.length) {
      result = await this.service.remove(pooled.map((item) => item.result.songId));
      this.#priorityPool.length = 0;
      this.#normalPool.length = 0;
    }
    this.emit("cleared", { pooled: pooled.length, dropped: dropped.length, result });
    this.emit("poolChanged", this.snapshot());
    return { pooled: pooled.length, dropped: dropped.length, result };
  }

  markPlaying(songId) {
    const wanted = String(songId || "");
    if (!wanted) return null;
    let pool = this.#priorityPool;
    let index = pool.findIndex((item) => String(item.result.songId) === wanted);
    if (index < 0) {
      pool = this.#normalPool;
      index = pool.findIndex((item) => String(item.result.songId) === wanted);
    }
    if (index < 0) return null;

    const [item] = pool.splice(index, 1);
    this.emit("playing", item);
    this.emit("poolChanged", this.snapshot());
    return item;
  }

  waitForIdle() {
    if (!this.#processing && this.#items.length === 0) return Promise.resolve();
    return new Promise((resolve) => this.#idleWaiters.push(resolve));
  }

  async #drain() {
    if (this.#processing) return;
    this.#processing = true;

    while (this.#items.length > 0) {
      const item = this.#items.shift();
      this.#currentItem = item;
      const priorityTail = this.#priorityPool.at(-1);
      const normalTail = this.#normalPool.at(-1);
      const anchor = item.priority ? priorityTail : (normalTail || priorityTail);
      const afterSongId = anchor?.result.songId || null;
      this.emit("processing", item, { afterSongId });
      try {
        const result = await this.service.insert(item.command, { afterSongId });
        const poolItem = { ...item, result };
        this.#currentItem = null;
        if (item.priority) this.#priorityPool.push(poolItem);
        else this.#normalPool.push(poolItem);
        this.emit("success", item, result);
        this.emit("poolChanged", this.snapshot());
      } catch (error) {
        this.#currentItem = null;
        this.emit("failure", item, error);
      }
    }

    this.#processing = false;
    const waiters = this.#idleWaiters.splice(0);
    for (const resolve of waiters) resolve();
    this.emit("idle");
  }
}
