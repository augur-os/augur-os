import importlib.util, sys
from pathlib import Path
OPT = Path(__file__).resolve().parents[2] / "scripts" / "optimizer"
spec = importlib.util.spec_from_file_location("score", OPT / "score.py")
score = importlib.util.module_from_spec(spec); sys.modules["score"] = score; spec.loader.exec_module(score)


def test_combined_rewards_fewer_tokens_same_accuracy():
    base = score.combined(0.8, 1000, 1000.0, lam=0.2, mu=0.1, baseline_tokens=1000, baseline_ms=1000.0)
    cheaper = score.combined(0.8, 500, 1000.0, lam=0.2, mu=0.1, baseline_tokens=1000, baseline_ms=1000.0)
    assert cheaper > base

def test_combined_rewards_accuracy_over_speed_at_low_weights():
    fast_worse = score.combined(0.6, 100, 100.0, lam=0.05, mu=0.05, baseline_tokens=1000, baseline_ms=1000.0)
    slow_better = score.combined(0.9, 1000, 1000.0, lam=0.05, mu=0.05, baseline_tokens=1000, baseline_ms=1000.0)
    assert slow_better > fast_worse

def test_split_is_deterministic_and_disjoint():
    cases = list(range(10))
    a1, b1 = score.split_cases(cases, validation_frac=0.4, seed=7)
    a2, b2 = score.split_cases(cases, validation_frac=0.4, seed=7)
    assert (a1, b1) == (a2, b2)
    assert set(a1).isdisjoint(b1) and len(b1) == 4 and len(a1) + len(b1) == 10

def test_split_zero_division_safe_on_empty():
    assert score.split_cases([], validation_frac=0.4, seed=1) == ([], [])
