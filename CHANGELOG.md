# Changelog

All notable changes to this project are documented here.

## [0.1.0] - 2026-11-02

### Added

- Apple-inspired PySide6 desktop interface: frameless window, right-side Windows-style minimise/maximise/close buttons, a leftmost three-language dropdown in the title bar, sidebar, cards, segmented controls, custom progress steps, completion dialog.
- Video import via file dialog or drag and drop; FFmpeg probing, thumbnail extraction, audio-only extraction.
- ASR model selection with latest `qwen-audio-3.1-asr-flash-filetrans` as default; `qwen-audio-3.0-asr-flash-filetrans` and `qwen3-asr-flash-filetrans` as alternatives.
- Qwen-MT Plus / Flash translation models (current Qwen3 lineup; legacy `qwen-mt-turbo` removed; `qwen-mt-lite` omitted because free-tier-only accounts receive `AllocationQuota.FreeTierOnly`).
- Mainland China / international region switch with separate DPAPI-encrypted API keys.
- Three subtitle content modes:
  - original only (skips Qwen-MT entirely),
  - translated only,
  - original + translation as two separate files (`*.original.*` and `*.<target>.*`).
- SRT, ASS, VTT output with UTF-8 BOM, line wrapping, cue splitting, collision-safe filenames.
- End-to-end pipeline with ASR, translation and write stages; cancellation; completion dialog with "Open folder" / "Open subtitle".
- Simplified Chinese, English and Japanese UI, default Chinese, switchable at runtime and persisted.
- Persistent user preferences: region, models, languages, content mode, format, UI language, FFmpeg path, output directory.
- Windows DPAPI secret storage; no plaintext keys in settings, logs, source, or repository.
- Local public-repository scanner for secrets and personal paths.
- 39 automated tests covering subtitles, config, secrets, API parsing, pipeline modes, i18n, and offscreen UI smoke.
- PyInstaller portable directory build with bundled Python, PySide6, resources and FFmpeg; packaged `--self-test` verifies the frozen UI, FFmpeg and a writable LocalAppData cache without relying on `%TEMP%`.
- Work files (audio extraction, thumbnails) now live in `%LOCALAPPDATA%\QwenSubtitle\cache` instead of the system temporary directory, so restricted Windows profiles can process videos without administrator rights.
- If AppData is not writable for the process, settings, DPAPI secrets, logs and cache fall back to a `portable-data` folder next to the EXE.
- Final portable build: 80,486,728-byte ZIP; self-test passes from the extracted archive with `PYTHONPATH`, `TEMP` and `TMP` unset.
- If the requested subtitle folder is not writable, writing now falls back to Desktop/Documents/home/app cache and reports the actual path instead of discarding the completed ASR/translation job.
- Documentation: README, AGENTS, product spec, architecture, API notes, UI design, testing, roadmap, handoff, security, privacy, contributing.

### Known limitations

- The portable EXE is unsigned; Windows SmartScreen may show an unknown-publisher warning.
- Single-file `--onefile` mode is not the default because it requires a writable system `%TEMP%` for extraction.
- Live Alibaba Cloud API calls are not part of CI and have not been validated with a real key in this repository.
- Only the official default DashScope endpoints are supported; workspace-specific domains are planned.
- No subtitle preview/editor, dark mode, batch queue, glossary, or diarization UI.
- Windows DPAPI is required for key storage.
- Automated tests use mocks and fake keys only.
