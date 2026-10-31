"""Palette + Pillow glass / button drawing (chroma-key safe)."""
import sys

from PIL import Image, ImageDraw, ImageFont

from .config import ICON_SIZE

# Chroma key never changes — windows punch this color out.
CHROMA = "#FF00FF"

# Current look, frozen as the saved default.
_DEFAULT = {
    "PANEL_BG": "#201C25",
    "PANEL_RIM": "#8E8E93",
    "BTN_BG": "#2E2A33",
    "BTN_RIM": "#55505C",
    "DIVIDER": "#3A3640",
    "TEXT_COLOR": "#F5F5F7",
    "MUTED": "#AEAEB2",
    "PL_PURPLE": "#3D195B",
    "PL_GREEN": "#00FF85",
    "PL_PINK": "#E90052",
    "CLOCK_LIVE": "#FF7EB6",
    "CARD_YELLOW": "#FFD60A",
    "DANGER": "#FF6B6B",
    "ICON_BADGE": "#E8E8ED",
    "ICON_BADGE_RIM": "#8E8E93",
}

# Scorebug for watching PL + Bundesliga.
# Dark panel (opaque) so grass / purple boards / red boards don't eat the text.
# Light rim so the capsule still separates from all three.
# White-ish type, mint live clock, PL green goals, Bundesliga red only on cards.
_EXPERIMENTAL = {
    "PANEL_BG": "#16121C",
    "PANEL_RIM": "#E4E4E8",
    "BTN_BG": "#241E2C",
    "BTN_RIM": "#6E6578",
    "DIVIDER": "#3A3344",
    "TEXT_COLOR": "#F4F1F8",
    "MUTED": "#C2B8CC",
    "PL_PURPLE": "#3D195B",
    "PL_GREEN": "#3DFF9A",
    "PL_PINK": "#E90052",
    "CLOCK_LIVE": "#B8FFD4",
    "CARD_YELLOW": "#FFD60A",
    "DANGER": "#E10600",
    "ICON_BADGE": "#F2F2F4",
    "ICON_BADGE_RIM": "#C8C8CE",
}

THEMES = {
    "default": {"label": "Default", "colors": _DEFAULT},
    "experimental": {
        "label": "Experimental — PL × Bundesliga",
        "colors": _EXPERIMENTAL,
    },
}
ACTIVE = "default"

PANEL_BG = _DEFAULT["PANEL_BG"]
PANEL_RIM = _DEFAULT["PANEL_RIM"]
BTN_BG = _DEFAULT["BTN_BG"]
BTN_RIM = _DEFAULT["BTN_RIM"]
DIVIDER = _DEFAULT["DIVIDER"]
TEXT_COLOR = _DEFAULT["TEXT_COLOR"]
MUTED = _DEFAULT["MUTED"]
PL_PURPLE = _DEFAULT["PL_PURPLE"]
PL_GREEN = _DEFAULT["PL_GREEN"]
PL_PINK = _DEFAULT["PL_PINK"]
CLOCK_LIVE = _DEFAULT["CLOCK_LIVE"]
CARD_YELLOW = _DEFAULT["CARD_YELLOW"]
DANGER = _DEFAULT["DANGER"]
ICON_BADGE = _DEFAULT["ICON_BADGE"]
ICON_BADGE_RIM = _DEFAULT["ICON_BADGE_RIM"]

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


def _button_styles():
    # Default keeps the current dock colors. Experimental stays soft,
    # just tinted so each action is still distinct on a match broadcast.
    if ACTIVE != "experimental":
        return {
            "default": (BTN_BG, BTN_RIM, TEXT_COLOR),
            "muted": (BTN_BG, BTN_RIM, MUTED),
            "danger": ("#3A1F24", "#7A3A40", DANGER),
            "on": ("#163326", PL_GREEN, PL_GREEN),
            "busy": ("#3A3018", "#8A7030", CARD_YELLOW),
            "refresh": ("#1A2838", "#4A7098", "#8EC5FF"),
            "test": ("#3A3018", "#8A7030", CARD_YELLOW),
            "settings": ("#2A2040", "#6A5088", "#C4B5FD"),
            "hidden": ("#242028", BTN_RIM, MUTED),
        }
    return {
        "default": (BTN_BG, BTN_RIM, TEXT_COLOR),
        "muted": (BTN_BG, BTN_RIM, MUTED),
        "danger": ("#3A1820", "#E10600", "#FFD5D8"),
        "on": ("#123024", PL_GREEN, "#E7FFF3"),
        "busy": ("#332C14", "#C9A227", "#FFF3C4"),
        "refresh": ("#162433", "#5B8FC4", "#E4F1FF"),
        "test": ("#332C14", "#C9A227", "#FFF3C4"),
        "settings": ("#2A1840", PL_PURPLE, "#F0E6FF"),
        "hidden": (BTN_BG, BTN_RIM, MUTED),
    }


BUTTON_STYLES = _button_styles()


def apply_theme(name):
    """Switch palette. Patches modules that did `from theme import COLOR`."""
    global ACTIVE, BUTTON_STYLES
    global PANEL_BG, PANEL_RIM, BTN_BG, BTN_RIM, DIVIDER, TEXT_COLOR, MUTED
    global PL_PURPLE, PL_GREEN, PL_PINK, CLOCK_LIVE, CARD_YELLOW, DANGER
    global ICON_BADGE, ICON_BADGE_RIM

    if name not in THEMES:
        name = "default"
    colors = THEMES[name]["colors"]
    ACTIVE = name
    g = globals()
    for key, value in colors.items():
        g[key] = value
    BUTTON_STYLES = _button_styles()

    for mod in list(sys.modules.values()):
        if mod is None:
            continue
        mod_name = getattr(mod, "__name__", "") or ""
        if not mod_name.startswith("football_floater"):
            continue
        if mod is sys.modules.get(__name__):
            continue
        bag = getattr(mod, "__dict__", None)
        if not isinstance(bag, dict):
            continue
        for key, value in colors.items():
            if key in bag:
                bag[key] = value
    try:
        from .icons import event_icon

        event_icon.cache_clear()
    except Exception:
        pass
    return name


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
    """Crest on a light circular badge — dark kits stay visible on PANEL_BG."""
    pad = max(1, size // 10)
    inner = max(8, size - pad * 2)
    im = im.convert("RGBA").resize((inner, inner), Image.Resampling.LANCZOS)

    badge = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(badge).ellipse(
        (0, 0, size - 1, size - 1),
        fill=_hex_rgb(ICON_BADGE) + (255,),
        outline=_hex_rgb(ICON_BADGE_RIM) + (255,),
        width=1,
    )

    mask = Image.new("L", (inner, inner), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, inner - 1, inner - 1), fill=255)
    logo = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    logo.paste(im, (pad, pad), mask)
    return Image.alpha_composite(badge, logo).convert("RGB")

