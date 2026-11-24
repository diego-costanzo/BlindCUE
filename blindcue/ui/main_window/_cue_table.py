"""Helpers & Table Population mixin for MainWindow."""

from __future__ import annotations

from i18n import tr

from ui.main_window._common import *  # noqa: F403,F401,F405
from ui.main_window._common import (  # noqa: F401
    _AutosaveWorker,
    _DEFAULT_TOP_RATIOS,
    _MEDIA_ICONS,
    _demote_live_on_layer,
)

import time

from engine.action_cues import describe_action
from ui.cue_table import ROLE_THUMB_PATH


class _EmergencyKeysInDialog(QObject):
    """Esc and Shift+Esc keep their emergency meaning inside a modal question.

    A modal dialog takes the keyboard from the window shortcuts, so with a
    show running PANIC needed three Esc and Shift+Esc did nothing. Here Esc
    closes the question and counts as the first press of Esc Esc = PANIC,
    and Shift+Esc closes it and fades everything out.
    """

    def __init__(self, window, box: QMessageBox) -> None:
        super().__init__(box)
        self._window = window
        self._box = box

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        if event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Escape:
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self._box.reject()
                QTimer.singleShot(0, self._window._on_fade_all)
                return True
            self._window._last_esc_press_mono = time.monotonic()
        return False


class _CueTableMixin:
    @staticmethod
    def _detect_media_type(file_path: str) -> MediaType | None:
        ext = Path(file_path).suffix.lower()
        if ext in VIDEO_EXT:
            return MediaType.VIDEO
        if ext in AUDIO_EXT:
            return MediaType.AUDIO
        if ext in IMAGE_EXT:
            return MediaType.IMAGE
        return None

    def set_preview_time(self, current_sec: float, total_sec: float) -> None:
        """Forward the rehearsal playhead to the preview monitor."""
        if hasattr(self, "_preview_panel"):
            self._preview_panel.set_time(current_sec, total_sec)

    def _cue_tooltip(self, row: int, cue: Cue) -> str:
        parts = []
        if cue.cue_id in self._layer_conflicts:
            parts.append(f"⚠️ ATTENZIONE: {self._layer_conflicts[cue.cue_id].reason}\n")
        parts.append(f"Posizione: #{row + 1}")
        if cue.q_label:
            parts.append(f"Q (Copione): {cue.q_label}")
        parts.append(f"Nome: {cue.name}")
        link_lbl = {
            FollowMode.MANUAL.value: "Blocco manuale",
            FollowMode.AUTO_FOLLOW.value: "Auto-GO a fine cue",
            FollowMode.SIMULTANEOUS.value: "Simultanea con successiva",
        }.get(cue.follow_mode, cue.follow_mode)
        timing_bits = []
        if cue.pre_delay > 0:
            timing_bits.append(f"Pre +{cue.pre_delay:.1f}s")
        if cue.media_type == MediaType.IMAGE:
            timing_bits.append(f"Durata {'∞' if cue.hold_time <= 0 else f'{cue.hold_time:.1f}s'}")
        if cue.post_delay > 0:
            timing_bits.append(f"Post +{cue.post_delay:.1f}s")
        timing_bits.append(link_lbl)
        parts.append("Tempi: " + " | ".join(timing_bits))
        if cue.notes:
            parts.append(f"Note di Regia: {cue.notes}")
        if cue.media_type == MediaType.ACTION:
            parts.append(f"Azione: {describe_action(cue.action_spec, self._cues)}")
        else:
            parts.append(f"File: {cue.file_path}")
        return "\n".join(parts)

    def _update_cue_readouts(self, row: int, cue: Cue) -> None:
        ref = format_cue_ref(row, cue)
        icon = _MEDIA_ICONS.get(cue.media_type, "🖼")
        self._lbl_preview_info.setText(f"{icon} {ref}  {cue.name}")
        if cue.media_type == MediaType.ACTION:
            self._lbl_preview_info.setToolTip(f"Azione: {describe_action(cue.action_spec, self._cues)}")
        else:
            self._lbl_preview_info.setToolTip(f"File: {cue.file_path}")
        self._lbl_cue_standby.setText(f"Standby: {ref} [{cue.media_type.value}]")

    def _reset_idle_preview_ui(self) -> None:
        self._img_previz_timer.stop()
        self._active_test_duration = 0.0
        self._active_section_idx = -1
        self._waveform.set_peaks(np.array([]))
        self._waveform.set_media_context(None)
        self._waveform.set_in_out_seconds(0.0, None, 0.0)
        self._waveform.set_sections([], -1)
        self._waveform_panel.section_bar.set_sections([], 0.0, -1)
        self._waveform_panel.sync_controls_for_cue(media_type=None)
        self.set_waveform_playhead_seconds(None, 0.0)
        self._lbl_preview_info.setText("— Nessun file selezionato —")
        self.set_preview_time(0.0, 0.0)
        self.clear_preview()

    def _populate_cue_row(self, row: int, cue: Cue, is_standby: bool) -> None:
        """Populate or update the 3 table cells (#, Q, Nome / Media) for a row."""
        status_txt = ""
        colour = CLR_TEXT
        if cue.status == CueStatus.LIVE:
            status_txt, colour = "LIVE", CLR_LIVE
        elif is_standby:
            status_txt, colour = "STANDBY", CLR_PREVIZ
        elif cue.status == CueStatus.PREVIZ:
            status_txt, colour = "PRE-VIZ", CLR_PREVIZ
        if not getattr(cue, "enabled", True):
            status_txt, colour = tr("⊘ ESCLUSA"), CLR_TEXT_MUTED  # 2.3: off in this version

        tooltip = self._cue_tooltip(row, cue)

        is_group = (cue.media_type == MediaType.GROUP)
        child_count = 0
        if is_group:
            child_count = sum(1 for c in self._cues if c.parent_id == cue.cue_id)

        is_last_child = False
        if cue.parent_id is not None:
            siblings = [c for c in self._cues if c.parent_id == cue.parent_id]
            if siblings and siblings[-1].cue_id == cue.cue_id:
                is_last_child = True

        item_num = self._cue_list.item(row, 0)
        if item_num is None:
            item_num = QTableWidgetItem()
            item_num.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_num.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            self._cue_list.setItem(row, 0, item_num)
        item_num.setText(f"#{row + 1}")
        item_num.setForeground(QColor(colour if status_txt in ("LIVE", "STANDBY") else CLR_TEXT_MUTED))
        item_num.setToolTip(tooltip)
        item_num.setData(ROLE_IS_GROUP, is_group)
        item_num.setData(ROLE_GROUP_COLLAPSED, getattr(cue, "collapsed", False))

        item_q = self._cue_list.item(row, 1)
        if item_q is None:
            item_q = QTableWidgetItem()
            item_q.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_q.setFlags(
                Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsEditable
            )
            self._cue_list.setItem(row, 1, item_q)
        item_q.setText(cue.q_label)
        item_q.setToolTip(tooltip)

        item_name = self._cue_list.item(row, 2)
        if item_name is None:
            item_name = QTableWidgetItem()
            item_name.setFlags(
                Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsEditable
            )
            self._cue_list.setItem(row, 2, item_name)
        item_name.setText(cue.name)
        cue_color = getattr(cue, "color", "") or ""
        prev_color = (getattr(self._cues[row - 1], "color", "") or "") if row > 0 else ""
        incoming_link = self._cues[row - 1].follow_mode if row > 0 else ""

        conflict = self._layer_conflicts.get(cue.cue_id)
        conflict_txt = conflict.reason if conflict else ""

        item_name.setData(ROLE_MEDIA_TYPE, cue.media_type.value)
        item_name.setData(ROLE_LAYER, cue.layer)
        item_name.setData(ROLE_OUTPUT_TARGET, getattr(cue, "output_target", "A"))
        item_name.setData(ROLE_LAYER_CONFLICT, conflict_txt)
        item_name.setData(ROLE_HAS_NOTES, bool(cue.notes))
        item_name.setData(ROLE_FOLLOW_MODE, cue.follow_mode)
        item_name.setData(ROLE_TIMING_BADGE, "⏱" if (cue.pre_delay > 0 or cue.post_delay > 0) else "")
        item_name.setData(ROLE_STATUS_TXT, status_txt)
        item_name.setData(ROLE_STATUS_CLR, colour)
        item_name.setData(ROLE_PARENT_ID, cue.parent_id)
        item_name.setData(ROLE_IS_GROUP, is_group)
        item_name.setData(ROLE_GROUP_MODE, getattr(cue, "group_mode", "STEP"))
        item_name.setData(ROLE_GROUP_COLLAPSED, getattr(cue, "collapsed", False))
        item_name.setData(ROLE_CHILD_COUNT, child_count)
        item_name.setData(ROLE_IS_LAST_CHILD, is_last_child)
        item_name.setData(ROLE_TIMELINE_COMPOSED, bool(getattr(cue, "timeline_composed", False)))
        item_name.setData(ROLE_THUMB_PATH, cue.file_path if cue.media_type in (MediaType.IMAGE, MediaType.VIDEO)
                          else "")  # 4.4: thumbnail in the editing list
        live_frac, live_warn = self._live_fractions.get(cue.cue_id, (-1.0, False))
        item_name.setData(ROLE_LIVE_FRACTION, live_frac)
        item_name.setData(ROLE_LIVE_WARN, live_warn)
        item_name.setToolTip(tooltip)

        for cell in (item_num, item_q, item_name):
            cell.setData(ROLE_CUE_COLOR, cue_color)
            cell.setData(ROLE_PREV_COLOR, prev_color)
            cell.setData(ROLE_FOLLOW_MODE, cue.follow_mode)
            cell.setData(ROLE_INCOMING_LINK, incoming_link)

        # Set row visibility based on parent collapse state
        if cue.parent_id is not None:
            parent_cue = next((c for c in self._cues if c.cue_id == cue.parent_id), None)
            is_hidden = bool(parent_cue and parent_cue.collapsed)
            self._cue_list.setRowHidden(row, is_hidden)
            if hasattr(self, "_live_show_panel") and self._live_show_panel is not None:
                self._live_show_panel.live_table.setRowHidden(row, is_hidden)
        else:
            self._cue_list.setRowHidden(row, False)
            if hasattr(self, "_live_show_panel") and self._live_show_panel is not None:
                self._live_show_panel.live_table.setRowHidden(row, False)

    def _sync_inspector_header_and_text(self, row: int, cue: Cue) -> None:
        if 0 <= row < len(self._cues) and row == self._cue_list.currentRow():
            self._inspector.sync_header_and_text(row, cue)
            self._update_cue_readouts(row, cue)

    def _for_each_status_panel(self):
        return getattr(self, "_status_panels", [self._live_status])

    def is_live_mode(self) -> bool:
        """True when the UI is in LIVE Show mode (large, simplified console)."""
        return self._live_mode

    @Slot(bool)
    def set_live_mode(self, enabled: bool, checked: bool = False) -> None:
        """Switch between design mode and LIVE Show mode.

        Entering goes through the readiness page first when it is due (it
        ends with the start buttons), otherwise through the start question;
        *checked*: the operator already chose the start there (or the program
        goes back into a show after a crash).
        """
        enabled = bool(enabled)
        if self._live_mode == enabled:
            return
        if enabled and not checked and not self._rehearsal and self._readiness_wanted():
            if hasattr(self, "_act_live_mode"):
                self._act_live_mode.blockSignals(True)
                self._act_live_mode.setChecked(False)
                self._act_live_mode.blockSignals(False)
            self._show_readiness()
            return
        if enabled and not checked and not self._confirm_live_start():
            if hasattr(self, "_act_live_mode"):
                self._act_live_mode.blockSignals(True)
                self._act_live_mode.setChecked(False)
                self._act_live_mode.blockSignals(False)
            return
        if enabled:
            self._readiness_timer.stop()
            self._end_preview_on_projector()  # 4.4: no preview survives into the show
        if enabled and self._go_target_index() == 0 and not self._show_running():
            self._played_ids.clear()  # a run from the top: nothing played yet
            self._goto_counts.clear()  # 2.2: jumps count again
            self._run_reset()  # 2.5: a new run of the show
            self._clock_reset()  # 2.6: today's time plan starts afresh
        if not enabled:
            saved = self._run_save()  # 2.5: the run log of the show that just ended
            if saved is not None:
                logger.info("[RUN LOG] %s", saved)
        if not enabled and self._cues:
            # Where the show was left: coming back to LIVE continues from here.
            self._live_resume_id = self._cues[self._go_target_index()].cue_id
        self._live_mode = enabled
        if not enabled:
            self._rehearsal = False
            self._close_drawer()
        self._undo_go_end()  # a change of mode ends the Undo GO offer
        self._note_banner.set_docked(enabled)  # in the show a plain note is a card of "Now playing"
        if hasattr(self, "_act_live_mode"):
            self._act_live_mode.blockSignals(True)
            self._act_live_mode.setChecked(enabled)
            self._act_live_mode.blockSignals(False)
        self._central_stack.setCurrentIndex(1 if enabled else 0)
        # The LIVE page has its own top row (tabs, clock, Fade All, PANIC).
        if hasattr(self, "_design_control_bar"):
            self._design_control_bar.setVisible(not enabled)
        self._apply_mode_visuals()
        if hasattr(self, "_act_end_show"):
            self._act_end_show.setEnabled(enabled)
        if enabled:
            prof = self._device_mgr.get_effective_profile() if self._device_mgr else "auto"
            ShowRuntimeGuard.on_live_mode_enter(prof)
            self._sync_live_view()
            self._status_label.setText("MODALITÀ LIVE ATTIVA — Interfaccia semplificata per la regia [ESC ×2 = PANIC]")
            # Keyboard on the list at once: arrows move the next cue, Space = GO.
            if hasattr(self, "_live_show_panel"):
                self._live_show_panel.live_table.setFocus()
        else:
            ShowRuntimeGuard.on_live_mode_exit()
            QTimer.singleShot(0, self._apply_top_splitter_ratios)
            self._status_label.setText("MODALITÀ PROGETTO — Modifica cue e anteprima riabilitate")
        self._update_readiness_warning()
        self._update_preview_timer()  # the output preview runs only in the show
        self.announce(self._status_label.text(), assertive=True)  # a change of mode (W17)
        if hasattr(self, "_update_focus_warning"):
            self._update_focus_warning()

    def _on_live_action_toggled(self, checked: bool) -> None:
        """F5 / View menu: enters the show only; leaving needs a deliberate step."""
        if checked:
            self.set_live_mode(True)
            return
        if self._live_mode:
            self._act_live_mode.blockSignals(True)
            self._act_live_mode.setChecked(True)
            self._act_live_mode.blockSignals(False)
            if self._rehearsal:
                self._show_from_rehearsal()  # F5 in the rehearsal enters the show
                return
            self._explain_how_to_leave()

    def _enter_show_from_key(self) -> None:
        """Ctrl+L: like F5, enters only."""
        if self._live_mode and self._rehearsal:
            self._show_from_rehearsal()
        elif self._live_mode:
            self._explain_how_to_leave()
        else:
            self.set_live_mode(True)

    def _explain_how_to_leave(self) -> None:
        from ui.hold_button import hold_text

        self._status_label.setText(  # W29: this computer's hold time
            tr("Per uscire dallo spettacolo: tieni premuto «○ Preparazione» per {} oppure Ctrl+Maiusc+F5")
            .format(hold_text()))
        if hasattr(self, "_earcon_mgr"):
            self._earcon_mgr.play_alert()

    def _on_end_show_requested(self) -> None:
        """Show menu → End the show…: asks, with "stay" as the safe default."""
        if not self._live_mode:
            return
        box = QMessageBox(
            QMessageBox.Icon.Question,
            "Termina lo spettacolo",
            "Tornare alla preparazione? Ciò che è in onda continua a suonare.",
            QMessageBox.StandardButton.NoButton,
            self,
        )
        stay = box.addButton("Resta nello spettacolo", QMessageBox.ButtonRole.RejectRole)
        to_rehearsal = box.addButton("Passa alla prova", QMessageBox.ButtonRole.ActionRole)
        box.addButton("Torna alla preparazione", QMessageBox.ButtonRole.AcceptRole)
        box.setDefaultButton(stay)
        box.setEscapeButton(stay)
        keys = _EmergencyKeysInDialog(self, box)
        box.installEventFilter(keys)
        for btn in box.buttons():
            btn.installEventFilter(keys)
        box.exec()
        if box.clickedButton() is to_rehearsal:
            self._leave_show_to("rehearsal")
        elif box.clickedButton() is not stay:
            self._leave_show_to("preparation")

    def _current_mode(self) -> str:
        from engine.show_mode import PREPARATION, REHEARSAL, SHOW

        if not self._live_mode:
            return PREPARATION
        return REHEARSAL if getattr(self, "_rehearsal", False) else SHOW

    def _change_allowed(self, change: str) -> bool:
        """Policy gate at every point that would change the show document.

        Blocked changes say why on the status line (with the alert earcon)
        instead of being ignored in silence.
        """
        from engine.show_mode import EDIT_CUE, EDIT_LIST, allows, blocked_message

        if change in (EDIT_LIST, EDIT_CUE) and (getattr(self, "_readiness_page", None) is not None
                                                and self._readiness_visible()
                                                or getattr(self, "_start_page", None) is not None
                                                and self._start_page_visible()):
            # The list is hidden behind "Before the show": Delete there removed cue #1 (QA C2a).
            self._status_label.setText(tr("La scaletta è nascosta: torna alla lista per modificarla"))
            self.announce(self._status_label.text(), assertive=True)
            return False
        if allows(self._current_mode(), change):
            return True
        self._status_label.setText(blocked_message(self._current_mode(), change))
        self.announce(self._status_label.text(), assertive=True)
        if hasattr(self, "_earcon_mgr"):
            self._earcon_mgr.play_alert()
        return False

    def _show_running(self) -> bool:
        """Something plays or waits for its start (pre-delay, Auto-GO).

        Group containers do not count: one stays LIVE after its GO until a
        stop clears its layer, even when its children have all ended.
        """
        return any(
            c.status == CueStatus.LIVE and c.media_type != MediaType.GROUP for c in self._cues
        ) or bool(self._live_phase_tags)

    def _confirm_live_start(self) -> bool:
        """Ask where the GO starts when it would not continue where the show was.

        GO fires the selected cue, so a cue fixed in the editor would otherwise
        open the show. Returns False when the operator cancels: LIVE stays off.
        """
        resume_id = getattr(self, "_live_resume_id", None)
        resume_row = next(
            (i for i, c in enumerate(self._cues) if c.cue_id == resume_id), None
        ) if resume_id is not None else None
        choices = live_start_choices(
            len(self._cues), self._go_target_index(), resume_row, self._show_running()
        )
        if not choices:
            return True
        labels = {
            START_FROM_TOP: "Dall'inizio: {}",
            START_RESUME: "Riprendi da: {}",
            START_SELECTED: "Dalla cue selezionata: {}",
        }
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle("Da dove parte lo spettacolo?")
        if resume_row is None:
            box.setText("La cue selezionata non è l'inizio della scaletta.\nDa quale cue deve partire il GO?")
        else:
            box.setText("La selezione è cambiata da quando hai lasciato LIVE.\nDa quale cue deve partire il GO?")
        rows: dict[object, int] = {}
        for kind, row in choices:
            cue = self._cues[row]
            name = cue.name if len(cue.name) <= 60 else cue.name[:59] + "…"
            btn = box.addButton(
                labels[kind].format(f"{format_cue_ref(row, cue)} '{name}'"),
                QMessageBox.ButtonRole.AcceptRole,
            )
            btn.setMinimumHeight(36)
            rows[btn] = row
            if len(rows) == 1:
                box.setDefaultButton(btn)
        box.addButton(QMessageBox.StandardButton.Cancel)
        keys = _EmergencyKeysInDialog(self, box)
        box.installEventFilter(keys)
        for btn in box.buttons():
            btn.installEventFilter(keys)
        box.exec()
        row = rows.get(box.clickedButton())
        if row is None:
            logger.info("[LIVE] Entering LIVE cancelled at the start question")
            return False
        logger.info("[LIVE] Show starts from row %d (#%d)", row, self._cues[row].cue_id)
        self._cue_list.setCurrentRow(row)
        return True

    @Slot()
    def toggle_live_mode(self) -> None:
        """Flip between design mode and LIVE Show mode."""
        self.set_live_mode(not self._live_mode)

    def set_device_manager(self, mgr: Any) -> None:
        """Register the central DeviceManager and wire its signals to the UI."""
        self._device_mgr = mgr
        if mgr is not None:
            mgr.profile_changed.connect(self._update_hardware_status_bar)
            mgr.master_device_changed.connect(self._update_hardware_status_bar)
            mgr.target_screen_changed.connect(self._update_hardware_status_bar)
            mgr.audio_devices_changed.connect(self._update_hardware_status_bar)
            mgr.audio_notice.connect(self._on_audio_notice)
            self._on_audio_notice(mgr.audio_notice_text())
            mgr.output_mode_changed.connect(self._on_output_mode_changed)
            mgr.screens_changed.connect(self._refresh_output_monitors)
            mgr.screens_changed.connect(self._schedule_director_check)
            mgr.screens_changed.connect(self._readiness_devices_changed)
            mgr.audio_devices_changed.connect(self._readiness_devices_changed)
            self._on_output_mode_changed(getattr(mgr, "_output_mode", "single"))
            self._refresh_output_monitors()
            self._update_hardware_status_bar()
            mgr.profile_changed.connect(lambda _p: self._apply_thumbnail_setting())  # 4.4: Eco = no thumbnails
            self._apply_thumbnail_setting()

    @Slot()
    def _schedule_director_check(self) -> None:
        # Windows 11 minimises the windows of a monitor that goes away and
        # moves windows around for a while after a display change: look once
        # it has settled, and once more a little later.
        for delay in (1500, 4000):
            QTimer.singleShot(delay, self._after_display_change)

    def _after_display_change(self) -> None:
        """Outputs back on their screens first, then the director visible."""
        for out in (self._output, getattr(self, "_output_b", None)):
            ensure = getattr(out, "ensure_on_target_screen", None)
            if ensure is not None:
                ensure()
        self._ensure_director_visible()

    def _ensure_director_visible(self) -> None:
        """Keep the director window usable after a display change.

        With Windows "Second screen only" (or the laptop lid closed) the
        director's monitor goes away and Windows 11 minimises the window; with
        the output full screen on the only screen nothing could be clicked
        (2026-11-22). The director goes back to the primary screen when it is
        minimised, off every screen, or under an output window.
        """
        app = QApplication.instance()
        if app is None or getattr(self, "_force_closing", False):
            return
        center = self.frameGeometry().center()
        on_screen = any(s.geometry().contains(center) for s in app.screens())
        covered = False
        for out in (self._output, getattr(self, "_output_b", None)):
            if out is None or not out.isVisible() or out.isMinimized():
                continue
            on_top = bool(out.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)
            if on_top and out.frameGeometry().contains(center):
                covered = True
        if on_screen and not covered and not self.isMinimized():
            return
        logger.info("[MAIN-WIN] Director window brought back after a display change "
                    "(minimised=%s, on screen=%s, covered=%s)", self.isMinimized(), on_screen, covered)
        self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized)
        self.bind_to_primary_screen()
        self.show()
        self.raise_()
        self.activateWindow()

    @Slot()
    def _refresh_output_monitors(self) -> None:
        """Fill the projector pickers in the layer panels.

        The pickers stay hidden unless two external displays are connected:
        with a single projector everything goes there automatically.
        """
        if self._device_mgr is None:
            return
        screens = self._device_mgr.get_external_screens()
        screen_a = self._device_mgr.get_output_screen("A")
        screen_b = self._device_mgr.get_output_screen("B")
        name_a = screen_a.name() if screen_a is not None else ""
        name_b = screen_b.name() if screen_b is not None else ""
        for sp in self._for_each_status_panel():
            setter = getattr(sp, "set_output_monitors", None)
            if setter is not None:
                setter(screens, name_a, name_b)

    @Slot(str, str)
    def _on_output_screen_selected(self, output: str, screen_name: str) -> None:
        """Route output A or B to the projector chosen in the layer panel."""
        if self._device_mgr is None:
            return
        screen = next(
            (s for s in self._device_mgr.get_external_screens() if s.name() == screen_name),
            None,
        )
        if screen is None:
            self._refresh_output_monitors()
            return
        if not self._device_mgr.set_output_screen(output, screen):
            self._status_label.setText(
                f"Proiettore '{screen_name}' non disponibile per l'uscita {output}"
            )
        self._refresh_output_monitors()

    @Slot(str)
    def _on_output_mode_changed(self, mode: str) -> None:
        """Show the output-B layer rows only when dual routing is active."""
        is_dual = str(mode) == "dual"
        self._dual_output_active = is_dual
        for sp in self._for_each_status_panel():
            setter = getattr(sp, "set_dual_mode", None)
            if setter is not None:
                setter(is_dual)
        if hasattr(self, "_inspector"):
            self._inspector.set_dual_mode(is_dual)
        self._refresh_output_monitors()
        # Layer collisions depend on the mode: with one projector, A·L2 and B·L2
        # really do overlap, so the badges must be recalculated.
        if self._cues:
            self._refresh_rows_in_place(list(range(len(self._cues))))

    def open_device_settings_dialog(self) -> None:
        """Open the Device & Hardware configuration dialog."""
        if self._device_mgr is None:
            return
        from ui.device_settings_dialog import DeviceSettingsDialog
        dlg = DeviceSettingsDialog(
            self._device_mgr, self,
            busy=lambda: any(c.status == CueStatus.LIVE for c in self._cues) or bool(self._live_phase_tags))
        dlg.exec()
        self._update_hardware_status_bar()

    def open_audio_outputs_dialog(self) -> None:
        """3.1: which speakers are the stage, the hall and the foldback on this computer."""
        if self._device_mgr is None:
            return
        from engine.show_mode import SHOW
        from ui.audio_outputs_dialog import AudioOutputsDialog

        dlg = AudioOutputsDialog(
            self._device_mgr, locked=self._current_mode() == SHOW, parent=self,
            busy=lambda: any(c.status == CueStatus.LIVE for c in self._cues) or bool(self._live_phase_tags))
        dlg.exec()
        dlg.deleteLater()

    @Slot(str)
    def _on_audio_notice(self, text: str) -> None:
        """Tell the operator when the speakers chosen on this computer are
        missing (the Windows default plays) or connected again."""
        if text:
            self._status_label.setText(text)
        if hasattr(self, "_alarm_bar"):
            self._alarm_bar.set_alarm("speakers", text)  # stays until the speakers are back

    def _on_alarm_changed(self, text: str) -> None:
        """A new warning on the alarm bar: said aloud, and a chime in the show."""
        if not text:
            return
        self.announce(text, assertive=True)
        earcons = getattr(self, "_earcon_mgr", None)
        if self._live_mode and earcons is not None and hasattr(earcons, "play_alert"):
            earcons.play_alert()

    def _update_hardware_status_bar(self, *args: Any) -> None:
        """Refresh the hardware and device brief in the status bar."""
        if hasattr(self, "_lbl_hw_info"):
            pref = self._device_mgr.get_profile_preference() if self._device_mgr else "auto"
            self._lbl_hw_info.setText(detect_hardware_brief(pref))

    def _show_hw_info(self) -> None:
        """Open detailed hardware information dialog."""
        pref = self._device_mgr.get_profile_preference() if self._device_mgr else "auto"
        show_hardware_info_dialog(self, pref)
