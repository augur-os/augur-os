# Developer Guide

This guide covers the current development workflow for Augur.

Augur is currently in soft launch, so this guide reflects the current repo state and validation workflow rather than a finished public-release surface.

## Where to author each Harness layer

Augur's architecture is the [Harness](./architecture-overview.md#the-harness) — five layers projected into every supported AI client. When you contribute to Augur, you author one of these layers; the [Connection Layer](./architecture-mcp-gateway.md) generates the per-client output.

| Harness layer | Where you author it | Generator that projects it per client |
|---|---|---|
| Constitution | `docs/agent-topics/agent-rules.md` (general) + project rules | `sync_agents` adapters |
| Skills | `project-brain/capabilities/skills/<skill-name>/SKILL.md` (+ scripts, modules, references) | `sync_agents` adapters |
| Hooks | `.githooks/`, `.pre-commit-config.yaml`, per-client hook entries | git natively (cross-agent); `sync_agents` (per-client) |
| Subagents | `project-brain/capabilities/skills/<skill-name>/agents/` | `sync_agents` adapters |
| Plugins | `project-brain/capabilities/skills/<skill-name>/` plus release/profile metadata | `sync_agents` plugin/package adapters |

If you're adding a new skill, see [creating-skills.md](./creating-skills.md). If you're adding a new client adapter, look at existing adapters in `project-brain/capabilities/skills/ai/scripts/sync_agents/` for the pattern.

## Bootstrap

Start from the repo directly:

```bash
git clone https://github.com/augur-os/augur-os.git
cd augur-os
corepack enable
pnpm install
uv sync
```

For local dashboard work:

```bash
pnpm --filter dashboard dev
```

## Repository Structure

The current repo is organized around a cross-platform core plus skill-owned extensions:

```text
augur-os/
├── apps/dashboard/      # Next.js dashboard shell
├── config/              # System configuration
├── docs/                # Canonical documentation
├── packages/            # Shared JS packages
├── plugins/             # Platform and integration adapters
├── project-brain/       # Project/core brain, including shared capabilities
├── scripts/             # Bootstrap and support scripts
├── src/                 # Core Python config, MCP, and libraries
└── tests/               # Repo-level tests
```

## Creating A Skill

Create shared/project skills under `project-brain/capabilities/skills/<skill-name>/`. User-private skills live in the configured personal brain `capabilities/skills/<skill-name>/`; team-governed skills belong to the commercial team brain tier.

See [creating-skills.md](creating-skills.md) for the canonical skill structure and authoring rules.

At a minimum, keep each skill self-contained:

```text
project-brain/capabilities/skills/<skill-name>/
├── SKILL.md
├── references/
├── scripts/
├── assets/
└── augur/
    ├── tests/
    └── dashboard/   # optional
```

If a skill exposes UI, the source of truth lives with the skill and is mounted into the dashboard shell.

## Testing

Use `uv` so tests run with the repo-managed Python environment:

```bash
uv run pytest
uv run pytest tests/
```

When you touch dashboard code, run the dashboard checks too:

```bash
pnpm --filter dashboard lint
pnpm --filter dashboard build
```

## Release Posture

The roadmap and release posture are still soft-launch scoped. Treat release docs, support claims, and platform statements as part of that external story rather than as a fully public product pipeline.

## Best Practices

- Keep `SKILL.md` focused and concise.
- Use `src/config/paths.py` instead of hardcoded data paths.
- Keep user data outside the repo-managed code surface.
- Prefer small, reviewable changes over broad rewrites.
- Update docs when platform support or release posture changes.
