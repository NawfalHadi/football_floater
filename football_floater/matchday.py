"""Matchday window (local 06:00 rollover) + ESPN datetime parse."""
from datetime import datetime, timedelta, time as dtime
from zoneinfo import ZoneInfo

from .config import MATCHDAY_ROLLOVER_HOUR


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

