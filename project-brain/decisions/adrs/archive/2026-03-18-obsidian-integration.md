# Obsidian Integration (ADR-436) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce Obsidian as the first "vault" integration — VaultAdapter base class, Obsidian skill with MCP tools, defuddle scraper upgrade, and integrations in Browse page.

**Architecture:** VaultAdapter is a new parallel adapter hierarchy alongside BaseAdapter, living in `vault_adapters/`. Obsidian is the first implementation (LocalFileVaultAdapter). Defuddle replaces the scraper's naive HTMLParser. Integrations move from Settings to Browse via decentralized SKILL.md frontmatter discovery.

**Tech Stack:** Python 3.11+ (adapters, MCP tools), TypeScript/React (dashboard), defuddle (npm), ripgrep (vault search)

**Spec:** `docs/superpowers/specs/2026-03-18-obsidian-integration-design.md`

---

## File Structure

### New files

| File | Responsibility |
|---|---|
| `.claude/skills/ai_bridge/scripts/sync_agents/vault_adapters/__init__.py` | VaultAdapter ABC + LocalFileVaultAdapter, LocalAppVaultAdapter, CloudVaultAdapter |
| `.claude/skills/ai_bridge/scripts/sync_agents/vault_adapters/obsidian.py` | ObsidianVaultAdapter — Obsidian-specific vault sync |
| `.claude/skills/ai_bridge/lib/markdown_flavors.py` | Stateless markdown format conversion (plain ↔ Obsidian ↔ Logseq) |
| `.claude/skills/obsidian/SKILL.md` | Obsidian skill instructions (vault access + Obsidian markdown syntax) |
| `.claude/skills/obsidian/scripts/mcp/__init__.py` | MCP tools: obsidian-read, obsidian-write, obsidian-search, obsidian-scaffold, obsidian-status |
| `.claude/skills/scraper/package.json` | defuddle npm dependency |
| `.claude/skills/scraper/.gitignore` | Ignore node_modules for defuddle |
| `.claude/skills/ai_bridge/augur/tests/test_vault_adapter.py` | Unit tests for VaultAdapter base + ObsidianVaultAdapter |
| `.claude/skills/obsidian/augur/tests/test_obsidian_mcp.py` | Unit tests for Obsidian MCP tools |
| `.claude/skills/scraper/augur/tests/test_defuddle_extraction.py` | Unit tests for defuddle extraction |

### Modified files

| File | Change |
|---|---|
| `.claude/skills/scraper/scripts/mcp/__init__.py` (lines 261–359) | Replace `_HtmlToText` + `_fetch_page` extraction with defuddle |
| `.claude/skills/ai_bridge/scripts/sync_agents/engine.py` (after line 933) | Add `sync_vaults()` orchestration function |
| `src/mcp/augur_mcp/infrastructure/browse.py` (line ~796) | Extend existing `list_integrations_impl` to discover vault adapters via frontmatter |

### Deleted files

| File | Reason |
|---|---|
| `apps/dashboard/app/settings/integrations/page.tsx` | Replaced by Browse integrations category |

---

## Task 1: VaultAdapter Base Class Hierarchy

**Files:**
- Create: `.claude/skills/ai_bridge/scripts/sync_agents/vault_adapters/__init__.py`
- Test: `.claude/skills/ai_bridge/augur/tests/test_vault_adapter.py`
- Reference: `.claude/skills/ai_bridge/scripts/sync_agents/adapters/base.py` (BaseAdapter pattern)

- [ ] **Step 1: Write failing tests for VaultAdapter ABC**

```python
# .claude/skills/ai_bridge/augur/tests/test_vault_adapter.py
import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Dynamic import (follows existing test pattern in codebase)
_vault_adapters_dir = (
    Path(__file__).resolve().parent.parent.parent
    / "scripts" / "sync_agents" / "vault_adapters"
)
_spec = importlib.util.spec_from_file_location(
    "vault_adapters", _vault_adapters_dir / "__init__.py"
)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["vault_adapters"] = _mod
_spec.loader.exec_module(_mod)

VaultAdapter = _mod.VaultAdapter
LocalFileVaultAdapter = _mod.LocalFileVaultAdapter
LocalAppVaultAdapter = _mod.LocalAppVaultAdapter
CloudVaultAdapter = _mod.CloudVaultAdapter


def test_vault_adapter_is_abstract():
    """Cannot instantiate VaultAdapter directly."""
    import pytest
    with pytest.raises(TypeError):
        VaultAdapter()


def test_local_file_adapter_storage_type():
    """LocalFileVaultAdapter has correct storage_type."""
    class TestAdapter(LocalFileVaultAdapter):
        adapter_name = "test"
        content_format = "markdown"
        supports_bidirectional = True
        def detect_installed(self): return True
        def scaffold_vault(self): pass
        def read_note(self, path): return ""
        def write_note(self, path, content): pass
        def search_notes(self, query): return []
        def sync_notes(self, direction): return 0
        def sync_memory(self, direction): return 0
        def cleanup(self): pass

    adapter = TestAdapter()
    assert adapter.storage_type == "local-file"


def test_local_app_adapter_storage_type():
    """LocalAppVaultAdapter has correct storage_type."""
    class TestAdapter(LocalAppVaultAdapter):
        adapter_name = "test"
        content_format = "html"
        supports_bidirectional = True
        def detect_installed(self): return True
        def scaffold_vault(self): pass
        def read_note(self, path): return ""
        def write_note(self, path, content): pass
        def search_notes(self, query): return []
        def sync_notes(self, direction): return 0
        def sync_memory(self, direction): return 0
        def cleanup(self): pass

    adapter = TestAdapter()
    assert adapter.storage_type == "local-app"


def test_cloud_adapter_storage_type():
    """CloudVaultAdapter has correct storage_type."""
    class TestAdapter(CloudVaultAdapter):
        adapter_name = "test"
        content_format = "json-blocks"
        supports_bidirectional = False
        def detect_installed(self): return True
        def scaffold_vault(self): pass
        def read_note(self, path): return ""
        def write_note(self, path, content): pass
        def search_notes(self, query): return []
        def sync_notes(self, direction): return 0
        def sync_memory(self, direction): return 0
        def cleanup(self): pass

    adapter = TestAdapter()
    assert adapter.storage_type == "cloud-api"


def test_vault_path_uses_get_vault_dir():
    """vault_path resolves via get_vault_dir(), not hardcoded."""
    class TestAdapter(LocalFileVaultAdapter):
        adapter_name = "test"
        content_format = "markdown"
        supports_bidirectional = True
        def detect_installed(self): return True
        def scaffold_vault(self): pass
        def read_note(self, path): return ""
        def write_note(self, path, content): pass
        def search_notes(self, query): return []
        def sync_notes(self, direction): return 0
        def sync_memory(self, direction): return 0
        def cleanup(self): pass

    with patch.object(_mod, "get_vault_dir", return_value=Path("/mock/vault")):
        adapter = TestAdapter()
        assert adapter.vault_path == Path("/mock/vault")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Projects/Augur && python -m pytest .claude/skills/ai_bridge/augur/tests/test_vault_adapter.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement VaultAdapter hierarchy**

```python
# .claude/skills/ai_bridge/scripts/sync_agents/vault_adapters/__init__.py
"""
VaultAdapter base class hierarchy for knowledge vault integrations.

Parallel to BaseAdapter (IDE sync), VaultAdapter handles knowledge
vault sync (notes, memory, bidirectional). Three storage tiers:
- LocalFileVaultAdapter: direct filesystem (Obsidian, Logseq)
- LocalAppVaultAdapter: CLI/AppleScript bridge (Apple Notes)
- CloudVaultAdapter: remote API (Notion)
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path

from src.config.paths import get_vault_dir

logger = logging.getLogger(__name__)


class VaultAdapter(ABC):
    """Abstract base for all vault integrations."""

    adapter_name: str
    storage_type: str  # "local-file" | "local-app" | "cloud-api"
    content_format: str  # "markdown" | "html" | "json-blocks"
    supports_bidirectional: bool

    @property
    def vault_path(self) -> Path | None:
        """Resolve vault path via get_vault_dir(). Never hardcoded."""
        try:
            return get_vault_dir()
        except Exception:
            return None

    @abstractmethod
    def detect_installed(self) -> bool:
        """Check if this vault tool is installed and configured."""
        ...

    @abstractmethod
    def scaffold_vault(self) -> None:
        """Opt-in: create vault-specific config in the Augur vault."""
        ...

    @abstractmethod
    def read_note(self, path: str) -> str:
        """Read a note from the vault by relative path."""
        ...

    @abstractmethod
    def write_note(self, path: str, content: str) -> None:
        """Write/update a note in the vault by relative path."""
        ...

    @abstractmethod
    def search_notes(self, query: str) -> list[dict]:
        """Search vault content. Returns list of {path, title, snippet}."""
        ...

    @abstractmethod
    def sync_notes(self, direction: str = "both") -> int:
        """Sync non-memory content. direction: push|pull|both. Returns count."""
        ...

    @abstractmethod
    def sync_memory(self, direction: str = "both") -> int:
        """Sync memory entries with vault-specific frontmatter. Returns count."""
        ...

    @abstractmethod
    def cleanup(self) -> None:
        """Remove all vault-specific config managed by this adapter."""
        ...


class LocalFileVaultAdapter(VaultAdapter):
    """Direct filesystem access. No app dependency."""
    storage_type = "local-file"


class LocalAppVaultAdapter(VaultAdapter):
    """CLI/AppleScript bridge. App-managed storage."""
    storage_type = "local-app"


class CloudVaultAdapter(VaultAdapter):
    """Remote API. Async. Rate-limited."""
    storage_type = "cloud-api"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Projects/Augur && python -m pytest .claude/skills/ai_bridge/augur/tests/test_vault_adapter.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/ai_bridge/scripts/sync_agents/vault_adapters/__init__.py .claude/skills/ai_bridge/augur/tests/test_vault_adapter.py
git commit -m "feat: add VaultAdapter base class hierarchy (ADR-436)"
```

---

## Task 2: markdown_flavors Utility

**Files:**
- Create: `.claude/skills/ai_bridge/lib/markdown_flavors.py`
- Test: `.claude/skills/ai_bridge/augur/tests/test_markdown_flavors.py`

- [ ] **Step 1: Write failing tests**

```python
# .claude/skills/ai_bridge/augur/tests/test_markdown_flavors.py
import importlib.util
import sys
from pathlib import Path

_lib_dir = Path(__file__).resolve().parent.parent.parent / "lib"
_spec = importlib.util.spec_from_file_location(
    "markdown_flavors", _lib_dir / "markdown_flavors.py"
)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["markdown_flavors"] = _mod
_spec.loader.exec_module(_mod)

convert = _mod.convert


def test_plain_to_obsidian_wikilinks():
    """Standard markdown links become wikilinks."""
    md = "See My Note for details."
    result = convert(md, source="plain", target="obsidian")
    assert "[[my-note|My Note]]" in result


def test_obsidian_to_plain_wikilinks():
    """Wikilinks become standard markdown links."""
    md = "See [[my-note|My Note]] for details."
    result = convert(md, source="obsidian", target="plain")
    assert "My Note" in result


def test_plain_to_plain_noop():
    """Same format returns unchanged content."""
    md = "# Hello\nSome text."
    result = convert(md, source="plain", target="plain")
    assert result == md


def test_obsidian_callout():
    """Obsidian callout syntax preserved in obsidian target."""
    md = "> [!note] Title\n> Content here"
    result = convert(md, source="obsidian", target="obsidian")
    assert "> [!note] Title" in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Projects/Augur && python -m pytest .claude/skills/ai_bridge/augur/tests/test_markdown_flavors.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement markdown_flavors**

```python
# .claude/skills/ai_bridge/lib/markdown_flavors.py
"""
Stateless markdown format conversion utility.

Converts between markdown flavors: plain, obsidian, logseq.
Used by vault adapters but not owned by them.
"""

from __future__ import annotations

import re


def convert(content: str, *, source: str = "plain", target: str = "plain") -> str:
    """Convert markdown between flavors.

    Args:
        content: Markdown string to convert.
        source: Source flavor ("plain", "obsidian", "logseq").
        target: Target flavor ("plain", "obsidian", "logseq").

    Returns:
        Converted markdown string.
    """
    if source == target:
        return content

    # Normalize to plain first, then convert to target
    normalized = _to_plain(content, source)
    return _from_plain(normalized, target)


def _to_plain(content: str, source: str) -> str:
    """Convert from a specific flavor to plain markdown."""
    if source == "plain":
        return content
    if source == "obsidian":
        return _obsidian_to_plain(content)
    return content


def _from_plain(content: str, target: str) -> str:
    """Convert from plain markdown to a specific flavor."""
    if target == "plain":
        return content
    if target == "obsidian":
        return _plain_to_obsidian(content)
    return content


def _obsidian_to_plain(content: str) -> str:
    """Convert Obsidian-flavored markdown to plain."""
    # [[target|display]] → display
    content = re.sub(
        r"\[\[([^|\]]+)\|([^\]]+)\]\]",
        r"\2",
        content,
    )
    # [[target]] → target
    content = re.sub(
        r"\[\[([^\]]+)\]\]",
        r"\1",
        content,
    )
    return content


def _plain_to_obsidian(content: str) -> str:
    """Convert plain markdown to Obsidian-flavored."""
    # display → [[target|display]]
    def _link_to_wikilink(m: re.Match) -> str:
        display = m.group(1)
        target = m.group(2)
        # Strip .md extension for wikilink
        target = re.sub(r"\.md$", "", target)
        if display == target:
            return f"[[{target}]]"
        return f"[[{target}|{display}]]"

    content = re.sub(
        r"\[([^\]]+)\]\(([^)]+\.md)\)",
        _link_to_wikilink,
        content,
    )
    return content
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Projects/Augur && python -m pytest .claude/skills/ai_bridge/augur/tests/test_markdown_flavors.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/ai_bridge/lib/markdown_flavors.py .claude/skills/ai_bridge/augur/tests/test_markdown_flavors.py
git commit -m "feat: add markdown_flavors conversion utility (ADR-436)"
```

---

## Task 3: ObsidianVaultAdapter

**Files:**
- Create: `.claude/skills/ai_bridge/scripts/sync_agents/vault_adapters/obsidian.py`
- Modify test: `.claude/skills/ai_bridge/augur/tests/test_vault_adapter.py` (add Obsidian-specific tests)
- Reference: `.claude/skills/ai_bridge/scripts/sync_agents/adapters/cursor.py` (adapter pattern)

- [ ] **Step 1: Add failing tests for ObsidianVaultAdapter**

Append to `.claude/skills/ai_bridge/augur/tests/test_vault_adapter.py`:

```python
# --- Obsidian-specific tests ---

_obs_spec = importlib.util.spec_from_file_location(
    "vault_adapters.obsidian", _vault_adapters_dir / "obsidian.py"
)
_obs_mod = importlib.util.module_from_spec(_obs_spec)
sys.modules["vault_adapters.obsidian"] = _obs_mod
_obs_spec.loader.exec_module(_obs_mod)

ObsidianVaultAdapter = _obs_mod.ObsidianVaultAdapter


def test_obsidian_adapter_name():
    adapter = ObsidianVaultAdapter()
    assert adapter.adapter_name == "obsidian"
    assert adapter.storage_type == "local-file"
    assert adapter.content_format == "markdown"
    assert adapter.supports_bidirectional is True


def test_obsidian_detect_installed_both_present():
    """Installed when Obsidian app exists AND .obsidian/ in vault."""
    with patch("platform.system", return_value="Darwin"), \
         patch("pathlib.Path.exists", return_value=True):
        adapter = ObsidianVaultAdapter()
        assert adapter.detect_installed() is True


def test_obsidian_detect_installed_no_obsidian_dir():
    """Not installed if vault has no .obsidian/ directory."""
    adapter = ObsidianVaultAdapter()
    with patch.object(type(adapter), "vault_path", new_callable=lambda: property(lambda self: Path("/mock/vault"))), \
         patch.object(Path, "exists", return_value=False):
        assert adapter.detect_installed() is False


def test_obsidian_scaffold_creates_dotobsidian():
    """scaffold_vault() creates .obsidian/ with config files."""
    adapter = ObsidianVaultAdapter()
    mock_vault = Path("/mock/vault")
    with patch.object(type(adapter), "vault_path", new_callable=lambda: property(lambda self: mock_vault)), \
         patch("pathlib.Path.mkdir") as mock_mkdir, \
         patch("builtins.open", MagicMock()):
        adapter.scaffold_vault()
        mock_mkdir.assert_called()


def test_obsidian_read_note():
    """read_note reads from vault_path / path."""
    adapter = ObsidianVaultAdapter()
    mock_vault = Path("/mock/vault")
    expected = "# Hello\nContent here."
    with patch.object(type(adapter), "vault_path", new_callable=lambda: property(lambda self: mock_vault)), \
         patch("pathlib.Path.read_text", return_value=expected):
        result = adapter.read_note("notes/hello.md")
        assert result == expected


def test_obsidian_search_notes():
    """search_notes uses ripgrep over vault dir."""
    adapter = ObsidianVaultAdapter()
    mock_vault = Path("/mock/vault")
    with patch.object(type(adapter), "vault_path", new_callable=lambda: property(lambda self: mock_vault)), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            stdout="notes/hello.md:1:# Hello world\n",
            returncode=0,
        )
        results = adapter.search_notes("Hello")
        assert len(results) >= 1
        assert results[0]["path"] == "notes/hello.md"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Projects/Augur && python -m pytest .claude/skills/ai_bridge/augur/tests/test_vault_adapter.py -v -k obsidian`
Expected: FAIL — obsidian module not found

- [ ] **Step 3: Implement ObsidianVaultAdapter**

```python
# .claude/skills/ai_bridge/scripts/sync_agents/vault_adapters/obsidian.py
"""ObsidianVaultAdapter — first LocalFileVaultAdapter implementation."""

from __future__ import annotations

import json
import logging
import platform
import subprocess
from pathlib import Path

from . import LocalFileVaultAdapter

logger = logging.getLogger(__name__)

# Default .obsidian config for scaffolding
_DEFAULT_APP_JSON = {
    "alwaysUpdateLinks": True,
    "newFileLocation": "current",
    "attachmentFolderPath": ".attachments",
}
_DEFAULT_APPEARANCE_JSON = {
    "accentColor": "",
    "theme": "obsidian",
}


class ObsidianVaultAdapter(LocalFileVaultAdapter):
    """Obsidian vault adapter. Direct filesystem read/write."""

    adapter_name = "obsidian"
    content_format = "markdown"
    supports_bidirectional = True

    def detect_installed(self) -> bool:
        """Check Obsidian app exists AND .obsidian/ is in vault (opt-in)."""
        vault = self.vault_path
        if vault is None:
            return False

        # Check .obsidian/ exists in vault (user has opted in)
        obsidian_dir = vault / ".obsidian"
        if not obsidian_dir.exists():
            return False

        # Check Obsidian app is installed (platform-aware)
        system = platform.system()
        if system == "Darwin":
            return Path("/Applications/Obsidian.app").exists() or \
                   Path.home().joinpath("Applications/Obsidian.app").exists()
        elif system == "Linux":
            # Check common Linux install paths
            return any(
                Path(p).exists()
                for p in ["/usr/bin/obsidian", "/snap/bin/obsidian"]
            )
        elif system == "Windows":
            return Path.home().joinpath(
                "AppData/Local/Obsidian/Obsidian.exe"
            ).exists()
        return False

    def scaffold_vault(self) -> None:
        """Create .obsidian/ config in the Augur vault."""
        vault = self.vault_path
        if vault is None:
            raise RuntimeError("Vault path not configured")

        obsidian_dir = vault / ".obsidian"
        obsidian_dir.mkdir(parents=True, exist_ok=True)

        # Write default config files
        _write_json(obsidian_dir / "app.json", _DEFAULT_APP_JSON)
        _write_json(obsidian_dir / "appearance.json", _DEFAULT_APPEARANCE_JSON)
        _write_json(obsidian_dir / "community-plugins.json", [])
        _write_json(obsidian_dir / "workspace.json", {"main": {"type": "empty"}})

        logger.info("Scaffolded .obsidian/ in %s", vault)

    def read_note(self, path: str) -> str:
        """Read a note from the vault by relative path."""
        vault = self.vault_path
        if vault is None:
            raise RuntimeError("Vault path not configured")
        note_path = vault / path
        return note_path.read_text(encoding="utf-8")

    def write_note(self, path: str, content: str) -> None:
        """Write/update a note in the vault by relative path."""
        vault = self.vault_path
        if vault is None:
            raise RuntimeError("Vault path not configured")
        note_path = vault / path
        note_path.parent.mkdir(parents=True, exist_ok=True)
        note_path.write_text(content, encoding="utf-8")

    def search_notes(self, query: str) -> list[dict]:
        """Search vault content using ripgrep."""
        vault = self.vault_path
        if vault is None:
            return []
        try:
            result = subprocess.run(
                ["rg", "--no-heading", "--line-number", "--glob", "*.md", query, str(vault)],
                capture_output=True, text=True, timeout=15,
            )
            matches = []
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                # Format: /path/to/file.md:linenum:content
                parts = line.split(":", 2)
                if len(parts) >= 3:
                    abs_path = parts[0]
                    rel_path = str(Path(abs_path).relative_to(vault))
                    matches.append({
                        "path": rel_path,
                        "line": int(parts[1]),
                        "snippet": parts[2].strip(),
                    })
            return matches
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return []

    def sync_notes(self, direction: str = "both") -> int:
        """Sync non-memory content. No-op for initial implementation."""
        logger.info("obsidian sync_notes(%s) — not yet implemented", direction)
        return 0

    def sync_memory(self, direction: str = "both") -> int:
        """Sync memory entries. No-op for initial implementation."""
        logger.info("obsidian sync_memory(%s) — not yet implemented", direction)
        return 0

    def cleanup(self) -> None:
        """Remove .obsidian/ from vault."""
        vault = self.vault_path
        if vault is None:
            return
        obsidian_dir = vault / ".obsidian"
        if obsidian_dir.exists():
            import shutil
            shutil.rmtree(obsidian_dir)
            logger.info("Removed .obsidian/ from %s", vault)


def _write_json(path: Path, data: dict | list) -> None:
    """Write JSON config file."""
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Projects/Augur && python -m pytest .claude/skills/ai_bridge/augur/tests/test_vault_adapter.py -v`
Expected: All tests PASS (base + obsidian)

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/ai_bridge/scripts/sync_agents/vault_adapters/obsidian.py .claude/skills/ai_bridge/augur/tests/test_vault_adapter.py
git commit -m "feat: add ObsidianVaultAdapter implementation (ADR-436)"
```

---

## Task 4: Obsidian MCP Tools

**Files:**
- Create: `.claude/skills/obsidian/scripts/mcp/__init__.py`
- Test: `.claude/skills/obsidian/augur/tests/test_obsidian_mcp.py`
- Reference: `.claude/skills/knowledge/scripts/mcp/rag_projects.py` (MCP registration pattern)

- [ ] **Step 1: Write failing tests for MCP tools**

```python
# .claude/skills/obsidian/augur/tests/test_obsidian_mcp.py
import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock
import asyncio

_mcp_dir = Path(__file__).resolve().parent.parent.parent / "scripts" / "mcp"
_spec = importlib.util.spec_from_file_location(
    "obsidian_mcp", _mcp_dir / "__init__.py"
)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["obsidian_mcp"] = _mod


def _run_async(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_module_has_register_tools():
    """Module exposes register_tools function."""
    _spec.loader.exec_module(_mod)
    assert hasattr(_mod, "register_tools")
    assert callable(_mod.register_tools)


def test_register_tools_registers_five_tools():
    """register_tools registers exactly 5 MCP tools."""
    _spec.loader.exec_module(_mod)
    mcp = MagicMock()
    registered = []
    mcp.tool = lambda **kwargs: lambda fn: (registered.append(kwargs["name"]), fn)[1]
    interceptor = lambda fn: fn
    metrics = MagicMock()

    _mod.register_tools(mcp, interceptor, metrics)

    expected = {"obsidian-read", "obsidian-write", "obsidian-search",
                "obsidian-scaffold", "obsidian-status"}
    assert set(registered) == expected
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Projects/Augur && python -m pytest .claude/skills/obsidian/augur/tests/test_obsidian_mcp.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Create directory structure and implement MCP tools**

First create directories:
```bash
mkdir -p .claude/skills/obsidian/scripts/mcp
mkdir -p .claude/skills/obsidian/augur/tests
touch .claude/skills/obsidian/scripts/__init__.py
touch .claude/skills/obsidian/scripts/mcp/__init__.py
touch .claude/skills/obsidian/augur/__init__.py
touch .claude/skills/obsidian/augur/tests/__init__.py
```

Then implement:

```python
# .claude/skills/obsidian/scripts/mcp/__init__.py
"""Obsidian vault MCP tools.

Provides: obsidian-read, obsidian-write, obsidian-search,
obsidian-scaffold, obsidian-status.
"""

from __future__ import annotations

import json
import logging
import platform
from pathlib import Path
from typing import Any, Callable

from src.config.paths import get_vault_dir

logger = logging.getLogger(__name__)


def _get_adapter():
    """Lazy import via importlib to avoid cross-skill relative import issues."""
    import importlib.util
    import sys

    if "vault_adapters.obsidian" not in sys.modules:
        adapter_path = (
            Path(__file__).resolve().parent.parent.parent.parent
            / "ai_bridge" / "scripts" / "sync_agents" / "vault_adapters" / "obsidian.py"
        )
        spec = importlib.util.spec_from_file_location("vault_adapters.obsidian", adapter_path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules["vault_adapters.obsidian"] = mod
        spec.loader.exec_module(mod)

    return sys.modules["vault_adapters.obsidian"].ObsidianVaultAdapter()


def register_tools(
    mcp: Any,
    mcp_tool_interceptor: Callable[..., Any],
    metrics: Any,
) -> None:
    """Register Obsidian vault MCP tools."""
    logger.info("Registering Obsidian MCP tools...")

    @mcp.tool(name="obsidian-read")
    @mcp_tool_interceptor
    async def obsidian_read(path: str) -> str:
        """Read a note from the Obsidian vault by relative path."""
        metrics.track_tool("obsidian_read", skill="obsidian")
        adapter = _get_adapter()
        try:
            content = adapter.read_note(path)
            return json.dumps({"path": path, "content": content}, indent=2)
        except FileNotFoundError:
            return json.dumps({"error": f"Note not found: {path}"})

    @mcp.tool(name="obsidian-write")
    @mcp_tool_interceptor
    async def obsidian_write(path: str, content: str) -> str:
        """Write or update a note in the Obsidian vault."""
        metrics.track_tool("obsidian_write", skill="obsidian")
        adapter = _get_adapter()
        adapter.write_note(path, content)
        return json.dumps({"path": path, "status": "written"})

    @mcp.tool(name="obsidian-search")
    @mcp_tool_interceptor
    async def obsidian_search(query: str, max_results: int = 20) -> str:
        """Search vault content by keyword (full-text via ripgrep)."""
        metrics.track_tool("obsidian_search", skill="obsidian")
        adapter = _get_adapter()
        results = adapter.search_notes(query)
        return json.dumps({"query": query, "results": results[:max_results]}, indent=2)

    @mcp.tool(name="obsidian-scaffold")
    @mcp_tool_interceptor
    async def obsidian_scaffold() -> str:
        """Opt-in: add .obsidian/ config to the Augur vault."""
        metrics.track_tool("obsidian_scaffold", skill="obsidian")
        adapter = _get_adapter()
        adapter.scaffold_vault()
        vault = adapter.vault_path
        return json.dumps({
            "status": "scaffolded",
            "vault_path": str(vault),
            "message": f".obsidian/ created in {vault}. Open this directory in Obsidian.",
        })

    @mcp.tool(name="obsidian-status")
    @mcp_tool_interceptor
    async def obsidian_status() -> str:
        """Check Obsidian installation status and vault configuration."""
        metrics.track_tool("obsidian_status", skill="obsidian")
        adapter = _get_adapter()
        vault = adapter.vault_path
        installed = adapter.detect_installed()
        has_obsidian_dir = (vault / ".obsidian").exists() if vault else False
        return json.dumps({
            "vault_path": str(vault) if vault else None,
            "obsidian_installed": installed,
            "vault_scaffolded": has_obsidian_dir,
            "adapter_name": adapter.adapter_name,
            "storage_type": adapter.storage_type,
        }, indent=2)

    logger.info("Obsidian MCP tools registered successfully")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Projects/Augur && python -m pytest .claude/skills/obsidian/augur/tests/test_obsidian_mcp.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/obsidian/
git commit -m "feat: add Obsidian MCP tools (ADR-436)"
```

---

## Task 5: Obsidian SKILL.md

**Files:**
- Create: `.claude/skills/obsidian/SKILL.md`

- [ ] **Step 1: Write SKILL.md with frontmatter and instructions**

```markdown
---
name: obsidian
description: Obsidian vault integration — read, write, search notes in the Augur vault using Obsidian-flavored markdown
x-augur-master: claude-code
x-augur-hub: admin
x-augur-integration-type: vault
x-augur-integration-storage: local-file
x-augur-integration-capabilities: [vault_read, vault_write, vault_search, bidirectional_sync]
x-augur-config:
  contributions:
    tools:
      - obsidian-read
      - obsidian-write
      - obsidian-search
      - obsidian-scaffold
      - obsidian-status
---

# Obsidian

Obsidian integration for Augur's vault. The Augur vault (`get_vault_dir()`) is an Obsidian-compatible markdown vault. When Obsidian is opt-in configured via `obsidian-scaffold`, users can open it directly in Obsidian.

## Vault Access

Use MCP tools for all vault operations:
- `obsidian-status` — check vault path, installation status, and configuration
- `obsidian-read` — read a note by relative path
- `obsidian-write` — write or update a note by relative path
- `obsidian-search` — full-text search across vault (ripgrep-backed)
- `obsidian-scaffold` — opt-in: add `.obsidian/` config to vault

Always call `obsidian-status` first to resolve the vault path. Never hardcode paths.

## Obsidian Markdown Syntax

When writing notes to the vault, use Obsidian-flavored markdown:

### Wikilinks
- Internal links: `[[note-name]]` or `[[note-name|Display Text]]`
- Embeds: `![[note-name]]` (embeds content inline)
- Heading links: `[[note-name#Heading]]`

### Properties (Frontmatter)
```yaml
---
title: Note Title
tags: [tag1, tag2]
created: 2026-03-18
---
```

### Callouts
```markdown
> [!note] Title
> Callout content here.

> [!warning] Warning Title
> Warning content.
```

Callout types: note, abstract, info, tip, success, question, warning, failure, danger, bug, example, quote.

### Tags
- Inline: `#tag-name`
- Nested: `#parent/child`
- In frontmatter: `tags: [tag1, tag2]`
```

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/obsidian/SKILL.md
git commit -m "feat: add Obsidian SKILL.md with frontmatter (ADR-436)"
```

---

## Task 6: Defuddle Integration into Scraper

**Files:**
- Create: `.claude/skills/scraper/package.json`
- Modify: `.claude/skills/scraper/scripts/mcp/__init__.py` (lines 261–359)
- Test: `.claude/skills/scraper/augur/tests/test_defuddle_extraction.py`

- [ ] **Step 1: Create scraper package.json with defuddle dependency**

```json
{
  "name": "@augur/scraper",
  "private": true,
  "dependencies": {
    "defuddle": "^1.0.0"
  }
}
```

- [ ] **Step 2: Create .gitignore for scraper**

```
# .claude/skills/scraper/.gitignore
node_modules/
```

- [ ] **Step 3: Install defuddle and verify CLI works**

```bash
cd .claude/skills/scraper && npm install && echo '<html><head><title>Test</title></head><body><p>Hello</p></body></html>' | node_modules/.bin/defuddle --format markdown
```
Expected: JSON output with `metadata.title` and `markdown` fields. If the CLI interface differs, adjust `_extract_content()` accordingly.

- [ ] **Step 4: Write failing tests for defuddle extraction**

```python
# .claude/skills/scraper/augur/tests/test_defuddle_extraction.py
import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

_mcp_dir = Path(__file__).resolve().parent.parent.parent / "scripts" / "mcp"
_spec = importlib.util.spec_from_file_location("scraper_mcp", _mcp_dir / "__init__.py")
_mod = importlib.util.module_from_spec(_spec)
sys.modules["scraper_mcp"] = _mod
_spec.loader.exec_module(_mod)


def test_extract_content_calls_defuddle_binary():
    """_extract_content invokes defuddle binary, not npx."""
    html = "<html><body><p>Hello world</p></body></html>"
    defuddle_output = json.dumps({
        "markdown": "Hello world",
        "metadata": {
            "title": "Test Page",
            "author": "Author",
            "date": "2026-03-18",
            "description": "A test page",
            "wordCount": 2,
        },
    })
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            stdout=defuddle_output, returncode=0
        )
        result = _mod._extract_content(html, "https://example.com")
        # Verify defuddle binary called (not npx)
        call_args = mock_run.call_args[0][0]
        assert "defuddle" in str(call_args[0])
        assert "npx" not in str(call_args[0])
        assert result["title"] == "Test Page"
        assert result["content"] == "Hello world"
        assert result["author"] == "Author"


def test_extract_content_fallback_on_failure():
    """Falls back to HTMLParser when defuddle fails."""
    html = "<html><head><title>Fallback</title></head><body><p>Content</p></body></html>"
    with patch("subprocess.run", side_effect=Exception("defuddle not found")):
        result = _mod._extract_content(html, "https://example.com")
        assert result["title"] == "Fallback"
        assert "Content" in result["content"]
```

- [ ] **Step 5: Run tests to verify they fail**

Run: `cd ~/Projects/Augur && python -m pytest .claude/skills/scraper/augur/tests/test_defuddle_extraction.py -v`
Expected: FAIL — `_extract_content` not found

- [ ] **Step 6: Modify scraper to add `_extract_content` with defuddle**

In `.claude/skills/scraper/scripts/mcp/__init__.py`, add the new extraction function and modify `_fetch_page` to use it. The key changes:

1. Add `_extract_content()` function after `_HtmlToText` class (around line 291):

```python
def _extract_content(html: str, url: str) -> dict:
    """Extract clean content from HTML using defuddle, with HTMLParser fallback."""
    try:
        skill_dir = Path(__file__).resolve().parent.parent.parent
        defuddle_bin = skill_dir / "node_modules" / ".bin" / "defuddle"
        if not defuddle_bin.exists():
            raise FileNotFoundError(f"defuddle not found at {defuddle_bin}")
        result = subprocess.run(
            [str(defuddle_bin), "--format", "markdown"],
            input=html, capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            raise RuntimeError(f"defuddle exited {result.returncode}: {result.stderr}")
        parsed = json.loads(result.stdout)
        return {
            "title": parsed.get("metadata", {}).get("title", ""),
            "author": parsed.get("metadata", {}).get("author"),
            "date": parsed.get("metadata", {}).get("date"),
            "description": parsed.get("metadata", {}).get("description"),
            "word_count": parsed.get("metadata", {}).get("wordCount"),
            "content": parsed.get("markdown", ""),
        }
    except Exception as e:
        logger.warning("defuddle failed (%s), falling back to HTMLParser", e)
        # Fallback: existing HTMLParser extraction
        parser = _HtmlToText()
        parser.feed(html)
        text = "\n".join(parser.parts)
        return {
            "title": "".join(parser.title) if parser.title else "",
            "author": None,
            "date": None,
            "description": None,
            "word_count": len(text.split()),
            "content": text,
        }
```

2. Update `_fetch_page()` (around line 330) to call `_extract_content()` instead of directly using `_HtmlToText`:

Replace the `_HtmlToText` usage block with:
```python
extracted = _extract_content(raw_html, url)
title = extracted["title"]
markdown = extracted["content"]
text = extracted["content"]  # defuddle markdown serves as both; HTMLParser fallback also returns text
```

Add `import subprocess` at the top if not already present.

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd ~/Projects/Augur && python -m pytest .claude/skills/scraper/augur/tests/test_defuddle_extraction.py -v`
Expected: All tests PASS

- [ ] **Step 8: Commit**

```bash
git add .claude/skills/scraper/package.json .claude/skills/scraper/package-lock.json .claude/skills/scraper/.gitignore .claude/skills/scraper/scripts/mcp/__init__.py .claude/skills/scraper/augur/tests/test_defuddle_extraction.py
git commit -m "feat: integrate defuddle into scraper extraction (ADR-436)"
```

---

## Task 7: sync_vaults() in Engine

**Files:**
- Modify: `.claude/skills/ai_bridge/scripts/sync_agents/engine.py` (add after `sync_all()`)
- Test: `.claude/skills/ai_bridge/augur/tests/test_vault_adapter.py` (add engine integration tests)

- [ ] **Step 1: Add failing test for sync_vaults()**

Append to `.claude/skills/ai_bridge/augur/tests/test_vault_adapter.py`:

```python
# --- Engine integration tests ---

_engine_spec = importlib.util.spec_from_file_location(
    "sync_engine", _vault_adapters_dir.parent / "engine.py"
)


def test_sync_vaults_discovers_and_calls_adapters():
    """sync_vaults() discovers vault adapters and calls sync methods."""
    mock_adapter = MagicMock()
    mock_adapter.adapter_name = "obsidian"
    mock_adapter.detect_installed.return_value = True
    mock_adapter.sync_notes.return_value = 5
    mock_adapter.sync_memory.return_value = 3

    with patch("importlib.import_module") as mock_import, \
         patch("pkgutil.iter_modules", return_value=[("", "obsidian", False)]):
        mock_module = MagicMock()
        mock_module.ObsidianVaultAdapter.return_value = mock_adapter
        mock_import.return_value = mock_module

        # Verify adapter files exist for discovery
        assert (_vault_adapters_dir / "obsidian.py").exists()
        assert (_vault_adapters_dir / "__init__.py").exists()
```

- [ ] **Step 2: Implement sync_vaults() in engine.py**

Add after the `sync_all()` function (around line 933) in `.claude/skills/ai_bridge/scripts/sync_agents/engine.py`:

```python
def sync_vaults(*, dry_run: bool = False) -> dict:
    """Orchestrate vault adapter sync. Separate from sync_all() (IDE adapters).

    Auto-discovers vault adapters from vault_adapters/ directory.
    Returns: {adapter_name: {status, notes_synced, memory_synced}}.
    """
    import importlib
    import pkgutil

    from .vault_adapters import VaultAdapter

    vault_adapters_dir = Path(__file__).parent / "vault_adapters"
    results = {}

    # Auto-discover vault adapters
    for _, module_name, _ in pkgutil.iter_modules([str(vault_adapters_dir)]):
        if module_name.startswith("_"):
            continue
        try:
            mod = importlib.import_module(f".vault_adapters.{module_name}", package=__package__)
            for attr_name in dir(mod):
                attr = getattr(mod, attr_name)
                if (isinstance(attr, type)
                    and issubclass(attr, VaultAdapter)
                    and attr is not VaultAdapter
                    and hasattr(attr, "adapter_name")):
                    adapter = attr()
                    if not adapter.detect_installed():
                        results[adapter.adapter_name] = {"status": "not_installed"}
                        continue
                    if dry_run:
                        results[adapter.adapter_name] = {"status": "dry_run"}
                        continue
                    notes = adapter.sync_notes("both")
                    memory = adapter.sync_memory("both")
                    results[adapter.adapter_name] = {
                        "status": "synced",
                        "notes_synced": notes,
                        "memory_synced": memory,
                    }
        except Exception as e:
            logger.warning("Failed to load vault adapter %s: %s", module_name, e)
            results[module_name] = {"status": "error", "error": str(e)}

    return results
```

- [ ] **Step 3: Run tests**

Run: `cd ~/Projects/Augur && python -m pytest .claude/skills/ai_bridge/augur/tests/test_vault_adapter.py -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/ai_bridge/scripts/sync_agents/engine.py .claude/skills/ai_bridge/augur/tests/test_vault_adapter.py
git commit -m "feat: add sync_vaults() orchestration to engine (ADR-436)"
```

---

## Task 8: Extend Existing list-integrations to Discover Vault Adapters

**Files:**
- Modify: `src/mcp/augur_mcp/infrastructure/browse.py` (~line 796, `list_integrations_impl`)
- Reference: `.claude/skills/ai_bridge/scripts/sync_agents/vault_adapters/` (vault adapter discovery)

> **Note:** The `list-integrations` MCP tool already exists in `browse.py`. Do NOT create a new `tools_integrations.py` — that would cause a name collision. Instead, extend the existing implementation to also discover vault adapters.

- [ ] **Step 1: Read the existing list_integrations_impl**

Read `src/mcp/augur_mcp/infrastructure/browse.py` around line 796 to understand the current implementation. It discovers IDE integrations via CLI bridge heuristics.

- [ ] **Step 2: Add vault adapter discovery to list_integrations_impl**

Extend the existing function to also scan `vault_adapters/` directory and include vault-type integrations in the response. Add after the existing IDE adapter discovery:

```python
# Discover vault adapters
import pkgutil
vault_adapters_dir = Path(__file__).resolve().parents[3] / ".claude" / "skills" / "ai_bridge" / "scripts" / "sync_agents" / "vault_adapters"
if vault_adapters_dir.exists():
    for _, module_name, _ in pkgutil.iter_modules([str(vault_adapters_dir)]):
        if module_name.startswith("_"):
            continue
        try:
            spec = importlib.util.spec_from_file_location(
                f"vault_adapters.{module_name}",
                vault_adapters_dir / f"{module_name}.py",
            )
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            for attr_name in dir(mod):
                attr = getattr(mod, attr_name)
                if (isinstance(attr, type)
                    and hasattr(attr, "adapter_name")
                    and attr_name not in ("VaultAdapter", "LocalFileVaultAdapter",
                                          "LocalAppVaultAdapter", "CloudVaultAdapter")):
                    try:
                        instance = attr()
                        installed = instance.detect_installed()
                    except Exception:
                        installed = False
                    integrations.append({
                        "name": instance.adapter_name,
                        "type": "vault",
                        "installed": installed,
                        "storage_type": getattr(instance, "storage_type", "unknown"),
                        "bidirectional": getattr(instance, "supports_bidirectional", False),
                    })
        except Exception as e:
            logger.warning("Failed to discover vault adapter %s: %s", module_name, e)
```

- [ ] **Step 3: Commit**

```bash
git add src/mcp/augur_mcp/infrastructure/browse.py
git commit -m "feat: extend list-integrations to discover vault adapters (ADR-436)"
```

---

## Task 9: Browse Page Integrations Category

**Files:**
- Modify: Browse page data source to include integrations from `list-integrations` MCP tool
- Reference: `apps/dashboard/lib/browse/types.ts` (BrowseItem, BROWSE_CATEGORIES)
- Reference: `apps/dashboard/app/api/browse/items/route.ts` (data fetching)

> **Note:** This task requires reading the current Browse page implementation to determine exact modification points. The Browse page already has a category system and an "Integrations" category may already be wired. The implementer should:

- [ ] **Step 1: Read current Browse page implementation**

Read these files to understand the current wiring:
- `apps/dashboard/lib/browse/types.ts` — check if "integrations" category exists
- `apps/dashboard/app/api/browse/items/route.ts` — check how items are fetched per category
- `apps/dashboard/app/(views)/browse/page.tsx` — check rendering

- [ ] **Step 2: Add integration items to browse API**

In the browse items API route, add a section that calls the `list-integrations` MCP tool and converts results to `BrowseItem` format:

```typescript
// In the browse items API route handler, add:
if (category === "integrations" || !category) {
  const integrationsResult = await callMcpTool("list-integrations", {});
  const parsed = JSON.parse(integrationsResult);
  for (const integration of parsed.integrations) {
    items.push({
      id: `integration-${integration.name}`,
      title: integration.name,
      description: integration.type === "vault"
        ? `${integration.storage_type} vault`
        : "IDE/CLI agent",
      hub: "admin",
      typeBadge: integration.type,
      primaryAction: { label: "View", type: "navigate", target: `/browse?filter=${integration.name}` },
      metadata: {
        installed: String(integration.installed),
        type: integration.type,
      },
    });
  }
}
```

- [ ] **Step 3: Verify integrations appear in Browse page**

Start dev server and check Browse page shows integrations:
```bash
cd ~/Projects/Augur && pnpm --filter dashboard dev
```
Navigate to `http://localhost:3000/browse` and check for integrations category.

- [ ] **Step 4: Commit**

```bash
git add apps/dashboard/
git commit -m "feat: add integrations to Browse page (ADR-436)"
```

---

## Task 10: Delete Settings Integrations Page

**Files:**
- Delete: `apps/dashboard/app/settings/integrations/page.tsx`

- [ ] **Step 1: Verify no other pages import from the integrations page**

```bash
cd ~/Projects/Augur && grep -r "settings/integrations" apps/dashboard/ --include="*.ts" --include="*.tsx" | grep -v node_modules
```

- [ ] **Step 2: Remove any navigation links to the old page**

Check sidebar/nav components for links to `/settings/integrations` and remove them.

- [ ] **Step 3: Delete the page**

```bash
rm apps/dashboard/app/settings/integrations/page.tsx
```

- [ ] **Step 4: Verify dashboard builds**

```bash
cd ~/Projects/Augur && pnpm --filter dashboard build
```
Expected: Build succeeds with no import errors.

- [ ] **Step 5: Commit**

```bash
git add -A apps/dashboard/app/settings/integrations/
git commit -m "chore: remove Settings integrations page, replaced by Browse (ADR-436)"
```

---

## Verification Checklist

After all tasks complete:

- [ ] `python -m pytest .claude/skills/ai_bridge/augur/tests/test_vault_adapter.py -v` — all pass
- [ ] `python -m pytest .claude/skills/ai_bridge/augur/tests/test_markdown_flavors.py -v` — all pass
- [ ] `python -m pytest .claude/skills/obsidian/augur/tests/test_obsidian_mcp.py -v` — all pass
- [ ] `python -m pytest .claude/skills/scraper/augur/tests/test_defuddle_extraction.py -v` — all pass
- [ ] `pnpm --filter dashboard build` — no errors
- [ ] Browse page shows integrations (both IDE and vault types)
- [ ] Settings integrations page is gone (404)
- [ ] `obsidian-status` MCP tool returns valid response
- [ ] `obsidian-scaffold` creates `.obsidian/` in vault dir
