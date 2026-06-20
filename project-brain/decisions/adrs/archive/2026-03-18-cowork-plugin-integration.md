# Cowork Plugin Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate Augur into Claude Cowork as a single personal plugin via a new sync adapter, using thin-plugin + fat-MCP architecture.

**Architecture:** New `cowork.py` adapter in `sync_agents/adapters/` assembles a complete Cowork plugin package at `dist/plugins/augur-cowork/`. MCP server gets cowork-specific tool filtering via `client_surface.py` per-client branching and a new `augur-list-capabilities` tool. Skills from any master client flow through the adapter with domain-oriented SKILL.md transformation.

**Tech Stack:** Python 3.11+, existing `sync_agents` engine, Augur MCP server

**ADR:** ADR-442
**Spec:** Design spec

---

### Task 1: Add cowork client capability to MCP server

**Files:**
- Modify: `src/mcp/augur_mcp/context_manager.py:71-83`
- Test: `.claude/skills/ai_bridge/augur/tests/test_cowork_mcp.py` (new)

- [ ] **Step 1: Write failing test for cowork capability**

```python
# .claude/skills/ai_bridge/augur/tests/test_cowork_mcp.py
"""Tests for Cowork MCP integration (ADR-442)."""
import sys
from pathlib import Path

# Bootstrap imports
PROJECT_ROOT = Path(__file__).resolve().parents[5]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_cowork_client_capability():
    from src.mcp.augur_mcp.context_manager import CLIENT_CAPABILITIES, ClientCapability

    assert "cowork" in CLIENT_CAPABILITIES
    assert CLIENT_CAPABILITIES["cowork"] == ClientCapability.LIMITED
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Projects/Augur && python -m pytest .claude/skills/ai_bridge/augur/tests/test_cowork_mcp.py::test_cowork_client_capability -v`
Expected: FAIL with KeyError "cowork"

- [ ] **Step 3: Add cowork to CLIENT_CAPABILITIES**

In `src/mcp/augur_mcp/context_manager.py`, add `"cowork"` entry after the `"claude_desktop"` line (around line 81):

```python
    "claude_desktop": ClientCapability.LIMITED,
    "cowork": ClientCapability.LIMITED,
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/Projects/Augur && python -m pytest .claude/skills/ai_bridge/augur/tests/test_cowork_mcp.py::test_cowork_client_capability -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/mcp/augur_mcp/context_manager.py .claude/skills/ai_bridge/augur/tests/test_cowork_mcp.py
git commit -m "feat(mcp): add cowork client capability (ADR-442)"
```

---

### Task 2: Add cowork-specific tool filtering

**Files:**
- Modify: `src/mcp/augur_mcp/client_surface.py:18-80`
- Test: `.claude/skills/ai_bridge/augur/tests/test_cowork_mcp.py` (append)

- [ ] **Step 1: Write failing test for cowork tool filtering**

Append to `test_cowork_mcp.py`:

```python
def test_cowork_tool_filter_excludes_dev_tools():
    """Cowork filter should exclude dev/admin tools but include knowledge tools."""
    from src.mcp.augur_mcp.client_surface import filter_tools_for_client

    class FakeTool:
        def __init__(self, name):
            self.name = name

    tools = [
        FakeTool("file-read"),
        FakeTool("unified-search"),
        FakeTool("health"),
        FakeTool("augur-list-capabilities"),
        FakeTool("get-daemon-status"),  # dev tool - should be excluded
        FakeTool("verify-changes"),  # dev tool - should be excluded
        FakeTool("get-ide-history"),  # dev tool - should be excluded
    ]

    result = filter_tools_for_client("cowork", tools)
    names = {t.name for t in result}

    assert "file-read" in names
    assert "unified-search" in names
    assert "health" in names
    assert "augur-list-capabilities" in names
    assert "get-daemon-status" not in names
    assert "verify-changes" not in names
    assert "get-ide-history" not in names


def test_default_tool_filter_unchanged():
    """Non-cowork clients should still use CURATED_VISIBLE_TOOLS."""
    from src.mcp.augur_mcp.client_surface import filter_tools_for_client

    class FakeTool:
        def __init__(self, name):
            self.name = name

    tools = [FakeTool("file-read"), FakeTool("verify-changes")]
    result = filter_tools_for_client("claude_code", tools)
    names = {t.name for t in result}

    # Both should be in CURATED_VISIBLE_TOOLS
    assert "file-read" in names
    assert "verify-changes" in names
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Projects/Augur && python -m pytest .claude/skills/ai_bridge/augur/tests/test_cowork_mcp.py -k "cowork_tool_filter or default_tool_filter" -v`
Expected: FAIL (cowork branch doesn't exist yet)

- [ ] **Step 3: Add COWORK_VISIBLE_TOOLS and per-client branching**

In `src/mcp/augur_mcp/client_surface.py`, add the cowork tool set after `CURATED_VISIBLE_TOOLS` (around line 64):

```python
COWORK_VISIBLE_TOOLS: frozenset[str] = frozenset({
    # Knowledge & search
    "file-read", "file-write", "file-list", "file-search", "file-info",
    "file-read-multi", "file-write-binary", "file-move", "file-edit",
    "unified-search", "search-skill-knowledge",
    "knowledge-summarize-file", "knowledge-summarize-url",
    "knowledge-project-index-rebuild",
    # Capabilities discovery
    "augur-list-capabilities",
    "health", "get-config", "get-system-health",
    "list-skills", "get-skill", "find-skill",
    # Existing cowork domain tools
    "sync-cowork-results", "get-cowork-status",
    # Skill discovery
    "load-module", "load-reference",
    "get-focused-tools", "get-context",
    "run-intelligence-prompt",
    "skill-action", "cross-skill",
})
```

Then modify `filter_tools_for_client()` (around line 79) to branch on client:

```python
def filter_tools_for_client(client: str | None, tools: Iterable[T]) -> list[T]:
    """Filter tools for client discovery surface."""
    if client == "cowork":
        return [tool for tool in tools if getattr(tool, "name", None) in COWORK_VISIBLE_TOOLS]
    return [tool for tool in tools if getattr(tool, "name", None) in CURATED_VISIBLE_TOOLS]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Projects/Augur && python -m pytest .claude/skills/ai_bridge/augur/tests/test_cowork_mcp.py -k "cowork_tool_filter or default_tool_filter" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/mcp/augur_mcp/client_surface.py .claude/skills/ai_bridge/augur/tests/test_cowork_mcp.py
git commit -m "feat(mcp): add cowork-specific tool filtering (ADR-442)"
```

---

### Task 3: Register augur-list-capabilities MCP tool

**Files:**
- Create: `src/mcp/augur_mcp/tools/hubs/capabilities.py`
- Test: `.claude/skills/ai_bridge/augur/tests/test_cowork_mcp.py` (append)

- [ ] **Step 1: Write failing test for capabilities tool**

Append to `test_cowork_mcp.py`:

```python
def test_list_capabilities_returns_domains():
    """augur-list-capabilities should return domain list with tool counts."""
    from src.mcp.augur_mcp.tools.hubs.capabilities import _build_capabilities_response

    result = _build_capabilities_response(client="cowork")

    assert "domains" in result
    assert "total_tools" in result
    assert "client" in result
    assert result["client"] == "cowork"
    assert isinstance(result["domains"], list)
    # Should have at least some domains
    assert len(result["domains"]) > 0
    # Each domain should have required fields
    for domain in result["domains"]:
        assert "name" in domain
        assert "description" in domain
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Projects/Augur && python -m pytest .claude/skills/ai_bridge/augur/tests/test_cowork_mcp.py::test_list_capabilities_returns_domains -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Create capabilities tool module**

```python
# src/mcp/augur_mcp/tools/hubs/capabilities.py
"""Augur capabilities discovery tool (ADR-442).

Returns currently enabled domains and their tool counts.
Used by Cowork Claude to understand what's available at conversation start.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server import Server

logger = logging.getLogger(__name__)

# Domain definitions — maps skill hub to user-facing domain description
_DOMAIN_DEFS: dict[str, str] = {
    "knowledge": "Personal knowledge retrieval, memory, and search",
    "career": "Job search, interviews, coaching, and LinkedIn",
    "finance": "Personal finance, investment, and wealth planning",
    "health": "Health tracking and medical information",
    "content": "Content creation, blog posts, and social media",
    "productivity": "Task prioritization, reading lists, and organization",
    "google-workspace": "Gmail, Calendar, Drive, Docs, Sheets, and Tasks",
    "apple": "Notes, Reminders, Calendar, and macOS automation",
    "channels": "Notifications via Telegram, macOS, and Dashboard",
    "clients": "Client management and consulting",
}


def _build_capabilities_response(client: str = "cowork") -> dict:
    """Build capabilities response without MCP dependency (testable)."""
    domains = []
    for name, description in sorted(_DOMAIN_DEFS.items()):
        domains.append({
            "name": name,
            "description": description,
        })

    return {
        "domains": domains,
        "total_tools": len(domains),  # Approximate
        "client": client,
    }


def register_tools(mcp: "Server", interceptor=None, metrics=None) -> None:
    """Register augur-list-capabilities tool."""

    @mcp.tool(name="augur-list-capabilities")
    async def list_capabilities() -> dict:
        """List available Augur capability domains.

        Returns the currently enabled domains and their descriptions.
        Call this early in conversation to understand what Augur can help with.
        """
        return _build_capabilities_response()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/Projects/Augur && python -m pytest .claude/skills/ai_bridge/augur/tests/test_cowork_mcp.py::test_list_capabilities_returns_domains -v`
Expected: PASS

- [ ] **Step 5: Wire tool registration into MCP server**

The tool module must be imported during server startup. Find where other hub tools are registered (check `src/mcp/augur_mcp/tools/hubs/__init__.py` or `src/mcp/augur_mcp/server.py` for the registration loop) and add:

```python
from .hubs.capabilities import register_tools as register_capabilities_tools
# ... in the registration block:
register_capabilities_tools(mcp, interceptor, metrics)
```

If `tools/hubs/__init__.py` auto-discovers modules, verify `capabilities.py` follows the naming convention. Otherwise, add the explicit import.

- [ ] **Step 6: Commit**

```bash
git add src/mcp/augur_mcp/tools/hubs/capabilities.py .claude/skills/ai_bridge/augur/tests/test_cowork_mcp.py
git commit -m "feat(mcp): add augur-list-capabilities tool (ADR-442)"
```

---

### Task 4: Create cowork sync adapter

**Files:**
- Create: `.claude/skills/ai_bridge/scripts/sync_agents/adapters/cowork.py`
- Test: `.claude/skills/ai_bridge/augur/tests/test_cowork_adapter.py` (new)

This is the main task. The adapter discovers user-facing skills from all master clients, transforms SKILL.md files to domain-oriented format, and assembles a complete Cowork plugin package.

- [ ] **Step 1: Write failing tests for skill filtering**

```python
# .claude/skills/ai_bridge/augur/tests/test_cowork_adapter.py
"""Tests for Cowork sync adapter (ADR-442)."""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[5]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_skill_should_include_user_facing():
    from sync_agents.adapters.cowork import _should_include_skill

    # User-facing skills should be included
    assert _should_include_skill("career", {"x-augur-hub": "career"}) is True
    assert _should_include_skill("finance", {"x-augur-hub": "life"}) is True
    assert _should_include_skill("knowledge", {"x-augur-hub": "brain"}) is True
    assert _should_include_skill("content", {"x-augur-hub": "studio"}) is True


def test_skill_should_exclude_dev_and_auto():
    from sync_agents.adapters.cowork import _should_include_skill

    # Dev/auto prefixed skills should be excluded
    assert _should_include_skill("auto-lint", {"x-augur-hub": "command"}) is False
    assert _should_include_skill("dev-build", {"x-augur-hub": "command"}) is False
    assert _should_include_skill("client-hub", {"x-augur-hub": "hidden"}) is False


def test_skill_should_exclude_infra():
    from sync_agents.adapters.cowork import _should_include_skill

    # Infrastructure skills excluded even if hub matches
    assert _should_include_skill("ai_bridge", {"x-augur-hub": "brain"}) is False
    assert _should_include_skill("renderer", {"x-augur-hub": "brain"}) is False
    assert _should_include_skill("daemon", {"x-augur-hub": "admin"}) is False


def test_skill_should_exclude_wrong_hub():
    from sync_agents.adapters.cowork import _should_include_skill

    assert _should_include_skill("some-skill", {"x-augur-hub": "command"}) is False
    assert _should_include_skill("some-skill", {"x-augur-hub": "admin"}) is False
    assert _should_include_skill("some-skill", {"x-augur-hub": "hidden"}) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Projects/Augur && python -m pytest .claude/skills/ai_bridge/augur/tests/test_cowork_adapter.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Write failing tests for SKILL.md transformation**

Append to `test_cowork_adapter.py`:

```python
def test_transform_skill_md_strips_augur_frontmatter():
    from sync_agents.adapters.cowork import _transform_skill_md

    input_md = """---
name: career
description: Manage job search pipeline
x-augur-hub: career
x-augur-master: claude-code
x-augur-mcp-tools:
  - career-pipeline-list
x-augur-plugin: augur-career
---
# Career
Run `/career` to manage your pipeline.
"""
    result = _transform_skill_md(input_md, "career", "claude-code")

    # Should keep name and description
    assert "name: career" in result
    assert "description: Manage job search pipeline" in result
    # Should strip x-augur-* fields
    assert "x-augur-hub" not in result
    assert "x-augur-master" not in result
    assert "x-augur-mcp-tools" not in result
    assert "x-augur-plugin" not in result
    # Should have AUGUR-ADAPTED-COPY marker
    assert "AUGUR-ADAPTED-COPY" in result
    assert "source=claude-code" in result
    # Should strip slash command references
    assert "`/career`" not in result


def test_transform_skill_md_removes_absolute_paths():
    from sync_agents.adapters.cowork import _transform_skill_md

    input_md = """---
name: test
description: Test skill
---
# Test
See /Users/someone/Projects/Augur/config for details.
Run `python3 /Users/someone/Projects/Augur/scripts/do.py`.
"""
    result = _transform_skill_md(input_md, "test", "claude-code")

    assert "/Users/" not in result
```

- [ ] **Step 4: Write failing test for plugin assembly**

Append to `test_cowork_adapter.py`:

```python
import json
import tempfile


def test_generate_plugin_json():
    from sync_agents.adapters.cowork import _generate_plugin_json

    result = json.loads(_generate_plugin_json())

    assert result["name"] == "augur"
    assert "second brain" in result["description"].lower() or "augur" in result["description"].lower()
    assert "version" in result
    assert result["author"]["name"] == "Gur Sannikov"


def test_generate_mcp_json():
    from sync_agents.adapters.cowork import _generate_mcp_json

    result = json.loads(_generate_mcp_json("/fake/root", "/fake/python"))

    assert "mcpServers" in result
    assert "augur" in result["mcpServers"]
    server = result["mcpServers"]["augur"]
    assert "--client-id" in server["args"]
    assert "cowork" in server["args"]
    assert server["cwd"] == "/fake/root"
```

- [ ] **Step 5: Create the cowork adapter**

```python
# .claude/skills/ai_bridge/scripts/sync_agents/adapters/cowork.py
"""Cowork sync adapter (ADR-442).

Assembles Augur as a single Claude Cowork personal plugin.
Discovers user-facing skills from all master clients via x-augur-master,
transforms SKILL.md to domain-oriented format, and generates plugin package.
"""
from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from .base import BaseAdapter

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Hubs that contain user-facing skills for Cowork
_COWORK_HUBS = frozenset({"brain", "career", "life", "studio"})

# Prefixes that always exclude a skill
_EXCLUDED_PREFIXES = ("auto-", "dev-", "client-")

# Infrastructure skills excluded even if hub matches
_COWORK_EXCLUDED_SKILLS = frozenset({
    "ai_bridge", "commands", "rag", "scraper", "advisor", "developer",
    "frontend", "renderer", "page-builder", "dashboard", "daemon",
    "ops-daemon", "kill-augur", "system-cleanup", "test-client", "test-ui",
    "validator", "mcp-app-factory", "devops", "nightly", "reindex-project",
    "reindex-rag", "sync-agents", "onboard", "updater", "remote-access",
    "executor", "discovery", "workflows", "file-manager", "observe",
    "metrics", "enterprise",
})


def _should_include_skill(skill_name: str, metadata: dict) -> bool:
    """Check if a skill should be included in the Cowork plugin."""
    hub = metadata.get("x-augur-hub", "")
    if hub not in _COWORK_HUBS:
        return False
    if any(skill_name.startswith(p) for p in _EXCLUDED_PREFIXES):
        return False
    if skill_name in _COWORK_EXCLUDED_SKILLS:
        return False
    return True


_TEMPLATES_DIR = Path(__file__).parent / "cowork_templates"


def _transform_skill_md(content: str, skill_name: str, master: str) -> str:
    """Transform a master SKILL.md to Cowork domain-oriented format."""
    import yaml as _yaml

    # Parse frontmatter using yaml.safe_load (not manual parsing)
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
        # Strip slash command references
        body = re.sub(r"`/[\w-]+`", "", body)
        body = re.sub(r"Run `/[\w-]+`[^.]*\.", "", body)

        # Strip absolute paths
        body = re.sub(r"/(?:Users|home)/[^\s]+", "", body)

        # Strip dev-only code blocks
        body = re.sub(r"```bash\s*\ngit\s+[^\n]+\n```", "", body)
        body = re.sub(r"```bash\s*\npytest\s+[^\n]+\n```", "", body)
        body = re.sub(r"```bash\s*\nnpm\s+run\s+test[^\n]*\n```", "", body)

    # Clean multiple blank lines
    body = re.sub(r"\n{3,}", "\n\n", body).strip()

    # Rebuild with marker + clean frontmatter (only name + description)
    result = f"<!-- AUGUR-ADAPTED-COPY source={master} -->\n"
    result += "---\n"
    result += f"name: {name}\n"
    if description:
        result += f"description: {description}\n"
    result += "---\n\n"
    if body:
        result += body + "\n"

    return result


def _generate_plugin_json() -> str:
    """Generate .claude-plugin/plugin.json manifest."""
    # Get version from git tags
    version = "1.0.0"
    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            version = result.stdout.strip().lstrip("v")
    except Exception:
        pass

    manifest = {
        "name": "augur",
        "description": "Your second brain -- personal knowledge, career, finance, health, and productivity powered by Augur",
        "version": version,
        "author": {"name": "Gur Sannikov"},
    }
    return json.dumps(manifest, indent=2) + "\n"


def _generate_mcp_json(project_root: str, python_path: str) -> str:
    """Generate .mcp.json pointing to Augur MCP server."""
    config = {
        "mcpServers": {
            "augur": {
                "command": python_path,
                "args": ["-m", "augur_mcp", "--client-id", "cowork"],
                "cwd": project_root,
                "env": {
                    "AUGUR_ROOT": project_root,
                    "PYTHONUNBUFFERED": "1",
                    "PYTHONPATH": f"{project_root}:{project_root}/src/mcp",
                },
            }
        }
    }
    return json.dumps(config, indent=2) + "\n"


class CoworkAdapter(BaseAdapter):
    """Sync adapter for Claude Cowork (ADR-442).

    Assembles a complete Cowork plugin package at dist/plugins/augur-cowork/.
    Unlike other adapters that write skills to a directory, this one
    generates plugin.json, .mcp.json, and commands/ alongside skills/.
    """

    adapter_name = "cowork"

    def __init__(self) -> None:
        super().__init__()
        # Import here to avoid circular deps
        try:
            from sync_agents.constants import PROJECT_ROOT
            self._project_root = PROJECT_ROOT
        except ImportError:
            self._project_root = Path(__file__).resolve().parents[6]
        self._output_dir = self._project_root / "dist" / "plugins" / "augur-cowork"

    def get_managed_files(self) -> list[str]:
        return [str(self._output_dir)]

    def cleanup(self) -> list[str]:
        deleted = []
        if self._output_dir.exists():
            shutil.rmtree(self._output_dir)
            deleted.append(str(self._output_dir))
        return deleted

    def detect_installed(self) -> bool:
        config = Path.home() / "Library" / "Application Support" / "Claude" / "config.json"
        return config.exists()

    def sync_rules(self, content: str) -> None:
        # No-op: Cowork doesn't have a rules file
        pass

    def sync_skill(self, skill_name: str, source_path: Path, metadata: dict) -> int:
        if not _should_include_skill(skill_name, metadata):
            return 0

        master = metadata.get("master", "claude-code")

        # Read and transform
        skill_md = source_path / "SKILL.md"
        if not skill_md.exists():
            return 0

        content = skill_md.read_text(encoding="utf-8")
        transformed = _transform_skill_md(content, skill_name, master)

        # Write to plugin structure
        target_dir = self._output_dir / "skills" / skill_name
        target_dir.mkdir(parents=True, exist_ok=True)
        target_file = target_dir / "SKILL.md"

        # Skip if unchanged
        if target_file.exists() and target_file.read_text(encoding="utf-8") == transformed:
            return 0

        target_file.write_text(transformed, encoding="utf-8")
        logger.info(f"  Adapted skill '{skill_name}' for cowork from {master}")
        return 1

    def sync_memory(self) -> None:
        # No-op: Cowork has no memory file target
        pass

    def generate_mcp_config(self) -> None:
        """Generate .mcp.json and .claude-plugin/plugin.json."""
        self._output_dir.mkdir(parents=True, exist_ok=True)

        # Find Python
        venv_python = self._project_root / ".venv" / "bin" / "python3"
        python_path = str(venv_python) if venv_python.exists() else "python3"

        # .mcp.json
        mcp_json = _generate_mcp_json(str(self._project_root), python_path)
        (self._output_dir / ".mcp.json").write_text(mcp_json, encoding="utf-8")

        # .claude-plugin/plugin.json
        plugin_dir = self._output_dir / ".claude-plugin"
        plugin_dir.mkdir(parents=True, exist_ok=True)
        (plugin_dir / "plugin.json").write_text(
            _generate_plugin_json(), encoding="utf-8"
        )

        logger.info("  Generated .mcp.json and .claude-plugin/plugin.json for cowork")
```

- [ ] **Step 6: Run all tests to verify they pass**

Run: `cd ~/Projects/Augur && python -m pytest .claude/skills/ai_bridge/augur/tests/test_cowork_adapter.py -v`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add .claude/skills/ai_bridge/scripts/sync_agents/adapters/cowork.py .claude/skills/ai_bridge/augur/tests/test_cowork_adapter.py
git commit -m "feat(sync): create cowork adapter with skill filtering and transformation (ADR-442)"
```

---

### Task 5: Create cowork templates for key skills

**Files:**
- Create: `.claude/skills/ai_bridge/scripts/sync_agents/adapters/cowork_templates/career.md`
- Create: `.claude/skills/ai_bridge/scripts/sync_agents/adapters/cowork_templates/knowledge.md`
- Create: `.claude/skills/ai_bridge/scripts/sync_agents/adapters/cowork_templates/finance.md`
- Create: `.claude/skills/ai_bridge/scripts/sync_agents/adapters/cowork_templates/health.md`
- Create: `.claude/skills/ai_bridge/scripts/sync_agents/adapters/cowork_templates/google-workspace.md`

These templates provide richer domain-oriented instructions for key skills instead of auto-generated bodies. The adapter checks for a template override before falling back to auto-generation.

- [ ] **Step 1: Create templates directory and career template**

```markdown
<!-- career.md -->
# Career

Help the user with their job search and career development. Capabilities include:
- **Pipeline management** -- track companies, roles, application stages, and next actions
- **Company research** -- gather and summarize information about target companies
- **Interview preparation** -- mock interviews, STAR story coaching, behavioral question prep
- **Professional growth** -- learning goals, skill tracking, career planning
- **LinkedIn content** -- draft posts, optimize profile, build professional presence

Use Augur MCP tools to read and write career data. Check available tools via augur-list-capabilities if unsure what's enabled.
```

- [ ] **Step 2: Create knowledge, finance, health, google-workspace templates**

Each follows the same pattern: heading, capability bullets, Augur MCP instruction. See spec section "SKILL.md transformation rules" for content guidance.

- [ ] **Step 3: Verify template loading works**

The `_transform_skill_md()` function in `cowork.py` (Task 4) already includes template loading via `_TEMPLATES_DIR`. Verify it works by writing a test:

Append to `test_cowork_adapter.py`:

```python
def test_transform_uses_template_override(tmp_path):
    """When a template exists for a skill, use its body instead of auto-stripping."""
    from unittest.mock import patch
    from sync_agents.adapters.cowork import _transform_skill_md, _TEMPLATES_DIR

    # Create a temporary template
    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    (template_dir / "career.md").write_text("# Career\n\nCustom template body.\n")

    input_md = "---\nname: career\ndescription: Job search\nx-augur-hub: career\n---\n# Original body\n"

    with patch("sync_agents.adapters.cowork._TEMPLATES_DIR", template_dir):
        result = _transform_skill_md(input_md, "career", "claude-code")

    assert "Custom template body" in result
    assert "Original body" not in result
    assert "name: career" in result
```

- [ ] **Step 4: Test template loading**

Run: `cd ~/Projects/Augur && python -m pytest .claude/skills/ai_bridge/augur/tests/test_cowork_adapter.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/ai_bridge/scripts/sync_agents/adapters/cowork_templates/ .claude/skills/ai_bridge/scripts/sync_agents/adapters/cowork.py
git commit -m "feat(sync): add cowork template overrides for key skills (ADR-442)"
```

---

### Task 6: Register adapter in engine.py

**Files:**
- Modify: `.claude/skills/ai_bridge/scripts/sync_agents/engine.py:69-81,235-261`

- [ ] **Step 1: Add cowork to ADAPTER_TO_MASTER**

In `engine.py` at line ~81, add after the `claude_desktop` entry:

```python
    "claude_desktop": "claude-desktop",
    "cowork": "cowork",
```

- [ ] **Step 2: Register CoworkAdapter in _get_all_adapters()**

In `engine.py` at `_get_all_adapters()` (line ~235), add the lazy import and instantiation:

```python
    from .adapters.cowork import CoworkAdapter
    # ... add to the returned list:
    adapters.append(CoworkAdapter())
```

- [ ] **Step 3: Run existing sync_agents tests to verify no regressions**

Run: `cd ~/Projects/Augur && python -m pytest .claude/skills/ai_bridge/augur/tests/ -k "sync" -v --timeout=30`
Expected: PASS (no regressions)

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/ai_bridge/scripts/sync_agents/engine.py
git commit -m "feat(sync): register cowork adapter in engine (ADR-442)"
```

---

### Task 7: Enable cowork in ide_integrations.yaml

**Files:**
- Modify: `config/agents/ide_integrations.yaml:311`

- [ ] **Step 1: Flip cowork enabled flag**

Change line 312 from:
```yaml
  enabled: false
```
to:
```yaml
  enabled: true
```

- [ ] **Step 2: Commit**

```bash
git add config/agents/ide_integrations.yaml
git commit -m "feat(config): enable cowork adapter (ADR-442)"
```

---

### Task 8: Delete legacy export script

**Files:**
- Delete: `dist/plugins/augur-knowledge/skills/ai_bridge/scripts/export_cowork_plugin.py`

- [ ] **Step 1: Verify no other code imports the export script**

Run: `cd ~/Projects/Augur && grep -r "export_cowork_plugin" --include="*.py" --include="*.md" --include="*.yaml" -l`
Expected: Only the file itself and possibly ADR/spec references (docs, not imports)

- [ ] **Step 2: Delete the file**

```bash
rm dist/plugins/augur-knowledge/skills/ai_bridge/scripts/export_cowork_plugin.py
```

- [ ] **Step 3: Commit**

```bash
git add -A dist/plugins/augur-knowledge/skills/ai_bridge/scripts/export_cowork_plugin.py
git commit -m "cleanup: delete legacy export_cowork_plugin.py, replaced by cowork adapter (ADR-442)"
```

---

### Task 9: Generate commands/ directory

**Files:**
- Modify: `.claude/skills/ai_bridge/scripts/sync_agents/adapters/cowork.py`

The ADR specifies 3 commands (`ask.md`, `search.md`, `save.md`) in the plugin's `commands/` directory. These are generated during `generate_mcp_config()` alongside the manifest.

- [ ] **Step 1: Add command generation to the adapter**

Add a `_generate_commands()` method to `CoworkAdapter` that creates `commands/` in the output directory:

```python
_COWORK_COMMANDS = {
    "ask": {
        "description": "Ask your second brain any question",
        "body": "Search across all your knowledge — notes, documents, memory, and project history — to answer questions and find information.",
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

def _generate_commands(self) -> None:
    """Generate commands/ directory with user-facing slash commands."""
    commands_dir = self._output_dir / "commands"
    commands_dir.mkdir(parents=True, exist_ok=True)

    for name, cmd in _COWORK_COMMANDS.items():
        content = f"---\nname: {name}\ndescription: {cmd['description']}\n---\n\n{cmd['body']}\n"
        (commands_dir / f"{name}.md").write_text(content, encoding="utf-8")
```

Call `self._generate_commands()` at the end of `generate_mcp_config()`.

- [ ] **Step 2: Test command generation**

Append to `test_cowork_adapter.py`:

```python
def test_generate_commands(tmp_path):
    from sync_agents.adapters.cowork import CoworkAdapter

    adapter = CoworkAdapter()
    adapter._output_dir = tmp_path / "augur-cowork"
    adapter.generate_mcp_config()

    assert (tmp_path / "augur-cowork" / "commands" / "ask.md").exists()
    assert (tmp_path / "augur-cowork" / "commands" / "search.md").exists()
    assert (tmp_path / "augur-cowork" / "commands" / "save.md").exists()

    content = (tmp_path / "augur-cowork" / "commands" / "ask.md").read_text()
    assert "name: ask" in content
```

- [ ] **Step 3: Run test**

Run: `cd ~/Projects/Augur && python -m pytest .claude/skills/ai_bridge/augur/tests/test_cowork_adapter.py::test_generate_commands -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/ai_bridge/scripts/sync_agents/adapters/cowork.py .claude/skills/ai_bridge/augur/tests/test_cowork_adapter.py
git commit -m "feat(sync): add commands/ generation to cowork adapter (ADR-442)"
```

---

### Task 10: Integration test -- run sync and verify output

**Files:**
- Test: `.claude/skills/ai_bridge/augur/tests/test_cowork_adapter.py` (append)

- [ ] **Step 1: Write integration test**

Append to `test_cowork_adapter.py`:

```python
def test_cowork_adapter_end_to_end(tmp_path):
    """Full adapter integration: sync skills, verify plugin output."""
    from sync_agents.adapters.cowork import CoworkAdapter

    adapter = CoworkAdapter()
    # Override output to tmp
    adapter._output_dir = tmp_path / "augur-cowork"

    # Generate MCP config and manifest
    adapter.generate_mcp_config()

    # Verify structure
    assert (tmp_path / "augur-cowork" / ".claude-plugin" / "plugin.json").exists()
    assert (tmp_path / "augur-cowork" / ".mcp.json").exists()

    # Verify plugin.json content
    manifest = json.loads(
        (tmp_path / "augur-cowork" / ".claude-plugin" / "plugin.json").read_text()
    )
    assert manifest["name"] == "augur"

    # Verify .mcp.json content
    mcp = json.loads((tmp_path / "augur-cowork" / ".mcp.json").read_text())
    assert "cowork" in mcp["mcpServers"]["augur"]["args"]

    # Sync a fake skill
    fake_skill = tmp_path / "fake-skill"
    fake_skill.mkdir()
    (fake_skill / "SKILL.md").write_text(
        "---\nname: test-skill\ndescription: A test\nx-augur-hub: brain\n---\n# Test\nContent here.\n"
    )
    count = adapter.sync_skill("test-skill", fake_skill, {
        "x-augur-hub": "brain",
        "master": "claude-code",
    })
    assert count == 1
    assert (tmp_path / "augur-cowork" / "skills" / "test-skill" / "SKILL.md").exists()

    # Verify AUGUR-ADAPTED-COPY marker
    result = (tmp_path / "augur-cowork" / "skills" / "test-skill" / "SKILL.md").read_text()
    assert "AUGUR-ADAPTED-COPY" in result
    assert "x-augur-hub" not in result
```

- [ ] **Step 2: Run integration test**

Run: `cd ~/Projects/Augur && python -m pytest .claude/skills/ai_bridge/augur/tests/test_cowork_adapter.py::test_cowork_adapter_end_to_end -v`
Expected: PASS

- [ ] **Step 3: Run full sync to verify end-to-end**

Run: `cd ~/Projects/Augur && python -m skills.ai.scripts.sync_agents sync all 2>&1 | grep -i cowork`
Expected: Output showing cowork adapter running, skills adapted, plugin generated at `dist/plugins/augur-cowork/`

- [ ] **Step 4: Verify generated plugin structure**

Run: `find dist/plugins/augur-cowork/ -type f | head -30 && echo "---" && cat dist/plugins/augur-cowork/.claude-plugin/plugin.json && echo "---" && cat dist/plugins/augur-cowork/.mcp.json`
Expected: Complete plugin structure with skills/, .claude-plugin/plugin.json, .mcp.json

- [ ] **Step 5: Run all tests to confirm no regressions**

Run: `cd ~/Projects/Augur && python -m pytest .claude/skills/ai_bridge/augur/tests/test_cowork_adapter.py .claude/skills/ai_bridge/augur/tests/test_cowork_mcp.py -v`
Expected: ALL PASS

- [ ] **Step 6: Final commit**

```bash
git add .claude/skills/ai_bridge/augur/tests/test_cowork_adapter.py
git commit -m "test: add cowork adapter integration tests (ADR-442)"
```

---

### Task 11: Update ADR status

- [ ] **Step 1: Update ADR-442 status to Implemented**

In `get_vault_dir()/dev/adrs/ADR-442-cowork-plugin-integration.md`, change:
```yaml
status: Proposed
```
to:
```yaml
status: Implemented
```

- [ ] **Step 2: Commit**

```bash
git add -A
git commit -m "docs: mark ADR-442 as Implemented"
```
