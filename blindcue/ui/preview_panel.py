"""Center Pre-Viz sandbox panel (header toolbar, 16:9 monitor, and transport bar)."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui.preview_monitor import StudioPreviewMonitor
from ui.theme import CLR_LIVE, CLR_PREVIZ


class PreviewControlPanel(QGroupBox):
    """Pre-Viz monitor panel containing toolbar, 16:9 StudioPreviewMonitor, and transport controls."""

    live_mirror_toggled = Signal(bool)
    preview_mute_toggled = Signal(bool)

    def __init__(self, layer0_path: Optional[str] = None, parent: Optional[QWidget] = None) -> None:
        super().__init__("ANTEPRIMA PRE-VIZ (Sandbox)", parent)
        self.setMinimumWidth(380)
        self._build_ui(layer0_path)

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        """Lock minimum width so long cue names never stretch the Pre-Viz sector."""
        return QSize(380, 240)

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(680, 560)

    def _build_ui(self, layer0_path: Optional[str]) -> None:
        preview_layout = QVBoxLayout(self)
        preview_layout.setContentsMargins(6, 4, 6, 6)
        preview_layout.setSpacing(4)

        preview_header_frame = QFrame()
        preview_header_frame.setFixedHeight(28)
        preview_header_frame.setStyleSheet("background: transparent; border: none;")
        preview_header = QHBoxLayout(preview_header_frame)
        preview_header.setContentsMargins(2, 0, 2, 0)
        preview_header.setSpacing(8)

        lbl_test = QLabel("PRE-VIZ")
        lbl_test.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_test.setStyleSheet(f"""
            QLabel {{
                background-color: {CLR_PREVIZ};
                color: #000;
                font-weight: bold;
                padding: 1px 7px;
                border-radius: 3px;
                font-size: 10px;
                max-height: 22px;
            }}
        """)
        lbl_test.setFixedHeight(22)
        preview_header.addWidget(lbl_test)

        self.lbl_info = QLabel("— Nessun file selezionato —")
        self.lbl_info.setFixedHeight(22)
        self.lbl_info.setMinimumWidth(0)
        self.lbl_info.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.lbl_info.setStyleSheet(
            "color: #00bcd4; font-size: 11px; font-weight: bold; background: transparent; padding-left: 4px;"
        )
        preview_header.addWidget(self.lbl_info, stretch=1)

        self.lbl_time = QLabel("⏱ 00:00.00 / 00:00.00")
        self.lbl_time.setFixedHeight(22)
        self.lbl_time.setStyleSheet(
            "color: #00e5ff; font-family: monospace; font-size: 11px; font-weight: bold; "
            "padding: 1px 6px; background: #1a1a1a; border: 1px solid #333; border-radius: 3px;"
        )
        preview_header.addWidget(self.lbl_time)

        lbl_sim = QLabel("16:9 Live")
        lbl_sim.setFixedHeight(22)
        lbl_sim.setStyleSheet("color: #666; font-size: 10px; font-weight: bold; background: transparent;")
        preview_header.addWidget(lbl_sim)

        preview_layout.addWidget(preview_header_frame, stretch=0)

        self.monitor = StudioPreviewMonitor()
        self.monitor.set_layer0_image(layer0_path)
        preview_layout.addWidget(self.monitor, stretch=1)

        transport_frame = QFrame()
        transport_frame.setFixedHeight(34)
        transport_frame.setStyleSheet("background: transparent; border: none;")
        transport = QHBoxLayout(transport_frame)
        transport.setContentsMargins(0, 2, 0, 0)
        transport.setSpacing(6)

        btn_style_base = """
            QPushButton {
                background-color: #383838;
                color: #e0e0e0;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 2px 12px;
                font-size: 11px;
                font-weight: bold;
                height: 24px;
                min-width: 65px;
            }
        """

        self.btn_play = QPushButton("▶  Play")
        self.btn_play.setToolTip("Riproduci anteprima / Pre-viz")
        self.btn_play.setStyleSheet(btn_style_base + """
            QPushButton:hover {
                background-color: #1e3d24;
                border-color: #00e676;
                color: #00e676;
            }
            QPushButton:pressed { background-color: #142918; }
        """)

        self.btn_pause = QPushButton("⏸  Pausa")
        self.btn_pause.setToolTip("Metti in pausa l'anteprima")
        self.btn_pause.setStyleSheet(btn_style_base + """
            QPushButton:hover {
                background-color: #2b3345;
                border-color: #64b5f6;
                color: #64b5f6;
            }
            QPushButton:pressed { background-color: #1c222e; }
        """)

        self.btn_stop = QPushButton("⏹  Stop")
        self.btn_stop.setToolTip("Arresta anteprima e riavvolgi")
        self.btn_stop.setStyleSheet(btn_style_base + """
            QPushButton:hover {
                background-color: #3d1e1e;
                border-color: #ff5252;
                color: #ff5252;
            }
            QPushButton:pressed { background-color: #291414; }
        """)

        for btn in (self.btn_play, self.btn_pause, self.btn_stop):
            btn.setFixedHeight(26)
            transport.addWidget(btn)

        transport.addStretch(1)

        self.btn_mute = QPushButton()
        self.btn_mute.setFixedHeight(26)
        self.btn_mute.setCheckable(True)
        self.btn_mute.setChecked(True)
        self.btn_mute.setToolTip(
            "Se attivo (default), l'anteprima è muta. Clicca per ascoltare l'audio su richiesta."
        )
        self.update_mute_style()
        self.btn_mute.toggled.connect(self.preview_mute_toggled)
        transport.addWidget(self.btn_mute)

        self.btn_live_mirror = QPushButton("🔗 MIRROR LIVE: OFF")
        self.btn_live_mirror.setCheckable(True)
        self.btn_live_mirror.setChecked(False)
        self.btn_live_mirror.setFixedHeight(26)
        self.btn_live_mirror.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_live_mirror.setToolTip(
            "Modalità Progettazione: se ATTIVO, le modifiche a Crop, Scala e Posizione vengono "
            "proiettate in tempo reale sullo schermo LIVE per calibrare il videoproiettore/schermo.\n"
            "In Spettacolo dal vivo: lasciare DISATTIVATO per isolare completamente l'anteprima."
        )
        self.set_live_mirror_style(False)
        self.btn_live_mirror.toggled.connect(self.live_mirror_toggled)
        transport.addWidget(self.btn_live_mirror)

        preview_layout.addWidget(transport_frame, stretch=0)

    def set_live_mirror_style(self, active: bool) -> None:
        if active:
            self.btn_live_mirror.setText("🔴 MIRROR: ON")
            self.btn_live_mirror.setStyleSheet("""
                QPushButton {
                    background-color: #5c1818;
                    color: #ff5252;
                    border: 1px solid #ff5252;
                    border-radius: 3px;
                    font-weight: bold;
                    font-size: 10px;
                    padding: 2px 10px;
                    height: 24px;
                }
                QPushButton:hover { background-color: #7a2020; color: #ffffff; }
            """)
        else:
            self.btn_live_mirror.setText("🔗 MIRROR LIVE: OFF")
            self.btn_live_mirror.setStyleSheet("""
                QPushButton {
                    background-color: #242b38;
                    color: #94a3b8;
                    border: 1px solid #3c4d66;
                    border-radius: 3px;
                    font-weight: bold;
                    font-size: 10px;
                    padding: 2px 10px;
                    height: 24px;
                }
                QPushButton:hover { background-color: #313b4d; color: #ffffff; border-color: #38bdf8; }
            """)

    def update_mute_style(self) -> None:
        if self.btn_mute.isChecked():
            self.btn_mute.setText("🔒 MUTE: ON")
            self.btn_mute.setStyleSheet(f"""
                QPushButton {{
                    background-color: #4d3800;
                    color: {CLR_PREVIZ};
                    border: 1px solid {CLR_PREVIZ};
                    border-radius: 3px;
                    padding: 2px 10px;
                    font-weight: bold;
                    font-size: 10px;
                    height: 22px;
                }}
                QPushButton:hover {{ background-color: #664d00; }}
            """)
        else:
            self.btn_mute.setText("🔊 CUFFIA: ON")
            self.btn_mute.setStyleSheet(f"""
                QPushButton {{
                    background-color: #004d20;
                    color: {CLR_LIVE};
                    border: 1px solid {CLR_LIVE};
                    border-radius: 3px;
                    padding: 2px 10px;
                    font-weight: bold;
                    font-size: 10px;
                    height: 22px;
                }}
                QPushButton:hover {{ background-color: #00662a; }}
            """)

    def set_time(self, current_sec: float, total_sec: float) -> None:
        """Update preview digital time counter in centesimi format ⏱ MM:SS.ss / MM:SS.ss."""
        def _fmt(sec: float) -> str:
            sec = max(0.0, sec)
            m = int(sec // 60)
            s = sec % 60
            return f"{m:02d}:{s:05.2f}"

        cur_str = _fmt(current_sec)
        tot_str = _fmt(total_sec) if total_sec > 0 else "--:--.--"
        self.lbl_time.setText(f"⏱ {cur_str} / {tot_str}")

