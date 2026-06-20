from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ZERO_OID = "0" * 40


@pytest.fixture(autouse=True)
def _force_docs_only_scope(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin the push guard to docs_only scope for the allowlist-behavior tests.

    The committed config/system/release_scope.yaml is now `full` (M6 public
    release). guard_public_push -> guard_public_tree -> resolve_scope reads scope
    from AUGUR_RELEASE_SCOPE_CONFIG when set; pointing it at a docs_only file
    forces the allowlist path inside the guard subprocesses (os.environ is
    inherited by subprocess.run). The build step that bakes scope into its tree
    is forced separately via its --config argument.
    """
    scope_cfg = tmp_path_factory.mktemp("release-scope") / "release_scope.yaml"
    scope_cfg.write_text("scope: docs_only\n", encoding="utf-8")
    monkeypatch.setenv("AUGUR_RELEASE_SCOPE_CONFIG", str(scope_cfg))


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return result.stdout.strip()


def _init_repo(path: Path) -> None:
    path.mkdir(parents=True)
    _git(path, "init", "-q")
    _git(path, "config", "user.name", "Test User")
    _git(path, "config", "user.email", "test@example.com")


def _commit_all(path: Path, message: str) -> str:
    _git(path, "add", "-A")
    _git(path, "commit", "-q", "-m", message)
    return _git(path, "rev-parse", "HEAD")


def _run_guard(
    repo: Path,
    remote_url: str,
    stdin: str,
    *,
    remote_name: str = "augur-os",
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "guard_public_push.py"),
            "--remote-name",
            remote_name,
            "--remote-url",
            remote_url,
            "--repo",
            str(repo),
            "--source-root",
            str(PROJECT_ROOT),
        ],
        input=stdin,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def test_public_push_guard_blocks_full_source_commit(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / "src").mkdir()
    (repo / "src" / "secret.py").write_text("print('private')\n", encoding="utf-8")
    commit = _commit_all(repo, "private source")

    result = _run_guard(
        repo,
        "https://github.com/augur-os/augur-os.git",
        f"refs/heads/main {commit} refs/heads/main {ZERO_OID}\n",
    )

    assert result.returncode == 1
    assert "forbidden path: src/secret.py" in result.stderr


def test_public_push_guard_allows_exact_public_tree_commit(tmp_path: Path) -> None:
    public_tree = tmp_path / "public-tree"
    # The committed release_scope.yaml is now `full`; this test asserts the
    # docs_only allowlist tree is accepted, so build it from a docs_only config.
    docs_only_config = tmp_path / "release_scope.yaml"
    docs_only_config.write_text("scope: docs_only\n", encoding="utf-8")
    build = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "build_public_release_tree.py"),
            "--config",
            str(docs_only_config),
            "--source-root",
            str(PROJECT_ROOT),
            "--output-root",
            str(public_tree),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    assert "release_scope=docs_only" in build.stdout
    _git(public_tree, "init", "-q")
    _git(public_tree, "config", "user.name", "Test User")
    _git(public_tree, "config", "user.email", "test@example.com")
    commit = _commit_all(public_tree, "public tree")

    result = _run_guard(
        public_tree,
        "https://github.com/augur-os/augur-os.git",
        f"refs/heads/release/v1.8.0 {commit} refs/heads/release/v1.8.0 {ZERO_OID}\n",
    )

    assert result.returncode == 0
    assert "public push guard passed" in result.stdout


def test_public_push_guard_ignores_private_origin(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / "src").mkdir()
    (repo / "src" / "secret.py").write_text("print('private')\n", encoding="utf-8")
    commit = _commit_all(repo, "private source")

    result = _run_guard(
        repo,
        "https://github.com/gsannikov/augur.git",
        f"refs/heads/main {commit} refs/heads/main {ZERO_OID}\n",
        remote_name="origin",
    )

    assert result.returncode == 0
    assert result.stdout == ""


def test_pre_push_hook_uses_tree_guard_without_public_bypass() -> None:
    hook = (PROJECT_ROOT / ".githooks" / "pre-push").read_text(encoding="utf-8")

    assert "scripts/guard_public_push.py" in hook
    assert "AUGUR_RELEASE_PUSH" not in hook
