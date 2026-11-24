"""List UI strings in blindcue/ that have no Polish (or English) translation yet.

Run after pulling a new upstream version:

    python tools/i18n_check.py            # missing Polish entries
    python tools/i18n_check.py en         # missing English entries
    python tools/i18n_check.py pl --all   # also the technical strings listed below

Each missing string is printed with its file:line. Add it to
blindcue/i18n/pl.py (and en.py) as  'original text': 'translation',
keeping the same number of {} placeholders. Strings that are not shown in
the UI (identifiers, file names) can simply be ignored.

Without --all the list leaves out what is technical on purpose: the AI
assistant's protocol texts (mcp_server/, read by the AI in English), HTML
markup without words, names in ``__all__``, and the strings of KNOWN_OK.
What is left is worth a look. The runtime check is tests/test_i18n_crawl.py.
"""

from __future__ import annotations

import ast
import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "blindcue"

SKIP_CALLS = {
    "info", "warning", "error", "debug", "critical", "exception", "log",
    "setStyleSheet", "QColor", "QFont", "getattr", "hasattr", "setattr", "get", "setValue",
    "value", "QSettings", "startswith", "endswith", "encode", "decode", "pack", "unpack",
    "open", "Popen", "run", "check_output", "send_header", "send_error", "setObjectName",
    "QKeySequence", "search", "match", "sub", "compile", "findall", "split", "join",
    "replace", "getLogger", "add_argument", "ValueError", "RuntimeError", "TypeError",
    "KeyError", "OSError", "set_palette_colors", "_resolve_binary", "_emit_change",
    "setProperty", "property", "remove", "pop", "setdefault", "isinstance", "getenv",
    "Path", "dumps", "loads", "_draw_tag", "QUrl", "fromLocalFile", "update_video_layout",
    "lower", "upper", "strip", "print", "write",
}
COLOR_RE = re.compile(r"^#[0-9a-fA-F]{3,8}$")
IDENT_RE = re.compile(r"^[a-z0-9_./\-:]+$")
CSS_RE = re.compile(r"[{};]\s*$|^\s*[\w\-]+\s*:\s*[^ ]+;|background-color|font-size|border:|padding:", re.IGNORECASE)
PH_RE = re.compile(r"\{[^{}]*\}|%(?:\.\d+)?[sdif]")
NAMED_PH_RE = re.compile(r"\{\w*\}")
TAG_RE = re.compile(r"<[^>]*>")

# Files whose strings never reach the teacher's screen in the UI language.
TECHNICAL_FILES = (
    "mcp_server/",              # the AI assistant's tools: English for the AI, not UI text
    "engine/hardware_profile.py",  # Windows API field names, GPU vendor names
    "version.py",               # product, author and repository names
)
# Strings that stay as they are on purpose (names, keys, units, formats, data
# for other programs). Keep the reason next to each group.
KNOWN_OK = {
    # key names and shortcuts
    "PgDown", "PgUp", "Enter", "Return", "Ctrl+P", "Ctrl+B",
    # proper names, fonts, file names, file filters, units
    "BlindCue", "Segoe UI", "BlindCue-logo.jpeg", "BlindCue-", "Mesa/EGL", " dB", "{} dB",
    "1920×1080 px", "{}×{} px", "🖥 {}×{} px", "{} px @1920", " (Feather {}px)", " · 🖼 PNG",
    "{}{} [{}×{} px]", " [PIN {}]", "📡 Web: {}{}", "📡 OSC: UDP {}", "✋ OK", "HH:mm:ss",
    "IN: {}s", "OUT: {}s", "⤵ AUTO-GO", "Auto-GO",
    "JSON (*.json)", "CSV (*.csv)", "CSV (*.csv *.txt)", "BlindCue (*.blindcue)", "Playlist (*.m3u *.m3u8)",
    ("Media (*.mp4 *.mkv *.avi *.mov *.webm *.mp3 *.wav *.flac *.ogg *.aac *.m4a *.png *.jpg *.jpeg "
     "*.bmp *.gif *.webp)"),
    "*.csv", "*.html", "{}.csv", "{}.blindcue", "{}.mcpb", "blindcue_{}.html", "caption_{}.png", "{}_copy",
    "corner_{}", ".{}.tmp", "{} {}.blindcue", "%Y-%m-%d", "%Y-%m-%d_%H%M%S", "%Y-%m-%d %H-%M-%S",
    # column aliases read from a spreadsheet (quick start), not shown
    "tytuł", "ścieżka", "cue line",
    # the language menu names each language in its own words; the restart note
    # is written in the language just chosen
    "🌐 Lingua / Language / Język",
    "La lingua dell'interfaccia cambierà al prossimo avvio di BlindCue.",
    "The interface language will change after restarting BlindCue.",
    "Język interfejsu zostanie zmieniony po ponownym uruchomieniu BlindCue.",
    # data for the phone remote page (translated there) and the AI assistant link
    "ON AIR", "Media L{}", "bad token", "The program could not do this: {}",
    "The teacher is running the show: save it in Preparation.",
    "This show has no file yet: ask the teacher to save it once (Ctrl+S).",
    "The program could not save the show.", "'{}' is not available while connected to the program.",
    "Unknown arguments for {}: {}.", "The program needs a full path.", "'{}' does not exist.",
    ("The teacher is running the show (Rehearsal or Show): the assistant changes it only in Preparation. "
     "Try again later."),
    "The teacher is looking at the readiness page: try again in a moment.",
    # internal names: object names, roles, regular expressions, ffmpeg filters, URLs, log formats
    "inspCard", "inspCardTitle", "ENVELOPE_LINE", "[A-Za-z0-9]?",
    "^$|^([01]?\\d|2[0-3]):[0-5]\\d(:[0-5]\\d)?$", "(\\d+(?:\\.\\d*)?|\\.\\d+)",
    "ebur128=peak=true", "{}_ebur128_{}{}", ".{}_ebur128_{}.{}.tmp{}", "loudnorm=I={}:TP={}:LRA={}",
    "http://{}:{}", "{}/?pin={}", "http://{}:{}/monitor", "{}?pin={}", "udp://{}:{}", "/blindcue/{}/",
    "%(asctime)s [%(levelname)s] %(name)s: %(message)s", "BlindCue – live cue player",
    "Cue #{} '{}' [{}]{} ({})", "Live show playback in progress", " class='alarm'", "manual_{}.html",
    "ACLineStatus", "BatteryFlag", "BatteryLifePercent", "SystemStatusFlag", "BatteryLifeTime",
    "BatteryFullLifeTime",
}
# Cue.validate() checks the program itself never lets happen (the fields have
# their ranges in the UI); "Media file not found" is translated.
VALIDATE_RE = re.compile(r"^[\w\[\]'{}()]+ (must|needs) ")


def call_name(func: ast.expr) -> str:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return "?"


def template(node: ast.JoinedStr) -> str:
    return "".join(
        v.value.replace("{", "{{").replace("}", "}}") if isinstance(v, ast.Constant) else "{}"
        for v in node.values
    )


def candidates() -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for path in sorted(ROOT.rglob("*.py")):
        rel = path.relative_to(ROOT).as_posix()
        if rel.startswith("i18n/") or rel.endswith("web_server.py"):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        parents = {ch: node for node in ast.walk(tree) for ch in ast.iter_child_nodes(node)}
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if isinstance(parents.get(node), (ast.JoinedStr, ast.FormattedValue)):
                    continue
                s = node.value
            elif isinstance(node, ast.JoinedStr):
                s = template(node)
            else:
                continue
            if sum(c.isalpha() for c in s) < 2:
                continue
            p = parents.get(node)
            if isinstance(p, (ast.Expr, ast.Subscript, ast.Compare)):
                continue
            if isinstance(p, ast.Dict) and node in p.keys:
                continue
            c = p
            while c is not None and not isinstance(c, (ast.Call, ast.stmt, ast.Compare)):
                c = parents.get(c)
            if isinstance(c, ast.Compare):
                continue
            if isinstance(c, ast.Call) and call_name(c.func) in SKIP_CALLS:
                continue
            st = s.strip()
            # Placeholders are not CSS: "Audio Preview: {}" ends with "}" but is UI text.
            if COLOR_RE.match(st) or IDENT_RE.match(st) or CSS_RE.search(NAMED_PH_RE.sub("", st)):
                continue
            if st.isupper() and len(st) <= 12 and " " not in st:
                continue
            found.setdefault(s, []).append(f"{rel}:{node.lineno}")
    return found


def load_table(lang: str) -> dict[str, str]:
    spec = importlib.util.spec_from_file_location(f"i18n_{lang}", ROOT / "i18n" / f"{lang}.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod.T


def technical(s: str, where: list[str]) -> bool:
    """True for strings that are not UI text in the UI language (see the module doc)."""
    if all(w.startswith(TECHNICAL_FILES) for w in where):
        return True
    if all("/__init__.py:" in w and w.startswith(("models/", "ui/main_window/")) for w in where):
        return True  # __all__ lists
    words = PH_RE.sub("", TAG_RE.sub("", s))
    if sum(c.isalpha() for c in words) < 2:
        return True  # markup only: "<tr>{}</tr>"
    return s in KNOWN_OK or bool(VALIDATE_RE.match(s))


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    lang = args[0] if args else "pl"
    show_all = "--all" in sys.argv
    table = load_table(lang)
    # tr() strips surrounding blanks before the lookup: "\n… e altri {}" is covered by "… e altri {}".
    missing = {s: where for s, where in candidates().items() if s not in table and s.strip() not in table}
    hidden = 0
    if not show_all:
        before = len(missing)
        missing = {s: where for s, where in missing.items() if not technical(s, where)}
        hidden = before - len(missing)
    for s, where in missing.items():
        print(f"{where[0]:45} {s!r}")
    print(f"\n{len(missing)} strings without a '{lang}' entry"
          + (f" ({hidden} technical ones not shown: --all lists them)." if not show_all else
             " (some are technical and can be ignored)."))
    bad = [k for k, v in table.items() if len(PH_RE.findall(k)) != len(re.findall(r"\{\d*\}", v))]
    for k in bad:
        print(f"PLACEHOLDER MISMATCH: {k!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
