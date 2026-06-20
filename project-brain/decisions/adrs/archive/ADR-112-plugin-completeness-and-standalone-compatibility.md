---
status: Implemented
date: '2026-02-17'
deciders:
- Project owner
related:
- ADR-040 (portable plugin template standard)
- ADR-109 (filesystem-driven dashboard)
- ADR-110 (bundle overview template)
- ADR-022 (plugin standardization — already superseded by ADR-040)
hub: null
tags:
- plugin
- completeness
- standalone
- compatibility
superseded_by: null
---

# ADR-112: Plugin Completeness & Standalone Compatibility

**Supersedes**: Partial aspects of ADR-040 (profile detection logic, `hub.category` field)

## Context

### The Audit Results

A full compliance audit of 40 plugins reveals systemic gaps that prevent plugins from being extracted as standalone units:

| Status | Count | Avg Score |
|--------|-------|-----------|
| PASS (90%+) | 17 | 93% |
| WARN (70-89%) | 9 | 82% |
| FAIL (<70%) | 14 | 39% |

The 14 failures are not random — they cluster around 5 root causes that compound on each other.

### Root Cause 1: `hub.category` Required But Never Existed

Every single `dashboard.yaml` across all 40 plugins is missing `hub.category` — a field the audit mandates as required. This is because ADR-109 Decision 2 explicitly states: **"category is NEVER stored in dashboard.yaml — it's always the bundle directory name."** The audit rule contradicts the architecture.

**Impact**: ~80 false failures (2 per plugin × 40 plugins). Every plugin appears worse than it is.

**Fix**: Remove `hub.category` from audit requirements. Category is derived from the filesystem (parent bundle directory), not declared in dashboard.yaml.

### Root Cause 2: Dev Agents Misclassified as "Standard" Profile

5 dev agents (`advisor`, `developer`, `devops`, `frontend`, `validator`) have a `dashboard.yaml` but lack all dashboard files (`page.tsx`, `layout.tsx`, `loading.tsx`). The current profile detection:

```python
def detect_profile(skill_path):
    if (skill_path / "api").is_dir():
        return "full"
    elif (skill_path / "dashboard.yaml").exists():
        return "standard"
    else:
        return "minimal"
```

These agents have `dashboard.yaml` because they contribute tabs to a **src/lib hub** (`hub_id: control`) — they are not standalone dashboard skills. The detection logic can't distinguish "contributes a tab to another skill's hub" from "owns a full dashboard."

**Impact**: 5 agents scored 20-38% instead of ~90%+. Each fails 10+ structural checks that don't apply to their actual role.

**Fix**: Introduce a "contributor" sub-profile — if `dashboard.yaml` exists but `dashboard/page.tsx` does not AND the skill has no `dashboard/` directory, classify as minimal (tab contributor), not standard.

### Root Cause 3: Full-Profile Plugins Missing MCP Tools

The diagram from the user shows all plugins should have: **Skills (bundled), MCP Connectors, Sub-agents, Slash commands.** The audit confirms 9 full-profile plugins lack `mcp/tools.py`:

| Plugin | Missing MCP Files | Missing Other |
|--------|-------------------|---------------|
| observe/daemon | tools.py | api/health/route.ts, version.yaml |
| admin/updater | tools.py | loading.tsx, tests, api/health, version.yaml |
| dev/project-dev | __init__.py, tools.py | tests, api/health, version.yaml |
| finance/finance | tools.py | api/health, version.yaml |
| admin/system-cleanup | __init__.py, tools.py | layout.tsx, loading.tsx, tests, api/health, version.yaml |
| productivity/organizer | tools.py | api/health |
| venture/venture-augur | __init__.py, tools.py | — |
| home/home-automation | tools.py | api/health, version.yaml |
| lifestyle/lifestyle | __init__.py, tools.py | api/health |

Beyond full-profile, 25 of 40 plugins have **zero** MCP tool registration (`mcp=NONE`). For a system whose core philosophy is "MCP as execution gateway" (ADR-005), this means most plugins are unreachable via MCP.

**Impact**: Plugins can't be extracted as standalone MCP servers. The `skill_exporter.py` `mcp-server` target produces empty servers.

**Fix**: Every plugin MUST register at least one MCP tool. For dashboard-only plugins, this means at minimum a `get-{skill}-status` tool. For agent plugins, their capabilities must be tool-invocable.

### Root Cause 4: `print()` and `import logging` Instead of `augur_logging`

14 plugins use `print()` (some with 40+ calls) and raw `import logging` instead of the standardized `from src/lib.augur_logging import get_entity_logger`. This matters for standalone extraction because:

- `print()` output disappears when run as an MCP server (no stdout)
- `import logging` uses root logger with no structured output
- `augur_logging` provides entity-scoped, JSON-structured logs that work in both embedded and standalone modes

**Impact**: Extracted plugins lose all diagnostic output. Debug becomes impossible outside Augur.

**Fix**: Enforce `augur_logging` usage. Provide a standalone-compatible shim so extracted plugins still get structured logging without depending on Augur internals.

### Root Cause 5: Hardcoded Paths

`productivity/organizer` has 5 hardcoded `~` paths. Any extracted plugin with hardcoded paths breaks immediately on another machine.

**Impact**: Non-portable. Fails on any system except the author's.

**Fix**: Already covered by existing audit rule. Just needs enforcement via the fixes below.

### The Filesystem Architecture Pattern (ADR-109)

ADR-109 establishes that **the filesystem IS the configuration**:

- **Bundle** = directory under `plugins/` → sidebar section
- **Skill** = directory under `plugins/{bundle}/skills/` → sidebar link
- **Category** = parent bundle directory name (NOT a field in dashboard.yaml)
- **Visibility** = presence of `dashboard.yaml` (has it → nav visible; doesn't → backend-only)

This ADR aligns the plugin compliance system with ADR-109's filesystem-first architecture.

### Standalone Extraction Requirement

A plugin extracted via `skill_exporter.py` must work as:

1. **Standalone MCP server** — `python -m {skill}_mcp` starts an MCP server with all tools registered
2. **Claude Code plugin** — `.claude-plugin/` directory with tool definitions
3. **Python package** — `pip install augur-{skill}` provides importable tool functions

For this to work, every plugin needs Layer 1 completeness: SKILL.md, scripts, MCP tool registration, structured logging, and zero hardcoded paths.

## Decision

### 1. Remove `hub.category` From Audit Validation

**Rationale**: ADR-109 Decision 2 explicitly derives category from the bundle directory name. Requiring it in `dashboard.yaml` contradicts the filesystem-first architecture.

**Changes**:
- `audit.py`: Remove `dashboard_yaml_hub` check for `hub.category`
- `audit.py`: Remove `dashboard_yaml_category` validation rule
- `plugin-spec.yaml`: Remove `hub.category` from `dashboard_yaml_schema.hub` required fields
- All `dashboard.yaml` files: Do NOT add `hub.category` — it doesn't belong there

**Impact**: Clears ~80 false failures across all 40 plugins. Average scores jump 4-8%.

### 2. Fix Profile Detection for Tab Contributors

**Rationale**: Dev agents contribute tabs to a src/lib hub but don't own a standalone dashboard. Profile detection should handle this pattern.

**Current detection**:
```python
has dashboard.yaml → standard profile
```

**New detection**:
```python
has dashboard.yaml AND has dashboard/ directory → standard profile
has dashboard.yaml AND no dashboard/ directory  → minimal profile (tab contributor)
```

A skill with `dashboard.yaml` but no `dashboard/` directory is a **tab contributor** — it provides metadata for a src/lib hub (like the 5 dev agents sharing `hub_id: control`) but has no standalone pages.

**Changes**:
- `audit.py`: Update `detect_profile()` to check for `dashboard/` directory, not just `dashboard.yaml`
- `plugin-spec.yaml`: Document the tab-contributor pattern under minimal profile

**Impact**: 5 dev agents reclassified from standard → minimal. Scores jump from 20-38% to 85%+.

### 3. Mandate MCP Tool Registration for All Plugins

**Rationale**: "MCP as execution gateway" (ADR-005) means every capability should be tool-invocable. The plugin diagram shows MCP Connectors as a required component of every plugin. Without MCP tools, plugins are black boxes — invisible to MCP clients and impossible to extract as standalone servers.

**New requirement (all profiles)**:

| Profile | MCP Requirement |
|---------|----------------|
| Minimal (agent) | `mcp/__init__.py` with at least one tool (e.g., `invoke-{agent}`, `get-{agent}-status`) |
| Minimal (tab contributor) | Exempt — contributes to parent skill's MCP tools |
| Standard | `mcp/__init__.py` with at least one tool per primary capability |
| Full | `mcp/__init__.py` + `mcp/tools.py` (existing requirement) |

**What "at least one MCP tool" means per skill type**:

| Skill Type | Minimum MCP Tools | Examples |
|------------|-------------------|---------|
| Agent (advisor, developer, etc.) | `invoke-{agent}`, `get-{agent}-capabilities` | "Ask advisor for code review guidance" |
| Dashboard-only (renderer, eisenhower) | `get-{skill}-status`, `get-{skill}-data` | "Get current Eisenhower matrix items" |
| Backend service (executor, router) | `{skill}-execute`, `get-{skill}-status` | "Execute chain via executor" |
| Data app (career, finance) | Full CRUD tools (existing) | "List active jobs", "Add transaction" |

**Changes**:
- `audit.py`: Add `required_mcp` check for ALL profiles (not just full)
- `plugin-spec.yaml`: Add `mcp/__init__.py` to minimal and standard required files
- Create `mcp/__init__.py` stub for 25 plugins currently at `mcp=NONE`

**Implementation detail — MCP stub template**:

```python
# mcp/__init__.py — AUTO-GENERATED stub for {skill_name}
# Replace with real tool implementations as capabilities are added.

from augur_mcp.tools import tool

@tool
def get_{skill_name}_status() -> dict:
    """Get current status of the {skill_name} skill."""
    return {
        "skill": "{skill_name}",
        "status": "active",
        "version": "1.0.0",
    }
```

This stub satisfies the audit while providing a real (if minimal) MCP surface. Each plugin owner replaces the stub with meaningful tools over time.

### 4. Replace `print()` and Raw Logging With Standalone-Compatible Logger

**Rationale**: Extracted plugins must produce structured logs without depending on Augur internals. The current `src/lib.augur_logging` import path breaks when a plugin is extracted.

**Solution**: Two-phase approach:

**Phase A — Bulk replacement in existing code**:
Replace all `print()` calls with logger calls, and all `import logging` with `from src/lib.augur_logging import get_entity_logger`. This fixes the 14 failing plugins within Augur.

**Phase B — Standalone logging shim**:
Add a fallback import path to `augur_logging` so extracted plugins gracefully degrade:

```python
# At the top of every plugin's scripts that use logging:
try:
    from src/lib.augur_logging import get_entity_logger
except ImportError:
    # Standalone mode — augur_logging not available
    import logging
    def get_entity_logger(name):
        logger = logging.getLogger(name)
        if not logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter(
                '%(asctime)s [%(name)s] %(levelname)s: %(message)s'
            ))
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger
```

**Changes**:
- `audit.py`: Keep existing `logging_print` and `logging_import` rules (they're correct)
- 14 plugins: Replace `print()` with logger, `import logging` with `augur_logging`
- `skill_exporter.py`: Inject the standalone shim when exporting

**Impact**: All 14 plugins pass logging compliance. Extracted plugins retain structured logging.

### 5. Fix Hardcoded Paths

**Rationale**: Existing audit rule is correct but not being enforced via fixes.

**Changes**:
- `productivity/organizer`: Replace 5 hardcoded `~` paths with `get_project_root()` / `Path.home()` resolution

**Impact**: Organizer passes hardcoded_path check. Becomes portable.

## Consequences

### Positive

- **Audit accuracy** — Removing false `hub.category` failures surfaces real issues instead of noise. Average scores increase 4-8%.
- **Profile accuracy** — Tab contributors correctly classified as minimal. 5 dev agents jump from ~30% to ~90%.
- **MCP completeness** — Every plugin becomes reachable via MCP. The `skill_exporter.py mcp-server` target produces working servers.
- **Standalone readiness** — Logging shim + MCP registration + no hardcoded paths = plugins that work outside Augur.
- **Filesystem alignment** — Category derived from directory structure, not declared in config. One source of truth.

### Negative

- **25 MCP stubs to create** — Bulk generation is mechanical but needs review to ensure tool names don't collide.
- **14 plugins need print→logger migration** — Some have 40+ print() calls. Largely automated via sed/ast but needs manual review for format strings.
- **Standalone shim adds complexity** — Every exported plugin carries a logging fallback. Acceptable trade-off for portability.

### Neutral

- ADR-040 plugin profiles remain (minimal/standard/full) — this refines detection logic and adds MCP to all profiles
- ADR-109 filesystem architecture unchanged — this aligns the audit with it
- `dashboard.yaml` schema unchanged except removing the phantom `hub.category` requirement
- Bundle structure unchanged
- Export targets (claude-code, mcp-server, python-package) unchanged

## Implementation Order

```
Phase 1: Audit Rule Fixes (PARALLEL — no code generation, just rule changes)
├── Step 1: Remove hub.category from audit.py validation (delete dashboard_yaml_hub category check + dashboard_yaml_category rule)
├── Step 2: Remove hub.category from plugin-spec.yaml required hub fields
├── Step 3: Fix detect_profile() — check for dashboard/ directory, not just dashboard.yaml
└── Step 4: Fix organizer hardcoded paths (5 replacements)

Phase 2: MCP Tool Registration (depends on Phase 1 for accurate audit baseline)
├── Step 5: Create mcp/__init__.py stub template
├── Step 6: Generate mcp/__init__.py stubs for 25 plugins at mcp=NONE
│           Plugins: renderer, scraper, settings, system-cleanup, ai_bridge,
│           consulting/client-ai-consulting, consulting/client-smb-design,
│           consulting/linkedin-writer, core/executor, core/router, core/swarm,
│           creative/content, dev/advisor, dev/developer, dev/devops, dev/frontend,
│           dev/project-dev, dev/validator, enterprise/enterprise, growth/growth,
│           lifestyle/lifestyle, observe/observe, productivity/eisenhower,
│           venture/venture-augur, wealth/wealth
├── Step 7: Add mcp/tools.py for full-profile plugins missing it
│           Plugins: daemon, updater, finance, system-cleanup, organizer,
│           venture-augur, home-automation, lifestyle
├── Step 8: Add mcp/__init__.py for full-profile plugins missing it
│           Plugins: project-dev, system-cleanup, venture-augur, lifestyle
└── Step 9: Update audit.py to require mcp/__init__.py for all profiles

Phase 3: Logging Compliance (PARALLEL with Phase 2)
├── Step 10: Bulk replace print() → logger in 14 plugins
│            Priority order by severity:
│            observe/daemon (40+), observe/observe (30+), dev/validator (30+),
│            dev/advisor (24+), dev/devops (20+), core/executor (15+),
│            admin/updater (11+), dev/developer (10+), dev/frontend (15+),
│            ai/ai_bridge (10+), finance/finance (13+),
│            ai/knowledge (4+), ai/mcp-app-factory (2+), productivity/organizer (0)
├── Step 11: Replace import logging → augur_logging in same 14 plugins
└── Step 12: Add standalone logging shim to skill_exporter.py export pipeline

Phase 4: Missing Structural Files (depends on Phase 2)
├── Step 13: Add api/health/route.ts to 7 full-profile plugins missing it
│            Plugins: daemon, updater, finance, system-cleanup, organizer,
│            home-automation, lifestyle
├── Step 14: Add version.yaml to 6 full-profile plugins missing it
│            Plugins: daemon, updater, project-dev, finance, system-cleanup,
│            home-automation
├── Step 15: Add missing dashboard files (layout.tsx, loading.tsx) to
│            updater and system-cleanup
└── Step 16: Add test stubs for plugins missing tests
│            Plugins: updater, project-dev, system-cleanup, observe/observe,
│            wealth/wealth

Phase 5: Verification (depends on all)
├── Step 17: Run audit.py --json — verify 0 plugins at FAIL status
├── Step 18: Verify all 40 plugins have mcp/__init__.py (except tab contributors)
├── Step 19: Verify 0 print() calls in library code (grep -r "print(" plugins/*/skills/*/scripts/)
├── Step 20: Verify 0 hardcoded paths (grep -r "/Users/" plugins/)
├── Step 21: Test standalone extraction — export career plugin as mcp-server, verify it starts
└── Step 22: Test profile detection — verify dev agents classified as minimal
```

## Completion Criteria

- [ ] `hub.category` removed from audit validation — zero false failures from missing category
- [ ] Profile detection fixed — dev agents (advisor, developer, devops, frontend, validator) score 85%+
- [ ] All 40 plugins have `mcp/__init__.py` (except tab contributors that don't own standalone dashboards)
- [ ] All full-profile plugins have `mcp/tools.py`, `api/health/route.ts`, `version.yaml`
- [ ] Zero `print()` calls in plugin library code
- [ ] Zero `import logging` without `augur_logging` wrapper
- [ ] Zero hardcoded `/Users/` paths
- [ ] `audit.py --json` returns 0 FAIL-status plugins
- [ ] At least one plugin successfully exports as standalone MCP server and starts
- [ ] Standalone logging shim integrated into `skill_exporter.py`

## Alternatives Considered

### Alternative 1: Remove MCP Requirement From Non-Full Profiles

Only require MCP tools for full-profile plugins (apps with APIs). Agent and dashboard-only plugins stay MCP-free.

**Rejected because**: This contradicts ADR-005 "MCP as execution gateway." If a capability exists but isn't MCP-invocable, it can't be composed, tested, or extracted. The whole point of MCP is universal tool access. A `get-status` stub is trivial to add and establishes the pattern.

### Alternative 2: Add `hub.category` to All dashboard.yaml Files

Instead of removing the audit rule, add the category field to all 40 plugins.

**Rejected because**: ADR-109 explicitly decided category derives from the filesystem. Adding it to dashboard.yaml creates a dual-source-of-truth problem — when you `git mv` a plugin to a new bundle, the dashboard.yaml category is stale. The filesystem IS the truth.

### Alternative 3: Create a "sub-agent" Profile Instead of Fixing Tab Contributors

Add a fourth profile specifically for skills that contribute to src/lib hubs.

**Rejected because**: Over-engineering. The tab-contributor pattern is just a minimal plugin with a `dashboard.yaml` for hub metadata. Adding a fourth profile adds complexity for a case that's handled by one extra condition in `detect_profile()`.

### Alternative 4: Skip Standalone Logging Shim — Just Use augur_logging Everywhere

Don't add the fallback. Extracted plugins simply require augur_logging as a dependency.

**Rejected because**: This defeats the purpose of standalone extraction. A plugin exported as a Python package shouldn't drag in the entire Augur logging infrastructure. The shim is 10 lines and provides graceful degradation.

## References

- ADR-005: MCP as execution gateway — all tool interactions go through MCP
- ADR-040: Portable plugin template standard — profile definitions, two-layer architecture
- ADR-109: Filesystem-driven dashboard — category derived from bundle directory, not dashboard.yaml
- ADR-110: Bundle overview template — overview.yaml at bundle level
- `plugins/ai/skills/mcp-app-factory/scripts/audit.py` — Compliance audit script (to be updated)
- `plugins/ai/skills/mcp-app-factory/plugin-spec.yaml` — Plugin specification (to be updated)
- `plugins/ai/skills/mcp-app-factory/scripts/skill_exporter.py` — Export tool (to be updated)

## Implementation Prompt

> Paste this into Claude Code to execute this ADR.

You are implementing **ADR-112: Plugin Completeness & Standalone Compatibility**.

Read the full ADR: `docs/decisions/ADR-112-plugin-completeness-and-standalone-compatibility.md`

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
4. Record the verdict
5. If `offload.enabled: false` OR tier is `medium`/`high` → do the step yourself

### Team Orchestration

Create a team and spawn teammates:

1. **Create team**: `TeamCreate(team_name="adr-112-plugin-completeness", description="Implementing ADR-112: Plugin Completeness & Standalone Compatibility")`
2. **Create tasks** from the Implementation Order phases
3. **Spawn teammates**:
   - `developer` (sonnet) — audit rule fixes, MCP stub generation, structural files
   - `devops` (sonnet) — logging migration, exporter updates
   - `validator` (haiku) — verification phase

**Model mapping**: `low` → haiku, `medium` → sonnet, `high` → opus

### Execution Plan

**Team name**: `adr-112-plugin-completeness`

#### Phase 1: Audit Rule Fixes
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | medium | In `audit.py`: (1) Remove the `dashboard_yaml_hub` check that validates `hub.category is required`. (2) Remove the `dashboard_yaml_category` rule that validates category enum values. (3) Update `detect_profile()`: if `dashboard.yaml` exists but `dashboard/` directory does NOT exist, classify as `minimal` (tab contributor) instead of `standard`. | `plugins/ai/skills/mcp-app-factory/scripts/audit.py` |
| 1.2 | developer | low | In `plugin-spec.yaml`: Remove `hub.category` from `dashboard_yaml_schema.hub` required fields. Add documentation note: "Category is derived from bundle directory name per ADR-109. Not stored in dashboard.yaml." Add `tab_contributor` documentation under minimal profile. | `plugins/ai/skills/mcp-app-factory/plugin-spec.yaml` |
| 1.3 | developer | low | In `productivity/organizer`: Replace all 5 hardcoded `~` paths with dynamic resolution using `Path.home()` or `get_project_root()`. Search all `.py` and `.ts` files in the skill directory. | `plugins/productivity/skills/organizer/` |

#### Phase 2: MCP Tool Registration
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | medium | Create MCP stub template. Then generate `mcp/__init__.py` for all 25 plugins at `mcp=NONE` that are NOT tab contributors. Each stub registers a `get-{skill_name}-status` tool. Use the tool decorator pattern from existing plugins (reference `plugins/ai/skills/knowledge/augur/__init__.py`). Skip tab-contributor dev agents (advisor, developer, devops, frontend, validator) — they are exempt. | 25 new `mcp/__init__.py` files |
| 2.2 | developer | medium | For 8 full-profile plugins missing `mcp/tools.py`: create `tools.py` files with at least one meaningful tool per plugin. Reference each plugin's `scripts/` directory to understand what capabilities exist and expose them as MCP tools. Plugins: daemon, updater, finance, system-cleanup, organizer, venture-augur, home-automation, lifestyle. | 8 new `mcp/tools.py` files |
| 2.3 | developer | low | For 4 full-profile plugins missing `mcp/__init__.py`: create init files that import and register tools from `tools.py`. Plugins: project-dev, system-cleanup, venture-augur, lifestyle. | 4 new `mcp/__init__.py` files |
| 2.4 | developer | low | Update `audit.py`: add `required_mcp` check requiring `mcp/__init__.py` for all profiles. Add exemption for tab contributors (skills with `dashboard.yaml` but no `dashboard/` directory). | `plugins/ai/skills/mcp-app-factory/scripts/audit.py` |

#### Phase 3: Logging Compliance
**Strategy**: PARALLEL with Phase 2

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | devops | medium | Bulk replace `print()` → logger calls in 14 plugins. For each plugin: (1) Add `from src/lib.augur_logging import get_entity_logger` at top. (2) Add `logger = get_entity_logger("{skill_name}")` after imports. (3) Replace `print(...)` with `logger.info(...)` (or `.debug`/`.warning`/`.error` based on context). (4) Replace `import logging` with the augur_logging import. Priority: daemon (40+), observe (30+), validator (30+), advisor (24+), devops (20+), executor (15+), frontend (15+), updater (11+), developer (10+), ai_bridge (10+), finance (13+), knowledge (4+), mcp-app-factory (2+). | 14 plugins' `scripts/` directories |
| 3.2 | devops | medium | Add standalone logging shim to `skill_exporter.py`. When exporting a plugin, inject a `_logging_compat.py` file that provides `get_entity_logger()` as a standalone fallback. Update exported plugin imports to use `try: from src/lib.augur_logging ... except ImportError: from ._logging_compat ...` pattern. | `plugins/ai/skills/mcp-app-factory/scripts/skill_exporter.py` |

#### Phase 4: Missing Structural Files
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 4.1 | developer | low | Add `api/health/route.ts` to 7 full-profile plugins. Use standard health check pattern: export GET handler that returns `{ status: "ok", skill: "{name}", timestamp: ISO }`. Plugins: daemon, updater, finance, system-cleanup, organizer, home-automation, lifestyle. | 7 new `api/health/route.ts` files |
| 4.2 | developer | low | Add `version.yaml` to 6 full-profile plugins. Fields: `version: 1.0.0`, `updated: 2026-02-17`, `profile: full`. Plugins: daemon, updater, project-dev, finance, system-cleanup, home-automation. | 6 new `version.yaml` files |
| 4.3 | developer | low | Add missing `dashboard/loading.tsx` to updater and system-cleanup. Add missing `dashboard/layout.tsx` to system-cleanup. Use standard skeleton pattern from existing plugins (reference career or health). | 3 new dashboard files |
| 4.4 | developer | low | Add minimal test stubs (`tests/test_{skill}.py`) for plugins missing tests: updater, project-dev, system-cleanup, observe, wealth. Each stub has one test that imports the skill's main module and asserts it loads. | 5 new test files |

#### Phase 5: Verification
**Strategy**: PIPELINE

| Step | Agent | Tier | Task |
|------|-------|------|------|
| 5.1 | validator | low | Run `python audit.py --json`. Parse output. Assert: 0 plugins with status=fail. Report any remaining failures with details. |
| 5.2 | validator | low | Verify all 40 plugins have `mcp/__init__.py` (except 5 tab-contributor dev agents). Run: `find plugins/*/skills/*/mcp/__init__.py \| wc -l` — expect 35+. |
| 5.3 | validator | low | Verify 0 `print()` in library code: `grep -r "print(" plugins/*/skills/*/scripts/ --include="*.py" \| grep -v "# noqa" \| grep -v "test_"`. Expect 0 matches. |
| 5.4 | validator | low | Verify 0 hardcoded paths: `grep -r "/Users/" plugins/ --include="*.py" --include="*.ts" \| grep -v node_modules \| grep -v __pycache__`. Expect 0 matches. |
| 5.5 | validator | medium | Test standalone extraction: Run `python skill_exporter.py --target mcp-server --name career --output /tmp/career-mcp`. Verify output contains `server.py`, `mcp/`, logging shim. Verify `python /tmp/career-mcp/server.py --help` doesn't crash. |
| 5.6 | validator | low | Verify profile detection: Run `python audit.py --json`, parse, assert advisor/developer/devops/frontend/validator all have `profile: minimal` and `score >= 85`. |

### Completion Criteria

- [ ] Zero `hub.category` false failures in audit
- [ ] Dev agents (advisor, developer, devops, frontend, validator) all score 85%+
- [ ] 35+ plugins have `mcp/__init__.py` (all except tab contributors)
- [ ] All full-profile plugins have `mcp/tools.py`, `api/health/route.ts`, `version.yaml`
- [ ] Zero `print()` in plugin library code
- [ ] Zero hardcoded `/Users/` paths
- [ ] `audit.py --json` returns 0 FAIL-status plugins
- [ ] Standalone MCP server export works for at least 1 plugin

### How to Run
```
# Option 1: Use /implement-adr
/implement-adr docs/decisions/ADR-112-plugin-completeness-and-standalone-compatibility.md

# Option 2: Paste the Implementation Prompt into Claude Code
```
