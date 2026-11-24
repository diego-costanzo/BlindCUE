"""Stage 5, items 5.7 and 5.8: extra keys and a presenter remote."""

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

from engine import key_map as km
from models.cue import Cue
from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication


def _pump(seconds: float = 0.05) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.005)


def test_map_text_lookup_and_conflicts():
    raw = {"go": ["PgDown", "PgDown", " "], "bogus": ["X"], "pause_toggle": "B"}
    assert km.clean(raw) == {"go": ["PgDown"]}
    assert km.from_text(km.to_text(km.PRESENTER)) == km.PRESENTER
    assert km.from_text("not json") == {}
    assert km.lookup({"go": ["PgDown"], "prev_cue": ["PgDown", "PgUp"]}) == {"PgDown": "go", "PgUp": "prev_cue"}
    found = km.conflicts({"go": ["Space", "B"], "pause_toggle": ["B"], "fade_all": ["Q"]}, effect_keys=["q"])
    assert ("Space", "reserved", "GO") in found
    assert ("B", "twice", "pause_toggle") in found
    assert ("Q", "effect", "fade_all") in found
    assert km.conflicts(km.PRESENTER) == []


def _press(widget, key, text=""):
    for kind in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
        QApplication.sendEvent(widget, QKeyEvent(kind, key, Qt.KeyboardModifier.NoModifier, text))


def test_window_runs_mapped_keys_only_in_the_show(monkeypatch):
    QApplication.instance() or QApplication([])
    from ui.main_window import MainWindow
    from ui.output_window import OutputWindow

    output = OutputWindow()
    win = MainWindow(output)
    win._clock_timer.stop()
    try:
        win._cues = [Cue.from_dict({"cue_id": 9501 + i, "name": f"k{i}", "media_type": "IMAGE",
                                    "file_path": "/x.png"}) for i in range(3)]
        win._refresh_cue_list(keep_selection=False)
        ran = []
        monkeypatch.setattr(win, "_run_key_function", ran.append)
        monkeypatch.setattr(win, "isActiveWindow", lambda: True)
        monkeypatch.setattr(win, "_readiness_visible", lambda: False)
        monkeypatch.setattr(win, "_is_text_input_focused", lambda: False)
        # A dialog left open by an earlier test in this process would (rightly) keep the keys away.
        monkeypatch.setattr(QApplication, "activeModalWidget", staticmethod(lambda: None))
        monkeypatch.setattr(QApplication, "activePopupWidget", staticmethod(lambda: None))
        win._keymap_store({})                       # nothing mapped: the filter is not even installed
        assert not win._key_filter_installed
        win._key_map = dict(km.PRESENTER)
        win._keymap_apply()
        assert win._key_filter_installed
        target = win._cue_list
        win._live_mode = False
        _press(target, Qt.Key.Key_PageDown)
        assert ran == []                            # Preparation: Page Down is the list's
        win._live_mode = True
        _press(target, Qt.Key.Key_PageDown)
        _press(target, Qt.Key.Key_B, "b")
        assert ran == [km.GO, km.PAUSE]
        win._hotkey_map = {"B": [9501]}             # an effect of the show has B: the effect wins
        _press(target, Qt.Key.Key_B, "b")
        assert ran == [km.GO, km.PAUSE]
    finally:
        win._live_mode = False
        win._keymap_store({})
        win._force_closing = True
        output.force_close()
        win.close()
        _pump()
        win.deleteLater()
        output.deleteLater()
        _pump()


def test_dialog_profile_capture_and_store(monkeypatch):
    QApplication.instance() or QApplication([])
    from ui import key_map_dialog as kd

    dlg = kd.KeyMapDialog({}, ["Q"])
    try:
        dlg._set_map(km.PRESENTER)
        assert dlg.key_map() == km.PRESENTER and dlg.lbl_conflicts.text() == ""
        dlg._add_key(km.FADE_ALL, "Q")
        assert "Q" in dlg.lbl_conflicts.text()     # the effect's key is pointed out
        cap = kd.KeyCaptureDialog("press")
        _press(cap, Qt.Key.Key_PageDown)
        assert cap.captured == "PgDown" and cap.result() == kd.QDialog.DialogCode.Accepted
        answers = iter([("PgDown", 1), ("", kd.SKIP), ("B", 1)])

        def fake_exec(self):
            key, code = next(answers)
            self.captured = key
            return code

        monkeypatch.setattr(kd.KeyCaptureDialog, "exec", fake_exec)
        dlg._set_map({})
        dlg._wizard()
        assert dlg.key_map() == {km.GO: ["PgDown"], km.PAUSE: ["B"]}
    finally:
        dlg.close()
        _pump()
