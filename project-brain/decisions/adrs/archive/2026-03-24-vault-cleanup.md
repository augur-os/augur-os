# Vault Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce vault from ~3,370 to ~1,100 content files by removing dead references, ephemeral data, runtime state, duplicates, and regenerable caches across 6 phases.

**Architecture:** Direct file operations on the vault at `Au-vault/` (resolved via `get_vault_dir()`). Each phase is a separate git commit for rollback safety. Two Python helper scripts handle memory dedup (Phase 5) and memory date-based pruning (Phase 6). MCP verification after each phase.

**Tech Stack:** Bash (file ops), Python 3.11+ (memory scripts), MCP tools (verification)

**Spec:** `docs/superpowers/specs/2026-03-24-vault-cleanup-design.md`

---

## Shared Context

```bash
# All tasks use this variable
VAULT="~/Projects/Au-vault"
```

MCP verification commands (run after each phase commit):
```bash
# In the Augur project root
python3 -c "
from src.mcp.augur_mcp.tools.internal.vault_status import vault_status_impl
import json, asyncio
result = asyncio.run(vault_status_impl())
print(json.dumps(result, indent=2, default=str))
"
```

Also verify via MCP tool calls: `vault-status`, `get-attention-items`, `get-attention-summary`, `insights-pending`, `get-daemon-notifications`, `browse-index category=vault`.

---

### Task 1: Phase 1 — System Artifacts (zero risk)

**Files:**
- Delete: `$VAULT/**/.DS_Store` (~51 files)
- Delete: `$VAULT/**/_index.cache.yaml` (~8 files)
- Delete: `$VAULT/**/*.yaml` where `_seeded: true` AND ≤5 lines (~3 files)
- Modify: `$VAULT/.gitignore` — add `.DS_Store` pattern to prevent re-accumulation

- [ ] **Step 1: Dry-run — list all .DS_Store files**

```bash
VAULT="~/Projects/Au-vault"
find "$VAULT" -name '.DS_Store' -not -path '*/.git/*' | wc -l
```
Expected: ~50-55

- [ ] **Step 2: Delete .DS_Store files**

```bash
find "$VAULT" -name '.DS_Store' -not -path '*/.git/*' -delete
```

- [ ] **Step 3: Add .DS_Store to vault .gitignore**

```bash
echo ".DS_Store" >> "$VAULT/.gitignore"
```

- [ ] **Step 4: Dry-run — list all _index.cache.yaml files**

```bash
find "$VAULT" -name '_index.cache.yaml' -not -path '*/.git/*'
```
Expected: ~8 files, all containing empty/minimal cache data

- [ ] **Step 5: Delete _index.cache.yaml files**

```bash
find "$VAULT" -name '_index.cache.yaml' -not -path '*/.git/*' -delete
```

- [ ] **Step 6: Dry-run — list seeded stubs**

```bash
grep -rl '_seeded: true' "$VAULT" --include='*.yaml' 2>/dev/null | while IFS= read -r f; do
  lines=$(wc -l < "$f")
  [ "$lines" -le 5 ] && echo "DELETE: $f ($lines lines)"
done
```
Expected: ~3 files (scraper install-requests.yaml, jobs.yaml, scraped-content.yaml)

- [ ] **Step 7: Delete seeded stubs**

```bash
grep -rl '_seeded: true' "$VAULT" --include='*.yaml' 2>/dev/null | while IFS= read -r f; do
  lines=$(wc -l < "$f")
  [ "$lines" -le 5 ] && rm "$f"
done
```

- [ ] **Step 8: Verify count**

```bash
find "$VAULT" -type f -not -path '*/.git/*' | wc -l
```
Expected: ~3,305-3,315 (down ~60)

- [ ] **Step 9: Commit**

```bash
cd "$VAULT"
git add -A
git commit -m "vault-cleanup phase 1: remove .DS_Store, cache files, seeded stubs (~62 files)"
```

---

### Task 2: Phase 2 — Dead References (zero risk)

All expiry files in channels/reviews and attention root reference paths that no longer exist. The channels/reviews/pending/ files reference a broken double-path (`/Vault/Augur/career/career/`). All are system-generated review nags with no live consumer.

**Files:**
- Delete: `$VAULT/channels/reviews/` — all expiry files at root (~164) AND in pending/ (~317), plus orphaned meta-files
- Delete: `$VAULT/attention/expiry-*.md` at root level (~164 files)
- Preserve: `$VAULT/channels/config.yaml`
- Preserve: `$VAULT/channels/reviews/` directory structure (recreate empty)

- [ ] **Step 1: Verify channels root files reference dead path**

```bash
VAULT="~/Projects/Au-vault"
head -15 "$VAULT/channels/reviews/expiry-02cec11f.md" | grep 'augur-data'
```
Expected: path containing `/Projects/augur-data/vertical-work/` (dead path)

- [ ] **Step 2: Verify channels pending files also reference broken path**

```bash
head -15 "$VAULT/channels/reviews/pending/expiry-01862096.md" | grep 'career/career/'
```
Expected: doubled path `/Vault/Augur/career/career/` (broken)

- [ ] **Step 3: Count all channels review files**

```bash
echo "root expiry: $(ls "$VAULT"/channels/reviews/expiry-*.md 2>/dev/null | wc -l)"
echo "pending: $(find "$VAULT/channels/reviews/pending" -type f 2>/dev/null | wc -l)"
echo "history: $(find "$VAULT/channels/reviews/history" -type f 2>/dev/null | wc -l)"
echo "other: $(find "$VAULT/channels/reviews" -maxdepth 1 -type f -not -name 'expiry-*' 2>/dev/null | wc -l)"
```
Expected: ~164 root + ~317 pending + ~1 history + ~1 other = ~483 total

- [ ] **Step 4: Delete all channels review content (preserve dir structure)**

```bash
rm -rf "$VAULT/channels/reviews/"
mkdir -p "$VAULT/channels/reviews"
```

- [ ] **Step 5: Count attention root expiry files**

```bash
ls "$VAULT/attention/expiry-"*.md 2>/dev/null | wc -l
```
Expected: ~160-170

- [ ] **Step 6: Verify attention root files reference dead path**

```bash
head -15 $(ls "$VAULT/attention/expiry-"*.md 2>/dev/null | head -1)
```
Expected: references to old paths

- [ ] **Step 7: Delete attention root expiry files**

```bash
rm "$VAULT"/attention/expiry-*.md 2>/dev/null
```

- [ ] **Step 8: Verify surviving files**

```bash
# channels/ should still have config.yaml and empty reviews/
ls "$VAULT/channels/"
# attention/ should still have pending/ and sync-map.yaml
ls "$VAULT/attention/"
```

- [ ] **Step 9: Verify count**

```bash
find "$VAULT" -type f -not -path '*/.git/*' | wc -l
```
Expected: ~2,640-2,670 (down ~645-650)

- [ ] **Step 10: Commit**

```bash
cd "$VAULT"
git add -A
git commit -m "vault-cleanup phase 2: remove dead channel/attention references (~650 files)

All channels/reviews files referenced dead augur-data or broken career/career paths.
Attention root expiry files referenced same dead paths."
```

---

### Task 3: Phase 3 — Ephemeral Operational Data (low risk)

System-generated items. Attention items are actively consumed by `get-attention-items` — dashboard will be temporarily empty until scanner re-populates.

**Files:**
- Delete: `$VAULT/attention/pending/expiry-*.md` (~316 files — consumed by `get-attention-items`, regenerable)
- Delete: `$VAULT/daemon/notifications/history/*.md` (~100 files)
- Delete: `$VAULT/daemon/insights/*.md` except README (~30 files — MCP reads `insights.yaml`, not these)

**Dashboard impact:** Attention page temporarily empty until scanner re-populates.

- [ ] **Step 1: Count attention pending files**

```bash
VAULT="~/Projects/Au-vault"
ls "$VAULT/attention/pending/expiry-"*.md 2>/dev/null | wc -l
```
Expected: ~315-320

- [ ] **Step 2: Delete attention pending expiry files**

```bash
rm "$VAULT"/attention/pending/expiry-*.md
```

- [ ] **Step 3: Count daemon notification history**

```bash
find "$VAULT/daemon/notifications/history" -name '*.md' -type f | wc -l
```
Expected: ~100

- [ ] **Step 4: Delete daemon notification history**

```bash
find "$VAULT/daemon/notifications/history" -name '*.md' -type f -delete
```

- [ ] **Step 5: Count daemon insight artifacts (not insights.yaml, not README)**

```bash
find "$VAULT/daemon/insights" -name '*.md' -not -name 'README*' -type f | wc -l
```
Expected: ~30

- [ ] **Step 6: Delete daemon insight .md artifacts**

```bash
find "$VAULT/daemon/insights" -name '*.md' -not -name 'README*' -type f -delete
```

- [ ] **Step 7: Verify daemon core files intact**

```bash
# These should still exist:
ls "$VAULT/daemon/notifications/pending.yaml" "$VAULT/daemon/notifications/preferences.yaml" "$VAULT/daemon/notifications/README.md"
```

- [ ] **Step 8: MCP verification**

Call MCP tools:
- `get-attention-items` — should return empty list (OK, scanner will re-populate)
- `get-attention-summary` — should return zero counts
- `insights-pending` — should still work (reads insights.yaml, not deleted .md files)
- `get-daemon-notifications` — should return empty history

- [ ] **Step 9: Verify count**

```bash
find "$VAULT" -type f -not -path '*/.git/*' | wc -l
```
Expected: ~2,190-2,220 (down ~446)

- [ ] **Step 10: Commit**

```bash
cd "$VAULT"
git add -A
git commit -m "vault-cleanup phase 3: clear ephemeral attention/daemon data (~446 files)

Attention dashboard temporarily empty until scanner re-populates.
Daemon notification history cleared; new notifications unaffected."
```

---

### Task 4: Phase 4 — Runtime State (low risk)

**Files:**
- Delete: `$VAULT/apple/**/*_sync.yaml` (~17 files — regenerated on next Apple sync)
- Delete: `$VAULT/validator/webapp-testing/` test artifacts (~15 files in subdirs)

- [ ] **Step 1: List apple sync files**

```bash
VAULT="~/Projects/Au-vault"
find "$VAULT/apple" -name '*_sync.yaml' -type f
```
Expected: ~17 files across reminders/ and notes-sync/

- [ ] **Step 2: Delete apple sync files**

```bash
find "$VAULT/apple" -name '*_sync.yaml' -type f -delete
```

- [ ] **Step 3: List validator test captures**

```bash
find "$VAULT/validator/webapp-testing" -type f -not -name 'README*'
```
Expected: ~15 files in captures/ and ui_qa_runs/ subdirs + 2 root-level validation files

- [ ] **Step 4: Delete validator test captures**

```bash
find "$VAULT/validator/webapp-testing" -type f -not -name 'README*' -delete
```

- [ ] **Step 5: Verify apple content intact**

```bash
# User notes and reminders should still exist
ls "$VAULT/apple/notes/"
ls "$VAULT/apple/reminders/"
```

- [ ] **Step 6: Verify count**

```bash
find "$VAULT" -type f -not -path '*/.git/*' | wc -l
```
Expected: ~2,155-2,190 (down ~32)

- [ ] **Step 7: Commit**

```bash
cd "$VAULT"
git add -A
git commit -m "vault-cleanup phase 4: remove runtime state from vault (~32 files)

Apple _sync.yaml and validator test captures belong in runtime dir, not vault."
```

---

### Task 5: Phase 5 — Memory Dedup + Career Stale Data (medium risk)

**Files:**
- Create: `~/Projects/Augur/scripts/vault_cleanup_phase5_memory.py`
- Delete: ~67 duplicate `$VAULT/memory/entries/` files that overlap with `system/`
- Archive: ~83 `$VAULT/memory/entries/` Feb files with no system/ counterpart → `$VAULT/memory/archive/`
- Archive: ~30 `$VAULT/memory/entries/` files with no `created:` date → `$VAULT/memory/archive/` (conservative — preserve rather than delete)
- Delete: `$VAULT/career/job-analyzer/jobs/active/*` (~174 scraped job files)
- Delete: `$VAULT/career/job-analyzer/companies/*` (~54 stale company profiles)

- [ ] **Step 1: Write memory dedup script**

Create `~/Projects/Augur/scripts/vault_cleanup_phase5_memory.py`:

```python
#!/usr/bin/env python3
"""Phase 5: Deduplicate memory entries/ vs system/ and archive stale entries."""
from __future__ import annotations

import shutil
from pathlib import Path

VAULT = Path("~/Projects/Au-vault")
ENTRIES = VAULT / "memory" / "entries"
SYSTEM = VAULT / "memory" / "system"
ARCHIVE = VAULT / "memory" / "archive"


def strip_client_prefix(name: str) -> str:
    """Remove client prefix: 'claude-code_feedback_foo.md' -> 'feedback_foo.md'."""
    parts = name.split("_", 1)
    if len(parts) == 2 and parts[0] in ("claude-code", "gemini", "codex"):
        return parts[1]
    return name


def get_created_month(path: Path) -> str | None:
    """Extract YYYY-MM from frontmatter 'created:' field."""
    for line in path.read_text(errors="ignore").splitlines()[:15]:
        if line.startswith("created:"):
            val = line.split(":", 1)[1].strip().strip("'\"")
            return val[:7]  # YYYY-MM
    return None


def main() -> None:
    if not ENTRIES.exists() or not SYSTEM.exists():
        print("ERROR: memory/entries or memory/system not found")
        return

    ARCHIVE.mkdir(exist_ok=True)

    system_names = {f.name for f in SYSTEM.iterdir() if f.is_file() and f.suffix == ".md"}
    dedup_count = 0
    archive_count = 0
    no_date_count = 0

    for entry_file in sorted(ENTRIES.iterdir()):
        if not entry_file.is_file() or entry_file.suffix != ".md":
            continue

        canonical = strip_client_prefix(entry_file.name)

        if canonical in system_names:
            # Duplicate — system/ has the canonical version
            print(f"DEDUP: {entry_file.name} (system/ has {canonical})")
            entry_file.unlink()
            dedup_count += 1
        else:
            month = get_created_month(entry_file)
            if month is None:
                # No date — archive conservatively
                print(f"ARCHIVE (no date): {entry_file.name}")
                shutil.move(str(entry_file), str(ARCHIVE / entry_file.name))
                no_date_count += 1
            elif month <= "2026-02":
                print(f"ARCHIVE: {entry_file.name} (created {month})")
                shutil.move(str(entry_file), str(ARCHIVE / entry_file.name))
                archive_count += 1

    print(f"\nDone: {dedup_count} deduplicated, {archive_count} archived (dated), {no_date_count} archived (no date)")
    print(f"Remaining entries: {sum(1 for f in ENTRIES.iterdir() if f.is_file())}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Dry-run memory dedup (preview only)**

```bash
cd ~/Projects/Augur
python3 -c "
from pathlib import Path
VAULT = Path('~/Projects/Au-vault')
entries = VAULT / 'memory' / 'entries'
system = VAULT / 'memory' / 'system'
system_names = {f.name for f in system.iterdir() if f.suffix == '.md'}

def strip_prefix(n):
    parts = n.split('_', 1)
    return parts[1] if len(parts) == 2 and parts[0] in ('claude-code','gemini','codex') else n

dupes = [f for f in entries.iterdir() if f.suffix == '.md' and strip_prefix(f.name) in system_names]
print(f'Would dedup: {len(dupes)} files')
for d in dupes[:5]: print(f'  {d.name}')
if len(dupes) > 5: print(f'  ... and {len(dupes)-5} more')
"
```
Expected: ~67 files

- [ ] **Step 3: Run memory dedup script**

```bash
python3 scripts/vault_cleanup_phase5_memory.py
```
Expected output: ~67 deduplicated, ~83 archived (dated), ~30 archived (no date)

- [ ] **Step 4: Verify memory archive created**

```bash
ls ~/Projects/Au-vault/memory/archive/ | wc -l
ls ~/Projects/Au-vault/memory/entries/ | wc -l
```
Expected: archive ~113, entries reduced to ~59

- [ ] **Step 5: Delete career job-analyzer/jobs/active/**

```bash
VAULT="~/Projects/Au-vault"
echo "Deleting $(find "$VAULT/career/job-analyzer/jobs/active" -type f | wc -l) job files"
rm -rf "$VAULT/career/job-analyzer/jobs/active/"
mkdir -p "$VAULT/career/job-analyzer/jobs/active"
```
Expected: ~174 files deleted

- [ ] **Step 6: Delete career job-analyzer/companies/**

```bash
echo "Deleting $(find "$VAULT/career/job-analyzer/companies" -type f | wc -l) company files"
rm -rf "$VAULT/career/job-analyzer/companies/"
mkdir -p "$VAULT/career/job-analyzer/companies"
```
Expected: ~54 files deleted

- [ ] **Step 7: Verify career structure intact**

```bash
# Seed files and structure should remain
ls "$VAULT/career/job-analyzer/jobs/"
ls "$VAULT/career/job-analyzer/"
ls "$VAULT/career/notes/" | head -5  # user notes untouched
```

- [ ] **Step 8: Verify count**

```bash
find "$VAULT" -type f -not -path '*/.git/*' | wc -l
```
Expected: ~1,830-1,870. Note: archived files still count (~113 moved to archive/, not deleted).

- [ ] **Step 9: MCP verification**

Call MCP tools:
- `browse-index category=vault` — should still resolve
- `memory-search` with a test query — should return results from system/
- `vault-status` — confirm no broken refs

- [ ] **Step 10: Commit**

```bash
cd "$VAULT"
git add -A
git commit -m "vault-cleanup phase 5: memory dedup + career stale data

- Removed 67 duplicate entries/ where system/ has canonical copy
- Archived ~113 stale/dateless entries/ to memory/archive/
- Cleared ~174 scraped job listings and ~54 stale company profiles"
```

- [ ] **Step 11: Commit helper script in Augur repo**

```bash
cd ~/Projects/Augur
git add scripts/vault_cleanup_phase5_memory.py
git commit -m "scripts: add vault cleanup phase 5 memory dedup helper"
```

---

### Task 6: Phase 6 — Deep Pruning (medium-high risk)

**Note:** `career/notes/` is excluded — contains user-created technical knowledge (hardware engineering notes), not ephemeral data. AI demo step files are all deleted (88 files) — the 5 preset files in playbooks/ root are kept.

**Files:**
- Create: `~/Projects/Augur/scripts/vault_cleanup_phase6_memory.py`
- Delete: ~150 `$VAULT/memory/system/` Feb entries (>30 days)
- Delete: `$VAULT/memory/archive/` (~113 files — already reviewed in Phase 5, safe to purge)
- Delete: `$VAULT/knowledge/rag/entries/*` (~169 regenerable files)
- Delete: `$VAULT/scraper/entries/*.md` (~11 stale scrape outputs)
- Delete: `$VAULT/ai/demo/playbooks/steps/*` (88 demo step files)
- Delete: empty dirs

- [ ] **Step 1: Write memory date-prune script**

Create `~/Projects/Augur/scripts/vault_cleanup_phase6_memory.py`:

```python
#!/usr/bin/env python3
"""Phase 6: Remove memory/system/ entries older than 30 days (created in Feb or earlier)."""
from __future__ import annotations

from pathlib import Path

VAULT = Path("~/Projects/Au-vault")
SYSTEM = VAULT / "memory" / "system"
CUTOFF = "2026-02"  # Delete entries created in Feb 2026 or earlier


def get_created_month(path: Path) -> str | None:
    """Extract YYYY-MM from frontmatter 'created:' field."""
    for line in path.read_text(errors="ignore").splitlines()[:15]:
        if line.startswith("created:"):
            val = line.split(":", 1)[1].strip().strip("'\"")
            return val[:7]
    return None


def main() -> None:
    if not SYSTEM.exists():
        print("ERROR: memory/system not found")
        return

    deleted = 0
    kept = 0

    for f in sorted(SYSTEM.iterdir()):
        if not f.is_file() or f.suffix != ".md":
            continue

        month = get_created_month(f)
        if month and month <= CUTOFF:
            print(f"DELETE: {f.name} (created {month})")
            f.unlink()
            deleted += 1
        else:
            kept += 1

    print(f"\nDone: {deleted} deleted, {kept} kept")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Dry-run memory prune**

```bash
cd ~/Projects/Augur
python3 -c "
from pathlib import Path
SYSTEM = Path('~/Projects/Au-vault/memory/system')
count = 0
for f in SYSTEM.iterdir():
    if not f.is_file() or f.suffix != '.md': continue
    for line in f.read_text(errors='ignore').splitlines()[:15]:
        if line.startswith('created:'):
            month = line.split(':', 1)[1].strip().strip(\"'\\\"\")[:7]
            if month <= '2026-02': count += 1
            break
print(f'Would delete: {count} files from memory/system/')
"
```
Expected: ~150

- [ ] **Step 3: Run memory prune**

```bash
python3 scripts/vault_cleanup_phase6_memory.py
```

- [ ] **Step 4: Delete memory archive (already reviewed in Phase 5)**

```bash
VAULT="~/Projects/Au-vault"
echo "Deleting $(find "$VAULT/memory/archive" -type f | wc -l) archived entries"
rm -rf "$VAULT/memory/archive/"
```

- [ ] **Step 5: Delete knowledge RAG entries**

```bash
echo "Deleting $(find "$VAULT/knowledge/rag/entries" -type f | wc -l) RAG entries"
rm -rf "$VAULT/knowledge/rag/entries/"
mkdir -p "$VAULT/knowledge/rag/entries"
```
Expected: ~169 files. Regenerable via `/auto-rag-reindex`.

- [ ] **Step 6: Delete scraper stale entries**

```bash
echo "Deleting $(find "$VAULT/scraper/entries" -name '*.md' -type f 2>/dev/null | wc -l) scraper entries"
find "$VAULT/scraper/entries" -name '*.md' -type f -delete 2>/dev/null
```

- [ ] **Step 7: Delete AI demo step files (keep 5 presets)**

```bash
echo "Deleting $(find "$VAULT/ai/demo/playbooks/steps" -type f | wc -l) demo steps"
rm -rf "$VAULT/ai/demo/playbooks/steps/"
mkdir -p "$VAULT/ai/demo/playbooks/steps"
# Verify presets intact:
ls "$VAULT/ai/demo/playbooks/"
```
Expected: 5 preset-*.md files + empty steps/

- [ ] **Step 8: Clean empty dirs**

```bash
rmdir "$VAULT/daemon/calendar" 2>/dev/null
find "$VAULT" -type d -empty -not -path '*/.git/*' -delete 2>/dev/null
```

- [ ] **Step 9: Final count**

```bash
find "$VAULT" -type f -not -path '*/.git/*' | wc -l
```
Expected: ~1,100-1,200

- [ ] **Step 10: MCP verification — full suite**

Call all MCP verification tools:
- `vault-status` — no broken refs
- `browse-index category=vault` — indexes still resolve
- `get-attention-items` — responds (empty OK)
- `get-attention-summary` — responds
- `insights-pending` — responds
- `get-daemon-notifications` — responds
- `memory-search` with test query — returns results from surviving system/ entries (March entries)
- `list-skill-vault-notes` for career, books, lifestyle — notes intact

- [ ] **Step 11: Commit**

```bash
cd "$VAULT"
git add -A
git commit -m "vault-cleanup phase 6: deep pruning — memory, RAG, scraper, AI demos

- Removed ~150 stale Feb memory/system entries
- Purged ~113 archived entries from Phase 5
- Cleared 169 regenerable RAG entries (run /auto-rag-reindex to rebuild)
- Deleted stale scraper entries and 88 AI demo step files
- Final count: ~1,100-1,200 files (down from ~3,370)"
```

- [ ] **Step 12: Commit helper scripts in Augur repo**

```bash
cd ~/Projects/Augur
git add scripts/vault_cleanup_phase6_memory.py
git commit -m "scripts: add vault cleanup phase 6 memory prune helper"
```

---

### Task 7: Post-Cleanup — Regenerate RAG + Verify Dashboard

**Files:**
- No new files — verification and regeneration only

- [ ] **Step 1: Regenerate RAG indexes**

Run `/auto-rag-reindex` to rebuild knowledge indexes from surviving vault content.

- [ ] **Step 2: Verify dashboard pages load**

Check these dashboard pages in browser:
- Attention hub (`/life/attention`) — should show empty state or re-populated items
- Career hub (`/career`) — should load with empty job analyzer
- Knowledge hub (`/brain/knowledge`) — should load after RAG reindex
- Life/Apple (`/life/apple`) — notes should display, reminders should still sync
- Daemon page — notifications should show empty history

- [ ] **Step 3: Final inventory**

```bash
VAULT="~/Projects/Au-vault"
echo "=== Final file count ==="
find "$VAULT" -type f -not -path '*/.git/*' | wc -l

echo ""
echo "=== Per-directory breakdown ==="
for d in "$VAULT"/*/; do
  echo "$(find "$d" -type f -not -path '*/.git/*' | wc -l | tr -d ' ') $(basename "$d")"
done | sort -rn
```

- [ ] **Step 4: Clean up helper scripts**

```bash
cd ~/Projects/Augur
rm scripts/vault_cleanup_phase5_memory.py scripts/vault_cleanup_phase6_memory.py
git add -A
git commit -m "scripts: remove one-time vault cleanup helpers"
```
