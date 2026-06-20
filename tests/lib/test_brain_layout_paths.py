import pytest

from src.config import paths
from src.lib import brain_manifest


@pytest.fixture
def domains_vault(tmp_path, monkeypatch):
    (tmp_path / "BRAIN.yaml").write_text(
        "schema_version: 1\nid: t\ntype: personal\nlayout: domains\n", encoding="utf-8"
    )
    monkeypatch.setattr(paths, "get_vault_dir", lambda: tmp_path)
    return tmp_path


def test_vault_helpers_in_domains_layout(domains_vault):
    assert paths.get_vault_notes_dir() == domains_vault
    assert paths.get_vault_skills_dir() == domains_vault / "_augur" / "capabilities" / "skills"
    assert paths.get_vault_config_dir() == domains_vault / "_augur" / "config"
    assert paths.get_vault_prompts_dir() == domains_vault / "_augur" / "prompts"
    assert paths.get_vault_archive_dir() == domains_vault / "_augur" / "archive"
    assert paths.get_vault_drafts_dir() == domains_vault / "_augur" / "drafts"
    assert paths.get_vault_staging_dir() == domains_vault / "_augur" / "drafts" / "staging"
    assert paths.get_memory_dir() == domains_vault / "_augur" / "knowledge" / "memory"


def test_config_skill_resolves_under_augur_in_domains(domains_vault):
    # .augur-reserved whitelists the names so validate_dir_name passes without
    # depending on this machine's real skill inventory.
    (domains_vault / ".augur-reserved").write_text("ai\ncareer\n", encoding="utf-8")
    assert paths.get_skill_vault_dir("ai") == domains_vault / "_augur" / "config" / "ai"


def test_domain_skill_resolves_at_root_in_domains(domains_vault):
    (domains_vault / ".augur-reserved").write_text("ai\ncareer\n", encoding="utf-8")
    assert paths.get_skill_vault_dir("career") == domains_vault / "career"


def test_skill_mapping_has_no_legacy_notes_prefix():
    for skill, rel in paths._VAULT_FIRST_SKILL_VAULT_DIRS.items():
        assert not str(rel).startswith("knowledge/notes"), f"{skill} still legacy"


def test_skeleton_for_domains_layout():
    tops = brain_manifest.brain_skeleton_top_dirs(layout="domains")
    assert "_augur" in tops and "inbox" in tops
    assert "knowledge" not in tops
    # legacy default unchanged
    assert "knowledge" in brain_manifest.brain_skeleton_top_dirs()


def test_write_brain_manifest_preserves_layout(tmp_path):
    """aug sync's ensure_mount rewrote BRAIN.yaml and dropped layout: domains
    (2026-06-12 incident) — the writer must carry an existing layout through."""
    from dataclasses import replace

    from src.lib.brain_layout import brain_layout
    from src.lib.brain_manifest import BrainManifest, read_brain_manifest, write_brain_manifest
    from src.lib.brain_registry_models import BrainType

    root = tmp_path / "brain"
    root.mkdir()
    (root / "BRAIN.yaml").write_text(
        "schema_version: 1\nid: t\ntype: personal\nroot: /x\nlayout: domains\n",
        encoding="utf-8",
    )
    manifest = BrainManifest(schema_version=1, id="t", type=BrainType("personal"), root="/x")
    try:
        write_brain_manifest(root, manifest)
        on_disk = read_brain_manifest(root / "BRAIN.yaml")
        assert on_disk.layout == "domains"
        assert brain_layout(root) == "domains"
        # absent layout stays absent (legacy brains gain no key)
        legacy_root = tmp_path / "legacy"
        legacy_root.mkdir()
        write_brain_manifest(legacy_root, replace(manifest, root=str(legacy_root)))
        assert read_brain_manifest(legacy_root / "BRAIN.yaml").layout is None
    finally:
        brain_layout.cache_clear()
