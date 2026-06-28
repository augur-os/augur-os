#!/bin/bash
set -euo pipefail
# Start the Augur dashboard dev server with Turbopack.
#
# Environment Variables:
#   AUGUR_DEV_HUBS  - Comma-separated hub IDs to mount (e.g., "professional,ai").
#                     When set, only these hubs + shell hubs are mounted, reducing
#                     Turbopack's page count from ~165 to ~10-25. Unset = mount all.
#   AUGUR_ACTIVE_ERROR_WATCH - Set to 1 to force active error monitoring,
#                     0 to disable it. Defaults to enabled only for TTY sessions.
#   NODE_OPTIONS    - Additional Node.js flags (heap limit is auto-appended below).
#
# Cache behavior:
#   - Clears .next/ if Turbopack PANIC marker or corruption is detected.
#   - Clears .next/ if Turbopack cache exceeds 512MB (GC thrashing prevention).

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
DASHBOARD_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$DASHBOARD_DIR"

# Production serve mode (ADR-787). The .mjs entry delegates here on macOS/Linux,
# so this POSIX launcher — not just the Windows branch — must honor --prod.
# Without it, the main :3000 dashboard always ran `next dev` and every start
# wiped .next/BUILD_ID, stranding the daemon supervisor's reboot-survival ensure
# ("No production build — skipping dashboard ensure"). In prod we preserve the
# freshly-built .next (AUGUR_PROD_SERVE=1 → clearNextCache no-ops), skip the
# Turbopack dev cache management + dev watchers, and serve via `next start`.
AUGUR_PROD_MODE=0
for _arg in "$@"; do
    if [ "$_arg" = "--prod" ]; then
        AUGUR_PROD_MODE=1
        export AUGUR_PROD_SERVE=1
    fi
done

PREFLIGHT_ARGS=(--root "$PROJECT_ROOT" --profile dashboard --repair)
if [ "${AUGUR_INTERACTIVE:-0}" = "1" ]; then
    PREFLIGHT_ARGS+=(--interactive)
fi
PREFLIGHT_JSON="$(python3 "$PROJECT_ROOT/scripts/worktree_preflight.py" "${PREFLIGHT_ARGS[@]}")"

preflight_value() {
    printf '%s' "$PREFLIGHT_JSON" | python3 -c 'import json,sys; data=json.load(sys.stdin); value=data.get(sys.argv[1]); print("" if value is None else value)' "$1"
}

export AUGUR_ROOT="$(preflight_value project_root)"
export AUGUR_STATE="$(preflight_value runtime_dir)"
export AUGUR_RUNTIME="$(preflight_value runtime_dir)"
export AUGUR_PYTHON="$(preflight_value python_path)"
export MCP_PORT="$(preflight_value mcp_port)"
export AUGUR_MCP_CLIENT_ID="$(preflight_value mcp_client_id)"
INSTANCE_KIND="$(preflight_value instance_kind)"
if [ -z "$INSTANCE_KIND" ]; then
    LEGACY_WORKTREE="$(preflight_value worktree)"
    if [ "$LEGACY_WORKTREE" = "True" ] || [ "$LEGACY_WORKTREE" = "true" ] || [ "$LEGACY_WORKTREE" = "1" ]; then
        INSTANCE_KIND="worktree"
    else
        INSTANCE_KIND="main"
    fi
fi
export AUGUR_INSTANCE_ID="$(preflight_value instance_id)"
export AUGUR_INSTANCE_ID="${AUGUR_INSTANCE_ID:-$INSTANCE_KIND}"
export AUGUR_INSTANCE_KIND="$INSTANCE_KIND"
export AUGUR_BROWSER_MODE="$(preflight_value browser_mode)"
export AUGUR_HEAL_POLICY="$(preflight_value heal_policy)"
export AUGUR_VISIBILITY_POLICY="$(preflight_value visibility_policy)"
if [ "$INSTANCE_KIND" = "main" ]; then
    export AUGUR_BROWSER_MODE="${AUGUR_BROWSER_MODE:-visible_allowed}"
    export AUGUR_HEAL_POLICY="${AUGUR_HEAL_POLICY:-enabled}"
    export AUGUR_VISIBILITY_POLICY="${AUGUR_VISIBILITY_POLICY:-visible_allowed}"
elif [ "$INSTANCE_KIND" = "worktree" ]; then
    export AUGUR_BROWSER_MODE="${AUGUR_BROWSER_MODE:-headless_only}"
    export AUGUR_HEAL_POLICY="${AUGUR_HEAL_POLICY:-validation_only}"
    export AUGUR_VISIBILITY_POLICY="${AUGUR_VISIBILITY_POLICY:-no_visible_mutation}"
elif [ "$INSTANCE_KIND" = "isolated" ]; then
    export AUGUR_BROWSER_MODE="${AUGUR_BROWSER_MODE:-headless_only}"
    export AUGUR_HEAL_POLICY="${AUGUR_HEAL_POLICY:-disabled}"
    export AUGUR_VISIBILITY_POLICY="${AUGUR_VISIBILITY_POLICY:-no_visible_mutation}"
else
    echo "Error: unknown dashboard instance_kind: $INSTANCE_KIND" >&2
    exit 1
fi
export NEXT_PUBLIC_AUGUR_INSTANCE_ID="$AUGUR_INSTANCE_ID"
export NEXT_PUBLIC_AUGUR_INSTANCE_KIND="$AUGUR_INSTANCE_KIND"
export NEXT_PUBLIC_AUGUR_VISIBILITY_POLICY="$AUGUR_VISIBILITY_POLICY"
export AUGUR_DASHBOARD_INCLUDE_LOCAL_SKILLS="${AUGUR_DASHBOARD_INCLUDE_LOCAL_SKILLS:-1}"
INFERRED_DEV_HUBS="$(preflight_value dev_hubs)"
export PYTHONPATH="${AUGUR_ROOT}/src/mcp:${AUGUR_ROOT}${PYTHONPATH:+:${PYTHONPATH}}"
export NODE_PATH="$PROJECT_ROOT/apps/dashboard/node_modules${NODE_PATH:+:$NODE_PATH}"

if [ -z "${AUGUR_DEV_HUBS:-}" ] && [ -n "$INFERRED_DEV_HUBS" ]; then
    export AUGUR_DEV_HUBS="$INFERRED_DEV_HUBS"
    echo "Auto-focused worktree hubs: $AUGUR_DEV_HUBS"
fi

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

ALLOCATED_DASHBOARD_PORT="$(preflight_value dashboard_port)"
if [ "$INSTANCE_KIND" = "main" ]; then
    DASHBOARD_PORT="3000"
    WORKTREE_PORT=""
elif [ "$INSTANCE_KIND" = "worktree" ] || [ "$INSTANCE_KIND" = "isolated" ]; then
    if [ -z "$ALLOCATED_DASHBOARD_PORT" ] || [ "$ALLOCATED_DASHBOARD_PORT" = "3000" ]; then
        echo "Error: $INSTANCE_KIND dashboard instance requires an allocated dashboard_port other than 3000." >&2
        exit 1
    fi
    DASHBOARD_PORT="$ALLOCATED_DASHBOARD_PORT"
    WORKTREE_PORT="$DASHBOARD_PORT"
else
    echo "Error: unknown dashboard instance_kind: $INSTANCE_KIND" >&2
    exit 1
fi

ensure_dashboard_dependencies() {
    if [ -x "$DASHBOARD_DIR/node_modules/.bin/next" ]; then
        return 0
    fi

    echo "Dashboard dependencies are missing; installing with pnpm..."
    (cd "$DASHBOARD_DIR" && corepack pnpm install --frozen-lockfile)
}

ensure_dashboard_dependencies

# Run prebuild under build lock (prevents concurrent prebuild races)
echo "Running prebuild under build lock..."
"$SCRIPT_DIR/build-lock.sh" sh -c '
  echo "Compiling build scripts..."
  node scripts/build-scripts.mjs
  echo "Running setup scripts..."
  node scripts/dist/setup-mcp.mjs
  python3 scripts/generate_registry.py
  node scripts/dist/mount-plugins.mjs
  node scripts/dist/generate-block-registry.mjs
  node scripts/dist/generate-tab-registry.mjs
  node scripts/dist/generate-item-actions.mjs
'

# Check if next binary exists
if [ ! -f "./node_modules/.bin/next" ]; then
    echo "Error: 'next' binary not found. node_modules might be corrupted."
    echo "Run: pnpm install"
    exit 1
fi

stop_existing_dashboard_listener() {
    local port="$1"
    local pids
    pids=$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)
    if [ -z "$pids" ]; then
        return 0
    fi

    while IFS= read -r pid; do
        [ -n "$pid" ] || continue
        local command
        command=$(ps -p "$pid" -o command= 2>/dev/null || true)
        case "$command" in
            *"next dev"*|*"next-server"*|*"apps/dashboard"*)
                echo "Stopping stale dashboard listener on port $port (PID $pid)..."
                kill "$pid" 2>/dev/null || true
                ;;
        esac
    done <<EOF
$pids
EOF

    for _ in $(seq 1 40); do
        if ! lsof -tiTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
            return 0
        fi
        sleep 0.25
    done

    echo "Timed out waiting for dashboard listener on port $port to stop." >&2
    return 1
}

if [ -n "$WORKTREE_PORT" ]; then
    echo "$INSTANCE_KIND dashboard instance detected — using port $DASHBOARD_PORT"
fi
stop_existing_dashboard_listener "$DASHBOARD_PORT"

# Clear corrupted Turbopack cache if a previous run left a panic marker.
# TurbopackInternalError is a runtime cache issue — the only fix is clearing .next/.
NEXT_DIR="$DASHBOARD_DIR/.next"
MYPY_CACHE_DIR="$DASHBOARD_DIR/.mypy_cache"
TSBUILDINFO_PATH="$DASHBOARD_DIR/tsconfig.tsbuildinfo"
EXTERNAL_DASHBOARD_CACHE="$AUGUR_STATE/../cache/dashboard"
EXTERNAL_NEXT_DIR="$EXTERNAL_DASHBOARD_CACHE/next"
EXTERNAL_MYPY_CACHE_DIR="$EXTERNAL_DASHBOARD_CACHE/mypy"
EXTERNAL_TSBUILDINFO_PATH="$EXTERNAL_DASHBOARD_CACHE/tsconfig.tsbuildinfo"

mkdir -p "$EXTERNAL_NEXT_DIR" "$EXTERNAL_MYPY_CACHE_DIR"
# The .next external-cache symlink is a dev/turbopack convention. A prod build
# writes a REAL .next dir; re-imposing the symlink here rm -rf's that build (and
# its BUILD_ID) before `next start` can serve it. So leave a real .next alone in
# prod mode and serve it directly. (Dev still gets the symlink.)
if [ "$AUGUR_PROD_MODE" != "1" ]; then
    if [ -L "$NEXT_DIR" ] && [ "$(readlink "$NEXT_DIR")" != "$EXTERNAL_NEXT_DIR" ]; then
        rm -f "$NEXT_DIR"
    fi
    if [ -d "$NEXT_DIR" ] && [ ! -L "$NEXT_DIR" ]; then
        rm -rf "$NEXT_DIR"
    fi
    if [ ! -e "$NEXT_DIR" ]; then
        ln -s "$EXTERNAL_NEXT_DIR" "$NEXT_DIR"
    fi
fi
if [ -L "$MYPY_CACHE_DIR" ] && [ "$(readlink "$MYPY_CACHE_DIR")" != "$EXTERNAL_MYPY_CACHE_DIR" ]; then
    rm -f "$MYPY_CACHE_DIR"
fi
if [ -d "$MYPY_CACHE_DIR" ] && [ ! -L "$MYPY_CACHE_DIR" ]; then
    rm -rf "$MYPY_CACHE_DIR"
fi
if [ ! -e "$MYPY_CACHE_DIR" ]; then
    ln -s "$EXTERNAL_MYPY_CACHE_DIR" "$MYPY_CACHE_DIR"
fi
if [ -L "$TSBUILDINFO_PATH" ] && [ "$(readlink "$TSBUILDINFO_PATH")" != "$EXTERNAL_TSBUILDINFO_PATH" ]; then
    rm -f "$TSBUILDINFO_PATH"
fi
if [ -L "$TSBUILDINFO_PATH" ] && [ ! -e "$TSBUILDINFO_PATH" ]; then
    rm -f "$TSBUILDINFO_PATH"
fi
if [ -f "$TSBUILDINFO_PATH" ] && [ ! -L "$TSBUILDINFO_PATH" ]; then
    rm -f "$TSBUILDINFO_PATH"
fi
if [ ! -e "$TSBUILDINFO_PATH" ]; then
    ln -s "$EXTERNAL_TSBUILDINFO_PATH" "$TSBUILDINFO_PATH"
fi
SWC_DIR="$DASHBOARD_DIR/.swc"
CACHE_NAMESPACE="dashboard"
if [ -n "$WORKTREE_PORT" ]; then
    CACHE_INSTANCE_SLUG="$(printf '%s' "${AUGUR_INSTANCE_ID:-$INSTANCE_KIND-$WORKTREE_PORT}" | LC_ALL=C tr -c 'A-Za-z0-9._-' '-')"
    CACHE_INSTANCE_SLUG="${CACHE_INSTANCE_SLUG%-}"
    CACHE_INSTANCE_SLUG="${CACHE_INSTANCE_SLUG:-$WORKTREE_PORT}"
    CACHE_NAMESPACE="dashboard-worktree-$CACHE_INSTANCE_SLUG"
fi
EXTERNAL_DASHBOARD_DIR="$AUGUR_CACHE_DIR/$CACHE_NAMESPACE"
EXTERNAL_NEXT_DIR="$EXTERNAL_DASHBOARD_DIR/next"
EXTERNAL_SWC_DIR="$EXTERNAL_DASHBOARD_DIR/swc"
EXTERNAL_NODE_MODULES_LINK="$EXTERNAL_DASHBOARD_DIR/node_modules"
ROOT_NEXT_DIR="$PROJECT_ROOT/.next"
REPO_RUNTIME_DIR="$PROJECT_ROOT/runtime"

mkdir -p "$EXTERNAL_DASHBOARD_DIR" "$EXTERNAL_NEXT_DIR" "$EXTERNAL_SWC_DIR"

if [ -L "$EXTERNAL_NODE_MODULES_LINK" ] && [ "$(readlink "$EXTERNAL_NODE_MODULES_LINK")" != "$DASHBOARD_DIR/node_modules" ]; then
    rm -f "$EXTERNAL_NODE_MODULES_LINK"
fi

if [ -e "$EXTERNAL_NODE_MODULES_LINK" ] && [ ! -L "$EXTERNAL_NODE_MODULES_LINK" ]; then
    rm -rf "$EXTERNAL_NODE_MODULES_LINK"
fi

if [ ! -e "$EXTERNAL_NODE_MODULES_LINK" ]; then
    ln -s "$DASHBOARD_DIR/node_modules" "$EXTERNAL_NODE_MODULES_LINK"
fi

# Second .next rewiring pass (worktree-namespaced external dir) — same hazard as
# the first; skip in prod so the real built .next survives to be served.
if [ "$AUGUR_PROD_MODE" != "1" ]; then
    if [ -L "$NEXT_DIR" ] && [ "$(readlink "$NEXT_DIR")" != "$EXTERNAL_NEXT_DIR" ]; then
        rm -f "$NEXT_DIR"
    fi

    if [ -d "$NEXT_DIR" ] && [ ! -L "$NEXT_DIR" ]; then
        rm -rf "$NEXT_DIR"
    fi

    if [ ! -e "$NEXT_DIR" ]; then
        ln -s "$EXTERNAL_NEXT_DIR" "$NEXT_DIR"
    fi
fi

if [ -L "$SWC_DIR" ] && [ "$(readlink "$SWC_DIR")" != "$EXTERNAL_SWC_DIR" ]; then
    rm -f "$SWC_DIR"
fi

if [ -d "$SWC_DIR" ] && [ ! -L "$SWC_DIR" ]; then
    rm -rf "$SWC_DIR"
fi

if [ ! -e "$SWC_DIR" ]; then
    ln -s "$EXTERNAL_SWC_DIR" "$SWC_DIR"
fi

if [ -d "$ROOT_NEXT_DIR" ] && [ ! -L "$ROOT_NEXT_DIR" ]; then
    rm -rf "$ROOT_NEXT_DIR"
fi

if [ -d "$REPO_RUNTIME_DIR" ] && [ ! -L "$REPO_RUNTIME_DIR" ]; then
    rm -rf "$REPO_RUNTIME_DIR"
fi

# Turbopack dev-cache management — dev only. In prod serve these rm -rf the very
# .next/BUILD_ID we are about to serve, so they are skipped entirely.
if [ "$AUGUR_PROD_MODE" != "1" ]; then
    TURBOPACK_PANIC="$EXTERNAL_NEXT_DIR/dev/cache/turbopack/PANIC"
    if [ -f "$TURBOPACK_PANIC" ] || grep -rql "TurbopackInternalError" "$EXTERNAL_NEXT_DIR/dev/cache/turbopack/*/LOG" 2>/dev/null; then
        echo "Turbopack cache corrupted — clearing .next/ directory..."
        rm -rf "$EXTERNAL_NEXT_DIR"
        mkdir -p "$EXTERNAL_NEXT_DIR"
    fi

    if grep -rql "MODULE_UNPARSABLE" "$EXTERNAL_NEXT_DIR/dev/server" 2>/dev/null; then
        echo "Turbopack server cache corrupted — clearing .next/ directory..."
        rm -rf "$EXTERNAL_NEXT_DIR"
        mkdir -p "$EXTERNAL_NEXT_DIR"
    fi

    # Turbopack filesystem cache grows unbounded (2+ GB observed for 134 pages).
    # Clear if it exceeds 1GB to prevent disk bloat and GC thrashing.
    # This is safe — Turbopack recompiles lazily on next page visit.
    TURBOPACK_CACHE="$EXTERNAL_NEXT_DIR/dev/cache"
    if [ -d "$TURBOPACK_CACHE" ]; then
        CACHE_SIZE_KB=$(du -sk "$TURBOPACK_CACHE" 2>/dev/null | cut -f1)
        if [ "${CACHE_SIZE_KB:-0}" -gt 1048576 ]; then
            echo "Turbopack cache exceeds 1GB (${CACHE_SIZE_KB}KB) — clearing..."
            rm -rf "$TURBOPACK_CACHE"
        fi
    fi

    # Ensure Turbopack cache directory exists to prevent SST write failures.
    # Turbopack expects .next/dev/cache/turbopack/ to exist; if it's missing
    # (e.g., partial cleanup or race condition), writes fail with os error 2.
    mkdir -p "$EXTERNAL_NEXT_DIR/dev/cache/turbopack"
fi

# Force Turbopack's mimalloc allocator to return unused pages to OS immediately.
# Without this, mimalloc retains freed memory in arenas indefinitely, causing
# RSS to stay at peak even after GC. PURGE_DELAY=0 purges on free.
export MIMALLOC_PURGE_DELAY=0
export MIMALLOC_ARENA_EAGER_COMMIT=0

# Cap Node.js heap to force earlier garbage collection during dev.
# Default to 4096MB to avoid runaway RSS in all-hub sessions, but raise the
# ceiling for worktrees: even a narrowed hub graph needs more than 8GB
# old-space during sustained /brain + MCP usage, and Next.js restarts the dev
# server once used heap crosses 80% of the configured limit.
# - worktree default: 16384MB
# - focused non-worktree default: 12288MB
# - all-hub/default session: 4096MB
# --max-semi-space-size: raises young-gen from 8MB to 64MB, reducing
#   minor GC frequency during heavy Turbopack module churn.
# NEXT_DISABLE_MEM_OVERRIDE: prevents Next.js from overriding our heap cap.
#   Without this, next-dev.js auto-sets max-old-space-size to 50% of total
#   system RAM (~8GB on 16GB), ignoring our NODE_OPTIONS value entirely.
export NEXT_DISABLE_MEM_OVERRIDE=1
NODE_OLD_SPACE_MB="${AUGUR_NODE_OLD_SPACE_MB:-4096}"
WORKTREE_NODE_OLD_SPACE_MB="${AUGUR_WORKTREE_NODE_OLD_SPACE_MB:-16384}"
FOCUSED_NODE_OLD_SPACE_MB="${AUGUR_FOCUSED_NODE_OLD_SPACE_MB:-12288}"
if [ -n "$WORKTREE_PORT" ] && [ "$NODE_OLD_SPACE_MB" -lt "$WORKTREE_NODE_OLD_SPACE_MB" ]; then
    NODE_OLD_SPACE_MB="$WORKTREE_NODE_OLD_SPACE_MB"
elif [ -n "${AUGUR_DEV_HUBS:-}" ] && [ "$NODE_OLD_SPACE_MB" -lt "$FOCUSED_NODE_OLD_SPACE_MB" ]; then
    NODE_OLD_SPACE_MB="$FOCUSED_NODE_OLD_SPACE_MB"
fi

# Clamp the selected heap cap to a safe fraction of physical RAM so the dev
# server RESTARTS (Next.js 80%-of-limit safety) instead of OOM-rebooting the
# machine on low-RAM hosts. See docs/superpowers/plans/2026-06-25-dashboard-dev-oom-fix.md
# shellcheck source=lib/heap-clamp.sh
source "$SCRIPT_DIR/lib/heap-clamp.sh"
augur_clamp_heap

export NODE_OPTIONS="${NODE_OPTIONS:+$NODE_OPTIONS }--max-old-space-size=${NODE_OLD_SPACE_MB} --max-semi-space-size=64"

RELOAD_LOCK_FILE="$AUGUR_RUNTIME/locks/dashboard_reload.lock"
LOCK_RELEASE_PID=""

release_reload_lock_when_ready() {
    if [ ! -f "$RELOAD_LOCK_FILE" ]; then
        return 0
    fi

    (
        for _ in $(seq 1 180); do
            if [ ! -f "$RELOAD_LOCK_FILE" ]; then
                exit 0
            fi
            if python3 - "$DASHBOARD_PORT" <<'PY'
import socket
import sys

sock = socket.socket()
sock.settimeout(0.5)
try:
    sock.connect(("127.0.0.1", int(sys.argv[1])))
except OSError:
    raise SystemExit(1)
else:
    raise SystemExit(0)
finally:
    sock.close()
PY
            then
                rm -f "$RELOAD_LOCK_FILE"
                echo "Released reload lock after dashboard became reachable."
                exit 0
            fi
            sleep 1
        done
    ) &
    LOCK_RELEASE_PID=$!
}

WATCHER_PID=""
ACTIVE_ERROR_WATCH_PID=""
PROD_MARKER=""
cleanup() {
    kill "${WATCHER_PID:-}" "${ACTIVE_ERROR_WATCH_PID:-}" "${LOCK_RELEASE_PID:-}" 2>/dev/null || true
}
on_stop_signal() {
    # Remove the prod-managed marker ONLY on an INTENTIONAL stop (SIGTERM/SIGINT
    # from cleanup_processes or the user). A server CRASH instead makes `next
    # start` return non-zero and the shell exit normally (EXIT trap, marker kept),
    # so the supervisor re-heals it. The marker is the crash-vs-stop signal —
    # removing it here means "do not resurrect"; a SIGKILL/reboot skips this and
    # leaves the marker so the supervisor brings :3000 back. See _ensure_prod_dashboard.
    [ -n "${PROD_MARKER:-}" ] && rm -f "$PROD_MARKER" 2>/dev/null
    cleanup
    exit 143
}

# Dev-only watchers (live plugin re-mount + error-stream tail) make no sense for
# a fixed production bundle, and the --watch mount would re-clear .next. Skip in prod.
if [ "$AUGUR_PROD_MODE" != "1" ]; then
    # Start plugin watcher in background (re-mounts + regenerates tabs on page changes)
    echo "Starting plugin watcher..."
    node scripts/dist/mount-plugins.mjs --watch &
    WATCHER_PID=$!

    ACTIVE_ERROR_WATCH="${AUGUR_ACTIVE_ERROR_WATCH:-auto}"
    if [ "$ACTIVE_ERROR_WATCH" = "1" ] || { [ "$ACTIVE_ERROR_WATCH" = "auto" ] && [ -t 1 ]; }; then
        echo "Starting active error watcher..."
        python3 "$SCRIPT_DIR/watch_error_streams.py" < /dev/null &
        ACTIVE_ERROR_WATCH_PID=$!
    fi
fi

release_reload_lock_when_ready
trap cleanup EXIT
trap on_stop_signal TERM INT

# Production serve (ADR-787): serve the prebuilt bundle via `next start`. The
# build (.next/BUILD_ID) is produced by the build:safe step in `pnpm prod` BEFORE
# this runs; we never build or fall back to dev here — a missing build is a hard
# error so the daemon's reboot-survival ensure can detect + report it instead of
# silently mounting dev on :3000.
if [ "$AUGUR_PROD_MODE" = "1" ]; then
    if [ ! -f ".next/BUILD_ID" ]; then
        echo "[start-dev] No production build found (.next/BUILD_ID missing)." >&2
        echo "[start-dev] Run 'pnpm run build:safe' first, or use 'pnpm prod'." >&2
        exit 1
    fi
    export NODE_ENV=production
    # Write the prod-managed marker (ADR-787): tells the daemon a prod server is
    # meant to own :3000. cleanup() removes it on clean exit; a crash leaves it,
    # so the supervisor's periodic ensure can distinguish a crash from a stop.
    # NOT exec'd, so the EXIT trap fires and removes the marker on a clean stop.
    if [ -n "${AUGUR_STATE:-}" ]; then
        PROD_MARKER="$AUGUR_STATE/dashboard.prod_managed"
        mkdir -p "$AUGUR_STATE" 2>/dev/null || true
        printf '%s\n%s\n' "$$" "$(date +%s)" > "$PROD_MARKER" 2>/dev/null || true
    fi
    echo "Starting production server (next start) on port ${DASHBOARD_PORT}..."
    ./node_modules/.bin/next start --port "$DASHBOARD_PORT"
    exit $?
fi

# Dev server runs unlocked (long-lived, HMR handles file changes)
echo "Starting Next.js..."
if [ -n "$WORKTREE_PORT" ]; then
    ./node_modules/.bin/next dev --turbopack --port "$WORKTREE_PORT"
else
    ./node_modules/.bin/next dev --turbopack
fi
