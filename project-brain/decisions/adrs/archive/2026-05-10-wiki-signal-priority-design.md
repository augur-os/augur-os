---
title: Wiki Signal Priority & Batched Update Design
date: 2026-05-10
status: draft
owner: ingest skill
related:
  - shared-vault/skills/ingest/scripts/wiki_scanner.py
  - shared-vault/skills/ingest/scripts/mcp/wiki_tools.py
  - config/system/wiki_signals.yaml (new)
---

# Wiki Signal Priority & Batched Update Design

## Problem

The wiki scanner today (`shared-vault/skills/ingest/scripts/wiki_scanner.py`) pulls from nine source surfaces — vault, documents, skills, repo_docs, project_deltas, git_history, runtime_memory, logs, ask_outcomes, adr_targets — and treats them all equally. Sources are deduped and emitted as one flat list. The `wiki-update` MCP tool is poll-driven via a `runtime/wiki/needs-update.flag` file that nothing currently writes automatically.

Three concrete consequences:

1. **High-signal events are invisible as events.** A `/save` write is the same to the scanner as a noisy log file. The scanner only knows "this file exists"; it does not know "the user just deliberately put this here."
2. **Cross-client memory is not scanned as a category.** AI clients such as Claude Code, Codex, Gemini, Copilot, Cursor, and ChatGPT all keep useful local memory/session state, but the wiki has no neutral client-memory inventory that treats them as peers.
3. **There is no cadence.** The wiki has been stale for ~7 days at the time of writing because no routine triggers `wiki-update`. The user runs it manually or it does not run.

This design adds tiered signal priority, a config-driven client-memory adapter, episodic-memory support, and a single token-conscious daily routine that drives wiki updates automatically.

## Design summary

- **Tier-tagged scanner output.** Each source dict gains `tier` and `weight` fields. Defaults map from `source_surface`; per-file frontmatter `wiki_tier:` overrides.
- **Client-neutral memory adapter.** `_scan_client_memory` reads configured client roots from `wiki_signals.yaml`; Claude Code, Codex, Gemini, Copilot, ChatGPT, Cursor, and future clients are data entries, not special-case architecture.
- **Vault mtime promotion.** Files in the vault with `mtime` within a configurable window (default 30 min) are tagged `save_events` (critical) instead of `vault` (high). Catches `/save`, Obsidian, any editor — without a producer-side hook.
- **One token-conscious daily routine.** `wiki-batched-daily` runs once at 06:23 UTC, weight-sorts the combined batch, applies per-tier caps, and skips the extraction LLM call entirely if nothing changed since the last extraction.
- **Single config file.** `config/system/wiki_signals.yaml` holds client-memory roots, the mtime window, tier caps, and extraction limits. Code carries defaults; the file overrides.

## Tier taxonomy

| Tier | Cadence | Weight | Source surfaces |
|---|---|---|---|
| **Critical** | first in batch, dominates token allocation | 3.0 | `save_events` (mtime-promoted vault writes), `ask_outcomes`, `client_memory`, `episodic` |
| **High** | second priority | 2.0 | `vault`, configured `client_memory` entries with `tier: high` |
| **Medium** | third priority | 1.0 | `documents`, `skills`, `repo_docs`, `project_deltas`, `adr_targets` |
| **Low** | scanned but excluded from extraction | 0.4 | `git_history`, `runtime_memory` |
| **Noise** | dropped before extraction | 0.0 | `logs` (kill-switch in config) |

Tier-to-surface mapping is a single dict (`_TIER_BY_SURFACE`) in `wiki_scanner.py`. Frontmatter `wiki_tier:` on a source overrides the default for that file.

## Scanner changes (`wiki_scanner.py`)

### Priority tagging
Every dict the scanner emits gains `tier: str` and `weight: float`. The resolution order is:

1. Frontmatter `wiki_tier:` if present in the file (markdown frontmatter; reuse `parse_frontmatter`).
2. `_TIER_BY_SURFACE[source_surface]`.
3. Fallback `medium`.

Weight is a fixed lookup from tier (3.0 / 2.0 / 1.0 / 0.4 / 0.0).

### Vault mtime promotion
Inside `_scan_dir(..., source_surface="vault")`, after the existing classification, check `path.stat().st_mtime`. If within the configured window (default 30 min, override `wiki_signals.yaml: mtime_window_minutes`), emit the source with `source_surface="save_events"` and `tier="critical"` instead of vault/high.

Edge case: a file seen as `save_events` once will age back to `vault` on the next scan past the window. Prevents indefinite re-firing.

### Client-memory adapter

All return the standard source dict (`path`, `type`, `title`, `hub`, `format`, `source_surface`, `tier`, `weight`). All read paths from `wiki_signals.yaml`.

| Adapter | Source | source_surface | Default tier |
|---|---|---|---|
| `_scan_client_memory()` | configured AI-client local memory/session roots | `client_memory` | configured per client |
| `_scan_episodic()` | episodic-memory MCP, conversations newer than `last_episodic_ts` | `episodic` | critical |

The `client_memory.clients` map lets you add platforms without writing new Python.

## Consumer changes (`wiki_tools.py` — `wiki-update`)

### `--tier` filter parameter
Add optional `tier: str = ""` to the `wiki-update` MCP tool. When set, the consumer keeps only sources whose tier is at or above the requested level (a `medium` request includes critical+high+medium). Default `tier=""` means "everything except noise" — preserves current callers, since the only change is `noise` is now dropped by default.

### Weight-aware extraction batch
`prepare_extraction_batch()` already takes `limit`. Extend to accept an optional weight map; sort sources by `(weight, recency)` before truncating. Higher-weight sources survive limit truncation first.

### Skip-if-unchanged guard
Before invoking concept extraction, read `runtime/wiki/last-extraction.ts`. If no source in the filtered batch has `mtime > last_extraction_ts` (or its surface-specific freshness signal — episodic/codex use their own watermark files), skip extraction entirely and exit with `status: "no_change"`. This is the dominant token-saving lever.

### Per-tier batch caps
After tier filter and before extraction, cap each tier independently per `wiki_signals.yaml: tier_caps`:

```yaml
tier_caps:
  critical: 5
  high: 15
  medium: 30
  low: 50
  noise: 0
```

Caps apply per-run, not per-day.

## Configuration (`config/system/wiki_signals.yaml`, new)

```yaml
mtime_window_minutes: 30

tier_caps:
  critical: 5
  high: 15
  medium: 30
  low: 50

extraction_limit: 20         # passed to prepare_extraction_batch

include_logs: false          # noise tier kill-switch

client_memory:
  enabled: true
  clients:
    claude:
      enabled: true
      path: ~/.claude
      globs:
        - projects/*/memory/*.md
      tier: critical
    codex:
      enabled: true
      path: ~/.codex/sessions
      tier: critical
    gemini:
      enabled: true
      path: ~/.gemini/conversations
      tier: high
    copilot:
      enabled: true
      path: ~/Library/Application Support/GitHub Copilot/sessions
      tier: high
    chatgpt:
      enabled: true
      path: ~/Library/Application Support/ChatGPT/exports
      tier: high
    cursor:
      enabled: true
      path: ~/Library/Application Support/Cursor/conversations
      tier: high
```

Code ships sensible defaults; the file overrides for path layout differences and per-machine tuning.

## Routine schedule

**One routine, one slot:** `wiki-batched-daily`, daily at `06:23 UTC`. Routine body calls `wiki-update` with `tier=""` (default — everything except noise) and `limit=20`.

The routine spends tokens only when something changed (skip-if-unchanged guard) and within bounded caps when it does run.

This collapses the original five-routine plan to one. The fast-lane scenario (a `wiki-critical-fast` running every few hours) is **deferred** — adding it later is a yaml + cron edit, not a code change. Token economy is the priority for v1.

Routine slot budget: 1 of 15 used.

## Token-saving levers (all applied in v1)

1. **One routine, one extraction call/day max.** Daily cadence over per-tier cron.
2. **Skip extraction if no mtime delta.** Dominant lever — most days are quiet.
3. **`extraction_limit: 20`** instead of the existing default 50. Smaller LLM calls.
4. **Low and noise tiers excluded from extraction.** Scanner still sees them (so `wiki-status` stays accurate); extraction never touches them.
5. **Weight-sorted truncation.** When the limit truncates, high-value sources survive.

Expected daily extraction cost: ~1 call on quiet days (skipped via guard), ~1 call with ≤20 sources on active days. Down from ~52 calls/day in the multi-routine variant.

## Telemetry (surfaced via `wiki-status`)

Four new fields:

| Field | Source |
|---|---|
| `signals_seen_by_tier` | counts from the scan dict, grouped by tier |
| `last_extraction_ts` | `runtime/wiki/last-extraction.ts` |
| `tokens_spent_last_run` | written by `wiki-update` after extraction |
| `dropped_low_noise_count` | count of sources filtered out per run |

These let `wiki-status` report a single line like:

> *3 critical signals today, last extracted 4 h ago, 3.2k tokens, 12 low/noise dropped.*

## Rollout

Three independently shippable commits:

1. **Scanner changes.** Tier table, frontmatter override, mtime promotion, the client-memory adapter, episodic-memory support, and the `wiki_signals.yaml` reader. Output is richer; behavior unchanged for existing callers because no consumer reads `tier` yet.
2. **Consumer changes.** `wiki-update` gains the tier filter, weight-aware sorting, skip-if-unchanged guard, and per-tier caps. Manual `wiki-update` calls already benefit from priority and token savings.
3. **Routine + telemetry.** `wiki-batched-daily` cron entry; `wiki-status` surfaces the four new fields.

Each commit is shippable on its own. Bisecting is straightforward.

## Explicitly out of scope

- **No event bus / `signals.jsonl`.** Mtime detection covers the hot path; an event bus would require producer-side changes everywhere `/save`, `/ask`, `/chat` write.
- **No per-skill signal config.** One central `config/system/wiki_signals.yaml`. Plugins add allowlist entries, not new yaml files.
- **No adaptive watermark or scoring model.** Fixed tier table; explicit beats clever.
- **No `/save` post-write hook.** Vault mtime catches it.
- **No real-time wiki-update.** Daily batch is the v1 contract. Splitting into a fast lane later is a yaml + cron edit.
- **No new MCP tool.** All changes reuse `wiki-update`, `wiki-status`, `wiki-scan-sources`.

## Open questions

None blocking — all major decisions resolved during brainstorming. Client-specific path differences belong in `client_memory.clients`, not in separate adapter architecture.

## Acceptance criteria

- Scanner emits `tier` and `weight` on every source dict.
- A vault file modified within `mtime_window_minutes` is tagged `save_events` (critical).
- Configured AI-client memory/session roots appear in scanner output as `client_memory` with a concrete `client` field.
- `wiki-update` skips extraction when no source mtime is newer than `last-extraction.ts` and reports `status: no_change`.
- `wiki-batched-daily` routine exists, runs at `06:23 UTC`, and triggers `wiki-update` with `extraction_limit=20`.
- `wiki-status` reports the four new telemetry fields.
- `config/system/wiki_signals.yaml` is the single source of truth for client-memory paths, mtime window, tier caps, and extraction limits.
