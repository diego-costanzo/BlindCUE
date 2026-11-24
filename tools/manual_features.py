"""Which optional features does this code base have?

The user manual sources (docs/manual/manual_<lang>.src.html) describe some
features in blocks that are kept only when the feature is in the code:

    <!--IF:crossfade--> ... <!--/IF:crossfade-->       kept when present
    <!--IFNOT:crossfade--> ... <!--/IFNOT:crossfade-->  kept when absent

tools/build_manual.py and tools/manual_screenshots.py use the same list, so
the manual and its screenshots always match the program they ship with.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# feature -> (file inside the repo, text that must appear in it; None = file exists)
FEATURES: dict[str, tuple[str, str | None]] = {
    "version": ("blindcue/version.py", None),
    "text_cues": ("blindcue/engine/text_render.py", None),
    "crossfade": ("blindcue/ui/output_window.py", "def begin_crossfade"),
    "f11": ("blindcue/ui/output_window.py", "Key_F11"),
    "audio_l2": ("blindcue/ui/main_window/_cue_manip.py", "cue.layer = 2"),
    "speakers": ("blindcue/engine/device_manager.py", "def saved_audio_choice"),
    "projector_only": ("blindcue/ui/main_window/_cue_table.py", "def _ensure_director_visible"),
    "go_guard": ("blindcue/ui/main_window/_transport.py", "def _go_guard_allows"),
    "fade_all": ("blindcue/ui/main_window/_transport.py", "def _on_fade_all"),
    "focus_warning": ("blindcue/ui/main_window/_window_setup.py", "def _update_focus_warning"),
    "live_dblclick": ("blindcue/ui/live_show_view.py", "def live_double_click_fires"),
    "exclusive": ("blindcue/models/cue.py", "exclusive: bool"),
    "action_cues": ("blindcue/engine/action_cues.py", None),
    "live_start": ("blindcue/engine/show_engine.py", "def live_start_choices"),
    "esc_everywhere": ("blindcue/ui/main_window/_window_setup.py", "Esc twice is PANIC in every view"),
    "live_times": ("blindcue/engine/live_state.py", None),
    "go_states": ("blindcue/ui/main_window/_window_setup.py", "def _go_label"),
    "insert_after": ("blindcue/engine/show_engine.py", "def insert_position"),
    "pause_go": ("blindcue/engine/show_scheduler.py", "frozen: bool"),
    "urgent_words": ("blindcue/ui/live_show_view.py", "_URGENT_NOTES_RE"),
    "release_scene": ("blindcue/engine/show_engine.py", "released_groups"),
    "drop_on_list": ("blindcue/ui/cue_table.py", "files_dropped = Signal"),
    "mode_tabs": ("blindcue/ui/mode_tabs.py", None),
    "master_volume": ("blindcue/ui/master_volume.py", None),
    "recovery_choice": ("blindcue/ui/main_window/_persistence.py", "Ripeti l'ultima"),
    "last_started": ("blindcue/ui/live_show_view.py", "def set_last_started"),
    "undo_go": ("blindcue/engine/undo_go.py", None),
    "readiness": ("blindcue/engine/readiness.py", None),
    "now_playing": ("blindcue/ui/now_playing.py", None),
    "rehearsal": ("blindcue/ui/rehearsal_drawer.py", None),
    "exit_pin": ("blindcue/ui/pin_bar.py", None),
    "show_list": ("blindcue/models/cue.py", "confirm_start: bool"),
    "view_variants": ("blindcue/ui/main_window/_variants.py", None),
    "fade_others": ("blindcue/models/cue.py", "fade_others: float"),
    "effects": ("blindcue/ui/main_window/_effects.py", None),
    "assistant": ("blindcue/mcp_server/server.py", None),
    "relative_start": ("blindcue/ui/main_window/_relative.py", None),
    "jump_actions": ("blindcue/models/cue.py", "ACTION_GOTO ="),
    "versions": ("blindcue/ui/main_window/_versions.py", None),
    "rehearse_from": ("blindcue/engine/rehearse_from.py", None),
    "countdown": ("blindcue/ui/main_window/_countdown.py", None),
    "clock_plan": ("blindcue/engine/clock_plan.py", None),
    "markers": ("blindcue/ui/main_window/_markers.py", None),
    "search": ("blindcue/ui/main_window/_search.py", None),
    "time_text": ("blindcue/ui/time_text.py", None),
    "new_actions": ("blindcue/models/cue.py", "ACTION_STOPWATCH ="),
    "audio_outputs": ("blindcue/engine/audio_routes.py", None),
    "playlist": ("blindcue/engine/playlist_import.py", None),
    "silence_trim": ("blindcue/engine/silence_trim.py", None),
    "tempo": ("blindcue/models/cue.py", "playback_rate: float"),
    "picture_layout": ("blindcue/ui/main_window/_layout_copy.py", None),
    "slideshow": ("blindcue/ui/main_window/_slideshow.py", None),
    "cue_export": ("blindcue/engine/cue_export.py", None),
    "renumber": ("blindcue/engine/renumber.py", None),
    "show_import": ("blindcue/engine/show_import.py", None),
    "identify_screens": ("blindcue/ui/identify_screens.py", None),
    "preshow": ("blindcue/engine/list_check.py", None),
}


def present(root: Path = ROOT) -> set[str]:
    """Names of the features found in the code under *root*."""
    found = set()
    for name, (rel, needle) in FEATURES.items():
        path = root / rel
        if path.is_file() and (needle is None or needle in path.read_text(encoding="utf-8")):
            found.add(name)
    return found
