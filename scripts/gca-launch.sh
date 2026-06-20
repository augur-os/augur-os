#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ATTEMPTED_RUNTIMES=("$REPO_ROOT/.venv/bin/python" "$REPO_ROOT/.venv/Scripts/python.exe" "uv run python" "python3")

if [[ -x "$REPO_ROOT/.venv/bin/python" ]]; then
    PYTHON_CMD=("$REPO_ROOT/.venv/bin/python")
elif [[ -x "$REPO_ROOT/.venv/Scripts/python.exe" ]]; then
    PYTHON_CMD=("$REPO_ROOT/.venv/Scripts/python.exe")
elif command -v uv >/dev/null 2>&1; then
    PYTHON_CMD=(uv run python)
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD=(python3)
else
    echo "Error: could not find Python for Augur launcher from repo root: $REPO_ROOT" >&2
    echo "Attempted: ${ATTEMPTED_RUNTIMES[*]}" >&2
    exit 1
fi

export PYTHONPATH="$REPO_ROOT${PYTHONPATH:+:$PYTHONPATH}"
cd "$REPO_ROOT"
exec "${PYTHON_CMD[@]}" -m src.scripts.agent_launch --client copilot "$@"
