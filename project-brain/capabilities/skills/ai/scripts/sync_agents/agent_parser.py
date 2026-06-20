"""sync_agents/agent_parser.py — Parse agent markdown files for cross-client sync.

ADR-464: Reads agent .md files from any client directory, extracts frontmatter
and body content, classifies master vs adapted copy. Also discovers installed
Claude Code plugin agents for inclusion in registry and cross-client sync.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Any

import yaml
from datetime import datetime


ADAPTED_COPY_MARKER = "AUGUR-ADAPTED-COPY"
ADAPTED_COPY_COMMENT = "<!-- AUGUR-ADAPTED-COPY source={master_client} -->"


def _strip_leading_html_comments(content: str) -> str:
    """Strip generated HTML comment headers before frontmatter parsing."""
    remaining = content.lstrip()
    while remaining.startswith("<!--"):
        end_idx = remaining.find("-->")
        if end_idx == -1:
            break
        remaining = remaining[end_idx + 3:].lstrip()
    return remaining


@dataclass
class AgentFile:
    """Parsed representation of an agent .md file."""

    name: str
    path: Path
    frontmatter: dict[str, Any]
    body: str
    client_dir: str  # e.g. "claude-code", "gemini"
    source_priority: float = 0.0

    @property
    def master_client(self) -> str:
        """The client that masters this agent."""
        return self.frontmatter.get("x-augur-master", self.client_dir)

    @cached_property
    def is_adapted(self) -> bool:
        """True if this file is an adapted copy."""
        return ADAPTED_COPY_MARKER in self.body

    @property
    def is_master(self) -> bool:
        """True if this file is the master copy (not an adapted copy)."""
        return not self.is_adapted

    @property
    def model(self) -> str:
        """The model declared in frontmatter."""
        return self.frontmatter.get("model", "sonnet")

    @property
    def mode(self) -> str:
        """The mode declared in frontmatter (auto/plan)."""
        return self.frontmatter.get("mode", "auto")

    @cached_property
    def description(self) -> str:
        """Extract description from first blockquote or first paragraph after title."""
        for line in self.body.splitlines():
            line = line.strip()
            if line.startswith("> "):
                return line[2:].strip()
            # Skip title lines
            if line.startswith("# ") or not line:
                continue
            if line.startswith("**") or line.startswith("##"):
                break
            return line
        return ""

    @cached_property
    def tools(self) -> list[str]:
        """Extract tools from frontmatter and the Allowed Tools section."""
        tools: list[str] = []

        def add_tool(value: object) -> None:
            tool = str(value).strip().strip("`")
            if tool and tool not in tools:
                tools.append(tool)

        raw_tools = self.frontmatter.get("tools")
        if isinstance(raw_tools, str):
            for tool in raw_tools.split(","):
                add_tool(tool)
        elif isinstance(raw_tools, list):
            for tool in raw_tools:
                add_tool(tool)

        in_tools_section = False
        for line in self.body.splitlines():
            if "## Allowed Tools" in line:
                in_tools_section = True
                continue
            if in_tools_section:
                if line.startswith("## "):
                    break
                stripped = line.strip()
                if stripped.startswith("- "):
                    tool = stripped[2:].strip().split(" ")[0].strip("`")
                    add_tool(tool)
        return tools

    @property
    def mcp_servers(self) -> list[str]:
        """MCP servers from frontmatter."""
        return self.frontmatter.get("mcpServers", [])


def parse_agent_file(path: Path, client_id: str) -> AgentFile | None:
    """Parse a single agent markdown file.

    Args:
        path: Path to the .md file.
        client_id: Client identifier for the directory (e.g., "claude-code").

    Returns:
        AgentFile or None if parsing fails.
    """
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return None

    content = _strip_leading_html_comments(content)

    frontmatter: dict[str, Any] = {}
    body = content

    if content.startswith("---"):
        try:
            end_idx = content.index("---", 3)
            fm_raw = yaml.safe_load(content[3:end_idx])
            if isinstance(fm_raw, dict):
                frontmatter = fm_raw
            body = content[end_idx + 3:].lstrip("\n")
        except (ValueError, Exception):
            body = content

    if not frontmatter:
        return None

    return AgentFile(
        name=str(frontmatter.get("name", path.stem)).strip(),
        path=path,
        frontmatter=frontmatter,
        body=body,
        client_dir=client_id,
    )


def _is_agent_markdown(path: Path) -> bool:
    """Return True for real agent markdown files, excluding README-style docs."""
    if path.suffix.lower() != ".md":
        return False
    stem = path.stem.strip().lower()
    return not stem.startswith("readme")


def _parse_manifest_timestamp(value: object) -> float:
    """Parse ISO timestamps from installed_plugins.json into sortable epochs."""
    if not isinstance(value, str) or not value.strip():
        return 0.0
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text).timestamp()
    except ValueError:
        return 0.0


# Client agent directory mapping (relative to project root)
# Note: Cline reads .claude/agents/ natively — omitted to avoid duplicate scanning.
CLIENT_AGENT_DIRS: dict[str, str] = {
    "claude-code": ".claude/agents",
    "gemini": ".antigravity/agents",
    "codex": ".codex/agents",
    "cursor": ".cursor/agents",
    "copilot": ".github/agents",
    "opencode": ".opencode/agents",
    "antigravity": ".subagents",
}


def scan_project_agents(project_root: Path) -> list[AgentFile]:
    """Scan canonical repo-owned agent definitions from plugins/agents/."""
    agents_dir = project_root / "plugins" / "agents"
    if not agents_dir.is_dir():
        return []

    agents: list[AgentFile] = []
    for md_file in sorted(agents_dir.glob("*.md")):
        if not _is_agent_markdown(md_file):
            continue
        agent = parse_agent_file(md_file, "claude-code")
        if agent is None:
            continue
        # Canonical repo profiles outrank stale generated client-local copies.
        agent.source_priority = 10**18
        agents.append(agent)
    return agents


def scan_agent_dirs(project_root: Path, clients: list[str] | None = None) -> list[AgentFile]:
    """Scan client agent directories for agent files.

    Args:
        project_root: Repository root path.
        clients: Optional list of client IDs to scan. Defaults to all.

    Returns:
        List of parsed AgentFile objects.
    """
    agents: list[AgentFile] = []
    scan_clients = clients or list(CLIENT_AGENT_DIRS.keys())

    for client_id in scan_clients:
        rel_dir = CLIENT_AGENT_DIRS.get(client_id)
        if not rel_dir:
            continue

        agent_dir = project_root / rel_dir
        if not agent_dir.is_dir():
            continue

        for md_file in sorted(agent_dir.glob("*.md")):
            if not _is_agent_markdown(md_file):
                continue
            agent = parse_agent_file(md_file, client_id)
            if agent is not None:
                agents.append(agent)

    return agents


def collect_masters(agents: list[AgentFile]) -> dict[str, AgentFile]:
    """Collect master agents, deduplicating by name.

    If two clients claim master for the same name, prefer the one
    with the most recent file modification time.

    Args:
        agents: All parsed agent files.

    Returns:
        Dict mapping agent name → master AgentFile.
    """
    from .constants import logger

    masters: dict[str, AgentFile] = {}

    for agent in agents:
        if agent.is_adapted:
            continue

        if agent.name in masters:
            existing = masters[agent.name]
            # Conflict: two clients claim master for same name.
            # Prefer explicit source priority from plugin install metadata,
            # then fall back to file mtime for local ties.
            if agent.source_priority != existing.source_priority:
                if agent.source_priority > existing.source_priority:
                    masters[agent.name] = agent
                continue

            existing_mtime = existing.path.stat().st_mtime
            new_mtime = agent.path.stat().st_mtime
            if new_mtime > existing_mtime:
                masters[agent.name] = agent
            else:
                logger.warning(
                    f"Dual master conflict for '{agent.name}': "
                    f"{existing.client_dir} vs {agent.client_dir} — "
                    f"keeping {existing.client_dir} (more recent)"
                )
        else:
            masters[agent.name] = agent

    return masters


def scan_plugin_agents() -> list[AgentFile]:
    """Discover agents from installed Claude Code plugins.

    Reads ~/.claude/plugins/installed_plugins.json, resolves each plugin's
    install path, and parses agent .md files from the agents/ subdirectory.

    Plugin agents use client_dir="plugin:<plugin-name>" to distinguish
    them from project-level agents.

    Returns:
        List of parsed AgentFile objects from installed plugins.
    """
    import json as _json
    from .constants import logger

    plugins_dir = Path.home() / ".claude" / "plugins"
    manifest = plugins_dir / "installed_plugins.json"
    if not manifest.exists():
        return []

    try:
        data = _json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, _json.JSONDecodeError) as e:
        logger.warning(f"Failed to read installed_plugins.json: {e}")
        return []

    agents: list[AgentFile] = []
    plugins = data.get("plugins", {})

    for plugin_key, installs in plugins.items():
        # plugin_key format: "feature-dev@claude-plugins-official"
        plugin_name = plugin_key.split("@")[0]

        if not isinstance(installs, list) or not installs:
            continue

        # Use the first (most recent) install entry
        install = installs[0]
        install_path = Path(install.get("installPath", ""))
        if not install_path.is_dir():
            continue
        install_priority = max(
            _parse_manifest_timestamp(install.get("lastUpdated")),
            _parse_manifest_timestamp(install.get("installedAt")),
        )

        agents_dir = install_path / "agents"
        if not agents_dir.is_dir():
            continue

        client_id = f"plugin:{plugin_name}"
        for md_file in sorted(agents_dir.glob("*.md")):
            if not _is_agent_markdown(md_file):
                continue
            agent = parse_agent_file(md_file, client_id)
            if agent is not None:
                # Plugin agents are always masters (source of truth from the plugin)
                agent.source_priority = install_priority
                agents.append(agent)

    return agents
