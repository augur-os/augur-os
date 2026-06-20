"""Tests for optimizer/judge.py — injected accuracy scoring."""
import importlib.util
import sys
from pathlib import Path

OPT = Path(__file__).resolve().parents[2] / "scripts" / "optimizer"
sys.path.insert(0, str(OPT))


def _load(name):
    spec = importlib.util.spec_from_file_location(name, OPT / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


types_opt = _load("types_opt")
judge = _load("judge")


def test_score_accuracy_uses_injected_judge():
    case = types_opt.ReplayCase(inputs={"q": "x"}, prior_output="gold")
    rr = types_opt.RunResult(output="cand", wall_ms=1, tokens=1, llm_calls=1)
    assert judge.score_accuracy(case, rr, judge_fn=lambda p: 0.73) == 0.73


def test_score_accuracy_zero_when_run_failed():
    case = types_opt.ReplayCase(inputs={})
    rr = types_opt.RunResult(output="", wall_ms=1, tokens=0, llm_calls=0, ok=False, error="x")
    assert judge.score_accuracy(case, rr, judge_fn=lambda p: 1.0) == 0.0


def test_score_accuracy_clamps_and_handles_bad_judge():
    case = types_opt.ReplayCase(inputs={}, prior_output="g")
    rr = types_opt.RunResult(output="c", wall_ms=1, tokens=1, llm_calls=1)
    assert judge.score_accuracy(case, rr, judge_fn=lambda p: 5.0) == 1.0
    assert judge.score_accuracy(case, rr, judge_fn=lambda p: (_ for _ in ()).throw(ValueError())) == 0.0
