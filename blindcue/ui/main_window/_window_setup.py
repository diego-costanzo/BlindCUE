"""Window setup mixin for MainWindow."""

from __future__ import annotations

import time

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

        app_icon = QApplication.windowIcon()
        if not app_icon.isNull():
            self.setWindowIcon(app_icon)
        elif DEFAULT_LOGO_PATH.is_file():
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
        if hasattr(self, "_live_status") and self._live_status is not None:
            if hasattr(self._live_status, "refresh_theme_styles"):
                self._live_status.refresh_theme_styles()
            self._live_status.update()
        if hasattr(self, "_inspector") and self._inspector is not None:
            if hasattr(self._inspector, "refresh_theme_styles"):
                self._inspector.refresh_theme_styles()
            self._inspector.update()

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

    def _go_label(self) -> tuple[str, bool]:
        """What the next GO will do, in words, and whether that is not a plain start.

        The state is said in text and an icon first (colour comes last and is
        never red), before the cue name: a long name is cut, the state never.
        Order: keyboard elsewhere > the cue cannot play > GO held by an
        exclusive cue > the cue already plays (GO restarts it) > ready.
        """
        if not self._cues:
            return "GO (Next Cue) — [ SPAZIO ]", False
        row = self._go_target_index()
        cue = self._cues[row]
        target = f"{format_cue_ref(row, cue)} '{cue.name}'"
        if getattr(self, "_focus_lost_shown", False):
            return f"⌨ Clicca qui: la tastiera è altrove — GO: {target}", True
        # The file itself, not the status: a failed GO leaves the cue LOADED.
        if cue.status == CueStatus.OFFLINE or (
            cue.media_type.has_file and not os.path.isfile(cue.file_path or "")
        ):
            return f"⚠ File mancante — GO: {target}", True
        blocker = self._exclusive_blocker()
        if blocker is not None:  # _manual_go_allowed refuses every GO meanwhile
            return f"⏳ GO in attesa (Ctrl+Spazio per forzare): '{blocker.name}' è esclusiva", True
        if cue.status == CueStatus.LIVE:
            return f"↻ Già in onda, riparte — GO: {target}", True
        return f"▶ GO: {target}", False

    def _update_go_button_text(self) -> None:
        """Both GO buttons (design view and LIVE) say what the next GO will do."""
        text, warn = self._go_label()
        if (text, warn) == getattr(self, "_go_button_source", None):
            return
        self._go_button_source = (text, warn)
        btn = getattr(self, "_btn_go", None)
        if btn is not None:
            btn.set_full_text(text)
        if hasattr(self, "_live_show_panel"):
            self._live_show_panel.set_go_label(text, warn)

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
        # Note: Ctrl+B (Blackout), F5 (Live Mode), F7 (Surface Mapping),
        # Shift+F7 (Calibration Guides), F8 (Remote) and Space (GO) are already
        # owned by QActions in the menu bar. Registering QShortcuts for the same
        # keys causes Qt "Ambiguous shortcut overload" and silently blocks them.
        QShortcut(QKeySequence(Qt.Key.Key_Delete), self, self._on_delete_cue)
        QShortcut(QKeySequence(Qt.Key.Key_Backspace), self, self._on_delete_cue)
        QShortcut(QKeySequence("Alt+Up"), self, self._on_move_up)
        QShortcut(QKeySequence("Alt+Down"), self, self._on_move_down)
        QShortcut(QKeySequence(Qt.Key.Key_I), self, lambda: self._on_snap_shortcut(True))
        QShortcut(QKeySequence(Qt.Key.Key_O), self, lambda: self._on_snap_shortcut(False))
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, self._on_escape_pressed)
        QShortcut(QKeySequence("Ctrl+L"), self, self._enter_show_from_key)  # enters only
        # Master volume of the show (C2a step 3); W3 of the accessibility review.
        QShortcut(QKeySequence("Ctrl+Up"), self, lambda: self._nudge_master(0.05))
        QShortcut(QKeySequence("Ctrl+Down"), self, lambda: self._nudge_master(-0.05))
        QShortcut(QKeySequence("Ctrl+M"), self, self._toggle_master_mute)
        # Slides: previous / next picture, only while the show's list has the keyboard
        # (text fields keep Ctrl+arrows for words).
        table = self._live_show_panel.live_table
        QShortcut(QKeySequence("Ctrl+Right"), table, lambda: self._go_picture(1),
                  context=Qt.ShortcutContext.WidgetShortcut)
        QShortcut(QKeySequence("Ctrl+Left"), table, lambda: self._go_picture(-1),
                  context=Qt.ShortcutContext.WidgetShortcut)
        for key in ("Return", "Enter"):  # the OK of a cue waiting for confirmation (1.9)
            QShortcut(QKeySequence(key), table, self._confirm_gate, context=Qt.ShortcutContext.WidgetShortcut)
        QShortcut(QKeySequence("Ctrl+G"), self, self._on_add_group)
        QShortcut(QKeySequence("Ctrl+Shift+G"), self, self._on_ctrl_shift_g)
        self._install_focus_watch()

    def _install_focus_watch(self) -> None:
        """Warn in LIVE mode when the keyboard is not on the director window.

        Space and Esc only reach BlindCue while this window (or one of its
        dialogs) is active; a click on the projector output or on another
        program silently takes them away.
        """
        self._focus_lost_shown = False
        self._focus_check_timer = QTimer(self)
        self._focus_check_timer.setSingleShot(True)
        self._focus_check_timer.setInterval(300)
        self._focus_check_timer.timeout.connect(self._update_focus_warning)
        app = QApplication.instance()
        if app is not None:
            app.focusWindowChanged.connect(self._schedule_focus_check)
            app.applicationStateChanged.connect(self._schedule_focus_check)

    def _schedule_focus_check(self, *_args: object) -> None:
        # Debounced: focus flips several times while dialogs open and close.
        self._focus_check_timer.start()

    def _keyboard_on_director(self) -> bool:
        """True when the active window is this one or a dialog owned by it."""
        widget = QApplication.activeWindow()
        while widget is not None:
            if widget is self:
                return True
            widget = widget.parentWidget()
        return False

    def _update_focus_warning(self) -> None:
        lost = bool(getattr(self, "_live_mode", False)) and not self._keyboard_on_director()
        if lost == getattr(self, "_focus_lost_shown", False):
            return
        self._focus_lost_shown = lost
        self._update_go_button_text()
        if hasattr(self, "_live_show_panel"):
            self._live_show_panel.set_focus_warning(lost)
        if lost:
            self._status_label.setText(
                "⚠ Tastiera non sul pannello regia: SPAZIO ed ESC non arrivano a BlindCue"
            )
            logger.warning("[FOCUS] Director window lost keyboard focus during LIVE")
            if hasattr(self, "_earcon_mgr"):
                self._earcon_mgr.play_alert()  # heard while looking at the stage (W41)
        else:
            logger.info("[FOCUS] Keyboard back on the director window")

    def _is_text_input_focused(self) -> bool:
        focus_w = QApplication.focusWidget()
        if isinstance(focus_w, (QLineEdit, QAbstractSpinBox, QComboBox, QPlainTextEdit)):
            return True
        return hasattr(self, "_cue_list") and self._cue_list.state() == QAbstractItemView.State.EditingState

    @Slot()
    def _on_escape_pressed(self) -> None:
        if hasattr(self, "_cue_list") and self._cue_list.state() == QAbstractItemView.State.EditingState:
            return
        if not self._live_mode and self._is_text_input_focused():
            # Esc in an editor field only leaves the field: it never counts
            # towards PANIC there (people press Esc to back out of typing).
            self._last_esc_press_mono = 0.0
            self._cue_list.setFocus()
            return
        # Esc twice is PANIC in every view: the emergency key must not depend
        # on the mode (a rehearsal run from the editor needs it too). In the
        # editor only while something plays or waits: there is nothing to
        # stop otherwise, and PANIC would black out the projector.
        now = time.monotonic()
        last = getattr(self, "_last_esc_press_mono", 0.0)
        if last > 0.0 and (now - last) <= 0.6 and (self._live_mode or self._show_running()):
            self._last_esc_press_mono = 0.0
            self._on_panic()
            return
        self._last_esc_press_mono = now
        if self._live_mode:
            self._status_label.setText(
                "⚠ Premi di nuovo ESC entro 0.6s per PANIC (0ms) — oppure clicca il pulsante PANIC"
            )
            self.announce(self._status_label.text(), assertive=True)
            return
        # In the editor a single Esc still stops the preview.
        if hasattr(self, "_btn_test_stop"):
            self._btn_test_stop.click()
        if self._show_running():
            self._status_label.setText("⚠ Premi di nuovo ESC entro 0.6s per PANIC (0ms)")
