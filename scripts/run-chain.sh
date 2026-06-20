#!/usr/bin/env bash
# Run an Augur chain in headless mode via Claude Code CLI.
# Usage: scripts/run-chain.sh <chain-name> [--resume <session-id>]
#
# Examples:
#   scripts/run-chain.sh test-nightly
#   scripts/run-chain.sh ops-audit --resume abc123
set -euo pipefail

CHAIN_NAME="${1:?Usage: run-chain.sh <chain-name> [--resume <session-id>]}"
shift

RESUME_FLAG=""
if [[ "${1:-}" == "--resume" ]]; then
  SESSION_ID="${2:?--resume requires a session ID}"
  RESUME_FLAG="--resume $SESSION_ID"
  shift 2
fi

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Determine Claude CLI path
CLAUDE_CLI="${CLAUDE_CLI:-claude}"

if [[ -n "$RESUME_FLAG" ]]; then
  exec "$CLAUDE_CLI" $RESUME_FLAG \
    --print \
    --output-format json \
    -p "Continue executing chain: $CHAIN_NAME"
else
  exec "$CLAUDE_CLI" \
    --print \
    --output-format json \
    -p "Execute chain: /$CHAIN_NAME"
fi
