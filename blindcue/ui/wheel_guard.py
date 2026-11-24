"""The mouse wheel scrolls a panel, it never changes a value by accident (evaluation 2026-11-24).

Scrolling the inspector with the wheel used to change whatever list, number
field or slider passed under the pointer (a video's format jumped from
"native" to 16:9 to 4:3 while the teacher only scrolled). Now such a control
takes the wheel only while it has the keyboard focus (clicked or tabbed into);
otherwise the wheel scrolls the panel it sits in.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QAbstractScrollArea, QAbstractSpinBox, QApplication, QComboBox, QSlider, QWidget

_GUARDED = (QComboBox, QAbstractSpinBox, QSlider)


def _control(widget: QWidget | None) -> QWidget | None:
    """The guarded control *widget* belongs to (a spin box's line edit counts), or None."""
    while widget is not None:
        if isinstance(widget, _GUARDED):
            return widget
        if isinstance(widget, QAbstractScrollArea):
            return None
        widget = widget.parentWidget()
    return None


def _scroll_area(widget: QWidget) -> QAbstractScrollArea | None:
    parent = widget.parentWidget()
    while parent is not None:
        if isinstance(parent, QAbstractScrollArea):
            return parent
        parent = parent.parentWidget()
    return None


class WheelGuard(QObject):
    def eventFilter(self, obj, event) -> bool:  # noqa: N802 - Qt override
        if event.type() == QEvent.Type.Polish and isinstance(obj, _GUARDED):
            # WheelFocus would hand the focus to the control before this filter
            # sees the wheel: only a click or Tab may give it the focus.
            if obj.focusPolicy() == Qt.FocusPolicy.WheelFocus:
                obj.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            return False
        if event.type() != QEvent.Type.Wheel or not isinstance(obj, QWidget):
            return False
        control = _control(obj)
        if control is None or control.hasFocus() or (control.focusProxy() and control.focusProxy().hasFocus()):
            return False
        area = _scroll_area(control)
        if area is None:
            return False  # not in a scrolling panel (e.g. the master volume): the control keeps the wheel
        QApplication.sendEvent(area.verticalScrollBar(), event)
        return True


_GUARD: WheelGuard | None = None


def install() -> None:
    """Once per application."""
    global _GUARD
    app = QApplication.instance()
    if app is None or _GUARD is not None:
        return
    _GUARD = WheelGuard(app)
    app.installEventFilter(_GUARD)
