"""Audio waveform extractor – runs on a background thread.

Uses ``ffprobe`` to read metadata and ``ffmpeg`` to decode raw PCM,
then down-samples via numpy into a fixed-width array of peak values
suitable for painting a waveform widget.

Runs as a :class:`QRunnable` on the application's QThreadPool so that
importing a heavy file never blocks the GUI or the live output.
"""

from __future__ import annotations

import logging
import subprocess
from typing import Optional

import numpy as np
from PySide6.QtCore import QObject, QRunnable, Signal, Slot

logger = logging.getLogger(__name__)

# Decoding sample rate – low enough for fast extraction, high enough
# for a visually accurate waveform.
_DECODE_SAMPLE_RATE = 8000


class _AnalyzerSignals(QObject):
    """Signals emitted from the background runnable."""
    finished = Signal(str, object)   # (file_path, np.ndarray | None)
    error = Signal(str, str)         # (file_path, error_message)


class WaveformAnalyzer(QRunnable):
    """Extract a waveform peak array from an audio/video file.

    Parameters
    ----------
    file_path : str
        Absolute path to the media file.
    target_width : int
        Number of horizontal bins (pixels) for the waveform.
    """

    def __init__(self, file_path: str, target_width: int = 800) -> None:
        super().__init__()
        self.file_path = file_path
        self.target_width = max(1, target_width)
        self.signals = _AnalyzerSignals()
        self.setAutoDelete(True)

    # ── Helpers ───────────────────────────────────────────────────────

    def _get_duration(self) -> Optional[float]:
        """Return file duration in seconds via ffprobe, or None."""
        try:
            result = subprocess.run(
                [
                    "ffprobe", "-v", "quiet",
                    "-show_entries", "format=duration",
                    "-of", "csv=p=0",
                    self.file_path,
                ],
                capture_output=True, text=True, timeout=15,
            )
            return float(result.stdout.strip())
        except Exception as exc:
            logger.warning("[WAVEFORM] ffprobe duration failed: %s", exc)
            return None

    def _decode_pcm(self) -> Optional[np.ndarray]:
        """Decode mono f32le PCM via ffmpeg and return as numpy array."""
        try:
            proc = subprocess.Popen(
                [
                    "ffmpeg", "-v", "quiet",
                    "-i", self.file_path,
                    "-ac", "1",
                    "-ar", str(_DECODE_SAMPLE_RATE),
                    "-f", "f32le",
                    "-acodec", "pcm_f32le",
                    "pipe:1",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
            try:
                raw, _ = proc.communicate(timeout=60)
            except subprocess.TimeoutExpired:
                proc.kill()
                raw, _ = proc.communicate()
                logger.warning("[WAVEFORM] ffmpeg timed out and was killed for %s", self.file_path)

            if not raw:
                return None
            return np.frombuffer(raw, dtype=np.float32)
        except Exception as exc:
            logger.warning("[WAVEFORM] ffmpeg decode failed: %s", exc)
            return None

    # ── QRunnable entry point ─────────────────────────────────────────

    @Slot()
    def run(self) -> None:  # noqa: D102 (QRunnable override)
        try:
            samples = self._decode_pcm()
            if samples is None or len(samples) == 0:
                try:
                    self.signals.error.emit(
                        self.file_path, "No audio data decoded."
                    )
                except RuntimeError:
                    pass
                return

            # Safe down-sampling to target_width bins via peak detection
            samples_abs = np.abs(samples)
            if len(samples_abs) <= self.target_width:
                # Short audio clip: pad with zeros to match width
                peaks = np.zeros(self.target_width, dtype=np.float32)
                peaks[:len(samples_abs)] = samples_abs
            else:
                # Divide into target_width contiguous chunks without shape errors
                splits = np.array_split(samples_abs, self.target_width)
                peaks = np.array([chunk.max() if len(chunk) > 0 else 0.0 for chunk in splits], dtype=np.float32)

            # Normalise to 0.0-1.0
            peak_max = peaks.max()
            if peak_max > 0:
                peaks = peaks / peak_max

            logger.info("[WAVEFORM] Extracted %d bins from %s",
                        len(peaks), self.file_path)
            try:
                self.signals.finished.emit(self.file_path, peaks)
            except RuntimeError:
                pass  # Window or signal source already closed/deleted

        except Exception as exc:
            logger.error("[WAVEFORM] Analysis failed for %s: %s",
                         self.file_path, exc, exc_info=True)
            try:
                self.signals.error.emit(self.file_path, str(exc))
            except RuntimeError:
                pass

