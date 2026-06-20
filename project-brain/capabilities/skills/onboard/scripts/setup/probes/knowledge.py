"""Knowledge setup probes."""

from __future__ import annotations

from typing import Any

import yaml

from src.config.paths import (
    get_compiled_wiki_dir,
    get_documents_dir,
    get_project_root,
    get_rag_dir,
    get_runtime_dir,
    get_vault_dir,
    get_wiki_dir,
)
from src.lib.brain_layout import brain_sources_dir

from .helpers import count_markdown, done, pending
from ..types import ProbeResult


def inbox_folders() -> ProbeResult:
    # Intake is lane-based (ADR-771 retired the vault inbox/): enabled lanes in
    # config/system/inbox.yaml drop into the documents inbox root.
    lanes = _enabled_inbox_lanes()
    if lanes:
        return done(f"{len(lanes)} inbox lanes enabled")
    inbox = get_documents_dir() / "inbox"
    if inbox.exists() and any(child.is_dir() for child in inbox.iterdir()):
        return done("documents inbox folder exists")
    return pending("no inbox lanes configured")


def _enabled_inbox_lanes() -> list[str]:
    config_path = get_project_root() / "config" / "system" / "inbox.yaml"
    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return []
    sources = data.get("default_sources")
    if not isinstance(sources, list):
        return []
    return [
        str(source.get("id"))
        for source in sources
        if isinstance(source, dict) and source.get("enabled") and source.get("id")
    ]


def source_folders() -> ProbeResult:
    vault_dir = get_vault_dir()
    runtime_dir = get_runtime_dir()
    rag_dir = get_rag_dir()
    candidates = [
        brain_sources_dir(vault_dir),
        runtime_dir / "knowledge" / "sources.yaml",
        rag_dir / "projects.yaml",
    ]
    if any(path.exists() for path in candidates):
        return done("source configuration found")
    return pending("no source folders linked")


def wiki_queries() -> ProbeResult:
    queries = _load_compounding_queries(get_wiki_dir())
    if queries:
        return done(f"{len(queries)} queries")
    return pending("no compounding wiki queries")


def _load_compounding_queries(wiki_dir) -> list[str]:
    candidates = [wiki_dir / "queries.yaml", wiki_dir / "config.yaml"]
    for candidate in candidates:
        if not candidate.exists():
            continue
        try:
            data = yaml.safe_load(candidate.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError):
            continue
        queries = _extract_compounding_queries(data)
        if queries:
            return queries
    return []


def _extract_compounding_queries(data: Any) -> list[str]:
    if isinstance(data, list):
        return [str(item).strip() for item in data if str(item).strip()]
    if not isinstance(data, dict):
        return []
    queries = data.get("queries")
    if isinstance(queries, list):
        return [str(item).strip() for item in queries if str(item).strip()]
    if isinstance(queries, dict):
        return [str(query_id).strip() for query_id in queries if str(query_id).strip()]
    compounding = data.get("compounding")
    if isinstance(compounding, dict):
        compounding_queries = compounding.get("queries")
        if isinstance(compounding_queries, list):
            return [str(item).strip() for item in compounding_queries if str(item).strip()]
    return []


def wiki_pages_5() -> ProbeResult:
    wiki_dir = get_compiled_wiki_dir()
    count = count_markdown(wiki_dir)
    if count >= 5:
        return done(f"{count} wiki pages")
    return pending(f"{count}/5 wiki pages")
