import subprocess
from pathlib import Path
from typing import Callable

from essaygen.assembly.captions import Cue, wrap_caption_text
from essaygen.core.errors import FatalError

_ASPECT_RATIO_DIMENSIONS = {
    "16:9": (1920, 1080),
    "9:16": (1080, 1920),
}

# Ken Burns tuning. Confirmed live (rendered + inspected frames) that
# omitting x/y anchors the crop at the top-left corner (zoompan's default),
# which reads as "zooming into one corner" rather than exploring the image —
# hence the explicit center-anchored x/y below. pan_variant cycles the pan
# direction across (up to) 4 diagonals so consecutive clips in a video
# don't all pan the same way.
_MAX_ZOOM = 1.4
_PAN_X_FRACTION = 0.12
_PAN_Y_FRACTION = 0.08
_PAN_DIRECTIONS = [(1, 1), (-1, 1), (1, -1), (-1, -1)]


def resolve_output_dimensions(aspect_ratio: str) -> tuple[int, int]:
    if aspect_ratio not in _ASPECT_RATIO_DIMENSIONS:
        raise FatalError(f"Unsupported aspect ratio: {aspect_ratio!r}")
    return _ASPECT_RATIO_DIMENSIONS[aspect_ratio]


def build_image_clip_command(
    image_path: Path,
    audio_path: Path,
    output_path: Path,
    duration_sec: float,
    width: int,
    height: int,
    fps: int = 25,
    ken_burns: bool = True,
    pan_variant: int = 0,
) -> list[str]:
    if ken_burns:
        total_frames = max(1, int(round(duration_sec * fps)))
        # Duration-adaptive rate: a fixed per-frame increment caps out early
        # on long clips and then sits frozen for the rest of the duration.
        # Scaling by total_frames means every clip reaches _MAX_ZOOM right
        # at its own end, regardless of length.
        zoom_increment = (_MAX_ZOOM - 1.0) / total_frames
        pan_x_sign, pan_y_sign = _PAN_DIRECTIONS[pan_variant % len(_PAN_DIRECTIONS)]
        pan_x = _PAN_X_FRACTION * pan_x_sign
        pan_y = _PAN_Y_FRACTION * pan_y_sign
        video_filter = (
            f"scale={width * 4}:-1,"
            f"zoompan=z='min(zoom+{zoom_increment:.6f},{_MAX_ZOOM})':"
            f"x='iw/2-(iw/zoom/2)+(iw*{pan_x:.4f}*on/{total_frames})':"
            f"y='ih/2-(ih/zoom/2)+(ih*{pan_y:.4f}*on/{total_frames})':"
            f"d={total_frames}:s={width}x{height}:fps={fps}"
        )
    else:
        video_filter = f"scale={width}:{height},fps={fps}"
    return [
        "ffmpeg",
        "-y",
        "-loop",
        "1",
        "-i",
        str(image_path),
        "-i",
        str(audio_path),
        "-filter_complex",
        video_filter,
        "-c:v",
        "libx264",
        "-t",
        f"{duration_sec:.3f}",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-shortest",
        str(output_path),
    ]


def build_concat_file_content(clip_paths: list[Path]) -> str:
    lines = [f"file '{p.resolve().as_posix()}'" for p in clip_paths]
    return "\n".join(lines) + "\n"


def build_concat_command(concat_file_path: Path, output_path: Path) -> list[str]:
    return [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_file_path),
        "-c",
        "copy",
        str(output_path),
    ]


def escape_filter_path(path: str) -> str:
    return path.replace("\\", "\\\\").replace(":", "\\:")


# Rough average glyph width as a fraction of font size, for common sans
# fonts — used to translate a target pixel width into a wrap character
# count, since drawtext has no built-in auto-wrap.
_AVG_CHAR_WIDTH_RATIO = 0.55


def compute_caption_font_size(height: int) -> int:
    return max(32, height // 18)


def compute_wrap_width_chars(frame_width: int, font_size: int, max_width_fraction: float = 0.5) -> int:
    max_width_px = frame_width * max_width_fraction
    return max(10, int(max_width_px / (font_size * _AVG_CHAR_WIDTH_RATIO)))


def write_cue_textfiles(cues: list[Cue], output_dir: Path, width: int, height: int) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    font_size = compute_caption_font_size(height)
    wrap_width = compute_wrap_width_chars(width, font_size)
    paths = []
    for cue in cues:
        path = output_dir / f"cue_{cue.index:03d}.txt"
        path.write_text(wrap_caption_text(cue.text, width=wrap_width, max_lines=2), encoding="utf-8")
        paths.append(path)
    return paths


def build_caption_filter(cue_files: list[tuple[Cue, Path]], width: int, height: int) -> str:
    font_size = compute_caption_font_size(height)
    y_margin = int(height * 0.15)
    parts = []
    for cue, path in cue_files:
        escaped_path = escape_filter_path(path.resolve().as_posix())
        parts.append(
            f"drawtext=textfile='{escaped_path}':fontcolor=white:fontsize={font_size}:"
            f"box=1:boxcolor=black@0.5:boxborderw=8:x=(w-text_w)/2:y=h-th-{y_margin}:"
            f"enable='between(t,{cue.start_sec:.3f},{cue.end_sec:.3f})'"
        )
    return ",".join(parts)


def build_caption_burn_command(
    input_video: Path, filter_script_path: Path, output_path: Path
) -> list[str]:
    # Reads the filter graph from a file via -filter_script:v rather than
    # passing it inline via -vf: with many sentence-level cues, the combined
    # filter string is long enough to exceed Windows' command-line length
    # limit (WinError 206). Reading from a file has no such limit.
    return [
        "ffmpeg",
        "-y",
        "-i",
        str(input_video),
        "-filter_script:v",
        str(filter_script_path),
        "-c:a",
        "copy",
        str(output_path),
    ]


def probe_duration_sec(path: Path, runner: Callable = subprocess.run) -> float:
    result = runner(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(result.stdout.strip())


def run_ffmpeg(args: list[str], runner: Callable = subprocess.run) -> None:
    result = runner(args, capture_output=True, text=True)
    if result.returncode != 0:
        raise FatalError(f"ffmpeg command failed: {result.stderr}")
