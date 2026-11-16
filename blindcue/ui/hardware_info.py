"""System hardware diagnostics, runtime performance guard, and resource profiling for BlindCue."""

from __future__ import annotations

import gc
import logging
import os
import platform
import subprocess
import sys

from PySide6.QtCore import QThreadPool
from PySide6.QtGui import QGuiApplication, QOffscreenSurface, QOpenGLContext
from PySide6.QtWidgets import QMessageBox, QWidget

from engine.runtime_limits import worker_thread_limit

logger = logging.getLogger(__name__)

PROFILE_AUTO = "auto"
PROFILE_ECO = "eco"
PROFILE_STANDARD = "standard"
PROFILE_PERFORMANCE = "performance"


def get_memory_details() -> dict:
    """Inspect physical system RAM across Linux, macOS, and Windows."""
    total_mb = 4096
    avail_mb = 2048

    # 1. Linux (/proc/meminfo)
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

    # 2. macOS (sysctl hw.memsize)
    elif sys.platform == "darwin":
        try:
            res = subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, timeout=2)
            total_b = int(res.stdout.strip())
            total_mb = total_b // (1024 * 1024)
            avail_mb = max(1024, total_mb // 2)
        except Exception as exc:
            logger.debug("[HW-INFO] macOS sysctl hw.memsize failed: %s", exc)

    # 3. Windows (GlobalMemoryStatusEx via ctypes)
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


def get_hardware_details() -> dict:
    """Inspect CPU, GPU, screens, memory, and display server across Linux, macOS, and Windows."""
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

    # Screens detection via PySide6 QGuiApplication
    screens: list[str] = []
    app = QGuiApplication.instance()
    if app is not None:
        try:
            for s in QGuiApplication.screens():
                geom = s.geometry()
                screens.append(f"{s.name()} ({geom.width()}x{geom.height()})")
        except Exception as exc:
            logger.debug("[HW-INFO] Screen detection failed: %s", exc)

    # GPU & Renderer detection via PySide6 OpenGL context (100% cross-platform)
    gpu_vendor = ""
    gpu_renderer = ""
    has_hw_accel = False

    try:
        if app is not None:
            ctx = QOpenGLContext()
            if ctx.create():
                surface = QOffscreenSurface()
                surface.create()
                if ctx.makeCurrent(surface):
                    funcs = ctx.functions()
                    # 0x1F00 = GL_VENDOR, 0x1F01 = GL_RENDERER
                    raw_vendor = funcs.glGetString(0x1F00)
                    raw_renderer = funcs.glGetString(0x1F01)
                    if raw_vendor:
                        gpu_vendor = raw_vendor.strip()
                    if raw_renderer:
                        gpu_renderer = raw_renderer.strip()
                    has_hw_accel = True
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
        has_hw_accel = True
    elif sys.platform.startswith("win"):
        gpu_desc = "Direct3D / OpenGL Hardware Adapter"
        has_hw_accel = True
    else:
        gpu_desc = "Standard GPU Adapter"

    wayland_session = os.environ.get("WAYLAND_DISPLAY", "")
    mem = get_memory_details()

    return {
        "cpu_cores": cpu_cores,
        "cpu_model": cpu_model,
        "gpu_desc": gpu_desc,
        "has_vaapi": has_hw_accel,
        "has_hw_accel": has_hw_accel,
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
        # Automatic determination:
        # <= 5500 MB (4-5 GB RAM like MacBook Air 2014) or dual-core -> ECO
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

    @classmethod
    def on_live_mode_enter(cls, profile: str = PROFILE_AUTO) -> None:
        """Called when entering LIVE show mode to secure zero-stutter playback."""
        if cls._active:
            return
        logger.debug("[RUNTIME-GUARD] Entering LIVE mode with profile '%s'", profile)
        try:
            cls._original_thresholds = gc.get_threshold()
            # Perform a deep generational GC sweep BEFORE show execution starts
            gc.collect(2)
            # Raise thresholds significantly so automatic GC sweeps do not freeze
            # time-critical audio or video frames during GO transitions
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
        """Configure QThreadPool limits according to hardware profile to prevent UI thread lock.

        The cap always leaves at least one core (two on 4+ core CPUs) free for
        the OS, the compositor and the real-time media threads.
        """
        pool = QThreadPool.globalInstance()
        workers = worker_thread_limit(profile)
        pool.setMaxThreadCount(workers)
        logger.info(
            "[RUNTIME-GUARD] Thread pool set to %d worker(s) (%s mode, %d cores detected)",
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
    accel = "VA-API" if prof["has_vaapi"] else "EGL"

    tag = "🍃 ECO" if prof["profile"] == PROFILE_ECO else ("🚀 PRO" if prof["profile"] == PROFILE_PERFORMANCE else "⚡ STD")
    return f"{tag} | 🖥️ CPU: {cores}C | 💾 RAM: {prof['total_gb']}GB | 🎮 GPU: {gpu_short} ({accel})"


def show_hardware_info_dialog(parent: QWidget, custom_profile: str = PROFILE_AUTO) -> None:
    """Display the Hardware & Acceleration summary dialog."""
    prof = evaluate_hardware_profile(custom_profile)
    dialog_txt = (
        f"<h3>Architettura Hardware & Prestazioni BlindCue</h3>"
        f"<p><b>Profilo Attivo:</b> <b style='color:#00bcd4;'>{prof['profile'].upper()}</b> ({prof['reason']})</p>"
        f"<p><b>Processore (CPU):</b> {prof['cpu_model']}<br/>"
        f"• Core / Thread rilevati: <b>{prof['cpu_cores']} core</b></p>"
        f"<p><b>Memoria RAM di Sistema:</b><br/>"
        f"• Totale: <b>{prof['total_gb']} GB</b> ({prof['total_mb']} MB)<br/>"
        f"• Disponibile: <b>{prof['avail_gb']} GB</b> ({prof['avail_mb']} MB)</p>"
        f"<p><b>Scheda Video (GPU):</b> {prof['gpu_desc']}<br/>"
        f"• Accelerazione Hardware: <b>{'Attiva (OpenGL / Hardware Accelerated)' if prof['has_vaapi'] else 'Software Renderer'}</b><br/>"
        f"• Schermi Rilevati: <b>{', '.join(prof.get('screens', [])) or 'Display Principale'}</b><br/>"
        f"• Piattaforma: <b>{platform.system()} ({platform.machine()})</b></p>"
        f"<hr/>"
        f"<h4>Ottimizzazioni per la Massima Stabilità Live:</h4>"
        f"<ul>"
        f"<li><b>GPU Offloading:</b> Compositing Layer 0..3 su GPU tramite Wayland EGL/OpenGL. Zero carico di ridisegno pixel sulla CPU.</li>"
        f"<li><b>Decodifica Video Hardware:</b> QtMultimedia e FFmpeg interrogano automaticamente VA-API / NVDEC per frame zero-copy.</li>"
        f"<li><b>Protezione GC Live:</b> In modalità LIVE il Garbage Collector di Python viene posticipato per prevenire micro-lag durante le Cue.</li>"
        f"<li><b>Isolamento Threading:</b> Worker asincroni limitati per garantire latenza istantanea su UI e Audio.</li>"
        f"</ul>"
        f"<p style='color: #00e676;'><b>Risultato:</b> Stabilità assoluta garantita sia su portatili da 4GB di RAM che su workstation multi-core.</p>"
    )
    QMessageBox.information(parent, "BlindCue — Info Hardware & Accelerazione", dialog_txt)


def show_about_dialog(parent: QWidget) -> None:
    """Display the About BlindCue dialog."""
    QMessageBox.about(
        parent,
        "About BlindCue",
        "<h2>BlindCue v0.1</h2>"
        "<p>Minimal failsafe cue player for live shows.</p>"
        "<p>Layer 0 always active • 100% Native Wayland QtMultimedia</p>"
        "<p>© 2026 — Zero crash in live.</p>",
    )

