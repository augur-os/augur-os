"""
Crew SKILL.md Parser.

Parses crew skill SKILL.md files (YAML frontmatter + markdown body) into
SubagentProfile objects for Claude Code subagent generation.

Part of ADR-046: Claude Code Crew Orchestration Bridge.
"""

import re
from pathlib import Path
from typing import Optional

import yaml

from src.lib.ai.subagent_profile import EscalationConfig, SafetyConfig, SubagentProfile, TierProfile

from src.logging import get_entity_logger

logger = get_entity_logger("crew_parser")


def parse_crew_skill(skill_path: Path) -> Optional[SubagentProfile]:
    """
    Parse a crew SKILL.md file into a SubagentProfile.

    Args:
        skill_path: Path to the skill directory (containing SKILL.md)

    Returns:
        SubagentProfile or None if parsing fails
    """
    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        logger.warning(f"No SKILL.md found at {skill_path}")
        return None

    try:
        content = skill_md.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        logger.warning(f"Failed to read {skill_md}: {e}")
        return None

    frontmatter, body = _split_frontmatter(content)
    if frontmatter is None:
        logger.warning(f"No YAML frontmatter in {skill_md}")
        return None

    return _build_profile(skill_path.name, frontmatter, body)


def _split_frontmatter(content: str) -> tuple[Optional[dict], str]:
    """Split SKILL.md into parsed YAML frontmatter dict and markdown body."""
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

    # Strip @augur comment annotations before parsing YAML
    raw_fm = "\n".join(lines[1:end_idx])
    clean_fm = _strip_augur_annotations(raw_fm)

    try:
        fm = yaml.safe_load(clean_fm)
    except yaml.YAMLError as e:
        logger.warning(f"Failed to parse YAML frontmatter: {e}")
        return None, content

    body = "\n".join(lines[end_idx + 1 :]).strip()
    return fm if isinstance(fm, dict) else None, body


def _strip_augur_annotations(text: str) -> str:
    """Strip # @augur, # @augur-start, # @augur-end comments from YAML."""
    return re.sub(r"\s*#\s*@augur(?:-(?:start|end))?\s*$", "", text, flags=re.MULTILINE)


def _build_profile(skill_name: str, fm: dict, body: str) -> SubagentProfile:
    """Build a SubagentProfile from parsed frontmatter and body."""
    # Parse tiers
    tiers = {}
    for tier_name, tier_data in (fm.get("tiers") or {}).items():
        if not isinstance(tier_data, dict):
            continue
        tiers[tier_name] = TierProfile(
            capability=tier_data.get("capability", "balanced"),
            mode=tier_data.get("mode", "advisory"),
            tools=tier_data.get("tools", []),
            max_files=str(tier_data.get("max_files", "5")),
            use_cases=tier_data.get("use_cases", []),
            escalate_when=tier_data.get("escalate_when", []),
        )

    # Parse safety
    safety_data = fm.get("safety") or {}
    read_only_data = safety_data.get("read_only_mode") or {}
    circuit_data = safety_data.get("circuit_breaker") or {}

    safety = SafetyConfig(
        read_only=read_only_data.get("enabled", True),
        iron_law=safety_data.get("iron_law", ""),
        circuit_breaker_max_failures=circuit_data.get("max_consecutive_failures", 3),
        circuit_breaker_action=circuit_data.get("action", "escalate_to_human"),
        verification_required=safety_data.get("verification_required", []),
        protected_areas=safety_data.get("protected_areas", []),
    )

    # Parse body sections
    capabilities = _extract_list_section(body, "Capabilities")
    constraints = _extract_list_section(body, "Constraints")
    chain_lines = _extract_list_section(body, "Chain Integration")

    # Build display name
    display_name = skill_name.replace("-", " ").title()

    # ADR-460: Parse x-augur-agent fields
    agent_data = fm.get("x-augur-agent") or {}
    agent_role = agent_data.get("role", "")
    agent_default_model = agent_data.get("default-model", "")
    agent_tools = agent_data.get("tools", [])

    # ADR-460: Schema validation (best-effort)
    if agent_data:
        try:
            import json as _json

            import jsonschema

            _schema_path = (
                Path(__file__).resolve().parents[5] / "src" / "config" / "schemas" / "agent-profile.schema.json"
            )
            if _schema_path.exists():
                _schema = _json.loads(_schema_path.read_text())
                jsonschema.validate(agent_data, _schema)
        except ImportError:
            pass  # jsonschema not installed
        except Exception as e:
            logger.warning("x-augur-agent validation failed in %s: %s", skill_name, e)

    # ADR-460: Parse tiers from x-augur-agent
    from src.lib.ai.subagent_profile import ROLE_TO_CLAUDE_MODE

    tiers_raw = agent_data.get("tiers", {})
    for tier_name, tier_data in tiers_raw.items():
        if not isinstance(tier_data, dict):
            continue
        # Map tier name to capability for model lookup
        cap_map = {"fast": "fast", "standard": "balanced", "deep": "reasoning"}
        capability = cap_map.get(tier_name, "balanced")
        claude_mode = ROLE_TO_CLAUDE_MODE.get(agent_role, "plan")
        tiers[tier_name] = TierProfile(
            capability=capability,
            mode=claude_mode,
            tools=tier_data.get("tools", agent_tools),
            max_files=str(tier_data.get("context-budget", 128000)),
            use_cases=tier_data.get("appropriate-for", []),
            escalate_when=tier_data.get("inappropriate-for", []),
            cost_multiplier=tier_data.get("cost-multiplier", 1.0),
        )

    # ADR-460: Parse safety from x-augur-agent
    safety_raw = agent_data.get("safety", {})
    if safety_raw:
        safety = SafetyConfig(
            max_file_edits=safety_raw.get("max-file-edits-per-run", 20),
            max_file_creates=safety_raw.get("max-file-creates-per-run", 5),
            max_bash_commands=safety_raw.get("max-bash-commands-per-run", 30),
            banned_paths=tuple(safety_raw.get("banned-paths", [])),
            require_confirmation=tuple(safety_raw.get("require-confirmation", [])),
            banned_operations=tuple(safety_raw.get("banned-operations", [])),
            read_only=read_only_data.get("enabled", True),
            iron_law=safety_data.get("iron_law", ""),
            circuit_breaker_max_failures=circuit_data.get("max_consecutive_failures", 3),
            circuit_breaker_action=circuit_data.get("action", "escalate_to_human"),
            verification_required=safety_data.get("verification_required", []),
            protected_areas=safety_data.get("protected_areas", []),
        )

    # ADR-460: Parse escalation from x-augur-agent
    esc_raw = agent_data.get("escalation", {})
    escalation = None
    if esc_raw:
        escalation = EscalationConfig(
            auto_escalate_on=tuple(esc_raw.get("auto-escalate-on", [])),
            escalation_path=esc_raw.get("escalation-path", "fast -> standard -> deep -> parent"),
            max_escalations=esc_raw.get("max-escalations-per-task", 2),
            cooldown_seconds=esc_raw.get("cooldown", 300),
        )

    # ADR-145: Parse enrichment fields from metadata section
    metadata = fm.get("x-augur-metadata") or fm.get("metadata") or {}
    skills = metadata.get("skills", [])
    memory = metadata.get("memory", "")
    max_turns = metadata.get("maxTurns", 0)
    mcp_servers = metadata.get("mcpServers") or metadata.get("mcp-server", [])
    if isinstance(mcp_servers, str):
        mcp_servers = [mcp_servers]
    agent_hooks = metadata.get("hooks", {})
    isolation = metadata.get("isolation", "")

    return SubagentProfile(
        name=skill_name,
        display_name=display_name,
        description=fm.get("description", ""),
        version=fm.get("version", "0.1.0"),
        tiers=tiers,
        safety=safety,
        escalation=escalation,
        capabilities=capabilities,
        constraints=constraints,
        chain_participation=chain_lines,
        triggers=fm.get("triggers", []),
        agent_role=agent_role,
        agent_default_model=agent_default_model,
        agent_tools=agent_tools,
        skills=skills,
        memory=memory,
        max_turns=max_turns,
        mcp_servers=mcp_servers,
        agent_hooks=agent_hooks,
        isolation=isolation,
    )


def _extract_list_section(body: str, heading: str) -> list[str]:
    """Extract bullet points from a markdown section by heading."""
    pattern = rf"##\s+{re.escape(heading)}\s*\n((?:.*\n)*?)\n(?:##|\Z)"
    match = re.search(pattern, body)
    if not match:
        return []

    items = []
    for line in match.group(1).splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            items.append(stripped[2:].strip())
    return items


def scan_crew_skills(project_root: Path | None = None) -> list[SubagentProfile]:
    """
    Scan all crew skills and parse them into SubagentProfiles.

    Uses discover_all_skills() for canonical skill scanning instead of
    manually walking skills/. Only skills declaring x-augur-agent
    generate subagent profiles.

    Args:
        project_root: Accepted for API compatibility but unused (discovery
            handles root resolution internally).

    Returns:
        List of SubagentProfile objects, sorted by name
    """
    from src.plugins.skill_discovery import discover_all_skills

    results = []
    for rec in discover_all_skills():
        if not rec.agent:
            continue
        profile = parse_crew_skill(rec.path)
        if profile and profile.agent_role:
            results.append(profile)
    return results
