"""Stage 3, item 3.3: playlists - several sounds dropped, .m3u files, sleep / wake of music."""

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
from engine.playlist_import import read_m3u
from models.cue import GroupMode, MediaType
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qt_app():
    app = QApplication.instance() or QApplication([])
    yield app


def _pump(seconds: float = 0.05) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.005)


def test_read_m3u(tmp_path):
    music = tmp_path / "muzyka"
    music.mkdir()
    for name in ("a.mp3", "b.mp3", "zażółć.mp3"):
        (music / name).write_bytes(b"\0")
    lines = ["#EXTM3U", "#EXTINF:123,Artist - A", "muzyka/a.mp3", "", str(music / "b.mp3"),
             (music / "a.mp3").as_uri(), "http://radio.example/stream", "muzyka/gone.mp3", "muzyka/zażółć.mp3"]
    plain = tmp_path / "lista.m3u"
    plain.write_bytes("\r\n".join(lines).encode("cp1250"))       # a Windows player's .m3u
    found, skipped = read_m3u(plain)
    assert [Path(f).name for f in found] == ["a.mp3", "b.mp3", "a.mp3", "zażółć.mp3"]
    assert skipped == ["http://radio.example/stream", "muzyka/gone.mp3"]
    utf8 = tmp_path / "lista.m3u8"
    utf8.write_text("\n".join(lines), encoding="utf-8")
    assert len(read_m3u(utf8)[0]) == 4


@pytest.fixture()
def window(qt_app, tmp_path):
    from ui.main_window import MainWindow
    from ui.output_window import OutputWindow

    output = OutputWindow()
    win = MainWindow(output)
    win._clock_timer.stop()
    win.files = []
    for name in ("one.wav", "two.wav", "three.wav"):
        path = tmp_path / name
        path.write_bytes(b"RIFF")
        win.files.append(str(path))
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


def test_dropped_sounds_become_one_playlist_row(window, monkeypatch):
    monkeypatch.setattr(window, "_ask_playlist", lambda n, answer: answer(True))
    window._on_files_dropped_on_list(window.files, -1)
    group = window._cues[0]
    assert group.media_type == MediaType.GROUP and group.group_mode == GroupMode.SEQUENCE.value
    assert [c.parent_id for c in window._cues[1:]] == [group.cue_id] * 3 and group.collapsed
    assert "3" in group.name


def test_or_separate_cues(window, monkeypatch):
    monkeypatch.setattr(window, "_ask_playlist", lambda n, answer: answer(False))
    window._on_files_dropped_on_list(window.files, -1)
    assert [c.media_type for c in window._cues] == [MediaType.AUDIO] * 3


def test_dropped_m3u(window, tmp_path, monkeypatch):
    monkeypatch.setattr(window, "_ask_playlist", lambda n, answer: pytest.fail("no question for an .m3u"))
    lista = tmp_path / "przerwa.m3u"
    lista.write_text("#EXTM3U\none.wav\ntwo.wav\nmissing.wav\n", encoding="utf-8")
    window._on_files_dropped_on_list([str(lista)], -1)
    assert window._cues[0].name == "przerwa" and len(window._cues) == 3
    assert "1" in window._status_label.text()                     # one entry not found


def test_review_m3u_encodings_and_server_paths(tmp_path, monkeypatch):
    from engine import playlist_import

    (tmp_path / "Perché.mp3").write_bytes(b"\0")
    western = tmp_path / "w.m3u"
    western.write_bytes("Perché.mp3\n".encode("cp1252"))          # written on an Italian / English Windows
    monkeypatch.setattr(playlist_import.locale, "getpreferredencoding", lambda *_a: "cp1250")   # Polish PC
    assert [Path(f).name for f in read_m3u(western)[0]] == ["Perché.mp3"]
    utf16 = tmp_path / "u.m3u"
    utf16.write_bytes("#EXTM3U\r\nPerché.mp3\r\n".encode("utf-16"))
    assert len(read_m3u(utf16)[0]) == 1
    unc = playlist_import._target("file://nas/Multimedia/a%20b.mp3", tmp_path)
    assert str(unc).replace("/", "\\").startswith(r"\\nas\Multimedia") and str(unc).endswith("a b.mp3")
    assert playlist_import._target("sub/../x.mp3", tmp_path) == tmp_path / "x.mp3"


def test_review_playlist_stops_after_its_last_track_and_go_goes_on(window, monkeypatch):
    from engine.show_engine import ShowEngine
    from models.cue import Cue

    monkeypatch.setattr(window, "_ask_playlist", lambda n, answer: answer(True))
    window._on_files_dropped_on_list(window.files[:2], -1)
    window._cues.append(Cue.from_dict({"cue_id": 9921, "name": "act 2", "media_type": "AUDIO",
                                       "file_path": window.files[2]}))
    window._refresh_cue_list(keep_selection=False)
    group, first, last, act2 = window._cues
    assert group.playlist and Cue.from_dict(group.to_dict()).playlist
    assert ShowEngine.auto_follow_target(window._cues, first) == 2       # track 1 -> track 2
    assert ShowEngine.auto_follow_target(window._cues, last) == -1       # then it stops: act 2 waits for GO
    assert not window._hands_over_by_itself(last)
    window._cue_list.setCurrentRow(0)
    window._fire_group_cue(0, group)
    assert window._cue_list.currentRow() == 3                            # the next GO is "act 2"


def test_review_no_playlist_inside_a_scene(window, monkeypatch):
    monkeypatch.setattr(window, "_ask_playlist", lambda n, answer: pytest.fail("no question inside a scene"))
    from models.cue import Cue

    scene = Cue.from_dict({"cue_id": 9931, "name": "scene", "media_type": "GROUP", "file_path": ""})
    child = Cue.from_dict({"cue_id": 9932, "name": "x", "media_type": "AUDIO", "file_path": window.files[0],
                           "parent_id": 9931})
    window._cues = [scene, child]
    window._refresh_cue_list(keep_selection=False)
    window._on_files_dropped_on_list(window.files[1:], 1)
    assert [c.media_type for c in window._cues].count(MediaType.GROUP) == 1   # no nested playlist


def test_dropped_pictures_become_one_scene(window, tmp_path, monkeypatch):
    """5.12: several files that are not only sounds -> one step-by-step scene on request."""
    pictures = []
    for name in ("p1.png", "p2.png"):
        path = tmp_path / name
        path.write_bytes(b"png")
        pictures.append(str(path))
    monkeypatch.setattr(window, "_ask_playlist", lambda n, answer: pytest.fail("no playlist for pictures"))
    monkeypatch.setattr(window, "_ask_scene", lambda n, answer: answer(True))
    window._on_files_dropped_on_list(pictures + window.files[:1], -1)
    group = window._cues[0]
    assert group.media_type == MediaType.GROUP and group.group_mode == GroupMode.STEP.value
    assert [c.parent_id for c in window._cues[1:]] == [group.cue_id] * 3
    window._on_undo()
    assert [c.media_type for c in window._cues] == [MediaType.IMAGE, MediaType.IMAGE, MediaType.AUDIO]
