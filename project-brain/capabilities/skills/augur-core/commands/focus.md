---
description: Focus session on a specific skill's context, tools, and data
visibility: core
---

# /focus

Focus your CLI session on a specific skill's context, narrowing MCP tools and surfacing
relevant data paths, actions, workflows, and orientation.

## Usage

- `/focus career`
- `/focus health`
- `/focus discover`
- `/focus career discover`
- `/focus`

## Workflow

1. Resolve the target skill
   - explicit argument if provided
   - otherwise infer from current dashboard/chat session
   - include `discover=true` when the `discover` flag is present
2. Call `focus-context`
   - with `{ "skill_name": "<resolved_name>" }`
   - or `{}` for inferred focus
   - add `"discover": true` when needed
3. Present the result as:

```text
Focused: {skill_name} ({bundle})

Data:    {data_dir}
Tools:   {N} active ({M} removed)
Actions: {comma-separated action labels}
Chains:  {comma-separated chain names}

{First 1-2 sentences from focus_prompt}
```

## Notes

- the dashboard uses the same `focus-context` MCP tool on page navigation
- focus is stateful until changed
- system pages use `switch-mcp-context` instead

## Examples

- `/focus career`
- `/focus discover`
- `/focus career discover`

