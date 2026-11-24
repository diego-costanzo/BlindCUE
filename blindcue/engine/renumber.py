"""Renumber the Q labels (stage 5, item 5.2). No Qt.

The cues GO starts (top level, in the GO order; a scene counts as one, its
items keep their labels) get ``prefix + number``: start, start + step, ...
A step of 10 leaves room for cues added later (Q10, Q15, Q20). Only the
chosen rows, or every row when nothing is chosen.
"""

from __future__ import annotations

from collections.abc import Iterable

from engine.show_engine import outside_go_order
from models.cue import Cue


def numbered_rows(cues: list[Cue], chosen: Iterable[int] = ()) -> list[int]:
    wanted = set(chosen)
    return [i for i, c in enumerate(cues)
            if (not wanted or i in wanted) and c.parent_id is None and not outside_go_order(c)
            and getattr(c, "enabled", True)]


def plan(cues: list[Cue], chosen: Iterable[int] = (), start: int = 1, step: int = 1,
         prefix: str = "Q") -> list[tuple[int, str, str]]:
    """(row, old label, new label) for every cue that gets a number."""
    out = []
    for n, row in enumerate(numbered_rows(cues, chosen)):
        out.append((row, cues[row].q_label or "", f"{prefix}{start + n * max(1, step)}"))
    return out


def apply(cues: list[Cue], changes: list[tuple[int, str, str]]) -> int:
    """Write the new labels; how many changed."""
    changed = 0
    for row, _old, new in changes:
        if 0 <= row < len(cues) and cues[row].q_label != new:
            cues[row].q_label = new
            changed += 1
    return changed
