# Typed Knowledge Graph Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic, zero-LLM typed-edge layer over the Augur vault — `graph/` skill, per-type `_<edge>:` frontmatter, rebuildable JSONL cache, entity tiers — wired into the `/ingest`, `/wiki`, `/save`, `/ask`, `/profile` write paths.

**Architecture:** A standalone `shared-vault/skills/graph/` skill owns a rule engine (`edge_rules.py`) that reads `config/system/graph_edges.yaml`, an extractor (`edge_extractor.py`) that derives typed edges deterministically from data the write paths already produce, an additive frontmatter writer (`edge_writer.py`), a file-first JSONL cache (`graph_cache.py`), tiering (`entity_tier.py`), a query layer (`graph_query.py`), and MCP/CLI tools. Edges are stored as per-type underscore-prefixed link lists so Obsidian's graph view renders them.

**Tech Stack:** Python 3.11+, `src/lib/frontmatter_utils.py`, `src/lib/relationship_index.py`, `src/config/paths.py`, FastMCP. No new dependencies. No database. No LLM calls.

**Spec:** `docs/superpowers/specs/2026-05-14-typed-knowledge-graph-design.md` · **ADR:** ADR-738

---

## Shared Test Harness (preamble — used verbatim by every test file)

Every test file in `shared-vault/skills/graph/augur/tests/` begins with this exact
loader block (per `feedback_skill_test_convention` — importlib, never dotted module path):

```python
"""Tests for <module>.py — typed knowledge graph (ADR-738).

Imports via importlib.util.spec_from_file_location per feedback_skill_test_convention.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"


def _load(module_name: str, file_name: str) -> Any:
    full_name = f"graph_{module_name}"
    if full_name in sys.modules:
        return sys.modules[full_name]
    spec = importlib.util.spec_from_file_location(full_name, SCRIPTS_DIR / file_name)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = module
    sys.modules[module_name] = module  # alias bare name so siblings resolve
    spec.loader.exec_module(module)
    return module
```

Run all graph tests with: `/auto-test-pytest shared-vault/skills/graph/augur/tests/`
(never raw `pytest` — rule 29).

---

# Phase 1 — Config + Rule Engine

## Task 1: Skill scaffold

**Files:**
- Create: `shared-vault/skills/graph/SKILL.md`
- Create: `shared-vault/skills/graph/config.yaml`
- Create: `shared-vault/skills/graph/scripts/__init__.py` (empty)
- Create: `shared-vault/skills/graph/scripts/bootstrap_paths.py`
- Create: `shared-vault/skills/graph/scripts/mcp/__init__.py` (stub — filled in Task 11)
- Create: `shared-vault/skills/graph/augur/tests/__init__.py` (empty)

- [ ] **Step 1: Create the skill directory tree**

```bash
mkdir -p shared-vault/skills/graph/scripts/mcp shared-vault/skills/graph/augur/tests
touch shared-vault/skills/graph/scripts/__init__.py shared-vault/skills/graph/augur/tests/__init__.py
```

- [ ] **Step 2: Write `bootstrap_paths.py`** (copied verbatim from the `evals` skill — it is generic)

```python
"""Bootstrap Augur project paths for graph skill scripts."""
from __future__ import annotations

import sys
from pathlib import Path


def find_project_root(start_file: str | Path) -> Path:
    """Find the Augur project root by repo landmarks."""
    start = Path(start_file).resolve()
    for candidate in (start.parent, *start.parents):
        if (
            (candidate / "pyproject.toml").is_file()
            and (candidate / "src" / "config" / "paths.py").is_file()
        ):
            return candidate
    raise RuntimeError(f"Unable to locate Augur project root from {start}")


def ensure_project_paths(start_file: str | Path) -> Path:
    """Put canonical shared-vault and project import roots on sys.path."""
    project_root = find_project_root(start_file)
    for path in (project_root / "src" / "mcp", project_root, project_root / "shared-vault"):
        text = str(path)
        if text not in sys.path:
            sys.path.insert(0, text)
    return project_root
```

- [ ] **Step 3: Write `SKILL.md`** with `x-augur-*` frontmatter (shape mirrors the `evals` skill)

```markdown
---
name: graph
x-augur-type: skill
x-augur-group: augur_brain
x-augur-release: mvp
x-augur-tags: [knowledge, graph, retrieval]
description: Typed knowledge graph layer — deterministic, zero-LLM typed-edge
  extraction over the vault. Labels every link (cites, mentions, depends_on, ...)
  as data is written by /ingest, /wiki, /save, /ask, /profile. Per-type
  underscore-prefixed frontmatter link lists (Obsidian-graph-visible) over a
  rebuildable JSONL cache. No database, no model calls. Implements ADR-738.
x-augur-hub: brain
x-augur-callable: shared-vault/skills/graph/scripts/graph_ops.py
x-augur-mcp-tools:
  - graph-extract
  - graph-query
  - graph-stats
  - entity-tier-recompute
  - graph-rebuild
x-augur-data-dir: graph
x-augur-config:
  commands:
  - id: graph
    type: workflow
    visibility: dev
    description: Typed knowledge graph CLI — extract, query, stats, rebuild,
      tier-recompute.
    callable: scripts/graph_ops.py
    protocol: guide
---

# graph

Augur's typed knowledge graph. Turns the vault's `[[links]]` into a queryable
map by labeling every connection deterministically — no LLM, no token cost — at
the moment `/ingest`, `/wiki`, `/save`, `/ask`, or `/profile` writes data.

Three non-negotiable principles, inherited from the gbrain borrow slate:

1. **File-first.** Durable edges live in vault frontmatter; the query cache is
   rebuildable JSONL under `get_cache_dir()/graph/`. `cat edges.jsonl` works.
2. **Zero-LLM.** Extraction is a deterministic rule engine over data the write
   paths already produce. No model calls, ever.
3. **Augment, never replace.** Typed edges sit alongside the untyped
   `RelationshipIndex`; both coexist.

See `docs/superpowers/specs/2026-05-14-typed-knowledge-graph-design.md`.
```

- [ ] **Step 4: Write `config.yaml`** (skill-local; loop/alert config — currently just a pointer, real config is `config/system/graph_edges.yaml`)

```yaml
# graph skill configuration — ADR-738
# The edge-type registry and tier thresholds are CENTRAL config, not skill-local,
# because users and other skills extend them. See config/system/graph_edges.yaml.
edge_config_path: config/system/graph_edges.yaml
```

- [ ] **Step 5: Write the `scripts/mcp/__init__.py` stub** (header + empty registration — filled in Task 11)

```python
"""MCP tools + CLI subcommands for the graph skill (ADR-738). Filled in Task 11."""
from __future__ import annotations


def register_tools(mcp, mcp_tool_interceptor, metrics) -> None:  # noqa: D103
    pass


def register_subcommands(subparsers) -> None:  # noqa: D103
    pass


__all__ = ["register_tools", "register_subcommands"]
```

- [ ] **Step 6: Commit**

```bash
git add shared-vault/skills/graph/
git commit -m "feat(graph): scaffold typed knowledge graph skill (ADR-738)"
```

## Task 2: Edge-type registry config

**Files:**
- Create: `config/system/graph_edges.yaml`

- [ ] **Step 1: Write `config/system/graph_edges.yaml`** — the Augur-native seed schema + tier thresholds

```yaml
# Typed knowledge graph — edge-type registry + tier thresholds (ADR-738).
# Extensible: users and skills append edge types here. Every rule is FORWARD —
# the edge is stored on the page being extracted, pointing at the link target.
#
# rule kinds:
#   frontmatter_key  — map an existing frontmatter list/scalar key to this edge
#   concept_hook     — consume concepts passed to extract(known=...) by /ingest
#   body_wikilink    — [[links]] in the body; scope: heading (under a heading) | bare

edge_types:
  mentions:
    description: any -> concept; the typed fallback for unmatched [[wikilinks]]
    rules:
      - {kind: concept_hook}
      - {kind: body_wikilink, scope: bare}
  cites:
    description: note/answer -> source
    rules:
      - {kind: frontmatter_key, key: cited_sources}
      - {kind: body_wikilink, scope: heading, headings: [Sources, References, Timeline]}
  authored_by:
    description: source -> person
    rules:
      - {kind: frontmatter_key, key: author}
  relates_to:
    description: concept <-> concept
    rules:
      - {kind: frontmatter_key, key: related}
      - {kind: frontmatter_key, key: tags}
  depends_on:
    description: skill/ADR -> skill/ADR
    rules:
      - {kind: body_wikilink, scope: heading, headings: ["Depends on", Dependencies]}
  part_of:
    description: sub-concept -> parent
    rules:
      - {kind: frontmatter_key, key: parent}
  supersedes:
    description: page -> page it replaces
    rules:
      - {kind: frontmatter_key, key: supersedes}

# Entity tier thresholds. Tier 3 is the implicit "everything else".
tiers:
  tier_1: {min_inbound: 10, min_source_types: 3}
  tier_2: {min_inbound: 3, min_source_types: 1}
```

- [ ] **Step 2: Verify it parses**

Run: `python3 -c "import yaml; d=yaml.safe_load(open('config/system/graph_edges.yaml')); print(sorted(d['edge_types']), d['tiers'])"`
Expected: `['authored_by', 'cites', 'depends_on', 'mentions', 'part_of', 'relates_to', 'supersedes'] {'tier_1': {...}, 'tier_2': {...}}`

- [ ] **Step 3: Commit**

```bash
git add config/system/graph_edges.yaml
git commit -m "feat(graph): add graph_edges.yaml edge-type registry (ADR-738)"
```

## Task 3: Rule engine — `edge_rules.py`

**Files:**
- Create: `shared-vault/skills/graph/scripts/edge_rules.py`
- Test: `shared-vault/skills/graph/augur/tests/test_edge_rules.py`

- [ ] **Step 1: Write the failing test** (prepend the Shared Test Harness loader block)

```python
def test_load_rules_parses_seed_schema(tmp_path: Path) -> None:
    er = _load("edge_rules", "edge_rules.py")
    cfg = tmp_path / "graph_edges.yaml"
    cfg.write_text(
        "edge_types:\n"
        "  cites:\n"
        "    rules:\n"
        "      - {kind: frontmatter_key, key: cited_sources}\n"
        "  mentions:\n"
        "    rules:\n"
        "      - {kind: body_wikilink, scope: bare}\n"
        "tiers:\n"
        "  tier_1: {min_inbound: 10, min_source_types: 3}\n"
        "  tier_2: {min_inbound: 3, min_source_types: 1}\n",
        encoding="utf-8",
    )
    rs = er.load_rules(cfg)
    assert set(rs.edge_types) == {"cites", "mentions"}
    assert rs.tiers["tier_1"]["min_inbound"] == 10
    fk = rs.rules_for_kind("frontmatter_key")
    assert ("cites", {"kind": "frontmatter_key", "key": "cited_sources"}) in fk


def test_malformed_config_fails_closed(tmp_path: Path) -> None:
    er = _load("edge_rules", "edge_rules.py")
    cfg = tmp_path / "broken.yaml"
    cfg.write_text("edge_types: [this is not a mapping", encoding="utf-8")
    rs = er.load_rules(cfg)  # must not raise
    # fail-closed: a minimal ruleset with only the bare-wikilink mentions rule
    assert set(rs.edge_types) == {"mentions"}
    assert rs.rules_for_kind("body_wikilink") == [
        ("mentions", {"kind": "body_wikilink", "scope": "bare"})
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/auto-test-pytest shared-vault/skills/graph/augur/tests/test_edge_rules.py`
Expected: FAIL — `ModuleNotFoundError` / `edge_rules.py` does not exist.

- [ ] **Step 3: Write `edge_rules.py`**

```python
"""Deterministic rule engine for the typed knowledge graph (ADR-738).

Loads config/system/graph_edges.yaml into a RuleSet. Fails CLOSED: a malformed
config never raises into a write path — it falls back to a minimal ruleset with
only the bare-wikilink `mentions` fallback (still a superset of nothing lost).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger("graph.edge_rules")

# The fail-closed minimum: every [[wikilink]] still becomes a `mentions` edge.
_FALLBACK_EDGE_TYPES: dict[str, Any] = {
    "mentions": {"rules": [{"kind": "body_wikilink", "scope": "bare"}]}
}
_FALLBACK_TIERS: dict[str, Any] = {
    "tier_1": {"min_inbound": 10, "min_source_types": 3},
    "tier_2": {"min_inbound": 3, "min_source_types": 1},
}


@dataclass
class RuleSet:
    """Parsed edge-type registry + tier thresholds."""

    edge_types: dict[str, Any] = field(default_factory=dict)
    tiers: dict[str, Any] = field(default_factory=dict)

    def rules_for_kind(self, kind: str) -> list[tuple[str, dict[str, Any]]]:
        """Return (edge_type, rule) pairs for every rule of the given kind."""
        out: list[tuple[str, dict[str, Any]]] = []
        for edge_type, spec in self.edge_types.items():
            for rule in spec.get("rules", []):
                if isinstance(rule, dict) and rule.get("kind") == kind:
                    out.append((edge_type, rule))
        return out


def _coerce(data: Any) -> RuleSet:
    """Validate a parsed YAML doc into a RuleSet, or raise ValueError."""
    if not isinstance(data, dict):
        raise ValueError("graph_edges.yaml root is not a mapping")
    edge_types = data.get("edge_types")
    if not isinstance(edge_types, dict) or not edge_types:
        raise ValueError("graph_edges.yaml has no edge_types mapping")
    for name, spec in edge_types.items():
        if not isinstance(spec, dict) or not isinstance(spec.get("rules"), list):
            raise ValueError(f"edge type {name!r} has no rules list")
    tiers = data.get("tiers")
    if not isinstance(tiers, dict):
        tiers = dict(_FALLBACK_TIERS)
    return RuleSet(edge_types=edge_types, tiers=tiers)


def load_rules(config_path: str | Path | None = None) -> RuleSet:
    """Load the edge-type registry. Fails closed to a minimal ruleset."""
    if config_path is None:
        from src.config.paths import get_project_root

        config_path = get_project_root() / "config" / "system" / "graph_edges.yaml"
    path = Path(config_path)
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return _coerce(data)
    except Exception as exc:  # noqa: BLE001 — fail closed, never raise into a write
        logger.warning("graph_edges.yaml unusable (%s); falling back to mentions-only", exc)
        return RuleSet(edge_types=dict(_FALLBACK_EDGE_TYPES), tiers=dict(_FALLBACK_TIERS))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/auto-test-pytest shared-vault/skills/graph/augur/tests/test_edge_rules.py`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add shared-vault/skills/graph/scripts/edge_rules.py shared-vault/skills/graph/augur/tests/test_edge_rules.py
git commit -m "feat(graph): rule engine with fail-closed config loading (ADR-738)"
```

---

# Phase 2 — Extractor + Writer + Cache

## Task 4: Edge model + extractor — `edge_extractor.py`

**Files:**
- Create: `shared-vault/skills/graph/scripts/edge_extractor.py`
- Test: `shared-vault/skills/graph/augur/tests/test_edge_extractor.py`

- [ ] **Step 1: Write the failing test** (prepend the Shared Test Harness loader block)

```python
WIKILINK_FIXTURE = """---
title: Reciprocal Rank Fusion
related: ["[[hybrid search]]"]
tags: ["[[retrieval]]"]
---

# Reciprocal Rank Fusion

## Depends on
- [[BM25]]

## Sources
- [[Cormack 2009]]

Body mentions [[vector search]] inline.
"""


def _write(tmp_path: Path, name: str, text: str) -> Path:
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


def test_extract_frontmatter_heading_and_bare_rules(tmp_path: Path) -> None:
    er = _load("edge_rules", "edge_rules.py")
    ex = _load("edge_extractor", "edge_extractor.py")
    cfg = _write(tmp_path, "graph_edges.yaml", (
        "edge_types:\n"
        "  relates_to: {rules: [{kind: frontmatter_key, key: related},"
        " {kind: frontmatter_key, key: tags}]}\n"
        "  depends_on: {rules: [{kind: body_wikilink, scope: heading,"
        " headings: [\"Depends on\"]}]}\n"
        "  cites: {rules: [{kind: body_wikilink, scope: heading, headings: [Sources]}]}\n"
        "  mentions: {rules: [{kind: concept_hook}, {kind: body_wikilink, scope: bare}]}\n"
        "tiers: {tier_1: {min_inbound: 10, min_source_types: 3},"
        " tier_2: {min_inbound: 3, min_source_types: 1}}\n"
    ))
    page = _write(tmp_path, "rrf.md", WIKILINK_FIXTURE)
    rs = er.load_rules(cfg)
    edges = ex.extract(page, ruleset=rs)
    pairs = {(e.type, e.dst) for e in edges}
    assert ("relates_to", "hybrid search") in pairs
    assert ("relates_to", "retrieval") in pairs
    assert ("depends_on", "BM25") in pairs
    assert ("cites", "Cormack 2009") in pairs
    assert ("mentions", "vector search") in pairs        # bare fallback
    # a link claimed by a heading rule is NOT also emitted as bare `mentions`
    assert ("mentions", "BM25") not in pairs
    assert all(e.src == "rrf" for e in edges)


def test_concept_hook_consumes_known(tmp_path: Path) -> None:
    er = _load("edge_rules", "edge_rules.py")
    ex = _load("edge_extractor", "edge_extractor.py")
    cfg = _write(tmp_path, "graph_edges.yaml", (
        "edge_types: {mentions: {rules: [{kind: concept_hook},"
        " {kind: body_wikilink, scope: bare}]}}\n"
        "tiers: {tier_2: {min_inbound: 3, min_source_types: 1}}\n"
    ))
    page = _write(tmp_path, "src.md", "---\ntitle: A source\n---\n\nNo wikilinks here.\n")
    rs = er.load_rules(cfg)
    edges = ex.extract(page, known={"concepts": ["RRF", "hybrid search"]}, ruleset=rs)
    assert {(e.type, e.dst) for e in edges} == {
        ("mentions", "RRF"), ("mentions", "hybrid search")
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/auto-test-pytest shared-vault/skills/graph/augur/tests/test_edge_extractor.py`
Expected: FAIL — `edge_extractor.py` does not exist.

- [ ] **Step 3: Write `edge_extractor.py`**

```python
"""Deterministic typed-edge extraction (ADR-738).

extract(path, known=..., ruleset=...) -> list[Edge]. No LLM. Three rule kinds,
applied in order so a link claimed by a specific rule is never double-emitted as
the bare `mentions` fallback.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.lib.frontmatter_utils import parse_frontmatter

from edge_rules import RuleSet, load_rules  # sibling import (scripts/ on sys.path)

_WIKILINK_RE = re.compile(r"\[\[([^\]|]+?)(?:\|[^\]]+)?\]\]")
_HEADING_RE = re.compile(r"^#{1,6}\s+(.*?)\s*$")


@dataclass(frozen=True)
class Edge:
    """A typed edge: src --type--> dst, both page-id strings."""

    src: str
    dst: str
    type: str


def _page_id(path: Path) -> str:
    """Page id = filename stem (matches how [[wikilinks]] resolve)."""
    return path.stem


def _norm(target: str) -> str:
    """Normalize a link target / frontmatter value to a bare page id."""
    m = _WIKILINK_RE.search(target) if "[[" in target else None
    return (m.group(1) if m else target).strip()


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(v) for v in value]
    return [str(value)]


def _headings_with_links(body: str) -> tuple[dict[str, set[str]], set[str]]:
    """Return ({heading: {link, ...}}, {all links anywhere})."""
    by_heading: dict[str, set[str]] = {}
    all_links: set[str] = set()
    current = ""
    for line in body.splitlines():
        h = _HEADING_RE.match(line)
        if h:
            current = h.group(1).strip()
            by_heading.setdefault(current, set())
            continue
        for m in _WIKILINK_RE.finditer(line):
            link = m.group(1).strip()
            all_links.add(link)
            if current:
                by_heading[current].add(link)
    return by_heading, all_links


def extract(
    path: str | Path,
    *,
    known: dict[str, Any] | None = None,
    ruleset: RuleSet | None = None,
) -> list[Edge]:
    """Extract typed edges for one page. Deterministic, no model calls."""
    path = Path(path)
    rs = ruleset or load_rules()
    known = known or {}
    src = _page_id(path)
    meta, body = parse_frontmatter(path)
    by_heading, all_links = _headings_with_links(body)

    edges: set[Edge] = set()
    claimed: set[str] = set()  # links claimed by a specific (non-bare) rule

    # 1. frontmatter_key rules
    for edge_type, rule in rs.rules_for_kind("frontmatter_key"):
        for raw in _as_list(meta.get(rule["key"])):
            dst = _norm(raw)
            if dst:
                edges.add(Edge(src, dst, edge_type))

    # 2. concept_hook rules — consume concepts the caller already extracted
    for edge_type, _rule in rs.rules_for_kind("concept_hook"):
        for concept in known.get("concepts", []):
            dst = _norm(str(concept))
            if dst:
                edges.add(Edge(src, dst, edge_type))

    # 3a. body_wikilink heading-scoped rules
    for edge_type, rule in rs.rules_for_kind("body_wikilink"):
        if rule.get("scope") != "heading":
            continue
        wanted = {h.lower() for h in rule.get("headings", [])}
        for heading, links in by_heading.items():
            if heading.lower() in wanted:
                for link in links:
                    edges.add(Edge(src, link, edge_type))
                    claimed.add(link)

    # 3b. body_wikilink bare fallback — any link not already claimed
    for edge_type, rule in rs.rules_for_kind("body_wikilink"):
        if rule.get("scope") != "bare":
            continue
        for link in all_links - claimed:
            edges.add(Edge(src, link, edge_type))

    return sorted(edges, key=lambda e: (e.type, e.dst))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/auto-test-pytest shared-vault/skills/graph/augur/tests/test_edge_extractor.py`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add shared-vault/skills/graph/scripts/edge_extractor.py shared-vault/skills/graph/augur/tests/test_edge_extractor.py
git commit -m "feat(graph): deterministic typed-edge extractor (ADR-738)"
```

## Task 5: Frontmatter writer — `edge_writer.py`

**Files:**
- Create: `shared-vault/skills/graph/scripts/edge_writer.py`
- Test: `shared-vault/skills/graph/augur/tests/test_edge_writer.py`

- [ ] **Step 1: Write the failing test** (prepend the Shared Test Harness loader block)

```python
def test_merge_is_additive_and_preserves_user_edges(tmp_path: Path) -> None:
    ex = _load("edge_extractor", "edge_extractor.py")
    ew = _load("edge_writer", "edge_writer.py")
    page = tmp_path / "note.md"
    # user has already hand-added a _depends_on edge via Obsidian's Properties panel
    page.write_text(
        '---\ntitle: Note\n_depends_on: ["[[hand-added]]"]\n---\n\nbody\n',
        encoding="utf-8",
    )
    edges = [ex.Edge("note", "RRF", "mentions"), ex.Edge("note", "BM25", "mentions")]
    diff = ew.merge(page, edges)

    from src.lib.frontmatter_utils import parse_frontmatter

    meta, _ = parse_frontmatter(page)
    assert sorted(meta["_mentions"]) == ["[[BM25]]", "[[RRF]]"]
    assert meta["_depends_on"] == ["[[hand-added]]"]      # user edge preserved
    assert meta["title"] == "Note"                        # user key untouched
    assert set(diff["added"]) == {"_mentions:[[RRF]]", "_mentions:[[BM25]]"}

    # second run is idempotent — nothing added
    diff2 = ew.merge(page, edges)
    assert diff2["added"] == []


def test_prune_removes_unmatched_but_diffs_first(tmp_path: Path) -> None:
    ex = _load("edge_extractor", "edge_extractor.py")
    ew = _load("edge_writer", "edge_writer.py")
    page = tmp_path / "note.md"
    page.write_text(
        '---\ntitle: Note\n_mentions: ["[[stale]]", "[[RRF]]"]\n---\n\nbody\n',
        encoding="utf-8",
    )
    edges = [ex.Edge("note", "RRF", "mentions")]
    diff = ew.merge(page, edges, prune=True)

    from src.lib.frontmatter_utils import parse_frontmatter

    meta, _ = parse_frontmatter(page)
    assert meta["_mentions"] == ["[[RRF]]"]
    assert diff["removed"] == ["_mentions:[[stale]]"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/auto-test-pytest shared-vault/skills/graph/augur/tests/test_edge_writer.py`
Expected: FAIL — `edge_writer.py` does not exist.

- [ ] **Step 3: Write `edge_writer.py`**

```python
"""Additive per-type frontmatter writer for typed edges (ADR-738).

Each edge type is its own underscore-prefixed key holding a list of [[wikilinks]]
(system-managed per ADR-571, but MERGED not overwritten — a user-added edge is
never clobbered). Only merge(..., prune=True) removes entries, and it diffs first.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from src.lib.frontmatter_utils import parse_frontmatter, write_frontmatter


def _key(edge_type: str) -> str:
    return f"_{edge_type}"


def _wikilink(dst: str) -> str:
    return dst if dst.startswith("[[") else f"[[{dst}]]"


def merge(path: str | Path, edges: Iterable[Any], *, prune: bool = False) -> dict[str, list[str]]:
    """Additively merge typed edges into a page's per-type frontmatter keys.

    Returns a diff: {"added": [...], "removed": [...], "unchanged": [...]}.
    `prune=True` removes managed-key entries not present in `edges`.
    """
    path = Path(path)
    meta, body = parse_frontmatter(path)

    extracted: dict[str, set[str]] = {}
    for edge in edges:
        extracted.setdefault(_key(edge.type), set()).add(_wikilink(edge.dst))

    added: list[str] = []
    removed: list[str] = []
    unchanged: list[str] = []

    managed_keys = set(extracted) | {k for k in meta if k.startswith("_") and k != "_entity_tier"}
    for key in sorted(managed_keys):
        if not key.startswith("_") or key == "_entity_tier":
            continue
        existing = {str(v) for v in (meta.get(key) or [])}
        incoming = extracted.get(key, set())
        if prune:
            final = incoming  # rebuild from scratch — only matched edges survive
        else:
            final = existing | incoming  # additive: user edges + extracted edges
        for v in sorted(final - existing):
            added.append(f"{key}:{v}")
        for v in sorted(existing - final):
            removed.append(f"{key}:{v}")
        for v in sorted(existing & final):
            unchanged.append(f"{key}:{v}")
        if final:
            meta[key] = sorted(final)
        elif key in meta:
            del meta[key]

    write_frontmatter(path, meta, body)
    return {"added": added, "removed": removed, "unchanged": unchanged}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/auto-test-pytest shared-vault/skills/graph/augur/tests/test_edge_writer.py`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add shared-vault/skills/graph/scripts/edge_writer.py shared-vault/skills/graph/augur/tests/test_edge_writer.py
git commit -m "feat(graph): additive per-type frontmatter edge writer (ADR-738)"
```

## Task 6: JSONL cache — `graph_cache.py`

**Files:**
- Create: `shared-vault/skills/graph/scripts/graph_cache.py`
- Test: `shared-vault/skills/graph/augur/tests/test_graph_cache.py`

- [ ] **Step 1: Write the failing test** (prepend the Shared Test Harness loader block)

```python
def test_cache_roundtrip_and_rebuild(tmp_path: Path, monkeypatch) -> None:
    ex = _load("edge_extractor", "edge_extractor.py")
    gc = _load("graph_cache", "graph_cache.py")
    cache_dir = tmp_path / "graph"
    monkeypatch.setattr(gc, "_cache_dir", lambda: cache_dir)

    edges = [
        ex.Edge("note-a", "RRF", "mentions"),
        ex.Edge("note-b", "RRF", "cites"),
    ]
    gc.write_edges(edges)
    loaded = gc.load_edges()
    assert {(e.src, e.dst, e.type) for e in loaded} == {
        ("note-a", "RRF", "mentions"), ("note-b", "RRF", "cites")
    }
    # edges.jsonl is plain JSONL — one record per line
    lines = (cache_dir / "edges.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["type"] in {"mentions", "cites"}

    # meta.json records the count
    meta = json.loads((cache_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta["edge_count"] == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/auto-test-pytest shared-vault/skills/graph/augur/tests/test_graph_cache.py`
Expected: FAIL — `graph_cache.py` does not exist.

- [ ] **Step 3: Write `graph_cache.py`**

```python
"""File-first rebuildable cache for the typed knowledge graph (ADR-738).

edges.jsonl + entities.jsonl + meta.json under get_cache_dir()/graph/. Fully
rebuildable from vault frontmatter; deleting it loses nothing. No database.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from edge_extractor import Edge  # sibling import


def _cache_dir() -> Path:
    from src.config.paths import get_cache_dir

    d = get_cache_dir() / "graph"
    d.mkdir(parents=True, exist_ok=True)
    return d


def write_edges(edges: Iterable[Edge]) -> Path:
    """Replace edges.jsonl with the given edge set and refresh meta.json."""
    edges = list(edges)
    cache = _cache_dir()
    edges_path = cache / "edges.jsonl"
    with edges_path.open("w", encoding="utf-8") as fh:
        for e in edges:
            fh.write(json.dumps({"src": e.src, "dst": e.dst, "type": e.type}) + "\n")
    (cache / "meta.json").write_text(
        json.dumps(
            {
                "rebuilt_at": datetime.now(timezone.utc).isoformat(),
                "edge_count": len(edges),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return edges_path


def load_edges() -> list[Edge]:
    """Load all edges from edges.jsonl (empty list if the cache is absent)."""
    edges_path = _cache_dir() / "edges.jsonl"
    if not edges_path.exists():
        return []
    out: list[Edge] = []
    for line in edges_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        out.append(Edge(rec["src"], rec["dst"], rec["type"]))
    return out


def write_entities(entities: list[dict[str, Any]]) -> Path:
    """Replace entities.jsonl with the given entity records."""
    entities_path = _cache_dir() / "entities.jsonl"
    with entities_path.open("w", encoding="utf-8") as fh:
        for ent in entities:
            fh.write(json.dumps(ent) + "\n")
    return entities_path


def load_entities() -> list[dict[str, Any]]:
    """Load all entity records from entities.jsonl."""
    entities_path = _cache_dir() / "entities.jsonl"
    if not entities_path.exists():
        return []
    return [
        json.loads(line)
        for line in entities_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/auto-test-pytest shared-vault/skills/graph/augur/tests/test_graph_cache.py`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
git add shared-vault/skills/graph/scripts/graph_cache.py shared-vault/skills/graph/augur/tests/test_graph_cache.py
git commit -m "feat(graph): file-first JSONL edge cache (ADR-738)"
```

---

# Phase 3 — Entity Tiering

## Task 7: Entity tiering — `entity_tier.py`

**Files:**
- Create: `shared-vault/skills/graph/scripts/entity_tier.py`
- Test: `shared-vault/skills/graph/augur/tests/test_entity_tier.py`

- [ ] **Step 1: Write the failing test** (prepend the Shared Test Harness loader block)

```python
def test_tier_thresholds_at_boundaries() -> None:
    er = _load("edge_rules", "edge_rules.py")
    ex = _load("edge_extractor", "edge_extractor.py")
    et = _load("entity_tier", "entity_tier.py")
    rs = er.RuleSet(
        edge_types={},
        tiers={"tier_1": {"min_inbound": 10, "min_source_types": 3},
               "tier_2": {"min_inbound": 3, "min_source_types": 1}},
    )
    # source_types maps each src page to its type
    src_types = {f"s{i}": ("url" if i < 4 else "memory" if i < 8 else "concept")
                 for i in range(12)}
    # 10 inbound across 3 source types -> Tier 1
    edges = [ex.Edge(f"s{i}", "hot", "mentions") for i in range(10)]
    assert et.compute_tier("hot", edges, src_types, rs) == 1
    # 3 inbound, 1 source type -> Tier 2
    edges = [ex.Edge(f"s{i}", "warm", "mentions") for i in range(3)]
    assert et.compute_tier("warm", edges, src_types, rs) == 2
    # 2 inbound -> Tier 3
    edges = [ex.Edge(f"s{i}", "cold", "mentions") for i in range(2)]
    assert et.compute_tier("cold", edges, src_types, rs) == 3


def test_recompute_all_returns_tier_per_entity() -> None:
    er = _load("edge_rules", "edge_rules.py")
    ex = _load("edge_extractor", "edge_extractor.py")
    et = _load("entity_tier", "entity_tier.py")
    rs = er.RuleSet(edge_types={}, tiers={"tier_2": {"min_inbound": 3, "min_source_types": 1}})
    edges = [ex.Edge(f"s{i}", "warm", "mentions") for i in range(3)]
    src_types = {f"s{i}": "url" for i in range(3)}
    tiers = et.recompute_all(edges, src_types, rs)
    assert tiers["warm"] == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/auto-test-pytest shared-vault/skills/graph/augur/tests/test_entity_tier.py`
Expected: FAIL — `entity_tier.py` does not exist.

- [ ] **Step 3: Write `entity_tier.py`**

```python
"""Deterministic entity tiering for the typed knowledge graph (ADR-738).

_entity_tier in {1, 2, 3}, computed from inbound-edge count and the diversity of
source-page types. Named distinctly from wiki_tier.py's signal-source tiers.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable

from edge_extractor import Edge  # sibling import
from edge_rules import RuleSet


def _inbound(entity: str, edges: Iterable[Edge], src_types: dict[str, str]) -> tuple[int, int]:
    """Return (inbound_count, distinct_source_type_count) for one entity."""
    srcs = {e.src for e in edges if e.dst == entity}
    types = {src_types.get(s, "unknown") for s in srcs}
    return len(srcs), len(types)


def compute_tier(
    entity: str, edges: Iterable[Edge], src_types: dict[str, str], ruleset: RuleSet
) -> int:
    """Compute the 1-3 tier for one entity. Higher tier number = less connected."""
    edges = list(edges)
    count, type_count = _inbound(entity, edges, src_types)
    t1 = ruleset.tiers.get("tier_1", {})
    t2 = ruleset.tiers.get("tier_2", {})
    if t1 and count >= t1.get("min_inbound", 10) and type_count >= t1.get("min_source_types", 3):
        return 1
    if t2 and count >= t2.get("min_inbound", 3) and type_count >= t2.get("min_source_types", 1):
        return 2
    return 3


def recompute_all(
    edges: Iterable[Edge], src_types: dict[str, str], ruleset: RuleSet
) -> dict[str, int]:
    """Compute tiers for every entity that appears as an edge destination."""
    edges = list(edges)
    by_dst: dict[str, list[Edge]] = defaultdict(list)
    for e in edges:
        by_dst[e.dst].append(e)
    return {
        entity: compute_tier(entity, by_dst[entity], src_types, ruleset)
        for entity in by_dst
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/auto-test-pytest shared-vault/skills/graph/augur/tests/test_entity_tier.py`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add shared-vault/skills/graph/scripts/entity_tier.py shared-vault/skills/graph/augur/tests/test_entity_tier.py
git commit -m "feat(graph): deterministic entity tiering (ADR-738)"
```

---

# Phase 4 — Query Layer + Orchestrator + MCP/CLI

## Task 8: Query layer — `graph_query.py`

**Files:**
- Create: `shared-vault/skills/graph/scripts/graph_query.py`
- Test: `shared-vault/skills/graph/augur/tests/test_graph_query.py`

- [ ] **Step 1: Write the failing test** (prepend the Shared Test Harness loader block)

```python
def test_query_by_type_entity_and_neighbors(tmp_path: Path, monkeypatch) -> None:
    ex = _load("edge_extractor", "edge_extractor.py")
    gc = _load("graph_cache", "graph_cache.py")
    gq = _load("graph_query", "graph_query.py")
    monkeypatch.setattr(gc, "_cache_dir", lambda: tmp_path / "graph")
    gc.write_edges([
        ex.Edge("note-a", "RRF", "mentions"),
        ex.Edge("note-a", "BM25", "depends_on"),
        ex.Edge("note-b", "RRF", "cites"),
    ])
    assert {e.src for e in gq.query(edge_type="cites")} == {"note-b"}
    # everything touching RRF (as src or dst)
    touching = gq.query(entity="RRF")
    assert {(e.src, e.type) for e in touching} == {("note-a", "mentions"), ("note-b", "cites")}
    # neighbors_of returns the dst ids reachable from a src
    assert set(gq.neighbors_of("note-a")) == {"RRF", "BM25"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/auto-test-pytest shared-vault/skills/graph/augur/tests/test_graph_query.py`
Expected: FAIL — `graph_query.py` does not exist.

- [ ] **Step 3: Write `graph_query.py`**

```python
"""Query layer over the typed knowledge graph cache (ADR-738).

Read-only. Loads edges.jsonl and filters in memory — the graph is small enough
that a linear scan is correct and fast. No query language; richer access is via
the MCP tools, never a query engine (spec Non-Goals).
"""
from __future__ import annotations

from collections import Counter
from typing import Any

import graph_cache  # sibling import
from edge_extractor import Edge


def query(
    *, edge_type: str | None = None, entity: str | None = None
) -> list[Edge]:
    """Return edges filtered by type and/or entity (entity matches src OR dst)."""
    edges = graph_cache.load_edges()
    if edge_type is not None:
        edges = [e for e in edges if e.type == edge_type]
    if entity is not None:
        edges = [e for e in edges if e.src == entity or e.dst == entity]
    return edges


def neighbors_of(entity: str) -> list[str]:
    """Return the distinct dst ids of every edge originating at `entity`."""
    return sorted({e.dst for e in graph_cache.load_edges() if e.src == entity})


def stats() -> dict[str, Any]:
    """Aggregate counts for graph-stats: totals, per-type, tier distribution, dangling."""
    edges = graph_cache.load_edges()
    entities = graph_cache.load_entities()
    all_ids = {e.src for e in edges} | {e.dst for e in edges}
    known_ids = {ent["id"] for ent in entities}
    dangling = sorted(d for d in {e.dst for e in edges} if d not in known_ids and d not in all_ids)
    return {
        "edge_count": len(edges),
        "entity_count": len(entities),
        "by_type": dict(Counter(e.type for e in edges)),
        "tier_distribution": dict(Counter(ent.get("tier", 3) for ent in entities)),
        "dangling_targets": dangling,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/auto-test-pytest shared-vault/skills/graph/augur/tests/test_graph_query.py`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
git add shared-vault/skills/graph/scripts/graph_query.py shared-vault/skills/graph/augur/tests/test_graph_query.py
git commit -m "feat(graph): read-only graph query layer (ADR-738)"
```

## Task 9: Orchestrator — `graph_ops.py`

The single in-process entry point the write paths, MCP tools, and CLI all call —
`extract → merge → cache.update` for one page, plus `src_types` bookkeeping.

**Files:**
- Create: `shared-vault/skills/graph/scripts/graph_ops.py`
- Test: `shared-vault/skills/graph/augur/tests/test_graph_ops.py`

- [ ] **Step 1: Write the failing test** (prepend the Shared Test Harness loader block)

```python
def test_index_page_extracts_writes_and_caches(tmp_path: Path, monkeypatch) -> None:
    gc = _load("graph_cache", "graph_cache.py")
    go = _load("graph_ops", "graph_ops.py")
    monkeypatch.setattr(gc, "_cache_dir", lambda: tmp_path / "graph")
    monkeypatch.setattr(go, "_edge_config_path", lambda: tmp_path / "graph_edges.yaml")
    (tmp_path / "graph_edges.yaml").write_text(
        "edge_types: {mentions: {rules: [{kind: body_wikilink, scope: bare}]}}\n"
        "tiers: {tier_2: {min_inbound: 3, min_source_types: 1}}\n",
        encoding="utf-8",
    )
    page = tmp_path / "note.md"
    page.write_text("---\ntitle: Note\n---\n\nbody links [[RRF]]\n", encoding="utf-8")

    result = go.index_page(page, source_type="memory")

    from src.lib.frontmatter_utils import parse_frontmatter

    meta, _ = parse_frontmatter(page)
    assert meta["_mentions"] == ["[[RRF]]"]                 # frontmatter written
    assert result["diff"]["added"] == ["_mentions:[[RRF]]"]
    assert any(e.dst == "RRF" for e in gc.load_edges())      # cache updated
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/auto-test-pytest shared-vault/skills/graph/augur/tests/test_graph_ops.py`
Expected: FAIL — `graph_ops.py` does not exist.

- [ ] **Step 3: Write `graph_ops.py`**

```python
"""Orchestrator for the typed knowledge graph (ADR-738).

index_page() is the single entry point the /ingest, /wiki, /save, /ask, /profile
write paths call: extract -> merge frontmatter -> update cache. Also hosts the
CLI dispatch (`aug graph <verb>`). Errors NEVER raise into a write path.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import edge_extractor
import edge_writer
import graph_cache
import graph_query
from edge_rules import load_rules

logger = logging.getLogger("graph.ops")


def _edge_config_path() -> Path:
    from src.config.paths import get_project_root

    return get_project_root() / "config" / "system" / "graph_edges.yaml"


# In-memory src page-id -> source_type map, persisted alongside the cache so
# tiering can run without re-reading every page. Rebuilt fully by graph-rebuild.
def _src_types_path() -> Path:
    return graph_cache._cache_dir() / "src_types.json"


def _load_src_types() -> dict[str, str]:
    import json

    p = _src_types_path()
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def _save_src_types(src_types: dict[str, str]) -> None:
    import json

    _src_types_path().write_text(json.dumps(src_types, indent=2), encoding="utf-8")


def index_page(
    path: str | Path,
    *,
    source_type: str = "unknown",
    known: dict[str, Any] | None = None,
    prune: bool = False,
) -> dict[str, Any]:
    """Extract -> merge frontmatter -> update cache for one page. Never raises."""
    path = Path(path)
    try:
        ruleset = load_rules(_edge_config_path())
        edges = edge_extractor.extract(path, known=known, ruleset=ruleset)
        diff = edge_writer.merge(path, edges, prune=prune)

        # incremental cache update: drop this page's old edges, add the new ones
        page_id = path.stem
        kept = [e for e in graph_cache.load_edges() if e.src != page_id]
        graph_cache.write_edges(kept + edges)

        src_types = _load_src_types()
        src_types[page_id] = source_type
        _save_src_types(src_types)

        return {"page": page_id, "edges": len(edges), "diff": diff, "ok": True}
    except Exception as exc:  # noqa: BLE001 — a graph failure must not break a write
        logger.warning("graph.index_page failed for %s: %s", path, exc)
        return {"page": Path(path).stem, "ok": False, "error": str(exc)}


def recompute_tiers() -> dict[str, int]:
    """Recompute _entity_tier for every entity and refresh entities.jsonl."""
    import entity_tier

    ruleset = load_rules(_edge_config_path())
    edges = graph_cache.load_edges()
    src_types = _load_src_types()
    tiers = entity_tier.recompute_all(edges, src_types, ruleset)
    from collections import Counter

    inbound = Counter(e.dst for e in edges)
    graph_cache.write_entities(
        [
            {"id": eid, "tier": tier, "inbound_count": inbound.get(eid, 0)}
            for eid, tier in sorted(tiers.items())
        ]
    )
    return tiers


def run_cli(verb: str, args: Any) -> int:
    """Dispatch `aug graph <verb>`."""
    import json

    if verb == "extract":
        print(json.dumps(index_page(args.path, source_type=args.source_type or "unknown"), indent=2))
        return 0
    if verb == "query":
        edges = graph_query.query(edge_type=args.type, entity=args.entity)
        print(json.dumps([e.__dict__ for e in edges], indent=2))
        return 0
    if verb == "stats":
        print(json.dumps(graph_query.stats(), indent=2))
        return 0
    if verb == "tier-recompute":
        tiers = recompute_tiers()
        print(json.dumps({"entities": len(tiers)}, indent=2))
        return 0
    if verb == "rebuild":
        import graph_rebuild

        print(json.dumps(graph_rebuild.rebuild(prune=args.prune, dry_run=args.dry_run), indent=2))
        return 0
    print(json.dumps({"error": "unknown verb", "verb": verb}, indent=2))
    return 2
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/auto-test-pytest shared-vault/skills/graph/augur/tests/test_graph_ops.py`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
git add shared-vault/skills/graph/scripts/graph_ops.py shared-vault/skills/graph/augur/tests/test_graph_ops.py
git commit -m "feat(graph): index_page orchestrator + CLI dispatch (ADR-738)"
```

## Task 10: Backfill — `graph_rebuild.py`

**Files:**
- Create: `shared-vault/skills/graph/scripts/graph_rebuild.py`
- Test: `shared-vault/skills/graph/augur/tests/test_graph_rebuild.py`

- [ ] **Step 1: Write the failing test** (prepend the Shared Test Harness loader block)

```python
def test_rebuild_is_idempotent_and_dry_run_writes_nothing(tmp_path: Path, monkeypatch) -> None:
    gc = _load("graph_cache", "graph_cache.py")
    go = _load("graph_ops", "graph_ops.py")
    gr = _load("graph_rebuild", "graph_rebuild.py")
    vault = tmp_path / "vault"
    (vault / "wiki").mkdir(parents=True)
    (vault / "wiki" / "a.md").write_text("---\ntitle: A\n---\nlinks [[B]]\n", encoding="utf-8")
    monkeypatch.setattr(gc, "_cache_dir", lambda: tmp_path / "graph")
    monkeypatch.setattr(go, "_edge_config_path", lambda: tmp_path / "graph_edges.yaml")
    monkeypatch.setattr(gr, "_vault_dir", lambda: vault)
    (tmp_path / "graph_edges.yaml").write_text(
        "edge_types: {mentions: {rules: [{kind: body_wikilink, scope: bare}]}}\n"
        "tiers: {tier_2: {min_inbound: 3, min_source_types: 1}}\n",
        encoding="utf-8",
    )

    dry = gr.rebuild(dry_run=True)
    assert dry["pages_scanned"] == 1
    assert not (tmp_path / "graph" / "edges.jsonl").exists()   # dry run wrote nothing

    real = gr.rebuild()
    assert real["pages_scanned"] == 1
    assert real["edges_total"] == 1
    real2 = gr.rebuild()                                      # idempotent
    assert real2["edges_total"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/auto-test-pytest shared-vault/skills/graph/augur/tests/test_graph_rebuild.py`
Expected: FAIL — `graph_rebuild.py` does not exist.

- [ ] **Step 3: Write `graph_rebuild.py`**

```python
"""One-shot full-vault backfill for the typed knowledge graph (ADR-738).

Scans every markdown page under the vault, runs extract -> merge -> cache, then
recomputes tiers. Idempotent. `dry_run=True` reports without writing. `prune=True`
removes managed-key entries whose rule no longer matches. Zero LLM cost.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import edge_extractor
import edge_writer
import graph_cache
import graph_ops
from edge_rules import load_rules


def _vault_dir() -> Path:
    from src.config.paths import get_vault_dir

    return get_vault_dir()


# vault subdir -> source_type, matched by longest-prefix
_SOURCE_TYPE_BY_DIR = {
    "sources/urls": "url",
    "sources/files": "file",
    "memory/entries": "memory",
    "wiki/concepts": "concept",
    "wiki": "wiki",
    "profile": "profile",
}


def _source_type_for(rel: Path) -> str:
    s = rel.as_posix()
    for prefix, stype in sorted(_SOURCE_TYPE_BY_DIR.items(), key=lambda kv: -len(kv[0])):
        if s.startswith(prefix + "/") or s == prefix:
            return stype
    return "unknown"


def rebuild(*, prune: bool = False, dry_run: bool = False) -> dict[str, Any]:
    """Backfill the whole vault. Returns a summary diff."""
    vault = _vault_dir()
    ruleset = load_rules(graph_ops._edge_config_path())
    pages = sorted(vault.rglob("*.md"))

    all_edges: list[edge_extractor.Edge] = []
    src_types: dict[str, str] = {}
    added = removed = 0
    failures: list[str] = []

    for page in pages:
        try:
            stype = _source_type_for(page.relative_to(vault))
            edges = edge_extractor.extract(page, ruleset=ruleset)
            all_edges.extend(edges)
            src_types[page.stem] = stype
            if not dry_run:
                diff = edge_writer.merge(page, edges, prune=prune)
                added += len(diff["added"])
                removed += len(diff["removed"])
        except Exception as exc:  # noqa: BLE001 — partial graph is acceptable
            failures.append(f"{page}: {exc}")

    if not dry_run:
        graph_cache.write_edges(all_edges)
        graph_ops._save_src_types(src_types)
        graph_ops.recompute_tiers()

    return {
        "pages_scanned": len(pages),
        "edges_total": len(all_edges),
        "frontmatter_added": added,
        "frontmatter_removed": removed,
        "failures": failures,
        "dry_run": dry_run,
        "pruned": prune,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/auto-test-pytest shared-vault/skills/graph/augur/tests/test_graph_rebuild.py`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
git add shared-vault/skills/graph/scripts/graph_rebuild.py shared-vault/skills/graph/augur/tests/test_graph_rebuild.py
git commit -m "feat(graph): one-shot idempotent vault backfill (ADR-738)"
```

## Task 11: MCP tools + CLI subcommands

**Files:**
- Modify: `shared-vault/skills/graph/scripts/mcp/__init__.py` (replace the Task 1 stub)
- Modify: `config/system/capability_exposure.yaml`

- [ ] **Step 1: Replace `scripts/mcp/__init__.py`** with the real registration

Use the bootstrap header block + `scripts/`-on-`sys.path` block exactly as in
`shared-vault/skills/evals/scripts/mcp/__init__.py` (lines 19–48 there), then:

```python
import json
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

try:
    from src.mcp.augur_shared.annotations import tool_annotations
    from src.mcp.augur_shared.logging import get_entity_logger
except ImportError:  # pragma: no cover
    import logging as _logging

    def get_entity_logger(name: str):
        return _logging.getLogger(name)

    def tool_annotations(annotations: dict) -> dict:
        return annotations

logger = get_entity_logger("mcp.brain.graph")

_READ_ONLY = {"destructiveHint": False, "idempotentHint": True,
              "openWorldHint": False, "readOnlyHint": True}
_WRITE = {"destructiveHint": False, "idempotentHint": True,
          "openWorldHint": False, "readOnlyHint": False}


def register_tools(mcp: "FastMCP", mcp_tool_interceptor: Callable[..., Any], metrics: Any) -> None:
    """Register the 5 graph MCP tools (ADR-738)."""
    logger.info("Registering graph MCP tools...")

    @mcp.tool(name="graph-query",
              annotations=tool_annotations({"title": "Graph Query", **_READ_ONLY}))
    @mcp_tool_interceptor
    async def graph_query_tool(edge_type: str | None = None, entity: str | None = None) -> str:
        """Query typed edges by edge type and/or entity (matches src or dst)."""
        metrics.track_tool("graph_query", skill="graph")
        import graph_query as gq  # type: ignore[import-not-found]

        return json.dumps([e.__dict__ for e in gq.query(edge_type=edge_type, entity=entity)],
                          indent=2, default=str)

    @mcp.tool(name="graph-stats",
              annotations=tool_annotations({"title": "Graph Stats", **_READ_ONLY}))
    @mcp_tool_interceptor
    async def graph_stats_tool() -> str:
        """Return edge/entity counts, per-type counts, tier distribution, dangling targets."""
        metrics.track_tool("graph_stats", skill="graph")
        import graph_query as gq  # type: ignore[import-not-found]

        return json.dumps(gq.stats(), indent=2, default=str)

    @mcp.tool(name="graph-extract",
              annotations=tool_annotations({"title": "Graph Extract", **_WRITE}))
    @mcp_tool_interceptor
    async def graph_extract_tool(path: str, source_type: str = "unknown") -> str:
        """Run extract -> merge -> cache for one page (the manual/repair path)."""
        metrics.track_tool("graph_extract", skill="graph")
        import graph_ops as go  # type: ignore[import-not-found]

        return json.dumps(go.index_page(path, source_type=source_type), indent=2, default=str)

    @mcp.tool(name="entity-tier-recompute",
              annotations=tool_annotations({"title": "Entity Tier Recompute", **_WRITE}))
    @mcp_tool_interceptor
    async def entity_tier_recompute_tool() -> str:
        """Recompute _entity_tier across all entities and refresh entities.jsonl."""
        metrics.track_tool("entity_tier_recompute", skill="graph")
        import graph_ops as go  # type: ignore[import-not-found]

        return json.dumps({"entities": len(go.recompute_tiers())}, indent=2)

    @mcp.tool(name="graph-rebuild",
              annotations=tool_annotations({"title": "Graph Rebuild", **_WRITE}))
    @mcp_tool_interceptor
    async def graph_rebuild_tool(prune: bool = False, dry_run: bool = False) -> str:
        """One-shot full-vault backfill: extract -> merge -> cache -> recompute tiers."""
        metrics.track_tool("graph_rebuild", skill="graph")
        import graph_rebuild as gr  # type: ignore[import-not-found]

        return json.dumps(gr.rebuild(prune=prune, dry_run=dry_run), indent=2, default=str)

    logger.info("graph MCP tools registered (5 tools)")


def register_subcommands(subparsers) -> None:
    """Register `aug graph <verb>` (ADR-260)."""
    parser = subparsers.add_parser("graph", help="Typed knowledge graph — ADR-738")
    sub = parser.add_subparsers(dest="graph_verb")

    p_extract = sub.add_parser("extract", help="extract->merge->cache for one page")
    p_extract.add_argument("path")
    p_extract.add_argument("--source-type", dest="source_type")

    p_query = sub.add_parser("query", help="query typed edges")
    p_query.add_argument("--type", dest="type")
    p_query.add_argument("--entity", dest="entity")

    sub.add_parser("stats", help="edge/entity/tier counts")
    sub.add_parser("tier-recompute", help="recompute _entity_tier for all entities")

    p_rebuild = sub.add_parser("rebuild", help="one-shot full-vault backfill")
    p_rebuild.add_argument("--prune", action="store_true")
    p_rebuild.add_argument("--dry-run", dest="dry_run", action="store_true")

    parser.set_defaults(func=_run_graph_cli)


def _run_graph_cli(args, remaining) -> int:
    verb = getattr(args, "graph_verb", None)
    if not verb:
        print(json.dumps({"error": "no verb",
                          "verbs": ["extract", "query", "stats", "tier-recompute", "rebuild"]},
                         indent=2))
        return 2
    import graph_ops  # type: ignore[import-not-found]

    return graph_ops.run_cli(verb, args)


__all__ = ["register_tools", "register_subcommands"]
```

- [ ] **Step 2: Add capability-exposure entries**

Append to the `capabilities:` mapping in `config/system/capability_exposure.yaml`
(alphabetical position) — one block per tool, following the existing `mcp-tool:` entry shape:

```yaml
  mcp-tool:graph-extract:
    classification_status: approved
    export_to: [browse]
    management: generated
    owner_kind: augur
    preferred_client: shell
    primary_surface: cli
    scope: project
  mcp-tool:graph-query:
    classification_status: approved
    export_to: [browse]
    management: generated
    owner_kind: augur
    preferred_client: shell
    primary_surface: cli
    scope: project
  mcp-tool:graph-rebuild:
    classification_status: approved
    export_to: [browse]
    management: generated
    owner_kind: augur
    preferred_client: shell
    primary_surface: cli
    scope: project
  mcp-tool:graph-stats:
    classification_status: approved
    export_to: [browse]
    management: generated
    owner_kind: augur
    preferred_client: shell
    primary_surface: cli
    scope: project
  mcp-tool:entity-tier-recompute:
    classification_status: approved
    export_to: [browse]
    management: generated
    owner_kind: augur
    preferred_client: shell
    primary_surface: cli
    scope: project
```

- [ ] **Step 3: Verify MCP registration imports cleanly**

Run: `PYTHONPATH=shared-vault python3 -c "import importlib.util,sys; sys.path.insert(0,'shared-vault/skills/graph/scripts'); spec=importlib.util.spec_from_file_location('m','shared-vault/skills/graph/scripts/mcp/__init__.py'); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); print(sorted(m.__all__))"`
Expected: `['register_subcommands', 'register_tools']`

- [ ] **Step 4: Commit**

```bash
git add shared-vault/skills/graph/scripts/mcp/__init__.py config/system/capability_exposure.yaml
git commit -m "feat(graph): 5 MCP tools + aug graph CLI + capability exposure (ADR-738)"
```

---

# Phase 5 — Write-Path Integration

Each task wires one command's write path to call `graph_ops.index_page(...)`
*after* the page is written. The call is best-effort (`index_page` never raises)
so a graph failure can never break an `/ingest` or `/save`.

## Task 12: Wire `/ingest`

**Files:**
- Modify: `shared-vault/skills/ingest/scripts/source_cards.py:147` (after `write_vault_frontmatter`)
- Modify: `shared-vault/skills/ingest/scripts/url_ingest.py` (after `write_url_source_card`)
- Test: `shared-vault/skills/graph/augur/tests/test_integration_ingest.py`

- [ ] **Step 1: Write the failing test** (prepend the Shared Test Harness loader block)

```python
def test_ingest_helper_indexes_source_card(tmp_path: Path, monkeypatch) -> None:
    gc = _load("graph_cache", "graph_cache.py")
    go = _load("graph_ops", "graph_ops.py")
    monkeypatch.setattr(gc, "_cache_dir", lambda: tmp_path / "graph")
    monkeypatch.setattr(go, "_edge_config_path", lambda: tmp_path / "graph_edges.yaml")
    (tmp_path / "graph_edges.yaml").write_text(
        "edge_types: {mentions: {rules: [{kind: concept_hook},"
        " {kind: body_wikilink, scope: bare}]}}\n"
        "tiers: {tier_2: {min_inbound: 3, min_source_types: 1}}\n",
        encoding="utf-8",
    )
    card = tmp_path / "card.md"
    card.write_text("---\ntitle: A source\n---\n\nsummary\n", encoding="utf-8")
    # this is exactly the call source_cards.py / url_ingest.py make:
    result = go.index_page(card, source_type="url", known={"concepts": ["RRF", "BM25"]})
    assert result["ok"] and result["edges"] == 2
    assert {e.dst for e in gc.load_edges()} == {"RRF", "BM25"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/auto-test-pytest shared-vault/skills/graph/augur/tests/test_integration_ingest.py`
Expected: PASS already if Tasks 4/6/9 are done — but the *integration call sites do not exist yet*. This test pins the contract; Steps 3–4 add the real call sites.

- [ ] **Step 3: Add the call site in `source_cards.py`**

After line 147 (`write_vault_frontmatter(target, metadata, card_body)`), before `return target`:

```python
    # ADR-738 — emit typed edges as part of the source-card write.
    try:
        import sys as _sys
        _graph_scripts = str(
            Path(__file__).resolve().parents[3] / "graph" / "scripts"
        )
        if _graph_scripts not in _sys.path:
            _sys.path.insert(0, _graph_scripts)
        import graph_ops  # type: ignore[import-not-found]

        graph_ops.index_page(target, source_type="file")
    except Exception:  # noqa: BLE001 — graph is best-effort, never breaks ingest
        pass
```

- [ ] **Step 4: Add the call site in `url_ingest.py`**

In `write_url_source_card`, after the `write_vault_frontmatter` call, add the same
best-effort block but with `source_type="url"` and `known=` populated from the
concepts `url_ingest` already extracts (pass `known={"concepts": <extracted>}` when
available, else omit `known`).

- [ ] **Step 5: Run test + ingest regression**

Run: `/auto-test-pytest shared-vault/skills/graph/augur/tests/test_integration_ingest.py shared-vault/skills/ingest/augur/tests/`
Expected: PASS — graph integration test passes, no ingest regressions.

- [ ] **Step 6: Commit**

```bash
git add shared-vault/skills/ingest/scripts/source_cards.py shared-vault/skills/ingest/scripts/url_ingest.py shared-vault/skills/graph/augur/tests/test_integration_ingest.py
git commit -m "feat(graph): wire /ingest write path to typed-edge extraction (ADR-738)"
```

## Task 13: Wire `/wiki`, `/ask` + curation, `/save`, `/profile`

**Files:**
- Modify: `shared-vault/skills/ingest/scripts/wiki_concept_pages.py` (after concept-page write)
- Modify: `shared-vault/skills/ingest/scripts/ask_sync.py` (after memory-entry write — covers `/ask` retention AND the daily-log curation cycle, which share `ask_sync`'s writer)
- Modify: `shared-vault/skills/augur-core/commands/save.md` (`/save` is agent-orchestrated — no Python writer; integrate via the command doc per Rule #19)
- Modify: `shared-vault/skills/knowledge/scripts/mcp/tools_memory_profile.py` (after `profile-write`)
- Test: `shared-vault/skills/graph/augur/tests/test_integration_writers.py`

- [ ] **Step 1: Write the failing test** (prepend the Shared Test Harness loader block)

```python
import pytest


@pytest.mark.parametrize("source_type", ["concept", "memory", "profile"])
def test_index_page_contract_for_each_writer(tmp_path: Path, monkeypatch, source_type: str) -> None:
    gc = _load("graph_cache", "graph_cache.py")
    go = _load("graph_ops", "graph_ops.py")
    monkeypatch.setattr(gc, "_cache_dir", lambda: tmp_path / source_type)
    monkeypatch.setattr(go, "_edge_config_path", lambda: tmp_path / "graph_edges.yaml")
    (tmp_path / "graph_edges.yaml").write_text(
        "edge_types: {mentions: {rules: [{kind: body_wikilink, scope: bare}]}}\n"
        "tiers: {tier_2: {min_inbound: 3, min_source_types: 1}}\n",
        encoding="utf-8",
    )
    page = tmp_path / f"{source_type}.md"
    page.write_text(f"---\ntitle: {source_type}\n---\n\nlinks [[Target]]\n", encoding="utf-8")
    result = go.index_page(page, source_type=source_type)
    assert result["ok"]
    assert any(e.dst == "Target" for e in gc.load_edges())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/auto-test-pytest shared-vault/skills/graph/augur/tests/test_integration_writers.py`
Expected: PASS for the contract — but the four call sites do not exist yet. Steps 3–6 add them.

- [ ] **Step 3: Wire `/wiki`** — in `wiki_concept_pages.py`, after a concept page is
written to disk, add the same best-effort `graph_ops.index_page(path, source_type="concept")`
block used in Task 12 Step 3 (adjust the `parents[N]` depth to reach
`shared-vault/skills/graph/scripts`).

- [ ] **Step 4: Wire `/ask` + curation** — in `ask_sync.py`, after each memory entry
is written, call `graph_ops.index_page(path, source_type="memory", known={"concepts": <cited_sources>})`,
passing the cited-source ids `ask_sync` already has so `_cites:` is exact. The
daily-log curation cycle goes through this same writer — one call site covers both.

- [ ] **Step 5: Wire `/save`** — `/save` writes through the agent's file tools
(there is no Python writer to hook). Per Rule #19 (agents orchestrate, MCP owns
atomic ops), integrate via the command doc: add a step to `save.md`'s "What It
Does" + a line under "Rules" instructing the agent that, after a successful
markdown (`.md`) save, it MUST call the `graph-extract` MCP tool with the saved
path and `source_type=note`. Binary assets emit no edges.

- [ ] **Step 6: Wire `/profile`** — in `tools_memory_profile.py`, after `profile-write`
persists the profile note, call `graph_ops.index_page(path, source_type="profile")`.

- [ ] **Step 7: Run test + regressions**

Run: `/auto-test-pytest shared-vault/skills/graph/augur/tests/ shared-vault/skills/ingest/augur/tests/ shared-vault/skills/knowledge/augur/tests/`
Expected: PASS — all graph tests + no ingest/knowledge regressions.

- [ ] **Step 8: Commit**

```bash
git add shared-vault/skills/ingest/scripts/wiki_concept_pages.py shared-vault/skills/ingest/scripts/ask_sync.py shared-vault/skills/augur-core/commands/save.md shared-vault/skills/knowledge/scripts/mcp/tools_memory_profile.py shared-vault/skills/graph/augur/tests/test_integration_writers.py
git commit -m "feat(graph): wire /wiki /ask /save /profile write paths (ADR-738)"
```

---

# Phase 6 — Supersede the `knowledge-graph` Stub

## Task 14: Deprecate `knowledge-graph` in favor of `graph-stats`

**Files:**
- Modify: `shared-vault/skills/knowledge/scripts/mcp/rag_search.py:165-245` (the `knowledge-graph` tool)
- Modify: `config/system/capability_exposure.yaml` (the `mcp-tool:knowledge-graph` entry)

- [ ] **Step 1: Write the failing test**

Add to `shared-vault/skills/knowledge/augur/tests/` a test asserting the
`knowledge-graph` tool's returned JSON now carries `"deprecated": true` and a
`"superseded_by": "graph-stats"` pointer (use the same importlib loader convention).

- [ ] **Step 2: Run test to verify it fails**

Run: `/auto-test-pytest shared-vault/skills/knowledge/augur/tests/`
Expected: FAIL — the tool does not yet return the deprecation fields.

- [ ] **Step 3: Edit `knowledge_graph_tool`** in `rag_search.py` — replace the
`_get_graph_stats` body so it returns:

```python
            return {
                "success": True,
                "deprecated": True,
                "superseded_by": "graph-stats",
                "message": "knowledge-graph is superseded by the graph skill's "
                           "graph-stats tool (ADR-738). Call graph-stats for typed "
                           "edge/entity/tier statistics.",
                "stats": stats,  # legacy RAG-manifest counts, kept for one release
            }
```

Per Rule #14 (canonical cleanup, no long-lived shims): this is a one-release
deprecation pointer, not a permanent alias.

- [ ] **Step 4: Update the capability entry** — in `capability_exposure.yaml`, set
the `mcp-tool:knowledge-graph` entry's `classification_status` to `deprecated`.

- [ ] **Step 5: Run test to verify it passes**

Run: `/auto-test-pytest shared-vault/skills/knowledge/augur/tests/`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add shared-vault/skills/knowledge/scripts/mcp/rag_search.py config/system/capability_exposure.yaml shared-vault/skills/knowledge/augur/tests/
git commit -m "refactor(knowledge): deprecate knowledge-graph stub for graph-stats (ADR-738)"
```

---

# Phase 7 — Docs + Regeneration + Final Validation

## Task 15: Topic docs + agent-instruction regeneration

**Files:**
- Modify: `docs/agent-topics/SKILLS.md` (document the typed-edge + per-type-key convention)
- Modify: `CLAUDE.md` capability table (regenerated, not hand-edited)

- [ ] **Step 1: Update `SKILLS.md`** — add a "Typed knowledge graph (ADR-738)"
subsection: the `graph/` skill owns deterministic typed edges; edges are per-type
underscore-prefixed frontmatter link lists (`_cites:`, `_mentions:`, …) that
augment — never replace — the untyped `RelationshipIndex`; the five write paths
(`/ingest`, `/wiki`, `/save`, `/ask`+curation, `/profile`) emit edges at write time;
`_entity_tier` (1–3) is distinct from `wiki_tier.py`'s signal-source tiers.

- [ ] **Step 2: Regenerate agent instructions + capability table**

Run: `PYTHONPATH=shared-vault python3 -m skills.ai.scripts.sync_agents sync agents all`
Expected: regenerates `CLAUDE.md` (and per-client surfaces) with the 5 new
`mcp-tool:graph-*` rows in the capability table.

- [ ] **Step 3: Commit**

```bash
git add docs/agent-topics/SKILLS.md CLAUDE.md AGENTS.md .claude/ .codex/ .gemini/
git commit -m "docs(graph): document typed-edge convention + regenerate surfaces (ADR-738)"
```

## Task 16: Full validation gate

- [ ] **Step 1: Full graph test suite**

Run: `/auto-test-pytest shared-vault/skills/graph/augur/tests/`
Expected: PASS — all 11 test files green.

- [ ] **Step 2: Regression — ingest + knowledge suites**

Run: `/auto-test-pytest shared-vault/skills/ingest/augur/tests/ shared-vault/skills/knowledge/augur/tests/`
Expected: PASS — no regressions from the write-path wiring.

- [ ] **Step 3: Lint**

Run: `/auto-lint`
Expected: clean — no new lint findings in `shared-vault/skills/graph/` or the modified write-path files.

- [ ] **Step 4: End-to-end backfill smoke**

Run: `PYTHONPATH=shared-vault python3 -c "import sys; sys.path.insert(0,'shared-vault/skills/graph/scripts'); import graph_rebuild; print(graph_rebuild.rebuild(dry_run=True))"`
Expected: a summary dict with `pages_scanned > 0`, `edges_total >= 0`, `failures: []`, `dry_run: true` — and **no frontmatter written** (dry run).

- [ ] **Step 5: Verify the seed config + tools are discoverable**

Run: `aug graph stats`
Expected: JSON with `edge_count`, `entity_count`, `by_type`, `tier_distribution`,
`dangling_targets` (zeros are fine before a real rebuild).

- [ ] **Step 6: Confirm no DB, no LLM call introduced**

Run: `grep -rnE "sqlite|pglite|lancedb|openai|anthropic|llm_call|generate\(" shared-vault/skills/graph/scripts/ || echo "clean"`
Expected: `clean` — the skill is file-first and zero-LLM by construction.

---

## Completion Checklist (maps to ADR-738 Completion Gates)

- [ ] All 8 graph modules written, no orphan code
- [ ] Five write paths call `graph_ops.index_page` — verified by integration tests
- [ ] `config/system/graph_edges.yaml` seeded; `capability_exposure.yaml` has 5 entries
- [ ] Every plan test case green; ingest + knowledge suites green (no regressions)
- [ ] `knowledge-graph` stub returns the deprecation pointer; zero permanent shims
- [ ] `SKILLS.md` documents the convention; agent instructions regenerated
- [ ] Backfill dry-run smoke passes; `grep` confirms no DB / no LLM call
- [ ] `superpowers:verification-before-completion` run before declaring done
```
