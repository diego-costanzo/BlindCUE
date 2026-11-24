"""Evaluation 2026-11-24: the "Edit cue" window (double-click / Enter / ✏ in every view)."""

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

import numpy as np
from models.cue import Cue
from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication


def _pump(seconds: float = 0.05) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.005)


def _wav(path: Path, seconds: float = 2.0) -> str:
    rate = 22050
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(rate)
        frames = b"".join(struct.pack("<h", int(8000 * math.sin(i / 10.0))) for i in range(int(rate * seconds)))
        out.writeframes(frames)
    return str(path)


def _cue(i, **extra):
    data = {"cue_id": 9601 + i, "name": f"e{i}", "media_type": "AUDIO", "file_path": f"/m/{i}.mp3"}
    data.update(extra)
    return Cue.from_dict(data)


def test_sound_cue_fields_and_points(tmp_path):
    QApplication.instance() or QApplication([])
    from ui.edit_cue_dialog import EditCueDialog

    cue = _cue(0, file_path=_wav(tmp_path / "song.wav"), fade_out=1.0)
    peaks = np.concatenate([np.zeros(40), np.full(120, 0.8), np.zeros(40)])
    dlg = EditCueDialog(cue, peaks_provider=lambda: peaks)
    try:
        assert dlg.changes() == {}
        assert dlg._waveform is not None and not dlg.lbl_wave.isVisible()   # peaks were there at once
        dlg._on_duration(2.0)                                                 # what the player reports
        dlg.sp_in.setValue(0.25)
        dlg.sp_out.setValue(1.5)
        dlg._apply_out(0.1)                                                   # before the start: refused
        assert dlg._vals["out_point"] == 1.5 and dlg.lbl_status.text()
        dlg.sl_volume.setValue(50)
        dlg.sp_fade_in.setValue(0.5)
        dlg.sp_crossfade.setValue(2.0)
        dlg.cb_loop.setChecked(True)
        dlg.ed_name.setText("  Walc  ")
        assert dlg.changes() == {"name": "Walc", "in_point": 0.25, "out_point": 1.5, "volume": 0.5,
                                 "fade_in": 0.5, "crossfade": 2.0, "loop": True}
        dlg._trim_silence()                                                   # 0.4 s … 1.6 s of sound, minus a margin
        assert 0.0 < dlg._vals["in_point"] < 0.45 and 1.5 < (dlg._vals["out_point"] or 2.0) <= 2.0
        dlg._whole_file()
        assert dlg._vals["in_point"] == 0.0 and dlg._vals["out_point"] is None
        assert dlg.sp_in.value() == 0.0 and dlg.sp_out.value() == 0.0
        dlg._waveform.set_playhead_seconds(0.8, 2.0)
        dlg._in_here()
        dlg._waveform.set_playhead_seconds(1.2, 2.0)
        dlg._out_here()
        assert (dlg._vals["in_point"], dlg._vals["out_point"]) == (0.8, 1.2)
        assert cue.in_point == 0.0 and cue.name == "e0"                       # the cue itself is untouched
    finally:
        dlg.reject()
        dlg.deleteLater()
        _pump()


def test_picture_scene_and_text(tmp_path):
    QApplication.instance() or QApplication([])
    from ui.edit_cue_dialog import EditCueDialog

    pic = _cue(1, media_type="IMAGE", file_path=str(tmp_path / "none.png"))
    dlg = EditCueDialog(pic)
    assert dlg._waveform is None and dlg.lbl_picture.text()                  # missing file said, no crash
    dlg.sp_hold.setValue(8.0)
    dlg.sl_scale.setValue(150)
    dlg.sp_x.setValue(0.25)
    assert dlg.changes() == {"hold_time": 8.0, "scale": 1.5, "position_x": 0.25}
    dlg.btn_center.click()
    assert dlg.changes() == {"hold_time": 8.0}
    dlg.reject()

    scene = _cue(2, media_type="GROUP", file_path="", group_mode="STEP")
    dlg = EditCueDialog(scene)
    dlg.cb_group_mode.setCurrentIndex(dlg.cb_group_mode.findData("SEQUENCE"))
    assert dlg.changes() == {"group_mode": "SEQUENCE"} and dlg.lbl_group_desc.text()
    dlg.reject()

    spec = {"text": "Akt I", "size": 80}
    caption = _cue(3, media_type="IMAGE", file_path=str(tmp_path / "t.png"), text_spec=dict(spec))
    new_spec = dict(spec, text="Akt II")
    dlg = EditCueDialog(caption, edit_text=lambda old: new_spec if old == spec else None)
    dlg.btn_text.click()
    assert dlg.changes() == {"text_spec": new_spec}
    dlg.reject()
    _pump()


def test_window_opens_it_everywhere_and_saves_one_step(tmp_path, monkeypatch):
    QApplication.instance() or QApplication([])
    from engine.show_mode import SHOW
    from ui import edit_cue_dialog
    from ui.main_window import MainWindow
    from ui.output_window import OutputWindow

    output = OutputWindow()
    win = MainWindow(output)
    win._clock_timer.stop()
    try:
        win._cues = [_cue(i, file_path=str(tmp_path / f"{i}.mp3")) for i in range(2)]
        win._refresh_cue_list(keep_selection=False)
        win._reset_undo_history()
        win._cue_list.setCurrentCell(1, 2)
        opened = []

        def fake_exec(self):
            opened.append(self._cue.cue_id)
            self.sp_fade_in.setValue(1.5)
            self.ed_name.setText("Burza")
            return edit_cue_dialog.QDialog.DialogCode.Accepted

        monkeypatch.setattr(edit_cue_dialog.EditCueDialog, "exec", fake_exec)
        win._on_cue_cell_double_clicked(1, 2)                                 # double-click on the name
        assert opened == [9602] and win._cues[1].fade_in == 1.5 and win._cues[1].name == "Burza"
        assert win._inspector.spin_fade_in.value() == 1.5                     # the inspector shows it too
        win._on_undo()                                                        # one step for the whole window
        assert win._cues[1].fade_in == 0.0 and win._cues[1].name == "e1"

        win._cue_list.setCurrentCell(0, 2)
        win._cue_list.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier))
        win._cue_list_panel.btn_edit_cue.click()
        assert opened[1:] == [9601, 9601]

        monkeypatch.setattr(edit_cue_dialog.EditCueDialog, "exec",
                            lambda self: edit_cue_dialog.QDialog.DialogCode.Rejected)
        win._cues[0].fade_in = 0.0
        assert win._open_cue_editor(0) is False                               # Cancel changes nothing

        def scene_exec(self):                                                 # #12: a new scene asks how it plays
            self.ed_name.setText("Akt I")
            self.cb_group_mode.setCurrentIndex(self.cb_group_mode.findData("SIMULTANEOUS"))
            return edit_cue_dialog.QDialog.DialogCode.Accepted

        monkeypatch.setattr(edit_cue_dialog.EditCueDialog, "exec", scene_exec)
        win._cue_list.setCurrentCell(1, 2)
        win._cue_list_panel.btn_add_group.click()
        scene = next(c for c in win._cues if c.media_type.name == "GROUP")
        assert (scene.name, scene.group_mode) == ("Akt I", "SIMULTANEOUS")

        monkeypatch.setattr(win, "_current_mode", lambda: SHOW)
        before = len(opened)
        assert win._open_cue_editor(0) is False and len(opened) == before    # not during the show
    finally:
        win._force_closing = True
        output.force_close()
        win.close()
        _pump()
        win.deleteLater()
        output.deleteLater()
        _pump()
