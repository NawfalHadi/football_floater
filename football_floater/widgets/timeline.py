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
from ..icons import event_icon
from ..monitors import list_monitors
from ..overlay import clock_color, setup_overlay
from ..theme import CHROMA, DIVIDER, MUTED, PANEL_BG, TEXT_COLOR, make_glass
from .match_pill import MatchPill


class TimelinePanel(tk.Toplevel):
    """
    Click-to-open match timeline.
    Position is frozen at open for ticker items (scroll-safe).
    Follows MatchPill anchors while dragging.
    Placement prefers beside the anchor (esp. left of right-edge pills)
    and stays inside the selected monitor — never parks over pitch center
    when a side slot fits.
    """

    def __init__(self, app):
        super().__init__(app.root)
        setup_overlay(self, 0.96)
        self.withdraw()
        self.app = app
        self.match_id = None
        self._timer = None
        self._anchor_box = None  # (ax, ay, aw, ah) screen coords
        self._prefer_above_ticker = False
        self._follow = None  # MatchPill or None
        self._size = (220, 100)
        self._ph = None
        self._icon_refs = []
        self.bg = tk.Label(self, bg=CHROMA, bd=0)
        self.bg.place(x=0, y=0)
        self.body = tk.Frame(self, bg=PANEL_BG)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

    def _tk_icon(self, kind, size=14):
        ph = ImageTk.PhotoImage(event_icon(kind, size))
        self._icon_refs.append(ph)
        return ph

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
        self._anchor_box = None
        self._follow = None
        self._prefer_above_ticker = False
        self.app.scroll_locked = False
        try:
            self.withdraw()
        except tk.TclError:
            pass

    def open(self, match, anchor, prefer_above_ticker=False):
        # lock scroll immediately so the next animation frame cannot move the match
        self.app.scroll_locked = True
        self._cancel()
        self._prefer_above_ticker = prefer_above_ticker
        self._icon_refs = []
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
            kind = ev.get("type") or "other"
            if kind in ("goal", "penalty", "yellow", "red"):
                tk.Label(row, image=self._tk_icon(kind, 16), bg=PANEL_BG, bd=0).pack(
                    side=tk.LEFT, anchor="n", padx=(0, 6)
                )
            who = tk.Frame(row, bg=PANEL_BG)
            who.pack(side=tk.LEFT, anchor="n")
            tk.Label(who, text=ev["player"], bg=PANEL_BG, fg=TEXT_COLOR, font=FONT_UI, anchor="w").pack(anchor="w")
            if ev.get("assist"):
                assist_row = tk.Frame(who, bg=PANEL_BG)
                assist_row.pack(anchor="w")
                tk.Label(assist_row, image=self._tk_icon("assist", 13), bg=PANEL_BG, bd=0).pack(
                    side=tk.LEFT, padx=(0, 4)
                )
                tk.Label(
                    assist_row, text=ev["assist"], bg=PANEL_BG, fg=MUTED, font=FONT_SMALL, anchor="w"
                ).pack(side=tk.LEFT)

        self.body.update_idletasks()
        w = max(220, self.body.winfo_reqwidth() + 32)
        h = self.body.winfo_reqheight() + 24
        self._size = (w, h)
        self._ph = ImageTk.PhotoImage(make_glass(w, h, radius=16))
        self.bg.configure(image=self._ph)
        self.body.place(x=16, y=12)

        self.match_id = match["id"]
        self._follow = anchor if (not prefer_above_ticker and isinstance(anchor, MatchPill)) else None
        self._capture_anchor(anchor)
        self._place_smart()
        self.deiconify()
        self.lift()
        # second pass after map — root coords / size settle
        self.update_idletasks()
        self._capture_anchor(anchor)
        self._place_smart()
        self._schedule_close(TIMELINE_IDLE_MS)

    def reattach_ticker_anchor(self, anchor):
        """After ticker rebuild, glue timeline back to the new chip widget."""
        if not self.is_open or self._follow or anchor is None:
            return
        self._prefer_above_ticker = True
        self._capture_anchor(anchor)
        self._place_smart()

    def _capture_anchor(self, anchor):
        try:
            anchor.update_idletasks()
            ax, ay = int(anchor.winfo_rootx()), int(anchor.winfo_rooty())
            aw = max(1, int(anchor.winfo_width()))
            ah = max(1, int(anchor.winfo_height()))
            if self._prefer_above_ticker:
                # use full ticker capsule as vertical band
                try:
                    ay = int(self.app.root.winfo_rooty())
                    ah = max(1, int(self.app.root.winfo_height()))
                except tk.TclError:
                    pass
            self._anchor_box = (ax, ay, aw, ah)
        except tk.TclError:
            self._anchor_box = None

    def _monitor_box_for_anchor(self):
        """Clamp to the screen that actually holds the anchor (multi-monitor safe)."""
        ax, ay, aw, ah = self._anchor_box
        cx, cy = ax + aw // 2, ay + ah // 2
        try:
            for mon in list_monitors(self.app.root):
                if mon["x"] <= cx < mon["x"] + mon["w"] and mon["y"] <= cy < mon["y"] + mon["h"]:
                    return int(mon["x"]), int(mon["y"]), int(mon["w"]), int(mon["h"])
            mon = self.app.selected_monitor()
            return int(mon["x"]), int(mon["y"]), int(mon["w"]), int(mon["h"])
        except Exception:
            return 0, 0, int(self.winfo_screenwidth()), int(self.winfo_screenheight())

    def _place_smart(self):
        if not self._anchor_box:
            return
        ax, ay, aw, ah = self._anchor_box
        w, h = self._size
        mx, my, mw, mh = self._monitor_box_for_anchor()
        margin = 8
        min_x, min_y = mx + margin, my + margin
        max_x = mx + mw - w - margin
        max_y = my + mh - h - margin

        def clamp(x, y):
            cx = min(max(min_x, x), max(min_x, max_x))
            cy = min(max(min_y, y), max(min_y, max_y))
            return int(cx), int(cy)

        def overflow(x, y):
            ox = max(0, min_x - x) + max(0, x - max_x) if max_x >= min_x else abs(x - min_x)
            oy = max(0, min_y - y) + max(0, y - max_y) if max_y >= min_y else abs(y - min_y)
            return ox + oy

        acx, acy = ax + aw / 2, ay + ah / 2

        if self._prefer_above_ticker:
            # Ticker click: prefer ABOVE the bar; only flip below if above clips.
            above = (acx - w / 2, ay - h - margin)
            below = (acx - w / 2, ay + ah + margin)
            ov_a, ov_b = overflow(*above), overflow(*below)
            if ov_a == 0:
                best = above
            elif ov_b == 0:
                best = below
            else:
                best = above if ov_a <= ov_b else below
            x, y = clamp(*best)
            self.geometry(f"{w}x{h}+{x}+{y}")
            return

        # Free-float pill: side slots first (stack is usually right edge).
        mcx, mcy = mx + mw / 2, my + mh / 2
        candidates = [
            (ax - w - margin, acy - h / 2),  # left of pill
            (ax + aw + margin, acy - h / 2),  # right of pill
            (ax - w - margin, ay),  # left, top-aligned
            (ax - w - margin, ay + ah - h),  # left, bottom-aligned
            (acx - w / 2, ay - h - margin),  # above
            (acx - w / 2, ay + ah + margin),  # below
        ]

        best = None
        best_score = None
        for x, y in candidates:
            ov = overflow(x, y)
            dist = abs((x + w / 2) - acx) + abs((y + h / 2) - acy)
            covers_center = 1 if (x <= mcx <= x + w and y <= mcy <= y + h) else 0
            score = (ov, covers_center, dist)
            if best_score is None or score < best_score:
                best_score = score
                best = (x, y)

        x, y = clamp(*best)
        self.geometry(f"{w}x{h}+{x}+{y}")

    def sync_follow(self):
        """Keep timeline glued to a dragged MatchPill."""
        if not self.is_open or not self._follow:
            return
        try:
            a = self._follow
            if not a.winfo_exists():
                return
            self._capture_anchor(a)
            self._place_smart()
        except tk.TclError:
            pass
