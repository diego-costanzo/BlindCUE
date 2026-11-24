"""Stage 5, item 5.18: the cheat sheet to print."""

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

from engine.cheat_sheet import to_html
from models.cue import Cue, MediaType
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication


def _pump(seconds: float = 0.05) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.005)


def test_page_layout_escapes_and_skips_empty_sections():
    page = to_html("Show <1>", [("Keys", [("Space", "GO")]), ("Effects", [])], ("Help", ["a & b"]), "foot")
    assert "Show &lt;1&gt;" in page and "a &amp; b" in page and "Effects" not in page and "@page" in page


def test_menu_page_lists_this_show_and_computer(tmp_path, monkeypatch):
    QApplication.instance() or QApplication([])
    from ui.main_window import MainWindow
    from ui.main_window import _cheat_sheet as mod
    from ui.output_window import OutputWindow

    output = OutputWindow()
    win = MainWindow(output)
    win._clock_timer.stop()
    try:
        win._cues = [Cue(name="Dzwonek szkolny", media_type=MediaType.AUDIO, file_path=str(tmp_path / "d.mp3"),
                         adlib=True, hotkey="d"),
                     Cue(name="Muzyka", media_type=MediaType.AUDIO, file_path=str(tmp_path / "m.mp3"))]
        win._key_map = {"go": ["PgDown"], "pause_toggle": []}
        opened = []
        monkeypatch.setattr(mod.QDesktopServices, "openUrl", staticmethod(lambda url: opened.append(url) or True))
        win._open_cheat_sheet()
        page = Path(opened[0].toLocalFile()).read_text(encoding="utf-8")
        assert "Dzwonek szkolny" in page and "<td class='k'>D</td>" in page and "Muzyka" not in page
        assert "PgDown" in page and "PANIC" in page
    finally:
        win._force_closing = True
        output.force_close()
        win.close()
        _pump()
        win.deleteLater()
        output.deleteLater()
        _pump()
