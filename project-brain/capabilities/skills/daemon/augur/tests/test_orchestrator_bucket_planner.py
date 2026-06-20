"""Tests for ADR-755 routine orchestrator bucket planning."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


TESTS_DIR = Path(__file__).resolve().parent
DAEMON_DIR = TESTS_DIR.parents[1]
BUCKET_PLANNER_PATH = DAEMON_DIR / "scripts" / "routine_orchestrator" / "bucket_planner.py"


def _load_module(module_name: str, module_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_bucket_planner():
    return _load_module("routine_orchestrator_bucket_planner", BUCKET_PLANNER_PATH)


def _finding(
    *,
    auto_command: str,
    path: str,
    band: str = "local-semantic",
    detail: str | None = None,
) -> dict:
    return {
        "auto_command": auto_command,
        "path": path,
        "finding_band": band,
        "detail": detail or f"{auto_command} finding for {path}",
    }


def test_buckets_group_by_command_and_file() -> None:
    bucket_planner = _load_bucket_planner()
    first = _finding(auto_command="auto-alpha", path="src/a.py", detail="first")
    second = _finding(auto_command="auto-alpha", path="src/a.py", detail="second")
    third = _finding(auto_command="auto-alpha", path="src/b.py")
    fourth = _finding(auto_command="auto-beta", path="src/a.py")

    plan = bucket_planner.plan_dispatch(
        [first, second, third, fourth],
        loop_name="testing",
    )

    assert isinstance(plan, bucket_planner.BucketPlan)
    assert [bucket.key for bucket in plan.buckets] == [
        ("auto-alpha", "src/a.py"),
        ("auto-alpha", "src/b.py"),
        ("auto-beta", "src/a.py"),
    ]
    assert [bucket.auto_command for bucket in plan.buckets] == [
        "auto-alpha",
        "auto-alpha",
        "auto-beta",
    ]
    assert [bucket.primary_file for bucket in plan.buckets] == [
        "src/a.py",
        "src/b.py",
        "src/a.py",
    ]
    assert plan.buckets[0].findings == [first, second]


def test_below_threshold_returns_single_dispatch_strategy() -> None:
    bucket_planner = _load_bucket_planner()
    findings = [
        _finding(auto_command=f"auto-{index}", path=f"src/{index}.py")
        for index in range(8)
    ]

    plan = bucket_planner.plan_dispatch(findings, loop_name="testing")

    assert plan.strategy == "inline-sequential"


def test_above_threshold_returns_fan_out_strategy() -> None:
    bucket_planner = _load_bucket_planner()
    findings = [
        _finding(auto_command=f"auto-{index}", path=f"src/{index}.py")
        for index in range(9)
    ]

    plan = bucket_planner.plan_dispatch(findings, loop_name="testing")

    assert plan.strategy == "parallel-fan-out"


def test_threshold_is_configurable_per_loop() -> None:
    bucket_planner = _load_bucket_planner()
    findings = [
        _finding(auto_command=f"auto-{index}", path=f"src/{index}.py")
        for index in range(3)
    ]
    config = {"loops": {"testing": {"fan_out_threshold": 2}}}

    plan = bucket_planner.plan_dispatch(findings, loop_name="testing", config=config)

    assert plan.fan_out_threshold == 2
    assert plan.strategy == "parallel-fan-out"


def test_threshold_can_be_read_from_project_config(tmp_path) -> None:
    bucket_planner = _load_bucket_planner()
    config_dir = tmp_path / "config" / "system"
    config_dir.mkdir(parents=True)
    (config_dir / "adaptive_loops.yaml").write_text(
        "loops:\n  testing:\n    fan_out_threshold: 1\n",
        encoding="utf-8",
    )

    plan = bucket_planner.plan_dispatch(
        [
            _finding(auto_command="auto-alpha", path="src/a.py"),
            _finding(auto_command="auto-beta", path="src/b.py"),
        ],
        loop_name="testing",
        project_root=tmp_path,
    )

    assert plan.fan_out_threshold == 1
    assert plan.strategy == "parallel-fan-out"


def test_structural_findings_never_bucketed() -> None:
    bucket_planner = _load_bucket_planner()
    structural = _finding(auto_command="auto-struct", path="src/design.py", band="structural")
    inferred_structural = {
        "auto_command": "auto-inferred-struct",
        "path": "src/ownership.py",
        "ownership_change": True,
    }
    semantic = _finding(auto_command="auto-semantic", path="src/value.py")

    plan = bucket_planner.plan_dispatch(
        [structural, inferred_structural, semantic],
        loop_name="testing",
    )

    assert [bucket.key for bucket in plan.buckets] == [("auto-semantic", "src/value.py")]
    assert plan.design_gate_findings == [structural, inferred_structural]


def test_maintenance_and_generated_artifact_findings_never_bucket() -> None:
    bucket_planner = _load_bucket_planner()
    maintenance = {
        "auto_command": "auto-maintenance",
        "path": "src/index.json",
        "kind": "maintenance",
        "detail": "Rebuild generated index",
    }
    generated_artifact = {
        "auto_command": "auto-generated",
        "path": "src/generated.ts",
        "kind": "actionable",
        "root_cause_type": "generated_artifact",
        "detail": "Regenerate generated file",
    }
    semantic = _finding(auto_command="auto-semantic", path="src/value.py")

    plan = bucket_planner.plan_dispatch(
        [maintenance, generated_artifact, semantic],
        loop_name="testing",
    )

    assert [bucket.key for bucket in plan.buckets] == [("auto-semantic", "src/value.py")]
    assert plan.design_gate_findings == []
