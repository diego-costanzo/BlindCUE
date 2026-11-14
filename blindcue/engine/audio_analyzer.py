"""Audio waveform extractor – runs on a background thread.

Uses ``ffprobe`` to read metadata and ``ffmpeg`` to decode raw PCM,
then down-samples via numpy into a fixed-width array of peak values
suitable for painting a waveform widget.

Runs as a :class:`QRunnable` on the application's QThreadPool so that
importing a heavy file never blocks the GUI or the live output.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import subprocess
from pathlib import Path
from typing import Optional

import numpy as np
from PySide6.QtCore import QObject, QRunnable, QStandardPaths, Signal, Slot

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

            # Safe vectorized peak down-sampling to target_width bins
            samples_abs = np.abs(samples)
            n = len(samples_abs)
            if n <= self.target_width:
                peaks = np.zeros(self.target_width, dtype=np.float32)
                peaks[:n] = samples_abs
            else:
                step = n // self.target_width
                if step >= 1 and step * self.target_width == n:
                    peaks = samples_abs.reshape(self.target_width, step).max(axis=1).astype(np.float32)
                elif step >= 2:
                    trim = step * self.target_width
                    peaks = samples_abs[:trim].reshape(self.target_width, step).max(axis=1).astype(np.float32)
                    rem_max = samples_abs[trim:].max()
                    if rem_max > peaks[-1]:
                        peaks[-1] = rem_max
                else:
                    splits = np.array_split(samples_abs, self.target_width)
                    peaks = np.array(
                        [chunk.max() if len(chunk) > 0 else 0.0 for chunk in splits],
                        dtype=np.float32,
                    )

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


# ── EBU R128 Loudness Scanner & Dynamics Normalizer ──────────────────

def scan_file_loudness(
    file_path: str,
    target_lufs: float = -16.0,
    peak_ceiling_db: float = -1.0,
    timeout_sec: float = 25.0,
) -> Optional[tuple[float, float, float]]:
    """Scan file loudness using ffmpeg ebur128 (ITU-R BS.1770-4).

    Returns (integrated_lufs, true_peak_dbfs, auto_gain_db) or None if analysis fails.
    """
    if not os.path.isfile(file_path):
        return None

    try:
        cmd = [
            "ffmpeg", "-nostats", "-i", file_path,
            "-filter_complex", "ebur128=peak=true",
            "-f", "null", "-",
        ]
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout_sec
        )
        stderr = proc.stderr

        m_i = re.search(r"Integrated loudness:\s+I:\s+([-\d.]+)\s+LUFS", stderr)
        m_p = re.search(r"True peak:\s+Peak:\s+([-\d.]+)\s+dBFS", stderr)
        if not m_i or not m_p:
            return None

        lufs = float(m_i.group(1))
        peak = float(m_p.group(1))

        # If silence / near-silence, do not boost noise floor
        if lufs <= -70.0:
            return (lufs, peak, 0.0)

        raw_gain = target_lufs - lufs
        # Ceiling limiter protection against clipping
        max_safe_gain = peak_ceiling_db - peak
        gain = min(raw_gain, max_safe_gain)
        return (round(lufs, 1), round(peak, 1), round(gain, 2))

    except Exception as exc:
        logger.warning("[LOUDNESS] Failed to scan %s: %s", file_path, exc)
        return None


class _LoudnessSignals(QObject):
    finished = Signal(str, float, float, float)  # (file_path, lufs, peak_dbfs, gain_db)
    error = Signal(str, str)                    # (file_path, err_msg)


class LoudnessScanner(QRunnable):
    """Asynchronous EBU R128 loudness scanner running on QThreadPool."""

    def __init__(self, file_path: str, target_lufs: float = -16.0) -> None:
        super().__init__()
        self.file_path = file_path
        self.target_lufs = target_lufs
        self.signals = _LoudnessSignals()
        self.setAutoDelete(True)

    @Slot()
    def run(self) -> None:
        res = scan_file_loudness(self.file_path, self.target_lufs)
        if res is not None:
            lufs, peak, gain = res
            try:
                self.signals.finished.emit(self.file_path, lufs, peak, gain)
            except RuntimeError:
                pass
        else:
            try:
                self.signals.error.emit(self.file_path, "Loudness scan failed or file has no audio.")
            except RuntimeError:
                pass


def render_normalized_media(
    file_path: str,
    target_lufs: float = -16.0,
    peak_ceiling_db: float = -1.5,
    lra_target: float = 11.0,
    timeout_sec: float = 120.0,
) -> Optional[str]:
    """Render a dynamic-range compressed / normalized media copy using ffmpeg loudnorm.

    For video files: video stream is copied lossless (-c:v copy), audio is compressed.
    For audio files: audio is rendered to lossless 16-bit PCM WAV.
    Returns path to output file in cache directory, or None on failure.
    """
    if not os.path.isfile(file_path):
        return None

    # Cross-platform standard cache path (Linux ~/.cache, macOS ~/Library/Caches, Windows %LOCALAPPDATA%)
    base_cache = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.CacheLocation)
    cache_dir = os.path.join(base_cache or os.path.expanduser("~/.cache"), "blindcue", "audio")
    os.makedirs(cache_dir, exist_ok=True)

    stem = Path(file_path).stem
    ext = Path(file_path).suffix.lower()
    h = hashlib.md5(f"{file_path}_{os.path.getmtime(file_path)}".encode(), usedforsecurity=False).hexdigest()[:8]

    video_exts = {".mp4", ".mkv", ".mov", ".webm", ".avi"}
    is_video = ext in video_exts
    out_ext = ext if is_video else ".wav"
    out_path = os.path.join(cache_dir, f"{stem}_ebur128_{h}{out_ext}")

    if os.path.isfile(out_path) and os.path.getsize(out_path) > 1000:
        return out_path

    filter_str = f"loudnorm=I={target_lufs}:TP={peak_ceiling_db}:LRA={lra_target}"

    if is_video:
        cmd = [
            "ffmpeg", "-y", "-nostats", "-i", file_path,
            "-c:v", "copy",
            "-af", filter_str,
            "-c:a", "aac", "-b:a", "256k",
            out_path,
        ]
    else:
        cmd = [
            "ffmpeg", "-y", "-nostats", "-i", file_path,
            "-af", filter_str,
            "-c:a", "pcm_s16le",
            out_path,
        ]

    try:
        subprocess.run(cmd, capture_output=True, check=True, timeout=timeout_sec)
        if os.path.isfile(out_path):
            return out_path
    except Exception as exc:
        logger.error("[LOUDNORM] Rendering failed for %s: %s", file_path, exc)
    return None


class _DynamicsSignals(QObject):
    finished = Signal(str, str)  # (orig_path, optimized_path)
    error = Signal(str, str)     # (orig_path, err_msg)


class DynamicsOptimizer(QRunnable):
    """Asynchronous loudnorm dynamics compressor running on QThreadPool."""

    def __init__(self, file_path: str, target_lufs: float = -16.0) -> None:
        super().__init__()
        self.file_path = file_path
        self.target_lufs = target_lufs
        self.signals = _DynamicsSignals()
        self.setAutoDelete(True)

    @Slot()
    def run(self) -> None:
        out_path = render_normalized_media(self.file_path, self.target_lufs)
        if out_path is not None:
            try:
                self.signals.finished.emit(self.file_path, out_path)
            except RuntimeError:
                pass
        else:
            try:
                self.signals.error.emit(self.file_path, "Ottimizzazione dinamica fallita.")
            except RuntimeError:
                pass


