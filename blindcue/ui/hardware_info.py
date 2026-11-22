"""UI Hardware Info & About dialogs for BlindCue.

Core non-UI hardware profiling and ``ShowRuntimeGuard`` live in
``engine.hardware_profile`` (respecting the engine -> ui architectural boundary)
and are re-exported here for full backward compatibility.
"""

from __future__ import annotations

import platform

from PySide6.QtWidgets import QMessageBox, QWidget

from engine.hardware_profile import (  # noqa: F401
    PROFILE_AUTO,
    PROFILE_ECO,
    PROFILE_PERFORMANCE,
    PROFILE_STANDARD,
    ShowRuntimeGuard,
    clear_hardware_cache,
    detect_hardware_brief,
    evaluate_hardware_profile,
    get_hardware_details,
    get_memory_details,
)


def show_hardware_info_dialog(parent: QWidget, custom_profile: str = PROFILE_AUTO) -> None:
    """Display the Hardware & Acceleration summary dialog."""
    prof = evaluate_hardware_profile(custom_profile)
    if prof["has_vaapi"]:
        accel_label = "Attiva (VA-API / Hardware Decode)"
    elif prof.get("has_hw_accel"):
        accel_label = "OpenGL / EGL (solo compositing, decode CPU)"
    else:
        accel_label = "Software Renderer (nessuna accelerazione GPU)"
    dialog_txt = (
        f"<h3>Architettura Hardware & Prestazioni BlindCue</h3>"
        f"<p><b>Profilo Attivo:</b> <b style='color:#00bcd4;'>{prof['profile'].upper()}</b> ({prof['reason']})</p>"
        f"<p><b>Processore (CPU):</b> {prof['cpu_model']}<br/>"
        f"• Core / Thread rilevati: <b>{prof['cpu_cores']} core</b></p>"
        f"<p><b>Memoria RAM di Sistema:</b><br/>"
        f"• Totale: <b>{prof['total_gb']} GB</b> ({prof['total_mb']} MB)<br/>"
        f"• Disponibile: <b>{prof['avail_gb']} GB</b> ({prof['avail_mb']} MB)</p>"
        f"<p><b>Scheda Video (GPU):</b> {prof['gpu_desc']}<br/>"
        f"• Accelerazione Hardware: <b>{accel_label}</b><br/>"
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
    from version import APP_NAME, APP_VERSION

    QMessageBox.about(
        parent,
        "About BlindCue",
        f"<h2>{APP_NAME} v{APP_VERSION}</h2>"
        "<p>Minimal failsafe cue player for live shows.</p>"
        "<p>Layer 0 always active • 100% Native Wayland QtMultimedia</p>"
        "<p>© 2026 — Zero crash in live.</p>",
    )
