---
name: plugin-pack
x-augur-type: integration
x-augur-group: augur_admin
x-augur-release: r3
x-augur-license: MIT
description: 'Assemble and install Augur as a plugin for Claude Desktop (Cowork),
  OpenAI Codex, Gemini CLI, and GitHub Copilot. Covers: plugin pack, targets'
x-augur-tab: system
x-augur-tags:
- claude-desktop
- codex
- copilot
- gemini
- plugin
- distribution
x-augur-mcp-tools:
- get-skill-doc
- get-skill-health
- list-skill-actions
x-augur-dashboard-pages: []
x-augur-data-dir: plugin-pack
x-augur-config:
  contributions:
    blocks: []
x-augur-metadata:
  author: Augur
  version: 2.0.0
---





















# Plugin Pack

Assembles Augur as a native plugin for multiple AI platforms (ADR-442, ADR-503).

This is the canonical owner for the old `ops-pkg export` packaging flow. Keep packaging guidance here rather than in a separate top-level wrapper skill.

## Targets

| Target | Platform | Output Format |
|--------|----------|---------------|
| `cowork` | Claude Desktop | `.claude-plugin/plugin.json` + marketplace |
| `codex` | OpenAI Codex | `.codex-plugin/plugin.json` + `.agents/plugins/marketplace.json` |
| `gemini` | Gemini CLI | `gemini-extension.json` + `~/.gemini/extensions/augur` |
| `copilot` | GitHub Copilot | `.github/copilot-instructions.md` + agents, skills, prompts, MCP setup doc |

## Usage

```
/plugin-pack --target cowork           # Assemble for Claude Desktop
/plugin-pack --target codex            # Assemble for Codex
/plugin-pack --target gemini           # Assemble for Gemini CLI
/plugin-pack --target gemini --install # Assemble and install
/plugin-pack --target copilot          # Assemble for GitHub Copilot
/plugin-pack --target copilot --install # Copy generated .github assets into the repo
```

## Workflow

1. Select the target profile in `scripts/profiles.py` to filter what gets packaged.
2. Run `scripts/plugin_assembler.py` to collect skill metadata and apply the target formatter.
3. Let the formatter write the platform-specific plugin bundle for Cowork, Codex, Gemini, or Copilot.
4. Validate the output manifest before installing or publishing the assembled bundle.

## Cloud Sync (Claude Desktop regular chats)

Regular Claude Desktop chats do NOT read the locally installed
`local-desktop-app-uploads` bundle — that path only feeds Cowork agent
sessions. Regular chats serve a cloud copy from the claude.ai "My Uploads"
marketplace, which Desktop mirrors into `rpm/<plugin_id>/` and re-syncs at app
launch. This copy drifted silently for three months (P1, 2026-06-11).

**The push is part of the sync flow, not a separate ask.** claude.ai exposes
no token API for plugin upload, so a headless daemon cannot do it — but Augur
sync flows are agent-executed (rule 19), and the executing agent has the
Chrome MCP. When the user runs the cowork sync, complete ALL of this without
asking for further confirmation (running the sync command IS the approval):

1. `--target cowork --install` runs `formatters/cloud_staleness.py` after the
   local install. In sync (exit 0) → done. Stale → it builds
   `build/cowork/augur-cloud.zip` (top-level `augur/` folder, as the validator
   requires), prints a `cloud-plugin-push` JSON spec — drift reasons, zip path
   + size + sha256, and the discovered `upload_url` (org + marketplace ids
   read from this machine's rpm manifest) — and exits 3.
2. Executing agent: POST the zip as multipart field `file` to the spec's
   `upload_url` from the user's logged-in browser via the Chrome MCP
   (`javascript_tool` fetch on a claude.ai tab). claude.ai CSP blocks
   localhost fetches and large inline base64 corrupts silently — transfer the
   payload in ~2KB chunks stored on `window`, then **verify the in-page
   SHA-256 against the spec's sha256 before POSTing**. HTTP 200 returns the
   plugin record with the new `updated_at`.
3. Tell the user to fully restart Claude Desktop (it re-syncs `rpm/` at
   launch), then rerun the sync command — exit 0 is the confirmation the fix
   is live in regular chats.

## Validation Checklist

- Confirm the target is correct before packaging (`cowork`, `codex`, `gemini`, or `copilot`).
- Verify the output manifest path matches the target platform conventions.
- Check that the generated bundle exposes the expected skills and action metadata.
- Re-run packaging after any skill frontmatter change that affects discovery or routing.

## Directory Structure

```
skills/plugin-pack/
├── SKILL.md
├── scripts/
│   ├── plugin_assembler.py      # Shared assembly pipeline + CLI
│   ├── formatters/
│   │   ├── base.py              # BaseFormatter ABC
│   │   ├── cowork.py            # Claude Desktop formatter
│   │   ├── codex.py             # Codex plugin formatter
│   │   ├── copilot.py           # GitHub Copilot .github asset formatter
│   │   └── gemini.py            # Gemini CLI extension formatter
│   └── profiles.py              # Per-target filter profiles
├── assets/
│   └── templates/               # Hub-specific SKILL.md overrides
└── augur/
    └── tests/
```

## Dashboard Surface

The `/command/plugin-pack` page renders live skill health, registered action metadata,
and the current SKILL.md overview through the generic skill MCP tools. It also
documents the supported packaging targets and the assembly pipeline so the page is
useful even when no packaging job is currently running.

## API

| Route | Method | Description |
|-------|--------|-------------|
| `/api/plugin-pack` | GET | Read-only summary of plugin-pack health, actions, overview text, targets, and assembly pipeline |

## Additional resources
- [evals/rank.json](evals/rank.json)
- [evals/evals/rank.json](evals/evals/rank.json)
- [augur/data/.gitkeep](augur/data/.gitkeep)
- [evals/evals.json](evals/evals.json)
- [references/.gitkeep](references/.gitkeep)
