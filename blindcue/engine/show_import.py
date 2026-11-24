"""Cues taken over from another show (stage 5, item 5.3). No Qt.

``take_over`` copies the chosen cues of another show (a chosen scene brings
its cues) with new cue ids, so they never collide with the open show, and
keeps the links between them: a scene and its cues, a start relative to a
cue, the cues an action acts on. A link to a cue that is not taken over is
dropped and reported, and so is a media file that is not there. The media
go into the show's folder the next time it is saved as a portable show.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from models.cue import Cue, MediaType


def _with_children(cues: list[Cue], ids: set[int]) -> set[int]:
    wanted = set(ids)
    changed = True
    while changed:
        changed = False
        for cue in cues:
            if cue.parent_id in wanted and cue.cue_id not in wanted:
                wanted.add(cue.cue_id)
                changed = True
    return wanted


def take_over(other: list[Cue], chosen_ids: Iterable[int]) -> tuple[list[Cue], list[tuple[str, str, int]]]:
    """(new cues in the other show's order, warnings as (kind, cue name, count)).

    kind: "relative" (its relative start was dropped), "targets" (count action targets dropped),
    "file" (its media file is not there).
    """
    wanted = _with_children(other, {int(i) for i in chosen_ids})
    picked = [c for c in other if c.cue_id in wanted]
    new_id = {c.cue_id: next(Cue._id_counter) for c in picked}
    warnings: list[tuple[str, str, int]] = []
    out: list[Cue] = []
    for cue in picked:
        data = cue.to_dict()
        data["cue_id"] = new_id[cue.cue_id]
        if cue.parent_id is not None:
            data["parent_id"] = new_id.get(cue.parent_id)  # a parent not taken over: top level
        ref = getattr(cue, "start_rel_cue", None)
        if ref is not None:
            if ref in new_id:
                data["start_rel_cue"] = new_id[ref]
            else:
                data["start_rel_cue"] = None
                warnings.append(("relative", cue.name, 1))
        if cue.media_type == MediaType.ACTION and isinstance(data.get("action_spec"), dict):
            spec = dict(data["action_spec"])
            ids = [int(i) for i in spec.get("cue_ids", [])]
            kept = [new_id[i] for i in ids if i in new_id]
            if len(kept) != len(ids):
                warnings.append(("targets", cue.name, len(ids) - len(kept)))
            spec["cue_ids"] = kept
            data["action_spec"] = spec
        copy = Cue.from_dict(data)
        if copy.media_type.has_file and not copy.text_spec and not Path(copy.file_path).is_file():
            warnings.append(("file", cue.name, 1))
        out.append(copy)
    return out, warnings
