#!/usr/bin/env bash
# ==============================================================================
# BlindCue — avvio su macOS
#
# Avvia il bundle installato in ~/Applications/BlindCue.app.
# ==============================================================================

set -uo pipefail

if [ -n "${BLINDCUE_PREFIX:-}" ]; then
    APP_BUNDLE="${BLINDCUE_PREFIX}"
else
    APP_BUNDLE="${HOME}/Applications/BlindCue.app"
fi

BIN="${APP_BUNDLE}/Contents/MacOS/BlindCue"

if [ ! -x "$BIN" ]; then
    echo "BlindCue non risulta installato in: ${APP_BUNDLE}"
    echo ""
    echo "Per installarlo esegui:"
    echo "  $(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/setup.py"
    echo "oppure:"
    echo "  ./setup/macos/install.command"
    exit 1
fi

exec "$BIN" "$@"
