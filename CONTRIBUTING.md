# 贡献指南

感谢参与维护网易云 OBS 点歌姬。

## 提交前检查

```powershell
npm test
node --check src/index.js
python -m compileall backend
```

涉及网易云客户端适配时，请记录：

- 网易云音乐 PC 客户端版本
- Windows 版本
- 使用的启动参数和 CDP 端口
- `python -m backend.cloudmusic.engine "测试歌曲" --json` 的结果
- 是否 `verified: true`

不要提交网易云账号信息、Cookie、完整弹幕日志、封面文件或包含用户资料的截图。

## 代码约定

- Node.js 使用 ESM，优先使用现有模块和事件接口。
- Python 适配代码保持标准库优先；第三方依赖写入 `requirements.txt`。
- 新功能应补充对应的 Node 或 Python 测试。
- 管理 API 默认只允许本机访问，除非同时设计鉴权方案。

## Pull Request

请说明变更目的、影响范围、测试命令和网易云客户端版本。UI 改动请附桌面截图；协议改动请附 JSON 示例。
