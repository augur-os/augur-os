import subprocess

import pytest

from src.lib.brain_classify.move_executor import move_file_across_repos


def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _init_repo(path):
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-q")
    _git(path, "config", "user.email", "t@t")
    _git(path, "config", "user.name", "t")


def test_move_preserves_content_and_both_histories(tmp_path):
    src_repo = tmp_path / "Au-vault"
    dst_repo = tmp_path / "Augur"
    _init_repo(src_repo)
    _init_repo(dst_repo)
    src = src_repo / "wiki" / "concepts" / "daemon.md"
    src.parent.mkdir(parents=True)
    src.write_text("# Daemon\nbody-XYZ", encoding="utf-8")
    _git(src_repo, "add", ".")
    _git(src_repo, "commit", "-qm", "seed")
    (dst_repo / "x.md").write_text("x", encoding="utf-8")
    _git(dst_repo, "add", ".")
    _git(dst_repo, "commit", "-qm", "seed")

    dst = dst_repo / "project-brain" / "knowledge" / "wiki" / "concepts" / "daemon.md"
    move_file_across_repos(src=src, dst=dst, src_repo=src_repo, dst_repo=dst_repo, message="relocate daemon")

    assert dst.read_text(encoding="utf-8") == "# Daemon\nbody-XYZ"
    assert not src.exists()
    log = subprocess.run(
        ["git", "-C", str(src_repo), "log", "--oneline", "--", "wiki/concepts/daemon.md"],
        capture_output=True,
        text=True,
    ).stdout
    assert log.strip()  # source history still contains the file (recoverable)


def test_refuses_to_delete_source_if_target_write_missing(tmp_path, monkeypatch):
    src_repo = tmp_path / "Au-vault"
    dst_repo = tmp_path / "Augur"
    _init_repo(src_repo)
    _init_repo(dst_repo)
    src = src_repo / "a.md"
    src.write_text("keep", encoding="utf-8")
    _git(src_repo, "add", ".")
    _git(src_repo, "commit", "-qm", "s")
    import src.lib.brain_classify.move_executor as mx

    monkeypatch.setattr(mx, "_verify_committed", lambda *a, **k: False)
    with pytest.raises(RuntimeError, match="target not verified"):
        mx.move_file_across_repos(src=src, dst=dst_repo / "a.md", src_repo=src_repo, dst_repo=dst_repo, message="m")
    assert src.exists()  # source preserved on failure
