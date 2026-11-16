"""BlindCue installer window (tkinter, no third-party dependencies).

The window exists because BlindCue cannot install PySide6 with PySide6: this
module only uses the Python standard library, so it always starts — even on a
machine where BlindCue has never been installed.

The heavy lifting stays in the per-OS scripts (``setup/<os>/install.*``); this
window explains what will happen, streams their output and reports the result.
"""

from __future__ import annotations

import queue
import re
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import font as tkfont
from tkinter import messagebox
from tkinter import ttk

import installer_core

# Palette identical to the "Obsidian Slate" BlindCue theme.
BG = "#0c1017"
PANEL = "#151b26"
ELEVATED = "#1e2838"
TEXT = "#e2e8f0"
MUTED = "#94a3b8"
ACCENT = "#38bdf8"
ACCENT_DEEP = "#0284c7"
BORDER = "#232f40"
OK_COLOR = "#10b981"
ERR_COLOR = "#ef4444"
WARN_COLOR = "#f59e0b"

ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
STEP_RE = re.compile(r"^\[STEP\]\s+(\d+)/(\d+)\s*(.*)$")


def _pick_font(candidates: tuple[str, ...], fallback: str) -> str:
    try:
        available = {name.lower() for name in tkfont.families()}
    except tk.TclError:
        return fallback
    for name in candidates:
        if name.lower() in available:
            return name
    return fallback


class InstallerWindow:
    """Single window: explanation → progress → result."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.platform = installer_core.current_platform()
        self.target = installer_core.install_dir(self.platform)
        self.engine = installer_core.engine_script(self.platform)
        self.messages: queue.Queue[tuple[str, str]] = queue.Queue()
        self.process: subprocess.Popen | None = None
        self.running = False
        self.total_steps = 0

        self.ui_font = _pick_font(("Inter", "Segoe UI", "Ubuntu", "DejaVu Sans"), "TkDefaultFont")
        self.mono_font = _pick_font(("JetBrains Mono", "Cascadia Mono", "DejaVu Sans Mono"), "TkFixedFont")

        root.title("BlindCue — Installazione")
        root.configure(bg=BG)
        root.minsize(680, 620)
        root.geometry("720x680")
        root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_header()
        self._build_body()
        self._build_progress()
        self._build_log()
        self._build_buttons()

    # ── costruzione dell'interfaccia ─────────────────────────────────────────
    def _build_header(self) -> None:
        header = tk.Frame(self.root, bg=PANEL, highlightthickness=0)
        header.pack(fill="x")

        logo_path = installer_core.icon_path(self.platform)
        self._logo = None
        if logo_path.is_file():
            try:
                image = tk.PhotoImage(file=str(logo_path))
                factor = max(1, image.width() // 84)
                self._logo = image.subsample(factor, factor)
                tk.Label(header, image=self._logo, bg=PANEL).pack(side="left", padx=(20, 14), pady=16)
            except tk.TclError:
                self._logo = None

        titles = tk.Frame(header, bg=PANEL)
        titles.pack(side="left", pady=16)
        tk.Label(
            titles, text="BlindCue", bg=PANEL, fg=TEXT,
            font=(self.ui_font, 20, "bold"),
        ).pack(anchor="w")
        tk.Label(
            titles,
            text="Player di cue audio/video per spettacoli dal vivo",
            bg=PANEL, fg=MUTED, font=(self.ui_font, 10),
        ).pack(anchor="w")

        tk.Label(
            header,
            text=f"{installer_core.platform_label(self.platform)}  ·  installazione per l'utente corrente",
            bg=PANEL, fg=ACCENT, font=(self.ui_font, 9),
        ).pack(side="right", padx=20)

        tk.Frame(self.root, bg=BORDER, height=1).pack(fill="x")

    def _build_body(self) -> None:
        body = tk.Frame(self.root, bg=BG, padx=22, pady=16)
        body.pack(fill="both", expand=True)

        self.intro = tk.Label(
            body,
            text=self._intro_text(),
            bg=BG, fg=TEXT, justify="left", anchor="w",
            font=(self.ui_font, 10), wraplength=660,
        )
        self.intro.pack(fill="x", anchor="w")

        tk.Label(
            body, text=f"Destinazione:  {self.target}",
            bg=BG, fg=MUTED, font=(self.mono_font, 9), anchor="w",
        ).pack(fill="x", pady=(10, 0))

        steps = tk.Frame(body, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
        steps.pack(fill="x", pady=(14, 0), ipady=6)
        for line in self._steps_text().splitlines():
            tk.Label(
                steps, text=line, bg=PANEL, fg=TEXT if not line.startswith(" ") else MUTED,
                font=(self.ui_font, 9), anchor="w", justify="left",
            ).pack(fill="x", padx=14, pady=1)

    def _build_progress(self) -> None:
        frame = tk.Frame(self.root, bg=BG, padx=22)
        frame.pack(fill="x")

        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(
            "BlindCue.Horizontal.TProgressbar",
            troughcolor=PANEL, bordercolor=BORDER, background=ACCENT,
            lightcolor=ACCENT, darkcolor=ACCENT, thickness=8,
        )

        self.progress = ttk.Progressbar(
            frame, style="BlindCue.Horizontal.TProgressbar",
            mode="determinate", maximum=6, value=0,
        )
        self.progress.pack(fill="x", pady=(14, 4))

        self.status = tk.Label(
            frame, text="Pronto per l'installazione.", bg=BG, fg=MUTED,
            font=(self.ui_font, 9), anchor="w",
        )
        self.status.pack(fill="x")

    def _build_log(self) -> None:
        container = tk.Frame(self.root, bg=BG, padx=22, pady=(10, 0))
        container.pack(fill="both", expand=True)

        self.log = tk.Text(
            container, height=10, bg="#080d14", fg=TEXT, insertbackground=TEXT,
            relief="flat", highlightthickness=1, highlightbackground=BORDER,
            font=(self.mono_font, 9), wrap="word", padx=10, pady=8,
        )
        scroll = ttk.Scrollbar(container, orient="vertical", command=self.log.yview)
        self.log.configure(yscrollcommand=scroll.set)
        self.log.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.log.configure(state="disabled")
        self.log.tag_configure("ok", foreground=OK_COLOR)
        self.log.tag_configure("err", foreground=ERR_COLOR)
        self.log.tag_configure("warn", foreground=WARN_COLOR)
        self.log.tag_configure("step", foreground=ACCENT)

    def _build_buttons(self) -> None:
        bar = tk.Frame(self.root, bg=BG, padx=22, pady=16)
        bar.pack(fill="x", side="bottom")

        self.btn_install = tk.Button(
            bar, text="Installa BlindCue" if not installer_core.is_installed(self.platform) else "Aggiorna BlindCue",
            command=self.start_install, bg=ACCENT, fg=BG, activebackground=ACCENT,
            activeforeground=BG, relief="flat", bd=0, padx=22, pady=9,
            font=(self.ui_font, 10, "bold"), cursor="hand2",
        )
        self.btn_install.pack(side="right")

        self.btn_later = tk.Button(
            bar, text="Chiudi", command=self._on_close, bg=ELEVATED, fg=TEXT,
            activebackground=BORDER, activeforeground=TEXT, relief="flat", bd=0,
            padx=18, pady=9, font=(self.ui_font, 10), cursor="hand2",
        )
        self.btn_later.pack(side="right", padx=(0, 10))

        self.btn_check = tk.Button(
            bar, text="Verifica requisiti", command=self.start_check, bg=BG, fg=MUTED,
            activebackground=BG, activeforeground=ACCENT, relief="flat", bd=0,
            padx=10, pady=9, font=(self.ui_font, 9), cursor="hand2",
        )
        self.btn_check.pack(side="left")

        self.btn_remove = tk.Button(
            bar, text="Rimuovi", command=self.remove, bg=BG, fg=ERR_COLOR,
            activebackground=BG, activeforeground=ERR_COLOR, relief="flat", bd=0,
            padx=10, pady=9, font=(self.ui_font, 9), cursor="hand2",
        )
        if installer_core.is_installed(self.platform):
            self.btn_remove.pack(side="left", padx=(8, 0))

    # ── testi ────────────────────────────────────────────────────────────────
    def _intro_text(self) -> str:
        if installer_core.is_installed(self.platform):
            return (
                "BlindCue risulta già installato. Puoi aggiornarlo riutilizzando "
                "l'ambiente Python esistente, oppure rimuoverlo senza lasciare tracce."
            )
        return (
            "L'installazione crea una copia privata di BlindCue per il tuo utente, "
            "installa solo i componenti mancanti e aggiunge un collegamento con "
            "l'icona del programma. Non richiede permessi di amministratore "
            "e non tocca i tuoi progetti."
        )

    def _steps_text(self) -> str:
        return (
            "Cosa verrà fatto\n"
            "  1. Controllo di Python, memoria, disco e connessione\n"
            "  2. Verifica di FFmpeg e delle librerie grafiche (solo se mancano)\n"
            "  3. Copia del programma nella cartella dell'utente\n"
            "  4. Ambiente Python isolato con le dipendenze\n"
            "  5. Test automatici di moduli, audio, schermi e avvio\n"
            "  6. Collegamento di avvio con l'icona di BlindCue"
        )

    # ── azioni ───────────────────────────────────────────────────────────────
    def start_install(self) -> None:
        extra = ["/yes"] if self.platform == "windows" else ["--yes"]
        self._run(extra, "Installazione in corso — non chiudere la finestra.")

    def start_check(self) -> None:
        extra = ["/check"] if self.platform == "windows" else ["--check"]
        self._run(extra, "Verifica dei requisiti in corso.")

    def remove(self) -> None:
        if self.running:
            return
        if not messagebox.askyesno(
            "BlindCue",
            "Rimuovere BlindCue da questo computer?\n\n"
            "Verranno eliminati il programma, i collegamenti di avvio e l'icona "
            "nel menu di sistema. I tuoi progetti non vengono toccati.",
            icon="warning",
            parent=self.root,
        ):
            return
        # L'autosave può contenere un progetto non salvato: default = conservalo.
        purge = messagebox.askyesno(
            "BlindCue",
            "Rimuovere anche impostazioni e autosave?\n\n"
            "No = l'autosave resta disponibile se reinstalli BlindCue.",
            icon="question",
            default="no",
            parent=self.root,
        )

        try:
            removed = installer_core.uninstall(self.platform, purge_user_data=purge)
        except OSError as exc:
            self._append(f"[FAIL] Rimozione non riuscita: {exc}\n", "err")
            return
        self._append("[ OK ] Rimozione completata.\n", "ok")
        for path in removed:
            self._append(f"        rimosso {path}\n")
        self._append("\n" + installer_core.FAREWELL + "\n", "ok")
        self.btn_remove.pack_forget()
        self.btn_install.configure(text="Installa BlindCue")
        self.status.configure(text="BlindCue non è più installato.", fg=MUTED)

    def _run(self, extra_args: list[str], status: str) -> None:
        if self.running:
            return
        if not self.engine.is_file():
            self._append(f"[FAIL] Script di installazione non trovato: {self.engine}\n", "err")
            return

        self.running = True
        self.progress.configure(value=0)
        self.status.configure(text=status, fg=ACCENT)
        self._clear_log()
        self.btn_install.configure(state="disabled", bg=BORDER)
        self.btn_check.configure(state="disabled")
        self.btn_later.configure(state="disabled")
        self.btn_remove.pack_forget()

        command = installer_core.engine_command(extra_args)
        threading.Thread(target=self._reader, args=(command,), daemon=True).start()
        self.root.after(90, self._poll)

    def _reader(self, command: list[str]) -> None:
        try:
            self.process = subprocess.Popen(
                command,
                # cwd = cartella dello script (vedi installer_core.engine_command)
                cwd=str(self.engine.parent),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
        except OSError as exc:
            self.messages.put(("line", f"[FAIL] Impossibile avviare l'installer: {exc}\n"))
            self.messages.put(("done", "1"))
            return

        assert self.process.stdout is not None
        for raw in self.process.stdout:
            self.messages.put(("line", raw))
        code = self.process.wait()
        self.messages.put(("done", str(code)))

    def _poll(self) -> None:
        finished = False
        try:
            while True:
                kind, payload = self.messages.get_nowait()
                if kind == "line":
                    self._append(payload)
                else:
                    finished = True
                    self._finish(int(payload))
        except queue.Empty:
            pass
        if not finished and self.running:
            self.root.after(90, self._poll)

    def _finish(self, exit_code: int) -> None:
        self.running = False
        self.btn_check.configure(state="normal")
        self.btn_later.configure(state="normal", text="Chiudi")

        if exit_code == 0:
            self.progress.configure(value=self.progress.cget("maximum"))
            self.status.configure(text="Installazione completata.", fg=OK_COLOR)
            self._append("\n[ OK ] Fatto. BlindCue è pronto.\n", "ok")
            self.btn_install.configure(
                text="Avvia BlindCue", state="normal", bg=OK_COLOR,
                command=self.launch_now,
            )
            if installer_core.is_installed(self.platform):
                self.btn_remove.pack(side="left", padx=(8, 0))
        elif exit_code == 130:
            self.status.configure(text="Installazione annullata.", fg=WARN_COLOR)
            self._reset_install_button()
        else:
            self.status.configure(
                text="Installazione non riuscita: leggi il messaggio sopra.", fg=ERR_COLOR
            )
            self._append("\n[FAIL] Installazione non completata.\n", "err")
            self._reset_install_button()

    def _reset_install_button(self) -> None:
        self.btn_install.configure(
            text="Riprova", state="normal", bg=ACCENT, command=self.start_install
        )

    def launch_now(self) -> None:
        try:
            installer_core.launch(self.platform)
        except OSError as exc:
            self._append(f"[FAIL] Avvio non riuscito: {exc}\n", "err")
            return
        self.root.after(600, self.root.destroy)

    # ── log ──────────────────────────────────────────────────────────────────
    def _clear_log(self) -> None:
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def _append(self, text: str, tag: str | None = None) -> None:
        clean = ANSI_RE.sub("", text)
        match = STEP_RE.match(clean.strip())
        if match:
            current, total, label = match.groups()
            total_value = max(1, int(total))
            self.progress.configure(maximum=total_value, value=int(current))
            self.status.configure(text=label or f"Passo {current} di {total}", fg=ACCENT)

        if tag is None:
            stripped = clean.lstrip()
            if stripped.startswith("[ OK ]"):
                tag = "ok"
            elif stripped.startswith("[FAIL]"):
                tag = "err"
            elif stripped.startswith("[WARN]"):
                tag = "warn"
            elif stripped.startswith("[STEP]"):
                tag = "step"

        self.log.configure(state="normal")
        self.log.insert("end", clean, tag or ())
        self.log.see("end")
        self.log.configure(state="disabled")

    def _on_close(self) -> None:
        if self.running:
            self.status.configure(
                text="Installazione in corso: attendi la fine prima di chiudere.", fg=WARN_COLOR
            )
            return
        if self.process is not None and self.process.poll() is None:
            try:
                self.process.terminate()
            except OSError:
                pass
        self.root.destroy()


def main(argv: list[str] | None = None) -> int:
    """Show the installer window. Returns a shell-style exit code."""
    argv = list(argv if argv is not None else sys.argv[1:])
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        print(f"[WARN] Interfaccia grafica non disponibile: {exc}", file=sys.stderr)
        return 2

    window = InstallerWindow(root)
    if "--auto-start" in argv:
        root.after(300, window.start_install)
    root.mainloop()
    return 0
