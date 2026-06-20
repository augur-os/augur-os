"""Shared/private overlay metadata helpers for RAG index scanners."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

OverlayScope = Literal["shared", "private"]

_ROOT_LABELS: dict[OverlayScope, str] = {
    "shared": "project-brain",
    "private": "private-vault",
}


def overlay_root_label(scope: OverlayScope, *, source_root: str | None = None) -> str:
    return _ROOT_LABELS[scope]


def is_promotion_packet_relative(rel: Path) -> bool:
    return len(rel.parts) >= 3 and rel.parts[0] == "inbox" and rel.parts[1] == "promotions"


def promotion_state(scope: OverlayScope, rel: Path) -> str:
    if scope == "shared" and is_promotion_packet_relative(rel):
        return "packet"
    if scope == "shared":
        return "integrated"
    return "private"


def overlay_metadata(*, scope: OverlayScope, rel: Path, source_root: str | None = None) -> dict[str, str]:
    resolved_source_root = source_root or _ROOT_LABELS[scope]
    return {
        "vault_scope": scope,
        "vault_root": overlay_root_label(scope, source_root=resolved_source_root),
        "promotion_state": promotion_state(scope, rel),
        "source_root": resolved_source_root,
    }


def overlay_entry_id(category: str, scope: OverlayScope, rel: Path) -> str:
    normalized = rel.with_suffix("").as_posix()
    return f"{category}:{scope}:{normalized}"


def vault_overlay_output_path(category_dir: Path, scope: OverlayScope, rel: Path) -> Path:
    if scope == "shared" and is_promotion_packet_relative(rel):
        return category_dir / rel
    if rel.parts and rel.parts[0] in {"inbox", "notes", "sources", "drafts", "_drafts", "archive", "_system"}:
        root = rel.parts[0]
        tail = Path(*rel.parts[1:]) if len(rel.parts) > 1 else Path(rel.name)
        return category_dir / root / scope / tail
    return category_dir / scope / rel


def wiki_overlay_output_path(category_dir: Path, scope: OverlayScope, rel: Path) -> Path:
    return category_dir / scope / rel
