"""Per-match timeline panel (auto-dismiss)."""
import tkinter as tk
from PIL import ImageTk

from ..config import (
    FONT_SMALL,
    FONT_TINY,
    FONT_UI,
    FONT_UI_BOLD,
    TIMELINE_IDLE_MS,
    TIMELINE_LEAVE_MS,
)
from ..overlay import clock_color, setup_overlay
from ..theme import (
    CARD_YELLOW,
    CHROMA,
    DANGER,
    DIVIDER,
    MUTED,
    PANEL_BG,
    PL_GREEN,
    TEXT_COLOR,
    make_glass,
)
from .match_pill import MatchPill


class TimelinePanel(tk.Toplevel):
    """
    Click-to-open match timeline.
    Position is frozen at open for ticker items (scroll-safe).
    Follows MatchPill anchors while dragging.
    """

    def __init__(self, app):
        super().__init__(app.root)
        setup_overlay(self, 0.96)
        self.withdraw()
        self.app = app
        self.match_id = None
        self._timer = None
        self._frozen = None  # (cx, top_y, bottom_y) screen coords
        self._follow = None  # MatchPill or None
        self._size = (220, 100)
        self.bg = tk.Label(self, bg=CHROMA, bd=0)
        self.bg.place(x=0, y=0)
        self.body = tk.Frame(self, bg=PANEL_BG)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

    @property
    def is_open(self):
        return self.match_id is not None

    def _cancel(self):
        if self._timer:
            try:
                self.after_cancel(self._timer)
            except tk.TclError:
                pass
            self._timer = None

    def _schedule_close(self, ms):
        self._cancel()
        self._timer = self.after(ms, self.close)

    def _on_enter(self, event):
        if self.is_open:
            self._cancel()

    def _on_leave(self, event):
        if self.is_open:
            self._schedule_close(TIMELINE_LEAVE_MS)

    def toggle(self, match, anchor, prefer_above_ticker=False):
        if self.is_open and str(self.match_id) == str(match["id"]):
            self.close()
        else:
            self.open(match, anchor, prefer_above_ticker=prefer_above_ticker)

    def close(self):
        self._cancel()
        self.match_id = None
        self._frozen = None
        self._follow = None
        self.app.scroll_locked = False
        try:
            self.withdraw()
        except tk.TclError:
            pass

    def open(self, match, anchor, prefer_above_ticker=False):
        # lock scroll immediately so the next animation frame cannot move the match
        self.app.scroll_locked = True
        self._cancel()
        for w in self.body.winfo_children():
            w.destroy()

        head = tk.Frame(self.body, bg=PANEL_BG)
        head.pack(fill=tk.X, pady=(0, 6))
        tk.Label(
            head,
            text=f"{match.get('league_short', '')}  {match['home']['tla']}  {match['home']['score']} - {match['away']['score']}  {match['away']['tla']}",
            bg=PANEL_BG,
            fg=TEXT_COLOR,
            font=FONT_UI_BOLD,
        ).pack(side=tk.LEFT)
        tk.Label(head, text=match["time"], bg=PANEL_BG, fg=clock_color(match["time"]), font=FONT_TINY).pack(
            side=tk.RIGHT, padx=(12, 0)
        )
        tk.Frame(self.body, bg=DIVIDER, height=1).pack(fill=tk.X, pady=(0, 6))

        events = self.app.match_details_cache.get(match["id"], [])
        if not events:
            tk.Label(self.body, text="No goals or cards yet", bg=PANEL_BG, fg=MUTED, font=FONT_UI).pack(anchor="w")
        for ev in events:
            row = tk.Frame(self.body, bg=PANEL_BG)
            row.pack(fill=tk.X, pady=2)
            tk.Label(row, text=ev["time"], bg=PANEL_BG, fg=MUTED, font=FONT_TINY, width=6, anchor="w").pack(
                side=tk.LEFT, anchor="n"
            )
            tag, col = {
                "goal": ("GOAL", PL_GREEN),
                "yellow": ("YELLOW", CARD_YELLOW),
                "red": ("RED", DANGER),
            }.get(ev["type"], ("", MUTED))
            tk.Label(row, text=tag, bg=PANEL_BG, fg=col, font=FONT_TINY, width=7, anchor="w").pack(
                side=tk.LEFT, anchor="n"
            )
            who = tk.Frame(row, bg=PANEL_BG)
            who.pack(side=tk.LEFT, anchor="n")
            tk.Label(who, text=ev["player"], bg=PANEL_BG, fg=TEXT_COLOR, font=FONT_UI, anchor="w").pack(anchor="w")
            if ev.get("assist"):
                tk.Label(
                    who, text=f"Assist: {ev['assist']}", bg=PANEL_BG, fg=MUTED, font=FONT_SMALL, anchor="w"
                ).pack(anchor="w")

        self.body.update_idletasks()
        w = max(220, self.body.winfo_reqwidth() + 32)
        h = self.body.winfo_reqheight() + 24
        self._size = (w, h)
        self._ph = ImageTk.PhotoImage(make_glass(w, h, radius=16))
        self.bg.configure(image=self._ph)
        self.body.place(x=16, y=12)

        # freeze screen geometry at click time
        self.update_idletasks()
        ax, ay = anchor.winfo_rootx(), anchor.winfo_rooty()
        aw, ah = max(1, anchor.winfo_width()), max(1, anchor.winfo_height())
        cx = ax + aw // 2
        if prefer_above_ticker:
            # always sit above the ticker capsule so scroll can't shove it under/aside
            try:
                top = self.app.root.winfo_rooty()
                bottom = top + self.app.root.winfo_height()
            except tk.TclError:
                top, bottom = ay, ay + ah
            self._frozen = (cx, top, bottom)
            self._follow = None
        else:
            self._frozen = (cx, ay, ay + ah)
            self._follow = anchor if isinstance(anchor, MatchPill) else None

        self.match_id = match["id"]
        self._place_from_frozen()
        self.deiconify()
        self.lift()
        self._schedule_close(TIMELINE_IDLE_MS)

    def _place_from_frozen(self):
        if not self._frozen:
            return
        w, h = self._size
        cx, top, bottom = self._frozen
        sw = self.winfo_screenwidth()
        x = min(max(8, cx - w // 2), sw - w - 8)
        y = top - h - 8
        if y < 8:
            y = bottom + 8
        self.geometry(f"{w}x{h}+{x}+{y}")

    def sync_follow(self):
        """Keep timeline glued to a dragged MatchPill."""
        if not self.is_open or not self._follow:
            return
        try:
            a = self._follow
            if not a.winfo_exists():
                return
            cx = a.winfo_rootx() + a.winfo_width() // 2
            top = a.winfo_rooty()
            bottom = top + a.winfo_height()
            self._frozen = (cx, top, bottom)
            self._place_from_frozen()
        except tk.TclError:
            pass

