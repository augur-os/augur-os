from __future__ import annotations
import pytest

import subprocess
import sys
import textwrap
from pathlib import Path

from src.lib import partition_integrity as pi


def _policy_file(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "partition_policy.yaml"
    p.write_text(textwrap.dedent(body), encoding="utf-8")
    return p


def test_load_policy_returns_normalized_keys(tmp_path: Path) -> None:
    cfg = _policy_file(
        tmp_path,
        """
        private_paths:
          - "project-brain/knowledge/wiki/**"
        forbidden_suffixes: [".pem", ".KEY"]
        forbidden_names: [".env"]
        secret_patterns:
          - "AKIA[0-9A-Z]{16}"
        exclude_dirs: [".git", "node_modules"]
        exclude_globs:
          - "**/__pycache__/**"
        """,
    )
    policy = pi.load_policy(cfg)
    assert policy["private_paths"] == ["project-brain/knowledge/wiki/**"]
    # forbidden_suffixes are lowercased for case-insensitive matching.
    assert policy["forbidden_suffixes"] == {".pem", ".key"}
    assert policy["forbidden_names"] == {".env"}
    assert policy["secret_patterns"] == ["AKIA[0-9A-Z]{16}"]
    assert policy["exclude_dirs"] == {".git", "node_modules"}
    assert policy["exclude_globs"] == ["**/__pycache__/**"]


def test_load_policy_tolerates_missing_keys(tmp_path: Path) -> None:
    cfg = _policy_file(tmp_path, "exclude_dirs: [.git]\n")
    policy = pi.load_policy(cfg)
    assert policy["private_paths"] == []
    assert policy["forbidden_suffixes"] == set()
    assert policy["forbidden_names"] == set()
    assert policy["secret_patterns"] == []


def _minimal_policy() -> dict:
    return {
        "private_paths": ["project-brain/knowledge/wiki/**"],
        "forbidden_suffixes": {".pem", ".key"},
        "forbidden_names": {".env"},
        "secret_patterns": [],
        "exclude_dirs": {"__pycache__", ".git", "node_modules"},
        "exclude_globs": ["**/__pycache__/**"],
    }


def test_scan_flags_file_in_private_path(tmp_path: Path) -> None:
    f = tmp_path / "project-brain/knowledge/wiki/note.md"
    f.parent.mkdir(parents=True)
    f.write_text("personal", encoding="utf-8")
    findings = pi.scan_partition(root=tmp_path, policy=_minimal_policy(), marker_regex=None)
    assert [(x.kind, x.path) for x in findings] == [("private-path", "project-brain/knowledge/wiki/note.md")]


def test_scan_flags_forbidden_suffix(tmp_path: Path) -> None:
    f = tmp_path / "src/server.key"
    f.parent.mkdir(parents=True)
    f.write_text("x", encoding="utf-8")
    findings = pi.scan_partition(root=tmp_path, policy=_minimal_policy(), marker_regex=None)
    assert [(x.kind, x.path) for x in findings] == [("forbidden-suffix", "src/server.key")]


def test_scan_respects_exclude_globs(tmp_path: Path) -> None:
    f = tmp_path / "src/__pycache__/x.key"
    f.parent.mkdir(parents=True)
    f.write_text("x", encoding="utf-8")
    assert pi.scan_partition(root=tmp_path, policy=_minimal_policy(), marker_regex=None) == []


def test_scan_clean_tree_returns_empty(tmp_path: Path) -> None:
    f = tmp_path / "src/ok.py"
    f.parent.mkdir(parents=True)
    f.write_text("print('hi')\n", encoding="utf-8")
    assert pi.scan_partition(root=tmp_path, policy=_minimal_policy(), marker_regex=None) == []


def test_scan_flags_dotfile_by_forbidden_name(tmp_path: Path) -> None:
    # `.env`.suffix == "" so the suffix check alone never catches it (false negative).
    f = tmp_path / "src/.env"
    f.parent.mkdir(parents=True)
    f.write_text("SECRET=hunter2\n", encoding="utf-8")
    findings = pi.scan_partition(root=tmp_path, policy=_minimal_policy(), marker_regex=None)
    kinds = {(x.kind, x.path) for x in findings}
    assert ("forbidden-name", "src/.env") in kinds


def test_scan_flags_dotfile_with_extra_suffix(tmp_path: Path) -> None:
    # `.env.local` must be caught too (name starts with the forbidden ".env." prefix).
    f = tmp_path / "src/.env.local"
    f.parent.mkdir(parents=True)
    f.write_text("SECRET=hunter2\n", encoding="utf-8")
    findings = pi.scan_partition(root=tmp_path, policy=_minimal_policy(), marker_regex=None)
    assert any(x.kind == "forbidden-name" and x.path == "src/.env.local" for x in findings)


def test_scan_does_not_flag_env_example_template(tmp_path: Path) -> None:
    # `.env.example` is a standard committed, secret-free public template.
    f = tmp_path / "config/.env.example"
    f.parent.mkdir(parents=True)
    f.write_text("SECRET=changeme\n", encoding="utf-8")
    findings = pi.scan_partition(root=tmp_path, policy=_minimal_policy(), marker_regex=None)
    assert all(x.kind != "forbidden-name" for x in findings), findings


def test_scan_does_not_flag_env_mcp_example_template(tmp_path: Path) -> None:
    f = tmp_path / "config/integrations/.env.mcp.example"
    f.parent.mkdir(parents=True)
    f.write_text("SECRET=changeme\n", encoding="utf-8")
    findings = pi.scan_partition(root=tmp_path, policy=_minimal_policy(), marker_regex=None)
    assert all(x.kind != "forbidden-name" for x in findings), findings


def test_scan_does_not_flag_environment_no_boundary(tmp_path: Path) -> None:
    # `.environment` must NOT match `.env` — there is no `.` boundary after `.env`.
    f = tmp_path / "src/.environment"
    f.parent.mkdir(parents=True)
    f.write_text("x\n", encoding="utf-8")
    findings = pi.scan_partition(root=tmp_path, policy=_minimal_policy(), marker_regex=None)
    assert all(x.kind != "forbidden-name" for x in findings), findings


def test_scan_flags_symlink_within_scan_root(tmp_path: Path) -> None:
    target = tmp_path / "outside"
    target.mkdir()
    (target / "private.md").write_text("private vault contents", encoding="utf-8")
    link = tmp_path / "src" / "vaultlink"
    link.parent.mkdir(parents=True)
    link.symlink_to(target, target_is_directory=True)
    findings = pi.scan_partition(root=tmp_path, policy=_minimal_policy(), marker_regex=None)
    symlinks = [x for x in findings if x.kind == "symlink"]
    assert symlinks, f"expected a symlink finding, got {findings!r}"
    assert symlinks[0].path == "src/vaultlink"


def test_scan_covers_toplevel_files(tmp_path: Path) -> None:
    # Top-level files (CLAUDE.md, project.yaml, ...) must be scanned under `full`.
    f = tmp_path / "CLAUDE.md"
    f.write_text("owner janedoe here\n", encoding="utf-8")
    findings = pi.scan_partition(root=tmp_path, policy=_minimal_policy(), marker_regex="janedoe")
    assert [(x.kind, x.path, x.line) for x in findings] == [("marker", "CLAUDE.md", 1)]


def test_scan_covers_toplevel_dirs(tmp_path: Path) -> None:
    # Whole top-level dirs (packages/, factory/, ...) must be scanned under `full`.
    f = tmp_path / "packages" / "thing" / "creds.py"
    f.parent.mkdir(parents=True)
    # A non-canonical AKIA-format token (not the AWS docs example) so the generic
    # detection assertion is unaffected by the AKIAIOSFODNN7EXAMPLE suppression.
    f.write_text("k = 'AKIAQWERTY1234567890'\n", encoding="utf-8")
    policy = _minimal_policy()
    policy["secret_patterns"] = ["AKIA[0-9A-Z]{16}"]
    findings = pi.scan_partition(root=tmp_path, policy=policy, marker_regex=None)
    assert [(x.kind, x.path, x.line) for x in findings] == [("secret", "packages/thing/creds.py", 1)]


def test_scan_skips_exclude_dirs(tmp_path: Path) -> None:
    f = tmp_path / "node_modules" / "pkg" / "server.key"
    f.parent.mkdir(parents=True)
    f.write_text("x", encoding="utf-8")
    assert pi.scan_partition(root=tmp_path, policy=_minimal_policy(), marker_regex=None) == []


def test_scan_forbidden_suffix_case_insensitive(tmp_path: Path) -> None:
    f = tmp_path / "src/server.KEY"
    f.parent.mkdir(parents=True)
    f.write_text("x", encoding="utf-8")
    findings = pi.scan_partition(root=tmp_path, policy=_minimal_policy(), marker_regex=None)
    assert [(x.kind, x.path) for x in findings] == [("forbidden-suffix", "src/server.KEY")]


def test_scan_flags_private_marker_when_regex_supplied(tmp_path: Path) -> None:
    f = tmp_path / "src/cfg.py"
    f.parent.mkdir(parents=True)
    f.write_text("owner = 'janedoe@example.com'\n", encoding="utf-8")
    findings = pi.scan_partition(root=tmp_path, policy=_minimal_policy(), marker_regex="janedoe")
    assert [(x.kind, x.path, x.line) for x in findings] == [("marker", "src/cfg.py", 1)]


def test_scan_no_marker_findings_without_regex(tmp_path: Path) -> None:
    f = tmp_path / "src/cfg.py"
    f.parent.mkdir(parents=True)
    f.write_text("owner = 'janedoe@example.com'\n", encoding="utf-8")
    assert pi.scan_partition(root=tmp_path, policy=_minimal_policy(), marker_regex=None) == []


def test_scan_flags_secret_pattern(tmp_path: Path) -> None:
    policy = _minimal_policy()
    policy["secret_patterns"] = ["AKIA[0-9A-Z]{16}"]
    f = tmp_path / "src/creds.py"
    f.parent.mkdir(parents=True)
    f.write_text("key = 'AKIAQWERTY1234567890'\n", encoding="utf-8")
    findings = pi.scan_partition(root=tmp_path, policy=policy, marker_regex=None)
    assert [(x.kind, x.line) for x in findings] == [("secret", 1)]


def test_secret_allow_globs_suppress_only_inside_allowlist(tmp_path: Path) -> None:
    # A file UNDER a secret_allow_glob with an example token -> NO secret finding;
    # the SAME token OUTSIDE the allowlist is still flagged (detection not weakened).
    policy = _minimal_policy()
    policy["secret_patterns"] = ["AKIA[0-9A-Z]{16}"]
    policy["secret_allow_globs"] = ["tests/**"]
    token = "k = 'AKIAQWERTY1234567890'\n"

    allowed = tmp_path / "tests/fixtures/creds.py"
    allowed.parent.mkdir(parents=True)
    allowed.write_text(token, encoding="utf-8")
    flagged = tmp_path / "src/creds.py"
    flagged.parent.mkdir(parents=True)
    flagged.write_text(token, encoding="utf-8")

    findings = pi.scan_partition(root=tmp_path, policy=policy, marker_regex=None)
    assert [(x.kind, x.path, x.line) for x in findings] == [("secret", "src/creds.py", 1)]


def test_secret_allow_globs_do_not_relax_marker_check(tmp_path: Path) -> None:
    # secret_allow_globs suppress ONLY `secret` findings; a marker in the same file
    # is still reported.
    policy = _minimal_policy()
    policy["secret_patterns"] = ["AKIA[0-9A-Z]{16}"]
    policy["secret_allow_globs"] = ["tests/**"]
    f = tmp_path / "tests/fixtures/creds.py"
    f.parent.mkdir(parents=True)
    f.write_text("janedoe AKIAQWERTY1234567890\n", encoding="utf-8")
    findings = pi.scan_partition(root=tmp_path, policy=policy, marker_regex="janedoe")
    assert [(x.kind, x.path, x.line) for x in findings] == [("marker", "tests/fixtures/creds.py", 1)]


def test_aws_example_token_never_flagged(tmp_path: Path) -> None:
    # The canonical AWS docs example token is suppressed everywhere, even outside
    # any secret_allow_glob.
    policy = _minimal_policy()
    policy["secret_patterns"] = ["AKIA[0-9A-Z]{16}"]
    f = tmp_path / "src/creds.py"
    f.parent.mkdir(parents=True)
    f.write_text("k = 'AKIAIOSFODNN7EXAMPLE'\n", encoding="utf-8")
    assert pi.scan_partition(root=tmp_path, policy=policy, marker_regex=None) == []


def test_scan_content_scans_non_allowlisted_text_suffix(tmp_path: Path) -> None:
    # A .sql file was missed by the old allowlist; the binary denylist now scans it.
    f = tmp_path / "src/dump.sql"
    f.parent.mkdir(parents=True)
    f.write_text("-- owner janedoe\nSELECT 1;\n", encoding="utf-8")
    findings = pi.scan_partition(root=tmp_path, policy=_minimal_policy(), marker_regex="janedoe")
    assert [(x.kind, x.path, x.line) for x in findings] == [("marker", "src/dump.sql", 1)]


def test_scan_skips_binary_suffix_content(tmp_path: Path) -> None:
    policy = _minimal_policy()
    policy["secret_patterns"] = ["AKIA[0-9A-Z]{16}"]
    f = tmp_path / "src/blob.png"
    f.parent.mkdir(parents=True)
    f.write_bytes(b"AKIAQWERTY1234567890\x00\xff")
    assert pi.scan_partition(root=tmp_path, policy=policy, marker_regex=None) == []


def _git_init(root: Path) -> None:
    env = {
        **__import__("os").environ,
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@e",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@e",
    }
    subprocess.run(["git", "init", "-q"], cwd=root, check=True, env=env)


def test_scan_only_tracked_in_git_repo(tmp_path: Path) -> None:
    # In a git work tree, only git-tracked files are scanned; gitignored/untracked
    # artifacts (which never get published) must NOT be reported.
    _git_init(tmp_path)
    tracked = tmp_path / "src/tracked.key"
    tracked.parent.mkdir(parents=True)
    tracked.write_text("x", encoding="utf-8")
    untracked = tmp_path / "src/untracked.key"
    untracked.write_text("x", encoding="utf-8")
    subprocess.run(["git", "add", "src/tracked.key"], cwd=tmp_path, check=True)

    findings = pi.scan_partition(root=tmp_path, policy=_minimal_policy(), marker_regex=None)
    paths = {(x.kind, x.path) for x in findings}
    assert ("forbidden-suffix", "src/tracked.key") in paths
    assert ("forbidden-suffix", "src/untracked.key") not in paths


def test_scan_git_repo_reports_tracked_symlink_only(tmp_path: Path) -> None:
    # A tracked symlink is still reported as kind="symlink"; an untracked symlink
    # (a dev/build artifact) is skipped.
    _git_init(tmp_path)
    target = tmp_path / "outside"
    target.mkdir()
    (target / "private.md").write_text("private vault contents", encoding="utf-8")

    (tmp_path / "src").mkdir()
    tracked_link = tmp_path / "src" / "trackedlink"
    tracked_link.symlink_to(target, target_is_directory=True)
    untracked_link = tmp_path / "src" / "untrackedlink"
    untracked_link.symlink_to(target, target_is_directory=True)
    subprocess.run(["git", "add", "src/trackedlink"], cwd=tmp_path, check=True)

    findings = pi.scan_partition(root=tmp_path, policy=_minimal_policy(), marker_regex=None)
    symlinks = {x.path for x in findings if x.kind == "symlink"}
    assert "src/trackedlink" in symlinks
    assert "src/untrackedlink" not in symlinks


def test_scan_subdir_of_git_repo_falls_back_to_full_walk(tmp_path: Path) -> None:
    # Scanning a SUBDIR of a git work tree (not the toplevel) must NOT trust the
    # tracked-set: `git ls-files` from there returns an empty set, which would skip
    # every file and report a false "clean". The scanner must fall back to the full
    # walk so an untracked secret in the subdir is STILL flagged.
    _git_init(tmp_path)
    sub = tmp_path / "scratch"
    sub.mkdir()
    (sub / "server.key").write_text("x", encoding="utf-8")  # untracked, never added

    findings = pi.scan_partition(root=sub, policy=_minimal_policy(), marker_regex=None)
    assert [(x.kind, x.path) for x in findings] == [("forbidden-suffix", "server.key")]
    # And the helper returns None for a non-toplevel subdir.
    assert pi._tracked_files(sub) is None


def test_tracked_files_returns_none_outside_git_repo(tmp_path: Path) -> None:
    # No .git -> _tracked_files returns None and the full-walk fallback runs
    # (this is the archived-release-tree case the release guard relies on).
    assert pi._tracked_files(tmp_path) is None


def test_resolve_scope_reads_value(tmp_path: Path) -> None:
    cfg = tmp_path / "release_scope.yaml"
    cfg.write_text("scope: full\n", encoding="utf-8")
    assert pi.resolve_scope(cfg) == "full"


def test_resolve_scope_defaults_docs_only(tmp_path: Path) -> None:
    cfg = tmp_path / "release_scope.yaml"
    cfg.write_text("{}\n", encoding="utf-8")
    assert pi.resolve_scope(cfg) == "docs_only"


def _cli_policy(tmp_path: Path) -> Path:
    policy = tmp_path / "policy.yaml"
    policy.write_text(
        "forbidden_suffixes: ['.key']\nforbidden_names: []\nprivate_paths: []\n"
        "secret_patterns: []\nexclude_dirs: []\nexclude_globs: []\n",
        encoding="utf-8",
    )
    return policy


def _run_cli(tmp_path: Path, policy: Path) -> subprocess.CompletedProcess:
    repo = Path(__file__).resolve().parents[1]
    return subprocess.run(
        [
            sys.executable,
            str(repo / "scripts/scan_partition_integrity.py"),
            "--root",
            str(tmp_path),
            "--policy",
            str(policy),
        ],
        capture_output=True,
        text=True,
    )


def test_cli_exits_zero_on_clean_tree(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src/ok.py").write_text("print('hi')\n", encoding="utf-8")
    proc = _run_cli(tmp_path, _cli_policy(tmp_path))
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_cli_exits_one_and_reports_on_finding(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src/server.key").write_text("x", encoding="utf-8")
    proc = _run_cli(tmp_path, _cli_policy(tmp_path))
    assert proc.returncode == 1
    assert "forbidden-suffix" in proc.stdout
    assert "src/server.key" in proc.stdout


@pytest.mark.skipif(sys.platform == "win32", reason="env-stripped subprocess on Windows; validation pending (ROADMAP)")
def test_cli_warns_when_no_marker_regex(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src/ok.py").write_text("print('hi')\n", encoding="utf-8")
    repo = Path(__file__).resolve().parents[1]
    env = {"PATH": "/usr/bin:/bin"}
    proc = subprocess.run(
        [
            sys.executable,
            str(repo / "scripts/scan_partition_integrity.py"),
            "--root",
            str(tmp_path),
            "--policy",
            str(_cli_policy(tmp_path)),
        ],
        capture_output=True,
        text=True,
        env={**env, "AUGUR_PRIVATE_MARKER_REGEX": ""},
    )
    assert "WARNING" in proc.stderr
    assert "marker" in proc.stderr.lower()


def test_public_release_files_includes_code_excludes_internal():
    from pathlib import Path
    from src.lib.partition_integrity import public_release_files, load_policy

    repo_root = Path(__file__).resolve().parents[1]
    files = set(public_release_files(repo_root, load_policy(repo_root / "config/system/partition_policy.yaml")))

    # Tracked code/docs that SHIP under full scope:
    assert any(f.startswith("src/") for f in files)
    assert any(f.startswith("project-brain/decisions/adrs/") for f in files)
    assert "config/system/partition_policy.yaml" in files
    assert any(f.startswith("tests/") for f in files)

    # Internal specs and build artifacts that must NOT ship:
    assert not any(f.startswith("docs/superpowers/") for f in files), "internal specs must be excluded"
    assert not any("__pycache__" in f for f in files)
    assert not any(f.startswith(".git/") for f in files)

    # Selector must equal the scanner's own considered set (published == scanned):
    from src.lib.partition_integrity import _iter_entries

    scanned = sorted(
        rel
        for _p, rel, is_link in _iter_entries(repo_root, load_policy(repo_root / "config/system/partition_policy.yaml"))
        if not is_link
    )
    assert sorted(files) == scanned
