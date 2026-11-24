"""Cues that start at a time of day (stage 2, item 2.6) mixin for MainWindow.

While the show (or, if chosen, the rehearsal) runs, a one-second timer
starts the cues whose time has come (``engine.clock_plan.due``); one more
than a minute late is skipped and said on the status line. The status bar
shows the clock and the next timed cue. "Hold the time plan" (Show menu)
stops it without changing the show; entering the show again starts the
day's plan afresh.

Never twice: every handled cue is remembered with the moment it was due
("2026-11-24T19:55:00") and that list goes into the autosave. After a
crash, restoring the session (or a new run from the top) never starts
the same moment again - the bell rang at 19:55:00, the program crashed at
19:55:10 and was back at 19:55:40: no second bell. Another day is another
moment, so tomorrow's show plays it again.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from i18n import tr

from ui.main_window._common import *  # noqa: F403,F401,F405

_KEEP_DONE = timedelta(hours=24)  # older handled moments are of no use any more


class _ClockPlanMixin:
    def _clock_setup(self) -> None:
        self._clock_handled: set[int] = set()
        self._clock_done: dict[int, str] = {}  # cue_id -> the moment it was due ("never twice")
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

    def _clock_reset(self, forget: bool = False) -> None:
        """A new run of the show (from the top) or another show (*forget*): today's plan starts afresh.

        A moment already handled stays handled (never twice); *forget* drops them all (another show:
        its cue ids mean other cues).
        """
        if forget:
            self._clock_done.clear()
        self._clock_handled = self._clock_still_done(datetime.now())

    def _clock_still_done(self, now: datetime) -> set[int]:
        """The cues whose moment due now (today's or tomorrow's time) was already handled."""
        from engine.clock_plan import occurrence, parse_clock

        done: set[int] = set()
        for cue in self._cues:
            stamp = self._clock_done.get(cue.cue_id)
            at = parse_clock(getattr(cue, "start_clock", ""))
            if stamp and at is not None and occurrence(now, at).isoformat() == stamp:
                done.add(cue.cue_id)
        return done

    def _clock_mark(self, cue: Cue, now: datetime | None = None) -> None:
        """*cue* was started or skipped: this moment of it is handled for good."""
        from engine.clock_plan import occurrence, parse_clock

        self._clock_handled.add(cue.cue_id)
        at = parse_clock(getattr(cue, "start_clock", ""))
        if at is not None:
            self._clock_done[cue.cue_id] = occurrence(now or datetime.now(), at).isoformat()

    def _clock_settings(self) -> dict:
        """For the autosave: the handled moments of the last 24 hours."""
        now = datetime.now()
        keep = {}
        for cue_id, stamp in self._clock_done.items():
            try:
                if abs(now - datetime.fromisoformat(stamp)) <= _KEEP_DONE:
                    keep[str(cue_id)] = stamp
            except (TypeError, ValueError):
                continue
        return {"clock_done": keep} if keep else {}

    def _clock_load(self, settings: dict) -> None:
        """Crash recovery: the handled moments from the autosave (nothing played twice)."""
        raw = settings.get("clock_done") if isinstance(settings, dict) else None
        self._clock_done = {}
        if isinstance(raw, dict):
            for key, stamp in raw.items():
                try:
                    datetime.fromisoformat(str(stamp))
                    self._clock_done[int(key)] = str(stamp)
                except (TypeError, ValueError):
                    continue
        self._clock_reset()

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
            self._clock_mark(cue, now)
            self._status_label.setText(tr("'{}' saltata: più di un minuto di ritardo sull'orario {}").format(
                cue.name, cue.start_clock))
            logger.warning("[CLOCK] '%s' skipped: more than a minute late (%s)", cue.name, cue.start_clock)
        for cue in start:
            self._clock_mark(cue, now)
            idx = next((i for i, c in enumerate(self._cues) if c is cue), -1)
            if idx >= 0 and self._loop_guard(cue.name):
                self._fire_cue_chain(idx, auto=True, keep_pointer=True)
                self._status_label.setText(tr("Alle {}: {}").format(cue.start_clock, cue.name))
                logger.info("[CLOCK] '%s' started at %s", cue.name, cue.start_clock)
        if start:
            self._auto_save()  # at once: a crash a second later must not start it again
