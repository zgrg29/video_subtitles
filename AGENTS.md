# AGENTS.md

本文件面向所有后续参与本项目的 AI 助手与开发者。它是工程约束，不是营销文档。开始工作前先读本文件，再读 `docs/PRODUCT_SPEC.md`、`docs/HANDOFF.md` 和当前相关代码。

## 项目使命

做一个**跑在 Windows 桌面上的小型字幕工具**：用户选择视频，使用千问 ASR 识别语音，使用 Qwen-MT 翻译字幕，最后输出 SRT / ASS / VTT。界面要有 Apple 式的克制、留白和圆角卡片质感，而不是通用后台管理界面。

产品名：**千问字幕 / Qwen Subtitle**。版本：`0.1.0`。

## 不可违背的产品约束

1. **默认使用最新 ASR**：默认模型必须是 `qwen-audio-3.1-asr-flash-filetrans`。用户可以在界面选择其他 ASR 模型，但应用不能静默把用户的选择换回默认。
2. **模型可选且持久化**：ASR 模型、翻译模型、地区、识别语言、目标语言、内容模式、字幕格式、界面语言都必须在修改后立即保存，下次启动恢复。
3. **三种字幕内容模式**：
   - `translated`：只输出译文。
   - `bilingual`：分别生成两个独立的字幕文件——一个原文、一个译文，时间轴一致；不要合并成一个文件。
   - `original`：只输出原文，**必须完全跳过 Qwen-MT 请求**，不能消耗翻译 token。
4. **最新优先，不暗降级**：如果用户选择的模型在当前地区不可用，应明确报错并允许换模型，不要偷偷改用旧模型。
5. **两个地区**：默认大陆版（`https://dashscope.aliyuncs.com`）；可切换国际版（`https://dashscope-intl.aliyuncs.com`）。两边的 API Key 不通用。
6. **密钥安全**：API Key 由用户在设置页输入，使用 Windows DPAPI 加密存到用户目录。禁止把 Key 写入源码、测试、文档、截图、日志、环境变量文件、命令行参数或本地设置 JSON。
7. **公开仓库**：本仓库是公开的。禁止加入真实姓名、个人邮箱、个人主页、住址、手机号、`C:\Users\<真实用户名>` 路径、真实视频/字幕内容、客户资料、访问令牌。提交前必须运行 `python scripts/check_public_repo.py`。
8. **原视频不出本机**：只上传 FFmpeg 提取出的音频。不要上传原始视频。
9. **三语 UI**：简体中文（默认）、English、日本語。所有界面文案、模型说明、进度、错误与弹窗必须走 `src/qwen_subtitle/i18n.py`，不要散落硬编码中文。
10. **完成反馈**：任务成功后必须显示完成弹窗，并提供「打开文件夹」按钮；同时保留工作台内的结果路径。
11. **无遥测**：不加入分析 SDK、广告、账号系统、自动更新上报或任何使用数据收集。
12. **普通用户零环境**：发布给别人的 Windows 版本必须是**自包含便携包**，内含 `QwenSubtitle.exe`、Python/PySide6 运行时、应用资源和 FFmpeg。优先目录版（`QwenSubtitle\QwenSubtitle.exe`），因为它不依赖系统 `%TEMP%` 自解压；单文件版只能作为可选，不得作为唯一分发形式。不能要求最终用户安装 Python、pip 或配置环境变量。`python run.py` 仅用于开发。
13. **视觉语言**：Apple 风格指大留白、圆角卡片、系统字体、克制的蓝色强调、分段控件、轻阴影和清晰层级；不要复制 Apple 商标、图标、SF Pro 字体文件或系统界面。窗口按钮必须遵循 Windows 习惯放在右上角；标题栏最左侧必须常驻三语下拉，方便看不懂当前语言的用户切换。

## 技术栈

- Python 3.11+
- PySide6（Qt Widgets）
- requests（直接调用 DashScope HTTP API）
- imageio-ffmpeg（FFmpeg 兜底二进制）
- pytest
- PyInstaller（打包，见 `scripts/build.ps1`）

不引入 Electron、Node、数据库或 Web 服务。当前架构刻意保持小而可审计。

## 目录与职责

```text
src/qwen_subtitle/
├─ app.py               启动、日志、主题、Windows AppUserModelID
├─ constants.py         模型目录、语言目录、地区、格式、默认值
├─ i18n.py              三语文案与运行时语言
├─ core/
│  ├─ config.py         非敏感设置；原子写入；非法值归一化
│  ├─ secrets.py        DPAPI；一个地区一个 Key
│  ├─ dashscope.py      临时上传、提交/轮询 ASR、下载 JSON、Qwen-MT
│  ├─ ffmpeg.py         探测、提取 16 kHz 单声道音频、缩略图
│  ├─ subtitle.py       Cue、断句、换行、SRT/ASS/VTT
│  ├─ pipeline.py       ASR → 可选翻译 → 写出
│  └─ errors.py         可安全展示给用户的错误
└─ ui/
   ├─ state.py          AppState：设置持久化 + 语言 + 密钥门面
   ├─ main_window.py    无边框窗口、标题栏、侧栏、页面切换
   ├─ theme.py          设计 token 与 QSS
   ├─ icons.py          内联 SVG 图标
   ├─ widgets.py        卡片、分段控件、拖拽区、步骤、Spinner
   ├─ dialogs.py        完成 / 错误 / 确认弹窗
   └─ pages/            工作台、设置、关于
```

## 关键数据流

```text
选择视频
  → ffmpeg -i 探测时长/分辨率/音轨
  → 提取 16 kHz 单声道 MP3（临时目录）
  → 获取该模型的临时上传凭证
  → 上传音频，得到 oss:// URL
  → 提交 filetrans 异步任务
  → 轮询 task
  → 下载 transcription JSON
  → sentences → Cue（毫秒时间戳）
  → （仅译文/双语时）Qwen-MT 批量翻译
  → 断句/换行
  → 原子写出 SRT / ASS / VTT
  → 完成弹窗 + 打开文件夹
```

`original` 模式在第 9 步后直接进入写出阶段；任何 Qwen-MT 调用都是 bug。

## 外部 API 不变量

- ASR 文件转写提交：`POST /api/v1/services/audio/asr/transcription`，`X-DashScope-Async: enable`。
- 临时 `oss://` 文件：请求头 `X-DashScope-OssResourceResolve: enable`。
- 上传凭证：`GET /api/v1/uploads?action=getPolicy&model=<model>`，上传到返回的 `.aliyuncs.com` host。
- 查询：`GET /api/v1/tasks/{task_id}`。
- Qwen-MT：`POST /compatible-mode/v1/chat/completions`，`translation_options` 使用语言英文名（如 `Simplified Chinese`），不是 `zh-Hans`。
- 模型不同，提交字段不同：
  - `qwen-audio-3.1/3.0-...-filetrans` → `input.file_urls: [url]`，语言参数 `language_hints: [code]`。
  - `qwen3-asr-flash-filetrans` → `input.file_url: url`，语言参数 `language: code`，结果路径 `output.result.transcription_url`。
- 不要假设某个模型返回结构永远不变；解析必须容忍 `result` / `results` 两种信封。
- 截图/测试/文档中的 Key 只能使用明显假的 `sk-test…`，且不得被真实调用。

详细接口和参考链接见 `docs/API_NOTES.md`。

## 本地数据

- 设置：`%LOCALAPPDATA%\QwenSubtitle\settings.json`（无密钥）。
- 密钥：`%LOCALAPPDATA%\QwenSubtitle\secrets.bin`（DPAPI 加密）。
- 日志：`%LOCALAPPDATA%\QwenSubtitle\app.log`（轮转；不记录 Key、媒体内容或完整路径）。
- 临时音频/缩略图：`%LOCALAPPDATA%\QwenSubtitle\cache`，任务结束或应用退出时清理；不依赖系统 `%TEMP%`。
- 如果 AppData 对当前进程不可写，数据目录回退到 EXE 同级的 `portable-data`。这是受限 Windows 配置下避免管理员权限的第二道保险。

这些路径永远不能提交到仓库。

## 常用命令

```powershell
# 安装
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"

# 运行
python run.py

# 测试
python -m pytest

# 公开仓库安全检查
python scripts/check_public_repo.py

# 构建无需 Python/临时目录权限的便携目录版
powershell -ExecutionPolicy Bypass -File scripts/build.ps1

# 离屏 UI 冒烟（可选）
$env:QT_QPA_PLATFORM = "offscreen"
python -m pytest tests/test_ui_smoke.py
```

当前 DSH 环境中 `.venv` 可能因 `ensurepip` 权限失败；可改用：

```powershell
python -m pip install --target .deps PySide6 requests pytest imageio-ffmpeg
$env:PYTHONPATH = "D:\video_subtitles\.deps;D:\video_subtitles\src"
```

`.deps` 已在 `.gitignore` 中。

## 代码规范

- 公开函数和核心模块写简短 docstring；不要写长篇注释解释显而易见的代码。
- 核心层不导入 Qt；UI 层可以导入核心层。
- 任何异常消息都可能展示给用户，不能包含 Key 或完整本地路径。
- UI 文案不硬编码；新增文案必须同时补齐 `zh`、`en`、`ja`，否则 `tests/test_i18n.py` 会失败。
- 设置写入使用 `ConfigStore.save` 的原子写入；密钥使用 `SecretStore`。
- 新增模型必须同时更新 `constants.py`、模型详情文案、`i18n.py` 和测试。
- 不要为了“兼容”默认回退到旧 ASR；只能让用户显式选择。
- 不要使用真实视频、真实字幕或真实 Key 做测试；使用临时文件、`sk-test…` 和 mock。

## 完成定义（DoD）

一个改动只有在下列条件都满足时才算完成：

- [ ] 符合 `docs/PRODUCT_SPEC.md` 的验收标准。
- [ ] 选择项能在重启后恢复（如涉及设置）。
- [ ] `original` 模式没有 Qwen-MT 网络请求。
- [ ] 三语文案齐全，UI 无明显截断。
- [ ] `python -m pytest` 通过。
- [ ] `python scripts/check_public_repo.py` 输出 clean。
- [ ] 文档、README、CHANGELOG、HANDOFF、RELEASE_NOTES 与实际行为一致。
- [ ] 没有提交 `.deps/`、`.venv/`、`.tmp/`、真实媒体、密钥或本地路径。
- [ ] 视觉改动至少通过离屏截图或实机截图检查。
- [ ] 涉及分发的改动必须构建 `dist\portable\QwenSubtitle\QwenSubtitle.exe`，并通过 `--self-test`（Qt 离屏 + 内置 FFmpeg）。
- [ ] 应用自己的音频/缩略图缓存必须位于 `%LOCALAPPDATA%\QwenSubtitle\cache`，不能依赖系统 `%TEMP%`。
- [ ] 不把 `dist\*.exe`、`dist\*.zip`、`build\` 提交进 Git；通过 GitHub Releases 分发。

## 每次对话结束的强制交接流程

用户要求：**每一次对话结束前，必须对齐工程文件、工程文档与最初目标，然后询问下一对话要做什么，并在得到方向后给出下一对话的提示词。**

按以下顺序执行：

1. **对齐**：重新阅读 `docs/PRODUCT_SPEC.md` 的目标与验收标准、`docs/ROADMAP.md`、`docs/HANDOFF.md`；逐项核对本次改动，列出“已完成 / 未完成 / 偏差”。
2. **修正文档**：更新 `README.md`（如用户可见行为变化）、`docs/HANDOFF.md`、`docs/ROADMAP.md`、`CHANGELOG.md`；如涉及架构决策，更新 `docs/ARCHITECTURE.md` 或 `docs/DECISIONS.md`。
3. **验证**：运行测试和公开仓库扫描；不要在没有运行的情况下声称通过。
4. **询问下一步**：向用户提出 2–3 个具体的下一步选项（推荐项放第一），并允许用户自由描述。
5. **给出下一对话提示词**：根据用户选择，输出一段可直接复制的新对话提示词，必须包含：
   - 项目根目录与当前版本；
   - 本次已完成的内容；
   - 下一对话的目标与不做什么；
   - 必读文件（`AGENTS.md`、`docs/PRODUCT_SPEC.md`、`docs/HANDOFF.md`，以及相关模块）；
   - 验收标准与必跑命令；
   - “结束时继续执行本文件的交接流程”。
6. **不得**要求用户粘贴真实 API Key；不得把 Key 写进提示词。

## 当前状态（以 docs/HANDOFF.md 为准）

v0.1.0 已完成可运行 MVP：三语 Apple 风格界面、视频导入、最新 ASR 默认与模型选择、三内容模式、Qwen-MT、SRT/ASS/VTT、两阶段进度、完成弹窗、DPAPI 密钥、设置持久化、39 项自动化测试，并提供内置 Python/PySide6/FFmpeg 的便携目录版构建。因为部分 Windows 配置文件禁止普通用户写入 `%TEMP%`，单文件自解压版不作为默认分发；缓存已迁移到 `%LOCALAPPDATA%\QwenSubtitle\cache`。尚未用真实 Key 做线上联调；首次真实调用需要用户自行在设置中输入 Key。
