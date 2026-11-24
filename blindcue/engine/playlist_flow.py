"""Stage 3, item 3.3: how a playlist moves from one track to the next. No Qt.

A playlist is a GROUP in "one after another" mode with ``playlist=True``.
Its settings live on the group cue (``playlist_*`` fields of ``Cue``); the
order of one run is kept by the main window in a :class:`PlaylistRun` per
playlist, so it survives between GOs (remember the position) and after the
music was put to sleep.

- **Transitions** between tracks: none (gapless as far as Qt allows: the next
  track is opened before the end), crossfade (the next track starts N s
  before the end of this one; this one fades out over them), overlap (the
  next track starts N s before the end; this one plays on to its end) and a
  pause of N s between the tracks.
- **Random order** with a gap: a track never comes back among the last N
  tracks played (as far as the length of the list allows).
- **Remember the position**: a new GO on the playlist goes on with the track
  after the one that played last, instead of starting again from the top.
- **Loop**: after the last track the playlist starts again (a new random
  order each pass); the transitions work across the wrap too.
- **Normalise the whole playlist**: one loudness for every track, reached by
  turning tracks down only (Qt never plays louder than the file).
"""

from __future__ import annotations

import math
import random
from collections.abc import Sequence
from dataclasses import dataclass, field

NONE = "none"
CROSSFADE = "crossfade"
OVERLAP = "overlap"
GAP = "gap"
TRANSITIONS = (NONE, CROSSFADE, OVERLAP, GAP)
DEFAULT_TRANSITION_SEC = 3.0
MAX_TRANSITION_SEC = 30.0
DEFAULT_SHUFFLE_GAP = 3
MAX_SHUFFLE_GAP = 50
# The next track is opened this many seconds (real time) before it is needed.
PRELOAD_SEC = 6.0
# A lead transition never takes more than this share of a track.
MAX_LEAD_SHARE = 0.5
TARGET_LUFS = -16.0


def normalize_transition(value: object) -> str:
    text = str(value or "").strip().lower()
    return text if text in TRANSITIONS else NONE


def clamp_seconds(value: object, default: float = DEFAULT_TRANSITION_SEC) -> float:
    try:
        num = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    if not math.isfinite(num):
        return default
    return round(min(MAX_TRANSITION_SEC, max(0.0, num)), 2)


def clamp_gap(value: object) -> int:
    try:
        num = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return DEFAULT_SHUFFLE_GAP
    return min(MAX_SHUFFLE_GAP, max(0, num))


def lead_seconds(transition: str, seconds: float, track_sec: float | None) -> float:
    """How long before the end of a track the next one starts (0 = at its end).

    Crossfade and overlap only; never more than half the track (a short jingle
    must not be swallowed by the next song).
    """
    if transition not in (CROSSFADE, OVERLAP) or seconds <= 0:
        return 0.0
    if track_sec is not None and track_sec > 0:
        return max(0.0, min(seconds, track_sec * MAX_LEAD_SHARE))
    return seconds


def gap_seconds(transition: str, seconds: float) -> float:
    """The silence between two tracks (the "pause" transition)."""
    return max(0.0, seconds) if transition == GAP else 0.0


@dataclass
class PlaylistRun:
    """Order and position of one playlist while the show runs (never saved)."""

    order: list[int] = field(default_factory=list)   # cue ids of this pass
    pos: int = -1                                     # index in order of the track started last
    history: list[int] = field(default_factory=list)  # tracks started, oldest first
    upcoming: list[int] | None = None                 # the next pass, drawn early (peek at the wrap)
    done: bool = False                                # the last pass ended (no loop)

    def current(self) -> int | None:
        return self.order[self.pos] if 0 <= self.pos < len(self.order) else None


def shuffled(ids: Sequence[int], history: Sequence[int], gap: int,
             rng: random.Random | None = None) -> list[int]:
    """A random order of *ids* in which no track comes back among the last *gap* tracks played.

    Drawn one track at a time from the tracks not heard within the gap
    (counting *history* and the tracks already drawn); when none is left -
    a list shorter than the gap - the one heard longest ago comes first.
    """
    rnd = rng or random
    pool = list(dict.fromkeys(ids))
    gap = max(0, min(int(gap), len(pool) - 1))
    played = list(history)
    out: list[int] = []
    while pool:
        recent = set(played[-gap:]) if gap > 0 else set()
        fresh = [i for i in pool if i not in recent]
        if fresh:
            pick = rnd.choice(fresh)
        else:
            last_seen = {cid: n for n, cid in enumerate(played)}
            pick = min(pool, key=lambda cid: last_seen.get(cid, -1))
        out.append(pick)
        played.append(pick)
        pool.remove(pick)
    return out


def _new_pass(ids: Sequence[int], history: Sequence[int], *, shuffle: bool, gap: int,
              rng: random.Random | None) -> list[int]:
    return shuffled(ids, history, gap, rng) if shuffle else list(ids)


def sync(run: PlaylistRun, ids: Sequence[int]) -> None:
    """The tracks changed in Preparation: forget the gone ones, add the new ones at the end."""
    present = set(ids)
    current = run.current()
    run.order = [cid for cid in run.order if cid in present]
    run.order += [cid for cid in ids if cid not in run.order]
    run.pos = run.order.index(current) if current in run.order else min(run.pos, len(run.order) - 1)
    if run.upcoming is not None:
        run.upcoming = [cid for cid in run.upcoming if cid in present]
        run.upcoming += [cid for cid in ids if cid not in run.upcoming]


def begin(run: PlaylistRun | None, ids: Sequence[int], *, shuffle: bool, gap: int, remember: bool,
          rng: random.Random | None = None) -> tuple[PlaylistRun, int | None]:
    """A GO on the playlist: (the run, the track to start).

    With *remember* the GO goes on after the track that played last (a new
    pass after the last one); otherwise it starts a new pass (a new random
    order with the gap kept across GOs).
    """
    if not ids:
        return run or PlaylistRun(), None
    if run is None:
        run = PlaylistRun()
    else:
        sync(run, ids)
    if remember and run.order and not run.done and run.pos + 1 < len(run.order):
        return run, run.order[run.pos + 1]
    run.order = run.upcoming if run.upcoming else _new_pass(ids, run.history, shuffle=shuffle, gap=gap, rng=rng)
    run.upcoming = None
    run.pos = -1
    run.done = False
    return run, run.order[0] if run.order else None


def note_started(run: PlaylistRun, cue_id: int, ids: Sequence[int], keep: int = 200) -> None:
    """A track started (by the playlist, or by hand on its row): the position follows it."""
    if cue_id not in ids:
        return
    sync(run, ids)
    if cue_id not in run.order:
        run.order.append(cue_id)
    run.pos = run.order.index(cue_id)
    run.done = False
    run.history.append(cue_id)
    del run.history[:-keep]


def peek_next(run: PlaylistRun, after_id: int, ids: Sequence[int], *, loop: bool, shuffle: bool, gap: int,
              rng: random.Random | None = None) -> int | None:
    """The track that will follow *after_id* (None: the playlist ends there).

    At the wrap of a looping playlist the next pass is drawn now and kept, so
    the track opened in advance is really the one that plays.
    """
    if after_id not in run.order:
        return None
    idx = run.order.index(after_id)
    if idx + 1 < len(run.order):
        return run.order[idx + 1]
    if not loop or not ids:
        return None
    if run.upcoming is None:
        upcoming = _new_pass(ids, run.history, shuffle=shuffle, gap=gap, rng=rng)
        if len(upcoming) > 1 and upcoming[0] == after_id:
            upcoming.append(upcoming.pop(0))  # never the same track twice in a row at the wrap
        run.upcoming = upcoming
    return run.upcoming[0] if run.upcoming else None


def advance(run: PlaylistRun, finished_id: int, ids: Sequence[int], *, loop: bool, shuffle: bool, gap: int,
            rng: random.Random | None = None) -> int | None:
    """*finished_id* ended: the track to start now (None: the playlist stops).

    When a later track already started (a transition started it early, or
    the operator started a track by hand), the answer is the track after
    *finished_id* and nothing moves: the caller sees it already started.
    """
    sync(run, ids)
    nxt = peek_next(run, finished_id, ids, loop=loop, shuffle=shuffle, gap=gap, rng=rng)
    if run.current() != finished_id:
        return nxt
    if nxt is None:
        run.done = True
        return None
    if run.order.index(finished_id) + 1 >= len(run.order):
        run.order = run.upcoming or []
        run.upcoming = None
        run.pos = -1
    return nxt


@dataclass(frozen=True)
class Normalized:
    """Result of "normalise the whole playlist"."""

    target_lufs: float          # the loudness every track gets
    gains_db: list[float]       # per track (in the order given)
    limited: bool               # the target is below TARGET_LUFS: a quiet track set it


def normalize_gains(tracks: Sequence[tuple[float, float]], target: float = TARGET_LUFS) -> Normalized:
    """One loudness for every track of a playlist: (measured LUFS, volume 0..1) per track.

    Qt plays a file at most as loud as it is (volume x gain is capped at 1.0),
    so the common target is the highest one every track can reach: never above
    *target*, and lowered when a quiet track at its volume cannot get there.
    The volume of each track stays the operator's choice on top of it.
    """
    usable = [(lufs, vol) for lufs, vol in tracks if math.isfinite(lufs) and vol > 0]
    if not usable:
        return Normalized(target, [0.0 for _ in tracks], False)
    reach = min(lufs - 20.0 * math.log10(vol) for lufs, vol in usable)
    common = min(target, reach)
    gains = [round(common - lufs, 2) if math.isfinite(lufs) and vol > 0 else 0.0 for lufs, vol in tracks]
    return Normalized(round(common, 2), gains, common < target - 0.01)


def pick_rng(seed: int | None = None) -> random.Random:
    """A random source (seeded in tests)."""
    return random.Random(seed)  # a music shuffle, not security
