# Skills Architecture

Skills are Augur's modular capability units. A skill can carry instructions, scripts, commands, MCP tools, dashboard pages, actions, tests, references, and packaging metadata, then be projected into every supported AI client.

```
project-brain/capabilities/skills/example/
  SKILL.md              # instructions, frontmatter, tool/action metadata
  commands/             # slash command docs and argument contracts
  scripts/              # deterministic Python/TS/shell implementation
  references/           # deeper docs loaded on demand
  assets/               # templates, seeds, fixtures, static inputs
  examples/             # example inputs/outputs
  evals/                # skill-specific evaluations
  agents/               # subagent definitions for cross-client sync
  augur/
    actions/            # dashboard/action definitions
    tests/              # skill-owned tests
    pages/              # config-driven dashboard pages (ADR-491)
    dashboard/          # source UI where the local contract allows it
```

## Skill file structure

`SKILL.md` is the entry point. It should stay concise and point to deeper files when a workflow needs detail. The surrounding directories provide deterministic behavior and reusable assets:

- `commands/` defines slash commands and their exported UX.
- `scripts/` implements atomic operations, scans, fixes, and helpers.
- `references/` stores long-form instructions.
- `agents/` stores role definitions that `sync_agents` can adapt across clients.
- `augur/actions/` and `augur/pages/` feed dashboard browse/action surfaces.

## Skill Placement Across Brain Tiers

Skills are authored in brain-owned `capabilities/skills/` roots and projected into client-native locations.

| Tier | Canonical skill root | Boundary |
|---|---|---|
| Global | Augur core `project-brain/capabilities/skills/` in this repo | Open-source shipped capabilities |
| User | configured personal brain `capabilities/skills/` | private user skills |
| Team | managed team brain `capabilities/skills/` | commercial shared/governed skills |
| Project | `<repo>/project-brain/capabilities/skills/` | repo-local skills and overrides |

Client-specific folders such as `.codex/skills/`, `.claude/skills/`, and `.gemini/skills/` are generated or adopted surfaces, not the durable source of truth for Augur-managed skills.

## Skill frontmatter contract

Skill frontmatter declares how the skill participates in Augur:

| Field | Purpose |
|---|---|
| `name` and `description` | Standard Agent Skills identity and discovery |
| `x-augur-type` | Skill type (domain, command, routine, …) |
| `x-augur-group` | Capability group (brain, dev, life, …) for packaging and Browse grouping |
| `x-augur-tab` | Browse tab the skill's items surface under |
| `x-augur-release` | Release tier that enables the skill (e.g. `mvp`) |
| `x-augur-mcp-tools` | Deterministic MCP tool declarations |
| `x-augur-commands` | Slash-command declarations owned by the skill |
| `x-augur-dashboard-pages` | Workspace page declarations (admit the skill to the dashboard) |
| `x-augur-config` | Config and data contributions |

Fields are top-level `x-augur-*` keys. The hub concept and the `x-augur-hub` field were removed (ADR-802): a skill is admitted to the dashboard by declaring `x-augur-dashboard-pages`, and grouping is by `x-augur-group` / `x-augur-tab`. This contract differs from vault note frontmatter — skill metadata is packaging and routing metadata; user note metadata is durable content metadata.

## Bundle assembly pipeline

The bundle pipeline reads the effective skill set, filters it by release profile, adapts the skill markdown, and writes client-native packages. ADR-522 and ADR-567 established the multi-target plugin package shape; ADR-670 and ADR-671 moved the Harness toward an effective source projected into many clients.

The assembler is intentionally format-aware. It does not copy the same folder blindly into every client. It strips unsupported fields, resolves platform manifests, and writes the client's expected plugin structure.

## Plugin Package Multi-Target Assembly

The current MVP release keeps package assembly with the AI skill's client adapters:

- `project-brain/capabilities/skills/ai/scripts/sync_agents/adapters/codex_plugin.py`
- `project-brain/capabilities/skills/ai/scripts/sync_agents/adapters/gemini_plugin.py`
- `project-brain/capabilities/skills/ai/scripts/sync_agents/adapters/cowork.py`
- `project-brain/capabilities/skills/ai/augur/adapters/_plugin_pack.py`

Each target has a formatter and filter profile. The formatter writes the target manifest, MCP config, skills, commands, and marketplace metadata. `sync_agents` is therefore both the local projection surface and the release-visible packaging implementation.

## Skill group and release enablement

Skill groups (`x-augur-group`) determine which capability families ship together and which user surfaces see them. The group assignment is not cosmetic: it controls Browse grouping, generated instruction surfacing, and enterprise/shared overlay behavior.

Release profiles can include or exclude skills by release tier (`x-augur-release`), group, prefix, or explicit skill name. This keeps personal-tier, team, and client-specific distributions from exposing every internal capability by default.

## Skill discovery

Discovery is file-based. Augur scans shared skills, configured private-vault skills, generated manifests, and client adapter outputs. The dashboard uses skill manifests and generated registries; AI clients receive generated skill stubs or native skill folders.

`docs/generated/skill-manifest.json` is the committed inventory. `docs/generated/skill-registry.md` is convenience output and not the canonical committed source.

## Implementation pointers

- `project-brain/capabilities/skills/README.md` documents shared skill placement.
- `src/config/paths.py` resolves shared and private skill roots.
- `project-brain/capabilities/skills/ai/scripts/sync_agents/` owns local client projection.
- `project-brain/capabilities/skills/ai/scripts/sync_agents/adapters/` and `project-brain/capabilities/skills/ai/augur/adapters/` own client package assembly.
- See [architecture-sync-agents.md](./architecture-sync-agents.md) for client projection and [architecture-capability-exposure.md](./architecture-capability-exposure.md) for tool exposure policy.
