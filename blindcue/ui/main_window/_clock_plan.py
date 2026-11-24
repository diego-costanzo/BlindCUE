"""Cues that start at a time of day (stage 2, item 2.6) mixin for MainWindow.

While the show (or, if chosen, the rehearsal) runs, a one-second timer
starts the cues whose time has come (``engine.clock_plan.due``); one more
than a minute late is skipped and said on the status line. The status bar
shows the clock and the next timed cue. "Hold the time plan" (Show menu)
stops it without changing the show; entering the show again starts the
day's plan afresh.
"""

from __future__ import annotations

from datetime import datetime

from i18n import tr

from ui.main_window._common import *  # noqa: F403,F401,F405


class _ClockPlanMixin:
    def _clock_setup(self) -> None:
        self._clock_handled: set[int] = set()
        self._clock_held = False
        self._clock_timer = QTimer(self)
        self._clock_timer.setInterval(1000)
        self._clock_timer.timeout.connect(self._clock_tick)
        self._clock_timer.start()
        self._lbl_clock = QLabel("")
        self._lbl_clock.setStyleSheet("color: #94a3b8; padding: 0 8px;")
        self._lbl_clock.setVisible(False)

    def _clock_active(self) -> bool:
        """The time plan runs in the show (and in the rehearsal when chosen), not when held."""
        from engine.show_mode import REHEARSAL, SHOW

        mode = self._current_mode()
        also_rehearsal = QSettings("BlindCue", "BlindCue").value("live/clock_in_rehearsal", False, type=bool)
        return not self._clock_held and (mode == SHOW or (mode == REHEARSAL and also_rehearsal))

    def _clock_reset(self) -> None:
        """A new run of the show (from the top) or another show: today's plan starts afresh."""
        self._clock_handled.clear()

    def _toggle_clock_hold(self, held: bool) -> None:
        self._clock_held = bool(held)
        self._status_label.setText(tr("Piano orario sospeso") if held else tr("Piano orario attivo"))
        self._clock_tick()

    def _clock_tick(self, now: datetime | None = None) -> None:
        from engine.clock_plan import due, next_timed

        now = now or datetime.now()
        timed = any(getattr(c, "start_clock", "") for c in self._cues)
        if not timed:
            self._lbl_clock.setVisible(False)
            return
        bar = self.statusBar()
        if self._lbl_clock.parent() is not bar:
            bar.addPermanentWidget(self._lbl_clock)
        coming = next_timed(self._cues, now, self._clock_handled)
        text = f"🕐 {now:%H:%M:%S}"
        if coming is not None:
            text += f"  → {coming[1]:%H:%M:%S} '{coming[0].name}'"
        if self._clock_held:
            text += "  " + tr("(sospeso)")
        self._lbl_clock.setText(text)
        self._lbl_clock.setVisible(True)
        if not self._clock_active():
            return
        if getattr(self, "_is_global_paused", False):
            return  # Pause All holds the plan too; after it, more than a minute late = skipped
        start, skip = due(self._cues, now, self._clock_handled)
        for cue in skip:
            self._clock_handled.add(cue.cue_id)
            self._status_label.setText(tr("'{}' saltata: più di un minuto di ritardo sull'orario {}").format(
                cue.name, cue.start_clock))
            logger.warning("[CLOCK] '%s' skipped: more than a minute late (%s)", cue.name, cue.start_clock)
        for cue in start:
            self._clock_handled.add(cue.cue_id)
            idx = next((i for i, c in enumerate(self._cues) if c is cue), -1)
            if idx >= 0 and self._loop_guard(cue.name):
                self._fire_cue_chain(idx, auto=True, keep_pointer=True)
                self._status_label.setText(tr("Alle {}: {}").format(cue.start_clock, cue.name))
                logger.info("[CLOCK] '%s' started at %s", cue.name, cue.start_clock)
