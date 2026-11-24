"""Stage 2, item 2.5: countdown (interval) and the run log of the show."""

from __future__ import annotations

import csv
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "blindcue"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import pytest
from engine.action_cues import describe_action
from models.cue import Cue, MediaType
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qt_app():
    app = QApplication.instance() or QApplication([])
    yield app


def _pump(seconds: float = 0.05) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.005)


def _cue(i: int, **extra) -> Cue:
    data = {"cue_id": 9901 + i, "name": f"c{i}", "media_type": MediaType.AUDIO.value,
            "file_path": f"/nonexistent/c{i}.wav"}
    data.update(extra)
    return Cue.from_dict(data)


def test_format_and_big_window(qt_app):
    from ui.countdown_window import CountdownWindow, format_left

    assert format_left(754) == "12:34" and format_left(3723) == "1:02:03" and format_left(-5) == "00:00"
    win = CountdownWindow()
    win.show_left(30, "Intervallo")
    first = win.lbl_time.styleSheet()
    win.show_left(29, "Intervallo")
    assert win.lbl_time.text() == "00:29" and first != win.lbl_time.styleSheet()   # the last minute blinks
    win.show_left(0, "Intervallo")
    assert "#ef4444" in win.lbl_time.styleSheet()
    win.close()
    assert describe_action({"kind": "countdown", "countdown_sec": 900, "text": "Przerwa"}).startswith(
        "Conto alla rovescia 15:00")


@pytest.fixture()
def window(qt_app, tmp_path, monkeypatch):
    from ui.main_window import MainWindow, _countdown
    from ui.output_window import OutputWindow

    monkeypatch.setattr(_countdown, "runs_dir", lambda show: tmp_path / "runs" / Path(show).stem if show else None)
    output = OutputWindow()
    win = MainWindow(output)
    win._cues = [_cue(0, name="a"), _cue(1, name="b"), _cue(2, name="c")]
    win._current_project_path = str(tmp_path / "play.blindcue")
    win._refresh_cue_list(keep_selection=False)
    win._cue_list.setCurrentRow(0)
    try:
        yield win, tmp_path
    finally:
        win.stop_countdown()
        win._force_closing = True
        output.force_close()
        win.close()
        _pump()
        win.deleteLater()
        output.deleteLater()
        _pump()


def test_countdown_on_the_status_bar(window):
    win, _tmp = window
    win.start_countdown(90, "Intervallo")
    assert win._lbl_countdown.isVisibleTo(win) and 89 <= win.countdown_left() <= 90
    assert "01:30" in win._lbl_countdown.text() or "01:29" in win._lbl_countdown.text()
    win.start_countdown(30, "Intervallo")
    win._cd_tick()
    assert "#f59e0b" in win._lbl_countdown.styleSheet()                    # the last minute
    win._show_countdown_window()
    assert win._cd_window.isVisible()
    win.start_countdown(0)                                                  # an action with 0 stops it
    assert not win._lbl_countdown.isVisibleTo(win) and win.countdown_left() is None


def test_run_log_and_last_time_hint(window):
    win, tmp = window
    win.set_live_mode(True)
    win._on_go()
    win._last_go_at = None
    time.sleep(0.05)
    win._on_go()
    win.set_live_mode(False)                                                # writes the run
    files = list((tmp / "runs" / "play").glob("*.csv"))
    assert len(files) == 1
    rows = list(csv.DictReader(open(files[0], encoding="utf-8")))
    gos = [r for r in rows if r["event"] in ("GO", "AUTO")]
    assert [r["name"] for r in gos] == ["a", "b"] and float(gos[1]["seconds"]) > 0
    assert rows[-1]["event"] == "END" and files[0].with_suffix(".html").is_file()   # 5.19: the report
    win._cue_list.setCurrentRow(0)
    win._confirm_live_start = lambda: True                                  # "where does it start?": the top
    win.set_live_mode(True)                                                 # the next run
    win._last_go_at = None                                                  # (no double-GO guard here)
    win._on_go()                                                            # reads the last run
    assert win.previous_run_hint(win._cues[1]).startswith("la volta scorsa a 00:00")
    assert win._live_show_panel.lbl_standby_prev.text() != ""


def test_review_damaged_log_and_rehearsal_not_logged(window):
    win, tmp = window
    folder = tmp / "runs" / "play"
    folder.mkdir(parents=True)
    (folder / "2020-01-01_000000.csv").write_text("seconds,time,cue_id\n1.0\n", encoding="utf-8")
    assert win._read_previous_run() == {}                                   # damaged: no hints, no error
    win._enter_rehearsal()
    win._on_go()
    assert win._run_log == []                                               # a rehearsal is not a run


def test_show_report_has_every_event_and_the_missed_cues(window):
    """5.19: PANIC, pauses, Fade All and the end go into the run log and the report page."""
    win, tmp = window
    win.set_live_mode(True)
    win._on_go()
    win.set_global_paused(True)
    win.set_global_paused(False)
    win._on_fade_all()
    win._on_panic()
    win.set_live_mode(False)
    csv_file = next((tmp / "runs" / "play").glob("*.csv"))
    events = [r["event"] for r in csv.DictReader(open(csv_file, encoding="utf-8"))]
    assert events[0] == "GO" and events[-1] == "END"
    assert {"PAUSE", "RESUME", "FADE_ALL", "PANIC"} <= set(events)
    page = csv_file.with_suffix(".html").read_text(encoding="utf-8")
    assert "class='alarm'" in page and "#3 &#x27;c&#x27;" in page and "#1 &#x27;a&#x27;" not in page  # c never played
    assert win._read_previous_run() == {9901: 0.0}                                  # hints read only GOs


def test_timers_for_the_phone_pages(window):
    """2.5: the phone remote and the director monitor get the clock, the countdown, the stopwatch, the plan."""
    win, _tmp = window
    timers = win.get_remote_state()["timers"]
    assert set(timers) == {"clock"} and len(timers["clock"]) == 8           # "19:54:10", nothing else yet
    win.start_countdown(90, "Przerwa")
    win.stopwatch("start")
    win._cues[2].start_clock = "23:59:59"
    timers = win.remote_timers()
    assert timers["countdown"]["title"] == "Przerwa" and 89 <= timers["countdown"]["left"] <= 90
    assert timers["stopwatch"]["running"] is True and timers["stopwatch"]["sec"] >= 0
    assert timers["next_timed"]["name"] == "c" and timers["next_timed"]["at"] == "23:59:59"
    win.stopwatch("stop")
    win.stop_countdown()
    timers = win.remote_timers()
    assert "countdown" not in timers and timers["stopwatch"]["running"] is False   # the stopwatch stays shown


def test_stopwatch_in_the_menu_and_the_big_window(window):
    """2.11 rest: start / stop / reset from the Show menu, and the stopwatch in the backstage window."""
    from PySide6.QtGui import QAction

    win, _tmp = window
    actions = {a.text(): a for a in win.findChildren(QAction)}
    actions["Cronometro: avvia"].trigger()
    assert win._sw_since is not None and win._lbl_stopwatch.isVisibleTo(win)
    win.start_countdown(120, "Intervallo")
    win._show_countdown_window()
    big = win._cd_window
    assert big.lbl_stopwatch.isVisible() and big.lbl_stopwatch.text().startswith("⏱ 00:0")
    assert big.lbl_time.isVisible()
    win.stop_countdown()                                                    # the stopwatch keeps the window
    assert big.isVisible() and not big.lbl_time.isVisible() and big.lbl_stopwatch.isVisible()
    assert big.lbl_stopwatch.font().pixelSize() == big.lbl_time.font().pixelSize()   # alone: large digits
    actions["Cronometro: ferma"].trigger()
    assert win._sw_since is None and big.lbl_stopwatch.text().endswith("❚❚")
    actions["Cronometro: azzera"].trigger()
    assert win.stopwatch_seconds() == 0.0
    win.start_countdown(60, "Intervallo")                                   # a new countdown comes back on
    assert big.lbl_time.isVisible() and big.lbl_title.text() == "Intervallo"
    big.close()


def test_big_window_without_anything_to_count(qt_app):
    from ui.countdown_window import CountdownWindow

    win = CountdownWindow()
    win.show_idle()
    assert win.lbl_time.text() == "--:--" and win.lbl_title.text() == "" and not win.lbl_stopwatch.isVisibleTo(win)
    win.close()
