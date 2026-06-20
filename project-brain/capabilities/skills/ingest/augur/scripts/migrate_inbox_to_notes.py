"""Migrate <vault>/{inbox,sources,prompts}/ Markdown cards to <vault>/notes/.

The migration is idempotent. Each migrated card gets an ``x-augur-note-type``
frontmatter discriminator inferred from its source folder and existing metadata.
Already migrated notes are left untouched, and source folders remain on disk for
the ADR-751 grace period.
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[5]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.lib.frontmatter_utils import parse_frontmatter, write_vault_frontmatter  # noqa: E402

SOURCE_FOLDERS = (
    ("inbox", "file"),
    ("sources/urls", "url"),
    ("sources/files", "file"),
    ("sources", "file"),
    ("prompts", "prompt"),
)


@dataclass
class MigrationReport:
    moved: int = 0
    skipped_already_migrated: int = 0
    skipped_collisions: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _classify_card(card_path: Path, default_type: str) -> str:
    """Infer the ADR-751 note type for ``card_path``."""
    try:
        frontmatter, _ = parse_frontmatter(card_path)
    except Exception:
        return default_type

    if frontmatter.get("x-augur-note-type"):
        return str(frontmatter["x-augur-note-type"])
    if frontmatter.get("prompt_triggerable") in ("true", "True", True):
        return "prompt"
    if frontmatter.get("x-augur-prompt-triggerable") in ("true", "True", True):
        return "prompt"
    if frontmatter.get("source") == "url" or frontmatter.get("source_type") == "url":
        return "url"
    if frontmatter.get("canonical_url") or frontmatter.get("url"):
        return "url"
    return default_type


def _walk_folder(vault: Path, subfolder: str) -> list[Path]:
    root = vault / subfolder
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*.md") if path.is_file())


def migrate_vault(vault: Path, *, dry_run: bool = True) -> MigrationReport:
    """Migrate Markdown cards into ``vault / "notes"``."""
    report = MigrationReport()
    vault = vault.expanduser().resolve()
    notes_dir = vault / "notes"
    if not dry_run:
        notes_dir.mkdir(parents=True, exist_ok=True)

    seen_sources: set[Path] = set()
    seen_destinations: set[Path] = set()
    for subfolder, default_type in SOURCE_FOLDERS:
        for card in _walk_folder(vault, subfolder):
            resolved_card = card.resolve()
            if resolved_card in seen_sources:
                continue
            seen_sources.add(resolved_card)

            if card.parent == notes_dir:
                report.skipped_already_migrated += 1
                continue

            note_type = _classify_card(card, default_type)
            destination = notes_dir / card.name
            if destination in seen_destinations or destination.exists():
                report.skipped_collisions.append(str(card.relative_to(vault)))
                continue
            seen_destinations.add(destination)

            if dry_run:
                report.moved += 1
                continue

            try:
                frontmatter, body = parse_frontmatter(card)
                frontmatter["x-augur-note-type"] = note_type
                write_vault_frontmatter(destination, frontmatter, body)
                card.unlink()
                report.moved += 1
            except Exception as exc:  # noqa: BLE001
                report.errors.append(f"{card}: {exc}")

    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Migrate inbox/sources/prompts Markdown cards into notes/"
    )
    parser.add_argument("--vault", type=Path, required=True, help="Vault root")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually move files. Default is a dry run.",
    )
    args = parser.parse_args(argv)

    report = migrate_vault(args.vault, dry_run=not args.apply)
    mode = "APPLIED" if args.apply else "DRY-RUN"
    print(
        f"[{mode}] moved={report.moved} "
        f"already_migrated={report.skipped_already_migrated} "
        f"collisions={len(report.skipped_collisions)} errors={len(report.errors)}"
    )
    if report.skipped_collisions:
        print("Collisions:")
        for collision in report.skipped_collisions:
            print(f"  - {collision}")
    if report.errors:
        print("Errors:")
        for error in report.errors:
            print(f"  - {error}")
    return 0 if not report.errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
