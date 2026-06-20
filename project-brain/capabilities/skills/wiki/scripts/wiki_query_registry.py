"""User-configurable wiki query registry.

Queries live at ``<vault>/wiki/queries.yaml`` and declare the sources,
prompt, output page, and required sections for manual wiki synthesis runs.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from src.config.paths import get_vault_dir


SOURCE_KINDS = frozenset(
    {
        "memory_md",
        "daily_logs",
        "ask_retention",
        "adr_index",
        "git_recent_commits",
        "inbox",
        "linked_folder",
    }
)
SUPPORTED_REFRESH_POLICIES = frozenset({"manual"})
_REQUIRED_KEYS = frozenset(
    {
        "title",
        "description",
        "prompt_template",
        "sources",
        "output",
        "page_type",
        "required_sections",
        "refresh_policy",
    }
)


class QueryRegistryError(ValueError):
    """Raised when a query spec or registry file is invalid."""


def _registry_path() -> Path:
    return get_vault_dir() / "wiki" / "queries.yaml"


def load_registry() -> dict[str, Any]:
    path = _registry_path()
    if not path.exists():
        return {"version": 1, "queries": {}}

    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise QueryRegistryError(f"queries.yaml root must be a mapping, got {type(raw).__name__}")

    version = raw.setdefault("version", 1)
    if version != 1:
        raise QueryRegistryError(f"unsupported registry version: {version!r}")

    queries = raw.setdefault("queries", {})
    if not isinstance(queries, dict):
        raise QueryRegistryError("queries.yaml 'queries' must be a mapping")

    for query_id, spec in queries.items():
        if not isinstance(spec, dict):
            raise QueryRegistryError(f"query '{query_id}' must be a mapping")
        validate_query_spec(str(query_id), spec, existing=queries)

    return raw


def list_queries() -> dict[str, dict[str, Any]]:
    return load_registry()["queries"]


def read_query(query_id: str) -> dict[str, Any] | None:
    return list_queries().get(query_id)


def validate_query_spec(
    query_id: str,
    spec: dict[str, Any],
    *,
    existing: dict[str, dict[str, Any]] | None = None,
) -> None:
    missing = _REQUIRED_KEYS - set(spec)
    if missing:
        raise QueryRegistryError(f"query '{query_id}' missing keys: {sorted(missing)}")

    if spec["page_type"] != "query":
        raise QueryRegistryError(f"page_type must be 'query', got {spec['page_type']!r}")

    refresh_policy = spec["refresh_policy"]
    if refresh_policy not in SUPPORTED_REFRESH_POLICIES:
        raise QueryRegistryError(
            f"refresh_policy must be one of {sorted(SUPPORTED_REFRESH_POLICIES)}; got {refresh_policy!r}"
        )

    sources = spec["sources"]
    if not isinstance(sources, list) or not sources:
        raise QueryRegistryError(f"query '{query_id}' sources must be a non-empty list")
    for source in sources:
        if not isinstance(source, dict):
            raise QueryRegistryError(f"query '{query_id}' source entries must be mappings")
        kind = source.get("kind")
        if kind not in SOURCE_KINDS:
            raise QueryRegistryError(f"unknown source kind: {kind!r}")

    output = str(spec["output"])
    if not output.startswith("vault/wiki/") or ".." in Path(output).parts:
        raise QueryRegistryError(f"output path must be under vault/wiki/ (got {output!r})")

    required_sections = spec["required_sections"]
    if not isinstance(required_sections, list) or not required_sections:
        raise QueryRegistryError("required_sections must be a non-empty list")
    if not all(isinstance(section, str) and section.strip() for section in required_sections):
        raise QueryRegistryError("required_sections entries must be non-empty strings")

    for other_id, other_spec in (existing or {}).items():
        if other_id == query_id:
            continue
        if other_spec.get("output") == output:
            raise QueryRegistryError(f"output path already claimed by query '{other_id}'")


def write_query(query_id: str, spec: dict[str, Any]) -> Path:
    registry = load_registry()
    validate_query_spec(query_id, spec, existing=registry["queries"])
    registry["queries"][query_id] = spec
    return _write_registry(registry)


def delete_query(query_id: str) -> bool:
    registry = load_registry()
    if query_id not in registry["queries"]:
        return False

    del registry["queries"][query_id]
    _write_registry(registry)
    return True


def _write_registry(registry: dict[str, Any]) -> Path:
    path = _registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(registry, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return path
