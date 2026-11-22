"""Crossfade between cues on the same layer."""
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
from PySide6.QtCore import QCoreApplication  # noqa: E402
from PySide6.QtGui import QColor, QPixmap  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from models.cue import Cue, MediaType  # noqa: E402


@pytest.fixture(scope="module")
def qt_app():
    app = QApplication.instance() or QApplication([])
    yield app


def _pump_until(predicate, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        QCoreApplication.processEvents()
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


def test_crossfade_is_saved_and_never_negative():
    cue = Cue(name="a", media_type=MediaType.IMAGE, file_path="a.png")
    assert cue.crossfade == 0.0
    cue.crossfade = 1.25
    assert Cue.from_dict(cue.to_dict()).crossfade == 1.25
    data = cue.to_dict()
    data["crossfade"] = -3
    assert Cue.from_dict(data).crossfade == 0.0
    del data["crossfade"]  # shows saved before the field existed
    assert Cue.from_dict(data).crossfade == 0.0


def test_snapshot_dissolves_and_is_removed(qt_app, tmp_path):
    from ui.output_window import OutputWindow

    img = tmp_path / "red.png"
    pm = QPixmap(320, 180)
    pm.fill(QColor("red"))
    pm.save(str(img))

    out = OutputWindow()
    out.resize(640, 360)
    out.show()
    try:
        out.show_image(1, str(img))
        _pump_until(lambda: False, 0.2)
        out.begin_crossfade(1, 0.3)
        ghost = out._xfade_ghosts.get(1)
        assert ghost is not None and ghost.opacity() == 1.0
        assert _pump_until(lambda: 1 not in out._xfade_ghosts, 3.0), "snapshot not removed"
        # Nothing on the layer: nothing to dissolve.
        out.clear_layer(1)
        out.begin_crossfade(1, 0.3)
        assert 1 not in out._xfade_ghosts
    finally:
        out.force_close()
