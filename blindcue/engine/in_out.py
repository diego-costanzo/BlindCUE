"""IN / OUT at the playhead: one rule for the waveform head ("IN/OUT Testina",
keys I and O) and for "start / end here" in the Edit cue window (3.4). No Qt.
"""

from __future__ import annotations

MIN_SPAN = 0.05   # OUT is always at least this far after IN

OUT_SET = "set"       # OUT where the playhead is
OUT_END = "end"       # the playhead is at the end: OUT = end of the file (None)
OUT_MIN = "min"       # the playhead is at or before IN: OUT just after IN


def in_at(playhead: float, duration: float) -> float:
    """IN at *playhead* (0.01 s), never in the last MIN_SPAN of the file."""
    top = max(0.0, duration - MIN_SPAN) if duration > 0 else max(0.0, playhead)
    return round(max(0.0, min(top, playhead)), 2)


def out_at(playhead: float, in_point: float, duration: float) -> tuple[float | None, str]:
    """(OUT, how) at *playhead*: None = the end of the file."""
    if duration > 0 and playhead >= duration - MIN_SPAN:
        return None, OUT_END
    if playhead <= in_point + 0.04:
        target = in_point + MIN_SPAN
        if duration > 0:
            target = min(duration, target)
        return round(target, 2), OUT_MIN
    return round(playhead, 2), OUT_SET
