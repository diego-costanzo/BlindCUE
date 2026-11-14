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
from PySide6.QtCore import QEvent, QSettings, Qt, QThreadPool, QTimer, Signal, Slot
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
    scan_file_loudness,
)
from engine.earcon import EarconManager
from engine.envelope import (
    evaluate_cue_level,
    merge_section_at,
    normalize_sections,
    split_sections_at,
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
)
from models.project_manager import ProjectManager
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
    THEMES,
    VIDEO_EXT,
    get_active_theme,
    set_active_theme,
)
from ui.undo_manager import UndoManager
from ui.waveform_widget import WaveformPanel, WaveformWidget

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
    "WaveformPanel",
    "WaveformWidget",
]

_MEDIA_ICONS = {
    MediaType.VIDEO: "🎬",
    MediaType.AUDIO: "🎵",
    MediaType.IMAGE: "🖼",
}

_DEFAULT_TOP_RATIOS: tuple[float, float, float] = (0.25, 0.45, 0.30)


class MainWindow(QMainWindow):
    """Director / Control Panel."""

    cue_fired = Signal(object)                     # emits Cue
    cue_preview_requested = Signal(object)         # emits Cue to load in preview
    layer_clear_requested = Signal(int)            # emits layer (1, 2, or 3)
    blackout_requested = Signal()                        # emits when blackout triggered
    preview_mute_toggled = Signal(bool)                  # emits is_muted (True or False)
    preview_in_out_changed = Signal(float, object, bool) # emits in_sec, out_sec, seek_to_start
    preview_seek_requested = Signal(float)               # emits scrubbed playhead position in seconds
    live_volume_changed = Signal(int)                    # emits volume 0-100
    live_automation_updated = Signal(object)             # emits edited Cue to refresh active players
    section_jump_requested = Signal(object, int, bool)   # emits (Cue, section_idx, is_live_jump)
    section_break_loop_requested = Signal(object, bool)  # emits (Cue, is_live_jump)
    layer_play_pause_requested = Signal(int)             # emits live layer (1..3) pause/resume toggle
    layer_seek_requested = Signal(int, float)            # emits live layer (1..3) and target position in seconds
    panic_requested = Signal()                           # emits instant 0ms Panic stop all
    pause_all_toggled = Signal()                         # emits global Show Pause/Resume toggle

    def __init__(self, output_window: OutputWindow,
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._output = output_window
        self._cues: list[Cue] = []
        self._layer_conflicts: dict[int, LayerConflict] = {}
        self._jam_mode_active: bool = False
        self._current_index: int = -1
        self._thread_pool = QThreadPool.globalInstance()
        self._test_player = None
        self._device_mgr = None
        self._active_analyzers: set = set()
        self._active_test_duration: float = 0.0
        self._active_section_idx: int = -1
        self._img_previz_elapsed: float = 0.0
        self._img_previz_timer = QTimer(self)
        self._img_previz_timer.setInterval(33)
        self._img_previz_timer.timeout.connect(self._on_img_previz_tick)

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
        self._known_file_durations: dict[str, float] = {}
        self._live_phase_tags: dict[int, str] = {}
        self._live_mode: bool = False
        self._panels_locked: bool = True
        self._top_ratios: tuple[float, float, float] = _DEFAULT_TOP_RATIOS
        self._applying_splitter_layout: bool = False

        self._undo = UndoManager(self)
        self._undo.commit_requested.connect(self._commit_undo_point)
        self._undo.history_changed.connect(self._on_undo_history_changed)

        self._earcon_mgr = EarconManager()
        settings = QSettings("BlindCue", "BlindCue")
        self._earcon_mgr.enabled = bool(settings.value("ui/earcons_enabled", False, type=bool))

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

        # Load persisted theme or default to Obsidian Slate
        settings = QSettings("BlindCue", "BlindCue")
        saved_theme = str(settings.value("ui/theme", "obsidian_slate"))
        self.apply_theme(saved_theme, save_pref=False)

        if DEFAULT_LOGO_PATH.is_file():
            self.setWindowIcon(QIcon(str(DEFAULT_LOGO_PATH)))

        self.bind_to_primary_screen()

    def apply_theme(self, theme_id: str, save_pref: bool = True) -> None:
        """Apply visual theme globally across application, windows, dialogs and custom canvas views."""
        if theme_id not in THEMES:
            theme_id = "obsidian_slate"

        stylesheet = set_active_theme(theme_id)
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(stylesheet)
        self.setStyleSheet(stylesheet)

        if save_pref:
            settings = QSettings("BlindCue", "BlindCue")
            settings.setValue("ui/theme", theme_id)

        if hasattr(self, "_theme_actions") and theme_id in self._theme_actions:
            self._theme_actions[theme_id].setChecked(True)

        # Repaint custom-painted components
        self._update_go_button_style()
        if hasattr(self, "_cue_list") and self._cue_list is not None:
            self._cue_list.viewport().update()
        if hasattr(self, "_cue_list_panel") and self._cue_list_panel is not None:
            if hasattr(self._cue_list_panel, "refresh_theme_styles"):
                self._cue_list_panel.refresh_theme_styles()
            self._cue_list_panel.update()
        if hasattr(self, "_live_show_panel") and self._live_show_panel is not None:
            if hasattr(self._live_show_panel, "refresh_theme_styles"):
                self._live_show_panel.refresh_theme_styles()
            self._live_show_panel.update()
            if hasattr(self._live_show_panel, "live_table"):
                self._live_show_panel.live_table.viewport().update()
        if hasattr(self, "_waveform_panel") and self._waveform_panel is not None:
            self._waveform_panel.update()
        if hasattr(self, "_live_status_panel") and self._live_status_panel is not None:
            if hasattr(self._live_status_panel, "refresh_theme_styles"):
                self._live_status_panel.refresh_theme_styles()
            self._live_status_panel.update()
        if hasattr(self, "_inspector_panel") and self._inspector_panel is not None:
            if hasattr(self._inspector_panel, "refresh_theme_styles"):
                self._inspector_panel.refresh_theme_styles()
            self._inspector_panel.update()

        # Update Status Bar widgets
        t = get_active_theme()
        if hasattr(self, "_lbl_hw_info") and self._lbl_hw_info is not None:
            if t.is_monochrome:
                self._lbl_hw_info.setStyleSheet("color: #ffffff; font-size: 11px; padding-left: 6px;")
            elif t.theme_id == "warm_amber_studio":
                self._lbl_hw_info.setStyleSheet("color: #fbbf24; font-size: 11px; padding-left: 6px;")
            else:
                self._lbl_hw_info.setStyleSheet("color: #00bcd4; font-size: 11px; padding-left: 6px;")

        if hasattr(self, "_btn_jam_mode") and self._btn_jam_mode is not None:
            if t.is_monochrome:
                self._btn_jam_mode.set_palette_colors(
                    color_idle="#1a1b1f",
                    border_idle="#3f404d",
                    text_color_idle="#d4d4d8",
                    color_active="#26272e",
                    border_active="#ffffff",
                    text_color_active="#ffffff",
                    fill_color="#ffffff",
                )
            elif t.theme_id == "warm_amber_studio":
                self._btn_jam_mode.set_palette_colors(
                    color_idle="#1e1916",
                    border_idle="#3d322a",
                    text_color_idle="#bfa89b",
                    color_active="#2b2420",
                    border_active="#f59e0b",
                    text_color_active="#fbbf24",
                    fill_color="#f59e0b",
                )
            else:
                self._btn_jam_mode.set_palette_colors(
                    color_idle="#16202e",
                    border_idle="#2d3e56",
                    text_color_idle="#94a3b8",
                    color_active="#064e3b",
                    border_active="#10b981",
                    text_color_active="#34d399",
                    fill_color="#10b981",
                )

    def _update_go_button_style(self) -> None:
        """Update Main GO button stylesheet to honor the active visual theme."""
        if not hasattr(self, "_btn_go") or self._btn_go is None:
            return
        t = get_active_theme()
        if t.is_monochrome:
            self._btn_go.setStyleSheet(f"""
                QPushButton {{
                    background-color: {t.go};
                    color: #0c1017;
                    border: 2px solid #ffffff;
                    border-radius: 6px;
                    font-size: 18px;
                    font-weight: bold;
                }}
                QPushButton:hover {{ background-color: {t.accent_hover}; }}
                QPushButton:pressed {{ background-color: {t.accent_muted}; }}
            """)
        elif t.theme_id == "warm_amber_studio":
            self._btn_go.setStyleSheet(f"""
                QPushButton {{
                    background-color: {t.go};
                    color: #151210;
                    border: 1px solid #fbbf24;
                    border-radius: 6px;
                    font-size: 18px;
                    font-weight: bold;
                }}
                QPushButton:hover {{ background-color: {t.accent_hover}; }}
                QPushButton:pressed {{ background-color: {t.accent_muted}; }}
            """)
        else:
            self._btn_go.setStyleSheet(f"""
                QPushButton {{
                    background-color: {t.go};
                    color: #000;
                    border: none;
                    border-radius: 6px;
                    font-size: 18px;
                    font-weight: bold;
                }}
                QPushButton:hover {{ background-color: #69f0ae; }}
                QPushButton:pressed {{ background-color: #00c853; }}
            """)

    def _set_earcons_enabled(self, enabled: bool) -> None:
        """Enable or disable auditory accessibility guidance chimes and persist setting."""
        if hasattr(self, "_earcon_mgr"):
            self._earcon_mgr.enabled = bool(enabled)
            settings = QSettings("BlindCue", "BlindCue")
            settings.setValue("ui/earcons_enabled", bool(enabled))
            if enabled:
                self._earcon_mgr.play_go()

    def bind_to_primary_screen(self, screen=None) -> None:
        """Bind MainWindow and its native handle to the primary monitor and fit inside it."""
        target = screen or QApplication.primaryScreen()
        if target is None:
            return
        avail = target.availableGeometry()
        if avail.width() > 0 and avail.height() > 0:
            self.setMinimumSize(min(1240, avail.width()), min(740, avail.height()))
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
        QShortcut(QKeySequence(Qt.Key.Key_I), self, lambda: self._on_snap_shortcut(True))
        QShortcut(QKeySequence(Qt.Key.Key_O), self, lambda: self._on_snap_shortcut(False))
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, self._on_escape_pressed)
        QShortcut(QKeySequence(Qt.Key.Key_F5), self, self.toggle_live_mode)
        QShortcut(QKeySequence("Ctrl+L"), self, self.toggle_live_mode)
        QShortcut(QKeySequence("Ctrl+G"), self, self._on_add_group)
        QShortcut(QKeySequence("Ctrl+Shift+G"), self, self._on_ctrl_shift_g)

    def _is_text_input_focused(self) -> bool:
        focus_w = QApplication.focusWidget()
        if isinstance(focus_w, (QLineEdit, QAbstractSpinBox, QComboBox)):
            return True
        return hasattr(self, "_cue_list") and self._cue_list.state() == QAbstractItemView.State.EditingState

    @Slot()
    def _on_escape_pressed(self) -> None:
        if hasattr(self, "_cue_list") and self._cue_list.state() == QAbstractItemView.State.EditingState:
            return
        if self._live_mode:
            self._on_panic()
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
                    self._sync_timeline_for_cue(cue)
                    self.live_automation_updated.emit(cue)
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
        if self._live_mode:
            return
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
        if self._live_mode:
            return
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
        show_menu.addSeparator()
        self._act_jam_mode = QAction("🎚 Modalità &Jam / Contest (Auto-Gain EBU R128)", self, checkable=True)
        self._act_jam_mode.setToolTip("Abilita il livellamento automatico EBU R128 (-16 LUFS) per contest, jam session e file non calibrati.")
        self._act_jam_mode.toggled.connect(self._set_jam_mode)
        show_menu.addAction(self._act_jam_mode)
        show_menu.addAction(
            QAction("⚙️ &Dispositivi & Hardware (Audio / Video / Profilo)…", self, triggered=self.open_device_settings_dialog)
        )

        view_menu = mb.addMenu("&View")
        self._act_live_mode = QAction("🎭 Modalità &LIVE (Show Mode)", self, checkable=True)
        self._act_live_mode.setShortcut(QKeySequence(Qt.Key.Key_F5))
        self._act_live_mode.toggled.connect(self.set_live_mode)
        view_menu.addAction(self._act_live_mode)
        view_menu.addSeparator()

        # Theme Submenu
        theme_menu = view_menu.addMenu("🎨 &Tema Interfaccia")
        self._theme_action_group = QActionGroup(self)
        self._theme_action_group.setExclusive(True)
        self._theme_actions: dict[str, QAction] = {}
        for tid, t_def in THEMES.items():
            if tid != t_def.theme_id:
                continue
            act = QAction(t_def.name, self, checkable=True)
            act.setToolTip(t_def.description)
            act.triggered.connect(lambda checked=False, theme_key=tid: self.apply_theme(theme_key))
            self._theme_action_group.addAction(act)
            theme_menu.addAction(act)
            self._theme_actions[tid] = act

        active_tid = get_active_theme().theme_id
        if active_tid in self._theme_actions:
            self._theme_actions[active_tid].setChecked(True)

        self._act_earcons = QAction("🔔 &Segnali Acustici Operatore (Earcons)", self, checkable=True)
        self._act_earcons.setToolTip(
            "Accessibilità Regia: Emette un discreto segnale sonoro di conferma ad ogni GO, STOP e PAUSA.\n"
            "Utile per operatori non vedenti o per chi guarda il palco senza guardare il monitor."
        )
        self._act_earcons.setChecked(self._earcon_mgr.enabled)
        self._act_earcons.toggled.connect(self._set_earcons_enabled)
        view_menu.addAction(self._act_earcons)

        view_menu.addSeparator()
        self._act_lock_layout = QAction("🔒 &Blocca Larghezza Pannelli", self, checkable=True)
        self._act_lock_layout.setChecked(True)
        self._act_lock_layout.toggled.connect(lambda checked: self._set_panels_locked(checked))
        view_menu.addAction(self._act_lock_layout)
        view_menu.addAction(
            QAction("↺ &Ripristina Larghezze Standard", self, triggered=self._reset_standard_layout)
        )

        help_menu = mb.addMenu("&Help")
        help_menu.addAction(
            QAction("&Info Hardware & Accelerazione…", self, triggered=self._show_hw_info)
        )
        help_menu.addSeparator()
        help_menu.addAction(
            QAction("&About BlindCue", self, triggered=lambda: show_about_dialog(self))
        )

    def _build_ui(self) -> None:
        self._central_stack = QStackedWidget()
        self.setCentralWidget(self._central_stack)

        self._design_page = QWidget()
        root_layout = QVBoxLayout(self._design_page)
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
        self._cue_list.color_selected.connect(self._set_cue_color)
        self._cue_list_panel.add_media_requested.connect(self._on_add_media)
        self._cue_list_panel.add_group_requested.connect(self._on_add_group)
        self._cue_list_panel.ungroup_requested.connect(self._ungroup_selected)
        self._cue_list_panel.extract_child_requested.connect(self._extract_selected_from_group)
        self._cue_list.open_timeline_requested.connect(self._on_open_group_timeline)
        self._cue_list.group_collapse_toggled.connect(self._toggle_group_collapsed)
        self._cue_list_panel.move_up_requested.connect(self._on_move_up)
        self._cue_list_panel.move_down_requested.connect(self._on_move_down)
        self._cue_list_panel.delete_requested.connect(self._on_delete_cue)
        self._cue_list_panel.go_live_mode_requested.connect(lambda: self.set_live_mode(True))
        self._cue_list_panel.follow_mode_selected.connect(self._set_follow_mode)
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
        self._preview_monitor.video_frame_changed.connect(self._on_preview_video_frame_for_mirror)
        center_layout.addWidget(self._preview_panel, stretch=1)

        self._btn_go = QPushButton("GO (Next Cue) — [ SPAZIO ]")
        self._btn_go.setMinimumHeight(48)
        self._btn_go.setMaximumHeight(54)
        self._btn_go.setFont(QFont("sans-serif", 18, QFont.Weight.Bold))
        self._update_go_button_style()
        self._btn_go.clicked.connect(self._on_go)
        center_layout.addWidget(self._btn_go, stretch=0)
        top_splitter.addWidget(center_panel)

        # Right: Cue Inspector
        self._inspector = CueInspectorPanel()
        self._inspector.value_changed.connect(self._on_inspector_value_changed)
        self._inspector.batch_field_edited.connect(self._on_batch_field_edited)
        self._inspector.layer_selected.connect(self._set_layer)
        self._inspector.color_selected.connect(self._set_cue_color)
        self._inspector.follow_mode_selected.connect(self._set_follow_mode)
        self._inspector.in_out_reset_requested.connect(self._on_reset_in_out)
        self._inspector.group_mode_selected.connect(self._set_group_mode)
        self._inspector.group_collapse_toggled.connect(self._toggle_group_collapse_from_inspector)
        self._inspector.ungroup_requested.connect(self._ungroup_selected)
        self._inspector.remove_child_requested.connect(self._on_remove_child_from_group)
        self._inspector.extract_child_requested.connect(self._extract_selected_from_group)
        self._inspector.open_group_timeline_requested.connect(self._on_open_group_timeline)
        self._inspector.scan_loudness_requested.connect(self._on_scan_loudness_requested)
        self._inspector.normalize_cue_toggled.connect(self._on_normalize_cue_toggled)
        self._inspector.optimize_dynamics_requested.connect(self._on_optimize_dynamics_requested)
        self._inspector.restore_original_requested.connect(self._on_restore_original_requested)
        self._bind_inspector_aliases()
        top_splitter.addWidget(self._inspector)

        top_splitter.setChildrenCollapsible(False)
        top_splitter.setStretchFactor(0, 25)
        top_splitter.setStretchFactor(1, 45)
        top_splitter.setStretchFactor(2, 30)
        top_splitter.setSizes([350, 630, 420])
        top_splitter.splitterMoved.connect(self._on_top_splitter_moved)
        root_layout.addWidget(top_splitter, stretch=7)

        # Bottom splitter: Waveform | Live Output Status | Drop Zone
        bottom_splitter = QSplitter(Qt.Orientation.Horizontal)
        bottom_splitter.setChildrenCollapsible(False)
        self._bottom_splitter = bottom_splitter

        self._waveform_panel = WaveformPanel()
        self._waveform = self._waveform_panel.waveform
        self._waveform_panel.in_changed.connect(self._on_waveform_in_changed)
        self._waveform_panel.out_changed.connect(self._on_waveform_out_changed)
        self._waveform_panel.seek_requested.connect(self._on_waveform_seek_requested)
        self._waveform_panel.snap_in_requested.connect(self._on_snap_in_to_playhead)
        self._waveform_panel.snap_out_requested.connect(self._on_snap_out_to_playhead)
        self._waveform_panel.reset_in_out_requested.connect(self._on_reset_in_out)
        self._waveform_panel.fade_in_changed.connect(self._on_waveform_fade_in_changed)
        self._waveform_panel.fade_out_changed.connect(self._on_waveform_fade_out_changed)
        self._waveform_panel.fade_curve_changed.connect(self._on_waveform_fade_curve_changed)
        self._waveform_panel.envelope_mode_changed.connect(self._on_envelope_mode_changed)
        self._waveform_panel.envelope_points_changed.connect(self._on_envelope_points_changed)
        self._waveform_panel.reset_envelope_points_requested.connect(self._on_reset_envelope_points)
        self._waveform_panel.image_horizon_changed.connect(self._on_image_horizon_changed)
        self._waveform_panel.split_section_requested.connect(self._on_split_section)
        self._waveform_panel.break_loop_requested.connect(self._on_break_section_loop)
        self._waveform_panel.reset_sections_requested.connect(self._on_reset_sections)
        self._waveform_panel.section_jump_requested.connect(self._on_section_jump_clicked)
        self._waveform_panel.section_mode_changed.connect(self._on_section_mode_changed)
        self._waveform_panel.section_remove_requested.connect(self._on_remove_section)
        self._waveform_panel.sections_changed.connect(self._on_sections_resized)
        bottom_splitter.addWidget(self._waveform_panel)

        self._live_status = LiveStatusPanel()
        self._lbl_tappo_info = self._live_status.lbl_tappo_info
        self._live_status.clear_layer_clicked.connect(self._on_clear_live_layer)
        self._live_status.blackout_clicked.connect(self._on_blackout)
        self._live_status.choose_layer0_clicked.connect(self._on_choose_layer0)
        self._live_status.reset_layer0_clicked.connect(self._on_reset_layer0)
        self._live_status.layer_play_pause_clicked.connect(self.layer_play_pause_requested.emit)
        self._live_status.layer_seek_requested.connect(self.layer_seek_requested.emit)
        bottom_splitter.addWidget(self._live_status)

        drop_group = QGroupBox("Caricamento Rapido (Drag && Drop)")
        drop_layout = QVBoxLayout(drop_group)
        self._drop_zone = DropZone()
        self._drop_zone.file_dropped.connect(self._on_file_dropped)
        drop_layout.addWidget(self._drop_zone)
        bottom_splitter.addWidget(drop_group)

        bottom_splitter.setSizes([460, 320, 220])
        root_layout.addWidget(bottom_splitter, stretch=2)

        # Dedicated distraction-free LIVE Show Mode page
        self._live_show_panel = LiveShowPanel()
        self._live_show_panel.exit_live_mode_requested.connect(lambda: self.set_live_mode(False))
        self._live_show_panel.go_requested.connect(self._on_go)
        self._live_show_panel.cue_row_clicked.connect(lambda r: self._cue_list.setCurrentRow(r))
        self._live_show_panel.cue_row_double_clicked.connect(self._on_live_row_double_clicked)
        self._live_show_panel.group_collapse_toggled.connect(self._toggle_group_collapsed)
        self._live_show_panel.pause_all_toggled.connect(self.pause_all_toggled.emit)
        self._live_show_panel.panic_requested.connect(self._on_panic)
        self._live_show_panel.break_loop_requested.connect(self._on_break_section_loop)
        self._live_show_panel.live_status.clear_layer_clicked.connect(self._on_clear_live_layer)
        self._live_show_panel.live_status.layer_play_pause_clicked.connect(self.layer_play_pause_requested.emit)
        self._live_show_panel.live_status.layer_seek_requested.connect(self.layer_seek_requested.emit)

        self._status_panels: list[LiveStatusPanel] = [
            self._live_status,
            self._live_show_panel.live_status,
        ]

        self._central_stack.addWidget(self._design_page)
        self._central_stack.addWidget(self._live_show_panel)
        self._central_stack.setCurrentIndex(0)

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

        self._btn_device_settings = QPushButton("⚙ Dispositivi · Uscite")
        self._btn_device_settings.setFixedHeight(22)
        self._btn_device_settings.setMinimumWidth(152)
        self._btn_device_settings.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_device_settings.setToolTip(
            "Configura Master Audio Sala, Cuffia Regia (PFL), Schermo Live e Profilo Hardware (Eco/Pro)."
        )
        self._btn_device_settings.setAccessibleName("Dispositivi e Uscite Hardware")
        self._btn_device_settings.setAccessibleDescription("Apre il pannello di configurazione delle uscite audio sala, monitor cuffia, schermo video live e profili prestazionali.")
        self._btn_device_settings.clicked.connect(self.open_device_settings_dialog)
        sb.addWidget(self._btn_device_settings)

        self._btn_lock_layout = QPushButton("🔒 Layout: Bloccato")
        self._btn_lock_layout.setCheckable(True)
        self._btn_lock_layout.setChecked(True)
        self._btn_lock_layout.setFixedHeight(22)
        self._btn_lock_layout.setMinimumWidth(142)
        self._btn_lock_layout.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_lock_layout.setToolTip(
            "Blocca o sblocca le larghezze dei 3 pannelli principali (Scaletta, Anteprima, Ispettore).\n"
            "Di default è bloccato per evitare spostamenti accidentali; clicca per ridimensionare a piacere."
        )
        self._btn_lock_layout.setAccessibleName("Blocca Larghezza Pannelli")
        self._btn_lock_layout.setAccessibleDescription("Attiva o disattiva il blocco delle larghezze dei pannelli di regia per prevenire spostamenti accidentali.")
        self._btn_lock_layout.toggled.connect(lambda checked: self._set_panels_locked(checked))
        sb.addWidget(self._btn_lock_layout)

        self._btn_jam_mode = HoldProgressButton(
            text_idle="🎚 Jam: OFF (Tieni 5s)",
            text_active="🎚 Jam Mode: ATTIVO",
            hold_ms=5000,
            deactivate_hold_ms=1500,
            is_toggle=True,
            initial_state=False,
            color_idle="#16202e",
            border_idle="#2d3e56",
            text_color_idle="#94a3b8",
            color_active="#064e3b",
            border_active="#10b981",
            text_color_active="#34d399",
            fill_color="#10b981",
        )
        self._btn_jam_mode.setFixedHeight(22)
        self._btn_jam_mode.setMinimumWidth(160)
        self._btn_jam_mode.setFont(QFont("sans-serif", 10, QFont.Weight.Bold))
        self._btn_jam_mode.setToolTip(
            "Modalità Jam / Contest (Default: OFF).\n"
            "PROTEZIONE REGIA: Tieni premuto per 5 secondi per attivare.\n"
            "Quando attiva, applica automaticamente il livellamento sonoro EBU R128 (-16 LUFS)\n"
            "su tutti i media per evitare salti improvvisi di volume durante contest o jam session.\n"
            "Per disattivare: tieni premuto 1.5 secondi."
        )
        self._btn_jam_mode.setAccessibleName("Modalità Jam e Contest Livellamento Audio")
        self._btn_jam_mode.setAccessibleDescription("Attiva o disattiva il livellamento automatico EBU R128 a -16 LUFS. Richiede una pressione continua di 5 secondi per attivare.")
        self._btn_jam_mode.toggled_state.connect(self._set_jam_mode)
        sb.addWidget(self._btn_jam_mode)

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
        parts = []
        if cue.cue_id in self._layer_conflicts:
            parts.append(f"⚠️ ATTENZIONE: {self._layer_conflicts[cue.cue_id].reason}\n")
        parts.append(f"Posizione: #{row + 1}")
        if cue.q_label:
            parts.append(f"Q (Copione): {cue.q_label}")
        parts.append(f"Nome: {cue.name}")
        link_lbl = {
            FollowMode.MANUAL.value: "Blocco manuale",
            FollowMode.AUTO_FOLLOW.value: "Auto-GO a fine cue",
            FollowMode.SIMULTANEOUS.value: "Simultanea con successiva",
        }.get(cue.follow_mode, cue.follow_mode)
        timing_bits = []
        if cue.pre_delay > 0:
            timing_bits.append(f"Pre +{cue.pre_delay:.1f}s")
        if cue.media_type == MediaType.IMAGE:
            timing_bits.append(f"Durata {'∞' if cue.hold_time <= 0 else f'{cue.hold_time:.1f}s'}")
        if cue.post_delay > 0:
            timing_bits.append(f"Post +{cue.post_delay:.1f}s")
        timing_bits.append(link_lbl)
        parts.append("Tempi: " + " | ".join(timing_bits))
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
        self._img_previz_timer.stop()
        self._active_test_duration = 0.0
        self._active_section_idx = -1
        self._waveform.set_peaks(np.array([]))
        self._waveform.set_media_context(None)
        self._waveform.set_in_out_seconds(0.0, None, 0.0)
        self._waveform.set_sections([], -1)
        self._waveform_panel.section_bar.set_sections([], 0.0, -1)
        self._waveform_panel.sync_controls_for_cue(media_type=None)
        self.set_waveform_playhead_seconds(None, 0.0)
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

        is_group = (cue.media_type == MediaType.GROUP)
        child_count = 0
        if is_group:
            child_count = sum(1 for c in self._cues if c.parent_id == cue.cue_id)

        is_last_child = False
        if cue.parent_id is not None:
            siblings = [c for c in self._cues if c.parent_id == cue.parent_id]
            if siblings and siblings[-1].cue_id == cue.cue_id:
                is_last_child = True

        item_num = self._cue_list.item(row, 0)
        if item_num is None:
            item_num = QTableWidgetItem()
            item_num.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_num.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            self._cue_list.setItem(row, 0, item_num)
        item_num.setText(f"#{row + 1}")
        item_num.setForeground(QColor(colour if status_txt in ("LIVE", "STANDBY") else CLR_TEXT_MUTED))
        item_num.setToolTip(tooltip)
        item_num.setData(ROLE_IS_GROUP, is_group)
        item_num.setData(ROLE_GROUP_COLLAPSED, getattr(cue, "collapsed", False))

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
        cue_color = getattr(cue, "color", "") or ""
        prev_color = (getattr(self._cues[row - 1], "color", "") or "") if row > 0 else ""
        incoming_link = self._cues[row - 1].follow_mode if row > 0 else ""

        conflict = self._layer_conflicts.get(cue.cue_id)
        conflict_txt = conflict.reason if conflict else ""

        item_name.setData(ROLE_MEDIA_TYPE, cue.media_type.value)
        item_name.setData(ROLE_LAYER, cue.layer)
        item_name.setData(ROLE_LAYER_CONFLICT, conflict_txt)
        item_name.setData(ROLE_HAS_NOTES, bool(cue.notes))
        item_name.setData(ROLE_FOLLOW_MODE, cue.follow_mode)
        item_name.setData(ROLE_TIMING_BADGE, "⏱" if (cue.pre_delay > 0 or cue.post_delay > 0) else "")
        item_name.setData(ROLE_STATUS_TXT, status_txt)
        item_name.setData(ROLE_STATUS_CLR, colour)
        item_name.setData(ROLE_PARENT_ID, cue.parent_id)
        item_name.setData(ROLE_IS_GROUP, is_group)
        item_name.setData(ROLE_GROUP_MODE, getattr(cue, "group_mode", "STEP"))
        item_name.setData(ROLE_GROUP_COLLAPSED, getattr(cue, "collapsed", False))
        item_name.setData(ROLE_CHILD_COUNT, child_count)
        item_name.setData(ROLE_IS_LAST_CHILD, is_last_child)
        item_name.setData(ROLE_TIMELINE_COMPOSED, bool(getattr(cue, "timeline_composed", False)))
        item_name.setToolTip(tooltip)

        for cell in (item_num, item_q, item_name):
            cell.setData(ROLE_CUE_COLOR, cue_color)
            cell.setData(ROLE_PREV_COLOR, prev_color)
            cell.setData(ROLE_FOLLOW_MODE, cue.follow_mode)
            cell.setData(ROLE_INCOMING_LINK, incoming_link)

        # Set row visibility based on parent collapse state
        if cue.parent_id is not None:
            parent_cue = next((c for c in self._cues if c.cue_id == cue.parent_id), None)
            is_hidden = bool(parent_cue and parent_cue.collapsed)
            self._cue_list.setRowHidden(row, is_hidden)
            if hasattr(self, "_live_show_panel") and self._live_show_panel is not None:
                self._live_show_panel.live_table.setRowHidden(row, is_hidden)
        else:
            self._cue_list.setRowHidden(row, False)
            if hasattr(self, "_live_show_panel") and self._live_show_panel is not None:
                self._live_show_panel.live_table.setRowHidden(row, False)

    def _sync_inspector_header_and_text(self, row: int, cue: Cue) -> None:
        if 0 <= row < len(self._cues) and row == self._cue_list.currentRow():
            self._inspector.sync_header_and_text(row, cue)
            self._update_cue_readouts(row, cue)

    def _for_each_status_panel(self):
        return getattr(self, "_status_panels", [self._live_status])

    def is_live_mode(self) -> bool:
        return self._live_mode

    @Slot(bool)
    def set_live_mode(self, enabled: bool) -> None:
        enabled = bool(enabled)
        if self._live_mode == enabled:
            return
        self._live_mode = enabled
        if hasattr(self, "_act_live_mode"):
            self._act_live_mode.blockSignals(True)
            self._act_live_mode.setChecked(enabled)
            self._act_live_mode.blockSignals(False)
        self._central_stack.setCurrentIndex(1 if enabled else 0)
        if enabled:
            prof = self._device_mgr.get_effective_profile() if self._device_mgr else "auto"
            ShowRuntimeGuard.on_live_mode_enter(prof)
            self._sync_live_view()
            self._status_label.setText("MODALITÀ LIVE ATTIVA — Interfaccia semplificata per la regia [ESC = PANIC]")
        else:
            ShowRuntimeGuard.on_live_mode_exit()
            QTimer.singleShot(0, self._apply_top_splitter_ratios)
            self._status_label.setText("MODALITÀ PROGETTO — Modifica cue e anteprima riabilitate")

    @Slot()
    def toggle_live_mode(self) -> None:
        self.set_live_mode(not self._live_mode)

    def set_device_manager(self, mgr: Any) -> None:
        """Register the central DeviceManager and wire its signals to the UI."""
        self._device_mgr = mgr
        if mgr is not None:
            mgr.profile_changed.connect(self._update_hardware_status_bar)
            mgr.master_device_changed.connect(self._update_hardware_status_bar)
            mgr.target_screen_changed.connect(self._update_hardware_status_bar)
            self._update_hardware_status_bar()

    def open_device_settings_dialog(self) -> None:
        """Open the Device & Hardware configuration dialog."""
        if self._device_mgr is None:
            return
        from ui.device_settings_dialog import DeviceSettingsDialog
        dlg = DeviceSettingsDialog(self._device_mgr, self)
        dlg.exec()
        self._update_hardware_status_bar()

    def _update_hardware_status_bar(self, *args: Any) -> None:
        """Refresh the hardware and device brief in the status bar."""
        if hasattr(self, "_lbl_hw_info"):
            pref = self._device_mgr.get_profile_preference() if self._device_mgr else "auto"
            self._lbl_hw_info.setText(detect_hardware_brief(pref))

    def _show_hw_info(self) -> None:
        """Open detailed hardware information dialog."""
        pref = self._device_mgr.get_profile_preference() if self._device_mgr else "auto"
        show_hardware_info_dialog(self, pref)

    def set_known_duration(self, file_path: str, dur_sec: float) -> None:
        if file_path and dur_sec > 0:
            self._known_file_durations[file_path] = dur_sec
            self._sync_live_view()

    def set_cue_phase_badge(self, cue_id: int, badge_text: str) -> None:
        prev = self._live_phase_tags.get(cue_id, "")
        if badge_text:
            self._live_phase_tags[cue_id] = badge_text
        else:
            self._live_phase_tags.pop(cue_id, None)
        if prev != badge_text:
            self._sync_live_view()

    def set_global_paused(self, paused: bool) -> None:
        if hasattr(self, "_earcon_mgr"):
            self._earcon_mgr.play_pause()
        if hasattr(self, "_live_show_panel"):
            self._live_show_panel.set_global_paused(paused)

    def _sync_live_view(self) -> None:
        if not hasattr(self, "_live_show_panel"):
            return
        standby_row, _ = self._anchor_row_and_cue()
        if standby_row < 0 and self._cues:
            standby_row = 0
        has_live_inf_sec = any(
            c.status == CueStatus.LIVE and any(s.loops == 0 and not s.skip for s in c.sections)
            for c in self._cues
        )
        self._live_show_panel.sync_cues(
            self._cues,
            standby_row,
            self._known_file_durations,
            self._live_phase_tags,
            show_break_loop=has_live_inf_sec,
            layer_conflicts=self._layer_conflicts,
        )

    def _update_live_layer_label(self, cue: Cue, preserve_timing: bool = False) -> None:
        dur = 0.0
        if cue.media_type == MediaType.IMAGE and cue.hold_time > 0:
            dur = cue.hold_time
        elif self._selected_cue() is cue and self._active_test_duration > 0:
            dur = self._active_test_duration
        elif cue.file_path in self._known_file_durations:
            dur = self._known_file_durations[cue.file_path]
        for sp in self._for_each_status_panel():
            sp.set_layer_live(cue, duration_sec=dur, preserve_timing=preserve_timing)

    def update_live_layer_phase(self, layer: int, cue: Cue, phase: str, elapsed: float, total: float) -> None:
        for sp in self._for_each_status_panel():
            sp.set_layer_phase_progress(layer, cue, phase, elapsed, total)

    def update_live_layer_progress(
        self,
        layer: int,
        pos_sec: float,
        end_sec: Optional[float] = None,
        start_sec: Optional[float] = None,
        is_looping_inf: Optional[bool] = None,
    ) -> None:
        for sp in self._for_each_status_panel():
            sp.set_layer_progress(
                layer,
                pos_sec,
                start_sec=start_sec,
                end_sec=end_sec,
                is_looping_inf=is_looping_inf,
            )

    def set_live_layer_paused(self, layer: int, paused: bool) -> None:
        for sp in self._for_each_status_panel():
            sp.set_layer_paused(layer, paused)

    def _reset_live_label(self, layer: int) -> None:
        for sp in self._for_each_status_panel():
            sp.reset_layer(layer)

    def promote_cue_to_live(self, cue: Cue) -> None:
        """Promote a cue to LIVE status once its Pre-Delay completes."""
        self._live_phase_tags.pop(cue.cue_id, None)
        for other in self._cues:
            if other.layer == cue.layer and other.cue_id != cue.cue_id and other.status == CueStatus.LIVE:
                other.status = CueStatus.LOADED
        cue.status = CueStatus.LIVE
        self._update_live_layer_label(cue)
        self._refresh_cue_list(keep_selection=True)
        self._sync_live_view()

    def finish_live_cue_status(self, cue: Cue) -> None:
        """Mark cue finished (LOADED) and clean up phase badges safely."""
        self._live_phase_tags.pop(cue.cue_id, None)
        if cue.status == CueStatus.LIVE:
            cue.status = CueStatus.LOADED
        self._refresh_cue_list(keep_selection=True)
        self._sync_live_view()

    def trigger_auto_follow_from(self, finished_cue: Cue) -> None:
        """Start the next cue in sequence when an AUTO_FOLLOW cue completes."""
        try:
            idx = self._cues.index(finished_cue)
        except ValueError:
            return
        next_idx = idx + 1
        if 0 <= next_idx < len(self._cues):
            self._fire_cue_chain(next_idx)

    @Slot(int)
    def _on_live_row_double_clicked(self, row: int) -> None:
        if 0 <= row < len(self._cues):
            self._fire_cue_chain(row)

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
            self._update_live_layer_label(cue, preserve_timing=True)
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
        self._sync_live_view()

        ref = format_cue_ref(row, cue)
        self._inspector.setTitle(f"ISPETTORE CUE — {ref} [{cue.media_type.value}] '{cue.name}'")
        self._update_cue_readouts(row, cue)
        if cue.status == CueStatus.LIVE:
            self._update_live_layer_label(cue, preserve_timing=True)

    def _refresh_rows_in_place(self, rows: list[int]) -> None:
        """Update table cell visuals for *rows* in place without altering selection."""
        self._layer_conflicts = detect_layer_conflicts(self._cues)
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
        self._sync_live_view()

    def _refresh_cue_list(self, keep_selection: bool = True,
                          select_row: Optional[int] = None) -> None:
        """Rebuild the 3-column table from the cue list with progressive row numbers."""
        self._layer_conflicts = detect_layer_conflicts(self._cues)
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
        group_count = sum(1 for c in self._cues if c.media_type == MediaType.GROUP)
        if total_cues == 0:
            self._lbl_cue_count.setText("0 Cue")
            self._lbl_cue_standby.setText("Standby: Nessuna")
            self._update_inspector(None)
        else:
            if group_count > 0:
                self._lbl_cue_count.setText(f"{total_cues} Cue ({group_count} scene)")
            else:
                self._lbl_cue_count.setText(f"{total_cues} Cue")
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
        self._sync_live_view()

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

    def set_waveform_playhead_seconds(
        self,
        sec: Optional[float],
        duration_sec: float = 0.0,
        source_tag: str = "PRE-VIZ",
    ) -> None:
        """Update waveform cursor position (testina) and header readout/buttons safely."""
        prev_dur = self._active_test_duration
        if duration_sec > 0:
            self._active_test_duration = max(0.001, duration_sec)
        dur = self._active_test_duration if duration_sec <= 0 else duration_sec
        cue = self._selected_cue()
        is_image = cue is not None and cue.media_type == MediaType.IMAGE
        timed_cue = cue is not None and cue.media_type in (MediaType.VIDEO, MediaType.AUDIO)
        sel_cues = self._selected_cues()
        uniform_timed = timed_cue and bool(sel_cues) and len({c.media_type for c in sel_cues}) == 1
        if sec is None or dur <= 0 or (not timed_cue and not is_image):
            self._waveform.set_playhead(None)
            self._waveform_panel.set_playhead_display(
                None, 0.0, source_tag, snap_enabled=False, reset_enabled=uniform_timed
            )
            return
        if prev_dur <= 0 and dur > 0 and cue is not None:
            self._inspector.spin_out.set_media_duration(dur)
            self._sync_timeline_for_cue(cue)
        self._waveform.set_playhead_seconds(sec, dur)
        self._waveform_panel.set_playhead_display(
            sec,
            dur,
            source_tag,
            snap_enabled=timed_cue,
            reset_enabled=uniform_timed,
        )

    def update_waveform_duration(self, duration_sec: float) -> None:
        self._active_test_duration = max(0.001, duration_sec)
        self._inspector.spin_out.set_media_duration(self._active_test_duration)
        cue = self._selected_cue()
        if cue:
            self._sync_timeline_for_cue(cue)
            if cue.media_type in (MediaType.VIDEO, MediaType.AUDIO):
                cur_ph = self._waveform.playhead_seconds()
                target_sec = min(self._active_test_duration, max(0.0, cue.in_point)) if cur_ph is None else cur_ph
                self.set_waveform_playhead_seconds(target_sec, self._active_test_duration, "PRE-VIZ")

    def _update_waveform_markers(self, cue: Optional[Cue] = None) -> None:
        if cue is None:
            cue = self._selected_cue()
        if cue is None:
            return
        self._sync_timeline_for_cue(cue)

    def _effective_timeline_end(self, cue: Cue) -> float:
        if cue.media_type == MediaType.IMAGE:
            return cue.hold_time if cue.hold_time > 0 else cue.image_timeline_sec
        dur = self._active_test_duration
        if dur <= 0:
            return 0.0
        if cue.out_point is not None and cue.out_point > cue.in_point:
            return min(dur, cue.out_point)
        return dur

    def _sync_timeline_for_cue(self, cue: Optional[Cue]) -> None:
        """Keep waveform/opacity canvas, fade pallini, section bands, and controls synced."""
        if cue is None:
            return
        is_image = (cue.media_type == MediaType.IMAGE)
        dur = (cue.hold_time if cue.hold_time > 0 else cue.image_timeline_sec) if is_image else self._active_test_duration
        if is_image:
            self._active_test_duration = dur

        mode = "opacity" if is_image else self._waveform._envelope_mode
        show_fo = (not is_image) or (cue.hold_time > 0)
        self._waveform.set_media_context(cue.media_type, mode, show_fade_out=show_fo)
        if is_image:
            self._waveform.set_in_out_seconds(0.0, None, dur)
        else:
            self._waveform.set_in_out_seconds(cue.in_point, cue.out_point, dur)

        self._waveform.set_fades(cue.fade_in, cue.fade_out, cue.fade_curve)
        self._waveform.set_envelopes(
            base_volume=cue.volume,
            base_opacity=cue.opacity,
            volume_points=cue.volume_points,
            opacity_points=cue.opacity_points,
        )

        eff_end = self._effective_timeline_end(cue)
        if not is_image and dur > 0 and cue.sections:
            cue.sections = normalize_sections(cue.sections, cue.in_point, eff_end)
        else:
            cue.sections = [] if is_image else cue.sections

        active_idx = self._active_section_idx if len(cue.sections) >= 2 else -1
        self._waveform.set_sections(cue.sections, active_idx=active_idx)
        self._waveform_panel.section_bar.set_sections(cue.sections, dur, active_index=active_idx)

        active_pts = cue.opacity_points if mode == "opacity" else cue.volume_points
        can_split = (not is_image) and dur > 0 and (eff_end - cue.in_point) >= 0.35
        has_repeating = any(s.loops == 0 or s.loops > 1 for s in cue.sections if not s.skip)
        self._waveform_panel.sync_controls_for_cue(
            media_type=cue.media_type,
            fade_curve=cue.fade_curve,
            has_points=bool(active_pts),
            has_sections=len(cue.sections) >= 2,
            can_split=can_split,
            has_repeating_section=has_repeating,
            image_horizon_sec=cue.image_timeline_sec,
            hold_time=cue.hold_time,
        )

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
            self._inspector.set_layer_conflict(None)
            return
        sel_cues = self._selected_cues()
        anchor_row, anchor_cue = self._anchor_row_and_cue()
        if anchor_cue is not None:
            self._update_crop_reference_for_cue(anchor_cue)
        if len(sel_cues) > 1:
            self._inspector.load_selection(sel_cues, anchor_cue=anchor_cue, anchor_row=anchor_row)
        else:
            self._inspector.load_cue(cue, anchor_row)
            if cue.media_type == MediaType.GROUP:
                children = [c for c in self._cues if c.parent_id == cue.cue_id]
                self._inspector.load_group_children(children, cue)
        self._inspector.set_layer_conflict(self._layer_conflicts.get(cue.cue_id))
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
            if field_key in ("in_point", "out_point", "volume", "opacity", "fade_in", "fade_out", "hold_time"):
                self._sync_timeline_for_cue(anchor)
                self.live_automation_updated.emit(anchor)
            if field_key in ("in_point", "out_point"):
                self.preview_in_out_changed.emit(
                    anchor.in_point, anchor.out_point, field_key == "in_point"
                )
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
        prev_in = cue.in_point
        prev_out = cue.out_point
        self._inspector.apply_to_cue(cue)
        self._sync_timeline_for_cue(cue)
        self.live_volume_changed.emit(self._inspector.slider_volume.value())
        self.live_automation_updated.emit(cue)
        if cue.in_point != prev_in or cue.out_point != prev_out:
            self.preview_in_out_changed.emit(
                cue.in_point, cue.out_point, cue.in_point != prev_in
            )

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

    def _commit_waveform_in(
        self, new_in: float, *, clear_conflicting_out: bool = False, seek_preview: bool = True
    ) -> None:
        sel_cues = self._selected_cues()
        if not sel_cues or len({c.media_type for c in sel_cues}) != 1:
            return
        rounded_in = round(max(0.0, new_in), 2)
        for cue in sel_cues:
            cue.in_point = rounded_in
            if cue.out_point is not None and cue.out_point <= rounded_in + 0.04:
                cue.out_point = None if clear_conflicting_out else round(rounded_in + 0.05, 2)
        anchor = self._selected_cue()
        if anchor:
            self._inspector.set_in_silent(anchor.in_point)
            self._inspector.set_out_silent(anchor.out_point or 0.0)
            self._update_waveform_markers(anchor)
            self.preview_in_out_changed.emit(anchor.in_point, anchor.out_point, seek_preview)
        self._schedule_undo_point()
        self._mark_modified(True)

    def _commit_waveform_out(self, new_out: Optional[float]) -> Optional[float]:
        sel_cues = self._selected_cues()
        if not sel_cues or len({c.media_type for c in sel_cues}) != 1:
            return None
        for cue in sel_cues:
            if new_out is None or new_out <= 0.0:
                cue.out_point = None
            elif new_out <= cue.in_point + 0.04:
                cue.out_point = round(cue.in_point + 0.05, 2)
            else:
                cue.out_point = round(new_out, 2)
        anchor = self._selected_cue()
        if anchor:
            self._inspector.set_out_silent(anchor.out_point or 0.0)
            self._update_waveform_markers(anchor)
            self.preview_in_out_changed.emit(anchor.in_point, anchor.out_point, False)
        self._schedule_undo_point()
        self._mark_modified(True)
        return anchor.out_point if anchor else None

    @Slot(float)
    def _on_waveform_in_changed(self, new_in: float) -> None:
        self._commit_waveform_in(new_in, clear_conflicting_out=False, seek_preview=True)

    @Slot(float)
    def _on_waveform_out_changed(self, new_out: float) -> None:
        self._commit_waveform_out(None if new_out <= 0.0 else new_out)

    @Slot(float)
    def _on_waveform_seek_requested(self, sec: float) -> None:
        cue = self._selected_cue()
        if cue is None:
            return
        if cue.media_type == MediaType.IMAGE:
            dur = self._effective_timeline_end(cue)
            self._img_previz_elapsed = max(0.0, min(dur, sec))
            self.set_waveform_playhead_seconds(self._img_previz_elapsed, dur, "PRE-VIZ")
            self.set_preview_time(self._img_previz_elapsed, dur)
            op = evaluate_cue_level(
                self._img_previz_elapsed,
                start_sec=0.0,
                end_sec=cue.hold_time if cue.hold_time > 0 else None,
                duration_sec=dur,
                fade_in=cue.fade_in,
                fade_out=cue.fade_out if cue.hold_time > 0 else 0.0,
                fade_curve=cue.fade_curve,
                points=cue.opacity_points,
                base_level=cue.opacity,
                apply_fade_out_at_end=(cue.hold_time > 0),
            )
            self._preview_monitor.set_opacity(op)
            return
        if cue.media_type not in (MediaType.VIDEO, MediaType.AUDIO):
            return
        self._waveform_panel.set_playhead_display(sec, self._active_test_duration, "PRE-VIZ", snap_enabled=True)
        self.set_preview_time(sec, self._active_test_duration)
        self.preview_seek_requested.emit(sec)

    def _on_snap_shortcut(self, is_in: bool) -> None:
        if self._live_mode or self._is_text_input_focused():
            return
        if is_in:
            self._on_snap_in_to_playhead()
        else:
            self._on_snap_out_to_playhead()

    @Slot()
    def _on_snap_in_to_playhead(self) -> None:
        cue = self._selected_cue()
        dur = self._waveform.duration_seconds()
        playhead_sec = self._waveform.playhead_seconds()
        if cue is None or cue.media_type not in (MediaType.VIDEO, MediaType.AUDIO) or dur <= 0 or playhead_sec is None:
            return
        target_in = round(max(0.0, min(max(0.0, dur - 0.05), playhead_sec)), 2)
        self._commit_waveform_in(target_in, clear_conflicting_out=True, seek_preview=False)
        self._status_label.setText(f"Punto IN spostato sulla testina: {target_in:.2f}s")

    @Slot()
    def _on_snap_out_to_playhead(self) -> None:
        cue = self._selected_cue()
        dur = self._waveform.duration_seconds()
        playhead_sec = self._waveform.playhead_seconds()
        if cue is None or cue.media_type not in (MediaType.VIDEO, MediaType.AUDIO) or dur <= 0 or playhead_sec is None:
            return
        if playhead_sec >= dur - 0.05:
            applied = self._commit_waveform_out(None)
            self._status_label.setText("Punto OUT impostato sulla fine del file (Fine)")
        elif playhead_sec <= cue.in_point + 0.04:
            target_out = round(min(dur, cue.in_point + 0.05), 2)
            applied = self._commit_waveform_out(target_out)
            self._status_label.setText(
                f"Testina prima di IN: OUT impostato al minimo ({applied:.2f}s)" if applied else "OUT aggiornato"
            )
        else:
            applied = self._commit_waveform_out(round(playhead_sec, 2))
            self._status_label.setText(
                f"Punto OUT spostato sulla testina: {applied:.2f}s" if applied else "OUT aggiornato"
            )

    @Slot()
    def _on_reset_in_out(self) -> None:
        """Reset IN to 0.00s and OUT to Fine (None) across selected same-type timed cues."""
        sel_cues = self._selected_cues()
        if not sel_cues or len({c.media_type for c in sel_cues}) != 1:
            return
        if sel_cues[0].media_type not in (MediaType.VIDEO, MediaType.AUDIO):
            return
        for cue in sel_cues:
            cue.in_point = 0.0
            cue.out_point = None
        anchor = self._selected_cue()
        if anchor:
            self._inspector.set_in_silent(0.0)
            self._inspector.set_out_silent(0.0)
            self._update_waveform_markers(anchor)
            self.preview_in_out_changed.emit(0.0, None, False)
        self._schedule_undo_point()
        self._mark_modified(True)
        self._status_label.setText("Punti IN e OUT ripristinati: IN = 0.00s, OUT = Fine")

    # ── Fade Ramps, Keyframe Envelopes, Image Pre-Viz & Sections ──────

    @Slot(float)
    def _on_waveform_fade_in_changed(self, new_fi: float) -> None:
        sel_cues = self._selected_cues()
        if not sel_cues or len({c.media_type for c in sel_cues}) != 1:
            return
        val = round(max(0.0, new_fi), 2)
        for cue in sel_cues:
            cue.fade_in = val
        anchor = self._selected_cue()
        if anchor:
            self._inspector.set_fades_silent(fade_in=val)
            self._sync_timeline_for_cue(anchor)
            self.live_automation_updated.emit(anchor)
        self._schedule_undo_point()
        self._mark_modified(True)
        self._status_label.setText(f"Fade IN: {val:.2f}s")

    @Slot(float)
    def _on_waveform_fade_out_changed(self, new_fo: float) -> None:
        sel_cues = self._selected_cues()
        if not sel_cues or len({c.media_type for c in sel_cues}) != 1:
            return
        val = round(max(0.0, new_fo), 2)
        for cue in sel_cues:
            cue.fade_out = val
        anchor = self._selected_cue()
        if anchor:
            self._inspector.set_fades_silent(fade_out=val)
            self._sync_timeline_for_cue(anchor)
            self.live_automation_updated.emit(anchor)
        self._schedule_undo_point()
        self._mark_modified(True)
        self._status_label.setText(f"Fade OUT: {val:.2f}s")

    @Slot(str)
    def _on_waveform_fade_curve_changed(self, curve: str) -> None:
        sel_cues = self._selected_cues()
        if not sel_cues or len({c.media_type for c in sel_cues}) != 1:
            return
        for cue in sel_cues:
            cue.fade_curve = curve
        anchor = self._selected_cue()
        if anchor:
            self._sync_timeline_for_cue(anchor)
            self.live_automation_updated.emit(anchor)
        self._schedule_undo_point()
        self._mark_modified(True)
        self._status_label.setText(f"Curva Fade impostata: {curve}")

    @Slot(str)
    def _on_envelope_mode_changed(self, mode: str) -> None:
        cue = self._selected_cue()
        if cue:
            self._sync_timeline_for_cue(cue)

    @Slot(str, list)
    def _on_envelope_points_changed(self, mode: str, points: list) -> None:
        sel_cues = self._selected_cues()
        if not sel_cues or len({c.media_type for c in sel_cues}) != 1:
            return
        copied = [list(p) for p in points]
        for cue in sel_cues:
            if mode == "opacity":
                cue.opacity_points = [list(p) for p in copied]
            else:
                cue.volume_points = [list(p) for p in copied]
        anchor = self._selected_cue()
        if anchor:
            self._sync_timeline_for_cue(anchor)
            self.live_automation_updated.emit(anchor)
        self._schedule_undo_point()
        self._mark_modified(True)

    @Slot(str)
    def _on_reset_envelope_points(self, mode: str) -> None:
        sel_cues = self._selected_cues()
        if not sel_cues or len({c.media_type for c in sel_cues}) != 1:
            return
        for cue in sel_cues:
            if mode == "opacity":
                cue.opacity_points = []
            else:
                cue.volume_points = []
        anchor = self._selected_cue()
        if anchor:
            self._sync_timeline_for_cue(anchor)
            self.live_automation_updated.emit(anchor)
            if anchor.media_type == MediaType.IMAGE:
                self._preview_monitor.set_opacity(anchor.opacity)
        self._commit_undo_point()
        self._mark_modified(True)
        self._status_label.setText("Punti envelope azzerati")

    @Slot(float)
    def _on_image_horizon_changed(self, horizon_sec: float) -> None:
        cue = self._selected_cue()
        if cue is None or cue.media_type != MediaType.IMAGE:
            return
        cue.image_timeline_sec = max(1.0, float(horizon_sec))
        self._sync_timeline_for_cue(cue)
        self.set_waveform_playhead_seconds(min(self._img_previz_elapsed, cue.image_timeline_sec), cue.image_timeline_sec, "PRE-VIZ")
        self._schedule_undo_point()
        self._mark_modified(True)

    @Slot()
    def _on_split_section(self) -> None:
        cue = self._selected_cue()
        dur = self._active_test_duration
        if cue is None or cue.media_type not in (MediaType.VIDEO, MediaType.AUDIO) or dur <= 0:
            return
        eff_end = self._effective_timeline_end(cue)
        ph = self._waveform.playhead_seconds()
        if ph is not None and cue.in_point + 0.15 <= ph <= eff_end - 0.15:
            split_t = ph
        else:
            # Smart midpoint split of active region when testina is sitting at an edge
            target_sec = next(
                (s for s in cue.sections if (s.end or eff_end) - s.start >= 0.30),
                None,
            )
            if target_sec is not None:
                s_end = target_sec.end if target_sec.end is not None else eff_end
                split_t = round((target_sec.start + s_end) / 2.0, 2)
            else:
                split_t = round((cue.in_point + eff_end) / 2.0, 2)

        updated = split_sections_at(cue.sections, split_t, cue.in_point, eff_end)
        if len(updated) <= len(cue.sections) and len(cue.sections) >= 2:
            self._status_label.setText("Spazio insufficiente per dividere ancora in questo punto")
            return
        cue.sections = updated
        self._sync_timeline_for_cue(cue)
        self.live_automation_updated.emit(cue)
        self._commit_undo_point()
        self._mark_modified(True)
        self._status_label.setText(f"Creato taglio sezione a {split_t:.2f}s ({len(cue.sections)} sezioni)")

    @Slot(list)
    def _on_sections_resized(self, sections_list: list) -> None:
        cue = self._selected_cue()
        if cue is None or cue.media_type not in (MediaType.VIDEO, MediaType.AUDIO):
            return
        cue.sections = list(sections_list)
        self._waveform_panel.section_bar.set_sections(
            cue.sections, self._active_test_duration, active_index=self._active_section_idx
        )
        self.live_automation_updated.emit(cue)
        self._schedule_undo_point()
        self._mark_modified(True)

    @Slot(int, int, bool)
    def _on_section_mode_changed(self, idx: int, loops: int, skip: bool) -> None:
        cue = self._selected_cue()
        if cue is None or not (0 <= idx < len(cue.sections)):
            return
        cue.sections[idx].loops = loops
        cue.sections[idx].skip = skip
        self._sync_timeline_for_cue(cue)
        self.live_automation_updated.emit(cue)
        self._commit_undo_point()
        self._mark_modified(True)
        mode_lbl = "Salta" if skip else ("∞ Infinito" if loops == 0 else f"x{loops}")
        self._status_label.setText(f"Sezione {cue.sections[idx].label}: {mode_lbl}")

    @Slot(int)
    def _on_remove_section(self, idx: int) -> None:
        cue = self._selected_cue()
        if cue is None or not cue.sections:
            return
        eff_end = self._effective_timeline_end(cue)
        cue.sections = merge_section_at(cue.sections, idx, cue.in_point, eff_end)
        if not cue.sections:
            self._active_section_idx = -1
        self._sync_timeline_for_cue(cue)
        self.live_automation_updated.emit(cue)
        self._commit_undo_point()
        self._mark_modified(True)
        self._status_label.setText(
            "Ritorno a file intero (modalità normale)" if not cue.sections else "Sezione unita"
        )

    @Slot()
    def _on_reset_sections(self) -> None:
        cue = self._selected_cue()
        if cue is None or not cue.sections:
            return
        cue.sections = []
        self._active_section_idx = -1
        self._sync_timeline_for_cue(cue)
        self.live_automation_updated.emit(cue)
        self._commit_undo_point()
        self._mark_modified(True)
        self._status_label.setText("Sezioni azzerate: ripristinato il file originale")

    @Slot(int)
    def _on_section_jump_clicked(self, idx: int) -> None:
        cue = self._selected_cue()
        if cue is None or not (0 <= idx < len(cue.sections)):
            return
        self._active_section_idx = idx
        self._waveform.set_active_section_index(idx)
        self._waveform_panel.section_bar.set_active_index(idx)
        self.section_jump_requested.emit(cue, idx, cue.status == CueStatus.LIVE)

    @Slot()
    def _on_break_section_loop(self) -> None:
        cue = self._selected_cue()
        if cue is None or not cue.sections:
            return
        self.section_break_loop_requested.emit(cue, cue.status == CueStatus.LIVE)

    def set_live_section_index(self, cue_id: int, sec_idx: int) -> None:
        cue = self._selected_cue()
        if cue is not None and cue.cue_id == cue_id:
            self._active_section_idx = sec_idx
            self._waveform.set_active_section_index(sec_idx)
            self._waveform_panel.section_bar.set_active_index(sec_idx)

    # ── Image Pre-Viz Opacity Timeline Player ─────────────────────────

    def start_image_preview_playback(self, cue: Cue) -> None:
        if cue.media_type != MediaType.IMAGE:
            return
        dur = self._effective_timeline_end(cue)
        if self._img_previz_elapsed >= dur - 0.02:
            self._img_previz_elapsed = 0.0
        self.show_preview_image(
            cue.file_path, scale=cue.scale, crop=cue.crop,
            pos_x=cue.position_x, pos_y=cue.position_y,
            opacity=cue.opacity, aspect_ratio=cue.aspect_ratio,
        )
        self._on_img_previz_tick(advance=False)
        self._img_previz_timer.start()

    def pause_image_preview_playback(self) -> None:
        self._img_previz_timer.stop()

    def stop_image_preview_playback(self) -> None:
        self._img_previz_timer.stop()
        self._img_previz_elapsed = 0.0
        cue = self._selected_cue()
        if cue is not None and cue.media_type == MediaType.IMAGE:
            dur = self._effective_timeline_end(cue)
            self.set_waveform_playhead_seconds(0.0, dur, "PRE-VIZ")
            self.set_preview_time(0.0, dur)
            self._preview_monitor.set_opacity(cue.opacity)

    def _on_img_previz_tick(self, advance: bool = True) -> None:
        cue = self._selected_cue()
        if cue is None or cue.media_type != MediaType.IMAGE:
            self._img_previz_timer.stop()
            return
        dur = self._effective_timeline_end(cue)
        if advance:
            self._img_previz_elapsed += 0.033
        if self._img_previz_elapsed >= dur:
            self._img_previz_elapsed = dur
            self._img_previz_timer.stop()
        op = evaluate_cue_level(
            self._img_previz_elapsed,
            start_sec=0.0,
            end_sec=cue.hold_time if cue.hold_time > 0 else None,
            duration_sec=dur,
            fade_in=cue.fade_in,
            fade_out=cue.fade_out if cue.hold_time > 0 else 0.0,
            fade_curve=cue.fade_curve,
            points=cue.opacity_points,
            base_level=cue.opacity,
            apply_fade_out_at_end=(cue.hold_time > 0),
        )
        self._preview_monitor.set_opacity(op)
        self.set_waveform_playhead_seconds(self._img_previz_elapsed, dur, "PRE-VIZ")
        self.set_preview_time(self._img_previz_elapsed, dur)

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
            anchor_row, anchor = self._anchor_row_and_cue()
            if anchor:
                self._inspector.set_layer_conflict(self._layer_conflicts.get(anchor.cue_id))

            sel_cues = [self._cues[r] for r in sel_rows]
            self._update_crop_reference_for_cue(cue)
            self._inspector.load_selection(sel_cues, anchor_cue=cue, anchor_row=anchor_row)
            if cue.media_type == MediaType.GROUP:
                children = [c for c in self._cues if c.parent_id == cue.cue_id]
                self._inspector.load_group_children(children, cue)

            if cue.cue_id != prev_anchor_id:
                self._img_previz_timer.stop()
                self._img_previz_elapsed = 0.0
                self._active_section_idx = -1
                self._waveform_panel.reset_zoom()
                self._request_waveform(cue)
                if cue.media_type == MediaType.IMAGE:
                    dur_img = cue.hold_time if cue.hold_time > 0 else cue.image_timeline_sec
                    self._active_test_duration = dur_img
                    self._sync_timeline_for_cue(cue)
                    self.set_waveform_playhead_seconds(0.0, dur_img, "PRE-VIZ")
                else:
                    self._active_test_duration = 0.0
                    self.set_waveform_playhead_seconds(None, 0.0)
                if cue.media_type == MediaType.VIDEO:
                    self._preview_monitor.clear_video_frame()
                self._render_cue_in_preview(cue, load_image=False)
                self.cue_preview_requested.emit(cue)

            self._sync_timeline_for_cue(cue)
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

            modes = {c.follow_mode for c in sel_cues}
            self._cue_list_panel.set_follow_mode_checked(
                next(iter(modes)) if len(modes) == 1 else None, enabled=True
            )
            self._sync_live_view()

            logger.debug("Cue selected (count=%d): %s", len(sel_cues), cue)
        else:
            self._inspector.load_cue(None)
            self._cue_list_panel.set_follow_mode_checked(FollowMode.MANUAL.value, enabled=False)
            self._reset_idle_preview_ui()
            self._lbl_cue_standby.setText("Standby: Nessuna")
            self._sync_live_view()

    @Slot(object)
    def _on_preview_video_frame_for_mirror(self, _frame) -> None:
        if not self._live_mirror_active:
            return
        cue = self._selected_cue()
        if cue is not None and cue.media_type == MediaType.VIDEO and cue.status != CueStatus.LIVE:
            self._push_cue_to_output(cue)

    def _push_cue_to_output(self, cue: Cue) -> None:
        """Render an IMAGE or VIDEO cue onto its assigned output layer (mirror-safe)."""
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
            if cue.status == CueStatus.LIVE:
                self._output.ensure_live_video_visible(
                    layer=cue.layer,
                    scale=cue.scale,
                    crop=cue.crop,
                    pos_x=cue.position_x,
                    pos_y=cue.position_y,
                    opacity=cue.opacity,
                    aspect_ratio=cue.aspect_ratio,
                )
            else:
                frame_img = self._preview_monitor.current_video_frame()
                if frame_img is not None and not frame_img.isNull():
                    # Keep standby/Pre-Viz preview opacity synced when playing fades
                    op = (
                        self._preview_monitor._opacity
                        if self._preview_monitor._active_media_type == MediaType.VIDEO
                        else cue.opacity
                    )
                    self._output.show_mirrored_frame(
                        cue.layer,
                        frame_img,
                        opacity=op,
                        crop=cue.crop,
                        scale=cue.scale,
                        pos_x=cue.position_x,
                        pos_y=cue.position_y,
                        aspect_ratio=cue.aspect_ratio,
                    )
                else:
                    # Wait for decoded Pre-Viz frame rather than flashing black video surface
                    has_live_on_layer = any(
                        c.status == CueStatus.LIVE and c.layer == cue.layer and c.media_type in (MediaType.IMAGE, MediaType.VIDEO)
                        for c in self._cues
                    )
                    if not has_live_on_layer:
                        self._output.clear_layer(cue.layer)
        elif cue.media_type == MediaType.AUDIO:
            has_live_visual = any(
                c.status == CueStatus.LIVE and c.layer == cue.layer and c.media_type in (MediaType.IMAGE, MediaType.VIDEO)
                for c in self._cues
            )
            if not has_live_visual:
                self._output.clear_layer(cue.layer)

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
            prev_layer = self._last_mirrored_layer
            self._last_mirrored_layer = None
            live_cues = [c for c in self._cues if c.status == CueStatus.LIVE]
            if not live_cues:
                self._output.show_fallback()
            elif prev_layer is not None:
                live_on_prev = next(
                    (
                        c for c in live_cues
                        if c.layer == prev_layer and c.media_type in (MediaType.IMAGE, MediaType.VIDEO)
                    ),
                    None,
                )
                if live_on_prev is None:
                    self._output.clear_layer(prev_layer)
                else:
                    self._push_cue_to_output(live_on_prev)
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
            self._refresh_rows_in_place(list(range(len(self._cues))))
            anchor_row, anchor = self._anchor_row_and_cue()
            if anchor:
                self._inspector.set_layer_conflict(self._layer_conflicts.get(anchor.cue_id))
            if len(sel_cues) > 1:
                anchor_row, anchor = self._anchor_row_and_cue()
                self._inspector.load_selection(sel_cues, anchor_cue=anchor, anchor_row=anchor_row)
            else:
                self._inspector.set_layer_conflict(self._layer_conflicts.get(sel_cues[0].cue_id))
            self._commit_undo_point()
            self._mark_modified(True)
            self._auto_save()
            self._sync_live_view()

    @Slot(str)
    def _set_follow_mode(self, mode: str) -> None:
        sel_rows = self._selected_rows()
        if not sel_rows:
            return
        if self._undo.is_debounce_active():
            self._commit_undo_point()
        sel_cues = [self._cues[r] for r in sel_rows]
        changed = any(cue.follow_mode != mode for cue in sel_cues)
        self._cue_list_panel.set_follow_mode_checked(mode, enabled=True)
        self._inspector.set_follow_mode_silent(mode, enabled=True)
        if changed:
            for cue in sel_cues:
                cue.follow_mode = mode
            self._refresh_rows_in_place(list(range(len(self._cues))))
            anchor_row, anchor = self._anchor_row_and_cue()
            if anchor:
                self._inspector.set_layer_conflict(self._layer_conflicts.get(anchor.cue_id))
            self._sync_live_view()
            self._commit_undo_point()
            self._mark_modified(True)
            self._auto_save()

    @Slot(str)
    def _set_cue_color(self, color_hex: str) -> None:
        """Assign or clear visual scene group colour across selected cue(s)."""
        sel_rows = self._selected_rows()
        if not sel_rows:
            return
        if self._undo.is_debounce_active():
            self._commit_undo_point()
        clean = _sanitize_hex_color(color_hex)
        sel_cues = [self._cues[r] for r in sel_rows]
        changed = any(getattr(cue, "color", "") != clean for cue in sel_cues)
        self._inspector.set_color_silent(clean)
        if changed:
            for cue in sel_cues:
                cue.color = clean
            self._refresh_rows_in_place(list(range(len(self._cues))))
            anchor_row, anchor = self._anchor_row_and_cue()
            if anchor:
                self._inspector.set_layer_conflict(self._layer_conflicts.get(anchor.cue_id))
            self._sync_live_view()
            self._commit_undo_point()
            self._mark_modified(True)
            self._auto_save()

    # ── Playback Transport (GO / Blackout / Panic) ────────────────────

    @Slot()
    def _on_go(self) -> None:
        focus_w = QApplication.focusWidget()
        if isinstance(focus_w, (QLineEdit, QAbstractSpinBox, QComboBox)):
            return

        if not self._cues:
            self._status_label.setText("Scaletta vuota — Aggiungi prima dei file multimediali")
            return

        if hasattr(self, "_earcon_mgr"):
            self._earcon_mgr.play_go()

        self._apply_inspector_to_cue()

        row, _ = self._anchor_row_and_cue()
        if 0 <= row < len(self._cues):
            target_idx = row
        elif 0 <= self._current_index < len(self._cues):
            target_idx = self._current_index
        else:
            target_idx = 0

        self._fire_cue_chain(target_idx)

    def _fire_cue_chain(self, start_idx: int) -> None:
        """Fire cue at *start_idx*, advancing immediately across any SIMULTANEOUS chain or Group execution."""
        if not (0 <= start_idx < len(self._cues)):
            return

        start_cue = self._cues[start_idx]

        # Auto-expand if cue belongs to a collapsed group
        if start_cue.parent_id is not None:
            parent_cue = next((c for c in self._cues if c.cue_id == start_cue.parent_id), None)
            if parent_cue and parent_cue.collapsed:
                p_row = self._cues.index(parent_cue)
                self._toggle_group_collapsed(p_row)

        if start_cue.media_type == MediaType.GROUP:
            self._fire_group_cue(start_idx, start_cue)
            return

        chain_indices: list[int] = []
        visited: set[int] = set()
        idx = start_idx
        while 0 <= idx < len(self._cues) and idx not in visited:
            visited.add(idx)
            chain_indices.append(idx)
            if self._cues[idx].follow_mode != FollowMode.SIMULTANEOUS.value:
                break
            idx += 1

        last_fired_idx = chain_indices[-1]
        self._live_show_panel.notify_first_go()
        for c_idx in chain_indices:
            cue = self._cues[c_idx]
            if cue.pre_delay <= 0.02:
                for other in self._cues:
                    if other.layer == cue.layer and other.cue_id != cue.cue_id and other.status == CueStatus.LIVE:
                        other.status = CueStatus.LOADED
                cue.status = CueStatus.LIVE
                self._update_live_layer_label(cue)
            self._current_index = c_idx
            self.cue_fired.emit(cue)
            logger.info("[GO] Fired cue #%d: %s", cue.cue_id, cue)

        self._refresh_cue_list(keep_selection=False)

        first_cue = self._cues[start_idx]
        ref = format_cue_ref(start_idx, first_cue)
        next_idx = last_fired_idx + 1
        if next_idx < len(self._cues):
            self._cue_list.setCurrentRow(next_idx)
            next_ref = format_cue_ref(next_idx, self._cues[next_idx])
            self._status_label.setText(
                f"LIVE → {ref} '{first_cue.name}' (Layer {first_cue.layer}) | Standby: {next_ref} '{self._cues[next_idx].name}'"
            )
        else:
            self._cue_list.setCurrentRow(last_fired_idx)
            self._status_label.setText(
                f"LIVE → {ref} '{first_cue.name}' (Layer {first_cue.layer}) — Fine scaletta (premi GO per rilanciare)"
            )

        self._sync_live_view()
        self._auto_save()

    def _fire_group_cue(self, group_idx: int, group_cue: Cue) -> None:
        """Execute a MediaType.GROUP container cue according to its group_mode."""
        children = [c for c in self._cues if c.parent_id == group_cue.cue_id]
        if not children:
            next_idx = group_idx + 1
            if next_idx < len(self._cues):
                self._cue_list.setCurrentRow(next_idx)
            self._sync_live_view()
            return

        self._live_show_panel.notify_first_go()
        mode = getattr(group_cue, "group_mode", GroupMode.STEP.value)

        if group_cue.collapsed:
            self._toggle_group_collapsed(group_idx)

        group_cue.status = CueStatus.LIVE

        if mode == GroupMode.SIMULTANEOUS.value:
            for child in children:
                if child.pre_delay <= 0.02:
                    for other in self._cues:
                        if other.layer == child.layer and other.cue_id != child.cue_id and other.status == CueStatus.LIVE:
                            other.status = CueStatus.LOADED
                    child.status = CueStatus.LIVE
                    self._update_live_layer_label(child)
                self.cue_fired.emit(child)
                logger.info("[GO-GROUP-SIMUL] Fired child #%d '%s'", child.cue_id, child.name)

            self._refresh_cue_list(keep_selection=False)
            last_child_idx = self._cues.index(children[-1])
            next_idx = last_child_idx + 1
            if next_idx < len(self._cues):
                self._cue_list.setCurrentRow(next_idx)
            else:
                self._cue_list.setCurrentRow(last_child_idx)

        elif mode == GroupMode.RANDOM.value:
            import random
            chosen = random.choice(children)
            if chosen.pre_delay <= 0.02:
                for other in self._cues:
                    if other.layer == chosen.layer and other.cue_id != chosen.cue_id and other.status == CueStatus.LIVE:
                        other.status = CueStatus.LOADED
                chosen.status = CueStatus.LIVE
                self._update_live_layer_label(chosen)
            self.cue_fired.emit(chosen)
            logger.info("[GO-GROUP-RANDOM] Fired random child #%d '%s'", chosen.cue_id, chosen.name)
            self._refresh_cue_list(keep_selection=False)
            last_child_idx = self._cues.index(children[-1])
            next_idx = last_child_idx + 1
            if next_idx < len(self._cues):
                self._cue_list.setCurrentRow(next_idx)

        elif mode == GroupMode.SEQUENCE.value:
            first_child = children[0]
            if first_child.pre_delay <= 0.02:
                for other in self._cues:
                    if other.layer == first_child.layer and other.cue_id != first_child.cue_id and other.status == CueStatus.LIVE:
                        other.status = CueStatus.LOADED
                first_child.status = CueStatus.LIVE
                self._update_live_layer_label(first_child)
            self.cue_fired.emit(first_child)
            logger.info("[GO-GROUP-SEQ] Fired child 0 #%d '%s'", first_child.cue_id, first_child.name)
            self._refresh_cue_list(keep_selection=False)
            if len(children) > 1:
                self._cue_list.setCurrentRow(self._cues.index(children[1]))
            else:
                next_idx = self._cues.index(first_child) + 1
                if next_idx < len(self._cues):
                    self._cue_list.setCurrentRow(next_idx)

        else:  # STEP or LOOP
            first_child = children[0]
            if first_child.pre_delay <= 0.02:
                for other in self._cues:
                    if other.layer == first_child.layer and other.cue_id != first_child.cue_id and other.status == CueStatus.LIVE:
                        other.status = CueStatus.LOADED
                first_child.status = CueStatus.LIVE
                self._update_live_layer_label(first_child)
            self.cue_fired.emit(first_child)
            logger.info("[GO-GROUP-STEP] Fired child 0 #%d '%s'", first_child.cue_id, first_child.name)
            self._refresh_cue_list(keep_selection=False)
            if len(children) > 1:
                self._cue_list.setCurrentRow(self._cues.index(children[1]))
            else:
                next_idx = self._cues.index(first_child) + 1
                if next_idx < len(self._cues):
                    self._cue_list.setCurrentRow(next_idx)

        self._sync_live_view()
        self._auto_save()

    @Slot()
    def _on_blackout(self) -> None:
        if hasattr(self, "_earcon_mgr"):
            self._earcon_mgr.play_stop()
        self._live_phase_tags.clear()
        self._output.show_fallback()
        for cue in self._cues:
            if cue.status == CueStatus.LIVE:
                cue.status = CueStatus.LOADED
        self._refresh_cue_list()
        for sp in self._for_each_status_panel():
            sp.reset_all_layers()
        self.set_global_paused(False)
        self.blackout_requested.emit()
        self._sync_live_view()
        self._status_label.setText("BLACKOUT — Output ripristinato a Layer 0 (Tappo)")
        logger.info("[BLACKOUT] Activated")

    @Slot()
    def _on_panic(self) -> None:
        """Immediate 0ms PANIC hard cut across every active player, delay timer, and output layer."""
        self._live_phase_tags.clear()
        for cue in self._cues:
            if cue.status == CueStatus.LIVE:
                cue.status = CueStatus.LOADED
        self._refresh_cue_list()
        for sp in self._for_each_status_panel():
            sp.reset_all_layers()
        self.set_global_paused(False)
        self.panic_requested.emit()
        self._output.panic_blackout()
        self._sync_live_view()
        self._status_label.setText("🚨 PANIC (0ms) — STOP TOTALE ESEGUITO")
        logger.warning("[PANIC] Executed hard stop all layers")

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

        moving_cue = self._cues[row]
        target_cue = self._cues[target_row]

        # Extract if moving past group boundaries
        if delta < 0 and moving_cue.parent_id == target_cue.cue_id:
            moving_cue.parent_id = None
            self._status_label.setText(f"Estratta cue '{moving_cue.name}' dal gruppo (spostata sopra la scena)")
        elif delta > 0 and moving_cue.parent_id is not None and target_cue.parent_id != moving_cue.parent_id:
            moving_cue.parent_id = None
            self._status_label.setText(f"Estratta cue '{moving_cue.name}' dal gruppo (spostata sotto la scena)")

        self._cues[row], self._cues[target_row] = self._cues[target_row], self._cues[row]
        self._current_index = target_row
        self._refresh_cue_list(keep_selection=False, select_row=target_row)
        self._sync_inspector_header_and_text(target_row, self._cues[target_row])
        self._commit_undo_point()
        self._mark_modified(True)
        self._auto_save()

    @Slot()
    def _on_move_up(self) -> None:
        if self._live_mode:
            return
        self._move_selected_cue(-1)

    @Slot()
    def _on_move_down(self) -> None:
        if self._live_mode:
            return
        self._move_selected_cue(1)

    @Slot()
    def _on_delete_cue(self) -> None:
        if self._live_mode:
            return
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
        for rem in removed:
            if rem.media_type == MediaType.GROUP:
                for c in self._cues:
                    if c.parent_id == rem.cue_id:
                        c.parent_id = None
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

    # ── Group Cues & Scene Containers ─────────────────────────────────

    @Slot()
    def _on_add_group(self) -> None:
        """Create a new Group cue, wrapping any selected cues or inserting an empty group."""
        if self._live_mode:
            return
        sel_rows = self._selected_rows()
        sel_cues = [self._cues[r] for r in sel_rows if self._cues[r].media_type != MediaType.GROUP]

        if self._undo.is_debounce_active():
            self._commit_undo_point()

        group_color = sel_cues[0].color if (sel_cues and sel_cues[0].color) else "#6366f1"
        group_cue = Cue(
            name="Nuova Scena / Gruppo",
            file_path="",
            media_type=MediaType.GROUP,
            group_mode=GroupMode.STEP.value,
            color=group_color,
            layer=1,
            collapsed=False,
            status=CueStatus.LOADED,
        )

        if sel_cues:
            insert_pos = min(sel_rows)
            # Remove sel_cues from self._cues
            remaining_cues = [c for c in self._cues if c not in sel_cues]
            # Set parent_id on all sel_cues
            for c in sel_cues:
                c.parent_id = group_cue.cue_id
            # Reconstruct list with group_cue and its children placed contiguously
            new_cues = remaining_cues[:insert_pos] + [group_cue] + sel_cues + remaining_cues[insert_pos:]
            self._cues = new_cues
            target_row = insert_pos
        else:
            curr = self._cue_list.currentRow()
            target_row = curr + 1 if 0 <= curr < len(self._cues) else len(self._cues)
            self._cues.insert(target_row, group_cue)

        self._refresh_cue_list(keep_selection=False)
        self._cue_list.setCurrentRow(target_row)
        self._commit_undo_point()
        self._mark_modified(True)
        self._status_label.setText(f"Creato Gruppo Scena: '{group_cue.name}'")
        self._auto_save()
        logger.info("[GROUP] Created group #%d '%s'", group_cue.cue_id, group_cue.name)

    @Slot()
    def _ungroup_selected(self) -> None:
        """Dissolve the selected group (or parent of selected child), returning cues to root."""
        if self._live_mode:
            return
        anchor_row, cue = self._anchor_row_and_cue()
        if cue is None:
            return

        target_group: Optional[Cue] = None
        if cue.media_type == MediaType.GROUP:
            target_group = cue
        elif cue.parent_id is not None:
            target_group = next((c for c in self._cues if c.cue_id == cue.parent_id), None)

        if target_group is None:
            return

        if self._undo.is_debounce_active():
            self._commit_undo_point()

        # Detach children
        for c in self._cues:
            if c.parent_id == target_group.cue_id:
                c.parent_id = None

        # Remove group cue
        if target_group in self._cues:
            idx = self._cues.index(target_group)
            self._cues.remove(target_group)
            target_row = min(idx, len(self._cues) - 1)
        else:
            target_row = max(0, len(self._cues) - 1)

        self._refresh_cue_list(keep_selection=False)
        if 0 <= target_row < len(self._cues):
            self._cue_list.setCurrentRow(target_row)
        self._commit_undo_point()
        self._mark_modified(True)
        self._status_label.setText(f"Sciolto Gruppo: '{target_group.name}'")
        self._auto_save()
        logger.info("[GROUP] Ungrouped group #%d", target_group.cue_id)

    @Slot(int)
    def _toggle_group_collapsed(self, row: int) -> None:
        """Toggle collapse/expand for the group at *row*."""
        if not (0 <= row < len(self._cues)):
            return
        cue = self._cues[row]
        if cue.media_type != MediaType.GROUP:
            return

        cue.collapsed = not cue.collapsed

        # Apply visibility to both tables
        for r, c in enumerate(self._cues):
            if c.parent_id == cue.cue_id:
                self._cue_list.setRowHidden(r, cue.collapsed)
                if hasattr(self, "_live_show_panel") and self._live_show_panel is not None:
                    self._live_show_panel.live_table.setRowHidden(r, cue.collapsed)

        # Update table row data
        it_num = self._cue_list.item(row, 0)
        if it_num:
            it_num.setData(ROLE_GROUP_COLLAPSED, cue.collapsed)
        it_name = self._cue_list.item(row, 2)
        if it_name:
            it_name.setData(ROLE_GROUP_COLLAPSED, cue.collapsed)
        self._cue_list.viewport().update()

        # Update button text in inspector if group is active
        if self._selected_cue() is cue:
            if cue.collapsed:
                self._inspector.btn_group_collapse_toggle.setText("▼ Espandi Gruppo in Scaletta")
            else:
                self._inspector.btn_group_collapse_toggle.setText("▶ Collassa Gruppo in Scaletta")

        self._sync_live_view()

    @Slot()
    def _toggle_group_collapse_from_inspector(self) -> None:
        anchor_row, cue = self._anchor_row_and_cue()
        if cue and cue.media_type == MediaType.GROUP:
            self._toggle_group_collapsed(anchor_row)

    @Slot(int)
    def _on_remove_child_from_group(self, child_cue_id: int) -> None:
        """Remove a child cue from its parent group and place it outside."""
        child = next((c for c in self._cues if c.cue_id == child_cue_id), None)
        if child is None or child.parent_id is None:
            return
        parent_group = next((c for c in self._cues if c.cue_id == child.parent_id), None)
        if self._undo.is_debounce_active():
            self._commit_undo_point()
        child.parent_id = None
        if parent_group is not None:
            siblings = [c for c in self._cues if c.parent_id == parent_group.cue_id and c != child]
            self._cues.remove(child)
            if siblings:
                last_sibling_idx = self._cues.index(siblings[-1])
                self._cues.insert(last_sibling_idx + 1, child)
            else:
                p_idx = self._cues.index(parent_group)
                self._cues.insert(p_idx + 1, child)
        target_row = self._cues.index(child)
        self._refresh_cue_list(keep_selection=False, select_row=target_row)
        self._commit_undo_point()
        self._mark_modified(True)
        anchor_row, group_cue = self._anchor_row_and_cue()
        if group_cue and group_cue.media_type == MediaType.GROUP:
            children = [c for c in self._cues if c.parent_id == group_cue.cue_id]
            self._inspector.load_group_children(children, group_cue)
        self._status_label.setText(f"Estratta cue '{child.name}' dal gruppo (spostata all'esterno)")

    @Slot()
    def _extract_selected_from_group(self) -> None:
        """Extract the selected cue(s) from their parent group."""
        sel_cues = [c for c in self._selected_cues() if c.parent_id is not None]
        if not sel_cues:
            anchor_row, cue = self._anchor_row_and_cue()
            if cue and cue.parent_id is not None:
                sel_cues = [cue]
        if not sel_cues:
            return
        for c in sel_cues:
            self._on_remove_child_from_group(c.cue_id)

    @Slot()
    def _on_ctrl_shift_g(self) -> None:
        """Ungroup if group is selected, or extract if child cue is selected."""
        anchor_row, cue = self._anchor_row_and_cue()
        if cue is None:
            return
        if cue.media_type == MediaType.GROUP:
            self._ungroup_selected()
        elif cue.parent_id is not None:
            self._extract_selected_from_group()

    @Slot(str)
    def _set_group_mode(self, mode: str) -> None:
        """Update group execution mode across selected group cue(s)."""
        sel_cues = [c for c in self._selected_cues() if c.media_type == MediaType.GROUP]
        if not sel_cues:
            anchor_row, cue = self._anchor_row_and_cue()
            if cue and cue.media_type == MediaType.GROUP:
                sel_cues = [cue]
        if not sel_cues:
            return

        if self._undo.is_debounce_active():
            self._commit_undo_point()

        for c in sel_cues:
            c.group_mode = mode

        self._refresh_rows_in_place(list(range(len(self._cues))))
        anchor_row, cue = self._anchor_row_and_cue()
        if cue:
            self._inspector.set_layer_conflict(self._layer_conflicts.get(cue.cue_id))
        self._commit_undo_point()
        self._mark_modified(True)
        self._sync_live_view()
        self._status_label.setText(f"Modalità Gruppo impostata a: {mode}")

    @Slot()
    def _on_open_group_timeline(self) -> None:
        """Open the dedicated 3-layer Studio Timeline Arranger Dialog for the selected group."""
        if self._live_mode:
            return
        anchor_row, cue = self._anchor_row_and_cue()
        if not cue:
            return
        group_cue = (
            cue if cue.media_type == MediaType.GROUP
            else next((c for c in self._cues if c.cue_id == cue.parent_id), None)
        )
        if not group_cue or group_cue.media_type != MediaType.GROUP:
            return

        child_cues = [c for c in self._cues if c.parent_id == group_cue.cue_id]
        if not child_cues:
            QMessageBox.information(
                self,
                "Studio Timeline Gruppo",
                f"Il gruppo '{group_cue.name}' non contiene ancora file multimediali.\n\n"
                "Aggiungi prima delle tracce audio, video o immagini al gruppo nella scaletta principale\n"
                "per poterle allineare e sincronizzare sulla timeline a 3 layer.",
            )
            return

        dialog = GroupTimelineStudioDialog(group_cue, child_cues, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._commit_undo_point()
            self._mark_modified(True)
            self._refresh_cue_list(keep_selection=True)
            self._update_inspector(group_cue)
            self._status_label.setText(
                f"Studio Timeline: Gruppo '{group_cue.name}' sincronizzato con successo ({len(child_cues)} file allineati sui layer)"
            )

    # ── EBU R128 Loudness Normalization & Jam / Contest Mode ──────────

    @Slot(bool)
    def _set_jam_mode(self, enabled: bool) -> None:
        """Toggle global Jam / Contest EBU R128 auto-gain normalization mode."""
        enabled = bool(enabled)
        if self._jam_mode_active == enabled:
            return
        self._jam_mode_active = enabled
        if hasattr(self, "_act_jam_mode"):
            self._act_jam_mode.blockSignals(True)
            self._act_jam_mode.setChecked(enabled)
            self._act_jam_mode.blockSignals(False)
        if hasattr(self, "_btn_jam_mode"):
            self._btn_jam_mode.blockSignals(True)
            self._btn_jam_mode.set_active(enabled, silent=True)
            self._btn_jam_mode.blockSignals(False)

        if enabled:
            self._status_label.setText("MODALITÀ JAM / CONTEST ATTIVA — Auto-Gain EBU R128 (-16 LUFS) abilitato su tutti i canali")
            for c in self._cues:
                if c.media_type in (MediaType.VIDEO, MediaType.AUDIO) and c.loudness_lufs is None:
                    self._launch_loudness_scan(c)
        else:
            self._status_label.setText("MODALITÀ JAM / CONTEST DISATTIVATA — Ripristinati livelli originali delle cue")

        # Hot-update active live / test players
        for c in self._cues:
            if c.status == CueStatus.LIVE or self._selected_cue() is c:
                self.live_automation_updated.emit(c)

    def _launch_loudness_scan(self, cue: Cue) -> None:
        """Launch background EBU R128 loudness analysis for *cue*."""
        if not (cue.media_type in (MediaType.VIDEO, MediaType.AUDIO) and os.path.isfile(cue.file_path)):
            return

        def _on_finished(fpath: str, lufs: float, peak: float, gain_db: float) -> None:
            if cue.file_path == fpath:
                cue.loudness_lufs = lufs
                cue.true_peak_dbfs = peak
                cue.auto_gain_db = gain_db
                sign = "+" if gain_db > 0 else ""
                if self._selected_cue() is cue:
                    self._inspector.set_loudness_result(lufs, peak, gain_db)
                    self._status_label.setText(
                        f"Analisi Loudness per '{cue.name}': {lufs:.1f} LUFS (Peak {peak:.1f} dBFS → Gain {sign}{gain_db:.1f} dB)"
                    )
                if cue.normalize_audio or self._jam_mode_active:
                    self.live_automation_updated.emit(cue)

        def _on_error(fpath: str, err: str) -> None:
            if cue.file_path == fpath and self._selected_cue() is cue:
                self._status_label.setText(f"Analisi Loudness non riuscita per '{cue.name}': {err}")

        scanner = LoudnessScanner(cue.file_path, target_lufs=-16.0)
        scanner.signals.finished.connect(_on_finished)
        scanner.signals.error.connect(_on_error)
        self._thread_pool.start(scanner)

    @Slot()
    def _on_scan_loudness_requested(self) -> None:
        cue = self._selected_cue()
        if cue is not None and cue.media_type in (MediaType.VIDEO, MediaType.AUDIO):
            self._status_label.setText(f"Scansione Loudness EBU R128 per '{cue.name}' in corso...")
            self._launch_loudness_scan(cue)

    @Slot(bool)
    def _on_normalize_cue_toggled(self, checked: bool) -> None:
        cue = self._selected_cue()
        if cue is None or cue.media_type not in (MediaType.VIDEO, MediaType.AUDIO):
            return
        cue.normalize_audio = checked
        if checked and cue.loudness_lufs is None:
            self._status_label.setText(f"Calcolo guadagno EBU R128 per '{cue.name}'...")
            self._launch_loudness_scan(cue)
        else:
            self.live_automation_updated.emit(cue)
        self._mark_modified(True)

    @Slot()
    def _on_optimize_dynamics_requested(self) -> None:
        cue = self._selected_cue()
        if cue is None or cue.media_type not in (MediaType.VIDEO, MediaType.AUDIO):
            return
        if not os.path.isfile(cue.file_path):
            self._status_label.setText("File sorgente non trovato per l'ottimizzazione dinamica.")
            return

        self._status_label.setText(f"Compressione dinamica e normalizzazione EBU R128 per '{cue.name}' in corso...")

        def _on_finished(orig_path: str, opt_path: str) -> None:
            if cue.file_path == orig_path or (cue.original_file_path and cue.original_file_path == orig_path):
                if cue.original_file_path is None:
                    cue.original_file_path = orig_path
                cue.file_path = opt_path
                cue.loudness_lufs = -16.0
                cue.true_peak_dbfs = -1.5
                cue.auto_gain_db = 0.0
                cue.normalize_audio = True

                if self._selected_cue() is cue:
                    self._inspector.set_loudness_result(-16.0, -1.5, 0.0)
                    self._inspector.btn_restore_original.setVisible(True)
                    self._request_waveform(cue)
                    self._render_cue_in_preview(cue, load_image=False)

                self._status_label.setText(f"Dinamica ottimizzata con successo per '{cue.name}' (-16 LUFS, Limiter -1.5 dBFS)")
                self._mark_modified(True)
                self.live_automation_updated.emit(cue)

        def _on_error(orig_path: str, err: str) -> None:
            self._status_label.setText(f"Errore ottimizzazione dinamica: {err}")

        optimizer = DynamicsOptimizer(cue.file_path, target_lufs=-16.0)
        optimizer.signals.finished.connect(_on_finished)
        optimizer.signals.error.connect(_on_error)
        self._thread_pool.start(optimizer)

    @Slot()
    def _on_restore_original_requested(self) -> None:
        cue = self._selected_cue()
        if cue is None or not cue.original_file_path:
            return
        cue.file_path = cue.original_file_path
        cue.original_file_path = None
        cue.loudness_lufs = None
        cue.true_peak_dbfs = None
        cue.auto_gain_db = 0.0
        cue.normalize_audio = False

        self._inspector.btn_restore_original.setVisible(False)
        self._inspector.lbl_loudness_info.setText("📊 Loudness: Non analizzato")
        self._inspector.lbl_loudness_info.setStyleSheet(
            "background-color: #0b111a; color: #94a3b8; border: 1px solid #1e293b; "
            "border-radius: 4px; font-family: monospace; font-size: 10px; padding: 4px 6px;"
        )
        self._inspector.chk_normalize_cue.blockSignals(True)
        self._inspector.chk_normalize_cue.setChecked(False)
        self._inspector.chk_normalize_cue.blockSignals(False)

        self._request_waveform(cue)
        self._render_cue_in_preview(cue, load_image=False)
        self._status_label.setText(f"File originale ripristinato per '{cue.name}'")
        self._mark_modified(True)
        self.live_automation_updated.emit(cue)

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
            analyzer = WaveformAnalyzer(cue.file_path, max(3200, self._waveform.width() * 6))
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
