---
title: Augur Project Brain Agent Instructions
brain_scope: project
status: active
owner: team
---

# Agent Instructions

This file is the project brain's portable agent-instruction source. Repo-root
`AGENTS.md`, `CODEX.md`, `CLAUDE.md`, and other client-native files remain
generated projections.

Durable instruction changes should be made in project-brain source files or the
mapped source files declared in `project-brain/config/mapped-sources.yaml`, then
projected through `sync_agents`.
