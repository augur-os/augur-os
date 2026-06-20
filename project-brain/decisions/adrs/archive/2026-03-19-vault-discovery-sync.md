# Vault Discovery + Unified Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace path-based sync discovery with content-based `rgrep` discovery so vault files stay syncable regardless of directory moves.

**Architecture:** New `sync_discover.py` scanner greps vault for `sync_target:` frontmatter, returns typed `SyncItem` list. Existing sync systems (`note_sync.py`, `auto_sync.py`, `auto_notes_sync.py`) replace their path-based discovery with calls to the scanner. `sync_to_apple` field deleted everywhere.

**Tech Stack:** Python 3.11+, ripgrep (`rg`), YAML frontmatter, AppleScript (unchanged transport)

**Spec:** `docs/superpowers/specs/2026-03-19-vault-discovery-sync-design.md`

---

## File Map

### Files to CREATE

| File | Purpose |
|------|---------|
| `.claude/skills/apple/scripts/sync_discover.py` | Unified vault discovery scanner |
| `tests/skills/apple/test_sync_discover.py` | Unit tests for scanner |

### Files to MODIFY

| File | Lines Affected | Change |
|------|---------------|--------|
| `.claude/skills/apple/scripts/note_sync.py` | 306-343, 405-428 | Replace discovery + remove `sync_to_apple` checks |
| `.claude/skills/apple/scripts/notes_lib.py` | 150-161, 164-203, 233-257 | Delete `discover_all_notes_dirs()`, remove `sync_to_apple` from templates |
| `.claude/skills/apple/scripts/sync/auto_sync.py` | 22-25, 52 | Replace reminders dir scan with scanner |
| `.claude/skills/apple/scripts/sync/auto_notes_sync.py` | 24, 35 | Replace notes-sync dir scan with scanner |
| `.claude/skills/apple/scripts/mcp/tools_notes.py` | 277-282 | Replace `sync_to_apple` param with `sync_target` |
| `.claude/skills/apple/augur/api/notes/route.ts` | 15-23 | Replace `sync_to_apple: boolean` with `sync_target: string` in type |
| Vault `.md` files (~5-10) | Frontmatter | Remove `sync_to_apple`, ensure `sync_target` present |

---

## Task 1: Create sync_discover.py with tests (TDD)

**Files:**
- Create: `.claude/skills/apple/scripts/sync_discover.py`
- Create: `tests/skills/apple/test_sync_discover.py`

- [ ] **Step 1: Write failing tests**

Create `tests/skills/apple/test_sync_discover.py`:

```python
"""Tests for sync_discover — vault-wide content-based sync discovery."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

# Will import after implementation
# from scripts.sync_discover import discover, discover_by_target, SyncItem


class TestSyncDiscover:
    """Test the discover() function."""

    def test_discover_returns_sync_items(self, tmp_path):
        """Files with sync_target in frontmatter are discovered."""
        md = tmp_path / "test.md"
        md.write_text("---\ntitle: Test\nsync_target: notes\n---\nBody\n")

        from sync_discover import discover
        items = discover(vault_root=tmp_path)
        assert len(items) == 1
        assert items[0].sync_target == "notes"
        assert items[0].title == "Test"
        assert items[0].path == md

    def test_discover_skips_no_frontmatter(self, tmp_path):
        """Files without frontmatter are skipped."""
        md = tmp_path / "plain.md"
        md.write_text("# Just markdown\nNo frontmatter here\n")

        from sync_discover import discover
        items = discover(vault_root=tmp_path)
        assert len(items) == 0

    def test_discover_skips_sync_target_in_body(self, tmp_path):
        """sync_target in body text (not frontmatter) is ignored."""
        md = tmp_path / "docs.md"
        md.write_text("---\ntitle: Docs\n---\nUse sync_target: notes in frontmatter\n")

        from sync_discover import discover
        items = discover(vault_root=tmp_path)
        assert len(items) == 0

    def test_discover_skips_unknown_target(self, tmp_path):
        """Unknown sync_target values are skipped with warning."""
        md = tmp_path / "bad.md"
        md.write_text("---\ntitle: Bad\nsync_target: dropbox\n---\n")

        from sync_discover import discover
        items = discover(vault_root=tmp_path)
        assert len(items) == 0

    def test_discover_by_target_filters(self, tmp_path):
        """discover_by_target returns only matching target type."""
        (tmp_path / "a.md").write_text("---\ntitle: A\nsync_target: notes\n---\n")
        (tmp_path / "b.md").write_text("---\ntitle: B\nsync_target: reminders\nsync_list: Shopping\n---\n")

        from sync_discover import discover_by_target
        notes = discover_by_target("notes", vault_root=tmp_path)
        assert len(notes) == 1
        assert notes[0].title == "A"

        reminders = discover_by_target("reminders", vault_root=tmp_path)
        assert len(reminders) == 1
        assert reminders[0].sync_list == "Shopping"

    def test_discover_extracts_optional_fields(self, tmp_path):
        """Optional fields (sync_folder, sync_list, etc.) are extracted."""
        md = tmp_path / "full.md"
        md.write_text(
            "---\ntitle: Full\nsync_target: notes\n"
            "sync_folder: My Folder\nsync_id: abc123\n---\n"
        )

        from sync_discover import discover
        items = discover(vault_root=tmp_path)
        assert items[0].sync_folder == "My Folder"
        assert items[0].sync_id == "abc123"
        assert items[0].sync_list is None

    def test_discover_fallback_when_rg_missing(self, tmp_path):
        """Falls back to grep when ripgrep is not available."""
        md = tmp_path / "note.md"
        md.write_text("---\ntitle: Note\nsync_target: notes\n---\n")

        from sync_discover import discover
        # Force rg to fail
        with patch("sync_discover.shutil.which", return_value=None):
            items = discover(vault_root=tmp_path)
            assert len(items) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Projects/Augur && python -m pytest tests/skills/apple/test_sync_discover.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement sync_discover.py**

Create `.claude/skills/apple/scripts/sync_discover.py`:

```python
#!/usr/bin/env python3
"""
Unified vault-wide sync discovery.

Finds all files in the vault that declare sync_target in their YAML frontmatter.
Replaces path-based discovery (discover_all_notes_dirs, reminders dir scan).

Usage:
    python3 sync_discover.py                    # table output
    python3 sync_discover.py --json             # JSON output
    python3 sync_discover.py --target notes     # filter by target
    python3 sync_discover.py --target reminders # filter by target
"""
from __future__ import annotations

import argparse
import json
import logging
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

# ─── project root & sys.path ──────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

try:
    from src.config.paths import get_vault_root
except ImportError:
    def get_vault_root() -> Path:
        return Path.home() / "Vault" / "Augur"

try:
    from src.logging import get_entity_logger
    logger = get_entity_logger("sync_discover")
except ImportError:
    logger = logging.getLogger("sync_discover")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s | %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

# ─── constants ────────────────────────────────────────────────────────────────

KNOWN_TARGETS = {"notes", "reminders"}


# ─── data model ───────────────────────────────────────────────────────────────

@dataclass
class SyncItem:
    """A vault file that declares itself as syncable."""
    path: Path
    sync_target: str
    title: str
    sync_folder: str | None = None
    sync_list: str | None = None
    sync_section: str | None = None
    sync_id: str | None = None


# ─── discovery ────────────────────────────────────────────────────────────────

def _find_candidates(vault_root: Path) -> list[Path]:
    """Find .md files containing sync_target: using rg, falling back to grep."""
    rg = shutil.which("rg")
    if rg:
        result = subprocess.run(
            [rg, "-l", "^sync_target:", str(vault_root), "--glob", "*.md"],
            capture_output=True, text=True, timeout=30,
        )
        paths = [Path(p) for p in result.stdout.strip().splitlines() if p]
    else:
        logger.info("ripgrep not found, falling back to grep")
        result = subprocess.run(
            ["grep", "-rl", "^sync_target:", str(vault_root), "--include=*.md"],
            capture_output=True, text=True, timeout=60,
        )
        paths = [Path(p) for p in result.stdout.strip().splitlines() if p]
    return sorted(paths)


def _parse_frontmatter_only(filepath: Path) -> dict:
    """Parse just the YAML frontmatter from a file, ignoring body."""
    import yaml

    text = filepath.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    end = text.find("---", 3)
    if end == -1:
        return {}
    try:
        return yaml.safe_load(text[3:end]) or {}
    except yaml.YAMLError:
        logger.warning(f"Malformed frontmatter in {filepath}")
        return {}


def discover(vault_root: Path | None = None) -> list[SyncItem]:
    """Discover all syncable files in the vault via content-based search."""
    root = vault_root or get_vault_root()
    candidates = _find_candidates(root)
    items: list[SyncItem] = []

    for filepath in candidates:
        try:
            fm = _parse_frontmatter_only(filepath)
        except (OSError, UnicodeDecodeError) as e:
            logger.warning(f"Cannot read {filepath}: {e}")
            continue

        target = fm.get("sync_target")
        if not target:
            continue  # sync_target was in body, not frontmatter

        if target not in KNOWN_TARGETS:
            logger.warning(f"Unknown sync_target '{target}' in {filepath}, skipping")
            continue

        items.append(SyncItem(
            path=filepath,
            sync_target=target,
            title=fm.get("title", filepath.stem),
            sync_folder=fm.get("sync_folder"),
            sync_list=fm.get("sync_list"),
            sync_section=fm.get("sync_section"),
            sync_id=fm.get("sync_id"),
        ))

    return items


def discover_by_target(target: str, vault_root: Path | None = None) -> list[SyncItem]:
    """Discover syncable files filtered by target type."""
    return [item for item in discover(vault_root) if item.sync_target == target]


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Discover syncable vault files")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--target", choices=list(KNOWN_TARGETS), help="Filter by sync target")
    args = parser.parse_args()

    if args.target:
        items = discover_by_target(args.target)
    else:
        items = discover()

    if args.json:
        print(json.dumps([{**asdict(i), "path": str(i.path)} for i in items], indent=2))
    else:
        if not items:
            print("No syncable files found.")
            return
        print(f"{'Target':<12} {'Title':<30} {'Path'}")
        print(f"{'─' * 12} {'─' * 30} {'─' * 50}")
        for item in items:
            print(f"{item.sync_target:<12} {item.title:<30} {item.path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Projects/Augur && python -m pytest tests/skills/apple/test_sync_discover.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Test CLI manually**

Run: `python3 .claude/skills/apple/scripts/sync_discover.py --target notes`
Expected: Lists the 3 ideas files + any existing notes-sync files

Run: `python3 .claude/skills/apple/scripts/sync_discover.py --json`
Expected: JSON array of SyncItem objects

- [ ] **Step 6: Commit**

```bash
git add .claude/skills/apple/scripts/sync_discover.py tests/skills/apple/test_sync_discover.py
git commit -m "feat: add sync_discover.py — content-based vault sync discovery"
```

---

## Task 2: Rewire note_sync.py to use scanner

**Files:**
- Modify: `.claude/skills/apple/scripts/note_sync.py` (lines 306-343, 405-428)

- [ ] **Step 1: Replace sync_all() discovery**

In `note_sync.py`, replace the `sync_all()` function (lines 405-428). Change from:

```python
notes_dirs = notes_lib.discover_all_notes_dirs(PROJECT_ROOT)
# ...iterates dirs, globs *.md, checks sync_to_apple
```

To:

```python
import sync_discover

def sync_all() -> int:
    """Sync all notes with sync_target: notes across the vault."""
    items = sync_discover.discover_by_target("notes")
    synced = 0
    for item in items:
        if sync_note_to_apple(item.path):
            synced += 1
    logger.info(f"Sync complete: {synced} notes synced to Apple Notes")
    return synced
```

- [ ] **Step 2: Remove sync_to_apple check from _do_sync()**

In `_do_sync()` (line 332), remove the guard:

```python
# DELETE this block:
if fm.get("sync_to_apple") is not True:
    logger.debug(f"sync_to_apple not true for {filepath.name}, skipping")
    return False
```

The scanner already filtered for `sync_target: notes` — no need to double-check.

- [ ] **Step 3: Remove sync_to_apple check from sync_note_to_apple()**

In `sync_note_to_apple()` (around line 332), remove:

```python
# DELETE:
if fm.get("sync_to_apple") is not True:
    logger.debug(f"sync_to_apple not true for {filepath.name}, skipping")
    return False
```

Keep the function accepting a `filepath` parameter — it's called directly for single-file sync.

- [ ] **Step 4: Test**

Run: `python3 .claude/skills/apple/scripts/note_sync.py --all`
Expected: Finds and syncs the 3 ideas files + any existing synced notes

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/apple/scripts/note_sync.py
git commit -m "feat: rewire note_sync.py to use sync_discover scanner"
```

---

## Task 3: Rewire auto_sync.py (reminders discovery)

**Files:**
- Modify: `.claude/skills/apple/scripts/sync/auto_sync.py` (lines 22-25, 52)

- [ ] **Step 1: Read auto_sync.py fully**

Read the entire file to understand the scan() function flow before modifying.

- [ ] **Step 2: Replace _get_reminders_dir() and directory scan**

Replace the reminders directory scan logic (lines 22-25, and the dir iteration around line 52) with:

```python
import sync_discover

# Replace _get_reminders_dir() usage and directory iteration with:
items = sync_discover.discover_by_target("reminders")
```

The `SyncItem.sync_list` provides the list name (previously derived from directory names). Pass it to the sync engine where `list_name` was used.

- [ ] **Step 3: Test**

Run: `python3 .claude/skills/apple/scripts/sync/auto_sync.py`
Expected: Discovers reminders lists via frontmatter, syncs as before

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/apple/scripts/sync/auto_sync.py
git commit -m "feat: rewire auto_sync.py reminders discovery to use scanner"
```

---

## Task 4: Rewire auto_notes_sync.py

**Files:**
- Modify: `.claude/skills/apple/scripts/sync/auto_notes_sync.py` (lines 24, 35)

- [ ] **Step 1: Read auto_notes_sync.py fully**

- [ ] **Step 2: Replace notes-sync directory scan**

Replace the path-based discovery (line 24: `get_skill_vault_dir("apple") / "notes-sync"`, line 35: folder iteration with `_sync.yaml` check) with:

```python
import sync_discover

items = sync_discover.discover_by_target("notes")
```

- [ ] **Step 3: Test**

Run: `python3 .claude/skills/apple/scripts/sync/auto_notes_sync.py`
Expected: Discovers notes via frontmatter, syncs as before

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/apple/scripts/sync/auto_notes_sync.py
git commit -m "feat: rewire auto_notes_sync.py discovery to use scanner"
```

---

## Task 5: Delete discover_all_notes_dirs() and clean notes_lib.py

**Files:**
- Modify: `.claude/skills/apple/scripts/notes_lib.py` (lines 150-161, 164-203, 233-257)

- [ ] **Step 1: Delete discover_all_notes_dirs()**

Remove the entire function (lines 233-257). It is no longer called by any code after Tasks 2-4.

- [ ] **Step 2: Remove sync_to_apple from DEFAULT_TEMPLATE**

In `DEFAULT_TEMPLATE` (line 157), remove the `sync_to_apple: {sync_to_apple}` line.

- [ ] **Step 3: Remove sync_to_apple from create_note()**

In `create_note()` (line 171), remove the `sync_to_apple: bool = False` parameter and any reference to it in the frontmatter output.

- [ ] **Step 4: Remove sync_to_apple from build_index_cache()**

In `build_index_cache()` (line 106), remove `sync_to_apple` from the cached fields.

- [ ] **Step 5: Verify no remaining references**

Run: `rg "sync_to_apple" .claude/skills/apple/scripts/notes_lib.py`
Expected: 0 matches

Run: `rg "discover_all_notes_dirs" .claude/skills/apple/scripts/`
Expected: 0 matches

- [ ] **Step 6: Commit**

```bash
git add .claude/skills/apple/scripts/notes_lib.py
git commit -m "fix: delete discover_all_notes_dirs and sync_to_apple from notes_lib"
```

---

## Task 6: Update MCP tools and API route

**Files:**
- Modify: `.claude/skills/apple/scripts/mcp/tools_notes.py` (line 282)
- Modify: `.claude/skills/apple/augur/api/notes/route.ts` (lines 15-23)

- [ ] **Step 1: Update tools_notes.py**

In `note_create_local_tool()` (line 282), replace `sync_to_apple: bool = False` parameter with `sync_target: str = ""`. Update the call to `create_note()` accordingly — if `sync_target` is provided, write it to frontmatter.

- [ ] **Step 2: Update route.ts NoteEntry type**

In `.claude/skills/apple/augur/api/notes/route.ts` (line 22), change:

```typescript
// Old:
sync_to_apple: boolean;

// New:
sync_target: string;
```

Update `loadAppleNotes()` to set `sync_target: ""` instead of `sync_to_apple: false`.

- [ ] **Step 3: Verify no remaining references in code**

Run: `rg "sync_to_apple" .claude/skills/apple/`
Expected: 0 matches (only comments/docs if any)

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/apple/scripts/mcp/tools_notes.py .claude/skills/apple/augur/api/notes/route.ts
git commit -m "fix: replace sync_to_apple with sync_target in MCP tools and API route"
```

---

## Task 7: Migrate vault frontmatter

**Files:**
- Modify: Multiple vault `.md` files (~5-10)

- [ ] **Step 1: Find all files with sync_to_apple in vault**

Run: `rg -l "sync_to_apple" get_vault_dir()/ --glob "*.md" --glob "*.yaml"`

- [ ] **Step 2: For each file, update frontmatter**

For files with `sync_to_apple: true` + `sync_target: notes`:
- Remove the `sync_to_apple: true` line

For files with `sync_to_apple: true` but NO `sync_target`:
- Replace `sync_to_apple: true` with `sync_target: notes`

For files with `sync_to_apple: false`:
- Remove the `sync_to_apple: false` line entirely

For template files (`_templates/*.md`):
- Remove `sync_to_apple` field entirely (templates don't sync by default)

- [ ] **Step 3: Verify zero remaining references**

Run: `rg "sync_to_apple" get_vault_dir()/`
Expected: 0 matches (except possibly `_index.cache.yaml` which regenerates)

- [ ] **Step 4: Test full sync cycle**

Run: `python3 .claude/skills/apple/scripts/sync_discover.py`
Expected: Shows all syncable files with correct targets

Run: `python3 .claude/skills/apple/scripts/note_sync.py --all`
Expected: Syncs all notes-target files successfully

- [ ] **Step 5: Commit vault changes**

```bash
cd get_vault_dir() && git add -A && git commit -m "fix: migrate sync_to_apple to sync_target across vault"
```

- [ ] **Step 6: Commit project changes**

```bash
cd ~/Projects/Augur && git add -A && git commit -m "feat: vault discovery + unified sync — complete migration"
```

---

## Task 8: Verify source_sync.py compatibility

**Files:**
- Modify: `.claude/skills/apple/scripts/sync/source_sync.py` (line 94) — if needed

- [ ] **Step 1: Read source_sync.py and verify**

Read line 94 — confirm it already writes `sync_target: "notes"` in frontmatter for generated `.md` files. If it does, no changes needed.

- [ ] **Step 2: Verify quick notes are discoverable**

Run: `python3 .claude/skills/apple/scripts/sync_discover.py --target notes`
Expected: Quick notes `.md` files (if any exist in `apple/notes-sync/`) appear in results

- [ ] **Step 3: Commit if changes needed**

Only if `source_sync.py` needed modification:
```bash
git add .claude/skills/apple/scripts/sync/source_sync.py
git commit -m "fix: ensure source_sync.py writes sync_target for quick notes"
```

---

## Summary

| Task | What | Files |
|------|------|-------|
| 1 | Create scanner + tests (TDD) | `sync_discover.py`, `test_sync_discover.py` |
| 2 | Rewire note_sync.py | `note_sync.py` |
| 3 | Rewire auto_sync.py (reminders) | `auto_sync.py` |
| 4 | Rewire auto_notes_sync.py | `auto_notes_sync.py` |
| 5 | Delete discover_all_notes_dirs() | `notes_lib.py` |
| 6 | Update MCP tools + API route | `tools_notes.py`, `route.ts` |
| 7 | Migrate vault frontmatter | ~5-10 vault `.md` files |
| 8 | Verify source_sync.py compat | `source_sync.py` (if needed) |

**Dependencies**: Task 1 must complete first. Tasks 2-4 depend on Task 1 but are independent of each other. Task 5 depends on 2-4. Task 6 is independent. Task 7 depends on 5-6. Task 8 is independent verification.
