---
title: "Comparison — Augur sync_agents vs cc-switch"
brain_scope: project
status: active
owner: team
date: 2026-05-24
tags: [comparison, sync, multi-client, landscape]
sources:
  - https://github.com/farion1231/cc-switch
note: "cc-switch analyzed at README/architecture level (not source-cloned); its exact file paths/formats are documented claims."
---

# Comparison — Augur `sync_agents` vs cc-switch

> One-liner: **Augur sync is a *compiler*** (one canonical source tree → projected deterministically into many AI clients). **cc-switch is a *control panel + package manager*** (a desktop GUI that switches API providers and round-trips config between a SQLite store and many CLI tools). They look adjacent because both fight "every AI CLI has its own config format," but they sit on opposite sides of it.

Note: in Augur there is **no standalone "sync skill"** — what's commonly called that is the `sync_agents` projection engine under the `ai` / `platform-admin` skills (`project-brain/capabilities/skills/ai/scripts/sync_agents/`), driven by `/dev sync`, `/dev-sync`, and git hooks.

## Side-by-side

| Dimension | Augur `sync_agents` | cc-switch |
|---|---|---|
| **Primary job** | Distribute *authored capabilities* (skills, agents, commands, rules, MCP topology) from one brain to N clients | *Switch API providers* and manage connection config across N CLI tools |
| **Form factor** | Headless Python package; runs in-session, via slash commands & git hooks | Standalone desktop app (Tauri 2.8, Rust + React 18, system tray) |
| **Source of truth** | Git-versioned source tree (`project-brain/.../skills/*`, `docs/agent-topics/agent-rules.md`, `config/system/*.yaml`) | SQLite DB at `~/.cc-switch/cc-switch.db` |
| **Data-flow direction** | **One-way** projection (source → generated client files) | **Bidirectional** (DB ↔ live client files: write-on-switch, backfill-on-edit) |
| **Drift model** | Drift = bug. Files marked `AUTO-GENERATED`, never hand-edited; pre-commit `--fix` re-projects | Drift expected & reconciled; "backfill protection" reads active file before edit |
| **Client coverage** | ~15 surfaces: Claude Code, Codex, Gemini, Cursor, Copilot, Cline, Windsurf, OpenCode, Cowork, Kimi, Antigravity, Claude Desktop, + plugin bundles | ~6 CLIs: Claude Code, Codex, Gemini, OpenCode, OpenClaw, Hermes |
| **Provider/proxy switching** | None (deliberate — harness-layer, uses host client's LLM; model *mapping* only, ADR-464) | **Core feature** — 50+ provider presets, hot-switch, local proxy, auto-failover, circuit breaker, health monitoring |
| **Skills handling** | **Authors** skills canonically, projects `SKILL.md` (copy/stub) into each client | **Installs** 3rd-party skills from GitHub/ZIP → `~/.cc-switch/skills/` → symlinked to apps (+20 backups) |
| **MCP handling** | Generates MCP config from `config/system/mcp_servers.yaml` template (`${AUGUR_ROOT}`, `PYTHONPATH`…) → `.claude/mcp.json`, `.codex/config.toml`… | Unified MCP panel, bidirectional sync across 4 apps, deep-link import |
| **Prompts/rules** | Projects `agent-rules.md` + skill/command/prompt content into `CLAUDE.md`/`AGENTS.md`/`GEMINI.md` + stubs | Markdown editor with cross-app sync of `CLAUDE.md`/`AGENTS.md`/`GEMINI.md` |
| **Policy/governance** | `capability_exposure.yaml` allow-list gates what's exposed where; structure validation | None documented (consumer convenience tool) |
| **Persistence** | File-first, no database; git is the history | SQLite + atomic writes (temp+rename) + cloud sync (Dropbox/OneDrive/iCloud/WebDAV) |
| **Audience** | Single power-user's knowledge OS (dev/build tooling) | Mass consumer (79.6k★, signed/notarized installers, Homebrew) |

## Where they genuinely overlap

The real comparison zone is three surfaces synced across Claude Code / Codex / Gemini / OpenCode: **MCP servers, prompts, and skills**. Both projects treat `CLAUDE.md`/`AGENTS.md`/`GEMINI.md` as per-client instruction targets, centralize MCP definitions and fan them out, and manage skills as portable units distributed to each client's skills directory. Everything else diverges.

## Where they fundamentally differ

1. **Compiler vs. reconciler.** Augur's generated files are *artifacts* — editing one is pointless because the next `sync --fix` overwrites it, and a git hook enforces that. cc-switch's "dual-way sync" makes live files first-class (it reads them back), so editing a tool's config directly is a supported path. Augur optimizes for **determinism / no-drift**; cc-switch for **convenience / meet-the-user-where-they-edited**. Augur can never have a "who-wins" conflict (source always wins); cc-switch can, and defends against it (backfill protection, atomic writes, mutex'd DB).

2. **Authoring vs. distributing skills.** Augur *is the place skills are written* (`SKILL.md`, command specs, agent defs, structure-validated). cc-switch is a *package manager* — pulls others' skills from GitHub/ZIP and symlinks them in, with backup retention. Augur is `gcc`; cc-switch is `apt`. **Augur's output is exactly the kind of payload cc-switch distributes** — they compose more than compete.

3. **Provider switching / proxy — cc-switch's whole identity, Augur's deliberate non-goal.** cc-switch's 50+ presets, hot-switching proxy, failover, circuit breaker, cost tracking have *no Augur analog* and shouldn't — Augur rides the host client's LLM and is explicitly vendor-neutral. Closest Augur gets is ADR-464 model *mapping* at projection time. cc-switch operates one layer down, at the connection/runtime tier.

4. **GUI vs. agent-orchestrated CLI.** cc-switch is a tray app a human clicks. Augur sync is invoked by an agent mid-session or by a hook — no UI of its own (the dashboard is a separate surface). Matches Augur rule-19 "agent-orchestrated MCP execution."

## What Augur could borrow from cc-switch

- **Deep-link import (`ccswitch://`) for shareable skills/MCP/prompts.** Augur has rich authoring but no one-click *import-a-capability-from-a-URL* primitive. Pairs with the external-skill tiers strategy — an `augur://install?skill=…` would formalize the third-party tier currently managed by hand. **(Highest-value borrowing.)**
- **Backup retention + symlink-vs-copy on skill install.** cc-switch keeps the last 20 skill backups and lets users pick symlink or copy. Augur projection always overwrites; a retained-snapshot option for *externally-sourced* skills would be a cheap safety net.
- **Usage/cost tracking + session browser** as an observability surface (adjacent to the ADR-743 job ledger + dashboard).
- **Health-check/failover thinking for MCP servers.** cc-switch's circuit breaker maps onto "is this MCP server reachable?" — Augur generates MCP config but doesn't probe liveness.

## What cc-switch could learn from Augur

- **One-way projection + generated-marker + hook enforcement** eliminates the conflict class cc-switch must actively defend against. For a single-author knowledge OS, "source always wins" is the right call.
- **Explicit capability-exposure policy** (`capability_exposure.yaml`) — an allow-list of *what's exposed to which surface*, a maturity cc-switch lacks.
- **Skills/commands/agents as validated first-class artifacts** rather than opaque folders to copy.

## Bottom line

Not competitors — **complementary layers**. cc-switch owns the **provider/connection/runtime tier** (which model, which endpoint, which key, is it up) with a consumer GUI and bidirectional reconciliation. Augur sync owns the **capability/content tier** (which skills, agents, rules, commands, MCP topology) with a deterministic compiler and git-enforced no-drift. Clean coexistence split: let cc-switch switch providers and proxy traffic; let Augur remain the source of truth that *compiles* skills/agents/rules into each client. Only real collision: both writing `CLAUDE.md`/`mcp.json` — Augur's `AUTO-GENERATED` marker + hook wins that by design.

**Most actionable takeaway for Augur:** the **deep-link / URL import primitive** for capabilities — the one cc-switch idea that fills a genuine gap in Augur's authoring-heavy model.
