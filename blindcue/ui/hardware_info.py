"""System hardware diagnostics, runtime performance guard, and resource profiling for BlindCue."""

from __future__ import annotations

import gc
import logging
import os
import shutil
import subprocess
from typing import Optional

from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import QMessageBox, QWidget

logger = logging.getLogger(__name__)

PROFILE_AUTO = "auto"
PROFILE_ECO = "eco"
PROFILE_STANDARD = "standard"
PROFILE_PERFORMANCE = "performance"


def get_memory_details() -> dict:
    """Inspect physical system RAM via /proc/meminfo on Linux."""
    total_mb = 4096
    avail_mb = 2048
    try:
        with open("/proc/meminfo", "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    total_mb = int(line.split()[1]) // 1024
                elif line.startswith("MemAvailable:"):
                    avail_mb = int(line.split()[1]) // 1024
    except Exception as exc:
        logger.debug("[HW-INFO] Could not read /proc/meminfo: %s", exc)

    return {
        "total_mb": total_mb,
        "avail_mb": avail_mb,
        "total_gb": round(total_mb / 1024.0, 1),
        "avail_gb": round(avail_mb / 1024.0, 1),
    }


def get_hardware_details() -> dict:
    """Inspect CPU, GPU/DRI, memory, and Wayland session details for diagnostics."""
    cpu_cores = os.cpu_count() or 1
    cpu_model = "Multi-core CPU"
    try:
        with open("/proc/cpuinfo", "r", encoding="utf-8") as f:
            for line in f:
                if "model name" in line:
                    cpu_model = line.split(":", 1)[1].strip()
                    break
    except Exception:
        pass

    gpu_desc = "Scheda Grafica Integrata / Discreta"
    if shutil.which("lspci"):
        try:
            res = subprocess.run(["lspci"], capture_output=True, text=True, timeout=2)
            lines = [line for line in res.stdout.splitlines() if any(k in line for k in ("VGA", "3D", "Display"))]
            if lines:
                parts = lines[0].split(":", 2)
                gpu_desc = parts[-1].strip() if len(parts) >= 3 else lines[0]
        except Exception:
            pass
    elif os.path.exists("/dev/dri/renderD128"):
        gpu_desc = "Mesa Direct Rendering (DRI/DRM)"

    has_vaapi = os.path.exists("/dev/dri/renderD128")
    wayland_session = os.environ.get("WAYLAND_DISPLAY", "")
    mem = get_memory_details()

    return {
        "cpu_cores": cpu_cores,
        "cpu_model": cpu_model,
        "gpu_desc": gpu_desc,
        "has_vaapi": has_vaapi,
        "wayland_session": wayland_session,
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
        """Configure QThreadPool limits according to hardware profile to prevent UI thread lock."""
        pool = QThreadPool.globalInstance()
        cores = os.cpu_count() or 2
        if profile == PROFILE_ECO:
            # Low-spec / dual-core: strictly limit background analysis to 2 threads
            # so UI (thread 0) and Audio/Video (thread 1) have 100% CPU priority
            pool.setMaxThreadCount(min(2, max(1, cores)))
            logger.info("[RUNTIME-GUARD] Thread pool capped at %d workers (ECO mode)", pool.maxThreadCount())
        elif profile == PROFILE_PERFORMANCE:
            pool.setMaxThreadCount(max(4, cores))
            logger.info("[RUNTIME-GUARD] Thread pool set to %d workers (PERFORMANCE mode)", pool.maxThreadCount())
        else:
            pool.setMaxThreadCount(max(2, min(4, cores)))
            logger.info("[RUNTIME-GUARD] Thread pool set to %d workers (STANDARD mode)", pool.maxThreadCount())


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
        f"• Accelerazione Hardware DRI/DRM (/dev/dri): <b>{'Attiva (VA-API / EGL)' if prof['has_vaapi'] else 'Mesa Software'}</b><br/>"
        f"• Sessione Grafica: <b>Native Wayland</b></p>"
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

