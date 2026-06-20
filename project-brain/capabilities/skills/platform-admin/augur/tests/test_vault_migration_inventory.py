from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
MODULE_PATH = SCRIPTS_DIR / "vault_migration_inventory.py"


def _module():
    module_name = "platform_admin_vault_migration_inventory_test"
    if module_name in sys.modules:
        return sys.modules[module_name]

    spec = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(module_name, None)
        raise
    return module


def test_classify_vault_path_preserves_runtime_roots(tmp_path: Path):
    classify_vault_path = _module().classify_vault_path
    vault = tmp_path / "vault"

    assert (
        classify_vault_path(vault / "skills" / "apple" / "SKILL.md", vault).classification
        == "protected_runtime_root"
    )
    assert (
        classify_vault_path(vault / "memory" / "index.md", vault).classification
        == "protected_runtime_root"
    )
    assert (
        classify_vault_path(vault / "wiki" / "overview.md", vault).classification
        == "protected_runtime_root"
    )
    assert (
        classify_vault_path(vault / "sources" / "web" / "item.md", vault).classification
        == "protected_runtime_root"
    )


def test_obsidian_first_roots_are_classified_as_in_place(tmp_path: Path):
    inventory = _module()

    vault = tmp_path / "vault"
    paths = [
        vault / "drafts" / "staging" / "r4" / "skills" / "career-ops" / "SKILL.md",
        vault / "archive" / "career" / "old.md",
        vault / "config" / "dashboard" / "active.yaml",
        vault / "notes" / "career" / "cv.md",
    ]
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("---\ntitle: Sample\n---\n", encoding="utf-8")

    classifications = {
        inventory.classify_vault_path(path, vault).relative_path:
        inventory.classify_vault_path(path, vault).classification
        for path in paths
    }

    assert classifications["drafts/staging/r4/skills/career-ops/SKILL.md"] == "inactive_draft_root"
    assert classifications["archive/career/old.md"] == "inactive_archive_root"
    assert classifications["config/dashboard/active.yaml"] == "durable_config_root"
    assert classifications["notes/career/cv.md"] == "active_notes_root"


def test_classify_vault_path_marks_legacy_underscore_roots_for_review(tmp_path: Path):
    classify_vault_path = _module().classify_vault_path
    vault = tmp_path / "vault"

    drafts = classify_vault_path(vault / "_drafts" / "staging" / "item.md", vault)
    system = classify_vault_path(vault / "_system" / "dashboard" / "active.yaml", vault)

    assert drafts.classification == "legacy_review_required"
    assert drafts.suggested_action == "review_for_notes_archive_delete_or_consolidation"
    assert drafts.suggested_target == "notes/_drafts/staging/item.md"
    assert system.classification == "non_markdown_review_required"
    assert system.suggested_action == "review_for_archive_or_keep"
    assert system.suggested_target == "archive/_system/dashboard/active.yaml"


def test_classify_vault_path_marks_legacy_roots_for_review(tmp_path: Path):
    classify_vault_path = _module().classify_vault_path
    vault = tmp_path / "vault"
    result = classify_vault_path(vault / "legacy-interviews" / "interview.md", vault)

    assert result.classification == "legacy_review_required"
    assert result.suggested_action == "review_for_notes_archive_delete_or_consolidation"
    assert result.suggested_target == "notes/legacy-interviews/interview.md"


def test_classify_vault_path_keeps_reserved_managed_roots(tmp_path: Path):
    classify_vault_path = _module().classify_vault_path
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / ".augur-reserved").write_text("career\n", encoding="utf-8")
    result = classify_vault_path(vault / "career" / "interview.md", vault)

    assert result.classification == "temporary_legacy_data_root"
    assert result.suggested_action == "review_for_notes_config_or_archive"
    assert result.suggested_target == "career/interview.md"


def test_classify_vault_path_ignores_outside_vault_markdown(tmp_path: Path):
    classify_vault_path = _module().classify_vault_path
    vault = tmp_path / "vault"
    outside = tmp_path / "outside.md"

    result = classify_vault_path(outside, vault)

    assert result.relative_path == outside.as_posix()
    assert result.classification == "outside_vault_root"
    assert result.suggested_action == "ignore_outside_vault"
    assert result.suggested_target == outside.as_posix()
    assert not result.suggested_target.startswith(("notes/", "archive/"))


def test_classify_vault_path_ignores_outside_vault_non_markdown(tmp_path: Path):
    classify_vault_path = _module().classify_vault_path
    vault = tmp_path / "vault"
    outside = tmp_path / "outside.pdf"

    result = classify_vault_path(outside, vault)

    assert result.relative_path == outside.as_posix()
    assert result.classification == "outside_vault_root"
    assert result.suggested_action == "ignore_outside_vault"
    assert result.suggested_target == outside.as_posix()
    assert not result.suggested_target.startswith(("notes/", "archive/"))


def test_collect_inventory_excludes_git_metadata(tmp_path: Path):
    collect_inventory = _module().collect_inventory
    vault = tmp_path / "vault"
    (vault / ".git").mkdir(parents=True)
    (vault / ".git" / "config").write_text("[core]\n", encoding="utf-8")
    (vault / "notes").mkdir()
    (vault / "notes" / "item.md").write_text("note\n", encoding="utf-8")

    paths = {item.relative_path for item in collect_inventory(vault)}

    assert ".git/config" not in paths
    assert "notes/item.md" in paths


def test_render_migration_ledger_uses_frontmatter(tmp_path: Path):
    mod = _module()
    vault = tmp_path / "vault"
    items = [
        mod.classify_vault_path(vault / "legacy-interviews" / "interview.md", vault),
        mod.classify_vault_path(vault / "skills" / "apple" / "SKILL.md", vault),
    ]

    markdown = mod.render_migration_ledger(items)

    assert markdown.startswith("---\ntitle: Vault Migration Inventory\n")
    assert (
        "| legacy-interviews/interview.md | legacy_review_required | "
        "review_for_notes_archive_delete_or_consolidation | notes/legacy-interviews/interview.md |"
    ) in markdown
    assert (
        "| skills/apple/SKILL.md | protected_runtime_root | keep_in_place | "
        "skills/apple/SKILL.md |"
    ) in markdown


def test_render_migration_ledger_escapes_table_cells():
    mod = _module()
    item = mod.VaultMigrationItem(
        "weird|name.md",
        "legacy\nreview",
        "review|keep",
        "notes/weird\nname.md",
    )

    markdown = mod.render_migration_ledger([item])

    expected_row = (
        "| weird\\|name.md | legacy<br>review | review\\|keep | "
        "notes/weird<br>name.md |"
    )
    assert expected_row in markdown
    assert "legacy\nreview" not in markdown
