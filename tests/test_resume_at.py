"""Undo GO resumes a cut sound from where it stopped (stage 1 C2a step 11).

On a player that just played another file the backend first reports the
resume point, then starts again from 0; the resume point must hold until
playback really passes it. Real playback in a child process.
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

import pytest
from PySide6.QtMultimedia import QMediaDevices

_RESUME = textwrap.dedent(
    """
    import math, os, struct, sys, wave
    sys.path.insert(0, sys.argv[1])
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication
    from engine.player_live import LivePlayer

    def tone(path, freq):
        rate = 48000
        frames = bytearray()
        for i in range(rate * 6):
            v = int(8000 * math.sin(2 * math.pi * freq * i / rate))
            frames += struct.pack("<hh", v, v)
        with wave.open(path, "wb") as w:
            w.setnchannels(2); w.setsampwidth(2); w.setframerate(rate)
            w.writeframes(bytes(frames))

    a, b = sys.argv[2], sys.argv[3]
    tone(a, 440); tone(b, 330)
    app = QApplication(sys.argv)
    lp = LivePlayer()
    seen = []
    lp.signals.position_changed.connect(seen.append)

    def play_b():
        lp.load(b); lp.play()

    def resume_a():
        seen.clear()
        lp.load(a, start=0.0, resume_at=2.0); lp.play()

    QTimer.singleShot(50, play_b)
    QTimer.singleShot(1200, resume_a)
    QTimer.singleShot(2700, app.quit)
    app.exec()
    print("LAST", round(seen[-1], 2) if seen else -1)
    """
)


@pytest.mark.skipif(not QMediaDevices.audioOutputs(), reason="no audio output device")
def test_resume_point_holds_after_another_file(tmp_path) -> None:
    script = tmp_path / "resume.py"
    script.write_text(_RESUME, encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(script), str(APP_DIR), str(tmp_path / "a.wav"), str(tmp_path / "b.wav")],
        capture_output=True, text=True, timeout=90,
    )
    last = float(proc.stdout.split("LAST", 1)[1].split()[0])
    assert last >= 2.8, proc.stdout + proc.stderr   # 2.0 + ~1.5 s of playing, never from 0
