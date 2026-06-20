---
status: Implemented
date: 2026-03-23
deciders:
  - Gur Sannikov
related:
  - ADR-163
  - ADR-438
hub: system
tags:
  - skills
  - portability
  - mcp
  - file-operations
superseded_by: null
---

# ADR-488: Native File Ops for Skills

## Context

Many skills route their own file operations through MCP tools (mcp__augur__file-read, file-write, file-edit, file-list, file-search, file-delete). This creates an unnecessary dependency on the MCP server for operations the agent can perform natively, making skills non-portable and adding latency. This was never a deliberate design choice — it was the path of least resistance when skills were being written.

The portable skills pack (one-click onboarding) requires skills that work without the MCP server. Skills that only need to read/write their own data should use the agent's native file tools.

## Decision

Skills use the agent's native file tools for their own data. MCP is reserved for cross-skill services and shared infrastructure.

### The Rule

| Operation | Use | Rationale |
|---|---|---|
| Read/write skill's own data files | Agent's native Read/Write/Edit | No server roundtrip needed |
| Search within skill's own data | Agent's native Grep | Direct access is faster |
| List skill's own files | Agent's native Glob/LS | No MCP overhead |
| RAG-indexed search across all skills | MCP | Requires server-side index |
| Cross-skill data access | MCP | Controlled API boundary |
| Background service queries | MCP | Requires running process |
| Server-side AI execution | MCP | Per CLAUDE.md rule #10 |
| Binary file operations | MCP | Agent tools may not handle binary |

### Data Location Pattern

Every portable skill's SKILL.md includes:

```
## Data Location

This skill stores data in `assets/seeds/` within this skill folder.
If Augur is fully installed, data may also be at the vault path — prefer that if it exists.
```

### SkillDataStore Change

`_resolve_data_dir()` in `src/mcp/plugin_utils.py` now returns `self.assets_seed_dir` when no vault is configured, instead of `self.skill_path / "data"`. This allows standalone skills to read/write directly to their seed directory.

### Portability Frontmatter

Skills declare portability via:

```yaml
x-augur-portable: true
x-augur-upgrade-hook: "contextual message about what full system adds"
```

The build script (`scripts/build_skills_pack.py`) filters on `x-augur-portable: true` to assemble the portable pack.

## Consequences

### Positive

- Skills that comply become candidates for the portable pack
- Performance improvement — eliminates agent-MCP-filesystem roundtrip
- Reliability improvement — no MCP crash breaks a skill's own file operations
- Token cost reduction — native tool calls use fewer tokens
- Skills are easier to test in isolation

### Negative

- Migration effort across ~114 MCP-dependent skills
- Risk of breaking skills if MCP file-* calls have special behavior (binary, multi-read)

### Neutral

- No user-facing behavior change — same data, same files, different access path
- MCP remains the right choice for cross-skill and service operations

## Alternatives Considered

### Alternative 1: All Skills Always Use MCP

Keep the status quo where every file operation goes through MCP.

Rejected because: prevents portability, adds unnecessary latency, creates single point of failure for basic file operations.

### Alternative 2: Ship a Headless MCP Server with the Skills Pack

Include a lightweight MCP server so skills can keep their MCP calls.

Rejected because: adds runtime dependency (Python process), maintenance burden for two packaging modes, and the fundamental problem is that basic file ops shouldn't need a server.

## References

- Design spec: `docs/superpowers/specs/2026-03-23-native-file-ops-for-skills-design.md`
- One-click onboarding spec: `docs/superpowers/specs/2026-03-23-one-click-onboarding-design.md`
- Implementation: `src/mcp/plugin_utils.py` (SkillDataStore._resolve_data_dir)
- Build script: `scripts/build_skills_pack.py`
- ADR-163: Plugin Decentralization

## Impact Manifest

```yaml
impact:
  paths_renamed: []
  apis_changed:
    - "SkillDataStore._resolve_data_dir() fallback changed from skill_path/data to assets_seed_dir"
  patterns_deprecated:
    - "Using mcp__augur__file-* for intra-skill file operations"
  files_affected:
    - "src/mcp/plugin_utils.py"
    - "scripts/build_skills_pack.py"
    - "skills/*/SKILL.md (portable skills)"
```
