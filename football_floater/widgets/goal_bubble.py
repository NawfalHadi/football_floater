"""Transient goal / penalty toast bubble."""
import tkinter as tk
from PIL import ImageTk

from ..config import FONT_TINY
from ..overlay import setup_overlay
from ..theme import CHROMA, PANEL_BG, PL_GREEN, TEXT_COLOR, make_glass


class GoalBubble(tk.Toplevel):
    def __init__(self, master, text):
        super().__init__(master)
        setup_overlay(self, 0.96)
        self.visible = True
        bg = tk.Label(self, bg=CHROMA, bd=0)
        bg.place(x=0, y=0)
        body = tk.Frame(self, bg=PANEL_BG)
        tk.Label(body, text="GOAL", bg=PANEL_BG, fg=PL_GREEN, font=FONT_TINY).pack(side=tk.LEFT, padx=(0, 6))
        tk.Label(body, text=text, bg=PANEL_BG, fg=TEXT_COLOR, font=FONT_TINY).pack(side=tk.LEFT)
        body.update_idletasks()
        w, h = body.winfo_reqwidth() + 32, 32
        self._ph = ImageTk.PhotoImage(make_glass(w, h))
        bg.configure(image=self._ph)
        body.place(x=16, y=(h - body.winfo_reqheight()) // 2)
        self.h = h
        self.geometry(f"{w}x{h}+-2000+-2000")

    def place_above(self, x, y):
        if not self.visible:
            self.deiconify()
            self.visible = True
        self.geometry(f"+{int(x)}+{int(y - self.h - 6)}")

    def hide(self):
        if self.visible:
            self.withdraw()
            self.visible = False

