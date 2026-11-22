"""Dialog for creating / editing a text cue (on-screen caption) with live preview."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from engine.text_render import normalize_spec, render_text_image

_POSITIONS = (("bottom", "In basso"), ("center", "Al centro"), ("top", "In alto"))


class TextCueDialog(QDialog):
    """Edit the text, size, colour, position and background of a caption."""

    def __init__(self, spec: dict[str, Any] | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Cue di testo (didascalia)")
        self.resize(640, 640)
        s = normalize_spec(spec)
        self._color = s["color"]

        self.edit_text = QPlainTextEdit(s["text"])
        self.edit_text.setPlaceholderText("Scrivi il testo da mostrare sul proiettore…")
        self.edit_text.setMinimumHeight(110)

        self.spin_size = QSpinBox()
        self.spin_size.setRange(12, 400)
        self.spin_size.setValue(s["size"])
        self.spin_size.setSuffix(" px")

        self.btn_color = QPushButton()
        self.btn_color.clicked.connect(self._pick_color)
        self._update_color_button()

        self.combo_pos = QComboBox()
        for key, label in _POSITIONS:
            self.combo_pos.addItem(label, key)
        self.combo_pos.setCurrentIndex(max(0, [k for k, _ in _POSITIONS].index(s["position"])))

        self.chk_bold = QCheckBox("Grassetto")
        self.chk_bold.setChecked(s["bold"])
        self.chk_box = QCheckBox("Fascia scura dietro il testo")
        self.chk_box.setChecked(s["box"])
        self.chk_shadow = QCheckBox("Ombra")
        self.chk_shadow.setChecked(s["shadow"])

        form = QFormLayout()
        # Explicit QLabel objects so the UI translation layer sees the text.
        form.addRow(QLabel("Testo:"), self.edit_text)
        form.addRow(QLabel("Dimensione carattere:"), self.spin_size)
        form.addRow(QLabel("Colore del testo:"), self.btn_color)
        form.addRow(QLabel("Posizione sullo schermo:"), self.combo_pos)
        opts = QHBoxLayout()
        for w in (self.chk_bold, self.chk_box, self.chk_shadow):
            opts.addWidget(w)
        opts.addStretch(1)
        form.addRow(QLabel(""), opts)

        self.preview = QLabel()
        self.preview.setFixedSize(576, 324)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setStyleSheet("border: 1px solid #334155;")

        hint = QLabel(
            "Suggerimento: la didascalia va sul Layer 3 (sopra video e foto). "
            "Fade In/Out, posizione e crossfade si impostano nell'Inspector come per una foto."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #94a3b8;")

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("OK")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Annulla")
        buttons.accepted.connect(self._accept_if_text)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(QLabel("Anteprima (proiettore):"))
        layout.addWidget(self.preview, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(hint)
        layout.addWidget(buttons)

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(120)
        self._debounce.timeout.connect(self._update_preview)
        for sig in (self.edit_text.textChanged, self.spin_size.valueChanged,
                    self.combo_pos.currentIndexChanged, self.chk_bold.toggled,
                    self.chk_box.toggled, self.chk_shadow.toggled):
            sig.connect(lambda *_: self._debounce.start())
        self._update_preview()

    # ── Helpers ────────────────────────────────────────────────────────
    def spec(self) -> dict[str, Any]:
        """Current settings as a normalised text spec."""
        return normalize_spec({
            "text": self.edit_text.toPlainText().strip("\n"),
            "size": self.spin_size.value(),
            "color": self._color,
            "bold": self.chk_bold.isChecked(),
            "position": self.combo_pos.currentData(),
            "box": self.chk_box.isChecked(),
            "shadow": self.chk_shadow.isChecked(),
        })

    def _pick_color(self) -> None:
        col = QColorDialog.getColor(QColor(self._color), self, "Colore del testo")
        if col.isValid():
            self._color = col.name()
            self._update_color_button()
            self._update_preview()

    def _update_color_button(self) -> None:
        fg = "#000000" if QColor(self._color).lightness() > 128 else "#ffffff"
        self.btn_color.setText(self._color)
        self.btn_color.setStyleSheet(f"background-color: {self._color}; color: {fg};")

    def _update_preview(self) -> None:
        img = render_text_image(self.spec())
        canvas = QPixmap(576, 324)
        canvas.fill(QColor("#1f2937"))
        p = QPainter(canvas)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        p.drawImage(canvas.rect(), img)
        p.end()
        self.preview.setPixmap(canvas)

    def _accept_if_text(self) -> None:
        if self.edit_text.toPlainText().strip():
            self.accept()
        else:
            self.edit_text.setFocus()
