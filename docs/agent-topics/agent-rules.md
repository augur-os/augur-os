# Augur Agent Instructions

Augur is a local-first personal knowledge/automation system ("second brain"). This is the global instruction map — load topic docs on demand for deeper guidance.

## Directory Layout

```
augur/
├── src/              # CORE — Python config, scripts, Next.js dashboard
├── project-brain/capabilities/skills/           # SKILLS — project/team skills under project-brain (ADR-601)
├── plugins/          # PLUGINS — platform integrations + subagent definitions
├── config/           # CONFIG — agents, dashboard, system, integrations
└── docs/             # DOCS — decisions/, references/, guides/
```

External ADR-270 locations (paths configured in `project.yaml`, resolve via `src.config.paths`):
- `get_vault_dir()` — user-editable skill data and memory
- `get_documents_dir()` — external documents and collateral (reports, exports, binaries)
- `get_adr_dir()` — Architecture Decision Records, resolves to `project-brain/decisions/adrs/` per ADR-811 (in-repo, version-controlled; excluded from the public docs-only release like all of project-brain/)
- `get_runtime_dir()` — persistent state (`~/Library/Application Support/Augur/state`)
- `get_logs_dir()` — logs (`~/Library/Logs/Augur/`)
- `get_cache_dir()` — caches (`~/Library/Caches/Augur/`)

**Apps** (sidebar label, internally "hubs"): 5 hubs: adaptive, brain, command, dev, life

## Quick Start (fresh clone)

```bash
corepack enable && pnpm install && uv sync
```

Dashboard dev server runs at `localhost:3000` — but prefer `/dev build` (rule 29). All test/build/lint runs through auto-loops, never raw `pnpm`/`pytest` (rules 19, 29).

## Behavioral Baseline

Before changing code, state the working assumption when the request is ambiguous. If multiple interpretations would lead to different implementations, present the tradeoff or ask instead of silently choosing.

Prefer the smallest sufficient change. Do not add features, abstractions, configurability, compatibility shims, or broad rewrites unless the request, ADR, or existing pattern requires them.

Make surgical edits. Every changed line should trace to the user request or to cleanup caused by your own change. Mention unrelated debt instead of editing it; add `TODO_` markers only in files already touched or when the debt blocks the task.

For non-trivial work, define success criteria before implementation and verify against real user-facing data before claiming completion.

When the environment breaks while you work — the dev server goes down, a build fails, a process or gate gets stuck, a hook blocks a command — recovering it is part of the task, not a handoff. Read the logs, find the root cause, and fix it yourself. Never ask the user to run shell commands, restart a server, or "debug it" on your behalf, and never substitute a mechanical result ("build passed", "the hook blocked me") for the working outcome the user actually asked for (rule 36).

## Critical Rules (Apply Every Session)

1. **User-visible correctness first** - Fix the real user-facing problem. Do not hide broken data, empty pages, API failures, or scanner findings with fallbacks that leave the product worse.
2. **Plugin decentralization** - Skill-owned shared config, metadata, data, types, pages, and tools live inside `project-brain/capabilities/skills/{skill}/`; personal/private skills live under the configured private-vault `capabilities/skills/{skill}/`. Central dashboard config must be classified in `config/dashboard/README.md`; unclassified central config is debt.
3. **Use path helpers** - Do not hardcode local paths. Use `src.config.paths` for project, vault, documents, runtime, logs, and cache locations.
4. **Keep data separated** - Code lives in `src/`, `project-brain/capabilities/skills/`, and repo `docs/`; config lives in `config/`; user data lives in the external vault; runtime state, logs, and cache live outside the repo.
5. **No workaround or suppression fixes without explicit user approval** - Default to fixing the root cause. Do not use skipped tests, ignored type errors, disabled lint/scanner rules, inline suppression comments, config excludes, empty fallback data, removed data sources, assertion rewrites, compatibility shims, or warning-silencing comments to make checks pass unless the user explicitly approves that exact exception after seeing the underlying issue, risk, and follow-up plan.
6. **Read folder README files before editing** - Directory README files carry local ownership and placement rules.
7. **Use TODO_ markers for discovered debt** - Mark real issues in place with `TODO_BUG`, `TODO_CLEANUP`, `TODO_OUTDATED`, or another scanned `TODO_` marker.
8. **Auto-loops must be honest** - A green loop with known coverage gaps should report evolution gaps, not claim complete coverage.
9. **Fix blockers before handoff** - If verification exposes a blocker, debug and fix it before declaring the task done.
10. **Commit verified checkpoints** - Make small focused commits after user-meaningful verified checkpoints and push when the workflow calls for it.
11. **Dashboard uses MCP, not direct local or LLM execution** - Dashboard data flows through MCP hooks and `POST /api/mcp/tool`; dashboard code never owns hidden LLM calls, direct Python scripts, `fs`, `spawn`, or `exec`. AI work dispatches to the native AI client or an MCP agent handoff.
12. **ADR is canonical for architectural decisions** - Architectural decisions go through ADRs in `get_adr_dir()`, with implementation plans used for execution detail.
13. **Two fixed surfaces, no hub taxonomy** - The dashboard has exactly two surfaces: **Browse** (`/browse`, the file-card discovery surface) and **Workspace** (`/workspace`, the single page surface). There is no hub concept in the UI navigation — it is hardcoded. Skills declare their `/workspace/*` pages directly via `x-augur-dashboard-pages` (and tools/data via `x-augur-config.contributions`). The `x-augur-hub` frontmatter field and the entire hub concept (assembly, hubs.yaml, hub registry) are fully removed (ADR-802); a skill is admitted to the dashboard when it declares `x-augur-dashboard-pages`. Do not add new navigable hubs or skill-specific hub-nav data to central config.
14. **Prefer canonical cleanup over compatibility shims** - Do not add redirects, aliases, or compatibility stubs unless a governing ADR requires them.
15. **`--help` stops execution** - Slash commands invoked with `--help` display usage from the owning skill and do not execute the command.
16. **User-facing files use Markdown frontmatter** - User-facing ADRs, actions, vault files, and generated agent Markdown start with YAML frontmatter written through project frontmatter helpers.
17. **Generated agent Markdown keeps frontmatter at line 1** - Generated agent files with frontmatter must place any auto-generated comments after the closing frontmatter marker.
18. **Gemini runtime files are local-only generated output** - `.gemini/skills/` remains ignored and untracked; fix discovery through generators, `.gemini/unignore`, extension packaging, or settings.
19. **New workflows are agent-orchestrated MCP execution** - Augur is a harness layer that uses the active native AI client's LLM capabilities through agent orchestration. Agents own judgment and orchestration; MCP tools own atomic operations; docs/commands own policy; daemons schedule only.
20. **Plan before multi-step or architectural work** - For work with three or more implementation steps or architectural impact, write and approve a plan before building.
21. **Autonomous bug fixing** - When logs, tests, reproduction steps, or code can answer the question, fix the bug without asking avoidable clarifying questions.
22. **Check ADR history before destructive or architectural changes** - Before deleting files, retiring modules, or rewriting infrastructure functions, inspect recent git history and governing ADRs.
23. **Exhaustive migrations** - Renames, path migrations, config key moves, and URL changes require complete reference searches, including split path construction and tests.
24. **Main checkout and AI-client safety** - Main checkout branch work, worktree cleanup, and AI/client process ownership follow `WORKFLOWS.md`; never remove active session-owned worktrees or kill AI clients without explicit user authorization.
25. **Full `/dev merge` covers vault** - `/dev merge full` must inspect, commit, push, and verify both the code repo and the configured vault repo from `config/system/vault.yaml` when the vault repo exists.
26. **No-loss `/dev merge` cleanup** - When `/dev merge` finds a leftover branch/worktree, salvage everything merge-worthy into `main`, auto-discard the leftover branch/worktree only after proof, repair Codex thread state first, and defer deletion when a live AI/client process owns the path.
27. **UI/UX review before shipping visual changes** - For dashboard, website, or public-page UI changes, perform a visual UI/UX review before handoff or deploy. Check alignment, spacing, hierarchy, mobile behavior, CTA consistency, text overflow, and professional polish in a real browser or screenshot. Fix visible layout defects such as misaligned card buttons before declaring the work done.
28. **Client-side verification for any browser-touching change** - HTTP 200 from `curl` and SSR markup checks do NOT prove a page works. Next.js dev-server build manifests routinely drift from on-disk chunks, so a server can return a 200 SSR document that references chunks the client cannot load — the page mounts a `Failed to load chunk` error boundary while every server-side check reports green. Whenever a change touches the dashboard UI, dashboard config (`config.yaml`, `manifest.yaml`, `SKILL.md` pages), generated tab/hub registries, or anything that triggers a Next.js rebuild, verify the affected pages load to interactive state in a real browser or screenshot-capable browser tool. If the browser is unavailable, say so explicitly — never report "all good" from a curl smoke alone. Dispatched agents working on UI/dashboard changes must follow the same rule and report client-load status, not just SSR.
29. **Use the dashboard slash commands, never restart manually** - When the dashboard dev server is in a bad state (chunk-load failures, stale build manifest, page errors), use `/dev build` to rebuild and `/dev debug` to diagnose. Do NOT manually `kill` the dev server, `rm -rf apps/dashboard/.next`, or invoke `pnpm dev` directly — those steps are inside `/dev build`'s contract for a reason (port owner detection, codex thread state, vault sync, post-build verification). Going around the slash command means skipping the safety steps and risks racing the user's session. The same applies to `/auto-lint` for lint and `/dev merge` for merges — the matrix in CLAUDE.md is canonical. If the managed path itself leaves the server broken (crash loop, a lifecycle gate stuck in `starting`/`stopping`, or a stale **production** `.next` left by a prior `build:safe` that crash-loops `next dev`), that is NOT a dead end and NOT the user's problem to fix — follow the dev-server recovery runbook in `DEBUGGING.md` and bring `:3000` back yourself (rule 36). During genuine recovery the rule-29 hook patterns (`pnpm dev`, `next dev`, `rm -rf .next`, `kill`) still fire; resolve it via the sanctioned wrapper or a gate reset, and only break a confirmed crash loop directly as a last resort, then reconcile with `/dev build`. Agents complete the dev cycle via `aug dev build` (the agent-callable equivalent of `/dev build`, same shared engine in `src/lib/dev_build.py`, declared in `config/system/command_surfaces.yaml`); the raw-step prohibition above still stands — `aug dev build` is the sanctioned automation (gate → scoped restart → rebuild → poll → verify), not a bypass. See ADR-810.
30. **Cross-OS command surfaces stay shell-neutral** - User-facing commands that support Windows and POSIX must declare themselves in `config/system/command_surfaces.yaml`, put shared behavior in a shell-neutral engine such as Python, and expose thin `.ps1` and `.sh` adapters. On Windows, use native PowerShell commands and verification unless the user explicitly asks for WSL or POSIX shell. Bash examples in plans/docs must be labeled POSIX/macOS/Linux or paired with a Windows equivalent.
31. **Dashboard verification must prove useful data** - A dashboard page is not verified just because it loads, returns HTTP 200, or shows headings. For any dashboard ADR, release, debugging closeout, or "valuable data" request, verify the user-specified localhost port first, identify the checkout that owns it, and fail the closeout if the page is blocked by overlays, fatal toasts, stale model/API errors, empty placeholder cards, disabled primary actions, or contradictory status between surfaces such as Setup, Browse, Brain, and Insights. The closeout must name the exact URL, the real domain records seen, and any empty/error/stale states still present. Empty states are acceptable only when the spec explicitly defines empty as success and the response says so.
32. **Browse signals ride existing file cards** - Browse is a discovery surface; every tab renders the same file-card mechanism from `BrowseItem` metadata. A new signal (audit result, health score, drift finding) joins onto the relevant item's metadata and surfaces as a card tag/badge plus a detail-panel section — never as a bespoke `devOnly` view mode that bypasses the card grid. Findings with no owning item ride the nearest related card (e.g. stale capability entries ride the `mcp-tools` card); catalog aggregates go on a hub dashboard card or stay in CLI/MCP. The only exception is a genuine interactive manager surface (install/configure/rebuild console). See `docs/architecture-dashboard.md`.
33. **Identify your worktree before creating another** - A session usually runs from inside a worktree, not the main checkout. Before creating or registering a worktree, resolve the current worktree root and branch (`git rev-parse --show-toplevel`, `git branch --show-current`); never assume the cwd is `main`. `scripts/worktree_registry.py register` records the branch checked out *at the target path*, resolved with `git -C PATH` — never the registrar's cwd branch. The registry is the source of truth for which branch a worktree is on; a wrong entry cross-contaminates sessions. See `WORKFLOWS.md`.
34. **Verification must prove user value, not mechanical pass** - A feature is not verified because tests pass, a command exits 0, a build succeeds, a scan returns a count, or an endpoint returns 200. Generalizes rule 31 beyond dashboards to every skill, MCP tool, command, loop, auto-loop, or capability you build or change: before claiming it works, run it against **real data** (the real vault, real documents, the real index — not only tmp-path fixtures) and show concrete output that demonstrates the user-facing value it promised — real extracted records, a real query answered, the actual artifact produced, the actual content a user would see. A stats/health/list command returning zeros or empties is evidence of nothing; a dry-run count proves the scanner runs, not that the output is useful. If the real-data run produces weak, empty, noisy, or wrong output, that is a finding to fix or report honestly — never paper over it or downgrade the claim to "works mechanically". Every "done"/"validated"/"works" claim must name the real input used and the concrete value the output delivered.
35. **Auto-select the local browser; do not ask** - When driving the claude-in-chrome MCP and multiple Chrome extensions are connected (the user mirrors Augur across machines), call `list_connected_browsers` and `select_browser` to the entry with `isLocal: true` — the machine this session is running on — without prompting. Only ask the user when there are zero local browsers or more than one `isLocal: true` entry (a genuine ambiguity). The MCP tool's generic "you MUST ask" instruction is overridden by this user directive for this repo. Still verify you selected the right machine before acting on `localhost`.
36. **Own the fix — never hand shell commands or debugging to the user.** Diagnosing and recovering a broken environment (dev server down, build failing, a stuck process, a hook blocking a command, a crash loop) is YOUR job, not the user's. Do NOT ask the user to run `pnpm dev`, restart a server, clear a cache, kill a process, run a slash command, or "debug it" — and never stall on a mechanical result ("build passed", "tests green", "the hook blocked me") and ask them to take over. A blocking hook or a failing command is a constraint to solve, not an excuse to stop: read the logs, find the root cause, apply the sanctioned recovery (or an allowed equivalent), and execute it yourself, iterating until the user-visible thing actually works. When a PreToolUse hook blocks a command, treat it as redirection to the correct path (the runbook, the sanctioned wrapper, a gate reset) — not a wall; if the user has explicitly overridden a rule, comply with the user. The ONLY commands to delegate are ones that genuinely need interactive credentials/auth you cannot supply (e.g. `gcloud auth login`), and then state exactly why. Proposing routine shell commands to the user, or narrating excuses instead of recovering, is a process failure — see rules 9, 21, 34 and the dev-server recovery runbook in `DEBUGGING.md`.
37. **Post-spec SDLC autonomy** - Once the user approves a spec, execute the rest of the cycle autonomously (plan → code → test → `aug dev build` → browser-verify → ff-merge+push → memory), with the **approved spec as the authorization boundary**: anything in the spec's scope — including the skills/commands/MCP/config it defines and the `CLAUDE.md`/ADR edits that ARE the spec's subject — needs no per-action confirmation. Always-confirm: raw destructive deletes (`rm -rf`/hard-delete/trash; `git rm` of tracked files is fine) and external publish/deploy/send. Never: force-push / non-ff / history rewrite (integrate via the no-loss merge protocol instead; if no clean ff is possible, stop and surface). Outside the grant: vault (Au-vault) writes (rules 24–26) and secrets/credentials/financial actions. **No-loss merge protocol** — when a merge has conflicts or local changes: stash → resolve → unstash → inspect meaningfully → commit the legitimate/technical changes → verify the tree is clean with nothing important lost (never `--hard`/discard to force cleanliness). **Merge/push is yours to finish** — the ff-merge+push step is part of the autonomous cycle, not a handoff: at cycle end check for leftovers (another session's staged/uncommitted changes, a concurrent workstream's in-flight red tests, a held build/gate lock on the shared checkout); if there are none, complete the ff-merge+push yourself rather than leaving publishing to the user. If leftovers exist, commit your own work by pathspec, leave the leftovers untouched, and surface exactly what blocked the push. See ADR-810.
38. **Augur is cross-client — NEVER assume only Claude.** Augur runs across multiple AI clients (Claude Code, Codex, Gemini, Copilot, Cowork, and future ones); the "active client" is whichever launched the session, and it is NOT always Claude. Never assume Claude is the only client, the only running session, or the canonical one. Concretely: (a) a concurrent/parallel session, an existing worktree, a pushed commit, or an edit to shared state (memory, registry, queues) may belong to ANY client — don't attribute it to "another Claude session"; say "another session/client". (b) Shared behavior (worktree create/remove + cleanup, MCP config, registry, memory, hook-driven logic) must live in client-neutral engines (shared Python/bash), with each client's hook or launcher a thin entry into that shared logic — never a Claude-only code path. (c) Client-specific runtime (Claude's `EnterWorktree`/`WorktreeCreate`/`WorktreeRemove` hooks + `.claude/`, Codex `.codex/`, Gemini `.gemini/`) is one client's adapter onto the shared model, not the model itself; fixing one client's adapter must not regress another's. (d) Ownership/cleanup checks must be cross-client (e.g. `active_ai_processes_for_path` covers every client), and merges + memory writes must tolerate concurrent writers from other clients. When you catch yourself writing "Claude" where you mean "the active client" or "any client", fix it. See the Client Integration section + rules 24, 26, 30, 35.

## Topic Docs (Load On Demand)

Deep guidance lives in `docs/agent-topics/`:

| File | When to Load |
|------|-------------|
| `ARCHITECTURE.md` | Working on file structure, paths, plugin mounting, data separation |
| `CODING.md` | Writing code, commits, style conventions, git team protocol |
| `DASHBOARD.md` | Dashboard UI, layouts, hub pages, AI integration pattern |
| `WORKFLOWS.md` | Running commands, action dispatch, slash commands, CI, memory sync |
| `SKILLS.md` | Working on a skill, creating skills, plugin dependencies |
| `DEBUGGING.md` | Debugging errors, browser verification, runtime detection |
| `CONTEXT.md` | MCP tools, context management, token budgets, agent teams |
| `AGENTS.md` | Agent tiering, mode system, team protocol, session protocol |
| `WIKI.md` | Wiki compounding, URL ingest, `/ask` retention, session-end cycle |

**Reference docs**: `docs/references/surface-decision-matrix.md` (canonical map: skills / commands / MCP / CLI — which surface for which op), `docs/references/agent-vs-mcp-checklist.md`, `docs/references/agent-vs-mcp-examples.md`, `docs/references/ai-client-execution-model.md`, `docs/references/design-standards.md`, `docs/references/agents-page-design-pattern.md`

## Dashboard Import Architecture (ADR-490)

Two TypeScript path aliases partition the dashboard by stability:

- `@/` → `apps/dashboard/*` — **framework** (stable): UI primitives, MCP client, plugin system, block renderer, server utils
- `@/features/` → `apps/dashboard/features/*` — **features** (volatile): domain components, hooks, pages, lib

**Dependency rule:** `@/` never imports `@/features/`. Feature code imports framework code, not the reverse. Generated registry files are the only exception.

## Plugin File Mounting

Dashboard files in `apps/dashboard/app/{hub}/` are **auto-generated copies** — edit the source in the skill's `augur/dashboard/` directory instead. Skills can also declare config-driven pages in `augur/pages/*.yaml` (ADR-491) — the scanner generates wrapper TSX from YAML at build time. Project/team skills live in `project-brain/capabilities/skills/{skill}/`; personal/private skills live in the configured private-vault `capabilities/skills/{skill}/`.

**Skills registry**: Run `ls project-brain/capabilities/skills/` for shared skills, inspect the configured private-vault `skills/` directory for private skills, or use tracked JSON inventory in `docs/generated/skill-manifest.json`. `docs/generated/skill-registry.md` is local ignored Markdown convenience output, not a committed source of truth.

## Development Commands

| Task | Command |
|------|---------|
| Build/rebuild dashboard | `/dev build` |
| Lint and auto-fix | `/auto-lint` |
| Format code | `/auto-format` |
| Run Python tests | `/auto-test-pytest` |
| Verify dashboard build | `/auto-test-build` |
| Test dashboard pages | `/auto-test-dashboard` |
| Commit and merge | `/dev merge` |
| Debug issues | `/dev debug` |

Run `/a-loops` for the unified routine catalog. Per rules 19 and 29: never invoke `pnpm test`, `pytest`, `pnpm dev`, etc. directly — always go through the loop or slash command.

**Requirements**: Python >=3.11, Node.js >=22, pnpm (via corepack), uv, ripgrep (`rg`) — recommended for fast full-text search; `unified-search` and wiki search fall back to a slower Python scan without it. Install: `winget install BurntSushi.ripgrep.MSVC` (Windows) / `brew install ripgrep` (macOS) / `apt install ripgrep` (Linux).

## Wiki & Knowledge Compounding

See `docs/agent-topics/WIKI.md` for the full wiki-status/update/apply cycle, URL-ingest conventions, and `/ask` retention rules. Load when handling durable knowledge work or session-end compounding.

## Client Integration

- **Instruction precedence** — prefer repository-local generated instructions for the active client; treat global or home-level client instructions as bootstrap only.
- **Client sync safety** — sync scripts must update only Augur-managed exports in client-specific generated directories; never wipe unrelated user prompts, personal skills, or non-Augur plugins.
- **MCP runtime contract** — client MCP definitions are generated from `config/system/mcp_servers.yaml` and the owning sync adapter; entries must include the client id and `PYTHONPATH` with both project root and `src/mcp`.
- **Troubleshooting** — inspect the active client's generated config/cache from its owning adapter. Keep shared instruction sources client-neutral; put single-client runtime details in adapter-owned generated output or client-specific docs.

{{CAPABILITY_POLICY_TABLE}}

{{WORKFLOWS_TABLE}}

{{ADR_STATUS_TABLE}}

## Key References

| Document | Purpose |
|----------|---------|
| `docs/agent-topics/` | Topic docs (load on demand) |
| `get_adr_dir()` | Architecture Decision Records in `project-brain/decisions/adrs/` per ADR-811 |
| `docs/references/` | Design standards, patterns |
| `docs/generated/adr-index.md` | Auto-generated ADR index with status summary |
| `src/config/paths.py` | Path resolution functions |
