#!/usr/bin/env python3
"""BlindCue — disinstallazione.

Rimuove l'installazione dell'utente e i collegamenti di avvio; con
``--purge`` elimina anche impostazioni e autosave. I progetti ``.blindcue``
non vengono **mai** toccati: restano dove li hai salvati.

Uso:
    python3 uninstall.py              finestra grafica con conferma
    python3 uninstall.py --terminal   solo terminale
    python3 uninstall.py --yes        nessuna domanda (per script)
    python3 uninstall.py --purge      rimuove anche impostazioni e autosave

Solo libreria standard: deve funzionare anche su un sistema dove BlindCue
non è (più) installato.
"""

from __future__ import annotations

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
RESET = "\033[0m"

THANKS = installer_core.FAREWELL


def _ask(prompt: str) -> bool:
    """Domanda sì/no da terminale, con default no."""
    try:
        answer = input(f"{prompt} [s/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    return answer in ("s", "si", "sì", "y", "yes")


def _report(removed: list[str]) -> None:
    if not removed:
        print(f"{CYAN}[INFO]{RESET} Nulla da rimuovere: era già tutto pulito.")
        return
    for path in removed:
        print(f"{GREEN}[ OK ]{RESET} rimosso {path}")


def terminal_uninstall(assume_yes: bool, purge: bool) -> int:
    target = installer_core.install_dir()
    print(f"{CYAN}[INFO]{RESET} Sistema: {installer_core.platform_label()}")
    print(f"{CYAN}[INFO]{RESET} BlindCue verrà rimosso da: {target}")
    print("       I tuoi progetti (.blindcue) non vengono toccati.")
    print()

    if not assume_yes:
        if not purge and _ask("Rimuovere anche impostazioni e autosave?"):
            purge = True
        if not _ask("Procedere con la disinstallazione?"):
            print(f"{YELLOW}[WARN]{RESET} Operazione annullata.")
            return 130

    removed = installer_core.uninstall(purge_user_data=purge)
    _report(removed)
    print()
    print(THANKS)
    return 0


class _Window:
    """Minimal tkinter window: confirm → result, in the BlindCue palette."""

    def __init__(self, root, purge: bool) -> None:
        import tkinter as tk

        self.tk = tk
        self.root = root
        self.purge = tk.BooleanVar(value=purge)

        # Palette del tema Obsidian Slate, condivisa con l'installer.
        from installer_ui import (  # import qui: tkinter è già disponibile
            ACCENT, BG, BORDER, ELEVATED, ERR_COLOR, MUTED, OK_COLOR, PANEL, TEXT,
        )

        self.palette = dict(
            ACCENT=ACCENT, BG=BG, BORDER=BORDER, ELEVATED=ELEVATED,
            ERR=ERR_COLOR, MUTED=MUTED, OK=OK_COLOR, PANEL=PANEL, TEXT=TEXT,
        )

        root.title("BlindCue — Disinstallazione")
        root.configure(bg=BG)
        root.minsize(620, 470)
        root.geometry("660x500")

        header = tk.Frame(root, bg=PANEL)
        header.pack(fill="x")

        logo = installer_core.icon_path()
        self._logo = None
        if logo.is_file():
            try:
                image = tk.PhotoImage(file=str(logo))
                factor = max(1, image.width() // 72)
                self._logo = image.subsample(factor, factor)
                tk.Label(header, image=self._logo, bg=PANEL).pack(
                    side="left", padx=(20, 12), pady=14
                )
            except tk.TclError:
                self._logo = None

        tk.Label(
            header, text="Rimuovere BlindCue?", bg=PANEL, fg=TEXT,
            font=("TkDefaultFont", 16, "bold"),
        ).pack(side="left", pady=14)

        body = tk.Frame(root, bg=BG, padx=22, pady=16)
        body.pack(fill="both", expand=True)

        tk.Label(
            body,
            text=(
                "Verrà eliminata l'installazione privata di BlindCue insieme al "
                "collegamento di avvio e all'icona nel menu di sistema.\n"
                "Nessun progetto viene toccato: i file .blindcue restano dove sono."
            ),
            bg=BG, fg=TEXT, justify="left", anchor="w", wraplength=600,
        ).pack(fill="x", anchor="w")

        tk.Label(
            body, text=f"Cartella:  {installer_core.install_dir()}",
            bg=BG, fg=MUTED, anchor="w", font=("TkFixedFont", 9),
        ).pack(fill="x", pady=(10, 0))

        tk.Checkbutton(
            body,
            text="Rimuovi anche impostazioni e autosave (consigliato se non tornerai a usarlo)",
            variable=self.purge, bg=BG, fg=MUTED, activebackground=BG,
            activeforeground=TEXT, selectcolor=PANEL, relief="flat",
            highlightthickness=0, anchor="w", font=("TkDefaultFont", 9),
        ).pack(fill="x", pady=(14, 0))

        bar = tk.Frame(root, bg=BG, padx=22, pady=16)
        bar.pack(fill="x", side="bottom")
        self.bar = bar

        self.btn_go = tk.Button(
            bar, text="Disinstalla BlindCue", command=self.run,
            bg=ERR_COLOR, fg=BG, activebackground=ERR_COLOR, activeforeground=BG,
            relief="flat", bd=0, padx=20, pady=9,
            font=("TkDefaultFont", 10, "bold"), cursor="hand2",
        )
        self.btn_go.pack(side="right")

        tk.Button(
            bar, text="Annulla", command=root.destroy,
            bg=ELEVATED, fg=TEXT, activebackground=BORDER, activeforeground=TEXT,
            relief="flat", bd=0, padx=18, pady=9,
            font=("TkDefaultFont", 10), cursor="hand2",
        ).pack(side="right", padx=(0, 10))

        self.body = body

    def run(self) -> None:
        p = self.palette
        self.btn_go.configure(state="disabled", bg=p["BORDER"], text="Rimozione in corso ...")
        self.root.update_idletasks()

        try:
            removed = installer_core.uninstall(purge_user_data=bool(self.purge.get()))
        except OSError as exc:
            self._show_result([], error=str(exc))
            return
        self._show_result(removed)

    def _show_result(self, removed: list[str], error: str | None = None) -> None:
        tk = self.tk
        p = self.palette
        for child in self.body.winfo_children():
            child.destroy()

        title = "Rimozione non completata" if error else "BlindCue è stato rimosso"
        color = p["ERR"] if error else p["OK"]

        tk.Label(
            self.body, text=title, bg=p["BG"], fg=color, anchor="w",
            font=("TkDefaultFont", 14, "bold"),
        ).pack(fill="x", anchor="w")

        tk.Label(
            self.body,
            text=error or THANKS,
            bg=p["BG"], fg=p["TEXT"], justify="left", anchor="w", wraplength=600,
        ).pack(fill="x", anchor="w", pady=(10, 0))

        if removed:
            tk.Label(
                self.body, text="Rimosso:", bg=p["BG"], fg=p["MUTED"], anchor="w",
                font=("TkDefaultFont", 9),
            ).pack(fill="x", pady=(14, 2))
            tk.Label(
                self.body, text="\n".join(removed), bg=p["BG"], fg=p["MUTED"],
                anchor="w", justify="left", font=("TkFixedFont", 8),
            ).pack(fill="x", anchor="w")

        for child in self.bar.winfo_children():
            child.destroy()
        tk.Button(
            self.bar, text="Chiudi", command=self.root.destroy,
            bg=p["ACCENT"], fg=p["BG"], activebackground=p["ACCENT"],
            activeforeground=p["BG"], relief="flat", bd=0, padx=22, pady=9,
            font=("TkDefaultFont", 10, "bold"), cursor="hand2",
        ).pack(side="right")


def run_gui(purge: bool) -> int | None:
    """Return None when tkinter is unavailable, so the caller falls back."""
    try:
        import tkinter as tk
    except ImportError:
        return None

    try:
        root = tk.Tk()
    except tk.TclError:
        return None

    try:
        _Window(root, purge)
    except ImportError:
        root.destroy()
        return None
    root.mainloop()
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])

    if any(a in ("-h", "--help") for a in args):
        print(__doc__)
        return 0

    purge = "--purge" in args
    assume_yes = any(a in ("--yes", "-y") for a in args)

    if "--terminal" in args or assume_yes or not sys.stdin.isatty():
        return terminal_uninstall(assume_yes, purge)

    code = run_gui(purge)
    if code is None:
        print(f"{YELLOW}[WARN]{RESET} Interfaccia grafica non disponibile: uso il terminale.")
        return terminal_uninstall(False, purge)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
