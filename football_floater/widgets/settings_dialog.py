"""Startup (leagues + display) and full Settings glass panel."""
import threading
import tkinter as tk
from io import BytesIO

import requests
from PIL import Image, ImageTk

from ..config import FONT_SMALL, FONT_TINY, FONT_UI, FONT_UI_BOLD, LEAGUES
from ..matchday import matchday_window
from ..monitors import list_monitors, resolve_monitor_index
from ..overlay import setup_overlay, window_fill
from ..theme import (
    BTN_BG,
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
    Startup: leagues + display only.
    Settings: full options (filters, theme, detach pills, advanced).
    """

    def __init__(self, app, startup=False):
        super().__init__(app.root)
        setup_overlay(self, 0.96)
        self.app = app
        self.startup = startup
        self._logo_refs = []
        self._pending_logos = []  # (label, url, size) — fetch off UI thread
        self._ph = None
        self._option_widgets = []

        self._move_off = (0, 0)
        self._dragging = False
        fill = window_fill()
        self.bg = tk.Label(self, bg=fill, bd=0)
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
        for w in (bar, title, grip, self.bg):
            w.bind("<ButtonPress-1>", self._start_move)
            w.bind("<B1-Motion>", self._do_move)
            w.bind("<ButtonRelease-1>", self._end_move)

        tk.Frame(self.body, bg=DIVIDER, height=1).pack(fill=tk.X, pady=(8, 8))

        start, end = matchday_window()
        tip = (
            f"Matchday {start.strftime('%a %H:%M')} → {end.strftime('%a %H:%M')} local. "
            f"Late kicks stay in; next evening stays out."
        )
        tk.Label(self.body, text=tip, bg=PANEL_BG, fg=MUTED, font=FONT_SMALL, justify="left", wraplength=340).pack(
            anchor="w", pady=(0, 6)
        )

        enabled = set(app.settings.get("leagues") or list(LEAGUES.keys()))
        self.league_vars = {}
        self._section("Leagues")
        for lid, meta in LEAGUES.items():
            var = tk.BooleanVar(value=lid in enabled)
            self.league_vars[lid] = var
            self._check_row(meta["name"], var, logo_url=meta.get("logo"), short=meta["short"])

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

        # Full settings only — keep first-run short.
        self.var_past = tk.BooleanVar(value=bool(app.settings.get("show_past", True)))
        self.var_live = tk.BooleanVar(value=bool(app.settings.get("show_live", True)))
        self.var_future = tk.BooleanVar(value=bool(app.settings.get("show_future", True)))
        saved_theme = app.settings.get("theme") or "default"
        if saved_theme not in THEMES:
            saved_theme = "default"
        self.var_theme = tk.StringVar(value=saved_theme)
        self.var_float = tk.BooleanVar(value=bool(app.free_float))
        self.var_skip = tk.BooleanVar(value=bool(app.settings.get("skip_startup_dialog", False)))

        if not startup:
            self._section("Match types")
            for text, var in (
                ("Past matches (full-time this matchday)", self.var_past),
                ("Live matches", self.var_live),
                ("Future matches (still this matchday)", self.var_future),
            ):
                self._check_row(text, var)

            self._section("Theme")
            for key, meta in THEMES.items():
                self._radio_row(meta["label"], self.var_theme, key)

            self._section("Layout")
            self._check_row("Detach matches as pills", self.var_float)
            tk.Label(
                self.body,
                text="Ticker hides; drag each match. Right-click a pill to hide it.",
                bg=PANEL_BG,
                fg=MUTED,
                font=FONT_SMALL,
                wraplength=340,
                justify="left",
            ).pack(anchor="w", pady=(0, 4))
            if app.free_float:
                GlassButton(
                    self.body,
                    "Reset pill layout",
                    self._reset_layout,
                    "default",
                    min_w=140,
                    icon="rearrange",
                ).pack(anchor="w", pady=(4, 0))

            self._section("Advanced")
            tk.Label(
                self.body,
                text="Fire on every visible match (float = in-pill pulse).",
                bg=PANEL_BG,
                fg=MUTED,
                font=FONT_SMALL,
                wraplength=340,
                justify="left",
            ).pack(anchor="w", pady=(0, 2))
            test_row = tk.Frame(self.body, bg=PANEL_BG)
            test_row.pack(fill=tk.X, pady=(2, 4))
            GlassButton(test_row, "Test GOAL", lambda: self._test_toast("GOAL"), "test", min_w=96, icon="ball").pack(
                side=tk.LEFT
            )
            GlassButton(test_row, "Test PEN", lambda: self._test_toast("PEN"), "test", min_w=88).pack(
                side=tk.LEFT, padx=(6, 0)
            )
            GlassButton(test_row, "Test SUB", lambda: self._test_toast("SUB"), "test", min_w=88).pack(
                side=tk.LEFT, padx=(6, 0)
            )
            self._check_row("Don't ask on startup", self.var_skip, muted=True)
        else:
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
            GlassButton(actions, "Apply", self._apply, "default", min_w=88).pack(side=tk.RIGHT, padx=(0, 6))
            GlassButton(actions, "Cancel", self.destroy, "muted", min_w=88).pack(side=tk.RIGHT, padx=(0, 6))
        else:
            GlassButton(actions, "Cancel", self._cancel_startup, "muted", min_w=88).pack(
                side=tk.RIGHT, padx=(0, 6)
            )

        self.protocol("WM_DELETE_WINDOW", self._cancel_startup if startup else self.destroy)
        self._resize_glass()
        self._place_center()
        self.deiconify()
        self.lift()
        self.focus_force()
        # No grab_set — dock / pills stay draggable & clickable while this is open.
        self.after(1, self._fetch_logos_async)

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
        logo_lbl = None
        if logo_url or short:
            # Short badge first — network logos load after dialog is on screen.
            logo_lbl = tk.Label(
                row,
                text=short or "?",
                bg=BTN_BG,
                fg=TEXT_COLOR,
                font=FONT_TINY,
                width=3,
                padx=4,
                pady=1,
            )
            logo_lbl.pack(side=tk.LEFT, padx=(2, 8))
            if logo_url:
                cached = self._cached_league_logo(logo_url)
                if cached:
                    logo_lbl.configure(image=cached, text="", width=0, padx=0, pady=0, bg=PANEL_BG)
                    logo_lbl.image = cached
                else:
                    self._pending_logos.append((logo_lbl, logo_url, 22))
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

        bind = [row, mark, label]
        if logo_lbl is not None:
            bind.append(logo_lbl)
        for w in bind:
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
        self.bg.configure(image=self._ph, bg=window_fill())
        self.geometry(f"{w}x{h}")
        self.body.place(x=16, y=14)

    def _place_center(self):
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
        self._dragging = True
        self._move_off = (event.x_root - self.winfo_x(), event.y_root - self.winfo_y())

    def _do_move(self, event):
        if not self._dragging:
            return
        ox, oy = self._move_off
        self.geometry(f"+{event.x_root - ox}+{event.y_root - oy}")

    def _end_move(self, _event=None):
        self._dragging = False

    def destroy(self):
        self._dragging = False
        if getattr(self.app, "_settings_dialog", None) is self:
            self.app._settings_dialog = None
        # Drop any residual press so dock/ticker do not inherit B1-Motion.
        try:
            self.app.end_move()
            self.app.dock._end_move()
        except Exception:
            pass
        super().destroy()

    def _cached_league_logo(self, url, size=22):
        cache = getattr(self.app, "image_cache", None)
        if cache is None:
            return None
        return cache.get(f"league:{url}:{size}")

    def _fetch_logos_async(self):
        pending = list(self._pending_logos)
        self._pending_logos.clear()
        if not pending:
            return

        def work():
            payloads = []
            for lbl, url, size in pending:
                try:
                    r = requests.get(url, timeout=4)
                    if r.status_code != 200:
                        continue
                    payloads.append((lbl, url, size, r.content))
                except Exception:
                    continue
            if payloads:
                self.after(0, lambda: self._apply_logo_bytes(payloads))

        threading.Thread(target=work, daemon=True).start()

    def _apply_logo_bytes(self, payloads):
        if not self.winfo_exists():
            return
        cache = getattr(self.app, "image_cache", None)
        for lbl, url, size, raw in payloads:
            try:
                if not lbl.winfo_exists():
                    continue
                key = f"league:{url}:{size}"
                if cache is not None and key in cache:
                    ph = cache[key]
                else:
                    ph = ImageTk.PhotoImage(make_circle_icon(Image.open(BytesIO(raw)), size))
                    self._logo_refs.append(ph)
                    if cache is not None:
                        cache[key] = ph
                lbl.configure(image=ph, text="", width=0, padx=0, pady=0, bg=PANEL_BG)
                lbl.image = ph
            except Exception:
                pass

    def _reset_layout(self):
        self.app.rearrange_float_pills()

    def _test_toast(self, kind="GOAL"):
        self.app.run_test_notification(kind)

    def _apply(self):
        self._commit(close=False)

    def _save(self):
        self._commit(close=True)

    def _cancel_startup(self):
        """Just dismiss the startup panel — dock / pills stay up."""
        try:
            self.destroy()
        except tk.TclError:
            pass
        # Prior session already had filters → keep (or start) the data loop.
        if self.app.settings.get("filters_set"):
            self.app._ensure_data_loop()
            if not self.app.current_matches:
                threading.Thread(target=self.app.run_once, daemon=True).start()

    def _refocus(self):
        try:
            if self.winfo_exists():
                self.lift()
                self.focus_force()
        except tk.TclError:
            pass

    def _commit(self, close=True):
        leagues = [lid for lid, var in self.league_vars.items() if var.get()]
        if not leagues:
            leagues = ["eng.1"]
            self.league_vars["eng.1"].set(True)

        prev_mon = resolve_monitor_index(self.app.settings.get("monitor_index"), self.app.root)
        self.app.settings["leagues"] = leagues
        self.app.settings["monitor_index"] = int(self.var_monitor.get())
        self.app.settings["skip_startup_dialog"] = self.var_skip.get()
        self.app.settings["filters_set"] = True

        if self.startup:
            # Smart defaults on first run — live + upcoming; past on for FT slate.
            self.app.settings.setdefault("show_past", True)
            self.app.settings.setdefault("show_live", True)
            self.app.settings.setdefault("show_future", True)
            self.app.settings.setdefault("theme", "default")
            want_float = False
        else:
            if not (self.var_past.get() or self.var_live.get() or self.var_future.get()):
                self.var_live.set(True)
            self.app.settings["show_past"] = self.var_past.get()
            self.app.settings["show_live"] = self.var_live.get()
            self.app.settings["show_future"] = self.var_future.get()
            self.app.settings["theme"] = self.var_theme.get() if self.var_theme.get() in THEMES else "default"
            want_float = bool(self.var_float.get())

        self.app.settings["free_float"] = want_float
        self.app.save_settings()
        force_mon = prev_mon != int(self.var_monitor.get())
        app = self.app
        keep = None if close else self
        if close:
            self.destroy()

        def _after():
            app.end_move()
            try:
                app.dock._end_move()
            except Exception:
                pass
            app.restyle()
            app.apply_display_layout(force=force_mon)
            app.apply_free_float(want_float)
            app._ensure_data_loop()
            threading.Thread(target=app.run_once, daemon=True).start()
            if keep is not None:
                try:
                    keep._resize_glass()
                    keep._refocus()
                except tk.TclError:
                    pass

        # Defer until after ButtonRelease so no stray B1-Motion hits the dock/ticker.
        app.root.after_idle(_after)
