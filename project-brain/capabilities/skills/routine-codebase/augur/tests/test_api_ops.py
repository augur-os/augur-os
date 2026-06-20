"""Tests for auto-test-api vertical."""
import json
from pathlib import Path
from unittest.mock import patch
import importlib.util

from src.lib.ops_protocol import make_test_ctx
from src.config.paths import get_runtime_dir

# Import via importlib to avoid hyphenated path issues
_mcp_path = Path(__file__).resolve().parents[2] / "scripts" / "test_api_ops.py"
_spec = importlib.util.spec_from_file_location("test_api_ops", _mcp_path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

scan = _mod.scan
fix = _mod.fix
_classify_issue = _mod._classify_issue
_fix_stale_plugin_path = _mod._fix_stale_plugin_path
_MODULE_NAME = "test_api_ops"


def _make_api_tree(tmp_path, routes: dict[str, str]):
    """Create route.ts files. routes = {relative_path: content}."""
    for path, content in routes.items():
        route_file = tmp_path / "apps/dashboard/app" / path / "route.ts"
        route_file.parent.mkdir(parents=True, exist_ok=True)
        route_file.write_text(content)


def test_scan_no_api_dir(tmp_path):
    result = scan(make_test_ctx(tmp_path))
    assert result.severity == "info"


def test_scan_all_routes_ok(tmp_path):
    _make_api_tree(tmp_path, {"api/career/jobs": "export async function GET() {}"})
    with patch.object(_mod, "check_http_route") as mock_check:
        mock_check.return_value = {"ok": True, "status": 200}
        result = scan(make_test_ctx(tmp_path, difficulty=1))
    assert result.severity == "info"


def test_scan_route_fails(tmp_path):
    _make_api_tree(tmp_path, {"api/career/jobs": "export async function GET() {}"})
    with patch.object(_mod, "check_http_route") as mock_check:
        mock_check.side_effect = [
            {"ok": True, "status": 200},
            {"ok": False, "status": 500, "error": "Server Error"},
        ]
        result = scan(make_test_ctx(tmp_path, difficulty=1))
    assert result.severity == "error"
    assert len(result.issues) == 1


def test_scan_hub_scoped(tmp_path):
    _make_api_tree(tmp_path, {
        "api/career/jobs": "export async function GET() {}",
        "api/ai/chat": "export async function GET() {}",
    })
    with patch.object(_mod, "check_http_route") as mock_check:
        mock_check.return_value = {"ok": True, "status": 200}
        ctx = make_test_ctx(tmp_path, difficulty=1)
        ctx.config["hub"] = "career"
        scan(ctx)
    assert mock_check.call_count == 2  # base_url probe + one career route


def test_scan_skips_dynamic_segments(tmp_path):
    _make_api_tree(tmp_path, {
        "api/career/jobs": "export async function GET() {}",
        "api/career/jobs/[id]": "export async function GET() {}",
    })
    with patch.object(_mod, "check_http_route") as mock_check:
        mock_check.return_value = {"ok": True, "status": 200}
        scan(make_test_ctx(tmp_path, difficulty=1))
    assert mock_check.call_count == 2  # base_url probe + one static route


def test_discover_api_routes_uses_shared_snapshot(tmp_path):
    routes = _mod._discover_api_routes(
        tmp_path,
        shared_snapshot={
            "api_routes": ["/api/career/jobs", "/api/career/jobs/[id]", "/api/ai/chat"],
        },
    )

    assert routes == ["/api/ai/chat", "/api/career/jobs"]


def test_scan_uses_shared_snapshot_for_hub_scope(tmp_path):
    with patch.object(_mod, "check_http_route") as mock_check:
        mock_check.return_value = {"ok": True, "status": 200}
        ctx = make_test_ctx(
            tmp_path,
            difficulty=1,
            shared_snapshot={
                "api_routes": ["/api/career/jobs", "/api/ai/chat"],
            },
        )
        ctx.config["hub"] = "career"
        scan(ctx)

    assert mock_check.call_count == 2  # base_url probe + one career route


def test_scan_d0_uses_surface_check_without_http_probe(tmp_path):
    _make_api_tree(tmp_path, {"api/career/jobs": "export async function GET() {}"})
    with patch.object(_mod, "check_http_route", side_effect=AssertionError("d0 should not probe HTTP")):
        result = scan(make_test_ctx(tmp_path, difficulty=0))

    assert result.severity == "info"
    assert "d0 surface" in result.summary


def test_fix_dry_run(tmp_path):
    ctx = make_test_ctx(tmp_path, dry_run=True)
    result = fix(ctx, [{"route": "/api/career/jobs", "error": "500"}])
    assert result.success
    assert "Dry run" in result.summary


def test_fix_writes_report(tmp_path):
    result = fix(make_test_ctx(tmp_path), [{"route": "/api/career/jobs", "error": "500"}])
    assert result.success
    report = get_runtime_dir() / "reports" / "test-api-latest.json"
    assert report.exists()


# ---------------------------------------------------------------------------
# Root-cause classification tests
# ---------------------------------------------------------------------------


def test_classify_stale_plugin_path_auto_fixable(tmp_path):
    """Stale plugins/ path with project-brain/capabilities/skills equivalent = auto-fixable."""
    route_content = '''
import { createAPIRoute } from "@/lib/mcp/createAPIRoute";
    const scriptPath = "plugins/observability/skills/monitor/scripts/health.py";
export const GET = createAPIRoute({ toolName: "get-health" });
'''
    _make_api_tree(tmp_path, {"api/health/check": route_content})
    # Create the project-brain/capabilities/skills equivalent
    target = tmp_path / "project-brain/capabilities/skills/monitor/scripts/health.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("# health script")

    result = _classify_issue(tmp_path, "/api/health/check", {"status": 500, "error": "err"})
    assert result["pattern"] == "stale-plugin-path"
    assert result["fixability"] == "auto"
    assert "health.py" in result["message"]
    assert result["fix_detail"]["old_path"] == "plugins/observability/skills/monitor/scripts/health.py"
    assert result["fix_detail"]["new_path"] == "project-brain/capabilities/skills/monitor/scripts/health.py"


def test_classify_stale_plugin_path_no_target(tmp_path):
    """Stale plugins/ path without project-brain/capabilities/skills equivalent = manual."""
    route_content = '''
    const scriptPath = "plugins/observability/skills/missing-skill/scripts/run.py";
export const GET = createAPIRoute({ toolName: "run" });
'''
    _make_api_tree(tmp_path, {"api/run": route_content})

    result = _classify_issue(tmp_path, "/api/run", {"status": 500, "error": "err"})
    assert result["pattern"] == "stale-plugin-path-no-target"
    assert result["fixability"] == "manual"


def test_classify_python_runner_bypass(tmp_path):
    """Route using runPythonScript = manual fix (Rule #11)."""
    route_content = '''
import { runPythonScript } from "@/lib/server/pythonRunner";
export async function GET() { return runPythonScript("foo.py"); }
'''
    _make_api_tree(tmp_path, {"api/legacy": route_content})

    result = _classify_issue(tmp_path, "/api/legacy", {"status": 500, "error": "err"})
    assert result["pattern"] == "python-runner-bypass"
    assert result["fixability"] == "manual"


def test_classify_python_code_bypass(tmp_path):
    """Route using runPythonCode = manual fix (Rule #11)."""
    route_content = '''
import { runPythonCode } from "@/lib/server/pythonRunner";
export async function GET() { return runPythonCode("print(1)"); }
'''
    _make_api_tree(tmp_path, {"api/legacy2": route_content})

    result = _classify_issue(tmp_path, "/api/legacy2", {"status": 500, "error": "err"})
    assert result["pattern"] == "python-runner-bypass"
    assert result["fixability"] == "manual"


def test_classify_missing_source(tmp_path):
    """Missing route.ts = manual."""
    result = _classify_issue(tmp_path, "/api/nowhere", {"status": 500, "error": "err"})
    assert result["pattern"] == "missing-source"
    assert result["fixability"] == "manual"


def test_classify_unregistered_tool(tmp_path):
    """Route with toolName not found in MCP registrations = unregistered-tool."""
    route_content = '''
import { createAPIRoute } from "@/lib/mcp/createAPIRoute";
export const GET = createAPIRoute({ toolName: "some-tool" });
'''
    _make_api_tree(tmp_path, {"api/clean-route": route_content})

    result = _classify_issue(tmp_path, "/api/clean-route", {"status": 500, "error": "err"})
    assert result["pattern"] == "unregistered-tool"
    assert result["fixability"] == "manual"
    assert "some-tool" in result["message"]


def test_classify_tool_registered_but_502(tmp_path):
    """Route with registered tool but 502 = environment issue."""
    route_content = '''
import { createAPIRoute } from "@/lib/mcp/createAPIRoute";
export const GET = createAPIRoute({ toolName: "test-registered-tool" });
'''
    _make_api_tree(tmp_path, {"api/health": route_content})
    # Register the tool in src/mcp/
    mcp_file = tmp_path / "src" / "mcp" / "tools" / "test_tools.py"
    mcp_file.parent.mkdir(parents=True, exist_ok=True)
    mcp_file.write_text('name="test-registered-tool"')

    result = _classify_issue(tmp_path, "/api/health", {"status": 502, "error": "Bad Gateway"})
    assert result["pattern"] == "tool-registered-but-502"
    assert result["fixability"] == "environment"


def test_classify_tool_runtime_error(tmp_path):
    """Route with registered tool but 500 = runtime error in tool."""
    route_content = '''
import { createAPIRoute } from "@/lib/mcp/createAPIRoute";
export const GET = createAPIRoute({ toolName: "test-runtime-tool" });
'''
    _make_api_tree(tmp_path, {"api/data": route_content})
    # Register the tool in src/mcp/
    mcp_file = tmp_path / "src" / "mcp" / "tools" / "runtime_tools.py"
    mcp_file.parent.mkdir(parents=True, exist_ok=True)
    mcp_file.write_text('name="test-runtime-tool"')

    result = _classify_issue(tmp_path, "/api/data", {"status": 500, "error": "Internal Error"})
    assert result["pattern"] == "tool-runtime-error"
    assert result["fixability"] == "manual"


def test_classify_unknown(tmp_path):
    """Route with no toolName and no recognizable pattern = unknown."""
    route_content = '''
import { NextResponse } from "next/server";
export async function GET() { return NextResponse.json({ ok: true }); }
'''
    _make_api_tree(tmp_path, {"api/clean-route": route_content})

    result = _classify_issue(tmp_path, "/api/clean-route", {"status": 500, "error": "err"})
    assert result["pattern"] == "unknown"
    assert result["fixability"] == "unknown"


# ---------------------------------------------------------------------------
# Auto-fix tests
# ---------------------------------------------------------------------------


def test_fix_stale_plugin_path_replaces_string(tmp_path):
    """fix() rewrites stale plugins/ path to project-brain/capabilities/skills in route.ts."""
    route_content = '''
import { createAPIRoute } from "@/lib/mcp/createAPIRoute";
    const scriptPath = "plugins/observability/skills/monitor/scripts/health.py";
export const GET = createAPIRoute({ toolName: "get-health" });
'''
    _make_api_tree(tmp_path, {"api/health/check": route_content})
    # Create the project-brain/capabilities/skills equivalent
    target = tmp_path / "project-brain/capabilities/skills/monitor/scripts/health.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("# health script")

    route_file = tmp_path / "apps/dashboard/app/api/health/check/route.ts"
    issue = {
        "route": "/api/health/check",
        "route_file": str(route_file),
        "pattern": "stale-plugin-path",
        "fixability": "auto",
        "fix_detail": {
            "old_path": "plugins/observability/skills/monitor/scripts/health.py",
            "new_path": "project-brain/capabilities/skills/monitor/scripts/health.py",
        },
    }

    action = _fix_stale_plugin_path(tmp_path, issue)
    assert "fixed" in action
    assert action["pattern"] == "stale-plugin-path"

    updated = route_file.read_text()
    assert "plugins/observability/skills/monitor" not in updated
    assert "project-brain/capabilities/skills/monitor/scripts/health.py" in updated
    assert "project-brain/capabilities/skills/monitor/scripts/health.py" in updated


def test_fix_mixed_auto_and_manual(tmp_path):
    """fix() auto-fixes what it can and reports the rest."""
    route_content = '''
const scriptPath = "skills/monitor/scripts/health.py";
'''
    _make_api_tree(tmp_path, {"api/health/check": route_content})
    target = tmp_path / "project-brain/capabilities/skills/monitor/scripts/health.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("# health script")

    route_file = tmp_path / "apps/dashboard/app/api/health/check/route.ts"

    issues = [
        {
            "route": "/api/health/check",
            "route_file": str(route_file),
            "pattern": "stale-plugin-path",
            "fixability": "auto",
            "fix_detail": {
                "old_path": "skills/monitor/scripts/health.py",
                "new_path": "project-brain/capabilities/skills/monitor/scripts/health.py",
            },
        },
        {
            "route": "/api/legacy",
            "route_file": str(tmp_path / "apps/dashboard/app/api/legacy/route.ts"),
            "pattern": "python-runner-bypass",
            "fixability": "manual",
            "message": "Uses runPythonScript",
        },
    ]

    result = fix(make_test_ctx(tmp_path), issues)
    assert result.success
    assert len(result.changes) == 1  # only auto-fix applied
    assert "auto-fixed 1 route(s)" in result.summary
    assert "1 code bug(s)" in result.summary
    assert result.fix_type == "code-fix"

    # Verify the file was actually updated
    updated = route_file.read_text()
    assert "project-brain/capabilities/skills/monitor/scripts/health.py" in updated


def test_fix_dry_run_with_classification(tmp_path):
    """Dry run with classified issues reports counts."""
    ctx = make_test_ctx(tmp_path, dry_run=True)
    issues = [
        {"fixability": "auto", "pattern": "stale-plugin-path"},
        {"fixability": "manual", "pattern": "python-runner-bypass"},
        {"fixability": "manual", "pattern": "unknown"},
    ]
    result = fix(ctx, issues)
    assert result.success
    assert "1 auto-fixable" in result.summary
    assert "2 manual" in result.summary


def test_fix_all_manual_writes_report(tmp_path):
    """When all issues are manual, only a report is written."""
    issues = [
        {
            "route": "/api/legacy",
            "fixability": "manual",
            "pattern": "python-runner-bypass",
            "message": "Uses runPythonScript",
        },
    ]
    result = fix(make_test_ctx(tmp_path), issues)
    assert result.success
    assert result.fix_type == "verified"
    assert result.actions
    assert len(result.changes) == 0
    report = get_runtime_dir() / "reports" / "test-api-latest.json"
    assert report.exists()
    data = json.loads(report.read_text())
    assert len(data["issues"]) == 1


def test_scan_classifies_issues(tmp_path):
    """Scan attaches classification metadata to each issue."""
    route_content = '''
import { runPythonScript } from "@/lib/server/pythonRunner";
export async function GET() { return runPythonScript("foo.py"); }
'''
    _make_api_tree(tmp_path, {"api/legacy": route_content})

    with patch.object(_mod, "check_http_route") as mock_check:
        mock_check.side_effect = [
            {"ok": True, "status": 200},   # dashboard probe
            {"ok": False, "status": 500, "error": "Internal Server Error"},
        ]
        result = scan(make_test_ctx(tmp_path, difficulty=2))

    assert len(result.issues) == 1
    issue = result.issues[0]
    assert issue["pattern"] == "python-runner-bypass"
    assert issue["fixability"] == "manual"
    assert "runPythonScript" in issue["message"]


def test_scan_summary_includes_fixability_counts(tmp_path):
    """Summary line reports auto-fixable and manual counts."""
    route1 = '''
    const scriptPath = "plugins/observability/skills/monitor/scripts/health.py";
export const GET = createAPIRoute({ toolName: "get-health" });
'''
    route2 = '''
import { runPythonScript } from "@/lib/server/pythonRunner";
export async function GET() { return runPythonScript("foo.py"); }
'''
    _make_api_tree(tmp_path, {"api/health": route1, "api/legacy": route2})
    # Create project-brain/capabilities/skills target so route1 is auto-fixable
    target = tmp_path / "project-brain/capabilities/skills/monitor/scripts/health.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("# health")

    with patch.object(_mod, "check_http_route") as mock_check:
        mock_check.side_effect = [
            {"ok": True, "status": 200},   # dashboard probe
            {"ok": False, "status": 500, "error": "err"},
            {"ok": False, "status": 500, "error": "err"},
        ]
        result = scan(make_test_ctx(tmp_path, difficulty=2))

    assert "1 auto-fixable" in result.summary
    assert "1 manual" in result.summary
