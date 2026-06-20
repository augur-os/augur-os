---
description: Detect notes markdown files missing from skill index caches and rebuild the cache
context: current
agent: general-purpose
visibility: ops
---

# /auto-index-notes

Scans skill `notes/` directories in external vault data for `.md` files that
are not recorded in the local `_index.cache.yaml`, then rebuilds the cache
using `notes_lib.write_index_cache` (with a minimal fallback if unavailable).

## What it does

- **Scan**: Compares `.md` files on disk against `_index.cache.yaml` entries.
  Returns one issue per notes directory that has unindexed files.
- **Fix**: Calls `notes_lib.write_index_cache()` via subprocess (to avoid
  import-path issues since `notes_lib` lives in the `apple` skill). Falls back
  to an inline minimal cache builder if `notes_lib.py` is not present. Commits
  the updated cache file per skill.

## Usage

Run automatically by the daemon at `tier: 1` (`trigger: nightly`) in the
`knowledge-enrichment` loop. Can also be invoked manually via `/routines`.

## Protocol

Implements the `OpsCommand` protocol (`scan-fix`). Dry run is supported —
pass `dry_run=True` to scan without writing or committing any cache files.

## Implementation

`skills/ai/scripts/ops/index_notes.py`
