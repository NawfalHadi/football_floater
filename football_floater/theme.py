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

# macOS / visionOS material: cool frosted charcoal, hairline light rim,
# system blue/cyan/green/red. Opaque fill — chroma key cannot blur the pitch.
_GLASS = {
    "PANEL_BG": "#2C2C2E",
    "PANEL_RIM": "#EBEBF0",
    "BTN_BG": "#3A3A3C",
    "BTN_RIM": "#636366",
    "DIVIDER": "#48484A",
    "TEXT_COLOR": "#F5F5F7",
    "MUTED": "#D1D1D6",
    "PL_PURPLE": "#5E5CE6",
    "PL_GREEN": "#30D158",
    "PL_PINK": "#FF375F",
    "CLOCK_LIVE": "#64D2FF",
    "CARD_YELLOW": "#FFD60A",
    "DANGER": "#FF453A",
    "ICON_BADGE": "#F5F5F7",
    "ICON_BADGE_RIM": "#D1D1D6",
}

THEMES = {
    "default": {"label": "Default", "colors": _DEFAULT, "sheen": 70},
    "experimental": {
        "label": "Experimental — PL × Bundesliga",
        "colors": _EXPERIMENTAL,
        "sheen": 70,
    },
    "glass": {"label": "Glass — macOS", "colors": _GLASS, "sheen": 150},
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
GLASS_SHEEN = 70

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
        (1, 1, width - 2, height - 2),
        radius=max(1, radius - 1),
        outline=(255, 255, 255, GLASS_SHEEN),
        width=1,
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
    if ACTIVE == "glass":
        return {
            "default": (BTN_BG, "#8E8E93", TEXT_COLOR),
            "muted": (BTN_BG, BTN_RIM, MUTED),
            "danger": ("#3A2024", "#FF453A", "#FFD6D3"),
            "on": ("#14301E", "#30D158", "#E5FFEE"),
            "busy": ("#3A3014", "#FFD60A", "#FFF6CC"),
            "refresh": ("#12304A", "#0A84FF", "#D6ECFF"),
            "test": ("#3A2A14", "#FF9F0A", "#FFE7C2"),
            "settings": ("#24244A", "#5E5CE6", "#E8E7FF"),
            "hidden": (BTN_BG, BTN_RIM, MUTED),
        }
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
    global ACTIVE, BUTTON_STYLES, GLASS_SHEEN
    global PANEL_BG, PANEL_RIM, BTN_BG, BTN_RIM, DIVIDER, TEXT_COLOR, MUTED
    global PL_PURPLE, PL_GREEN, PL_PINK, CLOCK_LIVE, CARD_YELLOW, DANGER
    global ICON_BADGE, ICON_BADGE_RIM

    if name not in THEMES:
        name = "default"
    colors = THEMES[name]["colors"]
    ACTIVE = name
    GLASS_SHEEN = int(THEMES[name].get("sheen", 70))
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


def _draw_glyph(d, name, box, color):
    """Tiny vector icon. Unicode glyphs are missing in Segoe/DejaVu and draw as empty boxes."""
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    name = name or ""
    if name == "refresh":
        d.arc((x0, y0, x1, y1), start=40, end=300, fill=color, width=2)
        d.polygon([(x1 - 2, cy - 1), (x1 - 6, cy + 3), (x1 + 1, cy + 3)], fill=color)
    elif name == "ball":
        d.ellipse((x0, y0, x1, y1), outline=color, width=2)
        d.line((cx, y0 + 1, cx, y1 - 1), fill=color, width=1)
        d.line((x0 + 1, cy, x1 - 1, cy), fill=color, width=1)
    elif name == "float":
        d.rounded_rectangle((x0, y0 + 1, x1, cy - 1), radius=2, outline=color, width=1)
        d.rounded_rectangle((x0, cy + 1, x1, y1 - 1), radius=2, outline=color, width=1)
    elif name == "hidden":
        d.ellipse((x0, y0 + 2, x1, y1 - 2), outline=color, width=1)
        d.line((x0, y1, x1, y0), fill=color, width=2)
    elif name == "gear":
        d.ellipse((x0 + 2, y0 + 2, x1 - 2, y1 - 2), outline=color, width=2)
        d.ellipse((cx - 1, cy - 1, cx + 2, cy + 2), fill=color)
        d.line((cx, y0, cx, y0 + 3), fill=color, width=2)
        d.line((cx, y1 - 3, cx, y1), fill=color, width=2)
        d.line((x0, cy, x0 + 3, cy), fill=color, width=2)
        d.line((x1 - 3, cy, x1, cy), fill=color, width=2)
    elif name == "mini":
        d.line((x0 + 1, cy, x1 - 1, cy), fill=color, width=2)
    elif name == "expand":
        d.rounded_rectangle((x0 + 1, y0 + 1, x1 - 1, y1 - 1), radius=2, outline=color, width=2)
    elif name == "quit":
        d.line((x0 + 1, y0 + 1, x1 - 1, y1 - 1), fill=color, width=2)
        d.line((x0 + 1, y1 - 1, x1 - 1, y0 + 1), fill=color, width=2)


def make_button(label, kind="default", hover=False, min_w=0, height=28, pad_x=14, icon=None):
    fill, rim, text = BUTTON_STYLES[kind]
    fill_rgb = _mix(fill, "#FFFFFF", 0.10) if hover else _hex_rgb(fill)
    font = _load_ui_font(12 if height >= 28 else 11)
    draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    bbox = draw.textbbox((0, 0), label or "", font=font) if label else (0, 0, 0, 0)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    glyph = max(10, height - 14) if icon else 0
    gap = 6 if icon and label else 0
    width = max(min_w, tw + glyph + gap + pad_x * 2)
    img = Image.new("RGB", (width, height), _hex_rgb(PANEL_BG))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle(
        (0, 0, width - 1, height - 1), radius=height // 2, fill=fill_rgb, outline=_hex_rgb(rim), width=1
    )
    content = tw + glyph + gap
    left = (width - content) / 2
    if icon:
        gy = (height - glyph) / 2
        _draw_glyph(d, icon, (left, gy, left + glyph, gy + glyph), _hex_rgb(text))
        left += glyph + gap
    if label:
        d.text((left - bbox[0], (height - th) / 2 - bbox[1]), label, fill=_hex_rgb(text), font=font)
    return img


def make_circle_icon(im, size=ICON_SIZE):
    """Circular crest on the panel color. No light disc."""
    im = im.convert("RGBA").resize((size, size), Image.Resampling.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(im, (0, 0), mask)
    bg = Image.new("RGBA", (size, size), _hex_rgb(PANEL_BG) + (255,))
    return Image.alpha_composite(bg, out).convert("RGB")

