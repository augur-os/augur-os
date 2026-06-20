#!/usr/bin/env python3
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path


from bootstrap_paths import ensure_project_paths  # noqa: E402

PROJECT_ROOT = ensure_project_paths(__file__)

from src.config.paths import get_vault_dir  # noqa: E402


PROTECTED_ROOTS = {"skills", "memory", "wiki", "sources", "drafts"}
USER_ROOTS = {"inbox", "notes", "archive"}
CONFIG_ROOTS = {"config"}
OBSIDIAN_ROOTS = {".obsidian", ".trash"}


@dataclass(frozen=True)
class VaultMigrationItem:
    relative_path: str
    classification: str
    suggested_action: str
    suggested_target: str


def _relative_path(path: Path, vault_dir: Path) -> Path | None:
    resolved_path = path.expanduser().resolve(strict=False)
    resolved_vault = vault_dir.expanduser().resolve(strict=False)
    try:
        return resolved_path.relative_to(resolved_vault)
    except ValueError:
        return None


def _is_git_metadata(path: Path, vault_dir: Path) -> bool:
    rel = _relative_path(path, vault_dir)
    return rel is not None and bool(rel.parts) and rel.parts[0] == ".git"


def _is_valid_managed_root(root: str, vault_dir: Path) -> bool:
    from src.lib.dir_alignment import ManagedLocation, validate_dir_name

    return validate_dir_name(ManagedLocation(path=vault_dir), root)


def _escape_markdown_table_cell(value: str) -> str:
    return (
        value.replace("|", "\\|")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("\n", "<br>")
    )


def classify_vault_path(path: Path, vault_dir: Path) -> VaultMigrationItem:
    rel = _relative_path(path, vault_dir)
    if rel is None:
        path_text = path.as_posix()
        return VaultMigrationItem(
            path_text,
            "outside_vault_root",
            "ignore_outside_vault",
            path_text,
        )

    rel_text = rel.as_posix()
    root = rel.parts[0] if rel.parts else ""

    if root == "drafts":
        return VaultMigrationItem(rel_text, "inactive_draft_root", "keep_in_place", rel_text)
    if root == "archive":
        return VaultMigrationItem(rel_text, "inactive_archive_root", "keep_in_place", rel_text)
    if root == "notes":
        return VaultMigrationItem(rel_text, "active_notes_root", "keep_in_place", rel_text)
    if root == "config":
        return VaultMigrationItem(rel_text, "durable_config_root", "keep_in_place", rel_text)
    if root in PROTECTED_ROOTS:
        return VaultMigrationItem(rel_text, "protected_runtime_root", "keep_in_place", rel_text)
    if root in USER_ROOTS:
        return VaultMigrationItem(rel_text, "already_in_target_root", "keep_in_place", rel_text)
    if root in CONFIG_ROOTS:
        return VaultMigrationItem(rel_text, "durable_config_root", "keep_in_place", rel_text)
    if root in OBSIDIAN_ROOTS or root.startswith("."):
        return VaultMigrationItem(rel_text, "obsidian_system_root", "keep_in_place", rel_text)
    if _is_valid_managed_root(root, vault_dir):
        return VaultMigrationItem(
            rel_text,
            "temporary_legacy_data_root",
            "review_for_notes_config_or_archive",
            rel_text,
        )
    if path.suffix.lower() != ".md":
        return VaultMigrationItem(
            rel_text,
            "non_markdown_review_required",
            "review_for_archive_or_keep",
            f"archive/{rel_text}",
        )

    target = Path("notes") / rel
    return VaultMigrationItem(
        rel_text,
        "legacy_review_required",
        "review_for_notes_archive_delete_or_consolidation",
        target.as_posix(),
    )


def render_migration_ledger(items: list[VaultMigrationItem]) -> str:
    lines = [
        "---",
        "title: Vault Migration Inventory",
        "status: draft",
        "type: migration-ledger",
        "---",
        "",
        "# Vault Migration Inventory",
        "",
        "| Path | Classification | Suggested Action | Suggested Target |",
        "| --- | --- | --- | --- |",
    ]
    for item in items:
        lines.append(
            f"| {_escape_markdown_table_cell(item.relative_path)} | "
            f"{_escape_markdown_table_cell(item.classification)} | "
            f"{_escape_markdown_table_cell(item.suggested_action)} | "
            f"{_escape_markdown_table_cell(item.suggested_target)} |"
        )
    lines.append("")
    return "\n".join(lines)


def collect_inventory(vault_dir: Path) -> list[VaultMigrationItem]:
    return [
        classify_vault_path(path, vault_dir)
        for path in sorted(vault_dir.rglob("*"))
        if path.is_file() and not _is_git_metadata(path, vault_dir)
    ]


def main() -> int:
    vault_dir = get_vault_dir()
    ledger = render_migration_ledger(collect_inventory(vault_dir))
    print(ledger)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
