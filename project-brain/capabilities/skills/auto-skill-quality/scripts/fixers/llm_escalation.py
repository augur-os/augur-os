"""LLM escalation — generate prompts for LLM-powered skill improvement."""
from __future__ import annotations


import importlib.util as _augur_importlib_util
import sys as _augur_sys
from pathlib import Path as _AugurPath

_augur_bootstrap_start = _AugurPath(__file__).resolve()
for _augur_bootstrap_parent in (_augur_bootstrap_start.parent, *_augur_bootstrap_start.parents):
    _augur_bootstrap_path = _augur_bootstrap_parent / "daemon" / "scripts" / "bootstrap_paths.py"
    if _augur_bootstrap_path.is_file():
        break
else:
    raise RuntimeError(f"Unable to locate shared skill bootstrap from {_augur_bootstrap_start}")

_augur_bootstrap_spec = _augur_importlib_util.spec_from_file_location(
    "_augur_shared_bootstrap_paths", _augur_bootstrap_path
)
if _augur_bootstrap_spec is None or _augur_bootstrap_spec.loader is None:
    raise RuntimeError(f"Unable to load shared skill bootstrap from {_augur_bootstrap_path}")
_augur_bootstrap_module = _augur_importlib_util.module_from_spec(_augur_bootstrap_spec)
_augur_sys.modules[_augur_bootstrap_spec.name] = _augur_bootstrap_module
_augur_bootstrap_spec.loader.exec_module(_augur_bootstrap_module)
_augur_bootstrap_module.ensure_project_paths(__file__)
from src.lib.frontmatter_utils import parse_frontmatter
from src.lib.ops_protocol import OpsContext


def llm_fix(ctx: OpsContext, issues: list[dict]) -> str:
    """Return a prompt for LLM-powered skill improvement.

    Called by the engine when fix() returns no changes (plateau).
    Returns a prompt string — the engine handles dispatch and safety.
    """
    if not issues:
        return ""

    # Group issues by skill, pick the worst one
    by_skill: dict[str, list[dict]] = {}
    for issue in issues:
        sname = issue.get("skill_name", "")
        if sname:
            by_skill.setdefault(sname, []).append(issue)

    if not by_skill:
        return ""

    # Pick the skill with the lowest score
    worst_skill = min(by_skill.keys(), key=lambda s: min(
        i.get("score", 100) for i in by_skill[s]
    ))
    skill_issues = by_skill[worst_skill]
    skill_dir = ctx.project_root / "project-brain" / "capabilities" / "skills" / worst_skill

    # Read skill context
    skill_md = skill_dir / "SKILL.md"
    description = ""
    hub = "system"
    if skill_md.exists():
        try:
            fm, body = parse_frontmatter(skill_md)
            description = fm.get("description", "")
            hub = (fm.get("x-augur-config") or {}).get("hub", "system")
        except Exception:
            pass

    # Build dimension breakdown
    dim_lines = []
    for issue in skill_issues:
        dim = issue.get("dimension", "unknown")
        score = issue.get("score", 0)
        detail = issue.get("detail", "")
        dim_lines.append(f"- {dim}: {score}/100 — {detail}")

    # Determine the worst dimension
    worst_dim = min(skill_issues, key=lambda i: i.get("score", 100)).get("dimension", "product")

    dim_instructions = {
        "instruction": (
            "Rewrite the SKILL.md to be genuinely useful. Read the skill's code, "
            "scripts, data, and page components to understand what it does. Write a "
            "description (20+ words) that tells a user: what problem this solves, when "
            "to use it, what they'll see on the dashboard. Add ## Overview, ## Usage, "
            "and ## Configuration sections with real content."
        ),
        "product": (
            "This skill lacks MCP tools or API routes. Create:\n"
            "1. A minimal MCP tool that returns useful data. Register it via "
            "@mcp.tool(name=...) following the pattern in existing tools under "
            "src/mcp/augur_framework/. The tool should return JSON relevant to this skill.\n"
            "2. An API route at apps/dashboard/app/api/{skill}/route.ts that calls "
            "the MCP tool via callMCPTool() from @/lib/mcp/MCPBridge.\n"
            "3. If vault data is empty, create seed files in assets/seeds/ with realistic "
            "sample data that would make the dashboard page look populated."
        ),
        "ui": (
            "Dashboard pages are missing or in mock/dev state. If page components "
            "exist in augur/dashboard/, promote their state in SKILL.md frontmatter "
            "x-augur-config.contributions.pages[].state from mock to dev (if .tsx "
            "files exist) or dev to mature (if data is populated). If no pages exist, "
            "create a minimal page.tsx in augur/dashboard/ that displays the skill's data."
        ),
        "wiring": (
            "API routes have issues. Check apps/dashboard/app/api/ for routes that "
            "reference this skill. Fix:\n"
            "- Replace any fs/spawn/exec imports with MCP tool calls via callMCPTool()\n"
            "- Update stale toolName references to match actual @mcp.tool registrations\n"
            "- Remove empty gracefulFallback objects that mask failures"
        ),
    }

    instructions = dim_instructions.get(worst_dim, dim_instructions["product"])

    prompt = f"""You are improving the "{worst_skill}" skill to reach tier A quality.

## Current Score
{chr(10).join(dim_lines)}

## Skill Context
- Hub: {hub}
- Purpose: {description or 'No description'}
- Path: project-brain/capabilities/skills/{worst_skill}/

## Bottleneck: {worst_dim}
{instructions}

## Rules
- Commit each meaningful change: git commit -m "auto(skill-quality): {worst_skill} — <what changed>"
- Only modify files in skills/{worst_skill}/ and apps/dashboard/app/api/
- If creating MCP tools, put them in the owning skill's scripts/mcp/ package or the canonical src/mcp/augur_framework/ tree for framework-owned tools
- Follow existing codebase patterns exactly — read examples before writing
- Do NOT break existing imports or other skills
- Keep changes minimal and focused
"""
    return prompt
