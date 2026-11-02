# 架构设计

## 1. 总览

```text
┌────────────────────────────────────────────────────────────┐
│ PySide6 UI                                                  │
│  MainWindow / Workbench / Settings / About / Dialogs       │
│  AppState (settings persistence, language, key facade)     │
└───────────────┬────────────────────────────────────────────┘
                │ PipelineWorker (QThread)
┌───────────────▼────────────────────────────────────────────┐
│ core                                                        │
│  ffmpeg.py  →  dashscope.py  →  subtitle.py                 │
│                    pipeline.py                              │
│  config.py / secrets.py / errors.py                        │
└───────────────┬────────────────────────────────────────────┘
                │ HTTPS
┌───────────────▼────────────────────────────────────────────┐
│ Alibaba Cloud Model Studio                                  │
│  temporary upload → ASR filetrans → Qwen-MT                │
└────────────────────────────────────────────────────────────┘
```

核心层不导入 Qt；UI 通过 `AppState` 和 `SubtitlePipeline` 使用核心能力。这样字幕格式、配置、API 解析可以独立测试。

## 2. 为什么是 Python + PySide6

| 方案 | 结论 |
| --- | --- |
| Electron + React | 视觉自由，但需要 Node 工具链和 100MB+ Chromium；对小型本地工具过重 |
| Tauri | 体积小，但需要 Rust 工具链，FFmpeg/进程管理复杂度高 |
| Web + 本地服务 | 变成浏览器应用，文件对话框、打开文件夹和密钥保护都更绕 |
| Python + PySide6 | 单语言、原生文件对话框、QThread、Windows DPAPI 直接可用；Qt Widgets 足以做出精致界面 |

代价是 Qt 的样式系统不如 CSS 灵活；本项目用设计 token + QSS + 少量自绘控件控制复杂度。

## 3. 模块职责

### `constants.py`

模型、语言、地区、格式、默认值的唯一事实来源。模型目录同时驱动 UI 下拉框、持久化校验和请求参数。

### `config.py`

- 存储非敏感设置到 `%LOCALAPPDATA%\QwenSubtitle\settings.json`。
- `normalized()` 将所有非法/缺失值收敛到合法默认。
- 原子写入（临时文件 + `os.replace`），避免半写文件。
- 不含 API Key。

### `secrets.py`

- 每个地区一个 Key。
- 使用 `CryptProtectData` / `CryptUnprotectData`（DPAPI），绑定当前 Windows 用户。
- 整个 JSON 字典加密后写入 `secrets.bin`。
- 原子写入。
- 错误消息不包含 Key。

### `dashscope.py`

直接使用 `requests` 调用 DashScope HTTP API，不依赖完整 SDK。

职责：

1. 获取模型绑定的临时上传凭证。
2. 以 multipart 上传音频，返回 `oss://` 地址。
3. 提交异步 filetrans 任务。
4. 轮询到 `SUCCEEDED` / `FAILED`。
5. 下载并解析 transcription JSON。
6. 调用 Qwen-MT OpenAI-compatible endpoint。
7. 对 429/5xx 做有限重试，并遵守 `Retry-After`。
8. 将所有 Key 从异常文本中脱敏。

### `ffmpeg.py`

- 解析 FFmpeg 路径：手动 > 内置 > PATH > imageio-ffmpeg。
- 用 `ffmpeg -i` 解析时长、分辨率、音视频编码。
- 提取 16 kHz 单声道 64 kbps MP3（失败时回退 AAC/M4A）。
- 生成 480px 缩略图（`-update 1`，兼容 FFmpeg 7 的 image2 muxer）。
- Windows 下用 `explorer /select,` 定位输出文件。

### `subtitle.py`

- `Cue(start_ms, end_ms, text, translation)`。
- `cues_from_sentences` 修复缺失/倒置时间戳。
- `normalize_cues` 去空、去越界、处理重叠。
- `split_oversized_cues` 按标点/宽度切分，按字符宽度比例分配时间。
- `wrap_subtitle` 控制每行宽度，最多两行。
- SRT / ASS / VTT 渲染；ASS 转义 `{}`、`\`、换行。
- UTF-8 BOM + 原子写入。

### `pipeline.py`

单次任务的编排：

```text
probe → extract → upload → submit → poll → download → parse
     → split cues
     → [translated/bilingual] translate in batches
     → write:
          original   → one *.original.* file
          translated → one *<target>.* file
          bilingual  → two independent files (*.original.* + *<target>.*)
```

`original` 模式下不进入翻译分支。进度回调只上报 `(stage, overall_percent, message)`，避免把 Qt 依赖带进核心层。

翻译批次策略：

- 每 10 条一次请求，用空行拼接。
- 如果返回的空行分段数与输入一致，按序映射。
- 如果数量不一致，逐条请求以保证时间轴对齐（更慢但正确）。

### `ui/state.py`

`AppState` 是 UI 与设置/密钥之间的门面：

- `settings` 内存快照。
- `update(**changes)` 立即持久化并发出 `settings_changed` / `language_changed`。
- 密钥读写委托给 `SecretStore`。
- 初始化时设置全局 UI 语言。

### UI 层

- `MainWindow`：无边框窗口、macOS 风格交通灯、侧栏、页面栈、关闭时取消任务。
- `WorkbenchPage`：视频卡、字幕设置、运行按钮、进度步骤、完成结果。
- `SettingsPage`：界面语言、地区/Key、FFmpeg、输出目录、隐私。
- `AboutPage`：版本、隐私、技术栈、许可。
- `theme.py`：设计 token 和 QSS。
- `widgets.py`：自绘/组合控件。
- `dialogs.py`：完成、错误、确认弹窗。

## 4. 线程模型

```text
main thread: Qt event loop + UI
worker: QThread(PipelineWorker)
  → SubtitlePipeline.run()
  → progress signal → UI slots
  → success/failed/cancelled signal
```

- UI 不在主线程执行网络/FFmpeg。
- 取消使用 `threading.Event`，在轮询、批次、提取回调中检查。
- 关闭窗口时取消任务；最多等待 4 秒，极端情况下终止 QThread 以避免退出时崩溃。
- 真正的 HTTP 读取中断仍受 `requests` timeout 限制；后续可改为可取消的流式上传/轮询。

## 5. 数据与隐私边界

| 数据 | 位置 | 是否离开本机 |
| --- | --- | --- |
| 原始视频 | 用户文件系统 | 否 |
| 提取音频 | `%LOCALAPPDATA%\QwenSubtitle\cache` | 是，上传到百炼临时存储，48 小时内有效（以官方文档为准） |
| 字幕文本 | 内存 / 输出文件 | 仅译文/双语模式发送给 Qwen-MT |
| API Key | `%LOCALAPPDATA%\QwenSubtitle\secrets.bin`，DPAPI；受限配置回退到 EXE 同级 `portable-data` | 仅作为 HTTPS Authorization 头发送 |
| 设置 | `%LOCALAPPDATA%\QwenSubtitle\settings.json`，同样支持 `portable-data` 回退 | 否 |
| 日志 | `%LOCALAPPDATA%\QwenSubtitle\app.log` | 否；不含 Key/媒体/完整路径 |
| 遥测 | 无 | 否 |

## 6. 错误模型

`AppError` 有 `user_message`，UI 可以直接展示。`ApiError` 额外带 `status_code`、`code`、`retryable`。

错误分层：

- 输入错误（无视频、无 Key、语言冲突）→ 运行前在 UI 拦截。
- 媒体错误（无音轨、FFmpeg 缺失/失败）→ 引导去设置或换文件。
- API 错误（401/403/429/5xx/文件不可读）→ 映射成可操作提示。
- 未知异常 → 只显示通用消息，不把堆栈/路径暴露给用户。

## 7. 本地化

- `i18n.py` 是纯 Python 字典，不依赖 Qt。
- 语言代码：`zh` / `ja` / `en`；默认 `zh`。
- 核心层在构造错误/进度消息时调用 `tr()`；UI 重绘时调用 `tr()`。
- 语言切换后 `MainWindow.retranslate()` 调用各页面 `retranslate()`；下拉框保留当前 `data`，只替换显示文本。
- 测试强制三种语言 key 集合一致。

## 8. 扩展点

- **自定义 endpoint**：在 `Region` 增加 `workspace_base_url`，Settings 增加“高级”输入；`QwenClient` 已接受任意 HTTPS base URL。
- **新 ASR 模型**：在 `constants.py` 增加 `AsrModel`，若 API 形态不同，在 `submit_transcription` 增加 `api_style` 分支。
- **术语表/热词**：Qwen-MT 支持 `terms`/`domains`；在 `PipelineOptions` 增加字段，翻译请求带入。
- **字幕预览/编辑**：将 `Cue` 列表放入模型，增加表格/视频预览页；写出层无需改动。
- **深色模式**：将 `theme.py` 的常量变为 dataclass token，提供 light/dark 两套 QSS；自绘控件读取 token。
- **批量队列**：`Pipeline` 已是独立可调用单元；增加任务队列和串行执行器即可。

## 9. 分发与打包

- 用户分发物是 PyInstaller `--onedir --windowed` 生成的 `QwenSubtitle\QwenSubtitle.exe`，整个文件夹压缩为便携 ZIP。
- 不默认使用 `--onefile`：它每次启动都需要把运行时解压到 `%TEMP%`，在 TEMP 权限异常的普通用户账户上会报 `Could not create temporary directory!`。
- 包内包含：Python 运行时、PySide6、Qt 插件、应用 resources、`imageio-ffmpeg` 的 FFmpeg 二进制。
- 构建后使用 `QwenSubtitle.exe --self-test`：
  - 设置 `QT_QPA_PLATFORM=offscreen`；
  - 创建完整 `QApplication` 与主窗口；
  - 调用 `resolve_ffmpeg()` 验证包内 FFmpeg；
  - 在 `%LOCALAPPDATA%\QwenSubtitle\cache` 创建/删除工作目录，验证不依赖系统 TEMP；
  - 以退出码 0/3/4 表示成功/缺少 FFmpeg/缓存不可写。
- 输出 `dist/portable/QwenSubtitle/QwenSubtitle.exe`、`dist/QwenSubtitle-portable.sha256`、`dist/QwenSubtitle-portable-0.1.0-win64.zip`。
- `.gitignore` 排除 `dist/`、`build/`、`*.spec`；二进制通过 GitHub Releases 分发。
- `run.py` 在开发环境可回退到 `.deps`，但冻结后的 EXE 不依赖 `.deps`。

## 10. 已知技术债

- HTTP 上传/轮询没有真正的流式取消；关闭应用依赖 timeout + 终止兜底。
- 字幕预览缺失，用户只能在生成后打开文件。
- 翻译批次用空行分隔，依赖 Qwen-MT 的格式保持；已实现数量不匹配时逐条回退。
- 没有真实 API 集成测试（出于公开仓库密钥安全）。
- 无边框窗口的 Windows Snap Layout / 系统缩放边缘仍有打磨空间。
- 仅使用官方默认域名，尚未支持业务空间专属域名。
