import json
import tkinter as tk
import requests
import threading
import time
from datetime import datetime, timedelta, time as dtime
from io import BytesIO
from pathlib import Path
from PIL import Image, ImageTk, ImageDraw, ImageFont
from zoneinfo import ZoneInfo

# --- CONFIGURATION ---
LEAGUES = {
    "eng.1": {"name": "Premier League", "short": "PL"},
    "ger.1": {"name": "Bundesliga", "short": "BL"},
}
REFRESH_RATE = 60
ANIMATION_SPEED = 40
SCROLL_STEP = 2
ALERT_DURATION = 60
TIMELINE_IDLE_MS = 4000
TIMELINE_LEAVE_MS = 1500
DRAG_THRESHOLD = 4
MATCHDAY_ROLLOVER_HOUR = 6  # local hour when football "day" rolls over
POSITIONS_FILE = Path(__file__).with_name("pill_positions.json")
SETTINGS_FILE = Path(__file__).with_name("settings.json")


def scoreboard_url(league_id):
    return f"https://site.api.espn.com/apis/site/v2/sports/soccer/{league_id}/scoreboard"


def summary_url(league_id):
    return f"https://site.api.espn.com/apis/site/v2/sports/soccer/{league_id}/summary"

# --- PALETTE ---
CHROMA = "#FF00FF"
PANEL_BG = "#201C25"
PANEL_RIM = "#8E8E93"
BTN_BG = "#2E2A33"
BTN_RIM = "#55505C"
DIVIDER = "#3A3640"
TEXT_COLOR = "#F5F5F7"
MUTED = "#AEAEB2"
PL_PURPLE = "#3D195B"
PL_GREEN = "#00FF85"
PL_PINK = "#E90052"
CARD_YELLOW = "#FFD60A"
DANGER = "#FF6B6B"

# --- SIZES ---
TICKER_W = 720
TICKER_H = 56
CTRL_H = 44
CTRL_MIN_H = 36
ROW_GAP = 8
WINDOW_ALPHA = 0.92
ICON_SIZE = 24
PILL_W = 168
PILL_H = 58
PILL_GAP = 10
PILL_MARGIN = 24
PILL_ICON = 26


def _font(size, bold=False):
    return ("Segoe UI", size, "bold") if bold else ("Segoe UI", size)


FONT_UI = _font(10)
FONT_UI_BOLD = _font(10, True)
FONT_SMALL = _font(8)
FONT_TINY = _font(8, True)
FONT_SCORE = _font(13, True)


def _hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


def _mix(a, b, t):
    return tuple(int(x * (1 - t) + y * t) for x, y in zip(_hex_rgb(a), _hex_rgb(b)))


def _load_ui_font(size=12):
    for name in ("segoeui.ttf", "Segoe UI.ttf", "SF-Pro-Text-Regular.otf", "DejaVuSans.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default()


def make_glass(width, height, radius=None, accent=None):
    if radius is None:
        radius = height // 2 if height <= 64 else 16
    size = (width, height)
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    ImageDraw.Draw(img).rounded_rectangle(
        (0, 0, width - 1, height - 1),
        radius=radius,
        fill=_hex_rgb(PANEL_BG) + (255,),
        outline=_hex_rgb(PANEL_RIM) + (255,),
        width=1,
    )
    hl = Image.new("RGBA", size, (0, 0, 0, 0))
    ImageDraw.Draw(hl).rounded_rectangle(
        (1, 1, width - 2, height - 2), radius=max(1, radius - 1), outline=(255, 255, 255, 70), width=1
    )
    top = Image.new("L", size, 0)
    ImageDraw.Draw(top).rectangle((0, 0, width, max(4, height // 3)), fill=255)
    hl.putalpha(Image.composite(hl.getchannel("A"), Image.new("L", size, 0), top))
    img = Image.alpha_composite(img, hl)
    if accent:
        ImageDraw.Draw(img).ellipse(
            (12, height // 2 - 3, 18, height // 2 + 3), fill=_hex_rgb(accent) + (255,)
        )
    result = Image.new("RGB", size, _hex_rgb(CHROMA))
    result.paste(img.convert("RGB"), mask=img.getchannel("A").point(lambda a: 255 if a > 128 else 0))
    return result


BUTTON_STYLES = {
    "default": (BTN_BG, BTN_RIM, TEXT_COLOR),
    "muted": (BTN_BG, BTN_RIM, MUTED),
    "danger": ("#3A1F24", "#7A3A40", DANGER),
    "on": ("#163326", PL_GREEN, PL_GREEN),
    "busy": (BTN_BG, CARD_YELLOW, CARD_YELLOW),
}


def make_button(label, kind="default", hover=False, min_w=0, height=28, pad_x=14):
    fill, rim, text = BUTTON_STYLES[kind]
    fill_rgb = _mix(fill, "#FFFFFF", 0.10) if hover else _hex_rgb(fill)
    font = _load_ui_font(12 if height >= 28 else 11)
    bbox = ImageDraw.Draw(Image.new("RGB", (1, 1))).textbbox((0, 0), label, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    width = max(min_w, tw + pad_x * 2)
    img = Image.new("RGB", (width, height), _hex_rgb(PANEL_BG))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle(
        (0, 0, width - 1, height - 1), radius=height // 2, fill=fill_rgb, outline=_hex_rgb(rim), width=1
    )
    d.text(
        ((width - tw) / 2 - bbox[0], (height - th) / 2 - bbox[1]),
        label,
        fill=_hex_rgb(text),
        font=font,
    )
    return img


def make_circle_icon(im, size=ICON_SIZE):
    im = im.convert("RGBA").resize((size, size), Image.Resampling.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(im, (0, 0), mask)
    bg = Image.new("RGBA", (size, size), _hex_rgb(PANEL_BG) + (255,))
    return Image.alpha_composite(bg, out).convert("RGB")


def setup_overlay(win, alpha=WINDOW_ALPHA):
    win.overrideredirect(True)
    win.wm_attributes("-topmost", True)
    try:
        win.wm_attributes("-alpha", alpha)
    except tk.TclError:
        pass
    win.configure(bg=CHROMA)
    try:
        win.wm_attributes("-transparentcolor", CHROMA)
    except tk.TclError:
        pass


def clock_color(t):
    if t == "FT":
        return MUTED
    if ":" in t:
        return PL_GREEN
    return PL_PINK


def local_tz():
    try:
        return datetime.now().astimezone().tzinfo
    except Exception:
        return ZoneInfo("UTC")


def matchday_window(now=None):
    """
    Football day window: [slate 06:00, slate+1 06:00) local.
    Before 06:00 local, slate is still yesterday — covers late kicks (e.g. 04:00)
    without pulling the next evening's slate (20:00).
    """
    now = now or datetime.now(local_tz())
    if now.tzinfo is None:
        now = now.replace(tzinfo=local_tz())
    if now.hour < MATCHDAY_ROLLOVER_HOUR:
        slate = now.date() - timedelta(days=1)
    else:
        slate = now.date()
    start = datetime.combine(slate, dtime(MATCHDAY_ROLLOVER_HOUR, 0), tzinfo=now.tzinfo)
    return start, start + timedelta(days=1)


def in_matchday(kickoff, window=None):
    start, end = window or matchday_window()
    if kickoff.tzinfo is None:
        kickoff = kickoff.replace(tzinfo=start.tzinfo)
    else:
        kickoff = kickoff.astimezone(start.tzinfo)
    return start <= kickoff < end


def parse_espn_dt(value):
    """ESPN uses ...Z; Python 3.14 strptime no longer accepts literal Z in format."""
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _monitors_windows():
    try:
        import ctypes
        from ctypes import wintypes

        class RECT(ctypes.Structure):
            _fields_ = [
                ("left", wintypes.LONG),
                ("top", wintypes.LONG),
                ("right", wintypes.LONG),
                ("bottom", wintypes.LONG),
            ]

        class MONITORINFO(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.DWORD),
                ("rcMonitor", RECT),
                ("rcWork", RECT),
                ("dwFlags", wintypes.DWORD),
            ]

        MONITORINFOF_PRIMARY = 1
        monitors = []
        user32 = ctypes.windll.user32

        def _cb(hmon, hdc, pref, data):
            info = MONITORINFO()
            info.cbSize = ctypes.sizeof(MONITORINFO)
            primary = False
            if user32.GetMonitorInfoW(hmon, ctypes.byref(info)):
                r = info.rcMonitor
                primary = bool(info.dwFlags & MONITORINFOF_PRIMARY)
            else:
                r = pref.contents
            monitors.append(
                {
                    "x": int(r.left),
                    "y": int(r.top),
                    "w": int(r.right - r.left),
                    "h": int(r.bottom - r.top),
                    "name": f"Display {len(monitors) + 1}",
                    "primary": primary,
                }
            )
            return 1

        MonitorEnumProc = ctypes.WINFUNCTYPE(
            ctypes.c_int, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(RECT), wintypes.LPARAM
        )
        user32.EnumDisplayMonitors(0, 0, MonitorEnumProc(_cb), 0)
        return monitors
    except Exception:
        return []


def _monitors_xrandr():
    import re
    import shutil
    import subprocess

    if not shutil.which("xrandr"):
        return []
    try:
        out = subprocess.check_output(["xrandr", "--query"], text=True, stderr=subprocess.DEVNULL)
    except Exception:
        return []
    monitors = []
    # e.g. HDMI-1 connected primary 1920x1080+0+0
    pat = re.compile(
        r"^(\S+)\s+connected(?:\s+primary)?\s+(\d+)x(\d+)\+(\d+)\+(\d+)", re.M
    )
    for m in pat.finditer(out):
        name, w, h, x, y = m.groups()
        monitors.append(
            {"name": name, "w": int(w), "h": int(h), "x": int(x), "y": int(y), "primary": "primary" in m.group(0)}
        )
    return monitors


def _monitors_gdk():
    try:
        import gi

        gi.require_version("Gdk", "3.0")
        from gi.repository import Gdk

        display = Gdk.Display.get_default()
        if not display:
            return []
        n = display.get_n_monitors()
        monitors = []
        for i in range(n):
            mon = display.get_monitor(i)
            geo = mon.get_geometry()
            primary = False
            try:
                primary = bool(mon.is_primary())
            except Exception:
                primary = False
            monitors.append(
                {
                    "name": f"Monitor {i + 1}",
                    "x": int(geo.x),
                    "y": int(geo.y),
                    "w": int(geo.width),
                    "h": int(geo.height),
                    "primary": primary,
                }
            )
        return monitors
    except Exception:
        return []


def list_monitors(tk_root=None):
    """Return [{name,x,y,w,h,primary,label}, ...] for connected displays."""
    monitors = _monitors_windows() or _monitors_xrandr() or _monitors_gdk()
    if not monitors:
        if tk_root is not None:
            try:
                w, h = tk_root.winfo_screenwidth(), tk_root.winfo_screenheight()
            except tk.TclError:
                w, h = 1920, 1080
        else:
            w, h = 1920, 1080
        monitors = [{"name": "Screen 1", "x": 0, "y": 0, "w": w, "h": h, "primary": True}]
    # Fallback: origin-containing screen counts as primary if OS never marked one
    if not any(m.get("primary") for m in monitors):
        for m in monitors:
            if m["x"] <= 0 < m["x"] + m["w"] and m["y"] <= 0 < m["y"] + m["h"]:
                m["primary"] = True
                break
        else:
            monitors[0]["primary"] = True
    for i, m in enumerate(monitors):
        m.setdefault("name", f"Screen {i + 1}")
        primary = " · primary" if m.get("primary") else ""
        m["label"] = f"{i + 1}. {m['name']}  {m['w']}×{m['h']}{primary}"
    return monitors


def primary_monitor_index(tk_root=None):
    monitors = list_monitors(tk_root)
    for i, m in enumerate(monitors):
        if m.get("primary"):
            return i
    return 0


def resolve_monitor_index(index=None, tk_root=None):
    """Use saved index when set; else OS primary."""
    monitors = list_monitors(tk_root)
    if not monitors:
        return 0
    if index is None or index == "":
        return primary_monitor_index(tk_root)
    try:
        i = int(index)
    except (TypeError, ValueError):
        return primary_monitor_index(tk_root)
    if i < 0 or i >= len(monitors):
        return primary_monitor_index(tk_root)
    return i


def get_monitor(index=None, tk_root=None):
    monitors = list_monitors(tk_root)
    if not monitors:
        return {"x": 0, "y": 0, "w": 1920, "h": 1080, "name": "Screen 1", "primary": True}
    i = resolve_monitor_index(index, tk_root)
    return monitors[i]


# ---------- widgets ----------
class GlassButton(tk.Label):
    def __init__(self, parent, label, command, kind="default", min_w=0, height=28):
        super().__init__(parent, bg=PANEL_BG, bd=0, cursor="hand2")
        self.command = command
        self.min_w = min_w
        self.height = height
        self.set(label, kind)
        self.bind("<Enter>", lambda e: self.configure(image=self._hover))
        self.bind("<Leave>", lambda e: self.configure(image=self._normal))
        self.bind("<Button-1>", lambda e: self.command())

    def set(self, label, kind="default"):
        self._normal = ImageTk.PhotoImage(make_button(label, kind, min_w=self.min_w, height=self.height))
        self._hover = ImageTk.PhotoImage(
            make_button(label, kind, hover=True, min_w=self.min_w, height=self.height)
        )
        self.configure(image=self._normal)


class GoalBubble(tk.Toplevel):
    def __init__(self, master, text):
        super().__init__(master)
        setup_overlay(self, 0.96)
        self.visible = True
        bg = tk.Label(self, bg=CHROMA, bd=0)
        bg.place(x=0, y=0)
        body = tk.Frame(self, bg=PANEL_BG)
        tk.Label(body, text="GOAL", bg=PANEL_BG, fg=PL_GREEN, font=FONT_TINY).pack(side=tk.LEFT, padx=(0, 6))
        tk.Label(body, text=text, bg=PANEL_BG, fg=TEXT_COLOR, font=FONT_TINY).pack(side=tk.LEFT)
        body.update_idletasks()
        w, h = body.winfo_reqwidth() + 32, 32
        self._ph = ImageTk.PhotoImage(make_glass(w, h))
        bg.configure(image=self._ph)
        body.place(x=16, y=(h - body.winfo_reqheight()) // 2)
        self.h = h
        self.geometry(f"{w}x{h}+-2000+-2000")

    def place_above(self, x, y):
        if not self.visible:
            self.deiconify()
            self.visible = True
        self.geometry(f"+{int(x)}+{int(y - self.h - 6)}")

    def hide(self):
        if self.visible:
            self.withdraw()
            self.visible = False


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


class MatchPill(tk.Toplevel):
    def __init__(self, app, match, x, y):
        super().__init__(app.root)
        setup_overlay(self)
        self.app = app
        self.match = match
        self._press = None
        self._dragging = False

        self._ph = ImageTk.PhotoImage(make_glass(PILL_W, PILL_H))
        self.bg = tk.Label(self, image=self._ph, bg=CHROMA, bd=0)
        self.bg.place(x=0, y=0, relwidth=1, relheight=1)

        self.body = tk.Frame(self, bg=PANEL_BG)
        self.body.place(x=14, y=8, width=PILL_W - 28, height=PILL_H - 16)
        self.lbl_home = tk.Label(self.body, bg=PANEL_BG, fg=TEXT_COLOR, font=FONT_TINY, bd=0)
        self.lbl_home.pack(side=tk.LEFT)
        self.lbl_away = tk.Label(self.body, bg=PANEL_BG, fg=TEXT_COLOR, font=FONT_TINY, bd=0)
        self.lbl_away.pack(side=tk.RIGHT)
        self.mid = tk.Frame(self.body, bg=PANEL_BG)
        self.mid.pack(side=tk.LEFT, expand=True)
        self.lbl_score = tk.Label(self.mid, bg=PANEL_BG, fg=TEXT_COLOR, font=FONT_SCORE)
        self.lbl_score.pack()
        self.lbl_clock = tk.Label(self.mid, bg=PANEL_BG, font=FONT_TINY)
        self.lbl_clock.pack()
        self.lbl_league = tk.Label(self.mid, bg=PANEL_BG, fg=MUTED, font=FONT_TINY)
        self.lbl_league.pack()

        for w in (
            self.bg,
            self.body,
            self.mid,
            self.lbl_home,
            self.lbl_away,
            self.lbl_score,
            self.lbl_clock,
            self.lbl_league,
        ):
            w.bind("<ButtonPress-1>", self._on_press)
            w.bind("<B1-Motion>", self._on_motion)
            w.bind("<ButtonRelease-1>", self._on_release)
            w.bind("<Button-3>", self._on_menu)

        self.geometry(f"{PILL_W}x{PILL_H}+{int(x)}+{int(y)}")
        self.update_match(match)

    @property
    def match_id(self):
        return str(self.match["id"])

    def update_match(self, match):
        self.match = match
        for lbl, side in ((self.lbl_home, "home"), (self.lbl_away, "away")):
            img = self.app.get_team_icon(match[side]["tla"], match[side]["logo"], size=PILL_ICON)
            if img:
                lbl.configure(image=img, text="")
                lbl.image = img
            else:
                lbl.configure(image="", text=match[side]["tla"])
        self.lbl_score.configure(text=f"{match['home']['score']} - {match['away']['score']}")
        self.lbl_clock.configure(text=match["time"], fg=clock_color(match["time"]))
        self.lbl_league.configure(text=match.get("league_short", ""))

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
        menu.add_command(label="Show timeline", command=lambda: self.app.timeline.open(self.match, self))
        menu.add_command(label="Hide this match", command=lambda: self.app.hide_match_pill(self.match_id))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()


class ControlDock(tk.Toplevel):
    """Independently movable control bar. Can minimize to icon-only strip."""

    def __init__(self, app):
        super().__init__(app.root)
        setup_overlay(self)
        self.app = app
        self.minimized = bool(app.settings.get("ctrl_minimized", False))
        self._move_off = (0, 0)

        self.bg = tk.Label(self, bg=CHROMA, bd=0)
        self.bg.place(x=0, y=0)
        self.body = tk.Frame(self, bg=PANEL_BG)

        self._build()
        self._place_default()

    def _clear_body(self):
        for w in self.body.winfo_children():
            w.destroy()

    def _build(self):
        self._clear_body()
        if self.minimized:
            self._build_mini()
        else:
            self._build_full()
        self.body.update_idletasks()
        h = CTRL_MIN_H if self.minimized else CTRL_H
        w = self.body.winfo_reqwidth() + 28
        self._ph = ImageTk.PhotoImage(make_glass(w, h))
        self.bg.configure(image=self._ph)
        self.body.place(x=14, y=(h - self.body.winfo_reqheight()) // 2)
        # keep current screen position when rebuilding
        try:
            x, y = self.winfo_x(), self.winfo_y()
        except tk.TclError:
            x, y = 100, 100
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.bg.bind("<ButtonPress-1>", self._start_move)
        self.bg.bind("<B1-Motion>", self._do_move)
        self.body.bind("<ButtonPress-1>", self._start_move)
        self.body.bind("<B1-Motion>", self._do_move)

    def _build_full(self):
        handle = tk.Label(self.body, text="Live", bg=PANEL_BG, fg=MUTED, font=FONT_UI_BOLD, cursor="fleur")
        handle.pack(side=tk.LEFT, padx=(0, 8))
        handle.bind("<ButtonPress-1>", self._start_move)
        handle.bind("<B1-Motion>", self._do_move)

        self.btn_refresh = GlassButton(self.body, "Refresh", self.app.manual_refresh, min_w=96)
        self.btn_refresh.pack(side=tk.LEFT, padx=3)
        GlassButton(self.body, "Test goal", self.app.run_test_notification).pack(side=tk.LEFT, padx=3)
        self.btn_free = GlassButton(
            self.body,
            "Float matches: On" if self.app.free_float else "Float matches: Off",
            self.app.toggle_free_float,
            "on" if self.app.free_float else "muted",
            min_w=150,
        )
        self.btn_free.pack(side=tk.LEFT, padx=3)
        self.btn_hidden = GlassButton(self.body, "Hidden (0)", self.app.show_hidden_menu, "muted", min_w=100)
        self.btn_hidden.pack(side=tk.LEFT, padx=3)
        GlassButton(self.body, "Settings", self.app.show_settings_dialog).pack(side=tk.LEFT, padx=3)
        GlassButton(self.body, "Minimize", self.toggle_minimize, "muted").pack(side=tk.LEFT, padx=3)
        GlassButton(self.body, "Quit", self.app.close_app, "danger").pack(side=tk.LEFT, padx=(8, 0))
        self.set_hidden(len(self.app.hidden_pills))

    def _build_mini(self):
        # icon-only: short glyphs, same actions
        handle = tk.Label(self.body, text="⋮⋮", bg=PANEL_BG, fg=MUTED, font=FONT_UI_BOLD, cursor="fleur")
        handle.pack(side=tk.LEFT, padx=(0, 4))
        handle.bind("<ButtonPress-1>", self._start_move)
        handle.bind("<B1-Motion>", self._do_move)

        h = 26
        self.btn_refresh = GlassButton(self.body, "↻", self.app.manual_refresh, min_w=28, height=h)
        self.btn_refresh.pack(side=tk.LEFT, padx=2)
        GlassButton(self.body, "⚽", self.app.run_test_notification, min_w=28, height=h).pack(side=tk.LEFT, padx=2)
        self.btn_free = GlassButton(
            self.body,
            "F",
            self.app.toggle_free_float,
            "on" if self.app.free_float else "muted",
            min_w=28,
            height=h,
        )
        self.btn_free.pack(side=tk.LEFT, padx=2)
        self.btn_hidden = GlassButton(self.body, "H", self.app.show_hidden_menu, "muted", min_w=28, height=h)
        self.btn_hidden.pack(side=tk.LEFT, padx=2)
        GlassButton(self.body, "⚙", self.app.show_settings_dialog, "muted", min_w=28, height=h).pack(
            side=tk.LEFT, padx=2
        )
        GlassButton(self.body, "▢", self.toggle_minimize, "default", min_w=28, height=h).pack(side=tk.LEFT, padx=2)
        GlassButton(self.body, "✕", self.app.close_app, "danger", min_w=28, height=h).pack(side=tk.LEFT, padx=(4, 0))
        self.set_hidden(len(self.app.hidden_pills))

    def _place_default(self):
        # Prefer apply_display_layout; this is a safe initial spot under ticker / on monitor
        pos = self.app.settings.get("ctrl_pos")
        mon = self.app.selected_monitor()
        if pos and mon["x"] <= int(pos[0]) < mon["x"] + mon["w"] and mon["y"] <= int(pos[1]) < mon["y"] + mon["h"]:
            self.geometry(f"+{int(pos[0])}+{int(pos[1])}")
            return
        try:
            tx = self.app.root.winfo_rootx()
            ty = self.app.root.winfo_rooty()
            tw = self.app.root.winfo_width() or TICKER_W
            th = self.app.root.winfo_height() or TICKER_H
        except tk.TclError:
            tx = mon["x"] + (mon["w"] - TICKER_W) // 2
            ty, tw, th = mon["y"] + 80, TICKER_W, TICKER_H
        self.update_idletasks()
        cw = self.winfo_width() or 400
        x = tx + (tw - cw) // 2
        y = ty + th + ROW_GAP
        self.geometry(f"+{x}+{y}")

    def toggle_minimize(self):
        self.minimized = not self.minimized
        self.app.settings["ctrl_minimized"] = self.minimized
        self.app.save_settings()
        self._build()

    def set_free_button(self):
        if not hasattr(self, "btn_free"):
            return
        if self.minimized:
            self.btn_free.set("F", "on" if self.app.free_float else "muted")
        else:
            label = "Float matches: On" if self.app.free_float else "Float matches: Off"
            self.btn_free.set(label, "on" if self.app.free_float else "muted")

    def set_refresh(self, label, kind="default"):
        if hasattr(self, "btn_refresh"):
            if self.minimized and kind != "busy":
                self.btn_refresh.set("↻", kind)
            elif self.minimized and kind == "busy":
                self.btn_refresh.set("…", "busy")
            else:
                self.btn_refresh.set(label, kind)

    def set_hidden(self, n):
        if not hasattr(self, "btn_hidden"):
            return
        if self.minimized:
            self.btn_hidden.set("H" if n == 0 else str(n), "default" if n else "muted")
        else:
            self.btn_hidden.set(f"Hidden ({n})", "default" if n else "muted")

    def _start_move(self, event):
        self._move_off = (event.x_root - self.winfo_x(), event.y_root - self.winfo_y())

    def _do_move(self, event):
        ox, oy = self._move_off
        self.geometry(f"+{event.x_root - ox}+{event.y_root - oy}")
        self.app.settings["ctrl_pos"] = [self.winfo_x(), self.winfo_y()]
        self.app.save_settings()


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


class SmartTicker:
    def __init__(self, root):
        self.root = root
        self.image_cache = {}
        self.last_scores = {}
        self.match_details_cache = {}
        self.assist_cache = {}
        self.current_matches = []

        self.active_alerts = {}
        self.active_bubbles = []

        self.free_float = False
        self.match_pills = {}
        self._hidden_labels = {}
        self.pill_positions, self.hidden_pills = self.load_pill_state()
        self.settings = self.load_settings()

        self.scroll_x = 0
        self.content_width = 0
        self.running = True
        self.hover_ticker = False
        self.scroll_locked = False
        self._move_off = (0, 0)

        self.setup_ticker_window()
        self.timeline = TimelinePanel(self)
        self.dock = ControlDock(self)

        # Every launch: ask leagues/filters/display unless user opted out
        if self.settings.get("skip_startup_dialog") and self.settings.get("filters_set"):
            self.apply_display_layout(force=False)
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
    def setup_ticker_window(self):
        setup_overlay(self.root)
        self.ticker_bg = tk.Label(self.root, bg=CHROMA, bd=0)
        self._ticker_ph = ImageTk.PhotoImage(make_glass(TICKER_W, TICKER_H))
        self.ticker_bg.configure(image=self._ticker_ph)
        self.ticker_bg.place(x=0, y=0, width=TICKER_W, height=TICKER_H)

        self.ticker_body = tk.Frame(self.root, bg=PANEL_BG)
        self.ticker_body.place(x=24, y=6, width=TICKER_W - 48, height=TICKER_H - 12)
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

        # Temporary place; apply_display_layout() runs after dock exists / dialog save
        mon = get_monitor(self.settings.get("monitor_index"), self.root)
        self.root.geometry(
            f"{TICKER_W}x{TICKER_H}+{mon['x'] + (mon['w'] - TICKER_W) // 2}+{mon['y'] + 80}"
        )

    def selected_monitor(self):
        return get_monitor(self.settings.get("monitor_index"), self.root)

    def apply_display_layout(self, force=False):
        """Place ticker + control dock on the chosen monitor."""
        mon = self.selected_monitor()
        pos = self.settings.get("ticker_pos")
        use_saved = (
            not force
            and pos
            and mon["x"] <= int(pos[0]) < mon["x"] + mon["w"]
            and mon["y"] <= int(pos[1]) < mon["y"] + mon["h"]
        )
        if use_saved:
            tx, ty = int(pos[0]), int(pos[1])
        else:
            tx = mon["x"] + (mon["w"] - TICKER_W) // 2
            ty = mon["y"] + 80
            self.settings["ticker_pos"] = [tx, ty]

        self.root.geometry(f"{TICKER_W}x{TICKER_H}+{tx}+{ty}")
        self.root.update_idletasks()

        if hasattr(self, "dock"):
            self.dock.update_idletasks()
            cw = max(self.dock.winfo_width(), self.dock.winfo_reqwidth(), 320)
            cpos = self.settings.get("ctrl_pos")
            use_c = (
                not force
                and cpos
                and mon["x"] <= int(cpos[0]) < mon["x"] + mon["w"]
                and mon["y"] <= int(cpos[1]) < mon["y"] + mon["h"]
            )
            if use_c:
                dx, dy = int(cpos[0]), int(cpos[1])
            else:
                dx = mon["x"] + (mon["w"] - cw) // 2
                dy = ty + TICKER_H + ROW_GAP
                self.settings["ctrl_pos"] = [dx, dy]
            self.dock.geometry(f"+{dx}+{dy}")
        self.save_settings()

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
        self.timeline.sync_follow()
        self.root.after(ANIMATION_SPEED, self.animate_ticker)

    def check_expired_alerts(self):
        now = time.time()
        for mid in [m for m, d in self.active_alerts.items() if now > d["expires"]]:
            del self.active_alerts[mid]
        kept = []
        for mid, anchor, bubble in self.active_bubbles:
            if mid in self.active_alerts:
                kept.append([mid, anchor, bubble])
            else:
                try:
                    bubble.destroy()
                except tk.TclError:
                    pass
        self.active_bubbles = kept

    def sync_bubbles(self):
        for mid, anchor, bubble in self.active_bubbles:
            try:
                if not anchor.winfo_exists():
                    bubble.hide()
                    continue
                ax, ay = anchor.winfo_rootx(), anchor.winfo_rooty()
                if not self.free_float:
                    cx, cw = self.clip_frame.winfo_rootx(), self.clip_frame.winfo_width()
                    if ax + anchor.winfo_width() < cx or ax > cx + cw:
                        bubble.hide()
                        continue
                    ay = self.root.winfo_rooty()
                bubble.place_above(ax, ay)
            except tk.TclError:
                pass

    def _clear_bubbles(self):
        for _, _, b in self.active_bubbles:
            try:
                b.destroy()
            except tk.TclError:
                pass
        self.active_bubbles = []

    def _add_bubble(self, mid, anchor):
        alert = self.active_alerts.get(mid)
        if alert and time.time() < alert["expires"]:
            self.active_bubbles.append([mid, anchor, GoalBubble(self.root, alert["text"])])

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
            if str(b[0]) == mid:
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
        StartupSettingsDialog(self, startup=False)

    def toggle_free_float(self):
        self.timeline.close()
        self._clear_bubbles()
        self.free_float = not self.free_float
        self.dock.set_free_button()
        if self.free_float:
            self.set_ticker_visible(False)
            self.sync_free_pills(self.current_matches)
        else:
            self._capture_live_pill_positions()
            self.destroy_all_pills()
            self.set_ticker_visible(True)
            self.render_matches(self.current_matches)

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
                time_str = kickoff.astimezone(local_tz()).strftime("%H:%M")
            competitors = event["competitions"][0]["competitors"]
            home = next(c for c in competitors if c["homeAway"] == "home")
            away = next(c for c in competitors if c["homeAway"] == "away")

            events_list = []
            for d in event["competitions"][0].get("details", []):
                clock = d.get("clock", {}).get("displayValue", "")
                type_txt = d.get("type", {}).get("text", "") or ""
                evt = {"time": clock, "player": self.get_player_name_from_detail(d), "assist": None, "type": "other"}
                if self.is_scoring_detail(d, type_txt):
                    evt["type"] = "goal"
                    evt["own_goal"] = bool(d.get("ownGoal") or "Own Goal" in type_txt)
                    if evt["own_goal"]:
                        evt["player"] += " (OG)"
                    if d.get("penaltyKick") or "Penalty" in type_txt:
                        evt["player"] += " (P)"
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
                    "tla": home["team"]["abbreviation"],
                    "logo": home["team"]["logo"],
                    "score": int(home.get("score", 0)),
                },
                "away": {
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

    def enrich_assists(self, m, score):
        goals = [e for e in m["history_list"] if e["type"] == "goal"]
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
            if a and not g.get("own_goal"):
                g["assist"] = a

    @staticmethod
    def goal_text(m):
        goals = [e for e in m["history_list"] if e["type"] == "goal"]
        if not goals:
            return ""
        g = goals[-1]
        return f"{g['player']} {g['time']}" + (f"  ·  assist {g['assist']}" if g.get("assist") else "")

    def passes_filters(self, m, window):
        if not in_matchday(m["kickoff"], window):
            return False
        state = m["state"]
        if state == "post":
            return bool(self.settings.get("show_past", True))
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
        dates = {start.strftime("%Y%m%d"), (start + timedelta(days=1)).strftime("%Y%m%d")}
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
                m["last_event"] = self.goal_text(m)
                self.match_details_cache[mid] = m["history_list"]
                if mid in self.last_scores and score != self.last_scores[mid]:
                    self.active_alerts[mid] = {
                        "text": m["last_event"] or "GOAL!",
                        "expires": time.time() + ALERT_DURATION,
                    }
                self.last_scores[mid] = score

            # stable order: kickoff, then league, then id
            parsed.sort(key=lambda m: (m["kickoff"], m["league_id"], m["id"]))
            self.current_matches = parsed
            self.root.after(0, lambda: self.render_matches(parsed))
        except Exception:
            pass
        finally:
            try:
                self.root.after(0, lambda: self.dock.set_refresh("Refresh"))
            except RuntimeError:
                pass

    # ---------- ticker rendering ----------
    def render_matches(self, matches):
        if self.free_float:
            self.sync_free_pills(matches)
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

        for i, m in enumerate(matches):
            item = tk.Frame(self.ticker_frame, bg=PANEL_BG, cursor="hand2")
            item.pack(side=tk.LEFT, padx=12, fill=tk.Y)
            parts = [item]

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
                    clock = tk.Label(
                        mid_box, text=m["time"], bg=PANEL_BG, fg=clock_color(m["time"]), font=FONT_TINY
                    )
                    clock.pack()
                    league = tk.Label(
                        mid_box, text=m.get("league_short", ""), bg=PANEL_BG, fg=MUTED, font=FONT_TINY
                    )
                    league.pack()
                    parts += [mid_box, score, clock, league]
                    continue
                img = self.get_team_icon(m[side]["tla"], m[side]["logo"])
                lbl = tk.Label(item, bg=PANEL_BG, fg=TEXT_COLOR, font=FONT_TINY, bd=0)
                if img:
                    lbl.configure(image=img)
                else:
                    lbl.configure(text=m[side]["tla"])
                lbl.pack(side=tk.LEFT)
                parts.append(lbl)

            for w in parts:
                w.bind(
                    "<Button-1>",
                    lambda e, mm=m, a=item: self.timeline.toggle(mm, a, prefer_above_ticker=True),
                )
                w.bind("<Enter>", lambda e: setattr(self, "hover_ticker", True))
                w.bind("<Leave>", lambda e: setattr(self, "hover_ticker", False))

            if i < len(matches) - 1:
                tk.Frame(self.ticker_frame, bg=DIVIDER, width=1).pack(side=tk.LEFT, fill=tk.Y, pady=8)

            self._add_bubble(m["id"], item)

        self.update_ticker_width()

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
            "text": "Test Player 88'  ·  assist Someone",
            "expires": time.time() + ALERT_DURATION,
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


if __name__ == "__main__":
    root = tk.Tk()
    app = SmartTicker(root)
    root.mainloop()
