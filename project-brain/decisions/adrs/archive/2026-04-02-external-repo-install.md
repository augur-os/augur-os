# External Repo Install & Update Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend install-skill to handle community repos with native installers (install.sh), track versions via registry, support `/import update`, and show "External" badges in browse.

**Architecture:** Wrap the repo's own install.sh — temp clone, security scan, run installer, snapshot before/after to detect installed skills, record in extended registry. Update flow re-clones and re-runs. Nightly GitHub API check for update detection. Browse page reads registry for badges.

**Tech Stack:** Python (MCP tools via FastMCP, registry YAML), TypeScript/React (BrowseCard badge), GitHub REST API.

**Spec:** `docs/superpowers/specs/2026-04-02-external-repo-install-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `skills/import/augur/lib/installer_detector.py` | Create | Detect install.sh/Makefile in a repo directory |
| `skills/import/augur/lib/repo_installer.py` | Create | Clone, snapshot, run installer, diff, cleanup |
| `skills/import/augur/tests/test_installer_detector.py` | Create | Tests for installer detection |
| `skills/import/augur/tests/test_repo_installer.py` | Create | Tests for install + snapshot logic |
| `skills/import/scripts/mcp/_registry.py` | Modify | Add new fields to add_entry, add update_repo_entry helper |
| `skills/import/scripts/mcp/tools_install.py` | Modify | Extend install-skill for script-based repos, add update-repo tool |
| `skills/import/augur/lib/update_checker.py` | Create | GitHub API update check per registry entry |
| `apps/dashboard/components/shared/BrowseCard.tsx` | Modify | Add "External" badge for registry-tracked skills |

---

### Task 1: Installer Detector Module

**Files:**
- Create: `skills/import/augur/lib/installer_detector.py`
- Create: `skills/import/augur/tests/test_installer_detector.py`

- [ ] **Step 1: Write failing tests**

```python
# skills/import/augur/tests/test_installer_detector.py
import pytest
from pathlib import Path
from installer_detector import detect_installer


def test_detects_install_sh(tmp_path):
    """Finds install.sh at repo root."""
    (tmp_path / "install.sh").write_text("#!/bin/bash\necho hello")
    result = detect_installer(tmp_path)
    assert result is not None
    assert result["type"] == "shell"
    assert result["path"] == "install.sh"


def test_detects_platform_installer(tmp_path):
    """Prefers install-mac.sh on darwin."""
    (tmp_path / "install.sh").write_text("#!/bin/bash")
    (tmp_path / "install-mac.sh").write_text("#!/bin/bash")
    result = detect_installer(tmp_path, platform="darwin")
    assert result["path"] == "install-mac.sh"


def test_detects_makefile_install(tmp_path):
    """Falls back to Makefile with install target."""
    makefile = tmp_path / "Makefile"
    makefile.write_text("install:\n\tcp files somewhere\n\ntest:\n\techo test")
    result = detect_installer(tmp_path)
    assert result is not None
    assert result["type"] == "make"
    assert result["path"] == "Makefile"


def test_returns_none_when_no_installer(tmp_path):
    """Returns None when no installer found."""
    (tmp_path / "README.md").write_text("# Just a readme")
    result = detect_installer(tmp_path)
    assert result is None


def test_ignores_makefile_without_install_target(tmp_path):
    """Makefile without install target is not an installer."""
    (tmp_path / "Makefile").write_text("build:\n\tgcc main.c\n\ntest:\n\techo test")
    result = detect_installer(tmp_path)
    assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Projects/Augur && python -m pytest skills/import/augur/tests/test_installer_detector.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement installer detector**

```python
# skills/import/augur/lib/installer_detector.py
"""Detect native installers in external skill repos."""

from __future__ import annotations

import platform as _platform
import re
from pathlib import Path
from typing import Any


# Platform-specific installer names, checked before generic ones
_PLATFORM_INSTALLERS: dict[str, list[str]] = {
    "darwin": ["install-mac.sh", "install-macos.sh"],
    "linux": ["install-linux.sh"],
    "win32": ["install-win.sh", "install.bat", "install-win.bat"],
}

_GENERIC_INSTALLERS = ["install.sh"]


def detect_installer(
    repo_dir: Path,
    platform: str | None = None,
) -> dict[str, Any] | None:
    """Detect the best installer in a repo directory.

    Args:
        repo_dir: path to the cloned repo root.
        platform: override platform detection (default: sys.platform).

    Returns:
        dict with 'type' ('shell'|'make'), 'path' (relative to repo_dir),
        and 'command' (list of args to execute), or None if no installer found.
    """
    plat = platform or _platform.system().lower()
    if plat == "darwin" or plat.startswith("mac"):
        plat = "darwin"
    elif plat.startswith("win"):
        plat = "win32"
    else:
        plat = "linux"

    # Check platform-specific installers first
    for name in _PLATFORM_INSTALLERS.get(plat, []):
        candidate = repo_dir / name
        if candidate.is_file():
            return {"type": "shell", "path": name, "command": ["bash", str(candidate)]}

    # Check generic installers
    for name in _GENERIC_INSTALLERS:
        candidate = repo_dir / name
        if candidate.is_file():
            return {"type": "shell", "path": name, "command": ["bash", str(candidate)]}

    # Check Makefile with install target
    makefile = repo_dir / "Makefile"
    if makefile.is_file():
        content = makefile.read_text(errors="replace")
        if re.search(r"^install\s*:", content, re.MULTILINE):
            return {"type": "make", "path": "Makefile", "command": ["make", "-C", str(repo_dir), "install"]}

    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Projects/Augur && python -m pytest skills/import/augur/tests/test_installer_detector.py -v`
Expected: All 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add skills/import/augur/lib/installer_detector.py skills/import/augur/tests/test_installer_detector.py
git commit -m "feat(import): add installer detector for external skill repos"
```

---

### Task 2: Repo Installer Module (Clone, Snapshot, Run, Diff)

**Files:**
- Create: `skills/import/augur/lib/repo_installer.py`
- Create: `skills/import/augur/tests/test_repo_installer.py`

- [ ] **Step 1: Write failing tests**

```python
# skills/import/augur/tests/test_repo_installer.py
import pytest
from pathlib import Path
from repo_installer import snapshot_skills_dir, diff_snapshots, run_installer


def test_snapshot_captures_dir_names(tmp_path):
    """Snapshot returns set of directory names."""
    (tmp_path / "skill-a").mkdir()
    (tmp_path / "skill-b").mkdir()
    (tmp_path / "not-a-dir.txt").write_text("file")
    result = snapshot_skills_dir(tmp_path)
    assert result == {"skill-a", "skill-b"}


def test_snapshot_empty_dir(tmp_path):
    """Snapshot of empty dir returns empty set."""
    result = snapshot_skills_dir(tmp_path)
    assert result == set()


def test_snapshot_missing_dir():
    """Snapshot of non-existent dir returns empty set."""
    result = snapshot_skills_dir(Path("/nonexistent/path"))
    assert result == set()


def test_diff_snapshots_detects_new():
    """Diff finds new skills added between snapshots."""
    before = {"skill-a", "skill-b"}
    after = {"skill-a", "skill-b", "skill-c", "skill-d"}
    result = diff_snapshots(before, after)
    assert result == {"skill-c", "skill-d"}


def test_diff_snapshots_no_change():
    """Diff returns empty when nothing changed."""
    before = {"skill-a"}
    after = {"skill-a"}
    result = diff_snapshots(before, after)
    assert result == set()


def test_run_installer_executes_script(tmp_path):
    """run_installer executes the command and returns success."""
    script = tmp_path / "install.sh"
    script.write_text("#!/bin/bash\nmkdir -p /tmp/test-installer-output")
    script.chmod(0o755)
    installer = {"type": "shell", "path": "install.sh", "command": ["bash", str(script)]}
    result = run_installer(installer, cwd=tmp_path)
    assert result["success"] is True
    assert result["return_code"] == 0
    # Cleanup
    import shutil
    shutil.rmtree("/tmp/test-installer-output", ignore_errors=True)


def test_run_installer_captures_failure(tmp_path):
    """run_installer captures non-zero exit code."""
    script = tmp_path / "install.sh"
    script.write_text("#!/bin/bash\nexit 1")
    script.chmod(0o755)
    installer = {"type": "shell", "path": "install.sh", "command": ["bash", str(script)]}
    result = run_installer(installer, cwd=tmp_path)
    assert result["success"] is False
    assert result["return_code"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Projects/Augur && python -m pytest skills/import/augur/tests/test_repo_installer.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement repo installer**

```python
# skills/import/augur/lib/repo_installer.py
"""Clone, snapshot, run installer, diff for external skill repos."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any


def snapshot_skills_dir(skills_dir: Path) -> set[str]:
    """Capture the set of directory names in a skills directory.

    Args:
        skills_dir: path to scan (e.g., ~/.claude/skills/).

    Returns:
        set of directory names found.
    """
    if not skills_dir.is_dir():
        return set()
    return {d.name for d in skills_dir.iterdir() if d.is_dir() and not d.name.startswith(".")}


def diff_snapshots(before: set[str], after: set[str]) -> set[str]:
    """Find new directories added between two snapshots.

    Returns:
        set of directory names that are in after but not in before.
    """
    return after - before


def run_installer(
    installer: dict[str, Any],
    cwd: Path,
    timeout: int = 120,
) -> dict[str, Any]:
    """Execute an installer script and capture the result.

    Args:
        installer: dict from detect_installer with 'command' key.
        cwd: working directory to run the installer in.
        timeout: max seconds to wait for the installer.

    Returns:
        dict with 'success', 'return_code', 'stdout', 'stderr'.
    """
    try:
        proc = subprocess.run(
            installer["command"],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=_build_env(),
        )
        return {
            "success": proc.returncode == 0,
            "return_code": proc.returncode,
            "stdout": proc.stdout[-2000:] if proc.stdout else "",
            "stderr": proc.stderr[-2000:] if proc.stderr else "",
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "return_code": -1, "stdout": "", "stderr": f"Installer timed out after {timeout}s"}
    except Exception as e:
        return {"success": False, "return_code": -1, "stdout": "", "stderr": str(e)}


def _build_env() -> dict[str, str]:
    """Build environment for installer execution — non-interactive."""
    import os
    env = os.environ.copy()
    env["NONINTERACTIVE"] = "1"
    env["CI"] = "true"  # Many installers skip prompts when CI=true
    return env
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Projects/Augur && python -m pytest skills/import/augur/tests/test_repo_installer.py -v`
Expected: All 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add skills/import/augur/lib/repo_installer.py skills/import/augur/tests/test_repo_installer.py
git commit -m "feat(import): add repo installer with snapshot/diff for skill detection"
```

---

### Task 3: Extend Registry Schema + install-skill for Script-Based Repos

**Files:**
- Modify: `skills/import/scripts/mcp/_registry.py`
- Modify: `skills/import/scripts/mcp/tools_install.py`

- [ ] **Step 1: Read the current registry and install-skill code**

Read: `skills/import/scripts/mcp/_registry.py` (full file)
Read: `skills/import/scripts/mcp/tools_install.py:253-335` (execute path)

- [ ] **Step 2: Extend add_entry with new fields**

In `_registry.py`, modify `add_entry` (around line 62) to accept and store new optional fields. Add these parameters to the function signature:

```python
def add_entry(
    data_dir: Path,
    title: str,
    source_url: str,
    source_type: str,
    category: str,
    target_bundle: str,
    target_skill: str,
    install_type: str = "enhance",
    # --- New optional fields for external repos ---
    installed_commit: str = "",
    install_method: str = "copy",
    installer_path: str = "",
    skills: list[str] | None = None,
    install_location: str = "",
) -> dict[str, Any]:
```

And add them to the entry dict:

```python
entry = {
    # ... existing fields ...
    "installed_commit": installed_commit,
    "install_method": install_method,
    "installer_path": installer_path,
    "skills": skills or [],
    "install_location": install_location,
    "latest_upstream_commit": None,
    "update_available": False,
}
```

- [ ] **Step 3: Add update_repo_entry helper to _registry.py**

After `update_entry_status`, add:

```python
def update_repo_entry(
    data_dir: Path,
    entry_id: str,
    installed_commit: str = "",
    latest_upstream_commit: str | None = None,
    update_available: bool | None = None,
) -> bool:
    """Update repo-specific fields on a registry entry."""
    registry = _read_registry(data_dir)
    for entry in registry.get("entries", []):
        if entry.get("id") == entry_id:
            if installed_commit:
                entry["installed_commit"] = installed_commit
                entry["install_metadata"] = entry.get("install_metadata", {})
                entry["install_metadata"]["installed_at"] = (
                    datetime.now(timezone.utc).isoformat()
                )
            if latest_upstream_commit is not None:
                entry["latest_upstream_commit"] = latest_upstream_commit
            if update_available is not None:
                entry["update_available"] = update_available
            _write_registry(data_dir, registry)
            return True
    return False
```

- [ ] **Step 4: Extend install-skill to handle repos with install.sh**

In `tools_install.py`, after the existing `execute=True` block (around line 335), add a new code path that handles script-based installation. This goes inside the `if execute:` block, before the existing `execute_install()` call:

```python
# --- Script-based install (external repos with install.sh) ---
augur_lib_dir = str(IMPORT_SKILL_ROOT / "augur" / "lib")
if augur_lib_dir not in sys.path:
    sys.path.insert(0, augur_lib_dir)

from installer_detector import detect_installer
from repo_installer import snapshot_skills_dir, diff_snapshots, run_installer

installer = detect_installer(Path(temp_clone_dir)) if temp_clone_dir else None

if installer:
    # Snapshot before install
    client_skills_dir = Path.home() / ".claude" / "skills"
    before = snapshot_skills_dir(client_skills_dir)

    # Run the repo's native installer
    install_result = run_installer(installer, cwd=Path(temp_clone_dir))

    if not install_result["success"]:
        update_entry_status(data_dir, entry["id"], "failed", error=install_result["stderr"])
        return json.dumps({
            "status": "error",
            "message": f"Installer failed (exit {install_result['return_code']})",
            "stderr": install_result["stderr"],
        })

    # Snapshot after install — detect which skills were added
    after = snapshot_skills_dir(client_skills_dir)
    new_skills = sorted(diff_snapshots(before, after))

    # Get commit hash from the temp clone
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=temp_clone_dir, capture_output=True, text=True
        ).stdout.strip()
    except Exception:
        commit = ""

    # Update registry with full metadata
    entry["installed_commit"] = commit
    entry["install_method"] = "script"
    entry["installer_path"] = installer["path"]
    entry["skills"] = new_skills
    entry["install_location"] = str(client_skills_dir)
    update_entry_status(data_dir, entry["id"], "installed", files_created=new_skills)

    trigger_rag_reindex()
    return json.dumps({
        "status": "installed",
        "method": "script",
        "installer": installer["path"],
        "skills_installed": new_skills,
        "commit": commit,
        "message": f"Installed {len(new_skills)} skills via {installer['path']}",
    })
```

Note: This requires the install-skill to temp-clone the repo when `execute=True` and `source_type == "github"`. Read the existing code to see how the temp clone is managed (it may already clone for the `execute_install` path). If not, add a temp clone step before this block.

- [ ] **Step 5: Run existing tests to verify nothing broke**

Run: `cd ~/Projects/Augur && python -m pytest skills/import/augur/tests/ -v`
Expected: All existing tests PASS.

- [ ] **Step 6: Commit**

```bash
git add skills/import/scripts/mcp/_registry.py skills/import/scripts/mcp/tools_install.py
git commit -m "feat(import): extend install-skill for repos with native installers"
```

---

### Task 4: Update Repo MCP Tool

**Files:**
- Modify: `skills/import/scripts/mcp/tools_install.py` — add `update-repo` tool
- Create: `skills/import/augur/lib/update_checker.py`
- Create: `skills/import/augur/tests/test_update_checker.py`

- [ ] **Step 1: Write failing test for update checker**

```python
# skills/import/augur/tests/test_update_checker.py
import pytest
from update_checker import check_github_update


def test_detects_update_available(monkeypatch):
    """Returns update_available=True when commits differ."""
    def mock_fetch_latest_commit(owner, repo, branch):
        return "newcommit123"

    monkeypatch.setattr("update_checker._fetch_latest_commit", mock_fetch_latest_commit)
    result = check_github_update(
        source_url="https://github.com/user/repo",
        installed_commit="oldcommit456",
    )
    assert result["update_available"] is True
    assert result["latest_commit"] == "newcommit123"


def test_no_update_when_same_commit(monkeypatch):
    """Returns update_available=False when commits match."""
    def mock_fetch_latest_commit(owner, repo, branch):
        return "samecommit"

    monkeypatch.setattr("update_checker._fetch_latest_commit", mock_fetch_latest_commit)
    result = check_github_update(
        source_url="https://github.com/user/repo",
        installed_commit="samecommit",
    )
    assert result["update_available"] is False


def test_handles_non_github_url():
    """Returns unknown for non-GitHub URLs."""
    result = check_github_update(
        source_url="https://gitlab.com/user/repo",
        installed_commit="abc",
    )
    assert result["update_available"] is False
    assert result["error"] == "Not a GitHub URL"


def test_parses_github_url_correctly(monkeypatch):
    """Extracts owner/repo from various GitHub URL formats."""
    captured = {}
    def mock_fetch(owner, repo, branch):
        captured["owner"] = owner
        captured["repo"] = repo
        return "abc"

    monkeypatch.setattr("update_checker._fetch_latest_commit", mock_fetch)
    check_github_update("https://github.com/zubair-trabzada/geo-seo-claude", "old")
    assert captured["owner"] == "zubair-trabzada"
    assert captured["repo"] == "geo-seo-claude"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Projects/Augur && python -m pytest skills/import/augur/tests/test_update_checker.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement update checker**

```python
# skills/import/augur/lib/update_checker.py
"""Check GitHub repos for updates against installed commit."""

from __future__ import annotations

import json
import re
import urllib.request
from typing import Any


def _fetch_latest_commit(owner: str, repo: str, branch: str = "main") -> str:
    """Fetch the latest commit SHA from GitHub API."""
    url = f"https://api.github.com/repos/{owner}/{repo}/commits/{branch}"
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github.v3+json",
    })
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read())
        return data["sha"]


def _fetch_changelog(owner: str, repo: str, base: str, head: str = "main") -> list[dict[str, str]]:
    """Fetch commit messages between base and head."""
    url = f"https://api.github.com/repos/{owner}/{repo}/compare/{base}...{head}"
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github.v3+json",
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            return [
                {"sha": c["sha"][:7], "message": c["commit"]["message"].split("\n")[0]}
                for c in data.get("commits", [])[:20]
            ]
    except Exception:
        return []


def check_github_update(
    source_url: str,
    installed_commit: str,
    branch: str = "main",
) -> dict[str, Any]:
    """Check if a GitHub repo has updates since the installed commit.

    Returns:
        dict with 'update_available', 'latest_commit', 'changelog', 'error'.
    """
    match = re.match(r"https://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$", source_url)
    if not match:
        return {"update_available": False, "latest_commit": "", "changelog": [], "error": "Not a GitHub URL"}

    owner, repo = match.group(1), match.group(2)
    try:
        latest = _fetch_latest_commit(owner, repo, branch)
        if latest == installed_commit or latest.startswith(installed_commit) or installed_commit.startswith(latest):
            return {"update_available": False, "latest_commit": latest, "changelog": [], "error": None}

        changelog = _fetch_changelog(owner, repo, installed_commit)
        return {
            "update_available": True,
            "latest_commit": latest,
            "changelog": changelog,
            "error": None,
        }
    except Exception as e:
        return {"update_available": False, "latest_commit": "", "changelog": [], "error": str(e)}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Projects/Augur && python -m pytest skills/import/augur/tests/test_update_checker.py -v`
Expected: All 4 tests PASS.

- [ ] **Step 5: Register the update-repo MCP tool**

In `tools_install.py`, at the end of `register_install_tools` (after the `uninstall-skill` tool), add:

```python
@mcp.tool(
    name="update-repo",
    annotations=tool_annotations(
        {
            "title": "Update External Repo",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": True,
        }
    ),
)
@mcp_tool_interceptor
async def update_repo_tool(
    name: str = "",
    source_url: str = "",
    check_only: bool = False,
) -> str:
    """Update an installed external repo skill or check for updates.

    Args:
        name: Registry entry name to update
        source_url: Alternative lookup by source URL
        check_only: If True, just check for updates without installing

    Returns:
        str: JSON with update status and changelog
    """
    metrics.track_tool("update_repo", skill="import")
    import sys
    augur_lib_dir = str(IMPORT_SKILL_ROOT / "augur" / "lib")
    if augur_lib_dir not in sys.path:
        sys.path.insert(0, augur_lib_dir)

    from update_checker import check_github_update

    # Find the registry entry
    registry = read_registry(get_data_dir())
    entry = None
    for e in registry.get("entries", []):
        if (name and e.get("title", "").lower() == name.lower()) or \
           (name and e.get("id", "").lower() == name.lower()) or \
           (source_url and e.get("source_url") == source_url):
            entry = e
            break

    if not entry:
        return json.dumps({"status": "error", "message": f"No registry entry found for '{name or source_url}'"})

    installed_commit = entry.get("installed_commit", "")
    if not installed_commit:
        return json.dumps({"status": "error", "message": "No installed_commit recorded — cannot check for updates"})

    # Check for updates
    update_info = check_github_update(entry["source_url"], installed_commit)

    if check_only or not update_info["update_available"]:
        # Update the registry with latest check result
        from _registry import update_repo_entry
        update_repo_entry(
            get_data_dir(), entry["id"],
            latest_upstream_commit=update_info.get("latest_commit", ""),
            update_available=update_info["update_available"],
        )
        return json.dumps({
            "status": "up_to_date" if not update_info["update_available"] else "update_available",
            "name": entry.get("title", ""),
            "installed_commit": installed_commit[:7],
            "latest_commit": update_info.get("latest_commit", "")[:7],
            "changelog": update_info.get("changelog", []),
            "message": "Already up to date" if not update_info["update_available"]
                       else f"{len(update_info.get('changelog', []))} new commits available",
        })

    # Execute update: temp clone + re-run installer
    import tempfile
    import shutil
    import subprocess as _sp

    temp_dir = tempfile.mkdtemp(prefix="augur-update-")
    try:
        # Clone latest
        clone_result = _sp.run(
            ["git", "clone", "--depth", "50", entry["source_url"], temp_dir + "/repo"],
            capture_output=True, text=True, timeout=60,
        )
        if clone_result.returncode != 0:
            return json.dumps({"status": "error", "message": f"Clone failed: {clone_result.stderr}"})

        clone_dir = temp_dir + "/repo"

        # Detect and run installer
        from installer_detector import detect_installer
        from repo_installer import snapshot_skills_dir, diff_snapshots, run_installer
        from pathlib import Path

        installer = detect_installer(Path(clone_dir))
        if not installer:
            return json.dumps({"status": "error", "message": "No installer found in repo"})

        client_skills_dir = Path.home() / ".claude" / "skills"
        before = snapshot_skills_dir(client_skills_dir)

        install_result = run_installer(installer, cwd=Path(clone_dir))
        if not install_result["success"]:
            return json.dumps({"status": "error", "message": f"Installer failed: {install_result['stderr']}"})

        after = snapshot_skills_dir(client_skills_dir)
        new_skills = sorted(diff_snapshots(before, after))

        # Get new commit
        new_commit = _sp.run(
            ["git", "rev-parse", "HEAD"], cwd=clone_dir,
            capture_output=True, text=True
        ).stdout.strip()

        # Update registry
        from _registry import update_repo_entry, update_entry_status
        update_repo_entry(get_data_dir(), entry["id"], installed_commit=new_commit, update_available=False)
        if new_skills:
            entry_meta = entry.get("install_metadata", {})
            existing_skills = entry.get("skills", entry_meta.get("skills", []))
            all_skills = sorted(set(existing_skills) | set(new_skills))
            # Update skills list in registry entry directly
            for e in read_registry(get_data_dir()).get("entries", []):
                if e.get("id") == entry["id"]:
                    e["skills"] = all_skills
                    break

        from _shared import trigger_rag_reindex
        trigger_rag_reindex()

        return json.dumps({
            "status": "updated",
            "name": entry.get("title", ""),
            "old_commit": installed_commit[:7],
            "new_commit": new_commit[:7],
            "changelog": update_info.get("changelog", []),
            "new_skills": new_skills,
            "message": f"Updated to {new_commit[:7]} ({len(update_info.get('changelog', []))} commits)",
        })
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
```

- [ ] **Step 6: Run all tests**

Run: `cd ~/Projects/Augur && python -m pytest skills/import/augur/tests/ -v`
Expected: All tests PASS.

- [ ] **Step 7: Commit**

```bash
git add skills/import/augur/lib/update_checker.py skills/import/augur/tests/test_update_checker.py skills/import/scripts/mcp/tools_install.py skills/import/scripts/mcp/_registry.py
git commit -m "feat(import): add update-repo MCP tool with GitHub changelog detection"
```

---

### Task 5: Browse Page "External" Badge

**Files:**
- Modify: `apps/dashboard/components/shared/BrowseCard.tsx:205-210`

- [ ] **Step 1: Read the current BrowseCard badge section**

Read: `apps/dashboard/components/shared/BrowseCard.tsx:200-215`

- [ ] **Step 2: Add External badge after masterClient badge**

After the masterClient badge block (around line 210), add:

```typescript
// External repo badge — skills from community repos tracked in registry
if (m?.source === 'external' || m?.installMethod === 'script') {
  badges.push({
    key: 'external',
    node: (
      <span className="inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium bg-[var(--accent-primary)]/10 text-[var(--accent-primary)] border-[var(--accent-primary)]/20">
        External
      </span>
    ),
  });
}
```

Note: The `m` variable is `item.metadata` — check the BrowseItem type to confirm the field names. The registry data needs to be surfaced through the browse-index enrichment cache. Read `src/mcp/augur_mcp/infrastructure/browse/index.py` to understand how enrichment data is merged into browse items — the `external` flag should come from matching skill names against registry entries during enrichment.

If enrichment doesn't currently check the install registry, this may require a small addition to the enrichment cache builder to cross-reference `registry.yaml`. Read the enrichment code first and determine the minimal change.

- [ ] **Step 3: Verify compilation**

Run: `cd ~/Projects/Augur/apps/dashboard && npx tsc --noEmit 2>&1 | grep BrowseCard | head -5`
Expected: No type errors.

- [ ] **Step 4: Commit**

```bash
git add apps/dashboard/components/shared/BrowseCard.tsx
git commit -m "feat(browse): add External badge for community repo skills"
```

---

### Task 6: End-to-End Test with geo-seo-claude

This is a manual verification task — not automated tests.

- [ ] **Step 1: Test the install flow**

Run the install-skill MCP tool against geo-seo-claude using a Python script:

```python
# Run from project root
python3 -c "
import sys, json
sys.path.insert(0, 'skills/import/augur/lib')
from installer_detector import detect_installer
from repo_installer import snapshot_skills_dir, diff_snapshots, run_installer
from pathlib import Path
import subprocess, tempfile, shutil

# 1. Temp clone
temp = tempfile.mkdtemp(prefix='augur-test-')
clone_dir = temp + '/repo'
subprocess.run(['git', 'clone', '--depth', '1', 'https://github.com/zubair-trabzada/geo-seo-claude', clone_dir], check=True)

# 2. Detect installer
installer = detect_installer(Path(clone_dir))
print(f'Installer: {installer}')

# 3. Snapshot before
client_dir = Path.home() / '.claude' / 'skills'
before = snapshot_skills_dir(client_dir)
print(f'Before: {len(before)} skills')

# 4. Run installer
result = run_installer(installer, cwd=Path(clone_dir))
print(f'Install result: success={result[\"success\"]}, rc={result[\"return_code\"]}')

# 5. Snapshot after
after = snapshot_skills_dir(client_dir)
new = diff_snapshots(before, after)
print(f'After: {len(after)} skills')
print(f'New skills: {sorted(new)}')

# 6. Get commit
commit = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=clone_dir, capture_output=True, text=True).stdout.strip()
print(f'Commit: {commit[:7]}')

# Cleanup
shutil.rmtree(temp)
"
```

Expected: installer detected as `install.sh`, skills installed to `~/.claude/skills/`, 15 new skill dirs detected.

- [ ] **Step 2: Test update check**

```python
python3 -c "
import sys
sys.path.insert(0, 'skills/import/augur/lib')
from update_checker import check_github_update
result = check_github_update('https://github.com/zubair-trabzada/geo-seo-claude', 'fake-old-commit')
print(f'Update available: {result[\"update_available\"]}')
print(f'Latest commit: {result[\"latest_commit\"][:7]}')
print(f'Changelog: {len(result[\"changelog\"])} commits')
for c in result['changelog'][:5]:
    print(f'  {c[\"sha\"]} {c[\"message\"][:60]}')
"
```

Expected: `update_available=True`, changelog with recent commits.

- [ ] **Step 3: Verify browse shows the skills**

After install, check that Augur's Tier 2 discovery finds the geo skills:

```bash
ls ~/.claude/skills/ | grep geo
```

Expected: `geo`, `geo-audit`, `geo-brand-mentions`, etc.

- [ ] **Step 4: Commit verification notes if needed**

```bash
git add -u && git commit -m "fix(import): address e2e test findings" 2>/dev/null || echo "No fixes needed"
```
