"""Tk overlay window helpers."""
import tkinter as tk

from .config import WINDOW_ALPHA
from .theme import CHROMA, MUTED, PL_GREEN, PL_PINK


def setup_overlay(win, alpha=WINDOW_ALPHA):
    win.overrideredirect(True)
    win.wm_attributes("-topmost", True)
    try:
        win.wm_attributes("-alpha", alpha)
    except tk.TclError:
        pass
    win.configure(bg=CHROMA)
    try:
        win.wm_attributes("-transparentcolor", CHROMA)
    except tk.TclError:
        pass


def clock_color(t):
    if t == "FT":
        return MUTED
    if ":" in t:
        return PL_GREEN
    return PL_PINK
