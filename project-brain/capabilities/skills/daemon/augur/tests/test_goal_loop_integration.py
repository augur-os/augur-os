import subprocess
from pathlib import Path
import pytest
from routine_orchestrator import goal_loop, goal_catalog


def _git(*args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


@pytest.fixture
def temp_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git("init", "-q", cwd=repo)
    _git("config", "user.email", "t@t.t", cwd=repo)
    _git("config", "user.name", "t", cwd=repo)
    # Some git versions default the initial branch name; make it deterministic.
    _git("symbolic-ref", "HEAD", "refs/heads/main", cwd=repo)
    (repo / "broken.txt").write_text("DEFECT\n")
    _git("add", "-A", cwd=repo)
    _git("commit", "-qm", "seed", cwd=repo)
    return repo


def test_run_goal_creates_worktree_and_converges(temp_repo, monkeypatch):
    spec = goal_catalog.GoalSpec(id="fixit", title="fix", loops=("testing",))
    monkeypatch.setitem(goal_catalog.GOAL_CATALOG, "fixit", spec)

    state = {"fixed": False}

    class _R:
        def __init__(self, findings):
            self.findings = findings

    def fake_orchestrate(loop, *, project_root=None, **_):
        wt = Path(project_root)
        defect = wt / "broken.txt"
        if not state["fixed"] and defect.read_text().strip() == "DEFECT":
            defect.write_text("OK\n")
            state["fixed"] = True
            return _R([{"detail": "defect present", "loop": loop}])
        return _R([])  # next scan: clean -> converged

    result = goal_loop.run_goal_loops(
        "fixit",
        project_root=str(temp_repo),
        stamp="itest",
        orchestrate=fake_orchestrate,
        worktree_factory=goal_loop.create_goal_worktree,
        escalate=lambda *a, **k: None,
        loop_cap=5,
        max_iterations=20,
    )

    assert result.branch == "goal/fixit-itest"
    assert Path(result.worktree_path).exists()
    assert (Path(result.worktree_path) / "broken.txt").read_text().strip() == "OK"
    assert result.loop_outcomes[0].stop_reason == "converged"
    assert result.converged is True
