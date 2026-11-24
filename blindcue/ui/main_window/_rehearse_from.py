"""Rehearsal from a chosen moment (stage 2, item 2.4) mixin for MainWindow.

Right-click a cue → "Rehearse from here": the program works out what stays
on screen and in the speakers at that point (``engine.rehearse_from``),
shows it, stops what plays now (after asking), starts those cues again with
the levels and opacity set on the way, and puts GO on the chosen cue.
Not in the Show mode: there the order is never jumped.
"""

from __future__ import annotations

import math

from i18n import tr

from ui.main_window._common import *  # noqa: F403,F401,F405


class _RehearseFromMixin:
    def _rehearse_from(self, row: int) -> None:
        from engine.rehearse_from import state_before
        from engine.show_mode import SHOW

        if not (0 <= row < len(self._cues)):
            return
        if self._current_mode() == SHOW:
            self._status_label.setText(tr("Nello spettacolo non si salta: usa la prova"))
            return
        state = state_before(self._cues, row, dual_active=self._dual_output_active)
        lines = []
        for (output, layer), entry in sorted(state.items(), key=lambda kv: kv[1].row):
            where = f"L{layer}" + (" · B" if output == "B" else "")
            extra = []
            if entry.level_abs is not None:
                extra.append(f"{round(entry.level_abs * 100)}%")
            if entry.level_db:
                extra.append(f"{entry.level_db:+.0f} dB")
            if entry.opacity is not None:
                extra.append(tr("opacità {}%").format(round(entry.opacity * 100)))
            lines.append(f"{where}: {format_cue_ref(entry.row, entry.cue)} '{entry.cue.name}'"
                         + (f" ({', '.join(extra)})" if extra else ""))
        target = f"{format_cue_ref(row, self._cues[row])} '{self._cues[row].name}'"
        text = tr("Prova da {}.").format(target) + "\n\n" + (
            tr("Prima di questa cue restano in onda:") + "\n" + "\n".join(lines) if lines
            else tr("Prima di questa cue non resta niente in onda."))
        if self._show_running():
            text += "\n\n" + tr("Ora suona qualcosa: verrà fermato.")
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle(tr("Prova da qui"))
        box.setText(text)
        go = box.addButton(tr("▶ Prepara la scena"), QMessageBox.ButtonRole.AcceptRole)
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(go)
        box.exec()
        if box.clickedButton() is not go:
            return
        self._rehearse_apply(row, state)

    def _fire_one_now(self, idx: int) -> None:
        """Start this one cue now: no "together" followers, no Pre-Delay, GO not moved."""
        cue = self._cues[idx]
        from models.cue import is_placeholder

        if is_placeholder(cue):
            return  # 3.4: no file yet: nothing to bring back
        self._rel_extra[cue.cue_id] = -float(max(0.0, cue.pre_delay))  # main.py: Pre-Delay + this = 0
        aside = getattr(self, "_firing_aside", False)
        self._firing_aside = True
        try:
            ShowEngine.promote_to_live(self._cues, cue, dual_active=self._dual_output_active,
                                       exclude_ids=set(self._slot_override))
            self._update_live_layer_label(cue)
            self._note_fired(cue)
            self.cue_fired.emit(cue)
        finally:
            self._rel_extra.pop(cue.cue_id, None)
            self._firing_aside = aside

    def _rehearse_apply(self, row: int, state: dict) -> None:
        """Stop everything, bring back what stays at *row*, put GO on *row*."""
        if self._show_running():
            self._on_panic()
        for entry in sorted(state.values(), key=lambda e: e.row):
            idx = next((i for i, c in enumerate(self._cues) if c is entry.cue), -1)
            if idx < 0:
                continue
            self._fire_one_now(idx)
            slot = self._runtime_slot(entry.cue)
            trim = None
            if entry.level_abs is not None and entry.cue.volume > 0:
                trim = entry.level_abs / entry.cue.volume
            if entry.level_db:
                trim = (trim if trim is not None else 1.0) * math.pow(10.0, entry.level_db / 20.0)
            if trim is not None:
                trim = max(0.0, min(1.0, trim))
                self._trims[slot] = trim
                self.layer_trim_requested.emit(slot, trim)
            if entry.opacity is not None:
                self.layer_opacity_requested.emit(slot, float(entry.opacity))
        self._cue_list.setCurrentRow(row)
        self._sync_live_view()
        self._status_label.setText(tr("Scena pronta: il prossimo GO è {}").format(
            format_cue_ref(row, self._cues[row])))
        self.announce(self._status_label.text())
