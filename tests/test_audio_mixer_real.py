"""The own mixer on the real sound card, with real FFmpeg (3.2): start time and no dropouts.

A child process plays a -70 dBFS tone (inaudible) through a mixer cue with
pan, two outputs, EQ and reverb, while its GUI thread is kept busy with
Python work and long C++ calls (a big picture scaled: the GIL is held for
~100 ms). It reports how long the first sound took and whether a device ran
dry. Skipped without FFmpeg or without an audio output.

Also a measuring tool: ``python tests/test_audio_mixer_real.py`` prints the
numbers (see docs/claude/noc/mikser.md).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "blindcue"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


def _ffmpeg() -> str | None:
    from engine.audio_mixer_source import find_ffmpeg

    found = find_ffmpeg()
    if found:
        return found
    for base in (ROOT, *ROOT.parents):
        exe = base / "build" / "ffmpeg" / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg")
        if exe.is_file():
            return str(exe)
    return None


def _has_output() -> bool:
    from PySide6.QtMultimedia import QMediaDevices

    try:
        return not QMediaDevices.defaultAudioOutput().isNull()
    except Exception:  # noqa: BLE001
        return False


CHILD = textwrap.dedent(r"""
    import json, os, subprocess, sys, time
    sys.path.insert(0, sys.argv[1])
    os.environ["BLINDCUE_FFMPEG"] = sys.argv[2]
    work = sys.argv[3]
    kind = sys.argv[4]          # idle / py / cxx / busy (= py + cxx)
    busy = kind != "idle"
    from PySide6.QtCore import QTimer, Qt, QSettings
    from PySide6.QtGui import QImage
    from PySide6.QtWidgets import QApplication
    app = QApplication(sys.argv[:1])
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, work)
    tone = os.path.join(work, "tone.wav")
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    subprocess.run([sys.argv[2], "-v", "error", "-y", "-f", "lavfi", "-i",
                    "sine=frequency=440:duration=6,volume=0.0003", "-ac", "2", tone],
                   check=True, creationflags=flags)
    from engine import audio_mix
    from engine.audio_mixer_output import MixerService
    from engine.player_live import LivePlayer
    service = MixerService.instance()
    head_ms = None
    if sys.argv[5] == "prefetch":
        # As the program does for the show's mixer cues: the start is decoded before the GO.
        src = service.acquire_source(tone)
        t = time.perf_counter()
        head = src.prefetch(0, 12.0)
        while not head.done and time.perf_counter() - t < 10:
            app.processEvents()
            time.sleep(0.005)
        head_ms = round((time.perf_counter() - t) * 1000, 1)
    lp = LivePlayer()
    spec = audio_mix.MixSpec(pan=-0.5, sends=(("stage", 1.0), ("hall", 0.5)), eq=(3.0, 0.0, -3.0),
                             reverb=0.3, room="medium")
    lp.use_mixer(spec)
    lp.load(tone)
    lp.configure_automation(base_volume=1.0)
    voice = lp._player._voice
    result = {"started_ms": None, "positions_ok": True, "head_ms": head_ms}
    last = [0]
    img = QImage(5000, 5000, QImage.Format.Format_ARGB32)
    img.fill(0x80ff0000)
    result["device_ms"] = None
    def watch():
        if result["started_ms"] is None and voice.started:
            result["started_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        worker = service._worker
        if result["device_ms"] is None and worker is not None and any(
                s.sink.processedUSecs() > 0 for s in list(worker._sinks.values())):
            result["device_ms"] = round((time.perf_counter() - t0) * 1000, 1)  # the device took sound
            result["_dev_t"] = time.perf_counter()
        pos = lp._player.position()
        if pos < last[0]:
            result["positions_ok"] = False
        last[0] = pos
    def load_gui():
        if not busy:
            return
        t = time.perf_counter()
        x = 0
        while kind in ("py", "busy") and time.perf_counter() - t < 0.12:
            for i in range(500):
                x += i * i
        t = time.perf_counter()
        if kind in ("cxx", "busy"):
            img.scaled(4999, 4999, mode=Qt.TransformationMode.SmoothTransformation)
        result["cxx_ms"] = max(result.get("cxx_ms", 0), round((time.perf_counter() - t) * 1000))
    w = QTimer(); w.setInterval(2); w.timeout.connect(watch); w.start()
    g = QTimer(); g.setInterval(400); g.timeout.connect(load_gui); g.start()
    t0 = time.perf_counter()
    lp.play()
    def finish():
        w.stop(); g.stop()
        stats = service.stats()
        worker = service._worker
        played = max((s.sink.processedUSecs() / 1000 for s in list(worker._sinks.values())), default=0.0)
        wall = (time.perf_counter() - result.pop("_dev_t", time.perf_counter())) * 1000
        # What the device played against the time it ran: a dropout makes it fall behind.
        result.update(drained=stats["drained"], starved=stats["starved"], sinks=stats["sinks"],
                      position_ms=lp._player.position(), max_gap_ms=stats["max_gap_ms"],
                      device_behind_ms=round(wall - played, 1))
        lp.stop()
        service.shutdown()
        print("RESULT " + json.dumps(result), flush=True)
        app.quit()
    QTimer.singleShot(3000, finish)
    app.exec()
""")


def measure(busy: bool | str = True, prefetch: bool = True, timeout: float = 90.0) -> dict:
    import tempfile

    ffmpeg = _ffmpeg()
    with tempfile.TemporaryDirectory(prefix="mixer-real-") as work:
        script = Path(work) / "child.py"
        script.write_text(CHILD, encoding="utf-8")
        env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
        kind = busy if isinstance(busy, str) else ("busy" if busy else "idle")
        proc = subprocess.run([sys.executable, str(script), str(APP_DIR), ffmpeg, work, kind,
                               "prefetch" if prefetch else "cold"],
                              capture_output=True, text=True, timeout=timeout, env=env)
    lines = [ln for ln in proc.stdout.splitlines() if ln.startswith("RESULT ")]
    if not lines:
        raise AssertionError(f"no result (exit {proc.returncode}): {proc.stderr[-2000:]}")
    return json.loads(lines[-1][len("RESULT "):])


@pytest.mark.skipif(_ffmpeg() is None, reason="FFmpeg not found")
@pytest.mark.skipif(not _has_output(), reason="no audio output")
def test_mixer_plays_on_the_sound_card_without_dropouts_while_the_gui_is_busy():
    result = measure(busy=True, prefetch=True)
    assert result["started_ms"] is not None and result["started_ms"] < 400
    assert result["starved"] == 0
    # The device played as long as it ran (a dropout makes it fall behind the clock).
    assert result["device_behind_ms"] < 60, result
    assert result["positions_ok"] and result["position_ms"] > 2000


if __name__ == "__main__":
    for busy in (False, True):
        for prefetch in (True, False):
            print("busy" if busy else "idle", "prefetched" if prefetch else "cold", measure(busy, prefetch))
