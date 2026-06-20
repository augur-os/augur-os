"""Tests for auto-mcp-health-audit."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import patch

from src.lib.ops_protocol import FixResult, OpsContext, ScanResult, make_issue

# Dynamic import of script module
_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "mcp_health_audit.py"
_SPEC = importlib.util.spec_from_file_location("mcp_health_audit", _MODULE_PATH)
mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mod)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _ctx(tmp_path: Path, difficulty: int = 0, **kw) -> OpsContext:
    return OpsContext(project_root=tmp_path, difficulty=difficulty, **kw)


# ── Phase 1a: Route toolName extraction ──


def test_extract_route_tool_names_basic(tmp_path: Path) -> None:
    """Extracts toolName values from _routes-*.ts files."""
    routes_dir = tmp_path / "apps" / "dashboard" / "app" / "api" / "[...proxy]"
    _write(
        routes_dir / "_routes-a.ts",
        '''export const ROUTES_A: RouteMap = {
  "browse/items": {
    GET: {
      toolName: "browse-index",
    },
  },
  "career/companies": {
    GET: {
      toolName: "get-career-companies",
      fallback: { success: true, data: [] },
    },
    POST: {
      toolName: "create-career-company",
    },
  },
};''',
    )

    result = mod.extract_route_tool_names(tmp_path)

    assert "browse-index" in result
    assert "get-career-companies" in result
    assert "create-career-company" in result
    assert result["browse-index"] == ["browse/items"]
    assert result["get-career-companies"] == ["career/companies"]


def test_extract_route_tool_names_empty(tmp_path: Path) -> None:
    """Returns empty dict when no route files exist."""
    result = mod.extract_route_tool_names(tmp_path)
    assert result == {}


# ── Phase 1b: MCP registration extraction ──


def test_extract_mcp_registrations_basic(tmp_path: Path) -> None:
    """Extracts @mcp.tool(name=...) from Python files."""
    core_dir = tmp_path / "src" / "mcp" / "augur_framework" / "core"
    _write(
        core_dir / "skills.py",
        '''
@mcp.tool(name="list-skills")
async def list_skills_tool():
    pass

@mcp.tool(name="get-skill")
async def get_skill_tool():
    pass
''',
    )

    plugin_dir = tmp_path / ".claude" / "skills" / "scraper" / "scripts" / "mcp"
    _write(
        plugin_dir / "__init__.py",
        '''
@mcp.tool(
    name="get-scraper-status",
    annotations=tool_annotations(readOnlyHint=True),
)
async def get_scraper_status():
    pass
''',
    )

    _write(
        plugin_dir / "_tools.py",
        '''
@mcp.tool(name="scrape-url")
async def scrape_url():
    pass
''',
    )

    result = mod.extract_mcp_registrations(tmp_path)

    assert "list-skills" in result
    assert "get-skill" in result
    assert "get-scraper-status" in result
    assert "scrape-url" in result
    assert "skills.py" in result["list-skills"]


def test_extract_mcp_registrations_empty(tmp_path: Path) -> None:
    """Returns empty dict when no Python MCP files exist."""
    result = mod.extract_mcp_registrations(tmp_path)
    assert result == {}


# ── Phase 1c-d: Cross-reference and fuzzy match ──


def test_cross_reference_finds_mismatches(tmp_path: Path) -> None:
    """Detects toolNames in routes that have no MCP registration."""
    route_tools = {"browse-index": ["browse/items"], "fake-tool": ["fake/route"]}
    mcp_tools = {"browse-index": "src/mcp/core/browse.py"}

    result = mod.cross_reference(route_tools, mcp_tools)

    assert len(result["mismatches"]) == 1
    assert result["mismatches"][0]["tool_name"] == "fake-tool"
    assert len(result["wired"]) == 1
    assert "browse-index" in result["wired"]


def test_cross_reference_finds_orphans(tmp_path: Path) -> None:
    """Detects registered tools with no route consumer."""
    route_tools = {"browse-index": ["browse/items"]}
    mcp_tools = {
        "browse-index": "src/mcp/core/browse.py",
        "orphan-tool": "src/mcp/core/orphan.py",
    }

    result = mod.cross_reference(route_tools, mcp_tools)

    assert len(result["orphans"]) == 1
    assert result["orphans"][0]["tool_name"] == "orphan-tool"


def test_summarize_orphans_groups_by_owner() -> None:
    summary = mod.summarize_orphans([
        {"tool_name": "apple-a", "file": "skills/apple/scripts/mcp/tools_notes.py"},
        {"tool_name": "apple-b", "file": "skills/apple/scripts/mcp/tools_voice.py"},
        {"tool_name": "core-a", "file": "src/mcp/augur_framework/core/tools.py"},
        {"tool_name": "plugin-a", "file": "skills/channels/scripts/mcp/__init__.py"},
    ], limit=3)

    assert "skills/apple (2)" in summary
    assert "src/mcp/augur_framework (1)" in summary
    assert "skills/channels (1)" in summary


def test_fuzzy_match_suggests_close_names(tmp_path: Path) -> None:
    """Suggests fuzzy matches for mismatched toolNames."""
    route_tools = {"get-career-company": ["career/companies"]}
    mcp_tools = {"get-career-companies": "src/mcp/career.py"}

    result = mod.cross_reference(route_tools, mcp_tools)

    assert len(result["mismatches"]) == 1
    mismatch = result["mismatches"][0]
    assert mismatch["closest_match"] == "get-career-companies"
    assert mismatch["distance"] <= 2


# ── Phase 2: Runtime probe ──


def test_classify_probe_response_healthy() -> None:
    result = mod.classify_probe_response(200, {"data": [1, 2, 3]})
    assert result["status"] == "healthy"


def test_classify_probe_response_fallback() -> None:
    result = mod.classify_probe_response(200, {"_fallback": True, "_reason": "tool_error"})
    assert result["status"] == "fallback-masked"


def test_classify_probe_response_app_error() -> None:
    result = mod.classify_probe_response(200, {"error": "Something failed"})
    assert result["status"] == "app-error"


def test_classify_probe_response_500() -> None:
    result = mod.classify_probe_response(500, {"error": "ImportError: no module named foo"})
    assert result["status"] == "runtime-error"


def test_fingerprint_error_import() -> None:
    assert mod.fingerprint_error("ImportError: No module named 'foo'") == "import-error"


def test_fingerprint_error_file_not_found() -> None:
    assert mod.fingerprint_error("FileNotFoundError: /path/to/data") == "missing-file"


def test_fingerprint_error_needs_args() -> None:
    assert mod.fingerprint_error("TypeError: missing 1 required positional argument") == "needs-args"


def test_probe_all_tools_aborts_on_server_down() -> None:
    """Stops probing when server is truly unreachable (ConnectionRefused)."""
    import urllib.error
    with patch.object(mod.urllib.request, "urlopen") as mock_urlopen:
        mock_urlopen.side_effect = urllib.error.URLError(ConnectionRefusedError("Connection refused"))
        results = mod.probe_all_tools(["tool-a", "tool-b", "tool-c"])
        assert len(results) == 1
        assert results[0]["status"] == "server-down"


# ── Phase 3: Auto-fix ──


def test_fix_toolname_typo(tmp_path: Path) -> None:
    routes_dir = tmp_path / "apps" / "dashboard" / "app" / "api" / "[...proxy]"
    _write(routes_dir / "_routes-a.ts", '''export const ROUTES_A: RouteMap = {
  "career/companies": {
    GET: {
      toolName: "get-career-company",
    },
  },
};''')
    changes = mod.fix_toolname_typo(tmp_path, "get-career-company", "get-career-companies")
    assert len(changes) == 1
    content = (routes_dir / "_routes-a.ts").read_text()
    assert "get-career-companies" in content
    assert "get-career-company" not in content


def test_fix_missing_data_dir(tmp_path: Path) -> None:
    target = tmp_path / "some" / "data" / "dir"
    assert not target.exists()
    changes = mod.fix_missing_dir(str(target))
    assert len(changes) == 1
    assert target.exists()


def test_apply_safe_fixes_respects_limit(tmp_path: Path) -> None:
    issues = [{"fix_type": "toolname-typo", "wrong_name": "a", "correct_name": "b", "affected_files": ["f1", "f2", "f3", "f4"]}]
    result = mod.apply_safe_fixes(tmp_path, issues)
    assert result["skipped"] == 1


# ── Phase 4: Report ──


def test_generate_report_markdown(tmp_path: Path) -> None:
    audit_data = {
        "phase1": {
            "route_count": 10, "registered_count": 8,
            "mismatches": [{"tool_name": "fake-tool", "routes": ["fake/route"], "closest_match": "fake-tools", "distance": 1}],
            "wired": ["browse-index"],
            "orphans": [{"tool_name": "orphan", "file": "src/orphan.py"}],
            "orphan_summary": "src/orphan (1)",
        },
        "phase2": {"healthy": [{"tool_name": "browse-index", "status": "healthy"}], "failures": [], "fallback_masked": []},
        "phase3": {"applied": 0, "skipped": 0, "changes": []},
    }
    report = mod.generate_report(audit_data)
    assert "## Critical: Wiring Mismatches" in report


def test_scan_d0_ignores_orphan_tools_as_action_items(tmp_path: Path) -> None:
    """Unproxied MCP tools are inventory, not d0 maintenance debt."""
    routes_dir = tmp_path / "apps" / "dashboard" / "app" / "api" / "[...proxy]"
    _write(
        routes_dir / "_routes-a.ts",
        '''export const ROUTES_A: RouteMap = {
  "browse/items": {
    GET: {
      toolName: "browse-index",
    },
  },
};''',
    )
    _write(
        tmp_path / "src" / "mcp" / "augur_framework" / "core" / "tools.py",
        '''
@mcp.tool(name="browse-index")
async def browse_index():
    pass

@mcp.tool(name="agent-only-tool")
async def agent_only_tool():
    pass
''',
    )

    result = mod.scan(_ctx(tmp_path, difficulty=0))

    assert result.health == "verified"
    assert result.severity == "info"
    assert result.issues == []


def test_scan_d2_rolls_orphan_inventory_into_single_evolution_gap(tmp_path: Path) -> None:
    """Higher difficulty should emit one bounded evolution gap, not one issue per orphan."""
    routes_dir = tmp_path / "apps" / "dashboard" / "app" / "api" / "[...proxy]"
    _write(
        routes_dir / "_routes-a.ts",
        '''export const ROUTES_A: RouteMap = {
  "browse/items": {
    GET: {
      toolName: "browse-index",
    },
  },
};''',
    )
    _write(
        tmp_path / "src" / "mcp" / "augur_framework" / "core" / "tools.py",
        '''
@mcp.tool(name="browse-index")
async def browse_index():
    pass

@mcp.tool(name="agent-only-tool")
async def agent_only_tool():
    pass
''',
    )

    with patch.object(mod, "probe_all_tools", return_value=[{"tool_name": "browse-index", "status": "healthy"}]):
        result = mod.scan(_ctx(tmp_path, difficulty=2))

    assert len(result.issues) == 1
    assert result.issues[0]["kind"] == "maintenance"
    assert "outside dashboard proxy coverage" in result.issues[0]["detail"]


# ── OpsCommand protocol: scan() and fix() ──


def test_scan_d0_static_only(tmp_path: Path) -> None:
    routes_dir = tmp_path / "apps" / "dashboard" / "app" / "api" / "[...proxy]"
    _write(routes_dir / "_routes-a.ts", 'export const ROUTES_A = {\n  "x/y": {\n    GET: {\n      toolName: "real-tool",\n    },\n  },\n};')
    mcp_dir = tmp_path / "src" / "mcp" / "augur_framework" / "core"
    _write(mcp_dir / "tools.py", '@mcp.tool(name="real-tool")\nasync def f(): pass')
    result = mod.scan(_ctx(tmp_path, difficulty=0))
    assert isinstance(result, ScanResult)
    assert result.health in ("verified", "degraded", "broken")


def test_scan_d0_finds_mismatch(tmp_path: Path) -> None:
    routes_dir = tmp_path / "apps" / "dashboard" / "app" / "api" / "[...proxy]"
    _write(routes_dir / "_routes-a.ts", 'export const ROUTES_A = {\n  "x/y": {\n    GET: {\n      toolName: "missing-tool",\n    },\n  },\n};')
    result = mod.scan(_ctx(tmp_path, difficulty=0))
    assert result.health == "broken"
    assert len(result.issues) >= 1
    assert any(i["category"] == "wiring-mismatch" for i in result.issues)


def test_fix_returns_fix_result(tmp_path: Path) -> None:
    issues = [make_issue(category="wiring-mismatch", detail="test", path="test", kind="actionable")]
    result = mod.fix(_ctx(tmp_path, difficulty=2), issues)
    assert isinstance(result, FixResult)


def test_module_has_name_and_difficulty_spec() -> None:
    assert hasattr(mod, "name")
    assert mod.name == "auto-mcp-health-audit"
    assert hasattr(mod, "DIFFICULTY_SPEC")
    assert 0 in mod.DIFFICULTY_SPEC
    assert 4 in mod.DIFFICULTY_SPEC


# ── ADR-465 / proxy-deletion regression ──


def test_scan_skips_orphan_calc_when_proxy_dir_missing(tmp_path: Path) -> None:
    """Without [...proxy]/_routes-*.ts, every registered tool would be 'orphan'.

    Regression: after the proxy route layer was deleted (ADR-465 / commit
    a688ad5ca), `route_tools` is always empty. The pre-fix scanner then
    computed `orphans = registered - {} = registered`, surfacing every MCP
    tool as orphan inventory every run. The fix short-circuits the
    cross-reference when no proxy is present and never produces orphan
    issues from a non-existent proxy.
    """
    _write(
        tmp_path / "src" / "mcp" / "augur_framework" / "core" / "tools.py",
        '@mcp.tool(name="alpha")\nasync def a(): pass\n'
        '@mcp.tool(name="beta")\nasync def b(): pass\n',
    )
    # Note: NO [...proxy] dir created.

    result = mod.scan(_ctx(tmp_path, difficulty=0))

    assert result.health == "verified"
    assert result.issues == []


def test_scan_d2_proxy_missing_emits_single_evolution_gap(tmp_path: Path) -> None:
    """With proxy gone, d2 must emit ONE evolution gap, not 324 orphan issues."""
    mcp_dir = tmp_path / "src" / "mcp" / "augur_framework" / "core"
    body = "\n".join(f'@mcp.tool(name="t{i}")\nasync def t{i}(): pass' for i in range(20))
    _write(mcp_dir / "tools.py", body)

    with patch.object(mod, "probe_all_tools", return_value=[]):
        result = mod.scan(_ctx(tmp_path, difficulty=2))

    assert len(result.issues) == 1
    assert result.issues[0]["kind"] == "maintenance"
    assert "proxy" in result.issues[0]["detail"].lower()


def test_scan_proxy_present_still_detects_orphan(tmp_path: Path) -> None:
    """Sanity: when the proxy DOES exist, orphan detection still works."""
    routes_dir = tmp_path / "apps" / "dashboard" / "app" / "api" / "[...proxy]"
    _write(
        routes_dir / "_routes-a.ts",
        'export const ROUTES_A = {\n  "x/y": {\n    GET: {\n      toolName: "wired-tool",\n    },\n  },\n};',
    )
    _write(
        tmp_path / "src" / "mcp" / "augur_framework" / "core" / "tools.py",
        '@mcp.tool(name="wired-tool")\nasync def w(): pass\n'
        '@mcp.tool(name="orphan-tool")\nasync def o(): pass\n',
    )

    with patch.object(mod, "probe_all_tools", return_value=[{"tool_name": "wired-tool", "status": "healthy"}]):
        result = mod.scan(_ctx(tmp_path, difficulty=2))

    # Should emit a single evolution gap mentioning orphan-tool coverage.
    assert len(result.issues) == 1
    assert "outside dashboard proxy coverage" in result.issues[0]["detail"]
