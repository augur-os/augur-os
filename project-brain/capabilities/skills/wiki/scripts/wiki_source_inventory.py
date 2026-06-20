from __future__ import annotations

from pathlib import Path
from typing import Any

from skills.wiki.scripts.wiki_concept_models import SourceDescriptor
from skills.wiki.scripts.wiki_tier import normalize_tier, tier_for_surface, weight_for_tier
from src.config.paths import get_project_root
from src.lib.frontmatter_utils import parse_frontmatter
from src.lib.relationship_index import RelationshipIndex

ALLOWED_TYPES = {
    "ask",
    "action",
    "actions",
    "adr",
    "adrs",
    "command",
    "commands",
    "document",
    "documents",
    "doc",
    "docs",
    "integration",
    "integrations",
    "page",
    "pages",
    "skill",
    "skills",
    "synthesis",
    "syntheses",
    "vault",
    "memory",
    "client_memory",
    "memory_files",
    "episodic",
    "codex_threads",
    "gemini",
    "copilot",
    "external_client",
}
EXCLUDED_TYPES = {
    "wiki",
    "logs",
    "background-routines",
    "source-summary",
    "concept",
    "query",
}


def build_source_inventory(*, rag_dir: Path, wiki_dir: Path) -> list[SourceDescriptor]:
    inventory: list[SourceDescriptor] = []
    if not rag_dir.exists():
        return inventory

    rag_root = rag_dir.resolve(strict=False)
    wiki_root = wiki_dir.resolve(strict=False)
    vault_root = wiki_root.parent
    project_root = get_project_root().resolve(strict=False)
    relationship_index = RelationshipIndex.build(vault_root)

    for entry_path in sorted(rag_dir.rglob("*.md")):
        entry_ref = entry_path.resolve(strict=False)
        if _is_under(entry_ref, rag_root / "wiki"):
            continue

        try:
            frontmatter, body = parse_frontmatter(entry_path)
        except OSError:
            continue

        entry_type = _text(frontmatter, "type")
        normalized_type = _normalized_type(entry_type)
        if not normalized_type or normalized_type in EXCLUDED_TYPES or normalized_type not in ALLOWED_TYPES:
            continue

        source_path = _text(frontmatter, "source_path")
        if not source_path:
            continue

        if _source_path_is_under_wiki(
            source_path=source_path,
            wiki_root=wiki_root,
            rag_root=rag_root,
            project_root=project_root,
        ):
            continue

        if _source_path_is_release_staging(source_path, vault_root=wiki_root.parent):
            continue

        if _source_path_is_inbox_holding(source_path):
            continue

        if _source_path_is_repo_local_generated_client_wrapper(source_path):
            continue

        checksum = _text(frontmatter, "checksum")
        if not checksum:
            continue

        title = _text(frontmatter, "name") or _title_fallback(source_path)
        modified_at = _text(frontmatter, "modified") or _text(frontmatter, "modifiedTime")

        source_surface = _source_surface_for(normalized_type, frontmatter)
        tier = _tier_for_source(source_surface, frontmatter)
        metadata: dict[str, Any] = {
            "rag_entry": str(entry_path),
            "hub": _source_hub(frontmatter=frontmatter, source_path=source_path, entry_path=entry_path),
            "source_family": _source_family(entry_path=entry_path, rag_dir=rag_dir, fallback=normalized_type),
            "source_surface": source_surface,
            "tier": tier,
            "weight": weight_for_tier(tier),
        }
        relationships = _relationship_map(frontmatter)
        indexed_relationships = relationship_index.relationships_for(Path(source_path))
        for field, targets in indexed_relationships.items():
            relationships.setdefault(field, [])
            relationships[field] = list(dict.fromkeys([*relationships[field], *targets]))
        if relationships:
            metadata["relationships"] = relationships
            metadata["relationship_targets"] = _relationship_targets(relationships)

        inventory.append(
            SourceDescriptor(
                source_id=f"{normalized_type}:{source_path}",
                kind=normalized_type,
                title=title,
                source_path=source_path,
                checksum=checksum,
                modified_at=modified_at,
                priority=_priority_for(normalized_type, body),
                metadata=metadata,
            )
        )

    return _dedupe_by_physical_source(inventory)


def _dedupe_by_physical_source(inventory: list[SourceDescriptor]) -> list[SourceDescriptor]:
    by_key: dict[str, SourceDescriptor] = {}
    duplicate_ids: dict[str, list[str]] = {}

    for source in inventory:
        key = _canonical_source_key(source.source_path)
        current = by_key.get(key)
        if current is None:
            by_key[key] = source
            duplicate_ids[key] = []
            continue

        winner, duplicate = _choose_canonical_source(current, source)
        by_key[key] = winner
        duplicate_ids[key].append(duplicate.source_id)

    deduped: list[SourceDescriptor] = []
    for source in by_key.values():
        key = _canonical_source_key(source.source_path)
        duplicates = sorted(dict.fromkeys(duplicate_ids.get(key, [])))
        if duplicates:
            metadata = dict(source.metadata)
            metadata["duplicate_source_ids"] = duplicates
            source = SourceDescriptor(
                source_id=source.source_id,
                kind=source.kind,
                title=source.title,
                source_path=source.source_path,
                checksum=source.checksum,
                modified_at=source.modified_at,
                priority=source.priority,
                metadata=metadata,
            )
        deduped.append(source)

    return sorted(deduped, key=lambda item: item.source_id)


def _canonical_source_key(source_path: str) -> str:
    return Path(source_path).expanduser().resolve(strict=False).as_posix()


def _choose_canonical_source(left: SourceDescriptor, right: SourceDescriptor) -> tuple[SourceDescriptor, SourceDescriptor]:
    return (left, right) if _source_rank(left) >= _source_rank(right) else (right, left)


def _source_rank(source: SourceDescriptor) -> tuple[int, int, str]:
    kind_rank = {
        "ask": 100,
        "synthesis": 95,
        "adr": 92,
        "adrs": 92,
        "vault": 90,
        "memory": 88,
        "client_memory": 88,
        "memory_files": 88,
        "episodic": 88,
        "codex_threads": 88,
        "gemini": 82,
        "copilot": 82,
        "external_client": 82,
        "document": 85,
        "documents": 85,
        "doc": 85,
        "docs": 85,
        "page": 60,
        "pages": 60,
        "integration": 55,
        "integrations": 55,
        "skill": 45,
        "skills": 45,
        "command": 35,
        "commands": 35,
        "action": 30,
        "actions": 30,
    }.get(source.kind, 0)
    return (kind_rank, source.priority, source.source_id)


def _priority_for(entry_type: str, body: str) -> int:
    kind = _normalized_type(entry_type)
    if kind in {"ask", "synthesis", "client_memory", "memory_files", "episodic", "codex_threads"}:
        return 100
    if kind in {"gemini", "copilot", "external_client", "memory"}:
        return 85
    if kind in {"vault", "documents", "document"}:
        return 80
    if kind in {"adr", "adrs"}:
        return 70
    if kind in {"page", "pages", "integration", "integrations"}:
        return 50
    if kind in {"skill", "skills"}:
        return 40
    if kind in {"command", "commands"}:
        return 30
    if kind in {
        "action",
        "actions",
    }:
        return 25
    if str(body).strip():
        return 40
    return 10


def _text(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if isinstance(value, str):
        return value.strip()
    return ""


def _source_surface_for(normalized_type: str, frontmatter: dict[str, Any]) -> str:
    explicit = _text(frontmatter, "source_surface") or _text(frontmatter, "sourceSurface")
    if explicit:
        return explicit
    if normalized_type in {"ask", "synthesis", "syntheses"}:
        return "ask_outcomes"
    if normalized_type in {"document", "documents", "doc", "docs"}:
        return "documents"
    if normalized_type in {"skill", "skills", "command", "commands", "action", "actions"}:
        return "skills"
    if normalized_type in {"adr", "adrs"}:
        return "adr_targets"
    if normalized_type in {"memory", "client_memory", "memory_files"}:
        return "client_memory"
    if normalized_type in {"episodic", "codex_threads", "gemini", "copilot", "external_client", "vault"}:
        return normalized_type
    return normalized_type


def _tier_for_source(source_surface: str, frontmatter: dict[str, Any]) -> str:
    frontmatter_tier = normalize_tier(frontmatter.get("wiki_tier"), default="")
    if frontmatter_tier:
        return frontmatter_tier
    explicit_tier = normalize_tier(frontmatter.get("tier"), default="")
    if explicit_tier:
        return explicit_tier
    return tier_for_surface(source_surface)


def _relationship_map(frontmatter: dict[str, Any]) -> dict[str, list[str]]:
    relationships = frontmatter.get("relationships")
    if not isinstance(relationships, dict):
        return {}
    normalized: dict[str, list[str]] = {}
    for field, targets in relationships.items():
        if not isinstance(field, str) or not isinstance(targets, list):
            continue
        values = [str(target).strip() for target in targets if str(target).strip()]
        if values:
            normalized[field] = list(dict.fromkeys(values))
    return normalized


def _relationship_targets(relationships: dict[str, list[str]]) -> list[str]:
    return list(dict.fromkeys(
        target for field_targets in relationships.values() for target in field_targets
    ))


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _normalized_type(entry_type: str) -> str:
    return entry_type.strip().lower()


def _title_fallback(source_path: str) -> str:
    return Path(source_path).stem


def _source_path_is_release_staging(source_path: str, *, vault_root: Path | None = None) -> bool:
    # drafts/staging/ is the release-staging holding area. Legacy _drafts/staging/
    # remains excluded during migration. Generic scanners and autoloops must
    # ignore these directories, so the wiki source inventory must not surface
    # scaffold READMEs and release manifests as durable concept candidates.
    normalized = source_path.replace("\\", "/")
    path = Path(normalized)
    rel = path
    if vault_root is not None and path.is_absolute():
        try:
            rel = path.resolve(strict=False).relative_to(vault_root.resolve(strict=False))
        except ValueError:
            return False
    parts = rel.parts
    return len(parts) >= 2 and parts[0] in {"drafts", "_drafts"} and parts[1] == "staging"


def _source_path_is_inbox_holding(source_path: str) -> bool:
    # Documents/inbox/ (and any /<name>/inbox/ holding area) is the triage
    # staging zone for incoming documents — receipts, scanned letters,
    # short-lived bureaucratic records, OCR'd PDFs that haven't been
    # categorized yet. Files genuinely worth durable wiki coverage are
    # promoted out of inbox by the user during triage. Surfacing inbox
    # contents in the wiki extraction batch wastes batch slots on transient
    # records (medical letters, insurance policy adjustments, OCR artifacts)
    # that will never feed an 8-15-source compound concept.
    normalized = source_path.replace("\\", "/").lower()
    return "/inbox/" in normalized


def _source_path_is_repo_local_generated_client_wrapper(source_path: str) -> bool:
    normalized = source_path.replace("\\", "/").lower().lstrip("./")
    prefixes = (
        "claude/skills/",
        "codex/skills/",
        "gemini/skills/",
        "opencode/skills/",
    )
    return any(normalized.startswith(prefix) for prefix in prefixes)


def _source_path_is_under_wiki(*, source_path: str, wiki_root: Path, rag_root: Path, project_root: Path) -> bool:
    raw_path = Path(source_path)
    candidates: list[Path] = []

    if raw_path.is_absolute():
        candidates.append(raw_path.resolve(strict=False))
    else:
        for base in (wiki_root.parent, rag_root.parent, project_root):
            candidates.append((base / raw_path).resolve(strict=False))

    for candidate in candidates:
        if _is_under(candidate, wiki_root):
            return True
    return False


def _source_family(*, entry_path: Path, rag_dir: Path, fallback: str) -> str:
    try:
        parts = entry_path.relative_to(rag_dir).parts
    except ValueError:
        return fallback
    if not parts:
        return fallback
    return parts[0] or fallback


def _source_hub(*, frontmatter: dict[str, Any], source_path: str, entry_path: Path) -> str:
    explicit = _canonical_hub(_text(frontmatter, "hub"))
    if explicit:
        return explicit
    inferred = _canonical_hub(source_path)
    if inferred:
        return inferred
    return _canonical_hub(entry_path.as_posix())


def _canonical_hub(value: str) -> str:
    text = str(value).strip().lower().replace("\\", "/")
    if not text or text in {"unknown", "general"}:
        return ""
    if text in {"adaptive", "brain", "career", "command", "life", "studio"}:
        return text
    if text in {"dev"}:
        return "adaptive"
    if text in {"core", "system"}:
        return "command"
    if any(
        marker in text
        for marker in (
            "venture-augur",
            "linkedin-writer",
            "websites",
            "presentations",
            "market-research",
            "geo-",
            "/geo",
            "codex-primary-runtime/slides",
            "codex-primary-runtime/spreadsheets",
            "imagegen",
            "frontend-design",
            "ui-ux",
        )
    ):
        return "studio"
    if any(marker in text for marker in ("career-ops", "/career/", "interview", "job-search", "/cv.md", "second-career", "sample-fitout-project")):
        return "career"
    if any(marker in text for marker in ("finance", "health", "lifestyle", "family", "recipe", "/apple/", "eisenhower", "/growth/")):
        return "life"
    if any(
        marker in text
        for marker in (
            "skills/augur-core",
            "/commands/",
            "command",
            "adr",
            "codex",
            "plugin-creator",
            "skill-installer",
            "find-skills",
            "openai-docs",
            "claude-md-management",
            "claude-skills-guide",
            "mcp-enhanced",
        )
    ):
        return "command"
    if any(
        marker in text
        for marker in (
            "skills/routine-",
            "daemon",
            "platform-admin",
            "adaptive",
            "ide-integration",
            "superpowers",
            "code-architect",
            "code-explorer",
            "code-reviewer",
            "test-driven-development",
            "systematic-debugging",
            "using-git-worktrees",
        )
    ):
        return "adaptive"
    if any(marker in text for marker in ("memory", "knowledge", "advisor", "brain")):
        return "brain"
    return ""
