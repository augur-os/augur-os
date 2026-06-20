---
status: Implemented
date: 2026-03-18
deciders:
  - Gur Sannikov
related:
  - ADR-270
  - ADR-163
hub: system
tags:
  - vault
  - obsidian
  - integrations
  - knowledge
superseded_by: null
---

# ADR-436: Obsidian Vault Integration [RECONSTRUCTED]

## Context

Augur's knowledge vault (`~/Vault/Augur/`) stores notes, memory, and ADRs as plain markdown files, but there was no structured way to integrate with external knowledge tools like Obsidian, Logseq, or Apple Notes. Users who wanted to browse their vault in Obsidian had to manually configure it. Additionally, the scraper skill used a naive HTMLParser for web content extraction, and the Settings integrations page was a dead-end that did not leverage decentralized SKILL.md frontmatter discovery.

## Decision

Introduce a VaultAdapter base class hierarchy parallel to BaseAdapter (IDE sync), with Obsidian as the first implementation. The changes span four areas:

### 1. VaultAdapter Hierarchy

A new `vault_adapters/` package in `sync_agents/` with three storage tiers:
- **LocalFileVaultAdapter**: Direct filesystem access (Obsidian, Logseq)
- **LocalAppVaultAdapter**: CLI/AppleScript bridge (Apple Notes)
- **CloudVaultAdapter**: Remote API (Notion)

Each adapter implements: `detect_installed()`, `sync_to_vault()`, `sync_from_vault()`, `get_managed_dirs()`, `cleanup()`. The base class provides a shared `cleanup()` that deletes managed directories.

### 2. Obsidian Skill and MCP Tools

New skill at `.claude/skills/obsidian/` with five MCP tools:
- `obsidian-read` -- read a note by relative path
- `obsidian-write` -- write or update a note
- `obsidian-search` -- full-text search via ripgrep
- `obsidian-scaffold` -- opt-in: create `.obsidian/` config in vault
- `obsidian-status` -- check installation and vault state

The vault at `~/Vault/Augur/` IS the Obsidian vault (per ADR-270). Obsidian support is opt-in: users run `obsidian-scaffold` to add `.obsidian/` config when they want to use Obsidian as a vault viewer.

### 3. Markdown Flavors Utility

Stateless `markdown_flavors.py` converts between plain, Obsidian, and Logseq markdown formats (wikilinks, callouts, etc.). Used by vault adapters but not owned by them.

### 4. Browse Page Integrations

The `list-integrations` MCP tool in `browse.py` was extended to discover vault adapters via `x-augur-integration-type` frontmatter in SKILL.md files. The Settings integrations page was deleted in favor of the Browse page's integrations category, following decentralized discovery (ADR-163).

### 5. Engine Orchestration

A `sync_vaults()` function was added to the sync engine, separate from `sync_all()` (IDE adapters). It auto-discovers vault adapters from the `vault_adapters/` directory.

## Consequences

### Positive

- Users can browse their Augur vault in Obsidian with full wikilink and callout support
- VaultAdapter hierarchy enables future integrations (Logseq, Notion, Apple Notes) with minimal code
- Vault search uses ripgrep for fast, local-first full-text search
- Integrations are discoverable from the Browse page via decentralized frontmatter

### Negative

- New adapter hierarchy to maintain alongside BaseAdapter
- Obsidian scaffold creates `.obsidian/` directory in the vault, which may conflict with user's existing Obsidian config if they already use the vault directory

### Neutral

- Vault path resolution uses `get_vault_dir()` from `src.config.paths` -- never hardcoded
- Obsidian is opt-in; the vault works without Obsidian installed
- The `obsidian` skill is in the `brain` hub

## Alternatives Considered

### Alternative 1: Obsidian Plugin Only (No Adapter Hierarchy)

Build Obsidian support as a standalone skill without the VaultAdapter base class.

**Rejected because**: Future vault integrations (Logseq, Notion) would require duplicating detection, sync, and cleanup logic. The adapter hierarchy provides reusable infrastructure.

### Alternative 2: Bidirectional Auto-Sync

Automatically sync vault content bidirectionally on every change.

**Rejected because**: Introduces conflict resolution complexity and risks data loss. The current approach uses explicit MCP tool calls for reads/writes and a separate `sync_vaults()` orchestration function.

## References

- Implementation plan: `docs/superpowers/plans/2026-03-18-obsidian-integration.md`
- VaultAdapter code: `.claude/skills/ai_bridge/scripts/sync_agents/vault_adapters/__init__.py`
- Obsidian skill: `.claude/skills/obsidian/SKILL.md`
- Tests: `.claude/skills/ai_bridge/augur/tests/test_vault_adapters.py`
- Browse integration: `src/mcp/augur_mcp/infrastructure/browse.py`
- ADR-270: Data Separation (vault storage model)
- ADR-163: Plugin Decentralization

## Impact Manifest

```yaml
impact:
  paths_renamed:
    - from: "apps/dashboard/app/settings/integrations/page.tsx"
      to: "(deleted, replaced by Browse integrations category)"
  apis_changed:
    - "list-integrations MCP tool extended with vault adapter discovery"
  patterns_deprecated:
    - "Settings integrations page (replaced by Browse page integrations category)"
  files_affected:
    - ".claude/skills/ai_bridge/scripts/sync_agents/vault_adapters/__init__.py"
    - ".claude/skills/ai_bridge/scripts/sync_agents/vault_adapters/obsidian.py"
    - ".claude/skills/ai_bridge/lib/markdown_flavors.py"
    - ".claude/skills/obsidian/SKILL.md"
    - ".claude/skills/obsidian/scripts/mcp/__init__.py"
    - "src/mcp/augur_mcp/infrastructure/browse.py"
    - ".claude/skills/ai_bridge/scripts/sync_agents/engine.py"
```
