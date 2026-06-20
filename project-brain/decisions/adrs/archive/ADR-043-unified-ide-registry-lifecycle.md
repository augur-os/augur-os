---
status: Implemented
date: '2026-02-06'
deciders:
- Augur Team
related: []
hub: null
tags:
- unified
- ide
- registry
- lifecycle
superseded_by: null
---

# ADR-043: Unified IDE Registry Lifecycle

## Context

IDE context routing depended on generated artifacts that could drift silently:
- Registry files existed in multiple locations with different freshness.
- MCP startup accepted missing/invalid registry state without a clear signal.
- `npm run dev` / `npm run build` did not guarantee registry regeneration.
- Pre-commit and CI did not enforce freshness for generated instruction/registry files.

This allowed stale routing metadata to survive across runs and made failures hard to diagnose.

## Decision

Adopt `data/core/ide-integration/registry.yaml` as the canonical IDE context registry and enforce its lifecycle:

1. Registry generation is wired into dashboard lifecycle:
   - `src/dashboard/package.json` runs `scripts/generate_registry.py` in `predev` and `prebuild`.
2. Registry generation is validated with a check mode:
   - `src/dashboard/scripts/generate_registry.py --check` fails when committed registry content is stale.
3. MCP validates registry health at startup:
   - `src/mcp/augur_mcp/context_injector.py` validates required sections from the canonical registry path only.
   - `src/mcp/augur_mcp/server.py` logs explicit startup health results and supports strict failure via `AUGUR_MCP_STRICT_REGISTRY=1`.
4. Generated artifact freshness is enforced before commit and in CI:
   - `.pre-commit-config.yaml` runs `sync_agents.py --check` and `generate_registry.py --check`.
   - `.github/scripts/ci_check.sh` runs the same validations.
5. Legacy duplicate registry files are removed:
   - `plugins/ai/skills/ai_bridge/augur/ide-integration/registry.yaml`
   - `config/agents/registry.yaml`

## Consequences

### Positive

- Registry freshness is automatic for normal dev/build flows.
- Stale generated files are blocked before commit and surfaced in CI.
- MCP startup now reports explicit registry health instead of failing silently.
- Context metadata is rebuilt from live sources (skills, chains, workflows, dashboard hubs) instead of stale manual tables.

### Negative

- `npm run dev` / `npm run build` now depend on Python + PyYAML being available.
- Startup logs are stricter and may expose configuration gaps that were previously hidden.

### Neutral

- Runtime behavior of context filtering remains the same when registry content is valid.

## Alternatives Considered

### Alternative 1: Keep multiple registries and sync periodically

Rejected because periodic sync still permits drift windows and hidden startup failures.

### Alternative 2: Build registry lazily inside MCP only

Rejected because dashboard build/dev and pre-commit would still not guarantee reproducible generated artifacts in git.

## References

- `src/dashboard/scripts/generate_registry.py`
- `src/mcp/augur_mcp/context_injector.py`
- `src/mcp/augur_mcp/server.py`
- `.pre-commit-config.yaml`
