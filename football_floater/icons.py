"""Small event glyphs (chroma-key safe — opaque RGB on PANEL_BG)."""
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont

from .theme import CARD_YELLOW, DANGER, MUTED, PANEL_BG, PL_GREEN, TEXT_COLOR, _hex_rgb


def _font(size):
    for name in ("segoeui.ttf", "Segoe UI.ttf", "DejaVuSans-Bold.ttf", "DejaVuSans.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _blank(size):
    return Image.new("RGB", (size, size), _hex_rgb(PANEL_BG))


@lru_cache(maxsize=64)
def event_icon(kind: str, size: int = 14) -> Image.Image:
    """kind: goal | penalty | assist | yellow | red → RGB image for ImageTk."""
    img = _blank(size)
    d = ImageDraw.Draw(img)
    m = max(1, size // 8)
    kind = (kind or "").lower()

    if kind == "goal":
        d.ellipse(
            (m, m, size - 1 - m, size - 1 - m),
            fill=_hex_rgb(TEXT_COLOR),
            outline=_hex_rgb(PL_GREEN),
            width=1,
        )
        cx = cy = size // 2
        d.ellipse((cx - 1, cy - 1, cx + 1, cy + 1), fill=_hex_rgb(PANEL_BG))
    elif kind == "penalty":
        d.ellipse(
            (m, m, size - 1 - m, size - 1 - m),
            fill=_hex_rgb(TEXT_COLOR),
            outline=_hex_rgb(PL_GREEN),
            width=1,
        )
        f = _font(max(7, size - 5))
        bx0, by0 = size - m - 7, size - m - 7
        d.rectangle((bx0, by0, size - 1 - m, size - 1 - m), fill=_hex_rgb(PL_GREEN))
        d.text((bx0 + 1, by0 - 1), "P", fill=_hex_rgb(PANEL_BG), font=f)
    elif kind == "assist":
        # pass arrow
        d.polygon(
            [(m, size // 2), (size // 2 + 1, m + 1), (size // 2 + 1, size - 2 - m)],
            fill=_hex_rgb(MUTED),
        )
        d.line((size // 2, size // 2, size - 1 - m, size // 2), fill=_hex_rgb(PL_GREEN), width=2)
        d.polygon(
            [
                (size - 1 - m, size // 2),
                (size - 4 - m, size // 2 - 3),
                (size - 4 - m, size // 2 + 3),
            ],
            fill=_hex_rgb(PL_GREEN),
        )
    elif kind == "sub":
        # up arrow (on) and down arrow (off), readable at 16px
        cx = size // 2
        d.polygon([(cx, m), (cx - 3, m + 5), (cx + 3, m + 5)], fill=_hex_rgb(TEXT_COLOR))
        d.polygon(
            [(cx, size - 1 - m), (cx - 3, size - 6 - m), (cx + 3, size - 6 - m)],
            fill=_hex_rgb(MUTED),
        )
        d.line((cx, m + 4, cx, size - 5 - m), fill=_hex_rgb(TEXT_COLOR), width=1)
    elif kind == "yellow":
        d.rounded_rectangle(
            (m + 1, m, size - 2 - m, size - 1 - m),
            radius=2,
            fill=_hex_rgb(CARD_YELLOW),
            outline=_hex_rgb(TEXT_COLOR),
            width=1,
        )
    elif kind == "red":
        d.rounded_rectangle(
            (m + 1, m, size - 2 - m, size - 1 - m),
            radius=2,
            fill=_hex_rgb(DANGER),
            outline=_hex_rgb(TEXT_COLOR),
            width=1,
        )
    else:
        d.ellipse((m, m, size - 1 - m, size - 1 - m), outline=_hex_rgb(MUTED), width=1)
    return img
