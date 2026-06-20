---
status: Implemented
date: 2026-05-20
deciders:
  - gsannikov
related:
  - ADR-745
  - ADR-755
  - ADR-756
  - ADR-758
hub: adaptive
tags:
  - routine
  - self-improvement
  - friction
  - transcripts
  - hooks
  - cli
superseded_by: null
spec_file: null
plan_file: null
---

# ADR-765: Agent Friction Self-Healing Routine

## Decision summary

Augur gains a self-improving routine, `auto-friction-audit` (scan-fix, under `routine-platform`, on the `self-heal` loop), that mines recent AI-client **session transcripts** plus hook logs for recurring *agent friction* — moments where an agent could not reach a sanctioned tool, hunted through tool discovery, hit a hook block, or hand-rolled a throwaway script — ranks the clusters, and writes a remedy report. Its autonomy boundary is **propose by default, auto-apply only allowlisted low-risk fixes on a dedicated branch** (never to `main`, never destructive); risky/architectural findings become proposals for `/skillify`, an ADR, or a `TODO_` marker.

## Context

A `/note <url>` capture from a Claude Code CLI session turned into an eight-step debugging detour: the agent could not reach the `save-url-source` atomic op, reverse-engineered the impl, hand-wrote a temp script at the repo root, and was then nagged by the rule-34 value-validation Stop hook — which had fired on unrelated branch dirtiness, not on anything that session did. The user's ask generalized the complaint: *"when I save a note I just want to see it saved + a summary"*, plus *"a self-improving mechanism I can run every few hours that analyzes and fixes issues like these."*

Three root causes sat under the single bad experience:

1. **No CLI path to the ingest tools.** `ingest` is a vault-tier bundle (`config/system/mcp_servers.yaml` `monolith_exclusions`), so its tools run in a separate bundle server only the dashboard connects to. A CLI agent had *no* sanctioned way to persist a URL note — hence the temp script.
2. **A hook that keyed on the wrong signal.** The rule-34 Stop hook decided "did this session do feature work" from `git status` + `git diff main...HEAD` — branch state polluted by prior, unrelated edits — so it false-fired on note-only sessions.
3. **No mechanism to notice this class of friction.** Each session re-discovered the same gaps; nothing aggregated them.

The existing routine system (ADR-755/756/758) and self-improvement surfaces (`command-evolution` loop, `/skillify` ADR-745, `/ops-learn`) gave a home to build on rather than inventing a parallel system.

## Decision

### 1. Friction is mined from transcripts, not inferred live

`shared-vault/skills/routine-platform/scripts/friction_audit.py` reads recent transcripts under `~/.claude/projects/<project-slug>*/` (main checkout + worktrees), bounded by a lookback window and file cap. Detectors (deterministic, no model calls):

- `cli-tool-unreachable` — `Error: Unknown tool '<name>'` in a tool result (aug's exact failure line; not gated on `is_error` because piped output loses the flag).
- `tool-discovery-miss` — `No matching deferred tools found` (ToolSearch came up empty).
- `hook-friction` — a Stop-hook fire (the reason text in a **user-string** message, not a tool result — matching tool results would false-positive on file reads of the hook source) and rule-29 denials (tool result with `is_error: True`).
- `adhoc-script-workaround` — a `Write` to a repo-root one-off script.
- `repeated-command-failure` — the same Bash command erroring 2+ times in one session.

Findings aggregate by `(kind, signature)` across sessions and rank by severity then recurrence.

### 2. Autonomy boundary: propose + auto-fix low-risk on a branch

`scan()` produces findings; `fix()` always writes a ranked report (`<runtime>/friction/latest-report.md`) and appends to a `friction-ledger.jsonl`, and emits a remedy proposal per cluster. Only findings explicitly tagged `remedy_auto` with a concrete patch are eligible for branch auto-apply; because friction remedies generally need judgment, the allowlist is conservative and detection is the primary value today. The branch-apply path is wired so future deterministic detectors can opt in without new plumbing. This realizes the user-chosen mode ("self-healing with a seatbelt") honestly: it never edits `main`, never deletes, and routes risky findings to proposals.

### 3. Supporting fixes (the friction the routine first surfaced)

- **Rule-34 hook scoping** (`scripts/hooks/run-hook.mjs`): "did this session change feature logic" is now derived from the Stop hook's `transcript_path` (Edit/Write/MultiEdit/NotebookEdit targets), not git branch state. Note-only sessions no longer nudge; fails open.
- **CLI-reachable note capture** (`aug note-url`): a `note_url_impl` workflow composes `url-extract` + `save-url-source`, exposed as an ADR-260 CLI subcommand (`register_subcommands` in the ingest skill) so any CLI agent gets a one-shot. The ingest `__init__.py` was made import-safe in the bare subcommand-load context. The dashboard/MCP surface still composes the atomic ops separately (the retired-`ingest-url` decision stands).
- **Brain-mount `PurePath` crash** (`src/lib/brain_mount.py`): mount paths are converted to a concrete `Path` at the single fs-op boundary, unblocking `sync all`.

## Consequences

- Recurring friction becomes visible and rankable; the first real run over 1,827 transcripts surfaced nine distinct `cli-tool-unreachable` tools (`note-url`, `ingest-url`, `wiki`, `vault-write`, `sync`, `config-sync`, …) — a whole class of bundle/CLI-surface gaps, not just the one that triggered this work.
- The routine is on-demand (`/routines run`) with a nightly `self-heal` cadence; cadence is configurable (the user's "every few hours" is a scheduler setting, not a code change).
- The friction detectors are an explicit, extensible allowlist — adding a detector or a deterministic auto-remedy is a local change to one module.
- Observer effect: sessions that build/test the friction routine appear in its own input. Detectors are scoped to precise tool-output/hook-fire shapes to keep this noise low.

## Alternatives considered

- **Propose-only** (no auto-apply): rejected — the user explicitly wanted fixes, with a seatbelt.
- **Full auto-fix to the working tree**: rejected — unattended heuristic edits to feature code is exactly where the seatbelt must hold.
- **Live capture hooks** (append friction events as they happen): deferred — transcript mining needs no new capture points and works retroactively over history.
- **A new dedicated routine skill**: rejected for now — `routine-platform` already owns harness/parity self-improvement (`auto-agent-config-parity`); a sibling command keeps the concern co-located.
