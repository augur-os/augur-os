# XA Main Or Worktree Launch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `xa` ask whether to launch Codex in the main checkout or a new worktree, and auto-sync local `main` to `origin/main` safely even when the repo has uncommitted changes.

**Architecture:** Keep `scripts/worktree-launch.sh` focused on worktree lifecycle and add a dedicated `scripts/xa-launch.sh` entrypoint for the interactive startup choice. Cover the launcher with subprocess-based pytest tests, then update `~/.zshrc` so `xa` points at the new script instead of embedding behavior directly in the alias.

**Tech Stack:** Bash, git, pytest, Python subprocess/pathlib, zsh alias wiring

---

### Task 1: Lock The XA Launcher Contract With Tests

**Files:**
- Create: `tests/scripts/test_xa_launch.py`
- Reference: `scripts/xa-launch.sh`
- Reference: `scripts/worktree-launch.sh`

- [ ] **Step 1: Write the failing launcher tests**

```python
from __future__ import annotations

import os
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = PROJECT_ROOT / "scripts" / "xa-launch.sh"


def run_script(*args: str, input_text: str = "", env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        cwd=PROJECT_ROOT,
        input=input_text,
        capture_output=True,
        text=True,
        check=False,
        env=merged_env,
    )


def test_help_mentions_main_and_worktree_choices() -> None:
    result = run_script("--help")

    assert result.returncode == 0
    assert "main" in result.stdout
    assert "worktree" in result.stdout
    assert "origin/main" in result.stdout


def test_invalid_choice_reprompts_until_valid_selection() -> None:
    result = run_script("--dry-run", input_text="wat\n2\n")

    assert result.returncode == 0
    assert "Invalid choice" in result.stdout
    assert "mode=worktree" in result.stdout


def test_dry_run_main_selection_reports_main_mode() -> None:
    result = run_script("--dry-run", input_text="1\n")

    assert result.returncode == 0
    assert "mode=main" in result.stdout
    assert "origin/main" in result.stdout


def test_dry_run_worktree_selection_reports_worktree_mode() -> None:
    result = run_script("--dry-run", input_text="2\n")

    assert result.returncode == 0
    assert "mode=worktree" in result.stdout
    assert "worktree-launch.sh create -- codex" in result.stdout
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
pytest tests/scripts/test_xa_launch.py -q
```

Expected:

```text
FAIL tests/scripts/test_xa_launch.py ...
```

- [ ] **Step 3: Commit the red test**

```bash
git add tests/scripts/test_xa_launch.py
git commit -m "test: define xa launcher contract"
```

### Task 2: Implement The Interactive XA Launcher

**Files:**
- Create: `scripts/xa-launch.sh`
- Modify: `tests/scripts/test_xa_launch.py`
- Reference: `scripts/worktree-launch.sh`

- [ ] **Step 1: Add the interactive launcher script**

```bash
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
WORKTREE_LAUNCH="$PROJECT_ROOT/scripts/worktree-launch.sh"
CODEX_CMD=(codex --dangerously-bypass-approvals-and-sandbox)

usage() {
    cat <<'EOF'
Usage:
  scripts/xa-launch.sh
  scripts/xa-launch.sh --help
  scripts/xa-launch.sh --dry-run

Interactive modes:
  1) main          Sync local main with origin/main, preserving uncommitted changes
  2) new worktree  Create a fresh worktree and launch Codex there
EOF
}

prompt_mode() {
    while true; do
        printf 'Start Codex in:\n'
        printf '  1) main\n'
        printf '  2) new worktree\n'
        printf 'Select [1-2]: '
        IFS= read -r choice
        case "$choice" in
            1|main) echo "main"; return 0 ;;
            2|worktree) echo "worktree"; return 0 ;;
            *) printf 'Invalid choice. Enter 1 or 2.\n' ;;
        esac
    done
}
```

- [ ] **Step 2: Implement main-mode sync with stash/restore**

```bash
sync_main_checkout() {
    cd "$PROJECT_ROOT"

    local current_branch
    current_branch=$(git rev-parse --abbrev-ref HEAD)
    [[ "$current_branch" == "main" ]] || {
        echo "Error: main mode requires the root checkout to be on branch 'main'." >&2
        return 1
    }

    git fetch origin main

    local local_sha remote_sha base_sha
    local_sha=$(git rev-parse main)
    remote_sha=$(git rev-parse origin/main)
    base_sha=$(git merge-base main origin/main)

    if [[ "$local_sha" == "$remote_sha" ]]; then
        return 0
    fi

    if [[ "$local_sha" != "$base_sha" ]]; then
        echo "Error: local main is ahead of or diverged from origin/main; sync manually first." >&2
        return 1
    fi

    local stash_name=""
    if [[ -n "$(git status --porcelain)" ]]; then
        stash_name="xa-autostash-$(date +%Y%m%d-%H%M%S)"
        git stash push --include-untracked --message "$stash_name" >/dev/null
    fi

    git merge --ff-only origin/main

    if [[ -n "$stash_name" ]]; then
        if ! git stash pop >/dev/null; then
            echo "Error: synced main but failed to restore stashed changes cleanly." >&2
            return 1
        fi
    fi
}
```

- [ ] **Step 3: Implement dispatch for main mode and worktree mode**

```bash
main() {
    local dry_run=false
    if [[ "${1:-}" == "--help" ]]; then
        usage
        exit 0
    fi
    if [[ "${1:-}" == "--dry-run" ]]; then
        dry_run=true
    fi

    local mode
    mode=$(prompt_mode)

    if $dry_run; then
        if [[ "$mode" == "main" ]]; then
            printf 'mode=main sync_target=origin/main command=%s\n' "${CODEX_CMD[*]}"
        else
            printf 'mode=worktree command=%s\n' "$WORKTREE_LAUNCH create -- ${CODEX_CMD[*]}"
        fi
        exit 0
    fi

    if [[ "$mode" == "main" ]]; then
        sync_main_checkout
        cd "$PROJECT_ROOT"
        exec "${CODEX_CMD[@]}"
    fi

    exec "$WORKTREE_LAUNCH" create -- "${CODEX_CMD[@]}"
}

main "$@"
```

- [ ] **Step 4: Run the targeted tests to verify green**

Run:

```bash
pytest tests/scripts/test_xa_launch.py -q
```

Expected:

```text
4 passed
```

- [ ] **Step 5: Commit the launcher implementation**

```bash
git add scripts/xa-launch.sh tests/scripts/test_xa_launch.py
git commit -m "feat: add interactive xa launcher"
```

### Task 3: Wire The Shell Alias To The New Launcher

**Files:**
- Modify: `~/.zshrc`

- [ ] **Step 1: Update the `xa` alias**

Replace:

```sh
alias xa="cd ~/Projects/Augur/ && scripts/worktree-launch.sh create -- codex --dangerously-bypass-approvals-and-sandbox"
```

With:

```sh
alias xa="cd ~/Projects/Augur/ && scripts/xa-launch.sh"
```

- [ ] **Step 2: Verify the alias text**

Run:

```bash
sed -n '108,118p' ~/.zshrc
```

Expected:

```text
alias xa="cd ~/Projects/Augur/ && scripts/xa-launch.sh"
```

- [ ] **Step 3: Commit the alias update**

```bash
git add ~/.zshrc
git commit -m "chore: point xa alias at launcher script"
```

### Task 4: Final Verification

**Files:**
- Verify: `scripts/xa-launch.sh`
- Verify: `tests/scripts/test_xa_launch.py`
- Verify: `~/.zshrc`

- [ ] **Step 1: Run the focused regression test**

Run:

```bash
pytest tests/scripts/test_xa_launch.py -q
```

Expected:

```text
4 passed
```

- [ ] **Step 2: Spot-check launcher help text**

Run:

```bash
bash scripts/xa-launch.sh --help
```

Expected:

```text
usage shows main mode, new worktree mode, and origin/main sync behavior
```

- [ ] **Step 3: Confirm the repo status is limited to intended files**

Run:

```bash
git status --short
```

Expected:

```text
scripts/xa-launch.sh, tests/scripts/test_xa_launch.py, the plan/spec docs, and any pre-existing unrelated changes only
```
