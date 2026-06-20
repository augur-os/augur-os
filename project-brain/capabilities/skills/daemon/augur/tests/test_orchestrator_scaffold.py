"""Smoke tests for the ADR-755 routine orchestrator scaffold."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
DAEMON_DIR = TESTS_DIR.parents[1]
ORCHESTRATOR_PATH = DAEMON_DIR / "scripts" / "routine_orchestrator" / "__init__.py"


def _load_module(module_name: str, module_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _load_orchestrator_module():
    return _load_module("routine_orchestrator", ORCHESTRATOR_PATH)


def _load_fixture_helpers():
    return _load_module("orchestrator_fixtures", TESTS_DIR / "_fixtures.py")


def _load_engine_quality():
    return _load_module(
        "engine_quality",
        DAEMON_DIR / "scripts" / "adaptive" / "engine_quality.py",
    )


def test_routine_orchestrator_exports_pending_entrypoints() -> None:
    orchestrator = _load_orchestrator_module()

    assert hasattr(orchestrator, "orchestrate_run")
    assert hasattr(orchestrator, "scan_only")
    assert callable(orchestrator.orchestrate_run)
    assert callable(orchestrator.scan_only)


def test_routine_orchestrator_loads_independent_of_cwd(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    orchestrator = _load_orchestrator_module()

    assert hasattr(orchestrator, "orchestrate_run")


def test_fixture_builders_create_toy_loop_and_runtime_files(tmp_path) -> None:
    fixtures = _load_fixture_helpers()

    loop = fixtures.build_toy_loop()

    assert loop["name"] == "toy-loop"
    assert loop["fixture_dir"] == TESTS_DIR / "fixtures" / "toy_loop"
    assert loop["modules"] == ["auto_mech", "auto_semantic", "auto_struct"]
    loop_config = loop["config"]["loops"]["toy-loop"]
    assert loop_config["trigger"] == "manual"
    assert set(loop_config["categories"]) == {
        "auto-mech",
        "auto-semantic",
        "auto-struct",
    }
    for category in loop_config["categories"].values():
        assert Path(category["path"]).is_file()

    runtime_dir = fixtures.build_fixture_runtime_dir(tmp_path)
    assert runtime_dir == tmp_path / "runtime"
    assert (runtime_dir / "adaptive").is_dir()

    trust_state = fixtures.build_trust_state_file(tmp_path)
    assert trust_state == runtime_dir / "adaptive" / "trust_state.json"
    payload = json.loads(trust_state.read_text(encoding="utf-8"))
    assert set(payload["loops"]["toy-loop"]["categories"]) == {
        "auto-mech",
        "auto-semantic",
        "auto-struct",
    }


@pytest.mark.parametrize(
    ("module_name", "expected_name", "expected_band"),
    [
        ("auto_mech", "auto-mech", "mechanical"),
        ("auto_semantic", "auto-semantic", "local-semantic"),
        ("auto_struct", "auto-struct", "structural"),
    ],
)
def test_toy_modules_expose_ops_protocol_and_expected_classification(
    module_name: str,
    expected_name: str,
    expected_band: str,
) -> None:
    fixtures = _load_fixture_helpers()
    engine_quality = _load_engine_quality()
    module = _load_module(module_name, fixtures.TOY_LOOP_FIXTURE_DIR / f"{module_name}.py")

    assert module.name == expected_name
    assert callable(module.scan)
    assert callable(module.fix)

    scan_result = module.scan(None)
    assert scan_result.issues
    assert engine_quality.classify_finding_band(scan_result.issues[0]) == expected_band


def test_semantic_toy_module_exposes_llm_fix_sentinel() -> None:
    fixtures = _load_fixture_helpers()
    module = _load_module(
        "auto_semantic",
        fixtures.TOY_LOOP_FIXTURE_DIR / "auto_semantic.py",
    )

    assert callable(module.llm_fix)
    scan_result = module.scan(None)
    assert module.llm_fix(None, scan_result.issues) == {
        "kind": "llm-fix-request",
        "loop": "toy-loop",
        "category": "auto-semantic",
        "issue_count": 1,
    }
