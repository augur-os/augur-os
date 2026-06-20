"""Atomic optimize ops: baseline, evaluate (tests + strict-improvement accept/revert)."""
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import score
import run_ledger


def _runtime_dir():
    from src.config.paths import get_runtime_dir
    return Path(get_runtime_dir()) / "optimizer"


def optimize_baseline(skill, *, cases, measure_fn, weights, validation_frac=0.4, seed=13):
    train, validation = score.split_cases(cases, validation_frac=validation_frac, seed=seed)
    baseline = float(measure_fn(validation))
    run_id = f"{skill['name']}-{int(time.time() * 1000)}"
    run = {"run_id": run_id, "skill": skill["name"], "weights": weights,
           "baseline_combined": baseline, "best_combined": baseline,
           "n_train": len(train), "n_val": len(validation), "rounds": [], "status": "open"}
    run_ledger.save_run(_runtime_dir(), run)
    return {"run_id": run_id, "baseline_combined": baseline, "n_train": len(train), "n_val": len(validation)}


def optimize_evaluate(run_id, *, measure_fn, tests_fn, commit_fn, revert_fn):
    run = run_ledger.load_run(_runtime_dir(), run_id)
    if not tests_fn():
        revert_fn()
        run["rounds"].append({"combined": None, "accepted": False, "reason": "tests-failed"})
        run_ledger.save_run(_runtime_dir(), run)
        return {"accepted": False, "reason": "tests-failed"}
    new_combined = float(measure_fn(None))
    accepted = new_combined > run["best_combined"]
    if accepted:
        commit_fn(f"optimize: round {len(run['rounds']) + 1} ({run['best_combined']:.4f} -> {new_combined:.4f})")
        run["best_combined"] = new_combined
        reason = "improved"
    else:
        revert_fn()
        reason = "no-improvement"
    run["rounds"].append({"combined": new_combined, "accepted": accepted, "reason": reason})
    run_ledger.save_run(_runtime_dir(), run)
    return {"accepted": accepted, "reason": reason, "combined": new_combined, "best_combined": run["best_combined"]}


def optimize_status(run_id, *, stall_k=3):
    run = run_ledger.load_run(_runtime_dir(), run_id)
    rounds = run["rounds"]
    if rounds and rounds[-1]["accepted"]:
        verdict = "improved"
    elif len(rounds) >= stall_k and all(not r["accepted"] for r in rounds[-stall_k:]):
        verdict = "stalled"
    else:
        verdict = "continue"
    return {"verdict": verdict, "rounds": len(rounds),
            "baseline_combined": run["baseline_combined"], "best_combined": run["best_combined"]}


def optimize_report(run_id):
    run = run_ledger.load_run(_runtime_dir(), run_id)
    accepted = [r for r in run["rounds"] if r["accepted"]]
    delta = run["best_combined"] - run["baseline_combined"]
    lines = [f"# Optimize report — {run['skill']}",
             f"- baseline combined: {run['baseline_combined']:.4f}",
             f"- best combined: {run['best_combined']:.4f}",
             f"- delta: {delta:+.4f}",
             f"- rounds: {len(run['rounds'])} ({len(accepted)} accepted)"]
    for i, r in enumerate(run["rounds"], 1):
        verdict = "ACCEPT" if r["accepted"] else "reject"
        lines.append(f"  round {i}: {verdict} ({r['reason']}) combined={r.get('combined')}")
    return "\n".join(lines)
