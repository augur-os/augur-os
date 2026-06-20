# ADR-751 Implementation Plan — Two-verb command surface and unified notes zone

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `/ingest` with `/note` as the daily input verb, collapse `<vault>/{inbox,sources,prompts}/` into a single `<vault>/notes/` zone typed by frontmatter, and fold the Browse `inbox`/`sources`/`prompts` tabs into one canonical `notes` tab with preset filter URLs.

**Architecture:** Augur four-layer harness — `/note` is the L2 policy (single command file under `shared-vault/skills/ingest/commands/note.md`), the L3 agent dispatches by argument shape, and existing L4 atomic ops (`save-url-source`, `save-prompt`, `inbox-consume-folder`) get rewired to write to `<vault>/notes/` with an `x-augur-note-type` frontmatter discriminator. The dashboard `notes` ViewMode becomes the canonical content tab; retired ViewModes (`inbox`, `sources`, `prompts`) redirect to filter-chip URLs over the same data.

**Tech Stack:** Python 3.11+, pytest (skill tests use `importlib.util.spec_from_file_location`, never dotted module paths — see memory `feedback-skill-test-convention`), Next.js 14 App Router, TypeScript, vitest for the dashboard tests, YAML frontmatter via `src/lib/frontmatter_utils.py`.

**Specs:** `docs/superpowers/specs/2026-05-15-gbrain-ingest-port-design.md`. **Related ADRs:** ADR-738, ADR-740, ADR-742, ADR-743, ADR-748, ADR-750. **Memory:** `feedback-skill-test-convention`, `feedback-command-capability-entry`, `feedback-skill-architecture-layering`, `feedback-vendor-neutral-design`, `feedback-client-side-verification`, `feedback-dashboard-ops`.

---

## File Structure

### Create

| Path | Responsibility |
|------|----------------|
| `docs/adrs/ADR-751-two-verb-command-surface-and-notes-zone.md` | Architecture decision record |
| `shared-vault/skills/ingest/commands/note.md` | L2 policy: `/note` command — dispatch table by argument shape |
| `shared-vault/skills/ingest/scripts/note_type.py` | Pure-logic helpers: detect note-type from argument, compute filename, validate type tag |
| `shared-vault/skills/ingest/augur/scripts/migrate_inbox_to_notes.py` | One-shot idempotent migration: `inbox/` + `sources/` + `prompts/` → `notes/` with `x-augur-note-type` frontmatter |
| `shared-vault/skills/ingest/augur/tests/test_note_type.py` | Unit tests for `note_type.py` |
| `shared-vault/skills/ingest/augur/tests/test_migrate_inbox_to_notes.py` | Unit tests for the migration script |
| `tests/dashboard/browse/viewMode-redirects.test.tsx` | Tests for retired ViewMode redirects |

### Modify

| Path | Change |
|------|--------|
| `shared-vault/skills/ingest/scripts/source_cards.py` | Write to `get_vault_notes_dir()` instead of `<vault>/sources/urls/`; add `x-augur-note-type: url` to frontmatter |
| `shared-vault/skills/ingest/scripts/prompt_cards.py` | Write to `get_vault_notes_dir()` instead of `get_vault_prompts_dir()`; add `x-augur-note-type: prompt` to frontmatter |
| `shared-vault/skills/ingest/scripts/mcp/inbox_tools.py` | `inbox-consume-folder` writes to `get_vault_notes_dir()`; add `x-augur-note-type: file` to frontmatter |
| `shared-vault/skills/ingest/scripts/mcp/url_tools.py` | If it owns path construction, redirect to notes dir |
| `shared-vault/skills/ingest/commands/ingest.md` | Convert to thin deprecation alias that delegates to `/note` with a one-time-per-session deprecation notice |
| `shared-vault/skills/ingest/SKILL.md` | Add `note` to `x-augur-commands`; mark `ingest` as `deprecated: true`; update `x-augur-dashboard-pages` to drop `/brain/inbox` |
| `config/system/capability_exposure.yaml` | Add `command:note:` entry; add `command:ingest:` entry marked `classification_status: deprecated` |
| `apps/dashboard/lib/browse/types.ts` | Retire `inbox`, `sources`, `prompts` from `ViewMode`; `notes` becomes canonical |
| `apps/dashboard/lib/browse/viewModeMapping.ts` | Redirect retired ViewModes to `notes` with filter query |
| `apps/dashboard/app/(views)/browse/page.tsx` | Handle retired-ViewMode redirects on initial render; add filter chip UI to `notes` view |
| `apps/dashboard/components/shared/BrowseCard.tsx` | Type-conditional metadata strip below the title; populate `typeBadge` from `x-augur-note-type` |
| `apps/dashboard/components/shared/BrowseDetailPanel.tsx` | Add type-conditional sections for `thought` and `image`; existing url/file/prompt sections stay |
| `tests/dashboard/components/shared/BrowseCard.test.tsx` | Add tests for new type badges and metadata strips |
| `tests/dashboard/browse/BrowseDetailPanel.test.tsx` | Add tests for new type-conditional sections |

### Rename (preserve git history with `git mv`)

| From | To |
|------|-----|
| `apps/dashboard/features/browse/IngestFAB.tsx` | `apps/dashboard/features/browse/NoteFAB.tsx` |
| `apps/dashboard/features/browse/IngestModal.tsx` | `apps/dashboard/features/browse/NoteModal.tsx` |
| `apps/dashboard/features/browse/IngestDropZone.tsx` | `apps/dashboard/features/browse/NoteDropZone.tsx` |
| `apps/dashboard/features/browse/IngestQueueItem.tsx` | `apps/dashboard/features/browse/NoteQueueItem.tsx` |

All imports of the renamed components in `apps/dashboard/` update to the new names; identifiers inside the files (component names, type names, prop names like `IngestUrlComposedResult`) all rename in lockstep.

---

## Task 1: Write ADR-751

**Files:**
- Create: `docs/adrs/ADR-751-two-verb-command-surface-and-notes-zone.md`

- [ ] **Step 1: Inspect the ADR template**

Run: `head -60 docs/adrs/ADR-750-content-aware-ingest-and-browser-first-fetch.md`
This gives the canonical frontmatter shape used by recent ADRs (Title, Status, Date, Stakeholders, plan_file, supersedes/superseded_by, decision/rationale/consequences sections).

- [ ] **Step 2: Write the ADR file**

Create `docs/adrs/ADR-751-two-verb-command-surface-and-notes-zone.md` with frontmatter matching ADR-750's pattern. Status `Proposed`. Date `2026-05-15`. `plan_file: docs/superpowers/plans/2026-05-15-adr-751-note-command-surface.md`. Sections:

- **Context:** Today's `/ingest`/`/save`/`/ask` overlap; daily-ergonomics gap; gbrain comparison; user choice for two-verb minimalism.
- **Decision:** `/note` as the only input verb; `<vault>/notes/` as the unified storage zone; Browse fold of `inbox`/`sources`/`prompts` tabs into `notes` with preset filter URLs.
- **Alternatives considered:** Three-verb intent split; single-verb smart router; keep `/ingest` and add `/signal`. (Reference the brainstorming spec for full options.)
- **Consequences:** Migration of `inbox/`+`sources/`+`prompts/` into `notes/`; capability_exposure.yaml gets a deprecation entry for `command:ingest`; one minor-version grace period with `/ingest` aliased to `/note`.
- **Non-goals:** Ambient signal-detector; archive-crawler; webhook-transforms; configurable entity templates; book-mirror; brain-pdf; media-ingest.
- **Implementation plan:** points to this plan file.

- [ ] **Step 3: Append ADR-751 to the ADR index**

Run: `python scripts/regenerate_adr_index.py` (or the equivalent — check `docs/generated/adr-index.md` header for the exact script reference).
Expected: `docs/generated/adr-index.md` now lists ADR-751 with status `Proposed`. `docs/adrs/adrs-index.json` contains the new entry.

- [ ] **Step 4: Commit**

```bash
git add docs/adrs/ADR-751-two-verb-command-surface-and-notes-zone.md docs/generated/adr-index.md docs/adrs/adrs-index.json
git commit -m "$(cat <<'EOF'
docs(adr): ADR-751 two-verb command surface and unified notes zone

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Pure-logic note-type helpers

**Files:**
- Create: `shared-vault/skills/ingest/scripts/note_type.py`
- Create: `shared-vault/skills/ingest/augur/tests/test_note_type.py`

- [ ] **Step 1: Write the failing test for `detect_note_type_from_arg`**

```python
# shared-vault/skills/ingest/augur/tests/test_note_type.py
"""Tests for note_type pure-logic helpers."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[5]
NOTE_TYPE_PATH = PROJECT_ROOT / "shared-vault" / "skills" / "ingest" / "scripts" / "note_type.py"


def _load_note_type():
    spec = importlib.util.spec_from_file_location("ingest_note_type", NOTE_TYPE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["ingest_note_type"] = module
    spec.loader.exec_module(module)
    return module


def test_detect_url():
    nt = _load_note_type()
    assert nt.detect_note_type_from_arg("https://hbr.org/leverage") == "url"
    assert nt.detect_note_type_from_arg("http://example.com/x") == "url"


def test_detect_file_pdf():
    nt = _load_note_type()
    assert nt.detect_note_type_from_arg("/tmp/report.pdf") == "file"


def test_detect_audio_m4a():
    nt = _load_note_type()
    assert nt.detect_note_type_from_arg("/tmp/voice.m4a") == "audio"


def test_detect_image_png():
    nt = _load_note_type()
    assert nt.detect_note_type_from_arg("/tmp/whiteboard.png") == "image"


def test_detect_thought_freetext(tmp_path):
    nt = _load_note_type()
    # Path does not exist and is not URL-shaped -> thought
    assert nt.detect_note_type_from_arg("I think RRF works because failures are orthogonal") == "thought"


def test_detect_folder(tmp_path):
    nt = _load_note_type()
    (tmp_path / "x").mkdir()
    assert nt.detect_note_type_from_arg(str(tmp_path / "x")) == "folder"


def test_valid_types_are_complete():
    nt = _load_note_type()
    assert set(nt.VALID_NOTE_TYPES) == {
        "url", "file", "thought", "voice-memo", "meeting", "image", "prompt", "folder", "audio",
    }
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd ~/Projects/Augur
uv run pytest shared-vault/skills/ingest/augur/tests/test_note_type.py -v
```
Expected: `FAILED` — `ModuleNotFoundError` because `note_type.py` does not yet exist.

- [ ] **Step 3: Implement `note_type.py`**

```python
# shared-vault/skills/ingest/scripts/note_type.py
"""Pure-logic helpers for /note argument-shape detection.

No I/O beyond stat() on filesystem-path arguments (to distinguish file vs folder).
The router in commands/note.md uses these helpers to decide which atomic op to call.
"""
from __future__ import annotations

import re
from pathlib import Path

URL_RE = re.compile(r"^https?://", re.IGNORECASE)

AUDIO_EXTS = {".m4a", ".mp3", ".wav", ".aac", ".flac", ".ogg", ".mp4", ".mov", ".m4v"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".heic", ".webp", ".gif"}
DOC_EXTS = {".pdf", ".docx", ".doc", ".md", ".html", ".htm", ".txt", ".rtf", ".epub"}

VALID_NOTE_TYPES = (
    "url",
    "file",
    "thought",
    "voice-memo",
    "meeting",
    "image",
    "prompt",
    "folder",
    "audio",
)


def detect_note_type_from_arg(arg: str) -> str:
    """Return the routing label for an /note argument.

    Returns one of: "url", "file", "audio", "image", "folder", "thought".
    "audio" is the routing label; audio-ingest (ADR-752) refines it to
    "voice-memo" or "meeting" based on transcript content. "prompt" is
    set by an explicit --as prompt flag, not by argument shape.
    """
    if not arg or not arg.strip():
        return "thought"  # interactive picker upstream; caller treats empty specially
    candidate = arg.strip()
    if URL_RE.match(candidate):
        return "url"
    path = Path(candidate)
    if path.exists():
        if path.is_dir():
            return "folder"
        suffix = path.suffix.lower()
        if suffix in AUDIO_EXTS:
            return "audio"
        if suffix in IMAGE_EXTS:
            return "image"
        if suffix in DOC_EXTS:
            return "file"
        # Unknown extension on an existing path: treat as file
        return "file"
    return "thought"


def is_valid_note_type(value: str) -> bool:
    return value in VALID_NOTE_TYPES
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
uv run pytest shared-vault/skills/ingest/augur/tests/test_note_type.py -v
```
Expected: all 7 tests pass.

- [ ] **Step 5: Commit**

```bash
git add shared-vault/skills/ingest/scripts/note_type.py shared-vault/skills/ingest/augur/tests/test_note_type.py
git commit -m "$(cat <<'EOF'
feat(ingest): add note_type detection helpers for /note router (ADR-751)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Atomic op `save-url-source` writes to `<vault>/notes/`

**Files:**
- Modify: `shared-vault/skills/ingest/scripts/source_cards.py`
- Modify: `shared-vault/skills/ingest/scripts/mcp/url_tools.py`
- Modify: `shared-vault/skills/ingest/augur/tests/test_source_cards.py`
- Modify: `shared-vault/skills/ingest/augur/tests/test_url_ingest_mcp.py`

- [ ] **Step 1: Read existing source_cards.py and url_tools.py**

```bash
cat shared-vault/skills/ingest/scripts/source_cards.py
cat shared-vault/skills/ingest/scripts/mcp/url_tools.py
```

Identify (a) where the target path is computed (look for `get_shared_vault_sources_dir`, `get_vault_dir`, `/sources/urls/`), and (b) where frontmatter is composed (look for `write_vault_frontmatter`).

- [ ] **Step 2: Modify `source_cards.py` to write to `get_vault_notes_dir()`**

Update the path-resolution function (typically `_target_path` or `card_path`) to compute the path under `get_vault_notes_dir()` instead of `get_vault_dir() / "sources" / "urls"`. Update the frontmatter composition to include `x-augur-note-type: url`. Keep the same filename slug pattern (`YYYY-MM-DD-url-<slug>.md`).

Concretely, find the line that today looks like:

```python
target = get_vault_dir() / "sources" / "urls" / f"{date_prefix}-{slug}.md"
```

and replace with:

```python
target = get_vault_notes_dir() / f"{date_prefix}-url-{slug}.md"
```

In the frontmatter dict passed to `write_vault_frontmatter`, add:

```python
"x-augur-note-type": "url",
```

- [ ] **Step 3: Modify the failing tests to expect notes/ path**

Open `shared-vault/skills/ingest/augur/tests/test_source_cards.py`. Find tests that assert path components like `"sources/urls"`; replace with `"notes"`. Add an assertion that the resulting frontmatter contains `x-augur-note-type: url`.

Example diff inside a test that previously read:

```python
assert "sources/urls" in str(card_path)
```

Replace with:

```python
assert card_path.parent.name == "notes"
fm, _ = parse_frontmatter(card_path.read_text())
assert fm["x-augur-note-type"] == "url"
```

- [ ] **Step 4: Run the tests**

```bash
uv run pytest shared-vault/skills/ingest/augur/tests/test_source_cards.py shared-vault/skills/ingest/augur/tests/test_url_ingest_mcp.py -v
```
Expected: PASS after the edits.

- [ ] **Step 5: Commit**

```bash
git add shared-vault/skills/ingest/scripts/source_cards.py shared-vault/skills/ingest/augur/tests/test_source_cards.py shared-vault/skills/ingest/augur/tests/test_url_ingest_mcp.py
git commit -m "$(cat <<'EOF'
feat(ingest): save-url-source writes to <vault>/notes with note-type frontmatter (ADR-751)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Atomic op `save-prompt` writes to `<vault>/notes/`

**Files:**
- Modify: `shared-vault/skills/ingest/scripts/prompt_cards.py`
- Modify: `shared-vault/skills/ingest/augur/tests/test_prompt_cards.py`
- Modify: `shared-vault/skills/ingest/augur/tests/test_save_prompt_mcp.py`

- [ ] **Step 1: Modify `prompt_cards.py` to target `notes/`**

Find the path-construction. Currently uses `get_vault_prompts_dir()`. Replace with `get_vault_notes_dir()`. Update slug template to `YYYY-MM-DD-prompt-<slug>.md`.

Frontmatter composition: add `x-augur-note-type: prompt` and `x-augur-prompt-triggerable: true`. Preserve all existing fields (placeholder list, label, description, source_url, etc.).

- [ ] **Step 2: Modify tests to expect new paths and frontmatter**

In `test_prompt_cards.py` and `test_save_prompt_mcp.py`, replace assertions about `"/prompts/"` with `card_path.parent.name == "notes"` and add an assertion `fm["x-augur-note-type"] == "prompt"`.

- [ ] **Step 3: Run the tests**

```bash
uv run pytest shared-vault/skills/ingest/augur/tests/test_prompt_cards.py shared-vault/skills/ingest/augur/tests/test_save_prompt_mcp.py -v
```
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add shared-vault/skills/ingest/scripts/prompt_cards.py shared-vault/skills/ingest/augur/tests/test_prompt_cards.py shared-vault/skills/ingest/augur/tests/test_save_prompt_mcp.py
git commit -m "$(cat <<'EOF'
feat(ingest): save-prompt writes to <vault>/notes with note-type frontmatter (ADR-751)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Atomic op `inbox-consume-folder` writes to `<vault>/notes/`

**Files:**
- Modify: `shared-vault/skills/ingest/scripts/mcp/inbox_tools.py`
- Modify: any helpers under `shared-vault/skills/ingest/scripts/inbox_*.py` that own path construction (likely `inbox_store.py` or `inbox_routing.py`)
- Modify: `shared-vault/skills/ingest/augur/tests/test_inbox_consume.py`
- Modify: `shared-vault/skills/ingest/augur/tests/test_inbox_tools.py`

- [ ] **Step 1: Locate path construction**

```bash
grep -n "vault_inbox\|/inbox/\|get_vault_inbox" shared-vault/skills/ingest/scripts/inbox_*.py shared-vault/skills/ingest/scripts/mcp/inbox_tools.py
```
Identify the function(s) that compute the persisted path (usually `_route_to_card_path` or similar in `inbox_routing.py`).

- [ ] **Step 2: Redirect path to `get_vault_notes_dir()`**

Change the target directory from `<vault>/inbox/<category>/` to `<vault>/notes/`. Preserve the filename slug pattern. Map the existing inbox category (which today determines a subfolder like `inbox/sources`, `inbox/promotions`) into a `x-augur-note-source` frontmatter field instead of a folder split.

In the frontmatter dict, set:

```python
"x-augur-note-type": "file",
"x-augur-note-source": category,  # was the inbox subfolder
```

- [ ] **Step 3: Modify tests**

Replace path-component assertions about `"/inbox/"` with `card_path.parent.name == "notes"`. Add an assertion that `fm["x-augur-note-type"] == "file"`.

- [ ] **Step 4: Run the tests**

```bash
uv run pytest shared-vault/skills/ingest/augur/tests/test_inbox_consume.py shared-vault/skills/ingest/augur/tests/test_inbox_tools.py shared-vault/skills/ingest/augur/tests/test_inbox_scan.py shared-vault/skills/ingest/augur/tests/test_inbox_routing.py -v
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add shared-vault/skills/ingest/scripts/mcp/inbox_tools.py shared-vault/skills/ingest/scripts/inbox_*.py shared-vault/skills/ingest/augur/tests/test_inbox_*.py
git commit -m "$(cat <<'EOF'
feat(ingest): inbox-consume-folder writes to <vault>/notes (ADR-751)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Migration script — `inbox/`+`sources/`+`prompts/` → `notes/`

**Files:**
- Create: `shared-vault/skills/ingest/augur/scripts/migrate_inbox_to_notes.py`
- Create: `shared-vault/skills/ingest/augur/tests/test_migrate_inbox_to_notes.py`

- [ ] **Step 1: Write the failing test**

```python
# shared-vault/skills/ingest/augur/tests/test_migrate_inbox_to_notes.py
"""Tests for the inbox-to-notes migration script."""
from __future__ import annotations

import importlib.util
import sys
import textwrap
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[5]
MIGRATE_PATH = PROJECT_ROOT / "shared-vault" / "skills" / "ingest" / "augur" / "scripts" / "migrate_inbox_to_notes.py"


def _load_migrate():
    spec = importlib.util.spec_from_file_location("ingest_migrate_inbox", MIGRATE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["ingest_migrate_inbox"] = module
    spec.loader.exec_module(module)
    return module


def _write_card(p: Path, frontmatter: dict, body: str = "stub body\n") -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    fm_lines = ["---"]
    for k, v in frontmatter.items():
        fm_lines.append(f"{k}: {v}")
    fm_lines.append("---\n")
    p.write_text("\n".join(fm_lines) + body)


def test_migrates_inbox_source_to_notes(tmp_path):
    m = _load_migrate()
    vault = tmp_path / "vault"
    inbox = vault / "inbox"
    notes = vault / "notes"
    notes.mkdir(parents=True, exist_ok=True)
    src = inbox / "2026-05-10-url-example.md"
    _write_card(src, {"title": "Example", "source": "url"})

    report = m.migrate_vault(vault, dry_run=False)
    assert report.moved == 1
    dst = notes / "2026-05-10-url-example.md"
    assert dst.exists()
    text = dst.read_text()
    assert "x-augur-note-type: url" in text
    assert not src.exists()


def test_migrates_prompts_to_notes(tmp_path):
    m = _load_migrate()
    vault = tmp_path / "vault"
    prompts = vault / "prompts"
    notes = vault / "notes"
    notes.mkdir(parents=True, exist_ok=True)
    src = prompts / "2026-05-10-prompt-pr-review.md"
    _write_card(src, {"label": "PR review", "prompt_triggerable": "true"})

    report = m.migrate_vault(vault, dry_run=False)
    assert report.moved == 1
    dst = notes / "2026-05-10-prompt-pr-review.md"
    assert dst.exists()
    text = dst.read_text()
    assert "x-augur-note-type: prompt" in text


def test_migrates_sources_url_to_notes(tmp_path):
    m = _load_migrate()
    vault = tmp_path / "vault"
    sources_urls = vault / "sources" / "urls"
    notes = vault / "notes"
    notes.mkdir(parents=True, exist_ok=True)
    src = sources_urls / "2026-05-10-url-example2.md"
    _write_card(src, {"title": "Example2", "url": "https://example.com"})

    report = m.migrate_vault(vault, dry_run=False)
    assert report.moved == 1
    dst = notes / "2026-05-10-url-example2.md"
    assert dst.exists()
    assert "x-augur-note-type: url" in dst.read_text()


def test_is_idempotent(tmp_path):
    m = _load_migrate()
    vault = tmp_path / "vault"
    notes = vault / "notes"
    notes.mkdir(parents=True, exist_ok=True)
    existing = notes / "2026-05-10-thought-already-migrated.md"
    _write_card(existing, {"title": "x", "x-augur-note-type": "thought"})

    report = m.migrate_vault(vault, dry_run=False)
    assert report.moved == 0
    assert report.skipped_already_migrated == 0
    # Idempotent re-run
    report2 = m.migrate_vault(vault, dry_run=False)
    assert report2.moved == 0


def test_dry_run_does_not_move(tmp_path):
    m = _load_migrate()
    vault = tmp_path / "vault"
    inbox = vault / "inbox"
    notes = vault / "notes"
    notes.mkdir(parents=True, exist_ok=True)
    src = inbox / "2026-05-10-url-example.md"
    _write_card(src, {"title": "Example", "source": "url"})

    report = m.migrate_vault(vault, dry_run=True)
    assert report.moved == 1  # would-move count
    assert src.exists()  # actually unchanged
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
uv run pytest shared-vault/skills/ingest/augur/tests/test_migrate_inbox_to_notes.py -v
```
Expected: `FAILED` with `ModuleNotFoundError`.

- [ ] **Step 3: Implement the migration script**

```python
# shared-vault/skills/ingest/augur/scripts/migrate_inbox_to_notes.py
"""One-shot, idempotent migration: <vault>/{inbox,sources,prompts}/ -> <vault>/notes/.

Each migrated card gets `x-augur-note-type` in its frontmatter, classified by
the source folder it came from. Already-migrated cards (existing
`x-augur-note-type`) are left untouched. Re-running is a no-op.

Logged to ADR-743 job ledger when the ledger module is available.
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Bootstrap PROJECT_ROOT onto sys.path so we can import from src.*
_PROJECT_ROOT = Path(__file__).resolve().parents[5]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.lib.frontmatter_utils import parse_frontmatter, write_vault_frontmatter  # noqa: E402


SOURCE_FOLDERS = (
    ("inbox", "file"),
    ("inbox/promotions", "file"),
    ("sources/urls", "url"),
    ("sources", "file"),
    ("prompts", "prompt"),
)


@dataclass
class MigrationReport:
    moved: int = 0
    skipped_already_migrated: int = 0
    skipped_collisions: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _classify_card(card_path: Path, default_type: str) -> str:
    """Decide the x-augur-note-type for a card based on its existing frontmatter.

    A prompt_triggerable flag overrides; otherwise the default for the
    source folder applies.
    """
    try:
        fm, _ = parse_frontmatter(card_path.read_text())
    except Exception:
        return default_type
    if fm.get("x-augur-note-type"):
        return str(fm["x-augur-note-type"])
    if fm.get("prompt_triggerable") in ("true", True, "True"):
        return "prompt"
    if fm.get("source") == "url":
        return "url"
    return default_type


def _walk_folder(vault: Path, sub: str) -> list[Path]:
    root = vault / sub
    if not root.exists():
        return []
    return sorted(p for p in root.rglob("*.md") if p.is_file())


def migrate_vault(vault: Path, *, dry_run: bool = True) -> MigrationReport:
    report = MigrationReport()
    notes_dir = vault / "notes"
    if not dry_run:
        notes_dir.mkdir(parents=True, exist_ok=True)

    seen_destinations: set[Path] = set()
    for sub, default_type in SOURCE_FOLDERS:
        for card in _walk_folder(vault, sub):
            note_type = _classify_card(card, default_type)
            dest = notes_dir / card.name

            if card.parent == notes_dir:
                report.skipped_already_migrated += 1
                continue
            if dest in seen_destinations or dest.exists():
                report.skipped_collisions.append(str(card.relative_to(vault)))
                continue
            seen_destinations.add(dest)

            if dry_run:
                report.moved += 1
                continue

            try:
                fm, body = parse_frontmatter(card.read_text())
                fm["x-augur-note-type"] = note_type
                write_vault_frontmatter(dest, fm, body)
                card.unlink()
                report.moved += 1
            except Exception as exc:  # noqa: BLE001
                report.errors.append(f"{card}: {exc}")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Migrate inbox/sources/prompts into notes/")
    parser.add_argument("--vault", type=Path, required=True, help="Vault root")
    parser.add_argument("--apply", action="store_true", help="Actually move files (default is dry-run)")
    args = parser.parse_args(argv)

    report = migrate_vault(args.vault, dry_run=not args.apply)
    mode = "APPLIED" if args.apply else "DRY-RUN"
    print(f"[{mode}] moved={report.moved} already_migrated={report.skipped_already_migrated} collisions={len(report.skipped_collisions)} errors={len(report.errors)}")
    if report.skipped_collisions:
        print("Collisions:")
        for c in report.skipped_collisions:
            print(f"  - {c}")
    if report.errors:
        print("Errors:")
        for e in report.errors:
            print(f"  - {e}")
    return 0 if not report.errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
uv run pytest shared-vault/skills/ingest/augur/tests/test_migrate_inbox_to_notes.py -v
```
Expected: all 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add shared-vault/skills/ingest/augur/scripts/migrate_inbox_to_notes.py shared-vault/skills/ingest/augur/tests/test_migrate_inbox_to_notes.py
git commit -m "$(cat <<'EOF'
feat(ingest): add idempotent inbox-to-notes migration script (ADR-751)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Run migration dry-run, inspect, then apply against the real vault

**Files:** none modified. Real-vault data migrated in place.

- [ ] **Step 1: Identify the real vault path**

```bash
uv run python -c "from src.config.paths import get_vault_dir; print(get_vault_dir())"
```
Note the path; use it as `--vault` below.

- [ ] **Step 2: Dry-run the migration**

```bash
uv run python shared-vault/skills/ingest/augur/scripts/migrate_inbox_to_notes.py --vault "$(uv run python -c 'from src.config.paths import get_vault_dir; print(get_vault_dir())')"
```
Expected output: `[DRY-RUN] moved=<N> already_migrated=<M> collisions=<K> errors=0` with K = 0 ideally.

- [ ] **Step 3: If collisions exist, resolve them**

Inspect each collision under the printed paths. A collision means two source folders contain a card with the same filename. Resolution: rename the older card (`git mv <oldpath> <oldpath>.bak.md`) and re-run dry-run until collisions=0.

- [ ] **Step 4: Apply the migration**

```bash
uv run python shared-vault/skills/ingest/augur/scripts/migrate_inbox_to_notes.py --vault "$(uv run python -c 'from src.config.paths import get_vault_dir; print(get_vault_dir())')" --apply
```
Expected: `[APPLIED] moved=<N> already_migrated=0 collisions=0 errors=0`.

- [ ] **Step 5: Spot-check three migrated cards**

```bash
ls "$(uv run python -c 'from src.config.paths import get_vault_notes_dir; print(get_vault_notes_dir())')" | head -10
head -20 "$(uv run python -c 'from src.config.paths import get_vault_notes_dir; print(get_vault_notes_dir())')"/$(ls "$(uv run python -c 'from src.config.paths import get_vault_notes_dir; print(get_vault_notes_dir())')" | head -1)
```
Expected: 10+ files listed; the spot-check shows frontmatter starts with `---` and includes `x-augur-note-type: <one of url/file/prompt>`.

- [ ] **Step 6: Confirm old folders are empty (or near-empty — only collisions left, if any)**

```bash
ls "$(uv run python -c 'from src.config.paths import get_vault_dir; print(get_vault_dir())')/inbox" 2>/dev/null
ls "$(uv run python -c 'from src.config.paths import get_vault_dir; print(get_vault_dir())')/prompts" 2>/dev/null
ls "$(uv run python -c 'from src.config.paths import get_vault_dir; print(get_vault_dir())')/sources" -R 2>/dev/null
```
Expected: empty or `.bak.md` only.

- [ ] **Step 7: Commit a session log**

This task does not modify the repo, but the migration is a checkpoint. Append a one-line note to `docs/migrations/2026-05-15-notes-zone-migration.md` (create it) with the moved-count and date. Commit.

```bash
mkdir -p docs/migrations
cat > docs/migrations/2026-05-15-notes-zone-migration.md <<'EOF'
# Notes-zone migration (ADR-751)

Date: 2026-05-15
Cards moved: <fill in actual count>
Vault: <fill in vault path>
Collisions: <fill in>

Old folders (`inbox/`, `sources/`, `prompts/`) retained as empty placeholders for one minor-version grace period.
EOF
git add docs/migrations/2026-05-15-notes-zone-migration.md
git commit -m "$(cat <<'EOF2'
chore(migration): record notes-zone migration outcome (ADR-751)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF2
)"
```

---

## Task 8: Write `/note` command policy

**Files:**
- Create: `shared-vault/skills/ingest/commands/note.md`

- [ ] **Step 1: Write the command file**

The command file is the L2 policy that an AI client renders into its slash command surface. It uses the same shape as `ingest.md`: YAML frontmatter with `description`, `visibility`, `x-augur-export-command`, then markdown body that instructs the agent how to dispatch.

```markdown
---
description: "Capture anything into your brain. /note <url|file|audio|image|folder|thought>. Same surface from any AI client. Agent picks the dispatcher; atomic ops persist. Use /note --help for the dispatch table."
visibility: core
x-augur-export-command: true
---
# /note Command Execution

This command sits at **L2 POLICY** in the surface decision matrix. It tells the agent what to do based on the argument shape. The agent (L3) picks the right atomic op. Atomic ops (L4 — `save-url-source`, `save-prompt`, `inbox-consume-folder`, `extract-audio` from ADR-752, etc.) only persist.

The argument-after-slash is in `ARGUMENTS`. Parse it before doing anything else.

## Dispatch

1. If `ARGUMENTS` is `--help` or `-h`: print the dispatch table from frontmatter `description` and stop (CLAUDE.md rule 15).
2. If `ARGUMENTS` is empty: open the interactive Note picker (dashboard `NoteModal` if running with dashboard surface; otherwise prompt the user for one of url/file/folder/thought).
3. Read flags first. If `--thought`, route to **Thought** below. If `--as prompt`, route to **Prompt**. If `--memo` or `--meeting`, route to **Audio** (forced sub-type). If `--from email`, route to **Email-drop**. If `--trigger <slug>`, route to **Trigger saved prompt**.
4. Otherwise dispatch by argument shape (use `shared-vault/skills/ingest/scripts/note_type.py:detect_note_type_from_arg`):
   - `url` → **URL** below
   - `audio` → **Audio** below
   - `image` → **Image** below
   - `file` → **File** below
   - `folder` → **Folder** below
   - `thought` (fallback) → **Thought** below

## URL

Same flow as `/ingest <url>` (see `ingest.md` for the full classification, fetch, validate, prompt-detect, persist sequence). The only difference: the atomic op `save-url-source` now writes under `<vault>/notes/` with `x-augur-note-type: url` (ADR-751). All other contracts are unchanged.

## File

Call atomic MCP tool `inbox-consume-folder` in single-file mode against the path (or, if a per-file MCP tool exists, prefer it). Frontmatter gets `x-augur-note-type: file`. Output is one note in `<vault>/notes/`.

## Audio

ADR-752 owns this path. Until ADR-752 ships, surface "Audio ingest not yet implemented (ADR-752)" to the user and stop — do not write a stub note (CLAUDE.md rule 1).

## Image

Call `document-extractor` for OCR + caption, then write a note with `x-augur-note-type: image`. Until the image-extraction MCP tool ships, surface the gap to the user. (Not in ADR-751 scope.)

## Folder

Same as `/ingest folder <path>` (see `ingest.md`).

## Thought

The user typed freeform text. Persist as a note under `<vault>/notes/` with `x-augur-note-type: thought`. Use the existing source-card writer with a thought-shaped slug (`YYYY-MM-DD-thought-<slug>.md`).

If the freeform text looks like a reusable prompt (instruction-shaped, contains `{{placeholder}}`, opens with system/role framing) — same content-aware sniff as `/ingest` (ADR-750) — ask before persisting:

> "This looks like a reusable prompt rather than a thought. Save it as a Prompt card (triggerable)?"

If the user confirms, route to **Prompt** below; otherwise persist as `thought`.

## Prompt

`--as prompt` is the explicit override. Call atomic MCP tool `save-prompt`. Frontmatter gets `x-augur-note-type: prompt` and `x-augur-prompt-triggerable: true`. Output is one note in `<vault>/notes/`.

## Trigger saved prompt

`--trigger <slug>` runs a saved prompt with current context. Read the prompt note from `<vault>/notes/`, fill any `{{placeholder}}` tokens by prompting the user, then dispatch the filled body to the active AI client. See ADR-748 for the trigger semantics.

## Email-drop

`--from email` calls the existing `email-drop-consume-source` atomic MCP tool. Output is one or more notes in `<vault>/notes/` per consumed message. (No change to email-drop semantics; only the destination folder changes per ADR-751.)

## Layering invariants for this command

- **The agent decides which fetcher to use** for URL paths (same as `/ingest`).
- **Atomic ops write to `<vault>/notes/`** unconditionally — never construct paths manually.
- **Deduplication is content-hash based** — re-noting the same content returns `deduplicated: true` from the atomic op and the existing card path. Surface that as "already saved".
- **Vendor neutrality.** Do not reference specific AI-client tool names. Refer to categories from agent-fetch-primitives.md.
- **Browser-first fetch for URLs** — per ADR-750.
- **Two-verb minimalism.** This command is the only input verb. `/save` remains for in-session artifact export; `/ask` for query. `/ingest` is the deprecation alias.
```

- [ ] **Step 2: Commit the command file**

```bash
git add shared-vault/skills/ingest/commands/note.md
git commit -m "$(cat <<'EOF'
feat(ingest): add /note command policy as canonical input verb (ADR-751)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: Convert `/ingest` into a deprecation alias

**Files:**
- Modify: `shared-vault/skills/ingest/commands/ingest.md`

- [ ] **Step 1: Replace the body of `ingest.md` with an alias notice**

Open `shared-vault/skills/ingest/commands/ingest.md`. Replace the entire body (keep frontmatter, update `description` to note the deprecation) with:

```markdown
---
description: "[DEPRECATED — use /note] Alias for /note. Will be removed next minor version. Usage matches /note exactly."
visibility: core
x-augur-export-command: true
x-augur-deprecated: true
x-augur-deprecated-in-favor-of: note
---
# /ingest Command Execution (DEPRECATED)

`/ingest` is an alias for `/note` and will be removed in the next minor version. Both commands accept identical arguments.

## Dispatch

1. Print a one-time-per-session deprecation notice: `"/ingest is deprecated; use /note instead. They take identical arguments."` (the AI client should track first-of-session and suppress for repeat calls within the same session).
2. Pass `ARGUMENTS` through to `/note` with no modification. The agent dispatches per `note.md`.

## Why this exists

Per ADR-751 the input surface collapses to a single daily verb. `/ingest` is kept as a thin pass-through for one minor-version cycle so existing scripts, docs, and muscle memory do not break overnight.
```

- [ ] **Step 2: Commit**

```bash
git add shared-vault/skills/ingest/commands/ingest.md
git commit -m "$(cat <<'EOF'
chore(ingest): convert /ingest to deprecation alias for /note (ADR-751)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: Update SKILL.md and capability_exposure.yaml

**Files:**
- Modify: `shared-vault/skills/ingest/SKILL.md`
- Modify: `config/system/capability_exposure.yaml`

- [ ] **Step 1: Update `shared-vault/skills/ingest/SKILL.md`**

Open the file. In the `x-augur-commands` list, add a new `note` entry (insert before the existing `ingest` entry); mark `ingest` as `deprecated: true`. Update `x-augur-dashboard-pages` to add `/brain/notes` if it is not already there; mark `/brain/inbox` as `deprecated: true` (or remove if the page is being retired in this task).

```yaml
x-augur-commands:
  - id: note
    type: workflow
    visibility: core
    description: Capture anything (URL, file, audio, image, folder, thought, prompt) into the brain. The single daily input verb. Atomic ops persist; agent dispatches.
  - id: ingest
    type: workflow
    visibility: core
    deprecated: true
    deprecated_in_favor_of: note
    description: "[DEPRECATED] Alias for /note. Removed next minor version."
```

- [ ] **Step 2: Update `config/system/capability_exposure.yaml`**

Per memory `feedback-command-capability-entry`: every new slash command needs a `command:<name>:` entry. Add `command:note:` with the same shape as other `command:` entries (look at an existing one like `command:save:` for the template). Add `command:ingest:` with `classification_status: deprecated`.

Approximate shape:

```yaml
  command:note:
    classification_status: approved
    export_to:
    - claude
    - codex
    - gemini
    management: generated
    owner_kind: augur
    preferred_client: claude
    primary_surface: command
    scope: project
  command:ingest:
    classification_status: deprecated
    export_to:
    - claude
    - codex
    - gemini
    management: generated
    owner_kind: augur
    preferred_client: claude
    primary_surface: command
    scope: project
```

(Exact `export_to` list and other fields should match the schema of other `command:` entries already in the file. Read the file first if uncertain.)

- [ ] **Step 3: Regenerate client surfaces**

Per memory `feedback-sync-agents-artifact-scope`: after editing command source, run `sync commands all` (or `sync all`) — do NOT use `sync agents all`.

```bash
augur sync commands all
```
Expected: `/note` appears in every client's generated command surface (`.claude/commands/`, `.codex/commands/`, `.gemini/skills/`).

- [ ] **Step 4: Commit**

```bash
git add shared-vault/skills/ingest/SKILL.md config/system/capability_exposure.yaml
git add .claude/commands/note.md .codex/commands/note.md .gemini/skills/ 2>/dev/null || true
git commit -m "$(cat <<'EOF'
feat(ingest): register /note command + deprecate /ingest in capability exposure (ADR-751)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: Retire `inbox`/`sources`/`prompts` ViewModes; canonicalize `notes`

**Files:**
- Modify: `apps/dashboard/lib/browse/types.ts`
- Modify: `apps/dashboard/lib/browse/viewModeMapping.ts` (or wherever ViewMode-to-route mapping lives)
- Modify: `apps/dashboard/app/(views)/browse/page.tsx`
- Create: `tests/dashboard/browse/viewMode-redirects.test.tsx`

- [ ] **Step 1: Inspect existing ViewMode usage**

```bash
grep -rn "ViewMode\|\"inbox\"\|\"sources\"\|\"prompts\"\|view=inbox\|view=sources\|view=prompts" apps/dashboard --include='*.ts' --include='*.tsx' | head -50
```
Note every site that uses `inbox`/`sources`/`prompts` as a ViewMode literal.

- [ ] **Step 2: Modify `apps/dashboard/lib/browse/types.ts`**

Remove `"inbox"`, `"sources"`, `"prompts"` from the `ViewMode` union (lines 1–27 in current file). The retained `"notes"` becomes canonical. Replace the three entries with a single comment noting their retirement and the redirect path:

```typescript
export type ViewMode =
  | "notes"        // canonical; was inbox/sources/prompts pre-ADR-751
  | "profile"
  | "memory"
  | "skills"
  // ... rest unchanged
```

Add a constant for redirects:

```typescript
export const RETIRED_VIEW_MODES: Record<string, { view: ViewMode; type?: string }> = {
  inbox: { view: "notes" },
  sources: { view: "notes", type: "url,file" },
  prompts: { view: "notes", type: "prompt" },
};
```

- [ ] **Step 3: Add redirect handling in `apps/dashboard/app/(views)/browse/page.tsx`**

On initial render (or in `useBrowseState`), check the URL `view` query param against `RETIRED_VIEW_MODES`; if matched, replace the URL with the canonical `notes` view and the preset `type` filter.

```typescript
import { RETIRED_VIEW_MODES } from "@/lib/browse/types";
import { useSearchParams, useRouter } from "next/navigation";

// inside the BrowsePage component
const searchParams = useSearchParams();
const router = useRouter();
useEffect(() => {
  const v = searchParams.get("view");
  if (v && v in RETIRED_VIEW_MODES) {
    const redirect = RETIRED_VIEW_MODES[v];
    const qs = new URLSearchParams(searchParams.toString());
    qs.set("view", redirect.view);
    if (redirect.type) qs.set("type", redirect.type);
    router.replace(`/browse?${qs.toString()}`);
  }
}, [searchParams, router]);
```

- [ ] **Step 4: Add filter-chip UI to the `notes` view**

Inside `BrowseToolbar.tsx` (or the equivalent toolbar component), when `viewMode === "notes"`, render filter chips for each `x-augur-note-type` value. Selecting a chip toggles the `type` URL query param. Multiple chips combine as comma-separated (`type=url,file`).

```tsx
{viewMode === "notes" && (
  <div className="flex flex-wrap gap-1.5">
    {(["url", "file", "thought", "voice-memo", "meeting", "image", "prompt"] as const).map((t) => (
      <button
        key={t}
        onClick={() => toggleTypeFilter(t)}
        className={`rounded-full border px-2.5 py-1 text-xs ${
          activeTypes.has(t)
            ? "bg-[var(--accent-primary)]/10 border-[var(--accent-primary)] text-[var(--accent-primary)]"
            : "border-[var(--border-color)] text-[var(--text-secondary)]"
        }`}
      >
        {t}
      </button>
    ))}
  </div>
)}
```

(`toggleTypeFilter` mutates the URL query; `activeTypes` parses it.)

- [ ] **Step 5: Write the failing redirect test**

```tsx
// tests/dashboard/browse/viewMode-redirects.test.tsx
import { describe, it, expect } from "vitest";
import { RETIRED_VIEW_MODES } from "@/lib/browse/types";

describe("RETIRED_VIEW_MODES", () => {
  it("redirects inbox -> notes (no type filter)", () => {
    expect(RETIRED_VIEW_MODES.inbox).toEqual({ view: "notes" });
  });
  it("redirects sources -> notes filtered to url,file", () => {
    expect(RETIRED_VIEW_MODES.sources).toEqual({ view: "notes", type: "url,file" });
  });
  it("redirects prompts -> notes filtered to prompt", () => {
    expect(RETIRED_VIEW_MODES.prompts).toEqual({ view: "notes", type: "prompt" });
  });
  it("does not list notes itself in retired modes", () => {
    expect(Object.keys(RETIRED_VIEW_MODES)).not.toContain("notes");
  });
});
```

- [ ] **Step 6: Run the test**

```bash
cd apps/dashboard && pnpm test viewMode-redirects -- --run
```
Expected: PASS (or FAIL with import error first, then PASS after fixing the import path).

- [ ] **Step 7: Commit**

```bash
git add apps/dashboard/lib/browse/types.ts apps/dashboard/lib/browse/viewModeMapping.ts apps/dashboard/app/\(views\)/browse/page.tsx apps/dashboard/app/\(views\)/browse/BrowseToolbar.tsx tests/dashboard/browse/viewMode-redirects.test.tsx
git commit -m "$(cat <<'EOF'
feat(dashboard): retire inbox/sources/prompts ViewModes; canonicalize notes (ADR-751)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 12: BrowseCard type-conditional metadata strip

**Files:**
- Modify: `apps/dashboard/components/shared/BrowseCard.tsx`
- Modify: `tests/dashboard/components/shared/BrowseCard.test.tsx`

- [ ] **Step 1: Read `BrowseCard.tsx` to find the metadata-strip location**

```bash
head -80 apps/dashboard/components/shared/BrowseCard.tsx
```
Identify where `typeBadge` is currently rendered. The strip lives directly under the title.

- [ ] **Step 2: Add type-to-icon mapping (Lucide names, not emoji)**

Near the top of `BrowseCard.tsx`, add:

```tsx
import { Link2, FileText, Lightbulb, Mic, Users, Zap, Image as ImageIcon } from "lucide-react";

const NOTE_TYPE_ICON: Record<string, React.ComponentType<{ size?: number; className?: string }>> = {
  url: Link2,
  file: FileText,
  thought: Lightbulb,
  "voice-memo": Mic,
  meeting: Users,
  prompt: Zap,
  image: ImageIcon,
};

const NOTE_TYPE_COLOR: Record<string, string> = {
  url: "text-blue-500",
  file: "text-slate-500",
  thought: "text-amber-500",
  "voice-memo": "text-purple-500",
  meeting: "text-purple-500",
  prompt: "text-emerald-500",
  image: "text-pink-500",
};
```

- [ ] **Step 3: Render the type badge from `typeBadge`**

In the card's title row, render the badge when `item.typeBadge` is present:

```tsx
{item.typeBadge && NOTE_TYPE_ICON[item.typeBadge] && (
  <span className={`inline-flex items-center gap-1 ${NOTE_TYPE_COLOR[item.typeBadge] ?? "text-slate-500"}`}>
    {(() => {
      const Icon = NOTE_TYPE_ICON[item.typeBadge];
      return <Icon size={12} />;
    })()}
    <span className="text-[10px] uppercase tracking-wide">{item.typeBadge}</span>
  </span>
)}
```

- [ ] **Step 4: Render type-specific metadata strip below the title**

```tsx
{item.metadata && item.typeBadge && (
  <div className="mt-0.5 text-[11px] text-[var(--text-muted)]">
    {item.typeBadge === "voice-memo" && item.metadata.duration_seconds && (
      <>{Math.round(Number(item.metadata.duration_seconds) / 60)} min · {item.metadata.transcript_status ?? "pending"}</>
    )}
    {item.typeBadge === "meeting" && (
      <>{Math.round(Number(item.metadata.duration_seconds ?? 0) / 60)} min · {item.metadata.attendee_count ?? "?"} attendees</>
    )}
    {item.typeBadge === "url" && item.metadata.source_domain && (
      <>{item.metadata.source_domain} · {item.metadata.enrichment_status ?? "raw"}</>
    )}
    {item.typeBadge === "prompt" && (
      <>triggers: {item.metadata.trigger_count ?? 0}{item.metadata.variable_count ? ` · vars: ${item.metadata.variable_count}` : ""}</>
    )}
  </div>
)}
```

- [ ] **Step 5: Add tests for the new badges**

In `tests/dashboard/components/shared/BrowseCard.test.tsx`, add cases for each of the 7 note types. Each test renders a `BrowseCard` with a stub `BrowseItem` that has `typeBadge: "<type>"` and the appropriate metadata, then asserts the badge label and the metadata-strip text both appear.

```tsx
import { render } from "@testing-library/react";
import { BrowseCard } from "@/components/shared/BrowseCard";
import { describe, it, expect } from "vitest";

const baseItem = {
  id: "x",
  title: "T",
  description: "D",
  hub: "brain",
  primaryAction: { label: "Open", type: "navigate" as const, target: "/x" },
};

describe("BrowseCard note-type badges", () => {
  it("renders url badge with source domain", () => {
    const { getByText } = render(
      <BrowseCard item={{ ...baseItem, typeBadge: "url", metadata: { source_domain: "hbr.org", enrichment_status: "enriched" } }} />
    );
    expect(getByText(/url/i)).toBeTruthy();
    expect(getByText(/hbr\.org/)).toBeTruthy();
  });

  it("renders voice-memo badge with duration", () => {
    const { getByText } = render(
      <BrowseCard item={{ ...baseItem, typeBadge: "voice-memo", metadata: { duration_seconds: "312", transcript_status: "complete" } }} />
    );
    expect(getByText(/voice-memo/i)).toBeTruthy();
    expect(getByText(/5 min/)).toBeTruthy();
  });

  it("renders meeting badge with attendee count", () => {
    const { getByText } = render(
      <BrowseCard item={{ ...baseItem, typeBadge: "meeting", metadata: { duration_seconds: "2280", attendee_count: "4" } }} />
    );
    expect(getByText(/meeting/i)).toBeTruthy();
    expect(getByText(/4 attendees/)).toBeTruthy();
  });

  it("renders prompt badge with trigger count", () => {
    const { getByText } = render(
      <BrowseCard item={{ ...baseItem, typeBadge: "prompt", metadata: { trigger_count: "7", variable_count: "3" } }} />
    );
    expect(getByText(/prompt/i)).toBeTruthy();
    expect(getByText(/triggers: 7/)).toBeTruthy();
  });
});
```

- [ ] **Step 6: Run the tests**

```bash
cd apps/dashboard && pnpm test BrowseCard -- --run
```
Expected: all new tests pass; existing tests still pass.

- [ ] **Step 7: Commit**

```bash
git add apps/dashboard/components/shared/BrowseCard.tsx tests/dashboard/components/shared/BrowseCard.test.tsx
git commit -m "$(cat <<'EOF'
feat(dashboard): BrowseCard type-conditional badge + metadata strip for note types (ADR-751)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 13: BrowseDetailPanel type-conditional sections (thought + image)

**Files:**
- Modify: `apps/dashboard/components/shared/BrowseDetailPanel.tsx`
- Modify: `tests/dashboard/browse/BrowseDetailPanel.test.tsx`

(Note: url/file/prompt detail sections already exist per ADR-748 and current `BrowseDetailPanel`. voice-memo and meeting sections are added in Plan 2 with ADR-752. Plan 1 only adds the `thought` and `image` sections.)

- [ ] **Step 1: Inspect existing detail-panel structure**

```bash
grep -n "typeBadge\|note-type\|kind\s*===" apps/dashboard/components/shared/BrowseDetailPanel.tsx | head -30
```
Find the switch/conditional that selects per-type rendering.

- [ ] **Step 2: Add `thought` section**

Inside `BrowseDetailPanel`, where other types branch, add a thought section that renders the note body + a "Linked entities" subsection (pull entity slugs from `item.metadata.linked_entities` if present):

```tsx
{item.typeBadge === "thought" && (
  <section className="space-y-2">
    <div className="prose prose-sm dark:prose-invert max-w-none">
      <pre className="whitespace-pre-wrap font-sans">{item.metadata?.body ?? ""}</pre>
    </div>
    {item.metadata?.linked_entities && (
      <div>
        <div className="text-[11px] uppercase tracking-wide text-[var(--text-muted)]">Linked entities</div>
        <div className="flex flex-wrap gap-1 mt-1">
          {item.metadata.linked_entities.split(",").map((slug) => (
            <a key={slug} href={`/brain/wiki/${slug.trim()}`} className="rounded bg-[var(--bg-secondary)] px-2 py-0.5 text-xs">
              {slug.trim()}
            </a>
          ))}
        </div>
      </div>
    )}
  </section>
)}
```

- [ ] **Step 3: Add `image` section**

```tsx
{item.typeBadge === "image" && (
  <section className="space-y-2">
    {item.metadata?.image_url && (
      // eslint-disable-next-line @next/next/no-img-element
      <img src={item.metadata.image_url} alt={item.title} className="max-h-96 rounded border border-[var(--border-color)]" />
    )}
    {item.metadata?.ocr_text && (
      <details className="text-sm">
        <summary className="cursor-pointer text-[var(--text-secondary)]">Extracted text (OCR)</summary>
        <pre className="mt-2 whitespace-pre-wrap rounded bg-[var(--bg-secondary)] p-2 text-xs">{item.metadata.ocr_text}</pre>
      </details>
    )}
    {item.metadata?.caption && <p className="text-sm text-[var(--text-secondary)]">{item.metadata.caption}</p>}
  </section>
)}
```

- [ ] **Step 4: Tests for both sections**

Add to `tests/dashboard/browse/BrowseDetailPanel.test.tsx`:

```tsx
it("renders thought body and linked entities", () => {
  const { getByText } = render(
    <BrowseDetailPanel item={{
      ...baseItem,
      typeBadge: "thought",
      metadata: { body: "I think X.", linked_entities: "concept-x,concept-y" },
    }} />
  );
  expect(getByText("I think X.")).toBeTruthy();
  expect(getByText("concept-x")).toBeTruthy();
});

it("renders image preview and OCR pane", () => {
  const { getByAltText, getByText } = render(
    <BrowseDetailPanel item={{
      ...baseItem,
      typeBadge: "image",
      metadata: { image_url: "data:image/png;base64,xyz", ocr_text: "hello", caption: "A whiteboard" },
    }} />
  );
  expect(getByAltText(baseItem.title)).toBeTruthy();
  expect(getByText(/Extracted text/)).toBeTruthy();
  expect(getByText("A whiteboard")).toBeTruthy();
});
```

- [ ] **Step 5: Run the tests**

```bash
cd apps/dashboard && pnpm test BrowseDetailPanel -- --run
```
Expected: new and existing tests pass.

- [ ] **Step 6: Commit**

```bash
git add apps/dashboard/components/shared/BrowseDetailPanel.tsx tests/dashboard/browse/BrowseDetailPanel.test.tsx
git commit -m "$(cat <<'EOF'
feat(dashboard): BrowseDetailPanel thought + image sections (ADR-751)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 14: Rename `Ingest*` components to `Note*`

**Files:**
- Rename (git mv): `apps/dashboard/features/browse/IngestFAB.tsx` → `NoteFAB.tsx`
- Rename (git mv): `apps/dashboard/features/browse/IngestModal.tsx` → `NoteModal.tsx`
- Rename (git mv): `apps/dashboard/features/browse/IngestDropZone.tsx` → `NoteDropZone.tsx`
- Rename (git mv): `apps/dashboard/features/browse/IngestQueueItem.tsx` → `NoteQueueItem.tsx`
- Modify: all importers in `apps/dashboard/`

- [ ] **Step 1: List all Ingest-prefixed dashboard symbols**

```bash
grep -rn "IngestFAB\|IngestModal\|IngestDropZone\|IngestQueueItem" apps/dashboard --include='*.tsx' --include='*.ts' | head -50
```
Capture the list — every file with an import or reference must be updated.

- [ ] **Step 2: `git mv` the four files**

```bash
git mv apps/dashboard/features/browse/IngestFAB.tsx apps/dashboard/features/browse/NoteFAB.tsx
git mv apps/dashboard/features/browse/IngestModal.tsx apps/dashboard/features/browse/NoteModal.tsx
git mv apps/dashboard/features/browse/IngestDropZone.tsx apps/dashboard/features/browse/NoteDropZone.tsx
git mv apps/dashboard/features/browse/IngestQueueItem.tsx apps/dashboard/features/browse/NoteQueueItem.tsx
```

- [ ] **Step 3: Rename inside each renamed file**

In each of the four files: rename the component (e.g. `export function IngestFAB(...)` → `export function NoteFAB(...)`), rename type exports (`type QueueItem`, `IngestUrlComposedResult`, etc. → `NoteUrlComposedResult`, etc.), rename internal handlers (`onIngest` → `onNote`, etc.). Update any user-facing strings: "Ingest" → "Note", "Run ingest" → "Capture note".

The agent should grep within each renamed file:

```bash
grep -n "Ingest" apps/dashboard/features/browse/NoteFAB.tsx apps/dashboard/features/browse/NoteModal.tsx apps/dashboard/features/browse/NoteDropZone.tsx apps/dashboard/features/browse/NoteQueueItem.tsx
```

and replace each match with the `Note` equivalent.

- [ ] **Step 4: Update importers**

For each file from Step 1's grep output that imports the renamed components, rewrite the import to use the new path and identifier. Example for `apps/dashboard/app/(views)/browse/page.tsx`:

```diff
- import { IngestDropZone } from "@/features/browse/IngestDropZone";
- import { IngestFAB } from "@/features/browse/IngestFAB";
- import { IngestModal } from "@/features/browse/IngestModal";
- import type { QueueItem } from "@/features/browse/IngestQueueItem";
+ import { NoteDropZone } from "@/features/browse/NoteDropZone";
+ import { NoteFAB } from "@/features/browse/NoteFAB";
+ import { NoteModal } from "@/features/browse/NoteModal";
+ import type { NoteQueueItem } from "@/features/browse/NoteQueueItem";
```

And in the JSX: `<IngestFAB ... />` → `<NoteFAB ... />`.

- [ ] **Step 5: TypeScript check + tests**

```bash
cd apps/dashboard && pnpm typecheck
cd apps/dashboard && pnpm test -- --run
```
Expected: no type errors; no test failures.

- [ ] **Step 6: Update any lingering `ingest` strings**

```bash
grep -rn '"ingest"\|"Ingest"\|>Ingest<' apps/dashboard --include='*.tsx' --include='*.ts' | grep -v "/skills/ingest" | head -30
```
Decide case-by-case: if the string is user-facing UI copy for the capture flow, rename to "Note"/"note". If it's a route to the `ingest` skill (e.g. capability_exposure references), leave alone — the skill name `ingest` stays internal.

- [ ] **Step 7: Commit**

```bash
git add apps/dashboard
git commit -m "$(cat <<'EOF'
refactor(dashboard): rename Ingest* components to Note* (ADR-751)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 15: Rebuild and verify dashboard end-to-end

**Files:** none modified. Real-data verification per CLAUDE.md Rule 28 + Rule 34.

- [ ] **Step 1: Rebuild dashboard via the slash command (Rule 29)**

```bash
/dev-build
```
Expected: build succeeds; dev server listens on the configured port (typically `localhost:3000`).

- [ ] **Step 2: Verify in a real browser per Rule 28**

Open `http://localhost:3000/browse?view=notes` in the browser (or via the Chrome MCP). Confirm:
  - The Notes tab loads to interactive state (no chunk-load error, no fatal toast)
  - Filter chips render (url, file, thought, voice-memo, meeting, image, prompt)
  - Cards render with the right type badges and metadata strips
  - Cards from the migrated vault data appear (not an empty grid)

- [ ] **Step 3: Verify retired-ViewMode redirects in the browser**

Open these URLs in turn and confirm the URL bar updates to the canonical filter-chip form:
  - `http://localhost:3000/browse?view=inbox` → `http://localhost:3000/browse?view=notes`
  - `http://localhost:3000/browse?view=sources` → `http://localhost:3000/browse?view=notes&type=url,file`
  - `http://localhost:3000/browse?view=prompts` → `http://localhost:3000/browse?view=notes&type=prompt`

- [ ] **Step 4: Verify a card detail panel for each type that has data**

Click into one card per type that exists in your vault (likely url, file, prompt, thought). Confirm the detail panel renders the right type-conditional sections.

- [ ] **Step 5: Document the verification in a session log**

Append a one-line note to `docs/migrations/2026-05-15-notes-zone-migration.md` recording the browser verification (browser used, screen size, ViewModes tested, card-count seen).

```bash
cat >> docs/migrations/2026-05-15-notes-zone-migration.md <<'EOF'

## Browser verification (2026-05-15)
- Browser: <Chrome MCP / Safari / Chromium>
- ViewModes tested: notes (canonical) + inbox/sources/prompts redirects
- Cards rendered: <count>
- Detail panels verified for types: <list>
EOF
git add docs/migrations/2026-05-15-notes-zone-migration.md
git commit -m "$(cat <<'EOF2'
chore(verify): browser verification of ADR-751 notes tab

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF2
)"
```

---

## Task 16: Real-data verification per Rule 34

**Files:** none modified. Concrete value-validation: run `/note` against real inputs and inspect the resulting note files.

- [ ] **Step 1: `/note <real URL>`**

In an active Claude/Codex/Gemini session, run:

```
/note https://www.lesswrong.com/posts/J78QF6yvvKDsRBsK4/the-best-textbooks-on-every-subject
```

Expected behaviour: agent dispatches to URL path, fetches the page, writes a card under `<vault>/notes/`. After the command completes:

```bash
ls -t "$(uv run python -c 'from src.config.paths import get_vault_notes_dir; print(get_vault_notes_dir())')" | head -1
head -20 "$(uv run python -c 'from src.config.paths import get_vault_notes_dir; print(get_vault_notes_dir())')/$(ls -t $(uv run python -c 'from src.config.paths import get_vault_notes_dir; print(get_vault_notes_dir())') | head -1)"
```
Expected: most-recent file is the new URL note; frontmatter contains `x-augur-note-type: url` and the canonical URL.

- [ ] **Step 2: `/note "<thought>"`**

```
/note "ADR-751 verification — two-verb surface feels lighter than the three-tab Browse already in five clicks."
```

Expected: writes a `type: thought` note. Verify the latest file in notes/ has `x-augur-note-type: thought`.

- [ ] **Step 3: `/note --as prompt`**

```
/note --as prompt "Review this PR for: (1) security (2) performance (3) test coverage. PR diff: {{diff}}"
```

Expected: writes a `type: prompt` note with `x-augur-prompt-triggerable: true` and the placeholder `{{diff}}` preserved. Verify by inspecting the latest notes/ file frontmatter.

- [ ] **Step 4: `/note <local PDF>`**

Find any PDF on the filesystem; run `/note <path-to-pdf>`. Expected: a `type: file` note is written; extracted text from the PDF appears in the body or in a linked extraction artifact.

- [ ] **Step 5: `/ingest <url>` deprecation notice**

```
/ingest https://example.com/something
```

Expected: command prints the deprecation notice (once per session), then dispatches identically to `/note`. The resulting card is in notes/ with the correct type.

- [ ] **Step 6: Report the verification**

In session-stop summary (or in a final comment to the user), state explicitly:
- The 5 real `/note` invocations run
- The actual file paths created in the real vault
- The actual frontmatter `x-augur-note-type` values observed

This satisfies CLAUDE.md Rule 34 — value validation must be against real data with concrete user-facing output, not tmp-fixture tests.

- [ ] **Step 7: Final commit**

If any artifacts were added during verification (a small Markdown report under `docs/migrations/`), commit them. No code changes expected here.

```bash
git status
git diff --stat
# If anything to commit:
git add docs/migrations/2026-05-15-notes-zone-migration.md
git commit -m "$(cat <<'EOF'
chore(verify): record ADR-751 real-data /note verifications

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Self-Review

After completing all tasks, run this checklist against the plan and the spec:

**1. Spec coverage**

| Spec section | Task |
|--------------|------|
| Command surface — `/note` daily verb | Task 8 |
| `/note` dispatch table | Task 8 (command policy body) |
| `/ingest` deprecation alias | Task 9 |
| Vault unification (notes zone) | Tasks 3, 4, 5, 6, 7 |
| `x-augur-note-type` frontmatter | Tasks 3, 4, 5, 6 |
| Browse `notes` canonical ViewMode | Task 11 |
| Retired-ViewMode redirects (inbox/sources/prompts) | Task 11 |
| Filter-chip UI in notes view | Task 11 step 4 |
| `BrowseItem.typeBadge` populated | Task 12 |
| BrowseCard type-conditional metadata strip | Task 12 |
| BrowseDetailPanel type-conditional sections (thought, image) | Task 13 |
| Capture-entry component renames (Ingest* → Note*) | Task 14 |
| Capability exposure entries for `note` + deprecated `ingest` | Task 10 |
| SKILL.md updates | Task 10 |
| ADR-751 document | Task 1 |
| Migration of `inbox`/`sources`/`prompts` to `notes` | Tasks 6, 7 |
| Migration idempotency | Task 6 step 1 (test) |
| Real-data verification per Rule 34 | Tasks 15, 16 |
| Browser verification per Rule 28 | Task 15 |

Gaps: none.

**2. Placeholder scan**

Search the plan for `TODO`, `TBD`, `fill in details`, `appropriate error handling`, `similar to`, `etc. (without enumeration)`. If any found, replace with concrete content.

```bash
grep -nE "TODO|TBD|FIXME|XXX|appropriate error|similar to Task" docs/superpowers/plans/2026-05-15-adr-751-note-command-surface.md
```
Expected: empty.

**3. Type consistency**

Cross-check identifiers used in later tasks against earlier definitions:
- `x-augur-note-type` — used in Tasks 3, 4, 5, 6, 12, 13. Spelled consistently throughout.
- `detect_note_type_from_arg` — defined in Task 2, referenced in Task 8 (command policy).
- `VALID_NOTE_TYPES` — defined in Task 2; not referenced elsewhere in the plan but available for ADR-752 use.
- `RETIRED_VIEW_MODES` — defined in Task 11; tested in Task 11 step 5.
- `migrate_vault` — defined in Task 6 step 3; invoked in Task 7 via the CLI.
- Component renames in Task 14 — every renamed identifier (`IngestFAB`→`NoteFAB`, etc.) is consistent in all four files and importers.

No inconsistencies.

---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-15-adr-751-note-command-surface.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration. Best when changes need fresh context per task.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints. Best when running the user is willing to keep this long session open.

Which approach?
