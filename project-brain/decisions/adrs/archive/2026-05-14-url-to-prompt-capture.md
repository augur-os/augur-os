# URL-to-Prompt Capture and Triggerable Prompt Cards — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a user capture a prompt from a URL with `/ingest <url> --as-prompt`, store it in their vault, see it under Browse → Prompts, and trigger it into their default CLI chat window with placeholder-fill.

**Architecture:** Reuse over rebuild. The URL fetch pipeline (`/ingest`), the `save-url-source` atomic-op pattern, the Browse file-card mechanism, the `chatStore.openChat` dispatch path, and the `{{placeholder}}` mini-form (already in `PromptCard.tsx`) all exist. New surface area: a `get_vault_prompts_dir()` helper, a `save-prompt` atomic op mirroring `save-url-source`, an `--as-prompt` branch in the ingest command doc, a vault-scan branch in `list_prompts_impl`, an extracted shared placeholder module, and a Trigger button on the Browse prompt card.

**Tech Stack:** Python 3.11+ (atomic ops, MCP tools, path helpers), FastMCP tool registration, Next.js / React / TypeScript (dashboard), Jest (dashboard tests), pytest (Python tests).

**Source of truth:** `docs/adrs/ADR-748-url-to-prompt-capture-and-triggerable-prompt-cards.md`.

**Test policy:** Per CLAUDE.md rules 19/29, whole-suite verification and commit-readiness go through `/auto-test-pytest`, `/auto-test-dashboard`, and `/auto-lint`. The per-step `pytest`/`jest` invocations below are for the TDD red→green cycle on a single test only — run the auto-loop at each phase checkpoint before moving on.

---

## File Structure

**Python (Phases 1–3):**
- `src/config/paths.py` — add `get_vault_prompts_dir()` (one-liner, mirrors `get_vault_notes_dir`).
- `shared-vault/skills/ingest/scripts/prompt_cards.py` — **new** pure-logic module: slug, content hash, placeholder extraction, `write_prompt_card`, `find_existing_prompt_card`.
- `shared-vault/skills/ingest/scripts/mcp/url_tools.py` — add `save_prompt_impl()` + `save-prompt` MCP tool registration inside the existing `register_url_tools()`.
- `shared-vault/skills/ingest/SKILL.md` — add `save-prompt` to `x-augur-mcp-tools`.
- `config/system/capability_exposure.yaml` — add `mcp-tool:save-prompt:` entry.
- `shared-vault/skills/ingest/commands/ingest.md` — add `--as-prompt` dispatch branch + `## Prompt ingestion` section + layering invariant.
- `src/mcp/augur_framework/tools/infrastructure/browse/skills.py` — extend `list_prompts_impl()` to scan the vault prompts dir.

**TypeScript / dashboard (Phases 3–4):**
- `apps/dashboard/lib/browse/types.ts` — extend `SkillPrompt` with `source`, `sourceUrl`, `placeholders`.
- `apps/dashboard/lib/browse/transforms.ts` — `prompts` case in the `actions` switch + `source` badge in metadata.
- `apps/dashboard/lib/browse/promptPlaceholders.ts` — **new** shared module; extract `PLACEHOLDER_PATTERN` / `extractVariables` / `resolvePromptBody` out of `PromptCard.tsx`.
- `apps/dashboard/components/browse/PromptCard.tsx` — refactor to import the extracted placeholder logic (no behavior change).
- `apps/dashboard/components/shared/BrowsePromptTrigger.tsx` — **new** button + inline placeholder form, mirrors the `BrowsePinButton` prop pattern.
- `apps/dashboard/components/shared/BrowseCard.tsx` — thread an optional `onTriggerPrompt` prop and render `BrowsePromptTrigger` for prompt items.
- `apps/dashboard/app/(views)/browse/useBrowseState.ts` (or the browse page) — wire `onTriggerPrompt` to `chatStore.openChat({ mode: "auto", initialPrompt })`.

**Tests:**
- `tests/src/test_paths.py` — extend for `get_vault_prompts_dir()`.
- `shared-vault/skills/ingest/augur/tests/test_prompt_cards.py` — **new**, pure-logic tests.
- `shared-vault/skills/ingest/augur/tests/test_save_prompt_mcp.py` — **new**, atomic-op tests.
- `tests/dashboard/browse/promptPlaceholders.test.ts` — **new**, placeholder-module tests.
- `tests/dashboard/browse/BrowsePromptTrigger.test.tsx` — **new**, component tests.

---

## Phase 1 — Storage + atomic op (Python, no UI)

### Task 1: `get_vault_prompts_dir()` path helper

**Files:**
- Modify: `src/config/paths.py` (the vault-helper block at lines 477–498)
- Test: `tests/src/test_paths.py`

- [ ] **Step 1: Write the failing test**

In `tests/src/test_paths.py`, add a new test next to `test_vault_first_helpers_share_vault_root`:

```python
def test_vault_prompts_dir_resolves_under_vault_root(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "_vault_home_dir", lambda: tmp_path / "vault")
    (tmp_path / "vault").mkdir()
    paths.invalidate_project_cache()

    assert paths.get_vault_prompts_dir() == tmp_path / "vault" / "prompts"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/src/test_paths.py::test_vault_prompts_dir_resolves_under_vault_root -v`
Expected: FAIL with `AttributeError: module 'src.config.paths' has no attribute 'get_vault_prompts_dir'`.

- [ ] **Step 3: Write minimal implementation**

In `src/config/paths.py`, add to the one-liner helper block (right after `get_vault_notes_dir`, ~line 489):

```python
def get_vault_prompts_dir() -> Path:
    return get_vault_dir() / "prompts"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/src/test_paths.py::test_vault_prompts_dir_resolves_under_vault_root -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/config/paths.py tests/src/test_paths.py
git commit -m "feat(paths): add get_vault_prompts_dir() for user-saved prompts"
```

---

### Task 2: `prompt_cards.py` — pure-logic helpers

**Files:**
- Create: `shared-vault/skills/ingest/scripts/prompt_cards.py`
- Test: `shared-vault/skills/ingest/augur/tests/test_prompt_cards.py`

This module mirrors `shared-vault/skills/ingest/scripts/url_ingest.py` (`compute_content_hash`, `slugify_url`, `write_url_source_card`, `find_existing_url_card`) but targets `get_vault_prompts_dir()` and adds `{{placeholder}}` extraction.

- [ ] **Step 1: Write the failing test**

Create `shared-vault/skills/ingest/augur/tests/test_prompt_cards.py`:

```python
"""Tests for prompt_cards — pure-logic helpers for user-saved prompts."""
from __future__ import annotations

from skills.ingest.scripts.prompt_cards import (
    compute_prompt_hash,
    extract_placeholders,
    find_existing_prompt_card,
    slugify_label,
    write_prompt_card,
)
from src.lib.frontmatter_utils import parse_frontmatter


def test_slugify_label_is_filesystem_safe():
    assert slugify_label("Define a Goal!") == "define-a-goal"
    assert slugify_label("  Multi   Space  ") == "multi-space"


def test_extract_placeholders_dedupes_preserving_order():
    body = "Given my {{goal}} and {{constraints}}, refine {{goal}}."
    assert extract_placeholders(body) == ["goal", "constraints"]


def test_extract_placeholders_empty_when_none():
    assert extract_placeholders("plain prompt, no slots") == []


def test_compute_prompt_hash_is_stable_and_content_sensitive():
    assert compute_prompt_hash("abc") == compute_prompt_hash("abc")
    assert compute_prompt_hash("abc") != compute_prompt_hash("abd")
    assert compute_prompt_hash("abc").startswith("sha256:")


def test_write_prompt_card_persists_under_prompts_dir(tmp_path):
    path = write_prompt_card(
        vault_dir=tmp_path,
        label="Define a Goal",
        description="Define then act on a goal",
        body="State your {{goal}} clearly.",
        source_url="https://example.com/goal-prompt",
    )
    assert path.parent == tmp_path / "prompts"
    meta, body = parse_frontmatter(path)
    assert meta["id"] == "define-a-goal"
    assert meta["label"] == "Define a Goal"
    assert meta["icon"] == "MessageSquare"
    assert meta["source_url"] == "https://example.com/goal-prompt"
    assert meta["placeholders"] == ["goal"]
    assert "State your {{goal}} clearly." in body


def test_find_existing_prompt_card_matches_by_content_hash(tmp_path):
    write_prompt_card(
        vault_dir=tmp_path, label="Reusable", description="d",
        body="reuse {{x}}", source_url="",
    )
    content_hash = compute_prompt_hash("reuse {{x}}")
    found = find_existing_prompt_card(tmp_path, content_hash)
    assert found is not None and found.parent == tmp_path / "prompts"
    assert find_existing_prompt_card(tmp_path, "sha256:deadbeef") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest shared-vault/skills/ingest/augur/tests/test_prompt_cards.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'skills.ingest.scripts.prompt_cards'`.

- [ ] **Step 3: Write minimal implementation**

Create `shared-vault/skills/ingest/scripts/prompt_cards.py`:

```python
"""Pure-logic helpers for user-saved prompt cards (ADR-748).

Mirrors url_ingest.py but targets <vault>/prompts/ and adds {{placeholder}}
extraction. No MCP, no I/O beyond the explicit vault_dir argument.
"""
from __future__ import annotations

import hashlib
import re
from datetime import date
from pathlib import Path

from src.lib.frontmatter_utils import parse_frontmatter, write_vault_frontmatter

_PLACEHOLDER_RE = re.compile(r"{{\s*([A-Za-z_][A-Za-z0-9_]*)\s*}}")
_SLUG_STRIP_RE = re.compile(r"[^a-z0-9]+")


def slugify_label(label: str, max_len: int = 80) -> str:
    """Filesystem-safe slug from a human label."""
    slug = _SLUG_STRIP_RE.sub("-", label.strip().lower()).strip("-")
    return slug[:max_len] or "prompt"


def extract_placeholders(body: str) -> list[str]:
    """Return {{slot}} names in first-seen order, deduplicated."""
    seen: list[str] = []
    for name in _PLACEHOLDER_RE.findall(body):
        if name not in seen:
            seen.append(name)
    return seen


def compute_prompt_hash(body: str) -> str:
    """Content hash of the prompt body, used for dedupe."""
    return f"sha256:{hashlib.sha256(body.encode()).hexdigest()}"


def _unique_path(target: Path) -> Path:
    if not target.exists():
        return target
    stem, suffix, parent = target.stem, target.suffix, target.parent
    n = 2
    while (candidate := parent / f"{stem}-{n}{suffix}").exists():
        n += 1
    return candidate


def write_prompt_card(
    *,
    vault_dir: Path,
    label: str,
    description: str,
    body: str,
    source_url: str = "",
    icon: str = "MessageSquare",
    today: date | None = None,
) -> Path:
    """Persist a prompt card under <vault_dir>/prompts/ and return its path."""
    today = today or date.today()
    prompts_dir = vault_dir / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    slug = slugify_label(label)
    target = _unique_path(prompts_dir / f"{slug}.md")

    frontmatter = {
        "id": slug,
        "label": label.strip(),
        "description": description.strip(),
        "icon": icon,
        "source": "vault",
        "content_hash": compute_prompt_hash(body),
        "placeholders": extract_placeholders(body),
        "captured_at": today.isoformat(),
    }
    if source_url:
        frontmatter["source_url"] = source_url

    write_vault_frontmatter(target, frontmatter, body.rstrip() + "\n")
    return target


def find_existing_prompt_card(vault_dir: Path, content_hash: str) -> Path | None:
    """Return the prompt card whose content_hash matches, else None."""
    prompts_dir = vault_dir / "prompts"
    if not prompts_dir.is_dir():
        return None
    for path in sorted(prompts_dir.glob("*.md")):
        meta, _ = parse_frontmatter(path)
        if meta.get("content_hash") == content_hash:
            return path
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest shared-vault/skills/ingest/augur/tests/test_prompt_cards.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add shared-vault/skills/ingest/scripts/prompt_cards.py shared-vault/skills/ingest/augur/tests/test_prompt_cards.py
git commit -m "feat(ingest): prompt_cards pure-logic helpers for user-saved prompts"
```

---

### Task 3: `save-prompt` atomic op + MCP registration + capability wiring

**Files:**
- Modify: `shared-vault/skills/ingest/scripts/mcp/url_tools.py` (add `save_prompt_impl` + register inside `register_url_tools`)
- Modify: `shared-vault/skills/ingest/SKILL.md` (add `save-prompt` to `x-augur-mcp-tools`)
- Modify: `config/system/capability_exposure.yaml` (add `mcp-tool:save-prompt:`)
- Test: `shared-vault/skills/ingest/augur/tests/test_save_prompt_mcp.py`

- [ ] **Step 1: Write the failing test**

Create `shared-vault/skills/ingest/augur/tests/test_save_prompt_mcp.py`:

```python
"""Behavioral tests for the save-prompt atomic op."""
from __future__ import annotations

import json

import pytest

from skills.ingest.scripts.mcp.url_tools import save_prompt_impl
from src.lib.frontmatter_utils import parse_frontmatter


@pytest.mark.asyncio
async def test_save_prompt_writes_card_and_returns_path(tmp_path):
    raw = await save_prompt_impl(
        label="Define a Goal",
        description="Define then act on a goal",
        body="State your {{goal}} clearly.",
        source_url="https://example.com/goal-prompt",
        vault_dir=tmp_path,
    )
    result = json.loads(raw)
    assert result["success"] is True
    assert result["deduplicated"] is False
    card = parse_frontmatter(result["path"])[0]
    assert card["id"] == "define-a-goal"
    assert card["placeholders"] == ["goal"]
    assert card["source"] == "vault"


@pytest.mark.asyncio
async def test_save_prompt_dedupes_by_content_hash(tmp_path):
    first = json.loads(await save_prompt_impl(
        label="Reusable", description="d", body="reuse {{x}}", vault_dir=tmp_path,
    ))
    second = json.loads(await save_prompt_impl(
        label="Reusable Again", description="d2", body="reuse {{x}}", vault_dir=tmp_path,
    ))
    assert second["deduplicated"] is True
    assert second["path"] == first["path"]


@pytest.mark.asyncio
async def test_save_prompt_requires_label_and_body(tmp_path):
    no_label = json.loads(await save_prompt_impl(
        label="", description="d", body="x", vault_dir=tmp_path))
    no_body = json.loads(await save_prompt_impl(
        label="L", description="d", body="", vault_dir=tmp_path))
    assert no_label["success"] is False and "label" in no_label["error"]
    assert no_body["success"] is False and "body" in no_body["error"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest shared-vault/skills/ingest/augur/tests/test_save_prompt_mcp.py -v`
Expected: FAIL with `ImportError: cannot import name 'save_prompt_impl'`.

- [ ] **Step 3: Write minimal implementation**

In `shared-vault/skills/ingest/scripts/mcp/url_tools.py`, add the impl function near `save_url_source_impl` (mirror its structure):

```python
async def save_prompt_impl(
    *,
    label: str = "",
    description: str = "",
    body: str = "",
    source_url: str = "",
    vault_dir: Path | None = None,
) -> str:
    """Persist a user prompt card under <vault>/prompts/. Inputs pre-parsed by caller."""
    from skills.ingest.scripts.prompt_cards import (
        compute_prompt_hash,
        find_existing_prompt_card,
        write_prompt_card,
    )
    from src.config.paths import get_vault_dir

    if not label.strip():
        return json.dumps({"success": False, "error": "label is required"}, indent=2)
    if not body.strip():
        return json.dumps({"success": False, "error": "body is required"}, indent=2)

    resolved_vault_dir = vault_dir or get_vault_dir()
    content_hash = compute_prompt_hash(body)
    existing = find_existing_prompt_card(resolved_vault_dir, content_hash)
    if existing is not None:
        return json.dumps({
            "success": True, "path": str(existing), "sha256": content_hash,
            "deduplicated": True, "label": label.strip(),
        }, indent=2)

    path = write_prompt_card(
        vault_dir=resolved_vault_dir, label=label, description=description,
        body=body, source_url=source_url,
    )
    return json.dumps({
        "success": True, "path": str(path), "sha256": content_hash,
        "deduplicated": False, "label": label.strip(),
    }, indent=2)
```

Then register the MCP tool inside `register_url_tools()` (after the `save_url_source_tool` block), mirroring its decorator stack:

```python
    @mcp.tool(
        name="save-prompt",
        annotations=tool_annotations(
            {
                "title": "Save Prompt Card",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def save_prompt_tool(
        label: str = "",
        description: str = "",
        body: str = "",
        source_url: str = "",
    ) -> str:
        """Persist a user prompt card. Inputs are pre-parsed by the caller."""
        if metrics:
            metrics.track_tool("save_prompt", skill="ingest")
        return await save_prompt_impl(
            label=label, description=description, body=body, source_url=source_url,
        )
```

In `shared-vault/skills/ingest/SKILL.md`, add `save-prompt` to `x-augur-mcp-tools:` immediately after `save-url-source`:

```yaml
  - save-url-source
  - save-prompt
```

In `config/system/capability_exposure.yaml`, add immediately after the `mcp-tool:save-url-source:` block:

```yaml
  mcp-tool:save-prompt:
    classification_status: approved
    export_to:
    - cli
    - agents-md
    - browse
    - mcp
    management: generated
    owner_kind: augur
    preferred_client: dashboard
    primary_surface: mcp
    scope: project
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest shared-vault/skills/ingest/augur/tests/test_save_prompt_mcp.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Phase 1 checkpoint — run the auto-loop**

Run `/auto-test-pytest` (narrowest scope covering `shared-vault/skills/ingest/` and `tests/src/`). Expected: green, no regressions.

- [ ] **Step 6: Commit**

```bash
git add shared-vault/skills/ingest/scripts/mcp/url_tools.py shared-vault/skills/ingest/SKILL.md config/system/capability_exposure.yaml shared-vault/skills/ingest/augur/tests/test_save_prompt_mcp.py
git commit -m "feat(ingest): save-prompt atomic op + MCP registration + capability entry"
```

---

## Phase 2 — Ingest command branch

### Task 4: `--as-prompt` branch in the `/ingest` command doc

**Files:**
- Modify: `shared-vault/skills/ingest/commands/ingest.md`

This is a policy-doc edit (no executable code, no test — it is L2 policy text the agent reads). Verification is a structural read-through.

- [ ] **Step 1: Add the Dispatch branch**

In `shared-vault/skills/ingest/commands/ingest.md`, in the `## Dispatch` list, add a new item between the current item 3 (`http(s)://` → URL ingestion) and item 4 (folder). Renumber folder to 5:

```markdown
4. If `ARGUMENTS` contains the `--as-prompt` flag (alongside an `http(s)://` URL): route to **Prompt ingestion** below.
5. If `ARGUMENTS` starts with `folder ` or is a filesystem path: route to **folder ingestion** below.
```

- [ ] **Step 2: Add the `## Prompt ingestion` section**

Insert a new section after `## URL ingestion` and before `## Folder ingestion`:

```markdown
## Prompt ingestion

`/ingest <url> --as-prompt` captures a *reusable prompt* from a page instead of a source card. Steps 1–5 of URL ingestion (classify, fetch, validate, decide) are identical and shared — only persistence differs.

1. Fetch the page exactly as in **URL ingestion** steps 1–5.
2. **Extract just the prompt.** The page may be an article that *contains* a prompt. Identify the actual reusable prompt text — not the surrounding commentary. If the prompt has fill-in spots, preserve them as `{{placeholder}}` tokens so the user can fill them at trigger time.
3. **Derive a label and description.** `label` — a short human title (e.g. "Define a Goal"). `description` — one line describing what the prompt does.
4. **Persist via the atomic op.** Call the MCP tool `save-prompt` with:
   - `label` — the human title
   - `description` — the one-line summary
   - `body` — the extracted prompt text, with `{{placeholder}}` tokens preserved
   - `source_url` — the page URL
   The tool returns `{success, path, sha256, deduplicated, label}`. Print the resolved card path. `deduplicated: true` means the same prompt body was already captured — surface that as "already saved".
```

- [ ] **Step 3: Add the layering invariant**

In `## Layering invariants for this command`, add a bullet after the source-cards bullet:

```markdown
- **Prompt cards land under `<vault>/prompts/`.** The `save-prompt` atomic op picks the path via `get_vault_prompts_dir()`; never construct it yourself. `--as-prompt` is a flag on URL ingestion, not a separate command.
```

- [ ] **Step 4: Verify structurally**

Read the edited file top-to-bottom. Confirm: the Dispatch list is sequentially numbered 1–5 with no gap (the pre-existing `1→3` gap in the URL-ingestion sub-list is out of scope — leave it), the new section references only `save-prompt` and `get_vault_prompts_dir()`, and no client-specific tool names appear (vendor neutrality).

- [ ] **Step 5: Commit**

```bash
git add shared-vault/skills/ingest/commands/ingest.md
git commit -m "feat(ingest): --as-prompt branch in the /ingest command policy doc"
```

---

## Phase 3 — Discovery

### Task 5: `list_prompts_impl` scans the vault prompts dir

**Files:**
- Modify: `src/mcp/augur_framework/tools/infrastructure/browse/skills.py` (`list_prompts_impl`)
- Test: `src/mcp/augur_framework/tools/infrastructure/browse/` test location — add `tests/mcp/test_list_prompts_vault.py` (root `tests/` tree; matches `testpaths = ["tests", "plugins"]`)

- [ ] **Step 1: Write the failing test**

Create `tests/mcp/test_list_prompts_vault.py`:

```python
"""list-prompts must also surface user prompts from <vault>/prompts/."""
from __future__ import annotations

import json

import pytest

from augur_framework.tools.infrastructure.browse.skills import list_prompts_impl
import src.config.paths as paths
from skills.ingest.scripts.prompt_cards import write_prompt_card


@pytest.mark.asyncio
async def test_list_prompts_includes_vault_prompts(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "_vault_home_dir", lambda: tmp_path / "vault")
    (tmp_path / "vault").mkdir()
    paths.invalidate_project_cache()
    write_prompt_card(
        vault_dir=tmp_path / "vault", label="Define a Goal",
        description="Define then act", body="State your {{goal}}.", source_url="",
    )

    result = json.loads(await list_prompts_impl())
    vault_items = [i for i in result["items"] if i.get("source") == "vault"]
    assert any(i["title"] == "Define a Goal" for i in vault_items)
    assert all("path" in i for i in vault_items)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/mcp/test_list_prompts_vault.py -v`
Expected: FAIL — no `source == "vault"` items (the vault dir is not scanned).

- [ ] **Step 3: Write minimal implementation**

In `src/mcp/augur_framework/tools/infrastructure/browse/skills.py`, inside `list_prompts_impl()`, after the existing three skill-scan loops and before `return json.dumps(...)`, add the vault scan. Also tag every existing skill item with `"source": "skill"` (add `"source": "skill",` to each of the three existing `items.append({...})` dicts):

```python
    # ADR-748: user-saved prompts from the vault.
    from src.config.paths import get_vault_prompts_dir

    vault_prompts_dir = get_vault_prompts_dir()
    if vault_prompts_dir.is_dir():
        for prompt_file in sorted(vault_prompts_dir.glob("*.md")):
            fm, body = _read_markdown_frontmatter(prompt_file)
            prompt_id = fm.get("id", prompt_file.stem)
            label = fm.get("label") or str(prompt_id).replace("-", " ").title()
            description = (
                fm.get("description")
                or _first_body_line(body)
                or "User-saved prompt"
            )
            items.append(
                {
                    "id": f"vault/prompts/{prompt_id}",
                    "title": label,
                    "description": description,
                    "hub": "brain",
                    "skill": None,
                    "source": "vault",
                    "path": str(prompt_file),
                    "file_type": "md",
                }
            )

    return json.dumps({"items": items, "count": len(items)})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/mcp/test_list_prompts_vault.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/mcp/augur_framework/tools/infrastructure/browse/skills.py tests/mcp/test_list_prompts_vault.py
git commit -m "feat(browse): list-prompts scans <vault>/prompts with a source discriminator"
```

---

### Task 6: Browse transform — prompts `actions` + `source` badge

**Files:**
- Modify: `apps/dashboard/lib/browse/types.ts` (`SkillPrompt` interface; `BrowseActionType` if a new type is added)
- Modify: `apps/dashboard/lib/browse/transforms.ts` (`prompts` case in the `actions` switch; `source` into `metadata`)
- Test: `tests/dashboard/browse/transformPrompts.test.ts`

Decision: reuse the existing `BrowseActionType` value `"run-action"` for the Trigger action rather than adding a new type — the actual interactive dispatch happens in the `BrowsePromptTrigger` component (Task 8), not in `executeBrowseAction`. The transform only needs to surface the trigger affordance and the `source` badge.

- [ ] **Step 1: Write the failing test**

Create `tests/dashboard/browse/transformPrompts.test.ts`:

```ts
import { transformIndexEntry } from "@/lib/browse/transforms";

describe("transformIndexEntry — prompts", () => {
  const baseEntry = {
    id: "vault/prompts/define-a-goal",
    title: "Define a Goal",
    description: "Define then act on a goal",
    source_path: "/vault/prompts/define-a-goal.md",
    source: "vault",
    metadata: { placeholders: ["goal"] },
  };

  it("carries the source badge in metadata", () => {
    const item = transformIndexEntry(baseEntry as never, "prompts");
    expect(item.metadata?.source).toBe("vault");
  });

  it("exposes a trigger action for prompt items", () => {
    const item = transformIndexEntry(baseEntry as never, "prompts");
    expect(item.actions?.some((a) => a.id === "trigger-prompt")).toBe(true);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/dashboard && pnpm jest ../../tests/dashboard/browse/transformPrompts.test.ts`
Expected: FAIL — `metadata.source` undefined and no `trigger-prompt` action.

- [ ] **Step 3: Write minimal implementation**

In `apps/dashboard/lib/browse/types.ts`, extend `SkillPrompt`:

```ts
export interface SkillPrompt {
  id: string;
  label: string;
  description?: string;
  prompt: string;
  icon?: string;
  source?: "skill" | "vault";
  sourceUrl?: string;
  placeholders?: string[];
}
```

In `apps/dashboard/lib/browse/transforms.ts`:

In the metadata-enrichment `case "prompts":` block (~line 1633), add the source passthrough:

```ts
    case "prompts": {
      const promptParts = (entry.source_path || "").split("/");
      const sIdx = promptParts.indexOf("skills");
      if (sIdx >= 0 && sIdx + 1 < promptParts.length) {
        enrichedMeta.skill = promptParts[sIdx + 1];
      }
      if (entry.source) enrichedMeta.source = String(entry.source);
      if (Array.isArray(entry.metadata?.placeholders)) {
        enrichedMeta.placeholders = (entry.metadata.placeholders as string[]).join(",");
      }
      break;
    }
```

In the secondary-`actions` switch (~line 1073–1205), add a `case "prompts":` that pushes the trigger action:

```ts
    case "prompts":
      actions.push({
        id: "trigger-prompt",
        label: "Trigger",
        icon: "Play",
        type: "run-action",
        target: entry.source_path || "",
      });
      break;
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/dashboard && pnpm jest ../../tests/dashboard/browse/transformPrompts.test.ts`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/lib/browse/types.ts apps/dashboard/lib/browse/transforms.ts tests/dashboard/browse/transformPrompts.test.ts
git commit -m "feat(browse): prompts carry source badge + trigger action in the transform"
```

---

## Phase 4 — Trigger UX

### Task 7: Extract the placeholder logic into a shared module

**Files:**
- Create: `apps/dashboard/lib/browse/promptPlaceholders.ts`
- Modify: `apps/dashboard/components/browse/PromptCard.tsx` (import from the new module instead of defining locally)
- Test: `tests/dashboard/browse/promptPlaceholders.test.ts`

`PromptCard.tsx` already defines `PLACEHOLDER_PATTERN`, `extractVariables`, and `resolvePromptBody`. This task moves those verbatim into a shared module so the new `BrowsePromptTrigger` (Task 8) can reuse them. No behavior change.

- [ ] **Step 1: Write the failing test**

Create `tests/dashboard/browse/promptPlaceholders.test.ts`:

```ts
import { extractVariables, resolvePromptBody } from "@/lib/browse/promptPlaceholders";

describe("promptPlaceholders", () => {
  it("extracts {{slots}} in first-seen order, deduplicated", () => {
    expect(extractVariables("use {{goal}} then {{ctx}} then {{goal}}")).toEqual(["goal", "ctx"]);
  });

  it("returns [] when there are no slots", () => {
    expect(extractVariables("plain prompt")).toEqual([]);
  });

  it("substitutes provided values, leaving unknown slots intact", () => {
    expect(resolvePromptBody("hi {{name}} from {{place}}", { name: "Ada" }))
      .toBe("hi Ada from {{place}}");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/dashboard && pnpm jest ../../tests/dashboard/browse/promptPlaceholders.test.ts`
Expected: FAIL — `Cannot find module '@/lib/browse/promptPlaceholders'`.

- [ ] **Step 3: Write minimal implementation**

First, open `apps/dashboard/components/browse/PromptCard.tsx` and copy the exact current definitions of `PLACEHOLDER_PATTERN`, `extractVariables`, and `resolvePromptBody`. Create `apps/dashboard/lib/browse/promptPlaceholders.ts` with those three symbols exported verbatim:

```ts
// apps/dashboard/lib/browse/promptPlaceholders.ts
// Shared {{placeholder}} parsing/substitution (ADR-748).
// Extracted verbatim from components/browse/PromptCard.tsx so the Browse
// prompt-card Trigger button can reuse identical semantics.

export const PLACEHOLDER_PATTERN = /{{\s*([A-Za-z_][A-Za-z0-9_]*)\s*}}/g;

export function extractVariables(body: string): string[] {
  // (paste the exact body from PromptCard.tsx)
}

export function resolvePromptBody(body: string, values: Record<string, string>): string {
  // (paste the exact body from PromptCard.tsx)
}
```

Then in `PromptCard.tsx`, delete the three local definitions and import them instead:

```ts
import { PLACEHOLDER_PATTERN, extractVariables, resolvePromptBody } from "@/lib/browse/promptPlaceholders";
```

- [ ] **Step 4: Run test to verify it passes (and PromptCard still works)**

Run: `cd apps/dashboard && pnpm jest ../../tests/dashboard/browse/promptPlaceholders.test.ts ../../tests/dashboard/browse/PromptCard.test.tsx`
Expected: PASS — new module tests pass AND the existing `PromptCard.test.tsx` still passes (proves no behavior change).

- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/lib/browse/promptPlaceholders.ts apps/dashboard/components/browse/PromptCard.tsx tests/dashboard/browse/promptPlaceholders.test.ts
git commit -m "refactor(browse): extract placeholder parsing into shared promptPlaceholders module"
```

---

### Task 8: `BrowsePromptTrigger` component + `BrowseCard` wiring + chat dispatch

**Files:**
- Create: `apps/dashboard/components/shared/BrowsePromptTrigger.tsx`
- Modify: `apps/dashboard/components/shared/BrowseCard.tsx` (thread `onTriggerPrompt` prop, render `BrowsePromptTrigger` for prompt items)
- Modify: `apps/dashboard/app/(views)/browse/useBrowseState.ts` (provide `onTriggerPrompt` → `chatStore.openChat`)
- Test: `tests/dashboard/browse/BrowsePromptTrigger.test.tsx`

`BrowsePromptTrigger` mirrors the `BrowsePinButton` prop pattern: a standalone component, threaded into `BrowseCard` via an optional prop. On click: if the prompt has placeholders, show an inline form (reusing `extractVariables` / `resolvePromptBody` from Task 7); on submit (or immediately, if no placeholders) call `onTrigger(resolvedPrompt)`. The page wires `onTrigger` to `chatStore.openChat({ mode: "auto", initialPrompt })` — the interactive default-CLI chat window the user described.

- [ ] **Step 1: Write the failing test**

Create `tests/dashboard/browse/BrowsePromptTrigger.test.tsx`:

```tsx
/** @jest-environment jsdom */
import { render, screen, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";
import { BrowsePromptTrigger } from "@/components/shared/BrowsePromptTrigger";

describe("BrowsePromptTrigger", () => {
  it("dispatches immediately when the prompt has no placeholders", () => {
    const onTrigger = jest.fn();
    render(<BrowsePromptTrigger promptBody="plain prompt" placeholders={[]} onTrigger={onTrigger} />);
    fireEvent.click(screen.getByRole("button", { name: /trigger/i }));
    expect(onTrigger).toHaveBeenCalledWith("plain prompt");
  });

  it("shows a form for placeholders and dispatches the resolved prompt", () => {
    const onTrigger = jest.fn();
    render(
      <BrowsePromptTrigger
        promptBody="State your {{goal}}."
        placeholders={["goal"]}
        onTrigger={onTrigger}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /trigger/i }));
    fireEvent.change(screen.getByLabelText("goal"), { target: { value: "ship ADR-748" } });
    fireEvent.click(screen.getByRole("button", { name: /send|run|dispatch/i }));
    expect(onTrigger).toHaveBeenCalledWith("State your ship ADR-748.");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/dashboard && pnpm jest ../../tests/dashboard/browse/BrowsePromptTrigger.test.tsx`
Expected: FAIL — `Cannot find module '@/components/shared/BrowsePromptTrigger'`.

- [ ] **Step 3: Write minimal implementation**

Create `apps/dashboard/components/shared/BrowsePromptTrigger.tsx`:

```tsx
"use client";

import { useState } from "react";
import { extractVariables, resolvePromptBody } from "@/lib/browse/promptPlaceholders";

interface BrowsePromptTriggerProps {
  promptBody: string;
  placeholders: string[];
  onTrigger: (resolvedPrompt: string) => void;
}

export function BrowsePromptTrigger({ promptBody, placeholders, onTrigger }: BrowsePromptTriggerProps) {
  const slots = placeholders.length > 0 ? placeholders : extractVariables(promptBody);
  const [open, setOpen] = useState(false);
  const [values, setValues] = useState<Record<string, string>>({});

  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (slots.length === 0) {
      onTrigger(promptBody);
      return;
    }
    setOpen(true);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onTrigger(resolvePromptBody(promptBody, values));
    setOpen(false);
    setValues({});
  };

  return (
    <>
      <button
        type="button"
        aria-label="Trigger prompt"
        onClick={handleClick}
        className="inline-flex items-center gap-1 rounded px-2 py-0.5 text-[11px] font-medium bg-[var(--accent-info)]/15 text-[var(--accent-info)]"
      >
        Trigger
      </button>
      {open && (
        <form onClick={(e) => e.stopPropagation()} onSubmit={handleSubmit} className="mt-2 space-y-2">
          {slots.map((slot) => (
            <label key={slot} className="block text-xs">
              <span className="text-[var(--text-muted)]">{slot}</span>
              <input
                aria-label={slot}
                value={values[slot] ?? ""}
                onChange={(e) => setValues((v) => ({ ...v, [slot]: e.target.value }))}
                className="mt-0.5 w-full rounded border border-[var(--border-color)] bg-[var(--bg-secondary)] px-2 py-1 text-sm"
              />
            </label>
          ))}
          <button type="submit" className="rounded bg-[var(--accent-info)] px-2 py-1 text-xs text-white">
            Send to CLI
          </button>
        </form>
      )}
    </>
  );
}
```

In `apps/dashboard/components/shared/BrowseCard.tsx`: add `onTriggerPrompt?: (resolvedPrompt: string) => void;` to `BrowseCardProps`, and render `BrowsePromptTrigger` in the actions area (line ~576, next to the primary button) when the item is a prompt:

```tsx
{onTriggerPrompt && item.category === "prompts" && (
  <BrowsePromptTrigger
    promptBody={item.metadata?.prompt ?? ""}
    placeholders={(item.metadata?.placeholders ?? "").split(",").filter(Boolean)}
    onTrigger={onTriggerPrompt}
  />
)}
```

(Confirm the field carrying the prompt body on `BrowseItem.metadata` while implementing — if the transform does not yet pass the body, add `enrichedMeta.prompt = entry.body ?? entry.description` to the Task 6 prompts metadata block and re-run Task 6's test.)

In `apps/dashboard/app/(views)/browse/useBrowseState.ts` (or wherever `BrowseCard` is rendered with its props), import `useChatStore` and provide the callback:

```ts
import { useChatStore } from "@/lib/stores/chatStore";
// ...
const openChat = useChatStore((s) => s.openChat);
const handleTriggerPrompt = (resolvedPrompt: string) => {
  openChat({ mode: "auto", initialPrompt: resolvedPrompt });
};
// pass onTriggerPrompt={handleTriggerPrompt} to <BrowseCard>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/dashboard && pnpm jest ../../tests/dashboard/browse/BrowsePromptTrigger.test.tsx`
Expected: PASS (2 tests).

- [ ] **Step 5: Phase 4 checkpoint — run the dashboard auto-loop + lint**

Run `/auto-test-dashboard` and `/auto-lint`. Expected: green, no regressions, no type errors.

- [ ] **Step 6: Commit**

```bash
git add apps/dashboard/components/shared/BrowsePromptTrigger.tsx apps/dashboard/components/shared/BrowseCard.tsx "apps/dashboard/app/(views)/browse/useBrowseState.ts" tests/dashboard/browse/BrowsePromptTrigger.test.tsx
git commit -m "feat(browse): Trigger button on prompt cards dispatches to the CLI chat window"
```

---

## Phase 5 — Verification

### Task 9: Full-stack verification

**Files:** none (verification only)

- [ ] **Step 1: Run the full auto-loop suite**

Run, in order: `/auto-test-pytest`, `/auto-test-dashboard`, `/auto-lint`, `/dev-build`. Expected: all green, no regressions.

- [ ] **Step 2: Impact Manifest stale-reference scan**

ADR-748 has an Impact Manifest (`/ingest --as-prompt`, `list-prompts` vault scan, `save-prompt`). Confirm zero stale references: every file in the manifest's `files_affected` was touched as planned, and no caller still assumes prompts are skill-only. Search for hardcoded `shared-vault/skills/*/prompts` assumptions outside `list_prompts_impl`.

- [ ] **Step 3: Real-browser verification of Browse → Prompts (rule 28)**

Identify the dashboard port for this checkout. In a real browser (or screenshot-capable browser tool), open `/browse`, select the **Prompts** category. Verify:
- A vault prompt (create one first via `save-prompt` or `/ingest <url> --as-prompt`) renders as a card with a `source: vault` badge distinct from skill prompts.
- The card shows a **Trigger** button.
- Triggering a prompt **with** `{{placeholders}}` opens the inline form; filling it and submitting opens the CLI chat window with the resolved prompt pre-loaded.
- Triggering a prompt **without** placeholders opens the chat window directly with the prompt body.
- Search/filter still behave correctly; the prompt card still opens its file via the existing open-file action.

The closeout must name the exact URL, the checkout/port, and confirm both trigger paths plus the source badge. Report any empty/error/stale states honestly.

- [ ] **Step 4: End-to-end manual smoke**

Run `/ingest <some-url-with-a-prompt> --as-prompt` in a CLI session. Confirm: a card lands under `<vault>/prompts/`, it appears in Browse → Prompts after refresh, and it triggers correctly. Re-run the same `/ingest` — confirm `deduplicated: true`.

- [ ] **Step 5: Final commit (if any verification fixes were needed)**

```bash
git add -A
git commit -m "test(browse): verification fixes for ADR-748 url-to-prompt capture"
```

---

## Self-Review

**1. Spec coverage** — ADR-748 Decision parts mapped to tasks:
- Part 1 (`--as-prompt` on `/ingest`) → Task 4. ✓
- Part 2 (vault home + `save-prompt` op) → Tasks 1, 2, 3. ✓
- Part 3 (`list-prompts` scans vault) → Task 5. ✓
- Part 4 (Trigger action wired to existing dispatch engine) → Tasks 6, 8. ✓ — uses `chatStore.openChat`, the existing interactive-window dispatch path; no new dispatch path built.
- Part 5 (placeholder-fill with graceful degradation) → Tasks 7, 8. ✓ — reuses the existing `PromptCard` placeholder logic, extracted to a shared module; placeholder-free prompts dispatch directly.

**2. Placeholder scan** — Task 7 Step 3 instructs "paste the exact body from `PromptCard.tsx`" rather than inlining code that does not yet exist in this plan's context; this is a verbatim-extraction refactor of code already in the repo, with the existing `PromptCard.test.tsx` as the regression guard. Task 8 Step 3 flags one field (`metadata.prompt`) to confirm-or-add during implementation, with the precise fix and re-test named. These are deliberate, bounded investigation points, not vague TODOs.

**3. Type consistency** — `SkillPrompt` gains `source`/`sourceUrl`/`placeholders` (Task 6) and those names are used consistently in the transform (Task 6), the trigger component props (Task 8), and the Python frontmatter (`source`, `source_url`, `placeholders` — Task 2). `save_prompt_impl` return keys (`success`, `path`, `sha256`, `deduplicated`, `label`) match the test assertions in Task 3 and the command doc in Task 4. `extractVariables` / `resolvePromptBody` keep their `PromptCard.tsx` names through the Task 7 extraction.

**Known follow-ups (out of scope, noted in ADR-748 Non-Goals):** no prompt-editing UI; remote-session dispatch fallback (the agent report noted `/api/cli/exec` rejects remote users — `chatStore.openChat` is used here instead, but a remote-session audit is worth a follow-up); de-duplication of pinned page cards in `pages` view is unrelated pre-existing ADR-728 behavior.
