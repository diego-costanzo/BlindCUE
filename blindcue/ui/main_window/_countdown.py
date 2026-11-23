"""Countdown and run log (stage 2, item 2.5) mixin for MainWindow.

Countdown (e.g. the interval): started from the Show menu or by a
"countdown" action cue; it shows on the status bar and, if wanted, in a big
window for backstage. The last minute is amber and blinks.

Run log: every GO of the show (the first cue of what it starts) is noted
with the time since the first GO of the run. Leaving the show writes it as
CSV to Documents/BlindCue/<runs>/<show>/<date time>.csv; the newest earlier
run of the same show is read when the show starts, so the NEXT bar can say
"last time at 12:34".
"""

from __future__ import annotations

import csv
import time
from datetime import datetime
from pathlib import Path

from i18n import tr
from PySide6.QtCore import QStandardPaths
from PySide6.QtWidgets import QInputDialog

from ui.main_window._common import *  # noqa: F403,F401,F405

RUNS_FOLDER = "przebiegi"


def runs_dir(show_path: str | None) -> Path | None:
    if not show_path:
        return None
    docs = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation) or str(Path.home())
    return Path(docs) / "BlindCue" / RUNS_FOLDER / Path(show_path).stem


class _CountdownMixin:
    def _countdown_setup(self) -> None:
        self._cd_end: float | None = None
        self._cd_title = ""
        self._cd_window = None
        self._cd_timer = QTimer(self)
        self._cd_timer.setInterval(250)
        self._cd_timer.timeout.connect(self._cd_tick)
        self._lbl_countdown = QLabel("")
        self._lbl_countdown.setVisible(False)
        self._run_log: list[tuple[float, int, str, bool]] = []
        self._run_t0: float | None = None
        self._prev_run: dict[int, float] = {}

    # ── countdown ──
    def start_countdown(self, seconds: float, title: str = "") -> None:
        """Start (or replace) the countdown; 0 stops it."""
        if seconds <= 0:
            self.stop_countdown()
            return
        self._cd_end = time.monotonic() + float(seconds)
        self._cd_title = title or tr("Intervallo")
        bar = self.statusBar()
        if self._lbl_countdown.parent() is not bar:
            bar.addPermanentWidget(self._lbl_countdown)
        self._lbl_countdown.setVisible(True)
        self._cd_timer.start()
        self._cd_tick()

    def stop_countdown(self) -> None:
        self._cd_end = None
        self._cd_timer.stop()
        self._lbl_countdown.setVisible(False)
        if self._cd_window is not None:
            self._cd_window.close()

    def countdown_left(self) -> float | None:
        return None if self._cd_end is None else max(0.0, self._cd_end - time.monotonic())

    def _cd_tick(self) -> None:
        from ui.countdown_window import format_left

        left = self.countdown_left()
        if left is None:
            return
        last_minute = 0 < left <= 60
        colour = "#ef4444" if left <= 0 else ("#f59e0b" if last_minute else "#e2e8f0")
        self._lbl_countdown.setText(f"⏳ {self._cd_title} {format_left(left)}")
        self._lbl_countdown.setStyleSheet(f"color: {colour}; font-weight: bold; padding: 0 8px;")
        if self._cd_window is not None and self._cd_window.isVisible():
            self._cd_window.show_left(left, self._cd_title)
        if left <= 0:
            self._cd_timer.stop()
            self._status_label.setText(tr("Fine del conto alla rovescia: {}").format(self._cd_title))
            self.announce(self._status_label.text(), assertive=True)
            if hasattr(self, "_earcon_mgr"):
                self._earcon_mgr.play_alert()

    def _ask_countdown(self) -> None:
        minutes, ok = QInputDialog.getInt(self, tr("Conto alla rovescia"), tr("Minuti (per esempio l'intervallo):"),
                                          15, 1, 240)
        if ok:
            self.start_countdown(minutes * 60, tr("Intervallo"))

    def _show_countdown_window(self) -> None:
        from ui.countdown_window import CountdownWindow

        if self._cd_window is None:
            self._cd_window = CountdownWindow(self)
        self._cd_window.show()
        self._cd_window.raise_()
        self._cd_tick()

    # ── run log ──
    def _run_note(self, idx: int, by_hand: bool) -> None:
        """A GO started *idx* (the first cue of what it starts)."""
        from engine.show_mode import SHOW

        if not (0 <= idx < len(self._cues)) or self._current_mode() != SHOW or getattr(self, "_firing_aside", False):
            return  # only the show's own GOs (not rehearsals, effects, relative starts, calls)
        now = time.monotonic()
        if self._run_t0 is None:
            self._run_t0 = now
            self._prev_run = self._read_previous_run()
        cue = self._cues[idx]
        self._run_log.append((now - self._run_t0, cue.cue_id, cue.name, by_hand))

    def _run_reset(self) -> None:
        self._run_log = []
        self._run_t0 = None

    def _run_save(self) -> Path | None:
        """Write the run (if any) and start a new one."""
        folder = runs_dir(getattr(self, "_current_project_path", None))
        log, self._run_log, self._run_t0 = self._run_log, [], None
        if folder is None or not log:
            return None
        try:
            folder.mkdir(parents=True, exist_ok=True)
            target = folder / f"{datetime.now():%Y-%m-%d_%H%M%S}.csv"
            rows = {c.cue_id: i for i, c in enumerate(self._cues)}
            with open(target, "w", newline="", encoding="utf-8") as fh:
                out = csv.writer(fh)
                out.writerow(["seconds", "time", "cue_id", "number", "name", "by_hand"])
                for secs, cue_id, name, by_hand in log:
                    out.writerow([f"{secs:.1f}", _mmss(secs), cue_id, rows.get(cue_id, -1) + 1, name, int(by_hand)])
            return target
        except OSError as exc:
            logger.warning("[RUN LOG] cannot write: %s", exc)
            return None

    def _read_previous_run(self) -> dict[int, float]:
        folder = runs_dir(getattr(self, "_current_project_path", None))
        if folder is None or not folder.is_dir():
            return {}
        files = sorted(folder.glob("*.csv"))
        if not files:
            return {}
        seen: dict[int, float] = {}
        try:
            with open(files[-1], encoding="utf-8") as fh:
                for row in csv.DictReader(fh):
                    seen.setdefault(int(row["cue_id"]), float(row["seconds"]))
        except (OSError, ValueError, KeyError, TypeError, csv.Error):
            return {}  # a damaged log: no hints, never a blocked GO
        return seen

    def previous_run_hint(self, cue: Cue | None) -> str:
        """"last time at 12:34" for the NEXT bar (empty without an earlier run)."""
        if cue is None or cue.cue_id not in self._prev_run:
            return ""
        return tr("la volta scorsa a {}").format(_mmss(self._prev_run[cue.cue_id]))


def _mmss(seconds: float) -> str:
    total = max(0, int(round(seconds)))
    hours, rest = divmod(total, 3600)
    return f"{hours}:{rest // 60:02d}:{rest % 60:02d}" if hours else f"{rest // 60:02d}:{rest % 60:02d}"
