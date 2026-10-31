"""Palette + Pillow glass / button drawing (chroma-key safe)."""
from PIL import Image, ImageDraw, ImageFont

from .config import ICON_SIZE

# --- palette ---
CHROMA = "#FF00FF"
PANEL_BG = "#201C25"
PANEL_RIM = "#8E8E93"
BTN_BG = "#2E2A33"
BTN_RIM = "#55505C"
DIVIDER = "#3A3640"
TEXT_COLOR = "#F5F5F7"
MUTED = "#AEAEB2"
PL_PURPLE = "#3D195B"
PL_GREEN = "#00FF85"
PL_PINK = "#E90052"
CARD_YELLOW = "#FFD60A"
DANGER = "#FF6B6B"

def _hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


def _mix(a, b, t):
    return tuple(int(x * (1 - t) + y * t) for x, y in zip(_hex_rgb(a), _hex_rgb(b)))


def _load_ui_font(size=12):
    for name in ("segoeui.ttf", "Segoe UI.ttf", "SF-Pro-Text-Regular.otf", "DejaVuSans.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default()


def make_glass(width, height, radius=None, accent=None):
    if radius is None:
        radius = height // 2 if height <= 64 else 16
    size = (width, height)
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    ImageDraw.Draw(img).rounded_rectangle(
        (0, 0, width - 1, height - 1),
        radius=radius,
        fill=_hex_rgb(PANEL_BG) + (255,),
        outline=_hex_rgb(PANEL_RIM) + (255,),
        width=1,
    )
    hl = Image.new("RGBA", size, (0, 0, 0, 0))
    ImageDraw.Draw(hl).rounded_rectangle(
        (1, 1, width - 2, height - 2), radius=max(1, radius - 1), outline=(255, 255, 255, 70), width=1
    )
    top = Image.new("L", size, 0)
    ImageDraw.Draw(top).rectangle((0, 0, width, max(4, height // 3)), fill=255)
    hl.putalpha(Image.composite(hl.getchannel("A"), Image.new("L", size, 0), top))
    img = Image.alpha_composite(img, hl)
    if accent:
        ImageDraw.Draw(img).ellipse(
            (12, height // 2 - 3, 18, height // 2 + 3), fill=_hex_rgb(accent) + (255,)
        )
    result = Image.new("RGB", size, _hex_rgb(CHROMA))
    result.paste(img.convert("RGB"), mask=img.getchannel("A").point(lambda a: 255 if a > 128 else 0))
    return result


BUTTON_STYLES = {
    "default": (BTN_BG, BTN_RIM, TEXT_COLOR),
    "muted": (BTN_BG, BTN_RIM, MUTED),
    "danger": ("#3A1F24", "#7A3A40", DANGER),
    "on": ("#163326", PL_GREEN, PL_GREEN),
    "busy": (BTN_BG, CARD_YELLOW, CARD_YELLOW),
}


def make_button(label, kind="default", hover=False, min_w=0, height=28, pad_x=14):
    fill, rim, text = BUTTON_STYLES[kind]
    fill_rgb = _mix(fill, "#FFFFFF", 0.10) if hover else _hex_rgb(fill)
    font = _load_ui_font(12 if height >= 28 else 11)
    bbox = ImageDraw.Draw(Image.new("RGB", (1, 1))).textbbox((0, 0), label, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    width = max(min_w, tw + pad_x * 2)
    img = Image.new("RGB", (width, height), _hex_rgb(PANEL_BG))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle(
        (0, 0, width - 1, height - 1), radius=height // 2, fill=fill_rgb, outline=_hex_rgb(rim), width=1
    )
    d.text(
        ((width - tw) / 2 - bbox[0], (height - th) / 2 - bbox[1]),
        label,
        fill=_hex_rgb(text),
        font=font,
    )
    return img


def make_circle_icon(im, size=ICON_SIZE):
    im = im.convert("RGBA").resize((size, size), Image.Resampling.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(im, (0, 0), mask)
    bg = Image.new("RGBA", (size, size), _hex_rgb(PANEL_BG) + (255,))
    return Image.alpha_composite(bg, out).convert("RGB")

