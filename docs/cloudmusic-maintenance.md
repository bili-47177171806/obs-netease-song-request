# 维护手册 · 网易云注入式「下一首播放」失效时怎么修

本方案依赖客户端**内部实现**（action 名、React 内部键、队列同步链路），客户端升级后可能失效。
这份手册说明：怎么判断失效、怎么重定位、各版本改了什么。配合 `backend/cloudmusic/research/` 里的探针脚本使用。

探针脚本是包内模块，**必须在项目根目录用模块方式运行**，直接按文件路径执行会报
`ModuleNotFoundError: No module named 'backend'`：

```powershell
python -m backend.cloudmusic.research.explore40      # 而不是 python backend/cloudmusic/research/explore40.py
```

下文提到的脚本名（explore40、explore51 等）都按这个方式运行。

---

## 一、先自检：是真失效，还是小毛病

升级客户端后跑一条已知歌：

```powershell
python -m backend.cloudmusic.engine "春を告げる" --json
```

| 返回 | 含义 |
|---|---|
| `"verified": true` | 一切正常，不用管 |
| `"verified": false` 但 `"ok": true` | 插入了但没排在当前曲后面（多半是 `offset` 语义变了） |
| `"ok": false, "err": "未找到客户端内部 store"` | React/redux 布局变了，按【第二节】重找 store |
| `"ok": false, "err": "搜不到……"` | 搜索流程变了（搜索框/标签结构变了），按【第三节】修 |
| `"ok": false, "err": "CDP 不可用"` | 客户端可能没开调试口 / 不再是 Chromium 内核（**架构级变化**，见【第五节】） |
| 返回里 `searchMode` 缺失 / 一直等于 `"ui"` | 客户端 API 搜索层挂了（非正式接口），靠 UI 回退兜底，见【三·补充】 |
| 脚本异常/连接拒连 | 9222 没起来 / WebSocket 被拦 |

自检完打开客户端「播放列表」抽屉肉眼确认顺序：**当前曲 → 插入曲 → 原下一首**。
如果是弹幕点歌姬场景（Node），跑通一条 `点歌[X]` 等同全链路自检。

---

## 二、store 找不到了 → 重定位 redux store

脚本：`backend/cloudmusic/research/explore40.py`、`backend/cloudmusic/research/explore41.py`

思路（换 React 版本只改前缀，方法论不变）：
1. 任取一个元素，找它身上以 `__react` 开头的键。不同 React 版本：
   - `__reactInternalInstance$…` → React 16/17
   - `__reactFiber$…` → React 18+
   - 键名变了就搜 `Object.keys(el).filter(k=>k.startsWith('__react'))` 看现在是什么
2. 沿该 fiber 的 `.return` 向上最多 400 层，找：
   - `fiber.memoizedProps.store`（react-redux `<Provider store={...}>`，v7 直接是 prop）
   - `fiber.type._currentValue.store`（Context，部分版本）
3. 找到后 `window.__STORE__ = store`，验证 `store.getState()` 里仍有 `playingList`、`playing` 等 reducer。

改 `backend/cloudmusic/engine.py` 的 `find_store()` 时：把「前缀候选」换成新发现的键即可。

---

## 三、store 在但插入不生效 → 重定位 action

脚本：`backend/cloudmusic/research/explore50.py`（列 action 类型）、`backend/cloudmusic/research/explore51.py`（看 saga 实现）

1. 抓 bundle：`backend/cloudmusic/research/explore29.py` 硬编码的 7 个 `orpheus://orpheus/pub/hybrid/*.chunk.<hash>.js`。
   **升级后 hash 会变**，先看资源清单：
   ```
   Page.getResourceTree → 取所有 .js URL（backend/cloudmusic/research/explore24.py 干这事）
   ```
2. 列 action 类型：搜 `"playingList/…"` 命名空间（explore50.py）。重点找：
   - `playingList/addItemToCurPlayingList` —— 本地插入主入口
   - `playingList/onAddItemToCurPlayingList` —— **陷阱**：这是 cloud 会话路径，改了本地列表 = 失效信号
3. 读 `addItemToCurPlayingList` 的 saga 体（explore51.py），确认：
   - `options.offset` 语义是否还是「插到下标 +1」
   - `trackFrom.resourceType` 取值（`$.m.track` 等）有没有变
   - 载荷字段是否增减
4. 按新结构改 `backend/cloudmusic/engine.py` 的 `insert_next()` payload。

**判断 cloud 路径踩雷的旁证**：dispatch `onAddItem…` 后 `store.getState()['async:playingListHandoff'].playingCommands` 只增不减、`curPlayingList` 不变——说明走错 action 了。

### 三·补充：搜索层（API 搜索 vs UI 搜索）

`backend/cloudmusic/engine.py` 现在的搜索分两层（`search_song_api` → 失败自动回退 `search_song`/UI）：
- **API 层** `https://music.163.com/…/search` 系列是非正式接口，被限流/改接口时最常见失效点。
  特征：返回 `searchMode: "ui"`（回退成功）或直接「搜不到」。改接口后只需替换 `search_song_api`
  里的 URL/参数（接口格式网上有大量维护项目可参考，如 `NeteaseCloudMusicApi`）。
- **UI 层** 是客户端自己的搜索框+单曲标签，跟客户端版本绑定；它失效才说明搜索 DOM 变了，
  按上文重定位（搜索框 `input[type=search]`、标签「单曲」、结果行 `div.tr` 的 fiber resource）。

---

## 四、同步到原生那步断了 → 重查同步链路

脚本：`backend/cloudmusic/research/explore51.py`、`backend/cloudmusic/research/explore53.py`

本地插入后队列没同步到原生（`verified` 逻辑查 `curPlayingList` 通过，但抽屉不变）：
1. 确认 `playingList/syncCurPlayingListToNative` 还在、还是被 saga 调用
2. `replaceCurPlayingList` 之后是否还触发同步
3. 原生 `player.*` 方法面有没有变：`backend/cloudmusic/research/explore48.py` 枚举 `At.call("…")` 全表
   （关键方法：`player.removeAll` / `player.addListElement` / `player.setCurrentPlay`）

---

## 五、架构级变化（最重）

- `9222` 永远起不来，或网页目标消失（`/json` 无 `orpheus://orpheus/pub/app.html` 页面）
  → 客户端可能抛弃了 CEF / 改成自绘原生 UI。这套注入失效。
  备选策略：退回「真实鼠标点原生菜单」（CDP 右键唤出原生菜单 → 系统级坐标点击），
  或 DLL 注入调原生 `winhelper.popupMenu`。
- 官方不再提供 `music.163.com/api/song/detail` → `--id` 模式失效，但搜索模式仍可用（数据从客户端页面拿）。

---

## 六、版本变更记录表

每次客户端升级 / 本方案修好后，在这记一笔，下次对照。

| 日期 | 客户端版本 | 变化点 | 处理 |
|---|---|---|---|
| 2026-08-11 | 3.1.37.205354 | 基线：`__reactInternalInstance$`、`addItemToCurPlayingList`、`options.offset` | 首次交付 |
| | | | |

## 七、兜底：research 探针脚本速查

统一用 `python -m backend.cloudmusic.research.<脚本名>` 在项目根目录运行。

| 用途 | 脚本 |
|---|---|
| 连 CDP 看页面目标 | `backend/cloudmusic/cdp.py` + `first_page()` |
| 枚举 JS bundle 资源 | explore24 |
| 定位 store | explore40 / explore41 |
| 列 playingList action 类型 | explore50 |
| 看 addItem saga 实现 | explore51 |
| 验证队列同步 | explore52 / explore53 |
| 枚举原生方法全表 | explore48 / explore49 |
| 判断右键菜单是否原生 | explore19 / explore20 / wlist.py（窗口枚举） |

> 建议：客户端升级后**先跑一条验证**再依赖它。失效时按上文流程重定位，通常改动只在
> `backend/cloudmusic/engine.py` 的 `find_store()`、`insert_next()` 或 `search_song_api()` 几处。
>
> **弹幕点歌姬依赖关系**：`src/`（Node）→ `backend/cloudmusic/server.py`（HTTP）→ `backend/cloudmusic/engine.py`（注入核心）。
> Python 侧修好后，跑 `npm test` + 一条 `点歌[X]` 确认全链路；Node 层一般不用动，
> 只有当你改了 `/health`、返回字段名或启动方式时才需要同步改 `src/` 里的调用。