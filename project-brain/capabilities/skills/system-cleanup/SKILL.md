---
name: system-cleanup
x-augur-type: skill
x-augur-tags:
- macos
- disk
- cleanup
- maintenance
description: Use when freeing disk space on macOS — scan disk-waste categories
  (browser/app caches, system logs, Trash, installer leftovers, Xcode data,
  AI-tool caches, dev artifacts, large files), report sizes and system pressure,
  and reversibly move confirmed items to the OS Trash via /cleanup.
x-augur-group: life
x-augur-release: mvp
x-augur-license: MIT
---

# system-cleanup

macOS disk maintenance. Scans disk-waste categories with sizes, then — only
after explicit per-category confirmation — moves approved items to the OS
Trash. Everything is CLI-invoked Python (no MCP tools, no dashboard pages);
`/cleanup` orchestrates the full flow.

## Categories

Eight path-based categories — `browser-caches`, `app-caches`, `system-logs`,
`trash` (report-only), `downloads-installers` (`*.dmg`/`*.pkg`/`*.zip`),
`xcode-derived`, `gemini-antigravity`, `dev-caches` — plus two computed scans:
`dev-artifacts` (`node_modules`, `.venv`, `dist`, `.next`, … under common
project roots) and `large-files` (>100 MB in `~/Downloads` and `~/Desktop`).
The category config lives in `scripts/cleanup_common.py`.

## Scripts

Run with `uv run python <script> --help` first; all are CLI-only.

| Script | Purpose |
|--------|---------|
| `scripts/cleanup_stats.py` | System pressure (CPU/memory/disk/uptime) + estimated size per category. Read-only. |
| `scripts/cleanup_scan.py` | Enumerate cleanup candidates in one category (or `all`) with sizes. Read-only. |
| `scripts/cleanup_execute.py` | Move scanned items to the OS Trash. Dry run unless `--confirm`. |

## Safety contract

- **Reversible by design** — execution uses `send2trash` (OS Trash) only;
  there is no `rm -rf`/`rmtree`/`unlink` path and no hard-delete mode.
  Trashed items are recoverable from the Trash until the user empties it.
- **Confirmation-gated** — `cleanup_execute.py` without `--confirm` is a dry
  run that touches nothing; `/cleanup` requires explicit per-category (or
  per-item) user approval before passing `--confirm`.
- **Item-scoped** — execution only targets items the category scan itself
  enumerated; `--items` paths outside the scan result are rejected, and a
  category root (e.g. `~/Library/Caches` itself) is never removed.
- **Protected paths** — the Augur repo, the configured vault and documents
  stores (`src.config.paths`), `~/Documents`, the home directory itself, and
  anything outside the user's home are never trashed (skipped and reported).
- **`trash` is report-only** — emptying the OS Trash is not reversible, so
  the executor refuses that category even with `--confirm`; point the user at
  Finder's Empty Trash.
- **Scans are side-effect-free** — `cleanup_stats.py` and `cleanup_scan.py`
  never write or delete anything.

## Workflow

The cleanup process follows a scan-confirm-execute procedure:

- Step 1: Run `cleanup_stats.py` to get a disk-pressure overview (CPU/memory/disk/uptime) and estimated category sizes without touching anything.
- Step 2: Run `cleanup_scan.py --category all` (or a specific category) to enumerate exact candidates with individual sizes.
- Step 3: Present findings to the user grouped by category; request explicit per-category or per-item confirmation.
- Step 4: For each confirmed category, run `cleanup_execute.py --confirm --items <path>...` to move approved items to the OS Trash.
- Step 5: Report sizes recovered per category and confirm nothing outside the user's home was touched.

Never run `cleanup_execute.py --confirm` without explicit user approval for each category.

## Checklist

- [ ] `cleanup_stats.py` run first (read-only overview)
- [ ] `cleanup_scan.py` run per category to confirm candidate list
- [ ] User confirmed each category before execution
- [ ] `cleanup_execute.py --confirm` called only for approved items
- [ ] No item outside `~/` was trashed
- [ ] `trash` category was reported only, not executed

## Examples

```bash
# Step 1 — disk-pressure overview (read-only, safe to run any time)
uv run python scripts/cleanup_stats.py

# Step 2 — enumerate what would be cleaned in a category
uv run python scripts/cleanup_scan.py --category app-caches

# Step 3 — enumerate ALL categories
uv run python scripts/cleanup_scan.py --category all

# Step 4 — move confirmed items to OS Trash (dry-run without --confirm)
uv run python scripts/cleanup_execute.py --category app-caches
uv run python scripts/cleanup_execute.py --category app-caches --confirm
```

## Constraints

- macOS-targeted (category paths are macOS conventions); stats degrade
  gracefully on Linux.
- Not a substitute for `scripts/disk-cleanup/*.sh` (the standalone interactive
  POSIX helpers covering APFS snapshots and sudo-level cleanup) — this skill
  owns only the reversible, agent-orchestrated path.

## Provenance

Selective port of the staged r3 `system-cleanup` draft. The staged executor
hard-deleted (`shutil.rmtree`) entire category roots and ignored its `items`
parameter; both were rewritten to the trash-safe, item-scoped semantics above.
Dead hub-era machinery (`tab_scorer.py`, dashboard page/block declarations,
MCP registration, permission probing) was excised at adoption; see CHANGELOG.
