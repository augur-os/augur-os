# Contributing to Augur OS

Augur is in soft launch. Native macOS support is implemented, native Windows architecture is implemented, and Windows validation is still pending before we make a stronger public support claim.

This document is for contributors working against the current repo state, not a polished public release process.

## Code of Conduct

Be respectful and constructive in all interactions.

## License and Contribution Terms

Augur OS is licensed under the MIT License. By contributing, you agree that your changes will be licensed under the MIT License as well.

## Getting Started

### Prerequisites

- `git` for version control
- Python 3.11+ for scripts and utilities
- Node.js 22+ for the dashboard
- A GitHub account for contributions

### Fork & Clone

```bash
git clone https://github.com/YOUR_USERNAME/augur-os.git
cd augur-os
```

## Development Setup

### Install Dependencies

```bash
uv run aug onboard run
```

`aug onboard run` checks prerequisites (and prints the exact per-OS install command if `uv` or Node 22+ is missing — it does not install system tooling for you), installs dependencies, builds the dashboard, wires MCP, seeds a local brain, and verifies the system is up at <http://localhost:3000/browse>. See the [README Quickstart](README.md#working-locally) for the one-prompt alternative.

### Build & Verify

```bash
pytest tests/
pnpm --filter dashboard lint
pnpm --filter dashboard build
```

### Run Locally

Use the repo-managed dev workflow from an Augur AI-client session, for example `/dev-build`, when you need the dashboard. Then open `http://localhost:3000` once the workflow reports the dashboard is active.

## Project Structure

```
augur-os/
├── apps/
├── config/
├── docs/
├── packages/
├── plugins/
├── scripts/
├── skills/
├── src/
├── tests/
└── .github/
```

## Making Changes

Use focused branches and conventional commit messages.

Examples:

- `feat(knowledge): add semantic search module`
- `fix(scraper): handle URLs with special characters`
- `docs: update contributing guidelines`

## Creating a New Skill

Create the minimum required structure under `skills/{skill-name}/` and keep the skill self-contained.
