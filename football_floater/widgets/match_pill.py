"""Free-float per-match pill — in-pill wipe alerts; width can grow for long sub names."""
import time
import tkinter as tk
from PIL import ImageTk

from ..config import (
    DRAG_THRESHOLD,
    FLOAT_ALERT_GOAL_S,
    FLOAT_ALERT_SUB_S,
    FONT_SCORE,
    FONT_SMALL,
    FONT_TINY,
    PILL_H,
    PILL_ICON,
    PILL_W,
)
from ..icons import event_icon
from ..matchday import COUNTDOWN_WIDTH, countdown_text
from ..overlay import clock_color, setup_overlay, window_fill
from ..theme import DANGER, MUTED, PANEL_BG, PANEL_RIM, PL_GREEN, PL_PINK, PL_PURPLE, TEXT_COLOR, make_glass

_TICK_MS = 32
_GOAL_HOLD_MS = int(FLOAT_ALERT_GOAL_S * 1000)
_SUB_HOLD_MS = int(FLOAT_ALERT_SUB_S * 1000)
_EXPAND_MS = 300
_SHRINK_MS = 260
_SCALE_IN_MS = 340
_GOAL_WIPE_MS = 380
_WIPE_OUT_MS = 280
_WIPE_PX = 36
_SLOT_W = PILL_ICON + 4
_SLOT_SUB_W = PILL_ICON + 20  # crest + ↑↓ beside it
_PILL_PAD_X = 14
_MAX_PILL_W = 320
# Goal/pen rim blink — slow, few pulses, then steady (not a strobe).
_BLINK_PERIOD_MS = 780
_BLINK_COUNT = 3
_BLINK_ON_FRAC = 0.58


def _ease_out_cubic(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1.0 - (1.0 - t) ** 3


def _ease_in_cubic(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t ** 3


def _tag_kind(tag: str) -> str:
    t = (tag or "GOAL").upper()
    if t == "SUB":
        return "sub"
    if t in ("PEN", "PENALTY"):
        return "penalty"
    return "goal"


def _split_scorer(text: str) -> tuple[str, str]:
    text = (text or "").strip()
    if not text:
        return "?", ""
    parts = text.rsplit(" ", 1)
    if len(parts) == 2 and "'" in parts[1]:
        return parts[0].strip() or "?", parts[1].strip()
    return text, ""


def _expand_slides(alerts: list) -> list:
    slides = []
    for alert in alerts or []:
        tag = (alert.get("tag") or "GOAL").upper()
        expires = alert.get("expires", 0)
        key = alert.get("key")
        if tag == "SUB":
            clock = (alert.get("text") or "").strip()
            lines = alert.get("lines") or [{"on": "?", "off": "", "side": None}]
            for i, line in enumerate(lines):
                side = line.get("side")
                if side not in ("home", "away"):
                    side = None
                slides.append(
                    {
                        "tag": "SUB",
                        "player": (line.get("on") or "?").strip(),
                        "extra": (line.get("off") or "").strip(),
                        "clock": clock,
                        "side": side,
                        "expires": expires,
                        "key": key,
                        "slide": i,
                    }
                )
            continue
        player, minute = _split_scorer(alert.get("text") or "")
        side = alert.get("side")
        if side not in ("home", "away"):
            side = None
        slides.append(
            {
                "tag": tag,
                "player": player,
                "extra": (alert.get("detail") or "").strip(),
                "clock": minute,
                "side": side,
                "expires": expires,
                "key": key,
                "slide": 0,
            }
        )
    return slides


def _goal_slide_copy(slide: dict) -> tuple[str, str]:
    """Scorer on top (minute lives in side slot like subs); assist or GOAL/PEN under."""
    tag = slide.get("tag") or "GOAL"
    player = (slide.get("player") or "?").strip()
    assist = (slide.get("extra") or "").strip()
    if assist:
        return player, assist
    label = "PEN" if tag in ("PEN", "PENALTY") else "GOAL"
    return player, label


class MatchPill(tk.Toplevel):
    def __init__(self, app, match, x, y):
        super().__init__(app.root)
        setup_overlay(self)
        self.app = app
        self.match = match
        self._press = None
        self._dragging = False

        self._alerts = []
        self._slides = []
        self._slide_i = 0
        self._job = None
        self._icon_ph = None
        self._layout = "idle"
        self._event_side = None

        self._phase = "idle"
        self._phase_t0 = 0.0
        self._hold_until = 0.0
        self._pill_w = PILL_W
        self._width_from = PILL_W
        self._width_to = PILL_W
        self._anchor_left = int(x)
        self._anchor_right = int(x) + PILL_W
        self._grow_dir = "right"  # "right" = left edge fixed; "left" = right edge fixed
        self._alert_rim = None
        self._blink_t0 = 0.0
        self._blink_rim_drawn = None
        self._after_out = "idle"  # "idle" | "next" | "shrink"

        # Shared idle glass from app (one draw); alert rims still make a local copy.
        self._ph = app.pill_glass_image()
        self.bg = tk.Label(self, image=self._ph, bg=window_fill(), bd=0)
        self.bg.place(x=0, y=0, relwidth=1, relheight=1)

        self.body = tk.Frame(self, bg=PANEL_BG)
        self.body.place(x=_PILL_PAD_X, y=8, width=PILL_W - 2 * _PILL_PAD_X, height=PILL_H - 16)

        # Fixed slots: left crest/arrows/time · mid content · right crest/arrows/time
        self.slot_l = tk.Frame(self.body, bg=PANEL_BG, width=_SLOT_W)
        self.slot_l.pack(side=tk.LEFT, fill=tk.Y)
        self.slot_l.pack_propagate(False)
        self.slot_r = tk.Frame(self.body, bg=PANEL_BG, width=_SLOT_W)
        self.slot_r.pack(side=tk.RIGHT, fill=tk.Y)
        self.slot_r.pack_propagate(False)

        self.lbl_home = tk.Label(self.slot_l, bg=PANEL_BG, fg=TEXT_COLOR, font=FONT_TINY, bd=0)
        self.lbl_away = tk.Label(self.slot_r, bg=PANEL_BG, fg=TEXT_COLOR, font=FONT_TINY, bd=0)
        self.lbl_time_l = tk.Label(self.slot_l, bg=PANEL_BG, fg=MUTED, font=FONT_TINY, bd=0)
        self.lbl_time_r = tk.Label(self.slot_r, bg=PANEL_BG, fg=MUTED, font=FONT_TINY, bd=0)

        self.arrows_l = tk.Frame(self.slot_l, bg=PANEL_BG)
        self.arrows_r = tk.Frame(self.slot_r, bg=PANEL_BG)
        self.lbl_arr_up_l = tk.Label(self.arrows_l, text="↑", bg=PANEL_BG, fg=PL_GREEN, font=FONT_SCORE, bd=0)
        self.lbl_arr_dn_l = tk.Label(self.arrows_l, text="↓", bg=PANEL_BG, fg=DANGER, font=FONT_SCORE, bd=0)
        self.lbl_arr_up_l.pack()
        self.lbl_arr_dn_l.pack()
        self.lbl_arr_up_r = tk.Label(self.arrows_r, text="↑", bg=PANEL_BG, fg=PL_GREEN, font=FONT_SCORE, bd=0)
        self.lbl_arr_dn_r = tk.Label(self.arrows_r, text="↓", bg=PANEL_BG, fg=DANGER, font=FONT_SCORE, bd=0)
        self.lbl_arr_up_r.pack()
        self.lbl_arr_dn_r.pack()

        self.mid = tk.Frame(self.body, bg=PANEL_BG)
        self.mid.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)

        self.clip = tk.Frame(self.mid, bg=PANEL_BG)
        self.clip.pack(expand=True, fill=tk.BOTH)
        self.clip.pack_propagate(False)

        # Idle / goal mid
        self.goal_host = tk.Frame(self.clip, bg=PANEL_BG)
        self.lbl_score = tk.Label(self.goal_host, bg=PANEL_BG, fg=TEXT_COLOR, font=FONT_SCORE)
        self.lbl_clock = tk.Label(
            self.goal_host, bg=PANEL_BG, font=FONT_SMALL, width=COUNTDOWN_WIDTH, anchor="center"
        )
        self.row_alert = tk.Frame(self.goal_host, bg=PANEL_BG)
        self.lbl_icon = tk.Label(self.row_alert, bg=PANEL_BG, bd=0)
        self.lbl_league = tk.Label(self.row_alert, bg=PANEL_BG, fg=MUTED, font=FONT_TINY, anchor="center")

        # Sub mid — centered names only
        self.sub_host = tk.Frame(self.clip, bg=PANEL_BG)
        self.lbl_sub_on = tk.Label(self.sub_host, text="", bg=PANEL_BG, fg=PL_GREEN, font=FONT_TINY, anchor="center")
        self.lbl_sub_off = tk.Label(self.sub_host, text="", bg=PANEL_BG, fg=DANGER, font=FONT_TINY, anchor="center")

        bind_widgets = [
            self.bg,
            self.body,
            self.slot_l,
            self.slot_r,
            self.mid,
            self.clip,
            self.goal_host,
            self.sub_host,
            self.row_alert,
            self.arrows_l,
            self.arrows_r,
            self.lbl_home,
            self.lbl_away,
            self.lbl_time_l,
            self.lbl_time_r,
            self.lbl_score,
            self.lbl_clock,
            self.lbl_league,
            self.lbl_icon,
            self.lbl_sub_on,
            self.lbl_sub_off,
            self.lbl_arr_up_l,
            self.lbl_arr_dn_l,
            self.lbl_arr_up_r,
            self.lbl_arr_dn_r,
        ]
        for w in bind_widgets:
            w.bind("<ButtonPress-1>", self._on_press)
            w.bind("<B1-Motion>", self._on_motion)
            w.bind("<ButtonRelease-1>", self._on_release)
            w.bind("<Button-3>", self._on_menu)

        self._pos = (int(x), int(y))
        self.geometry(f"{self._pill_w}x{PILL_H}+{self._pos[0]}+{self._pos[1]}")
        # Some WMs (Cosmic/Wayland) ignore pre-map geometry — re-apply on Map.
        self.bind("<Map>", self._on_map)
        self._layout = "idle"
        self._goal_mid_placed = False
        self._pack_idle_mid()
        self._show_slot_crests()
        # Must place goal_host into clip — packing labels alone leaves mid blank.
        self._place_goal_host(0)
        self.update_match(match)

    @property
    def match_id(self):
        return str(self.match["id"])

    def move_to(self, x, y):
        self._pos = (int(x), int(y))
        self._anchor_left = self._pos[0]
        self._anchor_right = self._pos[0] + self._pill_w
        try:
            self.geometry(f"{self._pill_w}x{PILL_H}+{self._pos[0]}+{self._pos[1]}")
        except tk.TclError:
            pass

    def _on_map(self, _event=None):
        self.move_to(*self._pos)

    def _set_pill_width(self, width, *, rim=None, remake=True):
        """Resize pill; keep the anchored edge fixed (grow left or right)."""
        width = int(max(PILL_W, min(_MAX_PILL_W, width)))
        y = self._pos[1]
        if self._grow_dir == "left":
            x = int(self._anchor_right - width)
        else:
            x = int(self._anchor_left)
        self._pill_w = width
        self._pos = (x, y)
        try:
            self.body.place_configure(width=width - 2 * _PILL_PAD_X)
        except tk.TclError:
            pass
        if remake:
            use_rim = rim if rim is not None else self._alert_rim
            try:
                self._ph = ImageTk.PhotoImage(make_glass(width, PILL_H, rim=use_rim or PANEL_RIM))
                self.bg.configure(image=self._ph)
            except Exception:
                pass
        try:
            self.geometry(f"{width}x{PILL_H}+{x}+{y}")
        except tk.TclError:
            pass

    def _pick_grow_dir(self):
        try:
            mon = self.app.selected_monitor()
            cx = self._pos[0] + self._pill_w / 2
            mid = mon["x"] + mon.get("ww", mon["w"]) / 2
        except Exception:
            mid = 960
            cx = self._pos[0] + self._pill_w / 2
        # Left of screen → expand right (left edge fixed). Right → expand left.
        self._grow_dir = "right" if cx < mid else "left"
        self._anchor_left = self._pos[0]
        self._anchor_right = self._pos[0] + self._pill_w

    def _max_pill_w(self):
        try:
            mon = self.app.selected_monitor()
            return min(_MAX_PILL_W, int(mon.get("ww", mon["w"]) * 0.45))
        except Exception:
            return _MAX_PILL_W

    def _width_for_mid(self, text_w, left_slot, right_slot):
        need = 2 * _PILL_PAD_X + left_slot + right_slot + max(48, int(text_w)) + 12
        return int(max(PILL_W, min(self._max_pill_w(), need)))

    def _measure_sub_width(self, on_name, off_name):
        """Pill width so both sub names fit without clipping into crests."""
        on_name = (on_name or "?").strip()
        off_name = (off_name or "—").strip()
        try:
            self.lbl_sub_on.configure(text=on_name)
            self.lbl_sub_off.configure(text=off_name)
            self.lbl_sub_on.update_idletasks()
            self.lbl_sub_off.update_idletasks()
            text_w = max(self.lbl_sub_on.winfo_reqwidth(), self.lbl_sub_off.winfo_reqwidth(), 48)
        except tk.TclError:
            text_w = max(len(on_name), len(off_name), 8) * 7
        side = self._event_side
        left_slot = _SLOT_SUB_W if side != "away" else _SLOT_W
        right_slot = _SLOT_SUB_W if side == "away" else _SLOT_W
        return self._width_for_mid(text_w, left_slot, right_slot)

    def _measure_goal_width(self):
        """Pill width so scorer + assist fit (same expand idea as subs)."""
        try:
            self.lbl_clock.update_idletasks()
            self.row_alert.update_idletasks()
            self.lbl_league.update_idletasks()
            self.lbl_icon.update_idletasks()
            text_w = max(
                self.lbl_clock.winfo_reqwidth(),
                self.row_alert.winfo_reqwidth(),
                self.lbl_league.winfo_reqwidth() + self.lbl_icon.winfo_reqwidth() + 4,
                48,
            )
        except tk.TclError:
            head = ""
            try:
                head = self.lbl_clock.cget("text") or ""
            except tk.TclError:
                pass
            text_w = max(len(head) * 7, 48)
        # Goal keeps both side slots at _SLOT_W (one crest, one blank).
        return self._width_for_mid(text_w, _SLOT_W, _SLOT_W)

    def _place_alert_scaled(self, scale=1.0, x_off=0.0):
        if self._layout == "sub":
            self._place_sub_host(x_off=x_off, scale=scale)
        else:
            self._place_goal_host(x_off=x_off, scale=scale)

    def _begin_width_then_scale(self, target_w):
        """Shared expand → scale-in gate for goal/pen/sub."""
        self._pick_grow_dir()
        self._width_from = self._pill_w
        self._width_to = target_w
        if abs(target_w - self._pill_w) > 2:
            self._phase = "expand"
            self._place_alert_scaled(scale=0.82)
        else:
            self._phase = "scale_in"
            self._place_alert_scaled(x_off=_WIPE_PX, scale=0.82)

    def _set_alert_chrome(self, tag):
        tag = (tag or "GOAL").upper()
        if tag == "SUB":
            self._alert_rim = PL_GREEN
            self._blink_t0 = 0.0
        elif tag in ("PEN", "PENALTY"):
            self._alert_rim = PL_PINK
            self._blink_t0 = time.time()
        else:
            self._alert_rim = PL_GREEN
            self._blink_t0 = time.time()
        self._blink_rim_drawn = None
        self._set_pill_width(self._pill_w, rim=self._alert_rim, remake=True)

    def _clear_alert_chrome(self):
        self._alert_rim = None
        self._blink_t0 = 0.0
        self._blink_rim_drawn = None
        try:
            self._ph = self.app.pill_glass_image()
            self.bg.configure(image=self._ph)
        except Exception:
            pass

    def _tick_goal_blink(self):
        """Soft rim blink for goal/pen only — 3 slow pulses, then solid accent."""
        if self._layout != "goal" or not self._alert_rim or not self._blink_t0:
            return
        elapsed = (time.time() - self._blink_t0) * 1000.0
        total = _BLINK_PERIOD_MS * _BLINK_COUNT
        if elapsed >= total:
            want = self._alert_rim
        else:
            cycle = elapsed % _BLINK_PERIOD_MS
            want = self._alert_rim if cycle < _BLINK_PERIOD_MS * _BLINK_ON_FRAC else PANEL_RIM
        if want == self._blink_rim_drawn:
            return
        self._blink_rim_drawn = want
        self._set_pill_width(self._pill_w, rim=want, remake=True)

    def update_match(self, match):
        self.match = match
        if self._layout == "idle":
            self.refresh_crests()
            self._paint_idle_mid()
        else:
            self.refresh_crests()

    def _clear_slot(self, slot):
        for child in slot.winfo_children():
            child.pack_forget()

    def _set_slot_width(self, left_w, right_w):
        self.slot_l.configure(width=left_w)
        self.slot_r.configure(width=right_w)

    def _show_slot_crests(self):
        self._set_slot_width(_SLOT_W, _SLOT_W)
        self._clear_slot(self.slot_l)
        self._clear_slot(self.slot_r)
        self.lbl_home.pack(expand=True)
        self.lbl_away.pack(expand=True)
        self._paint_crest("home", self.lbl_home)
        self._paint_crest("away", self.lbl_away)

    def refresh_crests(self):
        """Swap crest images in place — no pack_forget (avoids idle flicker)."""
        if self._layout == "idle":
            self._paint_crest("home", self.lbl_home)
            self._paint_crest("away", self.lbl_away)
            return
        side = self._event_side
        if self._layout == "sub":
            if side == "away":
                self._paint_crest("away", self.lbl_away)
            else:
                self._paint_crest("home", self.lbl_home)
            return
        if side == "away":
            self._paint_crest("away", self.lbl_away)
        elif side == "home":
            self._paint_crest("home", self.lbl_home)

    def _paint_crest(self, side, lbl):
        img = self.app.get_team_icon(self.match[side]["tla"], self.match[side]["logo"], size=PILL_ICON)
        if img:
            if getattr(lbl, "image", None) is img:
                return
            lbl.configure(image=img, text="")
            lbl.image = img
        else:
            tla = self.match[side]["tla"]
            try:
                if lbl.cget("text") == tla and not lbl.cget("image"):
                    return
            except tk.TclError:
                pass
            lbl.configure(image="", text=tla)
            lbl.image = None

    def _apply_event_slots(self, side, kind):
        """
        GOAL/PEN/SUB: crest on event side, minute on the opposite side (subs also get ↑↓).
        """
        self._event_side = side if side in ("home", "away") else None
        self._clear_slot(self.slot_l)
        self._clear_slot(self.slot_r)
        clock = ""
        slide = self._current_slide()
        if slide:
            clock = slide.get("clock") or ""
        clock_txt = clock or "—"

        if kind == "sub":
            if side == "away":
                self._set_slot_width(_SLOT_W, _SLOT_SUB_W)
                self.lbl_time_l.configure(text=clock_txt)
                self.lbl_time_l.pack(expand=True)
                self.lbl_away.pack(side=tk.LEFT, padx=(0, 1))
                self._paint_crest("away", self.lbl_away)
                self.arrows_r.pack(side=tk.LEFT)
            else:
                # home or unknown → crest+arrows left, time right
                self._set_slot_width(_SLOT_SUB_W, _SLOT_W)
                self.lbl_home.pack(side=tk.LEFT, padx=(0, 1))
                self._paint_crest("home", self.lbl_home)
                self.arrows_l.pack(side=tk.LEFT)
                self.lbl_time_r.configure(text=clock_txt)
                self.lbl_time_r.pack(expand=True)
            return

        # goal / pen — same minute placement as subs, crest only (no arrows)
        self._set_slot_width(_SLOT_W, _SLOT_W)
        if side == "away":
            self.lbl_time_l.configure(text=clock_txt)
            self.lbl_time_l.pack(expand=True)
            self.lbl_away.pack(expand=True)
            self._paint_crest("away", self.lbl_away)
        else:
            # home or unknown → crest left, minute right
            self.lbl_home.pack(expand=True)
            self._paint_crest("home", self.lbl_home)
            self.lbl_time_r.configure(text=clock_txt)
            self.lbl_time_r.pack(expand=True)

    def refresh_countdown(self):
        if self._layout != "idle" or self.match.get("state") != "pre":
            return
        text = countdown_text(self.match.get("kickoff"))
        if not text:
            return
        try:
            if self.lbl_clock.cget("text") != text:
                self.lbl_clock.configure(text=text, fg=clock_color(text))
        except tk.TclError:
            pass

    def sync_alerts(self, alerts):
        now = time.time()
        live = [a for a in (alerts or []) if now < a.get("expires", 0)]
        slides = _expand_slides(live)
        ids = [
            (s.get("key"), s.get("slide"), s.get("player"), s.get("extra"), s.get("side"))
            for s in slides
        ]
        prev = [
            (s.get("key"), s.get("slide"), s.get("player"), s.get("extra"), s.get("side"))
            for s in self._slides
        ]
        self._alerts = live
        # Same alert set (including both empty) → do nothing. Re-entering idle
        # every animate frame was the crazy flicker.
        if ids == prev:
            self._slides = slides
            return
        cur = self._current_slide() if self._slides else None
        self._slides = slides
        self._slide_i = 0
        if cur and slides:
            cur_id = (
                cur.get("key"),
                cur.get("slide"),
                cur.get("player"),
                cur.get("extra"),
                cur.get("side"),
            )
            if cur_id in ids:
                self._slide_i = ids.index(cur_id)
        if not slides:
            self._stop_loop()
            if self._layout != "idle":
                self._show_idle()
            return
        self._start_slide()
        self._ensure_loop()

    def _clip_size(self):
        try:
            self.mid.update_idletasks()
            w = max(48, self.mid.winfo_width())
            h = max(28, self.mid.winfo_height())
        except tk.TclError:
            w, h = max(48, PILL_W - 28 - 2 * _SLOT_W), PILL_H - 16
        try:
            self.clip.configure(width=w, height=h)
        except tk.TclError:
            pass
        return w, h

    def _pack_idle_mid(self):
        """Canonical idle stack: score → clock → league (never append score at bottom)."""
        for w in (self.lbl_score, self.lbl_clock, self.row_alert, self.lbl_icon, self.lbl_league):
            try:
                w.place_forget()
            except tk.TclError:
                pass
            w.pack_forget()
        self.lbl_score.pack()
        self.lbl_clock.pack()
        self.lbl_icon.pack(side=tk.LEFT, padx=(0, 2))
        self.lbl_league.pack(side=tk.LEFT)
        self.row_alert.pack()

    def _pack_goal_mid(self):
        """Scorer + minute / assist — vertically centered in the pill mid."""
        for w in (self.lbl_score, self.lbl_clock, self.row_alert, self.lbl_icon, self.lbl_league):
            w.pack_forget()
            try:
                w.place_forget()
            except tk.TclError:
                pass
        self.lbl_clock.configure(anchor="center", width=0)
        self.lbl_icon.pack(side=tk.LEFT, padx=(0, 2))
        self.lbl_league.configure(anchor="w")
        self.lbl_league.pack(side=tk.LEFT)
        # Place after host is mapped; _place_goal_host recenters each tick.
        self._goal_mid_placed = True

    def _place_goal_host(self, x_off: float = 0, scale: float = 1.0):
        w, h = self._clip_size()
        self.sub_host.place_forget()
        scale = max(0.72, min(1.0, scale))
        sw, sh = max(1, int(w * scale)), max(1, int(h * scale))
        ox = (w - sw) // 2 + int(x_off)
        oy = (h - sh) // 2
        self.goal_host.place(x=ox, y=oy, width=sw, height=sh)
        if getattr(self, "_goal_mid_placed", False) and self._layout == "goal":
            self.lbl_clock.place(relx=0.5, rely=0.38, anchor="center")
            self.row_alert.place(relx=0.5, rely=0.68, anchor="center")

    def _place_sub_host(self, y_off: float = 0, x_off: float = 0, scale: float = 1.0):
        w, h = self._clip_size()
        self.goal_host.place_forget()
        scale = max(0.72, min(1.0, scale))
        sw, sh = max(1, int(w * scale)), max(1, int(h * scale))
        ox = (w - sw) // 2 + int(x_off)
        oy = (h - sh) // 2
        self.sub_host.place(x=ox, y=oy, width=sw, height=sh)
        self.lbl_sub_on.place(relx=0.5, rely=0.32, anchor="center")
        self.lbl_sub_off.place(relx=0.5, rely=0.68, anchor="center")

    def _show_idle(self):
        self._layout = "idle"
        self._phase = "idle"
        self._event_side = None
        self._goal_mid_placed = False
        self._after_out = "idle"
        if self._pill_w != PILL_W:
            self._grow_dir = "right" if self._grow_dir == "right" else "left"
            # Snap anchors to current edges before shrink-to-idle.
            self._anchor_left = self._pos[0]
            self._anchor_right = self._pos[0] + self._pill_w
            self._set_pill_width(PILL_W, rim=PANEL_RIM, remake=False)
        self._clear_alert_chrome()
        self._show_slot_crests()
        self._pack_idle_mid()
        self._place_goal_host(0, scale=1.0)
        self._paint_idle_mid()

    def _paint_idle_mid(self):
        clock_text = self.match["time"]
        if self.match.get("state") == "pre":
            clock_text = countdown_text(self.match.get("kickoff")) or self.match["time"]
        score = f"{self.match['home']['score']} - {self.match['away']['score']}"
        try:
            if self.lbl_score.cget("text") != score:
                self.lbl_score.configure(text=score, fg=TEXT_COLOR)
            if self.lbl_clock.cget("text") != clock_text:
                self.lbl_clock.configure(
                    text=clock_text, fg=clock_color(clock_text), width=COUNTDOWN_WIDTH, anchor="center"
                )
            league = self.match.get("league_short", "")
            if self.lbl_league.cget("text") != league:
                self.lbl_league.configure(text=league, fg=MUTED)
            if self.lbl_icon.cget("image") or self.lbl_icon.cget("text"):
                self.lbl_icon.configure(image="", text="")
                self._icon_ph = None
        except tk.TclError:
            pass

    def _current_slide(self):
        if not self._slides or self._slide_i < 0 or self._slide_i >= len(self._slides):
            return None
        return self._slides[self._slide_i]

    def _fill_goal_copy(self, slide):
        self._pack_goal_mid()
        head, sub = _goal_slide_copy(slide)
        kind = _tag_kind(slide.get("tag"))
        try:
            self._icon_ph = ImageTk.PhotoImage(event_icon(kind, 12))
            self.lbl_icon.configure(image=self._icon_ph, text="")
        except Exception:
            self.lbl_icon.configure(image="", text="")
            self._icon_ph = None
        self.lbl_clock.configure(text=head, fg=PL_GREEN)
        self.lbl_league.configure(text=sub, fg=MUTED)

    def _fill_sub_copy(self, slide):
        on = (slide.get("player") or "?").strip()
        off = (slide.get("extra") or "—").strip()
        self.lbl_sub_on.configure(text=on, fg=PL_GREEN)
        self.lbl_sub_off.configure(text=off, fg=DANGER)

    def _hold_ms_for(self, slide) -> int:
        tag = ((slide or {}).get("tag") or "GOAL").upper()
        return _SUB_HOLD_MS if tag == "SUB" else _GOAL_HOLD_MS

    def _start_slide(self):
        slide = self._current_slide()
        if not slide:
            self._show_idle()
            return
        self._phase_t0 = time.time()
        tag = (slide.get("tag") or "GOAL").upper()
        side = slide.get("side")
        self._set_alert_chrome(tag)
        if tag == "SUB":
            self._layout = "sub"
            self._apply_event_slots(side, "sub")
            self._fill_sub_copy(slide)
            self._begin_width_then_scale(
                self._measure_sub_width(slide.get("player"), slide.get("extra"))
            )
        else:
            self._layout = "goal"
            self._apply_event_slots(side, "goal")
            self._fill_goal_copy(slide)
            # Same expand logic as subs — long scorers were clipping into the crest.
            self._begin_width_then_scale(self._measure_goal_width())

    def _advance_or_leave(self):
        """After hold: wipe out, then next slide or shrink/idle — no micro-loop."""
        now = time.time()
        self._slides = [s for s in _expand_slides(self._alerts) if now < s.get("expires", 0)]
        self._phase = "out"
        self._phase_t0 = now
        if self._slide_i + 1 < len(self._slides):
            self._after_out = "next"
        elif self._pill_w > PILL_W + 2:
            self._after_out = "shrink"
        else:
            self._after_out = "idle"

    def _next_slide_enter(self):
        self._slide_i += 1
        if self._slide_i >= len(self._slides):
            if self._pill_w > PILL_W + 2:
                self._begin_shrink()
            else:
                self._show_idle()
            return
        self._start_slide()

    def _begin_shrink(self):
        self._pick_grow_dir()
        self._width_from = self._pill_w
        self._width_to = PILL_W
        self._phase = "shrink"
        self._phase_t0 = time.time()
        self._ensure_loop()

    def _ensure_loop(self):
        if self._job is not None:
            return
        self._job = self.after(_TICK_MS, self._tick)

    def _stop_loop(self):
        if self._job is not None:
            try:
                self.after_cancel(self._job)
            except Exception:
                pass
            self._job = None

    def _tick(self):
        self._job = None
        now = time.time()
        self._alerts = [a for a in self._alerts if now < a.get("expires", 0)]
        live_slides = [s for s in _expand_slides(self._alerts) if now < s.get("expires", 0)]
        # Keep index stable while animating; drop only when leaving a slide.
        if self._phase in ("idle",):
            self._slides = live_slides
        elif not live_slides and self._phase not in ("out", "shrink"):
            self._slides = []
            self._phase = "out"
            self._after_out = "shrink" if self._pill_w > PILL_W + 2 else "idle"
            self._phase_t0 = now

        elapsed = (now - self._phase_t0) * 1000.0
        slide = self._current_slide() if self._slides else None

        if self._phase == "expand":
            t = _ease_out_cubic(elapsed / _EXPAND_MS)
            w = self._width_from + (self._width_to - self._width_from) * t
            remake = int(elapsed / _TICK_MS) % 2 == 0
            if remake:
                self._blink_rim_drawn = None  # width remake — let blink re-apply rim
            self._set_pill_width(w, remake=remake)
            self._place_alert_scaled(scale=0.82)
            self._tick_goal_blink()
            if elapsed >= _EXPAND_MS:
                self._blink_rim_drawn = None
                self._set_pill_width(self._width_to, remake=True)
                self._phase = "scale_in"
                self._phase_t0 = now
                self._place_alert_scaled(x_off=_WIPE_PX, scale=0.82)
                self._tick_goal_blink()
        elif self._phase == "scale_in":
            t = _ease_out_cubic(elapsed / _SCALE_IN_MS)
            scale = 0.82 + 0.18 * t
            x_off = _WIPE_PX * (1 - t)
            self._place_alert_scaled(x_off=x_off, scale=scale)
            self._tick_goal_blink()
            if elapsed >= _SCALE_IN_MS:
                self._place_alert_scaled(scale=1.0)
                self._phase = "hold"
                self._hold_until = now + self._hold_ms_for(slide) / 1000.0
                self._phase_t0 = now
        elif self._phase == "hold":
            self._place_alert_scaled(scale=1.0)
            self._tick_goal_blink()
            if now >= self._hold_until:
                self._advance_or_leave()
        elif self._phase == "out":
            t = _ease_in_cubic(elapsed / _WIPE_OUT_MS)
            scale = 1.0 - 0.12 * t
            x_off = -_WIPE_PX * t
            self._place_alert_scaled(x_off=x_off, scale=scale)
            if elapsed >= _WIPE_OUT_MS:
                self._slides = live_slides
                if self._after_out == "next":
                    self._next_slide_enter()
                elif self._after_out == "shrink" or self._pill_w > PILL_W + 2:
                    self._begin_shrink()
                else:
                    self._show_idle()
                    return
        elif self._phase == "shrink":
            t = _ease_in_cubic(elapsed / _SHRINK_MS)
            w = self._width_from + (self._width_to - self._width_from) * t
            self._set_pill_width(w, remake=(int(elapsed / _TICK_MS) % 2 == 0))
            if elapsed >= _SHRINK_MS:
                self._set_pill_width(PILL_W, remake=False)
                self._show_idle()
                return
        elif self._phase == "idle":
            return

        self._ensure_loop()

    def _on_press(self, event):
        self._press = (event.x_root, event.y_root, self.winfo_x(), self.winfo_y())
        self._dragging = False

    def _on_motion(self, event):
        if not self._press:
            return
        px, py, ox, oy = self._press
        dx, dy = event.x_root - px, event.y_root - py
        if not self._dragging and abs(dx) + abs(dy) < DRAG_THRESHOLD:
            return
        self._dragging = True
        self.move_to(ox + dx, oy + dy)
        self.app.timeline.sync_follow()

    def _on_release(self, event):
        if self._dragging:
            self._pos = (self.winfo_x(), self.winfo_y())
            self.app.pill_positions[self.match_id] = self._pos
            self.app.save_pill_state()
        else:
            self.app.timeline.toggle(self.match, self, prefer_above_ticker=False)
        self._press = None
        self._dragging = False

    def _on_menu(self, event):
        menu = tk.Menu(self, tearoff=0, bg=PANEL_BG, fg=TEXT_COLOR, activebackground=PL_PURPLE)
        mid = self.match_id
        match = self.match
        menu.add_command(
            label="Show timeline",
            command=lambda: self.app.run_context_menu_action(
                lambda: self.app.timeline.open(match, self)
            ),
        )
        menu.add_command(
            label="Hide this match",
            command=lambda: self.app.run_context_menu_action(lambda: self.app.hide_match_pill(mid)),
        )
        self.app.popup_context_menu(menu, event.x_root, event.y_root)

    def destroy(self):
        self._stop_loop()
        super().destroy()
