# Changelog

## Unreleased

### Added
- `list-routines` MCP tool and Background Routines Browse category for ADR-727.
- Unified background routine discovery across per-skill schedules, daemon services, daemon scripts, launchd agents, GitHub Actions cron workflows, and MCP background tasks.

### Changed
- `ingest` URL capture (`/keep <url>` → `url-extract`) now falls back to a plain-text source feed when a page is JS-rendered (returns a stub) or errors: GitHub repo URLs capture the **raw README** instead of a JS-shell stub or HTTP 504. *Incident:* two `/keep` GitHub captures on 2026-06-08 saved a 39-word stub / failed with 504, requiring a manual raw-README workaround — now automatic (`url_ingest._source_fallback`, 8 new tests).
- Browse category `scheduled-executions` is renamed to `background-routines`; the legacy URL redirects for one release.
- Routine table/detail views now surface cadence, next run, last run, spawn kind, and estimated AI CLI token cost.

## Current status

Augur is in soft launch.

- Native macOS support is implemented.
- Native Windows architecture is implemented.
- Windows validation is still pending before we make a firmer public support claim.

## [0.1.0] - 2026-04-20

### Added
- MCP-first architecture for Model Context Protocol execution
- 200+ composable skills across 6 hubs: adaptive, brain, career, command, life, and studio
- Dashboard with block system and YAML-configurable pages
- Multi-client support: Claude Code, Cursor, Codex, Gemini, Ollama
- Autonomous autoloops for self-healing and evolution
- BM25 + ripgrep hybrid RAG
- Full airplane mode via Ollama for local operation
- Apple ecosystem integration (Notes, Reminders, Calendar, Shortcuts)
- Google Workspace integration (Gmail, Calendar, Drive, Docs, Sheets)
- Agent Skills standard for portable, cross-client skills
- Terminal with session reconnect and detach support
- Early `create-augur` scaffolding work for repo bootstrap
