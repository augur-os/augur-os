---
status: Implemented
date: '2026-03-08'
deciders:
- Gur Sannikov
related: []
hub: null
tags:
- standardized
- markdown
- action
- instructions
superseded_by: null
---

# ADR-263: Standardized Markdown Action Instructions

## Context

Dashboard `runAction` calls contain 124 inline `description`/`prompt` strings across 64 TSX files. These inline strings are:

- **Invisible to agents**: CLI/IDE agents can't discover or reuse action instructions without parsing TSX source code.
- **Untestable**: No way to validate prompt quality, structure, or completeness without running the dashboard.
- **Inconsistent**: Descriptions range from empty strings to 500+ character template literals with dynamic context — no standard format.
- **Duplicated**: The same instruction content appears in both TSX `description` fields and `augur/data/actions/*.yaml` prompt fields with no single source of truth.
- **Not scannable**: The `auto-dead-ui` scanner detects contextless/shallow prompts but can't fix them because there's no standard to fix toward.

Industry consensus (Claude API docs, Semantic Kernel, LangChain) has converged on file-based markdown templates with `{{handlebars}}` variable syntax as the standard for AI prompt management. Augur already has 10 such files in the organizer/advisor plugins, and `ActionDef` already supports a `prompt_file` field.

## Decision

1. **Standardize on markdown template files** at `plugins/{bundle}/skills/{skill}/augur/data/prompts/{action-id}.md` with YAML frontmatter and XML-tagged body sections (`<instructions>`, `<context>`, `<task>`).

2. **Serve templates via API route** `/api/prompts/[action-id]` — raw for agents, rendered (with `{{variable}}` substitution) for UI components.

3. **Context resolution is caller-dependent**:
   - Dashboard UI passes variables directly from component state.
   - CLI/IDE agents read `context_hints` from frontmatter and gather data themselves via MCP tools/APIs.
   - No shared programmatic resolver — agents are smart enough to resolve context from hints.

4. **Create `usePromptTemplate` hook** for dashboard components to load and render templates.

5. **Create `auto-markdowns` auto-command** (`plugins/dev/skills/auto-markdowns/`) in the `skill-standards` loop at tier 2 to scan/fix template quality:
   - d0: Missing template files
   - d1: Missing `<instructions>` or `<task>` sections
   - d2: TSX still uses inline description (migration incomplete)
   - d3: Shallow/generic instructions, missing entity context

6. **Migrate prompt quality checks** from `auto-dead-ui` to `auto-markdowns` — `auto-dead-ui` keeps button/link/fetch checks only.

### Template format

```markdown
---
action: growth-add-habit
description: Add a new career development habit
dispatch: ide
input_variables:
  - name: habits_count
    type: number
    description: "Number of existing habits"
context_hints:
  - tool: career/habits
    description: "Fetch current habits list"
---

<instructions>
Add a new career development habit to track.
</instructions>

<context>
Existing habits ({{habits_count}}):
{{habits_list}}
</context>

<task>
Help the user define a new habit with name, frequency, and success criteria.
</task>
```

## Consequences

### Positive

- Single source of truth for action instructions — version-controlled, diffable, reviewable
- CLI/IDE agents can discover and use action instructions without dashboard
- Non-developers can edit prompt quality without touching TSX
- Nightly scanning catches prompt quality regressions
- Follows industry standard (Claude API `{{variables}}`, XML tags, Semantic Kernel file-based templates)
- `context_hints` make templates self-documenting for agent consumers

### Negative

- ~80-100 template files to create and maintain
- Migration effort: 64 TSX files need updating to use `usePromptTemplate`
- Extra API call per action button click (mitigated by 30s cache)

### Neutral

- `ActionDef.prompt_file` already exists — this extends the pattern to a standardized directory
- Existing 10 template files in organizer/advisor plugins are compatible

## Alternatives Considered

### Alternative 1: Enrich action YAML with prompt_template field

Put multi-line prompt content in `augur/data/actions/*.yaml` instead of separate `.md` files.

Rejected: YAML is awkward for long markdown (indentation sensitivity, escaping). Not as readable. Doesn't follow industry standard of file-per-prompt. Harder for non-developers to edit.

### Alternative 2: Hybrid — markdown for complex, inline for simple

Only extract prompts exceeding a complexity threshold. Simple static descriptions stay inline.

Rejected: Two systems to maintain. Scanner needs complex rules to decide which pattern. Inconsistent developer experience.

### Alternative 3: Full programmatic resolver with DSL

Templates declare `source`, `path`, and `format` fields that a Python resolver uses to programmatically fetch and format data.

Rejected: Over-engineered. Invents a custom query language. AI agents don't need a DSL — they can read `context_hints` and gather data themselves. Tight coupling to API routes makes templates brittle.

## References

- Design doc: `docs/plans/2026-03-08-markdown-instructions-design.md`
- Implementation plan: `docs/plans/2026-03-08-markdown-instructions-plan.md`
- [Claude API: Prompt Templates and Variables](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompt-templates-and-variables)
- [Claude API: Prompting Best Practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices)
- [Microsoft Semantic Kernel: Handlebars Templates](https://learn.microsoft.com/en-us/semantic-kernel/concepts/prompts/handlebars-prompt-templates)
- ADR-130: Action discovery from distributed plugin directories
- ADR-163: Plugin decentralization
- ADR-200: Auto-command protocol (scan/fix)

## Impact Manifest

```yaml
impact:
  paths_renamed: []
  apis_changed:
    - function: runAction
      module: useActionRunner
      breaking: false  # inline descriptions still work, migration is gradual
  patterns_deprecated:
    - grep: "runAction\\(\\{[^}]*description:\\s*['\"`]"
      replacement: "Use renderPrompt(actionId, variables) from usePromptTemplate hook"
  files_affected:
    - glob: "plugins/*/skills/*/augur/dashboard/**/*.tsx"
```

## Implementation Prompt

**Team name**: `adr-263-markdown-instructions`

### Phase 1: Infrastructure
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | backend | medium | Create prompt discovery library | `src/dashboard/lib/prompts/discovery.ts` |
| 1.2 | backend | low | Create API route | `src/dashboard/app/api/prompts/[actionId]/route.ts` |
| 1.3 | frontend | low | Create usePromptTemplate hook | `src/dashboard/hooks/usePromptTemplate.ts` |

### Phase 2: Pilot + Scanner
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | content | low | Create 3 pilot templates | `plugins/*/skills/*/augur/data/prompts/*.md` |
| 2.2 | backend | medium | Implement auto-markdowns scan/fix | `plugins/dev/skills/auto-markdowns/scripts/markdown_ops.py` |
| 2.3 | backend | low | Migrate prompt checks from auto-dead-ui | `plugins/dev/skills/auto-dead-ui/scripts/dead_ui_ops.py` |

### Phase 3: Mass Migration
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | content | medium | Generate skeleton templates for all actions | `plugins/*/skills/*/augur/data/prompts/*.md` |
| 3.2 | content | high | Enrich skeletons with real instructions | `plugins/*/skills/*/augur/data/prompts/*.md` |
| 3.3 | frontend | high | Migrate TSX to usePromptTemplate | `plugins/*/skills/*/augur/dashboard/**/*.tsx` |

### Final Phase: Verification
| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Run auto-markdowns scan at d3, verify 0 issues |
| V.2 | validator | low | Run auto-dead-ui scan, verify no prompt quality regressions |
| V.3 | architect | low | Verify API route serves all templates correctly |

### Completion Criteria
- [ ] All phases executed
- [ ] d0 scan: 0 missing templates
- [ ] d2 scan: 0 inline descriptions remaining
- [ ] d3 scan: 0 shallow/generic instructions
- [ ] auto-dead-ui no longer reports prompt quality issues
- [ ] ADR status updated to Implemented
