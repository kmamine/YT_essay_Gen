from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from essaygen.core.errors import FatalError
from essaygen.providers.llm.parsing import extract_json_object

_DEFAULT_WIDTH = 1280
_DEFAULT_HEIGHT = 720

# Gradient scrim over the bottom half of the frame, so bold text stays
# legible regardless of what's underneath -- classic YouTube thumbnail
# convention. Not full black (255 alpha) so the image is still visible
# through it, just darkened.
_GRADIENT_HEIGHT_FRACTION = 0.5
_GRADIENT_MAX_ALPHA = 190

_TEXT_FONT_SIZE_FRACTION = 0.09
_TEXT_STROKE_WIDTH_FRACTION = 0.006
_TEXT_MARGIN_FRACTION = 0.06

# Only drawn when play_button=True (e.g. embedding as a static link on a
# platform with no native player chrome, like a GitHub README). YouTube
# itself already overlays a play button on thumbnails in feeds, so the
# pipeline's own generated thumbnails leave this off by default.
_PLAY_BUTTON_RADIUS_FRACTION = 0.12


def build_thumbnail_hook_prompt(title: str, thesis: str) -> str:
    return (
        f'A video essay titled "{title}" argues: "{thesis}"\n\n'
        "Generate a short, punchy YouTube thumbnail hook -- 3-6 words, "
        "attention-grabbing, readable at a glance in a crowded feed. This "
        "is different from the video's actual title; it should tease the "
        "core claim or a provocative angle, not restate the title "
        'verbatim. Respond ONLY with JSON matching this shape: '
        '{"hook": "<3-6 word hook>"}'
    )


def parse_thumbnail_hook_response(raw: str) -> str:
    return extract_json_object(raw)["hook"]


def _cover_crop(img: Image.Image, width: int, height: int) -> Image.Image:
    src_ratio = img.width / img.height
    target_ratio = width / height
    if src_ratio > target_ratio:
        new_height = height
        new_width = round(height * src_ratio)
    else:
        new_width = width
        new_height = round(width / src_ratio)
    resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
    left = (new_width - width) // 2
    top = (new_height - height) // 2
    return resized.crop((left, top, left + width, top + height))


def _build_bottom_gradient(width: int, height: int) -> Image.Image:
    gradient_height = int(height * _GRADIENT_HEIGHT_FRACTION)
    # linear_gradient("L") is black (0) at top, white (255) at bottom;
    # resizing stretches it across the target region -- vectorized, no
    # per-pixel Python loop.
    mask = Image.linear_gradient("L").resize((width, gradient_height))
    mask = mask.point(lambda v: int(v / 255 * _GRADIENT_MAX_ALPHA))
    black = Image.new("RGBA", (width, gradient_height), (0, 0, 0, 255))
    black.putalpha(mask)
    full = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    full.paste(black, (0, height - gradient_height))
    return full


def _wrap_text(
    text: str, font: ImageFont.FreeTypeFont, max_width: int, draw: ImageDraw.ImageDraw
) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if not current or draw.textlength(candidate, font=font) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _draw_play_button(canvas: Image.Image, width: int, height: int) -> Image.Image:
    radius = int(height * _PLAY_BUTTON_RADIUS_FRACTION)
    cx, cy = width // 2, height // 2
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=(255, 255, 255, 210))
    tri_half = radius * 0.35
    tri_reach = radius * 0.5
    triangle = [
        (cx - tri_half, cy - tri_reach),
        (cx - tri_half, cy + tri_reach),
        (cx + tri_reach, cy),
    ]
    draw.polygon(triangle, fill=(20, 20, 20, 255))
    return Image.alpha_composite(canvas.convert("RGBA"), overlay).convert("RGB")


def render_thumbnail(
    image_path: Path,
    hook_text: str,
    output_path: Path,
    font_path: Path,
    width: int = _DEFAULT_WIDTH,
    height: int = _DEFAULT_HEIGHT,
    play_button: bool = False,
) -> None:
    if not font_path.exists():
        raise FatalError(f"thumbnail font not found: {font_path}")

    with Image.open(image_path) as src:
        canvas = _cover_crop(src.convert("RGB"), width, height)

    canvas = Image.alpha_composite(
        canvas.convert("RGBA"), _build_bottom_gradient(width, height)
    ).convert("RGB")

    if play_button:
        canvas = _draw_play_button(canvas, width, height)

    draw = ImageDraw.Draw(canvas)
    font_size = int(height * _TEXT_FONT_SIZE_FRACTION)
    font = ImageFont.truetype(str(font_path), font_size)
    stroke_width = max(1, int(height * _TEXT_STROKE_WIDTH_FRACTION))
    margin = int(width * _TEXT_MARGIN_FRACTION)
    lines = _wrap_text(hook_text, font, width - 2 * margin, draw)

    line_height = font_size + stroke_width * 2 + 6
    total_text_height = line_height * len(lines)
    y = height - int(height * _TEXT_MARGIN_FRACTION) - total_text_height
    for line in lines:
        line_width = draw.textlength(line, font=font)
        x = (width - line_width) / 2
        draw.text(
            (x, y),
            line,
            font=font,
            fill=(255, 255, 255),
            stroke_width=stroke_width,
            stroke_fill=(0, 0, 0),
        )
        y += line_height

    canvas.save(output_path, quality=90)
