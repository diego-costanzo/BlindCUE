"""The start page (stage 5, item 5.16) mixin for MainWindow."""

from __future__ import annotations

from ui.main_window._common import *  # noqa: F403,F401,F405


class _StartPageMixin:
    def _start_page_setup(self) -> None:
        from ui.start_page import SETTINGS_KEY, StartPage

        page = StartPage()
        self._start_page = page
        self._central_stack.addWidget(page)
        page.chk_show.setChecked(QSettings("BlindCue", "BlindCue").value(SETTINGS_KEY, True, type=bool))
        page.show_at_start_toggled.connect(lambda on: QSettings("BlindCue", "BlindCue").setValue(SETTINGS_KEY, bool(on)))
        page.new_requested.connect(lambda: self._start_then(self._on_new_show))
        page.folder_requested.connect(lambda: self._start_then(self._new_show_from_folder))
        page.practice_requested.connect(lambda: self._start_then(self._open_practice_show))
        page.open_requested.connect(lambda: self._start_then(self._on_open_show))
        page.recent_chosen.connect(lambda path: self._start_then(lambda: self.open_show_from_outside(path)))
        page.add_files_requested.connect(lambda: self._start_then(self._on_add_files))
        page.sound_requested.connect(self.open_audio_outputs_dialog)
        page.screens_requested.connect(self._show_screen_numbers)
        page.projector_requested.connect(self.open_device_settings_dialog)
        from ui.help_dialog import show_help

        page.manual_requested.connect(lambda: show_help(self))
        page.list_requested.connect(self._hide_start_page)

    def _start_page_visible(self) -> bool:
        page = getattr(self, "_start_page", None)
        return page is not None and self._central_stack.currentWidget() is page

    def _show_start_page(self) -> None:
        """File → "Start page" and the program's start without a show."""
        if self._live_mode:
            return
        self._start_page.set_recent([*self._pinned_projects(), *[p for p in self._recent_projects()
                                                                 if p not in self._pinned_projects()]])
        self._central_stack.setCurrentWidget(self._start_page)

    def _show_start_page_if_wanted(self) -> None:
        from ui.start_page import SETTINGS_KEY

        if not self._cues and QSettings("BlindCue", "BlindCue").value(SETTINGS_KEY, True, type=bool):
            self._show_start_page()

    def _hide_start_page(self) -> None:
        if self._start_page_visible():
            self._central_stack.setCurrentIndex(0)
            self._cue_list.setFocus()

    def _start_then(self, action) -> None:
        """A choice on the start page: back to the list, then do it."""
        self._hide_start_page()
        action()
