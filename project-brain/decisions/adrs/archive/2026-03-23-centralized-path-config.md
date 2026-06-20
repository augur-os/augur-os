# Centralized Path Config Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `project.yaml` the single source of truth for vault/documents paths, with self-discovery when paths go stale.

**Architecture:** `project.yaml` → `paths.py` reads it (cached) → all consumers use `paths.py` → `path_discovery.py` triggers on missing paths → prompts user or auto-uses discovered path.

**Tech Stack:** Python 3.11+, PyYAML, pathlib

**Spec:** `docs/superpowers/specs/2026-03-23-centralized-path-config-design.md`

---

## File Map

| File | Role | Action |
|------|------|--------|
| `project.yaml` | Single config file | Modify — add `paths:` block |
| `src/config/paths.py` | Central path resolver | Modify — add `get_project_paths()`, rewrite `_vault_home_dir()` / `_documents_home_dir()`, integrate discovery |
| `src/config/path_discovery.py` | Self-discovery engine | Create — marker scanning, fingerprinting, prompt, scan budget |
| `src/config/path_config.py` | Dashboard path config | Modify — remove YAML file dependency, build from `paths.py` |
| `src/config/path_config.yaml` | Old config file | Delete |
| `src/mcp/augur_mcp/config.py` | MCP standalone config | Modify — delegate vault/docs to `paths.py` |
| `src/mcp/augur_mcp/compat.py` | MCP compat layer | Modify — remove `get_config_path` export |
| `src/mcp/augur_mcp/infrastructure/paths.py` | MCP update-path tool | Modify — rewrite `save()` to update `project.yaml` |
| `src/lib/sync_discover.py` | Vault scanner | Modify — remove hardcoded fallback |
| `src/scripts/migrate_vault_flatten.py` | Migration script | Modify — remove hardcoded fallback |
| `skills/*/scripts/mcp/__init__.py` (~15 files) | Skill MCP modules | Modify — replace vault fallbacks |
| `skills/*/scripts/mcp/_shared.py`, `_helpers.py` (~5 files) | Skill helpers | Modify — replace vault fallbacks |
| `skills/daemon/scripts/schedule_executor.py` | Daemon scheduler | Modify — replace vault fallback |
| `~/.zshrc` | Shell config | Modify — remove `AUGUR_VAULT`, `AUGUR_DOCUMENTS` |
| `.claude/settings.json` | Claude Code hooks | Modify — update Stop hook |
| `tests/unit/test_path_resolution.py` | Unit tests for paths | Create |
| `tests/unit/test_path_discovery.py` | Unit tests for discovery | Create |

---

### Task 1: Add `paths:` block to `project.yaml`

**Files:**
- Modify: `project.yaml`

- [ ] **Step 1: Update project.yaml**

```yaml
name: Augur
port: 3000

paths:
  vault: ~/Projects/Au-vault
  documents: ~/Projects/Au-docs
```

- [ ] **Step 2: Commit**

```bash
git add project.yaml
git commit -m "feat: add paths block to project.yaml for centralized path config"
```

---

### Task 2: Add `get_project_paths()` to `paths.py` and rewrite resolution chain

**Files:**
- Modify: `src/config/paths.py`
- Test: `tests/unit/test_path_resolution.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_path_resolution.py`:

```python
"""Tests for project.yaml path resolution chain."""
import os
from pathlib import Path
from unittest.mock import patch
import pytest
from src.config import paths


@pytest.fixture(autouse=True)
def reset_caches():
    """Clear all path caches between tests."""
    paths.invalidate_project_cache()
    yield
    paths.invalidate_project_cache()


class TestGetProjectPaths:
    """Test get_project_paths() reads from project.yaml."""

    def test_reads_vault_path(self, tmp_path):
        project_yaml = tmp_path / "project.yaml"
        project_yaml.write_text("name: Test\npaths:\n  vault: /tmp/test-vault\n")
        with patch.object(paths, "get_project_root", return_value=tmp_path):
            result = paths.get_project_paths()
        assert result["vault"] == Path("/tmp/test-vault")

    def test_reads_documents_path(self, tmp_path):
        project_yaml = tmp_path / "project.yaml"
        project_yaml.write_text("name: Test\npaths:\n  documents: /tmp/test-docs\n")
        with patch.object(paths, "get_project_root", return_value=tmp_path):
            result = paths.get_project_paths()
        assert result["documents"] == Path("/tmp/test-docs")

    def test_expands_tilde(self, tmp_path):
        project_yaml = tmp_path / "project.yaml"
        project_yaml.write_text("name: Test\npaths:\n  vault: ~/my-vault\n")
        with patch.object(paths, "get_project_root", return_value=tmp_path):
            result = paths.get_project_paths()
        assert result["vault"] == Path.home() / "my-vault"

    def test_missing_paths_block_returns_empty(self, tmp_path):
        project_yaml = tmp_path / "project.yaml"
        project_yaml.write_text("name: Test\nport: 3000\n")
        with patch.object(paths, "get_project_root", return_value=tmp_path):
            result = paths.get_project_paths()
        assert result == {}

    def test_paths_not_dict_returns_empty(self, tmp_path):
        project_yaml = tmp_path / "project.yaml"
        project_yaml.write_text("name: Test\npaths: not-a-dict\n")
        with patch.object(paths, "get_project_root", return_value=tmp_path):
            result = paths.get_project_paths()
        assert result == {}

    def test_unknown_keys_ignored(self, tmp_path):
        project_yaml = tmp_path / "project.yaml"
        project_yaml.write_text("name: Test\npaths:\n  vault: /tmp/v\n  bogus: /tmp/x\n")
        with patch.object(paths, "get_project_root", return_value=tmp_path):
            result = paths.get_project_paths()
        assert "vault" in result
        assert "bogus" not in result

    def test_caching(self, tmp_path):
        project_yaml = tmp_path / "project.yaml"
        project_yaml.write_text("name: Test\npaths:\n  vault: /tmp/v1\n")
        with patch.object(paths, "get_project_root", return_value=tmp_path):
            r1 = paths.get_project_paths()
            project_yaml.write_text("name: Test\npaths:\n  vault: /tmp/v2\n")
            r2 = paths.get_project_paths()
        assert r1["vault"] == r2["vault"]  # cached, not re-read

    def test_cache_invalidation(self, tmp_path):
        project_yaml = tmp_path / "project.yaml"
        project_yaml.write_text("name: Test\npaths:\n  vault: /tmp/v1\n")
        with patch.object(paths, "get_project_root", return_value=tmp_path):
            r1 = paths.get_project_paths()
            project_yaml.write_text("name: Test\npaths:\n  vault: /tmp/v2\n")
            paths.invalidate_project_cache()
            r2 = paths.get_project_paths()
        assert r1["vault"] != r2["vault"]


class TestResolutionOrder:
    """Test env var > project.yaml > hardcoded default."""

    def test_env_var_overrides_project_yaml(self, tmp_path):
        project_yaml = tmp_path / "project.yaml"
        project_yaml.write_text("name: Test\npaths:\n  vault: /tmp/from-yaml\n")
        with patch.object(paths, "get_project_root", return_value=tmp_path), \
             patch.dict(os.environ, {"AUGUR_VAULT": "/tmp/from-env"}):
            result = paths.get_vault_dir()
        assert result == Path("/tmp/from-env")

    def test_project_yaml_overrides_hardcoded(self, tmp_path):
        project_yaml = tmp_path / "project.yaml"
        project_yaml.write_text("name: Test\npaths:\n  vault: /tmp/from-yaml\n")
        with patch.object(paths, "get_project_root", return_value=tmp_path), \
             patch.dict(os.environ, {}, clear=False):
            os.environ.pop("AUGUR_VAULT", None)
            result = paths.get_vault_dir()
        assert result == Path("/tmp/from-yaml")

    def test_hardcoded_default_when_nothing_set(self, tmp_path):
        project_yaml = tmp_path / "project.yaml"
        project_yaml.write_text("name: Test\nport: 3000\n")
        with patch.object(paths, "get_project_root", return_value=tmp_path), \
             patch.dict(os.environ, {}, clear=False):
            os.environ.pop("AUGUR_VAULT", None)
            result = paths.get_vault_dir()
        # Falls through to path_primitives.vault_home_dir("Test")
        assert "Vault" in str(result) or "vault" in str(result)


class TestLegacyRollback:
    """Test AUGUR_PATH_LEGACY=1 skips project.yaml reading."""

    def test_legacy_flag_skips_project_yaml(self, tmp_path):
        project_yaml = tmp_path / "project.yaml"
        project_yaml.write_text("name: Test\npaths:\n  vault: /tmp/from-yaml\n")
        with patch.object(paths, "get_project_root", return_value=tmp_path), \
             patch.dict(os.environ, {"AUGUR_PATH_LEGACY": "1"}):
            os.environ.pop("AUGUR_VAULT", None)
            result = paths.get_vault_dir()
        # Should NOT be /tmp/from-yaml — should be hardcoded default
        assert result != Path("/tmp/from-yaml")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Projects/Augur && python -m pytest tests/unit/test_path_resolution.py -v`
Expected: FAIL — `get_project_paths`, `invalidate_project_cache` do not exist yet.

- [ ] **Step 3: Implement `get_project_paths()` and rewrite resolution chain**

In `src/config/paths.py`, add after the existing `_project_name_cache` block:

```python
_KNOWN_PATH_KEYS = {"vault", "documents"}

_project_paths_cache: dict[str, Path] | None = None


def get_project_paths() -> dict[str, Path]:
    """Read paths: block from project.yaml. Cached after first read.

    Resolution order for each path: env var > project.yaml > hardcoded default.
    Only returns paths explicitly set in project.yaml (vault, documents).
    """
    global _project_paths_cache
    if _project_paths_cache is not None:
        return _project_paths_cache

    if os.environ.get("AUGUR_PATH_LEGACY"):
        _project_paths_cache = {}
        return _project_paths_cache

    project_yaml = get_project_root() / "project.yaml"
    if not project_yaml.exists():
        _project_paths_cache = {}
        return _project_paths_cache

    try:
        data = _yaml_mod.safe_load(project_yaml.read_text(encoding="utf-8"))
    except Exception:
        _project_paths_cache = {}
        return _project_paths_cache

    paths_block = data.get("paths", {}) if isinstance(data, dict) else {}
    if not isinstance(paths_block, dict):
        _project_paths_cache = {}
        return _project_paths_cache

    result: dict[str, Path] = {}
    for key in _KNOWN_PATH_KEYS:
        value = paths_block.get(key)
        if value and isinstance(value, str):
            result[key] = Path(os.path.expanduser(value)).resolve()

    _project_paths_cache = result
    return _project_paths_cache
```

Rename `invalidate_project_name_cache` to `invalidate_project_cache` (no alias — rule 14):

```python
def invalidate_project_cache() -> None:
    """Clear all cached project config. Call when project.yaml changes."""
    global _project_name_cache, _project_port_cache, _project_paths_cache
    _project_name_cache = None
    _project_port_cache = None
    _project_paths_cache = None
```

Verify all callers and update:

Run: `cd ~/Projects/Augur && grep -rn "invalidate_project_name_cache" --include="*.py" | grep -v __pycache__`

Update every caller to use `invalidate_project_cache` (known: `tests/src/test_paths.py`).

Rewrite `_vault_home_dir()` and `_documents_home_dir()`:

```python
def _vault_home_dir() -> Path:
    env = _env_path("AUGUR_VAULT")
    if env:
        return env
    yaml_path = get_project_paths().get("vault")
    if yaml_path:
        return yaml_path
    return path_primitives.vault_home_dir(get_project_name())


def _documents_home_dir() -> Path:
    env = _env_path("AUGUR_DOCUMENTS")
    if env:
        return env
    yaml_path = get_project_paths().get("documents")
    if yaml_path:
        return yaml_path
    return path_primitives.documents_home_dir(get_project_name())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Projects/Augur && python -m pytest tests/unit/test_path_resolution.py -v`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add src/config/paths.py tests/unit/test_path_resolution.py
git commit -m "feat: add get_project_paths() and rewrite vault/docs resolution chain"
```

---

### Task 3: Create `path_discovery.py` — self-discovery engine

**Files:**
- Create: `src/config/path_discovery.py`
- Test: `tests/unit/test_path_discovery.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_path_discovery.py`:

```python
"""Tests for path self-discovery engine."""
import os
import time
from pathlib import Path
from unittest.mock import patch
import pytest
from src.config import path_discovery


@pytest.fixture(autouse=True)
def reset_discovery_cache():
    """Clear discovery cache between tests."""
    path_discovery._discovery_cache.clear()
    yield
    path_discovery._discovery_cache.clear()


class TestMarkerDiscovery:
    """Test scanning for .augur-vault / .augur-docs marker files."""

    def test_finds_vault_by_marker(self, tmp_path):
        vault = tmp_path / "my-vault"
        vault.mkdir()
        (vault / ".augur-vault").write_text("project: Test\ncreated: 2026-03-23\n")
        result = path_discovery.discover_path(
            "vault", configured=tmp_path / "wrong-path",
            search_roots=[tmp_path],
        )
        assert result == vault

    def test_finds_docs_by_marker(self, tmp_path):
        docs = tmp_path / "my-docs"
        docs.mkdir()
        (docs / ".augur-docs").write_text("project: Test\ncreated: 2026-03-23\n")
        result = path_discovery.discover_path(
            "documents", configured=tmp_path / "wrong-path",
            search_roots=[tmp_path],
        )
        assert result == docs

    def test_returns_none_when_no_marker(self, tmp_path):
        (tmp_path / "some-dir").mkdir()
        result = path_discovery.discover_path(
            "vault", configured=tmp_path / "wrong-path",
            search_roots=[tmp_path],
        )
        assert result is None


class TestFingerprintDiscovery:
    """Test structure-based vault detection."""

    def test_finds_vault_by_structure(self, tmp_path):
        vault = tmp_path / "actual-vault"
        vault.mkdir()
        (vault / "memory").mkdir()
        # Create 3 skill-named subdirs
        for name in ["career", "health", "finance"]:
            (vault / name).mkdir()
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        for name in ["career", "health", "finance", "other"]:
            (skills_dir / name).mkdir()
        result = path_discovery.discover_path(
            "vault", configured=tmp_path / "wrong-path",
            search_roots=[tmp_path],
            skills_dir=skills_dir,
        )
        assert result == vault

    def test_no_match_without_memory_dir(self, tmp_path):
        vault = tmp_path / "not-a-vault"
        vault.mkdir()
        for name in ["career", "health", "finance"]:
            (vault / name).mkdir()
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        for name in ["career", "health", "finance"]:
            (skills_dir / name).mkdir()
        result = path_discovery.discover_path(
            "vault", configured=tmp_path / "wrong-path",
            search_roots=[tmp_path],
            skills_dir=skills_dir,
        )
        assert result is None

    def test_fallback_fingerprint_without_skills_dir(self, tmp_path):
        vault = tmp_path / "vault"
        vault.mkdir()
        (vault / "memory").mkdir()
        (vault / "dev").mkdir()
        (vault / "config").mkdir()
        result = path_discovery.discover_path(
            "vault", configured=tmp_path / "wrong-path",
            search_roots=[tmp_path],
            skills_dir=tmp_path / "nonexistent-skills",
        )
        assert result == vault


class TestOneShotCache:
    """Test that discovery runs only once per session."""

    def test_cached_after_first_run(self, tmp_path):
        result1 = path_discovery.discover_path(
            "vault", configured=tmp_path / "wrong",
            search_roots=[tmp_path],
        )
        # Even if we add a marker now, it should not be found
        vault = tmp_path / "late-vault"
        vault.mkdir()
        (vault / ".augur-vault").write_text("project: Test\n")
        result2 = path_discovery.discover_path(
            "vault", configured=tmp_path / "wrong",
            search_roots=[tmp_path],
        )
        assert result1 == result2  # both None — cached


class TestScanBudget:
    """Test scan budget limits."""

    def test_stops_after_max_candidates(self, tmp_path):
        # Create 200 directories
        for i in range(200):
            (tmp_path / f"dir-{i:04d}").mkdir()
        # Put marker in last one
        (tmp_path / "dir-0199" / ".augur-vault").write_text("project: Test\n")
        result = path_discovery.discover_path(
            "vault", configured=tmp_path / "wrong",
            search_roots=[tmp_path],
            max_candidates=50,
        )
        # Should not find it — budget exhausted before reaching dir-0199
        assert result is None


class TestCreateMarker:
    """Test marker file creation."""

    def test_creates_vault_marker(self, tmp_path):
        path_discovery.create_marker("vault", tmp_path)
        marker = tmp_path / ".augur-vault"
        assert marker.exists()
        content = marker.read_text()
        assert "project:" in content

    def test_creates_docs_marker(self, tmp_path):
        path_discovery.create_marker("documents", tmp_path)
        marker = tmp_path / ".augur-docs"
        assert marker.exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Projects/Augur && python -m pytest tests/unit/test_path_discovery.py -v`
Expected: FAIL — `src.config.path_discovery` does not exist.

- [ ] **Step 3: Implement `path_discovery.py`**

Create `src/config/path_discovery.py`:

```python
"""Path self-discovery engine.

When a configured vault or documents path doesn't exist, this module
scans for marker files (.augur-vault, .augur-docs) and falls back to
structure fingerprinting.

Spec: docs/superpowers/specs/2026-03-23-centralized-path-config-design.md
"""

from __future__ import annotations

import logging
import os
import sys
import time
from datetime import date
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Marker file names per path type
_MARKERS = {
    "vault": ".augur-vault",
    "documents": ".augur-docs",
}

# One-shot cache: path_type -> discovered Path or None
_discovery_cache: dict[str, Optional[Path]] = {}

# Default scan budget
_DEFAULT_MAX_CANDIDATES = 100
_DEFAULT_TIMEOUT_SECS = 5.0


def _default_search_roots(configured: Path) -> list[Path]:
    """Build default scan locations from the configured (stale) path."""
    roots: list[Path] = []
    # 1. Sibling directories of configured path
    if configured.parent.exists():
        roots.append(configured.parent)
    # 2. Home direct children
    roots.append(Path.home())
    # 3. ~/Documents
    docs = Path.home() / "Documents"
    if docs.exists():
        roots.append(docs)
    # 4. ~/Desktop
    desktop = Path.home() / "Desktop"
    if desktop.exists():
        roots.append(desktop)
    return roots


def _is_vault_fingerprint(
    candidate: Path, skills_dir: Optional[Path] = None
) -> bool:
    """Check if a directory looks like a vault by structure."""
    if not (candidate / "memory").is_dir():
        return False
    if skills_dir and skills_dir.is_dir():
        try:
            skill_names = {d.name for d in skills_dir.iterdir() if d.is_dir()}
        except OSError:
            skill_names = set()
        if skill_names:
            matching = sum(
                1
                for d in candidate.iterdir()
                if d.is_dir() and d.name in skill_names
            )
            return matching >= 3
    # Fallback: require memory/ + dev/ + config/
    return (candidate / "dev").is_dir() and (candidate / "config").is_dir()


def _is_docs_fingerprint(
    candidate: Path, skills_dir: Optional[Path] = None
) -> bool:
    """Check if a directory looks like a documents root.

    Requires skill-named subdirs containing binary files.
    """
    if not candidate.is_dir():
        return False
    subdirs = [d for d in candidate.iterdir() if d.is_dir()]
    if len(subdirs) < 2:
        return False
    # Match subdirs against skill names if available
    if skills_dir and skills_dir.is_dir():
        try:
            skill_names = {d.name for d in skills_dir.iterdir() if d.is_dir()}
        except OSError:
            skill_names = set()
        if skill_names:
            subdirs = [d for d in subdirs if d.name in skill_names]
            if len(subdirs) < 2:
                return False
    # Check for binary files in matched subdirs
    for subdir in subdirs[:5]:
        for f in subdir.iterdir():
            if f.is_file() and f.suffix in {".pdf", ".docx", ".xlsx", ".pptx", ".zip"}:
                return True
    return False


def discover_path(
    path_type: str,
    configured: Path,
    search_roots: Optional[list[Path]] = None,
    skills_dir: Optional[Path] = None,
    max_candidates: int = _DEFAULT_MAX_CANDIDATES,
    timeout_secs: float = _DEFAULT_TIMEOUT_SECS,
) -> Optional[Path]:
    """Discover a moved vault or documents directory.

    Args:
        path_type: "vault" or "documents"
        configured: The configured path that doesn't exist
        search_roots: Directories to scan (default: auto from configured path)
        skills_dir: Skills directory for fingerprint matching
        max_candidates: Stop after this many candidates
        timeout_secs: Stop after this many seconds

    Returns:
        Discovered path, or None if not found. Cached per path_type.
    """
    if path_type in _discovery_cache:
        return _discovery_cache[path_type]

    marker_name = _MARKERS.get(path_type)
    if not marker_name:
        _discovery_cache[path_type] = None
        return None

    roots = search_roots or _default_search_roots(configured)
    fingerprint_fn = _is_vault_fingerprint if path_type == "vault" else _is_docs_fingerprint

    candidates_checked = 0
    start_time = time.monotonic()

    for root in roots:
        if not root.is_dir():
            continue
        try:
            children = sorted(root.iterdir())
        except OSError:
            continue
        for child in children:
            if not child.is_dir() or child.name.startswith("."):
                continue
            candidates_checked += 1
            if candidates_checked > max_candidates:
                logger.warning(
                    "Discovery budget exhausted (%d candidates) without finding %s",
                    max_candidates, path_type,
                )
                _discovery_cache[path_type] = None
                return None
            if time.monotonic() - start_time > timeout_secs:
                logger.warning(
                    "Discovery timeout (%.1fs) without finding %s",
                    timeout_secs, path_type,
                )
                _discovery_cache[path_type] = None
                return None

            # Check marker
            if (child / marker_name).is_file():
                logger.info(
                    "%s not found at %s. Found at %s (marker file).",
                    path_type, configured, child,
                )
                _discovery_cache[path_type] = child
                return child

            # Check fingerprint
            if fingerprint_fn(child, skills_dir=skills_dir):
                logger.info(
                    "%s not found at %s. Found at %s (structure match).",
                    path_type, configured, child,
                )
                _discovery_cache[path_type] = child
                return child

    _discovery_cache[path_type] = None
    return None


def prompt_update(path_type: str, old_path: Path, new_path: Path) -> bool:
    """Prompt the user to update project.yaml if running interactively.

    Returns True if the user confirmed (or non-interactive mode used the path).
    """
    if not sys.stdin.isatty():
        logger.warning(
            "%s config stale: configured %s, using discovered %s. "
            "Run 'augur config fix' to update project.yaml.",
            path_type, old_path, new_path,
        )
        return False

    print(f"\n{path_type.title()} not found at: {old_path}")
    print(f"Discovered at:  {new_path}")
    try:
        answer = input("Update project.yaml? (y/n): ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False
    return answer in ("y", "yes")


def update_project_yaml(key: str, new_path: Path) -> None:
    """Atomically update a single path in project.yaml."""
    import tempfile

    import yaml

    from src.config.paths import get_project_root, invalidate_project_cache

    project_yaml = get_project_root() / "project.yaml"
    data = yaml.safe_load(project_yaml.read_text(encoding="utf-8")) or {}
    if "paths" not in data or not isinstance(data["paths"], dict):
        data["paths"] = {}
    data["paths"][key] = str(new_path)

    tmp_fd, tmp_path = tempfile.mkstemp(
        dir=project_yaml.parent, suffix=".yaml"
    )
    try:
        with os.fdopen(tmp_fd, "w") as f:
            yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)
        os.replace(tmp_path, project_yaml)
    except BaseException:
        os.unlink(tmp_path)
        raise

    invalidate_project_cache()
    logger.info("Updated project.yaml: paths.%s = %s", key, new_path)


def create_marker(path_type: str, directory: Path) -> None:
    """Create a discovery marker file in the given directory."""
    marker_name = _MARKERS.get(path_type)
    if not marker_name:
        return
    marker = directory / marker_name
    if marker.exists():
        return
    try:
        from src.config.paths import get_project_name
        project_name = get_project_name()
    except ImportError:
        project_name = "Augur"
    marker.write_text(
        f"project: {project_name}\ncreated: {date.today().isoformat()}\n"
    )
    logger.info("Created %s marker at %s", path_type, marker)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Projects/Augur && python -m pytest tests/unit/test_path_discovery.py -v`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add src/config/path_discovery.py tests/unit/test_path_discovery.py
git commit -m "feat: add path self-discovery engine with marker files and fingerprinting"
```

---

### Task 4: Integrate discovery into `paths.py`

**Files:**
- Modify: `src/config/paths.py`
- Test: `tests/unit/test_path_resolution.py` (add discovery integration tests)

- [ ] **Step 1: Add discovery integration tests**

Append to `tests/unit/test_path_resolution.py`:

```python
class TestDiscoveryIntegration:
    """Test that get_vault_dir() triggers discovery when path is missing."""

    def test_discovery_triggers_on_missing_vault(self, tmp_path):
        # Set up: project.yaml points to non-existent dir
        project_yaml = tmp_path / "project.yaml"
        project_yaml.write_text("name: Test\npaths:\n  vault: /tmp/nonexistent-vault\n")
        # Create a discoverable vault with marker
        real_vault = tmp_path / "real-vault"
        real_vault.mkdir()
        (real_vault / ".augur-vault").write_text("project: Test\n")
        with patch.object(paths, "get_project_root", return_value=tmp_path), \
             patch.dict(os.environ, {}, clear=False), \
             patch("src.config.path_discovery._default_search_roots",
                   return_value=[tmp_path]), \
             patch("src.config.path_discovery.prompt_update", return_value=False):
            os.environ.pop("AUGUR_VAULT", None)
            from src.config import path_discovery
            path_discovery._discovery_cache.clear()
            result = paths.get_vault_dir()
        assert result == real_vault

    def test_no_discovery_when_path_exists(self, tmp_path):
        vault = tmp_path / "vault"
        vault.mkdir()
        project_yaml = tmp_path / "project.yaml"
        project_yaml.write_text(f"name: Test\npaths:\n  vault: {vault}\n")
        with patch.object(paths, "get_project_root", return_value=tmp_path), \
             patch.dict(os.environ, {}, clear=False):
            os.environ.pop("AUGUR_VAULT", None)
            result = paths.get_vault_dir()
        assert result == vault
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Projects/Augur && python -m pytest tests/unit/test_path_resolution.py::TestDiscoveryIntegration -v`
Expected: FAIL — discovery not yet wired into `get_vault_dir()`.

- [ ] **Step 3: Wire discovery into `get_vault_dir()` and `get_documents_dir()`**

In `src/config/paths.py`, modify `get_vault_dir()` and `get_documents_dir()`.

Discovery runs silently — no prompting. Prompting is only done by `augur config fix` (Task 10).
This avoids blocking callers (daemons, MCP servers) with unexpected `input()` calls.

```python
def get_vault_dir() -> Path:
    resolved = _vault_home_dir()
    if resolved.exists():
        return resolved
    # Trigger silent self-discovery
    try:
        from src.config.path_discovery import discover_path
        discovered = discover_path(
            "vault",
            configured=resolved,
            skills_dir=get_skills_dir(),
        )
        if discovered:
            import logging
            logging.getLogger(__name__).warning(
                "Vault not at configured %s, using discovered %s. "
                "Run 'augur config fix' to update project.yaml.",
                resolved, discovered,
            )
            return discovered
    except Exception:
        import logging
        logging.getLogger(__name__).debug("Discovery failed", exc_info=True)
    return resolved


def get_documents_dir() -> Path:
    resolved = _documents_home_dir()
    if resolved.exists():
        return resolved
    try:
        from src.config.path_discovery import discover_path
        discovered = discover_path(
            "documents",
            configured=resolved,
            skills_dir=get_skills_dir(),
        )
        if discovered:
            import logging
            logging.getLogger(__name__).warning(
                "Documents not at configured %s, using discovered %s. "
                "Run 'augur config fix' to update project.yaml.",
                resolved, discovered,
            )
            return discovered
    except Exception:
        import logging
        logging.getLogger(__name__).debug("Discovery failed", exc_info=True)
    return resolved
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Projects/Augur && python -m pytest tests/unit/test_path_resolution.py -v`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add src/config/paths.py tests/unit/test_path_resolution.py
git commit -m "feat: wire path discovery into get_vault_dir() and get_documents_dir()"
```

---

### Task 5: Rewrite `path_config.py`, update consumers, delete `path_config.yaml`

**Files:**
- Modify: `src/config/path_config.py`
- Modify: `src/mcp/augur_mcp/compat.py`
- Modify: `src/mcp/augur_mcp/infrastructure/paths.py`
- Delete: `src/config/path_config.yaml`

- [ ] **Step 1: Rewrite `PathConfig.from_yaml()`, `get_config_path()`, and `save()`**

In `src/config/path_config.py`:

Remove `from_yaml` classmethod. Remove `get_config_path()`.

Rewrite `load_path_config()`:

```python
def load_path_config() -> PathConfig:
    """Load path configuration from paths.py functions (project.yaml backed)."""
    config = PathConfig.defaults()
    config.refresh_sizes()
    config.refresh_gitignored()
    return config
```

Rewrite `PathConfig.save()` to update `project.yaml` instead of a separate YAML.
`self.data` is a `PathCategory` with `id="data"` and `path` = vault root. Documents
are in `self.data.subdirs[0]` (set by `PathConfig.defaults()`).

```python
def save(self, config_path: Path | None = None) -> None:
    """Save vault/documents paths back to project.yaml."""
    from src.config.path_discovery import update_project_yaml
    update_project_yaml("vault", self.data.path)
    # subdirs[0] is documents dir (set by defaults())
    if self.data.subdirs:
        update_project_yaml("documents", Path(self.data.subdirs[0]))
```

Drop `exclude_patterns` from the YAML — they stay as hardcoded defaults in `calculate_directory_size()` (which already has them).

- [ ] **Step 2: Update `src/mcp/augur_mcp/compat.py`**

Remove `get_config_path` from the tuple returned by `_try_import_path_config()`:

```python
# Before: return (_get_config, refresh_path_config, check_size_alerts, generate_recommendations, get_config_path)
# After:  return (_get_config, refresh_path_config, check_size_alerts, generate_recommendations)
```

Update all destructuring sites to drop `get_config_path`.

- [ ] **Step 3: Update all 3 tuple destructuring sites in `src/mcp/augur_mcp/infrastructure/paths.py`**

The compat function now returns 4 elements instead of 5. Update all unpack sites:

```python
# Line 87 — get-path-config tool:
# Before: get_config, _, check_alerts, gen_recs, _ = funcs
# After:
get_config, _, check_alerts, gen_recs = funcs

# Line 162 — refresh-path-config tool:
# Before: _, refresh_config, _, _, _ = funcs
# After:
_, refresh_config, _, _ = funcs

# Line 253 — update-path tool:
# Before: get_path_config, refresh_path_config, _, _, get_config_path = funcs
# After:
get_path_config, refresh_path_config, _, _ = funcs
```

Also in the update-path tool, replace `config_path = get_config_path(); config.save(config_path)` with `config.save()`.

- [ ] **Step 4: Delete `path_config.yaml`**

```bash
git rm src/config/path_config.yaml
```

- [ ] **Step 5: Verify no remaining references**

Run: `cd ~/Projects/Augur && grep -rn "get_config_path\|path_config\.yaml\|from_yaml" src/ --include="*.py" | grep -v __pycache__`

Expected: No matches (except this plan file).

- [ ] **Step 6: Run existing tests**

Run: `cd ~/Projects/Augur && python -m pytest tests/ -k "path_config or path" -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/config/path_config.py src/mcp/augur_mcp/compat.py src/mcp/augur_mcp/infrastructure/paths.py
git commit -m "refactor: remove path_config.yaml, update MCP consumers to use project.yaml"
```

---

### Task 6: Fix `src/mcp/augur_mcp/config.py` parallel resolution

**Files:**
- Modify: `src/mcp/augur_mcp/config.py`

- [ ] **Step 1: Replace `_get_vault_dir()` and `_get_documents_dir()`**

Replace the existing functions:

```python
def _get_vault_dir() -> Path:
    try:
        from src.config.paths import get_vault_dir
        return get_vault_dir()
    except ImportError:
        return _env_path("AUGUR_VAULT") or vault_home_dir(_get_project_name())


def _get_documents_dir() -> Path:
    try:
        from src.config.paths import get_documents_dir
        return get_documents_dir()
    except ImportError:
        return _env_path("AUGUR_DOCUMENTS") or documents_home_dir(_get_project_name())
```

- [ ] **Step 2: Verify MCP server starts**

Run: `cd ~/Projects/Augur && python -c "from src.mcp.augur_mcp.config import _get_vault_dir; print(_get_vault_dir())"`
Expected: prints the correct vault path.

- [ ] **Step 3: Commit**

```bash
git add src/mcp/augur_mcp/config.py
git commit -m "fix: delegate MCP config vault/docs resolution to paths.py"
```

---

### Task 7: Sweep hardcoded vault fallbacks across all skill MCP modules

**Files:**
- Modify: ~22 files across `skills/*/scripts/mcp/`
- Modify: `skills/daemon/scripts/schedule_executor.py`
- Modify: `src/lib/sync_discover.py`
- Modify: `src/scripts/migrate_vault_flatten.py`

The fallback patterns to replace fall into 3 categories. All files already have a `try: from src.config... except ImportError:` structure. The fix is the same for all — replace the entire `try/except` block for `get_skill_data_dir` with:

```python
# FULL REPLACEMENT — replaces the entire try/except block:
try:
    from src.config.paths import get_skill_data_dir
    from src.logging import get_entity_logger, tool_annotations
except ImportError:
    # ... other fallbacks stay ...

    def get_skill_data_dir(skill: str) -> Path:
        import os
        vault = os.environ.get("AUGUR_VAULT")
        return Path(vault) / skill if vault else Path.home() / "Vault" / "Augur" / skill
```

The key change: the `except ImportError` fallback version of `get_skill_data_dir` now reads `AUGUR_VAULT` env var before the hardcoded default. The `try` block's version already delegates to `paths.py` and needs no change.

- [ ] **Step 1: Fix Pattern 1 files — inline `os.environ.get` with default**

These 10 files use `os.environ.get("AUGUR_VAULT", Path.home() / "Vault" / "Augur")`:

- `skills/wealth/scripts/mcp/__init__.py`
- `skills/lifestyle/scripts/mcp/__init__.py`
- `skills/venture-augur/scripts/mcp/__init__.py`
- `skills/eisenhower/scripts/mcp/__init__.py`
- `skills/books/scripts/mcp/__init__.py`
- `skills/wearables/scripts/mcp/__init__.py`
- `skills/growth/scripts/mcp/__init__.py`
- `skills/consulting-template/scripts/mcp/__init__.py`
- `skills/system-cleanup/scripts/mcp/__init__.py`
- `skills/ai_bridge/scripts/mcp/__init__.py`

For each file, replace the `get_skill_data_dir` function in the `except ImportError` block with:

```python
    def get_skill_data_dir(skill: str) -> Path:
        import os
        vault = os.environ.get("AUGUR_VAULT")
        return Path(vault) / skill if vault else Path.home() / "Vault" / "Augur" / skill
```

- [ ] **Step 2: Fix Pattern 2 files — if/else fallback with iteration**

These 5 files use a multi-line if/else with bundle iteration:

- `skills/attention/scripts/mcp/_shared.py`
- `skills/career/scripts/mcp/_shared.py`
- `skills/smb-client-template/scripts/mcp/_helpers.py`
- `skills/linkedin-writer/scripts/mcp/__init__.py`
- `skills/terminal-automation-template/scripts/mcp/__init__.py`

Same replacement as Step 1.

- [ ] **Step 3: Fix Pattern 3 files — plain hardcode in try/except**

These 5 files have `return Path.home() / "Vault" / "Augur" / ...` in except blocks:

- `skills/health/scripts/mcp/__init__.py`
- `skills/page-builder/scripts/mcp/__init__.py`
- `skills/project-dev/scripts/mcp/__init__.py`
- `skills/finance/scripts/mcp/__init__.py`
- `skills/import/scripts/mcp/__init__.py`

For each, update the `except ImportError` block to use `os.environ.get("AUGUR_VAULT")` before the hardcoded path.

- [ ] **Step 4: Fix Pattern 4 — daemon schedule_executor.py**

In `skills/daemon/scripts/schedule_executor.py`, replace the platform-aware fallback:

```python
def get_skill_data_dir(skill_name: str) -> Path:
    try:
        from src.config.paths import get_skill_data_dir
        return get_skill_data_dir(skill_name)
    except ImportError:
        import os
        vault = os.environ.get("AUGUR_VAULT")
        return Path(vault) / skill_name if vault else Path.home() / "Vault" / "Augur" / skill_name
```

- [ ] **Step 5: Fix `src/lib/sync_discover.py`**

Replace the `_resolve_vault_root()` function (already partially fixed earlier in session):

```python
def _resolve_vault_root() -> Path:
    """Resolve vault root via src.config.paths."""
    try:
        from src.config.paths import get_vault_dir
        return get_vault_dir()
    except (ImportError, Exception):
        import os
        env = os.environ.get("AUGUR_VAULT")
        return Path(env) if env else Path.home() / "Vault" / "Augur"
```

- [ ] **Step 6: Fix `src/scripts/migrate_vault_flatten.py`**

Replace the VAULT/DOCS constants:

```python
try:
    from src.config.paths import get_vault_dir, get_documents_dir
    VAULT = get_vault_dir()
    DOCS = get_documents_dir()
except ImportError:
    import os
    VAULT = Path(os.environ["AUGUR_VAULT"]) if os.environ.get("AUGUR_VAULT") else Path.home() / "Vault" / "Augur"
    DOCS = Path(os.environ["AUGUR_DOCUMENTS"]) if os.environ.get("AUGUR_DOCUMENTS") else Path.home() / "Documents" / "Augur"
```

- [ ] **Step 7: Verify no remaining hardcoded vault paths in Python code**

Run: `cd ~/Projects/Augur && grep -rn 'Path.home().*"Vault"' src/ skills/ --include="*.py" | grep -v __pycache__ | grep -v node_modules`

Expected: Only `path_primitives.py:103` (the intentional last-resort default).

- [ ] **Step 8: Commit**

```bash
git add skills/ src/lib/sync_discover.py src/scripts/migrate_vault_flatten.py
git commit -m "fix: sweep all hardcoded vault fallbacks to use AUGUR_VAULT env var"
```

---

### Task 8: Update Stop hook and clean `~/.zshrc`

**Files:**
- Modify: `.claude/settings.json`
- Modify: `~/.zshrc`

- [ ] **Step 1: Update Stop hook in `.claude/settings.json`**

Replace the Stop hook command. Since hooks run in the project directory (AUGUR_ROOT), we can use PYTHONPATH:

```json
"command": "bash -c 'VAULT=$(PYTHONPATH=\"$PWD\" python3 -c \"from src.config.paths import get_vault_dir; print(get_vault_dir())\" 2>/dev/null || echo \"$AUGUR_VAULT\") && [ -n \"$VAULT\" ] && cd \"$VAULT\" && git rev-parse --git-dir >/dev/null 2>&1 && git add -u && { git diff --cached --quiet || git commit -m \"vault: auto-commit $(date +%Y-%m-%d-%H%M)\"; }'"
```

- [ ] **Step 2: Remove `AUGUR_VAULT` and `AUGUR_DOCUMENTS` from `~/.zshrc`**

Remove these two lines (keep `AUGUR_ROOT`):

```bash
export AUGUR_VAULT="$HOME/Projects/Au-vault"
export AUGUR_DOCUMENTS="$HOME/Projects/Au-docs"
```

- [ ] **Step 3: Verify Stop hook works**

Run: `source ~/.zshrc && cd ~/Projects/Augur && PYTHONPATH="$PWD" python3 -c "from src.config.paths import get_vault_dir; print(get_vault_dir())"`
Expected: prints `~/Projects/Au-vault`

- [ ] **Step 4: Commit**

```bash
git add .claude/settings.json
git commit -m "fix: update Stop hook to resolve vault via paths.py, clean zshrc"
```

---

### Task 9: Add missing tests — atomic write, prompt behavior, timeout

**Files:**
- Modify: `tests/unit/test_path_discovery.py`
- Modify: `tests/unit/test_path_resolution.py`

- [ ] **Step 1: Add `update_project_yaml` atomic write test**

Append to `tests/unit/test_path_discovery.py`:

```python
class TestUpdateProjectYaml:
    """Test atomic write to project.yaml."""

    def test_updates_vault_path(self, tmp_path):
        project_yaml = tmp_path / "project.yaml"
        project_yaml.write_text("name: Test\npaths:\n  vault: /old/path\n")
        with patch("src.config.path_discovery.get_project_root", return_value=tmp_path), \
             patch("src.config.path_discovery.invalidate_project_cache"):
            path_discovery.update_project_yaml("vault", Path("/new/path"))
        import yaml
        data = yaml.safe_load(project_yaml.read_text())
        assert data["paths"]["vault"] == "/new/path"

    def test_creates_paths_block_if_missing(self, tmp_path):
        project_yaml = tmp_path / "project.yaml"
        project_yaml.write_text("name: Test\nport: 3000\n")
        with patch("src.config.path_discovery.get_project_root", return_value=tmp_path), \
             patch("src.config.path_discovery.invalidate_project_cache"):
            path_discovery.update_project_yaml("vault", Path("/new/vault"))
        import yaml
        data = yaml.safe_load(project_yaml.read_text())
        assert data["paths"]["vault"] == "/new/vault"

    def test_atomic_write_no_partial_file_on_error(self, tmp_path):
        project_yaml = tmp_path / "project.yaml"
        project_yaml.write_text("name: Test\n")
        original = project_yaml.read_text()
        with patch("src.config.path_discovery.get_project_root", return_value=tmp_path), \
             patch("yaml.safe_dump", side_effect=RuntimeError("write error")):
            with pytest.raises(RuntimeError):
                path_discovery.update_project_yaml("vault", Path("/fail"))
        assert project_yaml.read_text() == original  # unchanged


class TestPromptUpdate:
    """Test interactive vs non-interactive prompt behavior."""

    def test_non_interactive_returns_false(self):
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = False
            result = path_discovery.prompt_update("vault", Path("/old"), Path("/new"))
        assert result is False

    def test_interactive_yes(self):
        with patch("sys.stdin") as mock_stdin, \
             patch("builtins.input", return_value="y"):
            mock_stdin.isatty.return_value = True
            result = path_discovery.prompt_update("vault", Path("/old"), Path("/new"))
        assert result is True

    def test_interactive_no(self):
        with patch("sys.stdin") as mock_stdin, \
             patch("builtins.input", return_value="n"):
            mock_stdin.isatty.return_value = True
            result = path_discovery.prompt_update("vault", Path("/old"), Path("/new"))
        assert result is False


class TestScanTimeout:
    """Test timeout budget."""

    def test_stops_after_timeout(self, tmp_path):
        for i in range(10):
            (tmp_path / f"dir-{i}").mkdir()
        (tmp_path / "dir-9" / ".augur-vault").write_text("project: Test\n")
        # Mock time.monotonic to simulate elapsed time
        call_count = 0
        def mock_monotonic():
            nonlocal call_count
            call_count += 1
            return float(call_count * 10)  # 10s per call, exceeds any budget
        with patch("src.config.path_discovery.time") as mock_time:
            mock_time.monotonic = mock_monotonic
            result = path_discovery.discover_path(
                "vault", configured=tmp_path / "wrong",
                search_roots=[tmp_path],
                timeout_secs=5.0,
            )
        assert result is None
```

- [ ] **Step 2: Run tests**

Run: `cd ~/Projects/Augur && python -m pytest tests/unit/test_path_discovery.py tests/unit/test_path_resolution.py -v`
Expected: All PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_path_discovery.py tests/unit/test_path_resolution.py
git commit -m "test: add atomic write, prompt behavior, and timeout budget tests"
```

---

### Task 10: Create `augur config fix` CLI command

**Files:**
- Create: `src/scripts/config_fix.py`

- [ ] **Step 1: Implement the CLI command**

Create `src/scripts/config_fix.py`:

```python
#!/usr/bin/env python3
"""augur config fix — discover moved vault/documents and update project.yaml."""
import argparse
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Fix stale paths in project.yaml")
    parser.add_argument("--deep", action="store_true", help="Include /Volumes scan")
    args = parser.parse_args()

    from src.config.paths import get_vault_dir, get_documents_dir, get_project_paths, get_skills_dir
    from src.config.path_discovery import (
        create_marker,
        discover_path,
        prompt_update,
        update_project_yaml,
        _default_search_roots,
    )

    project_paths = get_project_paths()
    checks = [
        ("vault", project_paths.get("vault")),
        ("documents", project_paths.get("documents")),
    ]

    for path_type, configured in checks:
        if configured is None:
            print(f"  {path_type}: not configured in project.yaml, skipping")
            continue
        if configured.exists():
            print(f"  {path_type}: OK at {configured}")
            create_marker(path_type, configured)
            continue

        search_roots = _default_search_roots(configured)
        if args.deep:
            volumes = Path("/Volumes")
            if volumes.exists():
                search_roots.append(volumes)

        discovered = discover_path(
            path_type,
            configured=configured,
            skills_dir=get_skills_dir(),
            search_roots=search_roots,
        )
        if discovered:
            if prompt_update(path_type, configured, discovered):
                update_project_yaml(path_type, discovered)
                create_marker(path_type, discovered)
                print(f"  {path_type}: updated to {discovered}")
            else:
                print(f"  {path_type}: skipped (user declined)")
        else:
            print(f"  {path_type}: NOT FOUND (configured: {configured})")

    # Regenerate daemon plist with updated AUGUR_VAULT
    plist = Path.home() / "Library" / "LaunchAgents" / "com.augur.daemon.plist"
    if plist.exists():
        try:
            import plistlib
            with open(plist, "rb") as f:
                plist_data = plistlib.load(f)
            env = plist_data.get("EnvironmentVariables", {})
            vault_path = get_vault_dir()
            docs_path = get_documents_dir()
            changed = False
            if str(env.get("AUGUR_VAULT")) != str(vault_path):
                env["AUGUR_VAULT"] = str(vault_path)
                changed = True
            if str(env.get("AUGUR_DOCUMENTS")) != str(docs_path):
                env["AUGUR_DOCUMENTS"] = str(docs_path)
                changed = True
            if changed:
                plist_data["EnvironmentVariables"] = env
                with open(plist, "wb") as f:
                    plistlib.dump(plist_data, f)
                print(f"\nUpdated daemon plist paths")
        except Exception as e:
            print(f"\nWarning: could not update daemon plist: {e}")

    print("\nDone. Restart the daemon to pick up changes:")
    print("  launchctl unload ~/Library/LaunchAgents/com.augur.daemon.plist")
    print("  launchctl load -w ~/Library/LaunchAgents/com.augur.daemon.plist")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Test it**

Run: `cd ~/Projects/Augur && python -m src.scripts.config_fix`
Expected: shows OK for vault and documents paths.

- [ ] **Step 3: Commit**

```bash
git add src/scripts/config_fix.py
git commit -m "feat: add 'augur config fix' CLI for batch path discovery and update"
```

---

### Task 11: Create marker files and run end-to-end verification

**Files:**
- No new files — uses `path_discovery.create_marker()`

- [ ] **Step 1: Create marker files in the vault and documents directories**

```bash
cd ~/Projects/Augur
python3 -c "
from src.config.path_discovery import create_marker
from src.config.paths import get_vault_dir, get_documents_dir
create_marker('vault', get_vault_dir())
create_marker('documents', get_documents_dir())
print('Vault marker:', get_vault_dir() / '.augur-vault')
print('Docs marker:', get_documents_dir() / '.augur-docs')
"
```

- [ ] **Step 2: Verify full resolution chain**

```bash
cd ~/Projects/Augur
python3 -c "
from src.config.paths import get_vault_dir, get_documents_dir, get_project_paths
print('project.yaml paths:', get_project_paths())
print('Vault:', get_vault_dir())
print('Documents:', get_documents_dir())
assert get_vault_dir().exists(), 'Vault does not exist!'
assert get_documents_dir().exists(), 'Documents does not exist!'
print('All paths verified.')
"
```

- [ ] **Step 3: Restart daemon and verify it resolves paths correctly**

```bash
launchctl unload ~/Library/LaunchAgents/com.augur.daemon.plist
launchctl load -w ~/Library/LaunchAgents/com.augur.daemon.plist
sleep 2
launchctl list com.augur.daemon | grep PID
```

- [ ] **Step 4: Run all path-related tests**

```bash
cd ~/Projects/Augur
python -m pytest tests/unit/test_path_resolution.py tests/unit/test_path_discovery.py -v
```

- [ ] **Step 5: Commit**

```bash
git add project.yaml src/config/path_discovery.py src/config/paths.py
git commit -m "feat: complete centralized path config with self-discovery"
```
