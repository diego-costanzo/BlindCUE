"""Stage 5, item 5.2 (rest): relative changes for several cues, Q labels locked after the script is approved."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "blindcue"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from engine import bulk_change as bc
from models.cue import Cue
from PySide6.QtCore import QCoreApplication, QItemSelectionModel
from PySide6.QtWidgets import QApplication


def _pump(seconds: float = 0.05) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.005)


def _cue(i, **extra):
    data = {"cue_id": 9601 + i, "name": f"b{i}", "media_type": "AUDIO", "file_path": f"/m/b{i}.mp3"}
    data.update(extra)
    return Cue.from_dict(data)


def _show():
    return [_cue(0, volume=1.0, fade_in=1.0, q_label="Q1"),
            _cue(1, volume=0.5, fade_out=2.0, pre_delay=0.5, q_label="Q2"),
            _cue(2, media_type="IMAGE", file_path="/m/p.png", fade_in=0.5),
            _cue(3, media_type="GROUP", file_path="", pre_delay=1.0),
            _cue(4, parent_id=9604, volume=0.8)]


def test_plan_moves_each_cue_by_the_same_step():
    cues = _show()
    steps = bc.plan(cues, [0, 1, 2], {bc.VOLUME_DB: -6.0, "fade_in": 1.5, "fade_out": -5.0})
    got = {(s.row, s.field): s.new for s in steps}
    assert abs(got[(0, "volume")] - 0.5012) < 1e-3 and abs(got[(1, "volume")] - 0.2506) < 1e-3
    assert (2, "volume") not in got                         # a picture has no volume
    assert got[(0, "fade_in")] == 2.5 and got[(2, "fade_in")] == 2.0 and got[(1, "fade_in")] == 1.5
    assert got[(1, "fade_out")] == 0.0 and (0, "fade_out") not in got  # never below 0, 0 - 5 = no change
    up = bc.plan(cues, [0, 1], {bc.VOLUME_DB: 12.0})
    assert [(s.row, s.new) for s in up] == [(1, 1.0)]       # 100 % stays, 50 % +12 dB stops at 100 %
    assert bc.with_scene_cues(cues, [3]) == [3, 4]
    scene = bc.plan(cues, bc.with_scene_cues(cues, [3]), {"pre_delay": 2.0, "fade_in": 1.0})
    assert {(s.row, s.field) for s in scene} == {(3, "pre_delay"), (4, "pre_delay"), (4, "fade_in")}
    assert bc.apply(cues, steps) == 3 and cues[1].fade_out == 0.0


def test_locked_change():
    assert bc.locked_change("Q1", "Q2", True) and bc.locked_change("Q1", "", True)
    assert not bc.locked_change("", "Q5a", True)            # an empty label may still be filled in
    assert not bc.locked_change("Q1", "Q2", False) and not bc.locked_change("Q1", " Q1 ", True)


def test_window_lock_and_bulk_change(tmp_path, monkeypatch):
    QApplication.instance() or QApplication([])
    from ui import bulk_change_dialog
    from ui.main_window import MainWindow, _renumber
    from ui.output_window import OutputWindow

    output = OutputWindow()
    win = MainWindow(output)
    win._clock_timer.stop()
    try:
        win._cues = _show()
        win._refresh_cue_list(keep_selection=False)
        win._reset_undo_history()
        win._cue_list.setCurrentRow(0)
        _pump()
        win._act_q_lock.setChecked(True)
        assert win._q_locked() and win._inspector.edit_cue_q.isReadOnly()
        item = win._cue_list.item(0, 1)
        item.setText("Q9")                                  # an inline edit in the list
        _pump()
        assert win._cues[0].q_label == "Q1" and win._cue_list.item(0, 1).text() == "Q1"
        shown = []
        monkeypatch.setattr(_renumber.QMessageBox, "information", staticmethod(lambda *a, **k: shown.append(a)))
        win._renumber_q()
        assert shown and win._cues[0].q_label == "Q1"
        win._cue_list.setCurrentRow(2)                      # a picture without a label: may get one
        _pump()
        assert not win._inspector.edit_cue_q.isReadOnly()
        show = tmp_path / "Locked.blindcue"
        assert win._do_save(str(show))
        win._show_info_load({})
        assert not win._q_locked() and not win._act_q_lock.isChecked()
        from ui.main_window import _persistence
        monkeypatch.setattr(_persistence.QMessageBox, "warning", staticmethod(lambda *a, **k: None))  # files missing
        win._open_project_file(str(show))
        assert win._q_locked() and win._act_q_lock.isChecked()   # saved with the show

        win._cues = _show()
        win._refresh_cue_list(keep_selection=False)
        win._reset_undo_history()
        win._cue_list.selectRow(0)
        model = win._cue_list.selectionModel()
        model.select(win._cue_list.model().index(1, 0),
                     QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows)
        _pump()
        assert sorted(win._selected_rows()) == [0, 1]

        def accept(dlg):
            dlg.spin_db.setValue(-6.0)
            dlg.spins["pre_delay"].setValue(1.0)
            assert dlg.preview.count() == 4                 # 2 volumes + 2 pre-delays, shown before OK
            return bulk_change_dialog.QDialog.DialogCode.Accepted

        monkeypatch.setattr(bulk_change_dialog.BulkChangeDialog, "exec", accept)
        win._open_bulk_change()
        assert abs(win._cues[0].volume - 0.5012) < 1e-3 and win._cues[1].pre_delay == 1.5
        win._on_undo()                                      # one Ctrl+Z takes it all back
        assert win._cues[0].volume == 1.0 and win._cues[1].pre_delay == 0.5
    finally:
        win._force_closing = True
        output.force_close()
        win.close()
        _pump()
        win.deleteLater()
        output.deleteLater()
        _pump()
