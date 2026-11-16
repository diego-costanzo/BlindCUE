#!/usr/bin/env bash
# ==============================================================================
# BlindCue — Installer per macOS (Apple Silicon e Intel)
#
# Installa un bundle applicativo in:  ~/Applications/BlindCue.app
# (visibile nel Launchpad e nel Finder, con l'icona del programma).
#
# Uso:
#   ./setup/macos/install.command            installazione interattiva
#   ./setup/macos/install.command --yes      senza domande (per la GUI)
#   ./setup/macos/install.command --check    solo controlli
#   ./setup/macos/install.command --prefix DIR
#   ./setup/macos/install.command --uninstall
#
# Su macOS la decodifica video usa VideoToolbox: nessun driver aggiuntivo.
# ==============================================================================

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

if [ -n "${BLINDCUE_PREFIX:-}" ]; then
    APP_BUNDLE="${BLINDCUE_PREFIX}"
else
    APP_BUNDLE="${HOME}/Applications/BlindCue.app"
fi
CONTENTS="${APP_BUNDLE}/Contents"
MACOS_DIR="${CONTENTS}/MacOS"
RES_DIR="${CONTENTS}/Resources"
APP_DIR="${RES_DIR}/app"
VENV_DIR="${RES_DIR}/venv"
VENV_PY="${VENV_DIR}/bin/python"
REQ_FILE="${APP_DIR}/requirements.txt"
ICON_SRC="${REPO_ROOT}/setup/assets/blindcue.icns"

ASSUME_YES=false
CHECK_ONLY=false
UNINSTALL=false
TOTAL_STEPS=6
FAILED=0

# Homebrew non è sempre nel PATH delle shell non interattive
for brew_bin in /opt/homebrew/bin /usr/local/bin; do
    if [ -d "$brew_bin" ]; then
        export PATH="$brew_bin:$PATH"
    fi
done

CLR_RESET="\033[0m"
CLR_BOLD="\033[1m"
CLR_GREEN="\033[1;32m"
CLR_CYAN="\033[1;36m"
CLR_YELLOW="\033[1;33m"
CLR_RED="\033[1;31m"

log_info()    { echo -e "${CLR_CYAN}[INFO]${CLR_RESET} $1"; }
log_success() { echo -e "${CLR_GREEN}[ OK ]${CLR_RESET} $1"; }
log_warn()    { echo -e "${CLR_YELLOW}[WARN]${CLR_RESET} $1"; }
log_error()   { echo -e "${CLR_RED}[FAIL]${CLR_RESET} $1"; FAILED=1; }
log_step()    { echo -e "${CLR_CYAN}[STEP]${CLR_RESET} $1/${TOTAL_STEPS} $2"; }

while [ $# -gt 0 ]; do
    case "$1" in
        -y|--yes)     ASSUME_YES=true ;;
        --check)      CHECK_ONLY=true ;;
        --uninstall)  UNINSTALL=true ;;
        --prefix)     shift; APP_BUNDLE="${1:?--prefix richiede un percorso}"
                      CONTENTS="${APP_BUNDLE}/Contents"
                      MACOS_DIR="${CONTENTS}/MacOS"
                      RES_DIR="${CONTENTS}/Resources"
                      APP_DIR="${RES_DIR}/app"
                      VENV_DIR="${RES_DIR}/venv"
                      VENV_PY="${VENV_DIR}/bin/python"
                      REQ_FILE="${APP_DIR}/requirements.txt" ;;
        -h|--help)
            echo "Uso: ./setup/macos/install.command [--yes] [--check] [--prefix DIR] [--uninstall]"
            exit 0 ;;
        *) log_warn "Opzione ignorata: $1" ;;
    esac
    shift
done

ask_yes_no() {
    local prompt="$1"
    if [ "$ASSUME_YES" = true ]; then
        return 0
    fi
    if [ -t 0 ]; then
        local ans=""
        read -r -p "${prompt} [S/n] " ans || ans=""
        ans="${ans:-yes}"
        [[ "$ans" =~ ^([yYsS]|[yY][eE][sS]|[sS][iI])$ ]]
        return
    fi
    if command -v osascript &>/dev/null; then
        osascript -e "display dialog \"${prompt}\" buttons {\"Annulla\", \"Continua\"} default button \"Continua\" with title \"BlindCue\"" >/dev/null 2>&1
        return
    fi
    return 0
}

if [ "$UNINSTALL" = true ]; then
    if [ -d "$APP_BUNDLE" ]; then
        rm -rf "$APP_BUNDLE"
        log_success "Rimosso ${APP_BUNDLE}"
    else
        log_info "Nessuna installazione trovata in ${APP_BUNDLE}"
    fi
    exit 0
fi

echo -e "${CLR_CYAN}${CLR_BOLD}"
echo "======================================================================"
echo "        BlindCue — Installazione (macOS)"
echo "        bundle applicativo in ~/Applications, nessun permesso admin"
echo "======================================================================"
echo -e "${CLR_RESET}"

# ------------------------------------------------------------------------------
# 1. Controlli preliminari
# ------------------------------------------------------------------------------
log_step 1 "Controlli preliminari"

ARCH="$(uname -m)"
if [ "$ARCH" = "arm64" ]; then
    log_success "Apple Silicon (arm64) — VideoToolbox disponibile"
else
    log_success "Intel (${ARCH}) — VideoToolbox disponibile"
fi

if ! command -v python3 &>/dev/null; then
    log_error "Python 3 non trovato."
    log_info "Installa con: brew install python   (oppure https://www.python.org/downloads/)"
    exit 1
fi

PY_VER="$(python3 -c 'import sys; print("%d.%d.%d" % sys.version_info[:3])' 2>/dev/null || echo "0.0.0")"
if python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
    log_success "Python ${PY_VER}"
else
    log_warn "Python ${PY_VER}: consigliato 3.11 o superiore per i wheel PySide6."
    if command -v brew &>/dev/null && [ "$CHECK_ONLY" = false ]; then
        if ask_yes_no "Installare un Python aggiornato tramite Homebrew?"; then
            brew install python
            hash -r
        fi
    fi
fi

TOTAL_BYTES="$(sysctl -n hw.memsize 2>/dev/null || echo 0)"
TOTAL_MB=$(( TOTAL_BYTES / 1024 / 1024 ))
if [ "$TOTAL_MB" -gt 0 ]; then
    log_info "RAM totale: ${TOTAL_MB} MB"
    if [ "$TOTAL_MB" -lt 2048 ]; then
        log_warn "RAM limitata: BlindCue selezionera' automaticamente il profilo ECO."
    fi
fi

FREE_KB="$(df -Pk "$HOME" 2>/dev/null | awk 'NR==2 {print $4}')"
FREE_KB="${FREE_KB:-0}"
[[ "$FREE_KB" =~ ^[0-9]+$ ]] || FREE_KB=0
FREE_MB=$(( FREE_KB / 1024 ))
log_info "Spazio disco disponibile: ${FREE_MB} MB"
if [ "$FREE_MB" -lt 1500 ]; then
    log_error "Servono almeno 1.5 GB liberi (PySide6 e' voluminoso)."
fi

# ------------------------------------------------------------------------------
# 2. FFmpeg
# ------------------------------------------------------------------------------
log_step 2 "Componenti di sistema"
log_info "Verifica FFmpeg / FFprobe ..."
if ! command -v ffmpeg &>/dev/null || ! command -v ffprobe &>/dev/null; then
    log_warn "FFmpeg non trovato: forma d'onda, loudness e normalizzazione sarebbero disabilitate."
    if [ "$CHECK_ONLY" = false ]; then
        if command -v brew &>/dev/null; then
            if ask_yes_no "Installare FFmpeg tramite Homebrew?"; then
                brew install ffmpeg || log_error "Installazione FFmpeg non riuscita."
            fi
        else
            log_error "Homebrew non trovato. Installa FFmpeg da https://ffmpeg.org/download.html"
        fi
    fi
else
    log_success "FFmpeg disponibile: $(ffmpeg -version 2>/dev/null | head -n 1)"
fi

if [ "$CHECK_ONLY" = true ]; then
    if [ -x "$VENV_PY" ]; then
        log_info "Test moduli Python ..."
        "$VENV_PY" -c "import PySide6, numpy; from PySide6.QtMultimedia import QMediaPlayer; print('  [OK] moduli Python')" \
            || log_error "Moduli Python mancanti: esegui ./setup/macos/install.command"
    else
        log_warn "Bundle non installato: esegui ./setup/macos/install.command"
    fi
    echo ""
    if [ "$FAILED" -ne 0 ]; then
        log_error "Controlli completati con problemi (vedi sopra)."
        exit 1
    fi
    log_success "Controlli completati."
    exit 0
fi

if [ "$FAILED" -ne 0 ]; then
    log_error "Impossibile continuare: mancano prerequisiti obbligatori (vedi sopra)."
    exit 1
fi

if ! ask_yes_no "BlindCue verra' installato in ${APP_BUNDLE} con la sua icona. Procedo?"; then
    log_info "Installazione annullata."
    exit 0
fi

# ------------------------------------------------------------------------------
# 3. Copia dei file nel bundle
# ------------------------------------------------------------------------------
log_step 3 "Copia dei file in ${APP_BUNDLE}"

if [ ! -f "${REPO_ROOT}/blindcue/main.py" ]; then
    log_error "File del programma non trovati in ${REPO_ROOT}/blindcue"
    exit 1
fi

mkdir -p "$MACOS_DIR" "$RES_DIR" "$APP_DIR"
rm -rf "${APP_DIR}/blindcue" "${APP_DIR}/docs"
cp -a "${REPO_ROOT}/blindcue" "${APP_DIR}/blindcue"
cp -a "${REPO_ROOT}/requirements.txt" "$REQ_FILE"
[ -f "${REPO_ROOT}/LICENSE" ] && cp -a "${REPO_ROOT}/LICENSE" "$APP_DIR/LICENSE"
[ -f "${REPO_ROOT}/README.md" ] && cp -a "${REPO_ROOT}/README.md" "$APP_DIR/README.md"
[ -d "${REPO_ROOT}/docs" ] && cp -a "${REPO_ROOT}/docs" "$APP_DIR/docs"
find "$APP_DIR" -type d -name "__pycache__" -prune -exec rm -rf {} + 2>/dev/null || true
find "$APP_DIR" -type f -name "*.pyc" -delete 2>/dev/null || true

if [ -f "$ICON_SRC" ]; then
    cp -f "$ICON_SRC" "${RES_DIR}/blindcue.icns"
    log_success "Icona copiata nel bundle"
else
    log_warn "Icona non trovata (${ICON_SRC}): il bundle usera' l'icona generica."
fi

cat > "${CONTENTS}/Info.plist" << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key><string>BlindCue</string>
    <key>CFBundleDisplayName</key><string>BlindCue</string>
    <key>CFBundleExecutable</key><string>BlindCue</string>
    <key>CFBundleIdentifier</key><string>org.blindcue.app</string>
    <key>CFBundleVersion</key><string>1.0</string>
    <key>CFBundleShortVersionString</key><string>1.0</string>
    <key>CFBundlePackageType</key><string>APPL</string>
    <key>CFBundleIconFile</key><string>blindcue</string>
    <key>LSMinimumSystemVersion</key><string>11.0</string>
    <key>NSHighResolutionCapable</key><true/>
    <key>LSApplicationCategoryType</key><string>public.app-category.video</string>
</dict>
</plist>
EOF

echo "APPL????" > "${CONTENTS}/PkgInfo"

# Eseguibile del bundle: macOS non passa il PATH della shell, quindi qui
# aggiungiamo Homebrew (dove vive ffmpeg) prima di avviare il programma.
cat > "${MACOS_DIR}/BlindCue" << 'EOF'
#!/bin/bash
# BlindCue — avvio del bundle applicativo.
DIR="$(cd "$(dirname "$0")/../Resources" && pwd)"

export PATH="/opt/homebrew/bin:/usr/local/bin:${PATH}"
export LC_NUMERIC=C
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-2}"

exec "${DIR}/venv/bin/python" "${DIR}/app/blindcue/main.py" "$@"
EOF
chmod +x "${MACOS_DIR}/BlindCue"

log_success "Bundle creato in ${APP_BUNDLE}"

# ------------------------------------------------------------------------------
# 4. Ambiente Python e dipendenze
# ------------------------------------------------------------------------------
log_step 4 "Ambiente Python e dipendenze"

if [ ! -x "$VENV_PY" ]; then
    log_info "Creo l'ambiente virtuale in ${VENV_DIR} ..."
    python3 -m venv "$VENV_DIR" || { log_error "Creazione venv non riuscita."; exit 1; }
else
    log_info "Ambiente virtuale esistente riutilizzato"
fi

"$VENV_PY" -m pip install --upgrade pip setuptools wheel --quiet || log_warn "Aggiornamento pip non riuscito."
"$VENV_PY" -m pip install -r "$REQ_FILE" || { log_error "pip install non riuscito."; exit 1; }
log_success "Dipendenze Python installate"

# ------------------------------------------------------------------------------
# 5. Verifica
# ------------------------------------------------------------------------------
log_step 5 "Verifica dell'installazione"

if ! "$VENV_PY" - << 'PYEOF'
import sys
try:
    import PySide6
    from PySide6.QtCore import qVersion
    from PySide6.QtMultimedia import QMediaPlayer  # noqa: F401
    import numpy as np
    np.zeros((8,), dtype=np.float32)
    print(f"  [OK] PySide6 / QtMultimedia (Qt {qVersion()}) + NumPy")
except Exception as exc:
    print(f"  [FAIL] {exc}", file=sys.stderr)
    sys.exit(1)
PYEOF
then
    log_error "Moduli Python non funzionanti."
    exit 1
fi

if command -v ffmpeg &>/dev/null && ffmpeg -hide_banner -hwaccels 2>/dev/null | grep -qi videotoolbox; then
    log_success "VideoToolbox disponibile: decodifica video accelerata dalla GPU"
else
    log_info "VideoToolbox non segnalato da FFmpeg: verra' usata la decodifica software."
fi

if QT_QPA_PLATFORM=offscreen "$VENV_PY" - << 'PYEOF'
import sys
from PySide6.QtWidgets import QApplication
app = QApplication(sys.argv)
print(f"  [OK] {len(app.screens())} schermo/i rilevati")
PYEOF
then
    log_success "Backend grafico Qt operativo"
else
    log_warn "Qt non ha potuto inizializzare il backend offscreen in questo ambiente."
fi

log_info "Smoke test: import di tutti i moduli BlindCue ..."
if ( cd "${APP_DIR}/blindcue" && QT_QPA_PLATFORM=offscreen "$VENV_PY" - << 'PYEOF'
import sys
sys.path.insert(0, ".")
from PySide6.QtWidgets import QApplication
app = QApplication(sys.argv)
import engine.audio_analyzer          # noqa: F401
import engine.player_live             # noqa: F401
import engine.player_test             # noqa: F401
import models.project_manager         # noqa: F401
import services.osc_server            # noqa: F401
import services.web_server            # noqa: F401
import ui.main_window                 # noqa: F401
import ui.output_window               # noqa: F401
print("  [OK] Tutti i moduli BlindCue importati correttamente")
PYEOF
); then
    log_success "Smoke test applicazione superato"
else
    log_error "L'applicazione non e' riuscita a importare i propri moduli."
    exit 1
fi

# ------------------------------------------------------------------------------
# 6. Registrazione nel Launchpad
# ------------------------------------------------------------------------------
log_step 6 "Registrazione nel Launchpad"
# Ricostruisce la cache di Launchpad/Finder: senza questo il bundle appena
# creato può non comparire nel Launchpad finché non si fa logout.
if [ -x /System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister ]; then
    /System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister \
        -f "$APP_BUNDLE" &>/dev/null || true
fi
touch "$APP_BUNDLE"
log_success "Bundle registrato: lo trovi in ~/Applications e nel Launchpad"

echo ""
echo -e "${CLR_GREEN}${CLR_BOLD}"
echo "======================================================================"
echo "    [OK] BlindCue installato correttamente su macOS"
echo "======================================================================"
echo -e "${CLR_RESET}"
echo "Bundle:  ${APP_BUNDLE}"
echo "Avvio:   doppio clic su BlindCue nel Launchpad o in ~/Applications"
echo "         oppure: ./setup/macos/run.command"
echo "Proiettore: ./setup/macos/run.command --output-screen 1"
echo "Rimozione:  ./setup/macos/install.command --uninstall"
echo ""
