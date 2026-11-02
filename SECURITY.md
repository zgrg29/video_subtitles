# 安全策略

## 支持的版本

| 版本 | 支持 |
| --- | --- |
| 0.1.x | 是 |

## 报告安全问题

请使用 GitHub 仓库的 **Security → Report a vulnerability / Private vulnerability reporting**。不要在公开 Issue 中粘贴 API Key、临时 `oss://` 链接、带签名的 `transcription_url`、真实视频、字幕内容或个人路径。

如果仓库尚未开启私密报告，请先创建一个**不含敏感细节**的 Issue，说明“需要私下报告安全问题”，不要附上 Key 或数据。

## 密钥处理

- API Key 只由用户在设置页输入。
- 使用 Windows DPAPI 的 `CryptProtectData` 加密，绑定当前 Windows 用户。
- 保存在 `%LOCALAPPDATA%\QwenSubtitle\secrets.bin`；如果该目录不可写，回退到 EXE 同级 `portable-data`。不写入 `settings.json`。
- 不写入源码、测试、文档、截图、日志、命令行参数、环境变量文件。
- 请求时只放在 HTTPS `Authorization: Bearer` 头里。
- 异常文本会脱敏 `sk-…` 与 `Bearer …`，避免进入 UI 或日志。
- 设置页不显示 Key 明文；显示/隐藏按钮只在用户主动点击时临时显示输入框内容。

DPAPI 能防止其他 Windows 用户或离线拷贝直接读取，但**不能防御已在你账户下运行的恶意软件**。如果设备被入侵，请立即在百炼控制台轮换 Key。

## 如果 Key 泄露

1. 立即在阿里云百炼 / Model Studio 控制台删除或轮换该 Key。
2. 检查账单和调用日志。
3. 如果 Key 曾进入 Git 历史，仅删除文件不够；需要重写历史并强制推送，或直接废弃仓库重新发布。
4. 检查截图、Issue、PR、日志、构建产物中是否出现 Key。

## 公开仓库规则

禁止提交：

- 真实 API Key、Bearer token、私钥、临时上传链接、签名下载链接。
- 真实姓名、个人邮箱、手机号、住址、个人主页、`C:\Users\<name>` / `/home/<name>` 路径。
- 真实视频、音频、字幕、客户资料、聊天记录、课程内容。
- 带个人信息的截图（资源管理器路径、账号头像、控制台账号名等）。

提交前：

```powershell
python scripts/check_public_repo.py
```

该脚本只能发现常见模式，不能替代人工检查 Git 历史、图片和二进制文件。

## 数据上传边界

- 原始视频不离开本机。
- 提取出的音频会上传到阿里云百炼的临时存储，用于 ASR。
- 仅译文/双语模式会把字幕文本发送给 Qwen-MT；仅原文模式不发送翻译请求。
- 不加入遥测、分析、广告、账号或自动上传。

详见 [PRIVACY.md](PRIVACY.md)。

## 分发与 EXE

- 默认分发是便携目录版 ZIP。EXE 未使用代码签名证书，Windows SmartScreen 可能提示“未知发布者”；请核对发布来源和 SHA-256。
- 发布页应同时提供 `QwenSubtitle-portable.sha256`（EXE）与 `QwenSubtitle-portable-zip.sha256`（ZIP）。用户可分别对照下载的 ZIP 和解压后的 EXE。
- 目录版内含 Python 运行时、PySide6、Qt 插件和 FFmpeg；不要只转发 EXE 而丢掉 `_internal`，也不要把未经审查的第三方文件替换进发布包。
- 公开仓库不提交 `dist/`、`build/` 或二进制；通过 GitHub Releases 分发。
- 正式项目如有条件，应使用项目自有的 Windows 代码签名证书，并在发布前对便携包做一次干净机器启动测试。

## 依赖与供应链

- 依赖数量刻意保持很少：PySide6、requests、imageio-ffmpeg。
- 不使用来源不明的二进制；FFmpeg 由 `imageio-ffmpeg` 提供，或由用户手动指定。
- 发布构建前建议锁定依赖版本并审查 `pip` 输出。
- 不在 CI 中注入真实 API Key。

## 日志

- 日志位于 `%LOCALAPPDATA%\QwenSubtitle\app.log`，轮转保留少量文件。
- 日志只记录启动/退出与通用错误，不记录 Key、字幕文本、媒体文件名或完整路径。
- 用户可在关闭应用后自行删除该文件。
