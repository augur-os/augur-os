---
title: Project Brain
brain_scope: project
status: active
owner: team
---

# Project Brain

`project-brain/` is the repo-local Augur project brain. It stores durable
project-owned capabilities, knowledge, decisions, policies, workflows,
identity, and reports.

The standard root files are portable brain source:

| File | Purpose |
|---|---|
| `BRAIN.yaml` | Augur manifest and project attachment |
| `IDENTITY.md` | public project-brain identity card |
| `SOUL.md` | values, tone, and behavioral boundaries |
| `USER.md` | shared project/team user context |
| `AGENTS.md` | portable agent instructions source |
| `MEMORY.md` | compact project memory entrypoint |
| `TOOLS.md` | tool conventions, not authority |
| `HEARTBEAT.md` | recurring routine intent, not scheduler state |

The default read model is project brain plus private brain. Personal data stays
in the configured private brain unless it is explicitly promoted.

Team skills live in `project-brain/capabilities/skills/`. Mapped project
material such as ADRs, plans, specs, instruction topics, workflows, and agents
is declared in `project-brain/config/mapped-sources.yaml`.
