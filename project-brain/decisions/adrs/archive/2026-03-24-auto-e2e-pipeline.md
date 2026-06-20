# Auto E2E Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create an autoloop that validates the full data pipeline from vault files through RAG index, MCP tools, API routes, to dashboard page rendering — covering all browse categories and all page→MCP tool mappings — and pinpoints the exact stage where data drops off.

**Architecture:** Outside-in diagnostic. The scanner inventories both edges (vault files + dashboard API responses) then binary-searches inward through RAG index and MCP tool layers to classify exactly which pipeline stage is broken for each item. At d2+, triggers RAG reindex as an auto-fix for `rag_stale` issues. At d4, discovers every page→MCP tool mapping (YAML pages, SKILL.md blocks, custom TSX hooks) and verifies each tool returns data.

**Tech Stack:** Python (ops_protocol), httpx (API probes), unified_indexer (RAG reindex), frontmatter_utils (vault parsing)

---

## File Structure

```
skills/auto-e2e-pipeline/
├── SKILL.md                                    # Autoloop metadata + frontmatter
├── scripts/
│   ├── __init__.py                             # Empty
│   └── e2e_pipeline.py                         # OpsCommand: scan() + fix()
├── augur/
│   └── tests/
│       └── test_e2e_pipeline.py                # Unit tests
├── assets/
│   └── seeds/
│       └── .gitkeep
├── references/
│   └── .gitkeep
└── evals/
    └── .gitkeep
```

**Key dependencies (existing files, read-only):**

| File | What we use from it |
|------|-------------------|
| `src/lib/ops_protocol.py` | `OpsContext`, `ScanResult`, `FixResult`, `make_issue`, `evolution_gap`, `write_report`, `report_only_fix`, `check_http_route` |
| `skills/rag/scripts/unified_indexer.py` | `reindex_all()` (for auto-fix at d2+, loaded dynamically) |
| `src/config/paths.py` | `get_project_root()`, `get_vault_dir()`, `get_rag_dir()`, `get_rag_category_dir()`, `get_documents_dir()` |
| `src/lib/frontmatter_utils.py` | `parse_frontmatter()` |
| `src/mcp/augur_mcp/infrastructure/browse/index.py` | `browse_index_impl()` (reference for expected response shape) |

---

### Task 1: Scaffold skill directory and SKILL.md

**Files:**
- Create: `skills/auto-e2e-pipeline/SKILL.md`
- Create: `skills/auto-e2e-pipeline/scripts/__init__.py`
- Create: `skills/auto-e2e-pipeline/assets/seeds/.gitkeep`
- Create: `skills/auto-e2e-pipeline/references/.gitkeep`
- Create: `skills/auto-e2e-pipeline/evals/.gitkeep`
- Create: `skills/auto-e2e-pipeline/augur/tests/__init__.py`

- [ ] **Step 1: Create SKILL.md with autoloop frontmatter**

```markdown
---
name: auto-e2e-pipeline
x-augur-type: autoloop
x-augur-tags: [e2e, pipeline, validation, diagnostics]
description: >
  Validate the full data pipeline from vault files through RAG index, MCP tools,
  API routes, to dashboard rendering. Pinpoints the exact stage where data drops.
  Covers: auto-e2e-pipeline, scan, all browse categories, pipeline health

x-augur-visibility: auto

x-augur-loop:
  name: testing
  tier: 2
  trigger: nightly

x-augur-hub: adaptive
x-augur-tab: infrastructure
---

# auto-e2e-pipeline

End-to-end pipeline validator. Checks that data in the vault actually reaches
the dashboard by probing each stage of the pipeline:

1. **Vault files** — markdown with frontmatter exists
2. **RAG index** — unified indexer has pointer files for vault data
3. **MCP tool** — `browse-index` returns items for each category
4. **API route** — `POST /api/mcp/tool` proxies correctly
5. **Dashboard** — pages render data (d3+, requires running dashboard)

## Usage

```
/auto-e2e-pipeline              # d0: edge inventory
/auto-e2e-pipeline --difficulty 1  # d1: cross-reference vault vs RAG
/auto-e2e-pipeline --difficulty 2  # d2: MCP probe + auto-fix (RAG reindex)
/auto-e2e-pipeline --difficulty 3  # d3: API route probe (requires dashboard)
/auto-e2e-pipeline --difficulty 4  # d4: Page→tool audit (requires dashboard)
```

## Difficulty Levels

| Level | Check | Requires |
|-------|-------|----------|
| d0 | Edge inventory — count vault files, count RAG entries per category | Filesystem only |
| d1 | Cross-reference — for each category, compare vault/source count vs RAG count, flag gaps | Filesystem only |
| d2 | MCP probe — call `browse_index_impl()` directly, compare vs RAG entries. Auto-fix: trigger RAG reindex for stale categories | Python imports |
| d3 | API probe — HTTP POST to `localhost:3000/api/mcp/tool`, compare vs MCP response. Requires running dashboard | Network (httpx) |
| d4 | Page→tool audit — discover all MCP tools referenced by auto-pages (YAML), SKILL.md blocks, and custom TSX hooks, then call each tool and verify non-empty response | Dashboard running |
```

- [ ] **Step 2: Create empty `__init__.py` and `.gitkeep` files**

```python
# skills/auto-e2e-pipeline/scripts/__init__.py
# (empty)
```

```
# skills/auto-e2e-pipeline/assets/seeds/.gitkeep
# skills/auto-e2e-pipeline/references/.gitkeep
# skills/auto-e2e-pipeline/evals/.gitkeep
# skills/auto-e2e-pipeline/augur/tests/__init__.py (empty)
```

- [ ] **Step 3: Commit scaffold**

```bash
git add skills/auto-e2e-pipeline/
git commit -m "feat(auto-e2e-pipeline): scaffold skill directory and metadata"
```

---

### Task 2: Implement vault inventory helpers (Stage 1)

**Files:**
- Create: `skills/auto-e2e-pipeline/scripts/e2e_pipeline.py`
- Test: `skills/auto-e2e-pipeline/augur/tests/test_e2e_pipeline.py`

These helpers count source items that *should* exist in the pipeline. Each browse category has a different source of truth.

- [ ] **Step 1: Write failing test for module protocol compliance**

```python
# skills/auto-e2e-pipeline/augur/tests/test_e2e_pipeline.py
"""Tests for auto-e2e-pipeline autoloop."""
from __future__ import annotations

import importlib.util
from pathlib import Path

from src.lib.ops_protocol import OpsContext, ScanResult, FixResult, make_test_ctx

_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "e2e_pipeline.py"
_SPEC = importlib.util.spec_from_file_location("e2e_pipeline_under_test", str(_MODULE_PATH))
assert _SPEC and _SPEC.loader
mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mod)


def test_module_name() -> None:
    assert mod.name == "auto-e2e-pipeline"


def test_has_difficulty_spec() -> None:
    assert hasattr(mod, "DIFFICULTY_SPEC")
    assert isinstance(mod.DIFFICULTY_SPEC, dict)
    assert 0 in mod.DIFFICULTY_SPEC
    assert 3 in mod.DIFFICULTY_SPEC


def test_scan_returns_scan_result(tmp_path: Path) -> None:
    ctx = make_test_ctx(tmp_path)
    result = mod.scan(ctx)
    assert isinstance(result, ScanResult)


def test_fix_returns_fix_result(tmp_path: Path) -> None:
    ctx = make_test_ctx(tmp_path)
    result = mod.fix(ctx, [])
    assert isinstance(result, FixResult)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Projects/Augur && python -m pytest skills/auto-e2e-pipeline/augur/tests/test_e2e_pipeline.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Write minimal e2e_pipeline.py skeleton**

```python
# skills/auto-e2e-pipeline/scripts/e2e_pipeline.py
"""Auto E2E Pipeline — validate vault-to-dashboard data pipeline."""
from __future__ import annotations

import importlib.util
import json
import logging
from pathlib import Path

from src.config.paths import (
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
ALL_CATEGORIES = [
    "skills", "adrs", "actions", "prompts", "agents", "integrations",
    "cli-commands", "workflows", "vault", "scripts", "api-routes",
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
        return ScanResult(
            issues=issues,
            summary=f"Edge inventory: {total_rag} total RAG entries across {len(ALL_CATEGORIES)} categories, "
                    f"{vault_file_count} vault files. {len(empty_cats)} empty categories.",
            severity="warning" if empty_cats else "info",
            health="degraded" if empty_cats else "verified",
            items_scanned=len(ALL_CATEGORIES),
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
                    path="src/mcp/augur_mcp/infrastructure/browse/index.py",
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
                path="src/mcp/augur_mcp/infrastructure/browse/index.py",
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
    tools_checked = 0
    tools_ok = 0
    for pt in page_tools:
        tool_name = pt["mcp_tool"]
        source = pt["source"]  # "yaml_page", "skillmd_block", or "tsx_hook"
        skill = pt.get("skill", "unknown")
        tools_checked += 1
        try:
            api_result = _call_api_tool(base_url, tool_name, pt.get("args", {}))
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

    # Separate fixable (rag_stale) from report-only issues
    rag_stale = [i for i in issues if i.get("broken_stage") in ("rag_stale", "rag_empty")]
    other = [i for i in issues if i.get("broken_stage") not in ("rag_stale", "rag_empty")]

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

    parts = []
    if rag_stale and ctx.difficulty >= 2:
        parts.append(f"Triggered RAG reindex for {len(rag_stale)} stale categories")
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
        vault_dir = get_vault_dir()
        adr_dir = vault_dir / "dev" / "adrs"
        if not adr_dir.is_dir():
            return 0
        return sum(1 for f in adr_dir.glob("ADR-*.md"))

    if category == "skills":
        count = 0
        for sd in get_all_client_skill_dirs(project_root):
            count += sum(1 for f in sd.glob("*/SKILL.md"))
        return count

    if category == "actions":
        count = 0
        for sd in get_all_client_skill_dirs(project_root):
            for skill in sd.iterdir():
                actions_dir = skill / "augur" / "actions"
                if actions_dir.is_dir():
                    count += sum(1 for f in actions_dir.glob("*.md"))
                # Also check assets/actions (older convention)
                assets_actions = skill / "assets" / "actions"
                if assets_actions.is_dir():
                    count += sum(1 for f in assets_actions.glob("*.md"))
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
    """Call browse_index_impl() directly (in-process MCP tool)."""
    from src.mcp.augur_mcp.infrastructure.browse.index import browse_index_impl
    raw = browse_index_impl(category)
    return json.loads(raw)


def _check_dashboard_health(base_url: str) -> bool:
    """Check if the dashboard is responding."""
    import httpx
    try:
        resp = httpx.get(f"{base_url}/api/health", timeout=5)
        return resp.status_code == 200
    except Exception:
        # Fallback: try the root page
        try:
            resp = httpx.get(base_url, timeout=5, follow_redirects=True)
            return resp.status_code == 200
        except Exception:
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
    indexer_path = get_project_root() / "skills" / "rag" / "scripts" / "unified_indexer.py"
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
    hook_re = re.compile(
        r'useMcp(?:Query|Mutation|Poll)\s*(?:<[^>]*>)?\s*\(\s*'
        r'(?:[^,]+,\s*)?'       # optional key arg for Query/Poll
        r'"\'["\']',  # tool name in quotes
        re.IGNORECASE,
    )
    tsx_dirs = [
        project_root / "apps" / "dashboard",
    ]
    for sd in get_all_client_skill_dirs(project_root):
        tsx_dirs.append(sd)
    for tsx_dir in tsx_dirs:
        if not tsx_dir.is_dir():
            continue
        for tsx_file in tsx_dir.rglob("*.tsx"):
            try:
                content = tsx_file.read_text()
                for m in hook_re.finditer(content):
                    tool_name = m.group(1)
                    if tool_name not in seen:
                        seen.add(tool_name)
                        # Infer skill name from path
                        parts = tsx_file.parts
                        skill_name = "dashboard"
                        if "skills" in parts:
                            idx = parts.index("skills")
                            if idx + 1 < len(parts):
                                skill_name = parts[idx + 1]
                        tools.append({
                            "mcp_tool": tool_name,
                            "source": "tsx_hook",
                            "skill": skill_name,
                            "path": str(tsx_file),
                            "args": {},
                        })
            except Exception:
                pass

    return tools


def _call_api_tool(base_url: str, tool_name: str, args: dict) -> dict:
    """Call any MCP tool via the dashboard API route."""
    import httpx
    resp = httpx.post(
        f"{base_url}/api/mcp/tool",
        json={"tool": tool_name, "args": args},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def _response_has_data(result: dict) -> bool:
    """Check if an MCP tool response contains non-empty data."""
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Projects/Augur && python -m pytest skills/auto-e2e-pipeline/augur/tests/test_e2e_pipeline.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add skills/auto-e2e-pipeline/scripts/e2e_pipeline.py skills/auto-e2e-pipeline/augur/tests/test_e2e_pipeline.py
git commit -m "feat(auto-e2e-pipeline): implement scan/fix with 5 difficulty levels (d0-d4)"
```

---

### Task 3: Add targeted unit tests for each difficulty level

**Files:**
- Modify: `skills/auto-e2e-pipeline/augur/tests/test_e2e_pipeline.py`

- [ ] **Step 1: Write test for d0 — empty project returns empty RAG warning**

```python
def test_d0_empty_project_flags_empty_categories(tmp_path: Path) -> None:
    """d0 on a project with no RAG entries should flag all categories as empty."""
    ctx = make_test_ctx(tmp_path, difficulty=0)
    result = mod.scan(ctx)
    assert isinstance(result, ScanResult)
    assert result.health == "degraded"
    assert len(result.issues) == len(mod.ALL_CATEGORIES)
    assert all(i.get("broken_stage") == "rag_empty" for i in result.issues)
```

- [ ] **Step 2: Write test for d1 — source items with no RAG flags rag_stale**

```python
def test_d1_source_without_rag_flags_stale(tmp_path: Path) -> None:
    """d1 should flag categories where source items exist but RAG is empty."""
    # Create a fake SKILL.md so skills category has source items
    skill_dir = tmp_path / "skills" / "test-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: test-skill\n---\nTest")

    ctx = make_test_ctx(tmp_path, difficulty=1)
    result = mod.scan(ctx)
    assert isinstance(result, ScanResult)
    # Should have at least one rag_stale issue for skills category
    stale = [i for i in result.issues if i.get("broken_stage") == "rag_stale"]
    # On a tmp_path with no RAG dir, all categories with sources will be stale
    assert len(stale) >= 1  # skills category should be flagged as stale
```

- [ ] **Step 3: Write test for fix — dry_run returns early**

```python
def test_fix_dry_run_returns_early(tmp_path: Path) -> None:
    ctx = make_test_ctx(tmp_path, dry_run=True)
    issues = [{"broken_stage": "rag_stale", "browse_category": "skills"}]
    result = mod.fix(ctx, issues)
    assert isinstance(result, FixResult)
    assert result.success
    assert "Dry run" in result.summary
```

- [ ] **Step 4: Write test for fix — empty issues returns no-op**

```python
def test_fix_no_issues_is_noop(tmp_path: Path) -> None:
    ctx = make_test_ctx(tmp_path)
    result = mod.fix(ctx, [])
    assert isinstance(result, FixResult)
    assert result.success
    assert "No issues" in result.summary
```

- [ ] **Step 5: Run all tests**

Run: `cd ~/Projects/Augur && python -m pytest skills/auto-e2e-pipeline/augur/tests/test_e2e_pipeline.py -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add skills/auto-e2e-pipeline/augur/tests/test_e2e_pipeline.py
git commit -m "test(auto-e2e-pipeline): add unit tests for d0, d1, fix dry-run"
```

---

### Task 4: Smoke test with real project data

**Files:** None (manual verification)

- [ ] **Step 1: Run d0 scan on real project**

Run: `cd ~/Projects/Augur && python -c "
from pathlib import Path
from src.lib.ops_protocol import OpsContext
import importlib.util
spec = importlib.util.spec_from_file_location('e2e', 'skills/auto-e2e-pipeline/scripts/e2e_pipeline.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
ctx = OpsContext(project_root=Path('.').resolve(), difficulty=0)
r = mod.scan(ctx)
print(r.summary)
for i in r.issues[:5]:
    print(f'  - {i[\"detail\"][:100]}')
"`

Expected: Shows counts per category, flags any empty categories.

- [ ] **Step 2: Run d1 scan on real project**

Same as above but with `difficulty=1`. Expected: Shows source-vs-RAG comparison.

- [ ] **Step 3: Run d2 scan on real project**

Same with `difficulty=2`. Expected: Calls browse_index_impl() for each category. If any categories are stale, fix() should trigger reindex.

- [ ] **Step 4: If dashboard is running, run d3 scan**

Same with `difficulty=3`. Expected: Probes API routes. If dashboard is down, reports environment issue.

- [ ] **Step 5: Run fix for any issues found**

```python
ctx = OpsContext(project_root=Path('.').resolve(), difficulty=2)
r = mod.scan(ctx)
if r.issues:
    f = mod.fix(ctx, r.issues)
    print(f.summary)
```

- [ ] **Step 6: Commit any adjustments from smoke testing**

```bash
git add -u
git commit -m "fix(auto-e2e-pipeline): adjustments from smoke testing"
```

---

### Task 5: Final verification and cleanup

**Files:**
- Verify: all files in `skills/auto-e2e-pipeline/`

- [ ] **Step 1: Run full test suite**

Run: `cd ~/Projects/Augur && python -m pytest skills/auto-e2e-pipeline/augur/tests/test_e2e_pipeline.py -v`
Expected: All tests PASS

- [ ] **Step 2: Verify skill is discoverable**

Run: `cd ~/Projects/Augur && python -c "
from src.config.paths import get_all_client_skill_dirs, get_project_root
root = get_project_root()
for sd in get_all_client_skill_dirs(root):
    p = sd / 'auto-e2e-pipeline' / 'SKILL.md'
    if p.exists():
        print(f'Found: {p}')
        break
else:
    print('NOT FOUND')
"`

Expected: `Found: .../skills/auto-e2e-pipeline/SKILL.md`

- [ ] **Step 3: Verify no banned files at skill root**

Run: `ls skills/auto-e2e-pipeline/`
Expected: Only SKILL.md, scripts/, augur/, assets/, references/, evals/ — no `docs/`, `data/`, `lib/`

- [ ] **Step 4: Final commit if needed**

```bash
git add skills/auto-e2e-pipeline/
git commit -m "feat(auto-e2e-pipeline): complete e2e pipeline validation autoloop"
```

---

### Task 6: Add d4 page→tool audit tests and smoke test

**Files:**
- Modify: `skills/auto-e2e-pipeline/augur/tests/test_e2e_pipeline.py`

- [ ] **Step 1: Write test for _discover_page_mcp_tools helper**

```python
def test_discover_page_mcp_tools_yaml(tmp_path: Path) -> None:
    """Should discover mcp_tool from YAML auto-pages."""
    # Create a fake YAML page with mcp_tool blocks
    skill_dir = tmp_path / "skills" / "test-skill" / "augur" / "pages"
    skill_dir.mkdir(parents=True)
    (skill_dir / "overview.yaml").write_text(
        "title: Overview\nhub: test\nblocks:\n"
        "  - type: stat-grid\n    mcp_tool: get-test-counts\n"
        "  - type: data-table\n    mcp_tool: get-test-items\n"
    )
    # Also need SKILL.md for get_all_client_skill_dirs to find it
    (tmp_path / "skills" / "test-skill" / "SKILL.md").write_text(
        "---\nname: test-skill\n---\nTest"
    )
    tools = mod._discover_page_mcp_tools(tmp_path)
    tool_names = {t["mcp_tool"] for t in tools}
    assert "get-test-counts" in tool_names
    assert "get-test-items" in tool_names
    yaml_tools = [t for t in tools if t["source"] == "yaml_page"]
    assert len(yaml_tools) >= 2


def test_discover_page_mcp_tools_skillmd_blocks(tmp_path: Path) -> None:
    """Should discover data_source.mcp_tool from SKILL.md blocks."""
    skill_dir = tmp_path / "skills" / "test-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: test-skill\n"
        "x-augur-config:\n"
        "  contributions:\n"
        "    blocks:\n"
        "    - id: my-block\n"
        "      type: data-list\n"
        "      data_source:\n"
        "        mcp_tool: get-block-data\n"
        "---\nTest"
    )
    tools = mod._discover_page_mcp_tools(tmp_path)
    tool_names = {t["mcp_tool"] for t in tools}
    assert "get-block-data" in tool_names


def test_discover_page_mcp_tools_tsx_hooks(tmp_path: Path) -> None:
    """Should discover tool names from useMcpQuery/useMcpMutation in TSX."""
    dash_dir = tmp_path / "apps" / "dashboard" / "app" / "test"
    dash_dir.mkdir(parents=True)
    (dash_dir / "page.tsx").write_text(
        'const { data } = useMcpQuery<Foo>("key", "get-test-data", "config");\n'
        'const { mutate } = useMcpMutation("update-test-data");\n'
    )
    tools = mod._discover_page_mcp_tools(tmp_path)
    tool_names = {t["mcp_tool"] for t in tools}
    assert "get-test-data" in tool_names
    assert "update-test-data" in tool_names
```

- [ ] **Step 2: Write test for _response_has_data helper**

```python
def test_response_has_data_positive() -> None:
    assert mod._response_has_data({"items": [{"id": 1}], "count": 1}) is True
    assert mod._response_has_data({"data": {"key": "val"}}) is True
    assert mod._response_has_data({"count": 5}) is True


def test_response_has_data_negative() -> None:
    assert mod._response_has_data({"items": [], "count": 0}) is False
    assert mod._response_has_data({"error": "not found"}) is False
    assert mod._response_has_data({"success": True}) is False
```

- [ ] **Step 3: Run tests**

Run: `cd ~/Projects/Augur && python -m pytest skills/auto-e2e-pipeline/augur/tests/test_e2e_pipeline.py -v`
Expected: All tests PASS

- [ ] **Step 4: Smoke test d4 on real project (dashboard must be running)**

```python
ctx = OpsContext(project_root=Path('.').resolve(), difficulty=4)
r = mod.scan(ctx)
print(r.summary)
page_tool_issues = [i for i in r.issues if "page_tool" in i.get("broken_stage", "")]
print(f"\nPage-tool issues: {len(page_tool_issues)}")
for i in page_tool_issues[:10]:
    print(f"  [{i['broken_stage']}] {i['mcp_tool']} ({i['source_type']}, {i['skill']})")
```

Expected: Shows which page-referenced MCP tools return empty or error data.

- [ ] **Step 5: Commit**

```bash
git add skills/auto-e2e-pipeline/augur/tests/test_e2e_pipeline.py
git commit -m "test(auto-e2e-pipeline): add d4 page-tool audit tests and helpers"
```
