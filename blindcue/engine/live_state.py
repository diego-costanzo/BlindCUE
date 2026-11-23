"""Qt-free clock of what plays now, one entry per runtime layer.

The players and the scheduler already report position, length and the
Pre/Post-Delay waits many times a second (they drive the layer panels). This
store keeps the latest values, so a single 10 Hz UI clock can redraw just the
time cells of the cue lists instead of rebuilding the lists, which costs
dozens of item roles per cell on every refresh.

Elapsed time comes from the player position, so a pause is not counted.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

PHASE_PRE = "PRE"
PHASE_POST = "POST"

# Warn the operator this long before a cue ends (when the next GO is theirs).
WARN_BEFORE_END_SEC = 5.0


@dataclass
class LayerClock:
    """Latest timing reported for the cue on one runtime layer."""

    cue_id: int
    timed: bool                 # audio/video, or a picture with a hold time
    pos: float = 0.0
    start: float = 0.0
    end: float = 0.0            # 0 = length not known yet
    looping_inf: bool = False
    phase: str = ""             # "" while playing, PHASE_PRE / PHASE_POST while waiting
    wait_elapsed: float = 0.0
    wait_total: float = 0.0


@dataclass(frozen=True)
class CueTime:
    """Where a cue is, ready to be shown."""

    elapsed: float
    remaining: float | None     # None: length unknown
    fraction: float             # 0..1, or -1 when there is nothing to measure
    looping_inf: bool
    phase: str


class LiveClocks:
    """Per-layer timing of the cues on air (and of the ones waiting to start)."""

    def __init__(self) -> None:
        self._layers: dict[int, LayerClock] = {}
        # A cue waiting in its Pre-Delay on a layer where another cue still
        # plays: kept apart, so the playing cue keeps its own clock.
        self._waits: dict[int, LayerClock] = {}

    def start(self, layer: int, cue_id: int, timed: bool, duration: float = 0.0) -> None:
        """A cue went on air on *layer*: its clock starts at zero."""
        self._layers[layer] = LayerClock(cue_id=cue_id, timed=timed, end=max(0.0, float(duration)))
        self._waits.pop(layer, None)

    def progress(
        self,
        layer: int,
        pos: float,
        start: float | None = None,
        end: float | None = None,
        looping_inf: bool | None = None,
    ) -> None:
        """Playback position report for *layer* (ignored when no cue is known there)."""
        clock = self._layers.get(layer)
        if clock is None:
            return
        clock.pos = max(0.0, float(pos))
        if start is not None:
            clock.start = max(0.0, float(start))
        if end is not None:
            clock.end = max(0.0, float(end))
        if looping_inf is not None:
            clock.looping_inf = bool(looping_inf)

    def phase(self, layer: int, cue_id: int, phase: str, elapsed: float, total: float) -> None:
        """A Pre/Post-Delay wait of *cue_id* on *layer*."""
        store = self._layers
        clock = store.get(layer)
        if phase == PHASE_PRE and clock is not None and clock.cue_id != cue_id:
            store = self._waits  # another cue still plays there
            clock = store.get(layer)
        if clock is None or clock.cue_id != cue_id:
            clock = LayerClock(cue_id=cue_id, timed=False)
            store[layer] = clock
        clock.phase = phase
        clock.wait_elapsed = max(0.0, float(elapsed))
        clock.wait_total = max(0.0, float(total))

    def clear(self, layer: int) -> None:
        self._layers.pop(layer, None)
        self._waits.pop(layer, None)

    def clear_all(self) -> None:
        self._layers.clear()
        self._waits.clear()

    def layer_position(self, layer: int) -> float | None:
        """Last reported position (seconds in the file) of the cue on *layer*."""
        clock = self._layers.get(layer)
        return clock.pos if clock is not None and clock.timed else None

    def layer_end(self, layer: int) -> float | None:
        """End (seconds in the file) of the cue on *layer*, when known."""
        clock = self._layers.get(layer)
        return clock.end if clock is not None and clock.timed and clock.end > clock.start else None

    def is_empty(self) -> bool:
        return not self._layers and not self._waits

    def cue_ids(self) -> set[int]:
        return {c.cue_id for c in (*self._layers.values(), *self._waits.values())}

    def forget_cues(self, keep: set[int]) -> None:
        """Drop the clocks of cues that are no longer on air or waiting."""
        for store in (self._layers, self._waits):
            for layer in [lyr for lyr, c in store.items() if c.cue_id not in keep]:
                del store[layer]

    def cue_time(self, cue_id: int) -> CueTime | None:
        """Timing of *cue_id*, or None when nothing measurable is known."""
        clock = next(
            (c for c in (*self._layers.values(), *self._waits.values()) if c.cue_id == cue_id), None
        )
        if clock is None:
            return None
        if clock.phase in (PHASE_PRE, PHASE_POST):
            total = max(0.01, clock.wait_total)
            elapsed = min(clock.wait_elapsed, total)
            return CueTime(elapsed, max(0.0, total - elapsed), elapsed / total, False, clock.phase)
        if not clock.timed:
            return None
        elapsed = max(0.0, clock.pos - clock.start)
        if clock.end > clock.start:
            span = clock.end - clock.start
            return CueTime(elapsed, max(0.0, clock.end - clock.pos),
                           min(1.0, elapsed / span), clock.looping_inf, "")
        return CueTime(elapsed, None, -1.0, clock.looping_inf, "")


def fmt_clock(seconds: float) -> str:
    """MM:SS (H:MM:SS past an hour), whole seconds rounded down.

    The same as the layer panels and the length column, so the operator never
    sees two different numbers for the same cue.
    """
    whole = max(0, math.floor(seconds))
    mins, secs = divmod(whole, 60)
    hrs, mins = divmod(mins, 60)
    if hrs:
        return f"{hrs}:{mins:02d}:{secs:02d}"
    return f"{mins:02d}:{secs:02d}"


def short_time_text(t: CueTime) -> str:
    """Text for the narrow time slot of a cue row: what is left, or the wait."""
    if t.phase == PHASE_PRE:
        return f"⏳-{fmt_clock(t.remaining or 0.0)}"
    if t.phase == PHASE_POST:
        return f"⏱-{fmt_clock(t.remaining or 0.0)}"
    if t.remaining is None:
        return "∞" if t.looping_inf else fmt_clock(t.elapsed)
    text = f"-{fmt_clock(t.remaining)}"
    return f"{text}∞" if t.looping_inf else text


def ends_soon(t: CueTime) -> bool:
    """The cue is about to end by itself (not a wait, not an endless loop)."""
    return (
        not t.phase
        and not t.looping_inf
        and t.remaining is not None
        and t.remaining <= WARN_BEFORE_END_SEC
    )
