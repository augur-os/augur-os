"""Unit tests for src.lib.ops_protocol._core.

Exercises the data models and shared helpers not already covered by
tests/unit/test_ops_protocol_capabilities.py: issue construction and
fingerprinting, evolution gaps, the report-only fix path, report
read/write/clear (runtime dir redirected to tmp_path), the test-ctx
factory, module protocol validation, and platform normalization.
"""

from __future__ import annotations

import json
from pathlib import Path

import src.lib.ops_protocol._core as core
from src.lib.ops_protocol._core import (
    FixResult,
    OpsContext,
    ScanResult,
    SessionContext,
    _normalize_platform_name,
    clear_report,
    evolution_gap,
    issue_fingerprint,
    make_issue,
    make_test_ctx,
    report_only_fix,
    validate_ops_module,
    write_report,
)


def test_scanresult_defaults():
    r = ScanResult()
    assert r.issues == []
    assert r.severity == "info"
    assert r.health == "verified"
    assert r.items_scanned is None
    assert r.run_fix_on_clean is False


def test_session_context_defaults():
    s = SessionContext()
    assert s.has_tool_access is False
    assert s.max_turns == 20
    assert s.timeout == 600


def test_issue_fingerprint_stable_and_normalized():
    a = issue_fingerprint("cat", "actionable", "/Some/Path", "Detail   Text")
    b = issue_fingerprint("cat", "actionable", "/some/path", "detail text")
    assert a == b
    assert len(a) == 16
    # Different category -> different fingerprint.
    assert issue_fingerprint("other", "actionable", "/some/path", "detail text") != a


def test_make_issue_populates_metadata_and_fingerprint():
    issue = make_issue(
        category="lint",
        detail="missing newline",
        path="src/x.py",
        kind="actionable",
        extra_field="hello",
    )
    assert issue["category"] == "lint"
    assert issue["kind"] == "actionable"
    assert issue["root_cause_type"] == "unknown"
    assert issue["fixability"] == "unknown"
    assert issue["extra_field"] == "hello"
    # Fingerprint matches the standalone helper.
    assert issue["fingerprint"] == issue_fingerprint(
        category="lint", kind="actionable", path="src/x.py", detail="missing newline"
    )


def test_make_issue_respects_explicit_fingerprint():
    issue = make_issue(category="c", detail="d", fingerprint="deadbeef")
    assert issue["fingerprint"] == "deadbeef"


def test_evolution_gap_shape():
    gap = evolution_gap("coverage stalled at 40%")
    assert gap["category"] == "evolution"
    assert gap["kind"] == "maintenance"
    assert gap["root_cause_type"] == "manual_debt"
    assert gap["fixability"] == "manual"
    assert gap["detail"] == "coverage stalled at 40%"
    # Custom category honored.
    assert evolution_gap("x", category="drift")["category"] == "drift"


def test_make_test_ctx_defaults_and_overrides(tmp_path: Path):
    ctx = make_test_ctx(tmp_path)
    assert ctx.project_root == tmp_path
    assert ctx.dry_run is False
    ctx2 = make_test_ctx(tmp_path, dry_run=True, verbose=True)
    assert ctx2.dry_run is True
    assert ctx2.verbose is True


def test_report_only_fix_dry_run_writes_nothing(tmp_path: Path):
    ctx = make_test_ctx(tmp_path, dry_run=True)
    result = report_only_fix(ctx, "report.json", [{"a": 1}, {"b": 2}], noun="finding")
    assert isinstance(result, FixResult)
    assert result.success is True
    assert "Dry run: 2 finding(s)" == result.summary
    assert result.actions == []


def test_report_only_fix_writes_report(tmp_path: Path, monkeypatch):
    runtime = tmp_path / "runtime"
    monkeypatch.setattr(core, "get_runtime_dir", lambda: runtime)
    ctx = make_test_ctx(tmp_path, dry_run=False)
    result = report_only_fix(ctx, "findings.json", [{"x": 1}], noun="finding")
    assert result.success is True
    report_path = runtime / "reports" / "findings.json"
    assert report_path.is_file()
    payload = json.loads(report_path.read_text())
    assert payload == {"issues": [{"x": 1}]}
    assert result.actions == [{"report": str(report_path)}]


def test_write_and_clear_report_roundtrip(tmp_path: Path, monkeypatch):
    runtime = tmp_path / "runtime"
    monkeypatch.setattr(core, "get_runtime_dir", lambda: runtime)
    ctx = OpsContext(project_root=tmp_path)
    path = write_report(ctx, "r.json", {"k": "v"})
    assert path.is_file()
    assert json.loads(path.read_text()) == {"k": "v"}
    clear_report("r.json")
    assert not path.exists()
    # Clearing a missing report is a no-op (no exception).
    clear_report("r.json")


def test_validate_ops_module():
    class Good:
        name = "good"

        def scan(self, ctx):
            return ScanResult()

        def fix(self, ctx, issues):
            return FixResult()

    class MissingName:
        def scan(self, ctx):
            return ScanResult()

        def fix(self, ctx, issues):
            return FixResult()

    class NotCallable:
        name = "x"
        scan = "nope"
        fix = "nope"

    assert validate_ops_module(Good()) is True
    assert validate_ops_module(MissingName()) is False
    assert validate_ops_module(NotCallable()) is False


def test_normalize_platform_name():
    assert _normalize_platform_name("win32") == "windows"
    assert _normalize_platform_name("cygwin") == "windows"
    assert _normalize_platform_name("Darwin") == "macos"
    assert _normalize_platform_name("linux2") == "linux"
    assert _normalize_platform_name("freebsd") == "freebsd"
