# 千问 API 接入备注

> 最后核对：2026-11-02。千问/百炼的模型名、endpoint 和返回结构会变化；代码里的解析已尽量兼容，但上线前请再对照官方文档。本文不包含任何 API Key。Qwen-MT 当前目录为 Plus / Flash；旧文档中的 `qwen-mt-turbo` 已从应用选项中移除。

## 1. 地区与 Base URL

| 地区 | Base URL | API Key 控制台 |
| --- | --- | --- |
| 中国大陆（北京） | `https://dashscope.aliyuncs.com` | https://bailian.console.aliyun.com/ |
| 国际（新加坡） | `https://dashscope-intl.aliyuncs.com` | https://modelstudio.console.alibabacloud.com/ |

百炼正在推广业务空间专属域名：

- 北京：`https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com`
- 新加坡：`https://{WorkspaceId}.ap-southeast-1.maas.aliyuncs.com`

官方文档说明旧域名仍可正常使用。v0.1 使用旧域名；自定义 Workspace 域名是路线图项。

## 2. ASR 模型

| 模型 | 官方定位 | 本应用 |
| --- | --- | --- |
| `qwen-audio-3.1-asr-flash-filetrans` | 最新端到端离线语音识别，长音频、多语种/方言、句级时间戳 | **默认** |
| `qwen-audio-3.0-asr-flash-filetrans` | 上一代长音频模型 | 可选 |
| `qwen3-asr-flash-filetrans` | 轻量长音频模型 | 可选 |

参考：

- [非实时语音识别用户指南](https://help.aliyun.com/zh/model-studio/non-realtime-speech-recognition-user-guide)
- [Qwen-ASR API 参考](https://help.aliyun.com/zh/model-studio/qwen-asr-api-reference)
- [模型目录（Qwen-Audio-3.1-ASR）](https://raw.githubusercontent.com/modelstudioai/skills/main/skills/bailian-docs-llm-wiki/models/groups/qwen-audio-3.1-asr.json)

## 3. 长音频处理流程

```text
1. GET /api/v1/uploads?action=getPolicy&model=<model>
2. POST <upload_host>  (multipart/form-data)
3. POST /api/v1/services/audio/asr/transcription
4. GET  /api/v1/tasks/{task_id}   (poll)
5. GET  <transcription_url>       (download result JSON)
```

### 3.1 临时上传

`GET https://dashscope.aliyuncs.com/api/v1/uploads?action=getPolicy&model=qwen-audio-3.1-asr-flash-filetrans`

响应 `data` 包含：

- `upload_host`
- `upload_dir`
- `signature`
- `policy`
- `oss_access_key_id`
- `x_oss_object_acl`
- `x_oss_forbid_overwrite`
- `max_file_size_mb`

上传表单字段：

```text
OSSAccessKeyId, Signature, policy, x-oss-object-acl,
x-oss-forbid-overwrite, key, success_action_status=200, file
```

`key = upload_dir + "/" + 唯一文件名"`，返回 `oss://<key>`。

约束（官方文档）：

- 文件与上传时指定的模型绑定，后续调用必须使用同一个模型。
- 上传凭证/文件 48 小时有效。
- 单个上传默认上限 1 GB；ASR 模型本身对文件还有限制。
- 文件上传凭证接口按主账号 + 模型限流。
- 上传与识别必须属于同一个阿里云主账号。

上传完成后，调用 ASR 时**必须**在请求头加：

```text
X-DashScope-OssResourceResolve: enable
```

参考：[上传本地文件获取临时 URL](https://help.aliyun.com/zh/model-studio/get-temporary-file-url)

### 3.2 提交任务

`POST /api/v1/services/audio/asr/transcription`

请求头：

```text
Authorization: Bearer <API_KEY>
Content-Type: application/json
X-DashScope-Async: enable
X-DashScope-OssResourceResolve: enable
```

`qwen-audio-3.1` / `3.0`：

```json
{
  "model": "qwen-audio-3.1-asr-flash-filetrans",
  "input": { "file_urls": ["oss://..."] },
  "parameters": {
    "channel_id": [0],
    "language_hints": ["zh"],
    "enable_itn": true
  }
}
```

`qwen3-asr-flash-filetrans`：

```json
{
  "model": "qwen3-asr-flash-filetrans",
  "input": { "file_url": "oss://..." },
  "parameters": {
    "channel_id": [0],
    "language": "zh",
    "enable_itn": true,
    "enable_words": true
  }
}
```

`language_hints` / `language` 只在用户明确选择语言时发送；`auto` 时省略，交给模型自动判断。

### 3.3 轮询

`GET /api/v1/tasks/{task_id}`

状态：`PENDING`、`RUNNING`、`SUCCEEDED`、`FAILED`、`UNKNOWN`。本应用每 2.5 秒轮询，最长 2 小时，遇 429/5xx 有指数退避。

### 3.4 结果信封

不同模型返回不同：

`qwen3`：

```json
{
  "output": {
    "task_status": "SUCCEEDED",
    "result": { "transcription_url": "https://..." }
  }
}
```

`qwen-audio-3.1`：

```json
{
  "output": {
    "task_status": "SUCCEEDED",
    "results": [
      { "subtask_status": "SUCCEEDED", "transcription_url": "https://..." }
    ]
  }
}
```

下载后的 JSON 通常为：

```json
{
  "transcripts": [
    {
      "channel_id": 0,
      "sentences": [
        { "begin_time": 0, "end_time": 1440, "text": "欢迎使用。" }
      ]
    }
  ]
}
```

`begin_time` / `end_time` 单位为毫秒。应用会兼容 `result` / `results` / `sentences` 等嵌套形态；若仍拿不到句子，会明确报“没有识别到可用语音”。

## 4. Qwen-MT

请求：

`POST https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions`

```json
{
  "model": "qwen-mt-plus",
  "messages": [{ "role": "user", "content": "看完这个视频我没有笑" }],
  "translation_options": {
    "source_lang": "auto",
    "target_lang": "English"
  },
  "stream": false
}
```

响应：

```json
{
  "choices": [
    { "message": { "content": "I didn't laugh after watching this video." } }
  ]
}
```

语言值使用英文名称，例如 `Simplified Chinese`、`Traditional Chinese`、`English`、`Japanese`、`Cantonese`；源语言自动检测用 `auto`。ASR 的语言代码是另一套（`zh`、`yue`、`en`），不要混用。

模型：

- `qwen-mt-plus`：旗舰质量，支持 92 种语言，默认。
- `qwen-mt-flash`：轻量、快、便宜，支持 92 种语言。
- `qwen-mt-lite`：官方仍提供，但本应用暂不开放：部分免费额度账户会返回 `AllocationQuota.FreeTierOnly`，需付费额度才能使用。

参考：

- [机器翻译（Qwen-MT）](https://help.aliyun.com/zh/model-studio/machine-translation)
- [Qwen-MT API（模型目录）](https://raw.githubusercontent.com/modelstudioai/skills/main/skills/bailian-docs-llm-wiki/models/groups/qwen-mt-plus.json)
- [Qwen-MT OpenAI 兼容 API](https://docs.qwencloud.com/api-reference/specialized-models/qwen-mt/openai)

## 5. 翻译批处理与 token 说明

- 仅译文 / 双语：按 10 条字幕一批，用空行拼接后发送。
- 如果返回的空行数量与输入不一致，逐条重试以保证时间轴对齐。
- 仅原文：**不创建 Qwen-MT 请求**，也不要求配置翻译模型。
- 翻译成本按输入/输出 token 计费，字幕越长、语言越复杂，消耗越高。任务失败或取消时已发生的云端调用仍可能计费；本应用不做自动重试翻译（除网络层有限重试）。

## 6. 常见错误

| 现象 | 可能原因 | 处理 |
| --- | --- | --- |
| 401 | Key 错误或地区选错 | 检查地区与 Key |
| 403 / AccessDenied | Key 没有模型权限，或模型未在当前业务空间开通 | 在百炼控制台开通该模型；免费额度账户遇到 `AllocationQuota.FreeTierOnly` 时改用 Flash 或开通付费额度 |
| 429 | 限流/额度 | 等待后重试，检查配额 |
| `FILE_403_FORBIDDEN` | 上传文件与模型/账号不匹配、链接过期 | 重试；确认上传与识别使用同一账号、同一模型 |
| `UNKNOWN` | 任务过期/不存在 | 重新提交 |
| 无句子 | 无语音、纯音乐、音轨损坏 | 换视频或检查音轨 |
| 翻译为空 | 网络/模型异常、输入为空 | 重试或换翻译模型 |

## 7. 安全注意事项

- 不把 `Authorization`、`oss://` 临时链接、`transcription_url` 写入公开日志或仓库。
- `transcription_url` 是带签名的临时下载地址，默认 24 小时有效；不要持久化。
- 上传凭证接口有频控，不要并发轰炸。
- 应用只使用固定官方 Base URL；若未来允许自定义域名，必须强制 HTTPS 并校验返回的上传 host 属于 `.aliyuncs.com`。
