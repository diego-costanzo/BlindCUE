"""The "Edit cue" window (teacher-workflow evaluation, 2026-11-24).

The essentials of one cue in one place, opened by a double-click, Enter or
"✏ Edit" on the cue list in every view: for a sound or a film the waveform
with start and end, a preview and "start / end here", the volume, fades and
crossfade; for a picture its time on screen, size and place; for a caption
its text; for a scene how it plays. The window works on copies: OK hands the
changed fields back (the caller makes them one undo step), Cancel forgets
them. The side inspector stays for everything else.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

import numpy as np
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from i18n import tr
from models.cue import Cue, CueSection, MediaType
from ui.rehearsal_drawer import FOLLOW_CHOICES
from ui.spinboxes import SmartDoubleSpinBox
from ui.waveform_widget import WaveformWidget

TIMED = (MediaType.AUDIO, MediaType.VIDEO)
PICTURE = (MediaType.VIDEO, MediaType.IMAGE)
PREVIEW_W, PREVIEW_H = 384, 216

# Fields the window may hand back (sections and envelope points only when the waveform changed them).
FIELDS = ("name", "q_label", "notes", "follow_mode", "group_mode", "in_point", "out_point", "volume", "loop",
          "fade_in", "fade_out", "fade_curve", "crossfade", "volume_points", "sections", "hold_time", "scale",
          "position_x", "position_y", "text_spec", "crossfade_style", "hold_last_frame")


def _seconds_field(maximum: float, special: str = "") -> SmartDoubleSpinBox:
    spin = SmartDoubleSpinBox()
    spin.setRange(0.0, maximum)
    spin.setDecimals(2)
    spin.setSingleStep(0.1)
    spin.setSuffix(" s")
    if special:
        spin.setSpecialValueText(special)
    spin.setMinimumWidth(92)
    return spin


def _clock(sec: float) -> str:
    sec = max(0.0, float(sec))
    return f"{int(sec // 60)}:{sec % 60:04.1f}"


def _comparable(value: Any) -> Any:
    if isinstance(value, list) and value and isinstance(value[0], CueSection):
        return [s.to_dict() for s in value]
    return value


class EditCueDialog(QDialog):
    """One cue, its essentials, OK / Cancel."""

    def __init__(
        self,
        cue: Cue,
        *,
        peaks_provider: Callable[[], np.ndarray | None] | None = None,
        audio_device: Any = None,
        edit_text: Callable[[dict], dict | None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._cue = cue
        self._kind = cue.media_type
        self._is_text = bool(cue.text_spec)
        self._peaks_provider = peaks_provider
        self._edit_text = edit_text
        self._orig: dict[str, Any] = {f: self._copy(getattr(cue, f, None)) for f in FIELDS}
        self._vals: dict[str, Any] = {f: self._copy(v) for f, v in self._orig.items()}
        self._duration = 0.0
        self._player: Any = None
        self._waveform: WaveformWidget | None = None

        self.setWindowTitle("Modifica cue")
        self.setAccessibleName("Modifica cue")
        self.setModal(True)
        outer = QVBoxLayout(self)
        outer.setSpacing(8)
        self.lbl_title = QLabel()
        self.lbl_title.setTextFormat(Qt.TextFormat.PlainText)
        self.lbl_title.setStyleSheet("QLabel { font-size: 15px; font-weight: bold; }")
        self.lbl_title.setText(f"{self._icon()} {cue.name}")
        outer.addWidget(self.lbl_title)
        # The fields scroll; the title, the status and OK / Cancel always stay on screen
        # (a video cue was taller than a 1080p laptop screen at 125 %).
        self.body = QWidget()
        root = QVBoxLayout(self.body)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setWidget(self.body)
        outer.addWidget(self.scroll, stretch=1)

        root.addWidget(self._build_common())
        if self._kind == MediaType.GROUP:
            root.addWidget(self._build_scene())
        if self._kind in PICTURE:
            root.addWidget(self._build_preview(), alignment=Qt.AlignmentFlag.AlignHCenter)
        if self._kind in TIMED:
            root.addWidget(self._build_timed())
        if self._kind in PICTURE:
            root.addWidget(self._build_picture())
        if self._kind in (MediaType.AUDIO, MediaType.VIDEO, MediaType.IMAGE):
            root.addWidget(self._build_transitions())
        if self._kind == MediaType.ACTION:
            hint = QLabel("Che cosa fa l'azione si sceglie nel pannello a destra (scheda «⚡ Azione»).")
            hint.setWordWrap(True)
            root.addWidget(hint)

        root.addStretch(1)
        self.lbl_status = QLabel("")
        self.lbl_status.setWordWrap(True)
        self.lbl_status.setStyleSheet("QLabel { color: #fbbf24; }")
        outer.addWidget(self.lbl_status)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self.buttons = buttons
        outer.addWidget(buttons)
        self._fit_to_screen()

        if self._kind in TIMED:
            self._start_player(audio_device)
            self._peaks_timer = QTimer(self)
            self._peaks_timer.setInterval(250)
            self._peaks_timer.timeout.connect(self._poll_peaks)
            self._poll_peaks()
            if self._waveform is not None and self._waveform_peaks_missing():
                self._peaks_timer.start()
        self.ed_name.setFocus()
        self.ed_name.selectAll()

    # ── Building ──────────────────────────────────────────────────────

    def _fit_to_screen(self) -> None:
        """As tall as the fields need, never taller than the screen (they scroll then)."""
        from PySide6.QtGui import QGuiApplication

        screen = self.screen() or QGuiApplication.primaryScreen()
        avail = screen.availableGeometry() if screen is not None else None
        content = self.body.sizeHint()
        chrome = self.lbl_title.sizeHint().height() + self.buttons.sizeHint().height() + 60
        width = content.width() + self.scroll.verticalScrollBar().sizeHint().width() + 30
        height = content.height() + chrome
        if avail is not None:
            width = min(width, int(avail.width() * 0.95))
            height = min(height, int(avail.height() * 0.92))
        self.resize(width, height)

    @staticmethod
    def _copy(value: Any) -> Any:
        if isinstance(value, list):
            return [CueSection.from_dict(v.to_dict()) if isinstance(v, CueSection) else
                    (list(v) if isinstance(v, list) else v) for v in value]
        if isinstance(value, dict):
            return dict(value)
        return value

    def _icon(self) -> str:
        if self._is_text:
            return "🅣"
        return {MediaType.AUDIO: "🎵", MediaType.VIDEO: "🎬", MediaType.IMAGE: "🖼",
                MediaType.GROUP: "📂", MediaType.ACTION: "⚙"}.get(self._kind, "•")

    def _build_common(self) -> QGroupBox:
        box = QGroupBox("Dati della cue")
        grid = QGridLayout(box)
        grid.addWidget(QLabel("Nome"), 0, 0)
        self.ed_name = QLineEdit(self._vals["name"] or "")
        self.ed_name.setAccessibleName("Nome")
        self.ed_name.textChanged.connect(lambda t: self._set("name", t.strip() or self._orig["name"]))
        grid.addWidget(self.ed_name, 0, 1)
        lbl_q = QLabel("N. (Q)")
        grid.addWidget(lbl_q, 0, 2)
        self.ed_q = QLineEdit(self._vals["q_label"] or "")
        self.ed_q.setAccessibleName("N. (Q)")
        self.ed_q.setToolTip("Numero della cue nel copione (Q), per esempio 12 o 12a")
        lbl_q.setToolTip(self.ed_q.toolTip())
        self.ed_q.setMaximumWidth(70)
        self.ed_q.textChanged.connect(lambda t: self._set("q_label", t.strip()))
        grid.addWidget(self.ed_q, 0, 3)
        grid.addWidget(QLabel("Note"), 1, 0)
        self.ed_notes = QLineEdit(self._vals["notes"] or "")
        self.ed_notes.setAccessibleName("Note")
        self.ed_notes.textChanged.connect(lambda t: self._set("notes", t))
        grid.addWidget(self.ed_notes, 1, 1, 1, 3)
        grid.addWidget(QLabel("Poi"), 2, 0)
        self.cb_follow = QComboBox()
        self.cb_follow.setAccessibleName("Poi")
        for value, label in FOLLOW_CHOICES:
            self.cb_follow.addItem(label, value)
        idx = self.cb_follow.findData(self._vals["follow_mode"])
        if idx < 0:
            self.cb_follow.addItem(str(self._vals["follow_mode"]), self._vals["follow_mode"])
            idx = self.cb_follow.count() - 1
        self.cb_follow.setCurrentIndex(idx)
        self.cb_follow.currentIndexChanged.connect(lambda _i: self._set("follow_mode", self.cb_follow.currentData()))
        grid.addWidget(self.cb_follow, 2, 1, 1, 3)
        grid.setColumnStretch(1, 1)
        return box

    def _build_scene(self) -> QGroupBox:
        from ui.inspector_panel import _GROUP_MODE_SPECS

        box = QGroupBox("Come suona la scena")
        lay = QVBoxLayout(box)
        self.cb_group_mode = QComboBox()
        self.cb_group_mode.setAccessibleName("Come suona la scena")
        for key, label, desc, *_ in _GROUP_MODE_SPECS:
            self.cb_group_mode.addItem(label, key)
            self.cb_group_mode.setItemData(self.cb_group_mode.count() - 1, desc, Qt.ItemDataRole.ToolTipRole)
        self.cb_group_mode.setCurrentIndex(max(0, self.cb_group_mode.findData(self._vals["group_mode"])))
        self.lbl_group_desc = QLabel()
        self.lbl_group_desc.setWordWrap(True)

        def changed(_i: int) -> None:
            self._set("group_mode", self.cb_group_mode.currentData())
            self.lbl_group_desc.setText(self.cb_group_mode.itemData(self.cb_group_mode.currentIndex(),
                                                                    Qt.ItemDataRole.ToolTipRole) or "")

        self.cb_group_mode.currentIndexChanged.connect(changed)
        changed(self.cb_group_mode.currentIndex())
        lay.addWidget(self.cb_group_mode)
        lay.addWidget(self.lbl_group_desc)
        return box

    def _build_preview(self) -> QWidget:
        if self._kind == MediaType.VIDEO:
            from PySide6.QtMultimediaWidgets import QVideoWidget

            self.video = QVideoWidget()
            self.video.setFixedSize(PREVIEW_W, PREVIEW_H)
            self.video.setStyleSheet("background: black;")
            return self.video
        self.lbl_picture = QLabel()
        self.lbl_picture.setFixedSize(PREVIEW_W, PREVIEW_H)
        self.lbl_picture.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_picture.setStyleSheet("QLabel { background: black; }")
        self._show_picture(self._cue.file_path)
        return self.lbl_picture

    def _show_picture(self, path: str) -> None:
        pix = QPixmap(path) if path and os.path.isfile(path) else QPixmap()
        if pix.isNull():
            self.lbl_picture.setText("Il file non c'è")
            return
        self.lbl_picture.setPixmap(pix.scaled(PREVIEW_W, PREVIEW_H, Qt.AspectRatioMode.KeepAspectRatio,
                                              Qt.TransformationMode.SmoothTransformation))

    def _build_timed(self) -> QGroupBox:
        box = QGroupBox("Suono" if self._kind == MediaType.AUDIO else "Film")
        lay = QVBoxLayout(box)
        self._waveform = WaveformWidget()
        self._waveform.setMinimumHeight(110)
        self._waveform.setAccessibleName("Forma d'onda: trascina l'inizio e la fine")
        self._waveform.set_media_context(self._kind)
        self._waveform.set_fades(self._vals["fade_in"], self._vals["fade_out"], self._vals["fade_curve"])
        self._waveform.set_envelopes(base_volume=self._vals["volume"], base_opacity=1.0,
                                     volume_points=self._vals["volume_points"] or [], opacity_points=[])
        self._waveform.in_changed.connect(self._on_wave_in)
        self._waveform.out_changed.connect(lambda sec: self._apply_out(sec if sec > 0 else None))
        self._waveform.seek_requested.connect(self._seek)
        self._waveform.fade_in_changed.connect(lambda v: self.sp_fade_in.setValue(v))
        self._waveform.fade_out_changed.connect(lambda v: self.sp_fade_out.setValue(v))
        self._waveform.fade_curve_changed.connect(lambda c: self._set("fade_curve", c))
        self._waveform.envelope_points_changed.connect(
            lambda mode, pts: self._set("volume_points", [list(p) for p in pts]) if mode == "volume" else None)
        self._waveform.sections_changed.connect(lambda secs: self._set("sections", list(secs)))
        lay.addWidget(self._waveform)
        self.lbl_wave = QLabel("Forma d'onda in caricamento…")
        self.lbl_wave.setStyleSheet("QLabel { color: #94a3b8; }")
        lay.addWidget(self.lbl_wave)

        transport = QHBoxLayout()
        self.btn_play = QPushButton("▶ Ascolta")
        self.btn_play.setToolTip("Ascolta dall'inizio scelto (in cuffia, se è scelta)")
        self.btn_play.clicked.connect(self._toggle_play)
        transport.addWidget(self.btn_play)
        self.btn_stop = QPushButton("■")
        self.btn_stop.setToolTip("Stop")
        self.btn_stop.setAccessibleName("Stop")
        self.btn_stop.setFixedWidth(36)
        self.btn_stop.clicked.connect(self._stop)
        transport.addWidget(self.btn_stop)
        self.lbl_pos = QLabel("0:00.0")
        self.lbl_pos.setMinimumWidth(110)
        transport.addWidget(self.lbl_pos)
        # A short piece of a long file: the IN and OUT labels overlapped (GUI review 2026-11-24).
        self.btn_clip_view = QPushButton("🔍 Mostra il pezzo")
        self.btn_clip_view.setCheckable(True)
        self.btn_clip_view.setToolTip("Ingrandisce la forma d'onda tra l'inizio e la fine scelti; di nuovo: tutto il file")
        self.btn_clip_view.toggled.connect(self._show_clip)
        transport.addWidget(self.btn_clip_view)
        transport.addStretch(1)
        self.btn_in_here = QPushButton("⇤ Inizio qui")
        self.btn_in_here.setToolTip("L'inizio va dove si trova ora la riproduzione")
        self.btn_in_here.clicked.connect(self._in_here)
        transport.addWidget(self.btn_in_here)
        self.btn_out_here = QPushButton("Fine qui ⇥")
        self.btn_out_here.setToolTip("La fine va dove si trova ora la riproduzione")
        self.btn_out_here.clicked.connect(self._out_here)
        transport.addWidget(self.btn_out_here)
        lay.addLayout(transport)

        points = QHBoxLayout()
        points.addWidget(QLabel("Inizio"))
        self.sp_in = _seconds_field(36000.0)
        self.sp_in.setAccessibleName("Inizio")
        self.sp_in.setValue(self._vals["in_point"])
        self.sp_in.valueChanged.connect(lambda v: self._apply_in(float(v)))
        points.addWidget(self.sp_in)
        points.addWidget(QLabel("Fine"))
        self.sp_out = _seconds_field(36000.0, "fine del file")
        self.sp_out.setAccessibleName("Fine")
        self.sp_out.setValue(self._vals["out_point"] or 0.0)
        self.sp_out.valueChanged.connect(lambda v: self._apply_out(float(v) if v > 0 else None))
        points.addWidget(self.sp_out)
        self.btn_trim = QPushButton("✂")
        self.btn_trim.setToolTip("Taglia il silenzio all'inizio e alla fine")
        self.btn_trim.setAccessibleName("Taglia il silenzio all'inizio e alla fine")
        self.btn_trim.setFixedWidth(36)
        self.btn_trim.clicked.connect(self._trim_silence)
        points.addWidget(self.btn_trim)
        self.btn_whole = QPushButton("↺ Tutto il file")
        self.btn_whole.clicked.connect(self._whole_file)
        points.addWidget(self.btn_whole)
        points.addStretch(1)
        lay.addLayout(points)

        level = QHBoxLayout()
        level.addWidget(QLabel("Volume:"))
        self.sl_volume = QSlider(Qt.Orientation.Horizontal)
        self.sl_volume.setRange(0, 100)
        self.sl_volume.setAccessibleName("Volume")
        self.sl_volume.setValue(int(round(self._vals["volume"] * 100)))
        self.lbl_volume = QLabel(f"{self.sl_volume.value()} %")
        self.lbl_volume.setMinimumWidth(48)
        self.sl_volume.valueChanged.connect(self._on_volume)
        level.addWidget(self.sl_volume, stretch=1)
        level.addWidget(self.lbl_volume)
        self.cb_loop = QCheckBox("In loop")
        self.cb_loop.setChecked(bool(self._vals["loop"]))
        self.cb_loop.toggled.connect(lambda on: self._set("loop", bool(on)))
        level.addWidget(self.cb_loop)
        lay.addLayout(level)
        return box

    def _build_picture(self) -> QGroupBox:
        box = QGroupBox("Immagine")
        grid = QGridLayout(box)
        row = 0
        if self._kind == MediaType.IMAGE:
            grid.addWidget(QLabel("Tempo sullo schermo"), row, 0)
            self.sp_hold = _seconds_field(99999.0, "0 s (∞)")
            self.sp_hold.setAccessibleName("Tempo sullo schermo")
            self.sp_hold.setToolTip("Durata di permanenza in Live delle immagini statiche (0 = infinita)")
            self.sp_hold.setValue(self._vals["hold_time"])
            self.sp_hold.valueChanged.connect(lambda v: (self._set("hold_time", float(v)), self._check_timing()))
            grid.addWidget(self.sp_hold, row, 1)
            row += 1
            # 4.4: shorter than its transitions + 0.5 s, the picture is never seen still.
            self.lbl_timing = QLabel("")
            self.lbl_timing.setWordWrap(True)
            self.lbl_timing.setStyleSheet("QLabel { color: #fbbf24; }")
            self.lbl_timing.setVisible(False)
            grid.addWidget(self.lbl_timing, row, 0, 1, 4)
            row += 1
        if self._kind == MediaType.VIDEO:
            self.cb_hold_frame = QCheckBox("Alla fine resta l'ultimo fotogramma")
            self.cb_hold_frame.setToolTip(
                "Il video si ferma sull'ultimo fotogramma, che resta sullo schermo finché un'altra cue "
                "prende il suo layer o lo sfumi (Sfuma, Sfuma tutto, Blackout). Non con il loop infinito.")
            self.cb_hold_frame.setChecked(bool(self._vals["hold_last_frame"]))
            self.cb_hold_frame.toggled.connect(lambda on: self._set("hold_last_frame", bool(on)))
            grid.addWidget(self.cb_hold_frame, row, 0, 1, 4)
            row += 1
        grid.addWidget(QLabel("Dimensione"), row, 0)
        size = QHBoxLayout()
        self.sl_scale = QSlider(Qt.Orientation.Horizontal)
        self.sl_scale.setRange(10, 500)
        self.sl_scale.setAccessibleName("Dimensione")
        self.sl_scale.setValue(int(round(self._vals["scale"] * 100)))
        self.lbl_scale = QLabel(f"{self.sl_scale.value()} %")
        self.lbl_scale.setMinimumWidth(48)
        self.sl_scale.valueChanged.connect(self._on_scale)
        size.addWidget(self.sl_scale, stretch=1)
        size.addWidget(self.lbl_scale)
        grid.addLayout(size, row, 1, 1, 3)
        row += 1
        grid.addWidget(QLabel("Posizione"), row, 0)
        place = QHBoxLayout()
        self.sp_x = self._offset_field("X", "Offset orizzontale (-1.00 = sx, 0.00 = centro, +1.00 = dx)",
                                       "position_x")
        self.sp_y = self._offset_field("Y", "Offset verticale (-1.00 = alto, 0.00 = centro, +1.00 = basso)",
                                       "position_y")
        place.addWidget(QLabel("X"))
        place.addWidget(self.sp_x)
        place.addWidget(QLabel("Y"))
        place.addWidget(self.sp_y)
        self.btn_center = QPushButton("⌖ Centro")
        self.btn_center.clicked.connect(lambda: (self.sp_x.setValue(0.0), self.sp_y.setValue(0.0),
                                                 self.sl_scale.setValue(100)))
        place.addWidget(self.btn_center)
        place.addStretch(1)
        grid.addLayout(place, row, 1, 1, 3)
        row += 1
        if self._is_text:
            self.btn_text = QPushButton("✏ Cambia il testo…")
            self.btn_text.clicked.connect(self._change_text)
            grid.addWidget(self.btn_text, row, 0, 1, 2)
        grid.setColumnStretch(1, 1)
        return box

    def _offset_field(self, axis: str, tip: str, field: str) -> SmartDoubleSpinBox:
        spin = SmartDoubleSpinBox()
        spin.setRange(-2.0, 2.0)
        spin.setSingleStep(0.01)
        spin.setDecimals(2)
        spin.setToolTip(tip)
        spin.setAccessibleName(f"Pos {axis}:")
        spin.setValue(self._vals[field])
        spin.valueChanged.connect(lambda v: self._set(field, round(float(v), 3)))
        return spin

    def _build_transitions(self) -> QGroupBox:
        box = QGroupBox("Passaggi")
        row = QHBoxLayout(box)
        row.addWidget(QLabel("Fade In:"))
        self.sp_fade_in = _seconds_field(30.0)
        self.sp_fade_in.setAccessibleName("Fade In:")
        self.sp_fade_in.setValue(self._vals["fade_in"])
        self.sp_fade_in.valueChanged.connect(lambda v: self._on_fade("fade_in", float(v)))
        row.addWidget(self.sp_fade_in)
        row.addWidget(QLabel("Fade Out:"))
        self.sp_fade_out = _seconds_field(30.0)
        self.sp_fade_out.setAccessibleName("Fade Out:")
        self.sp_fade_out.setValue(self._vals["fade_out"])
        self.sp_fade_out.valueChanged.connect(lambda v: self._on_fade("fade_out", float(v)))
        row.addWidget(self.sp_fade_out)
        row.addWidget(QLabel("Crossfade:"))
        self.sp_crossfade = _seconds_field(10.0)
        self.sp_crossfade.setAccessibleName("Crossfade:")
        self.sp_crossfade.setToolTip("Dissolvenza incrociata: ciò che c'è ora sul layer di questo cue (immagine o suono) sfuma "
                                     "mentre questo cue entra, nel tempo indicato (0 = stacco netto).")
        self.sp_crossfade.setValue(self._vals["crossfade"])
        self.sp_crossfade.valueChanged.connect(lambda v: (self._set("crossfade", float(v)), self._check_timing()))
        row.addWidget(self.sp_crossfade)
        if self._kind in PICTURE:
            # 4.4 (MultiPlay): dissolve or slide in.
            self.cb_xfade_style = QComboBox()
            self.cb_xfade_style.addItem("Dissolvenza", "dissolve")
            self.cb_xfade_style.addItem("Scorrimento", "slide")
            self.cb_xfade_style.setAccessibleName("Tipo di passaggio dell'immagine")
            self.cb_xfade_style.setToolTip(
                "Come entra l'immagine: in dissolvenza sopra la precedente, oppure scorrendo da destra "
                "mentre la precedente esce a sinistra.")
            self.cb_xfade_style.setCurrentIndex(max(0, self.cb_xfade_style.findData(self._vals["crossfade_style"])))
            self.cb_xfade_style.currentIndexChanged.connect(
                lambda _i: self._set("crossfade_style", self.cb_xfade_style.currentData() or "dissolve"))
            row.addWidget(self.cb_xfade_style)
        row.addStretch(1)
        self._check_timing()  # the picture box (with its warning) is built before this one
        return box

    def _check_timing(self) -> None:
        """4.4: warn when a picture is shown shorter than its transitions + 0.5 s."""
        label = getattr(self, "lbl_timing", None)
        if label is None:
            return
        from engine.picture_timing import min_hold_seconds, too_short

        args = (self._vals["fade_in"], self._vals["fade_out"], self._vals["crossfade"])
        short = too_short(self._vals["hold_time"], *args)
        label.setText(tr("⚠ Tempo sullo schermo troppo breve: almeno {} s (passaggi + 0,5 s)").format(
            f"{min_hold_seconds(*args):g}") if short else "")
        label.setVisible(short)

    # ── Values ────────────────────────────────────────────────────────

    def _set(self, field: str, value: Any) -> None:
        self._vals[field] = value

    def changes(self) -> dict[str, Any]:
        """The fields that differ from the cue (empty: nothing to save)."""
        return {f: v for f, v in self._vals.items() if _comparable(v) != _comparable(self._orig[f])}

    def _on_volume(self, value: int) -> None:
        self.lbl_volume.setText(f"{value} %")
        self._set("volume", value / 100.0)
        if self._waveform is not None:
            self._waveform.set_envelopes(base_volume=value / 100.0, base_opacity=1.0,
                                         volume_points=self._vals["volume_points"] or [], opacity_points=[])
        self._configure_player()

    def _on_scale(self, value: int) -> None:
        self.lbl_scale.setText(f"{value} %")
        self._set("scale", round(value / 100.0, 2))

    def _on_fade(self, field: str, value: float) -> None:
        self._set(field, value)
        self._check_timing()
        if self._waveform is not None:
            self._waveform.set_fades(self._vals["fade_in"], self._vals["fade_out"], self._vals["fade_curve"])
        self._configure_player()

    def _on_wave_in(self, sec: float) -> None:
        self._apply_in(sec)
        self._seek(self._vals["in_point"])

    def _apply_in(self, sec: float) -> None:
        sec = round(max(0.0, sec), 2)
        if self._duration > 0:
            sec = min(sec, round(self._duration - 0.05, 2))
        self._vals["in_point"] = sec
        out = self._vals["out_point"]
        if out is not None and out <= sec + 0.04:
            self._vals["out_point"] = None
        self._sync_points()

    def _apply_out(self, sec: float | None) -> None:
        if sec is not None and sec <= 0:
            sec = None
        if sec is not None:
            sec = round(sec, 2)
            if self._duration > 0 and sec >= self._duration - 0.01:
                sec = None
            elif sec <= self._vals["in_point"] + 0.04:
                self.lbl_status.setText("La fine deve stare dopo l'inizio")
                self._sync_points()
                return
        self._vals["out_point"] = sec
        self._sync_points()

    def _sync_points(self) -> None:
        """Fields, waveform and preview show the same IN / OUT."""
        for spin, value in ((self.sp_in, self._vals["in_point"]), (self.sp_out, self._vals["out_point"] or 0.0)):
            if abs(spin.value() - value) > 0.004:
                spin.blockSignals(True)
                spin.setValue(value)
                spin.blockSignals(False)
        if self._waveform is not None:
            self._waveform.set_in_out_seconds(self._vals["in_point"], self._vals["out_point"], self._duration)
        if self._player is not None:
            self._player.set_bounds(self._vals["in_point"], self._vals["out_point"])

    def _whole_file(self) -> None:
        self._vals["in_point"] = 0.0
        self._vals["out_point"] = None
        self._sync_points()
        self.lbl_status.setText("")

    def _trim_silence(self) -> None:
        from engine.silence_trim import THRESHOLD_DB, sound_bounds

        peaks = self._current_peaks()
        bounds = sound_bounds(peaks if peaks is not None else None, self._duration)
        if bounds is None:
            self.lbl_status.setText("Taglia il silenzio: forma d'onda non ancora pronta o file muto")
            return
        start, end = bounds
        self._vals["in_point"] = round(start, 2)
        self._vals["out_point"] = round(end, 2) if end is not None else None
        self._sync_points()
        out_txt = f"{end:.2f} s" if end is not None else tr("fine")
        self.lbl_status.setText(tr("Silenzio tagliato (sotto {} dB): IN {} s, OUT {}").format(
            int(THRESHOLD_DB), f"{start:.2f}", out_txt))

    def _change_text(self) -> None:
        if self._edit_text is None:
            return
        spec = self._edit_text(dict(self._vals["text_spec"] or {}))
        if spec is None:
            return
        self._vals["text_spec"] = spec
        from engine.text_render import render_text_png

        try:
            self._show_picture(render_text_png(spec))
        except OSError as exc:
            self.lbl_status.setText(str(exc))

    # ── Preview (own player: the main preview and the inspector stay as they are) ──

    def _start_player(self, audio_device: Any) -> None:
        from engine.player_test import TestPlayer

        path = self._cue.file_path or ""
        if not path or not os.path.isfile(path):
            self.lbl_status.setText("Il file non c'è: scegline un altro con il menu della cue.")
            for btn in (self.btn_play, self.btn_stop, self.btn_in_here, self.btn_out_here):
                btn.setEnabled(False)
            return
        self._player = TestPlayer(video_widget=getattr(self, "video", None), parent=self)
        if audio_device is not None:
            self._player.set_audio_device(audio_device)
        self._player.signals.duration_changed.connect(self._on_duration)
        self._player.signals.position_changed.connect(self._on_position)
        self._player.signals.eof_reached.connect(self._on_preview_end)
        self._player.set_rate(getattr(self._cue, "playback_rate", 1.0) or 1.0,
                              bool(getattr(self._cue, "keep_pitch", True)))
        self._player.load(path, start=self._vals["in_point"], end=self._vals["out_point"], pause=True)
        self._player.set_mute(False)
        self._configure_player()

    def _configure_player(self) -> None:
        if self._player is None:
            return
        self._player.configure_automation(
            base_volume=self._vals["volume"], fade_in=self._vals["fade_in"], fade_out=self._vals["fade_out"],
            fade_curve=self._vals["fade_curve"], volume_points=self._vals["volume_points"] or [],
            is_video=self._kind == MediaType.VIDEO)
        self._player.set_mute(False)

    def _on_duration(self, sec: float) -> None:
        self._duration = float(sec)
        self._sync_points()
        self._on_position(self._vals["in_point"])

    def _on_position(self, sec: float) -> None:
        if self._waveform is not None:
            self._waveform.set_playhead_seconds(sec, self._duration or None)
        total = f" / {_clock(self._duration)}" if self._duration > 0 else ""
        self.lbl_pos.setText(_clock(sec) + total)

    def _on_preview_end(self) -> None:
        self.btn_play.setText("▶ Ascolta")

    def _toggle_play(self) -> None:
        if self._player is None:
            return
        if self._player.is_playing():
            self._player.pause()
            self.btn_play.setText("▶ Ascolta")
            return
        self.lbl_status.setText("")
        self._player.play()
        self.btn_play.setText("❚❚ Pausa")

    def _stop(self) -> None:
        if self._player is None:
            return
        if self._player.is_playing():
            self._player.pause()
        self._player.seek(self._vals["in_point"])
        self.btn_play.setText("▶ Ascolta")
        self._on_position(self._vals["in_point"])

    def _seek(self, sec: float) -> None:
        if self._player is None:
            return
        self._player.seek(max(0.0, float(sec)))
        self._on_position(sec)

    def _playhead(self) -> float | None:
        if self._waveform is None:
            return None
        return self._waveform.playhead_seconds()

    def _show_clip(self, on: bool) -> None:
        """🔍: the waveform between IN and OUT with a margin; off: the whole file."""
        wf = self._waveform
        if wf is None:
            return
        duration = wf.duration_seconds() or float(self._duration or 0.0)
        if not on or duration <= 0:
            wf.set_zoom(1.0)
            self.btn_clip_view.setText("🔍 Mostra il pezzo")
            return
        start = float(self._vals["in_point"] or 0.0)
        end = float(self._vals["out_point"] or 0.0) or duration
        margin = max(0.25, (end - start) * 0.1)
        span = max(0.5, end - start + 2 * margin)
        wf.set_zoom(duration / span)
        wf.set_view_start(max(0.0, start - margin))
        self.btn_clip_view.setText("↔ Tutto il file")

    def _in_here(self) -> None:
        sec = self._playhead()
        if sec is not None:
            self._apply_in(sec)

    def _out_here(self) -> None:
        sec = self._playhead()
        if sec is not None:
            self._apply_out(sec)

    # ── Waveform peaks (made in the background by the main window) ──

    def _current_peaks(self) -> np.ndarray | None:
        if self._peaks_provider is None:
            return None
        peaks = self._peaks_provider()
        return peaks if isinstance(peaks, np.ndarray) and peaks.size else None

    def _waveform_peaks_missing(self) -> bool:
        return self._current_peaks() is None

    def _poll_peaks(self) -> None:
        peaks = self._current_peaks()
        if peaks is None or self._waveform is None:
            return
        self._waveform.set_peaks(peaks)
        self.lbl_wave.setVisible(False)
        self._peaks_timer.stop()

    # ── Closing ───────────────────────────────────────────────────────

    def done(self, result: int) -> None:  # noqa: D401 - Qt override
        """Stop the preview whatever closes the window (OK, Cancel, Esc, ×)."""
        if getattr(self, "_peaks_timer", None) is not None:
            self._peaks_timer.stop()
        if self._player is not None and self._player.is_playing():
            self._player.pause()   # never at the end of the file: playing means not at EndOfMedia
        super().done(result)
