# Worktree Global Identity Isolation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop parallel Augur sessions from repointing shared CLI, editable install, MCP, and client-config identity to active worktrees.

**Architecture:** Main checkout is the installation authority for shared/global identity. Worktrees may run process-local overlays, but global installs and persistent client configs must resolve to main under a cross-session lock. Drift detection reports and repairs real shared state before mixed-root execution can continue.

**Tech Stack:** Python 3.12, git worktree metadata, Augur path helpers, shell-neutral Python scripts, POSIX shell and PowerShell launcher adapters, existing MCP config writers, existing sync_agents adapters, repo githooks and GitHub Actions.

**Implementation evidence (2026-05-24):** Completed. The live pre-repair audit found 9 shared identity drift issues in the shared `.venv` rooted at the active worktree; authority-root repair rewrote editable install and `.pth` state to the main checkout; a fresh post-repair audit reported `ok=true`; the active worktree still receives `AUGUR_PROJECT_ROOT=<active worktree>` as a process-local overlay with `can_mutate_global=False`. Focused identity tests passed (`28 passed`), command-surface lint coverage passed (`15 passed`), and the full monolithic Python suite passed (`2808 passed, 80 skipped`).

---

## Source Spec

- Design: `docs/superpowers/specs/2026-05-24-worktree-global-identity-isolation-design.md`
- Related implementation evidence: `docs/adrs/ADR-778-test-suite-module-identity-isolation.md`

## File Structure

- Create `docs/adrs/ADR-779-worktree-global-identity-isolation.md` as the governing ADR.
- Create `src/config/runtime_identity.py` for authority-root detection, mutation guarding, worktree overlays, and the global mutation lock.
- Modify `src/config/worktrees.py` to delegate legacy helpers to `runtime_identity.py`.
- Create `src/config/global_identity_drift.py` for editable install, `.pth`, import-spec, CLI, and MCP-config drift scans.
- Create `scripts/check_global_identity_drift.py` as the human and automation entrypoint for audit and repair.
- Modify `scripts/configure_mcp.py` so persistent global config writes resolve through the authority root and global lock.
- Modify `project-brain/capabilities/skills/ai/scripts/sync_agents/templates.py` and global-writing adapters so generated persistent config uses authority identity.
- Modify `project-brain/capabilities/skills/ai/scripts/sync_agents/adapters/codex.py` to remove the worktree global-write escape hatch and anchor global Codex config to authority root.
- Modify `scripts/augur-codex-mcp` and `scripts/augur-codex-mcp.ps1` so persistent launcher config does not choose `cwd` as root unless a process-local overlay env var asks for it.
- Create `.githooks/global-identity-staged-scan.sh` and invoke it from `.githooks/pre-commit`.
- Modify `.github/workflows/ci-tests.yml` to run identity unit tests and the fixture-based drift guard.
- Create tests:
  - `tests/config/test_runtime_identity.py`
  - `tests/config/test_global_identity_drift.py`
  - `tests/scripts/test_check_global_identity_drift.py`
  - `tests/sync_agents/test_global_identity_sync.py`
  - `tests/cli/test_codex_mcp_launcher_identity.py`
  - `tests/test_worktree_global_identity_isolation.py`

## Task 1: Promote The Design To ADR-779

**Files:**
- Create: `docs/adrs/ADR-779-worktree-global-identity-isolation.md`
- Modify: `docs/generated/adr-index.md`
- Test: ADR post-write/index scripts

- [ ] **Step 1: Create the ADR file**

Create `docs/adrs/ADR-779-worktree-global-identity-isolation.md` with this content:

```markdown
---
status: Accepted
date: 2026-05-24
deciders:
  - gsannikov
related: [778, 759]
hub: null
tags: [worktrees, cli, mcp, isolation, runtime, tooling]
superseded_by: null
spec_file: 2026-05-24-worktree-global-identity-isolation-design.md
plan_file: 2026-05-24-worktree-global-identity-isolation.md
---

# ADR-779: Worktree Global Identity Isolation

## Context

Parallel Augur sessions can run from multiple git worktrees at the same time.
Before this ADR, a worktree could run install or sync commands that rewrote
shared runtime identity to itself. Shared `.venv` editable installs, `.pth`
files, global `aug`, persistent MCP configs, and global client config could then
resolve to a stale or unrelated worktree.

ADR-778 fixed module identity isolation inside the Python test process. This ADR
protects the developer runtime so local shared identity cannot reintroduce stale
worktree packages or MCP launch roots.

## Decision

The main checkout is the installation authority for shared/global identity.
Worktree identity is process-local only.

Shared editable installs, `.pth` files, global CLI links, persistent MCP config,
and global client config must point to the main checkout. Worktree execution
uses explicit process overlays such as `AUGUR_PROJECT_ROOT`, `AUGUR_ROOT`, and
scoped `PYTHONPATH` only for that process or generated session-local config.

Global identity mutations are guarded by a shared filesystem lock. Worktree
global mutations are blocked unless the command is an explicitly allowed repair
or sync path that delegates to the main authority root.

## Consequences

- Parallel sessions can work from different worktrees without stealing `aug` or
  MCP runtime identity from each other.
- Persistent client config points to main, while session-local worktree config
  remains allowed.
- Drift becomes diagnosable by a single audit command.
- Repair rewrites shared identity to main and reports the changed surfaces.
- Commands that previously relied on a worktree mutating global install state
  must switch to process-local overlays.

## Acceptance Gate

- Unit tests prove authority-root detection, mutation guard behavior, lock
  serialization, overlay generation, and drift scanning.
- A two-worktree integration simulation proves concurrent install-like and
  sync-like operations cannot stamp shared identity with worktree paths.
- A live audit proves shared editable installs, `.pth`, import specs, global
  `aug`, and persistent MCP configs do not point at `augur-wt-*`.
- Persistent global client configs point to main after sync.
- Worktree-local MCP and CLI execution still runs worktree code through overlays.

## Impact Manifest

```yaml
impact:
  paths_renamed: []
  apis_changed:
    - "src.config.runtime_identity.resolve_runtime_identity"
    - "src.config.runtime_identity.GlobalMutationGuard"
    - "src.config.global_identity_drift.scan_global_identity_drift"
  patterns_deprecated:
    - "worktree process mutating shared editable installs"
    - "persistent global client config pointing at linked worktrees"
    - "Codex MCP launcher selecting cwd before explicit overlay/configured roots"
  files_affected:
    - src/config/runtime_identity.py
    - src/config/worktrees.py
    - src/config/global_identity_drift.py
    - scripts/check_global_identity_drift.py
    - scripts/configure_mcp.py
    - scripts/augur-codex-mcp
    - scripts/augur-codex-mcp.ps1
    - project-brain/capabilities/skills/ai/scripts/sync_agents/
    - .githooks/pre-commit
    - .github/workflows/ci-tests.yml
```
```

- [ ] **Step 2: Run the ADR post-write hooks**

Run:

```bash
.venv/bin/python .github/scripts/adr_upsert_live.py
.venv/bin/python .github/scripts/generate_adr_index.py
.venv/bin/python src/lib/index/unified_indexer.py --category adrs
PYTHONPATH=project-brain/capabilities .venv/bin/python -m skills.ai.scripts.sync_agents sync agents all
```

Expected:

```text
ADR index and generated agent ADR summaries include ADR-779.
No generated output points at an active worktree path.
```

- [ ] **Step 3: Commit the ADR checkpoint**

Run:

```bash
git add docs/adrs/ADR-779-worktree-global-identity-isolation.md docs/generated/adr-index.md
git add CODEX.md AGENTS.md CLAUDE.md GEMINI.md .github/copilot-instructions.md .codex/skills 2>/dev/null || true
git commit -m "Accept ADR-779 worktree global identity isolation"
```

Expected:

```text
Pre-commit checks pass.
Commit records the accepted ADR and generated ADR index updates.
```

## Task 2: Add Runtime Identity Foundation

**Files:**
- Create: `src/config/runtime_identity.py`
- Modify: `src/config/worktrees.py`
- Test: `tests/config/test_runtime_identity.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/config/test_runtime_identity.py`:

```python
from __future__ import annotations

import os
import threading
import time
from pathlib import Path

import pytest

from src.config.runtime_identity import (
    GlobalIdentityError,
    GlobalIdentityLock,
    GlobalMutationGuard,
    build_worktree_overlay_env,
    resolve_runtime_identity,
)


def _linked_worktree(tmp_path: Path) -> tuple[Path, Path]:
    main_root = tmp_path / "Augur"
    worktree_root = tmp_path / ".worktrees" / "feature"
    gitdir = main_root / ".git" / "worktrees" / "feature"
    gitdir.mkdir(parents=True)
    main_root.mkdir(parents=True)
    worktree_root.mkdir(parents=True)
    (main_root / "project.yaml").write_text("name: augur\n", encoding="utf-8")
    (worktree_root / "project.yaml").write_text("name: augur\n", encoding="utf-8")
    (worktree_root / ".git").write_text(f"gitdir: {gitdir}\n", encoding="utf-8")
    return main_root, worktree_root


def test_linked_worktree_identity_uses_main_authority(tmp_path: Path) -> None:
    main_root, worktree_root = _linked_worktree(tmp_path)

    identity = resolve_runtime_identity(worktree_root)

    assert identity.current_root == worktree_root.resolve()
    assert identity.authority_root == main_root.resolve()
    assert identity.main_root == main_root.resolve()
    assert identity.is_linked_worktree is True
    assert identity.can_mutate_global is False


def test_main_identity_can_mutate_global(tmp_path: Path) -> None:
    main_root = tmp_path / "Augur"
    main_root.mkdir()
    (main_root / ".git").mkdir()
    (main_root / "project.yaml").write_text("name: augur\n", encoding="utf-8")

    identity = resolve_runtime_identity(main_root)

    assert identity.authority_root == main_root.resolve()
    assert identity.is_linked_worktree is False
    assert identity.can_mutate_global is True


def test_mutation_guard_blocks_worktree_targeting_itself(tmp_path: Path) -> None:
    _main_root, worktree_root = _linked_worktree(tmp_path)
    identity = resolve_runtime_identity(worktree_root)

    with pytest.raises(GlobalIdentityError, match="worktree cannot mutate shared global identity"):
        with GlobalMutationGuard(identity, target_root=worktree_root, operation="editable-install"):
            raise AssertionError("guard did not block")


def test_mutation_guard_allows_delegated_sync_to_authority(tmp_path: Path) -> None:
    main_root, worktree_root = _linked_worktree(tmp_path)
    identity = resolve_runtime_identity(worktree_root)

    with GlobalMutationGuard(
        identity,
        target_root=main_root,
        operation="client-sync",
        allow_delegated=True,
    ):
        marker = "entered"

    assert marker == "entered"


def test_worktree_overlay_env_is_process_local(tmp_path: Path) -> None:
    main_root, worktree_root = _linked_worktree(tmp_path)
    identity = resolve_runtime_identity(worktree_root)

    env = build_worktree_overlay_env(identity, {"PYTHONPATH": "/outside"})

    assert env["AUGUR_PROJECT_ROOT"] == str(worktree_root.resolve())
    assert env["AUGUR_ROOT"] == str(worktree_root.resolve())
    assert str(worktree_root.resolve()) in env["PYTHONPATH"].split(os.pathsep)
    assert str(main_root.resolve()) not in env["PYTHONPATH"].split(os.pathsep)


def test_global_identity_lock_serializes_threads(tmp_path: Path) -> None:
    lock_path = tmp_path / "identity.lock"
    order: list[str] = []

    def first() -> None:
        with GlobalIdentityLock(lock_path):
            order.append("first-enter")
            time.sleep(0.05)
            order.append("first-exit")

    def second() -> None:
        time.sleep(0.01)
        with GlobalIdentityLock(lock_path):
            order.append("second-enter")

    t1 = threading.Thread(target=first)
    t2 = threading.Thread(target=second)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert order == ["first-enter", "first-exit", "second-enter"]
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run:

```bash
/auto-test-pytest tests/config/test_runtime_identity.py
```

Expected:

```text
The new tests fail because src.config.runtime_identity does not exist.
```

- [ ] **Step 3: Implement `src/config/runtime_identity.py`**

Create `src/config/runtime_identity.py`:

```python
"""Runtime identity helpers for main-owned global state and worktree overlays."""
from __future__ import annotations

import contextlib
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


class GlobalIdentityError(RuntimeError):
    """Raised when a command would mutate shared identity from an unsafe root."""


@dataclass(frozen=True)
class RuntimeIdentity:
    current_root: Path
    authority_root: Path
    main_root: Path | None
    is_linked_worktree: bool
    can_mutate_global: bool
    branch: str | None = None


@dataclass(frozen=True)
class WorktreeRecord:
    path: Path
    branch: str | None
    is_bare: bool = False


def _run_git(repo_root: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), *args],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    return result.stdout


def _parse_worktree_list(output: str) -> list[WorktreeRecord]:
    records: list[WorktreeRecord] = []
    current: dict[str, str | bool] = {}
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            if "worktree" in current:
                records.append(
                    WorktreeRecord(
                        path=Path(str(current["worktree"])).expanduser().resolve(),
                        branch=str(current["branch"]) if current.get("branch") else None,
                        is_bare=bool(current.get("bare")),
                    )
                )
            current = {}
            continue
        if line.startswith("worktree "):
            current["worktree"] = line.removeprefix("worktree ").strip()
        elif line.startswith("branch "):
            current["branch"] = line.removeprefix("branch ").strip().removeprefix("refs/heads/")
        elif line == "bare":
            current["bare"] = True
    if "worktree" in current:
        records.append(
            WorktreeRecord(
                path=Path(str(current["worktree"])).expanduser().resolve(),
                branch=str(current["branch"]) if current.get("branch") else None,
                is_bare=bool(current.get("bare")),
            )
        )
    return records


def _main_checkout_from_git_file(project_root: Path) -> Path | None:
    git_entry = project_root / ".git"
    if not git_entry.is_file():
        return None
    try:
        marker = git_entry.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not marker.startswith("gitdir:"):
        return None
    gitdir = Path(marker.split("gitdir:", 1)[1].strip()).expanduser()
    parts = gitdir.as_posix().split("/")
    if "worktrees" not in parts:
        return None
    worktrees_index = parts.index("worktrees")
    main_git_dir = Path("/".join(parts[:worktrees_index]))
    main_checkout = main_git_dir.parent
    if (main_checkout / "project.yaml").is_file() or (main_checkout / "pyproject.toml").is_file():
        return main_checkout.resolve()
    return None


def _branch_for(root: Path) -> str | None:
    output = _run_git(root, "branch", "--show-current")
    branch = output.strip() if output else ""
    return branch or None


def main_checkout_for_worktree(project_root: Path) -> Path | None:
    root = project_root.expanduser().resolve()
    output = _run_git(root, "worktree", "list", "--porcelain")
    if output:
        records = [record for record in _parse_worktree_list(output) if not record.is_bare]
        for record in records:
            if record.branch == "main" and record.path != root:
                return record.path
        for record in records:
            if record.path != root and (record.path / ".git").exists():
                return record.path
    return _main_checkout_from_git_file(root)


def resolve_runtime_identity(project_root: str | Path | None = None) -> RuntimeIdentity:
    root = Path(project_root or Path.cwd()).expanduser().resolve()
    main_root = main_checkout_for_worktree(root)
    is_linked = main_root is not None and main_root != root
    authority = (main_root or root).resolve()
    return RuntimeIdentity(
        current_root=root,
        authority_root=authority,
        main_root=main_root,
        is_linked_worktree=is_linked,
        can_mutate_global=not is_linked,
        branch=_branch_for(root),
    )


def global_mcp_project_root(project_root: str | Path | None = None) -> Path:
    return resolve_runtime_identity(project_root).authority_root


class GlobalMutationGuard:
    def __init__(
        self,
        identity: RuntimeIdentity,
        *,
        target_root: str | Path,
        operation: str,
        allow_delegated: bool = False,
    ) -> None:
        self.identity = identity
        self.target_root = Path(target_root).expanduser().resolve()
        self.operation = operation
        self.allow_delegated = allow_delegated

    def __enter__(self) -> "GlobalMutationGuard":
        authority = self.identity.authority_root.resolve()
        if self.target_root != authority:
            raise GlobalIdentityError(
                f"worktree cannot mutate shared global identity for {self.operation}: "
                f"target={self.target_root} authority={authority} current={self.identity.current_root}"
            )
        if self.identity.is_linked_worktree and not self.allow_delegated:
            raise GlobalIdentityError(
                f"worktree cannot mutate shared global identity for {self.operation}: "
                f"current={self.identity.current_root} authority={authority}"
            )
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def build_worktree_overlay_env(
    identity: RuntimeIdentity,
    base_env: dict[str, str] | None = None,
) -> dict[str, str]:
    env = dict(base_env or os.environ)
    root = identity.current_root
    canonical = [
        str(root / "project-brain" / "capabilities"),
        str(root),
        str(root / "src" / "mcp"),
    ]
    kept: list[str] = []
    for entry in (env.get("PYTHONPATH") or "").split(os.pathsep):
        if not entry or entry in canonical:
            continue
        kept.append(entry)
    env["AUGUR_PROJECT_ROOT"] = str(root)
    env["AUGUR_ROOT"] = str(root)
    env["AUGUR_CORE"] = str(root)
    env["AUGUR_REPO"] = str(root)
    env["PYTHONPATH"] = os.pathsep.join([*canonical, *kept])
    return env


class GlobalIdentityLock:
    def __init__(self, lock_path: Path, *, timeout_sec: float = 30.0) -> None:
        self.lock_path = lock_path
        self.timeout_sec = timeout_sec
        self._fh = None

    def __enter__(self) -> "GlobalIdentityLock":
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = self.lock_path.open("a+")
        deadline = time.monotonic() + self.timeout_sec
        while True:
            try:
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(self._fh.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                return self
            except OSError:
                if time.monotonic() >= deadline:
                    raise GlobalIdentityError(f"timed out waiting for global identity lock {self.lock_path}")
                time.sleep(0.05)

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._fh is None:
            return
        with contextlib.suppress(OSError):
            if os.name == "nt":
                import msvcrt

                self._fh.seek(0)
                msvcrt.locking(self._fh.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
        self._fh.close()
        self._fh = None


def default_global_identity_lock_path() -> Path:
    try:
        from src.config.paths import get_runtime_dir

        return get_runtime_dir() / "global-identity.lock"
    except Exception:
        return Path.home() / ".augur" / "state" / "global-identity.lock"
```

- [ ] **Step 4: Update `src/config/worktrees.py` compatibility helpers**

Replace `src/config/worktrees.py` with:

```python
"""Git worktree root helpers for generated runtime projections."""
from __future__ import annotations

from pathlib import Path

from src.config.runtime_identity import (
    global_mcp_project_root,
    main_checkout_for_worktree,
)


def is_linked_worktree(project_root: Path) -> bool:
    """Return True when project_root is a linked worktree rather than the main checkout."""
    return main_checkout_for_worktree(project_root) is not None
```

- [ ] **Step 5: Run the tests and commit**

Run:

```bash
/auto-test-pytest tests/config/test_runtime_identity.py tests/scripts/test_configure_mcp_cli.py tests/src/test_mcp_config_drift.py
git add src/config/runtime_identity.py src/config/worktrees.py tests/config/test_runtime_identity.py
git commit -m "Add runtime identity guard foundation"
```

Expected:

```text
Runtime identity tests pass.
Existing MCP config drift tests still pass.
Commit succeeds without absolute worktree path leaks.
```

## Task 3: Add DriftDoctor Audit And Repair

**Files:**
- Create: `src/config/global_identity_drift.py`
- Create: `scripts/check_global_identity_drift.py`
- Test: `tests/config/test_global_identity_drift.py`
- Test: `tests/scripts/test_check_global_identity_drift.py`

- [ ] **Step 1: Write failing drift tests**

Create `tests/config/test_global_identity_drift.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from src.config.global_identity_drift import (
    IdentityIssue,
    scan_editable_install_locations,
    scan_pth_files,
)


def test_scan_editable_install_locations_flags_worktree(tmp_path: Path) -> None:
    authority = tmp_path / "Augur"
    worktree = tmp_path / "augur-wt-feature"
    authority.mkdir()
    worktree.mkdir()
    pip_json = json.dumps(
        [
            {"name": "augur-cli", "editable_project_location": str(worktree)},
            {"name": "other", "editable_project_location": str(tmp_path / "other")},
        ]
    )

    issues = scan_editable_install_locations(
        pip_json=pip_json,
        authority_root=authority,
    )

    assert issues == [
        IdentityIssue(
            surface="editable-install",
            name="augur-cli",
            path=worktree.resolve(),
            expected=authority.resolve(),
            detail="editable install points at a worktree",
            repairable=True,
        )
    ]


def test_scan_pth_files_flags_worktree_path(tmp_path: Path) -> None:
    authority = tmp_path / "Augur"
    worktree = tmp_path / "augur-wt-feature"
    site_packages = tmp_path / "site-packages"
    authority.mkdir()
    worktree.mkdir()
    site_packages.mkdir()
    pth = site_packages / "_editable_impl_augur_mcp.pth"
    pth.write_text(f"{worktree}\n", encoding="utf-8")

    issues = scan_pth_files(
        site_package_dirs=[site_packages],
        authority_root=authority,
    )

    assert issues[0].surface == "pth"
    assert issues[0].name == str(pth)
    assert issues[0].path == worktree.resolve()
    assert issues[0].expected == authority.resolve()
```

Create `tests/scripts/test_check_global_identity_drift.py`:

```python
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_check_global_identity_drift_json_reports_fixture_issue(tmp_path: Path) -> None:
    authority = tmp_path / "Augur"
    worktree = tmp_path / "augur-wt-feature"
    site_packages = tmp_path / "site-packages"
    authority.mkdir()
    worktree.mkdir()
    site_packages.mkdir()
    (authority / "project.yaml").write_text("name: augur\n", encoding="utf-8")
    (site_packages / "_editable_impl_augur_mcp.pth").write_text(f"{worktree}\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/check_global_identity_drift.py",
            "--root",
            str(authority),
            "--site-packages",
            str(site_packages),
            "--json",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["issues"][0]["surface"] == "pth"
    assert payload["issues"][0]["path"] == str(worktree.resolve())
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run:

```bash
/auto-test-pytest tests/config/test_global_identity_drift.py tests/scripts/test_check_global_identity_drift.py
```

Expected:

```text
The tests fail because src.config.global_identity_drift and the script do not exist.
```

- [ ] **Step 3: Implement `src/config/global_identity_drift.py`**

Create `src/config/global_identity_drift.py`:

```python
"""Audit and repair shared Augur global identity drift."""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import site
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from src.config.mcp_config_drift import scan_global_mcp_config_references
from src.config.runtime_identity import (
    GlobalIdentityLock,
    default_global_identity_lock_path,
    resolve_runtime_identity,
)


@dataclass(frozen=True)
class IdentityIssue:
    surface: str
    name: str
    path: Path
    expected: Path
    detail: str
    repairable: bool = False

    def as_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["path"] = str(self.path)
        data["expected"] = str(self.expected)
        return data


def _is_worktree_path(path: Path, authority_root: Path) -> bool:
    resolved = path.expanduser().resolve(strict=False)
    expected = authority_root.expanduser().resolve(strict=False)
    if resolved == expected:
        return False
    return "augur-wt-" in resolved.as_posix() or "/.worktrees/" in resolved.as_posix()


def scan_editable_install_locations(
    *,
    pip_json: str,
    authority_root: Path,
) -> list[IdentityIssue]:
    try:
        rows = json.loads(pip_json)
    except ValueError:
        rows = []
    issues: list[IdentityIssue] = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "")
        location = row.get("editable_project_location") or row.get("location")
        if not name.startswith("augur") or not isinstance(location, str):
            continue
        path = Path(location).expanduser().resolve(strict=False)
        if _is_worktree_path(path, authority_root):
            issues.append(
                IdentityIssue(
                    surface="editable-install",
                    name=name,
                    path=path,
                    expected=authority_root.expanduser().resolve(strict=False),
                    detail="editable install points at a worktree",
                    repairable=True,
                )
            )
    return issues


def _pip_editable_json(python_executable: str) -> str:
    result = subprocess.run(
        [python_executable, "-m", "pip", "list", "--editable", "--format=json"],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.stdout if result.returncode == 0 else "[]"


def scan_pth_files(
    *,
    site_package_dirs: Iterable[Path],
    authority_root: Path,
) -> list[IdentityIssue]:
    issues: list[IdentityIssue] = []
    expected = authority_root.expanduser().resolve(strict=False)
    for site_dir in site_package_dirs:
        if not site_dir.exists():
            continue
        for pth in site_dir.glob("*.pth"):
            try:
                lines = pth.read_text(encoding="utf-8").splitlines()
            except OSError:
                continue
            for line in lines:
                raw = line.strip()
                if not raw or raw.startswith("import "):
                    continue
                path = Path(raw).expanduser().resolve(strict=False)
                if _is_worktree_path(path, expected):
                    issues.append(
                        IdentityIssue(
                            surface="pth",
                            name=str(pth),
                            path=path,
                            expected=expected,
                            detail=".pth file points at a worktree",
                            repairable=True,
                        )
                    )
    return issues


def _site_package_dirs() -> list[Path]:
    candidates: list[str] = []
    with contextlib_suppress():
        candidates.extend(site.getsitepackages())
    with contextlib_suppress():
        candidates.append(site.getusersitepackages())
    return [Path(candidate) for candidate in candidates if candidate]


class contextlib_suppress:
    def __enter__(self):
        return None

    def __exit__(self, exc_type, exc, tb):
        return True


def scan_import_specs(*, authority_root: Path) -> list[IdentityIssue]:
    issues: list[IdentityIssue] = []
    expected = authority_root.expanduser().resolve(strict=False)
    for module_name in ("augur_core", "augur_framework", "augur_shared"):
        spec = importlib.util.find_spec(module_name)
        origin = getattr(spec, "origin", None) if spec else None
        if not origin:
            continue
        path = Path(origin).expanduser().resolve(strict=False)
        if _is_worktree_path(path, expected):
            issues.append(
                IdentityIssue(
                    surface="import-spec",
                    name=module_name,
                    path=path,
                    expected=expected,
                    detail="import spec resolves to a worktree",
                    repairable=True,
                )
            )
    return issues


def scan_global_identity_drift(
    *,
    project_root: Path | None = None,
    python_executable: str | None = None,
    site_package_dirs: Iterable[Path] | None = None,
    config_catalog_path: Path | None = None,
) -> list[IdentityIssue]:
    identity = resolve_runtime_identity(project_root)
    authority = identity.authority_root
    python = python_executable or sys.executable
    issues: list[IdentityIssue] = []
    issues.extend(scan_editable_install_locations(pip_json=_pip_editable_json(python), authority_root=authority))
    issues.extend(scan_pth_files(site_package_dirs=site_package_dirs or _site_package_dirs(), authority_root=authority))
    issues.extend(scan_import_specs(authority_root=authority))
    for issue in scan_global_mcp_config_references(
        project_root=authority,
        config_catalog_path=config_catalog_path,
    ):
        issues.append(
            IdentityIssue(
                surface="mcp-config",
                name=f"{issue.client_key}:{issue.server_name}",
                path=issue.referenced_path,
                expected=authority,
                detail=issue.detail,
                repairable=True,
            )
        )
    return issues


def repair_editable_identity(
    *,
    authority_root: Path,
    python_executable: str,
) -> subprocess.CompletedProcess[str]:
    uv = shutil.which("uv")
    if uv:
        cmd = [
            uv,
            "pip",
            "install",
            "--python",
            python_executable,
            "-e",
            str(authority_root),
            "-e",
            str(authority_root / "src" / "mcp"),
        ]
    else:
        cmd = [
            python_executable,
            "-m",
            "pip",
            "install",
            "-e",
            str(authority_root),
            "-e",
            str(authority_root / "src" / "mcp"),
        ]
    with GlobalIdentityLock(default_global_identity_lock_path()):
        return subprocess.run(cmd, check=False, capture_output=True, text=True, timeout=120)
```

- [ ] **Step 4: Implement `scripts/check_global_identity_drift.py`**

Create `scripts/check_global_identity_drift.py`:

```python
#!/usr/bin/env python3
"""Audit and repair shared Augur global identity drift."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.config.global_identity_drift import repair_editable_identity, scan_global_identity_drift
from src.config.runtime_identity import resolve_runtime_identity


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Augur global identity drift.")
    parser.add_argument("--root", type=Path, default=None, help="Project root to inspect.")
    parser.add_argument("--python", default=sys.executable, help="Python executable to inspect.")
    parser.add_argument("--site-packages", action="append", type=Path, default=None)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--repair", action="store_true")
    args = parser.parse_args()

    identity = resolve_runtime_identity(args.root)
    site_dirs = args.site_packages if args.site_packages else None
    issues = scan_global_identity_drift(
        project_root=identity.current_root,
        python_executable=args.python,
        site_package_dirs=site_dirs,
    )

    if args.repair and issues:
        repair = repair_editable_identity(
            authority_root=identity.authority_root,
            python_executable=args.python,
        )
        issues = scan_global_identity_drift(
            project_root=identity.current_root,
            python_executable=args.python,
            site_package_dirs=site_dirs,
        )
        if repair.returncode != 0 and not args.json:
            print(repair.stderr, file=sys.stderr)

    payload = {
        "ok": not issues,
        "authorityRoot": str(identity.authority_root),
        "currentRoot": str(identity.current_root),
        "issues": [issue.as_dict() for issue in issues],
    }

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        if not issues:
            print(f"OK: shared Augur identity resolves to {identity.authority_root}")
        else:
            print(f"FAIL: {len(issues)} shared Augur identity issue(s)")
            for issue in issues:
                print(f"- {issue.surface} {issue.name}: {issue.path} expected {issue.expected}")
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run tests and commit**

Run:

```bash
/auto-test-pytest tests/config/test_global_identity_drift.py tests/scripts/test_check_global_identity_drift.py tests/src/test_mcp_config_drift.py
git add src/config/global_identity_drift.py scripts/check_global_identity_drift.py tests/config/test_global_identity_drift.py tests/scripts/test_check_global_identity_drift.py
git commit -m "Add global identity drift doctor"
```

Expected:

```text
Drift doctor tests pass.
The script returns non-zero for fixture drift and JSON names the drifted surface.
```

## Task 4: Guard Persistent MCP And Client Config Sync

**Files:**
- Modify: `scripts/configure_mcp.py`
- Modify: `project-brain/capabilities/skills/ai/scripts/sync_agents/templates.py`
- Modify: `project-brain/capabilities/skills/ai/scripts/sync_agents/adapters/codex.py`
- Modify: `project-brain/capabilities/skills/ai/scripts/sync_agents/adapters/opencode.py`
- Modify: `project-brain/capabilities/skills/ai/scripts/sync_agents/adapters/antigravity.py`
- Test: `tests/scripts/test_configure_mcp_cli.py`
- Test: `tests/sync_agents/test_global_identity_sync.py`

- [ ] **Step 1: Add failing sync tests**

Create `tests/sync_agents/test_global_identity_sync.py`:

```python
from __future__ import annotations

import importlib
import json
import os
from pathlib import Path


def _linked_worktree(tmp_path: Path) -> tuple[Path, Path]:
    main_root = tmp_path / "Augur"
    worktree_root = tmp_path / ".worktrees" / "feature"
    gitdir = main_root / ".git" / "worktrees" / "feature"
    gitdir.mkdir(parents=True)
    main_root.mkdir(parents=True)
    worktree_root.mkdir(parents=True)
    (main_root / "project.yaml").write_text("name: augur\n", encoding="utf-8")
    (worktree_root / "project.yaml").write_text("name: augur\n", encoding="utf-8")
    (worktree_root / ".git").write_text(f"gitdir: {gitdir}\n", encoding="utf-8")
    return main_root, worktree_root


def test_sync_templates_global_mcp_project_root_returns_authority(tmp_path: Path, monkeypatch) -> None:
    main_root, worktree_root = _linked_worktree(tmp_path)
    templates = importlib.import_module("skills.ai.scripts.sync_agents.templates")

    assert templates.global_mcp_project_root(worktree_root) == main_root.resolve()


def test_codex_adapter_global_config_uses_authority_root(tmp_path: Path, monkeypatch) -> None:
    main_root, worktree_root = _linked_worktree(tmp_path)
    codex_home = tmp_path / "codex-home"
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.delenv("AUGUR_SYNC_REPO_LOCAL_ONLY", raising=False)

    codex = importlib.import_module("skills.ai.scripts.sync_agents.adapters.codex")
    monkeypatch.setattr(codex, "PROJECT_ROOT", worktree_root)
    monkeypatch.setattr(codex, "CODEX_HOME", codex_home)
    monkeypatch.setattr(codex.CodexAdapter, "_sync_local_codex_config", lambda self: None)
    monkeypatch.setattr(codex.CodexAdapter, "_sync_routine_automations", lambda self: None)
    monkeypatch.setattr(codex.CodexAdapter, "_sync_dev_loop_automations", lambda self: None)
    monkeypatch.setattr(codex.CodexAdapter, "_sync_dream_automations", lambda self: None)
    monkeypatch.setattr(
        codex,
        "_build_codex_mcp_servers",
        lambda existing_server_ids=None: {
            "augur-core": {
                "command": str(main_root / "scripts" / "augur-codex-mcp"),
                "args": ["-m", "augur_core", "--client-id", "codex"],
            }
        },
    )

    codex.CodexAdapter().generate_mcp_config()

    written = (codex_home / "config.toml").read_text(encoding="utf-8")
    assert str(main_root.resolve()) in written
    assert str(worktree_root.resolve()) not in written
```

- [ ] **Step 2: Run sync tests and confirm the Codex case fails**

Run:

```bash
/auto-test-pytest tests/sync_agents/test_global_identity_sync.py tests/scripts/test_configure_mcp_cli.py
```

Expected:

```text
At least the Codex test fails because global Codex config still uses PROJECT_ROOT for marketplace/source or launcher root.
```

- [ ] **Step 3: Update `scripts/configure_mcp.py`**

Apply these edits:

```python
from src.config.runtime_identity import (
    GlobalIdentityLock,
    GlobalMutationGuard,
    default_global_identity_lock_path,
    resolve_runtime_identity,
)
```

Then replace the main-checkout resolution block with:

```python
    identity = resolve_runtime_identity(repo_root)
    main_checkout = identity.authority_root if identity.is_linked_worktree else None
```

Wrap the enabled-IDE loop when `should_apply` is true:

```python
    lock_context = (
        GlobalIdentityLock(default_global_identity_lock_path())
        if should_apply
        else contextlib.nullcontext()
    )
    with lock_context:
        for ide_name, ide_config in ides.items():
            if not ide_config.get("enabled", False):
                continue
            ide_repo_root = _effective_repo_root_for_ide(
                repo_root,
                ide_config,
                main_checkout=main_checkout,
            )
            if should_apply and not _config_path_is_repo_local(ide_config):
                with GlobalMutationGuard(
                    identity,
                    target_root=ide_repo_root,
                    operation=f"configure_mcp:{ide_name}",
                    allow_delegated=True,
                ):
                    pass
            # keep the existing body of the loop after this guard
```

Add `import contextlib` at the top of the file.

- [ ] **Step 4: Update `sync_agents/templates.py`**

Replace the existing `global_mcp_project_root` function with:

```python
def global_mcp_project_root(project_root: Path | None = None) -> Path:
    """Return the authority root that user-global MCP configs should embed."""
    from src.config.runtime_identity import global_mcp_project_root as _identity_root

    return _identity_root(project_root or PROJECT_ROOT)
```

- [ ] **Step 5: Update the Codex adapter**

In `project-brain/capabilities/skills/ai/scripts/sync_agents/adapters/codex.py`, import:

```python
from src.config.runtime_identity import (
    GlobalIdentityLock,
    GlobalMutationGuard,
    default_global_identity_lock_path,
    resolve_runtime_identity,
)
from ..templates import global_mcp_project_root
```

Replace `_should_sync_global_codex_home()` with:

```python
def _should_sync_global_codex_home() -> bool:
    """Return whether this sync should write shared ~/.codex files."""
    return os.environ.get("AUGUR_SYNC_REPO_LOCAL_ONLY") != "1"
```

Replace `_build_codex_mcp_entry` so it accepts a root:

```python
def _build_codex_mcp_entry(
    entry: ServerEntry | None = None,
    *,
    project_root: Path | None = None,
) -> dict[str, object]:
    server_args = _codex_args_for_entry(entry) if entry else [
        "-m",
        "augur_core",
        "--client-id",
        "codex",
    ]
    root = project_root or global_mcp_project_root(PROJECT_ROOT)
    return build_codex_mcp_entry(
        server_args,
        configured_root=root,
        startup_timeout_sec=entry.startup_timeout_sec if entry else None,
    )
```

Replace `_build_codex_mcp_servers` with:

```python
def _build_codex_mcp_servers(
    *,
    existing_server_ids: set[str] | None = None,
    project_root: Path | None = None,
) -> dict[str, dict[str, object]]:
    root = project_root or global_mcp_project_root(PROJECT_ROOT)
    return {
        entry.id: _build_codex_mcp_entry(entry, project_root=root)
        for entry in _load_manifest_entries(existing_server_ids=existing_server_ids)
    }
```

In `CodexAdapter.generate_mcp_config`, set the authority and guard global writes:

```python
        if _should_sync_global_codex_home():
            identity = resolve_runtime_identity(PROJECT_ROOT)
            authority_root = global_mcp_project_root(PROJECT_ROOT)
            with GlobalIdentityLock(default_global_identity_lock_path()):
                with GlobalMutationGuard(
                    identity,
                    target_root=authority_root,
                    operation="sync_agents:codex-global",
                    allow_delegated=True,
                ):
                    self._write_global_codex_config(authority_root)
```

Move the current global-write body into a new helper:

```python
    def _write_global_codex_config(self, authority_root: Path) -> None:
        config_path = CODEX_HOME / "config.toml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        desired_marketplace = {
            "source": str(authority_root.expanduser().resolve()),
            "source_type": "local",
        }
        current = _load_toml(config_path)
        changed = False
        tui = current.get("tui")
        if isinstance(tui, dict) and isinstance(tui.get("model_availability_nux"), dict):
            del tui["model_availability_nux"]
            if not tui:
                del current["tui"]
            changed = True
        mcp_servers = current.get("mcp_servers")
        if not isinstance(mcp_servers, dict):
            mcp_servers = {}
            current["mcp_servers"] = mcp_servers
        desired_servers = _build_codex_mcp_servers(
            existing_server_ids={
                str(server_id)
                for server_id in mcp_servers
                if str(server_id).startswith("augur")
            },
            project_root=authority_root,
        )
        marketplaces = current.get("marketplaces")
        if not isinstance(marketplaces, dict):
            marketplaces = {}
            current["marketplaces"] = marketplaces
        plugins = current.get("plugins")
        if not isinstance(plugins, dict):
            plugins = {}
            current["plugins"] = plugins
        for server_id in list(mcp_servers):
            if str(server_id).startswith("augur") and server_id not in desired_servers:
                del mcp_servers[server_id]
                changed = True
        for server_id, desired_entry in desired_servers.items():
            if mcp_servers.get(server_id) != desired_entry:
                mcp_servers[server_id] = desired_entry
                changed = True
        if marketplaces.get("augur-local") != desired_marketplace:
            marketplaces["augur-local"] = desired_marketplace
            changed = True
        plugin_entry = plugins.get("augur@augur-local")
        if isinstance(plugin_entry, dict):
            if plugin_entry.get("enabled") is not True:
                plugin_entry["enabled"] = True
                changed = True
        else:
            plugins["augur@augur-local"] = {"enabled": True}
            changed = True
        if changed:
            config_path.write_text(_toml_dump_simple(current), encoding="utf-8")
            GENERATED_FILES.append(config_path)
            logger.info("✅ Generated %s (Codex MCP config)", config_path)
```

- [ ] **Step 6: Guard OpenCode and Antigravity global writes**

Wrap the sections that write `Path.home() / ".config" / "opencode" / "opencode.json"` and `~/.gemini/antigravity/mcp_config.json`:

```python
identity = resolve_runtime_identity(PROJECT_ROOT)
target_root = global_mcp_project_root(PROJECT_ROOT)
with GlobalIdentityLock(default_global_identity_lock_path()):
    with GlobalMutationGuard(
        identity,
        target_root=target_root,
        operation="sync_agents:opencode-global",
        allow_delegated=True,
    ):
        target.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
```

Use operation name `sync_agents:antigravity-global` for Antigravity.

- [ ] **Step 7: Run tests and commit**

Run:

```bash
/auto-test-pytest tests/sync_agents/test_global_identity_sync.py tests/scripts/test_configure_mcp_cli.py tests/src/test_mcp_config_drift.py
git add scripts/configure_mcp.py project-brain/capabilities/skills/ai/scripts/sync_agents/templates.py project-brain/capabilities/skills/ai/scripts/sync_agents/adapters/codex.py project-brain/capabilities/skills/ai/scripts/sync_agents/adapters/opencode.py project-brain/capabilities/skills/ai/scripts/sync_agents/adapters/antigravity.py tests/sync_agents/test_global_identity_sync.py
git commit -m "Guard persistent MCP identity sync"
```

Expected:

```text
Global config tests prove worktree sync writes main-rooted persistent config.
Repo-local generated files can still point to the worktree.
```

## Task 5: Fix Codex MCP Launcher Root Selection

**Files:**
- Modify: `scripts/augur-codex-mcp`
- Modify: `scripts/augur-codex-mcp.ps1`
- Test: `tests/cli/test_codex_mcp_launcher_identity.py`

- [ ] **Step 1: Write failing launcher tests**

Create `tests/cli/test_codex_mcp_launcher_identity.py`:

```python
from __future__ import annotations

from pathlib import Path


def test_posix_codex_launcher_prefers_overlay_before_cwd() -> None:
    script = Path("scripts/augur-codex-mcp").read_text(encoding="utf-8")

    overlay_index = script.index('"${AUGUR_PROJECT_ROOT:-}"')
    cwd_index = script.index('"$cwd_root"')

    assert overlay_index < cwd_index


def test_posix_codex_launcher_uses_configured_root_before_cwd_without_overlay() -> None:
    script = Path("scripts/augur-codex-mcp").read_text(encoding="utf-8")

    configured_index = script.index('"$configured_root"')
    cwd_index = script.index('"$cwd_root"')

    assert configured_index < cwd_index


def test_windows_codex_launcher_prefers_overlay_before_cwd() -> None:
    script = Path("scripts/augur-codex-mcp.ps1").read_text(encoding="utf-8")

    overlay_index = script.index("$env:AUGUR_PROJECT_ROOT")
    cwd_index = script.index("$cwdRoot")

    assert overlay_index < cwd_index
```

- [ ] **Step 2: Run launcher tests and confirm they fail**

Run:

```bash
/auto-test-pytest tests/cli/test_codex_mcp_launcher_identity.py
```

Expected:

```text
Tests fail because the launchers check cwd before explicit overlay/configured roots.
```

- [ ] **Step 3: Update POSIX launcher candidate order**

In `scripts/augur-codex-mcp`, replace:

```sh
for candidate in "$cwd_root" "${AUGUR_ROOT:-}" "${AUGUR_REPO:-}" "$configured_root"; do
```

with:

```sh
for candidate in "${AUGUR_PROJECT_ROOT:-}" "${AUGUR_ROOT:-}" "${AUGUR_REPO:-}" "$configured_root" "$cwd_root"; do
```

Update the error message:

```sh
echo "[augur] Codex MCP could not locate an Augur checkout. checked AUGUR_PROJECT_ROOT=${AUGUR_PROJECT_ROOT:-} AUGUR_ROOT=${AUGUR_ROOT:-} AUGUR_REPO=${AUGUR_REPO:-} configured=$configured_root cwd=$cwd_root" >&2
```

- [ ] **Step 4: Update PowerShell launcher candidate order**

In `scripts/augur-codex-mcp.ps1`, replace the `$candidates` block with:

```powershell
    $candidates = @(
        $env:AUGUR_PROJECT_ROOT,
        $env:AUGUR_ROOT,
        $env:AUGUR_REPO,
        $configuredRoot,
        $cwdRoot
    )
```

Update the error:

```powershell
    Write-Error "[augur] Codex MCP could not locate an Augur checkout. checked AUGUR_PROJECT_ROOT=$env:AUGUR_PROJECT_ROOT AUGUR_ROOT=$env:AUGUR_ROOT AUGUR_REPO=$env:AUGUR_REPO configured=$configuredRoot cwd=$cwdRoot"
```

- [ ] **Step 5: Run tests and commit**

Run:

```bash
/auto-test-pytest tests/cli/test_codex_mcp_launcher_identity.py tests/cli/test_cli_mcp_runtime.py
git add scripts/augur-codex-mcp scripts/augur-codex-mcp.ps1 tests/cli/test_codex_mcp_launcher_identity.py
git commit -m "Prefer explicit Codex MCP runtime identity"
```

Expected:

```text
Codex launcher tests pass.
Launchers still support worktree overlays through AUGUR_PROJECT_ROOT.
```

## Task 6: Add Cross-Contamination Guardrails

**Files:**
- Create: `.githooks/global-identity-staged-scan.sh`
- Modify: `.githooks/pre-commit`
- Modify: `.github/workflows/ci-tests.yml`
- Test: `tests/test_worktree_global_identity_isolation.py`

- [ ] **Step 1: Write the integration guard test**

Create `tests/test_worktree_global_identity_isolation.py`:

```python
from __future__ import annotations

from pathlib import Path

from src.config.global_identity_drift import scan_editable_install_locations, scan_pth_files
from src.config.runtime_identity import (
    GlobalMutationGuard,
    build_worktree_overlay_env,
    resolve_runtime_identity,
)


def _linked_worktree(tmp_path: Path, name: str) -> tuple[Path, Path]:
    main_root = tmp_path / "Augur"
    worktree_root = tmp_path / ".worktrees" / name
    gitdir = main_root / ".git" / "worktrees" / name
    gitdir.mkdir(parents=True, exist_ok=True)
    main_root.mkdir(parents=True, exist_ok=True)
    worktree_root.mkdir(parents=True, exist_ok=True)
    (main_root / "project.yaml").write_text("name: augur\n", encoding="utf-8")
    (worktree_root / "project.yaml").write_text("name: augur\n", encoding="utf-8")
    (worktree_root / ".git").write_text(f"gitdir: {gitdir}\n", encoding="utf-8")
    return main_root, worktree_root


def test_two_worktrees_can_overlay_but_not_mutate_global_identity(tmp_path: Path) -> None:
    main_root, worktree_a = _linked_worktree(tmp_path, "feature-a")
    _same_main, worktree_b = _linked_worktree(tmp_path, "feature-b")
    identity_a = resolve_runtime_identity(worktree_a)
    identity_b = resolve_runtime_identity(worktree_b)

    env_a = build_worktree_overlay_env(identity_a, {})
    env_b = build_worktree_overlay_env(identity_b, {})

    assert env_a["AUGUR_PROJECT_ROOT"] == str(worktree_a.resolve())
    assert env_b["AUGUR_PROJECT_ROOT"] == str(worktree_b.resolve())
    for identity, worktree in ((identity_a, worktree_a), (identity_b, worktree_b)):
        try:
            with GlobalMutationGuard(identity, target_root=worktree, operation="install"):
                blocked = False
        except Exception:
            blocked = True
        assert blocked is True
        with GlobalMutationGuard(
            identity,
            target_root=main_root,
            operation="client-sync",
            allow_delegated=True,
        ):
            delegated = True
        assert delegated is True


def test_fixture_drift_scanners_catch_shared_worktree_identity(tmp_path: Path) -> None:
    main_root, worktree = _linked_worktree(tmp_path, "feature-a")
    site_packages = tmp_path / "site-packages"
    site_packages.mkdir()
    (site_packages / "_editable_impl_augur_cli.pth").write_text(f"{worktree}\n", encoding="utf-8")
    pip_json = '[{"name": "augur-cli", "editable_project_location": "' + str(worktree) + '"}]'

    editable_issues = scan_editable_install_locations(
        pip_json=pip_json,
        authority_root=main_root,
    )
    pth_issues = scan_pth_files(
        site_package_dirs=[site_packages],
        authority_root=main_root,
    )

    assert editable_issues
    assert pth_issues
```

- [ ] **Step 2: Add the staged scan hook**

Create `.githooks/global-identity-staged-scan.sh`:

```sh
#!/bin/sh
# Commit-time guard for ADR-779: global identity mutations must go through
# src.config.runtime_identity.

set -e

STAGED=$(git diff --cached --name-only --diff-filter=ACMR | grep -E '\.(py|sh|ps1|mjs|md|yml|yaml)$' || true)
[ -z "$STAGED" ] && exit 0

DIFF=$(git diff --cached -U0 --diff-filter=ACMR -- $STAGED 2>/dev/null || true)
[ -z "$DIFF" ] && exit 0

ADDED=$(echo "$DIFF" | grep -E '^\+' | grep -vE '^\+\+\+' | sed 's/^+//' || true)
[ -z "$ADDED" ] && exit 0

FAIL=0

if echo "$ADDED" | grep -E 'AUGUR_SYNC_ALLOW_''WORKTREE_GLOBAL' >/dev/null 2>&1; then
    echo "❌ ADR-779 violation: do not add AUGUR_SYNC_ALLOW_''WORKTREE_GLOBAL." >&2
    FAIL=1
fi

if echo "$ADDED" | grep -E 'uv pip install .*(-e|--editable).*(augur-wt-|\\.worktrees)' >/dev/null 2>&1; then
    echo "❌ ADR-779 violation: staged editable install targets a worktree path." >&2
    FAIL=1
fi

if echo "$ADDED" | grep -E 'pip install .*(-e|--editable).*(augur-wt-|\\.worktrees)' >/dev/null 2>&1; then
    echo "❌ ADR-779 violation: staged editable install targets a worktree path." >&2
    FAIL=1
fi

if [ "$FAIL" -eq 1 ]; then
    echo "Use src.config.runtime_identity.GlobalMutationGuard and authority-root repair instead." >&2
    exit 1
fi
```

Make it executable:

```bash
chmod +x .githooks/global-identity-staged-scan.sh
```

In `.githooks/pre-commit`, add this block before the final fail check:

```sh
# ── ADR-779: Global identity mutations must not target active worktrees ──
IDENTITY_HOOK="$(git rev-parse --show-toplevel)/.githooks/global-identity-staged-scan.sh"
if [ -x "$IDENTITY_HOOK" ]; then
    if ! "$IDENTITY_HOOK"; then
        FAIL=1
    fi
fi
```

- [ ] **Step 3: Add CI identity guard**

In `.github/workflows/ci-tests.yml`, add a step near the Python test jobs:

```yaml
      - name: Guard worktree global identity isolation
        run: |
          python scripts/check_global_identity_drift.py --root "$PWD" --json
          python -m pytest tests/config/test_runtime_identity.py tests/config/test_global_identity_drift.py tests/test_worktree_global_identity_isolation.py -q
        env:
          PYTHONPATH: "project-brain/capabilities:."
```

- [ ] **Step 4: Run guard tests and commit**

Run:

```bash
/auto-test-pytest tests/config/test_runtime_identity.py tests/config/test_global_identity_drift.py tests/test_worktree_global_identity_isolation.py
git add .githooks/global-identity-staged-scan.sh .githooks/pre-commit .github/workflows/ci-tests.yml tests/test_worktree_global_identity_isolation.py
git commit -m "Guard worktree global identity isolation"
```

Expected:

```text
Guard tests pass.
Pre-commit hook runs without blocking the new guarded code.
```

## Task 7: Real Live Audit, Repair, And Two-Worktree Verification

**Files:**
- Modify: `docs/adrs/ADR-779-worktree-global-identity-isolation.md`
- Modify: `docs/superpowers/plans/2026-05-24-worktree-global-identity-isolation.md`

- [ ] **Step 1: Run the live audit before repair**

Run:

```bash
.venv/bin/python scripts/check_global_identity_drift.py --json > /tmp/augur-identity-before.json
```

Expected:

```text
The JSON names each shared identity issue or reports ok=true.
If issues exist, every issue names surface, path, expected authority root, and repairable.
```

- [ ] **Step 2: Repair only through the authority path if needed**

Run only when `/tmp/augur-identity-before.json` contains `"ok": false`:

```bash
.venv/bin/python scripts/check_global_identity_drift.py --repair --json > /tmp/augur-identity-after-repair.json
```

Expected:

```text
Repair runs under the global identity lock.
The after-repair JSON reports ok=true or names the remaining non-repairable surfaces.
```

- [ ] **Step 3: Run focused tests**

Run:

```bash
/auto-test-pytest tests/config/test_runtime_identity.py tests/config/test_global_identity_drift.py tests/scripts/test_check_global_identity_drift.py tests/scripts/test_configure_mcp_cli.py tests/sync_agents/test_global_identity_sync.py tests/cli/test_codex_mcp_launcher_identity.py tests/test_worktree_global_identity_isolation.py
```

Expected:

```text
All identity, drift, config, sync, launcher, and two-worktree fixture tests pass.
```

- [ ] **Step 4: Run full Python suite through the approved loop**

Run:

```bash
/auto-test-pytest tests/
```

Expected:

```text
No new failures from identity changes.
Any pre-existing failures are named with root cause and compared to the baseline captured by the loop.
```

- [ ] **Step 5: Capture real user-value evidence**

Run:

```bash
.venv/bin/python scripts/check_global_identity_drift.py --json
.venv/bin/python - <<'PY'
from pathlib import Path
from src.config.runtime_identity import build_worktree_overlay_env, resolve_runtime_identity

identity = resolve_runtime_identity(Path.cwd())
env = build_worktree_overlay_env(identity, {})
print("authority=", identity.authority_root)
print("current=", identity.current_root)
print("overlay_root=", env["AUGUR_PROJECT_ROOT"])
print("can_mutate_global=", identity.can_mutate_global)
PY
```

Expected:

```text
The drift audit reports ok=true for shared identity.
The overlay proof shows the active checkout can run locally without becoming the authority root.
```

- [ ] **Step 6: Update ADR-779 with implementation evidence**

Add a status note under ADR-779:

```markdown
## Status notes

Implemented (2026-05-24). The implementation added a runtime identity layer,
global mutation lock, drift doctor, guarded persistent MCP/client config sync,
Codex launcher root ordering, staged/CI guardrails, and a two-worktree regression
test. Live audit after repair reported shared Augur identity rooted at main with
no editable install, `.pth`, import-spec, CLI, or persistent MCP config drift.
```

Set frontmatter:

```yaml
status: Implemented
```

- [ ] **Step 7: Run ADR post-write hooks and commit**

Run:

```bash
.venv/bin/python .github/scripts/adr_upsert_live.py
.venv/bin/python .github/scripts/generate_adr_index.py
.venv/bin/python src/lib/index/unified_indexer.py --category adrs
PYTHONPATH=project-brain/capabilities .venv/bin/python -m skills.ai.scripts.sync_agents sync agents all
git add docs/adrs/ADR-779-worktree-global-identity-isolation.md docs/generated/adr-index.md docs/superpowers/plans/2026-05-24-worktree-global-identity-isolation.md
git add CODEX.md AGENTS.md CLAUDE.md GEMINI.md .github/copilot-instructions.md .codex/skills 2>/dev/null || true
git commit -m "Implement ADR-779 worktree global identity isolation"
```

Expected:

```text
ADR-779 status is Implemented.
Generated ADR index and agent instruction projections are refreshed.
Commit succeeds with pre-commit guard enabled.
```

## Task 8: Merge And Cleanup

**Files:**
- No source edits unless merge conflict resolution is required.

- [ ] **Step 1: Run final status checks**

Run:

```bash
git status --short
git log --oneline -n 8
.venv/bin/python scripts/check_global_identity_drift.py --json
```

Expected:

```text
Only intended changes are committed.
Live identity audit reports ok=true.
Recent commits show the ADR, identity foundation, drift doctor, guarded sync, launcher fix, and guardrails.
```

- [ ] **Step 2: Merge through the repo workflow**

Run:

```bash
/dev-merge
```

Expected:

```text
Branch merges to main through the Augur workflow.
If a live AI/client process owns the source worktree, cleanup is deferred and reported with PID/path.
```

- [ ] **Step 3: Report user value**

Report:

```text
Before: shared identity could point at active worktrees.
After: live audit ok=true, persistent configs main-rooted, worktree overlays still run locally, and two-worktree regression guard passes.
```
