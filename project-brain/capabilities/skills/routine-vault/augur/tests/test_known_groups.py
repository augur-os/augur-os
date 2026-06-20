"""Tests for cached known_groups matching."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
_LC_PATH = _SCRIPTS / "lifecycle_config.py"
_KG_PATH = _SCRIPTS / "known_groups.py"

_lc_spec = importlib.util.spec_from_file_location("lifecycle_config_under_test", _LC_PATH)
assert _lc_spec and _lc_spec.loader
lc = importlib.util.module_from_spec(_lc_spec)
sys.modules["lifecycle_config_under_test"] = lc
_lc_spec.loader.exec_module(lc)

_kg_spec = importlib.util.spec_from_file_location("known_groups_under_test", _KG_PATH)
assert _kg_spec and _kg_spec.loader
kg = importlib.util.module_from_spec(_kg_spec)
sys.modules["known_groups_under_test"] = kg
_kg_spec.loader.exec_module(kg)


def _files(*names):
    return [
        {
            "name": name,
            "relative_path": f"foo/{name}",
            "size_bytes": 1,
            "mtime_iso": "2026-01-01T00:00:00Z",
        }
        for name in names
    ]


def test_match_known_groups_highest_version_picks_highest(tmp_path):
    files = _files("guriqo-com-V10001.zip", "guriqo-com-V10002.zip", "guriqo-com-V10032.zip")
    group = lc.KnownGroup(
        name="guriqo-com-build",
        canonical_strategy="highest_version",
        pattern="guriqo-com-*.zip",
    )
    result = kg.match_known_groups(files, [group])
    assert result.moves_by_group["guriqo-com-build"] == [
        "foo/guriqo-com-V10001.zip",
        "foo/guriqo-com-V10002.zip",
    ]
    assert result.no_touch == set()
    assert result.unmatched_files == []


def test_match_known_groups_explicit_keeps_canonical(tmp_path):
    files = _files("augur-intel-form-answers.md", "final-form-answers.md", "unrelated.md")
    group = lc.KnownGroup(
        name="form-answers",
        canonical_strategy="explicit",
        members=("augur-intel-form-answers.md", "final-form-answers.md"),
        canonical="final-form-answers.md",
    )
    result = kg.match_known_groups(files, [group])
    assert result.moves_by_group["form-answers"] == ["foo/augur-intel-form-answers.md"]
    assert result.no_touch == set()
    assert [f["name"] for f in result.unmatched_files] == ["unrelated.md"]


def test_match_known_groups_not_a_group_no_moves(tmp_path):
    files = _files("linkedin-banner-personal.png", "linkedin-banner-personal-augur.png")
    group = lc.KnownGroup(
        name="linkedin-banner-personal",
        canonical_strategy="not_a_group",
        members=("linkedin-banner-personal.png", "linkedin-banner-personal-augur.png"),
    )
    result = kg.match_known_groups(files, [group])
    assert result.moves_by_group == {}
    assert result.no_touch == {
        "foo/linkedin-banner-personal.png",
        "foo/linkedin-banner-personal-augur.png",
    }
    assert result.unmatched_files == []


def test_match_known_groups_no_matches_returns_all_unmatched(tmp_path):
    files = _files("a.md", "b.md")
    group = lc.KnownGroup(
        name="x",
        canonical_strategy="highest_version",
        pattern="nonmatching-*.zip",
    )
    result = kg.match_known_groups(files, [group])
    assert result.moves_by_group == {}
    assert len(result.unmatched_files) == 2


def test_match_known_groups_version_sort_handles_mixed_schemes(tmp_path):
    files = _files(
        "guriqo-com-v33-1.zip",
        "guriqo-com-v45-1.zip",
        "guriqo-com-V10001.zip",
        "guriqo-com-V10032.zip",
    )
    group = lc.KnownGroup(
        name="g",
        canonical_strategy="highest_version",
        pattern="guriqo-com-*.zip",
    )
    result = kg.match_known_groups(files, [group])
    archived = result.moves_by_group["g"]
    assert "foo/guriqo-com-V10032.zip" not in archived
    assert len(archived) == 3
