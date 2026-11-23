# PyInstaller spec for the self-contained Windows build of BlindCue.
# Build with packaging\windows\build.ps1 (it sets BLINDCUE_FFMPEG_DIR).
import os
from pathlib import Path

HERE = Path(SPECPATH).resolve()
ROOT = HERE.parents[1]
APP = ROOT / "blindcue"
FFMPEG = Path(os.environ.get("BLINDCUE_FFMPEG_DIR", ""))

binaries = []
for exe_name in ("ffmpeg.exe", "ffprobe.exe"):
    exe_path = FFMPEG / exe_name
    if not exe_path.is_file():
        raise SystemExit(f"Missing {exe_path} - set BLINDCUE_FFMPEG_DIR to FFmpeg's bin folder")
    binaries.append((str(exe_path), "ffmpeg"))

datas = [(str(APP / "assets"), "assets")]
if (APP / "help").is_dir():  # built-in user manual (F1), when present
    datas.append((str(APP / "help"), "help"))

a = Analysis(
    [str(APP / "main.py")],
    pathex=[str(APP)],
    binaries=binaries,
    datas=datas,
    # The translation dictionaries are imported by name at runtime.
    hiddenimports=["i18n.pl", "i18n.en"],
    runtime_hooks=[str(HERE / "rthook_ffmpeg.py")],
    excludes=[
        "tkinter",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtWebEngineQuick",
        "PySide6.Qt3DCore",
        "PySide6.QtQuick3D",
        "PySide6.QtCharts",
        "PySide6.QtDataVisualization",
        "PySide6.QtGraphs",
        "PySide6.QtPdf",
        "PySide6.QtDesigner",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="BlindCue",
    icon=str(ROOT / "setup" / "assets" / "blindcue.ico"),
    console=False,
    upx=False,
)

# The show assistant: an MCP server over stdio, started by an AI client
# (Claude Desktop). A console program - a windowed PyInstaller build has no
# stdin/stdout - sharing the program's _internal folder.
b = Analysis(
    [str(APP / "mcp_server" / "server.py")],
    pathex=[str(APP)],
    binaries=binaries,
    datas=[d for d in datas if d[1] == "help"],
    hiddenimports=["mcp.server.fastmcp", "mcp_server.show_tools", "mcp_server.program_link"],
    runtime_hooks=[str(HERE / "rthook_ffmpeg.py")],
    excludes=["tkinter", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick",
              "PySide6.Qt3DCore", "PySide6.QtQuick3D", "PySide6.QtCharts", "PySide6.QtDataVisualization",
              "PySide6.QtGraphs", "PySide6.QtPdf", "PySide6.QtDesigner"],
    noarchive=False,
)
pyz_b = PYZ(b.pure)
exe_b = EXE(
    pyz_b,
    b.scripts,
    [],
    exclude_binaries=True,
    name="BlindCue-Assistant",
    icon=str(ROOT / "setup" / "assets" / "blindcue.ico"),
    console=True,
    upx=False,
)
coll = COLLECT(exe, exe_b, a.binaries, a.datas, b.binaries, b.datas, name="BlindCue", upx=False)
