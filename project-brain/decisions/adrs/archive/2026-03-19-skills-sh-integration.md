# skills.sh Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate skills.sh (Vercel Labs' open agent skills ecosystem) into Augur for community skill discovery and installation via CLI and dashboard.

**Architecture:** New `.claude/skills/skills.sh/` skill wraps `npx skills` CLI via CLIBridge, exposing 5 MCP tools (search, add, list, remove, trending). Import skill's SKILL.md gets a `skills-sh-catalog` dashboard block. External MCP registry gets a `skills-sh` CLI entry.

**Tech Stack:** Python (MCP tools via CLIBridge), YAML (config/frontmatter)

**Spec:** `docs/superpowers/specs/2026-03-19-skills-sh-integration-design.md`

---

## File Structure

| File | Responsibility |
|------|---------------|
| `.claude/skills/skills.sh/SKILL.md` | Skill definition, frontmatter, slash command docs |
| `.claude/skills/skills.sh/scripts/mcp/__init__.py` | `register_tools()` + 5 MCP tools via CLIBridge |
| `config/integrations/external_mcp_registry.yaml` | Add `skills-sh` CLI entry under `services:` |
| `.claude/skills/import/SKILL.md` | Add `skills-sh-catalog` block to contributions |
| `tests/mcp/test_skills_sh.py` | Unit tests for all 5 MCP tools (mocked CLIBridge) |

---

### Task 1: Register skills-sh CLI in external MCP registry

**Files:**
- Modify: `config/integrations/external_mcp_registry.yaml`

- [ ] **Step 1: Add skills-sh entry under CLI Tools section**

Add after the `gcloud` entry (line ~180):

```yaml
  skills-sh:
    name: Skills.sh CLI
    type: cli
    description: Open agent skills ecosystem — search, install, manage community skills
    tier: 1
    cost: free
    enabled: true
    check_command: npx skills --version
    used_by:
      - skills.sh
      - import
      - dev-sync
    setup_url: https://skills.sh
    tags:
      - skills
      - community
      - marketplace
```

- [ ] **Step 2: Validate YAML syntax**

Run: `python -c "import yaml; yaml.safe_load(open('config/integrations/external_mcp_registry.yaml'))"`
Expected: No output (valid YAML)

- [ ] **Step 3: Commit**

```bash
git add config/integrations/external_mcp_registry.yaml
git commit -m "feat: register skills.sh CLI in external MCP registry"
```

---

### Task 2: Write failing tests for skills-sh MCP tools

**Files:**
- Create: `tests/mcp/test_skills_sh.py`

- [ ] **Step 1: Write test file with all test cases**

```python
"""
skills.sh MCP Tool Unit Tests.

Tests the skills.sh CLIBridge wrappers using mocked subprocess calls.
No real npx/skills CLI needed.

Run with: pytest tests/mcp/test_skills_sh.py -v
"""

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add augur-mcp src to path
_pkg_src = Path(__file__).parent.parent / "src"
if str(_pkg_src) not in sys.path:
    sys.path.insert(0, str(_pkg_src))


# =============================================================================
# Helpers
# =============================================================================

SKILLS_SH_MCP = (
    Path(__file__).parent.parent / ".claude" / "skills" / "skills.sh" / "scripts" / "mcp"
)


def _import_module():
    """Import the skills.sh MCP module dynamically."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "skills_sh_mcp", SKILLS_SH_MCP / "__init__.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# =============================================================================
# CLIBridge wrapper tests
# =============================================================================


class TestSkillsJsonWrapper:
    """Tests _skills_json wrapper which formats CLI output as JSON strings."""

    @patch("shutil.which", return_value="/usr/local/bin/npx")
    @patch("augur_mcp.cli_bridge.subprocess_run")
    def test_json_success(self, mock_run, mock_which):
        results = [
            {"name": "next-app", "author": "vercel-labs", "installs": 12800},
            {"name": "react-hooks", "author": "community", "installs": 5400},
        ]
        mock_run.return_value = MagicMock(
            stdout=json.dumps(results), stderr="", returncode=0
        )
        mod = _import_module()
        output = mod._skills_json(["find", "next.js"])
        data = json.loads(output)
        assert len(data) == 2
        assert data[0]["name"] == "next-app"

    @patch("shutil.which", return_value=None)
    def test_json_npx_not_installed(self, mock_which):
        mod = _import_module()
        output = mod._skills_json(["find", "test"])
        data = json.loads(output)
        assert "error" in data
        assert "Node.js" in data["error"]

    @patch("shutil.which", return_value="/usr/local/bin/npx")
    @patch("augur_mcp.cli_bridge.subprocess_run")
    def test_json_nonzero_exit(self, mock_run, mock_which):
        mock_run.return_value = MagicMock(
            stdout="", stderr="command failed", returncode=1
        )
        mod = _import_module()
        output = mod._skills_json(["find", "bad"])
        data = json.loads(output)
        assert "error" in data
        assert "command failed" in data["error"]


class TestSkillsActionWrapper:
    """Tests _skills_action wrapper for write operations."""

    @patch("shutil.which", return_value="/usr/local/bin/npx")
    @patch("augur_mcp.cli_bridge.subprocess_run")
    def test_action_success(self, mock_run, mock_which):
        mock_run.return_value = MagicMock(
            stdout="Installed next-app to ~/.claude/skills/next-app",
            stderr="",
            returncode=0,
        )
        mod = _import_module()
        output = mod._skills_action(["add", "vercel-labs/skills/next-app", "--client", "claude"])
        data = json.loads(output)
        assert data["success"] is True
        assert "Installed" in data["output"]

    @patch("shutil.which", return_value="/usr/local/bin/npx")
    @patch("augur_mcp.cli_bridge.subprocess_run")
    def test_action_nonzero_exit(self, mock_run, mock_which):
        mock_run.return_value = MagicMock(
            stdout="", stderr="skill not found", returncode=1
        )
        mod = _import_module()
        output = mod._skills_action(["add", "nonexistent/skill"])
        data = json.loads(output)
        assert "error" in data
        assert "skill not found" in data["error"]

    @patch("shutil.which", return_value="/usr/local/bin/npx")
    @patch("augur_mcp.cli_bridge.subprocess_run")
    def test_action_remove(self, mock_run, mock_which):
        mock_run.return_value = MagicMock(
            stdout="Removed next-app", stderr="", returncode=0
        )
        mod = _import_module()
        output = mod._skills_action(["remove", "next-app"])
        data = json.loads(output)
        assert data["success"] is True


class TestSkillsRun:
    """Tests _skills_run prepends npx -y skills args."""

    @patch("shutil.which", return_value="/usr/local/bin/npx")
    @patch("augur_mcp.cli_bridge.subprocess_run")
    def test_prepends_npx_y_skills(self, mock_run, mock_which):
        mock_run.return_value = MagicMock(stdout="ok", stderr="", returncode=0)
        mod = _import_module()
        mod._skills_run(["find", "test"])
        call_args = mock_run.call_args[0][0]
        assert call_args[:3] == ["npx", "-y", "skills"]
        assert call_args[3:] == ["find", "test"]


class TestClientMapping:
    def test_known_clients_map_correctly(self):
        mod = _import_module()
        assert mod.CLIENT_MAP["claude-code"] == "claude"
        assert mod.CLIENT_MAP["codex"] == "codex"
        assert mod.CLIENT_MAP["gemini"] == "gemini-cli"
        assert mod.CLIENT_MAP["cursor"] == "cursor"

    def test_unknown_client_not_in_map(self):
        mod = _import_module()
        assert "unknown-client" not in mod.CLIENT_MAP


class TestRegisterTools:
    """Verify register_tools wires up all 5 tools on a mock MCP."""

    def test_registers_five_tools(self):
        mod = _import_module()
        mock_mcp = MagicMock()
        # mcp.tool() returns a decorator, which returns the function
        mock_mcp.tool.return_value = lambda fn: fn
        mock_interceptor = lambda fn: fn  # noqa: E731
        mock_metrics = MagicMock()
        mod.register_tools(mock_mcp, mock_interceptor, mock_metrics)
        assert mock_mcp.tool.call_count == 5
        tool_names = [call.kwargs["name"] for call in mock_mcp.tool.call_args_list]
        assert "skills-sh-search" in tool_names
        assert "skills-sh-add" in tool_names
        assert "skills-sh-list" in tool_names
        assert "skills-sh-remove" in tool_names
        assert "skills-sh-trending" in tool_names
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/mcp/test_skills_sh.py -v 2>&1 | head -30`
Expected: FAIL — module not found at `.claude/skills/skills.sh/scripts/mcp/__init__.py`

- [ ] **Step 3: Commit**

```bash
git add tests/mcp/test_skills_sh.py
git commit -m "test: add failing tests for skills-sh MCP tools"
```

---

### Task 3: Create skills.sh skill SKILL.md

**Files:**
- Create: `.claude/skills/skills.sh/SKILL.md`

- [ ] **Step 1: Create skill directory**

Run: `mkdir -p .claude/skills/skills.sh/scripts/mcp`

- [ ] **Step 2: Write SKILL.md**

```markdown
---
name: skills.sh
description: Search, install, and manage community skills from skills.sh marketplace
x-augur-hub: command
x-augur-tab: system
x-augur-visibility: app
x-augur-license: MIT
x-augur-metadata:
  version: 1.0.0
  author: Augur
  mcp-server: augur
x-augur-master: claude-code
x-augur-plugin: augur-system
x-augur-requires-platform: true
x-augur-mcp-tools:
  - skills-sh-search
  - skills-sh-add
  - skills-sh-list
  - skills-sh-remove
  - skills-sh-trending
---

# /skills.sh

Search, install, and manage community skills from the skills.sh open agent skills ecosystem (by Vercel Labs). Supports 40+ agent clients including Claude Code, Codex, Gemini, Cursor, and more.

## Usage

```
/skills.sh search <query>                      # search skills.sh, show results table
/skills.sh add <owner/repo>                     # install to default master (claude-code)
/skills.sh add <owner/repo> --client codex      # install with explicit master client
/skills.sh list                                 # show installed community skills
/skills.sh remove <name>                        # uninstall
/skills.sh trending                             # show leaderboard top-20
```

## Options

| Flag | Description |
|------|-------------|
| `--client <name>` | Target client for install: claude-code (default), codex, gemini, cursor |

## Post-Install Flow

1. `npx skills add` installs to the master client's native dir (e.g. `~/.claude/skills/`)
2. Augur skill registry auto-discovers the new skill
3. `dev-sync` propagates to other connected clients
4. Optional: `/import promote` for full Augur management (MCP codegen, dashboard, tests)

## MCP Tools

| Tool | Description |
|------|-------------|
| `skills-sh-search` | Search skills.sh for community skills |
| `skills-sh-add` | Install skill to specified master client |
| `skills-sh-list` | List skills installed via skills.sh |
| `skills-sh-remove` | Uninstall a skills.sh-installed skill |
| `skills-sh-trending` | Show top-20 trending skills from leaderboard |

## Dependencies

- Node.js (for `npx`)
- `skills` npm package (auto-installed via `npx -y`)
```

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/skills.sh/SKILL.md
git commit -m "feat: add skills.sh skill definition"
```

---

### Task 4: Implement MCP tools via CLIBridge

**Files:**
- Create: `.claude/skills/skills.sh/scripts/mcp/__init__.py`

- [ ] **Step 1: Write the MCP module**

```python
"""
skills.sh — Community skill discovery and installation via skills.sh.

Wraps the `npx skills` CLI via CLIBridge for search, install, list,
remove, and trending operations across 40+ agent clients.

This module is loaded dynamically by the Augur MCP server
via the plugin tool loading system.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

try:
    from augur_mcp.logging import get_entity_logger
    from augur_mcp.annotations import tool_annotations
    from augur_mcp.cli_bridge import CLIBridge
except ImportError:
    import importlib

    def get_entity_logger(name: str):
        return importlib.import_module("logging").getLogger(name)

    def tool_annotations(annotations: dict) -> dict:
        return annotations

    CLIBridge = None  # type: ignore


logger = get_entity_logger("mcp.skills-sh")

# CLIBridge wraps npx; every call prepends: npx -y skills <subcommand>
_bridge = CLIBridge("npx", install_hint="Install Node.js from nodejs.org") if CLIBridge else None

# Default timeout: 90s to handle first-run npx package download
_TIMEOUT = 90

# Maps Augur client names to skills.sh --client flag values.
# Reuses the same client IDs as import skill's CLIENT_SKILL_DIRS.
CLIENT_MAP: dict[str, str] = {
    "claude-code": "claude",
    "codex": "codex",
    "gemini": "gemini-cli",
    "cursor": "cursor",
}


def _skills_run(
    args: list[str],
    timeout: int = _TIMEOUT,
    json_output: bool = False,
) -> dict[str, Any]:
    """Run an npx skills subcommand via CLIBridge.

    Prepends ["-y", "skills"] to all args so that:
        _skills_run(["find", "next.js"])
    executes:
        npx -y skills find next.js
    """
    if not _bridge:
        return {"error": "CLIBridge not available", "returncode": -1}
    return _bridge.run(["-y", "skills"] + args, timeout=timeout, json_output=json_output)


def _skills_json(args: list[str], timeout: int = _TIMEOUT) -> str:
    """Run an npx skills subcommand and return JSON string response."""
    result = _skills_run(args, timeout=timeout, json_output=True)
    if "error" in result:
        return json.dumps({"error": result["error"]})
    if result["returncode"] != 0:
        stderr = result.get("stderr", "").strip()
        return json.dumps({"error": stderr or f"npx skills failed (exit {result['returncode']})"})
    data = result.get("data") or result.get("stdout", "").strip()
    return json.dumps(data) if not isinstance(data, str) else data


def _skills_action(args: list[str], timeout: int = _TIMEOUT) -> str:
    """Run an npx skills action command and return JSON success/error."""
    result = _skills_run(args, timeout=timeout)
    if "error" in result:
        return json.dumps({"error": result["error"]})
    if result["returncode"] != 0:
        stderr = result.get("stderr", "").strip()
        return json.dumps({"error": stderr or f"npx skills failed (exit {result['returncode']})"})
    return json.dumps({"success": True, "output": result.get("stdout", "").strip()})


def register_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable[..., Any],
    metrics: Any,
) -> None:
    """Register skills.sh MCP tools."""
    logger.info("Registering skills.sh MCP tools...")

    # =========================================================================
    # Search
    # =========================================================================

    @mcp.tool(
        name="skills-sh-search",
        annotations=tool_annotations(
            {
                "title": "Search Community Skills",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": True,
            }
        ),
    )
    @mcp_tool_interceptor
    async def skills_sh_search(query: str) -> str:
        """Search skills.sh for community skills matching a query.

        Args:
            query: Search term (e.g. "next.js", "react", "testing")

        Returns:
            JSON array of matching skills with name, author, description, installs.
        """
        metrics.track_tool("skills_sh_search", skill="skills.sh")
        return _skills_json(["find", query])

    # =========================================================================
    # Add (install)
    # =========================================================================

    @mcp.tool(
        name="skills-sh-add",
        annotations=tool_annotations(
            {
                "title": "Install Community Skill",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": True,
            }
        ),
    )
    @mcp_tool_interceptor
    async def skills_sh_add(
        skill_ref: str,
        client: str = "claude-code",
    ) -> str:
        """Install a community skill from skills.sh to a master client.

        Args:
            skill_ref: Skill reference (e.g. "vercel-labs/skills/next-app")
            client: Target master client. One of: claude-code, codex, gemini, cursor.
                    Default: claude-code. Other clients sync via dev-sync.

        Returns:
            JSON with success status and install location.
        """
        metrics.track_tool("skills_sh_add", skill="skills.sh")
        client_flag = CLIENT_MAP.get(client)
        if not client_flag:
            valid = ", ".join(sorted(CLIENT_MAP.keys()))
            return json.dumps({"error": f"Unknown client '{client}'. Valid: {valid}"})
        return _skills_action(["add", skill_ref, "--client", client_flag])

    # =========================================================================
    # List
    # =========================================================================

    @mcp.tool(
        name="skills-sh-list",
        annotations=tool_annotations(
            {
                "title": "List Installed Community Skills",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def skills_sh_list() -> str:
        """List all skills installed via skills.sh.

        Returns:
            JSON array of installed skills with name, client, path.
        """
        metrics.track_tool("skills_sh_list", skill="skills.sh")
        return _skills_json(["list"])

    # =========================================================================
    # Remove
    # =========================================================================

    @mcp.tool(
        name="skills-sh-remove",
        annotations=tool_annotations(
            {
                "title": "Remove Community Skill",
                "readOnlyHint": False,
                "destructiveHint": True,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def skills_sh_remove(name: str) -> str:
        """Uninstall a skills.sh-installed skill.

        Args:
            name: Name of the skill to remove.

        Returns:
            JSON with success status and removed path.
        """
        metrics.track_tool("skills_sh_remove", skill="skills.sh")
        return _skills_action(["remove", name])

    # =========================================================================
    # Trending
    # =========================================================================

    @mcp.tool(
        name="skills-sh-trending",
        annotations=tool_annotations(
            {
                "title": "Trending Community Skills",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": True,
            }
        ),
    )
    @mcp_tool_interceptor
    async def skills_sh_trending() -> str:
        """Show top-20 trending skills from the skills.sh leaderboard.

        Returns:
            JSON array of trending skills sorted by 24h install count.
        """
        metrics.track_tool("skills_sh_trending", skill="skills.sh")
        return _skills_json(["find", "--sort", "trending", "--limit", "20"])

    logger.info("skills.sh MCP tools registered (5 tools)")


__all__ = ["register_tools"]
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `pytest tests/mcp/test_skills_sh.py -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/skills.sh/scripts/mcp/__init__.py
git commit -m "feat: implement skills-sh MCP tools via CLIBridge"
```

---

### Task 5: Add community skills dashboard block to import skill

**Files:**
- Modify: `.claude/skills/import/SKILL.md`

- [ ] **Step 1: Add skills-sh-catalog block to contributions.blocks**

In `.claude/skills/import/SKILL.md`, add after the existing `catalog` block (around line 116), before `actions:`:

```yaml
    - id: skills-sh-catalog
      type: data-table
      title: Community Skills
      icon: Globe
      search: true
      config_schema:
        columns:
          type: enum
          options:
            - name
            - author
            - installs_24h
            - installs_total
            - description
          default:
            - name
            - author
            - installs_total
      data_source:
        mcp_tool: skills-sh-list
      search_tool: skills-sh-search
```

- [ ] **Step 2: Add install-community-skill action**

In the existing top-level `actions:` list (sibling of `blocks:`, under `contributions:`), add:

```yaml
    - id: install-community-skill
      label: Install Community Skill
      icon: Globe
      dispatch: ide
      mcp_tools:
        - skills-sh-search
        - skills-sh-add
      prompt: |
        Install a community skill from skills.sh.
        1. Call skills-sh-search if user hasn't selected a specific skill.
        2. Show the selected skill details.
        3. Ask which master client to install to (default: claude-code).
        4. Call skills-sh-add with the selected owner/repo and client.
        5. Report install location and remind about /import promote for full Augur management.
```

- [ ] **Step 3: Validate SKILL.md YAML frontmatter**

Run: `python -c "import yaml; yaml.safe_load(open('.claude/skills/import/SKILL.md').read().split('---')[1])"`
Expected: No error

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/import/SKILL.md
git commit -m "feat: add community skills block to import skill dashboard"
```

---

### Task 6: Verify end-to-end wiring

**Files:** (no new files — verification only)

- [ ] **Step 1: Run all skills-sh tests**

Run: `pytest tests/mcp/test_skills_sh.py -v`
Expected: All PASS

- [ ] **Step 2: Verify SKILL.md frontmatter is valid**

Run: `python -c "import yaml; d=yaml.safe_load(open('.claude/skills/skills.sh/SKILL.md').read().split('---')[1]); print(d['name'], len(d['x-augur-mcp-tools']), 'tools')"`
Expected: `skills.sh 5 tools`

- [ ] **Step 3: Verify external registry is valid**

Run: `python -c "import yaml; d=yaml.safe_load(open('config/integrations/external_mcp_registry.yaml')); print('skills-sh' in d['services'])"`
Expected: `True`

- [ ] **Step 4: Verify import SKILL.md block wiring**

Run: `python -c "import yaml; d=yaml.safe_load(open('.claude/skills/import/SKILL.md').read().split('---')[1]); blocks=[b['id'] for b in d['x-augur-config']['contributions']['blocks']]; print('skills-sh-catalog' in blocks)"`
Expected: `True`

- [ ] **Step 5: Final commit (if any fixes needed)**

```bash
git add .claude/skills/skills.sh/ .claude/skills/import/SKILL.md config/integrations/external_mcp_registry.yaml tests/mcp/test_skills_sh.py
git commit -m "fix: address wiring issues from end-to-end verification"
```
