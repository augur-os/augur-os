# Multi-Client Skill Structure Refactor

**Date:** 2026-03-22
**Status:** Draft
**Supersedes:** ADR-426 (Phase 3-4), ADR-186 (sync refactor), ADR-171 (bidirectional sync)
**Reference:** [MiniMax-AI/skills](https://github.com/MiniMax-AI/skills)

## Problem

Augur skills are primarily stored in `.claude/skills/` (~200 SKILL.md files including nested sub-skills), with adapted copies in `.gemini/skills/`, `.codex/prompts/`, and a now-empty `plugins/` directory (legacy, already migrated). The infrastructure managing this — a 4-tier discovery engine with deduplication and shadowing (~600 lines), an MCP-backed render pipeline with adapted-copy markers (~500 lines) — remains complex despite the actual skill source being effectively one directory. This complexity exists to serve a simple goal: make skills available to multiple AI clients.

MiniMax-AI/skills demonstrates a radically simpler model: one `skills/` directory, per-client install instructions (symlinks or git clone), no sync engine. Their 10-skill repo works across Claude Code, Cursor, Codex, and OpenCode with ~0 lines of sync infrastructure.

### Goals

1. **Simplify sync infrastructure** — Replace 4-tier discovery + MCP sync with a single directory + one-way stub generator.
2. **Make skills distributable** — Enable community contributions and prepare for marketplace install when Claude Code plugin API stabilizes.
3. **Flatten storage** — One canonical `skills/` directory at project root.

### Non-Goals

- Changing the vault data model (ADR-270 external dirs stay).
- Changing the dashboard architecture.
- Rewriting skill content.

## Design

### Directory Structure

```
augur/
├── skills/                              # CANONICAL — all skills live here
│   ├── {skill-name}/                    # Flat, one dir per skill (~140 entries)
│   │   ├── SKILL.md                     # Frontmatter + instructions
│   │   ├── references/                  # Reference docs (optional)
│   │   ├── modules/                     # Modular docs (optional)
│   │   ├── scripts/                     # Python scripts (optional)
│   │   ├── templates/                   # Templates (optional)
│   │   └── augur/                       # AUGUR-NATIVE marker (optional)
│   │       ├── dashboard/               # Dashboard pages (mounted)
│   │       ├── data/                    # Skill data, prompts, configs
│   │       ├── tests/                   # Skill tests
│   │       └── seed/                    # Seed data
│   └── README.md                        # Auto-generated index grouped by hub
│
├── .claude-plugin/                      # Claude Code marketplace manifest
│   ├── plugin.json                      # {name, version, skills: "./skills/"}
│   └── marketplace.json                 # Marketplace listing
├── .cursor-plugin/
│   └── plugin.json                      # Cursor discovery
├── .codex/
│   ├── INSTALL.md                       # Codex install guide
│   └── prompts/                         # Generated stubs (committed)
├── .opencode/
│   └── INSTALL.md                       # OpenCode install guide
│
├── scripts/
│   └── generate_client_stubs.py         # One-way stub generator (~100 lines)
│
├── apps/dashboard/                      # Dashboard (mount paths updated)
├── src/                                 # Core Python (path refs updated)
├── config/                              # System config
└── docs/                                # Docs, ADRs
```

### Skill Tiers

Two tiers, distinguished by the presence of an `augur/` subdirectory:

| Aspect | Portable | Augur-Native |
|--------|----------|--------------|
| **Marker** | No `augur/` subdir | Has `augur/` subdir |
| **Frontmatter** | Standard: `name`, `description`, `license`, `metadata` | Standard + `x-augur-*` extensions |
| **Dashboard pages** | None | `augur/dashboard/` |
| **MCP tools** | None | Referenced via `x-augur-mcp-tools` |
| **Autoloop config** | None | `x-augur-loop` in frontmatter |
| **Distribution** | Works in any SKILL.md-aware client | Requires Augur runtime |
| **Community contribution** | PR to `skills/` | Requires Augur knowledge |

### Skill Sources and Lifecycle

Skills come from three distinct sources. Discovery aggregates all three into a unified registry for the dashboard.

#### Source Taxonomy

| Source | Location | Origin Tag | Author Tag | Managed By | Writable by Augur? |
|--------|----------|-----------|------------|-----------|-------------------|
| **Augur bundled** | `skills/` | `augur` | `bundled` | Git repo | Yes |
| **User-created via `/evolve`** | `skills/` | `augur` | `user` | Git repo | Yes |
| **Claude Code plugin cache** | `~/.claude/plugins/cache/{pkg}/skills/` | `claude-code` | `external` | Claude Code CLI | No (read-only) |
| **Codex installed** | `~/.codex/prompts/` (non-generated files) | `codex` | `external` | Codex CLI | No (read-only) |
| **Cursor installed** | `~/.cursor/rules/` (non-generated files) | `cursor` | `external` | Cursor CLI | No (read-only) |
| **Gemini installed** | `~/.gemini/skills/` (non-generated files) | `gemini` | `external` | Gemini CLI | No (read-only) |

**Key principle:** `skills/` is the only writable source. Client caches are read-only — Augur never writes to them, clients never write to `skills/`. The stub generator writes outward (Augur → client stubs), never inward.

#### Adding a New Skill

**Via `/evolve` pipeline (user-created):**
1. User runs `/evolve my-new-skill`
2. `/evolve` scaffolds `skills/my-new-skill/SKILL.md` with `x-augur-created-by: user`
3. User develops the skill (adds references, scripts, optionally `augur/` subdir for native features)
4. Stub generator runs (via `/dev-sync` or pre-commit hook) → generates stubs in `.codex/prompts/`, `.cursor/rules/`, etc.
5. Dashboard discovers the skill on next scan → shows it with origin=augur, author=user

**Manual creation:**
1. `mkdir skills/my-skill && $EDITOR skills/my-skill/SKILL.md`
2. Write frontmatter (at minimum: `name`, `description`)
3. Optionally add `x-augur-created-by: user` to distinguish from bundled
4. Run `/dev-sync` to generate client stubs

**Installing external skill packs (e.g., MiniMax):**
- Each AI client handles external installs through its own mechanism:
  - Claude Code: `claude plugin install` → `~/.claude/plugins/cache/{pkg}/skills/`
  - Codex: `git clone` + symlink → `~/.codex/prompts/` or `~/.agents/skills/`
  - Cursor: Git clone + settings → reads `skills/` from cloned repo
- Augur discovers these via read-only scans of client cache directories
- External skills are **never copied into `skills/`** — they stay in their client-managed locations
- Dashboard shows them tagged with their client origin

#### Removing a Skill

**Augur skill (bundled or user-created):**
1. `rm -rf skills/{name}/`
2. Stub generator on next run detects the skill is gone → deletes stale stubs from `.codex/prompts/{name}.md`, `.cursor/rules/{name}.mdc`, etc.
3. Dashboard mount script on next build → removes mounted dashboard pages
4. **Dependency check:** Before deletion, grep for `x-augur-dependencies: required: [{name}]` across all SKILL.md files. Warn if other skills depend on this one.
5. **Route cleanup:** If the skill had `x-augur-dashboard-pages`, verify those routes are removed from the dashboard build.

**External skill (client-installed):**
- Uninstall through the client that installed it (e.g., `claude plugin uninstall`)
- Augur's next discovery scan stops seeing it — no cleanup needed on Augur's side

#### Generated Stubs vs Client-Installed Skills

Client directories contain a mix of Augur-generated stubs and client-installed skills. Discovery must distinguish them:

```
.codex/prompts/
├── auto-lint.md          # AUGUR-GENERATED (from skills/auto-lint/) — skip in discovery
├── my-custom-skill.md    # AUGUR-GENERATED (from skills/my-custom-skill/) — skip in discovery
└── some-codex-plugin.md  # INSTALLED by user via Codex — discover as origin="codex"
```

**Marker:** Generated stubs include `<!-- AUGUR-GENERATED -->` in the first 5 lines. Discovery skips files with this marker in client dirs (those skills are already discovered from `skills/`). Files without the marker are treated as client-installed external skills.

### Discovery: Unified Multi-Source Scan

Discovery is not "one dir, one scan" but "one primary + N read-only client scans":

```python
def discover_all_skills() -> list[SkillRecord]:
    """Aggregate skills from all sources with origin tagging."""
    skills = []

    # 1. Primary source: skills/ (writable, Augur-owned)
    for skill_dir in sorted((get_project_root() / "skills").iterdir()):
        if (skill_dir / "SKILL.md").exists():
            record = parse_skill_md(skill_dir / "SKILL.md")
            record.origin = "augur"
            record.author = record.frontmatter.get("x-augur-created-by", "bundled")
            skills.append(record)

    # 2. Client caches: read-only, origin-tagged
    for client_name, cache_dir in CLIENT_CACHE_DIRS.items():
        if not cache_dir.exists():
            continue
        for skill_file in find_skill_files(cache_dir):
            if is_augur_generated(skill_file):
                continue  # Skip our own stubs
            record = parse_skill_md(skill_file)
            record.origin = client_name
            record.author = "external"
            skills.append(record)

    return skills
```

```python
# Resolved via src.config.paths (rule 3: no hardcoded paths)
def get_client_cache_dirs() -> dict[str, Path]:
    """Client cache directories — add to src/config/paths.py."""
    home = Path.home()
    return {
        "claude-code": home / ".claude/plugins/cache",  # Recursive scan for SKILL.md
        "codex": home / ".codex/prompts",                # Flat .md files
        "cursor": home / ".cursor/rules",                # Flat .mdc files
        "gemini": home / ".gemini/skills",               # SKILL.md per dir
    }
# This function lives in src/config/paths.py alongside get_skills_dir()
```

**Key differences from old 4-tier system:**

| Aspect | Old (4-tier) | New (primary + clients) |
|--------|-------------|------------------------|
| **Priority/shadowing** | Tier 4 overrides Tier 1 | No overrides — different origins coexist |
| **Deduplication** | By canonical name | By `(origin, name)` compound key — same name from different origins shown as separate entries |
| **Adapted-copy detection** | Scan first 500 bytes for markers | `AUGUR-GENERATED` marker to skip own stubs |
| **Writable sources** | All tiers writable | Only `skills/` is writable |
| **Complexity** | ~600 lines | ~100 lines |

**Name collision policy:** If an external skill pack (e.g., MiniMax) ships a skill with the same name as an Augur skill (e.g., both have `frontend-dev`), discovery returns both entries with different `origin` values. The dashboard shows both rows — the origin column distinguishes them. This is intentional: the user installed both and should see both. The compound key is `(origin, name)`, not just `name`. Within a single origin, names must be unique (enforced by directory structure for `skills/`, and by the client for external caches).

### Dashboard Skills Browser

The dashboard needs a unified view of all skills across all sources. This replaces the current skills page with a richer filterable view.

#### Data Model

Each skill in the dashboard registry has:

```typescript
interface SkillRecord {
  name: string;
  description: string;
  origin: "augur" | "claude-code" | "codex" | "cursor" | "gemini";
  author: "bundled" | "user" | "external";
  tier: "portable" | "native";       // Derived: has augur/ subdir?
  hub: string | null;                 // From x-augur-hub (null for portable/external)
  type: string | null;                // From x-augur-type
  tags: string[];                     // From metadata.tags
  path: string;                       // Absolute path to SKILL.md
  hasAugurDir: boolean;               // Has augur/ subdir
  hasDashboardPages: boolean;         // Has augur/dashboard/
  mcp_tools: string[];                // From x-augur-mcp-tools
}
```

#### Filters and Views

| Filter | Values | Use Case |
|--------|--------|----------|
| **Origin** | `augur`, `claude-code`, `codex`, `cursor`, `gemini`, `all` | "Show me all skills from Claude Code plugins" |
| **Author** | `bundled`, `user`, `external`, `all` | "Show me skills I created" |
| **Tier** | `portable`, `native`, `all` | "Show me skills that work in any client" |
| **Hub** | `adaptive`, `brain`, `career`, `command`, `life`, `studio`, `none` | "Show me all adaptive hub skills" |
| **Client availability** | Multi-select checkboxes | "Which clients can use this skill?" |

#### Client Availability Column

For each skill, the dashboard shows which clients can access it:

| Skill | Origin | Augur | Claude | Codex | Cursor | Gemini |
|-------|--------|-------|--------|-------|--------|--------|
| auto-lint | augur | Y | Y (stub) | Y (stub) | Y (stub) | Y (stub) |
| my-custom-skill | augur | Y | Y (stub) | Y (stub) | Y (stub) | Y (stub) |
| minimax-frontend | claude-code | - | Y (native) | - | - | - |
| some-codex-tool | codex | - | - | Y (native) | - | - |

- **Y (native)**: Client reads the skill directly from its own directory
- **Y (stub)**: Client has a generated stub from `skills/`
- **-**: Client cannot access this skill

#### API Endpoint

```
GET /api/skills/registry
```

Returns the unified skill list. Backed by the `discover_all_skills()` MCP tool which scans `skills/` + client caches. Cached with 30s TTL.

### SKILL.md Format

#### Portable Skill

```yaml
---
name: frontend-dev
description: |
  Full-stack frontend development with UI design, animations, and AI-generated media.
  Use when: building landing pages, dashboards, marketing sites.
license: MIT
metadata:
  version: "1.0.0"
  category: frontend
  tags: [react, nextjs, tailwind, animation]
---

# Frontend Dev

...skill instructions...
```

#### Augur-Native Skill

```yaml
---
name: auto-lint
description: Run ESLint auto-fix and AI-assisted lint error resolution
license: MIT
metadata:
  version: "1.0.0"
  category: automation
  tags: [eslint, code-quality]
# --- Augur extensions (ignored by non-Augur clients) ---
x-augur-hub: adaptive
x-augur-type: autoloop
x-augur-visibility: auto
x-augur-loop:
  name: code-quality
  tier: 1
  trigger: nightly
  config:
    scan_timeout: 120
    fix_timeout: 300
    max_turns: 12
x-augur-mcp-tools: [run-eslint, fix-lint-errors]
x-augur-dashboard-pages: [/adaptive/code-quality]
x-augur-dependencies:
  required: []
x-augur-config-file: config.yaml
---

# Auto-Lint

...skill instructions...
```

#### Fields Removed

| Field | Reason |
|-------|--------|
| `x-augur-master` | Single location = single owner. No master/slave semantics. |
| `x-augur-sync` | All skills are available to all clients by default. |
| `x-augur-origin` | Redundant — origin is always the `skills/` dir. |
| `x-augur-plugin` | No more plugin bundles. |

### Client Integration

| Client | How It Reads Skills | External Install Method |
|--------|-------------------|------------------------|
| **Claude Code** | `.claude-plugin/plugin.json` points to `skills/` | Git clone (marketplace install TBD — API not yet public) |
| **Cursor** | `.cursor-plugin/plugin.json` points to `skills/` | Git clone, point settings at `skills/` |
| **Codex** | Generated stubs in `.codex/prompts/` (committed) | Git clone + `ln -s skills/ ~/.agents/skills/augur` |
| **Gemini** | Config points to `skills/` directly | Git clone + symlink to `~/.gemini/skills/` |
| **OpenCode** | Symlinks from `~/.config/opencode/skills/` | Per `.opencode/INSTALL.md` |
| **Copilot** | Generated instructions in `.github/copilot/` | Via GitHub repo settings |

### Stub Generator

Replace the entire MCP-backed sync pipeline with a single script:

```
scripts/generate_client_stubs.py
```

**Input:** `skills/*/SKILL.md`
**Output:** Client-specific stub files for clients that cannot read `skills/` directly.

| Target | Output Format | Output Location |
|--------|--------------|-----------------|
| Codex | Flat `.md` with skill body inlined | `.codex/prompts/{skill-name}.md` |
| Cursor | `.mdc` rule files | `.cursor/rules/{skill-name}.mdc` |
| Copilot | Instruction markdown | `.github/copilot/{skill-name}.md` |

**Properties:**
- ~130 lines of Python, no MCP dependency
- One-way: reads `skills/`, writes stubs. Never modifies `skills/`.
- Runs via `/dev-sync` command (primary) or as pre-commit hook
- Generated files are committed (like MiniMax) so consumers don't need to run the script
- **Cleanup mode:** On each run, the generator lists all `AUGUR-GENERATED`-marked files in each target dir and deletes any whose source skill no longer exists in `skills/`. Only files with the marker are touched — manually created files in client dirs are never deleted. Generation and cleanup run in the same invocation (generate first, then cleanup).

### Discovery Changes

See "Discovery: Unified Multi-Source Scan" section above for the full implementation. Summary:

**Current** (`skill_discovery.py`, ~600 lines):
- 4-tier scan (plugin-cache → global → project → client)
- Deduplication by canonical name with shadowing
- Adapted-copy detection (marker scanning)
- Tier precedence rules

**New** (~100 lines):
- Primary scan of `skills/` (origin=augur)
- Read-only scans of client caches (origin={client})
- `AUGUR-GENERATED` marker to skip own stubs in client dirs
- No tiers, no dedup, no shadowing
- 30s TTL cache preserved for dashboard performance

**Function naming:** Keeps `discover_all_skills()` for caller compatibility (`filesystem_registry.py`, `skill_registry.py`, `__all__`). Signature and return type unchanged. Callers of `list_skills`, `resolve_skill`, `get_skill_path` preserved as thin wrappers.

**Nested/sub-skills:** Promoted to top-level during migration. Migration script walks recursively for all nesting patterns (see Phase 2). Post-migration, discovery scans top-level `skills/` only — no recursive descent.

### Dashboard Mount System

Current mount system is `apps/dashboard/scripts/mount-plugins.ts` (~900 lines), a TypeScript pipeline with:
- `CLIENT_SKILL_DIRS` map hardcoding `.claude/skills`, `.codex/prompts`, `.gemini/skills`, `.cursor/rules`
- Six separate scanning functions (`scanPluginDir`, `scanClientSkillDir`, `scanPluginCacheDir`, `discoverPlugins`, etc.)
- Each with their own skill-dir resolution logic

**This is a significant rewrite, not a one-line path update.**

**Before:** Multiple scanning functions across 4+ directories
**After:** Single scan of `skills/*/augur/dashboard/`

The mount script must be simplified to:
1. Remove `CLIENT_SKILL_DIRS` map and multi-directory scanning
2. Replace all scanning functions with a single `scanSkillsDir()` that reads `skills/`
3. Keep the dashboard page copying logic (just the source path changes)
4. This rewrite happens in Phase 3 step 4, in the same commit as the skill move

### What Gets Deleted

| Component | Lines | Action |
|-----------|-------|--------|
| `skill_discovery.py` 4-tier logic | ~550 | Rewrite to ~100 lines (single-dir scan + cache + wrappers) |
| Sync pipeline scripts (verify current filenames before migration) | ~300+ | Delete — confirm actual paths via grep |
| `skill_renderer.py` | ~106 | Delete |
| `client_formats.py` | ~86 | Absorb into stub generator |
| `skill_detection.py` (adapted-copy markers) | ~27 | Delete |
| `filesystem_registry.py` tier logic | ~100 | Simplify |
| `mount-plugins.ts` multi-dir scanning | ~900 | Rewrite to single-dir scan |
| `.claude/skills/` directory | ~200 skills | Move to `skills/`, delete dir |
| `plugins/` directory | empty (legacy) | Delete |
| `.gemini/skills/` adapted copies | varies | Delete |
| `AUGUR-ADAPTED-COPY` / `AUGUR-STUB` markers | scattered | Delete |
| `x-augur-master`, `x-augur-sync`, `x-augur-origin` fields | ~197 SKILL.md files | Remove |
| `PLUGIN_BUNDLES` constant + `get_plugin_bundles()` | ~20 | Remove, update all importers |
| `get_plugins_dir()` / `path_config.plugins.path` | ~10 | Remove or repurpose |

**Net reduction:** ~900 lines of infrastructure code deleted, ~150 lines added (stub generator + simplified discovery).

### What Gets Added

| Component | Lines (est.) | Purpose |
|-----------|-------------|---------|
| `scripts/generate_client_stubs.py` | ~100 | One-way stub generator with `AUGUR-GENERATED` markers |
| `scripts/generate_client_stubs.py` cleanup logic | ~30 | Detect and remove stale stubs for deleted skills |
| `.claude-plugin/plugin.json` | ~15 | Claude marketplace manifest |
| `.claude-plugin/marketplace.json` | ~15 | Marketplace listing |
| `.cursor-plugin/plugin.json` | ~20 | Cursor discovery |
| `.codex/INSTALL.md` | ~50 | Codex install guide |
| `.opencode/INSTALL.md` | ~50 | OpenCode install guide |
| `skills/README.md` | auto-gen | Skill index grouped by hub |
| `CLIENT_CACHE_DIRS` config | ~20 | Client cache directory map for multi-source discovery |
| Dashboard skills browser page | ~200 | Unified skills view with origin/author/tier/hub filters |
| `/api/skills/registry` route | ~30 | API endpoint for unified skill registry |

## Migration Plan

### Phase 1: Scaffold (No Breakage)

1. Create `skills/` directory at project root
2. Add `.claude-plugin/`, `.cursor-plugin/`, `.codex/INSTALL.md`, `.opencode/INSTALL.md`
3. Write `scripts/generate_client_stubs.py`
4. Write migration script: `scripts/migrate_skills.py`

### Phase 2: Move Skills (Scripted, Single Commit)

**Primary source:** `.claude/skills/` (~200 SKILL.md files). The `plugins/` directory is already empty of skills (legacy migration completed). `dist/plugins/` contains generated build artifacts — these are regenerated, not migrated.

Migration script does:
1. For each top-level skill in `.claude/skills/`: move to `skills/{name}/`
2. Flatten nested sub-skills using recursive SKILL.md walk. Known nesting patterns:
   - `{parent}/commands/{child}/SKILL.md` (e.g., `devops/commands/adr/`, `updater/commands/harden/`, `ai_bridge/commands/orch-audit/`)
   - `{parent}/references/skills/{child}/SKILL.md` (e.g., `lifestyle/references/skills/scrape-and-save-idea/`)
   - Any other depth — migration script walks recursively for all `SKILL.md` files, not just known patterns
   - Flattened children get `x-augur-parent: {parent-name}` field added
3. Remove `x-augur-master`, `x-augur-sync`, `x-augur-origin`, `x-augur-plugin` from all SKILL.md frontmatter (~197 files with ~355 occurrences in `.claude/skills/` alone; `dist/plugins/` is regenerated separately)
4. Delete `.claude/skills/` directory (no symlink — rule 14 forbids backward-compat shims)
5. Delete `plugins/` directory (already empty but remove the dir itself)
6. Pre-commit validation: count SKILL.md files before and after, abort if mismatch
7. Log every move for audit

**No backward-compat symlinks.** Per CLAUDE.md rule 14, all references must be fixed atomically in the same commit. The migration script includes a grep pass to catch stale references before committing.

### Phase 3: Update References

1. Update `skill_discovery.py` — single-dir scan, remove 4-tier logic
2. Update `src/config/paths.py`:
   - Add `get_skills_dir()` → `get_project_root() / "skills"`
   - Remove `plugins/` from `validate_paths()` (currently auto-creates it via `mkdir`)
   - Rewrite `get_skill_root()` to resolve from `skills/` instead of `plugins/{bundle}/skills/`
   - Remove or update `PLUGIN_BUNDLES` constant (evaluated at import time via `get_plugin_bundles()`) — all importers of this symbol must be audited and updated
3. Audit all consumers of `x-augur-master` and `x-augur-sync` fields in Python code (used by `filesystem_registry.py` to populate `SkillRecord.master` and `sync_enabled`) — remove or update these codepaths
4. **Rewrite dashboard mount system** (`apps/dashboard/scripts/mount-plugins.ts`, ~900 lines — see "Dashboard Mount System" section for full scope):
   - Remove `CLIENT_SKILL_DIRS` map and multi-directory scanning
   - Replace `scanPluginDir`, `scanClientSkillDir`, `scanPluginCacheDir`, `discoverPlugins` with single `scanSkillsDir()`
   - Update source glob to `skills/*/augur/dashboard/`
   - Keep page-copying logic unchanged (only source path changes)
5. Update `/dev-sync` skill's SKILL.md to invoke `generate_client_stubs.py` instead of the old sync pipeline
6. Run `grep -r '.claude/skills/' --include='*.py' --include='*.ts' --include='*.md'` and fix all stale refs
7. Run `grep -r 'plugins/' --include='*.py' --include='*.ts' --include='*.md'` and fix all stale refs
8. Run `grep -r 'x-augur-master\|x-augur-sync\|x-augur-origin' --include='*.py' --include='*.ts'` and remove all consumers
9. Update CLAUDE.md directory layout section
10. Update all topic docs (`ARCHITECTURE.md`, `SKILLS.md`, etc.)

### Phase 4: Delete Old Infrastructure

1. Delete `sync_client_skills.py`, `skill_renderer.py`, `skill_detection.py`
2. Simplify `client_formats.py` into `generate_client_stubs.py`
3. Simplify `filesystem_registry.py` — remove tier logic, adapted-copy detection
4. Delete `.gemini/skills/` adapted copies
5. Delete `augur.yaml` plugin manifests (discovery from SKILL.md frontmatter only)
6. Remove all `AUGUR-ADAPTED-COPY` and `AUGUR-STUB` markers from codebase

### Phase 5: Validate

1. Run full dashboard build
2. Run `/dev-test` suite
3. Run stub generator, verify output matches expectations
4. Verify all skills discoverable via new `discover_all_skills()` — count must match pre-migration count
5. Grep for any remaining stale paths (`.claude/skills/`, `plugins/`, `x-augur-master`, `AUGUR-ADAPTED-COPY`)
6. Write superseding ADR via `/adr write` (per CLAUDE.md rule 12 — this spec is not the canonical artifact, the ADR is)

## Open Questions

| # | Question | Default | Needs Decision |
|---|----------|---------|----------------|
| 1 | ~~Should `.codex/prompts/` stubs be committed?~~ | **Closed: Yes** — committed like MiniMax, so consumers don't need to run the generator | No |
| 2 | Should `augur.yaml` plugin manifests be deleted? | Yes — discovery from SKILL.md only. Delete in Phase 4 after `PLUGIN_BUNDLES` removed in Phase 3. | Yes |
| 3 | ~~Should the stub generator run as pre-commit hook?~~ | **Closed: Yes** — `/dev-sync` is primary, pre-commit hook as backup | No |
| 4 | Naming convention for community-contributed skills? | No prefix, flat namespace | Low priority |
| 5 | ~~Should `.claude/skills` symlink persist?~~ | **Closed: No symlink** — CLAUDE.md rule 14 forbids backward-compat shims | No |
| 6 | Should the `augur/` subdir in native skills keep current structure? | Yes — `dashboard/`, `data/`, `tests/`, `seed/` | No — proven |
| 7 | Should hub grouping be enforced by CI (frontmatter lint)? | Yes — `x-augur-hub` required for native skills | No — already exists |
| 8 | How to handle nested sub-skills (e.g., `devops/commands/adr/`)? | Promote to top-level with `x-augur-parent` field | Resolved in spec |

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Migration script misses edge cases (nested sub-skills, unusual structures) | Medium | High | Run in dry-run mode first, audit log, count validation, git revert safety net |
| Dashboard mount breaks | High | High | Update mount script in same commit as skill move |
| Stale path references in 140+ SKILL.md files | High | Medium | Automated grep + fix pass |
| `paths.py` hardcoded `plugins/` assumptions break startup | High | High | Explicit `paths.py` rewrite in Phase 3 step 2 — audit `validate_paths()`, `get_skill_root()`, `PLUGIN_BUNDLES` |
| `x-augur-master`/`x-augur-sync` consumers silently break | Medium | High | Audit all Python consumers of these fields before removing (Phase 3 step 3) |
| Autoloop configs reference old paths | Medium | Medium | Autoloops use skill names not paths — likely safe, but grep to confirm |
| `claude plugin install` CLI not yet public | High | Low | Not a success criterion — marketplace support is future work. Git clone works now. |
| Client cache dirs change between versions | Medium | Medium | `CLIENT_CACHE_DIRS` is a config map, not hardcoded. Update when clients change their paths. |
| Client cache scanning is slow (large caches) | Low | Medium | Scan is read-only with TTL cache. Client caches are typically small (<50 skills). |
| Generated stubs confused with client-installed skills | Low | High | `AUGUR-GENERATED` marker in first 5 lines. Discovery skips marked files. |
| 140-entry flat dir overwhelms IDE file browser | Low | Low | `.editorconfig` or IDE settings to collapse; `skills/README.md` index |

## Success Criteria

1. All Augur skills accessible from `skills/` at project root
2. `plugins/` and `.claude/skills/` directories deleted (no symlinks)
3. `skill_discovery.py` under 150 lines (primary scan + client cache scans + cache)
4. No adapted copies, no `AUGUR-ADAPTED-COPY` / `AUGUR-STUB` markers anywhere
5. No references to `x-augur-master`, `x-augur-sync`, `x-augur-origin` in Python/TS code
6. Stub generator produces valid Codex/Cursor files with `AUGUR-GENERATED` markers
7. Stub generator cleanup removes stale stubs when skills are deleted
8. Dashboard skills browser shows all skills from all sources with correct origin/author/tier tags
9. Client-installed skills (Claude plugin cache, Codex prompts, etc.) visible in dashboard with client origin tag
10. `/evolve` creates new skills in `skills/` with `x-augur-created-by: user`
11. Dashboard builds and all pages render
12. `/dev-test` passes
13. Skill count post-migration matches pre-migration count (no skills lost)
14. Superseding ADR written and indexed

## Artifact Note

Per CLAUDE.md rule 12, this spec is a brainstorming output — not the canonical artifact. Before implementation begins, invoke `/adr write` to create the superseding ADR at `get_vault_dir()/dev/adrs/ADR-NNN-multi-client-skill-structure.md`. The ADR absorbs this spec's content and becomes the implementation reference.
