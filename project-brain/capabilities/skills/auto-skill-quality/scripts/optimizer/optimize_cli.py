"""Optimizer CLI: baseline, evaluate (git-wired), status, report.
baseline/evaluate are driven by the skillify-optimize inline-session loop (ADR-804).
The AI client measures accuracy/tokens/time in-session and passes the combined score here;
this module owns only the deterministic persist + git accept/revert.
"""
import argparse, json, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import optimize_ops


# ---------------------------------------------------------------------------
# Git helpers — module-level so tests can monkeypatch them
# ---------------------------------------------------------------------------

def _git_commit(msg):
    subprocess.run(["git", "commit", "--no-verify", "-m", msg], check=True)


def _git_revert():
    subprocess.run(["git", "checkout", "--", "."], check=True)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv):
    p = argparse.ArgumentParser(prog="optimize")
    sub = p.add_subparsers(dest="cmd", required=True)

    # baseline
    b = sub.add_parser("baseline")
    b.add_argument("--skill", required=True)
    b.add_argument("--combined", type=float, required=True)
    b.add_argument("--n-cases", type=int, required=True)

    # evaluate
    e = sub.add_parser("evaluate")
    e.add_argument("--run", required=True)
    e.add_argument("--combined", type=float, required=True)
    e.add_argument("--tests-pass", type=int, choices=[0, 1], required=True)

    # status
    s = sub.add_parser("status")
    s.add_argument("--run", required=True)
    s.add_argument("--stall-k", type=int, default=3)

    # report
    r = sub.add_parser("report")
    r.add_argument("--run", required=True)

    args = p.parse_args(argv)

    if args.cmd == "baseline":
        combined = args.combined
        cases = [{} for _ in range(args.n_cases)]
        result = optimize_ops.optimize_baseline(
            {"name": args.skill},
            cases=cases,
            measure_fn=lambda *_a, **_k: combined,
            weights={"lam": 0.2, "mu": 0.1},
        )
        return json.dumps(result)

    if args.cmd == "evaluate":
        combined = args.combined
        tests_pass = bool(int(args.tests_pass))
        result = optimize_ops.optimize_evaluate(
            args.run,
            measure_fn=lambda *_a, **_k: combined,
            tests_fn=lambda: tests_pass,
            commit_fn=_git_commit,
            revert_fn=_git_revert,
        )
        return json.dumps(result)

    if args.cmd == "status":
        return json.dumps(optimize_ops.optimize_status(args.run, stall_k=args.stall_k))

    if args.cmd == "report":
        return optimize_ops.optimize_report(args.run)

    return ""


if __name__ == "__main__":
    print(main(sys.argv[1:]))
