"""Panel Width Lock & Standard Layout Management mixin for MainWindow."""

from __future__ import annotations

from ui.main_window._common import *  # noqa: F403,F401,F405
from ui.main_window._common import (  # noqa: F401
    _AutosaveWorker,
    _DEFAULT_TOP_RATIOS,
    _MEDIA_ICONS,
    _demote_live_on_layer,
)


class _LayoutMixin:
    def _apply_top_splitter_ratios(self) -> None:
        if not hasattr(self, "_top_splitter"):
            return
        total = self._top_splitter.width()
        if total <= 0:
            return
        r0, r1, r2 = self._top_ratios
        w0 = max(290, int(round(total * r0)))
        w2 = max(360, int(round(total * r2)))
        w1 = max(380, total - w0 - w2)
        self._applying_splitter_layout = True
        try:
            self._top_splitter.setSizes([w0, w1, w2])
        finally:
            self._applying_splitter_layout = False

    def _on_top_splitter_moved(self, _pos: int, _index: int) -> None:
        if self._applying_splitter_layout or self._panels_locked:
            return
        sizes = self._top_splitter.sizes()
        total = sum(sizes)
        if total > 0 and len(sizes) == 3:
            self._top_ratios = (sizes[0] / total, sizes[1] / total, sizes[2] / total)

    def _set_panels_locked(self, locked: bool, announce: bool = True) -> None:
        self._panels_locked = locked
        if hasattr(self, "_act_lock_layout"):
            self._act_lock_layout.blockSignals(True)
            self._act_lock_layout.setChecked(locked)
            self._act_lock_layout.blockSignals(False)

        if hasattr(self, "_btn_lock_layout"):
            self._btn_lock_layout.blockSignals(True)
            self._btn_lock_layout.setChecked(locked)
            if locked:
                self._btn_lock_layout.setText("🔒 Pannelli Bloccati")
                self._btn_lock_layout.setStyleSheet(
                    "QPushButton { background-color: #16202e; color: #94a3b8; border: 1px solid #2b3b52; "
                    "border-radius: 3px; font-size: 10px; padding: 1px 8px; } "
                    "QPushButton:hover { border-color: #38bdf8; color: #ffffff; }"
                )
            else:
                self._btn_lock_layout.setText("🔓 Pannelli Sbloccati (Trascina bordi)")
                self._btn_lock_layout.setStyleSheet(
                    "QPushButton { background-color: #452408; color: #fbbf24; border: 1px solid #f59e0b; "
                    "border-radius: 3px; font-size: 10px; font-weight: bold; padding: 1px 8px; } "
                    "QPushButton:hover { background-color: #5c310b; }"
                )
            self._btn_lock_layout.blockSignals(False)

        for splitter in (getattr(self, "_top_splitter", None), getattr(self, "_bottom_splitter", None)):
            if splitter is None:
                continue
            splitter.setHandleWidth(5)
            splitter.setStyleSheet(
                "QSplitter::handle { background-color: #182230; }"
                if locked
                else (
                    "QSplitter::handle { background-color: #26415c; } "
                    "QSplitter::handle:hover { background-color: #38bdf8; }"
                )
            )
            for idx in range(1, splitter.count()):
                handle = splitter.handle(idx)
                handle.setEnabled(not locked)
                handle.setCursor(Qt.CursorShape.ArrowCursor if locked else Qt.CursorShape.SplitHCursor)

        if announce and hasattr(self, "_status_label"):
            if locked:
                self._status_label.setText("Layout bloccato: le larghezze dei 3 pannelli principali sono fisse")
            else:
                self._status_label.setText("Layout sbloccato: trascina i divisori verticali per adattare i pannelli a piacere")

    @Slot()
    def _reset_standard_layout(self) -> None:
        self._top_ratios = _DEFAULT_TOP_RATIOS
        self._apply_top_splitter_ratios()
        if hasattr(self, "_bottom_splitter"):
            self._bottom_splitter.setSizes([460, 320, 220])
        if hasattr(self, "_status_label"):
            self._status_label.setText("Larghezze standard dei pannelli ripristinate")

    def showEvent(self, event) -> None:  # noqa: N802
        """Restore the saved splitter ratios once the first layout is ready."""
        super().showEvent(event)
        QTimer.singleShot(0, self._apply_top_splitter_ratios)

    def resizeEvent(self, event) -> None:  # noqa: N802
        """Keep the configured splitter ratios when the window is resized."""
        super().resizeEvent(event)
        self._apply_top_splitter_ratios()
