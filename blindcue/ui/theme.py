"""Visual theme, colour palette, stylesheets, and shared UI constants for BlindCue."""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_LOGO_PATH = PROJECT_ROOT / "immagini di progetto" / "BlindCue-logo.jpeg"

# ── Colour palette (Pro Broadcast / Obsidian Slate) ───────────────────
CLR_BG = "#0c1017"         # Deep obsidian backdrop
CLR_PANEL = "#151b26"      # Sleek slate panel surface
CLR_TEXT = "#e2e8f0"       # Clean readable text
CLR_TEXT_MUTED = "#94a3b8" # Soft secondary text
CLR_LIVE = "#10b981"       # Vivid broadcast emerald green
CLR_PREVIZ = "#f59e0b"     # Studio amber
CLR_GO = "#10b981"         # Emerald GO
CLR_ACCENT = "#38bdf8"     # Sky cyan accent

# Curated Cue Scene/Group Color Palette (empty = default uncolored)
CUE_COLOR_PALETTE: tuple[tuple[str, str], ...] = (
    ("", "Nessun Colore (Predefinito)"),
    ("#ef4444", "Rosso — Atto / Effetto"),
    ("#f59e0b", "Ambra — Dialogo / Luce Calda"),
    ("#10b981", "Verde — Musica / Ambiente"),
    ("#06b6d4", "Ciano — Video / Proiezione"),
    ("#3b82f6", "Blu — Cambio Scena"),
    ("#a855f7", "Viola — Sogno / Atmosfera"),
    ("#ec4899", "Magenta — Evento Speciale"),
)

# Supported file extensions
VIDEO_EXT = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv", ".wmv", ".m4v"}
AUDIO_EXT = {".mp3", ".wav", ".flac", ".ogg", ".aac", ".m4a", ".wma", ".opus"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".tiff", ".svg"}

NUDGE_BTN_STYLE = """
    QPushButton {
        background-color: #1e2838;
        border: 1px solid #2d3b50;
        border-radius: 4px;
        font-size: 11px;
        padding: 3px 8px;
        font-weight: bold;
        min-width: 30px;
        height: 22px;
    }
    QPushButton:hover {
        background-color: #2a374c;
        border-color: #38bdf8;
        color: #38bdf8;
    }
    QPushButton:pressed {
        background-color: #141b26;
    }
"""

DARK_STYLESHEET = f"""
    QMainWindow, QWidget {{
        background-color: {CLR_BG};
        color: {CLR_TEXT};
    }}
    QGroupBox {{
        background-color: {CLR_PANEL};
        border: 1px solid #232f40;
        border-radius: 6px;
        margin-top: 14px;
        padding: 12px 8px 8px 8px;
        font-weight: bold;
        font-size: 11px;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 10px;
        padding: 1px 8px;
        background-color: {CLR_PANEL};
        border-radius: 3px;
        color: {CLR_ACCENT};
        font-weight: bold;
    }}
    QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
        background-color: #080d14;
        border: 1px solid #354761;
        border-radius: 5px;
        padding: 3px 7px;
        color: #f8fafc;
        font-size: 11px;
        min-height: 24px;
        selection-background-color: #0284c7;
    }}
    QSpinBox, QDoubleSpinBox {{
        min-height: 26px;
        max-height: 26px;
        padding: 2px 24px 2px 7px;
    }}
    QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
        border: 1.5px solid {CLR_ACCENT};
        background-color: #0e1624;
    }}
    QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled {{
        background-color: #0a0d14;
        border-color: #1a2230;
        color: #475569;
    }}
    QSpinBox::up-button, QDoubleSpinBox::up-button {{
        subcontrol-origin: border;
        subcontrol-position: top right;
        top: 1px;
        right: 1px;
        width: 21px;
        height: 12px;
        background-color: #1c2738;
        border-left: 1px solid #2d3c52;
        border-bottom: 1px solid #2d3c52;
        border-top-right-radius: 4px;
    }}
    QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover {{
        background-color: #263850;
        border-left-color: {CLR_ACCENT};
    }}
    QSpinBox::up-button:pressed, QDoubleSpinBox::up-button:pressed {{
        background-color: #121a26;
    }}
    QSpinBox::down-button, QDoubleSpinBox::down-button {{
        subcontrol-origin: border;
        subcontrol-position: bottom right;
        bottom: 1px;
        right: 1px;
        width: 21px;
        height: 12px;
        background-color: #1c2738;
        border-left: 1px solid #2d3c52;
        border-bottom-right-radius: 4px;
    }}
    QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
        background-color: #263850;
        border-left-color: {CLR_ACCENT};
    }}
    QSpinBox::down-button:pressed, QDoubleSpinBox::down-button:pressed {{
        background-color: #121a26;
    }}
    QSpinBox::up-arrow, QDoubleSpinBox::up-arrow,
    QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
        image: none;
        width: 0px;
        height: 0px;
    }}
    QListWidget, QTableWidget {{
        background-color: #111722;
        border: 1px solid #232f40;
        border-radius: 5px;
        font-size: 12px;
        font-family: 'DejaVu Sans Mono', 'Liberation Mono', 'Roboto Mono', 'Ubuntu Mono', 'monospace', monospace;
        outline: none;
        gridline-color: #1a2332;
    }}
    QListWidget::item, QTableWidget::item {{
        padding: 4px 6px;
        border-bottom: 1px solid #1a2332;
    }}
    QListWidget::item:selected, QTableWidget::item:selected {{
        background-color: #1e2d42;
        color: #ffffff;
    }}
    QListWidget::item:hover:!selected, QTableWidget::item:hover:!selected {{
        background-color: #16202e;
    }}
    QHeaderView::section {{
        background-color: #0e141e;
        color: {CLR_ACCENT};
        border: none;
        border-bottom: 1px solid #232f40;
        border-right: 1px solid #1a2332;
        padding: 5px 6px;
        font-size: 11px;
        font-weight: bold;
    }}
    QHeaderView::section:last {{
        border-right: none;
    }}
    QPushButton {{
        background-color: #1c2534;
        border: 1px solid #2c3a4e;
        border-radius: 4px;
        padding: 5px 12px;
        color: {CLR_TEXT};
        font-size: 11px;
        font-weight: bold;
    }}
    QPushButton:hover {{
        background-color: #263448;
        border-color: {CLR_ACCENT};
        color: #ffffff;
    }}
    QPushButton:pressed {{
        background-color: #141b26;
        border-color: #0284c7;
    }}
    QPushButton:checked {{
        background-color: #065f46;
        border-color: {CLR_LIVE};
        color: #ffffff;
    }}
    QPushButton:disabled {{
        background-color: #0f141d;
        border-color: #1c2334;
        color: #475569;
    }}
    QLabel {{
        color: {CLR_TEXT};
    }}
    QSlider {{
        min-height: 22px;
        max-height: 22px;
        background: transparent;
    }}
    QSlider::groove:horizontal {{
        height: 6px;
        margin: 8px 8px;
        background: #1c2636;
        border-radius: 3px;
        border: 1px solid #283548;
    }}
    QSlider::sub-page:horizontal {{
        height: 6px;
        margin: 8px 0px 8px 8px;
        background: #0284c7;
        border-radius: 3px;
    }}
    QSlider::handle:horizontal {{
        width: 14px;
        height: 14px;
        margin: -5px -7px;
        background: {CLR_ACCENT};
        border-radius: 8px;
        border: 1px solid #ffffff;
    }}
    QSlider::handle:horizontal:hover {{
        background: #7dd3fc;
    }}
    QSlider::handle:horizontal:disabled {{
        background: #475569;
        border-color: #334155;
    }}
    QTabWidget::pane {{
        background-color: #0e141e;
        border: 1px solid #243347;
        border-radius: 6px;
        top: -1px;
    }}
    QTabBar::tab {{
        background-color: #111824;
        color: #94a3b8;
        border: 1px solid #202d3f;
        border-bottom: none;
        border-top-left-radius: 6px;
        border-top-right-radius: 6px;
        padding: 6px 9px;
        margin-right: 3px;
        font-size: 11px;
        font-weight: bold;
    }}
    QTabBar::tab:hover:!selected {{
        background-color: #192434;
        color: #e2e8f0;
        border-color: #354761;
    }}
    QTabBar::tab:selected {{
        background-color: #142132;
        color: #ffffff;
        border-color: {CLR_ACCENT};
        border-top: 2px solid {CLR_ACCENT};
    }}
    QCheckBox {{
        spacing: 6px;
        color: {CLR_TEXT};
    }}
    QCheckBox:disabled {{
        color: #475569;
    }}
    QSplitter::handle {{
        background-color: #101620;
    }}
    QSplitter::handle:hover {{
        background-color: {CLR_ACCENT};
    }}
    QStatusBar {{
        background-color: #090d13;
        color: {CLR_TEXT_MUTED};
        font-size: 11px;
        border-top: 1px solid #1a2332;
    }}
    QMenuBar {{
        background-color: #090d13;
        color: {CLR_TEXT};
        font-size: 12px;
        border-bottom: 1px solid #1a2332;
    }}
    QMenuBar::item:selected {{
        background-color: #1c2534;
        color: {CLR_ACCENT};
    }}
    QMenu {{
        background-color: {CLR_PANEL};
        border: 1px solid #283548;
        border-radius: 4px;
        color: {CLR_TEXT};
        padding: 4px;
    }}
    QMenu::item {{
        padding: 4px 18px;
        border-radius: 3px;
    }}
    QMenu::item:selected {{
        background-color: #1e2d42;
        color: {CLR_ACCENT};
    }}
    QScrollBar:vertical {{
        background: #0f1520;
        width: 10px;
        border-radius: 5px;
        margin: 0px;
    }}
    QScrollBar::handle:vertical {{
        background: #283548;
        border-radius: 5px;
        min-height: 20px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {CLR_ACCENT};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
"""

