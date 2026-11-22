"""Playback Transport (GO / Blackout / Panic) mixin for MainWindow."""

from __future__ import annotations

from ui.main_window._common import *  # noqa: F403,F401,F405
from ui.main_window._common import (  # noqa: F401
    _AutosaveWorker,
    _DEFAULT_TOP_RATIOS,
    _MEDIA_ICONS,
    ShowEngine,
    chain_indices,
)


class _TransportMixin:
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

        if hasattr(self, "_earcon_mgr"):
            self._earcon_mgr.play_go()

        self._apply_inspector_to_cue()

        row, _ = self._anchor_row_and_cue()
        if 0 <= row < len(self._cues):
            target_idx = row
        elif 0 <= self._current_index < len(self._cues):
            target_idx = self._current_index
        else:
            target_idx = 0

        self._fire_cue_chain(target_idx)

    def _fire_cue_chain(self, start_idx: int) -> None:
        """Fire cue at *start_idx*, advancing immediately across any SIMULTANEOUS chain or Group execution."""
        if not (0 <= start_idx < len(self._cues)):
            return

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
            if cue.media_type == MediaType.GROUP:
                self._fire_group_child(cue, depth=0)
                self._current_index = c_idx
                logger.info("[GO] Fired chained group #%d: %s", cue.cue_id, cue)
                continue
            if cue.pre_delay <= 0.02:
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
        if ShowEngine.group_mode_of(self._cues, fired_cue) == GroupMode.LOOP.value:
            # Loop Scena: the standby returns to the first element instead of
            # falling past the container once the last child has fired.
            kids = ShowEngine.children_of(self._cues, fired_cue.parent_id)
            inside = next_idx < len(self._cues) and any(
                kid is self._cues[next_idx] for kid in kids)
            if kids and not inside:
                next_idx = next(
                    (i for i, c in enumerate(self._cues) if c is kids[0]), next_idx)
        if next_idx < len(self._cues):
            self._cue_list.setCurrentRow(next_idx)
            next_ref = format_cue_ref(next_idx, self._cues[next_idx])
            self._status_label.setText(
                f"LIVE → {ref} '{first_cue.name}' (Layer {first_cue.layer}) | Standby: {next_ref} '{self._cues[next_idx].name}'"
            )
        else:
            self._cue_list.setCurrentRow(last_fired_idx)
            self._status_label.setText(
                f"LIVE → {ref} '{first_cue.name}' (Layer {first_cue.layer}) — Fine scaletta (premi GO per rilanciare)"
            )

        self._sync_live_view()
        self._auto_save()

    def _fire_group_cue(self, group_idx: int, group_cue: Cue, depth: int = 0) -> None:
        """Execute a MediaType.GROUP container cue according to its group_mode."""
        children = ShowEngine.children_of(self._cues, group_cue.cue_id)
        # The container is "executed" even when empty: keeping it LOADED made
        # the operator think the GO was swallowed.
        group_cue.status = CueStatus.LIVE
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
        if child.pre_delay <= 0.02:
            ShowEngine.promote_to_live(self._cues, child, dual_active=self._dual_output_active)
            self._update_live_layer_label(child)
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

    @Slot()
    def _on_panic(self) -> None:
        """Immediate 0ms PANIC hard cut across every active player, delay timer, and output layer."""
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
        self._sync_live_view()
        self._status_label.setText("🚨 PANIC (0ms) — STOP TOTALE ESEGUITO")
        logger.warning("[PANIC] Executed hard stop all layers")
