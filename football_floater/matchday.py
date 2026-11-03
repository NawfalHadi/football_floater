"""Matchday window (local 06:00 rollover) + ESPN datetime parse."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .config import MATCHDAY_ROLLOVER_HOUR


def local_now():
    """Current time in the user's timezone. `astimezone()` with no args is the OS local zone."""
    return datetime.now().astimezone()


def to_local(dt):
    """Convert an ESPN instant to the user's local timezone. Naive values are UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt.astimezone()


def local_tz():
    return local_now().tzinfo


def matchday_window(now=None):
    """
    Football day window: [slate 06:00, slate+1 06:00) local.
    Before 06:00 local, slate is still yesterday — covers late kicks (e.g. 04:00)
    without pulling the next evening's slate (20:00).
    """
    now = to_local(now) if now is not None else local_now()
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if now.hour < MATCHDAY_ROLLOVER_HOUR:
        midnight -= timedelta(days=1)
    start = midnight + timedelta(hours=MATCHDAY_ROLLOVER_HOUR)
    return start, start + timedelta(days=1)


def in_matchday(kickoff, window=None):
    start, end = window or matchday_window()
    kickoff = to_local(kickoff)
    return to_local(start) <= kickoff < to_local(end)


# Always HH:MM:SS so ticker chips do not grow/shrink every second.
COUNTDOWN_WIDTH = len("KO in 00:00:00")


def countdown_text(kickoff, now=None):
    """Time until kickoff. Prefixed so it is not read as a live match clock."""
    if kickoff is None:
        return None
    kickoff = to_local(kickoff)
    now = to_local(now) if now is not None else local_now()
    remaining = int((kickoff - now).total_seconds())
    if remaining < 0:
        remaining = 0
    hours, rem = divmod(remaining, 3600)
    minutes, seconds = divmod(rem, 60)
    # Cap display hours at 99 so width stays COUNTDOWN_WIDTH.
    hours = min(hours, 99)
    return f"KO in {hours:02d}:{minutes:02d}:{seconds:02d}"


def espn_dates(start, end):
    """Calendar dates to ask ESPN for. Include both local and UTC, since the feed keys off UTC."""
    dates = set()
    for dt in (start, end - timedelta(minutes=1)):
        local = to_local(dt)
        dates.add(local.strftime("%Y%m%d"))
        dates.add(local.astimezone(ZoneInfo("UTC")).strftime("%Y%m%d"))
    return dates


def parse_espn_dt(value):
    """ESPN uses ...Z. Return that instant in the user's local timezone."""
    utc = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if utc.tzinfo is None:
        utc = utc.replace(tzinfo=ZoneInfo("UTC"))
    return to_local(utc)

