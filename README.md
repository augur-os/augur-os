# Augur OS

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![CI](https://github.com/augur-os/augur-os/actions/workflows/ci-tests.yml/badge.svg)](https://github.com/augur-os/augur-os/actions/workflows/ci-tests.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Node 20+](https://img.shields.io/badge/node-20+-green.svg)](https://nodejs.org/)

[Website](https://augur.run) | [Documentation](https://augur.run/more.html) | [Sessions](https://augur.run/sessions.html) | [Roadmap](ROADMAP.md)

> Augur OS is the open-source local second-brain harness for the AI clients you already use.

Current state (April 2026):

- Runs natively on macOS today.
- Windows architecture is complete; validation is in flight before a firmer public support claim.
- MVP release targets May 2026. See [ROADMAP.md](ROADMAP.md) for the full release plan.

AI clients are the reasoning engines. Claude, Codex, Gemini, Cursor, and Ollama can connect through local MCP while Augur keeps memory, skills, tools, workflows, approvals, and automation on your machine.

Augur is not an LLM wrapper and does not require an Augur API key. Bring the AI subscriptions or local models you already use; Augur gives them one durable local harness to work against.

## What is Augur?

Augur is an open-source personal AI OS and second-brain harness. It gives your AI clients a shared skill layer, a persistent knowledge base, governed local tools, and a local dashboard.

Think of it as `.bashrc` for your AI: configure with text files, debug with `cat`, version with `git`.

### Key Features

- **Composable skill library** across the adaptive, brain, career, command, life, and studio hubs.
- **MCP-native** tooling exposed over local Model Context Protocol.
- **Local dashboard** for humans and agents.
- **Ingest pipeline** for OCR, document extraction, web scraping, and bookmark import.
- **LLM Wiki** synthesized from ADRs, memory, and sessions.
- **Multi-client** support for Claude Code, Codex, Gemini CLI, Cursor, Copilot, and Ollama.
- **Autoloops** for self-heal, code health, dependency audit, and memory sync.
- **Airplane mode** for offline operation with Ollama or local models.

## Working Locally

This repository is the source of truth for development and validation. Treat the repo-first workflow as canonical for now, and treat platform-specific installers as validation paths rather than a broad public-ready install story.

```bash
git clone https://github.com/augur-os/augur-os.git
cd augur-os
corepack enable && pnpm install && uv sync
pnpm --filter dashboard dev
```

The dashboard runs at [localhost:3000](http://localhost:3000).

For Windows-specific validation, follow the repo scripts and the current platform notes rather than assuming public release readiness.

## Architecture

```
+-----------------------------------------------------------+
|                    REASONING ENGINES                       |
|           (AI clients you choose and subscribe to)         |
| Claude · Codex · Gemini · Cursor · Copilot · Ollama       |
+-----------------------------+-----------------------------+
                              |
+-----------------------------v-----------------------------+
|                       MCP GATEWAY                          |
|        Single execution surface for human and agent        |
+-----------------------------+-----------------------------+
                              |
+-----------------------------v-----------------------------+
|                    EXECUTION LAYER                         |
|                                                            |
|   Skills                User · Project · Client            |
|   Wiki + Ingest         Concept-first compiler             |
|   Browse                Workbench surfaces                 |
|   Vault                 Local files, allowlisted           |
+-----------------------------+-----------------------------+
                              |
+-----------------------------v-----------------------------+
|                       OPS LAYER                            |
|   Autoloops · Approvals · Audit log · Health checks       |
|   Security autoloop: S1–S5 + Tank CLI                      |
+-----------------------------------------------------------+
                              |
          +-------------------+-------------------+
          |                   |                   |
     CLI (aug)          MCP Server          Dashboard
                                         localhost:3000
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
├── skills/             # Curated skill library across six hubs
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
| AI clients | Claude Code, Codex, Gemini CLI, Cursor, Copilot |

## Contributing

Contributions are welcome ahead of the May 2026 MVP. See [CONTRIBUTING.md](CONTRIBUTING.md) for the current workflow notes and scope.

## License

MIT License. See [LICENSE](LICENSE).
