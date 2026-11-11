"""Director / Control Panel – main window of BlindCue.

Composes modular UI panels (cue list, Pre-Viz sandbox, Cue Inspector,
Waveform, Live Output Status, Drop Zone) and coordinates show playback,
Undo/Redo, Live Mirror, and project persistence on the primary monitor.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Optional

import numpy as np
from PySide6.QtCore import QEvent, Qt, QThreadPool, QTimer, Signal, Slot
from PySide6.QtGui import QAction, QColor, QFont, QIcon, QImageReader, QKeySequence, QShortcut
from PySide6.QtMultimedia import QVideoSink
from PySide6.QtWidgets import (
    QAbstractItemView,
    QAbstractSpinBox,
    QApplication,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStatusBar,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from engine.audio_analyzer import WaveformAnalyzer
from models.cue import Cue, CueStatus, MediaType
from models.project_manager import ProjectManager
from ui.cue_list_panel import CueListPanel
from ui.cue_table import (
    ROLE_HAS_NOTES,
    ROLE_LAYER,
    ROLE_MEDIA_TYPE,
    ROLE_STATUS_CLR,
    ROLE_STATUS_TXT,
    CueSequenceTable,
    CueTableDelegate,
    format_cue_ref,
)
from ui.drop_zone import DropZone
from ui.hardware_info import detect_hardware_brief, show_about_dialog, show_hardware_info_dialog
from ui.inspector_panel import CueInspectorPanel
from ui.live_status_panel import LiveStatusPanel
from ui.output_window import OutputWindow
from ui.preview_monitor import StudioPreviewMonitor
from ui.preview_panel import PreviewControlPanel
from ui.spinboxes import InPointSpinBox, OutPointSpinBox, SmartDoubleSpinBox
from ui.theme import (
    AUDIO_EXT,
    CLR_GO,
    CLR_LIVE,
    CLR_PREVIZ,
    CLR_TEXT,
    CLR_TEXT_MUTED,
    DARK_STYLESHEET,
    DEFAULT_LOGO_PATH,
    IMAGE_EXT,
    VIDEO_EXT,
)
from ui.undo_manager import UndoManager
from ui.waveform_widget import WaveformWidget

logger = logging.getLogger(__name__)

__all__ = [
    "CueSequenceTable",
    "CueTableDelegate",
    "DropZone",
    "InPointSpinBox",
    "MainWindow",
    "OutPointSpinBox",
    "SmartDoubleSpinBox",
    "StudioPreviewMonitor",
    "WaveformWidget",
]

_MEDIA_ICONS = {
    MediaType.VIDEO: "🎬",
    MediaType.AUDIO: "🎵",
    MediaType.IMAGE: "🖼",
}

_DEFAULT_TOP_RATIOS: tuple[float, float, float] = (0.24, 0.49, 0.27)


class MainWindow(QMainWindow):
    """Director / Control Panel."""

    cue_fired = Signal(object)                     # emits Cue
    cue_preview_requested = Signal(object)         # emits Cue to load in preview
    layer_clear_requested = Signal(int)            # emits layer (1, 2, or 3)
    blackout_requested = Signal()                  # emits when blackout triggered
    preview_mute_toggled = Signal(bool)            # emits is_muted (True or False)
    preview_in_out_changed = Signal(float, object) # emits in_sec, out_sec
    live_volume_changed = Signal(int)              # emits volume 0-100

    def __init__(self, output_window: OutputWindow,
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._output = output_window
        self._cues: list[Cue] = []
        self._current_index: int = -1
        self._thread_pool = QThreadPool.globalInstance()
        self._test_player = None
        self._active_analyzers: set = set()
        self._active_test_duration: float = 0.0

        self._project_manager = ProjectManager()
        self._current_project_path: Optional[str] = None
        self._layer0_image: Optional[str] = None
        self._is_modified: bool = False
        self._updating_cue_list: bool = False
        self._force_closing: bool = False
        self._live_mirror_active: bool = False
        self._last_mirrored_layer: Optional[int] = None
        self._last_selection_sig: Optional[tuple] = None
        self._media_res_cache: dict[str, tuple[int, int]] = {}
        self._panels_locked: bool = True
        self._top_ratios: tuple[float, float, float] = _DEFAULT_TOP_RATIOS
        self._applying_splitter_layout: bool = False

        self._undo = UndoManager(self)
        self._undo.commit_requested.connect(self._commit_undo_point)
        self._undo.history_changed.connect(self._on_undo_history_changed)

        self._setup_window()
        self._build_menu_bar()
        self._build_ui()
        self._setup_shortcuts()
        self._update_inspector(None)
        self._build_status_bar()
        self._set_panels_locked(True, announce=False)
        self._setup_autosave()
        self._undo.set_committed_state(self._cues, self._current_index)

        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

        QTimer.singleShot(150, self._check_crash_recovery)

    # ── Window setup ──────────────────────────────────────────────────

    def _setup_window(self) -> None:
        self._update_window_title()
        self.setMinimumSize(1100, 680)
        self.resize(1400, 850)
        self.setStyleSheet(DARK_STYLESHEET)

        if DEFAULT_LOGO_PATH.is_file():
            self.setWindowIcon(QIcon(str(DEFAULT_LOGO_PATH)))

        self.bind_to_primary_screen()

    def bind_to_primary_screen(self, screen=None) -> None:
        """Bind MainWindow and its native handle to the primary monitor and fit inside it."""
        target = screen or QApplication.primaryScreen()
        if target is None:
            return
        avail = target.availableGeometry()
        if avail.width() > 0 and avail.height() > 0:
            self.setMinimumSize(min(1100, avail.width()), min(680, avail.height()))
            w = min(1400, avail.width())
            h = min(850, avail.height())
            x = avail.x() + max(0, (avail.width() - w) // 2)
            y = avail.y() + max(0, (avail.height() - h) // 2)
            self.setScreen(target)
            self.create()
            handle = self.windowHandle()
            if handle is not None:
                handle.setScreen(target)
            self.setGeometry(x, y, w, h)

    def _setup_autosave(self) -> None:
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setInterval(30000)
        self._autosave_timer.timeout.connect(self._auto_save)
        self._autosave_timer.start()

    def _setup_shortcuts(self) -> None:
        QShortcut(QKeySequence(Qt.Key.Key_Delete), self, self._on_delete_cue)
        QShortcut(QKeySequence(Qt.Key.Key_Backspace), self, self._on_delete_cue)
        QShortcut(QKeySequence("Alt+Up"), self, self._on_move_up)
        QShortcut(QKeySequence("Alt+Down"), self, self._on_move_down)
        QShortcut(QKeySequence("Ctrl+B"), self, self._on_blackout)
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, self._on_escape_pressed)

    @Slot()
    def _on_escape_pressed(self) -> None:
        if hasattr(self, "_cue_list") and self._cue_list.state() == QAbstractItemView.State.EditingState:
            return
        if hasattr(self, "_btn_test_stop"):
            self._btn_test_stop.click()

    # ── Undo / Redo Integration ───────────────────────────────────────

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        """Route Ctrl+Z / Ctrl+Shift+Z / Ctrl+Y to Cue Undo/Redo unless mid-typing in QLineEdit."""
        if event.type() == QEvent.Type.KeyPress and hasattr(obj, "window") and obj.window() is self:
            if isinstance(obj, QLineEdit):
                is_inline = (
                    hasattr(self, "_cue_list")
                    and self._cue_list.state() == QAbstractItemView.State.EditingState
                )
                mid_typing = is_inline or self._undo.is_debounce_active()
                if event.matches(QKeySequence.StandardKey.Undo):
                    if mid_typing and obj.isUndoAvailable():
                        return False
                    self._on_undo()
                    return True
                if (
                    event.matches(QKeySequence.StandardKey.Redo)
                    or (event.key() == Qt.Key.Key_Y and event.modifiers() == Qt.KeyboardModifier.ControlModifier)
                ):
                    if mid_typing and obj.isRedoAvailable():
                        return False
                    self._on_redo()
                    return True
        return super().eventFilter(obj, event)

    def _current_row_or_index(self) -> int:
        return self._cue_list.currentRow() if hasattr(self, "_cue_list") else self._current_index

    def _on_undo_history_changed(self, can_undo: bool, can_redo: bool) -> None:
        if hasattr(self, "_act_undo"):
            self._act_undo.setEnabled(can_undo)
        if hasattr(self, "_act_redo"):
            self._act_redo.setEnabled(can_redo)

    def _schedule_undo_point(self) -> None:
        self._undo.schedule_commit()

    @Slot()
    def _commit_undo_point(self) -> None:
        self._undo.commit(self._cues, self._current_row_or_index())

    def _reset_undo_history(self) -> None:
        self._undo.reset(self._cues, self._current_row_or_index())

    def _restore_snapshot(self, snapshot: dict) -> None:
        """Restore cues and settings from a snapshot without interrupting LIVE playback."""
        self._undo.restoring = True
        try:
            self._undo.stop_debounce()

            live_ids = {c.cue_id for c in self._cues if c.status == CueStatus.LIVE}
            prev_row = self._cue_list.currentRow()
            prev_cue_id = self._cues[prev_row].cue_id if 0 <= prev_row < len(self._cues) else None
            prev_file = self._cues[prev_row].file_path if 0 <= prev_row < len(self._cues) else None

            restored: list[Cue] = []
            for raw in snapshot.get("cues", []):
                cue = Cue.from_dict(raw)
                if cue.cue_id in live_ids:
                    cue.status = CueStatus.LIVE
                elif raw.get("status") == CueStatus.OFFLINE.value:
                    cue.status = CueStatus.OFFLINE
                else:
                    cue.status = CueStatus.LOADED
                restored.append(cue)

            self._cues = restored
            target_row = int(snapshot.get("current_index", -1))
            if restored and not (0 <= target_row < len(restored)):
                target_row = min(max(0, prev_row), len(restored) - 1)
            elif not restored:
                target_row = -1

            self._current_index = target_row
            self._last_selection_sig = None
            self._refresh_cue_list(keep_selection=False, select_row=target_row)

            if 0 <= target_row < len(self._cues):
                cue = self._cues[target_row]
                same_cue = (cue.cue_id == prev_cue_id and cue.file_path == prev_file)
                self._update_inspector(cue)
                self._update_cue_readouts(target_row, cue)

                if same_cue:
                    self._render_cue_in_preview(cue, load_image=True)
                    if self._live_mirror_active:
                        self._mirror_active_cue_to_live()
                else:
                    self._on_cue_selected(target_row)
            else:
                self._reset_idle_preview_ui()
                self._update_inspector(None)

            for c in self._cues:
                if c.status == CueStatus.LIVE:
                    self._update_live_layer_label(c)

            self._undo.set_committed_state(self._cues, self._current_row_or_index())
            self._mark_modified(True)
            self._auto_save()
        finally:
            self._undo.restoring = False
            self._on_undo_history_changed(self._undo.can_undo, self._undo.can_redo)

    @Slot()
    def _on_undo(self) -> None:
        if self._undo.is_debounce_active():
            self._commit_undo_point()
        prev = self._undo.pop_undo(self._cues, self._current_row_or_index())
        if prev is None:
            self._status_label.setText("Nessuna operazione da annullare")
            return
        self._restore_snapshot(prev)
        self._status_label.setText(
            f"↶ Annulla (Ctrl+Z) — Stato precedente ripristinato ({len(self._undo._undo_stack)} nel registro)"
        )

    @Slot()
    def _on_redo(self) -> None:
        nxt = self._undo.pop_redo(self._cues, self._current_row_or_index())
        if nxt is None:
            self._status_label.setText("Nessuna operazione da ripetere")
            return
        self._restore_snapshot(nxt)
        self._status_label.setText(
            f"↷ Ripeti — Modifica ripristinata ({len(self._undo._redo_stack)} ripetibili)"
        )

    def _update_window_title(self) -> None:
        name = Path(self._current_project_path).name if self._current_project_path else "Nuovo Show"
        mod = " *" if self._is_modified else ""
        self.setWindowTitle(f"BlindCue – [{name}{mod}] – Director Panel v0.1")

    def _mark_modified(self, modified: bool = True) -> None:
        self._is_modified = modified
        self._update_window_title()

    # ── Menu bar & UI Composition ─────────────────────────────────────

    def _build_menu_bar(self) -> None:
        mb = self.menuBar()

        file_menu = mb.addMenu("&File")
        file_menu.addAction(
            QAction("&New Show", self, shortcut=QKeySequence.StandardKey.New, triggered=self._on_new_show)
        )
        file_menu.addAction(
            QAction("&Open Show…", self, shortcut=QKeySequence.StandardKey.Open, triggered=self._on_open_show)
        )
        file_menu.addAction(
            QAction("&Save Show", self, shortcut=QKeySequence.StandardKey.Save, triggered=self._on_save_show)
        )
        file_menu.addAction(
            QAction("Save Show &As…", self, shortcut=QKeySequence("Ctrl+Shift+S"), triggered=self._on_save_as_show)
        )
        file_menu.addSeparator()
        file_menu.addAction(
            QAction("&Quit", self, shortcut=QKeySequence.StandardKey.Quit, triggered=self._on_quit)
        )

        edit_menu = mb.addMenu("&Modifica")
        self._act_undo = QAction("↶ &Annulla", self, triggered=self._on_undo)
        self._act_undo.setShortcut(QKeySequence.StandardKey.Undo)
        self._act_undo.setEnabled(False)
        self._act_redo = QAction("↷ &Ripeti", self, triggered=self._on_redo)
        self._act_redo.setShortcuts([
            QKeySequence.StandardKey.Redo,
            QKeySequence("Ctrl+Y"),
            QKeySequence("Ctrl+Shift+Z"),
        ])
        self._act_redo.setEnabled(False)
        edit_menu.addAction(self._act_undo)
        edit_menu.addAction(self._act_redo)

        show_menu = mb.addMenu("&Show")
        show_menu.addAction(
            QAction("&GO (Next Cue)", self, shortcut=QKeySequence("Space"), triggered=self._on_go)
        )
        show_menu.addAction(
            QAction("&Blackout", self, shortcut=QKeySequence("Ctrl+B"), triggered=self._on_blackout)
        )
        show_menu.addSeparator()
        show_menu.addAction(
            QAction("Imposta Immagine di &Tappo (Layer 0)…", self, triggered=self._on_choose_layer0)
        )
        show_menu.addAction(
            QAction("&Ripristina Tappo Predefinito", self, triggered=self._on_reset_layer0)
        )

        view_menu = mb.addMenu("&View")
        self._act_lock_layout = QAction("🔒 &Blocca Larghezza Pannelli", self, checkable=True)
        self._act_lock_layout.setChecked(True)
        self._act_lock_layout.toggled.connect(lambda checked: self._set_panels_locked(checked))
        view_menu.addAction(self._act_lock_layout)
        view_menu.addAction(
            QAction("↺ &Ripristina Larghezze Standard", self, triggered=self._reset_standard_layout)
        )

        help_menu = mb.addMenu("&Help")
        help_menu.addAction(
            QAction("&Info Hardware & Accelerazione…", self, triggered=lambda: show_hardware_info_dialog(self))
        )
        help_menu.addSeparator()
        help_menu.addAction(
            QAction("&About BlindCue", self, triggered=lambda: show_about_dialog(self))
        )

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(6, 6, 6, 6)
        root_layout.setSpacing(6)

        # Top splitter: Cue List | Preview + GO | Inspector
        top_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._top_splitter = top_splitter

        self._cue_list_panel = CueListPanel()
        self._cue_list = self._cue_list_panel.table
        self._lbl_cue_count = self._cue_list_panel.lbl_count
        self._lbl_cue_standby = self._cue_list_panel.lbl_standby
        self._cue_list.currentRowChanged.connect(self._on_cue_selected)
        self._cue_list.itemSelectionChanged.connect(self._on_cue_selection_changed)
        self._cue_list.cellDoubleClicked.connect(self._on_cue_cell_double_clicked)
        self._cue_list.itemChanged.connect(self._on_cue_item_changed)
        self._cue_list_panel.add_media_requested.connect(self._on_add_media)
        self._cue_list_panel.move_up_requested.connect(self._on_move_up)
        self._cue_list_panel.move_down_requested.connect(self._on_move_down)
        self._cue_list_panel.delete_requested.connect(self._on_delete_cue)
        top_splitter.addWidget(self._cue_list_panel)

        # Center column: Pre-Viz sandbox + GO trigger
        center_panel = QWidget()
        center_panel.setMinimumWidth(380)
        center_layout = QVBoxLayout(center_panel)
        center_layout.setContentsMargins(0, 0, 0, 0)

        self._preview_panel = PreviewControlPanel(self._output.get_layer0_path())
        self._preview_monitor = self._preview_panel.monitor
        self._btn_live_mirror = self._preview_panel.btn_live_mirror
        self._lbl_preview_info = self._preview_panel.lbl_info
        self._lbl_preview_time = self._preview_panel.lbl_time
        self._btn_test_play = self._preview_panel.btn_play
        self._btn_test_pause = self._preview_panel.btn_pause
        self._btn_test_stop = self._preview_panel.btn_stop
        self._btn_preview_mute = self._preview_panel.btn_mute

        self._preview_panel.live_mirror_toggled.connect(self._on_live_mirror_toggled)
        self._preview_panel.preview_mute_toggled.connect(self._on_preview_mute_toggled)
        self._preview_monitor.position_changed.connect(self._on_preview_position_changed)
        self._preview_monitor.crop_changed.connect(self._on_preview_crop_changed)
        self._preview_monitor.video_resolution_detected.connect(self._on_video_resolution_detected)
        center_layout.addWidget(self._preview_panel, stretch=1)

        self._btn_go = QPushButton("GO (Next Cue) — [ SPAZIO ]")
        self._btn_go.setMinimumHeight(48)
        self._btn_go.setMaximumHeight(54)
        self._btn_go.setFont(QFont("sans-serif", 18, QFont.Weight.Bold))
        self._btn_go.setStyleSheet(f"""
            QPushButton {{
                background-color: {CLR_GO};
                color: #000;
                border: none;
                border-radius: 6px;
                font-size: 18px;
            }}
            QPushButton:hover {{ background-color: #69f0ae; }}
            QPushButton:pressed {{ background-color: #00c853; }}
        """)
        self._btn_go.clicked.connect(self._on_go)
        center_layout.addWidget(self._btn_go, stretch=0)
        top_splitter.addWidget(center_panel)

        # Right: Cue Inspector
        self._inspector = CueInspectorPanel()
        self._inspector.value_changed.connect(self._on_inspector_value_changed)
        self._inspector.batch_field_edited.connect(self._on_batch_field_edited)
        self._inspector.layer_selected.connect(self._set_layer)
        self._bind_inspector_aliases()
        top_splitter.addWidget(self._inspector)

        top_splitter.setChildrenCollapsible(False)
        top_splitter.setStretchFactor(0, 24)
        top_splitter.setStretchFactor(1, 49)
        top_splitter.setStretchFactor(2, 27)
        top_splitter.setSizes([336, 686, 378])
        top_splitter.splitterMoved.connect(self._on_top_splitter_moved)
        root_layout.addWidget(top_splitter, stretch=7)

        # Bottom splitter: Waveform | Live Output Status | Drop Zone
        bottom_splitter = QSplitter(Qt.Orientation.Horizontal)
        bottom_splitter.setChildrenCollapsible(False)
        self._bottom_splitter = bottom_splitter

        waveform_group = QGroupBox("Forma d'Onda Audio (Waveform Analysis)")
        wf_layout = QVBoxLayout(waveform_group)
        lbl_wf_info = QLabel("Analisi dei picchi sonori e marcatori di inizio/fine (IN - OUT)")
        lbl_wf_info.setStyleSheet("color: #777; font-size: 10px;")
        wf_layout.addWidget(lbl_wf_info)
        self._waveform = WaveformWidget()
        self._waveform.in_changed.connect(self._on_waveform_in_changed)
        self._waveform.out_changed.connect(self._on_waveform_out_changed)
        wf_layout.addWidget(self._waveform)
        bottom_splitter.addWidget(waveform_group)

        self._live_status = LiveStatusPanel()
        self._lbl_tappo_info = self._live_status.lbl_tappo_info
        self._live_status.clear_layer_clicked.connect(self._on_clear_live_layer)
        self._live_status.blackout_clicked.connect(self._on_blackout)
        self._live_status.choose_layer0_clicked.connect(self._on_choose_layer0)
        self._live_status.reset_layer0_clicked.connect(self._on_reset_layer0)
        bottom_splitter.addWidget(self._live_status)

        drop_group = QGroupBox("Caricamento Rapido (Drag && Drop)")
        drop_layout = QVBoxLayout(drop_group)
        self._drop_zone = DropZone()
        self._drop_zone.file_dropped.connect(self._on_file_dropped)
        drop_layout.addWidget(self._drop_zone)
        bottom_splitter.addWidget(drop_group)

        bottom_splitter.setSizes([460, 320, 220])
        root_layout.addWidget(bottom_splitter, stretch=2)

    def _bind_inspector_aliases(self) -> None:
        """Expose direct references to inspector inputs for convenient integration."""
        insp = self._inspector
        self._grp_inspector = insp
        self._edit_cue_q = insp.edit_cue_q
        self._edit_cue_name = insp.edit_cue_name
        self._edit_cue_notes = insp.edit_cue_notes
        self._btn_layer1 = insp.btn_layer1
        self._btn_layer2 = insp.btn_layer2
        self._btn_layer3 = insp.btn_layer3
        self._spin_pos_x = insp.spin_pos_x
        self._spin_pos_y = insp.spin_pos_y
        self._spin_x = insp.spin_pos_x
        self._spin_y = insp.spin_pos_y
        self._slider_scale = insp.slider_scale
        self._slider_opacity = insp.slider_opacity
        self._slider_volume = insp.slider_volume
        self._spin_crop_l = insp.spin_crop_l
        self._spin_crop_r = insp.spin_crop_r
        self._spin_crop_t = insp.spin_crop_t
        self._spin_crop_b = insp.spin_crop_b
        self._spin_w = insp.spin_crop_r
        self._spin_h = insp.spin_crop_b
        self._spin_fade_in = insp.spin_fade_in
        self._spin_fade_out = insp.spin_fade_out
        self._spin_hold_time = insp.spin_hold_time
        self._chk_loop = insp.chk_loop
        self._combo_loop_mode = insp.combo_loop_mode
        self._spin_loop_count = insp.spin_loop_count
        self._combo_aspect = insp.combo_aspect
        self._spin_in = insp.spin_in
        self._spin_out = insp.spin_out

    def _build_status_bar(self) -> None:
        sb = QStatusBar()
        self._lbl_hw_info = QLabel(detect_hardware_brief())
        self._lbl_hw_info.setStyleSheet("color: #00bcd4; font-size: 11px; padding-left: 6px;")
        sb.addWidget(self._lbl_hw_info)

        self._btn_lock_layout = QPushButton("🔒 Layout: Bloccato")
        self._btn_lock_layout.setCheckable(True)
        self._btn_lock_layout.setChecked(True)
        self._btn_lock_layout.setFixedHeight(20)
        self._btn_lock_layout.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_lock_layout.setToolTip(
            "Blocca o sblocca le larghezze dei 3 pannelli principali (Scaletta, Anteprima, Ispettore).\n"
            "Di default è bloccato per evitare spostamenti accidentali; clicca per ridimensionare a piacere."
        )
        self._btn_lock_layout.toggled.connect(lambda checked: self._set_panels_locked(checked))
        sb.addWidget(self._btn_lock_layout)

        self._status_label = QLabel("Ready — No show loaded")
        self._status_label.setMinimumWidth(0)
        self._status_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        sb.addPermanentWidget(self._status_label, stretch=1)
        self.setStatusBar(sb)

    # ── Panel Width Lock & Standard Layout Management ─────────────────

    def _apply_top_splitter_ratios(self) -> None:
        if not hasattr(self, "_top_splitter"):
            return
        total = self._top_splitter.width()
        if total <= 0:
            return
        r0, r1, r2 = self._top_ratios
        w0 = max(260, int(round(total * r0)))
        w2 = max(340, int(round(total * r2)))
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
        super().showEvent(event)
        QTimer.singleShot(0, self._apply_top_splitter_ratios)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._apply_top_splitter_ratios()

    # ── Helpers & Table Population ────────────────────────────────────

    @staticmethod
    def _detect_media_type(file_path: str) -> Optional[MediaType]:
        ext = os.path.splitext(file_path)[1].lower()
        if ext in VIDEO_EXT:
            return MediaType.VIDEO
        if ext in AUDIO_EXT:
            return MediaType.AUDIO
        if ext in IMAGE_EXT:
            return MediaType.IMAGE
        return None

    def set_preview_time(self, current_sec: float, total_sec: float) -> None:
        if hasattr(self, "_preview_panel"):
            self._preview_panel.set_time(current_sec, total_sec)

    def _cue_tooltip(self, row: int, cue: Cue) -> str:
        parts = [f"Posizione: #{row + 1}"]
        if cue.q_label:
            parts.append(f"Q (Copione): {cue.q_label}")
        parts.append(f"Nome: {cue.name}")
        if cue.notes:
            parts.append(f"Note di Regia: {cue.notes}")
        parts.append(f"File: {cue.file_path}")
        return "\n".join(parts)

    def _update_cue_readouts(self, row: int, cue: Cue) -> None:
        ref = format_cue_ref(row, cue)
        icon = _MEDIA_ICONS.get(cue.media_type, "🖼")
        self._lbl_preview_info.setText(f"{icon} {ref}  {cue.name}")
        self._lbl_preview_info.setToolTip(f"File: {cue.file_path}")
        self._lbl_cue_standby.setText(f"Standby: {ref} [{cue.media_type.value}]")

    def _reset_idle_preview_ui(self) -> None:
        self._waveform.set_peaks(np.array([]))
        self._waveform.set_in_out_seconds(0.0, None, 0.0)
        self._lbl_preview_info.setText("— Nessun file selezionato —")
        self.set_preview_time(0.0, 0.0)
        self.clear_preview()

    def _populate_cue_row(self, row: int, cue: Cue, is_standby: bool) -> None:
        """Populate or update the 3 table cells (#, Q, Nome / Media) for a row."""
        status_txt = ""
        colour = CLR_TEXT
        if cue.status == CueStatus.LIVE:
            status_txt, colour = "LIVE", CLR_LIVE
        elif is_standby:
            status_txt, colour = "STANDBY", CLR_PREVIZ
        elif cue.status == CueStatus.PREVIZ:
            status_txt, colour = "PRE-VIZ", CLR_PREVIZ

        tooltip = self._cue_tooltip(row, cue)

        item_num = self._cue_list.item(row, 0)
        if item_num is None:
            item_num = QTableWidgetItem()
            item_num.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_num.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            self._cue_list.setItem(row, 0, item_num)
        item_num.setText(f"#{row + 1}")
        item_num.setForeground(QColor(colour if status_txt in ("LIVE", "STANDBY") else CLR_TEXT_MUTED))
        item_num.setToolTip(tooltip)

        item_q = self._cue_list.item(row, 1)
        if item_q is None:
            item_q = QTableWidgetItem()
            item_q.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_q.setFlags(
                Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsEditable
            )
            self._cue_list.setItem(row, 1, item_q)
        item_q.setText(cue.q_label)
        item_q.setToolTip(tooltip)

        item_name = self._cue_list.item(row, 2)
        if item_name is None:
            item_name = QTableWidgetItem()
            item_name.setFlags(
                Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsEditable
            )
            self._cue_list.setItem(row, 2, item_name)
        item_name.setText(cue.name)
        item_name.setData(ROLE_MEDIA_TYPE, cue.media_type.value)
        item_name.setData(ROLE_LAYER, cue.layer)
        item_name.setData(ROLE_HAS_NOTES, bool(cue.notes))
        item_name.setData(ROLE_STATUS_TXT, status_txt)
        item_name.setData(ROLE_STATUS_CLR, colour)
        item_name.setToolTip(tooltip)

    def _sync_inspector_header_and_text(self, row: int, cue: Cue) -> None:
        if 0 <= row < len(self._cues) and row == self._cue_list.currentRow():
            self._inspector.sync_header_and_text(row, cue)
            self._update_cue_readouts(row, cue)

    def _update_live_layer_label(self, cue: Cue) -> None:
        self._live_status.set_layer_live(cue)

    def _reset_live_label(self, layer: int) -> None:
        self._live_status.reset_layer(layer)

    @Slot(int, int)
    def _on_cue_cell_double_clicked(self, row: int, col: int) -> None:
        if not (0 <= row < len(self._cues)):
            return
        if col == 0:
            self._on_go()
        elif col in (1, 2):
            item = self._cue_list.item(row, col)
            if item is not None:
                self._cue_list.editItem(item)

    @Slot(QTableWidgetItem)
    def _on_cue_item_changed(self, item: QTableWidgetItem) -> None:
        """Handle inline editing of Q (col 1) or Nome (col 2) in the cue table."""
        if self._updating_cue_list:
            return
        row, col = item.row(), item.column()
        if not (0 <= row < len(self._cues)) or col not in (1, 2):
            return

        cue = self._cues[row]
        new_val = item.text().strip()
        old_val = cue.q_label if col == 1 else cue.name

        if col == 2 and not new_val:
            self._updating_cue_list = True
            self._cue_list.blockSignals(True)
            item.setText(old_val)
            self._cue_list.blockSignals(False)
            self._updating_cue_list = False
            return

        if new_val == old_val:
            return

        if self._undo.is_debounce_active():
            self._commit_undo_point()
        if col == 1:
            cue.q_label = new_val
        else:
            cue.name = new_val

        self._updating_cue_list = True
        self._cue_list.blockSignals(True)
        item.setText(new_val)
        tooltip = self._cue_tooltip(row, cue)
        for c_idx in range(3):
            cell = self._cue_list.item(row, c_idx)
            if cell is not None:
                cell.setToolTip(tooltip)
        self._cue_list.blockSignals(False)
        self._updating_cue_list = False

        self._sync_inspector_header_and_text(row, cue)
        if cue.status == CueStatus.LIVE:
            self._update_live_layer_label(cue)
        self._commit_undo_point()
        self._mark_modified(True)
        self._auto_save()

    def _update_selected_list_item(self, cue: Cue) -> None:
        """Lightweight in-place update for the active table row without focus stealing."""
        row = self._cue_list.currentRow()
        if not (0 <= row < len(self._cues)):
            return
        self._updating_cue_list = True
        self._cue_list.blockSignals(True)
        try:
            self._populate_cue_row(row, cue, is_standby=(cue.status != CueStatus.LIVE))
        finally:
            self._cue_list.blockSignals(False)
            self._updating_cue_list = False

        ref = format_cue_ref(row, cue)
        self._inspector.setTitle(f"ISPETTORE CUE — {ref} [{cue.media_type.value}] '{cue.name}'")
        self._update_cue_readouts(row, cue)
        if cue.status == CueStatus.LIVE:
            self._update_live_layer_label(cue)

    def _refresh_rows_in_place(self, rows: list[int]) -> None:
        """Update table cell visuals for *rows* in place without altering selection."""
        anchor_row, _ = self._anchor_row_and_cue()
        self._updating_cue_list = True
        self._cue_list.blockSignals(True)
        try:
            for row in rows:
                if 0 <= row < len(self._cues):
                    cue = self._cues[row]
                    is_standby = (row == anchor_row and cue.status != CueStatus.LIVE)
                    self._populate_cue_row(row, cue, is_standby=is_standby)
        finally:
            self._cue_list.blockSignals(False)
            self._updating_cue_list = False

    def _refresh_cue_list(self, keep_selection: bool = True,
                          select_row: Optional[int] = None) -> None:
        """Rebuild the 3-column table from the cue list with progressive row numbers."""
        prev_selected = self._selected_rows() if (keep_selection and select_row is None) else []

        if select_row is not None:
            target_row = select_row
        elif keep_selection:
            target_row = self._cue_list.currentRow()
            if target_row < 0 and 0 <= self._current_index < len(self._cues):
                target_row = self._current_index
        else:
            target_row = -1

        total_cues = len(self._cues)
        if total_cues == 0:
            self._lbl_cue_count.setText("0 Cue in scaletta")
            self._lbl_cue_standby.setText("Standby: Nessuna")
            self._update_inspector(None)
        else:
            self._lbl_cue_count.setText(f"{total_cues} Cue in scaletta")
            standby_row = target_row if (0 <= target_row < total_cues) else 0
            standby_cue = self._cues[standby_row]
            self._lbl_cue_standby.setText(
                f"Standby: {format_cue_ref(standby_row, standby_cue)} [{standby_cue.media_type.value}]"
            )

        self._updating_cue_list = True
        self._cue_list.blockSignals(True)
        try:
            self._cue_list.setRowCount(total_cues)
            self._cue_list._last_emitted_row = -1
            for i, cue in enumerate(self._cues):
                is_standby = (total_cues > 0 and i == target_row and cue.status != CueStatus.LIVE)
                self._populate_cue_row(i, cue, is_standby=is_standby)

            valid_prev = [r for r in prev_selected if 0 <= r < total_cues]
            if len(valid_prev) > 1 and select_row is None and keep_selection:
                self._cue_list.select_rows(valid_prev, anchor_row=target_row if target_row in valid_prev else valid_prev[0])
            elif 0 <= target_row < total_cues:
                self._cue_list.setCurrentRow(target_row)
            else:
                self._cue_list.clearSelection()
                self._last_selection_sig = None
        finally:
            self._cue_list.blockSignals(False)
            self._updating_cue_list = False

    def _selected_rows(self) -> list[int]:
        if not hasattr(self, "_cue_list"):
            return []
        return [r for r in self._cue_list.selected_rows() if 0 <= r < len(self._cues)]

    def _selected_cues(self) -> list[Cue]:
        return [self._cues[r] for r in self._selected_rows()]

    def _anchor_row_and_cue(self) -> tuple[int, Optional[Cue]]:
        rows = self._selected_rows()
        if not rows:
            return -1, None
        curr = self._cue_list.currentRow()
        anchor_row = curr if curr in rows else rows[0]
        return anchor_row, self._cues[anchor_row]

    def _selected_cue(self) -> Optional[Cue]:
        _, cue = self._anchor_row_and_cue()
        return cue

    # ── Waveform & Preview Layout Helpers ─────────────────────────────

    def update_waveform_duration(self, duration_sec: float) -> None:
        self._active_test_duration = max(0.001, duration_sec)
        self._inspector.spin_out.set_media_duration(self._active_test_duration)
        cue = self._selected_cue()
        if cue:
            self._waveform.set_in_out_seconds(cue.in_point, cue.out_point, self._active_test_duration)

    def _update_waveform_markers(self, cue: Optional[Cue] = None) -> None:
        if cue is None:
            cue = self._selected_cue()
        if cue is None or cue.media_type == MediaType.IMAGE:
            return
        self._waveform.set_in_out_seconds(cue.in_point, cue.out_point, self._active_test_duration)

    def _update_crop_reference_for_cue(self, cue: Cue) -> None:
        """Supply exact pixel dimensions (cached header/frame size) to Inspector Crop %/px."""
        cached = self._media_res_cache.get(cue.file_path)
        if cached is not None:
            self._inspector.set_crop_reference_size(cached[0], cached[1])
            return
        if cue.media_type == MediaType.IMAGE and os.path.isfile(cue.file_path):
            sz = QImageReader(cue.file_path).size()
            if sz.isValid() and sz.width() > 0 and sz.height() > 0:
                res = (sz.width(), sz.height())
                self._media_res_cache[cue.file_path] = res
                self._inspector.set_crop_reference_size(res[0], res[1])
                return
        self._inspector.set_crop_reference_size(1920, 1080)

    @Slot(int, int)
    def _on_video_resolution_detected(self, width: int, height: int) -> None:
        cue = self._selected_cue()
        if cue and cue.media_type == MediaType.VIDEO and width > 0 and height > 0:
            self._media_res_cache[cue.file_path] = (width, height)
            self._inspector.set_crop_reference_size(width, height)

    def _render_cue_in_preview(self, cue: Cue, load_image: bool = True) -> None:
        if cue.media_type == MediaType.VIDEO:
            if load_image:
                self.update_preview_video_layout(
                    scale=cue.scale, crop=cue.crop,
                    pos_x=cue.position_x, pos_y=cue.position_y,
                    opacity=cue.opacity, aspect_ratio=cue.aspect_ratio,
                )
            else:
                self.show_preview_video(
                    scale=cue.scale, crop=cue.crop,
                    pos_x=cue.position_x, pos_y=cue.position_y,
                    opacity=cue.opacity, aspect_ratio=cue.aspect_ratio,
                )
        elif cue.media_type == MediaType.IMAGE:
            self.show_preview_image(
                cue.file_path, scale=cue.scale, crop=cue.crop,
                pos_x=cue.position_x, pos_y=cue.position_y,
                opacity=cue.opacity, aspect_ratio=cue.aspect_ratio,
            )
        elif cue.media_type == MediaType.AUDIO:
            self.show_preview_audio()

    # ── Inspector & Waveform Interaction ──────────────────────────────

    def _update_inspector(self, cue: Optional[Cue]) -> None:
        if cue is None:
            self._inspector.load_cue(None)
            return
        sel_cues = self._selected_cues()
        anchor_row, anchor_cue = self._anchor_row_and_cue()
        if anchor_cue is not None:
            self._update_crop_reference_for_cue(anchor_cue)
        if len(sel_cues) > 1:
            self._inspector.load_selection(sel_cues, anchor_cue=anchor_cue, anchor_row=anchor_row)
        else:
            self._inspector.load_cue(cue, anchor_row)
        if anchor_cue is not None:
            self._update_waveform_markers(anchor_cue)

    @Slot(str)
    def _on_batch_field_edited(self, field_key: str) -> None:
        """Apply a single modified inspector property uniformly across same-type multi-selection."""
        sel_rows = self._selected_rows()
        if len(sel_rows) < 2:
            return
        sel_cues = [self._cues[r] for r in sel_rows]
        if len({c.media_type for c in sel_cues}) != 1:
            return

        self._inspector.apply_batch_field(field_key, sel_cues)
        self._schedule_undo_point()
        self._mark_modified(True)
        self._refresh_rows_in_place(sel_rows)

        anchor_row, anchor = self._anchor_row_and_cue()
        if anchor is not None:
            if field_key in ("in_point", "out_point"):
                self._update_waveform_markers(anchor)
                self.preview_in_out_changed.emit(anchor.in_point, anchor.out_point)
            if field_key == "volume":
                self.live_volume_changed.emit(self._inspector.slider_volume.value())
            if anchor.media_type in (MediaType.VIDEO, MediaType.IMAGE):
                self._render_cue_in_preview(anchor, load_image=(anchor.media_type == MediaType.VIDEO))
            if self._live_mirror_active:
                self._mirror_active_cue_to_live()

    @Slot()
    def _on_inspector_value_changed(self) -> None:
        sel_cues = self._selected_cues()
        if len(sel_cues) != 1:
            return
        self._apply_inspector_to_cue()
        self._schedule_undo_point()
        self._mark_modified(True)
        cue = sel_cues[0]
        self._update_selected_list_item(cue)
        if cue.media_type in (MediaType.VIDEO, MediaType.IMAGE):
            self._render_cue_in_preview(cue, load_image=(cue.media_type == MediaType.VIDEO))
        if self._live_mirror_active:
            self._mirror_active_cue_to_live()

    def _apply_inspector_to_cue(self) -> None:
        sel_cues = self._selected_cues()
        if len(sel_cues) != 1:
            return
        cue = sel_cues[0]
        self._inspector.apply_to_cue(cue)
        self._update_waveform_markers(cue)
        self.live_volume_changed.emit(self._inspector.slider_volume.value())
        self.preview_in_out_changed.emit(cue.in_point, cue.out_point)

    @Slot(float, float)
    def _on_preview_position_changed(self, pos_x: float, pos_y: float) -> None:
        self._inspector.set_position_silent(pos_x, pos_y)
        sel_cues = self._selected_cues()
        if not sel_cues or len({c.media_type for c in sel_cues}) != 1:
            return
        for cue in sel_cues:
            cue.position_x = pos_x
            cue.position_y = pos_y
        self._schedule_undo_point()
        self._mark_modified(True)
        if self._live_mirror_active:
            self._mirror_active_cue_to_live()

    @Slot(float, float, float, float)
    def _on_preview_crop_changed(self, crop_l: float, crop_r: float,
                                 crop_t: float, crop_b: float) -> None:
        self._inspector.set_crop_silent(crop_l, crop_r, crop_t, crop_b)
        sel_cues = self._selected_cues()
        if not sel_cues or len({c.media_type for c in sel_cues}) != 1:
            return
        crop_dict = {
            "x": round(crop_l, 6),
            "y": round(crop_t, 6),
            "w": max(0.01, round(1.0 - crop_l - crop_r, 6)),
            "h": max(0.01, round(1.0 - crop_t - crop_b, 6)),
        }
        for cue in sel_cues:
            cue.crop = dict(crop_dict)
        self._schedule_undo_point()
        self._mark_modified(True)
        if self._live_mirror_active:
            self._mirror_active_cue_to_live()

    @Slot(float)
    def _on_waveform_in_changed(self, new_in: float) -> None:
        self._inspector.set_in_silent(new_in)
        sel_cues = self._selected_cues()
        if not sel_cues or len({c.media_type for c in sel_cues}) != 1:
            return
        for cue in sel_cues:
            cue.in_point = new_in
            if cue.out_point is not None and cue.out_point <= new_in:
                cue.out_point = round(new_in + 0.05, 2)
        self._schedule_undo_point()
        self._mark_modified(True)
        anchor = self._selected_cue()
        if anchor:
            self.preview_in_out_changed.emit(anchor.in_point, anchor.out_point)

    @Slot(float)
    def _on_waveform_out_changed(self, new_out: float) -> None:
        self._inspector.set_out_silent(new_out)
        sel_cues = self._selected_cues()
        if not sel_cues or len({c.media_type for c in sel_cues}) != 1:
            return
        for cue in sel_cues:
            if new_out <= 0.0:
                cue.out_point = None
            elif new_out <= cue.in_point:
                cue.out_point = round(cue.in_point + 0.05, 2)
            else:
                cue.out_point = new_out
        self._schedule_undo_point()
        self._mark_modified(True)
        anchor = self._selected_cue()
        if anchor:
            self.preview_in_out_changed.emit(anchor.in_point, anchor.out_point)

    # ── Preview Mute & Live Layer Controls ────────────────────────────

    @Slot(bool)
    def _on_preview_mute_toggled(self, is_muted: bool) -> None:
        self._preview_panel.update_mute_style()
        self.preview_mute_toggled.emit(is_muted)
        state_txt = "Silenzioso (Muto)" if is_muted else "Ascolto Attivo"
        self._status_label.setText(f"Audio Preview: {state_txt}")

    @Slot(int)
    def _on_clear_live_layer(self, layer: int) -> None:
        self._reset_live_label(layer)
        for cue in self._cues:
            if cue.layer == layer and cue.status == CueStatus.LIVE:
                cue.status = CueStatus.LOADED
        self._refresh_cue_list()
        self.layer_clear_requested.emit(layer)
        self._status_label.setText(f"Layer {layer} arrestato e rimosso dal Live")
        logger.info("[LIVE STATUS] Cleared Layer %d", layer)

    # ── Layer 0 (Tappo) ───────────────────────────────────────────────

    def set_layer0_image(self, file_path: Optional[str]) -> bool:
        if self._output.set_layer0_image(file_path):
            self._layer0_image = file_path
            self._live_status.set_layer0_label(file_path)
            self._preview_monitor.set_layer0_image(file_path)
            return True
        return False

    @Slot()
    def _on_choose_layer0(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Seleziona Immagine di Tappo (Layer 0)",
            "",
            "Immagini (*.png *.jpg *.jpeg *.bmp *.webp *.svg);;Tutti i file (*)",
        )
        if file_path:
            if self.set_layer0_image(file_path):
                self._mark_modified(True)
                self._auto_save()
                self._status_label.setText(f"Tappo (Layer 0) impostato: {Path(file_path).name}")
            else:
                QMessageBox.warning(self, "File non valido", "Impossibile caricare l'immagine di tappo selezionata.")

    @Slot()
    def _on_reset_layer0(self) -> None:
        self._output.reset_layer0_default()
        self._layer0_image = None
        self._live_status.set_layer0_label(None)
        self._preview_monitor.set_layer0_image(str(DEFAULT_LOGO_PATH))
        self._mark_modified(True)
        self._auto_save()
        self._status_label.setText("Tappo (Layer 0) ripristinato al logo predefinito")

    # ── Selection & Live Mirror ───────────────────────────────────────

    @Slot(int)
    def _on_cue_selected(self, _row: int) -> None:
        self._sync_selection_state()

    @Slot()
    def _on_cue_selection_changed(self) -> None:
        self._sync_selection_state()

    def _sync_selection_state(self) -> None:
        """Update Inspector, Standby badges, Pre-Viz, and Waveform for 0, 1, or N selected cues."""
        if self._updating_cue_list:
            return
        if not self._undo.restoring and self._undo.is_debounce_active():
            self._commit_undo_point()

        sel_rows = self._selected_rows()
        anchor_row, cue = self._anchor_row_and_cue()
        sig = (tuple(sel_rows), anchor_row, cue.cue_id if cue else None)
        if sig == self._last_selection_sig:
            return
        prev_anchor_id = self._last_selection_sig[2] if self._last_selection_sig else None
        self._last_selection_sig = sig

        if cue is not None and 0 <= anchor_row < len(self._cues):
            self._current_index = anchor_row
            self._undo.update_current_index(anchor_row)
            self._refresh_rows_in_place(list(range(len(self._cues))))

            sel_cues = [self._cues[r] for r in sel_rows]
            self._update_crop_reference_for_cue(cue)
            self._inspector.load_selection(sel_cues, anchor_cue=cue, anchor_row=anchor_row)

            if cue.cue_id != prev_anchor_id:
                self._request_waveform(cue)
                self._waveform.set_playhead(None)
                self._render_cue_in_preview(cue, load_image=False)
                self.cue_preview_requested.emit(cue)

            self._update_waveform_markers(cue)
            self._update_cue_readouts(anchor_row, cue)
            if len(sel_cues) > 1:
                mtypes = {c.media_type for c in sel_cues}
                if len(mtypes) == 1:
                    self._lbl_cue_standby.setText(
                        f"Selezione: {len(sel_cues)} {cue.media_type.value}"
                    )
                else:
                    self._lbl_cue_standby.setText(f"Selezione mista: {len(sel_cues)} cue")

            if self._live_mirror_active:
                self._mirror_active_cue_to_live()

            logger.debug("Cue selected (count=%d): %s", len(sel_cues), cue)
        else:
            self._inspector.load_cue(None)
            self.clear_preview()
            self._lbl_preview_info.setText("— Nessun file selezionato —")
            self._lbl_cue_standby.setText("Standby: Nessuna")

    def _push_cue_to_output(self, cue: Cue) -> None:
        """Render an IMAGE or VIDEO cue onto its assigned output layer."""
        if cue.media_type == MediaType.IMAGE:
            self._output.show_image(
                cue.layer,
                cue.file_path,
                opacity=cue.opacity,
                crop=cue.crop,
                scale=cue.scale,
                pos_x=cue.position_x,
                pos_y=cue.position_y,
                aspect_ratio=cue.aspect_ratio,
            )
        elif cue.media_type == MediaType.VIDEO:
            self._output.show_video_widget(
                scale=cue.scale,
                crop=cue.crop,
                pos_x=cue.position_x,
                pos_y=cue.position_y,
                opacity=cue.opacity,
                layer=cue.layer,
                aspect_ratio=cue.aspect_ratio,
            )

    @Slot(bool)
    def _on_live_mirror_toggled(self, active: bool) -> None:
        self._live_mirror_active = active
        self._preview_panel.set_live_mirror_style(active)
        if active:
            self._status_label.setText(
                "PROGETTAZIONE: LIVE MIRROR ATTIVO (Modifiche visibili sullo schermo esterno)"
            )
            self._mirror_active_cue_to_live()
        else:
            self._status_label.setText(
                "LIVE MIRROR DISATTIVATO — Anteprima isolata (Pronto per lo spettacolo)"
            )
            self._restore_live_output()

    def _mirror_active_cue_to_live(self) -> None:
        cue = self._selected_cue()
        if not cue or not self._live_mirror_active:
            return
        try:
            prev_layer = self._last_mirrored_layer
            if prev_layer is not None and prev_layer != cue.layer:
                live_on_prev = next(
                    (c for c in self._cues if c.status == CueStatus.LIVE and c.layer == prev_layer),
                    None,
                )
                if live_on_prev is None:
                    self._output.clear_layer(prev_layer)
                else:
                    self._push_cue_to_output(live_on_prev)

            self._last_mirrored_layer = cue.layer
            self._push_cue_to_output(cue)
        except Exception as exc:
            logger.error("[LIVE MIRROR] Error mirroring cue: %s", exc)

    def _restore_live_output(self) -> None:
        try:
            self._last_mirrored_layer = None
            live_cues = [c for c in self._cues if c.status == CueStatus.LIVE]
            if not live_cues:
                self._output.show_fallback()
            else:
                self._output.clear_all_layers()
                for c in live_cues:
                    self._push_cue_to_output(c)
        except Exception as exc:
            logger.error("[LIVE MIRROR] Error restoring live output: %s", exc)

    @Slot(int)
    def _set_layer(self, layer: int) -> None:
        sel_rows = self._selected_rows()
        if not sel_rows:
            return
        sel_cues = [self._cues[r] for r in sel_rows]
        if len({c.media_type for c in sel_cues}) != 1:
            return

        self._inspector.set_layer_checked(layer)
        changed = any(cue.layer != layer for cue in sel_cues)
        if changed:
            if self._undo.is_debounce_active():
                self._commit_undo_point()
            for cue in sel_cues:
                cue.layer = layer
            self._refresh_rows_in_place(sel_rows)
            if len(sel_cues) > 1:
                anchor_row, anchor = self._anchor_row_and_cue()
                self._inspector.load_selection(sel_cues, anchor_cue=anchor, anchor_row=anchor_row)
            self._commit_undo_point()
            self._mark_modified(True)
            self._auto_save()

    # ── Playback Transport (GO / Blackout) ────────────────────────────

    @Slot()
    def _on_go(self) -> None:
        focus_w = QApplication.focusWidget()
        if isinstance(focus_w, (QLineEdit, QAbstractSpinBox, QComboBox)):
            return

        if not self._cues:
            self._status_label.setText("Scaletta vuota — Aggiungi prima dei file multimediali")
            return

        self._apply_inspector_to_cue()

        row, _ = self._anchor_row_and_cue()
        if 0 <= row < len(self._cues):
            target_idx = row
        elif 0 <= self._current_index < len(self._cues):
            target_idx = self._current_index
        else:
            target_idx = 0

        cue = self._cues[target_idx]
        for other in self._cues:
            if other.layer == cue.layer and other.cue_id != cue.cue_id and other.status == CueStatus.LIVE:
                other.status = CueStatus.LOADED

        cue.status = CueStatus.LIVE
        self._current_index = target_idx
        self.cue_fired.emit(cue)
        self._refresh_cue_list(keep_selection=False)
        self._update_live_layer_label(cue)

        ref = format_cue_ref(target_idx, cue)
        next_idx = target_idx + 1
        if next_idx < len(self._cues):
            self._cue_list.setCurrentRow(next_idx)
            next_ref = format_cue_ref(next_idx, self._cues[next_idx])
            self._status_label.setText(
                f"LIVE → {ref} '{cue.name}' (Layer {cue.layer}) | Standby: {next_ref} '{self._cues[next_idx].name}'"
            )
        else:
            self._cue_list.setCurrentRow(target_idx)
            self._status_label.setText(
                f"LIVE → {ref} '{cue.name}' (Layer {cue.layer}) — Fine scaletta (premi GO per rilanciare)"
            )

        self._auto_save()
        logger.info("[GO] Fired cue #%d: %s", cue.cue_id, cue)

    @Slot()
    def _on_blackout(self) -> None:
        self._output.show_fallback()
        for cue in self._cues:
            if cue.status == CueStatus.LIVE:
                cue.status = CueStatus.LOADED
        self._refresh_cue_list()
        self._live_status.reset_all_layers()
        self.blackout_requested.emit()
        self._status_label.setText("BLACKOUT — Output ripristinato a Layer 0 (Tappo)")
        logger.info("[BLACKOUT] Activated")

    # ── Cue List Manipulation ─────────────────────────────────────────

    def _on_add_media(self, media_type: MediaType) -> None:
        ext_map = {
            MediaType.VIDEO: "Video (*.mp4 *.mkv *.avi *.mov *.webm)",
            MediaType.AUDIO: "Audio (*.mp3 *.wav *.flac *.ogg *.aac *.m4a)",
            MediaType.IMAGE: "Image (*.png *.jpg *.jpeg *.bmp *.gif *.webp)",
        }
        file_path, _ = QFileDialog.getOpenFileName(
            self, f"Add {media_type.value}", "", ext_map.get(media_type, "All Files (*)")
        )
        if file_path:
            self._add_cue_from_file(file_path, media_type)

    def _add_cue_from_file(self, file_path: str, media_type: Optional[MediaType] = None) -> None:
        if media_type is None:
            media_type = self._detect_media_type(file_path)
        if media_type is None:
            QMessageBox.warning(self, "Unsupported File", f"Cannot determine media type for:\n{file_path}")
            return

        cue = Cue(name=os.path.basename(file_path), media_type=media_type, file_path=file_path)
        errors = cue.validate()
        if errors:
            QMessageBox.warning(self, "Validation Error", "\n".join(errors))
            return

        if self._undo.is_debounce_active():
            self._commit_undo_point()
        cue.status = CueStatus.LOADED
        self._cues.append(cue)
        self._refresh_cue_list()
        self._cue_list.setCurrentRow(len(self._cues) - 1)
        self._commit_undo_point()
        self._mark_modified(True)
        self._status_label.setText(f"Added: {cue}")
        self._auto_save()
        logger.info("Added cue: %s", cue)

    @Slot(str)
    def _on_file_dropped(self, file_path: str) -> None:
        self._add_cue_from_file(file_path)

    def _move_selected_cue(self, delta: int) -> None:
        sel_rows = self._selected_rows()
        if len(sel_rows) != 1:
            return
        row = sel_rows[0]
        target_row = row + delta
        if not (0 <= row < len(self._cues) and 0 <= target_row < len(self._cues)):
            return
        if self._undo.is_debounce_active():
            self._commit_undo_point()
        self._cues[row], self._cues[target_row] = self._cues[target_row], self._cues[row]
        self._current_index = target_row
        self._refresh_cue_list(keep_selection=False, select_row=target_row)
        self._sync_inspector_header_and_text(target_row, self._cues[target_row])
        self._commit_undo_point()
        self._mark_modified(True)
        self._auto_save()

    @Slot()
    def _on_move_up(self) -> None:
        self._move_selected_cue(-1)

    @Slot()
    def _on_move_down(self) -> None:
        self._move_selected_cue(1)

    @Slot()
    def _on_delete_cue(self) -> None:
        focus_w = QApplication.focusWidget()
        if isinstance(focus_w, (QLineEdit, QAbstractSpinBox, QComboBox)):
            return

        sel_rows = self._selected_rows()
        if not sel_rows:
            return
        if self._undo.is_debounce_active():
            self._commit_undo_point()
        anchor_row, _ = self._anchor_row_and_cue()
        self._undo.update_current_index(anchor_row)

        removed = [self._cues.pop(r) for r in sorted(sel_rows, reverse=True)]
        first_row = sel_rows[0]
        self._refresh_cue_list(keep_selection=False)
        if self._cues:
            self._cue_list.setCurrentRow(min(first_row, len(self._cues) - 1))
        else:
            self._current_index = -1
            self._reset_idle_preview_ui()
            self._update_inspector(None)
        self._commit_undo_point()
        self._mark_modified(True)
        if len(removed) == 1:
            rem = removed[0]
            self._status_label.setText(
                f"Deleted: {format_cue_ref(first_row, rem)} '{rem.name}' (Ctrl+Z per ripristinare)"
            )
        else:
            self._status_label.setText(
                f"Eliminate {len(removed)} cue selezionate (Ctrl+Z per ripristinare)"
            )
        self._auto_save()
        logger.info("Deleted %d cue(s)", len(removed))

    # ── Persistence & Crash Recovery ──────────────────────────────────

    def _auto_save(self) -> None:
        if self._cues or self._layer0_image:
            try:
                self._apply_inspector_to_cue()
                settings = {"layer0_image": self._layer0_image} if self._layer0_image else {}
                self._project_manager.autosave(
                    self._cues,
                    current_index=self._current_index,
                    active_project_path=self._current_project_path,
                    settings=settings,
                )
            except Exception as exc:
                logger.warning("[AUTOSAVE] Auto-save error: %s", exc)

    def _check_crash_recovery(self) -> None:
        if self._cues:
            return
        recovery = self._project_manager.check_crash_recovery()
        if not recovery:
            return

        saved_at = recovery.get("saved_at", "sconosciuto")
        cues_count = recovery.get("cues_count", len(recovery.get("cues", [])))
        reply = QMessageBox.question(
            self,
            "BlindCue — Ripristino Sessione (Crash Recovery)",
            f"È stata rilevata una sessione precedente interrotta o non salvata!\n\n"
            f"• Data ultimo autosave: {saved_at}\n"
            f"• Cue recuperabili: {cues_count}\n\n"
            f"Vuoi ripristinare il progetto da dove era stato interrotto?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )

        if reply == QMessageBox.StandardButton.Yes:
            self._cues.clear()
            for item in recovery.get("cues", []):
                try:
                    cue = Cue.from_dict(item)
                    cue.status = CueStatus.LOADED if os.path.isfile(cue.file_path) else CueStatus.OFFLINE
                    self._cues.append(cue)
                except Exception as exc:
                    logger.warning("[RECOVERY] Error recovering cue: %s", exc)
            self._current_index = recovery.get("current_cue_index", -1)
            self._current_project_path = recovery.get("active_project_path")

            rec_settings = recovery.get("settings", {})
            layer0 = rec_settings.get("layer0_image") if isinstance(rec_settings, dict) else None
            if layer0 and os.path.isfile(layer0):
                self.set_layer0_image(layer0)
            else:
                self._on_reset_layer0()

            self._refresh_cue_list(keep_selection=False)
            if 0 <= self._current_index < len(self._cues):
                self._cue_list.setCurrentRow(self._current_index)
            elif self._cues:
                self._cue_list.setCurrentRow(0)
            self._reset_undo_history()
            self._mark_modified(True)
            self._status_label.setText(f"Sessione ripristinata con successo ({len(self._cues)} cue)")
            logger.info("[RECOVERY] Restored %d cues from autosave", len(self._cues))
        else:
            self._project_manager.clear_autosave()
            logger.info("[RECOVERY] User discarded autosave recovery")

    def _confirm_save_if_modified(self, title: str, message: str) -> bool:
        """Prompt user to save dirty state; returns True to continue action or False to abort."""
        if not (self._is_modified and self._cues):
            return True
        ret = QMessageBox.question(
            self,
            title,
            message,
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if ret == QMessageBox.StandardButton.Save:
            return self._on_save_show()
        return ret != QMessageBox.StandardButton.Cancel

    @Slot()
    def _on_new_show(self) -> None:
        if not self._confirm_save_if_modified(
            "Nuovo Show",
            "Ci sono modifiche non salvate nel progetto corrente.\nVuoi salvarle prima di creare un nuovo show?",
        ):
            return

        self._cues.clear()
        self._current_index = -1
        self._current_project_path = None
        self._on_reset_layer0()
        self._refresh_cue_list()
        self._reset_idle_preview_ui()
        self._update_inspector(None)
        self._reset_undo_history()
        self._mark_modified(False)
        self._status_label.setText("Nuovo show creato")
        self._auto_save()

    @Slot()
    def _on_open_show(self) -> None:
        if not self._confirm_save_if_modified(
            "Apri Show",
            "Ci sono modifiche non salvate.\nVuoi salvare prima di aprire un altro show?",
        ):
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Apri Show BlindCue",
            "",
            "BlindCue Show (*.blindcue *.json);;Tutti i file (*)",
        )
        if not file_path:
            return

        try:
            cues, current_idx, settings = self._project_manager.load_project(file_path)
            self._cues = cues
            self._current_index = current_idx
            self._current_project_path = file_path

            layer0 = settings.get("layer0_image") if isinstance(settings, dict) else None
            if layer0 and os.path.isfile(layer0):
                self.set_layer0_image(layer0)
            else:
                self._on_reset_layer0()

            self._refresh_cue_list(keep_selection=False)
            if 0 <= self._current_index < len(self._cues):
                self._cue_list.setCurrentRow(self._current_index)
            elif self._cues:
                self._cue_list.setCurrentRow(0)
            self._reset_undo_history()
            self._mark_modified(False)
            self._status_label.setText(f"Caricato: {Path(file_path).name} ({len(cues)} cue)")
            self._auto_save()
        except Exception as exc:
            logger.error("[PROJECT] Error loading %s: %s", file_path, exc, exc_info=True)
            QMessageBox.critical(self, "Errore di Caricamento", f"Impossibile aprire il file:\n{exc}")

    @Slot()
    def _on_save_show(self) -> bool:
        if not self._current_project_path:
            return self._on_save_as_show()
        return self._do_save(self._current_project_path)

    @Slot()
    def _on_save_as_show(self) -> bool:
        suggested = self._current_project_path or "my_show.blindcue"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Salva Show Con Nome",
            suggested,
            "BlindCue Show (*.blindcue);;JSON File (*.json)",
        )
        if not file_path:
            return False
        if not file_path.endswith((".blindcue", ".json")):
            file_path += ".blindcue"
        self._current_project_path = file_path
        return self._do_save(file_path)

    def _do_save(self, file_path: str) -> bool:
        self._apply_inspector_to_cue()
        settings = {"layer0_image": self._layer0_image} if self._layer0_image else {}
        success = self._project_manager.save_project(
            file_path,
            self._cues,
            current_index=self._current_index,
            settings=settings,
        )
        if success:
            self._mark_modified(False)
            self._status_label.setText(f"Salvato con successo: {Path(file_path).name}")
            self._auto_save()
            return True
        QMessageBox.critical(self, "Errore Salvataggio", f"Impossibile salvare il file in:\n{file_path}")
        return False

    @Slot()
    def _on_quit(self) -> None:
        self.close()

    def closeEvent(self, event) -> None:  # noqa: N802
        if not self._force_closing and self._is_modified and self._cues:
            ret = QMessageBox.question(
                self,
                "Chiusura BlindCue",
                "Ci sono modifiche non salvate nel progetto.\nVuoi salvare prima di uscire?",
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Save,
            )
            if ret == QMessageBox.StandardButton.Save:
                if not self._on_save_show():
                    event.ignore()
                    return
            elif ret == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return

        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)
        self._project_manager.mark_clean_exit()
        self._output.force_close()
        event.accept()

    # ── Waveform Background Worker ────────────────────────────────────

    def _request_waveform(self, cue: Cue) -> None:
        if cue.media_type == MediaType.IMAGE:
            self._waveform.set_peaks(np.array([]))
            return
        try:
            analyzer = WaveformAnalyzer(cue.file_path, self._waveform.width())
            self._active_analyzers.add(analyzer)
            analyzer.signals.finished.connect(
                lambda path, peaks, a=analyzer: self._on_analyzer_ready(a, path, peaks)
            )
            analyzer.signals.error.connect(
                lambda path, msg, a=analyzer: self._on_analyzer_failed(a, path, msg)
            )
            self._thread_pool.start(analyzer)
        except Exception as exc:
            logger.error("Waveform request failed: %s", exc)

    def _on_analyzer_ready(self, analyzer, path: str, peaks: object) -> None:
        self._active_analyzers.discard(analyzer)
        cue = self._selected_cue()
        if cue and os.path.abspath(cue.file_path) == os.path.abspath(path):
            if isinstance(peaks, np.ndarray):
                self._waveform.set_peaks(peaks)

    def _on_analyzer_failed(self, analyzer, path: str, msg: str) -> None:
        self._active_analyzers.discard(analyzer)
        logger.warning("Waveform error for %s: %s", path, msg)
        self._waveform.set_peaks(np.array([]))

    # ── Preview Visual Pass-Throughs ──────────────────────────────────

    def show_preview_image(self, file_path: str, scale: float = 1.0, crop: Optional[dict] = None,
                           pos_x: float = 0.0, pos_y: float = 0.0, opacity: float = 1.0,
                           aspect_ratio: Optional[str] = None) -> None:
        self._preview_monitor.show_image(
            file_path, scale=scale, crop=crop, pos_x=pos_x, pos_y=pos_y,
            opacity=opacity, aspect_ratio=aspect_ratio,
        )

    def show_preview_video(self, scale: float = 1.0, crop: Optional[dict] = None,
                           pos_x: float = 0.0, pos_y: float = 0.0, opacity: float = 1.0,
                           aspect_ratio: Optional[str] = None) -> None:
        self._preview_monitor.show_video(
            scale=scale, crop=crop, pos_x=pos_x, pos_y=pos_y,
            opacity=opacity, aspect_ratio=aspect_ratio,
        )

    def update_preview_video_layout(self, scale: float = 1.0, crop: Optional[dict] = None,
                                    pos_x: float = 0.0, pos_y: float = 0.0, opacity: float = 1.0,
                                    aspect_ratio: Optional[str] = None) -> None:
        self._preview_monitor.update_video_layout(
            scale=scale, crop=crop, pos_x=pos_x, pos_y=pos_y,
            opacity=opacity, aspect_ratio=aspect_ratio,
        )

    def show_preview_audio(self) -> None:
        self._preview_monitor.show_audio()

    def set_preview_audio_playing(self, is_playing: bool) -> None:
        self._preview_monitor.set_audio_playing(is_playing)

    def clear_preview(self) -> None:
        self._preview_monitor.clear_media()

    def get_preview_video_sink(self) -> QVideoSink:
        return self._preview_monitor.get_video_sink()

    def get_preview_video_widget(self) -> Any:
        return self._preview_monitor.get_video_sink()

    def get_preview_wid(self) -> int:
        return 0
