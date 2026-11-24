"""Stage 4 (pictures and video) mixin for MainWindow.

- 4.4 "hold the last frame": which cues show their held last frame (main.py's
  ``HeldFrameController`` reports it here), the card and the layer bar of such
  a cue, and what the projector gets when it is pushed there again.
- 4.4 thumbnails in the editing list (on / off, off with the Eco profile).
- 4.4 the preview never stays on the projector in the rehearsal or the show.
- 4.5 (MultiPlay) the output windows: bring them to the front, clear them.
"""

from __future__ import annotations

from i18n import tr

from ui.main_window._common import *  # noqa: F403,F401,F405


class _PictureToolsMixin:
    # ── 4.4 Hold the last frame ───────────────────────────────────────
    def _last_frames(self) -> dict[int, tuple[int, Any]]:
        """cue_id -> (runtime slot, (frame, opacity) or None) of the cues holding their last frame."""
        held = getattr(self, "_last_frame_held", None)
        if held is None:
            held = self._last_frame_held = {}
        return held

    def set_last_frame_held(self, cue_id: int, slot: int, on: bool, kept: Any = None) -> None:
        """main.py: *cue_id* shows (or no longer shows) its held last frame on runtime *slot*."""
        held = self._last_frames()
        if on:
            held[int(cue_id)] = (int(slot), kept)
            cue = next((c for c in self._cues if c.cue_id == int(cue_id)), None)
            if cue is not None:
                self._show_last_frame_held(cue, int(slot))
        else:
            held.pop(int(cue_id), None)
        self._refresh_now_playing()

    def is_last_frame_held(self, cue: Cue | None) -> bool:
        """*cue* ended and its last frame is on air (it is LIVE but plays nothing)."""
        return (cue is not None and cue.status == CueStatus.LIVE
                and int(cue.cue_id) in getattr(self, "_last_frame_held", {}))

    def _show_last_frame_held(self, cue: Cue, slot: int) -> None:
        """The layer bar and the clocks of a held last frame: a still, no time."""
        self._live_clocks.clear(slot)
        self._live_phase_tags.pop(cue.cue_id, None)
        self._paused_slots.discard(slot)
        for sp in self._for_each_status_panel():
            if hasattr(sp, "set_layer_held"):
                sp.set_layer_held(slot, cue)

    def _push_held_frame(self, cue: Cue) -> bool:
        """Put the held last frame of *cue* on its output again (surfaces changed, mirror off)."""
        entry = self._last_frames().get(cue.cue_id)
        kept = entry[1] if entry is not None else None
        if not self.is_last_frame_held(cue) or not kept:
            return False
        frame, opacity = kept
        self._output_for_cue(cue).show_mirrored_frame(
            cue.layer, frame, opacity=opacity, crop=cue.crop, scale=cue.scale,
            pos_x=cue.position_x, pos_y=cue.position_y, aspect_ratio=cue.aspect_ratio,
            surface_id=getattr(cue, "surface_id", "default") or "default", rotation=cue.rotation,
        )
        return True

    # ── 4.4 Thumbnails in the editing list ────────────────────────────
    def _add_thumbnail_action(self, menu) -> None:
        """View menu: thumbnails in the list on / off (off by default with the Eco profile)."""
        self._act_thumbnails = QAction("🖼 Miniature nella lista", self, checkable=True)
        self._act_thumbnails.setToolTip("Una piccola immagine di foto e video nella lista; "
                                        "su un computer lento meglio spenta")
        self._act_thumbnails.toggled.connect(self._set_thumbnails_on)
        menu.addAction(self._act_thumbnails)
        self._apply_thumbnail_setting()

    def _thumbnail_cache(self):
        cache = getattr(self, "_thumbs", None)
        if cache is None:
            from ui.thumbnails import ThumbnailCache

            cache = self._thumbs = ThumbnailCache(getattr(self, "_thread_pool", None), self)
            cache.ready.connect(lambda: self._cue_list.viewport().update() if hasattr(self, "_cue_list") else None)
        return cache

    def _thumbnail_for(self, path: str, kind: str):
        """The delegate's source: a ready thumbnail or None (never in the show)."""
        if self._live_mode:
            return None
        return self._thumbnail_cache().get(path, kind)

    def _apply_thumbnail_setting(self) -> None:
        from ui.thumbnails import AUTO, SETTINGS_KEY, thumbnails_wanted

        setting = str(QSettings("BlindCue", "BlindCue").value(SETTINGS_KEY, AUTO))
        dm = getattr(self, "_device_mgr", None)
        try:
            profile = dm.get_effective_profile() if dm is not None else ""
        except Exception:  # noqa: BLE001 - no profile: the default (on)
            profile = ""
        self._thumbs_on = thumbnails_wanted(setting, profile)
        act = getattr(self, "_act_thumbnails", None)
        if act is not None:
            act.blockSignals(True)
            act.setChecked(self._thumbs_on)
            act.blockSignals(False)
        table = getattr(self, "_cue_list", None)
        if table is not None:
            table.thumbnail_source = self._thumbnail_for if self._thumbs_on else None
            table.viewport().update()

    def _set_thumbnails_on(self, on: bool) -> None:
        from ui.thumbnails import OFF, ON, SETTINGS_KEY

        QSettings("BlindCue", "BlindCue").setValue(SETTINGS_KEY, ON if on else OFF)
        self._apply_thumbnail_setting()
        self._status_label.setText(tr("Miniature nella lista: accese") if on else tr("Miniature nella lista: spente"))

    # ── 4.4 The preview never stays on the projector ─────────────────
    def _end_preview_on_projector(self) -> None:
        """Entering the rehearsal or the show: "show on the projector" goes off and its picture goes away.

        SCS does not even keep this switch between sessions: a preview the
        audience was not meant to see must never survive into the show.
        """
        mirror = getattr(getattr(self, "_preview_panel", None), "btn_live_mirror", None)
        if mirror is not None and mirror.isChecked():
            mirror.setChecked(False)  # _on_live_mirror_toggled(False) puts back only what is on air
        elif self._live_mirror_active or self._last_mirrored_layer is not None:
            self._live_mirror_active = False
            self._restore_live_output()

    # ── 4.4 (MultiPlay) Output windows ────────────────────────────────
    def _add_output_window_actions(self, menu) -> None:
        """Show → Devices: the output windows (identify the screens, to the front, clear)."""
        menu.addSeparator()
        menu.addAction(QAction("🔢 Identifica gli schermi", self, triggered=self._identify_screens_from_menu))
        act_front = QAction("🖥 Porta le uscite in primo piano", self, triggered=self.bring_outputs_to_front)
        act_front.setToolTip("Le finestre di uscita tornano sul loro schermo e sopra le altre finestre")
        menu.addAction(act_front)
        act_clear = QAction("🧹 Pulisci le uscite", self, triggered=self.clear_outputs)
        act_clear.setToolTip("Immagini, video e ultimi fotogrammi sfumano dai proiettori; il suono continua")
        menu.addAction(act_clear)

    def _identify_screens_from_menu(self) -> None:
        """The numbers on every screen - never while something is on air (the audience would see them)."""
        if any(c.status == CueStatus.LIVE for c in self._cues) or self._live_phase_tags:
            self._status_label.setText(tr("Qualcosa è in onda: i numeri degli schermi non compaiono ora"))
            if hasattr(self, "_earcon_mgr"):
                self._earcon_mgr.play_alert()
            return
        self._show_screen_numbers()

    def _outputs_shown(self) -> list:
        return [out for out in (self._output, getattr(self, "_output_b", None))
                if out is not None and out.isVisible()]

    def bring_outputs_to_front(self) -> None:
        """Every output window back on its screen and on top (after another program covered it)."""
        outs = self._outputs_shown()
        for out in outs:
            if out.isMinimized():
                out.setWindowState(out.windowState() & ~Qt.WindowState.WindowMinimized)
            ensure = getattr(out, "ensure_on_target_screen", None)
            if ensure is not None:
                ensure()
            out.raise_()
        if hasattr(self, "_ensure_director_visible"):
            self._ensure_director_visible()  # never left under a full-screen output
        self._status_label.setText(tr("Uscite in primo piano: {}").format(len(outs)) if outs
                                   else tr("Nessuna uscita aperta"))
        logger.info("[OUTPUT] %d output window(s) brought to the front", len(outs))

    def clear_outputs(self) -> None:
        """The projectors show only Layer 0: pictures, videos and held frames fade out; the sound plays on.

        Also takes away whatever a preview left there (it belongs to no cue)
        and switches "show on the projector" off, so the next selected cue
        does not come back.
        """
        mirror = getattr(getattr(self, "_preview_panel", None), "btn_live_mirror", None)
        if mirror is not None and mirror.isChecked():
            mirror.setChecked(False)  # its restore runs first; the clearing below wins
        slots = sorted({self._runtime_slot(c) for c in self._cues if c.status == CueStatus.LIVE
                        and c.media_type in (MediaType.IMAGE, MediaType.VIDEO)})
        for slot in slots:
            self.mark_layer_stopped(slot)
            self.layer_clear_requested.emit(slot)  # main.py: the cue's own fade-out (0.2 s without one)
        for slot in (1, 2, 3, 4, 5, 6):
            out = self._output if slot <= 3 else getattr(self, "_output_b", None)
            if slot not in slots and out is not None:
                out.clear_layer(slot if slot <= 3 else slot - 3)  # sound on this layer plays on
        self._last_mirrored_layer = None
        self._sync_live_view()
        self._status_label.setText(tr("Uscite pulite: immagini e video sfumano, il suono continua"))
        logger.info("[OUTPUT] Outputs cleared (%d layer(s) with pictures faded)", len(slots))
