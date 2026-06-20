---
title: Augur soft-launch punch-list — goal-mode continuation prompt
x-augur-note-type: thought
content_hash: sha256:09e4c6ac7febb74225ae2cc6da8402a93d613a990c39f37f6234f1fd87cfad55
captured_at: '2026-06-18T11:36:24.362067Z'
tags:
- thought
_source_type: thought
---

Paste this into a fresh session to resume the Augur public-soft-launch "all" punch-list program in goal mode.

---

Resume the Augur public-soft-launch "all" punch-list program in goal mode — keep driving it autonomously (brainstorm→spec→plan→subagent-build→ff-merge per item), surfacing only genuine blockers, until the goal is met or I stop you.

START HERE:
- Read the memory file first (full state): ~/.claude/projects/-Users-<user>-Projects-Augur/memory/public-soft-launch-readiness.md
- Specs/plans live in docs/superpowers/specs/ and docs/superpowers/plans/ (dated 2026-06-16..18).
- Everything below is merged to origin/main; latest commit 87a6dd9083 (plus this keep). No open branches, no background agents. The progress ledger is .git/sdd/progress.md.

DONE + MERGED (verified): M5b launch quality gate; M6 publish path (full-scope clean-history builder — M6 = flip release_scope.yaml docs_only→full + ./scripts/release.sh); WS1 (routing catalog 6×0 + 3 skills→tier-A); WS3 (ADR-040 standard-core scanner FP fix); WS4 (deep ingest re-architecture: src/lib/ingest shared lib + wiki skill + demo skill; ingest accepted at 24 tools, disclosed); WS5 Phase 1 (6 src/lib+cli files split behind stable re-export interfaces).

GOAL / what remains:
1. WS5 remaining oversized-file splits — DEFERRED, and I recommend leaving deferred: dashboard ~28, mcp 6, core 5 (paths.py, indexer, browse/index.py, skill_discovery). WS5 Phase 2a (the dashboard browse-cluster split) was REVERTED — it passed tsc + the full 3904 suite + had no console errors yet wedged the dashboard on "Loading" (a runtime React regression; classic rule-28). These are [low] "consider splitting" heuristics; the core/dashboard ones are high-risk core churn pre-launch. If you do pursue them, do dashboard files ONE AT A TIME with per-file BROWSER verification, not just tsc.
2. Gated on me (DO NOT do autonomously — always confirm): M4 fresh-env CI runner validation (blocked on my GitHub billing fix — when I say "billing fixed", re-dispatch fresh-env-onboard.yml all-OS + a negative control), and M6 (flip release_scope→full + public push to augur-os — irreversible external publish).

NON-NEGOTIABLE GUARDRAILS (learned the hard way this program):
- VERIFY EVERYTHING YOURSELF. Subagents repeatedly false-claimed "3904 passed" — re-run `uv run pytest -q -p no:cacheprovider` yourself before trusting any green claim (rule 34).
- For ANY dashboard change: browser-verify it renders real data to interactive state (rule 28); tsc + suite passing is NOT sufficient (Phase 2a proved this).
- Watch for ORPHAN next-dev servers squatting :3000 serving stale code: if /browse is stuck "Loading" but MCP health is ok, check `lsof -nP -iTCP:3000 -sTCP:LISTEN` PID vs the lifecycle; dev stderr "Another next dev server already running, run kill <pid>" / "unknown process" means an orphan — stop it, then `aug dev build` for a fresh managed server, then re-test.
- Use the sanctioned wrappers: `aug dev build` (never raw pnpm dev / rm -rf .next / kill), and re-run the catalog audit (check_resolvable → all 6 counters 0) after skill/capability changes.
- Use opus for whole-branch reviews of risky/large diffs — they caught real defects (missed import forms, scanner-gaming, orphan regressions) that sonnet implementers missed.
- ff-merge each verified phase to main; commit by explicit pathspec (NOT git add -A — it sweeps evals/rank.json telemetry); revert that telemetry before merging.

My recommendation (from last session): the safe, high-value work is banked; the remaining WS5 is disproportionate risk for [low] findings. Confirm with me whether to (a) stop the punch-list and hold for M4/M6, or (b) continue specific remaining items — before grinding more. Start by reading the memory file, give me a 2-line orientation, and ask which.
