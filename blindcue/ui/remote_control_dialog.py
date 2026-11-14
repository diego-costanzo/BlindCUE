"""Dialog displaying Web Remote pairing (QR code, LAN IPs, ports), OSC status, and PIN security controls."""

from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QFont, QPainter, QPixmap
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
    QVBoxLayout,
    QWidget,
)

from services.remote_manager import RemoteManager

logger = logging.getLogger("blindcue.remote_ui")


class RemoteControlDialog(QDialog):
    """Setup, PIN Security, and Live Monitor dialog for LAN Web Remote and OSC automation."""

    def __init__(self, remote_mgr: RemoteManager, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._remote_mgr = remote_mgr
        self.setWindowTitle("📡 Controllo Remoto LAN (Web & OSC) — BlindCUE")
        self.resize(800, 640)
        self.setMinimumSize(720, 560)

        self._build_ui()
        self._update_display()

        # Connect live updates
        self._remote_mgr.activity_updated.connect(self._update_display)

    def _build_ui(self) -> None:
        self.setStyleSheet("""
            QDialog {
                background-color: #0f172a;
                color: #f8fafc;
            }
            QGroupBox {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 8px;
                margin-top: 10px;
                padding: 10px;
                font-weight: bold;
                font-size: 11px;
                color: #38bdf8;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
            QLabel {
                color: #cbd5e1;
            }
            QPushButton {
                background-color: #334155;
                color: #ffffff;
                border: 1px solid #475569;
                border-radius: 5px;
                padding: 6px 12px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #475569;
                border-color: #64748b;
            }
            QPushButton:pressed {
                background-color: #0284c7;
            }
            QLineEdit, QSpinBox {
                background-color: #0f172a;
                color: #ffffff;
                border: 1px solid #475569;
                border-radius: 4px;
                padding: 4px 6px;
                font-size: 12px;
            }
            QCheckBox {
                color: #f1f5f9;
                font-size: 12px;
                font-weight: bold;
                spacing: 8px;
            }
        """)

        main_lay = QVBoxLayout(self)
        main_lay.setContentsMargins(16, 16, 16, 16)
        main_lay.setSpacing(12)

        # Header Banner
        header = QHBoxLayout()
        header_v = QVBoxLayout()
        lbl_title = QLabel("📡 CONTROLLO REMOTO IN RETE LOCALE (LAN REGIA)")
        lbl_title.setStyleSheet("font-size: 15px; font-weight: 900; color: #38bdf8; letter-spacing: 0.5px;")
        lbl_desc = QLabel("Controlla BlindCUE dal palco o dalla platea tramite Smartphone, Tablet, TouchOSC o mixer luci.")
        lbl_desc.setStyleSheet("font-size: 11px; color: #94a3b8;")
        header_v.addWidget(lbl_title)
        header_v.addWidget(lbl_desc)
        header.addLayout(header_v)
        header.addStretch()

        self.lbl_global_status = QLabel("● SERVER ATTIVO")
        self.lbl_global_status.setStyleSheet("font-size: 11px; font-weight: 800; color: #22c55e; background: #064e3b; border: 1px solid #059669; border-radius: 999px; padding: 4px 12px;")
        header.addWidget(self.lbl_global_status)
        main_lay.addLayout(header)

        # Columns
        body_lay = QHBoxLayout()
        body_lay.setSpacing(14)

        # ── LEFT: Smartphone QR Code & Security ──
        left_vlay = QVBoxLayout()
        left_vlay.setSpacing(10)

        grp_qr = QGroupBox("📱 ACCESSO SMARTPHONE & TABLET (WEB REMOTE)")
        qr_vlay = QVBoxLayout(grp_qr)
        qr_vlay.setSpacing(8)
        qr_vlay.setAlignment(Qt.AlignmentFlag.AlignTop)

        # QR Code Display
        self.qr_frame = QFrame()
        self.qr_frame.setFixedSize(180, 180)
        self.qr_frame.setStyleSheet("background: #ffffff; border-radius: 10px; border: 2px solid #38bdf8;")
        qr_box_lay = QVBoxLayout(self.qr_frame)
        qr_box_lay.setContentsMargins(4, 4, 4, 4)

        self.lbl_qr_img = QLabel()
        self.lbl_qr_img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_qr_img.setFixedSize(170, 170)
        qr_box_lay.addWidget(self.lbl_qr_img)

        qr_center_row = QHBoxLayout()
        qr_center_row.addStretch()
        qr_center_row.addWidget(self.qr_frame)
        qr_center_row.addStretch()
        qr_vlay.addLayout(qr_center_row)

        self.lbl_scan_info = QLabel("Inquadra il codice QR con lo smartphone\nper aprire istantaneamente il pannello LIVE.")
        self.lbl_scan_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_scan_info.setStyleSheet("font-size: 11px; color: #cbd5e1; font-weight: bold;")
        qr_vlay.addWidget(self.lbl_scan_info)

        # URL Box
        url_box = QFrame()
        url_box.setStyleSheet("background: #0f172a; border: 1px solid #334155; border-radius: 6px; padding: 6px;")
        url_lay = QVBoxLayout(url_box)
        url_lay.setContentsMargins(6, 6, 6, 6)
        url_lay.setSpacing(4)

        lbl_url_hdr = QLabel("Indirizzo Web Diretto:")
        lbl_url_hdr.setStyleSheet("font-size: 10px; color: #94a3b8; font-weight: bold;")
        url_lay.addWidget(lbl_url_hdr)

        self.lbl_url_val = QLabel("http://192.168.1.x:8080")
        self.lbl_url_val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.lbl_url_val.setStyleSheet("font-size: 12px; font-weight: 800; color: #38bdf8; font-family: monospace;")
        url_lay.addWidget(self.lbl_url_val)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        self.btn_copy_url = QPushButton("📋 Copia Link")
        self.btn_copy_url.clicked.connect(self._copy_url)
        self.btn_open_browser = QPushButton("🌐 Apri nel Browser")
        self.btn_open_browser.clicked.connect(self._open_in_browser)
        btn_row.addWidget(self.btn_copy_url)
        btn_row.addWidget(self.btn_open_browser)
        url_lay.addLayout(btn_row)

        qr_vlay.addWidget(url_box)
        left_vlay.addWidget(grp_qr)

        # ── Group: Sicurezza & Protezione Accessi (Anti-Burlone) ──
        grp_sec = QGroupBox("🛡️ SICUREZZA REGIA & PROTEZIONE ACCESSI (ANTI-BURLONE)")
        sec_lay = QVBoxLayout(grp_sec)
        sec_lay.setSpacing(8)

        self.chk_pin = QCheckBox("Proteggi Web Remote con Codice PIN di Regia")
        self.chk_pin.setChecked(self._remote_mgr.is_pin_enabled())
        self.chk_pin.toggled.connect(self._on_pin_settings_changed)
        sec_lay.addWidget(self.chk_pin)

        pin_row = QHBoxLayout()
        pin_row.setSpacing(6)
        pin_row.addWidget(QLabel("PIN Attuale:"))
        self.txt_pin = QLineEdit(self._remote_mgr.get_pin())
        self.txt_pin.setMaxLength(6)
        self.txt_pin.setFixedWidth(70)
        self.txt_pin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.txt_pin.setStyleSheet("font-weight: 900; font-size: 14px; letter-spacing: 2px; color: #38bdf8;")
        self.txt_pin.textChanged.connect(self._on_pin_settings_changed)
        pin_row.addWidget(self.txt_pin)

        self.btn_new_pin = QPushButton("🎲 Nuovo PIN")
        self.btn_new_pin.setToolTip("Genera un nuovo codice PIN casuale a 4 cifre")
        self.btn_new_pin.clicked.connect(self._generate_new_pin)
        pin_row.addWidget(self.btn_new_pin)

        self.btn_kick_all = QPushButton("⛔ Disconnetti Tutti")
        self.btn_kick_all.setStyleSheet("background-color: #450a0a; color: #f87171; border-color: #991b1b;")
        self.btn_kick_all.setToolTip("Sbatte fuori all'istante tutti i telefoni e client remoti connessi")
        self.btn_kick_all.clicked.connect(self._kick_all_clients)
        pin_row.addWidget(self.btn_kick_all)
        sec_lay.addLayout(pin_row)

        self.chk_qr_pin = QCheckBox("Includi PIN nel codice QR (Accesso immediato con fotocamera)")
        self.chk_qr_pin.setChecked(self._remote_mgr.is_qr_pin_included())
        self.chk_qr_pin.toggled.connect(self._on_pin_settings_changed)
        sec_lay.addWidget(self.chk_qr_pin)

        lbl_sec_tip = QLabel(
            "💡 <b>Protezione Wi-Fi Teatro:</b> Chi inquadra il monitor fisico della regia con lo smartphone "
            "entra all'istante senza digitare nulla. Chi invece è connesso al Wi-Fi e prova ad aprire l'indirizzo "
            "viene bloccato dal tastierino numerico PIN con blocco anti-forzatura."
        )
        lbl_sec_tip.setWordWrap(True)
        lbl_sec_tip.setStyleSheet("font-size: 10px; color: #94a3b8; line-height: 1.3;")
        sec_lay.addWidget(lbl_sec_tip)

        left_vlay.addWidget(grp_sec)
        body_lay.addLayout(left_vlay, 1)

        # ── RIGHT: Config & OSC Automation ──
        right_vlay = QVBoxLayout()
        right_vlay.setSpacing(10)

        # Configuration Box
        grp_cfg = QGroupBox("⚙ CONFIGURAZIONE PORTE & SERVIZI")
        cfg_lay = QGridLayout(grp_cfg)
        cfg_lay.setSpacing(8)

        self.chk_web = QCheckBox("Abilita Web Remote (Pagina Web)")
        self.chk_web.setChecked(self._remote_mgr._web_enabled)
        self.chk_web.toggled.connect(self._remote_mgr.set_web_enabled)
        cfg_lay.addWidget(self.chk_web, 0, 0)

        self.spin_web_port = QSpinBox()
        self.spin_web_port.setRange(1024, 65535)
        self.spin_web_port.setValue(self._remote_mgr.get_web_port())
        cfg_lay.addWidget(QLabel("Porta Web:"), 0, 1)
        cfg_lay.addWidget(self.spin_web_port, 0, 2)

        self.chk_osc = QCheckBox("Abilita Server OSC UDP")
        self.chk_osc.setChecked(self._remote_mgr._osc_enabled)
        self.chk_osc.toggled.connect(self._remote_mgr.set_osc_enabled)
        cfg_lay.addWidget(self.chk_osc, 1, 0)

        self.spin_osc_port = QSpinBox()
        self.spin_osc_port.setRange(1024, 65535)
        self.spin_osc_port.setValue(self._remote_mgr.get_osc_port())
        cfg_lay.addWidget(QLabel("Porta OSC:"), 1, 1)
        cfg_lay.addWidget(self.spin_osc_port, 1, 2)

        self.btn_apply_ports = QPushButton("🔄 Applica Nuove Porte")
        self.btn_apply_ports.setStyleSheet("background-color: #0284c7; color: #ffffff;")
        self.btn_apply_ports.clicked.connect(self._apply_ports)
        cfg_lay.addWidget(self.btn_apply_ports, 2, 0, 1, 3)

        right_vlay.addWidget(grp_cfg)

        # OSC Commands Cheat Sheet
        grp_osc = QGroupBox("🎛 PRONTUARIO COMANDI OSC (QLab / Mixer / TouchOSC)")
        osc_lay = QVBoxLayout(grp_osc)
        osc_lay.setSpacing(6)

        cheat_text = """
<b>Indirizzo OSC:</b> <span style='color:#38bdf8;'>udp://0.0.0.0:53000</span><br><br>
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
        lbl_cheat.setStyleSheet("font-size: 11px; line-height: 1.4;")
        lbl_cheat.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        osc_lay.addWidget(lbl_cheat)

        right_vlay.addWidget(grp_osc)

        # Real-time Activity Card
        grp_act = QGroupBox("📊 STATO CONNETTI & ATTIVITÀ")
        act_lay = QVBoxLayout(grp_act)
        act_lay.setSpacing(4)

        self.lbl_clients_count = QLabel("📱 Client Web connessi: 0")
        self.lbl_clients_count.setStyleSheet("font-weight: bold; color: #f8fafc;")
        act_lay.addWidget(self.lbl_clients_count)

        self.lbl_last_cmd = QLabel("Ultima attività: Nessun comando ricevuto")
        self.lbl_last_cmd.setStyleSheet("font-size: 11px; color: #94a3b8; font-style: italic;")
        act_lay.addWidget(self.lbl_last_cmd)

        right_vlay.addWidget(grp_act)

        body_lay.addLayout(right_vlay, 1)
        main_lay.addLayout(body_lay)

        # Bottom Bar
        bottom_row = QHBoxLayout()
        bottom_row.addStretch()

        btn_close = QPushButton("Chiudi")
        btn_close.setMinimumWidth(100)
        btn_close.clicked.connect(self.accept)
        bottom_row.addWidget(btn_close)

        main_lay.addLayout(bottom_row)

    def _update_display(self) -> None:
        web_ok = self._remote_mgr.is_web_active()
        osc_ok = self._remote_mgr.is_osc_active()

        if web_ok or osc_ok:
            pin_badge = f" [🔒 PIN {self._remote_mgr.get_pin()}]" if self._remote_mgr.is_pin_enabled() else ""
            self.lbl_global_status.setText(f"● SERVER ATTIVO{pin_badge}")
            self.lbl_global_status.setStyleSheet("font-size: 11px; font-weight: 800; color: #22c55e; background: #064e3b; border: 1px solid #059669; border-radius: 999px; padding: 4px 12px;")
        else:
            self.lbl_global_status.setText("○ SERVER DISATTIVATO")
            self.lbl_global_status.setStyleSheet("font-size: 11px; font-weight: 800; color: #ef4444; background: #450a0a; border: 1px solid #991b1b; border-radius: 999px; padding: 4px 12px;")

        # Base URL for human display
        url = self._remote_mgr.get_primary_web_url(include_pin=False)
        self.lbl_url_val.setText(url)

        # QR URL (includes PIN if enabled for 1-tap scan)
        qr_url = self._remote_mgr.get_qr_url()
        pix = self._remote_mgr.generate_qr_pixmap(qr_url, size=170)
        if pix:
            self.lbl_qr_img.setPixmap(pix)
        else:
            self.lbl_qr_img.setText("QR Code\nNon disponibile")

        if self._remote_mgr.is_pin_enabled() and self._remote_mgr.is_qr_pin_included():
            self.lbl_scan_info.setText("Inquadra con la fotocamera per aprire e sbloccare\nautomaticamente la regia con PIN protetto.")
        else:
            self.lbl_scan_info.setText("Inquadra il codice QR con lo smartphone\nper aprire il pannello di controllo LIVE.")

        # Update activity readouts
        c_count = self._remote_mgr.web_server.get_connected_clients_count()
        self.lbl_clients_count.setText(f"📱 Client Web connessi: {c_count}")

        last_web = self._remote_mgr.web_server.get_last_action_info()
        last_osc = self._remote_mgr.osc_server.get_last_command_info()
        self.lbl_last_cmd.setText(f"Web: {last_web} | OSC: {last_osc}")

    def _on_pin_settings_changed(self) -> None:
        p_en = self.chk_pin.isChecked()
        pin = self.txt_pin.text().strip() or "0000"
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

    def _copy_url(self) -> None:
        clipboard = QApplication.clipboard()
        if clipboard:
            # Copy QR URL with PIN if checked
            url_to_copy = self._remote_mgr.get_qr_url()
            clipboard.setText(url_to_copy)
            self.btn_copy_url.setText("✓ Copiato!")
            from PySide6.QtCore import QTimer
            QTimer.singleShot(1500, lambda: self.btn_copy_url.setText("📋 Copia Link"))

    def _open_in_browser(self) -> None:
        QDesktopServices.openUrl(QUrl(self._remote_mgr.get_qr_url()))
