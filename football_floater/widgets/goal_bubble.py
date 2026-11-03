"""Running-text toast above the ticker (float mode uses in-pill alerts instead)."""
import tkinter as tk
from PIL import ImageTk

from ..config import FONT_SMALL, FONT_TINY
from ..overlay import window_fill
from ..theme import CLOCK_LIVE, MUTED, PANEL_BG, PL_GREEN, TEXT_COLOR, make_glass


def _fill_toast_body(body, text, tag, detail, lines):
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


class TickerToast(tk.Frame):
    """
    Running-text toast living inside the ticker window.
    place() rides scroll_x — avoids separate Toplevels that freeze on some WMs.
    """

    def __init__(self, master, text, tag="GOAL", detail="", lines=None):
        fill = window_fill()
        super().__init__(master, bg=fill, bd=0)
        self.visible = True
        bg = tk.Label(self, bg=fill, bd=0)
        bg.place(x=0, y=0)
        body = tk.Frame(self, bg=PANEL_BG)
        _fill_toast_body(body, text, tag, detail or "", lines)
        body.update_idletasks()
        w = body.winfo_reqwidth() + 32
        h = max(32, body.winfo_reqheight() + 16)
        self._ph = ImageTk.PhotoImage(make_glass(w, h))
        bg.configure(image=self._ph, bg=fill)
        body.place(x=16, y=(h - body.winfo_reqheight()) // 2)
        self.w = w
        self.h = h
        self.configure(width=w, height=h)
        self.place(x=-4000, y=0, width=w, height=h)

    def update_position(self, x, y, lift=0, gap=8):
        """x = left edge in root; y = top of glass bar. Never draw into the glass."""
        bx = int(x)
        by = int(y - self.h - gap - lift)
        if by < 0:
            by = 0
        if not self.visible:
            self.visible = True
        self.place(x=bx, y=by, width=self.w, height=self.h)
        try:
            self.lift()
        except tk.TclError:
            pass

    def hide(self):
        if self.visible:
            self.place_forget()
            self.visible = False
