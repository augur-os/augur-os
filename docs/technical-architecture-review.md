# Technical Architecture Review

This guide is for external engineers reviewing the open-source Augur repository. It points to the shortest path through the architecture and names the release-visible evidence behind each major claim.

## Two-Minute Route

1. Read [README.md](../README.md) for the product boundary and supported review path.
2. Read [architecture-overview.md](architecture-overview.md) for the Harness, brain layering, Connection Layer, runtime substrate, and trust boundaries.
3. Read [architecture-mcp-gateway.md](architecture-mcp-gateway.md), [architecture-sync-agents.md](architecture-sync-agents.md), [architecture-memory.md](architecture-memory.md), and [architecture-skills.md](architecture-skills.md) for implementation-specific detail.
4. Read the brain-layering sections in [architecture-overview.md](architecture-overview.md), [architecture-sync-agents.md](architecture-sync-agents.md), and [architecture-memory.md](architecture-memory.md). Team brain governance is part of the commercial tier; the OSS docs describe the architectural slot without shipping the commercial control plane.
5. Read [architecture-mcp-gateway.md](architecture-mcp-gateway.md), [architecture-capability-exposure.md](architecture-capability-exposure.md), and [architecture-daemon.md](architecture-daemon.md) for trust boundaries, exposed surfaces, and background execution limits.

## What Augur Is

Augur is local-first harness and brain infrastructure for native AI clients. The open-source runtime owns local storage, skills, instructions, hooks, subagents, client projection, MCP execution, dashboard surfaces, and knowledge/memory plumbing. The active AI client remains the default reasoning layer.

## Architecture Claims And Repo Evidence

| Claim | Repo evidence |
|---|---|
| The Harness is a five-layer architecture, not a prompt folder | `docs/architecture-overview.md`, `project-brain/capabilities/skills/`, `docs/agent-topics/agent-rules.md`, `.githooks/`, `project-brain/capabilities/skills/ai/scripts/sync_agents/adapters/` |
| One source projects into multiple AI clients | `docs/architecture-sync-agents.md`, `project-brain/capabilities/skills/ai/scripts/sync_agents/`, `project-brain/capabilities/skills/ai/scripts/sync_agents/tests/`, `tests/integration/test_sync_agents.py` |
| Dashboard and agents share the MCP execution boundary | `docs/architecture-mcp-gateway.md`, `src/mcp/`, dashboard MCP routes, `config/system/mcp_servers.yaml` |
| Brain context is layered, not a single opaque vault | `docs/architecture-overview.md`, `docs/architecture-sync-agents.md`, `docs/architecture-memory.md` |
| Memory and knowledge stay local-first and inspectable | `docs/architecture-memory.md`, `docs/architecture-vault.md`, `project-brain/`, configured vault paths, `src/config/paths.py` |
| Trust boundaries are documented with current limits | `docs/architecture-mcp-gateway.md`, `docs/architecture-capability-exposure.md`, `docs/architecture-daemon.md` |

Generated client files such as `AGENTS.md`, `CODEX.md`, `.codex/skills/`, and `.gemini/GEMINI.md` are runtime outputs. The public release evidence is the generator source, adapters, policy, and tests that produce those files, not a hand-checked-in copy of every generated surface.

## Brain Tiers

Augur uses a layered brain model:

| Tier | Meaning | OSS/commercial boundary |
|---|---|---|
| Global | Augur core runtime and shipped capabilities | Open-source runtime |
| User | Personal brain: private skills, memory, profile, knowledge | Open-source runtime |
| Team | Organization-shared policy, governance, shared memory/capabilities | Commercial tier |
| Project | Repo-local brain with source-controlled project context and capabilities | Open-source runtime |

Precedence is most-specific-wins for capability/content selection: Project > Team > User > Global. The open-source repo implements the personal and project runtime foundation; the commercial product uses the same architectural spine for team governance and organization deployment.

## OSS Boundary

The open-source repository is the personal/project runtime. It should not be read as a completed enterprise governance product. Team brain, organization policy, managed-device enforcement, and full enterprise governance are commercial-tier architecture built on the same substrate.

## What To Inspect Next

- For client projection: [architecture-sync-agents.md](architecture-sync-agents.md)
- For MCP execution: [architecture-mcp-gateway.md](architecture-mcp-gateway.md)
- For memory/data: [architecture-memory.md](architecture-memory.md)
- For skills: [architecture-skills.md](architecture-skills.md)
- For trust boundaries: [architecture-capability-exposure.md](architecture-capability-exposure.md)
