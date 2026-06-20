---
id: ops-audit
description: Audit context usage across agents and run the orchestration audit workflow in isolated context
skill: augur-core
tags: []
x-augur-export-command: false
---

<!-- AUGUR_ARGUMENT_CONTRACT_V1 -->
## Argument Handling (Auto)

1. Parse runtime arguments from `$ARGUMENTS`.
2. If `$ARGUMENTS` is empty, parse text after `/ops-audit` in the user request.
3. Preserve argument tokens exactly, including flags and order.
4. If arguments are present, execute the matching sub-command or flag path in this command.
5. Only use the command's default behavior when arguments are truly empty.
6. If arguments are unrecognized, return valid usage instead of silently defaulting.

Run in isolated context to prevent polluting active conversation.

Audit context window usage and optimization across all agents.

Load and execute the context audit workflow:

Read and follow the instructions in `skills/ai/commands/orch-audit.md`

## Usage

```bash
/ops-audit
```

## Examples

- `/ops-audit` — Default command invocation
