"""Preview Mute & Live Layer Controls mixin for MainWindow."""

from __future__ import annotations

from ui.main_window._common import *  # noqa: F403,F401,F405
from ui.main_window._common import (  # noqa: F401
    _AutosaveWorker,
    _DEFAULT_TOP_RATIOS,
    _MEDIA_ICONS,
    ShowEngine,
)


class _LiveLayerMixin:
    @Slot(bool)
    def _on_preview_mute_toggled(self, is_muted: bool) -> None:
        self._preview_panel.update_mute_style()
        self.preview_mute_toggled.emit(is_muted)
        state_txt = "Silenzioso (Muto)" if is_muted else "Ascolto Attivo"
        self._status_label.setText(f"Audio Preview: {state_txt}")

    @Slot(int)
    def _on_clear_live_layer(self, layer: int) -> None:
        self._reset_live_label(layer)
        runtime = int(layer)
        if runtime > 3:
            # Output B: runtime 4-6 maps back to the cue layer 1-3.
            ShowEngine.clear_layer(
                self._cues, runtime - 3, output_target="B",
                dual_active=self._dual_output_active,
            )
            layer_txt = f"Layer {runtime - 3} · Uscita B"
        else:
            ShowEngine.clear_layer(
                self._cues, runtime, output_target="A",
                dual_active=self._dual_output_active,
            )
            layer_txt = f"Layer {runtime}"
        self._refresh_cue_list()
        self.layer_clear_requested.emit(runtime)
        self._status_label.setText(f"{layer_txt} arrestato e rimosso dal Live")
        logger.info("[LIVE STATUS] Cleared runtime layer %d", runtime)
