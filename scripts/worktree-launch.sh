#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# worktree-launch.sh — Create, list, launch, and clean up git worktrees
#
# Canonical actions:
#   create   Create a worktree, optionally launch a command inside it
#   list     Show active git worktrees and registry state
#   cleanup  Remove a worktree, unregister it, and delete its branch
#
# Examples:
#   worktree-launch.sh create
#   worktree-launch.sh create --name ask-native-ux
#   worktree-launch.sh create --json
#   worktree-launch.sh create -- codex --dangerously-bypass-approvals-and-sandbox
#   worktree-launch.sh cleanup wt-20260413-154500
#   worktree-launch.sh list
# =============================================================================

BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
DIM='\033[2m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MAIN_REPO="$(cd "$SCRIPT_DIR/.." && pwd)"
REGISTRY_SCRIPT="$MAIN_REPO/scripts/worktree_registry.py"
MCP_GEN_SCRIPT="$MAIN_REPO/scripts/generate-worktree-mcp.py"
PREFLIGHT_SCRIPT="$MAIN_REPO/scripts/worktree_preflight.py"

die()  { echo -e "${RED}Error:${NC} $*" >&2; exit 1; }
info() { [[ "${JSON_MODE:-false}" == "true" ]] && return; echo -e "${BLUE}>>>${NC} $*"; }
ok()   { [[ "${JSON_MODE:-false}" == "true" ]] && return; echo -e "${GREEN}>>>${NC} $*"; }
warn() { echo -e "${YELLOW}>>>${NC} $*" >&2; }

usage() {
    cat <<EOF
Usage:
  $(basename "$0") create [options] [-- <command> [args...]]
  $(basename "$0") cleanup <name-or-path>
  $(basename "$0") list

Actions:
  create                  Create a fresh worktree from the target branch
  cleanup                 Remove a worktree, unregister it, and delete its branch
  list                    Show active worktrees and registry state

Create options:
  --name <name>           Explicit worktree name (default: wt-YYYYMMDD-HHMMSS)
  --branch <branch>       Explicit branch name (default: worktree name)
  --into <branch>         Target branch to base the worktree from
  --base <ref>            Explicit base ref to branch from
  --json                  Print machine-readable JSON and exit
  --dry-run               Show what would happen without creating anything
  -h, --help              Show this help

Examples:
  $(basename "$0") create
  $(basename "$0") create --name ask-native-ux
  $(basename "$0") create --into main --json
  $(basename "$0") create -- codex --dangerously-bypass-approvals-and-sandbox
  $(basename "$0") create -- gemini --approval-mode yolo
  $(basename "$0") create -- zsh
  $(basename "$0") cleanup wt-20260413-154500
  $(basename "$0") list
EOF
}

normalize_name() {
    local raw="$1"
    local normalized
    normalized=$(printf '%s' "$raw" \
        | tr '[:upper:]' '[:lower:]' \
        | sed -E 's/[^a-z0-9._-]+/-/g; s/^-+//; s/-+$//; s/-{2,}/-/g')
    [[ -n "$normalized" ]] || die "Unable to derive a valid worktree name from: $raw"
    echo "$normalized"
}

generate_timestamp_name() {
    date +"wt-%Y%m%d-%H%M%S"
}

derive_worktree_dir() {
    local wt_name="$1"
    echo "$(dirname "$MAIN_REPO")/augur-${wt_name}"
}

resolve_base_ref() {
    if [[ -n "${BASE_REF:-}" ]]; then
        if git -C "$MAIN_REPO" rev-parse --verify --quiet "$BASE_REF" >/dev/null; then
            echo "$BASE_REF"
            return 0
        fi
        die "Base ref not found: $BASE_REF"
    fi

    if [[ -n "${TARGET_BRANCH:-}" ]]; then
        if git -C "$MAIN_REPO" show-ref --verify --quiet "refs/heads/$TARGET_BRANCH"; then
            echo "$TARGET_BRANCH"
            return 0
        fi
        if git -C "$MAIN_REPO" show-ref --verify --quiet "refs/remotes/origin/$TARGET_BRANCH"; then
            echo "origin/$TARGET_BRANCH"
            return 0
        fi
        die "Target branch not found locally or on origin: $TARGET_BRANCH"
    fi

    local remote_head=""
    remote_head=$(git -C "$MAIN_REPO" symbolic-ref --quiet --short refs/remotes/origin/HEAD 2>/dev/null || true)
    if [[ -n "$remote_head" ]]; then
        echo "$remote_head"
        return 0
    fi

    if git -C "$MAIN_REPO" show-ref --verify --quiet refs/heads/main; then
        echo "main"
        return 0
    fi

    die "Unable to resolve a base branch. Use --into <branch> or --base <ref>."
}

find_existing_worktree() {
    local pattern="$1"
    git -C "$MAIN_REPO" worktree list --porcelain 2>/dev/null | while IFS= read -r line; do
        if [[ "$line" =~ ^worktree\ (.+) ]]; then
            local wt_path="${BASH_REMATCH[1]}"
            [[ "$wt_path" == "$MAIN_REPO" ]] && continue
            if [[ "$wt_path" == "$pattern" ]] || echo "$wt_path" | grep -qi -- "$pattern"; then
                echo "$wt_path"
                return 0
            fi
        fi
    done
}

create_worktree() {
    local wt_dir="$1"
    local branch="$2"
    local base_ref="$3"

    if [[ -d "$wt_dir" ]]; then
        ok "Worktree directory exists: $wt_dir"
        return 0
    fi

    info "Creating worktree at ${wt_dir} (branch: ${branch}, base: ${base_ref})"
    git -C "$MAIN_REPO" worktree add "$wt_dir" -b "$branch" "$base_ref" >&2 2>&1
    ok "Worktree created"
}

register_worktree() {
    local wt_dir="$1"
    local wt_name="$2"

    if [[ ! -f "$REGISTRY_SCRIPT" ]]; then
        warn "Registry script not found, skipping port allocation"
        echo ""
        return 0
    fi

    info "Registering worktree for port isolation"
    local result exit_code=0
    result=$(python3 "$REGISTRY_SCRIPT" register --path "$wt_dir" --name "$wt_name" 2>&1) || exit_code=$?

    if [[ $exit_code -ne 0 ]]; then
        local err_msg
        err_msg=$(echo "$result" | python3 -c "import sys,json; print(json.load(sys.stdin).get('error','Registration failed'))" 2>/dev/null || echo "Registration failed (exit code $exit_code)")
        warn "Registration failed: $err_msg"
        echo "ERROR:$err_msg"
        return 1
    fi

    local success
    success=$(echo "$result" | python3 -c "import sys,json; print(json.load(sys.stdin).get('success', False))" 2>/dev/null || echo "False")

    if [[ "$success" != "True" ]]; then
        local err_msg
        err_msg=$(echo "$result" | python3 -c "import sys,json; print(json.load(sys.stdin).get('error','Unknown registration error'))" 2>/dev/null || echo "Unknown registration error")
        warn "Registration failed: $err_msg"
        echo "ERROR:$err_msg"
        return 1
    fi

    local dashboard_port mcp_port
    dashboard_port=$(echo "$result" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('dashboard_port', d.get('worktree',{}).get('dashboard_port','')))" 2>/dev/null || echo "")
    mcp_port=$(echo "$result" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('mcp_port', d.get('worktree',{}).get('mcp_port','')))" 2>/dev/null || echo "")

    if [[ -n "$dashboard_port" ]]; then
        ok "Ports allocated: dashboard=${dashboard_port}, mcp=${mcp_port}"

        echo "PORT=$dashboard_port" > "$wt_dir/.env.local"

        cat > "$wt_dir/.augur-worktree.yaml" <<MARKER
worktree: true
dashboard_port: ${dashboard_port}
mcp_port: ${mcp_port}
main_repo: ${MAIN_REPO}
name: ${wt_name}
created_at: $(date -u +%Y-%m-%dT%H:%M:%SZ)
MARKER
        ok "Worktree marker written"

        echo "${dashboard_port}:${mcp_port}"
    else
        warn "Port allocation returned no ports: $result"
        echo "ERROR:No ports allocated"
        return 1
    fi
}

generate_mcp_config() {
    local wt_dir="$1"
    local wt_name="$2"

    if [[ ! -f "$MCP_GEN_SCRIPT" ]]; then
        warn "MCP config generator not found, skipping"
        return 0
    fi

    info "Generating isolated MCP config"
    env \
        AUGUR_ROOT="$wt_dir" \
        AUGUR_CORE="$wt_dir" \
        AUGUR_REPO="$wt_dir" \
        python3 "$MCP_GEN_SCRIPT" --path "$wt_dir" --name "$wt_name" --all >&2 2>&1 || warn "MCP config generation had issues (non-fatal)"
    ok "MCP config generated"
}

repair_codex_thread_state() {
    local wt_dir="$1"
    local repair_script="$MAIN_REPO/project-brain/capabilities/skills/platform-admin/scripts/codex_thread_state.py"
    [[ -f "$repair_script" ]] || return 0

    local target_branch="main"
    target_branch=$(git -C "$MAIN_REPO" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "main")

    local result=""
    if result=$(python3 "$repair_script" \
        --worktree-path "$wt_dir" \
        --repo-root "$MAIN_REPO" \
        --target-branch "$target_branch" 2>/dev/null); then
        local updated="0"
        updated=$(printf '%s' "$result" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("updated_threads", 0))' 2>/dev/null || echo "0")
        if [[ "$updated" != "0" ]]; then
            ok "Codex thread state repaired (${updated} thread records)"
        fi
    else
        warn "Codex thread state repair failed; run codex_thread_state.py manually if Codex crashes on this worktree"
    fi
}

bootstrap_worktree() {
    local wt_dir="$1"
    if [[ ! -f "$PREFLIGHT_SCRIPT" ]]; then
        warn "Preflight helper not found, skipping bootstrap"
        return 0
    fi

    info "Bootstrapping worktree runtime and shared dependencies"
    local preflight_json
    if ! preflight_json=$(env \
        AUGUR_ROOT="$wt_dir" \
        AUGUR_CORE="$wt_dir" \
        AUGUR_REPO="$wt_dir" \
        python3 "$PREFLIGHT_SCRIPT" --root "$wt_dir" --profile worktree --repair 2>/dev/null); then
        warn "Worktree preflight reported unresolved issues"
        printf '%s\n' "$preflight_json" >&2
        return 1
    fi

    local repair_count
    repair_count=$(printf '%s' "$preflight_json" | python3 -c 'import json,sys; print(len(json.load(sys.stdin)["repairs_applied"]))')
    if [[ "$repair_count" != "0" ]]; then
        ok "Applied ${repair_count} bootstrap repairs"
    fi
}

generate_dashboard_runtime_artifacts() {
    local wt_dir="$1"
    local dashboard_dir="$wt_dir/apps/dashboard"

    [[ -d "$dashboard_dir" ]] || return 0

    if ! command -v node >/dev/null 2>&1; then
        warn "Node.js not available; dashboard generated runtime artifacts may be missing"
        return 0
    fi

    info "Generating dashboard runtime artifacts"
    if [[ ! -f "$dashboard_dir/scripts/dist/rebuild-plugins.mjs" ]]; then
        (
            cd "$dashboard_dir"
            env \
                AUGUR_ROOT="$wt_dir" \
                AUGUR_CORE="$wt_dir" \
                AUGUR_REPO="$wt_dir" \
                node scripts/build-scripts.mjs
        ) >&2 2>&1 || {
            warn "Dashboard script build failed; generated runtime artifacts may be missing"
            return 0
        }
    fi

    (
        cd "$dashboard_dir"
        env \
            AUGUR_ROOT="$wt_dir" \
            AUGUR_CORE="$wt_dir" \
            AUGUR_REPO="$wt_dir" \
            PATH="$wt_dir/scripts:$wt_dir/.venv/bin:$PATH" \
            node scripts/dist/rebuild-plugins.mjs --skip-registry
    ) >&2 2>&1 || {
        warn "Dashboard runtime artifact generation failed; run /dev-build before dashboard checks"
        return 0
    }
    ok "Dashboard runtime artifacts generated"
}

do_create() {
    local wt_name="$1"
    local branch="$2"
    local base_ref="$3"
    local wt_dir="$4"
    local reused=false

    local existing=""
    if [[ -n "${CREATE_NAME_EXPLICIT:-}" ]]; then
        existing=$(find_existing_worktree "$wt_name")
    fi

    if [[ -n "$existing" ]]; then
        wt_dir="$existing"
        reused=true
        ok "Reusing existing worktree: $wt_dir"
    else
        create_worktree "$wt_dir" "$branch" "$base_ref"
    fi

    local ports_line reg_exit=0
    ports_line=$(register_worktree "$wt_dir" "$wt_name" | tail -1) || reg_exit=$?

    local dashboard_port="" mcp_port=""
    if [[ "$ports_line" == ERROR:* ]]; then
        local reg_error="${ports_line#ERROR:}"
        if [[ "$JSON_MODE" == "true" ]]; then
            WT_DIR="$wt_dir"
            WT_NAME="$wt_name"
            WT_BRANCH="$branch"
            WT_REUSED="$reused"
            WT_BASE_REF="$base_ref"
            WT_DASHBOARD_PORT=""
            WT_MCP_PORT=""
            WT_REG_ERROR="$reg_error"
            return 0
        fi
        echo -e "${RED}Error:${NC} Port registration failed: $reg_error" >&2
        echo -e "${YELLOW}Hint:${NC} Run 'python3 $REGISTRY_SCRIPT prune' to clean ghost entries" >&2
        exit 1
    elif [[ "$ports_line" == *":"* ]]; then
        dashboard_port="${ports_line%%:*}"
        mcp_port="${ports_line##*:}"
    fi

    bootstrap_worktree "$wt_dir"
    generate_dashboard_runtime_artifacts "$wt_dir"
    generate_mcp_config "$wt_dir" "$wt_name"

    WT_DIR="$wt_dir"
    WT_NAME="$wt_name"
    WT_BRANCH="$branch"
    WT_BASE_REF="$base_ref"
    WT_REUSED="$reused"
    WT_DASHBOARD_PORT="${dashboard_port:-}"
    WT_MCP_PORT="${mcp_port:-}"
    WT_REG_ERROR=""
}

remove_dashboard_cache() {
    # Reap the worktree's external Next/SWC build cache (~400-550MB each) that
    # start-dev.sh creates under get_cache_dir()/dashboard-worktree-<slug>.
    # Must run while the worktree marker still exists so instance resolution
    # matches what start-dev.sh used. Never touches main's shared "dashboard"
    # namespace; skips a cache still held by a live next-dev lock PID.
    local wt_dir="$1"
    local result=""
    result=$(python3 - "$wt_dir" "$MAIN_REPO" <<'PY' 2>/dev/null
import json
import os
import shutil
import sys
from pathlib import Path

wt_dir, main_repo = Path(sys.argv[1]), sys.argv[2]
sys.path.insert(0, main_repo)
from src.lib.dashboard_instance import (
    external_dashboard_cache_dir,
    resolve_dashboard_instance,
)


def live_lock_pid(cache_dir: Path) -> int | None:
    lock_path = cache_dir / "next" / "dev" / "lock"
    try:
        pid = int(json.loads(lock_path.read_text(encoding="utf-8")).get("pid", 0))
    except (OSError, ValueError, json.JSONDecodeError):
        return None
    if pid <= 0:
        return None
    try:
        os.kill(pid, 0)
    except OSError:
        return None
    return pid


instance = resolve_dashboard_instance(wt_dir)
cache_dir = external_dashboard_cache_dir(instance)
if cache_dir is None or not cache_dir.is_dir():
    print("")
elif (pid := live_lock_pid(cache_dir)) is not None:
    print(f"skipped (live next-dev lock pid {pid}): {cache_dir}")
else:
    shutil.rmtree(cache_dir, ignore_errors=True)
    print(f"removed: {cache_dir}")
PY
    ) || true
    [[ -n "$result" ]] && info "Dashboard cache $result"
    return 0
}

remove_worktree_and_branch() {
    local wt_dir="$1"

    local branch=""
    branch=$(git -C "$wt_dir" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")

    remove_dashboard_cache "$wt_dir"

    if [[ -f "$REGISTRY_SCRIPT" ]]; then
        python3 "$REGISTRY_SCRIPT" unregister --path "$wt_dir" 2>/dev/null || true
    fi

    git -C "$MAIN_REPO" worktree remove "$wt_dir" --force 2>/dev/null || {
        warn "git worktree remove failed, removing directory manually"
        rm -rf "$wt_dir"
        git -C "$MAIN_REPO" worktree prune 2>/dev/null || true
    }
    repair_codex_thread_state "$wt_dir"

    if [[ -n "$branch" && "$branch" != "main" && "$branch" != "HEAD" ]]; then
        git -C "$MAIN_REPO" branch -D "$branch" 2>/dev/null || true
        ok "Branch deleted: $branch"
    fi
}

do_cleanup() {
    local name_or_path="$1"
    local wt_dir=""

    if [[ -d "$name_or_path" ]]; then
        wt_dir="$name_or_path"
    else
        wt_dir=$(derive_worktree_dir "$name_or_path")
        if [[ ! -d "$wt_dir" ]]; then
            local found=""
            found=$(find_existing_worktree "$name_or_path")
            [[ -n "$found" ]] || die "No worktree found matching: $name_or_path"
            wt_dir="$found"
        fi
    fi

    info "Removing worktree: $wt_dir"
    remove_worktree_and_branch "$wt_dir"
    ok "Worktree removed"
}

do_list() {
    echo -e "${BLUE}Git worktrees:${NC}"
    git -C "$MAIN_REPO" worktree list
    echo ""

    if [[ -f "$REGISTRY_SCRIPT" ]]; then
        echo -e "${BLUE}Registry:${NC}"
        python3 "$REGISTRY_SCRIPT" list 2>/dev/null || echo "  (no registry)"
    fi
}

print_json_result() {
    if [[ -n "${WT_REG_ERROR:-}" ]]; then
        cat <<JSON
{
  "worktree_path": "${WT_DIR}",
  "worktree_name": "${WT_NAME}",
  "branch": "${WT_BRANCH}",
  "base_ref": "${WT_BASE_REF}",
  "reused": ${WT_REUSED},
  "main_repo": "${MAIN_REPO}",
  "dashboard_port": null,
  "mcp_port": null,
  "env": {
    "AUGUR_ROOT": "${WT_DIR}",
    "AUGUR_CORE": "${WT_DIR}",
    "AUGUR_REPO": "${WT_DIR}"
  },
  "error": "${WT_REG_ERROR}"
}
JSON
        return 0
    fi

    cat <<JSON
{
  "worktree_path": "${WT_DIR}",
  "worktree_name": "${WT_NAME}",
  "branch": "${WT_BRANCH}",
  "base_ref": "${WT_BASE_REF}",
  "reused": ${WT_REUSED},
  "main_repo": "${MAIN_REPO}",
  "dashboard_port": ${WT_DASHBOARD_PORT:-null},
  "mcp_port": ${WT_MCP_PORT:-null},
  "env": {
    "AUGUR_ROOT": "${WT_DIR}",
    "AUGUR_CORE": "${WT_DIR}",
    "AUGUR_REPO": "${WT_DIR}"
  }
}
JSON
}

main() {
    [[ $# -eq 0 ]] && { usage; exit 1; }

    JSON_MODE=false
    local dry_run=false
    local action="$1"
    shift

    case "$action" in
        -h|--help)
            usage
            exit 0
            ;;
        list)
            do_list
            exit 0
            ;;
        cleanup)
            [[ $# -ge 1 ]] || die "cleanup requires a worktree name or path"
            do_cleanup "$1"
            exit 0
            ;;
        create)
            ;;
        *)
            die "Unknown action: $action"
            ;;
    esac

    local create_name=""
    local branch_override=""
    local passthrough=()
    CREATE_NAME_EXPLICIT=""
    TARGET_BRANCH=""
    BASE_REF=""

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --name)
                [[ $# -ge 2 ]] || die "--name requires a value"
                create_name=$(normalize_name "$2")
                CREATE_NAME_EXPLICIT=true
                shift 2
                ;;
            --branch)
                [[ $# -ge 2 ]] || die "--branch requires a value"
                branch_override=$(normalize_name "$2")
                shift 2
                ;;
            --into)
                [[ $# -ge 2 ]] || die "--into requires a branch name"
                TARGET_BRANCH="$2"
                shift 2
                ;;
            --base)
                [[ $# -ge 2 ]] || die "--base requires a ref"
                BASE_REF="$2"
                shift 2
                ;;
            --json)
                JSON_MODE=true
                shift
                ;;
            --dry-run)
                dry_run=true
                shift
                ;;
            --)
                shift
                passthrough=("$@")
                break
                ;;
            -h|--help)
                usage
                exit 0
                ;;
            *)
                die "Unknown create option: $1"
                ;;
        esac
    done

    local wt_name branch base_ref wt_dir
    wt_name="${create_name:-$(generate_timestamp_name)}"
    branch="${branch_override:-$wt_name}"
    base_ref=$(resolve_base_ref)
    wt_dir=$(derive_worktree_dir "$wt_name")

    if [[ "$JSON_MODE" == "false" ]]; then
        echo ""
        echo -e "${BLUE}╔══════════════════════════════════════════════════╗${NC}"
        echo -e "${BLUE}║${NC}  Worktree Create"
        echo -e "${BLUE}║${NC}  Name:   ${wt_name}"
        echo -e "${BLUE}║${NC}  Branch: ${branch}"
        echo -e "${BLUE}║${NC}  Base:   ${base_ref}"
        echo -e "${BLUE}║${NC}  Dir:    ${wt_dir}"
        echo -e "${BLUE}╚══════════════════════════════════════════════════╝${NC}"
        echo ""
    fi

    if $dry_run; then
        warn "DRY RUN — would create worktree from ${base_ref}"
        exit 0
    fi

    do_create "$wt_name" "$branch" "$base_ref" "$wt_dir"

    if [[ "$JSON_MODE" == "true" ]]; then
        print_json_result
        exit 0
    fi

    if [[ ${#passthrough[@]} -gt 0 ]]; then
        echo ""
        ok "Launching command in worktree"
        echo -e "${DIM}   cwd: ${WT_DIR}${NC}"
        echo -e "${DIM}   cmd: ${passthrough[*]}${NC}"
        echo ""

        cd "$WT_DIR"
        exec env \
            AUGUR_ROOT="$WT_DIR" \
            AUGUR_CORE="$WT_DIR" \
            AUGUR_REPO="$WT_DIR" \
            PATH="$WT_DIR/scripts:$WT_DIR/.venv/bin:$PATH" \
            "${passthrough[@]}"
    fi

    printf '%s\n' "$WT_DIR"
}

main "$@"
