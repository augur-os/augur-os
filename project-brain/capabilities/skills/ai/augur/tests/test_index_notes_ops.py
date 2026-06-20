"""
Tests for the auto-index-notes ADR-270 vault discovery behavior.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
import src.config.paths as config_paths
import yaml

from src.lib.ops_protocol import OpsContext


PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "ops" / "index_notes.py"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

_spec = importlib.util.spec_from_file_location("ai_index_notes", SCRIPT_PATH)
index_notes = importlib.util.module_from_spec(_spec)
sys.modules["ai_index_notes"] = index_notes
assert _spec.loader is not None
_spec.loader.exec_module(index_notes)


@pytest.fixture
def vault_notes_layout(tmp_path, monkeypatch):
    vault_root = tmp_path / "vault"
    monkeypatch.setenv("AUGUR_ROOT", str(tmp_path))
    monkeypatch.setenv("AUGUR_VAULT", str(vault_root))
    config_paths._skill_to_bundle_cache = None

    (tmp_path / "project-brain" / "capabilities" / "skills" / "knowledge").mkdir(parents=True)
    notes_dir = vault_root / "ai" / "knowledge" / "notes"
    notes_dir.mkdir(parents=True)

    return notes_dir


class TestIndexNotesScan:
    def test_scan_finds_unindexed_vault_notes(self, vault_notes_layout):
        (vault_notes_layout / "2026-03-11-idea.md").write_text(
            "---\ntitle: Vault Note\n---\nBody\n",
            encoding="utf-8",
        )

        result = index_notes.scan(OpsContext(project_root=vault_notes_layout.parents[3]))

        assert len(result.issues) == 1
        assert result.issues[0]["skill"] == "knowledge"
        assert result.issues[0]["path"] == str(vault_notes_layout)

    def test_minimal_cache_keeps_vault_skill_name(self, vault_notes_layout):
        (vault_notes_layout / "2026-03-11-idea.md").write_text(
            "---\ntitle: Vault Note\n---\nBody\n",
            encoding="utf-8",
        )

        index_notes._build_minimal_notes_cache(vault_notes_layout)

        cache = yaml.safe_load((vault_notes_layout / "_index.cache.yaml").read_text(encoding="utf-8"))
        assert cache["notes"][0]["skill"] == "knowledge"
