import subprocess
from pathlib import Path


from src.lib.vault_sync import vault_sync_status, vault_sync_run


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _init_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-q", "-b", "main")
    _git(path, "config", "user.email", "t@t.test")
    _git(path, "config", "user.name", "Test")
    (path / "BRAIN.yaml").write_text("layout: domains\n", encoding="utf-8")
    _git(path, "add", "-A")
    _git(path, "commit", "-q", "-m", "init")
    return path


def _bare_remote(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    # -b main so the bare repo's default HEAD matches the working repos; without
    # it, clones land on `master` and push to the wrong branch.
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(path)], check=True)
    return path


def test_status_clean_synced(tmp_path):
    remote = _bare_remote(tmp_path / "remote.git")
    repo = _init_repo(tmp_path / "vault")
    _git(repo, "remote", "add", "origin", str(remote))
    _git(repo, "push", "-q", "-u", "origin", "main")
    st = vault_sync_status(repo)
    assert st["vault_configured"] is True
    assert st["synced"] is True
    assert st["uncommitted"] == 0
    assert st["unpushed"] == 0
    assert st["has_upstream"] is True


def test_status_dirty_working_tree(tmp_path):
    repo = _init_repo(tmp_path / "vault")
    (repo / "note.md").write_text("new\n", encoding="utf-8")
    st = vault_sync_status(repo)
    assert st["uncommitted"] == 1
    assert st["synced"] is False


def test_status_unpushed_commits(tmp_path):
    remote = _bare_remote(tmp_path / "remote.git")
    repo = _init_repo(tmp_path / "vault")
    _git(repo, "remote", "add", "origin", str(remote))
    _git(repo, "push", "-q", "-u", "origin", "main")
    (repo / "a.md").write_text("x\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "local only")
    st = vault_sync_status(repo)
    assert st["unpushed"] == 1
    assert st["synced"] is False


def test_status_no_vault(tmp_path):
    plain = tmp_path / "not-a-repo"
    plain.mkdir()
    st = vault_sync_status(plain)
    assert st["vault_configured"] is False
    assert st["synced"] is True  # nothing to sync; chip will hide


def test_run_commits_pulls_pushes(tmp_path):
    remote = _bare_remote(tmp_path / "remote.git")
    repo = _init_repo(tmp_path / "vault")
    _git(repo, "remote", "add", "origin", str(remote))
    _git(repo, "push", "-q", "-u", "origin", "main")
    # a second clone pushes a commit so the remote is ahead of `repo`
    other = tmp_path / "other"
    subprocess.run(["git", "clone", "-q", str(remote), str(other)], check=True)
    _git(other, "config", "user.email", "o@o.test")
    _git(other, "config", "user.name", "Other")
    (other / "remote-add.md").write_text("from remote\n", encoding="utf-8")
    _git(other, "add", "-A")
    _git(other, "commit", "-q", "-m", "remote change")
    _git(other, "push", "-q")
    # local repo has its own uncommitted change
    (repo / "local.md").write_text("from local\n", encoding="utf-8")

    result = vault_sync_run(repo)
    assert result["success"] is True
    assert result["conflict"] is False
    assert result["committed"] == 1
    assert result["pulled"] == 1
    assert result["pushed"] >= 1
    # end state: clean + synced, remote has the local file
    st = vault_sync_status(repo)
    assert st["synced"] is True
    assert (repo / "remote-add.md").exists()  # pulled
    _, names, _ = _git2(remote, "ls-tree", "-r", "--name-only", "main")
    assert "local.md" in names  # pushed


def test_run_nothing_to_do(tmp_path):
    remote = _bare_remote(tmp_path / "remote.git")
    repo = _init_repo(tmp_path / "vault")
    _git(repo, "remote", "add", "origin", str(remote))
    _git(repo, "push", "-q", "-u", "origin", "main")
    result = vault_sync_run(repo)
    assert result["success"] is True
    assert result["committed"] == 0
    assert result["pushed"] == 0
    assert result["conflict"] is False


def test_run_conflict_aborts_no_loss(tmp_path):
    remote = _bare_remote(tmp_path / "remote.git")
    repo = _init_repo(tmp_path / "vault")
    _git(repo, "remote", "add", "origin", str(remote))
    (repo / "shared.md").write_text("base\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")
    _git(repo, "push", "-q", "-u", "origin", "main")
    other = tmp_path / "other"
    subprocess.run(["git", "clone", "-q", str(remote), str(other)], check=True)
    _git(other, "config", "user.email", "o@o.test")
    _git(other, "config", "user.name", "Other")
    (other / "shared.md").write_text("remote version\n", encoding="utf-8")
    _git(other, "add", "-A")
    _git(other, "commit", "-q", "-m", "remote edit")
    _git(other, "push", "-q")
    # local diverges on the SAME file
    (repo / "shared.md").write_text("local version\n", encoding="utf-8")

    result = vault_sync_run(repo)
    assert result["success"] is False
    assert result["conflict"] is True
    assert "shared.md" in result["message"]
    # working tree restored (merge aborted), local change intact, remote unchanged
    assert (repo / "shared.md").read_text(encoding="utf-8") == "local version\n"
    _, log, _ = _git2(remote, "log", "--oneline")
    assert "remote edit" in log and "local edit" not in log


def _git2(repo: Path, *args: str):
    proc = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
