# 测试与验收

## 1. 自动化测试

```powershell
python -m pytest
```

当前 39 项测试：

| 文件 | 覆盖 |
| --- | --- |
| `tests/test_subtitle.py` | 时间戳修复、断句、换行、SRT/ASS/VTT、双语/原文/译文、UTF-8 BOM、嵌套结果 |
| `tests/test_config.py` | 默认值、持久化、非法值归一化、旧版 `target_language=none` 迁移、损坏 JSON |
| `tests/test_secrets.py` | DPAPI 往返、明文不落盘、空/多行/未知地区拒绝、两个地区独立 |
| `tests/test_dashscope.py` | 两种 result 信封、上传 policy、multipart 字段、外域 host 拒绝、错误不含 Key、翻译参数 |
| `tests/test_pipeline.py` | 输出命名、重名、翻译批次对齐/回退、仅原文不调用翻译、双语两个独立文件、输出目录不可写时自动回退 |
| `tests/test_i18n.py` | 三语 key 集合一致、切换、占位符、未知 key |
| `tests/test_ui_smoke.py` | 离屏启动、三页切换、语言即时切换、仅原文禁用翻译控件 |

### 无真实 API Key

所有 API 测试使用 mock/fake session，**不需要也不接受真实 Key**。网络上没有真实调用；CI 不配置 Key。

### 当前环境的额外设置

如果依赖安装在 `.deps` 而不是虚拟环境：

```powershell
$env:TEMP = "D:\video_subtitles\.tmp"
$env:TMP = "D:\video_subtitles\.tmp"
$env:PYTHONPATH = "D:\video_subtitles\.deps;D:\video_subtitles\src"
$env:QT_QPA_PLATFORM = "offscreen"
$env:QT_QPA_FONTDIR = "C:\Windows\Fonts"
python -m pytest
```

`QT_QPA_FONTDIR` 只影响离屏截图/测试；正常桌面运行使用系统字体。

### 打包自检

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build.ps1
```

构建成功后会自动执行：

```powershell
dist\portable\QwenSubtitle\QwenSubtitle.exe --self-test
```

它会在离屏 Qt 平台创建完整主窗口、检查内置 FFmpeg、在 `%LOCALAPPDATA%\QwenSubtitle\cache` 创建并删除工作目录，并以退出码 0 表示通过。没有这个自检，不能声称 EXE 可用。最终仍应在一台**没有 Python、没有 FFmpeg** 的干净 Windows 机器上解压 ZIP 后双击验证一次。

2026-11-02 本机构建记录：

| 项目 | 结果 |
| --- | --- |
| `dist/portable/QwenSubtitle/QwenSubtitle.exe` | 4,871,979 bytes（运行时在 `_internal`） |
| `dist/QwenSubtitle-portable-0.1.0-win64.zip` | 80,486,728 bytes |
| 离屏 `--self-test`（无 TEMP 覆盖） | exit 0 |
| 原生 Windows `--self-test` | exit 0 |
| 从最终 ZIP 解压后自检（无 PYTHONPATH/TEMP） | exit 0 |
| 内置 FFmpeg | 可解析（source=runtime） |
| AppData/便携缓存可写 | exit 0 |
| 输出目录不可写自动回退 | 自动化测试通过 |
| 干净机器双击 | 尚未验证 |

### 公开仓库扫描

```powershell
python scripts/check_public_repo.py
```

必须输出 `public-repo scan: clean`。它扫描文本文件中的：

- `sk-…` 形式的 API Key
- Bearer token
- 私钥头
- `C:\Users\<name>` / `/Users/<name>` / `/home/<name>`
- 邮箱
- `DASHSCOPE_API_KEY=sk-…`
- 明显假的 `sk-test…` / `sk-fake…` 会被放行

这不是完整的秘密扫描器，提交前仍需人工检查截图、二进制和 Git 历史。

## 2. 手动验收清单

准备一个 10–30 秒、有清晰人声的测试视频（不要使用真实客户素材）。以下项目使用真实 Key 时由用户本人在设置中输入，不写入任何文件。

### 2.0 无环境启动

- [ ] 在一台没有 Python、没有 FFmpeg 的 Windows 10/11 64 位电脑上，解压 `QwenSubtitle-portable-*.zip` 后双击 `QwenSubtitle\QwenSubtitle.exe`。
- [ ] 不弹出 `Could not create temporary directory!`；不要求管理员权限；主窗口正常出现。
- [ ] 设置页显示 FFmpeg 已找到（来源为应用内置或 Python 运行时）。
- [ ] 关闭应用后再次双击仍能启动。
- [ ] 若 SmartScreen 提示未知发布者，确认发布来源与校验值后再运行。

### 2.1 启动与界面

- [ ] 双击/运行应用，窗口圆角、阴影、侧栏正常。
- [ ] 默认中文；标题“把视频，变成好字幕。”完整显示。
- [ ] 设置页可切换 English / 日本語，立即生效；重启后保持。
- [ ] 1024×700 以下内容可滚动，右上角主操作仍可见。
- [ ] 关闭窗口不会留下后台进程。

### 2.2 导入视频

- [ ] 点击「选择视频」能打开文件对话框。
- [ ] 拖入 MP4 能识别；拖入不支持的文件有明确提示。
- [ ] 文件卡片显示缩略图、文件名、容器、时长、分辨率、大小。
- [ ] 无音轨视频提示“没有音轨”，不进入运行。
- [ ] 删除视频后回到空状态，主按钮禁用。

### 2.3 API Key 与地区

- [ ] 未保存 Key 时，选中视频后右上角出现“需要 API Key”。
- [ ] 点击“开始生成字幕”弹出错误，点“去设置”跳到设置页。
- [ ] 设置页保存 Key 后显示“已保存（本机加密）”。
- [ ] 关闭并重启，Key 仍在，且设置 JSON 中没有 Key 明文。
- [ ] `secrets.bin` 不含 Key 明文。
- [ ] 删除 Key 有确认弹窗，删除后无法运行。
- [ ] 切换大陆版/国际版，Key 状态分别显示，互不串用。
- [ ] “测试连接”在有效 Key 下提示正常；无效 Key 有可读错误。

### 2.4 模型与语言选择

- [ ] 默认 ASR 为 Qwen-Audio 3.1 ASR。
- [ ] 可切换 3.0、Qwen3；界面说明同步变化。
- [ ] 翻译模型可选 Plus / Flash。
- [ ] 识别语言可选自动识别/中文/粤语/英语/日语等。
- [ ] 目标语言可选简中/繁中/英语/日语等。
- [ ] 选择后关闭应用重开，所有选择保持。
- [ ] 源语言=目标语言且需要翻译时，运行前阻止并提示。

### 2.5 内容模式与格式

- [ ] 「仅译文」只输出译文。
- [ ] 「原文 + 译文」生成两个独立文件：`*.original.*` 与 `*.<目标语言>.*`，内容分别为原文和译文。
- [ ] 「仅原文」禁用目标语言和翻译模型，并显示“不消耗翻译 token”。
- [ ] 抓包/日志确认「仅原文」没有任何 Qwen-MT 请求。
- [ ] SRT / ASS / VTT 均可生成；扩展名正确。
- [ ] ASS 在 VLC/PotPlayer 中可播放，中文不乱码。
- [ ] 同名文件存在时生成 `(2)`，不覆盖。

### 2.6 进度与完成

- [ ] 点击开始后进度卡自动出现并滚动到可见位置。
- [ ] ASR 阶段显示提取/上传/云端的可读状态。
- [ ] 翻译阶段显示批次进度。
- [ ] 仅原文时翻译步骤显示“已跳过”。
- [ ] 写出阶段完成到 100%。
- [ ] 完成弹窗出现，显示条数和路径。
- [ ] 点击「打开文件夹」能在资源管理器中选中字幕文件。
- [ ] 关闭弹窗后工作台保留结果和打开按钮。
- [ ] 点击「再生成一个」回到空闲，视频仍保留。

### 2.7 取消与异常

- [ ] 运行中点取消，按钮变为“正在取消…”，最终回到空闲。
- [ ] 取消后没有残留字幕文件。
- [ ] 断网运行，提示网络错误，不崩溃。
- [ ] 无效 Key，提示去设置，不显示 Key。
- [ ] 额度不足/模型无权限，提示检查控制台。
- [ ] 输出目录不可写时，自动改存到桌面/文档/用户目录/应用缓存，并提示实际路径。
- [ ] 关闭应用时若任务运行，出现确认；确认后退出，进程不残留。

### 2.8 隐私

- [ ] 任务管理器/网络抓包确认原视频没有上传；只有音频请求。
- [ ] 日志中没有 Key、字幕文本、完整视频路径。
- [ ] 仓库扫描 clean。
- [ ] 截图中没有真实 Key、真实人名、真实视频内容、个人路径。

## 3. 真实验证记录（待补）

| 日期 | 地区 | ASR 模型 | 翻译模型 | 视频时长 | 结果 | 备注 |
| --- | --- | --- | --- | --- | --- | --- |
| 待用户验证 |  |  |  |  |  | 不记录 Key |

## 4. CI

`.github/workflows/ci.yml` 在 Windows 上运行：

```powershell
python -m pip install -e ".[dev]"
python -m pytest
python scripts/check_public_repo.py
```

CI 不注入任何 Key。DPAPI 测试只在 Windows 运行；其他平台自动 skip。
