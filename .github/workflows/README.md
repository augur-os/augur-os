# CI/CD Workflows

This directory contains GitHub Actions workflows for the Augur project.
All workflows run on `ubuntu-latest` (except `ci-cross-platform.yml` which uses a matrix).

## Workflow Overview

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `ci-tests.yml` | push/PR | Test suite (skill, root, integration, MCP, dashboard) |
| `ci-lint.yml` | push/PR | Linting, type checking, audits |
| `ci-cross-platform.yml` | push/PR | Windows/Mac/Linux compatibility and Windows hardening verification (supported checks run read-only and fail on actionable findings) |
| `ci-security.yml` | push/PR | Security scanning |
| `cd-release.yml` | manual | Release automation |
| `cron-nightly.yml` | schedule | Backlog generation, failure analysis |
| `claude.yml` | issues | Claude Code integration |
| `codex.yml` | issues | Codex CLI integration |
| `export-plugins.yml` | manual | Export skills as portable plugins |
| `release.yml` | manual | Release Please automation; push trigger disabled until release version/tag history is reconciled |

## Skill Dependencies

**IMPORTANT**: Some workflows depend on skill scripts. If a skill is disabled or removed, the workflow may fail.

### Dependency Matrix

| Workflow | Required Skill | Scripts Used |
|----------|----------------|--------------|
| `ci-tests.yml` | `devops` | `ci_change_detector.py` |
| `ci-lint.yml` | `devops` | `cleanup_paths.py` |
| `ci-cross-platform.yml` | `daemon` | `service_healer.py`, `log_monitor.py`, `adaptive/platform_verify.py` |
| `cd-release.yml` | `devops` | `dependency_tracker.py`, `release.py` |
| `cron-nightly.yml` | `devops` | `ci_failure_analyzer.py`, `dependency_tracker.py` |
| `cron-nightly.yml` | `ai_bridge` | `sync_agents.py` |
| `export-plugins.yml` | dashboard tooling | `skill_exporter.py` |

### Script Locations

Scripts are located in `project-brain/capabilities/skills/{skill}/scripts/`:

| Script | Location |
|--------|----------|
| `ci_change_detector.py` | `project-brain/capabilities/skills/platform-admin/scripts/` |
| `ci_failure_analyzer.py` | `project-brain/capabilities/skills/platform-admin/scripts/` |
| `cleanup_paths.py` | `project-brain/capabilities/skills/platform-admin/scripts/` |
| `dependency_tracker.py` | `project-brain/capabilities/skills/platform-admin/scripts/` |
| `release.py` | `project-brain/capabilities/skills/platform-admin/scripts/` |
| `service_healer.py` | `project-brain/capabilities/skills/daemon/scripts/` |
| `log_monitor.py` | `project-brain/capabilities/skills/daemon/scripts/` |
| `platform_verify.py` | `project-brain/capabilities/skills/daemon/scripts/adaptive/` |
| `sync_agents.py` | `project-brain/capabilities/skills/ai/scripts/sync_agents/` |
| `skill_exporter.py` | `apps/dashboard/scripts/skill-scripts/` |

### CI Scripts (Framework)

These scripts are in `.github/scripts/` and don't depend on skills:

| Category | Scripts |
|----------|---------|
| Audit | `audit_paths.py`, `audit_data_separation.py`, `audit_logging.py`, `audit_git_hygiene.py` |
| Validation | `validate_structure.py`, `validate_boundaries.py`, `validate_file_placement.py`, `validate_dashboard.py`, `validate_budget.py` |
| Verification | `verify_api_endpoints.py`, `verify_schema.py` |
| Checks | `check_runtime_gitignore.py`, `check_sizes.py` |
| Registry | `generate_registry.py`, `generate_list_registry.py` |
| Quality | `scan_code_markers.py` |

## Windows Hardening Verify Contract

`ci-cross-platform.yml` runs `project-brain/capabilities/skills/daemon/scripts/adaptive/platform_verify.py` on Windows for the `hardening` loop.

- Supported checks run in non-mutating mode.
- `report_only` means the scan still runs, but fixes remain disabled.
- Actionable findings fail verification.
- Checks without a declared `OPS_CAPABILITIES` contract are reported as explicit skips until migrated.
- Unsupported checks are reported as explicit skips and do not fail the workflow by themselves.

## Updating Workflows

When modifying skill scripts that workflows depend on:

1. Check this README for affected workflows
2. Update script paths in workflow YAML if needed
3. Test workflow locally with `act` or manual trigger
4. Update this README if dependencies change
