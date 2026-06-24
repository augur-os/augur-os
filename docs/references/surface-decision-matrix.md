---
title: "Augur Surface Decision Matrix"
status: accepted
date: 2026-05-13
tags: [architecture, surfaces, mcp, cli, skills, commands, layering]
---

# Augur Surface Decision Matrix

The canonical map for where a capability lives in Augur and which surface(s) expose it. Authoritative reference for skill authors, AI clients reading agent instructions, and reviewers.

If you only read one section, read [The four-layer model](#the-four-layer-model) and [Decision flowchart](#decision-flowchart-for-where-does-this-op-go).

## TL;DR

Augur has **four architectural layers** and **seven surface types** that compose them. The same Python function can show up in multiple surfaces — surface is a routing/discovery choice, not an implementation choice. Default to **CLI-only**; promote to **MCP** only when the dashboard renders it or the agent calls it often enough that schema-discoverability beats `aug X` via Bash.

## The four-layer model

```
TRIGGER          CLI / Dashboard / Daemon / "/<command>"
                                  │
                                  ▼
POLICY           commands/*.md  ←── canonical user-facing surface
                                  │
              ┌───────────────────┴──────────────────────┐
              │                                          │
              ▼                                          ▼
   Native client reads               MCP discovery wrapper exposes
   command body directly             the same command as an MCP tool
   (Claude Code, Codex,              for clients that can't read
   Gemini all read commands/*.md)    commands/*.md natively
                                     (OpenCode etc.)
              │                                          │
              └───────────────────┬──────────────────────┘
                                  ▼
ORCHESTRATION    AI agent (vendor-neutral, native client's LLM)
                 Reads policy, uses ITS OWN fetch/browser tools,
                 judges, classifies, sequences
                                  │
                                  ▼
ATOMIC OPS       Atomic MCP tools  +  `aug` CLI commands
                 Bounded, stateless, never orchestrate
```

Direction is fixed: **trigger → policy → agent → atomic**. The agent is the only orchestrator. Atomic ops never decide the next step.

**The two MCP roles** that look identical on the wire but live in different layers:

- **MCP as discovery wrapper (top)** — a thin tool that says "I am `/ingest`; here's the policy body". Same body, same agent flow, just routed for non-generic clients. Lives in **L2 POLICY**.
- **MCP as atomic op (bottom)** — `save-url-source`, `wiki-write`, etc. The agent's hands. Lives in **L4 ATOMIC OPS**.

Conflating these two roles is the most common cause of AI clients drifting from the architecture. `x-augur-mcp-tools` frontmatter does not distinguish them today — a tool listed there could be either.

## Surfaces × layers × when-to-use

| Surface | Layer | Right when | Wrong when | Cost |
|---|---|---|---|---|
| **Skill** (`project-brain/capabilities/skills/<x>/`) | — (container) | A new domain capability with code, tests, optional UI, optional commands | Just a single function — that's a CLI subcommand, not a skill | Discovery, hub mounting, ADR governance |
| **Slash command** (`commands/<name>.md`) | **L2 POLICY** | User-facing entry point for a workflow; tells the agent what to do, in what order | You're tempted to make the command body "run Python" — it's a prompt body, not code | None at runtime; pure docs |
| **MCP discovery wrapper** (auto-generated from `commands/*.md`) | **L2 POLICY** (top half) | Client can't read `commands/*.md` natively (OpenCode etc.) and you want `/X` to still work via MCP | Client already reads commands natively (Claude/Codex/Gemini do — wrapper is redundant per ADR-734) | One tool-schema slot per command in the agent's tool list. **Policy**: generate ONLY for clients listed in the "needs-wrapper" set (`opencode` today); never for Claude / Codex / Gemini which read `commands/*.md` natively. |
| **AI agent's own tools** (WebFetch, browser MCP, playwright, Bash, agent web search) | **L3 ORCHESTRATION** | Fetching, exploring, parsing, classifying — any work that needs judgment about which tool, parallelism, or interpretation | The op is bounded, schema-shaped, and deterministic — use an atomic surface instead | Tokens for tool-result rendering |
| **MCP atomic tool** (real `mcp` export) | **L4 ATOMIC OPS** | Dashboard `useMcpQuery` calls it, OR agent calls it frequently enough that schema-discoverability beats `aug X` via Bash, OR returns complex structured data the agent needs typed | Caller is a shell script, cron, daemon, or one-shot agent call — `aug X` is fine and saves schema budget | Schema tokens in every AI session that imports the server |
| **`aug` CLI subcommand** | **L4 ATOMIC OPS** | Shell callers (Make, CI, daemon, cron); agent-via-Bash for ops it only needs occasionally; anything where schema-discoverability isn't worth a tool slot | Dashboard wants to call it from JS (dashboard must go via MCP per rule 11); op returns 10 KB of structured JSON the agent needs to traverse | One Bash invocation per call; no schema overhead |
| **Daemon trigger** | **L1 TRIGGER** | Scheduled work that creates an AI session to do the actual work | Daemon does the work itself (anti-pattern per [ai-client-execution-model.md](./ai-client-execution-model.md)) | Process management |
| **Dashboard `useMcpQuery` hook** | **L1 TRIGGER** (UI) → calls L4 | Any UI surface that needs server data or to mutate state — only path that satisfies rule 11 (no `fs`/`spawn` in dashboard code) | A pure client-side UI op with no backend touch | One MCP round-trip per call |

## Decision flowchart for "where does this op go?"

```
Is it user-facing policy / workflow narrative?
  └── YES → commands/*.md  (slash command body — L2 POLICY)
  └── NO ↓

Does the dashboard need to call it from JS?
  └── YES → MCP atomic tool (REQUIRED; rule 11 forbids fs/spawn in dashboard)
  └── NO ↓

Does the AI agent call it frequently enough during interactive sessions
that schema-discoverability beats `aug X` via Bash?
  └── YES → MCP atomic tool (also expose as `aug` CLI for shell parity — ~free)
  └── NO ↓

Will a shell script, daemon, cron, or CI ever call it?
  └── YES → `aug` CLI subcommand only
            (do NOT register as MCP tool — saves schema budget)
  └── NO  → it's not a real surface; delete it
```

## CLI vs MCP: they share implementation

`src/cli.py` (`_build_cli_mcps`) builds an **in-process FastMCP runtime** and calls tools directly. `aug X` and `mcp__augur-core__X` execute the same Python function at the same speed; the only difference is the routing/discovery layer above the function.

**Surface choice is not an implementation choice.** A `@mcp.tool` decorated function can be exposed via CLI only, MCP only, both, or neither, by changing one policy entry in `config/system/capability_exposure.yaml`. The runtime should respect that policy (see [Empirical state](#empirical-state-vs-target-state) for the current drift).

## What goes where: concrete checklist

### POLICY (L2): `commands/<name>.md`

- Frontmatter: `description` (one-liner with `Usage:` hint), optional `x-augur-export-command: true`.
- Body: numbered steps the agent follows.
- May reference atomic MCP tools and `aug` CLI commands by name; must not embed Python.
- Must support `--help` (per CLAUDE.md rule 15).
- Vendor-neutral (per [[feedback-vendor-neutral-design]]) — refer to fetch options by category, not by client name.

### ORCHESTRATION (L3): agent reads policy + acts

- Agent picks fetch tool per [agent-fetch-primitives.md](./agent-fetch-primitives.md) (forthcoming).
- Agent decides classification, retention, sequencing, parallelism.
- Agent calls atomic ops by name.

### ATOMIC OPS (L4): MCP tool OR `aug` CLI

Atomic op contract:
- Takes structured input, returns structured output (JSON-serializable).
- Performs one bounded mutation OR returns one bounded dataset.
- Never makes "next step" decisions, never calls other atomic ops in sequence.
- Idempotent where possible.
- Stateless (no in-memory state between calls).

Surface choice per the flowchart above. The same Python function can be registered with `@mcp.tool` and exposed via both surfaces — the `aug` CLI uses an in-process MCP runtime regardless.

For `SKILL.md`, prefer `x-augur.tools[].surface` over adding new top-level
`x-augur-*` fields. The surface values are `cli`, `mcp via dashboard`, and
`mcp`; `mcp-tool` is a capability type, not a primary surface.

### TRIGGER (L1): how work begins

- **CLI**: user types `aug X` or `/command` in an AI client.
- **Dashboard**: UI calls `useMcpQuery` / `useMcpMutation` / `useMcpPoll` / `mcpCall`.
- **Daemon**: scheduled job creates an AI client session and hands it a prompt.

Daemons never own the work itself — they only start AI sessions that do the work via the same policy + atomic-ops path.

## Empirical state vs target state

| Surface | Today (registered) | Today (per policy) | Today (actually used) | Target |
|---|---|---|---|---|
| MCP tools per monolith server | **275** | — | — | **~50** |
| Capabilities with `primary_surface: mcp` | — | 71 | — | ~50 |
| Capabilities with `primary_surface: cli` | — | 432 | — | 432+ |
| Capabilities with `export_to: [mcp]` | — | 62 | — | 30-50 |
| MCP tools dashboard actually calls | — | — | **35 unique** | 35-50 |

**Drift today:** the runtime ignores policy and registers all 275 `@mcp.tool` definitions to every AI session, even though only ~50 are actually MCP-callable per policy. That costs every Claude Code / Codex / Gemini session ~10-20 K tokens of schema budget for tools the agent will never use, and adds confusion ("which `inbox-*` tool do I use?"). The cleanup path is in the implementation tasks linked at the bottom of this document.

## Common violations and how to spot them

| Smell | Why it's wrong | Fix |
|---|---|---|
| One MCP tool that does fetch + parse + write | Tool is orchestrating a workflow (L4 → L3 leak); different sites/file types need different fetchers and the tool can't choose | Split into `extract` (atomic) and `save` (atomic). Agent picks the fetch path. See [agent-vs-mcp-examples.md](./agent-vs-mcp-examples.md) Example 2. |
| Slash command body says "call MCP tool X" as the first instruction | Skipping L3 — the body should describe the workflow; the agent decides when to call atomic ops | Rewrite body in terms of intent and let the agent route. Mention atomic tools by name where the agent will need them, not as imperative steps. |
| New tool added with `@mcp.tool` decorator by default | Forces MCP exposure for ops that are CLI-callable; bloats agent tool list | Default to plain `aug` subcommand. Add `@mcp.tool` only when the decision flowchart says so. |
| Dashboard calls a Python script directly | Violates CLAUDE.md rule 11 (dashboard never owns spawn/exec) | Move the op behind an MCP tool; call from `useMcpQuery` |
| Daemon classifies/edits content itself | Daemon became a second orchestrator (L1 → L3 leak) | Daemon triggers an AI session; the session does the work |
| Tool returns `{needs_llm: true, ...}` but caller is not an AI client | Mode-2 path missing | Implement Mode 2 per [llm-assisted-mcp-pattern.md](./llm-assisted-mcp-pattern.md) — spawn an AI session, retry |

## Appendix: MCP discovery-wrapper policy (resolves task #13)

ADR-734's spec deprecates auto-generated MCP wrappers "when AGENTS.md
and Browse are sufficient". That covers Claude Code, Codex, and Gemini
— all three read `commands/*.md` (or their generated agent-instruction
copies) directly, so the wrapper is redundant indirection.

For clients that **cannot** discover slash commands from `commands/*.md`
or an `AGENTS.md`/`GEMINI.md`-style file (e.g. OpenCode CLI), the wrapper
remains the only way for the user to invoke `/<command>`. These clients
get the wrapper.

**Concretely** — the "needs-wrapper" set today:

- `opencode` — minimal MCP-only client; no agent-instruction reader.
- Any future client matching the same pattern: stdio MCP server consumer,
  no instruction-file reader.

**NOT in the set** (these clients should NOT generate wrappers):

- `claude` / `claude-code` — reads `.claude/commands/*.md` natively.
- `codex` — reads `.codex/skills/<cmd>/SKILL.md` natively.
- `gemini` — reads `.gemini/skills/<cmd>/SKILL.md` natively.
- `cursor` / `windsurf` / `cline` / `copilot` — read project agent-md or
  their own command surfaces; do not need MCP-tool indirection.

The generator (`project-brain/capabilities/skills/ai/scripts/sync_agents/`) implements
this rule per-client. Adding a new client requires either (a) a natural
agent-instruction surface, or (b) explicit enrollment in the
needs-wrapper set with a TODO_CLEANUP marker tracking the eventual
removal once that client gains native support.

## Cross-references

Canonical sources for the architectural rules summarized here:

- [AI Client Execution Model](./ai-client-execution-model.md) — Augur as harness; the agent is the only orchestrator
- [Agent vs MCP Checklist](./agent-vs-mcp-checklist.md) — short checklist for placement decisions
- [Agent vs MCP Examples](./agent-vs-mcp-examples.md) — good-vs-bad concrete examples (especially Example 2: PDF ingestion)
- [LLM-Assisted MCP Pattern](./llm-assisted-mcp-pattern.md) — two-mode pattern for tools that need LLM help
- [Dispatch Escalation Pattern](./dispatch-escalation-pattern.md) — three-tier dispatch from dashboard
- [Agent Fetch Primitives](./agent-fetch-primitives.md) — vendor-neutral fetch options per content type (forthcoming)
- `docs/agent-topics/SKILLS.md` — skill directory layout
- `docs/agent-topics/ARCHITECTURE.md` — full architecture overview
- ADR-734 — Capability Surface Phase 3 (cleanup closure + drift guardrails)
- ADR-635, ADR-638 — Capability Inventory and Control Plane
- `config/system/capability_exposure.yaml` — per-capability policy entries (primary_surface, export_to)

## Compliance and drift

This matrix is enforced primarily through:

- ADR-734 drift guardrails (eight-dimension scanner)
- `auto-agent-config-parity` loop (per project_enforcement_layers memory)
- Pre-commit and pre-merge auto-loops in `/a-loops`
- Manual review when adding new skills (skill-creator template should default to CLI-only — pending [task #17])
