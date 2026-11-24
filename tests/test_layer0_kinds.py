"""Evaluation #9: the placeholder (Layer 0) is black, a picture, a looping video or the test pattern."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "blindcue"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import pytest
from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication


def _pump(seconds: float = 0.05) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.005)


def _ffmpeg() -> str | None:
    found = shutil.which("ffmpeg")
    if found:
        return found
    local = ROOT / "build" / "ffmpeg" / ("ffmpeg.exe" if sys.platform == "win32" else "ffmpeg")
    return str(local) if local.is_file() else None


def _png(path: Path) -> str:
    img = QImage(64, 36, QImage.Format.Format_RGB32)
    img.fill(QColor("#2266cc"))
    img.save(str(path))
    return str(path)


@pytest.fixture
def win():
    QApplication.instance() or QApplication([])
    from ui.main_window import MainWindow
    from ui.output_window import OutputWindow

    output = OutputWindow()
    window = MainWindow(output)
    window._clock_timer.stop()
    yield window
    window._force_closing = True
    output.force_close()
    window.close()
    _pump()
    window.deleteLater()
    output.deleteLater()
    _pump()


def test_black_by_default_pattern_only_in_preparation(win, tmp_path, monkeypatch):
    from engine.show_mode import REHEARSAL
    from ui.output_window import LAYER0_BLACK
    from ui.tappo_pattern import is_default_tappo_path

    out = win._output
    assert win._layer0_kind == "black" and out.get_layer0_path() == LAYER0_BLACK
    assert win._layer0_settings() == {"layer0_kind": "black"}
    assert win._l0_actions["black"].isChecked()

    win._choose_layer0_kind("pattern")
    assert is_default_tappo_path(out.get_layer0_path()) and win._l0_actions["pattern"].isChecked()
    monkeypatch.setattr(win, "_current_mode", lambda: REHEARSAL)
    win._layer0_follow_mode()                                  # rehearsal / show: never the pattern
    assert out.get_layer0_path() == LAYER0_BLACK and win._layer0_kind == "pattern"
    monkeypatch.undo()
    win._layer0_follow_mode()
    assert is_default_tappo_path(out.get_layer0_path())

    logo = _png(tmp_path / "logo.png")
    win._choose_layer0_kind("image", logo)
    assert out.get_layer0_path() == logo and win._layer0_settings() == {"layer0_kind": "image", "layer0_image": logo}
    assert "logo.png" in win._live_status.lbl_tappo_info.text()
    win._on_reset_layer0()
    assert out.get_layer0_path() == LAYER0_BLACK


def test_old_and_broken_shows_open_without_errors(win, tmp_path):
    from ui.output_window import LAYER0_BLACK

    logo = _png(tmp_path / "logo.png")
    win._restore_layer0({"layer0_image": logo})                        # a show saved before #9
    assert win._layer0_kind == "image" and win._output.get_layer0_path() == logo
    win._restore_layer0({})                                            # no placeholder saved: black
    assert win._layer0_kind == "black" and win._output.get_layer0_path() == LAYER0_BLACK
    win._restore_layer0({"layer0_kind": "video", "layer0_video": str(tmp_path / "gone.mp4")})
    assert win._layer0_kind == "black"                                 # a missing file: black, no error
    win._restore_layer0({"layer0_kind": "nonsense"})
    assert win._layer0_kind == "black"


@pytest.mark.skipif(_ffmpeg() is None, reason="ffmpeg not installed")
def test_looping_video_runs_only_while_it_can_be_seen(tmp_path):
    QApplication.instance() or QApplication([])
    from ui.output_window import LAYER0_BLACK, OutputWindow

    clip = tmp_path / "kurtyna.mp4"
    subprocess.run([_ffmpeg(), "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=320x180:rate=25",
                    "-t", "1", "-pix_fmt", "yuv420p", str(clip)], check=True)
    out = OutputWindow()
    try:
        assert not out.set_layer0_video(str(tmp_path / "gone.mp4"))
        assert out.set_layer0_video(str(clip))
        player, item = out._layer0_video
        assert player.audioOutput() is None                             # the placeholder never sounds
        deadline = time.monotonic() + 5
        while not out.layer0_video_playing() and time.monotonic() < deadline:
            _pump(0.05)
        assert out.layer0_video_playing() and item.isVisible()
        out.show_image(1, _png(tmp_path / "pic.png"))                   # a picture covers it: paused
        _pump(0.2)
        assert not out.layer0_video_playing() and not item.isVisible()
        out.clear_all_layers()
        _pump(0.2)
        assert out.layer0_video_playing() and item.isVisible()
        assert out.set_layer0_image(LAYER0_BLACK) and out._layer0_video is None
    finally:
        out.force_close()
        out.deleteLater()
        _pump()


def test_bundle_takes_the_placeholder_video_along(tmp_path):
    from models.cue import Cue, MediaType
    from models.project_manager import ProjectManager

    pm = ProjectManager(autosave_dir=tmp_path / "cfg")
    clip = tmp_path / "kurtyna.mp4"
    clip.write_bytes(b"mp4")
    show = tmp_path / "pc1" / "show.blindcue"
    show.parent.mkdir()
    cues = [Cue(name="V", media_type=MediaType.VIDEO, file_path=str(clip), layer=1)]
    saved, problems, _copied = pm.save_project_bundled(
        show, cues, settings={"layer0_kind": "video", "layer0_video": str(clip)})
    assert saved and not problems
    data = json.loads(show.read_text(encoding="utf-8"))
    assert data["settings"]["layer0_video"] == "show_media/kurtyna.mp4"
    moved = tmp_path / "pc2"
    shutil.copytree(show.parent, moved)
    _cues, _i, settings = pm.load_project(moved / "show.blindcue")
    assert Path(settings["layer0_video"]) == (moved / "show_media" / "kurtyna.mp4").resolve()
