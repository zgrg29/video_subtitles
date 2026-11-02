# 架构决策记录（ADR）

## ADR-001：Python + PySide6，而非 Electron

**日期**：2026-11-02  
**状态**：接受

**背景**：需要 Windows 桌面小工具、原生文件对话框、打开文件夹、后台任务、DPAPI 和 FFmpeg 调用。

**决策**：使用 Python 3.11+ + PySide6 Widgets。

**理由**：

- 单语言，核心逻辑与 UI 同仓，打包路径简单。
- Qt 原生文件对话框、`QThread`、`QDesktopServices` 直接可用。
- Windows DPAPI 通过 `ctypes` 调用，无需额外服务。
- 体积与依赖显著小于 Electron。
- Qt Widgets 足以通过 QSS + 少量自绘控件实现目标视觉。

**代价**：QSS 不如 CSS 灵活；无边框窗口的 Windows 集成需要额外打磨。

## ADR-002：直接调用 DashScope HTTP，不引入完整 SDK

**日期**：2026-11-02  
**状态**：接受

**决策**：用 `requests` 直接实现临时上传、filetrans、任务轮询、结果下载与 Qwen-MT。

**理由**：

- 只需少量 endpoint，SDK 会带来额外依赖和版本耦合。
- 可以精确控制请求头、超时、重试、脱敏和结果解析。
- 更容易在公开仓库中审计数据流。

**代价**：需要自己跟进 API 变化；已有 `API_NOTES.md` 和兼容解析。

## ADR-003：长音频使用异步 filetrans + 临时上传

**日期**：2026-11-02  
**状态**：接受

**备选**：

- 同步 `qwen3-asr-flash` + base64 分片：需要自己切分/合并时间戳，且同步模型时间戳能力有限。
- 异步 filetrans：原生长音频、句级时间戳、结果 URL。

**决策**：FFmpeg 提取一条 16 kHz 单声道 MP3 → 临时上传 → 异步 filetrans。

**理由**：长视频更稳，时间戳由服务端提供，避免自研 VAD 分片。临时上传文件与模型绑定，48 小时有效，适合一次性任务。

## ADR-004：Windows DPAPI 保存 API Key

**日期**：2026-11-02  
**状态**：接受

**备选**：明文 JSON、`.env`、Windows Credential Manager、keyring、DPAPI。

**决策**：DPAPI 加密整个 JSON 字典，写入 `%LOCALAPPDATA%\QwenSubtitle\secrets.bin`。

**理由**：

- 不增加依赖。
- 绑定当前 Windows 用户，离线拷贝无法直接读取。
- 文件不在仓库，不会误提交。
- 比起 `.env`，不会进入进程环境或命令历史。

**限制**：不能防御同账户下的恶意软件；跨平台需另做 keyring 实现。

## ADR-005：仅原文模式完全跳过 Qwen-MT

**日期**：2026-11-02  
**状态**：接受（用户明确要求）

**决策**：`output_mode=original` 时，pipeline 不进入翻译分支，UI 禁用目标语言/翻译模型，并显示“不消耗翻译 token”。自动化测试断言 `translate_calls == 0`。

**理由**：翻译按 token 计费，用户只想要原文时不应产生任何翻译成本。

## ADR-006：三语 UI 使用纯 Python 字典

**日期**：2026-11-02  
**状态**：接受

**备选**：gettext、Qt Linguist `.ts`、第三方 i18n 库。

**决策**：`i18n.py` 中的 `zh` / `en` / `ja` 字典 + `tr(key, **params)`。

**理由**：

- 文案量可控；无需编译 `.qm` 文件。
- 核心层也能调用，错误和进度消息统一本地化。
- 测试可强制三种语言 key 集合一致。

**代价**：大型项目会难以维护；本项目规模合适。

## ADR-007：翻译批次用空行分隔 + 逐条回退

**日期**：2026-11-02  
**状态**：接受

**决策**：10 条字幕用空行拼接成一次 Qwen-MT 请求；若返回分段数不匹配，逐条重新请求。

**理由**：减少请求次数和延迟；Qwen-MT 对格式保持较好。数量不匹配时优先保证时间轴对齐，而不是错误映射。

**代价**：回退路径会变慢、增加 token；但只在格式异常时触发。

## ADR-008：无边框窗口 + 自绘交通灯

**日期**：2026-11-02  
**状态**：接受

**决策**：Qt FramelessWindowHint + WA_TranslucentBackground + 16px 圆角 shell + 自绘交通灯。

**理由**：更接近目标视觉；避免系统标题栏破坏整体感。

**代价**：Windows Snap Layout、边缘缩放、最大化圆角需要额外处理；当前用右上角最大化按钮 + 右下角 QSizeGrip 兜底。

## ADR-009：公开仓库安全扫描作为提交门禁

**日期**：2026-11-02  
**状态**：接受

**决策**：`scripts/check_public_repo.py` 扫描常见 Key、Bearer、私钥、个人路径、邮箱。

**理由**：用户明确要求公开仓库不能含 Key 或个人信息；自动扫描降低误提交概率。

**限制**：不能覆盖图片、二进制、Git 历史；仍需人工 review。

## ADR-010：普通用户分发使用便携目录版（单文件为可选）

**日期**：2026-11-02  
**状态**：接受（用户明确要求：别人的电脑没有 Python 环境，且普通用户不能依赖管理员/系统 TEMP）

**决策**：默认使用 PyInstaller `--onedir --windowed` 构建 `dist\portable\QwenSubtitle\QwenSubtitle.exe`，整个 `QwenSubtitle` 文件夹压缩为便携 ZIP；内置 Python 运行时、PySide6、应用资源和 FFmpeg。`--onefile` 仅作为可选实验，不作为唯一分发形式。

**理由**：

- 单文件模式每次启动都要把运行时解压到 `%TEMP%`；在 TEMP ACL 异常、受管配置或杀毒策略下，普通用户会看到 `Could not create temporary directory!`，管理员启动反而正常。
- 目录版不写系统临时目录，解压一次后双击 EXE 即可；对普通用户仍是一个便携应用。
- 应用自身的音频/缩略图缓存放在 `%LOCALAPPDATA%\QwenSubtitle\cache`，也不依赖 `%TEMP%`。

**代价**：

- 分发物是 ZIP（内含 EXE + `_internal`），不是单个文件；用户需要先解压。
- 文件夹比单文件大，但启动更快。
- 未签名时 SmartScreen 会提示未知发布者；需提供 SHA-256。
- 不把 EXE/ZIP 提交进 Git，使用 Releases 管理。
