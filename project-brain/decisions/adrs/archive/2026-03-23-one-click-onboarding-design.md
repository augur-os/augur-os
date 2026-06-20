# One-Click Onboarding — Multi-Downstream Install Design

**Date:** 2026-03-23
**Status:** Draft
**Related:** ADR-437 (--from flag), ADR-438 (multi-entry onboarding), ADR-488 (native file ops for skills)

---

## Problem

Augur can only be installed by cloning the repo and running install.sh. Users coming from Obsidian, IDEs, or AI agents have no native install path from their platform. The onboarding skill needs to support one-click installation from any downstream.

## Design Principles

1. **One source of truth** — all install paths converge on the same repo and install.sh
2. **Skills pack as promotion** — standalone skills are the top of the funnel, full Augur is the product
3. **"Give your AI agent a memory"** — the skills pack theme; every skill persists data about the user that the base agent cannot
4. **No new infrastructure for standalone mode** — skills use the existing seed folder mechanism, no MCP server needed
5. **Upgrade preserves data** — everything the user created in standalone mode carries over to full Augur

## Install Matrix

| Group | Entry point | Mode | User action |
|---|---|---|---|
| 0 | Terminal | Full system | `curl -fsSL https://augur.run/install \| bash` |
| 1 | Obsidian | Full system | Community plugin button / paste prompt |
| 2 | IDE (VS Code, Cursor, Antigravity) | Full system | Extension marketplace / paste prompt |
| 3 | AI agent (Claude Code, Codex, Gemini, etc.) | Skills-only or Full system | Copy-paste universal install prompt |

Groups 0-2 always install the full system. Group 3 presents a choice.

## The Universal Install Prompt

A single markdown file (`dist/skills-pack/install.md`) that works in any AI agent. The user copies it, pastes it into their agent session, and the agent executes it.

### Step 1: Auto-detect platform

The prompt instructs the agent to detect its environment:

| Check | Platform |
|-------|----------|
| `~/.claude/` exists or agent is Claude Code | claude-code |
| `~/.codex/` exists or agent is Codex | codex |
| `~/.gemini/` exists or agent is Gemini CLI | gemini |
| `~/.cursor/` or `~/Library/Application Support/Cursor/` exists | cursor |
| `~/.codeium/windsurf/` exists | windsurf |
| `~/.opencode/` exists | opencode |
| `~/Library/Application Support/Cline/` exists | cline |
| Agent is running inside VS Code | vscode |
| Agent is running inside Antigravity | antigravity |

Fallback: ask the user which platform they're using.

### Step 2: Welcome message

```
Welcome to Augur — your AI-powered second brain.

How would you like to install?

1. Skills pack — a curated set of ready-to-use skills that make your
   agent smarter: dev workflows, coding best practices, interview prep,
   security audits. Works instantly, zero setup.

2. Full system — the complete Augur experience:
   - Your skills learn from each other and remember what you care about
   - A personal knowledge base that grows with you — searchable across
     everything you've ever saved
   - A visual dashboard for tracking career, finances, reading, health
   - Connects to Obsidian, Apple Notes, Google Workspace, and your IDE
   - Background agents that organize, improve, and maintain your system
     while you're away

   Setup takes ~3 minutes.

Pick 1 or 2:
```

### Step 3a: Skills pack (user picks 1)

1. Shallow clone: `git clone --depth 1 --branch skills-pack https://github.com/augur-os/augur-os /tmp/augur-install`
2. Copy skills to platform-specific directory:

| Platform | Target directory |
|----------|-----------------|
| claude-code | `~/.claude/skills/augur/` |
| codex | `~/.codex/augur/skills/` |
| gemini | `~/.gemini/augur/skills/` |
| cursor | `~/.cursor/augur/skills/` |
| windsurf | `~/.codeium/windsurf/augur/skills/` |
| opencode | `~/.config/opencode/skills/augur/` |
| cline | `~/.cline/augur/skills/` |
| vscode | `~/.vscode/augur/skills/` |
| antigravity | `~/.gemini/antigravity/augur/skills/` |

3. Platform-specific config if needed (codex: add to config.toml, opencode: add to config.json)
4. Clean up: `rm -rf /tmp/augur-install`
5. Confirmation message with example skills to try.

### Step 3b: Full system (user picks 2)

1. Run: `curl -fsSL https://raw.githubusercontent.com/augur-os/augur-os/main/scripts/install.sh | bash -s -- --from <PLATFORM>`
2. Confirmation message: restart session, run /commands.

## Skills Pack

### Theme: "Give your AI agent a memory about you"

Every skill in the pack stores persistent data about the user that the base agent cannot maintain across sessions. This is the value proposition no native agent provides, and the natural bridge to full Augur where all memories connect.

### Skill selection

| Skill | What it remembers about you | Refactor size | Notes |
|---|---|---|---|
| reading-list | Articles, notes, what's next | Small | No required deps |
| books | Book notes, ratings, progress | Small | No required deps; needs `_seed.yaml` created |
| career | Applications, contacts, pipeline | Medium | Has `knowledge` required dep — must degrade gracefully without it in standalone |
| interview-coach | STAR stories, prep sessions | Small | Has `knowledge` required dep — same treatment |
| content | Content calendar, drafts | Medium | Has `knowledge` required dep — same treatment |
| health | Health tracking, medical notes | Small | Has `knowledge` required dep — same treatment |
| finance | Budget, investments, goals | Small | Has `knowledge` required dep — same treatment |
| augur-upgrade | Upgrade to full system | N/A | — |

### Dependency handling in standalone mode

Five skills (career, interview-coach, content, health, finance) declare `knowledge` and/or `ai_bridge` as required dependencies. In standalone mode these deps are absent. The refactor must:

1. **Strip `x-augur-dependencies.required`** from the portable build output — the build script removes these fields
2. **Ensure SKILL.md instructions degrade gracefully** — features that need knowledge search (e.g., "search your notes for related content") should be gated with "If using full Augur..." conditionals, not assumed available
3. **Core skill functionality must work without deps** — career tracks applications via files, not via knowledge search. The search-across-skills feature is the upgrade hook.

### Platform flag handling

Some skills carry `x-augur-requires-platform: true`. This flag is legacy — it predates the portable skills concept. For portable pack candidates, this flag is stripped by the build script. The authoritative portability signal is `x-augur-portable: true`.

### Excluded by design

| Category | Why excluded |
|---|---|
| knowledge, search, rag | Need RAG/MCP to be genuinely useful — become upgrade hooks |
| auto-* maintenance skills | Internal Augur tooling |
| Integration skills (obsidian, apple, google-workspace) | Need full system — these are the upgrade pitch |
| Skills the agent already does natively | git-guidelines, shadcn-patterns, etc. — no added value |

### Upgrade moments

Each skill in the pack gets a footer appended by the build script:

```markdown
---
> This skill is part of [Augur](https://augur.run). With the full system,
> {contextual_upgrade_message}. Run `/augur-upgrade` to install.
```

The `x-augur-upgrade-hook` frontmatter field in each skill's SKILL.md provides the contextual message.

### The augur-upgrade skill

Included in every pack. When invoked:

1. Check if full Augur is already installed
2. Show value pitch (same as welcome message option 2)
3. Detect platform
4. Run `curl | bash --from <PLATFORM>`
5. Confirm: existing data in seeds folders is preserved

## Data Model — Standalone Mode

### How skills store data without MCP or vault

Skills already have a seed mechanism via `assets/seeds/` with a `_seed.yaml` manifest. The existing `SkillDataStore` reads from vault first, falls back to seeds.

**The only change for standalone mode:**

| Mode | Read from | Write to |
|---|---|---|
| Full Augur | Vault (seeds as fallback) | Vault |
| Standalone | `assets/seeds/` | `assets/seeds/` |

In standalone mode, seeds become the live working directory. No new folders, no new infrastructure.

**Note:** Writing user data into `assets/seeds/` is an intentional exception to CLAUDE.md rule #4 (data separation) for standalone mode only. The `x-augur-portable` flag serves as the discriminator — only portable skills in standalone mode write to seeds. In full Augur mode, all writes go to the vault as normal.

**`SkillDataStore` change:** one condition in `_resolve_data_dir()` — if no vault configured, return `self.assets_seed_dir` instead of `self.skill_path / "data"`.

### Upgrade migration

On upgrade to full Augur, `install.sh` copies everything from each skill's `assets/seeds/` into the vault. No filtering — the user likely modified the seeds, so copy all.

## Build System

### `scripts/build_skills_pack.py`

| Step | What it does |
|---|---|
| 1. Scan | Read all `skills/*/SKILL.md`, filter for `x-augur-portable: true` |
| 2. Copy | Copy qualifying skill directories into `dist/skills-pack/skills/` |
| 3. Strip | Remove `augur/` subdirectory (dashboard, tests, Augur-specific lib) and `scripts/mcp/` (server-side MCP tool registrations) — keep only portable dirs: `SKILL.md`, `commands/`, `references/`, `assets/`, `examples/` |
| 4. Append footer | Add upgrade message to each SKILL.md using `x-augur-upgrade-hook` |
| 5. Copy install prompt | Copy install.md into `dist/skills-pack/` |
| 6. Include augur-upgrade | Copy the upgrade skill into the pack |
| 7. Generate manifest | Write top-level SKILL.md for the pack (name: augur-skills) |

### Skill portability frontmatter

```yaml
x-augur-portable: true
x-augur-upgrade-hook: "your career pipeline connects to interview prep, calendar, and reminders"
```

Curation is decentralized — each skill declares its own portability. The build script just filters.

### CI/CD — GitHub Actions

`.github/workflows/build-skills-pack.yml` triggers on release tags:

1. Run `build_skills_pack.py`
2. Push result to `skills-pack` branch (clean, flat, no repo history)
3. Upload as release artifact

The install prompt clones from the `skills-pack` branch: `git clone --depth 1 --branch skills-pack`.

## Full System Entry Points (Groups 0-2)

### Group 0 — Standalone terminal

```bash
curl -fsSL https://augur.run/install | bash
```

No changes from current install.sh. `augur.run/install` redirects to raw install.sh.

### Group 1 — Obsidian

Two paths:
- **Community plugin (future):** Plugin's `onEnable()` calls `install.sh --from obsidian`, scaffolds vault connection
- **Prompt paste (now):** User pastes install prompt into any AI agent, prompt runs installer with `--from obsidian`

Existing plugin at `plugins/obsidian/` already has the integration hooks.

### Group 2 — IDEs

Two paths:
- **Extension marketplace (future):** Extension's `activate()` calls `install.sh --from <ide>`
- **Prompt paste (now):** Same universal install prompt, agent runs installer

Existing extensions at `plugins/vscode/` already have integration hooks.

### What `--from <platform>` controls

Already implemented in install.sh:

1. Records `install_source` in `onboard-complete.json`
2. Auto-configures MCP via `configure_mcp.py --client <platform>`
3. Platform-specific setup (Obsidian: scaffold vault)

## Related: ADR-488 — Native File Ops for Skills

A separate ADR (ADR-488) establishes the rule: **skills use the agent's native file tools for their own data, MCP only for cross-skill/service access.**

This is not a dependency for the skills pack — the 8 selected skills can be ported now with minimal effort. But as ADR-488 compliance spreads across the codebase, more skills naturally become portable and can be added to the pack via the `x-augur-portable` flag.

### The rule

| Operation | Use |
|---|---|
| Read/write skill's own data files | Agent's native Read/Write/Edit tools |
| Search within skill's own data | Agent's native Grep tool |
| List skill's own files | Agent's native Glob/LS tools |
| RAG-indexed search across all skills | MCP |
| Cross-skill data access | MCP |
| Background service queries (daemon, health) | MCP |
| Server-side AI execution | MCP |

## New Frontmatter Fields

| Field | Type | Purpose |
|---|---|---|
| `x-augur-portable` | boolean | Skill qualifies for the standalone skills pack |
| `x-augur-upgrade-hook` | string | Contextual upgrade message appended by build script |

## File Changes

### New files

| File | Purpose |
|---|---|
| `scripts/build_skills_pack.py` | Build script — assembles portable skills into dist/ |
| `.github/workflows/build-skills-pack.yml` | CI — builds pack on release tags, pushes to skills-pack branch |
| `dist/skills-pack/install.md` | Universal install prompt for AI agents |
| `skills/augur-upgrade/SKILL.md` | Upgrade skill included in every pack |
| `skills/augur-upgrade/assets/seeds/_seed.yaml` | Minimal seed manifest |

### Modified files

| File | Change |
|---|---|
| `skills/reading-list/SKILL.md` | Add `x-augur-portable`, `x-augur-upgrade-hook` |
| `skills/books/SKILL.md` | Add `x-augur-portable`, `x-augur-upgrade-hook` |
| `skills/career/SKILL.md` | Add `x-augur-portable`, `x-augur-upgrade-hook` |
| `skills/interview-coach/SKILL.md` | Add `x-augur-portable`, `x-augur-upgrade-hook` |
| `skills/content/SKILL.md` | Add `x-augur-portable`, `x-augur-upgrade-hook` |
| `skills/health/SKILL.md` | Add `x-augur-portable`, `x-augur-upgrade-hook` |
| `skills/finance/SKILL.md` | Add `x-augur-portable`, `x-augur-upgrade-hook` |
| `src/mcp/plugin_utils.py` | `SkillDataStore._resolve_data_dir()` — return seeds dir when no vault configured |
| `skills/onboard/SKILL.md` | Reference install prompt, add upgrade migration step |
| `scripts/install.sh` | Add seed-to-vault migration during upgrade |
