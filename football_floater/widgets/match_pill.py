"""Free-float per-match pill — in-pill wipe alerts; geometry stays fixed."""
import time
import tkinter as tk
from PIL import ImageTk

from ..config import DRAG_THRESHOLD, FONT_SCORE, FONT_SMALL, FONT_TINY, PILL_H, PILL_ICON, PILL_W
from ..icons import event_icon
from ..matchday import COUNTDOWN_WIDTH, countdown_text
from ..overlay import clock_color, setup_overlay, window_fill
from ..theme import DANGER, MUTED, PANEL_BG, PL_GREEN, PL_PURPLE, TEXT_COLOR, make_glass

_TICK_MS = 32
_SLIDE_HOLD_MS = 2200
_GOAL_WIPE_MS = 380
_SUB_ROW_MS = 320
_SUB_STAGGER_MS = 140
_WIPE_OUT_MS = 280
_WIPE_PX = 40
_SLOT_W = PILL_ICON + 4
_SLOT_SUB_W = PILL_ICON + 20  # crest + ↑↓ beside it


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


def _clip(s: str, n: int) -> str:
    s = (s or "").strip()
    if len(s) <= n:
        return s
    return s[: max(1, n - 1)] + "…"


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
    """Scorer + minute on top; assist name only underneath (no 'a ' prefix)."""
    tag = slide.get("tag") or "GOAL"
    player = _clip(slide.get("player") or "?", 12)
    clock = (slide.get("clock") or "").strip()
    assist = _clip(slide.get("extra") or "", 14)
    head = f"{player} {clock}".strip() if clock else player
    if assist:
        return head, assist
    label = "PEN" if tag in ("PEN", "PENALTY") else "GOAL"
    return head, label


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

        # Shared idle glass from app (one draw); alert rims still make a local copy.
        self._ph = app.pill_glass_image()
        self.bg = tk.Label(self, image=self._ph, bg=window_fill(), bd=0)
        self.bg.place(x=0, y=0, relwidth=1, relheight=1)

        self.body = tk.Frame(self, bg=PANEL_BG)
        self.body.place(x=14, y=8, width=PILL_W - 28, height=PILL_H - 16)

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

        self.geometry(f"{PILL_W}x{PILL_H}+{int(x)}+{int(y)}")
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
        GOAL: keep scoring crest, blank opposite.
        SUB: crest stays; ↑↓ sit beside it; minute on opposite side.
        """
        self._event_side = side if side in ("home", "away") else None
        self._clear_slot(self.slot_l)
        self._clear_slot(self.slot_r)
        clock = ""
        slide = self._current_slide()
        if slide:
            clock = slide.get("clock") or ""

        if kind == "sub":
            if side == "away":
                self._set_slot_width(_SLOT_W, _SLOT_SUB_W)
                self.lbl_time_l.configure(text=clock or "—")
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
                self.lbl_time_r.configure(text=clock or "—")
                self.lbl_time_r.pack(expand=True)
            return

        # goal / pen
        self._set_slot_width(_SLOT_W, _SLOT_W)
        if side == "away":
            self.lbl_away.pack(expand=True)
            self._paint_crest("away", self.lbl_away)
        elif side == "home":
            self.lbl_home.pack(expand=True)
            self._paint_crest("home", self.lbl_home)

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

    def _place_goal_host(self, x_off: float):
        w, h = self._clip_size()
        self.sub_host.place_forget()
        self.goal_host.place(x=int(x_off), y=0, width=w, height=h)
        if getattr(self, "_goal_mid_placed", False) and self._layout == "goal":
            # Vertically center the two-line goal block in the mid band.
            self.lbl_clock.place(relx=0.5, rely=0.38, anchor="center")
            self.row_alert.place(relx=0.5, rely=0.68, anchor="center")

    def _place_sub_host(self, y_off: float = 0, x_off: float = 0):
        w, h = self._clip_size()
        self.goal_host.place_forget()
        self.sub_host.place(x=int(x_off), y=0, width=w, height=h)
        # Center the two name lines in mid.
        self.lbl_sub_on.place(relx=0.5, rely=0.32, anchor="center")
        self.lbl_sub_off.place(relx=0.5, rely=0.68, anchor="center")
        # Horizontal wipe via shifting labels' x through place in tick — use x_off on host.
        if x_off:
            self.sub_host.place(x=int(x_off), y=0, width=w, height=h)

    def _show_idle(self):
        self._layout = "idle"
        self._phase = "idle"
        self._event_side = None
        self._goal_mid_placed = False
        self._show_slot_crests()
        self._pack_idle_mid()
        ph = self.app.pill_glass_image()
        if self._ph is not ph:
            self._ph = ph
            self.bg.configure(image=self._ph)
        self._place_goal_host(0)
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
        if not self._slides:
            return None
        self._slide_i %= len(self._slides)
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
        self.lbl_sub_on.configure(text=_clip(slide.get("player") or "?", 16), fg=PL_GREEN)
        self.lbl_sub_off.configure(text=_clip(slide.get("extra") or "—", 16), fg=DANGER)

    def _start_slide(self):
        slide = self._current_slide()
        if not slide:
            self._show_idle()
            return
        self._phase_t0 = time.time()
        tag = (slide.get("tag") or "GOAL").upper()
        side = slide.get("side")
        if tag == "SUB":
            self._layout = "sub"
            self._phase = "sub_in"
            self._apply_event_slots(side, "sub")
            self._fill_sub_copy(slide)
            self._place_sub_host(x_off=_WIPE_PX)
        else:
            self._layout = "goal"
            self._phase = "goal_wipe"
            self._apply_event_slots(side, "goal")
            self._fill_goal_copy(slide)
            self._place_goal_host(_WIPE_PX)

    def _advance_or_leave(self):
        now = time.time()
        self._slides = [s for s in _expand_slides(self._alerts) if now < s.get("expires", 0)]
        if not self._slides:
            self._phase = "out"
            self._phase_t0 = now
            return
        if len(self._slides) == 1:
            self._hold_until = now + 0.35
            return
        self._phase = "out"
        self._phase_t0 = now

    def _next_slide_enter(self):
        if not self._slides:
            self._show_idle()
            return
        self._slide_i = (self._slide_i + 1) % len(self._slides)
        self._start_slide()

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
        self._slides = [s for s in _expand_slides(self._alerts) if now < s.get("expires", 0)]
        if not self._slides and self._phase == "idle":
            self._show_idle()
            return
        if not self._slides and self._phase != "out":
            self._phase = "out"
            self._phase_t0 = now

        elapsed = (now - self._phase_t0) * 1000.0
        slide = self._current_slide()
        tag = (slide.get("tag") if slide else "") or ""
        is_sub = tag.upper() == "SUB"

        if self._phase == "goal_wipe":
            t = _ease_out_cubic(elapsed / _GOAL_WIPE_MS)
            self._place_goal_host(_WIPE_PX * (1 - t))
            if elapsed >= _GOAL_WIPE_MS:
                self._place_goal_host(0)
                self._phase = "hold"
                self._hold_until = now + _SLIDE_HOLD_MS / 1000.0
                self._phase_t0 = now
        elif self._phase == "sub_in":
            t = _ease_out_cubic(elapsed / (_SUB_ROW_MS + _SUB_STAGGER_MS))
            self._place_sub_host(x_off=_WIPE_PX * (1 - t))
            if elapsed >= _SUB_ROW_MS + _SUB_STAGGER_MS:
                self._place_sub_host(x_off=0)
                self._phase = "hold"
                self._hold_until = now + _SLIDE_HOLD_MS / 1000.0
                self._phase_t0 = now
        elif self._phase == "hold":
            if is_sub:
                self._place_sub_host(x_off=0)
            else:
                self._place_goal_host(0)
            if now >= self._hold_until:
                self._advance_or_leave()
        elif self._phase == "out":
            t = _ease_in_cubic(elapsed / _WIPE_OUT_MS)
            if is_sub or self._layout == "sub":
                self._place_sub_host(x_off=-_WIPE_PX * t)
            else:
                self._place_goal_host(-_WIPE_PX * t)
            if elapsed >= _WIPE_OUT_MS:
                if not self._slides:
                    self._show_idle()
                    return
                self._next_slide_enter()

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
        self.geometry(f"+{ox + dx}+{oy + dy}")
        self.app.timeline.sync_follow()

    def _on_release(self, event):
        if self._dragging:
            self.app.pill_positions[self.match_id] = (self.winfo_x(), self.winfo_y())
            self.app.save_pill_state()
        else:
            self.app.timeline.toggle(self.match, self, prefer_above_ticker=False)
        self._press = None
        self._dragging = False

    def _on_menu(self, event):
        menu = tk.Menu(self, tearoff=0, bg=PANEL_BG, fg=TEXT_COLOR, activebackground=PL_PURPLE)
        menu.add_command(
            label="Show timeline",
            command=lambda: (self.app.dismiss_context_menu(), self.app.timeline.open(self.match, self)),
        )
        menu.add_command(
            label="Hide this match",
            command=lambda: (self.app.dismiss_context_menu(), self.app.hide_match_pill(self.match_id)),
        )
        self.app.popup_context_menu(menu, event.x_root, event.y_root)

    def destroy(self):
        self._stop_loop()
        super().destroy()
