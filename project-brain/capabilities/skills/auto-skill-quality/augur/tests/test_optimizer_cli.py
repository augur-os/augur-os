"""Tests for optimize_cli.py — baseline/evaluate git-wired subcommands."""
import importlib.util, sys, json as _j
from pathlib import Path

OPT = Path(__file__).resolve().parents[2] / "scripts" / "optimizer"
sys.path.insert(0, str(OPT))

# Load optimize_ops first (dependency of optimize_cli)
_spec_ops = importlib.util.spec_from_file_location("optimize_ops", OPT / "optimize_ops.py")
optimize_ops = importlib.util.module_from_spec(_spec_ops)
sys.modules["optimize_ops"] = optimize_ops
_spec_ops.loader.exec_module(optimize_ops)

# Load optimize_cli
_spec_cli = importlib.util.spec_from_file_location("optimize_cli", OPT / "optimize_cli.py")
optimize_cli = importlib.util.module_from_spec(_spec_cli)
sys.modules["optimize_cli"] = optimize_cli
_spec_cli.loader.exec_module(optimize_cli)


def test_cli_baseline_then_evaluate_accepts_better(tmp_path, monkeypatch):
    monkeypatch.setattr(optimize_cli.optimize_ops, "_runtime_dir", lambda: tmp_path)
    commits, reverts = [], []
    monkeypatch.setattr(optimize_cli, "_git_commit", lambda m: commits.append(m))
    monkeypatch.setattr(optimize_cli, "_git_revert", lambda: reverts.append(1))
    out = optimize_cli.main(["baseline", "--skill", "demo", "--combined", "0.5", "--n-cases", "6"])
    run_id = _j.loads(out)["run_id"]
    r1 = _j.loads(optimize_cli.main(["evaluate", "--run", run_id, "--combined", "0.7", "--tests-pass", "1"]))
    r2 = _j.loads(optimize_cli.main(["evaluate", "--run", run_id, "--combined", "0.6", "--tests-pass", "1"]))
    assert r1["accepted"] is True and len(commits) == 1
    assert r2["accepted"] is False and len(reverts) == 1


def test_cli_evaluate_reverts_on_test_fail(tmp_path, monkeypatch):
    monkeypatch.setattr(optimize_cli.optimize_ops, "_runtime_dir", lambda: tmp_path)
    reverts = []
    monkeypatch.setattr(optimize_cli, "_git_commit", lambda m: None)
    monkeypatch.setattr(optimize_cli, "_git_revert", lambda: reverts.append(1))
    run_id = _j.loads(optimize_cli.main(["baseline", "--skill", "d", "--combined", "0.5", "--n-cases", "2"]))["run_id"]
    r = _j.loads(optimize_cli.main(["evaluate", "--run", run_id, "--combined", "0.9", "--tests-pass", "0"]))
    assert r["accepted"] is False and r["reason"] == "tests-failed" and len(reverts) == 1


def test_cli_status_subcommand(tmp_path, monkeypatch):
    monkeypatch.setattr(optimize_cli.optimize_ops, "_runtime_dir", lambda: tmp_path)
    monkeypatch.setattr(optimize_cli, "_git_commit", lambda m: None)
    monkeypatch.setattr(optimize_cli, "_git_revert", lambda: None)
    run_id = _j.loads(optimize_cli.main(["baseline", "--skill", "s", "--combined", "0.5", "--n-cases", "3"]))["run_id"]
    status = _j.loads(optimize_cli.main(["status", "--run", run_id]))
    assert status["verdict"] == "continue"
    assert status["baseline_combined"] == 0.5


def test_cli_report_subcommand(tmp_path, monkeypatch):
    monkeypatch.setattr(optimize_cli.optimize_ops, "_runtime_dir", lambda: tmp_path)
    monkeypatch.setattr(optimize_cli, "_git_commit", lambda m: None)
    monkeypatch.setattr(optimize_cli, "_git_revert", lambda: None)
    run_id = _j.loads(optimize_cli.main(["baseline", "--skill", "rpt", "--combined", "0.4", "--n-cases", "2"]))["run_id"]
    optimize_cli.main(["evaluate", "--run", run_id, "--combined", "0.8", "--tests-pass", "1"])
    report = optimize_cli.main(["report", "--run", run_id])
    assert "rpt" in report and "0.4000" in report and "0.8000" in report
