# Qwen Subtitle v0.1.0 · 千问字幕首个可用版

把视频变成字幕的 Windows 便携桌面工具。默认千问 ASR + Qwen-MT，支持 SRT / ASS / VTT、三语界面、两个独立字幕文件的双语输出。

## Highlights

- **无需 Python / FFmpeg / 管理员权限**：下载便携 ZIP，解压后双击 `QwenSubtitle\QwenSubtitle.exe`。
- **最新 ASR 默认**：`qwen-audio-3.1-asr-flash-filetrans`，可切换 Qwen-Audio 3.0、Qwen3-ASR。
- **翻译模型**：Qwen-MT Plus（旗舰，默认）与 Flash（轻量，免费额度可用）。
- **双语两个文件**：`*.original.*` 与 `*.<目标语言>.*`，不再合并成一个文件。
- **字幕格式**：SRT / ASS / VTT，UTF-8 BOM，重名不覆盖。
- **Apple 风格界面**：右侧 Windows 风格窗口按钮，标题栏最左侧常驻中文/English/日本語下拉。
- **进度与完成反馈**：语音识别 → 翻译 → 写出；完成后弹窗，打开文件夹。
- **本机密钥**：Windows DPAPI；不写入日志、设置 JSON、源码或公开仓库。
- **无遥测**：不收集使用数据。
- **自动回退**：输出目录不可写时，自动保存到桌面/文档/用户目录/应用缓存，并显示实际路径。

## 为什么移除 Qwen-MT Lite

`qwen-mt-lite` 官方存在，但仅免费额度账户会返回：

```text
AllocationQuota.FreeTierOnly
```

这不是 API Key 损坏，而是当前账户的免费额度不覆盖该模型。应用只保留 Plus / Flash；遇到该错误会提示改用 Flash 或开通付费额度。

## Downloads

- `QwenSubtitle-portable-0.1.0-win64.zip` — 80,486,728 bytes
- `QwenSubtitle-portable.sha256` — 解压后 `QwenSubtitle.exe` 的 SHA-256
- `QwenSubtitle-portable-zip.sha256` — ZIP 的 SHA-256

```text
ZIP: f2e5b3dffb193e1e492fefdbc8770706ce1b1a0693f8ae32cf780c11929166ea
EXE: aafa0b1264025da088273d6a526ea033ecc0f95628ad3800749aa29784deebf0
```

## Install

1. 解压 ZIP 到可写目录（桌面、`D:\Apps` 等）。
2. 保持 `_internal` 文件夹与 `QwenSubtitle.exe` 同目录。
3. 双击 `QwenSubtitle.exe`。
4. 设置 → 选择大陆版/国际版 → 由你本人输入 API Key → 保存。
5. 回工作台选择视频、语言、内容模式、模型与格式 → 开始生成字幕。

> 不需要管理员权限；不要从 ZIP 内直接运行，也不要只复制 EXE。

## Verification

- 39 automated tests passed.
- Public repository scan clean.
- Final ZIP extracted; `TEMP`、`TMP`、`PYTHONPATH` unset; `--self-test` exit 0.
- Native Windows `--self-test` exit 0.
- Built-in FFmpeg detected.
- No test keys, personal paths, or usernames in the portable folder.

## Known limitations

- EXE is unsigned; SmartScreen may warn about an unknown publisher. Verify SHA-256.
- Live Alibaba Cloud API integration has not been validated with a real key in this repository.
- Windows 10/11 x64 only.
- No dark mode, subtitle editor, batch queue, or custom workspace domain yet.
- Only the default DashScope endpoints are supported.

## License

MIT. Independent project; not an official Alibaba Cloud product.
