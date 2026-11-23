"""EBU R128 Loudness Normalization & Jam / Contest Mode mixin for MainWindow."""

from __future__ import annotations

from ui.main_window._common import *  # noqa: F403,F401,F405
from ui.main_window._common import (  # noqa: F401
    _AutosaveWorker,
    _DEFAULT_TOP_RATIOS,
    _MEDIA_ICONS,
    _demote_live_on_layer,
)


class _LoudnessMixin:
    @Slot(bool)
    def _set_jam_mode(self, enabled: bool) -> None:
        """Toggle global Jam / Contest EBU R128 auto-gain normalization mode."""
        enabled = bool(enabled)
        if hasattr(self, "_update_variant_status_bar"):
            QTimer.singleShot(0, self._update_variant_status_bar)  # shown while on, in every layout
        if self._jam_mode_active == enabled:
            return
        self._jam_mode_active = enabled
        if hasattr(self, "_act_jam_mode"):
            self._act_jam_mode.blockSignals(True)
            self._act_jam_mode.setChecked(enabled)
            self._act_jam_mode.blockSignals(False)
        if hasattr(self, "_btn_jam_mode"):
            self._btn_jam_mode.blockSignals(True)
            self._btn_jam_mode.set_active(enabled, silent=True)
            self._btn_jam_mode.blockSignals(False)

        if enabled:
            self._status_label.setText("MODALITÀ JAM / CONTEST ATTIVA — Auto-Gain EBU R128 (-16 LUFS) abilitato su tutti i canali")
            for c in self._cues:
                if c.media_type in (MediaType.VIDEO, MediaType.AUDIO) and c.loudness_lufs is None:
                    self._launch_loudness_scan(c)
        else:
            self._status_label.setText("MODALITÀ JAM / CONTEST DISATTIVATA — Ripristinati livelli originali delle cue")

        # Hot-update active live / test players
        for c in self._cues:
            if c.status == CueStatus.LIVE or self._selected_cue() is c:
                self.live_automation_updated.emit(c)

    def _launch_loudness_scan(self, cue: Cue) -> None:
        """Launch background EBU R128 loudness analysis for *cue*."""
        if not (cue.media_type in (MediaType.VIDEO, MediaType.AUDIO) and os.path.isfile(cue.file_path)):
            return

        def _on_finished(fpath: str, lufs: float, peak: float, gain_db: float) -> None:
            if cue.file_path == fpath:
                cue.loudness_lufs = lufs
                cue.true_peak_dbfs = peak
                cue.auto_gain_db = gain_db
                sign = "+" if gain_db > 0 else ""
                if self._selected_cue() is cue:
                    self._inspector.set_loudness_result(lufs, peak, gain_db)
                    self._status_label.setText(
                        f"Analisi Loudness per '{cue.name}': {lufs:.1f} LUFS (Peak {peak:.1f} dBFS → Gain {sign}{gain_db:.1f} dB)"
                    )
                if cue.normalize_audio or self._jam_mode_active:
                    self.live_automation_updated.emit(cue)

        def _on_error(fpath: str, err: str) -> None:
            if cue.file_path == fpath and self._selected_cue() is cue:
                self._status_label.setText(f"Analisi Loudness non riuscita per '{cue.name}': {err}")

        scanner = LoudnessScanner(cue.file_path, target_lufs=-16.0)
        scanner.signals.finished.connect(_on_finished)
        scanner.signals.error.connect(_on_error)
        self._thread_pool.start(scanner)

    @Slot()
    def _on_scan_loudness_requested(self) -> None:
        cue = self._selected_cue()
        if cue is not None and cue.media_type in (MediaType.VIDEO, MediaType.AUDIO):
            self._status_label.setText(f"Scansione Loudness EBU R128 per '{cue.name}' in corso...")
            self._launch_loudness_scan(cue)

    @Slot(bool)
    def _on_normalize_cue_toggled(self, checked: bool) -> None:
        cue = self._selected_cue()
        if cue is None or cue.media_type not in (MediaType.VIDEO, MediaType.AUDIO):
            return
        cue.normalize_audio = checked
        if checked and cue.loudness_lufs is None:
            self._status_label.setText(f"Calcolo guadagno EBU R128 per '{cue.name}'...")
            self._launch_loudness_scan(cue)
        else:
            self.live_automation_updated.emit(cue)
        self._mark_modified(True)

    @Slot()
    def _on_optimize_dynamics_requested(self) -> None:
        cue = self._selected_cue()
        if cue is None or cue.media_type not in (MediaType.VIDEO, MediaType.AUDIO):
            return
        if not os.path.isfile(cue.file_path):
            self._status_label.setText("File sorgente non trovato per l'ottimizzazione dinamica.")
            return

        self._status_label.setText(f"Compressione dinamica e normalizzazione EBU R128 per '{cue.name}' in corso...")

        def _on_finished(orig_path: str, opt_path: str) -> None:
            if cue.file_path == orig_path or (cue.original_file_path and cue.original_file_path == orig_path):
                if cue.original_file_path is None:
                    cue.original_file_path = orig_path
                cue.file_path = opt_path
                cue.loudness_lufs = -16.0
                cue.true_peak_dbfs = -1.5
                cue.auto_gain_db = 0.0
                cue.normalize_audio = True

                if self._selected_cue() is cue:
                    self._inspector.set_loudness_result(-16.0, -1.5, 0.0)
                    self._inspector.btn_restore_original.setVisible(True)
                    self._request_waveform(cue)
                    self._render_cue_in_preview(cue, load_image=False)

                self._status_label.setText(f"Dinamica ottimizzata con successo per '{cue.name}' (-16 LUFS, Limiter -1.5 dBFS)")
                self._mark_modified(True)
                self.live_automation_updated.emit(cue)

        def _on_error(orig_path: str, err: str) -> None:
            self._status_label.setText(f"Errore ottimizzazione dinamica: {err}")

        optimizer = DynamicsOptimizer(cue.file_path, target_lufs=-16.0)
        optimizer.signals.finished.connect(_on_finished)
        optimizer.signals.error.connect(_on_error)
        self._thread_pool.start(optimizer)

    @Slot()
    def _on_restore_original_requested(self) -> None:
        cue = self._selected_cue()
        if cue is None or not cue.original_file_path:
            return
        cue.file_path = cue.original_file_path
        cue.original_file_path = None
        cue.loudness_lufs = None
        cue.true_peak_dbfs = None
        cue.auto_gain_db = 0.0
        cue.normalize_audio = False

        self._inspector.btn_restore_original.setVisible(False)
        self._inspector.lbl_loudness_info.setText("📊 Loudness: Non analizzato")
        self._inspector.lbl_loudness_info.setStyleSheet(
            "background-color: #0b111a; color: #94a3b8; border: 1px solid #1e293b; "
            "border-radius: 4px; font-family: monospace; font-size: 10px; padding: 4px 6px;"
        )
        self._inspector.chk_normalize_cue.blockSignals(True)
        self._inspector.chk_normalize_cue.setChecked(False)
        self._inspector.chk_normalize_cue.blockSignals(False)

        self._request_waveform(cue)
        self._render_cue_in_preview(cue, load_image=False)
        self._status_label.setText(f"File originale ripristinato per '{cue.name}'")
        self._mark_modified(True)
        self.live_automation_updated.emit(cue)
