#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${AI_PROJECT_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
REPO_ROOT="$(cd "$PROJECT_ROOT" && pwd)"
WORKTREE_LAUNCH="${AI_WORKTREE_LAUNCH:-$SCRIPT_DIR/worktree-launch.sh}"

usage() {
    cat <<EOF
Usage:
  $(basename "$0") [--dry-run] -- <client> [client-flags...]
  $(basename "$0") --help

Interactive modes:
  1) main          Sync local main with origin/main, preserving uncommitted changes
  2) new worktree  Create a fresh worktree and launch the client there

Non-interactive mode:
  Append: choose main | choose worktree

Examples:
  $(basename "$0") -- claude --dangerously-skip-permissions
  $(basename "$0") -- codex --dangerously-bypass-approvals-and-sandbox
  $(basename "$0") -- codex --dangerously-bypass-approvals-and-sandbox choose main
  $(basename "$0") -- gemini --approval-mode yolo
  $(basename "$0") --dry-run -- codex --dangerously-bypass-approvals-and-sandbox
EOF
}

prompt_mode() {
    local client_name="$1"
    while true; do
        printf 'Start %s in:\n' "$client_name"
        printf '  1) main\n'
        printf '  2) new worktree\n'
        printf 'Select [1-2]: '

        local choice=""
        if ! IFS= read -r choice; then
            echo ""
            echo "Error: selection cancelled." >&2
            return 1
        fi

        case "$choice" in
            1|main)
                MODE_SELECTION="main"
                return 0
                ;;
            2|worktree)
                MODE_SELECTION="worktree"
                return 0
                ;;
            *)
                printf 'Invalid choice. Enter 1 or 2.\n'
                ;;
        esac
    done
}

normalize_mode_selection() {
    case "$1" in
        1|main)
            printf 'main'
            ;;
        2|worktree|new|new-worktree)
            printf 'worktree'
            ;;
        *)
            return 1
            ;;
    esac
}

consume_choose_mode() {
    MODE_SELECTION=""
    local i selected=""
    for ((i = 0; i < ${#CLIENT_CMD[@]}; i++)); do
        if [[ "${CLIENT_CMD[$i]}" != "choose" ]]; then
            continue
        fi
        if (( i + 1 >= ${#CLIENT_CMD[@]} )); then
            echo "Error: choose requires a mode: main or worktree." >&2
            return 1
        fi
        if ! selected="$(normalize_mode_selection "${CLIENT_CMD[$((i + 1))]}")"; then
            echo "Error: choose mode must be main or worktree." >&2
            return 1
        fi
        unset "CLIENT_CMD[$i]"
        unset "CLIENT_CMD[$((i + 1))]"
        MODE_SELECTION="$selected"
        return 0
    done
    return 0
}

repo_status_is_dirty() {
    [[ -n "$(git -C "$REPO_ROOT" status --porcelain)" ]]
}

prompt_safe_sync() {
    local ahead behind choice=""
    ahead=$(git -C "$REPO_ROOT" rev-list --count origin/main..main)
    behind=$(git -C "$REPO_ROOT" rev-list --count main..origin/main)

    printf 'Local main is ahead of or diverged from origin/main.\n'
    printf 'Safe sync can rebase local-only commits onto origin/main, push main normally, and preserve dirty work (%s ahead, %s behind).\n' "$ahead" "$behind"
    printf 'Run safe sync now? [y/N]: '

    if ! IFS= read -r choice; then
        echo ""
        echo "Error: safe sync cancelled." >&2
        return 1
    fi

    case "$choice" in
        y|Y|yes|YES|Yes)
            return 0
            ;;
        *)
            echo "Error: safe sync declined; local main is ahead of or diverged from origin/main." >&2
            return 1
            ;;
    esac
}

abort_merge_if_active() {
    if git -C "$REPO_ROOT" rev-parse --verify --quiet MERGE_HEAD >/dev/null 2>&1; then
        git -C "$REPO_ROOT" merge --abort >/dev/null 2>&1 || true
    fi
}

abort_rebase_if_active() {
    git -C "$REPO_ROOT" rebase --abort >/dev/null 2>&1 || true
}

safe_sync_main_checkout() {
    local remote_sha="$1" base_sha="$2" stash_created=false sync_status=0

    if repo_status_is_dirty; then
        git -C "$REPO_ROOT" stash push --include-untracked --message "ai-autostash-$(date +%Y%m%d-%H%M%S)" >/dev/null
        stash_created=true
    fi

    if [[ "$remote_sha" != "$base_sha" ]]; then
        if ! git -C "$REPO_ROOT" rebase origin/main >/dev/null; then
            abort_merge_if_active
            abort_rebase_if_active
            sync_status=1
        fi
    fi

    if [[ "$sync_status" -eq 0 ]]; then
        git -C "$REPO_ROOT" push origin main >/dev/null || sync_status=1
    fi

    if [[ "$sync_status" -eq 0 ]]; then
        git -C "$REPO_ROOT" fetch origin main >/dev/null || sync_status=1
    fi

    if [[ "$sync_status" -eq 0 ]]; then
        local post_local post_remote
        post_local=$(git -C "$REPO_ROOT" rev-parse main)
        post_remote=$(git -C "$REPO_ROOT" rev-parse origin/main)
        if [[ "$post_local" != "$post_remote" ]]; then
            echo "Error: safe sync did not leave main aligned with origin/main." >&2
            sync_status=1
        fi
    fi

    if [[ "$stash_created" == "true" ]]; then
        if ! git -C "$REPO_ROOT" stash pop --index >/dev/null; then
            echo "Error: failed to restore stashed changes cleanly." >&2
            return 1
        fi
    fi

    if [[ "$sync_status" -ne 0 ]]; then
        echo "Error: safe sync failed." >&2
        return 1
    fi
}

sync_main_checkout() {
    local current_branch stash_created=false
    current_branch=$(git -C "$REPO_ROOT" rev-parse --abbrev-ref HEAD)

    if [[ "$current_branch" != "main" ]]; then
        if repo_status_is_dirty; then
            git -C "$REPO_ROOT" stash push --include-untracked --message "ai-autostash-$(date +%Y%m%d-%H%M%S)" >/dev/null
            stash_created=true
        fi
        if ! git -C "$REPO_ROOT" checkout main >/dev/null 2>&1; then
            if [[ "$stash_created" == "true" ]]; then
                git -C "$REPO_ROOT" stash pop --index >/dev/null 2>&1 || true
            fi
            echo "Error: main mode requires branch 'main'; checkout failed — resolve manually." >&2
            return 1
        fi
        if [[ "$stash_created" == "true" ]]; then
            if ! git -C "$REPO_ROOT" stash pop --index >/dev/null; then
                echo "Error: switched to main but failed to restore stashed changes cleanly." >&2
                return 1
            fi
            stash_created=false
        fi
    fi

    git -C "$REPO_ROOT" fetch origin main >/dev/null

    local local_sha remote_sha base_sha
    local_sha=$(git -C "$REPO_ROOT" rev-parse main)
    remote_sha=$(git -C "$REPO_ROOT" rev-parse origin/main)
    base_sha=$(git -C "$REPO_ROOT" merge-base main origin/main)

    if [[ "$local_sha" == "$remote_sha" ]]; then
        return 0
    fi

    if [[ "$local_sha" != "$base_sha" ]]; then
        prompt_safe_sync
        safe_sync_main_checkout "$remote_sha" "$base_sha"
        return $?
    fi

    if repo_status_is_dirty; then
        git -C "$REPO_ROOT" stash push --include-untracked --message "ai-autostash-$(date +%Y%m%d-%H%M%S)" >/dev/null
        stash_created=true
    fi

    git -C "$REPO_ROOT" merge --ff-only origin/main >/dev/null

    if [[ "$stash_created" == "true" ]]; then
        if ! git -C "$REPO_ROOT" stash pop --index >/dev/null; then
            echo "Error: synced main but failed to restore stashed changes cleanly." >&2
            return 1
        fi
    fi
}

main() {
    local dry_run=false

    # Parse own flags (must come before --)
    while [[ "${1:-}" != "--" && "${1:-}" != "" ]]; do
        case "$1" in
            --help|-h)
                usage
                exit 0
                ;;
            --dry-run)
                dry_run=true
                shift
                ;;
            *)
                echo "Error: unknown option: $1" >&2
                usage >&2
                exit 1
                ;;
        esac
    done

    # Consume the -- separator
    if [[ "${1:-}" == "--" ]]; then
        shift
    fi

    if [[ $# -eq 0 ]]; then
        echo "Error: no client command specified. Use: $(basename "$0") [--dry-run] -- <client> [flags...]" >&2
        exit 1
    fi

    local CLIENT_CMD=("$@")
    local client_name
    client_name="$(basename "${CLIENT_CMD[0]}")"

    consume_choose_mode
    if [[ -z "${MODE_SELECTION:-}" ]]; then
        prompt_mode "$client_name"
    fi
    local mode="${MODE_SELECTION}"

    if [[ "$mode" == "main" ]]; then
        if [[ "$dry_run" == "true" ]]; then
            printf 'mode=main repo=%s sync_target=origin/main command=%s\n' "$REPO_ROOT" "${CLIENT_CMD[*]}"
            exit 0
        fi

        sync_main_checkout

        if [[ "${AI_NO_EXEC:-0}" == "1" ]]; then
            printf 'mode=main repo=%s sync_target=origin/main command=%s\n' "$REPO_ROOT" "${CLIENT_CMD[*]}"
            exit 0
        fi

        cd "$REPO_ROOT"
        exec "${CLIENT_CMD[@]}"
    fi

    if [[ "$dry_run" == "true" ]]; then
        printf 'mode=worktree command=%s create -- %s\n' "$WORKTREE_LAUNCH" "${CLIENT_CMD[*]}"
        exit 0
    fi

    if [[ "${AI_NO_EXEC:-0}" == "1" ]]; then
        printf 'mode=worktree command=%s create -- %s\n' "$WORKTREE_LAUNCH" "${CLIENT_CMD[*]}"
        exit 0
    fi

    exec "$WORKTREE_LAUNCH" create -- "${CLIENT_CMD[@]}"
}

main "$@"
