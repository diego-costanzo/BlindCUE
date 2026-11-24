"""Stage 1 C2b, P2 / W73: Edit → Add has every button of the add bar (keyboard and screen reader)."""

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

import pytest  # noqa: E402
from models.cue import ACTION_NOTE, MediaType  # noqa: E402
from PySide6.QtCore import QCoreApplication  # noqa: E402
from PySide6.QtGui import QAction  # noqa: E402
from PySide6.QtWidgets import QApplication, QMenu  # noqa: E402


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
def window(qt_app):
    from ui.main_window import MainWindow
    from ui.output_window import OutputWindow

    output = OutputWindow()
    win = MainWindow(output)
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


def _add_menu(win) -> QMenu:
    return next(m for m in win.findChildren(QMenu) if m.title() == "➕ Aggiungi")


def test_edit_add_menu_sends_what_the_add_bar_sends(window):
    from ui.cue_list_panel import ADD_ACTIONS

    menu = _add_menu(window)
    entries = {a.text(): a for a in menu.actions() if not a.isSeparator()}
    assert set(entries) == {"＋ Aggiungi file…", "+ Testo", "+ Gruppo", "+ Azione"}
    panel = window._cue_list_panel
    sent: list = []
    for signal in (panel.add_media_requested, panel.add_text_requested, panel.add_group_requested):
        signal.disconnect()                                     # no file or edit windows in a test
    panel.add_media_requested.connect(lambda kind: sent.append(("media", kind)))
    panel.add_text_requested.connect(lambda: sent.append(("text", None)))
    panel.add_group_requested.connect(lambda: sent.append(("group", None)))
    for text in ("＋ Aggiungi file…", "+ Testo", "+ Gruppo"):
        entries[text].trigger()
    assert sent == [("media", None), ("text", None), ("group", None)]
    actions = [a for a in entries["+ Azione"].menu().actions() if isinstance(a, QAction)]
    assert [a.text() for a in actions] == [label for _kind, label in ADD_ACTIONS]
    note = next(a for a, (kind, _l) in zip(actions, ADD_ACTIONS, strict=True) if kind == ACTION_NOTE)
    note.trigger()                                              # the real path: a note cue is added
    assert len(window._cues) == 1 and window._cues[0].media_type == MediaType.ACTION
    assert window._cues[0].action_spec["kind"] == ACTION_NOTE
