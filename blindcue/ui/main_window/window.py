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
from ui.main_window._undo_go import _UndoGoMixin
from ui.main_window._readiness import _ReadinessMixin
from ui.main_window._now_playing import _NowPlayingMixin
from ui.main_window._announce import _AnnounceMixin
from ui.main_window._rehearsal import _RehearsalMixin
from ui.main_window._pin import _PinMixin
from ui.main_window._variants import _VariantsMixin
from ui.main_window._effects import _EffectsMixin
from ui.main_window._assistant import _AssistantMixin
from ui.main_window._relative import _RelativeMixin
from ui.main_window._versions import _VersionsMixin
from ui.main_window._rehearse_from import _RehearseFromMixin
from ui.main_window._countdown import _CountdownMixin
from ui.main_window._clock_plan import _ClockPlanMixin
from ui.main_window._export import _ExportMixin
from ui.main_window._layout_copy import _LayoutCopyMixin
from ui.main_window._markers import _MarkersMixin
from ui.main_window._renumber import _RenumberMixin
from ui.main_window._search import _SearchMixin
from ui.main_window._show_import import _ShowImportMixin
from ui.main_window._show_info import _ShowInfoMixin
from ui.main_window._key_map import _KeyMapMixin
from ui.main_window._quick_start import _QuickStartMixin
from ui.main_window._relink import _RelinkMixin
from ui.main_window._history import _HistoryMixin
from ui.main_window._edit_cue import _EditCueMixin
from ui.main_window._settings_transfer import _SettingsTransferMixin
from ui.main_window._slideshow import _SlideshowMixin


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
    _UndoGoMixin,
    _ReadinessMixin,
    _NowPlayingMixin,
    _AnnounceMixin,
    _RehearsalMixin,
    _PinMixin,
    _VariantsMixin,
    _EffectsMixin,
    _AssistantMixin,
    _RelativeMixin,
    _VersionsMixin,
    _RehearseFromMixin,
    _CountdownMixin,
    _ClockPlanMixin,
    _ExportMixin,
    _LayoutCopyMixin,
    _MarkersMixin,
    _RenumberMixin,
    _SearchMixin,
    _ShowImportMixin,
    _ShowInfoMixin,
    _KeyMapMixin,
    _QuickStartMixin,
    _RelinkMixin,
    _HistoryMixin,
    _EditCueMixin,
    _SettingsTransferMixin,
    _SlideshowMixin,
    QMainWindow,
):
    """Director / Control Panel."""

    cue_fired = Signal(object)                     # emits Cue
    cue_preview_requested = Signal(object)         # emits Cue to load in preview
    layer_clear_requested = Signal(int)            # emits layer (1, 2, or 3)
    action_cancel_requested = Signal(int)          # emits cue_id of a deleted action cue
    undo_go_requested = Signal(object)             # list[UndoStep]: take back the last GO
    release_loop_requested = Signal(int)           # runtime layer: its loop ends after this pass
    layer_trim_requested = Signal(int, float)      # runtime layer, operator level correction 0..1
    layer_opacity_requested = Signal(int, float)   # 2.4: runtime layer, opacity 0..1 (rehearse from here)
    layer_stop_requested = Signal(int)             # runtime layer: stop at once (rehearsal card)
    card_fade_requested = Signal(int)              # runtime layer: fade the card's cue only
    layer_cancel_start_requested = Signal(int)     # runtime layer: the waiting start never happens
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
    master_gain_changed = Signal(float)                  # master volume × mute, 0..1 (all live players)
    pause_all_set = Signal(bool)                         # emits idempotent global pause/resume state

    def __init__(self, output_window: OutputWindow,
                 parent: QWidget | None = None,
                 secondary_output_window: OutputWindow | None = None) -> None:
        """Wire the main window to output A and, when present, to output B."""
        super().__init__(parent)
        from ui import wheel_guard

        wheel_guard.install()  # the wheel scrolls panels, never changes a value by accident
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
        self._layer0_video: str | None = None
        self._layer0_kind: str = "black"     # evaluation #9: black / image / video / pattern
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
        # GO target when LIVE was last left (cue_id); None for a freshly loaded show.
        self._live_resume_id: int | None = None
        # Times of the cues on air: fed by the layer reports, drawn at 10 Hz
        # into the time cells only (see _on_live_clock_tick).
        self._live_clocks = LiveClocks()
        self._live_fractions: dict[int, tuple[float, bool]] = {}
        self._live_clock_timer = QTimer(self)
        self._live_clock_timer.setInterval(100)
        self._live_clock_timer.timeout.connect(self._on_live_clock_tick)
        # Cues started in this run of the show (✓ in the LIVE list); emptied
        # by "from the top" and when another show is loaded.
        self._played_ids: set[int] = set()
        # cue_id -> order number of its last start (see trigger_auto_follow_from)
        self._fired_at: dict[int, int] = {}
        self._fire_seq = 0
        # Master volume of the show: 100 % at every start, never saved.
        self._master_level: float = 1.0
        self._master_muted: bool = False
        # "Loop Scena" groups a release action reached: they end after this pass.
        self._released_groups: set[int] = set()
        self._undo_go_setup()  # Undo the last GO (stage 1.18)
        self._paused_slots: set[int] = set()  # runtime layers paused one by one (Now playing)
        self._trims: dict[int, float] = {}    # runtime layer -> operator level correction
        self._ramps: dict[int, tuple[str, float]] = {}  # runtime layer -> (ramp text, ends at)
        self._held_auto_go: set[int] = set()  # cues whose Auto-GO waits for a GO instead
        self._rehearsal = False               # the show's screen in the rehearsal mode
        self._slot_override: dict[int, int] = {}  # cue_id -> spare player it borrowed (phase D)
        self._rehearsal_before: dict = {}     # (cue_id, field) -> value before the rehearsal
        self._rehearsal_undo: list = []       # (cue_id, field, before): Ctrl+Z in the rehearsal
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
        self._readiness_setup()  # "Before the show" page (stage 1 C2a step 7)
        self._now_playing_setup()  # right column of the show (stage 1 C2a step 8)
        self._rehearsal_setup()  # rehearsal drawer and tools (stage 1 C2a step 9)
        self._pin_setup()  # exit PIN of the show (stage 1 C2a step 10)
        self._relative_setup()  # cues starting relative to another cue (stage 2, 2.1)
        self._versions_setup()  # cues on/off and versions of the show (stage 2, 2.3)
        self._countdown_setup()  # countdown and run log (stage 2, 2.5)
        self._clock_setup()  # cues at a time of day (stage 2, 2.6)
        self._markers_setup()  # markers in a file, start on a marker (stage 2, 2.7)
        self._search_setup()  # Ctrl+F (stage 2, 2.8)
        self._layout_setup()  # copy / paste the picture layout (stage 4, 4.4)
        self._slideshow_setup()  # photos to music (stage 4, 4.3)
        self._effects_setup()  # effects on demand, keys and tiles (stage 1 phase D)
        self._keymap_setup()  # extra keys and a presenter remote (stage 5, 5.7-5.8)
        self._relink_setup()  # choose a cue's file, find missing files (stage 5, 5.10)
        self._edit_cue_setup()  # the "Edit cue" window (evaluation 2026-11-24)
        self._apply_layer0("black")  # the default placeholder (evaluation #9); a show sets its own
        self._assistant_setup()  # AI assistant link, off until allowed (stage 1M, M2)
        self._setup_shortcuts()
        self._update_inspector(None)
        self._build_status_bar()
        self._set_panels_locked(True, announce=False)
        self._variants_setup()  # Lite / Medium / Full of the Preparation view (stage 1 C2b)
        self._setup_autosave()
        self._undo.set_committed_state(self._cues, self._current_index)

        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)
        # The crash-recovery question is scheduled by main() once the whole
        # boot is done (see the end of main.main()).

