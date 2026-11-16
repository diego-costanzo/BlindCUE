#!/usr/bin/env python3
"""BlindCue — installer universale.

Un solo file per Linux, macOS e Windows: riconosce il sistema, apre la finestra
grafica di installazione e delega il lavoro vero allo script della piattaforma
corretta (``setup/linux``, ``setup/macos``, ``setup/windows``).

Uso:
    python3 setup.py                finestra grafica (consigliato)
    python3 setup.py --terminal     installazione testuale nel terminale
    python3 setup.py --check        solo diagnostica, non installa nulla
    python3 setup.py --yes          installazione senza domande
    python3 setup.py --run          avvia BlindCue se è già installato
    python3 setup.py --uninstall    rimuove l'installazione dell'utente
                                    (aggiungi --purge per cancellare anche
                                    impostazioni e autosave; i progetti no)

Solo libreria standard: questo file deve funzionare anche su un sistema dove
BlindCue (e quindi PySide6) non è ancora installato.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
COMMON_DIR = REPO_ROOT / "setup" / "common"

if str(COMMON_DIR) not in sys.path:
    sys.path.insert(0, str(COMMON_DIR))

import installer_core  # importato dopo aver aggiunto setup/common al path

GREEN = "\033[1;32m"
CYAN = "\033[1;36m"
YELLOW = "\033[1;33m"
RED = "\033[1;31m"
RESET = "\033[0m"


def usage() -> None:
    print(__doc__)


def run_engine(extra_args: list[str]) -> int:
    """Esegue lo script di installazione della piattaforma, in primo piano."""
    script = installer_core.engine_script()
    if not script.is_file():
        print(f"{RED}[FAIL]{RESET} Script di installazione non trovato: {script}")
        return 1

    # flush=True: quando l'output è una pipe (GUI o `| tail`) Python resta
    # bufferizzato e le righe comparirebbero dopo quelle dello script figlio.
    print(f"{CYAN}[INFO]{RESET} Sistema: {installer_core.platform_label()}", flush=True)
    print(f"{CYAN}[INFO]{RESET} Destinazione: {installer_core.install_dir()}", flush=True)
    print(flush=True)
    try:
        # cwd = cartella dello script: su Windows il comando usa il nome nudo
        # del file per non farsi rompere il quoting dagli spazi nel percorso.
        completed = subprocess.run(
            installer_core.engine_command(extra_args), cwd=str(script.parent), check=False
        )
    except OSError as exc:
        print(f"{RED}[FAIL]{RESET} Impossibile avviare l'installer: {exc}")
        return 1
    return completed.returncode


def _privileged(command: list[str]) -> int:
    """Esegue un comando come amministratore, con o senza terminale."""
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        return subprocess.run(command, check=False).returncode
    if sys.stdin.isatty():
        sudo = shutil.which("sudo")
        if sudo:
            return subprocess.run([sudo, *command], check=False).returncode
    pkexec = shutil.which("pkexec")
    if pkexec:
        return subprocess.run([pkexec, *command], check=False).returncode
    return 1


def _tk_packages() -> list[str] | None:
    """Comando per installare tkinter sul sistema corrente, se conosciuto."""
    platform = installer_core.current_platform()
    if platform == "macos":
        if not shutil.which("brew"):
            return None
        return ["brew", "install", "python-tk"]
    if platform != "linux":
        return None

    try:
        release = Path("/etc/os-release").read_text(encoding="utf-8", errors="replace").lower()
    except OSError:
        return None

    if "arch" in release:
        return ["pacman", "-S", "--needed", "--noconfirm", "tk"]
    if "fedora" in release or "rhel" in release:
        return ["dnf", "install", "-y", "python3-tkinter"]
    if "debian" in release or "ubuntu" in release:
        return ["apt-get", "install", "-y", "python3-tk"]
    return None


def ensure_tkinter() -> bool:
    """Apre la GUI anche se tkinter non è ancora installato.

    Su Linux tkinter vive in un pacchetto separato (python3-tk): senza di lui
    la finestra non può partire. Installarlo richiede i permessi di
    amministratore una volta sola, con la finestra di password di sistema
    (pkexec) quando non c'è un terminale.
    """
    try:
        import tkinter as _tk  # probe: verifica solo che sia importabile
        del _tk
        return True
    except ImportError:
        # Anche una libtk mancante arriva qui come ImportError.
        pass

    if os.environ.get("BLINDCUE_TK_BOOTSTRAP") == "1":
        return False

    command = _tk_packages()
    if not command:
        return False

    print(
        f"{CYAN}[INFO]{RESET} Il supporto grafico (tkinter) non è presente: lo installo ...",
        flush=True,
    )
    if _privileged(command) != 0:
        print(f"{YELLOW}[WARN]{RESET} Installazione di tkinter non riuscita.")
        return False

    # Riavvio pulito: le librerie appena installate devono essere caricate
    # da un interprete nuovo, non da quello che ha già provato una volta.
    os.environ["BLINDCUE_TK_BOOTSTRAP"] = "1"
    os.execv(sys.executable, [sys.executable, str(Path(__file__).resolve()), *sys.argv[1:]])


def run_gui(argv: list[str]) -> int:
    """Apre la finestra grafica; 2 significa "usa il terminale"."""
    try:
        import installer_ui
    except ImportError as exc:
        print(f"{YELLOW}[WARN]{RESET} tkinter non disponibile ({exc}).")
        return 2
    return installer_ui.main(argv)


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])

    if any(a in ("-h", "--help") for a in args):
        usage()
        return 0

    if "--run" in args:
        if not installer_core.is_installed():
            print(f"{YELLOW}[WARN]{RESET} BlindCue non risulta installato.")
            print(f"       Esegui:  python3 {Path(__file__).name}")
            return 1
        installer_core.launch()
        return 0

    if "--uninstall" in args:
        removed = installer_core.uninstall()
        if not removed:
            print(f"{CYAN}[INFO]{RESET} Nessuna installazione da rimuovere.")
            return 0
        for path in removed:
            print(f"{GREEN}[ OK ]{RESET} rimosso {path}")
        return 0

    passthrough = [a for a in args if a in ("--check", "--yes", "-y", "--no-sudo", "--no-gpu")]
    if "--prefix" in args:
        index = args.index("--prefix")
        if index + 1 < len(args):
            passthrough += ["--prefix", args[index + 1]]

    if "--terminal" in args or "--yes" in args or "--check" in args:
        return run_engine(passthrough)

    ensure_tkinter()
    code = run_gui([a for a in args if a.startswith("--")])
    if code == 2:
        print(f"{YELLOW}[WARN]{RESET} Installazione in modalità testuale.\n")
        return run_engine(passthrough)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
