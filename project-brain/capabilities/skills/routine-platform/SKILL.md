---
name: routine-platform
x-augur-type: autoloop
x-augur-group: augur_autoloops
x-augur-release: mvp
x-augur-license: MIT
description: Scheduled platform-health routines for maintaining Augur's git, dependency, page-health, MCP, observability, plugin-lint, filesystem, and runtime-parity surfaces after releases, refactors, scheduled drift checks, or suspected infrastructure regressions.
x-augur-tab: platform
x-augur-tags:
- routine
- autoloop
- platform
- observability
- git
- ops
x-augur-dashboard-pages: []
x-augur-data-dir: routine-platform
x-augur-commands:
- id: auto-agent-config-parity
  type: workflow
  visibility: auto
  description: Detect Claude-only enforcement gates that lack a cross-agent peer in `.githooks/` or `.pre-commit-config.yaml`, so behavior gates do not silently bypass non-Claude clients.
  callable: scripts/agent_config_parity.py
  protocol: scan-fix
  loop:
    name: hardening
    tier: 2
    trigger: nightly
- id: auto-dependency-audit
  type: workflow
  visibility: auto
  description: Scan dependency vulnerabilities and apply conservative audit fixes at higher hardening difficulty.
  callable: scripts/dependency_audit.py
  protocol: scan-fix
  loop:
    name: hardening
    tier: 3
    trigger: nightly
- id: auto-dir-alignment
  type: workflow
  visibility: auto
  description: Validate first-level dirs in managed locations against skill names and reserved entries.
  callable: scripts/dir_alignment_ops.py
  protocol: scan-fix
  loop:
    name: hardening
    tier: 2
    trigger: nightly
- id: auto-file-growth
  type: workflow
  visibility: auto
  description: Detect runaway file generation, duplicate content, and abnormal directory growth.
  callable: scripts/file_growth_ops.py
  protocol: scan-fix
  loop:
    name: self-heal
    tier: 0
    trigger: nightly
- id: auto-repo-pollution
  type: workflow
  visibility: auto
  description: Detect working-tree junk invisible to git (gitignored binaries, OS junk, orphan pycache, empty dirs) and remove expired session artifacts.
  callable: scripts/repo_pollution_ops.py
  protocol: scan-fix
  loop:
    name: self-heal
    tier: 0
    trigger: nightly
- id: auto-flow-optimizer
  type: workflow
  visibility: auto
  description: Detect dispatch mode mismatches across actions and write a flow optimization report.
  callable: scripts/flow_optimizer.py
  protocol: scan-fix
  loop:
    name: hardening
    tier: 5
    trigger: nightly
- id: auto-friction-audit
  type: workflow
  visibility: auto
  description: Mine recent AI-client session transcripts for recurring agent friction (unreachable tools, tool-discovery misses, hook false-fires, ad-hoc repo-root script workarounds, repeated command failures) and write a ranked report with remedy proposals. Self-improving — propose by default, auto-apply only allowlisted low-risk fixes on a branch.
  callable: scripts/friction_audit.py
  protocol: scan-fix
  loop:
    name: self-heal
    tier: 1
    trigger: nightly
- id: auto-fs-bypass
  type: workflow
  visibility: auto
  description: Detect direct filesystem access in API routes that bypass MCP-first policy.
  callable: scripts/fs_bypass.py
  protocol: scan-fix
  loop:
    name: hardening
    tier: 4
    trigger: nightly
- id: auto-git-health
  type: workflow
  visibility: auto
  description: Monitor repository object growth and run git garbage collection when needed.
  callable: scripts/git_health.py
  protocol: scan-fix
  loop:
    name: code-quality
    tier: 1
    trigger: nightly
- id: auto-inspect
  type: workflow
  visibility: auto
  description: Inspect observability dimensions and context window footprint.
  callable: scripts/inspect_ops.py
  protocol: scan-fix
  loop:
    name: observability
    tier: 3
    trigger: nightly
- id: auto-logs
  type: workflow
  visibility: auto
  description: Archive old logs and maintain runtime log hygiene.
  callable: scripts/logs.py
  protocol: scan-fix
  loop:
    name: code-quality
    tier: 1
    trigger: nightly
- id: auto-mcp-health-audit
  type: workflow
  visibility: auto
  description: Audit MCP route wiring, runtime health, and safe auto-fixes.
  callable: scripts/mcp_health_audit.py
  protocol: scan-fix
  loop:
    name: testing
    tier: 2
    trigger: nightly
- id: auto-page-health
  type: workflow
  visibility: auto
  description: Verify dashboard page MCP tool references and auto-fix YAML tool names.
  callable: scripts/page_health.py
  protocol: scan-fix
  loop:
    name: page-health
    tier: 1
    trigger: nightly
- id: auto-perf-profile
  type: workflow
  visibility: auto
  description: Check response times, disk bloat, stale files, cache size, and performance regressions.
  callable: scripts/perf_profile.py
  protocol: scan-fix
  loop:
    name: observability
    tier: 2
    trigger: nightly
- id: auto-plugin-lint
  type: workflow
  visibility: auto
  description: Fix plugin structural issues with AI-assisted lint and validation.
  callable: scripts/plugin_lint.py
  protocol: scan-fix
  loop:
    name: hardening
    tier: 3
    trigger: nightly
- id: auto-repo-sync
  type: workflow
  visibility: auto
  description: Check repos for uncommitted and unpushed changes, then sync at higher difficulty.
  callable: scripts/repo_sync.py
  protocol: scan-fix
  loop:
    name: observability
    tier: 1
    trigger: nightly
- id: auto-skill-root-migration
  type: workflow
  visibility: auto
  description: Enforce the shared/private vault skill-root migration contract.
  callable: scripts/skill_root_migration_ops.py
  protocol: scan-fix
  loop:
    name: hardening
    tier: 1
    trigger: nightly
x-augur-config:
  contributions:
    commands:
    - id: auto-agent-config-parity
      type: workflow
      visibility: auto
      description: Detect Claude-only enforcement gates that lack a cross-agent peer in `.githooks/` or `.pre-commit-config.yaml`, so behavior gates do not silently bypass non-Claude clients.
      callable: scripts/agent_config_parity.py
      protocol: scan-fix
    - id: auto-dependency-audit
      type: workflow
      visibility: auto
      description: Scan dependency vulnerabilities and apply conservative audit fixes at higher hardening difficulty.
      callable: scripts/dependency_audit.py
      protocol: scan-fix
    - id: auto-dir-alignment
      type: workflow
      visibility: auto
      description: Validate first-level dirs in managed locations against skill names and reserved entries.
      callable: scripts/dir_alignment_ops.py
      protocol: scan-fix
    - id: auto-file-growth
      type: workflow
      visibility: auto
      description: Detect runaway file generation, duplicate content, and abnormal directory growth.
      callable: scripts/file_growth_ops.py
      protocol: scan-fix
    - id: auto-repo-pollution
      type: workflow
      visibility: auto
      description: Detect working-tree junk invisible to git (gitignored binaries, OS junk, orphan pycache, empty dirs) and remove expired session artifacts.
      callable: scripts/repo_pollution_ops.py
      protocol: scan-fix
    - id: auto-flow-optimizer
      type: workflow
      visibility: auto
      description: Detect dispatch mode mismatches across actions and write a flow optimization report.
      callable: scripts/flow_optimizer.py
      protocol: scan-fix
    - id: auto-fs-bypass
      type: workflow
      visibility: auto
      description: Detect direct filesystem access in API routes that bypass MCP-first policy.
      callable: scripts/fs_bypass.py
      protocol: scan-fix
    - id: auto-git-health
      type: workflow
      visibility: auto
      description: Monitor repository object growth and run git garbage collection when needed.
      callable: scripts/git_health.py
      protocol: scan-fix
    - id: auto-inspect
      type: workflow
      visibility: auto
      description: Inspect observability dimensions and context window footprint.
      callable: scripts/inspect_ops.py
      protocol: scan-fix
    - id: auto-logs
      type: workflow
      visibility: auto
      description: Archive old logs and maintain runtime log hygiene.
      callable: scripts/logs.py
      protocol: scan-fix
    - id: auto-mcp-health-audit
      type: workflow
      visibility: auto
      description: Audit MCP route wiring, runtime health, and safe auto-fixes.
      callable: scripts/mcp_health_audit.py
      protocol: scan-fix
    - id: auto-page-health
      type: workflow
      visibility: auto
      description: Verify dashboard page MCP tool references and auto-fix YAML tool names.
      callable: scripts/page_health.py
      protocol: scan-fix
    - id: auto-perf-profile
      type: workflow
      visibility: auto
      description: Check response times, disk bloat, stale files, cache size, and performance regressions.
      callable: scripts/perf_profile.py
      protocol: scan-fix
    - id: auto-plugin-lint
      type: workflow
      visibility: auto
      description: Fix plugin structural issues with AI-assisted lint and validation.
      callable: scripts/plugin_lint.py
      protocol: scan-fix
    - id: auto-repo-sync
      type: workflow
      visibility: auto
      description: Check repos for uncommitted and unpushed changes, then sync at higher difficulty.
      callable: scripts/repo_sync.py
      protocol: scan-fix
    - id: auto-skill-root-migration
      type: workflow
      visibility: auto
      description: Enforce the shared/private vault skill-root migration contract.
      callable: scripts/skill_root_migration_ops.py
      protocol: scan-fix
x-augur-loops:
- id: hardening
  skill: routine-platform
  automation:
    trigger: nightly
    runner: auto
    discover: ../daemon/scripts/routine_orchestrator/orchestrator.py
  loop_name: hardening
  memory:
    trust: adaptive
- id: observability
  skill: routine-platform
  automation:
    trigger: nightly
    runner: auto
    discover: ../daemon/scripts/routine_orchestrator/orchestrator.py
  loop_name: observability
  memory:
    trust: adaptive
- id: page-health
  skill: routine-platform
  automation:
    trigger: nightly
    runner: auto
    discover: ../daemon/scripts/routine_orchestrator/orchestrator.py
  loop_name: page-health
  memory:
    trust: adaptive
---

# routine-platform

Platform health routines for git maintenance, dependency checks, page health,
observability, plugin lint, filesystem growth, and runtime parity.

## Commands

- [commands/auto-dependency-audit.md](commands/auto-dependency-audit.md)
- [commands/auto-dir-alignment.md](commands/auto-dir-alignment.md)
- [commands/auto-file-growth.md](commands/auto-file-growth.md)
- [commands/auto-flow-optimizer.md](commands/auto-flow-optimizer.md)
- [commands/auto-fs-bypass.md](commands/auto-fs-bypass.md)
- [commands/auto-git-health.md](commands/auto-git-health.md)
- [commands/auto-inspect.md](commands/auto-inspect.md)
- [commands/auto-logs.md](commands/auto-logs.md)
- [commands/auto-mcp-health-audit.md](commands/auto-mcp-health-audit.md)
- [commands/auto-page-health.md](commands/auto-page-health.md)
- [commands/auto-perf-profile.md](commands/auto-perf-profile.md)
- [commands/auto-plugin-lint.md](commands/auto-plugin-lint.md)
- [commands/auto-repo-sync.md](commands/auto-repo-sync.md)
- [commands/auto-skill-root-migration.md](commands/auto-skill-root-migration.md)

## Scope

Use this routine skill for platform health, git/runtime checks, page health, observability, and plugin lint previously split across retired ops, observability, and repository loop skills.

## When to use

Use `routine-platform` when Augur needs infrastructure drift checks rather than
domain-content checks: before a release, after a broad refactor, after dependency
updates, when MCP routes or dashboard pages look stale, or on the nightly
hardening and observability schedules.

## What it checks

- **Git and repo sync** — detects uncommitted, unpushed, or unhealthy repository
  state before automated work assumes a clean baseline.
- **Dependencies** — scans dependency vulnerabilities and applies conservative
  fixes only at higher hardening difficulty.
- **Dashboard pages** — validates page MCP tool references and repairs safe YAML
  tool-name drift.
- **MCP and filesystem policy** — audits route wiring and direct filesystem
  bypasses against the MCP-first dashboard contract.
- **Observability** — inspects logs, context footprint, performance, stale files,
  cache size, and runtime health signals.
- **Plugin and skill roots** — lints plugin structure and enforces the
  shared/private skill-root migration contract.
- **Agent parity** — compares agent/client enforcement gates so non-Claude
  clients do not silently miss platform safeguards.

## Workflow

Run the platform loop as a scan-fix process with difficulty set by the adaptive
routine orchestrator. Low difficulty reports drift; higher difficulty applies
safe mechanical fixes and leaves risky findings as manual issues.

- Step 1: Start from the owning command document in `commands/` to confirm the
  command contract and any `--help` behavior.
- Step 2: Run the matching implementation in `scripts/` through the routine
  orchestrator or auto-command bucket.
- Step 3: Inspect reported findings for user-visible infrastructure risk before
  editing unrelated files.
- Step 4: Verify against the real repository, dashboard page set, or runtime
  directories named by the finding.
- Step 5: Report any remaining manual issue with the exact command id, file, and
  blocked user-facing value.

## Examples

```bash
# Inspect runtime observability, performance, and cache drift on demand.
aug a-loops scan-only --loop observability

# Check dashboard page MCP tool references without changing page sources.
aug a-loops scan-only --loop page-health
```

## References

- Command contracts live under `commands/`, one Markdown file per workflow id.
- Deterministic implementations live under `scripts/`; prefer these over ad hoc
  shell snippets when investigating a platform finding.
- Additional operator notes live in `references/`, including MCP health-audit
  context and vault-hygiene follow-up resources.
