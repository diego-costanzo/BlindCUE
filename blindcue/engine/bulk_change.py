"""One relative change for several cues at once (stage 5, item 5.2). No Qt.

"Change the selected cues": louder or quieter by N dB, fades and delays
longer or shorter by N seconds - each cue keeps its own value and moves by
the same step (unlike the inspector, which gives every selected cue the same
value). ``plan`` says what would change (for the preview before OK),
``apply`` does it. Fields that do not suit a cue are left alone: a picture
has no volume, a scene or an action has no fades.

The labels of the cues (Q) can be locked once the script is approved
(``locked_change``): a label that is there stays, an empty one may still be
filled in (a cue added later, "Q15a").
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from models.cue import Cue, MediaType

VOLUME_DB = "volume_db"
DELTA_FIELDS = ("fade_in", "fade_out", "pre_delay", "post_delay")
MAX_DB = 40.0
MAX_SECONDS = 600.0


@dataclass(frozen=True)
class Step:
    row: int
    field: str      # a Cue attribute: "volume", "fade_in", ...
    old: float
    new: float


def _fits(cue: Cue, field: str) -> bool:
    kind = cue.media_type
    if field == "volume":
        return kind in (MediaType.AUDIO, MediaType.VIDEO)
    if field in ("fade_in", "fade_out"):
        return kind in (MediaType.AUDIO, MediaType.VIDEO, MediaType.IMAGE)
    return True  # pre / post delay: every cue, scenes too


def with_scene_cues(cues: list[Cue], rows: Iterable[int]) -> list[int]:
    """*rows* plus the cues inside the selected scenes (and their scenes), in list order."""
    chosen = {r for r in rows if 0 <= r < len(cues)}
    ids = {cues[r].cue_id for r in chosen if cues[r].media_type == MediaType.GROUP}
    grown = True
    while grown:
        grown = False
        for i, cue in enumerate(cues):
            if cue.parent_id in ids and i not in chosen:
                chosen.add(i)
                if cue.media_type == MediaType.GROUP:
                    ids.add(cue.cue_id)
                grown = True
    return sorted(chosen)


def plan(cues: list[Cue], rows: Iterable[int], deltas: dict[str, float]) -> list[Step]:
    """What *deltas* ({"volume_db": -3, "fade_in": 1.5, ...}) would change; unchanged values are left out.

    Volume: multiplied by 10^(dB/20), kept within 0-100 %. Seconds: never below 0.
    """
    steps: list[Step] = []
    db = max(-MAX_DB, min(MAX_DB, float(deltas.get(VOLUME_DB, 0.0) or 0.0)))
    for row in rows:
        if not 0 <= row < len(cues):
            continue
        cue = cues[row]
        if db and _fits(cue, "volume"):
            old = float(cue.volume)
            new = round(max(0.0, min(1.0, old * 10 ** (db / 20.0))), 4)
            if new != round(old, 4):
                steps.append(Step(row, "volume", old, new))
        for field in DELTA_FIELDS:
            delta = float(deltas.get(field, 0.0) or 0.0)
            if not delta or not _fits(cue, field):
                continue
            old = float(getattr(cue, field))
            new = round(max(0.0, min(MAX_SECONDS, old + delta)), 3)
            if new != round(old, 3):
                steps.append(Step(row, field, old, new))
    return steps


def apply(cues: list[Cue], steps: Iterable[Step]) -> int:
    """Apply *steps*; the number of cues changed."""
    touched = set()
    for step in steps:
        if 0 <= step.row < len(cues):
            setattr(cues[step.row], step.field, step.new)
            touched.add(step.row)
    return len(touched)


def locked_change(old_label: str, new_label: str, locked: bool) -> bool:
    """True when the change would alter a label the lock protects."""
    return bool(locked and (old_label or "").strip() and (old_label or "").strip() != (new_label or "").strip())
