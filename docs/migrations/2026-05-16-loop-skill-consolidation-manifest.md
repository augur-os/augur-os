# Loop skill consolidation migration manifest (ADR-756)

Date: 2026-05-16
Scope: consolidate `shared-vault/skills/loop-*` into five concern-owned `routine-*` skills.

## Live audit summary

- ADR-756/plan text expected 85 auto commands; this checkout has 53 `auto-*.md` command files under `loop-*`.
- This checkout has 55 unique `auto-*` declarations/files in the loop skills when SKILL metadata and command files are unioned.
- The current adaptive discovery registry loads 46 registry-active loop auto commands because it reads `x-augur-commands` entries with `protocol: scan-fix` and `loop.name`.
- `loop-wiring` owns nine `auto-*.md` command files but has no top-level `x-augur-commands` entries, so those files are migrated as payload without changing the active runtime set.
- `loop-ops` declares `auto-agent-config-parity` and `loop-test` declares `auto-test-onboarding-probes` without matching `commands/*.md`; both declarations and scripts are preserved.
- `loop-hygiene` is not empty in this checkout: it owns the `/sweep-stores` slash command, scripts, tests, references, data, and fixtures. It is migrated into `routine-vault`.

## Destination counts

| destination skill | auto declarations/files | concern |
|---|---:|---|
| `routine-codebase` | 25 | tests, type/build quality, dashboard/API/MCP/page wiring |
| `routine-platform` | 15 | git, page health, observability, plugin and platform hygiene |
| `routine-vault` | 7 | memory, vault/doc hygiene, stale artifact sweeping |
| `routine-coverage` | 7 | hub and command/skill usage coverage |
| `routine-security` | 1 | security audits |

## Per-command migration table

| command | source skill | destination skill | loop category | callable | command doc | registry/declaration notes | cross-skill mentions |
|---|---|---|---|---|---|---|---|
| `auto-claude-md-audit` | `loop-docs` | `routine-vault` | `knowledge-enrichment` | `scripts/claude_md_audit.py` | yes | x-augur-commands | (none) |
| `auto-command-help-coverage` | `loop-docs` | `routine-coverage` | `command-evolution` | `scripts/command_help_coverage_ops.py` | yes | x-augur-commands | (none) |
| `auto-frontmatter-lint` | `loop-docs` | `routine-vault` | `hardening` | `scripts/frontmatter_lint.py` | yes | x-augur-commands | (none) |
| `auto-markdowns` | `loop-docs` | `routine-vault` | `code-quality` | `scripts/markdown_ops.py` | yes | x-augur-commands | (none) |
| `auto-skill-usage` | `loop-docs` | `routine-coverage` | `skill-standards` | `scripts/auto_skill_usage_ops.py` | yes | x-augur-commands | (none) |
| `auto-stale-refs` | `loop-docs` | `routine-vault` | `hardening` | `scripts/stale_refs.py` | yes | x-augur-commands | (none) |
| `auto-adaptive-hub-coverage` | `loop-hub-coverage` | `routine-coverage` | `code-quality` | `scripts/adaptive_hub_coverage_ops.py` | yes | x-augur-commands | (none) |
| `auto-brain-hub-coverage` | `loop-hub-coverage` | `routine-coverage` | `code-quality` | `scripts/brain_hub_coverage_ops.py` | yes | x-augur-commands | (none) |
| `auto-command-hub-coverage` | `loop-hub-coverage` | `routine-coverage` | `code-quality` | `scripts/command_hub_coverage_ops.py` | yes | x-augur-commands | (none) |
| `auto-life-hub-coverage` | `loop-hub-coverage` | `routine-coverage` | `code-quality` | `scripts/life_hub_coverage_ops.py` | yes | x-augur-commands | (none) |
| `auto-studio-hub-coverage` | `loop-hub-coverage` | `routine-coverage` | `code-quality` | `scripts/studio_hub_coverage_ops.py` | yes | x-augur-commands | (none) |
| `sweep-stores` | `loop-hygiene` | `routine-vault` | `(not registry-active)` | `commands/sweep-stores.md` | yes | x-augur-commands | (none) |
| `auto-context-audit` | `loop-memory` | `routine-vault` | `observability` | `scripts/context_audit.py` | yes | x-augur-commands | (none) |
| `auto-memory-leak` | `loop-memory` | `routine-vault` | `hardening` | `scripts/memory_leak.py` | yes | x-augur-commands | (none) |
| `auto-flow-optimizer` | `loop-observability` | `routine-platform` | `hardening` | `scripts/flow_optimizer.py` | yes | x-augur-commands | (none) |
| `auto-perf-profile` | `loop-observability` | `routine-platform` | `observability` | `scripts/perf_profile.py` | yes | x-augur-commands | (none) |
| `auto-repo-sync` | `loop-observability` | `routine-platform` | `observability` | `scripts/repo_sync.py` | yes | x-augur-commands | (none) |
| `auto-agent-config-parity` | `loop-ops` | `routine-platform` | `hardening` | `scripts/agent_config_parity.py` | no | x-augur-commands | (none) |
| `auto-dependency-audit` | `loop-ops` | `routine-platform` | `hardening` | `scripts/dependency_audit.py` | yes | x-augur-commands | (none) |
| `auto-fs-bypass` | `loop-ops` | `routine-platform` | `hardening` | `scripts/fs_bypass.py` | yes | x-augur-commands | (none) |
| `auto-inspect` | `loop-ops` | `routine-platform` | `observability` | `scripts/inspect_ops.py` | yes | x-augur-commands | (none) |
| `auto-logs` | `loop-ops` | `routine-platform` | `code-quality` | `scripts/logs.py` | yes | x-augur-commands | (none) |
| `auto-mcp-health-audit` | `loop-ops` | `routine-platform` | `testing` | `scripts/mcp_health_audit.py` | yes | x-augur-commands | (none) |
| `auto-page-health` | `loop-ops` | `routine-platform` | `page-health` | `scripts/page_health.py` | yes | x-augur-commands | (none) |
| `auto-plugin-lint` | `loop-ops` | `routine-platform` | `hardening` | `scripts/plugin_lint.py` | yes | x-augur-commands | (none) |
| `auto-format` | `loop-quality` | `routine-codebase` | `code-quality` | `scripts/format.py` | yes | x-augur-commands | (none) |
| `auto-lint` | `loop-quality` | `routine-codebase` | `code-quality` | `scripts/lint.py` | yes | x-augur-commands | (none) |
| `auto-ui-quality` | `loop-quality` | `routine-codebase` | `ui-quality` | `scripts/ui_quality.py` | yes | x-augur-commands | (none) |
| `auto-yaml-lint` | `loop-quality` | `routine-codebase` | `hardening` | `scripts/yaml_lint_ops.py` | yes | x-augur-commands | (none) |
| `auto-dir-alignment` | `loop-repo` | `routine-platform` | `hardening` | `scripts/dir_alignment_ops.py` | yes | x-augur-commands | (none) |
| `auto-file-growth` | `loop-repo` | `routine-platform` | `self-heal` | `scripts/file_growth_ops.py` | yes | x-augur-commands | (none) |
| `auto-git-health` | `loop-repo` | `routine-platform` | `code-quality` | `scripts/git_health.py` | yes | x-augur-commands | (none) |
| `auto-skill-root-migration` | `loop-repo` | `routine-platform` | `hardening` | `scripts/skill_root_migration_ops.py` | yes | x-augur-commands | (none) |
| `auto-vault-hygiene` | `loop-repo` | `routine-vault` | `hardening` | `scripts/vault_hygiene_ops.py` | yes | x-augur-commands | (none) |
| `auto-security-audit` | `loop-security` | `routine-security` | `hardening` | `scripts/security_audit.py` | yes | x-augur-commands | (none) |
| `auto-e2e-actions` | `loop-test` | `routine-codebase` | `testing` | `scripts/e2e_actions.py` | yes | x-augur-commands | (none) |
| `auto-e2e-pipeline` | `loop-test` | `routine-codebase` | `testing` | `scripts/e2e_pipeline.py` | yes | x-augur-commands | (none) |
| `auto-test-api` | `loop-test` | `routine-codebase` | `testing` | `scripts/test_api_ops.py` | yes | x-augur-commands | (none) |
| `auto-test-build` | `loop-test` | `routine-codebase` | `testing` | `scripts/test_build_ops.py` | yes | x-augur-commands | (none) |
| `auto-test-dashboard` | `loop-test` | `routine-codebase` | `testing` | `scripts/test_dashboard_ops.py` | yes | x-augur-commands | (none) |
| `auto-test-links` | `loop-test` | `routine-codebase` | `testing` | `scripts/test_links_ops.py` | yes | x-augur-commands | (none) |
| `auto-test-mcp` | `loop-test` | `routine-codebase` | `testing` | `scripts/test_mcp_ops.py` | yes | x-augur-commands | (none) |
| `auto-test-mcp-commands` | `loop-test` | `routine-codebase` | `testing` | `scripts/test_mcp_commands_ops.py` | yes | x-augur-commands | (none) |
| `auto-test-onboarding-probes` | `loop-test` | `routine-codebase` | `testing` | `scripts/onboarding_probes_ops.py` | no | x-augur-commands | (none) |
| `auto-test-pages` | `loop-test` | `routine-codebase` | `testing` | `scripts/test_pages_ops.py` | yes | x-augur-commands | (none) |
| `auto-test-pytest` | `loop-test` | `routine-codebase` | `testing` | `scripts/test_pytest_ops.py` | yes | x-augur-commands | (none) |
| `auto-test-webmcp` | `loop-test` | `routine-codebase` | `testing` | `scripts/webmcp_ops.py` | yes | x-augur-commands | (none) |
| `auto-api-wiring` | `loop-wiring` | `routine-codebase` | `(not registry-active)` | `scripts/api_wiring_ops.py` | yes | command-file, x-augur-config; missing loop.name in active declaration | (none) |
| `auto-block-wiring` | `loop-wiring` | `routine-codebase` | `(not registry-active)` | `scripts/block_wiring.py` | yes | command-file, x-augur-config; missing loop.name in active declaration | (none) |
| `auto-dead-api` | `loop-wiring` | `routine-codebase` | `(not registry-active)` | `scripts/dead_api_ops.py` | yes | command-file, x-augur-config; missing loop.name in active declaration | (none) |
| `auto-dead-ui` | `loop-wiring` | `routine-codebase` | `(not registry-active)` | `scripts/dead_ui_ops.py` | yes | command-file, x-augur-config; missing loop.name in active declaration | (none) |
| `auto-dead-wiring` | `loop-wiring` | `routine-codebase` | `(not registry-active)` | `scripts/dead_wiring_ops.py` | yes | command-file, x-augur-config; missing loop.name in active declaration | (none) |
| `auto-page-mounts` | `loop-wiring` | `routine-codebase` | `(not registry-active)` | `scripts/page_mounts.py` | yes | command-file, x-augur-config; missing loop.name in active declaration | (none) |
| `auto-tab-registry` | `loop-wiring` | `routine-codebase` | `(not registry-active)` | `scripts/tab_registry.py` | yes | command-file, x-augur-config; missing loop.name in active declaration | (none) |
| `auto-tabs` | `loop-wiring` | `routine-codebase` | `(not registry-active)` | `scripts/tabs.py` | yes | command-file, x-augur-config; missing loop.name in active declaration | (none) |
| `auto-view-schema` | `loop-wiring` | `routine-codebase` | `(not registry-active)` | `scripts/view_schema.py` | yes | command-file, x-augur-config; missing loop.name in active declaration | (none) |

## Registry-active pre-migration snapshot

The following rows are the active auto-loop registry entries before migration. Post-migration verification must keep the same command ids and loop categories while changing only `source skill` from `loop-*` to `routine-*`.

| command | source skill | loop category | tier | trigger | module |
|---|---|---|---:|---|---|
| `auto-adaptive-hub-coverage` | `loop-hub-coverage` | `code-quality` | 2 | `nightly` | `shared-vault/skills/loop-hub-coverage/scripts/adaptive_hub_coverage_ops.py` |
| `auto-agent-config-parity` | `loop-ops` | `hardening` | 2 | `nightly` | `shared-vault/skills/loop-ops/scripts/agent_config_parity.py` |
| `auto-brain-hub-coverage` | `loop-hub-coverage` | `code-quality` | 2 | `nightly` | `shared-vault/skills/loop-hub-coverage/scripts/brain_hub_coverage_ops.py` |
| `auto-claude-md-audit` | `loop-docs` | `knowledge-enrichment` | 2 | `weekly` | `shared-vault/skills/loop-docs/scripts/claude_md_audit.py` |
| `auto-command-help-coverage` | `loop-docs` | `command-evolution` | 1 | `nightly` | `shared-vault/skills/loop-docs/scripts/command_help_coverage_ops.py` |
| `auto-command-hub-coverage` | `loop-hub-coverage` | `code-quality` | 2 | `nightly` | `shared-vault/skills/loop-hub-coverage/scripts/command_hub_coverage_ops.py` |
| `auto-context-audit` | `loop-memory` | `observability` | 1 | `nightly` | `shared-vault/skills/loop-memory/scripts/context_audit.py` |
| `auto-dependency-audit` | `loop-ops` | `hardening` | 3 | `nightly` | `shared-vault/skills/loop-ops/scripts/dependency_audit.py` |
| `auto-dir-alignment` | `loop-repo` | `hardening` | 2 | `nightly` | `shared-vault/skills/loop-repo/scripts/dir_alignment_ops.py` |
| `auto-e2e-actions` | `loop-test` | `testing` | 3 | `nightly` | `shared-vault/skills/loop-test/scripts/e2e_actions.py` |
| `auto-e2e-pipeline` | `loop-test` | `testing` | 3 | `nightly` | `shared-vault/skills/loop-test/scripts/e2e_pipeline.py` |
| `auto-file-growth` | `loop-repo` | `self-heal` | 0 | `nightly` | `shared-vault/skills/loop-repo/scripts/file_growth_ops.py` |
| `auto-flow-optimizer` | `loop-observability` | `hardening` | 5 | `nightly` | `shared-vault/skills/loop-observability/scripts/flow_optimizer.py` |
| `auto-format` | `loop-quality` | `code-quality` | 1 | `nightly` | `shared-vault/skills/loop-quality/scripts/format.py` |
| `auto-frontmatter-lint` | `loop-docs` | `hardening` | 1 | `nightly` | `shared-vault/skills/loop-docs/scripts/frontmatter_lint.py` |
| `auto-fs-bypass` | `loop-ops` | `hardening` | 4 | `nightly` | `shared-vault/skills/loop-ops/scripts/fs_bypass.py` |
| `auto-git-health` | `loop-repo` | `code-quality` | 1 | `nightly` | `shared-vault/skills/loop-repo/scripts/git_health.py` |
| `auto-inspect` | `loop-ops` | `observability` | 3 | `nightly` | `shared-vault/skills/loop-ops/scripts/inspect_ops.py` |
| `auto-life-hub-coverage` | `loop-hub-coverage` | `code-quality` | 2 | `nightly` | `shared-vault/skills/loop-hub-coverage/scripts/life_hub_coverage_ops.py` |
| `auto-lint` | `loop-quality` | `code-quality` | 1 | `nightly` | `shared-vault/skills/loop-quality/scripts/lint.py` |
| `auto-logs` | `loop-ops` | `code-quality` | 1 | `nightly` | `shared-vault/skills/loop-ops/scripts/logs.py` |
| `auto-markdowns` | `loop-docs` | `code-quality` | 2 | `nightly` | `shared-vault/skills/loop-docs/scripts/markdown_ops.py` |
| `auto-mcp-health-audit` | `loop-ops` | `testing` | 2 | `nightly` | `shared-vault/skills/loop-ops/scripts/mcp_health_audit.py` |
| `auto-memory-leak` | `loop-memory` | `hardening` | 2 | `nightly` | `shared-vault/skills/loop-memory/scripts/memory_leak.py` |
| `auto-page-health` | `loop-ops` | `page-health` | 1 | `nightly` | `shared-vault/skills/loop-ops/scripts/page_health.py` |
| `auto-perf-profile` | `loop-observability` | `observability` | 2 | `nightly` | `shared-vault/skills/loop-observability/scripts/perf_profile.py` |
| `auto-plugin-lint` | `loop-ops` | `hardening` | 3 | `nightly` | `shared-vault/skills/loop-ops/scripts/plugin_lint.py` |
| `auto-repo-sync` | `loop-observability` | `observability` | 1 | `nightly` | `shared-vault/skills/loop-observability/scripts/repo_sync.py` |
| `auto-security-audit` | `loop-security` | `hardening` | 3 | `nightly` | `shared-vault/skills/loop-security/scripts/security_audit.py` |
| `auto-skill-root-migration` | `loop-repo` | `hardening` | 1 | `nightly` | `shared-vault/skills/loop-repo/scripts/skill_root_migration_ops.py` |
| `auto-skill-usage` | `loop-docs` | `skill-standards` | 5 | `nightly` | `shared-vault/skills/loop-docs/scripts/auto_skill_usage_ops.py` |
| `auto-stale-refs` | `loop-docs` | `hardening` | 1 | `nightly` | `shared-vault/skills/loop-docs/scripts/stale_refs.py` |
| `auto-studio-hub-coverage` | `loop-hub-coverage` | `code-quality` | 2 | `nightly` | `shared-vault/skills/loop-hub-coverage/scripts/studio_hub_coverage_ops.py` |
| `auto-test-api` | `loop-test` | `testing` | 2 | `nightly` | `shared-vault/skills/loop-test/scripts/test_api_ops.py` |
| `auto-test-build` | `loop-test` | `testing` | 0 | `nightly` | `shared-vault/skills/loop-test/scripts/test_build_ops.py` |
| `auto-test-dashboard` | `loop-test` | `testing` | 1 | `nightly` | `shared-vault/skills/loop-test/scripts/test_dashboard_ops.py` |
| `auto-test-links` | `loop-test` | `testing` | 2 | `nightly` | `shared-vault/skills/loop-test/scripts/test_links_ops.py` |
| `auto-test-mcp` | `loop-test` | `testing` | 1 | `nightly` | `shared-vault/skills/loop-test/scripts/test_mcp_ops.py` |
| `auto-test-mcp-commands` | `loop-test` | `testing` | 3 | `nightly` | `shared-vault/skills/loop-test/scripts/test_mcp_commands_ops.py` |
| `auto-test-onboarding-probes` | `loop-test` | `testing` | 1 | `nightly` | `shared-vault/skills/loop-test/scripts/onboarding_probes_ops.py` |
| `auto-test-pages` | `loop-test` | `testing` | 2 | `nightly` | `shared-vault/skills/loop-test/scripts/test_pages_ops.py` |
| `auto-test-pytest` | `loop-test` | `testing` | 1 | `nightly` | `shared-vault/skills/loop-test/scripts/test_pytest_ops.py` |
| `auto-test-webmcp` | `loop-test` | `testing` | 3 | `nightly` | `shared-vault/skills/loop-test/scripts/webmcp_ops.py` |
| `auto-ui-quality` | `loop-quality` | `ui-quality` | 2 | `nightly` | `shared-vault/skills/loop-quality/scripts/ui_quality.py` |
| `auto-vault-hygiene` | `loop-repo` | `hardening` | 1 | `nightly` | `shared-vault/skills/loop-repo/scripts/vault_hygiene_ops.py` |
| `auto-yaml-lint` | `loop-quality` | `hardening` | 1 | `nightly` | `shared-vault/skills/loop-quality/scripts/yaml_lint_ops.py` |

## Trust state independence

- Trust state path inspected: `~/Library/Application Support/Augur/state/adaptive/trust_state.json`
- Trust keys are category names under `loops`: `auto-agent-digest`, `code-quality`, `command-evolution`, `duplication`, `evals`, `file-organizer`, `hardening`, `knowledge-enrichment`, `observability`, `page-health`, `self-heal`, `skill-quality`, `skill-standards`, `testing`, `ui-quality`.
- Contains no `loop-*` skill paths: `true`.

## Cross-reference audit

Audit command:

```bash
rg -n "loop-test|loop-quality|loop-wiring|loop-ops|loop-docs|loop-repo|loop-hub-coverage|loop-observability|loop-memory|loop-security|loop-hygiene" shared-vault/skills docs config src plugins -g "!**/__pycache__/**"
```

| reference group | hit count | disposition |
|---|---:|---|
| capability exposure config | 10 | active skill keys updated to routine-* |
| docs | 222 | review and update active references |
| historical/live ADR records | 37 | historical context kept where it describes pre-migration state; ADR-756 status notes updated after implementation |
| hygiene MCP wrapper | 5 | updated from loop-hygiene script root to routine-vault script root |
| implementation/spec/plan records | 134 | historical context kept where it describes pre-migration state; ADR-756 status notes updated after implementation |
| moved loop skill payloads | 77 | mechanically rewritten or removed by moving payloads |
| shared-vault | 56 | review and update active references |
| source code | 3 | review and update active references |

## Implementation notes

- Move tracked files with `git mv`; ignored `__pycache__/` files are intentionally not migrated.
- Preserve command ids, scan/fix callables, loop category names, tiers, and triggers for the registry-active set.
- Keep `/sweep-stores` slash command user-facing behavior unchanged while relocating its owning skill to `routine-vault`.
- Do not add loop metadata to `loop-wiring` during this ADR; that would expand the active runtime set and violate the move-only non-goal. A follow-up can register those nine commands deliberately if desired.
