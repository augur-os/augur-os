---
status: Implemented
date: 2026-04-29
deciders:
  - gsannikov
related:
  - docs/superpowers/specs/2026-04-28-cross-client-bundle-architecture-design.md
  - docs/superpowers/specs/2026-04-28-cross-client-bundle-migration-design.md
hub: null
tags:
  - architecture
  - bundle-migration
  - phase-0
superseded_by: null
---

# ADR-567: Bundle Architecture — Phase 0 Cleanup

## Context

Two specs (Layer 1 architecture + Layer 4 migration) describe moving Augur from a
single-MCP-server monolith with a hand-edited visibility allowlist to a per-bundle
MCP-server architecture with no proprietary visibility filter. The migration
proceeds as four tracks (libraries, vault server split, framework split + dashboard
hub-routing redesign, visibility filter removal).

Before any track starts, an audit identified two real, Phase-0-scoped layering
smells:

1. `src/config/mcp_tools.py` referenced the vault-private skill `apple` by string
   literal in `_detect_project_context()`. The flag (`has_voice`) was set but
   never read — dead code.
2. `skills/rag/scripts/mcp/rag_tools.py` imported `build_wiki_status` and
   `lint_wiki` from `skills/ingest/scripts/`. The `wiki-status` and `wiki-lint`
   MCP tools were registered in rag's tool surface but their dependencies lived
   in ingest.

**During Phase 0 execution, three further architectural findings emerged that
were absorbed into the appropriate later tracks rather than expanded into Phase 0:**

3. The dashboard hardcodes vault-private skill names (`apple`, `lifestyle`) in
   50+ locations across URL routing, skill-import templates, workflow code, and
   production UI. The `lifestyle` hub structure is a load-bearing dashboard
   architectural assumption — not a trivial cleanup. The migration spec's
   Track 3 was split into Track 3a (MCP framework split) and Track 3b
   (dashboard hub-routing redesign) to give 3b its own brainstorming and
   implementation cycle.
4. The MCP framework code in `src/` itself hardcodes vault-private skill names
   in 10 places across 7 files: `mcp_management.py:289`, `config.py:736`,
   `domain/plugins.py:218` (default parameter value), `tools/hubs/capabilities.py:24`,
   `tools/hubs/scrape_and_save_idea.py:17/22/53` (entire module),
   `infrastructure/browse/dev.py:98`, plus the `_detect_project_context()` set
   literal at `mcp_tools.py:387`. Same pattern as dashboard. Track 3a's scope
   expanded to include removing these src/ framework hardcodes alongside the
   server split.
5. Three MCP tools (`wiki-status`, `wiki-lint`, `wiki-purge`) were
   duplicate-registered between `skills/rag/scripts/mcp/rag_tools.py` and
   `skills/ingest/scripts/mcp/wiki_tools.py` with non-trivially different
   implementations. Whichever bundle registered second silently overrode the
   first based on MCP server registration order. The ingest-side
   implementations were strictly equal-or-better (tool annotations, metrics
   tracking, additional cache-handle invalidation in `wiki-purge`).
   Phase 0 removed the rag-side duplicates rather than leaving the silent
   override in place.

(Two further "smells" identified by the original regex audit — daemon's subprocess
invocations of platform-admin scripts, and ingest's filesystem checks for
obsidian's SKILL.md — were re-evaluated and confirmed to be path/discovery
references, not Python-import smells. No fix needed.)

## Decision

Land a single Phase 0 PR that does five things:

1. Remove the `has_voice` dead-code reference to `apple` from `mcp_tools.py`.
   No architecture-rule test in Phase 0 enforces this — the broader rule lands
   with Track 3a, which rewrites the surrounding hardcoded-skill-name code
   under `augur-core`'s dynamic discovery.
2. Remove the `wiki-status`, `wiki-lint`, and `wiki-purge` MCP tool definitions
   from `skills/rag/scripts/mcp/rag_tools.py`. The canonical implementations
   already exist in `skills/ingest/scripts/mcp/wiki_tools.py` with
   strictly equal-or-better behavior. Phase 0 does NOT add anything to ingest's
   `wiki_tools.py` — the tools were already there. Two stale tests (one from
   Task 4, one from Task 5) that monkeypatched the now-deleted rag-side wrappers
   were replaced with pointer comments to canonical ingest-side coverage.
3. Add one architecture-rule test under `tests/architecture/`:
   - `test_no_cross_skill_imports.py` — fails if any skill imports another
     skill's Python modules at the AST level (or if project code imports a
     vault skill). Ships with a seeded `ALLOWED_CROSS_SKILL_IMPORTS` allowlist
     of 7 pair entries covering the 13 known pre-existing import sites that
     Track 1 will retire.
4. The architecture test detects imports across both `<skill>/scripts/` and
   `<skill>/augur/lib/` Python paths (the regex broadened from `.scripts.` to
   any `skills.<X>.<rest>` after Task 3 review found 4 augur/lib couplings).
   The test includes an allowlist validity check (typos in
   `ALLOWED_CROSS_SKILL_IMPORTS` surface immediately rather than silently
   disabling the rule), filters out imports of names that aren't real project
   skills (handles a dangling `skills.channels.*` reference in
   `file-manager/scripts/autoloop.py:197`), and resolves underscore-form import
   names back to filesystem skill names (supports future hyphenated skills).
5. Records this decision in this ADR, including the explicit Track 3a/3b
   deferrals.

Phase 0 deliberately does NOT add `test_no_vault_skill_refs.py`. That rule has
a different shape — its violations are per-line strings rather than per-pair
couplings, so a per-line allowlist would be unwieldy bookkeeping. The src/
scope of that rule is delivered by Track 3a alongside the framework rewrite
that makes it pass cleanly. The dashboard scope is delivered by Track 3b.

`test_no_cross_skill_imports.py` IS added because its allowlist mechanism is a
clean fit: each entry maps to a Track 1 deliverable (extract `rag` → empty all
`("*", "rag")` entries; extract `ai` → empty all `("*", "ai")` entries). The
allowlist is small (7 entries), each entry has a documented retirement plan,
and the test still gates against NEW cross-skill imports during the long
Tracks 1+2 execution period.

## Consequences

### Positive

- One architecture rule (cross-skill imports) is encoded as an automated test that
  fails fast on regression. Future contributors cannot introduce new cross-skill
  Python imports without explicit ALLOWLIST changes that are visible in PR review.
- The rag↔ingest cyclical-import risk is reduced; the wiki MCP tools live where
  their dependencies live. Track 1's library extraction for `rag`
  (→ `src/lib/index/`) no longer has to detangle this coupling along the way.
- Three duplicate MCP tool registrations were eliminated. Behavior change is
  monotonic improvement: pre-Phase-0, MCP server registration order silently
  determined which `wiki-status`/`wiki-lint`/`wiki-purge` implementation served
  callers; post-Phase-0, there is exactly one canonical registration per name.
  In particular, `wiki-purge` now consistently calls
  `_reset_cached_wiki_handles()` after rmtree, preventing stale-handle bugs that
  could have hit users running on the rag-side implementation.
- The migration's Track 3 acquires an honest scope split (3a + 3b), reflecting
  what the framework and dashboard refactors actually require.
- Track 3a's scope is now precise: the 10 known src/ hardcodes are an explicit
  deliverable, alongside the augur-core/augur-framework split.

### Negative

- The `src/` and `apps/dashboard/` parallel architecture-rule tests
  (`test_no_vault_skill_refs.py`) are not added in Phase 0. Until Tracks 3a and
  3b land, those areas are not protected from new vault-private hardcodes by
  automated CI. Mitigation: code review and the eventual track-specific tests
  catch regressions.
- Phase 0 is smaller than originally planned; the broader cleanup is deferred
  to separate cycles.
- The architecture test does not catch duplicate MCP tool name registrations
  (only cross-skill Python imports). A future architecture test
  (`test_no_duplicate_mcp_tool_names.py`) could fence this class of bug; it is
  noted as a Track 1 follow-up rather than added in Phase 0 to keep scope tight.

### Neutral

- The original regex audit overcounted: 5 smells became 2 confirmed Phase-0-scoped
  (apple dead code, rag→ingest) plus 3 architectural findings deferred to later
  tracks (dashboard hardcodes → Track 3b, src/ framework hardcodes → Track 3a,
  duplicate MCP registrations → Track 1 follow-up) plus 2 false positives
  (daemon→platform-admin subprocess, ingest→obsidian filesystem discovery).
  The audit methodology is improved for future use.

## Alternatives Considered

### Alternative 1: Skip Phase 0; fix smells opportunistically during tracks

Each track would discover and fix its own smells in passing. Rejected because
the smells span multiple tracks. Bundling the small Phase-0-scoped fixes here
leaves later tracks focused on their architectural goals.

### Alternative 2: Stretch Phase 0 to fix the dashboard hub-routing layer (v1)

Initially attempted (Phase 0 v1 plan). When the architecture-test was written,
it revealed 50+ violations across the dashboard. Fixing them properly requires
rewriting skill-import templates, redesigning hub URL routing, regenerating tab
registries, and updating production data/UI code — far outside Phase 0 scope.
Rejected; deferred to Track 3b. The v1 plan was reverted at commit `6dadfdd9e`
and replaced with v2.

### Alternative 3: Keep `test_no_vault_skill_refs.py` with an ALLOWED-debt list (v2)

v2 narrowed the test to `src/` only and would have committed the test with an
allowlist of 10 known violations to be emptied by Track 3a. Rejected as v3:
adding a test that requires immediate maintenance burden (allowlist) is busywork.
The honest place for the rule is Track 3a, where the rule lands clean.

### Alternative 4: Stretch Phase 0 to fix the broader `_detect_project_context()` smell

Replacing `_detect_project_context()` with a dynamic skill-registry lookup
requires the `augur-core` server that lands in Track 3a. Rejected for Phase 0
scope.

### Alternative 5: Defer wiki-purge to Track 1 instead of bundling into Task 5

Code review on Task 4 (wiki-status) discovered that wiki-purge was also
duplicate-registered, with non-trivially different implementations. The fix
could have been deferred to Track 1. Rejected because the fix was mechanical
(remove rag's duplicate; ingest's version is strictly richer) and bundling
it with Task 5 left zero rag→ingest duplicate registrations after Phase 0 —
a cleaner end state for the same effort.

## References

- Layer 1 spec: `docs/superpowers/specs/2026-04-28-cross-client-bundle-architecture-design.md`
- Layer 4 spec (with Track 3a/3b split): `docs/superpowers/specs/2026-04-28-cross-client-bundle-migration-design.md`
- Phase 0 v3 plan: `docs/superpowers/plans/2026-04-28-bundle-architecture-phase0-cleanup.md`
- Phase 0 v1 reverted at commit `6dadfdd9e` on branch `phase0-bundle-cleanup`
- Worktree branch: `phase0-bundle-cleanup`

## Impact Manifest

```yaml
impact:
  paths_renamed: []
  apis_changed:
    - name: "MCP tool 'wiki-status' (silent override resolved)"
      from: skills/rag/scripts/mcp/rag_tools.py
      to: skills/ingest/scripts/mcp/wiki_tools.py
      breaking: false  # callers used tool name only; ingest version is strictly richer
    - name: "MCP tool 'wiki-lint' (silent override resolved)"
      from: skills/rag/scripts/mcp/rag_tools.py
      to: skills/ingest/scripts/mcp/wiki_tools.py
      breaking: false
    - name: "MCP tool 'wiki-purge' (silent override resolved)"
      from: skills/rag/scripts/mcp/rag_tools.py
      to: skills/ingest/scripts/mcp/wiki_tools.py
      breaking: false  # ingest version adds _reset_cached_wiki_handles() — net improvement
  patterns_deprecated:
    - "Cross-skill Python imports (`from skills.<X>.scripts.<Y>` or `from skills.<X>.augur.lib.<Y>`)"
    - "Duplicate MCP tool registrations across multiple bundles"
  files_affected:
    - src/config/mcp_tools.py
    - skills/rag/scripts/mcp/rag_tools.py
    - skills/rag/augur/tests/test_rag_tools.py
    - skills/ingest/augur/tests/test_rag_tools.py
    - tests/architecture/  (new directory)
```
