"""Cues taken over from another show (stage 5, item 5.3). No Qt.

``take_over`` copies the chosen cues of another show (a chosen scene brings
its cues) with new cue ids, so they never collide with the open show, and
keeps the links between them: a scene and its cues, a start relative to a
cue, the cues an action acts on. A link to a cue that is not taken over is
dropped and reported, and so is a media file that is not there. The media
go into the show's folder the next time it is saved as a portable show.

"Simultaneous" and Auto-GO tie a cue to the row after it, by position: a
tie to a cue that is not taken over (or no longer comes next) would start
a cue of the open show instead, so it becomes a plain GO and is reported.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from engine.show_engine import outside_go_order
from models.cue import ACTION_CALL, ACTION_GOTO, ACTION_TARGET_CUES, Cue, FollowMode, MediaType


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


def _next_in_order(cues: list[Cue], row: int, rows: Iterable[int]) -> int:
    """The first of *rows* after *row* that GO does not skip, or -1."""
    return next((r for r in rows if r > row and not outside_go_order(cues[r])), -1)


def _uses_cue_ids(spec: dict) -> bool:
    return spec.get("target") == ACTION_TARGET_CUES or spec.get("kind") in (ACTION_GOTO, ACTION_CALL)


def take_over(other: list[Cue], chosen_ids: Iterable[int],
              here: Iterable[Cue] = ()) -> tuple[list[Cue], list[tuple[str, str, int]]]:
    """(new cues in the other show's order, warnings as (kind, cue name, count)).

    *here*: the cues of the open show (for keys already taken by its effects).
    kind: "relative" (its relative start was dropped), "targets" (count action targets dropped),
    "file" (its media file is not there), "tie" (its Simultaneous / Auto-GO became a GO),
    "key" (its effect key is used in this show too), "clock" (it starts at a time of day),
    "call" (only an action starts it and none came along), "enabled" (it was switched off there).
    """
    return _take(other, chosen_ids, here, dry=False)


def preview(other: list[Cue], chosen_ids: Iterable[int], here: Iterable[Cue] = ()) -> list[tuple[str, str, int]]:
    """The warnings ``take_over`` would give, without making anything: shown while the cues are chosen."""
    return _take(other, chosen_ids, here, dry=True)[1]


def chosen_with_children(other: list[Cue], chosen_ids: Iterable[int]) -> set[int]:
    """The ids that come along: the chosen cues and everything inside the chosen scenes."""
    return _with_children(other, {int(i) for i in chosen_ids})


def _take(other: list[Cue], chosen_ids: Iterable[int], here: Iterable[Cue],
          dry: bool) -> tuple[list[Cue], list[tuple[str, str, int]]]:
    wanted = _with_children(other, {int(i) for i in chosen_ids})
    rows = [i for i, c in enumerate(other) if c.cue_id in wanted]
    all_rows = range(len(other))
    picked = [other[i] for i in rows]
    # A dry run never takes numbers from the counter (the preview runs at every tick of a box).
    new_id = {c.cue_id: (-1 - n if dry else next(Cue._id_counter)) for n, c in enumerate(picked)}
    keys_here = {(c.hotkey or "").upper() for c in here
                 if getattr(c, "adlib", False) and getattr(c, "hotkey", "")}
    called = {int(i) for c in picked if c.media_type == MediaType.ACTION and isinstance(c.action_spec, dict)
              and _uses_cue_ids(c.action_spec) for i in c.action_spec.get("cue_ids", [])}
    warnings: list[tuple[str, str, int]] = []
    out: list[Cue] = []
    for row, cue in zip(rows, picked):
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
            if len(kept) != len(ids) and _uses_cue_ids(spec):
                warnings.append(("targets", cue.name, len(ids) - len(kept)))
            spec["cue_ids"] = kept
            data["action_spec"] = spec
        if cue.follow_mode != FollowMode.MANUAL.value and not outside_go_order(cue):
            there = _next_in_order(other, row, all_rows)
            if there >= 0 and there != _next_in_order(other, row, rows):
                data["follow_mode"] = FollowMode.MANUAL.value
                warnings.append(("tie", cue.name, 1))
        if not getattr(cue, "enabled", True):
            data["enabled"] = True  # the versions of that show do not come along
            warnings.append(("enabled", cue.name, 1))
        if getattr(cue, "adlib", False) and (cue.hotkey or "").upper() in keys_here:
            warnings.append(("key", cue.name, 1))
        if getattr(cue, "start_clock", ""):
            warnings.append(("clock", cue.name, 1))
        if getattr(cue, "call_only", False) and cue.cue_id not in called:
            warnings.append(("call", cue.name, 1))
        if dry:
            if cue.media_type.has_file and not cue.text_spec and not Path(cue.file_path).is_file():
                warnings.append(("file", cue.name, 1))
            continue
        copy = Cue.from_dict(data)
        if copy.media_type.has_file and not copy.text_spec and not Path(copy.file_path).is_file():
            warnings.append(("file", cue.name, 1))
        out.append(copy)
    return out, warnings
