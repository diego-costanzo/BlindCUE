"""Markers in a media cue (stage 2, item 2.7) mixin for MainWindow.

A marker is a named point of the file ("◆3" at 12.5 s). "◆ Mark" on the
waveform puts one at the playhead; Ctrl+K puts one where the selected cue is
playing right now (tap it in time during a rehearsal) or at the playhead.
Another cue can start "on a marker" (relative start, 2.1). A marker used by
such a cue cannot be deleted ("used by #7").
"""

from __future__ import annotations

from i18n import tr

from ui.main_window._common import *  # noqa: F403,F401,F405


class _MarkersMixin:
    def _markers_setup(self) -> None:
        self._waveform_panel.marker_add_requested.connect(self._marker_add)
        QShortcut(QKeySequence("Ctrl+K"), self, self._marker_add)
        self._cue_list.itemSelectionChanged.connect(self._markers_show)
        self._inspector.marker_delete_requested.connect(self._marker_delete)

    def _markers_show(self) -> None:
        cue = self._selected_cue()
        items = [(m["sec"], m["name"]) for m in getattr(cue, "markers", [])] if cue is not None else []
        self._waveform_panel.set_markers(items)

    def _marker_target(self) -> Cue | None:
        """In the rehearsal the sound / video started last that plays now (GO already points past it);
        in Preparation the selected cue."""
        if self._live_mode:
            playing = [c for c in self._cues if c.status == CueStatus.LIVE
                       and c.media_type in (MediaType.AUDIO, MediaType.VIDEO)]
            if playing:
                return max(playing, key=lambda c: self._fired_at.get(c.cue_id, 0))
        return self._selected_cue()

    def _marker_add(self) -> None:
        """Ctrl+K / "◆ Mark": a marker where the cue plays now, or at the playhead."""
        from engine.show_mode import EDIT_CUE, REHEARSAL

        cue = self._marker_target()
        if cue is None or not cue.media_type.has_file or cue.media_type == MediaType.IMAGE:
            self._status_label.setText(tr("Segno: scegli una cue audio o video"))
            return
        if not self._change_allowed(EDIT_CUE):
            return
        sec = None
        if cue.status == CueStatus.LIVE:
            sec = self._live_clocks.layer_position(self._runtime_slot(cue))
        if sec is None:
            sec = self._waveform.playhead_seconds()
        if sec is None:
            self._status_label.setText(tr("Segno: nessuna posizione (fai partire la cue o sposta la testina)"))
            return
        if self._undo.is_debounce_active():
            self._commit_undo_point()
        if self._current_mode() == REHEARSAL:  # listed with the rehearsal's fixes, Ctrl+Z there takes it back
            self._rehearsal_before.setdefault((cue.cue_id, "markers"), list(cue.markers))
            self._rehearsal_undo.append((cue.cue_id, "markers", list(cue.markers)))
        next_id = max([m["id"] for m in cue.markers] + [0]) + 1
        cue.markers = sorted([*cue.markers, {"id": next_id, "name": f"◆{next_id}", "sec": round(float(sec), 3)}],
                             key=lambda m: m["sec"])
        self._commit_undo_point()
        self._mark_modified(True)
        self._markers_show()
        self._inspector.load_markers(cue)
        row = next((i for i, c in enumerate(self._cues) if c is cue), -1)
        self._status_label.setText(tr("Segno ◆{} a {} s").format(next_id, f"{sec:.2f}") + f" ({format_cue_ref(row, cue)})")

    def _marker_users(self, cue: Cue, marker_id: int) -> list[str]:
        return [f"#{i + 1}" for i, c in enumerate(self._cues)
                if getattr(c, "start_rel_cue", None) == cue.cue_id and getattr(c, "start_rel_when", "") == "marker"
                and getattr(c, "start_rel_marker", None) == marker_id]

    def _marker_delete(self, marker_id: int) -> None:
        from engine.show_mode import EDIT_CUE

        cue = self._selected_cue()
        if cue is None or not self._change_allowed(EDIT_CUE):
            return
        users = self._marker_users(cue, marker_id)
        if users:
            self._status_label.setText(tr("Il segno ◆{} è usato da {}: non si può eliminare").format(
                marker_id, ", ".join(users)))
            self.announce(self._status_label.text(), assertive=True)
            return
        if self._undo.is_debounce_active():
            self._commit_undo_point()
        cue.markers = [m for m in cue.markers if m["id"] != marker_id]
        self._commit_undo_point()
        self._mark_modified(True)
        self._markers_show()
        self._inspector.load_markers(cue)
