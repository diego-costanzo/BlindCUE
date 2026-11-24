"""Text cues (captions): rendering, caching and saving in the show."""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "blindcue"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import pytest
from engine.text_render import (
    DEFAULT_FONT,
    HEIGHT,
    WIDTH,
    normalize_spec,
    render_text_png,
    text_cue_name,
)
from models.cue import Cue, MediaType
from PySide6.QtCore import QStandardPaths
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication


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


def test_default_font_is_cross_platform_and_legacy_json_font_is_preserved(tmp_path):
    assert DEFAULT_FONT == "sans-serif"
    assert normalize_spec({"text": "Ciao"})["font"] == "sans-serif"
    assert normalize_spec({"text": "Ciao", "font": ""})["font"] == "sans-serif"
    assert normalize_spec({"text": "Ciao", "font": None})["font"] == "sans-serif"

    # Legacy show saved on Windows with explicit "Segoe UI" must load and render cleanly.
    legacy_spec = {
        "text": "Sipario",
        "size": 90,
        "color": "#ffffff",
        "bold": True,
        "position": "bottom",
        "box": True,
        "shadow": True,
        "font": "Segoe UI",
    }
    legacy_data = {
        "cue_id": 9001,
        "name": "📝 Sipario",
        "media_type": MediaType.IMAGE.value,
        "file_path": str(tmp_path / "old_caption.png"),
        "text_spec": legacy_spec,
    }
    back = Cue.from_dict(legacy_data)
    assert back.text_spec["font"] == "Segoe UI"
    assert Path(back.file_path).is_file()


def test_cache_filename_uses_sha256():
    spec = normalize_spec({"text": "Atto II", "size": 72})
    expected = hashlib.sha256(
        json.dumps(spec, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()[:12]
    path = Path(render_text_png(spec))
    assert path.name == f"caption_{expected}.png"
    assert path.is_file()
