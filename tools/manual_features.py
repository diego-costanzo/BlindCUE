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
}


def present(root: Path = ROOT) -> set[str]:
    """Names of the features found in the code under *root*."""
    found = set()
    for name, (rel, needle) in FEATURES.items():
        path = root / rel
        if path.is_file() and (needle is None or needle in path.read_text(encoding="utf-8")):
            found.add(name)
    return found
