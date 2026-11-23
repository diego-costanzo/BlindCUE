"""Undo the last GO (stage 1.18) mixin for MainWindow.

The GO given by hand is recorded while it runs (every cue it starts, and what
each one pushed off its layer). For 15 s – Pause All stops the count – the
"Last" line offers "↶ Undo GO #5 · 12"; one click fades out only what that GO
started, brings back a picture it replaced and points the GO back at its
first cue. The next GO by hand, PANIC, Fade All, Blackout and a change of mode
end the offer. ``main.py`` does the work on the players (``undo_go_requested``).
"""

from __future__ import annotations

import math
import time

from engine.undo_go import (
    CANCEL,
    ENDED,
    FADE,
    KEEP,
    LIFT,
    RESTORE,
    UndoRecord,
    UndoStep,
    can_undo,
    undo_plan,
)
from i18n import tr

from ui.main_window._common import *  # noqa: F403,F401,F405


class _UndoGoMixin:
    # ── Record ────────────────────────────────────────────────────────
    def _undo_go_setup(self) -> None:
        """State and the 4 Hz countdown (called from the window's __init__)."""
        self._undo_go: UndoRecord | None = None
        self._undo_go_collecting = False
        self._undo_auto_source: int | None = None
        self._undo_go_timer = QTimer(self)
        self._undo_go_timer.setInterval(250)
        self._undo_go_timer.timeout.connect(self._refresh_undo_go)

    def _undo_go_begin(self, cue: Cue) -> None:
        """A GO by hand starts now: it is the one Undo takes back."""
        self._undo_go = UndoRecord(first_id=cue.cue_id, started=time.monotonic())
        if getattr(self, "_is_global_paused", False):
            self._undo_go.set_paused(True, time.monotonic())
        if not self._undo_go_timer.isActive():
            self._undo_go_timer.start()

    def _undo_go_collect(self, cue: Cue) -> None:
        """*cue* was started by the GO being recorded (chain, group, its Auto-GO)."""
        if self._undo_go is not None and self._undo_go_collecting:
            self._undo_go.add(cue.cue_id)

    def _undo_go_takes_auto(self) -> bool:
        """An Auto-GO belongs to the recorded GO when the cue that handed over did."""
        rec = self._undo_go
        return rec is not None and self._undo_auto_source in rec.ids

    def note_replaced(self, cue: Cue, before: Cue | None) -> None:
        """main.py: *cue* goes on the layer where *before* was on air."""
        rec = self._undo_go
        if rec is None or before is None or before.cue_id == cue.cue_id or cue.cue_id not in rec.ids:
            return
        rec.replaced.setdefault(cue.cue_id, before.cue_id)

    def _undo_go_pause(self, paused: bool) -> None:
        if self._undo_go is not None:
            self._undo_go.set_paused(paused, time.monotonic())
            self._refresh_undo_go()

    def _undo_go_end(self) -> None:
        """The offer is over (time, a new GO, PANIC, Fade All, mode change, done)."""
        self._undo_go = None
        self._undo_go_timer.stop()
        self._show_undo_go("", "", "")

    # ── Words ─────────────────────────────────────────────────────────
    def _undo_ref(self, cue_id: int | None, with_name: bool = True) -> str:
        row = next((i for i, c in enumerate(self._cues) if c.cue_id == cue_id), -1)
        if row < 0:
            return "?"
        cue = self._cues[row]
        ref = format_cue_ref(row, cue)
        return f"{ref} '{cue.name}'" if with_name else ref

    def _undo_go_steps(self) -> list[UndoStep]:
        if self._undo_go is None:
            return []
        waiting = {cid for cid, tag in self._live_phase_tags.items() if str(tag).startswith("PRE")}
        return undo_plan(self._cues, self._undo_go, waiting)

    def _undo_go_preview(self, steps: list[UndoStep]) -> str:
        """What one click will do, in words (tooltip and screen reader)."""
        def refs(kind: str, attr: str = "cue_id") -> list[str]:
            picked = [getattr(s, attr) for s in steps if s.how == kind]
            return [self._undo_ref(cid, with_name=len(picked) == 1) for cid in picked]

        parts: list[str] = []
        if fades := refs(FADE):
            parts.append(tr("sfumo {} (1 s)").format(", ".join(fades)))
        if lifts := refs(LIFT):
            parts.append(tr("tolgo {} dallo schermo").format(", ".join(lifts)))
        for back in refs(RESTORE, "restore_id"):
            parts.append(tr("l'immagine {} torna").format(back))
        for cid in (s.cue_id for s in steps if s.how == CANCEL):
            parts.append(tr("{} non è ancora partita: la annullo").format(self._undo_ref(cid, False)))
        for cid in (s.cue_id for s in steps if s.how == ENDED):
            parts.append(tr("{} è già finita").format(self._undo_ref(cid, False)))
        for cid in (s.cut_id for s in steps if s.cut_id is not None):
            parts.append(tr("{} interrotta: non torna da sola").format(self._undo_ref(cid)))
        for cid in (s.cue_id for s in steps if s.how == KEEP):
            parts.append(tr("l'azione {} resta").format(self._undo_ref(cid, False)))
        parts.append(tr("prossima di nuovo {}").format(self._undo_ref(self._undo_go.first_id, False)))
        return tr("Annullo:") + " " + " · ".join(parts)

    def _show_undo_go(self, label: str, tip: str, accessible: str) -> None:
        panel = getattr(self, "_live_show_panel", None)
        if panel is not None:
            panel.set_undo_go(label, tip, accessible)
        act = getattr(self, "_act_undo_go", None)
        if act is not None:
            act.setEnabled(bool(label))
            act.setToolTip(tip)

    def _refresh_undo_go(self) -> None:
        """4 Hz: the countdown on the button; the offer ends after 15 s."""
        rec = self._undo_go
        if rec is None:
            self._undo_go_end()
            return
        left = rec.seconds_left(time.monotonic())
        if left <= 0:
            self._undo_go_end()
            return
        steps = self._undo_go_steps()
        ref = self._undo_ref(rec.first_id, with_name=False)
        secs = math.ceil(left)
        label = tr("↶ Annulla GO {} · {}").format(ref, secs)
        tip = self._undo_go_preview(steps) if can_undo(steps) else tr("Questo GO non si annulla (azione)")
        accessible = tr("Annulla GO {} ({} s)").format(self._undo_ref(rec.first_id), secs)
        self._show_undo_go(label, tip, accessible)

    # ── Doing it ──────────────────────────────────────────────────────
    @Slot()
    def _on_undo_go(self) -> None:
        """One click, no dialog: take back what the last GO by hand started."""
        rec = self._undo_go
        if rec is None or rec.seconds_left(time.monotonic()) <= 0:
            self._undo_go_end()
            self._status_label.setText(tr("Nessun GO da annullare"))
            return
        steps = self._undo_go_steps()
        if not can_undo(steps):
            self._status_label.setText(tr("Questo GO non si annulla (azione)"))
            if hasattr(self, "_earcon_mgr"):
                self._earcon_mgr.play_alert()
            return
        preview = self._undo_go_preview(steps)
        self.undo_go_requested.emit(steps)  # main.py: players and output
        by_id = {c.cue_id: c for c in self._cues}
        for step in steps:
            if step.how == KEEP:
                continue
            self._played_ids.discard(step.cue_id)
            self._fired_at.pop(step.cue_id, None)
            cue = by_id.get(step.cue_id)
            if cue is not None and step.how != ENDED:
                self._live_phase_tags.pop(cue.cue_id, None)
                if cue.status == CueStatus.LIVE:
                    cue.status = CueStatus.LOADED
        first_ref = self._undo_ref(rec.first_id, with_name=False)
        row = next((i for i, c in enumerate(self._cues) if c.cue_id == rec.first_id), -1)
        logger.info("[UNDO-GO] %s: %s", first_ref, preview)
        self._undo_go_end()
        if hasattr(self, "_earcon_mgr"):
            self._earcon_mgr.play_stop()
        self._refresh_cue_list(keep_selection=False)
        if row >= 0:
            self._cue_list.setCurrentRow(row)  # the GO points back at its first cue
        self._sync_live_view()
        panel = getattr(self, "_live_show_panel", None)
        if panel is not None:
            panel.set_last_started(tr("↶ GO {} annullato").format(first_ref), by_hand=False)
        self._status_label.setText(
            tr("GO {} annullato · prossima: {}").format(first_ref, self._undo_ref(rec.first_id))
        )

