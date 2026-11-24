"""Renumber the Q labels (stage 5, item 5.2). No Qt.

The cues the operator starts with GO (``show_engine.go_stops``: a scene
counts as one unless it goes step by step, cues pulled in by "Simultaneous"
or started by an Auto-GO are not GO cues) get ``prefix + number``: start,
start + step, ... A step of 10 leaves room for cues added later (Q10, Q15,
Q20). Only the chosen rows, or every GO cue when nothing is chosen. The plan
names cues by ``cue_id``, so it never relabels another cue if the list
changed in the meantime.
"""

from __future__ import annotations

from collections.abc import Iterable

from engine.show_engine import go_stops
from models.cue import Cue


def numbered_rows(cues: list[Cue], chosen: Iterable[int] = ()) -> list[int]:
    wanted = set(chosen)
    return [i for i in go_stops(cues) if not wanted or i in wanted]


def plan(cues: list[Cue], chosen: Iterable[int] = (), start: int = 1, step: int = 1,
         prefix: str = "Q") -> list[tuple[int, str, str]]:
    """(cue_id, old label, new label) for every cue that gets a number."""
    out = []
    for n, row in enumerate(numbered_rows(cues, chosen)):
        out.append((cues[row].cue_id, cues[row].q_label or "", f"{prefix}{start + n * max(1, step)}"))
    return out


def clashes(cues: list[Cue], changes: list[tuple[int, str, str]]) -> set[str]:
    """New labels another cue (one not renumbered) already has: two cues would answer to one Q."""
    ids = {cue_id for cue_id, _old, _new in changes}
    others = {c.q_label for c in cues if c.cue_id not in ids and c.q_label}
    return {new for _cue_id, _old, new in changes if new in others}


def apply(cues: list[Cue], changes: list[tuple[int, str, str]]) -> int:
    """Write the new labels; how many changed."""
    by_id = {c.cue_id: c for c in cues}
    changed = 0
    for cue_id, _old, new in changes:
        cue = by_id.get(cue_id)
        if cue is not None and cue.q_label != new:
            cue.q_label = new
            changed += 1
    return changed
