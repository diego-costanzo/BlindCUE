"""Drag-and-drop media import widget for BlindCue."""

from __future__ import annotations

import logging
import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QLabel, QWidget

from ui.theme import CLR_PANEL, CLR_PREVIZ

logger = logging.getLogger(__name__)


class DropZone(QLabel):
    """Drag-and-drop file import zone."""

    file_dropped = Signal(str)  # absolute path of dropped file

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create the drag-and-drop target shown when the rundown is empty."""
        super().__init__(parent)
        self.setText("Trascina qui file multimediali\n(Video, Audio, Immagini)\nper aggiungerli alla regia")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(160, 80)
        self.setStyleSheet(f"""
            QLabel {{
                border: 2px dashed {CLR_PREVIZ};
                border-radius: 6px;
                background-color: {CLR_PANEL};
                color: {CLR_PREVIZ};
                font-size: 11px;
                font-weight: bold;
                padding: 6px;
            }}
        """)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        """Accept the drag only when the payload carries file URLs."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        """Emit one ``file_dropped`` per existing local file."""
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path and os.path.isfile(path):
                self.file_dropped.emit(path)
                logger.info("[DROP] File dropped: %s", path)

