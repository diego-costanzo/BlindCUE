"""Dialog for Device Routing (Master Audio, Headphone PFL, Video Screen) and Hardware Profiling."""

from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from engine.device_manager import DeviceManager
from ui.hardware_info import (
    PROFILE_AUTO,
    PROFILE_ECO,
    PROFILE_PERFORMANCE,
    PROFILE_STANDARD,
    evaluate_hardware_profile,
)

logger = logging.getLogger(__name__)


class DeviceSettingsDialog(QDialog):
    """Modal dialog for selecting Audio Master/PFL devices, Video Screen, and Hardware Profile."""

    def __init__(self, device_mgr: DeviceManager, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.device_mgr = device_mgr
        self.setWindowTitle("Configurazione Hardware & Uscite di Regia")
        self.setMinimumWidth(560)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)

        self._build_ui()
        self._load_current_values()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        # Title header
        lbl_title = QLabel("⚙️ Dispositivi di Uscita & Ottimizzazione Hardware")
        lbl_title.setStyleSheet("font-size: 15px; font-weight: bold; color: #00bcd4;")
        layout.addWidget(lbl_title)

        # ── 1. Hardware Profile Card ──────────────────────────────────
        group_hw = QGroupBox("⚡ Profilo Hardware · Modalità Adattiva")
        group_hw.setStyleSheet(
            "QGroupBox { font-weight: bold; color: #e0e0e0; border: 1px solid #333946; "
            "border-radius: 6px; margin-top: 8px; padding-top: 14px; background: #181a20; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }"
        )
        l_hw = QVBoxLayout(group_hw)
        l_hw.setSpacing(8)

        # System info readout
        hw_info = self.device_mgr.get_profile_info()
        cpu_clean = hw_info['cpu_model'].strip()[:28].rstrip()
        self._lbl_sys_readout = QLabel(
            f"🖥️ <b>CPU:</b> {hw_info['cpu_cores']} Core ({cpu_clean}) | "
            f"💾 <b>RAM:</b> {hw_info['total_gb']} GB (Disp: {hw_info['avail_gb']} GB) | "
            f"🎮 <b>GPU:</b> {'VA-API Attiva' if hw_info['has_vaapi'] else 'Mesa/EGL'}"
        )
        self._lbl_sys_readout.setStyleSheet("color: #b0bec5; font-size: 11px;")
        l_hw.addWidget(self._lbl_sys_readout)

        row_prof = QHBoxLayout()
        lbl_p_tag = QLabel("Profilo Prestazioni:")
        lbl_p_tag.setStyleSheet("color: #ffffff; font-weight: bold;")
        self._combo_profile = QComboBox()
        self._combo_profile.addItem("Auto (Consigliato — Rilevamento Intelligente)", PROFILE_AUTO)
        self._combo_profile.addItem("🍃 Eco (Muletto / <=4GB RAM / Risparmio Risorse)", PROFILE_ECO)
        self._combo_profile.addItem("⚡ Standard (Bilanciato per Live)", PROFILE_STANDARD)
        self._combo_profile.addItem("🚀 Performance (Workstation Multi-Core / Pro)", PROFILE_PERFORMANCE)
        self._combo_profile.currentIndexChanged.connect(self._on_profile_selection_changed)
        row_prof.addWidget(lbl_p_tag)
        row_prof.addWidget(self._combo_profile, 1)
        l_hw.addLayout(row_prof)

        self._lbl_profile_desc = QLabel()
        self._lbl_profile_desc.setWordWrap(True)
        self._lbl_profile_desc.setStyleSheet(
            "color: #90a4ae; font-size: 11px; background: #131418; "
            "padding: 6px; border-radius: 4px; border: 1px solid #262933;"
        )
        l_hw.addWidget(self._lbl_profile_desc)
        layout.addWidget(group_hw)

        # ── 2. Audio Routing Card ─────────────────────────────────────
        group_audio = QGroupBox("🔊 Routing Uscite Audio di Regia")
        group_audio.setStyleSheet(
            "QGroupBox { font-weight: bold; color: #e0e0e0; border: 1px solid #333946; "
            "border-radius: 6px; margin-top: 8px; padding-top: 14px; background: #181a20; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }"
        )
        l_audio = QVBoxLayout(group_audio)
        l_audio.setSpacing(10)

        # Master Sala
        row_master = QVBoxLayout()
        lbl_master = QLabel("🔊 Master Spettacolo (Impianto Sala / PA Pubblico):")
        lbl_master.setStyleSheet("color: #00e676; font-weight: bold; font-size: 12px;")
        self._combo_master = QComboBox()
        row_master.addWidget(lbl_master)
        row_master.addWidget(self._combo_master)
        l_audio.addLayout(row_master)

        # Monitor PFL Headphones
        row_monitor = QVBoxLayout()
        lbl_monitor = QLabel("🎧 Pre-Ascolto / Monitor (Cuffia Tecnico / PFL):")
        lbl_monitor.setStyleSheet("color: #00bcd4; font-weight: bold; font-size: 12px;")
        self._combo_monitor = QComboBox()
        row_monitor.addWidget(lbl_monitor)
        row_monitor.addWidget(self._combo_monitor)
        l_audio.addLayout(row_monitor)

        lbl_audio_note = QLabel(
            "💡 <i>Suggerimento:</i> Assegna la Cuffia per ascoltare in anteprima i brani nell'Ispettore o nella Scaletta "
            "senza che il pubblico in sala senta nulla. Se usi una sola scheda, entrambi usano l'uscita predefinita."
        )
        lbl_audio_note.setWordWrap(True)
        lbl_audio_note.setStyleSheet("color: #78909c; font-size: 11px;")
        l_audio.addWidget(lbl_audio_note)
        layout.addWidget(group_audio)

        # ── 3. Video Output Card ──────────────────────────────────────
        group_video = QGroupBox("🖥️ Uscita Video Live (Proiettore / Display Esterno)")
        group_video.setStyleSheet(
            "QGroupBox { font-weight: bold; color: #e0e0e0; border: 1px solid #333946; "
            "border-radius: 6px; margin-top: 8px; padding-top: 14px; background: #181a20; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }"
        )
        l_video = QVBoxLayout(group_video)
        l_video.setSpacing(8)

        row_scr = QHBoxLayout()
        lbl_scr = QLabel("Schermo Live Output:")
        lbl_scr.setStyleSheet("color: #ffffff; font-weight: bold;")
        self._combo_screen = QComboBox()
        btn_refresh_screens = QPushButton("🔄 Rileva")
        btn_refresh_screens.setFixedWidth(80)
        btn_refresh_screens.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_refresh_screens.clicked.connect(self._populate_screens)
        row_scr.addWidget(lbl_scr)
        row_scr.addWidget(self._combo_screen, 1)
        row_scr.addWidget(btn_refresh_screens)
        l_video.addLayout(row_scr)

        lbl_video_hint = QLabel(
            "💡 Seleziona il monitor o proiettore collegato. Se c'è un solo schermo, l'uscita si apre in modalità finestra simulata per le prove."
        )
        lbl_video_hint.setWordWrap(True)
        lbl_video_hint.setStyleSheet("color: #78909c; font-size: 11px;")
        l_video.addWidget(lbl_video_hint)
        layout.addWidget(group_video)

        # ── Buttons ───────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        btn_cancel = QPushButton("Annulla")
        btn_cancel.setFixedWidth(100)
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)

        btn_apply = QPushButton("✓ Applica e Salva")
        btn_apply.setFixedWidth(140)
        btn_apply.setStyleSheet(
            "QPushButton { background: #00bcd4; color: #000000; font-weight: bold; border-radius: 4px; padding: 6px; }"
            "QPushButton:hover { background: #26c6da; }"
        )
        btn_apply.clicked.connect(self._on_apply)
        btn_row.addWidget(btn_apply)

        layout.addLayout(btn_row)

    # ── Population & Logic ────────────────────────────────────────────

    def _load_current_values(self) -> None:
        # 1. Profile
        cur_pref = self.device_mgr.get_profile_preference()
        idx = self._combo_profile.findData(cur_pref)
        if idx >= 0:
            self._combo_profile.setCurrentIndex(idx)
        else:
            self._combo_profile.setCurrentIndex(0)
        self._on_profile_selection_changed()

        # 2. Audio Devices
        self._populate_audio_devices()

        # 3. Screens
        self._populate_screens()

    def _populate_audio_devices(self) -> None:
        self._combo_master.clear()
        self._combo_monitor.clear()

        devs = self.device_mgr.get_available_audio_devices()
        cur_master = self.device_mgr.get_master_audio_device()
        cur_monitor = self.device_mgr.get_monitor_audio_device()

        cur_master_id = bytes(cur_master.id()) if cur_master and not cur_master.isNull() else b""
        cur_monitor_id = bytes(cur_monitor.id()) if cur_monitor and not cur_monitor.isNull() else b""

        if not devs:
            self._combo_master.addItem("Nessun dispositivo rilevato (Default)", None)
            self._combo_monitor.addItem("Nessun dispositivo rilevato (Default)", None)
            return

        master_idx = 0
        monitor_idx = 0

        for i, dev in enumerate(devs):
            name = dev.description().strip() or "Audio Device"
            is_def = " (Predefinito)" if dev.isDefault() else ""
            label = f"{name}{is_def}"
            dev_id = bytes(dev.id())

            self._combo_master.addItem(label, dev)
            self._combo_monitor.addItem(label, dev)

            if cur_master_id and dev_id == cur_master_id:
                master_idx = i
            elif not cur_master_id and dev.isDefault():
                master_idx = i

            if cur_monitor_id and dev_id == cur_monitor_id:
                monitor_idx = i
            elif not cur_monitor_id and dev.isDefault():
                monitor_idx = i

        self._combo_master.setCurrentIndex(master_idx)
        self._combo_monitor.setCurrentIndex(monitor_idx)

    def _populate_screens(self) -> None:
        self._combo_screen.clear()
        screens = self.device_mgr.get_available_screens()
        cur_target = self.device_mgr.get_target_screen()
        primary = QGuiApplication.primaryScreen()

        sel_idx = 0
        for i, s in enumerate(screens):
            geo = s.geometry()
            tag = " [Primario / Regia]" if s == primary else " [Esterno / Proiettore]"
            label = f"{s.name()} — {geo.width()}x{geo.height()}{tag}"
            self._combo_screen.addItem(label, s)

            if cur_target is not None and s == cur_target:
                sel_idx = i

        if screens:
            self._combo_screen.setCurrentIndex(sel_idx)

    def _on_profile_selection_changed(self) -> None:
        pref = self._combo_profile.currentData() or PROFILE_AUTO
        info = evaluate_hardware_profile(pref)
        eff = info["profile"]

        if eff == PROFILE_ECO:
            self._lbl_profile_desc.setText(
                "🍃 <b>Modalità ECO / Muletto:</b> Limitazione thread di calcolo a 2 core, gestione memoria "
                "leggera, protezione RAM <= 4GB (perfetta per portatili datati come MacBook Air 2014)."
            )
        elif eff == PROFILE_PERFORMANCE:
            self._lbl_profile_desc.setText(
                "🚀 <b>Modalità PERFORMANCE:</b> Multi-threading completo (fino a 8+ core), precaricamento "
                "istantaneo e massime prestazioni per workstation con GPU dedicata."
            )
        else:
            self._lbl_profile_desc.setText(
                "⚡ <b>Modalità STANDARD:</b> Bilanciamento ottimale tra consumo di risorse e fluidità live."
            )

    def _on_apply(self) -> None:
        # 1. Apply profile
        pref = self._combo_profile.currentData() or PROFILE_AUTO
        self.device_mgr.set_hardware_profile(pref)

        # 2. Apply audio devices
        master_dev = self._combo_master.currentData()
        monitor_dev = self._combo_monitor.currentData()
        self.device_mgr.set_master_audio_device(master_dev)
        self.device_mgr.set_monitor_audio_device(monitor_dev)

        # 3. Apply screen
        screen = self._combo_screen.currentData()
        if screen is not None:
            self.device_mgr.set_target_screen(screen)

        self.accept()
