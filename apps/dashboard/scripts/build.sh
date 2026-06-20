#!/bin/bash
# Production build wrapper for Next.js dashboard.
#
# Uses Turbopack (the Next.js default), with a narrow webpack retry for known
# Turbopack build-time races/invariants that otherwise block local verification.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SCRIPT_PATH="$SCRIPT_DIR/$(basename "$0")"
DASHBOARD_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
NEXT_DIR="$DASHBOARD_DIR/.next"
TSBUILDINFO_PATH="$DASHBOARD_DIR/tsconfig.tsbuildinfo"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
export AUGUR_ROOT="$PROJECT_ROOT"
export NODE_PATH="$PROJECT_ROOT/apps/dashboard/node_modules${NODE_PATH:+:$NODE_PATH}"
export AUGUR_CACHE_DIR="${AUGUR_CACHE_DIR:-$(AUGUR_ROOT="$AUGUR_ROOT" python3 - <<'PY'
import sys
from pathlib import Path

root = Path(__import__("os").environ["AUGUR_ROOT"])
if str(root) not in sys.path:
    sys.path.insert(0, str(root))
from src.config.paths import get_cache_dir

print(get_cache_dir())
PY
)}"
EXTERNAL_DASHBOARD_DIR="$AUGUR_CACHE_DIR/dashboard"
EXTERNAL_NEXT_DIR="$AUGUR_CACHE_DIR/dashboard/next"
EXTERNAL_NODE_MODULES_LINK="$EXTERNAL_DASHBOARD_DIR/node_modules"
ROOT_NEXT_DIR="$PROJECT_ROOT/.next"

if [ "${AUGUR_BUILD_LOCK_HELD:-0}" != "1" ]; then
  export AUGUR_BUILD_LOCK_HELD=1
  exec "$SCRIPT_DIR/build-lock.sh" "$SCRIPT_PATH" "$@"
fi

cd "$DASHBOARD_DIR"

mkdir -p "$EXTERNAL_DASHBOARD_DIR" "$EXTERNAL_NEXT_DIR"
if [ -L "$EXTERNAL_NODE_MODULES_LINK" ] && [ "$(readlink "$EXTERNAL_NODE_MODULES_LINK")" != "$DASHBOARD_DIR/node_modules" ]; then
  rm -f "$EXTERNAL_NODE_MODULES_LINK"
fi
if [ -e "$EXTERNAL_NODE_MODULES_LINK" ] && [ ! -L "$EXTERNAL_NODE_MODULES_LINK" ]; then
  rm -rf "$EXTERNAL_NODE_MODULES_LINK"
fi
if [ ! -e "$EXTERNAL_NODE_MODULES_LINK" ]; then
  ln -s "$DASHBOARD_DIR/node_modules" "$EXTERNAL_NODE_MODULES_LINK"
fi
if [ -L "$NEXT_DIR" ] && [ "$(readlink "$NEXT_DIR")" != "$EXTERNAL_NEXT_DIR" ]; then
  rm -f "$NEXT_DIR"
fi
if [ -d "$NEXT_DIR" ] && [ ! -L "$NEXT_DIR" ]; then
  rm -rf "$NEXT_DIR"
fi
if [ ! -e "$NEXT_DIR" ]; then
  ln -s "$EXTERNAL_NEXT_DIR" "$NEXT_DIR"
fi
if [ -d "$ROOT_NEXT_DIR" ] && [ ! -L "$ROOT_NEXT_DIR" ]; then
  rm -rf "$ROOT_NEXT_DIR"
fi
if [ -L "$TSBUILDINFO_PATH" ] && [ ! -e "$TSBUILDINFO_PATH" ]; then
  rm -f "$TSBUILDINFO_PATH"
fi

remove_next_dir() {
  if [ ! -d "$EXTERNAL_NEXT_DIR" ]; then
    return 0
  fi
  node -e '
    const fs = require("fs");
    const dir = process.argv[1];
    try {
      fs.rmSync(dir, { recursive: true, force: true, maxRetries: 20, retryDelay: 100 });
    } catch (err) {
      console.error("Failed to remove .next directory:", err);
      process.exit(1);
    }
  ' "$EXTERNAL_NEXT_DIR"
  mkdir -p "$EXTERNAL_NEXT_DIR"
}

# Kill any running dev server to avoid filesystem lock contention on .next.
DEV_PIDS=$(pgrep -f "next dev.*--turbopack" 2>/dev/null || true)
if [ -n "$DEV_PIDS" ]; then
  echo "Stopping running dev server (PIDs: $DEV_PIDS)..."
  echo "$DEV_PIDS" | xargs kill 2>/dev/null || true
  sleep 1
fi

# The plugin watcher belongs to a dev session. If it survives after dev exits,
# it can remount plugins and clear .next during this production build.
WATCHER_PIDS=$(pgrep -f "mount-plugins\\.mjs --watch" 2>/dev/null || true)
if [ -n "$WATCHER_PIDS" ]; then
  echo "Stopping plugin watcher (PIDs: $WATCHER_PIDS)..."
  echo "$WATCHER_PIDS" | xargs kill 2>/dev/null || true
  sleep 1
fi

remove_next_dir

# pnpm exec bypasses package lifecycle hooks, so build.sh must refresh the
# ignored runtime artifacts it imports before invoking next build.
pnpm run ensure-generated

# Large projects may need extra heap during build.
if [[ "${NODE_OPTIONS:-}" != *"--max-old-space-size="* ]]; then
  if [ -n "${NODE_OPTIONS:-}" ]; then
    export NODE_OPTIONS="${NODE_OPTIONS} --max-old-space-size=8192"
  else
    export NODE_OPTIONS="--max-old-space-size=8192"
  fi
fi

BUILD_LOG=$(mktemp -t augur-next-build.XXXXXX)

is_turbopack_manifest_race() {
  local log_file="$1"
  grep -Eq "ENOENT: no such file or directory, open[[:space:]]+'.*/\\.next/(required-server-files\\.json|server/pages-manifest\\.json|static/.*/_buildManifest\\.js\\.tmp|turbopack)" "$log_file"
}

is_turbopack_prerender_invariant() {
  local log_file="$1"
  grep -Fq "Expected workStore to be initialized" "$log_file" \
    && grep -Fq "Export encountered an error on /_global-error/page" "$log_file"
}

if ! pnpm exec next build 2>&1 | tee "$BUILD_LOG"; then
  if is_turbopack_manifest_race "$BUILD_LOG"; then
    echo "Detected Turbopack manifest race. Retrying production build with webpack..."
    remove_next_dir
    pnpm exec next build --webpack
  elif is_turbopack_prerender_invariant "$BUILD_LOG"; then
    echo "Detected Turbopack prerender invariant. Retrying production build with webpack..."
    remove_next_dir
    pnpm exec next build --webpack
  else
    exit 1
  fi
fi
