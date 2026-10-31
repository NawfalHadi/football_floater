"""Transient goal / penalty toast bubble."""
import tkinter as tk
from PIL import ImageTk

from ..config import FONT_SMALL, FONT_TINY
from ..overlay import setup_overlay
from ..theme import CHROMA, CLOCK_LIVE, MUTED, PANEL_BG, PL_GREEN, TEXT_COLOR, make_glass


class GoalBubble(tk.Toplevel):
    def __init__(self, master, text, tag="GOAL", detail="", lines=None):
        super().__init__(master)
        setup_overlay(self, 0.96)
        self.visible = True
        bg = tk.Label(self, bg=CHROMA, bd=0)
        bg.place(x=0, y=0)
        body = tk.Frame(self, bg=PANEL_BG)
        tag_color = CLOCK_LIVE if tag == "SUB" else PL_GREEN
        tk.Label(body, text=tag, bg=PANEL_BG, fg=tag_color, font=FONT_TINY).pack(side=tk.LEFT, anchor="n", padx=(0, 6))
        col = tk.Frame(body, bg=PANEL_BG)
        col.pack(side=tk.LEFT, anchor="n")
        if lines:
            tk.Label(col, text=text, bg=PANEL_BG, fg=MUTED, font=FONT_TINY, anchor="w").pack(anchor="w")
            for i, line in enumerate(lines):
                pair = tk.Frame(col, bg=PANEL_BG)
                pair.pack(anchor="w", pady=(5 if i else 1, 0))
                on_line = tk.Frame(pair, bg=PANEL_BG)
                on_line.pack(anchor="w")
                tk.Label(on_line, text=line.get("on") or "?", bg=PANEL_BG, fg=TEXT_COLOR, font=FONT_TINY, anchor="w").pack(
                    side=tk.LEFT
                )
                tk.Label(on_line, text=" on", bg=PANEL_BG, fg=MUTED, font=FONT_SMALL, anchor="w").pack(side=tk.LEFT)
                if line.get("off"):
                    tk.Label(pair, text=f"{line['off']} off", bg=PANEL_BG, fg=MUTED, font=FONT_SMALL, anchor="w").pack(
                        anchor="w"
                    )
        else:
            tk.Label(
                col, text=text, bg=PANEL_BG, fg=TEXT_COLOR, font=FONT_TINY, anchor="w", justify="left", wraplength=200
            ).pack(anchor="w")
            if detail:
                tk.Label(
                    col, text=detail, bg=PANEL_BG, fg=MUTED, font=FONT_SMALL, anchor="w", justify="left", wraplength=200
                ).pack(anchor="w")
        body.update_idletasks()
        w = body.winfo_reqwidth() + 32
        h = max(32, body.winfo_reqheight() + 16)
        self._ph = ImageTk.PhotoImage(make_glass(w, h))
        bg.configure(image=self._ph)
        body.place(x=16, y=(h - body.winfo_reqheight()) // 2)
        self.w = w
        self.h = h
        self.geometry(f"{w}x{h}+-2000+-2000")

    def place_above(self, x, y, lift=0, bounds=None):
        if not self.visible:
            self.deiconify()
            self.visible = True
        bx = int(x)
        by = int(y - self.h - 6 - lift)
        if bounds:
            mx, my, mw, mh = bounds
            bx = max(mx + 8, min(bx, mx + mw - self.w - 8))
            if by < my + 8:
                by = int(y + 8)
            by = max(my + 8, min(by, my + mh - self.h - 8))
        self.geometry(f"{self.w}x{self.h}+{bx}+{by}")

    def hide(self):
        if self.visible:
            self.withdraw()
            self.visible = False

