"""Unit tests for src.lib.staged_skill_catalog.

Covers the live/staged skill discovery and lookup surface:
  - is_staging_payload_path
  - iter_live_skill_dirs (dedup, ordering, SKILL.md gating)
  - iter_staged_skill_dirs (release filtering, multi-release aggregation, sort)
  - iter_all_release_skill_dirs
  - find_skill_dir (live precedence, vault fallback, staged fallback)
  - find_skill_file

Path roots are isolated under tmp_path. ``get_project_brain_skills_dir``
derives from the passed ``project_root`` (so a tmp project tree works without
patching), while the vault skills root and vault staging root are global
helpers that are monkeypatched onto both the module-level import and
``src.config.paths`` (find_skill_dir re-imports paths lazily for staging).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.lib import staged_skill_catalog as catalog
from src.lib.porting_payload import STAGED_RELEASES


def _make_skill(root: Path, name: str, *, with_skill_md: bool = True) -> Path:
    """Create a skill directory; optionally without SKILL.md to test gating."""
    skill_dir = root / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    if with_skill_md:
        (skill_dir / "SKILL.md").write_text(f"# {name}\n", encoding="utf-8")
    return skill_dir


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    """A project root whose live skills live under project-brain/capabilities/skills."""
    root = tmp_path / "repo"
    root.mkdir()
    return root


@pytest.fixture
def live_skills_root(project_root: Path) -> Path:
    root = catalog.get_project_brain_skills_dir(project_root)
    root.mkdir(parents=True, exist_ok=True)
    return root


@pytest.fixture
def vault_skills_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "vault" / "capabilities" / "skills"
    root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(catalog, "get_vault_skills_dir", lambda: root)
    return root


@pytest.fixture
def staging_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The drafts/staging root. Patched on the module import AND on src.config.paths.

    iter_staged_skill_dirs uses the module-level import; find_skill_dir's staging
    block lazily re-imports ``src.config.paths`` — both must resolve to tmp.
    """
    root = tmp_path / "vault" / "drafts" / "staging"
    root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(catalog, "get_vault_staging_dir", lambda: root)
    from src.config import paths as _paths

    monkeypatch.setattr(_paths, "get_vault_staging_dir", lambda: root)
    return root


# ---------------------------------------------------------------------------
# is_staging_payload_path
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("staging", True),
        ("staging/", True),
        ("staging/r1/skills/apple", True),
        ("/staging", True),  # leading slash is stripped
        ("/staging/r1", True),
        ("stagingx", False),  # prefix must be the segment "staging", not a substring
        ("staging-area/x", False),
        ("drafts/staging", False),  # staging must be the first segment
        ("skills/staging", False),
        ("", False),
    ],
)
def test_is_staging_payload_path(raw: str, expected: bool) -> None:
    assert catalog.is_staging_payload_path(Path(raw)) is expected


# ---------------------------------------------------------------------------
# iter_live_skill_dirs
# ---------------------------------------------------------------------------


def test_iter_live_skill_dirs_returns_only_dirs_with_skill_md(project_root: Path, live_skills_root: Path) -> None:
    _make_skill(live_skills_root, "apple")
    _make_skill(live_skills_root, "books")
    # A directory without SKILL.md must be excluded.
    _make_skill(live_skills_root, "no-manifest", with_skill_md=False)
    # A stray file (not a directory) must be ignored.
    (live_skills_root / "README.md").write_text("not a skill", encoding="utf-8")

    dirs = catalog.iter_live_skill_dirs(project_root)

    assert [d.name for d in dirs] == ["apple", "books"]
    assert all(d.is_dir() for d in dirs)


def test_iter_live_skill_dirs_empty_when_root_missing(project_root: Path) -> None:
    # No project-brain skills dir created at all.
    assert catalog.iter_live_skill_dirs(project_root) == []


def test_iter_live_skill_dirs_is_sorted(project_root: Path, live_skills_root: Path) -> None:
    for name in ("zebra", "alpha", "mango"):
        _make_skill(live_skills_root, name)

    names = [d.name for d in catalog.iter_live_skill_dirs(project_root)]

    assert names == ["alpha", "mango", "zebra"]


# ---------------------------------------------------------------------------
# iter_staged_skill_dirs
# ---------------------------------------------------------------------------


def test_iter_staged_skill_dirs_specific_release(project_root: Path, staging_root: Path) -> None:
    _make_skill(staging_root / "r1" / "skills", "apple")
    _make_skill(staging_root / "r1" / "skills", "books")
    _make_skill(staging_root / "r2" / "skills", "later-skill")

    dirs = catalog.iter_staged_skill_dirs(project_root, release="r1")

    assert [d.name for d in dirs] == ["apple", "books"]
    assert all("r1" in d.as_posix() for d in dirs)


def test_iter_staged_skill_dirs_unknown_release_is_empty(project_root: Path, staging_root: Path) -> None:
    _make_skill(staging_root / "r1" / "skills", "apple")

    # A release that exists in STAGED_RELEASES but has no payload on disk.
    assert catalog.iter_staged_skill_dirs(project_root, release="later") == []
    # A release tag that is not on disk at all.
    assert catalog.iter_staged_skill_dirs(project_root, release="does-not-exist") == []


def test_iter_staged_skill_dirs_aggregates_all_known_releases(project_root: Path, staging_root: Path) -> None:
    # Spread skills across two known staged releases.
    _make_skill(staging_root / "r1" / "skills", "file-manager")
    _make_skill(staging_root / "r2" / "skills", "apple")
    # A release tag that is NOT in STAGED_RELEASES must be ignored when aggregating.
    _make_skill(staging_root / "mvp" / "skills", "ignored")

    dirs = catalog.iter_staged_skill_dirs(project_root)
    names = [d.name for d in dirs]

    assert "file-manager" in names
    assert "apple" in names
    assert "ignored" not in names
    # Result is sorted by full path.
    assert dirs == sorted(dirs)


def test_iter_staged_skill_dirs_only_iterates_known_releases() -> None:
    # Guard the contract: STAGED_RELEASES drives the default aggregation.
    assert set(STAGED_RELEASES) >= {"r1", "r2"}


# ---------------------------------------------------------------------------
# iter_all_release_skill_dirs
# ---------------------------------------------------------------------------


def test_iter_all_release_skill_dirs_combines_live_and_staged(
    project_root: Path, live_skills_root: Path, staging_root: Path
) -> None:
    _make_skill(live_skills_root, "live-skill")
    _make_skill(staging_root / "r1" / "skills", "staged-skill")

    dirs = catalog.iter_all_release_skill_dirs(project_root)
    names = [d.name for d in dirs]

    assert "live-skill" in names
    assert "staged-skill" in names
    # Combined result is sorted.
    assert dirs == sorted(dirs)


# ---------------------------------------------------------------------------
# find_skill_dir
# ---------------------------------------------------------------------------


def test_find_skill_dir_prefers_live_repo_over_vault_and_staging(
    project_root: Path,
    live_skills_root: Path,
    vault_skills_root: Path,
    staging_root: Path,
) -> None:
    live = _make_skill(live_skills_root, "apple")
    _make_skill(vault_skills_root, "apple")
    _make_skill(staging_root / "r1" / "skills", "apple")

    found = catalog.find_skill_dir(project_root, "apple")

    assert found == live


def test_find_skill_dir_falls_back_to_vault(
    project_root: Path,
    live_skills_root: Path,
    vault_skills_root: Path,
    staging_root: Path,
) -> None:
    vault = _make_skill(vault_skills_root, "private-skill")

    found = catalog.find_skill_dir(project_root, "private-skill")

    assert found == vault


def test_find_skill_dir_falls_back_to_staged(
    project_root: Path,
    live_skills_root: Path,
    vault_skills_root: Path,
    staging_root: Path,
) -> None:
    # Only present in a staged release (the regression this fallback restored).
    staged = _make_skill(staging_root / "r2" / "skills", "books")

    found = catalog.find_skill_dir(project_root, "books")

    assert found == staged


def test_find_skill_dir_returns_none_when_absent(
    project_root: Path,
    live_skills_root: Path,
    vault_skills_root: Path,
    staging_root: Path,
) -> None:
    assert catalog.find_skill_dir(project_root, "ghost") is None


def test_find_skill_dir_requires_skill_md_marker(
    project_root: Path,
    live_skills_root: Path,
    vault_skills_root: Path,
    staging_root: Path,
) -> None:
    # Directory exists in every root but has no SKILL.md anywhere -> None.
    _make_skill(live_skills_root, "hollow", with_skill_md=False)
    _make_skill(vault_skills_root, "hollow", with_skill_md=False)
    _make_skill(staging_root / "r1" / "skills", "hollow", with_skill_md=False)

    assert catalog.find_skill_dir(project_root, "hollow") is None


# ---------------------------------------------------------------------------
# find_skill_file
# ---------------------------------------------------------------------------


def test_find_skill_file_returns_existing_nested_file(
    project_root: Path,
    live_skills_root: Path,
) -> None:
    skill = _make_skill(live_skills_root, "apple")
    nested = skill / "lib" / "notes.py"
    nested.parent.mkdir(parents=True)
    nested.write_text("# notes\n", encoding="utf-8")

    found = catalog.find_skill_file(project_root, "apple", "lib", "notes.py")

    assert found == nested


def test_find_skill_file_returns_skill_md_at_root(
    project_root: Path,
    live_skills_root: Path,
) -> None:
    skill = _make_skill(live_skills_root, "apple")

    found = catalog.find_skill_file(project_root, "apple", "SKILL.md")

    assert found == skill / "SKILL.md"


def test_find_skill_file_none_when_file_missing(
    project_root: Path,
    live_skills_root: Path,
) -> None:
    _make_skill(live_skills_root, "apple")

    assert catalog.find_skill_file(project_root, "apple", "does", "not", "exist.py") is None


def test_find_skill_file_none_when_skill_missing(
    project_root: Path,
    live_skills_root: Path,
    vault_skills_root: Path,
    staging_root: Path,
) -> None:
    assert catalog.find_skill_file(project_root, "ghost", "SKILL.md") is None


def test_find_skill_file_resolves_against_staged_skill(
    project_root: Path,
    live_skills_root: Path,
    vault_skills_root: Path,
    staging_root: Path,
) -> None:
    # File lookup must follow find_skill_dir's staged fallback.
    staged = _make_skill(staging_root / "r3" / "skills", "file-manager")
    asset = staged / "data" / "config.yaml"
    asset.parent.mkdir(parents=True)
    asset.write_text("k: v\n", encoding="utf-8")

    found = catalog.find_skill_file(project_root, "file-manager", "data", "config.yaml")

    assert found == asset
