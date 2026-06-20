# Augur Pages — HTML Artifacts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Unify Claude-generated HTML artifacts, user-saved static HTMLs, and live MCP-first dashboard pages under one Browse ViewMode (`pages`) with sidecar metadata, a `/artifact/<slug>` Next.js route with sandboxed iframe, a vault-backed pin store, and a `/save artifact` promote flow.

**Architecture:** Six new MCP tools under `src/mcp/augur_framework/tools/infrastructure/` (artifacts.py + pins.py) feed Browse via the existing `useMcpQuery` plumbing. The `dashboard-surfaces` ViewMode is renamed to `pages` (with a legacy alias for back-compat) and `transformPages()` is extended to merge two sources: existing `pluginTabRegistry` (live) plus a new `artifacts-list` MCP tool (saved + generated). Static artifacts open at `/artifact/[slug]` — an Augur-chrome wrapper around a sandboxed iframe. Pinning is global, vault-backed (`Au-vault/system/pins.yaml`), and rendered as a strip at the top of Browse.

**Tech Stack:** Python 3.11+ (MCP tools, pytest), TypeScript (Next.js dashboard, vitest-style test runner already configured), pnpm, uv.

**Spec:** `docs/superpowers/specs/2026-05-10-augur-pages-html-artifacts-design.md`

---

## File Structure

### Created

| Path | Responsibility |
|---|---|
| `src/mcp/augur_framework/tools/infrastructure/artifacts.py` | `save-artifact`, `artifacts-reindex`, `artifacts-list` MCP tools + sidecar I/O |
| `src/mcp/augur_framework/tools/infrastructure/pins.py` | `pin-add`, `pin-remove`, `pin-list` MCP tools + atomic pins.yaml I/O |
| `tests/test_artifacts_tool.py` | Pytest for sidecar parser/writer, slug derivation, list/reindex/save behavior |
| `tests/test_pins_tool.py` | Pytest for pin tools (atomicity, ordering, idempotency) |
| `apps/dashboard/lib/browse/pages-merge.ts` | Pure helper merging live + artifact sources into `BrowseItem[]` |
| `apps/dashboard/lib/browse/pages-merge.test.ts` | Vitest for `pages-merge` |
| `apps/dashboard/app/artifact/[slug]/page.tsx` | Chrome wrapper (server component) + iframe |
| `apps/dashboard/app/artifact/[slug]/ArtifactChrome.tsx` | Client component for the chrome bar (Pin button, postMessage handler) |
| `apps/dashboard/app/api/artifact/[slug]/raw/route.ts` | GET handler that streams the HTML file with CSP headers |

### Modified

| Path | Change |
|---|---|
| `apps/dashboard/lib/browse/types.ts` | Rename `dashboard-surfaces` → `pages` in ViewMode union; add `BrowseItem.metadata.kind: "live" \| "saved" \| "generated"` |
| `apps/dashboard/lib/browse/viewModeMapping.ts` | Flip `LEGACY_VIEW_MODE_MAP` so `dashboard-surfaces → pages`; update `indexCategoryForViewMode` |
| `apps/dashboard/lib/browse/transforms.ts` | Rename `transformPages` to call out to `pages-merge.ts`; tag entries with `kind: "live"` |
| `apps/dashboard/app/(views)/browse/BrowseToolbar.tsx` | Kind filter pill (4 chips) |
| `apps/dashboard/app/(views)/browse/BrowseContentGrid.tsx` | Kind chip badge on cards; pinned strip at top |
| `apps/dashboard/app/(views)/browse/useBrowseState.ts` | Fetch pin list + pinned-first sort |
| `shared-vault/skills/augur-core/commands/save.md` | Document `/save artifact <path>` form |
| `src/mcp/augur_framework/tools/infrastructure/__init__.py` | Register artifacts + pins tools |

---

## Task 1: Sidecar parser/writer

**Files:**
- Create: `src/mcp/augur_framework/tools/infrastructure/artifacts.py`
- Test: `tests/test_artifacts_tool.py`

- [ ] **Step 1: Write the failing tests for sidecar I/O**

```python
# tests/test_artifacts_tool.py
"""Tests for artifacts MCP tool: sidecar I/O, slug derivation, list/reindex."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.mcp.augur_framework.tools.infrastructure.artifacts import (
    Sidecar,
    derive_slug,
    derive_title,
    read_sidecar,
    write_sidecar,
)


def test_write_and_read_sidecar_roundtrip(tmp_path: Path) -> None:
    sidecar_path = tmp_path / "foo.meta.yaml"
    sc = Sidecar(
        slug="foo",
        title="Foo Title",
        kind="generated",
        hub="career",
        source={"type": "brainstorm", "session": "brainstorm/abc", "origin_path": ".superpowers/brainstorm/abc/foo.html"},
        tags=["onboarding"],
        created_at="2026-05-10T00:00:00Z",
        promoted_at="2026-05-10T00:01:00Z",
        notes="",
    )
    write_sidecar(sidecar_path, sc)
    loaded = read_sidecar(sidecar_path)
    assert loaded == sc


def test_derive_title_from_html_title_tag() -> None:
    html = "<html><head><title>My Title</title></head><body></body></html>"
    assert derive_title(html, fallback="x.html") == "My Title"


def test_derive_title_falls_back_to_h1() -> None:
    html = "<html><body><h1>From H1</h1></body></html>"
    assert derive_title(html, fallback="x.html") == "From H1"


def test_derive_title_falls_back_to_filename() -> None:
    assert derive_title("<html></html>", fallback="my-file.html") == "my-file"


def test_derive_slug_from_title() -> None:
    assert derive_slug(title="Onboarding — 6 Directions") == "onboarding-6-directions"


def test_derive_slug_from_filename_when_title_empty() -> None:
    assert derive_slug(title="", filename="resume-coleman.html") == "resume-coleman"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_artifacts_tool.py -v`
Expected: FAIL with `ImportError: cannot import name 'Sidecar'` (module doesn't exist yet).

- [ ] **Step 3: Implement minimal sidecar I/O + helpers**

```python
# src/mcp/augur_framework/tools/infrastructure/artifacts.py
"""Artifacts MCP tools: save-artifact, artifacts-reindex, artifacts-list.

Storage model (per ADR-pending: Augur Pages):
- New artifacts: Au-docs/<hub>/artifacts/<slug>.html + <slug>.meta.yaml
- Existing scattered files: kept-as-is, sidecar generated next to them.
- Ephemeral .superpowers/brainstorm/ files: never indexed unless promoted.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class Sidecar:
    slug: str
    title: str
    kind: str  # "generated" | "saved"
    hub: str
    source: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    created_at: str = ""
    promoted_at: str = ""
    notes: str = ""


def write_sidecar(path: Path, sidecar: Sidecar) -> None:
    """Write a sidecar YAML at `path` using the frontmatter-style block."""
    payload = asdict(sidecar)
    body = yaml.safe_dump(payload, sort_keys=False, allow_unicode=True).strip()
    path.write_text(f"---\n{body}\n---\n", encoding="utf-8")


def read_sidecar(path: Path) -> Sidecar:
    text = path.read_text(encoding="utf-8")
    if text.startswith("---"):
        # strip the frontmatter fences
        parts = text.split("---", 2)
        body = parts[2] if len(parts) >= 3 else parts[1]
    else:
        body = text
    data: dict[str, Any] = yaml.safe_load(body) or {}
    return Sidecar(**data)


_TITLE_RE = re.compile(r"<title>([^<]+)</title>", re.IGNORECASE)
_H1_RE = re.compile(r"<h1[^>]*>([^<]+)</h1>", re.IGNORECASE)


def derive_title(html: str, fallback: str) -> str:
    m = _TITLE_RE.search(html)
    if m:
        return m.group(1).strip()
    m = _H1_RE.search(html)
    if m:
        return m.group(1).strip()
    return Path(fallback).stem


_SLUG_NON_WORD = re.compile(r"[^a-z0-9]+")


def derive_slug(*, title: str = "", filename: str = "") -> str:
    candidate = title or Path(filename).stem
    s = candidate.lower()
    s = _SLUG_NON_WORD.sub("-", s).strip("-")
    return s or "artifact"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_artifacts_tool.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/mcp/augur_framework/tools/infrastructure/artifacts.py tests/test_artifacts_tool.py
git commit -m "feat(artifacts): sidecar I/O + slug/title derivation"
```

---

## Task 2: artifacts-list MCP tool (returns empty by default)

**Files:**
- Modify: `src/mcp/augur_framework/tools/infrastructure/artifacts.py`
- Modify: `tests/test_artifacts_tool.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_artifacts_tool.py`:

```python
from src.mcp.augur_framework.tools.infrastructure.artifacts import (
    artifacts_list_impl,
)


def test_artifacts_list_empty_when_no_files(tmp_path: Path) -> None:
    result = artifacts_list_impl(docs_dir=tmp_path)
    assert result == {"artifacts": []}


def test_artifacts_list_returns_html_with_sidecar(tmp_path: Path) -> None:
    hub_dir = tmp_path / "career" / "artifacts"
    hub_dir.mkdir(parents=True)
    html = hub_dir / "spec-x.html"
    html.write_text("<html><title>Spec X</title></html>", encoding="utf-8")
    sc = Sidecar(slug="spec-x", title="Spec X", kind="saved", hub="career")
    write_sidecar(hub_dir / "spec-x.meta.yaml", sc)

    result = artifacts_list_impl(docs_dir=tmp_path)
    assert len(result["artifacts"]) == 1
    entry = result["artifacts"][0]
    assert entry["slug"] == "spec-x"
    assert entry["title"] == "Spec X"
    assert entry["kind"] == "saved"
    assert entry["hub"] == "career"
    assert entry["url"] == "/artifact/spec-x"
    assert entry["path"].endswith("career/artifacts/spec-x.html")


def test_artifacts_list_skips_html_without_sidecar(tmp_path: Path) -> None:
    (tmp_path / "orphan.html").write_text("<html></html>", encoding="utf-8")
    result = artifacts_list_impl(docs_dir=tmp_path)
    assert result["artifacts"] == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_artifacts_tool.py::test_artifacts_list_empty_when_no_files -v`
Expected: FAIL `ImportError: cannot import name 'artifacts_list_impl'`.

- [ ] **Step 3: Implement `artifacts_list_impl`**

Append to `src/mcp/augur_framework/tools/infrastructure/artifacts.py`:

```python
def _iter_artifact_files(docs_dir: Path):
    """Yield (html_path, sidecar_path) for every *.html with a sibling .meta.yaml."""
    for html_path in docs_dir.rglob("*.html"):
        sidecar_path = html_path.with_suffix("").with_suffix(".meta.yaml")
        if sidecar_path.exists():
            yield html_path, sidecar_path


def artifacts_list_impl(docs_dir: Path) -> dict[str, Any]:
    """Return Browse-shape entries for every sidecar-backed HTML under `docs_dir`."""
    entries: list[dict[str, Any]] = []
    for html_path, sidecar_path in _iter_artifact_files(docs_dir):
        sc = read_sidecar(sidecar_path)
        entries.append(
            {
                "slug": sc.slug,
                "title": sc.title,
                "kind": sc.kind,
                "hub": sc.hub,
                "url": f"/artifact/{sc.slug}",
                "path": str(html_path),
                "tags": sc.tags,
                "promoted_at": sc.promoted_at,
                "created_at": sc.created_at,
            }
        )
    return {"artifacts": entries}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_artifacts_tool.py -v`
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add src/mcp/augur_framework/tools/infrastructure/artifacts.py tests/test_artifacts_tool.py
git commit -m "feat(artifacts): artifacts-list returns sidecar-backed HTML entries"
```

---

## Task 3: artifacts-reindex MCP tool

**Files:**
- Modify: `src/mcp/augur_framework/tools/infrastructure/artifacts.py`
- Modify: `tests/test_artifacts_tool.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_artifacts_tool.py`:

```python
from src.mcp.augur_framework.tools.infrastructure.artifacts import (
    artifacts_reindex_impl,
)


def test_reindex_creates_sidecar_for_html_without_one(tmp_path: Path) -> None:
    career = tmp_path / "career" / "resumes"
    career.mkdir(parents=True)
    html = career / "resume.html"
    html.write_text("<html><title>My Resume</title></html>", encoding="utf-8")

    result = artifacts_reindex_impl(docs_dir=tmp_path, dry_run=False)

    sidecar = career / "resume.meta.yaml"
    assert sidecar.exists()
    sc = read_sidecar(sidecar)
    assert sc.slug == "my-resume"
    assert sc.title == "My Resume"
    assert sc.kind == "saved"
    assert sc.hub == "career"
    assert result["created"] == 1


def test_reindex_dry_run_does_not_write(tmp_path: Path) -> None:
    html = tmp_path / "venture-augur" / "logos" / "concepts.html"
    html.parent.mkdir(parents=True)
    html.write_text("<html><title>Concepts</title></html>", encoding="utf-8")

    result = artifacts_reindex_impl(docs_dir=tmp_path, dry_run=True)

    assert not html.with_suffix("").with_suffix(".meta.yaml").exists()
    assert result["created"] == 0
    assert result["proposed"] == 1
    assert result["proposals"][0]["hub"] == "venture-augur"


def test_reindex_skips_html_with_existing_sidecar(tmp_path: Path) -> None:
    html = tmp_path / "career" / "artifacts" / "x.html"
    html.parent.mkdir(parents=True)
    html.write_text("<html></html>", encoding="utf-8")
    sc = Sidecar(slug="x", title="X", kind="saved", hub="career")
    write_sidecar(html.with_suffix("").with_suffix(".meta.yaml"), sc)

    result = artifacts_reindex_impl(docs_dir=tmp_path, dry_run=False)
    assert result["created"] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_artifacts_tool.py::test_reindex_creates_sidecar_for_html_without_one -v`
Expected: FAIL `ImportError: cannot import name 'artifacts_reindex_impl'`.

- [ ] **Step 3: Implement `artifacts_reindex_impl`**

Append to `src/mcp/augur_framework/tools/infrastructure/artifacts.py`:

```python
from datetime import datetime, timezone


def _hub_from_path(path: Path, docs_dir: Path) -> str:
    """First path segment under docs_dir is treated as the hub."""
    rel = path.relative_to(docs_dir)
    parts = rel.parts
    return parts[0] if parts else "uncategorized"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def artifacts_reindex_impl(
    *,
    docs_dir: Path,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Scan docs_dir for *.html without a sidecar; generate sidecars (or propose)."""
    created = 0
    proposed = 0
    proposals: list[dict[str, Any]] = []

    for html_path in docs_dir.rglob("*.html"):
        sidecar_path = html_path.with_suffix("").with_suffix(".meta.yaml")
        if sidecar_path.exists():
            continue
        html_text = html_path.read_text(encoding="utf-8", errors="replace")
        title = derive_title(html_text, fallback=html_path.name)
        slug = derive_slug(title=title, filename=html_path.name)
        hub = _hub_from_path(html_path, docs_dir)
        sc = Sidecar(
            slug=slug,
            title=title,
            kind="saved",
            hub=hub,
            source={"type": "manual", "origin_path": str(html_path)},
            created_at=_now_iso(),
            promoted_at=_now_iso(),
        )
        proposal = {
            "html": str(html_path),
            "sidecar": str(sidecar_path),
            "slug": slug,
            "title": title,
            "hub": hub,
        }
        if dry_run:
            proposed += 1
            proposals.append(proposal)
        else:
            write_sidecar(sidecar_path, sc)
            created += 1

    return {"created": created, "proposed": proposed, "proposals": proposals}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_artifacts_tool.py -v`
Expected: 11 passed.

- [ ] **Step 5: Commit**

```bash
git add src/mcp/augur_framework/tools/infrastructure/artifacts.py tests/test_artifacts_tool.py
git commit -m "feat(artifacts): artifacts-reindex generates sidecars for unsidecarred HTML"
```

---

## Task 4: --import flag for backlog brainstorm HTMLs

**Files:**
- Modify: `src/mcp/augur_framework/tools/infrastructure/artifacts.py`
- Modify: `tests/test_artifacts_tool.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_artifacts_tool.py`:

```python
def test_import_copies_brainstorm_html_into_docs_dir(tmp_path: Path) -> None:
    brain_root = tmp_path / "brainstorm" / "27346-1777974008" / "content"
    brain_root.mkdir(parents=True)
    src = brain_root / "spec-written.html"
    src.write_text("<html><title>Spec Written</title></html>", encoding="utf-8")

    docs = tmp_path / "docs"
    docs.mkdir()

    result = artifacts_reindex_impl(
        docs_dir=docs,
        dry_run=False,
        import_glob=str(brain_root / "*.html"),
        import_hub="career",
    )
    assert result["imported"] == 1
    target = docs / "career" / "artifacts" / "spec-written.html"
    assert target.exists()
    sidecar = target.with_suffix("").with_suffix(".meta.yaml")
    assert sidecar.exists()
    sc = read_sidecar(sidecar)
    assert sc.kind == "generated"
    assert sc.hub == "career"
    assert sc.source.get("type") == "brainstorm"
    assert sc.source.get("origin_path", "").endswith("spec-written.html")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_artifacts_tool.py::test_import_copies_brainstorm_html_into_docs_dir -v`
Expected: FAIL — `artifacts_reindex_impl()` doesn't accept `import_glob` yet.

- [ ] **Step 3: Extend `artifacts_reindex_impl` to support import**

Replace the existing `artifacts_reindex_impl` body with:

```python
import glob as _glob
import shutil


def artifacts_reindex_impl(
    *,
    docs_dir: Path,
    dry_run: bool = False,
    import_glob: str | None = None,
    import_hub: str = "uncategorized",
) -> dict[str, Any]:
    """Scan docs_dir for *.html without a sidecar; optionally import external HTMLs."""
    created = 0
    proposed = 0
    imported = 0
    proposals: list[dict[str, Any]] = []

    if import_glob:
        for src in (Path(p) for p in _glob.glob(import_glob)):
            if not src.is_file():
                continue
            target_dir = docs_dir / import_hub / "artifacts"
            target_dir.mkdir(parents=True, exist_ok=True)
            target = target_dir / src.name
            sidecar_path = target.with_suffix("").with_suffix(".meta.yaml")
            html_text = src.read_text(encoding="utf-8", errors="replace")
            title = derive_title(html_text, fallback=src.name)
            slug = derive_slug(title=title, filename=src.name)
            sc = Sidecar(
                slug=slug,
                title=title,
                kind="generated",
                hub=import_hub,
                source={
                    "type": "brainstorm",
                    "origin_path": str(src),
                },
                created_at=_now_iso(),
                promoted_at=_now_iso(),
            )
            if dry_run:
                proposals.append(
                    {"html": str(target), "slug": slug, "title": title, "hub": import_hub}
                )
                proposed += 1
            else:
                shutil.copy2(src, target)
                write_sidecar(sidecar_path, sc)
                imported += 1

    for html_path in docs_dir.rglob("*.html"):
        sidecar_path = html_path.with_suffix("").with_suffix(".meta.yaml")
        if sidecar_path.exists():
            continue
        html_text = html_path.read_text(encoding="utf-8", errors="replace")
        title = derive_title(html_text, fallback=html_path.name)
        slug = derive_slug(title=title, filename=html_path.name)
        hub = _hub_from_path(html_path, docs_dir)
        sc = Sidecar(
            slug=slug,
            title=title,
            kind="saved",
            hub=hub,
            source={"type": "manual", "origin_path": str(html_path)},
            created_at=_now_iso(),
            promoted_at=_now_iso(),
        )
        proposal = {
            "html": str(html_path),
            "sidecar": str(sidecar_path),
            "slug": slug,
            "title": title,
            "hub": hub,
        }
        if dry_run:
            proposed += 1
            proposals.append(proposal)
        else:
            write_sidecar(sidecar_path, sc)
            created += 1

    return {
        "created": created,
        "proposed": proposed,
        "imported": imported,
        "proposals": proposals,
    }
```

- [ ] **Step 4: Run all artifacts tests**

Run: `uv run pytest tests/test_artifacts_tool.py -v`
Expected: 12 passed.

- [ ] **Step 5: Commit**

```bash
git add src/mcp/augur_framework/tools/infrastructure/artifacts.py tests/test_artifacts_tool.py
git commit -m "feat(artifacts): --import flag for brainstorm backlog migration"
```

---

## Task 5: save-artifact MCP tool

**Files:**
- Modify: `src/mcp/augur_framework/tools/infrastructure/artifacts.py`
- Modify: `tests/test_artifacts_tool.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_artifacts_tool.py`:

```python
from src.mcp.augur_framework.tools.infrastructure.artifacts import (
    save_artifact_impl,
)


def test_save_artifact_writes_file_and_sidecar(tmp_path: Path) -> None:
    src = tmp_path / "src" / "draft.html"
    src.parent.mkdir()
    src.write_text("<html><title>Draft</title></html>", encoding="utf-8")
    docs = tmp_path / "docs"
    docs.mkdir()

    result = save_artifact_impl(
        docs_dir=docs,
        source_path=src,
        hub="career",
        slug=None,
        title=None,
        tags=["draft"],
    )
    assert result["slug"] == "draft"
    assert result["target"].endswith("career/artifacts/draft.html")
    target = Path(result["target"])
    assert target.exists()
    sidecar = target.with_suffix("").with_suffix(".meta.yaml")
    assert sidecar.exists()
    sc = read_sidecar(sidecar)
    assert sc.tags == ["draft"]
    assert sc.kind == "saved"


def test_save_artifact_appends_suffix_on_slug_collision(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    target_dir = docs / "career" / "artifacts"
    target_dir.mkdir(parents=True)
    (target_dir / "x.html").write_text("<html></html>", encoding="utf-8")
    write_sidecar(target_dir / "x.meta.yaml", Sidecar(slug="x", title="X", kind="saved", hub="career"))

    src = tmp_path / "x.html"
    src.write_text("<html><title>X</title></html>", encoding="utf-8")
    result = save_artifact_impl(
        docs_dir=docs,
        source_path=src,
        hub="career",
        slug="x",
        title="X",
        tags=[],
    )
    assert result["slug"] == "x-2"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_artifacts_tool.py::test_save_artifact_writes_file_and_sidecar -v`
Expected: FAIL `ImportError: cannot import name 'save_artifact_impl'`.

- [ ] **Step 3: Implement `save_artifact_impl`**

Append to `src/mcp/augur_framework/tools/infrastructure/artifacts.py`:

```python
def _resolve_unique_slug(target_dir: Path, slug: str) -> str:
    candidate = slug
    counter = 2
    while (target_dir / f"{candidate}.html").exists() or (
        target_dir / f"{candidate}.meta.yaml"
    ).exists():
        candidate = f"{slug}-{counter}"
        counter += 1
    return candidate


def save_artifact_impl(
    *,
    docs_dir: Path,
    source_path: Path,
    hub: str,
    slug: str | None,
    title: str | None,
    tags: list[str] | None,
) -> dict[str, Any]:
    """Promote a single HTML into Au-docs/<hub>/artifacts/<slug>.html + sidecar."""
    html_text = source_path.read_text(encoding="utf-8", errors="replace")
    resolved_title = title or derive_title(html_text, fallback=source_path.name)
    base_slug = slug or derive_slug(title=resolved_title, filename=source_path.name)
    target_dir = docs_dir / hub / "artifacts"
    target_dir.mkdir(parents=True, exist_ok=True)
    final_slug = _resolve_unique_slug(target_dir, base_slug)
    target = target_dir / f"{final_slug}.html"
    sidecar_path = target.with_suffix("").with_suffix(".meta.yaml")

    shutil.copy2(source_path, target)
    is_brainstorm = ".superpowers/brainstorm/" in str(source_path) or "/brainstorm/" in str(source_path)
    sc = Sidecar(
        slug=final_slug,
        title=resolved_title,
        kind="generated" if is_brainstorm else "saved",
        hub=hub,
        source={
            "type": "brainstorm" if is_brainstorm else "manual",
            "origin_path": str(source_path),
        },
        tags=list(tags or []),
        created_at=_now_iso(),
        promoted_at=_now_iso(),
    )
    write_sidecar(sidecar_path, sc)
    return {"slug": final_slug, "target": str(target), "sidecar": str(sidecar_path)}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_artifacts_tool.py -v`
Expected: 14 passed.

- [ ] **Step 5: Commit**

```bash
git add src/mcp/augur_framework/tools/infrastructure/artifacts.py tests/test_artifacts_tool.py
git commit -m "feat(artifacts): save-artifact promotes single HTML with collision-safe slug"
```

---

## Task 6: Pin store MCP tools (pin-add / pin-remove / pin-list)

**Files:**
- Create: `src/mcp/augur_framework/tools/infrastructure/pins.py`
- Test: `tests/test_pins_tool.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_pins_tool.py
"""Tests for pin MCP tools (atomic pins.yaml I/O)."""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.mcp.augur_framework.tools.infrastructure.pins import (
    pin_add_impl,
    pin_list_impl,
    pin_remove_impl,
)


def test_pin_list_empty(tmp_path: Path) -> None:
    pins_path = tmp_path / "pins.yaml"
    assert pin_list_impl(pins_path=pins_path) == {"pins": []}


def test_pin_add_creates_entry(tmp_path: Path) -> None:
    pins_path = tmp_path / "pins.yaml"
    pin_add_impl(
        pins_path=pins_path,
        url="/artifact/foo",
        title="Foo",
        kind="saved",
        hub="career",
    )
    result = pin_list_impl(pins_path=pins_path)
    assert len(result["pins"]) == 1
    assert result["pins"][0]["url"] == "/artifact/foo"
    assert result["pins"][0]["title"] == "Foo"


def test_pin_add_is_idempotent_on_url(tmp_path: Path) -> None:
    pins_path = tmp_path / "pins.yaml"
    for _ in range(3):
        pin_add_impl(
            pins_path=pins_path,
            url="/brain/inbox",
            title="Brain Inbox",
            kind="live",
            hub="brain",
        )
    assert len(pin_list_impl(pins_path=pins_path)["pins"]) == 1


def test_pin_remove_drops_by_url(tmp_path: Path) -> None:
    pins_path = tmp_path / "pins.yaml"
    pin_add_impl(pins_path=pins_path, url="/a", title="A", kind="saved", hub="brain")
    pin_add_impl(pins_path=pins_path, url="/b", title="B", kind="saved", hub="brain")
    pin_remove_impl(pins_path=pins_path, url="/a")
    pins = pin_list_impl(pins_path=pins_path)["pins"]
    assert len(pins) == 1
    assert pins[0]["url"] == "/b"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_pins_tool.py -v`
Expected: FAIL `ModuleNotFoundError: No module named '...pins'`.

- [ ] **Step 3: Implement pin tools**

```python
# src/mcp/augur_framework/tools/infrastructure/pins.py
"""Pin store MCP tools: pin-add, pin-remove, pin-list.

Storage: Au-vault/system/pins.yaml. Single-user, last-write-wins.
Atomicity: write-rename pattern.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_pins(pins_path: Path) -> list[dict[str, Any]]:
    if not pins_path.exists():
        return []
    data = yaml.safe_load(pins_path.read_text(encoding="utf-8")) or {}
    return list(data.get("pins") or [])


def _save_pins(pins_path: Path, pins: list[dict[str, Any]]) -> None:
    pins_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = pins_path.with_suffix(pins_path.suffix + ".tmp")
    body = yaml.safe_dump({"pins": pins}, sort_keys=False, allow_unicode=True)
    tmp.write_text(body, encoding="utf-8")
    os.replace(tmp, pins_path)


def pin_list_impl(*, pins_path: Path) -> dict[str, Any]:
    return {"pins": _load_pins(pins_path)}


def pin_add_impl(
    *,
    pins_path: Path,
    url: str,
    title: str,
    kind: str,
    hub: str,
) -> dict[str, Any]:
    pins = _load_pins(pins_path)
    if any(p.get("url") == url for p in pins):
        return {"added": False, "url": url}
    pins.append(
        {
            "url": url,
            "title": title,
            "kind": kind,
            "hub": hub,
            "pinnedAt": _now_iso(),
        }
    )
    _save_pins(pins_path, pins)
    return {"added": True, "url": url}


def pin_remove_impl(*, pins_path: Path, url: str) -> dict[str, Any]:
    pins = _load_pins(pins_path)
    new_pins = [p for p in pins if p.get("url") != url]
    if len(new_pins) == len(pins):
        return {"removed": False, "url": url}
    _save_pins(pins_path, new_pins)
    return {"removed": True, "url": url}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_pins_tool.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/mcp/augur_framework/tools/infrastructure/pins.py tests/test_pins_tool.py
git commit -m "feat(pins): pin-add / pin-remove / pin-list MCP tool implementations"
```

---

## Task 7: Register artifacts + pins tools with FastMCP

**Files:**
- Modify: `src/mcp/augur_framework/tools/infrastructure/__init__.py`
- Modify: `src/mcp/augur_framework/tools/__init__.py`

- [ ] **Step 1: Read current registration entrypoint**

Read `src/mcp/augur_framework/tools/__init__.py` and `src/mcp/augur_framework/tools/infrastructure/__init__.py` to find the existing `register_infrastructure_tools` pattern. Tools are wired by passing the `FastMCP` instance and calling `mcp.tool()` decorators or `mcp.add_tool()` per tool.

- [ ] **Step 2: Add registration helpers in artifacts.py and pins.py**

Append to `src/mcp/augur_framework/tools/infrastructure/artifacts.py`:

```python
def register_artifacts_tools(mcp, *, get_docs_dir) -> None:
    """Wire save-artifact, artifacts-reindex, artifacts-list onto the MCP server."""

    @mcp.tool(name="save-artifact")
    async def save_artifact(
        source_path: str,
        hub: str,
        slug: str | None = None,
        title: str | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        return save_artifact_impl(
            docs_dir=get_docs_dir(),
            source_path=Path(source_path),
            hub=hub,
            slug=slug,
            title=title,
            tags=tags,
        )

    @mcp.tool(name="artifacts-reindex")
    async def artifacts_reindex(
        dry_run: bool = False,
        import_glob: str | None = None,
        import_hub: str = "uncategorized",
    ) -> dict[str, Any]:
        return artifacts_reindex_impl(
            docs_dir=get_docs_dir(),
            dry_run=dry_run,
            import_glob=import_glob,
            import_hub=import_hub,
        )

    @mcp.tool(name="artifacts-list")
    async def artifacts_list() -> dict[str, Any]:
        return artifacts_list_impl(docs_dir=get_docs_dir())
```

Append to `src/mcp/augur_framework/tools/infrastructure/pins.py`:

```python
def register_pin_tools(mcp, *, get_pins_path) -> None:
    """Wire pin-add / pin-remove / pin-list onto the MCP server."""

    @mcp.tool(name="pin-add")
    async def pin_add(url: str, title: str, kind: str, hub: str) -> dict[str, Any]:
        return pin_add_impl(
            pins_path=get_pins_path(), url=url, title=title, kind=kind, hub=hub
        )

    @mcp.tool(name="pin-remove")
    async def pin_remove(url: str) -> dict[str, Any]:
        return pin_remove_impl(pins_path=get_pins_path(), url=url)

    @mcp.tool(name="pin-list")
    async def pin_list() -> dict[str, Any]:
        return pin_list_impl(pins_path=get_pins_path())
```

- [ ] **Step 3: Wire into infrastructure registration**

In `src/mcp/augur_framework/tools/infrastructure/__init__.py` (existing file), add at the end of `register_infrastructure_tools(...)`:

```python
from src.mcp.augur_framework.tools.infrastructure.artifacts import (
    register_artifacts_tools,
)
from src.mcp.augur_framework.tools.infrastructure.pins import (
    register_pin_tools,
)
from src.config.paths import get_documents_dir, get_vault_dir


def _docs_dir():
    return get_documents_dir()


def _pins_path():
    return get_vault_dir() / "system" / "pins.yaml"


register_artifacts_tools(mcp, get_docs_dir=_docs_dir)
register_pin_tools(mcp, get_pins_path=_pins_path)
```

(Place the imports at the top of the file with the other imports; place the registration calls inside the existing `register_infrastructure_tools` function.)

- [ ] **Step 4: Verify importability**

Run: `uv run python -c "from src.mcp.augur_framework.tools.infrastructure.artifacts import register_artifacts_tools; from src.mcp.augur_framework.tools.infrastructure.pins import register_pin_tools; print('ok')"`
Expected: `ok`

- [ ] **Step 5: Run full test suite**

Run: `/auto-test-pytest` (or `uv run pytest tests/test_artifacts_tool.py tests/test_pins_tool.py -v`)
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/mcp/augur_framework/tools/infrastructure/
git commit -m "feat(mcp): register artifacts + pins tools with augur-framework"
```

---

## Task 8: Run backlog migration (one-shot)

**Files:** none — this is an operational step that creates sidecars in `Au-docs/`.

- [ ] **Step 1: Dry-run scan of Au-docs existing files**

Run from a Claude Code session:

```
mcp call augur-framework artifacts-reindex {"dry_run": true}
```

Expected: a list of `proposals` for every existing HTML in `Au-docs/` that lacks a sidecar (resumes, presentations, collateral, website-working, etc.). Inspect titles and hubs; flag any wrong path-derived hubs.

- [ ] **Step 2: Commit Au-docs sidecars**

Run:

```
mcp call augur-framework artifacts-reindex {}
```

Expected: `{"created": <N>, "imported": 0}` where `<N>` matches the number of files in step 1.

- [ ] **Step 3: Dry-run import of brainstorm HTMLs**

Run:

```
mcp call augur-framework artifacts-reindex {"dry_run": true, "import_glob": ".superpowers/brainstorm/*/content/*.html", "import_hub": "dev"}
```

Expected: `proposed` count matches `find .superpowers/brainstorm -name "*.html" | wc -l` (~30+).

Review the proposed slugs and hubs. The default `import_hub` is `dev`; the user may run additional imports per hub for cleaner organization.

- [ ] **Step 4: Commit brainstorm imports (if review passes)**

Run:

```
mcp call augur-framework artifacts-reindex {"import_glob": ".superpowers/brainstorm/*/content/*.html", "import_hub": "dev"}
```

Expected: `{"imported": <N>, "created": 0}`.

- [ ] **Step 5: Verify in vault**

Run: `ls ~/Projects/Au-docs/dev/artifacts/ | head -10`
Expected: a list of imported HTML files plus `.meta.yaml` siblings.

- [ ] **Step 6: Commit nothing here (filesystem ops outside repo); document in session notes**

This task touches `Au-docs/` (external) and brainstorm temp files; no repo commit.

---

## Task 9: Rename ViewMode dashboard-surfaces → pages + legacy alias

**Files:**
- Modify: `apps/dashboard/lib/browse/types.ts`
- Modify: `apps/dashboard/lib/browse/viewModeMapping.ts`
- Test: `apps/dashboard/lib/browse/viewModeMapping.test.ts` (create)

- [ ] **Step 1: Write failing test for legacy alias**

```typescript
// apps/dashboard/lib/browse/viewModeMapping.test.ts
import { describe, expect, it } from "vitest";
import { normalizeRequestedViewMode, indexCategoryForViewMode } from "./viewModeMapping";

describe("viewModeMapping — pages rename", () => {
  it("normalizes 'pages' to the pages ViewMode", () => {
    expect(normalizeRequestedViewMode("pages")).toBe("pages");
  });

  it("aliases legacy 'dashboard-surfaces' to 'pages' for back-compat", () => {
    expect(normalizeRequestedViewMode("dashboard-surfaces")).toBe("pages");
  });

  it("indexCategoryForViewMode maps 'pages' to the 'pages' index", () => {
    expect(indexCategoryForViewMode("pages")).toBe("pages");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/dashboard && pnpm vitest run lib/browse/viewModeMapping.test.ts`
Expected: FAIL — `pages` is not in the ViewMode union; `LEGACY_VIEW_MODE_MAP` still maps `pages → dashboard-surfaces` (wrong direction).

- [ ] **Step 3: Update the ViewMode union and BrowseItem metadata**

In `apps/dashboard/lib/browse/types.ts`, find the `ViewMode` union and replace `"dashboard-surfaces"` with `"pages"`:

```typescript
export type ViewMode =
  | "inbox"
  | "notes"
  | "sources"
  | "wiki"
  | "skills"
  | "actions"
  | "prompts"
  | "adrs"
  | "integrations"
  | "extensions-bundles"
  | "scheduled-executions"
  | "drafts"
  | "archive"
  | "pages"            // was "dashboard-surfaces"
  | "agent-profiles"
  | "workflow-definitions"
  | "commands"
  | "mcp-servers"
  | "mcp-tools"
  | "api-routes"
  | "scripts"
  | "tests"
  | "logs"
  | "system-metadata";
```

Add a `kind` field to whatever metadata shape `BrowseItem` already declares. Find the `BrowseItem` interface in the same file and ensure its `metadata` (likely `Record<string, string>`) is documented as accepting `kind: "live" | "saved" | "generated"`. If `metadata` is loosely typed, no schema change is needed — just document by comment:

```typescript
// metadata.kind: "live" | "saved" | "generated" — used by Browse to render kind chip
```

If `BROWSE_CATEGORIES` references `dashboard-surfaces` by id, rename to `pages` there as well. Search:

Run: `grep -n '"dashboard-surfaces"' apps/dashboard/lib/browse/types.ts`

Replace any matched id strings.

- [ ] **Step 4: Update the legacy map**

In `apps/dashboard/lib/browse/viewModeMapping.ts`, replace the existing `LEGACY_VIEW_MODE_MAP`:

```typescript
const LEGACY_VIEW_MODE_MAP: Record<string, ViewMode> = {
  // back-compat: old links keep working
  "dashboard-surfaces": "pages",
  vault: "notes",
  documents: "sources",
  agents: "agent-profiles",
  workflows: "workflow-definitions",
};
```

Update `indexCategoryForViewMode` so `pages` returns `"pages"`:

```typescript
export function indexCategoryForViewMode(mode: ViewMode): string {
  if (mode === "pages") return "pages";
  if (mode === "agent-profiles") return "agents";
  if (mode === "workflow-definitions") return "workflows";
  if (VAULT_JOURNEY_MODES.has(mode)) return "vault";
  return mode;
}
```

- [ ] **Step 5: Search for and fix all remaining references to `dashboard-surfaces`**

Run: `cd apps/dashboard && grep -rn '"dashboard-surfaces"' --include='*.ts' --include='*.tsx'`

Replace each match with `"pages"`. Common locations: `transforms.ts`, `useBrowseState.ts`, `BrowseToolbar.tsx`, anywhere a string literal hard-codes the old name.

- [ ] **Step 6: Run vitest and the full TS build**

Run: `cd apps/dashboard && pnpm vitest run lib/browse/viewModeMapping.test.ts`
Expected: 3 passed.

Run: `/auto-test-build` (or `cd apps/dashboard && pnpm build`)
Expected: build green.

- [ ] **Step 7: Commit**

```bash
git add apps/dashboard/lib/browse/
git commit -m "refactor(browse): rename dashboard-surfaces → pages ViewMode + legacy alias"
```

---

## Task 10: Extract pages-merge.ts helper

**Files:**
- Create: `apps/dashboard/lib/browse/pages-merge.ts`
- Create: `apps/dashboard/lib/browse/pages-merge.test.ts`

- [ ] **Step 1: Write failing tests**

```typescript
// apps/dashboard/lib/browse/pages-merge.test.ts
import { describe, expect, it } from "vitest";
import { mergePagesSources, type LiveTabEntry, type ArtifactEntry } from "./pages-merge";

describe("mergePagesSources", () => {
  it("returns empty when both inputs empty", () => {
    expect(mergePagesSources([], [])).toEqual([]);
  });

  it("tags live entries with kind='live'", () => {
    const live: LiveTabEntry[] = [
      { label: "Brain Inbox", href: "/brain/inbox", hub: "brain", icon: "Inbox", pageType: "yaml" },
    ];
    const out = mergePagesSources(live, []);
    expect(out).toHaveLength(1);
    expect(out[0].metadata?.kind).toBe("live");
    expect(out[0].path).toBe("/brain/inbox");
  });

  it("tags artifacts with their kind from sidecar", () => {
    const artifacts: ArtifactEntry[] = [
      {
        slug: "spec-x",
        title: "Spec X",
        kind: "generated",
        hub: "career",
        url: "/artifact/spec-x",
        path: "/abs/path/spec-x.html",
        tags: [],
        promoted_at: "2026-05-10T00:00:00Z",
        created_at: "2026-05-08T00:00:00Z",
      },
    ];
    const out = mergePagesSources([], artifacts);
    expect(out).toHaveLength(1);
    expect(out[0].metadata?.kind).toBe("generated");
    expect(out[0].title).toBe("Spec X");
  });

  it("merges both sources preserving live first then artifacts", () => {
    const out = mergePagesSources(
      [{ label: "Live", href: "/brain", hub: "brain", icon: "X", pageType: "tsx" }],
      [
        {
          slug: "a",
          title: "A",
          kind: "saved",
          hub: "career",
          url: "/artifact/a",
          path: "/p/a.html",
          tags: [],
          promoted_at: "",
          created_at: "",
        },
      ],
    );
    expect(out.map((it) => it.metadata?.kind)).toEqual(["live", "saved"]);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/dashboard && pnpm vitest run lib/browse/pages-merge.test.ts`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement `pages-merge.ts`**

```typescript
// apps/dashboard/lib/browse/pages-merge.ts
import type { BrowseItem } from "./types";

export interface LiveTabEntry {
  label: string;
  href: string;
  hub: string;
  icon: string;
  pageType: "tsx" | "yaml";
  skillId?: string;
}

export interface ArtifactEntry {
  slug: string;
  title: string;
  kind: "saved" | "generated";
  hub: string;
  url: string;
  path: string;
  tags: string[];
  promoted_at: string;
  created_at: string;
}

export function mergePagesSources(
  live: LiveTabEntry[],
  artifacts: ArtifactEntry[],
): BrowseItem[] {
  const out: BrowseItem[] = [];

  for (const tab of live) {
    out.push({
      id: `live:${tab.href}`,
      title: tab.label,
      path: tab.href,
      icon: tab.icon,
      metadata: {
        kind: "live",
        hub: tab.hub,
        page_type: tab.pageType,
      },
    } as BrowseItem);
  }

  for (const a of artifacts) {
    out.push({
      id: `artifact:${a.slug}`,
      title: a.title,
      path: a.url,
      metadata: {
        kind: a.kind,
        hub: a.hub,
        promoted_at: a.promoted_at,
        created_at: a.created_at,
        tags: a.tags.join(","),
      },
    } as BrowseItem);
  }

  return out;
}
```

Note: the actual `BrowseItem` shape may have additional required fields. After running the failing test, adjust the cast / fill required fields based on the type errors that vitest reports. Keep the merge function stable; only adapt to the existing schema.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd apps/dashboard && pnpm vitest run lib/browse/pages-merge.test.ts`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/lib/browse/pages-merge.ts apps/dashboard/lib/browse/pages-merge.test.ts
git commit -m "feat(browse): pages-merge helper unifies live tabs + static artifacts"
```

---

## Task 11: Wire artifacts-list MCP into useBrowseState + transformPages

**Files:**
- Modify: `apps/dashboard/lib/browse/transforms.ts`
- Modify: `apps/dashboard/app/(views)/browse/useBrowseState.ts`

- [ ] **Step 1: Locate `transformPages()` in transforms.ts**

Run: `grep -n "transformPages" apps/dashboard/lib/browse/transforms.ts`

The function currently transforms a single source. Replace its body to call `mergePagesSources` from Task 10. Imports:

```typescript
import { mergePagesSources, type LiveTabEntry, type ArtifactEntry } from "./pages-merge";
```

- [ ] **Step 2: Update `transformPages` to accept artifacts**

Change the signature to accept `{ liveTabs, artifacts }` (or whatever names match the existing function shape). Replace the body with a single call to `mergePagesSources`. Preserve the existing return type.

If the function is currently called like `transformPages(getAllPages())`, update the call site to also pass `artifacts` from the new MCP query:

```typescript
const pages = transformPages({
  liveTabs: getAllPages(),
  artifacts: artifactsResponse?.artifacts ?? [],
});
```

- [ ] **Step 3: Add the artifacts MCP query in useBrowseState**

In `apps/dashboard/app/(views)/browse/useBrowseState.ts`, near the existing `useMcpQuery` calls, add:

```typescript
const artifactsResponse = useMcpQuery<{ artifacts: ArtifactEntry[] }>({
  tool: "artifacts-list",
  enabled: viewMode === "pages",
});
```

(Match the existing `useMcpQuery` signature in this file — adapt `tool` / `args` keys as needed.)

Pass `artifactsResponse?.data?.artifacts ?? []` into the `transformPages(...)` call.

- [ ] **Step 4: Run dashboard build**

Run: `/auto-test-build`
Expected: build green; no type errors.

- [ ] **Step 5: Run vitest**

Run: `cd apps/dashboard && pnpm vitest run lib/browse/`
Expected: all browse tests pass.

- [ ] **Step 6: Commit**

```bash
git add apps/dashboard/lib/browse/transforms.ts apps/dashboard/app/\(views\)/browse/useBrowseState.ts
git commit -m "feat(browse): merge artifacts-list MCP into pages ViewMode"
```

---

## Task 12: Kind filter pill in BrowseToolbar

**Files:**
- Modify: `apps/dashboard/app/(views)/browse/BrowseToolbar.tsx`

- [ ] **Step 1: Locate where filters render in BrowseToolbar**

Run: `grep -n "category\|filter\|chip" apps/dashboard/app/\(views\)/browse/BrowseToolbar.tsx | head -20`

Find the section that renders existing filter chips. The new kind pill should appear only when `viewMode === "pages"`.

- [ ] **Step 2: Add the kind filter component**

Inside `BrowseToolbar.tsx`, conditional on `viewMode === "pages"`, render a 4-chip pill:

```tsx
{viewMode === "pages" && (
  <div role="tablist" aria-label="Filter by kind" className="flex gap-1 rounded-lg border border-[var(--border-color)] p-0.5">
    {(["all", "live", "saved", "generated"] as const).map((k) => (
      <button
        key={k}
        type="button"
        role="tab"
        aria-selected={kindFilter === k}
        onClick={() => setKindFilter(k)}
        className={`px-2.5 py-1 text-xs rounded-md transition ${
          kindFilter === k
            ? "bg-[var(--accent-primary)]/15 text-[var(--accent-primary)]"
            : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
        }`}
      >
        {k[0].toUpperCase() + k.slice(1)}
      </button>
    ))}
  </div>
)}
```

`kindFilter` and `setKindFilter` come from `useBrowseState` — add them in the next step.

- [ ] **Step 3: Add kindFilter state in useBrowseState**

In `useBrowseState.ts`:

```typescript
const [kindFilter, setKindFilter] = useState<"all" | "live" | "saved" | "generated">("all");
```

After the items array is constructed from `transformPages`, filter:

```typescript
const filteredItems = useMemo(() => {
  if (viewMode !== "pages" || kindFilter === "all") return items;
  return items.filter((it) => it.metadata?.kind === kindFilter);
}, [items, viewMode, kindFilter]);
```

Return `kindFilter`, `setKindFilter`, and use `filteredItems` (instead of `items`) for the grid.

- [ ] **Step 4: Run dashboard build**

Run: `/auto-test-build`
Expected: green.

- [ ] **Step 5: Browser-verify the filter (per Augur Rule 28)**

Open dashboard at `localhost:3000/browse?category=pages` via Chrome MCP. Confirm:
- The kind pill appears only on Pages view.
- Clicking each chip narrows the grid to entries with the matching `kind`.

- [ ] **Step 6: Commit**

```bash
git add apps/dashboard/app/\(views\)/browse/BrowseToolbar.tsx apps/dashboard/app/\(views\)/browse/useBrowseState.ts
git commit -m "feat(browse): kind filter pill on Pages ViewMode"
```

---

## Task 13: Kind chip badge on BrowseContentGrid card

**Files:**
- Modify: `apps/dashboard/app/(views)/browse/BrowseContentGrid.tsx`

- [ ] **Step 1: Locate where each card renders metadata badges**

Run: `grep -n "metadata\|badge\|chip" apps/dashboard/app/\(views\)/browse/BrowseContentGrid.tsx | head -10`

- [ ] **Step 2: Add a kind chip near the title**

Inside the card render, when `item.metadata?.kind` is set, render:

```tsx
{item.metadata?.kind && (
  <span
    className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wide ${
      item.metadata.kind === "live"
        ? "bg-emerald-500/15 text-emerald-300"
        : item.metadata.kind === "saved"
        ? "bg-sky-500/15 text-sky-300"
        : "bg-amber-500/15 text-amber-300"
    }`}
  >
    {item.metadata.kind}
  </span>
)}
```

(Color tokens: live=emerald, saved=sky, generated=amber. Adjust to match the theme conventions in the existing file.)

- [ ] **Step 3: Run dashboard build**

Run: `/auto-test-build`
Expected: green.

- [ ] **Step 4: Browser-verify (Rule 28)**

Open `/browse?category=pages` and confirm chips appear on each card with the right colors per kind.

- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/app/\(views\)/browse/BrowseContentGrid.tsx
git commit -m "feat(browse): kind chip badge on Pages cards"
```

---

## Task 14: /api/artifact/[slug]/raw route — file streamer

**Files:**
- Create: `apps/dashboard/app/api/artifact/[slug]/raw/route.ts`

- [ ] **Step 1: Create the route**

```typescript
// apps/dashboard/app/api/artifact/[slug]/raw/route.ts
import { NextResponse } from "next/server";
import { promises as fs } from "node:fs";
import path from "node:path";
import { mcpCall } from "@/lib/mcp/client";

export async function GET(
  _req: Request,
  { params }: { params: { slug: string } },
) {
  const slug = params.slug;
  const list = await mcpCall<{ artifacts: Array<{ slug: string; path: string }> }>(
    "augur-framework",
    "artifacts-list",
    {},
  );
  const entry = list?.artifacts?.find((a) => a.slug === slug);
  if (!entry) {
    return NextResponse.json({ error: "not found" }, { status: 404 });
  }

  // Defensive: prevent path traversal — only serve files inside Au-docs.
  const docsDir = process.env.AUGUR_DOCS_DIR ?? "";
  if (docsDir && !path.resolve(entry.path).startsWith(path.resolve(docsDir))) {
    return NextResponse.json({ error: "forbidden" }, { status: 403 });
  }

  const html = await fs.readFile(entry.path, "utf-8");
  return new NextResponse(html, {
    status: 200,
    headers: {
      "Content-Type": "text/html; charset=utf-8",
      "Content-Security-Policy":
        "default-src 'self' 'unsafe-inline' 'unsafe-eval' data: blob:; frame-ancestors 'self'",
      "X-Frame-Options": "SAMEORIGIN",
    },
  });
}
```

- [ ] **Step 2: Smoke-test with a real artifact**

Run the dashboard via `/dev-build`. After the backlog migration in Task 8, pick a known slug from `mcp call augur-framework artifacts-list {}` output and:

Run: `curl -i http://localhost:3000/api/artifact/<known-slug>/raw | head -20`
Expected: `HTTP/1.1 200 OK` + the HTML body. Test a non-existent slug → 404.

- [ ] **Step 3: Commit**

```bash
git add apps/dashboard/app/api/artifact/
git commit -m "feat(artifact): raw HTML streamer route at /api/artifact/[slug]/raw"
```

---

## Task 15: /artifact/[slug] route — chrome wrapper + iframe

**Files:**
- Create: `apps/dashboard/app/artifact/[slug]/page.tsx`
- Create: `apps/dashboard/app/artifact/[slug]/ArtifactChrome.tsx`

- [ ] **Step 1: Server component for the page**

```tsx
// apps/dashboard/app/artifact/[slug]/page.tsx
import { notFound } from "next/navigation";
import { mcpCall } from "@/lib/mcp/client";
import { ArtifactChrome } from "./ArtifactChrome";

interface ArtifactSummary {
  slug: string;
  title: string;
  kind: "saved" | "generated";
  hub: string;
  url: string;
  path: string;
  tags: string[];
  promoted_at: string;
  created_at: string;
}

export default async function ArtifactPage({ params }: { params: { slug: string } }) {
  const list = await mcpCall<{ artifacts: ArtifactSummary[] }>(
    "augur-framework",
    "artifacts-list",
    {},
  );
  const entry = list?.artifacts?.find((a) => a.slug === params.slug);
  if (!entry) notFound();

  return (
    <div className="flex h-screen flex-col">
      <ArtifactChrome
        slug={entry.slug}
        title={entry.title}
        kind={entry.kind}
        hub={entry.hub}
        url={`/artifact/${entry.slug}`}
        sourcePath={entry.path}
      />
      <iframe
        src={`/api/artifact/${entry.slug}/raw`}
        sandbox="allow-scripts allow-same-origin allow-popups"
        className="flex-1 w-full border-0"
        title={entry.title}
      />
    </div>
  );
}
```

- [ ] **Step 2: Client component for the chrome bar**

```tsx
// apps/dashboard/app/artifact/[slug]/ArtifactChrome.tsx
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { mcpCall } from "@/lib/mcp/client";

interface Props {
  slug: string;
  title: string;
  kind: "saved" | "generated";
  hub: string;
  url: string;
  sourcePath: string;
}

export function ArtifactChrome({ slug, title, kind, hub, url, sourcePath }: Props) {
  const [pinned, setPinned] = useState(false);

  useEffect(() => {
    mcpCall<{ pins: Array<{ url: string }> }>("augur-framework", "pin-list", {}).then(
      (r) => setPinned(Boolean(r?.pins?.some((p) => p.url === url))),
    );
  }, [url]);

  useEffect(() => {
    function onMessage(ev: MessageEvent) {
      const data = ev.data as { type?: string; payload?: unknown };
      if (data?.type === "augur:copy" && typeof data.payload === "string") {
        navigator.clipboard.writeText(data.payload).catch(() => {});
      }
    }
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, []);

  async function togglePin() {
    if (pinned) {
      await mcpCall("augur-framework", "pin-remove", { url });
      setPinned(false);
    } else {
      await mcpCall("augur-framework", "pin-add", { url, title, kind, hub });
      setPinned(true);
    }
  }

  return (
    <div className="flex items-center gap-3 border-b border-[var(--border-color)] bg-[var(--bg-card)] px-3 py-2">
      <Link href="/browse?category=pages" className="text-xs text-[var(--text-secondary)] hover:text-[var(--text-primary)]">
        ← Browse
      </Link>
      <span className="font-semibold text-sm">{title}</span>
      <Link href={`/${hub}`} className="rounded bg-[var(--accent-primary)]/15 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-[var(--accent-primary)]">
        {hub}
      </Link>
      <span className="text-[10px] uppercase tracking-wide text-[var(--text-secondary)]">{kind}</span>
      <span className="ml-auto flex items-center gap-2">
        <button type="button" onClick={togglePin} className="text-xs">
          {pinned ? "★ Pinned" : "☆ Pin"}
        </button>
        <a href={`/api/artifact/${slug}/raw`} target="_blank" rel="noreferrer" className="text-xs text-[var(--text-secondary)] hover:text-[var(--text-primary)]">
          Open external
        </a>
        <span className="text-[10px] text-[var(--text-secondary)]" title={sourcePath}>
          source
        </span>
      </span>
    </div>
  );
}
```

- [ ] **Step 3: Browser-verify (Rule 28)**

Run `/dev-build`, then in Chrome MCP open `http://localhost:3000/artifact/<known-slug>` and confirm:
- Chrome bar renders with title, hub chip, kind, Pin button, "Open external".
- Iframe renders the HTML and any embedded scripts run (sliders, etc.).
- Clicking Pin toggles state and persists across reload.

- [ ] **Step 4: Commit**

```bash
git add apps/dashboard/app/artifact/
git commit -m "feat(artifact): /artifact/[slug] chrome wrapper + sandboxed iframe"
```

---

## Task 16: Pinned strip at top of BrowseContentGrid

**Files:**
- Modify: `apps/dashboard/app/(views)/browse/BrowseContentGrid.tsx`
- Modify: `apps/dashboard/app/(views)/browse/useBrowseState.ts`

- [ ] **Step 1: Add pin query in useBrowseState**

In `useBrowseState.ts`:

```typescript
import type { BrowseItem } from "@/lib/browse/types";

interface PinEntry {
  url: string;
  title: string;
  kind: "live" | "saved" | "generated";
  hub: string;
  pinnedAt: string;
}

const pinsResponse = useMcpQuery<{ pins: PinEntry[] }>({
  tool: "pin-list",
  enabled: true,
});

const pins: PinEntry[] = pinsResponse?.data?.pins ?? [];

const pinnedItems: BrowseItem[] = useMemo(
  () =>
    pins
      .map((p) => items.find((it) => it.path === p.url))
      .filter((x): x is BrowseItem => Boolean(x)),
  [pins, items],
);
```

Return `pinnedItems` and `pins` from the hook.

- [ ] **Step 2: Render the pinned strip in BrowseContentGrid**

Above the main grid, when `pinnedItems.length > 0` and `viewMode === "pages"` (or always — confirm with the existing UX once visible):

```tsx
{pinnedItems.length > 0 && (
  <section className="mb-4">
    <h3 className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
      Pinned
    </h3>
    <div className="grid grid-cols-2 gap-2 md:grid-cols-3 lg:grid-cols-4">
      {pinnedItems.map((it) => (
        <BrowseCard key={`pin-${it.id}`} item={it} />
      ))}
    </div>
  </section>
)}
```

(Reuse whatever component currently renders a single browse card. If the file inlines the card markup, extract a small `BrowseCard` component first to keep DRY — that's a small refactor, not new design.)

- [ ] **Step 3: Browser-verify (Rule 28)**

Open `/browse?category=pages`. Confirm:
- A "Pinned" section appears above the main grid when at least one pin exists.
- Pinning from the artifact chrome (Task 15) shows up here on next reload.
- Unpinning removes the card from the strip.

- [ ] **Step 4: Commit**

```bash
git add apps/dashboard/app/\(views\)/browse/
git commit -m "feat(browse): pinned strip above main grid on Pages ViewMode"
```

---

## Task 17: /save artifact slash command extension

**Files:**
- Modify: `shared-vault/skills/augur-core/commands/save.md`

- [ ] **Step 1: Read the current /save command**

Read the file. Add a new "Artifact mode" section after "Common Cases".

- [ ] **Step 2: Append the artifact mode**

Append:

```markdown
## Artifact Mode

`/save artifact <source-path> [--hub <name>] [--slug <slug>] [--title "..."] [--tags a,b,c]`

Promotes a single HTML file into Au-docs/<hub>/artifacts/<slug>.html with a sidecar.
Use this for Claude-generated brainstorm HTMLs you want to keep, or for static HTMLs
you want surfaced in Browse.

The implementation calls the `save-artifact` MCP tool on the augur-framework server:

- `source_path`: absolute or repo-relative path to the HTML.
- `hub`: one of the 9 hubs (brain, career, venture, dev, ...). Required.
- `slug`: optional; auto-derived from title or filename when omitted.
- `title`: optional; auto-derived from <title> tag, then <h1>, then filename.
- `tags`: optional comma-separated list.

After the tool returns, surface the new artifact at `/artifact/<slug>` and confirm
in the response that the sidecar is at `<target>.meta.yaml`.
```

- [ ] **Step 3: Verify the command renders**

Run: `/save --help` (per Augur Rule 15, --help shows usage and does not execute).
Expected: usage text includes the new "Artifact Mode" block.

- [ ] **Step 4: Commit**

```bash
git add shared-vault/skills/augur-core/commands/save.md
git commit -m "docs(save): document /save artifact form for Pages flow"
```

---

## Task 18: End-to-end browser verification (Rule 28)

**Files:** none — verification only.

- [ ] **Step 1: Rebuild the dashboard**

Run: `/dev-build`
Expected: build green; dev server up at `localhost:3000`.

- [ ] **Step 2: Browse — Pages ViewMode loads**

Open `localhost:3000/browse?category=pages` via Chrome MCP. Confirm:
- Grid renders.
- Live MCP pages (e.g. `/brain/inbox`) appear with kind=live chip.
- Saved/generated artifacts from Au-docs (after Task 8 migration) appear with their respective chips.
- Kind filter pill narrows the grid as expected.

- [ ] **Step 3: Legacy URL still works**

Open `localhost:3000/browse?category=dashboard-surfaces`. Confirm it resolves to the same Pages view (via legacy alias).

- [ ] **Step 4: Open an artifact**

Click any saved/generated card. Confirm:
- Routes to `/artifact/<slug>`.
- Chrome bar shows title, hub, kind, Pin button, Open external.
- Iframe renders the HTML, scripts execute (test with one of the brainstorm HTMLs that has interactive elements).

- [ ] **Step 5: Pin / unpin**

Click Pin in the chrome. Confirm the button toggles. Reload. Confirm the pin persists. Open `/browse?category=pages`. Confirm a Pinned strip appears with the pinned card.

- [ ] **Step 6: Promote a fresh brainstorm HTML**

In a Claude session, ask Claude to write a small HTML file under `.superpowers/brainstorm/test-<id>/content/`. Then run:

```
/save artifact .superpowers/brainstorm/test-<id>/content/example.html --hub dev --title "Promote test"
```

Reload `/browse?category=pages`. Confirm the new artifact appears with kind=generated and `/artifact/promote-test` opens correctly.

- [ ] **Step 7: Final lint and full test sweep**

Run: `/auto-lint`
Run: `/auto-test-pytest`
Run: `/auto-test-build`
Run: `/auto-test-dashboard`

Expected: all green.

- [ ] **Step 8: Final commit**

If any small fixes were needed during browser verification, commit them now:

```bash
git add -p
git commit -m "fix(pages): browser-verification cleanups"
```

---

## Self-Review Checklist (already run while writing)

- **Spec coverage:** Every section of the spec maps to at least one task. §3-6 (data model, storage, open route) → Tasks 1, 2, 14, 15. §7 (MCP tools) → Tasks 1-7, 11, 14. §8 (Browse integration) → Tasks 9-13, 16. §9-10 (registration / promote) → Tasks 5, 7, 17. §11 (phasing) → tasks ordered Phase 0 → Phase 1 → Phase 2. §12 (testing) → Task 18. §13 (risks) → orphan/collision handled in Tasks 3, 5; iframe scope explicit in Task 15.
- **Placeholder scan:** No "TBD"/"implement later"/"add error handling" — concrete code in every step.
- **Type consistency:** `Sidecar` defined in Task 1, used identically in Tasks 2-5. `ArtifactEntry` defined in Task 10, used in Tasks 11, 15. `LiveTabEntry` matches `getAllPages()` shape in `useBrowseState.ts`. `ViewMode` rename applied uniformly Tasks 9-13.
- **Out of scope (per spec §2):** brainstorm session viewer, HTML diff, S3 sharing, auto-promote, per-hub pinned sections, WYSIWYG — none of these have tasks. Correct.
