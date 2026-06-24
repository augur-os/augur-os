---
name: platform-admin
x-augur-type: domain
x-augur-group: augur_admin
x-augur-release: mvp
x-augur-tags: []
description: 'Environment setup, repo health, skill discovery, adaptive growth, CI/CD, and release management. Covers: platform admin capabilities'
x-augur-tab: workbench
x-augur-dependencies:
  required:
  - knowledge
  optional:
  - daemon
x-augur-commands:
- id: remote-access
  type: workflow
  visibility: ops
  description: Configure and operate remote dashboard and MCP access for trusted network users.
- id: auto-tidy
  type: workflow
  visibility: auto
  description: Review and cleanup all TODO_ markers in the codebase
  callable: scripts/ops/tidy_ops.py
  protocol: scan-fix
  loop:
    name: code-quality
    tier: 2
    trigger: nightly
- id: auto-debt
  type: workflow
  visibility: auto
  description: Identify, prioritize, and schedule technical debt work
  callable: scripts/ops/tech_debt_ops.py
  protocol: scan-fix
  loop:
    name: code-quality
    tier: 4
    trigger: nightly
- id: auto-docs
  type: workflow
  visibility: auto
  description: Keep documentation synchronized with code
  callable: scripts/ops/docs.py
  protocol: scan-fix
  loop:
    name: knowledge-enrichment
    tier: 2
    trigger: nightly
- id: auto-refactor
  type: skill
  visibility: auto
  description: Capability migration audit and refactoring
  callable: scripts/ops/refactor.py
  protocol: scan-fix
  loop:
    name: hardening
    tier: 4
    trigger: nightly
- id: auto-tabs
  type: workflow
  visibility: auto
  description: Score page maturity and reorder hub tabs with overflow dropdown
  callable: scripts/ops/tabs.py
  protocol: scan-fix
  loop:
    name: hardening
    tier: 3
    trigger: nightly
- id: auto-fix
  type: skill
  visibility: auto
  description: Auto-fix safe TODO_ markers (CLEANUP, OUTDATED) using the auto-fix-markers chain.
  callable: scripts/ops/auto_fix.py
  protocol: scan-fix
  loop:
    name: code-quality
    tier: 1
    trigger: nightly
- id: auto-markers
  type: workflow
  visibility: auto
  description: Scan and update TODO/FIXME markers across the codebase
  callable: scripts/ops/markers.py
  protocol: scan-fix
  loop:
    name: code-quality
    tier: 1
    trigger: nightly
- id: auto-duplication
  type: workflow
  visibility: auto
  description: Detect duplicate internal auto-command implementations and collapse safe mirrors into wrappers
  callable: scripts/ops/duplication_ops.py
  protocol: scan-fix
  loop:
    name: duplication
    tier: 1
    trigger: nightly
- id: auto-coverage-check
  type: workflow
  visibility: auto
  description: Analyze test coverage gaps and identify untested Python source modules
  callable: scripts/ops/coverage_check.py
  protocol: scan-fix
  loop:
    name: code-quality
    tier: 3
    trigger: nightly
- id: auto-debt-scan
  type: workflow
  visibility: auto
  description: Identify technical debt via large files and git churn analysis
  callable: scripts/ops/debt_scan.py
  protocol: scan-fix
  loop:
    name: code-quality
    tier: 4
    trigger: nightly
- id: auto-root-pollution
  type: workflow
  visibility: auto
  description: Detect repo-root strays, junk files, and legacy plugin skill copies
  callable: scripts/ops/root_pollution.py
  protocol: scan-fix
  loop:
    name: code-quality
    tier: 0
    trigger: nightly
- id: auto-code-review
  type: workflow
  visibility: auto
  description: Automated code review of recent changes (reports only, no auto-fix)
  callable: scripts/ops/code_review.py
  protocol: scan-fix
  loop:
    name: code-quality
    tier: 3
    trigger: nightly
- id: auto-test-coverage
  type: workflow
  visibility: auto
  description: Analyze test coverage and flag low-coverage modules
  callable: scripts/ops/test_coverage_ops.py
  protocol: scan-fix
  loop:
    name: code-quality
    tier: 2
    trigger: nightly
- id: auto-circular-deps
  type: workflow
  visibility: auto
  description: Detect circular import dependencies in TypeScript and Python code
  callable: scripts/ops/circular_deps.py
  protocol: scan-fix
  loop:
    name: code-quality
    tier: 2
    trigger: nightly
- id: auto-env-check
  type: workflow
  visibility: auto
  description: Validate environment variable usage against documentation files
  callable: scripts/ops/env_check.py
  protocol: scan-fix
  loop:
    name: code-quality
    tier: 1
    trigger: nightly
- id: auto-empty-states
  type: workflow
  visibility: auto
  description: Validate dashboard pages handle empty data gracefully (no blank screens)
  callable: scripts/ops/empty_states.py
  protocol: scan-fix
  loop:
    name: hardening
    tier: 2
    trigger: nightly
- id: auto-broken-assets
  type: workflow
  visibility: auto
  description: Detect referenced images/assets that don't exist on disk
  callable: scripts/ops/broken_assets.py
  protocol: scan-fix
  loop:
    name: hardening
    tier: 2
    trigger: nightly
x-augur-license: MIT
x-augur-metadata:
  version: 0.5.0
  author: Augur
  mcp-server: augur
  isolation: worktree
x-augur-requires-platform: true
x-augur-mcp-tools: []
x-augur-dashboard-pages: []
x-augur-config-file: config.yaml
x-augur-evolution:
  last_updated: 2026-03-22 13:50:28.310677+00:00
  improvements_applied: 1
x-augur-loop:
  id: duplication
  skill: platform-admin
  automation:
    trigger: nightly
    runner: auto
    discover: ../daemon/scripts/routine_orchestrator/orchestrator.py
  loop_name: duplication
  memory:
    trust: adaptive
---















<!-- ADR-102 Evolution: 2026-03-28T23:11:46.065760+00:00 - fix_error_pattern: Self-repair needed for auto-debt-scan -->

<!-- ADR-102 Evolution: 2026-03-28T23:11:45.969971+00:00 - fix_error_pattern: Self-repair needed for auto-code-review -->


<!-- ADR-102 Evolution: 2026-03-22T23:30:08.911782+00:00 - fix_error_pattern: Self-repair needed for auto-lint -->

# DevOps Agent

## Overview
Maintains operational health for Augur: environment checks, maintenance, and growth backlogs.
Primary problem solved: keep Augur reliably shippable by turning operational maintenance
into repeatable checks and executable actions.

## Capabilities
- Environment validation and dependency setup
- Repository health and skill discovery
- Adaptive growth backlog generation
- Code simplification and migration safety checks
- Remote dashboard and MCP access setup
- Augur-aware repository refactoring
- CI/CD pipeline management
- Infrastructure health monitoring
- Incident runbooks and response
- Release management with semantic versioning
- Repository health auditing against best practices

## Current Hardening Focus
- CI/CD execution readiness (change matrix + nightly checks)
- Incident runbooks discoverability and retrieval
- Release management dry-run validation
- Infrastructure health checks
- Adaptive growth backlog generation

## Constraints
- **Reversibility Required**: All infrastructure changes must have rollback plan.
- **Protected Areas**: Production config, secrets, and migrations require approval.
- **No Direct Secrets**: Never handle secrets directly; use secret managers.

## Rollback and Recovery
Use `ops-rollback` as the canonical rollback workflow for failed deployments or breaking changes.

### Worktree Isolation
Rollback operations must run in a git worktree. Use `using-git-worktrees` first, verify the recovery there, then merge back via `/project dev merge`.

### Procedure
1. Capture the current commit, error logs, and key telemetry before reverting.
2. Identify the rollback target from recent commits, tags, or the last green CI run.
3. Prefer `git revert` to preserve history; use `git reset` only when a clean slate is required.
4. Verify recovery with health checks, smoke tests, and key endpoint checks.
5. Document the incident and add prevention work before closing it out.

### When Not to Roll Back
Prefer a fix-forward approach when rollback would create data inconsistency, the forward fix is low-risk, or the issue is isolated to a non-critical path.

## Test Verticals
Use the auto-test verticals as the canonical testing surface for development verification.

### Fast Path
- build validation
- MCP handshake health
- Python tests
- dashboard/Jest tests

### Full Path
Add page-route validation, API route health, and MCP command-category checks when broader verification is needed.

### Scope
Hub scoping should narrow pytest, dashboard tests, page routes, API routes, and MCP command checks, while build and MCP handshake remain global.

## Commands
| Command | Action |
|---------|--------|
| `check environment` | Verify toolchain and config |
| `list skills` | Show available skills |
| `install dependencies` | Install uv/npm dependencies |
| `perform maintenance` | Cleanup and maintenance tasks |
| `remote-access` | Configure remote dashboard and MCP access |
| `adaptive growth` | Analyze commits and create backlog |
| `setup wizard` | Interactive setup |
| `goodnight augur` | Night shift prep |
| `pipeline status` | CI/CD health check |
| `deploy: [env]` | Deploy to environment |
| `health check` | Infrastructure checks |
| `runbook: [incident]` | Incident runbook |
| `/prepare release` | Create release notes, tag, changelog |
| `simplify code` | Persist simplification suggestions for the current context |
| `check migration safety` | Detect orphaned data before structural migration work |
| `augur-aware refactor` | Rename a skill across Augur with dry-run-first checks |
| `/project dev merge` | Commit, merge, push, and clean up branches/worktrees with merge-lock enforcement; `full` is a smart inspected no-loss merge, and `--purge` removes only stalled technical leftovers |

## Modules and References
| Trigger | Load |
|---------|------|
| Adaptive growth | `references/adaptive-growth.md` |
| Infrastructure | `modules/infrastructure.md` |
| Operating guide | `references/operating-guide.md` |
| Release management | `modules/release-management.md` |
| Community standards | `modules/community-standards.md` |
| Repo health audit | `modules/repo-health.md` |
| Rollback protocol | `modules/rollback-protocol.md` |

## Storage
`skills/platform-admin/augur/data/`

## Chain Integration
Participates in: adaptive_growth_cycle, product_launch, data_migration, system_optimization

---
Version: 0.5.0

## Additional resources

See [Additional resources](references/additional-resources.md) for details.
- [CHANGELOG.md](CHANGELOG.md)
- [pyproject.toml](pyproject.toml)
- [references/adaptive-growth.md](references/adaptive-growth.md)
- [commands/ops-refactor-followup.md](commands/ops-refactor-followup.md)
- [assets/seeds/_seed.yaml](assets/seeds/_seed.yaml)
- [assets/seeds/example-platform-admin.yaml](assets/seeds/example-platform-admin.yaml)
- [commands/dev.md](commands/dev.md)
- [commands/dev-merge.md](commands/dev-merge.md)
- [evals/evals.json](evals/evals.json)
- [evals/rank.json](evals/rank.json)
- [references/adaptive-growth.md](references/adaptive-growth.md)
- [references/additional-resources.md](references/additional-resources.md)
- [references/operating-guide.md](references/operating-guide.md)
- [references/docs/ACCEPTANCE_CRITERIA.md](references/docs/ACCEPTANCE_CRITERIA.md)


### Known Issue (ADR-102)

**Pattern:** self-repair plan from code-quality--auto-debt-scan.json; stagnation_streak=0; module=skills/platform-admin/scripts/ops/debt_scan.py; fingerprints=00bea78e7896c9d7, 00e495ef65ba9f27, 00f34b7ee3af1a59, 01e84a9816f531e4, 03906bba81cc2cd7

**Resolution:** inspect recurring actionable fingerprints for stale heuristics
