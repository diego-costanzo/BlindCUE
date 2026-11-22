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

