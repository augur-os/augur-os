"""Generate per-machine `files` symlinks from vault domains to the docs store.

Links are machine-local (gitignored) and computed from the configured roots,
so every machine/user generates links that match its own layout (spec
2026-06-12, Portability section). Run via:
    uv run python -m src.lib.vault_links
"""

from __future__ import annotations

import os
from pathlib import Path

from src.lib.brain_layout import MACHINE_DIR
from src.logging import get_entity_logger

logger = get_entity_logger("lib.vault_links")

# "profile" is spec-listed link-excluded infra; its redundancy with the
# target.is_dir() check below is intentional defense.
EXCLUDED = {"inbox", "wiki", "sources", "profile", MACHINE_DIR}
GITIGNORE_ENTRY = "*/files"


def generate_links(vault: Path, docs: Path) -> list[str]:
    if not vault.is_dir():
        raise ValueError(f"vault root is not a directory: {vault}")
    created: list[str] = []
    for domain in sorted(p for p in vault.iterdir() if p.is_dir()):
        if domain.name in EXCLUDED or domain.name.startswith("."):
            continue
        target = docs / domain.name
        if not target.is_dir():
            continue
        link = domain / "files"
        if link.is_symlink():
            if link.resolve() == target.resolve():
                continue  # already healthy — idempotent fast path, not counted
        elif link.exists():
            continue  # real folder named `files` — never clobber
        try:
            if link.is_symlink():
                link.unlink()
            try:
                rel = Path(os.path.relpath(target, start=domain))
                os.symlink(rel, link, target_is_directory=True)
            except OSError:
                os.symlink(target.resolve(), link, target_is_directory=True)
        except OSError as exc:
            logger.warning("could not link %s: %s", link, exc)
            continue
        created.append(str(link))
    _ensure_gitignore(vault)
    return created


def _ensure_gitignore(vault: Path) -> None:
    gi = vault / ".gitignore"
    lines = gi.read_text(encoding="utf-8").splitlines() if gi.is_file() else []
    if GITIGNORE_ENTRY not in lines:
        lines.append(GITIGNORE_ENTRY)
        gi.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    from src.config.paths import get_documents_dir, get_vault_dir

    created = generate_links(get_vault_dir(), get_documents_dir())
    for c in created:
        print(f"linked {c}")
    print(f"{len(created)} links")


if __name__ == "__main__":
    main()
