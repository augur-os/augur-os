"""Tests for .augur-lifecycle.yaml and .milestones.json readers."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "lifecycle_config.py"
_SPEC = importlib.util.spec_from_file_location("lifecycle_config_under_test", _MODULE_PATH)
assert _SPEC and _SPEC.loader
mod = importlib.util.module_from_spec(_SPEC)
sys.modules["lifecycle_config_under_test"] = mod
_SPEC.loader.exec_module(mod)


def test_read_lifecycle_config_absent_returns_none(tmp_path):
    assert mod.read_lifecycle_config(tmp_path) is None


def test_read_lifecycle_config_minimal(tmp_path):
    (tmp_path / ".augur-lifecycle.yaml").write_text("enabled: true\n")
    cfg = mod.read_lifecycle_config(tmp_path)
    assert cfg is not None
    assert cfg.enabled is True
    assert cfg.pattern_hints == []
    assert cfg.keep_latest is None
    assert cfg.deploy_root is False
    assert cfg.notes is None


def test_read_lifecycle_config_full(tmp_path):
    (tmp_path / ".augur-lifecycle.yaml").write_text(
        "enabled: true\n"
        "pattern_hints:\n  - 'guriqo-com-V*.zip'\n  - 'augur-run-V*.zip'\n"
        "keep_latest: 1\n"
        "deploy_root: true\n"
        "notes: 'prod website builds'\n"
    )
    cfg = mod.read_lifecycle_config(tmp_path)
    assert cfg.enabled is True
    assert cfg.pattern_hints == ["guriqo-com-V*.zip", "augur-run-V*.zip"]
    assert cfg.keep_latest == 1
    assert cfg.deploy_root is True
    assert cfg.notes == "prod website builds"


def test_read_lifecycle_config_known_groups_highest_version(tmp_path):
    (tmp_path / ".augur-lifecycle.yaml").write_text(
        "enabled: true\n"
        "known_groups:\n"
        "  - name: guriqo-com-build\n"
        "    canonical_strategy: highest_version\n"
        "    pattern: 'guriqo-com-*.zip'\n"
        "    decided_at: '2026-05-12T14:30:00Z'\n"
        "    decided_by: gsannikov\n"
        "    note: 'older scheme stale'\n"
    )
    cfg = mod.read_lifecycle_config(tmp_path)
    assert len(cfg.known_groups) == 1
    g = cfg.known_groups[0]
    assert g.name == "guriqo-com-build"
    assert g.canonical_strategy == "highest_version"
    assert g.pattern == "guriqo-com-*.zip"
    assert g.members is None
    assert g.canonical is None
    assert g.decided_at == "2026-05-12T14:30:00Z"
    assert g.decided_by == "gsannikov"
    assert g.note == "older scheme stale"


def test_read_lifecycle_config_known_groups_explicit(tmp_path):
    (tmp_path / ".augur-lifecycle.yaml").write_text(
        "known_groups:\n"
        "  - name: form-answers\n"
        "    canonical_strategy: explicit\n"
        "    members: ['augur-intel-form-answers.md', 'final-form-answers.md']\n"
        "    canonical: final-form-answers.md\n"
    )
    cfg = mod.read_lifecycle_config(tmp_path)
    g = cfg.known_groups[0]
    assert g.canonical_strategy == "explicit"
    assert g.members == ("augur-intel-form-answers.md", "final-form-answers.md")
    assert g.canonical == "final-form-answers.md"


def test_read_lifecycle_config_known_groups_not_a_group(tmp_path):
    (tmp_path / ".augur-lifecycle.yaml").write_text(
        "known_groups:\n"
        "  - name: linkedin-banner-personal\n"
        "    canonical_strategy: not_a_group\n"
        "    members: ['linkedin-banner-personal.png', 'linkedin-banner-personal-augur.png']\n"
    )
    cfg = mod.read_lifecycle_config(tmp_path)
    g = cfg.known_groups[0]
    assert g.canonical_strategy == "not_a_group"
    assert g.members == ("linkedin-banner-personal.png", "linkedin-banner-personal-augur.png")
    assert g.canonical is None


def test_read_lifecycle_config_known_groups_invalid_strategy_raises(tmp_path):
    (tmp_path / ".augur-lifecycle.yaml").write_text(
        "known_groups:\n"
        "  - name: x\n"
        "    canonical_strategy: bogus\n"
    )
    with pytest.raises(mod.LifecycleConfigError, match="canonical_strategy"):
        mod.read_lifecycle_config(tmp_path)


def test_read_lifecycle_config_known_groups_missing_pattern_raises(tmp_path):
    (tmp_path / ".augur-lifecycle.yaml").write_text(
        "known_groups:\n"
        "  - name: x\n"
        "    canonical_strategy: highest_version\n"
    )
    with pytest.raises(mod.LifecycleConfigError, match="requires 'pattern'"):
        mod.read_lifecycle_config(tmp_path)


def test_read_lifecycle_config_known_groups_missing_canonical_raises(tmp_path):
    (tmp_path / ".augur-lifecycle.yaml").write_text(
        "known_groups:\n"
        "  - name: x\n"
        "    canonical_strategy: explicit\n"
        "    members: ['a.md']\n"
    )
    with pytest.raises(mod.LifecycleConfigError, match="requires 'canonical'"):
        mod.read_lifecycle_config(tmp_path)


def test_read_lifecycle_config_known_groups_missing_members_raises(tmp_path):
    (tmp_path / ".augur-lifecycle.yaml").write_text(
        "known_groups:\n"
        "  - name: x\n"
        "    canonical_strategy: not_a_group\n"
    )
    with pytest.raises(mod.LifecycleConfigError, match="requires 'members'"):
        mod.read_lifecycle_config(tmp_path)


def test_read_lifecycle_config_known_groups_absent_returns_empty_tuple(tmp_path):
    (tmp_path / ".augur-lifecycle.yaml").write_text("enabled: true\n")
    cfg = mod.read_lifecycle_config(tmp_path)
    assert cfg.known_groups == ()


def test_read_lifecycle_config_malformed_yaml_raises(tmp_path):
    (tmp_path / ".augur-lifecycle.yaml").write_text("enabled: : invalid\n")
    with pytest.raises(mod.LifecycleConfigError, match="parse"):
        mod.read_lifecycle_config(tmp_path)


def test_read_lifecycle_config_wrong_type_raises(tmp_path):
    (tmp_path / ".augur-lifecycle.yaml").write_text("enabled: 'not-a-bool'\n")
    with pytest.raises(mod.LifecycleConfigError, match="enabled"):
        mod.read_lifecycle_config(tmp_path)


def test_read_milestones_absent_returns_empty(tmp_path):
    assert mod.read_milestones(tmp_path) == []


def test_read_milestones_valid(tmp_path):
    payload = {
        "websites/guriqo-com-V10025.zip": {
            "tag": "intel-submission",
            "tagged_at": "2026-04-25T10:00:00Z",
            "note": "sent to Intel",
        }
    }
    (tmp_path / ".milestones.json").write_text(json.dumps(payload))
    pins = mod.read_milestones(tmp_path)
    assert len(pins) == 1
    assert pins[0].relative_path == "websites/guriqo-com-V10025.zip"
    assert pins[0].tag == "intel-submission"
    assert pins[0].tagged_at == "2026-04-25T10:00:00Z"
    assert pins[0].note == "sent to Intel"


def test_read_milestones_malformed_json_raises(tmp_path):
    (tmp_path / ".milestones.json").write_text("{not-json")
    with pytest.raises(mod.LifecycleConfigError, match="parse"):
        mod.read_milestones(tmp_path)


def test_read_milestones_missing_tag_raises(tmp_path):
    payload = {"websites/x.zip": {"tagged_at": "2026-04-25T10:00:00Z"}}
    (tmp_path / ".milestones.json").write_text(json.dumps(payload))
    with pytest.raises(mod.LifecycleConfigError, match="tag"):
        mod.read_milestones(tmp_path)
