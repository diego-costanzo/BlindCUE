"""Text cues (captions): rendering, caching and saving in the show."""
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
from PySide6.QtCore import QStandardPaths  # noqa: E402
from PySide6.QtGui import QImage  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from engine.text_render import (  # noqa: E402
    HEIGHT,
    WIDTH,
    normalize_spec,
    render_text_png,
    text_cue_name,
)
from models.cue import Cue, MediaType  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def qt_app():
    # Test mode keeps the caption cache out of the real app data folder.
    QStandardPaths.setTestModeEnabled(True)
    app = QApplication.instance() or QApplication([])
    yield app
    QStandardPaths.setTestModeEnabled(False)


def test_spec_is_completed_and_clamped():
    s = normalize_spec({"text": "Ciao", "size": 5000, "color": "nonsense", "position": "left", "extra": 1})
    assert s["text"] == "Ciao"
    assert s["size"] == 400
    assert s["color"] == "#ffffff"
    assert s["position"] == "bottom"
    assert "extra" not in s


def test_same_settings_give_the_same_image_file():
    spec = {"text": "Atto I\nScena 2", "size": 80, "position": "top"}
    first = render_text_png(spec)
    assert Path(first).name.startswith("caption_")
    assert render_text_png(dict(spec)) == first
    img = QImage(first)
    assert (img.width(), img.height()) == (WIDTH, HEIGHT)
    assert img.hasAlphaChannel()
    assert render_text_png({**spec, "size": 81}) != first


def test_cue_name_uses_the_first_line():
    assert text_cue_name({"text": "Atto I\nScena 2"}) == "📝 Atto I"
    long = text_cue_name({"text": "x" * 80})
    assert long.endswith("…") and len(long) < 45


def test_text_spec_is_saved_and_a_missing_image_is_recreated(tmp_path):
    spec = normalize_spec({"text": "Fine"})
    cue = Cue(name=text_cue_name(spec), media_type=MediaType.IMAGE, file_path=render_text_png(spec))
    cue.text_spec = spec
    cue.layer = 3
    data = cue.to_dict()
    assert data["text_spec"] == spec
    # Another computer: the cached image is not there.
    data["file_path"] = str(tmp_path / "caption_missing.png")
    back = Cue.from_dict(data)
    assert back.text_spec == spec
    assert Path(back.file_path).is_file()
