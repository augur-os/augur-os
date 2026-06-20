# File Placement Matrix

Use this reference when deciding where a new file, skill, export, or knowledge artifact belongs.

## Core Rule

- Repo `src/`, `skills/`, `docs/`, `config/` are for tracked project code and documentation.
- External vault (`get_vault_dir()`) is for user-editable markdown knowledge.
- External documents (`get_documents_dir()`) are for collateral, exports, reports, and binary documents.
- External runtime/log/cache dirs are for state, flags, logs, and machine-managed transient data.

On this machine:

- `get_vault_dir()` → `Au-vault/`
- `get_documents_dir()` → `~/Documents/Augur`

## Matrix

| If you are adding... | Put it here | Why | Then run |
|---|---|---|---|
| Markdown note, journal, memory, source note | `get_vault_dir()` | User-editable text knowledge lives in the vault | `wiki update` if it should affect wiki pages |
| Wiki page | `get_vault_dir()/wiki/` via `wiki-write` | Wiki pages are synthesized markdown knowledge | `wiki-log` after updates |
| Binary source doc (PDF, PPTX, image, DOCX) | `get_documents_dir()` | Documents/collateral area is external, not repo docs | `ingest` or `wiki update` if it should feed the wiki |
| Generated report, export, deliverable, collateral HTML/PDF | `get_documents_dir()` | Deliverables are user/document collateral, not tracked repo docs | Nothing required unless you also want a checked-in snapshot |
| Tracked design doc, ADR note, guide, reference | Repo `docs/` | Project documentation belongs in version control | Sync/generated docs if relevant |
| Source code | Repo `src/` or `skills/` | Tracked implementation | Tests/build as appropriate |
| Runtime flag, state file, cache, machine output | `get_runtime_dir()`, `get_logs_dir()`, `get_cache_dir()` | Machine-managed state must stay out of repo and vault | Nothing special |

## New Skill

Create a new skill under:

```text
skills/<skill-name>/
```

Minimum required file:

- `skills/<skill-name>/SKILL.md`

Common optional surfaces:

- `skills/<skill-name>/commands/` — slash command docs
- `skills/<skill-name>/scripts/mcp/` — MCP tool implementations
- `skills/<skill-name>/augur/tests/` — tests
- `skills/<skill-name>/augur/dashboard/` — TSX dashboard pages/components
- `skills/<skill-name>/augur/pages/` — YAML config-driven pages
- `skills/<skill-name>/assets/` — skill-owned assets/seeds
- `skills/<skill-name>/references/` — skill-specific docs

After adding or changing a skill:

```bash
PYTHONPATH=project-brain/capabilities python3 -m skills.ai.scripts.sync_agents sync all
```

## New MCP Tool

For a new tool in an existing skill:

1. Implement it in `skills/<skill>/scripts/mcp/`
2. Declare it in `skills/<skill>/SKILL.md` frontmatter
3. Add tests in `skills/<skill>/augur/tests/`
4. Sync generated agent/client surfaces if needed

Do not add central registries for tool discovery when the skill frontmatter is the source of truth.

## Dashboard Surfaces

- TSX/custom page: `skills/<skill>/augur/dashboard/`
- YAML/config-driven page: `skills/<skill>/augur/pages/<name>.yaml`

Do not edit auto-generated mounted copies directly.

## Wiki Surfaces

Raw knowledge and synthesized knowledge are different:

- Raw markdown knowledge lives in the vault
- Raw binary knowledge lives in documents
- Synthesized wiki pages are written via `wiki-write`

Typical wiki update flow:

1. `wiki-tags`
2. `wiki-read` for matching pages if needed
3. `wiki-write`
4. `wiki-log`

Normal trigger surfaces:

- session-end wiki update rule
- `/wiki update`
- `/ingest`
- `/wiki rebuild`
- `/auto-wiki-maintenance`

`save-synthesis` stores reusable source material, but does not mutate wiki pages directly.

## Checked-In Snapshots

A generated collateral file may be copied into repo `docs/` only when it is intentionally versioned as project documentation or a reference/demo artifact.

That is the exception, not the default.
