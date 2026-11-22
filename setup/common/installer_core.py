"""BlindCue installer: platform detection and install-location helpers.

Shared by ``setup.py`` and the graphical installer window. Deliberately free of
third-party imports so it also runs on a bare Python installation, before
PySide6 (and therefore BlindCue itself) has been installed.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

SETUP_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = SETUP_DIR.parent

# Destination of a per-user installation, one per operating system.
LINUX_APP_NAME = "blindcue"
MACOS_APP_NAME = "BlindCue.app"
WINDOWS_APP_NAME = "BlindCue"

# Messaggio mostrato dopo la disinstallazione (testo unico per GUI e terminale).
FAREWELL = (
    "Grazie per aver provato BlindCue.\n\n"
    "Se qualcosa non ha funzionato come speravi, ci dispiace: BlindCue è un "
    "progetto libero e open source e ogni segnalazione aiuta a renderlo "
    "migliore. Puoi reinstallarlo in qualsiasi momento con python3 setup.py.\n\n"
    "I tuoi progetti non sono stati toccati."
)


def current_platform() -> str:
    """Return one of ``linux``, ``macos``, ``windows`` (``other`` if unknown)."""
    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    if sys.platform.startswith("linux"):
        return "linux"
    return "other"


def platform_label(platform: str | None = None) -> str:
    """Human readable operating system name for the UI."""
    names = {"linux": "Linux", "macos": "macOS", "windows": "Windows"}
    return names.get(platform or current_platform(), "Sistema sconosciuto")


def install_dir(platform: str | None = None) -> Path:
    """Where BlindCue is installed for the current user (no admin rights)."""
    platform = platform or current_platform()
    override = os.environ.get("BLINDCUE_PREFIX")
    if override:
        return Path(override).expanduser()

    if platform == "windows":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "Programs" / WINDOWS_APP_NAME
    if platform == "macos":
        return Path.home() / "Applications" / MACOS_APP_NAME

    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / LINUX_APP_NAME


def engine_script(platform: str | None = None) -> Path:
    """Path of the per-OS installer script executed by the GUI."""
    platform = platform or current_platform()
    if platform == "windows":
        return SETUP_DIR / "windows" / "install.bat"
    if platform == "macos":
        return SETUP_DIR / "macos" / "install.command"
    return SETUP_DIR / "linux" / "install.sh"


def run_script(platform: str | None = None) -> Path:
    """Path of the per-OS launcher used after a successful install."""
    platform = platform or current_platform()
    if platform == "windows":
        return SETUP_DIR / "windows" / "run.bat"
    if platform == "macos":
        return SETUP_DIR / "macos" / "run.command"
    return SETUP_DIR / "linux" / "run.sh"


def icon_path(platform: str | None = None) -> Path:
    """Bundled icon for the graphical installer window."""
    platform = platform or current_platform()
    name = "blindcue.ico" if platform == "windows" else "blindcue-256.png"
    candidate = SETUP_DIR / "assets" / name
    if candidate.is_file():
        return candidate
    candidate_app = SETUP_DIR.parent / "blindcue" / "assets" / name
    if candidate_app.is_file():
        return candidate_app
    return candidate


def engine_command(extra_args: list[str] | None = None) -> list[str]:
    """Command line that runs the installer script for this operating system.

    The command always expects to be started with ``cwd`` set to the script's
    own folder: on Windows only the bare file name is used, so paths containing
    spaces never break ``cmd.exe`` quoting.
    """
    platform = current_platform()
    script = engine_script(platform)
    args = list(extra_args or [])
    if platform == "windows":
        # ".\" prefix: works even when NoDefaultCurrentDirectoryInExePath is set
        return ["cmd", "/c", ".\\" + script.name, *args]
    return ["/bin/bash", str(script), *args]


def is_installed(platform: str | None = None) -> bool:
    """True when a previous per-user installation exists."""
    platform = platform or current_platform()
    target = install_dir(platform)
    if platform == "macos":
        return (target / "Contents" / "MacOS" / "BlindCue").is_file()
    if platform == "windows":
        return (target / "venv" / "Scripts" / "python.exe").is_file()
    return (target / "venv" / "bin" / "python").is_file()


def user_data_paths(platform: str | None = None) -> list[Path]:
    """Files BlindCue creates outside its install folder (settings, autosave).

    Two very different things live here on purpose: preferences (safe to throw
    away) and the autosave (an unsaved project, potentially precious). The
    caller must ask before deleting these — they are never removed by default.
    """
    platform = platform or current_platform()

    if platform == "windows":
        roaming = Path(os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming"))
        return [roaming / "BlindCue"]
    if platform == "macos":
        return [Path.home() / "Library" / "Preferences" / "com.BlindCue.BlindCue.plist"]

    config = Path(os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config"))
    return [config / "blindcue", config / "BlindCue"]


def _windows_shortcuts() -> list[Path]:
    """Shortcut files created by ``install.bat`` (Desktop + Start menu)."""
    name = "BlindCue.lnk"
    home = Path.home()
    candidates = [home / "Desktop" / name]
    onedrive = os.environ.get("OneDrive")
    if onedrive:
        candidates.append(Path(onedrive) / "Desktop" / name)
    roaming = Path(os.environ.get("APPDATA") or (home / "AppData" / "Roaming"))
    programs = roaming / "Microsoft" / "Windows" / "Start Menu" / "Programs"
    candidates.append(programs / name)
    candidates.append(programs / "Uninstall BlindCue.lnk")
    # Standalone uninstaller, kept next to the install folder.
    candidates.append(install_dir("windows").parent / "BlindCue-uninstall.bat")
    return candidates


def _linux_desktop_shortcuts() -> list[Path]:
    """Desktop launcher copies created by ``install.sh`` (one per desktop folder)."""
    candidates: list[Path] = []
    try:
        result = subprocess.run(
            ["xdg-user-dir", "DESKTOP"], capture_output=True, text=True, check=False
        )
        value = result.stdout.strip()
        if value and Path(value) != Path.home():
            candidates.append(Path(value) / "blindcue.desktop")
    except OSError:
        pass
    for name in ("Desktop", "Scrivania", "desktop"):
        candidates.append(Path.home() / name / "blindcue.desktop")

    unique: list[Path] = []
    for candidate in candidates:
        if candidate not in unique:
            unique.append(candidate)
    return unique


def _remove_path(path: Path) -> bool:
    """Delete a file or a directory tree if present. Never raises."""
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path, ignore_errors=True)
        return True
    if path.exists():
        try:
            path.unlink()
        except OSError:
            return False
        return True
    return False


def uninstall(
    platform: str | None = None, purge_user_data: bool = False
) -> list[str]:
    """Delete the per-user installation and its launcher entries.

    Returns the list of paths that were removed, so the caller can show it.
    User data (settings, autosave) is removed only when ``purge_user_data`` is
    True: the autosave can contain an unsaved show.
    """
    platform = platform or current_platform()
    target = install_dir(platform)
    removed: list[str] = []

    if target.exists():
        shutil.rmtree(target, ignore_errors=True)
        removed.append(str(target))

    extras: list[Path] = []
    if platform == "linux":
        home = Path.home()
        data = Path(os.environ.get("XDG_DATA_HOME") or (home / ".local" / "share"))
        icon_sizes = ["16x16", "24x24", "32x32", "48x48", "64x64", "128x128", "256x256", "512x512"]
        icon_files = [data / "icons" / "hicolor" / s / "apps" / "blindcue.png" for s in icon_sizes]
        extras = [
            home / ".local" / "bin" / "blindcue",
            home / ".local" / "bin" / "blindcue-uninstall",
            data / "applications" / "blindcue.desktop",
            data / "applications" / "blindcue-uninstall.desktop",
            *icon_files,
            data / "pixmaps" / "blindcue.png",
            *_linux_desktop_shortcuts(),
        ]
    elif platform == "windows":
        extras = _windows_shortcuts()
    elif platform == "macos":
        # Il bundle è la destinazione stessa: qui va solo la registrazione
        # nel Launchpad/Dock, senza la quale resterebbe un'icona fantasma.
        extras = [install_dir("macos").parent / "BlindCue Uninstall.command"]
        for tool in (
            "/System/Library/Frameworks/CoreServices.framework/Frameworks/"
            "LaunchServices.framework/Support/lsregister",
        ):
            if Path(tool).is_file():
                try:
                    subprocess.run([tool, "-u", str(target)], check=False)
                except OSError:
                    pass

    for extra in extras:
        if _remove_path(extra):
            removed.append(str(extra))

    if purge_user_data:
        for data_path in user_data_paths(platform):
            if _remove_path(data_path):
                removed.append(str(data_path))
        if platform == "windows":
            # QSettings su Windows scrive nel registro, non in una cartella.
            key = r"HKCU\Software\BlindCue"
            try:
                result = subprocess.run(
                    ["reg", "delete", key, "/f"],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except OSError:
                result = None
            if result is not None and result.returncode == 0:
                removed.append("HKEY_CURRENT_USER\\Software\\BlindCue")

    if platform == "linux":
        # Cache dei menu/icone: senza questo la voce rimossa può restare
        # visibile nel launcher fino al prossimo aggiornamento automatico.
        data_root = Path(os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share"))
        apps = data_root / "applications"
        for command in (
            ["update-desktop-database", str(apps)],
            ["gtk-update-icon-cache", "-f", "-t", str(data_root / "icons" / "hicolor")],
            ["kbuildsycoca6", "--noincremental"],
            ["kbuildsycoca5", "--noincremental"],
        ):
            if shutil.which(command[0]):
                try:
                    subprocess.run(
                        command, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                    )
                except OSError:
                    pass

    return removed


def launch(platform: str | None = None) -> None:
    """Start the installed application without blocking the installer window."""
    platform = platform or current_platform()
    script = run_script(platform)
    if not script.is_file():
        raise FileNotFoundError(str(script))

    if platform == "macos":
        # `open` fa partire il bundle come farebbe il Finder, con l'icona nel Dock.
        subprocess.Popen(["open", "-a", str(install_dir(platform))], close_fds=True)
        return

    if platform == "windows":
        subprocess.Popen(["cmd", "/c", ".\\" + script.name], cwd=str(script.parent))
        return

    subprocess.Popen(["/bin/bash", str(script)], cwd=str(REPO_ROOT), close_fds=True)
