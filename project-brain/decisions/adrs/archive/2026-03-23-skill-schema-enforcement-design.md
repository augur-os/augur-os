# Skill Schema Enforcement & Agents Migration

**Date:** 2026-03-23
**Status:** Draft
**Extends:** ADR-479 (Multi-Client Skill Structure)
**Standards:** [Agent Skills](https://agentskills.io/specification), [Claude Code Skills](https://code.claude.com/docs/en/skills), [Claude Code Plugins](https://code.claude.com/docs/en/plugins)

## Problem

After migrating 184 skills to `skills/` (ADR-479), the folder structure within each skill is inconsistent:

- 7 skills use `docs/` instead of the standard `references/`
- 1 skill has `data/` at root (should be `augur/data/` or `assets/`)
- 1 skill has `lib/` at root (should be `scripts/` or `augur/lib/`)
- 1 skill has `.augur-plugin/` and `node_modules/`
- Seeds live in `augur/seed/` but are portable templates (belong in `assets/seeds/`)
- 14 agent definitions live in `.claude/agents/` disconnected from their skills
- No CI enforcement prevents drift

Additionally, the Agent Skills open standard (agentskills.io) defines a portable schema that Augur skills should follow for cross-client compatibility. Everything portable should be at the skill root; everything Augur-specific should be inside `augur/`.

## Design

### Skill Folder Schema

Two layers: **standard** (portable, any AI client) and **augur-native** (requires Augur runtime).

```
skills/{skill-name}/
│
│  ── STANDARD LAYER (portable across AI clients) ──
│
├── SKILL.md              # REQUIRED — frontmatter + instructions
├── commands/             # OPTIONAL — slash commands (*.md)
├── references/           # OPTIONAL — on-demand documentation (*.md)
├── scripts/              # OPTIONAL — executable code (*.py, *.sh, *.js, *.mjs)
├── assets/               # OPTIONAL — static resources
│   ├── seeds/            #   Starter data / templates
│   ├── templates/        #   Document templates
│   └── ...               #   Images, schemas, lookup tables
├── examples/             # OPTIONAL — example outputs
├── modules/              # OPTIONAL — modular doc chunks (*.md)
│
│  ── AUGUR-NATIVE LAYER (requires Augur runtime) ──
│
└── augur/                # OPTIONAL — present = native skill
    ├── dashboard/        # Next.js App Router pages ONLY
    ├── data/             # Runtime config, prompts, action templates
    ├── tests/            # Skill tests (*.py, *.test.ts)
    └── lib/              # Augur-internal Python libraries
```

### Directory Rules

#### Standard Layer (Portable)

| Directory | Contents | Standard Source |
|-----------|----------|----------------|
| `SKILL.md` | Frontmatter + instructions. Required. | Agent Skills spec |
| `commands/` | Slash command `.md` files. Each creates a `/command-name`. | Claude Code (commands merged into skills) |
| `references/` | Documentation loaded on demand. Keep files focused and <500 lines. | Agent Skills spec |
| `scripts/` | Executable code: Python, Bash, JavaScript. Self-contained or with documented deps. | Agent Skills spec |
| `assets/` | Static resources: templates, images, data files, schemas, seeds. | Agent Skills spec |
| `examples/` | Example outputs showing expected format. | Claude Code extension |
| `modules/` | Modular documentation chunks (Augur convention, portable). | Augur convention |

#### Augur-Native Layer

| Directory | Contents | Rules |
|-----------|----------|-------|
| `augur/dashboard/` | Next.js App Router pages | `.tsx`, `.ts`, `.css`, `.js`, `.jsx` ONLY. No `.yaml`, `.py`, `.md`, `.json` (except `tsconfig.json`). Must follow App Router conventions (`page.tsx`, `layout.tsx`, `loading.tsx`, `error.tsx` + components). |
| `augur/data/` | Runtime config, prompts, action YAML | Augur-specific runtime data. NOT user data (that goes to vault at `get_vault_dir()/`). |
| `augur/tests/` | Skill tests | `*.py` (pytest), `*.test.ts` (jest). |
| `augur/lib/` | Augur-internal Python code | Libraries used only by Augur runtime. If code is useful standalone → `scripts/`. |

#### Banned at Skill Root

| Pattern | Reason | Migration |
|---------|--------|-----------|
| `docs/` | Use `references/` (standard name) | Move contents to `references/` |
| `data/` | Runtime data is Augur-specific | Move to `augur/data/` or `assets/` |
| `lib/` | Ambiguous ownership | Use `scripts/` (portable) or `augur/lib/` (Augur-only) |
| `seed/` (inside `augur/`) | Seeds are portable templates | Move to `assets/seeds/` |
| `.augur-plugin/` | Not needed post-ADR-479 | Delete |
| `node_modules/` | Must be gitignored | Add to `.gitignore` |
| `__pycache__/` | Must be gitignored | Add to `.gitignore` |
| `.DS_Store` | Must be gitignored | Delete |
| `.config/` | Not a skill concern | Delete |
| `requirements.txt` at root | Use `scripts/` deps or `pyproject.toml` | Move or delete |

#### Allowed Root-Level Files

Only these files are allowed at the skill root (alongside `SKILL.md`):

- `SKILL.md` (required)
- `CHANGELOG.md` (optional)
- `LICENSE.txt` / `LICENSE` (optional)
- `README.md` (optional — for external/community skills)
- `pyproject.toml` (optional — for skills with Python deps)
- `package.json` (optional — for skills with Node deps)
- `config.yaml` (optional — skill-specific config)

### Agents Migration

#### Current State

14 agent `.md` files in `.claude/agents/`:

```
.claude/agents/
├── advisor.md
├── dev-adr.md
├── dev-build.md
├── dev-debug.md
├── dev-merge.md
├── dev-rollback.md
├── dev-test.md
├── developer.md
├── devops.md
├── frontend.md
├── mcp-app-factory.md
├── test-client.md
├── test-ui.md
└── validator.md
```

Per Claude Code docs, agents can live in:
1. `.claude/agents/` (project-level, priority 2)
2. `~/.claude/agents/` (user-level, priority 3)
3. Plugin's `agents/` directory (priority 4)

Per the Claude Code plugin spec, plugins put `agents/` at the **plugin root** alongside `skills/`:

```
my-plugin/
├── .claude-plugin/
│   └── plugin.json
├── skills/
│   └── code-review/
│       └── SKILL.md
└── agents/            # Plugin-level agents
    └── code-reviewer.md
```

MiniMax uses the same pattern: `plugins/pptx-plugin/agents/`.

#### Decision

Agents are platform-neutral definitions synced to all IDE clients. They live in `plugins/agents/`:

1. **Canonical location:** `plugins/agents/` (alongside other platform integrations)
2. **Sync:** Stub generator copies to `.claude/agents/` (same as it copies skills to client dirs)
3. **Format:** Standard agent `.md` files with YAML frontmatter

```
augur/
├── skills/              # Skills
├── plugins/             # Platform integrations
│   ├── agents/          # Subagent definitions (canonical source)
│   │   ├── advisor.md
│   │   ├── frontend.md
│   │   └── ...
│   ├── obsidian/        # Obsidian community plugin
│   └── vscode/          # VS Code extension
├── .claude/agents/      # GENERATED — synced from plugins/agents/
└── .claude-plugin/
    └── plugin.json
```

#### Agent Sync

The stub generator (`scripts/generate_client_stubs.py`) gains a new sync target. Note: `.claude/agents/` is a new target type distinct from the existing skill stub targets (codex, cursor, etc.). The script needs a separate sync path for agents since the format is direct copy, not frontmatter extraction.

| Source | Target | Format |
|--------|--------|--------|
| `agents/*.md` | `.claude/agents/*.md` | Direct copy with `<!-- AUGUR-GENERATED -->` marker prepended |

The same `AUGUR-GENERATED` marker and cleanup logic applies: stale agents are deleted, user-created agents in `.claude/agents/` (without the marker) are preserved.

Agents are Claude Code-specific — no sync to Gemini, Codex, Cursor, or OpenCode. If other clients add agent support in the future, extend the sync at that time.

Phase 2 must also create `agents/README.md` (per CLAUDE.md rule 6: read README before editing any directory).

### Enforcement

#### 1. Pre-Commit Hook (extend existing `.github/scripts/validate_skill_structure.py`)

The hook already exists and is wired into `.pre-commit-config.yaml`. Extend it with the new schema rules. **Supersedes** the existing `augur/data/` ban (which conflated runtime config with seed data — `augur/data/` is now allowed for runtime config; seeds move to `assets/seeds/`).

```python
ALLOWED_ROOT_DIRS = {
    "commands", "references", "scripts", "assets",
    "examples", "modules", "augur",
}

ALLOWED_AUGUR_DIRS = {
    "dashboard", "data", "tests", "lib",
}

BANNED_ROOT_DIRS = {
    "docs", "data", "lib",
    ".augur-plugin", "node_modules", "__pycache__",
}

BANNED_AUGUR_DIRS = {
    "seed",  # moved to assets/seeds/
}

DASHBOARD_ALLOWED_EXTENSIONS = {
    ".tsx", ".ts", ".css", ".js", ".jsx",
}

DASHBOARD_ALLOWED_EXCEPTIONS = {
    "tsconfig.json",
}
```

Note: `seed` is banned inside `augur/` (not at skill root). `data` is banned at skill root (not inside `augur/`).

Checks:
1. Every `skills/{name}/` has `SKILL.md`
2. No dirs in `BANNED_ROOT_DIRS` at skill root
3. Only dirs in `ALLOWED_ROOT_DIRS` + `ALLOWED_AUGUR_DIRS` (warn on others, don't block)
4. `augur/dashboard/` contains only allowed extensions
5. No `augur/seed/` (moved to `assets/seeds/`)
6. `SKILL.md` frontmatter has required `name` and `description` fields
7. `name` field matches directory name

#### 2. CI Workflow (`ci-lint.yml`)

Same checks as pre-commit, plus:
- Count skills with non-standard dirs (metric tracking)
- Fail on new violations (allow existing ones with a grandfathered list that shrinks over time)

#### 3. CLAUDE.md Rule Update

Add to Critical Rules:

> **Skill folder schema** — Skills follow the Agent Skills standard. Standard dirs (`commands/`, `references/`, `scripts/`, `assets/`, `examples/`, `modules/`) are portable across AI clients. Augur-specific content goes in `augur/` (`dashboard/`, `data/`, `tests/`, `lib/`). Banned at root: `docs/` (use `references/`), `data/` (use `augur/data/`), `lib/` (use `scripts/` or `augur/lib/`). See ADR-479.

#### 4. `/evolve` Scaffold Update

When creating new skills, `/evolve` scaffolds only allowed dirs:

**Portable skill:**
```
skills/{name}/
├── SKILL.md
└── references/
```

**Native skill:**
```
skills/{name}/
├── SKILL.md
├── references/
├── scripts/
└── augur/
    ├── dashboard/
    ├── data/
    └── tests/
```

#### 5. Autoloop (`auto-skill-structure`)

The existing `auto-skill-structure` scan gains new checks matching the schema. At higher difficulty levels, it auto-fixes:
- `docs/` → `references/` (rename)
- `augur/seed/` → `assets/seeds/` (move)
- `data/` at root → `augur/data/` (move)
- `lib/` at root → classify and move

### Migration Plan

#### Phase 1: Fix Existing Violations

| Violation | Count | Fix |
|-----------|-------|-----|
| `docs/` at root | 7 skills (apple, career, daemon, dev-loops, google-workspace, lifestyle, venture-augur) | Rename to `references/`, merge if both exist |
| `data/` at root | 74 skills (most empty/gitkeep, ui-ux-pro-max has 24 CSV files) | Empty: delete. Non-empty: if portable data → `assets/`, if runtime config → `augur/data/`. Script-driven migration. |
| `lib/` at root | 1 skill (ai_bridge — also has separate `augur/lib/`) | Classify: portable → `scripts/`, Augur-only → merge into existing `augur/lib/` |
| `.augur-plugin/` | 1 skill (enterprise) | Delete |
| `augur/seed/` | 72 skills | Move to `assets/seeds/`. Script: `scripts/migrate_seeds_to_assets.py` |
| `node_modules/` | 0 (already cleaned) | Verify `.gitignore` covers it |

#### Phase 2: Migrate Agents

1. Create `agents/` dir at project root
2. Move `.claude/agents/*.md` → `agents/*.md`
3. Add agents to stub generator targets
4. Run stub generator (copies back to `.claude/agents/` with marker)
5. Verify all agents discoverable via `/agents` command

#### Phase 3: Update Enforcement

1. Update `validate_skill_structure.py` with new schema rules
2. Add to `.pre-commit-config.yaml`
3. Update CI workflow
4. Update CLAUDE.md rule
5. Update `/evolve` scaffold templates
6. Update `auto-skill-structure` autoloop

#### Phase 4: Validate

1. Run validation across all 184 skills
2. Grandfather existing non-standard dirs with tracking
3. Verify dashboard pages still mount correctly
4. Verify agents still discoverable
5. Run full test suite

## Open Questions

| # | Question | Default |
|---|----------|---------|
| 1 | Should `modules/` be in the Agent Skills standard or stay as Augur convention? | Augur convention for now |
| 2 | Should `config.yaml` at skill root be allowed or moved to `augur/data/`? | Allowed at root (per-skill config is portable) |
| 3 | Grandfathering period for existing violations? | 30 days, then block |
| 4 | Should agent sync support Gemini/Codex or Claude Code only? | Claude Code only for now |

## Success Criteria

1. All 184 skills pass `validate_skill_structure.py` (existing violations grandfathered)
2. Pre-commit hook blocks new violations
3. CI enforces schema on every PR
4. 14 agents migrated from `.claude/agents/` to `agents/`
5. `.claude/agents/` contains only `AUGUR-GENERATED` copies
6. `/evolve` scaffolds only allowed dirs
7. `auto-skill-structure` detects and reports violations
8. CLAUDE.md documents the schema
9. Zero `docs/`, `data/`, `lib/` dirs at skill root (migrated)
10. Zero `augur/seed/` dirs (moved to `assets/seeds/`)
