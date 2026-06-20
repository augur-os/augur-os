"""Tests for the restart-augur safe-sync logic (real git in temp repos)."""
import importlib.util, subprocess, sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "restart_augur.py"
spec = importlib.util.spec_from_file_location("restart_augur", SCRIPT)
restart_augur = importlib.util.module_from_spec(spec); sys.modules["restart_augur"] = restart_augur
spec.loader.exec_module(restart_augur)


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _setup(tmp):
    origin = tmp / "origin"; origin.mkdir()
    _git(origin, "init", "-q", "--initial-branch=main")
    _git(origin, "config", "user.email", "t@t"); _git(origin, "config", "user.name", "t")
    (origin / "f.txt").write_text("base\n"); _git(origin, "add", "."); _git(origin, "commit", "-qm", "base")
    checkout = tmp / "checkout"
    subprocess.run(["git", "clone", "-q", str(origin), str(checkout)], check=True, capture_output=True)
    _git(checkout, "config", "user.email", "t@t"); _git(checkout, "config", "user.name", "t")
    return origin, checkout


def test_sync_rebases_and_restores_dirty(tmp_path):
    origin, checkout = _setup(tmp_path)
    (origin / "new.txt").write_text("o\n"); _git(origin, "add", "."); _git(origin, "commit", "-qm", "origin-new")
    (checkout / "local.txt").write_text("l\n"); _git(checkout, "add", "."); _git(checkout, "commit", "-qm", "local")
    (checkout / "dirty.txt").write_text("uncommitted\n")
    res = restart_augur.sync_checkout(checkout, target="origin/main")
    assert res["ok"] is True and res["restored_dirty"] is True
    assert (checkout / "new.txt").exists()       # rebased onto origin
    assert (checkout / "local.txt").exists()      # kept local commit
    assert (checkout / "dirty.txt").read_text() == "uncommitted\n"  # dirty restored


def test_sync_conflict_aborts_and_restores(tmp_path):
    origin, checkout = _setup(tmp_path)
    (origin / "f.txt").write_text("origin-side\n"); _git(origin, "add", "."); _git(origin, "commit", "-qm", "o")
    (checkout / "f.txt").write_text("checkout-side\n"); _git(checkout, "add", "."); _git(checkout, "commit", "-qm", "c")
    res = restart_augur.sync_checkout(checkout, target="origin/main")
    assert res["ok"] is False and res["step"] == "rebase"
    assert not (checkout / ".git" / "rebase-merge").exists()
    assert not (checkout / ".git" / "rebase-apply").exists()
    assert (checkout / "f.txt").read_text() == "checkout-side\n"  # not broken


def test_sync_non_git_path(tmp_path):
    res = restart_augur.sync_checkout(tmp_path / "nope", target="origin/main")
    assert res["ok"] is False and res["step"] == "resolve"
