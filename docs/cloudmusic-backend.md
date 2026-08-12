# 网易云音乐 PC · 注入式「下一首播放」

把任意一首歌**直接插进当前播放队列、排到下一首**（等价于右键菜单「下一首播放」），
全程**程序化注入**，不模拟鼠标键盘、不碰 UI 坐标。给「其他应用接入」开了一扇干净的口子。

## 原理

网易云 PC 客户端（3.1.37，Chromium 内核）的界面是网页渲染的。我们做三件事：

1. **开 CDP 调试口** —— 以 `cloudmusic.exe --remote-debugging-port=9222` 启动，
   拿到渲染进程的完整控制权（底层就是在进程内干活，正是你要的"注入"）。
2. **定位内部 store** —— 首页/任意界面沿 React fiber 链找到 redux store（`window.__STORE__`）。
3. **调内部 action 插队** —— 派发 `playingList/addItemToCurPlayingList`，
   `options.offset = 当前播放曲在队列里的下标`；应用自己完成本地插入 →
   `replaceCurPlayingList` → `syncCurPlayingListToNative`，原生播放器同步更新。

实测原生播放列表 {"播放列表 206 → 207"，顺序 = 当前曲 → 插入曲 → 原下一首} 完美生效。

> 说明：本方案不走 UI 右键（那只键盘鼠标模拟的做不到后台、太脆），也不切 cloud 会话同步
> （那条通道不驱动本地播放器）。就是直接戳客户端自己的插入逻辑。

## 文件

| 文件 | 说明 |
|---|---|
| `backend/cloudmusic/engine.py` | 主工具（CLI） |
| `backend/cloudmusic/server.py` | 可选的 HTTP 服务，供其他应用调用 |
| `backend/cloudmusic/cdp.py` | 极简 CDP 客户端 |
| `src/` | Node.js 弹幕点歌姬 |
| `test/` | Node.js 指令、队列和服务调用测试 |
| `backend/cloudmusic/research/` | 全程逆向探针（审计留档，可忽略） |

## 用法

### CLI（一次性）

```powershell
python -m backend.cloudmusic.engine "春を告げる"                    # 按歌名搜索，插第一首结果
python -m backend.cloudmusic.engine "IF Else" --artist mochari --classic-search # 经典搜索，精确匹配歌手
python -m backend.cloudmusic.engine 3384055850 --id                 # 按网易云 songId 直接插入
python -m backend.cloudmusic.engine "Wow War Today" --json          # 机器可读输出
```

首次运行如果本地 `9222` 没开，会自动**带参重启客户端**（登录态保留），稍等即可。

### HTTP 服务（给其他应用接入）

```powershell
python -m backend.cloudmusic.server          # 默认监听 http://127.0.0.1:8866
```

其他程序（或脚本、网页、插件）只需 POST：

```powershell
curl -X POST http://127.0.0.1:8866 -H "Content-Type: application/json" ^
  -d '{"song": "IF Else"}'

curl -X POST http://127.0.0.1:8866 -H "Content-Type: application/json" ^
  -d '{"song": "IF Else", "artist": "mochari", "searchStrategy": "classic"}'

curl -X POST http://127.0.0.1:8866 -H "Content-Type: application/json" ^
  -d '{"id": "3384055850"}'

# 插到指定歌曲之后（点歌池按顺序追加时使用）：
curl -X POST http://127.0.0.1:8866 -H "Content-Type: application/json" ^
  -d '{"id": "3384055850", "afterSongId": "1911300549"}'

# 也可以直接传完整歌曲对象（最精确，免搜索）：
curl -X POST http://127.0.0.1:8866 -H "Content-Type: application/json" ^
  -d '{"track": {"id": 3384055850, "name": "IF Else", "artists": [{"name":"mochari"}], "album": {"name":"..."}}}'
```

传 `song` 时服务会先调用网易云搜索接口取得 songId，再在客户端上下文中拉取完整歌曲对象。
`searchStrategy` 默认为 `first`，直接选择 API 第一条；传 `classic` 时按标题和歌手文字评分；
搜索接口不可用或取详情失败时，会自动回退到客户端 UI 搜索。返回中的 `searchMode` 为 `api` 或 `ui`。
传 `id` 或 `track` 会跳过搜索。

搜索接口是网易云客户端使用的非正式接口，可能受限流或接口变更影响；回退逻辑用于保证兼容性。

统一返回：

```json
{"ok": true, "songId": "3384055850", "name": "IF Else", "searchMode": "api", "searchStrategy": "first",
 "searchQuery": "IF Else", "possessiveFallback": false,
 "offset": 154, "currentIdx": 154, "queueLenBefore": 207,
 "verified": true, "around": {"succeeded": true, "curId": "...", "idx": 154,
 "after": ["当前曲", "插入曲", "下一首"], "len": 208}}
```

`verified: true` 表示已确认插在当前播放曲之后。

读取当前播放：

```powershell
curl http://127.0.0.1:8866/now-playing
```

```json
{"ok": true, "songId": "2149887904", "name": "春日影",
 "artists": ["CRYCHIC"], "album": "春日影", "durationMs": 257840,
 "coverUrl": "http://p3.music.126.net/...", "playingState": 2}
```

### Node.js 弹幕点歌姬

要求 Node.js 18 或更高版本：

```powershell
npm install
npm start
```

点歌姬会检查 `http://127.0.0.1:8866/health`。如果 Python 注入服务尚未运行，会自动启动
`backend/cloudmusic/server.py` 并等待网易云客户端就绪。默认还会连接 `ws://127.0.0.1:8766/`，直接接收 B 站
弹幕服务广播的 JSON；无需鉴权或订阅。普通 `message` 事件会进入指令解析，其他事件不会触发点歌。
连接断开后会自动重连。

需要在终端模拟弹幕时，使用模拟消息源启动：

```powershell
$env:DANMAKU_SOURCE="mock"
npm start
```

随后可在终端输入：

```text
弹幕> 大家好
弹幕> 点歌[IF Else]
弹幕> 点歌[3384055850]
弹幕> 点歌【春を告げる】
弹幕> 点歌 Wow War Tonight
弹幕> 点歌Wow War Tonight
弹幕> 点歌3384055850
弹幕> 模糊点歌[被生命所厌恶]
弹幕> 经典搜索[被生命所厌恶]
弹幕> :fan 10
弹幕> 插队[IF Else]              # 拒绝
弹幕> :fan 11
弹幕> 插队[IF Else]              # 插到点歌池第一位
弹幕> :quit
```

`点歌` 和 `模糊点歌` 直接选择网易云 API 排名第一的结果；`经典搜索` 使用标题/歌手文字匹配算法。
普通点歌遇到 `XXX的YYY` 时会先搜索完整文本；如果候选中没有匹配标题，就把它解释为“歌手的歌曲”，
改搜 `YYY XXX` 并取第一条。例如 `点歌25时的命嫌` 会改搜 `命嫌 25时`，选择
《命に嫌われている》（ID `2623481920`）。真实同名歌曲（例如《我们的爱》）不会触发反转。
纯数字内容始终按 songId 处理。请求严格串行；某一首失败
不会阻塞后续点歌。`:quit` 会等待已入队请求处理完成后退出。

点歌姬在内存中维护两个“已插入、尚未开始播放”的 FIFO 池：插队池在前、普通点歌池在后。
普通点歌追加到普通池尾；`插队[歌名/ID]` 追加到插队池尾，因此后来的插队不会越过更早的插队。
最终顺序始终是“当前曲 → 插队池 → 普通点歌池”。NOW PLAYING 检测到池中歌曲开始播放后
会自动将它移出对应池。

网易云的随机播放和单曲循环不会保证“下一首”按点歌池顺序执行。每次插入前，服务会通过客户端
自身的播放模式控件切到按列表顺序播放；`playOrder`（顺序播放）和 `playCycle`（列表循环）都会
保留。点歌池非空时，NOW PLAYING 监控也会纠正用户中途切换到随机/单曲循环的情况。

服务通过可信点击标记记录用户最后一次手动选择的播放模式，机器人自己的自动切换不会覆盖它。
如果点歌池开始前或运行中最后一次手动选择是随机/单曲循环，池清空后会自动恢复；如果用户后来
手动选择了顺序播放或列表循环，则清除旧恢复目标，池结束后保持用户新选择。

`插队`要求粉丝团等级不低于 11。真实弹幕的 `fansMedalLevel` 会映射为内部 `fanLevel`；模拟模式
通过 `:fan 11` 修改等级。点歌池是进程内状态，重启 Node 点歌姬后会清空，不会删除已经插入
网易云播放列表的歌曲。

可选环境变量：

| 变量 | 默认值 | 说明 |
|---|---|---|
| `CLOUDMUSIC_API_URL` | `http://127.0.0.1:8866` | Python 注入服务地址 |
| `CLOUDMUSIC_AUTO_START` | `true` | 设为 `false` 时不自动启动 Python 服务 |
| `PYTHON_BIN` | `python` | Python 可执行文件 |
| `DANMAKU_SOURCE` | `bilibili` | 设为 `mock` 时改用终端模拟弹幕 |
| `DANMAKU_WS_URL` | `ws://127.0.0.1:8766/` | 本地弹幕 WebSocket 服务地址 |
| `MOCK_DANMAKU_USER` | `模拟用户` | 模拟弹幕用户名 |
| `MOCK_DANMAKU_FAN_LEVEL` | `0` | 模拟弹幕初始粉丝团等级 |
| `CLOUDMUSIC_TOAST` | `true` | 设为 `false` 时关闭成功后的 Windows 全局通知 |
| `NOW_PLAYING_COVER_PATH` | `C:\Program Files\Now Playing\Outputs\cover.jpg` | 当前播放封面的输出路径 |
| `NOW_PLAYING_COVER_CIRCLE_PATH` | `cover-circle.jpg` | 播放器圆孔尺寸封面的输出路径 |
| `NOW_PLAYING_COVER_CIRCLE_SIZE` | `288` | 圆孔封面边长（按 UI 中间圆孔直径） |

真实弹幕会保留 `uid`、`openId`、头像、粉丝牌、大航海、房管、表情和颜色字段。点歌功能当前只消费
昵称、消息正文和粉丝牌等级。

点歌成功和 NOW PLAYING 切歌时，Windows 桌面会显示系统级 Toast 通知；通知失败不会影响歌曲插入。
每次切歌还会下载当前封面并原子更新 `cover.jpg`。如果首选目录没有写入权限，会自动回退到点歌姬
启动目录下的 `cover.jpg`；同时生成按播放器圆孔直径裁切的 `cover-circle.jpg`。其他写入失败也不会
中断播放监控。

运行测试：

```powershell
npm test
```

## 前置与注意

- 需要已装网易云 PC 客户端（默认路径 `C:\Program Files\NetEase\CloudMusic\cloudmusic.exe`）。
- 依赖 Python 的 `websocket-client`（本机已装；`pip install websocket-client` 即可）。
- **客户端版本**：方案针对 3.1.x（Chromium 内核）。客户端升级后若失效，先跑一条歌看
  `verified`，再按 **[维护手册](cloudmusic-maintenance.md)** 的自检/重定位流程修（通常只改 `backend/cloudmusic/engine.py` 的
  `find_store()` / `insert_next()` / `search_song_api()` 几处）。
- 插入是"追加新条目"：同一首歌可重复插多次；`--id` 模式会自动先拉完整歌曲信息，不会出空白行。

## 其他应用接入思路（服务器模式之后）

- 局域网/本机其他进程 → POST JSON 到 `127.0.0.1:8866`。
- Node.js 点歌姬可 POST `{song, searchStrategy}`；`first` 取 API 第一条，`classic` 做文字匹配。也可以自行搜索后 POST `{id}`。
- 用歌曲详情 API（如 `https://music.163.com/api/song/detail/?ids=[id]`）拿 songId → 直接 `--id` 或传 full track。
- 想一次插多首，外部循环 POST 即可（或用 `trackList` 一次性传数组——需要改 `insert_next`
  的 `trackList: [resource]` 为 `trackList: resources`，action 天然支持批量）。
