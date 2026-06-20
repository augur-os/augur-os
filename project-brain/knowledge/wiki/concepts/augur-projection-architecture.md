---
title: 'Augur Projection Architecture: Standard Source, Generated Adapters'
summary: Augur keeps canonical brain-authored source standard and generic, scoped
  to the Global > Personal > Project brain stack, and treats Augur-specific behavior
  — MCP tools, dashboard, governance, supply-chain guardrails, and routines — as projection
  or adapter layers. Use it to decide where a capability's source lives versus where
  its Augur-specific wiring belongs.
tags:
- augur-projection-architecture
- adaptive
- augur
- projection
- architecture
- standard
- generated
- adapters
aliases: []
related:
- '[[agent-separation-mcp-skill-claude]]'
- '[[brain-stack-and-active-brain-resolution]]'
created: '2026-05-31T19:44:31Z'
_page_type: concept
_hub: dev
_sources:
- adr:index://ADR-787
- adr:index://ADR-788
- adr:index://ADR-789
- adr:index://ADR-790
- adr:index://ADR-791
- adr:index://ADR-792
- adr:index://ADR-793
- adr:index://ADR-794
_source_fingerprint: 2aabb7343a54487f6d4e584092f85445ecf77e549a62bec1e029da00e2dab2fc
_compiler_version: concept-article-v4
_updated: '2026-05-31T19:44:31Z'
_cites:
- '[[adr:index://ADR-787]]'
- '[[adr:index://ADR-788]]'
- '[[adr:index://ADR-789]]'
- '[[adr:index://ADR-790]]'
- '[[adr:index://ADR-791]]'
- '[[adr:index://ADR-792]]'
- '[[adr:index://ADR-793]]'
- '[[adr:index://ADR-794]]'
_relates_to:
- '[[adapters]]'
- '[[adaptive]]'
- '[[architecture]]'
- '[[augur]]'
- '[[generated]]'
- '[[projection]]'
- '[[standard]]'
---


# Augur Projection Architecture: Standard Source, Generated Adapters

## Compiled truth

### Current Thesis

Augur's durable unit is brain-scoped, standard source; Augur-specific behavior is a projection or adapter layer built on top of it, not part of the canonical source.

### What This Page Knows

Across ADR-787 through ADR-794, Augur converges on a single architectural rule: keep canonical brain-authored source standard and generic, scoped to the Global > Personal > Project brain stack, and express everything Augur-specific — MCP tools, dashboard pages, governance, supply-chain guardrails, and routines automation — as projections or adapters. The Apple migration (ADR-790) was generalized into the default for all brain-authored skills (ADR-791); supply-chain guardrails (ADR-788) and a deferred trusted registry (ADR-789) layer governance without polluting source; routines goal drivers (ADR-792/793) and dual compilation (ADR-787) operate on top of that source, and brain roots adopt standard workspace files (ADR-794).

### Key Dimensions

- Brain stack: Global > Personal > Project as the durable source (ADR-789, ADR-791)
- Dual compilation: main checkout = production, worktrees = dev (ADR-787)
- Routines automation: in-session and inline-session drivers (ADR-792, ADR-793)
- Standard agent-workspace files at brain roots (ADR-794)
- Standard source vs. Augur projection/adapter boundary (ADR-790, ADR-791)
- Supply-chain guardrails as a local-first control plane (ADR-788, ADR-789)

### Recent Shifts

- ADR-791 generalized ADR-790's Apple migration into the default architecture for all brain-authored skills.
- ADR-793 corrected ADR-792's subprocess dispatch model to an inline-session execution model.

### Open Tensions

- Local guardrails shipped now (ADR-788) vs. registry, signing, and runtime trust deferred to a future program (ADR-789).
- Standard-by-default source vs. genuinely Augur-platform skills that may embed Augur specifics (ADR-791).

### How to Use This

When adding a capability, put generic logic in standard brain-scoped source; route MCP tools, dashboard pages, governance, and Browse metadata through projection/adapter layers rather than the source itself.

### Open Questions

- How will the future trusted skill registry enforce runtime trust on top of the local guardrails?
- When does a skill qualify as an 'Augur platform skill' allowed to embed Augur specifics?

### Source Basis

- `adr:index://ADR-787`: The main checkout serves the production build on :3000; worktrees run the dev (Turbopack) server on their own ports.
- `adr:index://ADR-788`: Augur will add a local-first skill and plugin supply-chain guardrail layer: an Augur lockfile, hard integrity verification, declared authority metadata, permission escalation checks, lightweight package/security scanning, MCP/CLI verification surfaces, and Browse badges.
- `adr:index://ADR-789`: Augur is a local-first brain and harness runtime. Its durable source is the resolved brain stack: Global, User, Team, and Project capabilities.
- `adr:index://ADR-790`: Augur will replace its Augur-shaped staged Apple skill with a 100% standard, Hermes-compatible Apple skill while moving Augur-specific MCP, dashboard, sync projection, and governance behavior into an external adapter layer.
- `adr:index://ADR-791`: Augur treats canonical brain-authored skill source as standard and generic by default. Augur-specific metadata, MCP tools, dashboard pages, Browse metadata, commands, policies, runtime state, and generated client files are projection or adapter concerns.
- `adr:index://ADR-792`: Add /routines goal — an in-session autonomous driver that picks a harden/clean goal and runs the ADR-755 routine orchestrator to convergence or budget exhaustion, operating in an isolated worktree and ending at 'branch ready + report'.
- `adr:index://ADR-793`: Convert the routines goal catalog-loop from a Python subprocess dispatch model to an inline-session execution model (ADR-758). The AI client drives the convergence loop in-session and uses its own Agent/Task tool as the invoker.
- `adr:index://ADR-794`: Augur will align brain roots with common agent-workspace files (IDENTITY.md, SOUL.md, USER.md, AGENTS.md, MEMORY.md, TOOLS.md).

## Timeline

- _at: 2026-05-31T19:44:31Z  _source: adr:index://ADR-787
  The main checkout serves the production build on :3000; worktrees run the dev (Turbopack) server on their own ports.

- _at: 2026-05-31T19:44:31Z  _source: adr:index://ADR-788
  Augur will add a local-first skill and plugin supply-chain guardrail layer: an Augur lockfile, hard integrity verification, declared authority metadata, permission escalation checks, lightweight package/security scanning, MCP/CLI verification surfaces, and Browse badges.

- _at: 2026-05-31T19:44:31Z  _source: adr:index://ADR-789
  Augur is a local-first brain and harness runtime. Its durable source is the resolved brain stack: Global, User, Team, and Project capabilities.

- _at: 2026-05-31T19:44:31Z  _source: adr:index://ADR-790
  Augur will replace its Augur-shaped staged Apple skill with a 100% standard, Hermes-compatible Apple skill while moving Augur-specific MCP, dashboard, sync projection, and governance behavior into an external adapter layer.

- _at: 2026-05-31T19:44:31Z  _source: adr:index://ADR-791
  Augur treats canonical brain-authored skill source as standard and generic by default. Augur-specific metadata, MCP tools, dashboard pages, Browse metadata, commands, policies, runtime state, and generated client files are projection or adapter concerns.

- _at: 2026-05-31T19:44:31Z  _source: adr:index://ADR-792
  Add /routines goal — an in-session autonomous driver that picks a harden/clean goal and runs the ADR-755 routine orchestrator to convergence or budget exhaustion, operating in an isolated worktree and ending at 'branch ready + report'.

- _at: 2026-05-31T19:44:31Z  _source: adr:index://ADR-793
  Convert the routines goal catalog-loop from a Python subprocess dispatch model to an inline-session execution model (ADR-758). The AI client drives the convergence loop in-session and uses its own Agent/Task tool as the invoker.

- _at: 2026-05-31T19:44:31Z  _source: adr:index://ADR-794
  Augur will align brain roots with common agent-workspace files (IDENTITY.md, SOUL.md, USER.md, AGENTS.md, MEMORY.md, TOOLS.md).
