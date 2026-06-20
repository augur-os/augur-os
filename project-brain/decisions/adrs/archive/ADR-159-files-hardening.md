---
status: Implemented
date: '2026-02-25'
deciders:
- Project team
related:
- ADR-065 (dashboard hardening workflow automation)
hub: null
tags:
- files
- hardening
superseded_by: null
---

# ADR-159: files Hardening

## Audit Summary

| # | Dimension | Score | Weight | Status | Key Finding |
|---|-----------|-------|--------|--------|-------------|
| 1 | UI Compliance | 25/100 | 12% | critical | No GlassCard usage in /files |
| 2 | Page Coverage | 0/100 | 10% | critical | No tabs defined |
| 3 | API Completeness | 100/100 | 12% | good | - |
| 4 | MCP Tool Wiring | 0/100 | 10% | critical | No actions and no MCP integration — hub is entirely passive |
| 5 | Performance | 60/100 | 10% | significant-gaps | Good static performance patterns detected |
| 6 | User Value | 16/100 | 15% | critical | 2/4 API routes have real backend logic |
| 7 | Workflows | 0/100 | 8% | critical | No actions defined — hub has no workflows |
| 8 | Cross-Hub Connectivity | 20/100 | 5% | critical | No cross-hub navigation links — hub is isolated |
| 9 | Action Buttons | 0/100 | 8% | critical | No action buttons defined — hub has no interactivity |
| 10 | Wow Effect | 0/100 | 10% | critical | Best candidate: No wow effect identified |

**Composite Score**: 24/100 (major-rebuild)

## Wow Effect: Quick Edit + Commit

> Edit a file in Monaco editor, then one-click save + git commit flow with AI-generated commit message

**Score**: 0/100

**Demo Flow**:
1. Select file from tree
2. Edit in Monaco editor with syntax highlighting
3. Click Save to write changes
4. Click Commit to trigger AI-generated commit message
5. Review and confirm commit

**Current state**: File editing exists but no commit workflow
**Gap to demo-ready**: Add save action (exists), add git commit action with AI message generation via IDE dispatch

**Cross-hub leverage**: Pulls data from dev (git operations), ai (commit message generation)

**Priority**: This is the first thing to implement in Phase 1.

## Context

Automated hardening audit of **files** (http://localhost:3000/files) on 2026-02-25.
Composite score: **24/100**.

### Issues Identified

**UI Compliance** (25/100):
- No GlassCard usage in /files
- Missing proper layout structure in /files

**Page Coverage** (0/100):
- No tabs defined

**MCP Tool Wiring** (0/100):
- No actions and no MCP integration — hub is entirely passive

**Performance** (60/100):
- Good static performance patterns detected
- Score capped at 60/100 — runtime telemetry needed for full evaluation

**User Value** (16/100):
- 2/4 API routes have real backend logic
- No pages fetch real data — all use hardcoded/mock content
- No actions defined — hub is read-only

**Workflows** (0/100):
- No actions defined — hub has no workflows

**Cross-Hub Connectivity** (20/100):
- No cross-hub navigation links — hub is isolated
- No src/lib service imports — hub doesn't consume data from other hubs
- Cross-hub data flow detected: 1 connections

**Action Buttons** (0/100):
- No action buttons defined — hub has no interactivity

**Wow Effect** (0/100):
- Best candidate: No wow effect identified
- Description: Hub has no complete actions that could serve as a demo
- Gap to demo-ready: Add at least one action with real backend, real data, and visible output

## Decision

Implement hardening in three phases, ordered by severity and user impact.

### Phase 1: Wow Effect & Critical Gaps

> **User priority**: Fix colors and top border bleed first — these are the most urgent visual issues.

**UI Compliance** (current: 25/100) — **PRIORITY**:
- Replace all hardcoded hex colors (`#0f0f23`, `#0a0a0a`, `#2a2a4a`, `#4f46e5`, `#a5b4fc`) with CSS variables (`var(--bg-primary)`, `var(--bg-secondary)`, `var(--border-primary)`, `var(--accent-primary)`, etc.)
- Fix top gradient bleed: the root layout's `content-gradient` overlay (`from-purple-900/20`, `h-96`) bleeds into the files page because page uses `margin: '-2rem'` to negate parent's `p-8` padding. Either suppress the gradient for `/files` or use a proper full-bleed layout slot.
- Wrap file tree sidebar and editor in GlassCard-style containers
- Files: `src/dashboard/app/files/page.tsx`, `src/dashboard/components/files/FileTree.tsx`, `src/dashboard/components/files/FileEditor.tsx`

**Wow Effect** (current: 0/100):
- Implement "Quick Edit + Commit" flow: edit file in Monaco → save → one-click git commit with AI-generated commit message via IDE dispatch
- Add commit action button to FileEditor toolbar (next to Save)
- Create action YAML: `plugins/admin/skills/file-manager/augur/data/actions/quick-commit.yaml` with `dispatch: ide`
- Files: `src/dashboard/components/files/FileEditor.tsx`, action YAML, API route for git operations

**Page Coverage** (current: 0/100):
- Register Files in the tab registry with at minimum a "Browse" tab
- Files is a standalone utility page (not plugin-mounted), so registration may be sidebar-only
- Files: `config/dashboard/generated/tab-registry.ts`, `src/dashboard/app/files/`

**MCP Tool Wiring** (current: 0/100):
- Wire file operations to MCP tools: `file-read`, `file-write`, `file-list`, `file-info`
- Add action YAML manifests for file operations
- Files: `plugins/admin/skills/file-manager/augur/data/actions/`

**User Value** (current: 16/100):
- Add file creation/deletion support (currently edit-only)
- Add git status indicators (modified, untracked, staged) in file tree
- Implement search/filter in file tree sidebar

**Workflows** (current: 0/100):
- Create "Quick Edit + Commit" workflow chain: edit → save → diff preview → commit
- Wire to IDE dispatch for AI commit message generation

**Cross-Hub Connectivity** (current: 20/100):
- Add "Open in Dev" link to navigate to dev hub for git operations
- Link file paths in search results (other hubs) to `/files?path=...`

**Action Buttons** (current: 0/100):
- Add action bar to FileEditor: Save, Commit, Revert, Open in IDE
- Add context menu actions on file tree items: Rename, Delete, Copy Path

### Phase 2: Completeness

**Performance** (current: 60/100):
- Good static performance patterns detected
- Score capped at 60/100 — runtime telemetry needed for full evaluation

## Consequences

### Positive

- files hub upgraded with standardized hardening across 9 dimensions
- Critical gaps addressed in Phase 1, enabling demo-ready wow effect
- Killer demo use case identified: Quick Edit + Commit

### Negative

- Requires implementation effort across 9 dimensions
- Some dimensions may require runtime testing (performance, cross-hub connectivity)

### Neutral

- Existing working features remain untouched
- Audit report stored for trend tracking

## User Notes

Priority: fix colors + border. The color mismatch (hardcoded hex vs CSS variables) and top gradient bleed are the most urgent issues — address these in Phase 1 Step 1.1 before any feature work.

**Root causes identified during audit:**
- `FileTree.tsx`: background `#0f0f23`, border `#2a2a4a`, text colors `#ccc`/`#999`/`#a5b4fc` — all hardcoded
- `FileEditor.tsx`: breadcrumb bg `#0f0f23`, border `#2a2a4a`, accent `#4f46e5` — all hardcoded
- `page.tsx`: container bg `#0a0a0a`, negative margin `-2rem` — fights with layout padding
- `layout.tsx`: `content-gradient` div (`from-purple-900/20`, `h-96`) creates visible purple band at top that shows through the file browser

## Alternatives Considered

This ADR was auto-generated by the dashboard hardening audit engine (ADR-065).
No manual alternatives were evaluated.

## References

- ADR-065: Dashboard hardening workflow automation (parent)
- Audit report: `files` hub audit
- Audit timestamp: 2026-02-25T18:05:25.047111

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.
> Auto-generated by `generate_hardening_adr.py` from ADR-065.

You are implementing **ADR-159: files Hardening**.

Read the full ADR: `docs/decisions/ADR-159-files-hardening.md`

### Offload Protocol (ADR-054)

Before dispatching each step, check if it can be offloaded to a cheap CLI:

1. Read offload config: `cat config/system/llm.yaml` -> look for `offload:` section
2. If `offload.enabled: true` AND the step's tier is `low`:
   ```bash
   python3 plugins/orchestration/skills/executor/scripts/offload_dispatcher.py \
     --task "STEP DESCRIPTION" \
     --files "TARGET_FILE_1,TARGET_FILE_2" \
     --context-files "REFERENCE_FILE_FOR_PATTERNS" \
     --work-dir $(pwd)
   ```
3. Review the JSON output
4. Record the verdict (accept / fix / escalate)
5. If `offload.enabled: false` OR tier is `medium`/`high` -> do the step yourself

### Team Orchestration

Create a team and spawn teammates to execute the plan below:

1. **Create team**: `TeamCreate(team_name="adr-159-files-hardening", description="Implementing ADR-159: files Hardening")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role, spawn a teammate:
   ```
   Task(subagent_type="general-purpose", team_name="adr-159-files-hardening", name="{role}",
        model="{tier-model}", prompt="You are '{{role}}' on the {team_name} team.
        Read your profile: .claude/agents/{{role}}.md
        Check TaskList for your assigned tasks. After each task: TaskUpdate to complete,
        SendMessage to team lead. If blocked, move to next available task.")
   ```
4. **Profile loading**: Each teammate MUST read `.claude/agents/{name}.md` for iron laws and constraints
5. **Communication**: Teammates use `SendMessage` to report completion, request reviews, and debate
6. **Dependencies**: PARALLEL phases -> spawn all at once. PIPELINE phases -> use task blocking
7. **Shutdown**: When all phases pass, send `shutdown_request` to all teammates

**Model mapping**: `low` -> haiku, `medium` -> sonnet, `high` -> opus

### Execution Plan

**Team name**: `adr-159-files-hardening`

#### Phase 1: Wow Effect & Critical Gaps
**Strategy**: PIPELINE — UI compliance first (user priority), then features

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | frontend | high | **PRIORITY** Fix UI Compliance (25→90): Replace hardcoded hex colors with CSS variables, fix top gradient bleed, wrap in GlassCard containers | `src/dashboard/app/files/page.tsx`, `src/dashboard/components/files/FileTree.tsx`, `src/dashboard/components/files/FileEditor.tsx`, `src/dashboard/app/layout.tsx` |
| 1.2 | developer | high | Fix Wow Effect (0→90): Implement Quick Edit + Commit — add commit button to FileEditor, create action YAML, wire git operations via IDE dispatch | `src/dashboard/components/files/FileEditor.tsx`, `plugins/admin/skills/file-manager/augur/data/actions/quick-commit.yaml` |
| 1.3 | developer | medium | Fix Page Coverage (0→90): Register Files in tab registry, ensure sidebar entry works | `config/dashboard/generated/tab-registry.ts`, `src/dashboard/app/files/` |
| 1.4 | devops | low | Fix MCP Tool Wiring (0→90): Create action YAMLs for file-read, file-write, file-list | `plugins/admin/skills/file-manager/augur/data/actions/` |
| 1.5 | architect | high | Fix User Value (16→90): Add file creation/deletion, git status indicators in tree, search/filter | `src/dashboard/components/files/FileTree.tsx`, `src/dashboard/app/api/files/` |
| 1.6 | developer | medium | Fix Workflows (0→90): Wire Quick Edit + Commit chain, connect save → diff → commit flow | `plugins/admin/skills/file-manager/augur/data/actions/` |
| 1.7 | developer | medium | Fix Cross-Hub Connectivity (20→90): Add "Open in Dev" link, wire file paths from search results | `src/dashboard/components/files/FileEditor.tsx`, `src/dashboard/app/files/page.tsx` |
| 1.8 | frontend | medium | Fix Action Buttons (0→90): Add action bar (Save, Commit, Revert, Open in IDE) + context menu on tree items | `src/dashboard/components/files/FileEditor.tsx`, `src/dashboard/components/files/FileTree.tsx` |

#### Phase 2: Completeness
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.9 | frontend | medium | Fix Performance (60→90): Add loading skeletons, lazy-load file tree branches, add runtime telemetry | `src/dashboard/components/files/FileTree.tsx`, `src/dashboard/components/files/FileEditor.tsx` |

#### Final Phase: Verification

| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Run all tests, verify no regressions |
| V.2 | frontend | low | Browser validation: open http://localhost:3000/files in Chrome MCP, screenshot each tab, check console for runtime errors, verify auth gates render cleanly |
| V.3 | devops | low | MCP validation: cross-check all mcp_tool refs in dashboard.yaml against mcp/__init__.py registered tools |
| V.4 | architect | low | Verify ADR intent matches implementation |

### Completion Criteria

- [ ] Wow Effect improved from 0/100 to >= 90
- [ ] UI Compliance improved from 25/100 to >= 90
- [ ] Page Coverage improved from 0/100 to >= 90
- [ ] MCP Tool Wiring improved from 0/100 to >= 90
- [ ] User Value improved from 16/100 to >= 90
- [ ] Workflows improved from 0/100 to >= 90
- [ ] Cross-Hub Connectivity improved from 20/100 to >= 90
- [ ] Action Buttons improved from 0/100 to >= 90
- [ ] Performance improved from 60/100 to >= 90
- [ ] All phases executed
- [ ] All tests pass (`pytest tests/src/`, `npm run build`)
- [ ] Browser validation: page renders in Chrome MCP with zero console errors
- [ ] MCP validation: all tool references in dashboard.yaml resolve to registered tools
- [ ] No orphaned files or broken references
- [ ] Every skill with `dashboard/` has a `dashboard.yaml` manifest (required for mount-plugins discovery)
- [ ] No structural integrity issues (`structural_issues` in audit report is empty)
- [ ] ADR-159 status updated to Accepted
