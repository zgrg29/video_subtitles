"""Subtitle data model, cleanup, segmentation, and SRT/ASS/VTT writers."""

from __future__ import annotations

import math
import os
import re
import tempfile
import unicodedata
from dataclasses import dataclass, replace
from pathlib import Path

from qwen_subtitle.constants import OUTPUT_MODE_BY_KEY, SUBTITLE_FORMAT_BY_KEY

_CJK_RANGES = (
    (0x1100, 0x11FF),  # Hangul Jamo
    (0x2E80, 0xA4CF),  # CJK radicals through Yi
    (0xAC00, 0xD7A3),  # Hangul syllables
    (0xF900, 0xFAFF),  # CJK compatibility ideographs
    (0xFE30, 0xFE4F),  # CJK compatibility forms
    (0xFF00, 0xFFEF),  # half/full-width forms
    (0x1F300, 0x1FAFF),  # emoji
    (0x20000, 0x3FFFD),  # CJK extension planes
)
_ZERO_WIDTH = dict.fromkeys(map(ord, "\u200b\u200c\u200d\ufeff"), None)
_SPACE_RE = re.compile(r"[ \t\u00a0\u3000]+")
_BREAK_AFTER = set("，。！？；：、,.!?;:)]】》」』…—")
_SENTENCE_END = set("。！？.!?")


def display_width(text: str) -> int:
    """Approximate terminal/subtitle width: CJK and emoji count as two."""

    width = 0
    for char in text:
        code = ord(char)
        if unicodedata.combining(char):
            continue
        if any(start <= code <= end for start, end in _CJK_RANGES):
            width += 2
        else:
            width += 1
    return width


def clean_text(value: str) -> str:
    if not value:
        return ""
    text = unicodedata.normalize("NFC", str(value)).translate(_ZERO_WIDTH)
    text = _SPACE_RE.sub(" ", text).strip()
    # Remove spaces that models often insert between CJK characters.
    text = re.sub(r"(?<=[\u3400-\u9fff])\s+(?=[\u3400-\u9fff])", "", text)
    return text


@dataclass(frozen=True)
class Cue:
    start_ms: int
    end_ms: int
    text: str
    translation: str = ""

    @property
    def duration_ms(self) -> int:
        return max(0, self.end_ms - self.start_ms)

    def with_text(self, text: str) -> "Cue":
        return replace(self, text=text)

    def with_translation(self, text: str) -> "Cue":
        return replace(self, translation=clean_text(text))


def cues_from_sentences(
    sentences: list[dict],
    audio_duration_ms: int | None = None,
) -> list[Cue]:
    """Convert Qwen ``sentences`` objects into clean cues.

    The API returns millisecond ``begin_time`` / ``end_time`` fields.  Bad or
    missing timestamps are repaired rather than allowed to produce invalid
    subtitle files.
    """

    provisional: list[Cue] = []
    previous_end = 0
    for index, sentence in enumerate(sentences):
        if not isinstance(sentence, dict):
            continue
        text = clean_text(str(sentence.get("text", "")))
        if not text:
            continue
        try:
            start = int(sentence.get("begin_time", sentence.get("start_time", 0)))
            end = int(sentence.get("end_time", sentence.get("stop_time", 0)))
        except (TypeError, ValueError):
            start, end = previous_end, previous_end + 1000
        start = max(0, start)
        if end <= start:
            end = start + max(800, min(6000, display_width(text) * 110))
        if audio_duration_ms and audio_duration_ms > 0:
            start = min(start, audio_duration_ms)
            end = min(end, max(audio_duration_ms, start + 300))
        provisional.append(Cue(start, max(start + 300, end), text))
        previous_end = end

    return normalize_cues(provisional, audio_duration_ms)


def normalize_cues(cues: list[Cue], audio_duration_ms: int | None = None) -> list[Cue]:
    if not cues:
        return []
    ordered = sorted(cues, key=lambda cue: (cue.start_ms, cue.end_ms))
    result: list[Cue] = []
    for cue in ordered:
        text = clean_text(cue.text)
        if not text:
            continue
        start = max(0, int(cue.start_ms))
        end = max(start + 300, int(cue.end_ms))
        if audio_duration_ms and audio_duration_ms > 0:
            if start >= audio_duration_ms:
                continue
            end = min(end, audio_duration_ms)
        if result and start < result[-1].end_ms:
            previous = result[-1]
            available = start - previous.start_ms
            if available >= 500:
                result[-1] = replace(previous, end_ms=start)
            elif available >= 250:
                # Tiny overlap: keep the previous cue short but valid.
                result[-1] = replace(previous, end_ms=start)
            else:
                start = previous.end_ms
                end = max(start + 300, end)
        if end <= start:
            continue
        result.append(Cue(start, end, text))
    return result


def _split_text(text: str, max_units: int) -> list[str]:
    """Split one line at natural punctuation or word boundaries."""

    text = clean_text(text)
    if not text:
        return []
    if display_width(text) <= max_units:
        return [text]

    parts: list[str] = []
    current = ""
    for char in text:
        candidate = current + char
        if display_width(candidate) > max_units and current:
            # Prefer the last natural break if it is not too far back.
            break_at = -1
            for position in range(len(current) - 1, max(0, len(current) // 2) - 1, -1):
                if current[position] in _BREAK_AFTER or current[position].isspace():
                    break_at = position
                    break
            if break_at >= 0:
                head = current[: break_at + 1].strip()
                tail = current[break_at + 1 :].strip()
                if head:
                    parts.append(head)
                current = (tail + char).strip()
            else:
                parts.append(current.strip())
                current = char
        else:
            current = candidate
    if current.strip():
        parts.append(current.strip())
    return [part for part in parts if part]


def split_oversized_cues(cues: list[Cue], max_units: int = 42) -> list[Cue]:
    """Turn overlong cues into sequential cues with proportional timing."""

    output: list[Cue] = []
    for cue in cues:
        text = clean_text(cue.text)
        if display_width(text) <= max_units:
            output.append(cue.with_text(text))
            continue
        chunks = _split_text(text, max_units)
        total_units = sum(max(1, display_width(chunk)) for chunk in chunks)
        cursor = cue.start_ms
        for index, chunk in enumerate(chunks):
            if index == len(chunks) - 1:
                end = cue.end_ms
            else:
                share = max(1, display_width(chunk)) / total_units
                end = cursor + max(500, int(cue.duration_ms * share))
                end = min(end, max(cursor + 300, cue.end_ms - 300))
            if end <= cursor:
                end = cursor + 500
            output.append(Cue(cursor, end, chunk))
            cursor = end
    return normalize_cues(output)


def _wrap_by_width(text: str, max_units: int) -> list[str]:
    text = clean_text(text)
    if display_width(text) <= max_units:
        return [text]
    lines = _split_text(text, max_units)
    # _split_text can return three or more pieces; rebalance into two lines.
    if len(lines) <= 2:
        return lines
    joined = " ".join(lines)
    target = max(1, math.ceil(display_width(joined) / 2))
    left = _split_text(joined, target)
    if len(left) >= 2:
        return [left[0], "".join(left[1:])]
    return [joined]


def wrap_subtitle(text: str, max_units_per_line: int = 40) -> str:
    """Wrap into at most two balanced lines for subtitle display."""

    lines = _wrap_by_width(text, max_units_per_line)
    return "\n".join(line for line in lines if line)


def _ass_time(milliseconds: int) -> str:
    total_cs = max(0, int(round(milliseconds / 10)))
    hours, remainder = divmod(total_cs, 360_000)
    minutes, remainder = divmod(remainder, 6_000)
    seconds, centiseconds = divmod(remainder, 100)
    return f"{hours}:{minutes:02d}:{seconds:02d}.{centiseconds:02d}"


def _srt_time(milliseconds: int) -> str:
    milliseconds = max(0, int(round(milliseconds)))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def _vtt_time(milliseconds: int) -> str:
    return _srt_time(milliseconds).replace(",", ".")


def _ass_escape(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace("{", "\\{")
        .replace("}", "\\}")
        .replace("\n", "\\N")
    )


def _mode_body(cue: Cue, content_mode: str) -> str:
    original = wrap_subtitle(cue.text)
    if content_mode == "original":
        return original
    translated = wrap_subtitle(cue.translation or cue.text)
    if content_mode == "bilingual":
        if translated and translated != original:
            return f"{original}\n{translated}"
        return original
    return translated


def to_srt(cues: list[Cue], content_mode: str = "translated") -> str:
    blocks = []
    for index, cue in enumerate(cues, start=1):
        body = _mode_body(cue, content_mode)
        blocks.append(f"{index}\n{_srt_time(cue.start_ms)} --> {_srt_time(cue.end_ms)}\n{body}")
    return "\n\n".join(blocks) + ("\n" if blocks else "")


def to_vtt(cues: list[Cue], content_mode: str = "translated") -> str:
    blocks = ["WEBVTT"]
    for cue in cues:
        body = _mode_body(cue, content_mode)
        blocks.append(f"{_vtt_time(cue.start_ms)} --> {_vtt_time(cue.end_ms)}\n{body}")
    return "\n\n".join(blocks) + "\n"


def to_ass(cues: list[Cue], content_mode: str = "translated") -> str:
    header = """[Script Info]
; Generated by Qwen Subtitle
ScriptType: v4.00+
WrapStyle: 2
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709
PlayResX: 1920
PlayResY: 1080

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Microsoft YaHei UI,54,&H00FFFFFF,&H000000FF,&H00101010,&H64000000,0,0,0,0,100,100,0,0,1,2.2,0.8,2,80,80,56,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []
    for cue in cues:
        if content_mode == "bilingual":
            original = wrap_subtitle(cue.text, max_units_per_line=38)
            translated = wrap_subtitle(cue.translation or cue.text, max_units_per_line=38)
            body = original if translated == original else f"{original}\n{translated}"
        elif content_mode == "original":
            body = wrap_subtitle(cue.text, max_units_per_line=38)
        else:
            body = wrap_subtitle(cue.translation or cue.text, max_units_per_line=38)
        lines.append(
            f"Dialogue: 0,{_ass_time(cue.start_ms)},{_ass_time(cue.end_ms)},"
            f"Default,,0,0,0,,{_ass_escape(body)}"
        )
    return header + "\n".join(lines) + ("\n" if lines else "")


def render_subtitle(cues: list[Cue], format_key: str, content_mode: str = "translated") -> str:
    if format_key not in SUBTITLE_FORMAT_BY_KEY:
        raise ValueError(f"Unsupported subtitle format: {format_key}")
    if content_mode not in OUTPUT_MODE_BY_KEY:
        raise ValueError(f"Unsupported content mode: {content_mode}")
    if format_key == "srt":
        return to_srt(cues, content_mode)
    if format_key == "ass":
        return to_ass(cues, content_mode)
    return to_vtt(cues, content_mode)


def write_subtitle(
    cues: list[Cue],
    format_key: str,
    path: Path,
    content_mode: str = "translated",
) -> Path:
    if not cues:
        raise ValueError("没有可写入的字幕内容。")
    content = render_subtitle(cues, format_key, content_mode)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=".subtitle-", suffix=f".{format_key}", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8-sig", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
    return path


def parse_sentences(payload: dict) -> list[dict]:
    """Extract sentence objects from several Qwen-ASR result shapes."""

    if not isinstance(payload, dict):
        return []
    candidates: list[dict] = []
    for key in ("transcripts",):
        value = payload.get(key)
        if isinstance(value, list):
            candidates.extend(item for item in value if isinstance(item, dict))
    for container_key in ("result", "output", "data"):
        container = payload.get(container_key)
        if isinstance(container, dict):
            value = container.get("transcripts")
            if isinstance(value, list):
                candidates.extend(item for item in value if isinstance(item, dict))
    for transcript in candidates:
        sentences = transcript.get("sentences")
        if isinstance(sentences, list):
            cleaned = [item for item in sentences if isinstance(item, dict)]
            if cleaned:
                return cleaned
    # Some providers return a flat sentence list.
    flat = payload.get("sentences")
    if isinstance(flat, list):
        return [item for item in flat if isinstance(item, dict)]
    return []
