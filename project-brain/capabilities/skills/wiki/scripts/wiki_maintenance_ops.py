"""auto-wiki-maintenance: structural, freshness, and editorial wiki quality scan."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
import re

from src.config.paths import (
    get_compiled_wiki_dir,
    get_documents_dir,
    get_rag_dir,
    get_runtime_dir,
    get_vault_dir,
    resolve_wiki_dir,
)
from src.lib.frontmatter_utils import parse_frontmatter
from src.lib.ops_protocol import (
    FixResult,
    OpsContext,
    ScanResult,
    evolution_gap,
    make_issue,
    report_only_fix,
)

from skills.wiki.scripts.wiki_maintenance import (
    find_rewrite_candidates,
    find_stale_pages,
    lint_wiki,
)
from skills.wiki.scripts.wiki_concept_state import load_compiler_state
from skills.wiki.scripts.wiki_report import aggregate_report_data
from skills.wiki.scripts.wiki_source_inventory import build_source_inventory
from skills.wiki.scripts.wiki_status import build_wiki_status

name = "auto-wiki-maintenance"

DIFFICULTY_SPEC = {
    0: "Structural lint: broken links, duplicate titles, orphan pages",
    1: "d0 + stale-page detection from source fingerprints",
    2: "d1 + rewrite-candidate detection from quality heuristics",
    3: "d2 + low-density hub detection for weak cross-linking",
    4: "d3 + semantic adjacency, source coverage, evidence freshness, and contradiction checks",
}

DEFAULT_MIN_HUB_EDGE_DENSITY = 0.35
DEFAULT_MAX_DENSITY_ONLY_PAGES = 12
DEFAULT_MIN_INTERNAL_LINKS_PER_PAGE = 2.0
DEFAULT_MIN_BAD_LINK_COUNT = 3
DEFAULT_MAX_UNSUPPORTED_LINK_RATIO = 0.67
DEFAULT_MIN_SOURCE_CLUSTER_SIZE = 5
DEFAULT_MIN_SOURCE_CLUSTER_COVERAGE_RATIO = 0.05
DEFAULT_MAX_SOURCE_CLUSTER_ISSUES = 5
DEFAULT_MAX_CONTRADICTION_ISSUES = 5
DEFAULT_MIN_QUOTE_SPAN_TOKENS = 6
DEFAULT_OLD_EVIDENCE_DAYS = 1095
DEFAULT_MIN_QUOTE_TOKEN_COVERAGE = 0.8
DEFAULT_MIN_BROAD_PAGE_SOURCE_COUNT = 2
DEFAULT_MIN_BROAD_PAGE_SOURCE_FAMILIES = 1
DEFAULT_MAX_SOURCE_DIVERSITY_ISSUES = 5
DEFAULT_MIN_CLAIM_CORROBORATING_SOURCES = 2
DEFAULT_MIN_CLAIM_CORROBORATING_FAMILIES = 1
DEFAULT_MIN_CLAIM_CORROBORATION_TOKEN_OVERLAP = 0.25
DEFAULT_MIN_CLAIM_CORROBORATION_CRITICALITY = 6
DEFAULT_MAX_CORROBORATION_ISSUES = 5
DEFAULT_CRITICALITY_SOURCE_BONUS_THRESHOLD = 12
DEFAULT_CRITICALITY_FAMILY_BONUS_THRESHOLD = 14
DEFAULT_DOMAIN_RECENCY_DAYS = {
    "career": 365,
    "finance": 365,
    "health": 365,
}

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_EVIDENCE_SOURCE_RE = re.compile(r"^\s*-\s+`(?P<source>[^`]+)`\s*:", re.MULTILINE)
_EVIDENCE_ENTRY_RE = re.compile(r"^\s*-\s+`(?P<source>[^`]+)`\s*:\s*(?P<quote>.+)$", re.MULTILINE)
_TIMELINE_ENTRY_RE = re.compile(r"^\s*-\s+_at:\s+\S+\s+_source:\s+(?P<source>\S+)\s*$")
_SENTENCE_RE = re.compile(r"[^.!?\n]+[.!?]?")
_MODAL_CLAIM_RE = re.compile(
    r"\b(?P<subject>[a-z][a-z0-9 _/-]{1,60}?)\s+"
    r"(?P<modal>must|should|can|will)\s+"
    r"(?P<negation>not\s+)?"
    r"(?P<predicate>[a-z0-9][a-z0-9 _/.,:;()'\"-]{3,140})",
    re.IGNORECASE,
)
_STOPWORDS = {
    "and",
    "for",
    "from",
    "into",
    "overview",
    "page",
    "pages",
    "source",
    "sources",
    "the",
    "this",
    "that",
    "wiki",
    "with",
    "concept",
    "concepts",
}
_BROAD_PAGE_TOKENS = {
    "framework",
    "model",
    "playbook",
    "policy",
    "roadmap",
    "scoring",
    "strategy",
}
_CRITICALITY_TOKEN_WEIGHTS = {
    "automation": 1,
    "clinical": 3,
    "clinician": 3,
    "commercial": 2,
    "compliance": 3,
    "critical": 2,
    "finance": 3,
    "health": 3,
    "legal": 3,
    "license": 2,
    "licensing": 2,
    "must": 2,
    "policy": 1,
    "privacy": 3,
    "production": 2,
    "require": 2,
    "required": 2,
    "requires": 2,
    "revenue": 2,
    "risk": 2,
    "security": 3,
    "should": 1,
    "treatment": 3,
}


def _iter_report_hubs(report: object) -> list[dict]:
    hubs = getattr(report, "hubs", {})
    if isinstance(hubs, dict):
        return [
            {"name": name, **data}
            for name, data in hubs.items()
            if isinstance(data, dict)
        ]
    if isinstance(hubs, list):
        return [item for item in hubs if isinstance(item, dict)]
    return []


def _wiki_context() -> tuple[Path, Path, Path, Path]:
    runtime_wiki_dir = get_runtime_dir() / "wiki"
    wiki_dir = get_compiled_wiki_dir(resolve_wiki_dir())
    vault_dir = get_vault_dir()
    documents_dir = get_documents_dir()
    return wiki_dir, runtime_wiki_dir, vault_dir, documents_dir


def _hub_has_weak_internal_graph(
    hub: dict,
    *,
    min_density: float,
    max_density_only_pages: int,
    min_internal_links_per_page: float,
) -> bool:
    page_count = int(hub.get("page_count", 0) or 0)
    if page_count < 3:
        return False

    density = float(hub.get("hub_edge_density", 0.0) or 0.0)
    if density >= min_density:
        return False

    if page_count <= max_density_only_pages:
        return True

    internal_edges = int(hub.get("internal_edges", 0) or 0)
    avg_internal_links = internal_edges / page_count if page_count else 0.0
    return avg_internal_links < min_internal_links_per_page


def _semantic_tokens(value: object) -> set[str]:
    tokens: set[str] = set()
    if value is None:
        return tokens
    if isinstance(value, (list, tuple, set)):
        for item in value:
            tokens.update(_semantic_tokens(item))
        return tokens

    text = str(value).replace("_", " ").replace("-", " ").lower()
    for token in _TOKEN_RE.findall(text):
        if len(token) < 3 or token in _STOPWORDS:
            continue
        tokens.add(token)
    return tokens


def _page_semantic_tokens(page: dict) -> set[str]:
    tokens = set()
    for key in ("page", "title", "hub", "tags", "body_preview"):
        tokens.update(_semantic_tokens(page.get(key)))
    return tokens


def _append_semantic_adjacency_issues(
    issues: list[dict],
    *,
    report: object,
    wiki_dir: Path,
    min_bad_link_count: int,
    max_unsupported_link_ratio: float,
) -> None:
    """Flag pages whose generated adjacency is mostly unrelated by title/tag tokens."""
# TODO_CLEANUP: This file is 1608 lines — consider splitting into smaller modules
    pages = getattr(report, "pages", [])
    connections = getattr(report, "connections", [])
    if not isinstance(pages, list) or not isinstance(connections, list):
        return

    pages_by_key = {
        str(page.get("page", "")).strip(): page
        for page in pages
        if isinstance(page, dict) and str(page.get("page", "")).strip()
    }
    if not pages_by_key:
        return

    tokens_by_page = {
        page_key: _page_semantic_tokens(page)
        for page_key, page in pages_by_key.items()
    }
    outgoing: dict[str, list[str]] = defaultdict(list)
    unsupported: dict[str, list[str]] = defaultdict(list)

    for connection in connections:
        if not isinstance(connection, dict):
            continue
        source = str(connection.get("from", "")).strip()
        target = str(connection.get("to", "")).strip()
        if source not in pages_by_key or target not in pages_by_key:
            continue
        outgoing[source].append(target)
        source_tokens = tokens_by_page.get(source, set())
        target_tokens = tokens_by_page.get(target, set())
        if not source_tokens or not target_tokens:
            continue
        if source_tokens.isdisjoint(target_tokens):
            unsupported[source].append(target)

    for source, bad_targets in sorted(unsupported.items()):
        total_links = len(outgoing.get(source, []))
        if total_links == 0:
            continue
        unsupported_ratio = len(bad_targets) / total_links
        if len(bad_targets) < min_bad_link_count or unsupported_ratio < max_unsupported_link_ratio:
            continue
        sample_targets = ", ".join(bad_targets[:5])
        issues.append(make_issue(
            category="wiki-maintenance",
            detail=(
                f"Page '{source}' has low semantic adjacency quality: "
                f"{len(bad_targets)}/{total_links} link(s) lack title/tag token overlap "
                f"({sample_targets})"
            ),
            path=str(wiki_dir / f"{source}.md"),
            kind="maintenance",
            root_cause_type="manual_debt",
            fixability="manual",
            page=source,
            unsupported_links=bad_targets,
            outgoing_links=total_links,
            unsupported_link_ratio=round(unsupported_ratio, 3),
        ))


def _wiki_page_source_ids(wiki_dir: Path) -> set[str]:
    source_ids: set[str] = set()
    if not wiki_dir.exists():
        return source_ids
    for path in wiki_dir.rglob("*.md"):
        try:
            metadata, _body = parse_frontmatter(path)
        except OSError:
            continue
        raw_sources = metadata.get("sources", [])
        if not isinstance(raw_sources, list):
            continue
        for source in raw_sources:
            source_id = str(source).strip()
            if source_id:
                source_ids.add(source_id)
    return source_ids


def _source_family(source: object) -> str:
    metadata = getattr(source, "metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
    family = str(metadata.get("source_family") or getattr(source, "kind", "") or "unknown").strip()
    return family or "unknown"


def _source_families_by_id(sources: list[object]) -> dict[str, str]:
    families: dict[str, str] = {}
    for source in sources:
        source_id = str(getattr(source, "source_id", "")).strip()
        if source_id:
            families[source_id] = _source_family(source)
    return families


def _append_source_cluster_coverage_issues(
    issues: list[dict],
    *,
    wiki_dir: Path,
    runtime_wiki_dir: Path,
    min_cluster_size: int,
    min_coverage_ratio: float,
    max_issues: int,
) -> None:
    """Flag source families large enough to be durable but barely represented in compiled concepts."""
    try:
        sources = build_source_inventory(rag_dir=get_rag_dir(), wiki_dir=wiki_dir)
        compiler_state = load_compiler_state(runtime_wiki_dir)
    except (OSError, ValueError) as exc:
        issues.append(make_issue(
            category="wiki-maintenance",
            detail=f"Cannot inspect wiki source-cluster coverage: {exc}",
            path=str(runtime_wiki_dir),
            kind="actionable",
            root_cause_type="repo_bug",
            fixability="manual",
        ))
        return

    if not sources:
        return

    page_source_ids = _wiki_page_source_ids(wiki_dir)
    clusters: dict[str, dict[str, object]] = defaultdict(lambda: {"total": 0, "covered": 0, "examples": []})
    state_sources = getattr(compiler_state, "sources", {})
    if not isinstance(state_sources, dict):
        state_sources = {}

    for source in sources:
        source_id = str(getattr(source, "source_id", "")).strip()
        if not source_id:
            continue
        family = _source_family(source)
        cluster = clusters[family]
        cluster["total"] = int(cluster["total"]) + 1
        compile_state = state_sources.get(source_id)
        concept_slugs = getattr(compile_state, "concept_slugs", []) if compile_state else []
        covered = source_id in page_source_ids or bool(concept_slugs)
        if covered:
            cluster["covered"] = int(cluster["covered"]) + 1
        elif len(cluster["examples"]) < 5:
            cluster["examples"].append(source_id)

    findings: list[tuple[float, str, dict[str, object]]] = []
    for family, cluster in clusters.items():
        total = int(cluster["total"])
        covered = int(cluster["covered"])
        if total < min_cluster_size:
            continue
        coverage_ratio = covered / total if total else 0.0
        if coverage_ratio >= min_coverage_ratio:
            continue
        findings.append((coverage_ratio, family, cluster))

    for coverage_ratio, family, cluster in sorted(findings)[:max_issues]:
        total = int(cluster["total"])
        covered = int(cluster["covered"])
        examples = [str(item) for item in cluster["examples"] if str(item).strip()]
        issues.append(make_issue(
            category="wiki-maintenance",
            detail=(
                f"Source cluster '{family}' has low wiki coverage: "
                f"{covered}/{total} source(s) compile to concepts "
                f"({coverage_ratio:.1%} < {min_coverage_ratio:.1%})"
            ),
            path=str(get_rag_dir() / family),
            kind="maintenance",
            root_cause_type="manual_debt",
            fixability="manual",
            source_family=family,
            covered_sources=covered,
            total_sources=total,
            coverage_ratio=round(coverage_ratio, 3),
            uncovered_examples=examples,
        ))


def _extract_markdown_section(body: str, heading: str) -> str:
    pattern = re.compile(
        rf"^## {re.escape(heading)}\s*$\n(?P<section>.*?)(?=^## |\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(body)
    if not match:
        return ""
    return match.group("section").strip()


def _metadata_source_ids(metadata: dict) -> set[str]:
    raw_sources = metadata.get("sources", [])
    if not isinstance(raw_sources, list):
        return set()
    return {str(source).strip() for source in raw_sources if str(source).strip()}


def _evidence_source_ids(body: str) -> set[str]:
    section = _extract_markdown_section(body, "Evidence")
    legacy_sources = {
        match.group("source").strip()
        for match in _EVIDENCE_SOURCE_RE.finditer(section)
        if match.group("source").strip()
    }
    timeline_sources = {entry["source_id"] for entry in _timeline_entries(body)}
    return legacy_sources.union(timeline_sources)


def _evidence_entries(body: str) -> list[dict[str, str]]:
    section = _extract_markdown_section(body, "Evidence")
    entries: list[dict[str, str]] = []
    for match in _EVIDENCE_ENTRY_RE.finditer(section):
        source_id = match.group("source").strip()
        quote = match.group("quote").strip()
        if source_id and quote:
            entries.append({"source_id": source_id, "quote": quote})
    entries.extend(_timeline_entries(body))
    return entries


def _timeline_entries(body: str) -> list[dict[str, str]]:
    section = _extract_markdown_section(body, "Timeline")
    if not section:
        return []
    entries: list[dict[str, str]] = []
    current: list[str] = []
    for line in section.splitlines():
        if not line.strip():
            continue
        if line.lstrip().startswith("- "):
            if current:
                entry = _timeline_block_entry(current)
                if entry is not None:
                    entries.append(entry)
            current = [line]
            continue
        if current and line.startswith((" ", "\t")):
            current.append(line)
    if current:
        entry = _timeline_block_entry(current)
        if entry is not None:
            entries.append(entry)
    return entries


def _timeline_block_entry(block: list[str]) -> dict[str, str] | None:
    header = block[0] if block else ""
    match = _TIMELINE_ENTRY_RE.match(header)
    if match is None:
        return None
    source_id = match.group("source").strip()
    quote = " ".join(line.strip() for line in block[1:] if line.strip())
    if not source_id or not quote:
        return None
    return {"source_id": source_id, "quote": quote}


def _span_tokens(text: str) -> list[str]:
    return [token for token in _TOKEN_RE.findall(text.lower()) if token]


def _normalized_span(text: str) -> str:
    return " ".join(_span_tokens(text))


def _quote_supported_by_source_text(quote: str, source_text: str, *, min_token_coverage: float) -> bool:
    quote_span = _normalized_span(quote)
    if quote_span in _normalized_span(source_text):
        return True

    quote_tokens = _span_tokens(quote)
    if not quote_tokens:
        return True
    source_tokens = set(_span_tokens(source_text))
    covered = sum(1 for token in quote_tokens if token in source_tokens)
    return (covered / len(quote_tokens)) >= min_token_coverage


def _source_text_for_descriptor(source: object) -> str:
    metadata = getattr(source, "metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}

    candidate_paths = [
        metadata.get("rag_entry"),
        getattr(source, "source_path", ""),
    ]
    bodies: list[str] = []
    for raw_path in candidate_paths:
        if not raw_path:
            continue
        path = Path(str(raw_path)).expanduser()
        if not path.exists() or not path.is_file():
            continue
        try:
            if path.suffix.lower() == ".md":
                _meta, body = parse_frontmatter(path)
                bodies.append(body)
            else:
                bodies.append(path.read_text(encoding="utf-8", errors="ignore"))
        except OSError:
            continue
    return "\n".join(body for body in bodies if body.strip())


def _source_texts_by_id(sources: list[object]) -> dict[str, str]:
    texts: dict[str, str] = {}
    for source in sources:
        source_id = str(getattr(source, "source_id", "")).strip()
        if not source_id:
            continue
        text = _source_text_for_descriptor(source)
        if text.strip():
            texts[source_id] = text
    return texts


def _parse_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _source_modified_at(source: object) -> datetime | None:
    metadata = getattr(source, "metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
    for value in (
        getattr(source, "modified_at", None),
        metadata.get("modified_at"),
        metadata.get("modified"),
        metadata.get("modifiedTime"),
    ):
        parsed = _parse_datetime(value)
        if parsed is not None:
            return parsed
    return None


def _source_modified_by_id(sources: list[object]) -> dict[str, datetime]:
    modified: dict[str, datetime] = {}
    for source in sources:
        source_id = str(getattr(source, "source_id", "")).strip()
        if not source_id:
            continue
        parsed = _source_modified_at(source)
        if parsed is not None:
            modified[source_id] = parsed
    return modified


def _domain_recency_config(raw_config: object) -> dict[str, int]:
    values = dict(DEFAULT_DOMAIN_RECENCY_DAYS)
    if isinstance(raw_config, dict):
        for key, value in raw_config.items():
            domain = str(key).strip().lower()
            if not domain:
                continue
            try:
                days = int(value)
            except (TypeError, ValueError):
                continue
            if days > 0:
                values[domain] = days
    return values


def _page_domain(*, page_key: str, metadata: dict) -> str:
    tokens = _semantic_tokens([
        page_key,
        metadata.get("hub"),
        metadata.get("tags"),
        metadata.get("title"),
    ])
    for domain in sorted(DEFAULT_DOMAIN_RECENCY_DAYS):
        if domain in tokens:
            return domain
    return ""


def _page_family_requirements(
    *,
    metadata: dict,
    body: str,
    page_key: str,
) -> set[str]:
    claim_text = _claim_text(body)
    return _semantic_tokens([
        page_key,
        metadata.get("title"),
        metadata.get("hub"),
        metadata.get("tags"),
        claim_text,
    ])


def _is_broad_page(*, metadata: dict, body: str, page_key: str) -> bool:
    tokens = _page_family_requirements(metadata=metadata, body=body, page_key=page_key)
    return bool(tokens.intersection(_BROAD_PAGE_TOKENS))


def _append_source_diversity_issues(
    issues: list[dict],
    *,
    wiki_dir: Path,
    sources: list[object],
    min_source_count: int,
    min_source_families: int,
    max_issues: int,
) -> None:
    if not wiki_dir.exists():
        return

    source_family_by_id = _source_families_by_id(sources)
    if not source_family_by_id:
        return
    issue_count = 0
    for path in sorted(wiki_dir.rglob("*.md")):
        try:
            metadata, body = parse_frontmatter(path)
        except OSError:
            continue
        page_type = str(metadata.get("page_type") or metadata.get("type") or "").strip()
        if page_type not in {"concept", "query", "wiki-page"}:
            continue
        page_key = path.relative_to(wiki_dir).with_suffix("").as_posix()
        if not _is_broad_page(metadata=metadata, body=body, page_key=page_key):
            continue
        page_sources = _metadata_source_ids(metadata)
        evidence_sources = _evidence_source_ids(body)
        source_ids = sorted(page_sources.union(evidence_sources))
        if not source_ids:
            continue
        families = sorted({
            source_family_by_id.get(source_id, "unknown")
            for source_id in source_ids
        })
        if len(source_ids) >= min_source_count and len(families) >= min_source_families:
            continue
        issues.append(make_issue(
            category="wiki-maintenance",
            detail=(
                f"Page '{page_key}' has low source diversity for a broad claim: "
                f"{len(source_ids)} source(s), {len(families)} source family/families"
            ),
            path=str(path),
            kind="maintenance",
            root_cause_type="manual_debt",
            fixability="manual",
            page=page_key,
            source_count=len(source_ids),
            source_families=families,
            min_source_count=min_source_count,
            min_source_families=min_source_families,
        ))
        issue_count += 1
        if issue_count >= max_issues:
            return


def _claim_tokens(*, metadata: dict, body: str, page_key: str) -> set[str]:
    return _semantic_tokens([
        page_key,
        metadata.get("title"),
        metadata.get("hub"),
        metadata.get("tags"),
        _claim_text(body),
    ])


def _claim_criticality_score(*, metadata: dict, body: str, page_key: str) -> int:
    tokens = set(_span_tokens(" ".join([
        page_key,
        str(metadata.get("title") or ""),
        str(metadata.get("hub") or ""),
        " ".join(str(item) for item in metadata.get("tags", []) if str(item).strip())
        if isinstance(metadata.get("tags"), list)
        else str(metadata.get("tags") or ""),
        _claim_text(body),
    ])))
    score = sum(_CRITICALITY_TOKEN_WEIGHTS.get(token, 0) for token in tokens)
    if _modal_claims(body):
        score += 2
    if _is_broad_page(metadata=metadata, body=body, page_key=page_key):
        score += 1
    return score


def _evidence_claim_overlap(quote: str, claim_tokens: set[str]) -> float:
    quote_tokens = set(_span_tokens(quote))
    if not quote_tokens or not claim_tokens:
        return 0.0
    quote_span = _normalized_span(quote)
    claim_span = " ".join(sorted(claim_tokens))
    if quote_span and quote_span in claim_span:
        return 1.0
    shared = quote_tokens.intersection(claim_tokens)
    denominator = min(len(quote_tokens), len(claim_tokens))
    return len(shared) / denominator if denominator else 0.0


def _append_cross_source_corroboration_issues(
    issues: list[dict],
    *,
    wiki_dir: Path,
    sources: list[object],
    min_corroborating_sources: int,
    min_corroborating_families: int,
    min_token_overlap: float,
    criticality_source_bonus_threshold: int,
    criticality_family_bonus_threshold: int,
    max_issues: int,
    min_criticality: int = DEFAULT_MIN_CLAIM_CORROBORATION_CRITICALITY,
) -> None:
    if not wiki_dir.exists():
        return

    source_family_by_id = _source_families_by_id(sources)
    if not source_family_by_id:
        return

    issue_count = 0
    for path in sorted(wiki_dir.rglob("*.md")):
        try:
            metadata, body = parse_frontmatter(path)
        except OSError:
            continue
        page_type = str(metadata.get("page_type") or metadata.get("type") or "").strip()
        if page_type not in {"concept", "query", "wiki-page"}:
            continue

        evidence_entries = _evidence_entries(body)
        if not evidence_entries:
            continue
        page_key = path.relative_to(wiki_dir).with_suffix("").as_posix()
        claim_tokens = _claim_tokens(metadata=metadata, body=body, page_key=page_key)
        if not claim_tokens:
            continue

        page_sources = _metadata_source_ids(metadata)
        evidence_sources = {entry["source_id"] for entry in evidence_entries}
        source_ids = sorted(page_sources.union(evidence_sources))
        if len(source_ids) < min_corroborating_sources:
            continue

        criticality = _claim_criticality_score(metadata=metadata, body=body, page_key=page_key)
        if criticality < min_criticality:
            continue
        required_sources = min_corroborating_sources
        if criticality_source_bonus_threshold > 0 and criticality >= criticality_source_bonus_threshold:
            required_sources += 1
        required_families = min_corroborating_families
        if criticality_family_bonus_threshold > 0 and criticality >= criticality_family_bonus_threshold:
            required_families += 1

        best_overlap_by_source: dict[str, float] = {}
        for entry in evidence_entries:
            source_id = entry["source_id"]
            overlap = _evidence_claim_overlap(entry["quote"], claim_tokens)
            best_overlap_by_source[source_id] = max(
                overlap,
                best_overlap_by_source.get(source_id, 0.0),
            )
        corroborating_sources = sorted(
            source_id
            for source_id, overlap in best_overlap_by_source.items()
            if overlap >= min_token_overlap
        )
        corroborating_families = sorted({
            source_family_by_id.get(source_id, "unknown")
            for source_id in corroborating_sources
        })
        if (
            len(corroborating_sources) >= required_sources
            and len(corroborating_families) >= required_families
        ):
            continue

        issues.append(make_issue(
            category="wiki-maintenance",
            detail=(
                f"Page '{page_key}' has weak cross-source corroboration for "
                f"claim criticality {criticality}: {len(corroborating_sources)}/"
                f"{required_sources} source(s), {len(corroborating_families)}/"
                f"{required_families} source family/families corroborate the claim"
            ),
            path=str(path),
            kind="maintenance",
            root_cause_type="manual_debt",
            fixability="manual",
            page=page_key,
            claim_criticality=criticality,
            corroborating_sources=len(corroborating_sources),
            required_corroborating_sources=required_sources,
            corroborating_source_ids=corroborating_sources,
            corroborating_families=corroborating_families,
            required_corroborating_families=required_families,
            min_token_overlap=min_token_overlap,
        ))
        issue_count += 1
        if issue_count >= max_issues:
            return


def _append_operational_status_issues(
    issues: list[dict],
    *,
    status: dict,
    wiki_dir: Path,
) -> None:
    """Surface shared wiki-status compiler actions in the maintenance scan."""
    actionable_tools = {"wiki-update", "wiki-reset"}
    for action in status.get("actions", []):
        if not isinstance(action, dict):
            continue
        tool = str(action.get("tool") or "").strip()
        if tool not in actionable_tools:
            continue
        command = str(action.get("command") or tool).strip()
        reason = str(action.get("reason") or "wiki status action is required").strip()
        compiler = status.get("compiler", {})
        issues.append(make_issue(
            category="wiki-maintenance",
            detail=f"Wiki status recommends {command}: {reason}",
            path=str(wiki_dir),
            kind="actionable",
            root_cause_type="repo_bug" if tool == "wiki-reset" else "manual_debt",
            fixability="manual",
            tool=tool,
            action=action,
            wiki_status_verdict=status.get("verdict", ""),
            sources_pending_or_changed=int(compiler.get("sources_pending_or_changed", 0) or 0)
            if isinstance(compiler, dict)
            else 0,
        ))


def _append_evidence_freshness_issues(
    issues: list[dict],
    *,
    wiki_dir: Path,
    runtime_wiki_dir: Path,
    min_quote_span_tokens: int,
    min_quote_token_coverage: float,
    old_evidence_days: int,
    domain_recency_days: dict[str, int],
) -> None:
    """Flag page citations that no longer map to page sources or current source state."""
    try:
        inventory = build_source_inventory(rag_dir=get_rag_dir(), wiki_dir=wiki_dir)
        compiler_state = load_compiler_state(runtime_wiki_dir)
    except (OSError, ValueError) as exc:
        issues.append(make_issue(
            category="wiki-maintenance",
            detail=f"Cannot inspect wiki evidence freshness: {exc}",
            path=str(runtime_wiki_dir),
            kind="actionable",
            root_cause_type="repo_bug",
            fixability="manual",
        ))
        return

    known_source_ids = {
        str(getattr(source, "source_id", "")).strip()
        for source in inventory
        if str(getattr(source, "source_id", "")).strip()
    }
    state_sources = getattr(compiler_state, "sources", {})
    if isinstance(state_sources, dict):
        known_source_ids.update(str(source_id).strip() for source_id in state_sources if str(source_id).strip())

    source_texts = _source_texts_by_id(list(inventory))
    source_modified = _source_modified_by_id(list(inventory))
    now = datetime.now(tz=timezone.utc)

    for path in sorted(wiki_dir.rglob("*.md")) if wiki_dir.exists() else []:
        try:
            metadata, body = parse_frontmatter(path)
        except OSError:
            continue
        page_type = str(metadata.get("page_type") or metadata.get("type") or "").strip()
        if page_type not in {"concept", "query", "wiki-page"}:
            continue
        evidence_entries = _evidence_entries(body)
        evidence_sources = {entry["source_id"] for entry in evidence_entries}
        if not evidence_sources:
            continue
        page_sources = _metadata_source_ids(metadata)
        missing_from_page = sorted(evidence_sources - page_sources) if page_sources else []
        missing_from_current_sources = sorted(evidence_sources - known_source_ids) if known_source_ids else []
        stale_sources = sorted(set(missing_from_page).union(missing_from_current_sources))
        page_key = path.relative_to(wiki_dir).with_suffix("").as_posix()
        if stale_sources:
            issues.append(make_issue(
                category="wiki-maintenance",
                detail=(
                    f"Page '{page_key}' has stale evidence citation(s): "
                    f"{', '.join(stale_sources)}"
                ),
                path=str(path),
                kind="maintenance",
                root_cause_type="manual_debt",
                fixability="manual",
                page=page_key,
                stale_evidence_sources=stale_sources,
                missing_from_page_sources=missing_from_page,
                missing_from_current_sources=missing_from_current_sources,
            ))

        unsupported_quotes: list[dict[str, str]] = []
        for entry in evidence_entries:
            quote = entry["quote"]
            quote_span = _normalized_span(quote)
            if len(quote_span.split()) < min_quote_span_tokens:
                continue
            source_text = source_texts.get(entry["source_id"], "")
            if not source_text:
                continue
            if not _quote_supported_by_source_text(
                quote,
                source_text,
                min_token_coverage=min_quote_token_coverage,
            ):
                unsupported_quotes.append({
                    "source_id": entry["source_id"],
                    "quote": quote,
                })
        if unsupported_quotes:
            sample = unsupported_quotes[0]
            issues.append(make_issue(
                category="wiki-maintenance",
                detail=(
                    f"Page '{page_key}' evidence quote is not found in source text "
                    f"for {sample['source_id']}"
                ),
                path=str(path),
                kind="maintenance",
                root_cause_type="manual_debt",
                fixability="manual",
                page=page_key,
                unsupported_quotes=unsupported_quotes,
            ))

        dated_evidence: list[tuple[str, int]] = []
        for source_id in sorted(evidence_sources):
            modified_at = source_modified.get(source_id)
            if modified_at is None:
                continue
            age_days = (now - modified_at).days
            dated_evidence.append((source_id, age_days))
        if dated_evidence and all(age_days > old_evidence_days for _source_id, age_days in dated_evidence):
            oldest = sorted(dated_evidence, key=lambda item: item[1], reverse=True)[:5]
            issues.append(make_issue(
                category="wiki-maintenance",
                detail=(
                    f"Page '{page_key}' relies only on old evidence: "
                    f"{oldest[0][0]} is {oldest[0][1]} day(s) old"
                ),
                path=str(path),
                kind="maintenance",
                root_cause_type="manual_debt",
                fixability="manual",
                page=page_key,
                old_evidence_days=old_evidence_days,
                evidence_ages=[{"source_id": source_id, "age_days": age_days} for source_id, age_days in oldest],
            ))

        domain = _page_domain(page_key=page_key, metadata=metadata)
        domain_days = domain_recency_days.get(domain, 0) if domain else 0
        if not domain_days or not dated_evidence:
            continue
        domain_stale = [
            (source_id, age_days)
            for source_id, age_days in dated_evidence
            if age_days > domain_days
        ]
        if not domain_stale:
            continue
        issues.append(make_issue(
            category="wiki-maintenance",
            detail=(
                f"Page '{page_key}' has {domain} domain recency issue(s): "
                f"{len(domain_stale)}/{len(dated_evidence)} evidence source(s) exceed {domain_days} day(s)"
            ),
            path=str(path),
            kind="maintenance",
            root_cause_type="manual_debt",
            fixability="manual",
            page=page_key,
            domain=domain,
            domain_recency_days=domain_days,
            stale_evidence=[
                {"source_id": source_id, "age_days": age_days}
                for source_id, age_days in sorted(domain_stale, key=lambda item: item[1], reverse=True)[:5]
            ],
        ))


def _normalized_claim_fragment(text: str) -> str:
    return " ".join(_semantic_tokens(text))


def _claim_text(body: str) -> str:
    sections = [
        _extract_markdown_section(body, "Current Thesis"),
        _extract_markdown_section(body, "Summary"),
        _extract_markdown_section(body, "Answer"),
        _extract_markdown_section(body, "What It Means"),
    ]
    return "\n".join(section for section in sections if section)


def _modal_claims(body: str) -> list[dict[str, object]]:
    claims: list[dict[str, object]] = []
    for sentence_match in _SENTENCE_RE.finditer(_claim_text(body)):
        sentence = sentence_match.group(0).strip()
        if not sentence:
            continue
        for match in _MODAL_CLAIM_RE.finditer(sentence):
            predicate = match.group("predicate").strip(" .;:,")
            normalized_predicate = _normalized_claim_fragment(predicate)
            if not normalized_predicate:
                continue
            claims.append({
                "modal": match.group("modal").lower(),
                "negative": bool(match.group("negation")),
                "subject": _normalized_claim_fragment(match.group("subject")),
                "predicate": normalized_predicate,
                "sentence": sentence,
            })
    return claims


def _report_page_keys(report: object) -> set[str]:
    pages = getattr(report, "pages", [])
    if not isinstance(pages, list):
        return set()
    return {
        str(page.get("page", "")).strip()
        for page in pages
        if isinstance(page, dict) and str(page.get("page", "")).strip()
    }


def _connected_page_pairs(report: object) -> set[tuple[str, str]]:
    connections = getattr(report, "connections", [])
    pairs: set[tuple[str, str]] = set()
    if not isinstance(connections, list):
        return pairs
    for connection in connections:
        if not isinstance(connection, dict):
            continue
        source = str(connection.get("from", "")).strip()
        target = str(connection.get("to", "")).strip()
        if not source or not target or source == target:
            continue
        pairs.add(tuple(sorted((source, target))))
    return pairs


def _append_explicit_contradiction_issues(
    issues: list[dict],
    *,
    report: object,
    wiki_dir: Path,
    max_issues: int,
) -> None:
    """Flag direct modal contradictions between related concept/query pages."""
    page_keys = _report_page_keys(report)
    if len(page_keys) < 2 or not wiki_dir.exists():
        return

    page_data: dict[str, dict[str, object]] = {}
    for page_key in page_keys:
        path = wiki_dir / f"{page_key}.md"
        if not path.exists():
            continue
        try:
            _metadata, body = parse_frontmatter(path)
        except OSError:
            continue
        claims = _modal_claims(body)
        if claims:
            page_data[page_key] = {"path": path, "claims": claims}

    if len(page_data) < 2:
        return

    pairs = _connected_page_pairs(report)
    issue_count = 0
    for left_key, right_key in sorted(pairs):
        left_data = page_data.get(left_key)
        right_data = page_data.get(right_key)
        if not left_data or not right_data:
            continue
        for left_claim in left_data["claims"]:
            for right_claim in right_data["claims"]:
                if left_claim["modal"] != right_claim["modal"]:
                    continue
                if left_claim["negative"] == right_claim["negative"]:
                    continue
                if left_claim["predicate"] != right_claim["predicate"]:
                    continue
                if left_claim["subject"] and right_claim["subject"] and left_claim["subject"] != right_claim["subject"]:
                    continue
                issues.append(make_issue(
                    category="wiki-maintenance",
                    detail=(
                        f"Related pages '{left_key}' and '{right_key}' have an explicit contradiction: "
                        f"'{left_claim['sentence']}' vs '{right_claim['sentence']}'"
                    ),
                    path=str(left_data["path"]),
                    kind="maintenance",
                    root_cause_type="manual_debt",
                    fixability="manual",
                    page=left_key,
                    related_page=right_key,
                    left_claim=left_claim["sentence"],
                    right_claim=right_claim["sentence"],
                ))
                issue_count += 1
                if issue_count >= max_issues:
                    return
                break


def _append_report_quality_issues(issues: list[dict], *, report: object, wiki_dir: Path) -> None:
    """Add report-level wiki quality defects that lint/rewrite queues can miss."""
    stats = getattr(report, "stats", {})
    pages = getattr(report, "pages", [])
    connections = getattr(report, "connections", [])
    if not isinstance(stats, dict):
        stats = {}
    if not isinstance(pages, list):
        pages = []
    if not isinstance(connections, list):
        connections = []

    inbound = {
        str(page.get("page", "")).strip(): 0
        for page in pages
        if isinstance(page, dict) and str(page.get("page", "")).strip()
    }
    outbound = dict(inbound)
    for connection in connections:
        if not isinstance(connection, dict):
            continue
        source = str(connection.get("from", "")).strip()
        target = str(connection.get("to", "")).strip()
        if source in outbound:
            outbound[source] += 1
        if target in inbound:
            inbound[target] += 1

    for page in pages:
        if not isinstance(page, dict):
            continue
        page_key = str(page.get("page", "")).strip()
        if not page_key:
            continue
        title = str(page.get("title", "")).strip()
        quality_flags = [
            str(flag).strip()
            for flag in page.get("quality_flags", [])
            if str(flag).strip()
        ] if isinstance(page.get("quality_flags", []), list) else []
        semantic_flags = sorted(
            set(quality_flags).intersection(
                {
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
                }
            )
        )
        if semantic_flags:
            issues.append(make_issue(
                category="wiki-maintenance",
                detail=(
                    f"Page '{page_key}' has semantic quality defect(s): "
                    f"{', '.join(semantic_flags)}"
                ),
                path=str(wiki_dir / f"{page_key}.md"),
                kind="actionable",
                root_cause_type="repo_bug",
                fixability="manual",
                page=page_key,
                title=title,
                quality_score=page.get("quality_score", 0),
                reasons=semantic_flags,
            ))
        if page_key in inbound and (inbound[page_key] == 0 or outbound.get(page_key, 0) == 0):
            issues.append(make_issue(
                category="wiki-maintenance",
                detail=f"Page '{page_key}' has no inbound or outbound wiki links",
                path=str(wiki_dir / f"{page_key}.md"),
                kind="actionable",
                root_cause_type="manual_debt",
                fixability="manual",
                page=page_key,
                title=title,
                inbound_links=inbound[page_key],
                outbound_links=outbound.get(page_key, 0),
            ))

    if int(stats.get("pages_missing_source_fingerprint", 0) or 0) > 0:
        issues.append(make_issue(
            category="wiki-maintenance",
            detail=(
                f"{stats['pages_missing_source_fingerprint']} wiki page(s) are missing "
                "source fingerprints"
            ),
            path=str(wiki_dir),
            kind="actionable",
            root_cause_type="repo_bug",
            fixability="manual",
            missing_source_fingerprints=stats["pages_missing_source_fingerprint"],
        ))


def scan(ctx: OpsContext) -> ScanResult:
    """Scan the wiki for structural, freshness, and editorial maintenance debt."""
    wiki_dir, runtime_wiki_dir, vault_dir, documents_dir = _wiki_context()

    lint = lint_wiki(wiki_dir=wiki_dir)
    issues: list[dict] = []

    for name in lint.get("missing_required", []):
        issues.append(make_issue(
            category="wiki-maintenance",
            detail=f"Missing required wiki root page '{name}'",
            path=str(wiki_dir / f"{name}.md"),
            kind="actionable",
            root_cause_type="repo_bug",
            fixability="manual",
        ))
    for target in lint.get("missing_links", []):
        issues.append(make_issue(
            category="wiki-maintenance",
            detail=f"Broken wikilink target '{target}'",
            path=str(wiki_dir),
            kind="actionable",
            root_cause_type="repo_bug",
            fixability="manual",
        ))
    for page in lint.get("orphan_pages", []):
        issues.append(make_issue(
            category="wiki-maintenance",
            detail=f"Wiki page '{page}' has no inbound links",
            path=str(wiki_dir / f"{page}.md"),
            kind="actionable",
            root_cause_type="manual_debt",
            fixability="manual",
        ))
    for duplicate in lint.get("duplicate_titles", []):
        issues.append(make_issue(
            category="wiki-maintenance",
            detail=f"Duplicate wiki titles detected: {duplicate}",
            path=str(wiki_dir),
            kind="actionable",
            root_cause_type="manual_debt",
            fixability="manual",
        ))
    for item in lint.get("broken_links", []):
        page = str(item.get("page", "")).strip()
        target = str(item.get("target", "")).strip()
        issues.append(make_issue(
            category="wiki-maintenance",
            detail=f"Broken concept wikilink '{target}' on page '{page}'",
            path=str(wiki_dir / f"{page}.md") if page else str(wiki_dir),
            kind="actionable",
            root_cause_type="repo_bug",
            fixability="manual",
            page=page,
            target=target,
        ))
    for item in lint.get("legacy_pages", []):
        page = str(item.get("page", "")).strip()
        reasons = item.get("reasons", [])
        if not isinstance(reasons, list):
            reasons = []
        reason_text = ", ".join(str(reason).strip() for reason in reasons if str(reason).strip())
        issues.append(make_issue(
            category="wiki-maintenance",
            detail=f"Legacy wiki page '{page}' detected ({reason_text})",
            path=str(wiki_dir / f"{page}.md") if page else str(wiki_dir),
            kind="actionable",
            root_cause_type="manual_debt",
            fixability="manual",
            page=page,
            reasons=reasons,
        ))
    for item in lint.get("duplicate_aliases", []):
        alias = str(item.get("alias", "")).strip()
        pages = item.get("pages", [])
        if not isinstance(pages, list):
            pages = []
        page_list = [str(page).strip() for page in pages if str(page).strip()]
        issues.append(make_issue(
            category="wiki-maintenance",
            detail=f"Duplicate wiki alias '{alias}' used by pages: {', '.join(page_list)}",
            path=str(wiki_dir / f"{page_list[0]}.md") if page_list else str(wiki_dir),
            kind="actionable",
            root_cause_type="manual_debt",
            fixability="manual",
            alias=alias,
            pages=page_list,
        ))
    for violation in lint.get("schema_violations", []):
        issues.append(make_issue(
            category="wiki-maintenance",
            detail=f"Schema violation: {violation}",
            path=str(wiki_dir),
            kind="actionable",
            root_cause_type="repo_bug",
            fixability="manual",
        ))

    if ctx.config.get("include_operational_status"):
        try:
            status = build_wiki_status(wiki_dir=wiki_dir, runtime_wiki_dir=runtime_wiki_dir)
            _append_operational_status_issues(issues, status=status, wiki_dir=wiki_dir)
        except (OSError, ValueError) as exc:
            issues.append(make_issue(
                category="wiki-maintenance",
                detail=f"Cannot inspect wiki operational status: {exc}",
                path=str(wiki_dir),
                kind="actionable",
                root_cause_type="repo_bug",
                fixability="manual",
            ))

    if ctx.difficulty >= 1:
        stale_pages = find_stale_pages(
            wiki_dir=wiki_dir,
            vault_dir=vault_dir,
            documents_dir=documents_dir,
        )
        for item in stale_pages:
            issues.append(make_issue(
                category="wiki-maintenance",
                detail=f"Page '{item['page']}' is stale relative to its source fingerprint",
                path=str(wiki_dir / f"{item['page']}.md"),
                kind="actionable",
                root_cause_type="manual_debt",
                fixability="manual",
                page=item["page"],
                hub=item.get("hub", ""),
                title=item.get("title", ""),
                sources=item.get("sources", []),
            ))

    report = None

    if ctx.difficulty >= 2:
        max_candidates = int(ctx.config.get("max_rewrite_candidates", 10) or 10)
        rewrite_candidates = find_rewrite_candidates(wiki_dir=wiki_dir)[:max_candidates]
        for item in rewrite_candidates:
            issues.append(make_issue(
                category="wiki-maintenance",
                detail=(
                    f"Page '{item['page']}' scored {item['quality_score']}/100 and should be rewritten "
                    f"({', '.join(item['reasons'])})"
                ),
                path=str(wiki_dir / f"{item['page']}.md"),
                kind="actionable",
                root_cause_type="manual_debt",
                fixability="manual",
                page=item["page"],
                hub=item.get("hub", ""),
                title=item.get("title", ""),
                quality_score=item.get("quality_score", 0),
                reasons=item.get("reasons", []),
            ))
        report = aggregate_report_data(
            wiki_dir=wiki_dir,
            runtime_wiki_dir=runtime_wiki_dir,
            portfolio_dir=vault_dir / "portfolio",
            vault_dir=vault_dir,
            documents_dir=documents_dir,
        )
        _append_report_quality_issues(issues, report=report, wiki_dir=wiki_dir)

    if ctx.difficulty >= 3:
        if report is None:
            report = aggregate_report_data(
                wiki_dir=wiki_dir,
                runtime_wiki_dir=runtime_wiki_dir,
                portfolio_dir=vault_dir / "portfolio",
                vault_dir=vault_dir,
                documents_dir=documents_dir,
            )
        min_density = float(
            ctx.config.get("min_hub_edge_density", DEFAULT_MIN_HUB_EDGE_DENSITY)
            or DEFAULT_MIN_HUB_EDGE_DENSITY
        )
        max_density_only_pages = int(
            ctx.config.get("max_density_only_pages", DEFAULT_MAX_DENSITY_ONLY_PAGES)
            or DEFAULT_MAX_DENSITY_ONLY_PAGES
        )
        min_internal_links_per_page = float(
            ctx.config.get("min_internal_links_per_page", DEFAULT_MIN_INTERNAL_LINKS_PER_PAGE)
            or DEFAULT_MIN_INTERNAL_LINKS_PER_PAGE
        )
        for hub in _iter_report_hubs(report):
            density = float(hub.get("hub_edge_density", 0.0) or 0.0)
            if not _hub_has_weak_internal_graph(
                hub,
                min_density=min_density,
                max_density_only_pages=max_density_only_pages,
                min_internal_links_per_page=min_internal_links_per_page,
            ):
                continue
            page_count = int(hub.get("page_count", 0) or 0)
            internal_edges = int(hub.get("internal_edges", 0) or 0)
            avg_internal_links = internal_edges / page_count if page_count else 0.0
            issues.append(make_issue(
                category="wiki-maintenance",
                detail=(
                    f"Hub '{hub['name']}' has weak internal cross-link density "
                    f"({density:.2f} < {min_density:.2f}; "
                    f"{avg_internal_links:.2f} internal links/page)"
                ),
                path=str(wiki_dir / hub["name"]),
                kind="maintenance",
                root_cause_type="manual_debt",
                fixability="manual",
                hub=hub["name"],
                hub_edge_density=density,
                page_count=page_count,
                internal_edges=internal_edges,
                avg_internal_links_per_page=round(avg_internal_links, 2),
            ))

    if ctx.difficulty >= 4:
        if report is None:
            report = aggregate_report_data(
                wiki_dir=wiki_dir,
                runtime_wiki_dir=runtime_wiki_dir,
                portfolio_dir=vault_dir / "portfolio",
                vault_dir=vault_dir,
                documents_dir=documents_dir,
            )
        min_bad_link_count = int(
            ctx.config.get("min_bad_link_count", DEFAULT_MIN_BAD_LINK_COUNT)
            or DEFAULT_MIN_BAD_LINK_COUNT
        )
        max_unsupported_link_ratio = float(
            ctx.config.get("max_unsupported_link_ratio", DEFAULT_MAX_UNSUPPORTED_LINK_RATIO)
            or DEFAULT_MAX_UNSUPPORTED_LINK_RATIO
        )
        _append_semantic_adjacency_issues(
            issues,
            report=report,
            wiki_dir=wiki_dir,
            min_bad_link_count=min_bad_link_count,
            max_unsupported_link_ratio=max_unsupported_link_ratio,
        )
        min_source_cluster_size = int(
            ctx.config.get("min_source_cluster_size", DEFAULT_MIN_SOURCE_CLUSTER_SIZE)
            or DEFAULT_MIN_SOURCE_CLUSTER_SIZE
        )
        min_source_cluster_coverage_ratio = float(
            ctx.config.get(
                "min_source_cluster_coverage_ratio",
                DEFAULT_MIN_SOURCE_CLUSTER_COVERAGE_RATIO,
            )
            or DEFAULT_MIN_SOURCE_CLUSTER_COVERAGE_RATIO
        )
        max_source_cluster_issues = int(
            ctx.config.get("max_source_cluster_issues", DEFAULT_MAX_SOURCE_CLUSTER_ISSUES)
            or DEFAULT_MAX_SOURCE_CLUSTER_ISSUES
        )
        _append_source_cluster_coverage_issues(
            issues,
            wiki_dir=wiki_dir,
            runtime_wiki_dir=runtime_wiki_dir,
            min_cluster_size=min_source_cluster_size,
            min_coverage_ratio=min_source_cluster_coverage_ratio,
            max_issues=max_source_cluster_issues,
        )
        try:
            source_inventory = build_source_inventory(rag_dir=get_rag_dir(), wiki_dir=wiki_dir)
        except OSError as exc:
            issues.append(make_issue(
                category="wiki-maintenance",
                detail=f"Cannot inspect wiki source diversity: {exc}",
                path=str(wiki_dir),
                kind="actionable",
                root_cause_type="repo_bug",
                fixability="manual",
            ))
            source_inventory = []
        _append_source_diversity_issues(
            issues,
            wiki_dir=wiki_dir,
            sources=source_inventory,
            min_source_count=int(
                ctx.config.get("min_broad_page_source_count", DEFAULT_MIN_BROAD_PAGE_SOURCE_COUNT)
                or DEFAULT_MIN_BROAD_PAGE_SOURCE_COUNT
            ),
            min_source_families=int(
                ctx.config.get("min_broad_page_source_families", DEFAULT_MIN_BROAD_PAGE_SOURCE_FAMILIES)
                or DEFAULT_MIN_BROAD_PAGE_SOURCE_FAMILIES
            ),
            max_issues=int(
                ctx.config.get("max_source_diversity_issues", DEFAULT_MAX_SOURCE_DIVERSITY_ISSUES)
                or DEFAULT_MAX_SOURCE_DIVERSITY_ISSUES
            ),
        )
        _append_cross_source_corroboration_issues(
            issues,
            wiki_dir=wiki_dir,
            sources=source_inventory,
            min_corroborating_sources=int(
                ctx.config.get(
                    "min_claim_corroborating_sources",
                    DEFAULT_MIN_CLAIM_CORROBORATING_SOURCES,
                )
                or DEFAULT_MIN_CLAIM_CORROBORATING_SOURCES
            ),
            min_corroborating_families=int(
                ctx.config.get(
                    "min_claim_corroborating_families",
                    DEFAULT_MIN_CLAIM_CORROBORATING_FAMILIES,
                )
                or DEFAULT_MIN_CLAIM_CORROBORATING_FAMILIES
            ),
            min_token_overlap=float(
                ctx.config.get(
                    "min_claim_corroboration_token_overlap",
                    DEFAULT_MIN_CLAIM_CORROBORATION_TOKEN_OVERLAP,
                )
                or DEFAULT_MIN_CLAIM_CORROBORATION_TOKEN_OVERLAP
            ),
            criticality_source_bonus_threshold=int(
                ctx.config.get(
                    "criticality_source_bonus_threshold",
                    DEFAULT_CRITICALITY_SOURCE_BONUS_THRESHOLD,
                )
                or DEFAULT_CRITICALITY_SOURCE_BONUS_THRESHOLD
            ),
            criticality_family_bonus_threshold=int(
                ctx.config.get(
                    "criticality_family_bonus_threshold",
                    DEFAULT_CRITICALITY_FAMILY_BONUS_THRESHOLD,
                )
                or DEFAULT_CRITICALITY_FAMILY_BONUS_THRESHOLD
            ),
            max_issues=int(
                ctx.config.get("max_corroboration_issues", DEFAULT_MAX_CORROBORATION_ISSUES)
                or DEFAULT_MAX_CORROBORATION_ISSUES
            ),
            min_criticality=int(
                ctx.config.get(
                    "min_claim_corroboration_criticality",
                    DEFAULT_MIN_CLAIM_CORROBORATION_CRITICALITY,
                )
                or DEFAULT_MIN_CLAIM_CORROBORATION_CRITICALITY
            ),
        )
        _append_evidence_freshness_issues(
            issues,
            wiki_dir=wiki_dir,
            runtime_wiki_dir=runtime_wiki_dir,
            min_quote_span_tokens=int(
                ctx.config.get("min_quote_span_tokens", DEFAULT_MIN_QUOTE_SPAN_TOKENS)
                or DEFAULT_MIN_QUOTE_SPAN_TOKENS
            ),
            min_quote_token_coverage=float(
                ctx.config.get("min_quote_token_coverage", DEFAULT_MIN_QUOTE_TOKEN_COVERAGE)
                or DEFAULT_MIN_QUOTE_TOKEN_COVERAGE
            ),
            old_evidence_days=int(
                ctx.config.get("old_evidence_days", DEFAULT_OLD_EVIDENCE_DAYS)
                or DEFAULT_OLD_EVIDENCE_DAYS
            ),
            domain_recency_days=_domain_recency_config(ctx.config.get("domain_recency_days")),
        )
        max_contradiction_issues = int(
            ctx.config.get("max_contradiction_issues", DEFAULT_MAX_CONTRADICTION_ISSUES)
            or DEFAULT_MAX_CONTRADICTION_ISSUES
        )
        _append_explicit_contradiction_issues(
            issues,
            report=report,
            wiki_dir=wiki_dir,
            max_issues=max_contradiction_issues,
        )
        if not issues:
            issues.append(evolution_gap(
                "Wiki maintenance now validates structural lint, freshness, rewrite candidates, "
                "hub graph density, semantic adjacency, source-family coverage, evidence citation "
                "freshness, quote-content spans, temporal evidence age, and direct modal "
                "contradictions, source diversity, cross-source corroboration, claim "
                "criticality weighting, and domain-specific recency. Next: add "
                "cross-source disagreement clustering and evidence decay trend reporting.",
                category="wiki-maintenance",
            ))

    severity = "warning" if issues else "info"
    health = "degraded" if issues else "verified"
    summary = f"{len(issues)} wiki maintenance issue(s) across {lint.get('pages', 0)} pages"
    return ScanResult(
        issues=issues,
        summary=summary,
        severity=severity,
        health=health,
        items_scanned=lint.get("pages", 0),
    )


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    """Write a report for wiki maintenance work discovered by the scan."""
    if not issues:
        return FixResult(success=True, summary="No wiki maintenance issues")
    return report_only_fix(ctx, "wiki-maintenance.json", issues, noun="wiki issue")
