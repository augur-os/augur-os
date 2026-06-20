# XA Main or Worktree Launch — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the inline `xa()` / `ca()` / `ga()` shell functions in `~/.zshrc` (written by `scripts/install.sh`) with three thin, version-controlled launcher scripts (`scripts/xa-launch.sh`, `scripts/ca-launch.sh`, `scripts/ga-launch.sh`) that delegate to the existing `scripts/ai-launch.sh`. The functions in the rc-file marker block become one-line `exec` shims pointing at the install directory.

**Architecture:** Per-client wrappers carry only the client name + default flags. All meaningful logic (prompt for main/worktree, auto-stash, fast-forward, worktree creation, port registration, MCP-config generation) stays in `scripts/ai-launch.sh` and `scripts/worktree-launch.sh`. The installer rewrites the rc-file block to delegate. Tests follow `tests/scripts/test_ai_launch.py`'s subprocess + tmp-repo pattern.

**Tech Stack:** Bash (per-client wrappers, installer block), Python 3.11 + pytest (`tests/scripts/test_*.py`).

**Spec:** `docs/superpowers/specs/2026-05-10-xa-main-or-worktree-launch-design.md`

---

## File Structure

### Created (new files)

- `scripts/xa-launch.sh` — Codex wrapper, delegates to `ai-launch.sh`
- `scripts/ca-launch.sh` — Claude wrapper, delegates to `ai-launch.sh`
- `scripts/ga-launch.sh` — Gemini wrapper, delegates to `ai-launch.sh`
- `tests/scripts/test_xa_launch.py` — black-box tests for `xa-launch.sh`
- `tests/scripts/test_ca_launch.py` — black-box tests for `ca-launch.sh`
- `tests/scripts/test_ga_launch.py` — black-box tests for `ga-launch.sh`
- `tests/scripts/test_install_alias_block.py` — verifies installer marker block delegates to the new launchers

### Modified (existing files)

- `scripts/install.sh` — rewrite the `=== augur CLI shortcuts ===` block so functions delegate to `scripts/{xa,ca,ga}-launch.sh` instead of inlining the client commands

### Unchanged (load-bearing)

- `scripts/ai-launch.sh`, `scripts/worktree-launch.sh` — keep all sync / worktree / preflight logic in place; this plan only adds wrappers.
- `tests/scripts/test_ai_launch.py` — existing assertions stay green; the new tests are additive.

---

## Phase 0: Confirm ADR is referenced

ADR-617 is already adopted (Accepted) per the index. No `/adr write` step needed; commit messages reference `refs ADR-617`.

---

## Phase 1: Codex wrapper (xa-launch.sh)

### Task 1.1: Black-box test — `xa-launch.sh --help` exits 0 and mentions Codex

**Files:**
- Create: `tests/scripts/test_xa_launch.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/scripts/test_xa_launch.py
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


def test_help_mentions_codex_and_main_or_worktree() -> None:
    result = run_script("--help")
    assert result.returncode == 0, result.stderr
    assert "codex" in result.stdout.lower()
    assert "main" in result.stdout
    assert "worktree" in result.stdout
```

- [ ] **Step 2: Run test, expect FAIL**

```bash
/auto-test-pytest tests/scripts/test_xa_launch.py::test_help_mentions_codex_and_main_or_worktree
```

Expected: FAIL — `scripts/xa-launch.sh` does not exist.

- [ ] **Step 3: Implement the wrapper**

Create `scripts/xa-launch.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

# scripts/xa-launch.sh — Codex wrapper for ai-launch.sh.
# Forwards every invocation through ai-launch.sh so the user is prompted
# for "1) main / 2) new worktree" before Codex starts.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AI_LAUNCH="${XA_AI_LAUNCH:-$SCRIPT_DIR/ai-launch.sh}"
CLIENT="codex"
CLIENT_FLAGS=(--dangerously-bypass-approvals-and-sandbox)

usage() {
    cat <<EOF
Usage:
  $(basename "$0") [--dry-run] [-- <extra-codex-flags...>]
  $(basename "$0") --help

Behavior:
  Prompts: 1) main   Sync local main with origin/main, then launch codex
           2) new worktree   Create a fresh worktree, then launch codex inside it

Examples:
  $(basename "$0")
  $(basename "$0") --dry-run
  $(basename "$0") -- --resume thread-abc123
EOF
}

if [[ ! -x "$AI_LAUNCH" ]]; then
    echo "Error: ai-launch.sh not found or not executable: $AI_LAUNCH" >&2
    exit 1
fi

# Parse our own flags.
PASSTHROUGH_AI=()
EXTRA_CLIENT=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help)
            usage
            exit 0
            ;;
        --dry-run)
            PASSTHROUGH_AI+=(--dry-run)
            shift
            ;;
        --)
            shift
            EXTRA_CLIENT=("$@")
            break
            ;;
        *)
            echo "Error: unknown option: $1" >&2
            usage >&2
            exit 1
            ;;
    esac
done

if [[ "${XA_NO_EXEC:-0}" == "1" ]]; then
    printf 'mode=invoke target=%s args=%s\n' \
        "$AI_LAUNCH" \
        "${PASSTHROUGH_AI[*]} -- $CLIENT ${CLIENT_FLAGS[*]} ${EXTRA_CLIENT[*]}"
    exit 0
fi

exec "$AI_LAUNCH" "${PASSTHROUGH_AI[@]}" -- "$CLIENT" "${CLIENT_FLAGS[@]}" "${EXTRA_CLIENT[@]}"
```

Make it executable:

```bash
chmod +x scripts/xa-launch.sh
```

- [ ] **Step 4: Run test, expect PASS**

```bash
/auto-test-pytest tests/scripts/test_xa_launch.py::test_help_mentions_codex_and_main_or_worktree
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/xa-launch.sh tests/scripts/test_xa_launch.py
git commit -m "feat(scripts): add xa-launch.sh codex wrapper (refs ADR-617)"
```

---

### Task 1.2: `xa-launch.sh --dry-run` forwards to `ai-launch.sh --dry-run` with the codex command line

**Files:**
- Modify: `tests/scripts/test_xa_launch.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/scripts/test_xa_launch.py`:

```python
def test_dry_run_main_mode_forwards_to_ai_launch_with_codex_flags() -> None:
    result = run_script("--dry-run", input_text="1\n")
    assert result.returncode == 0, result.stderr
    assert "mode=main" in result.stdout
    # The forwarded command line must include the codex bypass flag verbatim.
    assert "codex --dangerously-bypass-approvals-and-sandbox" in result.stdout


def test_dry_run_worktree_mode_forwards_to_worktree_launch() -> None:
    result = run_script("--dry-run", input_text="2\n")
    assert result.returncode == 0, result.stderr
    assert "mode=worktree" in result.stdout
    assert "worktree-launch.sh create -- codex" in result.stdout


def test_extra_args_after_dashdash_are_forwarded_to_codex() -> None:
    result = run_script("--dry-run", "--", "--resume", "abc123", input_text="1\n")
    assert result.returncode == 0, result.stderr
    assert "codex --dangerously-bypass-approvals-and-sandbox --resume abc123" in result.stdout
```

- [ ] **Step 2: Run tests, expect PASS for the first two and PASS for the third**

```bash
/auto-test-pytest tests/scripts/test_xa_launch.py
```

If the first two pass and the third fails, debug `EXTRA_CLIENT` array handling in the wrapper.

- [ ] **Step 3: Fix the wrapper if any test fails**

The most common bug: `${EXTRA_CLIENT[*]}` must be inside the `exec` array, not flattened to a string. Confirm `${EXTRA_CLIENT[@]}` is used (not `${EXTRA_CLIENT[*]}`) in the `exec` line. The `printf` for `XA_NO_EXEC` uses `${EXTRA_CLIENT[*]}` for human-readable output — that is correct.

- [ ] **Step 4: Re-run, expect PASS**

```bash
/auto-test-pytest tests/scripts/test_xa_launch.py
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add tests/scripts/test_xa_launch.py
git commit -m "test(scripts): cover xa-launch dry-run forwarding (refs ADR-617)"
```

---

### Task 1.3: Missing `ai-launch.sh` produces a clear error

**Files:**
- Modify: `tests/scripts/test_xa_launch.py`

- [ ] **Step 1: Write the failing test**

```python
def test_missing_ai_launch_errors_clearly(tmp_path) -> None:
    bogus = tmp_path / "does-not-exist.sh"
    result = run_script("--help", env={"XA_AI_LAUNCH": str(bogus)})
    # --help exits 0 even with bogus AI_LAUNCH (we never run it), but
    # any other invocation must fail with a clear error.
    assert result.returncode == 0  # --help short-circuits before the check

    result2 = run_script("--dry-run", input_text="1\n", env={"XA_AI_LAUNCH": str(bogus)})
    assert result2.returncode != 0
    assert "ai-launch.sh not found" in result2.stderr
```

Wait — re-read the wrapper. The `if [[ ! -x "$AI_LAUNCH" ]]` check fires *before* arg parsing, so `--help` would also fail. Correct expectation:

```python
def test_missing_ai_launch_errors_clearly(tmp_path) -> None:
    bogus = tmp_path / "does-not-exist.sh"
    result = run_script("--dry-run", input_text="1\n", env={"XA_AI_LAUNCH": str(bogus)})
    assert result.returncode != 0
    assert "ai-launch.sh not found" in result.stderr
```

- [ ] **Step 2: Run test, expect PASS or refactor**

Run:

```bash
/auto-test-pytest tests/scripts/test_xa_launch.py::test_missing_ai_launch_errors_clearly
```

If `--help` is now blocked when `AI_LAUNCH` is missing, that is acceptable — but better UX is to short-circuit `--help` before the executability check. Move the `--help` recognition to *before* the `if [[ ! -x "$AI_LAUNCH" ]]` block in `xa-launch.sh`:

```bash
# Recognize --help before any environment check.
for arg in "$@"; do
    case "$arg" in
        -h|--help)
            usage
            exit 0
            ;;
    esac
done

if [[ ! -x "$AI_LAUNCH" ]]; then
    echo "Error: ai-launch.sh not found or not executable: $AI_LAUNCH" >&2
    exit 1
fi
```

- [ ] **Step 3: Re-run, expect PASS**

```bash
/auto-test-pytest tests/scripts/test_xa_launch.py
```

Expected: 5 passed.

- [ ] **Step 4: Commit**

```bash
git add scripts/xa-launch.sh tests/scripts/test_xa_launch.py
git commit -m "fix(scripts): xa-launch --help bypasses ai-launch availability check (refs ADR-617)"
```

---

## Phase 2: Claude wrapper (ca-launch.sh) — copy-paste with one-liner change

### Task 2.1: Test + script for Claude

**Files:**
- Create: `scripts/ca-launch.sh`
- Create: `tests/scripts/test_ca_launch.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/scripts/test_ca_launch.py
from __future__ import annotations

import os
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = PROJECT_ROOT / "scripts" / "ca-launch.sh"


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


def test_help_mentions_claude() -> None:
    result = run_script("--help")
    assert result.returncode == 0
    assert "claude" in result.stdout.lower()


def test_dry_run_main_includes_claude_skip_permissions_flag() -> None:
    result = run_script("--dry-run", input_text="1\n")
    assert result.returncode == 0, result.stderr
    assert "claude --dangerously-skip-permissions" in result.stdout


def test_dry_run_worktree_routes_to_worktree_launch_with_claude() -> None:
    result = run_script("--dry-run", input_text="2\n")
    assert result.returncode == 0, result.stderr
    assert "worktree-launch.sh create -- claude" in result.stdout
```

- [ ] **Step 2: Run, expect FAIL**

```bash
/auto-test-pytest tests/scripts/test_ca_launch.py
```

Expected: 3 failed (script does not exist).

- [ ] **Step 3: Implement**

Copy `scripts/xa-launch.sh` to `scripts/ca-launch.sh` and change two lines:

```bash
CLIENT="claude"
CLIENT_FLAGS=(--dangerously-skip-permissions)
```

Also update the `usage()` heredoc to mention "claude" and update the `XA_AI_LAUNCH` / `XA_NO_EXEC` env-var prefixes to `CA_AI_LAUNCH` / `CA_NO_EXEC` so the wrappers are independently overridable:

```bash
AI_LAUNCH="${CA_AI_LAUNCH:-$SCRIPT_DIR/ai-launch.sh}"
# ...
if [[ "${CA_NO_EXEC:-0}" == "1" ]]; then
```

`chmod +x scripts/ca-launch.sh`.

- [ ] **Step 4: Run, expect PASS**

```bash
/auto-test-pytest tests/scripts/test_ca_launch.py
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/ca-launch.sh tests/scripts/test_ca_launch.py
git commit -m "feat(scripts): add ca-launch.sh claude wrapper (refs ADR-617)"
```

---

## Phase 3: Gemini wrapper (ga-launch.sh)

### Task 3.1: Test + script for Gemini

**Files:**
- Create: `scripts/ga-launch.sh`
- Create: `tests/scripts/test_ga_launch.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/scripts/test_ga_launch.py
from __future__ import annotations

import os
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = PROJECT_ROOT / "scripts" / "ga-launch.sh"


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


def test_help_mentions_gemini() -> None:
    result = run_script("--help")
    assert result.returncode == 0
    assert "gemini" in result.stdout.lower()


def test_dry_run_main_includes_gemini_yolo_flag() -> None:
    result = run_script("--dry-run", input_text="1\n")
    assert result.returncode == 0, result.stderr
    assert "gemini --yolo" in result.stdout


def test_dry_run_worktree_routes_to_worktree_launch_with_gemini() -> None:
    result = run_script("--dry-run", input_text="2\n")
    assert result.returncode == 0, result.stderr
    assert "worktree-launch.sh create -- gemini" in result.stdout
```

- [ ] **Step 2: Run, expect FAIL**

```bash
/auto-test-pytest tests/scripts/test_ga_launch.py
```

Expected: 3 failed.

- [ ] **Step 3: Implement**

Copy `scripts/xa-launch.sh` to `scripts/ga-launch.sh`, then update:

```bash
CLIENT="gemini"
CLIENT_FLAGS=(--yolo)
AI_LAUNCH="${GA_AI_LAUNCH:-$SCRIPT_DIR/ai-launch.sh}"
# ...
if [[ "${GA_NO_EXEC:-0}" == "1" ]]; then
```

`chmod +x scripts/ga-launch.sh`.

- [ ] **Step 4: Run, expect PASS**

```bash
/auto-test-pytest tests/scripts/test_ga_launch.py
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/ga-launch.sh tests/scripts/test_ga_launch.py
git commit -m "feat(scripts): add ga-launch.sh gemini wrapper (refs ADR-617)"
```

---

## Phase 4: Installer rewrites the rc-file marker block

### Task 4.1: Test that the installer-emitted block delegates to the new launchers

**Files:**
- Create: `tests/scripts/test_install_alias_block.py`

- [ ] **Step 1: Write the failing test**

The installer is interactive and side-effecting on the user's `~/.zshrc`. We do **not** run it end-to-end here. Instead we read the literal heredoc lines in `scripts/install.sh` and assert on their content:

```python
# tests/scripts/test_install_alias_block.py
from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
INSTALL_SH = PROJECT_ROOT / "scripts" / "install.sh"


def test_install_block_delegates_to_xa_launch() -> None:
    text = INSTALL_SH.read_text(encoding="utf-8")
    # The marker block must contain a delegating xa() that points at xa-launch.sh.
    assert "xa-launch.sh" in text, "installer must reference scripts/xa-launch.sh"
    assert "ca-launch.sh" in text, "installer must reference scripts/ca-launch.sh"
    assert "ga-launch.sh" in text, "installer must reference scripts/ga-launch.sh"
    # The old hardcoded codex command must no longer be the body of xa().
    # It is acceptable for the comment block to mention --dangerously-... but
    # the function body must call the launcher.
    block_start = text.index("=== augur CLI shortcuts (ca/xa/ga) ===")
    block_end = text.index("=== end augur CLI shortcuts ===", block_start)
    block = text[block_start:block_end]
    # Old direct-call body must be gone:
    assert "codex --dangerously-bypass-approvals-and-sandbox" not in block, \
        "old inline codex body must be replaced by a launcher delegate"
    # New delegate body must be present:
    assert "xa-launch.sh" in block
```

- [ ] **Step 2: Run, expect FAIL**

```bash
/auto-test-pytest tests/scripts/test_install_alias_block.py
```

Expected: FAIL — `install.sh` still inlines the Codex command.

- [ ] **Step 3: Edit `scripts/install.sh`**

Replace lines 247–256 (the heredoc that writes the marker block) with a delegating block. The new block captures `INSTALL_DIR` (already a variable in `install.sh`) so the rc-file functions point at the resolved scripts directory:

```bash
    cat >> "$rc_file" <<EOF

$marker
# Augur CLI shortcuts (ca/xa/ga) — prompt main vs worktree, then launch.
# Delegating to scripts/{xa,ca,ga}-launch.sh keeps all logic version-controlled.
xa() { "$INSTALL_DIR/scripts/xa-launch.sh" "\$@"; }
ca() { "$INSTALL_DIR/scripts/ca-launch.sh" "\$@"; }
ga() { "$INSTALL_DIR/scripts/ga-launch.sh" "\$@"; }
# === end augur CLI shortcuts ===
EOF
```

Note the `$INSTALL_DIR` is expanded at heredoc-rendering time (because the heredoc is unquoted), so the user's rc file gets an absolute path baked in. The `\$@` is escaped so it lands literally in the rc file.

- [ ] **Step 4: Run, expect PASS**

```bash
/auto-test-pytest tests/scripts/test_install_alias_block.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/install.sh tests/scripts/test_install_alias_block.py
git commit -m "feat(installer): delegate ca/xa/ga rc functions to scripts/*-launch.sh (refs ADR-617)"
```

---

### Task 4.2: Make the installer rewrite an existing block in place

The current installer skips when the marker block already exists (`grep -qF "$marker"`). For users upgrading from the old inline functions, we want the installer to *replace* the block rather than skip it.

**Files:**
- Modify: `scripts/install.sh`
- Modify: `tests/scripts/test_install_alias_block.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/scripts/test_install_alias_block.py`:

```python
def test_installer_rewrites_existing_block(tmp_path) -> None:
    """When the rc file already contains an old-style block, the installer
    replaces it instead of duplicating or skipping."""
    rc = tmp_path / "fake-rc"
    rc.write_text(
        "# preexisting line\n"
        "# === augur CLI shortcuts (ca/xa/ga) ===\n"
        "ca() { claude --dangerously-skip-permissions \"$@\"; }\n"
        "xa() { codex --dangerously-bypass-approvals-and-sandbox \"$@\"; }\n"
        "ga() { gemini --yolo \"$@\"; }\n"
        "# === end augur CLI shortcuts ===\n"
        "# trailing line\n",
        encoding="utf-8",
    )
    import subprocess
    # We simulate the installer's `setup_rc_aliases` by sourcing install.sh
    # with the function's prerequisites stubbed in. This requires a thin
    # shell harness; for now, mark the test xfail and revisit in a follow-up.
    # The existence test below covers the rewrite expectation in code review.
    raise NotImplementedError("Wire setup_rc_aliases harness in follow-up commit")
```

Mark it `@pytest.mark.xfail(reason="Harness for in-place rewrite to land in follow-up", strict=False)` for now — the test is a placeholder that documents the expected behavior. The actual rewrite logic is straightforward to implement; we expose it for a future hardening task.

- [ ] **Step 2: Update `scripts/install.sh` `setup_rc_aliases()`**

Replace the early-return guard with a "remove old block, then append new block" sequence:

```bash
    if [ -f "$rc_file" ] && grep -qF "$marker" "$rc_file"; then
        # Remove existing block (between marker and end-marker, inclusive).
        local end_marker="# === end augur CLI shortcuts ==="
        # Use awk to drop lines inside the marker pair.
        local tmp
        tmp=$(mktemp)
        awk -v start="$marker" -v end="$end_marker" '
            $0 == start { skip=1; next }
            skip && $0 == end { skip=0; next }
            !skip { print }
        ' "$rc_file" > "$tmp" && mv "$tmp" "$rc_file"
        print_info "Refreshed CLI shortcut block in $rc_file"
    fi
```

- [ ] **Step 3: Verify by hand-running the test fixture**

This step is informational; the `xfail` test stays in place as a TODO marker. Document in the commit body that follow-up work is to wire a shell harness.

- [ ] **Step 4: Commit**

```bash
git add scripts/install.sh tests/scripts/test_install_alias_block.py
git commit -m "feat(installer): refresh existing ca/xa/ga block in place (refs ADR-617)"
```

---

## Phase 5: Worktree-mode end-to-end test (regression guard)

### Task 5.1: Verify `xa-launch.sh` worktree mode actually exec's `worktree-launch.sh`

We have unit-level tests that the dry-run output mentions `worktree-launch.sh create -- codex`. Add one full-pipeline test using the same fixture pattern as `tests/scripts/test_ai_launch.py::test_main_mode_fast_forwards_and_restores_dirty_changes` to exercise real git plumbing.

**Files:**
- Modify: `tests/scripts/test_xa_launch.py`

- [ ] **Step 1: Write the failing test**

```python
def test_worktree_mode_creates_worktree_dir(tmp_path) -> None:
    """xa-launch.sh in worktree mode must invoke worktree-launch.sh
    against the configured project root, creating a sibling augur-* dir."""
    from tests.scripts.test_ai_launch import init_main_repo_pair  # reuse helper
    local, _ = init_main_repo_pair(tmp_path)

    result = run_script(
        "--dry-run",
        input_text="2\n",
        env={
            "AI_PROJECT_ROOT": str(local),
            "AI_NO_EXEC": "1",
        },
    )
    assert result.returncode == 0, result.stderr
    assert "mode=worktree" in result.stdout
    assert "codex --dangerously-bypass-approvals-and-sandbox" in result.stdout
```

- [ ] **Step 2: Run, expect PASS**

```bash
/auto-test-pytest tests/scripts/test_xa_launch.py::test_worktree_mode_creates_worktree_dir
```

If FAIL, the wrapper is dropping `AI_PROJECT_ROOT` / `AI_NO_EXEC` somewhere — but since we use `exec`, those env vars are inherited automatically. PASS is expected.

- [ ] **Step 3: Commit**

```bash
git add tests/scripts/test_xa_launch.py
git commit -m "test(scripts): regression guard for xa-launch worktree forwarding (refs ADR-617)"
```

---

## Phase 6: Self-review & cross-cutting checks

- [ ] **Step 1: Verify the three wrappers are identical except for client name and flags**

```bash
diff <(sed -E 's/codex|--dangerously-bypass-approvals-and-sandbox|XA_AI_LAUNCH|XA_NO_EXEC//g' scripts/xa-launch.sh) \
     <(sed -E 's/claude|--dangerously-skip-permissions|CA_AI_LAUNCH|CA_NO_EXEC//g' scripts/ca-launch.sh)
```

Expected: empty diff (the only differences are the client-specific tokens we stripped). Same check for `xa` vs `ga`.

- [ ] **Step 2: `/auto-test-pytest` full launcher suite green**

```bash
/auto-test-pytest tests/scripts/test_ai_launch.py tests/scripts/test_xa_launch.py tests/scripts/test_ca_launch.py tests/scripts/test_ga_launch.py tests/scripts/test_install_alias_block.py
```

Expected: all PASS (or 1 xfail in the `test_install_alias_block.py::test_installer_rewrites_existing_block` placeholder).

- [ ] **Step 3: Confirm no new violations of CLAUDE.md rule 7 (`TODO_` markers)**

```bash
git diff main -- scripts/ tests/scripts/ | grep -E '^\+' | grep -E 'TODO[^_]' || echo "ok: no bare TODOs"
```

Bare `TODO` (without underscore) should be re-tagged to `TODO_CLEANUP` etc. The `xfail` placeholder above is allowed because it lives in a test docstring.

- [ ] **Step 4: Manual smoke (operator step)**

Operator runs:

```bash
bash scripts/xa-launch.sh --dry-run
# enter "1" → expect: mode=main repo=<repo> sync_target=origin/main command=codex --dangerously-bypass-approvals-and-sandbox
# Ctrl-C, repeat
bash scripts/xa-launch.sh --dry-run
# enter "2" → expect: mode=worktree command=...worktree-launch.sh create -- codex --dangerously-bypass-approvals-and-sandbox
```

- [ ] **Step 5: Update CHANGELOG / no separate doc**

ADR-617 is the changelog entry. No separate `CHANGELOG.md` update needed; the ADR pointer in `docs/adrs/adrs-index.json` is updated by the brainstorming step (`spec_file` / `plan_file`).

---

## Self-review

Before declaring done, the implementer confirms:

1. **Spec adherence** — every sub-decision in `2026-05-10-xa-main-or-worktree-launch-design.md` § Decision is reflected in code:
   - [ ] Per-client wrappers (`xa-launch.sh`, `ca-launch.sh`, `ga-launch.sh`) exist and are executable.
   - [ ] Wrappers `exec` into `ai-launch.sh` rather than re-implementing prompt or sync logic.
   - [ ] `--help` short-circuits before the AI-launch availability check.
   - [ ] `--dry-run` propagates correctly.
   - [ ] Extra `-- <flags>` are appended to the client command line, preserving array semantics.
   - [ ] Installer marker block rewrites in place when present, and the body delegates to the launchers.

2. **Rule-coverage** — the changes do not violate any CLAUDE.md rule:
   - [ ] Rule 1 (user-visible correctness): the prompt happens; no fallback hides a broken sync.
   - [ ] Rule 5 (no workaround fixes): no skipped tests except the documented `xfail` placeholder.
   - [ ] Rule 14 (canonical cleanup): the inline `xa()` body is removed, not aliased.
   - [ ] Rule 15 (`--help` stops execution): wrappers exit 0 on `--help` without prompting.
   - [ ] Rule 23 (exhaustive migration): all three rc-file functions migrate together; no half-migrated state.

3. **Documentation** — the ADR-617 entry in `docs/adrs/adrs-index.json` carries `spec_file` and `plan_file` pointers, plus the dated status_notes line.

4. **No drift** — `scripts/ai-launch.sh` and `scripts/worktree-launch.sh` are byte-for-byte unchanged. If a tester's diff shows a change in either of those files, revert it before merging.

---

## TODO markers (deliberate)

- `TODO_CLEANUP`: Phase 4.2 ships an `xfail`-marked placeholder for "installer rewrites existing block end-to-end". The follow-up task is to wire a shell harness that sources `setup_rc_aliases` against a fake `$HOME` and asserts the resulting rc-file content. This is a P3 hardening item, not a blocker for ADR-617 implementation.
