#!/usr/bin/env bash
# ==============================================================================
# BlindCue — avvio dal codice sorgente (uso interno / sviluppo)
#
# Per l'uso normale BlindCue si installa con `python3 setup.py` e si avvia
# dall'icona di sistema. Questo script serve a chi modifica il codice e vuole
# vedere subito le modifiche, senza reinstallare.
# ==============================================================================

set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -x "${DIR}/.venv/bin/python" ]; then
    exec "${DIR}/.venv/bin/python" "${DIR}/blindcue/main.py" "$@"
fi

if ! python3 -c "import PySide6" 2>/dev/null; then
    echo "Manca l'ambiente Python di BlindCue."
    echo ""
    echo "Per installare BlindCue:      python3 setup.py"
    echo "Per lo sviluppo, crea il venv: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
    exit 1
fi

export LC_NUMERIC=C
exec python3 "${DIR}/blindcue/main.py" "$@"
