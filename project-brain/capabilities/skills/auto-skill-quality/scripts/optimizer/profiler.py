"""Re-invoke a skill on a case and measure wall-time/tokens/llm-calls. Never raises."""
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from types_opt import ReplayCase, RunResult


def run_case(case: ReplayCase, *, run_fn) -> RunResult:
    """run_fn(inputs) -> (output:str, tokens:int, llm_calls:int). Resolved per skill type by the caller."""
    start = time.perf_counter()
    try:
        output, tokens, llm_calls = run_fn(case.inputs)
    except Exception as exc:
        return RunResult(output="", wall_ms=(time.perf_counter() - start) * 1000,
                         tokens=0, llm_calls=0, ok=False, error=str(exc)[:200])
    return RunResult(output=str(output), wall_ms=(time.perf_counter() - start) * 1000,
                     tokens=int(tokens), llm_calls=int(llm_calls), ok=True)
