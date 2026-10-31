"""Movable control dock (full + minimized)."""
import tkinter as tk
from PIL import ImageTk

from ..config import (
    CTRL_H,
    CTRL_MIN_H,
    FONT_TINY,
    FONT_UI,
    FONT_UI_BOLD,
    ROW_GAP,
    TICKER_H,
    TICKER_W,
)
from ..overlay import setup_overlay
from ..theme import CHROMA, MUTED, PANEL_BG, TEXT_COLOR, make_glass
from .glass_button import GlassButton


class ControlDock(tk.Toplevel):
    """Independently movable control bar. Can minimize to icon-only strip."""

    def __init__(self, app):
        super().__init__(app.root)
        setup_overlay(self)
        self.app = app
        self.minimized = bool(app.settings.get("ctrl_minimized", False))
        self._move_off = (0, 0)

        self.bg = tk.Label(self, bg=CHROMA, bd=0)
        self.bg.place(x=0, y=0)
        self.body = tk.Frame(self, bg=PANEL_BG)

        self._build()
        self._place_default()

    def _clear_body(self):
        for w in self.body.winfo_children():
            w.destroy()

    def _build(self):
        self._clear_body()
        if self.minimized:
            self._build_mini()
        else:
            self._build_full()
        self.body.update_idletasks()
        h = CTRL_MIN_H if self.minimized else CTRL_H
        w = self.body.winfo_reqwidth() + 28
        self._ph = ImageTk.PhotoImage(make_glass(w, h))
        self.bg.configure(image=self._ph)
        self.body.place(x=14, y=(h - self.body.winfo_reqheight()) // 2)
        # keep current screen position when rebuilding
        try:
            x, y = self.winfo_x(), self.winfo_y()
        except tk.TclError:
            x, y = 100, 100
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.bg.bind("<ButtonPress-1>", self._start_move)
        self.bg.bind("<B1-Motion>", self._do_move)
        self.body.bind("<ButtonPress-1>", self._start_move)
        self.body.bind("<B1-Motion>", self._do_move)

    def _build_full(self):
        handle = tk.Label(self.body, text="Live", bg=PANEL_BG, fg=MUTED, font=FONT_UI_BOLD, cursor="fleur")
        handle.pack(side=tk.LEFT, padx=(0, 8))
        handle.bind("<ButtonPress-1>", self._start_move)
        handle.bind("<B1-Motion>", self._do_move)

        self.btn_refresh = GlassButton(
            self.body, "Refresh", self.app.manual_refresh, "refresh", min_w=108, icon="refresh"
        )
        self.btn_refresh.pack(side=tk.LEFT, padx=3)
        GlassButton(self.body, "Test", self.app.run_test_notification, "test", icon="ball").pack(side=tk.LEFT, padx=3)
        self.btn_free = GlassButton(
            self.body,
            "Float: On" if self.app.free_float else "Float: Off",
            self.app.toggle_free_float,
            "on" if self.app.free_float else "muted",
            min_w=128,
            icon="float",
        )
        self.btn_free.pack(side=tk.LEFT, padx=3)
        self.btn_rearrange = GlassButton(
            self.body,
            "Rearrange",
            self.app.rearrange_float_pills,
            "default" if self.app.free_float else "muted",
            min_w=120,
            icon="rearrange",
        )
        self.btn_rearrange.pack(side=tk.LEFT, padx=3)
        self.btn_hidden = GlassButton(
            self.body, "Hidden 0", self.app.show_hidden_menu, "hidden", min_w=112, icon="hidden"
        )
        self.btn_hidden.pack(side=tk.LEFT, padx=3)
        GlassButton(self.body, "Settings", self.app.show_settings_dialog, "settings", icon="gear").pack(
            side=tk.LEFT, padx=3
        )
        GlassButton(self.body, "Mini", self.toggle_minimize, "muted", icon="mini").pack(side=tk.LEFT, padx=3)
        GlassButton(self.body, "Quit", self.app.close_app, "danger", icon="quit").pack(side=tk.LEFT, padx=(8, 0))
        self.set_hidden(len(self.app.hidden_pills))

    def _build_mini(self):
        # icon-only: short glyphs, same actions
        handle = tk.Label(self.body, text="⋮⋮", bg=PANEL_BG, fg=MUTED, font=FONT_UI_BOLD, cursor="fleur")
        handle.pack(side=tk.LEFT, padx=(0, 4))
        handle.bind("<ButtonPress-1>", self._start_move)
        handle.bind("<B1-Motion>", self._do_move)

        h = 26
        self.btn_refresh = GlassButton(
            self.body, "", self.app.manual_refresh, "refresh", min_w=28, height=h, icon="refresh"
        )
        self.btn_refresh.pack(side=tk.LEFT, padx=2)
        GlassButton(self.body, "", self.app.run_test_notification, "test", min_w=28, height=h, icon="ball").pack(
            side=tk.LEFT, padx=2
        )
        self.btn_free = GlassButton(
            self.body,
            "",
            self.app.toggle_free_float,
            "on" if self.app.free_float else "muted",
            min_w=28,
            height=h,
            icon="float",
        )
        self.btn_free.pack(side=tk.LEFT, padx=2)
        self.btn_rearrange = GlassButton(
            self.body,
            "",
            self.app.rearrange_float_pills,
            "default" if self.app.free_float else "muted",
            min_w=28,
            height=h,
            icon="rearrange",
        )
        self.btn_rearrange.pack(side=tk.LEFT, padx=2)
        self.btn_hidden = GlassButton(
            self.body, "", self.app.show_hidden_menu, "hidden", min_w=28, height=h, icon="hidden"
        )
        self.btn_hidden.pack(side=tk.LEFT, padx=2)
        GlassButton(self.body, "", self.app.show_settings_dialog, "settings", min_w=28, height=h, icon="gear").pack(
            side=tk.LEFT, padx=2
        )
        GlassButton(self.body, "", self.toggle_minimize, "default", min_w=28, height=h, icon="expand").pack(
            side=tk.LEFT, padx=2
        )
        GlassButton(self.body, "", self.app.close_app, "danger", min_w=28, height=h, icon="quit").pack(
            side=tk.LEFT, padx=(4, 0)
        )
        self.set_hidden(len(self.app.hidden_pills))

    def _place_default(self):
        pos = self.app.settings.get("ctrl_pos")
        self.update_idletasks()
        cw = self.winfo_width() or self.winfo_reqwidth() or 320
        ch = self.winfo_height() or CTRL_H
        if pos and len(pos) >= 2 and self.app.spot_on_screen(pos[0], pos[1], cw, ch):
            self.geometry(f"+{int(pos[0])}+{int(pos[1])}")
            return
        try:
            tx = self.app.root.winfo_rootx()
            ty = self.app.root.winfo_rooty()
            tw = self.app.root.winfo_width() or TICKER_W
            th = self.app.root.winfo_height() or TICKER_H
        except tk.TclError:
            mon = self.app.selected_monitor()
            tx = mon["x"] + (mon["w"] - TICKER_W) // 2
            ty, tw, th = mon["y"] + 80, TICKER_W, TICKER_H
        x = tx + (tw - cw) // 2
        y = ty + th + ROW_GAP
        self.geometry(f"+{int(x)}+{int(y)}")

    def toggle_minimize(self):
        self.minimized = not self.minimized
        self.app.settings["ctrl_minimized"] = self.minimized
        self.app.save_settings()
        self._build()

    def set_free_button(self):
        if not hasattr(self, "btn_free"):
            return
        kind = "on" if self.app.free_float else "muted"
        label = "" if self.minimized else ("Float: On" if self.app.free_float else "Float: Off")
        self.btn_free.set(label, kind, icon="float")
        if hasattr(self, "btn_rearrange"):
            self.btn_rearrange.set(
                "" if self.minimized else "Rearrange",
                "default" if self.app.free_float else "muted",
                icon="rearrange",
            )

    def set_refresh(self, label, kind="default"):
        if hasattr(self, "btn_refresh"):
            if kind == "busy":
                self.btn_refresh.set("" if self.minimized else "…", "busy", icon="refresh")
            else:
                self.btn_refresh.set("" if self.minimized else "Refresh", "refresh", icon="refresh")

    def set_hidden(self, n):
        if not hasattr(self, "btn_hidden"):
            return
        kind = "hidden" if n == 0 else "default"
        if self.minimized:
            self.btn_hidden.set("" if n == 0 else str(n), kind, icon="" if n else "hidden")
        else:
            self.btn_hidden.set(f"Hidden {n}", kind, icon="hidden")

    def _start_move(self, event):
        self._move_off = (event.x_root - self.winfo_x(), event.y_root - self.winfo_y())

    def _do_move(self, event):
        ox, oy = self._move_off
        self.geometry(f"+{event.x_root - ox}+{event.y_root - oy}")
        self.app.settings["ctrl_pos"] = [self.winfo_x(), self.winfo_y()]
        self.app.save_settings()

