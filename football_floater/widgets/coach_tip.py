"""One-shot coach tip overlay — auto-dismisses."""
import tkinter as tk
from PIL import ImageTk

from ..config import COACH_TIP_MS, FONT_SMALL, FONT_UI_BOLD
from ..overlay import setup_overlay, window_fill
from ..theme import MUTED, PANEL_BG, TEXT_COLOR, make_glass


class CoachTip(tk.Toplevel):
    def __init__(self, app, text, near=None):
        super().__init__(app.root)
        setup_overlay(self, 0.97)
        self.app = app
        pad_x, pad_y = 28, 22
        body = tk.Frame(self, bg=PANEL_BG)
        tk.Label(body, text="Tip", bg=PANEL_BG, fg=MUTED, font=FONT_UI_BOLD, anchor="w").pack(anchor="w")
        tk.Label(
            body,
            text=text,
            bg=PANEL_BG,
            fg=TEXT_COLOR,
            font=FONT_SMALL,
            justify="left",
            wraplength=280,
        ).pack(anchor="w", pady=(4, 0))
        body.update_idletasks()
        w = max(220, body.winfo_reqwidth() + pad_x)
        h = body.winfo_reqheight() + pad_y
        self._ph = ImageTk.PhotoImage(make_glass(w, h, radius=14))
        bg = tk.Label(self, image=self._ph, bg=window_fill(), bd=0)
        bg.place(x=0, y=0)
        body.place(x=14, y=10)
        self.geometry(f"{w}x{h}")
        self._place(near, w, h)
        self.after(COACH_TIP_MS, self._safe_destroy)

    def _place(self, near, w, h):
        mon = self.app.selected_monitor()
        if near is not None:
            try:
                x = int(near.winfo_rootx() + (near.winfo_width() - w) / 2)
                y = int(near.winfo_rooty() - h - 10)
                self.geometry(f"{w}x{h}+{x}+{y}")
                return
            except tk.TclError:
                pass
        x = mon["x"] + (mon["w"] - w) // 2
        y = mon["y"] + mon["h"] // 5
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _safe_destroy(self):
        try:
            self.destroy()
        except tk.TclError:
            pass
