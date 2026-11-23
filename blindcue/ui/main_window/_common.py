"""Shared imports, constants and helpers for the MainWindow mixins."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import numpy as np
from PySide6.QtCore import QEvent, QObject, QRunnable, QSettings, Qt, QThreadPool, QTimer, Signal, Slot
from PySide6.QtGui import QAction, QActionGroup, QColor, QFont, QIcon, QImageReader, QKeySequence, QShortcut
from PySide6.QtMultimedia import QVideoSink
from PySide6.QtWidgets import (
    QAbstractItemView,
    QAbstractSpinBox,
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from engine.audio_analyzer import (
    DynamicsOptimizer,
    LoudnessScanner,
    WaveformAnalyzer,
)
from engine.earcon import EarconManager
from engine.envelope import (
    evaluate_cue_level,
    merge_section_at,
    normalize_sections,
    split_sections_at,
)
from engine.show_engine import (
    ShowEngine,
    chain_indices,
    demote_live_on_layer as _demote_live_on_layer,
)
from models.cue import (
    Cue,
    CueStatus,
    FollowMode,
    GroupMode,
    LayerConflict,
    MediaType,
    _sanitize_hex_color,
    detect_layer_conflicts,
    layer_label,
    normalize_output_target,
    resolve_output_target,
    runtime_layer,
)
from models.project_manager import ProjectManager
from models.surface import SurfaceDefinition, create_default_surface
from ui.surface_mapping_dialog import SurfaceMappingDialog
from ui.cue_list_panel import CueListPanel
from ui.cue_table import (
    ROLE_CHILD_COUNT,
    ROLE_CUE_COLOR,
    ROLE_FOLLOW_MODE,
    ROLE_GROUP_COLLAPSED,
    ROLE_GROUP_MODE,
    ROLE_HAS_NOTES,
    ROLE_INCOMING_LINK,
    ROLE_IS_GROUP,
    ROLE_IS_LAST_CHILD,
    ROLE_LAYER,
    ROLE_LAYER_CONFLICT,
    ROLE_MEDIA_TYPE,
    ROLE_OUTPUT_TARGET,
    ROLE_PARENT_ID,
    ROLE_PREV_COLOR,
    ROLE_STATUS_CLR,
    ROLE_STATUS_TXT,
    ROLE_TIMELINE_COMPOSED,
    ROLE_TIMING_BADGE,
    CueSequenceTable,
    CueTableDelegate,
    format_cue_ref,
)
from ui.drop_zone import DropZone
from ui.group_timeline_editor import GroupTimelineStudioDialog
from ui.hardware_info import (
    ShowRuntimeGuard,
    detect_hardware_brief,
    show_about_dialog,
    show_hardware_info_dialog,
)
from ui.hold_button import HoldProgressButton
from ui.inspector_panel import CueInspectorPanel
from ui.live_show_view import LiveShowPanel
from ui.live_status_panel import LiveStatusPanel
from ui.mask_dialog import ImageMaskDialog
from ui.output_window import OutputWindow
from ui.preview_monitor import StudioPreviewMonitor
from ui.preview_panel import PreviewControlPanel
from ui.spinboxes import InPointSpinBox, OutPointSpinBox, SmartDoubleSpinBox
from ui.theme import (
    AUDIO_EXT,
    CLR_LIVE,
    CLR_PREVIZ,
    CLR_TEXT,
    CLR_TEXT_MUTED,
    DEFAULT_LOGO_PATH,
    IMAGE_EXT,
    THEMES,
    VIDEO_EXT,
    get_active_theme,
    set_active_theme,
)
from ui.undo_manager import UndoManager
from ui.waveform_widget import WaveformPanel, WaveformWidget

logger = logging.getLogger(__name__)


_MEDIA_ICONS = {
    MediaType.VIDEO: "🎬",
    MediaType.AUDIO: "🎵",
    MediaType.IMAGE: "🖼",
    MediaType.ACTION: "⚡",
}

_DEFAULT_TOP_RATIOS: tuple[float, float, float] = (0.25, 0.45, 0.30)


class _AutosaveSignals(QObject):
    """Signals emitted by the background autosave worker back to the GUI thread."""

    finished = Signal()


class _AutosaveWorker(QRunnable):
    """Persist a pre-built autosave payload on a worker thread.

    The recovery payload is assembled on the GUI thread (in
    ``ProjectManager.build_autosave_payload``) so no live GUI state is touched
    here; this worker only performs the blocking disk I/O (JSON encode + fsync +
    atomic rename), keeping the Qt main thread responsive during the show.
    """

    def __init__(self, project_manager: ProjectManager, payload: dict[str, Any]) -> None:
        """Serialize ``payload`` in the background; ownership stays with the caller."""
        super().__init__()
        self.signals = _AutosaveSignals()
        self._project_manager = project_manager
        self._payload = payload
        # Keep ownership in Python: the MainWindow holds a reference until the
        # finished signal is processed, then releases it.  This avoids the
        # QRunnable being freed by the pool while the queued signal is pending.
        self.setAutoDelete(False)

    def run(self) -> None:  # noqa: D102
        """Write one autosave snapshot on a worker thread (QRunnable override)."""
        try:
            self._project_manager.write_autosave_payload(self._payload)
        finally:
            # Always signal completion so the GUI can clear its in-flight flag,
            # even if the write unexpectedly raises.
            self.signals.finished.emit()
