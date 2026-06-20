import subprocess

from skills.wiki.scripts.wiki_query_sources import GitRecentCommitsAdapter


def test_adapter_kind():
    assert GitRecentCommitsAdapter().kind == "git_recent_commits"


def test_resolve_calls_git_log_with_since(monkeypatch):
    captured: dict = {}

    def fake_run(cmd, *, capture_output, text, cwd, check):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="abc123 2026-05-11 commit msg\n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = GitRecentCommitsAdapter().resolve({"kind": "git_recent_commits", "recent_days": 7}, budget_tokens=10_000)

    assert "abc123" in result.text
    assert any("--since" in arg for arg in captured["cmd"])
    assert any("7 days ago" in arg for arg in captured["cmd"])


def test_resolve_default_14_days(monkeypatch):
    captured: dict = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    GitRecentCommitsAdapter().resolve({"kind": "git_recent_commits"}, budget_tokens=10_000)

    assert any("14 days ago" in arg for arg in captured["cmd"])


def test_resolve_git_failure_returns_empty(monkeypatch):
    def fake_run(cmd, **kwargs):
        raise subprocess.CalledProcessError(returncode=1, cmd=cmd, stderr="not a git repo")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = GitRecentCommitsAdapter().resolve({"kind": "git_recent_commits"}, budget_tokens=10_000)

    assert result.text == ""
