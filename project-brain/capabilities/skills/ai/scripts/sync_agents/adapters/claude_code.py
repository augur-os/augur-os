"""sync_agents/adapters/claude_code.py — Claude Code adapter."""
from __future__ import annotations
import json
import re
from pathlib import Path

import yaml

from .base import BaseAdapter
from ..constants import (
    PROJECT_ROOT,
    SOURCE_RULES_LABEL,
    MCP_CONFIG_TEMPLATE,
    GENERATED_FILES,
    logger,
)
from ..engine import write_generated_file
from ..templates import locate_mcp_python, render_rules_projection

class ClaudeCodeAdapter(BaseAdapter):
    adapter_name = "claude_code"

    @property
    def skills_dir(self) -> Path:
        """Return the path to repo-owned project-brain skills."""
        return PROJECT_ROOT / "project-brain" / "capabilities" / "skills"

    def get_managed_files(self) -> list[str]:
        # `project-brain/capabilities/skills/` and `docs/agent-topics/` are repository source
        # trees, not Claude Code-generated outputs. Cleanup must only remove
        # generated integration artifacts.
        return [
            "CLAUDE.md",
            ".claude/mcp.json",
            ".claude/agents/",
            ".claude/commands/",
        ]

    def get_state_files(self) -> list[str]:
        home = str(Path.home())
        return [
            f"{home}/.claude/projects/",
            f"{home}/.claude/todos/",
            f"{home}/.claude/statsig/",
            f"{home}/.claude/plugins/data/",
        ]

    def detect_installed(self) -> bool:
        import shutil
        return shutil.which("claude") is not None or (Path.home() / ".claude").is_dir()

    def sync_rules(self, content: str) -> None:
        target = PROJECT_ROOT / "CLAUDE.md"
        final_content = render_rules_projection(content)
        write_generated_file(
            target,
            final_content,
            source=SOURCE_RULES_LABEL,
        )

    def generate_mcp_config(self) -> None:
        """Generate resolved MCP config for Claude Code (.claude/mcp.json).

        Reads the template from src/config/mcp_config.template.json,
        resolves ${AUGUR_ROOT} variables, and writes to .claude/mcp.json.
        """
        if not MCP_CONFIG_TEMPLATE.exists():
            logger.warning(f"MCP config template not found: {MCP_CONFIG_TEMPLATE}")
            return

        try:
            template_content = MCP_CONFIG_TEMPLATE.read_text(encoding="utf-8")

            # Resolve template variables.
            # locate_mcp_python() and PROJECT_ROOT.as_posix() emit POSIX-style paths
            # so JSON serialization stays safe on Windows.
            resolved = template_content.replace("${AUGUR_ROOT}", PROJECT_ROOT.as_posix())
            resolved = resolved.replace("${AUGUR_PYTHON}", locate_mcp_python())
            resolved = resolved.replace("${AUGUR_CLIENT_ID}", "claude-code")

            # Parse, re-serialize to ensure valid JSON
            config = json.loads(resolved)

            target = PROJECT_ROOT / ".claude" / "mcp.json"
            target.parent.mkdir(parents=True, exist_ok=True)

            # Don't use write_generated_file (no need for AUTO-GENERATED header on JSON)
            target.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
            GENERATED_FILES.append(target)
            logger.info(f"✅ Generated {target.relative_to(PROJECT_ROOT)} (MCP config)")
        except Exception as e:
            logger.error(f"Failed to generate MCP config for Claude Code: {e}")

    def sync_subagents(self) -> None:
        """Build registry.json from .claude/agents/*.md + installed Claude Code plugins.

        Sources:
        1. .claude/agents/*.md — hand-authored project agents (master_client: claude-code)
        2. ~/.claude/plugins/*/agents/*.md — installed plugin agents (source: plugin)

        Writes a unified registry.json with all agents.
        """
        from ..agent_parser import _is_agent_markdown, scan_plugin_agents

        agents_dir = PROJECT_ROOT / ".claude" / "agents"
        agents_dir.mkdir(parents=True, exist_ok=True)

        agents_dict: dict[str, dict] = {}

        # 1. Parse project agents from .claude/agents/*.md
        for md_file in sorted(agents_dir.glob("*.md")):
            if not _is_agent_markdown(md_file):
                continue
            try:
                entry = _parse_agent_md(md_file)
            except Exception as e:
                logger.warning(f"Failed to parse {md_file.name}: {e}")
                continue
            if entry is not None:
                agent_name = md_file.stem
                agents_dict[agent_name] = entry
                logger.info(
                    f"  → Subagent: {agent_name} "
                    f"({entry.get('role', '?')}, {entry.get('defaultModel', '?')})"
                )

        # 2. Discover and merge installed Claude Code plugin agents
        plugin_agents = scan_plugin_agents()
        for agent in plugin_agents:
            # Namespaced key: "plugin-name:agent-name"
            plugin_name = agent.client_dir.removeprefix("plugin:")
            key = f"{plugin_name}:{agent.name}"
            if key in agents_dict:
                continue  # Don't overwrite project agents

            tools_str = agent.frontmatter.get("tools", "")
            tools_list = [t.strip() for t in tools_str.split(",")] if isinstance(tools_str, str) and tools_str else []

            agents_dict[key] = {
                "role": "executor",
                "defaultModel": agent.model,
                "tools": tools_list,
                "master_client": "claude-code",
                "source": "plugin",
                "plugin": plugin_name,
                "description": agent.description,
            }
            logger.info(f"  → Plugin agent: {key} (model={agent.model})")

        if not agents_dict:
            logger.warning("No valid agent definitions found")
            return

        # Write registry.json as schema 2.0 (skip if unchanged)
        registry = {
            "schema": "2.0",
            "agents": agents_dict,
        }
        registry_content = json.dumps(registry, indent=2) + "\n"
        registry_path = agents_dir / "registry.json"
        skip_registry = False
        if registry_path.exists():
            try:
                if registry_path.read_text(encoding="utf-8") == registry_content:
                    skip_registry = True
            except OSError:
                pass
            if not skip_registry:
                current_mode = registry_path.stat().st_mode
                if not (current_mode & 0o200):
                    registry_path.chmod(current_mode | 0o200)
        if not skip_registry:
            registry_path.write_text(registry_content, encoding="utf-8")
            registry_path.chmod(0o444)
            logger.info(
                f"✅ Generated {agents_dir.relative_to(PROJECT_ROOT)}/registry.json "
                f"({len(agents_dict)} agents, schema {registry['schema']})"
            )
        GENERATED_FILES.append(registry_path)

    def distribute_external_skills(self, bundles: list) -> None:
        """Register vendored external bundles in Claude's known_marketplaces.json (ADR-605).

        Users opt into individual skills with ``/plugin install <name>@<bundle-id>``.
        We never write to ``.claude/skills/`` — Claude Code resolves vendored
        skills through the marketplace path, not by direct file copy.
        """
        from ..external_skills import _register_marketplace_for_claude_code
        _register_marketplace_for_claude_code(bundles)

    def cleanup(self, exclude_paths: set[Path] | None = None, dry_run: bool = False) -> list[str]:
        """Remove managed files and unregister the augur Claude Code plugin."""
        deleted: list[str] = []

        # 1. Surgical edit: remove augur@augur-cowork from installed_plugins.json
        plugins_json = Path.home() / ".claude" / "plugins" / "installed_plugins.json"
        if plugins_json.exists():
            try:
                data = json.loads(plugins_json.read_text(encoding="utf-8"))
                entries = data.get("plugins", {}).get("augur@augur-cowork", [])
                project_str = str(PROJECT_ROOT.resolve())
                matching = [
                    e for e in entries
                    if e.get("projectPath") == project_str or e.get("scope") == "user"
                ]
                if matching:
                    deleted.append(str(plugins_json))
                    if not dry_run:
                        remaining = [e for e in entries if e not in matching]
                        if remaining:
                            data["plugins"]["augur@augur-cowork"] = remaining
                        else:
                            del data["plugins"]["augur@augur-cowork"]
                        plugins_json.write_text(
                            json.dumps(data, indent=2) + "\n", encoding="utf-8"
                        )
                        logger.info("Removed augur@augur-cowork from %s", plugins_json)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Failed to clean %s: %s", plugins_json, e)

        # 2. Delete plugin cache dir
        cache_dir = Path.home() / ".claude" / "plugins" / "cache" / "augur-cowork"
        if cache_dir.exists():
            deleted.append(str(cache_dir) + "/")
            if not dry_run:
                import shutil
                shutil.rmtree(cache_dir)
                logger.info("Removed plugin cache: %s", cache_dir)

        # 3. Surgical edit: remove augur-* entries from known_marketplaces.json
        #    and delete the augur-skills marketplace install dir
        known_mp = Path.home() / ".claude" / "plugins" / "known_marketplaces.json"
        if known_mp.exists():
            try:
                data = json.loads(known_mp.read_text(encoding="utf-8"))
                augur_keys = [k for k in data if k.startswith("augur-")]
                if augur_keys:
                    deleted.append(str(known_mp))
                    if not dry_run:
                        for k in augur_keys:
                            data.pop(k)
                        known_mp.write_text(
                            json.dumps(data, indent=2) + "\n", encoding="utf-8"
                        )
                        logger.info("Removed augur marketplace entries from %s", known_mp)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Failed to clean %s: %s", known_mp, e)

        # 4. Delete augur-skills marketplace install dir (GitHub-cloned repo)
        augur_skills_mp = Path.home() / ".claude" / "plugins" / "marketplaces" / "augur-skills"
        if augur_skills_mp.exists():
            deleted.append(str(augur_skills_mp) + "/")
            if not dry_run:
                import shutil
                shutil.rmtree(augur_skills_mp)
                logger.info("Removed augur-skills marketplace dir: %s", augur_skills_mp)

        # 5. Delegate file cleanup to base
        deleted.extend(super().cleanup(exclude_paths=exclude_paths, dry_run=dry_run))
        return deleted

    def sync_memory(self) -> None:
        """Project canonical memory to Claude's native memory dir."""
        try:
            from src.config.paths import get_claude_native_memory_dir

            native_dir = get_claude_native_memory_dir(PROJECT_ROOT, create=True)
            if not native_dir:
                logger.info("Claude native memory dir not found, skipping")
                return
            memory_content = self.get_projected_memory_content()
            if not memory_content:
                return
            (native_dir / "MEMORY.md").write_text(memory_content, encoding="utf-8")
            logger.info("✅ Claude native memory dir ready at %s", native_dir)
        except Exception as e:
            logger.error("Failed to verify Claude memory dir: %s", e)


# ---------------------------------------------------------------------------
# Agent .md parser — reads hand-authored .claude/agents/*.md into registry
# entries matching schema 2.0.
# ---------------------------------------------------------------------------

def _parse_agent_md(path: Path) -> dict | None:
    """Parse a hand-authored agent .md file into a registry entry dict.

    Extracts:
      - mode, model (+ optional mcpServers, isolation, hooks) from YAML frontmatter
      - role from body text ("executor mode" / "advisor mode" / "orchestrator mode")
      - tools from "## Allowed Tools" section
      - tiers from "## Available Tiers" section
      - safety from "## Safety Constraints" section
      - escalation from "## Escalation Rules" section

    Returns a dict compatible with registry.json schema 2.0, or None on
    parse failure.
    """
    content = path.read_text(encoding="utf-8")

    # Strip HTML comment header if present (legacy AUTO-GENERATED marker)
    content = re.sub(r"^<!--.*?-->\s*", "", content, count=1, flags=re.DOTALL)

    # Split frontmatter / body
    fm, body = _split_frontmatter(content)
    if fm is None:
        logger.warning(f"No YAML frontmatter in {path.name}")
        return None

    model = fm.get("model", "sonnet")
    # Detect role from body text
    role = _detect_role(body)

    # Parse sections
    tools = _extract_bullet_list(body, "Allowed Tools")
    tiers = _extract_tiers(body, role, tools)
    safety = _extract_safety(body)
    escalation = _extract_escalation(body)

    entry: dict = {
        "role": role,
        "defaultModel": model,
        "tools": tools,
        "master_client": fm.get("x-augur-master", "claude-code"),
        "tiers": tiers,
        "safety": safety,
        "escalation": escalation,
    }

    # Optional enrichment fields from frontmatter
    if fm.get("mcpServers"):
        entry["mcp_servers"] = fm["mcpServers"]
    if fm.get("hooks"):
        entry["hooks"] = fm["hooks"]
    if fm.get("isolation"):
        entry["isolation"] = fm["isolation"]

    return entry


def _split_frontmatter(content: str) -> tuple[dict | None, str]:
    """Split content into parsed YAML frontmatter dict and markdown body."""
    if not content.startswith("---"):
        return None, content

    lines = content.splitlines()
    end_idx = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_idx = i
            break

    if end_idx is None:
        return None, content

    raw_fm = "\n".join(lines[1:end_idx])
    try:
        fm = yaml.safe_load(raw_fm)
    except yaml.YAMLError as e:
        logger.warning(f"Failed to parse YAML frontmatter: {e}")
        return None, content

    body = "\n".join(lines[end_idx + 1:]).strip()
    return fm if isinstance(fm, dict) else None, body


def _detect_role(body: str) -> str:
    """Detect agent role from body text patterns."""
    lower = body.lower()
    if "orchestrator mode" in lower:
        return "orchestrator"
    if "advisor" in lower and "mode" in lower:
        # Match "advisory mode" or "advisor mode"
        if "advisory mode" in lower or "advisor mode" in lower:
            return "advisor"
    if "executor mode" in lower:
        return "executor"
    # Fallback: check the **Role**: line
    m = re.search(r"\*\*Role\*\*:\s*(\w+)", body)
    if m:
        return m.group(1).lower()
    return "executor"


def _extract_bullet_list(body: str, heading: str) -> list[str]:
    """Extract bullet-point items from a markdown section by heading."""
    pattern = rf"##\s+{re.escape(heading)}\s*\n((?:.*\n)*?)(?:\n##|\Z)"
    match = re.search(pattern, body)
    if not match:
        return []
    items = []
    for line in match.group(1).splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            items.append(stripped[2:].strip())
    return items


def _extract_tiers(body: str, role: str, agent_tools: list[str]) -> dict:
    """Extract tier definitions from '## Available Tiers' section.

    Parses lines like:
      - **fast**: `haiku` (auto)
      - **standard**: `sonnet` (auto) <- default

    Populates each tier's tools list: fast tiers get read-only tools,
    standard/deep tiers inherit the full agent tools list.
    Advisor roles get advisor-appropriate budget/cost/appropriateFor defaults.
    """
    pattern = r"##\s+Available Tiers\s*\n((?:.*\n)*?)(?:\n##|\Z)"
    match = re.search(pattern, body)
    if not match:
        return {}

    is_advisor = role == "advisor"
    read_only_tools = [t for t in agent_tools if t in ("Read", "Glob", "Grep")]

    # Defaults differ by role
    if is_advisor:
        budget_map = {"fast": 16000, "standard": 64000, "deep": 200000}
        appropriate_map = {
            "fast": ["quick lookups", "file checks"],
            "standard": ["analysis", "recommendations", "code review"],
            "deep": ["security audits", "architecture review", "vulnerability analysis"],
        }
    else:
        budget_map = {"fast": 32000, "standard": 128000, "deep": 200000}
        appropriate_map = {
            "fast": ["simple lookups", "file checks", "pattern searches"],
            "standard": ["implementation", "bug fixes", "test writing"],
            "deep": ["architecture", "complex debugging", "cross-system refactoring"],
        }
    cost_map = {"fast": 0.1, "standard": 1.0, "deep": 5.0}

    tiers: dict = {}
    # Match: - **tier_name**: `model` (mode)
    tier_re = re.compile(r"-\s+\*\*(\w+)\*\*:\s+`(\w+)`\s+\((\w+)\)")
    for line in match.group(1).splitlines():
        m = tier_re.search(line)
        if m:
            tier_name, tier_model, _tier_mode = m.group(1), m.group(2), m.group(3)

            # Fast tiers get read-only tools; others get full tools
            tier_tools = read_only_tools if tier_name == "fast" else list(agent_tools)

            tier_entry: dict = {
                "model": tier_model,
                "tools": tier_tools,
                "contextBudget": budget_map.get(tier_name, 128000),
                "costMultiplier": cost_map.get(tier_name, 1.0),
            }
            if tier_name in appropriate_map:
                tier_entry["appropriateFor"] = appropriate_map[tier_name]
            tiers[tier_name] = tier_entry

    return tiers


def _extract_safety(body: str) -> dict:
    """Extract safety constraints from '## Safety Constraints' section."""
    pattern = r"##\s+Safety Constraints\s*\n((?:.*\n)*?)(?:\n##|\Z)"
    match = re.search(pattern, body)
    if not match:
        return {}

    section = match.group(1)
    safety: dict = {}

    # Max file edits
    m = re.search(r"Maximum\s+(\d+)\s+file\s+edits", section)
    if m:
        safety["maxFileEdits"] = int(m.group(1))

    # Banned paths (NEVER modify files matching: ...)
    m = re.search(r"NEVER modify files matching:\s*(.+)", section)
    if m:
        paths = [p.strip().strip("`") for p in m.group(1).split(",")]
        safety["bannedPaths"] = [p for p in paths if p]

    # Banned operations (NEVER execute: ...)
    m = re.search(r"NEVER execute:\s*(.+)", section)
    if m:
        ops = [o.strip().strip("`") for o in m.group(1).split(",")]
        safety["bannedOperations"] = [o for o in ops if o]
    else:
        safety.setdefault("bannedOperations", [])

    return safety


def _extract_escalation(body: str) -> dict:
    """Extract escalation rules from '## Escalation Rules' section."""
    pattern = r"##\s+Escalation Rules\s*\n((?:.*\n)*?)(?:\n##|\Z)"
    match = re.search(pattern, body)
    if not match:
        return {}

    section = match.group(1)
    escalation: dict = {}

    # Path: fast -> standard -> deep -> parent
    m = re.search(r"Path:\s*(.+)", section)
    if m:
        escalation["path"] = m.group(1).strip()

    # Maximum N escalations per task
    m = re.search(r"Maximum\s+(\d+)\s+escalation", section)
    if m:
        escalation["maxEscalations"] = int(m.group(1))

    return escalation
