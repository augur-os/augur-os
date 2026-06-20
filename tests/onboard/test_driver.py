from pathlib import Path

from src.lib.onboard.result import OnboardContext, StepResult
from src.lib.onboard import driver as d


def test_runs_all_steps_in_order_when_ok(tmp_path: Path):
    calls = []
    steps = [
        ("a", lambda ctx: (calls.append("a"), StepResult.ok("a"))[1]),
        ("b", lambda ctx: (calls.append("b"), StepResult.ok("b"))[1]),
    ]
    results = d.run_onboard(OnboardContext(repo_root=tmp_path), steps=steps)
    assert calls == ["a", "b"]
    assert all(r.is_ok for _, r in results)


def test_stops_on_guide(tmp_path: Path):
    calls = []
    steps = [
        ("a", lambda ctx: (calls.append("a"), StepResult.guide("install X"))[1]),
        ("b", lambda ctx: (calls.append("b"), StepResult.ok("b"))[1]),
    ]
    results = d.run_onboard(OnboardContext(repo_root=tmp_path), steps=steps)
    assert calls == ["a"]  # b never ran
    assert results[-1][1].status == "guide"


def test_default_steps_registry_order():
    names = [name for name, _ in d.STEPS]
    assert names == ["detect_prereqs", "sync_deps", "build_dashboard", "wire_mcp", "seed_brain_and_vault", "verify"]


def test_non_interactive_guide_is_hard_failure(tmp_path: Path, capsys):
    steps = [("detect_prereqs", lambda ctx: StepResult.guide("install uv"))]
    ctx = OnboardContext(repo_root=tmp_path, non_interactive=True)
    results = d.run_onboard(ctx, steps=steps)
    out = capsys.readouterr().out
    assert "non-interactive" in out.lower()
    assert "detect_prereqs" in out
    assert d.is_hard_failure(results, ctx) is True


def test_interactive_guide_is_soft_stop(tmp_path: Path, capsys):
    steps = [("detect_prereqs", lambda ctx: StepResult.guide("install uv"))]
    ctx = OnboardContext(repo_root=tmp_path, non_interactive=False)
    results = d.run_onboard(ctx, steps=steps)
    out = capsys.readouterr().out
    assert "non-interactive" not in out.lower()
    assert results[-1][1].status == "guide"
    assert d.is_hard_failure(results, ctx) is True  # guide is non-ok -> still non-zero
