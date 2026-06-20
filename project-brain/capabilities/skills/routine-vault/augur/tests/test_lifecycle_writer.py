"""Tests for atomic .augur-lifecycle.yaml writer."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
import yaml

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
_LW_PATH = _SCRIPTS / "lifecycle_writer.py"

_spec = importlib.util.spec_from_file_location("lifecycle_writer_under_test", _LW_PATH)
assert _spec and _spec.loader
lw = importlib.util.module_from_spec(_spec)
sys.modules["lifecycle_writer_under_test"] = lw
_spec.loader.exec_module(lw)


def test_append_known_group_creates_new_yaml(tmp_path):
    entry = {
        "name": "g1",
        "canonical_strategy": "highest_version",
        "pattern": "a-*.zip",
        "decided_at": "2026-05-12T14:30:00Z",
        "decided_by": "gsannikov",
    }
    lw.append_known_group(tmp_path, entry)
    data = yaml.safe_load((tmp_path / ".augur-lifecycle.yaml").read_text())
    assert data["known_groups"][0]["name"] == "g1"
    assert data["known_groups"][0]["canonical_strategy"] == "highest_version"


def test_append_known_group_appends_to_existing_yaml(tmp_path):
    (tmp_path / ".augur-lifecycle.yaml").write_text(
        "enabled: true\n"
        "pattern_hints: ['a-*.zip']\n"
        "known_groups:\n"
        "  - name: existing\n"
        "    canonical_strategy: highest_version\n"
        "    pattern: 'x-*.zip'\n"
    )
    entry = {"name": "new", "canonical_strategy": "not_a_group", "members": ["a.png", "b.png"]}
    lw.append_known_group(tmp_path, entry)
    data = yaml.safe_load((tmp_path / ".augur-lifecycle.yaml").read_text())
    assert data["enabled"] is True
    assert data["pattern_hints"] == ["a-*.zip"]
    assert len(data["known_groups"]) == 2
    assert data["known_groups"][1]["name"] == "new"


def test_append_known_group_collision_raises(tmp_path):
    (tmp_path / ".augur-lifecycle.yaml").write_text(
        "known_groups:\n"
        "  - name: dup\n"
        "    canonical_strategy: highest_version\n"
        "    pattern: 'x-*.zip'\n"
    )
    with pytest.raises(lw.LifecycleWriterCollision, match="dup"):
        lw.append_known_group(
            tmp_path,
            {"name": "dup", "canonical_strategy": "not_a_group", "members": ["a"]},
        )


def test_append_known_group_missing_name_raises(tmp_path):
    with pytest.raises(lw.LifecycleWriterError, match="name"):
        lw.append_known_group(tmp_path, {"canonical_strategy": "highest_version"})


def test_append_known_group_atomic_no_tempfile_left(tmp_path):
    lw.append_known_group(
        tmp_path,
        {"name": "g", "canonical_strategy": "highest_version", "pattern": "x-*"},
    )
    assert not (tmp_path / ".augur-lifecycle.yaml.tmp").exists()
    assert (tmp_path / ".augur-lifecycle.yaml").exists()


def test_append_known_group_malformed_existing_raises(tmp_path):
    (tmp_path / ".augur-lifecycle.yaml").write_text("not: valid: yaml: :")
    with pytest.raises(lw.LifecycleWriterError, match="malformed"):
        lw.append_known_group(
            tmp_path,
            {"name": "g", "canonical_strategy": "highest_version", "pattern": "x-*"},
        )
