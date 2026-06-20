# Changelog

All notable changes to the advisor skill will be documented in this file.

## [0.5.0] - 2026-06-11

### Changed
- Adopted into `project-brain/capabilities/skills/advisor/` as a selective
  port of the staged r3 draft (ADR-805 native-first, ADR-813 command ladder).
- SKILL.md rewritten: retired `x-augur-hub`/`x-augur-tab`/`x-augur-group`/
  `x-augur-release`/`x-augur-config`/`x-augur-env` fields stripped (ADR-802);
  the 18 stale `x-augur-mcp-tools` declarations dropped (the corresponding
  capability records were removed in 294f328f2); dashboard page/hub ownership
  dropped; commands declared via `x-augur-commands`. Explicit non-ownership
  boundaries written for `evals`, `auto-skill-quality`, `routine-coverage`,
  `knowledge`, backlog scanning, and `skillify`.
- `references/codebase-exploration.md` adapted from the staged
  `augur/modules/architecture-analyzer.md`: four-phase exploration framework
  kept; the Repository Adaptation Analysis half excluded (owned by
  `skillify` / port-release contract); Augur-specific anchors added.

### Added
- `/advisor-architecture` (four-phase exploration + decisive blueprint,
  ADR-checked, read-only) and `/advisor-prompt-optimize` (baseline →
  variants → A/B evaluation plan, retrieval measurement handed to `evals`).
- References ported verbatim: `prompt-optimization.md`,
  `ab-testing-framework.md`, `vision-framework.md`, `alignment-scoring.md`,
  `drift-detection.md`, `blueprint-template.md`.
- `augur/tests/test_advisor_skill.py` contract tests (frontmatter shape,
  retired-field guard, command/reference integrity, no-scripts guard).
- `evals/rank.json` kept verbatim as the historical quality-rank record.

### Removed (excluded from the port)
- **All scripts** (`scripts/analytics/`, `scripts/design/`, `scripts/mcp/`)
  — zero ported:
  - Speculative-generator machinery (the retired insight-scanner pattern,
    ADR-078): `generate_telemetry.py`, `process_self_improvement_results.py`,
    `process_data_scientist_logs.py`, `self_improvement_e2e_test.py`,
    `report_bug.py`, `sync_bugs_to_github.py`, `loop_advisor_ops.py`
    (suggests new auto-commands; imports nonexistent `src.lib.ops_protocol`),
    `monitor_prompts.py`, `monitoring_report.py`, `import_advisor_datasets.py`.
  - Stale pre-ADR-802 layout: `analyze_tokens.py`, `flow_audit.py` (also
    broken — undefined `chains_dir`, KeyError on `chains_scanned`),
    `generate_diagrams.py` (factory/horizontal/vertical scan + repo-tree
    write to docs/ARCHITECTURE.md), `evaluation/run_eval.py`,
    `evaluation/compare_runs.py`, `evaluation/generate_report.py`
    (plugins/dev/skills data dir), `run_action_evals.py` (imports
    nonexistent `skills.ai.augur.lib`), `data_audit.py` (repo-root
    `skills/advisor` data dir), `knowledge_manager.py` (writes into
    `get_config_dir()/horizontal/`).
  - Placeholder/no-value scripts (rule 34): `analyze_codebase.py` (file
    count), `explore_codebase.py` (hardcoded list), `create_blueprint.py`
    (static JSON), `design.py`, `vision_check.py` (word-overlap "score"),
    `vision_keeper.py` (runtime/factory JSON store), `system_optimization.py`
    (drives removed MCP pipeline), `analyze_logs.py`, `analyze_usage.py`,
    `optimize_prompts.py`, `prompt_versioning.py` (broken data-dir
    resolution / stale prompt-registry layout).
  - Duplicative: `skill_health_score.py` (auto-skill-quality owns skill
    scoring), `memory_audit.py` (knowledge owns memory health; stale
    MEMORY.md/daily-log layout), `adr_lifecycle_ops.py` (nonexistent ops
    protocol; ADR lifecycle scanning owned by routine loops).
  - `scripts/mcp/` — no MCP tools ship (stale advisor capability records
    removed in 294f328f2; tools call repo-root `skills/advisor` paths and
    nonexistent `skills.daemon.augur.lib.performance_ledger`).
- **References**: `workflows.md` (System Optimization calls removed MCP
  tools; Run Evaluations → `evals`; usage/backlog procedures reference
  nonexistent `augur-data/` stores), `analyst-operating-guide.md` and
  `analyst-workflow.md` (pointer docs to excluded telemetry machinery),
  `architect-workflow.md` (GitHub skill discovery → platform-admin),
  `architecture-workflow.md` (parallel ADR process conflicting with Augur's
  canonical ADR system), `analytics-patterns.md` (thin; analytics surfaces
  owned by knowledge/routine-coverage), `integration-patterns.md` (stale
  paths; covered by SKILLS.md topic doc), `pipeline-integration.md`
  (documents a nonexistent GitHub Actions workflow, self-described
  placeholders), `knowledge/horizontal-vertical-architecture.md` (retired
  three-layer plugins architecture, contradicts ADR-802).
- **Modules** (`augur/modules/`, factory-agent era): `backend.md`,
  `marketing-analytics.md` (Company-in-a-Box-derived, Apache-2.0-marked,
  off-domain), `cost-analytics.md`, `session-analytics.md`,
  `skill-usage-analytics.md` (knowledge/routine-coverage own usage
  analytics; stale data sources), `github-search.md` + `augur/config/sources.yaml`
  (platform-admin owns skill discovery), `refactor-engine.md`,
  `scaffold-generator.md` (skillify owns), `structure-validator.md`
  (validator/auto-skill-quality own; stale standards), `product-vision.md`
  (pointer to excluded vision_keeper machinery — methodology survives in
  references).
- **Draft commands**: `triage-backlog.md` (no advisor backlog store exists;
  debt discovery owned by TODO_ markers/hygiene/routine loops),
  `analyze-usage-patterns.md` (routine-coverage/knowledge own),
  `add-prompt-helper.md` (stale dashboard action-button pipeline),
  `improve-prompt.md` (superseded by /advisor-prompt-optimize).
- **Draft tests** (32 files): they test the excluded scripts.
- `evals/evals.json` (asserts removed MCP tools execute).

## [0.1.0] - 2025-12-25

### Added
- Initial staged draft: analyst/architect/vision-keeper agent workflows,
  analytics and telemetry scripts, MCP tool modules, dashboard hub page.
