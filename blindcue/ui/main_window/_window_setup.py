"""Window setup mixin for MainWindow."""

from __future__ import annotations

from ui.main_window._common import *  # noqa: F403,F401,F405
from ui.main_window._common import (  # noqa: F401
    _AutosaveWorker,
    _DEFAULT_TOP_RATIOS,
    _MEDIA_ICONS,
    _demote_live_on_layer,
)


class _WindowSetupMixin:
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
                    color: #ffffff;
                    border: 2px solid #ffffff;
                    border-radius: 6px;
                    font-size: 18px;
                    font-weight: bold;
                }}
                QPushButton:hover {{ background-color: {t.button_hover_bg}; border-color: #ffffff; color: #ffffff; }}
                QPushButton:pressed {{ background-color: {t.input_bg}; }}
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
        # Dedicated single-thread pool so autosave disk I/O never blocks the GUI
        # thread and never competes with waveform/loudness workers.  A single
        # thread also serializes writes to the autosave file.
        self._autosave_pool = QThreadPool(self)
        self._autosave_pool.setMaxThreadCount(1)
        self._autosave_in_progress: bool = False
        self._autosave_retry_pending: bool = False
        self._autosave_worker: _AutosaveWorker | None = None

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
        QShortcut(QKeySequence(Qt.Key.Key_F7), self, self._open_surface_mapping_dialog)
        QShortcut(QKeySequence("Shift+F7"), self, lambda: self._toggle_calibration_guides(not self._output.is_calibration_guides_visible()))

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
