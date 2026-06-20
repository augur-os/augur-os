---
status: Implemented
date: '2026-02-08'
deciders:
- User
- Claude
related:
- ADR-054 (cross-tool offloading)
- ADR-055 (plugin integration testing)
hub: null
tags:
- plugin
- health
- sweep
superseded_by: null
---

# ADR-056: Plugin Health Sweep

## Context

An audit of all plugins revealed concrete issues that would cause 404s, broken navigation, or empty pages for users:

| Plugin | Issue | Severity |
|--------|-------|----------|
| **mcp-app-factory** | 4 tabs defined in dashboard.yaml with no page.tsx files (create, audit, templates, migrate) | Critical |
| **google-workspace** | 4 tabs defined with no page.tsx files (gmail, calendar, drive, docs) | Critical |
| **client-smb-design** | Placeholder page ("This project hub is being assembled") | Low |
| **renderer** | Stub page with only 3 info cards, no functionality | Low |

Additionally, no plugin has been tested in isolation using the new plugin integration test (ADR-055). Running each plugin through `plugin_integration_test.py` will surface build failures, missing dependencies, and 404 pages that are invisible when all plugins are enabled together.

## Decision

### Phase 1: Fix Critical Missing Pages

Create the 8 missing page.tsx files following existing patterns in each plugin.

**mcp-app-factory** — 4 pages under `plugins/ai/skills/mcp-app-factory/augur/`:

| Tab | Missing File | Content Pattern |
|-----|-------------|-----------------|
| Create | `create/page.tsx` | Form page — follow `lifestyle/dashboard/recipes/page.tsx` pattern |
| Audit | `audit/page.tsx` | Table page — follow `install/dashboard/page.tsx` pattern |
| Templates | `templates/page.tsx` | Grid page — follow `lifestyle/dashboard/recipes/RecipesGrid.tsx` pattern |
| Migrate | `migrate/page.tsx` | Workflow page — follow `venture-augur/strategy/page.tsx` pattern |

**google-workspace** — 4 pages under `plugins/productivity/skills/google-workspace/augur/`:

| Tab | Missing File | Content Pattern |
|-----|-------------|-----------------|
| Gmail | `gmail/page.tsx` | List page — follow `apple/email/page.tsx` pattern |
| Calendar | `calendar/page.tsx` | Calendar page — follow `apple/calendar/page.tsx` pattern |
| Drive | `drive/page.tsx` | File browser — follow `knowledge/dashboard/page.tsx` pattern |
| Docs | `docs/page.tsx` | Document list — follow `venture-augur/components/DocumentList.tsx` pattern |

Each page will:
- Import from `lucide-react` for icons
- Use glass-panel styling (`bg-white/5 border border-white/10 rounded-xl`)
- Include a heading, description, and placeholder data grid
- Be a valid React Server Component (async function)
- Pass `npm run build` without errors

### Phase 2: Run Integration Tests per Plugin

Run `plugin_integration_test.py --plugin <name>` for each plugin with a dashboard, sequentially. This catches:
- Build failures when only that plugin is mounted
- 404 pages from missing page.tsx
- Import errors from cross-plugin assumptions
- TypeScript errors hidden by other plugins' type declarations

**Test order** (fix blockers between tests):

```
Phase 2a: Test fixed plugins first
├── mcp-app-factory  (just fixed 4 pages)
└── google-workspace (just fixed 4 pages)

Phase 2b: Test remaining plugins alphabetically
├── apple
├── career
├── client-ai-consulting
├── client-smb-design
├── client-terminal-automation
├── content
├── eisenhower
├── finance
├── health
├── home-automation
├── lifestyle (already tested in ADR-055 — skip)
├── renderer
├── install
├── scraper
├── venture-augur
└── wearables
```

Any plugin that fails → fix the issue → re-test → continue.

### Phase 3: Track Offload Usage (ADR-054 Validation)

During Phase 1, the 8 missing page.tsx files are all `low` tier (mechanical boilerplate). These are prime candidates for offloading to Kimi via `offload_dispatcher.py`.

**Offload execution plan for Phase 1:**

```bash
# For each missing page, offload to Kimi:
python3 plugins/orchestration/skills/executor/scripts/offload_dispatcher.py \
  --task "Create page.tsx for the {tab} tab of {plugin}" \
  --files "plugins/{bundle}/skills/{plugin}/dashboard/{tab}/page.tsx" \
  --context-files "plugins/lifestyle/skills/lifestyle/augur/page.tsx" \
  --work-dir /path/to/augur
```

After each offload:
1. Claude reviews the git diff
2. Accept / fix / escalate
3. Record metrics

**Expected offload split:**
- 8 page creations → offload to Kimi (`low` tier)
- Integration test execution → Claude (`medium` tier)
- Fix diagnosis + repair → Claude (`medium`/`high` tier)
- **Target: 40-60% of Phase 1 tokens offloaded**

After completion, run `offload_dispatcher.py --metrics` and compare actual vs projected savings.

## Consequences

### Positive

- All plugin pages accessible (zero 404s)
- Each plugin verified in isolation (catches hidden dependencies)
- First real-world validation of ADR-054 offload flow
- Concrete offload metrics for cost analysis

### Negative

- ~20 min of build time per plugin for integration tests (~5 hours for all 17)
- Page stubs may need follow-up work for real functionality (Phase 1 creates navigable pages, not feature-complete ones)

### Neutral

- Lifestyle plugin already tested (ADR-055), serves as baseline
- Plugin state always restored after each test (safe)

## Alternatives Considered

### Alternative 1: Fix all plugins in one batch without per-plugin testing

Fix everything, then run `--all` once. Rejected because:
- Can't isolate which fix broke which plugin
- No incremental progress tracking
- Misses cross-plugin dependency issues

### Alternative 2: Only fix critical (missing pages), skip integration testing

Just create the 8 files and move on. Rejected because:
- The whole point is to validate the offload flow end-to-end
- Integration testing catches issues beyond missing files

## References

- ADR-054: Cross-Tool Swarm Offloading (`offload_dispatcher.py`)
- ADR-055: Plugin Integration Testing (`plugin_integration_test.py`)
- `plugins/ai/skills/mcp-app-factory/augur.yaml` (4 missing hrefs)
- `plugins/productivity/skills/google-workspace/augur.yaml` (4 missing hrefs)
- `plugins/dev/skills/validator/scripts/plugin_integration_test.py` (test runner)
- `plugins/orchestration/skills/executor/scripts/offload_dispatcher.py` (offload CLI)

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

You are implementing **ADR-056: Plugin Health Sweep**.

Read the full ADR: `docs/decisions/ADR-056-plugin-health-sweep.md`

### Offload Protocol (ADR-054)

Before dispatching each step, check if it can be offloaded to a cheap CLI:

1. Read offload config: `cat config/system/llm.yaml` → look for `offload:` section
2. If `offload.enabled: true` AND the step's tier is `low`:
   ```bash
   python3 plugins/orchestration/skills/executor/scripts/offload_dispatcher.py \
     --task "STEP DESCRIPTION" \
     --files "TARGET_FILE_1,TARGET_FILE_2" \
     --context-files "REFERENCE_FILE_FOR_PATTERNS" \
     --work-dir $(pwd)
   ```
3. Review the JSON output — check `success`, `files_changed`, and `diff` fields
4. Record the verdict:
   - Accept (diff is correct): `python3 plugins/orchestration/skills/executor/scripts/offload_dispatcher.py --record-verdict accept`
   - Fix (you patched the output): `python3 plugins/orchestration/skills/executor/scripts/offload_dispatcher.py --record-verdict fix`
   - Escalate (offload failed, you did it yourself): `python3 plugins/orchestration/skills/executor/scripts/offload_dispatcher.py --record-verdict escalate`
5. If `offload.enabled: false` OR tier is `medium`/`high` → do the step yourself as normal

### Phase 1: Fix Missing Pages (Offload Candidates)
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | low | Create create/page.tsx for mcp-app-factory — form page with glass-panel styling | `plugins/ai/skills/mcp-app-factory/augur/create/page.tsx` |
| 1.2 | developer | low | Create audit/page.tsx for mcp-app-factory — table page with empty state | `plugins/ai/skills/mcp-app-factory/augur/audit/page.tsx` |
| 1.3 | developer | low | Create templates/page.tsx for mcp-app-factory — grid page | `plugins/ai/skills/mcp-app-factory/augur/templates/page.tsx` |
| 1.4 | developer | low | Create migrate/page.tsx for mcp-app-factory — workflow page | `plugins/ai/skills/mcp-app-factory/augur/migrate/page.tsx` |
| 1.5 | developer | low | Create gmail/page.tsx for google-workspace — email list page | `plugins/productivity/skills/google-workspace/augur/gmail/page.tsx` |
| 1.6 | developer | low | Create calendar/page.tsx for google-workspace — calendar view | `plugins/productivity/skills/google-workspace/augur/calendar/page.tsx` |
| 1.7 | developer | low | Create drive/page.tsx for google-workspace — file browser | `plugins/productivity/skills/google-workspace/augur/drive/page.tsx` |
| 1.8 | developer | low | Create docs/page.tsx for google-workspace — document list | `plugins/productivity/skills/google-workspace/augur/docs/page.tsx` |

### Phase 2: Integration Test Fixed Plugins
**Strategy**: PIPELINE

| Step | Agent | Tier | Task |
|------|-------|------|------|
| 2.1 | validator | medium | Run: `python3 plugins/dev/skills/validator/scripts/plugin_integration_test.py --plugin mcp-app-factory` — fix any failures |
| 2.2 | validator | medium | Run: `python3 plugins/dev/skills/validator/scripts/plugin_integration_test.py --plugin google-workspace` — fix any failures |

### Phase 3: Integration Test Remaining Plugins
**Strategy**: PIPELINE

| Step | Agent | Tier | Task |
|------|-------|------|------|
| 3.1 | validator | medium | Run integration test for: apple, career, client-ai-consulting, client-smb-design |
| 3.2 | validator | medium | Run integration test for: client-terminal-automation, content, eisenhower, finance |
| 3.3 | validator | medium | Run integration test for: health, home-automation, renderer, install |
| 3.4 | validator | medium | Run integration test for: scraper, venture-augur, wearables |
| 3.5 | developer | medium | Fix any issues found in steps 3.1-3.4 |

### Phase 4: Offload Metrics Report
**Strategy**: PIPELINE

| Step | Agent | Tier | Task |
|------|-------|------|------|
| 4.1 | analyst | low | Run `python3 offload_dispatcher.py --metrics` and report offload stats |
| 4.2 | analyst | low | Compare actual offload % against projected 40-60% |

### Final Phase: Verification
| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Run `pytest tests/unit/ tests/integration/` — no regressions |
| V.2 | validator | low | Run `npm run build` in `src/dashboard/` — clean build with all plugins |
| V.3 | architect | low | Verify all plugins have 0 pages_fail in test results |

### Completion Criteria
- [ ] 8 missing page.tsx files created and building
- [ ] mcp-app-factory: all pages return 200 in isolation test
- [ ] google-workspace: all pages return 200 in isolation test
- [ ] All remaining plugins tested (at least mount + build pass)
- [ ] Offload metrics captured and reported
- [ ] All existing tests pass, clean build
- [ ] plugin_state.json restored to original state
