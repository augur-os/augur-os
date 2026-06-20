"""Regression tests for ADR audit issue semantics."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from src.lib.ops_protocol import make_test_ctx as _ctx


MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "ops" / "adr_audit.py"
SPEC = importlib.util.spec_from_file_location("adr_audit_module", MODULE_PATH)
assert SPEC and SPEC.loader
adr_audit_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(adr_audit_module)


def test_status_format_issue_is_maintenance(tmp_path, monkeypatch) -> None:
    decisions_dir = tmp_path / "docs" / "decisions"
    decisions_dir.mkdir(parents=True)
    adr_path = decisions_dir / "ADR-412-example.md"
    adr_path.write_text("**Status**: implemented\n", encoding="utf-8")

    monkeypatch.setattr(
        adr_audit_module,
        "scan_adrs",
        lambda _path: [{"number": 412, "status": "implemented", "path": adr_path}],
    )
    monkeypatch.setattr(adr_audit_module, "find_duplicate_adrs", lambda _path: {})
    monkeypatch.setattr(adr_audit_module, "detect_stale_status", lambda *_args, **_kwargs: [])

    result = adr_audit_module.scan(_ctx(tmp_path))

    assert len(result.issues) == 1
    issue = result.issues[0]
    assert issue["type"] == "status_format"
    assert issue["kind"] == "maintenance"
    assert issue["root_cause_type"] == "generated_artifact"


def test_missing_file_issue_is_manual(tmp_path, monkeypatch) -> None:
    decisions_dir = tmp_path / "docs" / "decisions"
    decisions_dir.mkdir(parents=True)
    adr_path = decisions_dir / "ADR-411-example.md"
    adr_path.write_text("See `src/missing/module.py`\n", encoding="utf-8")

    monkeypatch.setattr(
        adr_audit_module,
        "scan_adrs",
        lambda _path: [{"number": 411, "status": "Implemented", "path": adr_path}],
    )
    monkeypatch.setattr(adr_audit_module, "find_duplicate_adrs", lambda _path: {})
    monkeypatch.setattr(adr_audit_module, "detect_stale_status", lambda *_args, **_kwargs: [])

    result = adr_audit_module.scan(_ctx(tmp_path))

    assert len(result.issues) == 1
    issue = result.issues[0]
    assert issue["type"] == "missing_file"
    assert issue["kind"] == "manual"
    assert issue["root_cause_type"] == "manual_debt"


def test_adr_audit_uses_canonical_adr_dir(monkeypatch, tmp_path) -> None:
    decisions_dir = tmp_path / "external-adrs"
    decisions_dir.mkdir(parents=True)
    adr_path = decisions_dir / "ADR-420-example.md"
    adr_path.write_text(
        "---\nstatus: Implemented\ndate: '2026-04-19'\n---\n"
        "# ADR-420: Example\n\nSee `src/missing/module.py`.\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(adr_audit_module, "get_adr_dir", lambda: decisions_dir)

    result = adr_audit_module.scan(_ctx(tmp_path))

    assert result.summary.startswith("Scanned 1 recent ADRs")
    assert result.issues
    assert result.issues[0]["type"] == "missing_file"
    assert result.issues[0]["file"] == str(adr_path)
