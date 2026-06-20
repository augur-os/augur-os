import importlib.util, sys
from pathlib import Path
OPT = Path(__file__).resolve().parents[2] / "scripts" / "optimizer"
sys.path.insert(0, str(OPT))
spec = importlib.util.spec_from_file_location("types_opt", OPT / "types_opt.py")
types_opt = importlib.util.module_from_spec(spec); spec.loader.exec_module(types_opt)

def test_replay_case_defaults():
    c = types_opt.ReplayCase(inputs={"q": "x"})
    assert c.prior_output is None and c.source == "unknown"

def test_run_result_ok_default_true():
    r = types_opt.RunResult(output="hi", wall_ms=12.0, tokens=5, llm_calls=1)
    assert r.ok is True and r.error is None
