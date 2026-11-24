"""Menu bar & UI Composition mixin for MainWindow."""

from __future__ import annotations

from ui.main_window._common import *  # noqa: F403,F401,F405
from ui.main_window._common import (  # noqa: F401
    _AutosaveWorker,
    _DEFAULT_TOP_RATIOS,
    _MEDIA_ICONS,
    _demote_live_on_layer,
)


class _MenuMixin:
    def _build_menu_bar(self) -> None:
        mb = self.menuBar()

        file_menu = mb.addMenu("&File")
        file_menu.addAction(
            QAction("&New Show", self, shortcut=QKeySequence.StandardKey.New, triggered=self._on_new_show)
        )
        file_menu.addAction(
            QAction("&Open Show…", self, shortcut=QKeySequence.StandardKey.Open, triggered=self._on_open_show)
        )
        file_menu.addAction(QAction("🏠 Pagina iniziale", self, triggered=self._show_start_page))  # 5.16
        # Recent projects: the list is rebuilt on open so it always reflects
        # what was saved/loaded during this session and in previous ones.
        self._recent_menu = file_menu.addMenu("Apri &recenti")
        self._recent_menu.setToolTipsVisible(True)
        self._recent_menu.aboutToShow.connect(self._rebuild_recent_menu)
        file_menu.addAction(
            QAction("&Save Show", self, shortcut=QKeySequence.StandardKey.Save, triggered=self._on_save_show)
        )
        file_menu.addAction(
            QAction("Save Show &As…", self, shortcut=QKeySequence("Ctrl+Shift+S"), triggered=self._on_save_as_show)
        )
        file_menu.addSeparator()
        file_menu.addAction(QAction("📁 Nuovo spettacolo da una cartella…", self,
                                    triggered=self._new_show_from_folder))  # 5.9
        file_menu.addAction(QAction("🎓 Spettacolo di prova", self, triggered=self._open_practice_show))  # 5.17
        # Rarely used items in submenus (evaluation 2026-11-24, #13): the menu fits on one screen.
        import_menu = file_menu.addMenu("📥 Importa")
        import_menu.addAction(QAction("📋 Importa una scaletta (CSV)…", self, triggered=self._import_skeleton))  # 5.9
        import_menu.addAction(QAction("🎵 Importa playlist (.m3u)…", self, triggered=self._on_import_playlist))  # 3.3
        import_menu.addAction(QAction("📥 Importa cue da un altro spettacolo…", self,
                                      triggered=self._import_from_show))  # 5.3
        export_menu = file_menu.addMenu("🖨 Esporta e stampa")
        export_menu.addAction(QAction("📄 Esporta la scaletta (CSV)…", self, triggered=self._export_list_csv))  # 5.1
        export_menu.addAction(QAction("🖨 Stampa la scaletta per la regia…", self,
                                      triggered=lambda: self._print_list("operator")))
        export_menu.addAction(QAction("🖨 Stampa la scaletta per il suggeritore…", self,
                                      triggered=lambda: self._print_list("prompter")))
        rescue_menu = file_menu.addMenu("🛟 Copie e file mancanti")
        rescue_menu.addAction(QAction("🕘 Ripristina una copia di sicurezza…", self,
                                      triggered=self._restore_backup))  # 5.11
        rescue_menu.addAction(QAction("🔎 Cerca i file mancanti in una cartella…", self,
                                      triggered=self._find_missing_files))  # 5.10
        self._build_settings_transfer_menu(file_menu)  # 5.13
        file_menu.addAction(QAction("ℹ Informazioni sullo spettacolo…", self, triggered=self._open_show_info))  # 5.6
        file_menu.addSeparator()
        file_menu.addAction(
            QAction("&Quit", self, shortcut=QKeySequence.StandardKey.Quit, triggered=self._on_quit)
        )

        edit_menu = mb.addMenu("&Modifica")
        self._act_undo = QAction("↶ &Annulla", self, triggered=self._on_undo)
        self._act_undo.setShortcut(QKeySequence.StandardKey.Undo)
        self._act_undo.setEnabled(False)
        self._act_redo = QAction("↷ &Ripeti", self, triggered=self._on_redo)
        redo_keys: list[QKeySequence] = []
        seen_redo: set[str] = set()
        for seq in (
            *QKeySequence.keyBindings(QKeySequence.StandardKey.Redo),
            QKeySequence("Ctrl+Y"),
            QKeySequence("Ctrl+Shift+Z"),
        ):
            key_str = seq.toString()
            if key_str and key_str not in seen_redo:
                seen_redo.add(key_str)
                redo_keys.append(seq)
        self._act_redo.setShortcuts(redo_keys)
        self._act_redo.setEnabled(False)
        edit_menu.addAction(self._act_undo)
        edit_menu.addAction(self._act_redo)
        edit_menu.addAction(QAction("🕘 Storia delle modifiche…", self, triggered=self._open_history))  # 5.11
        edit_menu.addSeparator()
        edit_menu.addAction(QAction("🔢 Rinumera le Q…", self, triggered=self._renumber_q))  # 5.2

        show_menu = mb.addMenu("&Show")
        show_menu.addAction(
            QAction("&GO (Next Cue)", self, shortcut=QKeySequence("Space"), triggered=self._on_go_shortcut)
        )
        show_menu.addAction(
            QAction("GO &forzato (ignora cue esclusiva)", self, shortcut=QKeySequence("Ctrl+Space"),
                    triggered=self._on_go_forced)
        )
        show_menu.addAction(
            QAction("&Blackout", self, shortcut=QKeySequence("Ctrl+B"), triggered=self._on_blackout)
        )
        show_menu.addAction(
            QAction("&Dissolvenza totale (Fade All)", self, shortcut=QKeySequence("Shift+Esc"),
                    triggered=self._on_fade_all)
        )
        # Pause All had no key at all (mouse only); W3 of the accessibility review.
        show_menu.addAction(
            QAction("❚❚ &Pausa / riprendi tutto", self, shortcut=QKeySequence("Ctrl+P"),
                    triggered=lambda: self.pause_all_toggled.emit())
        )
        # Undo the last GO (1.18): no key on purpose (Ctrl+Z and Backspace edit).
        self._act_undo_go = QAction("↶ Annulla l'ultimo GO", self, triggered=self._on_undo_go)
        self._act_undo_go.setEnabled(False)
        show_menu.addAction(self._act_undo_go)
        show_menu.addAction(QAction("◐ Prova", self, shortcut=QKeySequence("Shift+F5"),
                                    triggered=self._enter_rehearsal_from_key))
        self._act_end_show = QAction("Termina lo spettacolo…", self, shortcut=QKeySequence("Ctrl+Shift+F5"),
                                     triggered=self._on_end_show_requested)
        self._act_end_show.setEnabled(False)
        show_menu.addAction(self._act_end_show)
        show_menu.addSeparator()
        self._build_layer0_menu(show_menu)  # black / picture / looping video / test pattern (#9)
        show_menu.addSeparator()
        self._act_jam_mode = QAction("🎚 Modalità &Jam / Contest (Auto-Gain EBU R128)", self, checkable=True)
        self._act_jam_mode.setToolTip("Abilita il livellamento automatico EBU R128 (-16 LUFS) per contest, jam session e file non calibrati.")
        self._act_jam_mode.toggled.connect(self._set_jam_mode)
        devices_menu = show_menu.addMenu("🔌 Dispositivi")
        devices_menu.addAction(
            QAction("⚙️ &Dispositivi & Hardware (Audio / Video / Profilo)…", self, triggered=self.open_device_settings_dialog)
        )
        devices_menu.addAction(  # 3.1
            QAction("🔊 Uscite audio (Palco / Sala / Spie)…", self, triggered=self.open_audio_outputs_dialog)
        )
        devices_menu.addAction(
            QAction("📡 &Controllo Remoto LAN (Web & OSC)…", self, shortcut=QKeySequence(Qt.Key.Key_F8), triggered=self.open_remote_control_dialog)
        )
        settings_menu = show_menu.addMenu("⚙ Impostazioni dello spettacolo")
        settings_menu.addAction(QAction("⏬ Tempo del pulsante Sfuma…", self,
                                        triggered=self._ask_fade_button_seconds))  # evaluation 2026-11-24
        settings_menu.addAction(QAction("⌨ Tasti e telecomando di presentazione…", self,
                                        triggered=self._open_key_map))  # 5.7-5.8
        settings_menu.addAction(QAction("PIN di uscita dallo spettacolo…", self, triggered=self._set_exit_pin))
        settings_menu.addAction(self._act_jam_mode)
        # 2.3: versions of the show (named sets of cues that are off).
        self._versions_menu = show_menu.addMenu("🎭 Versioni dello spettacolo")
        # 2.5: countdown (e.g. the interval); 2.6: the time plan (cues at a time of day)
        time_menu = show_menu.addMenu("⏳ Tempo")
        time_menu.addAction(QAction("⏳ Conto alla rovescia…", self, triggered=lambda: self._ask_countdown()))
        time_menu.addAction(QAction("🖥 Conto alla rovescia grande (quinte)", self,
                                    triggered=lambda: self._show_countdown_window()))
        time_menu.addAction(QAction("⏹ Ferma il conto alla rovescia", self, triggered=lambda: self.stop_countdown()))
        time_menu.addSeparator()
        self._act_clock_hold = QAction("❚❚ Sospendi il piano orario", self, checkable=True)
        self._act_clock_hold.toggled.connect(lambda on: self._toggle_clock_hold(on))
        time_menu.addAction(self._act_clock_hold)
        self._act_clock_rehearsal = QAction("🕐 Piano orario anche nella prova", self, checkable=True)
        self._act_clock_rehearsal.setChecked(
            QSettings("BlindCue", "BlindCue").value("live/clock_in_rehearsal", False, type=bool))
        self._act_clock_rehearsal.toggled.connect(
            lambda on: QSettings("BlindCue", "BlindCue").setValue("live/clock_in_rehearsal", bool(on)))
        time_menu.addAction(self._act_clock_rehearsal)
        # Stage 1M, M2: an AI assistant (MCP) may change the open show - off by default.
        self._act_assistant = QAction("🤖 L'assistente AI può modificare lo spettacolo", self, checkable=True)
        self._act_assistant.setToolTip(
            "Un assistente AI su questo computer (Claude Desktop o un altro client MCP) può leggere lo "
            "spettacolo aperto e modificarlo nella preparazione. Ogni modifica si annulla con Ctrl+Z.")
        self._act_assistant.toggled.connect(self._on_assistant_toggled)
        assistant_menu = show_menu.addMenu("🤖 Assistente AI")
        assistant_menu.addAction(self._act_assistant)
        assistant_menu.addAction(QAction("🤖 Assistente AI…", self, triggered=self._open_assistant_dialog))

        view_menu = mb.addMenu("&View")
        self._act_live_mode = QAction("🎭 Modalità &LIVE (Show Mode)", self, checkable=True)
        self._act_live_mode.setShortcut(QKeySequence(Qt.Key.Key_F5))
        self._act_live_mode.toggled.connect(self._on_live_action_toggled)
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

        # Language submenu (applied on the next start)
        import i18n
        lang_menu = view_menu.addMenu("🌐 Lingua / Language / Język")
        self._lang_action_group = QActionGroup(self)
        self._lang_action_group.setExclusive(True)
        saved_lang = i18n.saved_language()
        for code, label in i18n.LANGUAGES.items():
            act = QAction(label, self, checkable=True)
            act.setChecked(code == saved_lang)
            act.triggered.connect(lambda checked=False, c=code: self._set_ui_language(c))
            self._lang_action_group.addAction(act)
            lang_menu.addAction(act)

        self._act_earcons = QAction("🔔 &Segnali Acustici Operatore (Earcons)", self, checkable=True)
        self._act_earcons.setToolTip(
            "Accessibilità Regia: Emette un discreto segnale sonoro di conferma ad ogni GO, STOP e PAUSA.\n"
            "Utile per operatori non vedenti o per chi guarda il palco senza guardare il monitor."
        )
        self._act_earcons.setChecked(self._earcon_mgr.enabled)
        self._act_earcons.toggled.connect(self._set_earcons_enabled)
        view_menu.addAction(self._act_earcons)

        view_menu.addSeparator()
        self._act_surface_mapping = QAction("📐 &Studio Superfici di Proiezione & Mapping…", self)
        self._act_surface_mapping.setShortcut(QKeySequence(Qt.Key.Key_F7))
        self._act_surface_mapping.setToolTip("Gestisci schermi virtuali, keystone a 4 angoli e configurazioni multi-proiettore")
        self._act_surface_mapping.triggered.connect(self._open_surface_mapping_dialog)
        view_menu.addAction(self._act_surface_mapping)

        self._act_calib_guides = QAction("👁 &Mostra Guide sul Proiettore Live", self, checkable=True)
        self._act_calib_guides.setShortcut(QKeySequence("Shift+F7"))
        self._act_calib_guides.setToolTip("Proietta mire ottiche, griglia di precisione e contorni delle superfici sul palco")
        self._act_calib_guides.setChecked(self._output.is_calibration_guides_visible())
        self._act_calib_guides.toggled.connect(self._toggle_calibration_guides)
        view_menu.addAction(self._act_calib_guides)

        # Lock and "restore" live in View → Window layout (C2b, _variants.py).
        self._act_lock_layout = QAction("🔒 &Blocca Larghezza Pannelli", self, checkable=True)
        self._act_lock_layout.setChecked(True)
        self._act_lock_layout.toggled.connect(lambda checked: self._set_panels_locked(checked))

        help_menu = mb.addMenu("&Help")
        from ui.help_dialog import show_help
        help_menu.addAction(
            QAction("📖 Manuale utente", self, shortcut=QKeySequence(Qt.Key.Key_F1),
                    triggered=lambda: show_help(self))
        )
        help_menu.addAction(QAction("🖨 Promemoria da stampare", self, triggered=self._open_cheat_sheet))  # 5.18
        help_menu.addAction(QAction("🎓 Spettacolo di prova", self, triggered=self._open_practice_show))  # 5.17
        help_menu.addSeparator()
        help_menu.addAction(
            QAction("&Info Hardware & Accelerazione…", self, triggered=self._show_hw_info)
        )
        help_menu.addSeparator()
        help_menu.addAction(
            QAction("&About BlindCue", self, triggered=lambda: show_about_dialog(self))
        )

    def _set_ui_language(self, code: str) -> None:
        """Store the UI language and ask for a restart (texts are set at build time)."""
        import i18n
        if code == i18n.saved_language():
            return
        i18n.save_language(code)
        msg = {
            "it": "La lingua dell'interfaccia cambierà al prossimo avvio di BlindCue.",
            "en": "The interface language will change after restarting BlindCue.",
            "pl": "Język interfejsu zostanie zmieniony po ponownym uruchomieniu BlindCue.",
        }[code]
        QMessageBox.information(self, "BlindCue", msg)

    def _design_control_bar_widget(self) -> QWidget:
        """Top row of the editor: mode tabs left, Fade All and PANIC right.

        The LIVE page has the same row (tabs in its top bar), so the mode and
        the emergency buttons sit in the same place in both views.
        """
        from PySide6.QtWidgets import QHBoxLayout

        from ui.mode_tabs import ModeTabs

        bar = QWidget()
        bar.setFixedHeight(44)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(10, 5, 10, 5)
        lay.setSpacing(8)
        self._mode_tabs = ModeTabs()
        self._mode_tabs.enter_show_requested.connect(self._enter_show_from_key)
        self._mode_tabs.leave_show_requested.connect(lambda: self._leave_show_to("preparation"))
        lay.addWidget(self._mode_tabs)
        lay.addStretch(1)
        from ui.master_volume import MasterVolume

        self._master_volume = MasterVolume()
        self._master_volume.level_changed.connect(lambda v: self._set_master(level=v))
        self._master_volume.mute_changed.connect(lambda m: self._set_master(muted=m))
        lay.addWidget(self._master_volume)
        btn_fade = QPushButton("🔉 DISSOLVI [⇧ESC]")
        btn_fade.setFixedHeight(34)
        btn_fade.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        btn_fade.setToolTip("Dissolvenza totale: tutto ciò che è in onda sfuma e si ferma [Maiusc+Esc]")
        btn_fade.setStyleSheet(
            "QPushButton { background-color: #3f2806; color: #fbbf24; border: 1px solid #d97706; "
            "border-radius: 5px; font-weight: bold; font-size: 12px; padding: 0px 12px; } "
            "QPushButton:hover { background-color: #5c3b09; color: #ffffff; } "
            "QPushButton:focus { border: 2px solid #fde68a; }"
        )
        btn_fade.clicked.connect(self._on_fade_all)
        lay.addWidget(btn_fade)
        btn_panic = QPushButton("🚨 PANIC [ESC ×2]")
        btn_panic.setFixedHeight(34)
        btn_panic.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        btn_panic.setToolTip("PANIC: ferma subito tutto (0 ms) [Esc due volte]")
        btn_panic.setStyleSheet(
            "QPushButton { background-color: #7f1d1d; color: #ffffff; border: 2px solid #ef4444; "
            "border-radius: 5px; font-weight: bold; font-size: 12px; padding: 0px 12px; } "
            "QPushButton:hover { background-color: #dc2626; border-color: #fca5a5; } "
            "QPushButton:focus { border: 2px solid #ffffff; }"
        )
        btn_panic.clicked.connect(self._on_panic)
        lay.addWidget(btn_panic)
        self._design_control_bar = bar
        return bar

    def _build_ui(self) -> None:
        from ui.operator_note import OperatorNoteBanner

        self._central_stack = QStackedWidget()
        # Operator notes sit above both pages (design and LIVE), never on the output.
        central = QWidget()
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        self._note_banner = OperatorNoteBanner()
        self._note_banner.item_toggled.connect(self._on_note_item_toggled)
        self._note_banner.dismissed.connect(self._on_note_dismissed)
        central_layout.addWidget(self._design_control_bar_widget())
        central_layout.addWidget(self._note_banner)
        central_layout.addWidget(self._central_stack, stretch=1)
        self.setCentralWidget(central)

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
        self._cue_list.files_dropped.connect(self._on_files_dropped_on_list)
        self._cue_list_panel.add_media_requested.connect(self._on_add_media)
        self._cue_list_panel.add_group_requested.connect(self._on_add_scene_interactive)
        self._cue_list_panel.add_text_requested.connect(self._on_add_text_cue)
        self._cue_list_panel.add_action_requested.connect(self._on_add_action_cue)
        self._cue_list_panel.edit_text_requested.connect(self._on_edit_text_cue)
        self._cue_list_panel.ungroup_requested.connect(self._ungroup_selected)
        self._cue_list_panel.extract_child_requested.connect(self._extract_selected_from_group)
        self._cue_list.open_timeline_requested.connect(self._on_open_group_timeline)
        self._cue_list.group_collapse_toggled.connect(self._toggle_group_collapsed)
        self._cue_list_panel.move_up_requested.connect(self._on_move_up)
        self._cue_list_panel.move_down_requested.connect(self._on_move_down)
        self._cue_list_panel.delete_requested.connect(self._on_delete_cue)
        self._cue_list_panel.go_live_mode_requested.connect(lambda: self.set_live_mode(True))
        # The mode tabs above replace it (the same place in every view).
        self._cue_list_panel.btn_go_live.setVisible(False)
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

        # The text names the cue the GO fires (see _update_go_button_text).
        self._btn_go = ElidedButton("GO (Next Cue) — [ SPAZIO ]")
        self._btn_go.setToolTip("GO: avvia la cue indicata sul pulsante [SPAZIO]")
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
        self._inspector.output_target_selected.connect(self._set_output_target)
        self._inspector.color_selected.connect(self._set_cue_color)
        self._inspector.follow_mode_selected.connect(self._set_follow_mode)
        self._inspector.in_out_reset_requested.connect(self._on_reset_in_out)
        self._inspector.silence_trim_requested.connect(self._on_trim_silence)
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
        self._inspector.open_surface_mapping_requested.connect(self._open_surface_mapping_dialog)
        self._inspector.mask_edit_requested.connect(self._on_mask_edit_requested)
        self._inspector.set_available_surfaces(self._surfaces)
        self._inspector.set_cue_catalog_provider(lambda: self._cues)
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
        self._live_status.choose_layer0_clicked.connect(self._on_layer0_button)
        self._live_status.reset_layer0_clicked.connect(self._on_reset_layer0)
        self._live_status.layer_play_pause_clicked.connect(self.layer_play_pause_requested.emit)
        self._live_status.layer_seek_requested.connect(self.layer_seek_requested.emit)
        bottom_splitter.addWidget(self._live_status)

        drop_group = self._drop_group = QGroupBox("Caricamento Rapido (Drag && Drop)")
        drop_layout = QVBoxLayout(drop_group)
        self._drop_zone = DropZone()
        self._drop_zone.file_dropped.connect(self._on_file_dropped)
        drop_layout.addWidget(self._drop_zone)
        bottom_splitter.addWidget(drop_group)

        bottom_splitter.setSizes([460, 320, 220])
        root_layout.addWidget(bottom_splitter, stretch=2)

        # Dedicated distraction-free LIVE Show Mode page
        self._live_show_panel = LiveShowPanel()
        self._live_show_panel.exit_live_mode_requested.connect(lambda: self._leave_show_to("preparation"))
        lv = self._live_show_panel.master_volume
        lv.level_changed.connect(lambda v: self._set_master(level=v))
        lv.mute_changed.connect(lambda m: self._set_master(muted=m))
        self._live_show_panel.go_requested.connect(self._on_go)
        self._live_show_panel.undo_go_requested.connect(self._on_undo_go)
        self._live_show_panel.gate_ok_requested.connect(self._confirm_gate)
        self._live_show_panel.mode_tabs.enter_show_requested.connect(self._enter_show_from_key)
        self._live_show_panel.readiness_review_requested.connect(lambda: self._show_readiness(review=True))
        self._live_show_panel.force_go_requested.connect(self._on_go_forced)
        self._live_show_panel.cue_row_clicked.connect(lambda r: self._cue_list.setCurrentRow(r))
        self._live_show_panel.cue_row_double_clicked.connect(self._on_live_row_double_clicked)
        self._live_show_panel.group_collapse_toggled.connect(self._toggle_group_collapsed)
        self._live_show_panel.pause_all_toggled.connect(self.pause_all_toggled.emit)
        self._live_show_panel.panic_requested.connect(self._on_panic)
        self._live_show_panel.fade_all_requested.connect(self._on_fade_all)
        self._live_show_panel.double_click_armed.connect(self._on_live_double_click_armed)
        self._live_show_panel.force_row_requested.connect(self._on_live_row_forced)
        self._live_show_panel.break_loop_requested.connect(self._on_break_section_loop)
        self._live_show_panel.live_status.clear_layer_clicked.connect(self._on_clear_live_layer)
        self._live_show_panel.live_status.layer_play_pause_clicked.connect(self.layer_play_pause_requested.emit)
        self._live_show_panel.live_status.layer_seek_requested.connect(self.layer_seek_requested.emit)

        self._status_panels: list[LiveStatusPanel] = [
            self._live_status,
            self._live_show_panel.live_status,
        ]
        for status_panel in self._status_panels:
            status_panel.output_screen_changed.connect(self._on_output_screen_selected)

        self._central_stack.addWidget(self._design_page)
        self._central_stack.addWidget(self._live_show_panel)
        self._central_stack.setCurrentIndex(0)

    def _rebuild_recent_menu(self) -> None:
        """Rebuild the "Apri recenti" submenu from QSettings.

        Rebuilding on ``aboutToShow`` (instead of keeping actions in sync while
        the app runs) means the menu is always correct after an open/save and
        costs nothing during a show.
        """
        menu = getattr(self, "_recent_menu", None)
        if menu is None:
            return
        menu.clear()
        pinned = self._pinned_projects()  # 5.9: always on top, never pushed out
        recent = [p for p in self._recent_projects() if p not in pinned]
        if not recent and not pinned:
            empty = menu.addAction("Nessun progetto recente")
            empty.setEnabled(False)
        for idx, path in enumerate(pinned + recent, start=1):
            name = Path(path).stem or Path(path).name
            mark = "📌 " if path in pinned else ""
            act = QAction(f"{idx}. {mark}{name}", self)
            act.setToolTip(path)
            # Missing files stay visible: clicking explains what happened and
            # removes the stale entry instead of failing silently.
            if not os.path.isfile(path):
                act.setText(f"{idx}. {mark}{name}  (non trovato)")
            act.triggered.connect(lambda _checked=False, p=path: self._open_recent_project(p))
            menu.addAction(act)
            if idx == len(pinned) and recent:
                menu.addSeparator()

        menu.addSeparator()
        current = getattr(self, "_current_project_path", None)
        is_pinned = bool(current) and self._recent_key(current) in pinned
        pin = QAction("📌 Non fissare più questo spettacolo" if is_pinned else "📌 Fissa questo spettacolo in cima",
                      self, triggered=self._toggle_pin_current)
        pin.setEnabled(bool(current))
        menu.addAction(pin)
        menu.addAction(QAction("Svuota elenco recenti", self, triggered=self._clear_recent_projects))

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

        self._lbl_perf_hint = QLabel("")
        self._lbl_perf_hint.setStyleSheet(
            "color: #f59e0b; font-size: 11px; font-weight: 600; padding-left: 8px;")
        self._lbl_perf_hint.setVisible(False)
        sb.addWidget(self._lbl_perf_hint)

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
        self._btn_jam_mode.setMinimumWidth(180)  # room for "(hold 5 s)" in every language
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

        self._btn_remote_status = QPushButton("📡 Remoto: OFF")
        self._btn_remote_status.setFixedHeight(22)
        self._btn_remote_status.setMinimumWidth(168)
        self._btn_remote_status.setStyleSheet("color: #64748b;")
        self._btn_remote_status.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_remote_status.setToolTip(
            "Controllo Remoto LAN per Smartphone/Tablet (Web) e OSC.\n"
            "Clicca per mostrare il QR Code, l'indirizzo IP e le opzioni di comando."
        )
        self._btn_remote_status.setAccessibleName("Controllo Remoto LAN Web e OSC")
        self._btn_remote_status.setAccessibleDescription("Mostra il codice QR per smartphone e la configurazione del server web e OSC.")
        self._btn_remote_status.clicked.connect(self.open_remote_control_dialog)
        sb.addWidget(self._btn_remote_status)

        self._status_label = QLabel("Ready — No show loaded")
        self._status_label.setMinimumWidth(0)
        self._status_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        sb.addPermanentWidget(self._status_label, stretch=1)
        self.setStatusBar(sb)

    def set_performance_hint(self, text: str | None) -> None:
        """Show or clear the persistent live-load warning in the status bar.

        The warning is advisory only: it never blocks the operator. It stays
        visible until explicitly cleared so an overloaded projector cannot be
        forgotten while working on other cues.
        """
        hint = (text or "").strip()
        # Called once per second by the live-load guard: skip the work when
        # nothing changed, so an idle show pays no repaint cost.
        if self._lbl_perf_hint.text() == hint and self._lbl_perf_hint.isHidden() == (not hint):
            return
        self._lbl_perf_hint.setText(hint)
        self._lbl_perf_hint.setVisible(bool(hint))
