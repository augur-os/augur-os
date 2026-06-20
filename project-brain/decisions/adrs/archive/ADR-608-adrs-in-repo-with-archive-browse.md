---
status: Implemented
date: 2026-05-10
deciders:
  - gsannikov
related:
  - ADR-270
  - ADR-440
  - ADR-537
  - ADR-541
  - ADR-607
hub: command
tags:
  - adr-tooling
  - documentation
  - public-release
  - dashboard-browse
  - augur-os
superseded_by: null
---

# ADR-608: ADRs Live In-Repo with Smart Archive Browsing

## Context

ADRs currently live in `~/Projects/Au-docs/adrs/` — outside the project repository, per ADR-270's documents-directory separation. As of 2026-05-10:

1. **The external directory is not under version control.** ADR-607 was just created there and is one `rm` away from being lost. There is no commit history, no PR review surface, no remote backup, and collaborators cannot see new ADRs without separate filesystem access.
2. **The release process publishes through `augur-os/augur-os`** (`scripts/release.sh` → `scripts/build_public_release_tree.py`). The hardcoded `DOCS_ONLY_ALLOWLIST` does not include any ADR content — the release surface has zero architectural decisions in it today.
3. **Archived ADRs are unbrowseable.** The 358 ADRs already moved into `archive/implemented/*.zip` (six 100-ADR bundles) are inaccessible from the dashboard. The `/browse` page's "ADRs" category shows only the 99 live `.md` files. To read an archived ADR a user must invoke `/adr extract ADR-NNN` from the CLI.
4. **Dashboard ADR surface is single-tab.** ADRs surface only via the `/browse` page's "ADRs" category — there is no dedicated hub tab. This is fine, but means the path migration must keep that one surface working.

The Augur repo is going public per ADR-537. A back-catalog content scan run on 2026-05-10 found zero blocking sensitive content across the 99 live ADRs (no PII, no secrets, no internal incident details, no third-party customer data — flagged keyword matches were word-overlap noise like "raise" used as a verb).

## Decision

Move ADRs into the project repository at `docs/adrs/`, repoint `get_adr_dir()`, include the directory in the public release pipeline, and extend the dashboard browse surface to show archived ADRs alongside live ones with a chip and lazy extraction. Two phases.

### Phase 1 — Path migration (immediate)

1. **Update `get_adr_dir()`** in `src/config/paths.py` and `src/lib/adr_utils.py` to resolve `<repo>/docs/adrs/`. This single helper drives the index generator, RAG indexer, `/adr` commands, and the dashboard `list-adrs` MCP tool — repoint once, everything follows.
2. **Migrate files**: copy `~/Projects/Au-docs/adrs/*.md`, `archive/`, `TEMPLATE.md`, and `implemented-adr-ledger.md` into `<repo>/docs/adrs/`. Commit. Verify `/adr status`, `/adr list`, `/adr extract` against the new location. Then remove from `~/Projects/Au-docs/adrs/` (the parent `~/Projects/Au-docs/` directory stays, retains non-ADR documents per ADR-270).
3. **Audit hardcoded paths** in `.github/scripts/generate_adr_index.py`, `.github/scripts/adr_archive.py`, agent-topic docs, CLAUDE.md generator, RAG indexer config. All should already use `get_adr_dir()`; flag and fix any literal paths.
4. **Update `scripts/build_public_release_tree.py`** to include `docs/adrs/` in the public release. Add a new `DOCS_ONLY_DIR_ALLOWLIST = ["docs/adrs"]` for recursive directory copy alongside the existing file allowlist. Add a test asserting `docs/adrs/TEMPLATE.md` and at least one archive zip end up in the release tree.

### Phase 2 — Smart archive browsing (scheduled)

5. **Sidecar JSON archive index.** Extend `.github/scripts/adr_archive.py archive-implemented` to also emit `archive/implemented-adrs-index.json` — structured ADR metadata extracted from each zipped `.md` (frontmatter + `# Title`). Schema:

   ```json
   {
     "adr_number": "ADR-NNN",
     "title": "...",
     "status": "Implemented",
     "date": "YYYY-MM-DD",
     "hub": "...",
     "tags": [...],
     "zip": "implemented-adrs-NNN-MMM.zip"
   }
   ```

   Add a `--rebuild-index` flag that regenerates the JSON from existing zips — used once for retroactive backfill of the 6 current bundles. The markdown ledger stays unchanged for humans.

6. **Browse-side wiring.** Five small changes:

   - `list_adrs_impl()` in `src/mcp/augur_framework/tools/infrastructure/browse/agents.py` reads both surfaces: live `.md` (existing) emits `archived: false`; entries from `archive/implemented-adrs-index.json` emit `archived: true` with a synthetic path `archive://ADR-NNN`.
   - `transformAdrs()` in `apps/dashboard/lib/browse/transforms.ts` propagates `archived` into `metadata.archived` and switches `primaryAction.type` from `"open-file"` to `"extract-and-open-adr"` for archived items.
   - New action handler in the dashboard recognizes `extract-and-open-adr`, calls a new API route `POST /api/adrs/extract`, then opens the returned path in the configured editor (same UX as live ADRs).
   - New API route `POST /api/adrs/extract` shells out to `.github/scripts/adr_archive.py extract ADR-NNN`, returns `{path: "/tmp/.../ADR-NNN.md"}`. Extracted files live in the runtime temp dir; cleaned up on dashboard restart.
   - Recent-views log at `runtime/adrs/recent-views.jsonl` — append-only line `{adr_number, ts, archived}` written by the extract route. Browse panel can later surface a "recently viewed ADRs" chip from this file. Display layer for it is out of scope here; the log is the foundation.

   The browse list-item component renders an `archived` chip alongside the existing status badge when `metadata.archived === true`.

### What this changes for the user

- **Same tab as today: `/browse` → "ADRs" category.** No new pages.
- **List doubles in size** (99 live + 358 archived = 457 visible). Existing search, filter, sort all work without modification because the data shape is the same.
- **Click on archived ADR**: brief extraction (~tens of ms), then opens in the editor identically to live ADRs.
- **All 458 ADRs are now in the public release** flowing through `augur-os/augur-os`.

## Consequences

### Positive

- ADR-607 and every ADR after it become version-controlled the moment they hit `docs/adrs/`. This was the bug.
- ADRs become visible in PRs, in `git blame`, in commit history. Reviewers see architecture decisions inline with code changes.
- Public release surface gains the architectural decision record — `augur-os/augur-os` reflects the real engineering history.
- Dashboard can now browse the *full* 458-ADR catalog. Archived ADRs become one click away instead of a CLI extract step. Big UX upgrade for any "what did we decide about X" investigation.
- Archive zips remain on disk, no gist or external repo to maintain. Single source of truth: the `docs/adrs/` directory.
- `/adr extract` already exists and is the right primitive for lazy extraction — the dashboard just learns to call it.
- Public release of ADRs is automatic via the existing `release.sh` flow once `DOCS_ONLY_DIR_ALLOWLIST` includes `docs/adrs/`. No new pipeline.

### Negative

- Repo size grows by ~3 MB (live `.md`) + ~6 MB (archive zips, compressed) ≈ 9 MB. Negligible.
- Extracting an archived ADR creates a temp file. Cumulative temp-dir size on heavy days could reach 100 KB; cleanup tied to dashboard restart. Acceptable.
- Phase 2 adds dashboard surface area: a new API route, a new action type, a new chip render, a new recent-views log. Each is small, but the bundle is non-trivial.
- ADR-270 needs partial supersedence in the deciders' minds. The ADR clause moves in-repo; non-ADR content (reports, exports, binaries) remains in `get_documents_dir()`. Documented here so future readers understand the boundary.
- Public visibility is the design intent (per ADR-537), but means future ADRs must be drafted with the assumption they'll be public. New convention going forward; not a regression.

### Neutral

- `~/Projects/Au-docs/` directory stays. Only the `adrs/` subtree migrates.
- Markdown ledger (`implemented-adr-ledger.md`) stays for humans; the new JSON index is parallel for tooling. No deprecation.
- The existing `/adr` command surface is unchanged — every subcommand goes through `get_adr_dir()`, which now points elsewhere. No user-facing CLI changes.

## Alternatives Considered

### Alternative 1: Public gist for archived bundles, in-repo for live

Keep live ADRs in-repo at `docs/adrs/`, but mirror archived zip bundles to a separate GitHub gist for public access without exposing the rest of Augur.

**Rejected because** the Augur repo is going public anyway (ADR-537) — there's no public/private boundary to preserve. The gist adds operational complexity (API to write, soft size limits, clunky binary diffs) for zero benefit. In-repo archives are strictly simpler.

### Alternative 2: Keep ADRs external, add a git submodule pointing at a new `augur-adrs` repo

Create a dedicated `augur-adrs` repo at `~/Projects/Au-docs/adrs/`, initialize it as a git repo, and reference it from Augur as a submodule.

**Rejected because** submodules add tooling friction (every `git clone` needs `--recurse-submodules`, every commit cycle has two repos, CI must handle the submodule), and the ADR catalog is small enough that a submodule is overkill. ADRs benefit from being inline with the code that implements them.

### Alternative 3: Eager extraction of all archives at migration time

Extract all 358 archived ADRs into `docs/adrs/archive/extracted/` and serve them as live `.md` files. No lazy extraction, no chip distinction.

**Rejected because** it inflates the repo browse surface from 99 to 457 entries with no UX distinction between active and archived, defeats the purpose of archiving in the first place, and increases repo file count by 4.6×. The chip + lazy extraction model preserves the live/archived semantic distinction users care about.

## Implementation Order

### Phase 1 — Path migration (4 commits, immediate)

| Step | Task |
|---|---|
| 1.1 | Repoint `get_adr_dir()` in `src/config/paths.py` and `src/lib/adr_utils.py`. Audit `.github/scripts/`, RAG indexer, agent-topic docs for hardcoded `~/Documents/Augur/adrs` or `~/Projects/Au-docs/adrs/` literals. Fix any. |
| 1.2 | Copy ADR contents into `docs/adrs/` (live `.md` + `archive/` + `TEMPLATE.md` + ledger). `git add`, commit. |
| 1.3 | Verify: regenerate ADR index, run RAG indexer, run `python3 -m skills.ai.scripts.sync_agents sync agents all`, browse the dashboard `/browse` ADRs category and confirm the list still loads. Fix any path issues that surfaced. |
| 1.4 | Update `scripts/build_public_release_tree.py`: add `DOCS_ONLY_DIR_ALLOWLIST = ["docs/adrs"]`, extend `build_release_tree` to recursively copy listed dirs. Add test asserting `docs/adrs/TEMPLATE.md` plus a sample archive zip land in the release tree. |
| 1.5 | Once verified: delete `~/Projects/Au-docs/adrs/` contents (preserve the parent `Au-docs/` directory for non-ADR content per ADR-270). |

### Phase 2 — Smart archive browsing (2 commits, scheduled)

| Step | Task |
|---|---|
| 2.1 | Extend `.github/scripts/adr_archive.py`: emit `archive/implemented-adrs-index.json` from each ADR's frontmatter at archive time. Add `--rebuild-index` flag. Run once with `--rebuild-index` to backfill the 6 existing bundles. Add tests covering frontmatter parsing and round-trip. |
| 2.2 | Browse wiring (5 sub-changes): `list_adrs_impl()` reads both live and indexed-archive surfaces; `transformAdrs()` honors `archived`; new dashboard action `extract-and-open-adr`; new API route `POST /api/adrs/extract`; recent-views log at `runtime/adrs/recent-views.jsonl`. Browse list-item renders `archived` chip when `metadata.archived === true`. Tests for each layer. |

## References

- ADR-270 — Documents directory separation (partially superseded by this ADR for the ADR clause only)
- ADR-440 — Open Source Launch (informs sensitive-content scrubbing posture)
- ADR-537 — Open Source Launch Execution (the deadline driving public visibility)
- ADR-541 — Browse Taxonomy (governs the `/browse` page categories)
- ADR-607 — Wiki Signal Priority (just-prior ADR; concrete instance of the problem this ADR solves)
- Existing tooling: `scripts/release.sh`, `scripts/build_public_release_tree.py`, `.github/scripts/adr_archive.py`, `src/mcp/augur_framework/tools/infrastructure/browse/agents.py`, `apps/dashboard/lib/browse/transforms.ts`

## Impact Manifest

```yaml
impact:
  paths_renamed:
    - "ADRs: ~/Projects/Au-docs/adrs/ -> docs/adrs/"
    - "ADR archive: ~/Projects/Au-docs/adrs/archive/ -> docs/adrs/archive/ (flat, no implemented/ subfolder)"
  paths_dropped:
    - "ADR markdown ledger: docs/adrs/archive/implemented-adr-ledger.md (replaced by JSON sidecar)"
    - "Archive subfolder: docs/adrs/archive/implemented/ (zips moved up one level)"
  apis_changed:
    - "get_adr_dir() in src/config/paths.py and src/lib/adr_utils.py: now resolves <repo>/docs/adrs/"
    - "list-adrs MCP tool: result entries now include `archived: bool` field"
    - "BrowseItem for ADRs: new metadata.archived field; primaryAction.type can be 'extract-and-open-adr'"
    - "build_public_release_tree.py: new DOCS_ONLY_DIR_ALLOWLIST recursive-copy mechanism"
    - "adr_archive.py archive-implemented: now emits implemented-adrs-index.json sidecar; new --rebuild-index flag"
  patterns_deprecated:
    - "External-only ADR storage (ADR-270's ADR clause). Other documents stay external."
  files_affected:
    - "src/config/paths.py"
    - "src/lib/adr_utils.py"
    - "scripts/build_public_release_tree.py"
    - "tests/scripts/test_build_public_release_tree.py"
    - ".github/scripts/adr_archive.py"
    - ".github/scripts/generate_adr_index.py (audit only — should already use the helper)"
    - "src/mcp/augur_framework/tools/infrastructure/browse/agents.py"
    - "apps/dashboard/lib/browse/transforms.ts"
    - "docs/agent-topics/agent-rules.md (CLAUDE.md source — update path references)"
    - "docs/agent-topics/ARCHITECTURE.md (if it documents the get_adr_dir layout)"
  files_created:
    - "docs/adrs/ (entire migrated tree, 99 .md + archive/ + TEMPLATE.md)"
    - "docs/adrs/archive/implemented-adrs-index.json"
    - "apps/dashboard/app/api/adrs/extract/route.ts"
    - "runtime/adrs/recent-views.jsonl (created at first extract)"
```

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

**Team name**: `adr-608-adrs-in-repo`

### Phase 1: Path migration
**Strategy**: PIPELINE (1.1 → 1.2 → 1.3 → 1.4 → 1.5)

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | architect | high | Repoint `get_adr_dir()` to resolve `<repo>/docs/adrs/`. Grep for any literal external ADR path; replace with helper call. | `src/config/paths.py`, `src/lib/adr_utils.py`, `.github/scripts/generate_adr_index.py`, RAG indexer config files |
| 1.2 | developer | medium | Copy ADR tree from `~/Projects/Au-docs/adrs/` into `docs/adrs/`. `git add` the tree. Single commit. | `docs/adrs/**` (99 .md + archive/ + TEMPLATE.md + ledger) |
| 1.3 | validator | medium | Regenerate ADR index, run RAG indexer, run sync_agents, smoke-test `/browse` ADRs category. Fix any surfaced path bugs. | `docs/generated/adr-index.md`, runtime indexes |
| 1.4 | developer | medium | Add `DOCS_ONLY_DIR_ALLOWLIST = ["docs/adrs"]` to `build_public_release_tree.py`. Extend `build_release_tree()` to recursively copy listed dirs. Add test. | `scripts/build_public_release_tree.py`, `tests/scripts/test_build_public_release_tree.py` |
| 1.5 | developer | low | Once 1.3 confirms no breakage, remove `~/Projects/Au-docs/adrs/` contents (preserve parent dir). One commit recording the cleanup. | `~/Projects/Au-docs/adrs/` (delete) |

### Phase 2: Smart archive browsing
**Strategy**: PIPELINE (2.1 → 2.2)

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | high | Extend `adr_archive.py`: emit `implemented-adrs-index.json` at archive time; add `--rebuild-index` flag; backfill existing 6 zips by running with `--rebuild-index`. Add tests. | `.github/scripts/adr_archive.py`, `tests/scripts/test_adr_archive.py`, `docs/adrs/archive/implemented-adrs-index.json` |
| 2.2 | developer | high | Browse wiring: `list_adrs_impl` reads both surfaces; `transformAdrs` propagates `archived`; new action `extract-and-open-adr`; new API route `POST /api/adrs/extract`; recent-views log; archived chip in list-item. Tests at each layer. | `src/mcp/augur_framework/tools/infrastructure/browse/agents.py`, `apps/dashboard/lib/browse/transforms.ts`, `apps/dashboard/app/api/adrs/extract/route.ts`, dashboard browse list-item component |

### Completion Criteria

**Phase 1**:
- [ ] `get_adr_dir()` returns `<repo>/docs/adrs/`
- [ ] No literal `Au-docs/adrs` or `Documents/Augur/adrs` strings remain in source files (excluding ADRs themselves and historical references)
- [ ] All 99 live `.md` ADRs + `archive/` + `TEMPLATE.md` + ledger present at `docs/adrs/`
- [ ] `/browse` page "ADRs" category loads identically to before
- [ ] `/adr status`, `/adr list`, `/adr extract ADR-NNN` work against the new location
- [ ] `python3 .github/scripts/generate_adr_index.py` succeeds and produces non-empty index
- [ ] `scripts/build_public_release_tree.py` includes `docs/adrs/**` content; test passes
- [ ] `~/Projects/Au-docs/adrs/` contents removed; parent dir intact
- [ ] One commit per implementation step (1.1, 1.2, 1.3 cleanup, 1.4, 1.5)

**Phase 2**:
- [ ] `docs/adrs/archive/implemented-adrs-index.json` exists and includes all 358 archived ADRs with full metadata
- [ ] `list-adrs` MCP tool returns combined list of live + archived; `archived` field present on every entry
- [ ] `/browse` ADRs category shows live (no chip) and archived (chip rendered) entries in one list
- [ ] Click on archived ADR opens the extracted file in the editor; recent-views log appended
- [ ] `runtime/adrs/recent-views.jsonl` accumulates one line per click
- [ ] Tests at archive, browse-MCP, and dashboard transform layers all green
- [ ] ADR status updated from Accepted → Implemented
