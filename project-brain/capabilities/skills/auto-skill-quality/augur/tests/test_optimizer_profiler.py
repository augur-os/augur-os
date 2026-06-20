"""Tests for optimizer/profiler.py — timed run wrapper."""
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
profiler = _load("profiler")


def test_run_case_times_and_wraps():
    def fake_run(inputs):
        return ("answer for " + inputs["q"], 42, 1)

    r = profiler.run_case(types_opt.ReplayCase(inputs={"q": "x"}), run_fn=fake_run)
    assert r.ok and r.output == "answer for x" and r.tokens == 42 and r.wall_ms >= 0


def test_run_case_never_raises_on_adapter_error():
    def boom(inputs):
        raise RuntimeError("nope")

    r = profiler.run_case(types_opt.ReplayCase(inputs={}), run_fn=boom)
    assert r.ok is False and "nope" in (r.error or "")
