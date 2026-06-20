# Augur Project Framework Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform augur-os into a project framework where each clone is an independent project with scoped paths, isolated plugins, and per-project daemons.

**Architecture:** Add `project.yaml` at repo root as the single identity file. Update `paths.py` to derive all external paths from the project name. Re-tag base skills, extract `augur-ops` plugin, and build `augur init` CLI.

**Tech Stack:** Python (paths, daemon, CLI), YAML (project config, skill frontmatter), zsh (shell shortcuts)

**Spec:** `docs/superpowers/specs/2026-03-19-augur-project-framework-design.md`

---

### Task 1: Add project.yaml to current Augur (Project0)

**Files:**
- Create: `project.yaml`
- Test: manual — verify `cat project.yaml` shows correct config

- [ ] **Step 1: Create project.yaml at repo root**

```yaml
name: Augur
port: 3000
```

Note: No `plugins` section yet — that comes with the install flow (Task 7).

- [ ] **Step 2: Add project.yaml to .gitignore considerations**

`project.yaml` should NOT be in `.gitignore` — it's part of the project identity and should be tracked. Verify it's not gitignored:

Run: `git check-ignore project.yaml`
Expected: No output (not ignored)

- [ ] **Step 3: Commit**

```bash
git add project.yaml
git commit -m "feat: add project.yaml for project identity (Project0)"
```

---

### Task 2: Update paths.py — add get_project_name() with caching

**Files:**
- Modify: `src/config/paths.py`
- Create: `tests/unit/test_project_name.py`

**Context:** `paths.py` is the central path resolver. Every external path function hardcodes `"Augur"`. We add `get_project_name()` that reads from `project.yaml` with a module-level cache. The fallback to `"Augur"` ensures backward compatibility.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_project_name.py
"""Tests for get_project_name() from project.yaml."""

import yaml
from pathlib import Path
from unittest.mock import patch


def test_get_project_name_reads_from_project_yaml(tmp_path):
    """get_project_name() reads name from project.yaml at project root."""
    import src.config.paths as paths_mod

    # Reset cache
    paths_mod._project_name_cache = None

    project_yaml = tmp_path / "project.yaml"
    project_yaml.write_text(yaml.dump({"name": "myapp", "port": 3001}))

    with patch.object(paths_mod, "get_project_root", return_value=tmp_path):
        result = paths_mod.get_project_name()
        assert result == "myapp"

    # Reset cache for other tests
    paths_mod._project_name_cache = None


def test_get_project_name_falls_back_to_augur(tmp_path):
    """get_project_name() returns 'Augur' when no project.yaml exists."""
    import src.config.paths as paths_mod

    paths_mod._project_name_cache = None

    with patch.object(paths_mod, "get_project_root", return_value=tmp_path):
        result = paths_mod.get_project_name()
        assert result == "Augur"

    paths_mod._project_name_cache = None


def test_get_project_name_caches_result(tmp_path):
    """get_project_name() caches the result after first read."""
    import src.config.paths as paths_mod

    paths_mod._project_name_cache = None

    project_yaml = tmp_path / "project.yaml"
    project_yaml.write_text(yaml.dump({"name": "cached-app", "port": 3002}))

    with patch.object(paths_mod, "get_project_root", return_value=tmp_path):
        result1 = paths_mod.get_project_name()
        # Delete the file — cache should still return the same value
        project_yaml.unlink()
        result2 = paths_mod.get_project_name()
        assert result1 == result2 == "cached-app"

    paths_mod._project_name_cache = None


def test_get_project_port_reads_from_project_yaml(tmp_path):
    """get_project_port() reads port from project.yaml."""
    import src.config.paths as paths_mod

    paths_mod._project_port_cache = None

    project_yaml = tmp_path / "project.yaml"
    project_yaml.write_text(yaml.dump({"name": "myapp", "port": 3001}))

    with patch.object(paths_mod, "get_project_root", return_value=tmp_path):
        result = paths_mod.get_project_port()
        assert result == 3001

    paths_mod._project_port_cache = None


def test_get_project_port_defaults_to_3000(tmp_path):
    """get_project_port() returns 3000 when no project.yaml exists."""
    import src.config.paths as paths_mod

    paths_mod._project_port_cache = None

    with patch.object(paths_mod, "get_project_root", return_value=tmp_path):
        result = paths_mod.get_project_port()
        assert result == 3000

    paths_mod._project_port_cache = None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Projects/Augur && python -m pytest tests/unit/test_project_name.py -v`
Expected: FAIL — `get_project_name` and `get_project_port` do not exist yet

- [ ] **Step 3: Implement get_project_name() in paths.py**

Add after the `_expand` / `_env_path` / `_is_macos` helper functions (around line 38), before `_application_support_dir`:

```python
import yaml as _yaml_mod

_project_name_cache: str | None = None


def get_project_name() -> str:
    """Read project name from project.yaml at repo root. Cached after first read.

    Falls back to 'Augur' if no project.yaml exists (backward compatibility).
    """
    global _project_name_cache
    if _project_name_cache is not None:
        return _project_name_cache
    project_yaml = get_project_root() / "project.yaml"
    if project_yaml.exists():
        data = _yaml_mod.safe_load(project_yaml.read_text(encoding="utf-8"))
        _project_name_cache = data.get("name", "Augur") if isinstance(data, dict) else "Augur"
    else:
        _project_name_cache = "Augur"
    return _project_name_cache


_project_port_cache: int | None = None


def get_project_port() -> int:
    """Read dashboard port from project.yaml. Cached after first read. Defaults to 3000."""
    global _project_port_cache
    if _project_port_cache is not None:
        return _project_port_cache
    project_yaml = get_project_root() / "project.yaml"
    if project_yaml.exists():
        data = _yaml_mod.safe_load(project_yaml.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            _project_port_cache = int(data.get("port", 3000))
        else:
            _project_port_cache = 3000
    else:
        _project_port_cache = 3000
    return _project_port_cache


def invalidate_project_name_cache() -> None:
    """Clear the cached project name. Call when project.yaml changes."""
    global _project_name_cache
    _project_name_cache = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/Projects/Augur && python -m pytest tests/unit/test_project_name.py -v`
Expected: PASS — all 3 tests

- [ ] **Step 5: Commit**

```bash
git add src/config/paths.py tests/unit/test_project_name.py
git commit -m "feat: add get_project_name() with caching to paths.py"
```

---

### Task 3: Scope all external paths by project name

**Files:**
- Modify: `src/config/paths.py`
- Create: `tests/unit/test_scoped_paths.py`

**Context:** Replace hardcoded `"Augur"` in every external path function with `get_project_name()`. This covers vault, documents, runtime (Application Support), logs, cache, and RAG dirs.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_scoped_paths.py
"""Tests that external paths are scoped by project name."""

import yaml
from pathlib import Path
from unittest.mock import patch


def _setup_project(tmp_path, name="testproject"):
    """Helper: create project.yaml and reset cache."""
    import src.config.paths as pm
    pm._project_name_cache = None
    project_yaml = tmp_path / "project.yaml"
    project_yaml.write_text(yaml.dump({"name": name, "port": 3000}))
    return pm


def test_vault_scoped_by_project_name(tmp_path):
    pm = _setup_project(tmp_path)
    with patch.object(pm, "get_project_root", return_value=tmp_path):
        vault = pm.get_vault_dir()
        assert vault.name == "testproject"
        assert "Vault" in str(vault)
    pm._project_name_cache = None


def test_documents_scoped_by_project_name(tmp_path):
    pm = _setup_project(tmp_path)
    with patch.object(pm, "get_project_root", return_value=tmp_path):
        docs = pm.get_documents_dir()
        assert docs.name == "testproject"
        assert "Documents" in str(docs)
    pm._project_name_cache = None


def test_logs_scoped_by_project_name(tmp_path):
    pm = _setup_project(tmp_path)
    with patch.object(pm, "get_project_root", return_value=tmp_path):
        logs = pm.get_logs_dir()
        assert "testproject" in str(logs)
    pm._project_name_cache = None


def test_cache_scoped_by_project_name(tmp_path):
    pm = _setup_project(tmp_path)
    with patch.object(pm, "get_project_root", return_value=tmp_path):
        cache = pm.get_cache_dir()
        assert "testproject" in str(cache)
    pm._project_name_cache = None


def test_fallback_uses_augur(tmp_path):
    """Without project.yaml, paths still use 'Augur'."""
    import src.config.paths as pm
    pm._project_name_cache = None
    # No project.yaml created
    with patch.object(pm, "get_project_root", return_value=tmp_path):
        vault = pm.get_vault_dir()
        assert vault.name == "Augur"
    pm._project_name_cache = None


def test_env_override_takes_precedence(tmp_path, monkeypatch):
    """Env vars still override project.yaml-derived paths."""
    pm = _setup_project(tmp_path)
    monkeypatch.setenv("AUGUR_VAULT", str(tmp_path / "custom-vault"))
    with patch.object(pm, "get_project_root", return_value=tmp_path):
        vault = pm.get_vault_dir()
        assert vault == (tmp_path / "custom-vault").resolve()
    pm._project_name_cache = None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_scoped_paths.py -v`
Expected: FAIL — paths still return `"Augur"` not `"testproject"`

- [ ] **Step 3: Update all external path functions in paths.py**

Replace every hardcoded `"Augur"` with `get_project_name()`:

```python
def _application_support_dir() -> Path:
    override = _env_path("AUGUR_APP_SUPPORT")
    if override:
        return override
    if _is_macos():
        return _expand(f"~/Library/Application Support/{get_project_name()}")
    return _xdg_data_home() / get_project_name().lower()


def _logs_home_dir() -> Path:
    override = _env_path("AUGUR_LOGS")
    if override:
        return override
    if _is_macos():
        return _expand(f"~/Library/Logs/{get_project_name()}")
    return _xdg_state_home() / get_project_name().lower() / "logs"


def _cache_home_dir() -> Path:
    override = _env_path("AUGUR_CACHE_DIR", "AUGUR_CACHE_PATH")
    if override:
        return override
    if _is_macos():
        return _expand(f"~/Library/Caches/{get_project_name()}")
    return _xdg_cache_home() / get_project_name().lower()


def _vault_home_dir() -> Path:
    override = _env_path("AUGUR_VAULT")
    if override:
        return override
    return _expand(f"~/Vault/{get_project_name()}")


def _documents_home_dir() -> Path:
    override = _env_path("AUGUR_DOCUMENTS")
    if override:
        return override
    return _expand(f"~/Documents/{get_project_name()}")
```

Also update `_state_home_dir()` Linux fallback — it hardcodes `"augur"` separately from `_application_support_dir()`:

```python
def _state_home_dir() -> Path:
    override = _env_path("AUGUR_STATE")
    if override:
        return override
    if _is_macos():
        return _application_support_dir() / "state"
    return _xdg_state_home() / get_project_name().lower()
```

Note: `_rag_home_dir()` derives from `_application_support_dir()` which is already scoped — no change needed for it.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_scoped_paths.py -v`
Expected: PASS — all 6 tests

- [ ] **Step 5: Run existing tests to verify no regressions**

Run: `python -m pytest tests/ -v --timeout=30 -x -q 2>&1 | head -50`
Expected: No failures related to path resolution

- [ ] **Step 6: Commit**

```bash
git add src/config/paths.py tests/unit/test_scoped_paths.py
git commit -m "feat: scope all external paths by project name from project.yaml"
```

---

### Task 4: Replace PLUGIN_BUNDLES with dynamic discovery

**Files:**
- Modify: `src/config/paths.py` (lines 142-146, 271-299)

**Context:** The hardcoded `PLUGIN_BUNDLES` list doesn't match reality and won't work when projects have different plugin sets. Replace it with dynamic scanning of `plugins/*/skills/`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_dynamic_discovery.py
"""Tests that plugin discovery is dynamic, not hardcoded."""

from pathlib import Path
from unittest.mock import patch


def test_discover_finds_plugins_dynamically(tmp_path):
    """Discovery scans plugins/ directory instead of using hardcoded list."""
    import src.config.paths as pm
    pm._skill_to_bundle_cache = None
    pm._project_name_cache = None

    # Create a fake plugin structure
    plugins_dir = tmp_path / "plugins"
    (plugins_dir / "augur" / "skills" / "onboard").mkdir(parents=True)
    (plugins_dir / "augur" / "skills" / "daemon").mkdir(parents=True)
    (plugins_dir / "augur-dev" / "skills" / "dev-debug").mkdir(parents=True)

    with patch.object(pm, "get_project_root", return_value=tmp_path):
        with patch.object(pm, "get_all_client_skill_dirs", return_value=[]):
            mapping = pm._discover_skill_to_bundle_mapping()

    assert "onboard" in mapping
    assert mapping["onboard"] == "augur"
    assert "daemon" in mapping
    assert "dev-debug" in mapping
    assert mapping["dev-debug"] == "augur-dev"

    pm._skill_to_bundle_cache = None
    pm._project_name_cache = None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_dynamic_discovery.py -v`
Expected: FAIL — current code iterates `PLUGIN_BUNDLES` list, not filesystem

- [ ] **Step 3: Replace PLUGIN_BUNDLES constant with a dynamic function**

In `paths.py`, replace the hardcoded list with a function, and keep the constant name as a backward-compat alias:

```python
def get_plugin_bundles() -> list[str]:
    """Dynamically discover plugin bundles by scanning plugins/ directory.

    Replaces the old hardcoded PLUGIN_BUNDLES list.
    """
    plugins_dir = get_project_root() / "plugins"
    if not plugins_dir.is_dir():
        return []
    return [
        d.name for d in sorted(plugins_dir.iterdir())
        if d.is_dir() and not d.name.startswith(".") and (d / "skills").is_dir()
    ]


# Backward compat: importers use this name. Now computed dynamically.
# WARNING: This is a list snapshot at import time for legacy code.
# New code should call get_plugin_bundles() directly.
PLUGIN_BUNDLES = get_plugin_bundles()
```

Update `_discover_skill_to_bundle_mapping` to use `get_plugin_bundles()` instead of the constant:

```python
def _discover_skill_to_bundle_mapping() -> dict[str, str]:
    global _skill_to_bundle_cache
    if _skill_to_bundle_cache is not None:
        return _skill_to_bundle_cache

    mapping: dict[str, str] = {}
    for plugins_dir in get_all_plugin_dirs():
        if not plugins_dir.exists():
            continue
        # Dynamic scan: iterate all plugin directories instead of hardcoded list
        for plugin_dir in plugins_dir.iterdir():
            if not plugin_dir.is_dir() or plugin_dir.name.startswith("."):
                continue
            skills_dir = plugin_dir / "skills"
            if not skills_dir.exists():
                continue
            for skill_dir in skills_dir.iterdir():
                if skill_dir.is_dir() and not skill_dir.name.startswith("."):
                    mapping[skill_dir.name] = plugin_dir.name

    # Also discover skills in client skill directories
    for client_skills_dir in get_all_client_skill_dirs():
        for skill_dir in client_skills_dir.iterdir():
            if not skill_dir.is_dir() or skill_dir.name.startswith("."):
                continue
            skill_name = skill_dir.name
            if skill_name in mapping:
                continue
            plugin = _read_skill_plugin(skill_dir)
            if plugin:
                mapping[skill_name] = plugin

    _skill_to_bundle_cache = mapping
    return mapping
```

- [ ] **Step 4: Update all files that import PLUGIN_BUNDLES**

These files import `PLUGIN_BUNDLES` and must be updated to use `get_plugin_bundles()`:

| File | Change |
|------|--------|
| `src/plugins/skill_registry.py` | `from src.config.paths import get_plugin_bundles` — replace `PLUGIN_BUNDLES` usage with `get_plugin_bundles()` |
| `src/mcp/augur_mcp/plugin_tools.py` | `from src.config.paths import get_plugin_bundles` — replace constant with function call |
| `src/mcp/augur_mcp/adapters/filesystem_registry.py` | Replace `DEFAULT_PLUGIN_BUNDLES` tuple with `get_plugin_bundles()` call |
| `src/mcp/augur_mcp/context_injector.py` | Update import chain (imports from plugin_tools) |
| `src/mcp/augur_mcp/registry_loader.py` | Update import chain (imports from plugin_tools) |
| `src/mcp/augur_mcp/config.py` | Update to use `get_plugin_bundles()` instead of `DEFAULT_PLUGIN_BUNDLES` |

For each file: grep for `PLUGIN_BUNDLES`, replace with `get_plugin_bundles()`, update import.

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/unit/test_dynamic_discovery.py tests/unit/test_project_name.py tests/unit/test_scoped_paths.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/config/paths.py tests/unit/test_dynamic_discovery.py
git commit -m "feat: replace hardcoded PLUGIN_BUNDLES with dynamic plugin discovery"
```

---

### Task 5: Scope daemon plist naming by project name

**Files:**
- Modify: `.claude/skills/daemon/scripts/service_healer.py` (line 81)
- Modify: `.claude/skills/daemon/assets/plists/com.augur.daemon.plist.template`
- Modify: `.claude/skills/daemon/assets/plists/com.augur.dashboard.plist.template`
- Modify: `.claude/skills/daemon/scripts/dashboard_monitor.py` (line 128)
- Modify: `.claude/skills/daemon/scripts/cleanup_processes.py` (port defaults)

**Context:** Hardcoded `"com.augur.daemon"` plist labels and port `3000` need to derive from `get_project_name()` and `get_project_port()`. Multiple projects on the same machine need distinct plist labels and ports.

- [ ] **Step 1: Update service_healer.py plist references**

Replace hardcoded `"com.augur.daemon.plist"` with a function that derives from project name:

```python
from src.config.paths import get_project_name

def _plist_label() -> str:
    return f"com.{get_project_name().lower()}.daemon"

def _plist_filename() -> str:
    return f"{_plist_label()}.plist"
```

Replace all `"com.augur.daemon.plist"` references with `_plist_filename()` and all `"com.augur.daemon"` label references with `_plist_label()`.

Also update legacy plist references (`com.augur.logmonitor`, `com.augur.nightly`, `com.augur.continuous`) — these should still use hardcoded names since they are legacy cleanup targets.

- [ ] **Step 2: Update dashboard_monitor.py port**

Replace `DASHBOARD_PORT = 3000` with:

```python
from src.config.paths import get_project_port
DASHBOARD_PORT = get_project_port()
```

- [ ] **Step 3: Update cleanup_processes.py port defaults**

Replace hardcoded `port: int = 3000` defaults with `get_project_port()`:

```python
from src.config.paths import get_project_port

def get_pids_on_port(port: int | None = None) -> list[int]:
    if port is None:
        port = get_project_port()
    ...

def cleanup_port(port: int | None = None, ...):
    if port is None:
        port = get_project_port()
    ...
```

- [ ] **Step 4: Update plist templates**

The plist template files need the label parameterized. If they use string substitution already, update the label field. If not, add a `{label}` placeholder:

```xml
<key>Label</key>
<string>{label}</string>
```

And update the script that generates plists from templates to pass `_plist_label()`.

- [ ] **Step 5: Update other hardcoded localhost:3000 references**

Files to update (use `get_project_port()`):
- `.claude/skills/daemon/scripts/notification_service.py` (line 405)
- `.claude/skills/daemon/scripts/schedule_executor.py` (line 106)
- `.claude/skills/daemon/scripts/insight_scanner.py` (line 599)

Pattern: replace `http://localhost:3000` with `f"http://localhost:{get_project_port()}"`.

- [ ] **Step 6: Fix cleanup_processes.py hardcoded 3000 conditionals**

This file has `port == 3000` in conditional branches (lines 547, 572, 604) and a hardcoded dict key `"port_3000"` (line 670). These are not just defaults — they contain port-specific logic. Update all of them:

- Replace `if force and port == 3000` with `if force and port == get_project_port()`
- Replace `if port == 3000` with `if port == get_project_port()`
- Replace `"port_3000": cleanup_port(3000, ...)` with `f"port_{get_project_port()}": cleanup_port(get_project_port(), ...)`

- [ ] **Step 8: Verify daemon still starts**

Run: `python .claude/skills/daemon/scripts/unified_daemon.py status`
Expected: Shows status without errors

- [ ] **Step 9: Commit**

```bash
git add .claude/skills/daemon/
git commit -m "feat: scope daemon plist labels and ports by project name"
```

---

### Task 6: Re-tag 7 base skills from augur-system to augur

**Files:**
- Modify: `.claude/skills/daemon/SKILL.md`
- Modify: `.claude/skills/discovery/SKILL.md`
- Modify: `.claude/skills/file-manager/SKILL.md`
- Modify: `.claude/skills/save/SKILL.md`
- Modify: `.claude/skills/import/SKILL.md`
- Modify: `.claude/skills/kill-augur/SKILL.md`
- Modify: `.claude/skills/updater/SKILL.md`

**Context:** These 7 skills currently declare `x-augur-plugin: augur-system`. They are base platform skills and must be re-tagged to `x-augur-plugin: augur` so they belong to the unified base plugin.

**Important clarification:** Base skills remain in `.claude/skills/` (Claude Code-mastered) in the main Augur repo. The `plugins/augur/skills/` structure shown in the spec's Section 10 is the target layout for the augur-os template repo only (Task 8). In the main Augur repo, the frontmatter tag is what matters — it determines which plugin a skill belongs to for vault path resolution, not its physical directory.

- [ ] **Step 1: Verify current tagging**

Run: `grep -l "x-augur-plugin: augur-system" .claude/skills/*/SKILL.md` (use Grep tool)
Expected: 16 files (7 base + 8 augur-ops + 1 skillstore)

- [ ] **Step 2: Re-tag the 7 base skills**

For each of these 7 SKILL.md files, change `x-augur-plugin: augur-system` to `x-augur-plugin: augur`:

1. `.claude/skills/daemon/SKILL.md`
2. `.claude/skills/discovery/SKILL.md`
3. `.claude/skills/file-manager/SKILL.md`
4. `.claude/skills/save/SKILL.md`
5. `.claude/skills/import/SKILL.md`
6. `.claude/skills/kill-augur/SKILL.md`
7. `.claude/skills/updater/SKILL.md`

Use the Edit tool for each file. The change is a single line in the YAML frontmatter.

- [ ] **Step 3: Verify re-tagging**

Run: `grep "x-augur-plugin: augur$" .claude/skills/*/SKILL.md` (use Grep tool)

Expected: 7 files plus `onboard` (which was already `augur`) = 8 total base skills tagged `augur`.

- [ ] **Step 4: Verify remaining augur-system skills are the 8 for augur-ops**

Run: `grep -l "x-augur-plugin: augur-system" .claude/skills/*/SKILL.md` (use Grep tool)

Expected: 9 files remaining — the 8 augur-ops skills (observe, metrics, ops-daemon, dev-loops, channels, remote-access, system-cleanup, workflows) + skillstore.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/daemon/SKILL.md .claude/skills/discovery/SKILL.md .claude/skills/file-manager/SKILL.md .claude/skills/save/SKILL.md .claude/skills/import/SKILL.md .claude/skills/kill-augur/SKILL.md .claude/skills/updater/SKILL.md
git commit -m "feat: re-tag 7 base skills from augur-system to augur plugin"
```

---

### Task 7: Create augur-ops plugin from extracted augur-system skills

**Files:**
- Modify: `.claude/skills/observe/SKILL.md`
- Modify: `.claude/skills/metrics/SKILL.md`
- Modify: `.claude/skills/ops-daemon/SKILL.md`
- Modify: `.claude/skills/dev-loops/SKILL.md`
- Modify: `.claude/skills/channels/SKILL.md`
- Modify: `.claude/skills/remote-access/SKILL.md`
- Modify: `.claude/skills/system-cleanup/SKILL.md`
- Modify: `.claude/skills/workflows/SKILL.md`

**Context:** The remaining 8 augur-system skills become the new `augur-ops` plugin. Since these are Claude Code-mastered skills (they live in `.claude/skills/`), the change is just re-tagging their frontmatter. The `augur-system` plugin name is then retired.

- [ ] **Step 1: Re-tag 8 skills from augur-system to augur-ops**

For each of these 8 SKILL.md files, change `x-augur-plugin: augur-system` to `x-augur-plugin: augur-ops`:

1. `.claude/skills/observe/SKILL.md`
2. `.claude/skills/metrics/SKILL.md`
3. `.claude/skills/ops-daemon/SKILL.md`
4. `.claude/skills/dev-loops/SKILL.md`
5. `.claude/skills/channels/SKILL.md`
6. `.claude/skills/remote-access/SKILL.md`
7. `.claude/skills/system-cleanup/SKILL.md`
8. `.claude/skills/workflows/SKILL.md`

- [ ] **Step 2: Decide on skillstore**

`skillstore` also declares `x-augur-plugin: augur-system`. It's the marketplace client. Per the spec, marketplace metadata is part of the base `augur` plugin. Re-tag skillstore to `x-augur-plugin: augur`:

Modify: `.claude/skills/skillstore/SKILL.md` — change `x-augur-plugin: augur-system` to `x-augur-plugin: augur`

- [ ] **Step 3: Verify no skills reference augur-system anymore**

Run: `grep -r "augur-system" .claude/skills/*/SKILL.md` (use Grep tool)
Expected: 0 results — `augur-system` is fully retired

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/observe/SKILL.md .claude/skills/metrics/SKILL.md .claude/skills/ops-daemon/SKILL.md .claude/skills/dev-loops/SKILL.md .claude/skills/channels/SKILL.md .claude/skills/remote-access/SKILL.md .claude/skills/system-cleanup/SKILL.md .claude/skills/workflows/SKILL.md .claude/skills/skillstore/SKILL.md
git commit -m "feat: create augur-ops plugin, retire augur-system"
```

---

### Task 8: Rebase augur-os to latest Augur and strip to base

**Files:**
- Work happens in the `augur-os` repo (separate from main Augur)

**Context:** The `augur-os` repo needs to be rebased to the latest Augur (which now has project.yaml, scoped paths, and re-tagged skills) and then stripped to contain only the base `augur` plugin.

**Important:** This task requires access to the augur-os repo. If it's at `~/Projects/augur-os/`, work there. Otherwise, clone it first.

- [ ] **Step 1: Find and verify augur-os repo**

Run: `ls ~/Projects/augur-os/ 2>/dev/null || echo "not found"`

If not found, determine where it lives or clone it.

- [ ] **Step 2: Rebase augur-os to latest Augur main**

```bash
cd ~/Projects/augur-os
git remote add upstream ../Augur 2>/dev/null || true
git fetch upstream
git rebase upstream/main
```

Resolve any conflicts. The key files from upstream that must land:
- `project.yaml`
- Updated `src/config/paths.py` (with `get_project_name()`)
- Re-tagged SKILL.md files

- [ ] **Step 3: Set augur-os project.yaml**

```yaml
name: augur-os
port: 3000
```

- [ ] **Step 4: Strip to base plugin only**

Remove all opt-in plugin skills from `.claude/skills/`. Keep only base skills:
- onboard, daemon, discovery, file-manager, save, import, kill-augur, updater, skillstore

Remove domain/opt-in skills directories. The exact list depends on what's in augur-os after rebase — remove everything NOT in the base list.

- [ ] **Step 5: Strip config to minimal**

Remove domain-specific config files. Keep only system-level config needed by base skills.

- [ ] **Step 6: Create minimal CLAUDE.md**

Strip CLAUDE.md to only universal rules:
- Rule 1 (user experience priority)
- Rule 3 (no hardcoded paths)
- Rule 4 (data separation)
- Rule 5 (no workarounds)
- Rule 9 (fix blockers before handoff)

Remove Augur-specific rules about hubs, dashboard, plugin decentralization.

- [ ] **Step 7: Commit in augur-os**

```bash
git add -A
git commit -m "feat: strip augur-os to base framework template"
```

---

### Task 9: Test dual-clone coexistence

**Files:**
- No code changes — validation only

**Context:** Run both Augur (Project0) and augur-os as separate projects on the same machine. Verify path isolation, daemon independence, and no collisions.

- [ ] **Step 1: Verify path isolation**

```bash
cd ~/Projects/Augur
python -c "from src.config.paths import get_vault_dir, get_project_name; print(f'{get_project_name()}: {get_vault_dir()}')"
# Expected: Augur: get_vault_dir()

cd ~/Projects/augur-os
python -c "from src.config.paths import get_vault_dir, get_project_name; print(f'{get_project_name()}: {get_vault_dir()}')"
# Expected: augur-os: ~/Vault/augur-os
```

- [ ] **Step 2: Verify external dirs are created**

```bash
cd ~/Projects/augur-os
python -c "from src.config.paths import validate_paths; validate_paths()"
ls ~/Vault/augur-os/
ls ~/Library/Logs/augur-os/
ls ~/Library/Application\ Support/augur-os/
```

Expected: All directories created with project name, separate from Augur's dirs.

- [ ] **Step 3: Test daemon coexistence**

```bash
# Start augur-os daemon
cd ~/Projects/augur-os
python .claude/skills/daemon/scripts/unified_daemon.py start

# Verify both daemons run
cd ~/Projects/Augur
python .claude/skills/daemon/scripts/unified_daemon.py status
# Expected: Shows Augur daemon status

cd ~/Projects/augur-os
python .claude/skills/daemon/scripts/unified_daemon.py status
# Expected: Shows augur-os daemon status (separate PID)

# Check PID files are separate
cat ~/Library/Application\ Support/Augur/state/daemon.pid
cat ~/Library/Application\ Support/augur-os/state/daemon.pid
# Expected: Different PIDs

# Stop augur-os daemon
python .claude/skills/daemon/scripts/unified_daemon.py stop
```

- [ ] **Step 4: Document any issues found**

If anything fails, create a follow-up task to fix it before proceeding.

- [ ] **Step 5: Commit test results (if any fixes needed)**

---

### Task 10: Build augur init CLI command

**Files:**
- Create: `.claude/skills/onboard/scripts/augur_init.py`
- Create: `tests/unit/test_augur_init.py`

**Context:** `augur init myapp` clones augur-os, sets project.yaml, creates external dirs, generates MCP config, and runs onboard. This is a CLI script that can be run as `python .claude/skills/onboard/scripts/augur_init.py myapp`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_augur_init.py
"""Tests for augur init project creation."""

import json
from pathlib import Path
from unittest.mock import patch

import yaml

# Import path will work after the script is created
# from ...claude.skills.onboard.scripts.augur_init import init_project


def test_init_creates_project_yaml(tmp_path):
    """init_project creates project.yaml with correct name and port."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    # We need to import after path setup; for now test the core logic inline

    project_dir = tmp_path / "myapp"
    project_dir.mkdir()

    # Simulate what init_project does (step 2: write project.yaml)
    from augur_init_helpers import write_project_yaml  # will fail until implemented

    write_project_yaml(project_dir, "myapp", 3001)

    loaded = yaml.safe_load((project_dir / "project.yaml").read_text())
    assert loaded["name"] == "myapp"
    assert loaded["port"] == 3001


def test_init_creates_external_dirs(tmp_path):
    """init_project creates all scoped external directories."""
    project_dir = tmp_path / "testapp"
    project_dir.mkdir()

    from augur_init_helpers import create_external_dirs  # will fail until implemented

    create_external_dirs("testapp", home=tmp_path / "fakehome")

    fakehome = tmp_path / "fakehome"
    assert (fakehome / "Vault" / "testapp").is_dir()
    assert (fakehome / "Documents" / "testapp").is_dir()


def test_init_creates_mcp_config(tmp_path):
    """init_project generates .claude/mcp.json with project-specific config."""
    project_dir = tmp_path / "myapp"
    project_dir.mkdir()

    from augur_init_helpers import write_mcp_config  # will fail until implemented

    write_mcp_config(project_dir, "myapp")

    mcp = json.loads((project_dir / ".claude" / "mcp.json").read_text())
    assert "myapp" in mcp["mcpServers"]
    assert "AUGUR_ROOT" in mcp["mcpServers"]["myapp"]["env"]
```

Note: Tests import from helper module that `augur_init.py` exposes. Adjust imports based on actual module structure when implementing.

- [ ] **Step 2: Implement augur_init.py**

```python
#!/usr/bin/env python3
"""
augur init — Create a new Augur project from the augur-os template.

Usage:
    python augur_init.py <project-name> [--port PORT] [--repo URL]
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import yaml


DEFAULT_REPO = "https://github.com/augur-os/augur-os"
DEFAULT_PORT = 3000


def init_project(
    name: str,
    target_dir: Path | None = None,
    port: int = DEFAULT_PORT,
    repo: str = DEFAULT_REPO,
) -> Path:
    """Create a new Augur project.

    1. Clone augur-os repo
    2. Write project.yaml with name and port
    3. Create scoped external dirs
    4. Generate MCP config
    """
    target = target_dir or Path.cwd() / name

    # 1. Clone
    if not target.exists():
        subprocess.run(
            ["git", "clone", repo, str(target)],
            check=True,
        )

    # 2. Write project.yaml
    project_yaml = target / "project.yaml"
    project_yaml.write_text(
        yaml.dump({"name": name, "port": port}, default_flow_style=False)
    )

    # 3. Create scoped external dirs
    home = Path.home()
    dirs = [
        home / "Vault" / name,
        home / "Documents" / name,
        home / "Library" / "Application Support" / name / "state",
        home / "Library" / "Application Support" / name / "rag",
        home / "Library" / "Logs" / name,
        home / "Library" / "Caches" / name,
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)

    # 4. Generate MCP config
    claude_dir = target / ".claude"
    claude_dir.mkdir(exist_ok=True)
    mcp_config = {
        "mcpServers": {
            name: {
                "command": str(target / ".venv" / "bin" / "python3"),
                "args": ["-m", "src.mcp.server"],
                "env": {
                    "AUGUR_ROOT": str(target),
                    "PYTHONPATH": str(target),
                },
            }
        }
    }
    (claude_dir / "mcp.json").write_text(json.dumps(mcp_config, indent=2))

    return target


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a new Augur project")
    parser.add_argument("name", help="Project name")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Dashboard port")
    parser.add_argument("--repo", default=DEFAULT_REPO, help="Template repo URL")
    args = parser.parse_args()

    target = init_project(args.name, port=args.port, repo=args.repo)
    print(f"Project '{args.name}' created at {target}")
    print(f"Next: cd {target} && python .claude/skills/onboard/scripts/onboard.py")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/unit/test_augur_init.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/onboard/scripts/augur_init.py tests/unit/test_augur_init.py
git commit -m "feat: add augur init CLI for project creation"
```

---

### Task 11: Update shell shortcuts to accept project argument

**Files:**
- This modifies `~/.zshrc` — user's personal config, NOT repo files

**Context:** Current shell aliases are hardcoded to `$AUGUR_ROOT` and port 3000. Update them to accept an optional project name argument, defaulting to `augur`.

**Important:** This is a manual user-side change. The plan documents the pattern; the user applies it.

- [ ] **Step 1: Document the shell shortcut pattern**

Create a reference doc in the repo:

```bash
# File: docs/references/shell-shortcuts.md
```

Content:

```markdown
# Shell Shortcuts for Multi-Project Augur

Add to your `.zshrc` or `.bashrc`:

## Project-aware helpers

PROJECTS_DIR="$HOME/Projects"

augur-cd() {
  local project="${1:-Augur}"
  cd "$PROJECTS_DIR/$project"
}

augur-dev() {
  local project="${1:-Augur}"
  cd "$PROJECTS_DIR/$project/apps/dashboard"
  local port=$(grep 'port:' "$PROJECTS_DIR/$project/project.yaml" | awk '{print $2}')
  npm run dev -- --port "${port:-3000}"
}

augur-daemon() {
  local project="${1:-Augur}"
  local action="${2:-status}"
  cd "$PROJECTS_DIR/$project"
  python .claude/skills/daemon/scripts/unified_daemon.py "$action"
}

augur-rebuild() {
  local project="${1:-Augur}"
  local port=$(grep 'port:' "$PROJECTS_DIR/$project/project.yaml" | awk '{print $2}')
  cd "$PROJECTS_DIR/$project"
  python .claude/skills/daemon/scripts/cleanup_processes.py --port "${port:-3000}" --force
  cd apps/dashboard && npm run build:safe
}
```

- [ ] **Step 2: Commit**

```bash
git add docs/references/shell-shortcuts.md
git commit -m "docs: add multi-project shell shortcut reference"
```

---

## Summary

| Task | What it does | Files touched |
|------|-------------|---------------|
| 1 | Add project.yaml to Project0 | `project.yaml` |
| 2 | Add get_project_name() to paths.py | `src/config/paths.py`, tests |
| 3 | Scope all external paths | `src/config/paths.py`, tests |
| 4 | Dynamic plugin discovery | `src/config/paths.py`, tests |
| 5 | Scope daemon plists and ports | `.claude/skills/daemon/scripts/*` |
| 6 | Re-tag 7 base skills | 7 SKILL.md files |
| 7 | Create augur-ops, retire augur-system | 9 SKILL.md files |
| 8 | Rebase and strip augur-os | augur-os repo |
| 9 | Test dual-clone coexistence | validation only |
| 10 | Build augur init CLI | `.claude/skills/onboard/scripts/augur_init.py`, tests |
| 11 | Document shell shortcuts | `docs/references/shell-shortcuts.md` |

**Dependency order:**
- **Phase 1 (parallel):** Tasks 1 and 2 (project.yaml + get_project_name)
- **Phase 2 (parallel, depends on Phase 1):** Tasks 3, 4, 5 (scoped paths, dynamic discovery, daemon ports — all use get_project_name/get_project_port from Task 2)
- **Phase 3 (parallel, independent):** Tasks 6, 7 (re-tag skills — frontmatter only, no code deps)
- **Phase 4 (sequential, depends on all above):** Task 8 (rebase augur-os)
- **Phase 5 (sequential, depends on 8):** Task 9 (test dual-clone)
- **Phase 6 (parallel, depends on 8):** Tasks 10, 11 (augur init + shell shortcuts)

Phase 3 can run in parallel with Phase 2.
