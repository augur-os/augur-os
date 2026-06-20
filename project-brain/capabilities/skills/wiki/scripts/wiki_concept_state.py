"""Runtime state for the concept-first wiki compiler."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from skills.wiki.scripts.wiki_concept_models import ConceptEvidence, ExtractedConcept
from src.lib.frontmatter_utils import parse_frontmatter

STATE_FILENAME = "concept-compiler-state.json"
COMPILER_VERSION = "concept-article-v4"


def _require_dict(data: Any, label: str) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError(f"{label} must be a JSON object")
    return data


def _require_text(data: dict[str, Any], key: str) -> str:
    if key not in data:
        raise ValueError(f"Missing required field: {key}")
    value = data[key]
    if not isinstance(value, str):
        raise ValueError(f"Field {key} must be a string")
    text = value.strip()
    if not text:
        raise ValueError(f"Field {key} must be a non-empty string")
    return text


def _optional_text(data: dict[str, Any], key: str) -> str | None:
    if key not in data or data[key] is None:
        return None
    value = data[key]
    if not isinstance(value, str):
        raise ValueError(f"Field {key} must be a string")
    return value


def _require_list(data: dict[str, Any], key: str) -> list[Any]:
    if key not in data:
        raise ValueError(f"Missing required field: {key}")
    value = data[key]
    if not isinstance(value, list):
        raise ValueError(f"Field {key} must be a list")
    return value


def _require_list_of_dicts(value: Any, label: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError(f"Field {label} must be a list")
    result: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError(f"Field {label} items must be objects")
        result.append(item)
    return result


def _require_dict_of_list_dicts(value: Any, label: str) -> dict[str, list[dict[str, Any]]]:
    if not isinstance(value, dict):
        raise ValueError(f"Field {label} must be a JSON object")
    result: dict[str, list[dict[str, Any]]] = {}
    for key, item in value.items():
        result[str(key)] = _require_list_of_dicts(item, label)
    return result


def _require_dict_of_list_text(value: Any, label: str) -> dict[str, list[str]]:
    if not isinstance(value, dict):
        raise ValueError(f"Field {label} must be a JSON object")
    result: dict[str, list[str]] = {}
    for key, item in value.items():
        if not isinstance(item, list):
            raise ValueError(f"Field {label} must map to lists of strings")
        normalized: list[str] = []
        for slug in item:
            if not isinstance(slug, str):
                raise ValueError(f"Field {label} items must be strings")
            normalized.append(slug)
        result[str(key)] = normalized
    return result


@dataclass
class SourceCompileState:
    checksum: str
    compiler_version: str = COMPILER_VERSION
    extracted_at: str | None = None
    generated_at: str | None = None
    concept_slugs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "checksum": self.checksum,
            "compiler_version": self.compiler_version,
            "extracted_at": self.extracted_at,
            "generated_at": self.generated_at,
            "concept_slugs": list(self.concept_slugs),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], *, fallback_compiler_version: str = COMPILER_VERSION) -> SourceCompileState:
        data = _require_dict(data, "source state")
        raw_slugs = _require_list(data, "concept_slugs")
        normalized_slugs = sorted({str(item) for item in raw_slugs})
        return cls(
            checksum=_require_text(data, "checksum"),
            compiler_version=_optional_text(data, "compiler_version") or fallback_compiler_version,
            extracted_at=_optional_text(data, "extracted_at"),
            generated_at=_optional_text(data, "generated_at"),
            concept_slugs=normalized_slugs,
        )


@dataclass
class WikiCompilerState:
    compiler_version: str = COMPILER_VERSION
    sources: dict[str, SourceCompileState] = field(default_factory=dict)
    extracted_concepts: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    frozen_slugs: dict[str, list[str]] = field(default_factory=dict)

    def record_processed(self, source_id: str, checksum: str, processed_at: str) -> None:
        self.sources[source_id] = SourceCompileState(
            checksum=checksum,
            compiler_version=COMPILER_VERSION,
            extracted_at=processed_at,
            concept_slugs=[],
        )
        self.extracted_concepts[source_id] = []

    def record_extraction(
        self,
        source_id: str,
        checksum: str,
        concepts: list[ExtractedConcept],
        extracted_at: str,
    ) -> None:
        slugs = sorted({concept.slug for concept in concepts})
        self.sources[source_id] = SourceCompileState(
            checksum=checksum,
            compiler_version=COMPILER_VERSION,
            extracted_at=extracted_at,
            concept_slugs=slugs,
        )
        self.extracted_concepts[source_id] = [concept.to_dict() for concept in concepts]

    def to_dict(self) -> dict[str, Any]:
        return {
            "compiler_version": self.compiler_version,
            "sources": {key: value.to_dict() for key, value in self.sources.items()},
            "extracted_concepts": self.extracted_concepts,
            "frozen_slugs": self.frozen_slugs,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WikiCompilerState:
        data = _require_dict(data, "compiler state")
        compiler_version = _require_text(data, "compiler_version")
        sources_payload = _require_dict(data.get("sources"), "sources")
        extracted_concepts_payload = _require_dict_of_list_dicts(
            data.get("extracted_concepts"),
            "extracted_concepts",
        )
        frozen_slugs_payload = _require_dict_of_list_text(
            data.get("frozen_slugs"),
            "frozen_slugs",
        )
        return cls(
            compiler_version=compiler_version,
            sources={
                str(key): SourceCompileState.from_dict(
                    value,
                    fallback_compiler_version=compiler_version,
                )
                for key, value in sources_payload.items()
            },
            extracted_concepts=extracted_concepts_payload,
            frozen_slugs=frozen_slugs_payload,
        )


def state_path(runtime_wiki_dir: Path) -> Path:
    return runtime_wiki_dir / STATE_FILENAME


def load_compiler_state(runtime_wiki_dir: Path) -> WikiCompilerState:
    path = state_path(runtime_wiki_dir)
    if not path.exists():
        return WikiCompilerState()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid compiler state JSON: {exc}") from exc
    return WikiCompilerState.from_dict(payload)


def save_compiler_state(runtime_wiki_dir: Path, state: WikiCompilerState) -> None:
    runtime_wiki_dir.mkdir(parents=True, exist_ok=True)
    state_path(runtime_wiki_dir).write_text(
        json.dumps(state.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def reconcile_state_from_compiled_wiki(
    state: WikiCompilerState,
    *,
    sources: list[Any],
    wiki_dir: Path,
) -> dict[str, Any]:
    """Recover current source bindings from existing v4 concept pages.

    Runtime compiler state is generated cache data. Older schema/path migrations
    can leave it at a previous compiler version while the durable wiki pages are
    already current. In that case, rebuild enough source bindings from the v4
    concept page metadata so `wiki-status` and `wiki-update` do not reprocess
    every already-compiled source.
    """
    state_version_before = state.compiler_version
    source_by_id = {source.source_id: source for source in sources}
    current_source_ids = set(source_by_id)
    stale_source_ids = set(state.sources) - current_source_ids

    stale_sources_pruned = 0
    for source_id in sorted(stale_source_ids):
        state.sources.pop(source_id, None)
        state.extracted_concepts.pop(source_id, None)
        stale_sources_pruned += 1

    for source_id, source_state in list(state.sources.items()):
        if source_state.compiler_version == COMPILER_VERSION:
            continue
        state.sources.pop(source_id, None)
        state.extracted_concepts.pop(source_id, None)
        stale_sources_pruned += 1

    slugs_by_source_id: dict[str, set[str]] = {}
    generated_at_by_source_id: dict[str, str] = {}
    concepts_by_source_id: dict[str, list[dict[str, Any]]] = {}
    concepts_scanned = 0
    concepts_used = 0
    concepts_dir = Path(wiki_dir) / "concepts"
    if concepts_dir.is_dir():
        for path in sorted(concepts_dir.glob("*.md")):
            try:
                metadata, _body = parse_frontmatter(path)
            except (OSError, ValueError):
                continue
            if str(metadata.get("page_type") or "").strip() != "concept":
                continue
            if str(metadata.get("compiler_version") or "").strip() != COMPILER_VERSION:
                continue
            raw_sources = metadata.get("sources") or []
            if not isinstance(raw_sources, list):
                continue
            concepts_scanned += 1
            slug = path.stem
            title = str(metadata.get("title") or slug.replace("-", " ").title()).strip()
            summary = _concept_summary(metadata, _body, fallback=title)
            updated = str(metadata.get("updated") or "").strip() or None
            matched_source_ids: list[str] = []
            matched = False
            for raw_source_id in raw_sources:
                source_id = str(raw_source_id).strip()
                if source_id not in source_by_id:
                    continue
                slugs_by_source_id.setdefault(source_id, set()).add(slug)
                if updated:
                    generated_at_by_source_id[source_id] = updated
                matched_source_ids.append(source_id)
                matched = True
            if matched:
                evidence = [
                    ConceptEvidence(
                        source_id=source_id,
                        quote=summary,
                        note=f"Recovered from existing v4 wiki page {slug}.",
                    )
                    for source_id in matched_source_ids
                ]
                recovered_concept = ExtractedConcept(
                    title=title,
                    slug=slug,
                    summary=summary,
                    evidence=evidence,
                    confidence=1.0,
                    aliases=_metadata_text_list(metadata.get("aliases")),
                    related=_metadata_text_list(metadata.get("related")),
                ).to_dict()
                for source_id in matched_source_ids:
                    concepts_by_source_id.setdefault(source_id, []).append(recovered_concept)
                concepts_used += 1

    recovered_sources = 0
    recovered_concept_payloads = 0
    for source_id, slugs in sorted(slugs_by_source_id.items()):
        source = source_by_id[source_id]
        existing = state.sources.get(source_id)
        concept_slugs = sorted(slugs)
        generated_at = generated_at_by_source_id.get(source_id) or (
            existing.generated_at if existing and existing.generated_at else None
        )
        if (
            existing is not None
            and existing.compiler_version == COMPILER_VERSION
            and existing.checksum == source.checksum
            and existing.concept_slugs == concept_slugs
            and existing.generated_at
        ):
            continue
        state.sources[source_id] = SourceCompileState(
            checksum=source.checksum,
            compiler_version=COMPILER_VERSION,
            extracted_at=existing.extracted_at if existing else None,
            generated_at=generated_at,
            concept_slugs=concept_slugs,
        )
        if not state.extracted_concepts.get(source_id):
            state.extracted_concepts[source_id] = concepts_by_source_id.get(source_id, [])
            recovered_concept_payloads += len(state.extracted_concepts[source_id])
        recovered_sources += 1

    for source_id, concepts in sorted(concepts_by_source_id.items()):
        if state.extracted_concepts.get(source_id):
            continue
        state.extracted_concepts[source_id] = concepts
        recovered_concept_payloads += len(concepts)

    if state.compiler_version != COMPILER_VERSION:
        state.compiler_version = COMPILER_VERSION

    changed = bool(
        state_version_before != state.compiler_version
        or stale_sources_pruned
        or recovered_sources
        or recovered_concept_payloads
    )
    return {
        "changed": changed,
        "state_version_before": state_version_before,
        "state_version_after": state.compiler_version,
        "stale_sources_pruned": stale_sources_pruned,
        "concept_pages_scanned": concepts_scanned,
        "concept_pages_used": concepts_used,
        "recovered_sources": recovered_sources,
        "recovered_concept_payloads": recovered_concept_payloads,
    }


def _concept_summary(metadata: dict[str, Any], body: str, *, fallback: str) -> str:
    summary = str(metadata.get("summary") or "").strip()
    if summary:
        return summary
    for line in body.splitlines():
        text = line.strip()
        if not text or text.startswith("#") or text.startswith("- _at:"):
            continue
        return text[:500]
    return fallback


def _metadata_text_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def source_needs_extraction(state: WikiCompilerState, source_id: str, checksum: str) -> bool:
    current = state.sources.get(source_id)
    if current is not None and current.compiler_version != COMPILER_VERSION:
        return True
    if current is None and state.compiler_version != COMPILER_VERSION:
        return True
    return current is None or current.checksum != checksum


def source_is_already_bound(state: WikiCompilerState, source_id: str) -> bool:
    current = state.sources.get(source_id)
    if current is None:
        return False
    if state.compiler_version != COMPILER_VERSION or current.compiler_version != COMPILER_VERSION:
        return False
    return bool(current.generated_at and current.concept_slugs)
