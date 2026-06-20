from __future__ import annotations

import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from scripts.build_public_release_tree import (  # noqa: E402
    DOCS_ONLY_ALLOWLIST,
    DOCS_ONLY_DIR_ALLOWLIST,
    build_release_tree,
    load_release_scope,
)


def test_load_release_scope_reads_yaml(tmp_path: Path) -> None:
    config_path = tmp_path / "release_scope.yaml"
    config_path.write_text("scope: docs_only\n", encoding="utf-8")

    assert load_release_scope(config_path) == "docs_only"


def test_configured_public_release_scope_is_full() -> None:
    assert load_release_scope(PROJECT_ROOT / "config/system/release_scope.yaml") == "full"


def test_windows_install_guide_is_in_public_release_allowlist() -> None:
    assert "docs/guides/installation-windows.md" in DOCS_ONLY_ALLOWLIST


def test_windows_install_guide_mentions_one_click_bootstrap() -> None:
    text = (PROJECT_ROOT / "docs" / "guides" / "installation-windows.md").read_text(encoding="utf-8")

    assert "One-click setup from augur.run" in text
    assert "windows-one-click-bootstrap.ps1" in text
    assert "Codex sign-in" in text


def test_windows_install_guide_does_not_route_quick_install_to_legacy_install_ps1() -> None:
    text = (PROJECT_ROOT / "docs" / "guides" / "installation-windows.md").read_text(encoding="utf-8")

    assert "raw.githubusercontent.com/augur-os/augur-os/main/scripts/install.ps1" not in text

    quick_install_match = re.search(
        r"^### Quick Install\b(?P<section>.*?)(?=^### |\Z)",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    if quick_install_match:
        assert "scripts/install.ps1" not in quick_install_match.group("section")
        assert ".\\install.ps1" not in quick_install_match.group("section")


def test_windows_install_guide_uses_supported_extraction_status_command() -> None:
    text = (PROJECT_ROOT / "docs" / "guides" / "installation-windows.md").read_text(encoding="utf-8")

    assert "uv run aug get-extraction-status" in text
    assert "skills/document-extractor/scripts/mcp/tools_extract.py" not in text


def _populate_docs_only_fixture(source_root: Path) -> None:
    """Create the minimum fixture tree needed for build_release_tree('docs_only')."""
    for rel_path in DOCS_ONLY_ALLOWLIST:
        target = source_root / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"content for {rel_path}\n", encoding="utf-8")
    for rel_dir in DOCS_ONLY_DIR_ALLOWLIST:
        dir_target = source_root / rel_dir
        dir_target.mkdir(parents=True, exist_ok=True)
        # Sentinel so the directory is non-empty
        (dir_target / ".keep").write_text("", encoding="utf-8")


def test_build_release_tree_docs_only_copies_allowlisted_files(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    output_root = tmp_path / "out"

    _populate_docs_only_fixture(source_root)

    manifest = build_release_tree(
        scope="docs_only",
        source_root=source_root,
        output_root=output_root,
    )

    expected_dir_files = [(Path(d) / ".keep").as_posix() for d in DOCS_ONLY_DIR_ALLOWLIST]
    assert sorted(manifest) == sorted([*DOCS_ONLY_ALLOWLIST, *expected_dir_files])
    for rel_path in DOCS_ONLY_ALLOWLIST:
        assert (output_root / rel_path).read_text(encoding="utf-8") == (f"content for {rel_path}\n")


def test_build_release_tree_fails_when_allowlisted_file_missing(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    output_root = tmp_path / "out"

    only_path = source_root / DOCS_ONLY_ALLOWLIST[0]
    only_path.parent.mkdir(parents=True, exist_ok=True)
    only_path.write_text("ok\n", encoding="utf-8")

    try:
        build_release_tree("docs_only", source_root=source_root, output_root=output_root)
    except FileNotFoundError as exc:
        assert "missing allowlisted release file" in str(exc)
    else:
        raise AssertionError("expected FileNotFoundError")


def test_brain_adrs_is_not_in_dir_allowlist() -> None:
    assert "project-brain/decisions/adrs" not in DOCS_ONLY_DIR_ALLOWLIST


def test_public_release_allowlist_excludes_all_adr_files() -> None:
    assert all(not path.startswith("project-brain/decisions/adrs/") for path in DOCS_ONLY_ALLOWLIST)


def test_public_release_has_no_recursive_directory_allowlist() -> None:
    assert DOCS_ONLY_DIR_ALLOWLIST == []


def test_build_release_tree_keeps_non_allowlisted_dirs_out(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    output_root = tmp_path / "out"

    _populate_docs_only_fixture(source_root)

    security_dir = source_root / "docs" / "security"
    (security_dir / "nested").mkdir(parents=True, exist_ok=True)
    (security_dir / "nested" / "control.md").write_text("control\n", encoding="utf-8")

    manifest = build_release_tree(
        scope="docs_only",
        source_root=source_root,
        output_root=output_root,
    )

    assert "docs/security/nested/control.md" not in manifest
    assert not (output_root / "docs/security/nested/control.md").exists()


def test_real_public_release_tree_excludes_internal_surfaces_and_private_markers(tmp_path: Path) -> None:
    output_root = tmp_path / "public"

    manifest = build_release_tree(
        scope="docs_only",
        source_root=PROJECT_ROOT,
        output_root=output_root,
    )

    forbidden_roots = {
        ".claude",
        ".codex",
        "apps",
        "config",
        "packages",
        "plugins",
        "project-brain",
        "scripts",
        "shared-vault",
        "src",
        "tests",
    }
    assert forbidden_roots.isdisjoint({Path(path).parts[0] for path in manifest})
    assert all(not path.startswith("project-brain/decisions/adrs/") for path in manifest)
    assert all(not path.startswith("docs/security/") for path in manifest)
    assert all(not path.endswith(".DS_Store") for path in manifest)
    assert all(not path.endswith((".zip", ".pptx", ".pdf", ".png", ".jpg")) for path in manifest)

    private_markers = [
        # "~" excluded: M1 genericization replaced /Users/… with ~ across 68 files;
        # bare ~ (and ~60 = "approximately 60") is the intended public form, not a leak.
        "C:\\Users\\intel",
        "Au-vault",
        "Au-docs",
        "IntelSubmit",
        "angel-deck",
        "project-brain/decisions/adrs",
        "adrs/",
        "docs/security",
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "PRIVATE KEY",
        "sk-abcdefghijklmnopqrstuvwxyz",
    ]
    for file_path in output_root.rglob("*"):
        if not file_path.is_file():
            continue
        text = file_path.read_text(encoding="utf-8")
        for marker in private_markers:
            assert marker not in text, f"{marker!r} leaked into {file_path.relative_to(output_root)}"


def test_build_release_tree_does_not_require_directory_allowlist(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    output_root = tmp_path / "out"

    for rel_path in DOCS_ONLY_ALLOWLIST:
        target = source_root / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("ok\n", encoding="utf-8")

    manifest = build_release_tree("docs_only", source_root=source_root, output_root=output_root)

    assert sorted(manifest) == sorted(DOCS_ONLY_ALLOWLIST)


def test_load_release_scope_accepts_full(tmp_path: Path) -> None:
    config_path = tmp_path / "release_scope.yaml"
    config_path.write_text("scope: full\n", encoding="utf-8")
    assert load_release_scope(config_path) == "full"


def test_load_release_scope_still_rejects_unknown(tmp_path: Path) -> None:
    config_path = tmp_path / "release_scope.yaml"
    config_path.write_text("scope: bogus\n", encoding="utf-8")
    import pytest

    with pytest.raises(ValueError):
        load_release_scope(config_path)


def test_build_release_tree_full_mirrors_partition_selection(tmp_path: Path) -> None:
    out = tmp_path / "full-tree"
    manifest = build_release_tree("full", PROJECT_ROOT, out)
    mset = set(manifest)

    # Ships code/docs/ADRs/tests/config:
    assert any(m.startswith("src/") for m in mset)
    assert any(m.startswith("project-brain/decisions/adrs/") for m in mset)
    assert any(m.startswith("tests/") for m in mset)
    # Withholds internal specs + artifacts:
    assert not any(m.startswith("docs/superpowers/") for m in mset)
    assert not any("__pycache__" in m for m in mset)

    # Manifest equals the partition selector (published == scanned):
    from src.lib.partition_integrity import public_release_files, load_policy

    expected = public_release_files(PROJECT_ROOT, load_policy(PROJECT_ROOT / "config/system/partition_policy.yaml"))
    assert sorted(manifest) == sorted(expected)

    # Every manifested file was actually copied to the output tree:
    for rel in manifest:
        assert (out / rel).is_file(), f"missing copied file: {rel}"
