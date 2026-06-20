---
title: Plugin, Client, And Skill Distribution Governance
summary: Architecture decisions that define how skills, plugin packs, client exports,
  registries, and releaseable distributions stay decoupled but coherent.
tags:
- plugin-client-and-skill-distribution-governance
- dashboard-and-browse-surface-governance
- platform-admin-and-skill-quality-commands
- command
- plugin
- client
- skill
- distribution
aliases:
- Client wrapper governance
- Generated client surface governance
- Multi-target plugin packaging
- Plugin-pack assembly governance
related:
- '[[dashboard-and-browse-surface-governance]]'
- '[[platform-admin-and-skill-quality-commands]]'
created: '2026-04-23T10:46:56Z'
_page_type: concept
_hub: command
_sources:
- adr:adrs/ADR-008-plugin-system.md
- adr:adrs/ADR-012-plugin-extraction-guide.md
- adr:adrs/ADR-024-mcp-package-decoupling.md
- adr:adrs/ADR-029-plugin-architecture-refactoring.md
- adr:adrs/ADR-031-claude-code-native-capabilities.md
- adr:adrs/ADR-447-unified-skill-scorer.md
- adr:adrs/ADR-470-unified-skill-scorer.md
- adr:adrs/ADR-492-type-aware-skill-scoring-tier-gates.md
- adr:adrs/ADR-503-distribution-plugins.md
- adr:adrs/ADR-524-managed-skill-lifecycle.md
- adr:adrs/ADR-551-skill-group-and-release-enablement.md
- adr:adrs/archive/implemented-adr-ledger.md
- page:skills/plugin-pack/SKILL.md
_source_fingerprint: f0b31909c7e4710631ba118c199dee628e7601def9a06af81e1a352a58ed4222
_compiler_version: concept-article-v4
_updated: '2026-05-03T13:17:12Z'
_cites:
- '[[adr:adrs/ADR-008-plugin-system.md]]'
- '[[adr:adrs/ADR-012-plugin-extraction-guide.md]]'
- '[[adr:adrs/ADR-024-mcp-package-decoupling.md]]'
- '[[adr:adrs/ADR-029-plugin-architecture-refactoring.md]]'
- '[[adr:adrs/ADR-031-claude-code-native-capabilities.md]]'
- '[[adr:adrs/ADR-447-unified-skill-scorer.md]]'
- '[[adr:adrs/ADR-470-unified-skill-scorer.md]]'
- '[[adr:adrs/ADR-492-type-aware-skill-scoring-tier-gates.md]]'
- '[[adr:adrs/ADR-503-distribution-plugins.md]]'
- '[[adr:adrs/ADR-524-managed-skill-lifecycle.md]]'
- '[[adr:adrs/ADR-551-skill-group-and-release-enablement.md]]'
- '[[adr:adrs/archive/implemented-adr-ledger.md]]'
- '[[page:skills/plugin-pack/SKILL.md]]'
_mentions:
- '[[concepts/dashboard-and-browse-surface-governance]]'
- '[[concepts/platform-admin-and-skill-quality-commands]]'
_relates_to:
- '[[client]]'
- '[[command]]'
- '[[dashboard-and-browse-surface-governance]]'
- '[[distribution]]'
- '[[platform-admin-and-skill-quality-commands]]'
- '[[plugin]]'
- '[[skill]]'
_entity_tier: 3
---

# Plugin, Client, And Skill Distribution Governance

## Compiled truth

### Current Thesis

These ADRs define the contract boundary between native Augur skills and the many client or plugin surfaces that expose them. The durable rule is that packaging, distribution, client-specific state, and generated wrappers must follow the skill contract instead of replacing it.

### What This Page Knows

Read together, these decisions govern plugin architecture, extraction and packaging, MCP/package decoupling, client-native capability support, distribution plugins, managed skill lifecycle, type-aware skill scoring, Gemini plugin-pack support, supported client-state cleanup, and runtime IDE registry behavior. The common pattern is controlled projection: Augur wants many client surfaces, but it keeps those surfaces safe by making skill-owned contracts, registries, and distribution rules explicit rather than letting each client evolve its own truth. The ledger connects plugin packaging, wrapper generation, purge workflows, and runtime registry behavior. Together they define a governance problem: each client needs useful capability exposure without letting generated files become unmanaged source inventory. The source identifies plugin-pack as the canonical owner for the old packaging flow and describes how profiles, assemblers, formatters, and validation checks produce client-specific bundles. This is distribution governance because it defines both what ships and how to verify it.

### Key Dimensions

- Client packaging and registry decisions are treated as architecture, not ad hoc sync output.
- Client-specific formatters
- Client-state cleanup and runtime registry ownership preserve a hard boundary between Augur-managed exports and user-owned client state.
- Command wrapper generation
- Dashboard packaging surface
- Manifest validation
- Plugin-pack assembly
- Runtime IDE registry
- Scoring and lifecycle rules keep skill distribution tied to quality gates rather than only to availability.
- Shared plugin assembler
- Skill-owned workflow contracts remain canonical even when several IDEs or plugin packs expose the same capability.
- Supported client-state cleanup
- Target profiles

### Recent Shifts

- Codex, Gemini, Copilot, and Cowork are treated as explicit packaging targets rather than one-off exports.
- Distribution and client support moved from repo-only assumptions toward explicit plugin-pack and marketplace-aware architecture.
- Gemini extension support and runtime registry work made multi-client exposure more explicit.
- Registry, scoring, and lifecycle decisions now make multi-client exposure governable instead of depending on wrappers alone.

### Open Tensions

- Client-native packaging improves reach, but every new client increases the pressure to duplicate logic outside the skill contract.
- Each platform needs native output conventions, but the skill contract should remain the shared source of truth.
- Managed lifecycle and quality gates protect the ecosystem, but they also make distribution slower when the contract is still evolving.
- More client support improves reach but increases the chance that generated outputs are mistaken for source material.

### How to Use This

Use this page when the question is about how a skill should be packaged, discovered, scored, registered, or projected into a client such as Gemini, Claude Code, VS Code, or an extension/plugin surface. Start here before editing wrappers or adapters because the key architectural question is whether the client surface still follows the native skill contract.

### Open Questions

- How much lifecycle gating is necessary before distribution governance starts slowing down legitimate capability rollout?
- How much per-target filtering should happen in profiles versus formatter code?
- Which client-specific capabilities deserve first-class architecture and which should remain thin projections over the same core skill contract?
- Which generated client artifacts should be indexed for debugging but excluded from durable wiki source inventory?

### Source Basis

- `adr:adrs/ADR-008-plugin-system.md`: Augur had 39 skills spread across `plugins/{factory,vertical,services}/` directories, each with SKILL.
- `adr:adrs/ADR-012-plugin-extraction-guide.md`: This guide documents the complete refactoring patterns established during ADR-012 implementation.
- `adr:adrs/ADR-024-mcp-package-decoupling.md`: Augur will be open-sourced for multiple users.
- `adr:adrs/ADR-029-plugin-architecture-refactoring.md`: **Supersedes**: Extends ADR-015-three-tier-plugin-architecture.
- `adr:adrs/ADR-031-claude-code-native-capabilities.md`: > **Note**: This ADR has been superseded by ADR-046, which implements the crew orchestration bridge including subagent profiles, chain commands, hooks integration, and swarm presets for Claude Code.
- `adr:adrs/ADR-447-unified-skill-scorer.md`: > **Superseded by ADR-492** (Type-Aware Skill Scoring with Behavioral Tier Gates).
- `adr:adrs/ADR-470-unified-skill-scorer.md`: > **Superseded by ADR-492** (Type-Aware Skill Scoring with Behavioral Tier Gates).
- `adr:adrs/ADR-492-type-aware-skill-scoring-tier-gates.md`: ADR-447 and ADR-470 both defined a "unified skill scorer" with 4 dimensions and a single flat weight set (instruction 30%, product 40%, UI 15%, wiring 15%).
- `adr:adrs/ADR-503-distribution-plugins.md`: Augur is only installable by cloning the repo and running install.
- `adr:adrs/ADR-524-managed-skill-lifecycle.md`: The current skill architecture drifted into two incompatible models:.
- `adr:adrs/ADR-551-skill-group-and-release-enablement.md`: Augur currently mixes several unrelated concerns inside skill metadata and catalog behavior:.
- `adr:adrs/archive/implemented-adr-ledger.md`: Before this decision, removing Augur from those surfaces required manual cleanup across project-local files, global client directories, generated MCP configs, plugin-pack installs, and orphaned exports ADR-558 shows client cleanup is part of the distribution contract.

### Related Concepts

- [[concepts/dashboard-and-browse-surface-governance]]
- [[concepts/platform-admin-and-skill-quality-commands]]

## Timeline

- _at: 2026-05-03T13:17:12Z  _source: adr:adrs/ADR-008-plugin-system.md
  Augur had 39 skills spread across `plugins/{factory,vertical,services}/` directories, each with SKILL.

- _at: 2026-05-03T13:17:12Z  _source: adr:adrs/ADR-012-plugin-extraction-guide.md
  This guide documents the complete refactoring patterns established during ADR-012 implementation.

- _at: 2026-05-03T13:17:12Z  _source: adr:adrs/ADR-024-mcp-package-decoupling.md
  Augur will be open-sourced for multiple users.

- _at: 2026-05-03T13:17:12Z  _source: adr:adrs/ADR-029-plugin-architecture-refactoring.md
  **Supersedes**: Extends ADR-015-three-tier-plugin-architecture.

- _at: 2026-05-03T13:17:12Z  _source: adr:adrs/ADR-031-claude-code-native-capabilities.md
  > **Note**: This ADR has been superseded by ADR-046, which implements the crew orchestration bridge including subagent profiles, chain commands, hooks integration, and swarm presets for Claude Code.

- _at: 2026-05-03T13:17:12Z  _source: adr:adrs/ADR-447-unified-skill-scorer.md
  > **Superseded by ADR-492** (Type-Aware Skill Scoring with Behavioral Tier Gates).

- _at: 2026-05-03T13:17:12Z  _source: adr:adrs/ADR-470-unified-skill-scorer.md
  > **Superseded by ADR-492** (Type-Aware Skill Scoring with Behavioral Tier Gates).

- _at: 2026-05-03T13:17:12Z  _source: adr:adrs/ADR-492-type-aware-skill-scoring-tier-gates.md
  ADR-447 and ADR-470 both defined a "unified skill scorer" with 4 dimensions and a single flat weight set (instruction 30%, product 40%, UI 15%, wiring 15%).

- _at: 2026-05-03T13:17:12Z  _source: adr:adrs/ADR-503-distribution-plugins.md
  Augur is only installable by cloning the repo and running install.

- _at: 2026-05-03T13:17:12Z  _source: adr:adrs/ADR-524-managed-skill-lifecycle.md
  The current skill architecture drifted into two incompatible models:.

- _at: 2026-05-03T13:17:12Z  _source: adr:adrs/ADR-551-skill-group-and-release-enablement.md
  Augur currently mixes several unrelated concerns inside skill metadata and catalog behavior:.

- _at: 2026-05-03T13:17:12Z  _source: adr:adrs/archive/implemented-adr-ledger.md
  ADR-558 shows client cleanup is part of the distribution contract.
