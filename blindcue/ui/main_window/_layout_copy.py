"""Copy / paste the picture layout of a cue (stage 4, item 4.4) mixin for MainWindow.

Right-click a picture or video: "Copy picture layout" keeps its position,
size, crop, rotation, aspect ratio, mask and surface; "Paste layout onto the
selected" gives the same layout to every selected picture and video (one
Ctrl+Z). Handy for a series of photos that must sit in the same frame.
"""

from __future__ import annotations

import copy

from i18n import tr

from ui.main_window._common import *  # noqa: F403,F401,F405

LAYOUT_FIELDS = ("position_x", "position_y", "scale", "crop", "rotation", "aspect_ratio",
                 "mask_polygon", "mask_feather", "surface_id")
_VISUAL = (MediaType.IMAGE, MediaType.VIDEO)


def layout_of(cue: Cue) -> dict:
    return {f: copy.deepcopy(getattr(cue, f)) for f in LAYOUT_FIELDS}


class _LayoutCopyMixin:
    def _layout_setup(self) -> None:
        self._copied_layout: dict | None = None
        self._cue_list.layout_copy_requested.connect(self._copy_layout)
        self._cue_list.layout_paste_requested.connect(self._paste_layout)

    def _copy_layout(self) -> None:
        cue = self._selected_cue()
        if cue is None or cue.media_type not in _VISUAL:
            self._status_label.setText(tr("Layout: scegli un'immagine o un video"))
            return
        self._copied_layout = layout_of(cue)
        self._status_label.setText(tr("Layout copiato da '{}'").format(cue.name))

    def _paste_layout(self) -> None:
        from engine.show_mode import EDIT_CUE

        if self._copied_layout is None:
            self._status_label.setText(tr("Prima copia il layout di un'immagine o di un video"))
            return
        # Captions are full-frame pictures drawn by the program: a photo's crop would cut them.
        targets = [c for c in self._selected_cues() if c.media_type in _VISUAL and not c.text_spec]
        if not targets or not self._change_allowed(EDIT_CUE):
            return
        if self._undo.is_debounce_active():
            self._commit_undo_point()
        for cue in targets:
            for field_name, value in self._copied_layout.items():
                setattr(cue, field_name, copy.deepcopy(value))
        self._commit_undo_point()
        self._mark_modified(True)
        rows = [i for i, c in enumerate(self._cues) if c in targets]
        self._refresh_rows_in_place(rows)
        anchor = self._selected_cue()
        if anchor is not None:
            self._update_inspector(anchor)
            if anchor.media_type in _VISUAL:
                self._render_cue_in_preview(anchor, load_image=(anchor.media_type == MediaType.VIDEO))
        if getattr(self, "_live_mirror_active", False):
            self._mirror_active_cue_to_live()  # the projector shows the new layout at once
        self._status_label.setText(tr("Layout incollato su {} cue").format(len(targets)))
