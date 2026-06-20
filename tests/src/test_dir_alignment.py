"""Tests for src/lib/dir_alignment.py."""

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _clear_skill_cache():
    from src.lib.dir_alignment import get_skill_names

    get_skill_names.cache_clear()
    yield
    get_skill_names.cache_clear()


@pytest.fixture()
def skills_dir(tmp_path: Path) -> Path:
    """Create a mock skills/ directory with known skill names."""
    sd = tmp_path / "skills"
    sd.mkdir()
    for name in ["career", "finance", "consulting-template", "auto-lint", "health"]:
        (sd / name).mkdir()
    return sd


@pytest.fixture()
def location_with_reserved(tmp_path: Path) -> Path:
    """Create a managed location with a .augur-reserved file."""
    loc = tmp_path / "vault"
    loc.mkdir()
    reserved = loc / ".augur-reserved"
    reserved.write_text("# Reserved\nconfig\ndev\nmemory\n")
    return loc


# --- get_reserved_names ---


def test_get_reserved_names_parses_file(location_with_reserved: Path):
    from src.lib.dir_alignment import ManagedLocation, get_reserved_names

    ml = ManagedLocation(path=location_with_reserved)
    result = get_reserved_names(ml)
    assert result == {"config", "dev", "memory"}


def test_get_reserved_names_returns_empty_when_missing(tmp_path: Path):
    from src.lib.dir_alignment import ManagedLocation, get_reserved_names

    ml = ManagedLocation(path=tmp_path / "nonexistent")
    result = get_reserved_names(ml)
    assert result == set()


def test_get_reserved_names_ignores_comments_and_blanks(tmp_path: Path):
    loc = tmp_path / "loc"
    loc.mkdir()
    (loc / ".augur-reserved").write_text("# comment\n\nfoo\n  \nbar\n# another\n")
    from src.lib.dir_alignment import ManagedLocation, get_reserved_names

    result = get_reserved_names(ManagedLocation(path=loc))
    assert result == {"foo", "bar"}


# --- get_skill_names ---


def test_get_skill_names_lists_skills_dir(skills_dir: Path, monkeypatch):
    from src.lib import dir_alignment

    monkeypatch.setattr(dir_alignment, "_get_all_client_skill_dirs", lambda: [skills_dir])
    result = dir_alignment.get_skill_names()
    assert "career" in result
    assert "consulting-template" in result
    assert len(result) == 5


# --- validate_dir_name ---


def test_validate_allows_skill_name(skills_dir: Path, location_with_reserved: Path, monkeypatch):
    from src.lib import dir_alignment

    monkeypatch.setattr(dir_alignment, "_get_all_client_skill_dirs", lambda: [skills_dir])
    ml = dir_alignment.ManagedLocation(path=location_with_reserved)
    assert dir_alignment.validate_dir_name(ml, "career") is True


def test_validate_allows_reserved_name(skills_dir: Path, location_with_reserved: Path, monkeypatch):
    from src.lib import dir_alignment

    monkeypatch.setattr(dir_alignment, "_get_all_client_skill_dirs", lambda: [skills_dir])
    ml = dir_alignment.ManagedLocation(path=location_with_reserved)
    assert dir_alignment.validate_dir_name(ml, "config") is True


def test_validate_rejects_unknown_name(skills_dir: Path, location_with_reserved: Path, monkeypatch):
    from src.lib import dir_alignment

    monkeypatch.setattr(dir_alignment, "_get_all_client_skill_dirs", lambda: [skills_dir])
    ml = dir_alignment.ManagedLocation(path=location_with_reserved)
    assert dir_alignment.validate_dir_name(ml, "random-junk") is False


# --- find_closest_skill ---


def test_find_closest_skill_matches_above_threshold(skills_dir: Path, monkeypatch):
    from src.lib import dir_alignment

    monkeypatch.setattr(dir_alignment, "_get_all_client_skill_dirs", lambda: [skills_dir])
    result = dir_alignment.find_closest_skill("consulting")
    assert result is not None
    name, score = result
    assert name == "consulting-template"
    assert score >= 0.85


def test_find_closest_skill_returns_none_below_threshold(skills_dir: Path, monkeypatch):
    from src.lib import dir_alignment

    monkeypatch.setattr(dir_alignment, "_get_all_client_skill_dirs", lambda: [skills_dir])
    result = dir_alignment.find_closest_skill("zzz-nothing-close")
    assert result is None


# --- classify_violation ---


def test_classify_trivial_rename(skills_dir: Path, tmp_path: Path, monkeypatch):
    from src.lib import dir_alignment

    monkeypatch.setattr(dir_alignment, "_get_all_client_skill_dirs", lambda: [skills_dir])
    loc = tmp_path / "docs"
    loc.mkdir()
    (loc / "consulting").mkdir()
    ml = dir_alignment.ManagedLocation(path=loc)
    result = dir_alignment.classify_violation(ml, "consulting")
    assert result == "trivial-rename"


def test_classify_new_skill_candidate(skills_dir: Path, tmp_path: Path, monkeypatch):
    from src.lib import dir_alignment

    monkeypatch.setattr(dir_alignment, "_get_all_client_skill_dirs", lambda: [skills_dir])
    loc = tmp_path / "vault"
    loc.mkdir()
    big_dir = loc / "my-project"
    big_dir.mkdir()
    (big_dir / "file1.md").touch()
    (big_dir / "file2.md").touch()
    (big_dir / "file3.md").touch()
    ml = dir_alignment.ManagedLocation(path=loc)
    result = dir_alignment.classify_violation(ml, "my-project")
    assert result == "new-skill-candidate"


def test_classify_unknown(skills_dir: Path, tmp_path: Path, monkeypatch):
    from src.lib import dir_alignment

    monkeypatch.setattr(dir_alignment, "_get_all_client_skill_dirs", lambda: [skills_dir])
    loc = tmp_path / "vault"
    loc.mkdir()
    small_dir = loc / "random"
    small_dir.mkdir()
    (small_dir / "note.txt").touch()
    ml = dir_alignment.ManagedLocation(path=loc)
    result = dir_alignment.classify_violation(ml, "random")
    assert result == "unknown"


# --- brain-root awareness (ADR-771 skeleton + Augur runtime dirs) ---


def _make_brain_root(tmp_path: Path) -> Path:
    loc = tmp_path / "brain"
    loc.mkdir()
    (loc / "BRAIN.yaml").write_text("schema_version: 1\n")
    return loc


def test_validate_allows_brain_skeleton_dir(tmp_path: Path, monkeypatch):
    from src.lib import dir_alignment

    monkeypatch.setattr(dir_alignment, "_get_all_client_skill_dirs", lambda: [])
    dir_alignment.get_skill_names.cache_clear()
    ml = dir_alignment.ManagedLocation(path=_make_brain_root(tmp_path))
    for name in ("capabilities", "knowledge", "decisions", "config"):
        assert dir_alignment.validate_dir_name(ml, name) is True, name


def test_validate_allows_augur_runtime_dirs_in_brain(tmp_path: Path, monkeypatch):
    from src.lib import dir_alignment

    monkeypatch.setattr(dir_alignment, "_get_all_client_skill_dirs", lambda: [])
    dir_alignment.get_skill_names.cache_clear()
    ml = dir_alignment.ManagedLocation(path=_make_brain_root(tmp_path))
    for name in ("system", "integrations", "prompts"):
        assert dir_alignment.validate_dir_name(ml, name) is True, name


def test_validate_rejects_skeleton_dir_outside_brain_root(tmp_path: Path, monkeypatch):
    """Without BRAIN.yaml, skeleton/runtime names get no special treatment."""
    from src.lib import dir_alignment

    monkeypatch.setattr(dir_alignment, "_get_all_client_skill_dirs", lambda: [])
    dir_alignment.get_skill_names.cache_clear()
    loc = tmp_path / "plain"
    loc.mkdir()
    ml = dir_alignment.ManagedLocation(path=loc)
    assert dir_alignment.validate_dir_name(ml, "capabilities") is False
    assert dir_alignment.validate_dir_name(ml, "system") is False
