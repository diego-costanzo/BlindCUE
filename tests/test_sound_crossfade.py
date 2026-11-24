"""Evaluation 2026-11-24: a sound handed over by a crossfade fades by itself; the show controls reach it."""

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

from engine import player_live as pl
from PySide6.QtCore import QCoreApplication
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import QApplication


def _pump(seconds: float) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.005)


def _tail(monkeypatch, seconds: float):
    QApplication.instance() or QApplication([])
    player, audio = QMediaPlayer(), QAudioOutput()
    audio.setVolume(0.8)
    state = {"s": QMediaPlayer.PlaybackState.PlayingState}
    monkeypatch.setattr(player, "playbackState", lambda: state["s"])
    monkeypatch.setattr(player, "stop", lambda: state.update(s=QMediaPlayer.PlaybackState.StoppedState))
    monkeypatch.setattr(player, "pause", lambda: state.update(s=QMediaPlayer.PlaybackState.PausedState))
    monkeypatch.setattr(player, "play", lambda: state.update(s=QMediaPlayer.PlaybackState.PlayingState))
    return pl._TailFade(player, audio, seconds), audio, state


def test_tail_fades_out_and_goes(monkeypatch):
    tail, audio, state = _tail(monkeypatch, 0.4)
    assert pl.tails_count() == 1
    _pump(0.2)
    assert 0.0 < audio.volume() < 0.8
    _pump(0.4)
    assert pl.tails_count() == 0 and state["s"] == QMediaPlayer.PlaybackState.StoppedState


def test_pause_holds_fade_all_shortens_panic_stops(monkeypatch):
    tail, audio, state = _tail(monkeypatch, 5.0)
    pl.pause_all_tails(True)
    held = audio.volume()
    _pump(0.3)
    assert audio.volume() == held and state["s"] == QMediaPlayer.PlaybackState.PausedState
    pl.pause_all_tails(False)
    assert state["s"] == QMediaPlayer.PlaybackState.PlayingState
    pl.fade_all_tails(0.2)                         # Fade All: silence within its own time, not 5 s
    _pump(0.4)
    assert pl.tails_count() == 0
    _tail(monkeypatch, 5.0)
    pl.stop_all_tails()                            # PANIC / blackout
    assert pl.tails_count() == 0
