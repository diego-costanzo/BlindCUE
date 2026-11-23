"""Rehearsal from a chosen moment (stage 2, item 2.4).

``state_before(cues, row)`` works out what the audience would see and hear
when the show reaches *row* (before its GO): the picture left on each layer
and the music still looping there, with the level and layer opacity the
action cues set on the way. Only what *stays* counts: a picture without a
hold time, a video or sound that loops forever. A sound that simply plays
to its end is not brought back - its timing depends on the operator. Stops
and fades on the way remove what they act on.

The window shows this as a list ("on screen: L1 'Forest' from #5 …"),
stops what plays (after asking) and starts these cues again, then puts GO
on *row*.
"""

from __future__ import annotations

from dataclasses import dataclass

from engine.action_cues import expand_cue_ids
from engine.show_engine import outside_go_order
from models.cue import (
    ACTION_FADE,
    ACTION_LEVEL,
    ACTION_OPACITY,
    ACTION_RELEASE,
    ACTION_STOP,
    ACTION_TARGET_ALL,
    ACTION_TARGET_CUES,
    ACTION_TARGET_LAYER,
    Cue,
    MediaType,
    resolve_output_target,
)


@dataclass
class LayerState:
    cue: Cue
    row: int
    level_db: float = 0.0        # relative level changes on the way (dB)
    level_abs: float | None = None  # an absolute level set on the way (0..1)
    opacity: float | None = None    # layer opacity set on the way (0..1)


def _stays(cue: Cue) -> bool:
    """True when *cue* is still there long after its start (a still picture, an endless loop)."""
    if cue.media_type == MediaType.IMAGE:
        return float(cue.hold_time) <= 0
    if cue.media_type in (MediaType.AUDIO, MediaType.VIDEO):
        return bool(cue.loop and cue.loop_count <= 0) or any(
            s.loops == 0 and not s.skip for s in getattr(cue, "sections", []))
    return False


def _key(cue: Cue, dual_active: bool) -> tuple[str, int]:
    output = resolve_output_target(getattr(cue, "output_target", "A"), dual_active)
    return (output, int(cue.layer))


def state_before(cues: list[Cue], row: int, dual_active: bool = False) -> dict[tuple[str, int], LayerState]:
    """What stays on each (output, layer) when the show reaches *row* (before its GO).

    Relative, call-only and effect cues are left out: when they ran depends on
    the operator, not on the order of the list.
    """
    state: dict[tuple[str, int], LayerState] = {}
    for idx, cue in enumerate(cues[:max(0, row)]):
        if outside_go_order(cue) or cue.media_type == MediaType.GROUP:
            continue
        if cue.media_type == MediaType.ACTION:
            _apply_action(cues, cue, state, dual_active)
            continue
        if not cue.media_type.has_file:
            continue
        if float(getattr(cue, "fade_others", 0.0) or 0.0) > 0:
            for key in [k for k, s in state.items() if s.cue.media_type in (MediaType.AUDIO, MediaType.VIDEO)]:
                state.pop(key, None)  # "fade the others when it starts"
        if _stays(cue):
            state[_key(cue, dual_active)] = LayerState(cue=cue, row=idx)
        else:
            state.pop(_key(cue, dual_active), None)  # it replaced what was there, then ended
    return state


def _apply_action(cues: list[Cue], action: Cue, state: dict[tuple[str, int], LayerState],
                  dual_active: bool = False) -> None:
    spec = action.action_spec
    kind = spec.get("kind")
    target = spec.get("target")
    if target == ACTION_TARGET_ALL:
        keys = list(state)
    elif target == ACTION_TARGET_LAYER:
        keys = [k for k in state if k == (resolve_output_target(spec.get("output", "A"), dual_active),
                                          int(spec.get("layer", 1)))]
    elif target == ACTION_TARGET_CUES:
        ids = expand_cue_ids(cues, spec.get("cue_ids") or [])
        keys = [k for k, s in state.items() if s.cue.cue_id in ids]
    else:
        keys = []
    for key in keys:
        entry = state[key]
        if kind in (ACTION_STOP, ACTION_FADE, ACTION_RELEASE):
            state.pop(key, None)  # a released loop plays its pass and ends
        elif kind == ACTION_LEVEL and entry.cue.media_type != MediaType.IMAGE:
            if spec.get("mode") == "relative":
                entry.level_db += float(spec.get("db", 0.0))
            else:
                entry.level_abs, entry.level_db = float(spec.get("level", 1.0)), 0.0
        elif kind == ACTION_OPACITY:
            entry.opacity = float(spec.get("level", 1.0))
