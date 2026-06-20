---
status: Implemented
date: '2026-03-24'
deciders:
- Gur Sannikov
related:
- ADR-437
hub: null
tags:
- distribution
- obsidian
- vscode
- install
- marketplace
superseded_by: null
---

# ADR-503: Distribution Plugin Architecture for Obsidian and VS Code

## Decision summary

Build thin platform-native plugins for Obsidian and VS Code that implement a 5-capability contract: 1. **Detect** — check if Augur is already installed 2. **Install** — call `scripts/install.sh --from <platform>` 3. **Configure** — set up MCP config for the platform 4. **Status** — show connection...

## Status notes

 | Flipped to Implemented 2026-05-10 per pass-2 code-evidence triage.
