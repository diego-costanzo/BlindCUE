"""VU meter next to the master volume (stage 1 C3, 1.14).

The level tap reads the decoded audio of the live players. It runs in the
playback path that once froze the program at the end of a file (pl3), so
it is checked with real playback to the end, three times, in a child process.
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "blindcue"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import pytest
from PySide6.QtMultimedia import QMediaDevices
from PySide6.QtWidgets import QApplication

_PLAY_WITH_TAP = textwrap.dedent(
    """
    import faulthandler, math, os, struct, sys, wave
    sys.path.insert(0, sys.argv[1])
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication
    from engine.player_live import LivePlayer

    media = sys.argv[2]
    rate = 48000
    frames = bytearray()
    for i in range(int(rate * 0.6)):
        v = int(16000 * math.sin(2 * math.pi * 440 * i / rate))
        frames += struct.pack("<hh", v, v)
    with wave.open(media, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(rate)
        w.writeframes(bytes(frames))

    app = QApplication(sys.argv)
    lp = LivePlayer()
    lp.enable_level_tap()
    done = []
    peaks = []

    def poll():
        peaks.append(lp.take_peak())

    def on_eof():
        lp.stop()
        done.append(1)
        if len(done) >= 3:
            app.quit()
        else:
            QTimer.singleShot(100, start)

    def start():
        lp.load(media)
        lp.play()

    lp.signals.eof_reached.connect(on_eof)
    meter = QTimer()
    meter.setInterval(50)
    meter.timeout.connect(poll)
    meter.start()
    faulthandler.dump_traceback_later(40, exit=True)
    QTimer.singleShot(50, start)
    app.exec()
    print("EOF-CYCLES", len(done))
    print("PEAK", round(max(peaks or [0.0]), 3))
    """
)


@pytest.mark.skipif(not QMediaDevices.audioOutputs(), reason="no audio output device")
def test_level_tap_reads_peaks_and_never_freezes_at_the_end(tmp_path) -> None:
    script = tmp_path / "play_with_tap.py"
    script.write_text(_PLAY_WITH_TAP, encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(script), str(APP_DIR), str(tmp_path / "tone.wav")],
        capture_output=True, text=True, timeout=90,
    )
    assert "EOF-CYCLES 3" in proc.stdout, proc.stdout + proc.stderr
    peak = float(proc.stdout.split("PEAK", 1)[1].split()[0])
    assert peak > 0.05, proc.stdout


def test_meter_scale_and_warning_colour():
    app = QApplication.instance() or QApplication([])
    from ui.master_volume import MasterVolume

    mv = MasterVolume()
    mv.set_vu(0.0)
    assert mv.vu.value() == 0
    mv.set_vu(1.0)
    assert mv.vu.value() == 100 and "#fbbf24" in mv.vu.styleSheet()
    mv.set_vu(10 ** (-24 / 20))      # -24 dB: half way, green
    assert 45 <= mv.vu.value() <= 55 and "#4ade80" in mv.vu.styleSheet()
    assert app is not None
