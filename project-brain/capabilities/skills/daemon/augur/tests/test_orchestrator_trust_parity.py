"""Parity tests for the extracted routine orchestrator trust ledger."""
from __future__ import annotations

import importlib.util
import importlib
import json
import os
import subprocess
import sys
import types
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable


PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
SHARED_CAPABILITIES_DIR = PROJECT_ROOT / "project-brain" / "capabilities"
DAEMON_SCRIPTS_DIR = SHARED_CAPABILITIES_DIR / "skills" / "daemon" / "scripts"
ADAPTIVE_DIR = DAEMON_SCRIPTS_DIR / "adaptive"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


ROUTINE_TRUST_PATH = (
    PROJECT_ROOT
    / "project-brain"
    / "capabilities"
    / "skills"
    / "daemon"
    / "scripts"
    / "routine_orchestrator"
    / "trust.py"
)


def _load_head_legacy_module(tmp_path: Path):
    result = subprocess.run(
        [
            "git",
            "show",
            "HEAD:project-brain/capabilities/skills/daemon/scripts/adaptive/trust_ledger.py",
        ],
        cwd=PROJECT_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    package_name = f"_legacy_adaptive_{abs(hash(str(tmp_path)))}"
    package_dir = tmp_path / package_name
    package_dir.mkdir()
    (package_dir / "__init__.py").write_text("", encoding="utf-8")
    legacy_path = package_dir / "trust_ledger.py"
    legacy_path.write_text(result.stdout, encoding="utf-8")

    package = types.ModuleType(package_name)
    package.__path__ = [str(package_dir), str(ADAPTIVE_DIR)]  # type: ignore[attr-defined]
    sys.modules[package_name] = package

    spec = importlib.util.spec_from_file_location(
        f"{package_name}.trust_ledger",
        legacy_path,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_routine_trust_module():
    spec = importlib.util.spec_from_file_location(
        "routine_orchestrator_trust_under_test",
        ROUTINE_TRUST_PATH,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _config() -> dict[str, Any]:
    return {
        "loops": {
            "modern-loop": {
                "enabled": True,
                "trigger": "nightly",
                "budget": 12,
                "budget_growth_rate": 2,
                "categories": {
                    "scan": {"enabled": True, "trust": 0.0, "tier": 0},
                    "fix": {"enabled": True, "trust": 0.2, "tier": 1},
                    "expand": {"enabled": False, "trust": 0.0, "tier": 2},
                },
            },
        },
    }


def _state_json(ledger: Any) -> dict[str, Any]:
    loop_state = ledger.get_loop_state("modern-loop")
    return json.loads(json.dumps(asdict(loop_state), sort_keys=True))


def _assert_parity(
    tmp_path: Path,
    operation: Callable[[Any, str], list[str] | None],
) -> None:
    legacy = _load_head_legacy_module(tmp_path)
    routine_trust = _load_routine_trust_module()
    legacy_dir = tmp_path / "legacy"
    routine_dir = tmp_path / "routine"

    legacy_ledger = legacy.TrustLedger(_config(), state_dir=legacy_dir)
    routine_ledger = routine_trust.TrustLedger(_config(), state_dir=routine_dir)

    legacy_notifications = operation(legacy_ledger, "modern-loop")
    routine_notifications = operation(routine_ledger, "modern-loop")

    assert routine_notifications == legacy_notifications
    assert _state_json(routine_ledger) == _state_json(legacy_ledger)
    assert (
        json.loads((routine_dir / "trust_state.json").read_text(encoding="utf-8"))
        == json.loads((legacy_dir / "trust_state.json").read_text(encoding="utf-8"))
    )


def test_success_transition_matches_legacy(tmp_path: Path) -> None:
    def operation(ledger: Any, loop: str) -> list[str]:
        return ledger.record_success(loop, "scan")

    _assert_parity(tmp_path, operation)


def test_failure_transition_matches_legacy(tmp_path: Path) -> None:
    def operation(ledger: Any, loop: str) -> list[str]:
        ledger.record_success(loop, "fix")
        return ledger.record_failure(loop, "fix")

    _assert_parity(tmp_path, operation)


def test_consecutive_success_difficulty_and_budget_match_legacy(tmp_path: Path) -> None:
    def operation(ledger: Any, loop: str) -> list[str]:
        notifications: list[str] = []
        for _ in range(12):
            notifications.extend(ledger.record_success(loop, "scan"))
        return notifications

    _assert_parity(tmp_path, operation)


def test_consecutive_failure_disable_matches_legacy(tmp_path: Path) -> None:
    from skills.daemon.scripts.adaptive.trust_ledger import CONSECUTIVE_FAILURES_TO_DISABLE

    def operation(ledger: Any, loop: str) -> list[str]:
        notifications: list[str] = []
        for _ in range(CONSECUTIVE_FAILURES_TO_DISABLE):
            notifications.extend(ledger.record_failure(loop, "fix"))
        return notifications

    _assert_parity(tmp_path, operation)


def test_clean_scan_trust_and_saturation_match_legacy(tmp_path: Path) -> None:
    from skills.daemon.scripts.adaptive.trust_ledger import CLEAN_SCAN_SATURATION

    def operation(ledger: Any, loop: str) -> list[str]:
        notifications: list[str] = []
        for _ in range(CLEAN_SCAN_SATURATION + 1):
            notifications.extend(ledger.record_clean_scan(loop, min_difficulty=0))
        return notifications

    _assert_parity(tmp_path, operation)


def test_legacy_imports_match_extracted_public_surface() -> None:
    from skills.daemon.scripts.adaptive import trust_ledger as legacy

    routine_trust = importlib.import_module("skills.daemon.scripts.routine_orchestrator.trust")

    assert legacy.TrustLedger is routine_trust.TrustLedger
    assert legacy.CategoryState is routine_trust.CategoryState
    assert legacy.LoopState is routine_trust.LoopState
    assert legacy.PROMOTION_THRESHOLD == routine_trust.PROMOTION_THRESHOLD
    assert legacy.CLEAN_SCAN_TRUST_INCREMENT == routine_trust.CLEAN_SCAN_TRUST_INCREMENT


def _assert_namespace_identity(
    pythonpath: Path,
    ledger_module: str,
    state_module: str,
    routine_module: str,
) -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(pythonpath)
    code = f"""
import importlib
ledger = importlib.import_module({ledger_module!r})
state = importlib.import_module({state_module!r})
routine = importlib.import_module({routine_module!r})
assert ledger.CategoryState is state.CategoryState
assert routine.CategoryState is state.CategoryState
assert ledger.LoopState is state.LoopState
assert routine.LoopState is state.LoopState
"""
    subprocess.run([sys.executable, "-c", code], check=True, env=env)


def test_top_level_adaptive_shim_preserves_state_class_identity() -> None:
    _assert_namespace_identity(
        DAEMON_SCRIPTS_DIR,
        "adaptive.trust_ledger",
        "adaptive.trust_state",
        "routine_orchestrator.trust",
    )


def test_package_adaptive_shim_preserves_state_class_identity() -> None:
    _assert_namespace_identity(
        SHARED_CAPABILITIES_DIR,
        "skills.daemon.scripts.adaptive.trust_ledger",
        "skills.daemon.scripts.adaptive.trust_state",
        "skills.daemon.scripts.routine_orchestrator.trust",
    )
