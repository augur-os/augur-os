from pathlib import Path

import src.mcp.augur_framework.tools.infrastructure.browse_delete_triage as tri


def test_standalone_artifact_routes_to_trash(tmp_path, monkeypatch):
    docs = tmp_path / "docs"
    (docs / "pages").mkdir(parents=True)
    f = docs / "pages" / "p.html"
    f.write_text("<html></html>", encoding="utf-8")
    monkeypatch.setattr(tri, "_is_git_tracked", lambda p, repo_root: False)
    monkeypatch.setattr(tri, "_has_rag_chunks", lambda p: False)
    out = tri.triage_impl(
        [{"id": "a", "path": str(f), "category": "pages"}],
        allowed_roots=[docs],
        repo_root=tmp_path / "repo",
    )
    assert out["trash"] == ["a"]
    assert out["sweep"] == []
    assert out["blocked"] == []


def test_git_tracked_routes_to_sweep(tmp_path, monkeypatch):
    docs = tmp_path / "docs"
    docs.mkdir()
    f = docs / "note.md"
    f.write_text("x", encoding="utf-8")
    monkeypatch.setattr(tri, "_is_git_tracked", lambda p, repo_root: True)
    monkeypatch.setattr(tri, "_has_rag_chunks", lambda p: False)
    out = tri.triage_impl(
        [{"id": "b", "path": str(f), "category": "notes"}],
        allowed_roots=[docs],
        repo_root=tmp_path / "repo",
    )
    assert out["sweep"] == ["b"]


def test_missing_path_is_blocked(tmp_path):
    out = tri.triage_impl(
        [{"id": "c", "path": "", "category": "notes"}],
        allowed_roots=[tmp_path],
        repo_root=tmp_path,
    )
    assert out["blocked"] == [{"id": "c", "reason": "missing path"}]


def test_is_git_tracked_handles_dash_prefixed_filename(tmp_path):
    """A filename beginning with '-' must not be smuggled as a git flag.

    Regression for argv flag injection: `git ls-files --error-unmatch <path>`
    without a `--` separator would treat `-dash.html` as an option. The `--`
    separator + resolved absolute path must classify it correctly as tracked.
    """
    import subprocess

    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    dash = repo / "-dash.html"
    normal = repo / "normal.html"
    dash.write_text("<html></html>", encoding="utf-8")
    normal.write_text("<html></html>", encoding="utf-8")
    # Stage both (the index is what --error-unmatch consults); use `--` so the
    # dash file is treated as a path here too.
    subprocess.run(["git", "add", "--", str(dash), str(normal)], cwd=repo, check=True)

    assert tri._is_git_tracked(dash, repo) is True
    assert tri._is_git_tracked(normal, repo) is True

    untracked_dash = repo / "-untracked.html"
    untracked_dash.write_text("<html></html>", encoding="utf-8")
    assert tri._is_git_tracked(untracked_dash, repo) is False
