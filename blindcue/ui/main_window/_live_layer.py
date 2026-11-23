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
        runtime = int(layer)
        # Output B: runtime 4-6 maps back to the cue layer 1-3.
        layer_txt = f"Layer {runtime - 3} · Uscita B" if runtime > 3 else f"Layer {runtime}"
        self.mark_layer_stopped(runtime)
        self.layer_clear_requested.emit(runtime)
        self._status_label.setText(f"{layer_txt} arrestato e rimosso dal Live")
        logger.info("[LIVE STATUS] Cleared runtime layer %d", runtime)
