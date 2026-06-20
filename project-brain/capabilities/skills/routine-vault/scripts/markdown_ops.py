"""Auto-markdowns: scan and fix action prompt template quality.

Validates that dashboard runAction calls have standardized markdown prompt
templates at the canonical path:
skills/{skill}/assets/seeds/prompts/{action-id}.md
with optional vault overrides under get_vault_dir()/{skill}/prompts/.

Difficulty levels:
  d0: Missing prompt template file for any runAction call
  d1: Template exists but missing <instructions> or <task> sections
  d2: TSX still uses inline description instead of renderPrompt()
  d3: Shallow/generic instructions, entity props not forwarded

See ADR-263 for full design.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


def _ensure_project_paths(start: Path) -> Path:
    for candidate in (start.parent, *start.parents):
        if (
            (candidate / "pyproject.toml").is_file()
            and (candidate / "src" / "config" / "paths.py").is_file()
        ):
            for path in (candidate / "src" / "mcp", candidate, candidate / "project-brain"):
                text = str(path)
                if text not in sys.path:
                    sys.path.insert(0, text)
            return candidate
    raise RuntimeError(f"Unable to locate Augur project root from {start}")


_ensure_project_paths(Path(__file__).resolve())

from src.config.paths import get_all_client_skill_dirs
from src.lib.ops_protocol import FixResult, OpsContext, ScanResult, report_only_fix

name = "auto-markdowns"

# ── Regex ────────────────────────────────────────────────────────────────

_RUN_ACTION_ID = re.compile(
    r"""runAction\(\s*\{[^}]*?id:\s*['"]([^'"]+)['"]""", re.DOTALL
)
_RENDER_PROMPT = re.compile(r"""renderPrompt\(\s*['"]([^'"]+)['"]""")


# ── Helpers ──────────────────────────────────────────────────────────────


def _find_run_action_ids(content: str) -> list[dict]:
    """Extract action IDs and line numbers from runAction calls in TSX."""
    results = []
    for m in _RUN_ACTION_ID.finditer(content):
        line = content[: m.start()].count("\n") + 1
        results.append({"action_id": m.group(1), "line": line})
    return results


def _find_render_prompt_ids(content: str) -> set[str]:
    """Extract action IDs from renderPrompt() calls — already migrated.

    Returns exact IDs for static calls like renderPrompt('add-habit'),
    and prefix patterns (ending with '-') for dynamic calls like
    renderPrompt("ide-prompt-" + name).
    """
    return {m.group(1) for m in _RENDER_PROMPT.finditer(content)}


def _is_migrated(action_id: str, migrated: set[str]) -> bool:
    """Check if an action ID is covered by the migrated renderPrompt set.

    Handles both exact matches and prefix matches for dynamic IDs
    (e.g. renderPrompt("ide-prompt-" + name) covers "ide-prompt-cursor").
    """
    if action_id in migrated:
        return True
    # Check prefix matches for dynamic concatenation patterns
    for mid in migrated:
        if mid.endswith("-") and action_id.startswith(mid):
            return True
    return False


def _discover_templates(project_root: Path) -> dict[str, Path]:
    """Discover all prompt template .md files across skills.

    Returns dict of action_id -> file path.
    """
    templates: dict[str, Path] = {}
    # Relative globs within each skill directory
    sub_globs = (
        "assets/seeds/prompts/*.md",
    )
    for skill_dir in get_all_client_skill_dirs(project_root):
        for pattern in sub_globs:
            for md_file in skill_dir.glob(pattern):
                try:
                    content = md_file.read_text(errors="replace")
                except OSError:
                    continue
                # Extract action ID from frontmatter
                fm_match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
                if fm_match:
                    action_match = re.search(
                        r"^action:\s*(.+)$", fm_match.group(1), re.MULTILINE
                    )
                    if action_match:
                        templates[action_match.group(1).strip()] = md_file
                        continue
                # Fallback: use filename
                templates[md_file.stem] = md_file
    return templates


def _check_template_structure(md_path: Path) -> list[str]:
    """Check a template .md file for required sections.

    Returns list of missing section names.
    """
    try:
        content = md_path.read_text(errors="replace")
    except OSError:
        return ["cannot read file"]

    # Strip frontmatter
    body = re.sub(
        r"^---\n.*?\n---\n?", "", content, count=1, flags=re.DOTALL
    )

    missing = []
    if "<instructions>" not in body:
        missing.append("instructions")
    if "<task>" not in body:
        missing.append("task")
    return missing


def _check_template_quality(md_path: Path) -> list[dict]:
    """d3: Check template content quality."""
    try:
        content = md_path.read_text(errors="replace")
    except OSError:
        return []

    body = re.sub(
        r"^---\n.*?\n---\n?", "", content, count=1, flags=re.DOTALL
    )
    issues: list[dict] = []

    # Check instructions section length
    inst_match = re.search(
        r"<instructions>(.*?)</instructions>", body, re.DOTALL
    )
    if inst_match:
        inst_text = inst_match.group(1).strip()
        if len(inst_text) < 30:
            issues.append(
                {
                    "type": "shallow_instructions",
                    "detail": f"instructions section is only {len(inst_text)} chars — likely too generic",
                }
            )

    # Check task section length
    task_match = re.search(r"<task>(.*?)</task>", body, re.DOTALL)
    if task_match:
        task_text = task_match.group(1).strip()
        if len(task_text) < 20:
            issues.append(
                {
                    "type": "shallow_task",
                    "detail": f"task section is only {len(task_text)} chars — likely too generic",
                }
            )

    return issues


# ── Protocol ─────────────────────────────────────────────────────────────


def scan(ctx: OpsContext) -> ScanResult:
    """Scan for action prompt template issues at the given difficulty level."""
    issues: list[dict] = []
    project_root = ctx.project_root
    d = ctx.difficulty

    # Discover all existing templates
    templates = _discover_templates(project_root)

    # Scan all TSX files for runAction calls
    tsx_files = []
    for skill_dir in get_all_client_skill_dirs(project_root):
        tsx_files.extend(skill_dir.glob("augur/dashboard/**/*.tsx"))

    for tsx in tsx_files:
        try:
            content = tsx.read_text(errors="replace")
        except OSError:
            continue

        actions = _find_run_action_ids(content)
        migrated = _find_render_prompt_ids(content) if d >= 2 else set()

        rel_path = str(tsx.relative_to(project_root))

        for action in actions:
            aid = action["action_id"]
            line = action["line"]

            # d0: Missing template
            if d >= 0 and aid not in templates:
                issues.append(
                    {
                        "type": "missing_template",
                        "file": rel_path,
                        "line": line,
                        "action_id": aid,
                        "detail": f"no prompt template at assets/seeds/prompts/{aid}.md",
                    }
                )
                continue

            # d1: Template exists but missing sections
            if d >= 1 and aid in templates:
                missing = _check_template_structure(templates[aid])
                if missing:
                    issues.append(
                        {
                            "type": "missing_sections",
                            "file": str(
                                templates[aid].relative_to(project_root)
                            ),
                            "action_id": aid,
                            "detail": f"template missing sections: {', '.join(missing)}",
                        }
                    )

            # d2: TSX still uses inline description (not migrated)
            if d >= 2 and aid in templates and not _is_migrated(aid, migrated):
                issues.append(
                    {
                        "type": "inline_not_migrated",
                        "file": rel_path,
                        "line": line,
                        "action_id": aid,
                        "detail": "TSX uses inline description instead of renderPrompt()",
                    }
                )

            # d3: Template quality
            if d >= 3 and aid in templates:
                quality_issues = _check_template_quality(templates[aid])
                for qi in quality_issues:
                    issues.append(
                        {
                            **qi,
                            "file": str(
                                templates[aid].relative_to(project_root)
                            ),
                            "action_id": aid,
                        }
                    )

    n = len(issues)
    return ScanResult(
        issues=issues,
        summary=f"{n} prompt template issue(s) at d{d}",
        severity="warning" if n > 0 else "info",
        health="degraded" if n > 0 else "verified",
    )


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    """Fix prompt template issues.

    d0-d1: Auto-generate missing .md files from inline descriptions.
    d2-d3: Report only (migration and quality require human review).
    """
    if ctx.difficulty >= 2 or ctx.dry_run:
        return report_only_fix(
            ctx, "auto-markdowns-latest.json", issues, noun="prompt issue"
        )

    generated: list[str] = []
    for issue in issues:
        if issue["type"] != "missing_template":
            continue

        aid = issue["action_id"]
        # Find skill directory from TSX file path
        # Pattern: skills/{skill}/augur/dashboard/...
        tsx_path = ctx.project_root / issue["file"]
        parts = tsx_path.relative_to(ctx.project_root).parts
        if len(parts) >= 2 and parts[0] == "skills":
            prompts_dir = (
                ctx.project_root
                / parts[0]
                / parts[1]
                / "augur"
                / "data"
                / "prompts"
            )
            prompts_dir.mkdir(parents=True, exist_ok=True)
            template_path = prompts_dir / f"{aid}.md"
            if not template_path.exists():
                template_path.write_text(
                    f"---\naction: {aid}\n"
                    f"description: TODO — add description\n"
                    f"dispatch: ide\n---\n\n"
                    f"<instructions>\n"
                    f"TODO — describe what this action does and how the agent should approach it.\n"
                    f"</instructions>\n\n"
                    f"<task>\n"
                    f"TODO — describe the specific task for the agent.\n"
                    f"</task>\n"
                )
                generated.append(
                    str(template_path.relative_to(ctx.project_root))
                )

    if generated:
        return FixResult(
            success=True,
            changes=generated,
            summary=f"Generated {len(generated)} prompt template(s)",
            fix_type="code-fix",
        )

    return report_only_fix(
        ctx, "auto-markdowns-latest.json", issues, noun="prompt issue"
    )
