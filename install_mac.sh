#!/usr/bin/env bash
# ==============================================================================
#  BlindCue — Setup e Installazione Automatica per macOS (Apple Silicon / Intel)
# ==============================================================================

set -euo pipefail

CLR_RESET="\033[0m"
CLR_BOLD="\033[1m"
CLR_GREEN="\033[1;32m"
CLR_CYAN="\033[1;36m"
CLR_YELLOW="\033[1;33m"

echo -e "${CLR_CYAN}${CLR_BOLD}"
echo "======================================================================"
echo "          🎬 BlindCue — Live Multimedia Cue Player (macOS Setup)      "
echo "======================================================================"
echo -e "${CLR_RESET}"

# 1. Verifica Python 3
if ! command -v python3 &>/dev/null; then
    echo -e "${CLR_YELLOW}[ATTENZIONE] Python 3 non trovato. Installalo tramite Homebrew (brew install python) o da python.org.${CLR_RESET}"
    exit 1
fi

# 2. Verifica FFmpeg (consigliato per decodifica video e analisi loudness)
if ! command -v ffmpeg &>/dev/null; then
    if command -v brew &>/dev/null; then
        echo -e "${CLR_CYAN}[INFO] Installazione automatica di FFmpeg tramite Homebrew...${CLR_RESET}"
        brew install ffmpeg || true
    else
        echo -e "${CLR_YELLOW}[AVVISO] FFmpeg non trovato. Ti consigliamo di installarlo (es. 'brew install ffmpeg') per supportare tutti i formati multimediali.${CLR_RESET}"
    fi
fi

# 3. Creazione e configurazione Virtual Environment
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo -e "${CLR_CYAN}[INFO] Configurazione virtual environment in ${DIR}/.venv...${CLR_RESET}"
if [ ! -d "${DIR}/.venv" ]; then
    python3 -m venv "${DIR}/.venv"
fi

source "${DIR}/.venv/bin/activate"
pip install --upgrade pip --quiet
pip install -r "${DIR}/requirements.txt"

chmod +x "${DIR}/run.sh"

echo ""
echo -e "${CLR_GREEN}${CLR_BOLD}"
echo "======================================================================"
echo "    [✓] Installazione completata con successo su macOS!"
echo "    Per avviare il software esegui semplicemente: ./run.sh"
echo "======================================================================"
echo -e "${CLR_RESET}"

