"""View variants Lite / Medium / Full and the 1.12 tidy-ups (stage 1 C2b)."""

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
from models.cue import Cue, MediaType
from PySide6.QtCore import QCoreApplication, QEvent, QSettings, Qt
from PySide6.QtGui import QKeyEvent
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


@pytest.fixture()
def window(qt_app, tmp_path):
    from ui.main_window import MainWindow
    from ui.output_window import OutputWindow

    output = OutputWindow()
    win = MainWindow(output)
    files = {}
    for kind, ext in ((MediaType.AUDIO, "wav"), (MediaType.IMAGE, "png"), (MediaType.VIDEO, "mp4")):
        p = tmp_path / f"x.{ext}"
        p.write_bytes(b"x")
        files[kind] = str(p)
    win._cues = [Cue.from_dict({"cue_id": 9501 + i, "name": f"c{i}", "media_type": k.value,
                                "file_path": files[k]})
                 for i, k in enumerate((MediaType.AUDIO, MediaType.IMAGE, MediaType.VIDEO))]
    win._refresh_cue_list(keep_selection=False)
    win.setWindowState(Qt.WindowState.WindowNoState)   # the 800x600 offscreen screen opens it maximised
    win.resize(1280, 720)
    win.show()
    _pump(0.1)
    try:
        yield win
    finally:
        QSettings("BlindCue", "BlindCue").remove("ui/view_variant")
        win._force_closing = True
        output.force_close()
        win.close()
        _pump()
        win.deleteLater()
        output.deleteLater()
        _pump()


def test_every_start_is_lite_and_full_shows_everything(window):
    assert window._variant == "lite"                         # every start (GUI review 2026-11-24)
    QSettings("BlindCue", "BlindCue").setValue("ui/view_variant", "full")   # an old saved choice: ignored
    from ui.main_window import MainWindow
    from ui.output_window import OutputWindow

    output = OutputWindow()
    second = MainWindow(output)
    try:
        assert second._variant == "lite"
    finally:
        second._force_closing = True
        output.force_close()
        second.close()
    window.apply_view_variant("full")
    _pump(0.05)
    assert window._bottom_splitter.isVisibleTo(window) and window._live_status.isVisibleTo(window)
    assert window._drop_group.isVisibleTo(window) and window._cue_list_panel.link_box.isVisibleTo(window)
    assert not window._inspector.btn_more.isVisibleTo(window)
    assert window._btn_variant.text().startswith("Layout: ")


def test_lite_hides_the_bottom_row_and_widens_the_list(window):
    window.apply_view_variant("full")
    _pump(0.05)
    full_list = window._top_splitter.sizes()[0]
    window.apply_view_variant("lite")
    _pump(0.05)
    assert not window._bottom_splitter.isVisibleTo(window)
    assert not window._cue_list_panel.link_box.isVisibleTo(window)
    assert window._top_splitter.sizes()[0] > full_list
    assert QSettings("BlindCue", "BlindCue").value("ui/view_variant") is None   # not remembered
    assert window._cue_list.hasFocus() or not window.isActiveWindow()


def test_medium_keeps_the_waveform_only(window):
    window.apply_view_variant("medium")
    assert window._bottom_splitter.isVisibleTo(window) and window._waveform_panel.isVisibleTo(window)
    assert not window._live_status.isVisibleTo(window) and not window._drop_group.isVisibleTo(window)


def test_basic_inspector_and_more_settings(window):
    window.apply_view_variant("lite")
    window._cues[0].pre_delay = 3.0
    window._cue_list.setCurrentRow(0)
    _pump(0.05)
    insp = window._inspector
    assert insp.btn_more.isVisibleTo(window) and not insp.spin_pre_delay.isVisibleTo(window)
    assert "3.0" in insp.lbl_also.text() and insp.lbl_also.isVisibleTo(window)
    insp.btn_more.click()                                    # ▾ More settings
    assert insp.spin_pre_delay.isVisibleTo(window) and not insp.lbl_also.isVisibleTo(window)
    assert window._variant == "lite"                         # the window layout does not change


def test_fields_that_do_nothing_for_the_type_are_hidden(window):
    window.apply_view_variant("full")                        # every start is Lite: the full inspector here
    insp = window._inspector
    window._cue_list.setCurrentRow(0)                        # audio
    _pump(0.05)
    assert not insp.tab_widget.isTabVisible(1)               # no picture tab
    assert not insp.spin_crossfade.isVisibleTo(window) and not insp.spin_hold_time.isVisibleTo(window)
    window._cue_list.setCurrentRow(1)                        # picture
    _pump(0.05)
    assert insp.tab_widget.isTabVisible(1) and insp.spin_hold_time.isVisibleTo(window)
    assert not insp._card_of(insp.slider_volume).isVisibleTo(window)
    assert insp.tab_widget.tabText(2).startswith("◐")


def test_enter_presses_the_focused_button_and_tab_leaves_the_list(window):
    assert not window._cue_list.tabKeyNavigation()
    from PySide6.QtWidgets import QPushButton

    pressed: list = []
    btn = QPushButton("probe", window._design_page)
    btn.clicked.connect(lambda: pressed.append(1))
    btn.show()
    btn.setFocus()
    _pump(0.02)
    window.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier))
    assert pressed == [1]
