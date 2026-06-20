# Generic Worktree Lifecycle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `scripts/worktree-launch.sh` client-neutral, auto-generate new worktree branches from the target branch, and align `/dev-merge` docs with automatic post-merge worktree cleanup.

**Architecture:** Keep ADR-101 worktree isolation mechanics intact, but replace the launcher’s task-specific Claude-first CLI with generic lifecycle verbs and a passthrough command launcher. Use lightweight regression tests for shell-facing behavior and command-doc contract tests for the `/dev-merge` cleanup requirement.

**Tech Stack:** Bash, git, pytest, Python subprocess/pathlib, markdown command docs

---

### Task 1: Lock The New Launcher Contract With Tests

**Files:**
- Create: `tests/scripts/test_worktree_launch.py`
- Modify: `skills/platform-admin/augur/tests/test_dev_merge_docs.py`
- Reference: `scripts/worktree-launch.sh`

- [ ] **Step 1: Write failing launcher behavior tests**

```python
from __future__ import annotations

import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = PROJECT_ROOT / "scripts" / "worktree-launch.sh"


def test_help_mentions_generic_create_cleanup_contract() -> None:
    result = subprocess.run(
        ["bash", str(SCRIPT), "--help"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "create" in result.stdout
    assert "cleanup" in result.stdout
    assert "implement-adr" not in result.stdout
    assert "launch Claude Code" not in result.stdout


def test_help_mentions_passthrough_launch_mode() -> None:
    result = subprocess.run(
        ["bash", str(SCRIPT), "--help"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert "create -- codex" in result.stdout


def test_worktreeinclude_comment_is_client_neutral() -> None:
    text = (PROJECT_ROOT / "worktreeinclude").read_text(encoding="utf-8")

    assert "Claude" not in text
    assert "AI client" in text or "agent" in text
```

- [ ] **Step 2: Extend the `/dev-merge` contract test with terminal cleanup wording**

```python
def test_dev_merge_command_requires_terminal_cleanup_after_verified_merge() -> None:
    text = _read("skills/platform-admin/commands/dev-merge.md")
    assert "successful verified merge" in text
    assert "remove the originating worktree" in text
    assert "delete the originating branch" in text
```

- [ ] **Step 3: Run the failing tests**

Run:

```bash
pytest tests/scripts/test_worktree_launch.py skills/platform-admin/augur/tests/test_dev_merge_docs.py -q
```

Expected:

```text
FAIL tests/scripts/test_worktree_launch.py ...
FAIL skills/platform-admin/augur/tests/test_dev_merge_docs.py ...
```

### Task 2: Refactor The Launcher To Generic Lifecycle Verbs

**Files:**
- Modify: `scripts/worktree-launch.sh`
- Modify: `worktreeinclude`
- Reference: `scripts/generate-worktree-mcp.py`

- [ ] **Step 1: Replace the CLI contract in `scripts/worktree-launch.sh`**

Implement these behavior changes:

```bash
# Canonical verbs
scripts/worktree-launch.sh create
scripts/worktree-launch.sh create --name demo
scripts/worktree-launch.sh create --json
scripts/worktree-launch.sh create -- codex --dangerously-bypass-approvals-and-sandbox
scripts/worktree-launch.sh cleanup wt-20260413-154500
scripts/worktree-launch.sh list
```

Key code requirements:

```bash
generate_timestamp_name() {
    date +"wt-%Y%m%d-%H%M%S"
}

resolve_base_ref() {
    if [[ -n "${TARGET_BRANCH:-}" ]]; then
        echo "$TARGET_BRANCH"
        return 0
    fi
    local remote_head=""
    remote_head=$(git -C "$MAIN_REPO" symbolic-ref --quiet --short refs/remotes/origin/HEAD 2>/dev/null || true)
    if [[ -n "$remote_head" ]]; then
        echo "${remote_head#origin/}"
        return 0
    fi
    if git -C "$MAIN_REPO" show-ref --verify --quiet refs/heads/main; then
        echo "main"
        return 0
    fi
    return 1
}
```

- [ ] **Step 2: Update worktree creation to branch from the resolved base ref**

Minimal target behavior:

```bash
base_ref=$(resolve_base_ref) || die "Unable to resolve base branch"
git -C "$MAIN_REPO" worktree add "$wt_dir" -b "$branch" "$base_ref"
```

Do not fall back to the current checkout branch.

- [ ] **Step 3: Replace client-specific shell mode with generic passthrough execution**

Minimal target behavior:

```bash
if [[ ${#LAUNCH_CMD[@]} -gt 0 ]]; then
    cd "$WT_DIR"
    exec env \
        AUGUR_ROOT="$WT_DIR" \
        AUGUR_CORE="$WT_DIR" \
        AUGUR_REPO="$WT_DIR" \
        "${LAUNCH_CMD[@]}"
fi

printf '%s\n' "$WT_DIR"
```

- [ ] **Step 4: Update comments and examples in `worktreeinclude`**

Replace client-specific wording with generic wording:

```text
# worktreeinclude — files to copy into new git worktrees
# Matches .gitignore syntax: patterns here that are also in .gitignore
# get automatically copied when a new AI worktree is created.
```

- [ ] **Step 5: Run the launcher/documentation tests**

Run:

```bash
pytest tests/scripts/test_worktree_launch.py skills/platform-admin/augur/tests/test_dev_merge_docs.py -q
```

Expected:

```text
all selected tests pass
```

### Task 3: Align `/dev-merge` Documentation With Terminal Cleanup

**Files:**
- Modify: `skills/platform-admin/commands/dev-merge.md`
- Modify: `docs/agent-topics/WORKFLOWS.md`

- [ ] **Step 1: Add explicit post-merge cleanup language to `/dev-merge` command docs**

Target wording to add:

```md
- after a successful verified merge, remove the originating worktree and delete the originating branch
```

And in the successful path section:

```md
1. determine whether the current session is running in a worktree
2. complete the merge and verification
3. prove the target branch contains the intended result
4. remove the originating worktree
5. delete the originating branch
```

- [ ] **Step 2: Update workflow guidance to match the launcher lifecycle**

Target additions:

```md
After a successful verified `/dev-merge` from a worktree, the originating worktree and branch should be removed automatically. Leaving successful worktree leftovers behind is a workflow bug, not an operator reminder.
```

- [ ] **Step 3: Re-run the doc contract tests**

Run:

```bash
pytest skills/platform-admin/augur/tests/test_dev_merge_docs.py -q
```

Expected:

```text
all selected tests pass
```

### Task 4: Wire Codex Startup To The Generic Launcher

**Files:**
- Modify: `~/.zshrc`

- [ ] **Step 1: Update the `xa` alias to launch Codex through the new lifecycle tool**

Replace the current alias with:

```sh
alias xa="cd ~/Projects/Augur/ && scripts/worktree-launch.sh create -- codex --dangerously-bypass-approvals-and-sandbox"
```

- [ ] **Step 2: Verify the alias text is updated**

Run:

```bash
sed -n '108,118p' ~/.zshrc
```

Expected:

```text
alias xa="cd ~/Projects/Augur/ && scripts/worktree-launch.sh create -- codex --dangerously-bypass-approvals-and-sandbox"
```

### Task 5: Final Verification

**Files:**
- Verify: `scripts/worktree-launch.sh`
- Verify: `skills/platform-admin/commands/dev-merge.md`
- Verify: `docs/agent-topics/WORKFLOWS.md`
- Verify: `~/.zshrc`

- [ ] **Step 1: Run the focused regression tests**

Run:

```bash
pytest tests/scripts/test_worktree_launch.py skills/platform-admin/augur/tests/test_dev_merge_docs.py -q
```

Expected:

```text
all selected tests pass
```

- [ ] **Step 2: Spot-check the launcher help text**

Run:

```bash
bash scripts/worktree-launch.sh --help
```

Expected:

```text
usage shows create/list/cleanup, generic examples, and no Claude-specific launch text
```

- [ ] **Step 3: Confirm repo-local status is limited to intended files**

Run:

```bash
git status --short
```

Expected:

```text
launcher, docs/tests, and any pre-existing unrelated changes only
```
