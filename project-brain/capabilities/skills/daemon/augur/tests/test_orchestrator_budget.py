"""Tests for ADR-755 per-subagent budget enforcement."""
from __future__ import annotations

import importlib.util
from pathlib import Path


TESTS_DIR = Path(__file__).resolve().parent
DAEMON_DIR = TESTS_DIR.parents[1]
BUDGET_PATH = DAEMON_DIR / "scripts" / "routine_orchestrator" / "budget.py"


def _load_budget_module():
    spec = importlib.util.spec_from_file_location(
        "routine_orchestrator_budget",
        BUDGET_PATH,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_budget_default_max_turns_20() -> None:
    budget_mod = _load_budget_module()

    budget = budget_mod.Budget.default(loop="testing", config={})

    assert budget.max_turns == 20
    assert budget.consumed_turns == 0


def test_budget_per_loop_override_from_config() -> None:
    budget_mod = _load_budget_module()
    config = {
        "engine": {"llm_escalation": {"max_turns": 20}},
        "loops": {"testing": {"subagent_max_turns": 30}},
    }

    budget = budget_mod.Budget.default(loop="testing", config=config)

    assert budget.max_turns == 30


def test_budget_reads_project_config(tmp_path) -> None:
    budget_mod = _load_budget_module()
    config_dir = tmp_path / "config" / "system"
    config_dir.mkdir(parents=True)
    (config_dir / "adaptive_loops.yaml").write_text(
        "\n".join(
            [
                "engine:",
                "  llm_escalation:",
                "    max_turns: 12",
                "    timeout_s: 45",
                "loops:",
                "  testing:",
                "    subagent_max_turns: 14",
            ]
        ),
        encoding="utf-8",
    )

    budget = budget_mod.Budget.default(loop="testing", project_root=tmp_path)

    assert budget.max_turns == 14
    assert budget.soft_timeout_s == 45


def test_budget_soft_timeout_default_600s() -> None:
    budget_mod = _load_budget_module()

    budget = budget_mod.Budget.default(loop="testing", config={})

    assert budget.soft_timeout_s == 600


def test_consume_increments_consumed_turns() -> None:
    budget_mod = _load_budget_module()
    budget = budget_mod.Budget.default(loop="testing", config={})

    budget.consume()
    budget.consume(turns=2)

    assert budget.consumed_turns == 3


def test_check_remaining_returns_false_when_exhausted() -> None:
    budget_mod = _load_budget_module()
    budget = budget_mod.Budget(max_turns=3, soft_timeout_s=600, start_time=100.0)

    budget.consume(turns=3)

    assert budget.check_remaining(now=101.0) is False


def test_check_remaining_returns_false_when_soft_timeout_elapsed() -> None:
    budget_mod = _load_budget_module()
    budget = budget_mod.Budget(max_turns=20, soft_timeout_s=10, start_time=100.0)

    assert budget.check_remaining(now=109.99) is True
    assert budget.check_remaining(now=110.0) is False
    assert budget.check_remaining(now=111.0) is False


def test_budget_3x_multiplier_for_llm_dispatch_preserved() -> None:
    budget_mod = _load_budget_module()
    config = {
        "engine": {
            "llm_escalation": {
                "max_turns": 10,
                "timeout_s": 60,
                "budget_multiplier": 3,
            }
        }
    }

    mechanical = budget_mod.Budget.default(
        loop="testing",
        kind="mechanical",
        config=config,
    )
    llm = budget_mod.Budget.default(loop="testing", kind="llm", config=config)

    assert mechanical.max_turns == 10
    assert llm.max_turns == 30
    assert mechanical.soft_timeout_s == 60
    assert llm.soft_timeout_s == 60
