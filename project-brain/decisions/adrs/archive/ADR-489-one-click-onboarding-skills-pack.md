---
status: Implemented
date: 2026-03-23
deciders:
  - Gur Sannikov
related:
  - ADR-437
  - ADR-438
  - ADR-488
hub: system
tags:
  - onboarding
  - skills-pack
  - portability
  - install
  - distribution
superseded_by: null
---

# ADR-489: One-Click Onboarding with Portable Skills Pack

## Context

ADR-437 and ADR-438 enabled multi-platform installation from Obsidian and IDEs, but AI agents (Claude Code, Codex, Gemini) had no install path. Users in these agents couldn't install Augur at all. Additionally, the full system install (clone repo, install deps, configure MCP) is heavyweight for users who just want to try Augur's skills.

The MiniMax skills repository demonstrated a pattern: distribute skills as a git-cloneable pack that works in any AI agent. But Augur's value is integration — standalone skills are the top of the funnel, full Augur is the product.

## Decision

### Install Matrix

Four entry points, two install modes:

| Group | Entry point | Mode |
|---|---|---|
| 0 | Terminal (`curl \| bash`) | Full system |
| 1 | Obsidian (plugin/prompt) | Full system |
| 2 | IDE (extension/prompt) | Full system |
| 3 | AI agent (copy-paste prompt) | Skills-only or full system (user chooses) |

### Universal Install Prompt

A single markdown file (`skills/onboard/install.md`) that works in any AI agent. The user copies it, pastes it into their agent session, and the agent:

1. Auto-detects the platform (9 supported: Claude Code, Codex, Gemini, Cursor, Windsurf, OpenCode, Cline, VS Code, Antigravity)
2. Shows a welcome message asking: skills-only or full system?
3. Installs accordingly

### Portable Skills Pack

Theme: "Give your AI agent a memory about you." Every skill in the pack stores persistent data about the user that the base agent cannot maintain across sessions.

Selected skills (all marked `x-augur-portable: true`):

| Skill | What it remembers |
|---|---|
| reading-list | Articles, notes, what's next |
| books | Book notes, ratings, progress |
| career | Applications, contacts, pipeline |
| interview-coach | STAR stories, prep sessions |
| content | Content calendar, drafts |
| health | Health tracking, medical notes |
| finance | Budget, investments, goals |
| augur-upgrade | Bridge to full system |

### Build System

`scripts/build_skills_pack.py` assembles the pack:

1. Scans `skills/*/SKILL.md` for `x-augur-portable: true`
2. Copies qualifying skills, strips `augur/` and `scripts/mcp/`
3. Strips `x-augur-dependencies` and `x-augur-requires-platform` from frontmatter
4. Appends upgrade footer using `x-augur-upgrade-hook`
5. Generates manifest

GitHub Actions (`.github/workflows/build-skills-pack.yml`) builds on release tags and pushes to `skills-pack` branch.

### Data Model

In standalone mode, skills read/write to their `assets/seeds/` directory (per ADR-488). On upgrade to full Augur, `install.sh` runs `migrate_seeds_to_vault()` to copy all user data into the vault.

### Upgrade Path

The `augur-upgrade` skill is included in every pack. When invoked, it detects the platform and runs `curl | bash --from <PLATFORM>` for the full system install.

## Consequences

### Positive

- Augur is installable from any AI agent via one copy-paste
- Users experience value immediately (persistent memory skills)
- Natural upgrade funnel — each skill shows what full Augur adds
- Single source of truth — pack is built from the same repo
- Decentralized curation — skills opt in via frontmatter flag

### Negative

- Pack is limited to skills that work without MCP (~8 currently)
- Seed data in `assets/seeds/` is a rule #4 exception (user data in code directory)
- Skills-pack branch requires force-push from CI (orphan branch pattern)

### Neutral

- Full system install paths (groups 0-2) are unchanged from ADR-437/438
- The pack grows automatically as more skills comply with ADR-488

## Alternatives Considered

### Alternative 1: Ship All Skills with Degraded Mode

Ship all 184 skills. MCP-dependent ones show "requires full Augur" when invoked.

Rejected because: 184 skills overwhelms the agent's skill index, and "this feature requires upgrade" repeated 114 times feels broken, not promotional.

### Alternative 2: Ship Skills + Headless MCP Server

Package a lightweight `augur-core` pip package with the MCP server but no dashboard.

Rejected because: significant engineering effort to extract MCP into standalone package, adds runtime dependency, and headless mode might work too well — removing the upgrade incentive.

### Alternative 3: Curated Pack of Utility Skills (No Memory Theme)

Ship standalone dev tools (git-guidelines, test-security, etc.) without a unifying theme.

Rejected because: most dev utility skills add no value over what the agent already does natively. The "memory" theme provides genuine value the base agent cannot offer.

## References

- Design spec: `docs/superpowers/specs/2026-03-23-one-click-onboarding-design.md`
- Implementation plan: `docs/superpowers/plans/2026-03-23-one-click-onboarding.md`
- ADR-437: Distribution Plugin Architecture
- ADR-438: Multi-Entry Onboarding
- ADR-488: Native File Ops for Skills
- MiniMax skills reference: https://github.com/MiniMax-AI/skills
- Agent Skills spec: https://agentskills.io/specification

## Impact Manifest

```yaml
impact:
  paths_renamed: []
  apis_changed:
    - "New x-augur-portable and x-augur-upgrade-hook frontmatter fields"
    - "New skills-pack branch (orphan, CI-managed)"
    - "install.sh gains migrate_seeds_to_vault() function"
  patterns_deprecated: []
  files_affected:
    - "scripts/build_skills_pack.py"
    - "scripts/install.sh"
    - ".github/workflows/build-skills-pack.yml"
    - "skills/onboard/install.md"
    - "skills/augur-upgrade/SKILL.md"
    - "skills/*/SKILL.md (7 portable skills)"
```
