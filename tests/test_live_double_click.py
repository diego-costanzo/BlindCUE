"""A double-click on the LIVE list arms the cue instead of starting it."""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "blindcue"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qt_app():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture()
def panel(qt_app):
    from ui.live_show_view import LiveShowPanel

    p = LiveShowPanel()
    got: dict[str, list[int]] = {"armed": [], "clicked": [], "fire": [], "forced": []}
    p.double_click_armed.connect(got["armed"].append)
    p.force_row_requested.connect(got["forced"].append)
    p.cue_row_clicked.connect(got["clicked"].append)
    p.cue_row_double_clicked.connect(got["fire"].append)
    p._got = got
    yield p
    p.deleteLater()


def test_double_click_arms_by_default(panel):
    panel._on_table_double_clicked(2, 1)
    assert panel._got == {"armed": [2], "clicked": [2], "fire": [], "forced": []}


def test_double_click_fires_when_opted_in(panel):
    from ui.live_show_view import DOUBLE_CLICK_FIRES_KEY

    settings = QSettings("BlindCue", "BlindCue")
    try:
        settings.setValue(DOUBLE_CLICK_FIRES_KEY, True)
        panel._on_table_double_clicked(1, 0)
    finally:
        settings.remove(DOUBLE_CLICK_FIRES_KEY)
    assert panel._got["fire"] == [1]
    assert panel._got["armed"] == []


def test_context_menu_force_go_is_its_own_signal(panel):
    panel.live_table.fire_row_requested.emit(3)
    assert panel._got["forced"] == [3]
    assert panel._got["fire"] == []


def test_double_click_ignored_while_table_refreshes(panel):
    panel._updating_table = True
    panel._on_table_double_clicked(1, 0)
    panel._updating_table = False
    assert panel._got["armed"] == [] and panel._got["fire"] == []
