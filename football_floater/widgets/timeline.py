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
from ..matchday import countdown_text
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
        self._clock_lbl = None
        self.bg = tk.Label(self, bg=CHROMA, bd=0)
        self.bg.place(x=0, y=0)
        self.body = tk.Frame(self, bg=PANEL_BG)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

    def _tk_icon(self, kind, size=14):
        ph = ImageTk.PhotoImage(event_icon(kind, size))
        self._icon_refs.append(ph)
        return ph

    @staticmethod
    def _group_events(events):
        """Collapse subs that share a minute into one block. Other events stay single rows."""
        grouped = []
        bucket = []
        bucket_time = None
        for ev in events:
            if ev.get("type") == "sub" and bucket and ev.get("time") == bucket_time:
                bucket.append(ev)
                continue
            if bucket:
                grouped.append(("subs", bucket))
                bucket = []
            if ev.get("type") == "sub":
                bucket = [ev]
                bucket_time = ev.get("time")
            else:
                grouped.append(("event", [ev]))
                bucket_time = None
        if bucket:
            grouped.append(("subs", bucket))
        return grouped

    def _columns(self, minute):
        row = tk.Frame(self.body, bg=PANEL_BG)
        row.pack(fill=tk.X, pady=2)
        row.columnconfigure(0, weight=1, minsize=120, uniform="side")
        row.columnconfigure(1, weight=0)
        row.columnconfigure(2, weight=1, minsize=120, uniform="side")
        left = tk.Frame(row, bg=PANEL_BG)
        mid = tk.Frame(row, bg=PANEL_BG)
        right = tk.Frame(row, bg=PANEL_BG)
        left.grid(row=0, column=0, sticky="nsew")
        mid.grid(row=0, column=1, sticky="n", padx=4)
        right.grid(row=0, column=2, sticky="nsew")
        tk.Label(mid, text=minute or "", bg=PANEL_BG, fg=MUTED, font=FONT_TINY, width=5).pack()
        return left, right

    def _event_names(self, parent, ev, side):
        anchor = "e" if side == "home" else "w"
        tk.Label(parent, text=ev.get("player") or "?", bg=PANEL_BG, fg=TEXT_COLOR, font=FONT_UI, anchor=anchor).pack(
            anchor=anchor
        )
        if ev.get("assist"):
            tk.Label(parent, text=ev["assist"], bg=PANEL_BG, fg=MUTED, font=FONT_SMALL, anchor=anchor).pack(anchor=anchor)

    def _render_event(self, ev):
        side = "away" if ev.get("side") == "away" else "home"
        left, right = self._columns(ev.get("time"))
        parent = right if side == "away" else left
        block = tk.Frame(parent, bg=PANEL_BG)
        block.pack(anchor="e" if side == "home" else "w")
        names = tk.Frame(block, bg=PANEL_BG)
        kind = ev.get("type") or "other"
        icon = None
        if kind in ("goal", "penalty", "yellow", "red"):
            icon = tk.Label(block, image=self._tk_icon(kind, 16), bg=PANEL_BG, bd=0)
        self._event_names(names, ev, side)
        if side == "home":
            names.pack(side=tk.LEFT, anchor="n")
            if icon:
                icon.pack(side=tk.LEFT, anchor="n", padx=(6, 0))
        else:
            if icon:
                icon.pack(side=tk.LEFT, anchor="n", padx=(0, 6))
            names.pack(side=tk.LEFT, anchor="n")

    def _fill_sub_side(self, parent, subs, side):
        block = tk.Frame(parent, bg=PANEL_BG)
        block.pack(anchor="e" if side == "home" else "w")
        names = tk.Frame(block, bg=PANEL_BG)
        icon = tk.Label(block, image=self._tk_icon("sub", 16), bg=PANEL_BG, bd=0)
        anchor = "e" if side == "home" else "w"
        for i, ev in enumerate(subs):
            pair = tk.Frame(names, bg=PANEL_BG)
            pair.pack(anchor=anchor, pady=(4 if i else 0, 0))
            on_line = tk.Frame(pair, bg=PANEL_BG)
            on_line.pack(anchor=anchor)
            tk.Label(on_line, text=ev.get("player") or "?", bg=PANEL_BG, fg=TEXT_COLOR, font=FONT_UI).pack(side=tk.LEFT)
            tk.Label(on_line, text=" on", bg=PANEL_BG, fg=MUTED, font=FONT_SMALL).pack(side=tk.LEFT)
            if ev.get("off"):
                tk.Label(pair, text=f"{ev['off']} off", bg=PANEL_BG, fg=MUTED, font=FONT_SMALL, anchor=anchor).pack(
                    anchor=anchor
                )
        if side == "home":
            names.pack(side=tk.LEFT, anchor="n")
            icon.pack(side=tk.LEFT, anchor="n", padx=(6, 0))
        else:
            icon.pack(side=tk.LEFT, anchor="n", padx=(0, 6))
            names.pack(side=tk.LEFT, anchor="n")

    def _render_sub_group(self, subs):
        """One minute in the middle. Home swaps on the left, away swaps on the right."""
        left, right = self._columns(subs[0].get("time"))
        home = [ev for ev in subs if ev.get("side") != "away"]
        away = [ev for ev in subs if ev.get("side") == "away"]
        if home:
            self._fill_sub_side(left, home, "home")
        if away:
            self._fill_sub_side(right, away, "away")

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

    def _fill(self, match):
        head = tk.Frame(self.body, bg=PANEL_BG)
        head.pack(fill=tk.X, pady=(0, 6))
        head.columnconfigure(0, weight=1, uniform="head")
        head.columnconfigure(1, weight=0)
        head.columnconfigure(2, weight=1, uniform="head")
        tk.Label(
            head,
            text=f"{match.get('league_short', '')}  {match['home']['tla']}".strip(),
            bg=PANEL_BG,
            fg=TEXT_COLOR,
            font=FONT_UI_BOLD,
            anchor="w",
        ).grid(row=0, column=0, sticky="w")
        tk.Label(
            head,
            text=f"{match['home']['score']} - {match['away']['score']}",
            bg=PANEL_BG,
            fg=TEXT_COLOR,
            font=FONT_UI_BOLD,
        ).grid(row=0, column=1, padx=8)
        tk.Label(head, text=match["away"]["tla"], bg=PANEL_BG, fg=TEXT_COLOR, font=FONT_UI_BOLD, anchor="e").grid(
            row=0, column=2, sticky="e"
        )
        clock_text = match["time"]
        if match.get("state") == "pre":
            clock_text = countdown_text(match.get("kickoff")) or match["time"]
        self._clock_lbl = tk.Label(head, text=clock_text, bg=PANEL_BG, fg=clock_color(clock_text), font=FONT_TINY)
        self._clock_lbl.grid(row=1, column=1, pady=(2, 0))
        tk.Frame(self.body, bg=DIVIDER, height=1).pack(fill=tk.X, pady=(0, 6))

        events = self.app.match_details_cache.get(match["id"], [])
        if not events:
            tk.Label(self.body, text="No goals, cards, or subs yet", bg=PANEL_BG, fg=MUTED, font=FONT_UI).pack(
                anchor="w"
            )
        for kind, evs in self._group_events(events):
            if kind == "subs":
                self._render_sub_group(evs)
            else:
                self._render_event(evs[0])

    def open(self, match, anchor, prefer_above_ticker=False):
        # lock scroll immediately so the next animation frame cannot move the match
        self.app.scroll_locked = True
        self._cancel()
        self._prefer_above_ticker = prefer_above_ticker
        self._icon_refs = []
        for w in self.body.winfo_children():
            w.destroy()
        self._fill(match)
        self.body.update_idletasks()
        w = max(340, self.body.winfo_reqwidth() + 32)
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

    def refresh_open(self):
        """Rebuild rows when a refresh brings new subs, without closing the panel."""
        if not self.is_open:
            return
        match = next((m for m in self.app.current_matches if str(m["id"]) == str(self.match_id)), None)
        if not match:
            return
        self._icon_refs = []
        for w in self.body.winfo_children():
            w.destroy()
        self._fill(match)
        self.body.update_idletasks()
        w = max(340, self.body.winfo_reqwidth() + 32)
        h = self.body.winfo_reqheight() + 24
        self._size = (w, h)
        self._ph = ImageTk.PhotoImage(make_glass(w, h, radius=16))
        self.bg.configure(image=self._ph)
        self.body.place(x=16, y=12)
        self._place_smart()

    def refresh_countdown(self):
        if not self.is_open or self._clock_lbl is None:
            return
        match = next((m for m in self.app.current_matches if str(m["id"]) == str(self.match_id)), None)
        if not match or match.get("state") != "pre":
            return
        text = countdown_text(match.get("kickoff"))
        if not text:
            return
        try:
            if self._clock_lbl.cget("text") != text:
                self._clock_lbl.configure(text=text, fg=clock_color(text))
        except tk.TclError:
            pass

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
