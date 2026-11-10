#!/usr/bin/env bash
# BlindCue Launch Script
set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -f "${DIR}/.venv/bin/activate" ]; then
    # shellcheck disable=SC1091
    source "${DIR}/.venv/bin/activate"
fi

export LC_NUMERIC=C

exec python3 "${DIR}/blindcue/main.py" "$@"

