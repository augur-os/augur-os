"""Tests for ADR-755 deterministic orchestrator scan dispatch."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

from src.lib.ops_protocol import SessionContext

TESTS_DIR = Path(__file__).resolve().parent
DAEMON_DIR = TESTS_DIR.parents[1]
SCAN_PHASE_PATH = DAEMON_DIR / "scripts" / "routine_orchestrator" / "scan_phase.py"


def _load_module(module_name: str, module_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_scan_phase():
    return _load_module("routine_orchestrator_scan_phase", SCAN_PHASE_PATH)


def _load_fixture_helpers():
    return _load_module("orchestrator_fixtures_scan_phase", TESTS_DIR / "_fixtures.py")


def _load_toy_commands():
    fixtures = _load_fixture_helpers()
    return [
        _load_module(module_name, fixtures.TOY_LOOP_FIXTURE_DIR / f"{module_name}.py")
        for module_name in fixtures.build_toy_loop()["modules"]
    ]


def test_scan_phase_runs_all_commands_in_loop(tmp_path) -> None:
    scan_phase = _load_scan_phase()
    fixtures = _load_fixture_helpers()

    findings = scan_phase.scan_loop(
        fixtures.TOY_LOOP_NAME,
        project_root=tmp_path,
        commands=_load_toy_commands(),
    )

    assert [finding["auto_command"] for finding in findings] == [
        "auto-mech",
        "auto-semantic",
        "auto-struct",
    ]
    assert {finding["loop"] for finding in findings} == {fixtures.TOY_LOOP_NAME}
    assert [finding["path"] for finding in findings] == [
        "fixtures/toy_loop/auto_mech.py",
        "fixtures/toy_loop/auto_semantic.py",
        "fixtures/toy_loop/auto_struct.py",
    ]


def test_scan_phase_continues_on_command_failure(tmp_path) -> None:
    scan_phase = _load_scan_phase()
    engine_quality = _load_module(
        "adaptive_engine_quality_for_scan_phase",
        DAEMON_DIR / "scripts" / "adaptive" / "engine_quality.py",
    )
    fixtures = _load_fixture_helpers()
    toy_commands = _load_toy_commands()

    def fail_scan(ctx):
        raise RuntimeError("deterministic fixture crash")

    failing_entry = SimpleNamespace(
        name="auto-fail",
        module=SimpleNamespace(scan=fail_scan),
        loop_name=fixtures.TOY_LOOP_NAME,
        config={},
    )

    findings = scan_phase.scan_loop(
        fixtures.TOY_LOOP_NAME,
        project_root=tmp_path,
        commands=[toy_commands[0], failing_entry, toy_commands[1]],
    )

    assert [finding["auto_command"] for finding in findings] == [
        "auto-mech",
        "auto-fail",
        "auto-semantic",
    ]
    error_finding = findings[1]
    assert error_finding["kind"] == "scan-error"
    assert error_finding["band"] == "mechanical"
    assert error_finding["finding_band"] == "mechanical"
    assert error_finding["loop"] == fixtures.TOY_LOOP_NAME
    assert error_finding["error_message"] == "deterministic fixture crash"
    assert engine_quality.classify_finding_band(error_finding) == engine_quality.MECHANICAL


def test_scan_phase_no_session_required(tmp_path) -> None:
    scan_phase = _load_scan_phase()
    fixtures = _load_fixture_helpers()

    findings = scan_phase.scan_loop(
        fixtures.TOY_LOOP_NAME,
        project_root=tmp_path,
        commands=_load_toy_commands(),
        session=SessionContext(has_llm=False),
    )

    assert len(findings) == 3
    assert {finding["auto_command"] for finding in findings} == {
        "auto-mech",
        "auto-semantic",
        "auto-struct",
    }


def test_discover_loop_commands_preserves_adaptive_tier_order(tmp_path) -> None:
    scan_phase = _load_scan_phase()
    fixtures = _load_fixture_helpers()

    def scan(ctx):
        return {"issues": []}

    high_tier = SimpleNamespace(
        name="alpha-high",
        module=SimpleNamespace(scan=scan),
        loop_name=fixtures.TOY_LOOP_NAME,
        config={},
        tier=2,
    )
    low_tier = SimpleNamespace(
        name="zeta-low",
        module=SimpleNamespace(scan=scan),
        loop_name=fixtures.TOY_LOOP_NAME,
        config={},
        tier=0,
    )

    fake_discovery = SimpleNamespace(
        discover_auto_commands=lambda root: {
            "alpha-high": high_tier,
            "zeta-low": low_tier,
        },
        group_by_loop=lambda registry: {fixtures.TOY_LOOP_NAME: [low_tier, high_tier]},
    )
    scan_phase._load_adaptive_discovery = lambda: fake_discovery

    entries = scan_phase.discover_loop_commands(fixtures.TOY_LOOP_NAME, tmp_path)

    assert [entry.name for entry in entries] == ["zeta-low", "alpha-high"]
    assert [entry.tier for entry in entries] == [0, 2]
