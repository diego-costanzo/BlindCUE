"""Visual themes, colour palettes, stylesheets, accessibility profiles, and shared UI constants for BlindCue."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_LOGO_PATH = PROJECT_ROOT / "immagini di progetto" / "BlindCue-logo.jpeg"


@dataclass(frozen=True)
class ThemeDefinition:
    """Complete visual palette and styling definition for a BlindCue theme."""
    theme_id: str
    name: str
    description: str
    is_high_contrast: bool

    # Core canvas & surfaces
    bg: str
    panel: str
    panel_elevated: str
    input_bg: str
    input_focus_bg: str
    header_bg: str
    status_bg: str
    menu_bg: str

    # Typography & contrast
    text: str
    text_muted: str
    selection_bg: str
    selection_fg: str

    # Borders & dividers
    border: str
    border_subtle: str
    border_width: str
    table_grid: str

    # Accents & broadcast semantics
    accent: str
    accent_hover: str
    accent_muted: str
    live: str
    previz: str
    go: str

    # Controls
    button_bg: str
    button_border: str
    button_hover_bg: str
    slider_groove: str
    slider_subpage: str


# ── Theme 1: Obsidian Slate (Pro Broadcast · Default Dark) ───────────
THEME_OBSIDIAN_SLATE = ThemeDefinition(
    theme_id="obsidian_slate",
    name="Obsidian Slate (Regia Pro · Predefinito)",
    description="Tema scuro broadcast calibrato per ambienti di regia con luce soffusa. Morbido e riposante.",
    is_high_contrast=False,
    bg="#0c1017",
    panel="#151b26",
    panel_elevated="#1e2838",
    input_bg="#080d14",
    input_focus_bg="#0e1624",
    header_bg="#0e141e",
    status_bg="#090d13",
    menu_bg="#151b26",
    text="#e2e8f0",
    text_muted="#94a3b8",
    selection_bg="#1e2d42",
    selection_fg="#ffffff",
    border="#232f40",
    border_subtle="#1a2332",
    border_width="1px",
    table_grid="#1a2332",
    accent="#38bdf8",
    accent_hover="#7dd3fc",
    accent_muted="#0284c7",
    live="#10b981",
    previz="#f59e0b",
    go="#10b981",
    button_bg="#1c2534",
    button_border="#2c3a4e",
    button_hover_bg="#263448",
    slider_groove="#1c2636",
    slider_subpage="#0284c7",
)

# ── Theme 2: Carbon Monocromo (Grayscale & Luminous Accent · WCAG AAA) ──
# Pro neutral gray-scale architecture inspired by DaVinci Resolve & Ableton:
# Eliminates chromatic noise, uses stepped neutral carbon tones with high-luminance accents.
THEME_CARBON_MONO = ThemeDefinition(
    theme_id="carbon_mono",
    name="Carbon Monocromo (Scala di Grigi & Accento Luminoso)",
    description="Architettura in scala di grigi carbonio ad alta leggibilità: elimina il rumore cromatico per daltonici e ipovedenti, guidando lo sguardo con accenti luminosi.",
    is_high_contrast=True,
    bg="#111215",              # Neutral deep carbon backdrop
    panel="#1a1b1f",           # Solid tactile graphite panel
    panel_elevated="#26272e",  # Stepped elevated carbon surface
    input_bg="#0d0e10",        # Sunken dark input
    input_focus_bg="#1e1f25",  # Clear focus lift
    header_bg="#16171b",       # Defined header
    status_bg="#0c0c0e",       # Bottom bar
    menu_bg="#1a1b1f",
    text="#f4f4f6",            # Soft white silk (15.7:1 contrast, no halation or glare)
    text_muted="#a1a1aa",      # Crisp silver secondary text
    selection_bg="#3f3f46",    # Neutral silver-charcoal highlight
    selection_fg="#ffffff",
    border="#3f3f46",          # Refined 1.5px border
    border_subtle="#27272a",
    border_width="1.5px",
    table_grid="#27272a",
    accent="#38bdf8",          # High-luminance electric sky cyan accent
    accent_hover="#7dd3fc",
    accent_muted="#0284c7",
    live="#4ade80",            # High-luminance lime green
    previz="#fbbf24",          # High-luminance warm amber
    go="#4ade80",
    button_bg="#26272e",       # Solid stepped carbon button
    button_border="#3f3f46",
    button_hover_bg="#33343d",
    slider_groove="#27272a",
    slider_subpage="#38bdf8",
)

# ── Theme 3: Deep Indigo & Warm Amber (Night Studio) ─────────────────
THEME_DEEP_INDIGO_AMBER = ThemeDefinition(
    theme_id="deep_indigo_amber",
    name="Deep Indigo & Warm Amber (Studio Notturno)",
    description="Tonalità rilassanti blu notte profondo e accenti caldi ambra/rame per sessioni prolungate senza affaticamento.",
    is_high_contrast=False,
    bg="#090d16",
    panel="#111827",
    panel_elevated="#1e293b",
    input_bg="#080c14",
    input_focus_bg="#141f33",
    header_bg="#0d1320",
    status_bg="#070a12",
    menu_bg="#111827",
    text="#f8fafc",
    text_muted="#94a3b8",
    selection_bg="#312e81",
    selection_fg="#ffffff",
    border="#293548",
    border_subtle="#1e2738",
    border_width="1px",
    table_grid="#1e293b",
    accent="#f59e0b",
    accent_hover="#fbbf24",
    accent_muted="#d97706",
    live="#10b981",
    previz="#fb923c",
    go="#10b981",
    button_bg="#1a2336",
    button_border="#2c3d5a",
    button_hover_bg="#263753",
    slider_groove="#1f293b",
    slider_subpage="#f59e0b",
)

THEMES: Mapping[str, ThemeDefinition] = {
    THEME_OBSIDIAN_SLATE.theme_id: THEME_OBSIDIAN_SLATE,
    THEME_CARBON_MONO.theme_id: THEME_CARBON_MONO,
    THEME_DEEP_INDIGO_AMBER.theme_id: THEME_DEEP_INDIGO_AMBER,
    # Backward compatibility aliases
    "high_contrast_mono": THEME_CARBON_MONO,
    "high_contrast_gold": THEME_CARBON_MONO,
    "daylight_studio": THEME_CARBON_MONO,
}

# ── Dynamic active theme tracking ────────────────────────────────────
_ACTIVE_THEME_ID: str = THEME_OBSIDIAN_SLATE.theme_id

# Backward-compatible global aliases (dynamically updated by set_active_theme)
CLR_BG: str = THEME_OBSIDIAN_SLATE.bg
CLR_PANEL: str = THEME_OBSIDIAN_SLATE.panel
CLR_TEXT: str = THEME_OBSIDIAN_SLATE.text
CLR_TEXT_MUTED: str = THEME_OBSIDIAN_SLATE.text_muted
CLR_LIVE: str = THEME_OBSIDIAN_SLATE.live
CLR_PREVIZ: str = THEME_OBSIDIAN_SLATE.previz
CLR_GO: str = THEME_OBSIDIAN_SLATE.go
CLR_ACCENT: str = THEME_OBSIDIAN_SLATE.accent

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


def get_active_theme() -> ThemeDefinition:
    """Return the currently active ThemeDefinition instance."""
    return THEMES.get(_ACTIVE_THEME_ID, THEME_OBSIDIAN_SLATE)


def build_nudge_btn_style(theme: ThemeDefinition | str | None = None) -> str:
    """Build CSS for micro-nudge modifier buttons matching the theme."""
    if isinstance(theme, str):
        t = THEMES.get(theme, THEME_OBSIDIAN_SLATE)
    elif isinstance(theme, ThemeDefinition):
        t = theme
    else:
        t = get_active_theme()

    return f"""
    QPushButton {{
        background-color: {t.panel_elevated};
        border: {t.border_width} solid {t.border};
        border-radius: 4px;
        font-size: 11px;
        padding: 3px 8px;
        font-weight: bold;
        min-width: 30px;
        height: 22px;
        color: {t.text};
    }}
    QPushButton:hover {{
        background-color: {t.button_hover_bg};
        border-color: {t.accent};
        color: {t.accent};
    }}
    QPushButton:pressed {{
        background-color: {t.input_bg};
    }}
    """


def build_stylesheet(theme: ThemeDefinition | str | None = None) -> str:
    """Generate complete Qt application stylesheet for the given theme."""
    if isinstance(theme, str):
        t = THEMES.get(theme, THEME_OBSIDIAN_SLATE)
    elif isinstance(theme, ThemeDefinition):
        t = theme
    else:
        t = get_active_theme()

    font_weight_headings = "bold"
    focus_border_width = "2px" if t.is_high_contrast else "1.5px"

    return f"""
    QMainWindow, QWidget {{
        background-color: {t.bg};
        color: {t.text};
    }}
    QGroupBox {{
        background-color: {t.panel};
        border: {t.border_width} solid {t.border};
        border-radius: 6px;
        margin-top: 14px;
        padding: 12px 8px 8px 8px;
        font-weight: {font_weight_headings};
        font-size: 11px;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 10px;
        padding: 1px 8px;
        background-color: {t.panel};
        border-radius: 3px;
        color: {t.accent};
        font-weight: bold;
    }}
    QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
        background-color: {t.input_bg};
        border: {t.border_width} solid {t.border};
        border-radius: 5px;
        padding: 3px 8px;
        color: {t.text};
        font-size: 11px;
        min-height: 24px;
        selection-background-color: {t.selection_bg};
        selection-color: {t.selection_fg};
    }}
    QSpinBox, QDoubleSpinBox {{
        min-height: 26px;
        max-height: 26px;
        padding: 2px 24px 2px 8px;
    }}
    QSpinBox QLineEdit, QDoubleSpinBox QLineEdit {{
        background: transparent;
        border: none;
        padding-left: 4px;
        color: {t.text};
    }}
    QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
        border: {focus_border_width} solid {t.accent};
        background-color: {t.input_focus_bg};
    }}
    QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled {{
        background-color: {t.panel_elevated};
        border-color: {t.border_subtle};
        color: {t.text_muted};
    }}
    QSpinBox::up-button, QDoubleSpinBox::up-button {{
        subcontrol-origin: border;
        subcontrol-position: top right;
        top: 1px;
        right: 1px;
        width: 21px;
        height: 12px;
        background-color: {t.panel_elevated};
        border-left: {t.border_width} solid {t.border};
        border-bottom: {t.border_width} solid {t.border};
        border-top-right-radius: 4px;
    }}
    QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover {{
        background-color: {t.button_hover_bg};
        border-left-color: {t.accent};
    }}
    QSpinBox::up-button:pressed, QDoubleSpinBox::up-button:pressed {{
        background-color: {t.input_bg};
    }}
    QSpinBox::down-button, QDoubleSpinBox::down-button {{
        subcontrol-origin: border;
        subcontrol-position: bottom right;
        bottom: 1px;
        right: 1px;
        width: 21px;
        height: 12px;
        background-color: {t.panel_elevated};
        border-left: {t.border_width} solid {t.border};
        border-bottom-right-radius: 4px;
    }}
    QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
        background-color: {t.button_hover_bg};
        border-left-color: {t.accent};
    }}
    QSpinBox::down-button:pressed, QDoubleSpinBox::down-button:pressed {{
        background-color: {t.input_bg};
    }}
    QSpinBox::up-arrow, QDoubleSpinBox::up-arrow,
    QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
        image: none;
        width: 0px;
        height: 0px;
    }}
    QListWidget, QTableWidget {{
        background-color: {t.panel};
        border: {t.border_width} solid {t.border};
        border-radius: 5px;
        font-size: 12px;
        font-family: 'DejaVu Sans Mono', 'Liberation Mono', 'Roboto Mono', 'Ubuntu Mono', 'monospace', monospace;
        outline: none;
        gridline-color: {t.table_grid};
        color: {t.text};
    }}
    QListWidget::item, QTableWidget::item {{
        padding: 4px 6px;
        border-bottom: 1px solid {t.table_grid};
        color: {t.text};
    }}
    QListWidget::item:selected, QTableWidget::item:selected {{
        background-color: {t.selection_bg};
        color: {t.selection_fg};
    }}
    QListWidget::item:hover:!selected, QTableWidget::item:hover:!selected {{
        background-color: {t.panel_elevated};
    }}
    QHeaderView::section {{
        background-color: {t.header_bg};
        color: {t.accent};
        border: none;
        border-bottom: {t.border_width} solid {t.border};
        border-right: 1px solid {t.border_subtle};
        padding: 5px 6px;
        font-size: 11px;
        font-weight: bold;
    }}
    QHeaderView::section:last {{
        border-right: none;
    }}
    QPushButton {{
        background-color: {t.button_bg};
        border: {t.border_width} solid {t.button_border};
        border-radius: 4px;
        padding: 5px 12px;
        color: {t.text};
        font-size: 11px;
        font-weight: bold;
    }}
    QPushButton:hover {{
        background-color: {t.button_hover_bg};
        border-color: {t.accent};
        color: {t.selection_fg};
    }}
    QPushButton:pressed {{
        background-color: {t.input_bg};
        border-color: {t.accent_muted};
    }}
    QPushButton:checked {{
        background-color: {t.panel_elevated};
        border-color: {t.live};
        color: {t.selection_fg};
    }}
    QPushButton:disabled {{
        background-color: {t.panel};
        border-color: {t.border_subtle};
        color: {t.text_muted};
    }}
    QLabel {{
        color: {t.text};
    }}
    QSlider {{
        min-height: 22px;
        max-height: 22px;
        background: transparent;
    }}
    QSlider::groove:horizontal {{
        height: 6px;
        margin: 8px 8px;
        background: {t.slider_groove};
        border-radius: 3px;
        border: 1px solid {t.border};
    }}
    QSlider::sub-page:horizontal {{
        height: 6px;
        margin: 8px 0px 8px 8px;
        background: {t.slider_subpage};
        border-radius: 3px;
    }}
    QSlider::handle:horizontal {{
        width: 14px;
        height: 14px;
        margin: -5px -7px;
        background: {t.accent};
        border-radius: 8px;
        border: 1px solid #ffffff;
    }}
    QSlider::handle:horizontal:hover {{
        background: {t.accent_hover};
    }}
    QSlider::handle:horizontal:disabled {{
        background: {t.border_subtle};
        border-color: {t.border_subtle};
    }}
    QTabWidget::pane {{
        background-color: {t.panel};
        border: {t.border_width} solid {t.border};
        border-radius: 6px;
        top: -1px;
    }}
    QTabBar::tab {{
        background-color: {t.panel_elevated};
        color: {t.text_muted};
        border: {t.border_width} solid {t.border_subtle};
        border-bottom: none;
        border-top-left-radius: 6px;
        border-top-right-radius: 6px;
        padding: 6px 9px;
        margin-right: 3px;
        font-size: 11px;
        font-weight: bold;
    }}
    QTabBar::tab:hover:!selected {{
        background-color: {t.panel};
        color: {t.text};
        border-color: {t.border};
    }}
    QTabBar::tab:selected {{
        background-color: {t.panel};
        color: {t.selection_fg};
        border-color: {t.accent};
        border-top: 2.5px solid {t.accent};
    }}
    QCheckBox {{
        spacing: 6px;
        color: {t.text};
    }}
    QCheckBox:disabled {{
        color: {t.text_muted};
    }}
    QSplitter::handle {{
        background-color: {t.bg};
    }}
    QSplitter::handle:hover {{
        background-color: {t.accent};
    }}
    QStatusBar {{
        background-color: {t.status_bg};
        color: {t.text_muted};
        font-size: 11px;
        border-top: 1px solid {t.border_subtle};
    }}
    QMenuBar {{
        background-color: {t.status_bg};
        color: {t.text};
        font-size: 12px;
        border-bottom: 1px solid {t.border_subtle};
    }}
    QMenuBar::item:selected {{
        background-color: {t.panel_elevated};
        color: {t.accent};
    }}
    QMenu {{
        background-color: {t.menu_bg};
        border: {t.border_width} solid {t.border};
        border-radius: 4px;
        color: {t.text};
        padding: 4px;
    }}
    QMenu::item {{
        padding: 4px 18px;
        border-radius: 3px;
    }}
    QMenu::item:selected {{
        background-color: {t.selection_bg};
        color: {t.selection_fg};
    }}
    QScrollBar:vertical {{
        background: {t.panel};
        width: 10px;
        border-radius: 5px;
        margin: 0px;
    }}
    QScrollBar::handle:vertical {{
        background: {t.border};
        border-radius: 5px;
        min-height: 20px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {t.accent};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    """


# Generate default stylesheet and nudge style
DARK_STYLESHEET: str = build_stylesheet(THEME_OBSIDIAN_SLATE)
NUDGE_BTN_STYLE: str = build_nudge_btn_style(THEME_OBSIDIAN_SLATE)


def set_active_theme(theme_id: str) -> str:
    """Set active theme by ID, update global color aliases and return generated stylesheet."""
    global _ACTIVE_THEME_ID, CLR_BG, CLR_PANEL, CLR_TEXT, CLR_TEXT_MUTED, CLR_LIVE, CLR_PREVIZ, CLR_GO, CLR_ACCENT, DARK_STYLESHEET, NUDGE_BTN_STYLE

    if theme_id not in THEMES:
        theme_id = THEME_OBSIDIAN_SLATE.theme_id

    _ACTIVE_THEME_ID = theme_id
    palette = THEMES[theme_id]

    CLR_BG = palette.bg
    CLR_PANEL = palette.panel
    CLR_TEXT = palette.text
    CLR_TEXT_MUTED = palette.text_muted
    CLR_LIVE = palette.live
    CLR_PREVIZ = palette.previz
    CLR_GO = palette.go
    CLR_ACCENT = palette.accent

    DARK_STYLESHEET = build_stylesheet(palette)
    NUDGE_BTN_STYLE = build_nudge_btn_style(palette)

    return DARK_STYLESHEET
