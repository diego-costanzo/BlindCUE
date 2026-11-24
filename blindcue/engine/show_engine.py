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


def outside_go_order(cue: Cue) -> bool:
    """Effects on demand, relative starts, call-only and disabled cues: GO skips them.

    So does a pre-show checklist kept from an older show (the checklist was taken out
    after the teacher-workflow evaluation, 2026-11-24).
    """
    return (bool(getattr(cue, "adlib", False)) or getattr(cue, "start_rel_cue", None) is not None
            or bool(getattr(cue, "call_only", False)) or not getattr(cue, "enabled", True)
            or bool(getattr(cue, "start_clock", ""))
            or (getattr(cue, "action_spec", None) or {}).get("kind") == "checklist")


def is_enabled(cue: Cue) -> bool:
    """2.3: False for a cue switched off in this version of the show (it never plays)."""
    return bool(getattr(cue, "enabled", True))


def relative_cycle(cues: list[Cue], cue_id: int, ref_id: int | None) -> bool:
    """True when *cue_id* starting relative to *ref_id* would start itself again (a loop)."""
    by_id = {c.cue_id: c for c in cues}
    seen: set[int] = set()
    current = ref_id
    while current is not None and current not in seen:
        if current == cue_id:
            return True
        seen.add(current)
        ref = by_id.get(current)
        current = getattr(ref, "start_rel_cue", None) if ref is not None else None
    return False


def chain_indices(cues: list[Cue], start_idx: int) -> list[int]:
    """Return the contiguous run of cue indices fired by a single GO.

    A SIMULTANEOUS cue pulls in the following cue, which may pull in the next
    one, until a non-SIMULTANEOUS cue (or the end of the list) closes the chain.
    """
    if not (0 <= start_idx < len(cues)):
        return []
    if outside_go_order(cues[start_idx]):
        return [start_idx]  # an effect or a relative start never pulls show cues with it
    indices: list[int] = []
    visited: set[int] = set()
    idx = start_idx
    while 0 <= idx < len(cues) and idx not in visited:
        visited.add(idx)
        indices.append(idx)
        if cues[idx].follow_mode != FollowMode.SIMULTANEOUS.value:
            break
        idx += 1
        while idx < len(cues) and outside_go_order(cues[idx]):
            idx += 1  # effects and relative starts are not in the order
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


def _tied_to_next(cues: list[Cue], row: int, end: int) -> bool:
    """The row after the block *row*..*end* starts with it or after it without a GO of its own.

    A scene is tied by its last row ("Simultaneous" / Auto-GO work by
    position) and a Cascata that is not a playlist starts the row after it.
    """
    cue = cues[row]
    if cue.follow_mode != FollowMode.MANUAL.value:
        return True
    if cue.media_type != MediaType.GROUP or end == row:
        return False
    if getattr(cue, "group_mode", "") == GroupMode.SEQUENCE.value and not getattr(cue, "playlist", False):
        return True
    last = cues[end]
    return last.follow_mode != FollowMode.MANUAL.value and not outside_go_order(last)


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
        if not _tied_to_next(cues, i, end):
            return end + 1, parent
        while nxt < n and outside_go_order(cues[nxt]):
            nxt = block_end(cues, nxt) + 1  # a tie skips effects and relative starts too
        if nxt >= n:
            return n, parent
        # Ties work by position: a last child tied to the row after its group
        # is tied to that row, so the chain is followed out of the group.
        parent = cues[nxt].parent_id
        i = nxt


def _follows_by_itself(cues: list[Cue], cue: Cue) -> bool:
    """The end of *cue* starts the next one (Auto-GO, or a child of a Cascata / Loop Scena)."""
    if outside_go_order(cue):
        return False
    return cue.follow_mode == FollowMode.AUTO_FOLLOW.value or ShowEngine.group_mode_of(cues, cue) in (
        GroupMode.SEQUENCE.value, GroupMode.LOOP.value)


def _row_of(cues: list[Cue], cue: Cue) -> int:
    return next((i for i, c in enumerate(cues) if c is cue), -1)


def _go_on_group(cues: list[Cue], idx: int, started: set[int], depth: int = 0) -> tuple[int, list[int]]:
    """What a GO on the scene at *idx* starts: (GO pointer after it, rows whose end may start more)."""
    group = cues[idx]
    started.add(idx)
    kids = [_row_of(cues, k) for k in ShowEngine.children_of(cues, group.cue_id)]
    if not kids:
        return idx + 1, []
    mode = getattr(group, "group_mode", GroupMode.STEP.value)

    def fire(row: int) -> list[int]:
        if cues[row].media_type == MediaType.GROUP and depth < 3:
            return _go_on_group(cues, row, started, depth + 1)[1]
        started.add(row)
        return [row]

    if mode == GroupMode.SIMULTANEOUS.value:
        ends = [r for row in kids for r in fire(row)]
        return kids[-1] + 1, ends
    if mode == GroupMode.RANDOM.value:
        started.update(kids)  # one of them plays: the GO covers them all
        return kids[-1] + 1, []
    ends = fire(kids[0])
    if mode == GroupMode.SEQUENCE.value and getattr(group, "playlist", False):
        return block_end(cues, idx) + 1, ends
    if len(kids) > 1:
        return kids[1], ends
    return kids[0] + 1, ends


def _go_on_row(cues: list[Cue], idx: int, started: set[int]) -> tuple[int, int, list[int]]:
    """A GO on *idx*: (GO pointer after it, last row it fired, rows whose end may start more)."""
    if cues[idx].media_type == MediaType.GROUP:
        pointer, ends = _go_on_group(cues, idx, started)
        return pointer, idx, ends
    chain = chain_indices(cues, idx)
    ends: list[int] = []
    for row in chain:
        if cues[row].media_type == MediaType.GROUP:
            ends += _go_on_group(cues, row, started)[1]
        else:
            started.add(row)
            ends.append(row)
    last = chain[-1]
    nxt = block_end(cues, last) + 1 if getattr(cues[last], "playlist", False) else last + 1
    while nxt < len(cues) and outside_go_order(cues[nxt]):
        nxt += 1
    return nxt, last, ends


def go_stops(cues: list[Cue]) -> list[int]:
    """Rows the operator starts with GO when the show runs from the top and every cue plays to its end.

    Replays the GO pointer of the program: a "Simultaneous" chain and the
    cues an Auto-GO, a Cascata or a Loop Scena start come by themselves (a
    Cascata that is not a playlist starts the row after it too); every child
    of a "Passo a passo" scene after the first needs its own GO. Rows outside
    the GO order (effects, relative / timed starts, call only, switched off)
    are never in it. The printed list for the operator and the Q renumbering
    use this, so they agree with what GO really does.
    """
    n = len(cues)
    started: set[int] = set()
    stops: list[int] = []
    pointer = 0
    for _ in range(4 * n + 4):
        while pointer < n and (pointer in started or outside_go_order(cues[pointer])):
            pointer += 1
        if pointer >= n:
            break
        stops.append(pointer)
        pointer, _last, ends = _go_on_row(cues, pointer, started)
        queue = list(ends)
        while queue:
            row = queue.pop(0)
            if not _follows_by_itself(cues, cues[row]):
                continue
            target = ShowEngine.auto_follow_target(cues, cues[row])
            if target < 0 or target in started or outside_go_order(cues[target]):
                continue
            held = pointer
            pointer, last, more = _go_on_row(cues, target, started)
            if held > last:
                pointer = held  # an Auto-GO never pulls the GO pointer back
            queue += more
    return stops


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
        """Return the children a GROUP plays itself, in list order.

        Not those outside the GO order (switched off, effects, relative starts,
        call only): they start in their own way or never.
        """
        return [c for c in cues if c.parent_id == group_cue_id and not outside_go_order(c)]

    @staticmethod
    def next_standby_index(cues: list[Cue], last_fired_idx: int) -> int:
        """Return the standby row after the last fired cue.

        Falls back to the last fired cue when the chain reached the end of the
        show, so the selection never lands past the final row.
        """
        nxt = last_fired_idx + 1
        return nxt if nxt < len(cues) else last_fired_idx

    outside_go_order = staticmethod(outside_go_order)
    is_enabled = staticmethod(is_enabled)
    relative_cycle = staticmethod(relative_cycle)

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
        if outside_go_order(finished_cue):
            return -1  # an effect or a relative start never starts the next cue
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
            if pos >= 0 and mode == GroupMode.SEQUENCE.value and getattr(parent, "playlist", False) \
                    and pos >= len(kids) - 1:
                return -1  # 3.3: a playlist stops after its last track (the next scene waits for GO)
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
        while nxt < len(cues) and outside_go_order(cues[nxt]):
            nxt += 1  # effects and relative starts are not in the order
        return nxt if 0 <= nxt < len(cues) else -1
