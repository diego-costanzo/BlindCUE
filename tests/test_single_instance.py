"""One running copy per user: a second launch wakes the first and quits."""
from __future__ import annotations

import os
import subprocess
import sys
import textwrap
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "blindcue"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import pytest  # noqa: E402
from PySide6.QtCore import QCoreApplication  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from services.single_instance import SingleInstance  # noqa: E402


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


def _key() -> str:
    return f"BlindCue-test-{os.getpid()}-{time.monotonic_ns()}"


def test_second_copy_is_refused_until_the_first_quits(qt_app, tmp_path):
    key = _key()
    first = SingleInstance(key, str(tmp_path))
    assert first.acquire()
    second = SingleInstance(key, str(tmp_path))
    assert not second.acquire()
    first.release()
    third = SingleInstance(key, str(tmp_path))
    assert third.acquire()
    third.release()


def test_second_launch_wakes_the_running_copy(qt_app, tmp_path):
    """A second process asks the first to come to the front and gets an answer."""
    key = _key()
    first = SingleInstance(key, str(tmp_path))
    assert first.acquire()
    woken: list[bool] = []
    first.activation_requested.connect(lambda: woken.append(True))

    script = textwrap.dedent(f"""
        import os, sys
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        sys.path.insert(0, {str(APP_DIR)!r})
        from PySide6.QtWidgets import QApplication
        from services.single_instance import SingleInstance
        app = QApplication([])
        other = SingleInstance({key!r}, {str(tmp_path)!r})
        print("acquired" if other.acquire() else "refused")
        print("answered" if other.notify_running(5000) else "silent", flush=True)
    """)
    proc = subprocess.Popen([sys.executable, "-c", script], stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True)
    # The first copy must run its event loop to answer.
    assert _pump_until(lambda: proc.poll() is not None, timeout=20), "second copy hung"
    out, err = proc.communicate()
    first.release()
    assert out.split() == ["refused", "answered"], (out, err)
    assert woken == [True]


def test_a_double_clicked_show_goes_to_the_running_copy(qt_app, tmp_path):
    """5.14: a second launch with a .blindcue file hands the file to the running copy."""
    from services.single_instance import show_file_from_args

    show = tmp_path / "Bajka o smoku.blindcue"
    show.write_text("{}", encoding="utf-8")
    assert show_file_from_args(["BlindCue.exe", "--debug", str(show)]) == str(show)
    assert show_file_from_args(["BlindCue.exe", str(tmp_path / "gone.blindcue")]) is None
    assert show_file_from_args(["BlindCue.exe", str(tmp_path)]) is None
    key = _key()
    first = SingleInstance(key, str(tmp_path))
    assert first.acquire()
    opened: list[str] = []
    first.open_requested.connect(opened.append)
    script = textwrap.dedent(f"""
        import os, sys
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        sys.path.insert(0, {str(APP_DIR)!r})
        from PySide6.QtWidgets import QApplication
        from services.single_instance import SingleInstance
        app = QApplication([])
        other = SingleInstance({key!r}, {str(tmp_path)!r})
        other.acquire()
        print("answered" if other.notify_running(5000, show_file={str(show)!r}) else "silent", flush=True)
    """)
    proc = subprocess.Popen([sys.executable, "-c", script], stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True)
    assert _pump_until(lambda: proc.poll() is not None, timeout=20), "second copy hung"
    out, err = proc.communicate()
    _pump_until(lambda: bool(opened), timeout=2)
    first.release()
    assert out.split() == ["answered"], (out, err)
    assert opened == [str(show)]


def test_open_from_outside_never_replaces_a_running_show(qt_app, tmp_path, monkeypatch):
    from engine.show_mode import SHOW
    from models.cue import Cue, MediaType
    from models.project_manager import ProjectManager
    from ui.main_window import MainWindow
    from ui.output_window import OutputWindow

    show = tmp_path / "inne.blindcue"
    (tmp_path / "d.mp3").write_bytes(b"ID3")   # a missing file would open a warning box
    pm = ProjectManager(autosave_dir=tmp_path / "cfg")
    assert pm.save_project(str(show), [Cue(name="Dzwonek", media_type=MediaType.AUDIO,
                                           file_path=str(tmp_path / "d.mp3"))])
    output = OutputWindow()
    win = MainWindow(output)
    win._clock_timer.stop()
    try:
        monkeypatch.setattr(win, "_current_mode", lambda: SHOW)
        win.open_show_from_outside(str(show))
        assert win._cues == [] and "inne.blindcue" in win._status_label.text()
        monkeypatch.undo()
        monkeypatch.setattr(win, "_confirm_save_if_modified", lambda *a: True)
        win.open_show_from_outside(str(show))
        assert [c.name for c in win._cues] == ["Dzwonek"] and win._current_project_path == str(show)
    finally:
        win._force_closing = True
        output.force_close()
        win.close()
        QCoreApplication.processEvents()
        win.deleteLater()
        output.deleteLater()
        QCoreApplication.processEvents()
