# Changelog

All notable changes to the validator skill will be documented in this file.

## [0.5.0] - 2026-06-11

### Changed
- Adopted into `project-brain/capabilities/skills/validator/` as a selective
  port of the staged r3 draft (ADR-805 native-first, ADR-813 command ladder).
- SKILL.md rewritten: retired `x-augur-hub`/`x-augur-tab`/`x-augur-group`/
  `x-augur-release` fields stripped (ADR-802), MCP tool and dashboard-page
  declarations dropped (nothing shipped), commands declared via
  `x-augur-commands`.
- `ui_qa.py` / `capture_ui.py` repointed at canonical paths
  (`src.config.paths` helpers, skill-relative config); artifacts now land in
  runtime/logs dirs, never the repo tree.

### Added
- `/validator-verify` and `/validator-regression` commands orchestrating the
  ported scripts plus the sanctioned auto-loops.
- `augur/tests/` smoke + behavior tests for every ported script.

### Removed (excluded from the port)
- Raw test/build runners duplicating sanctioned loops: `verify_changes.py`,
  `regression_testing.py`, `regression_tests.py`, `run_verification_loop.py`,
  `plugin_integration_test.py`, `augur_pre_merge.py`.
- Stale-layout or broken scripts: `enforce.py`, `validate_integrations.py`,
  `validate_plugin_compliance.py`, `check_cross_repo_consistency.py`,
  `resolve_review.py`, `import_validator_datasets.py`, `confidence_review.py`,
  `validator_audit.py`, `scripts/mcp/`.
- `scripts/security/` (duplicates routine-security ownership of secret and
  security scanning).

## [0.1.0] - 2025-12-25

### Added
- Initial implementation of Validator Agent
- `verify_changes` workflow for task verification
- `regression_testing` workflow for release validation
- SKILL.md orchestrator
- Workflow documentation
- Pipeline integration
