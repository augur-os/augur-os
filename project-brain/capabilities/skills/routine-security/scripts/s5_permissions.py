"""S5: Permissions and policy compliance checks."""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

_ASQ_SCRIPTS = Path(__file__).resolve().parents[2] / "auto-skill-quality" / "scripts"
if str(_ASQ_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_ASQ_SCRIPTS))
from standard_skill_contract import is_standard_core  # noqa: E402


# Policy rules (can be loaded from docs/references/skill-policy.md in future)
_POLICY_RULES = [
    {
        "id": "POL-001",
        "name": "overly-broad-mcp-tools",
        "severity": "medium",
        "check": lambda fm: len(fm.get("x-augur-mcp-tools", [])) > 20,
        "message": "Skill declares more than 20 MCP tools — review for scope creep",
    },
    # POL-002 (missing-hub) removed: ADR-802 deleted the x-augur-hub field
    # and the entire hub concept — requiring it quarantined ~40 valid skills.
    {
        "id": "POL-003",
        "name": "no-release-tag",
        "severity": "low",
        "check": lambda fm: not fm.get("x-augur-release"),
        "message": "Skill missing x-augur-release tag",
    },
    {
        "id": "POL-004",
        "name": "no-commands-declared",
        "severity": "low",
        "check": lambda fm: not fm.get("x-augur-commands"),
        "message": "Skill has no commands declared — is it usable?",
    },
]

# Standard cores (ADR-040) omit Augur frontmatter by design; these metadata
# policy rules do not apply to them. Real scope checks (overly-broad-mcp-tools)
# still run.
_CORE_EXEMPT_RULES = {"no-release-tag", "no-commands-declared"}


def scan_skill(skill_dir: Path, is_augur_managed: bool = True) -> list[dict]:
    """Scan a skill directory for policy violations.

    Args:
        skill_dir: Path to the skill directory.
        is_augur_managed: If True, enforce Augur-specific policy rules.
            External skills (tier>=1) should pass False.
    """
    findings = []
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return findings

    # Skip Augur policy checks for external skills
    if not is_augur_managed:
        return findings

    try:
        content = skill_md.read_text(encoding="utf-8")
        if content.startswith("---"):
            end = content.index("---", 3)
            fm = yaml.safe_load(content[3:end])
        else:
            fm = {}
    except Exception:
        return findings

    if not isinstance(fm, dict):
        fm = {}

    core = is_standard_core(skill_dir)
    for rule in _POLICY_RULES:
        if core and rule["name"] in _CORE_EXEMPT_RULES:
            continue
        try:
            if rule["check"](fm):
                findings.append({
                    "stage": "S5",
                    "category_name": rule["name"],
                    "severity": rule["severity"],
                    "file": "SKILL.md",
                    "line": 0,
                    "message": rule["message"],
                    "pattern": rule["id"],
                })
        except Exception:
            continue

    return findings
