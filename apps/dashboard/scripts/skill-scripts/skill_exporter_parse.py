"""Skill SKILL.md parsing, marker stripping, and content generation.

Functions for parsing SKILL.md frontmatter and body, stripping
Augur-specific markers, and generating portable SKILL.md, agent
definitions, tier agents, and commands.

Split from skill_exporter.py for module size management.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))


def parse_skill_md(skill_path: Path) -> dict[str, Any]:
    """Parse SKILL.md into frontmatter dict and body markdown."""
    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        raise FileNotFoundError(f"SKILL.md not found at {skill_md}")

    content = skill_md.read_text(encoding="utf-8")

    # Split YAML frontmatter from markdown body
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            frontmatter_raw = parts[1].strip()
            body = parts[2].strip()
        else:
            frontmatter_raw = ""
            body = content
    else:
        frontmatter_raw = ""
        body = content

    # Parse YAML frontmatter
    frontmatter: dict[str, Any] = {}
    if frontmatter_raw:
        try:
            import yaml

            frontmatter = yaml.safe_load(frontmatter_raw) or {}
        except Exception as error:
            _out(f"Warning: failed to parse SKILL.md frontmatter: {error}", file=sys.stderr)

    return {
        "frontmatter": frontmatter,
        "frontmatter_raw": frontmatter_raw,
        "body": body,
        "raw": content,
    }


def strip_augur_markers_from_frontmatter(frontmatter_raw: str) -> str:
    """Strip lines marked with # @augur from YAML frontmatter.

    Handles both:
        - Individual line markers: `category: business  # @augur`
        - Block markers: `# @augur-start` ... `# @augur-end`
    """
    lines = frontmatter_raw.split("\n")
    filtered = []
    in_augur_block = False

    for line in lines:
        # Check for block markers
        stripped = line.strip()
        if "# @augur-start" in stripped or stripped == "# @augur-start":
            in_augur_block = True
            continue
        if "# @augur-end" in stripped or stripped == "# @augur-end":
            in_augur_block = False
            continue

        # Skip lines inside augur blocks
        if in_augur_block:
            continue

        # Skip individual augur-marked lines
        if "# @augur" in line:
            continue

        # Skip section comments about Augur extensions
        if "augur extensions" in stripped.lower():
            continue

        filtered.append(line)

    # Clean up: remove trailing empty lines and double blanks
    result = "\n".join(filtered)
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip()


def strip_augur_references_from_body(body: str) -> str:
    """Remove Augur-specific sections from the skill body."""
    lines = body.split("\n")
    filtered = []
    skip = False

    for line in lines:
        # Skip sections that reference Augur internals
        if any(
            marker in line.lower()
            for marker in [
                "## storage",
                "## chain integration",
                "plugins/data/",
                "~/projects/augur",
            ]
        ):
            skip = True
            continue

        # Resume at next heading
        if skip and line.startswith("## "):
            skip = False

        if skip and line.startswith("---"):
            skip = False
            continue

        if not skip:
            filtered.append(line)

    result = "\n".join(filtered).strip()

    # Remove trailing version line (e.g., "---\nVersion: 0.5.0 | Patterns: ...")
    result = re.sub(r"\n---\nVersion:.*", "", result)
    result = re.sub(r"\nVersion:.*$", "", result)

    return result


def generate_standard_frontmatter(parsed: dict[str, Any]) -> str:
    """Generate Layer 1 (Standard Core) frontmatter only."""
    fm_raw = parsed.get("frontmatter_raw", "")

    if fm_raw:
        # Use marker-based stripping
        return strip_augur_markers_from_frontmatter(fm_raw)
    else:
        # Fallback: build from parsed frontmatter
        fm = parsed["frontmatter"]
        import yaml

        standard_fm = {
            "name": fm.get("name", "unknown"),
            "version": fm.get("version", "1.0.0"),
            "description": fm.get("description", ""),
        }
        triggers = fm.get("triggers", [])
        if triggers:
            standard_fm["triggers"] = triggers

        return yaml.dump(standard_fm, default_flow_style=False, allow_unicode=True).strip()


def generate_exported_skill_md(parsed: dict[str, Any]) -> str:
    """Generate a portable SKILL.md with only Layer 1 content."""
    fm_str = generate_standard_frontmatter(parsed)
    body = strip_augur_references_from_body(parsed["body"])

    return f"---\n{fm_str}\n---\n\n{body}\n"


def generate_agent_md(parsed: dict[str, Any]) -> str:
    """Generate an agent definition markdown for agents/ directory."""
    fm = parsed["frontmatter"]
    name = fm.get("name", "unknown")
    description = fm.get("description", "")

    # Extract capabilities from body
    body = parsed["body"]

    capabilities = []
    in_capabilities = False
    for line in body.split("\n"):
        if "## Capabilities" in line or "## Overview" in line:
            in_capabilities = True
            continue
        if in_capabilities and line.startswith("## "):
            break
        if in_capabilities and line.startswith("- "):
            capabilities.append(line)

    caps_str = "\n".join(capabilities) if capabilities else f"- {description}"

    constraints = []
    in_constraints = False
    for line in body.split("\n"):
        if "## Constraints" in line:
            in_constraints = True
            continue
        if in_constraints and line.startswith("## "):
            break
        if in_constraints and line.startswith("- "):
            constraints.append(line)

    constraints_str = "\n".join(constraints) if constraints else ""

    agent_md = f"""# {name.title()} Agent

{description}

## Capabilities
{caps_str}
"""

    if constraints_str:
        agent_md += f"""
## Constraints
{constraints_str}
"""

    # Add tier info if available
    tiers = fm.get("tiers", {})
    if tiers:
        agent_md += "\n## Tier Configuration\n"
        for tier_name, tier_config in tiers.items():
            if isinstance(tier_config, dict):
                capability = tier_config.get("capability", tier_name)
                mode = tier_config.get("mode", "advisory")
                use_cases = tier_config.get("use_cases", [])
                cases_str = ", ".join(use_cases[:3]) if use_cases else "General tasks"
                agent_md += f"- **{tier_name}** ({capability}): {mode} mode - {cases_str}\n"

    return agent_md.strip() + "\n"


def generate_tier_agents(parsed: dict[str, Any]) -> dict[str, str]:
    """Generate per-tier agent files (fast/deep variants)."""
    fm = parsed["frontmatter"]
    name = fm.get("name", "unknown")
    description = fm.get("description", "")
    tiers = fm.get("tiers", {})

    if not tiers:
        return {}

    agents = {}

    tier_mapping = {
        "low": "fast",
        "medium": "standard",
        "high": "deep",
        "fast": "fast",
        "standard": "standard",
        "deep": "deep",
    }

    for tier_name, tier_config in tiers.items():
        if not isinstance(tier_config, dict):
            continue

        standard_tier = tier_mapping.get(tier_name, tier_name)
        if standard_tier not in ("fast", "deep"):
            continue

        capability = tier_config.get("capability", standard_tier)
        mode = tier_config.get("mode", "advisory")
        tools = tier_config.get("tools", [])
        use_cases = tier_config.get("use_cases", [])
        escalate_when = tier_config.get("escalate_when", [])
        max_files = tier_config.get("max_files", "unlimited")

        tools_str = ", ".join(str(t) for t in tools) if tools else "All available tools"
        cases_str = "\n".join(f"- {case}" for case in use_cases) if use_cases else f"- {description}"
        escalate_str = ""
        if escalate_when:
            escalate_str = "\n## When to Escalate\n" + "\n".join(f"- {cond}" for cond in escalate_when)

        agent_md = f"""# {name.title()} Agent ({standard_tier.title()} Tier)

{description}

**Tier**: {standard_tier} ({capability})
**Mode**: {mode}
**Available Tools**: {tools_str}
**Max Files**: {max_files}

## Best Used For
{cases_str}
{escalate_str}

## Instructions

When operating in {standard_tier} tier:
- Use only the tools listed above
- {"Request approval before making changes" if mode == "advisory" else "Execute changes directly"}
- {"Escalate to a higher tier if the task exceeds your scope" if standard_tier == "fast" else "This is the highest capability tier - handle complex tasks thoroughly"}
"""
        agents[f"{name}-{standard_tier}"] = agent_md.strip() + "\n"

    return agents


def generate_commands(parsed: dict[str, Any]) -> dict[str, str]:
    """Generate command markdown files from triggers."""
    fm = parsed["frontmatter"]
    name = fm.get("name", "unknown")
    description = fm.get("description", "")
    triggers = fm.get("triggers", [])

    commands = {}

    if triggers:
        primary = triggers[0]
        slug = primary.replace(" ", "-").lower()

        cmd_content = f"""---
description: {description}
---

{parsed['body'].split('## Commands')[0].strip().split('## Capabilities')[0].strip()}

When invoked, act as the {name} agent and handle the user's request.
Use $ARGUMENTS as the task specification.
"""
        commands[slug] = cmd_content

    return commands
