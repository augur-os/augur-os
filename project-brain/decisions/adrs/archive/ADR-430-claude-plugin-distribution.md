---
status: Implemented
date: 2026-03-17
deciders:
  - Gur Sannikov
related:
  - ADR-426
  - ADR-428
  - ADR-163
  - ADR-012
hub: dev
tags:
  - plugins
  - distribution
  - architecture
  - migration
  - claude-code
superseded_by: null
---

# ADR-430: Claude Code Plugin Distribution

## Context

Augur is a monolith: 131 skills, an MCP server, a Next.js dashboard, and Python core all live in a single repository. This means:

1. **No distribution path** — users cannot install Augur through Claude Code's native `claude plugin install` system. They must clone the repo, install Python dependencies, install Node dependencies, configure MCP, and set up the vault manually.
2. **All-or-nothing** — users get 131 skills regardless of which domains they care about. A developer who wants `dev-adr` and `dev-merge` also gets `wealth`, `health`, `wearables`, `home-automation`, and 50 adaptive auto-commands.
3. **Heavy prerequisites** — the dashboard requires Node.js, npm, and a full Next.js build even though everything works from the CLI via MCP tools. Non-technical users face a pip + npm + mcp configuration gauntlet.
4. **No marketplace presence** — Claude Code's plugin marketplace is the primary discovery channel. Augur is invisible to it.

Claude Code plugins are distributable packages installed via `claude plugin install <name>` from marketplace repos. A plugin can contain skills (SKILL.md), agents, hooks, commands, and arbitrary files (scripts, assets, data).

ADR-426 already moved all skills to client-native directories (`.claude/skills/`), making them structurally compatible with Claude Code's skill format. This ADR completes the journey by packaging them as distributable plugins.

### Critical Design Discovery: Dynamic Tool Loading

The MCP server already dynamically discovers and loads tools from skill directories via `plugin_tools.py` (ADR-012). It scans for `scripts/mcp/__init__.py` in each skill dir and calls `register_tools()` at runtime using `importlib`. This means:

- **MCP tools do NOT need to be centralized** in the platform repo
- **Scripts, assets, seeds, dashboard pages, API routes all stay with the skill** in the plugin
- **The platform is a thin framework** — MCP server engine, shared libs, dashboard shell
- **One change needed**: `plugin_tools.py:_collect_skill_dirs()` must also scan Claude Code plugin install directories (`~/.claude/plugins/cache/`)

Similarly, `mount-plugins` already copies dashboard pages and API routes from skill directories into `apps/dashboard/`. It just needs to also scan plugin install directories.

### Current Architecture

```
Augur (monolith repo)
├── .claude/skills/           # 131 skills across 15 hubs
│   └── {skill}/
│       ├── SKILL.md          # Skill instructions
│       ├── augur/
│       │   ├── augur.yaml    # Hub metadata, MCP tool declarations
│       │   ├── dashboard/    # Next.js pages (105 skills have these)
│       │   ├── api/          # API routes (41 skills)
│       │   ├── tests/        # Python tests
│       │   ├── data/         # Runtime data
│       │   └── modules/      # Reference documentation
│       ├── scripts/
│       │   ├── mcp/          # MCP tool implementations (51 skills total)
│       │   └── *.py          # Business logic (called by MCP tools)
│       ├── assets/           # Prompts, seeds, reports
│       └── references/       # Supporting docs
├── src/                      # Python core + MCP server framework
│   ├── mcp/augur_mcp/
│   │   ├── server.py         # MCP server engine
│   │   ├── plugin_tools.py   # Dynamic tool discovery (THE KEY FILE)
│   │   └── domain/           # Core non-plugin tools
│   ├── config/paths.py       # Path resolution
│   └── lib/                  # Shared Python libs
├── apps/dashboard/           # Next.js dashboard shell
│   ├── components/           # Shared UI components
│   ├── hooks/                # useActionRunner, etc.
│   └── app/                  # Hub routes (auto-generated from skills)
├── scripts/mount-plugins.*   # Copies dashboard/api from skills into Next.js
└── config/                   # System configuration
```

### Skill Distribution by Hub

| Hub | Skills | Dashboard | MCP Scripts | API Routes |
|-----|--------|-----------|-------------|------------|
| adaptive | 52 | 52 | 0 | 0 |
| admin | 9 | 7 | 6 | 4 |
| ai | 13 | 10 | 10 | 8 |
| career | 7 | 7 | 7 | 6 |
| consulting | 4 | 4 | 4 | 3 |
| core | 2 | 2 | 2 | 1 |
| dev | 13 | 10 | 7 | 7 |
| enterprise | 1 | 1 | 1 | 1 |
| finance | 2 | 2 | 2 | 2 |
| health | 2 | 2 | 2 | 2 |
| home | 1 | 1 | 1 | 1 |
| lifestyle | 2 | 2 | 2 | 2 |
| observability | 6 | 5 | 4 | 3 |
| productivity | 5 | 5 | 5 | 4 |
| professional | 2 | 2 | 2 | 2 |
| *(unassigned)* | 2 | 1 | 0 | 0 |
| **Total** | **131** | **105** | **51** | **41** |

## Decision

Split Augur into **8 distributable units**: 1 thin platform repo, 1 bootstrap plugin, and 6 domain plugins. Skills are **self-contained** — each plugin carries the full skill directory (SKILL.md, scripts, MCP tools, dashboard pages, API routes, assets, tests). The platform is a thin framework.

### Core Principle: Skills Are Self-Contained

The existing architecture already supports this via dynamic discovery:
- `plugin_tools.py` dynamically loads MCP tools from `{skill}/scripts/mcp/__init__.py`
- `mount-plugins` copies `{skill}/augur/dashboard/` into the Next.js app
- `mount-plugins` copies `{skill}/augur/api/` into the Next.js API routes

Nothing needs to be extracted from skills into the platform. The platform is already just a framework that assembles skills. The only change is teaching the framework to also discover skills from Claude Code plugin install directories.

### Target Architecture

```
Distribution Units:

┌─────────────────────────────────────────────────────┐
│ augur-platform (GitHub repo, pip-installable)       │
│   THIN FRAMEWORK ONLY:                             │
│   src/mcp/augur_mcp/  MCP server engine            │
│   src/config/          Path resolution              │
│   src/lib/             Shared Python libs           │
│   apps/dashboard/      Next.js shell (layout,       │
│                        shared components, hooks)    │
│   scripts/mount-plugins  Assembles skills into app  │
│   config/              System configuration         │
│                                                     │
│   NO skill-specific code lives here.                │
└─────────────────────────────────────────────────────┘

┌────────────────────┐  ┌────────────────────────────┐
│ augur              │  │ augur-system               │
│ (bootstrap plugin) │  │ admin + core +             │
│ 1 skill: onboard   │  │ observability = ~17 skills │
│ Installs platform  │  │ Each skill is COMPLETE     │
└────────────────────┘  └────────────────────────────┘

┌────────────────────┐  ┌────────────────────────────┐
│ augur-knowledge    │  │ augur-dashboard            │
│ ai hub = ~13       │  │ UI skills + dashboard      │
│ Each with scripts, │  │ auto-* commands = ~15      │
│ MCP tools, assets  │  │ Requires Node.js           │
└────────────────────┘  └────────────────────────────┘

┌────────────────────┐  ┌────────────────────────────┐
│ augur-adaptive     │  │ augur-dev                  │
│ Code-focused       │  │ dev hub = ~13 skills       │
│ auto-* = ~37       │  │ Each with full structure   │
│ No dashboard deps  │  │                            │
└────────────────────┘  └────────────────────────────┘

┌────────────────────┐  ┌────────────────────────────┐
│ augur-life         │  │ augur-career               │
│ productivity +     │  │ career + professional      │
│ finance + health + │  │ = ~9 skills                │
│ lifestyle + home   │  │ Each with MCP tools,       │
│ = ~12 skills       │  │ dashboard, seeds, etc.     │
└────────────────────┘  └────────────────────────────┘

NOT PUBLISHED (stay in local .claude/skills/):
- consulting: client-terminal-automation, client-smb-design,
              client-ai-consulting, client-hub (4 skills)
- enterprise: enterprise (1 skill)
- unassigned: executor, reindex-rag (2 skills — need hub assignment first)
```

### What Changes Per Skill: Concrete Example (Career)

**Before** — career skill in monolith at `.claude/skills/career/`:
```
career/                              ← 157 files
├── SKILL.md                         ← skill instructions
├── .config                          ← skill config
├── scripts/
│   ├── mcp/                         ← MCP tool registrations (7 files)
│   │   ├── __init__.py              ← register_tools() — MCP server loads this
│   │   ├── tools_jobs.py
│   │   ├── tools_portfolio.py
│   │   ├── tools_resume.py
│   │   └── tools_training.py
│   ├── career_hardening.py          ← business logic (imported by MCP tools)
│   ├── career_status.py
│   ├── company_research.py
│   └── ... (12 .py files)
├── assets/
│   ├── actions/                     ← 12 action prompt templates
│   ├── prompts/                     ← 3 prompt templates
│   ├── reports/                     ← generated artifacts
│   └── seed-data/                   ← vault initialization data (9 files)
├── augur/
│   ├── augur.yaml                   ← hub metadata
│   ├── dashboard/                   ← 30+ React components & pages
│   ├── api/                         ← 14 Next.js API routes
│   ├── tests/                       ← 11 Python test files
│   ├── data/prompts/                ← runtime prompt data
│   └── modules/scoring-formulas.md  ← reference doc
└── (+ __pycache__/ artifacts)
```

**After** — career skill in `augur-career` plugin:
```
augur-career/
├── .claude-plugin/plugin.json
├── skills/
│   └── career/                      ← SAME STRUCTURE, ALMOST NOTHING CHANGES
│       ├── SKILL.md                 ← enriched with x-augur-* frontmatter
│       ├── scripts/
│       │   ├── mcp/                 ← STAYS — MCP server discovers dynamically
│       │   │   ├── __init__.py
│       │   │   ├── tools_jobs.py
│       │   │   ├── tools_portfolio.py
│       │   │   ├── tools_resume.py
│       │   │   └── tools_training.py
│       │   ├── career_hardening.py  ← STAYS — imported by MCP tools above
│       │   ├── career_status.py
│       │   ├── company_research.py
│       │   └── ...
│       ├── assets/
│       │   ├── actions/             ← STAYS — Claude reads these
│       │   ├── prompts/             ← STAYS — Claude reads these
│       │   └── seed-data/           ← STAYS — /onboard uses these
│       ├── augur/
│       │   ├── dashboard/           ← STAYS — mount-plugins copies to Next.js
│       │   ├── api/                 ← STAYS — mount-plugins copies to Next.js
│       │   ├── tests/               ← STAYS — tests for the skill's code
│       │   ├── data/prompts/        ← STAYS — runtime data
│       │   └── modules/             ← STAYS — reference docs
│       └── references/              ← STAYS — if any
├── README.md
└── LICENSE
```

**What's deleted** (3 files):
```
DELETED:
├── augur/augur.yaml     ← absorbed into SKILL.md x-augur-* frontmatter
├── augur/version.yaml   ← replaced by plugin.json version
└── .config              ← replaced by plugin enable/disable
```

**What's added** (2 files):
```
ADDED:
├── .claude-plugin/plugin.json   ← plugin manifest
└── SKILL.md frontmatter         ← x-augur-hub, x-augur-plugin, x-augur-mcp-tools
```

**The skill directory structure is preserved almost exactly.** This is the lowest-risk migration possible.

### Skill Directory Cleanup (Phase 0)

Before plugin packaging, each skill is normalized to a canonical structure. The audit found these issues across all skills:

| Issue | Count | Action |
|-------|-------|--------|
| `.DS_Store` files | 26 | Delete, .gitignore |
| `__pycache__/` directories | ~60 | Delete, .gitignore |
| `augur/README.md` (auto-generated) | ~80 | Delete, .gitignore |
| `augur/api/tsconfig.json` (auto-generated) | ~40 | Delete, .gitignore |
| `augur/dashboard/tsconfig.json` (auto-generated) | ~100 | Delete, .gitignore |
| `augur/data/prompts/` (stale TODO stubs) | ~10 | Delete entirely |
| `assets/prompts/` (duplicates seeds/prompts/) | ~30 | Consolidate into seeds/prompts/ |
| `.config` (replaced by plugin enable/disable) | 131 | Delete |
| `augur/version.yaml` (replaced by plugin.json) | ~50 | Delete |
| Per-skill `requirements.txt` | ~5 | Delete (plugin-level) |
| User data in git (`.xlsx`, `.docx`, `.m4a`) | 3 skills | Move to vault |

**Prompt duplication** is the most confusing issue — three locations for the same data:
```
assets/prompts/career-check-in.md          ← FULL content (777B)
assets/seed-data/prompts/career-check-in.md ← STRIPPED copy (261B)
augur/data/prompts/career-check-in.md       ← STALE stub with TODO
```
Consolidated to one: `assets/seeds/prompts/career-check-in.md`

**User data in git** (must move to vault before distribution):
- `career/assets/reports/companies-db.xlsx` — personal generated report
- `apple/assets/voice-memos/audio/*.m4a` — personal voice recordings
- `finance/assets/zero-cost-collar-avgo.docx` — personal financial document

### Platform Changes (Thin Framework)

The platform repo keeps ONLY framework code. No skill-specific code moves into it.

```
augur-platform/
├── src/
│   ├── mcp/augur_mcp/
│   │   ├── server.py              # MCP server engine (unchanged)
│   │   ├── plugin_tools.py        # UPDATED: scan Claude plugin dirs too
│   │   ├── compat.py              # Shared utilities (unchanged)
│   │   ├── domain/                # Core non-plugin tools (unchanged)
│   │   └── ...
│   ├── config/paths.py            # UPDATED: add Claude plugin paths
│   └── lib/                       # Shared Python libs (unchanged)
├── apps/dashboard/
│   ├── components/                # Shared UI components (unchanged)
│   ├── hooks/                     # useActionRunner, etc. (unchanged)
│   └── app/layout.tsx             # Shell layout (unchanged)
│   └── app/{hub}/                 # AUTO-GENERATED by mount-plugins
├── scripts/
│   └── mount-plugins.*            # UPDATED: scan Claude plugin dirs too
├── config/                        # System configuration (unchanged)
├── pyproject.toml                 # pip install augur-cli
└── package.json                   # npm install (dashboard only)
```

**Total platform changes: 3 files updated** (`plugin_tools.py`, `paths.py`, `mount-plugins`). All other framework code is unchanged.

### The Key Code Change: `plugin_tools.py`

Current `_collect_skill_dirs()` scans:
1. `plugins/{bundle}/skills/{skill}/` (legacy)
2. `.claude/skills/{skill}/` (client-native, per ADR-426)

Needs one addition — scan Claude Code plugin install directories:
```python
# Claude Code installed plugins: ~/.claude/plugins/cache/{marketplace}/{plugin}/{version}/skills/*/
claude_plugins_cache = Path.home() / ".claude" / "plugins" / "cache"
if claude_plugins_cache.exists():
    for marketplace_dir in claude_plugins_cache.iterdir():
        if not marketplace_dir.is_dir():
            continue
        for plugin_dir in marketplace_dir.iterdir():
            if not plugin_dir.is_dir() or not plugin_dir.name.startswith("augur"):
                continue
            # Find the latest version directory
            version_dirs = sorted(plugin_dir.iterdir(), reverse=True)
            if not version_dirs:
                continue
            skills_dir = version_dirs[0] / "skills"
            if skills_dir.exists():
                for skill_dir in skills_dir.iterdir():
                    if skill_dir.is_dir() and not skill_dir.name.startswith("."):
                        # Read hub from augur.yaml or SKILL.md frontmatter
                        ...
                        result.append((plugin_id, skill_dir))
```

Same change needed in `mount-plugins` for dashboard/API route discovery.

### Plugin Composition Detail

#### Plugin 0: `augur` (Bootstrap)

**Purpose**: Zero-prerequisite entry point. Non-technical users install this one plugin and run `/onboard` — it handles everything else.

**Contains**:
| Skill | Description |
|-------|-------------|
| onboard | Platform installer wizard |

**What `/onboard` does**:
1. Check prerequisites (Python >= 3.11, git)
2. Clone or download `augur-platform`
3. `pip install augur-cli` (or `uv pip install augur-cli`)
4. `claude mcp add --transport stdio augur -- augur mcp serve`
5. Create vault directory structure (`~/Vault/Augur/`)
6. Interactive module selection: "Which Augur modules? [system, knowledge, dashboard, adaptive, dev, life, career]"
7. `claude plugin install augur-system augur-knowledge` (required)
8. Install selected optional plugins
9. If dashboard selected: check Node.js, run `npm install` in dashboard dir, run `mount-plugins`
10. Run health check via MCP tools

**Hooks**:
```json
{
  "hooks": {
    "SessionStart": [{
      "matcher": "startup",
      "hooks": [{
        "type": "command",
        "command": "\"${CLAUDE_PLUGIN_ROOT}/hooks/check-platform\" 2>/dev/null || true",
        "async": true
      }]
    }]
  }
}
```

#### Plugin 1: `augur-system` (Required Infrastructure)

**Merges hubs**: admin + core + observability

| Skill | Original Hub | Has MCP | Has API | Has Dashboard |
|-------|-------------|---------|---------|---------------|
| channels | admin | yes | yes | yes |
| import | admin | yes | yes | yes |
| remote-access | admin | yes | no | yes |
| save | admin | yes | no | yes |
| system-cleanup | admin | no | no | yes |
| updater | admin | yes | no | yes |
| workflows | admin | no | no | yes |
| discovery | core | yes | yes | yes |
| file-manager | core | yes | no | yes |
| daemon | observability | yes | yes | yes |
| dev-loops | observability | yes | yes | yes |
| kill-augur | observability | no | no | yes |
| metrics | observability | yes | yes | yes |
| observe | observability | yes | yes | yes |
| ops-daemon | observability | yes | no | no |

**Not included from admin** (move to augur-dashboard):
- `renderer` — pure dashboard rendering service
- `page-builder` — dashboard page composition

Each skill carries its full directory (scripts/mcp/, augur/dashboard/, augur/api/, etc.).

#### Plugin 2: `augur-knowledge` (The Second Brain)

**Hub**: ai (all skills except onboard)

| Skill | Has MCP | Has API | Has Dashboard |
|-------|---------|---------|---------------|
| ai_bridge | yes | yes | yes |
| ask | yes | yes | yes |
| commands | yes | no | no |
| dev-learn | yes | yes | yes |
| dev-sync | yes | no | yes |
| knowledge | yes | yes | yes |
| nightly | yes | yes | yes |
| rag | yes | yes | yes |
| reindex-project | yes | yes | no |
| scraper | yes | yes | yes |
| search | yes | yes | yes |
| sync-agents | yes | no | no |

#### Plugin 3: `augur-dashboard` (Optional UI)

**Purpose**: Everything needed to run the Next.js dashboard. Contains UI-specific skills and dashboard-focused adaptive commands.

Dashboard management skills (from admin):
| Skill | Description |
|-------|-------------|
| renderer | Markdown/YAML rendering service |
| page-builder | Visual page composition |
| dev-build | Cache clean, rebuild, reload |
| frontend | UI component development (ShadCN, Tailwind) |
| test-ui | Browser QA validation |

Dashboard-focused adaptive skills (from adaptive hub):
| Skill | Description |
|-------|-------------|
| auto-test-dashboard | Jest test suite |
| auto-test-pages | Page route validation |
| auto-test-links | Broken link scan |
| auto-test-build | Build verification |
| auto-block-wiring | Block data pipeline validation |
| auto-page-mounts | Mount verification |
| auto-tabs | Tab maturity scoring |
| auto-dead-ui | Unwired UI element detection |
| auto-view-schema | View YAML validation |
| auto-memory-leak | Polling/cache leak detection |

Setup skill:
| Skill | Description |
|-------|-------------|
| dashboard-setup | `npm install && npm run build && mount-plugins` |

**Total**: ~16 skills

**Dependency**: Requires `augur-platform` repo cloned + Node.js >= 18.

#### Plugin 4: `augur-adaptive` (Code Quality Automation)

**Hub**: adaptive (minus dashboard-specific skills in augur-dashboard)

All auto-* skills that analyze **code, config, and wiring** (not dashboard UI):

| Skill | Description |
|-------|-------------|
| auto-api-wiring | API route → MCP tool validation |
| auto-analytics | Usage analytics from logs |
| auto-claude-md-audit | CLAUDE.md accuracy |
| auto-code-health | TypeScript build errors |
| auto-code-review | Recent changes review |
| auto-dead-api | Orphan API/MCP tools |
| auto-dead-wiring | augur.yaml vs implementation |
| auto-dependency-audit | npm/pip vulnerabilities |
| auto-doc-freshness | Stale docs detection |
| auto-duplication | Duplicate auto-command detection |
| auto-fix | TODO marker auto-fix |
| auto-flow-optimizer | Dispatch mode mismatches |
| auto-format | Prettier formatting |
| auto-frontmatter-lint | Frontmatter validation |
| auto-git-health | Git repo maintenance |
| auto-index-notes | Notes index rebuild |
| auto-inspect | Observability analysis |
| auto-lint | ESLint auto-fix |
| auto-logs | Log hygiene |
| auto-loop-advisor | Loop maturity analysis |
| auto-markers | TODO/FIXME scanning |
| auto-markdowns | Action template quality |
| auto-memory-sync | Memory curation |
| auto-orphan-plans | Design doc orphan detection |
| auto-plugin-lint | Plugin structure validation |
| auto-refactor | Capability migration audit |
| auto-repo-sync | Uncommitted changes check |
| auto-seed-data | Template data seeding |
| auto-security-scan | Secret/CVE scanning |
| auto-self-heal | Runtime error delegation |
| auto-skill-enhance | Skill description generation |
| auto-skill-md | SKILL.md validation |
| auto-skill-migrate | augur.yaml → frontmatter |
| auto-skill-refs | SKILL.md file references |
| auto-stale-refs | Stale path references |
| auto-tech-debt | Tech debt prioritization |
| auto-test-api | API route health |
| auto-test-coverage | Test coverage analysis |
| auto-test-mcp | MCP handshake verification |
| auto-test-mcp-commands | MCP tool invocation test |
| auto-test-pytest | Python test suite |
| auto-test-webmcp | WebMCP validation |
| auto-vault-hygiene | Vault structure monitoring |
| auto-yaml-lint | augur.yaml schema validation |

**Total**: ~44 skills

#### Plugin 5: `augur-dev` (Developer Tools)

**Hub**: dev

| Skill | Has MCP | Has API | Has Dashboard |
|-------|---------|---------|---------------|
| advisor | yes | no | yes |
| dev-adr | yes | yes | yes |
| dev-debug | no | no | yes |
| dev-merge | no | no | no |
| dev-rollback | no | no | no |
| dev-test | no | no | yes |
| developer | no | no | no |
| devops | yes | yes | yes |
| mcp-app-factory | yes | yes | yes |
| test-client | yes | no | yes |
| validator | yes | yes | yes |

**Total**: ~11 skills

#### Plugin 6: `augur-life` (Personal Management)

**Merges hubs**: productivity + finance + health + lifestyle + home

| Skill | Original Hub | Has MCP | Has API |
|-------|-------------|---------|---------|
| apple | productivity | yes | yes |
| eisenhower | productivity | yes | yes |
| google-workspace | productivity | yes | yes |
| organizer | productivity | yes | yes |
| reading-list | productivity | yes | no |
| finance | finance | yes | yes |
| wealth | finance | yes | yes |
| health | health | yes | yes |
| wearables | health | yes | yes |
| books | lifestyle | yes | yes |
| lifestyle | lifestyle | yes | yes |
| home-automation | home | yes | yes |

**Total**: 12 skills

#### Plugin 7: `augur-career` (Career & Professional)

**Merges hubs**: career + professional

| Skill | Original Hub | Has MCP | Has API |
|-------|-------------|---------|---------|
| career | career | yes | yes |
| coach | career | yes | yes |
| content | career | yes | yes |
| danit | career | yes | yes |
| growth | career | yes | yes |
| interview-coach | career | yes | yes |
| linkedin-writer | career | yes | yes |
| post | career | no | no |
| project-dev | professional | yes | yes |
| venture-augur | professional | yes | yes |

**Total**: 10 skills

### Plugin File Structure

Each plugin ships the **complete skill directory** plus a manifest:

```
augur-{name}/
├── .claude-plugin/
│   └── plugin.json              # Required: name, description, version, author
├── skills/
│   └── {skill-name}/
│       ├── SKILL.md             # Skill instructions (enriched frontmatter)
│       ├── scripts/
│       │   ├── mcp/             # MCP tool registrations (dynamic discovery)
│       │   │   ├── __init__.py  # register_tools() entry point
│       │   │   └── tools_*.py   # Tool implementations
│       │   └── *.py             # Business logic (imported by MCP tools)
│       ├── assets/
│       │   ├── actions/         # Action prompt templates
│       │   ├── prompts/         # Prompt templates
│       │   └── seed-data/       # Vault initialization data
│       ├── augur/
│       │   ├── dashboard/       # React pages (mount-plugins copies to Next.js)
│       │   ├── api/             # API routes (mount-plugins copies to Next.js)
│       │   ├── tests/           # Python tests
│       │   ├── data/            # Runtime data
│       │   └── modules/         # Reference documentation
│       └── references/          # Supporting docs
├── agents/                      # Optional: agent definitions
├── hooks/                       # Optional: event hooks
│   └── hooks.json
├── package.json                 # npm metadata for marketplace
├── README.md
├── LICENSE
└── CHANGELOG.md
```

### Marketplace Structure

```
augur-marketplace/
├── .claude-plugin/
│   └── marketplace.json
├── plugins/
│   ├── augur/                   # Bootstrap
│   ├── augur-system/            # Infrastructure
│   ├── augur-knowledge/         # Second brain
│   ├── augur-dashboard/         # UI (optional)
│   ├── augur-adaptive/          # Auto-commands (optional)
│   ├── augur-dev/               # Developer tools (optional)
│   ├── augur-life/              # Personal management (optional)
│   └── augur-career/            # Career (optional)
└── README.md
```

Marketplace manifest:
```json
{
  "$schema": "https://anthropic.com/claude-code/marketplace.schema.json",
  "name": "augur-marketplace",
  "description": "Augur — local-first personal knowledge and automation system",
  "owner": {
    "name": "Gur Sannikov",
    "email": "..."
  },
  "plugins": [
    {
      "name": "augur",
      "description": "Bootstrap installer for the Augur platform. Run /onboard after installing.",
      "version": "1.0.0",
      "source": "./plugins/augur",
      "category": "productivity"
    },
    {
      "name": "augur-system",
      "description": "Core infrastructure — daemon, channels, import, observe, metrics, file management",
      "version": "1.0.0",
      "source": "./plugins/augur-system",
      "category": "productivity"
    },
    {
      "name": "augur-knowledge",
      "description": "Second brain — knowledge retrieval, RAG search, web scraping, AI bridge",
      "version": "1.0.0",
      "source": "./plugins/augur-knowledge",
      "category": "productivity"
    },
    {
      "name": "augur-dashboard",
      "description": "Optional Next.js dashboard UI with visual page builder and QA tools",
      "version": "1.0.0",
      "source": "./plugins/augur-dashboard",
      "category": "productivity"
    },
    {
      "name": "augur-adaptive",
      "description": "44 autonomous code quality scanners — lint, security, wiring, coverage, debt",
      "version": "1.0.0",
      "source": "./plugins/augur-adaptive",
      "category": "development"
    },
    {
      "name": "augur-dev",
      "description": "Developer tools — ADR management, merge workflow, debugging, testing",
      "version": "1.0.0",
      "source": "./plugins/augur-dev",
      "category": "development"
    },
    {
      "name": "augur-life",
      "description": "Personal management — Apple integration, finance, health, productivity, home",
      "version": "1.0.0",
      "source": "./plugins/augur-life",
      "category": "productivity"
    },
    {
      "name": "augur-career",
      "description": "Career management — job search, coaching, content creation, interview prep",
      "version": "1.0.0",
      "source": "./plugins/augur-career",
      "category": "productivity"
    }
  ]
}
```

### SKILL.md Frontmatter Additions

```yaml
---
name: career
description: Manage job search pipeline, company research, and interview preparation
x-augur-hub: career
x-augur-plugin: augur-career
x-augur-requires-platform: true
x-augur-mcp-tools:
  - get-career-jobs
  - add-career-job
  - get-career-companies
  - tailor-resume
x-augur-dashboard-page: /career
---
```

The `augur.yaml` file is deleted. Its fields are absorbed:
- `contributes_to` → `x-augur-hub`
- MCP tool list → `x-augur-mcp-tools`
- Dependencies → `x-augur-requires-platform`

### Dependency Graph

```
                    augur (bootstrap)
                       │
              ┌────────┴────────┐
              ▼                  ▼
        augur-platform     (recommends)
        (pip install)           │
              │          ┌──────┼──────┬──────┬──────┐
              ▼          ▼      ▼      ▼      ▼      ▼
        augur-system  augur-  augur- augur- augur- augur-
        (required)    knowledge dashboard adaptive dev  life/career
                      (required) (optional) (opt)  (opt)  (opt)
                                    │
                                    ▼
                              Node.js >= 18
```

### User Journeys

**Journey 1: Non-technical user (CLI only)**
```bash
claude plugin marketplace add https://github.com/augur-os/augur-marketplace
claude plugin install augur
/onboard
# → installs Python platform, MCP server, vault structure
# → installs augur-system + augur-knowledge
# → no Node.js needed, no dashboard
# → user can now: /ask, /search, /career, etc.
```

**Journey 2: Developer wanting full stack**
```bash
claude plugin install augur
/onboard --full
# → installs everything including dashboard
# → augur-system + augur-knowledge + augur-dashboard + augur-dev + augur-adaptive
```

**Journey 3: Existing user upgrading**
```bash
/onboard --migrate
# → reads current .claude/skills/ structure
# → installs matching plugins
# → moves personal/client skills to local .claude/skills/
# → removes migrated skills from repo
```

### Migration Safety

#### What Can Break

1. **Plugin tool discovery path**: The MCP server must find `scripts/mcp/__init__.py` inside plugin install directories (`~/.claude/plugins/cache/`). The path structure differs from `.claude/skills/`. **Mitigation**: `_collect_skill_dirs()` updated with explicit Claude plugin path scanning. Verified with `augur mcp serve` health check after update.

2. **Python import paths**: MCP tool scripts use relative imports (`from ._shared import ...`) and absolute imports (`from src.config.paths import ...`). After moving to plugin install dir, `src.*` imports need the platform on `PYTHONPATH`. **Mitigation**: The MCP server already sets `PYTHONPATH` when starting. Plugin scripts import `src.*` via the same mechanism. Test with `python -c "import src.config.paths"` from plugin dir.

3. **Dashboard mount-plugins**: Currently copies from `.claude/skills/{skill}/augur/dashboard/`. Must also copy from plugin install dirs. **Mitigation**: `mount-plugins` updated to scan plugin dirs. Runs during `/onboard` and `/dev-build`. Verified with `npm run build`.

4. **CLAUDE.md references**: The root CLAUDE.md references `.claude/skills/` paths. After migration, skills are in `~/.claude/plugins/cache/augur-marketplace/`. **Mitigation**: CLAUDE.md generation script updated to discover skills from both locations.

5. **augur.yaml metadata loss**: Skills currently carry rich metadata in `augur.yaml`. Migrating to `x-augur-*` frontmatter in SKILL.md. **Mitigation**: Phase 1 migrates all fields before any restructuring. Verified with diff of old augur.yaml vs new frontmatter.

6. **Skill cross-references**: Some skills reference other skills by relative path (e.g., `../auto-lint/SKILL.md`). Plugin isolation breaks relative paths. **Mitigation**: Audit all SKILL.md files for relative path references and convert to skill name references.

7. **Hooks and session-start**: Current behavior relies on hooks in settings.json. Plugins have their own hooks.json. **Mitigation**: Plugin hooks.json replaces settings.json entries for plugin-owned hooks.

8. **Local-only skills left behind**: After migration, consulting/enterprise/unassigned skills remain in `.claude/skills/` but the discovery system may not scan there anymore. **Mitigation**: Claude Code always scans `.claude/skills/` for project-scoped skills, regardless of plugins. These skills continue to work.

9. **Adaptive skill splitting**: 52 adaptive skills must be split between augur-adaptive (code-focused, ~44) and augur-dashboard (UI-focused, ~8). Misclassification breaks the independence guarantee. **Mitigation**: The split criterion is objective — if the skill's auto-command scans dashboard pages/routes/blocks, it goes to augur-dashboard. If it scans code/config/wiring, it goes to augur-adaptive. Phase 1 includes a classification audit with grep verification.

10. **Seed data discovery**: `/onboard` and `/import` use seed data from `assets/seed-data/`. After migration, seeds are in plugin install dirs. **Mitigation**: Seed discovery updated to scan plugin dirs alongside `.claude/skills/`. Same pattern as MCP tool discovery.

#### System Integration Impact

Four subsystems are deeply coupled to skill directory locations. Each requires specific updates.

##### 1. RAG Index Impact

**Current state**: RAG indexing scans `.claude/skills/` and `plugins/*/skills/` to discover SKILL.md, action definitions, prompt templates, and scripts for indexing. The entire content pipeline — discovery, indexing, storage, and retrieval — uses paths from `get_all_client_skill_dirs()`.

**What breaks**: Skills in plugin install directories (`~/.claude/plugins/cache/`) are invisible to RAG. The indexer won't find them, so search results will be empty for plugin-installed skills.

**Files to update**:
| File | Function | Change |
|------|----------|--------|
| `src/config/paths.py` | `get_all_client_skill_dirs()` | Add plugin cache dirs to scan list |
| `.claude/skills/rag/scripts/_indexer_helpers.py` | `_discover_skill_dirs()` | Scan plugin cache via updated paths |
| `.claude/skills/rag/scripts/rag_indexer.py` | `resolve_rag_output_root()` | Handle plugin cache path → RAG output mapping |
| `.claude/skills/rag/scripts/mcp/rag_tools.py` | `_resolve_scope_paths()` | Resolve plugin-installed skills to correct RAG indices |
| `.claude/skills/ai_bridge/scripts/ops/rag_reindex.py` | Nightly reindex automation | Scan plugin cache dirs for reindex jobs |
| `scripts/bulk_index.py` | Bulk indexing | Include plugin cache in scan |

**RAG output path mapping**: Plugin-installed skills must map to the same RAG output structure as local skills. Example:
```
# Local skill:
.claude/skills/career/ → ~/Library/Application Support/Augur/rag/career/career/

# Plugin-installed skill (same output):
~/.claude/plugins/cache/augur-marketplace/augur-career/1.0.0/skills/career/
  → ~/Library/Application Support/Augur/rag/career/career/
```
The RAG output path is derived from `{bundle}/{skill_name}`, not from the skill's file location. So the output stays the same — only the input discovery changes.

##### 2. Vault Impact

**Current state**: Vault path resolution is **already decoupled** from skill file location (ADR-270). Skills call `get_skill_data_dir("career")` with a hardcoded name, which resolves to `~/Vault/Augur/{bundle}/{skill_name}/` via the `contributes_to` field in `augur.yaml`.

**What doesn't break**: Vault read/write paths. MCP tools hardcode their skill name: `get_skill_data_dir("career")`. This function resolves via bundle mapping, not file location. Vault data at `~/Vault/Augur/career/career/` is untouched.

**What breaks**: The bundle mapping itself. `get_skill_bundle()` reads `contributes_to` from `augur/augur.yaml` in the skill directory. After Phase 1, `augur.yaml` is deleted and replaced by `x-augur-hub` in SKILL.md frontmatter. After Phase 3, skills are in plugin cache dirs.

**Files to update**:
| File | Function | Change |
|------|----------|--------|
| `src/config/paths.py` | `_discover_skill_to_bundle_mapping()` | Read `x-augur-hub` from SKILL.md frontmatter (not augur.yaml). Scan plugin cache dirs. |
| `src/mcp/augur_mcp/config.py` | `get_skill_data_dir()` | Same: scan plugin cache dirs for skill discovery |
| `src/mcp/augur_mcp/config.py` | `_resolve_client_skill_bundle()` | Parse SKILL.md frontmatter instead of augur.yaml |

**Seed data impact**: Seed files move from `assets/seed-data/` to `assets/seeds/` (Phase 0). The auto-seed-data system must scan plugin cache dirs to find seeds for newly installed plugins. `/onboard` copies seeds from plugin dirs to vault on first install.

##### 3. Runtime Structure Impact (`__file__`-Based Path Resolution)

**Current state**: MCP tool scripts use `Path(__file__)` to locate co-located resources — sibling scripts, sync modules, config files. This is the most common pattern:

```python
# .claude/skills/apple/scripts/mcp/_helpers.py
PLUGIN_ROOT = Path(__file__).parent.parent.parent  # → .../apple/
SCRIPTS_DIR = PLUGIN_ROOT / "scripts"
```

**What doesn't break**: `__file__` still works. When Python loads a module from any path (including `~/.claude/plugins/cache/.../skills/career/scripts/mcp/tools_jobs.py`), `__file__` resolves to that actual path. Relative navigation (`parent.parent`) finds the same skill root regardless of where it's installed.

**What breaks**: Only if skills import resources from OUTSIDE their own directory. Two patterns found:

| Pattern | Example | Risk |
|---------|---------|------|
| Cross-skill imports | `apple/scripts/triage_inbox.py` referencing another skill's plugin path | **Medium** — must use `get_skill_root()` instead |
| `from src.*` imports | `from src.config.paths import get_skill_data_dir` | **Low** — already on `PYTHONPATH` via MCP server |

**Mitigation**: Phase 1.3 (cross-ref-auditor) catches cross-skill path references. The `PYTHONPATH` is set by the MCP server at startup and includes the platform repo root, so `from src.*` imports work regardless of where the calling script lives.

##### 4. Daemon Impact

**Current state**: The daemon skill (`observability/daemon`) manages background services via macOS LaunchAgents. It has **hardcoded paths** to skill executables:

```python
# daemon/scripts/service_healer.py (line 68)
"executable": "plugins/observability/skills/daemon/bundle/Augur Daemon.app/..."

# daemon/scripts/service_healer.py (line 88)
def _get_plist_templates_dir(project_root: Path) -> Path:
    return project_root / "plugins" / "observability" / "skills" / "daemon" / "assets" / "plists"
```

The LaunchAgent plist template sets:
- `ProgramArguments` → hardcoded executable path
- `WorkingDirectory` → project root
- No `PYTHONPATH` or `AUGUR_SKILL_ROOT` environment variables

**What breaks**: After migration, the daemon skill moves from `.claude/skills/daemon/` to the `augur-system` plugin at `~/.claude/plugins/cache/augur-marketplace/augur-system/{version}/skills/daemon/`. All hardcoded paths fail:
- LaunchAgent can't find the executable
- Plist template directory not found
- Service healer can't restart crashed services

**Files to update**:
| File | Change |
|------|--------|
| `daemon/scripts/service_healer.py` | Replace hardcoded `plugins/observability/skills/daemon/` with `get_skill_root("daemon")` |
| `daemon/assets/plists/*.plist.template` | Use `__SKILL_ROOT__` placeholder resolved at generation time |
| `daemon/scripts/mcp/__init__.py` | Set `SKILL_ROOT` env var in plist environment for child processes |

**Mitigation**: The daemon skill should use `get_skill_root("daemon")` (from `src.config.paths`) instead of hardcoded paths. The plist template should inject the resolved skill root as an environment variable so child processes can find their assets. This change makes the daemon portable across any install location.

**Daemon-specific test**: After updating, verify:
```bash
# Generate plist from template
augur daemon generate-plist

# Check that ProgramArguments points to actual executable
plutil -p ~/Library/LaunchAgents/com.augur.daemon.plist

# Verify service starts
launchctl load ~/Library/LaunchAgents/com.augur.daemon.plist
```

##### 5. Cross-Client Sync Impact (Gemini, Codex, Cursor, etc.)

**Current state**: ADR-426 established a client-native mastering model. Each skill declares `x-augur-master: claude-code` in SKILL.md frontmatter. The sync engine (`sync_agents` package in `ai_bridge/scripts/sync_agents/`) reads master skills from `.claude/skills/`, adapts them per-client, and writes adapted copies to `.gemini/skills/`, `.codex/prompts/`, etc. Adapted copies are marked with `<!-- AUGUR-ADAPTED-COPY source={master} -->` to prevent deletion during cleanup.

**Sync flow (current)**:
```
.claude/skills/career/SKILL.md          ← master (x-augur-master: claude-code)
         │
         ├─→ .gemini/skills/career/SKILL.md    (adapted, stripped Claude fields)
         ├─→ .codex/prompts/career/SKILL.md    (adapted, Codex format)
         ├─→ .cursor/rules/career.mdc          (adapted, Cursor format)
         └─→ [8+ other client adapters]
```

**What breaks**: The sync engine scans `CLIENT_SKILL_DIRS` which maps to project-local directories (`.claude/skills/`, `.gemini/skills/`, `.codex/prompts/`). When Claude skills move to plugin cache (`~/.claude/plugins/cache/augur-*/`):

1. **Master discovery fails** — `engine.py` iterates `CLIENT_SKILL_DIRS[".claude/skills"]` to find masters. Plugin-installed skills aren't there.
2. **Freshness check fails** — `_fix_adapted_copy_freshness()` compares mtimes across client dirs. Plugin cache masters won't be found, so adapted copies appear "orphaned" and get deleted.
3. **Auto-tag inference breaks** — `auto_tag_master()` infers master from directory: `.claude/skills/*` → `claude-code`. Plugin cache path doesn't match this inference.
4. **Orphan cleanup deletes valid copies** — Adapted copies in `.gemini/skills/career/` are valid, but their master isn't in `.claude/skills/career/` anymore. The cleanup loop would delete them as orphans.

**Design decision — two viable approaches**:

| Approach | Description | Pros | Cons |
|----------|-------------|------|------|
| **A: Scan plugin cache** | Sync engine treats plugin cache as another master location | Simple extension of existing model. One source of truth. | Plugin cache path is deep/versioned. Sync runs slower. |
| **B: Pre-adapted copies in plugins** | Each plugin ships adapted copies for all clients | No sync needed for distributed skills. Works offline. | Plugins double in size. Adapted copies may go stale. N adapters × M skills to maintain. |

**Recommendation: Approach A** — extend the sync engine to scan plugin cache dirs. This is consistent with every other integration (RAG, vault, MCP tools, mount-plugins) and keeps the sync engine as the single source of truth for cross-client adaptation.

**Files to update**:
| File | Function | Change |
|------|----------|--------|
| `ai_bridge/scripts/sync_agents/constants.py` | `CLIENT_SKILL_DIRS` | Add plugin cache path for claude-code masters |
| `ai_bridge/scripts/sync_agents/engine.py` | `sync_all_skills()` | Scan plugin cache dirs for masters (use `get_claude_plugin_skill_dirs()` from Phase 2.1) |
| `ai_bridge/scripts/sync_agents/engine.py` | `_fix_adapted_copy_freshness()` | Check plugin cache for master mtimes |
| `ai_bridge/scripts/sync_agents/engine.py` | `cleanup_orphan_adapted_copies()` | Don't orphan-delete adapted copies whose master is in plugin cache |
| `ai_bridge/scripts/sync_agents/engine.py` | `auto_tag_master()` | Infer `claude-code` for skills in plugin cache dirs (not just `.claude/skills/`) |
| `ai_bridge/scripts/sync_agents/discovery.py` | `_discover_masters()` | Include plugin cache in master scan |
| `apps/dashboard/scripts/mount/discovery.ts` | `scanClientSkillDir()` | Already skips adapted copies; must also scan plugin cache for masters |

**Sync model after migration**:
```
~/.claude/plugins/cache/augur-marketplace/
  augur-career/1.0.0/skills/career/SKILL.md    ← master (plugin-installed)
         │
         ├─→ .gemini/skills/career/SKILL.md    (adapted copy, local project)
         ├─→ .codex/prompts/career/SKILL.md    (adapted copy, local project)
         └─→ .cursor/rules/career.mdc          (adapted copy, local project)

.claude/skills/client-smb-design/SKILL.md      ← master (personal, NOT published)
         │
         ├─→ .gemini/skills/client-smb-design/SKILL.md
         └─→ [other adapters]
```

**Key invariant preserved**: Adapted copies always live in project-local client dirs (`.gemini/skills/`, `.codex/prompts/`). Only the master's location changes (from `.claude/skills/` to plugin cache). The `AUGUR-ADAPTED-COPY` marker system works identically — it doesn't care where the master is, only that adapted copies are marked.

**Sync-specific tests**:
```bash
# Install augur-career plugin
claude plugin install augur-career

# Run sync — should discover career master in plugin cache
python3 -m sync_agents --all --verbose

# Verify adapted copies created
test -f .gemini/skills/career/SKILL.md
grep "AUGUR-ADAPTED-COPY" .gemini/skills/career/SKILL.md

# Verify cleanup doesn't delete them
python3 -m sync_agents --fix
test -f .gemini/skills/career/SKILL.md  # still exists

# Verify freshness — modify master in plugin, re-sync
python3 -m sync_agents --check  # should detect stale copies
```

##### 6. Browse Page & Skill Registry Impact

**Current state**: The Browse page (`apps/dashboard/app/(views)/browse/`) shows all skills in a unified grid with filtering by hub, master client, search, and tags. Skill discovery runs through `src/plugins/skill_registry.py` which scans `.claude/skills/` (tier 2) and `~/.claude/skills/` (tier 1, global). Adapted copies are hidden via `_is_auto_generated()`. The `transformSkills()` function maps skill metadata to `BrowseItem` objects with `metadata.masterClient` badges.

**Design decision: Unified list with source badges, not separate sections.**

Users don't think "is this a plugin or a local skill?" — they think "what does this do?" Separating into "Skills" and "Plugins" tabs creates confusion. Instead, add a **source** metadata dimension to the existing Browse system.

**New metadata fields per skill**:

```typescript
// Added to BrowseItem.metadata
{
  source: "plugin" | "local" | "global",    // WHERE it comes from
  plugin: "augur-career" | null,            // WHICH plugin (if source=plugin)
  masterClient: "claude-code",              // WHO owns it (existing)
  installed: true,                          // Is the platform connected?
}
```

**Source values**:
| Source | Meaning | Badge color | Example |
|--------|---------|-------------|---------|
| `plugin` | Installed via `claude plugin install` from marketplace | Blue | career, eisenhower |
| `local` | Personal skill in project `.claude/skills/` (not published) | Gray | client-smb-design |
| `global` | User's global `~/.claude/skills/` (cross-project) | Green | custom user skills |

**New filter dimension**: Plugin name filter alongside existing hub filter:
```
[All Plugins ▾] [All Hubs ▾] [Search...]

Pills: augur-system | augur-knowledge | augur-dev | augur-career | augur-life | Local
```

**Browse card changes**: Add a subtle source indicator:
```
┌──────────────────────────────────┐
│ 🧩 Career                       │
│ Job search pipeline management   │
│                                  │
│ [career] [claude-code] [plugin: augur-career]  │
│                        ^^^^^^^^^^^^^^^^         │
│                        NEW: plugin source badge │
└──────────────────────────────────┘
```

**What changes in `skill_registry.py`**:

The discovery tier system needs a new tier for plugin-installed skills:

| Tier | Location | Source | Priority |
|------|----------|--------|----------|
| 1 | `~/.claude/skills/` | `global` | Highest (user overrides) |
| 2 | `.claude/skills/` | `local` | Project-level |
| **3** | **`~/.claude/plugins/cache/augur-*/`** | **`plugin`** | **Plugin-installed (NEW)** |
| 4 | `.gemini/skills/`, `.codex/prompts/` | *(hidden)* | Adapted copies (skipped) |

**Deduplication rule**: If a skill exists in both `.claude/skills/` (local) and plugin cache (plugin), the **local version wins** (tier 2 > tier 3). This lets users override a plugin skill by creating a local copy — same pattern as `~/.claude/skills/` overriding project skills.

**Files to update**:
| File | Change |
|------|--------|
| `src/plugins/skill_registry.py` | Add tier 3 for plugin cache scanning. Add `source` and `plugin` fields to skill metadata. |
| `apps/dashboard/lib/browse/types.ts` | Add `source` and `plugin` to BrowseItem metadata type |
| `apps/dashboard/lib/browse/transforms.ts` | `transformSkills()` maps new metadata fields to badges |
| `apps/dashboard/app/(views)/browse/BrowseToolbar.tsx` | Add plugin name filter pills |
| `apps/dashboard/components/shared/BrowseCard.tsx` | Render source badge (plugin name or "Local") |
| `apps/dashboard/app/api/browse/items/route.ts` | Pass `source`/`plugin` through from MCP response |
| MCP tool: `list-skills` (in `browse.py`) | Include `source` and `plugin` fields in response |

**What this enables for users**:
- Filter Browse to see only `augur-career` plugin skills → understand what each plugin provides
- See at a glance which skills are personal (local) vs distributed (plugin)
- Discover which plugin to install for a capability they want
- Override a plugin skill locally (tier 2 > tier 3) without uninstalling the plugin

##### 7. Docs & ADR System Impact

**Current state**: 283 ADRs (4.5M) live in `docs/decisions/` alongside 46 design docs in `docs/plans/` (1.2M) and 62 brainstorming specs/plans in `docs/superpowers/` (1.6M). Total: **7.3M of project knowledge** in the platform repo. This bloats the repo — new users installing Augur plugins don't need historical architecture decisions.

**Decision: Move all project knowledge to vault. Platform keeps only guides and auto-generated files.**

```
BEFORE (in platform repo):          AFTER (in vault):
docs/                               ~/Vault/Augur/dev/
├── decisions/ (4.5M, 283 ADRs)     ├── adrs/          (283 ADRs)
├── plans/     (1.2M, 46 docs)      ├── plans/         (46 design docs)
├── superpowers/specs/ (30 files)    ├── specs/         (brainstorming output)
├── superpowers/plans/ (32 files)    └── impl-plans/    (implementation plans)
├── generated/ (stays)
├── guides/    (stays)               DELETED:
├── agent-topics/ (stays, mirrors)   docs/archive/      (dead)
├── references/   (stays, synced)    docs/content/      (empty)
└── memory/, archive/, content/      docs/memory/       (legacy)
                                     docs/exec-plans/   (1 file)
```

**Platform `docs/` after cleanup** (~430K, down from 8M+):
```
augur-platform/docs/
├── generated/          ← auto-generated indices (nightly, reads from vault)
│   └── adr-index.md
├── guides/             ← stable how-to docs (64K)
└── agent-topics/       ← mirrors from vault (76K)
    references/         ← synced from plugins (72K)
```

**Superpowers interaction**: Superpowers is an external Claude Code plugin. When you brainstorm, it writes specs to `docs/superpowers/specs/` in the project. After migration, this path no longer exists. Two options:

| Option | How | Tradeoff |
|--------|-----|----------|
| **A: `/adr plan` moves files** | Superpowers writes to its default `docs/superpowers/specs/`. `/adr plan` reads from there and moves the spec to vault (`~/Vault/Augur/dev/specs/`), then deletes the local copy. | Works with unmodified superpowers plugin. Requires running `/adr plan` after brainstorming. |
| **B: Redirect via symlink** | `docs/superpowers/specs/` → symlink to `~/Vault/Augur/dev/specs/` | Transparent to superpowers. But symlinks in git repos are fragile. |

**Recommendation: Option A** — fits the existing workflow naturally:

```
User workflow (unchanged):
1. /brainstorming → superpowers writes docs/superpowers/specs/{date}-{topic}-design.md
2. /adr plan      → reads docs/superpowers/specs/, converts to ADR in vault, moves spec to vault
3. /adr implement → reads ADR from vault, executes
4. /adr test      → runs test cases from ADR in vault
```

`/adr plan` gains one new responsibility: after converting the spec to an ADR, **move the source spec from `docs/superpowers/specs/` to `~/Vault/Augur/dev/specs/`** and clean up the local copy. This keeps `docs/superpowers/` as a temporary inbox, not a permanent store.

**Guardrail**: Add `docs/superpowers/specs/*.md` check to the Phase 0.5 pre-commit hook — warn (not block) if specs are committed without being moved to vault. This catches forgotten `/adr plan` runs.

**Files to update**:
| File | Change |
|------|--------|
| `src/lib/adr_utils.py` | Change `ADR_DIR` from `docs/decisions/` to `get_vault_dir() / "dev" / "adrs"` |
| `.claude/skills/dev-adr/SKILL.md` | Update all path references to vault location |
| `.claude/skills/dev-adr/scripts/mcp/` | Update ADR read/write paths |
| `.github/scripts/generate_adr_index.py` | Scan vault for ADRs, write index to `docs/generated/` |
| `.claude/skills/rag/scripts/unified_indexer.py` | `index_adrs()` reads from vault path |
| `src/mcp/augur_mcp/infrastructure/browse.py` | `list_adr_impl()` reads from vault |
| `.claude/skills/ai_bridge/scripts/ops/orphan_plans.py` | Scan vault for plans |
| `auto-orphan-plans` skill | Scan vault for plans without ADR refs |
| `auto-doc-freshness` skill | Scan vault for stale ADR links |
| `CLAUDE.md` | Update ADR references to note vault location |
| `/onboard` | Seed `TEMPLATE.md` and `README.md` to vault `dev/adrs/` |

**Git history preservation**: ADR frontmatter already contains `date` and `deciders`. After the move, `git log --all -- docs/decisions/ADR-430-*` still works in the platform repo for historical attribution. The vault copy is the living document.

#### Rollback Strategy

Each phase is independently reversible:
- **Phase 0** (cleanup + docs migration): Revert all deletions and renames via `git checkout`. ADRs restored from vault copies back to `docs/decisions/`. User data files restored from vault.
- **Phase 0.5** (guardrails): Remove pre-commit hook entry, delete `validate_skill_structure.py`, remove plugin hook entries, delete `auto-skill-structure` skill.
- **Phase 1** (metadata migration): Revert SKILL.md frontmatter changes via git
- **Phase 2** (framework & integration): Revert updated files via git (paths.py, plugin_tools.py, config.py, rag scripts, daemon scripts, mount-plugins, seed discovery). Skills still work from `.claude/skills/` — all changes are additive (new scan paths), not destructive.
- **Phase 3** (plugin packaging): Delete plugin repos, skills remain in `.claude/skills/`
- **Phase 4** (marketplace): Remove marketplace, `claude plugin uninstall` all plugins, restore `.claude/skills/` from git

At no point during migration are skills deleted from the monolith until the plugin versions are verified working.

## Consequences

### Positive

- Users can install Augur via `claude plugin install augur` + `/onboard` — no pip/npm knowledge required
- Modular: install only the domains you need (dev, career, life, etc.)
- Dashboard is optional — CLI-only users skip Node.js entirely
- Marketplace discovery — Augur becomes visible in the Claude Code plugin ecosystem
- Plugin updates via `claude plugin update augur-knowledge` — no git pull required
- **Skills are self-contained** — no cross-repo editing to develop a skill. MCP tools, dashboard pages, API routes, tests, and assets all travel with the skill in the plugin
- **Skill directory structure preserved** — almost no changes to individual skill files
- **All framework changes are additive** — new scan paths added, existing paths still work during transition

### Negative

- **8 repos to maintain** (1 platform + 1 marketplace + 6 plugin repos, or monorepo with subdirectories)
- **Version coordination**: platform shared lib changes (`src.config.paths`, `src.lib.*`) may affect all plugin skills that import them
- **Two-step install**: platform (pip) + plugins (claude plugin) instead of one clone
- **131 skills need individual frontmatter audit** for the metadata migration
- **Plugin install path is deep**: `~/.claude/plugins/cache/augur-marketplace/augur-career/1.0.0/skills/career/` — framework code must handle this reliably

### Neutral

- Personal/client skills (consulting, enterprise) continue working from `.claude/skills/` exactly as today
- MCP tool contract (tool names, input/output schemas) is unchanged
- Dashboard page behavior is unchanged — mount-plugins just has a new source location
- The adaptive hub's zero-MCP architecture makes it the easiest to extract
- Developing skills locally still works in `.claude/skills/` — plugins are for distribution

## Alternatives Considered

### Alternative 1: Single Monolithic Plugin

Package all 131 skills as one `augur` plugin.

**Rejected because**: Too large, all-or-nothing (same problem as current monolith), and forces non-technical users to understand the full system.

### Alternative 2: One Plugin Per Hub (15 Plugins)

Direct 1:1 mapping from hubs to plugins.

**Rejected because**: Too many small plugins (core has 2 skills, enterprise has 1, home has 1). Users face decision fatigue choosing from 15 options.

### Alternative 3: Skills-Only Plugins (Strip Code to Platform)

Extract only SKILL.md and reference docs into plugins. Move all MCP tools, scripts, dashboard pages, API routes, tests, and assets into the platform repo.

**Rejected because**: Breaks skill self-containment. Developing a skill means editing two repos. Tests get separated from the code they test. The MCP server already has dynamic loading — centralizing tools is unnecessary work that adds risk and complexity.

### Alternative 4: Monorepo With Plugin Subdirectories

Instead of 8 separate GitHub repos, use one monorepo with a build script that generates plugin packages.

**Considered and viable**: This avoids multi-repo maintenance overhead. The marketplace can point to subdirectories in a single repo. Recommend evaluating during Phase 3 — if multi-repo coordination proves painful, consolidate into monorepo with build-time packaging.

## References

- ADR-012: Community Package Extraction (dynamic MCP tool loading from plugins)
- ADR-426: Client-Native Skill Mastering (skills already in `.claude/skills/`)
- ADR-428: Missing MCP Tools Implementation (platform tool inventory)
- ADR-163: Plugin Architecture Integrity (decentralization principle)
- `src/mcp/augur_mcp/plugin_tools.py` — dynamic tool loading implementation
- Claude Code plugin documentation: `claude plugin --help`, `claude plugin marketplace --help`
- Superpowers plugin as reference implementation: `~/.claude/plugins/cache/claude-plugins-official/superpowers/`

## Impact Manifest

```yaml
impact:
  paths_renamed:
    - from: ".claude/skills/{skill}/augur/augur.yaml"
      to: "SKILL.md x-augur-* frontmatter (fields absorbed)"
    - from: ".claude/skills/{skill}/assets/seed-data/"
      to: ".claude/skills/{skill}/assets/seeds/"
    - from: ".claude/skills/{skill}/assets/prompts/"
      to: ".claude/skills/{skill}/assets/seeds/prompts/ (consolidated)"
    - from: "docs/decisions/ADR-*.md"
      to: "~/Vault/Augur/dev/adrs/ADR-*.md"
    - from: "docs/plans/*.md"
      to: "~/Vault/Augur/dev/plans/*.md"
    - from: "docs/superpowers/specs/"
      to: "~/Vault/Augur/dev/specs/"
    - from: "docs/superpowers/plans/"
      to: "~/Vault/Augur/dev/impl-plans/"
  apis_changed: []
  patterns_deprecated:
    - "augur.yaml as skill metadata (replaced by SKILL.md x-augur-* frontmatter)"
    - "augur/version.yaml (replaced by plugin.json version)"
    - ".config enable/disable files (replaced by claude plugin enable/disable)"
    - "augur/data/ directories (stale duplicates of assets/seed-data/, deleted)"
    - "augur/README.md (auto-generated, deleted)"
    - "augur/api/tsconfig.json and augur/dashboard/tsconfig.json (auto-generated, gitignored)"
    - "assets/prompts/ as separate directory (consolidated into assets/seeds/prompts/)"
    - "docs/decisions/ as ADR storage (moved to vault ~/Vault/Augur/dev/adrs/)"
    - "docs/plans/ as design doc storage (moved to vault ~/Vault/Augur/dev/plans/)"
    - "docs/superpowers/ as brainstorming output storage (moved to vault, /adr plan moves files)"
  files_affected:
    - ".claude/skills/*/SKILL.md"
    - ".claude/skills/*/augur/augur.yaml"
    - ".claude/skills/*/.config"
    - ".claude/skills/*/augur/data/"
    - ".claude/skills/*/augur/README.md"
    - ".claude/skills/*/augur/version.yaml"
    - ".claude/skills/*/assets/prompts/"
    - ".claude/skills/*/assets/seed-data/"
    - "src/mcp/augur_mcp/plugin_tools.py"
    - "src/config/paths.py"
    - "scripts/mount-plugins.*"
    - ".gitignore"
    - "CLAUDE.md"
```

## Implementation Prompt

> Single-command orchestrator. Run `/adr implement ADR-430` — agents handle everything.
> Each sub-ADR runs as a team with full parallelism. Dependency gates block until prerequisites pass.

**Team name**: `adr-430-orchestrator`
**Execution model**: Teams with 1M context per agent. No batching needed.

### Orchestration Pipeline

```
/adr implement ADR-430
    │
    ├── [1] Implement ADR-431 (Cleanup & Guardrails)
    │       Team: adr-431-cleanup
    │       8 parallel agents (cleanup) → gate → 3 parallel agents (guardrails) → gate
    │       ~15 min wall time
    │
    │── [GATE] Verify ADR-431 completion criteria
    │       Zero garbage, zero duplicates, ADRs in vault, guardrails active
    │       BLOCK if any criterion fails
    │
    ├── [2] Implement ADR-432 (Metadata & Framework)
    │       Team: adr-432-framework
    │       4 parallel (metadata) → gate → 3 sequential (paths core) → gate → 8 parallel (consumers) → gate
    │       ~30 min wall time
    │
    │── [GATE] Verify ADR-432 completion criteria
    │       Framework scans plugin cache, all integration systems updated
    │       BLOCK if any criterion fails
    │
    ├── [3] Implement ADR-433 (Packaging & Marketplace)
    │       Team: adr-433-packaging
    │       9 parallel agents (one per plugin + marketplace)
    │       ~10 min wall time
    │
    │── [GATE] Verify ADR-433 completion criteria
    │       All plugins validate, marketplace installs cleanly
    │       BLOCK if any criterion fails
    │
    ├── [4] Implement ADR-434 (Migration Verification)
    │       Team: adr-434-verification
    │       7 parallel agents (test categories)
    │       ~20 min wall time
    │
    └── [GATE] Final — all 4 sub-ADRs Implemented
            Mark ADR-430 status → Implemented
```

**Total estimated wall time**: ~75 min (with 1M context + teams)

### Sub-ADR Dependency Graph

```
ADR-431 ──→ ADR-432 ──→ ADR-433 ──→ ADR-434 ──→ ADR-430 ✓
(cleanup)   (framework)  (package)   (verify)     (done)
```

Each sub-ADR has its own:
- Implementation prompt with team-based agents
- Completion criteria (gate checks)
- Rollback strategy
- Full details in `docs/decisions/ADR-{431-434}-*.md`

### Gate Protocol

Between each sub-ADR, the orchestrator runs gate checks. If ANY check fails:

1. **Identify** which agent's work caused the failure
2. **Fix** the specific issue (dispatch a targeted fix agent)
3. **Re-run** only the failed gate checks (not the entire sub-ADR)
4. **Proceed** only when all checks pass

The orchestrator does NOT skip gates or proceed optimistically.

### Execution Steps

**Step 1**: Read and implement ADR-431 (`docs/decisions/ADR-431-plugin-cleanup-guardrails.md`)
- Create team `adr-431-cleanup`
- Dispatch all Batch A agents in parallel
- Wait for completion, run Gate 1 checks
- Dispatch Batch B agents in parallel
- Wait for completion, run Gate 2 checks
- Mark ADR-431 → Implemented

**Step 2**: Read and implement ADR-432 (`docs/decisions/ADR-432-plugin-metadata-framework.md`)
- Create team `adr-432-framework`
- Dispatch Batch A agents (metadata) in parallel
- Wait, run Gate 1 checks
- Dispatch Sequential agents (paths core) one by one
- Wait, run Gate 2 checks
- Dispatch Batch B agents (consumers) in parallel
- Wait, run Gate 3 checks
- Mark ADR-432 → Implemented

**Step 3**: Read and implement ADR-433 (`docs/decisions/ADR-433-plugin-packaging-marketplace.md`)
- Create team `adr-433-packaging`
- Dispatch all 9 agents in parallel
- Wait, run Gate 1 + Gate 2 checks
- Mark ADR-433 → Implemented

**Step 4**: Read and implement ADR-434 (`docs/decisions/ADR-434-plugin-migration-verification.md`)
- Create team `adr-434-verification`
- Dispatch all 7 test agents in parallel
- Wait, run Gate 1 + Gate 2 + Gate 3 checks
- Mark ADR-434 → Implemented
- Mark ADR-430 → Implemented

### Phase Details (in sub-ADRs)

Detailed implementation prompts, agent tables, and gate checks are in the sub-ADRs:

| Sub-ADR | Phase | File | Agents |
|---------|-------|------|--------|
| ADR-431 | 0 + 0.5 | `ADR-431-plugin-cleanup-guardrails.md` | 8 cleanup + 3 guardrail |
| ADR-432 | 1 + 2 | `ADR-432-plugin-metadata-framework.md` | 4 metadata + 3 sequential + 8 consumer |
| ADR-433 | 3 | `ADR-433-plugin-packaging-marketplace.md` | 9 packaging |
| ADR-434 | 4 | `ADR-434-plugin-migration-verification.md` | 7 test categories |

> **HISTORICAL NOTE**: The detailed phase tables below are preserved for reference but are superseded by the sub-ADR implementation prompts above. The orchestrator reads the sub-ADRs, not these tables.

### Phase 0: Skill Directory Cleanup & Standardization (→ ADR-431)
**Strategy**: PARALLEL (steps 0.1-0.4 are independent, 0.5-0.6 depend on 0.1-0.4)

This phase normalizes all 131 skill directories to a canonical structure before any plugin packaging. Eliminates duplicates, removes generated artifacts, moves user data to vault, and standardizes naming. Low-risk, fully reversible via git.

#### Canonical Skill Structure (Target)

```
{skill}/
├── SKILL.md                          ← SINGLE metadata source (absorbs augur.yaml)
├── scripts/                          ← Runtime code
│   ├── mcp/                          ← MCP tool registrations
│   │   ├── __init__.py               ← register_tools() entry point
│   │   └── tools_*.py                ← Tool implementations
│   └── *.py                          ← Business logic (imported by MCP tools)
├── assets/                           ← Templates & seeds
│   ├── actions/                      ← Action prompt templates (frontmatter .md)
│   └── seeds/                        ← Vault initialization data
│       ├── _seed.yaml                ← Manifest of seed directories
│       ├── prompts/                  ← SINGLE prompt location (no duplication)
│       └── {entity}/                 ← Seed data by category
├── augur/                            ← Dashboard integration
│   ├── dashboard/                    ← React pages (mount-plugins copies)
│   ├── api/                          ← API routes (mount-plugins copies)
│   ├── tests/                        ← Python tests
│   └── modules/                      ← Reference documentation
└── references/                       ← Supporting docs (optional)
```

**Deleted files** (per skill):
- `.config` — replaced by plugin enable/disable
- `augur/augur.yaml` — absorbed into SKILL.md frontmatter (Phase 1)
- `augur/version.yaml` — replaced by plugin.json version
- `augur/README.md` — auto-generated, not source
- `augur/data/` — stale duplicates of assets/seed-data/
- `augur/api/tsconfig.json` — auto-generated by mount-plugins
- `augur/dashboard/tsconfig.json` — auto-generated by mount-plugins
- `assets/prompts/` — consolidated into `assets/seeds/prompts/`
- `requirements.txt` — moved to plugin-level

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 0.1 | garbage-cleaner | low | Delete all `.DS_Store` files (26 found), `__pycache__/` directories, and add patterns to `.gitignore`: `**/.DS_Store`, `**/__pycache__/`, `.claude/skills/*/augur/README.md`, `.claude/skills/*/augur/api/tsconfig.json`, `.claude/skills/*/augur/dashboard/tsconfig.json`. | `.gitignore`, `.claude/skills/` |
| 0.2 | generated-deleter | low | Delete auto-generated files from all 131 skills: `augur/README.md`, `augur/api/tsconfig.json`, `augur/dashboard/tsconfig.json`. Verify mount-plugins regenerates them on next run. | `.claude/skills/*/augur/` |
| 0.3 | user-data-mover | medium | Move user-generated artifacts out of git into vault: (1) `career/assets/reports/*.xlsx,*.html` → `~/Vault/Augur/career/reports/`, (2) `apple/assets/voice-memos/audio/*.m4a` → `~/Vault/Augur/apple/voice-memos/`, (3) `finance/assets/zero-cost-collar-avgo.docx` → `~/Vault/Augur/finance/documents/`. Run `git rm --cached` for each. Add gitignore patterns: `assets/**/*.xlsx`, `assets/**/*.docx`, `assets/**/*.m4a`, `assets/voice-memos/audio/`. | `.claude/skills/career/assets/reports/`, `.claude/skills/apple/assets/voice-memos/`, `.claude/skills/finance/assets/` |
| 0.4 | prompt-consolidator | medium | For all skills with duplicate prompts: (1) Delete `augur/data/prompts/` everywhere (stale TODO stubs). (2) Delete `augur/data/` directory if empty after prompt removal. (3) Merge `assets/prompts/` content into `assets/seed-data/prompts/` (keep the richer version, deduplicate). (4) Delete `assets/prompts/` directory. (5) Update any code references from `assets/prompts/` or `augur/data/prompts/` to `assets/seeds/prompts/`. Verify by grepping for old paths. | `.claude/skills/*/augur/data/`, `.claude/skills/*/assets/prompts/`, `.claude/skills/*/assets/seed-data/prompts/` |
| 0.5 | seed-renamer | low | Rename `assets/seed-data/` to `assets/seeds/` across all skills. Update any references in code (grep for `seed-data` in scripts/, augur/, SKILL.md). | `.claude/skills/*/assets/seed-data/` |
| 0.6 | docs-migrator | high | Move project knowledge to vault: (1) `docs/decisions/*.md` → `~/Vault/Augur/dev/adrs/` (283 files, 4.5M). (2) `docs/plans/*.md` → `~/Vault/Augur/dev/plans/` (46 files, 1.2M). (3) `docs/superpowers/specs/` → `~/Vault/Augur/dev/specs/`. (4) `docs/superpowers/plans/` → `~/Vault/Augur/dev/impl-plans/`. (5) Delete dead dirs: `docs/archive/`, `docs/content/`, `docs/memory/`, `docs/exec-plans/`. (6) Update `src/lib/adr_utils.py` `ADR_DIR` to vault path. (7) Update `generate_adr_index.py` to scan vault. (8) Update `CLAUDE.md` ADR references. Verify: `/adr query 430` returns ADR from vault. `/adr status` reads index from vault. | `docs/decisions/`, `docs/plans/`, `docs/superpowers/`, `src/lib/adr_utils.py`, `.github/scripts/generate_adr_index.py`, `CLAUDE.md` |
| 0.7 | adr-plan-update | medium | Update `/adr plan` flow: after converting a brainstorming spec to an ADR, move the source spec from `docs/superpowers/specs/` to `~/Vault/Augur/dev/specs/` and delete the local copy. Update dev-adr SKILL.md `plan` subcommand. Add `docs/superpowers/specs/*.md` warning to Phase 0.5 pre-commit hook (warn if specs committed without vault move). | `.claude/skills/dev-adr/SKILL.md` |
| 0.8 | metadata-reducer | medium | Delete per-skill metadata files that will be replaced: (1) `.config` from all 131 skills. (2) `augur/version.yaml` from all skills that have it (~50). (3) Per-skill `requirements.txt` (consolidate to plugin-level later). (4) Fix finance `data_dir: .` to `data_dir: finance` in augur.yaml (before Phase 1 deletes it). Report any skills with non-standard `.config` values (not just `enabled: true, status: stable`). | `.claude/skills/*/.config`, `.claude/skills/*/augur/version.yaml`, `.claude/skills/*/requirements.txt` |

**Verification**:
- Zero `.DS_Store`, `__pycache__/`, `augur/README.md`, `augur/api/tsconfig.json`, `augur/dashboard/tsconfig.json` in `.claude/skills/`
- Zero `augur/data/` directories remain
- Zero `assets/prompts/` directories remain (consolidated into `assets/seeds/prompts/`)
- All `assets/seed-data/` renamed to `assets/seeds/`
- Zero `.config`, `augur/version.yaml`, or per-skill `requirements.txt` files remain
- No user data files (`.xlsx`, `.docx`, `.m4a`) in git
- `mount-plugins` still works (regenerates tsconfig.json files)
- `npm run build` passes
- `pytest` passes
- Git diff shows only deletions and renames — no functional changes

### Phase 0.5: Structure Guardrails (Prevent Regression)
**Strategy**: PIPELINE

Cleanup without guardrails re-degrades within weeks. This step installs enforcement at three layers: git pre-commit (blocks bad commits), Claude hooks (warns during sessions), and adaptive scans (catches drift nightly).

#### Layer 1: Pre-Commit Hook — `validate-skill-structure`

New pre-commit hook added to `.pre-commit-config.yaml` (joins the existing 13 hooks):

```python
# .github/scripts/validate_skill_structure.py
#
# Runs on every commit touching .claude/skills/
# Exit 1 = block commit with error message
#
# Checks:
# 1. BANNED FILES — files that Phase 0 deleted must not return
# 2. BANNED DIRECTORIES — deprecated dirs must not be recreated
# 3. USER DATA — binary/media files must not be in skills
# 4. CANONICAL STRUCTURE — new skills must have required files
```

| Check | Pattern | Action |
|-------|---------|--------|
| No `.config` files | `.claude/skills/*/.config` | Block commit |
| No `augur/augur.yaml` | `.claude/skills/*/augur/augur.yaml` | Block commit (use SKILL.md frontmatter) |
| No `augur/version.yaml` | `.claude/skills/*/augur/version.yaml` | Block commit (use plugin.json) |
| No `augur/README.md` | `.claude/skills/*/augur/README.md` | Block commit (auto-generated) |
| No `augur/data/` dirs | `.claude/skills/*/augur/data/` | Block commit (stale pattern) |
| No `assets/prompts/` dirs | `.claude/skills/*/assets/prompts/` | Block commit (use assets/seeds/prompts/) |
| No `augur/api/tsconfig.json` | `.claude/skills/*/augur/api/tsconfig.json` | Block commit (auto-generated) |
| No `augur/dashboard/tsconfig.json` | `.claude/skills/*/augur/dashboard/tsconfig.json` | Block commit (auto-generated) |
| No per-skill `requirements.txt` | `.claude/skills/*/requirements.txt` | Block commit (plugin-level) |
| No user media | `.claude/skills/**/*.{xlsx,docx,m4a,mp3,mp4,wav,pptx}` | Block commit (move to vault) |
| No `.DS_Store` | `.claude/skills/**/.DS_Store` | Block commit |
| SKILL.md required | new skill dir without `SKILL.md` | Block commit |
| x-augur-plugin required | SKILL.md missing `x-augur-plugin` frontmatter | Block commit (after Phase 1) |

Pre-commit config entry:
```yaml
- repo: local
  hooks:
    - id: validate-skill-structure
      name: Validate skill directory structure (ADR-430)
      entry: python3 .github/scripts/validate_skill_structure.py
      language: python
      files: '^\.claude/skills/'
      pass_filenames: true
```

#### Layer 2: Plugin Hook — `PostToolUse` on Write/Edit

Each Augur plugin includes a PostToolUse hook that warns (not blocks) when Claude writes to a deprecated path. This catches mistakes during development sessions before they reach commit.

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "\"${CLAUDE_PLUGIN_ROOT}/hooks/check-skill-structure\"",
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```

The `check-skill-structure` hook script:
```bash
#!/bin/bash
# Read tool input from stdin (JSON with file_path)
INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tool_input',{}).get('file_path',''))" 2>/dev/null)

# Check for banned patterns
BANNED_PATTERNS=(
  "/augur/augur.yaml"
  "/augur/version.yaml"
  "/augur/README.md"
  "/augur/data/"
  "/assets/prompts/"
  "/.config"
)

for PATTERN in "${BANNED_PATTERNS[@]}"; do
  if [[ "$FILE_PATH" == *"$PATTERN" ]]; then
    echo "{\"continue\": true, \"systemMessage\": \"WARNING (ADR-430): Writing to deprecated path '$PATTERN'. Use the canonical location instead. See Phase 0 in ADR-430.\"}"
    exit 0
  fi
done
```

This hook:
- Runs after every Write/Edit in skills directories
- Emits a warning (not a block) — exit 0, not exit 2
- Injects a `systemMessage` that Claude sees, so it self-corrects
- Lightweight (< 5ms, no blocking)

#### Layer 3: Adaptive Command — `auto-skill-structure`

New adaptive auto-command that runs nightly (joins the existing 50+ auto-* commands). Catches drift that bypasses pre-commit (e.g., manual file creation, script-generated files).

| Check | Scan |
|-------|------|
| Banned files | Glob for all patterns from Layer 1 |
| Orphan `augur/` subdirs | Skill dirs with `augur/` content but no SKILL.md |
| Prompt duplication | Skills with both `assets/seeds/prompts/` and `assets/prompts/` |
| Missing frontmatter | SKILL.md files without `x-augur-plugin` field |
| User data in git | Binary files in skills (by extension and size > 100KB) |
| Stale metadata | Any `augur.yaml`, `.config`, `version.yaml` files |

Reports findings via the standard adaptive loop output format. At max difficulty, evolves to also check:
- Cross-plugin import consistency (no skill importing from another plugin's skill)
- Seed data freshness (seeds match vault schema)
- Dashboard page mount verification (pages in plugin match what's mounted)

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 0.5.1 | guardrail-precommit | medium | Create `.github/scripts/validate_skill_structure.py` with all banned pattern checks. Add entry to `.pre-commit-config.yaml`. Test by attempting to commit a `.config` file — verify it blocks. | `.github/scripts/validate_skill_structure.py`, `.pre-commit-config.yaml` |
| 0.5.2 | guardrail-plugin-hook | medium | Create `hooks/check-skill-structure` script for the platform. Add PostToolUse hook entry to each plugin's `hooks/hooks.json`. Test by writing to `augur/augur.yaml` — verify warning appears. | Plugin `hooks/` directories |
| 0.5.3 | guardrail-adaptive | medium | Create `auto-skill-structure` adaptive command. SKILL.md, augur.yaml, scanner script. Register in adaptive hub. Test by creating a banned file and running the scan. | `.claude/skills/auto-skill-structure/` |

**Verification**:
- `git add .claude/skills/test-skill/.config && git commit` → **blocked** with clear error message
- Writing to `augur/augur.yaml` in a Claude session → **warning** in transcript
- `auto-skill-structure` scan finds zero violations after Phase 0 cleanup
- All 3 guardrails are independent — any one failing doesn't break the others

### Phase 1: Metadata Migration & Classification Audit
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | metadata-migrator | medium | For all 131 skills: read `augur/augur.yaml`, extract all fields, write them as `x-augur-*` frontmatter into SKILL.md. Preserve existing frontmatter. Delete `augur.yaml` after migration. | `.claude/skills/*/SKILL.md`, `.claude/skills/*/augur/augur.yaml` |
| 1.2 | adaptive-classifier | medium | Classify each of 52 adaptive skills as "code-focused" or "dashboard-focused" based on what they scan (grep for dashboard/page/route/block references vs code/config references). Output classification table with plugin assignment. | `.claude/skills/auto-*/SKILL.md` |
| 1.3 | cross-ref-auditor | medium | Audit all SKILL.md files for relative path references to other skills (`../`, `../../`). Convert to skill name references. Report all changes. | `.claude/skills/*/SKILL.md` |
| 1.4 | unassigned-fixer | low | Assign hub and plugin to `executor` and `reindex-rag` (currently missing augur.yaml). Create their `x-augur-*` frontmatter. | `.claude/skills/executor/`, `.claude/skills/reindex-rag/` |

**Verification**: All SKILL.md files have `x-augur-plugin` frontmatter. Zero `augur.yaml` files remain. Zero relative path cross-references. Classification table reviewed and approved.

### Phase 2: Framework & Integration Update
**Strategy**: PIPELINE

Phase 2 is expanded from 3 files to cover all 4 integration systems identified in the impact analysis.

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | paths-core | high | Update `src/config/paths.py`: (1) Add `get_claude_plugin_skill_dirs()` to scan `~/.claude/plugins/cache/augur-*/` for skill directories. (2) Update `get_all_client_skill_dirs()` to include plugin cache dirs. (3) Update `_discover_skill_to_bundle_mapping()` to read `x-augur-hub` from SKILL.md frontmatter instead of `contributes_to` from augur.yaml. (4) Update `get_skill_root()` to also check plugin cache paths. | `src/config/paths.py` |
| 2.2 | mcp-discovery | high | Update `plugin_tools.py:_collect_skill_dirs()` to scan plugin cache dirs (uses `get_claude_plugin_skill_dirs()` from 2.1). Handle version directory selection (latest). Add `augur-` prefix filter. | `src/mcp/augur_mcp/plugin_tools.py` |
| 2.3 | vault-resolution | high | Update `src/mcp/augur_mcp/config.py`: (1) `get_skill_data_dir()` must scan plugin cache dirs for skill discovery. (2) `_resolve_client_skill_bundle()` must parse SKILL.md frontmatter (`x-augur-hub`) instead of augur.yaml (`contributes_to`). Both now depend on 2.1 helpers. | `src/mcp/augur_mcp/config.py` |
| 2.4 | rag-indexer | high | Update RAG system: (1) `_indexer_helpers.py:_discover_skill_dirs()` — use updated `get_all_client_skill_dirs()`. (2) `rag_indexer.py:resolve_rag_output_root()` — handle plugin cache paths mapping to `{bundle}/{skill_name}` output. (3) `rag_tools.py:_resolve_scope_paths()` — resolve plugin-installed skills to correct RAG indices. (4) `rag_reindex.py` — scan plugin cache dirs for reindex jobs. (5) `scripts/bulk_index.py` — include plugin cache in scan. | `.claude/skills/rag/scripts/_indexer_helpers.py`, `.claude/skills/rag/scripts/rag_indexer.py`, `.claude/skills/rag/scripts/mcp/rag_tools.py`, `.claude/skills/ai_bridge/scripts/ops/rag_reindex.py`, `scripts/bulk_index.py` |
| 2.5 | daemon-portability | high | Update daemon skill: (1) `service_healer.py` — replace all hardcoded `plugins/observability/skills/daemon/` paths with `get_skill_root("daemon")`. (2) Plist templates — use `__SKILL_ROOT__` placeholder resolved at generation time. (3) Add `AUGUR_SKILL_ROOT` and `PYTHONPATH` environment variables to plist template. (4) Test LaunchAgent generation and service start from new path. | `.claude/skills/daemon/scripts/service_healer.py`, `.claude/skills/daemon/assets/plists/*.plist.template`, `.claude/skills/daemon/scripts/mcp/__init__.py` |
| 2.6 | mount-plugins | high | Update `mount-plugins` to also scan Claude Code plugin install directories for `augur/dashboard/` and `augur/api/` resources. Uses `get_claude_plugin_skill_dirs()` from 2.1. | `scripts/mount-plugins.*` |
| 2.7 | seed-discovery | medium | Update auto-seed-data and `/import` skill: seed discovery must scan plugin cache dirs to find `assets/seeds/` for newly installed plugins. `/onboard` copies seeds from plugin dirs to vault on first install. | `.claude/skills/import/scripts/`, `.claude/skills/auto-seed-data/` |
| 2.8 | cross-skill-paths | medium | Audit and fix all `Path(__file__).parent` patterns that navigate OUTSIDE the skill directory. Grep for patterns like `parent.parent.parent.parent` or references to `plugins/` in scripts. Convert to `get_skill_root()` calls. | `.claude/skills/*/scripts/**/*.py` |
| 2.10 | adr-consumers | medium | Update all ADR consumers to read from vault: (1) `unified_indexer.py:index_adrs()` — scan `~/Vault/Augur/dev/adrs/` instead of `docs/decisions/`. (2) `browse.py:list_adr_impl()` — read from vault. (3) `orphan_plans.py` — scan `~/Vault/Augur/dev/plans/` for orphans vs vault ADRs. (4) `auto-doc-freshness` — scan vault ADR links. (5) Dev-adr MCP tools — all read/write vault. Verify: Browse ADR category shows all 283 ADRs from vault. RAG `/ask` returns ADR content. | `.claude/skills/rag/scripts/unified_indexer.py`, `src/mcp/augur_mcp/infrastructure/browse.py`, `.claude/skills/ai_bridge/scripts/ops/orphan_plans.py`, `.claude/skills/dev-adr/scripts/mcp/` |
| 2.11 | browse-registry | medium | Update Browse page and skill registry: (1) `skill_registry.py` — add tier 3 for plugin cache scanning, add `source` and `plugin` fields to skill metadata. (2) MCP `list-skills` tool — include `source`/`plugin` in response. (3) `transforms.ts:transformSkills()` — map new fields to BrowseItem badges. (4) `BrowseToolbar.tsx` — add plugin name filter pills. (5) `BrowseCard.tsx` — render source badge. (6) Deduplication: local (tier 2) overrides plugin (tier 3). | `src/plugins/skill_registry.py`, `src/mcp/augur_mcp/infrastructure/browse.py`, `apps/dashboard/lib/browse/transforms.ts`, `apps/dashboard/lib/browse/types.ts`, `apps/dashboard/app/(views)/browse/BrowseToolbar.tsx`, `apps/dashboard/components/shared/BrowseCard.tsx` |
| 2.9 | sync-engine | high | Update cross-client sync engine: (1) `constants.py` — add plugin cache to `CLIENT_SKILL_DIRS` for Claude masters. (2) `engine.py:sync_all_skills()` — scan plugin cache via `get_claude_plugin_skill_dirs()`. (3) `engine.py:cleanup_orphan_adapted_copies()` — don't delete adapted copies whose master is in plugin cache. (4) `engine.py:_fix_adapted_copy_freshness()` — check plugin cache for master mtimes. (5) `engine.py:auto_tag_master()` — infer `claude-code` for plugin cache skills. (6) `discovery.py` — include plugin cache in master scan. (7) `mount/discovery.ts:scanClientSkillDir()` — scan plugin cache for master skills. Test by installing a plugin and verifying adapted copies are generated for Gemini/Codex. | `.claude/skills/ai_bridge/scripts/sync_agents/constants.py`, `.claude/skills/ai_bridge/scripts/sync_agents/engine.py`, `.claude/skills/ai_bridge/scripts/sync_agents/discovery.py`, `apps/dashboard/scripts/mount/discovery.ts` |

**Verification**:
- `augur mcp serve` starts and loads tools from both `.claude/skills/` and a test plugin directory
- `get_skill_data_dir("career")` resolves correctly for both local and plugin-installed skills
- `get_skill_bundle("career")` reads `x-augur-hub` from SKILL.md frontmatter (not augur.yaml)
- RAG reindex discovers and indexes skills from plugin cache dirs
- RAG search returns results for plugin-installed skills
- Daemon LaunchAgent generates correct plist with dynamic `__SKILL_ROOT__` path
- Daemon service starts successfully from plugin install location
- `mount-plugins` finds dashboard/API resources from plugin cache locations
- Seed data copied from plugin-installed skill to vault on `/onboard`
- Zero `Path(__file__)` navigations that exit the skill directory boundary
- `sync_agents --all` discovers masters in plugin cache and generates adapted copies in `.gemini/skills/`, `.codex/prompts/`
- `sync_agents --fix` cleanup does NOT delete adapted copies whose master is in plugin cache
- Freshness check detects stale adapted copies when plugin-installed master is newer
- Browse page lists plugin-installed skills with `source: plugin` and `plugin: augur-{name}` badges
- Browse filter by plugin name shows only that plugin's skills
- Local skill in `.claude/skills/career/` overrides plugin-installed `career` in Browse (tier 2 > tier 3)
- Browse ADR category lists all 283 ADRs from vault location
- RAG `/ask "what is ADR-430"` returns content from vault
- `/adr query 430` reads from vault, not `docs/decisions/`
- `npm run build` passes
- `pytest` passes

### Phase 3: Plugin Packaging
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | plugin-packager-bootstrap | medium | Create `augur` plugin: `.claude-plugin/plugin.json`, onboard skill (full directory), check-platform hook. Validate with `claude plugin validate`. | New: `augur/` |
| 3.2 | plugin-packager-system | medium | Create `augur-system` plugin. Copy full skill directories for 15 skills. Create plugin.json. Validate. | New: `augur-system/` |
| 3.3 | plugin-packager-knowledge | medium | Create `augur-knowledge` plugin. Copy full skill directories for 12 skills. Create plugin.json. Validate. | New: `augur-knowledge/` |
| 3.4 | plugin-packager-dashboard | medium | Create `augur-dashboard` plugin. Copy full skill directories for ~16 skills. Create dashboard-setup skill. Add hooks. Validate. | New: `augur-dashboard/` |
| 3.5 | plugin-packager-adaptive | medium | Create `augur-adaptive` plugin. Copy full skill directories for ~44 skills. Create plugin.json. Validate. | New: `augur-adaptive/` |
| 3.6 | plugin-packager-dev | medium | Create `augur-dev` plugin. Copy full skill directories for ~11 skills. Create plugin.json. Validate. | New: `augur-dev/` |
| 3.7 | plugin-packager-life | medium | Create `augur-life` plugin. Copy full skill directories for 12 skills. Create plugin.json. Validate. | New: `augur-life/` |
| 3.8 | plugin-packager-career | medium | Create `augur-career` plugin. Copy full skill directories for 10 skills. Create plugin.json. Validate. | New: `augur-career/` |
| 3.9 | marketplace-creator | medium | Create `augur-marketplace` with marketplace.json listing all 8 plugins. Validate with `claude plugin validate`. | New: `augur-marketplace/` |

**Verification**: `claude plugin validate` passes for all 8 plugins and the marketplace. Each plugin installs cleanly via `claude plugin install`. Each plugin's skills appear in `/commands`. MCP tools from installed plugins are discovered by `augur mcp serve`.

### Phase 4: Integration Testing & Cutover
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 4.1 | fresh-install-tester | high | On a clean machine (or clean user profile): add marketplace, install augur, run /onboard. Verify platform installs, MCP connects, skills work, MCP tools from plugins are discovered. | All plugins |
| 4.2 | existing-user-migrator | high | Test /onboard --migrate path: verify it detects current .claude/skills/ structure, installs matching plugins, preserves personal skills. | augur bootstrap plugin |
| 4.3 | skill-parity-verifier | high | For each plugin: verify every skill's slash command works, MCP tools respond, and (if dashboard installed) pages render. Compare behavior to pre-migration baseline. | All plugins |
| 4.4 | claude-md-updater | medium | Update CLAUDE.md generation to reference plugin-based skill discovery alongside .claude/skills/ scanning. | `CLAUDE.md`, generation scripts |

**Verification**: Fresh install produces working system. Migration preserves all functionality. No skill regressions. CLAUDE.md accurate.

### Completion Criteria

**Phase 0 (Cleanup)**:
- [ ] Zero `.DS_Store`, `__pycache__/`, auto-generated files in `.claude/skills/`
- [ ] Zero `augur/data/` directories remain (stale duplicates deleted)
- [ ] Zero `assets/prompts/` directories remain (consolidated into `assets/seeds/prompts/`)
- [ ] All `assets/seed-data/` renamed to `assets/seeds/`
- [ ] Zero `.config`, `augur/version.yaml`, or per-skill `requirements.txt` remain
- [ ] No user data files (`.xlsx`, `.docx`, `.m4a`) in git
- [ ] `.gitignore` updated with patterns for auto-generated and user data files
- [ ] All ADRs moved to `~/Vault/Augur/dev/adrs/` (283 files)
- [ ] All plans moved to `~/Vault/Augur/dev/plans/` (46 files)
- [ ] All superpowers specs/plans moved to vault
- [ ] Dead dirs deleted (`docs/archive/`, `docs/content/`, `docs/memory/`, `docs/exec-plans/`)
- [ ] `src/lib/adr_utils.py` reads/writes from vault path
- [ ] `/adr query`, `/adr status` work from vault
- [ ] `/adr plan` moves superpowers specs from `docs/superpowers/specs/` to vault after conversion

**Phase 0.5 (Guardrails)**:
- [ ] Pre-commit hook `validate-skill-structure` blocks commits with banned files
- [ ] Plugin PostToolUse hook warns when writing to deprecated paths
- [ ] `auto-skill-structure` adaptive command scans for structure violations
- [ ] All 3 guardrails tested and verified working

**Phase 1 (Metadata)**:
- [ ] All 131 skills have x-augur-* frontmatter with plugin assignment
- [ ] All augur.yaml files deleted (metadata absorbed into SKILL.md)
- [ ] All 52 adaptive skills classified as code-focused or dashboard-focused
- [ ] Zero relative path cross-references between skills

**Phase 2 (Framework & Integration)**:
- [ ] `get_all_client_skill_dirs()` includes plugin cache directories
- [ ] `_discover_skill_to_bundle_mapping()` reads SKILL.md frontmatter (not augur.yaml)
- [ ] `plugin_tools.py` discovers MCP tools from Claude plugin install dirs
- [ ] `get_skill_data_dir()` resolves vault paths for plugin-installed skills
- [ ] RAG indexer discovers and indexes content from plugin cache dirs
- [ ] RAG search returns results for plugin-installed skills
- [ ] Daemon plist generation uses `get_skill_root()` (no hardcoded paths)
- [ ] Daemon service starts successfully from plugin install location
- [ ] `mount-plugins` discovers dashboard/API resources from plugin install dirs
- [ ] Seed discovery scans plugin cache dirs for `assets/seeds/`
- [ ] Zero `Path(__file__)` patterns that navigate outside skill directory boundary
- [ ] `sync_agents --all` discovers masters in plugin cache and generates adapted copies
- [ ] Adapted copies in `.gemini/skills/`, `.codex/prompts/` not orphan-deleted when master is in plugin cache
- [ ] Freshness check detects stale adapted copies vs plugin-installed masters
- [ ] All ADR consumers (Browse, RAG, orphan-plans, doc-freshness) read from vault
- [ ] Browse ADR category shows all ADRs from vault
- [ ] Browse page shows `source` badge (plugin/local/global) per skill
- [ ] Browse page shows plugin name badge for plugin-installed skills
- [ ] Plugin name filter pills work in Browse toolbar
- [ ] Local skill (tier 2) overrides same-named plugin skill (tier 3) in Browse

**Phase 3 (Packaging)**:
- [ ] All 8 plugins pass `claude plugin validate`
- [ ] Marketplace installs cleanly on fresh profile

**Phase 4 (Integration)**:
- [ ] `/onboard` bootstraps complete system from zero prerequisites (except Python)
- [ ] `/onboard --migrate` handles existing users
- [ ] All skills produce same behavior from plugin as from `.claude/skills/`
- [ ] Personal/client skills continue working from `.claude/skills/`
- [ ] `npm run build` passes (if dashboard installed)
- [ ] All MCP tools respond via `augur mcp serve` (both local and plugin-installed skills)
- [ ] ADR status updated to Implemented

### Testing

| Test Case | Method | Expected Result |
|-----------|--------|-----------------|
| Fresh install (CLI only) | Install augur + system + knowledge, no dashboard | All slash commands work, MCP tools respond, no Node.js needed |
| Fresh install (full) | Install all 8 plugins | Dashboard runs, all pages render, all auto-commands execute |
| Existing user migration | Run /onboard --migrate on current repo | Plugins installed, personal skills preserved, no duplicates |
| Plugin isolation | Install only augur-career | Career skills work, no errors from missing system/knowledge skills (graceful "platform required" message) |
| Plugin update | Modify a skill, bump version, `claude plugin update` | Updated skill behavior visible immediately |
| Plugin disable/enable | `claude plugin disable augur-adaptive` | 44 auto-commands disappear from /commands, re-enable restores them |
| Dashboard optional | Install system + knowledge without dashboard | No Node.js errors, no dashboard references in skill output |
| MCP tool discovery | Install augur-career plugin, start MCP server | Career MCP tools (get-career-jobs, etc.) registered and responding |
| Dashboard mount | Install augur-career plugin, run mount-plugins | Career dashboard pages appear at /career/* |
| Python imports | Career MCP tools import src.config.paths | Imports resolve via PYTHONPATH set by MCP server |
| Cross-skill references | Skills that reference other skills by name | References resolve correctly via plugin discovery |
| Rollback | Uninstall all plugins, restore .claude/skills/ from git | System works exactly as before migration |
