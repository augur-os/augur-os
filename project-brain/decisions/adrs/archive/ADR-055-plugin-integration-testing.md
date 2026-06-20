---
status: Implemented
date: '2026-02-08'
deciders:
- User
- Claude
related: []
hub: null
tags:
- plugin
- integration
- testing
superseded_by: null
---

# ADR-055: Plugin Integration Testing

## Context

Every plugin in Augur has a dashboard UI (pages, tabs, buttons, actions), but there is no automated way to verify that enabling a plugin actually produces a working UI. The existing test suite has only smoke tests (`renders without crashing` via Jest) — these catch import errors but miss:

- Pages that 404 after mounting
- Broken navigation tabs (href mismatches)
- Buttons that render but don't have click handlers
- Visual regressions (missing icons, broken layouts)
- Build failures from bad TypeScript in plugin code

Currently all 25 plugins are permanently enabled in `plugin_state.json`. There is no test that validates the enable → mount → build → UI flow for a single plugin in isolation.

## Decision

### 1. Plugin Integration Test Script

New script: `plugins/dev/skills/validator/scripts/plugin_integration_test.py`

Tests one plugin at a time through the full lifecycle:

```
Phase 1: ISOLATE  — disable all plugins, enable only the target
Phase 2: MOUNT    — run mount-plugins, generate tab registry
Phase 3: BUILD    — npm run build (catches TS errors, missing imports)
Phase 4: SERVE    — start dev server in background
Phase 5: NAVIGATE — visit every page defined in dashboard.yaml
Phase 6: CHECK    — for each page: no console errors, key elements present, buttons rendered
Phase 7: RESTORE  — re-enable all plugins, remount
```

### 2. Page Checks (Phase 6)

For each page in `dashboard.yaml → tabs`:

| Check | Method | Pass Criteria |
|-------|--------|---------------|
| **Page loads** | HTTP GET → 200 | Status code 200, no redirect to error page |
| **No console errors** | Chrome MCP `read_console_messages` | Zero `error`-level messages |
| **Layout rendered** | DOM query for `[data-testid="hub-layout"]` or `<main>` | Element exists |
| **Tab navigation** | DOM query for tab links matching dashboard.yaml hrefs | All tabs present with correct hrefs |
| **Buttons rendered** | DOM query for `<button>` elements | At least 1 button on each page |
| **No broken images** | Query `img[src]` elements, check naturalWidth > 0 | No zero-width images |
| **Visual snapshot** | Screenshot per page | Saved for manual review / future regression |

### 3. CLI Interface

```bash
# Test a single plugin
python3 plugins/dev/skills/validator/scripts/plugin_integration_test.py \
  --plugin lifestyle

# Test with Chrome MCP (full visual checks)
python3 plugins/dev/skills/validator/scripts/plugin_integration_test.py \
  --plugin lifestyle --browser

# Dry run (show what would be tested, don't change state)
python3 plugins/dev/skills/validator/scripts/plugin_integration_test.py \
  --plugin lifestyle --dry-run

# Test all plugins one by one
python3 plugins/dev/skills/validator/scripts/plugin_integration_test.py --all
```

### 4. Output Format

JSON report to stdout + saved to `runtime/plugin-test-results/{plugin}.json`:

```json
{
  "plugin": "lifestyle",
  "timestamp": "2026-02-08T15:00:00",
  "phases": {
    "isolate": { "status": "pass", "duration_s": 0.1 },
    "mount": { "status": "pass", "duration_s": 2.3 },
    "build": { "status": "pass", "duration_s": 18.5 },
    "serve": { "status": "pass", "duration_s": 3.0 },
    "navigate": { "status": "pass", "duration_s": 8.2 },
    "check": { "status": "pass", "duration_s": 4.1 },
    "restore": { "status": "pass", "duration_s": 2.5 }
  },
  "pages": [
    {
      "path": "/lifestyle",
      "tab_id": "overview",
      "status": 200,
      "console_errors": 0,
      "buttons_found": 3,
      "layout_present": true,
      "screenshot": "runtime/plugin-test-results/lifestyle/overview.png"
    },
    {
      "path": "/lifestyle/recipes",
      "tab_id": "recipes",
      "status": 200,
      "console_errors": 0,
      "buttons_found": 5,
      "layout_present": true,
      "screenshot": "runtime/plugin-test-results/lifestyle/recipes.png"
    }
  ],
  "summary": {
    "total_pages": 8,
    "pages_pass": 8,
    "pages_fail": 0,
    "build_pass": true,
    "total_duration_s": 38.7
  }
}
```

### 5. How It Works Internally

**Plugin state manipulation**:
```python
# Save original state
original = json.loads(plugin_state_path.read_text())

# Disable all, enable target
isolated = {k: False for k in original}
isolated[plugin_name] = True
plugin_state_path.write_text(json.dumps(isolated, indent=2))

# ... run tests ...

# Restore original state
plugin_state_path.write_text(json.dumps(original, indent=2))
```

**Mount + build**:
```python
subprocess.run(["npm", "run", "mount-plugins"], cwd=dashboard_dir)
subprocess.run(["npm", "run", "build"], cwd=dashboard_dir)
```

**Page navigation** (two modes):

**Mode A: HTTP-only** (default, no browser needed):
- Start dev server: `npm run dev` in background
- For each tab: `requests.get(f"http://localhost:3000{tab.href}")`
- Check status code 200, response contains expected HTML

**Mode B: Browser via Chrome MCP** (`--browser` flag):
- Use Chrome MCP `navigate` + `read_page` + `read_console_messages`
- Full DOM inspection, button counting, screenshot capture
- Catches JS runtime errors, hydration failures, broken interactivity

## Consequences

### Positive

- Catches broken plugins before they reach the user
- Tests the full enable → mount → build → serve → navigate chain
- Produces visual screenshots for manual review
- Can run per-plugin (fast) or all-plugins (nightly)
- JSON output integrable with nightly CI reports

### Negative

- Full build per plugin is slow (~20s per plugin, ~8 min for all 25)
- Plugin state manipulation during test means dashboard is unusable during run
- Chrome MCP mode requires browser to be running

### Neutral

- Test results saved to runtime dir (gitignored, ephemeral)
- No changes to plugin code — purely observational testing
- Restores original state even on failure (try/finally)

## Alternatives Considered

### Alternative 1: Jest-only testing (no real server)

Extend existing RSC smoke tests with more assertions. Rejected because:
- Cannot test mounting, tab registry generation, or navigation
- Cannot catch build failures from bad TypeScript
- No visual verification

### Alternative 2: Playwright e2e tests per plugin

Full Playwright test suite per plugin. Rejected for now because:
- Heavyweight setup for a first iteration
- This ADR is a stepping stone — can add Playwright later using the screenshots as baselines

## References

- `config/system/plugin_state.json` (plugin enable/disable state)
- `src/dashboard/lib/plugin-state.ts` (`isPluginEnabled()`, `loadPluginState()`)
- `src/dashboard/scripts/mount-plugins.ts` (plugin mounting logic)
- `src/dashboard/scripts/validate-tab-registry.ts` (tab validation)
- `plugins/dev/skills/validator/SKILL.md` (UI validation capabilities)
- `plugins/lifestyle/skills/lifestyle/augur.yaml` (test candidate: 8 tabs)

## Implementation Prompt

> Paste this into Claude Code to execute this ADR.

You are implementing **ADR-055: Plugin Integration Testing**.

Read the full ADR: `docs/decisions/ADR-055-plugin-integration-testing.md`

### Phase 1: Create Test Script
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | medium | Create plugin_integration_test.py with all 7 phases (isolate, mount, build, serve, navigate, check, restore), CLI args (--plugin, --browser, --dry-run, --all), JSON output | `plugins/dev/skills/validator/scripts/plugin_integration_test.py` |

### Phase 2: Run on Lifestyle Plugin
**Strategy**: PIPELINE

| Step | Agent | Tier | Task |
|------|-------|------|------|
| 2.1 | validator | medium | Execute: `python3 plugins/dev/skills/validator/scripts/plugin_integration_test.py --plugin lifestyle` |
| 2.2 | validator | low | Verify JSON output, check all 8 lifestyle pages passed |

### Final Phase: Verification
| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Verify plugin_state.json is restored to original |
| V.2 | validator | low | Verify no regressions: `pytest tests/unit/ tests/integration/` |

### Completion Criteria
- [ ] plugin_integration_test.py exists and runs without errors
- [ ] Lifestyle plugin: all 8 pages return 200
- [ ] Lifestyle plugin: build passes in isolation
- [ ] plugin_state.json restored to original state after test
- [ ] JSON report saved to runtime/plugin-test-results/lifestyle.json
