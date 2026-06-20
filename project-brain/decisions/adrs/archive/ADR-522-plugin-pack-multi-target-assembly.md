---
title: "Plugin-Pack: Multi-Target Plugin Assembly (Codex Support)"
status: Implemented
date: 2026-03-28
extends: ADR-503
tags: [codex, plugin, distribution, cowork]
---

# ADR-522: Plugin-Pack Multi-Target Plugin Assembly

## Context

Codex now has a plugin system (`.codex-plugin/plugin.json`, marketplace discovery, skills bundling) comparable to Claude Desktop's Cowork plugin system. Augur's existing `cowork` skill assembled Augur as a Claude Desktop plugin only. To support Codex as a first-class target, the assembler needed generalization.

## Decision

1. **Rename** `skills/cowork/` to `skills/plugin-pack/` to reflect multi-target scope.
2. **Refactor** the monolithic `cowork_assembler.py` into a shared 4-stage pipeline (`discover_skills` -> `transform_skills` -> `assemble` -> `install`) with per-target formatters via a `BaseFormatter` ABC.
3. **Add `CodexFormatter`** producing `.codex-plugin/plugin.json`, `.mcp.json` (with `--client-id codex`), and `.agents/plugins/marketplace.json`.
4. **Configurable filter profiles** per target: `CoworkProfile` (curated user hubs) and `CodexProfile` (includes dev skills for CLI users).
5. **Update onboarding** to assemble + install the Codex plugin when `--from codex` is used, and provide a bootstrap SKILL.md for in-Codex onboarding.
6. **Install marketplace** to both global (`~/.agents/plugins/`) and repo-scoped (`.agents/plugins/`) locations.

## Consequences

- `/cowork` command replaced by `/plugin-pack`. No backward-compatibility aliases (CLAUDE.md rule 14).
- The `cowork` client-id for Claude Desktop MCP is unchanged — only the skill name was renamed.
- Adding future targets (Gemini, Cursor) requires only a new formatter class and filter profile.
- The `src/mcp/augur_mcp/domain/cowork.py` MCP domain module is unaffected — it handles runtime task dispatch, not plugin assembly.

## Implementation Order

1. FilterProfile dataclass + COWORK/CODEX profiles (`profiles.py`)
2. BaseFormatter ABC (`formatters/base.py`)
3. CoworkFormatter (extracted from `cowork_assembler.py`) + CodexFormatter (new) — parallel
4. Shared assembler pipeline (`plugin_assembler.py`) — depends on 1-3
5. SKILL.md, asset templates, sync adapter — parallel
6. Onboarding: `install.sh` update, bootstrap SKILL.md, status mode — parallel
7. Delete `skills/cowork/`, exhaustive reference migration (rule 23)
8. Verification, ADR, repo-scoped marketplace

## Alternatives Considered

**Fork and specialize** — Copy `cowork_assembler.py` to `codex_assembler.py`. Zero risk to existing cowork flow but duplicates discovery + transformation logic. Adding a third target means a third copy. Rejected for maintainability.

**Config-driven template** — Define each target as YAML; a single generic assembler reads config and produces output. Over-engineered for 2 targets. YAML can't express all format differences (TOML vs JSON, different manifest schemas). Rejected for premature abstraction.

## Impact Manifest

```yaml
paths_renamed:
  - old: skills/cowork/
    new: skills/plugin-pack/
  - old: skills/cowork/scripts/cowork_assembler.py
    new: skills/plugin-pack/scripts/plugin_assembler.py
  - old: skills/ai/scripts/sync_agents/adapters/cowork.py
    new: skills/ai/scripts/sync_agents/adapters/plugin_pack.py
apis_changed: []
patterns_deprecated:
  - pattern: "from cowork_assembler import"
    replacement: "from plugin_assembler import"
  - pattern: "CoworkAdapter (sync_agents)"
    replacement: "PluginPackAdapter"
files_affected:
  - CLAUDE.md
  - AGENTS.md
  - CODEX.md
  - .gemini/GEMINI.md
  - docs/references/agent-taxonomy.md
  - docs/generated/skill-manifest.json
  - docs/generated/skill-registry.md
  - scripts/install.sh
  - skills/onboard/references/mode-status.md
  - skills/ai/scripts/sync_agents/adapters/__init__.py
  - skills/ai/scripts/sync_agents/engine.py
```
