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


def _generate_notes_wav(notes: list[tuple[float, float]], gap_ms: float, volume: float = 0.3) -> bytes:
    """Several short notes in a row (frequency, ms), *gap_ms* of silence between them."""
    sample_rate = 44100
    pcm = bytearray()
    for idx, (freq, dur_ms) in enumerate(notes):
        n = int(sample_rate * dur_ms / 1000.0)
        for i in range(n):
            envelope = math.sin(math.pi * i / max(1, n - 1))
            val = int(32767.0 * volume * envelope * math.sin(2.0 * math.pi * freq * i / sample_rate))
            pcm += struct.pack("<h", max(-32767, min(32767, val)))
        if idx < len(notes) - 1:
            pcm += b"\x00\x00" * int(sample_rate * gap_ms / 1000.0)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(bytes(pcm))
    return buf.getvalue()


# Told apart by rhythm, not only by pitch (accessibility review W39); each 80-300 ms.
EARCON_NOTES: dict[str, tuple[list[tuple[float, float]], float]] = {
    "go": ([(659.25, 70.0), (880.0, 70.0)], 30.0),                       # two up
    "alert": ([(330.0, 80.0), (330.0, 80.0)], 40.0),                     # two low, equal
    "enter_show": ([(523.25, 60.0), (659.25, 60.0), (784.0, 60.0)], 25.0),  # three up
    "exit_show": ([(784.0, 60.0), (659.25, 60.0), (523.25, 60.0)], 25.0),   # three down
    "undo": ([(880.0, 70.0), (659.25, 70.0)], 30.0),                     # two down
    "stop": ([(220.0, 280.0)], 0.0),                                     # one long, low (PANIC, Fade All)
    "pause": ([(659.25, 90.0)], 0.0),                                    # one short, middle
}


def earcon_duration_ms(name: str) -> float:
    notes, gap = EARCON_NOTES[name]
    return sum(ms for _f, ms in notes) + gap * (len(notes) - 1)


class EarconManager:
    """Manages low-latency auditory confirmation cues for show operator accessibility."""

    def __init__(self, temp_dir: Path | None = None) -> None:
        """Create the earcon manager; audio assets are loaded only when ``enabled`` is set."""
        self._enabled: bool = False
        self._audio_device: QAudioDevice | None = None
        self._master_device: QAudioDevice | None = None
        self._temp_files: list[QTemporaryFile] = []
        self._sounds: dict[str, QSoundEffect] = {}
        self._init_sounds()

    def set_master_device(self, device: QAudioDevice | None) -> None:
        """The audience speakers: earcons never play there (W42)."""
        self._master_device = device

    def on_audience_speakers(self) -> bool:
        """True when the headphones are the audience speakers: then the earcons keep quiet."""
        from PySide6.QtMultimedia import QMediaDevices

        def _id(dev: QAudioDevice | None) -> bytes:
            dev = dev if dev is not None and not dev.isNull() else QMediaDevices.defaultAudioOutput()
            return bytes(dev.id())

        return _id(self._audio_device) == _id(self._master_device)

    def _can_play(self, name: str) -> bool:
        return self._enabled and name in self._sounds and not self.on_audience_speakers()

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
        for name, (notes, gap) in EARCON_NOTES.items():
            wav_bytes = _generate_notes_wav(notes, gap)
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

    def _play(self, name: str) -> None:
        if self._can_play(name):
            self._sounds[name].play()

    def play_go(self) -> None:
        """GO: two notes up."""
        self._play("go")

    def play_pause(self) -> None:
        """Pause All on/off: one short middle note."""
        self._play("pause")

    def play_stop(self) -> None:
        """PANIC, Fade All, Blackout: one long low note."""
        self._play("stop")

    def play_alert(self) -> None:
        """Something was refused (a blocked GO, an action not allowed now): two low equal notes."""
        self._play("alert")

    def play_enter_show(self) -> None:
        """Into the show: three notes up."""
        self._play("enter_show")

    def play_exit_show(self) -> None:
        """Out of the show (to the rehearsal or the preparation): three notes down."""
        self._play("exit_show")

    def play_undo(self) -> None:
        """Undo GO: two notes down."""
        self._play("undo")

