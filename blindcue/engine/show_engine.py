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
    exclude_ids: set[int] | frozenset[int] = frozenset(),
) -> None:
    """Mark the previously LIVE media cue on *layer* as LOADED.

    Cues in *exclude_ids* play on a borrowed spare player, not on their
    layer, so a cue starting there does not take them off the air.

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
            and other.cue_id not in exclude_ids
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
    if getattr(cues[start_idx], "adlib", False):
        return [start_idx]  # an effect on demand never pulls show cues with it
    indices: list[int] = []
    visited: set[int] = set()
    idx = start_idx
    while 0 <= idx < len(cues) and idx not in visited:
        visited.add(idx)
        indices.append(idx)
        if cues[idx].follow_mode != FollowMode.SIMULTANEOUS.value:
            break
        idx += 1
        while idx < len(cues) and getattr(cues[idx], "adlib", False):
            idx += 1  # effects on demand are not in the order
    return indices


def block_end(cues: list[Cue], idx: int) -> int:
    """Last row of *idx* together with all its descendants (a group's children)."""
    cue = cues[idx]
    if cue.media_type != MediaType.GROUP:
        return idx
    ids = {cue.cue_id}
    end = idx
    j = idx + 1
    while j < len(cues) and cues[j].parent_id in ids:
        if cues[j].media_type == MediaType.GROUP:
            ids.add(cues[j].cue_id)
        end = j
        j += 1
    return end


def insert_position(cues: list[Cue], selected_row: int) -> tuple[int, int | None]:
    """Where a new cue goes when the operator adds one: (index, parent_id).

    Right after the selected cue, in the same group, so the show is built in
    order. Following cues are tied to their position ("Simultaneous" pulls the
    next row into its GO, Auto-GO starts the next row, a group owns the rows
    below it), so when the selected cue is tied to the next one the new cue
    goes after the end of that chain or group instead of silently joining it.
    No selection: at the end of the list.
    """
    n = len(cues)
    if not (0 <= selected_row < n):
        return n, None
    parent = cues[selected_row].parent_id
    i = selected_row
    while True:
        end = block_end(cues, i)
        nxt = end + 1
        tied = cues[i].follow_mode != FollowMode.MANUAL.value
        if not tied or nxt >= n:
            return end + 1, parent
        # Ties work by position: a last child tied to the row after its group
        # is tied to that row, so the chain is followed out of the group.
        parent = cues[nxt].parent_id
        i = nxt


# Where the show can continue from when the operator enters LIVE.
START_FROM_TOP = "top"
START_RESUME = "resume"
START_SELECTED = "selected"


def live_start_choices(
    n_cues: int,
    selected_row: int,
    resume_row: int | None,
    show_running: bool = False,
) -> list[tuple[str, int]]:
    """Rows the GO could start from when LIVE is entered, preferred first.

    GO fires the selected row, so a cue just fixed in the editor would open
    the show. *resume_row* is the GO target LIVE was left at (``None`` the
    first time); while something plays, the current target counts as that
    position. An empty list means there is nothing to ask: the target is the
    top of the list or the place the show was left at.
    """
    if n_cues <= 0:
        return []
    sel = selected_row if 0 <= selected_row < n_cues else 0
    resume = resume_row if resume_row is not None and 0 <= resume_row < n_cues else None
    if resume is None and show_running:
        resume = sel
    if resume is None:
        order = [(START_FROM_TOP, 0), (START_SELECTED, sel)]
    elif sel == resume:
        return []
    else:
        order = [(START_RESUME, resume), (START_SELECTED, sel), (START_FROM_TOP, 0)]
    choices: list[tuple[str, int]] = []
    for kind, row in order:
        if any(row == seen for _, seen in choices):
            continue
        choices.append((START_FROM_TOP if row == 0 else kind, row))
    return choices if len(choices) > 1 else []


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
    def promote_to_live(cues: list[Cue], cue: Cue, dual_active: bool = True,
                        exclude_ids: set[int] | frozenset[int] = frozenset()) -> None:
        """Demote the same layer/output and mark *cue* LIVE (its pre-delay has elapsed)."""
        demote_live_on_layer(
            cues, cue.layer, cue.cue_id,
            output_target=getattr(cue, "output_target", "A"),
            dual_active=dual_active,
            exclude_ids=exclude_ids,
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
        exclude_ids: set[int] | frozenset[int] = frozenset(),
    ) -> None:
        """Demote every LIVE cue on *layer* (not those on a borrowed player, *exclude_ids*).

        When *output_target* is ``"A"`` or ``"B"`` only that projector output
        is cleared; ``None`` clears the layer on both outputs.  When
        ``dual_active`` is false every cue is treated as output A.
        """
        target = None if output_target is None else resolve_output_target(
            output_target, dual_active
        )
        for cue in cues:
            if cue.layer != layer or cue.status != CueStatus.LIVE or cue.cue_id in exclude_ids:
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
    def auto_follow_target(
        cues: list[Cue], finished_cue: Cue, released_groups: set[int] | None = None
    ) -> int:
        """Return the index to fire after *finished_cue*, or -1 if none.

        The container mode wins over the single child's follow flag: a
        SEQUENCE group cascades to the next child and a LOOP group wraps back
        to the first one, because that is what the operator selected
        ("Cascata" / "Loop Scena") in the inspector. A LOOP group in
        *released_groups* (a "release loop" action reached it) plays the rest
        of its pass and then ends: no wrap, and no start of the next scene.
        """
        if getattr(finished_cue, "adlib", False):
            return -1  # an effect on demand never starts the next cue
        parent = ShowEngine.group_parent(cues, finished_cue)
        if parent is not None:
            kids = ShowEngine.children_of(cues, parent.cue_id)
            pos = next(
                (i for i, k in enumerate(kids) if k.cue_id == finished_cue.cue_id),
                -1,
            )
            mode = getattr(parent, "group_mode", "")
            if mode == GroupMode.LOOP.value and parent.cue_id in (released_groups or ()):
                if pos < 0 or pos >= len(kids) - 1:
                    return -1
                mode = GroupMode.SEQUENCE.value
            if pos >= 0 and mode == GroupMode.SEQUENCE.value and pos < len(kids) - 1:
                target = kids[pos + 1]
                return next((i for i, c in enumerate(cues) if c is target), -1)
            if pos >= 0 and mode == GroupMode.LOOP.value and kids:
                target = kids[(pos + 1) % len(kids)]
                return next((i for i, c in enumerate(cues) if c is target), -1)
        try:
            idx = cues.index(finished_cue)
        except ValueError:
            idx = next(
                (i for i, c in enumerate(cues) if c.cue_id == finished_cue.cue_id),
                -1,
            )
            if idx < 0:
                return -1
        nxt = idx + 1
        while nxt < len(cues) and getattr(cues[nxt], "adlib", False):
            nxt += 1  # effects on demand are not in the order
        return nxt if 0 <= nxt < len(cues) else -1
