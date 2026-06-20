---
description: Generate usage analytics from LLM execution logs via nightly_maintainer
context: current
agent: general-purpose
visibility: ops
---

# /auto-analytics

Delegates to `nightly_maintainer.generate_analytics()` to produce usage
analytics from the external LLM execution log under `~/Library/Logs/Augur/llm_logs.jsonl`.

## What it does

- **Scan**: Always returns a single issue — analytics need generating each
  nightly cycle.
- **Fix**: Calls `generate_analytics(log_file)` from `nightly_maintainer`
  (graceful optional import — skips with a warning if the module is unavailable).
  Uses `src.config.paths.get_logs_dir()` to resolve the log path.

## Usage

Run automatically by the daemon at `tier: 1` (`trigger: nightly`) in the
`knowledge-enrichment` loop. Can also be invoked manually via `/routines`.

## Protocol

Implements the `OpsCommand` protocol (`scan-fix`). Dry run is supported —
pass `dry_run=True` to skip the analytics generation call.

## Implementation

`skills/ai/scripts/ops/analytics.py`
