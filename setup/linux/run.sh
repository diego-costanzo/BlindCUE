#!/usr/bin/env bash
# ==============================================================================
# BlindCue — avvio su Linux
#
# Usa l'installazione in ${XDG_DATA_HOME:-$HOME/.local/share}/blindcue.
# Se non è ancora installata, spiega come fare invece di fallire in silenzio.
# ==============================================================================

set -euo pipefail

INSTALL_DIR="${BLINDCUE_PREFIX:-${XDG_DATA_HOME:-$HOME/.local/share}/blindcue}"
RUNNER="${INSTALL_DIR}/run.sh"

if [ ! -x "$RUNNER" ]; then
    echo "BlindCue non risulta installato in: ${INSTALL_DIR}"
    echo ""
    echo "Per installarlo esegui:"
    echo "  $(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/setup.py"
    echo "oppure:"
    echo "  ./setup/linux/install.sh"
    exit 1
fi

exec "$RUNNER" "$@"
