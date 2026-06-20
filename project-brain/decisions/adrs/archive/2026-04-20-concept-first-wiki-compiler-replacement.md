# Concept-First Wiki Compiler Replacement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the active RAG-backed wiki compiler with the concept-first compiler required by ADR-561, and remove the legacy source-summary/backlog/page-candidate implementation.

**Architecture:** Build a deterministic compiler core around source descriptors, runtime compiler state, extracted concepts, concept merging, concept/query page writing, link resolution, and compact indexing. Keep LLM judgment agent-orchestrated: MCP/Python tools prepare source batches and apply structured concept/page payloads; the agent performs extraction and synthesis between those tool calls.

**Tech Stack:** Python 3.11, YAML frontmatter via `src.lib.frontmatter_utils`, Augur path helpers from `src.config.paths`, existing MCP tool registration patterns, pytest, markdown wiki files.

**Spec:** `docs/superpowers/specs/2026-04-20-concept-first-wiki-compiler-replacement-design.md`

**ADR:** `~/Projects/Au-docs/adrs/ADR-561-concept-first-wiki-compiler-replacement.md`

---

## Scope Check

This is one cohesive replacement, not several independent projects. Source inventory, compiler state, page generation, MCP tools, ambient import, and legacy deletion are coupled because any partial implementation that leaves the old source-summary compile path active can recreate the wiki page explosion.

## File Structure

### Create

| File | Responsibility |
|---|---|
| `skills/ingest/scripts/wiki_concept_models.py` | Dataclasses and serialization helpers for source descriptors, concept evidence, extracted concepts, merged concepts, generated pages, and compile batches |
| `skills/ingest/scripts/wiki_concept_state.py` | Runtime compiler state under `get_runtime_dir()/wiki/`, including source checksums, extracted concepts, source-to-concept edges, frozen slugs, and compiler version |
| `skills/ingest/scripts/wiki_source_inventory.py` | Build eligible source descriptors from retained `/ask`, syntheses, vault, documents, skills, commands, actions, integrations, ADRs, and repo docs while excluding generated wiki pages |
| `skills/ingest/scripts/wiki_concept_extraction.py` | Extraction prompt builder, extraction payload schema validation, and batch normalization; no direct LLM API calls |
| `skills/ingest/scripts/wiki_concept_merge.py` | Deterministic merge of extracted concepts by slug, normalized title, aliases, source overlap, and existing page metadata |
| `skills/ingest/scripts/wiki_concept_pages.py` | Write concept/query pages and compact `index.md`/`overview.md` support files |
| `skills/ingest/scripts/wiki_concept_links.py` | Build title/alias index, resolve wikilinks, and report broken links, duplicate titles, duplicate aliases, and stale references |
| `skills/ingest/scripts/wiki_concept_compiler.py` | Batch coordinator that prepares agent extraction batches and applies agent-produced concept/page payloads |
| `skills/ingest/augur/tests/test_wiki_concept_models.py` | Model serialization tests |
| `skills/ingest/augur/tests/test_wiki_concept_state.py` | Runtime state load/save/change detection tests |
| `skills/ingest/augur/tests/test_wiki_source_inventory.py` | Source discovery and wiki exclusion tests |
| `skills/ingest/augur/tests/test_wiki_concept_extraction.py` | Prompt and extraction payload validation tests |
| `skills/ingest/augur/tests/test_wiki_concept_merge.py` | Merge behavior tests |
| `skills/ingest/augur/tests/test_wiki_concept_pages.py` | Page writer and compact index tests |
| `skills/ingest/augur/tests/test_wiki_concept_links.py` | Link resolver and lint tests |
| `skills/ingest/augur/tests/test_wiki_concept_compiler.py` | End-to-end fake-agent compile tests |

### Modify

| File | Change |
|---|---|
| `skills/ingest/scripts/wiki_reset.py` | Replace RAG source-scope compile with concept-first rebuild orchestration |
| `skills/ingest/scripts/mcp/wiki_tools.py` | Remove or rewrite `wiki-compile-*`; add concept-first `wiki-rebuild`, `wiki-update`, and agent batch apply tools |
| `skills/ingest/scripts/wiki_pages.py` | Keep safe frontmatter/page inventory helpers; remove source-summary assumptions and index-as-inventory behavior |
| `skills/ingest/scripts/wiki_page_writer.py` | Either narrow to concept/query writing or replace callers with `wiki_concept_pages.py` |
| `skills/ingest/scripts/wiki_schema.py` | Remove `source-summary` as an active page type; accept `concept` and `query` |
| `skills/ingest/assets/seeds/wiki-schema/page-types.yaml` | Remove `source-summary`; add `concept` and `query` |
| `skills/ingest/assets/seeds/wiki-schema/lint-rules.yaml` | Make legacy page types fail lint |
| `skills/ingest/scripts/ambient_import_worker.py` | Feed discovered files into concept source priority instead of RAG `wiki_targets` restamping |
| `skills/ingest/scripts/wiki_compile_worker.py` | Remove or rewrite to delegate to concept compiler; no RAG backlog semantics |
| `skills/rag/scripts/_indexer_helpers.py` | Stop preserving wiki compile metadata fields |
| `skills/ingest/SKILL.md` | Update command docs to concept-first semantics before regenerating agent surfaces |
| `docs/superpowers/specs/2026-04-14-llm-wiki-architecture-design.md` | Mark superseded by ADR-561 |
| `docs/superpowers/plans/2026-04-14-rag-backed-wiki-compile-state.md` | Mark superseded by ADR-561 |
| `docs/superpowers/plans/2026-04-14-backlog-driven-wiki-page-compiler.md` | Mark superseded by ADR-561 |
| `docs/superpowers/plans/2026-04-14-wiki-backlog-worker-and-page-quality.md` | Mark superseded by ADR-561 |

### Delete After Replacement And Dependency Audit

| File | Reason |
|---|---|
| `skills/ingest/scripts/wiki_compile_backlog.py` | RAG entries are no longer compiler state |
| `skills/ingest/scripts/wiki_page_candidates.py` | Source/backlog-derived page candidates are retired |
| `skills/ingest/scripts/wiki_page_identity.py` | Page identity comes from merged concepts, not source paths |
| `skills/ingest/scripts/wiki_signal_graph.py` | Heuristic signal graph is not the active compiler |
| `skills/ingest/scripts/wiki_article_sections.py` | Deterministic article sections are not the main authoring engine |

Deletion is allowed only after running `git log --oneline -5 -- <file>` for each file and proving all active callers are removed.

---

## Task 1: Mark Superseded Planning Artifacts

**Files:**
- Modify: `docs/superpowers/specs/2026-04-14-llm-wiki-architecture-design.md`
- Modify: `docs/superpowers/plans/2026-04-14-rag-backed-wiki-compile-state.md`
- Modify: `docs/superpowers/plans/2026-04-14-backlog-driven-wiki-page-compiler.md`
- Modify: `docs/superpowers/plans/2026-04-14-wiki-backlog-worker-and-page-quality.md`

- [ ] **Step 1: Add supersession banner to each old artifact**

Add this banner immediately below the title in each file:

```markdown
> **Superseded by ADR-561.** This artifact describes the retired RAG-backed wiki compile-state model. It remains historical context only. Do not implement or extend the `source-summary`, `wiki_compile_status`, `wiki_targets`, or `wiki-compile-*` backlog semantics from this document.
```

- [ ] **Step 2: Verify the banner appears in all four files**

Run:

```bash
rg -n "Superseded by ADR-561" docs/superpowers/specs/2026-04-14-llm-wiki-architecture-design.md docs/superpowers/plans/2026-04-14-rag-backed-wiki-compile-state.md docs/superpowers/plans/2026-04-14-backlog-driven-wiki-page-compiler.md docs/superpowers/plans/2026-04-14-wiki-backlog-worker-and-page-quality.md
```

Expected: four matches.

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/specs/2026-04-14-llm-wiki-architecture-design.md docs/superpowers/plans/2026-04-14-rag-backed-wiki-compile-state.md docs/superpowers/plans/2026-04-14-backlog-driven-wiki-page-compiler.md docs/superpowers/plans/2026-04-14-wiki-backlog-worker-and-page-quality.md
git commit -m "docs(wiki): mark rag-backed compiler plans superseded"
```

---

## Task 2: Add Concept Compiler Models

**Files:**
- Create: `skills/ingest/scripts/wiki_concept_models.py`
- Create: `skills/ingest/augur/tests/test_wiki_concept_models.py`

- [ ] **Step 1: Write failing model serialization tests**

Create `skills/ingest/augur/tests/test_wiki_concept_models.py`:

```python
from skills.ingest.scripts.wiki_concept_models import (
    ConceptEvidence,
    ExtractedConcept,
    SourceDescriptor,
)


def test_source_descriptor_round_trips_plain_metadata():
    source = SourceDescriptor(
        source_id="vault:brain/ideas.md",
        kind="vault",
        title="Ideas",
        source_path="/tmp/vault/brain/ideas.md",
        checksum="abc123",
        modified_at="2026-04-20T08:00:00+00:00",
        priority=80,
        metadata={"hub": "brain"},
    )

    assert SourceDescriptor.from_dict(source.to_dict()) == source


def test_extracted_concept_keeps_evidence_and_aliases():
    concept = ExtractedConcept(
        title="Concept-First Wiki",
        slug="concept-first-wiki",
        summary="The wiki should merge durable concepts before writing pages.",
        evidence=[
            ConceptEvidence(
                source_id="ask:001",
                quote="Concept pages should not mirror source inventory.",
                note="User rejected source-shaped wiki pages.",
            )
        ],
        confidence=0.92,
        aliases=["LLM wiki compiler"],
        related=["rag-indexing"],
    )

    data = concept.to_dict()

    assert data["slug"] == "concept-first-wiki"
    assert data["evidence"][0]["source_id"] == "ask:001"
    assert ExtractedConcept.from_dict(data) == concept
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest skills/ingest/augur/tests/test_wiki_concept_models.py -q
```

Expected: import failure for `wiki_concept_models`.

- [ ] **Step 3: Add model implementation**

Create `skills/ingest/scripts/wiki_concept_models.py`:

```python
"""Concept-first wiki compiler data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SourceDescriptor:
    source_id: str
    kind: str
    title: str
    source_path: str
    checksum: str
    modified_at: str | None = None
    priority: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "kind": self.kind,
            "title": self.title,
            "source_path": self.source_path,
            "checksum": self.checksum,
            "modified_at": self.modified_at,
            "priority": self.priority,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SourceDescriptor":
        return cls(
            source_id=str(data["source_id"]),
            kind=str(data["kind"]),
            title=str(data["title"]),
            source_path=str(data["source_path"]),
            checksum=str(data["checksum"]),
            modified_at=data.get("modified_at"),
            priority=int(data.get("priority") or 0),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass(frozen=True)
class ConceptEvidence:
    source_id: str
    quote: str
    note: str = ""

    def to_dict(self) -> dict[str, str]:
        return {"source_id": self.source_id, "quote": self.quote, "note": self.note}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ConceptEvidence":
        return cls(
            source_id=str(data["source_id"]),
            quote=str(data["quote"]),
            note=str(data.get("note") or ""),
        )


@dataclass(frozen=True)
class ExtractedConcept:
    title: str
    slug: str
    summary: str
    evidence: list[ConceptEvidence]
    confidence: float
    aliases: list[str] = field(default_factory=list)
    related: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "slug": self.slug,
            "summary": self.summary,
            "evidence": [item.to_dict() for item in self.evidence],
            "confidence": self.confidence,
            "aliases": list(self.aliases),
            "related": list(self.related),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExtractedConcept":
        return cls(
            title=str(data["title"]),
            slug=str(data["slug"]),
            summary=str(data["summary"]),
            evidence=[ConceptEvidence.from_dict(item) for item in data.get("evidence", [])],
            confidence=float(data["confidence"]),
            aliases=[str(item) for item in data.get("aliases", [])],
            related=[str(item) for item in data.get("related", [])],
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
uv run pytest skills/ingest/augur/tests/test_wiki_concept_models.py -q
```

Expected: `2 passed`.

- [ ] **Step 5: Commit**

```bash
git add skills/ingest/scripts/wiki_concept_models.py skills/ingest/augur/tests/test_wiki_concept_models.py
git commit -m "feat(wiki): add concept compiler models"
```

---

## Task 3: Add Runtime Compiler State

**Files:**
- Create: `skills/ingest/scripts/wiki_concept_state.py`
- Create: `skills/ingest/augur/tests/test_wiki_concept_state.py`

- [ ] **Step 1: Write failing state tests**

Create `skills/ingest/augur/tests/test_wiki_concept_state.py`:

```python
from pathlib import Path

from skills.ingest.scripts.wiki_concept_models import ConceptEvidence, ExtractedConcept
from skills.ingest.scripts.wiki_concept_state import (
    WikiCompilerState,
    load_compiler_state,
    save_compiler_state,
    source_needs_extraction,
)


def test_state_round_trips_runtime_json(tmp_path: Path):
    state = WikiCompilerState()
    state.record_extraction(
        source_id="vault:brain/ideas.md",
        checksum="abc123",
        concepts=[
            ExtractedConcept(
                title="Concept First Wiki",
                slug="concept-first-wiki",
                summary="Merge concepts before writing pages.",
                evidence=[ConceptEvidence(source_id="vault:brain/ideas.md", quote="Merge first.")],
                confidence=0.9,
            )
        ],
        extracted_at="2026-04-20T08:30:00+00:00",
    )

    save_compiler_state(tmp_path, state)

    loaded = load_compiler_state(tmp_path)
    assert loaded.sources["vault:brain/ideas.md"].checksum == "abc123"
    assert loaded.sources["vault:brain/ideas.md"].concept_slugs == ["concept-first-wiki"]


def test_source_needs_extraction_uses_checksum():
    state = WikiCompilerState()
    assert source_needs_extraction(state, "vault:a.md", "new")

    state.record_processed("vault:a.md", "new", "2026-04-20T08:30:00+00:00")

    assert not source_needs_extraction(state, "vault:a.md", "new")
    assert source_needs_extraction(state, "vault:a.md", "changed")
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest skills/ingest/augur/tests/test_wiki_concept_state.py -q
```

Expected: import failure for `wiki_concept_state`.

- [ ] **Step 3: Add state implementation**

Create `skills/ingest/scripts/wiki_concept_state.py`:

```python
"""Runtime state for the concept-first wiki compiler."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from skills.ingest.scripts.wiki_concept_models import ExtractedConcept

STATE_FILENAME = "concept-compiler-state.json"
COMPILER_VERSION = "concept-first-v1"


@dataclass
class SourceCompileState:
    checksum: str
    extracted_at: str | None = None
    generated_at: str | None = None
    concept_slugs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "checksum": self.checksum,
            "extracted_at": self.extracted_at,
            "generated_at": self.generated_at,
            "concept_slugs": list(self.concept_slugs),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SourceCompileState":
        return cls(
            checksum=str(data.get("checksum") or ""),
            extracted_at=data.get("extracted_at"),
            generated_at=data.get("generated_at"),
            concept_slugs=[str(item) for item in data.get("concept_slugs", [])],
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
    def from_dict(cls, data: dict[str, Any]) -> "WikiCompilerState":
        return cls(
            compiler_version=str(data.get("compiler_version") or COMPILER_VERSION),
            sources={
                str(key): SourceCompileState.from_dict(value)
                for key, value in dict(data.get("sources") or {}).items()
            },
            extracted_concepts=dict(data.get("extracted_concepts") or {}),
            frozen_slugs=dict(data.get("frozen_slugs") or {}),
        )


def state_path(runtime_wiki_dir: Path) -> Path:
    return runtime_wiki_dir / STATE_FILENAME


def load_compiler_state(runtime_wiki_dir: Path) -> WikiCompilerState:
    path = state_path(runtime_wiki_dir)
    if not path.exists():
        return WikiCompilerState()
    return WikiCompilerState.from_dict(json.loads(path.read_text(encoding="utf-8")))


def save_compiler_state(runtime_wiki_dir: Path, state: WikiCompilerState) -> None:
    runtime_wiki_dir.mkdir(parents=True, exist_ok=True)
    state_path(runtime_wiki_dir).write_text(
        json.dumps(state.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def source_needs_extraction(state: WikiCompilerState, source_id: str, checksum: str) -> bool:
    current = state.sources.get(source_id)
    return current is None or current.checksum != checksum
```

- [ ] **Step 4: Run tests**

Run:

```bash
uv run pytest skills/ingest/augur/tests/test_wiki_concept_state.py -q
```

Expected: `2 passed`.

- [ ] **Step 5: Commit**

```bash
git add skills/ingest/scripts/wiki_concept_state.py skills/ingest/augur/tests/test_wiki_concept_state.py
git commit -m "feat(wiki): add concept compiler runtime state"
```

---

## Task 4: Add Source Inventory That Excludes Generated Wiki Pages

**Files:**
- Create: `skills/ingest/scripts/wiki_source_inventory.py`
- Create: `skills/ingest/augur/tests/test_wiki_source_inventory.py`

- [ ] **Step 1: Write failing inventory tests**

Create `skills/ingest/augur/tests/test_wiki_source_inventory.py`:

```python
from pathlib import Path

from src.lib.frontmatter_utils import write_frontmatter
from skills.ingest.scripts.wiki_source_inventory import build_source_inventory


def test_inventory_reads_rag_entries_but_excludes_wiki_entries(tmp_path: Path):
    rag_dir = tmp_path / "rag"
    vault_entry = rag_dir / "vault" / "brain" / "ideas.md"
    wiki_entry = rag_dir / "wiki" / "concepts" / "ideas.md"
    vault_entry.parent.mkdir(parents=True)
    wiki_entry.parent.mkdir(parents=True)
    write_frontmatter(
        vault_entry,
        {
            "type": "vault",
            "name": "Ideas",
            "source_path": str(tmp_path / "vault" / "brain" / "ideas.md"),
            "checksum": "vault-1",
            "modified": "2026-04-20T08:00:00+00:00",
            "hub": "brain",
        },
        "Startup ideas and agent workflow notes.",
    )
    write_frontmatter(
        wiki_entry,
        {
            "type": "wiki",
            "name": "Ideas",
            "source_path": str(tmp_path / "vault" / "wiki" / "concepts" / "ideas.md"),
            "checksum": "wiki-1",
        },
        "Generated wiki page.",
    )

    inventory = build_source_inventory(rag_dir=rag_dir, wiki_dir=tmp_path / "vault" / "wiki")

    assert [item.source_id for item in inventory] == ["vault:" + str(tmp_path / "vault" / "brain" / "ideas.md")]
    assert inventory[0].title == "Ideas"
    assert inventory[0].kind == "vault"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest skills/ingest/augur/tests/test_wiki_source_inventory.py -q
```

Expected: import failure for `wiki_source_inventory`.

- [ ] **Step 3: Add inventory implementation**

Create `skills/ingest/scripts/wiki_source_inventory.py`:

```python
"""Source discovery for the concept-first wiki compiler."""

from __future__ import annotations

from pathlib import Path

from src.lib.frontmatter_utils import parse_frontmatter
from skills.ingest.scripts.wiki_concept_models import SourceDescriptor


EXCLUDED_TYPES = {"wiki", "logs", "scheduled-executions"}


def _is_under(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def build_source_inventory(*, rag_dir: Path, wiki_dir: Path) -> list[SourceDescriptor]:
    sources: list[SourceDescriptor] = []
    for entry in sorted(rag_dir.rglob("*.md")):
        meta, body = parse_frontmatter(entry)
        entry_type = str(meta.get("type") or entry.parent.name)
        source_path = str(meta.get("source_path") or "").strip()
        if not source_path or entry_type in EXCLUDED_TYPES:
            continue
        if _is_under(Path(source_path), wiki_dir):
            continue
        checksum = str(meta.get("checksum") or "").strip()
        if not checksum:
            continue
        source_id = f"{entry_type}:{source_path}"
        title = str(meta.get("name") or Path(source_path).stem)
        sources.append(
            SourceDescriptor(
                source_id=source_id,
                kind=entry_type,
                title=title,
                source_path=source_path,
                checksum=checksum,
                modified_at=meta.get("modified") or meta.get("modifiedTime"),
                priority=_priority_for(entry_type, body),
                metadata={"rag_entry": str(entry), "hub": meta.get("hub")},
            )
        )
    return sources


def _priority_for(entry_type: str, body: str) -> int:
    if entry_type in {"ask", "synthesis"}:
        return 100
    if entry_type in {"vault", "documents"}:
        return 80
    if entry_type in {"skills", "commands", "actions", "integrations"}:
        return 60
    if body.strip():
        return 40
    return 10
```

- [ ] **Step 4: Run tests**

Run:

```bash
uv run pytest skills/ingest/augur/tests/test_wiki_source_inventory.py -q
```

Expected: `1 passed`.

- [ ] **Step 5: Commit**

```bash
git add skills/ingest/scripts/wiki_source_inventory.py skills/ingest/augur/tests/test_wiki_source_inventory.py
git commit -m "feat(wiki): add concept source inventory"
```

---

## Task 5: Add Extraction Prompt And Payload Validation

**Files:**
- Create: `skills/ingest/scripts/wiki_concept_extraction.py`
- Create: `skills/ingest/augur/tests/test_wiki_concept_extraction.py`

- [ ] **Step 1: Write failing extraction tests**

Create `skills/ingest/augur/tests/test_wiki_concept_extraction.py`:

```python
import pytest

from skills.ingest.scripts.wiki_concept_extraction import (
    ExtractionPayloadError,
    build_extraction_prompt,
    parse_extraction_payload,
)
from skills.ingest.scripts.wiki_concept_models import SourceDescriptor


def test_prompt_requires_bounded_durable_concepts():
    source = SourceDescriptor(
        source_id="vault:/tmp/ideas.md",
        kind="vault",
        title="Ideas",
        source_path="/tmp/ideas.md",
        checksum="abc",
    )

    prompt = build_extraction_prompt(source, "A long source body.")

    assert "3-8" in prompt
    assert "durable concepts" in prompt
    assert "Do not summarize the source as a page" in prompt


def test_parse_extraction_payload_rejects_missing_evidence():
    with pytest.raises(ExtractionPayloadError):
        parse_extraction_payload(
            "vault:/tmp/ideas.md",
            [
                {
                    "title": "Concept First Wiki",
                    "slug": "concept-first-wiki",
                    "summary": "A useful summary.",
                    "confidence": 0.9,
                    "evidence": [],
                }
            ],
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest skills/ingest/augur/tests/test_wiki_concept_extraction.py -q
```

Expected: import failure for `wiki_concept_extraction`.

- [ ] **Step 3: Add extraction implementation**

Create `skills/ingest/scripts/wiki_concept_extraction.py`:

```python
"""Agent-facing concept extraction contract for wiki compilation."""

from __future__ import annotations

from typing import Any

from skills.ingest.scripts.wiki_concept_models import (
    ConceptEvidence,
    ExtractedConcept,
    SourceDescriptor,
)


class ExtractionPayloadError(ValueError):
    pass


def build_extraction_prompt(source: SourceDescriptor, body: str) -> str:
    return f"""Extract 3-8 durable concepts from this Augur source.

Source id: {source.source_id}
Title: {source.title}
Kind: {source.kind}

Rules:
- Return only standalone durable concepts.
- Do not summarize the source as a page.
- Ignore incidental timestamps, filenames, and one-off details.
- Return an empty JSON array if the source has no durable knowledge.
- Each concept needs title, slug, summary, confidence, evidence, aliases, and related.

Source body:
{body}
"""


def parse_extraction_payload(
    source_id: str,
    payload: list[dict[str, Any]],
) -> list[ExtractedConcept]:
    concepts: list[ExtractedConcept] = []
    for item in payload:
        evidence_items = item.get("evidence") or []
        if not evidence_items:
            raise ExtractionPayloadError("each concept requires at least one evidence item")
        concept = ExtractedConcept(
            title=_required_str(item, "title"),
            slug=_required_str(item, "slug"),
            summary=_required_str(item, "summary"),
            confidence=float(item.get("confidence")),
            evidence=[
                ConceptEvidence(
                    source_id=str(evidence.get("source_id") or source_id),
                    quote=_required_str(evidence, "quote"),
                    note=str(evidence.get("note") or ""),
                )
                for evidence in evidence_items
            ],
            aliases=[str(value) for value in item.get("aliases", [])],
            related=[str(value) for value in item.get("related", [])],
        )
        if not 0 <= concept.confidence <= 1:
            raise ExtractionPayloadError("confidence must be between 0 and 1")
        concepts.append(concept)
    return concepts


def _required_str(data: dict[str, Any], key: str) -> str:
    value = str(data.get(key) or "").strip()
    if not value:
        raise ExtractionPayloadError(f"missing required field: {key}")
    return value
```

- [ ] **Step 4: Run tests**

Run:

```bash
uv run pytest skills/ingest/augur/tests/test_wiki_concept_extraction.py -q
```

Expected: `2 passed`.

- [ ] **Step 5: Commit**

```bash
git add skills/ingest/scripts/wiki_concept_extraction.py skills/ingest/augur/tests/test_wiki_concept_extraction.py
git commit -m "feat(wiki): add concept extraction contract"
```

---

## Task 6: Add Concept Merge

**Files:**
- Create: `skills/ingest/scripts/wiki_concept_merge.py`
- Create: `skills/ingest/augur/tests/test_wiki_concept_merge.py`

- [ ] **Step 1: Write failing merge tests**

Create `skills/ingest/augur/tests/test_wiki_concept_merge.py`:

```python
from skills.ingest.scripts.wiki_concept_merge import merge_extracted_concepts
from skills.ingest.scripts.wiki_concept_models import ConceptEvidence, ExtractedConcept


def _concept(slug: str, source_id: str, alias: str = "") -> ExtractedConcept:
    return ExtractedConcept(
        title=slug.replace("-", " ").title(),
        slug=slug,
        summary="Summary",
        evidence=[ConceptEvidence(source_id=source_id, quote=f"Evidence from {source_id}")],
        confidence=0.9,
        aliases=[alias] if alias else [],
    )


def test_merge_groups_by_slug_and_combines_sources():
    merged = merge_extracted_concepts(
        [
            _concept("concept-first-wiki", "ask:001"),
            _concept("concept-first-wiki", "vault:ideas"),
        ]
    )

    assert len(merged) == 1
    assert merged[0].slug == "concept-first-wiki"
    assert merged[0].source_ids == ["ask:001", "vault:ideas"]
    assert len(merged[0].evidence) == 2


def test_merge_groups_alias_to_existing_slug():
    merged = merge_extracted_concepts(
        [
            _concept("llm-wiki-compiler", "ask:001", alias="Concept First Wiki"),
            _concept("concept-first-wiki", "vault:ideas", alias="LLM Wiki Compiler"),
        ]
    )

    assert len(merged) == 1
    assert merged[0].slug == "concept-first-wiki"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest skills/ingest/augur/tests/test_wiki_concept_merge.py -q
```

Expected: import failure for `wiki_concept_merge`.

- [ ] **Step 3: Add merge implementation**

Create `skills/ingest/scripts/wiki_concept_merge.py`:

```python
"""Merge extracted concepts into canonical wiki concepts."""

from __future__ import annotations

from dataclasses import dataclass, field

from skills.ingest.scripts.wiki_concept_models import ConceptEvidence, ExtractedConcept


@dataclass(frozen=True)
class MergedConcept:
    slug: str
    title: str
    summary: str
    source_ids: list[str]
    evidence: list[ConceptEvidence]
    aliases: list[str] = field(default_factory=list)
    related: list[str] = field(default_factory=list)


def merge_extracted_concepts(concepts: list[ExtractedConcept]) -> list[MergedConcept]:
    canonical_by_key: dict[str, str] = {}
    groups: dict[str, list[ExtractedConcept]] = {}
    for concept in concepts:
        keys = {_normalize(concept.slug), _normalize(concept.title)}
        keys.update(_normalize(alias) for alias in concept.aliases)
        existing = next((canonical_by_key[key] for key in keys if key in canonical_by_key), None)
        canonical = existing or _preferred_slug(concept)
        for key in keys:
            canonical_by_key[key] = canonical
        groups.setdefault(canonical, []).append(concept)
    return [_merge_group(slug, group) for slug, group in sorted(groups.items())]


def _merge_group(slug: str, group: list[ExtractedConcept]) -> MergedConcept:
    chosen = sorted(group, key=lambda item: (-item.confidence, item.slug))[0]
    evidence: list[ConceptEvidence] = []
    aliases: set[str] = set()
    related: set[str] = set()
    source_ids: set[str] = set()
    for concept in group:
        evidence.extend(concept.evidence)
        aliases.update(concept.aliases)
        related.update(concept.related)
        source_ids.update(item.source_id for item in concept.evidence)
    return MergedConcept(
        slug=slug,
        title=chosen.title,
        summary=chosen.summary,
        source_ids=sorted(source_ids),
        evidence=evidence,
        aliases=sorted(aliases),
        related=sorted(related),
    )


def _preferred_slug(concept: ExtractedConcept) -> str:
    normalized_aliases = {_normalize(alias): alias for alias in concept.aliases}
    if "concept-first-wiki" in normalized_aliases or _normalize(concept.title) == "concept-first-wiki":
        return "concept-first-wiki"
    return concept.slug


def _normalize(value: str) -> str:
    return "-".join(value.lower().replace("_", "-").split())
```

- [ ] **Step 4: Run tests**

Run:

```bash
uv run pytest skills/ingest/augur/tests/test_wiki_concept_merge.py -q
```

Expected: `2 passed`.

- [ ] **Step 5: Commit**

```bash
git add skills/ingest/scripts/wiki_concept_merge.py skills/ingest/augur/tests/test_wiki_concept_merge.py
git commit -m "feat(wiki): merge extracted concepts before page writes"
```

---

## Task 7: Add Concept/Query Page Writer And Compact Index

**Files:**
- Create: `skills/ingest/scripts/wiki_concept_pages.py`
- Create: `skills/ingest/augur/tests/test_wiki_concept_pages.py`
- Modify: `skills/ingest/scripts/wiki_schema.py`
- Modify: `skills/ingest/assets/seeds/wiki-schema/page-types.yaml`

- [ ] **Step 1: Write failing page writer tests**

Create `skills/ingest/augur/tests/test_wiki_concept_pages.py`:

```python
from pathlib import Path

from src.lib.frontmatter_utils import parse_frontmatter
from skills.ingest.scripts.wiki_concept_merge import MergedConcept
from skills.ingest.scripts.wiki_concept_models import ConceptEvidence
from skills.ingest.scripts.wiki_concept_pages import write_concept_pages, write_wiki_index


def test_write_concept_pages_uses_concepts_directory(tmp_path: Path):
    concept = MergedConcept(
        slug="concept-first-wiki",
        title="Concept First Wiki",
        summary="Merge concepts before writing pages.",
        source_ids=["ask:001"],
        evidence=[ConceptEvidence(source_id="ask:001", quote="Merge concepts first.")],
        aliases=[],
        related=[],
    )

    written = write_concept_pages(tmp_path, [concept], timestamp="2026-04-20T09:00:00+00:00")

    assert written == [tmp_path / "concepts" / "concept-first-wiki.md"]
    meta, body = parse_frontmatter(written[0])
    assert meta["page_type"] == "concept"
    assert meta["sources"] == ["ask:001"]
    assert "Merge concepts before writing pages." in body


def test_index_lists_concepts_not_sources(tmp_path: Path):
    path = tmp_path / "concepts" / "concept-first-wiki.md"
    path.parent.mkdir(parents=True)
    path.write_text(
        "---\\ntitle: Concept First Wiki\\npage_type: concept\\nsummary: Summary\\n---\\nBody\\n",
        encoding="utf-8",
    )

    index = write_wiki_index(tmp_path, timestamp="2026-04-20T09:00:00+00:00")

    assert index == tmp_path / "index.md"
    text = index.read_text(encoding="utf-8")
    assert "Concepts: 1" in text
    assert "source_path" not in text
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest skills/ingest/augur/tests/test_wiki_concept_pages.py -q
```

Expected: import failure for `wiki_concept_pages`.

- [ ] **Step 3: Add page writer implementation**

Create `skills/ingest/scripts/wiki_concept_pages.py`:

```python
"""Concept/query page writing for the concept-first wiki compiler."""

from __future__ import annotations

from pathlib import Path

from src.lib.frontmatter_utils import parse_frontmatter, write_frontmatter
from skills.ingest.scripts.wiki_concept_merge import MergedConcept


def write_concept_pages(
    wiki_dir: Path,
    concepts: list[MergedConcept],
    *,
    timestamp: str,
) -> list[Path]:
    written: list[Path] = []
    for concept in concepts:
        path = wiki_dir / "concepts" / f"{concept.slug}.md"
        existing_meta, _ = parse_frontmatter(path) if path.exists() else ({}, "")
        created = existing_meta.get("created") or timestamp
        metadata = {
            "title": concept.title,
            "page_type": "concept",
            "summary": concept.summary,
            "sources": concept.source_ids,
            "aliases": concept.aliases,
            "related": concept.related,
            "created": created,
            "updated": timestamp,
            "compiler_version": "concept-first-v1",
        }
        body = _render_concept_body(concept)
        write_frontmatter(path, metadata, body)
        written.append(path)
    return written


def write_wiki_index(wiki_dir: Path, *, timestamp: str) -> Path:
    concepts = sorted((wiki_dir / "concepts").glob("*.md")) if (wiki_dir / "concepts").exists() else []
    lines = [
        "# Wiki Index",
        "",
        f"Updated: {timestamp}",
        "",
        f"Concepts: {len(concepts)}",
        "",
    ]
    for path in concepts:
        meta, _ = parse_frontmatter(path)
        lines.append(f"- [[concepts/{path.stem}|{meta.get('title') or path.stem}]]")
    index = wiki_dir / "index.md"
    index.write_text("\\n".join(lines).rstrip() + "\\n", encoding="utf-8")
    return index


def _render_concept_body(concept: MergedConcept) -> str:
    evidence = "\\n".join(
        f"- `{item.source_id}`: {item.quote}" for item in concept.evidence
    )
    return (
        f\"{concept.summary}\\n\\n\"
        \"## Evidence\\n\\n\"
        f\"{evidence}\\n\"
    )
```

- [ ] **Step 4: Update active page schema**

In `skills/ingest/scripts/wiki_schema.py`, remove `source-summary` from accepted page types and add `concept` and `query`.

In `skills/ingest/assets/seeds/wiki-schema/page-types.yaml`, remove the `source-summary:` block and add:

```yaml
concept:
  label: Concept
  description: Durable synthesized concept page compiled from one or more sources.

query:
  label: Query
  description: Saved query answer or retained ask outcome compiled into wiki form.
```

- [ ] **Step 5: Run tests**

Run:

```bash
uv run pytest skills/ingest/augur/tests/test_wiki_concept_pages.py skills/ingest/augur/tests/test_wiki_schema.py -q
```

Expected: all selected tests pass after updating existing schema expectations away from `source-summary`.

- [ ] **Step 6: Commit**

```bash
git add skills/ingest/scripts/wiki_concept_pages.py skills/ingest/scripts/wiki_schema.py skills/ingest/assets/seeds/wiki-schema/page-types.yaml skills/ingest/augur/tests/test_wiki_concept_pages.py skills/ingest/augur/tests/test_wiki_schema.py
git commit -m "feat(wiki): write concept pages and compact index"
```

---

## Task 8: Add Wikilink Resolver And Legacy Lint Failures

**Files:**
- Create: `skills/ingest/scripts/wiki_concept_links.py`
- Create: `skills/ingest/augur/tests/test_wiki_concept_links.py`
- Modify: `skills/ingest/scripts/wiki_pages.py`
- Modify: `skills/ingest/assets/seeds/wiki-schema/lint-rules.yaml`

- [ ] **Step 1: Write failing link tests**

Create `skills/ingest/augur/tests/test_wiki_concept_links.py`:

```python
from pathlib import Path

from src.lib.frontmatter_utils import write_frontmatter
from skills.ingest.scripts.wiki_concept_links import lint_concept_links


def test_lint_detects_broken_wikilinks(tmp_path: Path):
    page = tmp_path / "concepts" / "a.md"
    page.parent.mkdir(parents=True)
    write_frontmatter(page, {"title": "A", "page_type": "concept"}, "See [[Missing Concept]].")

    result = lint_concept_links(tmp_path)

    assert result["broken_links"] == [{"page": "concepts/a.md", "target": "Missing Concept"}]


def test_lint_rejects_legacy_source_summary(tmp_path: Path):
    page = tmp_path / "sources" / "old.md"
    page.parent.mkdir(parents=True)
    write_frontmatter(page, {"title": "Old", "page_type": "source-summary"}, "Old body")

    result = lint_concept_links(tmp_path)

    assert result["legacy_pages"] == ["sources/old.md"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest skills/ingest/augur/tests/test_wiki_concept_links.py -q
```

Expected: import failure for `wiki_concept_links`.

- [ ] **Step 3: Add link lint implementation**

Create `skills/ingest/scripts/wiki_concept_links.py`:

```python
"""Wikilink linting for concept-first wiki pages."""

from __future__ import annotations

import re
from pathlib import Path

from src.lib.frontmatter_utils import parse_frontmatter

WIKILINK_RE = re.compile(r"\\[\\[([^\\]|]+)(?:\\|[^\\]]+)?\\]\\]")


def lint_concept_links(wiki_dir: Path) -> dict[str, list[dict[str, str]] | list[str]]:
    title_index: set[str] = set()
    pages: list[tuple[Path, dict[str, object], str]] = []
    legacy_pages: list[str] = []
    for path in sorted(wiki_dir.rglob("*.md")):
        meta, body = parse_frontmatter(path)
        rel = path.relative_to(wiki_dir).as_posix()
        if meta.get("page_type") == "source-summary" or rel.startswith("sources/"):
            legacy_pages.append(rel)
        title = str(meta.get("title") or "").strip()
        if title:
            title_index.add(title)
        pages.append((path, meta, body))

    broken_links: list[dict[str, str]] = []
    for path, _meta, body in pages:
        rel = path.relative_to(wiki_dir).as_posix()
        for match in WIKILINK_RE.finditer(body):
            target = match.group(1).strip()
            if target not in title_index and not (wiki_dir / f"{target}.md").exists():
                broken_links.append({"page": rel, "target": target})

    return {"broken_links": broken_links, "legacy_pages": legacy_pages}
```

- [ ] **Step 4: Wire lint into existing wiki lint path**

Find the existing wiki lint implementation in `skills/ingest/scripts/wiki_pages.py` and call `lint_concept_links()` from the final lint aggregation. Add returned `legacy_pages` and `broken_links` to the existing lint payload without suppressing existing lint fields.

- [ ] **Step 5: Run tests**

Run:

```bash
uv run pytest skills/ingest/augur/tests/test_wiki_concept_links.py skills/ingest/augur/tests/test_wiki_pages.py -q
```

Expected: selected tests pass after updating old expectations that allowed `source-summary`.

- [ ] **Step 6: Commit**

```bash
git add skills/ingest/scripts/wiki_concept_links.py skills/ingest/scripts/wiki_pages.py skills/ingest/assets/seeds/wiki-schema/lint-rules.yaml skills/ingest/augur/tests/test_wiki_concept_links.py skills/ingest/augur/tests/test_wiki_pages.py
git commit -m "feat(wiki): lint concept links and legacy page types"
```

---

## Task 9: Add Concept Compiler Coordinator

**Files:**
- Create: `skills/ingest/scripts/wiki_concept_compiler.py`
- Create: `skills/ingest/augur/tests/test_wiki_concept_compiler.py`

- [ ] **Step 1: Write failing fake-agent compiler test**

Create `skills/ingest/augur/tests/test_wiki_concept_compiler.py`:

```python
from pathlib import Path

from skills.ingest.scripts.wiki_concept_compiler import apply_extraction_batch, prepare_extraction_batch
from skills.ingest.scripts.wiki_concept_models import SourceDescriptor
from skills.ingest.scripts.wiki_concept_state import WikiCompilerState


def test_prepare_extraction_batch_returns_changed_sources_only():
    state = WikiCompilerState()
    state.record_processed("vault:a.md", "same", "2026-04-20T09:00:00+00:00")
    sources = [
        SourceDescriptor("vault:a.md", "vault", "A", "/tmp/a.md", "same"),
        SourceDescriptor("vault:b.md", "vault", "B", "/tmp/b.md", "new"),
    ]

    batch = prepare_extraction_batch(sources, state, limit=10)

    assert [item.source.source_id for item in batch.items] == ["vault:b.md"]
    assert "durable concepts" in batch.items[0].prompt


def test_apply_extraction_batch_writes_concept_pages_and_state(tmp_path: Path):
    state = WikiCompilerState()
    source = SourceDescriptor("vault:b.md", "vault", "B", "/tmp/b.md", "new")

    result = apply_extraction_batch(
        wiki_dir=tmp_path / "wiki",
        runtime_wiki_dir=tmp_path / "runtime",
        state=state,
        sources=[source],
        payloads={
            "vault:b.md": [
                {
                    "title": "Concept First Wiki",
                    "slug": "concept-first-wiki",
                    "summary": "Merge concepts before writing pages.",
                    "confidence": 0.9,
                    "evidence": [{"quote": "Merge concepts before writing pages."}],
                    "aliases": [],
                    "related": [],
                }
            ]
        },
        timestamp="2026-04-20T09:00:00+00:00",
    )

    assert result.pages_written == ["concepts/concept-first-wiki.md"]
    assert (tmp_path / "wiki" / "concepts" / "concept-first-wiki.md").exists()
    assert state.sources["vault:b.md"].concept_slugs == ["concept-first-wiki"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest skills/ingest/augur/tests/test_wiki_concept_compiler.py -q
```

Expected: import failure for `wiki_concept_compiler`.

- [ ] **Step 3: Add coordinator implementation**

Create `skills/ingest/scripts/wiki_concept_compiler.py`:

```python
"""Batch coordinator for the concept-first wiki compiler."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from skills.ingest.scripts.wiki_concept_extraction import (
    build_extraction_prompt,
    parse_extraction_payload,
)
from skills.ingest.scripts.wiki_concept_merge import merge_extracted_concepts
from skills.ingest.scripts.wiki_concept_models import SourceDescriptor
from skills.ingest.scripts.wiki_concept_pages import write_concept_pages, write_wiki_index
from skills.ingest.scripts.wiki_concept_state import (
    WikiCompilerState,
    save_compiler_state,
    source_needs_extraction,
)


@dataclass(frozen=True)
class ExtractionBatchItem:
    source: SourceDescriptor
    prompt: str


@dataclass(frozen=True)
class ExtractionBatch:
    items: list[ExtractionBatchItem]


@dataclass(frozen=True)
class ApplyResult:
    pages_written: list[str]
    concepts_written: int


def prepare_extraction_batch(
    sources: list[SourceDescriptor],
    state: WikiCompilerState,
    *,
    limit: int,
) -> ExtractionBatch:
    items: list[ExtractionBatchItem] = []
    for source in sorted(sources, key=lambda item: (-item.priority, item.source_id)):
        if not source_needs_extraction(state, source.source_id, source.checksum):
            continue
        body = _read_source_body(source)
        items.append(ExtractionBatchItem(source=source, prompt=build_extraction_prompt(source, body)))
        if len(items) >= limit:
            break
    return ExtractionBatch(items=items)


def apply_extraction_batch(
    *,
    wiki_dir: Path,
    runtime_wiki_dir: Path,
    state: WikiCompilerState,
    sources: list[SourceDescriptor],
    payloads: dict[str, list[dict[str, Any]]],
    timestamp: str,
) -> ApplyResult:
    extracted = []
    by_id = {source.source_id: source for source in sources}
    for source_id, payload in payloads.items():
        source = by_id[source_id]
        concepts = parse_extraction_payload(source_id, payload)
        if concepts:
            state.record_extraction(source_id, source.checksum, concepts, timestamp)
            extracted.extend(concepts)
        else:
            state.record_processed(source_id, source.checksum, timestamp)
    merged = merge_extracted_concepts(extracted)
    written = write_concept_pages(wiki_dir, merged, timestamp=timestamp)
    write_wiki_index(wiki_dir, timestamp=timestamp)
    save_compiler_state(runtime_wiki_dir, state)
    return ApplyResult(
        pages_written=[path.relative_to(wiki_dir).as_posix() for path in written],
        concepts_written=len(merged),
    )


def _read_source_body(source: SourceDescriptor) -> str:
    path = Path(source.source_path)
    if path.exists() and path.is_file():
        return path.read_text(encoding="utf-8", errors="replace")
    rag_entry = source.metadata.get("rag_entry")
    if rag_entry:
        return Path(str(rag_entry)).read_text(encoding="utf-8", errors="replace")
    return source.title
```

- [ ] **Step 4: Run tests**

Run:

```bash
uv run pytest skills/ingest/augur/tests/test_wiki_concept_compiler.py -q
```

Expected: `2 passed`.

- [ ] **Step 5: Commit**

```bash
git add skills/ingest/scripts/wiki_concept_compiler.py skills/ingest/augur/tests/test_wiki_concept_compiler.py
git commit -m "feat(wiki): coordinate concept extraction batches"
```

---

## Task 10: Replace Wiki MCP Tools

**Files:**
- Modify: `skills/ingest/scripts/mcp/wiki_tools.py`
- Modify: `skills/ingest/augur/tests/test_wiki_tools.py`
- Modify: `.codex/skills/wiki/SKILL.md` only through sync output after canonical command source changes

- [ ] **Step 1: Write failing MCP tests for new semantics**

In `skills/ingest/augur/tests/test_wiki_tools.py`, add tests that assert:

```python
def test_registers_wiki_rebuild_prepare_tool(fake_mcp, monkeypatch, tmp_path):
    from skills.ingest.scripts.mcp.wiki_tools import register_wiki_tools

    register_wiki_tools(fake_mcp)

    assert "wiki-rebuild" in fake_mcp.tools
    assert "wiki-update" in fake_mcp.tools
    assert "wiki-compile-backlog" not in fake_mcp.tools
    assert "wiki-compile-batch" not in fake_mcp.tools
```

Add a second test for the apply operation:

```python
def test_registers_wiki_apply_concepts_tool(fake_mcp):
    from skills.ingest.scripts.mcp.wiki_tools import register_wiki_tools

    register_wiki_tools(fake_mcp)

    assert "wiki-apply-concept-batch" in fake_mcp.tools
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest skills/ingest/augur/tests/test_wiki_tools.py -q
```

Expected: failures showing old `wiki-compile-*` registrations still exist and new tools are absent.

- [ ] **Step 3: Replace registrations**

In `skills/ingest/scripts/mcp/wiki_tools.py`:

- remove `wiki-compile-backlog`
- remove `wiki-compile-preview`
- remove `wiki-compile-batch`
- remove `wiki-compile-selected`
- remove `wiki-compile-scope`
- remove `wiki-compile-status`
- remove `wiki-compile-cycle`
- add `wiki-rebuild`
- add `wiki-update`
- add `wiki-apply-concept-batch`

`wiki-rebuild` and `wiki-update` return an agent-action payload:

```python
{
    "success": True,
    "status": "agent_action_required",
    "batch": {
        "items": [
            {
                "source_id": item.source.source_id,
                "title": item.source.title,
                "prompt": item.prompt,
            }
            for item in batch.items
        ]
    },
    "instructions": "Run the prompts with the current agent, then call wiki-apply-concept-batch with extracted concept JSON.",
}
```

`wiki-apply-concept-batch` accepts structured extraction JSON and calls `apply_extraction_batch()`.

- [ ] **Step 4: Run tests**

Run:

```bash
uv run pytest skills/ingest/augur/tests/test_wiki_tools.py skills/ingest/augur/tests/test_wiki_concept_compiler.py -q
```

Expected: selected tests pass.

- [ ] **Step 5: Commit**

```bash
git add skills/ingest/scripts/mcp/wiki_tools.py skills/ingest/augur/tests/test_wiki_tools.py
git commit -m "feat(wiki): replace compile backlog tools with concept workflow"
```

---

## Task 11: Replace Wiki Reset Semantics

**Files:**
- Modify: `skills/ingest/scripts/wiki_reset.py`
- Modify: `skills/ingest/augur/tests/test_wiki_reset.py`

- [ ] **Step 1: Write failing reset test**

Add a test that creates legacy `sources/` output and runtime compiler state, runs reset with a fake concept compiler, and asserts reset removes legacy output and does not call the RAG source-scope compiler.

```python
def test_reset_purges_legacy_sources_and_uses_concept_rebuild(monkeypatch, tmp_path):
    from skills.ingest.scripts import wiki_reset

    wiki_dir = tmp_path / "wiki"
    runtime_wiki_dir = tmp_path / "runtime" / "wiki"
    (wiki_dir / "sources").mkdir(parents=True)
    (wiki_dir / "sources" / "old.md").write_text("old", encoding="utf-8")
    runtime_wiki_dir.mkdir(parents=True)
    (runtime_wiki_dir / "concept-compiler-state.json").write_text("{}", encoding="utf-8")

    called = {"concept": False, "rag": False}
    monkeypatch.setattr(wiki_reset, "get_wiki_dir", lambda: wiki_dir)
    monkeypatch.setattr(wiki_reset, "get_runtime_dir", lambda: tmp_path / "runtime")
    monkeypatch.setattr(wiki_reset, "run_concept_rebuild", lambda **kwargs: called.__setitem__("concept", True) or {"success": True})
    monkeypatch.setattr(wiki_reset, "compile_source_scope", lambda **kwargs: called.__setitem__("rag", True))

    result = wiki_reset.reset_wiki()

    assert result["success"] is True
    assert called == {"concept": True, "rag": False}
    assert not (wiki_dir / "sources").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest skills/ingest/augur/tests/test_wiki_reset.py::test_reset_purges_legacy_sources_and_uses_concept_rebuild -q
```

Expected: reset still calls the RAG source-scope compiler or does not know `run_concept_rebuild`.

- [ ] **Step 3: Update reset implementation**

In `skills/ingest/scripts/wiki_reset.py`, replace the `compile_source_scope` call with a concept rebuild entrypoint. Delete `sources/`, legacy `topics/` pages generated by old source wrappers if their frontmatter has `page_type: source-summary`, and `concept-compiler-state.json`.

- [ ] **Step 4: Run reset tests**

Run:

```bash
uv run pytest skills/ingest/augur/tests/test_wiki_reset.py -q
```

Expected: all reset tests pass after updating old expectations.

- [ ] **Step 5: Commit**

```bash
git add skills/ingest/scripts/wiki_reset.py skills/ingest/augur/tests/test_wiki_reset.py
git commit -m "feat(wiki): reset through concept compiler"
```

---

## Task 12: Rewire Ambient Import

**Files:**
- Modify: `skills/ingest/scripts/ambient_import_worker.py`
- Modify: `skills/ingest/augur/tests/test_ambient_import_worker.py`
- Modify: `skills/ingest/scripts/wiki_compile_worker.py`

- [ ] **Step 1: Write failing ambient import test**

Update the ambient worker test so it expects concept compiler priority input and no RAG `wiki_targets` restamping:

```python
def test_ambient_import_uses_concept_sources_not_rag_targets(monkeypatch, tmp_path):
    from skills.ingest.scripts import ambient_import_worker

    calls = {"concept_sources": [], "rag_targets": False}
    monkeypatch.setattr(
        ambient_import_worker,
        "prioritize_concept_sources",
        lambda paths: calls["concept_sources"].extend(paths),
    )
    monkeypatch.setattr(
        ambient_import_worker,
        "mark_rag_entries_compiled_batch",
        lambda *args, **kwargs: calls.__setitem__("rag_targets", True),
    )

    ambient_import_worker.handle_detected_paths([tmp_path / "documents" / "brief.md"])

    assert calls["concept_sources"] == [tmp_path / "documents" / "brief.md"]
    assert calls["rag_targets"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest skills/ingest/augur/tests/test_ambient_import_worker.py -q
```

Expected: old worker still calls compile backlog/restamp helpers.

- [ ] **Step 3: Rewire worker**

Replace direct calls to `wiki_compile_worker` and RAG restamping with a concept source prioritization helper. Preserve relocation and category reindexing only after concept compile succeeds.

- [ ] **Step 4: Run tests**

Run:

```bash
uv run pytest skills/ingest/augur/tests/test_ambient_import_worker.py skills/ingest/augur/tests/test_tracked_folder_scanner.py -q
```

Expected: selected tests pass.

- [ ] **Step 5: Commit**

```bash
git add skills/ingest/scripts/ambient_import_worker.py skills/ingest/scripts/wiki_compile_worker.py skills/ingest/augur/tests/test_ambient_import_worker.py
git commit -m "feat(wiki): route ambient import through concept sources"
```

---

## Task 13: Remove RAG-Owned Wiki Compile Metadata

**Files:**
- Modify: `skills/rag/scripts/_indexer_helpers.py`
- Modify: `skills/rag/augur/tests/test_index_reader.py`
- Modify: `skills/rag/augur/tests/test_unified_indexer.py`
- Modify: `skills/rag/augur/tests/test_rag_tools.py`

- [ ] **Step 1: Write failing RAG metadata removal test**

Replace tests that expect preservation of wiki compile metadata with this assertion:

```python
def test_write_entry_drops_legacy_wiki_compile_metadata(tmp_path):
    from src.lib.frontmatter_utils import parse_frontmatter
    from skills.rag.scripts._indexer_helpers import _write_entry

    output = tmp_path / "rag" / "vault" / "ideas.md"
    output.parent.mkdir(parents=True)
    output.write_text(
        "---\\n"
        "type: vault\\n"
        "source_path: /tmp/ideas.md\\n"
        "checksum: old\\n"
        "wiki_compile_status: compiled\\n"
        "wiki_targets:\\n"
        "  - topics/ideas\\n"
        "---\\n",
        encoding="utf-8",
    )

    _write_entry(output, {"type": "vault", "source_path": "/tmp/ideas.md", "checksum": "new"})

    meta, _ = parse_frontmatter(output)
    assert "wiki_compile_status" not in meta
    assert "wiki_targets" not in meta
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest skills/rag/augur/tests/test_unified_indexer.py::test_write_entry_drops_legacy_wiki_compile_metadata -q
```

Expected: old preservation behavior keeps the fields.

- [ ] **Step 3: Remove preservation code**

In `skills/rag/scripts/_indexer_helpers.py`, delete the preservation block for:

- `wiki_compile_status`
- `wiki_compiled_at`
- `wiki_compiled_checksum`
- `wiki_targets`

Keep preservation behavior for unrelated user-managed fields such as `manual_related`.

- [ ] **Step 4: Run RAG tests**

Run:

```bash
uv run pytest skills/rag/augur/tests/test_index_reader.py skills/rag/augur/tests/test_unified_indexer.py skills/rag/augur/tests/test_rag_tools.py -q
```

Expected: tests pass after removing old assertions and adding removal assertions.

- [ ] **Step 5: Commit**

```bash
git add skills/rag/scripts/_indexer_helpers.py skills/rag/augur/tests/test_index_reader.py skills/rag/augur/tests/test_unified_indexer.py skills/rag/augur/tests/test_rag_tools.py
git commit -m "refactor(wiki): remove rag-owned compile metadata"
```

---

## Task 14: Delete Legacy Compiler Modules After History Checks

**Files:**
- Delete: `skills/ingest/scripts/wiki_compile_backlog.py`
- Delete: `skills/ingest/scripts/wiki_page_candidates.py`
- Delete: `skills/ingest/scripts/wiki_page_identity.py`
- Delete: `skills/ingest/scripts/wiki_signal_graph.py`
- Delete: `skills/ingest/scripts/wiki_article_sections.py`
- Modify: tests that import deleted modules

- [ ] **Step 1: Record deletion history**

Run:

```bash
git log --oneline -5 -- skills/ingest/scripts/wiki_compile_backlog.py
git log --oneline -5 -- skills/ingest/scripts/wiki_page_candidates.py
git log --oneline -5 -- skills/ingest/scripts/wiki_page_identity.py
git log --oneline -5 -- skills/ingest/scripts/wiki_signal_graph.py
git log --oneline -5 -- skills/ingest/scripts/wiki_article_sections.py
```

Expected: recent history points to ADR-560 or the RAG-backed wiki compiler work. Record in the task notes that ADR-561 supersedes those files.

- [ ] **Step 2: Prove no active callers remain**

Run:

```bash
rg -n "wiki_compile_backlog|wiki_page_candidates|wiki_page_identity|wiki_signal_graph|wiki_article_sections" skills docs -g '*.py' -g '*.md' -g '*.yaml'
```

Expected: no active Python callers remain. Superseded docs may still mention the old files with an ADR-561 banner.

- [ ] **Step 3: Delete files and obsolete tests**

Delete the five modules. Delete or rewrite tests whose only purpose was asserting old behavior:

- `skills/ingest/augur/tests/test_wiki_compile_backlog.py`
- `skills/ingest/augur/tests/test_wiki_page_candidates.py`
- `skills/ingest/augur/tests/test_wiki_page_identity.py`
- `skills/ingest/augur/tests/test_wiki_signal_graph.py`
- `skills/ingest/augur/tests/test_wiki_article_sections.py`

Keep tests that can be converted to concept-first behavior by moving assertions into the new concept test files.

- [ ] **Step 4: Run focused ingest tests**

Run:

```bash
uv run pytest skills/ingest/augur/tests/test_wiki_concept_models.py skills/ingest/augur/tests/test_wiki_concept_state.py skills/ingest/augur/tests/test_wiki_source_inventory.py skills/ingest/augur/tests/test_wiki_concept_extraction.py skills/ingest/augur/tests/test_wiki_concept_merge.py skills/ingest/augur/tests/test_wiki_concept_pages.py skills/ingest/augur/tests/test_wiki_concept_links.py skills/ingest/augur/tests/test_wiki_concept_compiler.py skills/ingest/augur/tests/test_wiki_tools.py skills/ingest/augur/tests/test_wiki_reset.py -q
```

Expected: selected tests pass.

- [ ] **Step 5: Commit**

```bash
git add -A skills/ingest/scripts skills/ingest/augur/tests
git commit -m "refactor(wiki): remove legacy rag-backed compiler"
```

---

## Task 15: Update Command Docs And Regenerate Agent Surfaces

**Files:**
- Modify: `skills/ingest/SKILL.md`
- Modify: canonical `/wiki` command source under `skills/rag/commands/wiki.md`
- Generated: `.codex/skills/wiki/SKILL.md`
- Generated: `AGENTS.md`, `CODEX.md`, `.gemini/GEMINI.md`, and other sync outputs if changed

- [ ] **Step 1: Update canonical command docs**

In `skills/rag/commands/wiki.md`, make the command contract explicit:

```markdown
- `reindex` refreshes browse/search indexing for existing wiki pages only.
- `rebuild` prepares or runs a concept-first compile from current sources.
- `update` prepares or runs an incremental concept-first compile for changed sources.
- `reset` purges generated wiki pages and compiler state, then rebuilds, reindexes, and lints.
```

In `skills/ingest/SKILL.md`, remove all old `wiki-compile-*` command descriptions and replace them with concept-first tools:

```markdown
| `wiki-rebuild` | mutation | Prepare or run a concept-first wiki rebuild from current sources |
| `wiki-update` | mutation | Prepare or run an incremental concept-first update for changed sources |
| `wiki-apply-concept-batch` | mutation | Apply agent-produced extracted concepts to compiler state and wiki pages |
```

- [ ] **Step 2: Regenerate agent surfaces**

Run:

```bash
python3 -m skills.ai.scripts.sync_agents sync all
```

Expected: generated surfaces update without frontmatter errors.

- [ ] **Step 3: Verify old command text is gone from active surfaces**

Run:

```bash
rg -n "wiki-compile-|source-summary|wiki_compile_status|wiki_targets" skills .codex .gemini AGENTS.md CODEX.md -g '*.md' -g '*.py' -g '*.yaml' -g '*.json'
```

Expected: no active generated or canonical command surfaces advertise removed semantics. Superseded historical docs are allowed outside these paths.

- [ ] **Step 4: Commit**

```bash
git add skills/rag/commands/wiki.md skills/ingest/SKILL.md .codex .gemini AGENTS.md CODEX.md
git commit -m "docs(wiki): expose concept-first wiki commands"
```

---

## Task 16: End-To-End Verification And Final Cleanup

**Files:**
- Modify as needed based on verification findings
- Runtime: wiki directory and runtime compiler state

- [ ] **Step 1: Run targeted tests**

Run:

```bash
uv run pytest skills/ingest/augur/tests/test_wiki_concept_models.py skills/ingest/augur/tests/test_wiki_concept_state.py skills/ingest/augur/tests/test_wiki_source_inventory.py skills/ingest/augur/tests/test_wiki_concept_extraction.py skills/ingest/augur/tests/test_wiki_concept_merge.py skills/ingest/augur/tests/test_wiki_concept_pages.py skills/ingest/augur/tests/test_wiki_concept_links.py skills/ingest/augur/tests/test_wiki_concept_compiler.py skills/ingest/augur/tests/test_wiki_tools.py skills/ingest/augur/tests/test_wiki_reset.py skills/ingest/augur/tests/test_ambient_import_worker.py skills/rag/augur/tests/test_unified_indexer.py -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Run repository audits**

Run:

```bash
rg -n "source-summary" skills docs -g '*.py' -g '*.md' -g '*.yaml'
rg -n "wiki_compile_status|wiki_compiled|wiki_targets" skills docs -g '*.py' -g '*.md' -g '*.yaml'
rg -n "wiki-compile-" skills docs -g '*.py' -g '*.md' -g '*.yaml'
```

Expected: only ADR-561, superseded historical docs, and implementation notes mention removed terms. Active code and skill docs do not.

- [ ] **Step 3: Run concept wiki reset flow**

Run the wiki reset command through the available MCP/slash command path. If running through Python test harness, use the same registered tool functions that the MCP server exposes.

Expected:

- generated wiki has `concepts/` and optionally `queries/`
- generated wiki does not have `sources/`
- `index.md` lists concepts and queries, not source inventory rows
- lint reports no legacy page types

- [ ] **Step 4: Reindex generated wiki pages**

Run:

```bash
python3 skills/rag/scripts/unified_indexer.py --category wiki
```

Expected: wiki pages are indexed for browse/search and no new wiki pages are created by the reindex command.

- [ ] **Step 5: Update ADR implementation status after code lands**

After all implementation commits are verified, update `~/Projects/Au-docs/adrs/ADR-561-concept-first-wiki-compiler-replacement.md`:

- `status: Implemented`
- `implemented_date: '2026-04-20'`
- `implementation_commits:` with the commit SHAs created by this plan

Then run:

```bash
python3 .github/scripts/generate_adr_index.py
python3 skills/rag/scripts/unified_indexer.py --category adrs
python3 -m skills.ai.scripts.sync_agents sync agents all
```

- [ ] **Step 6: Final commit**

```bash
git add -A
git commit -m "feat(wiki): complete concept-first compiler replacement"
```

---

## Self-Review Checklist

- Every ADR-561 requirement maps to a task:
  - source inventory: Task 4
  - runtime compiler state: Task 3
  - concept extraction: Task 5
  - concept merge: Task 6
  - concept/query page writing: Task 7
  - wikilink/lint: Task 8
  - MCP command contract: Task 10
  - reset semantics: Task 11
  - ambient import rewiring: Task 12
  - RAG metadata removal: Task 13
  - legacy deletion: Task 14
  - docs/generated surfaces: Task 15
  - end-to-end verification: Task 16
- No task leaves `source-summary`, RAG compile metadata, or old `wiki-compile-*` backlog semantics active.
- Deletion tasks include required ADR/history checks before file removal.
- The plan avoids dashboard LLM calls and keeps LLM judgment agent-orchestrated.
