"""Transient goal / penalty toast bubble."""
import tkinter as tk
from PIL import ImageTk

from ..config import FONT_SMALL, FONT_TINY
from ..overlay import setup_overlay
from ..theme import CHROMA, CLOCK_LIVE, MUTED, PANEL_BG, PL_GREEN, TEXT_COLOR, make_glass


def _rects_hit(a, b, pad=6):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return not (ax + aw + pad <= bx or bx + bw + pad <= ax or ay + ah + pad <= by or by + bh + pad <= ay)


def choose_bubble_origin(anchor, bubble_w, bubble_h, bounds, avoid, lift=0):
    """Prefer above the anchor. Slide until the popup misses every other pill."""
    ax, ay, aw, ah = anchor
    if bounds:
        mx, my, mw, mh = bounds
    else:
        mx, my, mw, mh = ax - 4000, ay - 4000, 8000, 8000
    gap = 10

    def clamp(x, y):
        return (
            max(mx + 4, min(int(x), mx + mw - bubble_w - 4)),
            max(my + 4, min(int(y), my + mh - bubble_h - 4)),
        )

    def open_spot(x, y):
        x, y = clamp(x, y)
        rect = (x, y, bubble_w, bubble_h)
        if any(_rects_hit(rect, other) for other in avoid):
            return None
        return x, y

    base_x = ax
    base_y = ay - gap - bubble_h - lift
    found = open_spot(base_x, base_y)
    if found:
        return found
    y = base_y
    for _ in range(24):
        y -= 14
        found = open_spot(base_x, y)
        if found:
            return found
    x = base_x
    for _ in range(24):
        x -= 14
        found = open_spot(x, base_y)
        if found:
            return found
    x = base_x
    for _ in range(24):
        x += 14
        found = open_spot(x, base_y)
        if found:
            return found
    for cand in (
        (ax - gap - bubble_w, ay),
        (ax + aw + gap, ay),
        (ax, ay + ah + gap + lift),
    ):
        found = open_spot(*cand)
        if found:
            return found
    return clamp(base_x, base_y)


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

    def place_near(self, anchor, lift=0, bounds=None, avoid=()):
        if not self.visible:
            self.deiconify()
            self.visible = True
            self._placed = None
        bx, by = choose_bubble_origin(anchor, self.w, self.h, bounds, avoid, lift=lift)
        if (bx, by) == getattr(self, "_placed", None):
            return bx, by
        self._placed = (bx, by)
        self.geometry(f"{self.w}x{self.h}+{bx}+{by}")
        try:
            self.lift()
        except tk.TclError:
            pass
        return bx, by

    def hide(self):
        if self.visible:
            self.withdraw()
            self.visible = False

