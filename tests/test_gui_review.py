"""GUI review of 2026-11-24: alarm bar, what plays in Preparation, test pattern, empty columns, Edit zoom."""
from __future__ import annotations

import math
import os
import struct
import sys
import time
import wave
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "blindcue"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import numpy as np  # noqa: E402
import pytest  # noqa: E402
from models.cue import Cue, MediaType  # noqa: E402
from PySide6.QtCore import QCoreApplication, Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402


def _pump(seconds: float = 0.05) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.005)


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def window(qt_app, tmp_path):
    from ui.main_window import MainWindow
    from ui.output_window import OutputWindow

    output = OutputWindow()
    win = MainWindow(output)
    clip = tmp_path / "x.wav"
    clip.write_bytes(b"x")
    win._cues = [Cue.from_dict({"cue_id": 9701 + i, "name": f"g{i}", "media_type": "AUDIO",
                                "file_path": str(clip)}) for i in range(2)]
    win._refresh_cue_list(keep_selection=False)
    win.setWindowState(Qt.WindowState.WindowNoState)
    win.resize(1280, 720)
    win.show()
    _pump(0.1)
    try:
        yield win
    finally:
        win._force_closing = True
        output.force_close()
        win.close()
        _pump()


def test_alarm_bar_keeps_warnings_until_the_cause_is_gone(qt_app):
    from ui.alarm_bar import AlarmBar

    bar = AlarmBar()
    seen: list[str] = []
    bar.changed.connect(seen.append)
    bar.set_alarm("speakers", "Speakers unplugged")
    assert not bar.isHidden() and "Speakers unplugged" in bar.lbl.text()
    bar.set_alarm("mute", "All muted")
    assert "Speakers unplugged" in bar.lbl.text() and "All muted" in bar.lbl.text()
    bar.btn_hide.click()                                     # hidden until something changes
    assert bar.isHidden()
    bar.set_alarm("mute", "")                                # one cause gone: nothing new to show
    assert bar.isHidden()
    bar.set_alarm("load", "Projector overloaded")            # a new warning comes back alone
    assert not bar.isHidden() and bar.lbl.text() == "⚠ Projector overloaded"
    bar.set_alarm("load", None)
    bar.set_alarm("speakers", "")
    assert bar.isHidden() and bar.alarms() == {}
    assert seen and seen[-1] == ""


def test_mute_and_unplugged_speakers_go_to_the_alarm_bar(window):
    window._set_master(muted=True)
    assert "mute" in window._alarm_bar.alarms() and not window._alarm_bar.isHidden()
    window._set_master(muted=False)
    assert "mute" not in window._alarm_bar.alarms()
    window._on_audio_notice("Speakers 'HDMI' not connected")
    assert window._alarm_bar.alarms().get("speakers") == "Speakers 'HDMI' not connected"
    window._on_audio_notice("")
    assert "speakers" not in window._alarm_bar.alarms() and window._alarm_bar.isHidden()
    window.set_performance_hint("Projector overloaded")
    assert window._alarm_bar.alarms().get("load") == "Projector overloaded"
    assert window._lbl_perf_hint.isHidden()                  # not on the status bar any more
    window.set_performance_hint(None)
    assert window._alarm_bar.isHidden()


def test_what_plays_shows_above_the_go_in_preparation_only(window):
    from ui.now_playing import NOTE, TIMED, CardState

    strip = window._prep_now_playing
    assert strip.isHidden()                                  # nothing plays: no strip
    states = [CardState(9701, TIMED, "♪ #1 'g0'", "L2", remaining="-01:00", fraction=0.5, slot=2),
              CardState(9799, NOTE, "📝 note")]
    strip.set_cards(states)
    assert not strip.isHidden() and list(strip.cards()) == [9701]   # notes stay in the show
    card = strip.cards()[9701]
    assert card._compact and card.btn_fade_small.isVisibleTo(strip)
    faded: list[int] = []
    window.card_fade_requested.connect(faded.append)
    card.btn_fade_small.click()                              # the same request as the show's card
    assert faded == [2]
    strip.set_cards([])
    assert strip.isHidden()
    window._cues[0].status = __import__("models.cue", fromlist=["CueStatus"]).CueStatus.LIVE
    window._live_mode = True
    window._refresh_now_playing()
    assert strip.isHidden()                                  # in the show the right column has them
    window._live_mode = False


def test_test_pattern_on_the_readiness_page(window):
    from engine.readiness import OK, SCREEN, Check

    view = window._readiness_view(Check(SCREEN, OK, {"name": "Projector (screen 2)"}))
    assert [action for _label, action in view.buttons] == ["pattern"]
    off_label = view.buttons[0][0]
    assert not window._output.is_calibration_guides_visible()
    window._on_readiness_action("pattern")
    assert window._output.is_calibration_guides_visible()
    on_view = window._readiness_view(Check(SCREEN, OK, {"name": "Projector (screen 2)"}))
    assert on_view.buttons[0][0] != off_label                # the button now hides it
    window._on_readiness_start(0)                            # never in front of the audience
    assert not window._output.is_calibration_guides_visible()
    window.set_live_mode(False)


def test_empty_number_column_is_hidden(window):
    assert window._cue_list.isColumnHidden(1)
    window._cues[1].q_label = "12a"
    window._refresh_cue_list()
    assert not window._cue_list.isColumnHidden(1)


def test_hardware_label_left_the_status_bar(window):
    assert window._lbl_hw_info.isHidden()
    window.apply_view_variant("full")
    assert window._lbl_hw_info.isHidden()                    # Help → Hardware info has it


def _wav(path: Path, seconds: float = 6.0) -> str:
    rate = 8000
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(rate)
        out.writeframes(b"".join(struct.pack("<h", int(6000 * math.sin(i / 7.0))) for i in range(rate * int(seconds))))
    return str(path)


def test_edit_window_zooms_on_a_short_piece(qt_app, tmp_path):
    from ui.edit_cue_dialog import EditCueDialog

    cue = Cue.from_dict({"cue_id": 9801, "name": "long", "media_type": "AUDIO",
                         "file_path": _wav(tmp_path / "long.wav"), "in_point": 2.0, "out_point": 2.5})
    dlg = EditCueDialog(cue, peaks_provider=lambda: np.full(300, 0.5))
    try:
        dlg._on_duration(6.0)
        dlg._waveform.set_in_out_seconds(2.0, 2.5, 6.0)
        dlg.btn_clip_view.setChecked(True)
        wf = dlg._waveform
        assert wf.zoom_factor() > 4 and wf.view_start_sec() <= 2.0 <= 2.5 <= wf.view_start_sec() + wf.view_span_sec()
        dlg.btn_clip_view.setChecked(False)
        assert wf.zoom_factor() == 1.0
    finally:
        dlg.close()
        dlg.deleteLater()
        _pump()
