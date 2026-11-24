"""Rehearsal (stage 1 C2a step 9) mixin for MainWindow.

The rehearsal runs on the show's screen: the same list, GO, cards. It adds a
drawer for small fixes of one cue, opened by "✎" next to a named cue, and
keeps the list of changes made during the rehearsal (field, before, now, with
"Undo" for each). Preparation ↔ Rehearsal is one click (Shift+F5 enters);
Rehearsal → Show goes through the readiness page; Show → Rehearsal is a
1.5 s hold, like every way out of the show.
"""

from __future__ import annotations

from i18n import tr
from PySide6.QtWidgets import QHBoxLayout

from ui.main_window._common import *  # noqa: F403,F401,F405
from ui.rehearsal_drawer import FIELDS

_FIELD_WORDS = {
    "name": "nome", "notes": "note", "volume": "livello", "fade_in": "entrata", "fade_out": "sfumatura",
    "in_point": "inizio", "out_point": "fine", "follow_mode": "poi", "markers": "segni",
}


def _shown(field: str, value: object) -> str:
    if field == "volume":
        return f"{round(float(value) * 100)} %"
    if field in ("fade_in", "fade_out", "in_point"):
        return f"{float(value):.1f} s"
    if field == "markers":
        return f"{len(value)} ◆"
    if field == "out_point":
        return tr("fine") if not value else f"{float(value):.1f} s"
    return str(value)


class _RehearsalMixin:
    # ── Setup ─────────────────────────────────────────────────────────
    def _rehearsal_setup(self) -> None:
        """Wire the drawer, the "✎" buttons and the rehearsal tools of the cards."""
        self._editing_cue_id = -1
        panel = self._live_show_panel
        drawer = panel.now_playing.drawer
        drawer.field_changed.connect(self._on_drawer_field)
        drawer.closed.connect(self._close_drawer)
        drawer.review_requested.connect(self._review_rehearsal_changes)
        drawer.more_requested.connect(self._drawer_more_settings)
        drawer.done_editing.connect(lambda: self._live_show_panel.live_table.setFocus())
        panel.edit_cue_requested.connect(self._open_drawer)
        panel.now_playing.edit_requested.connect(self._open_drawer)
        panel.now_playing.stop_requested.connect(self._on_card_stop)
        panel.now_playing.to_end_requested.connect(self._on_card_to_end)
        panel.now_playing.save_level_requested.connect(self._on_card_save_level)
        for tabs in (self._mode_tabs, panel.mode_tabs):
            tabs.rehearsal_requested.connect(self._enter_rehearsal)
            tabs.preparation_requested.connect(lambda: self.set_live_mode(False))
            for hold in (tabs.tab_prep_hold, tabs.tab_reh_hold):
                hold.released_early.connect(self._hold_longer)

    def _hold_longer(self) -> None:
        """A tab of the show let go too early: say so instead of nothing happening (W29)."""
        self._status_label.setText(tr("Tieni premuto più a lungo (1,5 s) per uscire dallo spettacolo"))
        self.announce(self._status_label.text(), assertive=True)

    # ── Modes ─────────────────────────────────────────────────────────
    def _enter_rehearsal_from_key(self) -> None:
        """Shift+F5: into the rehearsal from Preparation; in the show only says how to leave (M4)."""
        if self._current_mode() == "show":
            self._explain_how_to_leave()
            return
        self._enter_rehearsal()

    def _apply_mode_visuals(self) -> None:
        mode = self._current_mode()
        before = getattr(self, "_mode_shown", "preparation")
        self._mode_shown = mode
        if mode != before:
            self._undo_go_end()  # a change of mode ends the Undo GO offer (L7)
            self._layer0_follow_mode()  # the test pattern only in Preparation (#9)
            dlg = getattr(self, "_rehearsal_review", None)
            if dlg is not None and mode == "show":
                dlg.close()
        if hasattr(self, "_earcon_mgr") and mode != before:
            # Into the show three notes up, out of it three down (W41).
            if mode == "show":
                self._earcon_mgr.play_enter_show()
            elif before == "show":
                self._earcon_mgr.play_exit_show()
        self._effects_activate(mode != "preparation")
        self._mode_tabs.set_mode(mode)
        if hasattr(self, "_variant"):
            self._update_variant_status_bar()  # Rehearsal / Show: only the switches that are on
        self._live_show_panel.mode_tabs.set_mode(mode)
        self._live_show_panel.set_rehearsal(self._live_mode and self._rehearsal)

    def _enter_rehearsal(self) -> None:
        """Shift+F5 / "◐ Rehearsal": from Preparation with the start question, from the show by a hold."""
        if self._live_mode and self._rehearsal:
            return
        if self._live_mode:
            self._leave_show_to("rehearsal")  # out of the show: through the PIN when one is set
            return
        self._rehearsal = True
        self.set_live_mode(True)  # the start question when needed; no readiness check
        if not self._live_mode:
            self._rehearsal = False
            self._apply_mode_visuals()
            return
        self._status_label.setText(tr("Prova: lo spettacolo con piccole correzioni (✎). Ciò che suona continua."))
        self.announce(self._status_label.text(), assertive=True)

    def _switch_show_to_rehearsal(self) -> None:
        self._rehearsal = True
        self._apply_mode_visuals()
        self._status_label.setText(tr("Prova: lo spettacolo con piccole correzioni (✎). Ciò che suona continua."))
        self.announce(self._status_label.text(), assertive=True)

    def _show_from_rehearsal(self) -> None:
        """"● Show" / F5 in the rehearsal: through the readiness page when it is due."""
        if self._readiness_wanted():
            self._show_readiness()
            return
        self._rehearsal = False
        self._close_drawer()
        self._apply_mode_visuals()
        self._status_label.setText("MODALITÀ LIVE ATTIVA — Interfaccia semplificata per la regia [ESC ×2 = PANIC]")
        self.announce(self._status_label.text(), assertive=True)

    # ── Drawer ────────────────────────────────────────────────────────
    def _drawer_cue(self) -> tuple[int, Cue | None]:
        row = next((i for i, c in enumerate(self._cues) if c.cue_id == self._editing_cue_id), -1)
        return row, (self._cues[row] if row >= 0 else None)

    def _open_drawer(self, cue_id: int) -> None:
        if not (self._live_mode and self._rehearsal):
            return
        self._editing_cue_id = int(cue_id)
        self._refresh_drawer()
        self._live_show_panel.now_playing.show_drawer(True)

    def _refresh_drawer(self) -> None:
        row, cue = self._drawer_cue()
        if cue is None:
            self._close_drawer()
            return
        values = {f: getattr(cue, f) for f in FIELDS}
        playing = cue.status == CueStatus.LIVE or str(self._live_phase_tags.get(cue.cue_id, "")) != ""
        drawer = self._live_show_panel.now_playing.drawer
        drawer.edit(tr("✎ CORREGGI {} '{}'").format(format_cue_ref(row, cue), cue.name), values, playing)
        changes = self._rehearsal_changes()
        drawer.set_changes(tr("Modifiche della prova: {}").format(len(changes)), len(changes))

    def _close_drawer(self) -> None:
        self._editing_cue_id = -1
        self._live_show_panel.now_playing.show_drawer(False)

    def _on_drawer_field(self, field: str, value: object) -> None:
        row, cue = self._drawer_cue()
        if cue is None or not self._change_allowed(EDIT_CUE):
            return
        self._set_cue_field(cue, field, value)
        self._refresh_drawer()

    def _set_cue_field(self, cue: Cue, field: str, value: object) -> bool:
        """Change one field of *cue* in the rehearsal: saved at once, undoable, listed."""
        if field not in FIELDS:
            return False
        if field == "name" and not str(value).strip():
            return False
        if field == "follow_mode" and cue.status == CueStatus.LIVE:
            return False  # "then" changes only while the cue does not play
        before = getattr(cue, field)
        if before == value:
            return False
        if self._undo.is_debounce_active():
            self._commit_undo_point()
        self._rehearsal_before.setdefault((cue.cue_id, field), before)
        self._rehearsal_undo.append((cue.cue_id, field, before))
        setattr(cue, field, value)
        self._commit_undo_point()
        self._mark_modified(True)
        if cue.status == CueStatus.LIVE and field in ("volume", "fade_in", "fade_out"):
            self.live_automation_updated.emit(cue)  # heard at once on the cue that plays
        self._refresh_cue_list(keep_selection=True)
        self._sync_live_view()
        row = next((i for i, c in enumerate(self._cues) if c is cue), -1)
        self._status_label.setText(tr("Prova: {} {} {} → {}").format(
            format_cue_ref(row, cue), tr(_FIELD_WORDS[field]), _shown(field, before), _shown(field, value)))
        logger.info("[REHEARSAL] #%d %s: %r -> %r", cue.cue_id, field, before, value)
        return True

    def _rehearsal_changes(self) -> list[tuple[Cue, str, object, object]]:
        """(cue, field, before, now) of what is still changed (Ctrl+Z may have undone some)."""
        by_id = {c.cue_id: c for c in self._cues}
        out = []
        for (cue_id, field), before in list(self._rehearsal_before.items()):
            cue = by_id.get(cue_id)
            if cue is None or getattr(cue, field) == before:
                self._rehearsal_before.pop((cue_id, field), None)
                continue
            out.append((cue, field, before, getattr(cue, field)))
        return out

    def _drawer_more_settings(self) -> None:
        """"More settings → Preparation": the editor on this cue (what plays goes on)."""
        cue_id = self._editing_cue_id
        self.set_live_mode(False)
        row = next((i for i, c in enumerate(self._cues) if c.cue_id == cue_id), -1)
        if row >= 0:
            self._cue_list.setCurrentRow(row)

    def _review_rehearsal_changes(self) -> None:
        """The list of changes of the rehearsal, each with Undo (a window that does not block)."""
        if self._current_mode() == "show":
            # It would take the keyboard (Space, Esc) from the show.
            self._status_label.setText(tr("Le modifiche della prova si rivedono nella prova o in preparazione"))
            return
        dlg = getattr(self, "_rehearsal_review", None)
        if dlg is None:
            from ui.main_window._cue_table import _EmergencyKeysInDialog

            dlg = QDialog(self)
            dlg.setWindowTitle(tr("Modifiche della prova"))
            dlg.setModal(False)
            dlg.setMinimumWidth(520)
            QVBoxLayout(dlg)
            self._rehearsal_review_keys = _EmergencyKeysInDialog(self, dlg)
            dlg.installEventFilter(self._rehearsal_review_keys)
            self._rehearsal_review = dlg
        lay = dlg.layout()
        while lay.count():
            item = lay.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
            elif item.layout() is not None:
                while item.layout().count():
                    sub = item.layout().takeAt(0)
                    if sub.widget() is not None:
                        sub.widget().deleteLater()
        changes = self._rehearsal_changes()
        if not changes:
            lay.addWidget(QLabel(tr("Nessuna modifica nella prova.")))
        for cue, field, before, now in changes:
            row = next((i for i, c in enumerate(self._cues) if c is cue), -1)
            line = QHBoxLayout()
            text = QLabel(f"{format_cue_ref(row, cue)} '{cue.name}' · {tr(_FIELD_WORDS[field])}: "
                          f"{_shown(field, before)} → {_shown(field, now)}")
            text.setTextFormat(Qt.TextFormat.PlainText)
            line.addWidget(text, stretch=1)
            btn = QPushButton(tr("Annulla modifica"))
            btn.installEventFilter(self._rehearsal_review_keys)
            btn.clicked.connect(lambda _=False, c=cue.cue_id, f=field, b=before:
                                self._undo_rehearsal_change(c, f, b))
            line.addWidget(btn)
            lay.addLayout(line)
        close = QPushButton(tr("Chiudi"))
        close.installEventFilter(self._rehearsal_review_keys)
        close.clicked.connect(dlg.close)
        lay.addWidget(close)
        dlg.show()
        dlg.raise_()

    def _undo_rehearsal_change(self, cue_id: int, field: str, before: object) -> None:
        cue = next((c for c in self._cues if c.cue_id == cue_id), None)
        if cue is None or not self._change_allowed(EDIT_CUE):
            return
        setattr(cue, field, before)
        self._rehearsal_before.pop((cue.cue_id, field), None)
        self._commit_undo_point()
        self._mark_modified(True)
        if cue.status == CueStatus.LIVE:
            self.live_automation_updated.emit(cue)
        self._refresh_cue_list(keep_selection=True)
        self._sync_live_view()
        if self._editing_cue_id >= 0:
            self._refresh_drawer()
        dlg = getattr(self, "_rehearsal_review", None)
        if dlg is not None and dlg.isVisible():
            self._review_rehearsal_changes()

    def _undo_last_rehearsal_change(self) -> None:
        """Ctrl+Z in the rehearsal: only its own last fix, never a list edit or the GO pointer (M6)."""
        while self._rehearsal_undo:
            cue_id, field, before = self._rehearsal_undo.pop()
            cue = next((c for c in self._cues if c.cue_id == cue_id), None)
            if cue is None or getattr(cue, field) == before:
                continue
            row = next((i for i, c in enumerate(self._cues) if c is cue), -1)
            now = getattr(cue, field)
            if not self._change_allowed(EDIT_CUE):
                return
            # One step back (the change list keeps the value from before the
            # rehearsal; an entry back at that value drops out by itself).
            setattr(cue, field, before)
            self._commit_undo_point()
            self._mark_modified(True)
            if cue.status == CueStatus.LIVE:
                self.live_automation_updated.emit(cue)
            self._refresh_cue_list(keep_selection=True)
            self._sync_live_view()
            if self._editing_cue_id >= 0:
                self._refresh_drawer()
            self._status_label.setText(tr("Annullato: {} {} {} → {}").format(
                format_cue_ref(row, cue), tr(_FIELD_WORDS[field]), _shown(field, now), _shown(field, before)))
            return
        self._status_label.setText(tr("Nessuna correzione della prova da annullare"))

    # ── Card tools of the rehearsal ───────────────────────────────────
    def _on_card_stop(self, slot: int) -> None:
        self.mark_layer_stopped(slot)
        self.layer_stop_requested.emit(slot)

    def _on_card_to_end(self, slot: int) -> None:
        end = self._live_clocks.layer_end(slot)
        if end:
            self.layer_seek_requested.emit(slot, max(0.0, end - 5.0))

    def _on_card_save_level(self, cue_id: int) -> None:
        """"Save level": the corrected level becomes the cue's own; it sounds the same."""
        cue = next((c for c in self._cues if c.cue_id == cue_id), None)
        if cue is None or not self._change_allowed(EDIT_CUE):
            return
        slot = self._runtime_slot(cue)
        trim = self._trims.get(slot, 1.0)
        new_volume = round(max(0.0, min(1.0, cue.volume * trim)), 3)
        self._trims[slot] = 1.0
        self.layer_trim_requested.emit(slot, 1.0)
        self._set_cue_field(cue, "volume", new_volume)
