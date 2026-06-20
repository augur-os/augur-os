"""
Command Rewriter for Adaptive Slash Commands (ADR-102)

Rewrites SKILL.md and chain YAML files based on improvement suggestions.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

import yaml

from .analyze_execution import Improvement, ImprovementType


_MAX_EVOLUTION_COMMENTS_PER_FILE = 3
_MAX_KNOWN_ISSUES_PER_FILE = 2


def _already_has_improvement(content: str, improvement: Improvement) -> bool:
    """Check if this improvement (or an equivalent one) already exists in the file."""
    desc = (improvement.description or "").strip()
    evidence = str(improvement.evidence or "").strip()

    # Check for duplicate evolution metadata comments (full description match)
    if desc and desc in content:
        return True
    # Check for duplicate Known Issue blocks with same evidence
    if evidence and evidence in content:
        return True
    return False


def _cap_evolution_comments(content: str) -> str:
    """Ensure no more than _MAX_EVOLUTION_COMMENTS_PER_FILE evolution comments exist."""
    lines = content.split("\n")
    evolution_indices = [
        i for i, line in enumerate(lines)
        if "<!-- ADR-102 Evolution:" in line
    ]
    if len(evolution_indices) <= _MAX_EVOLUTION_COMMENTS_PER_FILE:
        return content
    # Keep only the most recent N (last N in file)
    to_remove = set(evolution_indices[:-_MAX_EVOLUTION_COMMENTS_PER_FILE])
    lines = [line for i, line in enumerate(lines) if i not in to_remove]
    return "\n".join(lines)


def _cap_known_issues(content: str) -> str:
    """Ensure no more than _MAX_KNOWN_ISSUES_PER_FILE Known Issue blocks exist."""
    # Count existing Known Issue blocks
    count = content.count("### Known Issue (ADR-102)")
    if count <= _MAX_KNOWN_ISSUES_PER_FILE:
        return content
    # Remove oldest blocks (first occurrences) keeping only the last N
    parts = content.split("### Known Issue (ADR-102)")
    # parts[0] is before first block, parts[1:] are blocks
    blocks = parts[1:]
    keep = blocks[-_MAX_KNOWN_ISSUES_PER_FILE:]
    return parts[0] + "### Known Issue (ADR-102)".join([""] + keep)


def apply_improvement_to_skill(
    skill_path: Path,
    improvement: Improvement,
) -> bool:
    """Apply an improvement to a SKILL.md file.

    Idempotent: skips if an equivalent improvement already exists.
    Caps evolution comments and Known Issue blocks to prevent accumulation.
    """
    if not skill_path.exists():
        return False

    content = skill_path.read_text()

    # Dedup gate: skip if this improvement is already present
    if _already_has_improvement(content, improvement):
        return False

    if improvement.type == ImprovementType.ADD_HINT:
        content = _add_hint(content, improvement)
    elif improvement.type == ImprovementType.ADD_CHECK:
        content = _add_check(content, improvement)
    elif improvement.type == ImprovementType.ADD_TIMEOUT:
        content = _add_timeout_hint(content, improvement)
    elif improvement.type == ImprovementType.ADD_STEP:
        content = _add_step(content, improvement)
    elif improvement.type == ImprovementType.FIX_ERROR_PATTERN:
        content = _add_error_handling(content, improvement)
    else:
        return False

    content = _add_evolution_metadata(content, improvement)

    # Cap accumulated hints to prevent file bloat
    content = _cap_evolution_comments(content)
    content = _cap_known_issues(content)

    skill_path.write_text(content)
    return True


def _add_hint(content: str, improvement: Improvement) -> str:
    """Add a hint/learning note to the skill."""
    if improvement.target_phase:
        # Find the phase section and add hint after it
        pattern = rf"(## {re.escape(improvement.target_phase)}.*?)(\n## |\n---|\Z)"
        hint_block = f"\n\n**Learning (ADR-102):** {improvement.suggested_content}\n"
        return re.sub(pattern, r"\1" + hint_block + r"\2", content, flags=re.DOTALL)
    else:
        # Add at the end of the file
        hint_section = f"\n\n---\n\n## Adaptive Improvements (ADR-102)\n\n**{improvement.description}**\n\n{improvement.suggested_content}\n"
        return content + hint_section


def _add_check(content: str, improvement: Improvement) -> str:
    """Add a pre-check step to the skill."""
    check_block = f"""

### Pre-Check (ADR-102 Adaptive)

{improvement.suggested_content}

**Evidence:** {improvement.evidence or "From execution analysis"}

"""
    if improvement.target_phase:
        # Add before the target phase
        pattern = rf"(## {re.escape(improvement.target_phase)})"
        return re.sub(pattern, check_block + r"\n\1", content)
    return content


def _add_timeout_hint(content: str, improvement: Improvement) -> str:
    """Add timeout hint to a step."""
    if improvement.target_step:
        # Find the step and add timeout hint
        pattern = rf"({re.escape(improvement.target_step)}.*?)(\n\n|\n##|\n---)"
        timeout_hint = f"\n\n**Timeout Hint:** {improvement.suggested_content}\n"
        return re.sub(pattern, r"\1" + timeout_hint + r"\2", content, flags=re.DOTALL)
    return content


def _add_step(content: str, improvement: Improvement) -> str:
    """Add a new step/phase to the skill."""
    step_block = f"""

## {improvement.description}

{improvement.suggested_content}

**Model:** Haiku (automated check)

"""
    # Add before the final verification section
    if "## Final Verification" in content:
        return content.replace("## Final Verification", step_block + "## Final Verification")
    return content + step_block


def _add_error_handling(content: str, improvement: Improvement) -> str:
    """Add error handling note to the skill."""
    error_block = f"""

### Known Issue (ADR-102)

**Pattern:** {improvement.evidence}

**Resolution:** {improvement.suggested_content}

"""
    if "## Anti-Patterns" in content:
        return content.replace("## Anti-Patterns", error_block + "## Anti-Patterns")
    return content + error_block


def _add_evolution_metadata(content: str, improvement: Improvement) -> str:
    """Add evolution metadata to the skill file."""
    timestamp = datetime.now(timezone.utc).isoformat()
    evolution_line = (
        f"\n<!-- ADR-102 Evolution: {timestamp} - {improvement.type.value}: {improvement.description[:50]} -->\n"
    )

    # Add to front matter if exists
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            front_matter = parts[1]
            body = parts[2]
            # Add evolution to front matter
            if "x-augur-evolution:" not in front_matter:
                front_matter += (
                    f"\nx-augur-evolution:\n"
                    f"  last_updated: {timestamp}\n"
                    "  improvements_applied: 1\n"
                )
            return f"---{front_matter}---{evolution_line}{body}"

    return evolution_line + content


def apply_improvement_to_chain(
    chain_path: Path,
    improvement: Improvement,
) -> bool:
    """Apply an improvement to a chain YAML file."""
    if not chain_path.exists():
        return False

    with open(chain_path) as f:
        chain_data = yaml.safe_load(f)

    if not chain_data:
        return False

    if improvement.type == ImprovementType.ADD_TIMEOUT:
        # Add timeout to agents
        for agent in chain_data.get("agents", []):
            if agent.get("name") == improvement.target_step or agent.get("action") == improvement.target_step:
                agent["timeout_hint"] = improvement.suggested_content
                agent["adaptive_improvement"] = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "type": improvement.type.value,
                }

    elif improvement.type == ImprovementType.ADD_CHECK:
        # Add a pre-check agent
        check_agent = {
            "name": "validator",
            "action": f"precheck_{improvement.target_step or 'general'}",
            "description": improvement.suggested_content,
            "output": "precheck_result",
            "adaptive_improvement": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "type": improvement.type.value,
                "evidence": improvement.evidence,
            },
        }
        if "agents" not in chain_data:
            chain_data["agents"] = []
        chain_data["agents"].insert(0, check_agent)

    elif improvement.type == ImprovementType.ADD_CACHE:
        # Add cache key to agents
        for agent in chain_data.get("agents", []):
            if "cache_key" not in agent:
                agent["cache_key"] = f"{agent.get('name', 'unknown')}_{agent.get('action', 'unknown')}"

    else:
        return False

    # Update metadata
    if "metadata" not in chain_data:
        chain_data["metadata"] = {}
    chain_data["metadata"]["last_evolved"] = datetime.now(timezone.utc).isoformat()
    chain_data["metadata"]["evolution_count"] = chain_data["metadata"].get("evolution_count", 0) + 1

    with open(chain_path, "w") as f:
        yaml.dump(chain_data, f, default_flow_style=False, sort_keys=False)

    return True


def log_improvement(
    command_name: str,
    improvement: Improvement,
    runtime_dir: Path,
    applied: bool = True,
) -> Path:
    """Log an applied improvement for audit trail."""
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    log_dir = runtime_dir / "command-evolution" / command_name / "improvements"
    log_dir.mkdir(parents=True, exist_ok=True)

    status = "auto-applied" if applied and improvement.auto_apply.value == "yes" else "queued"
    log_path = log_dir / status / f"{timestamp}.yaml"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    log_data = {
        "timestamp": timestamp,
        "command": command_name,
        "type": improvement.type.value,
        "priority": improvement.priority.value,
        "auto_apply": improvement.auto_apply.value,
        "description": improvement.description,
        "target_phase": improvement.target_phase,
        "target_step": improvement.target_step,
        "suggested_content": improvement.suggested_content,
        "evidence": improvement.evidence,
        "status": "applied" if applied else "queued",
    }

    log_path.write_text(yaml.dump(log_data, default_flow_style=False))
    return log_path


def commit_skill_update(
    command_name: str,
    skill_path: Path | None,
    chain_path: Path | None,
    runtime_dir: Path,
) -> None:
    """Record a skill update in the evolution log."""
    evolution_log = runtime_dir / "command-evolution" / command_name / "evolution-log.md"

    timestamp = datetime.now(timezone.utc).isoformat()

    entry = f"""
## {timestamp}

Updated command `{command_name}` based on adaptive analysis.

**Files modified:**
"""
    if skill_path:
        entry += f"- {skill_path}\n"
    if chain_path:
        entry += f"- {chain_path}\n"

    entry += "\n---\n"

    if evolution_log.exists():
        existing = evolution_log.read_text()
        evolution_log.write_text(entry + existing)
    else:
        evolution_log.write_text(f"# Evolution Log: {command_name}\n\n{entry}")


def find_skill_definition(command_name: str, project_root: Path) -> Path | None:
    """Find the SKILL.md file for a command."""
    # Check ai skills first
    skill_path = (
        project_root / "plugins" / "ai" / "skills" / "ai" / "data" / "skills" / command_name / "SKILL.md"
    )
    if skill_path.exists():
        return skill_path

    # Check all bundles
    for bundle in [
        "core",
        "career",
        "growth",
        "finance",
        "health",
        "productivity",
        "integrations",
        "lifestyle",
        "creative",
        "home",
        "consulting",
        "venture",
        "enterprise",
        "ai",
        "admin",
        "observe",
        "dev",
    ]:
        skill_path = project_root / "plugins" / bundle / "skills" / command_name / "SKILL.md"
        if skill_path.exists():
            return skill_path

    return None


def find_chain_definition(command_name: str, project_root: Path) -> Path | None:
    """Find the chain YAML file for a command."""
    # Convert command name to possible chain names
    chain_names = [
        command_name.replace("-", "_"),
        command_name,
    ]

    for bundle in [
        "core",
        "career",
        "growth",
        "finance",
        "health",
        "productivity",
        "integrations",
        "lifestyle",
        "creative",
        "home",
        "consulting",
        "venture",
        "enterprise",
        "ai",
        "admin",
        "observe",
        "dev",
    ]:
        chains_dir = project_root / "plugins" / bundle / "skills"
        if chains_dir.exists():
            for skill_dir in chains_dir.iterdir():
                if skill_dir.is_dir():
                    chains_subdir = skill_dir / "chains"
                    if chains_subdir.exists():
                        for chain_name in chain_names:
                            chain_path = chains_subdir / f"{chain_name}.yaml"
                            if chain_path.exists():
                                return chain_path

    return None
