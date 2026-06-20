---
id: discover
description: Show Augur capabilities, available commands, and system state
skill: augur-core
tags: []
x-augur-export-command: true
---

Show the Augur capability manifest and available commands.

## Usage

```bash
aug discover              # Full capability manifest
aug discover --commands   # List available slash commands with descriptions
aug discover --hub command
aug discover --compact
aug discover --format json
```

## Dispatch

1. If `ARGUMENTS` contains `--commands` or the first argument is `commands`:
   call `list-commands` MCP tool and format the output as a table of available
   slash commands with their descriptions. Group by visibility tier (core, dev, ops).
2. Otherwise: use the same manifest assembler as the `discover-augur` MCP surface.
