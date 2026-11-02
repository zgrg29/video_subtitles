# 贡献指南

感谢你愿意改进千问字幕。这个仓库是公开的，第一条规则是：**不要提交任何真实密钥或个人信息**。

## 开始之前

1. 阅读 [AGENTS.md](AGENTS.md)、[docs/PRODUCT_SPEC.md](docs/PRODUCT_SPEC.md)、[docs/HANDOFF.md](docs/HANDOFF.md)。
2. 确认改动符合“选视频 → 千问识别 → 翻译 → 字幕”的核心目标。
3. 如果改动会改变用户可见行为，先开 Issue 描述场景与验收标准。

## 开发环境

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python run.py
```

## 提交前检查

```powershell
python -m pytest
python scripts/check_public_repo.py
```

两项都必须通过。UI 改动还需要附一张不含个人信息的截图（建议使用合成视频/空状态）。

## 绝对不要提交

- 真实 API Key、Bearer token、私钥、临时上传/下载链接。
- `.env`、`secrets.bin`、`settings.json`、`app.log`。
- 真实视频、音频、字幕、客户资料。
- 真实姓名、邮箱、手机号、住址、个人主页、`C:\Users\<name>` 路径。
- 带账号名/头像/文件路径的截图。

测试里只能使用 `sk-test…` / `sk-fake…` 这类明显伪造的值，并且不能被真实调用。

## 代码约定

- 核心层（`core/`）不导入 Qt。
- UI 文案必须走 `i18n.py`，新增 key 要同时补齐 `zh`、`en`、`ja`。
- 新增 ASR/翻译模型时，同步更新 `constants.py`、模型说明、`i18n.py`、测试和文档。
- 不要为了兼容而静默把用户选择的模型换成旧模型；明确报错，让用户选择。
- 不要在「仅原文」模式发起 Qwen-MT 请求。
- 错误消息不能包含 Key 或完整本地路径。
- 保持依赖精简；不要无理由引入大型框架。

## 翻译贡献

- 三语 key 必须一致；`tests/test_i18n.py` 会检查。
- 中文用短句、动词开头；English 用 sentence case；日本語用です・ます调。
- 不要直译模型名；品牌名保持 `Qwen` / `Qwen-MT`。
- 修改文案时同时检查 1024×700 和 1180×800 下的截断。

## Pull Request

请包含：

- 解决的问题与用户场景。
- 改动范围（UI/核心/文档）。
- 测试结果（粘贴 `pytest` 与公开仓库扫描的结论，不要粘贴 Key）。
- UI 截图（如有）。
- 是否影响模型默认值、持久化、token 消耗或隐私边界。

## 提交身份

如果你不希望公开个人邮箱，请使用 GitHub 提供的 noreply 邮箱配置 Git：

```powershell
git config user.email "<your-github-noreply-email>"
```

不要把真实邮箱写进提交作者、文档或示例。维护者合并前会检查提交历史中是否意外带入个人信息。
