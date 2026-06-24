"""Tests for the dream MCP + CLI registration (ADR-744 task 10).

Confirms both the MCP-side ``register_tools`` and the CLI-side
``register_subcommands`` expose every dream tool / verb the routine relies
on. Uses a tiny FastMCP-compatible mock to capture tool names + annotations
so the test doesn't pull the FastMCP runtime into the test environment.
"""
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "mcp" / "__init__.py"
_SPEC = importlib.util.spec_from_file_location("dream_mcp", _MODULE_PATH)
assert _SPEC and _SPEC.loader
mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mod)

_FIXTURES_PATH = Path(__file__).resolve().parent / "_fixtures.py"
_FIX_SPEC = importlib.util.spec_from_file_location("dream_test_fixtures", _FIXTURES_PATH)
assert _FIX_SPEC and _FIX_SPEC.loader
_fix = importlib.util.module_from_spec(_FIX_SPEC)
_FIX_SPEC.loader.exec_module(_fix)


@pytest.fixture
def fixture_vault(tmp_path: Path) -> Path:
    return _fix.build_fixture_vault(tmp_path)


@pytest.fixture
def fixture_graph_cache(tmp_path: Path) -> Path:
    return _fix.build_fixture_graph_cache(tmp_path)


EXPECTED_TOOLS = {
    "dream-orphans",
    "dream-stale-pages",
    "dream-merge-candidates",
    "dream-dead-citations",
    "dream-cache-gc",
    "dream-report-write",
    "dream-last-report",
    "dream-status",
    "dream-config",
}


EXPECTED_VERBS = {
    "orphans",
    "stale-pages",
    "merge-candidates",
    "dead-citations",
    "cache-gc",
    "report-write",
    "last-report",
    "run",
    "status",
    "config",
}


class _MockMcp:
    """Minimal FastMCP shim capturing tool registrations for inspection."""

    def __init__(self) -> None:
        self.registered: list[tuple[str, dict]] = []

    def tool(self, *, name: str, annotations: dict):
        captured = self.registered

        def decorator(fn):
            captured.append((name, annotations))
            return fn

        return decorator


def _identity_interceptor(fn):
    return fn


class _MetricsStub:
    def __init__(self) -> None:
        self.tracked: list[str] = []

    def track_tool(self, name: str, *, skill: str | None = None) -> None:
        self.tracked.append(name)


def test_register_tools_exposes_all_nine_dream_tools():
    mcp = _MockMcp()
    mod.register_tools(mcp, _identity_interceptor, _MetricsStub())
    names = {entry[0] for entry in mcp.registered}
    assert names == EXPECTED_TOOLS


def _read_only_hint(annotation) -> bool:
    """tool_annotations() may return a dict (CLI fallback) or a FastMCP
    ``ToolAnnotations`` dataclass (when the real ``src.mcp.augur_shared``
    package is importable). Read the field through either shape."""
    if isinstance(annotation, dict):
        return bool(annotation.get("readOnlyHint"))
    return bool(getattr(annotation, "readOnlyHint", False))


def test_read_only_vs_write_annotations_match_intent():
    mcp = _MockMcp()
    mod.register_tools(mcp, _identity_interceptor, _MetricsStub())
    by_name = {name: ann for name, ann in mcp.registered}
    # Aggregators + status/config/last-report are read-only
    for read_tool in (
        "dream-orphans",
        "dream-stale-pages",
        "dream-merge-candidates",
        "dream-dead-citations",
        "dream-last-report",
        "dream-status",
        "dream-config",
    ):
        assert _read_only_hint(by_name[read_tool]) is True
    # report-write + cache-gc mutate the filesystem
    for write_tool in ("dream-report-write", "dream-cache-gc"):
        assert _read_only_hint(by_name[write_tool]) is False


def test_register_subcommands_exposes_aug_dream_verbs():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="cmd")
    mod.register_subcommands(subparsers)

    for verb in EXPECTED_VERBS:
        # Each verb should parse without error
        args = parser.parse_args(["dream", verb])
        assert args.cmd == "dream"
        assert args.dream_verb == verb


def test_aug_dream_with_no_verb_lists_options(capsys):
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="cmd")
    mod.register_subcommands(subparsers)
    args = parser.parse_args(["dream"])
    # The CLI runner should bail with a no-verb message and exit code 2.
    exit_code = args.func(args, [])
    assert exit_code == 2
    out = capsys.readouterr().out
    assert "verbs" in out


def test_aug_dream_orphans_invokes_underlying_aggregator(
    fixture_vault: Path,
    fixture_graph_cache: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys,
):
    """`aug dream orphans` should resolve vault + cache via path helpers and
    call dream_orphans, printing JSON."""
    # Force the CLI runner to use our fixture roots instead of get_vault_dir() /
    # get_cache_dir() — the runner reads these via the path-helper functions.
    monkeypatch.setattr(mod, "_resolve_vault_root", lambda: fixture_vault)
    monkeypatch.setattr(mod, "_resolve_cache_root", lambda: fixture_graph_cache)

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="cmd")
    mod.register_subcommands(subparsers)
    args = parser.parse_args(["dream", "orphans"])
    exit_code = args.func(args, [])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "wiki-orphan" in out


def test_aug_dream_run_invokes_ledger_backed_runner(monkeypatch, tmp_path: Path, capsys):
    calls = []

    def fake_dream_run(**kwargs):
        calls.append(kwargs)
        return {"count": kwargs["iterations"], "runs": [{"job_id": "dream-1"}]}

    monkeypatch.setitem(sys.modules, "dream_run", SimpleNamespace(dream_run=fake_dream_run))
    monkeypatch.setattr(mod, "_resolve_vault_root", lambda: tmp_path / "vault")
    monkeypatch.setattr(mod, "_resolve_cache_root", lambda: tmp_path / "cache")
    monkeypatch.setattr(mod, "_resolve_report_output_root", lambda: tmp_path / "reports")

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="cmd")
    mod.register_subcommands(subparsers)
    args = parser.parse_args(["dream", "run", "--iterations", "2", "--cache-gc-dry-run"])

    exit_code = args.func(args, [])

    assert exit_code == 0
    assert calls[0]["iterations"] == 2
    assert calls[0]["cache_gc_dry_run"] is True
    out = capsys.readouterr().out
    assert '"count": 2' in out
    assert "/a-loops run dream" in out


def test_aug_dream_status_invokes_unified_payload_helper(monkeypatch, capsys):
    calls = []

    def fake_status_payload(*, history_limit: int):
        calls.append(history_limit)
        return {"latest": {"job_id": "dream-1"}, "history": [{"job_id": "dream-1"}]}

    monkeypatch.setattr(mod, "_dream_status_payload", fake_status_payload)

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="cmd")
    mod.register_subcommands(subparsers)
    args = parser.parse_args(["dream", "status", "--history-limit", "2"])

    exit_code = args.func(args, [])

    assert exit_code == 0
    assert calls == [2]
    assert '"dream-1"' in capsys.readouterr().out
