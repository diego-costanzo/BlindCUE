"""Cues that start at a time of day (stage 2, item 2.6).

A cue with ``start_clock`` ("19:55" or "19:55:30") starts by itself at that
time while the show runs - music before the show, the bell before the end of
the interval. More than a minute late (the computer was busy, the show began
later) it is skipped, never started late by surprise. Such a cue is outside
the GO order.
"""

from __future__ import annotations

import re
from datetime import datetime, time, timedelta

from models.cue import Cue

LATE_LIMIT = timedelta(seconds=60)
_CLOCK = re.compile(r"^\s*(\d{1,2}):(\d{2})(?::(\d{2}))?\s*$")


def parse_clock(text: str | None) -> time | None:
    """"19:55" / "7:05:30" -> a time of day; anything else -> None."""
    match = _CLOCK.match(text or "")
    if not match:
        return None
    hours, minutes, seconds = int(match.group(1)), int(match.group(2)), int(match.group(3) or 0)
    if hours > 23 or minutes > 59 or seconds > 59:
        return None
    return time(hours, minutes, seconds)


def normalize_clock(text: str | None) -> str:
    """A valid time as "HH:MM" or "HH:MM:SS"; "" for anything else."""
    parsed = parse_clock(text)
    if parsed is None:
        return ""
    return parsed.strftime("%H:%M:%S" if parsed.second else "%H:%M")


def occurrence(now: datetime, at: time) -> datetime:
    """The *at* nearest to *now*: 00:10 seen at 23:30 is tomorrow's, 23:50 seen at 00:05 yesterday's."""
    when = datetime.combine(now.date(), at)
    if when - now > timedelta(hours=12):
        when -= timedelta(days=1)
    elif now - when > timedelta(hours=12):
        when += timedelta(days=1)
    return when


def due(cues: list[Cue], now: datetime, handled: set[int]) -> tuple[list[Cue], list[Cue]]:
    """(to start now, to skip as too late) among the timed cues not handled yet today."""
    start, skip = [], []
    for cue in cues:
        if cue.cue_id in handled or not getattr(cue, "enabled", True):
            continue
        at = parse_clock(getattr(cue, "start_clock", ""))
        if at is None:
            continue
        when = occurrence(now, at)
        if now < when:
            continue
        (start if now - when <= LATE_LIMIT else skip).append(cue)
    return start, skip


def next_timed(cues: list[Cue], now: datetime, handled: set[int]) -> tuple[Cue, datetime] | None:
    """The next timed cue still to come today (for the clock on the status bar)."""
    best: tuple[Cue, datetime] | None = None
    for cue in cues:
        if cue.cue_id in handled or not getattr(cue, "enabled", True):
            continue
        at = parse_clock(getattr(cue, "start_clock", ""))
        if at is None:
            continue
        when = occurrence(now, at)
        if when >= now and (best is None or when < best[1]):
            best = (cue, when)
    return best
