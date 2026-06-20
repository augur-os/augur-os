#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config.paths import get_vault_dir  # noqa: E402

FINAL_ROOTS = {
    "inbox",
    "notes",
    "sources",
    "wiki",
    "skills",
    "drafts",
    "archive",
    "config",
    "memory",
}
DEFAULT_TEMPORARY_ROOTS: set[str] = set()
SKILL_MD_ALLOWED_ROOTS = {"skills", "drafts"}


def check_vault_roots(vault_dir: Path, *, temporary_roots: set[str] | None = None) -> list[str]:
    allowed = set(FINAL_ROOTS)
    allowed.update(temporary_roots if temporary_roots is not None else DEFAULT_TEMPORARY_ROOTS)
    unexpected: list[str] = []
    for entry in sorted(vault_dir.iterdir(), key=lambda item: item.name):
        if not entry.is_dir() or entry.name.startswith("."):
            continue
        if entry.name not in allowed:
            unexpected.append(entry.name)
    return unexpected


def check_disallowed_skill_markdown(vault_dir: Path) -> list[str]:
    disallowed: list[str] = []
    for skill_md in sorted(vault_dir.rglob("SKILL.md")):
        rel = skill_md.relative_to(vault_dir)
        root = rel.parts[0] if rel.parts else ""
        if root not in SKILL_MD_ALLOWED_ROOTS:
            disallowed.append(rel.as_posix())
    return disallowed


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Au-vault root folders against the Obsidian-first contract.")
    parser.add_argument("--vault", type=Path, default=get_vault_dir())
    parser.add_argument("--strict", action="store_true", help="Disallow temporary migration roots.")
    args = parser.parse_args()

    temporary = set() if args.strict else DEFAULT_TEMPORARY_ROOTS
    unexpected = check_vault_roots(args.vault, temporary_roots=temporary)
    disallowed_skill_md = check_disallowed_skill_markdown(args.vault)
    if unexpected or disallowed_skill_md:
        if unexpected:
            print("Unexpected vault roots:")
            for root in unexpected:
                print(f"- {root}")
        if disallowed_skill_md:
            print("Disallowed SKILL.md locations:")
            for rel_path in disallowed_skill_md:
                print(f"- {rel_path}")
        return 1
    print("Vault roots match Obsidian-first contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
