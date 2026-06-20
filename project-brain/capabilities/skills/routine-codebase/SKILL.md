---
name: routine-codebase
x-augur-type: autoloop
x-augur-group: augur_autoloops
x-augur-release: mvp
x-augur-license: MIT
description: Use when Augur needs codebase validation across tests, builds, lint, formatting, dashboard page routes,
  API/MCP wiring, or UI interaction quality after code changes or nightly drift.
x-augur-tab: codebase
x-augur-tags:
- routine
- autoloop
- codebase
- testing
- quality
- wiring
x-augur-dashboard-pages: []
x-augur-data-dir: routine-codebase
x-augur-routines:
- id: testing
  execution: tiered
  policy: adaptive
  callable: ../daemon/scripts/routine_orchestrator/orchestrator.py
  loop: testing
  hub: adaptive
  description: Test and build verification routine.
- id: code-quality
  execution: tiered
  policy: adaptive
  callable: ../daemon/scripts/routine_orchestrator/orchestrator.py
  loop: code-quality
  hub: adaptive
  description: Formatting, linting, and code health routine.
- id: ui-quality
  execution: tiered
  policy: adaptive
  callable: ../daemon/scripts/routine_orchestrator/orchestrator.py
  loop: ui-quality
  hub: adaptive
  description: UI and interaction quality routine.
x-augur-commands:
- id: auto-e2e-actions
  type: workflow
  visibility: auto
  description: Validate dashboard actions through MCP writes and round-trip mutation flows
  callable: scripts/e2e_actions.py
  protocol: scan-fix
  loop:
    name: testing
    tier: 3
    trigger: nightly
- id: auto-e2e-pipeline
  type: workflow
  visibility: auto
  description: Validate the vault-to-dashboard data pipeline and pinpoint the failing stage
  callable: scripts/e2e_pipeline.py
  protocol: scan-fix
  loop:
    name: testing
    tier: 3
    trigger: nightly
- id: auto-format
  type: workflow
  visibility: auto
  description: Run Prettier against the source tree and commit safe formatting repairs.
  callable: scripts/format.py
  protocol: scan-fix
  loop:
    name: code-quality
    tier: 1
    trigger: nightly
- id: auto-lint
  type: workflow
  visibility: auto
  description: Run ESLint auto-fix, then escalate unresolved diagnostics for focused repair.
  callable: scripts/lint.py
  protocol: scan-fix
  loop:
    name: code-quality
    tier: 1
    trigger: nightly
- id: auto-test-api
  type: workflow
  visibility: auto
  description: Validate dashboard API route health, classify failures, and apply safe path
    repairs
  callable: scripts/test_api_ops.py
  protocol: scan-fix
  loop:
    name: testing
    tier: 2
    trigger: nightly
- id: auto-test-build
  type: workflow
  visibility: auto
  description: Verify dashboard builds without errors
  callable: scripts/test_build_ops.py
  protocol: scan-fix
  loop:
    name: testing
    tier: 0
    trigger: nightly
- id: auto-test-dashboard
  type: workflow
  visibility: auto
  description: Run Jest dashboard test suite with hub scoping
  callable: scripts/test_dashboard_ops.py
  protocol: scan-fix
  loop:
    name: testing
    tier: 1
    trigger: nightly
- id: auto-test-links
  type: workflow
  visibility: auto
  description: Scan all dashboard pages for broken internal links and unreachable routes
  callable: scripts/test_links_ops.py
  protocol: scan-fix
  loop:
    name: testing
    tier: 2
    trigger: nightly
- id: auto-test-mcp
  type: workflow
  visibility: auto
  description: Verify MCP server handshake and tool listing
  callable: scripts/test_mcp_ops.py
  protocol: scan-fix
  loop:
    name: testing
    tier: 1
    trigger: nightly
- id: auto-test-mcp-commands
  type: workflow
  visibility: auto
  description: Categorized invocation test of all Augur MCP tools
  callable: scripts/test_mcp_commands_ops.py
  protocol: scan-fix
  loop:
    name: testing
    tier: 3
    trigger: nightly
- id: auto-test-onboarding-probes
  type: workflow
  visibility: auto
  description: Run setup-completeness probes against fixture vaults
  callable: scripts/onboarding_probes_ops.py
  protocol: scan-fix
  loop:
    name: testing
    tier: 1
    trigger: nightly
- id: auto-test-pages
  type: workflow
  visibility: auto
  description: Validate dashboard page routes resolve without errors
  callable: scripts/test_pages_ops.py
  protocol: scan-fix
  loop:
    name: testing
    tier: 2
    trigger: nightly
- id: auto-test-pytest
  type: workflow
  visibility: auto
  description: Run Python test suite with hub scoping
  callable: scripts/test_pytest_ops.py
  protocol: scan-fix
  loop:
    name: testing
    tier: 1
    trigger: nightly
- id: auto-test-webmcp
  type: workflow
  visibility: auto
  description: Validate WebMCP tool registration, execution, and state reporting across all
    phases
  callable: scripts/webmcp_ops.py
  protocol: scan-fix
  loop:
    name: testing
    tier: 3
    trigger: nightly
- id: auto-ui-quality
  type: workflow
  visibility: auto
  description: Nightly UI/UX quality audit with accessibility, interaction, and responsive
    checks.
  callable: scripts/ui_quality.py
  protocol: scan-fix
  loop:
    name: ui-quality
    tier: 2
    trigger: nightly
- id: auto-yaml-lint
  type: workflow
  visibility: auto
  description: Lint YAML config for syntax, formatting, and structural drift.
  callable: scripts/yaml_lint_ops.py
  protocol: scan-fix
  loop:
    name: hardening
    tier: 1
    trigger: nightly
x-augur-config:
  contributions:
    commands:
    - id: auto-api-wiring
      type: workflow
      visibility: auto
      description: Validate API route toolName references and detect bypasses
      callable: scripts/api_wiring_ops.py
      protocol: scan-fix
    - id: auto-block-wiring
      type: workflow
      visibility: auto
      description: Validate block data pipelines and route/tool wiring
      callable: scripts/block_wiring.py
      protocol: scan-fix
    - id: auto-dead-api
      type: workflow
      visibility: auto
      description: Detect orphan API routes and MCP tools
      callable: scripts/dead_api_ops.py
      protocol: scan-fix
    - id: auto-dead-ui
      type: workflow
      visibility: auto
      description: Detect unwired UI elements and broken interaction targets
      callable: scripts/dead_ui_ops.py
      protocol: scan-fix
    - id: auto-dead-wiring
      type: workflow
      visibility: auto
      description: Cross-check declarations against implementations and detect dead wiring
      callable: scripts/dead_wiring_ops.py
      protocol: scan-fix
    - id: auto-e2e-actions
      type: workflow
      visibility: auto
      description: Validate dashboard actions through MCP writes and round-trip mutation flows
      callable: scripts/e2e_actions.py
      protocol: scan-fix
    - id: auto-e2e-pipeline
      type: workflow
      visibility: auto
      description: Validate the vault-to-dashboard data pipeline and pinpoint the failing
        stage
      callable: scripts/e2e_pipeline.py
      protocol: scan-fix
    - id: auto-format
      type: workflow
      visibility: auto
      description: Run Prettier against the source tree and commit safe formatting repairs.
      callable: scripts/format.py
      protocol: scan-fix
    - id: auto-lint
      type: workflow
      visibility: auto
      description: Run ESLint auto-fix, then escalate unresolved diagnostics for focused repair.
      callable: scripts/lint.py
      protocol: scan-fix
    - id: auto-page-mounts
      type: workflow
      visibility: auto
      description: Verify mounted page declarations have a source owner
      callable: scripts/page_mounts.py
      protocol: scan-fix
    - id: auto-tab-registry
      type: workflow
      visibility: auto
      description: Validate generated tab registry entries resolve to pages or catch-all routes
      callable: scripts/tab_registry.py
      protocol: scan-fix
    - id: auto-tabs
      type: workflow
      visibility: auto
      description: Score page maturity and reorder hub tabs
      callable: scripts/tabs.py
      protocol: scan-fix
    - id: auto-test-api
      type: workflow
      visibility: auto
      description: Validate dashboard API route health, classify failures, and apply safe
        path repairs
      callable: scripts/test_api_ops.py
      protocol: scan-fix
    - id: auto-test-build
      type: workflow
      visibility: auto
      description: Verify dashboard builds without errors
      callable: scripts/test_build_ops.py
      protocol: scan-fix
    - id: auto-test-dashboard
      type: workflow
      visibility: auto
      description: Run Jest dashboard test suite with hub scoping
      callable: scripts/test_dashboard_ops.py
      protocol: scan-fix
    - id: auto-test-links
      type: workflow
      visibility: auto
      description: Scan all dashboard pages for broken internal links and unreachable routes
      callable: scripts/test_links_ops.py
      protocol: scan-fix
    - id: auto-test-mcp
      type: workflow
      visibility: auto
      description: Verify MCP server handshake and tool listing
      callable: scripts/test_mcp_ops.py
      protocol: scan-fix
    - id: auto-test-mcp-commands
      type: workflow
      visibility: auto
      description: Categorized invocation test of all Augur MCP tools
      callable: scripts/test_mcp_commands_ops.py
      protocol: scan-fix
    - id: auto-test-onboarding-probes
      type: workflow
      visibility: auto
      description: Run setup-completeness probes against fixture vaults
      callable: scripts/onboarding_probes_ops.py
      protocol: scan-fix
    - id: auto-test-pages
      type: workflow
      visibility: auto
      description: Validate dashboard page routes resolve without errors
      callable: scripts/test_pages_ops.py
      protocol: scan-fix
    - id: auto-test-pytest
      type: workflow
      visibility: auto
      description: Run Python test suite with hub scoping
      callable: scripts/test_pytest_ops.py
      protocol: scan-fix
    - id: auto-test-webmcp
      type: workflow
      visibility: auto
      description: Validate WebMCP tool registration, execution, and state reporting across
        all phases
      callable: scripts/webmcp_ops.py
      protocol: scan-fix
    - id: auto-ui-quality
      type: workflow
      visibility: auto
      description: Nightly UI/UX quality audit with accessibility, interaction, and responsive
        checks.
      callable: scripts/ui_quality.py
      protocol: scan-fix
    - id: auto-view-schema
      type: workflow
      visibility: auto
      description: Validate runtime view YAML files and block layout wiring
      callable: scripts/view_schema.py
      protocol: scan-fix
    - id: auto-yaml-lint
      type: workflow
      visibility: auto
      description: Lint YAML config for syntax, formatting, and structural drift.
      callable: scripts/yaml_lint_ops.py
      protocol: scan-fix
---

# routine-codebase

Codebase correctness routines keep Augur's test, build, lint, formatting,
dashboard route, API, MCP, and UI-quality surfaces honest after code changes.
Use this skill to choose the right auto-command and to interpret its findings
without bypassing the repo's loop-driven workflow.

## When to use

Use `routine-codebase` when a finding mentions tests, build health, lint,
formatting, route resolution, API route wiring, block data flow, MCP handshakes,
dashboard action round trips, or UI interaction quality.

Do not use it for platform health, dependency audits, vault hygiene, security
audits, or hub/skill coverage unless the reported defect lands in a codebase
test or wiring command listed below.

## Command map

Start from the command document that matches the failing surface:

- [commands/auto-api-wiring.md](commands/auto-api-wiring.md)
- [commands/auto-block-wiring.md](commands/auto-block-wiring.md)
- [commands/auto-dead-api.md](commands/auto-dead-api.md)
- [commands/auto-dead-ui.md](commands/auto-dead-ui.md)
- [commands/auto-dead-wiring.md](commands/auto-dead-wiring.md)
- [commands/auto-e2e-actions.md](commands/auto-e2e-actions.md)
- [commands/auto-e2e-pipeline.md](commands/auto-e2e-pipeline.md)
- [commands/auto-format.md](commands/auto-format.md)
- [commands/auto-lint.md](commands/auto-lint.md)
- [commands/auto-page-mounts.md](commands/auto-page-mounts.md)
- [commands/auto-tab-registry.md](commands/auto-tab-registry.md)
- [commands/auto-tabs.md](commands/auto-tabs.md)
- [commands/auto-test-api.md](commands/auto-test-api.md)
- [commands/auto-test-build.md](commands/auto-test-build.md)
- [commands/auto-test-dashboard.md](commands/auto-test-dashboard.md)
- [commands/auto-test-links.md](commands/auto-test-links.md)
- [commands/auto-test-mcp-commands.md](commands/auto-test-mcp-commands.md)
- [commands/auto-test-mcp.md](commands/auto-test-mcp.md)
- [commands/auto-test-pages.md](commands/auto-test-pages.md)
- [commands/auto-test-pytest.md](commands/auto-test-pytest.md)
- [commands/auto-test-webmcp.md](commands/auto-test-webmcp.md)
- [commands/auto-ui-quality.md](commands/auto-ui-quality.md)
- [commands/auto-view-schema.md](commands/auto-view-schema.md)
- [commands/auto-yaml-lint.md](commands/auto-yaml-lint.md)

The command docs define user-facing behavior and help text. The deterministic
implementations live in `scripts/`; prefer those scripts or the routine
orchestrator over ad hoc shell snippets when investigating a bucket.

## Scope

Use this routine skill for codebase validation, quality checks, and wiring scans previously split across retired test, quality, and wiring loop skills.

## What it checks

- **Build and test health** — dashboard build, Jest dashboard tests, Python
  tests, API smoke checks, page resolution, link checks, and onboarding probes.
- **Source quality** — formatting, ESLint repair, YAML syntax and structural
  lint, tab registry checks, and runtime view schema validation.
- **Dashboard wiring** — API route tool names, block data pipelines, page mount
  declarations, dead API/UI/wiring detection, and stale generated tab entries.
- **MCP and action flows** — MCP server handshake, categorized MCP command
  invocation, WebMCP registration, dashboard action writes, and full
  vault-to-dashboard pipeline checks.
- **UI quality** — accessibility, interaction, responsive behavior, and visual
  polish checks for dashboard pages that changed.

## Workflow

Run the codebase loop as a scan-fix process. Keep fixes local to the failing
surface, then prove the user-facing value with the same class of check that
reported the defect.

- Step 1: Identify the exact command id, file path, and surface from the
  auto-command bucket or routine issue.
- Step 2: Read the matching file in `commands/` for the command contract, then
  inspect the callable in `scripts/` only as needed.
- Step 3: Reproduce the finding with the auto-command bucket, routine
  orchestrator, or the script-specific scan mode. Do not replace loop commands
  with raw `pnpm`, `pytest`, or one-off dashboard probes.
- Step 4: Apply the smallest fix in the owned source file. For generated
  dashboard copies, edit the owning skill source or YAML declaration instead.
- Step 5: Re-run the relevant scan or command against the real repository,
  dashboard route set, MCP catalog, or vault-backed data flow named by the
  finding.
- Step 6: Report remaining gaps with the command id, concrete output, and the
  user-facing value still blocked.

## Verification checklist

- [ ] The reported command id maps to one of this skill's command documents.
- [ ] The edit touched only the owning source, command, script, or test fixture
  required by the finding.
- [ ] Generated dashboard files were not patched directly when an owning skill
  or page YAML exists.
- [ ] Verification used the relevant auto-loop command, scan mode, or routine
  path rather than a weaker HTTP 200, lint-only, or dry mechanical check.
- [ ] Browser-touching changes include client-side browser or screenshot
  evidence when the dashboard UI, generated pages, or registries changed.
- [ ] The final report names the real input checked and any empty, stale, or
  still-failing state.

## Examples

```text
Finding: auto-test-pages reports /workspace/inbox fails route resolution.
Use: commands/auto-test-pages.md, then scripts/test_pages_ops.py scan output.
Fix: repair the owning page source or generated page declaration.
Verify: rerun the page command and load the affected route in a browser if UI changed.
```

```text
Finding: auto-api-wiring reports a stale toolName in an API route.
Use: commands/auto-api-wiring.md and scripts/api_wiring_ops.py.
Fix: update the route or skill-owned YAML declaration that names the MCP tool.
Verify: rerun the wiring scan and show the route now resolves the live tool.
```

## References

- Command contracts live under `commands/`, one Markdown file per auto-command.
- Deterministic scan and fix implementations live under `scripts/`.
- Add heavier operator notes under `references/` only when a future routine
  needs detail that would bloat this SKILL.md.
