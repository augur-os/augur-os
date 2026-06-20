import importlib.util, sys
from pathlib import Path
OPT = Path(__file__).resolve().parents[2] / "scripts" / "optimizer"
sys.path.insert(0, str(OPT))
spec = importlib.util.spec_from_file_location("optimize_ops", OPT / "optimize_ops.py")
optimize_ops = importlib.util.module_from_spec(spec); sys.modules["optimize_ops"] = optimize_ops; spec.loader.exec_module(optimize_ops)


def test_baseline_then_accept_better_then_reject_worse(tmp_path, monkeypatch):
    monkeypatch.setattr(optimize_ops, "_runtime_dir", lambda: tmp_path)
    cases = [{"inputs": {"i": i}} for i in range(6)]
    scores = iter([0.50, 0.62, 0.55])  # baseline, round1(better), round2(worse)
    measure = lambda *_a, **_k: next(scores)
    base = optimize_ops.optimize_baseline({"name": "demo"}, cases=cases, measure_fn=measure,
                                          weights={"lam": 0.2, "mu": 0.1})
    assert base["baseline_combined"] == 0.50 and base["n_val"] >= 1
    commits, reverts = [], []
    r1 = optimize_ops.optimize_evaluate(base["run_id"], measure_fn=measure, tests_fn=lambda: True,
                                        commit_fn=lambda m: commits.append(m), revert_fn=lambda: reverts.append(1))
    r2 = optimize_ops.optimize_evaluate(base["run_id"], measure_fn=measure, tests_fn=lambda: True,
                                        commit_fn=lambda m: commits.append(m), revert_fn=lambda: reverts.append(1))
    assert r1["accepted"] is True and len(commits) == 1
    assert r2["accepted"] is False and len(reverts) == 1

def test_evaluate_reverts_when_tests_fail(tmp_path, monkeypatch):
    monkeypatch.setattr(optimize_ops, "_runtime_dir", lambda: tmp_path)
    base = optimize_ops.optimize_baseline({"name": "demo"}, cases=[{"inputs": {}}],
                                          measure_fn=lambda *_a, **_k: 0.5, weights={"lam": 0.2, "mu": 0.1})
    reverts = []
    r = optimize_ops.optimize_evaluate(base["run_id"], measure_fn=lambda *_a, **_k: 0.9, tests_fn=lambda: False,
                                       commit_fn=lambda m: None, revert_fn=lambda: reverts.append(1))
    assert r["accepted"] is False and r["reason"] == "tests-failed" and len(reverts) == 1
