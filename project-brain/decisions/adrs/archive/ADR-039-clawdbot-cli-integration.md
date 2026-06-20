---
status: Implemented
date: '2026-02-04'
deciders:
- Augur Team
related: []
hub: null
tags:
- clawdbot
- cli
- integration
- via
- clibridge
superseded_by: null
---

# ADR-039: ClawdBot CLI Integration via CLIBridge Pattern

## Context

ClawdBot (now OpenClaw) is an open-source personal AI assistant built by Peter Steinberger (steipete) that integrates ~30 CLI tools for macOS automation, messaging, smart home control, and productivity. All tools are open-source (MIT license). We evaluated each tool for integration into Augur's "second brain" architecture, filtering for tools that align with Augur's vision rather than importing the entire ClawdBot ecosystem.

The existing `icloud` and `capture` skills in Augur were fragmented — Apple Notes lived in `icloud`, voice memos in `capture`, and both had overlapping macOS-native concerns. Similarly, messaging (iMessage, WhatsApp), smart home (Hue, Sonos), and content summarization had no representation in Augur.

## Decision

### 1. CLIBridge Pattern

Created a src/lib `CLIBridge` utility (`src/mcp/augur_mcp/cli_bridge.py`) that standardizes how external CLIs are wrapped as Augur MCP tools. Any CLI becomes an MCP tool with:
- Install detection (`is_installed()`)
- Subprocess execution with timeout (`run()`)
- Error-to-string convenience method (`run_or_error()`)

### 2. Skill Classification (17 skip, 13 integrate)

| Decision | Tools |
|----------|-------|
| **NEW `apple` plugin** | apple-notes, apple-reminders, peekaboo, openai-whisper + existing icloud/capture |
| **NEW `google-workspace` plugin** | gog (Gmail, Calendar, Drive, Docs) |
| **Enhance `channels`** | imsg (iMessage), wacli (WhatsApp) |
| **Enhance `home-automation`** | openhue (Philips Hue), sonoscli (Sonos) |
| **Enhance `knowledge`** | summarize (URL/podcast/YouTube), nano-pdf |
| **SKIP (17 tools)** | 1password, bear-notes, bird, blogwatcher, blucli, camsnap, clawhub, eightctl, gifgrep, goplaces, himalaya, mcporter, model-usage, obsidian, ordercli, sag, songsee, things-mac |

### 3. Apple Ecosystem Consolidation

Merged `icloud` + `capture` into a single `apple` plugin:
- **FROM `icloud`**: AppleNotesIO, inbox refresh, calendar service, desktop scanning, email inbox, all scripts
- **FROM `capture`**: Voice memo recording/listing, screenshots gallery, all dashboard/API
- **NEW**: Reminders via `remindctl`, screenshots via `peekaboo`, transcription via `whisper`

Both old skill directories deleted. Dashboard auto-mounts, API routes, and config references updated.

### 4. Distribution Strategy — No ClawdBot Dashboard

Tools are absorbed into existing Augur hubs rather than creating a separate "ClawdBot" page. Each CLI maps to the skill it naturally belongs to.

## Consequences

### Positive

- 13 new MCP tools available across 5 skills with no custom API code — just CLI wrappers
- Apple ecosystem unified under one plugin (was split across two)
- CLIBridge pattern is reusable for future CLI integrations
- All tools are Operation mode, accessible from relevant dashboard pages
- Graceful degradation: tools return install hints if CLI is missing

### Negative

- Dependency on external CLIs that may change their interfaces
- `sonoscli` not yet installed (requires Go toolchain)
- Dashboard pages for `apple` plugin need UI polish (migrated from two sources)
- Some CLIs use unofficial/reverse-engineered APIs (wacli, imsg) which may break

### Neutral

- No new Python/npm dependencies added to root — all CLIs are standalone binaries
- Existing knowledge, channels, and home-automation skills retain all prior functionality
- Auto-generated files (generated-registry.ts, mounted pages) regenerate on next `npm run build`

## Alternatives Considered

### Alternative 1: Import ClawdBot as a Whole

Install all 30 ClawdBot tools and create a ClawdBot dashboard hub. Rejected because most tools don't align with Augur's second-brain vision (food delivery, GIF search, audio spectrograms are not knowledge/automation tools).

### Alternative 2: MCP Server Proxying

Use ClawdBot's MCP servers directly instead of wrapping CLIs. Rejected because Augur has its own MCP framework and adding external MCP servers would increase context window pressure (ADR context limits already documented in CLAUDE.md).

### Alternative 3: Keep icloud and capture Separate

Add new tools to existing skills without consolidation. Rejected because the split was arbitrary — Apple Notes in `icloud` but voice memos in `capture`, both are macOS-native. Unification into `apple` is cleaner.

## Files Changed

| Path | Action |
|------|--------|
| `src/mcp/augur_mcp/cli_bridge.py` | NEW |
| `plugins/productivity/skills/apple/` | NEW (full plugin, 15+ files) |
| `plugins/productivity/skills/google-workspace/` | NEW (plugin) |
| `plugins/productivity/skills/apple/` | DELETED (merged into apple) |
| `plugins/productivity/skills/apple/` | DELETED (merged into apple) |
| `plugins/admin/skills/channels/mcp/__init__.py` | NEW (imsg + wacli tools) |
| `plugins/home/skills/home-automation/mcp/__init__.py` | NEW (openhue + sonoscli tools) |
| `plugins/ai/skills/knowledge/augur/__init__.py` | MODIFIED (summarize + nano-pdf tools) |
| `src/config/plugin_state.json` | MODIFIED |
| `config/dashboard/mcp_tool_groups.yaml` | MODIFIED |
| `src/dashboard/lib/services/calendar.ts` | MODIFIED (path update) |

## References

- [OpenClaw (formerly ClawdBot)](https://github.com/clawdbot/clawdbot) — MIT License
- [steipete's homebrew tap](https://github.com/steipete/homebrew-tap) — CLI install source
- Plan file: `.claude/plans/kind-hopping-rainbow.md`
