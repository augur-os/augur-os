---
title: Runtime Control And Access Actions
summary: Runtime access actions are read-first entrypoints for ask/search, daemon
  state, loop controls, onboarding, remote access, and document intake. They matter
  because users and agents need truthful orientation before choosing a repair, automation,
  or ingestion path.
tags:
- runtime-control-and-access-actions
- daemon-maintenance-command-loops
- knowledge-automation-command-loops
- platform-admin-and-skill-quality-commands
- command
- runtime
- control
- access
aliases:
- command access actions
- runtime access actions
related:
- '[[daemon-maintenance-command-loops]]'
- '[[knowledge-automation-command-loops]]'
- '[[platform-admin-and-skill-quality-commands]]'
created: '2026-04-23T10:46:56Z'
_page_type: concept
_hub: command
_sources:
- action:skills/augur-core/augur/actions/ask-overview.md
- action:skills/augur-core/augur/actions/search-overview.md
- action:skills/daemon/augur/actions/auto-heal-validate-overview.md
- action:skills/daemon/augur/actions/dev-loops-overview.md
- action:skills/onboard/augur/actions/onboard-action.md
- action:skills/platform-admin/augur/actions/remote-access-overview.md
- page:skills/daemon/SKILL.md
- page:skills/document-extractor/SKILL.md
_source_fingerprint: 75ddabc78c32c73281a238b620380ee179a4ca62c1e3d619d595b4f7889cc902
_compiler_version: concept-article-v4
_updated: '2026-05-03T13:27:14Z'
_cites:
- '[[action:skills/augur-core/augur/actions/ask-overview.md]]'
- '[[action:skills/augur-core/augur/actions/search-overview.md]]'
- '[[action:skills/daemon/augur/actions/auto-heal-validate-overview.md]]'
- '[[action:skills/daemon/augur/actions/dev-loops-overview.md]]'
- '[[action:skills/onboard/augur/actions/onboard-action.md]]'
- '[[action:skills/platform-admin/augur/actions/remote-access-overview.md]]'
- '[[page:skills/daemon/SKILL.md]]'
- '[[page:skills/document-extractor/SKILL.md]]'
_mentions:
- '[[concepts/daemon-maintenance-command-loops]]'
- '[[concepts/knowledge-automation-command-loops]]'
- '[[concepts/platform-admin-and-skill-quality-commands]]'
_relates_to:
- '[[access]]'
- '[[command]]'
- '[[control]]'
- '[[daemon-maintenance-command-loops]]'
- '[[knowledge-automation-command-loops]]'
- '[[platform-admin-and-skill-quality-commands]]'
- '[[runtime]]'
_entity_tier: 3
---

# Runtime Control And Access Actions

## Compiled truth

### Current Thesis

Runtime access actions are the orientation layer before repair: they expose what the system knows, what services are doing, which onboarding pieces are connected, and which access surfaces are available.

### What This Page Knows

The source set spans ask and search entrypoints, self-heal validation, adaptive loop status, onboarding health, remote access, daemon control, and document extraction. Together they describe a user-facing control surface that should answer the first operational question before deeper commands mutate state: what is available, what is stale, what is connected, and which lower-level owner should take over.

### Key Dimensions

- Ask and search actions orient knowledge work before a compile, save, or reindex path is chosen.
- Daemon and dev-loop actions expose long-running service state, healing, scheduler ownership, and autonomous cycle controls.
- Document extraction sits beside runtime access because files often enter the system as operational intake before becoming durable knowledge.
- Onboarding and remote-access actions expose installation, platform connectivity, and network entrypoints for local-first operation.

### Recent Shifts

- The generated query now links to the current knowledge-automation-command-loops concept, keeping access actions connected to the active knowledge maintenance surface.

### Open Tensions

- An orientation action must show enough state to be useful without becoming a second copy of the command it points to.
- Remote access and document intake are user-facing entrypoints, but their implementation details still belong to their owning skills.

### How to Use This

Start here when the user asks what Augur knows, whether services are healthy, how to access the dashboard remotely, whether onboarding is complete, or how a document should enter the system. After orientation, hand off to daemon maintenance, knowledge automation, platform admin, or document extraction for execution.

### Open Questions

- How should Browse expose these access paths without turning them into implementation noise?
- Which access actions should display live state directly, and which should only link to the owning command page?

### Source Basis

- `action:skills/augur-core/augur/actions/ask-overview.md`: View reflective `/ask` workflows from augur-core.
- `action:skills/augur-core/augur/actions/search-overview.md`: View knowledge search, RAG status, and index maintenance workflows from augur-core.
- `action:skills/daemon/augur/actions/auto-heal-validate-overview.md`: View the absorbed auto-heal-validate workflow from the consolidated daemon surface.
- `action:skills/daemon/augur/actions/dev-loops-overview.md`: View adaptive loop status, split scheduler ownership, healing, and autonomous cycle controls.
- `action:skills/onboard/augur/actions/onboard-action.md`: Display the current Augur installation state including install source, connected platforms, vault scaffolding status, dashboard health, and MCP server connectivity.
- `action:skills/platform-admin/augur/actions/remote-access-overview.md`: View Network access to the Augur dashboard and MCP server for remote users.
- `page:skills/daemon/SKILL.md`: Use when managing background services, checking daemon status, configuring autoloops, debugging self-heal pipeline issues, or controlling the unified daemon via macOS launchd or Windows Task Scheduler.
- `page:skills/document-extractor/SKILL.md`: Universal document-to-Markdown extraction powered by MarkItDown.

### Related Concepts

- [[concepts/daemon-maintenance-command-loops]]
- [[concepts/knowledge-automation-command-loops]]
- [[concepts/platform-admin-and-skill-quality-commands]]

## Timeline

- _at: 2026-05-03T13:27:14Z  _source: action:skills/augur-core/augur/actions/ask-overview.md
  View reflective `/ask` workflows from augur-core.

- _at: 2026-05-03T13:27:14Z  _source: action:skills/augur-core/augur/actions/search-overview.md
  View knowledge search, RAG status, and index maintenance workflows from augur-core.

- _at: 2026-05-03T13:27:14Z  _source: action:skills/daemon/augur/actions/auto-heal-validate-overview.md
  View the absorbed auto-heal-validate workflow from the consolidated daemon surface.

- _at: 2026-05-03T13:27:14Z  _source: action:skills/daemon/augur/actions/dev-loops-overview.md
  View adaptive loop status, split scheduler ownership, healing, and autonomous cycle controls.

- _at: 2026-05-03T13:27:14Z  _source: action:skills/onboard/augur/actions/onboard-action.md
  Display the current Augur installation state including install source, connected platforms, vault scaffolding status, dashboard health, and MCP server connectivity.

- _at: 2026-05-03T13:27:14Z  _source: action:skills/platform-admin/augur/actions/remote-access-overview.md
  View Network access to the Augur dashboard and MCP server for remote users.

- _at: 2026-05-03T13:27:14Z  _source: page:skills/daemon/SKILL.md
  Use when managing background services, checking daemon status, configuring autoloops, debugging self-heal pipeline issues, or controlling the unified daemon via macOS launchd or Windows Task Scheduler.

- _at: 2026-05-03T13:27:14Z  _source: page:skills/document-extractor/SKILL.md
  Universal document-to-Markdown extraction powered by MarkItDown.
