#!/usr/bin/env python3
"""
Render README screenshots with the same glass theme (no live ESPN required).
Run inside roblox-bot or any env with Pillow:

  python3 scripts/capture_screenshots.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from football_floater.theme import (  # noqa: E402
    CARD_YELLOW,
    CLOCK_LIVE,
    DIVIDER,
    MUTED,
    PANEL_BG,
    PL_GREEN,
    TEXT_COLOR,
    apply_theme,
    make_glass,
    make_speech_glass,
    set_solid_mode,
    speech_outer_size,
)


OUT = ROOT / "docs" / "screenshots"
W, H = 1400, 780
PITCH = (18, 72, 42)  # dark grass stand-in


def _font(size: int, bold: bool = False):
    names = (
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
        "segoeui.ttf",
        "arial.ttf",
    )
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def canvas() -> Image.Image:
    img = Image.new("RGB", (W, H), PITCH)
    d = ImageDraw.Draw(img)
    # subtle pitch lines
    for y in range(80, H, 48):
        d.line((0, y, W, y), fill=(22, 88, 52), width=1)
    d.ellipse((W // 2 - 90, H // 2 - 90, W // 2 + 90, H // 2 + 90), outline=(28, 110, 64), width=2)
    return img


def paste_glass(base: Image.Image, glass: Image.Image, xy: tuple[int, int]):
    base.paste(glass, xy)


def draw_match_chip(d: ImageDraw.ImageDraw, x: int, y: int, home: str, away: str, score: str, clock: str, clock_fg):
    f_tla = _font(11, True)
    f_score = _font(14, True)
    f_clk = _font(10, True)
    d.text((x, y + 8), home, fill=TEXT_COLOR, font=f_tla)
    d.text((x + 48, y + 4), score, fill=TEXT_COLOR, font=f_score)
    d.text((x + 48, y + 24), clock, fill=clock_fg, font=f_clk)
    d.text((x + 110, y + 8), away, fill=TEXT_COLOR, font=f_tla)


def shot_ticker():
    img = canvas()
    glass = make_glass(720, 56)
    x, y = (W - 720) // 2, 90
    paste_glass(img, glass, (x, y))
    d = ImageDraw.Draw(img)
    chip_x = x + 40
    draw_match_chip(d, chip_x, y + 8, "ARS", "CHE", "2 - 1", "64'", CLOCK_LIVE)
    d.line((chip_x + 160, y + 12, chip_x + 160, y + 44), fill=DIVIDER, width=1)
    draw_match_chip(d, chip_x + 176, y + 8, "MCI", "LIV", "0 - 0", "12'", CLOCK_LIVE)
    d.line((chip_x + 336, y + 12, chip_x + 336, y + 44), fill=DIVIDER, width=1)
    draw_match_chip(d, chip_x + 352, y + 8, "BAY", "DOR", "1 - 1", "KO in 0:42:00", PL_GREEN)
    # dock
    dock = make_glass(420, 44)
    paste_glass(img, dock, ((W - 420) // 2, y + 56 + 12))
    d = ImageDraw.Draw(img)
    d.text(((W - 420) // 2 + 24, y + 56 + 24), "Live   Refresh   Settings   Hide   Quit", fill=TEXT_COLOR, font=_font(12, True))
    img.save(OUT / "01-ticker.png")
    # Dock-focused crop for 02
    dock_y = y + 56 + 12
    crop = img.crop((W // 2 - 280, dock_y - 40, W // 2 + 280, dock_y + 100))
    pad = Image.new("RGB", (W, H), PITCH)
    pad.paste(crop, ((W - crop.size[0]) // 2, (H - crop.size[1]) // 2))
    pad.save(OUT / "02-dock.png")


def shot_settings():
    img = canvas()
    panel = make_glass(400, 420, radius=16)
    x, y = (W - 400) // 2, (H - 420) // 2
    paste_glass(img, panel, (x, y))
    d = ImageDraw.Draw(img)
    d.text((x + 28, y + 24), "What do you want to watch?", fill=TEXT_COLOR, font=_font(14, True))
    d.text((x + 28, y + 56), "Pick leagues and which screen owns the overlay.", fill=MUTED, font=_font(10))
    d.text((x + 28, y + 96), "LEAGUES", fill=MUTED, font=_font(9, True))
    for i, name in enumerate(
        ("●  Premier League", "●  Bundesliga", "●  La Liga", "●  UEFA Champions League")
    ):
        d.text((x + 28, y + 118 + i * 28), name, fill=TEXT_COLOR, font=_font(12))
    d.text((x + 28, y + 248), "DISPLAY", fill=MUTED, font=_font(9, True))
    d.text((x + 28, y + 270), "●  Display 1 — Primary", fill=TEXT_COLOR, font=_font(12))
    d.text((x + 28, y + 318), "○  Don't ask next time", fill=MUTED, font=_font(11))
    btn = make_glass(96, 36)
    paste_glass(img, btn, (x + 280, y + 360))
    d.text((x + 308, y + 370), "Start", fill=PL_GREEN, font=_font(12, True))
    img.save(OUT / "03-settings.png")


def shot_float_pills():
    img = canvas()
    d = ImageDraw.Draw(img)
    pills = [
        (980, 420, "ARS", "CHE", "2 - 1", "64'"),
        (980, 490, "MCI", "LIV", "0 - 0", "12'"),
        (980, 560, "BAY", "DOR", "1 - 1", "FT"),
    ]
    for x, y, h, a, sc, clk in pills:
        g = make_glass(168, 58)
        paste_glass(img, g, (x, y))
        fg = MUTED if clk == "FT" else CLOCK_LIVE
        draw_match_chip(ImageDraw.Draw(img), x + 18, y + 8, h, a, sc, clk, fg)
    dock = make_glass(520, 44)
    paste_glass(img, dock, (40, 40))
    ImageDraw.Draw(img).text(
        (64, 52),
        "Live   Refresh   Show hidden 0   Reset layout   Settings   Hide   Quit",
        fill=TEXT_COLOR,
        font=_font(11, True),
    )
    img.save(OUT / "04-float-pills.png")


def shot_float_toast():
    img = canvas()
    pill = make_glass(168, 58)
    px, py = 900, 360
    paste_glass(img, pill, (px, py))
    draw_match_chip(ImageDraw.Draw(img), px + 18, py + 8, "ARS", "CHE", "2 - 1", "64'", CLOCK_LIVE)
    body_w, body_h = 180, 48
    toast = make_speech_glass(body_w, body_h, tail="bottom")
    tw, th = speech_outer_size(body_w, body_h, "bottom")
    tx, ty = px - 8, py - th - 8
    paste_glass(img, toast, (tx, ty))
    d = ImageDraw.Draw(img)
    d.text((tx + 20, ty + 10), "GOAL", fill=PL_GREEN, font=_font(9, True))
    d.text((tx + 20, ty + 24), "Saka 64'", fill=TEXT_COLOR, font=_font(12, True))
    img.save(OUT / "05-float-toast.png")


def shot_ticker_toast():
    img = canvas()
    glass = make_glass(720, 56)
    x, y = (W - 720) // 2, 160
    # toast above bar
    toast = make_glass(200, 44)
    paste_glass(img, toast, (x + 80, y - 52))
    d = ImageDraw.Draw(img)
    d.text((x + 96, y - 42), "GOAL  Haaland 12'", fill=TEXT_COLOR, font=_font(12, True))
    paste_glass(img, glass, (x, y))
    draw_match_chip(d, x + 40, y + 8, "MCI", "LIV", "1 - 0", "12'", CLOCK_LIVE)
    d.line((x + 200, y + 12, x + 200, y + 44), fill=DIVIDER, width=1)
    draw_match_chip(d, x + 216, y + 8, "ARS", "CHE", "2 - 1", "64'", CLOCK_LIVE)
    img.save(OUT / "06-ticker-toast.png")


def shot_timeline():
    img = canvas()
    panel = make_glass(260, 320, radius=16)
    x, y = 200, 180
    paste_glass(img, panel, (x, y))
    d = ImageDraw.Draw(img)
    d.text((x + 24, y + 20), "ARS  2 - 1  CHE", fill=TEXT_COLOR, font=_font(14, True))
    d.text((x + 24, y + 44), "64'", fill=CLOCK_LIVE, font=_font(11, True))
    d.line((x + 24, y + 68, x + 236, y + 68), fill=DIVIDER, width=1)
    rows = [
        (88, "Saka", "GOAL", True),
        (55, "Palmer", "GOAL", False),
        (41, "Rice", "YELLOW", True),
        (22, "Havertz", "GOAL", True),
    ]
    yy = y + 84
    for minute, player, tag, home in rows:
        color = PL_GREEN if tag == "GOAL" else CARD_YELLOW
        if home:
            d.text((x + 24, yy), f"{player}", fill=TEXT_COLOR, font=_font(11))
            d.text((x + 118, yy), f"{minute}'", fill=MUTED, font=_font(10, True))
            d.text((x + 24, yy + 14), tag, fill=color, font=_font(9, True))
        else:
            d.text((x + 150, yy), f"{player}", fill=TEXT_COLOR, font=_font(11))
            d.text((x + 118, yy), f"{minute}'", fill=MUTED, font=_font(10, True))
            d.text((x + 150, yy + 14), tag, fill=color, font=_font(9, True))
        yy += 48
    # pill hint
    pill = make_glass(168, 58)
    paste_glass(img, pill, (900, 300))
    draw_match_chip(ImageDraw.Draw(img), 918, 308, "ARS", "CHE", "2 - 1", "64'", CLOCK_LIVE)
    img.save(OUT / "07-timeline.png")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    apply_theme("default")
    set_solid_mode(True)  # solid outside fill for readable PNG edges
    shot_ticker()
    shot_settings()
    shot_float_pills()
    shot_float_toast()
    shot_ticker_toast()
    shot_timeline()
    print(f"Wrote screenshots to {OUT}")


if __name__ == "__main__":
    main()
