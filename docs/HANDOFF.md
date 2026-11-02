# 对话交接

> 每个对话结束前更新本文件。新对话先读 `AGENTS.md`、`docs/PRODUCT_SPEC.md`、本文件，再读相关代码。

## 当前版本

`0.1.0` — 可运行 MVP，2026-11-02。

## 本次对话完成

- 从空仓库搭出完整 Python + PySide6 桌面工程。
- Apple 风格浅色界面：无边框窗口、右侧 Windows 风格窗口按钮、标题栏左侧三语下拉、侧栏、卡片、分段控件、拖拽区、缩略图、进度步骤、完成弹窗。
- 视频导入、FFmpeg 探测/提取/缩略图；无音轨校验。
- 最新 `qwen-audio-3.1-asr-flash-filetrans` 为默认，另有 3.0 与 Qwen3-ASR 可选。
- Qwen-MT Plus / Flash 可选（当前官方 Qwen3 系列；旧 Turbo 已移除；Lite 因免费额度账户报 `AllocationQuota.FreeTierOnly` 暂不提供）。
- 大陆版 / 国际版独立 Key。
- 三种内容模式：仅原文 / 仅译文 / 原文+译文（两个独立文件）；仅原文完全不调用翻译。双语输出 `*.original.*` 与 `*.<目标语言>.*`，不再合并为一个文件。
- SRT / ASS / VTT；同目录输出、重名 `(2)`、UTF-8 BOM、原子写入。
- 两阶段进度（ASR → 翻译 → 写出），取消，完成后弹窗 + 打开文件夹/打开字幕。
- 三语 UI（简中/英/日），默认简中，即时切换；所有选择持久化。
- Windows DPAPI 密钥存储；设置 JSON 无 Key；日志不记录敏感信息。
- 公开仓库安全检查脚本。
- 39 项自动化测试通过（字幕、配置、DPAPI、API 解析、流水线、i18n、UI 冒烟）。
- 增加 PyInstaller 便携目录版构建：内置 Python/PySide6/FFmpeg，构建后自动 `--self-test`；发布工作流在 `v*` tag 时构建并附加 SHA-256。
- 已产出 `dist/portable/QwenSubtitle/QwenSubtitle.exe`（4,871,979 bytes）、`dist/QwenSubtitle-portable-0.1.0-win64.zip`（80,486,728 bytes）；SHA-256 见 `dist/*.sha256`。
- 解决普通用户无管理员权限时的 `Could not create temporary directory!`：不再默认使用 `--onefile` 自解压，改为目录版；应用缓存也从 `%TEMP%` 迁到 `%LOCALAPPDATA%\QwenSubtitle\cache`，AppData 不可写时回退到 EXE 同级 `portable-data`。
- 写出字幕失败时自动回退到桌面/文档/用户目录/应用缓存，并在完成弹窗中显示实际路径。
- 最终 ZIP 解压后，清空 `PYTHONPATH`、`TEMP`、`TMP` 并运行自检：exit 0；原生 Windows 平台自检也 exit 0。
- EXE 字符串扫描未发现用户名/个人路径/测试 Key。
- 文档强调普通用户无需 Python/FFmpeg；源码运行仅作为开发方式。
- 文档：README、AGENTS、产品规格、架构、API 备注、UI 设计、测试、路线图、安全、隐私、贡献、变更记录。

## 验证状态

| 项目 | 状态 |
| --- | --- |
| `python -m pytest` | ✅ 39 passed（含输出目录回退） |
| `python scripts/check_public_repo.py` | ✅ clean |
| 离屏启动/三语切换 | ✅ |
| 视频探测 + 音频提取 + 缩略图 | ✅ 用 4 秒本地合成视频验证 |
| 双语模式两个独立文件 | ✅ 自动化测试通过 |
| DPAPI 往返 + 明文检查 | ✅ |
| 真实大陆版 API 端到端 | ⏳ 未验证（需用户本人在本机输入 Key） |
| 真实国际版 API | ⏳ 未验证 |
| 1 小时以上长视频 | ⏳ 未验证 |
| 便携目录版构建 | ✅ `dist/portable/QwenSubtitle/QwenSubtitle.exe` |
| 打包 `--self-test`（offscreen + native，无自定义 TEMP） | ✅ exit 0，内置 FFmpeg 与 AppData/便携缓存可用 |
| 最终 ZIP 解压后自检（无 PYTHONPATH/TEMP） | ✅ exit 0 |
| EXE 内个人路径/Key 扫描 | ✅ 未发现 |
| 干净 Windows 机器双击 | ⏳ 未验证（需另一台无 Python/FFmpeg 的机器） |

## 已知限制 / 风险

1. **真实 API 未联调**：上传 policy、3.1 结果信封、Qwen-MT 批次格式都按官方文档实现并有 mock 测试，但未用真实 Key 跑通。下一对话优先处理。
2. 仅使用官方默认域名，不支持企业业务空间专属域名。
3. 无字幕预览/编辑；生成后只能打开文件。
4. 无边框窗口的 Windows Snap Layout、边缘缩放、深色模式未完成。
5. 关闭应用时若 HTTP 阻塞，最多等 4 秒后终止线程；正常流程不受影响。
6. 翻译批次用空行分隔，依赖 Qwen-MT 格式保持；已做数量不匹配时逐条回退。
7. DeepSeek Harness 环境中 `.venv` 的 `ensurepip` 可能被文件权限阻挡，测试使用 `.deps` + `PYTHONPATH`；这只是开发环境问题，不影响用户安装。
8. 单文件 `--onefile` 仍会依赖 `%TEMP%` 自解压；在 TEMP ACL 异常或受管 Windows 配置下，普通用户会报 `Could not create temporary directory!`。默认分发改为目录版，不再使用单文件。
9. 应用音频/缩略图缓存已迁移到 `%LOCALAPPDATA%\QwenSubtitle\cache`，不依赖系统 TEMP；自检会验证该目录可写。若 AppData 对当前进程不可写，会回退到 EXE 同级 `portable-data`。

## 下一对话建议

**首选：把便携 ZIP 解压到一台没有 Python/FFmpeg 的干净 Windows 电脑上做真实 API 联调。** 这一步同时验证“零环境双击”和真实千问链路；需要用户自己在本机设置页输入 Key，助手只观察脱敏后的错误/结构，不读取或记录 Key。

备选：

- 代码签名与安装包（消除 SmartScreen 未知发布者）。
- 自定义 Workspace/Endpoint。
- 深色模式。
- 字幕预览与轻量编辑。

## 下一对话提示词（首选方案）

> 项目根目录：`D:\video_subtitles`，版本 `0.1.0`。
>
> 请先阅读 `AGENTS.md`、`docs/PRODUCT_SPEC.md`、`docs/HANDOFF.md`、`docs/API_NOTES.md`，再开始。
>
> 本次目标：把已构建的便携 ZIP 解压到一台**没有 Python、没有 FFmpeg** 的干净 Windows 机器上，验证零环境双击启动；然后在该机器上，由用户自行在设置页输入 Key，完成千问 ASR + Qwen-MT 的真实 API 联调与兼容性修复。助手不得读取、记录或写入 Key。
>
> 必做：
> 1. 解压 ZIP，双击 `QwenSubtitle\QwenSubtitle.exe`；确认主窗口、中文默认界面、设置页 FFmpeg 状态正常。
> 2. 用大陆版 `qwen-audio-3.1-asr-flash-filetrans` + `qwen-mt-plus`，对一个 10–30 秒测试视频跑通：选择视频 → 仅译文 → SRT → 完成弹窗 → 打开文件夹。
> 3. 检查上传 policy、`oss://` 提交、轮询、结果下载、句子时间戳、翻译批次映射。
> 4. 验证「仅原文」不产生任何 Qwen-MT 请求。
> 5. 验证「原文+译文」生成两个独立文件（`*.original.*` 与 `*.<目标语言>.*`）、ASS 可播放、重名不覆盖。
> 6. 如真实返回与代码假设不同，修正解析并补测试；不要静默降级模型。
> 7. 不在代码、日志、文档、测试、截图中写入 Key、真实视频/字幕、个人路径或邮箱。
>
> 不做：深色模式、字幕编辑器、自定义域名、批量队列（除非联调必须）。
>
> 验收：
> - 干净机器无需 Python/FFmpeg 可双击启动。
> - 真实端到端成功一次，输出文件可播放。
> - 仅原文模式确认无翻译请求。
> - 失败场景（错误 Key/无权限/断网）有可操作提示。
> - `python -m pytest` 通过。
> - `python scripts/check_public_repo.py` 输出 clean。
> - 如重新分发，构建 `dist\portable\QwenSubtitle\QwenSubtitle.exe` 并通过 `--self-test`；不要把 EXE/ZIP 提交进 Git。
> - 更新 `docs/HANDOFF.md`、`CHANGELOG.md`、`docs/ROADMAP.md`。
>
> 结束时继续执行 `AGENTS.md` 的“每次对话结束的强制交接流程”：对齐目标、更新文档、运行验证、询问下一对话方向、给出下一段提示词。

## Release

- 版本：`v0.1.0`
- Release notes：`docs/RELEASE_NOTES_v0.1.0.md`
- 分发资产：`QwenSubtitle-portable-0.1.0-win64.zip` + 两个 SHA-256 文件
- 提交与 tag 由本地完成；不 push，不包含真实 Key。

## 交接检查清单

- [ ] 用户可运行 `python run.py` 看到最新界面。
- [ ] 39 项测试仍通过。
- [ ] 公开仓库扫描 clean。
- [ ] 新增文案三语齐全。
- [ ] 无真实 Key、个人路径、真实媒体进入仓库。
- [ ] 本文件、README、CHANGELOG、ROADMAP 与代码一致。
