"""Startup / Settings dialog (leagues, filters, monitor)."""
import tkinter as tk

from ..config import FONT_SMALL, FONT_TINY, FONT_UI, FONT_UI_BOLD, LEAGUES
from ..matchday import matchday_window
from ..monitors import list_monitors, resolve_monitor_index
from ..theme import BTN_BG, MUTED, PANEL_BG, TEXT_COLOR


class StartupSettingsDialog(tk.Toplevel):
    """
    Shown on every app open (unless skip_startup_dialog).
    Also opened from Settings. Choose leagues + past/live/future.
    """

    def __init__(self, app, startup=False):
        super().__init__(app.root)
        self.app = app
        self.startup = startup
        self.title("Live Scores — Settings" if not startup else "Live Scores — What to show?")
        self.configure(bg=PANEL_BG)
        self.resizable(False, False)
        self.transient(app.root)
        self.grab_set()

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
            tk.Checkbutton(
                self,
                text=meta["name"],
                variable=var,
                bg=PANEL_BG,
                fg=TEXT_COLOR,
                selectcolor=BTN_BG,
                activebackground=PANEL_BG,
                activeforeground=TEXT_COLOR,
                font=FONT_UI,
                anchor="w",
            ).pack(fill=tk.X, padx=16, pady=1)

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

        # --- Display / monitor ---
        self.monitors = list_monitors(app.root)
        # Unset / invalid → OS primary (not blindly index 0)
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
        tk.Button(row, text="Start" if startup else "Save", command=self._save, bg=BTN_BG, fg=TEXT_COLOR, relief="flat", padx=12).pack(
            side=tk.RIGHT
        )
        if not startup:
            tk.Button(
                row, text="Cancel", command=self.destroy, bg=BTN_BG, fg=MUTED, relief="flat", padx=12
            ).pack(side=tk.RIGHT, padx=(0, 8))

        # On startup, closing the window still applies current choices
        self.protocol("WM_DELETE_WINDOW", self._save if startup else self.destroy)
        self.update_idletasks()
        # Center dialog on currently selected / primary-ish monitor
        mon = self.monitors[saved_mon]
        dw, dh = self.winfo_reqwidth(), self.winfo_reqheight()
        self.geometry(
            f"+{mon['x'] + (mon['w'] - dw) // 2}+{mon['y'] + (mon['h'] - dh) // 2}"
        )

    def _save(self):
        leagues = [lid for lid, var in self.league_vars.items() if var.get()]
        if not leagues:
            leagues = ["eng.1"]
            self.league_vars["eng.1"].set(True)
        if not (self.var_past.get() or self.var_live.get() or self.var_future.get()):
            self.var_live.set(True)

        self.app.settings["leagues"] = leagues
        self.app.settings["show_past"] = self.var_past.get()
        self.app.settings["show_live"] = self.var_live.get()
        self.app.settings["show_future"] = self.var_future.get()
        self.app.settings["skip_startup_dialog"] = self.var_skip.get()
        self.app.settings["monitor_index"] = int(self.var_monitor.get())
        self.app.settings["filters_set"] = True
        self.app.save_settings()
        self.destroy()
        self.app.apply_display_layout(force=True)
        self.app._ensure_data_loop()
        threading.Thread(target=self.app.run_once, daemon=True).start()

