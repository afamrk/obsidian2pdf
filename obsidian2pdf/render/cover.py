"""Cover page: the exported folder/note name as a typographic title page,
plus a matching cover *image* for readers/library views that show a
thumbnail (e.g. Kobo's home screen) rather than rendering the EPUB's cover
XHTML page.
"""
from __future__ import annotations

import html
import io
from datetime import date

from PIL import Image, ImageDraw, ImageFont

SUBTITLE = "Obsidian"

_IMAGE_SIZE = (1600, 2400)
_TITLE_FONT_SIZE = 150
_SUBTITLE_FONT_SIZE = 88
_DATE_FONT_SIZE = 64
_TITLE_Y_FRACTION = 0.40
_SUBTITLE_GAP_PX = 190
_DATE_GAP_PX = 330


def cover_html(title: str) -> str:
    return (
        '<section class="cover">'
        f'<div class="cover-title">{html.escape(title)}</div>'
        f'<div class="cover-subtitle">{html.escape(SUBTITLE)}</div>'
        f'<div class="cover-date">{date.today():%B %d, %Y}</div>'
        "</section>\n"
    )


def cover_image(title: str) -> bytes:
    """A plain white cover image with the title, an "Obsidian" subtitle,
    and today's date, encoded as PNG bytes. Used for the EPUB's registered
    cover-image (see writer/epub.py) so library/shelf views show a real
    thumbnail instead of a blank placeholder — the cover *page* alone
    isn't enough, since that's only ever seen inside the reading flow."""
    width, height = _IMAGE_SIZE
    image = Image.new("RGB", (width, height), "#ffffff")
    draw = ImageDraw.Draw(image)
    title_font = ImageFont.load_default(size=_TITLE_FONT_SIZE)
    subtitle_font = ImageFont.load_default(size=_SUBTITLE_FONT_SIZE)
    date_font = ImageFont.load_default(size=_DATE_FONT_SIZE)

    def centered_text(text: str, font: ImageFont.FreeTypeFont, y: float) -> None:
        left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
        draw.text(((width - (right - left)) / 2, y), text, font=font, fill="#111111")

    title_y = height * _TITLE_Y_FRACTION
    centered_text(title, title_font, title_y)
    centered_text(SUBTITLE, subtitle_font, title_y + _SUBTITLE_GAP_PX)
    centered_text(
        f"{date.today():%B %d, %Y}", date_font, title_y + _DATE_GAP_PX
    )

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
