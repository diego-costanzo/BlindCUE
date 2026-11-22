"""Lightweight UI translation layer for BlindCue.

The original UI strings are hard-coded (mostly Italian, some English) across
the code base. Instead of rewriting every call site, this module translates
text at the Qt boundary: the Qt setters/constructors that put text on screen
(``QLabel.setText``, ``QAction(...)``, ``QMessageBox.question`` ...) are
wrapped once at start-up so every string passes through :func:`tr`.

Lookup order for a string ``s``:

1. exact match in the active dictionary;
2. template match (keys containing ``{}`` / ``{name}`` / ``%s`` placeholders),
   with captured values translated recursively;
3. multi-line text: each line translated on its own;
4. known prefixes ("Tempi: ...") followed by a translated remainder.

Anything not found is shown unchanged, so a missing entry never breaks the UI.
Internal logic never sees translated text: models keep the original strings.

The language is stored in QSettings (``ui/language``): ``pl``, ``en`` or
``it`` (original, no translation). Default: ``it``.
"""

from __future__ import annotations

import functools
import logging
import re

logger = logging.getLogger("blindcue.i18n")

LANGUAGES: dict[str, str] = {
    "it": "Italiano",
    "en": "English",
    "pl": "Polski",
}
DEFAULT_LANGUAGE = "it"
SETTINGS_KEY = "ui/language"

_lang: str = "it"
_exact: dict[str, str] = {}
_templates: list[tuple[re.Pattern[str], str]] = []
_prefixes: list[tuple[str, str]] = []
_suffixes: list[tuple[str, str]] = []
_installed = False

_PLACEHOLDER_RE = re.compile(r"\{[^{}]*\}|%(?:\.\d+)?[sdif]")
_TARGET_SLOT_RE = re.compile(r"\{(\d*)\}")


# --------------------------------------------------------------------------- #
# Language selection
# --------------------------------------------------------------------------- #
def saved_language() -> str:
    """Language stored in QSettings (falls back to the default)."""
    try:
        from PySide6.QtCore import QSettings

        value = QSettings("BlindCue", "BlindCue").value(SETTINGS_KEY, DEFAULT_LANGUAGE)
        value = str(value or DEFAULT_LANGUAGE)
    except Exception:  # pragma: no cover - Qt missing / settings unreadable
        value = DEFAULT_LANGUAGE
    return value if value in LANGUAGES else DEFAULT_LANGUAGE


def save_language(code: str) -> None:
    """Persist the UI language; it is applied on the next start."""
    from PySide6.QtCore import QSettings

    QSettings("BlindCue", "BlindCue").setValue(SETTINGS_KEY, code)


def current_language() -> str:
    return _lang


def set_language(code: str) -> None:
    """Load the dictionary for *code* (``it`` = no translation)."""
    global _lang, _exact, _templates, _prefixes, _suffixes
    _lang = code if code in LANGUAGES else DEFAULT_LANGUAGE
    _exact, _templates, _prefixes, _suffixes = {}, [], [], []
    _translate_cached.cache_clear()
    if _lang == "it":
        return
    if _lang == "pl":
        from .pl import T
    else:
        from .en import T
    for src, dst in T.items():
        if not dst:
            continue
        if _PLACEHOLDER_RE.search(src):
            _templates.append((_compile_template(src), dst))
        else:
            _exact[src] = dst
            if src.endswith((": ", " ", ":\n")) and len(src.strip()) > 2:
                _prefixes.append((src, dst))
            if src.startswith(" ") and len(src.strip()) > 2:
                _suffixes.append((src, dst))
    # Longest (most specific) templates first.
    _templates.sort(key=lambda item: -len(item[0].pattern))
    _prefixes.sort(key=lambda item: -len(item[0]))


def _compile_template(src: str) -> re.Pattern[str]:
    parts = _PLACEHOLDER_RE.split(src)
    pattern = "(.*?)".join(re.escape(p) for p in parts)
    return re.compile("^" + pattern + "$", re.DOTALL)


# --------------------------------------------------------------------------- #
# Translation
# --------------------------------------------------------------------------- #
def tr(text):
    """Translate *text* for the active language (non-strings pass through)."""
    if not isinstance(text, str) or not text:
        return text
    if not any(c.isalpha() for c in text):
        return text
    return _translate_cached(text)


@functools.lru_cache(maxsize=4096)
def _translate_cached(text: str) -> str:
    return text if _lang == "it" else _translate(text, depth=0)


def _translate(text: str, depth: int) -> str:
    hit = _exact.get(text)
    if hit is not None:
        return hit
    if depth > 6:  # "Tempi: Pre +1s | Durata ∞ | Blocco manuale" nests 5 deep
        return text

    stripped = text.strip()
    if stripped != text and stripped:
        hit = _exact.get(stripped)
        if hit is not None:
            lead = text[: len(text) - len(text.lstrip())]
            trail = text[len(text.rstrip()):]
            return lead + hit + trail

    # Trailing "modified" / punctuation markers: "Nuovo Show*", "Volume:".
    for marker in ("*", " *", ":", "…", "..."):
        if text.endswith(marker) and len(text) > len(marker) + 1:
            hit = _exact.get(text[: -len(marker)])
            if hit is not None:
                return hit + marker

    for regex, dst in _templates:
        m = regex.match(text)
        if m:
            values = [_translate(v, depth + 1) if v else v for v in m.groups()]
            return _fill(dst, values)

    if "\n" in text:
        lines = text.split("\n")
        out = [_translate(line, depth + 1) if line else line for line in lines]
        if out != lines:
            return "\n".join(out)

    for src, dst in _prefixes:
        if text.startswith(src) and len(text) > len(src):
            return dst + _translate(text[len(src):], depth + 1)

    # Known suffixes appended to user/device names: "Speakers (Predefinito)".
    for src, dst in _suffixes:
        if text.endswith(src) and len(text) > len(src):
            return text[: -len(src)] + dst

    return text


def _fill(dst: str, values: list[str]) -> str:
    counter = iter(range(len(values)))

    def repl(m: re.Match[str]) -> str:
        idx = m.group(1)
        i = int(idx) if idx else next(counter, len(values))
        return values[i] if i < len(values) else m.group(0)

    return _TARGET_SLOT_RE.sub(repl, dst)


# --------------------------------------------------------------------------- #
# Qt boundary hooks
# --------------------------------------------------------------------------- #
_TEXT_KWARGS = {"text", "title", "caption", "filter", "label", "toolTip", "windowTitle"}


def _tr_args(args, kwargs):
    new_args = [tr(a) if isinstance(a, str) else _tr_list(a) for a in args]
    for k in list(kwargs):
        if k in _TEXT_KWARGS:
            kwargs[k] = tr(kwargs[k])
    return new_args, kwargs


def _tr_list(value):
    if isinstance(value, list) and value and all(isinstance(v, str) for v in value):
        return [tr(v) for v in value]
    return value


def _wrap_method(cls, name: str) -> None:
    orig = cls.__dict__.get(name) or getattr(cls, name, None)
    if orig is None or getattr(orig, "_bc_i18n", False):
        return

    def wrapper(self, *args, **kwargs):
        args, kwargs = _tr_args(args, kwargs)
        return orig(self, *args, **kwargs)

    wrapper._bc_i18n = True  # type: ignore[attr-defined]
    try:
        setattr(cls, name, wrapper)
    except (TypeError, AttributeError) as exc:  # pragma: no cover
        logger.debug("i18n: cannot wrap %s.%s: %s", cls.__name__, name, exc)


def _wrap_static(cls, name: str) -> None:
    orig = getattr(cls, name, None)
    if orig is None or getattr(orig, "_bc_i18n", False):
        return

    def wrapper(*args, **kwargs):
        args, kwargs = _tr_args(args, kwargs)
        return orig(*args, **kwargs)

    wrapper._bc_i18n = True  # type: ignore[attr-defined]
    try:
        setattr(cls, name, staticmethod(wrapper))
    except (TypeError, AttributeError) as exc:  # pragma: no cover
        logger.debug("i18n: cannot wrap static %s.%s: %s", cls.__name__, name, exc)


def _wrap_set_data(cls) -> None:
    """Translate display/tooltip strings stored via ``setData(role, str)``."""
    from PySide6.QtCore import Qt

    orig = getattr(cls, "setData", None)
    if orig is None or getattr(orig, "_bc_i18n", False):
        return
    roles = {Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ToolTipRole}

    def wrapper(self, *args):
        if len(args) >= 2 and isinstance(args[-1], str):
            role = args[-2]
            if role in roles:
                args = (*args[:-1], tr(args[-1]))
        return orig(self, *args)

    wrapper._bc_i18n = True  # type: ignore[attr-defined]
    setattr(cls, "setData", wrapper)


def install(language: str | None = None) -> str:
    """Load the dictionary and wrap Qt text entry points. Returns the language."""
    global _installed
    set_language(language or saved_language())
    if _installed:
        return _lang
    _installed = True

    from PySide6 import QtGui, QtWidgets

    W, G = QtWidgets, QtGui
    methods: dict[object, tuple[str, ...]] = {
        W.QWidget: ("setToolTip", "setWindowTitle", "setStatusTip", "setWhatsThis",
                    "setAccessibleName", "setAccessibleDescription"),
        W.QLabel: ("__init__", "setText"),
        W.QAbstractButton: ("setText",),
        W.QPushButton: ("__init__",),
        W.QToolButton: ("__init__",),
        W.QCheckBox: ("__init__",),
        W.QRadioButton: ("__init__",),
        W.QGroupBox: ("__init__", "setTitle"),
        G.QAction: ("__init__", "setText", "setToolTip", "setStatusTip", "setIconText"),
        W.QMenu: ("__init__", "setTitle", "addMenu", "addAction", "addSection"),
        W.QMenuBar: ("addMenu", "addAction"),
        W.QToolBar: ("__init__", "addAction"),
        W.QComboBox: ("addItem", "addItems", "insertItem", "insertItems", "setItemText",
                      "setPlaceholderText"),
        W.QTabWidget: ("addTab", "insertTab", "setTabText", "setTabToolTip"),
        W.QLineEdit: ("setPlaceholderText",),
        W.QTextEdit: ("setPlaceholderText",),
        W.QPlainTextEdit: ("setPlaceholderText",),
        W.QSpinBox: ("setSuffix", "setPrefix", "setSpecialValueText"),
        W.QDoubleSpinBox: ("setSuffix", "setPrefix", "setSpecialValueText"),
        W.QStatusBar: ("showMessage",),
        W.QMessageBox: ("__init__", "setText", "setInformativeText", "setDetailedText",
                        "addButton", "setWindowTitle"),
        W.QDialogButtonBox: ("addButton",),
        W.QTableWidgetItem: ("__init__", "setText", "setToolTip", "setStatusTip"),
        W.QListWidgetItem: ("__init__", "setText", "setToolTip"),
        W.QTreeWidgetItem: ("setText", "setToolTip"),
        W.QListWidget: ("addItem", "addItems"),
        W.QTableWidget: ("setHorizontalHeaderLabels", "setVerticalHeaderLabels"),
        W.QTreeWidget: ("setHeaderLabels", "setHeaderLabel"),
        W.QProgressBar: ("setFormat",),
        W.QDockWidget: ("__init__",),
        G.QStandardItem: ("__init__", "setText", "setToolTip"),
        G.QStandardItemModel: ("setHorizontalHeaderLabels", "setVerticalHeaderLabels"),
        G.QPainter: ("drawText",),
    }
    for cls, names in methods.items():
        for name in names:
            _wrap_method(cls, name)

    for name in ("information", "warning", "critical", "question", "about"):
        _wrap_static(W.QMessageBox, name)
    for name in ("getOpenFileName", "getOpenFileNames", "getSaveFileName",
                 "getExistingDirectory"):
        _wrap_static(W.QFileDialog, name)
    for name in ("getText", "getItem", "getInt", "getDouble", "getMultiLineText"):
        _wrap_static(W.QInputDialog, name)
    _wrap_static(W.QToolTip, "showText")

    _wrap_set_data(W.QTableWidgetItem)
    _wrap_set_data(G.QStandardItem)
    _install_qt_translator()
    logger.info("[I18N] UI language: %s (%d exact, %d templates)",
                _lang, len(_exact), len(_templates))
    return _lang


def _install_qt_translator() -> None:
    """Load Qt's own translation so standard buttons (Yes/No/Save/Cancel…)
    of message boxes and dialogs follow the UI language."""
    if _lang not in ("pl", "it"):  # English is Qt's own language
        return
    try:
        import os

        import PySide6
        from PySide6.QtCore import QCoreApplication, QLibraryInfo, QTranslator

        app = QCoreApplication.instance()
        if app is None:
            return
        translator = QTranslator(app)
        for folder in (
            os.path.join(os.path.dirname(PySide6.__file__), "translations"),
            QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath),
        ):
            if translator.load(f"qtbase_{_lang}", folder):
                app.installTranslator(translator)
                return
        logger.warning("[I18N] Qt translation qtbase_%s not found", _lang)
    except Exception:  # pragma: no cover - never block startup on this
        logger.debug("[I18N] Qt translator not installed", exc_info=True)


__all__: list[str] = [
    "LANGUAGES", "DEFAULT_LANGUAGE", "tr", "install", "current_language",
    "saved_language", "save_language", "set_language",
]
