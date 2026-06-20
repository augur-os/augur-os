# /dev-clean pnpm-store-prune Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `pnpm-store-prune` to `/dev-clean` Tier 2 so `--include-git` / `--all` invocations reclaim unreferenced versions from the global pnpm content-addressable store (measured: ~2.4 GB on a long-lived dev machine).

**Architecture:** One new `Operation` record in the existing Tier 2 dispatch list. Pure Python wrapping `pnpm store prune`. Reuses the existing `ReclaimReport` shape so table + JSON output gain the row automatically.

**Tech Stack:** Python 3.12, pytest, pnpm 10.32.1, existing `/dev-clean` script.

**Spec:** [`docs/superpowers/specs/2026-05-16-dev-clean-pnpm-store-prune-design.md`](../specs/2026-05-16-dev-clean-pnpm-store-prune-design.md).

---

## File Structure

| File | Role | New / Modified |
|---|---|---|
| `shared-vault/skills/platform-admin/scripts/dev_clean.py` (or wherever the dispatch lives) | Add `_prune_pnpm_store` function + Tier 2 dispatch entry | Modified |
| `shared-vault/skills/platform-admin/scripts/dev_clean_pnpm_store.py` (optional split) | If isolation wanted, the function can live in its own module | Created (optional) |
| `tests/scripts/test_dev_clean_pnpm_store.py` | Unit + integration tests | **Created** |
| `shared-vault/skills/platform-admin/commands/dev-clean.md` | Add the new row to the "What Gets Reclaimed" table; extend the "After `/dev-clean`, the next `pnpm install` / `uv sync` may take longer" note | Modified |
| `shared-vault/skills/platform-admin/references/dev-clean-execution-steps.md` (if exists) | Mention the new Tier 2 op | Modified |

---

## Task 1: Locate the dev-clean dispatch + existing Tier 2 pattern

**Files:**
- Read: `shared-vault/skills/platform-admin/scripts/dev_clean*.py` (or equivalent — locate via `grep -rln "git-lfs-prune\|git_lfs_prune" shared-vault/skills/platform-admin/scripts/`)
- Read: the `Operation` / `ReclaimReport` dataclass definitions

- [ ] **Step 1: Find the file**

```bash
grep -rln "git-lfs-prune\|git_lfs_prune\|TIER_2_OPERATIONS\|tier 2" shared-vault/skills/platform-admin/scripts/ shared-vault/skills/platform-admin/commands/
```

Expected: locates the script that owns the dispatch table (likely `dev_clean.py` or `tools/dev_clean/cli.py`).

- [ ] **Step 2: Read the file**

Read the existing `git_lfs_prune` and `git_gc` operation definitions. Note:
- the dataclass shape (`ReclaimReport`, `Operation`)
- where `--dry-run` is checked
- how the operation list is registered
- how the JSON / table outputs are produced

- [ ] **Step 3: Note any conventions**

Augur-specific conventions to follow:
- `from src.config.paths import get_project_root` for any path resolution
- subprocess timeout pattern (look for `subprocess.run(..., timeout=...)`)
- error format (Incident-style or operation-status-style)

---

## Task 2: Write failing unit tests

**Files:**
- Create: `tests/scripts/test_dev_clean_pnpm_store.py`

- [ ] **Step 1: Write the failing tests**

```python
"""Unit tests for the pnpm store prune Tier 2 operation in /dev-clean."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from src.config.paths import get_project_root

PROJECT_ROOT = get_project_root()
DEV_CLEAN_DIR = PROJECT_ROOT / "shared-vault" / "skills" / "platform-admin" / "scripts"
if str(DEV_CLEAN_DIR) not in sys.path:
    sys.path.insert(0, str(DEV_CLEAN_DIR))

import dev_clean  # noqa: E402 — adjust import name to match actual module


def test_prune_pnpm_store_skipped_when_pnpm_missing(monkeypatch):
    monkeypatch.setattr(dev_clean.shutil, "which", lambda tool: None)
    report = dev_clean._prune_pnpm_store(dry_run=False)
    assert report.status == "skipped"
    assert "pnpm not found" in report.message.lower()


def test_prune_pnpm_store_parses_pnpm_output(monkeypatch):
    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(
            cmd, 0,
            "Removed all cached metadata files\nRemoved 100 files\nRemoved 5 packages\n",
            "",
        )
    monkeypatch.setattr(dev_clean.shutil, "which", lambda tool: "/usr/local/bin/pnpm")
    monkeypatch.setattr(dev_clean.subprocess, "run", fake_run)
    report = dev_clean._prune_pnpm_store(dry_run=False)
    assert report.status == "reclaimed"
    assert report.files_removed == 100
    assert report.packages_removed == 5


def test_prune_pnpm_store_failed_on_nonzero_exit(monkeypatch):
    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 1, "", "ENOSPC: out of space\n")
    monkeypatch.setattr(dev_clean.shutil, "which", lambda tool: "/usr/local/bin/pnpm")
    monkeypatch.setattr(dev_clean.subprocess, "run", fake_run)
    report = dev_clean._prune_pnpm_store(dry_run=False)
    assert report.status == "failed"
    assert "out of space" in report.message.lower()


def test_prune_pnpm_store_dry_run_does_not_mutate(monkeypatch):
    invocations = []
    def fake_run(cmd, **kwargs):
        invocations.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, "Would remove 50 files\n", "")
    monkeypatch.setattr(dev_clean.shutil, "which", lambda tool: "/usr/local/bin/pnpm")
    monkeypatch.setattr(dev_clean.subprocess, "run", fake_run)
    report = dev_clean._prune_pnpm_store(dry_run=True)
    assert report.status == "dry-run"
    # Confirm `--dry-run` was passed to pnpm
    assert any("--dry-run" in c for c in invocations)


def test_prune_pnpm_store_uses_corepack_when_pnpm_missing_but_corepack_present(monkeypatch):
    which_table = {"pnpm": None, "corepack": "/usr/local/bin/corepack"}
    monkeypatch.setattr(dev_clean.shutil, "which", lambda tool: which_table.get(tool))
    captured = {}
    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, "Removed 0 files\nRemoved 0 packages\n", "")
    monkeypatch.setattr(dev_clean.subprocess, "run", fake_run)
    report = dev_clean._prune_pnpm_store(dry_run=False)
    assert report.status == "reclaimed"
    assert captured["cmd"][:2] == ["/usr/local/bin/corepack", "pnpm"]


def test_prune_pnpm_store_in_tier_2_dispatch():
    # Confirm the new operation is registered in the Tier 2 list
    names = [op.name for op in dev_clean.TIER_2_OPERATIONS]
    assert "pnpm-store-prune" in names
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
/auto-test-pytest tests/scripts/test_dev_clean_pnpm_store.py
```

Expected: FAIL — `AttributeError: module 'dev_clean' has no attribute '_prune_pnpm_store'`.

---

## Task 3: Implement `_prune_pnpm_store`

**Files:**
- Modify: `shared-vault/skills/platform-admin/scripts/dev_clean.py` (or actual file)

- [ ] **Step 1: Add the implementation**

Add near the other Tier 2 operations (after `git_gc`):

```python
def _prune_pnpm_store(dry_run: bool) -> ReclaimReport:
    """Tier 2 operation: pnpm store prune — reclaim unreferenced package versions."""
    pnpm_cmd: list[str] | None = None
    pnpm = shutil.which("pnpm")
    if pnpm is not None:
        pnpm_cmd = [pnpm]
    else:
        corepack = shutil.which("corepack")
        if corepack is None:
            return ReclaimReport(
                name="pnpm-store-prune",
                tier=2,
                status="skipped",
                message=(
                    "pnpm not found (neither pnpm nor corepack on PATH). "
                    "Run `corepack enable && corepack prepare pnpm@latest --activate`."
                ),
                bytes_reclaimed=0,
                files_removed=0,
                packages_removed=0,
            )
        pnpm_cmd = [corepack, "pnpm"]

    cmd = pnpm_cmd + ["store", "prune"]
    if dry_run:
        cmd.append("--dry-run")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired:
        return ReclaimReport(
            name="pnpm-store-prune",
            tier=2,
            status="failed",
            message="pnpm store prune timed out after 300s",
            bytes_reclaimed=0,
        )

    if result.returncode != 0:
        return ReclaimReport(
            name="pnpm-store-prune",
            tier=2,
            status="failed",
            message=f"pnpm exited {result.returncode}: {(result.stderr or '').strip()[:200]}",
            bytes_reclaimed=0,
        )

    # Parse "Removed N files\nRemoved N packages\n" output (also handles dry-run "Would remove...")
    import re
    files_match = re.search(r"(?:Removed|Would remove)\s+(\d+)\s+files", result.stdout)
    packages_match = re.search(r"(?:Removed|Would remove)\s+(\d+)\s+packages", result.stdout)
    files_removed = int(files_match.group(1)) if files_match else 0
    packages_removed = int(packages_match.group(1)) if packages_match else 0

    return ReclaimReport(
        name="pnpm-store-prune",
        tier=2,
        status="dry-run" if dry_run else "reclaimed",
        message=(
            f"{'Would prune' if dry_run else 'Pruned'} {files_removed} files "
            f"across {packages_removed} packages from the pnpm store"
        ),
        files_removed=files_removed,
        packages_removed=packages_removed,
        # bytes_reclaimed left to the caller to measure via df-delta if desired;
        # the file count is a structurally-meaningful signal even without bytes.
        bytes_reclaimed=0,
    )
```

- [ ] **Step 2: Register in the Tier 2 dispatch list**

Find the `TIER_2_OPERATIONS = [...]` list (or equivalent) and add an entry:

```python
TIER_2_OPERATIONS = [
    Operation(name="git-lfs-prune", apply_fn=_git_lfs_prune, ...),
    Operation(name="git-gc", apply_fn=_git_gc, ...),
    Operation(name="pnpm-store-prune", apply_fn=_prune_pnpm_store, dry_run_fn=lambda: _prune_pnpm_store(dry_run=True)),
]
```

(Match the exact dataclass shape the existing entries use — read the existing code first.)

- [ ] **Step 3: If `ReclaimReport` doesn't have `files_removed` / `packages_removed` fields, add them**

Optional fields (default 0) so other operations don't need to populate them. Keep backward-compatible with the JSON output.

- [ ] **Step 4: Run tests to verify pass**

```bash
/auto-test-pytest tests/scripts/test_dev_clean_pnpm_store.py
```

Expected: 6 tests PASS.

---

## Task 4: Update dev-clean.md command docs

**Files:**
- Modify: `shared-vault/skills/platform-admin/commands/dev-clean.md`

- [ ] **Step 1: Add the row to "What Gets Reclaimed"**

```markdown
| 2 | `pnpm-store-prune` | Unreferenced versions in `~/Library/pnpm/store/` (or platform equivalent) | `pnpm store prune` only removes versions no current node_modules references; next install re-downloads |
```

- [ ] **Step 2: Extend the "next install may take longer" note**

Reword the existing Gotcha #3:

> After `/dev-clean`, the next `pnpm install` / `uv sync` may take longer
>
> That is expected — caches were emptied. The actual installed `node_modules` and `.venv` are not touched. **`/dev-clean --all` also prunes the global pnpm content-addressable store**, so the next `pnpm install` may re-download some packages from the registry (typically 10-30s for a fresh dashboard install).

- [ ] **Step 3: Commit**

---

## Task 5: Real-data verification (CLAUDE.md rule #34)

**Files:** none — runs on the developer's actual machine.

- [ ] **Step 1: Capture baseline**

```bash
df -h /
du -A -k -s ~/Library/pnpm/store | awk '{print int($1/1024) " MB"}'
```

- [ ] **Step 2: Run the new dev-clean operation**

```bash
/dev-clean --dry-run --all  # confirm the new row appears
/dev-clean --all            # actually prune
```

- [ ] **Step 3: Measure delta**

```bash
df -h /
du -A -k -s ~/Library/pnpm/store | awk '{print int($1/1024) " MB"}'
```

- [ ] **Step 4: Sanity — existing worktrees still functional**

For each non-empty worktree:
```bash
node -e "require('next/package.json')"  # in apps/dashboard
```

Should succeed regardless of store state because APFS / hardlink semantics keep the bytes alive in node_modules.

- [ ] **Step 5: Paste evidence into merge commit**

Concrete numbers (store MB before/after, volume MB before/after, file counts) go in the commit message.

---

## Self-Review Notes

Spec coverage check:

| Spec component | Task(s) |
|---|---|
| New `_prune_pnpm_store` function | Task 3 |
| Tier 2 dispatch registration | Task 3 |
| Dry-run + apply paths | Tasks 2-3 (tests + impl) |
| Cross-OS shell-neutrality | Task 3 (pure Python, pnpm handles platform) |
| Documentation update | Task 4 |
| Real-data validation | Task 5 |

Out of scope: pruning `~/.npm/_cacache/`, pruning `~/Library/Caches/Augur/`, modifying `pnpm config get store-dir`.
