"""Stage 5, item 5.17: the practice show (built-in media, every kind of cue)."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "blindcue"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from engine.practice_show import MEDIA_FILES, practice_cues
from engine.show_engine import outside_go_order
from models.cue import MediaType
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication
from ui.theme import ASSETS_DIR


def _pump(seconds: float = 0.05) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.005)


def test_every_kind_of_cue_on_the_built_in_media(tmp_path):
    media = ASSETS_DIR / "practice"
    assert all((media / name).is_file() and (media / name).stat().st_size < 400_000 for name in MEDIA_FILES)
    rendered = []
    (tmp_path / "c.png").write_bytes(b"png")
    cues = practice_cues(media, lambda spec: rendered.append(spec["text"]) or str(tmp_path / "c.png"))
    kinds = {c.media_type for c in cues}
    assert kinds == {MediaType.ACTION, MediaType.AUDIO, MediaType.IMAGE, MediaType.VIDEO, MediaType.GROUP}
    assert len(rendered) == 3 and all(not c.validate() for c in cues)
    scene = next(c for c in cues if c.media_type == MediaType.GROUP)
    assert [c.name for c in cues if c.parent_id == scene.cue_id] == ["Sfondo: il castello", "📝 Atto II – Il castello"]
    bell = next(c for c in cues if c.hotkey == "D")
    assert outside_go_order(bell)                                        # an effect on a key, not a GO
    assert all(Path(c.file_path).is_file() for c in cues if c.media_type in (MediaType.AUDIO, MediaType.VIDEO))


def test_menu_makes_and_saves_it(monkeypatch):
    QApplication.instance() or QApplication([])
    from ui.main_window import MainWindow
    from ui.output_window import OutputWindow

    output = OutputWindow()
    win = MainWindow(output)
    win._clock_timer.stop()
    try:
        monkeypatch.setattr(win, "_confirm_save_if_modified", lambda *a: True)
        assert win._open_practice_show()
        path = Path(win._current_project_path)
        assert path.is_file() and len(win._cues) == 12 and not win._is_modified
        assert {p.name for p in (path.parent / "media").iterdir()} >= set(MEDIA_FILES)
        data = json.loads(path.read_text(encoding="utf-8"))
        assert len(data["cues"]) == 12
        # opened again it never overwrites a copy the teacher changed
        (path.parent / "media" / "bell.mp3").write_bytes(b"changed")
        assert win._open_practice_show()
        assert (path.parent / "media" / "bell.mp3").read_bytes() == b"changed"
    finally:
        win._force_closing = True
        output.force_close()
        win.close()
        _pump()
        win.deleteLater()
        output.deleteLater()
        _pump()
