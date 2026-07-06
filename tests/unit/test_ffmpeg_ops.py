from pathlib import Path

import pytest

from essaygen.assembly.captions import Cue
from essaygen.assembly.ffmpeg_ops import (
    build_caption_burn_command,
    build_caption_filter,
    build_concat_command,
    build_concat_file_content,
    build_image_clip_command,
    compute_caption_font_size,
    compute_wrap_width_chars,
    escape_filter_path,
    probe_duration_sec,
    resolve_output_dimensions,
    run_ffmpeg,
    write_cue_textfiles,
)
from essaygen.core.errors import FatalError


def test_resolve_output_dimensions_for_16_9():
    assert resolve_output_dimensions("16:9") == (1920, 1080)


def test_resolve_output_dimensions_for_9_16():
    assert resolve_output_dimensions("9:16") == (1080, 1920)


def test_resolve_output_dimensions_raises_for_unknown_ratio():
    with pytest.raises(FatalError):
        resolve_output_dimensions("4:3")


def test_build_image_clip_command_includes_expected_args():
    args = build_image_clip_command(
        image_path=Path("images/sec_01_sub_01.png"),
        audio_path=Path("audio/sec_01_sub_01.wav"),
        output_path=Path("sections/sec_01_sub_01_clip.mp4"),
        duration_sec=5.0,
        width=1920,
        height=1080,
        fps=25,
    )

    assert args[0] == "ffmpeg"
    assert str(Path("images/sec_01_sub_01.png")) in args
    assert str(Path("audio/sec_01_sub_01.wav")) in args
    assert str(Path("sections/sec_01_sub_01_clip.mp4")) in args
    assert any("zoompan" in arg for arg in args)
    assert any("1920x1080" in arg for arg in args)
    assert "5.000" in args


def test_build_image_clip_command_zoom_is_center_anchored_not_corner():
    # Regression test: the original formula omitted x/y entirely, which
    # zoompan defaults to x=0:y=0 — anchoring the crop at the top-left
    # corner so the clip appeared to "zoom into one corner" instead of
    # zooming toward the image's content. Confirmed live by rendering both
    # versions and comparing frames before writing this fix.
    args = build_image_clip_command(
        image_path=Path("images/sec_01_sub_01.png"),
        audio_path=Path("audio/sec_01_sub_01.wav"),
        output_path=Path("sections/sec_01_sub_01_clip.mp4"),
        duration_sec=5.0,
        width=1920,
        height=1080,
    )
    filter_arg = args[args.index("-filter_complex") + 1]

    assert "iw/2-(iw/zoom/2)" in filter_arg
    assert "ih/2-(ih/zoom/2)" in filter_arg


def test_build_image_clip_command_pan_direction_varies_by_variant():
    kwargs = dict(
        image_path=Path("images/sec_01_sub_01.png"),
        audio_path=Path("audio/sec_01_sub_01.wav"),
        output_path=Path("sections/sec_01_sub_01_clip.mp4"),
        duration_sec=5.0,
        width=1920,
        height=1080,
    )
    args_v0 = build_image_clip_command(**kwargs, pan_variant=0)
    args_v1 = build_image_clip_command(**kwargs, pan_variant=1)

    filter_v0 = args_v0[args_v0.index("-filter_complex") + 1]
    filter_v1 = args_v1[args_v1.index("-filter_complex") + 1]

    assert filter_v0 != filter_v1


def test_build_image_clip_command_pan_variant_cycles():
    kwargs = dict(
        image_path=Path("images/sec_01_sub_01.png"),
        audio_path=Path("audio/sec_01_sub_01.wav"),
        output_path=Path("sections/sec_01_sub_01_clip.mp4"),
        duration_sec=5.0,
        width=1920,
        height=1080,
    )
    args_v0 = build_image_clip_command(**kwargs, pan_variant=0)
    args_v4 = build_image_clip_command(**kwargs, pan_variant=4)

    filter_v0 = args_v0[args_v0.index("-filter_complex") + 1]
    filter_v4 = args_v4[args_v4.index("-filter_complex") + 1]

    assert filter_v0 == filter_v4


def test_build_image_clip_command_zoom_rate_is_duration_adaptive():
    # A fixed per-frame zoom increment caps out early on long clips and then
    # sits frozen for the rest of the duration. The increment should instead
    # scale with clip length so max zoom is reached right at the clip's end.
    import re

    kwargs = dict(
        image_path=Path("images/sec_01_sub_01.png"),
        audio_path=Path("audio/sec_01_sub_01.wav"),
        output_path=Path("sections/sec_01_sub_01_clip.mp4"),
        width=1920,
        height=1080,
        fps=25,
    )
    args_short = build_image_clip_command(**kwargs, duration_sec=2.0)
    args_long = build_image_clip_command(**kwargs, duration_sec=20.0)

    filter_short = args_short[args_short.index("-filter_complex") + 1]
    filter_long = args_long[args_long.index("-filter_complex") + 1]

    incr_short = float(re.search(r"zoom\+([\d.]+)", filter_short).group(1))
    incr_long = float(re.search(r"zoom\+([\d.]+)", filter_long).group(1))

    assert incr_short > incr_long


def test_build_image_clip_command_without_ken_burns_uses_plain_scale():
    args = build_image_clip_command(
        image_path=Path("images/sec_01_sub_01.png"),
        audio_path=Path("audio/sec_01_sub_01.wav"),
        output_path=Path("sections/sec_01_sub_01_clip.mp4"),
        duration_sec=5.0,
        width=1920,
        height=1080,
        fps=25,
        ken_burns=False,
    )

    assert not any("zoompan" in arg for arg in args)
    assert any("scale=1920:1080" in arg for arg in args)


def test_build_concat_file_content_uses_absolute_paths():
    # ffmpeg's concat demuxer resolves relative paths in the list file
    # relative to the list file's own directory, not the process cwd — using
    # absolute paths sidesteps that ambiguity regardless of where the list
    # file itself ends up living.
    content = build_concat_file_content([Path("sections/sec_01.mp4"), Path("sections/sec_02.mp4")])

    lines = content.splitlines()
    assert len(lines) == 2
    assert lines[0] == f"file '{Path('sections/sec_01.mp4').resolve().as_posix()}'"
    assert lines[1] == f"file '{Path('sections/sec_02.mp4').resolve().as_posix()}'"


def test_build_concat_command_includes_expected_args():
    args = build_concat_command(Path("sections/concat.txt"), Path("final.mp4"))

    assert args[0] == "ffmpeg"
    assert str(Path("sections/concat.txt")) in args
    assert "final.mp4" in args
    assert "concat" in args


# Caption burn-in uses drawtext (not the `subtitles` filter): conda-forge's
# Windows ffmpeg builds don't link libass, so `subtitles` isn't available in
# this build at all (confirmed live — every ffmpeg build searched on
# conda-forge, gpl and lgpl alike, has zero libass dependency). drawtext
# needs no libass and this build already has libfreetype/libfontconfig.
# Text is passed via `textfile=` rather than inline `text='...'` specifically
# to sidestep drawtext's fragile quote/colon escaping rules for arbitrary
# narration text (apostrophes, colons in the narration are common and painful
# to escape correctly inline).


def test_escape_filter_path_escapes_backslashes_and_colons():
    assert escape_filter_path("C:/Users/kerko/cue.txt") == "C\\:/Users/kerko/cue.txt"


def test_compute_caption_font_size_scales_with_height():
    font_1080p = compute_caption_font_size(1080)
    font_1920p = compute_caption_font_size(1920)

    assert font_1080p > 36  # bigger than the old height // 30 default
    assert font_1920p > font_1080p


def test_compute_wrap_width_chars_stays_within_target_fraction_of_frame_width():
    font_size = compute_caption_font_size(1080)
    chars = compute_wrap_width_chars(1920, font_size, max_width_fraction=0.5)

    # rough round-trip: chars * an average glyph width shouldn't wildly
    # exceed half the frame width
    assert chars * font_size * 0.55 <= 1920 * 0.5 + font_size  # small slack for rounding


def test_write_cue_textfiles_writes_one_file_per_cue(tmp_path):
    cues = [Cue(index=1, start_sec=0.0, end_sec=2.0, text="First line.")]

    paths = write_cue_textfiles(cues, tmp_path / "caption_cues", width=1920, height=1080)

    assert len(paths) == 1
    assert paths[0].read_text(encoding="utf-8") == "First line."


def test_write_cue_textfiles_wraps_long_cue_text_to_at_most_two_lines(tmp_path):
    long_text = (
        "This is a fairly long sentence with plenty of words that is definitely "
        "going to need wrapping across more than one line to fit within half "
        "the frame width at a larger font size than before."
    )
    cues = [Cue(index=1, start_sec=0.0, end_sec=2.0, text=long_text)]

    paths = write_cue_textfiles(cues, tmp_path / "caption_cues", width=1920, height=1080)

    content = paths[0].read_text(encoding="utf-8")
    lines = content.split("\n")
    assert len(lines) <= 2


def test_build_caption_filter_includes_timing_window_per_cue(tmp_path):
    cue = Cue(index=1, start_sec=1.5, end_sec=4.0, text="Hello.")
    path = tmp_path / "cue_001.txt"
    path.write_text("Hello.", encoding="utf-8")

    filter_str = build_caption_filter([(cue, path)], width=1920, height=1080)

    assert "drawtext" in filter_str
    assert "between(t,1.500,4.000)" in filter_str
    assert "textfile=" in filter_str


def test_build_caption_filter_uses_bigger_font_and_higher_position():
    cue = Cue(index=1, start_sec=0.0, end_sec=2.0, text="Hello.")
    path = Path("cue_001.txt")

    filter_str = build_caption_filter([(cue, path)], width=1920, height=1080)

    font_size = compute_caption_font_size(1080)
    assert f"fontsize={font_size}" in filter_str
    # positioned above the old fixed 40px margin from the bottom
    assert "y=h-th-40" not in filter_str


def test_build_caption_filter_chains_multiple_cues(tmp_path):
    cue1 = Cue(index=1, start_sec=0.0, end_sec=2.0, text="First.")
    cue2 = Cue(index=2, start_sec=2.0, end_sec=4.0, text="Second.")
    path1 = tmp_path / "cue_001.txt"
    path2 = tmp_path / "cue_002.txt"
    path1.write_text("First.", encoding="utf-8")
    path2.write_text("Second.", encoding="utf-8")

    filter_str = build_caption_filter([(cue1, path1), (cue2, path2)], width=1920, height=1080)

    assert filter_str.count("drawtext") == 2
    assert "between(t,0.000,2.000)" in filter_str
    assert "between(t,2.000,4.000)" in filter_str


def test_build_caption_burn_command_uses_filter_script_not_inline_vf():
    # With many sentence-level cues, an inline -vf string long enough
    # exceeded Windows' command-line length limit (WinError 206) — the
    # filter graph is written to a file and read via -filter_script:v
    # instead, which has no such limit.
    args = build_caption_burn_command(Path("merged.mp4"), Path("caption_filter.txt"), Path("final.mp4"))

    assert args[0] == "ffmpeg"
    assert "merged.mp4" in args
    assert "-filter_script:v" in args
    assert str(Path("caption_filter.txt")) in args
    assert "-vf" not in args
    assert "final.mp4" in args


class FakeCompletedProcess:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_probe_duration_sec_parses_ffprobe_output():
    def fake_runner(args, capture_output, text, check):
        return FakeCompletedProcess(stdout="12.345000\n")

    duration = probe_duration_sec(Path("audio/sec_01_sub_01.wav"), runner=fake_runner)

    assert duration == pytest.approx(12.345)


def test_run_ffmpeg_raises_fatal_error_on_nonzero_exit():
    def fake_runner(args, capture_output, text):
        return FakeCompletedProcess(returncode=1, stderr="boom")

    with pytest.raises(FatalError):
        run_ffmpeg(["ffmpeg", "-y"], runner=fake_runner)


def test_run_ffmpeg_succeeds_silently_on_zero_exit():
    def fake_runner(args, capture_output, text):
        return FakeCompletedProcess(returncode=0)

    run_ffmpeg(["ffmpeg", "-y"], runner=fake_runner)
