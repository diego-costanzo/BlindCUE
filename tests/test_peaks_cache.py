"""Stage 3, item 3.4: waveform peaks kept on disk; volume envelope points in dB."""

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

import numpy as np
import pytest
from engine import peaks_cache
from engine.envelope import db_to_level, format_level_db, level_to_db
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qt_app():
    app = QApplication.instance() or QApplication([])
    yield app


def test_store_and_load_follow_the_file(tmp_path):
    media = tmp_path / "song.wav"
    media.write_bytes(b"RIFF" + b"\0" * 100)
    cache = str(tmp_path / "cache")
    peaks = np.linspace(0, 1, 50, dtype=np.float32)
    assert peaks_cache.load(cache, str(media)) is None
    assert peaks_cache.store(cache, str(media), peaks, 12.5)
    got, duration = peaks_cache.load(cache, str(media))
    assert np.allclose(got, peaks) and duration == 12.5
    media.write_bytes(b"RIFF" + b"\0" * 200)                 # a changed file is a new entry
    assert peaks_cache.load(cache, str(media)) is None
    assert peaks_cache.load(None, str(media)) is None         # no folder: no cache
    assert peaks_cache.load(cache, str(tmp_path / "gone.wav")) is None


def test_prune_keeps_the_newest(tmp_path):
    cache = tmp_path / "cache"
    for i in range(6):
        media = tmp_path / f"{i}.wav"
        media.write_bytes(bytes([i]) * 10)
        peaks_cache.store(str(cache), str(media), np.ones(4, dtype=np.float32), None)
        entry = next(p for p in cache.iterdir() if p.name.startswith(peaks_cache.cache_key(str(media))))
        os.utime(entry, (time.time() - 100 + i, time.time() - 100 + i))
    assert peaks_cache.prune(str(cache), keep=4) == 2
    assert len(list(cache.glob("*.npz"))) == 4
    assert peaks_cache.load(str(cache), str(tmp_path / "5.wav")) is not None
    assert peaks_cache.load(str(cache), str(tmp_path / "0.wav")) is None


def test_analyzer_uses_the_disk_cache(qt_app, tmp_path, monkeypatch):
    from engine import audio_analyzer

    media = tmp_path / "song.wav"
    media.write_bytes(b"RIFF" + b"\0" * 100)
    cache = str(tmp_path / "cache")
    first = audio_analyzer.WaveformAnalyzer(str(media), 10, cache_dir=cache)
    monkeypatch.setattr(first, "_get_duration", lambda: 3.0)
    monkeypatch.setattr(first, "_decode_pcm", lambda: np.linspace(-1, 1, 1000, dtype=np.float32))
    got: list = []
    first.signals.finished.connect(lambda _p, peaks: got.append(peaks))
    first.run()
    second = audio_analyzer.WaveformAnalyzer(str(media), 10, cache_dir=cache)
    monkeypatch.setattr(second, "_decode_pcm", lambda: pytest.fail("decoded again"))
    monkeypatch.setattr(second, "_get_duration", lambda: pytest.fail("probed again"))
    durations: list = []
    second.signals.duration_ready.connect(lambda _p, sec: durations.append(sec))
    second.signals.finished.connect(lambda _p, peaks: got.append(peaks))
    second.run()
    assert len(got) == 2 and np.allclose(got[0], got[1]) and durations == [3.0]


def test_levels_in_db():
    assert level_to_db(1.0) == 0.0 and level_to_db(0.0) == float("-inf")
    assert db_to_level(-6.0) == pytest.approx(0.501, abs=0.001)
    assert db_to_level(-60.0) == 0.0 and db_to_level(3.0) == 1.0    # never above the file's level
    assert format_level_db(0.5) == "-6.0 dB" and format_level_db(1.0) == "0.0 dB"
    assert format_level_db(0.0) == "-∞ dB"


def test_fade_out_ends_at_the_out_point_not_at_the_file_end():
    """3.4 (checked and documented): the Fade Out is counted back from OUT when there is one."""
    from engine.envelope import evaluate_cue_level

    def level(t, end):
        return evaluate_cue_level(t, start_sec=0.0, end_sec=end, duration_sec=60.0, fade_in=0.0, fade_out=2.0,
                                  fade_curve="linear", points=[], base_level=1.0)

    assert level(9.0, 10.0) == pytest.approx(0.5)       # OUT 10 s: halfway through the fade at 9 s
    assert level(10.0, 10.0) == 0.0
    assert level(9.0, None) == 1.0 and level(59.0, None) == pytest.approx(0.5)   # no OUT: the file end


def test_point_level_typed_in_db(qt_app):
    from models.cue import MediaType
    from ui.waveform_widget import WaveformWidget

    wave = WaveformWidget()
    wave.set_media_context(MediaType.AUDIO)
    wave.set_envelopes(base_volume=1.0, base_opacity=1.0, volume_points=[[1.0, 1.0], [2.0, 0.8]],
                       opacity_points=[])
    seen: list = []
    wave.envelope_points_changed.connect(lambda mode, pts: seen.append((mode, pts)))
    assert wave.edit_point_db(1, -12.0)
    assert seen[-1][0] == "volume" and seen[-1][1][1][1] == pytest.approx(0.2512, abs=1e-4)
    assert not wave.edit_point_db(5, -3.0)
    wave.deleteLater()
