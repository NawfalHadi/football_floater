"""App constants, paths, and Tk font tuples."""
from pathlib import Path

LEAGUES = {
    "eng.1": {
        "name": "Premier League",
        "short": "PL",
        "logo": "https://a.espncdn.com/i/leaguelogos/soccer/500/eng.1.png",
    },
    "ger.1": {
        "name": "Bundesliga",
        "short": "BL",
        "logo": "https://a.espncdn.com/i/leaguelogos/soccer/500/ger.1.png",
    },
    "esp.1": {
        "name": "La Liga",
        "short": "LL",
        "logo": "https://a.espncdn.com/i/leaguelogos/soccer/500/esp.1.png",
    },
}
REFRESH_RATE = 90
ANIMATION_SPEED = 40
SCROLL_STEP = 2
ALERT_DURATION = 60  # running-text toast above the ticker
FLOAT_ALERT_DURATION = 8  # free-float toast beside a pill
TIMELINE_IDLE_MS = 4000
TIMELINE_LEAVE_MS = 1500
DRAG_THRESHOLD = 4
MATCHDAY_ROLLOVER_HOUR = 6  # local hour when football "day" rolls over

# Persist next to repo root (parent of this package)
ROOT_DIR = Path(__file__).resolve().parent.parent
POSITIONS_FILE = ROOT_DIR / "pill_positions.json"
SETTINGS_FILE = ROOT_DIR / "settings.json"

TICKER_W = 720
TICKER_H = 56
# Empty chroma band above the glass so running-text toasts can place() inside the
# same window and ride scroll_x (separate Toplevels freeze on some WMs).
# Must clear a full GOAL+assist toast + gap — too small and the toast clips into the bar.
TOAST_BAND = 64
TOAST_GAP = 8
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
