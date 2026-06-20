# MCP-Based Skill Sync

**Date**: 2026-03-20
**Status**: Draft
**Scope**: Replace file-copy adapter pattern in sync_agents with MCP-based skill distribution

## Problem

The current `sync_agents` system distributes skills across 11 AI coding clients using per-client adapter classes. Each adapter (ClaudeCodeAdapter, GeminiAdapter, CodexAdapter, etc.) implements `sync_skill()` to read a master SKILL.md, reformat it for the target client, and write an adapted copy.

Three problems:

1. **Maintenance burden**: 11 adapter classes (~1500 lines total), each with format-specific copy logic. Adding a new client means writing another 100-300 line adapter.

2. **Incomplete distribution**: Only SKILL.md gets copied. Commands, scripts, references, and modules stay in the master directory. Non-master clients can't access them.

3. **Broken cross-client access**: The MCP skill registry deduplicates by skill ID using last-scanned-wins. When an adapted copy is scanned after the master, the registry points to the adapted directory — which has no scripts/, references/, or modules/. MCP tools like `load-module`, `load-reference`, and `skill-action` silently fail.

## Research Findings

All 11 supported clients have:
- **Native file-based discovery**: Each client scans a specific directory at session start
- **MCP support**: All clients can connect to the Augur MCP server

No client can discover skills purely via MCP — all require local files on disk for their native scanner. However, the local file only needs to contain enough metadata for discovery (name, description, triggers). Full skill content can be served via MCP.

### Client Discovery Mechanisms

| Client | Scans | Format | Discovery |
|--------|-------|--------|-----------|
| Claude Code | `.claude/skills/*/SKILL.md` | MD + frontmatter | Loads metadata immediately, body on trigger |
| Claude Desktop | `CLAUDE.md` | Plain MD | Context injection only |
| Gemini CLI | `.gemini/skills/*/SKILL.md` | MD + frontmatter | Injects name+description into system prompt, `activate_skill` loads body |
| Codex | `~/.codex/prompts/*.md` + `AGENTS.md` | Plain MD | Loads into developer message |
| Cursor | `.cursor/rules/*.mdc` | MDC + frontmatter (`globs`, `alwaysApply`, `description`) | Auto-attached by pattern, agent-requested by description |
| Windsurf | `.windsurf/rules/` + `.windsurfrules` | MD | Scans workspace + parent dirs (global rules, not per-skill) |
| Cline | `.clinerules/*.md` + `.claude/skills/` | MD + conditional frontmatter | Shares Claude Code skill files; `.clinerules/` is for rules only |
| Copilot | `.github/instructions/*.instructions.md` | MD + `applyTo` frontmatter | Auto-loads, pattern-matched |
| Kimi | `AGENTS.md` | Plain MD | Context injection only |
| OpenCode | `.opencode/AGENTS.md` | Plain MD | Context injection only |
| Antigravity | `.antigravity/instructions.md` | Plain MD | Context injection only |

## Design

### Change 1: Master-Aware Registry Deduplication

**Files**: `src/mcp/augur_mcp/adapters/filesystem_registry.py` AND `src/mcp/augur_mcp/core/skills.py`

Both files have independent last-scanned-wins deduplication. Both must be fixed.

When deduplicating skills by ID during registry scan, detect adapted copies and exclude them.

```python
# Before (broken): last-scanned wins
skills_dict[skill.id] = skill

# After: reject adapted copies entirely
if _is_adapted_copy(skill):
    continue  # skip — master is the only entry
if skill.id in skills_dict:
    existing = skills_dict[skill.id]
    if _is_adapted_copy(existing):
        skills_dict[skill.id] = skill  # replace stale adapted entry
    # else: keep existing master (first master wins)
else:
    skills_dict[skill.id] = skill
```

**Adapted copy detection** (`_is_adapted_copy()`):
- Read the first 500 bytes of the SKILL.md file
- Check if `AUGUR-ADAPTED-COPY` appears anywhere in that window — definitive signal (existing marker)
- OR if `AUGUR-STUB` appears anywhere in that window — new stub format

Uses `in` (substring search), not `startswith`, because stubs begin with `---` YAML frontmatter and the marker comment appears after the closing `---`. This matches the approach already used by `_is_auto_generated()` in `src/plugins/skill_registry.py`.

This detection only applies to subdirectory-layout clients (Claude Code, Gemini) where `SKILL.md` files exist in the scan path. Flat-file clients (Cursor, Codex, Copilot) write stubs as standalone files (e.g., `.cursor/rules/{skill_id}.mdc`) that are not discovered by `filesystem_registry.py`'s `_iter_skill_dirs` scanner (which only yields directories containing `SKILL.md`).

**Dedup sites** — three locations need the adapted-copy exclusion:
1. `filesystem_registry.py._scan_skills()` — primary registry scan
2. `skills.py.list_skills_impl()` — secondary dedup loop (defensive; receives already-filtered output from registry, but guards against partial-fix scenarios)
3. `src/plugins/skill_registry.py._is_auto_generated()` — already detects `AUGUR-ADAPTED-COPY`; must also detect `AUGUR-STUB` (add to the marker list)

Note: `find_skill_impl()` is NOT an independent dedup site — it delegates to `registry_list_skills()` without its own dedup loop.

**Impact**: All MCP tools (`get-skill`, `load-module`, `load-reference`, `skill-action`) automatically resolve to the master directory. Cross-client resource access works.

### Change 2: Client Format Spec Table

Replace adapter `sync_skill()` methods with a declarative configuration table describing each client's local file requirements.

```yaml
client_formats:
  claude-code:
    path_base: project  # relative to project root
    skill_dir: ".claude/skills/{skill_id}"
    filename: "SKILL.md"
    frontmatter_fields: [name, description, x-augur-master, triggers]
    body: false

  gemini:
    path_base: project
    skill_dir: ".gemini/skills/{skill_id}"
    filename: "SKILL.md"
    frontmatter_fields: [name, description]
    body: false

  codex:
    path_base: home  # relative to ~ (resolved via CODEX_HOME or ~/.codex)
    skill_dir: "prompts"
    filename: "{skill_id}.md"
    frontmatter_fields: []
    body: true
    body_template: "codex_prompt"  # short summary template

  cursor:
    path_base: project
    skill_dir: ".cursor/rules"
    filename: "{skill_id}.mdc"
    frontmatter_fields: [description, globs, alwaysApply]
    frontmatter_map:
      description: "{skill.description}"
      globs: ""
      alwaysApply: false
    body: false

  copilot:
    path_base: project
    skill_dir: ".github/instructions"
    filename: "{skill_id}.instructions.md"
    frontmatter_fields: [applyTo]
    frontmatter_map:
      applyTo: "**/*"
    body: false

  # --- MCP-only clients (no per-skill stubs) ---

  cline:
    skill_dir: null  # shares .claude/skills/ with Claude Code

  claude-desktop:
    skill_dir: null  # context via CLAUDE.md only

  windsurf:
    skill_dir: null  # .windsurf/rules/ is for global rules, not per-skill stubs

  kimi:
    skill_dir: null  # context via AGENTS.md only

  opencode:
    skill_dir: null  # context via AGENTS.md only

  antigravity:
    skill_dir: null  # context via instructions.md only
```

**Key decisions**:
- `path_base: home` vs `project` — Codex writes to `~/.codex/prompts/`, not project-relative. The sync script resolves the base path accordingly.
- Cline set to `null` — it shares `.claude/skills/` with Claude Code (confirmed in adapter code). No separate stubs needed.
- Windsurf set to `null` — `.windsurf/rules/` is for global rules (`augur.md`), not per-skill files. Generating stubs there would inject every skill into every session.
- Claude Desktop added as `null` — no project-scoped skill discovery.
- `triggers` field (not `x-augur-triggers`) — matches the existing field name the registry reads from via `frontmatter.get("triggers")`.

**Example generated stub** (Claude Code):
```markdown
---
name: apple
description: "Unified Apple platform integration"
x-augur-master: claude-code
triggers: [apple, notes, reminders, calendar]
---
<!-- AUGUR-STUB — full content via MCP get-skill -->
```

### Change 3: `render-skill-file` MCP Tool

New MCP tool that generates a client-formatted stub file for native discovery.

**Input**: `skill_id`, `client_id`
**Output**: `{path, content, path_base}` — the target path, file content, and whether path is project-relative or home-relative

Logic:
1. Look up skill from registry (always resolves to master)
2. Look up client format spec from table
3. If `skill_dir` is null, return `{skip: true}`
4. Build frontmatter per client's schema
5. For `body: false` clients, body is `<!-- AUGUR-STUB — full content via MCP get-skill -->`
6. For `body: true` clients (Codex), render a short summary template
7. Return path + content + path_base

Companion `render-all-skill-files(client_id)` returns all stubs for a client in one call.

**What this replaces**:

| Before | After |
|--------|-------|
| `ClaudeCodeAdapter.sync_skill()` | `render-skill-file(skill, "claude-code")` |
| `GeminiAdapter.sync_skill()` | `render-skill-file(skill, "gemini")` |
| `CodexAdapter.sync_skill()` | `render-skill-file(skill, "codex")` |
| `CursorAdapter.sync_skill()` | `render-skill-file(skill, "cursor")` |
| `CopilotAdapter.sync_skill()` | `render-skill-file(skill, "copilot")` |
| 6 more null-dir clients | `render-skill-file` returns `{skip: true}` |

**What the tool does NOT handle** (stays in existing adapters):
- Global rules sync (`sync_rules()`) — CLAUDE.md, GEMINI.md, .cursorrules etc.
- MCP config generation (`generate_mcp_config()`) — .claude/mcp.json, .gemini/settings.json etc.
- Memory sync (`sync_memory()`) — distributing memory files
- Gemini `.gemini/unignore` file — generated by `generate_mcp_config()`, stays as-is

### Change 4: Thin Sync Script

Replace the skill-sync portion of `sync_agents` engine with a script that calls MCP tools and writes files.

```python
def sync_skills_for_client(mcp_client, client_id: str, project_root: Path):
    """Sync all skill stubs for one client."""
    fmt = CLIENT_FORMATS[client_id]
    if not fmt.skill_dir:
        return  # MCP-only client

    # 1. Get all rendered stubs in one MCP call
    results = mcp_client.call("render-all-skill-files", client_id=client_id)

    # 2. Resolve base path
    if fmt.path_base == "home":
        base = get_client_config_dir(client_id, scope='global')  # e.g. ~/.codex
    else:
        base = project_root

    # 3. Write stubs and track paths
    written_paths = set()
    for result in results:
        target = base / result["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(result["content"])
        written_paths.add(target)

    # 4. Clean up orphan stubs
    cleanup_orphans(fmt, base, written_paths)

    # 5. Invalidate MCP registry cache so new stubs are visible
    mcp_client.call("invalidate-cache")


def cleanup_orphans(fmt, base: Path, written_paths: set[Path]):
    """Remove stubs for skills that no longer exist."""
    skill_dir = base / fmt.skill_dir_root  # e.g. ".claude/skills" or ".cursor/rules"
    if not skill_dir.exists():
        return

    if fmt.has_subdirs:
        # Claude Code, Gemini: .claude/skills/{skill_id}/SKILL.md
        # Delete entire skill subdirectory if not in written_paths
        for subdir in skill_dir.iterdir():
            if subdir.is_dir():
                stub_file = subdir / fmt.filename
                if stub_file not in written_paths:
                    shutil.rmtree(subdir)
    else:
        # Cursor, Codex, Copilot: flat directory with per-skill files
        # Only delete files that contain the AUGUR-STUB marker to avoid
        # deleting user-authored files (e.g., custom .cursor/rules/*.mdc)
        for f in skill_dir.iterdir():
            if f.is_file() and f not in written_paths:
                header = f.read_text()[:500]
                if "AUGUR-STUB" in header or "AUGUR-ADAPTED-COPY" in header:
                    f.unlink()


def sync_all_clients(mcp_client, project_root: Path):
    """Sync skill stubs for all installed clients."""
    for client_id in CLIENT_FORMATS:
        if not is_client_installed(client_id):
            continue
        sync_skills_for_client(mcp_client, client_id, project_root)
```

**Integration with existing sync_agents**: The adapter classes remain for `sync_rules()`, `generate_mcp_config()`, `sync_memory()`, and `detect_installed()`. Only `sync_skill()` is removed from each adapter. The `engine.py` orchestrator calls `sync_all_clients()` instead of iterating adapters for skill sync, but still iterates adapters for rules/config/memory sync.

**Invocation**: Same triggers as today — nightly daemon, `/sync-agents`, manual.

**Cache invalidation**: After writing stubs, call `invalidate-cache` on the MCP server so the registry re-scans and excludes the new stubs (which have `AUGUR-STUB` markers). This is critical for long-lived daemon processes.

### What Stays Unchanged

- **Rules sync** (`sync_rules()`): CLAUDE.md, GEMINI.md, .cursorrules etc. — these are global instruction files, not skills
- **MCP config sync** (`generate_mcp_config()`): .claude/mcp.json, .gemini/settings.json etc.
- **Memory sync** (`sync_memory()`): Distributing memory files to client directories
- **Client detection** (`detect_installed()`): Checking which clients are present
- **Adapter classes**: Retained for rules/config/memory sync — only `sync_skill()` method removed from each
- **Gemini `.gemini/unignore`**: Generated by `generate_mcp_config()`, unaffected

### What Gets Deleted

From each adapter class (`adapters/*.py`):
- `sync_skill()` method (or `BaseAdapter.sync_skill()` default if no override exists — verify per adapter before deleting)

From `engine.py`:
- `sync_single_skill()` orchestration
- `_fix_adapted_copy_freshness()` — stubs are cheap to regenerate, no freshness tracking needed
- Format transformation logic

### Dependencies and Prerequisites

- **`using-superpowers` skill**: When Claude Code triggers a stub skill, the LLM sees `<!-- AUGUR-STUB — full content via MCP get-skill -->` as the body. The LLM must know to call `get-skill` via MCP to load the full content. This works because `using-superpowers` instructs the LLM to invoke skills via the `Skill` tool. If `using-superpowers` is not loaded (e.g., non-Augur Claude Code session), the stub body is unhelpful. This is acceptable — non-Augur sessions don't have MCP access either.

## Migration Path

All changes land atomically in one commit to avoid intermediate broken states:

1. Fix registry deduplication in all three sites: `filesystem_registry.py`, `skills.py`, and add `AUGUR-STUB` to `src/plugins/skill_registry.py._is_auto_generated()` (Change 1)
2. Add client format spec table (Change 2)
3. Add `render-skill-file` and `render-all-skill-files` MCP tools (Change 3)
4. Add thin sync script with orphan cleanup and cache invalidation (Change 4)
5. Replace `sync_single_skill()` calls in engine.py with `sync_all_clients()`
6. Remove `sync_skill()` methods from adapter classes
7. Remove `_fix_adapted_copy_freshness()` from engine.py
8. Update tests: validate stubs instead of full adapted copies, verify cross-client resource access
9. Run `/sync-agents` to regenerate all stubs
10. Verify each client discovers skills correctly

## Risks

- **Codex prompt format**: Codex loads prompts as plain text without MCP trigger flow. The `body_template` needs to produce a useful summary, not just a stub marker. May need iteration on template content.
- **Cursor .mdc format**: Cursor uses a non-standard format with specific frontmatter semantics. Need to verify the generated .mdc files are parsed correctly by Cursor's scanner.
- **Stub body in Claude Code**: When the LLM sees the stub body on skill trigger, it must call `get-skill` via MCP. This relies on `using-superpowers` being loaded. Validated as acceptable since non-Augur sessions lack MCP access anyway.
- **Atomic migration**: Changes 1-7 must land together. Partial application (e.g., dedup fix without stub generation) could cause the registry to find no entry for skills that only exist as adapted copies.
