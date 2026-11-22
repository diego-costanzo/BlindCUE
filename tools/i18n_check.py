"""List UI strings in blindcue/ that have no Polish (or English) translation yet.

Run after pulling a new upstream version:

    python tools/i18n_check.py            # missing Polish entries
    python tools/i18n_check.py en         # missing English entries

Each missing string is printed with its file:line. Add it to
blindcue/i18n/pl.py (and en.py) as  'original text': 'translation',
keeping the same number of {} placeholders. Strings that are not shown in
the UI (identifiers, file names) can simply be ignored.
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
CSS_RE = re.compile(r"[{};]\s*$|^\s*[\w\-]+\s*:\s*[^ ]+;|background-color|font-size|border:|padding:", re.I)
PH_RE = re.compile(r"\{[^{}]*\}|%(?:\.\d+)?[sdif]")


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
            if COLOR_RE.match(st) or IDENT_RE.match(st) or CSS_RE.search(st):
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


def main() -> int:
    lang = sys.argv[1] if len(sys.argv) > 1 else "pl"
    table = load_table(lang)
    missing = {s: where for s, where in candidates().items() if s not in table}
    for s, where in missing.items():
        print(f"{where[0]:45} {s!r}")
    print(f"\n{len(missing)} strings without a '{lang}' entry "
          f"(some are technical and can be ignored).")
    bad = [k for k, v in table.items() if len(PH_RE.findall(k)) != len(re.findall(r"\{\d*\}", v))]
    for k in bad:
        print(f"PLACEHOLDER MISMATCH: {k!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
