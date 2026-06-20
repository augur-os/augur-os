# Known Issues

> Augur soft-launch rough edges, as of **2026-06-17**.
>
> The launch-critical loops are **green**: the full test suite passes
> (3900 passed, 0 failed), the dashboard builds and its pages mount to
> interactive with real data, and the security scan reports zero
> medium/high/critical findings (secrets, prompt-injection, static-analysis,
> file-integrity, permissions). The items below are maintenance/meta findings
> from the broader routine catalog — disclosed honestly rather than suppressed.
> They are non-blocking for the soft launch and tracked for follow-up.
>
> Each entry traces to a real run captured in
> `docs/superpowers/notes/m5b-punchlist-findings.md`.

## Code quality (`code-quality` loop)

- **[low]** Source files over the 800-line size threshold. WS5 (2026-06-18)
  split 6 `src/lib`/`cli` files behind stable interfaces (behavior-preserving,
  merged). The dashboard browse-cluster split was attempted and **reverted**: it
  passed tsc + the full suite + had no console errors, yet introduced a runtime
  React regression that left the dashboard stuck on "Loading" (a rule-28
  case — green at type-check/SSR but broken in the client). Lesson: dashboard
  component splits need per-file browser verification, not just tsc. The
  remaining oversized files (dashboard ~28, mcp ~6, core ~5 incl. `paths.py`,
  the indexer, `browse/index.py`, `skill_discovery`) stay decomposed-later —
  high-risk core/UI churn for a `[low]` heuristic; defer to a focused
  post-launch effort with browser verification per dashboard file.
- **[low]** ~42 `TODO_CLEANUP` markers across the tree — tracked debt, each
  in place at its site.
- **[low]** 1 module flagged as untested by the coverage heuristic.

## Skill catalog (`skill-standards`, `skill-quality` loops)

- **[medium]** Routing collisions: the catalog audit reports ~8 unrouted
  intents and ~7 routing collisions among skill triggers. Discovery still
  works; some intents may resolve ambiguously. Needs a routing-table pass.
- **[low]** 3 skills score below the instruction-quality threshold (tier A).
- **[low]** ~14 skills show zero recorded invocations (candidate for pruning
  or better surfacing — not necessarily dead).
- **[low]** ~10 skills declare no commands (may be data/library skills; review
  whether each is intentionally command-less).
- **[resolved]** 5 nested "standard skill core" directories
  (`recurring-reflection/dream-routine`, `retrieval-evals/retrieval-eval-harness`,
  `local-audio-processing/audio-transcription`,
  `local-document-extraction/document-to-markdown`,
  `markdown-knowledge-graph/typed-link-extraction`) carry incomplete Augur
  frontmatter (missing `x-augur-type`, no commands). They are **not** stale
  duplicates: they are intentional portable skill cores from an in-flight
  migration (ADR-040 portable-plugin-template-standard; plan
  `2026-05-30-full-standard-skill-migration.md`). The scanners now recognize
  standard cores (`is_standard_core`) and exempt them from Augur-metadata checks,
  so these false `incomplete-manifest`/`missing-license`/`no-commands-declared`/
  `no-release-tag` findings no longer fire. Completing or retiring the broader
  ADR-040 migration remains a post-launch design item.
- **[low, accepted]** The `ingest` skill declares 24 MCP tools (just over the
  20 `overly-broad-mcp-tools` heuristic). WS4 (2026-06-18) re-architected the
  former 42-tool catch-all: shared ingestion primitives were hoisted to
  `src/lib/ingest/`, the wiki engine (~12k lines) was extracted into a `wiki`
  skill, and the demo harness into a `demo` skill. The remaining 24 are a
  cohesive "bring things in" surface (url + inbox pipeline + email-drop + enrich
  + brain-insights); the inbox pipeline (14 tools) intentionally stays in
  `ingest`. The residual count over the heuristic is an accepted state for the
  ingestion hub — clearing it fully would mean extracting inbox into
  `inbox-triage`, deferred as not worth further core-MCP surgery for a `[low]`
  heuristic.

## Static analysis — out of the security loop's scope (`bandit`)

The authoritative security loop (`s1`–`s5`) scans skill directories and is
**clean** (zero medium/high). A separate raw `bandit` sweep of `src/`
(framework code, outside the loop's scope) surfaces two low-risk patterns,
tracked here for transparency:

- **[low]** `src/mcp/augur_framework/tools/infrastructure/browse/index.py:525`
  uses `exec()` to load a sweep-archive module from a **local, trusted** file
  (a module-loader pattern, not attacker-controlled input). Candidate for an
  `importlib`-based refactor.
- **[low]** A `B615` finding in the transcription/diarization path
  (ML-model loading). Standard for the model-loading library; low risk.

## Dependencies & filesystem (`self-heal`, dependency audit)

- **[low]** ~63 stray `.zip` binary fixtures live under the eval test
  fixtures; relocation/cleanup pending (test-only, not shipped at runtime).
- **[low]** `.opencode/` (IDE integration, **untracked** — not part of the
  published repo) carries a moderate `uuid` npm advisory. Out of scope for the
  published runtime.
- **[low]** A few empty directories and minor file-growth findings.
- **[info]** Stale runtime logs outside the repo (in the OS logs dir) — not
  version-controlled.

## Generated instruction files & docs (`knowledge-enrichment`)

- **[low]** Generated client instruction projections
  (`CLAUDE.md`/`CODEX.md`/`AGENTS.md`) are slightly stale relative to source;
  regenerate via the agent-sync routine.
- **[low]** One broken link in a generated audit doc
  (`docs/generated/2026-04-08-skill-catalog-audit-pass1.md`).

## Client MCP config

- **[low]** `mcp_config_drift`: `augur-core` is absent from the Claude Desktop
  and Cowork MCP configs on this branch; reconciled by the standard config
  sync (`aug config sync`) post-merge.

## Maintenance loops not run this pass

- **[info]** Three `inline-session` routines require an interactive AI-client
  session and were not executed in this gate run: `dream` (last run
  2026-05-18), `inbox-triage`, and `goal-loop`. They run in normal client
  sessions, not in the headless gate.

---

*Blockers verified green on 2026-06-17 (tests, security, page-health). This
list is the maintenance backlog, not a list of launch blockers. See
`docs/superpowers/specs/2026-06-17-launch-quality-gate-m5b-design.md` for the
quality-gate definition.*
