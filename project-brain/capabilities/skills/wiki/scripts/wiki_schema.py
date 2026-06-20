"""Load declarative schema assets for wiki page validation."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


_ASSET_DIR = Path(__file__).resolve().parents[1] / "assets" / "seeds" / "wiki-schema"


def _load_yaml(name: str) -> dict[str, Any]:
    path = _ASSET_DIR / name
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise TypeError(f"Schema asset {path} must load to a mapping")
    return data


@lru_cache(maxsize=1)
def load_wiki_schema() -> dict[str, Any]:
    """Return the current wiki schema assets."""
    return {
        "page_types": _load_yaml("page-types.yaml"),
        "lint_rules": _load_yaml("lint-rules.yaml"),
        "entity_types": _load_yaml("entity-types.yaml"),
    }


def resolve_page_kind(*, page: str, page_type: str | None = None) -> str:
    """Map a page path/frontmatter type to a schema page kind."""
    normalized_page = str(page or "").strip()
    normalized_type = str(page_type or "").strip()

    if normalized_type in {"topic", "overview", "entity", "comparison", "concept", "query"}:
        return normalized_type
    if normalized_page.startswith("concepts/"):
        return "concept"
    if normalized_page.startswith("queries/"):
        return "query"
    if normalized_page == "overview" or normalized_page.endswith("/overview"):
        return "overview"
    if normalized_page.startswith("comparisons/"):
        return "comparison"
    if normalized_page.startswith("entities/"):
        return "entity"
    return "topic"


def page_schema(*, page: str, page_type: str | None = None) -> dict[str, Any]:
    """Return the schema entry for a page."""
    schema = load_wiki_schema()
    kind = resolve_page_kind(page=page, page_type=page_type)
    entry = schema["page_types"].get(kind, {})
    return entry if isinstance(entry, dict) else {}


def allowed_page_types() -> set[str]:
    """Return the allowed stored page_type values."""
    schema = load_wiki_schema()
    values = schema["lint_rules"].get("allowed_page_types", [])
    return {
        str(item).strip()
        for item in values
        if str(item).strip()
    }


def lint_penalties() -> dict[str, int]:
    """Return the schema-defined penalty map for quality scoring."""
    schema = load_wiki_schema()
    penalties = schema["lint_rules"].get("penalties", {})
    if not isinstance(penalties, dict):
        return {}
    return {
        str(key): int(value)
        for key, value in penalties.items()
        if isinstance(value, int | float)
    }
