"""Wiki maintenance helpers for the ADR-546 ingest-era wiki model."""
from __future__ import annotations

import hashlib
import json
import posixpath
import re
from collections import Counter
from pathlib import Path
from pathlib import PurePosixPath
from typing import Any

from src.lib.frontmatter_utils import parse_frontmatter
from src.lib.wiki_utils import MARKDOWN_LINK_RE, WIKILINK_RE

from src.lib.frontmatter_utils import write_vault_frontmatter

try:
    from .wiki_concept_links import lint_concept_links
    from .wiki_pages import WikiPages, compute_source_fingerprint
    from .wiki_quality import assess_page_quality
    from .wiki_schema import allowed_page_types, page_schema
    from .wiki_timeline import replace_compiled_truth
except ImportError:
    from wiki_concept_links import lint_concept_links
    from wiki_pages import WikiPages, compute_source_fingerprint
    from wiki_quality import assess_page_quality
    from wiki_schema import allowed_page_types, page_schema
    from wiki_timeline import replace_compiled_truth


_REQUIRED_ROOT_PAGES = ("index", "overview")
_SYSTEM_ROOT_PAGES = {"index.md", "overview.md"}
_IGNORED_PAGE_FILENAMES = {"README.md"}
_FORCE_REWRITE_QUALITY_REASONS = {
    "inventory_style",
    "deep_structure_gap",
    "deep_content_gap",
    "generic_current_reality",
    "generic_source_doctrine",
    "draft_source_basis",
    "pending_source_cluster",
    "below_cluster_source_floor",
    "overbroad_source_cluster",
    "shallow_synthesis",
    "index_like_prose",
    "clipped_evidence",
    "unsupported_domain_abstraction",
}
_GENERIC_SOURCE_THEME_LABELS = {
    "",
    "ai",
    "augur",
    "dashboard",
    "data",
    "docs",
    "document",
    "documents",
    "generic",
    "hub",
    "hubs",
    "import",
    "imports",
    "inbox",
    "markdown",
    "md",
    "note",
    "notes",
    "notion import",
    "overview",
    "reminder",
    "reminders",
    "seed",
    "skill",
    "soft skills",
    "hard skills",
    "source",
    "sync",
}
_THEME_PHRASE_HINTS = (
    "ai platform",
    "career growth",
    "comparison",
    "consulting work",
    "deep work",
    "developer use case",
    "developer workflow",
    "dashboard loops",
    "ide integration",
    "interview prep",
    "leadership",
    "local execution",
    "learning roadmap",
    "product direction",
    "product ideas",
    "project management",
    "scheduled tasks",
    "startup ideas",
    "startups",
)
_SOURCE_ROLE_ORDER = {
    "reference context": 0,
    "working notes": 1,
    "tasks and ideas": 2,
    "source material": 3,
}


def _normalize_page_name(name: str) -> str:
    normalized = name.strip().replace("\\", "/")
    if normalized.endswith(".md"):
        normalized = normalized[:-3]
    normalized = normalized.strip("/")
    normalized = re.sub(r"[^\w\s/-]", "", normalized)
    normalized = re.sub(r"[\s_]+", "-", normalized)
    normalized = re.sub(r"-+", "-", normalized).strip("-/")
    return normalized or "note"


def lint_wiki(*, wiki_dir: Path) -> dict[str, Any]:
    """Validate the hub-based wiki for missing pages, broken links, and orphans."""
# TODO_CLEANUP: This file is 1908 lines — consider splitting into smaller modules
    wiki_dir = Path(wiki_dir)
    if not wiki_dir.is_dir():
        return {
            "ok": False,
            "path": str(wiki_dir),
            "pages": 0,
            "hubs": 0,
            "missing_required": list(_REQUIRED_ROOT_PAGES),
            "missing_links": [],
            "orphan_pages": [],
            "duplicate_titles": [],
            "broken_links": [],
            "legacy_pages": [],
            "duplicate_aliases": [],
            "schema_violations": [],
        }

    pages: dict[str, Path] = {}
    hub_names: set[str] = set()
    for path in sorted(wiki_dir.rglob("*.md")):
        rel = path.relative_to(wiki_dir)
        if rel.name in _IGNORED_PAGE_FILENAMES:
            continue
        if rel.parent == Path(".") and rel.name in _SYSTEM_ROOT_PAGES:
            pages[rel.stem] = path
            continue
        key = str(rel.with_suffix(""))
        pages[key] = path
        if len(rel.parts) > 1:
            hub_names.add(rel.parts[0])

    missing_required = [name for name in _REQUIRED_ROOT_PAGES if name not in pages]
    missing_links: set[str] = set()
    inbound = {name: 0 for name in pages}
    title_index: dict[str, list[str]] = {}
    metadata_by_name: dict[str, dict[str, Any]] = {}
    schema_violations: list[str] = []
    allowed_types = allowed_page_types()
    concept_lint = lint_concept_links(wiki_dir)
    resolved_links = {
        (item["page"], item["target"]): item["resolved"]
        for item in concept_lint.get("links", [])
    }

    for name, path in pages.items():
        meta, body = parse_frontmatter(path)
        metadata_by_name[name] = meta
        title = str(meta.get("title") or Path(name).name.replace("-", " ").title()).strip()
        title_index.setdefault(title.lower(), []).append(name)
        if name not in _REQUIRED_ROOT_PAGES:
            page_type = str(meta.get("page_type") or "").strip()
            if page_type and page_type not in allowed_types:
                schema_violations.append(f"Page '{name}' has invalid page_type '{page_type}'")
            schema_entry = page_schema(page=name, page_type=page_type)
            required_sections = [
                str(item).strip()
                for item in schema_entry.get("required_sections", [])
                if str(item).strip()
            ]
            missing_sections = [
                heading for heading in required_sections
                if f"## {heading}" not in body
            ]
            if missing_sections:
                schema_violations.append(
                    f"Page '{name}' is missing required sections: {', '.join(missing_sections)}"
                )
        for target in WIKILINK_RE.findall(body):
            link_key = (name, target)
            normalized = resolved_links[link_key] if link_key in resolved_links else _normalize_page_name(target)
            if normalized not in pages:
                missing_links.add(target)
                continue
            inbound[normalized] += 1
        for target in MARKDOWN_LINK_RE.findall(body):
            normalized = _normalize_markdown_page_link(name, target)
            if normalized is None:
                continue
            if normalized not in pages:
                missing_links.add(target)
                continue
            inbound[normalized] += 1

    orphan_pages = sorted(
        name
        for name, count in inbound.items()
        if name not in _REQUIRED_ROOT_PAGES
        and not _is_root_query_output(name, metadata_by_name.get(name, {}))
        and count == 0
    )
    duplicate_titles = sorted(
        "/".join(names)
        for names in title_index.values()
        if len(names) > 1
    )

    return {
        "ok": (
            not missing_required
            and not missing_links
            and not orphan_pages
            and not duplicate_titles
            and not schema_violations
            and not concept_lint["broken_links"]
            and not concept_lint["legacy_pages"]
            and not concept_lint.get("duplicate_aliases", [])
        ),
        "path": str(wiki_dir),
        "pages": len(pages),
        "hubs": len(hub_names),
        "missing_required": missing_required,
        "missing_links": sorted(missing_links),
        "orphan_pages": orphan_pages,
        "duplicate_titles": duplicate_titles,
        "broken_links": concept_lint["broken_links"],
        "legacy_pages": concept_lint["legacy_pages"],
        "duplicate_aliases": concept_lint.get("duplicate_aliases", []),
        "schema_violations": schema_violations,
    }


def _is_root_query_output(name: str, metadata: dict[str, Any]) -> bool:
    return (
        "/" not in name
        and str(metadata.get("page_type") or "").strip() == "query"
        and bool(str(metadata.get("query_id") or "").strip())
    )


def _normalize_markdown_page_link(source_page: str, target: str) -> str | None:
    raw_target = str(target or "").strip()
    if not raw_target:
        return None

    # Drop optional Markdown title syntax: [text](page.md "title").
    raw_target = raw_target.split(maxsplit=1)[0].strip("<>")
    if not raw_target or raw_target.startswith("#") or raw_target.startswith("//"):
        return None
    if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", raw_target):
        return None

    raw_target = raw_target.split("#", 1)[0].split("?", 1)[0].strip()
    if not raw_target.endswith(".md"):
        return None

    page_target = raw_target[:-3]
    if page_target.startswith("/"):
        normalized = posixpath.normpath(page_target.strip("/"))
    else:
        base = PurePosixPath(source_page).parent
        normalized = posixpath.normpath(str(base / page_target))

    normalized = normalized.strip("/")
    if not normalized or normalized == "." or normalized.startswith("../"):
        return None
    return normalized


def find_stale_pages(*, wiki_dir: Path, vault_dir: Path, documents_dir: Path) -> list[dict[str, Any]]:
    """Return pages whose source fingerprint no longer matches current sources."""
    wiki_dir = Path(wiki_dir)
    if not wiki_dir.is_dir():
        return []

    stale_pages: list[dict[str, Any]] = []
    for path in sorted(wiki_dir.rglob("*.md")):
        rel = path.relative_to(wiki_dir)
        if rel.parent == Path(".") and rel.name in _SYSTEM_ROOT_PAGES:
            continue

        meta, _ = parse_frontmatter(path)
        sources = [str(item) for item in meta.get("sources", [])]
        if not sources:
            continue

        stored_fingerprint = str(meta.get("source_fingerprint", "") or "")
        if not stored_fingerprint:
            continue
        current_fingerprint = compute_source_fingerprint(sources)
        if stored_fingerprint == current_fingerprint:
            continue

        stale_pages.append({
            "page": str(rel.with_suffix("")),
            "title": meta.get("title", path.stem),
            "hub": meta.get("hub", ""),
            "sources": sources,
        })

    return stale_pages


def backfill_source_fingerprints(*, wiki_dir: Path, runtime_wiki_dir: Path) -> dict[str, Any]:
    """Add missing source fingerprints to existing wiki pages without rewriting content."""
    wiki_dir = Path(wiki_dir)
    runtime_wiki_dir = Path(runtime_wiki_dir)
    if not wiki_dir.is_dir():
        return {"updated_pages": 0, "pages_scanned": 0, "path": str(wiki_dir)}

    pages_scanned = 0
    updated_pages = 0
    for path in sorted(wiki_dir.rglob("*.md")):
        rel = path.relative_to(wiki_dir)
        if rel.parent == Path(".") and rel.name in _SYSTEM_ROOT_PAGES:
            continue

        meta, body = parse_frontmatter(path)
        pages_scanned += 1
        if meta.get("source_fingerprint"):
            continue

        sources = [str(item) for item in meta.get("sources", [])]
        if not sources:
            continue

        write_vault_frontmatter(
            path,
            {**meta, "source_fingerprint": compute_source_fingerprint(sources)},
            body,
        )
        updated_pages += 1

    WikiPages(wiki_dir=wiki_dir, runtime_wiki_dir=runtime_wiki_dir).refresh_metadata()
    return {
        "updated_pages": updated_pages,
        "pages_scanned": pages_scanned,
        "path": str(wiki_dir),
    }


def find_rewrite_candidates(
    *,
    wiki_dir: Path,
    ask_outcomes: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Flag pages whose content shape suggests they should be rewritten."""
    wiki_dir = Path(wiki_dir)
    if not wiki_dir.is_dir():
        return []

    bodies: dict[str, str] = {}
    metas: dict[str, dict[str, Any]] = {}
    outgoing_counts: dict[str, int] = {}
    for path in sorted(wiki_dir.rglob("*.md")):
        rel = path.relative_to(wiki_dir)
        if rel.parent == Path(".") and rel.name in _SYSTEM_ROOT_PAGES:
            continue
        page = str(rel.with_suffix(""))
        meta, body = parse_frontmatter(path)
        metas[page] = meta
        bodies[page] = body
        outgoing_counts[page] = len(WIKILINK_RE.findall(body))

    candidates: list[dict[str, Any]] = []
    for page, body in bodies.items():
        meta = metas[page]
        quality = assess_page_quality(
            page=page,
            page_type=str(meta.get("page_type") or ""),
            hub=str(meta.get("hub", "") or ""),
            tags=meta.get("tags", []) if isinstance(meta.get("tags"), list) else [],
            sources=meta.get("sources", []) if isinstance(meta.get("sources"), list) else [],
            body=body,
            cross_ref_count=outgoing_counts[page],
            compiler_version=str(meta.get("compiler_version") or ""),
            article_metadata=meta.get("article_metadata")
            if isinstance(meta.get("article_metadata"), dict)
            else None,
            ask_outcomes=ask_outcomes,
        )
        reasons = list(quality["quality_flags"])
        quality_score = int(quality["quality_score"])

        article_metadata = meta.get("article_metadata")
        if isinstance(article_metadata, dict) and article_metadata.get("needs_richer_article"):
            quality_score = min(quality_score, 72)

        sources = meta.get("sources", []) if isinstance(meta.get("sources"), list) else []
        tags = meta.get("tags", []) if isinstance(meta.get("tags"), list) else []
        stored_fingerprint = str(meta.get("source_fingerprint", "") or "")
        if (
            stored_fingerprint
            and sources
            and "seed" not in {str(tag).lower() for tag in tags}
            and stored_fingerprint != compute_source_fingerprint([str(source) for source in sources])
        ):
            reasons.append("stale_synthesis")
            reasons.append("stale_claim_pressure")
            quality_score = min(quality_score, 60)

        if "contradiction_pressure" in reasons:
            quality_score = min(quality_score, 70)
        if "stale_claim_pressure" in reasons:
            quality_score = min(quality_score, 62)

        if not _quality_reasons_keep_rewrite_candidate(quality_score=quality_score, reasons=reasons):
            continue
        candidates.append({
            "page": page,
            "title": meta.get("title", Path(page).name.replace("-", " ").title()),
            "hub": meta.get("hub", ""),
            "quality_score": quality_score,
            "reasons": reasons,
        })

    candidates.sort(key=lambda item: (item["quality_score"], item["page"]))
    return candidates


def _quality_reasons_keep_rewrite_candidate(*, quality_score: int, reasons: list[str]) -> bool:
    if quality_score < 75:
        return True
    return any(reason in _FORCE_REWRITE_QUALITY_REASONS for reason in reasons)


def build_rewrite_proposals(
    *,
    wiki_dir: Path,
    runtime_wiki_dir: Path,
    sources: list[dict[str, Any]] | None = None,
    ask_outcomes: list[dict[str, Any]] | None = None,
    max_proposals: int = 20,
) -> list[dict[str, Any]]:
    """Combine stale-page debt with fresh ask and change signals into rewrite proposals."""
    wiki_dir = Path(wiki_dir)
    runtime_wiki_dir = Path(runtime_wiki_dir)
    if not wiki_dir.is_dir():
        return []

    wp = WikiPages(wiki_dir=wiki_dir, runtime_wiki_dir=runtime_wiki_dir)
    tag_manifest = wp.read_tags()
    pages = tag_manifest.get("pages", {}) if isinstance(tag_manifest, dict) else {}
    proposals: dict[str, dict[str, Any]] = {}

    for candidate in find_rewrite_candidates(wiki_dir=wiki_dir, ask_outcomes=ask_outcomes):
        proposal = _ensure_rewrite_proposal(proposals, pages, candidate["page"])
        if proposal is None:
            continue
        proposal["reasons"].update(str(reason) for reason in candidate.get("reasons", []))
        proposal["quality_score"] = int(candidate.get("quality_score", proposal["quality_score"]))

    hub_source_paths: dict[str, set[str]] = {}
    for source in sources or []:
        hub_name = str(source.get("hub", "")).strip()
        path = str(source.get("path", "")).strip()
        if not hub_name or not path:
            continue
        hub_source_paths.setdefault(hub_name, set()).add(path)

    for page, page_meta in pages.items():
        if not isinstance(page_meta, dict) or not page.endswith("/overview"):
            continue
        hub_name = str(page_meta.get("hub") or page.split("/", 1)[0]).strip()
        current_paths = hub_source_paths.get(hub_name, set())
        if not current_paths:
            continue
        stored_paths = {
            str(item).strip()
            for item in page_meta.get("sources", [])
            if str(item).strip()
        }
        if current_paths.issubset(stored_paths):
            continue
        proposal = _ensure_rewrite_proposal(proposals, pages, page)
        if proposal is None:
            continue
        proposal["reasons"].add("source_coverage_gap")
        proposal["quality_score"] = min(int(proposal["quality_score"]), 72)

    if ask_outcomes:
        try:
            from .ask_sync_clusters import cluster_ask_outcomes, suggest_page_targets
        except ImportError:
            from ask_sync_clusters import cluster_ask_outcomes, suggest_page_targets

        clusters = suggest_page_targets(cluster_ask_outcomes(ask_outcomes), tag_manifest)
        for cluster in clusters:
            page = _primary_cluster_target(cluster, pages)
            if not page:
                continue
            proposal = _ensure_rewrite_proposal(proposals, pages, page)
            if proposal is None:
                continue
            proposal["reasons"].add("ask_cluster")
            proposal["new_signal_counts"]["ask_clusters"] += 1
            proposal["new_signal_counts"]["ask_items"] += int(cluster.get("item_count", 0) or 0)
            proposal["ask_clusters"].append({
                "label": str(cluster.get("label", "")).strip(),
                "summary": str(cluster.get("summary", "")).strip(),
                "item_count": int(cluster.get("item_count", 0) or 0),
                "shared_kinds": [str(kind) for kind in cluster.get("shared_kinds", [])],
                "highlights": _cluster_highlights(
                    cluster,
                    page=page,
                    page_meta=pages.get(page, {}),
                ),
            })

    for source in sources or []:
        surface = str(source.get("source_surface", "")).strip()
        if surface not in {"git_history", "project_deltas"}:
            continue
        hub = str(source.get("hub", "")).strip()
        page = f"{hub}/overview" if hub else ""
        if not page or page not in pages:
            continue
        proposal = _ensure_rewrite_proposal(proposals, pages, page)
        if proposal is None:
            continue
        proposal["reasons"].add("change_signal")
        proposal["new_signal_counts"][surface] += 1
        proposal["change_signals"][surface].append(str(source.get("title", "")).strip())

    finalized: list[dict[str, Any]] = []
    for proposal in proposals.values():
        if not proposal["reasons"]:
            continue
        finalized_proposal = _finalize_rewrite_proposal(proposal)
        if finalized_proposal["proposal_fingerprint"] == _stored_rewrite_signal_fingerprint(
            wiki_dir=wiki_dir,
            page=finalized_proposal["page"],
        ):
            continue
        finalized.append(finalized_proposal)

    finalized.sort(
        key=lambda item: (
            item["priority_score"],
            item["new_signal_counts"]["ask_clusters"],
            item["new_signal_counts"]["git_history"] + item["new_signal_counts"]["project_deltas"],
            -item["quality_score"],
            item["page"],
        ),
        reverse=True,
    )
    return finalized[: max(max_proposals, 0)]


def _ensure_rewrite_proposal(
    proposals: dict[str, dict[str, Any]],
    pages: dict[str, Any],
    page: str,
) -> dict[str, Any] | None:
    page_meta = pages.get(page)
    if not isinstance(page_meta, dict):
        return None
    proposal = proposals.get(page)
    if proposal is not None:
        return proposal

    page_parts = [part for part in page.split("/") if part]
    hub = page_parts[0] if page_parts else ""
    proposal = {
        "page": page,
        "title": str(page_meta.get("title") or Path(page).name.replace("-", " ").title()),
        "hub": hub,
        "reasons": set(),
        "quality_score": 100,
        "new_signal_counts": {
            "ask_clusters": 0,
            "ask_items": 0,
            "git_history": 0,
            "project_deltas": 0,
        },
        "ask_clusters": [],
        "change_signals": {
            "git_history": [],
            "project_deltas": [],
        },
    }
    proposals[page] = proposal
    return proposal


def _primary_cluster_target(cluster: dict[str, Any], pages: dict[str, Any]) -> str:
    for target in cluster.get("page_targets", []):
        page = str(target.get("page", "")).strip()
        if page and page in pages:
            return page
    hub = str(cluster.get("hub", "")).strip()
    overview_page = f"{hub}/overview" if hub else ""
    if overview_page in pages:
        return overview_page
    return ""


def _finalize_rewrite_proposal(proposal: dict[str, Any]) -> dict[str, Any]:
    ask_clusters = proposal["ask_clusters"]
    change_signals = proposal["change_signals"]
    new_signal_counts = dict(proposal["new_signal_counts"])
    reasons = sorted(str(reason) for reason in proposal["reasons"])
    priority_score = round(
        (1.0 if "stale_synthesis" in reasons else 0.0)
        + (0.9 if "stale_claim_pressure" in reasons else 0.0)
        + (0.8 if "deep_structure_gap" in reasons else 0.0)
        + (0.7 if "deep_content_gap" in reasons else 0.0)
        + (0.65 if "source_coverage_gap" in reasons else 0.0)
        + (0.6 if "contradiction_pressure" in reasons else 0.0)
        + (0.55 if "generic_current_reality" in reasons else 0.0)
        + (0.6 if "generic_source_doctrine" in reasons else 0.0)
        + new_signal_counts["ask_clusters"] * 0.9
        + min(new_signal_counts["ask_items"], 3) * 0.2
        + min(new_signal_counts["git_history"], 5) * 0.15
        + min(new_signal_counts["project_deltas"], 5) * 0.2
        + max(0, 75 - int(proposal["quality_score"])) / 100.0,
        3,
    )
    finalized = {
        "page": proposal["page"],
        "title": proposal["title"],
        "hub": proposal["hub"],
        "reasons": reasons,
        "quality_score": int(proposal["quality_score"]),
        "new_signal_counts": new_signal_counts,
        "ask_clusters": ask_clusters,
        "change_signals": {
            surface: signals[:5]
            for surface, signals in change_signals.items()
            if signals
        },
        "rewrite_brief": _rewrite_brief(proposal),
        "priority_score": priority_score,
    }
    finalized["proposal_fingerprint"] = _proposal_fingerprint(finalized)
    return finalized


def _rewrite_brief(proposal: dict[str, Any]) -> str:
    reasons = proposal["reasons"]
    counts = proposal["new_signal_counts"]
    ask_summary = ""
    if counts["ask_clusters"]:
        ask_summaries = _ask_cluster_sentences(proposal["ask_clusters"], limit=1)
        ask_summary = ask_summaries[0] if ask_summaries else ""
    ask_rationale = _ask_rationale_phrase(ask_summary)

    change_total = counts["git_history"] + counts["project_deltas"]
    has_stale = "stale_synthesis" in reasons
    change_rationale = _change_rationale_phrase(proposal.get("change_signals", {}))

    if ask_summary and change_total:
        return (
            f"Retained /ask signals have sharpened the direction here, especially toward "
            f"{_lowercase_first(ask_rationale)}, "
            f"and {change_rationale.rstrip('.').lower()}."
        )
    if ask_summary and "contradiction_pressure" in reasons:
        return (
            f"Retained /ask contradiction signals now point this page toward "
            f"{_lowercase_first(ask_rationale)}."
        )
    if ask_summary and has_stale:
        return (
            f"The underlying source mix has shifted, and retained /ask signals now point more clearly toward "
            f"{_lowercase_first(ask_rationale)}."
        )
    if ask_summary:
        return (
            f"Retained /ask signals have sharpened the direction here, especially toward "
            f"{_lowercase_first(ask_rationale)}."
        )
    if change_total and has_stale:
        return (
            "The source mix has shifted, and "
            f"{change_rationale.rstrip('.').lower()}."
        )
    if change_total:
        return change_rationale
    if has_stale:
        return "The underlying source mix has shifted enough that this page now needs a fresh synthesis."
    return "This page has accumulated enough new signal to justify a fresh synthesis pass."


def _proposal_fingerprint(proposal: dict[str, Any]) -> str:
    normalized_change_signals = {
        str(surface): sorted(dict.fromkeys(str(item).strip() for item in items if str(item).strip()))
        for surface, items in dict(proposal.get("change_signals", {})).items()
        if [str(item).strip() for item in items if str(item).strip()]
    }
    payload = {
        "page": proposal["page"],
        "reasons": sorted(str(reason) for reason in proposal.get("reasons", [])),
        "ask_clusters": [
            {
                "label": str(cluster.get("label", "")).strip(),
                "summary": str(cluster.get("summary", "")).strip(),
                "item_count": int(cluster.get("item_count", 0) or 0),
                "highlights": sorted(dict.fromkeys(str(item).strip() for item in cluster.get("highlights", []))),
            }
            for cluster in proposal.get("ask_clusters", [])
        ],
        "change_signals": normalized_change_signals,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def _stored_rewrite_signal_fingerprint(*, wiki_dir: Path, page: str) -> str:
    path = Path(wiki_dir) / f"{page}.md"
    if not path.exists():
        return ""
    meta, _ = parse_frontmatter(path)
    return str(meta.get("rewrite_signal_fingerprint", "") or "")


def apply_top_rewrite_proposal(
    *,
    wiki_dir: Path,
    runtime_wiki_dir: Path,
    sources: list[dict[str, Any]] | None = None,
    ask_outcomes: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """Rewrite the highest-priority proposal page, preserving page metadata."""
    results = apply_rewrite_proposals(
        wiki_dir=wiki_dir,
        runtime_wiki_dir=runtime_wiki_dir,
        sources=sources,
        ask_outcomes=ask_outcomes,
        limit=1,
    )
    return results[0] if results else None


def apply_rewrite_proposals(
    *,
    wiki_dir: Path,
    runtime_wiki_dir: Path,
    sources: list[dict[str, Any]] | None = None,
    ask_outcomes: list[dict[str, Any]] | None = None,
    limit: int = 1,
) -> list[dict[str, Any]]:
    """Rewrite up to N highest-priority proposal pages."""
    proposals = build_rewrite_proposals(
        wiki_dir=wiki_dir,
        runtime_wiki_dir=runtime_wiki_dir,
        sources=sources,
        ask_outcomes=ask_outcomes,
        max_proposals=max(limit, 0),
    )
    if not proposals:
        return []

    wp = WikiPages(wiki_dir=Path(wiki_dir), runtime_wiki_dir=Path(runtime_wiki_dir))
    results: list[dict[str, Any]] = []
    for proposal in proposals[: max(limit, 0)]:
        existing = wp.read(proposal["page"])
        if existing is None:
            continue
        existing_meta, _ = parse_frontmatter(Path(wiki_dir) / f"{proposal['page']}.md")
        existing = {
            **existing,
            "compiler_version": str(existing_meta.get("compiler_version") or "").strip(),
        }

        resolved_sources = _rewrite_source_paths(existing=existing, proposal=proposal, sources=sources or [])
        existing_for_render = {**existing, "sources": resolved_sources}
        rendered = _render_rewrite_body(existing_for_render, proposal)
        if _is_v4_concept(existing):
            body = replace_compiled_truth(
                str(existing.get("body") or ""),
                _compiled_truth_from_rendered_rewrite(rendered),
            )
        else:
            body = rendered
        path = wp.write(
            page=proposal["page"],
            title=str(existing.get("title") or proposal["title"]),
            tags=[str(tag) for tag in existing.get("tags", [])],
            sources=resolved_sources,
            body=body,
            hub=str(existing.get("hub") or proposal["hub"]),
        )
        meta, written_body = parse_frontmatter(path)
        current_quality = assess_page_quality(
            page=proposal["page"],
            page_type=str(meta.get("page_type") or ""),
            hub=str(meta.get("hub", "") or proposal.get("hub", "")),
            tags=meta.get("tags", []) if isinstance(meta.get("tags"), list) else [],
            sources=meta.get("sources", []) if isinstance(meta.get("sources"), list) else [],
            body=written_body,
            cross_ref_count=len(WIKILINK_RE.findall(written_body)),
            compiler_version=str(meta.get("compiler_version") or ""),
            ask_outcomes=ask_outcomes,
        )
        current_quality_reasons = [
            str(reason)
            for reason in current_quality.get("quality_flags", [])
            if _quality_reasons_keep_rewrite_candidate(
                quality_score=int(current_quality.get("quality_score", 100)),
                reasons=[str(flag) for flag in current_quality.get("quality_flags", [])],
            )
        ]
        remaining_signal_reasons = [
            reason
            for reason in proposal.get("reasons", [])
            if reason in {"ask_cluster", "change_signal", "contradiction_pressure"}
        ]
        consumed_fingerprint = _proposal_fingerprint(
            {
                **proposal,
                "reasons": sorted(
                    {
                        *remaining_signal_reasons,
                        *current_quality_reasons,
                    }
                ),
            }
        )
        article_metadata = {
            "needs_richer_article": "needs_richer_article" in current_quality_reasons,
            "quality_flags": current_quality_reasons,
        }
        write_vault_frontmatter(
            path,
            {**meta, "article_metadata": article_metadata},
            written_body.strip("\n"),
        )

        live_proposals = build_rewrite_proposals(
            wiki_dir=wiki_dir,
            runtime_wiki_dir=runtime_wiki_dir,
            sources=sources,
            ask_outcomes=ask_outcomes,
            max_proposals=max(len(wp.list_pages()), 20),
        )
        live_proposal = next(
            (item for item in live_proposals if str(item.get("page") or "") == str(proposal["page"])),
            None,
        )
        write_vault_frontmatter(
            path,
            {
                **meta,
                "article_metadata": article_metadata,
                "rewrite_signal_fingerprint": str(
                    live_proposal.get("proposal_fingerprint") if isinstance(live_proposal, dict) else consumed_fingerprint
                ),
            },
            written_body.strip("\n"),
        )

        results.append({
            **proposal,
            "path": str(path),
        })
    return results


def _is_v4_concept(existing: dict[str, Any]) -> bool:
    return (
        str(existing.get("page_type") or "").strip() == "concept"
        and str(existing.get("compiler_version") or "").strip() == "concept-article-v4"
    )


def _compiled_truth_from_rendered_rewrite(rendered: str) -> str:
    lines = rendered.strip().splitlines()
    if lines and lines[0].lstrip().startswith("# "):
        lines = lines[1:]
        while lines and not lines[0].strip():
            lines = lines[1:]
    lines = _drop_rendered_rewrite_section(lines, "Evidence")
    demoted = [
        "### " + line.removeprefix("## ").strip()
        if line.startswith("## ")
        else line
        for line in lines
    ]
    return "\n".join(demoted).strip()


def _drop_rendered_rewrite_section(lines: list[str], heading: str) -> list[str]:
    filtered: list[str] = []
    skipping = False
    target = f"## {heading}"
    for line in lines:
        if line.strip() == target:
            skipping = True
            continue
        if skipping and line.startswith("## "):
            skipping = False
        if not skipping:
            filtered.append(line)
    return filtered


def _rewrite_source_paths(
    *,
    existing: dict[str, Any],
    proposal: dict[str, Any],
    sources: list[dict[str, Any]],
) -> list[str]:
    hub = str(existing.get("hub") or proposal.get("hub") or "").strip()
    if not hub:
        return [str(source) for source in existing.get("sources", [])]

    matching_paths = [
        str(source.get("path", "")).strip()
        for source in sources
        if str(source.get("hub", "")).strip() == hub and str(source.get("path", "")).strip()
    ]
    if not matching_paths:
        return [str(source) for source in existing.get("sources", [])]
    return sorted(dict.fromkeys(matching_paths))


def _render_rewrite_body(existing: dict[str, Any], proposal: dict[str, Any]) -> str:
    title = str(existing.get("title") or proposal.get("title") or Path(str(proposal.get("page", "page"))).name.replace("-", " ").title())
    page = str(proposal.get("page", ""))
    hub = str(existing.get("hub") or proposal.get("hub") or "")
    ask_clusters = proposal.get("ask_clusters", [])
    change_signals = proposal.get("change_signals", {})
    source_paths = [str(source) for source in existing.get("sources", [])]
    intro = _current_reality_sentence(
        existing_body=str(existing.get("body") or ""),
        page=page,
        title=title,
        hub=hub,
        source_paths=source_paths,
        ask_clusters=ask_clusters,
        change_signals=change_signals,
        fallback=proposal["rewrite_brief"],
    )
    current_thesis = _current_thesis_sentence(
        intro=intro,
        ask_clusters=ask_clusters,
        change_signals=change_signals,
        source_paths=source_paths,
        hub=hub,
    )
    recent_shift = _recent_shift_sentence(ask_clusters, change_signals, source_paths=source_paths, hub=hub)
    open_tensions = _open_tensions_sentence(
        ask_clusters,
        change_signals,
        source_paths=source_paths,
        hub=hub,
    )
    if ask_clusters:
        evidence_lines = _format_ask_cluster_lines(ask_clusters)
    elif any(change_signals.values()):
        evidence_lines = _format_change_signal_lines(change_signals)
    else:
        evidence_lines = _source_evidence_lines(source_paths)

    lines = [
        f"# {title}",
        "",
        "## Current Thesis",
        "",
        current_thesis,
        "",
        "## What This Hub Knows",
        "",
        intro,
        "",
        "## Recent Additions",
        "",
        recent_shift,
        "",
    ]

    if open_tensions:
        lines.extend([
            "## Open Questions",
            "",
            open_tensions,
            "",
        ])

    if evidence_lines:
        lines.extend([
            "## Supporting Signals",
            "",
            *evidence_lines,
            "",
        ])

    return "\n".join(lines).strip()


def _first_meaningful_paragraph(body: str) -> str:
    paragraphs: list[str] = []
    current: list[str] = []
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line:
            if current:
                paragraphs.append(" ".join(current).strip())
                current = []
            continue
        if line.startswith("#") or line.startswith("- ") or line.startswith("* "):
            if current:
                paragraphs.append(" ".join(current).strip())
                current = []
            continue
        current.append(line)
    if current:
        paragraphs.append(" ".join(current).strip())
    return paragraphs[0] if paragraphs else ""


def _existing_current_reality(body: str) -> str:
    section = _extract_section(body, "What This Hub Knows") or _extract_section(body, "Current Reality")
    thesis = _first_meaningful_paragraph(_extract_section(body, "Current Thesis"))
    if section:
        current = _first_meaningful_paragraph(section)
        if (
            current
            and _summary_key(current) != _summary_key(thesis)
            and not _looks_like_scope_scaffold(current)
            and not _looks_like_placeholder_reality(current)
            and not _looks_like_generic_source_current_reality(current)
        ):
            return current
        return ""
    current = _first_meaningful_paragraph(body)
    if (
        current
        and not _looks_like_scope_scaffold(current)
        and not _looks_like_placeholder_reality(current)
        and not _looks_like_generic_source_current_reality(current)
    ):
        return current
    return ""


def _extract_section(body: str, heading: str) -> str:
    pattern = re.compile(
        rf"^## {re.escape(heading)}\s*$\n(?P<section>.*?)(?=^## |\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(body)
    if not match:
        return ""
    return match.group("section").strip()


def _looks_like_scope_scaffold(text: str) -> bool:
    normalized = text.lower()
    return "is the compiled overview for the" in normalized


def _looks_like_placeholder_reality(text: str) -> bool:
    normalized = " ".join(text.lower().split())
    if normalized in {
        "old positioning summary.",
        "old positioning summary",
        "existing dev synthesis.",
        "existing dev synthesis",
        "metadata-only seed page generated from scanned sources.",
        "metadata-only seed page generated from scanned sources",
    }:
        return True
    if len(normalized) < 120 and any(
        token in normalized
        for token in ("old ", "existing ", "summary", "synthesis", "metadata-only seed")
    ):
        return True
    return False


def _looks_like_generic_source_current_reality(text: str) -> bool:
    normalized = " ".join(text.lower().split())
    return (
        "currently draws most of its working knowledge from" in normalized
        and "it should explain how those materials fit together in practice" in normalized
    ) or (
        "currently concentrates on" in normalized
        and "it should explain how those strands fit together in practice" in normalized
    )


def _current_reality_sentence(
    *,
    existing_body: str,
    page: str,
    title: str,
    hub: str,
    source_paths: list[str],
    ask_clusters: list[dict[str, Any]],
    change_signals: dict[str, list[str]],
    fallback: str,
) -> str:
    existing = _existing_current_reality(existing_body)
    if existing and not _looks_like_scope_scaffold(existing):
        return existing

    ask_summary = _ask_cluster_sentences(ask_clusters, limit=1)
    normalized_ask = ask_summary[0].lower() if ask_summary else ""

    if hub == "venture-augur" or "founder-plus-product-builder identity" in normalized_ask:
        return (
            "The venture-augur hub is the business and positioning layer for Augur as a product. "
            "It gathers the material that defines how Augur should be framed to the outside world."
        )
    if hub == "dev" or (change_signals.get("git_history") and change_signals.get("project_deltas")):
        return (
            "The dev hub explains how Augur is built and changed. "
            "It sits where architecture intent, workflow policy, and shipped implementation meet."
        )
    if hub == "ai":
        return (
            "The AI hub documents how Augur uses agents in practice. "
            "It explains the boundary between orchestration by agents and bounded execution through MCP tools."
        )
    role_fragments = _source_role_fragments(source_paths)
    if hub and len(role_fragments) >= 2:
        lead = role_fragments[0]
        tail = role_fragments[1]
        if len(role_fragments) >= 3:
            return (
                f"The {hub.replace('-', ' ')} hub currently combines {lead}, {tail}, "
                f"and {role_fragments[2]}."
            )
        return f"The {hub.replace('-', ' ')} hub currently combines {lead} with {tail}."
    themes = _source_theme_labels(source_paths)
    skill_brief = _skill_source_brief(source_paths)
    if hub and skill_brief:
        skill_name, description = skill_brief
        return (
            f"The {hub.replace('-', ' ')} hub is anchored by the {skill_name} skill. "
            f"{description}"
        )
    if hub and themes:
        return (
            f"The {hub.replace('-', ' ')} hub currently concentrates on "
            f"{_human_join(themes[:4])}. It should explain how those strands fit together in practice."
        )
    if hub and source_paths:
        focus = _source_focus_labels(source_paths)
        if focus:
            return (
                f"The {hub.replace('-', ' ')} hub currently draws most of its working knowledge from "
                f"{_human_join(focus[:2])}. It should explain how those materials fit together in practice."
            )
        return (
            f"The {hub.replace('-', ' ')} hub currently draws on a compact source base. "
            "It should explain how that material fits together in practice."
        )

    derived = _first_meaningful_paragraph(existing_body)
    if derived and not _looks_like_scope_scaffold(derived):
        return derived
    return fallback


def _current_thesis_sentence(
    *,
    intro: str,
    ask_clusters: list[dict[str, Any]],
    change_signals: dict[str, list[str]],
    source_paths: list[str],
    hub: str,
) -> str:
    pattern = _core_pattern_sentence(
        intro=intro,
        ask_clusters=ask_clusters,
        change_signals=change_signals,
        source_paths=source_paths,
        hub=hub,
    )
    normalized = pattern.strip()
    if normalized.startswith("The durable pattern here is that "):
        return _uppercase_first(normalized.removeprefix("The durable pattern here is that "))
    if normalized.startswith("The durable pattern here is to "):
        return _ensure_sentence(
            "This hub is strongest when it can "
            + normalized.removeprefix("The durable pattern here is to ").rstrip(".")
        )
    if normalized.startswith("The durable pattern here is "):
        return _uppercase_first(normalized.removeprefix("The durable pattern here is "))
    return pattern


def _emerging_direction_sentence(ask_clusters: list[dict[str, Any]]) -> str:
    summaries = _ask_cluster_sentences(ask_clusters)
    summaries = [summary for summary in summaries if summary]
    if not summaries:
        return "Retained /ask outcomes now point this page toward a sharper synthesis of the current direction."
    primary = summaries[0]
    if len(summaries) == 1:
        return _ensure_sentence(primary)
    secondary = summaries[1]
    return f"{_ensure_sentence(primary)} A second signal is that {_lowercase_first(secondary)}."


def _recent_delivery_sentence(change_signals: dict[str, list[str]]) -> str:
    fragments = _change_signal_fragments(change_signals)
    if not fragments:
        return "Recent shipped changes should now be reflected in this page."
    if len(fragments) == 1:
        return f"Recent delivery is anchored by {fragments[0]}."
    return f"Recent delivery is anchored by {fragments[0]}, alongside {fragments[1]}."


def _recent_shift_sentence(
    ask_clusters: list[dict[str, Any]],
    change_signals: dict[str, list[str]],
    *,
    source_paths: list[str] | None = None,
    hub: str = "",
) -> str:
    ask_shift = _emerging_direction_sentence(ask_clusters) if ask_clusters else ""
    change_shift = _recent_delivery_sentence(change_signals) if change_signals else ""

    if ask_shift and change_shift:
        return f"{ask_shift} {change_shift}"
    if ask_shift:
        return ask_shift
    if change_shift:
        return change_shift
    source_shift = _source_base_shift_sentence(source_paths or [], hub=hub)
    if source_shift:
        return source_shift
    return "This area has accumulated enough new signal to justify a fresh synthesis."


def _format_ask_cluster_lines(ask_clusters: list[dict[str, Any]]) -> list[str]:
    lines = [f"- {summary}" for summary in _ask_cluster_sentences(ask_clusters, limit=3)]
    return lines or ["- Retained /ask outcomes are pushing this page toward a fresher synthesis."]


def _page_scope_sentence(*, page: str, title: str, hub: str) -> str:
    label = hub.replace("-", " ").strip() if hub else Path(page).parent.name.replace("-", " ").strip()
    page_label = title.strip() or Path(page).name.replace("-", " ").title()
    if label:
        return (
            f"{page_label} is the compiled overview for the {label} hub. "
            "It should hold the durable model of what matters here, what is changing, "
            "and where the active tensions now sit."
        )
    return (
        f"{page_label} is a compiled wiki page. "
        "It should hold the durable model of what matters here, what is changing, "
        "and where the active tensions now sit."
    )


def _core_pattern_sentence(
    *,
    intro: str,
    ask_clusters: list[dict[str, Any]],
    change_signals: dict[str, list[str]],
    source_paths: list[str],
    hub: str = "",
) -> str:
    intro_sentences = _sentences(intro)

    ask_summary = _ask_cluster_sentences(ask_clusters, limit=1)
    normalized_ask = ask_summary[0].lower() if ask_summary else ""
    if "founder-plus-product-builder identity" in normalized_ask:
        return (
            "The durable pattern here is that positioning gets stronger when Augur is framed as a product with ownership and direction, not as a generic services offering."
        )
    if "compiled brain" in normalized_ask or "wiki" in normalized_ask:
        return (
            "The durable pattern here is that the wiki should compound from retained signals over time instead of behaving like a static archive."
        )
    normalized_intro = intro.lower()
    if "agents do judgment and orchestration" in normalized_intro and "mcp tools perform bounded operations" in normalized_intro:
        return (
            "The durable pattern here is to keep agent judgment, MCP execution, and workflow discipline in the same operating model."
        )

    if change_signals.get("git_history") and change_signals.get("project_deltas"):
        return (
            "The durable pattern here is to keep architecture intent, workflow policy, and shipped implementation in the same frame."
        )
    if change_signals.get("git_history"):
        return "The durable pattern here is to keep shipped implementation changes anchored to the stable operating model."
    if change_signals.get("project_deltas"):
        return "The durable pattern here is to keep active plans and specs tied to the stable operating model."
    themes = _source_theme_labels(source_paths)
    skill_brief = _skill_source_brief(source_paths)
    if skill_brief:
        _, description = skill_brief
        return (
            "The durable pattern here is to keep the hub aligned with its core brief: "
            f"{_lowercase_first(description)}"
        )
    if themes:
        return (
            f"The durable pattern here is to keep {_human_join(themes[:3])} in one practical operating model."
        )
    focus = _source_focus_labels(source_paths)
    if hub and focus:
        return (
            f"The durable pattern here is to turn {_human_join(focus[:2])} materials into one practical operating model."
        )
    if len(intro_sentences) >= 2:
        return _ensure_sentence(intro_sentences[1])
    if intro_sentences:
        return _ensure_sentence(intro_sentences[0])
    return "The durable pattern here is still being clarified by the source set."


def _open_tensions_sentence(
    ask_clusters: list[dict[str, Any]],
    change_signals: dict[str, list[str]],
    *,
    source_paths: list[str] | None = None,
    hub: str = "",
) -> str:
    ask_summary = _ask_cluster_sentences(ask_clusters, limit=1)
    normalized_ask = ask_summary[0].lower() if ask_summary else ""

    if "move away from consultancy and ai infrastructure consultant framing" in normalized_ask:
        return (
            "Older consultancy framing still exists across the source set, so this page needs to keep translating legacy materials into the newer founder-plus-product-builder story."
        )
    if "move away from consultancy framing" in normalized_ask:
        return (
            "Older consultancy framing still exists across the source set, so this page needs to keep translating legacy materials into the newer product story."
        )
    if "stop leading with ai infrastructure consultant" in normalized_ask:
        return (
            "Some materials still carry the AI Infrastructure Consultant label, even as the stronger direction shifts toward a broader product identity."
        )

    if change_signals.get("git_history") and change_signals.get("project_deltas"):
        return (
            "Shipped changes and active plans are moving together, but this page still needs to reconcile what is already implemented with what is still being designed."
        )
    role_labels = [profile["role"] for profile in _source_role_profiles(source_paths or [])]
    if "reference context" in role_labels and "tasks and ideas" in role_labels:
        return (
            "The open tension here is that reference context is getting clearer, but the page still needs stronger doctrine connecting it to the active tasks and ideas."
        )
    themes = _source_theme_labels(source_paths or [])
    if themes:
        return (
            f"The open tension here is that the source base is starting to cluster around {_human_join(themes[:4])}, "
            "but the page still needs a stronger doctrine that explains how those strands fit together."
        )
    focus = _source_focus_labels(source_paths or [])
    if hub == "ai" and focus:
        return (
            "The open tension here is that workflow coverage is growing faster than the shared doctrine that explains how those workflows fit together."
        )
    if focus:
        return (
            f"The open tension here is that the source base is starting to cluster around {_human_join(focus[:2])}, "
            "but the page still needs a stronger doctrine that explains how those materials fit together."
        )
    return ""


def _clean_cluster_summary(summary: str) -> str:
    text = " ".join(summary.split()).strip()
    if not text:
        return ""

    text = re.sub(r"^[^:]+ centers on\s+", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^[^:]+ highlights\s+", "", text, flags=re.IGNORECASE)
    parts = re.split(r";\s*it also highlights\s+|(?:^|\.\s+)it also suggests\s+", text, flags=re.IGNORECASE)

    cleaned: list[str] = []
    seen: set[str] = set()
    for part in parts:
        clause = part.strip(" .;")
        if not clause:
            continue
        normalized = clause.lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        cleaned.append(clause)

    if not cleaned:
        return text
    if len(cleaned) == 1:
        return cleaned[0]
    return f"{cleaned[0]}. It also suggests {cleaned[1][0].lower() + cleaned[1][1:] if len(cleaned[1]) > 1 else cleaned[1].lower()}."


def _cluster_highlights(
    cluster: dict[str, Any],
    *,
    page: str,
    page_meta: dict[str, Any] | None = None,
    limit: int = 2,
) -> list[str]:
    page_meta = page_meta or {}
    page_tokens = _page_relevance_tokens(page, page_meta)
    scored_items: list[tuple[int, str]] = []

    for item in cluster.get("items", []):
        summary = _compress_highlight_text(str(item.get("summary", "")), hub=page.split("/", 1)[0] if "/" in page else page)
        if not summary:
            continue
        score = _ask_item_relevance_score(item, page=page, page_meta=page_meta, page_tokens=page_tokens)
        scored_items.append((score, summary))

    scored_items.sort(key=lambda item: (item[0], len(item[1])), reverse=True)

    highlights: list[str] = []
    for _, summary in scored_items:
        if _is_redundant_summary(summary, highlights):
            continue
        highlights.append(summary)
        if len(highlights) >= limit:
            break
    return highlights


def _ask_cluster_sentences(ask_clusters: list[dict[str, Any]], *, limit: int = 2) -> list[str]:
    raw_sentences: list[str] = []
    for cluster in ask_clusters:
        highlights = [str(item).strip() for item in cluster.get("highlights", []) if str(item).strip()]
        if highlights:
            candidates = highlights
        else:
            cleaned = _clean_cluster_summary(str(cluster.get("summary", "")).strip())
            candidates = [cleaned] if cleaned else []
        for candidate in candidates:
            normalized = candidate.lower().rstrip(".")
            if not normalized or _is_redundant_summary(candidate, raw_sentences):
                continue
            raw_sentences.append(candidate.rstrip("."))
    if not raw_sentences:
        return []

    merged_sentences = _merge_related_ask_sentences(raw_sentences)
    return merged_sentences[:limit]


def _merge_related_ask_sentences(sentences: list[str]) -> list[str]:
    normalized_sentences = [sentence.strip().rstrip(".") for sentence in sentences if sentence.strip()]
    if not normalized_sentences:
        return []

    merged: list[str] = []
    consumed: set[int] = set()

    positioning_indexes = [
        index
        for index, sentence in enumerate(normalized_sentences)
        if _is_positioning_shift_signal(sentence)
    ]
    if positioning_indexes:
        positioning_sentences = [normalized_sentences[index] for index in positioning_indexes]
        merged_positioning = _merge_positioning_shift(positioning_sentences)
        if merged_positioning:
            merged.append(merged_positioning)
            consumed.update(positioning_indexes)

    for index, sentence in enumerate(normalized_sentences):
        if index in consumed:
            continue
        if _is_redundant_summary(sentence, merged):
            continue
        merged.append(sentence)
    return merged


def _is_positioning_shift_signal(sentence: str) -> bool:
    normalized = sentence.lower()
    return any(
        token in normalized
        for token in (
            "founder",
            "product-builder",
            "consultancy",
            "ai infrastructure consultant",
            "service-led",
        )
    )


def _merge_positioning_shift(sentences: list[str]) -> str:
    normalized = " ".join(sentences).lower()
    has_founder_identity = "founder" in normalized or "product-builder" in normalized
    has_consultancy = "consultancy" in normalized
    has_ai_infra = "ai infrastructure consultant" in normalized
    has_service_led = "service-led" in normalized

    if not has_founder_identity:
        return ""

    target = "Augur should move toward a founder-plus-product-builder identity"
    if has_consultancy and has_ai_infra:
        return (
            "Augur should move away from consultancy and AI Infrastructure Consultant framing "
            "toward a founder-plus-product-builder identity"
        )
    if has_consultancy:
        return "Augur should move away from consultancy framing toward a founder-plus-product-builder identity"
    if has_ai_infra or has_service_led:
        return (
            "Augur should stop leading with AI Infrastructure Consultant framing and move toward "
            "a founder-plus-product-builder identity"
        )
    return target


def _ask_rationale_phrase(summary: str) -> str:
    stripped = summary.strip().rstrip(".")
    if not stripped:
        return "a sharper direction for this page"

    normalized = stripped.lower()
    if "founder-plus-product-builder identity" in normalized:
        if "consultancy" in normalized or "ai infrastructure consultant" in normalized:
            return "a more product-led founder identity for Augur"
        return "a clearer founder-plus-product-builder identity for Augur"
    if "compiled brain" in normalized or "upgrades itself in cycles" in normalized:
        return "a more compounding, self-improving wiki model"

    softened = re.sub(r"^Augur should\s+", "", stripped, flags=re.IGNORECASE)
    softened = re.sub(r"^You want\s+", "", softened, flags=re.IGNORECASE)
    softened = softened.strip()
    if softened:
        return softened[0].lower() + softened[1:] if not softened.startswith("Augur ") else softened
    return "a sharper direction for this page"


def _change_rationale_phrase(change_signals: dict[str, list[str]]) -> str:
    git_titles = [title for title in change_signals.get("git_history", []) if title]
    delta_titles = [title for title in change_signals.get("project_deltas", []) if title]

    if git_titles and delta_titles:
        return "The implementation story here has moved enough that recent commits and active plans now need to be read together."
    if git_titles:
        return "Recent commits have moved the implementation story enough to warrant a refresh here."
    if delta_titles:
        return "Active plans and specs have moved the implementation story enough to warrant a refresh here."
    return "Recent implementation activity has moved this page enough to justify a refresh."


def _sentences(text: str) -> list[str]:
    return [
        sentence.strip().rstrip(".")
        for sentence in re.split(r"(?<=[.!?])\s+", text.strip())
        if sentence.strip()
    ]


def _ensure_sentence(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        return stripped
    if stripped[-1] in ".!?":
        return stripped
    return f"{stripped}."


def _lowercase_first(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        return stripped
    if stripped.startswith("Augur "):
        return stripped
    return stripped[0].lower() + stripped[1:]


def _uppercase_first(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        return stripped
    return stripped[0].upper() + stripped[1:]


def _is_redundant_summary(candidate: str, existing_items: list[str]) -> bool:
    candidate_key = _summary_key(candidate)
    if not candidate_key:
        return True
    for existing in existing_items:
        existing_key = _summary_key(existing)
        if not existing_key:
            continue
        if candidate_key == existing_key:
            return True
        if candidate_key.startswith(existing_key[:120]) or existing_key.startswith(candidate_key[:120]):
            return True
    return False


def _summary_key(text: str) -> str:
    normalized = text.lower().replace("…", "").strip().rstrip(".")
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized


def _compress_highlight_text(text: str, *, hub: str = "", limit: int = 160) -> str:
    normalized = " ".join(text.split()).strip()
    if not normalized:
        return ""

    normalized = normalized.replace("…", "")
    sentences = [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", normalized)
        if sentence.strip()
    ]

    if sentences:
        first = sentences[0].rstrip(".")
        if len(first) <= limit:
            return _polish_highlight_style(first, hub=hub)

    clauses = [
        clause.strip(" ,;.")
        for clause in re.split(r"[.;]|,\s+(?:and|but)\s+", normalized)
        if clause.strip(" ,;.")
    ]
    if clauses:
        first_clause = clauses[0]
        if len(first_clause) <= limit:
            return _polish_highlight_style(_balance_terminal_quotes(first_clause), hub=hub)

    clipped = normalized[:limit].rstrip(" ,;.")
    return _polish_highlight_style(_balance_terminal_quotes(clipped), hub=hub)


def _balance_terminal_quotes(text: str) -> str:
    balanced = text.strip().rstrip(".")
    if balanced.count("'") % 2 == 1 and balanced.endswith("'"):
        balanced = balanced[:-1].rstrip()
    if balanced.count("'") % 2 == 1 and "'" in balanced:
        balanced = balanced.replace("'", "")
    return balanced


def _polish_highlight_style(text: str, *, hub: str = "") -> str:
    polished = text.strip()
    if not polished:
        return polished

    polished = re.sub(
        r"^Looking at where Augur is heading,\s*I would\s+",
        "Augur should ",
        polished,
        flags=re.IGNORECASE,
    )
    polished = re.sub(
        r"^I would\s+",
        "",
        polished,
        flags=re.IGNORECASE,
    )

    if hub in {"venture-augur", "business", "career-ops", "augur"}:
        polished = re.sub(
            r"^Lead with\s+",
            "Augur should lead with ",
            polished,
            flags=re.IGNORECASE,
        )
        polished = re.sub(
            r"^Stop leading with\s+",
            "Augur should stop leading with ",
            polished,
            flags=re.IGNORECASE,
        )

    return polished[0].upper() + polished[1:] if polished else polished


def _page_relevance_tokens(page: str, page_meta: dict[str, Any]) -> set[str]:
    tokens: set[str] = set()
    for part in page.split("/"):
        tokens.update(_normalize_relevance_term(part))
    tokens.update(_normalize_relevance_term(str(page_meta.get("title", ""))))
    for tag in page_meta.get("tags", []) if isinstance(page_meta.get("tags"), list) else []:
        tokens.update(_normalize_relevance_term(str(tag)))
    return tokens


def _ask_item_relevance_score(
    item: dict[str, Any],
    *,
    page: str,
    page_meta: dict[str, Any],
    page_tokens: set[str],
) -> int:
    score = 0
    item_hub = str(item.get("hub", "")).strip()
    page_hub = page.split("/", 1)[0] if "/" in page else page
    if item_hub and item_hub == page_hub:
        score += 6

    item_tags = {str(tag).strip() for tag in item.get("tags", []) if str(tag).strip()}
    page_tags = {str(tag).strip() for tag in page_meta.get("tags", []) if isinstance(page_meta.get("tags"), list)} if isinstance(page_meta.get("tags"), list) else set()
    score += len(item_tags & page_tags) * 3

    item_tokens: set[str] = set()
    item_tokens.update(_normalize_relevance_term(str(item.get("question", ""))))
    item_tokens.update(_normalize_relevance_term(str(item.get("summary", ""))))
    score += len(item_tokens & page_tokens)
    return score


def _normalize_relevance_term(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", text.lower().replace("-", " "))
        if len(token) > 2
    }


def _format_change_signal_lines(change_signals: dict[str, list[str]]) -> list[str]:
    lines = [f"- {fragment[0].upper() + fragment[1:]}" for fragment in _change_signal_fragments(change_signals)]
    return lines or ["- Recent shipped changes should be folded into this page."]


def _source_base_shift_sentence(source_paths: list[str], *, hub: str = "") -> str:
    if not source_paths:
        return ""
    count = len(source_paths)
    role_fragments = _source_role_fragments(source_paths)
    if len(role_fragments) >= 2:
        return (
            f"The source base now mixes {role_fragments[0]} with {role_fragments[1]}, "
            "so this page should explain how those layers work together."
        )
    themes = _source_theme_labels(source_paths)
    if themes:
        return (
            f"The source base currently draws on {count} files, with the strongest concentration around "
            f"{_human_join(themes[:4])}, so this page should turn that material into a clearer operating model."
        )
    focus = _source_focus_labels(source_paths)
    if focus:
        return (
            f"The source base currently draws on {count} files, with the strongest concentration around "
            f"{_human_join(focus[:2])}, so this page should turn that material into a clearer operating model."
        )
    if hub:
        return (
            f"The source base currently draws on {count} files for the {hub.replace('-', ' ')} hub, "
            "so this page should turn that material into a clearer operating model."
        )
    return (
        f"The source base currently draws on {count} files, so this page should turn that material into a clearer operating model."
    )


def _source_evidence_lines(source_paths: list[str]) -> list[str]:
    if not source_paths:
        return []
    count = len(source_paths)
    profiles = _source_role_profiles(source_paths)
    if len(profiles) >= 2:
        lines = [f"- Source base currently draws on {count} files"]
        for profile in profiles[:3]:
            lines.append(f"- {_source_role_fragment(profile)[0].upper() + _source_role_fragment(profile)[1:]}")
        return lines
    focus = _source_theme_labels(source_paths) or _source_focus_labels(source_paths)
    lines = [f"- Source base currently draws on {count} files"]
    if focus:
        lines.append(f"- Material is currently concentrated in {_human_join(focus[:4])}")
    return lines


def _skill_source_brief(source_paths: list[str]) -> tuple[str, str] | None:
    for source in source_paths:
        path = Path(source)
        if path.name != "SKILL.md" or not path.exists():
            continue
        try:
            meta, _ = parse_frontmatter(path)
        except OSError:
            continue
        description = " ".join(str(meta.get("description", "")).split()).strip()
        if not description:
            continue
        skill_name = str(meta.get("name") or path.parent.name.replace("-", " ")).strip()
        if description[-1] not in ".!?":
            description = f"{description}."
        return skill_name.replace("-", " "), description
    return None


def _source_theme_labels(source_paths: list[str]) -> list[str]:
    counts: Counter[str] = Counter()
    for source in source_paths:
        path = Path(source)
        if not path.exists() or path.suffix.lower() not in {".md", ".txt"}:
            continue
        try:
            meta, body = parse_frontmatter(path)
        except OSError:
            continue
        title = str(meta.get("title") or "").strip()
        counts.update(_source_theme_counter(meta=meta, body=body, title=title))
    return [label for label, _ in counts.most_common(4)]


def _source_theme_counter(*, meta: dict[str, Any], body: str, title: str) -> Counter[str]:
    counts: Counter[str] = Counter()
    for value in meta.get("tags", []) if isinstance(meta.get("tags"), list) else []:
        label = _normalize_source_theme_label(value)
        if label:
            counts[label] += 3
    for key in ("category", "data_type", "sync_target", "type"):
        label = _normalize_source_theme_label(meta.get(key))
        if label:
            counts[label] += 2
    for label in _title_theme_labels(title):
        counts[label] += 1
    body_weight = 5 if str(meta.get("sync_target", "")).strip().lower() == "reminders" else 2
    for label in _body_theme_labels(body):
        counts[label] += body_weight
    return counts


def _normalize_source_theme_label(value: Any) -> str:
    if value is None:
        return ""
    text = " ".join(str(value).replace("_", " ").replace("-", " ").lower().split()).strip()
    if not text or text in _GENERIC_SOURCE_THEME_LABELS:
        return ""
    return text


def _title_theme_labels(title: str) -> list[str]:
    return _theme_phrases_from_text(title)


def _body_theme_labels(body: str) -> list[str]:
    labels: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("- [ ] "):
            text = stripped[6:]
        elif stripped.startswith("- ") or stripped.startswith("* "):
            text = stripped[2:]
        else:
            text = stripped
        for label in _theme_phrases_from_text(text):
            if label not in labels:
                labels.append(label)
    return labels


def _theme_phrases_from_text(text: str) -> list[str]:
    normalized = " ".join(text.replace("_", " ").replace("-", " ").split()).strip().lower()
    if not normalized:
        return []
    labels: list[str] = []
    for phrase in _THEME_PHRASE_HINTS:
        if phrase in normalized and phrase not in labels:
            labels.append(phrase)
    if "startup" in normalized and "startup ideas" not in labels:
        labels.append("startup ideas")
    if "ideas" in normalized and "product ideas" not in labels and "startup ideas" not in labels:
        labels.append("product ideas")
    return labels


def _source_role_profiles(source_paths: list[str]) -> list[dict[str, Any]]:
    role_counts: Counter[str] = Counter()
    role_themes: dict[str, Counter[str]] = {}
    for source in source_paths:
        path = Path(source)
        meta: dict[str, Any] = {}
        body = ""
        title = path.stem.replace("-", " ").replace("_", " ").strip()
        if path.exists() and path.suffix.lower() in {".md", ".txt"}:
            try:
                meta, body = parse_frontmatter(path)
            except OSError:
                meta, body = {}, ""
            title = str(meta.get("title") or title).strip()
        role = _classify_source_role(path=path, meta=meta, title=title, body=body)
        role_counts[role] += 1
        role_themes.setdefault(role, Counter()).update(_source_theme_counter(meta=meta, body=body, title=title))

    profiles = [
        {
            "role": role,
            "count": count,
            "themes": [label for label, _ in role_themes.get(role, Counter()).most_common(4)],
        }
        for role, count in role_counts.items()
    ]
    profiles.sort(key=lambda item: (_SOURCE_ROLE_ORDER.get(item["role"], 99), -item["count"], item["role"]))
    return profiles


def _classify_source_role(*, path: Path, meta: dict[str, Any], title: str, body: str) -> str:
    lower_title = " ".join(title.lower().split())
    lower_parts = {part.replace("-", " ").lower() for part in path.parts}
    sync_target = str(meta.get("sync_target", "")).strip().lower()
    if sync_target == "reminders" or "reminders" in lower_parts:
        return "tasks and ideas"
    if "notes sync" in lower_parts or "voice memos" in lower_parts or "note" in lower_title or "journal" in lower_parts:
        return "working notes"
    if (
        path.name.lower() == "readme.md"
        or "comparison" in lower_title
        or "guide" in lower_title
        or "reference" in lower_title
        or "config" in lower_parts
        or path.suffix.lower() == ".json"
    ):
        return "reference context"
    if _body_theme_labels(body):
        return "working notes"
    return "source material"


def _source_role_fragment(profile: dict[str, Any]) -> str:
    role = str(profile.get("role", "")).strip() or "source material"
    themes = [str(item).strip() for item in profile.get("themes", []) if str(item).strip()]
    if themes:
        return f"{role} around {_human_join(themes[:4])}"
    return role


def _source_role_fragments(source_paths: list[str]) -> list[str]:
    return [_source_role_fragment(profile) for profile in _source_role_profiles(source_paths)]


def _source_focus_labels(source_paths: list[str]) -> list[str]:
    labels: dict[str, int] = {}
    for source in source_paths:
        path = Path(source)
        ignored = {
            "",
            "/",
            "users",
            "projects",
            "au-vault",
            "au vault",
            "augur",
            "private",
            "var",
            "folders",
            "tmp",
            "vault",
        }
        dir_parts = [
            part.replace("-", " ").lower()
            for part in path.parent.parts
            if part and part not in {path.anchor}
            and part.replace("-", " ").lower() not in ignored
            and not part.replace("-", " ").lower().startswith(("test", "pytest", "tmp"))
        ]
        if not dir_parts:
            label = path.stem.replace("-", " ")
        else:
            last = dir_parts[-1]
            previous = dir_parts[-2] if len(dir_parts) >= 2 else ""
            if last == "workflows" and previous and previous not in {"ai", "dev", "venture augur"}:
                label = f"{previous} workflows"
            elif last not in {"ai", "dev", "venture augur"}:
                label = last
            elif previous and previous not in {"ai", "dev", "venture augur"}:
                label = previous
            else:
                label = path.stem.replace("-", " ")
        labels[label] = labels.get(label, 0) + 1
    return [
        label
        for label, _ in sorted(labels.items(), key=lambda item: (-item[1], item[0]))
    ]


def _human_join(items: list[str]) -> str:
    cleaned = [item for item in items if item]
    if not cleaned:
        return ""
    if len(cleaned) == 1:
        return cleaned[0]
    if len(cleaned) == 2:
        return f"{cleaned[0]} and {cleaned[1]}"
    return f"{', '.join(cleaned[:-1])}, and {cleaned[-1]}"


def _change_signal_fragments(change_signals: dict[str, list[str]]) -> list[str]:
    fragments: list[str] = []
    git_titles = [title for title in change_signals.get("git_history", [])[:3] if title]
    delta_titles = [title for title in change_signals.get("project_deltas", [])[:3] if title]
    if git_titles:
        fragments.append(f"recent commits including {', '.join(git_titles)}")
    if delta_titles:
        fragments.append(f"active plans and specs including {', '.join(delta_titles)}")
    return fragments
