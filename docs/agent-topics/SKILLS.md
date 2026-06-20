<!--
⚠️  AUTO-GENERATED FILE - DO NOT EDIT DIRECTLY
Source: docs/agent-topics/SKILLS.md
Generator: project-brain/capabilities/skills/ai/scripts/sync_agents/__init__.py
-->
# Skills

> **When to load**: Load this doc when working on a specific skill, creating new skills, or managing plugin dependencies.

See also [architecture-skills.md](../architecture-skills.md) for the contributor-facing skill distribution architecture.

## Available Skills

| Skill | Hub | Path |
|---|---|---|
| channels | admin | `project-brain/capabilities/skills/channels` |
| renderer | admin | `project-brain/capabilities/skills/renderer` |
| settings | admin | `project-brain/capabilities/skills/settings` |
| system-cleanup | admin | `project-brain/capabilities/skills/system-cleanup` |
| updater | admin | `project-brain/capabilities/skills/updater` |
| ai_bridge | ai | `project-brain/capabilities/skills/ai_bridge` |
| knowledge | ai | `project-brain/capabilities/skills/knowledge` |
| install | ai | `project-brain/capabilities/skills/install` |
| scraper | ai | `project-brain/capabilities/skills/scraper` |
| career | career | `project-brain/capabilities/skills/career` |
| content | career | `project-brain/capabilities/skills/content` |
| growth | career | `project-brain/capabilities/skills/growth` |
| linkedin-writer | career | `project-brain/capabilities/skills/linkedin-writer` |
| advisor | dev | `project-brain/capabilities/skills/advisor` |
| developer | dev | `project-brain/capabilities/skills/developer` |
| devops | dev | `project-brain/capabilities/skills/platform-admin` |
| dashboard | dev | `apps/dashboard/features` |
| validator | dev | `project-brain/capabilities/skills/validator` |
| finance | finance | `project-brain/capabilities/skills/finance` |
| health | health | `project-brain/capabilities/skills/health` |
| home-automation | home | `project-brain/capabilities/skills/home-automation` |
| lifestyle | lifestyle | `project-brain/capabilities/skills/lifestyle` |
| daemon | observability | `project-brain/capabilities/skills/daemon` |
| metrics | observability | `project-brain/capabilities/skills/metrics` |
| observe | observability | `project-brain/capabilities/skills/observe` |
| router | orchestration | `project-brain/capabilities/skills/router` |
| swarm | orchestration | `project-brain/capabilities/skills/swarm` |
| apple | productivity | `project-brain/capabilities/skills/apple` |
| eisenhower | productivity | `project-brain/capabilities/skills/eisenhower` |
| google-workspace | productivity | `project-brain/capabilities/skills/google-workspace` |
| organizer | productivity | `project-brain/capabilities/skills/organizer` |
| project-dev | professional | `project-brain/capabilities/skills/project-dev` |
| venture | professional | `project-brain/capabilities/skills/venture` |

## Ownership Model

Skill lifecycle is ownership-first:

- `augur` — canonical shared skill content lives in `project-brain/capabilities/skills/` and Augur owns it
- `external` — discovered outside managed shared/private skill roots and shown for awareness only
- `adopted` — canonical skill content lives in `project-brain/capabilities/skills/`, but preserves structured `upstream` metadata from the original external source

Client folders are not ownership states. Augur-managed exports are generated only for enabled clients and are repo-scoped by default.

## Skill Directory Structure

Every skill follows this layout. The `augur/` subfolder is the skill's Augur integration root — config, dashboard, API routes, and tests all live inside it.

```
project-brain/capabilities/skills/{skill}/
├── SKILL.md                    # User-facing documentation (skill root)
├── assets/                     # Static assets (images, templates)
├── scripts/                    # Python scripts (MCP tools, automation)
│   └── mcp/
│       └── __init__.py         # MCP tool implementations
└── augur/                      # Augur integration root
    ├── version.yaml            # Skill version tracking
    ├── README.md               # Auto-generated from SKILL.md
    ├── api/                    # Next.js API routes (mounted to dashboard)
    │   └── {resource}/
    │       └── route.ts
    ├── dashboard/              # Dashboard UI components (mounted to dashboard)
    │   ├── page.tsx            # Hub main page
    │   ├── tabs/               # Tab components
    │   └── components/         # Shared components
    └── tests/                  # Tests for this skill
        └── test_*.py
```

**CRITICAL**: Skill metadata lives in `SKILL.md` frontmatter (ADR-430). `augur.yaml` is fully retired. New or actively touched skills use standard Agent Skills fields first, with Augur-specific routing in one `x-augur:` block. Legacy top-level `x-augur-*` fields remain readable during migration. Dashboard pages, API routes, and config must be inside the `augur/` subfolder. Only `SKILL.md`, `assets/`, and `scripts/` live at the skill root level.

**CRITICAL**: Vault notes written by skills use ADR-571 vault frontmatter conventions, not SKILL.md conventions. User-facing fields stay plain; Augur-managed system fields use leading `_` keys and must be written through `merge_system_user()`. Do not apply vault-note frontmatter migrations to `SKILL.md`, `config.yaml`, ADRs, generated agent markdown, or dashboard manifests.

**CRITICAL**: Vault-note relationships are discovered dynamically from any frontmatter value containing `[[wikilinks]]`. Do not register or hardcode relationship field names such as `related`, `topics`, or `mentors`; use `extract_relationships()` / `RelationshipIndex` so new user-authored relationship fields work without code changes.

### Typed knowledge graph (ADR-738)

The `graph/` skill (`project-brain/capabilities/skills/graph/`, hub `brain`) owns a deterministic, zero-LLM typed-edge layer that **augments — never replaces** the untyped `RelationshipIndex` above; both coexist.

- **Edges are per-type underscore-prefixed frontmatter link lists** — `_cites:`, `_mentions:`, `_depends_on:`, etc., each holding `[[wikilinks]]`. They are system-managed per ADR-571 but written **additively** (`edge_writer.merge`): a user-added edge is never clobbered. Obsidian's graph view renders them like any other link list.
- **Extraction is deterministic** — a rule engine (`config/system/graph_edges.yaml`) maps frontmatter keys, caller-supplied concepts, and body `[[wikilinks]]` to typed edges. No model calls, ever. The config fails closed to a `mentions`-only ruleset.
- **Five write paths emit edges at write time** — `/keep` (`source_cards.py`, `url_ingest.py`), `/wiki` (`wiki_concept_pages.py`), `/ask` retention (`ask_retention.py` — daily log + synthesis notes), `/save` (agent calls the `graph-extract` MCP tool after a `.md` save), and `/profile` (`tools_memory_profile.py`). Every call site is best-effort: `graph_ops.index_page` never raises, so the graph can never break a write.
- **`_entity_tier` (1–3)** is computed deterministically from inbound-edge count + source-type diversity. It is **distinct** from `wiki_tier.py`'s signal-source tiers — different concept, different field.
- A rebuildable JSONL cache lives under `get_cache_dir()/graph/`; `aug graph rebuild` backfills the whole vault. Deleting the cache loses nothing — it is derived from frontmatter.

The legacy `knowledge-graph` MCP tool is deprecated in favor of `graph-stats`.

**CRITICAL**: Custom dashboard page TSX files go in `apps/dashboard/features/pages/{hub}/{page}/page.tsx`, NOT in `project-brain/capabilities/skills/*/augur/dashboard/`. The catch-all registry only includes pages from `features/pages/`. Pages in `project-brain/capabilities/skills/augur/dashboard/` create orphan tabs that crash the build.

**Naming**: Avoid naming a skill the same as its group/workspace segment (e.g., skill "career" under path "career") — this causes route path doubling. Use the `x-augur:` block for Augur routing metadata (`hub`, `type`, `release`, `tools`, etc.).

### Minimal Augur Extension

New or actively touched skills should use standard Agent Skills fields first:
`name`, `description`, concise body instructions, and standard directories such
as `commands/`, `references/`, `scripts/`, `assets/`, `examples/`, `evals/`,
and `modules/`.

Augur-specific routing belongs in one `x-augur:` block:

```yaml
x-augur:
  hub: brain
  type: domain
  release: mvp
  tools:
    - name: memory-search
      surface: mcp
    - name: knowledge-project-index-rebuild
      surface: cli
```

Legacy top-level `x-augur-*` fields remain readable during migration, but new
metadata should not add more scattered proprietary fields.

## Adding a New Skill

1. Read existing skill as template: `cat project-brain/capabilities/skills/{skill}/SKILL.md`
2. Create skill directory structure (see layout above)
3. Write SKILL.md (<100 lines)
4. Add standard `name` and `description` fields, then put Augur routing in the `x-augur:` block (hub, type, release, tools, commands, etc.)
5. Add data directory in `project-brain/capabilities/skills/{skill}/data/` if needed
6. Register in relevant dashboard hub
7. **If skill needs Python dependencies**: Create `requirements.txt` in skill folder (see below)

## Adding a New Tool (CLI default; opt-in to MCP)

Per `docs/references/surface-decision-matrix.md`, new tools default to **CLI-only**. They become reachable through `aug <tool-name>` in shell or via Bash. They do NOT surface to AI clients (Claude/Codex/Gemini) until you opt in via the policy.

1. Implement the tool as a `@mcp.tool` decorated function in `project-brain/capabilities/skills/{skill}/scripts/mcp/<file>.py`. Keep it atomic (per `docs/references/agent-vs-mcp-checklist.md`) — one bounded operation, returns structured data, never orchestrates other tools.
2. Add the tool name and intended surface to the skill's `SKILL.md` frontmatter `x-augur.tools` list. Use `surface: cli`, `surface: mcp via dashboard`, or `surface: mcp`.
3. Add a policy entry to `config/system/capability_exposure.yaml`:

   ```yaml
   mcp-tool:{tool-name}:
     classification_status: approved
     description: "<one-line summary>"
     export_to:
     - cli
     - agents-md
     - browse
     management: generated
     owner_kind: augur
     preferred_client: shell
     primary_surface: cli   # default: CLI-only
     scope: project
   ```

4. **Opt-in to MCP exposure** by editing the policy entry per use case:
   - **Dashboard atomic op** (called from `useMcpQuery`/`useMcpMutation`): set `primary_surface: mcp via dashboard`, `preferred_client: dashboard`. Do NOT add `mcp` to `export_to`.
   - **Agent-callable** (slash-command body invokes it as MCP tool): add `mcp` to `export_to`, set `primary_surface: mcp`. The tool surfaces to all AI clients.

5. Re-run `scripts/mcp_surface_audit.py` to confirm the tool lands in the right bucket. Tools that aren't called from anywhere should not be on the AI-client surface.

**Why default to CLI-only?** Every MCP tool exposed to AI clients costs schema tokens in every session's system prompt. The `aug <tool>` shell path is free of that overhead. Default to it; promote to MCP only when the use case justifies it.

**Hub ID uniqueness**: Each `hub.id` in `dashboard.yaml` maps 1:1 to a plugin mount. Only ONE skill per hub may claim a given `hub.id`. If a sub-skill needs pages under an existing hub, place its dashboard files as a sub-route inside the primary skill's `dashboard/` directory and add its tab to the primary skill's `dashboard.yaml`. Do NOT create a separate `dashboard.yaml` with the same `hub.id` — mount-plugins uses `Map<hubId, Plugin>` and the last discovered skill silently overwrites the first.

## Plugin Dependency Management (ADR-018)

**CRITICAL**: Plugins must be self-contained. Never add plugin-specific dependencies to root `requirements.txt`.

```
# WRONG - adding plugin deps to root
Edit /requirements.txt  # Adding psutil for knowledge skill

# CORRECT - skill manages its own deps
Edit project-brain/capabilities/skills/knowledge/requirements.txt
```

**Core vs Plugin Dependencies**:
- **Core** (`requirements.txt`): Framework essentials only (mcp, pyyaml, pydantic, requests)
- **Plugin** (`project-brain/capabilities/skills/{skill}/requirements.txt`): Plugin-specific deps

**When creating a plugin with Python dependencies**:
```bash
# 1. Create requirements.txt in skill folder
project-brain/capabilities/skills/{skill}/requirements.txt

# 2. Document in SKILL.md installation section
## Installation
pip install -r project-brain/capabilities/skills/{skill}/requirements.txt

# 3. For complex plugins with entry points, use pyproject.toml instead
```

**Current plugins with dependencies**:
| Plugin | Deps File | Key Dependencies |
|--------|-----------|-----------------|
| knowledge | requirements.txt | psutil |
| validator | requirements.txt | playwright |

## Workspace Page Alignment & Decentralization

- Skills declare Workspace pages via `x-augur-dashboard-pages` in SKILL.md frontmatter; Browse is the discovery surface and needs no explicit declaration
- Never store plugin-specific data in `config/` files — use the skill's own SKILL.md frontmatter
- Never create redirect stubs when moving pages — move the skill itself to the correct path
- Mounted dashboard files come from `apps/dashboard/features/pages/{group}/{page}/page.tsx` or generated page config — never write directly to `apps/dashboard/app/`
- The `x-augur.hub` field within the `x-augur:` block is used as an internal grouping/discovery key; it does not create navigable hub sections in the UI

## Hot-Reload

Skills in `project-brain/capabilities/skills/` hot-reload on file change. Edits to SKILL.md files take effect immediately without restarting the active agent client.

## MANDATORY: Use Before Skill Work

Before modifying ANY skill, ALWAYS:

1. **Use `get-context` MCP tool**
   ```
   Tool: get-context
   Args: { "skill_hint": "lifestyle" }
   ```
   Returns: SKILL.md content, related files, recent changes, user preferences.

2. **Read SKILL.md**
   ```
   Read project-brain/capabilities/skills/{skill}/SKILL.md
   ```
   Understand current capabilities before adding new ones.

3. **Check for relevant actions**
   ```
   ls project-brain/capabilities/skills/{skill}/assets/actions/
   ```
   Complex workflows may already have action YAMLs with dispatch modes (fire, oneshot, ide, modal).

## Skill folder schema

Skills follow the Agent Skills standard. Standard directories at skill root include `commands/`, `references/`, `scripts/`, `assets/`, `examples/`, `evals/`, and `modules/`.

Augur-specific content belongs in `augur/`, including `augur/dashboard/`, `augur/data/`, `augur/tests/`, and `augur/lib/`.

Allowed optional root files include `README.md`, `CHANGELOG.md`, `LICENSE*`, `pyproject.toml`, `package.json`, and `config.yaml` when they are skill-owned.

Banned at skill root:

- `docs/` - use `references/`
- `data/` - use `augur/data/` or `assets/`
- `lib/` - use `scripts/` or `augur/lib/`
- `augur/seed/` - use `assets/seeds/`

Dashboard files in `augur/dashboard/` may use `.tsx`, `.ts`, `.css`, `.js`, or `.jsx`.
