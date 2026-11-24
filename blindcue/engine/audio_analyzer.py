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
import selectors
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import numpy as np
from PySide6.QtCore import QObject, QRunnable, QStandardPaths, Signal, Slot

from engine.runtime_limits import (
    child_process_kwargs,
    ffmpeg_thread_args,
    low_priority_prefix,
)

logger = logging.getLogger(__name__)

# Decoding sample rate – low enough for fast extraction, high enough
# for a visually accurate waveform.
_DECODE_SAMPLE_RATE = 8000
_DECODE_TIMEOUT_SEC = 60.0


def _resolve_binary(name: str) -> str | None:
    """Return the absolute path of a required CLI tool, or None if missing."""
    return shutil.which(name)


def _no_window_kwargs() -> dict[str, object]:
    """Platform flags that keep child processes invisible and low priority.

    On Windows a GUI application spawning ``ffmpeg``/``ffprobe`` via a console
    shows a black window for the duration of the child process; that window
    steals keyboard focus from the operator, which is unacceptable during a
    live show.  On Linux/macOS this is a no-op.
    """
    return child_process_kwargs()


def _ffmpeg_cmd(ffmpeg: str) -> list[str]:
    """Start an ffmpeg command with a low OS priority and a capped thread count."""
    return [*low_priority_prefix(), ffmpeg, *ffmpeg_thread_args()]


class _AnalyzerSignals(QObject):
    """Signals emitted from the background runnable."""
    duration_ready = Signal(str, float)  # (file_path, duration_sec)
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
        """Prepare a waveform peak-extraction job for ``file_path``."""
        super().__init__()
        self.file_path = file_path
        self.target_width = max(1, target_width)
        self.signals = _AnalyzerSignals()
        self.setAutoDelete(True)

    # ── Helpers ───────────────────────────────────────────────────────

    def _get_duration(self) -> float | None:
        """Return file duration in seconds via ffprobe, or None."""
        ffprobe = _resolve_binary("ffprobe")
        if ffprobe is None:
            logger.debug("[WAVEFORM] ffprobe not available in PATH")
            return None
        try:
            result = subprocess.run(
                [
                    *low_priority_prefix(), ffprobe, "-v", "quiet",
                    "-show_entries", "format=duration",
                    "-of", "csv=p=0",
                    self.file_path,
                ],
                capture_output=True, text=True, timeout=15,
                stdin=subprocess.DEVNULL,
                **child_process_kwargs(),
            )
            return float(result.stdout.strip())
        except Exception as exc:
            logger.warning("[WAVEFORM] ffprobe duration failed: %s", exc)
            return None

    def _decode_pcm(self) -> np.ndarray | None:
        """Decode mono f32le PCM via ffmpeg with bounded streaming memory.

        Streams 64 KiB chunks from ffmpeg and folds excess samples into a
        compact peak-envelope buffer (strictly O(target_width) RAM even for
        multi-hour audio files), while remaining compatible with mocked Popen
        objects in unit tests.
        """
        ffmpeg = _resolve_binary("ffmpeg")
        if ffmpeg is None:
            logger.warning("[WAVEFORM] ffmpeg not found in PATH; waveform unavailable")
            return None

        proc: subprocess.Popen | None = None
        # Keep peak buffer bounded to ~512 KiB max regardless of audio length
        max_buf_samples = max(16384, self.target_width * 16)
        # Align max_buf_samples to an even number for lossless pairwise folding
        if max_buf_samples % 2 != 0:
            max_buf_samples += 1

        try:
            with subprocess.Popen(
                [
                    *_ffmpeg_cmd(ffmpeg),
                    "-v", "quiet", "-nostdin",
                    "-i", self.file_path,
                    "-ac", "1",
                    "-ar", str(_DECODE_SAMPLE_RATE),
                    "-f", "f32le",
                    "-acodec", "pcm_f32le",
                    "pipe:1",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                **child_process_kwargs(),
            ) as proc:
                stdout = getattr(proc, "stdout", None)
                if stdout is None or not hasattr(stdout, "read"):
                    # Fallback for test doubles implementing communicate() only
                    try:
                        raw, _ = proc.communicate(timeout=_DECODE_TIMEOUT_SEC)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        try:
                            raw, _ = proc.communicate(timeout=5)
                        except subprocess.TimeoutExpired:
                            raw = b""
                        logger.warning("[WAVEFORM] ffmpeg timed out and was killed for %s", self.file_path)
                    except BaseException:
                        proc.kill()
                        raise
                    if not raw:
                        return None
                    trimmed = len(raw) - (len(raw) % 4)
                    if trimmed <= 0:
                        return None
                    return np.frombuffer(raw[:trimmed], dtype=np.float32)

                # Real streaming decode with wall-clock deadline + O(target_width) RAM
                deadline = time.monotonic() + _DECODE_TIMEOUT_SEC
                peak_buf = np.empty(0, dtype=np.float32)
                stride = 1
                carry = np.empty(0, dtype=np.float32)
                byte_rem = b""
                timed_out = False

                sel: selectors.BaseSelector | None = None
                try:
                    if hasattr(stdout, "fileno"):
                        sel = selectors.DefaultSelector()
                        sel.register(stdout, selectors.EVENT_READ)
                except Exception:
                    sel = None

                try:
                    while True:
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            timed_out = True
                            break
                        if sel is not None:
                            events = sel.select(timeout=min(0.5, remaining))
                            if not events:
                                if proc.poll() is not None:
                                    # Drain any final bytes after process exit
                                    pass
                                else:
                                    continue
                        chunk = stdout.read(65536)
                        if not chunk:
                            break
                        if byte_rem:
                            chunk = byte_rem + chunk
                        usable = len(chunk) - (len(chunk) % 4)
                        byte_rem = chunk[usable:]
                        if usable <= 0:
                            continue

                        samples = np.abs(np.frombuffer(chunk[:usable], dtype=np.float32))
                        if stride > 1:
                            if len(carry) > 0:
                                samples = np.concatenate((carry, samples))
                            n_blocks = len(samples) // stride
                            if n_blocks > 0:
                                reduced = samples[: n_blocks * stride].reshape(n_blocks, stride).max(axis=1)
                                carry = samples[n_blocks * stride :]
                            else:
                                carry = samples
                                continue
                        else:
                            reduced = samples

                        peak_buf = np.concatenate((peak_buf, reduced))
                        while len(peak_buf) >= max_buf_samples:
                            even_n = len(peak_buf) - (len(peak_buf) % 2)
                            tail = peak_buf[even_n:]
                            peak_buf = np.maximum(peak_buf[0:even_n:2], peak_buf[1:even_n:2])
                            if len(tail) > 0:
                                peak_buf = np.concatenate((peak_buf, tail))
                            stride *= 2
                except BaseException:
                    proc.kill()
                    raise
                finally:
                    if sel is not None:
                        try:
                            sel.close()
                        except Exception:
                            pass

                if timed_out:
                    proc.kill()
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        pass
                    logger.warning("[WAVEFORM] ffmpeg timed out and was killed for %s", self.file_path)
                    return None

                try:
                    proc.wait(timeout=max(1.0, deadline - time.monotonic()))
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)
                    logger.warning("[WAVEFORM] ffmpeg exit timed out for %s", self.file_path)
                    return None

                if len(carry) > 0:
                    peak_buf = np.concatenate((peak_buf, np.array([carry.max()], dtype=np.float32)))

                return peak_buf if len(peak_buf) > 0 else None
        except Exception as exc:
            logger.warning("[WAVEFORM] ffmpeg decode failed: %s", exc)
            return None
        finally:
            if proc is not None and proc.poll() is None:
                try:
                    proc.kill()
                    proc.wait(timeout=5)
                except Exception:
                    logger.debug("[WAVEFORM] Could not reap ffmpeg child", exc_info=True)

    # ── QRunnable entry point ─────────────────────────────────────────

    @Slot()
    def run(self) -> None:  # noqa: D102 (QRunnable override)
        """Decode the media audio on a worker thread and emit the peaks.

        Runs inside the QThreadPool so a long file never freezes the UI; the
        result is delivered through ``signals.finished`` on the GUI thread.
        """
        try:
            # Report the container duration as soon as it is known: the waveform
            # toolbar must enable split/zoom on first selection even when
            # QMediaPlayer does not (re-)emit durationChanged for the file, or
            # when the file carries no audio track at all.
            duration_sec = self._get_duration()
            if duration_sec is not None and duration_sec > 0:
                try:
                    self.signals.duration_ready.emit(self.file_path, duration_sec)
                except RuntimeError:
                    pass  # Window or signal source already closed/deleted

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
                # Equal slices of the whole file: bin i covers [i, i+1) / width of its
                # length. (Fixed-size slices with the remainder piled into the last bin
                # put every point a few % too late on the waveform and in "cut the
                # silence".)
                edges = np.linspace(0, n, self.target_width + 1).astype(np.int64)
                peaks = np.maximum.reduceat(samples_abs, edges[:-1]).astype(np.float32)

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
) -> tuple[float, float, float] | None:
    """Scan file loudness using ffmpeg ebur128 (ITU-R BS.1770-4).

    Returns (integrated_lufs, true_peak_dbfs, auto_gain_db) or None if analysis fails.
    """
    if not os.path.isfile(file_path):
        return None
    ffmpeg = _resolve_binary("ffmpeg")
    if ffmpeg is None:
        logger.debug("[LOUDNESS] ffmpeg not available in PATH")
        return None

    try:
        cmd = [
            *_ffmpeg_cmd(ffmpeg),
            "-nostats", "-nostdin", "-i", file_path,
            "-filter_complex", "ebur128=peak=true",
            "-f", "null", "-",
        ]
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout_sec,
            stdin=subprocess.DEVNULL,
            **_no_window_kwargs(),
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
        """Prepare a LUFS measurement job aiming at ``target_lufs``."""
        super().__init__()
        self.file_path = file_path
        self.target_lufs = target_lufs
        self.signals = _LoudnessSignals()
        self.setAutoDelete(True)

    @Slot()
    def run(self) -> None:
        """Measure LUFS/peak on a worker thread and emit the gain suggestion."""
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
) -> str | None:
    """Render a dynamic-range compressed / normalized media copy using ffmpeg loudnorm.

    For video files: video stream is copied lossless (-c:v copy), audio is compressed.
    For audio files: audio is rendered to lossless 16-bit PCM WAV.
    Returns path to output file in cache directory, or None on failure.
    """
    if not os.path.isfile(file_path):
        return None
    ffmpeg = _resolve_binary("ffmpeg")
    if ffmpeg is None:
        logger.warning("[LOUDNORM] ffmpeg not available in PATH")
        return None

    # Cross-platform standard cache path (Linux ~/.cache, macOS ~/Library/Caches, Windows %LOCALAPPDATA%)
    # QStandardPaths can return an empty string if the application name was not
    # set yet: never fall back to a relative path (it would end up in the CWD,
    # which may be read-only, e.g. Program Files on Windows).
    cache_root = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.CacheLocation) or ""
    if not cache_root:
        cache_root = tempfile.gettempdir()
    cache_dir = Path(cache_root) / "audio"
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logger.warning("[LOUDNORM] Cache directory not writable (%s): using temp dir", exc)
        cache_dir = Path(tempfile.gettempdir()) / "blindcue_audio"
        try:
            cache_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc2:
            logger.error("[LOUDNORM] No writable cache directory: %s", exc2)
            return None

    stem = Path(file_path).stem
    ext = Path(file_path).suffix.lower()
    st = os.stat(file_path)
    cache_sig = f"{file_path}|{st.st_mtime_ns}|{st.st_size}|{target_lufs:.2f}|{peak_ceiling_db:.2f}|{lra_target:.2f}"
    h = hashlib.sha256(cache_sig.encode("utf-8", errors="replace")).hexdigest()[:12]

    video_exts = {".mp4", ".mkv", ".mov", ".webm", ".avi"}
    is_video = ext in video_exts
    out_ext = ext if is_video else ".wav"
    out_path = str(cache_dir / f"{stem}_ebur128_{h}{out_ext}")
    tmp_path = str(cache_dir / f".{stem}_ebur128_{h}.{os.getpid()}.tmp{out_ext}")

    if os.path.isfile(out_path) and os.path.getsize(out_path) > 1000:
        return out_path

    filter_str = f"loudnorm=I={target_lufs}:TP={peak_ceiling_db}:LRA={lra_target}"

    if is_video:
        cmd = [
            *_ffmpeg_cmd(ffmpeg),
            "-y", "-nostats", "-nostdin", "-i", file_path,
            "-c:v", "copy",
            "-af", filter_str,
            "-c:a", "aac", "-b:a", "256k",
            tmp_path,
        ]
    else:
        cmd = [
            *_ffmpeg_cmd(ffmpeg),
            "-y", "-nostats", "-nostdin", "-i", file_path,
            "-af", filter_str,
            "-c:a", "pcm_s16le",
            tmp_path,
        ]

    try:
        subprocess.run(cmd, capture_output=True, check=True, timeout=timeout_sec,
                       stdin=subprocess.DEVNULL, **_no_window_kwargs())
        if os.path.isfile(tmp_path) and os.path.getsize(tmp_path) > 0:
            os.replace(tmp_path, out_path)
            return out_path
    except Exception as exc:
        logger.error("[LOUDNORM] Rendering failed for %s: %s", file_path, exc)
    finally:
        if os.path.isfile(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                logger.debug("[LOUDNORM] Could not remove partial temp output %s", tmp_path, exc_info=True)
    return None


class _DynamicsSignals(QObject):
    finished = Signal(str, str)  # (orig_path, optimized_path)
    error = Signal(str, str)     # (orig_path, err_msg)


class DynamicsOptimizer(QRunnable):
    """Asynchronous loudnorm dynamics compressor running on QThreadPool."""

    def __init__(self, file_path: str, target_lufs: float = -16.0) -> None:
        """Prepare a loudness-normalisation render job for ``file_path``."""
        super().__init__()
        self.file_path = file_path
        self.target_lufs = target_lufs
        self.signals = _DynamicsSignals()
        self.setAutoDelete(True)

    @Slot()
    def run(self) -> None:
        """Render a loudness-normalised copy of the media on a worker thread."""
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


