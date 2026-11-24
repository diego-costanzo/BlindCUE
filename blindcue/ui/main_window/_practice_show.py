"""File → "Practice show" (stage 5, item 5.17) mixin for MainWindow.

Copies the practice media next to a new show in Documents\\BlindCue,
builds the cues (engine/practice_show.py) and saves the show, so the teacher
can learn and rehearse on it and change it freely.
"""

from __future__ import annotations

import shutil

from i18n import tr
from ui.main_window._common import *  # noqa: F403,F401,F405
from ui.theme import ASSETS_DIR


class _PracticeShowMixin:
    def _open_practice_show(self) -> bool:
        from engine.practice_show import MEDIA_FILES, practice_cues
        from engine.show_mode import EDIT_LIST
        from engine.text_render import render_text_png
        from ui import dialog_dirs

        if not self._change_allowed(EDIT_LIST):
            return False
        title = tr("Spettacolo di prova")
        folder = Path(dialog_dirs.show_dir()) / title
        media = folder / "media"
        source = ASSETS_DIR / "practice"
        try:
            media.mkdir(parents=True, exist_ok=True)
            for name in MEDIA_FILES:
                target = media / name
                if not target.is_file():  # the teacher may have edited a copy: never overwritten
                    shutil.copy2(source / name, target)
        except OSError as exc:
            QMessageBox.warning(self, title, tr("Impossibile preparare lo spettacolo di prova: {}").format(exc))
            return False
        if not self._on_new_show():
            return False
        self._cues = practice_cues(media, render_text_png, tr)
        self._refresh_cue_list(keep_selection=False)
        self._cue_list.setCurrentRow(0)
        self._reset_undo_history()
        path = folder / f"{title}.blindcue"
        if self._do_save(str(path)):
            self._current_project_path = str(path)
        self._status_label.setText(tr("Spettacolo di prova pronto: entra nella Prova (Maiusc+F5) e premi Spazio"))
        return True
