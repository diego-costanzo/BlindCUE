"""Hardware diagnostics, real VA-API probing, and runtime performance guard for BlindCue.

Lives under ``engine/`` so engine services (such as ``DeviceManager``) can query
hardware profiles and control ``ShowRuntimeGuard`` without importing ``ui/``.
Pure open-source probes only (``/proc``, Qt OpenGL, optional open-source ``vainfo``).
"""

from __future__ import annotations

import gc
import logging
import os
import platform
import shutil
import subprocess
import sys

from PySide6.QtCore import QThread, QThreadPool
from PySide6.QtGui import QGuiApplication, QOffscreenSurface, QOpenGLContext

from engine.runtime_limits import child_process_kwargs, worker_thread_limit

logger = logging.getLogger(__name__)

PROFILE_AUTO = "auto"
PROFILE_ECO = "eco"
PROFILE_STANDARD = "standard"
PROFILE_PERFORMANCE = "performance"

_SW_RENDERER_MARKERS = ("llvmpipe", "softpipe", "swrast", "swiftshader", "microsoft basic render")

# Static probes (CPU model, GPU OpenGL strings, VA-API availability) are cached
# once per process so creating QOpenGLContext + QOffscreenSurface never stalls
# the GUI thread repeatedly mid-show.
_static_hw_cache: dict[str, object] | None = None


def clear_hardware_cache() -> None:
    """Clear the cached static hardware probe (primarily for tests)."""
    global _static_hw_cache
    _static_hw_cache = None


def get_memory_details() -> dict:
    """Inspect physical system RAM across Linux, macOS, and Windows."""
    total_mb = 4096
    avail_mb = 2048

    if sys.platform.startswith("linux"):
        try:
            with open("/proc/meminfo", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        total_mb = int(line.split()[1]) // 1024
                    elif line.startswith("MemAvailable:"):
                        avail_mb = int(line.split()[1]) // 1024
        except Exception as exc:
            logger.debug("[HW-INFO] Could not read /proc/meminfo: %s", exc)

    elif sys.platform == "darwin":
        try:
            res = subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, timeout=2)
            total_b = int(res.stdout.strip())
            total_mb = total_b // (1024 * 1024)
            avail_mb = max(1024, total_mb // 2)
        except Exception as exc:
            logger.debug("[HW-INFO] macOS sysctl hw.memsize failed: %s", exc)

    elif sys.platform.startswith("win"):
        try:
            import ctypes

            class _MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            stat = _MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(_MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                total_mb = int(stat.ullTotalPhys // (1024 * 1024))
                avail_mb = int(stat.ullAvailPhys // (1024 * 1024))
        except Exception as exc:
            logger.debug("[HW-INFO] Windows GlobalMemoryStatusEx failed: %s", exc)

    return {
        "total_mb": total_mb,
        "avail_mb": avail_mb,
        "total_gb": round(total_mb / 1024.0, 1),
        "avail_gb": round(avail_mb / 1024.0, 1),
    }


def _probe_linux_vaapi(is_software_gl: bool) -> bool:
    """Detect genuine VA-API hardware decode capability on Linux (open-source vainfo/DRM)."""
    if is_software_gl:
        return False
    vainfo = shutil.which("vainfo")
    if vainfo:
        try:
            res = subprocess.run(
                [vainfo],
                capture_output=True,
                text=True,
                timeout=2,
                stdin=subprocess.DEVNULL,
                **child_process_kwargs(),
            )
            combined = (res.stdout or "") + "\n" + (res.stderr or "")
            if res.returncode == 0 and "VAEntrypointVLD" in combined:
                return True
            return False
        except Exception as exc:
            logger.debug("[HW-INFO] vainfo probe failed: %s", exc)

    # Fallback when vainfo CLI is not installed: require a DRM render node
    return os.path.exists("/dev/dri/renderD128")


def _probe_static_hardware() -> dict[str, object]:
    """Probe CPU model, OpenGL renderer, and VA-API once and memoize."""
    global _static_hw_cache
    if _static_hw_cache is not None:
        return _static_hw_cache

    cpu_cores = os.cpu_count() or 1
    cpu_model = platform.processor() or ""
    if not cpu_model.strip() or "x86" in cpu_model or "AMD64" in cpu_model:
        if sys.platform.startswith("linux"):
            try:
                with open("/proc/cpuinfo", encoding="utf-8") as f:
                    for line in f:
                        if "model name" in line:
                            cpu_model = line.split(":", 1)[1].strip()
                            break
            except Exception:
                logger.debug("[HW] Could not read /proc/cpuinfo", exc_info=True)
        elif sys.platform.startswith("win"):
            cpu_model = os.environ.get("PROCESSOR_IDENTIFIER", cpu_model)
    if not cpu_model.strip():
        cpu_model = f"{platform.machine()} ({platform.system()})"

    # GPU & Renderer detection via PySide6 OpenGL context (100% open-source & cross-platform)
    gpu_vendor = ""
    gpu_renderer = ""
    has_hw_gl = False
    is_software_gl = False

    app = QGuiApplication.instance()
    try:
        if app is not None and app.platformName() != "offscreen":
            ctx = QOpenGLContext()
            if ctx.create():
                surface = QOffscreenSurface()
                surface.create()
                if ctx.makeCurrent(surface):
                    funcs = ctx.functions()
                    raw_vendor = funcs.glGetString(0x1F00)
                    raw_renderer = funcs.glGetString(0x1F01)
                    if raw_vendor:
                        gpu_vendor = str(raw_vendor).strip()
                    if raw_renderer:
                        gpu_renderer = str(raw_renderer).strip()
                    renderer_lc = f"{gpu_vendor} {gpu_renderer}".lower()
                    is_software_gl = any(m in renderer_lc for m in _SW_RENDERER_MARKERS)
                    has_hw_gl = bool(gpu_renderer or gpu_vendor) and not is_software_gl
                    ctx.doneCurrent()
                surface.destroy()
    except Exception as exc:
        logger.debug("[HW-INFO] OpenGL hardware query failed: %s", exc)

    if gpu_vendor and gpu_renderer:
        gpu_desc = gpu_renderer if gpu_vendor in gpu_renderer else f"{gpu_vendor} {gpu_renderer}"
    elif gpu_renderer:
        gpu_desc = gpu_renderer
    elif sys.platform == "darwin":
        gpu_desc = f"Apple Metal / GPU ({platform.machine()})"
        has_hw_gl = True
    elif sys.platform.startswith("win"):
        gpu_desc = "Direct3D / OpenGL Hardware Adapter"
        has_hw_gl = True
    else:
        gpu_desc = "Software / Headless Renderer" if (app is not None and app.platformName() == "offscreen") else "Standard GPU Adapter"

    if sys.platform.startswith("linux"):
        has_vaapi = _probe_linux_vaapi(is_software_gl or (app is not None and app.platformName() == "offscreen"))
    else:
        has_vaapi = has_hw_gl

    _static_hw_cache = {
        "cpu_cores": cpu_cores,
        "cpu_model": cpu_model,
        "gpu_desc": gpu_desc,
        "has_vaapi": has_vaapi,
        "has_hw_accel": has_hw_gl or has_vaapi,
    }
    return _static_hw_cache


def get_hardware_details() -> dict:
    """Inspect CPU, GPU, screens, memory, and display server across Linux, macOS, and Windows."""
    static = _probe_static_hardware()

    # Screens & free RAM can change dynamically during runtime
    screens: list[str] = []
    app = QGuiApplication.instance()
    if app is not None:
        try:
            for s in QGuiApplication.screens():
                geom = s.geometry()
                screens.append(f"{s.name()} ({geom.width()}x{geom.height()})")
        except Exception as exc:
            logger.debug("[HW-INFO] Screen detection failed: %s", exc)

    wayland_session = os.environ.get("WAYLAND_DISPLAY", "")
    mem = get_memory_details()

    return {
        "cpu_cores": static["cpu_cores"],
        "cpu_model": static["cpu_model"],
        "gpu_desc": static["gpu_desc"],
        "has_vaapi": static["has_vaapi"],
        "has_hw_accel": static["has_hw_accel"],
        "screens": screens,
        "screen_count": len(screens),
        "wayland_session": wayland_session,
        "os_name": platform.system(),
        "total_gb": mem["total_gb"],
        "avail_gb": mem["avail_gb"],
        "total_mb": mem["total_mb"],
        "avail_mb": mem["avail_mb"],
    }


def evaluate_hardware_profile(custom_preference: str = PROFILE_AUTO) -> dict:
    """Determine performance profile based on system resources or explicit user override."""
    hw = get_hardware_details()
    pref = (custom_preference or PROFILE_AUTO).strip().lower()

    if pref in (PROFILE_ECO, PROFILE_STANDARD, PROFILE_PERFORMANCE):
        active = pref
        reason = "Scelta manuale operatore"
    else:
        if hw["total_mb"] <= 5500 or hw["cpu_cores"] <= 2:
            active = PROFILE_ECO
            reason = f"Auto (RAM {hw['total_gb']}GB / {hw['cpu_cores']} Core: profilo salva-memoria attivo)"
        elif hw["total_mb"] >= 14000 and hw["cpu_cores"] >= 8:
            active = PROFILE_PERFORMANCE
            reason = f"Auto (RAM {hw['total_gb']}GB / {hw['cpu_cores']} Core: massime prestazioni e multi-screen)"
        else:
            active = PROFILE_STANDARD
            reason = f"Auto (RAM {hw['total_gb']}GB / {hw['cpu_cores']} Core: bilanciamento standard)"

    return {
        "profile": active,
        "reason": reason,
        "cpu_cores": hw["cpu_cores"],
        "cpu_model": hw["cpu_model"],
        "gpu_desc": hw["gpu_desc"],
        "has_vaapi": hw["has_vaapi"],
        "has_hw_accel": hw["has_hw_accel"],
        "screens": hw.get("screens", []),
        "screen_count": hw.get("screen_count", 0),
        "total_gb": hw["total_gb"],
        "avail_gb": hw["avail_gb"],
        "total_mb": hw["total_mb"],
        "avail_mb": hw["avail_mb"],
    }


class ShowRuntimeGuard:
    """Live performance guard – protects live show playback against Python GC pauses and thread starvation."""

    _active: bool = False
    _original_thresholds: tuple[int, int, int] = (2000, 10, 10)
    _analysis_pool: QThreadPool | None = None

    @classmethod
    def analysis_pool(cls) -> QThreadPool:
        """Return the dedicated pool used by BlindCue background analysis."""
        if cls._analysis_pool is None:
            cls._analysis_pool = QThreadPool()
            cls._analysis_pool.setMaxThreadCount(worker_thread_limit())
        return cls._analysis_pool

    @classmethod
    def on_live_mode_enter(cls, profile: str = PROFILE_AUTO) -> None:
        """Called when entering LIVE show mode to secure zero-stutter playback."""
        if cls._active:
            return
        logger.debug("[RUNTIME-GUARD] Entering LIVE mode with profile '%s'", profile)
        try:
            cls._original_thresholds = gc.get_threshold()
            gc.collect(2)
            gc.set_threshold(50000, 50, 50)
            cls._active = True
            logger.info("[RUNTIME-GUARD] Live Show Guard ACTIVE (GC deferred: %s)", gc.get_threshold())
        except Exception as exc:
            logger.warning("[RUNTIME-GUARD] Could not adjust GC thresholds: %s", exc)

    @classmethod
    def on_live_mode_exit(cls) -> None:
        """Called when exiting LIVE mode back to project mode."""
        if not cls._active:
            return
        try:
            gc.set_threshold(*cls._original_thresholds)
            gc.collect()
            cls._active = False
            logger.info("[RUNTIME-GUARD] Live Show Guard RESTORED to standard GC: %s", cls._original_thresholds)
        except Exception as exc:
            logger.warning("[RUNTIME-GUARD] Could not restore GC thresholds: %s", exc)

    @classmethod
    def configure_thread_pool(cls, profile: str) -> None:
        """Cap BlindCue's background pool according to the hardware profile."""
        workers = worker_thread_limit(profile)
        cls.analysis_pool().setMaxThreadCount(workers)
        QThreadPool.globalInstance().setMaxThreadCount(QThread.idealThreadCount())
        logger.info(
            "[RUNTIME-GUARD] Analysis pool set to %d worker(s) (%s mode, %d cores detected)",
            workers, profile.upper(), os.cpu_count() or 1,
        )


def detect_hardware_brief(custom_profile: str = PROFILE_AUTO) -> str:
    """Return compact CPU/GPU/RAM summary string for the status bar."""
    prof = evaluate_hardware_profile(custom_profile)
    cores = prof["cpu_cores"]
    gpu = prof["gpu_desc"]
    if "Intel" in gpu:
        gpu_short = "Intel Graphics"
    elif "NVIDIA" in gpu or "GeForce" in gpu:
        gpu_short = "NVIDIA GPU"
    elif "AMD" in gpu or "Radeon" in gpu:
        gpu_short = "AMD Radeon"
    else:
        gpu_short = gpu[:18]
    accel = "VA-API" if prof["has_vaapi"] else ("EGL" if prof.get("has_hw_accel") else "SW")

    tag = "🍃 ECO" if prof["profile"] == PROFILE_ECO else ("🚀 PRO" if prof["profile"] == PROFILE_PERFORMANCE else "⚡ STD")
    return f"{tag} | 🖥️ CPU: {cores}C | 💾 RAM: {prof['total_gb']}GB | 🎮 GPU: {gpu_short} ({accel})"
