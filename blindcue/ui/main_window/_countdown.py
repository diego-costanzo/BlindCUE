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
        # (seconds from the first GO, cue_id or -1, name or detail, by hand, event) - 5.19 events too
        self._run_log: list[tuple[float, int, str, bool, str]] = []
        self._run_t0: float | None = None
        self._run_started: datetime | None = None
        self._prev_run: dict[int, float] = {}
        self._sw_total = 0.0                     # 2.11 stopwatch: seconds before the current run
        self._sw_since: float | None = None      # monotonic start of the current run (None = stopped)
        self._sw_used = False                    # shown (status bar, big window, phone) once it was used
        self._sw_timer = QTimer(self)
        self._sw_timer.setInterval(500)
        self._sw_timer.timeout.connect(self._sw_tick)
        self._lbl_stopwatch = QLabel("")
        self._lbl_stopwatch.setVisible(False)

    # ── stopwatch (2.11) ──
    def stopwatch(self, mode: str) -> None:
        """An action cue or the Show menu: "start", "stop" (goes on from there next time) or "reset" (zero)."""
        self._sw_used = True
        now = time.monotonic()
        if mode == "start" and self._sw_since is None:
            self._sw_since = now
        elif mode == "stop" and self._sw_since is not None:
            self._sw_total += now - self._sw_since
            self._sw_since = None
        elif mode == "reset":
            self._sw_total = 0.0
            if self._sw_since is not None:
                self._sw_since = now
        bar = self.statusBar()
        if self._lbl_stopwatch.parent() is not bar:
            bar.addPermanentWidget(self._lbl_stopwatch)
        self._lbl_stopwatch.setVisible(True)
        if self._sw_since is None:
            self._sw_timer.stop()
        else:
            self._sw_timer.start()
        self._sw_tick()

    def stopwatch_seconds(self) -> float:
        return self._sw_total + (0.0 if self._sw_since is None else time.monotonic() - self._sw_since)

    def _sw_tick(self) -> None:
        running = self._sw_since is not None
        self._lbl_stopwatch.setText(f"⏱ {_mmss(int(self.stopwatch_seconds()))}" + ("" if running else " ❚❚"))
        self._lbl_stopwatch.setStyleSheet(f"color: {'#7dd3fc' if running else '#94a3b8'}; padding: 0 8px;")
        if self._cd_window is not None and self._cd_window.isVisible():
            self._cd_window.show_stopwatch(self.stopwatch_seconds(), running)  # 2.11: also backstage

    def remote_timers(self) -> dict:
        """2.5: what the phone pages show next to the cues - the computer clock, the countdown,
        the stopwatch (once used) and the next cue that starts at a time of day."""
        from engine.clock_plan import next_timed

        now = datetime.now()
        data: dict = {"clock": now.strftime("%H:%M:%S")}
        left = self.countdown_left()
        if left is not None:
            data["countdown"] = {"title": self._cd_title, "left": round(left, 1)}
        if self._sw_used:
            data["stopwatch"] = {"sec": round(self.stopwatch_seconds(), 1), "running": self._sw_since is not None}
        if any(getattr(c, "start_clock", "") for c in self._cues):
            coming = next_timed(self._cues, now, getattr(self, "_clock_handled", set()))
            if coming is not None:
                data["next_timed"] = {"at": coming[1].strftime("%H:%M:%S"), "name": coming[0].name,
                                      "held": bool(getattr(self, "_clock_held", False))}
        return data

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
            if self._sw_used and self._cd_window.isVisible():
                self._cd_window.show_countdown_off()  # 2.11: the stopwatch stays on the big window
            else:
                self._cd_window.close()

    def countdown_left(self) -> float | None:
        return None if self._cd_end is None else max(0.0, self._cd_end - time.monotonic())

    def _cd_tick(self) -> None:
        from ui.countdown_window import format_left

        left = self.countdown_left()
        if left is None:
            if self._cd_window is not None and self._cd_window.isVisible():
                if self._sw_used:
                    self._cd_window.show_countdown_off()  # 2.11: the stopwatch alone, in large digits
                else:
                    self._cd_window.show_idle()
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
        if self._sw_used:
            self._sw_tick()
        else:
            self._cd_window.show_stopwatch(None)

    # ── run log ──
    def _run_note(self, idx: int, by_hand: bool) -> None:
        """A GO started *idx* (the first cue of what it starts)."""
        from engine.show_mode import SHOW

        if not (0 <= idx < len(self._cues)) or self._current_mode() != SHOW or getattr(self, "_firing_aside", False):
            return  # only the show's own GOs (not rehearsals, effects, relative starts, calls)
        now = self._run_clock()
        cue = self._cues[idx]
        self._run_log.append((now - self._run_t0, cue.cue_id, cue.name, by_hand, "GO" if by_hand else "AUTO"))

    def _run_clock(self) -> float:
        now = time.monotonic()
        if self._run_t0 is None:
            self._run_t0 = now
            self._run_started = datetime.now()
            self._prev_run = self._read_previous_run()
        return now

    def _run_event(self, event: str, detail: str = "", cue_id: int = -1) -> None:
        """5.19: PANIC, Fade All, a pause, Undo GO, an effect... of the show (not of a rehearsal)."""
        from engine.show_mode import SHOW

        if self._current_mode() != SHOW:
            return
        now = self._run_clock()
        self._run_log.append((now - self._run_t0, cue_id, detail, True, event))

    def _run_reset(self) -> None:
        self._run_log = []
        self._run_t0 = None
        self._run_started = None

    def _run_save(self) -> Path | None:
        """Write the run (if any) and start a new one."""
        folder = runs_dir(getattr(self, "_current_project_path", None))
        if self._run_log and self._run_t0 is not None:
            self._run_log.append((time.monotonic() - self._run_t0, -1, "", True, "END"))
        log, self._run_log, self._run_t0 = self._run_log, [], None
        started, self._run_started = self._run_started, None
        if folder is None or not log:
            return None
        try:
            folder.mkdir(parents=True, exist_ok=True)
            target = folder / f"{datetime.now():%Y-%m-%d_%H%M%S}.csv"
            rows = {c.cue_id: i for i, c in enumerate(self._cues)}
            with open(target, "w", newline="", encoding="utf-8") as fh:
                out = csv.writer(fh)
                out.writerow(["seconds", "time", "cue_id", "number", "name", "by_hand", "event"])
                for secs, cue_id, name, by_hand, event in log:
                    out.writerow([f"{secs:.1f}", _mmss(secs), cue_id, rows.get(cue_id, -1) + 1, name,
                                  int(by_hand), event])
            self._write_run_report(target.with_suffix(".html"), log, started or datetime.now())
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
                    if row.get("event", "GO") in ("GO", "AUTO"):  # 5.19 logs also PANIC, pauses...
                        seen.setdefault(int(row["cue_id"]), float(row["seconds"]))
        except (OSError, ValueError, KeyError, TypeError, csv.Error):
            return {}  # a damaged log: no hints, never a blocked GO
        return seen

    def _write_run_report(self, target: Path, log: list, started: datetime) -> None:
        """5.19: the report page next to the run's CSV (what played, when, by hand or not, alarms)."""
        from engine import run_report as rr
        from engine.show_engine import go_stops
        from version import APP_NAME, APP_VERSION

        rows = {c.cue_id: i for i, c in enumerate(self._cues)}
        labels = {rr.GO: tr("GO"), rr.AUTO: tr("automatico"), rr.PANIC: tr("PANIC"),
                  rr.FADE_ALL: tr("Sfuma tutto"), rr.PAUSE: tr("Pausa tutto"), rr.RESUME: tr("Riprendi"),
                  rr.BLACKOUT: tr("Blackout"), rr.UNDO_GO: tr("Annulla l'ultimo GO"), rr.EFFECT: tr("Effetto"),
                  rr.FADE_SCENE: tr("Sfuma la scena"), rr.END: tr("Fine dello spettacolo"),
                  rr.NOTE: tr("📝 Annotazione")}  # 5.6: the operator's diary
        summary = {"start": tr("Inizio"), "end": tr("Fine"), "length": tr("Durata"),
                   rr.GO: tr("GO a mano"), rr.AUTO: tr("Partenze automatiche"), rr.EFFECT: tr("Effetti"),
                   rr.PAUSE: tr("Pause"), rr.FADE_ALL: tr("Sfuma tutto"), rr.PANIC: tr("PANIC"),
                   rr.BLACKOUT: tr("Blackout"), rr.UNDO_GO: tr("GO annullati"), rr.NOTE: tr("Annotazioni")}
        entries = [(secs, event, f"#{rows[cid] + 1}" if cid in rows else "", name)
                   for secs, cid, name, _hand, event in log]
        played = {cid for _s, cid, _n, _h, event in log if event in rr.CUE_EVENTS}
        go_rows = go_stops(self._cues)
        missed = [f"#{r + 1} '{self._cues[r].name}'" for r in
                  rr.unplayed(go_rows, played, [c.cue_id for c in self._cues])]
        title = tr("Rapporto dello spettacolo") + " – " + (self._show_title() if hasattr(self, "_show_title") else "")
        page = rr.to_html(title, started, entries, labels, summary, missed,
                          (tr("In breve"), tr("Che cosa è successo"), tr("Cue con GO mai partite")),
                          f"{started:%Y-%m-%d} · {APP_NAME} {APP_VERSION}")
        try:
            target.write_text(page, encoding="utf-8")
        except OSError as exc:
            logger.warning("[RUN REPORT] cannot write: %s", exc)

    def _open_last_run_report(self) -> None:
        """File → Export and print → "Report of the last show"."""
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        folder = runs_dir(getattr(self, "_current_project_path", None))
        reports = sorted(folder.glob("*.html")) if folder is not None and folder.is_dir() else []
        if not reports:
            self._status_label.setText(tr("Nessun rapporto: si scrive alla fine dello spettacolo (non della prova)"))
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(reports[-1])))

    def previous_run_hint(self, cue: Cue | None) -> str:
        """"last time at 12:34" for the NEXT bar (empty without an earlier run)."""
        if cue is None or cue.cue_id not in self._prev_run:
            return ""
        return tr("la volta scorsa a {}").format(_mmss(self._prev_run[cue.cue_id]))


def _mmss(seconds: float) -> str:
    total = max(0, int(round(seconds)))
    hours, rest = divmod(total, 3600)
    return f"{hours}:{rest // 60:02d}:{rest % 60:02d}" if hours else f"{rest // 60:02d}:{rest % 60:02d}"
