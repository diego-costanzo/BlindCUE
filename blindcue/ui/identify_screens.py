""""Identify the screens" (stage 4, item 4.5): a big number on every screen for a few seconds.

The numbers match the list of screens in the device dialog, so in a new room
the operator sees at once which screen is the projector. A click closes a
number early. Nothing is shown while something is on air (the projector
would show it to the audience).
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QGuiApplication, QScreen
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from i18n import tr


def screen_role(screen: QScreen) -> str:
    return tr("Regia") if screen == QGuiApplication.primaryScreen() else tr("Proiettore / esterno")


class ScreenNumber(QWidget):
    """A frameless window on top of everything in the middle of one screen."""

    def __init__(self, number: int, screen: QScreen) -> None:
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
                         | Qt.WindowType.Tool | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setStyleSheet("background:#101418; color:#ffffff; border:4px solid #00bcd4;")
        lay = QVBoxLayout(self)
        big = QLabel(str(number))
        big.setAlignment(Qt.AlignmentFlag.AlignCenter)
        big.setStyleSheet("font-size:180px; font-weight:bold; border:none;")
        geo = screen.geometry()
        small = QLabel(f"{screen.name()} – {geo.width()}×{geo.height()}\n{screen_role(screen)}")
        small.setAlignment(Qt.AlignmentFlag.AlignCenter)
        small.setStyleSheet("font-size:22px; border:none;")
        lay.addWidget(big, 1)
        lay.addWidget(small)
        self.setAccessibleName(tr("Schermo {}").format(number))
        width, height = 460, 340
        self.setGeometry(geo.x() + (geo.width() - width) // 2, geo.y() + (geo.height() - height) // 2,
                         width, height)

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt override
        self.close()


def show_screen_numbers(screens: list[QScreen], seconds: float = 4.0) -> list[ScreenNumber]:
    """Show 1, 2, ... on *screens* (in this order) and close them after *seconds*."""
    shown = []
    for i, screen in enumerate(screens):
        win = ScreenNumber(i + 1, screen)
        win.show()
        win.raise_()
        QTimer.singleShot(int(seconds * 1000), win, win.close)  # gone already after a click: no call
        shown.append(win)
    return shown
