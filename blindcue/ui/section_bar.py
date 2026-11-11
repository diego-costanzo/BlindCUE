"""Interactive virtual sections bar (A, B, C...) aligned below the Waveform canvas."""

from __future__ import annotations

from typing import Optional, Sequence

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QPushButton, QWidget

from models.cue import CueSection

# Shared palette used by both WaveformWidget bands and SectionControlBar cells
SECTION_PALETTE: tuple[tuple[str, str, str], ...] = (
    # (accent_hex, band_bg_hex, active_pill_bg)
    ("#38bdf8", "#0c2233", "#075985"),  # A - Cyan / Sky
    ("#a78bfa", "#1d1433", "#5b21b6"),  # B - Violet
    ("#2dd4bf", "#0a2926", "#115e59"),  # C - Teal
    ("#fbbf24", "#2e1f07", "#92400e"),  # D - Amber
    ("#fb7185", "#33101a", "#9f1239"),  # E - Rose
    ("#a3e635", "#1b2909", "#3f6212"),  # F - Lime
)

_LOOP_OPTIONS: tuple[tuple[str, int, bool], ...] = (
    ("x1", 1, False),
    ("x2", 2, False),
    ("x3", 3, False),
    ("x4", 4, False),
    ("x5", 5, False),
    ("x8", 8, False),
    ("∞", 0, False),
    ("Salta", 1, True),
)


class _SectionCell(QWidget):
    """Single proportional cell representing one virtual CueSection (badge + loop combo)."""

    jump_clicked = Signal(int)
    mode_changed = Signal(int, int, bool)  # index, loops, skip
    remove_clicked = Signal(int)

    def __init__(self, index: int, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.index = index

        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 1, 2, 1)
        layout.setSpacing(2)

        self.btn_label = QPushButton("A")
        self.btn_label.setFixedHeight(22)
        self.btn_label.setMinimumWidth(20)
        self.btn_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_label.clicked.connect(lambda: self.jump_clicked.emit(self.index))

        self.combo_mode = QComboBox()
        self.combo_mode.setFixedHeight(22)
        self.combo_mode.setMinimumWidth(46)
        self.combo_mode.setCursor(Qt.CursorShape.PointingHandCursor)
        for text, loops, skip in _LOOP_OPTIONS:
            self.combo_mode.addItem(text, (loops, skip))
        self.combo_mode.currentIndexChanged.connect(self._on_combo_changed)

        self.btn_merge = QPushButton("×")
        self.btn_merge.setFixedSize(16, 22)
        self.btn_merge.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_merge.setToolTip("Rimuovi questa sezione e uniscila alla adiacente")
        self.btn_merge.setStyleSheet(
            "QPushButton { background: transparent; color: #94a3b8; border: none; font-size: 11px; font-weight: bold; } "
            "QPushButton:hover { color: #ff6b6b; }"
        )
        self.btn_merge.clicked.connect(lambda: self.remove_clicked.emit(self.index))

        layout.addWidget(self.btn_label, stretch=1)
        layout.addWidget(self.combo_mode, stretch=2)
        layout.addWidget(self.btn_merge, stretch=0)

    def _on_combo_changed(self, idx: int) -> None:
        data = self.combo_mode.itemData(idx)
        if isinstance(data, tuple) and len(data) == 2:
            self.mode_changed.emit(self.index, int(data[0]), bool(data[1]))

    def sync(self, sec: CueSection, is_active: bool) -> None:
        accent, bg, active_bg = SECTION_PALETTE[self.index % len(SECTION_PALETTE)]
        self.btn_label.setText(sec.label)
        end_lbl = f"{sec.end:.2f}s" if sec.end is not None else "OUT/Fine"
        self.btn_label.setToolTip(
            f"Sezione {sec.label} ({sec.start:.2f}s – {end_lbl})\nClicca per saltare subito qui"
        )
        if sec.skip:
            badge_style = (
                f"QPushButton {{ background-color: #24191c; color: #94a3b8; border: 1px dashed #64748b; "
                "border-radius: 3px; font-size: 10px; font-weight: bold; padding: 0 4px; }"
                f"QPushButton:hover {{ border-color: {accent}; color: #ffffff; }}"
            )
        elif is_active:
            badge_style = (
                f"QPushButton {{ background-color: {active_bg}; color: #ffffff; border: 2px solid {accent}; "
                "border-radius: 3px; font-size: 10px; font-weight: bold; padding: 0 4px; }"
            )
        else:
            badge_style = (
                f"QPushButton {{ background-color: {bg}; color: {accent}; border: 1px solid {accent}; "
                "border-radius: 3px; font-size: 10px; font-weight: bold; padding: 0 4px; }"
                f"QPushButton:hover {{ background-color: {active_bg}; color: #ffffff; }}"
            )
        self.btn_label.setStyleSheet(badge_style)

        self.combo_mode.setToolTip(
            f"Ripetizioni o salto automatico per la Sezione {sec.label} (default: x1)"
        )
        self.combo_mode.setStyleSheet(
            f"QComboBox {{ background-color: #111824; color: {'#64748b' if sec.skip else '#e2e8f0'}; "
            f"border: 1px solid {accent if not sec.skip else '#334155'}; border-radius: 3px; "
            "font-size: 10px; font-weight: bold; padding: 0 4px; }"
        )

        self.combo_mode.blockSignals(True)
        target_idx = 0
        for row_idx in range(self.combo_mode.count()):
            loops, skip = self.combo_mode.itemData(row_idx)
            if skip == sec.skip and (skip or loops == sec.loops):
                target_idx = row_idx
                break
        self.combo_mode.setCurrentIndex(target_idx)
        self.combo_mode.blockSignals(False)


class SectionControlBar(QWidget):
    """Horizontally aligned section pills & loop dropdowns matching Waveform timestamps."""

    section_jump_requested = Signal(int)
    section_mode_changed = Signal(int, int, bool)  # idx, loops, skip
    section_remove_requested = Signal(int)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._sections: list[CueSection] = []
        self._duration_sec: float = 0.0
        self._view_start_sec: float = 0.0
        self._view_span_sec: float = 0.0
        self._active_index: int = -1
        self._cells: list[_SectionCell] = []
        self.setFixedHeight(28)
        self.setVisible(False)
        self.setStyleSheet("background-color: #0d131c; border-top: 1px solid #1e293b;")

    def set_view_window(self, view_start_sec: float, view_span_sec: float) -> None:
        """Align section controls dynamically when Waveform zoom/pan changes."""
        self._view_start_sec = max(0.0, float(view_start_sec))
        self._view_span_sec = max(0.0, float(view_span_sec))
        self._relayout_cells()

    def set_sections(
        self,
        sections: Sequence[CueSection],
        duration_sec: float,
        active_index: int = -1,
    ) -> None:
        self._sections = [CueSection(**s.to_dict()) for s in sections]
        self._duration_sec = max(0.0, float(duration_sec))
        self._active_index = active_index

        has_secs = len(self._sections) >= 2 and self._duration_sec > 0
        if not has_secs:
            self.setVisible(False)
            for c in self._cells:
                c.hide()
            return

        while len(self._cells) < len(self._sections):
            cell = _SectionCell(len(self._cells), self)
            cell.jump_clicked.connect(self.section_jump_requested)
            cell.mode_changed.connect(self.section_mode_changed)
            cell.remove_clicked.connect(self.section_remove_requested)
            self._cells.append(cell)

        for i, cell in enumerate(self._cells):
            if i < len(self._sections):
                cell.sync(self._sections[i], is_active=(i == self._active_index))
                cell.show()
            else:
                cell.hide()

        self.setVisible(True)
        self._relayout_cells()

    def set_active_index(self, active_index: int) -> None:
        if self._active_index == active_index:
            return
        self._active_index = active_index
        for i, sec in enumerate(self._sections):
            if i < len(self._cells):
                self._cells[i].sync(sec, is_active=(i == active_index))

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._relayout_cells()

    def _relayout_cells(self) -> None:
        n = len(self._sections)
        if n < 2 or self._duration_sec <= 0 or len(self._cells) < n:
            return
        w = max(1, self.width())
        h = self.height()
        dur = self._duration_sec
        span = self._view_span_sec if self._view_span_sec > 0 else dur
        v_start = max(0.0, min(dur, self._view_start_sec))
        v_end = v_start + span

        # Track visible sections within current zoomed time viewport
        vis_indices: list[int] = []
        starts_x: list[int] = []
        ends_x: list[int] = []
        for i, sec in enumerate(self._sections):
            end_s = sec.end if sec.end is not None else dur
            if end_s <= v_start + 1e-4 or sec.start >= v_end - 1e-4:
                self._cells[i].hide()
                continue
            x0 = max(0, int(round(((sec.start - v_start) / span) * w)))
            x1 = min(w, max(x0 + 1, int(round(((end_s - v_start) / span) * w))))
            vis_indices.append(i)
            starts_x.append(x0)
            ends_x.append(x1)

        if not vis_indices:
            return

        min_cell_w = min(84, max(48, w // max(1, len(vis_indices))))
        for k, sec_idx in enumerate(vis_indices):
            cw = ends_x[k] - starts_x[k]
            if cw < min_cell_w:
                diff = min_cell_w - cw
                if ends_x[k] + diff <= w:
                    ends_x[k] += diff
                    if k + 1 < len(vis_indices):
                        starts_x[k + 1] = max(starts_x[k + 1], ends_x[k])
                else:
                    starts_x[k] = max(0, starts_x[k] - diff)
                    if k > 0:
                        ends_x[k - 1] = min(ends_x[k - 1], starts_x[k])
            cell = self._cells[sec_idx]
            cell.setGeometry(starts_x[k], 1, max(32, ends_x[k] - starts_x[k]), h - 2)
            cell.show()
