"""Zero-latency synthetic auditory guidance feedback (Earcons) for blind and low-vision show operators.

Produces clean, non-intrusive confirmation chimes for critical director actions (GO, Stop, Pause, Alert)
using in-memory generated PCM waveforms and native QtMultimedia QSoundEffect.
Requires 0 external audio files and 0 external dependencies.
"""

from __future__ import annotations

import io
import math
import struct
import wave
from pathlib import Path

from PySide6.QtCore import QByteArray, QTemporaryFile, QUrl
from PySide6.QtMultimedia import QAudioDevice, QSoundEffect


def _generate_sine_wav(frequency_hz: float, duration_ms: float, volume: float = 0.28) -> bytes:
    """Generate a mono 44.1kHz 16-bit PCM WAV audio in memory with smooth cosine envelope."""
    sample_rate = 44100
    num_samples = int(sample_rate * (duration_ms / 1000.0))
    buf = io.BytesIO()

    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)

        samples: list[bytes] = []
        for i in range(num_samples):
            # Raised cosine envelope (Hanning window) to avoid any audio clicks/pops
            envelope = math.sin(math.pi * i / max(1, num_samples - 1))
            val = math.sin(2.0 * math.pi * frequency_hz * i / sample_rate)
            sample_val = int(32767.0 * volume * envelope * val)
            clamped = max(-32767, min(32767, sample_val))
            samples.append(struct.pack("<h", clamped))

        wf.writeframes(b"".join(samples))

    return buf.getvalue()


class EarconManager:
    """Manages low-latency auditory confirmation cues for show operator accessibility."""

    def __init__(self, temp_dir: Path | None = None) -> None:
        """Create the earcon manager; audio assets are loaded only when ``enabled`` is set."""
        self._enabled: bool = False
        self._audio_device: QAudioDevice | None = None
        self._temp_files: list[QTemporaryFile] = []
        self._sounds: dict[str, QSoundEffect] = {}
        self._init_sounds()

    def set_audio_device(self, device: QAudioDevice | None) -> None:
        """Route operator earcons to the monitor/headphone device instead of the PA."""
        self._audio_device = device
        if device is None or device.isNull():
            return
        for sound in self._sounds.values():
            if hasattr(sound, "setAudioDevice"):
                try:
                    sound.setAudioDevice(device)
                except Exception:
                    pass

    def _init_sounds(self) -> None:
        """Synthesize earcons and load them into memory-backed QSoundEffect objects."""
        earcon_specs = {
            "go": (880.0, 45.0, 0.35),       # A5 high bright confirmation ping
            "pause": (659.25, 40.0, 0.30),   # E5 medium pause tone
            "stop": (440.0, 60.0, 0.32),     # A4 low grounding stop tone
            "alert": (523.25, 50.0, 0.35),   # C5 warning tone
        }

        for name, (freq, dur_ms, vol) in earcon_specs.items():
            wav_bytes = _generate_sine_wav(freq, dur_ms, volume=vol)
            tmp = QTemporaryFile()
            tmp.setAutoRemove(True)
            if tmp.open():
                tmp.write(QByteArray(wav_bytes))
                tmp.flush()
                tmp.close()

                sound = QSoundEffect()
                sound.setSource(QUrl.fromLocalFile(tmp.fileName()))
                sound.setVolume(1.0)
                self._sounds[name] = sound
                self._temp_files.append(tmp)

    @property
    def enabled(self) -> bool:
        """True when auditory feedback is active (off by default: silent shows)."""
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        """Enable/disable the earcons without recreating the audio effects."""
        self._enabled = bool(value)

    def play_go(self) -> None:
        """Play affirmative high confirmation tone on cue GO execution."""
        if self._enabled and "go" in self._sounds:
            self._sounds["go"].play()

    def play_pause(self) -> None:
        """Play medium hold tone on pause/freeze toggle."""
        if self._enabled and "pause" in self._sounds:
            self._sounds["pause"].play()

    def play_stop(self) -> None:
        """Play low grounding tone on show stop or master blackout."""
        if self._enabled and "stop" in self._sounds:
            self._sounds["stop"].play()

    def play_alert(self) -> None:
        """Play warning alert tone on blocked operation or critical safety trigger."""
        if self._enabled and "alert" in self._sounds:
            self._sounds["alert"].play()

