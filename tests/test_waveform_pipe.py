"""The waveform decoder reads ffmpeg's pipe on every platform.

On Windows select() accepts sockets only: registering ffmpeg's stdout in a
selector failed with WinError 10038 at the first select(), so no waveform
was ever drawn there. Uses a real ffmpeg (PATH or build/ffmpeg), else skipped.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "blindcue"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from engine import audio_analyzer  # noqa: E402


def _ffmpeg() -> str | None:
    found = shutil.which("ffmpeg")
    if found:
        return found
    local = ROOT / "build" / "ffmpeg" / ("ffmpeg.exe" if sys.platform == "win32" else "ffmpeg")
    return str(local) if local.exists() else None


@pytest.mark.skipif(_ffmpeg() is None, reason="ffmpeg not installed")
def test_real_ffmpeg_pipe_gives_samples(monkeypatch, tmp_path):
    ffmpeg = _ffmpeg()
    tone = tmp_path / "tone.mp3"
    subprocess.run([ffmpeg, "-v", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
                    str(tone)], check=True)
    monkeypatch.setattr(audio_analyzer, "_resolve_binary", lambda name: ffmpeg if name == "ffmpeg" else None)
    samples = audio_analyzer.WaveformAnalyzer(str(tone))._decode_pcm()
    assert samples is not None and len(samples) > 1000
    assert float(samples.max()) > 0.1          # a real tone, not silence
