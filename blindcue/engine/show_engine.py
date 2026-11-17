"""Qt-free state machine for the live show cue list.

``MainWindow`` owns the widgets, the Qt signals and the actual ``list[Cue]``;
this module owns the *pure* show logic that drives them:

  * which cues go LIVE and which get demoted on a layer,
  * how a SIMULTANEOUS chain expands across consecutive cues,
  * how a GROUP container selects its children,
  * the standby-row and auto-follow index arithmetic,
  * blackout / panic / layer-clear status transitions.

The module imports nothing from Qt on purpose: it can be unit-tested headlessly
and reused by non-GUI tooling (CLI preview, exporters, headless schedulers).
"""

from __future__ import annotations

from models.cue import Cue, CueStatus, FollowMode, GroupMode, MediaType, resolve_output_target


def demote_live_on_layer(
    cues: list[Cue],
    layer: int,
    keep_cue_id: int,
    output_target: str = "A",
    dual_active: bool = True,
) -> None:
    """Mark the previously LIVE media cue on *layer* as LOADED.

    ``output_target`` keeps the two independent projector outputs separate: a
    cue firing on output B must not demote a cue live on the same layer of
    output A.  When ``dual_active`` is false there is a single projector, so
    every cue is treated as output A and the collision is real.

    Group containers are intentionally skipped: a GROUP cue is a folder, not
    media, so it must keep its LIVE badge in the cue list while its children
    are playing.  Without this guard the first child fired on the same layer
    demoted its own parent container.
    """
    target = resolve_output_target(output_target, dual_active)
    for other in cues:
        if (
            other.layer == layer
            and resolve_output_target(
                getattr(other, "output_target", "A"), dual_active
            ) == target
            and other.cue_id != keep_cue_id
            and other.status == CueStatus.LIVE
            and other.media_type != MediaType.GROUP
        ):
            other.status = CueStatus.LOADED


def chain_indices(cues: list[Cue], start_idx: int) -> list[int]:
    """Return the contiguous run of cue indices fired by a single GO.

    A SIMULTANEOUS cue pulls in the following cue, which may pull in the next
    one, until a non-SIMULTANEOUS cue (or the end of the list) closes the chain.
    """
    if not (0 <= start_idx < len(cues)):
        return []
    indices: list[int] = []
    visited: set[int] = set()
    idx = start_idx
    while 0 <= idx < len(cues) and idx not in visited:
        visited.add(idx)
        indices.append(idx)
        if cues[idx].follow_mode != FollowMode.SIMULTANEOUS.value:
            break
        idx += 1
    return indices


class ShowEngine:
    """Pure show-state transitions.

    Methods are static and take the cue list explicitly, so the engine never
    holds a stale reference to a list that ``MainWindow`` may replace when
    loading a show or restoring an undo snapshot.
    """

    @staticmethod
    def children_of(cues: list[Cue], group_cue_id: int) -> list[Cue]:
        """Return the children of a GROUP container, in list order."""
        return [c for c in cues if c.parent_id == group_cue_id]

    @staticmethod
    def next_standby_index(cues: list[Cue], last_fired_idx: int) -> int:
        """Return the standby row after the last fired cue.

        Falls back to the last fired cue when the chain reached the end of the
        show, so the selection never lands past the final row.
        """
        nxt = last_fired_idx + 1
        return nxt if nxt < len(cues) else last_fired_idx

    @staticmethod
    def promote_to_live(cues: list[Cue], cue: Cue, dual_active: bool = True) -> None:
        """Demote the same layer/output and mark *cue* LIVE (its pre-delay has elapsed)."""
        demote_live_on_layer(
            cues, cue.layer, cue.cue_id,
            output_target=getattr(cue, "output_target", "A"),
            dual_active=dual_active,
        )
        cue.status = CueStatus.LIVE

    @staticmethod
    def demote_all_live(cues: list[Cue]) -> None:
        """Mark every LIVE cue LOADED (blackout / panic)."""
        for cue in cues:
            if cue.status == CueStatus.LIVE:
                cue.status = CueStatus.LOADED

    @staticmethod
    def clear_layer(
        cues: list[Cue],
        layer: int,
        output_target: str | None = None,
        dual_active: bool = True,
    ) -> None:
        """Demote every LIVE cue on *layer*.

        When *output_target* is ``"A"`` or ``"B"`` only that projector output
        is cleared; ``None`` clears the layer on both outputs.  When
        ``dual_active`` is false every cue is treated as output A.
        """
        target = None if output_target is None else resolve_output_target(
            output_target, dual_active
        )
        for cue in cues:
            if cue.layer != layer or cue.status != CueStatus.LIVE:
                continue
            if target is not None and resolve_output_target(
                getattr(cue, "output_target", "A"), dual_active
            ) != target:
                continue
            cue.status = CueStatus.LOADED

    @staticmethod
    def group_parent(cues: list[Cue], cue: Cue) -> Cue | None:
        """Return the GROUP container that owns *cue*, if any."""
        parent_id = getattr(cue, "parent_id", None)
        if parent_id is None:
            return None
        return next(
            (c for c in cues
             if c.cue_id == parent_id and c.media_type == MediaType.GROUP),
            None,
        )

    @staticmethod
    def group_mode_of(cues: list[Cue], cue: Cue) -> str:
        """Return the container mode (SEQUENCE/LOOP/…) or '' for a plain cue."""
        parent = ShowEngine.group_parent(cues, cue)
        return getattr(parent, "group_mode", "") if parent is not None else ""

    @staticmethod
    def auto_follow_target(cues: list[Cue], finished_cue: Cue) -> int:
        """Return the index to fire after *finished_cue*, or -1 if none.

        The container mode wins over the single child's follow flag: a
        SEQUENCE group cascades to the next child and a LOOP group wraps back
        to the first one, because that is what the operator selected
        ("Cascata" / "Loop Scena") in the inspector.
        """
        parent = ShowEngine.group_parent(cues, finished_cue)
        if parent is not None:
            kids = ShowEngine.children_of(cues, parent.cue_id)
            pos = next(
                (i for i, k in enumerate(kids) if k.cue_id == finished_cue.cue_id),
                -1,
            )
            mode = getattr(parent, "group_mode", "")
            if pos >= 0 and mode == GroupMode.SEQUENCE.value and pos < len(kids) - 1:
                target = kids[pos + 1]
                return next((i for i, c in enumerate(cues) if c is target), -1)
            if pos >= 0 and mode == GroupMode.LOOP.value and kids:
                target = kids[(pos + 1) % len(kids)]
                return next((i for i, c in enumerate(cues) if c is target), -1)
        try:
            idx = cues.index(finished_cue)
        except ValueError:
            return -1
        nxt = idx + 1
        return nxt if 0 <= nxt < len(cues) else -1
