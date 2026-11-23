"""Undo the last GO (stage 1.18): what to do with each cue that GO started.

Pure logic, no Qt: the main window keeps the record of the last GO given by
hand and asks :func:`undo_plan` what to do; ``main.py`` carries the steps out
on the players and the output.

One click, no dialog: a mistake costs one repeated GO. Only what that GO
started is touched; a picture it replaced comes back; an audio or video it cut
off does not come back yet (stage 1 C2a step 11 will bring it back from where
it stopped).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from models.cue import Cue, CueStatus, MediaType

# How long Undo stays offered after the GO (seconds, Pause All stops the count).
UNDO_WINDOW_SECONDS = 15.0
# Fade of a sound or a moving picture taken back.
FADE_SECONDS = 1.0
# Fade of a still picture (or a caption) taken off, or dissolve back to the one it replaced.
PICTURE_SECONDS = 0.5

FADE = "fade"            # audio/video on air: fade it out
LIFT = "lift"            # picture on an empty layer: take it off the screen
RESTORE = "restore"      # picture that replaced another picture: the old one comes back
CANCEL = "cancel"        # still waiting in its Pre-Delay: it never starts
ENDED = "ended"          # already over: only the GO pointer moves back
KEEP = "keep"            # action cue: what it did stays
CONTAINER = "container"  # group container: no media of its own, only its state


@dataclass
class UndoRecord:
    """What one GO given by hand started (filled while that GO runs)."""

    first_id: int                                    # the cue the GO was given on
    started: float                                   # time.monotonic() of the GO
    ids: list[int] = field(default_factory=list)     # every cue it started, in order
    replaced: dict[int, int] = field(default_factory=dict)  # cue_id -> cue_id it pushed off its layer
    paused_total: float = 0.0                        # seconds spent in Pause All
    paused_since: float | None = None

    def add(self, cue_id: int) -> None:
        if cue_id not in self.ids:
            self.ids.append(cue_id)

    def age(self, now: float) -> float:
        """Seconds since the GO, not counting Pause All."""
        paused = self.paused_total + (now - self.paused_since if self.paused_since is not None else 0.0)
        return max(0.0, now - self.started - paused)

    def seconds_left(self, now: float) -> float:
        return max(0.0, UNDO_WINDOW_SECONDS - self.age(now))

    def set_paused(self, paused: bool, now: float) -> None:
        if paused and self.paused_since is None:
            self.paused_since = now
        elif not paused and self.paused_since is not None:
            self.paused_total += now - self.paused_since
            self.paused_since = None


@dataclass(frozen=True)
class UndoStep:
    """One cue of the GO and what Undo does with it."""

    cue_id: int
    how: str
    seconds: float = 0.0
    restore_id: int | None = None   # RESTORE: the picture that comes back
    cut_id: int | None = None       # audio/video this cue cut off (does not come back yet)


def _is_picture(cue: Cue | None) -> bool:
    return cue is not None and cue.media_type == MediaType.IMAGE


def _is_timed(cue: Cue | None) -> bool:
    return cue is not None and cue.media_type in (MediaType.AUDIO, MediaType.VIDEO)


def undo_plan(cues: list[Cue], record: UndoRecord, waiting: set[int]) -> list[UndoStep]:
    """Steps for every cue *record* started, in the order they were started.

    *waiting* holds the ids of cues still counting down their Pre-Delay; a
    cue is on air when its status is LIVE.
    """
    by_id = {c.cue_id: c for c in cues}
    steps: list[UndoStep] = []
    for cue_id in record.ids:
        cue = by_id.get(cue_id)
        if cue is None:
            continue  # deleted meanwhile
        if cue.media_type == MediaType.ACTION:
            steps.append(UndoStep(cue_id, KEEP))
            continue
        if cue.media_type == MediaType.GROUP:
            steps.append(UndoStep(cue_id, CONTAINER))
            continue
        if cue_id in waiting:
            steps.append(UndoStep(cue_id, CANCEL))
            continue
        if cue.status != CueStatus.LIVE:
            steps.append(UndoStep(cue_id, ENDED))
            continue
        before = by_id.get(record.replaced.get(cue_id, -1))
        if before is not None and before.cue_id in record.ids:
            before = None  # pushed off by its own GO: nothing to bring back
        cut = before.cue_id if _is_timed(before) else None
        if _is_picture(cue):
            if _is_picture(before):
                steps.append(UndoStep(cue_id, RESTORE, PICTURE_SECONDS, restore_id=before.cue_id))
            else:
                steps.append(UndoStep(cue_id, LIFT, PICTURE_SECONDS, cut_id=cut))
        else:
            steps.append(UndoStep(cue_id, FADE, FADE_SECONDS, cut_id=cut))
    return steps


def can_undo(steps: list[UndoStep]) -> bool:
    """False when Undo would change nothing on stage (only actions kept)."""
    return any(s.how != KEEP for s in steps)
