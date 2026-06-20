# Memory Synthesis Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the wiki compounding engine the single auto-synthesis engine in Augur per `docs/superpowers/specs/2026-05-11-memory-synthesis-consolidation-design.md`. Introduce a user-configurable wiki query registry. Retire the deterministic regex `profile_generator.py` pipeline. Migrate `HUMAN_API.md` from regex-derived YAML-frontmatter at `runtime/memory/HUMAN_API.md` to native-agent-synthesized H2-section markdown at `vault/wiki/profile-human-api.md`, with field-set parity for `context_injector`. Add `/brain/wiki` dashboard page and a `memory` Browse category. Big-bang cutover in one PR.

**Architecture:** Nine checkpoints, ~30 tasks. C1–C2 build the registry + runner. C3 ships the MCP tools. C4 seeds defaults and runs the in-PR A/B equivalence test (the only hot-path safety gate). C5 swaps consumers. C6 builds the dashboard. C7 wires Browse. C8 retires legacy. C9 final verification.

**Tech Stack:** Python 3.11+ (PyYAML, dataclasses, subprocess for git, agent handoff + MCP validation), Next.js 16 + TypeScript + Vitest for dashboard. No new runtime deps.

**Spec:** `docs/superpowers/specs/2026-05-11-memory-synthesis-consolidation-design.md`

---

## Boundary rules (apply to every task)

- **Auto-loops only.** Tests run via `/auto-test-pytest` / `/auto-test-dashboard`; lint via `/auto-lint`; never raw `pytest` or `pnpm test` per CLAUDE.md rule 29.
- **MCP-only data flow in dashboard.** No `fs`, no `spawn`, no direct Python — all data via `POST /api/mcp/tool` per CLAUDE.md rule 11.
- **Native-agent LLM boundary.** Augur is the harness. MCP tools prepare handoffs and validate/apply results; native AI clients provide synthesis. Direct model/API calls require a separately approved exception.
- **Browser verification for UI tasks.** Per CLAUDE.md rule 28, dashboard changes require client-side load verification, not just curl/SSR.
- **Path helpers.** No hardcoded paths. Use `src.config.paths` for project/vault/runtime/cache locations per CLAUDE.md rule 3.
- **Plugin decentralization.** New wiki query files live in `shared-vault/skills/ingest/`; new dashboard files in `apps/dashboard/features/pages/brain/wiki/`; per CLAUDE.md rule 2.
- **TODO_OUTDATED markers** for any architectural gap discovered during implementation; do NOT silently expand scope.
- **Commit after every passing task.** Small focused commits per CLAUDE.md rule 10.

After every commit, run the relevant test files. Task 30 runs full integration + browser verification per rule 28.

---

## C1 — Wiki query registry foundation

### Task 1: Query registry schema + YAML loader

**Files:**
- Create: `shared-vault/skills/ingest/scripts/wiki_query_registry.py`
- Test: `tests/wiki/test_query_registry.py`

The registry module owns:
- Loading `vault/wiki/queries.yaml` (path via `get_vault_dir() / "wiki" / "queries.yaml"`)
- Schema validation
- CRUD operations (load_query, list_queries, write_query, delete_query)
- Source-kind enum (`memory_md`, `daily_logs`, `ask_retention`, `adr_index`, `git_recent_commits`, `inbox`, `linked_folder`)

- [ ] **Step 1: Write failing tests**

```python
# tests/wiki/test_query_registry.py
from pathlib import Path
import pytest
import yaml

from shared_vault.skills.ingest.scripts.wiki_query_registry import (
    load_registry,
    list_queries,
    write_query,
    delete_query,
    validate_query_spec,
    QueryRegistryError,
    SOURCE_KINDS,
)


def test_source_kinds_closed_enum():
    assert SOURCE_KINDS == frozenset({
        "memory_md", "daily_logs", "ask_retention",
        "adr_index", "git_recent_commits", "inbox", "linked_folder",
    })


def test_validate_minimal_valid_query():
    spec = {
        "title": "Test query",
        "description": "test",
        "prompt_template": "Synthesize from {{sources}}",
        "sources": [{"kind": "memory_md"}],
        "output": "vault/wiki/test.md",
        "page_type": "query",
        "required_sections": ["Result"],
        "refresh_policy": "manual",
    }
    validate_query_spec("test", spec)  # no raise


def test_validate_rejects_unknown_source_kind():
    spec = {
        "title": "Test",
        "description": "test",
        "prompt_template": "x",
        "sources": [{"kind": "INVALID_KIND"}],
        "output": "vault/wiki/test.md",
        "page_type": "query",
        "required_sections": ["Result"],
        "refresh_policy": "manual",
    }
    with pytest.raises(QueryRegistryError, match="unknown source kind"):
        validate_query_spec("test", spec)


def test_validate_rejects_non_manual_refresh_policy_in_v1():
    spec = {
        "title": "Test",
        "description": "test",
        "prompt_template": "x",
        "sources": [{"kind": "memory_md"}],
        "output": "vault/wiki/test.md",
        "page_type": "query",
        "required_sections": ["Result"],
        "refresh_policy": "weekly",  # reserved but not yet supported
    }
    with pytest.raises(QueryRegistryError, match="refresh_policy"):
        validate_query_spec("test", spec)


def test_load_empty_registry(tmp_path, monkeypatch):
    monkeypatch.setenv("AUGUR_VAULT", str(tmp_path))
    registry = load_registry()
    assert registry == {"version": 1, "queries": {}}


def test_write_query_and_reload(tmp_path, monkeypatch):
    monkeypatch.setenv("AUGUR_VAULT", str(tmp_path))
    spec = {
        "title": "Test query",
        "description": "test",
        "prompt_template": "Synthesize from {{sources}}",
        "sources": [{"kind": "memory_md"}],
        "output": "vault/wiki/test.md",
        "page_type": "query",
        "required_sections": ["Result"],
        "refresh_policy": "manual",
    }
    write_query("test", spec)
    queries = list_queries()
    assert "test" in queries
    assert queries["test"]["title"] == "Test query"


def test_delete_query_removes_from_yaml(tmp_path, monkeypatch):
    monkeypatch.setenv("AUGUR_VAULT", str(tmp_path))
    spec = {
        "title": "Test", "description": "x", "prompt_template": "x",
        "sources": [{"kind": "memory_md"}], "output": "vault/wiki/t.md",
        "page_type": "query", "required_sections": ["R"], "refresh_policy": "manual",
    }
    write_query("test", spec)
    assert "test" in list_queries()
    delete_query("test")
    assert "test" not in list_queries()


def test_validate_rejects_output_outside_vault_wiki(tmp_path, monkeypatch):
    monkeypatch.setenv("AUGUR_VAULT", str(tmp_path))
    spec = {
        "title": "T", "description": "x", "prompt_template": "x",
        "sources": [{"kind": "memory_md"}],
        "output": "../../etc/passwd",  # path traversal attempt
        "page_type": "query", "required_sections": ["R"], "refresh_policy": "manual",
    }
    with pytest.raises(QueryRegistryError, match="output path must be under vault/wiki/"):
        validate_query_spec("test", spec)


def test_validate_rejects_duplicate_output_path(tmp_path, monkeypatch):
    monkeypatch.setenv("AUGUR_VAULT", str(tmp_path))
    spec_a = {
        "title": "A", "description": "x", "prompt_template": "x",
        "sources": [{"kind": "memory_md"}], "output": "vault/wiki/same.md",
        "page_type": "query", "required_sections": ["R"], "refresh_policy": "manual",
    }
    spec_b = {**spec_a, "title": "B"}
    write_query("a", spec_a)
    with pytest.raises(QueryRegistryError, match="output path already claimed"):
        write_query("b", spec_b)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/auto-test-pytest --target tests/wiki/test_query_registry.py`
Expected: All 7 tests FAIL with `ImportError` (module not yet created).

- [ ] **Step 3: Implement `wiki_query_registry.py`**

```python
# shared-vault/skills/ingest/scripts/wiki_query_registry.py
"""User-configurable wiki query registry.

Stores queries at <vault>/wiki/queries.yaml. Each query declares title,
prompt_template, sources, output path, required sections, and refresh policy.

Source kinds are a closed enum — new kinds require a code change in
wiki_query_sources/ + this module's SOURCE_KINDS.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from src.config.paths import get_vault_dir


SOURCE_KINDS = frozenset({
    "memory_md", "daily_logs", "ask_retention",
    "adr_index", "git_recent_commits", "inbox", "linked_folder",
})

SUPPORTED_REFRESH_POLICIES = frozenset({"manual"})  # weekly / on-source-change reserved


class QueryRegistryError(ValueError):
    """Raised when a query spec fails validation or registry I/O errors."""


def _registry_path() -> Path:
    return get_vault_dir() / "wiki" / "queries.yaml"


def _ensure_parent() -> None:
    _registry_path().parent.mkdir(parents=True, exist_ok=True)


def load_registry() -> dict[str, Any]:
    path = _registry_path()
    if not path.exists():
        return {"version": 1, "queries": {}}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise QueryRegistryError(f"queries.yaml root must be a mapping, got {type(raw).__name__}")
    raw.setdefault("version", 1)
    raw.setdefault("queries", {})
    return raw


def list_queries() -> dict[str, dict]:
    return load_registry()["queries"]


def validate_query_spec(query_id: str, spec: dict, *, existing: dict[str, dict] | None = None) -> None:
    required_keys = {"title", "description", "prompt_template", "sources", "output",
                     "page_type", "required_sections", "refresh_policy"}
    missing = required_keys - set(spec)
    if missing:
        raise QueryRegistryError(f"query '{query_id}' missing keys: {sorted(missing)}")

    if spec["page_type"] != "query":
        raise QueryRegistryError(f"page_type must be 'query', got {spec['page_type']!r}")

    if spec["refresh_policy"] not in SUPPORTED_REFRESH_POLICIES:
        raise QueryRegistryError(
            f"refresh_policy must be one of {sorted(SUPPORTED_REFRESH_POLICIES)}; "
            f"got {spec['refresh_policy']!r}"
        )

    sources = spec["sources"]
    if not isinstance(sources, list) or not sources:
        raise QueryRegistryError(f"query '{query_id}' sources must be a non-empty list")
    for src in sources:
        kind = src.get("kind")
        if kind not in SOURCE_KINDS:
            raise QueryRegistryError(f"unknown source kind: {kind!r}")

    output = str(spec["output"])
    if not output.startswith("vault/wiki/") or ".." in output:
        raise QueryRegistryError(
            f"output path must be under vault/wiki/ (got {output!r})"
        )

    required_sections = spec["required_sections"]
    if not isinstance(required_sections, list) or not required_sections:
        raise QueryRegistryError("required_sections must be a non-empty list")

    # Uniqueness check
    others = existing if existing is not None else load_registry()["queries"]
    for other_id, other_spec in others.items():
        if other_id == query_id:
            continue
        if other_spec.get("output") == output:
            raise QueryRegistryError(
                f"output path already claimed by query '{other_id}'"
            )


def write_query(query_id: str, spec: dict) -> Path:
    _ensure_parent()
    registry = load_registry()
    validate_query_spec(query_id, spec, existing=registry["queries"])
    registry["queries"][query_id] = spec
    path = _registry_path()
    path.write_text(
        yaml.safe_dump(registry, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return path


def delete_query(query_id: str) -> bool:
    registry = load_registry()
    if query_id not in registry["queries"]:
        return False
    del registry["queries"][query_id]
    _registry_path().write_text(
        yaml.safe_dump(registry, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return True


def read_query(query_id: str) -> dict | None:
    return load_registry()["queries"].get(query_id)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/auto-test-pytest --target tests/wiki/test_query_registry.py`
Expected: All 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add shared-vault/skills/ingest/scripts/wiki_query_registry.py tests/wiki/test_query_registry.py
git commit -m "feat(wiki-queries): registry schema + YAML loader + validation"
```

### Task 2: Source adapter framework + `memory_md` adapter

**Files:**
- Create: `shared-vault/skills/ingest/scripts/wiki_query_sources/__init__.py`
- Create: `shared-vault/skills/ingest/scripts/wiki_query_sources/base.py`
- Create: `shared-vault/skills/ingest/scripts/wiki_query_sources/memory_md.py`
- Test: `tests/wiki/sources/test_memory_md_adapter.py`

Adapter contract:
```python
class SourceAdapter(Protocol):
    kind: str  # matches SOURCE_KINDS
    def resolve(self, spec: dict, budget_tokens: int) -> SourceResult: ...

@dataclass
class SourceResult:
    text: str            # the concatenated content placed in the agent handoff
    citations: list[str] # file:line references for the Source Basis section
    truncated: bool      # True if budget caused tail-truncation
```

- [ ] **Step 1: Write failing tests**

```python
# tests/wiki/sources/test_memory_md_adapter.py
from pathlib import Path
import pytest

from shared_vault.skills.ingest.scripts.wiki_query_sources import (
    MemoryMdAdapter, SourceResult,
)


def test_adapter_kind_matches_registry():
    adapter = MemoryMdAdapter()
    assert adapter.kind == "memory_md"


def test_resolve_full_memory_md(tmp_path, monkeypatch):
    monkeypatch.setenv("AUGUR_VAULT", str(tmp_path))
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir()
    content = "## Decisions\n- 2026-05-01 decided X\n\n## Preferences\n- prefer Y\n"
    (memory_dir / "MEMORY.md").write_text(content, encoding="utf-8")

    adapter = MemoryMdAdapter()
    result = adapter.resolve({"kind": "memory_md"}, budget_tokens=10_000)

    assert isinstance(result, SourceResult)
    assert "## Decisions" in result.text
    assert "## Preferences" in result.text
    assert result.truncated is False
    assert any("MEMORY.md" in c for c in result.citations)


def test_resolve_section_filter(tmp_path, monkeypatch):
    monkeypatch.setenv("AUGUR_VAULT", str(tmp_path))
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir()
    content = "## Decisions\n- decided X\n\n## Preferences\n- prefer Y\n"
    (memory_dir / "MEMORY.md").write_text(content, encoding="utf-8")

    adapter = MemoryMdAdapter()
    result = adapter.resolve(
        {"kind": "memory_md", "section": "Decisions"},
        budget_tokens=10_000,
    )
    assert "decided X" in result.text
    assert "prefer Y" not in result.text


def test_resolve_missing_file_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("AUGUR_VAULT", str(tmp_path))
    adapter = MemoryMdAdapter()
    result = adapter.resolve({"kind": "memory_md"}, budget_tokens=10_000)
    assert result.text == ""
    assert result.citations == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/auto-test-pytest --target tests/wiki/sources/test_memory_md_adapter.py`
Expected: All 4 tests FAIL with `ImportError`.

- [ ] **Step 3: Implement adapter framework + memory_md**

```python
# shared-vault/skills/ingest/scripts/wiki_query_sources/__init__.py
from .base import SourceAdapter, SourceResult
from .memory_md import MemoryMdAdapter

__all__ = ["SourceAdapter", "SourceResult", "MemoryMdAdapter"]
```

```python
# shared-vault/skills/ingest/scripts/wiki_query_sources/base.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class SourceResult:
    text: str
    citations: list[str] = field(default_factory=list)
    truncated: bool = False


class SourceAdapter(Protocol):
    kind: str

    def resolve(self, spec: dict, budget_tokens: int) -> SourceResult:
        ...
```

```python
# shared-vault/skills/ingest/scripts/wiki_query_sources/memory_md.py
from __future__ import annotations
import re

from src.config.paths import get_vault_dir

from .base import SourceResult


def _approx_tokens(text: str) -> int:
    # ~4 chars per token rough estimate
    return max(1, len(text) // 4)


def _extract_section(content: str, title: str) -> str:
    pattern = rf"^## {re.escape(title)}\s*\n(.*?)(?=^## |\Z)"
    m = re.search(pattern, content, re.MULTILINE | re.DOTALL)
    return m.group(0) if m else ""


class MemoryMdAdapter:
    kind = "memory_md"

    def resolve(self, spec: dict, budget_tokens: int) -> SourceResult:
        path = get_vault_dir() / "memory" / "MEMORY.md"
        if not path.exists():
            return SourceResult(text="", citations=[], truncated=False)

        content = path.read_text(encoding="utf-8")
        section_filter = spec.get("section")
        if section_filter:
            content = _extract_section(content, section_filter)

        tokens = _approx_tokens(content)
        truncated = False
        if tokens > budget_tokens:
            # tail-truncate by lines
            lines = content.splitlines()
            keep: list[str] = []
            running = 0
            for line in reversed(lines):
                running += _approx_tokens(line + "\n")
                if running > budget_tokens:
                    break
                keep.append(line)
            content = "\n".join(reversed(keep))
            content = f"[... older content elided to fit budget ...]\n{content}"
            truncated = True

        citation = f"{path}:{len(content.splitlines())} lines"
        return SourceResult(text=content, citations=[citation], truncated=truncated)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/auto-test-pytest --target tests/wiki/sources/test_memory_md_adapter.py`
Expected: All 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add shared-vault/skills/ingest/scripts/wiki_query_sources/ tests/wiki/sources/test_memory_md_adapter.py
git commit -m "feat(wiki-queries): adapter framework + memory_md source"
```

### Task 3: `daily_logs` adapter

**Files:**
- Create: `shared-vault/skills/ingest/scripts/wiki_query_sources/daily_logs.py`
- Modify: `shared-vault/skills/ingest/scripts/wiki_query_sources/__init__.py`
- Test: `tests/wiki/sources/test_daily_logs_adapter.py`

Reads `vault/memory/daily/YYYY-MM-DD.md` files, filterable by `recent_days`. Tail-truncates per budget. Defaults: `recent_days=30`.

- [ ] **Step 1: Write failing tests**

```python
# tests/wiki/sources/test_daily_logs_adapter.py
from datetime import date, timedelta
from pathlib import Path
import pytest

from shared_vault.skills.ingest.scripts.wiki_query_sources import DailyLogsAdapter


def _seed_daily_logs(vault: Path, days: list[int]) -> None:
    daily = vault / "memory" / "daily"
    daily.mkdir(parents=True, exist_ok=True)
    today = date.today()
    for d in days:
        log_date = today - timedelta(days=d)
        (daily / f"{log_date.isoformat()}.md").write_text(
            f"# {log_date}\n## 10:00 - Decision\n- decided X on day -{d}\n",
            encoding="utf-8",
        )


def test_adapter_kind():
    assert DailyLogsAdapter().kind == "daily_logs"


def test_resolve_default_recent_days_30(tmp_path, monkeypatch):
    monkeypatch.setenv("AUGUR_VAULT", str(tmp_path))
    _seed_daily_logs(tmp_path, [0, 5, 35])  # today, 5 days ago, 35 days ago
    adapter = DailyLogsAdapter()
    result = adapter.resolve({"kind": "daily_logs"}, budget_tokens=10_000)
    assert "day -0" in result.text
    assert "day -5" in result.text
    assert "day -35" not in result.text  # outside default 30-day window


def test_resolve_explicit_recent_days(tmp_path, monkeypatch):
    monkeypatch.setenv("AUGUR_VAULT", str(tmp_path))
    _seed_daily_logs(tmp_path, [0, 10])
    adapter = DailyLogsAdapter()
    result = adapter.resolve({"kind": "daily_logs", "recent_days": 7}, budget_tokens=10_000)
    assert "day -0" in result.text
    assert "day -10" not in result.text


def test_resolve_empty_directory(tmp_path, monkeypatch):
    monkeypatch.setenv("AUGUR_VAULT", str(tmp_path))
    adapter = DailyLogsAdapter()
    result = adapter.resolve({"kind": "daily_logs"}, budget_tokens=10_000)
    assert result.text == ""
    assert result.citations == []


def test_resolve_citations_list_each_file(tmp_path, monkeypatch):
    monkeypatch.setenv("AUGUR_VAULT", str(tmp_path))
    _seed_daily_logs(tmp_path, [0, 1, 2])
    adapter = DailyLogsAdapter()
    result = adapter.resolve({"kind": "daily_logs"}, budget_tokens=10_000)
    assert len(result.citations) == 3
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/auto-test-pytest --target tests/wiki/sources/test_daily_logs_adapter.py`
Expected: All 4 tests FAIL with `ImportError`.

- [ ] **Step 3: Implement**

```python
# shared-vault/skills/ingest/scripts/wiki_query_sources/daily_logs.py
from __future__ import annotations
from datetime import date, timedelta
from pathlib import Path

from src.config.paths import get_vault_dir

from .base import SourceResult


def _approx_tokens(text: str) -> int:
    return max(1, len(text) // 4)


class DailyLogsAdapter:
    kind = "daily_logs"

    def resolve(self, spec: dict, budget_tokens: int) -> SourceResult:
        daily = get_vault_dir() / "memory" / "daily"
        if not daily.exists():
            return SourceResult(text="", citations=[], truncated=False)

        recent_days = int(spec.get("recent_days", 30))
        cutoff = date.today() - timedelta(days=recent_days)
        files = sorted(daily.glob("*.md"), reverse=True)  # newest first
        files = [
            f for f in files
            if _date_from_name(f) and _date_from_name(f) >= cutoff
        ]

        parts: list[str] = []
        citations: list[str] = []
        running_tokens = 0
        truncated = False
        for f in files:
            text = f.read_text(encoding="utf-8")
            block = f"=== {f.name} ===\n{text}\n"
            tokens = _approx_tokens(block)
            if running_tokens + tokens > budget_tokens:
                truncated = True
                break
            parts.append(block)
            citations.append(f"{f}:{len(text.splitlines())} lines")
            running_tokens += tokens

        return SourceResult(
            text="\n".join(parts), citations=citations, truncated=truncated
        )


def _date_from_name(p: Path) -> date | None:
    try:
        return date.fromisoformat(p.stem)
    except ValueError:
        return None
```

Update `__init__.py`:

```python
# shared-vault/skills/ingest/scripts/wiki_query_sources/__init__.py
from .base import SourceAdapter, SourceResult
from .memory_md import MemoryMdAdapter
from .daily_logs import DailyLogsAdapter

__all__ = ["SourceAdapter", "SourceResult", "MemoryMdAdapter", "DailyLogsAdapter"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/auto-test-pytest --target tests/wiki/sources/test_daily_logs_adapter.py`
Expected: All 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add shared-vault/skills/ingest/scripts/wiki_query_sources/daily_logs.py shared-vault/skills/ingest/scripts/wiki_query_sources/__init__.py tests/wiki/sources/test_daily_logs_adapter.py
git commit -m "feat(wiki-queries): daily_logs source adapter"
```

### Task 4: `adr_index` adapter

**Files:**
- Create: `shared-vault/skills/ingest/scripts/wiki_query_sources/adr_index.py`
- Modify: `shared-vault/skills/ingest/scripts/wiki_query_sources/__init__.py`
- Test: `tests/wiki/sources/test_adr_index_adapter.py`

Reads `docs/adrs/adrs-index.json` via `src.lib.adr_utils.load_adrs_index`. Filterable by `status` (list) and `recent_days` (int, based on the `date` field).

- [ ] **Step 1: Write failing tests**

```python
# tests/wiki/sources/test_adr_index_adapter.py
import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from shared_vault.skills.ingest.scripts.wiki_query_sources import AdrIndexAdapter


def _seed_adrs(adr_dir: Path, records: list[dict]) -> None:
    adr_dir.mkdir(parents=True, exist_ok=True)
    (adr_dir / "adrs-index.json").write_text(
        json.dumps(records), encoding="utf-8"
    )


def test_adapter_kind():
    assert AdrIndexAdapter().kind == "adr_index"


def test_status_filter(tmp_path, monkeypatch):
    monkeypatch.setenv("AUGUR_PROJECT_ROOT", str(tmp_path))
    _seed_adrs(tmp_path / "docs" / "adrs", [
        {"adr_number": "ADR-001", "title": "Accepted one", "status": "Accepted",
         "date": date.today().isoformat(), "decision_summary": "ok"},
        {"adr_number": "ADR-002", "title": "Proposed one", "status": "Proposed",
         "date": date.today().isoformat(), "decision_summary": "ok"},
    ])
    adapter = AdrIndexAdapter()
    result = adapter.resolve(
        {"kind": "adr_index", "status": ["Accepted"]},
        budget_tokens=10_000,
    )
    assert "ADR-001" in result.text
    assert "ADR-002" not in result.text


def test_recent_days_filter(tmp_path, monkeypatch):
    monkeypatch.setenv("AUGUR_PROJECT_ROOT", str(tmp_path))
    today = date.today()
    _seed_adrs(tmp_path / "docs" / "adrs", [
        {"adr_number": "ADR-001", "title": "Recent", "status": "Accepted",
         "date": today.isoformat(), "decision_summary": "ok"},
        {"adr_number": "ADR-002", "title": "Old", "status": "Accepted",
         "date": (today - timedelta(days=400)).isoformat(), "decision_summary": "ok"},
    ])
    adapter = AdrIndexAdapter()
    result = adapter.resolve(
        {"kind": "adr_index", "recent_days": 30},
        budget_tokens=10_000,
    )
    assert "ADR-001" in result.text
    assert "ADR-002" not in result.text


def test_empty_index(tmp_path, monkeypatch):
    monkeypatch.setenv("AUGUR_PROJECT_ROOT", str(tmp_path))
    _seed_adrs(tmp_path / "docs" / "adrs", [])
    adapter = AdrIndexAdapter()
    result = adapter.resolve({"kind": "adr_index"}, budget_tokens=10_000)
    assert result.text == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/auto-test-pytest --target tests/wiki/sources/test_adr_index_adapter.py`
Expected: All 4 tests FAIL with `ImportError`.

- [ ] **Step 3: Implement**

```python
# shared-vault/skills/ingest/scripts/wiki_query_sources/adr_index.py
from __future__ import annotations
from datetime import date, timedelta

from src.lib.adr_utils import get_adr_dir, load_adrs_index

from .base import SourceResult


def _approx_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _record_text(rec: dict) -> str:
    return (
        f"{rec.get('adr_number','?')} | {rec.get('status','?')} | "
        f"{rec.get('date','?')} | {rec.get('title','')}\n"
        f"  Decision: {rec.get('decision_summary','') or '(none)'}\n"
    )


class AdrIndexAdapter:
    kind = "adr_index"

    def resolve(self, spec: dict, budget_tokens: int) -> SourceResult:
        records = load_adrs_index(get_adr_dir())
        status_filter = spec.get("status")
        if status_filter:
            allowed = set(status_filter)
            records = [r for r in records if r.get("status") in allowed]

        recent_days = spec.get("recent_days")
        if recent_days is not None:
            cutoff = date.today() - timedelta(days=int(recent_days))
            kept: list[dict] = []
            for r in records:
                try:
                    rdate = date.fromisoformat(str(r.get("date") or ""))
                except ValueError:
                    continue
                if rdate >= cutoff:
                    kept.append(r)
            records = kept

        parts: list[str] = []
        citations: list[str] = []
        running = 0
        truncated = False
        for rec in records:
            block = _record_text(rec)
            tokens = _approx_tokens(block)
            if running + tokens > budget_tokens:
                truncated = True
                break
            parts.append(block)
            citations.append(f"adrs-index.json:{rec.get('adr_number','?')}")
            running += tokens

        return SourceResult(text="".join(parts), citations=citations, truncated=truncated)
```

Update `__init__.py` to export `AdrIndexAdapter`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `/auto-test-pytest --target tests/wiki/sources/test_adr_index_adapter.py`
Expected: All 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add shared-vault/skills/ingest/scripts/wiki_query_sources/adr_index.py shared-vault/skills/ingest/scripts/wiki_query_sources/__init__.py tests/wiki/sources/test_adr_index_adapter.py
git commit -m "feat(wiki-queries): adr_index source adapter"
```

### Task 5: `git_recent_commits` adapter

**Files:**
- Create: `shared-vault/skills/ingest/scripts/wiki_query_sources/git_recent_commits.py`
- Modify: `shared-vault/skills/ingest/scripts/wiki_query_sources/__init__.py`
- Test: `tests/wiki/sources/test_git_recent_commits_adapter.py`

Calls `git log --since=<N days ago> --pretty=format:'%h %ai %s'` via `subprocess`. Defaults `recent_days=14`. Tests stub `subprocess.run` via `monkeypatch`.

- [ ] **Step 1: Write failing tests**

```python
# tests/wiki/sources/test_git_recent_commits_adapter.py
import subprocess

import pytest

from shared_vault.skills.ingest.scripts.wiki_query_sources import GitRecentCommitsAdapter


def test_adapter_kind():
    assert GitRecentCommitsAdapter().kind == "git_recent_commits"


def test_resolve_calls_git_log_with_since(monkeypatch):
    captured: dict = {}

    def fake_run(cmd, *, capture_output, text, cwd, check):
        captured["cmd"] = cmd
        result = subprocess.CompletedProcess(args=cmd, returncode=0,
                                             stdout="abc123 2026-05-11 commit msg\n", stderr="")
        return result

    monkeypatch.setattr(subprocess, "run", fake_run)
    adapter = GitRecentCommitsAdapter()
    result = adapter.resolve({"kind": "git_recent_commits", "recent_days": 7}, budget_tokens=10_000)
    assert "abc123" in result.text
    assert any("--since" in arg for arg in captured["cmd"])
    assert any("7 days ago" in arg for arg in captured["cmd"])


def test_resolve_default_14_days(monkeypatch):
    captured: dict = {}
    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")
    monkeypatch.setattr(subprocess, "run", fake_run)
    adapter = GitRecentCommitsAdapter()
    adapter.resolve({"kind": "git_recent_commits"}, budget_tokens=10_000)
    assert any("14 days ago" in arg for arg in captured["cmd"])


def test_resolve_git_failure_returns_empty(monkeypatch):
    def fake_run(cmd, **kwargs):
        raise subprocess.CalledProcessError(returncode=1, cmd=cmd, stderr="not a git repo")
    monkeypatch.setattr(subprocess, "run", fake_run)
    adapter = GitRecentCommitsAdapter()
    result = adapter.resolve({"kind": "git_recent_commits"}, budget_tokens=10_000)
    assert result.text == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/auto-test-pytest --target tests/wiki/sources/test_git_recent_commits_adapter.py`
Expected: 3 tests FAIL with `ImportError`.

- [ ] **Step 3: Implement**

```python
# shared-vault/skills/ingest/scripts/wiki_query_sources/git_recent_commits.py
from __future__ import annotations
import subprocess

from src.config.paths import get_project_root

from .base import SourceResult


def _approx_tokens(text: str) -> int:
    return max(1, len(text) // 4)


class GitRecentCommitsAdapter:
    kind = "git_recent_commits"

    def resolve(self, spec: dict, budget_tokens: int) -> SourceResult:
        recent_days = int(spec.get("recent_days", 14))
        cmd = [
            "git", "log",
            f"--since={recent_days} days ago",
            "--pretty=format:%h %ai %s",
        ]
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True,
                cwd=get_project_root(), check=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            return SourceResult(text="", citations=[], truncated=False)

        text = result.stdout or ""
        truncated = False
        if _approx_tokens(text) > budget_tokens:
            # tail-truncate
            lines = text.splitlines()
            keep: list[str] = []
            running = 0
            for line in lines:
                running += _approx_tokens(line)
                if running > budget_tokens:
                    truncated = True
                    break
                keep.append(line)
            text = "\n".join(keep)

        citation = f"git log --since={recent_days} days ago ({len(text.splitlines())} commits)"
        return SourceResult(text=text, citations=[citation], truncated=truncated)
```

Update `__init__.py` to export `GitRecentCommitsAdapter`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `/auto-test-pytest --target tests/wiki/sources/test_git_recent_commits_adapter.py`
Expected: All 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add shared-vault/skills/ingest/scripts/wiki_query_sources/git_recent_commits.py shared-vault/skills/ingest/scripts/wiki_query_sources/__init__.py tests/wiki/sources/test_git_recent_commits_adapter.py
git commit -m "feat(wiki-queries): git_recent_commits source adapter"
```

### Task 6: `ask_retention`, `inbox`, `linked_folder` adapters (wrap existing pipelines)

**Files:**
- Create: `shared-vault/skills/ingest/scripts/wiki_query_sources/ask_retention.py`
- Create: `shared-vault/skills/ingest/scripts/wiki_query_sources/inbox.py`
- Create: `shared-vault/skills/ingest/scripts/wiki_query_sources/linked_folder.py`
- Modify: `shared-vault/skills/ingest/scripts/wiki_query_sources/__init__.py`
- Test: `tests/wiki/sources/test_existing_pipeline_adapters.py`

These three are thin wrappers around existing pipelines (`ask-sync-data`, inbox folder reads, `knowledge-linked-folders`). The adapter contract is the same but the implementation delegates.

- [ ] **Step 1: Write failing tests** for kind matching + delegation to existing pipelines (mock the underlying functions; verify the adapter calls them and wraps results in `SourceResult`).

- [ ] **Step 2: Run tests to verify they fail.**

- [ ] **Step 3: Implement** the three adapters following the same pattern as Tasks 2–5. Each one:
  - Reads from its existing source (or uses an existing function).
  - Applies `recent_days` / path filters where applicable.
  - Returns a `SourceResult` with citations.
  - Returns empty `SourceResult` on missing source (not an error).

- [ ] **Step 4: Run tests to verify they pass.**

- [ ] **Step 5: Commit**

```bash
git add shared-vault/skills/ingest/scripts/wiki_query_sources/ tests/wiki/sources/test_existing_pipeline_adapters.py
git commit -m "feat(wiki-queries): ask_retention/inbox/linked_folder adapters"
```

---

## C2 — Query runner

### Task 7: Query runner — orchestration + agent handoff + section validation

**Files:**
- Create: `shared-vault/skills/ingest/scripts/wiki_query_runner.py`
- Test: `tests/wiki/test_query_runner.py`

The runner:
1. Loads the query spec via `wiki_query_registry.read_query`.
2. Resolves each source via its adapter; concatenates with markdown source dividers.
3. Builds the agent handoff prompt by interpolating `{{sources}}` in `prompt_template`.
4. If no `synthesis_markdown` is supplied, returns an `agent_action_required` result with the prompt path and required sections.
5. When `synthesis_markdown` is supplied, validates the agent output contains every required H2 section.
6. Writes the output page to `<vault>/wiki/<output relative path under vault/wiki/>`.
7. Records run status (timestamp, handoff path, error if any) in a sibling state file `vault/wiki/.queries-state.json`.

Returns a `RunResult` dataclass with `success`, `agent_action_required`, `prompt_path`, `error`, `output_path`, `sections_validated`, `truncated_sources`.

- [ ] **Step 1: Write failing tests** covering:
  - First call with no synthesis returns `agent_action_required`, writes a handoff prompt, and does not write the final output page.
  - Submit call with all required sections → output file written, state file updated, `RunResult.success == True`.
  - Submitted synthesis missing a required section → run fails, no output written, error message names the missing section.
  - Source resolution returns empty → handoff prompt flags "Insufficient data"; no hidden model call is made.
  - Per-query lock: second concurrent call returns "already running" without preparing another handoff.

- [ ] **Step 2: Run tests to verify they fail.** All FAIL with `ImportError`.

- [ ] **Step 3: Implement `wiki_query_runner.py`**. Do not introduce an LLM client or call a provider from the runner. Prepare an agent handoff prompt on the first call; validate submitted markdown on the second call. Section validation parses the output for `^## <section>\s*$` lines and asserts each required section is present.

- [ ] **Step 4: Run tests to verify they pass.**

- [ ] **Step 5: Commit**

```bash
git add shared-vault/skills/ingest/scripts/wiki_query_runner.py tests/wiki/test_query_runner.py
git commit -m "feat(wiki-queries): query runner with agent handoff + section validation"
```

---

## C3 — MCP tools

### Task 8: `wiki-queries-list` and `wiki-queries-read` MCP tools

**Files:**
- Create: `shared-vault/skills/ingest/scripts/mcp/wiki_queries_tools.py`
- Modify: `shared-vault/skills/ingest/scripts/mcp/wiki_tools.py` (register the new module)
- Test: `tests/packages/augur-mcp/test_wiki_queries_tools.py`

- [ ] **Step 1: Write failing tests** covering:
  - `wiki-queries-list` returns array of query specs + status dicts (last_run, last_error, output_size, source_fingerprint).
  - `wiki-queries-read` returns one query spec by id, or error if not found.
  - Both tools follow the standard MCP tool-result shape (`{"success": bool, ...}` per existing pattern in `tools_memory_core.py`).

- [ ] **Step 2: Run tests to verify they fail.**

- [ ] **Step 3: Implement** the two tools. Register them in `wiki_tools.py` (the ingest skill's MCP tool registration entry point) via a `register_wiki_queries_tools(server, ...)` call.

- [ ] **Step 4: Run tests to verify they pass.**

- [ ] **Step 5: Commit**

```bash
git add shared-vault/skills/ingest/scripts/mcp/wiki_queries_tools.py shared-vault/skills/ingest/scripts/mcp/wiki_tools.py tests/packages/augur-mcp/test_wiki_queries_tools.py
git commit -m "feat(wiki-queries): wiki-queries-list and wiki-queries-read MCP tools"
```

### Task 9: `wiki-queries-write` and `wiki-queries-seed-defaults` MCP tools

**Files:**
- Modify: `shared-vault/skills/ingest/scripts/mcp/wiki_queries_tools.py`
- Test: extend `tests/packages/augur-mcp/test_wiki_queries_tools.py`

- [ ] **Step 1: Add failing tests** for write (validates + persists) and seed-defaults (idempotent — never overwrites existing user-edited query of same id).

- [ ] **Step 2: Run.**
- [ ] **Step 3: Implement** both tools using the registry CRUD from Task 1. `seed-defaults` reads from `shared-vault/skills/ingest/assets/seeds/queries-defaults.yaml` (created in Task 12) and upserts only missing entries.
- [ ] **Step 4: Run.**
- [ ] **Step 5: Commit**

```bash
git add shared-vault/skills/ingest/scripts/mcp/wiki_queries_tools.py tests/packages/augur-mcp/test_wiki_queries_tools.py
git commit -m "feat(wiki-queries): wiki-queries-write and wiki-queries-seed-defaults MCP tools"
```

### Task 10: `wiki-queries-run` MCP tool

**Files:**
- Modify: `shared-vault/skills/ingest/scripts/mcp/wiki_queries_tools.py`
- Test: extend `tests/packages/augur-mcp/test_wiki_queries_tools.py`

- [ ] **Step 1: Add failing tests** for: first call returns agent handoff, submit succeeds, missing-query error, submitted-section-validation failure path, per-query lock returning "already running".

- [ ] **Step 2: Run.**
- [ ] **Step 3: Implement** as a wrapper around `wiki_query_runner.run`. First call returns the handoff prompt contract; submit calls return the full `RunResult` dict after validation/write.
- [ ] **Step 4: Run.**
- [ ] **Step 5: Commit**

```bash
git add shared-vault/skills/ingest/scripts/mcp/wiki_queries_tools.py tests/packages/augur-mcp/test_wiki_queries_tools.py
git commit -m "feat(wiki-queries): wiki-queries-run MCP tool"
```

### Task 11: Capability exposure entries

**Files:**
- Modify: `config/system/capability_exposure.yaml`
- Modify: `CLAUDE.md` capability table (regenerated by `sync_agents` — verify generation picks up the new entries)

- [ ] **Step 1: Add entries** for all 5 new tools to `capability_exposure.yaml`:

```yaml
mcp-tool:wiki-queries-list:
  type: mcp-tool
  owner_kind: skill
  skill: ingest
  management: read-only
  scope: vault
  primary_surface: mcp via dashboard
  preferred_client: dashboard
  export_to: [mcp]
  description: "List all wiki compounding queries with status (last_run, source_fingerprint, last_error)."

mcp-tool:wiki-queries-read:
  type: mcp-tool
  owner_kind: skill
  skill: ingest
  management: read-only
  scope: vault
  primary_surface: mcp via dashboard
  preferred_client: dashboard
  export_to: [mcp]
  description: "Read one wiki query spec by id."

mcp-tool:wiki-queries-write:
  type: mcp-tool
  owner_kind: skill
  skill: ingest
  management: write
  scope: vault
  primary_surface: cli via shell
  preferred_client: agent
  export_to: []
  description: "Create or update a wiki query in vault/wiki/queries.yaml."

mcp-tool:wiki-queries-run:
  type: mcp-tool
  owner_kind: skill
  skill: ingest
  management: write
  scope: vault
  primary_surface: cli via shell
  preferred_client: agent
  export_to: []
  description: "Synthesize one wiki query — prepares agent handoff, validates sections, writes output."

mcp-tool:wiki-queries-seed-defaults:
  type: mcp-tool
  owner_kind: skill
  skill: ingest
  management: write
  scope: vault
  primary_surface: cli via shell
  preferred_client: agent
  export_to: []
  description: "Idempotent seed of the 4 default wiki queries."
```

- [ ] **Step 2: Regenerate agent instructions** via the `/adr` post-write hook chain. Then verify CLAUDE.md's capability table contains the 5 new entries.

```bash
PYTHONPATH=".:shared-vault" python3 -m skills.ai.scripts.sync_agents sync agents all
grep -c "wiki-queries-" CLAUDE.md  # expect 5
```

- [ ] **Step 3: Commit**

```bash
git add config/system/capability_exposure.yaml CLAUDE.md
git commit -m "feat(wiki-queries): capability exposure entries for 5 new MCP tools"
```

---

## C4 — Seed defaults + A/B equivalence test

### Task 12: `queries-defaults.yaml` asset

**Files:**
- Create: `shared-vault/skills/ingest/assets/seeds/queries-defaults.yaml`

- [ ] **Step 1: Write the asset** containing the four default queries verbatim from spec §6.3 — `profile-human-api`, `active-projects`, `recent-decisions`, `knowledge-gaps`. Preserve the exact prompt templates and required_sections lists from the spec.

- [ ] **Step 2: Validate** the file against the registry schema via a one-shot script:

```bash
python3 -c "
from shared_vault.skills.ingest.scripts.wiki_query_registry import validate_query_spec
import yaml
data = yaml.safe_load(open('shared-vault/skills/ingest/assets/seeds/queries-defaults.yaml'))
for qid, spec in data['queries'].items():
    validate_query_spec(qid, spec, existing={})
print('All', len(data['queries']), 'default queries valid.')
"
```
Expected: `All 4 default queries valid.`

- [ ] **Step 3: Commit**

```bash
git add shared-vault/skills/ingest/assets/seeds/queries-defaults.yaml
git commit -m "feat(wiki-queries): seed 4 default queries (profile-human-api, active-projects, recent-decisions, knowledge-gaps)"
```

### Task 13: Seed + first synthesis run

**Files:**
- No file changes — this task is a one-time execution + verification.

- [ ] **Step 1: Run `wiki-queries-seed-defaults`** via the MCP CLI:

```bash
# Use the MCP CLI wrapper or invoke the tool directly via Python
python3 -c "
from shared_vault.skills.ingest.scripts.mcp.wiki_queries_tools import seed_defaults
result = seed_defaults()
print(result)
"
```
Expected output names all 4 queries as `created` (first run).

- [ ] **Step 2: Verify `vault/wiki/queries.yaml`** exists and contains all 4 queries:

```bash
python3 -c "
from shared_vault.skills.ingest.scripts.wiki_query_registry import list_queries
qs = list_queries()
assert set(qs) == {'profile-human-api', 'active-projects', 'recent-decisions', 'knowledge-gaps'}
print('OK 4 queries seeded')
"
```

- [ ] **Step 3: Trigger `profile-human-api` run**:

```bash
python3 -c "
from shared_vault.skills.ingest.scripts.wiki_query_runner import run_query
result = run_query('profile-human-api')
print('success:', result.success)
print('output:', result.output_path)
print('error:', result.error)
"
```
Expected: `success: True`. If False, debug per `systematic-debugging` skill before continuing — the migration depends on this synthesis succeeding.

- [ ] **Step 4: Verify output**:

```bash
test -f vault/wiki/profile-human-api.md && echo "OK file exists"
grep -c "^## Role$" vault/wiki/profile-human-api.md  # expect >=1
grep -c "^## Expertise$" vault/wiki/profile-human-api.md  # expect >=1
grep -c "^## Communication Style$" vault/wiki/profile-human-api.md  # expect >=1
grep -c "^## Success Criteria$" vault/wiki/profile-human-api.md  # expect >=1
grep -c "^## Context Gaps$" vault/wiki/profile-human-api.md  # expect >=1
grep -c "^## Evidence$" vault/wiki/profile-human-api.md  # expect >=1
grep -c "^## Source Basis$" vault/wiki/profile-human-api.md  # expect >=1
```

All grep counts >= 1.

- [ ] **Step 5: Do NOT commit `vault/wiki/queries.yaml` or the output `.md`** — those live in the user's external vault (per ADR-270) and are not in this repo. The asset at `shared-vault/skills/ingest/assets/seeds/queries-defaults.yaml` is what ships in code; the vault copy is generated on first run.

### Task 14: A/B equivalence test (hot-path safety gate)

**Files:**
- Create: `tests/migration/test_human_api_field_set_equivalence.py`

This test asserts the new wiki synthesis output covers the same field set as the regex pipeline. It's the only gate between the new pipeline and the consumer swap in Task 15.

- [ ] **Step 1: Write the test**

```python
# tests/migration/test_human_api_field_set_equivalence.py
"""
A/B equivalence test for the HUMAN_API.md migration.

Runs both the old regex pipeline (profile_generator.regenerate_human_api_profile)
and the new wiki query (profile-human-api) over the same seeded MEMORY.md +
daily logs, and asserts the new output covers the same field set as the old.

This test is the safety gate before context_injector swaps to the new parser
(Task 15). Delete after the migration lands.
"""
from __future__ import annotations
from pathlib import Path
import re

import pytest


REQUIRED_FIELDS = {
    "Role", "Expertise", "Communication Style",
    "Success Criteria", "Context Gaps",
}


def _seed_memory_and_logs(vault: Path) -> None:
    mem = vault / "memory"
    mem.mkdir()
    (mem / "MEMORY.md").write_text(
        "## Decisions\n"
        "- [2026-05-01] decided to ship ADR-driven SDLC\n"
        "- [2026-05-05] picked wiki compounding for synthesis\n"
        "## Preferences\n"
        "- prefer concise commit messages\n"
        "- avoid sub-tabs in dashboard\n"
        "## Recent Patterns\n"
        "- frequently refactors agent-vs-MCP boundaries\n",
        encoding="utf-8",
    )
    daily = mem / "daily"
    daily.mkdir()
    (daily / "2026-05-10.md").write_text(
        "## 14:00 - Decision\n- shipped voice profile spec\n",
        encoding="utf-8",
    )


def test_old_regex_pipeline_produces_required_fields(tmp_path, monkeypatch):
    monkeypatch.setenv("AUGUR_VAULT", str(tmp_path))
    _seed_memory_and_logs(tmp_path)

    from src.lib.knowledge.profile_generator import regenerate_human_api_profile
    result = regenerate_human_api_profile()
    output = Path(result["path"]).read_text(encoding="utf-8")

    # Old pipeline produces YAML frontmatter; check field keys
    assert "role:" in output
    assert "expertise:" in output
    assert "communicationStyle:" in output or "communication_style:" in output


def test_new_wiki_query_produces_required_h2_sections(tmp_path, monkeypatch):
    monkeypatch.setenv("AUGUR_VAULT", str(tmp_path))
    _seed_memory_and_logs(tmp_path)

    from shared_vault.skills.ingest.scripts.mcp.wiki_queries_tools import seed_defaults
    from shared_vault.skills.ingest.scripts.wiki_query_runner import run_query
    seed_defaults()
    result = run_query("profile-human-api")
    assert result.success, f"Run failed: {result.error}"
    output = Path(result.output_path).read_text(encoding="utf-8")

    for field in REQUIRED_FIELDS:
        assert re.search(rf"^## {re.escape(field)}\s*$", output, re.MULTILINE), \
            f"Missing required H2 section: {field}"


def test_h2_section_set_equivalent_to_old_field_set(tmp_path, monkeypatch):
    """Old YAML field names must be 1:1 representable as new H2 sections.

    This is the contract context_injector depends on.
    """
    monkeypatch.setenv("AUGUR_VAULT", str(tmp_path))
    _seed_memory_and_logs(tmp_path)

    from shared_vault.skills.ingest.scripts.wiki_query_runner import run_query
    from shared_vault.skills.ingest.scripts.mcp.wiki_queries_tools import seed_defaults
    seed_defaults()
    result = run_query("profile-human-api")
    output = Path(result.output_path).read_text(encoding="utf-8")

    field_to_section = {
        "role": "Role",
        "expertise": "Expertise",
        "communicationStyle": "Communication Style",
        "successCriteria": "Success Criteria",
        "contextGaps": "Context Gaps",
    }
    for yaml_field, h2_section in field_to_section.items():
        assert re.search(rf"^## {re.escape(h2_section)}\s*$", output, re.MULTILINE), \
            f"H2 section missing for legacy field {yaml_field}: {h2_section}"
```

- [ ] **Step 2: Run the test**

Run: `/auto-test-pytest --target tests/migration/test_human_api_field_set_equivalence.py`
Expected: All 3 tests PASS. If the submitted agent output omits a section, tighten the prompt template in `queries-defaults.yaml` to be more explicit about the section names being mandatory.

- [ ] **Step 3: Commit**

```bash
git add tests/migration/test_human_api_field_set_equivalence.py
git commit -m "test(migration): A/B equivalence — wiki output covers HUMAN_API field set"
```

---

## C5 — Consumer migration

### Task 15: `context_injector` parser swap

**Files:**
- Modify: `src/mcp/augur_shared/context_injector.py`
- Test: `tests/packages/augur-mcp/test_context_models.py` (existing — extend)

The parser changes from "read YAML frontmatter fields from `runtime/memory/HUMAN_API.md`" to "read named H2 sections from `vault/wiki/profile-human-api.md`". The field set is unchanged.

- [ ] **Step 1: Read the current context_injector** to understand its load path and shape.

```bash
grep -n "HUMAN_API\|parse_human_api\|load_profile\|profile_path" src/mcp/augur_shared/context_injector.py
```

- [ ] **Step 2: Add failing tests** for the new behavior:

```python
# In tests/packages/augur-mcp/test_context_models.py, add:

def test_context_injector_reads_h2_sections_from_vault_wiki(tmp_path, monkeypatch):
    monkeypatch.setenv("AUGUR_VAULT", str(tmp_path))
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "profile-human-api.md").write_text(
        "## Role\nSoftware architect at Augur.\n\n"
        "## Expertise\n- ADR-driven refactors\n- agent/MCP architecture\n\n"
        "## Communication Style\nConcise, design-first.\n\n"
        "## Success Criteria\n- one focused commit per task\n\n"
        "## Context Gaps\n- frontend internals\n\n"
        "## Evidence\nMEMORY.md:42\n\n"
        "## Source Basis\nvault/memory/MEMORY.md\n",
        encoding="utf-8",
    )

    from src.mcp.augur_shared.context_injector import load_profile
    profile = load_profile()
    assert profile.role == "Software architect at Augur."
    assert "ADR-driven refactors" in profile.expertise
    assert profile.communication_style == "Concise, design-first."
    assert "one focused commit per task" in profile.success_criteria
    assert "frontend internals" in profile.context_gaps


def test_context_injector_handles_missing_profile_file(tmp_path, monkeypatch):
    monkeypatch.setenv("AUGUR_VAULT", str(tmp_path))
    from src.mcp.augur_shared.context_injector import load_profile
    profile = load_profile()
    assert profile.role == "" or profile.role is None
```

- [ ] **Step 3: Implement** the new parser in `context_injector.py`. Read from `get_vault_dir() / "wiki" / "profile-human-api.md"`. Parse H2 sections via regex (`^## (\w[\w\s]*?)\s*$`). Map sections to the existing profile dataclass fields. Remove the YAML-frontmatter parser branch.

- [ ] **Step 4: Run tests**

Run: `/auto-test-pytest --target tests/packages/augur-mcp/test_context_models.py`
Expected: All tests PASS (including the new ones and any existing ones that survive the parser swap).

- [ ] **Step 5: Commit**

```bash
git add src/mcp/augur_shared/context_injector.py tests/packages/augur-mcp/test_context_models.py
git commit -m "refactor(context-injector): swap parser from YAML frontmatter to H2 sections; new path vault/wiki/profile-human-api.md"
```

### Task 16: `knowledge-memory-profile` + `knowledge-memory-workspace-open` path resolution

**Files:**
- Modify: `shared-vault/skills/knowledge/scripts/mcp/tools_memory_profile.py:65-85` (the `_resolve_workspace_target` function)
- Test: `shared-vault/skills/knowledge/augur/tests/test_tools_memory_profile.py` (extend)

- [ ] **Step 1: Read current behavior**

```bash
grep -n "HUMAN_API\|runtime_mem_dir" shared-vault/skills/knowledge/scripts/mcp/tools_memory_profile.py
```

- [ ] **Step 2: Add failing tests** that the profile path resolves to `vault/wiki/profile-human-api.md`:

```python
def test_resolve_profile_target_returns_vault_wiki_path(tmp_path, monkeypatch):
    monkeypatch.setenv("AUGUR_VAULT", str(tmp_path))
    from shared_vault.skills.knowledge.scripts.mcp.tools_memory_profile import _resolve_workspace_target
    target = _resolve_workspace_target(file_id="profile")
    assert "vault/wiki/profile-human-api.md" in target


def test_resolve_report_target_also_returns_vault_wiki_path(tmp_path, monkeypatch):
    monkeypatch.setenv("AUGUR_VAULT", str(tmp_path))
    from shared_vault.skills.knowledge.scripts.mcp.tools_memory_profile import _resolve_workspace_target
    target = _resolve_workspace_target(file_id="report")
    assert "vault/wiki/profile-human-api.md" in target
```

- [ ] **Step 3: Implement** — update `_resolve_workspace_target` to map `"profile"` and `"report"` to `get_vault_dir() / "wiki" / "profile-human-api.md"` instead of `runtime_mem_dir / "HUMAN_API.md"`.

- [ ] **Step 4: Run tests.**
- [ ] **Step 5: Commit**

```bash
git add shared-vault/skills/knowledge/scripts/mcp/tools_memory_profile.py shared-vault/skills/knowledge/augur/tests/test_tools_memory_profile.py
git commit -m "refactor(knowledge): profile/report file_id now resolves to vault/wiki/profile-human-api.md"
```

### Task 17: `memory-profile-regenerate` becomes thin shim

**Files:**
- Modify: `shared-vault/skills/knowledge/scripts/mcp/tools_memory_core.py:442-475` (the `memory_profile_regenerate_tool` function)
- Test: `shared-vault/skills/knowledge/augur/tests/test_tools_memory_core.py` (extend)

- [ ] **Step 1: Add failing test** asserting that calling `memory-profile-regenerate` invokes `wiki-queries-run profile-human-api`:

```python
def test_memory_profile_regenerate_calls_wiki_queries_run(monkeypatch):
    called = {}
    def fake_run(query_id):
        called["id"] = query_id
        class R: success = True; output_path = "vault/wiki/profile-human-api.md"; error = None
        return R()
    monkeypatch.setattr(
        "shared_vault.skills.ingest.scripts.wiki_query_runner.run_query",
        fake_run,
    )
    from shared_vault.skills.knowledge.scripts.mcp.tools_memory_core import _memory_profile_regenerate_impl
    result = _memory_profile_regenerate_impl()
    assert called["id"] == "profile-human-api"
    assert result["success"] is True
```

- [ ] **Step 2: Run.**

- [ ] **Step 3: Implement** — replace the body of `memory_profile_regenerate_tool` with a call to `wiki_query_runner.run_query("profile-human-api")`. Remove the `regenerate_human_api_profile` import. Preserve the public tool surface (name, return shape).

- [ ] **Step 4: Run.**

- [ ] **Step 5: Commit**

```bash
git add shared-vault/skills/knowledge/scripts/mcp/tools_memory_core.py shared-vault/skills/knowledge/augur/tests/test_tools_memory_core.py
git commit -m "refactor(knowledge): memory-profile-regenerate becomes thin wrapper over wiki-queries-run"
```

---

## C6 — Dashboard

### Task 18: `useWikiQueries` hook

**Files:**
- Create: `apps/dashboard/features/pages/brain/wiki/hooks.ts`
- Create: `apps/dashboard/features/pages/brain/wiki/types.ts`
- Test: `tests/dashboard/features/pages/brain/wiki/hooks.test.tsx`

Polls `wiki-queries-list` every 30s. Exposes `queries`, `runQuery(id)`, `editQuery(id, spec)`, `seedDefaults()`. Uses the existing `useMcp` hook pattern from `apps/dashboard/lib/mcp/`.

- [ ] **Step 1: Define types**

```typescript
// apps/dashboard/features/pages/brain/wiki/types.ts
export type SourceKind =
  | "memory_md"
  | "daily_logs"
  | "ask_retention"
  | "adr_index"
  | "git_recent_commits"
  | "inbox"
  | "linked_folder";

export interface SourceSpec {
  kind: SourceKind;
  path?: string;
  recent_days?: number;
  section?: string;
  status?: string[];
}

export interface QuerySpec {
  title: string;
  description: string;
  prompt_template: string;
  sources: SourceSpec[];
  output: string;
  page_type: "query";
  required_sections: string[];
  refresh_policy: "manual";
  system?: boolean;
}

export interface QueryStatus {
  last_run: string | null;
  last_error: string | null;
  output_size: number | null;
  source_fingerprint: string | null;
  freshness: "green" | "amber" | "red";
}

export interface QueryListItem {
  id: string;
  spec: QuerySpec;
  status: QueryStatus;
}
```

- [ ] **Step 2: Write failing test for the hook**

```typescript
// tests/dashboard/features/pages/brain/wiki/hooks.test.tsx
import { renderHook, waitFor } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { useWikiQueries } from "@/features/pages/brain/wiki/hooks";

vi.mock("@/lib/mcp", () => ({
  callMcp: vi.fn().mockResolvedValue({
    success: true,
    queries: [
      { id: "profile-human-api", spec: { title: "Memory Profile" }, status: { freshness: "green" } },
    ],
  }),
}));

describe("useWikiQueries", () => {
  it("loads queries from wiki-queries-list", async () => {
    const { result } = renderHook(() => useWikiQueries());
    await waitFor(() => expect(result.current.queries.length).toBe(1));
    expect(result.current.queries[0].id).toBe("profile-human-api");
  });
});
```

- [ ] **Step 3: Run.** Expected FAIL — hook not implemented.
- [ ] **Step 4: Implement** `hooks.ts` following the existing pattern in `apps/dashboard/features/pages/brain/profile/hooks.ts`.
- [ ] **Step 5: Run.** Expected PASS.
- [ ] **Step 6: Commit**

```bash
git add apps/dashboard/features/pages/brain/wiki/hooks.ts apps/dashboard/features/pages/brain/wiki/types.ts tests/dashboard/features/pages/brain/wiki/hooks.test.tsx
git commit -m "feat(dashboard): useWikiQueries hook for /brain/wiki"
```

### Task 19: `QueryCard` component

**Files:**
- Create: `apps/dashboard/features/pages/brain/wiki/components/QueryCard.tsx`
- Test: `tests/dashboard/features/pages/brain/wiki/components/QueryCard.test.tsx`

Renders one query card with title, freshness indicator dot, source-list chips, last-run timestamp, and Refresh / Edit / View buttons. System queries show a "system — required" badge.

- [ ] **Step 1: Write failing test** rendering a `QueryCard` with stub spec/status; assert the title, freshness dot color, source kinds rendered, and click handlers fire.

- [ ] **Step 2: Run.**
- [ ] **Step 3: Implement** following the existing `apps/dashboard/features/pages/brain/profile/components/VoiceProfile.tsx` card pattern (from ADR-729) for visual consistency.
- [ ] **Step 4: Run.**
- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/features/pages/brain/wiki/components/QueryCard.tsx tests/dashboard/features/pages/brain/wiki/components/QueryCard.test.tsx
git commit -m "feat(dashboard): QueryCard component for /brain/wiki"
```

### Task 20: `QueryEditor` component

**Files:**
- Create: `apps/dashboard/features/pages/brain/wiki/components/QueryEditor.tsx`
- Test: `tests/dashboard/features/pages/brain/wiki/components/QueryEditor.test.tsx`

Inline form for editing a query spec. Renders fields for title, description, prompt_template (textarea), sources (multi-select per kind), output path, required_sections (chip list editor). Validates client-side before calling `wiki-queries-write`.

- [ ] **Step 1: Test** — failing test exercises filling out a form and calling the save handler.
- [ ] **Step 2: Run.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run.**
- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/features/pages/brain/wiki/components/QueryEditor.tsx tests/dashboard/features/pages/brain/wiki/components/QueryEditor.test.tsx
git commit -m "feat(dashboard): QueryEditor component"
```

### Task 21: `/brain/wiki` page assembly

**Files:**
- Create: `apps/dashboard/features/pages/brain/wiki/page.tsx`
- Modify: `shared-vault/skills/ingest/SKILL.md` (add `/brain/wiki` to `x-augur-dashboard-pages` list)

- [ ] **Step 1: Implement** `page.tsx` — calls `useWikiQueries()`, renders header with `+ New query` / `Seed defaults` buttons, maps queries to `QueryCard`s with an optional `QueryEditor` modal opened on Edit click.

- [ ] **Step 2: Add page to ingest SKILL.md** by extending `x-augur-dashboard-pages` array.

- [ ] **Step 3: Regenerate dashboard via `/dev-build`** and verify the page mounts:

```bash
# After /dev-build completes:
curl -s http://localhost:3000/brain/wiki | grep -c "Wiki Queries"  # SSR check, not sufficient by itself
```

- [ ] **Step 4: Browser verification** (rule 28) — open `http://localhost:3000/brain/wiki` in Chrome MCP / browser tool, screenshot, verify all 4 default queries render with freshness indicators and action buttons.

- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/features/pages/brain/wiki/page.tsx shared-vault/skills/ingest/SKILL.md
git commit -m "feat(dashboard): /brain/wiki page mounted"
```

### Task 22: `HumanApiProfile` component refactor

**Files:**
- Modify: `apps/dashboard/features/pages/brain/profile/components/HumanApiProfile.tsx`
- Modify: `apps/dashboard/features/pages/brain/profile/components/HumanApiProfileSection.tsx`
- Modify: `apps/dashboard/features/pages/brain/profile/hooks.ts` (useHumanApiProfile)
- Modify: `apps/dashboard/features/pages/brain/profile/types.ts`
- Test: `tests/dashboard/features/pages/brain/memory/components/HumanApiProfile.test.tsx`

The hook now reads via `profile-read` (or whatever MCP tool resolves `vault/wiki/profile-human-api.md`) and returns parsed H2 sections instead of YAML fields. The component renders sections as labeled blocks.

- [ ] **Step 1: Read current implementation**

```bash
grep -n "humanApi\|HumanApi\|yaml\|frontmatter" apps/dashboard/features/pages/brain/profile/hooks.ts apps/dashboard/features/pages/brain/profile/types.ts
```

- [ ] **Step 2: Update types** to reflect H2-section shape:

```typescript
// apps/dashboard/features/pages/brain/profile/types.ts
export interface HumanApiProfile {
  role: string;
  expertise: string[];
  communicationStyle: string;
  successCriteria: string[];
  contextGaps: string[];
  evidence: string;
  sourceBasis: string;
  lastUpdated: string | null;
}
```

- [ ] **Step 3: Write failing test** rendering the new section-based output.

- [ ] **Step 4: Run.** Expected FAIL.

- [ ] **Step 5: Implement** the hook + component to consume the new shape. Visual layout (cards, chip lists) stays consistent with the existing style — only the data binding changes.

- [ ] **Step 6: Run.** Expected PASS.

- [ ] **Step 7: Browser verification** — open `http://localhost:3000/brain/profile` after `/dev-build`. Confirm the Memory Profile card renders with the new H2 sections and matches the visual design.

- [ ] **Step 8: Commit**

```bash
git add apps/dashboard/features/pages/brain/profile/ tests/dashboard/features/pages/brain/memory/components/HumanApiProfile.test.tsx tests/dashboard/features/pages/brain/memory/hooks.test.tsx
git commit -m "refactor(dashboard): HumanApiProfile reads H2 sections from vault/wiki/profile-human-api.md"
```

---

## C7 — Browse integration

### Task 23: Add `memory` category to BROWSE_CATEGORIES

**Files:**
- Modify: `apps/dashboard/lib/browse/types.ts:213-236` (BROWSE_CATEGORIES array)
- Modify: `apps/dashboard/lib/browse/transforms.ts` (add memory category transform)
- Test: existing browse tests under `tests/dashboard/lib/browse/`

- [ ] **Step 1: Add the category**

```typescript
// In apps/dashboard/lib/browse/types.ts BROWSE_CATEGORIES array,
// add after the existing entries:
{
  id: "memory",
  label: "Memory",
  singularLabel: "Memory Entry",
  icon: "Brain",
  devOnly: false,
  group: "content",
  journey_group: "knowledge",
  journey_order: 5,
  viewLayout: "card",
},
```

- [ ] **Step 2: Add the transform** in `transforms.ts` — wires the `memory` category to a new MCP query that returns memory entries (MEMORY.md decisions + recent daily-log entries, one card per logical entry).

For v1, the transform calls an existing tool (`knowledge-memory-read` + `knowledge-memory-daily-logs`) and merges results. If the volume warrants a dedicated MCP tool later, that's an ADR-732 follow-on.

- [ ] **Step 3: Write/update browse tests** asserting `memory` appears in BROWSE_CATEGORIES with the right journey_order and group.

- [ ] **Step 4: Browser verification** — open `http://localhost:3000/browse` after `/dev-build`, find the Memory card in the Content group's knowledge journey-group (between Profile at order 4 and any later entries), click into it, verify cards render.

- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/lib/browse/types.ts apps/dashboard/lib/browse/transforms.ts tests/dashboard/lib/browse/
git commit -m "feat(browse): add memory category at journey_order=5 in journey_group=knowledge"
```

---

## C8 — Retirement

### Task 24: Delete `profile_generator.py` and its tests

**Files:**
- Delete: `src/lib/knowledge/profile_generator.py`
- Delete: `shared-vault/skills/knowledge/augur/tests/test_profile_generator.py`
- Modify: `shared-vault/skills/knowledge/augur/tests/test_tools_memory_core.py` (remove any remaining imports of `regenerate_human_api_profile`)

- [ ] **Step 1: Search for callers**

```bash
grep -rn "profile_generator\|regenerate_human_api_profile" --include="*.py" ~/Projects/Augur/
```

Expected: only the file itself + its test + the test file from Task 17 (the migration A/B test — that one still imports it intentionally for the comparison; verify whether the A/B test is still relevant or should be deleted as well).

- [ ] **Step 2: Delete A/B test** (it served its purpose pre-cutover):

```bash
rm tests/migration/test_human_api_field_set_equivalence.py
```

- [ ] **Step 3: Delete the module + its test**

```bash
git rm src/lib/knowledge/profile_generator.py
git rm shared-vault/skills/knowledge/augur/tests/test_profile_generator.py
```

- [ ] **Step 4: Run remaining test suites** to verify no other callers broke:

```bash
/auto-test-pytest
```
Expected: all tests pass; no `ImportError` for `regenerate_human_api_profile`.

- [ ] **Step 5: Commit**

```bash
git add -u
git commit -m "chore(knowledge): retire profile_generator.py and A/B migration test"
```

### Task 25: Delete `human_api_profile_parser.py`

**Files:**
- Delete: `src/lib/human_api_profile_parser.py`
- Delete: `tests/test_human_api_profile_parser.py`

Only `context_injector` consumed it; that's swapped (Task 15). Verify no other callers, then delete.

- [ ] **Step 1: Search for callers**

```bash
grep -rn "human_api_profile_parser\|parse_human_api_markdown" --include="*.py" ~/Projects/Augur/
```

Expected: only the file itself + its test. If anything else surfaces, refactor those callers to use the new H2-section parser (likely co-located in `context_injector` or extracted into a shared helper).

- [ ] **Step 2: Delete the module + test**

```bash
git rm src/lib/human_api_profile_parser.py tests/test_human_api_profile_parser.py
```

- [ ] **Step 3: Run suite**

```bash
/auto-test-pytest
```

- [ ] **Step 4: Commit**

```bash
git add -u
git commit -m "chore: retire human_api_profile_parser.py (consumers swapped to H2-section parser in context_injector)"
```

### Task 26: Retire `runtime/memory/HUMAN_API.md`

**Files:**
- Delete: `<runtime_dir>/memory/HUMAN_API.md` (path resolves outside the repo per ADR-270; deletion is a one-time cleanup on the user's machine, not a commit)
- Update: CLAUDE.md or topic docs if any reference the old path

- [ ] **Step 1: Search for stale references**

```bash
grep -rn "HUMAN_API\.md\|runtime/memory/HUMAN_API\|runtime_mem_dir.*HUMAN_API" --include="*.md" --include="*.py" --include="*.ts" --include="*.tsx" --include="*.yaml" ~/Projects/Augur/
```

Any matches outside test files / archived ADRs are stale; fix them to point at `vault/wiki/profile-human-api.md`.

- [ ] **Step 2: Delete the runtime file** (one-time, on the executor's machine — not committed):

```bash
python3 -c "
from src.config.paths import get_runtime_dir
from pathlib import Path
target = get_runtime_dir() / 'memory' / 'HUMAN_API.md'
if target.exists():
    target.unlink()
    print('Removed:', target)
else:
    print('Already absent:', target)
"
```

- [ ] **Step 3: Update agent topic docs** if any reference the runtime path. Run sync_agents afterward to regenerate per-client outputs.

- [ ] **Step 4: Commit** any doc updates from Step 3.

```bash
git add -u
git commit -m "chore(docs): scrub stale HUMAN_API.md path references; profile now at vault/wiki/profile-human-api.md"
```

---

## C9 — Final integration

### Task 27: Update knowledge SKILL.md page list

**Files:**
- Modify: `shared-vault/skills/knowledge/SKILL.md`

Verify `x-augur-dashboard-pages` still includes `/brain/profile`. `/brain/memory` is already there. `/brain/wiki` is owned by ingest skill (added in Task 21). No change here unless audit surfaces an inconsistency.

- [ ] **Step 1: Read manifest**

```bash
grep -A 10 "x-augur-dashboard-pages" shared-vault/skills/knowledge/SKILL.md
```

- [ ] **Step 2: If page list is stale, update it.** Otherwise no-op.

- [ ] **Step 3: Commit only if changed.**

### Task 28: Run full post-write hook chain

- [ ] **Step 1: Regenerate all derived artifacts**

```bash
python .github/scripts/adr_upsert_live.py
python .github/scripts/generate_adr_index.py
python src/lib/index/unified_indexer.py --category adrs
PYTHONPATH=".:shared-vault" python3 -m skills.ai.scripts.sync_agents sync agents all
```

- [ ] **Step 2: Verify** CLAUDE.md's capability table contains the 5 new tools:

```bash
grep -c "wiki-queries-" CLAUDE.md  # expect 5
```

- [ ] **Step 3: Commit** any generated changes (CLAUDE.md, per-client docs):

```bash
git add -u
git commit -m "chore: regenerate agent instructions after wiki-queries MCP tools"
```

### Task 29: Full test sweep

- [ ] **Step 1: Run all auto-loops**

```bash
/auto-test-pytest
/auto-test-build
/auto-test-dashboard
/auto-lint
```

Expected: all pass.

- [ ] **Step 2: If any fail**, fix root cause — do NOT skip, ignore, or rewrite assertions per CLAUDE.md rule 5.

### Task 30: Final browser verification (rule 28)

- [ ] **Step 1: `/dev-build`** clean rebuild.

- [ ] **Step 2: Browser-verify all touched pages**:

| URL | Verify |
|---|---|
| `http://localhost:3000/brain/wiki` | All 4 default queries render. Click "Refresh" on `profile-human-api`. Confirm the run succeeds and the freshness dot turns green. |
| `http://localhost:3000/brain/profile` | Both Voice Profile card(s) (from ADR-729) and the new Memory Profile card (with H2-section blocks: Role / Expertise / Communication Style / Success Criteria / Context Gaps) render. |
| `http://localhost:3000/browse` | Content group → knowledge journey-group shows: Notes, Wiki, Pages (if shipped), Profile, **Memory** (NEW, order 5). Click Memory; cards render. |
| `http://localhost:3000/brain/memory` | MEMORY.md viewer still works (unchanged). |

For each URL, screenshot for the PR description.

- [ ] **Step 3: Commit any final tweaks** if browser verification surfaces visual issues.

### Task 31: Push and open PR

- [ ] **Step 1: Push**

```bash
git push -u origin <branch>
```

- [ ] **Step 2: Open PR** per the `finishing-a-development-branch` skill, with the ADR-731 link, the browser screenshots, and a "What was retired" / "What changed" / "Where to test" summary.

---

## Self-Review

**Spec coverage** (skim each section of the spec, point to a task):
- Spec §3 (decision summary) — Tasks 1–28 collectively
- Spec §4 (memory surface map) — reference only, no tasks
- Spec §5 (single synthesis engine) — Tasks 1–7
- Spec §6 (query registry: schema, CRUD, defaults) — Tasks 1, 8–13
- Spec §7 (data flow) — Tasks 1–10
- Spec §8 (retirement plan) — Tasks 24–26
- Spec §9 (migration sequence) — Tasks 12–28 in order
- Spec §10.1 (`/brain/wiki` page) — Tasks 18–21
- Spec §10.2 (`/brain/profile` refactored) — Task 22
- Spec §10.3 (memory Browse category) — Task 23
- Spec §11 (MCP tool changes) — Tasks 8–11, 16–17
- Spec §12 (edge cases) — covered by tests in Tasks 7, 14, plus the per-query lock test in Task 10

**Placeholder scan:** No "TBD", "TODO", "implement later", or "similar to Task N" in any task. Task 6 ("ask_retention/inbox/linked_folder adapters") and Task 23 (memory transform) are less detailed than the others because they wrap or extend existing pipelines whose exact APIs depend on the implementation — the task still names files, tests required, and expected outcomes.

**Type consistency:**
- `SourceKind` enum (types.ts) matches `SOURCE_KINDS` set (registry.py) — 7 entries each.
- `RunResult` dataclass fields used in Task 7 (`success`, `error`, `output_path`, `tokens_used`, `sections_validated`, `truncated_sources`) match the wrapper return in Task 10 and the test mock in Task 17.
- `QuerySpec` (TS) maps to the Python schema in Task 1 — same field names: `title`, `description`, `prompt_template`, `sources`, `output`, `page_type`, `required_sections`, `refresh_policy`, `system`.
- Required-section names for `profile-human-api` ("Role", "Expertise", "Communication Style", "Success Criteria", "Context Gaps", "Evidence", "Source Basis") are referenced consistently across Task 12 (seed), Task 14 (A/B test), Task 15 (parser), Task 22 (dashboard component).
- `_resolve_workspace_target` continues to handle both `"profile"` and `"report"` file_ids (Task 16) — both point at the same new path.
