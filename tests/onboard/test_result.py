from pathlib import Path

from src.lib.onboard.result import OnboardContext, StepResult


def test_stepresult_fields_and_ok_helper():
    r = StepResult.ok("done", {"k": 1})
    assert r.status == "ok" and r.message == "done" and r.details == {"k": 1}
    assert r.is_ok is True


def test_stepresult_guide_and_fail_helpers():
    g = StepResult.guide("install uv")
    f = StepResult.fail("boom", {"err": "x"})
    assert g.status == "guide" and g.is_ok is False
    assert f.status == "fail" and f.details == {"err": "x"}


def test_context_defaults(tmp_path: Path):
    ctx = OnboardContext(repo_root=tmp_path)
    assert ctx.repo_root == tmp_path
    assert ctx.non_interactive is False
