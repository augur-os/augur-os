"""auto-test-webmcp: Real WebMCP validation across all 9 phases.

Tests actual block data sources, page mounts, view storage, action wiring,
and component health — not just infrastructure plumbing.
"""
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
import importlib.util
import logging
import re
import subprocess
from pathlib import Path

from src.lib.staged_skill_catalog import find_skill_file
from src.lib.ops_protocol import (
    OpsContext,
    ScanResult,
    FixResult,
    write_report,
)

logger = logging.getLogger(__name__)

# Load check modules from file paths (directory uses hyphens, not a valid package)
_CHECKS_DIR = Path(__file__).resolve().parent / "checks"


def _load_check_module(filename: str) -> object:
    """Load a check module from the checks/ directory by filename."""
    mod_path = _CHECKS_DIR / filename
    spec = importlib.util.spec_from_file_location(f"webmcp_check_{mod_path.stem}", str(mod_path))
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_d0 = _load_check_module("d0_surface.py")
_d1 = _load_check_module("d1_content.py")
_d2 = _load_check_module("d2_integration.py")
_d3 = _load_check_module("d3_advanced.py")
_d4 = _load_check_module("d4_comprehensive.py")

check_d0_surface = _d0.check_d0_surface
check_d1_content = _d1.check_d1_content
check_d2_live = _d2.check_d2_live
check_d3_deep = _d3.check_d3_deep
check_d4_exhaustive = _d4.check_d4_exhaustive
check_evolution = _d4.check_evolution

name = "auto-test-webmcp"

DIFFICULTY_SPEC = {
    0: "Surface — verify files exist and block registry is populated",
    1: "Content — validate block data sources, page mounts, expandTo targets",
    2: "Live — probe dashboard APIs, test real block data fetches",
    3: "Deep — validate all block MCP tools return data, test action dispatch",
    4: "Exhaustive — Jest + TypeScript + data shape + response time + view CRUD + evolution check",
}


# ── Main ────────────────────────────────────────────────────────────────────────


def scan(ctx: OpsContext) -> ScanResult:
    """Scan for real WebMCP issues at current difficulty."""
    all_issues: list[dict] = []
    base_url = ctx.config.get("base_url", "http://localhost:3000")
    timeout = ctx.config.get("request_timeout", 15)

    # d0: Surface
    d0 = check_d0_surface(ctx.project_root)
    all_issues.extend(d0)
    if ctx.difficulty < 1:
        return _result(all_issues, 0)

    # d1: Content
    d1 = check_d1_content(ctx.project_root)
    all_issues.extend(d1)
    if ctx.difficulty < 2:
        return _result(all_issues, 1)

    # d2: Live API
    d2 = check_d2_live(ctx.project_root, base_url, timeout)
    all_issues.extend(d2)
    if ctx.difficulty < 3:
        return _result(all_issues, 2)

    # d3: Deep
    d3 = check_d3_deep(ctx.project_root, base_url, timeout)
    all_issues.extend(d3)
    if ctx.difficulty < 4:
        return _result(all_issues, 3)

    # d4: Exhaustive
    d4 = check_d4_exhaustive(ctx.project_root, base_url, timeout)
    all_issues.extend(d4)

    # Evolution: if all d4 checks passed, look for uncovered areas
    real_so_far = [i for i in all_issues if i.get("kind") not in ("environment", "maintenance")]
    if not real_so_far:
        evo = check_evolution(ctx.project_root, base_url)
        all_issues.extend(evo)

    return _result(all_issues, 4)


def _result(issues: list[dict], level: int) -> ScanResult:
    """Build ScanResult with appropriate severity."""
    real = [i for i in issues if i.get("kind") not in ("environment", "maintenance")]
    maint = [i for i in issues if i.get("kind") == "maintenance"]
    env = [i for i in issues if i.get("kind") == "environment"]

    if not real and not maint and not env:
        return ScanResult(issues=[], summary=f"d{level}: all checks passed", severity="info", health="verified")
    if not real and maint:
        return ScanResult(
            issues=issues,
            summary=f"d{level}: all checks passed — {len(maint)} evolution gap(s) to raise the bar",
            severity="info",
            health="verified",
        )
    if not real and env:
        return ScanResult(issues=issues, summary=f"d{level}: {len(env)} environment issue(s) (dashboard not running?)", severity="warning", health="degraded")

    # Use "degraded" not "broken" — these are real but non-critical gaps in
    # WebMCP integration (missing hooks, pages, data sources).  "broken" should
    # be reserved for infrastructure failures that prevent the scanner itself
    # from running, not for a high count of known feature gaps.
    return ScanResult(
        issues=issues,
        summary=f"d{level}: {len(real)} issue(s) found" + (f" + {len(maint)} evolution" if maint else "") + (f" + {len(env)} env" if env else ""),
        severity="error" if len(real) > 5 else "warning",
        health="degraded",
    )


# ── Fix helpers ─────────────────────────────────────────────────────────────────


def _is_environment_issue(issue: dict) -> bool:
    """Check if an issue is caused by environment/infrastructure, not code."""
    return issue.get("kind") == "environment" or issue.get("root_cause_type") == "env_runtime"


def _is_generated_artifact(issue: dict) -> bool:
    """Check if the issue is about a generated artifact that can be regenerated."""
    return issue.get("root_cause_type") == "generated_artifact"


def _regenerate_block_registry(project_root: Path) -> dict:
    """Attempt to regenerate the block registry by running the generation script.

    Returns an action dict describing what happened.
    """
    gen_script = project_root / "src" / "scripts" / "generate_block_registry.py"
    if not gen_script.exists():
        # Try alternate locations
        for candidate in [
            project_root / "scripts" / "generate_block_registry.py",
            project_root / "apps" / "dashboard" / "scripts" / "generate-block-registry.ts",
        ]:
            if candidate.exists():
                gen_script = candidate
                break

    if not gen_script.exists():
        return {"skipped": "block-registry", "reason": "generation script not found"}

    try:
        if gen_script.suffix == ".py":
            result = subprocess.run(
                ["python", str(gen_script)],
                capture_output=True, text=True, timeout=30,
                cwd=str(project_root),
                env={**__import__("os").environ, "PYTHONPATH": str(project_root)},
            )
        else:
            result = subprocess.run(
                ["npx", "tsx", str(gen_script)],
                capture_output=True, text=True, timeout=30,
                cwd=str(project_root / "apps" / "dashboard"),
            )

        if result.returncode != 0:
            return {
                "failed": "block-registry",
                "reason": f"script exited {result.returncode}: {result.stderr[:200]}",
            }

        # Generator exited 0 — but a clean exit does NOT prove the artifact was
        # produced (e.g. a generator that no-ops without node_modules). Verify
        # the registry file actually exists and is non-trivial before claiming
        # success. Mirror d0's entry-count heuristic (>= 10 `':` entries).
        registry_file = project_root / "apps/dashboard/lib/blocks/generated-block-registry.ts"
        if not registry_file.exists():
            return {
                "failed": "block-registry",
                "reason": "generator exited 0 but registry file still missing",
            }
        entry_count = registry_file.read_text(encoding="utf-8").count("':")
        if entry_count < 10:
            return {
                "failed": "block-registry",
                "reason": f"generator exited 0 but registry has only {entry_count} entries",
            }
        return {"regenerated": "block-registry", "script": str(gen_script)}
    except subprocess.TimeoutExpired:
        return {"failed": "block-registry", "reason": "script timed out (30s)"}
    except Exception as e:
        return {"failed": "block-registry", "reason": str(e)}


def _check_tool_registered(project_root: Path, tool_name: str) -> bool:
    """Check if an MCP tool name is registered in any Python MCP server file.

    Searches for @mcp.tool(name="...") or tool name in tool registration patterns.
    Checks both core MCP tools (src/mcp/) and client-native skill MCP tools
    (skills/*, .claude/skills/*, .gemini/skills/*).
    """
    # Search in src/mcp/ for core tool registrations
    mcp_dirs: list[Path] = [
        project_root / "src" / "mcp",
        project_root / "src" / "mcp" / "tools",
    ]

    # Also search client-native skill MCP directories
    for client_dir_name in (".claude", ".codex", ".gemini"):
        skills_dir = project_root / client_dir_name / "skills"
        if skills_dir.is_dir():
            for skill_dir in skills_dir.iterdir():
                if skill_dir.is_dir() and not skill_dir.name.startswith("."):
                    mcp_script_dir = skill_dir / "scripts" / "mcp"
                    if mcp_script_dir.is_dir():
                        mcp_dirs.append(mcp_script_dir)

    for mcp_dir in mcp_dirs:
        if not mcp_dir.is_dir():
            continue
        for py_file in mcp_dir.rglob("*.py"):
            try:
                content = py_file.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            # Match @mcp.tool(name="tool-name") or name="tool-name" in tool registration
            if f'name="{tool_name}"' in content or f"name='{tool_name}'" in content:
                return True
            # Also match def tool_name patterns (normalized)
            normalized = tool_name.replace("-", "_")
            if f"def {normalized}(" in content:
                return True

    return False


def _classify_webmcp_issue(project_root: Path, issue: dict) -> dict:
    """Enrich a WebMCP issue with fix classification.

    Adds:
      - fix_class: "environment" | "auto" | "wiring_bug" | "manual"
      - fix_instruction: human-readable fix description
    """
    enriched = dict(issue)

    if _is_environment_issue(issue):
        enriched["fix_class"] = "environment"
        detail = issue.get("detail", "")
        if "not running" in detail.lower() or "unreachable" in detail.lower():
            enriched["fix_instruction"] = "Dashboard not running. Start with /dev-build or npm run dev."
        elif "502" in detail or "not registered" in detail.lower():
            enriched["fix_instruction"] = (
                "MCP tool not loaded — restart the MCP server. "
                "If the tool is newly added, run "
                "`PYTHONPATH=project-brain/capabilities python -m skills.ai.scripts.sync_agents sync all` to regenerate registrations."
            )
        else:
            enriched["fix_instruction"] = f"Environment issue: {detail}"
        return enriched

    if _is_generated_artifact(issue):
        enriched["fix_class"] = "auto"
        enriched["fix_instruction"] = "Regenerate the artifact (block registry, etc.)"
        return enriched

    # For actionable issues with MCP tool references, check if tool is registered
    detail = issue.get("detail", "")
    path = issue.get("path", "")

    if path.startswith("mcp:"):
        tool_name = path[4:]  # Strip "mcp:" prefix
        if not _check_tool_registered(project_root, tool_name):
            enriched["fix_class"] = "wiring_bug"
            enriched["fix_instruction"] = (
                f"MCP tool '{tool_name}' is referenced by a block but not registered in "
                f"src/mcp/ or any client-native skill scripts/mcp/. Either register the "
                f"tool or update the block's data_source.mcp_tool."
            )
            return enriched

    # Check for missing files
    if "missing" in detail.lower() or "Missing:" in detail:
        enriched["fix_class"] = "manual"
        enriched["fix_instruction"] = f"Missing file needs to be created: {detail}"
        return enriched

    # Default: manual review
    enriched["fix_class"] = "manual"
    enriched["fix_instruction"] = f"Manual review needed: {detail}"
    return enriched


def _is_missing_page_issue(issue: dict) -> bool:
    """Check if the issue is a missing page.tsx file."""
    detail = issue.get("detail", "")
    return "page.tsx missing" in detail.lower() or "page.tsx missing" in detail


def _extract_page_path(issue: dict) -> Path | None:
    """Extract the expected page.tsx path from a missing-page issue."""
    path_str = issue.get("path", "")
    if path_str and path_str.endswith("page.tsx"):
        return Path(path_str)
    return None


def _generate_stub_page(page_path: Path, skill_name: str) -> bool:
    """Generate a minimal stub page.tsx for a missing skill page.

    Creates the directory and writes a stub that renders the skill name
    with a TODO_CLEANUP marker for manual replacement.

    Returns True if the page was created, False on error.
    """
    pascal = "".join(
        word.capitalize()
        for word in re.sub(r"[_-]", " ", skill_name).split()
    )
    content = f"""// TODO_CLEANUP(auto-test-webmcp): stub page — replace with real implementation
'use client';

export default function {pascal}Page() {{
  return (
    <div className="space-y-6 p-6">
      <h1 className="text-xl font-semibold">{skill_name}</h1>
      <p className="text-sm text-[var(--text-muted)]">
        This page was auto-generated by auto-test-webmcp because the skill
        declares a page mount but no page.tsx existed. Replace this stub
        with a real implementation.
      </p>
    </div>
  );
}}
"""
    try:
        page_path.parent.mkdir(parents=True, exist_ok=True)
        page_path.write_text(content)
        logger.info("Generated stub page: %s", page_path)
        return True
    except OSError as exc:
        logger.warning("Failed to generate stub page %s: %s", page_path, exc)
        return False


def _add_todo_marker_to_skill_md(skill_md_path: Path, marker_msg: str) -> bool:
    """Add a TODO_CLEANUP marker as a comment after the frontmatter in a SKILL.md.

    Returns True if the marker was added, False if already present or on error.
    """
    marker = f"<!-- TODO_CLEANUP(auto-test-webmcp): {marker_msg} -->"
    try:
        content = skill_md_path.read_text()
    except OSError:
        return False

    if "TODO_CLEANUP(auto-test-webmcp)" in content:
        return False  # Already has a marker from this scanner

    # Insert after the closing --- of frontmatter
    parts = content.split("---", 2)
    if len(parts) >= 3:
        content = f"{parts[0]}---{parts[1]}---\n{marker}\n{parts[2]}"
    else:
        content = f"{marker}\n{content}"

    skill_md_path.write_text(content)
    return True


def _clear_stale_next_cache(project_root: Path) -> list[str]:
    """Clear stale .next cache directories that may cause health check failures.

    Returns list of cleared paths.
    """
    cleared: list[str] = []
    dashboard_dir = project_root / "apps" / "dashboard"
    cache_dirs = [
        dashboard_dir / ".next" / "cache",
        dashboard_dir / ".next" / "server",
    ]
    for cache_dir in cache_dirs:
        if cache_dir.is_dir():
            try:
                import shutil
                shutil.rmtree(cache_dir)
                cleared.append(str(cache_dir.relative_to(project_root)))
                logger.info("Cleared stale cache: %s", cache_dir)
            except OSError as exc:
                logger.warning("Failed to clear cache %s: %s", cache_dir, exc)
    return cleared


def _find_skill_md_for_issue(project_root: Path, issue: dict) -> Path | None:
    """Locate the SKILL.md that owns a given issue based on path or detail."""
    detail = issue.get("detail", "")
    # Extract skill name from detail like "Page ai_bridge:ai_bridge ..."
    match = re.search(r"Page\s+([\w_-]+):", detail)
    if match:
        skill_name = match.group(1)
        candidate = find_skill_file(project_root, skill_name, "SKILL.md")
        if candidate is not None:
            return candidate
    # Fallback: try to find from path
    path_str = issue.get("path", "")
    if path_str:
        # Path like .../app/system/ai_bridge/page.tsx -> skill = ai_bridge
        parts = Path(path_str).parts
        for i, part in enumerate(parts):
            if part == "app" and i + 2 < len(parts):
                skill_name = parts[i + 2]  # hub/skill/page.tsx
                candidate = find_skill_file(project_root, skill_name, "SKILL.md")
                if candidate is not None:
                    return candidate
    return None


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    """Fix WebMCP issues: regenerate artifacts, generate stub pages, add markers, classify the rest.

    Auto-fixable:
      - generated_artifact: regenerate block registry
      - missing_page: generate stub page.tsx with TODO_CLEANUP marker (d1+)
      - environment/health: clear stale .next cache (d1+)
    Diagnosed (actionable report with fix instructions):
      - wiring_bug: tool referenced but not registered — add TODO_CLEANUP to SKILL.md
    Report-only:
      - environment: dashboard down, MCP server not running
      - manual: structural issues needing human judgment
    """
    if ctx.dry_run:
        env_count = sum(1 for i in issues if _is_environment_issue(i))
        gen_count = sum(1 for i in issues if _is_generated_artifact(i))
        page_count = sum(1 for i in issues if _is_missing_page_issue(i))
        code_count = len(issues) - env_count - gen_count - page_count
        parts = []
        if gen_count:
            parts.append(f"{gen_count} auto-fixable (regenerate)")
        if page_count:
            parts.append(f"{page_count} stub page(s) to generate")
        if code_count:
            parts.append(f"{code_count} code issue(s)")
        if env_count:
            parts.append(f"{env_count} environment issue(s)")
        return FixResult(
            success=True,
            summary=f"Dry run: {', '.join(parts) if parts else f'{len(issues)} issue(s)'}",
        )

    if not issues:
        return FixResult(success=True, summary="No WebMCP issues to fix")

    changes: list[str] = []
    actions: list[dict] = []
    env_issues: list[dict] = []
    manual_issues: list[dict] = []
    wiring_bugs: list[dict] = []

    # Classify all issues
    classified = [_classify_webmcp_issue(ctx.project_root, i) for i in issues]

    # Pass 1: Auto-fix generated artifacts
    registry_regen_failed = False
    registry_needs_regen = any(i.get("fix_class") == "auto" for i in classified)
    if registry_needs_regen:
        result = _regenerate_block_registry(ctx.project_root)
        actions.append(result)
        if "regenerated" in result:
            registry_path = ctx.project_root / "apps/dashboard/lib/blocks/generated-block-registry.ts"
            changes.append(str(registry_path))
        elif "failed" in result:
            # Honesty: a requested regeneration that did not produce the
            # artifact must surface as a failed fix, not a silent success.
            registry_regen_failed = True

    stubs_generated = 0
    markers_added = 0
    for issue in classified:
        if not _is_missing_page_issue(issue):
            continue
        page_path = _extract_page_path(issue)
        if not page_path:
            manual_issues.append(issue)
            continue

        # Extract skill name from path for stub generation
        detail = issue.get("detail", "")
        skill_match = re.search(r"Page\s+([\w_-]+):", detail)
        skill_name = skill_match.group(1) if skill_match else page_path.parent.name

        # Generate the stub page
        if _generate_stub_page(page_path, skill_name):
            changes.append(str(page_path))
            stubs_generated += 1
            actions.append({"generated_stub": str(page_path), "skill": skill_name})

            # Also mark the SKILL.md so it's discoverable by auto-tidy
            skill_md = _find_skill_md_for_issue(ctx.project_root, issue)
            if skill_md:
                msg = f"stub page generated for {skill_name} — needs real implementation"
                if _add_todo_marker_to_skill_md(skill_md, msg):
                    markers_added += 1
                    changes.append(str(skill_md))
        else:
            manual_issues.append(issue)

    # Pass 3: Clear stale cache for environment/health issues
    has_env_health = any(
        _is_environment_issue(i) and ("stale" in i.get("detail", "").lower() or "health" in i.get("detail", "").lower())
        for i in classified
    )
    if has_env_health or ctx.difficulty >= 1:
        cleared = _clear_stale_next_cache(ctx.project_root)
        if cleared:
            actions.append({"cleared_cache": cleared})

    for issue in classified:
        fix_class = issue.get("fix_class", "manual")
        if fix_class == "auto" or _is_missing_page_issue(issue):
            continue  # Already handled
        elif fix_class == "environment":
            env_issues.append(issue)
        elif fix_class == "wiring_bug":
            tool_path = issue.get("path", "")
            if ctx.difficulty >= 1 and tool_path.startswith("mcp:"):
                tool_name = tool_path[4:]
                # Find which SKILL.md references this tool
                for skill_md in (ctx.project_root / "project-brain" / "capabilities" / "skills").glob("*/SKILL.md"):
                    try:
                        content = skill_md.read_text()
                        if tool_name in content:
                            msg = f"MCP tool '{tool_name}' referenced but not registered"
                            if _add_todo_marker_to_skill_md(skill_md, msg):
                                markers_added += 1
                                changes.append(str(skill_md))
                            break
                    except OSError:
                        continue
            wiring_bugs.append(issue)
        else:
            manual_issues.append(issue)

    # Write classified report with actionable fix instructions
    report_data: dict = {
        "auto_fixed": [a for a in actions if "regenerated" in a or "generated_stub" in a],
        "wiring_bugs": [],
        "manual_issues": [],
        "environment_issues": [],
    }

    for issue in wiring_bugs:
        report_data["wiring_bugs"].append({
            "detail": issue.get("detail", ""),
            "path": issue.get("path", ""),
            "fix_instruction": issue.get("fix_instruction", ""),
            "category": issue.get("category", ""),
        })

    for issue in manual_issues:
        report_data["manual_issues"].append({
            "detail": issue.get("detail", ""),
            "path": issue.get("path", ""),
            "fix_instruction": issue.get("fix_instruction", ""),
            "category": issue.get("category", ""),
        })

    for issue in env_issues:
        report_data["environment_issues"].append({
            "detail": issue.get("detail", ""),
            "fix_instruction": issue.get("fix_instruction", ""),
        })

    report_path = write_report(ctx, "webmcp-test-latest.json", report_data)
    actions.append({"report": str(report_path)})

    # Summary
    parts = []
    if stubs_generated:
        parts.append(f"generated {stubs_generated} stub page(s)")
    if markers_added:
        parts.append(f"added {markers_added} TODO_CLEANUP marker(s)")
    if any("regenerated" in a for a in actions):
        parts.append(f"regenerated {sum(1 for a in actions if 'regenerated' in a)} artifact(s)")
    if any("cleared_cache" in a for a in actions):
        parts.append("cleared stale .next cache")
    if wiring_bugs:
        parts.append(f"{len(wiring_bugs)} wiring bug(s) diagnosed")
    if manual_issues:
        parts.append(f"{len(manual_issues)} manual issue(s)")
    if env_issues:
        parts.append(f"{len(env_issues)} environment issue(s) (not actionable)")
    if registry_regen_failed:
        parts.append("block-registry regeneration FAILED (artifact not produced)")
    summary = "; ".join(parts) if parts else "No actionable fixes"

    return FixResult(
        success=not registry_regen_failed,
        actions=actions,
        changes=changes,
        summary=summary,
        fix_type="code-fix" if changes else ("verified" if (env_issues or manual_issues or wiring_bugs) else "report"),
    )
