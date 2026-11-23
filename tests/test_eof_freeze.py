"""Regression: the app froze for good when an audio cue played to its end.

At EndOfMedia the live player paused the deck and the EOF handler then called
``stop()``. The pause makes the Qt FFmpeg backend rebuild its renderers on a
worker thread; ``stop()`` blocks the GIL-holding main thread on that worker,
which waits for the GIL to destroy a PySide-wrapped object (seen 2026-11-21).

Run:
    QT_QPA_PLATFORM=offscreen pytest -q tests/test_eof_freeze.py
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest
from PySide6.QtMultimedia import QMediaDevices, QMediaPlayer
from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "blindcue"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


@pytest.fixture(scope="session")
def qt_app():
    app = QApplication.instance() or QApplication([])
    yield app


class _EndedDeck:
    """QMediaPlayer stand-in that has already reached the end of the file."""

    def __init__(self) -> None:
        self.pause_calls = 0

    def mediaStatus(self):  # noqa: N802 - Qt API
        return QMediaPlayer.MediaStatus.EndOfMedia

    def pause(self) -> None:
        self.pause_calls += 1


def test_finished_deck_is_not_paused(qt_app) -> None:
    from engine.player_live import LivePlayer

    player = LivePlayer()
    try:
        deck = _EndedDeck()
        player._deck_pair = lambda idx=None: (deck, None)  # type: ignore[assignment]
        fired: list[bool] = []
        player.signals.eof_reached.connect(lambda: fired.append(True))

        player._handle_cue_finished()
        player.pause()

        assert fired == [True]
        assert deck.pause_calls == 0, "pause() at EndOfMedia freezes the next stop()"
    finally:
        player._driver_timer.stop()
        player.shutdown()


_PLAY_TO_END = textwrap.dedent(
    """
    import faulthandler, os, sys, wave
    sys.path.insert(0, sys.argv[1])
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication
    from engine.player_live import LivePlayer

    media = sys.argv[2]
    with wave.open(media, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(48000)
        w.writeframes(b"\\0\\0\\0\\0" * int(48000 * 0.5))

    app = QApplication(sys.argv)
    lp = LivePlayer()
    done = []

    def on_eof():
        lp.stop()                      # exactly what main._finalize_cue_exit does
        done.append(1)
        if len(done) >= 3:
            app.quit()
        else:
            QTimer.singleShot(100, start)

    def start():
        lp.load(media)
        lp.play()

    lp.signals.eof_reached.connect(on_eof)
    faulthandler.dump_traceback_later(40, exit=True)
    QTimer.singleShot(50, start)
    app.exec()
    print("EOF-CYCLES", len(done))
    """
)


def test_play_to_end_then_stop_does_not_freeze(qt_app, tmp_path) -> None:
    # Do NOT probe QMediaDevices at import time (in a skipif decorator): that
    # initialises the QtMultimedia FFmpeg backend before a QApplication exists
    # and makes it segfault in its static destructor at exit(). Probe here,
    # after the qt_app session fixture has created the application.
    if not QMediaDevices.audioOutputs():
        pytest.skip("no audio output device")
    script = tmp_path / "play_to_end.py"
    script.write_text(_PLAY_TO_END, encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(script), str(APP_DIR), str(tmp_path / "silence.wav")],
        capture_output=True,
        text=True,
        timeout=90,
    )
    assert "EOF-CYCLES 3" in proc.stdout, proc.stdout + proc.stderr
