"""Playback Transport (GO / Blackout / Panic) mixin for MainWindow."""

from __future__ import annotations

import time

from ui.main_window._common import *  # noqa: F403,F401,F405
from ui.main_window._common import (  # noqa: F401
    _AutosaveWorker,
    _DEFAULT_TOP_RATIOS,
    _MEDIA_ICONS,
    ShowEngine,
    chain_indices,
)


GO_GUARD_SETTINGS_KEY = "live/go_guard_ms"
GO_GUARD_DEFAULT_MS = 400


def read_go_guard_ms() -> int:
    """Double-GO guard window in ms from QSettings (0 = guard off)."""
    try:
        value = int(QSettings("BlindCue", "BlindCue").value(GO_GUARD_SETTINGS_KEY, GO_GUARD_DEFAULT_MS))
    except (TypeError, ValueError):
        value = GO_GUARD_DEFAULT_MS
    return max(0, min(value, 5000))


FADE_ALL_SETTINGS_KEY = "live/fade_all_sec"
FADE_ALL_DEFAULT_SEC = 1.0


def read_fade_all_sec() -> float:
    """Fade All duration in seconds from QSettings (0.1–10 s)."""
    try:
        value = float(QSettings("BlindCue", "BlindCue").value(FADE_ALL_SETTINGS_KEY, FADE_ALL_DEFAULT_SEC))
    except (TypeError, ValueError):
        value = FADE_ALL_DEFAULT_SEC
    return max(0.1, min(value, 10.0))


class _TransportMixin:
    def _exclusive_blocker(self) -> Cue | None:
        """The live cue marked exclusive that refuses a manual GO, if any."""
        return next(
            (c for c in self._cues if getattr(c, "exclusive", False) and c.status == CueStatus.LIVE),
            None,
        )

    def _manual_go_allowed(self) -> bool:
        """Gate shared by every manual GO: exclusive cue first, then the double-GO guard.

        A forced GO (Ctrl+Space) skips the exclusive check only.
        """
        forced = bool(getattr(self, "_go_force_once", False))
        self._go_force_once = False
        if not forced:
            blocker = self._exclusive_blocker()
            if blocker is not None:
                self._status_label.setText(
                    f"GO bloccato: '{blocker.name}' è esclusiva ed è in onda — Ctrl+Spazio per forzare"
                )
                logger.info("[GO] Refused: exclusive cue #%d is live", blocker.cue_id)
                return False
        return self._go_guard_allows()

    @Slot()
    def _on_go_forced(self) -> None:
        """Ctrl+Space: GO even while an exclusive cue is live."""
        if self._is_text_input_focused():
            return
        self._go_force_once = True
        try:
            self._on_go()
        finally:
            self._go_force_once = False

    def _go_guard_allows(self) -> bool:
        """Swallow a second GO that arrives within the guard window.

        A double press of Space, a bouncing remote button or a double-click
        would otherwise fire two cues in a row. The window is measured from
        the last GO that was accepted; ``live/go_guard_ms`` = 0 disables it.
        """
        guard_ms = getattr(self, "_go_guard_ms", None)
        if guard_ms is None:
            guard_ms = self._go_guard_ms = read_go_guard_ms()
        now = time.monotonic()
        last = getattr(self, "_last_go_at", None)
        if guard_ms > 0 and last is not None and (now - last) * 1000.0 < guard_ms:
            self._status_label.setText(f"GO ignorato: secondo GO entro {guard_ms} ms")
            logger.info("[GO] Ignored second GO within %d ms", guard_ms)
            return False
        self._last_go_at = now
        return True

    @Slot()
    def _on_go_shortcut(self) -> None:
        """Keyboard Space trigger: suppressed while typing in text/spin/combo inputs."""
        if self._is_text_input_focused():
            return
        self._on_go()

    @Slot()
    def _on_go(self) -> None:
        """Direct GO trigger (GO buttons, double-click, programmatic calls): always fires."""
        if not self._cues:
            self._status_label.setText("Scaletta vuota — Aggiungi prima dei file multimediali")
            return
        if not self._manual_go_allowed():
            return

        if hasattr(self, "_earcon_mgr"):
            self._earcon_mgr.play_go()

        self._apply_inspector_to_cue()

        target_idx = self._go_target_index()
        self._remember_manual_go(target_idx)
        self._fire_cue_chain(target_idx)

    def _note_fired(self, cue: Cue) -> None:
        """A cue was started (GO, Auto-GO, chain, group): ✓ in the list, and in which order."""
        self._played_ids.add(cue.cue_id)
        self._fire_seq += 1
        self._fired_at[cue.cue_id] = self._fire_seq
        if cue.parent_id in self._released_groups:
            # A released Loop Scena never comes back to its first child by
            # itself: starting that child again starts the loop again.
            kids = ShowEngine.children_of(self._cues, cue.parent_id)
            if kids and kids[0] is cue:
                self._released_groups.discard(cue.parent_id)

    def _go_target_index(self) -> int:
        """Row the next GO fires: the selected one, else the last fired, else the top."""
        row, _ = self._anchor_row_and_cue()
        if 0 <= row < len(self._cues):
            return row
        if 0 <= self._current_index < len(self._cues):
            return self._current_index
        return 0

    def _remember_manual_go(self, idx: int) -> None:
        """Note the cue an operator started by hand (GO, remote, forced start).

        After a stop the next GO points back at it, so a GO given too early
        can simply be repeated at the right moment. A hand-given GO also
        moves past the operator note on screen (an Auto-GO does not).
        """
        if 0 <= idx < len(self._cues):
            self._last_manual_go_cue = self._cues[idx]
        self._dismiss_note_on_go()

    def _fire_cue_chain(self, start_idx: int, auto: bool = False) -> None:
        """Fire cue at *start_idx*, advancing immediately across any SIMULTANEOUS chain or Group execution.

        *auto*: started by an Auto-GO, not by the operator. Then the GO
        pointer only moves forward: if the operator already set it past this
        cue (e.g. to the cue after a released Loop Scena), it stays there.
        """
        if not (0 <= start_idx < len(self._cues)):
            return
        held_row = self._go_target_index() if auto else -1

        start_cue = self._cues[start_idx]

        # Auto-expand if cue belongs to a collapsed group
        if start_cue.parent_id is not None:
            parent_cue = next((c for c in self._cues if c.cue_id == start_cue.parent_id), None)
            if parent_cue and parent_cue.collapsed:
                p_row = self._cues.index(parent_cue)
                self._toggle_group_collapsed(p_row)

        if start_cue.media_type == MediaType.GROUP:
            self._fire_group_cue(start_idx, start_cue)
            return

        chain = chain_indices(self._cues, start_idx)
        last_fired_idx = chain[-1]
        self._live_show_panel.notify_first_go()
        for c_idx in chain:
            cue = self._cues[c_idx]
            self._note_fired(cue)
            if cue.media_type == MediaType.GROUP:
                self._fire_group_child(cue, depth=0)
                self._current_index = c_idx
                logger.info("[GO] Fired chained group #%d: %s", cue.cue_id, cue)
                continue
            # An action cue takes no layer: it must not demote what plays there.
            if cue.pre_delay <= 0.02 and cue.media_type != MediaType.ACTION:
                ShowEngine.promote_to_live(self._cues, cue, dual_active=self._dual_output_active)
                self._update_live_layer_label(cue)
            self._current_index = c_idx
            self.cue_fired.emit(cue)
            logger.info("[GO] Fired cue #%d: %s", cue.cue_id, cue)

        self._refresh_cue_list(keep_selection=False)

        first_cue = self._cues[start_idx]
        ref = format_cue_ref(start_idx, first_cue)
        next_idx = last_fired_idx + 1
        fired_cue = self._cues[last_fired_idx]
        if (ShowEngine.group_mode_of(self._cues, fired_cue) == GroupMode.LOOP.value
                and fired_cue.parent_id not in self._released_groups):
            # Loop Scena: the standby returns to the first element instead of
            # falling past the container once the last child has fired
            # (not after a release: then the scene ends and the show goes on).
            kids = ShowEngine.children_of(self._cues, fired_cue.parent_id)
            inside = next_idx < len(self._cues) and any(
                kid is self._cues[next_idx] for kid in kids)
            if kids and not inside:
                next_idx = next(
                    (i for i, c in enumerate(self._cues) if c is kids[0]), next_idx)
        if held_row > last_fired_idx and held_row < len(self._cues):
            next_idx = held_row  # an Auto-GO never pulls the GO pointer back
        # An action cue has already written what it did on the status line.
        is_action = first_cue.media_type == MediaType.ACTION
        if next_idx < len(self._cues):
            self._cue_list.setCurrentRow(next_idx)
            next_ref = format_cue_ref(next_idx, self._cues[next_idx])
            if not is_action:
                self._status_label.setText(
                    f"LIVE → {ref} '{first_cue.name}' (Layer {first_cue.layer}) | Standby: {next_ref} '{self._cues[next_idx].name}'"
                )
        else:
            self._cue_list.setCurrentRow(last_fired_idx)
            if not is_action:
                self._status_label.setText(
                    f"LIVE → {ref} '{first_cue.name}' (Layer {first_cue.layer}) — Fine scaletta (premi GO per rilanciare)"
                )
        if not self._live_mode and self._live_resume_id is not None:
            # The show moved on while the editor is open: LIVE resumes from here.
            row = next_idx if next_idx < len(self._cues) else last_fired_idx
            self._live_resume_id = self._cues[row].cue_id

        self._sync_live_view()
        self._auto_save()

    def _fire_group_cue(self, group_idx: int, group_cue: Cue, depth: int = 0) -> None:
        """Execute a MediaType.GROUP container cue according to its group_mode."""
        children = ShowEngine.children_of(self._cues, group_cue.cue_id)
        # The container is "executed" even when empty: keeping it LOADED made
        # the operator think the GO was swallowed.
        group_cue.status = CueStatus.LIVE
        self._note_fired(group_cue)
        self._released_groups.discard(group_cue.cue_id)  # a new run loops again
        if not children:
            self._refresh_cue_list(keep_selection=False)
            next_idx = group_idx + 1
            if next_idx < len(self._cues):
                self._cue_list.setCurrentRow(next_idx)
            self._sync_live_view()
            self._auto_save()
            return

        self._live_show_panel.notify_first_go()
        mode = getattr(group_cue, "group_mode", GroupMode.STEP.value)

        if group_cue.collapsed:
            self._toggle_group_collapsed(group_idx)

        if mode == GroupMode.SIMULTANEOUS.value:
            for child in children:
                self._fire_group_child(child, depth)

            self._refresh_cue_list(keep_selection=False)
            last_child_idx = self._cues.index(children[-1])
            self._cue_list.setCurrentRow(
                ShowEngine.next_standby_index(self._cues, last_child_idx)
            )

        elif mode == GroupMode.RANDOM.value:
            import random
            pool = children
            if len(children) > 1:
                # The inspector promises "senza ripetere due volte di fila lo
                # stesso elemento": draw from the other children only.
                last_id = getattr(group_cue, "_last_random_child_id", None)
                fresh = [c for c in children if c.cue_id != last_id]
                if fresh:
                    pool = fresh
            chosen = random.choice(pool)  # noqa: S311  # Non-cryptographic cue shuffle
            group_cue._last_random_child_id = chosen.cue_id
            self._fire_group_child(chosen, depth)
            logger.info("[GO-GROUP-RANDOM] Fired random child #%d '%s'", chosen.cue_id, chosen.name)
            self._refresh_cue_list(keep_selection=False)
            last_child_idx = self._cues.index(children[-1])
            next_idx = last_child_idx + 1
            if next_idx < len(self._cues):
                self._cue_list.setCurrentRow(next_idx)

        elif mode == GroupMode.SEQUENCE.value:
            first_child = children[0]
            self._fire_group_child(first_child, depth)
            logger.info("[GO-GROUP-SEQ] Fired child 0 #%d '%s'", first_child.cue_id, first_child.name)
            self._refresh_cue_list(keep_selection=False)
            if len(children) > 1:
                self._cue_list.setCurrentRow(self._cues.index(children[1]))
            else:
                next_idx = self._cues.index(first_child) + 1
                if next_idx < len(self._cues):
                    self._cue_list.setCurrentRow(next_idx)

        else:  # STEP or LOOP
            first_child = children[0]
            self._fire_group_child(first_child, depth)
            logger.info("[GO-GROUP-STEP] Fired child 0 #%d '%s'", first_child.cue_id, first_child.name)
            self._refresh_cue_list(keep_selection=False)
            if len(children) > 1:
                self._cue_list.setCurrentRow(self._cues.index(children[1]))
            elif mode == GroupMode.LOOP.value:
                self._cue_list.setCurrentRow(self._cues.index(first_child))
            else:
                next_idx = self._cues.index(first_child) + 1
                if next_idx < len(self._cues):
                    self._cue_list.setCurrentRow(next_idx)

        self._sync_live_view()
        self._auto_save()

    def _fire_group_child(self, child: Cue, depth: int) -> None:
        """Launch one group child; a nested container expands recursively.

        Without this, a group holding another group emitted ``cue_fired`` for
        the container, ``main.py`` had no media branch for it, and the inner
        media silently never played.
        """
        if child.media_type == MediaType.GROUP:
            if depth >= 3:
                logger.warning("[GO-GROUP] Annidamento troppo profondo su '%s'", child.name)
                return
            self._fire_group_cue(self._cues.index(child), child, depth + 1)
            return
        if child.pre_delay <= 0.02 and child.media_type != MediaType.ACTION:
            ShowEngine.promote_to_live(self._cues, child, dual_active=self._dual_output_active)
            self._update_live_layer_label(child)
        self._note_fired(child)
        self.cue_fired.emit(child)

    @Slot()
    def _on_blackout(self) -> None:
        if hasattr(self, "_earcon_mgr"):
            self._earcon_mgr.play_stop()
        self._live_phase_tags.clear()
        self._output.show_fallback()
        if getattr(self, "_output_b", None) is not None:
            self._output_b.show_fallback()
        ShowEngine.demote_all_live(self._cues)
        self._refresh_cue_list()
        for sp in self._for_each_status_panel():
            sp.reset_all_layers()
        self.set_global_paused(False, silent=True)
        self.blackout_requested.emit()
        self._sync_live_view()
        self._status_label.setText("BLACKOUT — Output ripristinato a Layer 0 (Tappo)")
        logger.info("[BLACKOUT] Activated")

    def _stopped_manual_go_index(self) -> int | None:
        """Row of the last hand-started cue if it is still running or waiting.

        Called before a stop. Only the cue the operator started counts:
        background music started earlier in the act must not take the next
        GO, and a cue already in its Post-Delay has finished playing.
        """
        cue = getattr(self, "_last_manual_go_cue", None)
        if cue is None:
            return None
        idx = next((i for i, c in enumerate(self._cues) if c is cue), None)
        if idx is None:
            return None
        tags = getattr(self, "_live_phase_tags", {}) or {}

        def running(c: Cue) -> bool:
            return c.status == CueStatus.LIVE or str(tags.get(c.cue_id, "")).startswith("PRE")

        if cue.media_type == MediaType.GROUP:
            kids = ShowEngine.children_of(self._cues, cue.cue_id)
            return idx if any(running(k) for k in kids) else None
        return idx if running(cue) else None

    def _standby_on_first_stopped(self, first_stopped: int | None) -> None:
        """After a stop, put the next GO back on the hand-started cue that was stopped."""
        if first_stopped is not None and 0 <= first_stopped < len(self._cues):
            self._current_index = first_stopped
            self._cue_list.setCurrentRow(first_stopped)

    @Slot()
    def _on_fade_all(self) -> None:
        """Fade All: every layer fades out together (Shift+Esc), a softer PANIC."""
        seconds = read_fade_all_sec()
        first_stopped = self._stopped_manual_go_index()
        if hasattr(self, "_earcon_mgr"):
            self._earcon_mgr.play_stop()
        self._live_phase_tags.clear()
        ShowEngine.demote_all_live(self._cues)
        self._refresh_cue_list()
        for sp in self._for_each_status_panel():
            sp.reset_all_layers()
        self.set_global_paused(False, silent=True)
        self.fade_all_requested.emit(seconds)
        self._standby_on_first_stopped(first_stopped)
        self._sync_live_view()
        self._status_label.setText(f"Dissolvenza totale in {seconds:.1f} s")
        logger.info("[FADE ALL] %.2fs", seconds)

    @Slot()
    def _on_panic(self) -> None:
        """Immediate 0ms PANIC hard cut across every active player, delay timer, and output layer."""
        first_stopped = self._stopped_manual_go_index()
        self._live_phase_tags.clear()
        ShowEngine.demote_all_live(self._cues)
        self._refresh_cue_list()
        for sp in self._for_each_status_panel():
            sp.reset_all_layers()
        self.set_global_paused(False, silent=True)
        self.panic_requested.emit()
        self._output.panic_blackout()
        if getattr(self, "_output_b", None) is not None:
            self._output_b.panic_blackout()
        self._standby_on_first_stopped(first_stopped)
        self._sync_live_view()
        self._status_label.setText("🚨 PANIC (0ms) — STOP TOTALE ESEGUITO")
        logger.warning("[PANIC] Executed hard stop all layers")
