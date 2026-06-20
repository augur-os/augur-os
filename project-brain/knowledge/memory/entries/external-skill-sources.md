---
title: external skill sources
name: external-skill-sources
description: Pointers to upstream repos and install paths for the third-party skills
  the user has installed
brain_scope: personal
type: reference
status: active
source_client: claude-code
source_file: reference_external_skill_sources.md
source_hash: da5d8ac5b73f8de7
---

Map of external (third-party) AI skills currently installed and their upstream sources, for future updates and version checks.

| Skill / bundle | Upstream | Local install | Update via |
|---|---|---|---|
| `geo` + 15 sub-skills (`geo-audit`, `geo-citability`, `geo-llmstxt`, `geo-brand-mentions`, `geo-content`, `geo-crawlers`, `geo-platform-optimizer`, `geo-prospect`, `geo-proposal`, `geo-report`, `geo-report-pdf`, `geo-schema`, `geo-technical`, `geo-compare`, `geo-update`) | `https://github.com/zubair-trabzada/geo-seo-claude` (MIT, ~7k★) | `~/.claude/skills/geo*/` (manual `cp -R` from upstream `geo/` + `skills/*` + `scripts/` + `schema/`) | `/geo update` slash command (the `geo-update` sub-skill itself), OR re-clone upstream + `cp -R` |
| `ui-ux-pro-max` | `https://github.com/nextlevelbuilder/ui-ux-pro-max-skill` | `~/.claude/plugins/marketplaces/ui-ux-pro-max-skill/` (Claude marketplace) | `/plugin update ui-ux-pro-max@ui-ux-pro-max-skill` |
| `superpowers` | `https://github.com/obra/superpowers` (Jesse Vincent, MIT) | `~/.claude/plugins/cache/claude-plugins-official/superpowers/5.1.0/` (Claude marketplace) + `~/.gemini/extensions/superpowers/` (Gemini extension) | `/plugin update superpowers@claude-plugins-official` |

Notes:
- Augur's vendor tier is registered in `config/external_skills.yaml` and fanned out by `shared-vault/skills/ai/scripts/sync_agents/external_skills.py`. It is currently empty; `geo`/`ui-ux-pro-max`/`superpowers` stay deliberately Claude-only or Claude+Gemini-only.
- `superpowers-marketplace` (Jesse Vincent's standalone marketplace at `~/.claude/plugins/marketplaces/superpowers-marketplace/`) is registered but the active superpowers comes from `claude-plugins-official`. Marketplace stays registered so `episodic-memory`, `elements-of-style`, `double-shot-latte`, `superpowers-chrome` etc. remain installable on demand.
