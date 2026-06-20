import importlib.util, sys
from pathlib import Path
OPT = Path(__file__).resolve().parents[2] / "scripts" / "optimizer"
sys.path.insert(0, str(OPT))
spec = importlib.util.spec_from_file_location("optimize_ops", OPT / "optimize_ops.py")
optimize_ops = importlib.util.module_from_spec(spec); sys.modules["optimize_ops"] = optimize_ops; spec.loader.exec_module(optimize_ops)


def test_status_stalled_after_k_rejects(tmp_path, monkeypatch):
    monkeypatch.setattr(optimize_ops, "_runtime_dir", lambda: tmp_path)
    base = optimize_ops.optimize_baseline({"name": "d"}, cases=[{"inputs": {}}],
                                          measure_fn=lambda *_a, **_k: 0.5, weights={"lam": 0.2, "mu": 0.1})
    for _ in range(3):
        optimize_ops.optimize_evaluate(base["run_id"], measure_fn=lambda *_a, **_k: 0.4, tests_fn=lambda: True,
                                       commit_fn=lambda m: None, revert_fn=lambda: None)
    assert optimize_ops.optimize_status(base["run_id"], stall_k=3)["verdict"] == "stalled"

def test_status_improved_when_last_round_accepted(tmp_path, monkeypatch):
    monkeypatch.setattr(optimize_ops, "_runtime_dir", lambda: tmp_path)
    base = optimize_ops.optimize_baseline({"name": "d"}, cases=[{"inputs": {}}],
                                          measure_fn=lambda *_a, **_k: 0.5, weights={"lam": 0.2, "mu": 0.1})
    optimize_ops.optimize_evaluate(base["run_id"], measure_fn=lambda *_a, **_k: 0.7, tests_fn=lambda: True,
                                   commit_fn=lambda m: None, revert_fn=lambda: None)
    assert optimize_ops.optimize_status(base["run_id"], stall_k=3)["verdict"] == "improved"

def test_report_contains_baseline_and_best(tmp_path, monkeypatch):
    monkeypatch.setattr(optimize_ops, "_runtime_dir", lambda: tmp_path)
    base = optimize_ops.optimize_baseline({"name": "demo"}, cases=[{"inputs": {}}],
                                          measure_fn=lambda *_a, **_k: 0.5, weights={"lam": 0.2, "mu": 0.1})
    optimize_ops.optimize_evaluate(base["run_id"], measure_fn=lambda *_a, **_k: 0.8, tests_fn=lambda: True,
                                   commit_fn=lambda m: None, revert_fn=lambda: None)
    rep = optimize_ops.optimize_report(base["run_id"])
    assert "demo" in rep and "0.5000" in rep and "0.8000" in rep and "+0.3000" in rep
