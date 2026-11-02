"""Product constants, model catalogues, and language metadata.

Only public, non-secret values live here.  API keys are never stored in this
module or in the repository.
"""

from __future__ import annotations

from dataclasses import dataclass

APP_NAME = "Qwen Subtitle"
APP_NAME_ZH = "千问字幕"
APP_ID = "QwenSubtitle"
VERSION = "0.1.0"
LICENSE_NAME = "MIT"
PROJECT_TAGLINE = "把视频，变成好字幕。"

# Intentionally blank until the public repository has an owner-approved URL.
# Never put a personal homepage, real name, or contact address here.
PROJECT_URL = ""


@dataclass(frozen=True)
class Region:
    key: str
    label: str
    short_label: str
    base_url: str
    console_url: str
    note: str


REGIONS: tuple[Region, ...] = (
    Region(
        key="cn",
        label="中国大陆",
        short_label="大陆版",
        base_url="https://dashscope.aliyuncs.com",
        console_url="https://bailian.console.aliyun.com/",
        note="北京地域，使用阿里云百炼大陆版 API Key",
    ),
    Region(
        key="intl",
        label="国际（新加坡）",
        short_label="国际版",
        base_url="https://dashscope-intl.aliyuncs.com",
        console_url="https://modelstudio.console.alibabacloud.com/",
        note="新加坡地域，API Key 与大陆版不通用",
    ),
)

DEFAULT_REGION = "cn"
REGION_BY_KEY = {region.key: region for region in REGIONS}


@dataclass(frozen=True)
class AsrModel:
    key: str
    label: str
    tagline: str
    description: str
    api_style: str  # "file_urls" or "file_url"
    badge: str = ""
    language_param: str = "language_hints"


ASR_MODELS: tuple[AsrModel, ...] = (
    AsrModel(
        key="qwen-audio-3.1-asr-flash-filetrans",
        label="Qwen-Audio 3.1 ASR",
        tagline="最新旗舰 · 长音频 · 句级时间戳",
        description="千问当前最新的长音频识别模型，支持多语种与中文方言，适合字幕制作。",
        api_style="file_urls",
        badge="最新",
        language_param="language_hints",
    ),
    AsrModel(
        key="qwen-audio-3.0-asr-flash-filetrans",
        label="Qwen-Audio 3.0 ASR",
        tagline="上一代旗舰 · 稳定",
        description="成熟的上一代长音频识别模型，适合作为兼容性备选。",
        api_style="file_urls",
        language_param="language_hints",
    ),
    AsrModel(
        key="qwen3-asr-flash-filetrans",
        label="Qwen3-ASR",
        tagline="轻量 · 长音频 · 句级时间戳",
        description="轻量长音频转写模型，速度快、成本低，适合日常视频。",
        api_style="file_url",
        language_param="language",
    ),
)

ASR_MODEL_BY_KEY = {model.key: model for model in ASR_MODELS}
DEFAULT_ASR_MODEL = ASR_MODELS[0].key


@dataclass(frozen=True)
class TranslationModel:
    key: str
    label: str
    tagline: str
    description: str
    badge: str = ""


TRANSLATION_MODELS: tuple[TranslationModel, ...] = (
    TranslationModel(
        key="qwen-mt-plus",
        label="Qwen-MT Plus",
        tagline="旗舰质量 · 术语与格式更稳",
        description="基于 Qwen3 的旗舰翻译模型，适合对译文质量要求高的内容。",
        badge="推荐",
    ),
    TranslationModel(
        key="qwen-mt-flash",
        label="Qwen-MT Flash",
        tagline="速度与成本平衡",
        description="轻量翻译模型，字幕批量翻译更快，日常内容足够。",
    ),
)

TRANSLATION_MODEL_BY_KEY = {model.key: model for model in TRANSLATION_MODELS}
DEFAULT_TRANSLATION_MODEL = TRANSLATION_MODELS[0].key


@dataclass(frozen=True)
class Language:
    code: str
    label: str
    asr_code: str | None
    qwen_name: str


SOURCE_LANGUAGES: tuple[Language, ...] = (
    Language("auto", "自动识别", None, "auto"),
    Language("zh", "中文（普通话）", "zh", "Chinese"),
    Language("yue", "粤语", "yue", "Cantonese"),
    Language("en", "英语", "en", "English"),
    Language("ja", "日语", "ja", "Japanese"),
    Language("ko", "韩语", "ko", "Korean"),
    Language("fr", "法语", "fr", "French"),
    Language("de", "德语", "de", "German"),
    Language("es", "西班牙语", "es", "Spanish"),
    Language("ru", "俄语", "ru", "Russian"),
    Language("pt", "葡萄牙语", "pt", "Portuguese"),
    Language("it", "意大利语", "it", "Italian"),
    Language("ar", "阿拉伯语", "ar", "Arabic"),
    Language("th", "泰语", "th", "Thai"),
    Language("vi", "越南语", "vi", "Vietnamese"),
    Language("id", "印尼语", "id", "Indonesian"),
    Language("tr", "土耳其语", "tr", "Turkish"),
)

TARGET_LANGUAGES: tuple[Language, ...] = (
    Language("zh-Hans", "简体中文", None, "Simplified Chinese"),
    Language("zh-Hant", "繁体中文", None, "Traditional Chinese"),
    Language("en", "英语", None, "English"),
    Language("ja", "日语", None, "Japanese"),
    Language("ko", "韩语", None, "Korean"),
    Language("fr", "法语", None, "French"),
    Language("de", "德语", None, "German"),
    Language("es", "西班牙语", None, "Spanish"),
    Language("ru", "俄语", None, "Russian"),
    Language("pt", "葡萄牙语", None, "Portuguese"),
    Language("it", "意大利语", None, "Italian"),
    Language("ar", "阿拉伯语", None, "Arabic"),
    Language("th", "泰语", None, "Thai"),
    Language("vi", "越南语", None, "Vietnamese"),
    Language("id", "印尼语", None, "Indonesian"),
    Language("tr", "土耳其语", None, "Turkish"),
)

SOURCE_LANGUAGE_BY_CODE = {lang.code: lang for lang in SOURCE_LANGUAGES}
TARGET_LANGUAGE_BY_CODE = {lang.code: lang for lang in TARGET_LANGUAGES}
DEFAULT_SOURCE_LANGUAGE = "auto"
DEFAULT_TARGET_LANGUAGE = "zh-Hans"


@dataclass(frozen=True)
class OutputMode:
    key: str
    label: str
    description: str


OUTPUT_MODES: tuple[OutputMode, ...] = (
    OutputMode(
        key="translated",
        label="仅译文",
        description="只输出翻译后的字幕。",
    ),
    OutputMode(
        key="bilingual",
        label="原文 + 译文（2 文件）",
        description="分别生成原文文件和译文文件，两个文件时间轴一致。",
    ),
    OutputMode(
        key="original",
        label="仅原文",
        description="只运行语音识别，不调用翻译模型，不消耗翻译 token。",
    ),
)

OUTPUT_MODE_BY_KEY = {mode.key: mode for mode in OUTPUT_MODES}
DEFAULT_OUTPUT_MODE = "translated"
UI_LANGUAGES = ("zh", "ja", "en")
DEFAULT_UI_LANGUAGE = "zh"


@dataclass(frozen=True)
class SubtitleFormat:
    key: str
    label: str
    extension: str
    description: str


SUBTITLE_FORMATS: tuple[SubtitleFormat, ...] = (
    SubtitleFormat("srt", "SRT", "srt", "兼容性最好，几乎所有播放器都支持"),
    SubtitleFormat("ass", "ASS", "ass", "可设置字体、描边与样式，适合视频压制"),
    SubtitleFormat("vtt", "VTT", "vtt", "网页与 HTML5 播放器常用格式"),
)

SUBTITLE_FORMAT_BY_KEY = {fmt.key: fmt for fmt in SUBTITLE_FORMATS}
DEFAULT_SUBTITLE_FORMAT = "srt"

VIDEO_EXTENSIONS = (
    ".mp4",
    ".mov",
    ".mkv",
    ".avi",
    ".webm",
    ".m4v",
    ".flv",
    ".wmv",
    ".ts",
    ".mts",
    ".m2ts",
    ".mpg",
    ".mpeg",
    ".3gp",
)

MAX_UPLOAD_BYTES = 1_000 * 1024 * 1024  # documented temporary upload limit
POLL_INTERVAL_SECONDS = 2.5
POLL_TIMEOUT_SECONDS = 2 * 60 * 60
TRANSLATION_BATCH_SIZE = 10
