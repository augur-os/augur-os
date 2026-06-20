# LLM Wiki Maintenance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform Augur's wiki into an LLM-maintained knowledge base with page CRUD, tag manifests, source scanning, wiki commands (/wiki seed, update, rebuild), nightly autoloop, and knowledge stack consolidation.

**Architecture:** New wiki modules in `skills/ingest/scripts/` (wiki_pages.py, wiki_scanner.py) providing page CRUD and source scanning. 7 new MCP tools registered alongside Phase 1 ingest tools. Agent instructions in command .md files drive when/how the LLM updates pages. Nightly autoloop for editorial passes. Knowledge consolidation moves daily logs and HUMAN_API.md to runtime.

**Tech Stack:** Python 3.11+ (wiki modules), YAML (tags manifest, page frontmatter), FastMCP (MCP tools)

**Spec:** `docs/superpowers/specs/2026-04-11-llm-wiki-maintenance-design.md`

---

## File Structure

### Create

| File | Responsibility |
|------|---------------|
| `skills/ingest/scripts/wiki_pages.py` | Wiki page CRUD: read, write, list, search. Tags manifest rebuild. Index/overview refresh. |
| `skills/ingest/scripts/wiki_scanner.py` | Scan vault, documents, scraper for sources that could feed wiki pages |
| `skills/ingest/scripts/mcp/wiki_tools.py` | 7 wiki MCP tools: wiki-read, wiki-write, wiki-list, wiki-tags, wiki-log, wiki-search, wiki-scan-sources |
| `skills/ingest/augur/tests/test_wiki_pages.py` | Wiki page CRUD tests |
| `skills/ingest/augur/tests/test_wiki_scanner.py` | Source scanner tests |
| `skills/ingest/commands/wiki-seed.md` | `/wiki seed` command — lightweight skeleton bootstrap |
| `skills/ingest/commands/wiki-update.md` | `/wiki update` command — manual wiki update trigger |
| `skills/ingest/commands/wiki-rebuild.md` | `/wiki rebuild` command — full LLM bootstrap |
| `skills/ingest/commands/auto-wiki-maintenance.md` | Nightly autoloop command |

### Modify

| File | Change |
|------|--------|
| `skills/ingest/commands/ingest.md` | Add wiki update step after routing |
| `skills/ingest/scripts/mcp/ingest_tools.py` | Import and call `register_wiki_tools()` |
| `skills/ingest/SKILL.md` | Add wiki MCP tools, commands, autoloop config |
| `skills/rag/scripts/unified_indexer.py` | Add `wiki` category to index `vault/wiki/**/*.md` |

---

## Task 1: Wiki Page CRUD

**Files:**
- Create: `skills/ingest/scripts/wiki_pages.py`
- Test: `skills/ingest/augur/tests/test_wiki_pages.py`

- [ ] **Step 1: Write the failing test**

Create `skills/ingest/augur/tests/test_wiki_pages.py`:

```python
"""Tests for wiki page CRUD operations."""
from pathlib import Path

import yaml

from scripts.wiki_pages import WikiPages


def test_write_and_read(tmp_path):
    wiki_dir = tmp_path / "wiki"
    runtime_dir = tmp_path / "runtime"
    wp = WikiPages(wiki_dir=wiki_dir, runtime_wiki_dir=runtime_dir / "wiki")

    wp.write(
        page="finance/budgeting",
        title="Personal Budgeting",
        tags=["budget", "expenses", "savings"],
        sources=["2026-04-11-budget-report.pdf"],
        body="# Personal Budgeting\n\nTrack monthly expenses...",
        hub="finance",
    )

    result = wp.read("finance/budgeting")
    assert result is not None
    assert result["title"] == "Personal Budgeting"
    assert "budget" in result["tags"]
    assert "budget-report" in result["body"]
    assert result["hub"] == "finance"


def test_write_creates_hub_directory(tmp_path):
    wiki_dir = tmp_path / "wiki"
    runtime_dir = tmp_path / "runtime"
    wp = WikiPages(wiki_dir=wiki_dir, runtime_wiki_dir=runtime_dir / "wiki")

    wp.write(
        page="home-automation/smart-lights",
        title="Smart Lights",
        tags=["hue", "lighting"],
        sources=[],
        body="# Smart Lights\n\nPhilips Hue setup...",
        hub="home-automation",
    )

    assert (wiki_dir / "home-automation" / "smart-lights.md").exists()


def test_write_updates_tags_yaml(tmp_path):
    wiki_dir = tmp_path / "wiki"
    runtime_dir = tmp_path / "runtime"
    wp = WikiPages(wiki_dir=wiki_dir, runtime_wiki_dir=runtime_dir / "wiki")

    wp.write(
        page="dev/architecture",
        title="System Architecture",
        tags=["mcp", "dashboard", "plugin"],
        sources=[],
        body="# Architecture\n\nAugur uses MCP...",
        hub="dev",
    )

    tags_path = runtime_dir / "wiki" / "tags.yaml"
    assert tags_path.exists()
    tags = yaml.safe_load(tags_path.read_text())
    assert "dev/architecture" in tags["pages"]
    assert "mcp" in tags["pages"]["dev/architecture"]["tags"]


def test_write_updates_index(tmp_path):
    wiki_dir = tmp_path / "wiki"
    runtime_dir = tmp_path / "runtime"
    wp = WikiPages(wiki_dir=wiki_dir, runtime_wiki_dir=runtime_dir / "wiki")

    wp.write(
        page="finance/taxes",
        title="Tax Planning",
        tags=["tax"],
        sources=[],
        body="# Tax Planning\n\nAnnual tax strategies...",
        hub="finance",
    )

    index = (wiki_dir / "index.md").read_text()
    assert "Tax Planning" in index


def test_read_nonexistent(tmp_path):
    wp = WikiPages(wiki_dir=tmp_path / "wiki", runtime_wiki_dir=tmp_path / "runtime" / "wiki")
    assert wp.read("nonexistent/page") is None


def test_list_pages(tmp_path):
    wiki_dir = tmp_path / "wiki"
    runtime_dir = tmp_path / "runtime"
    wp = WikiPages(wiki_dir=wiki_dir, runtime_wiki_dir=runtime_dir / "wiki")

    wp.write(page="finance/a", title="A", tags=["x"], sources=[], body="# A", hub="finance")
    wp.write(page="finance/b", title="B", tags=["y"], sources=[], body="# B", hub="finance")
    wp.write(page="dev/c", title="C", tags=["z"], sources=[], body="# C", hub="dev")

    all_pages = wp.list_pages()
    assert len(all_pages) == 3

    finance_pages = wp.list_pages(hub="finance")
    assert len(finance_pages) == 2


def test_read_tags(tmp_path):
    wiki_dir = tmp_path / "wiki"
    runtime_dir = tmp_path / "runtime"
    wp = WikiPages(wiki_dir=wiki_dir, runtime_wiki_dir=runtime_dir / "wiki")

    wp.write(page="dev/x", title="X", tags=["a", "b"], sources=[], body="# X", hub="dev")
    tags = wp.read_tags()
    assert "dev/x" in tags["pages"]


def test_log_entry(tmp_path):
    wiki_dir = tmp_path / "wiki"
    runtime_dir = tmp_path / "runtime"
    wp = WikiPages(wiki_dir=wiki_dir, runtime_wiki_dir=runtime_dir / "wiki")

    wp.log("Ingested 3 finance docs, updated budgeting.md")
    log_path = runtime_dir / "wiki" / "log.md"
    assert log_path.exists()
    assert "finance docs" in log_path.read_text()


def test_log_rolling_window(tmp_path):
    wiki_dir = tmp_path / "wiki"
    runtime_dir = tmp_path / "runtime"
    wp = WikiPages(wiki_dir=wiki_dir, runtime_wiki_dir=runtime_dir / "wiki", max_log_entries=3)

    for i in range(5):
        wp.log(f"Entry {i}")

    log_text = (runtime_dir / "wiki" / "log.md").read_text()
    assert "Entry 4" in log_text
    assert "Entry 3" in log_text
    assert "Entry 2" in log_text
    assert "Entry 0" not in log_text


def test_search_by_content(tmp_path):
    wiki_dir = tmp_path / "wiki"
    runtime_dir = tmp_path / "runtime"
    wp = WikiPages(wiki_dir=wiki_dir, runtime_wiki_dir=runtime_dir / "wiki")

    wp.write(page="health/diet", title="Diet Notes", tags=["nutrition"],
             sources=[], body="# Diet Notes\n\nMediterranean diet is heart-healthy.", hub="health")
    wp.write(page="finance/budget", title="Budget", tags=["money"],
             sources=[], body="# Budget\n\nMonthly expense tracking.", hub="finance")

    matches = wp.search("mediterranean")
    assert len(matches) >= 1
    assert any("diet" in m["page"] for m in matches)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd skills/ingest && PYTHONPATH=. python -m pytest augur/tests/test_wiki_pages.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write wiki_pages.py implementation**

Create `skills/ingest/scripts/wiki_pages.py`:

```python
"""Wiki page CRUD operations.

Manages wiki pages in vault/wiki/ with tag manifest in runtime/wiki/.
Pages use YAML frontmatter with title, type, hub, tags, sources, updated.
"""
from __future__ import annotations

import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


class WikiPages:
    """Read, write, list, and search wiki pages."""

    def __init__(
        self,
        *,
        wiki_dir: Path,
        runtime_wiki_dir: Path,
        max_log_entries: int = 30,
    ) -> None:
        self._wiki_dir = Path(wiki_dir)
        self._runtime_dir = Path(runtime_wiki_dir)
        self._max_log = max_log_entries
        self._wiki_dir.mkdir(parents=True, exist_ok=True)
        self._runtime_dir.mkdir(parents=True, exist_ok=True)

    def write(
        self,
        *,
        page: str,
        title: str,
        tags: list[str],
        sources: list[str],
        body: str,
        hub: str,
    ) -> Path:
        """Write or overwrite a wiki page, then update tags and index."""
        page_path = self._resolve_page_path(page)
        page_path.parent.mkdir(parents=True, exist_ok=True)

        now = datetime.now(tz=timezone.utc).isoformat()
        metadata: dict[str, Any] = {
            "title": title,
            "type": "wiki-page",
            "hub": hub,
            "tags": tags,
            "sources": sources,
            "updated": now,
        }

        yaml_str = yaml.dump(
            metadata, allow_unicode=True, sort_keys=False, default_flow_style=False
        ).rstrip("\n")
        content = f"---\n{yaml_str}\n---\n\n{body.rstrip()}\n"
        page_path.write_text(content, encoding="utf-8")

        self._rebuild_tags()
        self._refresh_index()
        return page_path

    def read(self, page: str) -> dict[str, Any] | None:
        """Read a wiki page. Returns None if not found."""
        page_path = self._resolve_page_path(page)
        if not page_path.exists():
            return None
        meta, body = self._parse_frontmatter(page_path)
        return {
            "title": meta.get("title", page_path.stem),
            "type": meta.get("type", "wiki-page"),
            "hub": meta.get("hub", ""),
            "tags": meta.get("tags", []),
            "sources": meta.get("sources", []),
            "updated": meta.get("updated", ""),
            "body": body,
        }

    def list_pages(self, *, hub: str | None = None) -> list[dict[str, Any]]:
        """List all wiki pages, optionally filtered by hub."""
        pages = []
        for md_file in sorted(self._wiki_dir.rglob("*.md")):
            if md_file.name in ("index.md", "overview.md"):
                continue
            rel = md_file.relative_to(self._wiki_dir)
            page_key = str(rel.with_suffix(""))
            if hub and not page_key.startswith(f"{hub}/"):
                continue
            meta, _ = self._parse_frontmatter(md_file)
            pages.append({
                "page": page_key,
                "title": meta.get("title", md_file.stem),
                "tags": meta.get("tags", []),
                "hub": meta.get("hub", ""),
                "updated": meta.get("updated", ""),
            })
        return pages

    def read_tags(self) -> dict[str, Any]:
        """Read the tags manifest from runtime."""
        tags_path = self._runtime_dir / "tags.yaml"
        if not tags_path.exists():
            return {"pages": {}}
        return yaml.safe_load(tags_path.read_text(encoding="utf-8")) or {"pages": {}}

    def log(self, entry: str) -> None:
        """Append a session summary to the rolling log in runtime."""
        log_path = self._runtime_dir / "log.md"
        now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
        new_entry = f"## [{now}]\n\n{entry}"

        if log_path.exists():
            text = log_path.read_text(encoding="utf-8")
            entries = re.split(r"(?=^## \[)", text, flags=re.MULTILINE)
            entries = [e.strip() for e in entries if e.strip()]
        else:
            entries = []

        entries.insert(0, new_entry)
        entries = entries[: self._max_log]

        log_path.write_text("\n\n".join(entries) + "\n", encoding="utf-8")

    def search(self, query: str, *, tags: list[str] | None = None) -> list[dict[str, Any]]:
        """Search wiki pages by content using ripgrep, optionally filtered by tags."""
        matches = []
        try:
            result = subprocess.run(
                ["rg", "--no-heading", "-l", "-i", query, str(self._wiki_dir)],
                capture_output=True,
                text=True,
                timeout=10,
            )
            for line in result.stdout.strip().splitlines():
                path = Path(line)
                if not path.exists() or path.name in ("index.md", "overview.md"):
                    continue
                rel = path.relative_to(self._wiki_dir)
                page_key = str(rel.with_suffix(""))
                meta, body = self._parse_frontmatter(path)
                page_tags = meta.get("tags", [])
                if tags and not any(t in page_tags for t in tags):
                    continue
                snippet = ""
                for ln in body.splitlines():
                    if query.lower() in ln.lower():
                        snippet = ln.strip()[:200]
                        break
                matches.append({
                    "page": page_key,
                    "title": meta.get("title", path.stem),
                    "score": 1.0,
                    "snippet": snippet,
                })
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        return matches

    def _resolve_page_path(self, page: str) -> Path:
        """Convert a page key like 'finance/budgeting' to a full path."""
        if not page.endswith(".md"):
            page = f"{page}.md"
        return self._wiki_dir / page

    def _parse_frontmatter(self, path: Path) -> tuple[dict[str, Any], str]:
        """Parse YAML frontmatter from a markdown file."""
        text = path.read_text(encoding="utf-8")
        if not text.startswith("---"):
            return {}, text
        parts = text.split("---", 2)
        if len(parts) < 3:
            return {}, text
        meta = yaml.safe_load(parts[1]) or {}
        body = parts[2].strip()
        return meta, body

    def _rebuild_tags(self) -> None:
        """Rebuild tags.yaml from all wiki page frontmatter."""
        pages_data: dict[str, Any] = {}
        for md_file in sorted(self._wiki_dir.rglob("*.md")):
            if md_file.name in ("index.md", "overview.md"):
                continue
            rel = md_file.relative_to(self._wiki_dir)
            page_key = str(rel.with_suffix(""))
            meta, _ = self._parse_frontmatter(md_file)
            pages_data[page_key] = {
                "tags": meta.get("tags", []),
                "title": meta.get("title", md_file.stem),
                "updated": meta.get("updated", ""),
            }
        tags_path = self._runtime_dir / "tags.yaml"
        tags_path.write_text(
            yaml.dump({"pages": pages_data}, allow_unicode=True, sort_keys=False, default_flow_style=False),
            encoding="utf-8",
        )

    def _refresh_index(self) -> None:
        """Rebuild index.md from all wiki pages."""
        hubs: dict[str, list[str]] = {}
        for md_file in sorted(self._wiki_dir.rglob("*.md")):
            if md_file.name in ("index.md", "overview.md"):
                continue
            rel = md_file.relative_to(self._wiki_dir)
            page_key = str(rel.with_suffix(""))
            meta, body = self._parse_frontmatter(md_file)
            title = meta.get("title", md_file.stem)
            hub = meta.get("hub", rel.parts[0] if len(rel.parts) > 1 else "general")
            first_line = ""
            for line in body.splitlines():
                stripped = line.strip()
                if stripped and not stripped.startswith("#"):
                    first_line = stripped[:120]
                    break
            entry = f"- [[{page_key}]] — {first_line}" if first_line else f"- [[{page_key}]]"
            hubs.setdefault(hub, []).append(entry)

        lines = ["# Wiki Index", ""]
        for hub_name in sorted(hubs):
            lines.append(f"## {hub_name.replace('-', ' ').title()}")
            lines.append("")
            lines.extend(hubs[hub_name])
            lines.append("")

        index_path = self._wiki_dir / "index.md"
        index_meta = {"title": "Wiki Index", "type": "wiki-index", "updated": datetime.now(tz=timezone.utc).isoformat()}
        yaml_str = yaml.dump(index_meta, allow_unicode=True, sort_keys=False, default_flow_style=False).rstrip("\n")
        index_path.write_text(f"---\n{yaml_str}\n---\n\n" + "\n".join(lines) + "\n", encoding="utf-8")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd skills/ingest && PYTHONPATH=. python -m pytest augur/tests/test_wiki_pages.py -v`
Expected: All tests PASS

- [ ] **Step 5: Run full test suite for regressions**

Run: `cd skills/ingest && PYTHONPATH=. python -m pytest augur/tests/ -v`
Expected: All 41 + new tests PASS

- [ ] **Step 6: Commit**

```bash
git add skills/ingest/scripts/wiki_pages.py skills/ingest/augur/tests/test_wiki_pages.py
git commit -m "feat(wiki): page CRUD with tag manifest, rolling log, and ripgrep search"
```

---

## Task 2: Source Scanner

**Files:**
- Create: `skills/ingest/scripts/wiki_scanner.py`
- Test: `skills/ingest/augur/tests/test_wiki_scanner.py`

- [ ] **Step 1: Write the failing test**

Create `skills/ingest/augur/tests/test_wiki_scanner.py`:

```python
"""Tests for wiki source scanner."""
from pathlib import Path

from scripts.wiki_scanner import WikiScanner


def test_scan_vault_markdown(tmp_path):
    vault = tmp_path / "vault"
    (vault / "finance" / "data").mkdir(parents=True)
    (vault / "finance" / "data" / "report.md").write_text("# Finance Report\n\nQ3 results.")

    scanner = WikiScanner(vault_dir=vault, documents_dir=tmp_path / "docs")
    sources = scanner.scan()
    assert len(sources) >= 1
    assert any(s["title"] == "Finance Report" for s in sources)


def test_scan_documents(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "invoice.pdf").write_bytes(b"fake pdf")

    scanner = WikiScanner(vault_dir=vault, documents_dir=docs)
    sources = scanner.scan()
    assert any(s["path"].endswith("invoice.pdf") for s in sources)


def test_scan_filters_by_hub(tmp_path):
    vault = tmp_path / "vault"
    (vault / "finance" / "data").mkdir(parents=True)
    (vault / "finance" / "data" / "a.md").write_text("# A")
    (vault / "health" / "data").mkdir(parents=True)
    (vault / "health" / "data" / "b.md").write_text("# B")

    scanner = WikiScanner(vault_dir=vault, documents_dir=tmp_path / "docs")
    finance_only = scanner.scan(hub="finance")
    assert all("finance" in s["path"] for s in finance_only)


def test_scan_skips_wiki_dir(tmp_path):
    vault = tmp_path / "vault"
    (vault / "wiki").mkdir(parents=True)
    (vault / "wiki" / "existing-page.md").write_text("# Wiki Page")
    (vault / "notes").mkdir(parents=True)
    (vault / "notes" / "real-source.md").write_text("# Source")

    scanner = WikiScanner(vault_dir=vault, documents_dir=tmp_path / "docs")
    sources = scanner.scan()
    assert not any("wiki/" in s["path"] for s in sources)
    assert any("real-source" in s["path"] for s in sources)


def test_scan_extracts_title_from_h1(tmp_path):
    vault = tmp_path / "vault"
    (vault / "notes").mkdir(parents=True)
    (vault / "notes" / "meeting.md").write_text("# Q3 Planning Meeting\n\nAgenda items...")

    scanner = WikiScanner(vault_dir=vault, documents_dir=tmp_path / "docs")
    sources = scanner.scan()
    assert any(s["title"] == "Q3 Planning Meeting" for s in sources)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd skills/ingest && PYTHONPATH=. python -m pytest augur/tests/test_wiki_scanner.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write wiki_scanner.py implementation**

Create `skills/ingest/scripts/wiki_scanner.py`:

```python
"""Scan vault, documents, and scraper for sources that could feed wiki pages."""
from __future__ import annotations

from pathlib import Path
from typing import Any


# Extensions worth scanning
_SCANNABLE = {".md", ".txt", ".pdf", ".docx", ".pptx", ".xlsx", ".csv", ".json"}
_SKIP_DIRS = {"wiki", ".git", "__pycache__", "node_modules", ".augur"}


def _extract_title(path: Path) -> str:
    """Extract title from markdown H1 or use filename stem."""
    if path.suffix.lower() in (".md", ".txt"):
        try:
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                stripped = line.strip()
                if stripped.startswith("# "):
                    return stripped[2:].strip()
        except Exception:
            pass
    return path.stem.replace("-", " ").replace("_", " ").title()


def _guess_hub(path: Path, vault_dir: Path) -> str:
    """Guess hub from path relative to vault."""
    try:
        rel = path.relative_to(vault_dir)
        parts = rel.parts
        if len(parts) >= 1 and parts[0] not in _SKIP_DIRS:
            return parts[0]
    except ValueError:
        pass
    return "general"


class WikiScanner:
    """Scan knowledge sources for wiki-eligible content."""

    def __init__(
        self,
        *,
        vault_dir: Path,
        documents_dir: Path,
    ) -> None:
        self._vault_dir = Path(vault_dir)
        self._documents_dir = Path(documents_dir)

    def scan(self, *, hub: str | None = None) -> list[dict[str, Any]]:
        """Scan all sources. Returns list of source dicts.

        Each dict has: path, type, title, hub, format.
        """
        sources: list[dict[str, Any]] = []
        sources.extend(self._scan_dir(self._vault_dir, hub=hub))
        if self._documents_dir.is_dir():
            sources.extend(self._scan_dir(self._documents_dir, hub=hub, default_hub="documents"))
        return sources

    def _scan_dir(
        self,
        root: Path,
        *,
        hub: str | None = None,
        default_hub: str | None = None,
    ) -> list[dict[str, Any]]:
        """Recursively scan a directory for scannable files."""
        if not root.is_dir():
            return []
        results = []
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            if any(skip in path.parts for skip in _SKIP_DIRS):
                continue
            ext = path.suffix.lower()
            if ext not in _SCANNABLE:
                continue
            source_hub = default_hub or _guess_hub(path, self._vault_dir)
            if hub and source_hub != hub:
                continue
            results.append({
                "path": str(path),
                "type": ext.lstrip("."),
                "title": _extract_title(path),
                "hub": source_hub,
                "format": ext.lstrip("."),
            })
        return results
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd skills/ingest && PYTHONPATH=. python -m pytest augur/tests/test_wiki_scanner.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add skills/ingest/scripts/wiki_scanner.py skills/ingest/augur/tests/test_wiki_scanner.py
git commit -m "feat(wiki): source scanner for vault, documents, and scraper content"
```

---

## Task 3: Wiki MCP Tools

**Files:**
- Create: `skills/ingest/scripts/mcp/wiki_tools.py`
- Modify: `skills/ingest/scripts/mcp/ingest_tools.py` (add import)

- [ ] **Step 1: Write wiki_tools.py**

Create `skills/ingest/scripts/mcp/wiki_tools.py`:

```python
"""MCP tool definitions for wiki operations.

Seven stateless tools: wiki-read, wiki-write, wiki-list, wiki-tags,
wiki-log, wiki-search, wiki-scan-sources.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

_skill_root = Path(__file__).resolve().parents[2]
_scripts_dir = _skill_root / "scripts"
if str(_skill_root) not in sys.path:
    sys.path.insert(0, str(_skill_root))
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))

try:
    from augur_mcp.logging import get_entity_logger
    from augur_mcp.annotations import tool_annotations
except ImportError:
    import importlib

    def get_entity_logger(name: str):
        return importlib.import_module("logging").getLogger(name)

    def tool_annotations(annotations: dict) -> dict:
        return annotations

logger = get_entity_logger("wiki")

_wiki_pages = None


def _get_wiki_pages():
    global _wiki_pages
    if _wiki_pages is None:
        from wiki_pages import WikiPages
        try:
            from src.config.paths import get_wiki_dir, get_runtime_dir
            wiki_dir = get_wiki_dir()
            runtime_wiki = get_runtime_dir() / "wiki"
        except ImportError:
            wiki_dir = Path.home() / "Au-vault" / "wiki"
            runtime_wiki = Path.home() / "Library" / "Application Support" / "Augur" / "state" / "wiki"
        _wiki_pages = WikiPages(wiki_dir=wiki_dir, runtime_wiki_dir=runtime_wiki)
    return _wiki_pages


def _get_scanner():
    from wiki_scanner import WikiScanner
    try:
        from src.config.paths import get_vault_dir, get_documents_dir
        return WikiScanner(vault_dir=get_vault_dir(), documents_dir=get_documents_dir())
    except ImportError:
        return WikiScanner(
            vault_dir=Path.home() / "Au-vault",
            documents_dir=Path.home() / "Documents",
        )


def register_wiki_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable[..., Any],
    metrics: Any,
) -> None:
    """Register all 7 wiki MCP tools."""

    @mcp.tool(
        name="wiki-read",
        annotations=tool_annotations({"title": "Wiki Read", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}),
    )
    @mcp_tool_interceptor
    async def wiki_read(page: str = "") -> str:
        """Read a wiki page by hub-relative path (e.g., 'finance/budgeting')."""
        metrics.track_tool("wiki_read", skill="ingest")
        try:
            result = _get_wiki_pages().read(page)
            if result is None:
                return json.dumps({"success": False, "error": f"Page not found: {page}"})
            return json.dumps({"success": True, **result}, indent=2, default=str)
        except Exception as exc:
            return json.dumps({"success": False, "error": str(exc)})

    @mcp.tool(
        name="wiki-write",
        annotations=tool_annotations({"title": "Wiki Write", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False}),
    )
    @mcp_tool_interceptor
    async def wiki_write(
        page: str = "", title: str = "", tags: str = "[]",
        sources: str = "[]", body: str = "", hub: str = "",
    ) -> str:
        """Write or update a wiki page. Creates hub directory if needed."""
        metrics.track_tool("wiki_write", skill="ingest")
        try:
            parsed_tags = json.loads(tags) if isinstance(tags, str) else tags
            parsed_sources = json.loads(sources) if isinstance(sources, str) else sources
            path = _get_wiki_pages().write(
                page=page, title=title, tags=parsed_tags,
                sources=parsed_sources, body=body, hub=hub,
            )
            return json.dumps({"success": True, "path": str(path), "created_or_updated": "ok"}, indent=2)
        except Exception as exc:
            logger.error("wiki-write failed: %s", exc, exc_info=True)
            return json.dumps({"success": False, "error": str(exc)})

    @mcp.tool(
        name="wiki-list",
        annotations=tool_annotations({"title": "Wiki List", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}),
    )
    @mcp_tool_interceptor
    async def wiki_list(hub: str = "") -> str:
        """List all wiki pages, optionally filtered by hub."""
        metrics.track_tool("wiki_list", skill="ingest")
        try:
            pages = _get_wiki_pages().list_pages(hub=hub or None)
            return json.dumps({"success": True, "pages": pages, "count": len(pages)}, indent=2, default=str)
        except Exception as exc:
            return json.dumps({"success": False, "error": str(exc)})

    @mcp.tool(
        name="wiki-tags",
        annotations=tool_annotations({"title": "Wiki Tags", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}),
    )
    @mcp_tool_interceptor
    async def wiki_tags() -> str:
        """Read the tag manifest — maps pages to their tags for fast matching."""
        metrics.track_tool("wiki_tags", skill="ingest")
        try:
            tags = _get_wiki_pages().read_tags()
            return json.dumps({"success": True, **tags}, indent=2, default=str)
        except Exception as exc:
            return json.dumps({"success": False, "error": str(exc)})

    @mcp.tool(
        name="wiki-log",
        annotations=tool_annotations({"title": "Wiki Log", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False}),
    )
    @mcp_tool_interceptor
    async def wiki_log(entry: str = "") -> str:
        """Append a session summary to the wiki log (rolling 30 entries)."""
        metrics.track_tool("wiki_log", skill="ingest")
        try:
            _get_wiki_pages().log(entry)
            return json.dumps({"success": True, "logged_at": "ok"}, indent=2)
        except Exception as exc:
            return json.dumps({"success": False, "error": str(exc)})

    @mcp.tool(
        name="wiki-search",
        annotations=tool_annotations({"title": "Wiki Search", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}),
    )
    @mcp_tool_interceptor
    async def wiki_search(query: str = "", tags: str = "[]") -> str:
        """Search wiki pages by content, optionally filtered by tags."""
        metrics.track_tool("wiki_search", skill="ingest")
        try:
            parsed_tags = json.loads(tags) if isinstance(tags, str) and tags else None
            matches = _get_wiki_pages().search(query, tags=parsed_tags)
            return json.dumps({"success": True, "matches": matches, "count": len(matches)}, indent=2, default=str)
        except Exception as exc:
            return json.dumps({"success": False, "error": str(exc)})

    @mcp.tool(
        name="wiki-scan-sources",
        annotations=tool_annotations({"title": "Wiki Scan Sources", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True}),
    )
    @mcp_tool_interceptor
    async def wiki_scan_sources(hub: str = "") -> str:
        """List all content across vault and documents that could feed wiki pages."""
        metrics.track_tool("wiki_scan_sources", skill="ingest")
        try:
            scanner = _get_scanner()
            sources = scanner.scan(hub=hub or None)
            return json.dumps({"success": True, "sources": sources, "count": len(sources)}, indent=2, default=str)
        except Exception as exc:
            return json.dumps({"success": False, "error": str(exc)})
```

- [ ] **Step 2: Register wiki tools in ingest_tools.py**

Add to the end of `skills/ingest/scripts/mcp/ingest_tools.py`, inside or after `register_ingest_tools()`:

```python
# At the top of the file, add import:
from .wiki_tools import register_wiki_tools

# At the end of register_ingest_tools(), add:
    register_wiki_tools(mcp, mcp_tool_interceptor, metrics)
```

Alternatively, if the MCP server calls `register_ingest_tools()` and expects it to register everything, add the call at the end of that function. The exact wiring depends on how the MCP server discovers skill tools — check the existing pattern.

- [ ] **Step 3: Commit**

```bash
git add skills/ingest/scripts/mcp/wiki_tools.py skills/ingest/scripts/mcp/ingest_tools.py
git commit -m "feat(wiki): 7 MCP tools — wiki-read, wiki-write, wiki-list, wiki-tags, wiki-log, wiki-search, wiki-scan-sources"
```

---

## Task 4: Wiki Commands

**Files:**
- Create: `skills/ingest/commands/wiki-seed.md`
- Create: `skills/ingest/commands/wiki-update.md`
- Create: `skills/ingest/commands/wiki-rebuild.md`
- Create: `skills/ingest/commands/auto-wiki-maintenance.md`
- Modify: `skills/ingest/commands/ingest.md`

- [ ] **Step 1: Write /wiki seed command**

Create `skills/ingest/commands/wiki-seed.md`:

```markdown
---
id: wiki-seed
description: Create skeleton wiki pages from existing vault content without LLM synthesis
skill: ingest
tags: [wiki, bootstrap, seed]
---

Create lightweight skeleton wiki pages from file metadata across vault, documents, and scraper. No LLM needed — instant.

## Steps

1. Call `wiki-scan-sources` to discover all content
2. Group sources by hub (finance, career, health, dev, etc.)
3. For each hub with sources:
   - Create a hub overview page listing what's there
   - Create one page per major source cluster with title, source list, and placeholder body
4. Call `wiki-tags` to verify the tag manifest was rebuilt
5. Report: pages created, hubs populated, sources covered

## Notes

- This is the fast bootstrap. Run `/wiki rebuild` for deep LLM synthesis.
- The nightly autoloop will enrich skeleton pages over time.
- Safe to re-run — overwrites existing skeleton pages but not LLM-synthesized ones (check for body length > 100 chars).
```

- [ ] **Step 2: Write /wiki update command**

Create `skills/ingest/commands/wiki-update.md`:

```markdown
---
id: wiki-update
description: Update wiki pages based on recent session activity and new content
skill: ingest
tags: [wiki, update, knowledge]
---

Review recent activity and update wiki pages with new knowledge.

## Steps

1. Call `wiki-scan-sources` to find content not yet reflected in wiki
2. Call `wiki-tags` to get existing page tags
3. For each source not covered by existing pages:
   - Read the source content (use `ingest-extract` for binary files)
   - Decide which existing wiki pages this content is relevant to (match against tags)
   - For matching pages: `wiki-read` the page, rewrite to incorporate new knowledge, `wiki-write`
   - For new topics: create a new page in the appropriate hub via `wiki-write`
4. Call `wiki-log` with a summary of changes

## Important

- **Rewrite, don't append.** Wiki pages should stay under 500 words. Incorporate new knowledge by rewriting the page concisely.
- **Cross-reference.** When updating a page, add `[[wikilinks]]` to related pages in a "See Also" section.
- **Tag accurately.** Each page's tags should reflect its actual content so future matching works.
```

- [ ] **Step 3: Write /wiki rebuild command**

Create `skills/ingest/commands/wiki-rebuild.md`:

```markdown
---
id: wiki-rebuild
description: Full LLM-driven wiki rebuild from all knowledge sources
skill: ingest
tags: [wiki, rebuild, bootstrap]
---

Scan all knowledge sources and create deeply synthesized wiki pages. Expensive but thorough.

## Usage

```
/wiki rebuild              # all hubs
/wiki rebuild --hub dev    # specific hub only
```

## Steps

1. Call `wiki-scan-sources` (with `--hub` filter if specified)
2. Group sources by topic and hub
3. For each topic cluster:
   - Read all sources in the cluster (use `ingest-extract` for binary files)
   - Synthesize a wiki page that captures the key knowledge across all sources
   - Write via `wiki-write` with appropriate title, tags, sources, and hub
4. After all pages are written, verify `wiki-tags` shows complete manifest
5. Call `wiki-log` with rebuild summary

## Important

- Process hub by hub to keep context focused
- Use parallel tool calls or batch for efficiency within a hub
- Each page should be a concise synthesis (under 500 words), not a concatenation of sources
- Add `[[wikilinks]]` cross-references between related pages
- This replaces all existing wiki content — back up first if needed
```

- [ ] **Step 4: Write autoloop command**

Create `skills/ingest/commands/auto-wiki-maintenance.md`:

```markdown
---
id: auto-wiki-maintenance
description: Nightly editorial pass — rewrite stale pages, merge duplicates, fix cross-references, fill gaps
skill: ingest
tags: [wiki, autoloop, maintenance, editorial]
---

Nightly wiki maintenance autoloop. Full editorial pass at max difficulty.

## Difficulty Levels

| Level | Scope |
|-------|-------|
| 1 | Structural: fix broken `[[wikilinks]]`, rebuild tags.yaml, refresh index.md |
| 2 | + detect stale pages (sources newer than page), rewrite them |
| 3 | + detect source gaps (content with no wiki coverage), create pages |
| 4 | + detect duplicate pages (overlapping tags/content), merge them |
| 5 | + full editorial: rewrite for clarity, enforce 500-word page budget, consistency across hubs |

## Steps (at current difficulty)

1. Call `wiki-tags` to get current manifest
2. Call `wiki-scan-sources` to get all available sources
3. **Structural checks (level 1+):**
   - Read every page, validate all `[[wikilinks]]` resolve to real pages
   - Fix broken links (update or remove)
   - Rebuild tags.yaml and index.md
4. **Staleness detection (level 2+):**
   - Compare page `updated` timestamps against source file mtimes
   - Pages with newer sources: `wiki-read`, rewrite with current sources, `wiki-write`
5. **Gap detection (level 3+):**
   - Find sources not covered by any wiki page tags
   - Create new pages for uncovered topics
6. **Duplicate merging (level 4+):**
   - Find pages with >50% tag overlap
   - Read both, merge into the more comprehensive one, delete the other
7. **Editorial pass (level 5):**
   - Read each page, rewrite for clarity and conciseness
   - Split pages exceeding 500 words into sub-topics
   - Ensure cross-hub consistency (same entity described consistently)
8. Call `wiki-log` with maintenance summary
9. Report findings and evolution gaps

## Evolution Gaps

When all checks pass at max difficulty, report:
- Source types not yet indexed (e.g., audio transcripts, images)
- Hubs with < 3 pages (sparse coverage)
- Pages with no cross-references (isolated knowledge)
- Sources ingested in last 7 days with no wiki coverage
```

- [ ] **Step 5: Modify /ingest command — add wiki update step**

Add to the end of `skills/ingest/commands/ingest.md`, before the MCP Tools section:

```markdown
## Wiki Update (after routing)

After all items are routed to the vault:
1. Call `wiki-tags` to get the tag manifest
2. For each ingested item, extract key topics from the content
3. Match topics against existing wiki page tags
4. For matching pages: `wiki-read` → rewrite to incorporate new knowledge → `wiki-write`
5. For unmatched topics: create a new page in the appropriate hub via `wiki-write`
6. Call `wiki-log` with a session summary
```

- [ ] **Step 6: Commit**

```bash
git add skills/ingest/commands/wiki-seed.md skills/ingest/commands/wiki-update.md skills/ingest/commands/wiki-rebuild.md skills/ingest/commands/auto-wiki-maintenance.md skills/ingest/commands/ingest.md
git commit -m "feat(wiki): commands — /wiki seed, update, rebuild, and auto-wiki-maintenance autoloop"
```

---

## Task 5: Update SKILL.md

**Files:**
- Modify: `skills/ingest/SKILL.md`

- [ ] **Step 1: Add wiki tools, commands, and autoloop to SKILL.md**

Add the 7 wiki MCP tools to `x-augur-mcp-tools` list:

```yaml
x-augur-mcp-tools:
- ingest-process
- ingest-extract
- ingest-rename
- ingest-route
- ingest-status
- ingest-history
- ingest-config
- wiki-read
- wiki-write
- wiki-list
- wiki-tags
- wiki-log
- wiki-search
- wiki-scan-sources
```

Add the autoloop entry to `x-augur-config.contributions`:

```yaml
x-augur-config:
  contributions:
    actions:
    - id: ingest-content
      label: Ingest Content
      dispatch: ide
      prompt: "Process the dropped content through the ingest pipeline"
    - id: wiki-update
      label: Update Wiki
      dispatch: ide
      prompt: "Update wiki pages based on recent activity"
```

Update the body to document wiki tools and commands alongside existing ingest docs.

- [ ] **Step 2: Commit**

```bash
git add skills/ingest/SKILL.md
git commit -m "feat(wiki): update SKILL.md with wiki MCP tools, commands, and autoloop"
```

---

## Task 6: RAG Indexer — Add Wiki Category

**Files:**
- Modify: `skills/rag/scripts/unified_indexer.py`

- [ ] **Step 1: Read the existing indexer to find where categories are defined**

Read `skills/rag/scripts/unified_indexer.py` and find the category list and the pattern for adding a new category scanner.

- [ ] **Step 2: Add wiki category**

Add a `index_wiki()` function that scans `vault/wiki/**/*.md` and creates pointer markdown files in `rag/wiki/{hub}/{page}.md`. Follow the existing pattern used by other category scanners (e.g., `index_documents()`).

The function should:
- Iterate `wiki_dir.rglob("*.md")`, skip index.md and overview.md
- For each page: parse frontmatter, extract title/tags/hub/sources
- Write a pointer entry to `rag_dir / "wiki" / hub / f"{page_name}.md"` with frontmatter

- [ ] **Step 3: Register the category in the main reindex function**

Add `index_wiki()` to the category dispatch in `reindex_all()` or equivalent.

- [ ] **Step 4: Commit**

```bash
git add skills/rag/scripts/unified_indexer.py
git commit -m "feat(wiki): add wiki category to RAG unified indexer"
```

---

## Task 7: Knowledge Consolidation — Path Migrations

**Files:**
- Modify: paths referenced by `auto-memory-sync`, `memory-curate`, `memory-profile-regenerate`

- [ ] **Step 1: Identify all path references to daily logs and HUMAN_API.md**

Search for:
```bash
grep -rn "daily" skills/knowledge/scripts/ --include="*.py" | grep -i "memory\|log\|vault"
grep -rn "HUMAN_API" skills/knowledge/scripts/ --include="*.py"
grep -rn "memory/daily" skills/ --include="*.py"
```

- [ ] **Step 2: Update daily log path**

Change daily log writes from `get_memory_dir() / "daily"` to `get_runtime_dir() / "memory" / "daily"`. Update all scripts that read/write daily logs.

- [ ] **Step 3: Update HUMAN_API.md path**

Change from `get_memory_dir() / "HUMAN_API.md"` to `get_runtime_dir() / "memory" / "HUMAN_API.md"`.

- [ ] **Step 4: Run tests to verify no regressions**

Run: `cd skills/ingest && PYTHONPATH=. python -m pytest augur/tests/ -v`

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor(knowledge): move daily logs and HUMAN_API.md to runtime (knowledge ring consolidation)"
```

---

## Dependencies Between Tasks

```
Task 1 (Wiki Pages CRUD)
  ↓
Task 2 (Source Scanner) ──→ Task 3 (MCP Tools) ──→ Task 4 (Commands) ──→ Task 5 (SKILL.md)
                                                                            ↑
Task 6 (RAG Indexer) ──────────────────────────────────────────────────────┘
Task 7 (Knowledge Consolidation) ─────────────────────────────────────────┘
```

Tasks 2, 6, and 7 can run in parallel after Task 1.
Task 3 depends on Tasks 1 and 2.
Task 4 depends on Task 3.
Task 5 depends on Tasks 4 and 6.
