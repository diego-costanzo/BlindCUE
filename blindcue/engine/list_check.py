"""Mistakes in the cue list that only show up during the show (stage 5, item 5.6). No Qt.

``list_problems`` finds cues that will not do what the list suggests: a
start relative to a cue that is gone, an action whose target cues are gone
(it would do nothing), a jump / call to nothing, a scene with nothing to
play, a "call only" cue that no action ever calls. The readiness page lists
them before the show; the operator fixes them in Preparation.
"""

from __future__ import annotations

from collections.abc import Iterable

from engine.picture_timing import cue_too_short
from engine.show_engine import outside_go_order
from models.cue import ACTION_CALL, ACTION_GOTO, ACTION_TARGET_CUES, Cue, MediaType

REL_MISSING = "relative_missing"
NO_TARGET = "no_target"
JUMP_NOWHERE = "jump_nowhere"
EMPTY_SCENE = "empty_scene"
NEVER_CALLED = "never_called"
PICTURE_TOO_SHORT = "picture_too_short"  # 4.4: shown shorter than its passages + 0.5 s


def _ids(spec: dict) -> list[int]:
    out = []
    for i in spec.get("cue_ids", []) or []:
        try:
            out.append(int(i))
        except (TypeError, ValueError):
            continue
    return out


def list_problems(cues: Iterable[Cue]) -> list[tuple[int, str]]:
    """(row, kind) for every cue that will not work as the list suggests, in list order."""
    cue_list = list(cues)
    ids = {c.cue_id for c in cue_list}
    called: set[int] = set()
    for cue in cue_list:
        if cue.media_type == MediaType.ACTION and isinstance(cue.action_spec, dict):
            called.update(_ids(cue.action_spec))
    out: list[tuple[int, str]] = []
    for row, cue in enumerate(cue_list):
        if not getattr(cue, "enabled", True):
            continue  # switched off in this version: it never plays anyway
        ref = getattr(cue, "start_rel_cue", None)
        if ref is not None and ref not in ids:
            out.append((row, REL_MISSING))
        if cue.media_type == MediaType.ACTION and isinstance(cue.action_spec, dict):
            spec = cue.action_spec
            alive = [i for i in _ids(spec) if i in ids]
            if spec.get("kind") in (ACTION_GOTO, ACTION_CALL):
                if not alive:
                    out.append((row, JUMP_NOWHERE))
            elif spec.get("target") == ACTION_TARGET_CUES and not alive:
                out.append((row, NO_TARGET))
        if cue.media_type == MediaType.GROUP and not any(
                c.parent_id == cue.cue_id and not outside_go_order(c) for c in cue_list):
            out.append((row, EMPTY_SCENE))
        if getattr(cue, "call_only", False) and cue.cue_id not in called:
            out.append((row, NEVER_CALLED))
        if cue_too_short(cue):
            out.append((row, PICTURE_TOO_SHORT))
    return out
