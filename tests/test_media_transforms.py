"""Test delle trasformazioni non distruttive immagine/video (rotazione e maschera).

I controlli qui verificano che i valori salvati nel progetto siano sempre
legittimi anche quando arrivano da un JSON corrotto o scritto a mano: un
progetto danneggiato deve comunque aprirsi in live, degradando la sola
proprietà invalida invece di sollevare un'eccezione.

Esecuzione:
    pytest -q tests/test_media_transforms.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "blindcue"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from models.cue import (
    MASK_MAX_POINTS,
    Cue,
    MediaType,
    normalize_rotation,
    sanitize_mask_polygon,
)


@pytest.fixture(scope="session")
def qt_app():
    """A single offscreen QApplication for the widget tests in this module."""
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


class TestNormalizeRotation:
    def test_plain_values_pass_through(self) -> None:
        assert normalize_rotation(0) == 0.0
        assert normalize_rotation(90) == 90.0
        assert normalize_rotation(-45.5) == -45.5
        assert normalize_rotation(180) == 180.0

    def test_wraps_into_supported_range(self) -> None:
        assert normalize_rotation(270) == -90.0
        assert normalize_rotation(-270) == 90.0
        assert normalize_rotation(360) == 0.0
        assert normalize_rotation(540) == 180.0

    def test_invalid_input_falls_back_to_upright(self) -> None:
        assert normalize_rotation(None) == 0.0
        assert normalize_rotation("non un numero") == 0.0
        assert normalize_rotation(float("nan")) == 0.0
        assert normalize_rotation(float("inf")) == 0.0

    def test_rounds_to_two_decimals(self) -> None:
        assert normalize_rotation(12.3456) == 12.35


class TestSanitizeMaskPolygon:
    def test_valid_polygon_is_clamped_and_rounded(self) -> None:
        result = sanitize_mask_polygon([[0.5, 0.25], [1.5, -0.2], [0.123456, 0.9]])
        assert result == [[0.5, 0.25], [1.0, 0.0], [0.1235, 0.9]]

    def test_too_few_points_means_no_mask(self) -> None:
        assert sanitize_mask_polygon([[0.1, 0.1], [0.9, 0.1]]) == []
        assert sanitize_mask_polygon([]) == []

    def test_malformed_points_reject_the_whole_mask(self) -> None:
        assert sanitize_mask_polygon([[0.1, 0.1], "punto", [0.9, 0.9]]) == []
        assert sanitize_mask_polygon([[0.1, 0.1], [float("nan"), 0.5], [0.9, 0.9]]) == []
        assert sanitize_mask_polygon({"x": 0.1}) == []

    def test_point_count_is_capped(self) -> None:
        points = [[i / 100.0, i / 100.0] for i in range(MASK_MAX_POINTS + 20)]
        assert len(sanitize_mask_polygon(points)) == MASK_MAX_POINTS


class TestCueSerialization:
    def test_rotation_and_mask_survive_a_round_trip(self) -> None:
        cue = Cue(
            cue_id=1,
            name="Maschera",
            media_type=MediaType.IMAGE,
            file_path="/tmp/none.png",
            rotation=270.0,
            mask_polygon=[[0.1, 0.1], [0.9, 0.1], [0.5, 0.9]],
        )
        assert cue.rotation == -90.0
        restored = Cue.from_dict(cue.to_dict())
        assert restored.rotation == -90.0
        assert restored.mask_polygon == [[0.1, 0.1], [0.9, 0.1], [0.5, 0.9]]

    def test_old_projects_without_the_new_fields_still_load(self) -> None:
        restored = Cue.from_dict(
            {
                "cue_id": 2,
                "name": "Vecchia",
                "media_type": MediaType.IMAGE.value,
                "file_path": "/tmp/none.png",
            }
        )
        assert restored.rotation == 0.0
        assert restored.mask_polygon == []

    def test_corrupt_mask_does_not_break_loading(self) -> None:
        restored = Cue.from_dict(
            {
                "cue_id": 3,
                "name": "Rotta",
                "media_type": MediaType.IMAGE.value,
                "file_path": "/tmp/none.png",
                "rotation": "storto",
                "mask_polygon": [[0.1, 0.1], ["boh", 2]],
            }
        )
        assert restored.rotation == 0.0
        assert restored.mask_polygon == []
        # Only the missing media file may be reported: transforms must be clean.
        assert not [e for e in restored.validate() if "rotation" in e or "mask" in e]


class TestMaskDialogPaint:
    """Regressione: il disegno del poligono non deve mai chiudere l'applicazione.

    Storico: ``QPainterPath(rect)`` non esiste come costruttore. Al terzo punto
    il ``paintEvent`` sollevava un'eccezione, il widget smetteva di ridisegnarsi
    e il ``QPainter`` rimasto aperto provocava un crash nativo (SIGSEGV).
    """

    def test_clicking_past_three_points_keeps_painting(self, tmp_path, qt_app) -> None:
        from PySide6.QtCore import QPointF, Qt
        from PySide6.QtGui import QColor, QImage, QMouseEvent
        from PySide6.QtWidgets import QApplication

        from ui.mask_dialog import ImageMaskDialog

        image_path = tmp_path / "mask.png"
        image = QImage(320, 180, QImage.Format.Format_RGB32)
        image.fill(QColor("#334455"))
        assert image.save(str(image_path))

        dialog = ImageMaskDialog(str(image_path))
        dialog.show()
        QApplication.processEvents()
        canvas = dialog._canvas

        for x, y in ((40, 40), (200, 50), (210, 150), (60, 140), (120, 100)):
            canvas.mousePressEvent(
                QMouseEvent(QMouseEvent.Type.MouseButtonPress, QPointF(x, y), QPointF(x, y),
                            Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
                            Qt.KeyboardModifier.NoModifier)
            )
            canvas.mouseReleaseEvent(
                QMouseEvent(QMouseEvent.Type.MouseButtonRelease, QPointF(x, y), QPointF(x, y),
                            Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton,
                            Qt.KeyboardModifier.NoModifier)
            )
            canvas.repaint()  # must not raise and must not crash
            QApplication.processEvents()

        assert len(canvas.points()) == 5
        dialog.close()

    def test_open_polyline_and_cursor_preview_are_painted(self, tmp_path, qt_app) -> None:
        """One and two points (open polyline + rubber band) must paint safely."""
        from PySide6.QtCore import QPointF, Qt
        from PySide6.QtGui import QColor, QImage, QMouseEvent
        from PySide6.QtWidgets import QApplication

        from ui.mask_dialog import ImageMaskDialog

        image_path = tmp_path / "mask2.png"
        image = QImage(200, 200, QImage.Format.Format_RGB32)
        image.fill(QColor("#223344"))
        assert image.save(str(image_path))

        dialog = ImageMaskDialog(str(image_path))
        dialog.show()
        QApplication.processEvents()
        canvas = dialog._canvas

        canvas.mousePressEvent(
            QMouseEvent(QMouseEvent.Type.MouseButtonPress, QPointF(30, 30), QPointF(30, 30),
                        Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
                        Qt.KeyboardModifier.NoModifier)
        )
        canvas.repaint()
        canvas.mousePressEvent(
            QMouseEvent(QMouseEvent.Type.MouseButtonPress, QPointF(160, 40), QPointF(160, 40),
                        Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton,
                        Qt.KeyboardModifier.NoModifier)
        )
        canvas.mouseMoveEvent(
            QMouseEvent(QMouseEvent.Type.MouseMove, QPointF(120, 160), QPointF(120, 160),
                        Qt.MouseButton.NoButton, Qt.MouseButton.NoButton,
                        Qt.KeyboardModifier.NoModifier)
        )
        canvas.repaint()
        QApplication.processEvents()

        assert len(canvas._points) == 2
        dialog.close()

    def test_right_click_never_drops_below_three_points(self, tmp_path, qt_app) -> None:
        """A stray right-click must not wipe the whole selection."""
        from PySide6.QtCore import QPointF, Qt
        from PySide6.QtGui import QColor, QImage, QMouseEvent
        from PySide6.QtWidgets import QApplication

        from ui.mask_dialog import ImageMaskDialog

        image_path = tmp_path / "mask3.png"
        image = QImage(400, 300, QImage.Format.Format_RGB32)
        image.fill(QColor("#101820"))
        assert image.save(str(image_path))

        points = [[0.2, 0.2], [0.8, 0.2], [0.5, 0.8]]
        dialog = ImageMaskDialog(str(image_path), points=points)
        dialog.resize(800, 600)
        dialog.show()
        QApplication.processEvents()
        canvas = dialog._canvas

        rect = canvas._image_rect()
        x = rect.x() + 0.8 * rect.width()
        y = rect.y() + 0.2 * rect.height()
        canvas.mousePressEvent(
            QMouseEvent(QMouseEvent.Type.MouseButtonPress, QPointF(x, y), QPointF(x, y),
                        Qt.MouseButton.RightButton, Qt.MouseButton.RightButton,
                        Qt.KeyboardModifier.NoModifier)
        )
        assert len(canvas.points()) == 3

        # With four points the same click does remove the vertex.
        canvas._points.append([0.5, 0.5])
        canvas.mousePressEvent(
            QMouseEvent(QMouseEvent.Type.MouseButtonPress, QPointF(x, y), QPointF(x, y),
                        Qt.MouseButton.RightButton, Qt.MouseButton.RightButton,
                        Qt.KeyboardModifier.NoModifier)
        )
        assert len(canvas.points()) == 3
        dialog.close()

    def test_selection_interior_shows_the_untouched_image(self, tmp_path, qt_app) -> None:
        """No flat tint inside the mask: only the ramp band may be highlighted."""
        from PySide6.QtGui import QColor, QImage
        from PySide6.QtWidgets import QApplication

        from ui.mask_dialog import ImageMaskDialog

        image_path = tmp_path / "tint.png"
        image = QImage(400, 400, QImage.Format.Format_RGB32)
        image.fill(QColor("#334455"))
        assert image.save(str(image_path))

        points = [[0.15, 0.15], [0.85, 0.15], [0.85, 0.85], [0.15, 0.85]]
        for feather in (0.0, 0.04):
            dialog = ImageMaskDialog(str(image_path), points=points, feather=feather)
            dialog.resize(700, 700)
            dialog.show()
            QApplication.processEvents()
            canvas = dialog._canvas

            shot = canvas.grab().toImage()
            rect = canvas._image_rect()
            center = shot.pixelColor(
                int(rect.x() + rect.width() / 2), int(rect.y() + rect.height() / 2)
            )
            # The image colour must survive untouched under the selection.
            assert (center.red(), center.green(), center.blue()) == (0x33, 0x44, 0x55)
            dialog.close()

    def test_zoom_keeps_the_selection_intact(self, tmp_path, qt_app) -> None:
        """Zoom/pan is a view transform: it must never alter the drawn polygon."""
        from PySide6.QtCore import QPointF, Qt
        from PySide6.QtGui import QColor, QImage, QWheelEvent
        from PySide6.QtWidgets import QApplication

        from ui.mask_dialog import ImageMaskDialog

        image_path = tmp_path / "zoom.png"
        image = QImage(400, 225, QImage.Format.Format_RGB32)
        image.fill(QColor("#203040"))
        assert image.save(str(image_path))

        dialog = ImageMaskDialog(
            str(image_path), points=[[0.1, 0.1], [0.8, 0.2], [0.5, 0.9]]
        )
        dialog.show()
        QApplication.processEvents()
        canvas = dialog._canvas
        before = [list(p) for p in canvas.points()]

        wheel = QWheelEvent(
            QPointF(120.0, 90.0), QPointF(120.0, 90.0),
            QPointF(0, 0).toPoint(), QPointF(0, 120).toPoint(),
            # Qt6: angle is the important part for our handler.
            Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.NoScrollPhase, False,
        )
        canvas.wheelEvent(wheel)
        assert canvas.zoom_percent() > 100
        assert canvas.points() == before

        canvas.set_zoom(100.0)  # clamps to the 8× ceiling
        assert canvas.zoom_percent() == 800
        assert canvas.points() == before

        canvas.set_zoom(0.1)  # clamps to 1× floor
        assert canvas.zoom_percent() == 100
        assert canvas.points() == before
        canvas.repaint()
        dialog.close()


class TestFeatheredMask:
    """The soft mask must fade the edge without eating the shape."""

    @staticmethod
    def _alpha_stats(mask, step: int = 4) -> tuple[int, int, int]:
        opaque = partial = clear = 0
        for y in range(0, mask.height(), step):
            for x in range(0, mask.width(), step):
                a = mask.pixelColor(x, y).alpha()
                if a >= 250:
                    opaque += 1
                elif a <= 5:
                    clear += 1
                else:
                    partial += 1
        return opaque, partial, clear

    def test_feather_creates_a_gradient_edge(self, qt_app) -> None:
        from ui.layout_math import feathered_mask_image

        points = [[0.25, 0.25], [0.75, 0.25], [0.75, 0.75], [0.25, 0.75]]
        hard = feathered_mask_image(points, 400, 400, 0.0)
        soft = feathered_mask_image(points, 400, 400, 20.0)

        assert not hard.isNull() and not soft.isNull()
        hard_opaque, hard_partial, hard_clear = self._alpha_stats(hard)
        soft_opaque, soft_partial, soft_clear = self._alpha_stats(soft)

        # Inside stays opaque, outside stays transparent in both variants.
        assert hard_opaque > 0 and soft_opaque > 0
        assert hard_clear > 0 and soft_clear > 0
        # Only the feathered version has a real ramp.
        assert soft_partial > hard_partial
        assert hard_partial <= 60  # antialiasing only

    def test_cached_mask_is_reused(self, qt_app) -> None:
        from ui.layout_math import _soft_mask_cached, feathered_mask_image

        points = [[0.2, 0.2], [0.8, 0.2], [0.5, 0.8]]
        first = feathered_mask_image(points, 300, 300, 10.0)
        second = feathered_mask_image(points, 300, 300, 10.0)
        assert first is second
        _soft_mask_cached.cache_clear()

    def test_unusable_polygon_returns_empty_mask(self, qt_app) -> None:
        from ui.layout_math import feathered_mask_image

        assert feathered_mask_image([], 100, 100, 5.0).isNull()
        assert feathered_mask_image([[0.1, 0.1], [0.2, 0.2]], 100, 100, 5.0).isNull()

    def test_cue_round_trips_mask_feather(self) -> None:
        from models.cue import MASK_MAX_FEATHER, sanitize_mask_feather

        cue = Cue(
            name="feather",
            media_type=MediaType.IMAGE,
            file_path="/tmp/f.png",
            mask_polygon=[[0.1, 0.1], [0.9, 0.1], [0.5, 0.9]],
            mask_feather=0.012,
        )
        restored = Cue.from_dict(cue.to_dict())
        assert restored.mask_feather == 0.012
        # Out-of-range and garbage input must degrade, never raise.
        assert sanitize_mask_feather(9.0) == MASK_MAX_FEATHER
        assert sanitize_mask_feather(-3.0) == 0.0
        assert sanitize_mask_feather("nope") == 0.0
        assert sanitize_mask_feather(float("nan")) == 0.0


class TestMaskRowVisibility:
    """La riga maschera appartiene solo alle immagini: i video usano il crop."""

    @staticmethod
    def _panel():
        from ui.inspector_panel import CueInspectorPanel

        return CueInspectorPanel()

    def test_hidden_for_video_and_audio(self, qt_app) -> None:
        panel = self._panel()
        panel.set_enabled_for_cue(True, MediaType.VIDEO)
        assert panel.mask_row_widget.isHidden()
        panel.set_enabled_for_cue(True, MediaType.AUDIO)
        assert panel.mask_row_widget.isHidden()

    def test_visible_for_images(self, qt_app) -> None:
        panel = self._panel()
        panel.set_enabled_for_cue(True, MediaType.IMAGE)
        assert not panel.mask_row_widget.isHidden()

    def test_hidden_when_nothing_is_selected(self, qt_app) -> None:
        panel = self._panel()
        panel.set_enabled_for_cue(True, MediaType.IMAGE)
        panel.set_enabled_for_cue(False)
        assert panel.mask_row_widget.isHidden()


class TestRecentProjects:
    """Recent list: newest first, capped, duplicates moved to the top."""

    @staticmethod
    def _harness(tmp_path):
        from PySide6.QtCore import QSettings

        from ui.main_window._persistence import _PersistenceMixin

        store = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)

        class _Harness(_PersistenceMixin):
            def _settings(self):  # noqa: D102 - override in tests
                return store

        return _Harness()

    def test_most_recent_first_and_capped(self, tmp_path) -> None:
        harness = self._harness(tmp_path)
        for idx in range(7):
            harness._remember_recent_project(f"/shows/show{idx}.blindcue")

        recent = harness._recent_projects()
        assert len(recent) == harness._RECENT_PROJECTS_LIMIT
        assert recent[0].endswith("show6.blindcue")
        assert recent[-1].endswith("show2.blindcue")

        harness._remember_recent_project("/shows/show3.blindcue")
        assert harness._recent_projects()[0].endswith("show3.blindcue")
        # Stored paths are OS-normalised (backslashes on Windows).
        assert harness._recent_projects().count(str(Path("/shows/show3.blindcue"))) == 1

    def test_forget_and_clear(self, tmp_path) -> None:
        harness = self._harness(tmp_path)
        harness._remember_recent_project("/shows/a.blindcue")
        harness._remember_recent_project("/shows/b.blindcue")

        harness._forget_recent_project("/shows/a.blindcue")
        assert harness._recent_projects() == [str(Path("/shows/b.blindcue"))]

        harness._clear_recent_projects()
        assert harness._recent_projects() == []

