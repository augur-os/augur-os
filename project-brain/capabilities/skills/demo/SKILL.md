---
name: demo
x-augur-type: domain
x-augur-group: brain
x-augur-release: mvp
x-augur-license: MIT
description: Demo harness for Augur workflow demonstrations. Use when resetting demo state, checking demo readiness, running per-demo workflow acceptance steps, capturing demo run evidence, or executing demo runbooks.
x-augur-requires-platform: true
x-augur-mcp-tools:
- demo-reset
- demo-readiness
- demo-smoke
- demo-run-note
- demo-run-reset
- demo-run-record-evidence
- demo-runbook-output
- demo-run-prompt
- demo-run-transcript
- demo-run-meeting-memory
- demo-run-ask-transcript
---

# Demo

Demo harness for Augur workflow demonstrations.

## Scope

Use this skill when the work is about demo lifecycle management: resetting
demo state before a live session, verifying readiness (inbox populated,
RAG indexed, cloud available), running per-demo acceptance steps and
capturing evidence, or executing demo runbooks end-to-end.

Do not use this skill for general ingestion, wiki compounding, or everyday
note capture. Those surfaces live in the `ingest` and `wiki` skills.

## Operating Contract

- Demo state lives in the runtime store (never in vault or source files).
- Evidence cards follow frontmatter conventions via `write_vault_frontmatter`.
- Each demo step is idempotent: reset → smoke → run → evidence.
- Imports shared primitives from `src.lib.ingest` (no cross-bundle ingest imports).

## Workflow

Step 1. Call `demo-readiness` to verify inbox, RAG, and cloud state.
Step 2. Call `demo-reset` to purge prior artifacts and set airplane mode.
Step 3. Run each demo step via the numbered `demo-run-*` tools.
Step 4. Call `demo-run-record-evidence` after each step to capture evidence.
Step 5. Use `demo-runbook-output` to verify expected runbook output headings.

## References

- Runbook files: `demos/demo_0{1-6}_*.md` (one per workflow example)
- Acceptance cases: `scripts/demo_run_acceptance.py`
- Readiness checks: `scripts/demo_ready.py`
- Collateral ranking: `scripts/demo_collateral_rank.py`
