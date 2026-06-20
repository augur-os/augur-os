"""Accuracy in [0,1] for a case's run output. judge_fn is injected (LLM in production)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from types_opt import ReplayCase, RunResult

_RUBRIC = ("Score 0..1 how well CANDIDATE answers the task vs REFERENCE.\n"
           "TASK INPUTS:\n{inputs}\nREFERENCE:\n{ref}\nCANDIDATE:\n{cand}\nReturn only a float.")


def build_prompt(case: ReplayCase, rr: RunResult) -> str:
    return _RUBRIC.format(inputs=case.inputs, ref=case.prior_output or "(none)", cand=rr.output)


def score_accuracy(case: ReplayCase, rr: RunResult, *, judge_fn) -> float:
    if not rr.ok:
        return 0.0
    try:
        val = float(judge_fn(build_prompt(case, rr)))
    except Exception:
        return 0.0
    return max(0.0, min(1.0, val))
