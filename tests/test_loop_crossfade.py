"""Stage 3, item 3.4: a sound loop whose passes run into each other (crossfade) with a repeat count."""

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
from models.cue import Cue, MediaType
from PySide6.QtMultimedia import QMediaDevices
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qt_app():
    app = QApplication.instance() or QApplication([])
    yield app


def test_loop_crossfade_round_trip_and_old_shows():
    cue = Cue(name="rain", media_type=MediaType.AUDIO, file_path="rain.wav", loop=True, loop_count=3)
    cue.loop_crossfade = 2.5
    assert Cue.from_dict(cue.to_dict()).loop_crossfade == 2.5
    old = Cue.from_dict({"cue_id": 5501, "name": "old", "media_type": "AUDIO", "file_path": "a.wav", "loop": True})
    assert old.loop_crossfade == 0.0
    assert Cue.from_dict({**cue.to_dict(), "loop_crossfade": 99}).loop_crossfade == 30.0


def test_fade_out_only_on_the_last_pass(qt_app):
    from engine.player_live import LivePlayer

    lp = LivePlayer()
    try:
        lp._is_video_cue = False
        lp.set_loop(True, 3, crossfade=1.0)
        lp._duration_sec = 10.0
        lp._fade_out_sec = 2.0
        assert lp._compute_audio_gain(9.5) == pytest.approx(1.0)        # pass 1 of 3: no fade out
        lp._current_loop_iteration = 2
        assert lp._compute_audio_gain(9.5) < 0.5                         # the last pass fades out
        lp.set_loop(True, 0, crossfade=1.0)
        lp._current_loop_iteration = 7
        assert lp._compute_audio_gain(9.5) == pytest.approx(1.0)        # endless: never
    finally:
        lp.shutdown()


_LOOP = textwrap.dedent(
    """
    import faulthandler, os, sys, time, wave
    sys.path.insert(0, sys.argv[1])
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication
    from engine.player_live import LivePlayer

    media = os.path.join(sys.argv[2], "loop.wav")
    with wave.open(media, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(48000)
        w.writeframes(b"\\0\\0\\0\\0" * int(48000 * 1.0))

    app = QApplication(sys.argv)
    lp = LivePlayer()
    state = {"t0": None, "decks": [], "eof": 0, "xf_seen": 0}

    def tick():
        if lp._xf is not None:
            state["xf_seen"] += 1
        if not state["decks"] or state["decks"][-1] != lp._active_deck:
            state["decks"].append(lp._active_deck)

    def on_eof():
        state["eof"] += 1
        print("ELAPSED", round(time.monotonic() - state["t0"], 2))
        lp.stop()                       # what main._finalize_cue_exit does
        QTimer.singleShot(300, app.quit)

    def start():
        lp.load(media)
        lp.set_loop(True, 3, crossfade=0.3)
        lp.play()

    def on_pos(sec):
        if state["t0"] is None and sec > 0:
            state["t0"] = time.monotonic() - sec   # opening the sound device may take a second here

    poll = QTimer(); poll.setInterval(10); poll.timeout.connect(tick); poll.start()
    lp.signals.position_changed.connect(on_pos)
    lp.signals.eof_reached.connect(on_eof)
    faulthandler.dump_traceback_later(40, exit=True)
    QTimer.singleShot(50, start)
    QTimer.singleShot(12000, app.quit)
    app.exec()
    print("DECKS", "".join(str(d) for d in state["decks"]))
    print("EOF", state["eof"], "XF", state["xf_seen"] > 0, "XF-IN", lp._xf_in)
    lp.shutdown()
    print("DONE")
    """
)


def test_three_passes_with_a_crossfade_end_once(qt_app, tmp_path):
    if not QMediaDevices.audioOutputs():
        pytest.skip("no audio output device")
    script = tmp_path / "loop.py"
    script.write_text(_LOOP, encoding="utf-8")
    proc = subprocess.run([sys.executable, str(script), str(APP_DIR), str(tmp_path)],
                          capture_output=True, text=True, timeout=90)
    out = proc.stdout + proc.stderr
    assert "DONE" in proc.stdout, out
    assert "DECKS 010" in proc.stdout, out          # pass 2 on the second deck, pass 3 back on the first
    assert "EOF 1 XF True XF-IN 1.0" in proc.stdout, out
    elapsed = float(next(line for line in proc.stdout.splitlines() if line.startswith("ELAPSED")).split()[1])
    assert 1.5 < elapsed < 2.7, out                 # 3 x (1 s - 0.12 s margin) minus 2 overlaps of 0.3 s
