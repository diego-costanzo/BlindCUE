#!/usr/bin/env bash
# ==============================================================================
# BlindCue — Installer per Linux (installazione per-utente, senza password)
#
# Installa in:  ${XDG_DATA_HOME:-$HOME/.local/share}/blindcue
# Crea:         ~/.local/bin/blindcue
#               ~/.local/share/applications/blindcue.desktop
#               ~/.local/share/icons/hicolor/256x256/apps/blindcue.png
#
# Uso:
#   ./setup/linux/install.sh              installazione interattiva completa
#   ./setup/linux/install.sh --yes        senza domande (per la GUI)
#   ./setup/linux/install.sh --check      solo controlli, non installa nulla
#   ./setup/linux/install.sh --no-sudo    non usa mai i privilegi di root
#   ./setup/linux/install.sh --no-gpu     non installa i driver VA-API
#   ./setup/linux/install.sh --prefix DIR installa in una cartella alternativa
#
# Le righe che iniziano con "[STEP]" permettono alla finestra grafica di
# mostrare l'avanzamento: numero di passo e descrizione.
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

INSTALL_DIR="${BLINDCUE_PREFIX:-${XDG_DATA_HOME:-$HOME/.local/share}/blindcue}"
APP_DIR="${INSTALL_DIR}/app"
VENV_DIR="${INSTALL_DIR}/venv"
VENV_PY="${VENV_DIR}/bin/python"
REQ_FILE="${APP_DIR}/requirements.txt"

BIN_DIR="${HOME}/.local/bin"
APPS_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
ICON_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/256x256/apps"
ICON_SRC="${REPO_ROOT}/setup/assets/blindcue-256.png"

TOTAL_STEPS=6
ASSUME_YES=false
CHECK_ONLY=false
NO_SUDO=false
WITH_GPU=true

# ── Colori ANSI ───────────────────────────────────────────────────────────────
CLR_RESET="\033[0m"
CLR_BOLD="\033[1m"
CLR_RED="\033[1;31m"
CLR_GREEN="\033[1;32m"
CLR_YELLOW="\033[1;33m"
CLR_BLUE="\033[1;34m"
CLR_CYAN="\033[1;36m"

print_header() {
    echo -e "${CLR_CYAN}${CLR_BOLD}"
    echo "======================================================================"
    echo "         🎬 BlindCue — Installazione (Linux)"
    echo "              installazione nella cartella utente, senza password"
    echo "======================================================================"
    echo -e "${CLR_RESET}"
}

log_info()    { echo -e "${CLR_BLUE}[INFO]${CLR_RESET} $1"; }
log_success() { echo -e "${CLR_GREEN}[ OK ]${CLR_RESET} $1"; }
log_warn()    { echo -e "${CLR_YELLOW}[WARN]${CLR_RESET} $1"; }
log_error()   { echo -e "${CLR_RED}[FAIL]${CLR_RESET} $1"; }
log_step()    { echo -e "${CLR_CYAN}[STEP]${CLR_RESET} $1/${TOTAL_STEPS} $2"; }

# ── Argomenti ─────────────────────────────────────────────────────────────────
while [ $# -gt 0 ]; do
    case "$1" in
        -y|--yes)      ASSUME_YES=true ;;
        --check)       CHECK_ONLY=true ;;
        --no-sudo|--user) NO_SUDO=true ;;
        --no-gpu)      WITH_GPU=false ;;
        --prefix)      shift; INSTALL_DIR="${1:?--prefix richiede un percorso}"
                       APP_DIR="${INSTALL_DIR}/app"
                       VENV_DIR="${INSTALL_DIR}/venv"
                       VENV_PY="${VENV_DIR}/bin/python"
                       REQ_FILE="${APP_DIR}/requirements.txt" ;;
        -h|--help)
            echo "Uso: ./setup/linux/install.sh [--yes] [--check] [--no-sudo] [--no-gpu] [--prefix DIR]"
            exit 0 ;;
        *) log_warn "Opzione ignorata: $1" ;;
    esac
    shift
done

# ── Privilegi ─────────────────────────────────────────────────────────────────
# Tre strade, in ordine di preferenza quando non c'è un terminale:
#   1. già root            -> esegue
#   2. terminale (TTY)     -> sudo, che può chiedere la password nel terminale
#   3. sessione grafica    -> pkexec, che mostra la richiesta di password in una
#                             finestra di sistema (nessun terminale necessario)
run_privileged() {
    if [ "$(id -u)" -eq 0 ]; then
        "$@"
    elif [ "$NO_SUDO" = true ]; then
        log_error "Servono i privilegi di root ma è attivo --no-sudo: $*"
        return 1
    elif [ -t 0 ]; then
        sudo "$@"
    elif command -v pkexec &>/dev/null; then
        pkexec "$@"
    else
        sudo -n "$@"
    fi
}

# ── Domande all'utente ────────────────────────────────────────────────────────
ask_yes_no() {
    local prompt="$1"
    local default="${2:-yes}"
    local ans=""
    if [ "$ASSUME_YES" = true ]; then
        return 0
    fi
    if [ -t 0 ]; then
        if [ "$default" = "yes" ]; then
            read -r -p "${prompt} [S/n] " ans || ans=""
        else
            read -r -p "${prompt} [s/N] " ans || ans=""
        fi
        ans="${ans:-$default}"
        [[ "$ans" =~ ^([yYsS]|[yY][eE][sS]|[sS][iI])$ ]]
        return
    fi
    if command -v zenity &>/dev/null; then
        zenity --question --title="BlindCue" --text="$prompt" --width=460 2>/dev/null
        return
    fi
    if command -v kdialog &>/dev/null; then
        kdialog --title "BlindCue" --yesno "$prompt" 2>/dev/null
        return
    fi
    return 0
}

# ------------------------------------------------------------------------------
# 1. Rilevamento distribuzione
# ------------------------------------------------------------------------------
detect_distribution() {
    if [ ! -f /etc/os-release ]; then
        log_error "Impossibile riconoscere la distribuzione (/etc/os-release assente)."
        exit 1
    fi
    # shellcheck disable=SC1091
    . /etc/os-release
    DISTRO_ID="${ID:-unknown}"
    DISTRO_LIKE="${ID_LIKE:-}"

    log_info "Sistema: ${PRETTY_NAME:-$DISTRO_ID} (ID: $DISTRO_ID, ID_LIKE: $DISTRO_LIKE)"

    if [[ "$DISTRO_ID" =~ ^(arch|endeavouros|manjaro|artix|garuda)$ ]] || [[ "$DISTRO_LIKE" =~ arch ]]; then
        FAMILY="arch"
    elif [[ "$DISTRO_ID" =~ ^(debian|ubuntu|linuxmint|pop|elementary|zorin|kali|raspbian)$ ]] || [[ "$DISTRO_LIKE" =~ (debian|ubuntu) ]]; then
        FAMILY="debian"
    elif [[ "$DISTRO_ID" =~ ^(fedora|rhel|centos|rocky|almalinux)$ ]] || [[ "$DISTRO_LIKE" =~ (fedora|rhel) ]]; then
        FAMILY="fedora"
    else
        FAMILY="unknown"
        log_warn "Distribuzione '$DISTRO_ID' non mappata: uso controlli generici."
    fi
    log_info "Gestore pacchetti: ${CLR_BOLD}${FAMILY}${CLR_RESET}"
}

# ------------------------------------------------------------------------------
# 2. Controlli preliminari
# ------------------------------------------------------------------------------
PREFLIGHT_FAILED=false

check_python() {
    log_info "Controllo Python 3.10+ ..."
    if ! command -v python3 &>/dev/null; then
        log_error "python3 non trovato."
        PREFLIGHT_FAILED=true
        return
    fi
    local ver
    ver="$(python3 -c 'import sys; print("%d.%d.%d" % sys.version_info[:3])' 2>/dev/null || echo "0.0.0")"
    if python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
        log_success "Python ${ver}"
    else
        log_error "Python ${ver} è troppo vecchio: serve 3.10 o superiore."
        PREFLIGHT_FAILED=true
    fi
    if ! python3 -c 'import venv' 2>/dev/null; then
        log_warn "Modulo 'venv' mancante (verrà installato più avanti se necessario)."
    fi
}

check_memory() {
    local avail_mb=0 total_mb=0
    if [ -r /proc/meminfo ]; then
        avail_mb="$(awk '/^MemAvailable:/ {print int($2/1024)}' /proc/meminfo)"
        total_mb="$(awk '/^MemTotal:/ {print int($2/1024)}' /proc/meminfo)"
        log_info "Memoria: ${total_mb} MB totali, ${avail_mb} MB disponibili"
        if [ "${avail_mb:-0}" -lt 1024 ]; then
            log_warn "Meno di 1 GB di RAM libera: chiudi altri programmi prima di uno spettacolo."
        fi
        if [ "${total_mb:-0}" -lt 2048 ]; then
            log_warn "Solo ${total_mb} MB di RAM: verrà scelto il profilo ECO."
        fi
    fi
}

check_disk() {
    local target_parent
    target_parent="$(dirname "$INSTALL_DIR")"
    while [ ! -d "$target_parent" ] && [ "$target_parent" != "/" ]; do
        target_parent="$(dirname "$target_parent")"
    done
    local free_kb
    free_kb="$(df -Pk "$target_parent" | awk 'NR==2 {print $4}')"
    local free_mb=$(( free_kb / 1024 ))
    log_info "Spazio libero: ${free_mb} MB"
    if [ "$free_mb" -lt 1500 ]; then
        log_error "Servono almeno 1.5 GB liberi (PySide6 è pesante)."
        PREFLIGHT_FAILED=true
    fi
}

check_network() {
    log_info "Controllo connessione a PyPI ..."
    if command -v curl &>/dev/null && curl -sSf --max-time 8 https://pypi.org/simple/ -o /dev/null 2>/dev/null; then
        log_success "PyPI raggiungibile"
    elif command -v wget &>/dev/null && wget -q --timeout=8 -O /dev/null https://pypi.org/simple/ 2>/dev/null; then
        log_success "PyPI raggiungibile"
    elif [ -d "$VENV_DIR" ]; then
        log_warn "Controllo rete fallito, ma esiste già un ambiente virtuale: continuo."
    else
        log_error "Nessun accesso a pypi.org: impossibile scaricare le dipendenze."
        PREFLIGHT_FAILED=true
    fi
}

check_audio_server() {
    log_info "Controllo server audio ..."
    if [ -n "${PIPEWIRE_RUNTIME_DIR:-}" ] || command -v pw-cli &>/dev/null; then
        log_success "PipeWire rilevato"
    elif command -v pactl &>/dev/null; then
        log_success "PulseAudio rilevato"
    elif [ -d /dev/snd ]; then
        log_success "Dispositivi ALSA rilevati"
    else
        log_warn "Nessun server audio: la riproduzione potrebbe fallire (installa PipeWire o PulseAudio)."
    fi
}

check_display() {
    log_info "Controllo sessione grafica ..."
    if [ -n "${WAYLAND_DISPLAY:-}" ]; then
        log_success "Sessione Wayland (${WAYLAND_DISPLAY})"
    elif [ -n "${DISPLAY:-}" ]; then
        log_success "Sessione X11 (${DISPLAY})"
    else
        log_warn "Nessuna sessione grafica attiva: avvia BlindCue dal desktop."
    fi
}

check_gpu() {
    log_info "Controllo accelerazione video hardware ..."
    if [ -e /dev/dri/renderD128 ]; then
        log_success "Dispositivo Direct Rendering trovato (/dev/dri/renderD128)"
    elif [ -d /dev/dri ]; then
        log_success "Dispositivo DRM trovato (/dev/dri)"
    else
        log_info "Nessun /dev/dri: verrà usato il rendering software."
    fi
    if command -v vainfo &>/dev/null; then
        if vainfo 2>/dev/null | grep -q "VAProfile"; then
            log_success "Decodifica VA-API disponibile"
        else
            log_info "VA-API presente ma nessun profilo di decodifica riportato"
        fi
    fi
}

run_preflight() {
    echo ""
    log_step 1 "Controlli preliminari"
    detect_distribution
    check_python
    check_memory
    check_disk
    check_network
    check_audio_server
    check_display
    check_gpu
    echo ""
}

# ------------------------------------------------------------------------------
# 3. Pacchetti di sistema (solo se mancano: ffmpeg, python3, librerie Qt)
# ------------------------------------------------------------------------------
install_system_packages() {
    echo ""
    log_step 2 "Componenti di sistema"
    log_info "Verifico i componenti di sistema mancanti ..."

    local missing=()
    command -v python3  &>/dev/null || missing+=("python3")
    command -v ffmpeg   &>/dev/null || missing+=("ffmpeg")
    command -v ffprobe  &>/dev/null || missing+=("ffprobe")

    if [ ${#missing[@]} -eq 0 ]; then
        log_success "python3, ffmpeg e ffprobe sono già installati."
        install_qt_runtime_libs
        return 0
    fi

    if [ "$NO_SUDO" = true ]; then
        log_error "Strumenti obbligatori mancanti: ${missing[*]}"
        log_error "Installali a mano (es. 'sudo apt install python3 python3-venv ffmpeg') e riprova."
        exit 1
    fi

    log_warn "Servono i privilegi di amministratore per installare: ${missing[*]}"

    case "$FAMILY" in
        arch)
            local core=(python ffmpeg libva libva-utils tk)
            log_info "Installazione via pacman: ${core[*]}"
            run_privileged pacman -S --needed --noconfirm "${core[@]}" || {
                log_error "pacman ha fallito. Controlla mirror/keyring e riprova."
                exit 1
            }
            ;;
        debian)
            log_info "Aggiornamento indici apt ..."
            run_privileged apt-get update -y || log_warn "apt-get update fallito: uso gli indici in cache."
            local core=(python3 python3-venv python3-pip python3-tk ffmpeg libva2 libva-drm2 vainfo)
            log_info "Installazione via apt: ${core[*]}"
            run_privileged apt-get install -y "${core[@]}" || {
                log_error "apt-get non è riuscito a installare i pacchetti obbligatori."
                exit 1
            }
            ;;
        fedora)
            log_info "Installazione via dnf ..."
            run_privileged dnf install -y python3 python3-pip python3-tkinter libva libva-utils || {
                log_error "dnf ha fallito per python/libva."
                exit 1
            }
            # 'ffmpeg' è in RPM Fusion; 'ffmpeg-free' è il pacchetto Fedora.
            run_privileged dnf install -y ffmpeg || run_privileged dnf install -y ffmpeg-free || {
                log_error "Impossibile installare FFmpeg. Abilita RPM Fusion free e riprova:"
                log_error "  sudo dnf install https://download1.rpmfusion.org/free/fedora/rpmfusion-free-release-\$(rpm -E %fedora).noarch.rpm"
                exit 1
            }
            ;;
        *)
            log_error "Distribuzione non riconosciuta: installa 'python3' (3.10+) e 'ffmpeg' a mano."
            exit 1
            ;;
    esac

    verify_mandatory_tools
    install_qt_runtime_libs
    if [ "$WITH_GPU" = true ]; then
        install_gpu_drivers
    fi
    return 0
}

verify_mandatory_tools() {
    local ok=true
    for tool in python3 ffmpeg ffprobe; do
        if command -v "$tool" &>/dev/null; then
            log_success "$tool disponibile"
        else
            log_error "$tool è ancora mancante"
            ok=false
        fi
    done
    if [ "$ok" != true ]; then
        exit 1
    fi
}

# Qt 6 richiede alcune librerie X11/xcb anche su Wayland, altrimenti il
# programma termina all'avvio con "could not load the Qt platform plugin".
install_qt_runtime_libs() {
    local pkgs=()
    case "$FAMILY" in
        debian)
            pkgs=(libgl1 libegl1 libxkbcommon0 libxkbcommon-x11-0 libxcb-cursor0
                  libxcb-icccm4 libxcb-keysyms1 libxcb-shape0 libxcb-xinerama0
                  libxcb-randr0 libxcb-render-util0 libxcb-image0 libxcb-sync1
                  libxcb-xfixes0 libxcb-xkb1 libpulse0)
            ;;
        fedora)
            pkgs=(mesa-libGL mesa-libEGL libxkbcommon-x11 xcb-util-cursor
                  xcb-util-wm pulseaudio-libs)
            ;;
        arch)
            pkgs=(libglvnd mesa libxkbcommon-x11 xcb-util-cursor xcb-util-wm libpulse)
            ;;
        *) return 0 ;;
    esac

    if [ "$NO_SUDO" = true ]; then
        return 0
    fi

    log_info "Verifico le librerie runtime di Qt 6 (xcb/EGL/audio) ..."
    case "$FAMILY" in
        debian)
            run_privileged apt-get install -y --no-install-recommends "${pkgs[@]}" \
                || log_warn "Alcune librerie Qt non sono state installate automaticamente."
            ;;
        fedora)
            run_privileged dnf install -y "${pkgs[@]}" \
                || log_warn "Alcune librerie Qt non sono state installate automaticamente."
            ;;
        arch)
            run_privileged pacman -S --needed --noconfirm "${pkgs[@]}" \
                || log_warn "Alcune librerie Qt non sono state installate automaticamente."
            ;;
    esac
}

install_gpu_drivers() {
    local gpu_pkgs=()
    case "$FAMILY" in
        debian) gpu_pkgs=(mesa-va-drivers mesa-vulkan-drivers) ;;
        fedora) gpu_pkgs=(mesa-va-drivers mesa-dri-drivers) ;;
        arch)   gpu_pkgs=(libva-mesa-driver) ;;
        *) return 0 ;;
    esac

    log_info "Installazione driver GPU/VA-API: ${gpu_pkgs[*]}"
    case "$FAMILY" in
        debian) run_privileged apt-get install -y --no-install-recommends "${gpu_pkgs[@]}" ;;
        fedora) run_privileged dnf install -y "${gpu_pkgs[@]}" ;;
        arch)   run_privileged pacman -S --needed --noconfirm "${gpu_pkgs[@]}" ;;
    esac || log_warn "Driver GPU non installati: verrà usata la decodifica software."
}

# ------------------------------------------------------------------------------
# 4. Copia dei file nella cartella di installazione
# ------------------------------------------------------------------------------
copy_application_files() {
    echo ""
    log_step 3 "Copia dei file in ${INSTALL_DIR}"

    if [ ! -f "${REPO_ROOT}/blindcue/main.py" ]; then
        log_error "File del programma non trovati in ${REPO_ROOT}/blindcue"
        exit 1
    fi

    mkdir -p "$INSTALL_DIR"
    # Sostituisce solo il codice: la cartella venv resta (aggiornamento veloce).
    rm -rf "${APP_DIR}/blindcue" "${APP_DIR}/docs"
    mkdir -p "$APP_DIR"
    cp -a "${REPO_ROOT}/blindcue" "${APP_DIR}/blindcue"
    cp -a "${REPO_ROOT}/requirements.txt" "$APP_DIR/requirements.txt"
    [ -f "${REPO_ROOT}/LICENSE" ] && cp -a "${REPO_ROOT}/LICENSE" "$APP_DIR/LICENSE"
    [ -f "${REPO_ROOT}/README.md" ] && cp -a "${REPO_ROOT}/README.md" "$APP_DIR/README.md"
    if [ -d "${REPO_ROOT}/docs" ]; then
        cp -a "${REPO_ROOT}/docs" "${APP_DIR}/docs"
    fi

    # Le cache di Python non servono e confondono un aggiornamento.
    find "$APP_DIR" -type d -name "__pycache__" -prune -exec rm -rf {} + 2>/dev/null || true
    find "$APP_DIR" -type f -name "*.pyc" -delete 2>/dev/null || true

    log_success "Programma copiato in ${APP_DIR}"
}

# ------------------------------------------------------------------------------
# 5. Ambiente Python e dipendenze
# ------------------------------------------------------------------------------
setup_python_env() {
    echo ""
    log_step 4 "Ambiente Python e dipendenze"

    if [ ! -x "$VENV_PY" ]; then
        log_info "Creo l'ambiente virtuale in ${VENV_DIR} ..."
        if ! python3 -m venv "$VENV_DIR" 2>/dev/null; then
            if [ "$NO_SUDO" = false ] && command -v apt-get &>/dev/null; then
                log_warn "Creazione venv fallita: installo python3-venv ..."
                run_privileged apt-get install -y python3-venv
                python3 -m venv "$VENV_DIR"
            else
                log_error "Impossibile creare l'ambiente virtuale. Installa 'python3-venv' e riprova."
                exit 1
            fi
        fi
        log_success "Ambiente virtuale creato"
    else
        log_info "Ambiente virtuale esistente riutilizzato"
    fi

    log_info "Aggiorno pip, setuptools e wheel ..."
    "$VENV_PY" -m pip install --upgrade pip setuptools wheel --quiet

    if [ ! -f "$REQ_FILE" ]; then
        log_error "requirements.txt non trovato in ${REQ_FILE}"
        exit 1
    fi

    log_info "Installo le dipendenze Python (può richiedere qualche minuto) ..."
    "$VENV_PY" -m pip install -r "$REQ_FILE" || {
        log_error "pip install fallito. Controlla la connessione e riprova."
        exit 1
    }
    log_success "Dipendenze Python installate"
}

# ------------------------------------------------------------------------------
# 6. Verifica
# ------------------------------------------------------------------------------
verify_installation() {
    echo ""
    log_step 5 "Verifica dell'installazione"

    if [ ! -x "$VENV_PY" ]; then
        log_warn "Ambiente virtuale assente: salto i test dei moduli Python."
        return 0
    fi

    log_info "Test moduli Python (PySide6, QtMultimedia, NumPy, qrcode) ..."
    if "$VENV_PY" - << 'PYEOF'
import sys

try:
    import PySide6
    from PySide6.QtCore import qVersion
    from PySide6.QtMultimedia import QMediaPlayer  # noqa: F401
    from PySide6.QtMultimediaWidgets import QVideoWidget  # noqa: F401
    print(f"  [OK] PySide6 / QtMultimedia caricati (Qt {qVersion()})")
except Exception as exc:
    print(f"  [FAIL] PySide6 / QtMultimedia: {exc}", file=sys.stderr)
    sys.exit(1)

try:
    import numpy as np
    np.zeros((8,), dtype=np.float32)
    print("  [OK] NumPy caricato")
except Exception as exc:
    print(f"  [FAIL] NumPy: {exc}", file=sys.stderr)
    sys.exit(1)

try:
    import qrcode  # noqa: F401
    print("  [OK] qrcode caricato")
except Exception as exc:
    print(f"  [WARN] qrcode mancante ({exc}): verrà usato il fallback nativo per il QR")
PYEOF
    then
        log_success "Moduli Python obbligatori verificati"
    else
        log_error "Moduli Python rotti. Riprova: ${VENV_PY} -m pip install -r ${REQ_FILE}"
        exit 1
    fi

    log_info "Test FFmpeg / FFprobe ..."
    if command -v ffmpeg &>/dev/null && command -v ffprobe &>/dev/null; then
        log_success "FFmpeg disponibile: $(ffmpeg -version 2>/dev/null | head -n 1)"
    else
        log_error "FFmpeg o FFprobe mancante: forma d'onda, loudness e normalizzazione sarebbero disattivati."
        exit 1
    fi

    log_info "Test accelerazione video hardware ..."
    if command -v vainfo &>/dev/null && vainfo 2>/dev/null | grep -q "VAProfile"; then
        log_success "Decodifica VA-API disponibile (offload sulla GPU)"
    elif [ -e /dev/dri/renderD128 ]; then
        log_info "Dispositivo DRM presente; QtMultimedia negozierà la decodifica hardware all'avvio."
    else
        log_info "Nessuna decodifica hardware: verrà usato il rendering software."
    fi

    log_info "Test uscite audio ..."
    if "$VENV_PY" - << 'PYEOF'
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtMultimedia import QMediaDevices

app = QApplication.instance() or QApplication(sys.argv)
outputs = QMediaDevices.audioOutputs()
if not outputs:
    print("  [WARN] Nessuna uscita audio riportata")
else:
    default = QMediaDevices.defaultAudioOutput()
    label = default.description() if default and not default.isNull() else outputs[0].description()
    print(f"  [OK] {len(outputs)} uscite audio; predefinita: {label}")
PYEOF
    then
        log_success "Sottosistema audio raggiungibile"
    else
        log_warn "Impossibile interrogare le uscite audio ora (la sessione audio potrebbe funzionare lo stesso)."
    fi

    log_info "Test schermi ..."
    if QT_QPA_PLATFORM=offscreen "$VENV_PY" - << 'PYEOF'
import sys
from PySide6.QtWidgets import QApplication

app = QApplication(sys.argv)
print(f"  [OK] {len(app.screens())} schermo/i rilevati")
PYEOF
    then
        log_success "Backend grafico Qt operativo"
    else
        log_warn "Qt non è riuscito a inizializzare il backend offscreen in questo ambiente."
    fi

    log_info "Smoke test: importo tutti i moduli BlindCue ..."
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
        log_success "Smoke test dell'applicazione superato"
    else
        log_error "L'applicazione non è riuscita a importare i propri moduli. Segnala l'errore qui sopra."
        exit 1
    fi
}

# ------------------------------------------------------------------------------
# 7. Lanciatore, icona e voce di menu
# ------------------------------------------------------------------------------
create_launchers() {
    echo ""
    log_step 6 "Lanciatore, icona e voce di menu"

    local run_script="${INSTALL_DIR}/run.sh"
    cat > "$run_script" << 'EOF'
#!/usr/bin/env bash
# BlindCue — avvio dell'installazione corrente.
set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export LC_NUMERIC=C
# Un solo core libero per il sistema anche quando FFmpeg decodifica: il
# programma limita da sé i propri worker, qui evitiamo solo thread illimitati.
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-2}"

exec "${DIR}/venv/bin/python" "${DIR}/app/blindcue/main.py" "$@"
EOF
    chmod +x "$run_script"
    log_success "Creato ${run_script}"

    mkdir -p "$BIN_DIR"
    cat > "${BIN_DIR}/blindcue" << EOF
#!/usr/bin/env bash
# BlindCue — comando di avvio (generato dall'installer).
exec "${run_script}" "\$@"
EOF
    chmod +x "${BIN_DIR}/blindcue"
    log_success "Comando disponibile: ${BIN_DIR}/blindcue"

    mkdir -p "$ICON_DIR"
    if [ -f "$ICON_SRC" ]; then
        cp -f "$ICON_SRC" "${ICON_DIR}/blindcue.png"
        command -v gtk-update-icon-cache &>/dev/null && \
            gtk-update-icon-cache -f -t "$(dirname "$(dirname "$(dirname "$ICON_DIR")")")" &>/dev/null || true
        log_success "Icona installata in ${ICON_DIR}/blindcue.png"
    else
        log_warn "Icona non trovata (${ICON_SRC}): la voce di menu userà un'icona generica."
    fi

    mkdir -p "$APPS_DIR"
    cat > "${APPS_DIR}/blindcue.desktop" << EOF
[Desktop Entry]
Type=Application
Name=BlindCue
GenericName=Live Cue Player
Comment=Player di cue audio/video per spettacoli dal vivo
Exec="${run_script}"
Icon=blindcue
Terminal=false
Categories=AudioVideo;Player;AudioVideoEditing;
StartupNotify=true
StartupWMClass=blindcue
EOF
    chmod +x "${APPS_DIR}/blindcue.desktop"
    command -v update-desktop-database &>/dev/null && \
        update-desktop-database "$APPS_DIR" &>/dev/null || true
    log_success "Voce di menu creata: ${APPS_DIR}/blindcue.desktop"

    # Copia "sul posto": se l'utente lancia il software dalla cartella del
    # progetto, il venv locale non deve più essere ricreato ad ogni prova.
    log_info "Suggerimento: nei lanci successivi usa 'blindcue' oppure il menu applicazioni."
}

# ------------------------------------------------------------------------------
# Flusso principale
# ------------------------------------------------------------------------------
main() {
    print_header

    run_preflight

    if [ "$CHECK_ONLY" = true ]; then
        verify_installation || true
        echo ""
        if [ "$PREFLIGHT_FAILED" = true ]; then
            log_error "I controlli hanno trovato problemi bloccanti (vedi sopra)."
            exit 1
        fi
        log_success "Controlli completati. Esegui senza --check per installare ciò che manca."
        exit 0
    fi

    if [ "$PREFLIGHT_FAILED" = true ]; then
        log_error "Impossibile continuare: mancano i prerequisiti obbligatori (vedi sopra)."
        exit 1
    fi

    if ! ask_yes_no "$(printf 'BlindCue verrà installato in %s e creerà il collegamento di avvio. Procedo?' "$INSTALL_DIR")" "yes"; then
        log_info "Installazione annullata."
        exit 0
    fi

    install_system_packages
    copy_application_files
    setup_python_env
    verify_installation
    create_launchers

    local cores ram
    cores="$(nproc 2>/dev/null || echo '?')"
    ram="$(awk '/^MemTotal:/ {print int($2/1024)}' /proc/meminfo 2>/dev/null || echo '?')"

    echo ""
    echo -e "${CLR_GREEN}${CLR_BOLD}"
    echo "======================================================================"
    echo "            🎉 BlindCue INSTALLATO CORRETTAMENTE"
    echo "======================================================================"
    echo -e "${CLR_RESET}"
    echo "Sistema: ${cores} core CPU, ${ram} MB RAM"
    echo "Cartella: ${INSTALL_DIR}"
    echo ""
    echo "Avvio:"
    echo -e "  1. ${CLR_CYAN}blindcue${CLR_RESET}   (oppure ${BIN_DIR}/blindcue)"
    echo "  2. Dal menu applicazioni: cerca 'BlindCue'"
    echo -e "  3. ${CLR_CYAN}${INSTALL_DIR}/run.sh --output-screen 1${CLR_RESET}   (scegli il proiettore)"
    echo ""
    echo -e "Disinstallazione: cancella ${CLR_CYAN}${INSTALL_DIR}${CLR_RESET} e la voce di menu."
    echo ""
}

main "$@"
