"""Unit tests for DataResult helper (TDD — module does not exist yet).

Tests cover vault-first loading with seed fallback, all vault_status values,
loader variants (yaml, json, collection), and default passthrough.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from src.lib.data_result import DataResult, read_skill_data

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def skill_tree(tmp_path: Path) -> dict[str, Path]:
    """Build a minimal skill directory structure under tmp_path.

    Returns a dict with keys:
      - skill_root: tmp_path/skills/test-skill/
      - caller_file: tmp_path/skills/test-skill/scripts/mcp/tools.py
      - seeds_dir:   tmp_path/skills/test-skill/assets/seeds/
      - vault_dir:   tmp_path/vault/test-skill/
    """
    skill_root = tmp_path / "skills" / "test-skill"
    caller_file = skill_root / "scripts" / "mcp" / "tools.py"
    caller_file.parent.mkdir(parents=True, exist_ok=True)
    caller_file.write_text("# stub caller\n", encoding="utf-8")

    seeds_dir = skill_root / "assets" / "seeds"
    seeds_dir.mkdir(parents=True, exist_ok=True)

    vault_dir = tmp_path / "vault" / "test-skill"
    # vault_dir is NOT created here — tests that need it create it themselves

    return {
        "skill_root": skill_root,
        "caller_file": caller_file,
        "seeds_dir": seeds_dir,
        "vault_dir": vault_dir,
    }


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _mock_paths(skill_tree: dict[str, Path]):
    """Return a context manager pair that patches get_own_data_dir and
    _find_skill_root to use the tmp_path-based skill tree."""
    vault_dir = skill_tree["vault_dir"]
    skill_root = skill_tree["skill_root"]

    vault_patch = patch(
        "src.lib.data_result.get_own_data_dir",
        return_value=vault_dir,
    )
    root_patch = patch(
        "src.lib.data_result._find_skill_root",
        return_value=skill_root,
    )
    return vault_patch, root_patch


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDataResult:
    def test_vault_ok(self, skill_tree):
        """Vault file exists with data → source='vault', vault_status='ok'."""
        vault_dir = skill_tree["vault_dir"]
        vault_dir.mkdir(parents=True, exist_ok=True)
        data_file = vault_dir / "items.yaml"
        data_file.write_text("- name: alpha\n- name: beta\n", encoding="utf-8")

        caller = skill_tree["caller_file"]
        vault_patch, root_patch = _mock_paths(skill_tree)
        with vault_patch, root_patch:
            result = read_skill_data(caller, "items.yaml", default=[])

        assert isinstance(result, DataResult)
        assert result.source == "vault"
        assert result.vault_status == "ok"
        assert result.data == [{"name": "alpha"}, {"name": "beta"}]
        assert result.vault_path == vault_dir / "items.yaml"

    def test_vault_missing_dir_falls_to_seed(self, skill_tree):
        """Vault dir does not exist → falls back to seed, vault_status='missing_dir'."""
        seeds_dir = skill_tree["seeds_dir"]
        seed_file = seeds_dir / "items.yaml"
        seed_file.write_text("- name: seed-alpha\n", encoding="utf-8")

        caller = skill_tree["caller_file"]
        vault_patch, root_patch = _mock_paths(skill_tree)
        with vault_patch, root_patch:
            result = read_skill_data(caller, "items.yaml", default=[])

        assert result.source == "seed"
        assert result.vault_status == "missing_dir"
        assert result.data == [{"name": "seed-alpha"}]
        assert result.seed_path == seeds_dir / "items.yaml"

    def test_vault_no_file_falls_to_seed(self, skill_tree):
        """Vault dir exists but file is absent → falls back to seed, vault_status='no_file'."""
        vault_dir = skill_tree["vault_dir"]
        vault_dir.mkdir(parents=True, exist_ok=True)
        # no items.yaml in vault

        seeds_dir = skill_tree["seeds_dir"]
        (seeds_dir / "items.yaml").write_text("- name: seed-beta\n", encoding="utf-8")

        caller = skill_tree["caller_file"]
        vault_patch, root_patch = _mock_paths(skill_tree)
        with vault_patch, root_patch:
            result = read_skill_data(caller, "items.yaml", default=[])

        assert result.source == "seed"
        assert result.vault_status == "no_file"
        assert result.data == [{"name": "seed-beta"}]

    def test_vault_empty_file_falls_to_seed(self, skill_tree):
        """Vault file exists but is empty → falls back to seed, vault_status='empty_file'."""
        vault_dir = skill_tree["vault_dir"]
        vault_dir.mkdir(parents=True, exist_ok=True)
        (vault_dir / "items.yaml").write_text("", encoding="utf-8")

        seeds_dir = skill_tree["seeds_dir"]
        (seeds_dir / "items.yaml").write_text("- name: seed-gamma\n", encoding="utf-8")

        caller = skill_tree["caller_file"]
        vault_patch, root_patch = _mock_paths(skill_tree)
        with vault_patch, root_patch:
            result = read_skill_data(caller, "items.yaml", default=[])

        assert result.source == "seed"
        assert result.vault_status == "empty_file"
        assert result.data == [{"name": "seed-gamma"}]

    def test_no_seed_returns_default(self, skill_tree):
        """No vault, no seed file → source='default', data=default value."""
        caller = skill_tree["caller_file"]
        vault_patch, root_patch = _mock_paths(skill_tree)
        with vault_patch, root_patch:
            result = read_skill_data(caller, "items.yaml", default={"fallback": True})

        assert result.source == "default"
        assert result.data == {"fallback": True}

    def test_vault_takes_priority_over_seed(self, skill_tree):
        """Both vault and seed exist → vault wins, source='vault'."""
        vault_dir = skill_tree["vault_dir"]
        vault_dir.mkdir(parents=True, exist_ok=True)
        (vault_dir / "items.yaml").write_text("- name: vault-item\n", encoding="utf-8")

        seeds_dir = skill_tree["seeds_dir"]
        (seeds_dir / "items.yaml").write_text("- name: seed-item\n", encoding="utf-8")

        caller = skill_tree["caller_file"]
        vault_patch, root_patch = _mock_paths(skill_tree)
        with vault_patch, root_patch:
            result = read_skill_data(caller, "items.yaml", default=[])

        assert result.source == "vault"
        assert result.data == [{"name": "vault-item"}]

    def test_json_loader(self, skill_tree):
        """JSON loader reads a .json file correctly."""
        vault_dir = skill_tree["vault_dir"]
        vault_dir.mkdir(parents=True, exist_ok=True)
        payload = {"key": "value", "count": 42}
        (vault_dir / "config.json").write_text(json.dumps(payload), encoding="utf-8")

        caller = skill_tree["caller_file"]
        vault_patch, root_patch = _mock_paths(skill_tree)
        with vault_patch, root_patch:
            result = read_skill_data(caller, "config.json", default={}, loader="json")

        assert result.source == "vault"
        assert result.vault_status == "ok"
        assert result.data == {"key": "value", "count": 42}

    def test_collection_loader(self, skill_tree):
        """Collection loader reads a directory of .md files into a list of dicts."""
        vault_dir = skill_tree["vault_dir"]
        collection_dir = vault_dir / "notes"
        collection_dir.mkdir(parents=True, exist_ok=True)

        (collection_dir / "alpha.md").write_text("---\ntitle: Alpha\nstatus: active\n---\n\nBody.\n", encoding="utf-8")
        (collection_dir / "beta.md").write_text("---\ntitle: Beta\nstatus: done\n---\n\nContent.\n", encoding="utf-8")

        caller = skill_tree["caller_file"]
        vault_patch, root_patch = _mock_paths(skill_tree)
        with vault_patch, root_patch:
            result = read_skill_data(caller, "notes", default=[], loader="collection")

        assert result.source == "vault"
        assert result.vault_status == "ok"
        assert isinstance(result.data, list)
        assert len(result.data) == 2
        titles = {item["title"] for item in result.data}
        assert titles == {"Alpha", "Beta"}
