"""Startup / Settings dialog (leagues, filters, monitor)."""
import threading
import tkinter as tk
from io import BytesIO

import requests
from PIL import Image, ImageTk

from ..config import FONT_SMALL, FONT_TINY, FONT_UI, FONT_UI_BOLD, LEAGUES
from ..matchday import matchday_window
from ..monitors import list_monitors, resolve_monitor_index
from ..theme import BTN_BG, MUTED, PANEL_BG, TEXT_COLOR, THEMES, make_circle_icon


class StartupSettingsDialog(tk.Toplevel):
    """
    Shown on every app open (unless skip_startup_dialog).
    Also opened from Settings. Choose leagues + past/live/future.
    """

    def __init__(self, app, startup=False):
        super().__init__(app.root)
        self.app = app
        self.startup = startup
        self._logo_refs = []
        self.title("Live Scores — Settings" if not startup else "Live Scores — What to show?")
        self.configure(bg=PANEL_BG)
        self.resizable(False, False)
        # Borderless ticker cannot parent a transient dialog on Windows — the
        # window is created and then never mapped. Stay topmost instead.
        try:
            self.wm_attributes("-topmost", True)
        except tk.TclError:
            pass

        start, end = matchday_window()
        tip = (
            f"Matchday window: {start.strftime('%a %H:%M')} → {end.strftime('%a %H:%M')} local.\n"
            f"Late kicks (e.g. 04:00) stay in; next evening (e.g. 20:00) stays out."
        )

        tk.Label(
            self,
            text="What do you want to watch?" if startup else "Settings",
            bg=PANEL_BG,
            fg=TEXT_COLOR,
            font=FONT_UI_BOLD,
        ).pack(anchor="w", padx=16, pady=(14, 4))
        tk.Label(self, text=tip, bg=PANEL_BG, fg=MUTED, font=FONT_SMALL, justify="left").pack(
            anchor="w", padx=16, pady=(0, 8)
        )

        enabled = set(app.settings.get("leagues") or ["eng.1"])
        self.league_vars = {}
        tk.Label(self, text="Leagues", bg=PANEL_BG, fg=MUTED, font=FONT_TINY).pack(anchor="w", padx=16, pady=(6, 2))
        for lid, meta in LEAGUES.items():
            var = tk.BooleanVar(value=lid in enabled)
            self.league_vars[lid] = var
            row = tk.Frame(self, bg=PANEL_BG)
            row.pack(fill=tk.X, padx=16, pady=2)
            logo = self._league_logo(meta.get("logo"))
            if logo:
                tk.Label(row, image=logo, bg=PANEL_BG, bd=0).pack(side=tk.LEFT, padx=(0, 8))
            else:
                tk.Label(
                    row,
                    text=meta["short"],
                    bg=BTN_BG,
                    fg=TEXT_COLOR,
                    font=FONT_TINY,
                    width=3,
                ).pack(side=tk.LEFT, padx=(0, 8))
            tk.Checkbutton(
                row,
                text=meta["name"],
                variable=var,
                bg=PANEL_BG,
                fg=TEXT_COLOR,
                selectcolor=BTN_BG,
                activebackground=PANEL_BG,
                activeforeground=TEXT_COLOR,
                font=FONT_UI,
                anchor="w",
            ).pack(side=tk.LEFT, fill=tk.X, expand=True)

        tk.Label(self, text="Match types", bg=PANEL_BG, fg=MUTED, font=FONT_TINY).pack(
            anchor="w", padx=16, pady=(10, 2)
        )
        self.var_past = tk.BooleanVar(value=bool(app.settings.get("show_past", True)))
        self.var_live = tk.BooleanVar(value=bool(app.settings.get("show_live", True)))
        self.var_future = tk.BooleanVar(value=bool(app.settings.get("show_future", True)))
        for text, var in (
            ("Past matches (full-time in this matchday)", self.var_past),
            ("Live matches", self.var_live),
            ("Future matches (still in this matchday)", self.var_future),
        ):
            tk.Checkbutton(
                self,
                text=text,
                variable=var,
                bg=PANEL_BG,
                fg=TEXT_COLOR,
                selectcolor=BTN_BG,
                activebackground=PANEL_BG,
                activeforeground=TEXT_COLOR,
                font=FONT_UI,
                anchor="w",
            ).pack(fill=tk.X, padx=16, pady=1)

        tk.Label(self, text="Theme", bg=PANEL_BG, fg=MUTED, font=FONT_TINY).pack(
            anchor="w", padx=16, pady=(10, 2)
        )
        saved_theme = app.settings.get("theme") or "default"
        if saved_theme not in THEMES:
            saved_theme = "default"
        self.var_theme = tk.StringVar(value=saved_theme)
        for key, meta in THEMES.items():
            tk.Radiobutton(
                self,
                text=meta["label"],
                variable=self.var_theme,
                value=key,
                bg=PANEL_BG,
                fg=TEXT_COLOR,
                selectcolor=BTN_BG,
                activebackground=PANEL_BG,
                activeforeground=TEXT_COLOR,
                font=FONT_UI,
                anchor="w",
            ).pack(fill=tk.X, padx=16, pady=1)

        # --- Display / monitor ---
        self.monitors = list_monitors(app.root)
        saved_mon = resolve_monitor_index(app.settings.get("monitor_index"), app.root)
        self.var_monitor = tk.IntVar(value=saved_mon)
        tk.Label(self, text="Display (where ticker & controls appear)", bg=PANEL_BG, fg=MUTED, font=FONT_TINY).pack(
            anchor="w", padx=16, pady=(10, 2)
        )
        if len(self.monitors) == 1:
            tk.Label(
                self,
                text=f"Detected: {self.monitors[0]['label']}",
                bg=PANEL_BG,
                fg=TEXT_COLOR,
                font=FONT_UI,
                anchor="w",
            ).pack(fill=tk.X, padx=16, pady=1)
        else:
            for i, mon in enumerate(self.monitors):
                tk.Radiobutton(
                    self,
                    text=mon["label"],
                    variable=self.var_monitor,
                    value=i,
                    bg=PANEL_BG,
                    fg=TEXT_COLOR,
                    selectcolor=BTN_BG,
                    activebackground=PANEL_BG,
                    activeforeground=TEXT_COLOR,
                    font=FONT_UI,
                    anchor="w",
                ).pack(fill=tk.X, padx=16, pady=1)

        self.var_skip = tk.BooleanVar(value=bool(app.settings.get("skip_startup_dialog", False)))
        tk.Checkbutton(
            self,
            text="Don't ask next time (open Settings later to change)",
            variable=self.var_skip,
            bg=PANEL_BG,
            fg=MUTED,
            selectcolor=BTN_BG,
            activebackground=PANEL_BG,
            activeforeground=MUTED,
            font=FONT_SMALL,
            anchor="w",
        ).pack(fill=tk.X, padx=16, pady=(12, 2))

        row = tk.Frame(self, bg=PANEL_BG)
        row.pack(fill=tk.X, padx=16, pady=14)
        tk.Button(
            row, text="Start" if startup else "Save", command=self._save, bg=BTN_BG, fg=TEXT_COLOR, relief="flat", padx=12
        ).pack(side=tk.RIGHT)
        if not startup:
            tk.Button(
                row, text="Cancel", command=self.destroy, bg=BTN_BG, fg=MUTED, relief="flat", padx=12
            ).pack(side=tk.RIGHT, padx=(0, 8))

        self.protocol("WM_DELETE_WINDOW", self._save if startup else self.destroy)
        self._place_near_dock()
        self.deiconify()
        self.lift()
        self.focus_force()
        try:
            self.grab_set()
        except tk.TclError:
            pass

    def _place_near_dock(self):
        """Center on the screen that actually holds the dock, not a hidden monitor."""
        self.update_idletasks()
        dw, dh = max(self.winfo_reqwidth(), 280), max(self.winfo_reqheight(), 200)
        try:
            dock = self.app.dock
            ax = dock.winfo_rootx() + max(dock.winfo_width(), 1) // 2
            ay = dock.winfo_rooty()
        except (tk.TclError, AttributeError):
            mon = self.monitors[0]
            ax = mon["x"] + mon["w"] // 2
            ay = mon["y"] + 120
        mon = self.monitors[0]
        for candidate in self.monitors:
            if candidate["x"] <= ax < candidate["x"] + candidate["w"] and candidate["y"] <= ay < candidate["y"] + candidate["h"]:
                mon = candidate
                break
        x = int(ax - dw / 2)
        y = int(ay - dh - 16)
        x = max(mon["x"] + 8, min(x, mon["x"] + mon["w"] - dw - 8))
        y = max(mon["y"] + 8, min(y, mon["y"] + mon["h"] - dh - 8))
        self.geometry(f"{dw}x{dh}+{x}+{y}")

    def destroy(self):
        if getattr(self.app, "_settings_dialog", None) is self:
            self.app._settings_dialog = None
        super().destroy()

    def _league_logo(self, url, size=22):
        if not url:
            return None
        # reuse app image cache when possible
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
