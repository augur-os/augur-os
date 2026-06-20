# TODO_CLEANUP: This file is 1043 lines — consider splitting into smaller modules
# skills/auto-e2e-pipeline/scripts/e2e_pipeline.py
"""Auto E2E Pipeline — validate vault-to-dashboard data pipeline."""
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
import inspect
import json
import logging
from pathlib import Path

from src.config.paths import (
    get_adr_dir,
    get_all_client_skill_dirs,
    get_documents_dir,
    get_project_root,
    get_rag_category_dir,
    get_rag_dir,
    get_vault_dir,
)
from src.lib.frontmatter_utils import parse_frontmatter
from src.lib.ops_protocol import (
    FixResult,
    OpsContext,
    ScanResult,
    evolution_gap,
    make_issue,
    report_only_fix,
    write_report,
)

logger = logging.getLogger(__name__)

name = "auto-e2e-pipeline"

DIFFICULTY_SPEC = {
    0: "Edge inventory — count vault files and RAG entries per category",
    1: "Cross-reference — compare source counts vs RAG counts, flag gaps",
    2: "MCP probe — call browse_index_impl() directly, auto-fix via RAG reindex",
    3: "API probe — HTTP POST to dashboard /api/mcp/tool, compare vs MCP",
    4: "Page-tool audit — discover all page→MCP tool mappings, verify each returns data",
}

# All browse categories the unified indexer produces
# ("actions" retired by ADR-806 — the FILE-actions pipeline is gone)
ALL_CATEGORIES = [
    "skills", "adrs", "prompts", "agents", "integrations",
    "commands", "vault", "scripts", "api-routes",
    "tests", "pages", "blocks", "mcp-tools",
]


def scan(ctx: OpsContext) -> ScanResult:
    """Validate the e2e data pipeline at the requested difficulty."""
    issues: list[dict] = []
    stage_counts: dict[str, dict] = {}

    # ── d0: Edge inventory ──────────────────────────────────────────
    for cat in ALL_CATEGORIES:
        cat_dir = get_rag_category_dir(cat)
        rag_count = _count_rag_entries(cat_dir)
        stage_counts[cat] = {"rag": rag_count}

    vault_dir = get_vault_dir()
    vault_file_count = _count_vault_files(vault_dir) if vault_dir.is_dir() else 0
    stage_counts["_vault_files"] = {"source": vault_file_count}

    total_rag = sum(v.get("rag", 0) for k, v in stage_counts.items() if k != "_vault_files")

    # ── d0 continued: Seed fallback detection ───────────────────────
    seed_issues = _detect_seed_fallbacks(ctx.project_root)
    issues.extend(seed_issues)
    seed_fallback_issues = [
        issue for issue in seed_issues
        if issue.get("broken_stage") == "seed_fallback"
    ]

    # ── d0 continued: Pulse endpoint wiring ───────────────────────
    pulse_issues = _detect_dead_pulse_endpoints(ctx.project_root)
    issues.extend(pulse_issues)

    if ctx.difficulty < 1:
        # d0: just report counts
        empty_cats = [c for c in ALL_CATEGORIES if stage_counts[c]["rag"] == 0]
        if empty_cats:
            for cat in empty_cats:
                issues.append(make_issue(
                    category="e2e-pipeline",
                    detail=f"RAG category '{cat}' has 0 entries",
                    path=str(get_rag_category_dir(cat)),
                    kind="actionable",
                    root_cause_type="env_runtime",
                    fixability="auto",
                    broken_stage="rag_empty",
                    browse_category=cat,
                ))
        scanned = len(ALL_CATEGORIES) + len(seed_fallback_issues) + len(pulse_issues)
        has_degrading_issues = bool(empty_cats or seed_fallback_issues or pulse_issues)
        return ScanResult(
            issues=issues,
            summary=f"Edge inventory: {total_rag} total RAG entries across {len(ALL_CATEGORIES)} categories, "
                    f"{vault_file_count} vault files. {len(empty_cats)} empty categories. "
                    f"{len(seed_fallback_issues)} seed fallbacks. {len(pulse_issues)} dead pulse endpoints.",
            severity="warning" if has_degrading_issues else "info",
            health="degraded" if has_degrading_issues else "verified",
            items_scanned=scanned,
        )

    # ── d1: Cross-reference source vs RAG ───────────────────────────
    for cat in ALL_CATEGORIES:
        source_count = _count_source_items(cat, ctx.project_root)
        stage_counts[cat]["source"] = source_count
        rag_count = stage_counts[cat]["rag"]

        if source_count > 0 and rag_count == 0:
            issues.append(make_issue(
                category="e2e-pipeline",
                detail=f"Category '{cat}': {source_count} source items but 0 RAG entries — indexer not running or broken",
                path=str(get_rag_category_dir(cat)),
                kind="actionable",
                root_cause_type="env_runtime",
                fixability="auto",
                broken_stage="rag_stale",
                browse_category=cat,
                source_count=source_count,
                rag_count=0,
            ))
        elif source_count > 0 and rag_count < source_count * 0.5:
            issues.append(make_issue(
                category="e2e-pipeline",
                detail=f"Category '{cat}': {source_count} source items but only {rag_count} RAG entries — "
                       f"indexer coverage is {rag_count * 100 // source_count}%",
                path=str(get_rag_category_dir(cat)),
                kind="actionable",
                root_cause_type="env_runtime",
                fixability="auto",
                broken_stage="rag_stale",
                browse_category=cat,
                source_count=source_count,
                rag_count=rag_count,
            ))

    if ctx.difficulty < 2:
        return _build_result(issues, stage_counts, "Cross-reference")

    # ── d2: MCP probe — call browse_index_impl() directly ──────────
    for cat in ALL_CATEGORIES:
        try:
            mcp_result = _call_browse_index_impl(cat)
            mcp_count = mcp_result.get("total_count") or mcp_result.get("count", 0)
            stage_counts[cat]["mcp"] = mcp_count
            rag_count = stage_counts[cat]["rag"]

            if rag_count > 0 and mcp_count == 0:
                issues.append(make_issue(
                    category="e2e-pipeline",
                    detail=f"Category '{cat}': {rag_count} RAG entries but browse_index_impl() returns 0 items — "
                           f"MCP tool broken or index reader failing",
                    path="src/mcp/augur_framework/tools/infrastructure/browse/index.py",
                    kind="actionable",
                    root_cause_type="repo_bug",
                    fixability="manual",
                    broken_stage="mcp_empty",
                    browse_category=cat,
                    rag_count=rag_count,
                    mcp_count=0,
                ))
        except Exception as exc:
            stage_counts[cat]["mcp"] = -1
            issues.append(make_issue(
                category="e2e-pipeline",
                detail=f"Category '{cat}': browse_index_impl() raised {type(exc).__name__}: {exc}",
                path="src/mcp/augur_framework/tools/infrastructure/browse/index.py",
                kind="broken",
                root_cause_type="repo_bug",
                fixability="manual",
                broken_stage="mcp_error",
                browse_category=cat,
            ))

    if ctx.difficulty < 3:
        return _build_result(issues, stage_counts, "MCP probe")

    # ── d3: API probe — HTTP POST to running dashboard ──────────────
    import httpx

    base_url = "http://localhost:3000"
    dashboard_up = _check_dashboard_health(base_url)
    if not dashboard_up:
        issues.append(make_issue(
            category="e2e-pipeline",
            detail="Dashboard not running at localhost:3000 — cannot probe API routes. "
                   "Start with /dev-build or pnpm --filter dashboard dev.",
            kind="environment",
            root_cause_type="env_runtime",
            fixability="manual",
            broken_stage="api_unreachable",
        ))
        return _build_result(issues, stage_counts, "API probe (dashboard down)")

    for cat in ALL_CATEGORIES:
        mcp_count = stage_counts[cat].get("mcp", 0)
        if mcp_count <= 0:
            continue  # Already flagged at d2, skip API probe

        try:
            api_result = _call_api_route(base_url, cat)
            api_count = api_result.get("count", 0)
            stage_counts[cat]["api"] = api_count

            if mcp_count > 0 and api_count == 0:
                issues.append(make_issue(
                    category="e2e-pipeline",
                    detail=f"Category '{cat}': MCP returns {mcp_count} items but API route returns 0 — "
                           f"MCPBridge or proxy broken",
                    path="apps/dashboard/app/api/mcp/tool/route.ts",
                    kind="actionable",
                    root_cause_type="repo_bug",
                    fixability="manual",
                    broken_stage="api_error",
                    browse_category=cat,
                    mcp_count=mcp_count,
                    api_count=0,
                ))
            elif api_result.get("error"):
                issues.append(make_issue(
                    category="e2e-pipeline",
                    detail=f"Category '{cat}': API returned error: {api_result['error']}",
                    path="apps/dashboard/app/api/mcp/tool/route.ts",
                    kind="actionable",
                    root_cause_type="repo_bug",
                    fixability="manual",
                    broken_stage="api_error",
                    browse_category=cat,
                ))
        except Exception as exc:
            stage_counts[cat]["api"] = -1
            issues.append(make_issue(
                category="e2e-pipeline",
                detail=f"Category '{cat}': API probe failed: {type(exc).__name__}: {exc}",
                path="apps/dashboard/app/api/mcp/tool/route.ts",
                kind="broken",
                root_cause_type="env_runtime",
                fixability="manual",
                broken_stage="api_error",
                browse_category=cat,
            ))

    if ctx.difficulty < 4:
        return _build_result(issues, stage_counts, "API probe")

    # ── d4: Page→tool audit — discover all page MCP tool refs, verify each ─
    page_tools = _discover_page_mcp_tools(ctx.project_root)
    # Write-action prefixes: these tools require args and won't return data
    # when called with empty args, so skip them in the d4 probe.
    _WRITE_PREFIXES = (
        "add-", "set-", "create-", "update-", "delete-", "manage-",
        "file-write", "file-edit", "file-delete",
        "page-builder-delete", "career-create-cv",
    )
    tools_checked = 0
    tools_ok = 0
    for pt in page_tools:
        tool_name = pt["mcp_tool"]
        source = pt["source"]  # "yaml_page", "skillmd_block", "tsx_hook", or "tsx_mutation"
        skill = pt.get("skill", "unknown")
        # Skip mutation hooks and write-action tools — they require args
        if source == "tsx_mutation" or tool_name.startswith(_WRITE_PREFIXES):
            continue
        tools_checked += 1
        try:
            api_result = _call_api_tool(base_url, tool_name, pt.get("args", {}))
            err_msg = str(api_result.get("error", "")) if isinstance(api_result, dict) else ""
            # Tool requires args (Pydantic validation or custom arg check) — not a pipeline issue
            if "Field required" in err_msg or "required" in err_msg.lower() and "parameter" in err_msg.lower():
                tools_ok += 1
                continue
            # Tool has runtime/hardware dependency (e.g. peekaboo, CLI not installed)
            if any(p in err_msg for p in ("exit code", "not found", "not installed", "invalid JSON")):
                # Environment issue, not a pipeline data bug — classify but don't block
                tools_ok += 1
                continue
            # Tool not registered in MCP server — wiring issue, not data issue
            if "Unknown tool" in err_msg:
                issues.append(make_issue(
                    category="e2e-pipeline",
                    detail=f"Page tool '{tool_name}' ({source}, skill={skill}) not registered in MCP server",
                    path=pt.get("path", ""),
                    kind="actionable",
                    root_cause_type="repo_bug",
                    fixability="manual",
                    broken_stage="page_tool_unregistered",
                    mcp_tool=tool_name,
                    source_type=source,
                    skill=skill,
                ))
                continue
            # Check for non-empty response
            has_data = _response_has_data(api_result)
            if has_data:
                tools_ok += 1
            else:
                issues.append(make_issue(
                    category="e2e-pipeline",
                    detail=f"Page tool '{tool_name}' ({source}, skill={skill}) returns empty data via API",
                    path=pt.get("path", ""),
                    kind="actionable",
                    root_cause_type="repo_bug",
                    fixability="manual",
                    broken_stage="page_tool_empty",
                    mcp_tool=tool_name,
                    source_type=source,
                    skill=skill,
                ))
        except Exception as exc:
            # httpx raises for 4xx/5xx — check if it's a "needs args" error
            exc_str = str(exc)
            if "Field required" in exc_str:
                tools_ok += 1
                continue
            issues.append(make_issue(
                category="e2e-pipeline",
                detail=f"Page tool '{tool_name}' ({source}, skill={skill}) failed: "
                       f"{type(exc).__name__}: {exc}",
                path=pt.get("path", ""),
                kind="broken",
                root_cause_type="env_runtime",
                fixability="manual",
                broken_stage="page_tool_error",
                mcp_tool=tool_name,
                source_type=source,
                skill=skill,
            ))

    # Evolution gap at max difficulty
    if not any(i.get("kind") == "actionable" for i in issues):
        issues.append(evolution_gap(
            f"All {tools_checked} page→tool mappings verified. "
            "Does not validate per-item field correctness (title, description, tags) "
            "or response schema matching component destructuring. "
            "Next: add d5 that samples N items per tool and verifies field completeness."
        ))

    return _build_result(issues, stage_counts, f"Page-tool audit ({tools_ok}/{tools_checked} ok)")


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    """Fix pipeline issues — primarily triggers RAG reindex for stale categories."""
    if ctx.dry_run:
        return FixResult(success=True, summary=f"Dry run: {len(issues)} issue(s)")

    if not issues:
        return FixResult(success=True, summary="No issues to fix")

    # Separate fixable (rag_stale) from report-only issues. Evolution gaps are
    # intentional maintenance signals, not manual release blockers.
    rag_stale = [i for i in issues if i.get("broken_stage") in ("rag_stale", "rag_empty")]
    evolution_gaps = [
        i for i in issues
        if i.get("category") == "evolution" or i.get("kind") == "maintenance"
    ]
    other = [
        i for i in issues
        if i.get("broken_stage") not in ("rag_stale", "rag_empty")
        and i not in evolution_gaps
    ]

    actions: list[dict] = []
    changes: list[str] = []

    # Auto-fix: trigger RAG reindex for stale categories
    if rag_stale and ctx.difficulty >= 2:
        stale_categories = {i.get("browse_category", "") for i in rag_stale}
        stale_categories.discard("")
        try:
            stats = _trigger_rag_reindex()
            actions.append({
                "action": "rag_reindex",
                "categories": list(stale_categories),
                "stats": stats,
            })
            changes.append("RAG index rebuilt")
        except Exception as exc:
            actions.append({
                "action": "rag_reindex_failed",
                "error": str(exc),
            })

    # Report-only for non-fixable issues
    if other:
        report_path = write_report(ctx, "e2e-pipeline-report.json", {
            "issues": other,
            "fixable_count": len(rag_stale),
            "manual_count": len(other),
        })
        actions.append({"report": str(report_path)})

    if evolution_gaps:
        report_path = write_report(ctx, "e2e-pipeline-evolution-gaps.json", {
            "evolution_gaps": evolution_gaps,
            "count": len(evolution_gaps),
        })
        actions.append({"report": str(report_path), "evolution_gap_count": len(evolution_gaps)})

    parts = []
    if rag_stale and ctx.difficulty >= 2:
        parts.append(f"Triggered RAG reindex for {len(rag_stale)} stale categories")
    if evolution_gaps:
        parts.append(f"{len(evolution_gaps)} evolution gap(s) reported")
    if other:
        parts.append(f"{len(other)} issues need manual investigation (report written)")

    return FixResult(
        success=True,
        actions=actions,
        changes=changes,
        summary=". ".join(parts) if parts else "No fixable issues",
        fix_type="sync" if rag_stale else "report",
    )


# ── Private helpers ─────────────────────────────────────────────────


def _count_rag_entries(cat_dir: Path) -> int:
    """Count RAG entries in a category directory."""
    if not cat_dir.exists():
        return 0
    return sum(1 for _ in cat_dir.rglob("*.md"))


def _count_vault_files(vault_dir: Path) -> int:
    """Count all indexable files in the vault."""
    if not vault_dir.is_dir():
        return 0
    extensions = {".md", ".yaml", ".yml", ".json", ".txt", ".csv"}
    count = 0
    for f in vault_dir.rglob("*"):
        if f.is_file() and f.suffix in extensions:
            count += 1
    return count


def _count_source_items(category: str, project_root: Path) -> int:
    """Count source items for a category (what should exist in RAG).

    Each category has a different source of truth. This function mirrors
    what the unified indexer scans for each category.
    """
    from src.config.paths import get_all_client_skill_dirs

    if category == "vault":
        vault_dir = get_vault_dir()
        return _count_vault_files(vault_dir)

    if category == "adrs":
        adr_dir = get_adr_dir()
        if not adr_dir.is_dir():
            return 0
        # ADR-642: count entries in the central JSON index plus any stray .md.
        count = 0
        try:
            from src.lib.adr_utils import load_adrs_index

            count = len(load_adrs_index(adr_dir))
        except Exception:
            count = 0
        count += sum(1 for f in adr_dir.glob("ADR-*.md"))
        return count

    if category == "skills":
        count = 0
        for sd in get_all_client_skill_dirs(project_root):
            count += sum(1 for f in sd.glob("*/SKILL.md"))
        return count

    if category == "prompts":
        count = 0
        for sd in get_all_client_skill_dirs(project_root):
            for skill in sd.iterdir():
                for prompts_dir in [
                    skill / "assets" / "seeds" / "prompts",
                    skill / "assets" / "seeds",
                ]:
                    if prompts_dir.is_dir():
                        count += sum(1 for f in prompts_dir.glob("*.md")
                                     if "prompt" in f.stem.lower() or prompts_dir.name == "prompts")
        return count

    if category == "agents":
        agents_dir = project_root / "config" / "agents"
        if not agents_dir.is_dir():
            return 0
        return sum(1 for f in agents_dir.glob("*.yaml")) + sum(1 for f in agents_dir.glob("*.yml"))

    if category == "scripts":
        count = 0
        for sd in get_all_client_skill_dirs(project_root):
            for skill in sd.iterdir():
                scripts_dir = skill / "scripts"
                if scripts_dir.is_dir():
                    count += sum(1 for f in scripts_dir.rglob("*.py") if f.name != "__init__.py")
                    count += sum(1 for f in scripts_dir.rglob("*.sh"))
        return count

    if category == "api-routes":
        api_dir = project_root / "apps" / "dashboard" / "app" / "api"
        if not api_dir.is_dir():
            return 0
        return sum(1 for _ in api_dir.rglob("route.ts"))

    if category == "tests":
        count = 0
        for sd in get_all_client_skill_dirs(project_root):
            for skill in sd.iterdir():
                tests_dir = skill / "augur" / "tests"
                if tests_dir.is_dir():
                    count += sum(1 for f in tests_dir.rglob("test_*.py"))
        # Dashboard tests
        dash_tests = project_root / "apps" / "dashboard" / "__tests__"
        if dash_tests.is_dir():
            count += sum(1 for f in dash_tests.rglob("*.test.*"))
        return count

    if category == "pages":
        count = 0
        for sd in get_all_client_skill_dirs(project_root):
            for skill_md in sd.glob("*/SKILL.md"):
                try:
                    fm, _ = parse_frontmatter(skill_md)
                    config = fm.get("x-augur-config") or {}
                    pages = (config.get("contributions") or {}).get("pages") or []
                    count += len(pages)
                except Exception:
                    pass
        return count

    if category == "blocks":
        count = 0
        for sd in get_all_client_skill_dirs(project_root):
            for skill_md in sd.glob("*/SKILL.md"):
                try:
                    fm, _ = parse_frontmatter(skill_md)
                    config = fm.get("x-augur-config") or {}
                    blocks = (config.get("contributions") or {}).get("blocks") or []
                    count += len(blocks)
                except Exception:
                    pass
        return count

    if category == "mcp-tools":
        count = 0
        for sd in get_all_client_skill_dirs(project_root):
            for init_py in sd.glob("*/scripts/mcp/__init__.py"):
                try:
                    content = init_py.read_text()
                    count += content.count("@mcp.tool(")
                except Exception:
                    pass
        return count

    if category in ("integrations", "cli-commands", "workflows"):
        # These are extracted from SKILL.md frontmatter during indexing —
        # exact counting requires parsing all SKILL.md files.
        # For now, use RAG count as baseline (counted elsewhere).
        return -1  # -1 = skip comparison

    return -1  # Unknown category, skip


def _call_browse_index_impl(category: str) -> dict:
    """Call browse_index_impl() directly (in-process MCP tool).

    The runtime MCP packages may expect src/mcp on sys.path. We add it
    temporarily here for parity with client launchers.
    """
    import sys
    mcp_root = str(get_project_root() / "src" / "mcp")
    added = mcp_root not in sys.path
    if added:
        sys.path.insert(0, mcp_root)
    try:
        from src.mcp.augur_framework.tools.infrastructure.browse.index import browse_index_impl
        raw = browse_index_impl(category)
        return json.loads(raw)
    finally:
        if added and mcp_root in sys.path:
            sys.path.remove(mcp_root)


def _check_dashboard_health(base_url: str) -> bool:
    """Check if the dashboard is responding (any HTTP response = alive)."""
    import httpx
    try:
        resp = httpx.get(base_url, timeout=5, follow_redirects=True)
        # Any HTTP response means the server is up (even 404/500)
        return True
    except (httpx.ConnectError, httpx.ConnectTimeout, OSError):
        return False


def _call_api_route(base_url: str, category: str) -> dict:
    """Call the dashboard MCP proxy API route."""
    import httpx
    resp = httpx.post(
        f"{base_url}/api/mcp/tool",
        json={"tool": "browse-index", "args": {"category": category}},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def _trigger_rag_reindex() -> dict:
    """Trigger a full RAG reindex and return stats."""
    indexer_path = get_project_root() / "src" / "lib" / "index" / "unified_indexer.py"
    spec = importlib.util.spec_from_file_location("unified_indexer", str(indexer_path))
    if not spec or not spec.loader:
        raise ImportError(f"Cannot load unified_indexer from {indexer_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.reindex_all(
        get_project_root(),
        get_rag_dir(),
        vault_dir=get_vault_dir(),
        documents_dir=get_documents_dir(),
    )


def _discover_page_mcp_tools(project_root: Path) -> list[dict]:
    """Discover all MCP tool references from pages and blocks.

    Scans three sources:
    1. YAML auto-pages: skills/*/augur/pages/*.yaml → blocks[].mcp_tool
    2. SKILL.md blocks: x-augur-config.contributions.blocks[].data_source.mcp_tool
    3. Custom TSX hooks: useMcpQuery/useMcpMutation/useMcpPoll in dashboard code
    """
    import re
    import yaml
    from src.config.paths import get_all_client_skill_dirs

    tools: list[dict] = []
    seen: set[str] = set()  # Dedupe by tool name

    # 1. YAML auto-pages
    for sd in get_all_client_skill_dirs(project_root):
        for yaml_path in sd.rglob("augur/pages/*.yaml"):
            try:
                config = yaml.safe_load(yaml_path.read_text())
                if not isinstance(config, dict):
                    continue
                skill_name = yaml_path.parts[
                    yaml_path.parts.index("skills") + 1
                ] if "skills" in yaml_path.parts else "unknown"
                for block in config.get("blocks", []):
                    if isinstance(block, dict) and block.get("mcp_tool"):
                        tool_name = block["mcp_tool"]
                        if tool_name not in seen:
                            seen.add(tool_name)
                            tools.append({
                                "mcp_tool": tool_name,
                                "source": "yaml_page",
                                "skill": skill_name,
                                "path": str(yaml_path),
                                "args": {},
                            })
                    # Also check row_actions
                    for action in block.get("row_actions", []):
                        if isinstance(action, dict) and action.get("mcp_tool"):
                            t = action["mcp_tool"]
                            if t not in seen:
                                seen.add(t)
                                tools.append({
                                    "mcp_tool": t,
                                    "source": "yaml_page",
                                    "skill": skill_name,
                                    "path": str(yaml_path),
                                    "args": {},
                                })
            except Exception:
                pass

    # 2. SKILL.md blocks
    for sd in get_all_client_skill_dirs(project_root):
        for skill_md in sd.glob("*/SKILL.md"):
            try:
                fm, _ = parse_frontmatter(skill_md)
                skill_name = fm.get("name", skill_md.parent.name)
                config = fm.get("x-augur-config") or {}
                blocks = (config.get("contributions") or {}).get("blocks") or []
                for block in blocks:
                    if not isinstance(block, dict):
                        continue
                    ds = block.get("data_source") or {}
                    tool_name = ds.get("mcp_tool") if isinstance(ds, dict) else None
                    if tool_name and tool_name not in seen:
                        seen.add(tool_name)
                        tools.append({
                            "mcp_tool": tool_name,
                            "source": "skillmd_block",
                            "skill": skill_name,
                            "path": str(skill_md),
                            "args": {},
                        })
            except Exception:
                pass

    # 3. Custom TSX hooks (useMcpQuery, useMcpMutation, useMcpPoll)
    # Three separate regexes to match each hook's argument signature:
    # useMcpQuery(key, tool, preset) — tool is 2nd arg (key can be string or array)
    query_re = re.compile(
        r'useMcpQuery\s*(?:<[^>]*>)?\s*\(\s*'
        r'(?:\[[^\]]*\]|[^,]+),\s*'  # key arg (array or scalar, required)
        r'["\']([a-z][a-z0-9_-]*)["\']',  # tool name
        re.IGNORECASE,
    )
    # useMcpPoll(key, tool, interval) — tool is 2nd arg
    poll_re = re.compile(
        r'useMcpPoll\s*(?:<[^>]*>)?\s*\(\s*'
        r'(?:\[[^\]]*\]|[^,]+),\s*'  # key arg (array or scalar, required)
        r'["\']([a-z][a-z0-9_-]*)["\']',  # tool name
        re.IGNORECASE,
    )
    # useMcpMutation(tool) — tool is 1st arg
    mutation_re = re.compile(
        r'useMcpMutation\s*(?:<[^>]*>)?\s*\(\s*'
        r'["\']([a-z][a-z0-9_-]*)["\']',  # tool name (1st arg)
        re.IGNORECASE,
    )
    # Utility files that don't contain actual hook calls (just re-exports / helpers)
    _SKIP_BASENAMES = {"useBlockData.ts", "useBlockData.tsx", "useMcpQuery.ts",
                       "useMcpQuery.tsx", "useMcpMutation.ts", "useMcpMutation.tsx",
                       "useMcpPoll.ts", "useMcpPoll.tsx"}
    tsx_dirs = [
        project_root / "apps" / "dashboard",
    ]
    for sd in get_all_client_skill_dirs(project_root):
        tsx_dirs.append(sd)
    for tsx_dir in tsx_dirs:
        if not tsx_dir.is_dir():
            continue
        for tsx_file in tsx_dir.rglob("*.tsx"):
            if tsx_file.name in _SKIP_BASENAMES:
                continue
            try:
                content = tsx_file.read_text()
                # Infer skill name from path (shared across all matches)
                parts = tsx_file.parts
                skill_name = "dashboard"
                if "skills" in parts:
                    idx = parts.index("skills")
                    if idx + 1 < len(parts):
                        skill_name = parts[idx + 1]
                # Query and Poll hooks → source "tsx_hook"
                for regex in (query_re, poll_re):
                    for m in regex.finditer(content):
                        tool_name = m.group(1)
                        if tool_name not in seen:
                            seen.add(tool_name)
                            tools.append({
                                "mcp_tool": tool_name,
                                "source": "tsx_hook",
                                "skill": skill_name,
                                "path": str(tsx_file),
                                "args": {},
                            })
                # Mutation hooks → source "tsx_mutation" (skipped in d4 probes)
                for m in mutation_re.finditer(content):
                    tool_name = m.group(1)
                    if tool_name not in seen:
                        seen.add(tool_name)
                        tools.append({
                            "mcp_tool": tool_name,
                            "source": "tsx_mutation",
                            "skill": skill_name,
                            "path": str(tsx_file),
                            "args": {},
                        })
            except Exception:
                pass

    return tools


def _call_api_tool(base_url: str, tool_name: str, args: dict) -> dict | list:
    """Call any MCP tool via the dashboard API route.

    Does NOT raise on 4xx so caller can inspect error body
    (e.g. Pydantic "Field required" errors for tools needing args).
    Only raises on 5xx or connection errors.
    """
    import httpx
    resp = httpx.post(
        f"{base_url}/api/mcp/tool",
        json={"tool": tool_name, "args": args},
        timeout=30,
    )
    # Don't raise — let caller inspect error body for classification
    # (Pydantic "Field required" can come back as 400 or 500)
    return resp.json()


def _response_has_data(result: object) -> bool:
    """Check if an MCP tool response contains non-empty data.

    Handles both dict envelopes ({items: [...]}) and bare list responses ([...]).
    """
    # Some tools return bare lists (e.g. symptoms: [{...}, {...}])
    if isinstance(result, list):
        return len(result) > 0
    if not isinstance(result, dict):
        return bool(result)
    if result.get("error"):
        return False
    # Common envelope patterns: {items: [...]}, {data: ...}, {count: N}
    for key in ("items", "data", "stories", "entries", "results"):
        val = result.get(key)
        if isinstance(val, list) and len(val) > 0:
            return True
        if isinstance(val, dict) and len(val) > 0:
            return True
    if result.get("count", 0) > 0:
        return True
    # If result itself has keys beyond metadata, consider it has data
    data_keys = {k for k in result.keys()} - {"success", "status", "error", "message"}
    if data_keys and any(result.get(k) for k in data_keys):
        return True
    return False


class _ProbeMCP:
    """Tiny MCP decorator shim used by DataResult runtime probes."""

    def __init__(self) -> None:
        self.tools: dict[str, object] = {}

    def tool(self, *args, **kwargs):
        explicit_name = kwargs.get("name")
        if args and isinstance(args[0], str):
            explicit_name = args[0]

        def decorator(func):
            tool_name = explicit_name or func.__name__.replace("_", "-")
            self.tools[tool_name] = func
            return func

        return decorator


class _ProbeMetrics:
    def track_tool(self, *args, **kwargs) -> None:
        return None


def _probe_interceptor(func=None, *args, **kwargs):
    if func is None:
        return lambda wrapped: wrapped
    return func


def _data_result_helper_names(py_file: Path) -> set[str]:
    import ast

    try:
        content = py_file.read_text(encoding="utf-8")
        tree = ast.parse(content)
    except Exception:
        return set()
    helper_names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        try:
            segment = ast.get_source_segment(content, node) or ""
        except Exception:
            segment = ""
        if (
            "DataResult" in segment
            or "read_skill_data" in segment
            or "read_path_data" in segment
        ):
            helper_names.add(node.name)
    return helper_names


def _load_probe_module(py_file: Path):
    import sys

    module_name = f"_augur_data_result_probe_{abs(hash(str(py_file.resolve())))}"
    kwargs = {}
    if py_file.name == "__init__.py":
        kwargs["submodule_search_locations"] = [str(py_file.parent)]
    spec = importlib.util.spec_from_file_location(module_name, str(py_file), **kwargs)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {py_file}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _register_probe_tools(module) -> dict[str, object]:
    mcp = _ProbeMCP()
    for attr_name in dir(module):
        if attr_name != "register_tools" and not (
            attr_name.startswith("register_") and attr_name.endswith("_tools")
        ):
            continue
        register = getattr(module, attr_name, None)
        if not callable(register):
            continue
        try:
            register(mcp, _probe_interceptor, _ProbeMetrics())
        except TypeError:
            continue
    return mcp.tools


def _tool_accepts_default_args(func: object) -> bool:
    try:
        signature = inspect.signature(func)
    except (TypeError, ValueError):
        return False
    for param in signature.parameters.values():
        if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
            continue
        if param.default is inspect.Parameter.empty:
            return False
    return True


def _tool_references_helpers(func: object, helper_names: set[str], py_file: Path) -> bool:
    code = getattr(func, "__code__", None)
    if code is not None and helper_names.intersection(code.co_names):
        return True

    try:
        source = inspect.getsource(func)
    except (OSError, TypeError):
        return False
    return any(name in source for name in helper_names)


def _decode_probe_payload(payload: object) -> object:
    if isinstance(payload, str):
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            return payload
    return payload


def _source_values(payload: object) -> list[object]:
    values: list[object] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key == "source":
                values.append(value)
            values.extend(_source_values(value))
    elif isinstance(payload, (list, tuple)):
        for item in payload:
            values.extend(_source_values(item))
    return values


def _call_probe_tool(func: object) -> object:
    import asyncio

    result = func()
    if inspect.isawaitable(result):
        result = asyncio.run(result)
    return _decode_probe_payload(result)


def _probe_data_result_response_sources(project_root: Path, data_result_files: list[Path]) -> list[dict]:
    issues: list[dict] = []

    for py_file in data_result_files:
        helper_names = _data_result_helper_names(py_file)
        if not helper_names:
            continue
        try:
            module = _load_probe_module(py_file)
            tools = _register_probe_tools(module)
        except Exception as exc:
            issues.append(make_issue(
                category="e2e-pipeline",
                detail=f"Could not import DataResult MCP module for source probe: {type(exc).__name__}: {exc}",
                path=str(py_file),
                kind="environment",
                root_cause_type="env_runtime",
                fixability="manual",
                broken_stage="data_result_source_probe_error",
            ))
            continue

        for tool_name, func in sorted(tools.items()):
            if not _tool_accepts_default_args(func):
                continue
            if not _tool_references_helpers(func, helper_names, py_file):
                continue
            try:
                payload = _call_probe_tool(func)
            except Exception as exc:
                issues.append(make_issue(
                    category="e2e-pipeline",
                    detail=f"DataResult-backed tool '{tool_name}' failed during source probe: {type(exc).__name__}: {exc}",
                    path=str(py_file),
                    kind="environment",
                    root_cause_type="env_runtime",
                    fixability="manual",
                    broken_stage="data_result_source_probe_error",
                    mcp_tool=tool_name,
                ))
                continue

            sources = _source_values(payload)
            has_source = any(isinstance(value, str) and value.strip() for value in sources)
            if not has_source:
                issues.append(make_issue(
                    category="e2e-pipeline",
                    detail=f"DataResult-backed tool '{tool_name}' returned no non-empty source metadata",
                    path=str(py_file),
                    kind="actionable",
                    root_cause_type="repo_bug",
                    fixability="manual",
                    broken_stage="data_result_source_missing",
                    mcp_tool=tool_name,
                ))

    return issues


def _detect_seed_fallbacks(project_root: Path) -> list[dict]:
    """Detect MCP tools that silently return seed data when vault data is missing.

    Scans Python MCP tool files for patterns where seed/demo data is returned
    as a fallback without any indicator to the caller.  These hide empty states
    from users and mask wiring or data-source problems.

    Also tracks DataResult adoption: files that import ``read_skill_data`` or
    ``from src.lib.data_result`` are counted as migrated.  The summary is
    attached as metadata on a synthetic issue so callers can surface progress.

    When all legacy patterns are gone but migrated files exist, an evolution
    gap is emitted suggesting d2 runtime validation of the ``source`` field.
    """
    import re

    # Patterns that indicate a legacy seed fallback
    seed_patterns = [
        # Explicit seed path construction followed by file I/O
        re.compile(r'seed[_s]?(?:_dir|_path|_data|dir)\b.*?(?:\.exists|read_text|read_bytes|json\.load)', re.DOTALL),
        # assets/seeds/ path references in data-loading context
        re.compile(r'["\']assets[/\\]seeds[/\\]'),
        # "_seed_dir()" helper call — catches embedded helper patterns in
        # _shared.py files (reading-list, lifestyle, career) where the fallback
        # condition lives inside the helper, not adjacent to the call site.
        re.compile(r'_seed_dir\s*\(\s*\)'),
    ]

    # Pattern for DataResult adoption
    data_result_pattern = re.compile(
        r'(?:from\s+src\.lib\.data_result\b|import\s+read_skill_data\b)'
    )

    issues: list[dict] = []
    data_result_files: list[Path] = []
    migrated_count = 0
    legacy_count = 0

    all_skill_dirs = list(get_all_client_skill_dirs(project_root))

    # --- Pass 1: detect legacy seed fallbacks ---
    for sd in all_skill_dirs:
        for py_file in sd.rglob("scripts/mcp/*.py"):
            try:
                content = py_file.read_text(encoding="utf-8")
            except Exception:
                continue

            # Skip files that only DEFINE seed helpers without fallback usage
            if "seed" not in content.lower():
                continue

            # Look for the fallback pattern: condition check → seed load
            # Common shapes:
            #   if not items: ... seed_path ... json.loads(seed_path.read_text())
            #   if not file_path.exists(): ... seed_dir / rel ...
            lines = content.split("\n")
            skill_name = "unknown"
            parts = py_file.parts
            if "skills" in parts:
                idx = parts.index("skills")
                if idx + 1 < len(parts):
                    skill_name = parts[idx + 1]

            for i, line in enumerate(lines):
                # Match: loading from seed path as a fallback
                stripped = line.strip()
                if any(p.search(stripped) for p in seed_patterns):
                    # Check surrounding context for fallback condition.
                    # For _seed_dir() calls we also treat the call itself as
                    # indicative — helper functions in _shared.py encapsulate
                    # the condition internally so the surrounding context at
                    # the call site may not contain fallback keywords.
                    context_window = "\n".join(lines[max(0, i - 5):i + 3])
                    is_seed_dir_call = re.search(r'_seed_dir\s*\(\s*\)', stripped)
                    is_fallback = is_seed_dir_call or any(kw in context_window for kw in (
                        "if not items", "if not data", "if not result",
                        "if not tasks", "if not spaces",
                        "not file_path.exists", "not items",
                        "error", "fallback", "Seed fallback",
                    ))
                    if is_fallback:
                        legacy_count += 1
                        issues.append(make_issue(
                            category="e2e-pipeline",
                            detail=f"Skill '{skill_name}' returns seed data as silent fallback "
                                   f"({py_file.name}:{i + 1})",
                            path=str(py_file),
                            kind="actionable",
                            root_cause_type="repo_bug",
                            fixability="manual",
                            broken_stage="seed_fallback",
                            skill=skill_name,
                            line=i + 1,
                        ))
                        break  # One issue per file is enough

    # --- Pass 2: count DataResult adoption ---
    for sd in all_skill_dirs:
        for py_file in sd.rglob("scripts/mcp/*.py"):
            try:
                content = py_file.read_text(encoding="utf-8")
            except Exception:
                continue
            if data_result_pattern.search(content):
                migrated_count += 1
                data_result_files.append(py_file)

    # Surface migration progress only while there is still work to do. When
    # legacy_count == 0 the maintenance status is pure noise — nothing to
    # action, no value in the report, and the executor surfaces it as
    # 'manual investigation needed' which is misleading. The evolution_gap
    # below already carries the 'fully migrated' signal for the loop.
    if legacy_count > 0 or migrated_count == 0:
        issues.append(make_issue(
            category="e2e-pipeline",
            detail=(
                f"DataResult adoption: {migrated_count} migrated, {legacy_count} legacy "
                f"seed-fallback files remaining"
            ),
            kind="maintenance",
            root_cause_type="coverage_gap",
            fixability="automatic",
            broken_stage="seed_fallback",
            migrated=migrated_count,
            legacy=legacy_count,
        ))

    if legacy_count == 0 and migrated_count > 0:
        issues.extend(_probe_data_result_response_sources(project_root, data_result_files))

    return issues


def _detect_dead_pulse_endpoints(project_root: Path) -> list[dict]:
    """Detect endpoints referenced in the pulse health check that don't exist.

    The pulse route probes a list of API endpoints — if any don't have
    corresponding route.ts files, they'll always return 404 and pollute
    health status.
    """
    import re

    pulse_route = project_root / "apps" / "dashboard" / "app" / "api" / "settings" / "layout" / "pulse" / "route.ts"
    if not pulse_route.exists():
        return []

    try:
        content = pulse_route.read_text(encoding="utf-8")
    except Exception:
        return []

    # Extract endpoint strings from QUICK_ENDPOINTS and DEEP_ENDPOINTS arrays
    endpoint_re = re.compile(r'["\'](/api/[a-zA-Z0-9/_?=&-]+)["\']')
    referenced = set()
    for m in endpoint_re.finditer(content):
        path = m.group(1).split("?")[0]  # Strip query params
        referenced.add(path)

    # Check which ones have actual route.ts files
    api_dir = project_root / "apps" / "dashboard" / "app" / "api"
    issues: list[dict] = []

    for endpoint in sorted(referenced):
        # Convert /api/foo/bar → apps/dashboard/app/api/foo/bar/route.ts
        segments = endpoint.strip("/").split("/")[1:]  # Drop "api" prefix
        route_path = api_dir / "/".join(segments) / "route.ts"

        # Also check for dynamic route segments: [id], [skillId], etc.
        if not route_path.exists():
            # Try parent with dynamic segment
            parent = api_dir / "/".join(segments[:-1]) if segments else api_dir
            found = False
            if parent.is_dir():
                for child in parent.iterdir():
                    if child.is_dir() and child.name.startswith("["):
                        if (child / "route.ts").exists():
                            found = True
                            break
            if not found:
                issues.append(make_issue(
                    category="e2e-pipeline",
                    detail=f"Pulse probes '{endpoint}' but no route.ts exists",
                    path=str(pulse_route),
                    kind="actionable",
                    root_cause_type="repo_bug",
                    fixability="manual",
                    broken_stage="pulse_dead_endpoint",
                    endpoint=endpoint,
                ))

    return issues


def _build_result(
    issues: list[dict],
    stage_counts: dict[str, dict],
    phase_label: str,
) -> ScanResult:
    """Build a ScanResult with a stage-count summary."""
    actionable = [i for i in issues if i.get("kind") in ("actionable", "broken")]
    broken_stages = {i.get("broken_stage", "unknown") for i in actionable}

    severity = "info"
    health = "verified"
    if any(i.get("kind") == "broken" for i in issues):
        severity = "error"
        health = "broken"
    elif actionable:
        severity = "warning"
        health = "degraded"

    # Build human-readable summary
    cats_ok = sum(1 for c in ALL_CATEGORIES if not any(
        i.get("browse_category") == c and i.get("kind") in ("actionable", "broken")
        for i in issues
    ))
    summary = (
        f"{phase_label}: {cats_ok}/{len(ALL_CATEGORIES)} categories healthy. "
        f"{len(actionable)} issue(s)."
    )
    if broken_stages - {"unknown"}:
        summary += f" Broken stages: {', '.join(sorted(broken_stages - {'unknown'}))}."

    return ScanResult(
        issues=issues,
        summary=summary,
        severity=severity,
        health=health,
        items_scanned=len(ALL_CATEGORIES),
    )
