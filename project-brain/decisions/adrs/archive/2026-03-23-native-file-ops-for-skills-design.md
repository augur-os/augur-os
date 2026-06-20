# ADR-488: Native File Ops for Skills

**Date:** 2026-03-23
**Status:** Proposed
**Related:** One-Click Onboarding spec, ADR-163 (decentralization)

---

## Problem

Many skills route their own file operations through MCP tools (`mcp__augur__file-read`, `mcp__augur__file-write`, `mcp__augur__file-edit`, `mcp__augur__file-list`, `mcp__augur__file-search`, `mcp__augur__file-delete`). This creates an unnecessary dependency on the MCP server for operations the agent can perform natively, making skills non-portable and adding latency.

This was never a deliberate architectural decision — it was the path of least resistance when skills were being written.

## Decision

**Skills use the agent's native file tools for their own data. MCP is reserved for cross-skill services and shared infrastructure.**

### The Rule

| Operation | Use | Rationale |
|---|---|---|
| Read/write skill's own data files | Agent's native Read/Write/Edit | Agent is already present, no server roundtrip |
| Search within skill's own data | Agent's native Grep | Direct file access is faster and more reliable |
| List skill's own files | Agent's native Glob/LS | No MCP overhead needed |
| RAG-indexed search across all skills | MCP | Requires server-side index |
| Cross-skill data access | MCP | Controlled API boundary between skills |
| Background service queries (daemon, health) | MCP | Requires running process |
| Server-side AI execution | MCP | LLM calls happen server-side per rule #10 |
| Binary file operations | MCP | Agent tools may not handle binary safely |

### How to identify violations

A skill SKILL.md or command file references `mcp__augur__file-*` for operations on paths within its own `assets/seeds/` or vault data directory. These should be rewritten to use native agent file tools.

### How to fix

Before:
```markdown
Use the mcp__augur__file-read tool to read the career applications file at {vault}/career/applications.md
```

After:
```markdown
Read the file at {data_dir}/applications.md
If it doesn't exist, create it with the template below.
```

The agent resolves `{data_dir}` using the following pattern, which every portable skill's SKILL.md must include:

```markdown
## Data Location

This skill stores data in `assets/seeds/` within this skill folder.
If Augur is fully installed, data may also be at the vault path
(e.g., `~/Vault/Augur/{skill}/`) — prefer that if it exists.
```

This gives the agent concrete instructions for path resolution without requiring access to `SkillDataStore` or `src.config.paths`.

## Impact

- Skills that comply become candidates for the portable skills pack (`x-augur-portable: true`)
- No user-facing behavior change — same data, same files, different access path
- Performance improvement — eliminates agent → MCP → filesystem → MCP → agent roundtrip
- Reliability improvement — no MCP server crash can break a skill's own file operations
- Token cost reduction — native tool calls use fewer tokens than MCP tool calls

## Migration

### Scope

Approximately 114 skills reference MCP file tools. Not all references are violations — some legitimately access cross-skill data or use MCP-specific features (binary ops, multi-file reads).

### Approach

1. Audit each skill's MCP `file-*` references
2. Classify as intra-skill (violation) or cross-skill (legitimate)
3. Rewrite intra-skill references to use native agent file tools
4. Add `x-augur-portable: true` to skills that become fully MCP-independent
5. Skills that retain legitimate MCP dependencies keep `x-augur-portable: false` (default)

### Priority

Start with the 7 user-facing skills selected for the portable pack (reading-list, books, career, interview-coach, content, health, finance) plus the augur-upgrade utility skill. Expand to remaining skills incrementally.

## Consequences

- More skills become portable over time, growing the skills pack automatically
- Skill authors learn to default to native tools, using MCP only when necessary
- The MCP server handles fewer trivial file operations, reducing load
- Skills are easier to test in isolation without a running MCP server
