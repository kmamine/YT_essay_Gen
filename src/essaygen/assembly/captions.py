import re
import textwrap
from dataclasses import dataclass

_SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'])")


@dataclass
class Cue:
    index: int
    start_sec: float
    end_sec: float
    text: str


def format_srt_timestamp(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_BOUNDARY_RE.split(text.strip()) if s.strip()]


def wrap_caption_text(text: str, width: int = 45, max_lines: int | None = None) -> str:
    lines = textwrap.wrap(text, width=width, max_lines=max_lines, placeholder=" …")
    return "\n".join(lines)


def build_cues(narrations: list[str], durations: list[float]) -> list[Cue]:
    cues = []
    index = 1
    elapsed = 0.0
    for narration, duration in zip(narrations, durations):
        sentences = split_sentences(narration) or [narration]
        total_chars = sum(len(s) for s in sentences) or 1
        sentence_start = elapsed
        for sentence in sentences:
            sentence_duration = duration * (len(sentence) / total_chars)
            cues.append(
                Cue(
                    index=index,
                    start_sec=sentence_start,
                    end_sec=sentence_start + sentence_duration,
                    text=sentence,
                )
            )
            sentence_start += sentence_duration
            index += 1
        elapsed += duration
    return cues


def render_srt(cues: list[Cue]) -> str:
    blocks = [
        f"{cue.index}\n{format_srt_timestamp(cue.start_sec)} --> "
        f"{format_srt_timestamp(cue.end_sec)}\n{cue.text}\n"
        for cue in cues
    ]
    return "\n".join(blocks)
