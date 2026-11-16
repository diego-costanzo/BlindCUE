"""CPU / thread budgeting shared by the UI and the media engines.

BlindCue runs on stage machines that must stay responsive for the operating
system and for the live audio/video pipeline.  Saturating every core with
background analysis (waveform, loudness, normalisation) causes dropped frames
and audio glitches, so all worker pools and child processes are capped here.

The budget always keeps at least one core free (two on 4+ core machines) for
the OS, the compositor and the real-time media threads.

Note on GPU: FFmpeg has **no GPU audio encoders**.  Audio gain/normalisation
is inherently CPU work; the GPU is only used for video decode/encode (VA-API,
NVDEC, VideoToolbox, D3D11VA) by QtMultimedia and FFmpeg's own ``-hwaccel``.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess

logger = logging.getLogger(__name__)

# Cores never handed to BlindCue background work.
_RESERVED_CORES_MIN = 1
_RESERVED_CORES_BIG = 2
_BIG_MACHINE_CORES = 4


def cpu_count() -> int:
    """Physical/logical CPU count, never below 1."""
    try:
        return max(1, os.cpu_count() or 1)
    except Exception:
        return 1


def _usable_cores(cores: int | None = None) -> int:
    total = cores if cores is not None else cpu_count()
    reserve = _RESERVED_CORES_BIG if total >= _BIG_MACHINE_CORES else _RESERVED_CORES_MIN
    return max(1, total - reserve)


def worker_thread_limit(profile: str | None = None, cores: int | None = None) -> int:
    """Maximum number of *background* workers BlindCue may run at once.

    ``profile`` is one of ``eco`` / ``standard`` / ``performance`` (``auto``
    resolves to standard here; the profiling module picks the real one).
    """
    usable = _usable_cores(cores)
    if profile == "eco":
        return 1
    if profile == "performance":
        return max(2, min(usable, 6))
    return max(1, min(usable, 4))


def ffmpeg_thread_limit(cores: int | None = None) -> int:
    """Threads handed to a single ffmpeg/ffprobe child process."""
    return max(1, min(4, _usable_cores(cores)))


def ffmpeg_thread_args(cores: int | None = None) -> list[str]:
    """FFmpeg flags that cap both decoding and filter-graph threads."""
    n = ffmpeg_thread_limit(cores)
    return ["-threads", str(n), "-filter_threads", str(n)]


def low_priority_prefix() -> list[str]:
    """Wrap a command so it runs at low CPU priority on POSIX systems.

    Uses the external ``nice`` binary instead of ``preexec_fn``: the latter is
    documented as unsafe in multi-threaded programs (BlindCue is always
    threaded), because it runs between ``fork`` and ``exec``.
    """
    if os.name == "nt":
        return []
    nice = shutil.which("nice")
    return [nice, "-n", "15"] if nice else []


def child_process_kwargs() -> dict[str, object]:
    """Extra keyword arguments for ``subprocess`` on the current platform.

    On Windows this hides the console window (which would otherwise steal
    keyboard focus from the operator mid-show) and lowers the child priority
    so encoding never starves the live pipeline.
    """
    if os.name != "nt":
        return {}
    flags = 0
    flags |= getattr(subprocess, "CREATE_NO_WINDOW", 0)
    flags |= getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0)
    return {"creationflags": flags} if flags else {}
