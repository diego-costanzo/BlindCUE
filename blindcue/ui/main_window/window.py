"""Director / Control Panel – main window of BlindCue.

Composes modular UI panels (cue list, Pre-Viz sandbox, Cue Inspector,
Waveform, Live Output Status, Drop Zone) and coordinates show playback,
Undo/Redo, Live Mirror, and project persistence on the primary monitor.
The implementation is split across small mixin modules in this package.
"""

from __future__ import annotations

from ui.main_window._common import *  # noqa: F403,F401,F405
from ui.main_window._common import (  # noqa: F401
    _AutosaveWorker,
    _DEFAULT_TOP_RATIOS,
    _MEDIA_ICONS,
    _demote_live_on_layer,
)

from ui.main_window._window_setup import _WindowSetupMixin
from ui.main_window._undo import _UndoRedoMixin
from ui.main_window._menu import _MenuMixin
from ui.main_window._layout import _LayoutMixin
from ui.main_window._cue_table import _CueTableMixin
from ui.main_window._remote import _RemoteMixin
from ui.main_window._waveform import _WaveformMixin
from ui.main_window._inspector import _InspectorMixin
from ui.main_window._envelope import _EnvelopeMixin
from ui.main_window._previz import _PrevizMixin
from ui.main_window._live_layer import _LiveLayerMixin
from ui.main_window._layer0 import _Layer0Mixin
from ui.main_window._selection import _SelectionMixin
from ui.main_window._transport import _TransportMixin
from ui.main_window._cue_manip import _CueManipMixin
from ui.main_window._groups import _GroupsMixin
from ui.main_window._loudness import _LoudnessMixin
from ui.main_window._persistence import _PersistenceMixin
from ui.main_window._waveform_worker import _WaveformWorkerMixin
from ui.main_window._preview import _PreviewMixin
from ui.main_window._actions import _ActionsMixin


class MainWindow(
    _WindowSetupMixin,
    _UndoRedoMixin,
    _MenuMixin,
    _LayoutMixin,
    _CueTableMixin,
    _RemoteMixin,
    _WaveformMixin,
    _InspectorMixin,
    _EnvelopeMixin,
    _PrevizMixin,
    _LiveLayerMixin,
    _Layer0Mixin,
    _SelectionMixin,
    _TransportMixin,
    _CueManipMixin,
    _GroupsMixin,
    _LoudnessMixin,
    _PersistenceMixin,
    _WaveformWorkerMixin,
    _PreviewMixin,
    _ActionsMixin,
    QMainWindow,
):
    """Director / Control Panel."""

    cue_fired = Signal(object)                     # emits Cue
    cue_preview_requested = Signal(object)         # emits Cue to load in preview
    layer_clear_requested = Signal(int)            # emits layer (1, 2, or 3)
    action_cancel_requested = Signal(int)          # emits cue_id of a deleted action cue
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
    fade_all_requested = Signal(float)                   # emits Fade All duration in seconds
    pause_all_toggled = Signal()                         # emits global Show Pause/Resume toggle
    pause_all_set = Signal(bool)                         # emits idempotent global pause/resume state

    def __init__(self, output_window: OutputWindow,
                 parent: QWidget | None = None,
                 secondary_output_window: OutputWindow | None = None) -> None:
        """Wire the main window to output A and, when present, to output B."""
        super().__init__(parent)
        self._output = output_window
        # Second independent projector window (output B). It receives the cues
        # whose ``output_target`` is "B"; ``None`` means dual routing is off.
        self._output_b = secondary_output_window
        self._cues: list[Cue] = []
        self._layer_conflicts: dict[int, LayerConflict] = {}
        # True only when the two independent projector outputs are active; when
        # false, cues assigned to output B are projected on output A.
        self._dual_output_active: bool = False
        self._jam_mode_active: bool = False
        self._current_index: int = -1
        # Background analysis (waveform, loudness, dynamics) runs on its own
        # pool: the global one belongs to Qt Multimedia's media loading.
        self._thread_pool = ShowRuntimeGuard.analysis_pool()
        self._test_player = None
        self._device_mgr = None
        self._active_analyzers: set = set()
        self._waveform_cache: dict[str, object] = {}
        self._active_test_duration: float = 0.0
        self._active_section_idx: int = -1
        self._img_previz_elapsed: float = 0.0
        self._img_previz_timer = QTimer(self)
        self._img_previz_timer.setInterval(33)
        self._img_previz_timer.timeout.connect(self._on_img_previz_tick)

        self._project_manager = ProjectManager()
        self._current_project_path: str | None = None
        # True when the current show was saved with its media copied next to it.
        self._project_bundled: bool = False
        if self._output and self._output.get_surfaces():
            self._surfaces = [s.clone() for s in self._output.get_surfaces()]
        else:
            self._surfaces = [create_default_surface()]
        self._layer0_image: str | None = None
        self._is_modified: bool = False
        self._updating_cue_list: bool = False
        self._force_closing: bool = False
        self._live_mirror_active: bool = False
        self._last_mirrored_layer: tuple[Any, int] | None = None
        self._last_selection_sig: tuple | None = None
        self._media_res_cache: dict[str, tuple[int, int]] = {}
        self._known_file_durations: dict[str, float] = {}
        self._live_phase_tags: dict[int, str] = {}
        self._live_mode: bool = False
        self._is_global_paused: bool = False
        self._last_esc_press_mono: float = 0.0
        self._panels_locked: bool = True
        self._top_ratios: tuple[float, float, float] = _DEFAULT_TOP_RATIOS
        self._applying_splitter_layout: bool = False
        self._remote_mgr: Any | None = None

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
        # The crash-recovery question is scheduled by main() once the whole
        # boot is done (see the end of main.main()).

