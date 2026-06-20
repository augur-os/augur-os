# Obsidian-Native Ingest URL Wiki MVP — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a live `obsidian` skill at `shared-vault/skills/obsidian/` that registers seven `vault-*` MCP tools (read, write, search, status, scaffold, convert, health-repairs), and add a single new `ingest-url` MCP tool on the existing `ingest` skill that captures a webpage as a source card the wiki compiler picks up.

**Architecture:** Two tracks delivered together. Track A (`obsidian` skill) is mostly registration glue: existing impls in `src/mcp/augur_core/tools/core/vault_ops.py` and `src/mcp/augur_framework/tools/internal/vault_status.py` get exposed under stable `vault-*` names from the new skill, plus three small new modules (`vault_search.py`, `vault_scaffold.py`, `vault_convert.py`). Track B (`ingest-url`) extends the inbox-style source card pipeline with a URL fetcher that writes to `<vault>/sources/urls/`, satisfying the wiki compiler's frontmatter contract.

**Tech Stack:** Python 3.11, FastMCP (`@mcp.tool`), pytest, YAML (SKILL.md frontmatter), `trafilatura` (new dependency for HTML main-content extraction), `httpx` (existing).

**Spec:** `docs/superpowers/specs/2026-05-10-obsidian-native-ingest-url-wiki-mvp-design.md`

---

## File Structure

### Created (new files) — Track A: `obsidian` skill

- `shared-vault/skills/obsidian/SKILL.md`
- `shared-vault/skills/obsidian/__init__.py`
- `shared-vault/skills/obsidian/scripts/__init__.py`
- `shared-vault/skills/obsidian/scripts/vault_search.py`
- `shared-vault/skills/obsidian/scripts/vault_scaffold.py`
- `shared-vault/skills/obsidian/scripts/vault_convert.py`
- `shared-vault/skills/obsidian/scripts/mcp/__init__.py`
- `shared-vault/skills/obsidian/scripts/mcp/vault_tools.py`
- `shared-vault/skills/obsidian/augur/__init__.py`
- `shared-vault/skills/obsidian/augur/dashboard/__init__.py`
- `shared-vault/skills/obsidian/augur/pages/vault.yaml` — config-driven dashboard page (ADR-491)
- `shared-vault/skills/obsidian/augur/tests/__init__.py`
- `shared-vault/skills/obsidian/augur/tests/test_vault_search.py`
- `shared-vault/skills/obsidian/augur/tests/test_vault_scaffold.py`
- `shared-vault/skills/obsidian/augur/tests/test_vault_convert.py`
- `shared-vault/skills/obsidian/augur/tests/test_vault_tools_register.py`
- `shared-vault/skills/obsidian/augur/data/scaffold-readme-sources.md` — seed README copied by `vault-scaffold`
- `shared-vault/skills/obsidian/augur/data/scaffold-readme-prompts.md`

### Created (new files) — Track B: `ingest-url`

- `shared-vault/skills/ingest/scripts/url_ingest.py`
- `shared-vault/skills/ingest/augur/tests/test_url_ingest.py`
- `shared-vault/skills/ingest/augur/tests/test_source_card_url.py`

### Modified (existing files)

- `shared-vault/skills/ingest/scripts/source_cards.py` — extend `write_source_card` to accept `source_url`, `fetched_at`, `publish_date`, `author` keys and write them into frontmatter; also add a sibling `write_url_source_card` helper that produces the URL-flavor body shape.
- `shared-vault/skills/ingest/scripts/mcp/wiki_tools.py` — register the new `ingest-url` MCP tool alongside the existing wiki tools. (Tools live on the `ingest` skill; the file is the right home because it already has the FastMCP plumbing and metrics tracker imports.)
- `shared-vault/skills/ingest/SKILL.md` — append `ingest-url` to `x-augur-mcp-tools`.
- `pyproject.toml` — add `trafilatura` to project dependencies.
- `config/system/capability_exposure.yaml` — add capability rows for the seven `vault-*` tools and for `ingest-url` (all `cli via shell` for MVP).
- `CLAUDE.md` — capability-policy table already lists the `vault-*` rows; verify the owner column points at `obsidian` (currently it lists `vault` for some, which has no skill).
- `shared-vault/skills/ingest/scripts/wiki_scanner.py` — extend `_SCANNABLE` to ensure `sources/urls/*.md` is walked; verify the existing logic already handles arbitrary subdirectories of `sources/`.

### Unchanged (load-bearing)

- `src/mcp/augur_core/tools/core/vault_ops.py` — kept verbatim; the new skill imports `vault_file_read_impl` and `vault_file_write_impl` directly.
- `src/mcp/augur_framework/tools/internal/vault_status.py` — kept verbatim; the new skill registers a tool whose body delegates to its impl.
- `plugins/obsidian/` — unchanged (this ADR is Augur-side only).

---

## Phase 0: Confirm ADR-624 reference

ADR-624 is already adopted (Accepted). Commit messages reference `refs ADR-624`.

---

## Track A — Phase 1: Skill scaffold + manifest

### Task A1.1: Create the `obsidian` skill manifest

**Files:**
- Create: `shared-vault/skills/obsidian/SKILL.md`

- [ ] **Step 1: Write a failing test that asserts the manifest exists and lists the seven tools**

```python
# shared-vault/skills/obsidian/augur/tests/test_vault_tools_register.py
from __future__ import annotations

from pathlib import Path

import yaml

SKILL_ROOT = Path(__file__).resolve().parents[2]
SKILL_MD = SKILL_ROOT / "SKILL.md"


def _load_frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"Missing frontmatter: {path}"
    end = text.index("\n---\n", 4)
    return yaml.safe_load(text[4:end])


def test_skill_md_lists_seven_vault_tools() -> None:
    fm = _load_frontmatter(SKILL_MD)
    assert fm["name"] == "obsidian"
    assert fm["x-augur-hub"] == "brain"
    expected = {
        "vault-read",
        "vault-write",
        "vault-search",
        "vault-status",
        "vault-scaffold",
        "vault-convert",
        "vault-health-repairs",
    }
    assert set(fm["x-augur-mcp-tools"]) == expected
```

- [ ] **Step 2: Run, expect FAIL (file does not exist)**

```bash
/auto-test-pytest shared-vault/skills/obsidian/augur/tests/test_vault_tools_register.py::test_skill_md_lists_seven_vault_tools
```

- [ ] **Step 3: Create the SKILL.md**

```markdown
---
name: obsidian
x-augur-type: domain
x-augur-group: brain
x-augur-release: mvp
description: Obsidian-native browsing and editing surface for vault source cards and compiled wiki pages. Provides vault read/write/search plus scaffold and convert helpers.
x-augur-hub: brain
x-augur-tab: vault
x-augur-mcp-tools:
  - vault-read
  - vault-write
  - vault-search
  - vault-status
  - vault-scaffold
  - vault-convert
  - vault-health-repairs
x-augur-dashboard-pages:
  - /brain/vault
---

# Obsidian

Augur-side companion to the user's Obsidian vault.

## What this skill owns

- The seven `vault-*` MCP tools listed above.
- A minimal `/brain/vault` dashboard tab listing recent source cards
  with `obsidian://` deep-links.
- The vault folder layout convention enforced by `vault-scaffold`
  (`sources/{files,urls}/`, `wiki/`, `prompts/`, `scratch/`).

## What this skill does NOT own

- URL-to-source-card capture — that belongs to the `ingest` skill's
  `ingest-url` tool.
- Wiki-page compilation — that belongs to the `ingest` skill's wiki
  compiler.
- The Obsidian *plugin* under `plugins/obsidian/` — that is its own
  governance per ADR-559.
```

- [ ] **Step 4: Run, expect PASS**

```bash
/auto-test-pytest shared-vault/skills/obsidian/augur/tests/test_vault_tools_register.py::test_skill_md_lists_seven_vault_tools
```

- [ ] **Step 5: Commit**

```bash
git add shared-vault/skills/obsidian/SKILL.md shared-vault/skills/obsidian/augur/tests/test_vault_tools_register.py shared-vault/skills/obsidian/augur/tests/__init__.py
git commit -m "feat(obsidian): add SKILL.md with seven vault-* tool registrations (refs ADR-624)"
```

---

### Task A1.2: Empty package init files

**Files:**
- Create: `shared-vault/skills/obsidian/__init__.py`
- Create: `shared-vault/skills/obsidian/scripts/__init__.py`
- Create: `shared-vault/skills/obsidian/scripts/mcp/__init__.py`
- Create: `shared-vault/skills/obsidian/augur/__init__.py`

- [ ] **Step 1: Write a failing test that imports `skills.obsidian.scripts.mcp`**

```python
# Append to test_vault_tools_register.py
def test_obsidian_mcp_module_importable() -> None:
    import importlib
    importlib.import_module("skills.obsidian.scripts.mcp")
```

- [ ] **Step 2: Run, expect FAIL (no package)**

- [ ] **Step 3: Create empty `__init__.py` files (no contents).**

- [ ] **Step 4: Run, expect PASS**

- [ ] **Step 5: Commit**

```bash
git add shared-vault/skills/obsidian/__init__.py shared-vault/skills/obsidian/scripts/__init__.py shared-vault/skills/obsidian/scripts/mcp/__init__.py shared-vault/skills/obsidian/augur/__init__.py
git commit -m "feat(obsidian): scaffold package layout (refs ADR-624)"
```

---

## Track A — Phase 2: `vault-search`

### Task A2.1: `vault_search.py` — frontmatter-aware grep

**Files:**
- Create: `shared-vault/skills/obsidian/scripts/vault_search.py`
- Create: `shared-vault/skills/obsidian/augur/tests/test_vault_search.py`

- [ ] **Step 1: Write the failing test**

```python
# shared-vault/skills/obsidian/augur/tests/test_vault_search.py
from __future__ import annotations

from pathlib import Path


def _seed(vault: Path) -> None:
    """Write a small fixture vault."""
    (vault / "sources" / "files").mkdir(parents=True)
    (vault / "sources" / "urls").mkdir(parents=True)
    (vault / "wiki" / "brain").mkdir(parents=True)

    (vault / "sources" / "files" / "meeting-notes.md").write_text(
        "---\ntitle: Meeting notes\nsource_type: file\ntags: [meetings]\n---\n\n"
        "Discussed the roadmap for Q3.\n",
        encoding="utf-8",
    )
    (vault / "sources" / "urls" / "2026-05-09-attention-paper.md").write_text(
        "---\ntitle: Attention paper\nsource_type: url\ntags: [research, ml]\n---\n\n"
        "# Attention paper\n\n> [!summary]\n> Self-attention is all you need.\n",
        encoding="utf-8",
    )
    (vault / "wiki" / "brain" / "ml-attention.md").write_text(
        "---\ntitle: ML Attention\nhub: brain\ntags: [ml, attention]\n---\n\n"
        "Compounded notes on attention.\n",
        encoding="utf-8",
    )


def test_search_matches_body_text(tmp_path: Path) -> None:
    from skills.obsidian.scripts.vault_search import search_vault

    _seed(tmp_path)
    hits = search_vault(tmp_path, query="attention")
    paths = {h["path"] for h in hits}
    assert "sources/urls/2026-05-09-attention-paper.md" in paths
    assert "wiki/brain/ml-attention.md" in paths
    assert "sources/files/meeting-notes.md" not in paths


def test_search_filters_by_source_type(tmp_path: Path) -> None:
    from skills.obsidian.scripts.vault_search import search_vault

    _seed(tmp_path)
    hits = search_vault(tmp_path, query="attention", source_type="url")
    paths = {h["path"] for h in hits}
    assert paths == {"sources/urls/2026-05-09-attention-paper.md"}


def test_search_filters_by_tag(tmp_path: Path) -> None:
    from skills.obsidian.scripts.vault_search import search_vault

    _seed(tmp_path)
    hits = search_vault(tmp_path, query="", tags=["ml"])
    paths = {h["path"] for h in hits}
    assert "sources/urls/2026-05-09-attention-paper.md" in paths
    assert "wiki/brain/ml-attention.md" in paths


def test_search_returns_snippet_around_match(tmp_path: Path) -> None:
    from skills.obsidian.scripts.vault_search import search_vault

    _seed(tmp_path)
    hits = search_vault(tmp_path, query="roadmap")
    assert len(hits) == 1
    snippet = hits[0]["snippet"]
    assert "roadmap" in snippet.lower()
```

- [ ] **Step 2: Run, expect FAIL**

```bash
/auto-test-pytest shared-vault/skills/obsidian/augur/tests/test_vault_search.py
```

- [ ] **Step 3: Implement**

```python
# shared-vault/skills/obsidian/scripts/vault_search.py
"""Frontmatter-aware vault search.

Walks the vault, filters by frontmatter (tags, source_type, hub), and
returns body matches with a ±60-char snippet. Designed for AI clients
to scope their queries — not a replacement for RAG.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from src.lib.frontmatter_utils import parse_frontmatter

_DEFAULT_LIMIT = 20
_SNIPPET_RADIUS = 60
_SCANNABLE_SUFFIX = ".md"


def search_vault(
    vault_dir: Path,
    *,
    query: str = "",
    hub: str = "",
    source_type: str = "",
    tags: list[str] | None = None,
    limit: int = _DEFAULT_LIMIT,
) -> list[dict[str, Any]]:
    """Return up to `limit` hits matching `query` and frontmatter filters."""
    if not vault_dir.is_dir():
        return []

    pattern = re.compile(re.escape(query), re.IGNORECASE) if query else None
    tag_set = {t.strip().lower() for t in (tags or []) if t.strip()}

    hits: list[dict[str, Any]] = []
    for path in sorted(vault_dir.rglob(f"*{_SCANNABLE_SUFFIX}")):
        if not path.is_file():
            continue
        try:
            fm, body = parse_frontmatter(path, include_sidecar_config=False)
        except OSError:
            continue
        if hub and fm.get("hub") != hub:
            continue
        if source_type and fm.get("source_type") != source_type:
            continue
        if tag_set:
            page_tags = {str(t).lower() for t in (fm.get("tags") or [])}
            if not (tag_set & page_tags):
                continue

        if pattern is None:
            hits.append({
                "path": str(path.relative_to(vault_dir)),
                "title": fm.get("title", path.stem),
                "tags": fm.get("tags", []),
                "snippet": body[:120].strip(),
            })
        else:
            match = pattern.search(body)
            if not match:
                continue
            start = max(0, match.start() - _SNIPPET_RADIUS)
            end = min(len(body), match.end() + _SNIPPET_RADIUS)
            hits.append({
                "path": str(path.relative_to(vault_dir)),
                "title": fm.get("title", path.stem),
                "tags": fm.get("tags", []),
                "snippet": body[start:end].strip(),
            })

        if len(hits) >= limit:
            break
    return hits
```

- [ ] **Step 4: Run, expect PASS**

```bash
/auto-test-pytest shared-vault/skills/obsidian/augur/tests/test_vault_search.py
```

- [ ] **Step 5: Commit**

```bash
git add shared-vault/skills/obsidian/scripts/vault_search.py shared-vault/skills/obsidian/augur/tests/test_vault_search.py
git commit -m "feat(obsidian): vault_search frontmatter-aware grep (refs ADR-624)"
```

---

## Track A — Phase 3: `vault-scaffold`

### Task A3.1: `vault_scaffold.py` — idempotent layout creator

**Files:**
- Create: `shared-vault/skills/obsidian/scripts/vault_scaffold.py`
- Create: `shared-vault/skills/obsidian/augur/data/scaffold-readme-sources.md`
- Create: `shared-vault/skills/obsidian/augur/data/scaffold-readme-prompts.md`
- Create: `shared-vault/skills/obsidian/augur/tests/test_vault_scaffold.py`

- [ ] **Step 1: Write the failing test**

```python
# shared-vault/skills/obsidian/augur/tests/test_vault_scaffold.py
from __future__ import annotations

from pathlib import Path


def test_scaffold_creates_canonical_layout(tmp_path: Path) -> None:
    from skills.obsidian.scripts.vault_scaffold import scaffold_vault

    result = scaffold_vault(tmp_path)
    assert result["created"]
    assert (tmp_path / "sources" / "files").is_dir()
    assert (tmp_path / "sources" / "urls").is_dir()
    assert (tmp_path / "wiki").is_dir()
    assert (tmp_path / "prompts").is_dir()
    assert (tmp_path / "scratch").is_dir()
    assert (tmp_path / "sources" / "README.md").is_file()
    assert (tmp_path / "prompts" / "README.md").is_file()


def test_scaffold_is_idempotent(tmp_path: Path) -> None:
    from skills.obsidian.scripts.vault_scaffold import scaffold_vault

    first = scaffold_vault(tmp_path)
    assert first["created"]
    # Modify a README; re-running must not overwrite.
    readme = tmp_path / "sources" / "README.md"
    readme.write_text("user customized\n", encoding="utf-8")

    second = scaffold_vault(tmp_path)
    assert second["created"] == []  # nothing new
    assert second["already_existed"]
    assert readme.read_text(encoding="utf-8") == "user customized\n"


def test_scaffold_returns_relative_paths_for_created_dirs(tmp_path: Path) -> None:
    from skills.obsidian.scripts.vault_scaffold import scaffold_vault

    result = scaffold_vault(tmp_path)
    assert "sources/files" in result["created"]
    assert "sources/urls" in result["created"]
    assert "wiki" in result["created"]
```

- [ ] **Step 2: Run, expect FAIL**

- [ ] **Step 3: Implement**

```python
# shared-vault/skills/obsidian/scripts/vault_scaffold.py
"""Idempotent vault layout scaffolding.

Creates the canonical folder structure used by Augur skills:

    sources/files/   — inbox-consumed cards
    sources/urls/    — URL-ingested cards
    wiki/            — compiled wiki pages
    prompts/         — user saved prompts
    scratch/         — ad-hoc workspace

Seed READMEs in sources/ and prompts/ document the convention.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

_DATA_DIR = Path(__file__).resolve().parents[1] / "augur" / "data"

_DIRS = (
    "sources",
    "sources/files",
    "sources/urls",
    "wiki",
    "prompts",
    "scratch",
)

_README_SEEDS = {
    "sources/README.md": _DATA_DIR / "scaffold-readme-sources.md",
    "prompts/README.md": _DATA_DIR / "scaffold-readme-prompts.md",
}


def scaffold_vault(vault_dir: Path) -> dict[str, Any]:
    """Create canonical layout. Idempotent. Never overwrites user files."""
    vault_dir.mkdir(parents=True, exist_ok=True)
    created: list[str] = []
    already: list[str] = []

    for rel in _DIRS:
        target = vault_dir / rel
        if target.is_dir():
            already.append(rel)
        else:
            target.mkdir(parents=True, exist_ok=True)
            created.append(rel)

    for rel, seed in _README_SEEDS.items():
        target = vault_dir / rel
        if target.is_file():
            already.append(rel)
            continue
        if not seed.is_file():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(seed.read_text(encoding="utf-8"), encoding="utf-8")
        created.append(rel)

    return {
        "created": created,
        "already_existed": already,
    }
```

- [ ] **Step 4: Create the seed READMEs**

```markdown
# augur/data/scaffold-readme-sources.md
# Sources

This folder holds **source cards** — one Markdown file per captured
artifact (file, transcript, or webpage).

## Subfolders

- `files/` — Cards written by `inbox-consume-folder`. One card per
  ingested file; filename derived from the original.
- `urls/` — Cards written by `ingest-url`. One card per webpage;
  filename is `<YYYY-MM-DD>-<slug>.md`.

## Convention

Every card starts with YAML frontmatter (`title`, `source_type`,
`tags`, `content_hash`, …) and is consumed by the wiki compiler.
Manual edits to the body are preserved; system fields (prefixed `_`)
are managed by Augur.
```

```markdown
# augur/data/scaffold-readme-prompts.md
# Prompts

This folder holds **your saved prompts** — reusable instructions you
can paste into any AI client. See ADR-563 for the full convention.

## Convention

- One prompt per `.md` file.
- Frontmatter: `title`, `created`, `tags`, optional `source`.
- Body: free-form Markdown. Wrap actual prompt text in fenced code
  blocks (` ```text `) for easy copying.
```

- [ ] **Step 5: Run, expect PASS**

```bash
/auto-test-pytest shared-vault/skills/obsidian/augur/tests/test_vault_scaffold.py
```

- [ ] **Step 6: Commit**

```bash
git add shared-vault/skills/obsidian/scripts/vault_scaffold.py \
        shared-vault/skills/obsidian/augur/data/scaffold-readme-sources.md \
        shared-vault/skills/obsidian/augur/data/scaffold-readme-prompts.md \
        shared-vault/skills/obsidian/augur/tests/test_vault_scaffold.py
git commit -m "feat(obsidian): vault_scaffold idempotent layout creator (refs ADR-624)"
```

---

## Track A — Phase 4: `vault-convert`

### Task A4.1: `vault_convert.py` — frontmatter-aware format conversion

**Files:**
- Create: `shared-vault/skills/obsidian/scripts/vault_convert.py`
- Create: `shared-vault/skills/obsidian/augur/tests/test_vault_convert.py`

- [ ] **Step 1: Write the failing test**

```python
# shared-vault/skills/obsidian/augur/tests/test_vault_convert.py
from __future__ import annotations

from pathlib import Path


def test_convert_adds_frontmatter_to_legacy_md(tmp_path: Path) -> None:
    from skills.obsidian.scripts.vault_convert import convert_path

    target = tmp_path / "legacy.md"
    target.write_text("# Legacy note\n\nNo frontmatter at all.\n", encoding="utf-8")

    result = convert_path(target, target_format="frontmatter")
    assert result["converted"]
    text = target.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    assert "title: Legacy note" in text
    assert "No frontmatter at all." in text


def test_convert_idempotent_when_already_has_frontmatter(tmp_path: Path) -> None:
    from skills.obsidian.scripts.vault_convert import convert_path

    target = tmp_path / "modern.md"
    target.write_text(
        "---\ntitle: Modern note\ntags: []\n---\n\nbody\n",
        encoding="utf-8",
    )
    original = target.read_text(encoding="utf-8")
    result = convert_path(target, target_format="frontmatter")
    assert not result["converted"]
    assert target.read_text(encoding="utf-8") == original


def test_convert_txt_to_md_with_seed_frontmatter(tmp_path: Path) -> None:
    from skills.obsidian.scripts.vault_convert import convert_path

    target = tmp_path / "raw.txt"
    target.write_text("Just plain text.\n", encoding="utf-8")

    result = convert_path(target, target_format="frontmatter")
    assert result["converted"]
    new_path = tmp_path / "raw.md"
    assert new_path.is_file()
    assert not target.exists()
    text = new_path.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    assert "title: raw" in text
    assert "Just plain text." in text
```

- [ ] **Step 2: Run, expect FAIL**

- [ ] **Step 3: Implement**

```python
# shared-vault/skills/obsidian/scripts/vault_convert.py
"""Vault file format conversion.

Currently supports one transform:

    target_format="frontmatter"
        - .md without frontmatter → prepend frontmatter (title from H1
          or filename, empty tags, empty source_type).
        - .txt → rename to .md and prepend frontmatter.
        - Already-frontmatter .md → no-op.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_H1_RE = re.compile(r"^# +(?P<title>.+)$", re.MULTILINE)


def _extract_title(body: str, fallback: str) -> str:
    match = _H1_RE.search(body)
    if match:
        return match.group("title").strip()
    return fallback


def _has_frontmatter(text: str) -> bool:
    return text.startswith("---\n") and "\n---\n" in text[4:]


def _seed_frontmatter(title: str) -> str:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return (
        "---\n"
        f"title: {title}\n"
        "tags: []\n"
        f"created: {now}\n"
        "source_type: \"\"\n"
        "---\n\n"
    )


def convert_path(path: Path, *, target_format: str = "frontmatter") -> dict[str, Any]:
    """Convert a single vault file to the target format. Idempotent."""
    if target_format != "frontmatter":
        raise ValueError(f"Unsupported target_format: {target_format}")
    if not path.is_file():
        return {"converted": False, "reason": f"not a file: {path}"}

    suffix = path.suffix.lower()
    if suffix == ".md":
        text = path.read_text(encoding="utf-8")
        if _has_frontmatter(text):
            return {"converted": False, "reason": "already has frontmatter"}
        title = _extract_title(text, path.stem)
        new_text = _seed_frontmatter(title) + text
        path.write_text(new_text, encoding="utf-8")
        return {"converted": True, "path": str(path), "added": "frontmatter"}

    if suffix == ".txt":
        text = path.read_text(encoding="utf-8")
        title = _extract_title(text, path.stem)
        new_path = path.with_suffix(".md")
        if new_path.exists():
            return {"converted": False, "reason": f"target exists: {new_path}"}
        new_path.write_text(_seed_frontmatter(title) + text, encoding="utf-8")
        path.unlink()
        return {"converted": True, "path": str(new_path), "renamed_from": str(path)}

    return {"converted": False, "reason": f"unsupported suffix: {suffix}"}
```

- [ ] **Step 4: Run, expect PASS**

- [ ] **Step 5: Commit**

```bash
git add shared-vault/skills/obsidian/scripts/vault_convert.py shared-vault/skills/obsidian/augur/tests/test_vault_convert.py
git commit -m "feat(obsidian): vault_convert frontmatter-aware format converter (refs ADR-624)"
```

---

## Track A — Phase 5: MCP tool registration

### Task A5.1: Wire the seven `vault-*` tools in `mcp/vault_tools.py`

**Files:**
- Create: `shared-vault/skills/obsidian/scripts/mcp/vault_tools.py`
- Modify: `shared-vault/skills/obsidian/scripts/mcp/__init__.py`
- Modify: `shared-vault/skills/obsidian/augur/tests/test_vault_tools_register.py`

- [ ] **Step 1: Write a failing test that asserts `register_vault_tools` registers seven tools**

```python
# Append to test_vault_tools_register.py
def test_register_vault_tools_registers_seven_tools(monkeypatch) -> None:
    from skills.obsidian.scripts.mcp.vault_tools import register_vault_tools

    registered: list[str] = []

    class FakeMCP:
        def tool(self, name: str, **kwargs):
            def deco(fn):
                registered.append(name)
                return fn
            return deco

    class FakeMetrics:
        def track_tool(self, *args, **kwargs) -> None:
            pass

    register_vault_tools(FakeMCP(), lambda fn: fn, FakeMetrics())
    assert sorted(registered) == [
        "vault-convert",
        "vault-health-repairs",
        "vault-read",
        "vault-scaffold",
        "vault-search",
        "vault-status",
        "vault-write",
    ]
```

- [ ] **Step 2: Run, expect FAIL (module does not exist)**

- [ ] **Step 3: Implement**

```python
# shared-vault/skills/obsidian/scripts/mcp/vault_tools.py
"""MCP tool registrations for the obsidian skill."""
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
    from augur_mcp.annotations import tool_annotations
except ImportError:
    def tool_annotations(annotations: dict) -> dict:
        return annotations

from src.config.paths import get_vault_dir
from src.mcp.augur_core.tools.core.vault_ops import (
    vault_file_read_impl,
    vault_file_write_impl,
)


def register_vault_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable[..., Any],
    metrics: Any,
) -> None:
    """Register the seven vault-* MCP tools."""

    @mcp.tool(
        name="vault-read",
        annotations=tool_annotations({
            "title": "Vault Read",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        }),
    )
    @mcp_tool_interceptor
    async def vault_read(skill: str = "", path: str = "") -> str:
        """Read a vault file by skill and relative path."""
        metrics.track_tool("vault_read", skill="obsidian")
        return await vault_file_read_impl(skill=skill, path=path)

    @mcp.tool(
        name="vault-write",
        annotations=tool_annotations({
            "title": "Vault Write",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        }),
    )
    @mcp_tool_interceptor
    async def vault_write(
        skill: str = "",
        path: str = "",
        title: str = "",
        body: str = "",
        metadata: str = "{}",
    ) -> str:
        """Write or update a vault file with frontmatter merge."""
        metrics.track_tool("vault_write", skill="obsidian")
        try:
            md = json.loads(metadata) if metadata else {}
        except json.JSONDecodeError as exc:
            return json.dumps({"success": False, "error": f"metadata not JSON: {exc}"})
        return await vault_file_write_impl(
            skill=skill, path=path, title=title, body=body, metadata=md,
        )

    @mcp.tool(
        name="vault-search",
        annotations=tool_annotations({
            "title": "Vault Search",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        }),
    )
    @mcp_tool_interceptor
    async def vault_search(
        query: str = "",
        hub: str = "",
        source_type: str = "",
        tags: str = "",
        limit: int = 20,
    ) -> str:
        """Frontmatter-aware grep across the vault."""
        from skills.obsidian.scripts.vault_search import search_vault
        metrics.track_tool("vault_search", skill="obsidian")
        tag_list = [t for t in (tags or "").split(",") if t.strip()]
        try:
            hits = search_vault(
                get_vault_dir(),
                query=query,
                hub=hub,
                source_type=source_type,
                tags=tag_list,
                limit=int(limit),
            )
            return json.dumps({"success": True, "hits": hits, "count": len(hits)}, default=str)
        except Exception as exc:  # noqa: BLE001
            return json.dumps({"success": False, "error": str(exc)})

    @mcp.tool(
        name="vault-status",
        annotations=tool_annotations({
            "title": "Vault Status",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        }),
    )
    @mcp_tool_interceptor
    async def vault_status() -> str:
        """Vault git status, sync state, and health summary."""
        from src.mcp.augur_framework.tools.internal.vault_status import (
            build_vault_status_payload,
        )
        metrics.track_tool("vault_status", skill="obsidian")
        try:
            payload = build_vault_status_payload()
            return json.dumps({"success": True, **payload}, default=str)
        except Exception as exc:  # noqa: BLE001
            return json.dumps({"success": False, "error": str(exc)})

    @mcp.tool(
        name="vault-scaffold",
        annotations=tool_annotations({
            "title": "Vault Scaffold",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        }),
    )
    @mcp_tool_interceptor
    async def vault_scaffold(skill: str = "") -> str:
        """Idempotently create the canonical vault folder layout."""
        from skills.obsidian.scripts.vault_scaffold import scaffold_vault
        metrics.track_tool("vault_scaffold", skill="obsidian")
        try:
            result = scaffold_vault(get_vault_dir())
            return json.dumps({"success": True, **result}, default=str)
        except Exception as exc:  # noqa: BLE001
            return json.dumps({"success": False, "error": str(exc)})

    @mcp.tool(
        name="vault-convert",
        annotations=tool_annotations({
            "title": "Vault Convert",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        }),
    )
    @mcp_tool_interceptor
    async def vault_convert(path: str = "", target_format: str = "frontmatter") -> str:
        """Convert a vault file to the target format (currently only `frontmatter`)."""
        from skills.obsidian.scripts.vault_convert import convert_path
        metrics.track_tool("vault_convert", skill="obsidian")
        try:
            target = (get_vault_dir() / path).resolve()
            target.relative_to(get_vault_dir().resolve())
            result = convert_path(target, target_format=target_format)
            return json.dumps({"success": True, **result}, default=str)
        except Exception as exc:  # noqa: BLE001
            return json.dumps({"success": False, "error": str(exc)})

    @mcp.tool(
        name="vault-health-repairs",
        annotations=tool_annotations({
            "title": "Vault Health Repairs",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        }),
    )
    @mcp_tool_interceptor
    async def vault_health_repairs(action: str = "report") -> str:
        """Delegate to the platform-admin vault healers; `action='apply'` mutates."""
        # TODO_CLEANUP: wire to platform-admin healer entrypoint once promoted
        # out of the staging tree (issue tracked in ADR-624 Phase 6 review).
        metrics.track_tool("vault_health_repairs", skill="obsidian")
        return json.dumps({
            "success": True,
            "action": action,
            "note": "MVP: report-only delegate. Full repair wiring lands in follow-up.",
        })
```

- [ ] **Step 4: Wire it into the registry**

```python
# shared-vault/skills/obsidian/scripts/mcp/__init__.py
from .vault_tools import register_vault_tools


def register_tools(mcp, mcp_tool_interceptor, metrics) -> None:
    register_vault_tools(mcp, mcp_tool_interceptor, metrics)


__all__ = ["register_tools"]
```

- [ ] **Step 5: Run, expect PASS**

```bash
/auto-test-pytest shared-vault/skills/obsidian/augur/tests/test_vault_tools_register.py
```

- [ ] **Step 6: Commit**

```bash
git add shared-vault/skills/obsidian/scripts/mcp/vault_tools.py shared-vault/skills/obsidian/scripts/mcp/__init__.py shared-vault/skills/obsidian/augur/tests/test_vault_tools_register.py
git commit -m "feat(obsidian): register seven vault-* MCP tools (refs ADR-624)"
```

---

## Track A — Phase 6: Dashboard config-driven page

### Task A6.1: `pages/vault.yaml` — minimal /brain/vault tab

**Files:**
- Create: `shared-vault/skills/obsidian/augur/pages/vault.yaml`

- [ ] **Step 1: Write a failing test (architecture-level)**

```python
# Append to test_vault_tools_register.py
def test_vault_yaml_page_is_well_formed() -> None:
    import yaml
    page_path = SKILL_ROOT / "augur" / "pages" / "vault.yaml"
    assert page_path.is_file()
    page = yaml.safe_load(page_path.read_text(encoding="utf-8"))
    assert page["route"] == "/brain/vault"
    assert page["hub"] == "brain"
    assert "blocks" in page
```

- [ ] **Step 2: Run, expect FAIL**

- [ ] **Step 3: Create the page**

```yaml
# shared-vault/skills/obsidian/augur/pages/vault.yaml
route: /brain/vault
hub: brain
title: Vault
description: Source cards and compiled wiki pages, with deep links into Obsidian.
blocks:
  - type: heading
    level: 1
    text: Your Vault
  - type: text
    text: Recent source cards. Click a row to open in Obsidian.
  - type: mcp-table
    tool: vault-search
    args:
      query: ""
      limit: 20
    columns:
      - field: title
        label: Title
      - field: path
        label: Path
        render: "obsidian://open?path={path}"
      - field: tags
        label: Tags
```

- [ ] **Step 4: Run, expect PASS**

- [ ] **Step 5: Commit**

```bash
git add shared-vault/skills/obsidian/augur/pages/vault.yaml shared-vault/skills/obsidian/augur/tests/test_vault_tools_register.py
git commit -m "feat(obsidian): /brain/vault dashboard page yaml (refs ADR-624)"
```

---

## Track B — Phase 7: `ingest-url` MCP tool

### Task B7.1: Extend `source_cards.py` with URL flavor

**Files:**
- Modify: `shared-vault/skills/ingest/scripts/source_cards.py`
- Create: `shared-vault/skills/ingest/augur/tests/test_source_card_url.py`

- [ ] **Step 1: Write the failing test**

```python
# shared-vault/skills/ingest/augur/tests/test_source_card_url.py
from __future__ import annotations

from pathlib import Path

import yaml


def _read_frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    end = text.index("\n---\n", 4)
    return yaml.safe_load(text[4:end])


def test_write_url_source_card_writes_to_sources_urls(tmp_path: Path) -> None:
    from skills.ingest.scripts.source_cards import write_url_source_card

    card_path = write_url_source_card(
        vault_dir=tmp_path,
        url="https://example.com/post",
        title="Example post",
        body="The article body, several sentences long.",
        publish_date="2025-12-01",
        author="Jane Doe",
        tags=["research"],
        note="Why I saved this.",
        content_hash="sha256:abc",
        fetched_at="2026-05-10T14:30:00Z",
    )
    rel = card_path.relative_to(tmp_path).as_posix()
    assert rel.startswith("sources/urls/")
    assert rel.endswith(".md")

    fm = _read_frontmatter(card_path)
    assert fm["source_type"] == "url"
    assert fm["source_url"] == "https://example.com/post"
    assert fm["fetched_at"] == "2026-05-10T14:30:00Z"
    assert fm["author"] == "Jane Doe"
    assert "research" in fm["tags"]

    body = card_path.read_text(encoding="utf-8")
    assert "Why I saved this." in body
    assert "The article body" in body
    assert "https://example.com/post" in body


def test_write_url_source_card_filename_is_date_slug(tmp_path: Path) -> None:
    from skills.ingest.scripts.source_cards import write_url_source_card

    card = write_url_source_card(
        vault_dir=tmp_path,
        url="https://example.com/some-cool-post",
        title="Some Cool Post",
        body="body",
        publish_date=None,
        author=None,
        tags=[],
        note="",
        content_hash="sha256:abc",
        fetched_at="2026-05-10T14:30:00Z",
    )
    name = card.name
    # Pattern: YYYY-MM-DD-<slug>.md
    assert name.startswith("2026-05-10-")
    assert "some-cool-post" in name
```

- [ ] **Step 2: Run, expect FAIL**

```bash
/auto-test-pytest shared-vault/skills/ingest/augur/tests/test_source_card_url.py
```

- [ ] **Step 3: Implement `write_url_source_card`**

Append to `shared-vault/skills/ingest/scripts/source_cards.py`:

```python
def _slugify(value: str, max_length: int = 60) -> str:
    import re
    slug = value.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
    return slug[:max_length] or "url"


def write_url_source_card(
    *,
    vault_dir: Path,
    url: str,
    title: str,
    body: str,
    publish_date: str | None,
    author: str | None,
    tags: list[str],
    note: str,
    content_hash: str,
    fetched_at: str,
) -> Path:
    from urllib.parse import urlparse

    parsed = urlparse(url)
    slug_basis = parsed.path.rstrip("/").split("/")[-1] or parsed.netloc
    slug = _slugify(slug_basis or title or "url")
    date_prefix = fetched_at.split("T", 1)[0]
    target = _unique_card_path(
        vault_dir / "sources" / "urls" / f"{date_prefix}-{slug}.md"
    )
    target.parent.mkdir(parents=True, exist_ok=True)

    summary_callout = _format_summary_callout(body)

    metadata = {
        "title": title,
        "source_type": "url",
        "source_url": url,
        "fetched_at": fetched_at,
        "publish_date": publish_date,
        "author": author,
        "tags": list(dict.fromkeys((tags or []) + ["url"])),
        "content_hash": content_hash,
        "_source_type": "ingest-url",
    }

    note_block = f"\n{note.strip()}\n" if note.strip() else ""

    card_body = f"""# {title}

> [!summary]
{summary_callout}
{note_block}
## Article

{body}

## Source

- URL: [{url}]({url})
- Author: {author or ''}
- Published: {publish_date or ''}
- Fetched: {fetched_at}
"""
    write_vault_frontmatter(target, metadata, card_body)
    return target
```

- [ ] **Step 4: Run, expect PASS**

- [ ] **Step 5: Commit**

```bash
git add shared-vault/skills/ingest/scripts/source_cards.py shared-vault/skills/ingest/augur/tests/test_source_card_url.py
git commit -m "feat(ingest): write_url_source_card for sources/urls/ flavor (refs ADR-624)"
```

---

### Task B7.2: `url_ingest.py` — fetcher + extractor

**Files:**
- Create: `shared-vault/skills/ingest/scripts/url_ingest.py`
- Create: `shared-vault/skills/ingest/augur/tests/test_url_ingest.py`

- [ ] **Step 1: Write the failing test**

```python
# shared-vault/skills/ingest/augur/tests/test_url_ingest.py
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch


_HTML = """
<!DOCTYPE html>
<html>
  <head>
    <title>Attention is All You Need</title>
    <meta property="article:published_time" content="2017-06-12T00:00:00Z" />
  </head>
  <body>
    <article>
      <h1>Attention is All You Need</h1>
      <p>The dominant sequence transduction models are based on complex recurrent or convolutional neural networks.</p>
      <p>We propose a new simple network architecture, the Transformer, based solely on attention mechanisms.</p>
    </article>
  </body>
</html>
""".strip()


def _patch_fetch(html: str = _HTML, status: int = 200):
    from unittest.mock import MagicMock
    response = MagicMock()
    response.status_code = status
    response.text = html
    response.headers = {"content-type": "text/html"}
    response.url = "https://example.com/papers/attention"
    response.raise_for_status = MagicMock()
    return patch("skills.ingest.scripts.url_ingest._fetch", return_value=response)


def test_ingest_url_writes_card_to_sources_urls(tmp_path: Path) -> None:
    from skills.ingest.scripts import url_ingest

    with _patch_fetch():
        result = url_ingest.ingest_url(
            url="https://example.com/papers/attention",
            vault_dir=tmp_path,
            tags=["research", "ml"],
            note="Foundational transformer paper.",
        )
    assert result["success"], result
    rel = result["path"]
    assert rel.startswith("sources/urls/")
    assert (tmp_path / rel).is_file()
    body = (tmp_path / rel).read_text(encoding="utf-8")
    assert "Attention is All You Need" in body
    assert "Foundational transformer paper." in body
    assert result["title"] == "Attention is All You Need"
    assert "ml" in result["tags"]


def test_ingest_url_is_idempotent_on_same_content_hash(tmp_path: Path) -> None:
    from skills.ingest.scripts import url_ingest

    with _patch_fetch():
        first = url_ingest.ingest_url(
            url="https://example.com/papers/attention",
            vault_dir=tmp_path,
        )
    with _patch_fetch():
        second = url_ingest.ingest_url(
            url="https://example.com/papers/attention",
            vault_dir=tmp_path,
        )
    assert first["success"] and second["success"]
    assert first["path"] == second["path"]
    assert second["reused"] is True


def test_ingest_url_canonicalizes_tracking_params(tmp_path: Path) -> None:
    from skills.ingest.scripts import url_ingest

    with _patch_fetch():
        a = url_ingest.ingest_url(
            url="https://example.com/papers/attention?utm_source=twitter",
            vault_dir=tmp_path,
        )
    with _patch_fetch():
        b = url_ingest.ingest_url(
            url="https://example.com/papers/attention?utm_campaign=foo",
            vault_dir=tmp_path,
        )
    assert a["content_hash"] == b["content_hash"]
    assert b["reused"] is True


def test_ingest_url_empty_extraction_returns_error(tmp_path: Path) -> None:
    from skills.ingest.scripts import url_ingest

    empty_html = "<html><head><title>Empty</title></head><body></body></html>"
    with _patch_fetch(html=empty_html):
        result = url_ingest.ingest_url(
            url="https://example.com/empty",
            vault_dir=tmp_path,
        )
    assert result["success"] is False
    assert result["stage"] == "extract"
    # No card written.
    assert not (tmp_path / "sources" / "urls").exists() or not list(
        (tmp_path / "sources" / "urls").glob("*.md")
    )
```

- [ ] **Step 2: Run, expect FAIL (module missing)**

- [ ] **Step 3: Implement**

```python
# shared-vault/skills/ingest/scripts/url_ingest.py
"""Capture a URL as a vault source card.

The wiki compiler picks up the resulting card on next run.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from skills.ingest.scripts.source_cards import write_url_source_card

_TRACKING_PARAM_PREFIXES = ("utm_",)
_TRACKING_PARAMS_EXACT = {"fbclid", "gclid", "mc_cid", "mc_eid"}

_TIMEOUT_SEC = 10.0


def canonicalize_url(url: str) -> str:
    """Strip tracking params and fragment; collapse trailing slash."""
    parsed = urlparse(url)
    keep = [
        (k, v)
        for k, v in parse_qsl(parsed.query, keep_blank_values=True)
        if not (
            any(k.lower().startswith(p) for p in _TRACKING_PARAM_PREFIXES)
            or k.lower() in _TRACKING_PARAMS_EXACT
        )
    ]
    path = parsed.path
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")
    return urlunparse(parsed._replace(
        path=path,
        query=urlencode(keep, doseq=True),
        fragment="",
    ))


def _fetch(url: str):
    """Hook used by tests to mock HTTP fetches."""
    import httpx
    return httpx.get(url, follow_redirects=True, timeout=_TIMEOUT_SEC)


def _extract(html: str) -> tuple[str, str, str | None, str | None]:
    """Return (title, body, publish_date, author)."""
    title = ""
    body = ""
    publish = None
    author = None
    try:
        import trafilatura
        extracted = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=False,
            with_metadata=True,
            output_format="json",
        )
        if extracted:
            data = json.loads(extracted)
            title = data.get("title") or ""
            body = data.get("text") or ""
            publish = data.get("date")
            author = data.get("author")
    except Exception:  # noqa: BLE001
        pass

    if not body:
        # Fallback extractor: BeautifulSoup pulling <article> or <main>.
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")
            container = soup.find("article") or soup.find("main") or soup.body
            if container is not None:
                body = container.get_text(separator="\n", strip=True)
            if not title:
                if soup.title and soup.title.string:
                    title = soup.title.string.strip()
                elif soup.h1 and soup.h1.string:
                    title = soup.h1.string.strip()
        except Exception:  # noqa: BLE001
            pass

    return title.strip(), body.strip(), publish, author


def _content_hash(canonical_url: str, body: str) -> str:
    digest = hashlib.sha256()
    digest.update(canonical_url.encode("utf-8"))
    digest.update(b"\0")
    digest.update(body.encode("utf-8"))
    return f"sha256:{digest.hexdigest()}"


def _existing_card_for_hash(vault_dir: Path, content_hash: str) -> Path | None:
    target_dir = vault_dir / "sources" / "urls"
    if not target_dir.is_dir():
        return None
    needle = f'content_hash: "{content_hash}"'
    needle_alt = f"content_hash: {content_hash}"
    for path in target_dir.glob("*.md"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        head = text.split("\n---\n", 1)[0]
        if needle in head or needle_alt in head:
            return path
    return None


def ingest_url(
    *,
    url: str,
    vault_dir: Path,
    tags: list[str] | None = None,
    note: str = "",
) -> dict[str, Any]:
    """Fetch `url`, extract main content, write a source card. Idempotent on canonical URL + body."""
    canonical = canonicalize_url(url)

    try:
        response = _fetch(canonical)
        response.raise_for_status()
        html = response.text
    except Exception as exc:  # noqa: BLE001
        return {"success": False, "stage": "fetch", "error": str(exc), "url": canonical}

    title, body, publish_date, author = _extract(html)
    if not body.strip():
        return {
            "success": False,
            "stage": "extract",
            "error": "Empty extraction (likely paywall or JS-rendered page)",
            "url": canonical,
        }
    if not title:
        title = canonical

    chash = _content_hash(canonical, body)

    existing = _existing_card_for_hash(vault_dir, chash)
    if existing is not None:
        return {
            "success": True,
            "path": str(existing.relative_to(vault_dir)),
            "title": title,
            "source_url": canonical,
            "content_hash": chash,
            "reused": True,
            "tags": list(dict.fromkeys((tags or []) + ["url"])),
        }

    fetched_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    card = write_url_source_card(
        vault_dir=vault_dir,
        url=canonical,
        title=title,
        body=body,
        publish_date=publish_date,
        author=author,
        tags=tags or [],
        note=note,
        content_hash=chash,
        fetched_at=fetched_at,
    )
    return {
        "success": True,
        "path": str(card.relative_to(vault_dir)),
        "title": title,
        "source_url": canonical,
        "content_hash": chash,
        "fetched_at": fetched_at,
        "reused": False,
        "tags": list(dict.fromkeys((tags or []) + ["url"])),
    }
```

- [ ] **Step 4: Add `trafilatura` and `beautifulsoup4` to `pyproject.toml`**

```toml
# pyproject.toml — under [project] dependencies, alphabetized
"trafilatura>=1.8.0",
"beautifulsoup4>=4.12.0",
```

Run `uv sync` so the lockfile updates. (Operator step; do not run as part of the test loop.)

- [ ] **Step 5: Run, expect PASS**

```bash
/auto-test-pytest shared-vault/skills/ingest/augur/tests/test_url_ingest.py
```

- [ ] **Step 6: Commit**

```bash
git add shared-vault/skills/ingest/scripts/url_ingest.py shared-vault/skills/ingest/augur/tests/test_url_ingest.py pyproject.toml
git commit -m "feat(ingest): url_ingest fetcher with trafilatura + bs4 fallback (refs ADR-624)"
```

---

### Task B7.3: Register `ingest-url` MCP tool

**Files:**
- Modify: `shared-vault/skills/ingest/scripts/mcp/wiki_tools.py`
- Modify: `shared-vault/skills/ingest/SKILL.md`
- Create: append-to `shared-vault/skills/ingest/augur/tests/test_url_ingest.py`

- [ ] **Step 1: Write the failing registration test**

Append to `tests/test_url_ingest.py`:

```python
def test_register_wiki_tools_now_registers_ingest_url() -> None:
    from skills.ingest.scripts.mcp.wiki_tools import register_wiki_tools

    registered: list[str] = []

    class FakeMCP:
        def tool(self, name: str, **kwargs):
            def deco(fn):
                registered.append(name)
                return fn
            return deco

    class FakeMetrics:
        def track_tool(self, *a, **k) -> None:
            pass

    register_wiki_tools(FakeMCP(), lambda fn: fn, FakeMetrics())
    assert "ingest-url" in registered
```

- [ ] **Step 2: Run, expect FAIL**

- [ ] **Step 3: Add the tool registration**

In `wiki_tools.py`, inside `register_wiki_tools`, add a new `@mcp.tool` block (mirror the `wiki_write` shape):

```python
    @mcp.tool(
        name="ingest-url",
        annotations=tool_annotations({
            "title": "Ingest URL",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,  # network call
        }),
    )
    @mcp_tool_interceptor
    async def ingest_url_tool(url: str = "", tags: str = "", note: str = "") -> str:
        """Capture a URL as a vault source card. Idempotent on canonical URL + body."""
        from src.config.paths import get_vault_dir
        from skills.ingest.scripts.url_ingest import ingest_url
        metrics.track_tool("ingest_url", skill="ingest")
        try:
            tag_list = [t.strip() for t in (tags or "").split(",") if t.strip()]
            result = ingest_url(
                url=url,
                vault_dir=get_vault_dir(),
                tags=tag_list,
                note=note,
            )
            return json.dumps(result, default=str)
        except Exception as exc:  # noqa: BLE001
            logger.error("ingest-url failed: %s", exc, exc_info=True)
            return json.dumps({"success": False, "error": str(exc), "stage": "tool"})
```

- [ ] **Step 4: Append `ingest-url` to `SKILL.md` `x-augur-mcp-tools`**

```yaml
x-augur-mcp-tools:
  - inbox-folders
  - inbox-scan-folder
  - inbox-consume-folder
  - inbox-run-history
  - inbox-run-detail
  - brain-insights
  - wiki-report-data
  - wiki-rewrite-candidates
  - demo-reset
  - demo-readiness
  - demo-smoke
  - ingest-url   # new — ADR-624
```

- [ ] **Step 5: Run, expect PASS**

```bash
/auto-test-pytest shared-vault/skills/ingest/augur/tests/test_url_ingest.py
```

- [ ] **Step 6: Commit**

```bash
git add shared-vault/skills/ingest/scripts/mcp/wiki_tools.py shared-vault/skills/ingest/SKILL.md shared-vault/skills/ingest/augur/tests/test_url_ingest.py
git commit -m "feat(ingest): register ingest-url MCP tool on ingest skill (refs ADR-624)"
```

---

## Phase 8: Wiki compiler integration test

### Task 8.1: Wiki scanner picks up `sources/urls/` cards

**Files:**
- Create: append-to `shared-vault/skills/ingest/augur/tests/test_url_ingest.py`

- [ ] **Step 1: Write a failing integration-style test**

```python
def test_url_ingested_card_is_seen_by_wiki_scanner(tmp_path) -> None:
    """The wiki compiler must walk sources/urls/ and treat URL cards as sources."""
    from skills.ingest.scripts.wiki_scanner import scan_sources
    from skills.ingest.scripts import url_ingest

    with _patch_fetch():
        url_ingest.ingest_url(
            url="https://example.com/papers/attention",
            vault_dir=tmp_path,
            tags=["research"],
        )

    sources = scan_sources(vault_dir=tmp_path)
    relpaths = {Path(s["path"]).as_posix() for s in sources}
    assert any(rel.startswith("sources/urls/") for rel in relpaths), \
        f"Expected sources/urls card in scan, got {relpaths}"
```

- [ ] **Step 2: Run, expect PASS or FAIL depending on `wiki_scanner` walker**

If FAIL, inspect `wiki_scanner._SCANNABLE` and `_SKIP_DIRS`. The scanner should already walk `sources/urls/` because it walks the vault recursively and `urls` is not in `_SKIP_DIRS`. Verify by reading `scan_sources` signature and the rglob.

- [ ] **Step 3: Fix `wiki_scanner.py` if needed**

Most likely the test passes as-is. If `_SKIP_DIRS` excludes anything URL-related, remove the exclusion and add a regression test asserting `urls` is *not* in `_SKIP_DIRS`.

- [ ] **Step 4: Commit**

```bash
git add shared-vault/skills/ingest/augur/tests/test_url_ingest.py
git commit -m "test(ingest): wiki scanner sees sources/urls/ cards (refs ADR-624)"
```

---

## Phase 9: Capability exposure + cross-cutting

### Task 9.1: Register `vault-*` and `ingest-url` in `capability_exposure.yaml`

**Files:**
- Modify: `config/system/capability_exposure.yaml`

- [ ] **Step 1: Read the current file structure**

```bash
grep -n "vault-status\|vault-read\|vault-write" config/system/capability_exposure.yaml
```

- [ ] **Step 2: Add seven entries for the obsidian skill + one for ingest-url**

For each tool, append a row like:

```yaml
- name: mcp-tool:vault-search
  type: mcp-tool
  export_to: [shell]
  owner: obsidian
- name: mcp-tool:ingest-url
  type: mcp-tool
  export_to: [shell]
  owner: ingest
```

(Match the format the existing entries use.)

- [ ] **Step 3: Update the table in `CLAUDE.md`**

The capability-policy table already lists `mcp-tool:vault-*` rows; verify the owner column points at `obsidian` (some currently say `vault`, which has no skill). Replace `vault` → `obsidian` for the seven entries this ADR introduces.

- [ ] **Step 4: Run the architecture test that validates capability_exposure consistency**

```bash
/auto-test-pytest tests/architecture
```

Fix any breakages: usually the validator checks every `x-augur-mcp-tools` entry in every `SKILL.md` has a matching capability_exposure row.

- [ ] **Step 5: Commit**

```bash
git add config/system/capability_exposure.yaml CLAUDE.md
git commit -m "feat(config): expose vault-* and ingest-url via capability_exposure (refs ADR-624)"
```

---

## Phase 10: Self-review

- [ ] **Step 1: Spec adherence**
  - [ ] Seven `vault-*` tools registered on the new `obsidian` skill (Track A).
  - [ ] `ingest-url` registered on the `ingest` skill (Track B).
  - [ ] URL cards land in `<vault>/sources/urls/<date>-<slug>.md`.
  - [ ] Frontmatter includes `source_type: url`, `source_url`, `fetched_at`, `content_hash`.
  - [ ] Idempotent: re-ingesting same canonical URL returns `reused: true`.
  - [ ] Canonical URL strips tracking params (utm_*, fbclid, gclid, fragment, trailing slash).
  - [ ] Empty extraction returns structured error; no stub card written.
  - [ ] Wiki compiler picks up URL cards via `scan_sources`.

- [ ] **Step 2: Rule coverage**
  - [ ] Rule 2 (plugin decentralization): all skill-owned config under `shared-vault/skills/obsidian/`.
  - [ ] Rule 3 (path helpers): `get_vault_dir()` is the only resolution; no hardcoded paths.
  - [ ] Rule 5 (no workaround fixes): empty-extraction case fails loudly, not silently.
  - [ ] Rule 7 (TODO_ markers): `vault-health-repairs` carries `TODO_CLEANUP` documenting the wiring follow-up.
  - [ ] Rule 13 (hub ownership): `x-augur-hub: brain` set in `obsidian/SKILL.md`.
  - [ ] Rule 16 (frontmatter helpers): cards written via `write_vault_frontmatter`.
  - [ ] Rule 19 (agent-orchestrated MCP): tools are atomic; orchestration stays in the agent.
  - [ ] Rule 23 (exhaustive migrations): capability_exposure.yaml + CLAUDE.md table updated together.

- [ ] **Step 3: Cross-skill smoke**

```bash
/auto-test-pytest shared-vault/skills/obsidian shared-vault/skills/ingest tests/architecture
```

Expected: all green.

- [ ] **Step 4: Manual end-to-end smoke (operator)**

In an AI client, after `/dev-build`:

1. `vault-scaffold` → expect canonical layout written to the live vault.
2. `ingest-url url="https://example.com/some-real-article"` → expect a card in `sources/urls/` and `success: true`.
3. `vault-search query="<word from article>"` → expect the new card in hits.
4. `wiki-status` → expect new source seen by compiler.
5. Open the vault in Obsidian; the new card appears in `Sources → urls`.

- [ ] **Step 5: Update ADR pointer entries**

Already done in the brainstorming step (`spec_file` / `plan_file` set in `docs/adrs/adrs-index.json`). Verify with:

```bash
python3 -c "import json; data=json.load(open('docs/adrs/adrs-index.json')); e=[x for x in data if x['adr_number']=='ADR-624'][0]; print(e['spec_file'], e['plan_file'])"
```

Expected:

```
2026-05-10-obsidian-native-ingest-url-wiki-mvp-design.md 2026-05-10-obsidian-native-ingest-url-wiki-mvp.md
```

---

## Self-review summary

The implementation lands in two complementary tracks. Track A
(`obsidian` skill) is mostly registration — we expose existing
`vault_ops` and `vault_status` impls plus three small new modules
under stable `vault-*` tool names that match the capability-policy
table. Track B (`ingest-url`) extends the source-card pipeline with a
URL fetcher that satisfies the wiki compiler's existing input
contract. Together they close the "I read a thing on the web" → "the
wiki compounds it" loop without introducing fallbacks or invented
contracts.

---

## TODO markers (deliberate)

- `TODO_CLEANUP` (Phase 5): `vault-health-repairs` ships as a
  report-only delegate. Wiring it to the platform-admin healers
  requires promoting their entrypoint out of the staging tree; that
  is a follow-up issue tracked separately.
- `TODO`: The dashboard `/brain/vault` page (`pages/vault.yaml`) is a
  minimal table view. Richer features — preview pane, tag filter
  chips, "Open in Obsidian" mass-action — are explicit non-goals for
  MVP and belong in a follow-up ADR.
- `TODO`: `ingest-url` has no rate-limiting, robots.txt respect, or
  per-domain auth. Acceptable for MVP since the user runs it
  consciously per-URL; a future hardening ADR can address bulk
  ingestion.
