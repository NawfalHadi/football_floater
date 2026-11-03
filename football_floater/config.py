"""App constants, paths, and Tk font tuples."""
import os
import shutil
import sys
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
    "uefa.champions": {
        "name": "UEFA Champions League",
        "short": "UCL",
        "logo": "https://a.espncdn.com/i/leaguelogos/soccer/500/2.png",
    },
}
REFRESH_RATE = 90
ANIMATION_SPEED = 40
SCROLL_STEP = 2
ALERT_DURATION = 60  # running-text toast above the ticker
FLOAT_ALERT_DURATION = 8  # free-float in-pill goal/sub pulse
TIMELINE_IDLE_MS = 4000
TIMELINE_LEAVE_MS = 1500
DRAG_THRESHOLD = 4
MATCHDAY_ROLLOVER_HOUR = 6  # local hour when football "day" rolls over
COACH_TIP_MS = 6500

# Package / repo root (parent of this package)
ROOT_DIR = Path(__file__).resolve().parent.parent


def user_config_dir() -> Path:
    """OS user config — portable .exe / AppImage friendly (not beside the binary)."""
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
        return base / "FootballFloater"
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "football-floater"
    return Path.home() / ".config" / "football-floater"


def _data_file(name: str) -> Path:
    """Prefer user config; migrate once from old repo-root copies if present."""
    cfg = user_config_dir()
    dest = cfg / name
    legacy = ROOT_DIR / name
    try:
        cfg.mkdir(parents=True, exist_ok=True)
        if not dest.exists() and legacy.is_file():
            shutil.copy2(legacy, dest)
    except OSError:
        pass
    return dest


POSITIONS_FILE = _data_file("pill_positions.json")
SETTINGS_FILE = _data_file("settings.json")

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
