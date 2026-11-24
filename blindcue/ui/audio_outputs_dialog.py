"""Audio outputs of this computer (stage 3, item 3.1).

Which device is the stage, the hall and the foldback (monitors for the
performers) on THIS computer, what plays when it is missing (the fallback
rule) and a trim in dB. A test button plays a short tone on each output, and
"test them all" goes through them one by one with the name on the dialog.
The map can be exported to a file and imported on another computer. During
the Show the map is read-only (and no test tone reaches the audience).
"""

from __future__ import annotations

import json
import math
import struct
import tempfile
import wave
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from engine import audio_routes
from i18n import tr
from ui.spinboxes import SmartDoubleSpinBox

_KEEP = "_keep"  # the remembered device is not connected: keep the choice
_FALLBACK_LABELS = {"default": "Uscita predefinita", "stage": "Come il Palco", "mute": "Muto"}


def _tone_file() -> Path:
    """A short 880 Hz tone (0.6 s) for the output test, written once."""
    path = Path(tempfile.gettempdir()) / "blindcue_output_test.wav"
    if not path.exists():
        rate = 44100
        frames = b"".join(
            struct.pack("<h", int(12000 * math.sin(2 * math.pi * 880 * i / rate) * min(1.0, i / 800, (rate * 0.6 - i) / 800)))
            for i in range(int(rate * 0.6)))
        with wave.open(str(path), "wb") as out:
            out.setnchannels(1)
            out.setsampwidth(2)
            out.setframerate(rate)
            out.writeframes(frames)
    return path


class AudioOutputsDialog(QDialog):
    def __init__(self, device_mgr, locked: bool = False, parent: QWidget | None = None,
                 busy: Callable[[], bool] | None = None) -> None:
        super().__init__(parent)
        self.mgr = device_mgr
        self.locked = locked
        self._busy = busy or (lambda: False)  # something plays: no test tone over it
        self.setWindowTitle("Uscite audio di questo computer")
        self.setMinimumWidth(640)
        self._rows: dict[str, tuple[QComboBox, QComboBox, SmartDoubleSpinBox, QPushButton]] = {}
        self._devices: list = []
        self._player = QMediaPlayer(self)
        self._audio = QAudioOutput(self)
        self._player.setAudioOutput(self._audio)
        self._sequence: list[str] = []
        self._build()
        self._fill()

    # ── UI ──
    def _build(self) -> None:
        lay = QVBoxLayout(self)
        intro = QLabel("Ogni cue suona su un'uscita: Palco, Sala o Spie (ascolto per gli attori). Qui si sceglie "
                       "quale altoparlante è ognuna su questo computer; lo spettacolo non cambia su un altro "
                       "computer.")
        intro.setWordWrap(True)
        lay.addWidget(intro)
        grid = QGridLayout()
        for col, head in enumerate(("Uscita", "Dispositivo", "Se manca", "Regolazione", "")):
            title = QLabel(head)
            title.setStyleSheet("font-weight: bold;")
            grid.addWidget(title, 0, col)
        for row, key in enumerate(audio_routes.OUTPUTS, 1):
            device = QComboBox()
            name = tr(audio_routes.LABELS[key])
            device.setAccessibleName(tr("Dispositivo: {}").format(name))
            fallback = QComboBox()
            for rule in audio_routes.ALLOWED_FALLBACKS[key]:
                fallback.addItem(_FALLBACK_LABELS[rule], rule)
            fallback.setEnabled(key != "stage")  # the stage always falls back on the default output
            fallback.setAccessibleName(tr("Se manca: {}").format(name))
            trim = SmartDoubleSpinBox()
            trim.setRange(audio_routes.TRIM_MIN_DB, 0.0)
            trim.setDecimals(1)
            trim.setSingleStep(1.0)
            trim.setSuffix(" dB")
            trim.setAccessibleName(tr("Regolazione: {}").format(name))
            test = QPushButton("▶ Prova")
            test.setAccessibleName(tr("Prova: {}").format(name))
            test.clicked.connect(lambda _c=False, k=key: self._test(k))
            device.currentIndexChanged.connect(lambda _i, k=key: self._device_changed(k))
            fallback.currentIndexChanged.connect(lambda _i, k=key: self._rule_changed(k))
            trim.valueChanged.connect(lambda _v, k=key: self._rule_changed(k))
            grid.addWidget(QLabel(audio_routes.LABELS[key]), row, 0)
            grid.addWidget(device, row, 1)
            grid.addWidget(fallback, row, 2)
            grid.addWidget(trim, row, 3)
            grid.addWidget(test, row, 4)
            self._rows[key] = (device, fallback, trim, test)
        grid.setColumnStretch(1, 1)
        lay.addLayout(grid)
        self.lbl_status = QLabel("")
        self.lbl_status.setWordWrap(True)
        lay.addWidget(self.lbl_status)
        if self.locked:
            note = QLabel("Durante lo spettacolo le uscite non si cambiano e non si provano.")
            note.setStyleSheet("color: #f59e0b;")
            lay.addWidget(note)
        buttons = QHBoxLayout()
        self.btn_test_all = QPushButton("▶ Prova tutte in ordine")
        self.btn_test_all.clicked.connect(self._test_all)
        self.btn_export = QPushButton("Esporta…")
        self.btn_export.clicked.connect(self._export)
        self.btn_import = QPushButton("Importa…")
        self.btn_import.clicked.connect(self._import)
        close = QPushButton("Chiudi")
        close.clicked.connect(self.accept)
        for b in (self.btn_test_all, self.btn_export, self.btn_import):
            buttons.addWidget(b)
        buttons.addStretch()
        buttons.addWidget(close)
        lay.addLayout(buttons)
        for key, (device, fallback, trim, test) in self._rows.items():
            for w in (device, fallback, trim, test):
                w.setEnabled(not self.locked and (w is not fallback or key != "stage"))
        self.btn_test_all.setEnabled(not self.locked)
        self.btn_import.setEnabled(not self.locked)

    def _fill(self) -> None:
        """Show the current map (signals blocked: filling changes nothing)."""
        self._devices = self.mgr.get_available_audio_devices()
        choices = self.mgr.output_choices()
        for key, (device, fallback, trim, _test) in self._rows.items():
            for w in (device, fallback, trim):
                w.blockSignals(True)
            device.clear()
            device.addItem("Predefinito di sistema" if key == "stage" else "— non impostata —", None)
            for i, dev in enumerate(self._devices):
                device.addItem(dev.description(), i)
            choice = choices.get(key)
            if choice is not None:
                found = self.mgr.find_audio_device(choice, self._devices)
                if found is not None:
                    device.setCurrentIndex(1 + next(i for i, d in enumerate(self._devices) if d is found))
                else:
                    device.addItem(tr("{} (non collegato)").format(choice[1] or choice[0]), (_KEEP, choice))
                    device.setCurrentIndex(device.count() - 1)
            fallback.setCurrentIndex(max(0, fallback.findData(self.mgr.output_fallback(key))))
            trim.setValue(self.mgr.output_trim_db(key))
            for w in (device, fallback, trim):
                w.blockSignals(False)
        self._show_routes()

    def _show_routes(self) -> None:
        parts = []
        for key in audio_routes.OUTPUTS:
            route = self.mgr.resolve_output(key)
            label = tr(audio_routes.LABELS[key])
            if route.muted:
                where = tr("muto")
            elif route.device is not None:
                where = route.device.description()
            else:
                where = tr("uscita predefinita")
            extra = " " + tr("{} (non collegato)").format(route.missing) if route.missing else ""
            parts.append(f"{label} → {where}{extra}")
        text = " · ".join(parts)
        fold = self.mgr.resolve_output("foldback")
        audience = {bytes(d.id()) for d in self.mgr.audience_devices()}
        if not fold.muted and bytes(self.mgr.route_device(fold).id()) in audience:
            text += "\n⚠ " + tr("Le spie usano lo stesso dispositivo del pubblico: la traccia privata si sente in sala.")
        self.lbl_status.setText(text)

    # ── changes ──
    def _device_changed(self, key: str) -> None:
        if self.locked:
            return
        data = self._rows[key][0].currentData()
        if isinstance(data, tuple) and data[0] == _KEEP:
            self.mgr.set_output_choice(key, data[1])  # back to the device that is not connected now
        else:
            self.mgr.set_output_device(key, None if data is None else self._devices[int(data)])
        self._show_routes()

    def _rule_changed(self, key: str) -> None:
        if self.locked:
            return
        _device, fallback, trim, _test = self._rows[key]
        self.mgr.set_output_rule(key, fallback=fallback.currentData(), trim_db=trim.value())
        self._show_routes()

    # ── tests ──
    def _test(self, key: str) -> None:
        from PySide6.QtMultimedia import QMediaDevices

        route = self.mgr.resolve_output(key)
        label = tr(audio_routes.LABELS[key])
        if self._busy():
            self._sequence = []
            self.lbl_status.setText(tr("Qualcosa suona: la prova non parte."))
            return
        if route.muted:
            self.lbl_status.setText(f"▶ {label}: " + tr("muto (nessun suono)"))
            return
        device = self.mgr.route_device(route) if hasattr(self.mgr, "route_device") else (
            route.device if route.device is not None else QMediaDevices.defaultAudioOutput())
        self._audio.setDevice(device)
        self._audio.setVolume(audio_routes.trim_gain(self.mgr.output_trim_db(key)))
        self._player.stop()
        self._player.setSource(QUrl.fromLocalFile(str(_tone_file())))
        self._player.play()
        self.lbl_status.setText(f"▶ {label} → {device.description()}")

    def _test_all(self) -> None:
        self._sequence = list(audio_routes.OUTPUTS)
        self._next_test()

    def _next_test(self) -> None:
        if not self._sequence or not self.isVisible():
            return
        self._test(self._sequence.pop(0))
        QTimer.singleShot(1400, self._next_test)

    def done(self, result: int) -> None:  # noqa: D102
        self._sequence = []
        self._player.stop()  # no test tone after the window is closed
        super().done(result)

    # ── file ──
    def _export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Esporta le uscite audio", "uscite_audio.json", "JSON (*.json)")
        if not path:
            return
        Path(path).write_text(json.dumps(self.mgr.export_outputs(), indent=2, ensure_ascii=False), encoding="utf-8")
        self.lbl_status.setText(tr("Esportato: {}").format(path))

    def _import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Importa le uscite audio", "", "JSON (*.json)")
        if not path:
            return
        sure = QMessageBox.question(self, tr("Importa le uscite audio"), tr(
            "Sostituire le uscite audio di questo computer con quelle del file?"))
        if sure != QMessageBox.StandardButton.Yes:
            return
        try:
            self.mgr.import_outputs(json.loads(Path(path).read_text(encoding="utf-8")))
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, tr("Importa le uscite audio"), tr("Non è una mappa di uscite audio: {}").format(exc))
            return
        self._fill()
