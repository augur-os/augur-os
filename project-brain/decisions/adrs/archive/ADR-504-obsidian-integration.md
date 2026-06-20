---
id: ADR-504
title: Obsidian Vault Integration
status: Implemented
date: 2026-03-24
deciders: [Gur Sannikov]
tags: [obsidian, vault, integration, adapters, scraper]
related: [ADR-436]
---

# ADR-504: Obsidian Vault Integration

## Context

Augur needed a vault integration layer to connect with external knowledge management tools. Obsidian was selected as the first integration due to its local-first architecture and markdown-native storage. ADR-436 defined the design; this plan covered implementation of VaultAdapter hierarchy, MCP tools, and Browse page integration.

## Decision

Implement Obsidian as the first vault integration with:
- **VaultAdapter base class** — ABC hierarchy (LocalFileVaultAdapter, LocalAppVaultAdapter, CloudVaultAdapter) in `vault_adapters/`
- **Obsidian skill** — 5 MCP tools: obsidian-read, obsidian-write, obsidian-search, obsidian-scaffold, obsidian-status
- **Defuddle scraper upgrade** — Replace naive HTMLParser with defuddle for better content extraction
- **Browse page integration** — Discover vault adapters via SKILL.md frontmatter in Browse page
- **Markdown flavor conversion** — Stateless conversion between plain, Obsidian, and Logseq markdown formats

## Consequences

### Positive
- Users can access Obsidian vaults through Augur's MCP tools
- VaultAdapter pattern supports future integrations (Logseq, Notion)
- Defuddle produces cleaner extracted content than HTMLParser

### Negative
- Obsidian-specific markdown (wikilinks, callouts) requires format conversion layer

## References

- Plan: `docs/superpowers/plans/2026-03-18-obsidian-integration.md`
- Parent ADR: ADR-436 in `Au-vault/dev/adrs/`
- Skill: `skills/obsidian/`
