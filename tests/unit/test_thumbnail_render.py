from pathlib import Path

import pytest
from PIL import Image

from essaygen.assembly.thumbnail import render_thumbnail, to_thumbnail_display_text
from essaygen.core.errors import FatalError


@pytest.fixture
def source_image(tmp_path) -> Path:
    # bright uniform image so darkening/gradient effects are easy to detect
    path = tmp_path / "source.jpg"
    Image.new("RGB", (800, 600), color=(230, 230, 230)).save(path)
    return path


@pytest.fixture
def font_path() -> Path:
    windows_font = Path(r"C:\Windows\Fonts\arialbd.ttf")
    if not windows_font.exists():
        pytest.skip("arialbd.ttf not available on this machine")
    return windows_font


def test_render_thumbnail_writes_file_at_youtube_standard_resolution(source_image, font_path, tmp_path):
    output_path = tmp_path / "thumbnail.jpg"

    render_thumbnail(source_image, "Rome's Fatal Mistake", output_path, font_path)

    assert output_path.exists()
    with Image.open(output_path) as img:
        assert img.size == (1280, 720)


def test_render_thumbnail_respects_custom_dimensions(source_image, font_path, tmp_path):
    output_path = tmp_path / "thumbnail.jpg"

    render_thumbnail(source_image, "Hook", output_path, font_path, width=640, height=360)

    with Image.open(output_path) as img:
        assert img.size == (640, 360)


def test_render_thumbnail_darkens_bottom_for_text_legibility(source_image, font_path, tmp_path):
    # A gradient scrim over the bottom portion of the frame is what makes
    # bold white text readable regardless of the underlying image content.
    # Starting from a uniformly bright source image, the bottom-left corner
    # (away from the text itself) should end up darker than the top-left
    # corner, which the gradient shouldn't reach.
    output_path = tmp_path / "thumbnail.jpg"

    render_thumbnail(source_image, "Hook Text", output_path, font_path)

    with Image.open(output_path) as img:
        top_left = img.getpixel((10, 10))
        bottom_left = img.getpixel((10, 710))
        assert sum(bottom_left[:3]) < sum(top_left[:3])


def test_render_thumbnail_without_play_button_by_default(source_image, font_path, tmp_path):
    # YouTube already overlays its own play-button UI on thumbnails in
    # feeds -- baking one in would be redundant/look amateurish there.
    output_path_no_button = tmp_path / "no_button.jpg"
    output_path_with_button = tmp_path / "with_button.jpg"

    render_thumbnail(source_image, "Hook", output_path_no_button, font_path, play_button=False)
    render_thumbnail(source_image, "Hook", output_path_with_button, font_path, play_button=True)

    with Image.open(output_path_no_button) as no_button, Image.open(output_path_with_button) as with_button:
        # center pixel should differ: the play button glyph sits dead center
        center = (640, 360)
        assert no_button.getpixel(center) != with_button.getpixel(center)


def test_render_thumbnail_raises_fatal_error_when_font_missing(source_image, tmp_path):
    output_path = tmp_path / "thumbnail.jpg"
    missing_font = tmp_path / "does_not_exist.ttf"

    with pytest.raises(FatalError):
        render_thumbnail(source_image, "Hook", output_path, missing_font)


def test_to_thumbnail_display_text_uppercases():
    # Live-reported: the original mixed-case rendering read as visually
    # flat. All-caps is the standard YouTube thumbnail convention for
    # maximum punch and legibility at small sizes.
    assert to_thumbnail_display_text("This Woman Doomed Britain") == "THIS WOMAN DOOMED BRITAIN"


def test_render_thumbnail_text_is_bold_and_large_enough_to_read_at_a_glance(
    source_image, font_path, tmp_path
):
    # Regression test: live-reported the original text as too small/thin
    # to read as an attention-grabbing thumbnail. Pin a floor on both the
    # font size and stroke width (as fractions of frame height) so a
    # future tuning pass can't silently drift back toward flat/small text.
    from essaygen.assembly.thumbnail import _TEXT_FONT_SIZE_FRACTION, _TEXT_STROKE_WIDTH_FRACTION

    assert _TEXT_FONT_SIZE_FRACTION >= 0.11
    assert _TEXT_STROKE_WIDTH_FRACTION >= 0.008
