# Augur OS

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![CI](https://github.com/augur-os/augur-os/actions/workflows/ci-tests.yml/badge.svg)](https://github.com/augur-os/augur-os/actions/workflows/ci-tests.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Node 20+](https://img.shields.io/badge/node-20+-green.svg)](https://nodejs.org/)

[Website](https://augur.run) | [Documentation](https://augur.run/more.html) | [Sessions](https://augur.run/sessions.html) | [Roadmap](ROADMAP.md)

Technical review path: [Architecture Review](docs/technical-architecture-review.md) · [Architecture Overview](docs/architecture-overview.md) · [Connection Layer](docs/architecture-mcp-gateway.md)

> **Build a second brain on your laptop that your AI clients can operate.**
>
> Ingest your documents, compound them into a wiki, save prompts and skills, ask questions across your local knowledge. The same effective brain context works in Claude Code, Codex CLI, Gemini CLI, Cursor, and Copilot — no vendor lock-in, no Augur-managed API key by default, no cloud service.
>
> Augur is open source (MIT) and local-first. The technical architecture that makes this portable across clients is **the Harness** (see [docs/architecture-overview.md](docs/architecture-overview.md)); reviewers can start with [docs/technical-architecture-review.md](docs/technical-architecture-review.md). New here? Start with [docs/what-is-augur.md](docs/what-is-augur.md).

Augur OS is the public open-source repository for the Augur system. It is the technical home for the philosophy, architecture, install path, and implementation while Augur is in soft launch.

Augur is not a `.agent/` folder you copy into each project. It is not a generic LLM wrapper. You run Augur as the local harness underneath your native AI agents, then connect projects, documents, notes, skills, dashboard pages, and MCP commands to one control layer that every supported client can read. Direct model/API access from Augur code is a rare named exception, not the default product path.

Current support status:

- Native macOS support is implemented.
- Native Windows architecture is implemented.
- Windows validation is still pending before we make a firmer public support claim.
- The canonical roadmap lives at [ROADMAP.md](ROADMAP.md).

## What is Augur?

Augur authors the Harness once and projects it into every supported AI client. The Harness has five layers — the same five every modern AI client ships natively, just usually authored once per client and stuck there:

- **Constitution** — your project rules, conventions, repo map. Augur lands these as `CLAUDE.md`, `CODEX.md`, `AGENTS.md`, `.cursor/rules/augur.mdc`, `.github/copilot-instructions.md`, `.gemini/GEMINI.md`.
- **Skills** — modular expertise you write once in `project-brain/capabilities/skills/`. Augur generates `.claude/skills/`, `.codex/skills/`, `.gemini/skills/`, `.cursor/skills/`, and Copilot skill packs from that one source.
- **Hooks** — deterministic guardrails: `.githooks/` and `.pre-commit-config.yaml` fire for every client; per-client `.claude/settings.json` and `.codex/hooks.json` add tool-time enforcement.
- **Subagents** — bounded specialists with their own context and tools. Authored once, generated for `.claude/agents/`, `.codex/agents/`, `.cursor/agents/`.
- **Plugins** — bundled skills/agents/hooks/commands assembled into Claude plugin packages, Codex plugin packages, Gemini extensions, and Cowork DXT bundles by the AI skill's `sync_agents` plugin/package adapters.

Wrapping all five: a local **MCP server** (one trust boundary, every client connects to the same execution surface) and the **vault** (your durable second brain on your laptop).

Think of it as the local SDK and control plane for your personal AI stack — not a chat app, not the reasoning agent, not a cloud service.

## The Story

Most second brains start as folders, notes, and prompts. Augur is for the point where you take that second brain seriously enough to treat it like a software project: ADRs for decisions, CI for checks, tests for regressions, auto-loops for maintenance, and dashboards for observability.

Augur is the harness around that second brain. It lets your knowledge and skills ride on whichever native AI client is best for the job: Claude Code, Codex, Gemini, Cursor, Ollama-backed clients, private-model clients, or public-model clients, without rebuilding your setup around one vendor.

The target first-run story is simple: install Augur, add documents and notes, and let Augur start compounding. The target path is repo-first.
From there Augur starts compounding by indexing, summarizing, routing, and exposing that knowledge through MCP commands and dashboard pages.

## What You Can Do With Augur

- Connect notes, documents, and vault folders so agents can retrieve and compound them.
- Discover and install skills across AI clients, then expose them through MCP commands.
- Add OCR, document extraction, web capture, bookmark import, and source-card workflows.
- Ask your second brain questions while retained answers strengthen memory and wiki context.
- Build local dashboard pages and apps on top of the same MCP-backed system.
- Run adaptive loops for self-heal, code health, dependency audit, memory sync, and wiki maintenance.
- Work in airplane mode with Ollama or local models when cloud AI is unavailable or inappropriate.

## Demo

To see the kind of inspectable output Augur generates from your local knowledge base, install Augur and run:

```
/wiki reindex
/wiki report
```

This produces a self-contained HTML report ("What Your AI Knows About You") covering identity, brain contents, and patterns/blind spots — written to your local documents dir, no server required. A short ingest-to-`/ask` GIF is still a launch asset to record; it is not referenced here until that asset exists.

## Working Locally

```bash
npx create-augur@latest my-brain
cd my-brain
pnpm --filter dashboard dev
```

This repository is the source of truth for development and validation. The simplest current setup path is `create-augur`, which creates a repo-first full Augur workspace and installs the Python and Node dependency layers used by the MCP server and dashboard.

The dashboard runs at [localhost:3000](http://localhost:3000).

First brain workflow for a local release candidate:

1. Open `/brain` and confirm the Brain Inbox and Brain Insights cards are visible.
2. Open `/brain/inbox`, add a watched folder such as Desktop or Downloads, then run Scan before Consume.
3. Use Consume for valuable files; it routes supported documents through extraction, renaming, knowledge routing, RAG indexing, and wiki-update signaling.
4. Use Purge to Trash only for disposable candidates shown by the scan; it moves safe stale files to the OS trash and reports skipped files.
5. Open `/brain/insights` to inspect wiki freshness, retained `/ask` signals, inbox runs, and next actions.
6. Open `/browse?category=wiki` to read compiled wiki pages and use secondary actions from the overflow menu.

The release checklist for these surfaces lives in [docs/guides/wiki-llm-release-gate.md](docs/guides/wiki-llm-release-gate.md).

Manual clone remains useful for contributors who want direct control over bootstrap:

```bash
git clone https://github.com/augur-os/augur-os.git
cd augur-os
corepack enable && pnpm install && uv sync
pnpm --filter dashboard dev
```

The MCP/skills-only path is planned but not claimed as a working public install path yet. Until that mode is implemented, use the full repo-first setup when you need the local MCP server, generated client surfaces, indexes, and dashboard.

For Windows-specific validation, follow the repo scripts and the current platform notes rather than assuming public release readiness.

## Release Staging

`project-brain/capabilities/skills/` contains the repo's shared capability tree. User-owned private skills live in the configured personal brain under `capabilities/skills/`. Team-governed skills are part of the commercial team brain tier, not a claim that this OSS repo ships full enterprise governance.

Repo `staging/` is no longer a live surface. Release drafts live in the user vault under `drafts/staging/` until they are promoted into `project-brain/capabilities/skills/` or active private-vault skills.

Current repo inventory: 21 live repo skills, 0 repo-staged release skills. Release drafts now live in the user vault.

## Architecture

The full Harness story (5 layers, the Inversion, the Connection Layer, the runtime substrate) lives in [docs/architecture-overview.md](docs/architecture-overview.md). The diagram below shows the runtime substrate — what actually runs when the Harness fires and your AI client starts working:

```
+-----------------------------------------------------------+
|                    REASONING LAYER                         |
|        Claude - Codex - Gemini - Cursor - Ollama           |
+-----------------------------+-----------------------------+
                              |
+-----------------------------v-----------------------------+
|                    EXECUTION LAYER                         |
|        Skills - MCP commands - ingestion - search          |
|                                                           |
|   project-brain/capabilities/skills/  Shared project capabilities        |
|   src/mcp/           Local MCP server and tool gateway     |
|   .codex/.gemini     Generated client runtime surfaces    |
+-----------------------------+-----------------------------+
                              |
+-----------------------------v-----------------------------+
|                      KNOWLEDGE LAYER                       |
|       Notes - documents - memory - RAG - LLM Wiki          |
+-----------------------------+-----------------------------+
                              |
+-----------------------------v-----------------------------+
|                       OPS LAYER                            |
|          Dashboard - daemon - autoloops - health checks    |
+-----------------------------------------------------------+
```

For a deeper dive, see [docs/architecture-overview.md](docs/architecture-overview.md).

## Repository Structure

```
augur-os/
├── apps/dashboard/     # Next.js dashboard
├── config/             # System configuration
├── docs/               # Documentation and ADRs
├── packages/           # Shared JS packages
├── plugins/            # Platform integrations
├── scripts/            # Bootstrap and support scripts
├── project-brain/       # Project/core brain, including shared capabilities
├── staging/            # Future release payloads staged by release
├── src/                # Framework (CLI, config, MCP server)
├── tests/              # Repo-level tests
└── .github/            # CI/CD workflows
```

## CLI

```bash
aug discover                         # Full JSON manifest
aug discover --hub career --compact  # Filter by hub
aug <tool-name> [--param value ...]  # Run any tool
aug unified-search --query "health tracking"
aug --list-tools
```

## Built With

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11+, uv |
| MCP server | Python MCP SDK (stdio JSON-RPC) |
| Dashboard | Next.js 15, TypeScript, Tailwind CSS, shadcn/ui |
| Package manager | pnpm (workspaces) |
| Document processing | MarkItDown, ReportLab |
| AI clients | Claude Code, Codex, Gemini CLI, Cursor, Copilot, MCP-capable clients |

## Contributing

Contributions are welcome, but the project should be treated as soft launch work rather than a broadly public-ready release. See [CONTRIBUTING.md](CONTRIBUTING.md) for current workflow notes.

## License

MIT License. See [LICENSE](LICENSE).

## Augur Enterprise

Augur Enterprise is a separate, closed-source product that builds on this open-source runtime for organizational deployment — team brains, role brains, governance, multi-user compounding. This repository is the personal-tier runtime; Augur Enterprise is not in scope here.

See [augur.run](https://augur.run) for information on the Enterprise tier.
