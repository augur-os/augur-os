---
title: adaptive loop engine difficulty + promotion quirks
name: adaptive-loop-engine-difficulty-promotion-quirks
description: Engine semantics that are non-obvious from the docs — REPORT_ONLY_DEMOTION_THRESHOLD,
  --promote resets, DIFFICULTY_ESCALATION_THRESHOLD, fix:commit ratio
brain_scope: project
type: project
status: active
source_client: claude-code
source_file: project_loop_engine_quirks.md
source_hash: 08da566fa0b3ba80
---

Behaviors of `skills/daemon/scripts/adaptive_loop_executor.py` that are easy to misread:

1. **Engine demotes report-only categories at d0** when `total_fixes >= REPORT_ONLY_DEMOTION_THRESHOLD (20)` and `total_commits == 0`. So a scanner stuck in "report only — no actionable fixes" gets capped at d0 even after many runs. To activate higher-difficulty fixes, the scanner's `fix()` must actually modify code (producing real commits) — not just write reports.

2. **`--promote` is a re-enable, NOT a difficulty bump.** `python skills/daemon/scripts/adaptive_loop_executor.py --promote <loop> <category>` calls `TrustLedger.promote_category` which RESETS the category to `difficulty=0, trust=0.0, consecutive_failures=0`. Counterintuitive name.

3. **Auto-promotion via `DIFFICULTY_ESCALATION_THRESHOLD = 3`** consecutive successes triggers `d → d+1`. There's no manual difficulty-set command; you have to either (a) run the loop successfully 3 times in a row, or (b) edit `~/Library/Application Support/Augur/state/adaptive/trust_state.json` directly (hack, against the design).

4. **fix:commit ratio is the real signal.** A scanner with `total_fixes >> 0` and `total_commits == 0` is producing report-only output that the engine treats as not-making-progress and demotes. Found false-positive scanner bugs by sorting by this ratio: tech_debt_ops (rstrip-vs-strip in long-function counter), claude_md_audit (subcommand discovery missing), mcp_health_audit (proxy layer deleted in ADR-465 but scanner still cross-references against it).

5. **Wiki cycles are agent-orchestrated, not engine-orchestrated.** The `wiki-update`/`wiki-apply-concept-batch` MCP tools are atomic hands; LLM concept synthesis is the agent's job. Don't try to inline a heavy compile cycle — dispatch a sub-agent in worktree isolation. Wiki backlog is signaled via runtime `wiki/needs-update.flag`.

**How to apply:** When investigating low-trust scanners, sort by `total_fixes:total_commits == X:0`. When asked to "promote difficulty", clarify whether the user wants `--promote` (reset) or actual auto-escalation (run successfully 3x). When wiki work is queued, dispatch an agent rather than running inline.
