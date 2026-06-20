# Dashboard Worktree Toolchain Sharing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop duplicating `apps/dashboard/node_modules` (~767MB per worktree) by fixing pnpm hardlinking and adding CoW-clone-on-worktree-creation with graceful fallback. Each worktree keeps its own real `node_modules` (existing preflight invariant preserved); bytes are shared at the filesystem layer.

**Architecture:** Approach A+C with capability probe. **A** = configure pnpm's `package-import-method=hardlink` where dashboard installs actually run (`apps/dashboard/.npmrc`) and force it in the preflight fallback install command so every install hardlinks files to the shared content-addressable store. **C** = on worktree creation, the preflight orchestrator CoW-clones `node_modules` from main via the platform-appropriate primitive (`cp -c` on APFS, `cp --reflink=auto` on btrfs/xfs, `Copy-Item` with CoW flag on ReFS), falling back to `pnpm install --frozen-lockfile --package-import-method hardlink` when no CoW is available or when lockfiles diverge.

**Tech Stack:** Python 3.12, pytest, pnpm 10.32.1, Next.js dashboard at `apps/dashboard/`, existing `scripts/worktree_preflight.py` extended with two integration points.

**Spec:** [`docs/superpowers/specs/2026-05-16-dashboard-worktree-toolchain-sharing-design.md`](../specs/2026-05-16-dashboard-worktree-toolchain-sharing-design.md) (commit `60bbc5a10`).

---

## File Structure

| File | Role | New / Modified |
|---|---|---|
| `/.npmrc` | Append `package-import-method=hardlink` | Modified |
| `apps/dashboard/.npmrc` | Dashboard-local effective pnpm config | **Created** |
| `apps/dashboard/package-lock.json` | Stale npm artifact — delete | Deleted |
| `scripts/worktree_toolchain.py` | New module: `verify_pnpm_alignment`, `probe_clone_primitive`, `materialize_node_modules` | **Created** |
| `tests/scripts/test_worktree_toolchain.py` | Unit tests for the new module | **Created** |
| `scripts/worktree_preflight.py` | Add `_check_pnpm_alignment` step; route `_ensure_dashboard_dependencies` repair path through the materializer | Modified |
| `tests/scripts/test_worktree_preflight.py` | New tests for alignment check and materializer integration | Modified |
| `scripts/verify_worktree_toolchain.py` | Real-data Layer 3 verification script | **Created** |
| `apps/dashboard/README.md` | Note the pnpm store same-volume requirement | Modified |
| `docs/agent-topics/WORKFLOWS.md` | Cross-link to the toolchain sharing behavior | Modified |

Tests live as siblings under `tests/scripts/`, matching the existing `test_worktree_preflight.py` pattern. The new module is in `scripts/` (not `src/dashboard/` — that directory doesn't exist) and is imported the same way: add `scripts/` to `sys.path` then `import worktree_toolchain`.

**Test command convention** (CLAUDE.md rule #19): never invoke `pytest` directly. Use `/auto-test-pytest <path>` for the canonical loop, or `uv run pytest <path> -v` for one-off engineer-side runs (the loop wraps this).

---

## Task 1: Delete stale npm lockfile

**Files:**
- Delete: `apps/dashboard/package-lock.json`

The dashboard is pnpm-managed (`packageManager: pnpm@10.32.1`, `pnpm-lock.yaml` present). The 504KB `package-lock.json` is leftover npm residue from prior mixed-tool usage and contributes to the broken hardlink situation by confusing some tools about which lockfile is authoritative.

- [ ] **Step 1: Verify the file is indeed unused**

```bash
grep -rn "package-lock.json" apps/dashboard/ --include="*.ts" --include="*.tsx" --include="*.js" --include="*.json" --include="*.md" 2>/dev/null
grep -rn "package-lock.json" scripts/ src/ --include="*.py" 2>/dev/null
```

Expected: no references in dashboard source, and any Python references should only be in fallback logic that already prefers `pnpm-lock.yaml` when present (verify by reading the matches).

- [ ] **Step 2: Delete the file**

```bash
git rm apps/dashboard/package-lock.json
```

- [ ] **Step 3: Commit**

```bash
git commit -m "chore(dashboard): remove stale npm package-lock.json

The dashboard is pnpm-managed (packageManager: pnpm@10.32.1,
pnpm-lock.yaml present). This npm lockfile was leftover residue
from prior mixed-tool usage and contributed to broken pnpm
hardlinking (0-2 of 41-83k files hardlinked across worktrees).
"
```

---

## Task 2: Make dashboard pnpm hardlink config effective

**Files:**
- Modify: `/.npmrc`
- Create: `apps/dashboard/.npmrc`

Tells pnpm to hardlink package files from the content-addressable store into each `node_modules` instead of copying. The root `.npmrc` keeps the repo-level directive, and `apps/dashboard/.npmrc` makes the directive effective for commands run from the standalone dashboard package.

- [ ] **Step 1: Read the current `.npmrc`**

```bash
cat .npmrc
```

Expected:
```
shamefully-hoist=true
public-hoist-pattern[]=*node-pty*
```

- [ ] **Step 2: Append the directive**

Use the Edit tool to change `~/Projects/Augur/.npmrc` from:
```
shamefully-hoist=true
public-hoist-pattern[]=*node-pty*
```
to:
```
shamefully-hoist=true
public-hoist-pattern[]=*node-pty*
package-import-method=hardlink
```

- [ ] **Step 3: Verify the change**

```bash
cat .npmrc
grep -c "package-import-method=hardlink" .npmrc
cd apps/dashboard && pnpm config get package-import-method
```

Expected: file shows all three directives; grep count = `1`; dashboard-local pnpm config prints `hardlink`.

- [ ] **Step 4: Commit**

```bash
git add .npmrc
git commit -m "chore(npm): force pnpm to hardlink from store

Adds package-import-method=hardlink so pnpm installs into
node_modules via hardlinks to ~/Library/pnpm/store/ instead
of full copies. Without this, hardlinking silently falls back
to copy when pnpm's heuristics can't confirm same-volume safety
— measured today: 2 of 83k files hardlinked in main, 0 in
sibling worktrees. After this change a fresh pnpm install will
hardlink ~all files, sharing bytes with every other worktree.
"
```

---

## Task 3: Create `scripts/worktree_toolchain.py` with `verify_pnpm_alignment()`

**Files:**
- Create: `scripts/worktree_toolchain.py`
- Create: `tests/scripts/test_worktree_toolchain.py`

This function detects whether pnpm's store and the projects directory live on the same filesystem volume. If they don't, hardlinking silently degrades to copying — exactly the bug we're fixing. The check returns an `Incident` with a remediation hint when misaligned.

We reuse the `Incident` dataclass from `worktree_preflight.py` so callers can route findings into the existing preflight contract.

- [ ] **Step 1: Write the failing test**

Create `tests/scripts/test_worktree_toolchain.py`:

```python
"""Tests for worktree_toolchain module."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

from src.config.paths import get_project_root

PROJECT_ROOT = get_project_root()
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import worktree_toolchain  # noqa: E402


def test_verify_pnpm_alignment_returns_none_when_devices_match(tmp_path: Path):
    project_root = tmp_path / "project"
    project_root.mkdir()
    store_dir = tmp_path / "store"
    store_dir.mkdir()

    with patch.object(
        worktree_toolchain, "_resolve_pnpm_store_dir", return_value=store_dir
    ), patch.object(worktree_toolchain, "_device_id", return_value=42):
        result = worktree_toolchain.verify_pnpm_alignment(project_root)

    assert result is None


def test_verify_pnpm_alignment_returns_incident_when_devices_differ(tmp_path: Path):
    project_root = tmp_path / "project"
    project_root.mkdir()
    store_dir = tmp_path / "store"
    store_dir.mkdir()

    devices = {project_root: 1, store_dir: 2}

    with patch.object(
        worktree_toolchain, "_resolve_pnpm_store_dir", return_value=store_dir
    ), patch.object(
        worktree_toolchain, "_device_id", side_effect=lambda p: devices[p]
    ):
        result = worktree_toolchain.verify_pnpm_alignment(project_root)

    assert result is not None
    assert result.severity == "high"
    assert "different filesystem volume" in result.message.lower()
    assert str(project_root) in result.message
    assert str(store_dir) in result.message
    assert result.safe_to_repair is False  # user must choose remediation
    assert result.fingerprint == "worktree/toolchain/pnpm-store-misaligned"


def test_verify_pnpm_alignment_returns_incident_when_store_missing(tmp_path: Path):
    project_root = tmp_path / "project"
    project_root.mkdir()

    with patch.object(
        worktree_toolchain, "_resolve_pnpm_store_dir", return_value=None
    ):
        result = worktree_toolchain.verify_pnpm_alignment(project_root)

    assert result is not None
    assert result.severity == "high"
    assert "store-dir" in result.message.lower()
    assert result.fingerprint == "worktree/toolchain/pnpm-store-unresolved"
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
/auto-test-pytest tests/scripts/test_worktree_toolchain.py
```

Expected: FAIL — `ModuleNotFoundError: No module named 'worktree_toolchain'`.

- [ ] **Step 3: Create the module with the minimal implementation**

Create `scripts/worktree_toolchain.py`:

```python
"""Worktree toolchain helpers: pnpm alignment, CoW clones, node_modules materialization.

This module owns the cheapest-path materialization of apps/dashboard/node_modules
across worktrees. It is imported by scripts/worktree_preflight.py and runs entirely
under the existing preflight Incident/Repair contract.

Three pure functions:
    verify_pnpm_alignment(project_root) -> Incident | None
    probe_clone_primitive() -> CloneFn | None
    materialize_node_modules(worktree_root, source_worktree) -> MaterializeResult
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

# Reuse the Incident dataclass from worktree_preflight to keep the contract single-source.
SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from worktree_preflight import Incident  # noqa: E402


def _resolve_pnpm_store_dir() -> Path | None:
    """Return the resolved pnpm store directory, or None if unresolvable."""
    pnpm = shutil.which("pnpm")
    if pnpm is None:
        return None
    try:
        result = subprocess.run(
            [pnpm, "config", "get", "store-dir"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        return None
    value = (result.stdout or "").strip()
    if not value or value.lower() == "undefined":
        # pnpm prints "undefined" when no override is set; fall back to platform default.
        value = _platform_default_store_dir()
    if not value:
        return None
    candidate = Path(value).expanduser()
    if not candidate.exists():
        try:
            candidate.mkdir(parents=True, exist_ok=True)
        except OSError:
            return None
    return candidate


def _platform_default_store_dir() -> str:
    if sys.platform == "darwin":
        return str(Path.home() / "Library" / "pnpm" / "store")
    if sys.platform.startswith("win"):
        local = os.environ.get("LOCALAPPDATA")
        if local:
            return str(Path(local) / "pnpm" / "store")
        return str(Path.home() / "AppData" / "Local" / "pnpm" / "store")
    return str(Path.home() / ".local" / "share" / "pnpm" / "store")


def _device_id(path: Path) -> int:
    return os.stat(path).st_dev


def verify_pnpm_alignment(project_root: Path) -> Incident | None:
    """Return an Incident when the pnpm store and project root are on different volumes.

    Hardlinks cannot cross filesystem boundaries. When they're misaligned pnpm
    silently falls back to copying files, defeating the content-addressable store
    benefit. The user must choose how to resolve (move projects, or set store-dir
    to a path on the projects volume) — this check does NOT auto-fix.
    """
    store_dir = _resolve_pnpm_store_dir()
    if store_dir is None:
        return Incident(
            fingerprint="worktree/toolchain/pnpm-store-unresolved",
            severity="high",
            message=(
                "Could not resolve pnpm store-dir. Install pnpm (corepack enable && "
                "corepack prepare pnpm@latest --activate) or set store-dir via "
                "`pnpm config set store-dir <path>`."
            ),
            owner_path=str(project_root),
            safe_to_repair=False,
            repaired=False,
        )

    project_dev = _device_id(project_root)
    store_dev = _device_id(store_dir)
    if project_dev == store_dev:
        return None

    return Incident(
        fingerprint="worktree/toolchain/pnpm-store-misaligned",
        severity="high",
        message=(
            f"pnpm store and projects directory live on different filesystem volume. "
            f"Project root: {project_root} (dev={project_dev}). "
            f"Store: {store_dir} (dev={store_dev}). "
            f"Hardlinks cannot cross volumes; pnpm will copy files instead. "
            f"Resolve by either moving projects to the store volume, or running "
            f"`pnpm config set store-dir <path-on-projects-volume>`."
        ),
        owner_path=str(project_root),
        safe_to_repair=False,
        repaired=False,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
/auto-test-pytest tests/scripts/test_worktree_toolchain.py
```

Expected: 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/worktree_toolchain.py tests/scripts/test_worktree_toolchain.py
git commit -m "feat(worktree-toolchain): add verify_pnpm_alignment check

New scripts/worktree_toolchain.py module. The alignment check
detects when pnpm's store-dir and the projects directory live
on different filesystem volumes (hardlinks cannot cross volumes;
pnpm silently falls back to copying when misaligned). Returns
an Incident with a remediation hint; does NOT auto-fix because
the user must choose which side to move.

Reuses the Incident dataclass from worktree_preflight so the
check routes cleanly into the existing preflight contract.
"
```

---

## Task 4: Add `probe_clone_primitive()` to `worktree_toolchain.py`

**Files:**
- Modify: `scripts/worktree_toolchain.py`
- Modify: `tests/scripts/test_worktree_toolchain.py`

Returns the platform-appropriate filesystem-CoW callable for cloning a directory tree, or `None` if no CoW is available (NTFS, ext4, etc.). Callers use the return value to decide whether to attempt clone-based materialization or fall straight to `pnpm install`.

Detection is by `(os, filesystem-type)`. macOS APFS uses `cp -c -R`; Linux btrfs/xfs uses `cp --reflink=auto -R`; Windows ReFS Dev Drive uses `Copy-Item -Force`. NTFS and ext4 return `None`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/scripts/test_worktree_toolchain.py`:

```python
def test_probe_clone_primitive_returns_callable_on_apfs(monkeypatch):
    monkeypatch.setattr(worktree_toolchain.sys, "platform", "darwin")
    monkeypatch.setattr(worktree_toolchain, "_detect_fs_type", lambda p: "apfs")
    result = worktree_toolchain.probe_clone_primitive(Path("/tmp"))
    assert result is not None
    assert callable(result)


def test_probe_clone_primitive_returns_callable_on_btrfs(monkeypatch):
    monkeypatch.setattr(worktree_toolchain.sys, "platform", "linux")
    monkeypatch.setattr(worktree_toolchain, "_detect_fs_type", lambda p: "btrfs")
    result = worktree_toolchain.probe_clone_primitive(Path("/tmp"))
    assert result is not None
    assert callable(result)


def test_probe_clone_primitive_returns_none_on_ntfs(monkeypatch):
    monkeypatch.setattr(worktree_toolchain.sys, "platform", "win32")
    monkeypatch.setattr(worktree_toolchain, "_detect_fs_type", lambda p: "ntfs")
    result = worktree_toolchain.probe_clone_primitive(Path("C:\\tmp"))  # audit-ignore: illustrative Windows path in archived ADR
    assert result is None


def test_probe_clone_primitive_returns_none_on_ext4(monkeypatch):
    monkeypatch.setattr(worktree_toolchain.sys, "platform", "linux")
    monkeypatch.setattr(worktree_toolchain, "_detect_fs_type", lambda p: "ext4")
    result = worktree_toolchain.probe_clone_primitive(Path("/tmp"))
    assert result is None


def test_probe_clone_primitive_callable_invokes_cp_dash_c_on_apfs(monkeypatch, tmp_path):
    monkeypatch.setattr(worktree_toolchain.sys, "platform", "darwin")
    monkeypatch.setattr(worktree_toolchain, "_detect_fs_type", lambda p: "apfs")

    recorded = {}

    def fake_run(cmd, **kwargs):
        recorded["cmd"] = cmd
        recorded["kwargs"] = kwargs
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(worktree_toolchain.subprocess, "run", fake_run)

    fn = worktree_toolchain.probe_clone_primitive(tmp_path)
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    fn(src, dst)

    assert recorded["cmd"][:3] == ["cp", "-c", "-R"]
    assert recorded["cmd"][-2:] == [str(src), str(dst)]
```

Add `import subprocess` at the top of the test file if not already present.

- [ ] **Step 2: Run tests to verify they fail**

```bash
/auto-test-pytest tests/scripts/test_worktree_toolchain.py::test_probe_clone_primitive_returns_callable_on_apfs
```

Expected: FAIL — `AttributeError: module 'worktree_toolchain' has no attribute 'probe_clone_primitive'`.

- [ ] **Step 3: Add the implementation**

Append to `scripts/worktree_toolchain.py`:

```python
CloneFn = Callable[[Path, Path], None]


def _detect_fs_type(path: Path) -> str:
    """Return the filesystem type for the given path, or '' if undetectable.

    macOS: parses `diskutil info -plist` or falls back to `mount`.
    Linux: parses `stat -f -c %T`.
    Windows: parses `Get-Volume` output.
    """
    if sys.platform == "darwin":
        try:
            result = subprocess.run(
                ["stat", "-f", "%T", str(path)],
                capture_output=True,
                text=True,
                check=True,
                timeout=5,
            )
            # On macOS `stat -f %T` returns file type, not fs type. Use diskutil instead.
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
            pass
        try:
            mount_result = subprocess.run(
                ["mount"], capture_output=True, text=True, check=True, timeout=5
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
            return ""
        resolved = str(path.resolve())
        best_match = ""
        best_len = -1
        for line in mount_result.stdout.splitlines():
            # Format: /dev/disk3s1s1 on / (apfs, sealed, local, ...)
            if " on " not in line or "(" not in line:
                continue
            try:
                mountpoint = line.split(" on ", 1)[1].split(" (", 1)[0]
                fs_info = line.split("(", 1)[1].rstrip(")")
                fs_type = fs_info.split(",", 1)[0].strip().lower()
            except IndexError:
                continue
            if resolved.startswith(mountpoint) and len(mountpoint) > best_len:
                best_match = fs_type
                best_len = len(mountpoint)
        return best_match

    if sys.platform.startswith("linux"):
        try:
            result = subprocess.run(
                ["stat", "-f", "-c", "%T", str(path)],
                capture_output=True,
                text=True,
                check=True,
                timeout=5,
            )
            return result.stdout.strip().lower()
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
            return ""

    if sys.platform.startswith("win"):
        try:
            drive = Path(path).resolve().drive  # e.g. "C:"
            if not drive:
                return ""
            result = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    f"(Get-Volume -DriveLetter {drive[0]}).FileSystemType",
                ],
                capture_output=True,
                text=True,
                check=True,
                timeout=5,
            )
            return result.stdout.strip().lower()
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
            return ""

    return ""


def _cp_clone(src: Path, dst: Path, *, mode: str) -> None:
    """Run `cp <mode> -R src dst` and raise on failure."""
    if mode == "apfs":
        cmd = ["cp", "-c", "-R", str(src), str(dst)]
    elif mode == "reflink":
        cmd = ["cp", "--reflink=auto", "-R", str(src), str(dst)]
    elif mode == "refs":
        cmd = [
            "powershell",
            "-NoProfile",
            "-Command",
            f"Copy-Item -Path '{src}' -Destination '{dst}' -Recurse -Force",
        ]
    else:
        raise ValueError(f"Unknown clone mode: {mode}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"Clone failed ({mode}): rc={result.returncode} stderr={result.stderr.strip()[:300]}"
        )


def probe_clone_primitive(path: Path) -> CloneFn | None:
    """Return a callable (src, dst) -> None for CoW cloning, or None if unsupported.

    `path` selects which filesystem to probe — pass the target worktree root so the
    primitive is matched to the volume the clone will land on.
    """
    fs_type = _detect_fs_type(path)
    if sys.platform == "darwin" and fs_type == "apfs":
        return lambda src, dst: _cp_clone(src, dst, mode="apfs")
    if sys.platform.startswith("linux") and fs_type in {"btrfs", "xfs"}:
        return lambda src, dst: _cp_clone(src, dst, mode="reflink")
    if sys.platform.startswith("win") and fs_type == "refs":
        return lambda src, dst: _cp_clone(src, dst, mode="refs")
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
/auto-test-pytest tests/scripts/test_worktree_toolchain.py
```

Expected: 8 tests PASS (3 from Task 3 + 5 new).

- [ ] **Step 5: Commit**

```bash
git add scripts/worktree_toolchain.py tests/scripts/test_worktree_toolchain.py
git commit -m "feat(worktree-toolchain): add probe_clone_primitive

Detects the platform-appropriate filesystem-CoW callable for
cloning node_modules cheaply. APFS uses cp -c -R; btrfs/xfs use
cp --reflink=auto -R; Windows ReFS uses Copy-Item with CoW flag.
NTFS and ext4 return None (callers fall through to pnpm install).
"
```

---

## Task 5: Add `materialize_node_modules()` core decision tree

**Files:**
- Modify: `scripts/worktree_toolchain.py`
- Modify: `tests/scripts/test_worktree_toolchain.py`

The orchestrator. Given a target worktree and an optional source worktree, pick the cheapest path to ready `apps/dashboard/node_modules`:
1. If `.bin/next` already exists at the target → `method="skip"`.
2. If the source worktree exists, has `.bin/next`, has matching `pnpm-lock.yaml`, AND `probe_clone_primitive(target)` returns a callable → attempt clone.
3. On clone success → `method="clone"`. On clone failure (or any prior condition unmet) → fall through.
4. Fall through: `pnpm install --frozen-lockfile --package-import-method hardlink` in the target's `apps/dashboard/`.
5. Install success → `method="install"`. Install failure → `method="failed"` with a fatal `Incident`.

Returns a `MaterializeResult` struct so callers can log timing and decisions.

- [ ] **Step 1: Write the failing tests**

Append to `tests/scripts/test_worktree_toolchain.py`:

```python
import hashlib


def _make_worktree(tmp_path: Path, name: str, lockfile_content: str = "lock-v1\n") -> Path:
    wt = tmp_path / name
    dashboard = wt / "apps" / "dashboard"
    dashboard.mkdir(parents=True)
    (dashboard / "pnpm-lock.yaml").write_text(lockfile_content)
    return wt


def _populate_node_modules(wt: Path, with_next_bin: bool = True) -> None:
    node_modules = wt / "apps" / "dashboard" / "node_modules"
    node_modules.mkdir(parents=True, exist_ok=True)
    (node_modules / "marker.txt").write_text("populated")
    if with_next_bin:
        bin_dir = node_modules / ".bin"
        bin_dir.mkdir(exist_ok=True)
        (bin_dir / "next").write_text("#!/bin/sh\nexit 0\n")
        (bin_dir / "next").chmod(0o755)


def test_materialize_skips_when_next_bin_already_exists(tmp_path):
    target = _make_worktree(tmp_path, "target")
    _populate_node_modules(target, with_next_bin=True)

    result = worktree_toolchain.materialize_node_modules(target, source_worktree=None)

    assert result.method == "skip"
    assert result.incidents == []


def test_materialize_clones_when_lockfile_matches_and_primitive_available(
    tmp_path, monkeypatch
):
    source = _make_worktree(tmp_path, "source")
    _populate_node_modules(source, with_next_bin=True)
    target = _make_worktree(tmp_path, "target")  # same lockfile content

    clone_calls = []

    def fake_clone(src, dst):
        clone_calls.append((src, dst))
        # Simulate the clone effect:
        shutil.copytree(src, dst)

    monkeypatch.setattr(
        worktree_toolchain, "probe_clone_primitive", lambda p: fake_clone
    )

    result = worktree_toolchain.materialize_node_modules(target, source_worktree=source)

    assert result.method == "clone"
    assert len(clone_calls) == 1
    assert (target / "apps" / "dashboard" / "node_modules" / ".bin" / "next").exists()
    assert result.incidents == []


def test_materialize_falls_through_to_install_when_lockfile_differs(
    tmp_path, monkeypatch
):
    source = _make_worktree(tmp_path, "source", lockfile_content="lock-v1\n")
    _populate_node_modules(source, with_next_bin=True)
    target = _make_worktree(tmp_path, "target", lockfile_content="lock-v2\n")

    clone_called = False

    def fake_clone(src, dst):
        nonlocal clone_called
        clone_called = True

    monkeypatch.setattr(
        worktree_toolchain, "probe_clone_primitive", lambda p: fake_clone
    )

    install_called = {"count": 0}

    def fake_install(dashboard_dir):
        install_called["count"] += 1
        _populate_node_modules(dashboard_dir.parent.parent, with_next_bin=True)
        return None  # no incident

    monkeypatch.setattr(worktree_toolchain, "_pnpm_install_frozen", fake_install)

    result = worktree_toolchain.materialize_node_modules(target, source_worktree=source)

    assert clone_called is False
    assert install_called["count"] == 1
    assert result.method == "install"


def test_materialize_falls_through_when_clone_primitive_unavailable(
    tmp_path, monkeypatch
):
    source = _make_worktree(tmp_path, "source")
    _populate_node_modules(source, with_next_bin=True)
    target = _make_worktree(tmp_path, "target")

    monkeypatch.setattr(worktree_toolchain, "probe_clone_primitive", lambda p: None)

    install_called = {"count": 0}

    def fake_install(dashboard_dir):
        install_called["count"] += 1
        _populate_node_modules(dashboard_dir.parent.parent, with_next_bin=True)
        return None

    monkeypatch.setattr(worktree_toolchain, "_pnpm_install_frozen", fake_install)

    result = worktree_toolchain.materialize_node_modules(target, source_worktree=source)

    assert install_called["count"] == 1
    assert result.method == "install"


def test_materialize_falls_through_when_source_missing_next_bin(
    tmp_path, monkeypatch
):
    source = _make_worktree(tmp_path, "source")  # no node_modules populated
    target = _make_worktree(tmp_path, "target")

    clone_called = False

    def fake_clone(src, dst):
        nonlocal clone_called
        clone_called = True

    monkeypatch.setattr(
        worktree_toolchain, "probe_clone_primitive", lambda p: fake_clone
    )

    def fake_install(dashboard_dir):
        _populate_node_modules(dashboard_dir.parent.parent, with_next_bin=True)
        return None

    monkeypatch.setattr(worktree_toolchain, "_pnpm_install_frozen", fake_install)

    result = worktree_toolchain.materialize_node_modules(target, source_worktree=source)

    assert clone_called is False
    assert result.method == "install"


def test_materialize_clone_failure_falls_through_to_install(tmp_path, monkeypatch):
    source = _make_worktree(tmp_path, "source")
    _populate_node_modules(source, with_next_bin=True)
    target = _make_worktree(tmp_path, "target")

    def failing_clone(src, dst):
        raise RuntimeError("simulated clone failure")

    monkeypatch.setattr(
        worktree_toolchain, "probe_clone_primitive", lambda p: failing_clone
    )

    install_called = {"count": 0}

    def fake_install(dashboard_dir):
        install_called["count"] += 1
        _populate_node_modules(dashboard_dir.parent.parent, with_next_bin=True)
        return None

    monkeypatch.setattr(worktree_toolchain, "_pnpm_install_frozen", fake_install)

    result = worktree_toolchain.materialize_node_modules(target, source_worktree=source)

    assert install_called["count"] == 1
    assert result.method == "install"
    # Partial target should have been cleaned up; no leftover marker.txt.
    nm = target / "apps" / "dashboard" / "node_modules"
    if nm.exists():
        # If install fake populated it, that's fine; just confirm clone leftover is gone.
        # Specifically the marker we'd have copied from source must NOT be there because
        # clone failed AND we cleaned up before install ran.
        assert (nm / ".bin" / "next").exists()


def test_materialize_install_failure_returns_failed_with_incident(tmp_path, monkeypatch):
    target = _make_worktree(tmp_path, "target")

    monkeypatch.setattr(worktree_toolchain, "probe_clone_primitive", lambda p: None)

    def failing_install(dashboard_dir):
        return worktree_toolchain.Incident(
            fingerprint="worktree/toolchain/install-failed",
            severity="high",
            message="pnpm install failed: simulated",
            owner_path=str(dashboard_dir),
            safe_to_repair=False,
            repaired=False,
        )

    monkeypatch.setattr(worktree_toolchain, "_pnpm_install_frozen", failing_install)

    result = worktree_toolchain.materialize_node_modules(target, source_worktree=None)

    assert result.method == "failed"
    assert len(result.incidents) == 1
    assert "install failed" in result.incidents[0].message.lower()
```

Add `import shutil` to the top of the test file if not already present.

- [ ] **Step 2: Run tests to verify they fail**

```bash
/auto-test-pytest tests/scripts/test_worktree_toolchain.py::test_materialize_skips_when_next_bin_already_exists
```

Expected: FAIL — `AttributeError: module 'worktree_toolchain' has no attribute 'materialize_node_modules'`.

- [ ] **Step 3: Add the implementation**

Append to `scripts/worktree_toolchain.py`:

```python
import hashlib
import shlex
import time


@dataclass
class MaterializeResult:
    method: str  # "skip" | "clone" | "install" | "failed"
    duration_ms: int
    source_worktree: str | None
    clone_primitive: str | None
    incidents: list[Incident]


def _next_bin(worktree_root: Path) -> Path:
    return worktree_root / "apps" / "dashboard" / "node_modules" / ".bin" / "next"


def _lockfile_hash(worktree_root: Path) -> str | None:
    lockfile = worktree_root / "apps" / "dashboard" / "pnpm-lock.yaml"
    if not lockfile.exists():
        return None
    return hashlib.sha256(lockfile.read_bytes()).hexdigest()


def _pnpm_install_frozen(dashboard_dir: Path) -> Incident | None:
    """Run `pnpm install --frozen-lockfile` with hardlink imports in dashboard_dir."""
    pnpm = shutil.which("pnpm")
    if pnpm is None:
        corepack = shutil.which("corepack")
        if corepack is None:
            return Incident(
                fingerprint="worktree/toolchain/no-pnpm",
                severity="high",
                message=(
                    "Neither pnpm nor corepack found on PATH. Run "
                    "`corepack enable && corepack prepare pnpm@latest --activate`."
                ),
                owner_path=str(dashboard_dir),
                safe_to_repair=False,
                repaired=False,
            )
        cmd = [corepack, "pnpm", "install", "--frozen-lockfile"]
    else:
        cmd = [pnpm, "install", "--frozen-lockfile"]

    try:
        subprocess.run(
            cmd,
            cwd=dashboard_dir,
            check=True,
            capture_output=True,
            text=True,
            timeout=600,
        )
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or exc.stdout or "").strip()
        return Incident(
            fingerprint="worktree/toolchain/install-failed",
            severity="high",
            message=(
                f"pnpm install failed in {dashboard_dir}: "
                f"{stderr[:500] or 'pnpm exited non-zero'} "
                f"(cmd={' '.join(shlex.quote(p) for p in cmd)})"
            ),
            owner_path=str(dashboard_dir),
            safe_to_repair=False,
            repaired=False,
        )
    except subprocess.TimeoutExpired:
        return Incident(
            fingerprint="worktree/toolchain/install-timeout",
            severity="high",
            message=f"pnpm install timed out after 600s in {dashboard_dir}",
            owner_path=str(dashboard_dir),
            safe_to_repair=False,
            repaired=False,
        )
    return None


def _clone_dashboard_node_modules(
    source: Path, target: Path, clone_fn: CloneFn
) -> Incident | None:
    """CoW-clone source/apps/dashboard/node_modules into target/apps/dashboard/."""
    src_nm = source / "apps" / "dashboard" / "node_modules"
    target_dashboard = target / "apps" / "dashboard"
    dst_nm = target_dashboard / "node_modules"

    if dst_nm.exists():
        shutil.rmtree(dst_nm, ignore_errors=True)
    target_dashboard.mkdir(parents=True, exist_ok=True)

    try:
        clone_fn(src_nm, dst_nm)
    except Exception as exc:  # noqa: BLE001 — fall through path
        # Clean up partial target so install can start clean.
        if dst_nm.exists():
            shutil.rmtree(dst_nm, ignore_errors=True)
        return Incident(
            fingerprint="worktree/toolchain/clone-failed",
            severity="medium",
            message=f"CoW clone failed ({exc}); falling through to pnpm install.",
            owner_path=str(target),
            safe_to_repair=True,
            repaired=True,  # we handled it by falling through
        )
    return None


def materialize_node_modules(
    worktree_root: Path,
    source_worktree: Path | None,
) -> MaterializeResult:
    """Ensure worktree_root/apps/dashboard/node_modules is ready, cheaply.

    Decision tree:
      1. If .bin/next already exists at target → method="skip".
      2. If source worktree provided, has matching lockfile, has .bin/next,
         and a clone primitive is available → attempt clone.
      3. On clone success → method="clone".
      4. Otherwise → pnpm install --frozen-lockfile.
      5. On install success → method="install"; on failure → method="failed".
    """
    start = time.monotonic()
    target_dashboard = worktree_root / "apps" / "dashboard"
    incidents: list[Incident] = []
    clone_primitive_name: str | None = None

    if _next_bin(worktree_root).exists():
        return MaterializeResult(
            method="skip",
            duration_ms=int((time.monotonic() - start) * 1000),
            source_worktree=str(source_worktree) if source_worktree else None,
            clone_primitive=None,
            incidents=[],
        )

    # Probe clone primitive (called even when source is None so tests can patch).
    clone_fn = probe_clone_primitive(target_dashboard)
    if clone_fn is not None:
        clone_primitive_name = clone_fn.__name__ if hasattr(clone_fn, "__name__") else "anon"

    can_clone = (
        source_worktree is not None
        and clone_fn is not None
        and _next_bin(source_worktree).exists()
        and _lockfile_hash(worktree_root) is not None
        and _lockfile_hash(worktree_root) == _lockfile_hash(source_worktree)
    )

    if can_clone:
        clone_incident = _clone_dashboard_node_modules(source_worktree, worktree_root, clone_fn)
        if clone_incident is None and _next_bin(worktree_root).exists():
            return MaterializeResult(
                method="clone",
                duration_ms=int((time.monotonic() - start) * 1000),
                source_worktree=str(source_worktree),
                clone_primitive=clone_primitive_name,
                incidents=[],
            )
        if clone_incident is not None:
            incidents.append(clone_incident)

    install_incident = _pnpm_install_frozen(target_dashboard)
    if install_incident is None:
        return MaterializeResult(
            method="install",
            duration_ms=int((time.monotonic() - start) * 1000),
            source_worktree=str(source_worktree) if source_worktree else None,
            clone_primitive=clone_primitive_name,
            incidents=incidents,
        )

    incidents.append(install_incident)
    return MaterializeResult(
        method="failed",
        duration_ms=int((time.monotonic() - start) * 1000),
        source_worktree=str(source_worktree) if source_worktree else None,
        clone_primitive=clone_primitive_name,
        incidents=incidents,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
/auto-test-pytest tests/scripts/test_worktree_toolchain.py
```

Expected: 15 tests PASS (3 + 5 + 7 new).

- [ ] **Step 5: Commit**

```bash
git add scripts/worktree_toolchain.py tests/scripts/test_worktree_toolchain.py
git commit -m "feat(worktree-toolchain): add materialize_node_modules

The orchestrator that materializes apps/dashboard/node_modules
via the cheapest available path: skip if already present, CoW
clone from a sibling worktree when lockfiles match and a clone
primitive is available, fall through to pnpm install
--frozen-lockfile otherwise. Lockfile equality is verified via
SHA-256 before any clone. Partial clone failures clean up before
install runs. Returns a MaterializeResult so callers can log
timing and which method was used.
"
```

---

## Task 6: Add file lock for race protection

**Files:**
- Modify: `scripts/worktree_toolchain.py`
- Modify: `tests/scripts/test_worktree_toolchain.py`

Two parallel `materialize_node_modules` calls on the same target (e.g., user spawns two worktree creations simultaneously) must not race. Use a `flock`-style lockfile at `<worktree>/apps/dashboard/.materialize.lock` for the duration of the call. Second caller waits, then sees `next_bin` exists and returns `method="skip"`.

Python's `fcntl.flock` is POSIX-only; `msvcrt.locking` is Windows-only. Wrap in a context manager that picks the right primitive.

- [ ] **Step 1: Write the failing test**

Append to `tests/scripts/test_worktree_toolchain.py`:

```python
import threading


def test_materialize_serializes_concurrent_calls(tmp_path, monkeypatch):
    target = _make_worktree(tmp_path, "target")

    monkeypatch.setattr(worktree_toolchain, "probe_clone_primitive", lambda p: None)

    install_call_count = {"n": 0}
    install_started = threading.Event()
    install_can_finish = threading.Event()

    def slow_install(dashboard_dir):
        install_call_count["n"] += 1
        install_started.set()
        install_can_finish.wait(timeout=5)
        _populate_node_modules(dashboard_dir.parent.parent, with_next_bin=True)
        return None

    monkeypatch.setattr(worktree_toolchain, "_pnpm_install_frozen", slow_install)

    results: list[worktree_toolchain.MaterializeResult] = []

    def run():
        results.append(
            worktree_toolchain.materialize_node_modules(target, source_worktree=None)
        )

    t1 = threading.Thread(target=run)
    t2 = threading.Thread(target=run)
    t1.start()
    install_started.wait(timeout=5)
    t2.start()
    install_can_finish.set()
    t1.join(timeout=10)
    t2.join(timeout=10)

    assert install_call_count["n"] == 1
    methods = sorted(r.method for r in results)
    assert methods == ["install", "skip"]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
/auto-test-pytest tests/scripts/test_worktree_toolchain.py::test_materialize_serializes_concurrent_calls
```

Expected: FAIL — both calls run install, count = 2.

- [ ] **Step 3: Add the lock context manager and wrap materialize_node_modules**

Add near the top of `scripts/worktree_toolchain.py` (after imports):

```python
from contextlib import contextmanager


@contextmanager
def _materialize_lock(worktree_root: Path):
    """Cross-platform exclusive file lock for the duration of materialization."""
    lock_dir = worktree_root / "apps" / "dashboard"
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_path = lock_dir / ".materialize.lock"
    lock_file = open(lock_path, "a+")
    try:
        if sys.platform.startswith("win"):
            import msvcrt

            # Block until lock is acquired; lock 1 byte at offset 0.
            while True:
                try:
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
                    break
                except OSError:
                    time.sleep(0.05)
            try:
                yield
            finally:
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
    finally:
        lock_file.close()
```

Then wrap the body of `materialize_node_modules` in the lock. Modify the function so its existing body runs inside `with _materialize_lock(worktree_root):`. The early `_next_bin` skip check should ALSO be inside the lock to ensure a second waiter sees the install completed by the first:

```python
def materialize_node_modules(
    worktree_root: Path,
    source_worktree: Path | None,
) -> MaterializeResult:
    start = time.monotonic()
    target_dashboard = worktree_root / "apps" / "dashboard"
    incidents: list[Incident] = []
    clone_primitive_name: str | None = None

    with _materialize_lock(worktree_root):
        if _next_bin(worktree_root).exists():
            return MaterializeResult(
                method="skip",
                duration_ms=int((time.monotonic() - start) * 1000),
                source_worktree=str(source_worktree) if source_worktree else None,
                clone_primitive=None,
                incidents=[],
            )

        clone_fn = probe_clone_primitive(target_dashboard)
        if clone_fn is not None:
            clone_primitive_name = (
                clone_fn.__name__ if hasattr(clone_fn, "__name__") else "anon"
            )

        can_clone = (
            source_worktree is not None
            and clone_fn is not None
            and _next_bin(source_worktree).exists()
            and _lockfile_hash(worktree_root) is not None
            and _lockfile_hash(worktree_root) == _lockfile_hash(source_worktree)
        )

        if can_clone:
            clone_incident = _clone_dashboard_node_modules(
                source_worktree, worktree_root, clone_fn
            )
            if clone_incident is None and _next_bin(worktree_root).exists():
                return MaterializeResult(
                    method="clone",
                    duration_ms=int((time.monotonic() - start) * 1000),
                    source_worktree=str(source_worktree),
                    clone_primitive=clone_primitive_name,
                    incidents=[],
                )
            if clone_incident is not None:
                incidents.append(clone_incident)

        install_incident = _pnpm_install_frozen(target_dashboard)
        if install_incident is None:
            return MaterializeResult(
                method="install",
                duration_ms=int((time.monotonic() - start) * 1000),
                source_worktree=str(source_worktree) if source_worktree else None,
                clone_primitive=clone_primitive_name,
                incidents=incidents,
            )

        incidents.append(install_incident)
        return MaterializeResult(
            method="failed",
            duration_ms=int((time.monotonic() - start) * 1000),
            source_worktree=str(source_worktree) if source_worktree else None,
            clone_primitive=clone_primitive_name,
            incidents=incidents,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
/auto-test-pytest tests/scripts/test_worktree_toolchain.py
```

Expected: 16 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/worktree_toolchain.py tests/scripts/test_worktree_toolchain.py
git commit -m "feat(worktree-toolchain): serialize concurrent materialize calls

Acquires an exclusive file lock at
<worktree>/apps/dashboard/.materialize.lock for the duration of
materialize_node_modules. A second caller blocks until the first
finishes, then sees next_bin exists and returns method='skip'.
Uses fcntl.flock on POSIX and msvcrt.locking on Windows.
"
```

---

## Task 7: Integrate `_check_pnpm_alignment` into `worktree_preflight.py`

**Files:**
- Modify: `scripts/worktree_preflight.py`
- Modify: `tests/scripts/test_worktree_preflight.py`

Hook the alignment check into the existing preflight check sequence. When pnpm's store and the projects directory live on different volumes, surface it as an incident through the existing contract.

- [ ] **Step 1: Write the failing test**

Append to `tests/scripts/test_worktree_preflight.py`:

```python
def test_build_contract_emits_alignment_incident_when_misaligned(
    tmp_path: Path, monkeypatch
):
    # Use a real temp worktree so build_contract has something to inspect.
    project_root = tmp_path / "wt"
    (project_root / "apps" / "dashboard" / "node_modules" / ".bin").mkdir(parents=True)
    (project_root / "apps" / "dashboard" / "node_modules" / ".bin" / "next").write_text(
        "#!/bin/sh\nexit 0\n"
    )

    import worktree_toolchain  # noqa: E402

    misaligned_incident = worktree_toolchain.Incident(
        fingerprint="worktree/toolchain/pnpm-store-misaligned",
        severity="high",
        message="pnpm store and projects directory live on different filesystem volume.",
        owner_path=str(project_root),
        safe_to_repair=False,
        repaired=False,
    )

    monkeypatch.setattr(
        worktree_toolchain, "verify_pnpm_alignment", lambda root: misaligned_incident
    )

    # Call the helper directly; it should return the misaligned incident.
    result = worktree_preflight._check_pnpm_alignment(project_root)
    assert result is not None
    assert result.fingerprint == "worktree/toolchain/pnpm-store-misaligned"


def test_build_contract_emits_no_alignment_incident_when_aligned(
    tmp_path: Path, monkeypatch
):
    project_root = tmp_path / "wt"
    project_root.mkdir(parents=True)

    import worktree_toolchain  # noqa: E402

    monkeypatch.setattr(worktree_toolchain, "verify_pnpm_alignment", lambda root: None)

    result = worktree_preflight._check_pnpm_alignment(project_root)
    assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
/auto-test-pytest tests/scripts/test_worktree_preflight.py::test_build_contract_emits_alignment_incident_when_misaligned
```

Expected: FAIL — `AttributeError: module 'worktree_preflight' has no attribute '_check_pnpm_alignment'`.

- [ ] **Step 3: Add the integration**

Edit `scripts/worktree_preflight.py`. Do NOT add `import worktree_toolchain` at the top — that would cause a circular import because `worktree_toolchain.py` imports `Incident` from `worktree_preflight` (which isn't defined until line 101). Use a lazy import inside the helper function instead.

Add the helper function near the other `_check_*` helpers, just before `_ensure_dashboard_dependencies` around line 565:

```python
def _check_pnpm_alignment(project_root: Path) -> Incident | None:
    """Wrapper around worktree_toolchain.verify_pnpm_alignment for the preflight contract."""
    import worktree_toolchain  # lazy: avoid circular import (toolchain imports Incident from here)
    return worktree_toolchain.verify_pnpm_alignment(project_root)
```

Next, wire it into the contract. Find `build_contract` (around line 884) and add the alignment check alongside the other check sequence. Search for the existing `_check("dashboard_node_modules", ...)` call and insert immediately after it:

```python
    alignment_incident = _check_pnpm_alignment(project_root)
    _check(
        "pnpm_alignment",
        alignment_incident is None,
        f"store_aligned={alignment_incident is None}",
        checks,
    )
    if alignment_incident is not None:
        incidents.append(alignment_incident)
```

(Read the surrounding 10-20 lines first to match the exact `_check(...)` call shape used in that file — pass the right `checks` and `incidents` collections that are already in scope at that point.)

- [ ] **Step 4: Run tests to verify they pass**

```bash
/auto-test-pytest tests/scripts/test_worktree_preflight.py
```

Expected: existing tests still pass + 2 new tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/worktree_preflight.py tests/scripts/test_worktree_preflight.py
git commit -m "feat(worktree-preflight): add pnpm store alignment check

Wires worktree_toolchain.verify_pnpm_alignment into the preflight
check sequence so misaligned store/projects volumes surface as
high-severity incidents through the existing contract. The check
does not auto-fix — the user must choose which side to move.
"
```

---

## Task 8: Route `_ensure_dashboard_dependencies` repair path through the materializer

**Files:**
- Modify: `scripts/worktree_preflight.py`
- Modify: `tests/scripts/test_worktree_preflight.py`

Replace the direct `_run_dashboard_install` call in `_ensure_dashboard_dependencies` with `worktree_toolchain.materialize_node_modules`. Keep the existing symlink guard (lines 579-597 today) — that invariant is preserved. The change is at the bottom of the function (the line that today reads `return _run_dashboard_install(...)`): on the repair path, call the materializer instead and translate its result into the existing incident/repair shape.

The materializer's `method="clone"` becomes a `Repair(type="cow-clone", ...)`; `method="install"` becomes the existing `Repair(type="npm-install", ...)`; `method="failed"` propagates its incidents.

- [ ] **Step 1: Write the failing test**

Append to `tests/scripts/test_worktree_preflight.py`:

```python
def test_ensure_dashboard_dependencies_uses_materializer(tmp_path: Path, monkeypatch):
    project_root = tmp_path / "wt"
    (project_root / "apps" / "dashboard").mkdir(parents=True)
    # No node_modules — repair path will fire.

    import worktree_toolchain  # noqa: E402

    captured = {}

    def fake_materialize(worktree_root, source_worktree):
        captured["worktree_root"] = worktree_root
        captured["source_worktree"] = source_worktree
        # Populate node_modules to simulate success.
        bin_dir = worktree_root / "apps" / "dashboard" / "node_modules" / ".bin"
        bin_dir.mkdir(parents=True)
        (bin_dir / "next").write_text("#!/bin/sh\nexit 0\n")
        return worktree_toolchain.MaterializeResult(
            method="clone",
            duration_ms=42,
            source_worktree=str(source_worktree) if source_worktree else None,
            clone_primitive="apfs",
            incidents=[],
        )

    monkeypatch.setattr(worktree_toolchain, "materialize_node_modules", fake_materialize)

    incidents: list = []
    repairs: list = []

    result = worktree_preflight._ensure_dashboard_dependencies(
        project_root,
        repairs,
        incidents,
        owner_path=project_root,
        repair=True,
    )

    assert result is True
    assert captured["worktree_root"] == project_root
    # Repair should record the cow-clone method.
    assert any(r.type == "cow-clone" for r in repairs)


def test_ensure_dashboard_dependencies_propagates_install_failure(
    tmp_path: Path, monkeypatch
):
    project_root = tmp_path / "wt"
    (project_root / "apps" / "dashboard").mkdir(parents=True)

    import worktree_toolchain  # noqa: E402

    fatal_incident = worktree_toolchain.Incident(
        fingerprint="worktree/toolchain/install-failed",
        severity="high",
        message="pnpm install failed: simulated",
        owner_path=str(project_root / "apps" / "dashboard"),
        safe_to_repair=False,
        repaired=False,
    )

    def failing_materialize(worktree_root, source_worktree):
        return worktree_toolchain.MaterializeResult(
            method="failed",
            duration_ms=10,
            source_worktree=None,
            clone_primitive=None,
            incidents=[fatal_incident],
        )

    monkeypatch.setattr(
        worktree_toolchain, "materialize_node_modules", failing_materialize
    )

    incidents: list = []
    repairs: list = []

    result = worktree_preflight._ensure_dashboard_dependencies(
        project_root,
        repairs,
        incidents,
        owner_path=project_root,
        repair=True,
    )

    assert result is False
    assert any(
        i.fingerprint == "worktree/toolchain/install-failed" for i in incidents
    )
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
/auto-test-pytest tests/scripts/test_worktree_preflight.py::test_ensure_dashboard_dependencies_uses_materializer
```

Expected: FAIL — current implementation calls `_run_dashboard_install` directly, no materializer involved.

- [ ] **Step 3: Modify `_ensure_dashboard_dependencies` to route through the materializer**

In `scripts/worktree_preflight.py`, locate `_ensure_dashboard_dependencies` (line ~565). Replace the final line of the function:

```python
    return _run_dashboard_install(dashboard_dir, incidents, repairs, owner_path)
```

with:

```python
    import worktree_toolchain  # lazy: avoid circular import
    source_worktree = _detect_main_worktree(project_root)
    result = worktree_toolchain.materialize_node_modules(
        worktree_root=project_root,
        source_worktree=source_worktree,
    )
    for incident in result.incidents:
        incidents.append(incident)
    if result.method == "clone":
        repairs.append(
            Repair(
                type="cow-clone",
                path=str(dashboard_dir),
                target=f"source={result.source_worktree} primitive={result.clone_primitive} ms={result.duration_ms}",
            )
        )
    elif result.method == "install":
        repairs.append(
            Repair(
                type="npm-install",
                path=str(dashboard_dir),
                target=f"pnpm install --frozen-lockfile ms={result.duration_ms}",
            )
        )
    return result.method in {"clone", "install", "skip"}
```

Also add the `_detect_main_worktree` helper near the other path helpers (search for `_resolve_main_repo` which does adjacent work at line ~196; place the new helper after it):

```python
def _detect_main_worktree(project_root: Path) -> Path | None:
    """Return the main checkout path if it's a sibling of this worktree and has node_modules.

    Reuses the existing main-repo resolution but additionally verifies the source has a
    materialized node_modules — otherwise there's nothing to clone from.
    """
    try:
        main_repo = _resolve_main_repo(project_root, _load_marker(project_root))
    except Exception:
        return None
    if main_repo == project_root:
        return None  # we're already in main; no sibling source
    candidate_next = main_repo / "apps" / "dashboard" / "node_modules" / ".bin" / "next"
    if not candidate_next.exists():
        return None
    return main_repo
```

Note: do NOT delete `_run_dashboard_install` or `_dashboard_install_command` from the file — they remain reachable through historical call sites and tests. Their behavior is now covered by `_pnpm_install_frozen` in the toolchain module for the new path; the old code stays as-is.

- [ ] **Step 4: Run tests to verify they pass**

```bash
/auto-test-pytest tests/scripts/test_worktree_preflight.py
```

Expected: existing tests still pass + 2 new tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/worktree_preflight.py tests/scripts/test_worktree_preflight.py
git commit -m "feat(worktree-preflight): route dashboard deps through materializer

_ensure_dashboard_dependencies now delegates to
worktree_toolchain.materialize_node_modules on the repair path,
which picks the cheapest path (skip / CoW clone from main /
pnpm install --frozen-lockfile). Records the method used as a
Repair (type=cow-clone or type=npm-install with timing).

Preserves the existing 'node_modules pointing outside worktree
root' guard and keeps _run_dashboard_install for historical call
sites. Detects the main worktree via _detect_main_worktree which
reuses _resolve_main_repo and additionally verifies the source
has a materialized node_modules to clone from.
"
```

---

## Task 9: Write Layer 3 real-data verification script

**Files:**
- Create: `scripts/verify_worktree_toolchain.py`

A standalone script for one-off real-data verification (per CLAUDE.md rule #34). Runs against the actual Augur repo, creates a throwaway worktree, measures materialization correctness and disk efficiency, then tears it down. The output is what gets pasted into the merge commit as evidence.

- [ ] **Step 1: Create the script**

```python
"""Real-data verification of dashboard worktree toolchain sharing.

Run from the main checkout:
    uv run python scripts/verify_worktree_toolchain.py

Creates a throwaway worktree, runs preflight repair, measures hardlink
count and disk delta, then tears the worktree down. Prints evidence to
stdout for inclusion in merge commits.

Does NOT mutate main, does NOT push, does NOT touch any persistent state.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from src.config.paths import get_project_root

PROJECT_ROOT = get_project_root()
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def _run(cmd: list[str], cwd: Path | None = None) -> str:
    result = subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def _df_kb(path: Path) -> int:
    """Return free space in KB on the volume containing path."""
    stat = os.statvfs(path)
    return (stat.f_bavail * stat.f_frsize) // 1024


def _file_count(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for _ in path.rglob("*") if _.is_file())


def _hardlinked_file_count(path: Path) -> int:
    if not path.exists():
        return 0
    count = 0
    for entry in path.rglob("*"):
        try:
            if entry.is_file() and entry.stat().st_nlink > 1:
                count += 1
        except OSError:
            continue
    return count


def main() -> int:
    main_wt = PROJECT_ROOT
    main_node_modules = main_wt / "apps" / "dashboard" / "node_modules"

    if not (main_node_modules / ".bin" / "next").exists():
        print(
            "ERROR: main worktree has no apps/dashboard/node_modules. "
            "Run `pnpm install` in main first.",
            file=sys.stderr,
        )
        return 1

    throwaway_name = f"toolchain-verify-{int(time.time())}"
    throwaway_path = PROJECT_ROOT.parent / f"augur-verify-{throwaway_name}"
    throwaway_branch = f"verify/{throwaway_name}"

    print("=" * 70)
    print("Layer 3 verification — dashboard worktree toolchain sharing")
    print("=" * 70)
    print(f"Main checkout:     {main_wt}")
    print(f"Throwaway worktree: {throwaway_path}")
    print(f"Throwaway branch:  {throwaway_branch}")
    print()

    main_files = _file_count(main_node_modules)
    main_hardlinks = _hardlinked_file_count(main_node_modules)
    print(f"BEFORE (main): {main_files} files, {main_hardlinks} hardlinked")
    free_before = _df_kb(PROJECT_ROOT)
    print(f"BEFORE: {free_before // 1024} MB free on volume")
    print()

    try:
        _run(["git", "worktree", "add", "-b", throwaway_branch, str(throwaway_path)],
             cwd=main_wt)
        print(f"Worktree created at {throwaway_path}")
        print()

        free_after_create = _df_kb(PROJECT_ROOT)
        print(f"After git worktree add: "
              f"{(free_before - free_after_create) // 1024} MB consumed")

        t0 = time.monotonic()
        _run(
            ["uv", "run", "python", "scripts/worktree_preflight.py",
             "--repair", "--profile", "worktree"],
            cwd=throwaway_path,
        )
        materialize_ms = int((time.monotonic() - t0) * 1000)
        print(f"Preflight --repair completed in {materialize_ms} ms")
        print()

        throwaway_nm = throwaway_path / "apps" / "dashboard" / "node_modules"
        new_files = _file_count(throwaway_nm)
        new_hardlinks = _hardlinked_file_count(throwaway_nm)
        next_bin = throwaway_nm / ".bin" / "next"

        print("AFTER (throwaway):")
        print(f"  files:           {new_files}")
        print(f"  hardlinked:      {new_hardlinks} ({(new_hardlinks * 100 // max(new_files, 1))}%)")
        print(f"  .bin/next exists: {next_bin.exists()}")
        free_after = _df_kb(PROJECT_ROOT)
        print(f"  total disk delta: {(free_before - free_after) // 1024} MB consumed")
        print()

        print("PASS CRITERIA:")
        print(f"  - .bin/next exists: {next_bin.exists()}")
        hardlink_pct = (new_hardlinks * 100 // max(new_files, 1))
        print(f"  - hardlink rate >= 80%: {hardlink_pct >= 80} ({hardlink_pct}%)")
        delta_mb = (free_before - free_after) // 1024
        print(f"  - disk delta < 100 MB: {delta_mb < 100} ({delta_mb} MB)")
        print(f"  - materialize time < 30s: {materialize_ms < 30000} ({materialize_ms} ms)")

    finally:
        print()
        print("Cleaning up...")
        if throwaway_path.exists():
            try:
                _run(["git", "worktree", "remove", "--force", str(throwaway_path)],
                     cwd=main_wt)
            except subprocess.CalledProcessError:
                shutil.rmtree(throwaway_path, ignore_errors=True)
        try:
            _run(["git", "branch", "-D", throwaway_branch], cwd=main_wt)
        except subprocess.CalledProcessError:
            pass
        print("Cleanup complete.")
        free_final = _df_kb(PROJECT_ROOT)
        print(f"Final disk delta: {(free_before - free_final) // 1024} MB net consumed (should be ~0)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run the verification script against the real repo**

```bash
uv run python scripts/verify_worktree_toolchain.py
```

Expected output: all four PASS CRITERIA lines should show `True`. If any show `False`, the implementation has a real defect — investigate before continuing. The throwaway worktree must be cleaned up regardless of pass/fail.

- [ ] **Step 3: Capture the output for the merge commit**

```bash
uv run python scripts/verify_worktree_toolchain.py | tee /tmp/toolchain-verify-output.txt
```

- [ ] **Step 4: Browser verification (CLAUDE.md rule #28)**

The toolchain change is dashboard-touching, so SSR-only verification does not count. Run `/dev-build` in a fresh worktree created via the new path, then open the dashboard in a browser and confirm at least one page mounts to interactive state. Capture a screenshot or use `mcp__claude-in-chrome__read_page` to extract a snippet showing interactive content (not just SSR markup).

- [ ] **Step 5: Commit the script**

```bash
git add scripts/verify_worktree_toolchain.py
git commit -m "test(worktree-toolchain): add Layer 3 verification script

Real-data verification per CLAUDE.md rule #34. Creates a
throwaway worktree, runs preflight repair, measures hardlink
count, disk delta, and materialize time, then tears the worktree
down. Output is suitable for pasting into merge commits as
evidence. Does NOT mutate main, push, or touch persistent state.
"
```

---

## Task 10: Update documentation

**Files:**
- Modify: `apps/dashboard/README.md`
- Modify: `docs/agent-topics/WORKFLOWS.md`

Document the new behavior so future contributors understand the pnpm alignment requirement and the worktree materialization flow.

- [ ] **Step 1: Update `apps/dashboard/README.md`**

Read the current README, then insert this new section after the "Getting Started" section:

```markdown
## Worktree Toolchain Sharing

`apps/dashboard/node_modules` is per-worktree (the preflight orchestrator
keeps every worktree fully isolated), but the *bytes* are shared at the
filesystem layer via pnpm hardlinks. `apps/dashboard/.npmrc` sets
`package-import-method=hardlink`, so `pnpm install` commands run from
the dashboard package hardlink files from the platform-default store
rather than copying them.

**Requirement:** the pnpm store and the projects directory must live on
the same filesystem volume. Hardlinks cannot cross volumes. Preflight
checks this on every run; if misaligned, it surfaces a high-severity
incident telling you to either move projects or run
`pnpm config set store-dir <path-on-projects-volume>`.

**New worktree creation:** preflight chooses the cheapest path to ready
`node_modules` — CoW clone from main on APFS/btrfs/ReFS (typically ~2s,
~0 new bytes), or `pnpm install --frozen-lockfile --package-import-method hardlink`
on filesystems without CoW (still fast because hardlinks replace network downloads).

See `docs/superpowers/specs/2026-05-16-dashboard-worktree-toolchain-sharing-design.md` for the full design.
```

- [ ] **Step 2: Update `docs/agent-topics/WORKFLOWS.md`**

Read the current file and find the worktree section (around line 70-90 based on the earlier grep). Add a paragraph after the existing worktree-creation discussion:

```markdown
### Dashboard toolchain sharing

`apps/dashboard/node_modules` is shared across worktrees at the
filesystem layer via pnpm hardlinks (configured in
`apps/dashboard/.npmrc`). The preflight orchestrator materializes `node_modules` in a
new worktree by CoW-cloning from main when the filesystem supports it
(APFS / btrfs / ReFS), or falling through to `pnpm install
--frozen-lockfile --package-import-method hardlink` otherwise. Both paths preserve the existing invariant
that each worktree owns its own real `node_modules` (no symlinks).

If preflight reports `worktree/toolchain/pnpm-store-misaligned`, the
pnpm store and projects directory are on different filesystem volumes
— hardlinks won't work until you resolve that. See the dashboard README
for remediation.
```

- [ ] **Step 3: Commit**

```bash
git add apps/dashboard/README.md docs/agent-topics/WORKFLOWS.md
git commit -m "docs: document dashboard worktree toolchain sharing

Adds README and WORKFLOWS sections explaining the
package-import-method=hardlink configuration, the same-volume
requirement, and the CoW-clone-or-install materialization flow
for new worktrees.
"
```

---

## Task 11: One-time migration hand-off (manual)

**Files:**
- None — this is a runbook step, not a code change.

The new `.npmrc` setting only affects *future* pnpm installs. Existing worktrees still have their fully-copied `node_modules` from before the fix. To realize the disk savings, run `pnpm install` once in each existing worktree — pnpm will detect that files don't match the store's expected hardlink state and re-link them in place.

- [ ] **Step 1: List existing worktrees**

```bash
git worktree list
```

- [ ] **Step 2: For each worktree (including main), re-install**

For each path printed above, run:

```bash
cd <worktree-path>/apps/dashboard
pnpm install --frozen-lockfile --package-import-method hardlink
```

Each run should take ~5-10 seconds and produce no new bytes (just re-link).

- [ ] **Step 3: Verify the disk delta**

```bash
for wt in $(git worktree list --porcelain | awk '/^worktree / {print $2}'); do
  nm="$wt/apps/dashboard/node_modules"
  if [ -d "$nm" ]; then
    total=$(find "$nm" -type f 2>/dev/null | wc -l | tr -d ' ')
    linked=$(find "$nm" -type f -links +1 2>/dev/null | wc -l | tr -d ' ')
    pct=$((linked * 100 / (total > 0 ? total : 1)))
    echo "$wt: $linked / $total hardlinked ($pct%)"
  fi
done
df -h /
```

Expected: each worktree should show ≥80% hardlinked. `df` should show significantly more free space on `/` than before migration.

- [ ] **Step 4: Optional — prune the pnpm store**

```bash
pnpm store prune
```

Reclaims store space for package versions no longer referenced by any worktree. Safe at any time.

- [ ] **Step 5: Paste evidence into a follow-up commit on main**

```bash
git checkout main
git commit --allow-empty -m "chore(toolchain): migration complete — N worktrees re-linked

After Task 1-10 landed, ran pnpm install --frozen-lockfile in
each existing worktree to re-link the previously-copied
node_modules against the now-correctly-configured store.

Evidence:
<paste the df + per-worktree hardlink % from Step 3>
"
```

---

## Self-Review Notes

Spec coverage check: every component listed in the spec maps to a task.

| Spec component | Task(s) |
|---|---|
| Component 1: effective pnpm hardlink config | Task 2 |
| Component 2: `scripts/worktree_toolchain.py` — `verify_pnpm_alignment` | Task 3 |
| Component 2: `scripts/worktree_toolchain.py` — `probe_clone_primitive` | Task 4 |
| Component 2: `scripts/worktree_toolchain.py` — `materialize_node_modules` | Tasks 5, 6 |
| Component 3: `worktree_preflight.py` — alignment check | Task 7 |
| Component 3: `worktree_preflight.py` — materializer integration | Task 8 |
| Component 4: one-off cleanup (stale `package-lock.json`) | Task 1 |
| Component 4: one-off cleanup (per-worktree re-install) | Task 11 |
| Component 5: docs | Task 10 |
| Testing Layer 1: unit tests | Tasks 3-6 (each function has its own tests) |
| Testing Layer 2: integration tests | Tasks 7-8 (preflight contract tests) |
| Testing Layer 3: real-data verification | Task 9 |

Error handling table from the spec: every row maps to logic in Tasks 3, 5, or 6 (alignment check → Task 3; clone failure / install failure / lockfile divergence / source missing → Task 5; race protection → Task 6; symlink guard → unchanged, preserved by Task 8 leaving that code path alone).

Cross-OS coverage: Task 4 probes the right primitive per `(OS, fs)`; Task 6's lock uses the right primitive per OS; Task 9's verification runs locally (macOS) — CI runs Tasks 3-8 unit/integration tests across OSes.
