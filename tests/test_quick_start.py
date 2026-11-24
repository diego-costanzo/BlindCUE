"""Stage 5, item 5.9: new show from a folder, a cue list from a spreadsheet, pinned shows."""

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
from engine.quick_start import media_in_folder, natural_key, read_skeleton, resolve_file
from models.cue import CueStatus, MediaType
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication


def _pump(seconds: float = 0.05) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.005)


def test_natural_order_of_a_folder(tmp_path):
    for name in ("Scena 10.jpg", "scena 2.jpg", "Scena 1.jpg", "notes.txt", ".hidden.jpg"):
        (tmp_path / name).write_bytes(b"x")
    (tmp_path / "sub").mkdir()
    files = media_in_folder(tmp_path, lambda p: p.endswith(".jpg"))
    assert [Path(f).name for f in files] == ["Scena 1.jpg", "scena 2.jpg", "Scena 10.jpg"]
    assert natural_key("a2") < natural_key("A10")
    assert media_in_folder(tmp_path / "none", lambda p: True) == []


def test_skeleton_in_polish_excel_and_our_own_export(tmp_path):
    (tmp_path / "bell.wav").write_bytes(b"RIFF")
    pl = tmp_path / "lista.csv"
    pl.write_bytes("Q;Nazwa;Plik;Strona;Kwestia;Uwagi\nQ1;Dzwonek;bell.wav;3;…i wtedy;cicho\n;Muzyka;;;;\n;;;;;\n"
                   .encode("cp1250", errors="replace"))
    rows = read_skeleton(pl)
    assert [r["name"] for r in rows] == ["Dzwonek", "Muzyka"]
    assert rows[0]["q"] == "Q1" and rows[0]["page"] == "3" and rows[0]["notes"] == "cicho"
    assert resolve_file(rows[0]["file"], pl) == str((tmp_path / "bell.wav").resolve())
    en = tmp_path / "list.csv"
    en.write_text("#,Q,Name,Type,File\n1,Q5,Intro,VIDEO,\n", encoding="utf-8-sig")
    assert read_skeleton(en)[0] == {"q": "Q5", "name": "Intro", "type": "VIDEO", "file": "", "page": "",
                                    "line": "", "notes": ""}
    bad = tmp_path / "bad.csv"
    bad.write_text("a;b\n1;2\n", encoding="utf-8")
    with pytest.raises(ValueError):
        read_skeleton(bad)


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


def test_new_show_from_a_folder_as_a_scene(win, tmp_path, monkeypatch):
    from ui.main_window import _quick_start

    for name in ("2.png", "10.png", "1.png"):
        (tmp_path / name).write_bytes(b"png")
    monkeypatch.setattr(_quick_start.QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: str(tmp_path)))
    monkeypatch.setattr(win, "_ask_folder_layout", lambda count, sounds: True)
    monkeypatch.setattr(win, "_confirm_save_if_modified", lambda *a: True)
    win._new_show_from_folder()
    names = [c.name for c in win._cues]
    assert names[2:] == ["1.png", "2.png", "10.png"] and win._cues[1].media_type == MediaType.GROUP
    assert all(c.parent_id == win._cues[1].cue_id for c in win._cues[2:])
    monkeypatch.setattr(win, "_ask_folder_layout", lambda count, sounds: None)   # cancelled: nothing changes
    win._new_show_from_folder()
    assert [c.name for c in win._cues] == names


def test_import_a_cue_list_and_pin_the_show(win, tmp_path, monkeypatch):
    from ui.main_window import _quick_start

    (tmp_path / "bell.wav").write_bytes(b"RIFF")
    csv_file = tmp_path / "lista.csv"
    csv_file.write_text("Q;Nazwa;Plik;Typ\nQ1;Dzwonek;bell.wav;\nQ2;Film;;VIDEO\n", encoding="utf-8-sig")
    monkeypatch.setattr(_quick_start.QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(csv_file), "")))
    before = len(win._cues)
    win._import_skeleton()
    bell, film = win._cues[before:before + 2]
    assert (bell.q_label, bell.media_type, bell.status) == ("Q1", MediaType.AUDIO, CueStatus.LOADED)
    assert (film.media_type, film.status, film.file_path) == (MediaType.VIDEO, CueStatus.OFFLINE, "")
    win._on_undo()
    assert len(win._cues) == before
    show = tmp_path / "pinned.blindcue"
    assert win._do_save(str(show))
    win._current_project_path = str(show)
    win._toggle_pin_current()
    assert win._recent_key(str(show)) in win._pinned_projects()
    win._rebuild_recent_menu()
    texts = [a.text() for a in win._recent_menu.actions()]
    assert texts[0].startswith("1. 📌 pinned")
    win._toggle_pin_current()
    assert win._pinned_projects() == []
