"""Aggregate wiki data into structured report data.

Reads all wiki pages, computes stats, extracts cross-references,
scans portfolio folder, and builds a ReportData object that the
renderer and agent use.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
import re
from typing import Any

from src.lib.frontmatter_utils import parse_frontmatter
from src.lib.wiki_utils import WIKILINK_RE
from skills.wiki.scripts.wiki_maintenance import find_stale_pages
from skills.wiki.scripts.wiki_pages import WikiPages
from skills.wiki.scripts.wiki_quality import assess_page_quality
from skills.wiki.scripts.wiki_schema import lint_penalties
from skills.wiki.scripts.wiki_scanner import _SCANNABLE, _SKIP_DIRS, WikiScanner

_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"}


@dataclass
class ReportData:
    """Structured data for report rendering."""
    stats: dict[str, Any] = field(default_factory=dict)
    hubs: dict[str, dict[str, Any]] = field(default_factory=dict)
    pages: list[dict[str, Any]] = field(default_factory=list)
    connections: list[dict[str, str]] = field(default_factory=list)
    consolidation: list[dict[str, Any]] = field(default_factory=list)
    portfolio: dict[str, Any] = field(default_factory=dict)


_HUB_META = {
    "advisor": {"icon": "Advisor", "color": "#8b5cf6"},
    "ai": {"icon": "AI", "color": "#6366f1"},
    "apple": {"icon": "Apple", "color": "#06b6d4"},
    "attention": {"icon": "Inbox", "color": "#f59e0b"},
    "books": {"icon": "Books", "color": "#10b981"},
    "career": {"icon": "Career", "color": "#3b82f6"},
    "content": {"icon": "Content", "color": "#ec4899"},
    "daemon": {"icon": "Ops", "color": "#ef4444"},
    "dev": {"icon": "Dev", "color": "#6366f1"},
    "documents": {"icon": "Docs", "color": "#22c55e"},
    "eisenhower": {"icon": "Priority", "color": "#f97316"},
    "finance": {"icon": "Finance", "color": "#14b8a6"},
    "general": {"icon": "General", "color": "#64748b"},
    "health": {"icon": "Health", "color": "#22c55e"},
    "knowledge": {"icon": "Knowledge", "color": "#8b5cf6"},
    "lifestyle": {"icon": "Life", "color": "#f59e0b"},
    "memory": {"icon": "Memory", "color": "#06b6d4"},
    "websites": {"icon": "Web", "color": "#3b82f6"},
}


def aggregate_report_data(
    *,
    wiki_dir: Path,
    runtime_wiki_dir: Path,
    portfolio_dir: Path | None = None,
    vault_dir: Path | None = None,
    documents_dir: Path | None = None,
    hub: str | None = None,
) -> ReportData:
    """Read all wiki pages and build report data."""
    requested_hub = str(hub or "").strip()
    pages_data: list[dict[str, Any]] = []
    connections: list[dict[str, str]] = []
    hubs: dict[str, dict[str, Any]] = {}
    total_words = 0
    all_source_names: set[str] = set()
    wp = WikiPages(wiki_dir=wiki_dir, runtime_wiki_dir=runtime_wiki_dir)

    # Single pass over wiki pages — runtime wiki dir is for manifests/logs, not page inventory.
    if wiki_dir and wiki_dir.is_dir():
        wiki_files = [
            md_file
            for md_file in sorted(wiki_dir.rglob("*.md"))
            if md_file.is_file()
            and not (md_file.relative_to(wiki_dir).parent == Path(".") and md_file.name in ("index.md", "overview.md"))
        ]
        page_keys = {md_file.relative_to(wiki_dir).with_suffix("").as_posix() for md_file in wiki_files}

        for md_file in wiki_files:
            if not md_file.is_file():
                continue
            rel = md_file.relative_to(wiki_dir)
            try:
                meta, body = parse_frontmatter(md_file)
            except Exception:
                continue

            page_key = str(rel.with_suffix(""))
            word_count = len(body.split())
            total_words += word_count
            sources = meta.get("sources", []) if isinstance(meta.get("sources"), list) else []
            all_source_names.update(sources)
            page_hub = meta.get("hub", "general") or "general"
            if requested_hub and page_hub != requested_hub:
                continue

            related_targets = {
                _canonical_connection_target(match.group(1).strip(), page_keys=page_keys)
                for match in WIKILINK_RE.finditer(body)
                if match.group(1).strip()
            }
            related_targets.update(
                _canonical_connection_target(target, page_keys=page_keys)
                for target in wp._find_related_pages(
                    page=page_key,
                    title=str(meta.get("title", "")),
                    hub=str(page_hub),
                    tags=meta.get("tags", []) if isinstance(meta.get("tags"), list) else [],
                    body=body,
                )
            )
            related_targets.discard(page_key)
            if requested_hub:
                related_targets = {
                    target for target in related_targets
                    if target.startswith(f"{requested_hub}/")
                }
            cross_ref_count = len(related_targets)
            for target in sorted(related_targets):
                connections.append({"from": page_key, "to": target})
            quality = assess_page_quality(
                page=page_key,
                page_type=str(meta.get("page_type") or ""),
                hub=page_hub,
                tags=meta.get("tags", []) if isinstance(meta.get("tags"), list) else [],
                sources=sources,
                body=body,
                cross_ref_count=cross_ref_count,
                compiler_version=str(meta.get("compiler_version") or ""),
            )
            if not meta.get("source_fingerprint") and str(meta.get("page_type") or "") in {"concept", "query", "overview"}:
                quality_flags = list(quality.get("quality_flags", []))
                quality_flags.append("missing_source_fingerprint")
                quality["quality_flags"] = quality_flags
                penalty = int(lint_penalties().get("missing_source_fingerprint", 0))
                quality["quality_score"] = max(int(quality.get("quality_score", 0)) - penalty, 0)

            if page_hub not in hubs:
                hubs[page_hub] = {
                    "page_count": 0,
                    "source_count": 0,
                    "word_count": 0,
                    "tags": set(),
                    "internal_edges": 0,
                }
            hubs[page_hub]["page_count"] += 1
            hubs[page_hub]["source_count"] += len(sources)
            hubs[page_hub]["word_count"] += word_count
            hubs[page_hub]["tags"].update(meta.get("tags", []) if isinstance(meta.get("tags"), list) else [])

            pages_data.append({
                "page": page_key,
                "title": meta.get("title", ""),
                "hub": page_hub,
                "tags": meta.get("tags", []) if isinstance(meta.get("tags"), list) else [],
                "sources": sources,
                "word_count": word_count,
                "cross_ref_count": cross_ref_count,
                "body_preview": body[:300],
                "has_source_fingerprint": bool(meta.get("source_fingerprint")),
                **quality,
            })

    page_hubs = {page["page"]: page["hub"] for page in pages_data}
    incoming_counts = {page["page"]: 0 for page in pages_data}
    outgoing_counts = {page["page"]: 0 for page in pages_data}
    unique_internal_edges: dict[str, set[tuple[str, str]]] = {hub_name: set() for hub_name in hubs}
    for connection in connections:
        source = connection["from"]
        target = connection["to"]
        outgoing_counts[source] = outgoing_counts.get(source, 0) + 1
        if target in incoming_counts:
            incoming_counts[target] += 1
            source_hub = page_hubs.get(source)
            target_hub = page_hubs.get(target)
            if source_hub and source_hub == target_hub and source_hub in hubs:
                unique_internal_edges[source_hub].add((source, target))

    isolated_pages = sum(
        1
        for page in pages_data
        if incoming_counts.get(page["page"], 0) == 0 or outgoing_counts.get(page["page"], 0) == 0
    )

    for hub_name, hub_data in hubs.items():
        hub_page_keys = [page["page"] for page in pages_data if page["hub"] == hub_name]
        page_count = len(hub_page_keys)
        hub_data["internal_edges"] = len(unique_internal_edges.get(hub_name, set()))
        max_possible_edges = page_count * max(page_count - 1, 0)
        hub_data["hub_edge_density"] = (
            round(hub_data["internal_edges"] / max_possible_edges, 4)
            if max_possible_edges
            else 0.0
        )

    # Convert tag sets to lists for serialization
    for hub_data in hubs.values():
        hub_data["tags"] = sorted(hub_data["tags"])

    stale_pages = []
    filtered_noise_sources = 0
    pages_missing_source_fingerprint = sum(1 for page in pages_data if not page.get("has_source_fingerprint"))
    semantic_quality_flags = {
        "raw_metadata_evidence",
        "duplicate_physical_sources",
        "catch_all_page",
        "non_synthetic_overview",
        "missing_source_fingerprint",
        "generic_taxonomy_tags",
        "legacy_client_source_path",
        "generated_boilerplate_sections",
        "unsupported_domain_abstraction",
        "index_shaped_page",
        "draft_source_basis",
        "pending_source_cluster",
        "below_cluster_source_floor",
        "overbroad_source_cluster",
        "shallow_synthesis",
        "index_like_prose",
        "clipped_evidence",
    }
    editorial_quality_flags = {
        "draft_source_basis",
        "pending_source_cluster",
        "below_cluster_source_floor",
        "overbroad_source_cluster",
        "shallow_synthesis",
        "index_like_prose",
        "thin_page",
        "index_shaped_page",
        "clipped_evidence",
    }
    rewrite_candidate_count = sum(
        1
        for page in pages_data
        if page.get("quality_score", 100) < 75
        or "inventory_style" in page.get("quality_flags", [])
        or semantic_quality_flags.intersection(set(page.get("quality_flags", [])))
    )
    semantic_quality_defects = sum(
        len(semantic_quality_flags.intersection(set(page.get("quality_flags", []))))
        for page in pages_data
    )
    editorial_quality_defects = sum(
        len(editorial_quality_flags.intersection(set(page.get("quality_flags", []))))
        for page in pages_data
    )
    draft_pages = sum(
        1
        for page in pages_data
        if "draft_source_basis" in page.get("quality_flags", [])
    )
    pending_cluster_pages = sum(
        1
        for page in pages_data
        if "pending_source_cluster" in page.get("quality_flags", [])
    )
    thin_pages = sum(
        1
        for page in pages_data
        if editorial_quality_flags.intersection(set(page.get("quality_flags", [])))
    )
    merge_candidates = sum(
        1
        for page in pages_data
        if {"draft_source_basis", "pending_source_cluster", "index_like_prose"}.intersection(
            set(page.get("quality_flags", []))
        )
    )
    cluster_ready_pages = sum(
        1
        for page in pages_data
        if page.get("page_kind") == "concept"
        and 8 <= len(page.get("sources", [])) <= 15
        and not {
            "shallow_synthesis",
            "index_like_prose",
            "overbroad_source_cluster",
        }.intersection(set(page.get("quality_flags", [])))
    )
    consolidation = _build_consolidation_clusters(pages_data)
    avg_quality_score = round(
        sum(page.get("quality_score", 0) for page in pages_data) / len(pages_data), 2
    ) if pages_data else 0.0
    quality_gate_inputs = {
        "rewrite_candidates": rewrite_candidate_count,
        "semantic_quality_defects": semantic_quality_defects,
        "editorial_quality_defects": editorial_quality_defects,
        "thin_pages": thin_pages,
        "draft_pages": draft_pages,
        "pending_cluster_pages": pending_cluster_pages,
        "duplicate_concept_clusters": len(consolidation),
    }
    quality_gate_failures = [
        key for key, value in quality_gate_inputs.items() if int(value or 0) > 0
    ]
    if vault_dir and documents_dir:
        stale_pages = find_stale_pages(
            wiki_dir=wiki_dir,
            vault_dir=vault_dir,
            documents_dir=documents_dir,
        )
        scanner = WikiScanner(vault_dir=vault_dir, documents_dir=documents_dir)
        pre_noise_candidates = 0
        for root in (Path(vault_dir), Path(documents_dir)):
            if not root.is_dir():
                continue
            for path in root.rglob("*"):
                if not path.is_file():
                    continue
                if any(skip in path.parts for skip in _SKIP_DIRS):
                    continue
                if path.suffix.lower() not in _SCANNABLE:
                    continue
                pre_noise_candidates += 1
        filtered_noise_sources = max(pre_noise_candidates - len(scanner.scan()), 0)

    # Portfolio scanning
    portfolio = {"profile": None, "logo": None, "cover": None, "hub_images": {}}
    if portfolio_dir and portfolio_dir.is_dir():
        for img in portfolio_dir.iterdir():
            if img.suffix.lower() not in _IMAGE_EXTS:
                continue
            stem = img.stem.lower()
            if stem.startswith("profile"):
                portfolio["profile"] = str(img)
            elif stem.startswith("logo"):
                portfolio["logo"] = str(img)
            elif stem.startswith("cover"):
                portfolio["cover"] = str(img)
            else:
                # Match hub-* pattern
                for hub_name in hubs:
                    if stem.startswith(f"{hub_name}-") or stem.startswith(f"{hub_name}_"):
                        portfolio["hub_images"].setdefault(hub_name, []).append(str(img))
                        break

    return ReportData(
        stats={
            "total_pages": len(pages_data),
            "total_hubs": len(hubs),
            "total_sources": len(all_source_names),
            "total_words": total_words,
            "total_cross_refs": len(connections),
            "avg_outgoing_links_per_page": round(len(connections) / len(pages_data), 2) if pages_data else 0.0,
            "isolated_pages": isolated_pages,
            "stale_pages": len(stale_pages),
            "pages_missing_source_fingerprint": pages_missing_source_fingerprint,
            "filtered_noise_sources": filtered_noise_sources,
            "avg_quality_score": avg_quality_score,
            "rewrite_candidates": rewrite_candidate_count,
            "semantic_quality_defects": semantic_quality_defects,
            "editorial_quality_defects": editorial_quality_defects,
            "thin_pages": thin_pages,
            "draft_pages": draft_pages,
            "pending_cluster_pages": pending_cluster_pages,
            "cluster_ready_pages": cluster_ready_pages,
            "merge_candidates": merge_candidates,
            "duplicate_concept_clusters": len(consolidation),
            "cluster_source_floor": 8,
            "cluster_source_ceiling": 15,
            "quality_gate_ok": not quality_gate_failures,
            "quality_gate_failures": quality_gate_failures,
        },
        hubs=hubs,
        pages=pages_data,
        connections=connections,
        consolidation=consolidation,
        portfolio=portfolio,
    )


_CONSOLIDATION_STOPWORDS = {
    "actions",
    "concept",
    "concepts",
    "command",
    "page",
    "pages",
    "query",
    "source",
    "sources",
    "the",
    "used",
    "wiki",
}


def _build_consolidation_clusters(pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group thin concept pages that should be merged into broader articles."""
    pair_groups: dict[tuple[str, tuple[str, str]], list[dict[str, Any]]] = {}
    for page in pages:
        if page.get("page_kind") != "concept":
            continue
        flags = set(page.get("quality_flags", []))
        if not {"draft_source_basis", "pending_source_cluster", "index_like_prose"}.intersection(flags):
            continue
        tokens = sorted(_consolidation_tokens(page))
        if len(tokens) < 2:
            continue
        hub = str(page.get("hub") or "general")
        for left_index, left in enumerate(tokens):
            for right in tokens[left_index + 1:]:
                pair_groups.setdefault((hub, (left, right)), []).append(page)

    clusters: list[dict[str, Any]] = []
    used_pages: set[str] = set()
    for (hub, token_pair), group in sorted(
        pair_groups.items(),
        key=lambda item: (-len(item[1]), item[0][0], item[0][1]),
    ):
        available = [
            page for page in group
            if str(page.get("page") or "") not in used_pages
        ]
        if len(available) < 2:
            continue
        page_keys = sorted(str(page.get("page")) for page in available)
        used_pages.update(page_keys)
        source_count = sum(len(page.get("sources", [])) for page in available)
        clusters.append({
            "cluster_key": f"{hub}:{'-'.join(token_pair)}",
            "hub": hub,
            "tokens": list(token_pair),
            "pages": page_keys,
            "source_count": source_count,
            "reason": "merge thin concept pages into a broader source cluster before durable publication",
        })

    return clusters


def _consolidation_tokens(page: dict[str, Any]) -> set[str]:
    values = [
        page.get("page", ""),
        page.get("title", ""),
        page.get("hub", ""),
        *(page.get("tags", []) if isinstance(page.get("tags"), list) else []),
    ]
    tokens: set[str] = set()
    for value in values:
        for token in re.findall(r"[a-z0-9]+", str(value).lower()):
            if len(token) < 4 or token in _CONSOLIDATION_STOPWORDS:
                continue
            tokens.add(token)
    return tokens


def _canonical_connection_target(target: str, *, page_keys: set[str]) -> str:
    cleaned = str(target).strip().strip("/")
    if not cleaned:
        return cleaned
    if "|" in cleaned:
        cleaned = cleaned.split("|", 1)[0].strip()
    if "#" in cleaned:
        cleaned = cleaned.split("#", 1)[0].strip()
    if cleaned in page_keys:
        return cleaned
    for prefix in ("concepts", "queries"):
        candidate = f"{prefix}/{cleaned}"
        if "/" not in cleaned and candidate in page_keys:
            return candidate
    if cleaned.startswith("concepts/") or cleaned.startswith("queries/"):
        return cleaned
    return cleaned


def build_report_json(
    data: ReportData,
    *,
    name: str = "user",
    report_title: str = "Second Brain Intelligence Report",
    generated_on: str | None = None,
) -> dict[str, Any]:
    """Build a deterministic report payload from aggregated wiki data."""
    generated_on = generated_on or date.today().isoformat()
    hubs_sorted = sorted(data.hubs.items(), key=lambda item: item[1]["source_count"], reverse=True)
    pages_sorted = sorted(data.pages, key=lambda item: item["word_count"], reverse=True)
    strong_hubs = [hub for hub, _ in hubs_sorted[:3]]
    strong_hub_labels = ", ".join(hub.replace("-", " ") for hub in strong_hubs) or "your current wiki hubs"
    top_titles = [page["title"] for page in pages_sorted[:3] if page.get("title")]
    top_titles_text = ", ".join(top_titles) if top_titles else "the current anchor pages"

    synthesis = (
        f"This brain currently compiles {data.stats.get('total_pages', 0)} wiki pages across "
        f"{data.stats.get('total_hubs', 0)} hubs, with the center of gravity in {strong_hub_labels}. "
        f"It reads like someone building a local-first operating system while simultaneously curating "
        f"career, memory, and execution systems into reusable operating knowledge."
    )

    top_hub_name = strong_hubs[0] if strong_hubs else "general"
    top_hub = data.hubs.get(top_hub_name, {"source_count": 0, "word_count": 0, "tags": []})
    secondary_hub_name = strong_hubs[1] if len(strong_hubs) > 1 else top_hub_name

    what_you_do = (
        f"Your current knowledge base is anchored in {top_hub_name.replace('-', ' ')}, with "
        f"{top_hub.get('source_count', 0)} linked sources and {top_hub.get('word_count', 0)} words of compiled knowledge. "
        f"The next layer is {secondary_hub_name.replace('-', ' ')}, which suggests you are not just building systems "
        f"but also packaging them for decisions, delivery, and real-world use. Right now the anchor pages are {top_titles_text}."
    )
    how_you_think = (
        f"The wiki shows a bias toward connected systems rather than isolated notes: "
        f"{data.stats.get('total_cross_refs', 0)} wikilinks across {data.stats.get('total_pages', 0)} pages. "
        f"That pattern usually means you think in architectures, interfaces, and operating loops instead of one-off documents. "
        f"The corpus is denser around maintained operating surfaces than around static reference material."
    )

    expertise = []
    for hub_name, hub_data in hubs_sorted[:8]:
        score = hub_data["source_count"]
        if score >= 25:
            level = "Expert"
        elif score >= 12:
            level = "Advanced"
        elif score >= 5:
            level = "Active"
        else:
            level = "Growing"
        expertise.append({
            "domain": hub_name.replace("-", " ").title(),
            "level": level,
            "score": min(score, 100),
        })

    hub_sections = []
    for hub_name, hub_data in hubs_sorted[:8]:
        tags = ", ".join(hub_data.get("tags", [])[:4])
        summary = (
            f"{hub_data['page_count']} pages and {hub_data['source_count']} sources. "
            f"Most visible themes: {tags or 'emerging topics'}. "
            f"This hub currently holds {hub_data['word_count']} words of compiled context."
        )
        meta = _HUB_META.get(hub_name, {"icon": None, "color": "#64748b"})
        hub_sections.append({
            "name": hub_name.replace("-", " ").title(),
            "source_count": hub_data["source_count"],
            "summary": summary,
            "icon": meta["icon"],
            "color": meta["color"],
        })

    patterns = []
    if strong_hubs:
        patterns.append({
            "title": "A few hubs dominate the brain",
            "description": (
                f"{strong_hubs[0].replace('-', ' ').title()} leads the corpus, with "
                f"{', '.join(h.replace('-', ' ') for h in strong_hubs[1:3]) or 'other hubs'} acting as adjacent support systems rather than isolated side projects."
            ),
        })
    if data.stats.get("total_cross_refs", 0) > 0:
        patterns.append({
            "title": "Knowledge is being compiled, not just stored",
            "description": (
                f"{data.stats['total_cross_refs']} cross-references across the wiki suggest deliberate synthesis and navigation between topics."
            ),
        })
    if pages_sorted:
        patterns.append({
            "title": "Long-form pages still hold the core narrative",
            "description": (
                f"The heaviest page right now is '{pages_sorted[0]['title']}', which is a good proxy for where your deepest active context still lives."
            ),
        })

    blind_spots = []
    sparse_hubs = [hub for hub, hub_data in hubs_sorted if hub_data["page_count"] < 2][:3]
    if sparse_hubs:
        blind_spots.append({
            "title": "Sparse hubs need another synthesis pass",
            "description": (
                f"{', '.join(h.replace('-', ' ') for h in sparse_hubs)} still have thin coverage. Add or rewrite pages there if you want those areas to materially affect future answers."
            ),
            "severity": "warning",
        })
    if not data.portfolio.get("profile"):
        blind_spots.append({
            "title": "No profile or cover assets found",
            "description": "The report can embed profile, logo, and hub visuals, but no portfolio images were available in the vault.",
            "severity": "warning",
        })
    if data.stats.get("total_cross_refs", 0) < data.stats.get("total_pages", 0):
        blind_spots.append({
            "title": "Some pages are still isolated",
            "description": "Cross-reference density is lower than page count, which usually means some topics have not been integrated into the main wiki graph yet.",
            "severity": "critical",
        })

    return {
        "title": report_title,
        "name": name,
        "date": generated_on,
        "synthesis": synthesis,
        "stats": {
            "pages": data.stats.get("total_pages", 0),
            "hubs": data.stats.get("total_hubs", 0),
            "sources": data.stats.get("total_sources", 0),
            "words": data.stats.get("total_words", 0),
            "cross_refs": data.stats.get("total_cross_refs", 0),
        },
        "who_you_are": {
            "what_you_do": what_you_do,
            "how_you_think": how_you_think,
        },
        "expertise": expertise,
        "hub_sections": hub_sections,
        "patterns": patterns[:4],
        "blind_spots": blind_spots[:3],
        "portfolio": data.portfolio,
        "charts": {},
    }
