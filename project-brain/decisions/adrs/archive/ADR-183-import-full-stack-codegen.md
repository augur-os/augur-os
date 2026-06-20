---
status: Implemented
date: '2026-02-28'
deciders:
- Gur Sannikov
related: []
hub: null
tags:
- import
- full
- stack
- code
- generation
superseded_by: null
---

# ADR-183: /import Full-Stack Code Generation

## Context

`/import` currently stops at writing data files into `augur/data/`. It does not produce dashboard tabs, API routes, MCP tools, or augur.yaml contributions — leaving imported data invisible in the UI and unreachable via MCP. Users must manually build the full stack after import, which is error-prone and time-consuming.

## Decision

Upgrade `/import` to generate the complete hub stack using **template-based code generation**. The import pipeline gains a new Stage 4 (Code Generation) that:

1. **Scans data** and classifies each directory into a data shape
2. **Maps each shape** to a template that generates TSX tabs, API routes, MCP tool entries, and augur.yaml contributions
3. **Composes outputs** into the final file set

### 5 Templates

| Template | Detects | Generates |
|----------|---------|-----------|
| `knowledge-browser` | Directory with `.md` files | KnowledgeTab.tsx + knowledge API route + MCP list/get tools |
| `project-board` | YAML with `id`/`title`/`status` arrays | ProjectsTab.tsx + projects API route + MCP list/get tools |
| `asset-gallery` | Binary files (PDF, PNG, JPG) | AssetsTab.tsx + assets API route + MCP list tool |
| `data-table` | YAML arrays with simple objects | DataTab.tsx + data API route + MCP get tool |
| `overview` | Always generated | page.tsx router + OverviewTab.tsx + layout.tsx + loading.tsx |

### Updated Pipeline

```
Stage 1: Deep Scan       → data shapes detected
Stage 2: Blueprint        → user confirms tabs + layout
Stage 3: ADR              → documents the plan
Stage 4: Code Generation  → templates emit full stack (NEW)
Stage 5: Mount + Verify   → mount-plugins, build check
```

### Existing Hub Integration

When importing into an existing skill: preserve existing tabs/pages/routes, append new entries to augur.yaml, generate new components alongside existing ones, merge MCP tools.

## Consequences

### Positive

- `/import ~/folder` produces a fully working hub with visible dashboard tabs, API routes, and MCP tools
- Deterministic output — same data always generates same code
- Consistent with existing hub patterns (knowledge browser, project board, etc.)
- `/harden` can audit generated hubs immediately after import

### Negative

- Templates may need extension for novel data shapes not covered by the 5 templates
- Generated code is a starting point — complex hubs still need manual refinement
- Agent-generated code (not scripted) means output quality depends on agent performance

### Neutral

- `/harden` remains a separate manual step for quality auditing after import
- No external codegen scripts — agent follows template patterns documented in SKILL.md

## Alternatives Considered

### LLM-only generation (no templates)

Let the agent generate all code from scratch each time. Rejected: inconsistent output, slow, expensive, doesn't leverage established patterns.

### Script-based codegen

Write a Python/Node script that generates files deterministically. Rejected: brittle to hub variations, requires maintaining template code alongside actual code, can't adapt to novel data structures.

## References

- [Design doc](../plans/2026-02-28-import-full-stack-codegen-design.md) — full template registry and architecture
- [Implementation plan](../plans/2026-02-28-import-full-stack-codegen-plan.md) — multi-stage implementation plan

## Impact Manifest

```yaml
impact:
  apis_changed:
    - function: import_pipeline
      module: plugins/ai/skills/mcp-app-factory/commands/import/SKILL.md
      breaking: false  # Added Stage 4 code generation
  files_affected:
    - glob: "plugins/ai/skills/mcp-app-factory/commands/import/SKILL.md"
    - glob: "plugins/admin/skills/updater/commands/harden/SKILL.md"
```
