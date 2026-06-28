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


def test_write_brain_manifest_preserves_relative_path_style(tmp_path):
    """aug project init / sync rewrote BRAIN.yaml's root: . and attached_project: ..
    to absolute /Users/<name> paths, dirtying the repo and leaking machine paths
    into a public release (v1.12.0 incident). The writer must keep the committed
    relative form when the new absolute path resolves to the same location."""
    from src.lib.brain_manifest import BrainManifest, read_brain_manifest, write_brain_manifest
    from src.lib.brain_registry_models import BrainType

    project = tmp_path / "Augur"
    brain_root = project / "project-brain"
    brain_root.mkdir(parents=True)
    (brain_root / "BRAIN.yaml").write_text(
        "schema_version: 1\nid: project-augur\ntype: project\n"
        "root: .\nattached_project: ..\ndescription: Augur project brain\n",
        encoding="utf-8",
    )

    # Simulate the heal path: absolute root/attached_project resolving to the
    # same dirs as the relative committed form.
    manifest = BrainManifest(
        schema_version=1,
        id="project-augur",
        type=BrainType("project"),
        root=str(brain_root),
        attached_project=str(project),
        description="Augur project brain",
    )
    write_brain_manifest(brain_root, manifest)

    raw = (brain_root / "BRAIN.yaml").read_text(encoding="utf-8")
    on_disk = read_brain_manifest(brain_root / "BRAIN.yaml")
    assert on_disk.root == "."
    assert on_disk.attached_project == ".."
    assert str(tmp_path) not in raw  # no machine-specific absolute paths leaked


def test_write_brain_manifest_rewrites_genuinely_moved_attached_project(tmp_path):
    """When attached_project really points somewhere else, the new value wins —
    style preservation must not pin a stale location."""
    from src.lib.brain_manifest import BrainManifest, read_brain_manifest, write_brain_manifest
    from src.lib.brain_registry_models import BrainType

    project = tmp_path / "Augur"
    brain_root = project / "project-brain"
    brain_root.mkdir(parents=True)
    moved = tmp_path / "Augur-moved"
    moved.mkdir()
    (brain_root / "BRAIN.yaml").write_text(
        "schema_version: 1\nid: project-augur\ntype: project\n" "root: .\nattached_project: ..\n",
        encoding="utf-8",
    )

    manifest = BrainManifest(
        schema_version=1,
        id="project-augur",
        type=BrainType("project"),
        root=str(brain_root),
        attached_project=str(moved),  # genuinely different project dir
    )
    write_brain_manifest(brain_root, manifest)

    on_disk = read_brain_manifest(brain_root / "BRAIN.yaml")
    assert on_disk.root == "."  # unchanged — still resolves correctly
    assert on_disk.attached_project == str(moved)  # rewritten to the new location
