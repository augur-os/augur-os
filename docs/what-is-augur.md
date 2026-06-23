# What is Augur?

Augur is a **local-first brain and harness runtime on your laptop that your AI clients can operate**. You ingest documents into it, it compounds them into a wiki, you save prompts and skills, you ask questions across your local knowledge, and the same effective brain context works in Claude Code, Codex CLI, Gemini CLI, Cursor, and Copilot.

Underneath, the technical architecture that makes this portable across clients is **the Harness** (see [architecture-overview.md](./architecture-overview.md)). The rest of this page explains what that means in practice, then what Augur isn't.

## What you actually do with Augur

After install, you operate Augur from your laptop in three places: the dashboard browse page, your AI client (Claude Code / Codex / Gemini / Cursor / Copilot), and the Augur CLI on the shell.

### The browse page is your home

The dashboard browse page (`/browse`) is where your second brain lives. The categories map to the nouns you actually use:

| Category | What lives there |
|---|---|
| **Inbox** | New documents waiting to be processed |
| **Notes** | Your written notes |
| **Sources** | Document folders you've connected (Desktop, Downloads, Notion, etc.) |
| **Wiki** | Compounded pages built from your ingested content |
| **Skills** | Modular expertise — yours and Augur-shipped |
| **Actions** | One-click operations skills expose |
| **Prompts** | Reusable prompt templates you saved |
| **Integrations** | Connected services (calendar, mail, etc.) |
| **Drafts / Archive** | Work-in-progress and stored content |

You don't memorize this — you open `/browse`, pick a category, and the AI client (or you) can act on it.

### The 11 onboarding milestones are the journey

Augur ships a Setup Completeness Widget in the dashboard sidebar that surfaces 11 milestones organized into three phases. It's not a one-time wizard — it tracks what's working and surfaces regressions over time.

**Foundation** — connect Augur to your laptop:
1. Index your machine — Augur discovers your AI clients and skills
2. Create or clone your vault — your durable local data root
3. Build your human profile — Augur learns your preferences

**Knowledge** — connect your data, watch the wiki compound:
4. Configure inbox folders — Augur watches these for new documents
5. Add document source folders — point Augur at your existing knowledge
6. Set wiki compounding queries — tell Augur what topics to compound
7. Get to ≥5 compounded wiki pages — the wiki starts being useful

**Personalization** — make Augur specifically yours:
8. Create a private skill — your own modular expertise
9. Save your first prompt — reusable prompt templates
10. Ask your first question (`/ask`) — query across everything you've ingested
11. Connect your first integration — calendar, mail, etc.

The widget quiets itself as you progress (full card → compact bar → tiny chip) and flips amber if something regresses (e.g., the vault disconnects).

### Day-to-day

Once you're past onboarding, your daily flow is:

1. New documents land in **Inbox** (or you drop them there)
2. Augur extracts, indexes, and routes them
3. The **Wiki** compounds — recurring concepts get their own pages
4. You ask questions via `/ask` in any AI client; the answer cites your own sources
5. The AI client uses your **Skills**, your **Prompts**, your **Constitution** — because the Harness landed all of those in every client

The Harness is the *means*. The browse page and the 11 milestones are the *experience*.

## Augur is not the default LLM executor

Augur is a harness layer. Its default job is to give your existing AI client the right context, tools, memory, skills, and guardrails, then let that client's native LLM do the reasoning.

Your existing AI client — Claude Code, Codex, Gemini, Cursor, Copilot — is the agent. Augur is the local infrastructure that makes that agent specific to your work.

Direct model/API access is the exception, not the product model. It is allowed only for explicitly approved internal tasks where the governing ADR, command, or config names the exception, the credential boundary is clear, and there is no better native-agent handoff. Normal user-facing reasoning, classification, summarization, wiki synthesis, and workflow orchestration use the active AI-client session.

## Augur is reactive

Augur reacts to your work — your commits, your files, your dashboard signals, your `/ask` queries — by maintaining the Harness. It does not autonomously act on your behalf. Your AI client does the acting; Augur made sure your AI client had what it needed.

This is a hard line: Augur is build-time + runtime infrastructure. The runtime LLM is your AI client by default. No autonomous outbound calls, no background agents, no cloud workers. Rare direct-LLM infrastructure tasks require explicit approval and should read like named exceptions, not hidden defaults.

## Augur converts general coding agents into personalized experts

Out of the box, Claude Code is generic. Codex is generic. Gemini CLI is generic. They know how to write code, but they don't know **your** codebase conventions, **your** skills, **your** vault layout, **your** project rules, **your** tools.

After Augur runs, the same general agent on your laptop is a domain expert on your work:

- It loads **your** constitution (project rules, conventions, repo map) at session start
- It can call **your** skills (modular expertise you authored) on demand
- It is bounded by **your** hooks (deterministic guardrails — auto-lint on write, block destructive commands)
- It can delegate to **your** subagents (specialists with their own context and tools)
- It ships **your** plugins (bundled skills/agents/hooks installable across your team)

The same Harness lands in every supported client. Switch from Claude Code to Codex — your constitution, skills, hooks, subagents, and plugins are already there because Augur generated each client's native format from one source.

## Bring your own AI

You use whatever AI client subscription you already pay for. Augur is unchanged when you switch vendors:

- **Claude Code subscription** — Augur lands `CLAUDE.md`, `.claude/skills/`, `.claude/agents/`, `.claude/settings.json`, MCP server config.
- **OpenAI Codex** — Augur lands `CODEX.md`, `.codex/skills/`, `.codex/agents/`, `.codex/config.toml`, plugin package.
- **Google Gemini CLI** — Augur lands `GEMINI.md`, `.gemini/skills/`, `.gemini/settings.json`, Gemini extension.
- **Cursor** — Augur lands `.cursor/rules/augur.mdc`, `.cursor/skills/`, `.cursor/mcp.json`.
- **GitHub Copilot CLI** — Augur lands `.github/copilot-instructions.md`, `.github/skills/`.

Also supported: Antigravity, Windsurf, OpenCode, Cline. The five above are the flagship integration paths.

## The split

| | Augur | Your AI client |
|---|---|---|
| **Role** | Harness, memory, tools, guardrails, local runtime | The runtime LLM |
| **Makes LLM calls?** | Default no; rare approved internal exceptions only | Yes |
| **Needs an API key?** | Not for normal use; exception tasks may need an explicit configured credential | Yes (your subscription) |
| **Where it runs** | On your laptop | Wherever you already pay for it |
| **What changes when you switch vendors** | Nothing | Everything |

Clean boundary. Augur doesn't replace your AI client — it harnesses and personalizes it.

## Brain layers in plain English

Augur separates context by scope. Global is Augur's shipped platform layer. User is your personal brain. Project is the repo-local brain for a specific codebase. Team is the commercial tier for organization-shared context and governance. Augur computes the effective context and projects it into each AI client.

## First ten minutes

Install per [getting-started.md](./getting-started.md). After install:

1. Point Augur at a project. The Harness generators run.
2. Open Claude Code (or Codex, or Gemini CLI) in that project.
3. The agent loads your constitution at session start. It can now see your skills, your project rules, your repo map, your conventions.
4. Ask it to do something specific to your work — refactor a module the way your codebase prefers, generate a skill scaffold matching your patterns, review against your hooks.
5. Watch a generic coding agent behave as a specialist because the Harness is in place.

The same project, opened in Codex tomorrow, gets the same behavior — because Augur already generated Codex's harness files alongside Claude's.

## What Augur is not

- Not an agent or general LLM wrapper
- Not a cloud service
- Not a per-project `.agent/` folder you copy around
- Not a vendor-locked memory system
- Not an enterprise product (see the bottom of [README.md](../README.md) for the separate closed-source product)

## See also

- [README.md](../README.md) — repository overview and install
- [docs/architecture-overview.md](./architecture-overview.md) — The Harness in detail (5 layers, runtime substrate, the Inversion)
- [docs/architecture-mcp-gateway.md](./architecture-mcp-gateway.md) — The Connection Layer (how Augur reaches every client)
- [docs/getting-started.md](./getting-started.md) — first install, first session
- [docs/vibe-coding.md](./vibe-coding.md) — building by directing your AI client, and the safe loop
