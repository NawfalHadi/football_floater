"""Startup / Settings glass panel (leagues, filters, monitor)."""
import threading
import tkinter as tk
from io import BytesIO

import requests
from PIL import Image, ImageTk

from ..config import FONT_SMALL, FONT_TINY, FONT_UI, FONT_UI_BOLD, LEAGUES
from ..matchday import matchday_window
from ..monitors import list_monitors, resolve_monitor_index
from ..overlay import setup_overlay
from ..theme import (
    BTN_BG,
    CHROMA,
    DIVIDER,
    MUTED,
    PANEL_BG,
    PL_GREEN,
    TEXT_COLOR,
    THEMES,
    make_circle_icon,
    make_glass,
)
from .glass_button import GlassButton


class StartupSettingsDialog(tk.Toplevel):
    """
    Shown on every app open (unless skip_startup_dialog).
    Also opened from Settings. Choose leagues + past/live/future.
    Glass capsule — same look as dock / timeline / pills.
    """

    def __init__(self, app, startup=False):
        super().__init__(app.root)
        setup_overlay(self, 0.96)
        self.app = app
        self.startup = startup
        self._logo_refs = []
        self._ph = None
        self._option_widgets = []  # (var, kind, indicator, is_on_fn) for refresh

        self._move_off = (0, 0)
        self.bg = tk.Label(self, bg=CHROMA, bd=0)
        self.bg.place(x=0, y=0)
        self.body = tk.Frame(self, bg=PANEL_BG)

        title_text = "What do you want to watch?" if startup else "Settings"
        bar = tk.Frame(self.body, bg=PANEL_BG, cursor="fleur")
        bar.pack(fill=tk.X)
        title = tk.Label(
            bar,
            text=title_text,
            bg=PANEL_BG,
            fg=TEXT_COLOR,
            font=FONT_UI_BOLD,
            anchor="w",
            cursor="fleur",
        )
        title.pack(side=tk.LEFT, fill=tk.X, expand=True)
        grip = tk.Label(bar, text="⋮⋮", bg=PANEL_BG, fg=MUTED, font=FONT_UI_BOLD, cursor="fleur")
        grip.pack(side=tk.RIGHT, padx=(8, 0))
        for w in (bar, title, grip):
            w.bind("<ButtonPress-1>", self._start_move)
            w.bind("<B1-Motion>", self._do_move)
        # Glass rim also drags — empty chrome around the body.
        self.bg.bind("<ButtonPress-1>", self._start_move)
        self.bg.bind("<B1-Motion>", self._do_move)

        tk.Frame(self.body, bg=DIVIDER, height=1).pack(fill=tk.X, pady=(8, 8))

        start, end = matchday_window()
        tip = (
            f"Matchday {start.strftime('%a %H:%M')} → {end.strftime('%a %H:%M')} local. "
            f"Late kicks stay in; next evening stays out."
        )
        tk.Label(self.body, text=tip, bg=PANEL_BG, fg=MUTED, font=FONT_SMALL, justify="left", wraplength=340).pack(
            anchor="w", pady=(0, 6)
        )

        enabled = set(app.settings.get("leagues") or ["eng.1"])
        self.league_vars = {}
        self._section("Leagues")
        for lid, meta in LEAGUES.items():
            var = tk.BooleanVar(value=lid in enabled)
            self.league_vars[lid] = var
            self._check_row(meta["name"], var, logo_url=meta.get("logo"), short=meta["short"])

        self._section("Match types")
        self.var_past = tk.BooleanVar(value=bool(app.settings.get("show_past", True)))
        self.var_live = tk.BooleanVar(value=bool(app.settings.get("show_live", True)))
        self.var_future = tk.BooleanVar(value=bool(app.settings.get("show_future", True)))
        for text, var in (
            ("Past matches (full-time this matchday)", self.var_past),
            ("Live matches", self.var_live),
            ("Future matches (still this matchday)", self.var_future),
        ):
            self._check_row(text, var)

        self._section("Theme")
        saved_theme = app.settings.get("theme") or "default"
        if saved_theme not in THEMES:
            saved_theme = "default"
        self.var_theme = tk.StringVar(value=saved_theme)
        for key, meta in THEMES.items():
            self._radio_row(meta["label"], self.var_theme, key)

        self.monitors = list_monitors(app.root)
        saved_mon = resolve_monitor_index(app.settings.get("monitor_index"), app.root)
        self.var_monitor = tk.IntVar(value=saved_mon)
        self._section("Display")
        if len(self.monitors) == 1:
            tk.Label(
                self.body,
                text=self.monitors[0]["label"],
                bg=PANEL_BG,
                fg=TEXT_COLOR,
                font=FONT_UI,
                anchor="w",
            ).pack(fill=tk.X, pady=2)
        else:
            for i, mon in enumerate(self.monitors):
                self._radio_row(mon["label"], self.var_monitor, i)

        self.var_skip = tk.BooleanVar(value=bool(app.settings.get("skip_startup_dialog", False)))
        tk.Frame(self.body, bg=DIVIDER, height=1).pack(fill=tk.X, pady=(10, 8))
        self._check_row("Don't ask next time", self.var_skip, muted=True)

        actions = tk.Frame(self.body, bg=PANEL_BG)
        actions.pack(fill=tk.X, pady=(14, 0))
        GlassButton(
            actions,
            "Start" if startup else "Save",
            self._save,
            "on",
            min_w=96,
            icon="gear" if not startup else None,
        ).pack(side=tk.RIGHT)
        if not startup:
            GlassButton(actions, "Cancel", self.destroy, "muted", min_w=88).pack(side=tk.RIGHT, padx=(0, 6))

        self.protocol("WM_DELETE_WINDOW", self._save if startup else self.destroy)
        self._resize_glass()
        self._place_center()
        self.deiconify()
        self.lift()
        self.focus_force()
        try:
            self.grab_set()
        except tk.TclError:
            pass

    def _section(self, title):
        tk.Frame(self.body, bg=DIVIDER, height=1).pack(fill=tk.X, pady=(8, 6))
        tk.Label(self.body, text=title.upper(), bg=PANEL_BG, fg=MUTED, font=FONT_TINY).pack(anchor="w", pady=(0, 2))

    def _mark(self, on):
        return "●" if on else "○"

    def _mark_color(self, on):
        return PL_GREEN if on else MUTED

    def _check_row(self, text, var, logo_url=None, short=None, muted=False):
        row = tk.Frame(self.body, bg=PANEL_BG, cursor="hand2")
        row.pack(fill=tk.X, pady=2)
        mark = tk.Label(
            row,
            text=self._mark(var.get()),
            bg=PANEL_BG,
            fg=self._mark_color(var.get()),
            font=FONT_UI_BOLD,
            width=2,
        )
        mark.pack(side=tk.LEFT)
        if logo_url or short:
            logo = self._league_logo(logo_url) if logo_url else None
            if logo:
                tk.Label(row, image=logo, bg=PANEL_BG, bd=0).pack(side=tk.LEFT, padx=(2, 8))
            else:
                badge = tk.Label(
                    row,
                    text=short or "?",
                    bg=BTN_BG,
                    fg=TEXT_COLOR,
                    font=FONT_TINY,
                    width=3,
                    padx=4,
                    pady=1,
                )
                badge.pack(side=tk.LEFT, padx=(2, 8))
        label = tk.Label(
            row,
            text=text,
            bg=PANEL_BG,
            fg=MUTED if muted else TEXT_COLOR,
            font=FONT_SMALL if muted else FONT_UI,
            anchor="w",
        )
        label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        def toggle(_e=None, v=var, m=mark):
            v.set(not v.get())
            m.configure(text=self._mark(v.get()), fg=self._mark_color(v.get()))

        for w in (row, mark, label):
            w.bind("<Button-1>", toggle)
        self._option_widgets.append(("check", var, mark, None))

    def _radio_row(self, text, var, value):
        row = tk.Frame(self.body, bg=PANEL_BG, cursor="hand2")
        row.pack(fill=tk.X, pady=2)
        on = var.get() == value
        mark = tk.Label(
            row,
            text=self._mark(on),
            bg=PANEL_BG,
            fg=self._mark_color(on),
            font=FONT_UI_BOLD,
            width=2,
        )
        mark.pack(side=tk.LEFT)
        label = tk.Label(row, text=text, bg=PANEL_BG, fg=TEXT_COLOR, font=FONT_UI, anchor="w")
        label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        def select(_e=None, v=var, val=value):
            v.set(val)
            self._refresh_radios(v)
            if v is self.var_monitor:
                self._place_center()

        for w in (row, mark, label):
            w.bind("<Button-1>", select)
        self._option_widgets.append(("radio", var, mark, value))

    def _refresh_radios(self, target_var):
        for kind, var, mark, value in self._option_widgets:
            if kind != "radio" or var is not target_var:
                continue
            on = var.get() == value
            mark.configure(text=self._mark(on), fg=self._mark_color(on))

    def _resize_glass(self):
        self.body.update_idletasks()
        pad_x, pad_y = 32, 28
        w = max(360, self.body.winfo_reqwidth() + pad_x)
        h = self.body.winfo_reqheight() + pad_y
        self._size = (w, h)
        self._ph = ImageTk.PhotoImage(make_glass(w, h, radius=16))
        self.bg.configure(image=self._ph)
        self.geometry(f"{w}x{h}")
        self.body.place(x=16, y=14)

    def _place_center(self):
        """Own window — center on the chosen display, not glued to the Live dock."""
        self.update_idletasks()
        dw, dh = self._size
        idx = int(self.var_monitor.get())
        if idx < 0 or idx >= len(self.monitors):
            idx = 0
        mon = self.monitors[idx]
        x = int(mon["x"] + (mon["w"] - dw) / 2)
        y = int(mon["y"] + (mon["h"] - dh) / 2)
        self.geometry(f"{dw}x{dh}+{x}+{y}")

    def _start_move(self, event):
        self._move_off = (event.x_root - self.winfo_x(), event.y_root - self.winfo_y())

    def _do_move(self, event):
        ox, oy = self._move_off
        self.geometry(f"+{event.x_root - ox}+{event.y_root - oy}")

    def destroy(self):
        if getattr(self.app, "_settings_dialog", None) is self:
            self.app._settings_dialog = None
        super().destroy()

    def _league_logo(self, url, size=22):
        if not url:
            return None
        cache = getattr(self.app, "image_cache", None)
        key = f"league:{url}:{size}"
        if cache is not None and key in cache:
            return cache[key]
        try:
            r = requests.get(url, timeout=4)
            if r.status_code != 200:
                return None
            ph = ImageTk.PhotoImage(make_circle_icon(Image.open(BytesIO(r.content)), size))
            self._logo_refs.append(ph)
            if cache is not None:
                cache[key] = ph
            return ph
        except Exception:
            return None

    def _save(self):
        leagues = [lid for lid, var in self.league_vars.items() if var.get()]
        if not leagues:
            leagues = ["eng.1"]
            self.league_vars["eng.1"].set(True)
        if not (self.var_past.get() or self.var_live.get() or self.var_future.get()):
            self.var_live.set(True)

        prev_mon = resolve_monitor_index(self.app.settings.get("monitor_index"), self.app.root)
        self.app.settings["leagues"] = leagues
        self.app.settings["show_past"] = self.var_past.get()
        self.app.settings["show_live"] = self.var_live.get()
        self.app.settings["show_future"] = self.var_future.get()
        self.app.settings["skip_startup_dialog"] = self.var_skip.get()
        self.app.settings["monitor_index"] = int(self.var_monitor.get())
        self.app.settings["theme"] = self.var_theme.get() if self.var_theme.get() in THEMES else "default"
        self.app.settings["filters_set"] = True
        self.app.save_settings()
        self.destroy()
        self.app.restyle()
        self.app.apply_display_layout(force=prev_mon != int(self.var_monitor.get()))
        self.app._ensure_data_loop()
        threading.Thread(target=self.app.run_once, daemon=True).start()
