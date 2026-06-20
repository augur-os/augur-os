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
