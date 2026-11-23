"""Stage 2, item 2.3: cues on / off and named versions of the show."""

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

import pytest
from engine.show_engine import ShowEngine, chain_indices, outside_go_order
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
    data = {"cue_id": 9701 + i, "name": f"c{i}", "media_type": MediaType.AUDIO.value,
            "file_path": f"/nonexistent/c{i}.wav"}
    data.update(extra)
    return Cue.from_dict(data)


def test_engine_passes_disabled_cues_by():
    off = _cue(1, enabled=False)
    assert not Cue.from_dict(off.to_dict()).enabled and outside_go_order(off)
    cues = [_cue(0, follow_mode="SIMULTANEOUS"), off, _cue(2)]
    assert chain_indices(cues, 0) == [0, 2]
    group = _cue(3, media_type="GROUP", file_path="")
    kids = [_cue(4, parent_id=9704), _cue(5, parent_id=9704, enabled=False)]
    assert [k.cue_id for k in ShowEngine.children_of([group, *kids], 9704)] == [9705]


@pytest.fixture()
def window(qt_app):
    from ui.main_window import MainWindow
    from ui.output_window import OutputWindow

    output = OutputWindow()
    win = MainWindow(output)
    win._cues = [_cue(0, name="a", follow_mode="AUTO_FOLLOW"), _cue(1, name="b"), _cue(2, name="c")]
    win._refresh_cue_list(keep_selection=False)
    win._cue_list.setCurrentRow(0)
    fired: list[int] = []
    win.cue_fired.connect(lambda c: fired.append(c.cue_id))
    win.fired = fired
    try:
        yield win
    finally:
        win._force_closing = True
        output.force_close()
        win.close()
        _pump()
        win.deleteLater()
        output.deleteLater()
        _pump()


def test_switch_off_with_a_warning_and_go_passes_it_by(window):
    window._cue_list.setCurrentRow(1)
    window._toggle_selected_enabled()                          # "b" off: "a" Auto-GOs into it
    assert not window._cues[1].enabled
    assert "Auto-GO" in window._status_label.text() and window._lbl_version.isVisibleTo(window)
    window._cue_list.setCurrentRow(0)
    window._on_go()
    assert window.fired == [9701] and window._cue_list.currentRow() == 2
    window._cue_list.setCurrentRow(1)                          # GO on the disabled row itself
    window._last_go_at = None
    window._on_go()
    assert window.fired[-1] == 9703                            # the next cue that is on
    window._cue_list.setCurrentRow(1)
    window._toggle_selected_enabled()
    assert window._cues[1].enabled


def test_versions_travel_with_the_show(window, monkeypatch):
    from ui.main_window import _versions

    window._cues[2].enabled = False
    monkeypatch.setattr(_versions.QInputDialog, "getText", staticmethod(lambda *a, **k: ("ridotta", True)))
    window._save_version_as()
    assert window._versions == {"ridotta": [9703]} and window._version_name == "ridotta"
    window._switch_version("")
    assert all(c.enabled for c in window._cues)
    window._switch_version("ridotta")
    assert [c.enabled for c in window._cues] == [True, True, False]
    saved = window._versions_settings()
    window._versions_load({})
    assert window._versions == {} and window._version_name == ""
    window._versions_load(saved)
    assert window._version_name == "ridotta" and "ridotta" in window._lbl_version.text()
    window._rebuild_versions_menu()
    names = [a.text() for a in window._versions_menu.actions() if a.text()]
    assert any("ridotta" in n for n in names)


def test_review_group_off_takes_its_items_and_undo_keeps_the_version(window):
    group = _cue(5, name="scene", media_type="GROUP", file_path="")
    kid = _cue(6, name="kid", parent_id=9706)
    window._cues = [window._cues[0], group, kid, window._cues[2]]
    window._refresh_cue_list(keep_selection=False)
    window._cue_list.setCurrentRow(1)
    window._toggle_selected_enabled()
    assert not group.enabled and not kid.enabled                 # the scene with everything inside
    window._version_name, window._versions = "short", {"short": []}
    window._refresh_cue_list(keep_selection=True)
    assert set(window._versions["short"]) == {9706, 9707}        # the version follows the list (Undo too)
