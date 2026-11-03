"""Tk overlay window helpers — Windows chroma first; Linux solid glass fallback."""
import os
import sys
import tkinter as tk

from .config import WINDOW_ALPHA
from .theme import CHROMA, CLOCK_LIVE, MUTED, PANEL_BG, PL_GREEN, key_color, set_solid_mode


def setup_overlay(win, alpha=WINDOW_ALPHA):
    """
    Always-on-top undecorated overlay.

    Windows: punch CHROMA via -transparentcolor (stream / chroma-key friendly).
    Linux / macOS / failed chroma: solid PANEL_BG — no magenta holes.
    Set FOOTBALL_FLOATER_FORCE_SOLID=1 to force solid panels anywhere.
    """
    win.overrideredirect(True)
    win.wm_attributes("-topmost", True)
    try:
        win.wm_attributes("-alpha", alpha)
    except tk.TclError:
        pass

    force_solid = os.environ.get("FOOTBALL_FLOATER_FORCE_SOLID", "").strip() in ("1", "true", "yes")
    # Windows is the gold path. Elsewhere prefer solid panels that still look intentional.
    use_chroma = sys.platform == "win32" and not force_solid
    if use_chroma:
        win.configure(bg=CHROMA)
        try:
            win.wm_attributes("-transparentcolor", CHROMA)
            set_solid_mode(False)
            return
        except tk.TclError:
            use_chroma = False

    set_solid_mode(True)
    win.configure(bg=PANEL_BG)


def window_fill():
    """Bg for Labels/Frames that sit in the punch-out / solid fill area."""
    return key_color()


def clock_color(t):
    if t == "FT":
        return MUTED
    if ":" in t:
        return PL_GREEN
    return CLOCK_LIVE
