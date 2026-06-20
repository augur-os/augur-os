"""Frontmatter relationship index for vault markdown notes."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
from typing import Any

from src.lib.frontmatter_utils import extract_relationships, parse_frontmatter


def _is_windows() -> bool:
    """Windows detection seam. Tests patch THIS (not the global os.name) so that
    simulating Windows never mutates os.name globally — mutating os.name makes
    pathlib.Path() construct WindowsPath, which raises on non-Windows runners and
    leaks into unrelated fixture teardowns under CI collection order."""
    return os.name == "nt"


def _git_head_cache_key(vault_dir: Path) -> str | None:
    if _is_windows() and os.environ.get("AUGUR_MCP_CLIENT_ID"):
        return None
    try:
        result = subprocess.run(
            ["git", "-C", str(vault_dir), "rev-parse", "--show-toplevel", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except subprocess.TimeoutExpired:
        return None
    if result.returncode != 0:
        return None
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if len(lines) < 2:
        return None
    git_root, head = lines[0], lines[1]
    return f"git:{git_root}:{head}"


def _filesystem_cache_key(vault_dir: Path) -> str:
    latest = 0
    for md_file in vault_dir.rglob("*.md"):
        if not md_file.is_file():
            continue
        try:
            latest = max(latest, md_file.stat().st_mtime_ns)
        except OSError:
            continue
    return f"fs:{vault_dir.resolve()}:{latest}"


@dataclass(frozen=True)
class RelationshipIndex:
    """In-memory view of wikilink-bearing frontmatter relationships."""

    vault_dir: Path
    cache_key: str
    relationships_by_file: dict[Path, dict[str, list[str]]]

    @classmethod
    def build(cls, vault_dir: Path) -> "RelationshipIndex":
        root = Path(vault_dir)
        relationships_by_file: dict[Path, dict[str, list[str]]] = {}
        if root.is_dir():
            for md_file in sorted(root.rglob("*.md")):
                if not md_file.is_file():
                    continue
                try:
                    meta, _body = parse_frontmatter(md_file)
                except Exception:
                    continue
                relationships = extract_relationships(meta)
                if relationships:
                    relationships_by_file[md_file.resolve(strict=False)] = relationships

        cache_key = _git_head_cache_key(root) or _filesystem_cache_key(root)
        return cls(root, cache_key, relationships_by_file)

    def relationships_for(self, path: Path) -> dict[str, list[str]]:
        return {
            field: list(targets)
            for field, targets in self.relationships_by_file.get(
                Path(path).resolve(strict=False),
                {},
            ).items()
        }

    def targets_for(self, path: Path, *, field: str | None = None) -> list[str]:
        relationships = self.relationships_by_file.get(Path(path).resolve(strict=False), {})
        if field is not None:
            return list(relationships.get(field, []))

        targets: list[str] = []
        seen: set[str] = set()
        for field_targets in relationships.values():
            for target in field_targets:
                if target not in seen:
                    seen.add(target)
                    targets.append(target)
        return targets

    def sources_for(self, target: str) -> list[Path]:
        sources: list[Path] = []
        for path, relationships in self.relationships_by_file.items():
            if any(target in targets for targets in relationships.values()):
                sources.append(path)
        return sources

    def as_records(self) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for path, relationships in self.relationships_by_file.items():
            records.append({"path": path, "relationships": self.relationships_for(path)})
        return records
