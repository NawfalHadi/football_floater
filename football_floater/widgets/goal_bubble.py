"""Transient goal / penalty toast bubble."""
import tkinter as tk
from PIL import ImageTk

from ..config import FONT_TINY
from ..overlay import setup_overlay
from ..theme import CHROMA, CLOCK_LIVE, PANEL_BG, PL_GREEN, TEXT_COLOR, make_glass


class GoalBubble(tk.Toplevel):
    def __init__(self, master, text, tag="GOAL"):
        super().__init__(master)
        setup_overlay(self, 0.96)
        self.visible = True
        bg = tk.Label(self, bg=CHROMA, bd=0)
        bg.place(x=0, y=0)
        body = tk.Frame(self, bg=PANEL_BG)
        tag_color = CLOCK_LIVE if tag == "SUB" else PL_GREEN
        tk.Label(body, text=tag, bg=PANEL_BG, fg=tag_color, font=FONT_TINY).pack(side=tk.LEFT, padx=(0, 6))
        tk.Label(body, text=text, bg=PANEL_BG, fg=TEXT_COLOR, font=FONT_TINY).pack(side=tk.LEFT)
        body.update_idletasks()
        w, h = body.winfo_reqwidth() + 32, 32
        self._ph = ImageTk.PhotoImage(make_glass(w, h))
        bg.configure(image=self._ph)
        body.place(x=16, y=(h - body.winfo_reqheight()) // 2)
        self.h = h
        self.geometry(f"{w}x{h}+-2000+-2000")

    def place_above(self, x, y, lift=0):
        if not self.visible:
            self.deiconify()
            self.visible = True
        self.geometry(f"+{int(x)}+{int(y - self.h - 6 - lift)}")

    def hide(self):
        if self.visible:
            self.withdraw()
            self.visible = False

