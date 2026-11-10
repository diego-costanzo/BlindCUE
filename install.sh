#!/usr/bin/env bash
# ==============================================================================
# BlindCue — Installer & Environment Setup for Linux
# Distro support: Debian / Ubuntu / Mint / Pop!_OS, Arch / EndeavourOS / Manjaro, Fedora
# ==============================================================================

set -euo pipefail

# ANSI Colors
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
    echo "         🎬 BlindCue — Live Multimedia Cue Player Installer           "
    echo "              Failsafe Architecture • Linux Optimized                 "
    echo "======================================================================"
    echo -e "${CLR_RESET}"
}

log_info() {
    echo -e "${CLR_BLUE}[INFO]${CLR_RESET} $1"
}

log_success() {
    echo -e "${CLR_GREEN}[✓ SUCCESS]${CLR_RESET} $1"
}

log_warn() {
    echo -e "${CLR_YELLOW}[WARNING]${CLR_RESET} $1"
}

log_error() {
    echo -e "${CLR_RED}[ERROR]${CLR_RESET} $1"
}

# ------------------------------------------------------------------------------
# 1. Distribution Detection
# ------------------------------------------------------------------------------
detect_distribution() {
    if [ ! -f /etc/os-release ]; then
        log_error "Cannot detect Linux distribution (/etc/os-release not found)."
        exit 1
    fi

    # Read os-release
    . /etc/os-release
    DISTRO_ID="${ID:-unknown}"
    DISTRO_LIKE="${ID_LIKE:-}"

    log_info "Detected OS: ${PRETTY_NAME:-$DISTRO_ID} (ID: $DISTRO_ID, ID_LIKE: $DISTRO_LIKE)"

    if [[ "$DISTRO_ID" =~ ^(arch|endeavouros|manjaro|artix|garuda)$ ]] || [[ "$DISTRO_LIKE" =~ arch ]]; then
        FAMILY="arch"
    elif [[ "$DISTRO_ID" =~ ^(debian|ubuntu|linuxmint|pop|elementary|zorin)$ ]] || [[ "$DISTRO_LIKE" =~ (debian|ubuntu) ]]; then
        FAMILY="debian"
    elif [[ "$DISTRO_ID" =~ ^(fedora|rhel|centos|rocky|almalinux)$ ]] || [[ "$DISTRO_LIKE" =~ (fedora|rhel) ]]; then
        FAMILY="fedora"
    else
        FAMILY="unknown"
        log_warn "Distribution '$DISTRO_ID' is not explicitly mapped. Will attempt generic install."
    fi
    log_info "Package manager family: ${CLR_BOLD}${FAMILY}${CLR_RESET}"
}

# ------------------------------------------------------------------------------
# 2. System Dependencies Installation
# ------------------------------------------------------------------------------
install_system_packages() {
    echo ""
    log_info "Verifica dei componenti essenziali di sistema (python3, ffmpeg)..."

    # Check if core tools are already present
    local HAS_PYTHON=$(command -v python3 || true)
    local HAS_FFMPEG=$(command -v ffmpeg || true)
    local HAS_FFPROBE=$(command -v ffprobe || true)

    # If the user explicitly requested --no-sudo or if all core tools exist, skip sudo!
    if [ "${NO_SUDO:-false}" = "true" ]; then
        log_info "Modalità --no-sudo attiva: salto l'installazione dei pacchetti con privilegi root."
        return 0
    fi

    if [ -n "$HAS_PYTHON" ] && [ -n "$HAS_FFMPEG" ] && [ -n "$HAS_FFPROBE" ]; then
        log_success "Tutti i componenti di sistema (python3, ffmpeg, ffprobe) sono GIÀ PRESENTI!"
        log_info "Nessun pacchetto di sistema da installare: non è richiesta alcuna password di sudo/root."
        return 0
    fi

    log_warn "Alcuni componenti di sistema mancano. Verrà richiesto l'accesso sudo (usa la password del tuo utente, non quella di root)."

    case "$FAMILY" in
        arch)
            PACKAGES=("ffmpeg" "python")
            
            # Check what needs to be installed
            TO_INSTALL=()
            for pkg in "${PACKAGES[@]}"; do
                if ! pacman -Q "$pkg" &>/dev/null; then
                    TO_INSTALL+=("$pkg")
                fi
            done

            if [ ${#TO_INSTALL[@]} -gt 0 ]; then
                log_info "Installazione dei pacchetti mancanti via pacman: ${TO_INSTALL[*]}"
                sudo pacman -S --needed --noconfirm "${TO_INSTALL[@]}"
            else
                log_success "Tutti i pacchetti Arch necessari sono già installati."
            fi
            ;;

        debian)
            PACKAGES=("ffmpeg" "python3" "python3-venv" "python3-pip" "build-essential")

            log_info "Aggiornamento indici apt..."
            sudo apt-get update -y
            log_info "Installazione pacchetti via apt: ${PACKAGES[*]}"
            sudo apt-get install -y "${PACKAGES[@]}"
            ;;

        fedora)
            PACKAGES=("ffmpeg" "python3" "python3-pip")

            log_info "Installazione pacchetti via dnf: ${PACKAGES[*]}"
            sudo dnf install -y "${PACKAGES[@]}"
            ;;

        *)
            log_warn "Distribuzione generica: verifica che ffmpeg e python3 siano presenti."
            ;;
    esac
}

# ------------------------------------------------------------------------------
# 3. Python Virtual Environment & PIP Packages
# ------------------------------------------------------------------------------
setup_python_env() {
    echo ""
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    VENV_DIR="${SCRIPT_DIR}/.venv"
    REQ_FILE="${SCRIPT_DIR}/blindcue/requirements.txt"

    log_info "Configuring Python virtual environment at ${VENV_DIR}..."

    if [ ! -d "$VENV_DIR" ]; then
        python3 -m venv "$VENV_DIR"
        log_success "Created Python virtual environment in .venv"
    else
        log_info "Existing virtual environment found in .venv"
    fi

    # Activate environment
    # shellcheck disable=SC1091
    source "${VENV_DIR}/bin/activate"

    log_info "Upgrading pip, setuptools, and wheel..."
    python3 -m pip install --upgrade pip setuptools wheel --quiet

    if [ -f "$REQ_FILE" ]; then
        log_info "Installing Python dependencies from ${REQ_FILE}..."
        python3 -m pip install -r "$REQ_FILE"
        log_success "Python dependencies installed successfully."
    else
        log_error "Requirements file not found at ${REQ_FILE}!"
        exit 1
    fi
}

# ------------------------------------------------------------------------------
# 4. Automated Sanity Verification & Diagnostics
# ------------------------------------------------------------------------------
verify_installation() {
    echo ""
    log_info "Running automated system diagnostics and verification tests..."

    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    # shellcheck disable=SC1091
    source "${SCRIPT_DIR}/.venv/bin/activate"

    # Test Python dependencies
    log_info "Testing Python modules..."
    python3 - << 'EOF'
import sys

# Test PySide6 & QtMultimedia (Native Wayland)
try:
    import PySide6
    from PySide6.QtCore import qVersion
    from PySide6.QtMultimedia import QMediaPlayer
    from PySide6.QtMultimediaWidgets import QVideoWidget
    print(f"  [✓] PySide6 and QtMultimedia loaded successfully (Qt {qVersion()})")
except Exception as e:
    print(f"  [✗] Failed to import PySide6 / QtMultimedia: {e}", file=sys.stderr)
    sys.exit(1)

# Test NumPy
try:
    import numpy as np
    a = np.zeros((10,), dtype=np.float32)
    print("  [✓] NumPy loaded and verified")
except Exception as e:
    print(f"  [✗] Failed to import NumPy: {e}", file=sys.stderr)
    sys.exit(1)
EOF
    log_success "All Python modules and native Qt libraries verified."

    # Test FFmpeg & FFprobe
    echo ""
    log_info "Testing FFmpeg & FFprobe availability..."
    if command -v ffmpeg &>/dev/null && command -v ffprobe &>/dev/null; then
        FF_VER=$(ffmpeg -version | head -n 1)
        log_success "FFmpeg available: ${FF_VER}"
    else
        log_error "FFmpeg or FFprobe executable not found in PATH!"
        exit 1
    fi

    # Check Hardware Video Acceleration (DRI/DRM VA-API)
    echo ""
    log_info "Testing Hardware Acceleration (/dev/dri)..."
    if [ -e "/dev/dri/renderD128" ]; then
        log_success "Direct Rendering DRI/DRM device detected (/dev/dri/renderD128) - Hardware Acceleration active!"
    else
        log_info "DRI direct rendering device not found - Mesa software rendering will be used."
    fi

    # Multi-Monitor Check
    echo ""
    log_info "Checking connected monitors..."
    python3 - << 'EOF'
from PySide6.QtWidgets import QApplication
import sys

app = QApplication(sys.argv)
screens = app.screens()
primary = app.primaryScreen()
print(f"  • Detected {len(screens)} screen(s):")
for i, s in enumerate(screens):
    geo = s.geometry()
    is_p = " [PRIMARY - Regia]" if s == primary else " [EXTERNAL - Output Window]"
    print(f"    - Screen {i}: '{s.name()}' ({geo.width()}x{geo.height()}){is_p}")

if len(screens) < 2:
    print("  ℹ Single monitor detected: BlindCue will run both Regia and Output on the same display for testing.")
else:
    print("  ✓ Multi-monitor setup confirmed: Output window will automatically attach to screen 1.")
EOF
}

# ------------------------------------------------------------------------------
# 5. Create Convenient Launchers & Desktop Entry
# ------------------------------------------------------------------------------
create_launchers() {
    echo ""
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    RUN_SCRIPT="${SCRIPT_DIR}/run.sh"
    LOGO_PATH="${SCRIPT_DIR}/immagini di progetto/BlindCue-logo.jpeg"
    DESKTOP_ENTRY="${SCRIPT_DIR}/blindcue.desktop"

    log_info "Generating executable runner script at ${RUN_SCRIPT}..."
    cat << EOF > "$RUN_SCRIPT"
#!/usr/bin/env bash
# BlindCue Launch Script
DIR="\$(cd "\$(dirname "\${BASH_SOURCE[0]}")" && pwd)"
source "\${DIR}/.venv/bin/activate"
exec python3 "\${DIR}/blindcue/main.py" "\$@"
EOF
    chmod +x "$RUN_SCRIPT"
    log_success "Created ${RUN_SCRIPT}"

    log_info "Generating Desktop Shortcut at ${DESKTOP_ENTRY}..."
    cat << EOF > "$DESKTOP_ENTRY"
[Desktop Entry]
Name=BlindCue
Comment=Minimal Failsafe Live Multimedia Cue Player
Exec=${RUN_SCRIPT}
Icon=${LOGO_PATH}
Terminal=false
Type=Application
Categories=AudioVideo;Player;AudioVideoEditing;
StartupNotify=true
EOF
    chmod +x "$DESKTOP_ENTRY"
    log_success "Created ${DESKTOP_ENTRY}"

    # Prompt user to copy to ~/.local/share/applications/ if desired
    LOCAL_APP_DIR="${HOME}/.local/share/applications"
    if [ -d "$LOCAL_APP_DIR" ]; then
        cp "$DESKTOP_ENTRY" "${LOCAL_APP_DIR}/blindcue.desktop"
        log_success "Installed desktop icon into application launcher (${LOCAL_APP_DIR}/blindcue.desktop)"
    fi
}

# ------------------------------------------------------------------------------
# Main Execution Flow
# ------------------------------------------------------------------------------
main() {
    NO_SUDO=false
    for arg in "$@"; do
        if [ "$arg" = "--no-sudo" ] || [ "$arg" = "--user" ]; then
            NO_SUDO=true
        fi
    done

    print_header
    detect_distribution
    install_system_packages
    setup_python_env
    verify_installation
    create_launchers

    echo ""
    echo -e "${CLR_GREEN}${CLR_BOLD}"
    echo "======================================================================"
    echo "            🎉 BlindCue INSTALLAZIONE COMPLETATA CON SUCCESSO!         "
    echo "======================================================================"
    echo -e "${CLR_RESET}"
    echo -e "Per avviare BlindCue puoi usare uno dei seguenti metodi:"
    echo -e "  1. Esegui il comodo script:     ${CLR_CYAN}./run.sh${CLR_RESET}"
    echo -e "  2. Con selezione schermo:       ${CLR_CYAN}./run.sh --output-screen 1${CLR_RESET}"
    echo -e "  3. Dal menu applicazioni Linux: Cerca 'BlindCue' nella dashboard"
    echo ""
}

main "$@"

