# Codex Plugin Support & Plugin-Pack Rename Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename `cowork` to `plugin-pack`, refactor the assembler into a shared pipeline with per-target formatters, add a Codex plugin formatter, and update onboarding to support Codex plugin installation.

**Architecture:** Single `plugin_assembler.py` pipeline with `BaseFormatter` ABC, `CoworkFormatter` (extracted from existing code), and `CodexFormatter` (new). Per-target `FilterProfile` dataclasses control which skills are included. The onboarding script and a Codex bootstrap SKILL.md enable installation from Codex.

**Tech Stack:** Python 3.11+, TOML (for Codex config), JSON (manifests), pytest

---

## Important: Cowork MCP Domain is Separate

The MCP domain module `src/mcp/augur_mcp/domain/cowork.py` registers tools for Cowork task dispatch/ingestion (`sync-cowork-results`, `get-cowork-status`, `classify-collateral`). These are **runtime integration tools**, not part of the plugin assembly pipeline. They use "cowork" as a **client identity** (like "codex" or "claude-code"), not as a skill name. **Do not rename these** — "cowork" is the correct client-id for Claude Desktop's Cowork feature. The rename only affects the skill directory and assembler code.

## File Structure

### New/Moved Files

| File | Responsibility |
|------|----------------|
| `skills/plugin-pack/SKILL.md` | Skill metadata (renamed from cowork) |
| `skills/plugin-pack/scripts/plugin_assembler.py` | Shared 4-stage pipeline + CLI entry point |
| `skills/plugin-pack/scripts/formatters/__init__.py` | Formatter registry |
| `skills/plugin-pack/scripts/formatters/base.py` | `BaseFormatter` ABC |
| `skills/plugin-pack/scripts/formatters/cowork.py` | Claude Desktop formatter (extracted) |
| `skills/plugin-pack/scripts/formatters/codex.py` | Codex plugin formatter (new) |
| `skills/plugin-pack/scripts/profiles.py` | `FilterProfile` dataclass + COWORK/CODEX profiles |
| `skills/plugin-pack/assets/templates/` | Hub-specific SKILL.md templates (moved from cowork) |
| `skills/plugin-pack/evals/rank.json` | Eval config (moved from cowork) |
| `skills/plugin-pack/augur/tests/test_profiles.py` | Tests for filter profiles |
| `skills/plugin-pack/augur/tests/test_assembler.py` | Tests for shared pipeline (migrated from test_cowork_adapter.py) |
| `skills/plugin-pack/augur/tests/test_codex_formatter.py` | Tests for Codex formatter |
| `skills/plugin-pack/augur/tests/test_cowork_formatter.py` | Tests for Cowork formatter (migrated from test_cowork_mcp.py) |
| `skills/onboard/assets/codex-bootstrap/SKILL.md` | Codex bootstrap skill for onboarding |
| `skills/ai/scripts/sync_agents/adapters/plugin_pack.py` | Sync adapter (renamed from cowork.py) |

### Modified Files

| File | Change |
|------|--------|
| `scripts/install.sh` | Add Codex plugin assembly step after MCP wiring |
| `skills/onboard/references/mode-status.md` | Add Codex plugin status fields |
| `skills/ai/scripts/sync_agents/adapters/__init__.py` | Update import |
| `skills/ai/scripts/sync_agents/engine.py` | Update import |
| `CLAUDE.md` | `/cowork` -> `/plugin-pack` in slash commands |
| `AGENTS.md` | `/cowork` -> `/plugin-pack` in app list |

### Deleted Files

| File | Reason |
|------|--------|
| `skills/cowork/` (entire directory) | Renamed to `skills/plugin-pack/` |

---

### Task 1: Create Filter Profiles Module

**Files:**
- Create: `skills/plugin-pack/scripts/profiles.py`
- Test: `skills/plugin-pack/augur/tests/test_profiles.py`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p skills/plugin-pack/scripts/formatters
mkdir -p skills/plugin-pack/augur/tests
```

- [ ] **Step 2: Write the failing test for FilterProfile**

```python
# skills/plugin-pack/augur/tests/test_profiles.py
"""Tests for plugin-pack filter profiles."""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPTS_DIR = PROJECT_ROOT / "skills" / "plugin-pack" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def test_cowork_profile_has_expected_hubs():
    from profiles import COWORK_PROFILE
    assert COWORK_PROFILE.hubs == frozenset({"brain", "career", "life", "studio"})


def test_codex_profile_includes_command_hub():
    from profiles import CODEX_PROFILE
    assert "command" in CODEX_PROFILE.hubs
    assert "brain" in CODEX_PROFILE.hubs


def test_codex_profile_allows_dev_prefix():
    from profiles import CODEX_PROFILE
    assert "dev-" not in CODEX_PROFILE.excluded_prefixes


def test_cowork_profile_excludes_dev_prefix():
    from profiles import COWORK_PROFILE
    assert "dev-" in COWORK_PROFILE.excluded_prefixes


def test_both_profiles_exclude_plugin_pack():
    from profiles import COWORK_PROFILE, CODEX_PROFILE
    assert "plugin-pack" in COWORK_PROFILE.excluded_skills
    assert "plugin-pack" in CODEX_PROFILE.excluded_skills


def test_both_profiles_have_core_commands():
    from profiles import COWORK_PROFILE, CODEX_PROFILE
    for profile in [COWORK_PROFILE, CODEX_PROFILE]:
        assert "ask" in profile.commands
        assert "search" in profile.commands
        assert "save" in profile.commands


def test_get_profile_by_name():
    from profiles import get_profile
    assert get_profile("cowork").name == "cowork"
    assert get_profile("codex").name == "codex"


def test_get_profile_unknown_raises():
    from profiles import get_profile
    import pytest
    with pytest.raises(ValueError, match="Unknown target"):
        get_profile("unknown-target")
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd ~/Projects/Augur && python -m pytest skills/plugin-pack/augur/tests/test_profiles.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'profiles'`

- [ ] **Step 4: Write profiles.py**

```python
# skills/plugin-pack/scripts/profiles.py
"""Filter profiles for plugin-pack targets."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class FilterProfile:
    """Defines which skills to include for a given target platform."""

    name: str
    hubs: frozenset[str]
    excluded_prefixes: tuple[str, ...]
    excluded_skills: frozenset[str]
    commands: dict[str, dict] = field(default_factory=dict)


_CORE_COMMANDS = {
    "ask": {
        "description": "Ask your second brain any question",
        "body": "Search across all your knowledge -- notes, documents, memory, and project history -- to answer questions and find information.",
    },
    "search": {
        "description": "Search knowledge across all sources",
        "body": "Search across all indexed documents, notes, and knowledge sources. Returns relevant matches ranked by relevance.",
    },
    "save": {
        "description": "Save information to your knowledge base",
        "body": "Save files, images, PDFs, or text content to the appropriate location in your knowledge system.",
    },
}

_COMMON_EXCLUDED_SKILLS = frozenset({
    "ai", "commands", "rag", "scraper", "advisor",
    "frontend", "renderer", "page-builder", "dashboard", "daemon",
    "kill-augur", "system-cleanup", "test-client", "test-ui",
    "validator", "mcp-app-factory", "devops", "nightly",
    "reindex-project", "auto-rag-reindex", "sync-agents",
    "updater", "remote-access", "executor", "discovery", "workflows",
    "file-manager", "observe", "metrics", "enterprise", "plugin-pack",
})

COWORK_PROFILE = FilterProfile(
    name="cowork",
    hubs=frozenset({"brain", "career", "life", "studio"}),
    excluded_prefixes=("auto-", "dev-", "client-"),
    excluded_skills=_COMMON_EXCLUDED_SKILLS | {"developer", "onboard"},
    commands=_CORE_COMMANDS,
)

CODEX_PROFILE = FilterProfile(
    name="codex",
    hubs=frozenset({"brain", "career", "life", "studio", "command"}),
    excluded_prefixes=("auto-", "client-"),
    excluded_skills=_COMMON_EXCLUDED_SKILLS | {"reload-dashboard", "deploy-website"},
    commands=_CORE_COMMANDS,
)

_PROFILES = {
    "cowork": COWORK_PROFILE,
    "codex": CODEX_PROFILE,
}


def get_profile(target: str) -> FilterProfile:
    """Look up a filter profile by target name."""
    if target not in _PROFILES:
        raise ValueError(f"Unknown target: {target!r}. Available: {sorted(_PROFILES)}")
    return _PROFILES[target]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd ~/Projects/Augur && python -m pytest skills/plugin-pack/augur/tests/test_profiles.py -v`
Expected: All 8 tests PASS

- [ ] **Step 6: Commit**

```bash
git add skills/plugin-pack/scripts/profiles.py skills/plugin-pack/augur/tests/test_profiles.py
git commit -m "feat(plugin-pack): add FilterProfile dataclass and cowork/codex profiles"
```

---

### Task 2: Create BaseFormatter ABC

**Files:**
- Create: `skills/plugin-pack/scripts/formatters/__init__.py`
- Create: `skills/plugin-pack/scripts/formatters/base.py`

- [ ] **Step 1: Write `__init__.py`**

```python
# skills/plugin-pack/scripts/formatters/__init__.py
"""Plugin-pack formatters for different target platforms."""
from .base import BaseFormatter

__all__ = ["BaseFormatter"]
```

- [ ] **Step 2: Write `base.py`**

```python
# skills/plugin-pack/scripts/formatters/base.py
"""Base formatter interface for plugin assembly targets."""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class BaseFormatter(ABC):
    """Abstract base for platform-specific plugin formatters."""

    @abstractmethod
    def write_manifest(self, plugin_dir: Path, version: str) -> None:
        """Write the plugin manifest file (e.g., plugin.json)."""

    @abstractmethod
    def write_mcp_config(self, plugin_dir: Path, project_root: Path, python_path: str) -> None:
        """Write MCP server configuration."""

    @abstractmethod
    def write_marketplace(self, output_dir: Path, version: str) -> None:
        """Write marketplace discovery manifest."""

    @abstractmethod
    def write_skills(self, plugin_dir: Path, skills: dict[str, str]) -> None:
        """Write transformed SKILL.md files. skills is {name: transformed_content}."""

    @abstractmethod
    def write_commands(self, plugin_dir: Path, commands: dict[str, dict]) -> None:
        """Write command files. commands is {name: {description, body}}."""

    @abstractmethod
    def install(self, output_dir: Path, version: str) -> bool:
        """Install the assembled plugin to the target platform. Returns True on success."""
```

- [ ] **Step 3: Commit**

```bash
git add skills/plugin-pack/scripts/formatters/__init__.py skills/plugin-pack/scripts/formatters/base.py
git commit -m "feat(plugin-pack): add BaseFormatter ABC for plugin assembly targets"
```

---

### Task 3: Extract CoworkFormatter from Existing Code

**Files:**
- Create: `skills/plugin-pack/scripts/formatters/cowork.py`
- Test: `skills/plugin-pack/augur/tests/test_cowork_formatter.py`

- [ ] **Step 1: Write failing test**

```python
# skills/plugin-pack/augur/tests/test_cowork_formatter.py
"""Tests for Cowork formatter (Claude Desktop plugin output)."""
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPTS_DIR = PROJECT_ROOT / "skills" / "plugin-pack" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def test_write_manifest_creates_claude_plugin_dir(tmp_path):
    from formatters.cowork import CoworkFormatter
    fmt = CoworkFormatter()
    plugin_dir = tmp_path / "augur"
    plugin_dir.mkdir()
    fmt.write_manifest(plugin_dir, "1.0.0")

    manifest_path = plugin_dir / ".claude-plugin" / "plugin.json"
    assert manifest_path.exists()
    data = json.loads(manifest_path.read_text())
    assert data["name"] == "augur"
    assert data["version"] == "1.0.0"
    assert data["author"]["name"] == "Gur Sannikov"


def test_write_mcp_config(tmp_path):
    from formatters.cowork import CoworkFormatter
    fmt = CoworkFormatter()
    plugin_dir = tmp_path / "augur"
    plugin_dir.mkdir()
    fmt.write_mcp_config(plugin_dir, Path("/fake/root"), "/fake/python")

    mcp_path = plugin_dir / ".mcp.json"
    assert mcp_path.exists()
    data = json.loads(mcp_path.read_text())
    assert "augur" in data["mcpServers"]
    assert "cowork" in data["mcpServers"]["augur"]["args"]


def test_write_skills(tmp_path):
    from formatters.cowork import CoworkFormatter
    fmt = CoworkFormatter()
    plugin_dir = tmp_path / "augur"
    plugin_dir.mkdir()
    fmt.write_skills(plugin_dir, {
        "career": "---\nname: career\n---\n# Career\n",
        "finance": "---\nname: finance\n---\n# Finance\n",
    })
    assert (plugin_dir / "skills" / "career" / "SKILL.md").exists()
    assert (plugin_dir / "skills" / "finance" / "SKILL.md").exists()


def test_write_commands(tmp_path):
    from formatters.cowork import CoworkFormatter
    fmt = CoworkFormatter()
    plugin_dir = tmp_path / "augur"
    plugin_dir.mkdir()
    fmt.write_commands(plugin_dir, {
        "ask": {"description": "Ask a question", "body": "Ask body."},
    })
    cmd_path = plugin_dir / "commands" / "ask.md"
    assert cmd_path.exists()
    content = cmd_path.read_text()
    assert "name: ask" in content
    assert "Ask body." in content


def test_write_marketplace(tmp_path):
    from formatters.cowork import CoworkFormatter
    fmt = CoworkFormatter()
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    fmt.write_marketplace(output_dir, "1.0.0")

    mp_path = output_dir / ".claude-plugin" / "marketplace.json"
    assert mp_path.exists()
    data = json.loads(mp_path.read_text())
    assert data["name"] == "augur-cowork"
    assert len(data["plugins"]) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Projects/Augur && python -m pytest skills/plugin-pack/augur/tests/test_cowork_formatter.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'formatters'`

- [ ] **Step 3: Write CoworkFormatter**

Extract from the existing `cowork_assembler.py` (lines 130-241). The formatter receives pre-assembled data and writes it in Claude Desktop format.

```python
# skills/plugin-pack/scripts/formatters/cowork.py
"""Cowork formatter — produces Claude Desktop plugin structure."""
from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path

from .base import BaseFormatter

logger = logging.getLogger(__name__)


class CoworkFormatter(BaseFormatter):
    """Format assembled plugin for Claude Desktop (Cowork)."""

    def write_manifest(self, plugin_dir: Path, version: str) -> None:
        manifest = {
            "name": "augur",
            "description": "Your second brain -- personal knowledge, career, finance, health, and productivity powered by Augur",
            "version": version,
            "author": {"name": "Gur Sannikov"},
        }
        meta_dir = plugin_dir / ".claude-plugin"
        meta_dir.mkdir(parents=True, exist_ok=True)
        (meta_dir / "plugin.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )

    def write_mcp_config(self, plugin_dir: Path, project_root: Path, python_path: str) -> None:
        config = {
            "mcpServers": {
                "augur": {
                    "command": python_path,
                    "args": ["-m", "augur_mcp", "--client-id", "cowork"],
                    "cwd": str(project_root),
                    "env": {
                        "AUGUR_ROOT": str(project_root),
                        "PYTHONUNBUFFERED": "1",
                        "PYTHONPATH": f"{project_root}:{project_root}/src/mcp",
                    },
                }
            }
        }
        (plugin_dir / ".mcp.json").write_text(
            json.dumps(config, indent=2) + "\n", encoding="utf-8"
        )

    def write_marketplace(self, output_dir: Path, version: str) -> None:
        marketplace = {
            "$schema": "https://anthropic.com/claude-code/marketplace.schema.json",
            "name": "augur-cowork",
            "description": "Augur personal knowledge system plugins for Claude Cowork",
            "owner": {"name": "Gur Sannikov"},
            "plugins": [
                {
                    "name": "augur",
                    "description": "Your second brain -- personal knowledge, career, finance, health, and productivity powered by Augur",
                    "version": version,
                    "author": {"name": "Gur Sannikov"},
                    "source": "./plugins/augur",
                }
            ],
        }
        mp_dir = output_dir / ".claude-plugin"
        mp_dir.mkdir(parents=True, exist_ok=True)
        (mp_dir / "marketplace.json").write_text(
            json.dumps(marketplace, indent=2) + "\n", encoding="utf-8"
        )

    def write_skills(self, plugin_dir: Path, skills: dict[str, str]) -> None:
        for name, content in skills.items():
            skill_dir = plugin_dir / "skills" / name
            skill_dir.mkdir(parents=True, exist_ok=True)
            (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")

    def write_commands(self, plugin_dir: Path, commands: dict[str, dict]) -> None:
        commands_dir = plugin_dir / "commands"
        commands_dir.mkdir(parents=True, exist_ok=True)
        for name, cmd in commands.items():
            content = f"---\nname: {name}\ndescription: {cmd['description']}\n---\n\n{cmd['body']}\n"
            (commands_dir / f"{name}.md").write_text(content, encoding="utf-8")

    def install(self, output_dir: Path, version: str) -> bool:
        """Install to Claude Desktop's local-desktop-app-uploads."""
        cowork_dir = _find_cowork_plugin_dir()
        if not cowork_dir:
            logger.info("  Cowork not detected, skipping desktop install")
            return False

        uploads_dir = cowork_dir / "marketplaces" / "local-desktop-app-uploads"
        if not uploads_dir.exists():
            logger.info("  Cowork local-desktop-app-uploads not found, skipping")
            return False

        plugin_dir = output_dir / "plugins" / "augur"
        target = uploads_dir / "augur"

        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(plugin_dir, target)

        # Register in installed_plugins.json
        installed_path = cowork_dir / "installed_plugins.json"
        if installed_path.exists():
            try:
                installed = json.loads(installed_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                installed = {"version": 2, "plugins": {}}
        else:
            installed = {"version": 2, "plugins": {}}

        now = datetime.now(timezone.utc).isoformat()
        key = "augur@local-desktop-app-uploads"
        existing = installed.get("plugins", {}).get(key, [{}])
        installed["plugins"][key] = [{
            "scope": "user",
            "installPath": str(target),
            "version": version,
            "installedAt": existing[0].get("installedAt", now) if existing else now,
            "lastUpdated": now,
        }]

        installed_path.write_text(json.dumps(installed, indent=2) + "\n", encoding="utf-8")

        # Register MCP server in claude_desktop_config.json
        _register_mcp_connector(output_dir)

        logger.info("  Installed augur to Cowork desktop")
        return True


def _find_cowork_plugin_dir() -> Path | None:
    """Find Cowork's cowork_plugins directory inside Claude Desktop app data."""
    base = Path.home() / "Library" / "Application Support" / "Claude" / "local-agent-mode-sessions"
    if not base.exists():
        return None
    for session_dir in base.iterdir():
        if not session_dir.is_dir():
            continue
        for org_dir in session_dir.iterdir():
            if not org_dir.is_dir():
                continue
            candidate = org_dir / "cowork_plugins"
            if candidate.exists():
                return candidate
    return None


def _register_mcp_connector(output_dir: Path) -> None:
    """Register Augur MCP server in claude_desktop_config.json."""
    from src.config.paths import get_project_root

    project_root = Path(get_project_root())
    config_path = Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    if not config_path.exists():
        return

    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return

    venv_python = project_root / ".venv" / "bin" / "python3"
    python_path = str(venv_python) if venv_python.exists() else "python3"

    mcp_entry = {
        "command": python_path,
        "args": ["-m", "augur_mcp", "--client-id", "cowork"],
        "cwd": str(project_root),
        "env": {
            "AUGUR_ROOT": str(project_root),
            "PYTHONUNBUFFERED": "1",
            "PYTHONPATH": f"{project_root}:{project_root}/src/mcp",
        },
    }

    if "mcpServers" not in config:
        config["mcpServers"] = {}

    config["mcpServers"]["augur"] = mcp_entry
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    logger.info("  Registered Augur MCP connector in claude_desktop_config.json")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/Projects/Augur && python -m pytest skills/plugin-pack/augur/tests/test_cowork_formatter.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add skills/plugin-pack/scripts/formatters/cowork.py skills/plugin-pack/augur/tests/test_cowork_formatter.py
git commit -m "feat(plugin-pack): extract CoworkFormatter from cowork_assembler"
```

---

### Task 4: Create CodexFormatter

**Files:**
- Create: `skills/plugin-pack/scripts/formatters/codex.py`
- Test: `skills/plugin-pack/augur/tests/test_codex_formatter.py`

- [ ] **Step 1: Write failing test**

```python
# skills/plugin-pack/augur/tests/test_codex_formatter.py
"""Tests for Codex formatter (Codex plugin output)."""
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPTS_DIR = PROJECT_ROOT / "skills" / "plugin-pack" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def test_write_manifest_creates_codex_plugin_dir(tmp_path):
    from formatters.codex import CodexFormatter
    fmt = CodexFormatter()
    plugin_dir = tmp_path / "augur"
    plugin_dir.mkdir()
    fmt.write_manifest(plugin_dir, "1.0.0")

    manifest_path = plugin_dir / ".codex-plugin" / "plugin.json"
    assert manifest_path.exists()
    data = json.loads(manifest_path.read_text())
    assert data["name"] == "augur"
    assert data["version"] == "1.0.0"
    assert data["skills"] == "./skills/"
    assert data["mcpServers"] == "./.mcp.json"
    assert data["interface"]["displayName"] == "Augur"
    assert data["interface"]["category"] == "Productivity"


def test_write_mcp_config_uses_codex_client_id(tmp_path):
    from formatters.codex import CodexFormatter
    fmt = CodexFormatter()
    plugin_dir = tmp_path / "augur"
    plugin_dir.mkdir()
    fmt.write_mcp_config(plugin_dir, Path("/fake/root"), "/fake/python")

    mcp_path = plugin_dir / ".mcp.json"
    assert mcp_path.exists()
    data = json.loads(mcp_path.read_text())
    server = data["mcpServers"]["augur"]
    assert "--client-id" in server["args"]
    assert "codex" in server["args"]
    assert server["cwd"] == "/fake/root"


def test_write_skills_creates_skill_dirs(tmp_path):
    from formatters.codex import CodexFormatter
    fmt = CodexFormatter()
    plugin_dir = tmp_path / "augur"
    plugin_dir.mkdir()
    fmt.write_skills(plugin_dir, {
        "career": "---\nname: career\n---\n# Career\n",
        "dev-test": "---\nname: dev-test\n---\n# Dev Test\n",
    })
    assert (plugin_dir / "skills" / "career" / "SKILL.md").exists()
    assert (plugin_dir / "skills" / "dev-test" / "SKILL.md").exists()


def test_write_commands(tmp_path):
    from formatters.codex import CodexFormatter
    fmt = CodexFormatter()
    plugin_dir = tmp_path / "augur"
    plugin_dir.mkdir()
    fmt.write_commands(plugin_dir, {
        "ask": {"description": "Ask a question", "body": "Ask body."},
    })
    # Codex uses skills/ for commands too (they are just skills)
    cmd_path = plugin_dir / "skills" / "ask" / "SKILL.md"
    assert cmd_path.exists()


def test_write_marketplace_creates_agents_dir(tmp_path):
    from formatters.codex import CodexFormatter
    fmt = CodexFormatter()
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    fmt.write_marketplace(output_dir, "1.0.0")

    mp_path = output_dir / ".agents" / "plugins" / "marketplace.json"
    assert mp_path.exists()
    data = json.loads(mp_path.read_text())
    assert data["name"] == "augur-local"
    assert data["plugins"][0]["name"] == "augur"
    assert data["plugins"][0]["source"]["source"] == "local"
    assert data["plugins"][0]["policy"]["installation"] == "INSTALLED_BY_DEFAULT"


def test_install_to_cache(tmp_path):
    """Install should copy plugin to ~/.codex/plugins/cache/ structure."""
    from formatters.codex import CodexFormatter
    fmt = CodexFormatter()

    # Build a minimal plugin
    output_dir = tmp_path / "build"
    plugin_dir = output_dir / "plugins" / "augur"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "test.txt").write_text("test")

    # Mock home dir
    fake_home = tmp_path / "home"
    codex_cache = fake_home / ".codex" / "plugins" / "cache"
    codex_cache.mkdir(parents=True)
    agents_dir = fake_home / ".agents" / "plugins"
    agents_dir.mkdir(parents=True)

    result = fmt.install(
        output_dir,
        "1.0.0",
        cache_dir=codex_cache,
        global_marketplace_dir=agents_dir,
    )
    assert result is True

    # Check cache
    cached = codex_cache / "augur-local" / "augur" / "1.0.0" / "test.txt"
    assert cached.exists()

    # Check global marketplace
    mp = agents_dir / "marketplace.json"
    assert mp.exists()
    data = json.loads(mp.read_text())
    augur_entry = [p for p in data["plugins"] if p["name"] == "augur"]
    assert len(augur_entry) == 1


def test_install_merges_existing_marketplace(tmp_path):
    """Install should merge into existing marketplace.json, not overwrite."""
    from formatters.codex import CodexFormatter
    fmt = CodexFormatter()

    output_dir = tmp_path / "build"
    plugin_dir = output_dir / "plugins" / "augur"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "test.txt").write_text("test")

    fake_home = tmp_path / "home"
    codex_cache = fake_home / ".codex" / "plugins" / "cache"
    codex_cache.mkdir(parents=True)
    agents_dir = fake_home / ".agents" / "plugins"
    agents_dir.mkdir(parents=True)

    # Pre-existing marketplace with another plugin
    existing = {
        "name": "my-marketplace",
        "interface": {"displayName": "My Marketplace"},
        "plugins": [
            {"name": "other-plugin", "source": {"source": "local", "path": "./other"}}
        ],
    }
    (agents_dir / "marketplace.json").write_text(json.dumps(existing))

    fmt.install(output_dir, "1.0.0", cache_dir=codex_cache, global_marketplace_dir=agents_dir)

    data = json.loads((agents_dir / "marketplace.json").read_text())
    names = [p["name"] for p in data["plugins"]]
    assert "other-plugin" in names
    assert "augur" in names
    assert data["name"] == "my-marketplace"  # Preserved
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Projects/Augur && python -m pytest skills/plugin-pack/augur/tests/test_codex_formatter.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write CodexFormatter**

```python
# skills/plugin-pack/scripts/formatters/codex.py
"""Codex formatter — produces Codex plugin structure."""
from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path

from .base import BaseFormatter

logger = logging.getLogger(__name__)


class CodexFormatter(BaseFormatter):
    """Format assembled plugin for OpenAI Codex."""

    def write_manifest(self, plugin_dir: Path, version: str) -> None:
        manifest = {
            "name": "augur",
            "version": version,
            "description": "Your second brain -- personal knowledge, career, finance, health, and productivity powered by Augur",
            "author": {"name": "Gur Sannikov"},
            "skills": "./skills/",
            "mcpServers": "./.mcp.json",
            "interface": {
                "displayName": "Augur",
                "shortDescription": "Personal knowledge system & second brain",
                "category": "Productivity",
                "capabilities": ["Read", "Write"],
            },
        }
        meta_dir = plugin_dir / ".codex-plugin"
        meta_dir.mkdir(parents=True, exist_ok=True)
        (meta_dir / "plugin.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )

    def write_mcp_config(self, plugin_dir: Path, project_root: Path, python_path: str) -> None:
        config = {
            "mcpServers": {
                "augur": {
                    "command": python_path,
                    "args": ["-m", "augur_mcp", "--client-id", "codex"],
                    "cwd": str(project_root),
                    "env": {
                        "AUGUR_ROOT": str(project_root),
                        "PYTHONUNBUFFERED": "1",
                        "PYTHONPATH": f"{project_root}:{project_root}/src/mcp",
                    },
                }
            }
        }
        (plugin_dir / ".mcp.json").write_text(
            json.dumps(config, indent=2) + "\n", encoding="utf-8"
        )

    def write_marketplace(self, output_dir: Path, version: str) -> None:
        marketplace = {
            "name": "augur-local",
            "interface": {"displayName": "Augur Local"},
            "plugins": [
                {
                    "name": "augur",
                    "source": {"source": "local", "path": "./plugins/augur"},
                    "policy": {
                        "installation": "INSTALLED_BY_DEFAULT",
                        "authentication": "ON_INSTALL",
                    },
                    "category": "Productivity",
                }
            ],
        }
        mp_dir = output_dir / ".agents" / "plugins"
        mp_dir.mkdir(parents=True, exist_ok=True)
        (mp_dir / "marketplace.json").write_text(
            json.dumps(marketplace, indent=2) + "\n", encoding="utf-8"
        )

    def write_skills(self, plugin_dir: Path, skills: dict[str, str]) -> None:
        for name, content in skills.items():
            skill_dir = plugin_dir / "skills" / name
            skill_dir.mkdir(parents=True, exist_ok=True)
            (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")

    def write_commands(self, plugin_dir: Path, commands: dict[str, dict]) -> None:
        # Codex uses skills for commands — write as SKILL.md in skills/
        for name, cmd in commands.items():
            skill_dir = plugin_dir / "skills" / name
            skill_dir.mkdir(parents=True, exist_ok=True)
            content = f"---\nname: {name}\ndescription: {cmd['description']}\n---\n\n{cmd['body']}\n"
            (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")

    def install(
        self,
        output_dir: Path,
        version: str,
        *,
        cache_dir: Path | None = None,
        global_marketplace_dir: Path | None = None,
    ) -> bool:
        """Install plugin to Codex cache and write global marketplace.

        Args:
            output_dir: Build output directory containing plugins/augur/.
            version: Plugin version string.
            cache_dir: Override for ~/.codex/plugins/cache/ (for testing).
            global_marketplace_dir: Override for ~/.agents/plugins/ (for testing).

        Returns:
            True if installed successfully.
        """
        if cache_dir is None:
            cache_dir = Path.home() / ".codex" / "plugins" / "cache"
        if global_marketplace_dir is None:
            global_marketplace_dir = Path.home() / ".agents" / "plugins"

        plugin_source = output_dir / "plugins" / "augur"
        if not plugin_source.exists():
            logger.warning("Plugin source not found at %s", plugin_source)
            return False

        # Copy to cache
        cache_target = cache_dir / "augur-local" / "augur" / version
        cache_target.mkdir(parents=True, exist_ok=True)
        if cache_target.exists():
            shutil.rmtree(cache_target)
        shutil.copytree(plugin_source, cache_target)
        logger.info("  Installed augur to Codex cache: %s", cache_target)

        # Write/merge global marketplace
        global_marketplace_dir.mkdir(parents=True, exist_ok=True)
        mp_path = global_marketplace_dir / "marketplace.json"

        augur_entry = {
            "name": "augur",
            "source": {"source": "local", "path": str(cache_target)},
            "policy": {
                "installation": "INSTALLED_BY_DEFAULT",
                "authentication": "ON_INSTALL",
            },
            "category": "Productivity",
        }

        if mp_path.exists():
            try:
                existing = json.loads(mp_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                existing = None
        else:
            existing = None

        if existing and isinstance(existing.get("plugins"), list):
            # Merge: replace existing augur entry or append
            plugins = [p for p in existing["plugins"] if p.get("name") != "augur"]
            plugins.append(augur_entry)
            existing["plugins"] = plugins
            marketplace = existing
        else:
            marketplace = {
                "name": "augur-local",
                "interface": {"displayName": "Augur Local"},
                "plugins": [augur_entry],
            }

        mp_path.write_text(json.dumps(marketplace, indent=2) + "\n", encoding="utf-8")
        logger.info("  Updated global marketplace: %s", mp_path)

        return True
```

- [ ] **Step 4: Update formatters `__init__.py`**

```python
# skills/plugin-pack/scripts/formatters/__init__.py
"""Plugin-pack formatters for different target platforms."""
from .base import BaseFormatter
from .codex import CodexFormatter
from .cowork import CoworkFormatter

__all__ = ["BaseFormatter", "CodexFormatter", "CoworkFormatter"]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd ~/Projects/Augur && python -m pytest skills/plugin-pack/augur/tests/test_codex_formatter.py -v`
Expected: All 8 tests PASS

- [ ] **Step 6: Commit**

```bash
git add skills/plugin-pack/scripts/formatters/codex.py skills/plugin-pack/scripts/formatters/__init__.py skills/plugin-pack/augur/tests/test_codex_formatter.py
git commit -m "feat(plugin-pack): add CodexFormatter for Codex plugin output"
```

---

### Task 5: Write Shared Assembler Pipeline

**Files:**
- Create: `skills/plugin-pack/scripts/plugin_assembler.py`
- Test: `skills/plugin-pack/augur/tests/test_assembler.py`

- [ ] **Step 1: Write failing test**

```python
# skills/plugin-pack/augur/tests/test_assembler.py
"""Tests for shared plugin assembler pipeline."""
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPTS_DIR = PROJECT_ROOT / "skills" / "plugin-pack" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def test_should_include_skill_cowork():
    from plugin_assembler import should_include_skill
    from profiles import COWORK_PROFILE

    assert should_include_skill("career", {"x-augur-hub": "career"}, COWORK_PROFILE) is True
    assert should_include_skill("finance", {"x-augur-hub": "life"}, COWORK_PROFILE) is True
    assert should_include_skill("auto-lint", {"x-augur-hub": "command"}, COWORK_PROFILE) is False
    assert should_include_skill("dev-build", {"x-augur-hub": "command"}, COWORK_PROFILE) is False
    assert should_include_skill("ai", {"x-augur-hub": "brain"}, COWORK_PROFILE) is False


def test_should_include_skill_codex():
    from plugin_assembler import should_include_skill
    from profiles import CODEX_PROFILE

    assert should_include_skill("career", {"x-augur-hub": "career"}, CODEX_PROFILE) is True
    assert should_include_skill("dev-test", {"x-augur-hub": "command"}, CODEX_PROFILE) is True
    assert should_include_skill("dev-merge", {"x-augur-hub": "command"}, CODEX_PROFILE) is True
    assert should_include_skill("auto-lint", {"x-augur-hub": "adaptive"}, CODEX_PROFILE) is False
    assert should_include_skill("ai", {"x-augur-hub": "brain"}, CODEX_PROFILE) is False


def test_transform_skill_md():
    from plugin_assembler import transform_skill_md

    input_md = "---\nname: career\ndescription: Job search\nx-augur-hub: career\n---\n# Career\nRun `/career` to start.\n"
    result = transform_skill_md(input_md, "career", "claude-code")

    assert "name: career" in result
    assert "description: Job search" in result
    assert "x-augur-hub" not in result
    assert "AUGUR-ADAPTED-COPY" in result
    assert "`/career`" not in result


def test_assemble_cowork(tmp_path):
    from plugin_assembler import assemble

    output, version = assemble("cowork", tmp_path / "cowork-out")
    assert isinstance(version, str)
    assert (output / "plugins" / "augur" / ".claude-plugin" / "plugin.json").exists()
    assert (output / "plugins" / "augur" / ".mcp.json").exists()
    assert (output / "plugins" / "augur" / "commands" / "ask.md").exists()


def test_assemble_codex(tmp_path):
    from plugin_assembler import assemble

    output, version = assemble("codex", tmp_path / "codex-out")
    assert isinstance(version, str)
    assert (output / "plugins" / "augur" / ".codex-plugin" / "plugin.json").exists()
    assert (output / "plugins" / "augur" / ".mcp.json").exists()
    # Codex puts commands in skills/
    assert (output / "plugins" / "augur" / "skills" / "ask" / "SKILL.md").exists()

    # Verify codex manifest has interface field
    manifest = json.loads(
        (output / "plugins" / "augur" / ".codex-plugin" / "plugin.json").read_text()
    )
    assert manifest["interface"]["displayName"] == "Augur"


def test_assemble_unknown_target_raises(tmp_path):
    from plugin_assembler import assemble
    import pytest
    with pytest.raises(ValueError, match="Unknown target"):
        assemble("unknown", tmp_path / "out")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Projects/Augur && python -m pytest skills/plugin-pack/augur/tests/test_assembler.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write plugin_assembler.py**

```python
# skills/plugin-pack/scripts/plugin_assembler.py
"""Shared plugin assembler pipeline.

Assembles Augur as a plugin for different target platforms (Claude Desktop, Codex).
Each target uses a formatter + filter profile to produce platform-specific output.

Usage:
    python skills/plugin-pack/scripts/plugin_assembler.py --target codex [--install]
    python skills/plugin-pack/scripts/plugin_assembler.py --target cowork [--install]
"""
from __future__ import annotations

import logging
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from formatters import CoworkFormatter, CodexFormatter
from formatters.base import BaseFormatter
from profiles import FilterProfile, get_profile

logger = logging.getLogger(__name__)

_SKILL_ROOT = Path(__file__).resolve().parent.parent  # skills/plugin-pack/
_TEMPLATES_DIR = _SKILL_ROOT / "assets" / "templates"

_FORMATTERS: dict[str, type[BaseFormatter]] = {
    "cowork": CoworkFormatter,
    "codex": CodexFormatter,
}


def _get_project_root() -> Path:
    from src.config.paths import get_project_root
    return Path(get_project_root())


def should_include_skill(skill_name: str, metadata: dict, profile: FilterProfile) -> bool:
    """Check if a skill should be included for the given profile."""
    hub = metadata.get("x-augur-hub", "")
    if hub not in profile.hubs:
        return False
    if any(skill_name.startswith(p) for p in profile.excluded_prefixes):
        return False
    if skill_name in profile.excluded_skills:
        return False
    return True


def transform_skill_md(content: str, skill_name: str, master: str) -> str:
    """Transform a master SKILL.md to domain-oriented format."""
    import yaml as _yaml

    name = skill_name
    description = ""
    body = content

    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            try:
                fm = _yaml.safe_load(parts[1]) or {}
            except Exception:
                fm = {}
            name = fm.get("name", skill_name)
            description = fm.get("description", "")
            body = parts[2]

    # Check for template override
    template_path = _TEMPLATES_DIR / f"{skill_name}.md"
    if template_path.exists():
        body = "\n" + template_path.read_text(encoding="utf-8").strip() + "\n"
    else:
        body = re.sub(r"`/[\w-]+`", "", body)
        body = re.sub(r"Run `/[\w-]+`[^.]*\.", "", body)
        body = re.sub(r"/(?:Users|home)/[^\s]+", "", body)
        body = re.sub(r"```bash\s*\ngit\s+[^\n]+\n```", "", body)
        body = re.sub(r"```bash\s*\npytest\s+[^\n]+\n```", "", body)
        body = re.sub(r"```bash\s*\nnpm\s+run\s+test[^\n]*\n```", "", body)

    body = re.sub(r"\n{3,}", "\n\n", body).strip()

    safe_desc = description.replace("\n", " ").strip() if description else ""

    fm_dict = {"name": name}
    if safe_desc:
        fm_dict["description"] = safe_desc

    result = "---\n"
    result += _yaml.dump(fm_dict, default_flow_style=False, allow_unicode=True).rstrip("\n") + "\n"
    result += "---\n"
    result += f"<!-- AUGUR-ADAPTED-COPY source={master} -->\n\n"
    if body:
        result += body + "\n"
    return result


def get_version() -> str:
    """Get version from git tags or fallback to date-based."""
    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().lstrip("v")
    except Exception:
        pass
    return datetime.now(timezone.utc).strftime("0.%Y%m%d.0")


def discover_skills(profile: FilterProfile) -> dict[str, str]:
    """Discover and read skills matching the profile.

    Returns:
        Dict of {skill_name: raw SKILL.md content}.
    """
    import yaml as _yaml

    project_root = _get_project_root()
    skills_root = project_root / "skills"
    result = {}

    for skill_dir in sorted(skills_root.iterdir()):
        if not skill_dir.is_dir():
            continue
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue

        content = skill_md.read_text(encoding="utf-8")
        metadata = {}
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                try:
                    metadata = _yaml.safe_load(parts[1]) or {}
                except Exception:
                    pass

        skill_name = skill_dir.name
        if should_include_skill(skill_name, metadata, profile):
            result[skill_name] = content

    return result


def assemble(target: str, output_dir: Path | None = None) -> tuple[Path, str]:
    """Assemble plugin for the given target.

    Args:
        target: Target platform name ("cowork" or "codex").
        output_dir: Where to write output. Defaults to build/{target}/ under project root.

    Returns:
        Tuple of (output_dir, version).
    """
    profile = get_profile(target)

    if target not in _FORMATTERS:
        raise ValueError(f"Unknown target: {target!r}. Available: {sorted(_FORMATTERS)}")

    formatter = _FORMATTERS[target]()
    project_root = _get_project_root()

    if output_dir is None:
        output_dir = project_root / "build" / target

    version = get_version()
    plugin_dir = output_dir / "plugins" / "augur"
    plugin_dir.mkdir(parents=True, exist_ok=True)

    # Resolve python path
    venv_python = project_root / ".venv" / "bin" / "python3"
    python_path = str(venv_python) if venv_python.exists() else "python3"

    # Discover and transform skills
    raw_skills = discover_skills(profile)
    transformed = {
        name: transform_skill_md(content, name, "augur")
        for name, content in raw_skills.items()
    }

    # Write all plugin files via formatter
    formatter.write_manifest(plugin_dir, version)
    formatter.write_mcp_config(plugin_dir, project_root, python_path)
    formatter.write_skills(plugin_dir, transformed)
    formatter.write_commands(plugin_dir, profile.commands)
    formatter.write_marketplace(output_dir, version)

    logger.info("  Generated plugin v%s for %s at %s", version, target, output_dir)
    return output_dir, version


def install(target: str, output_dir: Path, version: str) -> bool:
    """Install assembled plugin to the target platform."""
    if target not in _FORMATTERS:
        raise ValueError(f"Unknown target: {target!r}")
    formatter = _FORMATTERS[target]()
    return formatter.install(output_dir, version)


# ── CLI Entry Point ─────────────────────────────────────────────────
def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Augur plugin assembler")
    parser.add_argument("--target", required=True, choices=sorted(_FORMATTERS), help="Target platform")
    parser.add_argument("--output", type=Path, default=None, help="Output directory")
    parser.add_argument("--install", action="store_true", help="Install after assembly")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    output_dir, version = assemble(args.target, args.output)
    print(f"Assembled {args.target} plugin v{version} at {output_dir}")

    if args.install:
        ok = install(args.target, output_dir, version)
        if ok:
            print(f"Installed {args.target} plugin v{version}")
        else:
            print(f"Install skipped (target not detected)")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/Projects/Augur && python -m pytest skills/plugin-pack/augur/tests/test_assembler.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add skills/plugin-pack/scripts/plugin_assembler.py skills/plugin-pack/augur/tests/test_assembler.py
git commit -m "feat(plugin-pack): add shared assembler pipeline with CLI entry point"
```

---

### Task 6: Write SKILL.md and Move Assets

**Files:**
- Create: `skills/plugin-pack/SKILL.md`
- Move: `skills/cowork/assets/templates/` -> `skills/plugin-pack/assets/templates/`
- Move: `skills/cowork/evals/rank.json` -> `skills/plugin-pack/evals/rank.json`

- [ ] **Step 1: Copy asset templates from cowork to plugin-pack**

```bash
cp -r skills/cowork/assets skills/plugin-pack/assets
cp -r skills/cowork/evals skills/plugin-pack/evals
```

- [ ] **Step 2: Write SKILL.md**

```markdown
---
name: plugin-pack
description: Assemble and install Augur as a plugin for Claude Desktop (Cowork) and OpenAI Codex
x-augur-hub: command
x-augur-tab: system
x-augur-type: integration
x-augur-tags: [claude-desktop, codex, plugin, distribution]
x-augur-visibility: app
x-augur-metadata:
  author: Augur
  version: 2.0.0
---

# Plugin Pack

Assembles Augur as a native plugin for multiple AI platforms (ADR-442, ADR-503).

## Targets

| Target | Platform | Output Format |
|--------|----------|---------------|
| `cowork` | Claude Desktop | `.claude-plugin/plugin.json` + marketplace |
| `codex` | OpenAI Codex | `.codex-plugin/plugin.json` + `.agents/plugins/marketplace.json` |

## Usage

```
/plugin-pack --target cowork          # Assemble for Claude Desktop
/plugin-pack --target codex           # Assemble for Codex
/plugin-pack --target codex --install # Assemble and install
```

## Directory Structure

```
skills/plugin-pack/
├── SKILL.md
├── scripts/
│   ├── plugin_assembler.py      # Shared assembly pipeline + CLI
│   ├── formatters/
│   │   ├── base.py              # BaseFormatter ABC
│   │   ├── cowork.py            # Claude Desktop formatter
│   │   └── codex.py             # Codex plugin formatter
���   └── profiles.py              # Per-target filter profiles
├── assets/
│   └── templates/               # Hub-specific SKILL.md overrides
└── augur/
    └── tests/
```

## Additional resources
- assets/templates/career.md
- assets/templates/finance.md
- assets/templates/google-workspace.md
- assets/templates/health.md
- assets/templates/knowledge.md
- evals/rank.json
```

- [ ] **Step 3: Commit**

```bash
git add skills/plugin-pack/SKILL.md skills/plugin-pack/assets/ skills/plugin-pack/evals/
git commit -m "feat(plugin-pack): add SKILL.md and copy asset templates from cowork"
```

---

### Task 7: Update Sync Agent Adapter

**Files:**
- Create: `skills/ai/scripts/sync_agents/adapters/plugin_pack.py`
- Modify: `skills/ai/scripts/sync_agents/adapters/__init__.py`
- Modify: `skills/ai/scripts/sync_agents/engine.py`

- [ ] **Step 1: Write plugin_pack.py adapter**

```python
# skills/ai/scripts/sync_agents/adapters/plugin_pack.py
"""Plugin-pack sync adapter (ADR-442, ADR-503).

The implementation lives in skills/plugin-pack/scripts/plugin_assembler.py.
This adapter integrates it with the sync_agents framework.
"""
from __future__ import annotations

import logging
import shutil
import sys
from pathlib import Path

from .base import BaseAdapter

logger = logging.getLogger(__name__)


class PluginPackAdapter(BaseAdapter):
    """Sync adapter for plugin-pack (Claude Desktop + Codex)."""

    adapter_name = "plugin-pack"

    def __init__(self) -> None:
        super().__init__()
        try:
            from sync_agents.constants import PROJECT_ROOT
            self._project_root = PROJECT_ROOT
        except ImportError:
            self._project_root = Path(__file__).resolve().parents[6]
        self._cowork_output = self._project_root / "build" / "cowork"
        self._codex_output = self._project_root / "build" / "codex"

    def get_managed_files(self) -> list[str]:
        return [str(self._cowork_output), str(self._codex_output)]

    def cleanup(self) -> list[str]:
        deleted = []
        for output_dir in [self._cowork_output, self._codex_output]:
            if output_dir.exists():
                shutil.rmtree(output_dir)
                deleted.append(str(output_dir))
        return deleted

    def detect_installed(self) -> bool:
        claude_config = Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
        codex_config = Path.home() / ".codex" / "config.toml"
        return claude_config.exists() or codex_config.exists()

    def sync_rules(self, content: str) -> None:
        pass

    def sync_memory(self) -> None:
        pass

    def generate_mcp_config(self) -> None:
        """Generate plugins + install for all detected targets."""
        scripts_path = str(self._project_root / "skills" / "plugin-pack" / "scripts")
        if scripts_path not in sys.path:
            sys.path.insert(0, scripts_path)

        from plugin_assembler import assemble, install

        # Always build cowork
        cowork_output, cowork_version = assemble("cowork", self._cowork_output)
        install("cowork", cowork_output, cowork_version)

        # Build codex if detected
        codex_config = Path.home() / ".codex" / "config.toml"
        if codex_config.exists():
            codex_output, codex_version = assemble("codex", self._codex_output)
            install("codex", codex_output, codex_version)
```

- [ ] **Step 2: Update `__init__.py`**

Read `skills/ai/scripts/sync_agents/adapters/__init__.py`, find the `from .cowork import CoworkAdapter` line and replace with `from .plugin_pack import PluginPackAdapter`.

- [ ] **Step 3: Update `engine.py`**

Read `skills/ai/scripts/sync_agents/engine.py`, find the conditional import of `CoworkAdapter` (around line 90) and replace with `PluginPackAdapter`.

- [ ] **Step 4: Run existing tests**

Run: `cd ~/Projects/Augur && python -m pytest skills/cowork/augur/tests/test_cowork_adapter.py::test_adapter_output_dir -v --no-header 2>&1 | head -20`

This test will break because it imports from the old path — that's expected and will be cleaned up in Task 9 when we delete `skills/cowork/`.

- [ ] **Step 5: Commit**

```bash
git add skills/ai/scripts/sync_agents/adapters/plugin_pack.py skills/ai/scripts/sync_agents/adapters/__init__.py skills/ai/scripts/sync_agents/engine.py
git commit -m "feat(plugin-pack): update sync adapter from cowork to plugin-pack"
```

---

### Task 8: Update install.sh for Codex Plugin Assembly

**Files:**
- Modify: `scripts/install.sh`

- [ ] **Step 1: Read the install.sh section around line 461**

Read `scripts/install.sh` lines 460-477 to see the exact section after MCP client configuration.

- [ ] **Step 2: Add Codex plugin assembly step**

After the existing MCP client configuration loop (line 461, after the `fi` closing the `CONFIGURE_CLIENTS` block), insert:

```bash
    # Install Codex plugin if codex was configured (ADR-503)
    if [[ "$INSTALL_FROM" == "codex" ]] || [[ "$CONFIGURE_CLIENTS" == *"codex"* ]]; then
        print_step "Assembling Codex plugin..."
        ASSEMBLER="${INSTALL_DIR}/skills/plugin-pack/scripts/plugin_assembler.py"
        if [ -f "$ASSEMBLER" ]; then
            PYTHONPATH="${INSTALL_DIR}:${INSTALL_DIR}/src/mcp:${INSTALL_DIR}/skills/plugin-pack/scripts" \
                uv run python "$ASSEMBLER" --target codex --install || print_warning "Codex plugin assembly skipped"
        fi
    fi
```

- [ ] **Step 3: Also install repo-scoped marketplace**

After the Codex plugin assembly block above, add:

```bash
    # Write repo-scoped marketplace for Augur project (ADR-503)
    if [ -d "${INSTALL_DIR}/.agents/plugins" ] || [[ "$CONFIGURE_CLIENTS" == *"codex"* ]]; then
        mkdir -p "${INSTALL_DIR}/.agents/plugins"
        PYTHONPATH="${INSTALL_DIR}:${INSTALL_DIR}/src/mcp:${INSTALL_DIR}/skills/plugin-pack/scripts" \
            uv run python -c "
import sys; sys.path.insert(0, '${INSTALL_DIR}/skills/plugin-pack/scripts')
from plugin_assembler import assemble
assemble('codex', None)  # Writes to build/codex/ which includes marketplace
" 2>/dev/null || true
    fi
```

- [ ] **Step 4: Commit**

```bash
git add scripts/install.sh
git commit -m "feat(onboard): add Codex plugin assembly to install.sh"
```

---

### Task 9: Create Codex Bootstrap SKILL.md

**Files:**
- Create: `skills/onboard/assets/codex-bootstrap/SKILL.md`

- [ ] **Step 1: Write the bootstrap skill**

```markdown
---
name: augur-bootstrap
description: Install and configure Augur as a Codex plugin
---

# Augur Bootstrap

This skill installs and configures the Augur personal knowledge system as a Codex plugin.

## Steps

1. **Check if Augur is already installed:**
   ```bash
   ls ~/Projects/Augur/src/config/paths.py 2>/dev/null && echo "INSTALLED" || echo "NOT_INSTALLED"
   ```
   If `AUGUR_ROOT` environment variable is set, check that path instead.

2. **If not installed**, clone and run the installer:
   ```bash
   git clone https://github.com/augur-os/augur-os.git ~/Projects/Augur
   cd ~/Projects/Augur && bash scripts/install.sh --from codex
   ```

3. **If installed but plugin not detected**, assemble and install the Codex plugin:
   ```bash
   cd ~/Projects/Augur
   PYTHONPATH=".:src/mcp:skills/plugin-pack/scripts" \
     python skills/plugin-pack/scripts/plugin_assembler.py --target codex --install
   ```

4. **Verify installation:**
   - Check MCP: `grep -q 'augur' ~/.codex/config.toml && echo "MCP: OK"`
   - Check plugin cache: `ls ~/.codex/plugins/cache/augur-local/augur/ 2>/dev/null && echo "Plugin: OK"`
   - Check marketplace: `cat ~/.agents/plugins/marketplace.json 2>/dev/null | grep augur && echo "Marketplace: OK"`

5. **Report status** to the user with what was installed and any issues encountered.
```

- [ ] **Step 2: Commit**

```bash
git add skills/onboard/assets/codex-bootstrap/SKILL.md
git commit -m "feat(onboard): add Codex bootstrap SKILL.md for in-Codex onboarding"
```

---

### Task 10: Update Onboard Status Mode

**Files:**
- Modify: `skills/onboard/references/mode-status.md`

- [ ] **Step 1: Add Codex plugin status fields**

Read `skills/onboard/references/mode-status.md` and add Codex rows to the status table:

```markdown
# Mode: --status

Display the current Augur installation state. Read-only, modifies nothing.

## Steps

1. **Read state file** — Load `~/Library/Application Support/Augur/state/onboard-complete.json`.
2. **Display status table**:

| Field | Source |
|-------|--------|
| Installed | Check if install dir exists |
| Install source | `install_source` from state file |
| Connected platforms | `configured_clients` from state file |
| Vault scaffolded | `vault_scaffolded` from state file |
| Dashboard status | Ping `localhost:3000` |
| MCP status | Ping `localhost:3001/health` |
| Codex MCP | Check `~/.codex/config.toml` for `[mcp_servers.augur]` |
| Codex plugin | Check `~/.codex/plugins/cache/augur-local/augur/` exists |
| Codex marketplace (global) | Check `~/.agents/plugins/marketplace.json` for augur entry |
| Codex marketplace (repo) | Check `.agents/plugins/marketplace.json` for augur entry |

If no state file exists, show "Augur has not been fully onboarded. Run `/onboard` first."
```

- [ ] **Step 2: Commit**

```bash
git add skills/onboard/references/mode-status.md
git commit -m "feat(onboard): add Codex plugin status to --status mode"
```

---

### Task 11: Delete Old Cowork Skill & Full Reference Migration

This is the most critical task. Follow CLAUDE.md rule 23 — exhaustive path migration.

**Files:**
- Delete: `skills/cowork/` (entire directory)
- Delete: `skills/ai/scripts/sync_agents/adapters/cowork.py`
- Delete: `tests/test_cowork.py`
- Modify: `CLAUDE.md` — `/cowork` -> `/plugin-pack`
- Modify: `AGENTS.md` — `/cowork` -> `/plugin-pack`
- Modify: Multiple generated/synced files

- [ ] **Step 1: Run exhaustive grep for "cowork" references**

Use **system grep** (not built-in Grep tool) per rule 23:

```bash
grep -rn 'cowork' --include='*.py' --include='*.ts' --include='*.tsx' --include='*.yaml' --include='*.yml' --include='*.json' --include='*.md' --include='*.toml' . 2>/dev/null | grep -v node_modules | grep -v .git/ | grep -v build/ | grep -v __pycache__ | wc -l
```

Also search for split-segment patterns:

```bash
grep -rn '"cowork"' --include='*.py' . 2>/dev/null | grep -v node_modules | grep -v .git/ | grep -v build/ | grep -v __pycache__
```

Record all files and line numbers. This is the migration checklist.

- [ ] **Step 2: Categorize references into rename vs keep**

References to rename (skill name):
- `skills/cowork/` paths -> `skills/plugin-pack/`
- `cowork_assembler` module name -> `plugin_assembler`
- `_COWORK_EXCLUDED_SKILLS` -> absorbed into `profiles.py`
- `CoworkAdapter` in sync adapters -> `PluginPackAdapter`
- `/cowork` slash command -> `/plugin-pack`
- `"cowork"` as a skill name in exclusion lists, registries

References to **keep** (client identity — NOT renaming):
- `--client-id cowork` (MCP client identity for Claude Desktop)
- `CLIENT_CAPABILITIES["cowork"]` (MCP context manager)
- `filter_tools_for_client("cowork", ...)` (MCP tool filtering)
- `cowork-dispatch/`, `cowork-results/` (runtime directories)
- `cowork_plugins` (Claude Desktop internal directory name)
- `"cowork"` in `prompt-adapter.ts` dispatch target type
- `"cowork"` in `output-polling.ts`
- `_has_cowork_feature()`, `dispatch_to_cowork()` (IDE bridge)
- `"augur-cowork"` marketplace name (Claude Desktop marketplace)
- `augur@augur-cowork` settings key

- [ ] **Step 3: Delete old cowork skill directory**

```bash
rm -rf skills/cowork/
rm -f skills/ai/scripts/sync_agents/adapters/cowork.py
rm -f tests/test_cowork.py
```

- [ ] **Step 4: Update CLAUDE.md**

Find `/cowork` in the App commands list and replace with `/plugin-pack`.

- [ ] **Step 5: Update AGENTS.md**

Find `/cowork` in the App commands list and replace with `/plugin-pack`.

- [ ] **Step 6: Update remaining Python references**

Update any remaining imports or path references to `skills/cowork/` or `cowork_assembler` found in step 1 that are in the "rename" category. Each file needs to be read and edited.

Common patterns to fix:
- `self._project_root / "skills" / "cowork" / "scripts"` -> `self._project_root / "skills" / "plugin-pack" / "scripts"`
- `from cowork_assembler import ...` -> `from plugin_assembler import ...`
- `"cowork"` in skill exclusion lists -> `"plugin-pack"`

- [ ] **Step 7: Update generated prompt files**

The `.claude/skills/cowork/`, `.codex/prompts/cowork.md`, `.gemini/skills/cowork/`, `.cursor/rules/cowork.md`, `.github/instructions/cowork.md`, `.opencode/skills/cowork.md` files are **auto-generated** by `sync_agents.py`. They will be regenerated on next sync. Delete them:

```bash
rm -rf .claude/skills/cowork/
rm -f .codex/prompts/cowork.md
rm -rf .gemini/skills/cowork/
rm -f .cursor/rules/cowork.md
rm -f .cursor/rules/cowork.mdc
rm -f .github/instructions/cowork.md
rm -f .github/copilot/cowork.md
rm -f .opencode/skills/cowork.md
```

Update the `.augur-generated-prompts.json` manifests in each client dir to remove the "cowork" entry.

- [ ] **Step 8: Re-run exhaustive grep**

```bash
grep -rn 'skills/cowork' --include='*.py' --include='*.ts' --include='*.yaml' --include='*.json' --include='*.md' . 2>/dev/null | grep -v node_modules | grep -v .git/ | grep -v build/ | grep -v __pycache__
```

This must return zero results. If any remain, fix them.

Also verify "keep" references are still intact:

```bash
grep -rn 'client.*cowork\|cowork.*client\|client-id.*cowork' --include='*.py' --include='*.ts' . 2>/dev/null | grep -v node_modules | grep -v .git/ | head -5
```

These should still exist.

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "refactor(plugin-pack): rename cowork to plugin-pack, delete old skill, migrate all references

BREAKING: /cowork is now /plugin-pack. No backward-compatibility aliases (rule 14).
The 'cowork' client-id for Claude Desktop MCP is unchanged — only the skill name changed."
```

---

### Task 12: Run Full Test Suite & Verify

**Files:** None (verification only)

- [ ] **Step 1: Run plugin-pack tests**

```bash
cd ~/Projects/Augur && python -m pytest skills/plugin-pack/augur/tests/ -v
```

Expected: All tests in test_profiles.py, test_assembler.py, test_cowork_formatter.py, test_codex_formatter.py PASS.

- [ ] **Step 2: Run MCP cowork domain tests (should still pass — client identity unchanged)**

```bash
cd ~/Projects/Augur && python -m pytest tests/ -k "cowork" -v
```

If any importability tests fail because the old `skills/cowork` is deleted, remove them (they were auto-generated stubs).

- [ ] **Step 3: Verify Codex plugin assembly end-to-end**

```bash
cd ~/Projects/Augur && PYTHONPATH=".:src/mcp:skills/plugin-pack/scripts" python skills/plugin-pack/scripts/plugin_assembler.py --target codex --output /tmp/codex-test
ls -la /tmp/codex-test/plugins/augur/.codex-plugin/plugin.json
cat /tmp/codex-test/plugins/augur/.codex-plugin/plugin.json
ls /tmp/codex-test/plugins/augur/skills/ | head -10
cat /tmp/codex-test/.agents/plugins/marketplace.json
```

Expected: Valid plugin structure with plugin.json, .mcp.json, skills/, and marketplace.json.

- [ ] **Step 4: Verify Cowork assembly still works**

```bash
cd ~/Projects/Augur && PYTHONPATH=".:src/mcp:skills/plugin-pack/scripts" python skills/plugin-pack/scripts/plugin_assembler.py --target cowork --output /tmp/cowork-test
ls -la /tmp/cowork-test/plugins/augur/.claude-plugin/plugin.json
```

Expected: Valid Claude Desktop plugin structure.

- [ ] **Step 5: Final grep verification**

```bash
grep -rn 'skills/cowork\|from cowork_assembler\|import cowork_assembler' --include='*.py' --include='*.ts' --include='*.yaml' --include='*.json' --include='*.md' . 2>/dev/null | grep -v node_modules | grep -v .git/ | grep -v build/ | grep -v __pycache__ | grep -v docs/superpowers/
```

Expected: Zero results (docs/superpowers/ excluded since specs/plans reference the old name historically).

- [ ] **Step 6: Commit any fixes**

If any tests failed and required fixes:

```bash
git add -A
git commit -m "fix(plugin-pack): address test failures from cowork rename"
```

---

### Task 13: Write ADR

**Files:**
- Create: ADR via `/adr write`

- [ ] **Step 1: Write ADR extending ADR-503**

Run `/adr write` with:
- Title: "Plugin-Pack: Multi-Target Plugin Assembly (Codex Support)"
- Status: accepted
- Extends: ADR-503
- Context: Codex now has a plugin system. Augur should be a first-class plugin on both Claude Desktop and Codex.
- Decision: Rename cowork to plugin-pack, shared assembler with per-target formatters, configurable filter profiles, Codex plugin output, onboarding support for Codex.
- Consequences: `/cowork` command replaced by `/plugin-pack`. No backward compatibility. Cowork MCP client-id unchanged.

- [ ] **Step 2: Commit the ADR**

```bash
git add -A
git commit -m "docs(adr): plugin-pack multi-target assembly (extends ADR-503)"
```

---

### Task 14: Write Repo-Scoped Marketplace

**Files:**
- Create: `.agents/plugins/marketplace.json`

- [ ] **Step 1: Write repo-scoped marketplace**

```json
{
  "name": "augur-local",
  "interface": {
    "displayName": "Augur Local"
  },
  "plugins": [
    {
      "name": "augur",
      "source": {
        "source": "local",
        "path": "./build/codex/plugins/augur"
      },
      "policy": {
        "installation": "INSTALLED_BY_DEFAULT",
        "authentication": "ON_INSTALL"
      },
      "category": "Productivity"
    }
  ]
}
```

- [ ] **Step 2: Commit**

```bash
git add .agents/plugins/marketplace.json
git commit -m "feat(codex): add repo-scoped marketplace.json for Codex plugin discovery"
```
