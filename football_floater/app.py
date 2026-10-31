"""Core app: ticker, data loop, free-float sync."""
import json
import threading
import time
import traceback
import tkinter as tk
from datetime import datetime
from io import BytesIO
from zoneinfo import ZoneInfo

import requests
from PIL import Image, ImageTk

from .config import (
    ALERT_DURATION,
    ANIMATION_SPEED,
    DRAG_THRESHOLD,
    FLOAT_ALERT_DURATION,
    FONT_SCORE,
    FONT_SMALL,
    FONT_TINY,
    FONT_UI,
    FONT_UI_BOLD,
    ICON_SIZE,
    LEAGUES,
    PILL_GAP,
    PILL_H,
    PILL_MARGIN,
    PILL_W,
    POSITIONS_FILE,
    REFRESH_RATE,
    ROW_GAP,
    SCROLL_STEP,
    SETTINGS_FILE,
    TICKER_H,
    TICKER_W,
    TOAST_BAND,
)
from .espn import scoreboard_url, summary_url
from .matchday import countdown_text, espn_dates, in_matchday, matchday_window, parse_espn_dt
from .monitors import get_monitor, list_monitors
from .overlay import clock_color, setup_overlay
from .theme import (
    CHROMA,
    DIVIDER,
    MUTED,
    PANEL_BG,
    PL_GREEN,
    PL_PINK,
    PL_PURPLE,
    TEXT_COLOR,
    THEMES,
    apply_theme,
    make_circle_icon,
    make_glass,
)
from .widgets.control_dock import ControlDock
from .widgets.goal_bubble import GoalBubble, TickerToast
from .widgets.match_pill import MatchPill
from .widgets.settings_dialog import StartupSettingsDialog
from .widgets.timeline import TimelinePanel


class SmartTicker:
    def __init__(self, root):
        self.root = root
        self.image_cache = {}
        self.last_scores = {}
        self.sub_seen = {}
        self.sub_cache = {}
        self.match_details_cache = {}
        self.assist_cache = {}
        self.seen_live = set()
        self.current_matches = []

        self.active_alerts = {}
        self.active_bubbles = []

        self.free_float = False
        self.match_pills = {}
        self._hidden_labels = {}
        self.pill_positions, self.hidden_pills = self.load_pill_state()
        self.settings = self.load_settings()
        apply_theme(self.settings.get("theme") or "default")

        self.scroll_x = 0
        self.content_width = 0
        self.running = True
        self.hover_ticker = False
        self.scroll_locked = False
        self._clock_labels = []
        self._countdown_ms = 0
        self._move_off = (0, 0)

        self.setup_ticker_window()
        self.timeline = TimelinePanel(self)
        self.dock = ControlDock(self)
        self.apply_display_layout(force=False)

        # Every launch: ask leagues/filters/display unless user opted out
        if self.settings.get("skip_startup_dialog") and self.settings.get("filters_set"):
            threading.Thread(target=self.update_data_loop, daemon=True).start()
        else:
            StartupSettingsDialog(self, startup=True)
            self.root.after(500, self._ensure_data_loop)

        self.animate_ticker()

    def _ensure_data_loop(self):
        if getattr(self, "_loop_started", False):
            return
        if self.settings.get("filters_set"):
            self._loop_started = True
            threading.Thread(target=self.update_data_loop, daemon=True).start()
        else:
            self.root.after(500, self._ensure_data_loop)

    # ---------- persistence ----------
    def load_settings(self):
        defaults = {
            "filters_set": False,
            "skip_startup_dialog": False,
            "leagues": ["eng.1"],
            "show_past": True,
            "show_live": True,
            "show_future": True,
            "ctrl_minimized": False,
            "ctrl_pos": None,
            "ticker_pos": None,
            "monitor_index": None,  # None → OS primary at runtime
            "theme": "default",
        }
        try:
            if SETTINGS_FILE.exists():
                raw = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
                defaults.update(raw)
        except Exception:
            pass
        # migrate / sanitize
        leagues = [lid for lid in defaults.get("leagues") or [] if lid in LEAGUES]
        defaults["leagues"] = leagues or ["eng.1"]
        raw_mon = defaults.get("monitor_index", None)
        if raw_mon is None or raw_mon == "":
            defaults["monitor_index"] = None
        else:
            try:
                defaults["monitor_index"] = int(raw_mon)
            except (TypeError, ValueError):
                defaults["monitor_index"] = None
        if defaults.get("theme") not in THEMES:
            defaults["theme"] = "default"
        return defaults

    def save_settings(self):
        try:
            SETTINGS_FILE.write_text(json.dumps(self.settings, indent=2), encoding="utf-8")
        except Exception:
            pass

    def load_pill_state(self):
        positions, hidden = {}, set()
        try:
            if not POSITIONS_FILE.exists():
                return positions, hidden
            raw = json.loads(POSITIONS_FILE.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and raw.get("layout") == "vertical-stack":
                positions = {str(k): tuple(v) for k, v in raw.get("positions", {}).items()}
                hidden = {str(x) for x in raw.get("hidden", [])}
                self._hidden_labels = {str(k): v for k, v in raw.get("hidden_labels", {}).items()}
        except Exception:
            pass
        return positions, hidden

    def save_pill_state(self):
        try:
            payload = {
                "layout": "vertical-stack",
                "positions": {str(k): [int(v[0]), int(v[1])] for k, v in self.pill_positions.items()},
                "hidden": sorted(self.hidden_pills),
                "hidden_labels": {k: v for k, v in self._hidden_labels.items() if k in self.hidden_pills},
            }
            POSITIONS_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception:
            pass

    # ---------- ticker window ----------
    def _ticker_root_h(self):
        return TICKER_H + TOAST_BAND

    def setup_ticker_window(self):
        setup_overlay(self.root)
        self.ticker_bg = tk.Label(self.root, bg=CHROMA, bd=0)
        self._ticker_ph = ImageTk.PhotoImage(make_glass(TICKER_W, TICKER_H))
        self.ticker_bg.configure(image=self._ticker_ph)
        # Glass sits under a chroma toast band so in-window toasts can place() above it.
        self.ticker_bg.place(x=0, y=TOAST_BAND, width=TICKER_W, height=TICKER_H)

        self.ticker_body = tk.Frame(self.root, bg=PANEL_BG)
        self.ticker_body.place(x=24, y=TOAST_BAND + 6, width=TICKER_W - 48, height=TICKER_H - 12)
        self.clip_frame = tk.Frame(self.ticker_body, bg=PANEL_BG)
        self.clip_frame.pack(fill=tk.BOTH, expand=True)
        self.ticker_frame = tk.Frame(self.clip_frame, bg=PANEL_BG)
        self.ticker_frame.place(x=0, y=0, relheight=1.0)
        tk.Label(self.ticker_frame, text="Connecting…", bg=PANEL_BG, fg=MUTED, font=FONT_UI).pack(
            side=tk.LEFT, padx=8
        )

        for w in (self.ticker_bg, self.clip_frame):
            w.bind("<ButtonPress-1>", self.start_move)
            w.bind("<B1-Motion>", self.do_move)

        # Temporary place; apply_display_layout() keeps a saved spot that is still on a screen
        mon = get_monitor(self.settings.get("monitor_index"), self.root)
        root_h = self._ticker_root_h()
        pos = self.settings.get("ticker_pos")
        if pos and len(pos) >= 2 and self.spot_on_screen(pos[0], pos[1], TICKER_W, root_h):
            tx, ty = int(pos[0]), int(pos[1])
        else:
            tx = mon["x"] + (mon["w"] - TICKER_W) // 2
            ty = mon["y"] + 80
        self.root.geometry(f"{TICKER_W}x{root_h}+{tx}+{ty}")

    def selected_monitor(self):
        return get_monitor(self.settings.get("monitor_index"), self.root)

    def spot_on_screen(self, x, y, w, h):
        """True when enough of the window still sits on a connected display."""
        try:
            x, y, w, h = int(x), int(y), int(w), int(h)
        except (TypeError, ValueError):
            return False
        if w < 1 or h < 1:
            return False
        monitors = list_monitors(self.root)
        if not monitors:
            return True
        need_w, need_h = min(48, w), min(24, h)
        for mon in monitors:
            visible_w = min(x + w, mon["x"] + mon["w"]) - max(x, mon["x"])
            visible_h = min(y + h, mon["y"] + mon["h"]) - max(y, mon["y"])
            if visible_w >= need_w and visible_h >= need_h:
                return True
        return False

    def apply_display_layout(self, force=False):
        """Restore ticker and dock. A spot off every screen goes back to the default on the chosen monitor."""
        mon = self.selected_monitor()
        root_h = self._ticker_root_h()
        pos = self.settings.get("ticker_pos")
        if (
            not force
            and pos
            and len(pos) >= 2
            and self.spot_on_screen(pos[0], pos[1], TICKER_W, root_h)
        ):
            tx, ty = int(pos[0]), int(pos[1])
        else:
            tx = mon["x"] + (mon["w"] - TICKER_W) // 2
            ty = mon["y"] + 80
            self.settings["ticker_pos"] = [tx, ty]

        self.root.geometry(f"{TICKER_W}x{root_h}+{tx}+{ty}")
        self.root.update_idletasks()

        if hasattr(self, "dock"):
            self.dock.update_idletasks()
            cw = max(self.dock.winfo_width(), self.dock.winfo_reqwidth(), 200)
            ch = max(self.dock.winfo_height(), self.dock.winfo_reqheight(), 32)
            cpos = self.settings.get("ctrl_pos")
            if (
                not force
                and cpos
                and len(cpos) >= 2
                and self.spot_on_screen(cpos[0], cpos[1], cw, ch)
            ):
                dx, dy = int(cpos[0]), int(cpos[1])
            else:
                dx = mon["x"] + max(0, (mon["w"] - cw) // 2)
                dy = ty + root_h + ROW_GAP
                dx = min(max(dx, mon["x"]), mon["x"] + mon["w"] - min(cw, mon["w"]))
                dy = min(max(dy, mon["y"]), mon["y"] + mon["h"] - min(ch, mon["h"]))
                self.settings["ctrl_pos"] = [int(dx), int(dy)]
            self.dock.geometry(f"+{int(dx)}+{int(dy)}")
        self.save_settings()

    def restyle(self):
        """Repaint ticker, dock, and pills after a theme change."""
        apply_theme(self.settings.get("theme") or "default")
        self.image_cache.clear()
        self._ticker_ph = ImageTk.PhotoImage(make_glass(TICKER_W, TICKER_H))
        self.ticker_bg.configure(image=self._ticker_ph)
        try:
            self.ticker_bg.place(x=0, y=TOAST_BAND, width=TICKER_W, height=TICKER_H)
            self.ticker_body.place(x=24, y=TOAST_BAND + 6, width=TICKER_W - 48, height=TICKER_H - 12)
        except tk.TclError:
            pass
        for w in (self.ticker_body, self.clip_frame, self.ticker_frame):
            try:
                w.configure(bg=PANEL_BG)
            except tk.TclError:
                pass
        if self.free_float:
            self.destroy_all_pills()
            self.sync_free_pills(self.current_matches)
        elif self.current_matches:
            self.render_matches(self.current_matches)
        if getattr(self, "timeline", None) and self.timeline.is_open:
            self.timeline.close()
        if getattr(self, "dock", None):
            self.dock._build()

    def start_move(self, event):
        self._move_off = (event.x_root - self.root.winfo_x(), event.y_root - self.root.winfo_y())

    def do_move(self, event):
        ox, oy = self._move_off
        self.root.geometry(f"+{event.x_root - ox}+{event.y_root - oy}")
        self.settings["ticker_pos"] = [self.root.winfo_x(), self.root.winfo_y()]
        self.save_settings()

    def set_ticker_visible(self, visible):
        if visible:
            self.root.deiconify()
        else:
            self.root.withdraw()

    # ---------- animation ----------
    def animate_ticker(self):
        if not self.running:
            return
        paused = self.free_float or self.hover_ticker or self.scroll_locked or self.timeline.is_open
        if not paused:
            self.scroll_x -= SCROLL_STEP
            if self.scroll_x < -self.content_width:
                self.scroll_x = self.clip_frame.winfo_width()
            self.ticker_frame.place(x=self.scroll_x, y=0, relheight=1.0)
        self.check_expired_alerts()
        self.sync_bubbles()
        self.tick_countdowns()
        self.timeline.sync_follow()
        self.root.after(ANIMATION_SPEED, self.animate_ticker)

    def _alert_ttl(self):
        """Ticker toasts stay longer; float toasts clear faster so they do not cover the pitch."""
        return FLOAT_ALERT_DURATION if self.free_float else ALERT_DURATION

    def _refresh_alert_ttls_for_mode(self):
        """
        Open alerts keep living across Float ↔ running-text, but TTL matches the new surface.
        Float → ticker: give the full ticker window so the toast can ride the chip.
        Ticker → float: cap so a 60s ticker toast does not sit on the pitch.
        """
        if not self.active_alerts:
            return
        now = time.time()
        ttl = self._alert_ttl()
        for alert in self.active_alerts.values():
            if now >= alert["expires"]:
                continue
            if self.free_float:
                alert["expires"] = min(alert["expires"], now + ttl)
            else:
                alert["expires"] = now + ttl

    def check_expired_alerts(self):
        now = time.time()
        for mid in [m for m, d in self.active_alerts.items() if now > d["expires"]]:
            del self.active_alerts[mid]
        kept = []
        for key, anchor, bubble, _slot in self.active_bubbles:
            if key in self.active_alerts:
                kept.append([key, anchor, bubble, _slot])
            else:
                try:
                    bubble.destroy()
                except tk.TclError:
                    pass
        self.active_bubbles = kept

    def tick_countdowns(self):
        self._countdown_ms += ANIMATION_SPEED
        if self._countdown_ms < 1000:
            return
        self._countdown_ms = 0
        for label, match in self._clock_labels:
            if match.get("state") != "pre":
                continue
            text = countdown_text(match.get("kickoff"))
            if not text:
                continue
            try:
                if label.cget("text") != text:
                    label.configure(text=text, fg=clock_color(text))
            except tk.TclError:
                pass
        for pill in self.match_pills.values():
            pill.refresh_countdown()
        if self.timeline.is_open:
            self.timeline.refresh_countdown()

    def _avoid_rects(self):
        rects = []
        for pill in self.match_pills.values():
            try:
                if not pill.winfo_exists():
                    continue
                rects.append(
                    (
                        pill.winfo_rootx(),
                        pill.winfo_rooty(),
                        max(pill.winfo_width(), PILL_W),
                        max(pill.winfo_height(), PILL_H),
                    )
                )
            except tk.TclError:
                pass
        return rects

    def sync_bubbles(self):
        if self.free_float:
            avoid = self._avoid_rects()
            placed = []
            for _key, anchor, bubble, slot in self.active_bubbles:
                try:
                    if not anchor.winfo_exists():
                        bubble.hide()
                        continue
                    ax, ay = anchor.winfo_rootx(), anchor.winfo_rooty()
                    aw = max(anchor.winfo_width(), PILL_W)
                    ah = max(anchor.winfo_height(), PILL_H)
                    bx, by = bubble.place_near(
                        (ax, ay, aw, ah),
                        lift=slot * (bubble.h + 4),
                        bounds=self._bubble_bounds(ax, ay),
                        avoid=avoid + placed,
                        stick_above=False,
                    )
                    placed.append((bx, by, bubble.w, bubble.h))
                except tk.TclError:
                    pass
            try:
                self.dock.lift()
            except tk.TclError:
                pass
            return

        # Running-text: toast is a Frame inside root (TickerToast). Same scroll math as
        # old main.py, but place() in-window — Toplevel geometry freezes on this WM.
        try:
            clip_left = self.ticker_body.winfo_x() + self.clip_frame.winfo_x()
            clip_w = max(1, self.clip_frame.winfo_width())
        except tk.TclError:
            return
        for _key, anchor, bubble, slot in self.active_bubbles:
            try:
                if not anchor.winfo_exists():
                    bubble.hide()
                    continue
                aw = max(1, anchor.winfo_width())
                local_x = clip_left + self.scroll_x + anchor.winfo_x()
                if local_x + aw < clip_left or local_x > clip_left + clip_w:
                    bubble.hide()
                    continue
                # Center toast on the match chip (old +40 offset sat over the away crest).
                bx = local_x + (aw - bubble.w) // 2
                bx = max(4, min(bx, TICKER_W - bubble.w - 4))
                bubble.update_position(bx, TOAST_BAND, lift=slot * (bubble.h + 4))
            except tk.TclError:
                pass
        try:
            self.dock.lift()
        except tk.TclError:
            pass

    def _clear_bubbles(self):
        for entry in self.active_bubbles:
            try:
                entry[2].destroy()
            except tk.TclError:
                pass
        self.active_bubbles = []

    def _bubble_bounds(self, x, y):
        for mon in list_monitors(self.root):
            if mon["x"] <= x < mon["x"] + mon["w"] and mon["y"] <= y < mon["y"] + mon["h"]:
                return mon["x"], mon["y"], mon["w"], mon["h"]
        mon = self.selected_monitor()
        return mon["x"], mon["y"], mon["w"], mon["h"]

    def _alert_keys_for(self, mid):
        now = time.time()
        keys = []
        if mid in self.active_alerts and now < self.active_alerts[mid]["expires"]:
            keys.append(mid)
        prefix = f"{mid}|sub|"
        for key, alert in self.active_alerts.items():
            if str(key).startswith(prefix) and now < alert["expires"]:
                keys.append(key)
        return keys

    def _add_bubble(self, mid, anchor):
        for slot, key in enumerate(self._alert_keys_for(mid)):
            alert = self.active_alerts[key]
            kwargs = dict(
                text=alert["text"],
                tag=alert.get("tag", "GOAL"),
                detail=alert.get("detail") or "",
                lines=alert.get("lines") or None,
            )
            # Float → separate overlay window. Running-text → in-root Frame (tracks scroll).
            bubble = GoalBubble(self.root, **kwargs) if self.free_float else TickerToast(self.root, **kwargs)
            self.active_bubbles.append([key, anchor, bubble, slot])

    # ---------- free-float ----------
    def _rects_overlap(self, x1, y1, w1, h1, x2, y2, w2, h2, pad=PILL_GAP):
        return not (x1 + w1 + pad <= x2 or x2 + w2 + pad <= x1 or y1 + h1 + pad <= y2 or y2 + h2 + pad <= y1)

    def _occupied_rects(self, skip_mid=None):
        rects = []
        for mid, (x, y) in self.pill_positions.items():
            if str(mid) != str(skip_mid) and mid not in self.hidden_pills:
                rects.append((x, y, PILL_W, PILL_H))
        for mid, pill in self.match_pills.items():
            if str(mid) == str(skip_mid):
                continue
            try:
                rects.append((pill.winfo_x(), pill.winfo_y(), PILL_W, PILL_H))
            except tk.TclError:
                pass
        return rects

    def allocate_pill_pos(self, mid):
        mid = str(mid)
        mon = self.selected_monitor()
        left, top = mon["x"] + PILL_MARGIN, mon["y"] + PILL_MARGIN
        right = mon["x"] + mon["w"] - PILL_MARGIN
        bottom = mon["y"] + mon["h"] - PILL_MARGIN - 40

        if mid in self.pill_positions:
            x, y = self.pill_positions[mid]
            on_mon = left <= x <= right - PILL_W and top <= y <= bottom - PILL_H
            if on_mon and not any(
                self._rects_overlap(x, y, PILL_W, PILL_H, *r) for r in self._occupied_rects(mid)
            ):
                return (x, y)

        x_right = right - PILL_W
        y_bottom = bottom - PILL_H
        occupied = self._occupied_rects(mid)
        x = x_right
        while x >= left:
            y = y_bottom
            while y >= top:
                if not any(self._rects_overlap(x, y, PILL_W, PILL_H, *r) for r in occupied):
                    self.pill_positions[mid] = (x, y)
                    self.save_pill_state()
                    return (x, y)
                y -= PILL_H + PILL_GAP
            x -= PILL_W + PILL_GAP
        pos = (x_right, y_bottom)
        self.pill_positions[mid] = pos
        self.save_pill_state()
        return pos

    def _match_label(self, mid):
        mid = str(mid)
        for m in self.current_matches:
            if str(m["id"]) == mid:
                return f"{m['home']['tla']} vs {m['away']['tla']}"
        return self._hidden_labels.get(mid, mid)

    def hide_match_pill(self, mid):
        mid = str(mid)
        pill = self.match_pills.pop(mid, None)
        if pill:
            try:
                self.pill_positions[mid] = (pill.winfo_x(), pill.winfo_y())
                pill.destroy()
            except tk.TclError:
                pass
        if self.timeline.is_open and str(self.timeline.match_id) == mid:
            self.timeline.close()
        self.hidden_pills.add(mid)
        self._hidden_labels[mid] = self._match_label(mid)
        self.save_pill_state()
        self._update_hidden_chip()
        kept = []
        for b in self.active_bubbles:
            if str(b[0]) == mid or str(b[0]).startswith(f"{mid}|"):
                b[2].destroy()
            else:
                kept.append(b)
        self.active_bubbles = kept

    def unhide_match_pill(self, mid):
        self.hidden_pills.discard(str(mid))
        self.save_pill_state()
        self._update_hidden_chip()
        self.sync_free_pills(self.current_matches)

    def unhide_all_pills(self):
        self.hidden_pills.clear()
        self.save_pill_state()
        self._update_hidden_chip()
        self.sync_free_pills(self.current_matches)

    def _update_hidden_chip(self):
        if hasattr(self, "dock"):
            self.dock.set_hidden(len(self.hidden_pills))

    def show_hidden_menu(self):
        menu = tk.Menu(self.root, tearoff=0, bg=PANEL_BG, fg=TEXT_COLOR, activebackground=PL_PURPLE)
        if not self.hidden_pills:
            menu.add_command(label="No hidden matches", state="disabled")
        else:
            menu.add_command(label="Show all", command=self.unhide_all_pills)
            menu.add_separator()
            for mid in sorted(self.hidden_pills, key=self._match_label):
                menu.add_command(
                    label=f"Show {self._match_label(mid)}", command=lambda m=mid: self.unhide_match_pill(m)
                )
        btn = self.dock.btn_hidden
        try:
            menu.tk_popup(btn.winfo_rootx(), btn.winfo_rooty() + 32)
        finally:
            menu.grab_release()

    def show_settings_dialog(self):
        existing = getattr(self, "_settings_dialog", None)
        try:
            if existing is not None and existing.winfo_exists():
                existing.deiconify()
                existing.lift()
                existing.focus_force()
                return
        except tk.TclError:
            pass
        self._settings_dialog = StartupSettingsDialog(self, startup=False)

    def toggle_free_float(self):
        self.timeline.close()
        self._clear_bubbles()
        self.free_float = not self.free_float
        self._refresh_alert_ttls_for_mode()
        self.dock.set_free_button()
        if self.free_float:
            self.set_ticker_visible(False)
            # Recreate toasts on pills for any alert still open from running-text.
            self.sync_free_pills(self.current_matches)
        else:
            self._capture_live_pill_positions()
            self.destroy_all_pills()
            self.set_ticker_visible(True)
            # Recreate toasts on ticker chips for any alert still open from float.
            self.render_matches(self.current_matches)

    def rearrange_float_pills(self):
        """Restack visible float pills from the bottom-right of the chosen display."""
        if not self.free_float:
            return
        self.timeline.close()
        self._clear_bubbles()
        visible = [str(m["id"]) for m in self.current_matches if str(m["id"]) not in self.hidden_pills]
        for mid in visible:
            self.pill_positions.pop(mid, None)
            pill = self.match_pills.pop(mid, None)
            if pill:
                try:
                    pill.destroy()
                except tk.TclError:
                    pass
        self.sync_free_pills(self.current_matches)
        self.save_pill_state()

    def _capture_live_pill_positions(self):
        for mid, pill in self.match_pills.items():
            try:
                self.pill_positions[str(mid)] = (pill.winfo_x(), pill.winfo_y())
            except tk.TclError:
                pass
        self.save_pill_state()

    def destroy_all_pills(self):
        for pill in self.match_pills.values():
            try:
                pill.destroy()
            except tk.TclError:
                pass
        self.match_pills.clear()

    def sync_free_pills(self, matches):
        if not self.free_float:
            return
        live_ids = {str(m["id"]) for m in matches}
        for mid in [m for m in self.match_pills if m not in live_ids]:
            try:
                self.match_pills.pop(mid).destroy()
            except tk.TclError:
                pass
        for m in matches:
            mid = str(m["id"])
            if mid in self.hidden_pills:
                self._hidden_labels[mid] = f"{m['home']['tla']} vs {m['away']['tla']}"
                continue
            if mid in self.match_pills:
                self.match_pills[mid].update_match(m)
            else:
                x, y = self.allocate_pill_pos(mid)
                self.match_pills[mid] = MatchPill(self, m, x, y)
        self._update_hidden_chip()
        self._clear_bubbles()
        for mid, pill in self.match_pills.items():
            self._add_bubble(mid, pill)

    # ---------- parsing / fetch ----------
    def get_player_name_from_detail(self, detail):
        if detail.get("athletesInvolved"):
            a = detail["athletesInvolved"][0]
            return a.get("shortName", a.get("displayName", "Unknown"))
        if detail.get("participants"):
            return detail["participants"][0]["athlete"].get("shortName", "Unknown")
        if detail.get("text"):
            return (
                detail["text"]
                .replace("Goal - ", "")
                .replace("Yellow Card - ", "")
                .replace("Red Card - ", "")
                .replace("Penalty - Scored - ", "")
                .split(" ")[-1]
            )
        return "Unknown"

    @staticmethod
    def is_scoring_detail(detail, type_txt):
        if detail.get("scoringPlay"):
            return True
        if detail.get("penaltyKick") and "Miss" not in type_txt:
            return True
        if detail.get("ownGoal"):
            return True
        if "Goal" in type_txt:
            return True
        return type_txt.startswith("Penalty") and "Scored" in type_txt

    def parse_espn_match(self, event, league_id):
        try:
            espn_id = event["id"]
            mid = f"{league_id}:{espn_id}"
            status = event["status"]
            state = status["type"]["state"]
            kickoff = parse_espn_dt(event["date"])
            if state == "in":
                time_str = status["type"]["shortDetail"]
            elif state == "post":
                time_str = "FT"
            else:
                time_str = kickoff.strftime("%H:%M")
            competitors = event["competitions"][0]["competitors"]
            home = next(c for c in competitors if c["homeAway"] == "home")
            away = next(c for c in competitors if c["homeAway"] == "away")

            events_list = []
            for d in event["competitions"][0].get("details", []):
                clock = d.get("clock", {}).get("displayValue", "")
                type_txt = d.get("type", {}).get("text", "") or ""
                own_goal = bool(d.get("ownGoal") or "Own Goal" in type_txt)
                evt = {
                    "time": clock,
                    "player": self.get_player_name_from_detail(d),
                    "assist": None,
                    "type": "other",
                    "side": self._team_side(d.get("team"), home, away, own_goal=own_goal),
                }
                if self.is_scoring_detail(d, type_txt):
                    is_pen = bool(d.get("penaltyKick") or ("Penalty" in type_txt and "Scored" in type_txt))
                    evt["type"] = "penalty" if is_pen else "goal"
                    evt["own_goal"] = own_goal
                    if evt["own_goal"]:
                        evt["player"] += " (OG)"
                    events_list.append(evt)
                elif "Card" in type_txt:
                    evt["type"] = "red" if "Red" in type_txt else "yellow"
                    events_list.append(evt)

            meta = LEAGUES.get(league_id, {"name": league_id, "short": "?"})
            return {
                "id": mid,
                "espn_id": espn_id,
                "league_id": league_id,
                "league_short": meta["short"],
                "league_name": meta["name"],
                "time": time_str,
                "state": state,
                "kickoff": kickoff,
                "home": {
                    "id": str(home["team"].get("id") or ""),
                    "tla": home["team"]["abbreviation"],
                    "logo": home["team"]["logo"],
                    "score": int(home.get("score", 0)),
                },
                "away": {
                    "id": str(away["team"].get("id") or ""),
                    "tla": away["team"]["abbreviation"],
                    "logo": away["team"]["logo"],
                    "score": int(away.get("score", 0)),
                },
                "history_list": events_list,
                "last_event": "",
            }
        except Exception:
            return None

    def fetch_assists(self, m):
        r = requests.get(summary_url(m["league_id"]), params={"event": m["espn_id"]}, timeout=10)
        out = []
        for k in r.json().get("keyEvents", []):
            if not k.get("scoringPlay"):
                continue
            parts = k.get("participants", [])
            assist = None
            if len(parts) > 1 and "Own" not in (k.get("type", {}).get("text") or ""):
                a = parts[1].get("athlete", {})
                assist = a.get("shortName")
                if not assist and a.get("displayName"):
                    names = a["displayName"].split()
                    assist = f"{names[0][0]}. {' '.join(names[1:])}" if len(names) > 1 else names[0]
            out.append((k.get("clock", {}).get("displayValue", ""), assist))
        return out

    def fetch_substitutions(self, m):
        r = requests.get(summary_url(m["league_id"]), params={"event": m["espn_id"]}, timeout=10)
        out = []
        for k in r.json().get("keyEvents", []):
            typ = k.get("type") or {}
            if typ.get("type") != "substitution" and typ.get("text") != "Substitution":
                continue
            clock = (k.get("clock") or {}).get("displayValue", "")
            parts = k.get("participants") or []

            def _name(p):
                a = (p or {}).get("athlete") or {}
                return a.get("shortName") or a.get("displayName") or ""

            on = _name(parts[0]) if parts else ""
            off = _name(parts[1]) if len(parts) > 1 else ""
            if not on or not off:
                text = k.get("text") or ""
                if " replaces " in text:
                    tail = text.split(". ")[-1]
                    on_txt, _, off_txt = tail.partition(" replaces ")
                    on = on or on_txt.strip(" .")
                    off = off or off_txt.strip(" .")
            if on:
                out.append({"clock": clock, "on": on, "off": off, "side": self._team_side(k.get("team"), m)})
        return out

    @staticmethod
    def _team_side(team, home, away=None, own_goal=False):
        """home or away. Own goals flip: ESPN tags the team credited with the goal, not the player."""
        team = team or {}
        if away is None and isinstance(home, dict) and "home" in home and "away" in home:
            away = home["away"]
            home = home["home"]
        tid = str(team.get("id") or "")
        abbr = (team.get("abbreviation") or "").upper()

        def is_side(info):
            if not isinstance(info, dict):
                return False
            info_id = str(info.get("id") or (info.get("team") or {}).get("id") or "")
            info_abbr = (info.get("tla") or info.get("abbreviation") or (info.get("team") or {}).get("abbreviation") or "").upper()
            return (tid and info_id and tid == info_id) or (abbr and info_abbr and abbr == info_abbr)

        if is_side(home):
            side = "home"
        elif is_side(away):
            side = "away"
        else:
            return None
        if own_goal:
            return "away" if side == "home" else "home"
        return side

    @staticmethod
    def _clock_sort(clock):
        raw = (clock or "").replace("'", "")
        extra = 0
        if "+" in raw:
            raw, plus = raw.split("+", 1)
            extra = int("".join(ch for ch in plus if ch.isdigit()) or 0)
        base = int("".join(ch for ch in raw if ch.isdigit()) or 0)
        return base + extra

    def _merge_subs(self, m, subs):
        rows = [e for e in m["history_list"] if e.get("type") != "sub"]
        for s in subs:
            rows.append(
                {
                    "time": s["clock"],
                    "type": "sub",
                    "player": s["on"],
                    "off": s.get("off") or "",
                    "assist": None,
                    "side": s.get("side"),
                }
            )
        rows.sort(key=lambda e: (self._clock_sort(e.get("time")), 0 if e.get("type") != "sub" else 1))
        m["history_list"] = rows

    def note_substitutions(self, m):
        """Put every sub on the timeline. Toast only subs that appear after the first live look."""
        if m.get("state") not in ("in", "post"):
            return
        if m.get("state") == "post" and m["id"] in self.sub_cache:
            subs = self.sub_cache[m["id"]]
        else:
            subs = self.fetch_substitutions(m)
            if m.get("state") == "post":
                self.sub_cache[m["id"]] = subs
        self._merge_subs(m, subs)
        if m.get("state") != "in":
            return
        fresh = []
        for s in subs:
            key = f"{m['id']}|sub|{s['clock']}|{s['on']}|{s['off']}"
            fresh.append((key, s))
        seen = self.sub_seen.get(m["id"])
        if seen is None:
            self.sub_seen[m["id"]] = {key for key, _s in fresh}
            return
        fresh_by_clock = {}
        clocks = []
        for key, s in fresh:
            if key in seen:
                continue
            seen.add(key)
            clock = s["clock"]
            if clock not in fresh_by_clock:
                fresh_by_clock[clock] = []
                clocks.append(clock)
            fresh_by_clock[clock].append({"on": s["on"], "off": s.get("off") or ""})
        now = time.time()
        ttl = self._alert_ttl()
        for clock in clocks:
            alert_key = f"{m['id']}|sub|{clock}"
            existing = self.active_alerts.get(alert_key)
            if existing and now < existing["expires"]:
                existing["lines"].extend(fresh_by_clock[clock])
                existing["expires"] = now + ttl
            else:
                self.active_alerts[alert_key] = {
                    "text": clock,
                    "lines": fresh_by_clock[clock],
                    "expires": now + ttl,
                    "tag": "SUB",
                }

    def enrich_assists(self, m, score):
        goals = [e for e in m["history_list"] if e["type"] in ("goal", "penalty")]
        if not goals:
            return
        cached = self.assist_cache.get(m["id"])
        if not cached or cached[0] != score:
            try:
                cached = (score, self.fetch_assists(m))
                self.assist_cache[m["id"]] = cached
            except Exception:
                cached = cached or (score, [])
        assists = cached[1]
        by_clock = {c: a for c, a in assists}
        for i, g in enumerate(goals):
            a = by_clock.get(g["time"])
            if a is None and i < len(assists):
                a = assists[i][1]
            if a and not g.get("own_goal") and g["type"] != "penalty":
                g["assist"] = a

    @staticmethod
    def goal_text(m):
        goals = [e for e in m["history_list"] if e["type"] in ("goal", "penalty")]
        if not goals:
            return "", ""
        g = goals[-1]
        return f"{g['player']} {g['time']}", (g.get("assist") or "")

    def passes_filters(self, m, window):
        if not in_matchday(m["kickoff"], window):
            return False
        state = m["state"]
        mid = str(m["id"])
        if state == "in" and self.settings.get("show_live", True):
            self.seen_live.add(mid)
        if state == "post":
            if self.settings.get("show_past", True):
                return True
            # Live-only: keep a match that finished during this run. Gone after restart.
            return bool(self.settings.get("show_live", True) and mid in self.seen_live)
        if state == "in":
            return bool(self.settings.get("show_live", True))
        if state == "pre":
            return bool(self.settings.get("show_future", True))
        return False

    def selected_leagues(self):
        leagues = [lid for lid in self.settings.get("leagues") or [] if lid in LEAGUES]
        return leagues or ["eng.1"]

    def fetch_matchday_events(self):
        """Pull scoreboards for each selected league across the matchday window dates."""
        start, end = matchday_window()
        dates = espn_dates(start, end)
        # (league_id, event) pairs; key by league:espn_id
        by_key = {}
        for league_id in self.selected_leagues():
            url = scoreboard_url(league_id)
            boards = [requests.get(url, timeout=15).json()]
            for d in sorted(dates):
                boards.append(requests.get(url, params={"dates": d}, timeout=15).json())
            for board in boards:
                for e in board.get("events", []):
                    by_key[f"{league_id}:{e['id']}"] = (league_id, e)
        return list(by_key.values()), (start, end)

    def run_once(self):
        try:
            raw_events, window = self.fetch_matchday_events()
            parsed = []
            for league_id, e in raw_events:
                m = self.parse_espn_match(e, league_id)
                if not m or not self.passes_filters(m, window):
                    continue
                parsed.append(m)
                mid = m["id"]
                score = f"{m['home']['score']}-{m['away']['score']}"
                self.enrich_assists(m, score)
                headline, assist = self.goal_text(m)
                m["last_event"] = headline
                if mid in self.last_scores and score != self.last_scores[mid]:
                    self.active_alerts[mid] = {
                        "text": headline or "GOAL!",
                        "detail": assist,
                        "expires": time.time() + self._alert_ttl(),
                        "tag": "GOAL",
                    }
                self.last_scores[mid] = score
                try:
                    self.note_substitutions(m)
                except Exception:
                    pass
                self.match_details_cache[mid] = m["history_list"]

            # stable order: kickoff, then league, then id
            parsed.sort(key=lambda m: (m["kickoff"], m["league_id"], m["id"]))
            self.current_matches = parsed
            self.root.after(0, lambda: self.render_matches(parsed))
        except Exception:
            traceback.print_exc()
        finally:
            try:
                self.root.after(0, lambda: self.dock.set_refresh("Refresh"))
            except RuntimeError:
                pass

    # ---------- ticker rendering ----------
    def render_matches(self, matches):
        if self.free_float:
            self.sync_free_pills(matches)
            if self.timeline.is_open:
                self.timeline.refresh_open()
            return

        # keep timeline if its match still exists; else close
        if self.timeline.is_open:
            if str(self.timeline.match_id) not in {str(m["id"]) for m in matches}:
                self.timeline.close()

        for w in self.ticker_frame.winfo_children():
            w.destroy()
        self._clear_bubbles()

        if not matches:
            tk.Label(self.ticker_frame, text="No matches for current filters", bg=PANEL_BG, fg=MUTED, font=FONT_UI_BOLD).pack(
                side=tk.LEFT, padx=12
            )
            self.update_ticker_width()
            return

        id_to_item = {}
        self._clock_labels = []
        for i, m in enumerate(matches):
            item = tk.Frame(self.ticker_frame, bg=PANEL_BG, cursor="hand2")
            item.pack(side=tk.LEFT, padx=12, fill=tk.Y)
            parts = [item]
            id_to_item[str(m["id"])] = item

            for side in ("home", None, "away"):
                if side is None:
                    mid_box = tk.Frame(item, bg=PANEL_BG)
                    mid_box.pack(side=tk.LEFT, padx=8)
                    score = tk.Label(
                        mid_box,
                        text=f"{m['home']['score']} - {m['away']['score']}",
                        bg=PANEL_BG,
                        fg=TEXT_COLOR,
                        font=FONT_SCORE,
                    )
                    score.pack()
                    clock_text = m["time"]
                    if m.get("state") == "pre":
                        clock_text = countdown_text(m.get("kickoff")) or m["time"]
                    clock = tk.Label(
                        mid_box, text=clock_text, bg=PANEL_BG, fg=clock_color(clock_text), font=FONT_SMALL
                    )
                    clock.pack()
                    league = tk.Label(
                        mid_box, text=m.get("league_short", ""), bg=PANEL_BG, fg=MUTED, font=FONT_TINY
                    )
                    league.pack()
                    parts += [mid_box, score, clock, league]
                    self._clock_labels.append((clock, m))
                    continue
                img = self.get_team_icon(m[side]["tla"], m[side]["logo"])
                lbl = tk.Label(item, bg=PANEL_BG, fg=TEXT_COLOR, font=FONT_TINY, bd=0)
                if img:
                    lbl.configure(image=img)
                else:
                    lbl.configure(text=m[side]["tla"])
                lbl.pack(side=tk.LEFT)
                parts.append(lbl)

            def _open_timeline(_e=None, mm=m, a=item):
                # lock before toggle — chip may sit under cursor without <Enter>
                self.scroll_locked = True
                self.timeline.toggle(mm, a, prefer_above_ticker=True)

            for w in parts:
                w.bind("<Button-1>", _open_timeline)
                w.bind("<Enter>", lambda e: setattr(self, "hover_ticker", True))
                w.bind("<Leave>", lambda e: setattr(self, "hover_ticker", False))

            if i < len(matches) - 1:
                tk.Frame(self.ticker_frame, bg=DIVIDER, width=1).pack(side=tk.LEFT, fill=tk.Y, pady=8)

            self._add_bubble(m["id"], item)

        self.update_ticker_width()
        if self.timeline.is_open:
            self.timeline.reattach_ticker_anchor(id_to_item.get(str(self.timeline.match_id)))
            self.timeline.refresh_open()

    def update_ticker_width(self):
        self.ticker_frame.update_idletasks()
        self.content_width = max(300, self.ticker_frame.winfo_reqwidth())

    def get_team_icon(self, tla, url, size=ICON_SIZE):
        if not url:
            return None
        key = f"{tla}:{size}"
        if key in self.image_cache:
            return self.image_cache[key]
        try:
            r = requests.get(url, timeout=2)
            if r.status_code == 200:
                ph = ImageTk.PhotoImage(make_circle_icon(Image.open(BytesIO(r.content)), size))
                self.image_cache[key] = ph
                return ph
        except Exception:
            pass
        return None

    # ---------- actions ----------
    def manual_refresh(self):
        self.dock.set_refresh("Refreshing…", "busy")
        threading.Thread(target=self.run_once, daemon=True).start()

    def run_test_notification(self):
        if not self.current_matches:
            now = datetime.now(ZoneInfo("UTC"))
            lid = self.selected_leagues()[0]
            self.current_matches = [
                {
                    "id": f"{lid}:999",
                    "espn_id": "999",
                    "league_id": lid,
                    "league_short": LEAGUES[lid]["short"],
                    "league_name": LEAGUES[lid]["name"],
                    "time": "88'",
                    "state": "in",
                    "kickoff": now,
                    "home": {"tla": "TES", "logo": "", "score": 2},
                    "away": {"tla": "DSG", "logo": "", "score": 1},
                    "history_list": [],
                    "last_event": "",
                }
            ]
        mid = self.current_matches[0]["id"]
        self.active_alerts[mid] = {
            "text": "Test Player 88'",
            "detail": "Someone",
            "expires": time.time() + self._alert_ttl(),
        }
        if self.free_float:
            self.sync_free_pills(self.current_matches)
        else:
            self.render_matches(self.current_matches)

    def update_data_loop(self):
        self._loop_started = True
        while self.running:
            self.run_once()
            time.sleep(REFRESH_RATE)

    def close_app(self):
        self.running = False
        self._capture_live_pill_positions()
        try:
            self.settings["ctrl_pos"] = [self.dock.winfo_x(), self.dock.winfo_y()]
            self.settings["ticker_pos"] = [self.root.winfo_x(), self.root.winfo_y()]
            self.save_settings()
        except tk.TclError:
            pass
        self.destroy_all_pills()
        self._clear_bubbles()
        try:
            self.timeline.destroy()
        except tk.TclError:
            pass
        try:
            self.dock.destroy()
        except tk.TclError:
            pass
        self.root.destroy()


def run():
    """Create Tk root and start the overlay."""
    root = tk.Tk()
    SmartTicker(root)
    root.mainloop()

