"""Dialog displaying Web Remote pairing (QR code, LAN IPs, ports), Director Monitor, OSC status, and PIN security controls."""

from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from services.remote_manager import RemoteManager

logger = logging.getLogger("blindcue.remote_ui")


class RemoteControlDialog(QDialog):
    """Setup, PIN Security, and Live Monitor dialog for LAN Web Remote, Director Monitor, and OSC automation."""

    def __init__(self, remote_mgr: RemoteManager, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._remote_mgr = remote_mgr
        self.setWindowTitle("📡 Controllo Remoto LAN (Web & OSC) — BlindCUE")
        self.resize(880, 710)
        self.setMinimumSize(840, 660)

        self._build_ui()
        self._update_display()

        # Connect live updates
        self._remote_mgr.activity_updated.connect(self._update_display)

    def _build_ui(self) -> None:
        self.setStyleSheet("""
            QDialog {
                background-color: #0c1017;
                color: #f8fafc;
            }
            QGroupBox {
                background-color: #151d2c;
                border: 1px solid #283548;
                border-radius: 8px;
                margin-top: 12px;
                padding: 12px;
                font-weight: bold;
                font-size: 11px;
                color: #38bdf8;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 6px;
                background: transparent;
            }
            QGroupBox QLabel, QGroupBox QCheckBox {
                background: transparent;
            }
            QTabWidget::pane {
                border: 1px solid #283548;
                background-color: #151d2c;
                border-radius: 8px;
                padding: 12px;
            }
            QTabBar::tab {
                background: #0c1017;
                color: #94a3b8;
                border: 1px solid #283548;
                border-bottom: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                padding: 8px 18px;
                font-weight: bold;
                font-size: 12px;
                margin-right: 4px;
            }
            QTabBar::tab:selected {
                background: #151d2c;
                color: #38bdf8;
                border-color: #38bdf8;
            }
            QTabBar::tab:hover {
                color: #f1f5f9;
            }
            QLabel {
                color: #cbd5e1;
                background: transparent;
            }
            QPushButton {
                background-color: #263346;
                color: #ffffff;
                border: 1px solid #3b4d66;
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #33445c;
                border-color: #64748b;
            }
            QPushButton:pressed {
                background-color: #0284c7;
            }
            QLineEdit, QSpinBox {
                background-color: #0b1120;
                color: #ffffff;
                border: 1px solid #3b4d66;
                border-radius: 5px;
                padding: 4px 8px;
                font-size: 12px;
            }
            QCheckBox {
                color: #f1f5f9;
                font-size: 12px;
                font-weight: bold;
                spacing: 8px;
                background: transparent;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                background-color: #0b1120;
                border: 1px solid #475569;
                border-radius: 4px;
            }
            QCheckBox::indicator:hover {
                border-color: #38bdf8;
            }
            QCheckBox::indicator:checked {
                background-color: #0284c7;
                border-color: #38bdf8;
            }
        """)

        main_lay = QVBoxLayout(self)
        main_lay.setContentsMargins(16, 16, 16, 16)
        main_lay.setSpacing(10)

        # ── Header Banner with Master Toggle ──
        header = QHBoxLayout()
        header.setSpacing(14)

        header_v = QVBoxLayout()
        header_v.setSpacing(2)
        lbl_title = QLabel("📡 CONTROLLO REMOTO IN RETE LOCALE (LAN REGIA)")
        lbl_title.setStyleSheet("font-size: 15px; font-weight: 900; color: #38bdf8; letter-spacing: 0.5px; background: transparent;")
        lbl_desc = QLabel("Telecomando Operatore (GO/Pause/Panic), Monitor Regista (Sola Lettura) e Server OSC per automazione.")
        lbl_desc.setStyleSheet("font-size: 11px; color: #94a3b8; background: transparent;")
        header_v.addWidget(lbl_title)
        header_v.addWidget(lbl_desc)
        header.addLayout(header_v, stretch=1)

        self.btn_master_toggle = QPushButton("🔴 SERVIZI REMOTI: DISATTIVATI (Avvia)")
        self.btn_master_toggle.setFixedHeight(36)
        self.btn_master_toggle.setMinimumWidth(280)
        self.btn_master_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_master_toggle.clicked.connect(self._toggle_master_services)
        header.addWidget(self.btn_master_toggle, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        main_lay.addLayout(header)

        # ── Central Tabs ──
        self.tabs = QTabWidget()

        # Tab 1: Telecomando Operatore
        self.tab_operator = QWidget()
        self._build_operator_tab()
        self.tabs.addTab(self.tab_operator, "📱 Telecomando Operatore (Master LIVE)")

        # Tab 2: Monitor Regista (Sola Lettura)
        self.tab_director = QWidget()
        self._build_director_tab()
        self.tabs.addTab(self.tab_director, "👁️ Monitor Regista (Sola Lettura)")

        # Tab 3: Configurazione Porte & OSC
        self.tab_osc = QWidget()
        self._build_osc_tab()
        self.tabs.addTab(self.tab_osc, "🎛️ Automazione OSC && Porte")

        main_lay.addWidget(self.tabs, stretch=1)

        # ── Group: Sicurezza & Protezione Accessi (Anti-Burlone) ──
        grp_sec = QGroupBox("🛡️ SICUREZZA REGIA — PROTEZIONE PIN (ANTI-BURLONE)")
        sec_lay = QVBoxLayout(grp_sec)
        sec_lay.setSpacing(8)

        sec_top_row = QHBoxLayout()
        sec_top_row.setSpacing(12)

        self.chk_pin = QCheckBox("Proteggi con Codice PIN a 6 Cifre")
        self.chk_pin.setChecked(self._remote_mgr.is_pin_enabled())
        self.chk_pin.toggled.connect(self._on_pin_settings_changed)
        sec_top_row.addWidget(self.chk_pin)

        lbl_pin_lbl = QLabel("PIN Attuale:")
        lbl_pin_lbl.setStyleSheet("font-weight: bold; color: #94a3b8;")
        sec_top_row.addWidget(lbl_pin_lbl)

        self.txt_pin = QLineEdit(self._remote_mgr.get_pin())
        self.txt_pin.setMaxLength(6)
        self.txt_pin.setFixedWidth(120)
        self.txt_pin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.txt_pin.setStyleSheet("""
            QLineEdit {
                background-color: #060a12;
                color: #38bdf8;
                border: 2px solid #0284c7;
                border-radius: 6px;
                font-family: 'DejaVu Sans Mono', 'Liberation Mono', 'Roboto Mono', 'Ubuntu Mono', 'monospace', monospace;
                font-size: 15px;
                font-weight: 900;
                letter-spacing: 3px;
                padding: 2px 4px;
            }
        """)
        self.txt_pin.textChanged.connect(self._on_pin_settings_changed)
        sec_top_row.addWidget(self.txt_pin)

        self.btn_new_pin = QPushButton("🎲 Nuovo PIN Casuale")
        self.btn_new_pin.setToolTip("Genera un nuovo codice PIN casuale a 6 cifre e revoca le sessioni precedenti")
        self.btn_new_pin.clicked.connect(self._generate_new_pin)
        sec_top_row.addWidget(self.btn_new_pin)

        self.btn_kick_all = QPushButton("⛔ Disconnetti Tutti")
        self.btn_kick_all.setStyleSheet("background-color: #450a0a; color: #f87171; border: 1px solid #991b1b; font-weight: bold;")
        self.btn_kick_all.setToolTip("Sbatte fuori all'istante tutti i dispositivi connessi")
        self.btn_kick_all.clicked.connect(self._kick_all_clients)
        sec_top_row.addWidget(self.btn_kick_all)

        sec_top_row.addStretch()
        sec_lay.addLayout(sec_top_row)

        self.chk_qr_pin = QCheckBox("Includi PIN nel codice QR (Accesso immediato con fotocamera)")
        self.chk_qr_pin.setChecked(self._remote_mgr.is_qr_pin_included())
        self.chk_qr_pin.toggled.connect(self._on_pin_settings_changed)
        sec_lay.addWidget(self.chk_qr_pin)

        lbl_sec_tip = QLabel(
            "💡 <b>Massima Tranquillità in Teatro:</b> Inquadrando il monitor con lo smartphone si entra all'istante senza digitare nulla. "
            "Chiunque altro sulla LAN che tenti di accedere via browser troverà il tastierino PIN casuale a 6 cifre con blocco forzatura dopo 5 errori."
        )
        lbl_sec_tip.setWordWrap(True)
        lbl_sec_tip.setStyleSheet("font-size: 11px; color: #94a3b8; line-height: 1.4; background: transparent;")
        sec_lay.addWidget(lbl_sec_tip)

        main_lay.addWidget(grp_sec)

        # ── Bottom Bar ──
        bottom_row = QHBoxLayout()

        self.lbl_clients_count = QLabel("📱 Client Web connessi: 0")
        self.lbl_clients_count.setStyleSheet("font-weight: bold; color: #94a3b8; font-size: 11px; background: transparent;")
        bottom_row.addWidget(self.lbl_clients_count)

        bottom_row.addStretch()

        btn_close = QPushButton("Chiudi")
        btn_close.setMinimumWidth(110)
        btn_close.clicked.connect(self.accept)
        bottom_row.addWidget(btn_close)

        main_lay.addLayout(bottom_row)

    def _build_operator_tab(self) -> None:
        """Build UI for Operator / Technician Web Remote."""
        lay = QHBoxLayout(self.tab_operator)
        lay.setSpacing(16)

        # QR Box
        qr_box = QVBoxLayout()
        qr_box.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.qr_frame_op = QFrame()
        self.qr_frame_op.setFixedSize(170, 170)
        self.qr_frame_op.setStyleSheet("background: #ffffff; border-radius: 10px; border: 2px solid #38bdf8;")
        qr_inner = QVBoxLayout(self.qr_frame_op)
        qr_inner.setContentsMargins(4, 4, 4, 4)

        self.lbl_qr_op = QLabel()
        self.lbl_qr_op.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_qr_op.setFixedSize(160, 160)
        self.lbl_qr_op.setStyleSheet("background: #ffffff;")
        qr_inner.addWidget(self.lbl_qr_op)
        qr_box.addWidget(self.qr_frame_op)

        lbl_scan_op = QLabel("Inquadra con Smartphone\nper aprire il Telecomando LIVE")
        lbl_scan_op.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_scan_op.setStyleSheet("font-size: 10px; color: #94a3b8; font-weight: bold; background: transparent;")
        qr_box.addWidget(lbl_scan_op)

        lay.addLayout(qr_box)

        # Info & Details
        info_lay = QVBoxLayout()
        info_lay.setSpacing(8)

        lbl_op_title = QLabel("📱 TELECOMANDO MASTER LIVE (OPERATORE)")
        lbl_op_title.setStyleSheet("font-size: 14px; font-weight: 800; color: #38bdf8; background: transparent;")
        info_lay.addWidget(lbl_op_title)

        lbl_op_desc = QLabel(
            "Ideale per il tecnico sul palco o in sala durante le prove e il montaggio. "
            "Offre il controllo completo sull'emissione dei media."
        )
        lbl_op_desc.setWordWrap(True)
        lbl_op_desc.setStyleSheet("font-size: 11px; color: #cbd5e1; background: transparent;")
        info_lay.addWidget(lbl_op_desc)

        features_box = QFrame()
        features_box.setObjectName("op_features_card")
        features_box.setStyleSheet("""
            QFrame#op_features_card {
                background-color: #0b1120;
                border: 1px solid #233147;
                border-radius: 8px;
                padding: 10px;
            }
            QFrame#op_features_card QLabel {
                background: transparent;
                border: none;
                font-size: 11px;
                color: #e2e8f0;
                padding: 2px 0px;
            }
        """)
        feat_lay = QVBoxLayout(features_box)
        feat_lay.setSpacing(4)
        feat_lay.addWidget(QLabel("✅ <b>Pulsante GO tattile gigante</b> con vibrazione aptica"))
        feat_lay.addWidget(QLabel("✅ <b>Monitor Cue in onda</b> con barra countdown in tempo reale"))
        feat_lay.addWidget(QLabel("✅ <b>Pulsanti di emergenza:</b> Pausa/Riprendi, Blackout e PANIC 0ms"))
        feat_lay.addWidget(QLabel("✅ <b>Scaletta completa:</b> navigazione rapida e lancio diretto [ ▶ GO ] per singola Cue"))
        info_lay.addWidget(features_box)

        # URL row
        url_row = QHBoxLayout()
        url_row.setSpacing(6)
        lbl_u = QLabel("Indirizzo Web:")
        lbl_u.setStyleSheet("font-size: 11px; font-weight: bold; color: #94a3b8; background: transparent;")
        url_row.addWidget(lbl_u)

        self.lbl_url_op = QLabel("http://127.0.0.1:8080")
        self.lbl_url_op.setStyleSheet("font-size: 12px; font-weight: 800; color: #38bdf8; font-family: monospace; background: transparent;")
        self.lbl_url_op.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        url_row.addWidget(self.lbl_url_op, stretch=1)

        self.btn_copy_op = QPushButton("📋 Copia Link")
        self.btn_copy_op.clicked.connect(self._copy_op_url)
        url_row.addWidget(self.btn_copy_op)

        self.btn_open_op = QPushButton("🌐 Apri nel Browser")
        self.btn_open_op.clicked.connect(self._open_op_browser)
        url_row.addWidget(self.btn_open_op)

        info_lay.addLayout(url_row)
        info_lay.addStretch()
        lay.addLayout(info_lay, stretch=1)

    def _build_director_tab(self) -> None:
        """Build UI for Director / Stage Manager Read-Only Monitor."""
        lay = QHBoxLayout(self.tab_director)
        lay.setSpacing(16)

        # QR Box
        qr_box = QVBoxLayout()
        qr_box.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.qr_frame_dir = QFrame()
        self.qr_frame_dir.setFixedSize(170, 170)
        self.qr_frame_dir.setStyleSheet("background: #ffffff; border-radius: 10px; border: 2px solid #c084fc;")
        qr_inner = QVBoxLayout(self.qr_frame_dir)
        qr_inner.setContentsMargins(4, 4, 4, 4)

        self.lbl_qr_dir = QLabel()
        self.lbl_qr_dir.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_qr_dir.setFixedSize(160, 160)
        self.lbl_qr_dir.setStyleSheet("background: #ffffff;")
        qr_inner.addWidget(self.lbl_qr_dir)
        qr_box.addWidget(self.qr_frame_dir)

        lbl_scan_dir = QLabel("Inquadra con Tablet / iPad\nper aprire il Monitor Regia")
        lbl_scan_dir.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_scan_dir.setStyleSheet("font-size: 10px; color: #c084fc; font-weight: bold; background: transparent;")
        qr_box.addWidget(lbl_scan_dir)

        lay.addLayout(qr_box)

        # Info & Details
        info_lay = QVBoxLayout()
        info_lay.setSpacing(8)

        lbl_dir_title = QLabel("👁️ MONITOR REGISTA && DIRETTORE DI SCENA (SOLA LETTURA)")
        lbl_dir_title.setStyleSheet("font-size: 14px; font-weight: 800; color: #c084fc; background: transparent;")
        info_lay.addWidget(lbl_dir_title)

        lbl_dir_desc = QLabel(
            "Interfaccia di sola visualizzazione passiva per tablet, iPad o computer del regista e del direttore di scena. "
            "Mostra in tempo reale come lavorano i 3 layer e la scaletta, garantendo zero rischi."
        )
        lbl_dir_desc.setWordWrap(True)
        lbl_dir_desc.setStyleSheet("font-size: 11px; color: #cbd5e1; background: transparent;")
        info_lay.addWidget(lbl_dir_desc)

        features_box = QFrame()
        features_box.setObjectName("dir_features_card")
        features_box.setStyleSheet("""
            QFrame#dir_features_card {
                background-color: #0b1120;
                border: 1px solid #233147;
                border-radius: 8px;
                padding: 10px;
            }
            QFrame#dir_features_card QLabel {
                background: transparent;
                border: none;
                font-size: 11px;
                color: #e2e8f0;
                padding: 2px 0px;
            }
        """)
        feat_lay = QVBoxLayout(features_box)
        feat_lay.setSpacing(4)
        feat_lay.addWidget(QLabel("👁️ <b>Panoramica 3 Layer Live:</b> stato simultaneo di Layer 1 (Fondo), Layer 2 (Medio) e Layer 3 (Overlay)"))
        feat_lay.addWidget(QLabel("👁️ <b>Prossimo Lancio in Standby:</b> Q in attesa, destinazione layer, fade e tempi di transizione"))
        feat_lay.addWidget(QLabel("👁️ <b>Scaletta Dinamica Completa:</b> stato live, tipi media, tempi ed avanzamento"))
        feat_lay.addWidget(QLabel("🔒 <b style='color:#f87171;'>Zero comandi e zero click:</b> nessun pulsante interattivo, nessun rischio di errore accidentale"))
        info_lay.addWidget(features_box)

        # URL row
        url_row = QHBoxLayout()
        url_row.setSpacing(6)
        lbl_u = QLabel("Indirizzo Monitor:")
        lbl_u.setStyleSheet("font-size: 11px; font-weight: bold; color: #94a3b8; background: transparent;")
        url_row.addWidget(lbl_u)

        self.lbl_url_dir = QLabel("http://127.0.0.1:8080/monitor")
        self.lbl_url_dir.setStyleSheet("font-size: 12px; font-weight: 800; color: #c084fc; font-family: monospace; background: transparent;")
        self.lbl_url_dir.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        url_row.addWidget(self.lbl_url_dir, stretch=1)

        self.btn_copy_dir = QPushButton("📋 Copia Link Monitor")
        self.btn_copy_dir.clicked.connect(self._copy_dir_url)
        url_row.addWidget(self.btn_copy_dir)

        self.btn_open_dir = QPushButton("🌐 Apri nel Browser")
        self.btn_open_dir.clicked.connect(self._open_dir_browser)
        url_row.addWidget(self.btn_open_dir)

        info_lay.addLayout(url_row)

        # Quick Guide Box for communicating with the director in the auditorium
        guide_box = QFrame()
        guide_box.setObjectName("dir_guide_card")
        guide_box.setStyleSheet("""
            QFrame#dir_guide_card {
                background-color: #0b1120;
                border: 1px dashed #334d6e;
                border-radius: 8px;
                padding: 10px;
            }
            QFrame#dir_guide_card QLabel {
                background: transparent;
                border: none;
                padding: 1px 0px;
            }
        """)
        guide_lay = QVBoxLayout(guide_box)
        guide_lay.setSpacing(4)
        lbl_g_title = QLabel("🗣️ <b>Come collegare il regista che si trova in platea:</b>")
        lbl_g_title.setStyleSheet("font-size: 11px; color: #38bdf8; font-weight: bold; background: transparent;")
        guide_lay.addWidget(lbl_g_title)

        lbl_g1 = QLabel("1. <b>A voce / Intercom (se digita a mano):</b> Digli di collegarsi al Wi-Fi del teatro, aprire il browser (Safari, Chrome o Edge) e digitare l'indirizzo IP con la porta e <code>/monitor</code> (oppure <code>/regia</code>). Inserirà poi il PIN a 6 cifre visualizzato in basso.")
        lbl_g1.setWordWrap(True)
        lbl_g1.setStyleSheet("font-size: 10px; color: #cbd5e1; line-height: 1.3; background: transparent;")
        guide_lay.addWidget(lbl_g1)

        lbl_g2 = QLabel("2. <b>Via Messaggio / WhatsApp / Email:</b> Clicca su <b>[ 📋 Copia Link Monitor ]</b> e incollaglielo in chat. Il link copiato include già il token PIN autorizzato: al regista basterà toccare il link per entrare subito senza digitare nulla!")
        lbl_g2.setWordWrap(True)
        lbl_g2.setStyleSheet("font-size: 10px; color: #cbd5e1; line-height: 1.3; background: transparent;")
        guide_lay.addWidget(lbl_g2)

        info_lay.addWidget(guide_box)
        info_lay.addStretch()
        lay.addLayout(info_lay, stretch=1)

    def _build_osc_tab(self) -> None:
        """Build UI for OSC & Ports Configuration."""
        lay = QVBoxLayout(self.tab_osc)
        lay.setSpacing(10)

        # Configuration Box
        grp_cfg = QGroupBox("⚙ CONFIGURAZIONE PORTE DI RETE && PROTOCOLLI")
        cfg_lay = QGridLayout(grp_cfg)
        cfg_lay.setSpacing(8)

        self.chk_web = QCheckBox("Abilita Servizio Web (Telecomando && Monitor Regia)")
        self.chk_web.setChecked(self._remote_mgr._web_enabled)
        self.chk_web.toggled.connect(self._remote_mgr.set_web_enabled)
        cfg_lay.addWidget(self.chk_web, 0, 0)

        self.spin_web_port = QSpinBox()
        self.spin_web_port.setRange(1024, 65535)
        self.spin_web_port.setValue(self._remote_mgr.get_web_port())
        lbl_pw = QLabel("Porta Web:")
        lbl_pw.setStyleSheet("background: transparent; color: #cbd5e1; font-weight: bold;")
        cfg_lay.addWidget(lbl_pw, 0, 1)
        cfg_lay.addWidget(self.spin_web_port, 0, 2)

        self.chk_osc = QCheckBox("Abilita Server OSC UDP")
        self.chk_osc.setChecked(self._remote_mgr._osc_enabled)
        self.chk_osc.toggled.connect(self._remote_mgr.set_osc_enabled)
        cfg_lay.addWidget(self.chk_osc, 1, 0)

        self.spin_osc_port = QSpinBox()
        self.spin_osc_port.setRange(1024, 65535)
        self.spin_osc_port.setValue(self._remote_mgr.get_osc_port())
        lbl_po = QLabel("Porta OSC UDP:")
        lbl_po.setStyleSheet("background: transparent; color: #cbd5e1; font-weight: bold;")
        cfg_lay.addWidget(lbl_po, 1, 1)
        cfg_lay.addWidget(self.spin_osc_port, 1, 2)

        self.btn_apply_ports = QPushButton("🔄 Applica Nuove Porte")
        self.btn_apply_ports.setStyleSheet("background-color: #0284c7; color: #ffffff; font-weight: bold;")
        self.btn_apply_ports.clicked.connect(self._apply_ports)
        cfg_lay.addWidget(self.btn_apply_ports, 2, 0, 1, 3)

        lay.addWidget(grp_cfg)

        # OSC Commands Cheat Sheet
        grp_osc = QGroupBox("🎛 PRONTUARIO COMANDI OSC (QLab / Mixer Luci / TouchOSC)")
        osc_lay = QVBoxLayout(grp_osc)
        osc_lay.setSpacing(4)

        cheat_text = """
<b>Indirizzo OSC:</b> <span style='color:#38bdf8;'>udp://0.0.0.0:53000</span><br>
• <b style='color:#4ade80;'>/go</b> oppure <b>/cue/go</b> &nbsp;→&nbsp; Esegue GO sulla cue in Standby<br>
• <b style='color:#f87171;'>/panic</b> &nbsp;→&nbsp; Arresto immediato 0ms (Tutti i livelli)<br>
• <b style='color:#f87171;'>/stop</b> oppure <b>/blackout</b> &nbsp;→&nbsp; Blackout live (Ritorno a Layer 0)<br>
• <b style='color:#fbbf24;'>/pause</b> oppure <b>/resume</b> &nbsp;→&nbsp; Mette in pausa o riprende l'emissione<br>
• <b style='color:#38bdf8;'>/next</b> / <b>/prev</b> &nbsp;→&nbsp; Sposta la selezione della scaletta<br>
• <b style='color:#38bdf8;'>/cue/&lt;numero&gt;/go</b> &nbsp;→&nbsp; Esegue subito la cue indicata (es. <i>/cue/3/go</i>)<br>
• <b style='color:#a855f7;'>/auth &lt;pin&gt;</b> &nbsp;→&nbsp; Autentica l'IP per inviare comandi protetti
        """
        lbl_cheat = QLabel(cheat_text)
        lbl_cheat.setTextFormat(Qt.TextFormat.RichText)
        lbl_cheat.setStyleSheet("font-size: 11px; line-height: 1.3; background: transparent;")
        lbl_cheat.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        osc_lay.addWidget(lbl_cheat)

        lay.addWidget(grp_osc)

        self.lbl_last_cmd = QLabel("Ultima attività: Nessun comando ricevuto")
        self.lbl_last_cmd.setStyleSheet("font-size: 11px; color: #94a3b8; font-style: italic; background: transparent;")
        lay.addWidget(self.lbl_last_cmd)

        lay.addStretch()

    def _update_display(self) -> None:
        web_ok = self._remote_mgr.is_web_active()
        osc_ok = self._remote_mgr.is_osc_active()

        if web_ok or osc_ok:
            pin_badge = f" [PIN {self._remote_mgr.get_pin()}]" if self._remote_mgr.is_pin_enabled() else ""
            self.btn_master_toggle.setText(f"🟢 SERVIZI: ATTIVI{pin_badge} (Arresta)")
            self.btn_master_toggle.setStyleSheet("""
                background-color: #064e3b;
                color: #4ade80;
                border: 1.5px solid #059669;
                border-radius: 6px;
                font-size: 11px;
                font-weight: 800;
                padding: 6px 14px;
            """)
        else:
            self.btn_master_toggle.setText("🔴 SERVIZI REMOTI: OFF (Avvia)")
            self.btn_master_toggle.setStyleSheet("""
                background-color: #450a0a;
                color: #f87171;
                border: 1.5px solid #991b1b;
                border-radius: 6px;
                font-size: 11px;
                font-weight: 800;
                padding: 6px 14px;
            """)

        self.chk_web.setChecked(self._remote_mgr._web_enabled)
        self.chk_osc.setChecked(self._remote_mgr._osc_enabled)

        # 1. Update Operator URL & QR
        op_url_disp = self._remote_mgr.get_primary_web_url(include_pin=False)
        self.lbl_url_op.setText(op_url_disp)

        qr_op_url = self._remote_mgr.get_qr_url()
        pix_op = self._remote_mgr.generate_qr_pixmap(qr_op_url, size=160)
        if pix_op:
            self.lbl_qr_op.setPixmap(pix_op)
        else:
            self.lbl_qr_op.setText("QR Code\nNon disponibile")

        # 2. Update Director Monitor URL & QR
        dir_url_disp = self._remote_mgr.get_monitor_url(include_pin=False)
        self.lbl_url_dir.setText(dir_url_disp)

        qr_dir_url = self._remote_mgr.get_monitor_qr_url()
        pix_dir = self._remote_mgr.generate_qr_pixmap(qr_dir_url, size=160)
        if pix_dir:
            self.lbl_qr_dir.setPixmap(pix_dir)
        else:
            self.lbl_qr_dir.setText("QR Code\nNon disponibile")

        # Update stats
        c_count = self._remote_mgr.web_server.get_connected_clients_count()
        self.lbl_clients_count.setText(f"📱 Client Web connessi: {c_count}")

        last_web = self._remote_mgr.web_server.get_last_action_info()
        last_osc = self._remote_mgr.osc_server.get_last_command_info()
        self.lbl_last_cmd.setText(f"Web: {last_web} | OSC: {last_osc}")

    def _toggle_master_services(self) -> None:
        """Toggle all remote services ON or OFF."""
        is_active = self._remote_mgr.is_web_active() or self._remote_mgr.is_osc_active()
        if is_active:
            self._remote_mgr.stop_all()
        else:
            w_port = self.spin_web_port.value()
            o_port = self.spin_osc_port.value()
            self._remote_mgr.start_all(web_port=w_port, osc_port=o_port)
        self._update_display()

    def _on_pin_settings_changed(self) -> None:
        p_en = self.chk_pin.isChecked()
        pin = self.txt_pin.text().strip() or "123456"
        qr_pin = self.chk_qr_pin.isChecked()
        self._remote_mgr.set_pin_security(p_en, pin, qr_pin)
        self._update_display()

    def _generate_new_pin(self) -> None:
        new_pin = self._remote_mgr.generate_new_pin()
        self.txt_pin.setText(new_pin)
        self._update_display()

    def _kick_all_clients(self) -> None:
        self._remote_mgr.revoke_all_sessions()
        self.btn_kick_all.setText("✓ Disconnessi!")
        from PySide6.QtCore import QTimer
        QTimer.singleShot(1500, lambda: self.btn_kick_all.setText("⛔ Disconnetti Tutti"))

    def _apply_ports(self) -> None:
        w_port = self.spin_web_port.value()
        o_port = self.spin_osc_port.value()
        self._remote_mgr.start_all(web_port=w_port, osc_port=o_port)
        self._update_display()

    def _copy_op_url(self) -> None:
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(self._remote_mgr.get_qr_url())
            self.btn_copy_op.setText("✓ Copiato!")
            from PySide6.QtCore import QTimer
            QTimer.singleShot(1500, lambda: self.btn_copy_op.setText("📋 Copia Link"))

    def _open_op_browser(self) -> None:
        QDesktopServices.openUrl(QUrl(self._remote_mgr.get_qr_url()))

    def _copy_dir_url(self) -> None:
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(self._remote_mgr.get_monitor_qr_url())
            self.btn_copy_dir.setText("✓ Copiato!")
            from PySide6.QtCore import QTimer
            QTimer.singleShot(1500, lambda: self.btn_copy_dir.setText("📋 Copia Link Monitor"))

    def _open_dir_browser(self) -> None:
        QDesktopServices.openUrl(QUrl(self._remote_mgr.get_monitor_qr_url()))
