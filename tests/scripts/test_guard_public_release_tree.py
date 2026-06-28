from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from scripts.build_public_release_tree import build_release_tree  # noqa: E402
from scripts.guard_public_release_tree import (  # noqa: E402
    PublicReleaseGuardError,
    guard_public_tree,
    machine_path_markers,
    scan_content_safety,
)


@pytest.fixture(autouse=True)
def _force_docs_only_scope(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin the guard to docs_only scope for the allowlist-behavior tests.

    The committed config/system/release_scope.yaml is now `full` (M6 public
    release). These tests assert the docs_only allowlist guard rejects leaks, so
    they must be hermetic w.r.t. the committed scope. AUGUR_RELEASE_SCOPE_CONFIG
    is the seam the guard already honors (guard_public_release_tree.guard_public_tree
    -> resolve_scope); pointing it at a docs_only file forces the allowlist path
    in-process and (via inherited os.environ) in the CLI subprocess tests.
    """
    scope_cfg = tmp_path_factory.mktemp("release-scope") / "release_scope.yaml"
    scope_cfg.write_text("scope: docs_only\n", encoding="utf-8")
    monkeypatch.setenv("AUGUR_RELEASE_SCOPE_CONFIG", str(scope_cfg))


def test_guard_allows_generated_public_release_tree(tmp_path: Path) -> None:
    output_root = tmp_path / "public"

    build_release_tree("docs_only", source_root=PROJECT_ROOT, output_root=output_root)

    assert guard_public_tree(output_root) == []


def test_guard_rejects_unallowlisted_public_files(tmp_path: Path) -> None:
    output_root = tmp_path / "public"
    build_release_tree("docs_only", source_root=PROJECT_ROOT, output_root=output_root)

    (output_root / "docs" / "random-investor-note.md").write_text("# not allowlisted\n", encoding="utf-8")

    try:
        guard_public_tree(output_root)
    except PublicReleaseGuardError as exc:
        message = str(exc)
    else:
        raise AssertionError("expected public release guard to fail")

    assert "unexpected public file: docs/random-investor-note.md" in message


def test_guard_rejects_missing_allowlisted_public_files(tmp_path: Path) -> None:
    output_root = tmp_path / "public"
    build_release_tree("docs_only", source_root=PROJECT_ROOT, output_root=output_root)

    (output_root / "README.md").unlink()

    try:
        guard_public_tree(output_root)
    except PublicReleaseGuardError as exc:
        message = str(exc)
    else:
        raise AssertionError("expected public release guard to fail")

    assert "missing allowlisted file: README.md" in message


def test_guard_rejects_full_source_tree_surfaces(tmp_path: Path) -> None:
    public_root = tmp_path / "public"
    (public_root / "src" / "secret.py").parent.mkdir(parents=True)
    (public_root / "src" / "secret.py").write_text("print('not public')\n", encoding="utf-8")
    (public_root / "project-brain" / "decisions" / "adrs" / "ADR-001.md").parent.mkdir(parents=True)
    (public_root / "project-brain" / "decisions" / "adrs" / "ADR-001.md").write_text("# internal\n", encoding="utf-8")
    (public_root / "docs" / "security" / "README.md").parent.mkdir(parents=True)
    (public_root / "docs" / "security" / "README.md").write_text("# internal\n", encoding="utf-8")

    try:
        guard_public_tree(public_root)
    except PublicReleaseGuardError as exc:
        message = str(exc)
    else:
        raise AssertionError("expected public release guard to fail")

    assert "forbidden path: src/secret.py" in message
    assert "forbidden path: project-brain/decisions/adrs/ADR-001.md" in message
    assert "forbidden path: docs/security/README.md" in message


def test_guard_rejects_binary_files_and_private_markers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # M2 redesign: personal-path markers (Au-vault, ~/…) are no longer hardcoded in
    # FORBIDDEN_CONTENT_MARKERS; they come from AUGUR_PRIVATE_MARKER_REGEX (never committed).
    # Bare "~" is also NOT a forbidden marker — M1 genericized /Users/… → ~ across docs.
    # Drive the personal-marker check through the env var to prove detection still works.
    monkeypatch.setenv("AUGUR_PRIVATE_MARKER_REGEX", "Au-vault")

    public_root = tmp_path / "public"
    (public_root / "docs").mkdir(parents=True)
    (public_root / "docs" / "architecture-overview.md").write_text(
        "Review path: ~/Projects/Au-vault\n",
        encoding="utf-8",
    )
    (public_root / "docs" / "deck.pdf").write_bytes(b"%PDF private deck")

    try:
        guard_public_tree(public_root)
    except PublicReleaseGuardError as exc:
        message = str(exc)
    else:
        raise AssertionError("expected public release guard to fail")

    # Env-driven personal-marker detection: guard must flag Au-vault via AUGUR_PRIVATE_MARKER_REGEX
    assert "forbidden content marker 'Au-vault'" in message
    # Binary / forbidden file-type detection must still work
    assert "forbidden file type: docs/deck.pdf" in message


def test_guard_cli_exits_nonzero_for_unsafe_tree(tmp_path: Path) -> None:
    public_root = tmp_path / "public"
    (public_root / "apps" / "dashboard").mkdir(parents=True)
    (public_root / "apps" / "dashboard" / "page.tsx").write_text("export {}\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/guard_public_release_tree.py",
            "--root",
            str(public_root),
        ],
        cwd=PROJECT_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 1
    assert "forbidden path: apps/dashboard/page.tsx" in result.stderr


def test_guard_cli_allows_generated_public_release_tree(tmp_path: Path) -> None:
    public_root = tmp_path / "public"
    build_release_tree("docs_only", source_root=PROJECT_ROOT, output_root=public_root)

    result = subprocess.run(
        [
            sys.executable,
            "scripts/guard_public_release_tree.py",
            "--root",
            str(public_root),
            "--source-root",
            str(PROJECT_ROOT),
        ],
        cwd=PROJECT_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0
    assert "public release guard passed" in result.stdout


# --- Machine-specific path leak guard (regression: BRAIN.yaml /Users/<name> in v1.12.0) ---


def test_scan_content_safety_flags_builder_home_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A file containing the building user's absolute home dir is a leak.

    Regression: `project-brain/BRAIN.yaml` mutated locally to
    `root: /Users/<name>/...` was published to the public release tree because
    the release builder copies the working tree and the partition scan does not
    inspect content. The guard must reject the builder's real home path.
    """
    fake_home = tmp_path / "home" / "alice-dev-9000"
    fake_home.mkdir(parents=True)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))

    tree = tmp_path / "public"
    (tree / "project-brain").mkdir(parents=True)
    (tree / "project-brain" / "BRAIN.yaml").write_text(f"root: {fake_home}/project-brain\n", encoding="utf-8")

    violations = scan_content_safety(tree)
    assert any(v.reason == "machine-specific path" for v in violations), violations
    assert any(str(fake_home) in v.format() for v in violations)


def test_scan_content_safety_ignores_placeholder_user_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Generic placeholder home paths in fixtures/docs are NOT leaks.

    The release tree legitimately carries `/Users/example`, `/home/user`, and
    Home Assistant `/home/skills` entity ids; only the *actual* builder home is a
    leak, so these must pass.
    """
    fake_home = tmp_path / "home" / "alice-dev-9000"
    fake_home.mkdir(parents=True)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))

    tree = tmp_path / "public"
    (tree / "tests").mkdir(parents=True)
    (tree / "tests" / "fixtures.py").write_text(
        'P = "/Users/example/x"\nQ = "/home/user/y"\nR = "/home/skills"\n',
        encoding="utf-8",
    )

    assert scan_content_safety(tree) == []


def test_machine_path_markers_skips_degenerate_home(monkeypatch: pytest.MonkeyPatch) -> None:
    """A degenerate home like '/' must not become a marker that matches everything."""
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: Path("/")))
    monkeypatch.setattr("getpass.getuser", lambda: "ci")  # too short to be a marker
    assert machine_path_markers() == []


def test_full_scope_guard_blocks_machine_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Under `full` scope the guard must still block machine-path leaks.

    Regression: full scope previously returned ONLY partition findings, so
    content leaks (secrets, private markers, machine paths) were never scanned.
    """
    scope_cfg = tmp_path / "release_scope.yaml"
    scope_cfg.write_text("scope: full\n", encoding="utf-8")
    monkeypatch.setenv("AUGUR_RELEASE_SCOPE_CONFIG", str(scope_cfg))
    # Isolate the content-safety addition from the real partition policy.
    monkeypatch.setattr("scripts.guard_public_release_tree.scan_partition", lambda **_: [])

    fake_home = tmp_path / "home" / "alice-dev-9000"
    fake_home.mkdir(parents=True)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))

    tree = tmp_path / "public"
    (tree / "src").mkdir(parents=True)
    (tree / "src" / "leak.py").write_text(f'HOME = "{fake_home}"\n', encoding="utf-8")

    try:
        guard_public_tree(tree, source_root=PROJECT_ROOT)
    except PublicReleaseGuardError as exc:
        message = str(exc)
    else:
        raise AssertionError("expected full-scope guard to block machine path")

    assert "machine-specific path" in message
    assert "src/leak.py" in message


def test_full_scope_guard_honors_private_marker_regex(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Full scope must apply the configured AUGUR_PRIVATE_MARKER_REGEX to content.

    Regression: full scope previously returned ONLY partition findings, so the
    configured private-marker regex was never applied to file content.
    """
    scope_cfg = tmp_path / "release_scope.yaml"
    scope_cfg.write_text("scope: full\n", encoding="utf-8")
    monkeypatch.setenv("AUGUR_RELEASE_SCOPE_CONFIG", str(scope_cfg))
    monkeypatch.setenv("AUGUR_PRIVATE_MARKER_REGEX", "Au-vault")
    monkeypatch.setattr("scripts.guard_public_release_tree.scan_partition", lambda **_: [])

    tree = tmp_path / "public"
    (tree / "src").mkdir(parents=True)
    (tree / "src" / "cfg.py").write_text('PATH = "~/Projects/Au-vault"\n', encoding="utf-8")

    try:
        guard_public_tree(tree, source_root=PROJECT_ROOT)
    except PublicReleaseGuardError as exc:
        message = str(exc)
    else:
        raise AssertionError("expected full-scope guard to honor private marker regex")

    assert "forbidden content marker 'Au-vault'" in message


def test_full_scope_guard_ignores_envvar_name_markers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Full scope must NOT flag env-var NAMES in real source (false-positive guard).

    OPENAI_API_KEY / ANTHROPIC_API_KEY / "PRIVATE KEY" appear legitimately across
    the full code tree (adapters, config templates, security scanners). The
    docs_only env-var-name marker list must not be applied under full scope.
    """
    scope_cfg = tmp_path / "release_scope.yaml"
    scope_cfg.write_text("scope: full\n", encoding="utf-8")
    monkeypatch.setenv("AUGUR_RELEASE_SCOPE_CONFIG", str(scope_cfg))
    monkeypatch.delenv("AUGUR_PRIVATE_MARKER_REGEX", raising=False)
    monkeypatch.setattr("scripts.guard_public_release_tree.scan_partition", lambda **_: [])

    tree = tmp_path / "public"
    (tree / "src").mkdir(parents=True)
    (tree / "src" / "adapter.py").write_text(
        'TOKEN_ENV = "ANTHROPIC_API_KEY"\nOTHER = "OPENAI_API_KEY"\n', encoding="utf-8"
    )

    assert guard_public_tree(tree, source_root=PROJECT_ROOT) == []
