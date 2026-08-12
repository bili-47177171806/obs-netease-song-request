# 网易云 OBS 点歌姬

面向 B 站直播间的网易云音乐点歌姬。它从本地弹幕姬接收 WebSocket 弹幕指令，调用网易云音乐 PC 客户端的本地 CDP 注入服务，把歌曲插入“下一首播放”队列，并提供可直接放进 OBS 的点歌池与 Now Playing 页面。

> 本项目是社区工具，不是网易云音乐或哔哩哔哩官方项目。网易云部分依赖桌面客户端内部页面结构，客户端升级后可能需要重新适配。

## 功能

- `点歌`、`模糊点歌`、`经典搜索` 三种搜索策略
- 支持歌曲名、网易云歌曲 ID、中文括号和无空格指令
- 支持“歌手的歌名”输入失败后的反向搜索，例如 `点歌25时的命嫌`
- 普通点歌池与插队池分离，插队池先进先出
- `插队[歌曲]` 仅允许粉丝团等级 `11+`
- NOW PLAYING 监控、播放模式保护、短暂超时自动重试
- Windows Toast 成功通知
- 原尺寸封面输出、播放器圆孔裁切封面输出
- OBS 浏览器源页面、主播管理面板、SSE 实时状态
- B 站弹幕 WebSocket 断线自动重连
- 可选的 Widdit Now Playing Service 只读 API 兼容服务

## 架构

```text
B 站弹幕姬 (WebSocket :8766)
          |
          v
Node.js 点歌姬 (:8899) -----> Python 注入服务 (:8866) -----> 网易云音乐 PC 客户端 (CDP :9222)
          |
          +---- OBS /panel
          +---- OBS /now-playing
          +---- 主播 /admin
```

Node.js 负责弹幕、权限、双队列和网页；Python 服务负责与网易云客户端通信。Python 服务只监听 `127.0.0.1`，管理面板默认也只监听本机。

## 环境要求

### 必需

- Windows 10/11
- Node.js 18 或更高版本
- Python 3.10 或更高版本
- 网易云音乐 PC 客户端，并已登录账号
- 一个能提供本地 WebSocket 弹幕的弹幕姬，默认地址为 `ws://127.0.0.1:8766/`

### Python 依赖

```powershell
python -m pip install -r requirements.txt
```

网易云客户端需要允许 CDP 调试端口 `9222`。如果客户端没有运行，点歌姬会尝试自动启动；首次使用仍需要手动登录网易云。

## 安装与启动

```powershell
git clone https://github.com/bili-47177171806/obs-netease-song-request.git
cd obs-netease-song-request
npm install
python -m pip install -r requirements.txt
npm start
```

启动后访问：

| 页面 | 地址 | 用途 |
|---|---|---|
| 点歌池 | `http://127.0.0.1:8899/panel` | OBS 浏览器源 |
| 当前播放 | `http://127.0.0.1:8899/now-playing` | OBS 浏览器源 |
| 管理面板 | `http://127.0.0.1:8899/admin` | 主播手动加歌、删歌、跳歌 |
| 状态 JSON | `http://127.0.0.1:8899/api/state` | 调试或二次开发 |

### Now Playing Service 兼容模式

需要让基于 [Widdit/now-playing-service](https://github.com/Widdit/now-playing-service) API 的组件读取本项目时，启用兼容服务：

```powershell
$env:NOW_PLAYING_COMPAT = "true"
npm start
```

服务默认监听 `http://127.0.0.1:9863`。已兼容 `/query`、`/api/query`、播放器/歌曲/进度拆分查询、`hasSong`、`isConnected` 和封面 Base64 转换接口。数据仍由本项目的网易云 CDP 后端提供，不需要启动原项目的 Java 或 C# 程序。

歌词、配置管理、插件和播放控制不属于当前兼容范围；访问这些接口会返回 `404`，以免第三方程序误以为操作成功。

### 添加到 OBS

1. 打开 OBS，添加“浏览器”源。
2. 点歌池源填写 `/panel`，建议宽 `480`、高 `540`。
3. 当前播放源填写 `/now-playing`，按你的播放器布局设置宽高。
4. 管理面板不要作为直播画面源，只在主播本机打开 `/admin`。

## 弹幕姬 WebSocket 协议

点歌姬不会连接 B 站官方接口，而是连接你的本地弹幕姬：

```text
ws://127.0.0.1:8766/
```

连接后服务端直接发送 JSON，不需要鉴权或订阅。点歌姬只消费 `message` 事件，`enter`、`gift`、`sc`、`guard` 等事件会被忽略但不会断开连接。

连接状态：

```json
{"sys":"connected","mock":false}
```

弹幕消息（推荐格式）：

```json
{
  "type": "message",
  "uid": "123456",
  "openId": "open-id",
  "uname": "观众昵称",
  "message": "点歌 春を告げる",
  "fansMedalName": "粉丝牌",
  "fansMedalLevel": 11,
  "guardLevel": 0,
  "face": "https://example.com/avatar.jpg",
  "color": "#ffffff"
}
```

必需字段：`type`（值为 `message`）、`message`、`uname`。权限相关字段：`fansMedalLevel`（缺省按 `0` 处理）。其余用户字段均可缺省。也兼容把字段放在 `data` 对象中的格式：`{"type":"message","data":{...}}`。

## 弹幕指令

括号和空格都可以省略：

| 指令 | 说明 |
|---|---|
| `点歌[歌名/ID]` | API 搜索结果第一名，加入普通点歌池 |
| `模糊点歌[歌名]` | 与 `点歌` 相同，保留语义别名 |
| `经典搜索[歌名]` | 标题与歌手文字匹配优先 |
| `插队[歌名/ID]` | 加入插队池首部，要求粉丝团 `11+` |

示例：

```text
点歌 誰にもなれない私だから
点歌爆裂绽放
经典搜索[被生命所厌恶]
点歌25时的命嫌
插队 千本桜
```

普通队列顺序始终是：当前播放 -> 插队池 -> 普通点歌池。两类队列均按先来先播，后来的插队不会越过更早的插队请求。点歌池为空后，播放模式会恢复到用户最近一次手动选择的模式。

## 模拟弹幕

没有弹幕姬时可以用 stdin：

```powershell
$env:DANMAKU_SOURCE = "mock"
$env:MOCK_DANMAKU_FAN_LEVEL = "11"
npm start
```

然后输入 `点歌 春を告げる`、`插队 千本桜` 或 `:quit`。

## 配置

| 环境变量 | 默认值 | 说明 |
|---|---|---|
| `DANMAKU_SOURCE` | `bilibili` | 设为 `mock` 使用终端模拟弹幕 |
| `DANMAKU_WS_URL` | `ws://127.0.0.1:8766/` | 弹幕姬 WebSocket 地址 |
| `CLOUDMUSIC_API_URL` | `http://127.0.0.1:8866` | Python 注入服务地址 |
| `CLOUDMUSIC_AUTO_START` | `true` | 是否自动启动 Python 服务 |
| `PYTHON_BIN` | `python` | Python 可执行文件 |
| `WEB_HOST` | `127.0.0.1` | Web 监听地址，不建议改成公网地址 |
| `WEB_PORT` | `8899` | Web 端口 |
| `WEB_UI` | `true` | 设为 `false` 关闭网页服务 |
| `NOW_PLAYING_COMPAT` | `false` | 设为 `true` 启动 Widdit Now Playing API 兼容服务 |
| `NOW_PLAYING_COMPAT_HOST` | `127.0.0.1` | 兼容服务监听地址 |
| `NOW_PLAYING_COMPAT_PORT` | `9863` | 兼容服务端口 |
| `CLOUDMUSIC_TOAST` | `true` | Windows Toast 开关 |
| `NOW_PLAYING_COVER_PATH` | `C:\Program Files\Now Playing\Outputs\cover.jpg` | 原尺寸封面输出 |
| `NOW_PLAYING_COVER_CIRCLE_PATH` | `cover-circle.jpg` | 圆孔裁切封面输出 |
| `NOW_PLAYING_COVER_CIRCLE_SIZE` | `288` | 圆孔输出边长 |

## 开发与测试

```powershell
npm test
python -m backend.cloudmusic.server --port 8866
python -m backend.cloudmusic.engine "歌曲名" --json
```

测试覆盖指令解析、权限、双队列、播放模式、NOW PLAYING、封面输出、Web API 和弹幕协议。

## 安全与隐私

- 管理 API 默认无鉴权，只监听 `127.0.0.1`，不要直接暴露到公网。
- 不要提交网易云登录信息、Cookie、调试日志、封面文件或直播间用户数据。
- 网易云 CDP 端口拥有客户端页面控制能力，只应绑定本机。
- 本项目不存储弹幕用户资料；仅在进程内使用昵称和粉丝牌等级完成权限判断。

## 许可证

本项目使用 MIT License。网易云音乐、哔哩哔哩及其相关客户端、接口和素材的权利归各自权利人所有。

## 贡献

请先阅读 [CONTRIBUTING.md](CONTRIBUTING.md)。提交网易云客户端适配时，请附上客户端版本、系统版本、复现步骤和 `verified` 结果；不要提交账号数据或完整调试日志。
