"""Layer 0 (Tappo) mixin for MainWindow.

Layer 0 is the always-on background image shown on every projector when no cue
is live: the show looks "closed" instead of black. It is mirrored on both
outputs and on the preview monitor so the operator sees exactly what the
audience sees.
"""

from __future__ import annotations

from ui.main_window._common import *  # noqa: F403,F401,F405
from ui.main_window._common import (  # noqa: F401
    _AutosaveWorker,
    _DEFAULT_TOP_RATIOS,
    _MEDIA_ICONS,
    _demote_live_on_layer,
)


class _Layer0Mixin:
    def set_layer0_image(self, file_path: str | None) -> bool:
        """Apply *file_path* as Layer-0 background on both outputs and the preview.

        Returns ``False`` when the image cannot be loaded, leaving the previous
        tappo untouched so the projector never goes black.
        """
        if self._output.set_layer0_image(file_path):
            if getattr(self, "_output_b", None) is not None:
                self._output_b.set_layer0_image(file_path)
            self._layer0_image = file_path
            self._live_status.set_layer0_label(file_path)
            self._preview_monitor.set_layer0_image(file_path)
            return True
        return False

    @Slot()
    def _on_choose_layer0(self) -> None:
        """Let the operator pick a new tappo image from the file system."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Seleziona Immagine di Tappo (Layer 0)",
            "",
            "Immagini (*.png *.jpg *.jpeg *.bmp *.webp *.svg);;Tutti i file (*)",
        )
        if file_path:
            if self.set_layer0_image(file_path):
                self._mark_modified(True)
                self._auto_save()
                self._status_label.setText(f"Tappo (Layer 0) impostato: {Path(file_path).name}")
            else:
                QMessageBox.warning(self, "File non valido", "Impossibile caricare l'immagine di tappo selezionata.")

    @Slot()
    def _on_reset_layer0(self) -> None:
        self._output.reset_layer0_default()
        if getattr(self, "_output_b", None) is not None:
            self._output_b.reset_layer0_default()
        self._layer0_image = None
        self._live_status.set_layer0_label(None)
        self._preview_monitor.set_layer0_image(str(DEFAULT_LOGO_PATH))
        self._mark_modified(True)
        self._auto_save()
        self._status_label.setText("Tappo (Layer 0) ripristinato al logo predefinito")
