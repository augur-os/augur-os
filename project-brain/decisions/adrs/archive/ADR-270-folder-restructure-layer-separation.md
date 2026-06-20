---
status: Implemented
date: '2026-03-10'
deciders:
- '@gsannikov'
related: []
hub: null
tags:
- folder
- restructure
- layer
- separation
superseded_by: null
---

# ADR-270: Folder Restructure — Layer Separation

**Related ADRs**: ADR-083 (Plugin Data Colocation), ADR-143 (Chains Removal), ADR-163 (Config Decentralization), ADR-238 (Skill Standards Loop)

## Context

Augur's folder structure conflates code, user data, derived indexes, runtime state, and platform wiring inside a single monorepo. This creates five problems:

1. **User data locked in git** — personal notes, career records, financial data live inside `plugins/{bundle}/skills/{skill}/augur/data/` and are version-controlled alongside code. Users can't browse or edit their data with Obsidian, iA Writer, or other external tools.

2. **Skills are non-portable** — the `augur/` folder inside each skill mixes Augur platform wiring with standard-compatible content. Skills can't be used as vanilla Claude Code skills per the [open standard](https://code.claude.com/docs/en/skills).

3. **RAG is distributed** — each skill maintains its own `augur/rag/` index (7,141 files across 30 skills, growing to 130 at full coverage). Cross-skill search requires fan-out. RAG indexes are derived data stored alongside source code.

4. **Runtime in the repo** — logs, cache, daemon state live in `runtime/` inside the project directory. macOS can't manage these (Time Machine backs up caches, Console.app can't find logs, no auto-purge under disk pressure).

5. **Dead code accumulation** — `augur/chains/` (removed per ADR-143), `augur/_dev/` (zero references), `augur/data-template/` (unused), `augur/hooks/` (orphaned), `src/lib/plugins/` (stale mounts from Feb 24).

Augur's identity is a **connection layer** between AI agents, documents, skills, notes, and automation workflows. The folder structure should reflect this by separating concerns into layers with independent lifecycles.

## Decision

### Layer Architecture

| Layer | Location | Lifecycle | Managed by |
|---|---|---|---|
| Engine + Plugins (code) | `~/Projects/Augur/` | Developer | Git |
| User Data (vault) | `~/Vault/Augur/` | User | Obsidian/editor, git/iCloud |
| Binary Documents | `~/Documents/Augur/` | User | Finder, iCloud/Drive |
| RAG Indexes | `~/Library/Application Support/Augur/rag/` | Derived | Augur engine |
| Persistent State | `~/Library/Application Support/Augur/state/` | System | Time Machine backed |
| Logs | `~/Library/Logs/Augur/` | Ephemeral | Console.app visible |
| Caches | `~/Library/Caches/Augur/` | Ephemeral | macOS auto-purges |
| LaunchAgents | `~/Library/LaunchAgents/com.augur.*.plist` | System | Already here |

Linux fallback: `~/.local/share/augur/`, `~/.cache/augur/`, `~/.local/state/augur/logs/`

### D1: Skill Folder — `rm -rf augur/` Rule

Every skill must pass: **delete `augur/` and what remains is 100% Claude Code skills-standard-compliant.**

Standard folders at skill root (per spec):
- `SKILL.md` — skill definition with frontmatter
- `scripts/` — executable code (Python, Bash), including MCP tools at `scripts/mcp/`
- `references/` — documentation loaded into AI context on demand
- `examples/` — runnable examples
- `assets/` — templates used in output (default action YAMLs, prompt templates, block templates, seed data, plist templates)

Non-standard content lives IN `augur/`:
- `augur.yaml`, `README.md`, `api/`, `dashboard/`, `lib/`, `config/`, `adapters/`, `tests/`, `modules/`

### D2: Centralized RAG

RAG indexes are build artifacts (like `.next/` output). Derived from source, fully rebuildable.

- Location: `~/Library/Application Support/Augur/rag/`
- All `augur/rag/` directories and `symbols.yaml` files move to central index
- Cross-skill queries become zero-cost (single index, no fan-out)
- Skill install triggers reindex; uninstall prunes index

### D3: User Data Vault

User-created and user-evolved content moves external:

- Location: `~/Vault/Augur/{bundle}/{skill}/`
- What moves: notes, jobs, profiles, knowledge, evolved actions, evolved prompts, user custom dashboards, memory (MEMORY.md + daily logs)
- Install flow: `assets/` defaults seeded to vault on skill install
- Lookup order: vault first → `assets/` fallback
- Browseable in Obsidian, editable with any markdown editor

### D4: macOS Standard Runtime

- Logs → `~/Library/Logs/Augur/` (Console.app auto-discovers)
- State → `~/Library/Application Support/Augur/state/` (Time Machine backed)
- Caches → `~/Library/Caches/Augur/` (auto-excluded from Time Machine, purged under disk pressure)
- Plist **templates** stored in daemon plugin `assets/plists/*.plist.tmpl`, rendered and installed to `~/Library/LaunchAgents/`

### D5: Binary Documents

Binary files (PDFs, Excel, images) → `~/Documents/Augur/{bundle}/{skill}/`. Syncs via iCloud/Drive. RAG indexes via pointers.

### D6: Dead Code Cleanup

Delete immediately:
- `augur/chains/` — 6 files, dead per ADR-143
- `augur/_dev/` — 5 dirs, zero code references
- `augur/data-template/` — 1 dir, unused
- `augur/hooks/` — orphaned, never integrated
- `src/lib/plugins/` — 612KB stale mounts
- Fix `src/mcp/augur_mcp/compat.py:262` broken import

## Cross-Cutting Concerns

### C1: SKILL.md Workflow Migration

SKILL.md workflow definitions that users evolve:
- Default workflows ship in `assets/`
- User-evolved workflows live in vault at `~/Vault/Augur/{bundle}/{skill}/workflows/`
- Lookup: vault overrides asset defaults

### C2: Self-Heal and Daemon Impact

Critical path — daemon is the heartbeat. Both systems deeply reference current paths:
- `unified_daemon.py` reads `runtime/daemon/`, `runtime/logs/`, `runtime/adaptive/`
- `ai_self_healer.py` reads `augur/config/self_heal.yaml`, writes `runtime/self_heal/`
- `service_healer.py` generates plists inline, reads `runtime/daemon.pid`
- Phase 5 must include full daemon lifecycle verification

### C3: Settings Dashboard — Storage Block

Dashboard `/settings` should show all storage locations with: path, size, last modified, "Open in Finder" button.

### C4: Documentation Refresh (Per Phase)

Each phase MUST update before completion:
- `docs/agent-topics/ARCHITECTURE.md`, `SKILLS.md`, `DEBUGGING.md`, `WORKFLOWS.md`, `CONTEXT.md`
- `CLAUDE.md` critical rules and directory layout
- Skill-specific docs affected by the phase

### C5: AI Bridge Sync Updates (Per Phase)

Each phase MUST update:
- `sync_agents.py` path scanning and config generation
- All IDE adapter configs (Claude, Codex, Cursor, Windsurf)
- Agent instruction templates referencing file paths
- Regenerate and verify all agent configs

## Implementation Phases

### Phase 1: Dead Code Cleanup

**Scope**: Delete dead artifacts, fix broken import. Zero risk.

| # | Task | Files |
|---|---|---|
| 1 | Delete `augur/chains/` from all skills | 6 chain YAML files across 4 skills |
| 2 | Delete `augur/_dev/` from all skills | 5 dirs (advisor, devops, validator, frontend, organizer) |
| 3 | Delete `augur/data-template/` | organizer skill only |
| 4 | Delete `augur/hooks/` | ai_bridge skill only |
| 5 | Delete `src/lib/plugins/` | Stale mounted copies (612KB) |
| 6 | Fix `compat.py:262` import | `src/mcp/augur_mcp/compat.py` |
| 7 | Clean recursive backup nesting | `runtime/backups/manual-*/runtime/backups/...` |
| 8 | Remove chain refs from sync/lint | `sync_agents/templates.py`, `plugin-lint.py` |

**Testing**:
- `npm run build` succeeds
- `python -m augur_mcp` starts
- All existing tests pass
- `plugin-lint.py` runs clean

**Docs**: Update ARCHITECTURE.md (remove chains/hooks), SKILLS.md (expected structure)
**AI Bridge**: Update `sync_agents.py` to stop scanning for chains

---

### Phase 2: Skill Standardization

**Scope**: Restructure 130 skills so `rm -rf augur/` yields a pure standard skill.

| # | Task | Scope |
|---|---|---|
| 1 | Move `augur.yaml` → `augur/augur.yaml` | All skills |
| 2 | Move `README.md` → `augur/README.md` | All skills |
| 3 | Move `tests/` → `augur/tests/` | All skills with tests |
| 4 | Move `modules/` → `augur/modules/` | 24 skills |
| 5 | Move `augur/mcp/` → `scripts/mcp/` | 43 skills |
| 6 | Create `references/` with context docs | Where applicable |
| 7 | Create `assets/` with defaults from `augur/data/` | Actions, prompts, blocks, seed |
| 8 | Update `mount-plugins.ts` | New `augur/` paths |
| 9 | Update `discovery.py` | Read `augur/augur.yaml` |
| 10 | Update `generate-skill.py` | New structure |
| 11 | Update MCP tool discovery | Scan `scripts/mcp/` |
| 12 | Update `paths.py` | `get_skill_data_dir()` |

**Testing**:
- Dashboard builds, all pages render
- MCP server discovers all tools
- All plugin tests pass
- `auto-skill-md` validation passes
- Manual: `rm -rf augur/` on 3 skills → valid Claude Code skills

**Docs**: Rewrite ARCHITECTURE.md structure, SKILLS.md guide, CLAUDE.md mounting section
**AI Bridge**: Update `sync_agents.py` for new paths, regenerate all agent configs

---

### Phase 3: Central RAG

**Scope**: Move RAG from per-skill to centralized infrastructure.

| # | Task | Files |
|---|---|---|
| 1 | Add `get_rag_dir()` to paths.py | Platform-aware (macOS/Linux) |
| 2 | Create `~/Library/Application Support/Augur/rag/` | Directory structure |
| 3 | Update `rag_indexer.py` | Write to central location |
| 4 | Update `symbol_extractor.py` | Write symbols centrally |
| 5 | Update `rag_tools.py` | Read from central location |
| 6 | Update `bulk_index.py` | Central index path |
| 7 | Delete all `augur/rag/` from skills | 30 skills |
| 8 | Delete all `symbols.yaml` from skills | 448 files |
| 9 | Add reindex on skill install/uninstall | Install/uninstall flow |
| 10 | Update `auto-rag-reindex` | Central path |

**Testing**:
- `/search` and `/ask` return cross-skill results
- `auto-rag-reindex` completes
- Install test skill → indexed; uninstall → pruned
- No `augur/rag/` or `symbols.yaml` remain in plugins/

**Docs**: Update ARCHITECTURE.md data separation, add RAG infrastructure section
**AI Bridge**: Update agent configs with central RAG path

---

### Phase 4: User Data Vault

**Scope**: Move user data from plugins to external vault.

| # | Task | Scope |
|---|---|---|
| 1 | Add `get_vault_dir()`, `get_skill_vault_dir()` | paths.py |
| 2 | Vault scaffolding on first run | Bundle directories |
| 3 | Migrate `augur/data/{user content}` → vault | ~80 skills |
| 4 | Migrate actions/prompts → vault (user copies) | Keep assets/ defaults |
| 5 | Vault-first lookup with assets/ fallback | Path resolution |
| 6 | Update seed system: install → copy assets/ to vault | Seed flow |
| 7 | Migrate `docs/memory/` → `~/Vault/Augur/memory/` | Memory system |
| 8 | Create `~/Vault/Augur/dashboards/` | User custom views |
| 9 | Update all MCP tools for vault paths | Data read/write |
| 10 | Update all API routes for vault paths | Data serving |
| 11 | Migrate SKILL.md workflow data → vault | Workflow skills |

**Testing**:
- Dashboard pages load data from vault
- Create note via MCP → appears in vault
- Edit vault file in external editor → dashboard reflects
- Install skill → vault scaffolded with defaults
- `/ask` and `/search` find vault content
- Memory sync to AI clients works from vault

**Docs**: Rewrite ARCHITECTURE.md data separation, add vault setup guide, update SKILLS.md, WORKFLOWS.md
**AI Bridge**: Update `sync_agents.py` memory source, agent configs with vault paths, regenerate all

---

### Phase 5: macOS Runtime

**Scope**: Move runtime to macOS standard locations. Critical path — daemon impact.

| # | Task | Files |
|---|---|---|
| 1 | Add platform-aware runtime paths | `get_logs_dir()`, `get_state_dir()`, `get_cache_dir()` |
| 2 | Store plist templates in daemon | `assets/plists/com.augur.*.plist.tmpl` |
| 3 | Update `service_healer.py` | Render from templates |
| 4 | Update `setup_wizard.py` | Install from template source |
| 5 | Migrate daemon state | `runtime/daemon/` → `~/Library/App Support/Augur/state/daemon/` |
| 6 | Migrate logs | `runtime/logs/` → `~/Library/Logs/Augur/` |
| 7 | Migrate caches | → `~/Library/Caches/Augur/` |
| 8 | Update `unified_daemon.py` | New runtime paths |
| 9 | Update `ai_self_healer.py` | New runtime paths |
| 10 | Update `nightly_maintainer.py` | New log paths |
| 11 | Update dashboard API routes | Runtime path references |
| 12 | Add storage visualization block | `/settings` page |

**Testing**:
- Daemon starts, writes logs to `~/Library/Logs/Augur/`
- Console.app shows Augur logs
- Dashboard starts from LaunchAgent
- `service_healer.py heal` works with templates
- Fresh install from clean state works
- Time Machine excludes `~/Library/Caches/Augur/`
- Full daemon lifecycle: start → heal → stop → restart

**Docs**: Rewrite ARCHITECTURE.md runtime, DEBUGGING.md log locations, daemon SKILL.md, add macOS paths reference
**AI Bridge**: Update agent configs with runtime/log paths

---

### Phase 6: Binary Documents

**Scope**: Move binary media to ~/Documents/Augur/. Smallest phase.

| # | Task | Scope |
|---|---|---|
| 1 | Add `get_documents_dir()`, `get_skill_documents_dir()` | paths.py |
| 2 | Migrate binary assets → Documents | 8 skills |
| 3 | Update RAG indexer for external docs | Index ~/Documents/Augur/ |
| 4 | Update MCP tools serving binaries | Binary file paths |
| 5 | Update API routes serving binaries | Binary content |

**Testing**:
- Binary files accessible from dashboard
- RAG indexes Documents content
- iCloud sync picks up ~/Documents/Augur/
- New binary output goes to Documents

**Docs**: Update ARCHITECTURE.md with Documents layer, user guide file locations
**AI Bridge**: Update agent configs for binary content paths

### Phase 7: Adaptive Loop Enforcement

**Scope**: Add auto-commands to the adaptive loop engine that continuously validate and enforce the new folder structure. Prevents drift back to old patterns.

| # | Task | Scope |
|---|---|---|
| 1 | Create `auto-folder-structure` (tier 0) | Scan all skills: no user data in `augur/data/`, no `augur/rag/`, no `symbols.yaml`, no `augur/chains/`, no `augur/_dev/`. Flag violations. |
| 2 | Create `auto-skill-compliance` (tier 1) | Verify `rm -rf augur/` rule: SKILL.md exists at root, scripts/ has mcp/ if skill has MCP tools, assets/ has defaults if vault has user copies. Flag non-standard files at skill root. |
| 3 | Create `auto-vault-integrity` (tier 2) | Verify vault scaffolding: every installed skill has its vault directory, vault actions/prompts match or extend asset defaults, no orphan vault dirs for uninstalled skills. |
| 4 | Create `auto-runtime-paths` (tier 1) | Verify no code references old `runtime/` paths directly, all path resolution goes through `paths.py` functions, no hardcoded `~/Library/` paths. |
| 5 | Register loop in `adaptive_loops.yaml` | New `folder-structure` category with budget 10, trigger `nightly` |
| 6 | Register commands in daemon `augur.yaml` | 4 auto-commands with progressive tiers |
| 7 | Update `auto-skill-refs` (ADR-238) | Extend existing skill refs validation to check new structure (scripts/mcp/, assets/, references/) |

**Testing**:
- Introduce a deliberate violation (e.g., create `augur/data/test-note.md` in a skill) → auto-folder-structure detects it
- Run all 4 auto-commands in dry-run mode → no false positives on current (post-migration) state
- Adaptive engine schedules and executes the loop on nightly trigger
- `auto-skill-compliance` correctly passes a skill after `rm -rf augur/` and fails when non-standard files exist at root

**Docs**: Update WORKFLOWS.md with new auto-commands, update adaptive loops documentation
**AI Bridge**: Update agent configs with new auto-command references

---

## End State

### Skill Folder

```
plugins/{bundle}/skills/{skill}/
├── SKILL.md                    ← standard
├── scripts/                    ← standard (includes mcp/)
├── references/                 ← standard
├── examples/                   ← standard
├── assets/                     ← standard (default templates)
│
└── augur/                      ← platform wiring only
    ├── augur.yaml
    ├── README.md
    ├── api/                    ← Next.js routes (mounted)
    ├── dashboard/              ← React TSX (mounted)
    ├── lib/                    ← TS+Python utilities
    ├── config/                 ← system configs
    ├── adapters/               ← IDE adapters (ai_bridge)
    ├── tests/
    └── modules/
```

### External Locations

```
~/Vault/Augur/                          ← user data (Obsidian-browseable)
├── {bundle}/{skill}/                   ← per-skill user data
│   ├── actions/                        ← evolved workflows
│   ├── prompts/                        ← evolved prompts
│   └── {domain}/                       ← notes, jobs, profiles
├── memory/                             ← MEMORY.md, daily logs
└── dashboards/                         ← user custom views

~/Documents/Augur/                      ← binary media (iCloud/Drive synced)
└── {bundle}/{skill}/

~/Library/Application Support/Augur/    ← persistent state + RAG
├── rag/                                ← central RAG index
└── state/                              ← daemon, sessions, adaptive

~/Library/Logs/Augur/                   ← Console.app visible
~/Library/Caches/Augur/                 ← auto-purged by macOS
~/Library/LaunchAgents/com.augur.*.plist ← daemon services
```

### paths.py Changes

```python
# New
get_vault_dir()                 # ~/Vault/Augur/
get_skill_vault_dir(skill)      # ~/Vault/Augur/{bundle}/{skill}/
get_rag_dir()                   # ~/Library/Application Support/Augur/rag/
get_state_dir()                 # ~/Library/Application Support/Augur/state/
get_documents_dir()             # ~/Documents/Augur/
get_skill_documents_dir(skill)  # ~/Documents/Augur/{bundle}/{skill}/

# Updated
get_logs_dir()                  # ~/Library/Logs/Augur/ (was runtime/logs/)
get_cache_dir()                 # ~/Library/Caches/Augur/ (was runtime/cache/)
get_skill_data_dir(skill)       # ~/Vault/Augur/{bundle}/{skill}/ (was augur/data/)
get_memory_dir()                # ~/Vault/Augur/memory/ (was docs/memory/)

# Platform
_is_macos()                     # True on Darwin
_xdg_fallback(name)             # ~/.local/share/augur/{name} on Linux
```

## Consequences

### Positive
- Skills become 100% Claude Code standard-compliant (`rm -rf augur/` = pure skill)
- User data browseable in Obsidian, editable with any markdown editor
- Cross-skill RAG search zero-cost (single centralized index)
- macOS manages runtime (auto-purge caches, Console.app logs, Time Machine skips caches)
- Clean layer separation: code / data / binaries / indexes / runtime
- Plist templates in source enable clean fresh installs
- Each phase independently shippable and testable

### Negative
- Large migration across 130 skills (mitigated by phased approach)
- Dual-path lookup (vault → assets fallback) adds complexity
- External dependency on vault location existing
- paths.py grows with platform detection

### Risks
- Breaking existing workflows during migration (mitigated by per-phase testing)
- AI bridge sync missing a path update → agents read stale data (mitigated by mandatory sync update per phase)
- User confusion about where files live (mitigated by C3 storage block and documentation)
- Daemon breakage in Phase 5 (mitigated by full lifecycle testing)

## References

- [Claude Code Skills Spec](https://code.claude.com/docs/en/skills)
- [Agent Skills Open Standard](https://agentskills.io)
- Design doc: `docs/superpowers/specs/2026-03-10-folder-restructure-design.md`
- ADR-083: Plugin Data Colocation (superseded by D3)
- ADR-143: Chains Removal
- ADR-163: Config Decentralization
- ADR-238: Skill Standards Loop
