# docs/

**Purpose**: Project documentation.

## Structure
```
docs/
├── agent-topics/           # Generated topic docs for IDE agents
├── architecture-*.md       # Architecture docs (flat, prefixed)
├── developer-guide.md      # Developer onboarding
├── generated/              # Auto-generated reference docs (never hand-edit)
├── guides/                 # How-to guides
├── references/             # Design standards and patterns
├── superpowers/plans/      # Implementation plans (session artifacts)
├── superpowers/specs/      # Design specs for brainstorming output
└── user-guide.md           # User documentation
```

## Rules
- Keep architecture and guide docs in `docs/`; prefer topic-specific subfolders over ad-hoc nesting
- Agent instruction source-of-truth is `docs/agent-topics/agent-rules.md`
- ADRs live in the documents directory (`get_adr_dir()`, resolves to `get_documents_dir()/adrs/`), not in this directory

## Important
- To update IDE instructions, edit `docs/agent-topics/agent-rules.md` then run:
  `PYTHONPATH=project-brain/capabilities python3 -m skills.ai.scripts.sync_agents sync all`
- Do NOT edit CLAUDE.md, .cursorrules, etc. directly — they are auto-generated

## Data Separation (ADR-270)
- Runtime state lives outside the repo via `get_runtime_dir()` / `get_logs_dir()` / `get_cache_dir()`
- Config root is `config/`
- Memory lives in the external vault via `get_memory_dir()` — never in `docs/`
- User-editable skill data lives in the external vault via `get_skill_data_dir()`
