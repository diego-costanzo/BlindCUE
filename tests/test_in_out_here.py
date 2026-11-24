"""3.4 supplement: IN / OUT from where the audition is, in the Edit cue window - one rule with
"IN / OUT Testina" (keys I and O) of the main waveform."""

from __future__ import annotations

import os
import sys
import time
import wave
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "blindcue"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import pytest
from engine.in_out import OUT_END, OUT_MIN, OUT_SET, in_at, out_at
from models.cue import Cue
from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication


def _pump(seconds: float = 0.05) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.005)


def test_one_rule_for_in_and_out():
    assert in_at(1.234, 10.0) == 1.23
    assert in_at(9.99, 10.0) == 9.95                    # never in the last 0.05 s
    assert out_at(5.0, 1.0, 10.0) == (5.0, OUT_SET)
    assert out_at(9.97, 1.0, 10.0) == (None, OUT_END)   # at the end: the end of the file
    assert out_at(0.5, 1.0, 10.0) == (1.05, OUT_MIN)    # before IN: just after it


@pytest.fixture()
def dialog(tmp_path):
    QApplication.instance() or QApplication([])
    from ui.edit_cue_dialog import EditCueDialog

    path = tmp_path / "song.wav"
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(22050)
        out.writeframes(b"\0\0" * 22050 * 2)
    cue = Cue.from_dict({"cue_id": 9701, "name": "song", "media_type": "AUDIO", "file_path": str(path)})
    dlg = EditCueDialog(cue)
    dlg._on_duration(2.0)
    try:
        yield dlg
    finally:
        dlg.reject()
        dlg.deleteLater()
        _pump()


def _key(dlg, key) -> None:
    dlg.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier))


def test_keys_i_and_o_like_on_the_main_waveform(dialog, monkeypatch):
    dialog.btn_play.setFocus()
    monkeypatch.setattr(QApplication, "focusWidget", staticmethod(lambda: dialog.btn_play))
    dialog._waveform.set_playhead_seconds(0.6, 2.0)
    _key(dialog, Qt.Key.Key_I)
    dialog._waveform.set_playhead_seconds(0.3, 2.0)
    _key(dialog, Qt.Key.Key_O)                          # before IN: just after it (not refused)
    assert (dialog._vals["in_point"], dialog._vals["out_point"]) == (0.6, 0.65)
    assert "0.65" in dialog.lbl_status.text()
    monkeypatch.setattr(QApplication, "focusWidget", staticmethod(lambda: dialog.ed_name))
    dialog._waveform.set_playhead_seconds(1.5, 2.0)
    _key(dialog, Qt.Key.Key_O)                          # typing a name: the letter is the name's
    assert dialog._vals["out_point"] == 0.65


def test_while_listening_the_player_position_counts(dialog, monkeypatch):
    monkeypatch.setattr(dialog._player, "is_playing", lambda: True)
    monkeypatch.setattr(dialog._player, "position_seconds", lambda: 1.337)
    dialog._waveform.set_playhead_seconds(1.2, 2.0)     # the head drawn a moment ago
    dialog._in_here()
    assert dialog._vals["in_point"] == 1.34
    monkeypatch.setattr(dialog._player, "position_seconds", lambda: 1.99)
    dialog._out_here()
    assert dialog._vals["out_point"] is None and dialog.lbl_status.text()
