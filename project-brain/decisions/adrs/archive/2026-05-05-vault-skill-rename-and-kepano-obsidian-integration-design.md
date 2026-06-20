---
title: Vault Skill Rename + kepano/obsidian-skills Integration
date: 2026-05-05
status: draft
owners: gsannikov
related_adrs:
  - ADR-270  # Vault path contract
  - ADR-563  # Vault-Owned User Skills
  - ADR-567  # Bundle Architecture Phase 0
  - ADR-569  # Framework Server Split
  - ADR-570  # Visibility Filter Removal
---

# Vault Skill Rename + kepano/obsidian-skills Integration

## Summary

Rename the `obsidian` vault-tier skill to `vault` to match its actual purpose
(`x-augur-integration-type: vault`), free the `obsidian-*` namespace for
authoritative reference skills from `kepano/obsidian-skills`, and integrate
those reference skills across all five AI clients (Claude Code, Codex,
Gemini, OpenCode, Copilot) via Augur's existing client-sync pipeline.

After this work the user has:

- **`vault`** skill — Augur's vault-integration skill (MCP tools, ADR-270 path
  contract, dashboard tile, hub/tab routing). Body cross-references kepano's
  reference skills for syntax.
- **kepano's reference skills** — `obsidian-markdown`, `obsidian-bases`,
  `obsidian-cli`, `json-canvas`, `defuddle`. Authoritative format docs by
  Obsidian's CEO. Vendored centrally, distributed to each client by Augur's
  sync adapters.

## Motivation

The current `obsidian` skill at `~/Projects/Au-vault/skills/obsidian/` is
misnamed. Its own frontmatter declares `x-augur-integration-type: vault` and
its body explicitly states "Obsidian is opt-in. The vault at
`get_vault_dir()` works without Obsidian installed." It is a vault skill that
happens to know about Obsidian's flavor, not an Obsidian skill.

Installing `kepano/obsidian-skills` (28k stars, authored by Obsidian's CEO)
across all clients creates a name collision: agents would have to choose
between `obsidian` (Augur's vault integration) and `obsidian-markdown` /
`obsidian-bases` / `obsidian-cli` (kepano's reference skills) for overlapping
prompts like "edit a note." The kepano skills are authoritative for
Obsidian's syntax surface; Augur's skill should not squat on the bare
`obsidian` name.

Renaming resolves the collision at the root, aligns naming with
architectural classification, and is future-proof if the vault viewer
changes (Logseq, plain markdown, etc.).

## Goals

1. Rename the vault-tier skill `obsidian` → `vault` everywhere it appears
   (vault bundle, MCP server, registry, tests, dashboard wiring,
   onboarding).
2. Slim the renamed `vault` skill body to integration content only,
   removing the duplicate Obsidian markdown stub.
3. Vendor `kepano/obsidian-skills` as a git submodule under
   `vendor/skills/obsidian-skills/`.
4. Extend `sync_agents` to distribute vendored external skills to all five
   client surfaces (Claude Code via marketplace, Codex/OpenCode via file
   copy, Gemini via existing converter, Copilot via instructions
   converter).
5. Add cross-references from the `vault` SKILL.md to kepano's reference
   skills so agents discover authoritative format docs.

## Non-goals

- Forking, modifying, or republishing kepano's skill content.
- Adding new MCP tools for Bases or Canvas. Tools that read/write the
  vault already exist; format-specific tooling is out of scope.
- Replacing the existing TypeScript Obsidian plugin at `plugins/obsidian/`.
- Refactoring the vault adapter, markdown flavor converter, or onboarding
  flow beyond what the rename mechanically requires.
- Decomposing the `vault` skill into smaller skills.

## Current state

### Source of truth for the `obsidian` skill

The canonical SKILL.md lives at
`~/Projects/Au-vault/skills/obsidian/SKILL.md` (vault-owned user skill per
ADR-563). Generated outputs appear at:

- `.opencode/skills/obsidian/SKILL.md`
- `.gemini/skills/obsidian/SKILL.md`
- (Claude Code consumes via marketplace plugin distribution.)

The bundle directory `~/Projects/Au-vault/skills/obsidian/` contains
`augur/`, `evals/`, `references/`, `scripts/`, and `SKILL.md`.

### What depends on the name `obsidian`

| Component | Path | Role |
|---|---|---|
| Vault skill bundle | `~/Projects/Au-vault/skills/obsidian/` | SKILL.md + augur/evals/references/scripts |
| MCP server | `config/system/mcp_servers.yaml` (`augur-obsidian`) | Defines 7 vault MCP tools |
| Vault-tier registry | `src/mcp/augur_shared/skill_registry.py` | `VAULT_SKILL_NAMES` includes `obsidian` |
| Architecture test | `tests/architecture/test_no_vault_skill_refs.py` | Pinned `VAULT_SKILL_NAMES` list |
| Bundle server entry | `python -m augur_shared.bundle_server obsidian` | Per-bundle MCP server |
| Onboarding platform | `skills/onboard/augur/data/platforms.yaml` | `obsidian:` platform entry |
| Browse CLI probe | `src/mcp/augur_framework/tools/infrastructure/browse/cli.py` | `skill == "obsidian"` (`.obsidian/` directory probe — keep this string, see notes) |
| Vault adapter | `skills/ai/scripts/sync_agents/vault_adapters/obsidian.py` | Vault sync adapter (filename references the *flavor*, not the skill) |
| Markdown flavor converter | `skills/ai/scripts/markdown_flavors.py` | `plain_to_obsidian`, `obsidian_to_plain` (flavor names — keep) |
| Tests | 14 files (see Migration table below; 12 require changes, 2 conditional) | Reference skill name and bundle |
| Generated registries | `docs/generated/skill-manifest.json`, `launch-skill-inventory.json`, `skill-release-matrix.json` | Auto-regen from source |
| RAG quality baseline | `skills/rag/assets/seeds/quality_baseline.yaml` | "obsidian vault integration" probe |
| Dashboard contributions | SKILL.md frontmatter `x-augur-config` | Tile `/brain/obsidian/vault` |

## Design

### Phase 1 — Rename `obsidian` → `vault`

The rename is mechanical for most touch points but requires three semantic
decisions:

#### Decision 1: MCP tool prefix

All seven tools rename to the `vault-*` prefix. The skill is named
`vault`; consistency outweighs the implementation detail that two tools
happen to know about Obsidian-specific artifacts.

| Old | New |
|---|---|
| `obsidian-read` | `vault-read` |
| `obsidian-write` | `vault-write` |
| `obsidian-search` | `vault-search` |
| `obsidian-status` | `vault-status` |
| `obsidian-health-repairs` | `vault-health-repairs` |
| `obsidian-scaffold` | `vault-scaffold` |
| `obsidian-convert` | `vault-convert` |

The MCP server is renamed: `augur-obsidian` → `augur-vault`. All seven
tools live under the `augur-vault` server.

Note: `vault-scaffold` still writes `.obsidian/` config files in its
current implementation, and `vault-convert` still handles
Obsidian-flavored markdown conversion. The rename is at the tool-name
layer; implementation behavior is unchanged.

#### Decision 2: Bundle directory move

`~/Projects/Au-vault/skills/obsidian/` → `~/Projects/Au-vault/skills/vault/`.

This is a real disk move (`git mv` inside the vault repo). The bundle
contents (`augur/`, `evals/`, `references/`, `scripts/`, `SKILL.md`) move
intact.

#### Decision 3: Browse CLI probe and flavor names

Two places legitimately keep the literal string `"obsidian"`:

- `browse/cli.py` checks for the presence of the `.obsidian/` directory
  (file-system probe — string is the directory name, not the skill name).
- `markdown_flavors.py` exposes `plain_to_obsidian` / `obsidian_to_plain`
  (functions named after the flavor, not the skill).

These are unaffected by the rename. Architecture test allowlist already
documents this.

#### Rename surface

| File / location | Change |
|---|---|
| `~/Projects/Au-vault/skills/obsidian/` | `git mv` → `~/Projects/Au-vault/skills/vault/` |
| `~/Projects/Au-vault/skills/vault/SKILL.md` | Update `name: obsidian` → `name: vault`. Update dashboard page id/title (Phase 4 reuses this file). |
| `config/system/mcp_servers.yaml` | Rename server `augur-obsidian` → `augur-vault`. Update tool entries (5 renamed, 2 kept). |
| `src/mcp/augur_shared/skill_registry.py` | `VAULT_SKILL_NAMES` swap `obsidian` → `vault`. Any helper functions that check `name == "obsidian"`. |
| `tests/architecture/test_no_vault_skill_refs.py` | Update pinned `VAULT_SKILL_NAMES` list. |
| `skills/onboard/augur/data/platforms.yaml` | Rename platform key `obsidian:` → `vault:`. Update `setup_tool: obsidian-scaffold` → `setup_tool: vault-scaffold`. Update `getting_started` text to drop the "Open Obsidian" framing (the vault works without Obsidian; users who want Obsidian viewing run `vault-scaffold`). Detection rule may need rewording from "obsidian vault configured" → "vault configured". |
| `skills/onboard/SKILL.md` | Update `--connect <platform>` listing: `obsidian` → `vault`. **User-facing CLI change**: `augur onboard --connect obsidian` becomes `augur onboard --connect vault`. |
| `skills/onboard/references/mode-connect.md` | Update all `--connect obsidian` and `--from obsidian` references to `--connect vault` / `--from vault`. Drop "Obsidian" framing where it confuses platform-vs-skill distinction. |
| Test files (12) | Update references — see Migration table. |
| Generated registries | Regenerate after source changes. |
| RAG quality baseline | Update probe text from "obsidian vault integration" to "Augur vault integration" or split into two probes. |

#### Migration table — tests

| Test | Required change |
|---|---|
| `tests/architecture/test_no_vault_skill_refs.py` | Update `VAULT_SKILL_NAMES` |
| `tests/cli/test_bundle_server_obsidian.py` | Rename file → `test_bundle_server_vault.py`; update `OBSIDIAN_BUNDLE` constant; update `bundle_server obsidian` invocation → `bundle_server vault` |
| `tests/dashboard/scripts/generate-block-registry.test.ts` | Update string fixtures |
| `tests/dashboard/surfaces/classifySurface.test.ts` | Update fixture skill names |
| `tests/dashboard/surfaces/buildSurfaceInventory.test.ts` | Update fixtures |
| `tests/packages/augur-mcp/infrastructure/test_browse_vault_integrations.py` | Update expected skill name |
| `tests/test_onboard_state.py` | Update expected skill mapping (platform `obsidian` → skill `vault`) |
| `tests/scripts/test_install_flags.py` | Update `--connect obsidian` flag expectations if any reference the skill |
| `tests/scripts/test_platform_plugins.py` | Update plugin-platform mapping |
| `tests/mcp/test_shared_config_paths.py` | Update path expectations |
| `tests/src/test_paths.py` | Update path expectations |
| `skills/ai/augur/tests/test_obsidian.py` | Rename file → `test_vault.py`; update references |
| `skills/ai/augur/tests/test_vault_adapters.py` | Update if references skill name (vault adapter file itself stays `vault_adapters/obsidian.py` — flavor name) |
| `skills/ai/augur/tests/test_markdown_flavors.py` | No change (flavor functions unchanged) |

### Phase 2 — Vendor kepano/obsidian-skills

Add as a git submodule pinned to a specific tag/SHA:

```
git submodule add https://github.com/kepano/obsidian-skills.git vendor/skills/obsidian-skills
git -C vendor/skills/obsidian-skills checkout <pinned-sha>
```

Pin to a specific commit (not a moving branch). Updates are deliberate via
`git -C vendor/skills/obsidian-skills checkout <new-sha>` followed by
re-sync.

Layout after vendoring:

```
vendor/skills/obsidian-skills/        ← git submodule (pinned)
  .claude-plugin/                     ← Claude Code plugin manifest
  LICENSE
  README.md
  skills/
    obsidian-markdown/SKILL.md
    obsidian-bases/SKILL.md
    json-canvas/SKILL.md
    obsidian-cli/SKILL.md
    defuddle/SKILL.md
config/external_skills.yaml           ← new — declares vendored bundles
```

`config/external_skills.yaml` schema (new file):

```yaml
external_skill_bundles:
  - id: kepano-obsidian-skills
    source: vendor/skills/obsidian-skills
    upstream: https://github.com/kepano/obsidian-skills
    pinned_sha: <sha>
    skills:
      - obsidian-markdown
      - obsidian-bases
      - obsidian-cli
      - json-canvas
      - defuddle
    targets:
      claude_code: marketplace
      codex: file_copy
      opencode: file_copy
      gemini: convert_and_copy
      copilot: convert_to_instructions
```

### Phase 3 — Distribute to all five clients

Extend `skills/ai/scripts/sync_agents/` to consume `external_skills.yaml`.
Add a new `distribute_external_skills()` method on `BaseAdapter`. Each
adapter implements its target mode:

#### Claude Code

Register `vendor/skills/obsidian-skills/` as an additional marketplace in
the existing `augur-skills` marketplace config. The user runs once:

```
/plugin install obsidian-markdown@obsidian-skills
/plugin install obsidian-bases@obsidian-skills
/plugin install obsidian-cli@obsidian-skills
/plugin install json-canvas@obsidian-skills
/plugin install defuddle@obsidian-skills
```

Updates flow through Claude Code's `/plugin update`. No `.claude/skills/`
directory writes — Claude Code's adapter does not manage that path.

#### Codex / OpenCode

Plain file copy — kepano follows the AgentSkills.io spec, which both
clients consume natively.

| Client | Target |
|---|---|
| Codex | `.codex/skills/obsidian-markdown/SKILL.md` ... |
| OpenCode | `.opencode/skills/obsidian-markdown/SKILL.md` ... |

Adapter copies each `vendor/skills/obsidian-skills/skills/<name>/`
directory wholesale (preserves `references/` subdirectories).

#### Gemini

Reuse the existing SKILL.md → Gemini converter that already produces
`.gemini/skills/obsidian/SKILL.md` from your bundle. Apply it to each
kepano skill to produce `.gemini/skills/obsidian-markdown/`,
`.gemini/skills/obsidian-bases/`, etc. The directory is gitignored
(per existing rule).

#### Copilot

Reuse the existing SKILL.md → `.github/instructions/*.instructions.md`
converter. Output:

```
.github/instructions/obsidian-markdown.instructions.md
.github/instructions/obsidian-bases.instructions.md
.github/instructions/obsidian-cli.instructions.md
.github/instructions/json-canvas.instructions.md
.github/instructions/defuddle.instructions.md
```

#### Update workflow

```
git -C vendor/skills/obsidian-skills checkout <new-sha>
sync agents all
```

For Claude Code: standard `/plugin update`.

### Phase 4 — Slim the `vault` skill body and add cross-references

Rewrite `~/Projects/Au-vault/skills/vault/SKILL.md` body. Target ~25 lines
of actual content (down from ~30, but with no dead weight).

Keep verbatim:

- All `x-augur-*` frontmatter (update name to `vault`, dashboard page id
  if desired).
- ADR-270 path contract: `get_vault_dir()` IS the vault.
- MCP tool list (all seven renamed to `vault-*` prefix).
- Scaffold instruction (now invokes `vault-scaffold`).

Remove:

- The "Obsidian Markdown Syntax" 5-bullet stub (replaced by kepano's
  authoritative `obsidian-markdown` skill).
- The "Additional resources" `.gitkeep` placeholder list (signal-free).

Add a "Related skills" section with cross-references to kepano:

```markdown
## Related skills

For Obsidian-specific syntax and formats, use the dedicated skills:

- `obsidian-markdown` — wikilinks, embeds, callouts, properties, all
  Obsidian-flavored markdown syntax.
- `obsidian-bases` — `.base` files (database views, filters, formulas).
- `json-canvas` — `.canvas` files (JSON Canvas spec).
- `obsidian-cli` — `obsidian` CLI for vault operations and plugin/theme
  development.
- `defuddle` — extract clean markdown from web pages.

This skill (`vault`) handles read/write/search and integration with the
Augur vault. Format-specific knowledge lives in the skills above.
```

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Rename misses a hardcoded `"obsidian"` string somewhere unexpected and a runtime path breaks. | Architecture test (`test_no_vault_skill_refs.py`) is precisely designed to catch this. Run after every change. Include a grep verification step in the implementation plan. |
| Vault directory rename breaks open Obsidian / live sessions. | Coordinate the disk move when no live AI client owns the path (per CLAUDE.md rule 24). Document in plan. |
| MCP tool rename breaks existing user prompts / scripts that called `obsidian-read` etc. by name. | Acceptable — agents discover tools by current name. No backwards-compatibility shim per project rule 14. Document the new tool names in CHANGELOG. |
| Gemini converter mishandles kepano's syntax (callouts, properties, math, mermaid). | Smoke-test conversion of each kepano SKILL.md after first sync. Diff vs upstream for fidelity check. |
| Claude Code marketplace install requires manual user action — could be missed. | Document in the implementation plan output. Verify with `/plugin list` after install. |
| Submodule pinning vs. floating-branch drift. | Pin to specific SHA in `external_skills.yaml`. Updates require explicit SHA bump. |
| Copilot converter produces low-quality output for format-heavy skills (Bases tables, Canvas JSON examples). | Spot-check the generated `.instructions.md` files. If poor, accept Copilot as best-effort target (lowest priority of the five clients). |
| User-facing CLI change (`--connect obsidian` → `--connect vault`) breaks any external scripts, docs, or muscle memory that called the old form. | Document in CHANGELOG. No backwards-compat alias per project rule 14 (no compatibility shims). Search docs and external references before merging. |

## Success criteria

1. `~/Projects/Au-vault/skills/vault/SKILL.md` exists; the old
   `~/Projects/Au-vault/skills/obsidian/` is deleted.
2. `python -m augur_shared.bundle_server vault` starts and lists tools.
3. `mcp_servers.yaml` declares `augur-vault` server with `vault-read`,
   `vault-write`, `vault-search`, `vault-status`, `vault-health-repairs`,
   `vault-scaffold`, `vault-convert`.
4. `tests/architecture/test_no_vault_skill_refs.py` passes.
5. All 14 listed test files pass.
6. Generated registries (`skill-manifest.json`,
   `launch-skill-inventory.json`, `skill-release-matrix.json`) contain
   `vault`, not `obsidian`.
7. `vendor/skills/obsidian-skills/` exists as a submodule pinned to a
   specific SHA.
8. `config/external_skills.yaml` declares the kepano bundle.
9. After `sync agents all`:
   - `.codex/skills/obsidian-markdown/SKILL.md` and the other 4 exist.
   - `.opencode/skills/obsidian-markdown/SKILL.md` and the other 4 exist.
   - `.gemini/skills/obsidian-markdown/` and the other 4 exist
     (gitignored).
   - `.github/instructions/obsidian-markdown.instructions.md` and the
     other 4 exist.
10. Claude Code marketplace registration succeeds; `/plugin install
    obsidian-markdown@obsidian-skills` works.
11. The `vault` SKILL.md body is ~25 lines and includes a "Related
    skills" cross-reference section pointing at kepano's 5 skills.
12. Dashboard tile renders at `/brain/vault`.
13. RAG quality baseline probe passes (updated text is found in the
    new `vault` SKILL.md).

## Resolved decisions

1. **Dashboard route**: `/brain/vault`. Hub `brain`, tile `vault`. Drop
   the redundant `/obsidian/` segment from the old route
   `/brain/obsidian/vault`.
2. **Platform key in `platforms.yaml`**: renamed `obsidian:` → `vault:`.
   User-facing CLI changes from `--connect obsidian` to `--connect
   vault`. Document in CHANGELOG.
3. **MCP tool rename**: all seven tools rename to the `vault-*` prefix.
4. **Phase ordering**: 1 → 2 → 3 → 4. Phase 1 must complete before
   Phase 2 to avoid transient name overlap. Phase 4 must come last so
   the cross-references resolve.

## Out of scope (track separately)

- New MCP tools for editing `.base` or `.canvas` files.
- Rebuilding the wiki to incorporate kepano's format awareness.
- Forking kepano's content for Augur-specific extensions.
- Replacing the TS Obsidian plugin (`plugins/obsidian/src/main.ts`).
- Re-classifying any of the other vault-tier skills (`apple`,
  `lifestyle`, `file-manager`, `ingest`).
