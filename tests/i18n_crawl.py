"""Runtime crawl of the UI in Polish (or English): visible texts still in Italian.

Builds the real MainWindow offscreen with ``i18n.install(<lang>)``, fills it
with one cue of every kind, walks it in Preparation, Rehearsal and Show
(inspector on every cue kind), constructs the dialogs that can be built
without a modal ``exec()`` and collects every text a user can see: labels,
buttons, tooltips, accessible names, menus, combo items, tabs, table cells,
spin box suffixes, window titles and the text painted with ``QPainter``.

A text is a *leftover* when it holds a word of the source language that no
translation uses ("foreign" vocabulary = words of the dictionary keys and of
the code's string constants, minus the words of the translations, minus
``ALLOWED`` proper names / technical words).

``i18n.install()`` wraps Qt classes for the whole process, so this runs in a
process of its own: ``tests/test_i18n_crawl.py`` starts it with
``--json`` and fails on leftovers. By hand:

    python tests/i18n_crawl.py            # Polish, readable report
    python tests/i18n_crawl.py en         # English
"""

from __future__ import annotations

import contextlib
import html
import importlib.util
import json
import os
import re
import sys
import tempfile
import time
import traceback
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

TESTS = Path(__file__).resolve().parent
ROOT = TESTS.parent
APP_DIR = ROOT / "blindcue"
for _p in (str(APP_DIR), str(TESTS)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import conftest  # noqa: F401  - sandboxed settings / home / app data

# Proper names, units and technical words that stay as they are in every
# language (lower case). Keep this short: a word here is never reported.
ALLOWED = {
    # product, people, programs, formats, hardware
    "blindcue", "teatr", "poza", "diego", "costanzo", "ciechomir", "ffmpeg", "ffprobe",
    "vlc", "obs", "claude", "mcp", "mcpb", "json", "csv", "html", "png", "jpg", "jpeg",
    "mp3", "mp4", "wav", "flac", "ogg", "aac", "mkv", "mov", "webm", "gif", "bmp", "webp",
    "m3u", "osc", "udp", "tcp", "http", "https", "lan", "wifi", "hdmi", "usb", "dmx",
    "midi", "qr", "pin", "ebu", "lufs", "lra", "dbtp", "rms", "cpu", "gpu", "ram",
    "opengl", "egl", "mesa", "vaapi", "nvidia", "intel", "amd", "radeon", "direct",
    "wayland", "windows", "linux", "macos", "x11", "qt", "pyside", "python",
    "utf", "rgb", "rgba", "fps", "px", "db", "khz", "hz", "ms",
    # words the user decided to keep in Polish too
    "go", "panic", "cue", "cues", "auto",
}

# Whole texts that stay as they are on purpose: the language menu names each
# language in its own words.
ALLOWED_TEXTS = {
    "🌐 Lingua / Language / Język",
    "Italiano (originale)",
}

WORD_RE = re.compile(r"[^\W\d_]{3,}")
TAG_RE = re.compile(r"<[^>]+>")
PH_RE = re.compile(r"\{[^{}]*\}|%(?:\.\d+)?[sdif]")
STYLE_RE = re.compile(r"<style.*?</style>", re.DOTALL | re.IGNORECASE)
# File paths and file-type filters are names, not words to translate.
PATH_RE = re.compile(r"\w+://\S+|(?<![A-Za-z])[A-Za-z]:[\\/][^\n'\"“”„]*|\*\.\w+|\(\*\)"
                     r"|\w+\.(?:csv|json|html|blindcue|mcpb|png|mp3|mp4)\b")


def _plain(text: str) -> str:
    text = STYLE_RE.sub(" ", text)
    text = TAG_RE.sub(" ", text)
    return PATH_RE.sub(" ", html.unescape(text).replace("&", ""))


def system_names() -> set[str]:
    """Words of this computer's device and screen names (they are shown as the system gives them)."""
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtMultimedia import QMediaDevices

    # Outputs only: listing the microphones (audioInputs) left the process hanging at exit on Windows.
    names = [d.description() for d in QMediaDevices.audioOutputs()]
    for screen in QGuiApplication.screens():
        names += [screen.name(), screen.manufacturer(), screen.model()]
    import platform

    names += [os.environ.get("COMPUTERNAME", ""), platform.processor()]
    return {w.lower() for n in names for w in WORD_RE.findall(n or "")}


def _load_table(lang: str) -> dict[str, str]:
    spec = importlib.util.spec_from_file_location(f"i18n_{lang}_crawl", APP_DIR / "i18n" / f"{lang}.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod.T


def foreign_vocabulary(lang: str) -> set[str]:
    """Words of the source strings that no translation into *lang* uses."""
    table = _load_table(lang)
    sys.path.insert(0, str(ROOT / "tools"))
    try:
        import i18n_check
        sources = list(i18n_check.candidates()) + list(table)
    finally:
        sys.path.remove(str(ROOT / "tools"))
    source_words = {w.lower() for s in sources for w in WORD_RE.findall(_plain(PH_RE.sub(" ", s)))}
    target_words = {w.lower() for v in table.values() for w in WORD_RE.findall(_plain(v))}
    if lang == "en":
        # English source strings need no English entry: their words are English.
        # They are the keys with an identical entry, or with a Polish entry only.
        polish = _load_table("pl")
        english = [k for k in table if table[k] == k] + [k for k in polish if k not in table]
        target_words |= {w.lower() for k in english for w in WORD_RE.findall(_plain(PH_RE.sub(" ", k)))}
    return source_words - target_words - ALLOWED


class Crawl:
    def __init__(self, lang: str) -> None:
        self.lang = lang
        self.texts: dict[str, set[str]] = {}

    def add(self, where: str, text) -> None:
        if isinstance(text, str) and text.strip():
            self.texts.setdefault(text, set()).add(where)

    # ── widgets ───────────────────────────────────────────────────────
    def widget(self, w, where: str) -> None:
        import i18n
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import (
            QAbstractButton,
            QAbstractItemView,
            QAbstractSpinBox,
            QComboBox,
            QDoubleSpinBox,
            QGroupBox,
            QLabel,
            QLineEdit,
            QMenu,
            QPlainTextEdit,
            QSpinBox,
            QTabBar,
            QTextEdit,
        )

        name = f"{where}/{type(w).__name__}"
        if w.objectName():
            name += f"#{w.objectName()}"
        for kind, value in (("tooltip", w.toolTip()), ("accessibleName", w.accessibleName()),
                            ("accessibleDescription", w.accessibleDescription()),
                            ("statusTip", w.statusTip()), ("whatsThis", w.whatsThis())):
            self.add(f"{name} [{kind}]", value)
        if w.isWindow():
            self.add(f"{name} [windowTitle]", w.windowTitle())
        if isinstance(w, QLabel):
            self.add(f"{name} [text]", w.text())
        if isinstance(w, QAbstractButton):
            # HoldProgressButton keeps its source text and paints it through tr().
            painted = type(w).__name__ == "HoldProgressButton"
            self.add(f"{name} [text]", i18n.tr(w.text()) if painted else w.text())
        if isinstance(w, QGroupBox):
            self.add(f"{name} [title]", w.title())
        if isinstance(w, QLineEdit):
            self.add(f"{name} [placeholder]", w.placeholderText())
            if w.isReadOnly():
                self.add(f"{name} [text]", w.text())
        if isinstance(w, (QTextEdit, QPlainTextEdit)):
            self.add(f"{name} [placeholder]", w.placeholderText())
            # The user manual (QTextBrowser) is a document of its own, written per language.
            if w.isReadOnly() and type(w).__name__ != "QTextBrowser":
                self.add(f"{name} [text]", w.toPlainText())
        if isinstance(w, QComboBox):
            for i in range(w.count()):
                self.add(f"{name} [item]", w.itemText(i))
                self.add(f"{name} [item tooltip]", w.itemData(i, Qt.ItemDataRole.ToolTipRole))
        if isinstance(w, QTabBar):
            for i in range(w.count()):
                self.add(f"{name} [tab]", w.tabText(i))
                self.add(f"{name} [tab tooltip]", w.tabToolTip(i))
        if isinstance(w, (QSpinBox, QDoubleSpinBox)):
            for kind, value in (("suffix", w.suffix()), ("prefix", w.prefix()),
                                ("special", w.specialValueText())):
                self.add(f"{name} [{kind}]", value)
        if isinstance(w, QAbstractSpinBox):
            self.add(f"{name} [spin text]", w.text() if not w.text()[:1].isdigit() else "")
        if isinstance(w, QAbstractItemView) and w.model() is not None:
            self.model(w.model(), name)
        if isinstance(w, QMenu):
            self.menu(w, name)
        for act in w.actions():
            if isinstance(w, QMenu):
                continue
            self.action(act, name)

    def model(self, model, name: str) -> None:
        from PySide6.QtCore import QModelIndex, Qt

        roles = (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ToolTipRole)
        rows = model.rowCount(QModelIndex())
        try:
            cols = model.columnCount(QModelIndex())
        except TypeError:  # QAbstractListModel: one column, columnCount() is private
            cols = 1
        for orient, count in ((Qt.Orientation.Horizontal, cols), (Qt.Orientation.Vertical, rows)):
            for i in range(min(count, 60)):
                for role in roles:
                    value = model.headerData(i, orient, role)
                    if orient == Qt.Orientation.Vertical and str(value) == str(i + 1):
                        continue
                    self.add(f"{name} [header]", value)
        for r in range(min(rows, 80)):
            for c in range(min(cols, 20)):
                idx = model.index(r, c)
                for role in roles:
                    self.add(f"{name} [cell]", model.data(idx, role))

    def action(self, act, name: str) -> None:
        if act.isSeparator():
            return
        label = act.text()
        self.add(f"{name} [action]", label)
        tip = act.toolTip()
        if tip and tip.replace("&", "") != label.replace("&", ""):
            self.add(f"{name} [action tooltip]", tip)
        self.add(f"{name} [action statusTip]", act.statusTip())
        if act.menu() is not None:
            self.menu(act.menu(), f"{name}>{label}")

    def menu(self, menu, name: str) -> None:
        self.add(f"{name} [menu title]", menu.title())
        for act in menu.actions():
            self.action(act, f"{name}>{menu.title()}")

    def tree(self, root, where: str) -> None:
        from PySide6.QtWidgets import QWidget

        self.widget(root, where)
        for child in root.findChildren(QWidget):
            self.widget(child, where)

    def paint(self, w) -> None:
        """Paint *w* (also when hidden) so delegates and custom widgets draw their text."""
        with contextlib.suppress(Exception):  # a widget that cannot paint offscreen
            w.grab()


def _record_painter(crawl: Crawl) -> None:
    """Record what QPainter.drawText puts on screen (after the i18n wrapper)."""
    import i18n
    from PySide6.QtGui import QPainter

    prev = QPainter.drawText

    def drawText(self, *args, **kwargs):
        for a in args:
            if isinstance(a, str):
                crawl.add("painted", i18n.tr(a))
        return prev(self, *args, **kwargs)

    QPainter.drawText = drawText


def _progress(step: str) -> None:
    if os.environ.get("BLINDCUE_CRAWL_VERBOSE"):
        sys.stderr.write(f"[crawl] {step}\n")
        sys.stderr.flush()


def _add_page(crawl: Crawl, where: str, page: str) -> None:
    """A generated page (HTML / CSV): every line of its visible text on its own."""
    for line in _plain(page).splitlines():
        crawl.add(where, line.strip())


def _patch_modals(crawl: Crawl) -> None:
    """Modal dialogs, message boxes, file dialogs and the browser never open:
    they are crawled and answered with "Cancel" / nothing."""
    import i18n
    from PySide6.QtGui import QDesktopServices
    from PySide6.QtWidgets import QDialog, QFileDialog, QInputDialog, QMessageBox

    def fake_exec(self, *args, **kwargs):
        crawl.paint(self)
        crawl.tree(self, f"exec:{type(self).__name__}")
        return 0

    QDialog.exec = fake_exec
    QMessageBox.exec = fake_exec

    def record(kind: str, default):
        def fn(*args, **kwargs):
            for a in list(args) + list(kwargs.values()):
                if isinstance(a, str):
                    crawl.add(kind, i18n.tr(a))
            return default
        return staticmethod(fn)

    for name in ("information", "warning", "critical", "question"):
        setattr(QMessageBox, name, record(f"QMessageBox.{name}", QMessageBox.StandardButton.Cancel))
    QMessageBox.about = record("QMessageBox.about", None)
    QFileDialog.getOpenFileName = record("QFileDialog.getOpenFileName", ("", ""))
    QFileDialog.getSaveFileName = record("QFileDialog.getSaveFileName", ("", ""))
    QFileDialog.getOpenFileNames = record("QFileDialog.getOpenFileNames", ([], ""))
    QFileDialog.getExistingDirectory = record("QFileDialog.getExistingDirectory", "")
    QInputDialog.getText = record("QInputDialog.getText", ("", False))
    QInputDialog.getItem = record("QInputDialog.getItem", ("", False))
    QInputDialog.getInt = record("QInputDialog.getInt", (0, False))
    QInputDialog.getDouble = record("QInputDialog.getDouble", (0.0, False))
    QInputDialog.getMultiLineText = record("QInputDialog.getMultiLineText", ("", False))

    def open_url(url) -> bool:
        path = Path(url.toLocalFile()) if url.isLocalFile() else None
        if path is not None and path.suffix == ".html" and path.is_file():
            _add_page(crawl, f"page:{path.name}", path.read_text(encoding="utf-8"))
        return True

    QDesktopServices.openUrl = staticmethod(open_url)


def _sample_png(folder: Path) -> Path:
    from PySide6.QtGui import QColor, QImage

    img = QImage(64, 36, QImage.Format.Format_ARGB32)
    img.fill(QColor("#336699"))
    path = folder / "zdjecie.png"
    img.save(str(path))
    return path


def crawl_dialogs(crawl: Crawl, win, output, folder: Path, errors: list[str]) -> None:
    """Dialogs built directly (no exec) and the dialogs the menus open (exec patched)."""
    from datetime import datetime

    from engine import run_report as rr
    from engine.device_manager import DeviceManager
    from models.cue import MediaType
    from services.remote_manager import RemoteManager

    def visit(tag: str, build) -> None:
        _progress(tag)
        try:
            dlg = build()
        except Exception:  # noqa: BLE001 - recorded in errors, the crawl goes on
            errors.append(f"{tag}: {traceback.format_exc(limit=4)}")
            return
        try:
            _pump(0.05)
            crawl.paint(dlg)
            crawl.tree(dlg, tag)
        finally:
            dlg.close()
            dlg.deleteLater()
            _pump(0.02)

    def call(tag: str, fn, *args) -> None:
        _progress(tag)
        try:
            fn(*args)
            _pump(0.05)
        except Exception:  # noqa: BLE001 - recorded in errors, the crawl goes on
            errors.append(f"{tag}: {traceback.format_exc(limit=4)}")

    from ui.assistant_dialog import AssistantDialog
    from ui.audio_outputs_dialog import AudioOutputsDialog
    from ui.countdown_window import CountdownWindow
    from ui.device_settings_dialog import DeviceSettingsDialog
    from ui.group_timeline_editor import GroupTimelineStudioDialog
    from ui.help_dialog import HelpDialog
    from ui.key_map_dialog import KeyMapDialog
    from ui.mask_dialog import ImageMaskDialog
    from ui.remote_control_dialog import RemoteControlDialog
    from ui.renumber_dialog import RenumberDialog
    from ui.surface_mapping_dialog import SurfaceMappingDialog
    from ui.text_cue_dialog import TextCueDialog

    device_mgr = DeviceManager()
    remote_mgr = RemoteManager(win)
    group = next(c for c in win._cues if c.media_type == MediaType.GROUP)
    children = [c for c in win._cues if c.parent_id == group.cue_id]
    png = _sample_png(folder)
    visit("DeviceSettingsDialog", lambda: DeviceSettingsDialog(device_mgr, win))
    visit("AudioOutputsDialog", lambda: AudioOutputsDialog(device_mgr, parent=win))
    visit("RemoteControlDialog", lambda: RemoteControlDialog(remote_mgr, win))
    visit("SurfaceMappingDialog", lambda: SurfaceMappingDialog(output, None, win, device_mgr))
    visit("HelpDialog", lambda: HelpDialog(win))
    visit("TextCueDialog", lambda: TextCueDialog(None, win))
    visit("CountdownWindow", lambda: CountdownWindow(win))
    visit("GroupTimelineStudioDialog", lambda: GroupTimelineStudioDialog(group, children, win))
    visit("ImageMaskDialog", lambda: ImageMaskDialog(str(png), None, None, 0.0, win))
    visit("KeyMapDialog", lambda: KeyMapDialog(getattr(win, "_key_map", {}), [], win))
    visit("RenumberDialog", lambda: RenumberDialog(win._cues, [0, 1], win))
    visit("AssistantDialog", lambda: AssistantDialog(win))

    for row in range(len(win._cues)):          # the "Edit cue" window on every kind
        call(f"edit-cue row {row}", win._open_cue_editor, row)
    table = win._cue_list

    def close_menu() -> None:
        # QMenu.exec cannot be replaced in PySide6: read the open menu, then close it.
        from PySide6.QtWidgets import QApplication, QMenu

        menu = QApplication.activePopupWidget()
        if isinstance(menu, QMenu):
            crawl.menu(menu, "context-menu")
            menu.close()

    for row in (0, 3, 5):                       # the list's right-click menu
        _progress(f"context menu row {row}")
        try:
            from PySide6.QtCore import QPoint, QTimer
            from PySide6.QtGui import QContextMenuEvent

            QTimer.singleShot(150, close_menu)
            QTimer.singleShot(2000, close_menu)
            table.setCurrentCell(row, 2)
            rect = table.visualRect(table.model().index(row, 2))
            pos = rect.center() if rect.isValid() else QPoint(10, 10)
            table.contextMenuEvent(QContextMenuEvent(QContextMenuEvent.Reason.Mouse, pos,
                                                     table.viewport().mapToGlobal(pos)))
        except Exception:  # noqa: BLE001 - recorded in errors, the crawl goes on
            errors.append(f"context menu row {row}: {traceback.format_exc(limit=4)}")
    for name, args in (
        ("_open_cheat_sheet", ()), ("_print_list", ("operator",)), ("_print_list", ("prompter",)),
        ("_open_history", ()), ("_open_show_info", ()), ("_open_key_map", ()), ("_renumber_q", ()),
        ("_open_assistant_dialog", ()), ("_ask_countdown", ()), ("_find_missing_files", ()),
        ("_save_version_as", ()), ("_open_last_run_report", ()), ("_import_skeleton", ()),
        ("_import_from_show", ()), ("_export_computer_settings", ()), ("_import_computer_settings", ()),
        ("_search_open", ()), ("_add_tool_program", ()), ("_new_show_from_folder", ()),
        ("_on_add_text_cue", ()), ("_choose_file_for_cue", ()),
    ):
        fn = getattr(win, name, None)
        if fn is None:
            errors.append(f"no method {name}")
            continue
        call(name, fn, *args)

    # The run report and the CSV export: generated pages, read back.
    try:
        ids = [c.cue_id for c in win._cues]
        log = [(0.0, ids[0], win._cues[0].name, True, rr.GO), (2.0, ids[1], win._cues[1].name, False, rr.AUTO)]
        log += [(3.0 + i, -1, "", True, ev) for i, ev in enumerate(
            (rr.PAUSE, rr.RESUME, rr.FADE_ALL, rr.PANIC, rr.BLACKOUT, rr.UNDO_GO, rr.EFFECT, rr.FADE_SCENE, rr.END))]
        target = folder / "raport.html"
        win._write_run_report(target, log, datetime.now())
        _add_page(crawl, "page:run-report", target.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 - recorded in errors, the crawl goes on
        errors.append(f"run report: {traceback.format_exc(limit=4)}")
    try:
        from PySide6.QtWidgets import QFileDialog

        saved = QFileDialog.getSaveFileName
        csv_path = folder / "scaletta.csv"
        QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (str(csv_path), ""))
        try:
            win._export_list_csv()
        finally:
            QFileDialog.getSaveFileName = saved
        for line in csv_path.read_text(encoding="utf-8-sig").splitlines():
            for cell in line.split(";"):
                crawl.add("page:csv", cell)
    except Exception:  # noqa: BLE001 - recorded in errors, the crawl goes on
        errors.append(f"csv export: {traceback.format_exc(limit=4)}")


def _pump(seconds: float = 0.05) -> None:
    from PySide6.QtCore import QCoreApplication

    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.005)


def _sample_cues(folder: Path):
    from engine.action_cues import ACTION_FADE
    from models.cue import Cue, FollowMode, GroupMode, MediaType

    cues = [
        Cue(name="Muzyka na wejście", media_type=MediaType.AUDIO, file_path=str(folder / "muzyka.mp3"),
            layer=2, fade_in=2.0, fade_out=3.0, pre_delay=1.0, post_delay=2.0, notes="po brawach",
            follow_mode=FollowMode.AUTO_FOLLOW.value),
        # Names people type are shown as they are: neither Italian nor English words here.
        Cue(name="Wideo", media_type=MediaType.VIDEO, file_path=str(folder / "wideo.mp4"), layer=1,
            follow_mode=FollowMode.SIMULTANEOUS.value, crossfade=1.0),
        Cue(name="Zdjęcie", media_type=MediaType.IMAGE, file_path=str(folder / "zdjecie.png"), layer=1,
            hold_time=5.0),
    ]
    group = Cue(name="Akt 1", media_type=MediaType.GROUP, file_path="", group_mode=GroupMode.STEP.value)
    cues.append(group)
    cues.append(Cue(name="Dzwonek", media_type=MediaType.AUDIO, file_path=str(folder / "dzwonek.mp3"),
                    layer=2, parent_id=group.cue_id))
    cues.append(Cue(name="Wyciszenie", media_type=MediaType.ACTION, file_path="",
                    action_spec={"kind": ACTION_FADE, "target": "all", "duration": 3.0}))
    return cues


def crawl_main_window(crawl: Crawl, folder: Path, errors: list[str], dialogs: bool = True) -> None:
    from ui.main_window import MainWindow
    from ui.output_window import OutputWindow

    output = OutputWindow()
    win = MainWindow(output)
    with contextlib.suppress(AttributeError):
        win._clock_timer.stop()
    win.resize(1600, 950)
    win.show()
    _pump(0.3)

    def snap(tag: str) -> None:
        _progress(f"snap {tag}")
        _pump(0.1)
        crawl.paint(win)
        crawl.tree(win, tag)
        if win.menuBar() is not None:
            for act in win.menuBar().actions():
                crawl.action(act, f"{tag}/menubar")

    try:
        snap("empty")                                  # start page, empty list
        win._cues = _sample_cues(folder)
        win._refresh_cue_list(keep_selection=False)
        for row in range(len(win._cues)):              # inspector on every cue kind
            try:
                win._cue_list.setCurrentRow(row)
                _pump(0.1)
                snap(f"prep/row{row}:{win._cues[row].media_type.value}")
            except Exception:  # noqa: BLE001 - recorded in errors, the crawl goes on
                errors.append(f"inspector row {row}: {traceback.format_exc(limit=3)}")
        win._cue_list.setCurrentRow(0)
        for tag, enter in (("rehearsal", win._enter_rehearsal),
                           ("show", win._show_from_rehearsal)):
            try:
                enter()
                snap(tag)
            except Exception:  # noqa: BLE001 - recorded in errors, the crawl goes on
                errors.append(f"{tag}: {traceback.format_exc(limit=3)}")
        try:
            win.set_live_mode(False)
            _pump(0.1)
        except Exception:  # noqa: BLE001 - recorded in errors, the crawl goes on
            errors.append(f"leave show: {traceback.format_exc(limit=3)}")
        if dialogs:
            crawl_dialogs(crawl, win, output, folder, errors)
            snap("after-dialogs")                       # status bar texts the openers left
            from PySide6.QtWidgets import QApplication

            for top in QApplication.topLevelWidgets():  # non-modal windows they opened
                if top is not win and top.isVisible():
                    crawl.paint(top)
                    crawl.tree(top, f"window:{type(top).__name__}")
    finally:
        win._force_closing = True
        output.force_close()
        win.close()
        _pump()
        win.deleteLater()
        output.deleteLater()
        _pump()


def run(lang: str) -> dict:
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    import i18n
    i18n.install(lang)
    crawl = Crawl(lang)
    _record_painter(crawl)
    _patch_modals(crawl)
    errors: list[str] = []
    folder = Path(tempfile.mkdtemp(prefix="blindcue-crawl-"))
    crawl_main_window(crawl, folder, errors)
    foreign = foreign_vocabulary(lang) - system_names()
    del app
    leftovers = []
    for text, where in sorted(crawl.texts.items()):
        if text.strip() in ALLOWED_TEXTS:
            continue
        words = sorted({w for w in WORD_RE.findall(_plain(text)) if w.lower() in foreign})
        if words:
            leftovers.append({"text": text, "words": words, "where": sorted(where)[:4]})
    return {"lang": lang, "texts": len(crawl.texts), "leftovers": leftovers, "errors": errors}


def main() -> int:
    import faulthandler

    faulthandler.dump_traceback_later(float(os.environ.get("BLINDCUE_CRAWL_TIMEOUT", "240")), exit=True)
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    lang = args[0] if args else "pl"
    result = run(lang)
    if "--json" in sys.argv:
        sys.stdout.write("\n@@CRAWL@@" + json.dumps(result, ensure_ascii=False) + "\n")
    else:
        for item in result["leftovers"]:
            print(f"{item['words']}  {item['text']!r}")
            for w in item["where"]:
                print(f"        {w}")
        for err in result["errors"]:
            print("ERROR", err)
        print(f"\n{result['texts']} texts, {len(result['leftovers'])} leftovers ({lang}).")
    _hard_exit()
    return 0


def _hard_exit() -> None:
    """Leave without Qt / multimedia teardown: on Windows even os._exit() hung for
    minutes in the DLL detach after the crawl (seen 2026-11-24)."""
    sys.stdout.flush()
    sys.stderr.flush()
    if sys.platform == "win32":
        import ctypes

        kernel32 = ctypes.windll.kernel32
        kernel32.TerminateProcess(kernel32.GetCurrentProcess(), 0)
    os._exit(0)


if __name__ == "__main__":
    main()
