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

# Aspect-ratio-preserving fill: source images rarely match the output
# aspect ratio exactly. "blur" (default) fills the leftover space with a
# heavily blurred, cropped-to-cover copy of the same image -- the common
# Shorts/Stories look. "black" pads with solid bars instead. Either way
# the foreground image itself is scaled to fit entirely within the frame
# (force_original_aspect_ratio=decrease), never cropped or stretched.
_BLUR_SIGMA = 20


def resolve_output_dimensions(aspect_ratio: str) -> tuple[int, int]:
    if aspect_ratio not in _ASPECT_RATIO_DIMENSIONS:
        raise FatalError(f"Unsupported aspect ratio: {aspect_ratio!r}")
    return _ASPECT_RATIO_DIMENSIONS[aspect_ratio]


def _build_canvas_filter(width: int, height: int, fill_mode: str) -> str:
    if fill_mode == "blur":
        return (
            f"[0:v]scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},gblur=sigma={_BLUR_SIGMA}[bg];"
            f"[0:v]scale={width}:{height}:force_original_aspect_ratio=decrease[fg];"
            "[bg][fg]overlay=(W-w)/2:(H-h)/2[canvas]"
        )
    if fill_mode == "black":
        return (
            f"[0:v]scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black[canvas]"
        )
    raise FatalError(f"Unsupported image fill mode: {fill_mode!r}")


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
    fill_mode: str = "blur",
) -> list[str]:
    canvas_filter = _build_canvas_filter(width, height, fill_mode)

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
            f"{canvas_filter};"
            f"[canvas]scale={width * 4}:-1,"
            f"zoompan=z='min(zoom+{zoom_increment:.6f},{_MAX_ZOOM})':"
            f"x='iw/2-(iw/zoom/2)+(iw*{pan_x:.4f}*on/{total_frames})':"
            f"y='ih/2-(ih/zoom/2)+(ih*{pan_y:.4f}*on/{total_frames})':"
            f"d={total_frames}:s={width}x{height}:fps={fps}"
        )
    else:
        video_filter = f"{canvas_filter};[canvas]fps={fps}"
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


# "constant" mode: one fixed volume for the whole runtime -- simple and
# predictable, the default after live feedback that duck mode's sidechain
# behavior read as either inaudible or overpowering depending on the
# track. Originally -22dB, live-reported as too quiet to hear at all;
# raised to -14dB (duck mode's own pre-ducking base level) so it's clearly
# audible without ducking to compensate. "duck" mode: sidechain-compresses
# the music under narration and lets it recover in the gaps.
_MUSIC_CONSTANT_VOLUME_DB = -14.0
_MUSIC_DUCK_BASE_VOLUME_DB = -14.0
_DUCK_THRESHOLD = 0.05
_DUCK_RATIO = 8
_DUCK_ATTACK_MS = 5
_DUCK_RELEASE_MS = 250

# Live-verified real bug: different Freesound tracks have wildly different
# native recording levels (one ambient drone track measured -43dB mean /
# -20dB max even completely unprocessed). Normalizing to a consistent EBU
# R128 loudness target before applying the volume= offset above means that
# offset is relative to a fixed reference, not to whatever level a given
# track happened to be recorded/mastered at.
_MUSIC_LOUDNORM_TARGET_LUFS = -20
_MUSIC_LOUDNORM_TRUE_PEAK = -2
_MUSIC_LOUDNORM_LRA = 7
_LOUDNORM_FILTER = (
    f"loudnorm=I={_MUSIC_LOUDNORM_TARGET_LUFS}:TP={_MUSIC_LOUDNORM_TRUE_PEAK}:"
    f"LRA={_MUSIC_LOUDNORM_LRA}"
)


def build_music_mix_command(
    video_path: Path, music_path: Path, output_path: Path, mode: str = "constant"
) -> list[str]:
    # normalize=0 on amix: live-verified real bug -- ffmpeg's amix filter
    # defaults to normalize=true, which auto-scales down input levels to
    # prevent clipping, silently undermining the volume= boost above
    # regardless of how high it's set (measured -30.9dB max during a
    # narration gap even with -14dB pre-mix volume applied). Disabling it
    # makes our explicit volume control actually take effect.
    if mode == "constant":
        filter_complex = (
            f"[1:a]{_LOUDNORM_FILTER},volume={_MUSIC_CONSTANT_VOLUME_DB}dB[music];"
            "[0:a][music]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[aout]"
        )
    elif mode == "duck":
        filter_complex = (
            f"[1:a]{_LOUDNORM_FILTER},volume={_MUSIC_DUCK_BASE_VOLUME_DB}dB[music];"
            f"[music][0:a]sidechaincompress=threshold={_DUCK_THRESHOLD}:ratio={_DUCK_RATIO}:"
            f"attack={_DUCK_ATTACK_MS}:release={_DUCK_RELEASE_MS}[ducked];"
            "[0:a][ducked]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[aout]"
        )
    else:
        raise FatalError(f"Unsupported music mix mode: {mode!r}")

    return [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-stream_loop",
        "-1",
        "-i",
        str(music_path),
        "-filter_complex",
        filter_complex,
        "-map",
        "0:v",
        "-map",
        "[aout]",
        "-c:v",
        "copy",
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
