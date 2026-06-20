---
status: Implemented
date: '2026-02-06'
deciders:
- Augur Team
related:
- ADR-006 (Local-First Architecture)
- ADR-020 (Plugin Bundle Architecture)
- ADR-045 (Launch Plan & Go-To-Market)
hub: null
tags:
- multi
- user
- scale
- support
- distribution
superseded_by: null
---

# ADR-048: Multi-User Scale Support — Distribution, Branching & Update Strategy

## Context

Augur is a private monorepo on GitHub, currently developed and used by a single user. ADR-045 targets a public launch at `v0.1.0` with realistic month-1 adoption of ~50 users, scaling to hundreds by month 3-6.

Each user will:
1. **Receive updates** — core framework improvements, new plugins, bug fixes, security patches
2. **Customize data structures** — modify YAML files in `data/` to fit their life (goals, habits, career data)
3. **Create custom plugins** — build personal skills in `plugins/` that don't exist upstream
4. **Modify existing plugins** — tweak upstream plugin behavior, dashboards, chains

This creates a classic **upstream divergence problem**: how do 50+ users stay on the latest Augur while preserving their personal customizations? Without a deliberate strategy, users either stop updating (and fall behind on fixes/features) or lose customizations on every update.

### Current State

| Aspect | Today | Problem at 50 Users |
|--------|-------|---------------------|
| Distribution | Single private repo | Need access control + fork workflow |
| Updates | `git pull` on main | Conflicts with user modifications |
| Versioning | No tags, no releases | Users don't know what changed or when |
| Data schemas | Implicit contracts | Upstream schema changes break user data |
| Custom plugins | Don't exist yet | No convention for where they live |
| Migrations | None | Data structure changes require manual fixes |

### Industry Precedents

| Project | Model | Lesson for Augur |
|---------|-------|------------------|
| Home Assistant + HACS | Core releases (CalVer) + community plugin registry | Plugin isolation via `custom_components/` directory |
| Obsidian | Plugin registry (`community-plugins.json`) + per-vault config | Registry model for discoverability |
| LazyVim | Curated Neovim distro, users fork and customize | Fork-and-merge is viable for <500 power users |
| WordPress | Core auto-updates, plugins via marketplace | Never touch `wp-content/` — filesystem separation |
| Backstage (Spotify) | Core framework + org-specific plugins | Same plugin contract for core and custom |

## Decision

### 1. Distribution Model: Fork-Based with Upstream Sync

**Users fork the repo, not clone it.** This gives each user their own Git history while maintaining the ability to pull upstream changes.

```
augur-project/augur (upstream)     ← Core team pushes releases here
    ↓ fork
user1/augur (fork)                 ← User's personal copy
    ↓ local clone
~/Projects/Augur                   ← User's working installation
```

**Access control via GitHub Organization:**

```
GitHub Org: augur-project
├── Team: augur-users      → Read access (fork + pull)
├── Team: augur-core       → Write access (push to upstream)
└── Repo: augur (private at launch, public later per ADR-045)
```

When the repo goes public (per ADR-045), forking becomes unrestricted. Pre-public: invite users to the org with read access.

### 2. Versioning: Semantic Versioning with Conventional Commits

**Format**: `vMAJOR.MINOR.PATCH` (e.g., `v0.1.0`, `v0.2.0`, `v1.0.0`)

| Version Bump | When | Example |
|-------------|------|---------|
| PATCH (`v0.1.1`) | Bug fixes, docs, no schema changes | Fix broken chain execution |
| MINOR (`v0.2.0`) | New features, new plugins, backward-compatible schema additions | Add `wearables` plugin, add optional field to career data |
| MAJOR (`v1.0.0`) | Breaking changes, required schema migrations, removed features | Restructure `data/` layout, rename plugin bundle |

**Every release gets:**
- A Git tag (`v0.2.0`)
- A GitHub Release with auto-generated changelog (from conventional commits)
- Migration notes if MINOR/MAJOR (which files changed, what to run)
- A `CHANGELOG.md` entry

**Tooling**: Use [Release-Please](https://github.com/googleapis/release-please-action) GitHub Action to automate release creation from conventional commit messages. The project already uses conventional commits (`feat:`, `fix:`, `refactor:`, etc.).

### 3. Branching Strategy: Trunk-Based with Release Branches

```
main                           ← Active development (next release)
  │
  ├── release/0.1.x            ← Hotfix-only branch for v0.1.x users
  ├── release/0.2.x            ← Hotfix-only branch after v0.2.0 ships
  │
  ├── feat/some-feature        ← Short-lived feature branches (merged to main)
  └── fix/some-bug             ← Short-lived fix branches (merged to main)
```

**Rules:**
- `main` is always the next release. Never broken (CI enforces).
- `release/X.Y.x` branches are created when tagging `vX.Y.0`. Only hotfixes (cherry-picks from main) land here.
- Feature branches are short-lived (<1 week), merged via PR to `main`.
- No long-lived development branches.

**LTS policy (post-v1.0.0):** Once we have enough users to warrant it, the last minor of each major version gets 6 months of security patches. Not needed at 50 users.

### 4. Filesystem Isolation: Core vs. Custom

**The fundamental principle**: upstream and user content live in clearly separated directories. Upstream never writes to user directories; users never need to edit upstream directories.

```
plugins/
├── core/           # UPSTREAM-OWNED — auto-updated
├── services/       # UPSTREAM-OWNED — auto-updated
├── apps/           # UPSTREAM-OWNED — auto-updated
├── orchestrator/   # UPSTREAM-OWNED — auto-updated
└── custom/         # USER-OWNED — gitignored from upstream
    └── skills/
        └── my-skill/
            ├── SKILL.md
            ├── dashboard.yaml
            ├── dashboard/
            ├── scripts/
            └── chains/

data/
├── defaults/       # UPSTREAM-OWNED — default YAML templates (new)
│   ├── apps/
│   ├── services/
│   └── core/
├── core/           # USER-OWNED — initialized from defaults/
├── services/       # USER-OWNED — user's actual data
├── apps/           # USER-OWNED — user's actual data
└── custom/         # USER-OWNED — data for custom plugins
```

**Key changes from today:**

| Change | Rationale |
|--------|-----------|
| Add `plugins/custom/` directory | Designated home for user-created plugins |
| Add `data/defaults/` directory | Upstream-owned YAML templates, never edited by users |
| Add `plugins/custom/` to upstream `.gitignore` | Upstream never sees user plugins |
| Add `data/custom/` to upstream `.gitignore` | Upstream never sees custom plugin data |
| `.gitattributes` merge driver for `data/` | Protects user data during upstream merges |

**`.gitattributes` (new):**
```gitattributes
# User data files: always keep user's version during merges
data/core/**/*.yaml merge=ours
data/services/**/*.yaml merge=ours
plugins/**/*.yaml merge=ours
data/core/**/*.md merge=ours

# User memory: never overwritten
data/core/memory/** merge=ours
```

**Custom plugin contract**: plugins in `plugins/custom/` follow the exact same `SKILL.md` + `dashboard.yaml` contract as upstream plugins. The plugin loader discovers them automatically. No registration step needed — convention over configuration.

### 5. Schema Versioning & Data Migrations

**Every YAML data file gets a `schema_version` field:**

```yaml
# plugins/career/goals.yaml
schema_version: 1
goals:
  - title: "Ship Augur v0.1.0"
    priority: critical
    deadline: 2026-03-01
```

**Migration scripts follow the Flyway-style sequential pattern:**

```
src/scripts/migrations/
├── __init__.py
├── runner.py                    # Migration runner
├── V001__initial_schema.py      # Baseline (schema_version: 1)
├── V002__add_health_metrics.py  # Add new fields to health data
├── V003__career_restructure.py  # Restructure career YAML
└── V004__rename_lifestyle.py    # Rename keys in lifestyle data
```

**Each migration script:**
```python
# src/scripts/migrations/V002__add_health_metrics.py

VERSION = 2
DESCRIPTION = "Add metrics tracking to health data"
AFFECTS = ["plugins/health/config.yaml"]

def upgrade(data_dir: Path):
    """Add default metrics fields to health config."""
    health_config = data_dir / "apps" / "health" / "config.yaml"
    if not health_config.exists():
        return  # User doesn't use this plugin

    data = yaml.safe_load(health_config.read_text())
    if data.get("schema_version", 1) >= VERSION:
        return  # Already migrated

    # Add new fields with sensible defaults
    data.setdefault("metrics", {"track_sleep": True, "track_steps": True})
    data["schema_version"] = VERSION

    health_config.write_text(yaml.dump(data, default_flow_style=False))

def downgrade(data_dir: Path):
    """Remove metrics fields (rollback)."""
    # ...
```

**Migration runner behavior:**
1. On `npm run dev`, `npm run build`, or explicit `python3 src/scripts/migrate.py`
2. Reads `runtime/migration_history.yaml` for previously applied migrations
3. Discovers unapplied migrations, runs them sequentially
4. Creates automatic backup: `runtime/backups/pre-migration-V002-{timestamp}/`
5. Records each migration in history
6. Logs everything to `runtime/logs/migrations.log`

**Rules:**
- Migrations are **additive only** for PATCH/MINOR versions (new optional fields, never remove/rename)
- MAJOR versions may include **breaking migrations** (renames, restructures) — documented in release notes
- Migrations are **idempotent** — safe to run multiple times
- Migrations **never delete user data** — only restructure or add defaults
- Migration history file is **user-owned** (gitignored from upstream, created locally)

### 6. User Update Workflow

**For typical users (no custom plugins, just data customizations):**

```bash
# Option A: Manual (recommended for month 1)
git fetch upstream
git merge upstream/main --no-edit
python3 src/scripts/migrate.py
npm run build  # in src/dashboard/

# Option B: One-command update script (shipped with Augur)
python3 src/scripts/augur_update.py
```

**The `augur_update.py` script:**
1. Stashes any uncommitted changes
2. Fetches upstream
3. Attempts merge (using `.gitattributes` to protect `data/`)
4. If conflict: reports conflicting files and exits with instructions
5. If clean merge: runs migrations, rebuilds dashboard
6. Unstashes user changes
7. Prints summary: "Updated from v0.1.3 → v0.2.0. 2 migrations applied."

**For advanced users (custom plugins, modified upstream code):**

```bash
# They maintain a personal branch
git checkout my-customizations
git rebase upstream/main
# Resolve any conflicts in their modified upstream files
python3 src/scripts/migrate.py
```

### 7. GitHub Actions for Automated Sync (User-Side)

Ship a workflow file that users can enable in their forks:

```yaml
# .github/workflows/sync-upstream.yml
name: Sync Upstream
on:
  schedule:
    - cron: '0 6 * * 1'  # Weekly Monday 6am
  workflow_dispatch:       # Manual trigger

jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Configure upstream
        run: |
          git remote add upstream https://github.com/augur-project/augur.git || true
          git fetch upstream

      - name: Attempt merge
        run: git merge upstream/main --no-edit

      - name: Run migrations
        run: python3 src/scripts/migrate.py

      - name: Create PR with changes
        uses: peter-evans/create-pull-request@v6
        with:
          title: "chore: sync upstream $(git describe --tags upstream/main)"
          body: |
            Automated sync from upstream Augur.
            Review changes before merging into your fork.
          branch: auto-sync-upstream
```

This creates a PR in the user's fork — they review changes before accepting. No silent overwrites.

### 8. Dashboard Update Notification

Add a lightweight version check to the dashboard:

```typescript
// plugins/observability/skills/daemon/dashboard/components/UpdateBanner.tsx
// Checks GitHub API for latest release tag, compares with local VERSION file
// Shows banner: "Augur v0.3.0 available. You're on v0.2.1. Run `augur update` to upgrade."
```

- Polls GitHub Releases API once per day (cached in `runtime/`)
- Non-intrusive banner in dashboard (dismissible)
- Links to release notes and migration guide
- No auto-update — user controls when to upgrade

### 9. Data Initialization for New Users

**First-time setup** (`python3 src/scripts/augur_init.py` or part of onboarding):

1. Copy `data/defaults/` → `data/` (only files that don't already exist)
2. Set `schema_version` in all YAML files to current latest
3. Create `plugins/custom/` with README explaining the convention
4. Create `data/custom/` for custom plugin data
5. Initialize `runtime/migration_history.yaml`
6. Print: "Augur initialized. Run `npm run dev` in src/dashboard/ to start."

**Existing users upgrading from pre-ADR-048**: A one-time bootstrap migration detects missing `schema_version` fields and adds them at version 1, then runs all subsequent migrations.

### 10. Release Process (Core Team)

```
1. Development on main (conventional commits)
2. When ready to release:
   a. Release-Please creates a release PR (bumps version, generates CHANGELOG)
   b. PR includes migration scripts for any data changes
   c. Review and merge the release PR
   d. Release-Please creates Git tag + GitHub Release
   e. Create release/X.Y.x branch from the tag
3. Post-release:
   a. Announce in GitHub Discussions / Discord
   b. Dashboard update notification propagates to users within 24h
```

### 11. Updater Service Plugin — Dashboard & MCP Integration

The entire update lifecycle (check, review, apply, migrate, rollback) is exposed as a **first-class service plugin** at `plugins/admin/skills/updater/`. Users manage updates through the same dashboard + MCP command flow they use for everything else in Augur — no terminal required.

#### Plugin Structure

```
plugins/admin/skills/updater/
├── SKILL.md                         # Plugin documentation (<100 lines)
├── dashboard.yaml                   # Hub definition, tabs, actions, modals
├── dashboard/
│   ├── layout.tsx                   # Hub layout wrapper
│   ├── page.tsx                     # Overview tab (update status at a glance)
│   ├── releases/
│   │   └── page.tsx                 # Release history tab (changelog browser)
│   ├── migrations/
│   │   └── page.tsx                 # Migration status tab
│   ├── plugins/
│   │   └── page.tsx                 # Custom plugins tab (manage user plugins)
│   └── components/
│       ├── UpdateStatusCard.tsx      # Current vs latest version, status indicator
│       ├── ChangelogViewer.tsx       # Rendered release notes from GitHub API
│       ├── MigrationTimeline.tsx     # Visual migration history + pending
│       ├── ConflictResolver.tsx      # Show merge conflicts with resolution UI
│       ├── PluginCard.tsx            # Custom plugin status card
│       └── BackupManager.tsx         # List/restore data backups
├── api/
│   ├── status/route.ts              # GET — current version, latest available, drift status
│   ├── check/route.ts               # POST — fetch latest release from GitHub API
│   ├── update/route.ts              # POST — execute git fetch + merge + migrate
│   ├── migrate/route.ts             # POST — run pending migrations only
│   ├── rollback/route.ts            # POST — restore from pre-update backup
│   ├── releases/route.ts            # GET — list releases from GitHub API (cached)
│   ├── conflicts/route.ts           # GET — list current merge conflicts
│   ├── plugins/route.ts             # GET — list custom plugins + their status
│   └── backup/route.ts              # GET/POST — list backups / create manual backup
├── scripts/
│   ├── updater_service.py           # Core update logic (wraps augur_update.py)
│   ├── version_checker.py           # Polls GitHub Releases API, caches result
│   ├── conflict_analyzer.py         # Parses git merge conflicts, suggests resolutions
│   └── plugin_scanner.py            # Discovers and validates plugins/custom/ skills
├── mcp/
│   └── __init__.py                  # MCP tool definitions (see below)
├── chains/
│   └── full_update.yaml             # Chain: check → backup → update → migrate → verify
└── tests/
    ├── test_updater_service.py
    ├── test_version_checker.py
    └── test_migrations.py
```

#### dashboard.yaml

```yaml
version: "2.0"

hub:
  id: updater
  title: System Updates
  subtitle: Manage Augur versions, migrations, and custom plugins
  icon: RefreshCw
  category: system
  iconBg: "bg-blue-500/20"
  iconColor: "text-blue-400"

data_dir: updater

tab_groups:
  - id: status
    label: Status
  - id: management
    label: Management

tabs:
  - id: overview
    label: Overview
    icon: LayoutDashboard
    group: status
    default: true

  - id: releases
    label: Releases
    icon: Tag
    group: status
    href: /updater/releases

  - id: migrations
    label: Migrations
    icon: Database
    group: management
    href: /updater/migrations

  - id: plugins
    label: Custom Plugins
    icon: Puzzle
    group: management
    href: /updater/plugins

modals:
  confirm-update:
    title: "Apply Update"
    description: "Review changes before updating"
    submitTool: mcp://augur/updater-apply
    submitLabel: "Update Now"
    fields:
      - name: target_version
        label: "Target Version"
        type: text
        required: true
      - name: auto_migrate
        label: "Run migrations automatically"
        type: checkbox
        default: true
      - name: create_backup
        label: "Create backup before update"
        type: checkbox
        default: true

  rollback:
    title: "Rollback Update"
    description: "Restore from a previous backup"
    submitTool: mcp://augur/updater-rollback
    submitLabel: "Rollback"
    fields:
      - name: backup_id
        label: "Backup to restore"
        type: select
        required: true

actions:
  - id: check-updates
    label: "Check for Updates"
    description: "Query GitHub for the latest Augur release"
    icon: "Search"
    flow: fast
    tool: mcp://augur/updater-check

  - id: apply-update
    label: "Update Augur"
    description: "Fetch upstream changes, merge, and run migrations"
    icon: "Download"
    type: modal
    modal: confirm-update

  - id: run-migrations
    label: "Run Migrations"
    description: "Apply pending data migrations without updating code"
    icon: "Database"
    flow: fast
    tool: mcp://augur/updater-migrate

  - id: create-backup
    label: "Backup Data"
    description: "Create a manual backup of your data/ directory"
    icon: "Save"
    flow: fast
    tool: mcp://augur/updater-backup

  - id: rollback
    label: "Rollback"
    description: "Restore data from a previous backup"
    icon: "RotateCcw"
    type: modal
    modal: rollback

  - id: diagnose-conflicts
    label: "Diagnose Conflicts"
    description: "AI analyzes merge conflicts and suggests resolutions"
    icon: "Stethoscope"
    flow: llm
    mode: ide
```

#### MCP Tools

The updater exposes MCP commands so users (and AI agents) can manage updates from the IDE chat or any MCP client:

| MCP Tool | Description | Flow |
|----------|-------------|------|
| `updater-check` | Check GitHub for latest release, return version comparison | Read-only |
| `updater-status` | Return current version, pending migrations, custom plugin count, last update time | Read-only |
| `updater-apply` | Execute full update cycle (backup → fetch → merge → migrate → rebuild) | Write — requires confirmation |
| `updater-migrate` | Run pending data migrations only (no git operations) | Write |
| `updater-rollback` | Restore data/ from a named backup | Write — requires confirmation |
| `updater-backup` | Create a named backup of data/ directory | Write |
| `updater-releases` | List recent releases with changelogs | Read-only |
| `updater-conflicts` | List current merge conflicts with file paths and context | Read-only |
| `updater-plugins` | List custom plugins with validation status | Read-only |
| `updater-diff` | Show what would change if update is applied (dry-run) | Read-only |

**Example MCP interactions:**

```
User: "Is my Augur up to date?"
→ Agent calls updater-status
→ Returns: "You're on v0.2.1. Latest is v0.3.0. 2 migrations pending."

User: "What's new in the latest release?"
→ Agent calls updater-releases
→ Returns: changelog for v0.3.0 (new plugins, bug fixes, migration notes)

User: "Show me what would change if I update"
→ Agent calls updater-diff
→ Returns: list of changed files, new migrations, potential conflicts

User: "Update my Augur"
→ Agent calls updater-apply with create_backup=true, auto_migrate=true
→ Executes: backup → git fetch → git merge → migrate → npm run build
→ Returns: "Updated v0.2.1 → v0.3.0. Backup created at backups/pre-update-v030-1707234567. 2 migrations applied successfully."

User: "Something broke, roll back"
→ Agent calls updater-rollback with backup_id="pre-update-v030-1707234567"
→ Restores data/ from backup, reverts git merge
→ Returns: "Rolled back to pre-update state. You're back on v0.2.1."
```

#### Dashboard Tabs Detail

**Overview Tab** (`page.tsx`):
- **UpdateStatusCard** — large card showing: current version, latest version, status badge (up-to-date / update available / update in progress / conflict detected)
- **Quick Stats Row** — 4 stat cards: pending migrations, custom plugins installed, last update date, data backup count
- **Recent Activity** — timeline of last 5 update/migration events from `plugins/admin/skills/updater/data/history.yaml`
- **Action buttons** — Check for Updates, Update Now, Backup Data (rendered from dashboard.yaml actions)

**Releases Tab** (`releases/page.tsx`):
- **ChangelogViewer** — fetches releases from GitHub API (cached 24h in `runtime/cache/releases.json`)
- Each release rendered as a card: version tag, date, changelog (markdown rendered), "currently installed" badge on active version
- Filter: all releases, breaking changes only, since my version
- Link to full release notes on GitHub

**Migrations Tab** (`migrations/page.tsx`):
- **MigrationTimeline** — vertical timeline showing: applied migrations (green), pending migrations (amber), failed migrations (red)
- Each migration shows: version number, description, affected files, timestamp applied
- **Run Pending** button — triggers `POST /api/updater/migrate`
- **Dry Run** button — shows what migrations would do without applying
- **BackupManager** — list of data backups with restore buttons, backup size, timestamp

**Custom Plugins Tab** (`plugins/page.tsx`):
- **PluginCard** grid — each card shows: plugin name (from SKILL.md), status (valid / missing fields / error), last modified date
- Validation checks: has SKILL.md, has dashboard.yaml, follows naming convention, no conflicts with upstream plugin IDs
- **Health indicators**: schema version alignment, API route conflicts, dashboard mount status
- Link to plugin development guide

#### Data Storage

```yaml
# plugins/admin/skills/updater/config.yaml
schema_version: 1
check_interval: daily          # daily | weekly | manual
auto_backup: true              # Create backup before every update
notify_in_dashboard: true      # Show update banner
github_repo: augur-project/augur  # Upstream repo for API checks

# plugins/admin/skills/updater/data/history.yaml
schema_version: 1
events:
  - type: update
    from_version: v0.1.0
    to_version: v0.2.0
    timestamp: 2026-03-15T10:30:00Z
    migrations_applied: [V001, V002]
    status: success

  - type: migration
    version: V003
    timestamp: 2026-03-20T14:15:00Z
    status: success
    affected_files: [plugins/career/goals.yaml]

  - type: rollback
    to_backup: pre-update-v020-1710498600
    timestamp: 2026-03-15T11:00:00Z
    reason: "Dashboard build failed after update"

# plugins/admin/skills/updater/data/state.yaml (runtime state, lives in runtime/)
current_version: v0.2.0
latest_checked: v0.3.0
last_check: 2026-03-25T06:00:00Z
pending_migrations: [V004, V005]
active_conflicts: []
backups:
  - id: pre-update-v020-1710498600
    path: runtime/backups/pre-update-v020-1710498600/
    size_mb: 12.4
    created: 2026-03-15T10:29:00Z
```

#### Integration with Existing Systems

| System | Integration |
|--------|------------|
| **Daemon (ADR-041)** | Daemon's scheduled tasks run `version_checker.py` daily. Results cached in `plugins/admin/skills/updater/data/state.yaml`. |
| **Channels (notifications)** | Update available → `raise_review("update_available", ...)` → notification card in channels |
| **FloatingChat** | MCP tools appear in IDE chat. User says "update augur" → agent runs `updater-apply` |
| **Plugin loader** | `plugin_scanner.py` validates `plugins/custom/` skills, reports issues in Custom Plugins tab |
| **Migration runner** | `src/scripts/migrations/runner.py` is called by updater API routes, not duplicated |
| **augur_update.py** | `updater_service.py` wraps the existing CLI script, adding event logging and error handling |

## Implementation Phases

### Phase 1: Foundation (Pre-Launch, Week 1-2)

| Task | Files | Status |
|------|-------|--------|
| Create `plugins/custom/` with README + `.gitkeep` | `plugins/custom/README.md` | DONE |
| Create `data/custom/` with README | `data/custom/README.md` | DONE |
| Add `.gitattributes` with merge drivers | `.gitattributes` | DONE |
| Update `.gitignore` for custom dirs + updater mount paths | `.gitignore` | DONE |
| Add `VERSION` file at repo root | `VERSION` | DONE |
| Create `data/defaults/` with current YAML templates | `data/defaults/**/*.yaml` | DONE |
| Create migration runner | `src/scripts/migrations/runner.py` | DONE |
| Create `augur_update.py` script | `src/scripts/augur_update.py` | DONE |
| Create `augur_init.py` script | `src/scripts/augur_init.py` | DONE |
| Add `schema_version` to all existing YAML data files | `data/**/*.yaml` | DONE |
| Write V001 baseline migration | `src/scripts/migrations/V001__baseline.py` | DONE |

### Phase 2: Automation (Launch Week)

| Task | Files |
|------|-------|
| Set up Release-Please GitHub Action | `.github/workflows/release.yml` |
| Ship user-side sync workflow | `.github/workflows/sync-upstream.yml` |
| Tag `v0.1.0` with GitHub Release | Git tag |
| Write migration guide in README | `README.md` |

### Phase 3: Updater Plugin — Core (Month 1, Week 1-2)

| Task | Files |
|------|-------|
| Create updater SKILL.md | `plugins/admin/skills/updater/SKILL.md` |
| Create dashboard.yaml with hub, tabs, actions | `plugins/admin/skills/updater/augur.yaml` |
| Build `version_checker.py` (GitHub API polling + cache) | `plugins/admin/skills/updater/scripts/version_checker.py` |
| Build `updater_service.py` (wraps augur_update.py) | `plugins/admin/skills/updater/scripts/updater_service.py` |
| Build API routes: `/api/updater/status`, `/check`, `/releases` | `plugins/admin/skills/updater/api/` |
| Create Overview tab with UpdateStatusCard + stats | `plugins/admin/skills/updater/augur/page.tsx` |
| Register MCP tools: `updater-check`, `updater-status`, `updater-releases` | `plugins/admin/skills/updater/mcp/__init__.py` |
| Create data directory + config/state YAML | `plugins/admin/skills/updater/data/` |

### Phase 4: Updater Plugin — Full (Month 1, Week 3-4)

| Task | Files |
|------|-------|
| Build API routes: `/update`, `/migrate`, `/rollback`, `/backup` | `plugins/admin/skills/updater/api/` |
| Register write MCP tools: `updater-apply`, `updater-migrate`, `updater-rollback` | `plugins/admin/skills/updater/mcp/__init__.py` |
| Build Releases tab with ChangelogViewer | `plugins/admin/skills/updater/augur/releases/page.tsx` |
| Build Migrations tab with MigrationTimeline | `plugins/admin/skills/updater/augur/migrations/page.tsx` |
| Build Custom Plugins tab with PluginCard grid | `plugins/admin/skills/updater/augur/plugins/page.tsx` |
| Build `conflict_analyzer.py` (parse conflicts, suggest fixes) | `plugins/admin/skills/updater/scripts/conflict_analyzer.py` |
| Build `plugin_scanner.py` (validate custom plugins) | `plugins/admin/skills/updater/scripts/plugin_scanner.py` |
| Create `full_update` chain (check → backup → update → migrate → verify) | `plugins/admin/skills/updater/chains/full_update.yaml` |
| Integrate with daemon scheduled tasks (daily version check) | `plugins/observability/skills/daemon/config/tasks.yaml` |
| Integrate with channels (update notification review card) | `plugins/admin/skills/channels/` |
| Add confirm-update and rollback modals | `plugins/admin/skills/updater/augur.yaml` |
| Build BackupManager component | `plugins/admin/skills/updater/augur/components/BackupManager.tsx` |
| Write tests | `plugins/admin/skills/updater/tests/` |

### Phase 5: Scale (Month 3-6, if >100 users)

| Task | Description |
|------|-------------|
| Community plugin registry | `community-plugins.yaml` — Obsidian-style, linking to external repos |
| Plugin marketplace in dashboard | Browse, install, update third-party plugins from the Updater UI |
| LTS release branches | `release/1.x` maintained for 6 months after `2.0` ships |
| Automated migration testing | CI runs all migrations against fixture YAML data |
| Updater-diff tool | Preview exact file changes before applying an update |
| Auto-update mode | Opt-in: daemon applies PATCH updates automatically (with backup) |

## Consequences

### Positive

- Users can customize freely without fear of losing work on update
- Clear separation of "upstream code" and "user space" prevents accidental conflicts
- Schema versioning catches data drift early instead of mysterious runtime failures
- Fork-based model is familiar to developers and requires zero custom infrastructure
- Migration scripts provide a tested, repeatable upgrade path
- GitHub Actions handle sync automation — no custom server needed
- `data/defaults/` gives new users a working starting point immediately
- Custom plugin directory gives users a sanctioned place to build without forking core
- **Updater plugin gives non-terminal users a GUI for the entire update lifecycle** — check, review, apply, rollback
- **MCP tools enable AI-assisted updates** — "update my augur" in chat triggers the full workflow
- **Update history is tracked** — users can audit what changed when, and rollback to any previous state
- **Custom plugin health is visible** — validation catches issues before they cause runtime failures

### Negative

- Fork-based model requires Git literacy — non-technical users may struggle (mitigated by updater dashboard)
- `.gitattributes` merge driver (`ours`) can silently discard upstream data template improvements — users must manually adopt new default fields
- Migration scripts are one more thing to maintain — every data schema change requires a migration
- 50 private forks increase GitHub API pressure (rate limits on sync workflows)
- No real-time update push — users must actively pull or rely on weekly sync Action
- **Updater plugin adds a new service to maintain** — API routes, MCP tools, dashboard components
- **Git operations from a web UI can fail in unexpected ways** — merge conflicts need careful error handling and clear user messaging

### Neutral

- Local-first architecture (ADR-006) is fully preserved — no cloud dependency for updates
- Commercial licensing (docs/COMMERCIAL.md) is unaffected — forks inherit the same license
- Plugin contract (SKILL.md + dashboard.yaml) stays identical for core and custom plugins
- Existing CI/CD scripts continue to work — this ADR adds to, not replaces, current infrastructure
- Updater plugin follows the exact same architecture as daemon, channels, and other services — no special patterns

## Alternatives Considered

### Alternative 1: Git Submodules for Plugins

Split each plugin bundle into its own Git repo. Users add them as submodules.

**Rejected because:**
- Submodules are notoriously painful for non-expert Git users
- Adds significant complexity to the development workflow (cross-repo PRs, version pinning)
- At 50 users, the operational overhead outweighs the isolation benefit
- Monorepo with directory separation achieves the same isolation with less friction

**Revisit when:** Plugin ecosystem grows beyond what a single repo can hold (>100 plugins, multiple maintainers).

### Alternative 2: Template Repository (GitHub Templates)

Create Augur as a template repo. Users click "Use this template" to get their own copy.

**Rejected because:**
- Template repos create a **disconnected copy** — no upstream link, no `git fetch upstream`
- Users cannot pull updates without manually adding the remote and resolving full-repo diffs
- Fundamentally incompatible with the "stay updated" requirement

### Alternative 3: Package Manager Distribution (npm/pip)

Publish Augur core as an npm/pip package. Users install it, put their customizations alongside.

**Rejected because:**
- Augur is not a library — it's a full application with dashboard, data, plugins, and scripts
- Package managers don't handle the `data/` and `plugins/custom/` customization model well
- Would require extracting the core into a separate package and redesigning the entire architecture
- Massive overengineering for 50 users

**Revisit when:** Augur Cloud (hosted version) is built — then the core framework becomes a package.

### Alternative 4: Calendar Versioning (CalVer)

Use `2026.02.1` instead of `v0.1.0`.

**Rejected because:**
- SemVer communicates the *nature* of changes (breaking vs. additive vs. fix)
- Users need to know "is this update safe to pull?" — SemVer answers that directly
- CalVer is better for time-based release trains (Home Assistant ships monthly). Augur releases when features are ready, not on a schedule.

### Alternative 5: Centralized Update Server

Build a custom update server that users' Augur instances ping for updates.

**Rejected because:**
- Violates local-first principle (ADR-006) — adds cloud dependency
- Requires hosting infrastructure, monitoring, uptime guarantees
- GitHub Releases API already serves this purpose for free
- Massive overengineering for 50 users

## Open Items

Items completed so far in Phase 1 (foundation scaffolding):
- `VERSION` file at repo root (set to `0.1.0`)
- `plugins/custom/README.md` + `.gitkeep`
- `data/custom/README.md`
- `.gitattributes` with `merge=ours` drivers for `data/`
- `.gitignore` updated for `plugins/custom/skills/`, `data/custom/skills/`, `plugins/admin/skills/updater/data/state.yaml`, and updater mount paths

Remaining Phase 1 tasks:
- `data/defaults/` — copy sanitized YAML templates from current `data/` tree
- `src/scripts/migrations/runner.py` — migration discovery, execution, history, backup
- `src/scripts/migrations/V001__baseline.py` — bootstrap `schema_version` on all existing YAML
- `src/scripts/augur_update.py` — one-command update (fetch → merge → migrate → build)
- `src/scripts/augur_init.py` — first-time setup (copy defaults, create custom dirs, init history)

Phase 2 (automation) blocked until Phase 1 complete.
Phase 3-4 (updater plugin) blocked until migration runner exists.

## References

- [Release-Please Action](https://github.com/googleapis/release-please-action) — Automated release management
- [HACS (Home Assistant Community Store)](https://www.hacs.xyz/) — Plugin distribution model
- [Obsidian Community Plugins](https://github.com/obsidianmd/obsidian-releases) — Registry-based plugin discovery
- [Soft Fork Strategy](https://open-energy-transition.github.io/handbook/docs/Engineering/SoftForkStrategy/) — Fork-and-merge workflow
- [Git .gitattributes merge drivers](https://medium.com/@porteneuve/how-to-make-git-preserve-specific-files-while-merging-18c92343826b) — Protecting user files during merge
- [Flyway Migrations](https://www.deployhq.com/blog/master-your-database-migrations-with-flyway-a-comprehensive-guide-for-all-projects) — Sequential migration pattern
- ADR-006: Local-First Architecture
- ADR-020: Plugin Bundle Architecture
- ADR-045: Launch Plan & Go-To-Market Strategy

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.
> Auto-generated by `/write-adr`. Edit if needed before running.

You are implementing **ADR-048: Multi-User Scale Support**.

Read the full ADR: `docs/decisions/ADR-048-multi-user-scale-support.md`

### Offload Protocol (ADR-054)

Before dispatching each step, check if it can be offloaded to a cheap CLI:

1. Read offload config: `cat config/system/llm.yaml` → look for `offload:` section
2. If `offload.enabled: true` AND the step's tier is `low`:
   ```bash
   python3 plugins/orchestration/skills/executor/scripts/offload_dispatcher.py \
     --task "STEP DESCRIPTION" \
     --files "TARGET_FILE_1,TARGET_FILE_2" \
     --context-files "REFERENCE_FILE_FOR_PATTERNS" \
     --work-dir $(pwd)
   ```
3. Review the JSON output — check `success`, `files_changed`, and `diff` fields
4. Record the verdict:
   - Accept (diff is correct): `python3 plugins/orchestration/skills/executor/scripts/offload_dispatcher.py --record-verdict accept`
   - Fix (you patched the output): `python3 plugins/orchestration/skills/executor/scripts/offload_dispatcher.py --record-verdict fix`
   - Escalate (offload failed, you did it yourself): `python3 plugins/orchestration/skills/executor/scripts/offload_dispatcher.py --record-verdict escalate`
5. If `offload.enabled: false` OR tier is `medium`/`high` → do the step yourself as normal

**Team name**: `adr-048-scale-support`

### Phase 1: Foundation
**Strategy**: PARALLEL (steps 1.1-1.5 independent, then 1.6-1.8 depend on 1.5)

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | low | Create `data/defaults/` directory tree — copy sanitized YAML templates from existing `plugins/`, `data/services/`, `data/core/` (strip personal data, keep structure + `schema_version: 1` in each) | `data/defaults/**/*.yaml` |
| 1.2 | developer | medium | Create migration runner: discover `V*__*.py` files in `src/scripts/migrations/`, execute in sequence, track history in `runtime/migration_history.yaml`, auto-backup before each run, support `--dry-run` flag | `src/scripts/migrations/__init__.py`, `src/scripts/migrations/runner.py` |
| 1.3 | developer | medium | Create `augur_update.py`: stash uncommitted → fetch upstream → merge (respecting `.gitattributes`) → run migration runner → rebuild dashboard (`npm run build` in `src/dashboard/`) → unstash → print summary. Handle merge conflicts gracefully with clear error messages. | `src/scripts/augur_update.py` |
| 1.4 | developer | medium | Create `augur_init.py`: copy `data/defaults/` → `data/` (skip existing files) → create `plugins/custom/skills/` → create `data/custom/skills/` → init `runtime/migration_history.yaml` → print welcome message | `src/scripts/augur_init.py` |
| 1.5 | developer | low | Create V001 baseline migration: scan all YAML files in `data/`, add `schema_version: 1` to any file missing it, skip files that already have it. Must be idempotent. | `src/scripts/migrations/V001__baseline.py` |
| 1.6 | validator | low | Run V001 baseline migration on local data directory, verify `schema_version: 1` was added without data loss | — |
| 1.7 | validator | low | Run `augur_init.py` on a clean temp directory, verify all defaults copied, dirs created, history initialized | — |
| 1.8 | validator | low | Run `python3 -m pytest tests/` to confirm no regressions | — |

### Phase 2: Automation
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | devops | medium | Create Release-Please GitHub Action workflow: trigger on push to main, parse conventional commits, generate CHANGELOG.md, create GitHub Release with tag | `.github/workflows/release.yml` |
| 2.2 | devops | medium | Create user-side sync workflow: weekly schedule + manual trigger, fetch upstream, merge, run migrations, create PR via peter-evans/create-pull-request | `.github/workflows/sync-upstream.yml` |

### Phase 3: Updater Plugin — Core
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | developer | low | Create updater SKILL.md (<100 lines): describe update management capabilities, list MCP tools, reference ADR-048 | `plugins/admin/skills/updater/SKILL.md` |
| 3.2 | developer | low | Create dashboard.yaml exactly as specified in ADR-048 Decision §11 (version 2.0, hub/tabs/modals/actions) | `plugins/admin/skills/updater/augur.yaml` |
| 3.3 | developer | low | Create updater data directory with config.yaml and empty history.yaml (both with `schema_version: 1`) | `plugins/admin/skills/updater/config.yaml`, `plugins/admin/skills/updater/data/history.yaml` |
| 3.4 | developer | medium | Build `version_checker.py`: query GitHub Releases API (`repos/{owner}/{repo}/releases`), compare against `VERSION` file, cache result in `runtime/cache/releases.json` (24h TTL), return structured dict | `plugins/admin/skills/updater/scripts/version_checker.py` |
| 3.5 | developer | medium | Build `updater_service.py`: wrap `augur_update.py` with event logging to `plugins/admin/skills/updater/data/history.yaml`, error handling, backup management, version state tracking | `plugins/admin/skills/updater/scripts/updater_service.py` |
| 3.6 | frontend | medium | Build Overview tab `page.tsx`: UpdateStatusCard (current vs latest version with status badge), 4 stat cards (pending migrations, custom plugins, last update, backup count), recent activity timeline from history.yaml. Use `glass-panel` pattern from daemon overview. Fetch data from `/api/updater/status`. | `plugins/admin/skills/updater/augur/page.tsx`, `plugins/admin/skills/updater/augur/layout.tsx`, `plugins/admin/skills/updater/augur/components/UpdateStatusCard.tsx` |
| 3.7 | developer | medium | Build API routes: `GET /api/updater/status` (read VERSION + state + pending migrations), `POST /api/updater/check` (run version_checker), `GET /api/updater/releases` (cached GitHub releases). Follow `api/career/jobs/route.ts` pattern (Next.js Route Handlers, YAML I/O via `DATA_PATHS`). | `plugins/admin/skills/updater/api/status/route.ts`, `plugins/admin/skills/updater/api/check/route.ts`, `plugins/admin/skills/updater/api/releases/route.ts` |

### Phase 4: Updater Plugin — Full
**Strategy**: PARALLEL (4.1-4.4 independent, 4.5 depends on all)

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 4.1 | developer | medium | Build write API routes: `POST /api/updater/update` (calls updater_service), `POST /api/updater/migrate` (calls migration runner), `POST /api/updater/rollback` (restore from backup), `POST /api/updater/backup` (create manual backup) | `plugins/admin/skills/updater/api/update/route.ts`, `.../migrate/route.ts`, `.../rollback/route.ts`, `.../backup/route.ts` |
| 4.2 | frontend | medium | Build Releases tab: ChangelogViewer component fetching from `/api/updater/releases`, render each release as card (version, date, markdown changelog), "currently installed" badge, filter controls | `plugins/admin/skills/updater/augur/releases/page.tsx`, `.../components/ChangelogViewer.tsx` |
| 4.3 | frontend | medium | Build Migrations tab: MigrationTimeline component (vertical timeline, color-coded by status), Run Pending button, Dry Run button, BackupManager component (list backups with restore buttons, size, timestamp) | `plugins/admin/skills/updater/augur/migrations/page.tsx`, `.../components/MigrationTimeline.tsx`, `.../components/BackupManager.tsx` |
| 4.4 | frontend | medium | Build Custom Plugins tab: PluginCard grid scanning `plugins/custom/skills/`, validation checks (SKILL.md exists, dashboard.yaml valid, no ID conflicts), health indicators | `plugins/admin/skills/updater/augur/plugins/page.tsx`, `.../components/PluginCard.tsx` |
| 4.5 | developer | medium | Build `plugin_scanner.py` (discover + validate custom plugins), `conflict_analyzer.py` (parse git merge conflicts), `full_update.yaml` chain (check → backup → update → migrate → verify) | `plugins/admin/skills/updater/scripts/plugin_scanner.py`, `.../conflict_analyzer.py`, `.../chains/full_update.yaml` |

### Final Phase: Verification
| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Run `npm run build` in `src/dashboard/` — verify updater plugin mounts and builds clean |
| V.2 | validator | low | Run `python3 -m pytest tests/` — verify no regressions |
| V.3 | validator | low | Run `python3 src/scripts/augur_init.py --dry-run` — verify initialization logic |
| V.4 | validator | low | Run `python3 src/scripts/migrations/runner.py --dry-run` — verify migration discovery |
| V.5 | architect | low | Verify ADR-048 intent matches implementation — filesystem isolation, schema versioning, update workflow all working |

### Completion Criteria
- [ ] All phases executed
- [ ] `VERSION` file exists at repo root
- [ ] `.gitattributes` protects `data/` on merge
- [ ] `plugins/custom/` and `data/custom/` exist with READMEs
- [ ] Migration runner discovers and executes V001 baseline
- [ ] `augur_update.py` performs full update cycle (or errors gracefully)
- [ ] `augur_init.py` bootstraps a fresh install from defaults
- [ ] Updater plugin builds and mounts in dashboard (`npm run build` clean)
- [ ] Updater Overview tab renders version status
- [ ] API routes `/api/updater/status`, `/check`, `/releases` respond
- [ ] All tests pass
- [ ] No orphaned files or broken references
- [ ] ADR status updated to Accepted/Implemented
