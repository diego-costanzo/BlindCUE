"""Remote Control & LAN Automation (Web & OSC) mixin for MainWindow."""

from __future__ import annotations

from ui.main_window._common import *  # noqa: F403,F401,F405
from ui.main_window._common import (  # noqa: F401
    _AutosaveWorker,
    _DEFAULT_TOP_RATIOS,
    _MEDIA_ICONS,
    ShowEngine,
)


class _RemoteMixin:
    def set_remote_manager(self, mgr: Any) -> None:
        """Register the central RemoteManager and wire its triggers to MainWindow."""
        self._remote_mgr = mgr
        if mgr is not None:
            mgr.set_state_provider(self.get_remote_state)
            mgr.go_requested.connect(self._on_remote_go, Qt.ConnectionType.QueuedConnection)
            mgr.panic_requested.connect(self._on_remote_panic, Qt.ConnectionType.QueuedConnection)
            mgr.blackout_requested.connect(self._on_remote_blackout, Qt.ConnectionType.QueuedConnection)
            mgr.pause_toggle_requested.connect(self._on_remote_pause_toggle, Qt.ConnectionType.QueuedConnection)
            mgr.pause_requested.connect(self._on_remote_pause, Qt.ConnectionType.QueuedConnection)
            mgr.resume_requested.connect(self._on_remote_resume, Qt.ConnectionType.QueuedConnection)
            mgr.next_cue_requested.connect(self._on_remote_next_cue, Qt.ConnectionType.QueuedConnection)
            mgr.prev_cue_requested.connect(self._on_remote_prev_cue, Qt.ConnectionType.QueuedConnection)
            mgr.cue_go_requested.connect(self._on_remote_cue_go, Qt.ConnectionType.QueuedConnection)
            mgr.cue_select_requested.connect(self._on_remote_cue_select, Qt.ConnectionType.QueuedConnection)
            mgr.volume_change_requested.connect(self._on_remote_volume_change, Qt.ConnectionType.QueuedConnection)
            mgr.activity_updated.connect(self._update_remote_status_bar, Qt.ConnectionType.QueuedConnection)
            self._update_remote_status_bar()

    def open_remote_control_dialog(self) -> None:
        """Open the Remote Control & Smartphone QR Code setup dialog."""
        if self._remote_mgr is None:
            return
        from ui.remote_control_dialog import RemoteControlDialog
        dlg = RemoteControlDialog(self._remote_mgr, self)
        dlg.exec()
        self._update_remote_status_bar()

    def _update_remote_status_bar(self) -> None:
        """Update discrete remote control button in status bar."""
        if hasattr(self, "_btn_remote_status") and self._remote_mgr:
            if self._remote_mgr.is_web_active():
                url = self._remote_mgr.get_primary_web_url()
                display_url = url.replace("http://", "")
                c_cnt = self._remote_mgr.web_server.get_connected_clients_count()
                suffix = f" ({c_cnt} 📱)" if c_cnt > 0 else ""
                self._btn_remote_status.setText(f"📡 Web: {display_url}{suffix}")
                self._btn_remote_status.setStyleSheet("color: #38bdf8; font-weight: bold;")
            elif self._remote_mgr.is_osc_active():
                port = self._remote_mgr.get_osc_port()
                self._btn_remote_status.setText(f"📡 OSC: UDP {port}")
                self._btn_remote_status.setStyleSheet("color: #a855f7; font-weight: bold;")
            else:
                self._btn_remote_status.setText("📡 Remoto: OFF")
                self._btn_remote_status.setStyleSheet("color: #64748b;")

    def get_remote_state(self) -> dict[str, Any]:
        """Provide a complete real-time JSON snapshot for web remotes, Director Monitor, and OSC clients."""
        row, standby_cue = self._anchor_row_and_cue()
        active_cues_data = []
        layers_data: dict[str, Any] = {}

        # Default empty layer state for all active runtime layers (1-3, plus 4-6 in dual output)
        dual_active = bool(getattr(self, "_dual_output_active", False))
        active_slot_ids = (1, 2, 3, 4, 5, 6) if dual_active else (1, 2, 3)
        for l_idx in active_slot_ids:
            layers_data[str(l_idx)] = {
                "layer": l_idx,
                "is_live": False,
                "title": "— Inattivo / Nero —",
                "q_label": "",
                "cue_id": -1,
                "pos_sec": 0.0,
                "end_sec": 0.0,
                "start_sec": 0.0,
                "is_paused": False,
                "phase": "IDLE",
            }

        if hasattr(self, "_live_status") and hasattr(self._live_status, "_layer_labels"):
            for l_idx, bar in self._live_status._layer_labels.items():
                if bar._is_live:
                    cue_entry = {
                        "layer": bar._layer_idx,
                        "cue_id": bar._cue_id,
                        "title": bar._title or f"Media L{bar._layer_idx}",
                        "q_label": bar._q_label,
                        "pos_sec": round(bar._pos_sec, 2),
                        "end_sec": round(bar._end_sec, 2),
                        "start_sec": round(bar._start_sec, 2),
                        "is_paused": bar._is_paused,
                        "phase": bar._phase or "ON AIR",
                    }
                    active_cues_data.append(cue_entry)
                    layers_data[str(bar._layer_idx)] = {
                        "layer": bar._layer_idx,
                        "is_live": True,
                        "title": bar._title or f"Media L{bar._layer_idx}",
                        "q_label": bar._q_label,
                        "cue_id": bar._cue_id,
                        "pos_sec": round(bar._pos_sec, 2),
                        "end_sec": round(bar._end_sec, 2),
                        "start_sec": round(bar._start_sec, 2),
                        "is_paused": bar._is_paused,
                        "phase": bar._phase or "ON AIR",
                    }

        cues_data = []
        for idx, c in enumerate(self._cues):
            c_dur = c.out_point or c.hold_time or self._known_file_durations.get(c.file_path, 0.0) or getattr(c, "target_duration", 0.0) or 0.0
            cues_data.append({
                "index": idx,
                "id": c.cue_id,
                "name": c.name,
                "ref": format_cue_ref(idx, c),
                "type": c.media_type.value,
                "layer": c.layer,
                "output_target": getattr(c, "output_target", "A"),
                "status": c.status.value,
                "duration": round(float(c_dur), 2),
                "fade_in": round(float(getattr(c, "fade_in", 0.0) or 0.0), 1),
                "fade_out": round(float(getattr(c, "fade_out", 0.0) or 0.0), 1),
                "follow_mode": getattr(c, "follow_mode", "MANUAL"),
                "notes": getattr(c, "notes", ""),
                "surface_id": getattr(c, "surface_id", "default"),
                "is_standby": (idx == row),
            })

        sb_dur = 0.0
        if standby_cue:
            sb_dur = standby_cue.out_point or standby_cue.hold_time or self._known_file_durations.get(standby_cue.file_path, 0.0) or getattr(standby_cue, "target_duration", 0.0) or 0.0

        return {
            "show_title": Path(self._current_project_path).stem if self._current_project_path else "Nuovo Spettacolo",
            "is_live_mode": self.is_live_mode(),
            "is_paused": getattr(self, "_is_global_paused", False),
            "dual_output_active": dual_active,
            "current_index": row,
            "standby_cue": {
                "id": standby_cue.cue_id,
                "name": standby_cue.name,
                "ref": format_cue_ref(row, standby_cue),
                "type": standby_cue.media_type.value,
                "layer": standby_cue.layer,
                "duration": round(float(sb_dur), 2),
                "fade_in": round(float(getattr(standby_cue, "fade_in", 0.0) or 0.0), 1),
                "fade_out": round(float(getattr(standby_cue, "fade_out", 0.0) or 0.0), 1),
                "notes": getattr(standby_cue, "notes", ""),
            } if standby_cue else None,
            "active_cues": active_cues_data,
            "layers": layers_data,
            "cues": cues_data,
        }

    @Slot()
    def _on_remote_go(self) -> None:
        logger.info("[REMOTE] Triggering GO from Remote")
        if not self._cues:
            return
        if not self._manual_go_allowed():
            if self._remote_mgr:
                self._remote_mgr.trigger_state_broadcast()
            return
        if hasattr(self, "_earcon_mgr"):
            self._earcon_mgr.play_go()
        self._apply_inspector_to_cue()
        target_idx = self._go_target_index()
        self._remember_manual_go(target_idx)
        self._fire_cue_chain(target_idx)
        if self._remote_mgr:
            self._remote_mgr.trigger_state_broadcast()

    @Slot()
    def _on_remote_panic(self) -> None:
        logger.info("[REMOTE] Triggering PANIC from Remote")
        self._on_panic()
        if self._remote_mgr:
            self._remote_mgr.trigger_state_broadcast()

    @Slot()
    def _on_remote_blackout(self) -> None:
        logger.info("[REMOTE] Triggering BLACKOUT from Remote")
        self._on_blackout()
        if self._remote_mgr:
            self._remote_mgr.trigger_state_broadcast()

    @Slot()
    def _on_remote_pause_toggle(self) -> None:
        logger.info("[REMOTE] Toggling Pause from Remote")
        self.pause_all_toggled.emit()
        if self._remote_mgr:
            self._remote_mgr.trigger_state_broadcast()

    @Slot()
    def _on_remote_pause(self) -> None:
        logger.info("[REMOTE] Pausing show from Remote (idempotent)")
        self.pause_all_set.emit(True)
        if self._remote_mgr:
            self._remote_mgr.trigger_state_broadcast()

    @Slot()
    def _on_remote_resume(self) -> None:
        logger.info("[REMOTE] Resuming show from Remote (idempotent)")
        self.pause_all_set.emit(False)
        if self._remote_mgr:
            self._remote_mgr.trigger_state_broadcast()

    @Slot()
    def _on_remote_next_cue(self) -> None:
        if not self._cues:
            return
        cur = self._cue_list.currentRow()
        nxt = min(len(self._cues) - 1, (cur + 1) if cur >= 0 else 0)
        self._cue_list.setCurrentRow(nxt)
        if self._remote_mgr:
            self._remote_mgr.trigger_state_broadcast()

    @Slot()
    def _on_remote_prev_cue(self) -> None:
        if not self._cues:
            return
        cur = self._cue_list.currentRow()
        prv = max(0, (cur - 1) if cur > 0 else 0)
        self._cue_list.setCurrentRow(prv)
        if self._remote_mgr:
            self._remote_mgr.trigger_state_broadcast()

    def _resolve_remote_cue_index(self, target: Any) -> int | None:
        """Resolve an OSC/Web cue target by exact cue_id, q_label/name, or 1-based cue number."""
        if isinstance(target, int) and not isinstance(target, bool):
            for idx, c in enumerate(self._cues):
                if c.cue_id == target:
                    return idx
            # Match 1-based cue number (/cue/3/go -> 3rd cue) without silently aliasing 0-based index
            if 1 <= target <= len(self._cues):
                return target - 1
            return None
        if isinstance(target, str):
            target_clean = target.strip().lower()
            if not target_clean:
                return None
            for idx, c in enumerate(self._cues):
                q_lbl = (c.q_label or "").strip().lower()
                if str(c.cue_id) == target_clean or (q_lbl and q_lbl == target_clean) or c.name.lower() == target_clean:
                    return idx
            if target_clean.isdigit():
                num = int(target_clean)
                if 1 <= num <= len(self._cues):
                    return num - 1
        return None

    @Slot(object)
    def _on_remote_cue_go(self, target: Any) -> None:
        """Jump to and immediately execute specific cue by id, Q-label, or 1-based cue number."""
        if not self._cues:
            return
        found_idx = self._resolve_remote_cue_index(target)
        if found_idx is not None and 0 <= found_idx < len(self._cues):
            if not self._manual_go_allowed():
                if self._remote_mgr:
                    self._remote_mgr.trigger_state_broadcast()
                return
            logger.info("[REMOTE] Jump and fire cue at index %d (#%d)", found_idx, self._cues[found_idx].cue_id)
            self._cue_list.setCurrentRow(found_idx)
            self._remember_manual_go(found_idx)
            self._fire_cue_chain(found_idx)
            if self._remote_mgr:
                self._remote_mgr.trigger_state_broadcast()
        else:
            logger.warning("[REMOTE] Ignored cue_go for unknown target: %r", target)

    @Slot(object)
    def _on_remote_cue_select(self, target: Any) -> None:
        """Set standby selection to specific cue without executing."""
        if not self._cues:
            return
        found_idx = self._resolve_remote_cue_index(target)
        if found_idx is not None and 0 <= found_idx < len(self._cues):
            self._cue_list.setCurrentRow(found_idx)
            if self._remote_mgr:
                self._remote_mgr.trigger_state_broadcast()
        else:
            logger.warning("[REMOTE] Ignored cue_select for unknown target: %r", target)

    @Slot(float)
    def _on_remote_volume_change(self, vol: float) -> None:
        """Adjust volume from OSC or Web remote."""
        cue = self._selected_cue()
        if cue:
            cue.volume = max(0.0, min(1.0, vol))
            self._inspector.spin_volume.setValue(int(cue.volume * 100))
            if self._remote_mgr:
                self._remote_mgr.trigger_state_broadcast()

    @Slot()
    def _open_surface_mapping_dialog(self) -> None:
        """Open the visual Surface Mapping & Virtual Screen Studio Dialog (F7)."""
        dlg = SurfaceMappingDialog(
            self._output,
            surfaces=self._surfaces,
            parent=self,
            device_manager=self._device_mgr,
        )
        dlg.surfaces_changed.connect(self._on_surfaces_updated)
        if dlg.exec():
            self._on_surfaces_updated(dlg._surfaces)
        if hasattr(self, "_act_calib_guides"):
            self._act_calib_guides.blockSignals(True)
            self._act_calib_guides.setChecked(self._output.is_calibration_guides_visible())
            self._act_calib_guides.blockSignals(False)

    def _on_surfaces_updated(self, surfaces: list[SurfaceDefinition]) -> None:
        """Propagate updated surfaces list to OutputWindow, Inspector, and modified show state."""
        self._surfaces = [s.clone() for s in surfaces]
        self._output.set_surfaces(self._surfaces)
        if getattr(self, "_output_b", None) is not None:
            self._output_b.set_surfaces(self._surfaces)
        self._inspector.set_available_surfaces(self._surfaces)
        self._mark_modified(True)
        if self._live_mirror_active:
            self._mirror_active_cue_to_live()
        else:
            live_cues = [c for c in self._cues if c.status == CueStatus.LIVE]
            for c in live_cues:
                self._push_cue_to_output(c)

    @Slot(bool)
    def _toggle_calibration_guides(self, enabled: bool) -> None:
        """Toggle live on-projector calibration overlay (Shift+F7)."""
        self._output.set_calibration_guides_visible(enabled)
        if hasattr(self, "_act_calib_guides"):
            self._act_calib_guides.blockSignals(True)
            self._act_calib_guides.setChecked(self._output.is_calibration_guides_visible())
            self._act_calib_guides.blockSignals(False)

    def set_known_duration(self, file_path: str, dur_sec: float) -> None:
        """Cache the real duration measured for *file_path*.

        Durations are probed once per media file (FFmpeg) and reused for the
        progress bars and the remote snapshot: re-probing during a show would
        stall the UI thread, so the value is memoised here.
        """
        if file_path and dur_sec > 0:
            self._known_file_durations[file_path] = dur_sec
            self._sync_live_view()

    def set_cue_phase_badge(self, cue_id: int, badge_text: str) -> None:
        """Show a transient phase badge (PRE-DELAY, FADE OUT, …) on a cue.

        Passing an empty *badge_text* clears the badge. The live view is only
        refreshed when the text actually changes, so the 30 fps progress timer
        does not repaint the list needlessly.
        """
        prev = self._live_phase_tags.get(cue_id, "")
        if badge_text:
            self._live_phase_tags[cue_id] = badge_text
        else:
            self._live_phase_tags.pop(cue_id, None)
        if prev != badge_text:
            if hasattr(self, "_live_show_panel") and self._live_show_panel.update_phase_badge(cue_id, badge_text):
                return
            self._sync_live_view()

    def set_global_paused(self, paused: bool, *, silent: bool = False) -> None:
        """Mirror the global transport pause (PANIC/PAUSE) in the live panel.

        A short earcon confirms the state change to the operator even without
        looking at the screen — useful when pause is triggered from a remote.
        """
        paused = bool(paused)
        changed = (getattr(self, "_is_global_paused", False) != paused)
        self._is_global_paused = paused
        if not silent and changed and hasattr(self, "_earcon_mgr"):
            self._earcon_mgr.play_pause()
        if hasattr(self, "_live_show_panel"):
            self._live_show_panel.set_global_paused(paused)

    def _sync_live_view(self) -> None:
        self._update_go_button_text()
        if not hasattr(self, "_live_show_panel"):
            return
        standby_row, _ = self._anchor_row_and_cue()
        if standby_row < 0 and self._cues:
            standby_row = 0
        has_live_inf_sec = any(
            c.status == CueStatus.LIVE and any(s.loops == 0 and not s.skip for s in c.sections)
            for c in self._cues
        )
        self._live_show_panel.sync_cues(
            self._cues,
            standby_row,
            self._known_file_durations,
            self._live_phase_tags,
            show_break_loop=has_live_inf_sec,
            layer_conflicts=self._layer_conflicts,
        )

    def _update_live_layer_label(self, cue: Cue, preserve_timing: bool = False) -> None:
        dur = 0.0
        if cue.media_type == MediaType.IMAGE and cue.hold_time > 0:
            dur = cue.hold_time
        elif self._selected_cue() is cue and self._active_test_duration > 0:
            dur = self._active_test_duration
        elif cue.file_path in self._known_file_durations:
            dur = self._known_file_durations[cue.file_path]
        for sp in self._for_each_status_panel():
            sp.set_layer_live(
                cue,
                duration_sec=dur,
                preserve_timing=preserve_timing,
                layer_idx=self._runtime_slot(cue),
            )

    def update_live_layer_phase(self, layer: int, cue: Cue, phase: str, elapsed: float, total: float) -> None:
        """Forward the current automation phase of *layer* to every layer panel.

        Called by the show scheduler on each tick; the panel draws the phase
        name together with elapsed/total so the operator sees section loops
        and pre-delays without watching the cue list.
        """
        for sp in self._for_each_status_panel():
            sp.set_layer_phase_progress(layer, cue, phase, elapsed, total)

    def update_live_layer_progress(
        self,
        layer: int,
        pos_sec: float,
        end_sec: float | None = None,
        start_sec: float | None = None,
        is_looping_inf: bool | None = None,
    ) -> None:
        """Push playback position to the layer progress bars.

        *start_sec*/*end_sec* delimit the section being played: the bar shows
        the position inside the section, not the whole file, which is what the
        operator needs when a cue is split into loops.
        """
        for sp in self._for_each_status_panel():
            sp.set_layer_progress(
                layer,
                pos_sec,
                start_sec=start_sec,
                end_sec=end_sec,
                is_looping_inf=is_looping_inf,
            )

    def set_live_layer_paused(self, layer: int, paused: bool) -> None:
        """Toggle the paused indicator on the panel of *layer*."""
        for sp in self._for_each_status_panel():
            sp.set_layer_paused(layer, paused)

    def _reset_live_label(self, layer: int) -> None:
        for sp in self._for_each_status_panel():
            sp.reset_layer(layer)

    def promote_cue_to_live(self, cue: Cue) -> None:
        """Promote a cue to LIVE status once its Pre-Delay completes."""
        self._live_phase_tags.pop(cue.cue_id, None)
        ShowEngine.promote_to_live(self._cues, cue, dual_active=self._dual_output_active)
        self._update_live_layer_label(cue)
        self._refresh_cue_list(keep_selection=True)
        self._sync_live_view()

    def finish_live_cue_status(self, cue: Cue) -> None:
        """Mark cue finished (LOADED) and clean up phase badges safely (even after Undo)."""
        self._live_phase_tags.pop(cue.cue_id, None)
        if cue.status == CueStatus.LIVE:
            cue.status = CueStatus.LOADED
        for item in self._cues:
            if item.cue_id == cue.cue_id and item.status == CueStatus.LIVE:
                item.status = CueStatus.LOADED
        self._refresh_cue_list(keep_selection=True)
        self._sync_live_view()

    def trigger_auto_follow_from(self, finished_cue: Cue) -> None:
        """Start the next cue in sequence when an AUTO_FOLLOW cue completes."""
        next_idx = ShowEngine.auto_follow_target(self._cues, finished_cue)
        if next_idx >= 0:
            self._fire_cue_chain(next_idx)

    @Slot(int)
    def _on_live_double_click_armed(self, row: int) -> None:
        """Double-click in LIVE armed the cue as next instead of starting it."""
        if 0 <= row < len(self._cues):
            ref = format_cue_ref(row, self._cues[row])
            self._status_label.setText(f"{ref} pronta — premi GO per avviarla (il doppio clic in LIVE non avvia)")

    @Slot(int)
    def _on_live_row_double_clicked(self, row: int) -> None:
        """Double-click on the live list (only when ``live/double_click_fires`` is on): a GO."""
        if 0 <= row < len(self._cues) and self._manual_go_allowed():
            self._remember_manual_go(row)
            self._fire_cue_chain(row)

    @Slot(int)
    def _on_live_row_forced(self, row: int) -> None:
        """Right-click "start this cue now": deliberate, skips the GO guards."""
        if 0 <= row < len(self._cues):
            self._remember_manual_go(row)
            self._fire_cue_chain(row)

    @Slot(int, int)
    def _on_cue_cell_double_clicked(self, row: int, col: int) -> None:
        if not (0 <= row < len(self._cues)):
            return
        if col == 0:
            self._on_go()
        elif col in (1, 2):
            item = self._cue_list.item(row, col)
            if item is not None:
                self._cue_list.editItem(item)

    @Slot(QTableWidgetItem)
    def _on_cue_item_changed(self, item: QTableWidgetItem) -> None:
        """Handle inline editing of Q (col 1) or Nome (col 2) in the cue table."""
        if self._updating_cue_list:
            return
        row, col = item.row(), item.column()
        if not (0 <= row < len(self._cues)) or col not in (1, 2):
            return

        cue = self._cues[row]
        new_val = item.text().strip()
        old_val = cue.q_label if col == 1 else cue.name

        if col == 2 and not new_val:
            self._updating_cue_list = True
            self._cue_list.blockSignals(True)
            item.setText(old_val)
            self._cue_list.blockSignals(False)
            self._updating_cue_list = False
            return

        if new_val == old_val:
            return

        if self._undo.is_debounce_active():
            self._commit_undo_point()
        if col == 1:
            cue.q_label = new_val
        else:
            cue.name = new_val

        self._updating_cue_list = True
        self._cue_list.blockSignals(True)
        item.setText(new_val)
        tooltip = self._cue_tooltip(row, cue)
        for c_idx in range(3):
            cell = self._cue_list.item(row, c_idx)
            if cell is not None:
                cell.setToolTip(tooltip)
        self._cue_list.blockSignals(False)
        self._updating_cue_list = False

        self._sync_inspector_header_and_text(row, cue)
        if cue.status == CueStatus.LIVE:
            self._update_live_layer_label(cue, preserve_timing=True)
        self._commit_undo_point()
        self._mark_modified(True)
        self._auto_save()

    def _update_selected_list_item(self, cue: Cue) -> None:
        """Lightweight in-place update for the active table row without focus stealing."""
        row = self._cue_list.currentRow()
        if not (0 <= row < len(self._cues)):
            return
        self._updating_cue_list = True
        self._cue_list.blockSignals(True)
        try:
            self._populate_cue_row(row, cue, is_standby=(cue.status != CueStatus.LIVE))
        finally:
            self._cue_list.blockSignals(False)
            self._updating_cue_list = False
        self._sync_live_view()

        ref = format_cue_ref(row, cue)
        self._inspector.setTitle(f"ISPETTORE CUE — {ref} [{cue.media_type.value}] '{cue.name}'")
        self._update_cue_readouts(row, cue)
        if cue.status == CueStatus.LIVE:
            self._update_live_layer_label(cue, preserve_timing=True)

    def _refresh_rows_in_place(self, rows: list[int]) -> None:
        """Update table cell visuals for *rows* in place without altering selection."""
        self._layer_conflicts = detect_layer_conflicts(
            self._cues, dual_active=self._dual_output_active
        )
        anchor_row, _ = self._anchor_row_and_cue()
        self._updating_cue_list = True
        self._cue_list.blockSignals(True)
        try:
            for row in rows:
                if 0 <= row < len(self._cues):
                    cue = self._cues[row]
                    is_standby = (row == anchor_row and cue.status != CueStatus.LIVE)
                    self._populate_cue_row(row, cue, is_standby=is_standby)
        finally:
            self._cue_list.blockSignals(False)
            self._updating_cue_list = False
        self._sync_live_view()

    def _refresh_cue_list(self, keep_selection: bool = True,
                          select_row: int | None = None) -> None:
        """Rebuild the 3-column table from the cue list with progressive row numbers."""
        self._layer_conflicts = detect_layer_conflicts(
            self._cues, dual_active=self._dual_output_active
        )
        prev_selected = self._selected_rows() if (keep_selection and select_row is None) else []

        if select_row is not None:
            target_row = select_row
        elif keep_selection:
            target_row = self._cue_list.currentRow()
            if target_row < 0 and 0 <= self._current_index < len(self._cues):
                target_row = self._current_index
        else:
            target_row = -1

        total_cues = len(self._cues)
        group_count = sum(1 for c in self._cues if c.media_type == MediaType.GROUP)
        if total_cues == 0:
            self._lbl_cue_count.setText("0 Cue")
            self._lbl_cue_standby.setText("Standby: Nessuna")
            self._update_inspector(None)
        else:
            if group_count > 0:
                self._lbl_cue_count.setText(f"{total_cues} Cue ({group_count} scene)")
            else:
                self._lbl_cue_count.setText(f"{total_cues} Cue")
            standby_row = target_row if (0 <= target_row < total_cues) else 0
            standby_cue = self._cues[standby_row]
            self._lbl_cue_standby.setText(
                f"Standby: {format_cue_ref(standby_row, standby_cue)} [{standby_cue.media_type.value}]"
            )

        self._updating_cue_list = True
        self._cue_list.blockSignals(True)
        try:
            self._cue_list.setRowCount(total_cues)
            self._cue_list._last_emitted_row = -1
            for i, cue in enumerate(self._cues):
                is_standby = (total_cues > 0 and i == target_row and cue.status != CueStatus.LIVE)
                self._populate_cue_row(i, cue, is_standby=is_standby)

            valid_prev = [r for r in prev_selected if 0 <= r < total_cues]
            if len(valid_prev) > 1 and select_row is None and keep_selection:
                self._cue_list.select_rows(valid_prev, anchor_row=target_row if target_row in valid_prev else valid_prev[0])
            elif 0 <= target_row < total_cues:
                self._cue_list.setCurrentRow(target_row)
            else:
                self._cue_list.clearSelection()
                self._last_selection_sig = None
        finally:
            self._cue_list.blockSignals(False)
            self._updating_cue_list = False
        self._sync_live_view()

    def _selected_rows(self) -> list[int]:
        if not hasattr(self, "_cue_list"):
            return []
        return [r for r in self._cue_list.selected_rows() if 0 <= r < len(self._cues)]

    def _selected_cues(self) -> list[Cue]:
        return [self._cues[r] for r in self._selected_rows()]

    def _anchor_row_and_cue(self) -> tuple[int, Cue | None]:
        rows = self._selected_rows()
        if not rows:
            return -1, None
        curr = self._cue_list.currentRow()
        anchor_row = curr if curr in rows else rows[0]
        return anchor_row, self._cues[anchor_row]

    def _selected_cue(self) -> Cue | None:
        _, cue = self._anchor_row_and_cue()
        return cue
