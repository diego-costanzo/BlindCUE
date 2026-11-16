"""Main window package for BlindCue.

The director/control panel is split into small mixin modules. This
package re-exports the composed ``MainWindow`` and the UI helpers that
previously lived in the single ``main_window.py`` module, so existing
imports keep working unchanged.

Orientation map (one mixin = one responsibility):

===================================  =========================================
``_window_setup``                    window flags, duplicazione schermo
``_layout``                          lock larghezze pannelli, layout standard
``_menu``                            menu bar, composizione UI, status panel
``_cue_manip``                       aggiunta/rimozione/duplicazione cue
``_cue_table``                       popolamento tabella, badge, monitor A/B
``_selection``                       selezione cue e live mirror
``_inspector``                       ispettore + interazioni waveform
``_transport``                       GO / blackout / panic / trasporto
``_live_layer``                      mute anteprima e layer live
``_envelope``                        fade, keyframe, sezioni
``_previz``                          player anteprima immagini (opacity)
``_preview``                         pass-through video verso l'anteprima
``_waveform`` / ``_waveform_worker`` waveform: layout e worker in background
``_groups``                          cue di gruppo e contenitori scena
``_loudness``                        normalizzazione EBU R128 e jam mode
``_layer0``                          immagine "tappo" di Layer 0
``_remote``                          controllo remoto LAN (Web/OSC)
``_undo``                            integrazione undo/redo
``_persistence``                     salvataggio, autosave, crash recovery
``_common``                          import condivisi + worker autosave
===================================  =========================================

Regola pratica per chi modifica il codice: aggiungi qui un nuovo file
``_nome.py`` con una sola responsabilità, dichiaralo come mixin di
``MainWindow`` in ``window.py`` e non chiamare mai direttamente widget di
un altro mixin: usa gli attributi già creati in ``_window_setup``/``_menu``.
"""

from ui.main_window._common import (
    CueSequenceTable,
    CueTableDelegate,
    DropZone,
    InPointSpinBox,
    OutPointSpinBox,
    SmartDoubleSpinBox,
    StudioPreviewMonitor,
    WaveformPanel,
    WaveformWidget,
)
from ui.main_window.window import MainWindow

__all__ = [
    "CueSequenceTable",
    "CueTableDelegate",
    "DropZone",
    "InPointSpinBox",
    "MainWindow",
    "OutPointSpinBox",
    "SmartDoubleSpinBox",
    "StudioPreviewMonitor",
    "WaveformPanel",
    "WaveformWidget",
]
