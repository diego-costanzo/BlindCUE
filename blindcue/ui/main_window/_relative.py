"""Cues that start relative to another cue (stage 2, item 2.1) mixin for MainWindow.

A cue may start by itself N s after another cue starts, after it ends, or
N s before it ends. Such a cue is outside the GO order (like an effect on
demand). main.py reports the real start of every cue (after its Pre-Delay)
with the time it still plays, its natural end, and a length that became
known only after the start; this mixin fires the cues that wait for those
moments. The wait itself runs in the show's scheduler as an extra Pre-Delay
(``take_rel_extra``), so Pause All holds it and PANIC / Fade All cancel it.
"""

from __future__ import annotations

import time
from collections import deque

from i18n import tr

from ui.main_window._common import *  # noqa: F403,F401,F405

_MAX_PER_SECOND = 20  # relative starts per second before the chain is cut off (a loop)


class _RelativeMixin:
    def _relative_setup(self) -> None:
        self._rel_extra: dict[int, float] = {}          # cue_id -> extra wait for main.py
        self._rel_until_known: dict[int, list[int]] = {}  # ref -> "before end" cues, length unknown yet
        self._rel_before_end: dict[int, int] = {}       # "before end" cue waiting -> its reference
        self._rel_marker: dict[int, int] = {}           # 2.7: "on a marker" cue waiting -> its reference
        self._rel_held: set[int] = set()                 # waiting cues held while their reference is paused
        self._rel_fired: deque[float] = deque(maxlen=_MAX_PER_SECOND)
        self._goto_counts: dict[int, int] = {}            # 2.2: jump action -> times it jumped this run

    def _rel_refresh_choices(self) -> None:
        """Inspector: the cues a relative start can follow, and the loop check."""
        inspector = getattr(self, "_inspector", None)
        if inspector is None or not hasattr(inspector, "set_cue_choices"):
            return
        inspector.relative_cycle_check = lambda cue_id, ref_id: ShowEngine.relative_cycle(self._cues, cue_id, ref_id)
        media = {c.cue_id for c in self._cues if c.media_type.has_file}
        lost = [i for i, c in enumerate(self._cues)
                if getattr(c, "start_rel_cue", None) is not None and c.start_rel_cue not in media]
        for i in lost:
            self._cues[i].start_rel_cue = None  # its reference is gone: it waits for GO again
        if lost:
            self._status_label.setText(tr("Partenza relativa persa (cue di riferimento eliminata): {} ora parte con il GO")
                                       .format(", ".join(f"#{i + 1}" for i in lost)))
        inspector.set_cue_choices([(c.cue_id, f"{format_cue_ref(i, c)} {c.name}") for i, c in enumerate(self._cues)
                                   if c.media_type.has_file])

    def take_rel_extra(self, cue_id: int) -> float:
        """main.py: the extra wait of this start (0 for any other start)."""
        return float(self._rel_extra.pop(cue_id, 0.0))

    def _rel_reset(self) -> None:
        """PANIC, Fade All, another show: nothing waits for a reference any more."""
        self._rel_extra.clear()
        self._rel_until_known.clear()
        self._rel_before_end.clear()
        self._rel_marker.clear()
        self._rel_held.clear()

    def _rel_dependents(self, ref_id: int, whens: tuple[str, ...]) -> list[tuple[int, Cue]]:
        return [(i, c) for i, c in enumerate(self._cues)
                if getattr(c, "start_rel_cue", None) == ref_id and getattr(c, "start_rel_when", "start") in whens
                and getattr(c, "enabled", True) and not getattr(c, "start_clock", "")]  # a time of day wins

    # ── events from main.py ──
    def _marker_wait(self, ref: Cue, dep: Cue, pos: float | None, remaining: float | None = None) -> float | None:
        """Seconds from *pos* until *dep*'s marker in *ref* (+ its offset).

        None when the marker is passed, missing, after the end (*remaining* s from *pos*), or *ref* has
        sections (repeated / skipped parts: file time is not the time it plays).
        """
        marker = next((m for m in getattr(ref, "markers", []) if m["id"] == dep.start_rel_marker), None)
        if marker is None or pos is None or marker["sec"] < pos - 0.05 or getattr(ref, "sections", None):
            return None
        rate = max(0.5, float(getattr(ref, "playback_rate", 1.0)))  # 3.7: file seconds -> real seconds
        if remaining is not None and (marker["sec"] - pos) / rate > remaining + 0.05:
            return None  # behind the OUT point: never reached
        return max(0.0, marker["sec"] - pos) / rate + float(getattr(dep, "start_rel_offset", 0.0))

    def cue_launched(self, cue: Cue, remaining: float | None, start_pos: float | None = None) -> None:
        """*cue* really started at *start_pos* s of its file; it plays *remaining* more seconds."""
        markers = self._rel_dependents(cue.cue_id, ("marker",))
        if markers and getattr(cue, "sections", None):
            self._status_label.setText(tr("'{}' ha sezioni: le cue che partono sui suoi segni non partono")
                                       .format(cue.name))
        for idx, dep in markers:
            wait = self._marker_wait(cue, dep, start_pos, remaining)
            if wait is not None:
                self._rel_marker[dep.cue_id] = cue.cue_id
                self._rel_fire(idx, dep, wait)
        for idx, dep in self._rel_dependents(cue.cue_id, ("start", "before_end")):
            offset = float(getattr(dep, "start_rel_offset", 0.0))
            if dep.start_rel_when == "start":
                self._rel_fire(idx, dep, offset)
            elif remaining is not None:
                self._rel_before_end[dep.cue_id] = cue.cue_id
                self._rel_fire(idx, dep, max(0.0, remaining - offset))
            else:
                self._rel_until_known.setdefault(cue.cue_id, []).append(dep.cue_id)

    def cue_duration_known(self, cue: Cue, remaining: float | None) -> None:
        """The length of a playing *cue* became known: its "before the end" cues can be timed now."""
        waiting = self._rel_until_known.pop(cue.cue_id, [])
        if remaining is None:
            if waiting:
                self._rel_until_known[cue.cue_id] = waiting  # looping forever: they start at its end
            return
        for dep_id in waiting:
            idx = next((i for i, c in enumerate(self._cues) if c.cue_id == dep_id), -1)
            if idx >= 0:
                dep = self._cues[idx]
                self._rel_before_end[dep_id] = cue.cue_id
                self._rel_fire(idx, dep, max(0.0, remaining - float(dep.start_rel_offset)))

    def cue_ended(self, cue: Cue) -> None:
        """*cue* ended by itself (not stopped by hand): its "after the end" cues start."""
        late = set(self._rel_until_known.pop(cue.cue_id, []))
        for dep_id, ref in list(self._rel_before_end.items()):
            if ref == cue.cue_id:
                self._rel_before_end.pop(dep_id, None)
        for idx, dep in self._rel_dependents(cue.cue_id, ("end", "before_end")):
            if dep.start_rel_when == "end":
                self._rel_fire(idx, dep, float(getattr(dep, "start_rel_offset", 0.0)))
            elif dep.cue_id in late:  # its length was never known: it starts at the end
                logger.info("[RELATIVE] '%s': length of '%s' unknown, started at its end", dep.name, cue.name)
                self._rel_fire(idx, dep, 0.0)

    def _rel_cancel_waiting(self, dep: Cue) -> bool:
        """Cancel *dep*'s start if it still waits (an action on its own slot, media on its layer)."""
        if dep.cue_id not in self._live_phase_tags:
            return False
        if dep.media_type == MediaType.ACTION:
            self.action_cancel_requested.emit(dep.cue_id)
        else:
            self.layer_cancel_start_requested.emit(self._runtime_slot(dep))
        return True

    def _rel_stopped_by_hand(self, cue_ids: list[int]) -> None:
        """Cues stopped by the operator: what waited to start before their end does not start."""
        gone = set(cue_ids)
        for waiting in (self._rel_before_end, self._rel_marker):
            for dep_id, ref in list(waiting.items()):
                if ref in gone:
                    waiting.pop(dep_id, None)
                    self._rel_held.discard(dep_id)
                    dep = next((c for c in self._cues if c.cue_id == dep_id), None)
                    if dep is not None:
                        self._rel_cancel_waiting(dep)
        for ref in gone:
            self._rel_until_known.pop(ref, None)

    def rel_cancel_dependents(self, cue_ids: list[int]) -> None:
        """Undo GO took these cues back: nothing waiting to start relative to them starts."""
        gone = set(cue_ids)
        for dep in self._cues:
            if getattr(dep, "start_rel_cue", None) in gone:
                self._rel_cancel_waiting(dep)
                self._rel_before_end.pop(dep.cue_id, None)
                self._rel_marker.pop(dep.cue_id, None)
                self._rel_held.discard(dep.cue_id)
        for ref in gone:
            self._rel_until_known.pop(ref, None)

    def cue_retimed(self, cue: Cue, remaining: float | None, pos: float | None = None) -> None:
        """A playing *cue* was moved (seek): its "before the end" and marker cues are timed again."""
        for dep_id, ref in list(self._rel_marker.items()):
            if ref != cue.cue_id:
                continue
            idx = next((i for i, c in enumerate(self._cues) if c.cue_id == dep_id), -1)
            held = dep_id in self._rel_held
            self._rel_held.discard(dep_id)
            if idx < 0 or not (held or self._rel_cancel_waiting(self._cues[idx])):
                continue
            self._rel_marker.pop(dep_id, None)
            wait = self._marker_wait(cue, self._cues[idx], pos, remaining)
            if wait is not None:  # moved past the marker: it does not start
                self._rel_marker[dep_id] = cue.cue_id
                self._rel_fire(idx, self._cues[idx], wait)
        for dep_id, ref in list(self._rel_before_end.items()):
            if ref != cue.cue_id:
                continue
            idx = next((i for i, c in enumerate(self._cues) if c.cue_id == dep_id), -1)
            held = dep_id in self._rel_held
            self._rel_held.discard(dep_id)
            if idx < 0 or not (held or self._rel_cancel_waiting(self._cues[idx])):
                continue  # already started: nothing to move
            dep = self._cues[idx]
            self._rel_before_end.pop(dep_id, None)
            if remaining is None:
                self._rel_until_known.setdefault(cue.cue_id, []).append(dep_id)
            else:
                self._rel_before_end[dep_id] = cue.cue_id
                self._rel_fire(idx, dep, max(0.0, remaining - float(dep.start_rel_offset)))

    def cue_paused(self, cue: Cue) -> None:
        """*cue* was paused (its card, a pause action): what waits for its marker or its end is held."""
        for waiting in (self._rel_marker, self._rel_before_end):
            for dep_id, ref in list(waiting.items()):
                dep = next((c for c in self._cues if c.cue_id == dep_id), None)
                if ref == cue.cue_id and dep is not None and self._rel_cancel_waiting(dep):
                    self._rel_held.add(dep_id)

    def cue_resumed(self, cue: Cue, remaining: float | None, pos: float | None) -> None:
        """*cue* plays on from *pos*: the held cues are timed again from there."""
        self.cue_retimed(cue, remaining, pos)

    def rel_reference_gone(self, cue_ids: list[int]) -> None:
        """main.py: these cues were pushed off their layer by another cue (no marker, no end comes)."""
        self._rel_stopped_by_hand(cue_ids)

    # ── starting ──
    def _loop_guard(self, name: str) -> bool:
        """False after 20 automatic starts within a second: cues start each other in a loop."""
        now = time.monotonic()
        while self._rel_fired and now - self._rel_fired[0] > 1.0:
            self._rel_fired.popleft()
        if len(self._rel_fired) >= _MAX_PER_SECOND:
            self._status_label.setText(tr("Partenze relative fermate: le cue si avviano a vicenda in un ciclo"))
            logger.warning("[RELATIVE] more than %d starts in a second: '%s' not started", _MAX_PER_SECOND, name)
            return False
        self._rel_fired.append(now)
        return True

    def action_jump(self, action: Cue) -> None:
        """2.2: a jump or call action reached its moment (main.py)."""
        spec = action.action_spec
        ids = list(spec.get("cue_ids") or [])
        target_row = next((i for i, c in enumerate(self._cues) if ids and c.cue_id == ids[0]), -1)
        if target_row < 0:
            self._status_label.setText(tr("Salto o chiamata senza una cue valida: '{}'").format(action.name))
            return
        kind = spec.get("kind")
        if kind == "goto":
            limit = int(spec.get("goto_max", 0) or 0)
            done = self._goto_counts.get(action.cue_id, 0)
            if limit and done >= limit:
                self._status_label.setText(tr("Salto '{}' già fatto {} volte: il GO prosegue").format(action.name, done))
                return
            self._goto_counts[action.cue_id] = done + 1
        target_id, play = ids[0], bool(spec.get("goto_play", True))
        # After the GO that started the action has finished moving the pointer.
        QTimer.singleShot(0, lambda: self._do_jump(target_id, kind, play))

    def _do_jump(self, target_id: int, kind: str, play: bool) -> None:
        idx = next((i for i, c in enumerate(self._cues) if c.cue_id == target_id), -1)
        if idx < 0 or not self._loop_guard(self._cues[idx].name if idx >= 0 else "?"):
            return
        ref = f"{format_cue_ref(idx, self._cues[idx])} '{self._cues[idx].name}'"
        if kind == "call":
            self._fire_cue_chain(idx, auto=True, keep_pointer=True)
            self._status_label.setText(tr("Chiamata: {}").format(ref))
        elif play:
            self._cue_list.setCurrentRow(idx)  # a jump back: GO goes on from the target, not after the jump
            self._fire_cue_chain(idx, auto=True)
            self._status_label.setText(tr("Salto: {}").format(ref))
        else:
            self._cue_list.setCurrentRow(idx)
            self._sync_live_view()
            self._status_label.setText(tr("Prossimo GO: {}").format(ref))

    def _rel_fire(self, idx: int, dep: Cue, extra: float) -> None:
        if not self._loop_guard(dep.name):
            return
        self._rel_extra[dep.cue_id] = max(0.0, extra)
        try:
            self._fire_cue_chain(idx, auto=True, keep_pointer=True)
        finally:
            self._rel_extra.pop(dep.cue_id, None)
        logger.info("[RELATIVE] '%s' starts in %.2fs", dep.name, extra)
