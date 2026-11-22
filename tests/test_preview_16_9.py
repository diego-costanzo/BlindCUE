"""The single-monitor preview keeps a 16:9 picture; a projector uses all of it."""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "blindcue"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="module")
def output():
    app = QApplication.instance() or QApplication([])  # noqa: F841
    from ui.output_window import OutputWindow
    out = OutputWindow()
    yield out
    out.force_close()


@pytest.mark.parametrize("size, canvas", [
    ((1600, 900), (1600, 900)),   # already 16:9
    ((900, 1000), (900, 506)),    # tall strip (Windows Snap): bars top and bottom
    ((1600, 600), (1067, 600)),   # wide strip: bars left and right
])
def test_preview_canvas_is_16_9(output, size, canvas):
    output._is_external = False
    output.resize(*size)
    assert output._canvas_size() == canvas


def test_projector_uses_the_whole_window(output):
    output._is_external = True
    output.resize(1280, 1024)
    assert output._canvas_size() == (1280, 1024)
    output._is_external = False
