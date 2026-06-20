---
status: Implemented
date: 2026-04-02
deciders:
  - gsannikov
related:
  - ADR-275
  - ADR-489
  - ADR-524
  - ADR-529
hub: command
tags:
  - import
  - skills
  - community
  - updates
superseded_by: null
---

# ADR-530: External Repo Install & Update

## Context

Community skill repos (like geo-seo-claude, 4,700+ stars) ship their own `install.sh` that copies skills into `~/.claude/skills/`. After installation, Augur's Tier 2 discovery finds the skills automatically — but Augur has no idea where they came from, what version is installed, or when updates are available. There's no `/import update` path, no source attribution in browse, and no way to track the 5-10 external repos a power user installs.

### Skill Ownership Tiers

| Tier | Source | Update mechanism | Install location |
|------|--------|-----------------|-----------------|
| 1. Platform | AI client (Claude, Codex, Gemini) | Client auto-updates | `~/.claude/skills/`, `~/.codex/prompts/` |
| 2. Community | GitHub repos | `/import update <name>` | `~/.claude/skills/` (via repo's installer) |
| 3. User-created | Born in Augur | User maintains | `skills/` (project-local) |

This ADR covers Tier 2.

### Design Principles

1. **Don't fight the repo's install model** — repos already know how to install themselves. Augur wraps and tracks, doesn't replace.
2. **No persistent clones** — temp clone, run installer, record metadata, delete clone. Same as repos' own model.
3. **No new discovery paths** — Tier 2 already scans `~/.claude/skills/`. No symlinks, no new platform dirs.
4. **Registry is the only addition** — everything else (discovery, RAG, sync, dashboard) already works.

## Decision

### Install Flow (repos with install.sh)

1. Temp clone (`git clone --depth 1` to temp dir)
2. Security scan (`scan_skill_security` on all `.py`/`.sh`/`.md` files)
3. Detect installer (install.sh, Makefile with install target, platform variants)
4. Snapshot `~/.claude/skills/` before install
5. Run installer non-interactively (`NONINTERACTIVE=1`, `CI=true`)
6. Snapshot after, diff to detect installed skills
7. Record in registry: source URL, commit hash, installer path, skills list
8. Delete temp clone, trigger RAG reindex

Repos without install.sh fall back to the existing `install-skill` copy pipeline.

### Update Flow

1. Look up registry entry by name
2. Check GitHub API for new commits (compare installed_commit vs latest)
3. Show changelog to user
4. Temp clone latest, re-run installer, update registry
5. Trigger RAG reindex

### New Backend Modules

| Module | File | Purpose |
|--------|------|---------|
| Installer detector | `skills/import/augur/lib/installer_detector.py` | Detect install.sh, Makefile, platform variants in cloned repos |
| Repo installer | `skills/import/augur/lib/repo_installer.py` | `clone_and_run_installer()` — clone, snapshot, run, diff, cleanup |
| Update checker | `skills/import/augur/lib/update_checker.py` | GitHub API update check with 5-min TTL cache |

### New MCP Tool

`update-repo` — check for updates or execute an update. Supports `check_only=True` for nightly polling.

### Registry Schema Extension

New fields on registry entries: `installed_commit`, `install_method` ("script"/"copy"), `installer_path`, `skills` (list of installed skill names), `install_location`, `latest_upstream_commit`, `update_available`. Passed as a single `repo_meta` dict to `add_entry()`.

### Browse Integration

"Community" badge on BrowseCard for skills matching a registry entry with `install_method: "script"` or `source: "external"`.

## Consequences

### Positive

- Community repos install with one command, tracked for updates
- No persistent clones to manage — same model repos already use
- Augur discovery already works (Tier 2 scans `~/.claude/skills/`)
- Version tracking enables update notifications
- Security scan runs before installer execution

### Negative

- Running install.sh from untrusted repos is inherently risky (v1 mitigated by security scan + showing script content, no sandbox)
- Update detection requires GitHub API calls (rate-limited at 60/hour unauthenticated)
- Browse "Community" badge requires enrichment cache to surface registry data (not yet wired — badge code is safe but won't render until enrichment integration)

### Neutral

- No changes to discovery scanner, RAG indexer, or sync_agents
- Repos without install.sh use existing copy pipeline unchanged
- The Add Skill Modal (ADR-529) already handles URL input — this extends the backend execution path

## Alternatives Considered

### Alternative 1: Persistent git clones in a repos directory

Full git clone kept permanently in `~/Projects/Au-repos/`. User runs `git pull` for updates, Augur overlays added as rebase commits.

Rejected: unnecessary complexity. Most repos design for disposable installs (curl | bash). Persistent clones add maintenance burden (rebase conflicts, 5-10 dirs to manage) without proportional benefit. The temp-clone model gives version tracking without persistent state.

### Alternative 2: Manifest-only (no clone, no local files)

Single YAML file tracks URLs. Augur fetches SKILL.md from GitHub API at index time. No local installation.

Rejected: can't run Python scripts from external repos, can't execute installers, only works for agent-native skills with no code dependencies.

### Alternative 3: Symlinks from skills/ into a repos dir

Clone repos externally, create symlinks in `skills/` pointing to clone dirs.

Rejected: fragile paths, `.gitignore` complexity, Augur's git would track symlinks, not portable across machines.

## Implementation Order

### Phase 1: Backend modules
1. Installer detector (`installer_detector.py` + 5 tests)
2. Repo installer with `clone_and_run_installer` helper (`repo_installer.py` + 7 tests)
3. Update checker with TTL cache (`update_checker.py` + 4 tests)

### Phase 2: Integration
4. Registry schema extension (`_registry.py` — `repo_meta` parameter)
5. Wire script-based install path into `install-skill` (`tools_install.py`)
6. Register `update-repo` MCP tool (`tools_install.py`)

### Phase 3: Frontend
7. Browse "Community" badge (`BrowseCard.tsx`)

## References

- Design spec: `docs/superpowers/specs/2026-04-02-external-repo-install-design.md`
- Implementation plan: `docs/superpowers/plans/2026-04-02-external-repo-install.md`
- ADR-529: Unified Add Skill Modal (URL install UI)
- ADR-275: Skill Import/Export Consolidation
- ADR-489: One-Click Onboarding with Portable Skills Pack
- ADR-524: Managed Skill Lifecycle

## Implementation Prompt

> Already implemented. See commit history from `cc13f478e` (installer detector) through latest simplify fixes.

**Team name**: `adr-530-external-repo-install`

### Phase 1: Backend
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | low | Installer detector + tests | `augur/lib/installer_detector.py` |
| 1.2 | developer | low | Repo installer + clone_and_run_installer + tests | `augur/lib/repo_installer.py` |
| 1.3 | developer | low | Update checker with TTL cache + tests | `augur/lib/update_checker.py` |

### Phase 2: Integration
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | medium | Registry extension + install-skill wiring | `_registry.py`, `tools_install.py` |
| 2.2 | developer | medium | update-repo MCP tool | `tools_install.py` |

### Phase 3: Frontend
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | developer | low | Browse Community badge | `BrowseCard.tsx` |

### Completion Criteria
- [x] All phases executed
- [x] All 16 new Python tests pass
- [x] Code review completed (reuse, quality, efficiency)
- [x] Duplicate logic extracted into shared helpers
- [x] Async blocking fixed (asyncio.to_thread)
- [x] GitHub API caching added (5-min TTL)
- [ ] Browse "Community" badge visible (pending enrichment cache integration)
- [x] ADR status updated to Implemented
