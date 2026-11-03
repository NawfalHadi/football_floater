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


def _soccer_ball(d, x0, y0, x1, y1, fill, rim, stitch):
    """Simple ball: filled circle + center pentagon hint + seam arcs."""
    d.ellipse((x0, y0, x1, y1), fill=fill, outline=rim, width=1)
    cx = (x0 + x1) / 2
    cy = (y0 + y1) / 2
    r = min(x1 - x0, y1 - y0) / 2
    # center patch
    pr = max(2, r * 0.28)
    d.polygon(
        [
            (cx, cy - pr),
            (cx + pr * 0.95, cy - pr * 0.3),
            (cx + pr * 0.6, cy + pr * 0.8),
            (cx - pr * 0.6, cy + pr * 0.8),
            (cx - pr * 0.95, cy - pr * 0.3),
        ],
        fill=stitch,
    )
    # light seams
    d.arc((x0 + 1, y0 + 1, x1 - 1, y1 - 1), start=20, end=100, fill=stitch, width=1)
    d.arc((x0 + 1, y0 + 1, x1 - 1, y1 - 1), start=200, end=280, fill=stitch, width=1)


@lru_cache(maxsize=64)
def event_icon(kind: str, size: int = 14) -> Image.Image:
    """kind: goal | penalty | assist | yellow | red | sub → RGB image for ImageTk."""
    img = _blank(size)
    d = ImageDraw.Draw(img)
    m = max(1, size // 8)
    kind = (kind or "").lower()
    white = _hex_rgb(TEXT_COLOR)
    green = _hex_rgb(PL_GREEN)
    muted = _hex_rgb(MUTED)
    panel = _hex_rgb(PANEL_BG)

    if kind == "goal":
        _soccer_ball(d, m, m, size - 1 - m, size - 1 - m, white, green, panel)
    elif kind == "penalty":
        _soccer_ball(d, m, m, size - 1 - m, size - 1 - m, white, green, panel)
        # green corner badge with P
        bs = max(6, size // 2)
        bx0, by0 = size - m - bs, size - m - bs
        d.rounded_rectangle((bx0, by0, size - 1 - m, size - 1 - m), radius=2, fill=green)
        f = _font(max(7, bs - 2))
        d.text((bx0 + 1, by0 - 1), "P", fill=panel, font=f)
    elif kind == "assist":
        # chevron pass →
        y = size // 2
        d.line((m + 1, y, size - 4 - m, y), fill=green, width=max(2, size // 8))
        d.polygon(
            [
                (size - 1 - m, y),
                (size - 5 - m, y - 4),
                (size - 5 - m, y + 4),
            ],
            fill=green,
        )
        d.ellipse((m, y - 2, m + 4, y + 2), fill=white)
    elif kind == "sub":
        # green ↑ on / red ↓ off side by side — reads at 16–18px
        mid = size // 2
        # on (left)
        d.polygon([(mid - 4, m + 1), (mid - 7, m + 6), (mid - 1, m + 6)], fill=green)
        d.rectangle((mid - 5, m + 5, mid - 3, size - 2 - m), fill=green)
        # off (right)
        d.polygon(
            [(mid + 4, size - 2 - m), (mid + 1, size - 7 - m), (mid + 7, size - 7 - m)],
            fill=_hex_rgb(DANGER),
        )
        d.rectangle((mid + 3, m + 1, mid + 5, size - 7 - m), fill=_hex_rgb(DANGER))
    elif kind == "yellow":
        # portrait card
        pad = m + 1
        d.rounded_rectangle(
            (pad + 1, m, size - 2 - pad, size - 1 - m),
            radius=2,
            fill=_hex_rgb(CARD_YELLOW),
            outline=white,
            width=1,
        )
        d.line((pad + 3, m + 3, size - 4 - pad, m + 3), fill=panel, width=1)
    elif kind == "red":
        pad = m + 1
        d.rounded_rectangle(
            (pad + 1, m, size - 2 - pad, size - 1 - m),
            radius=2,
            fill=_hex_rgb(DANGER),
            outline=white,
            width=1,
        )
        d.line((pad + 3, m + 3, size - 4 - pad, m + 3), fill=panel, width=1)
    else:
        d.ellipse((m, m, size - 1 - m, size - 1 - m), outline=muted, width=1)
    return img
