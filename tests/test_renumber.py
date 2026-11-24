"""Stage 5, item 5.2: renumber the Q labels with a preview."""

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

from engine import renumber
from models.cue import Cue
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication, QDialog


def _pump(seconds: float = 0.05) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.005)


def _show() -> list[Cue]:
    def cue(i, **extra):
        data = {"cue_id": 9931 + i, "name": f"c{i}", "media_type": "AUDIO", "file_path": f"/m/{i}.mp3",
                "q_label": f"old{i}"}
        data.update(extra)
        return Cue.from_dict(data)

    return [cue(0), cue(1, media_type="GROUP", file_path=""), cue(2, parent_id=9932), cue(3, adlib=True),
            cue(4), cue(5, enabled=False)]


def test_plan_numbers_go_cues_only():
    cues = _show()
    changes = renumber.plan(cues, start=10, step=10)
    assert [(r, new) for r, _old, new in changes] == [(0, "Q10"), (1, "Q20"), (4, "Q30")]   # scene = one
    assert renumber.plan(cues, chosen=[4], start=5, prefix="")[0] == (4, "old4", "5")
    assert renumber.apply(cues, changes) == 3 and cues[2].q_label == "old2" and cues[3].q_label == "old3"


def test_window_renumbers_with_one_undo(monkeypatch):
    QApplication.instance() or QApplication([])
    from ui.main_window import MainWindow
    from ui.output_window import OutputWindow
    from ui.renumber_dialog import RenumberDialog

    output = OutputWindow()
    win = MainWindow(output)
    win._clock_timer.stop()
    try:
        win._cues = _show()
        win._refresh_cue_list(keep_selection=False)
        win._commit_undo_point()
        monkeypatch.setattr(RenumberDialog, "exec", lambda self: QDialog.DialogCode.Accepted)
        win._renumber_q()
        assert [c.q_label for c in win._cues][:2] == ["Q1", "Q2"]
        win._on_undo()
        assert win._cues[0].q_label == "old0"
    finally:
        win._force_closing = True
        output.force_close()
        win.close()
        _pump()
        win.deleteLater()
        output.deleteLater()
        _pump()
