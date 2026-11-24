"""Picture timing (stage 4.4): a picture shown shorter than its transitions. No Qt.

A timed picture fades in (or crossfades over the previous one) at its start
and fades out at its end, all within its time on screen. Shorter than those
transitions plus half a second, it is never seen still: the audience sees a
flicker. The inspector, the "Edit cue" window and the list check before the
show warn about it.
"""

from __future__ import annotations

from collections.abc import Iterable

from models.cue import Cue, MediaType

STILL_SECONDS = 0.5  # the least time a picture is fully on screen, not changing


def transition_seconds(fade_in: float, fade_out: float, crossfade: float) -> float:
    """Seconds a picture spends coming in and going out.

    Fade In and the crossfade both happen at its start (the longer one counts),
    the Fade Out at its end.
    """
    return max(0.0, float(fade_in or 0.0), float(crossfade or 0.0)) + max(0.0, float(fade_out or 0.0))


def min_hold_seconds(fade_in: float, fade_out: float, crossfade: float) -> float:
    """The shortest time on screen that still shows the picture still for STILL_SECONDS."""
    return round(transition_seconds(fade_in, fade_out, crossfade) + STILL_SECONDS, 2)


def too_short(hold: float, fade_in: float, fade_out: float, crossfade: float) -> bool:
    """True for a timed picture (hold > 0) shown shorter than its transitions + STILL_SECONDS.

    A picture without a time (0 = until the next cue) is never too short.
    """
    hold = float(hold or 0.0)
    return hold > 0 and hold + 1e-6 < min_hold_seconds(fade_in, fade_out, crossfade)


def cue_too_short(cue: Cue) -> bool:
    if cue.media_type != MediaType.IMAGE:
        return False
    return too_short(cue.hold_time, cue.fade_in, cue.fade_out, getattr(cue, "crossfade", 0.0))


def short_pictures(cues: Iterable[Cue]) -> list[int]:
    """Rows of the timed pictures that are shown shorter than their transitions + 0.5 s."""
    return [row for row, cue in enumerate(cues) if getattr(cue, "enabled", True) and cue_too_short(cue)]
