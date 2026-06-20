---
status: Implemented
date: 2026-05-05
deciders:
  - Gur Sannikov
related:
  - ADR-270
  - ADR-563
  - ADR-567
  - ADR-569
  - ADR-570
hub: null
tags: []
superseded_by: null
---

# ADR-605: Vault Skill Rename and Kepano Obsidian Integration

## Context

The current `obsidian` vault-tier skill at `~/Projects/Au-vault/skills/obsidian/` is misnamed. Its own frontmatter declares `x-augur-integration-type: vault` and its body explicitly states "Obsidian is opt-in. The vault at `get_vault_dir()` works without Obsidian installed." It is a vault skill that happens to know about Obsidian's flavor, not an Obsidian skill.

Installing `kepano/obsidian-skills` (28k stars, authored by Obsidian's CEO) across all clients creates a name collision: agents would have to choose between Augur's `obsidian` skill (vault integration) and kepano's `obsidian-markdown` / `obsidian-bases` / `obsidian-cli` (authoritative format references) for overlapping prompts. The kepano skills are authoritative for Obsidian's syntax surface; Augur's skill should not squat on the bare `obsidian` name.

The rename surface includes the vault bundle directory, MCP server (`augur-obsidian`), seven MCP tools (`obsidian-read`, `obsidian-write`, `obsidian-search`, `obsidian-status`, `obsidian-health-repairs`, `obsidian-scaffold`, `obsidian-convert`), the `VAULT_SKILL_NAMES` registry, the architecture test, the onboarding platform key (`obsidian:` → `vault:`, including the user-facing `--connect obsidian` CLI flag), 12 test files (with 2 conditional), generated registries, RAG quality baseline, and dashboard route. Two places legitimately keep the literal string `"obsidian"`: `browse/cli.py` (probes the `.obsidian/` directory by name) and `markdown_flavors.py` (`plain_to_obsidian` / `obsidian_to_plain` flavor functions).

After the rename, kepano's reference skills are vendored as a git submodule pinned to a specific SHA and distributed to all five client surfaces (Claude Code via marketplace, Codex/OpenCode via file copy, Gemini via the existing converter, Copilot via the instructions converter).

## Decision

Execute four sequential phases:

**Phase 1 — Rename `obsidian` → `vault`.** Move `~/Projects/Au-vault/skills/obsidian/` → `~/Projects/Au-vault/skills/vault/` via `git mv`. Rename the MCP server `augur-obsidian` → `augur-vault` and all seven tools to the `vault-*` prefix. Update `VAULT_SKILL_NAMES`, `test_no_vault_skill_refs.py`, the bundle server entry, the onboarding `platforms.yaml` key (and the user-facing `--connect obsidian` → `--connect vault` CLI flag — no backwards-compat alias per project rule 14), 12 test files, generated registries, and the RAG quality baseline. Dashboard route becomes `/brain/vault`. Implementation behavior is unchanged at the rename layer — `vault-scaffold` still writes `.obsidian/` config files; `vault-convert` still handles Obsidian-flavored markdown.

**Phase 2 — Vendor kepano/obsidian-skills.** Add as a git submodule at `vendor/skills/obsidian-skills/`, pinned to a specific SHA (not a moving branch). Create `config/external_skills.yaml` declaring the bundle, included skills (`obsidian-markdown`, `obsidian-bases`, `obsidian-cli`, `json-canvas`, `defuddle`), and per-client targets (`marketplace` / `file_copy` / `convert_and_copy` / `convert_to_instructions`).

**Phase 3 — Distribute to all five clients.** Extend `skills/ai/scripts/sync_agents/` to consume `external_skills.yaml`. Add `distribute_external_skills()` to `BaseAdapter`. Claude Code: register vendor path as additional marketplace; users install with `/plugin install <skill>@obsidian-skills`. Codex/OpenCode: plain file copy (kepano follows AgentSkills.io spec). Gemini: reuse existing SKILL.md → Gemini converter (output gitignored per rule 18). Copilot: reuse SKILL.md → `.github/instructions/*.instructions.md` converter. Updates flow through SHA bumps + `sync agents all`; Claude Code uses `/plugin update`.

**Phase 4 — Slim the `vault` SKILL.md and add cross-references.** Remove the duplicate Obsidian markdown stub and `.gitkeep` placeholder list. Add a "Related skills" section pointing at kepano's five reference skills so agents discover authoritative format docs. Target ~25 lines of body content.

Phase ordering 1 → 2 → 3 → 4 is required: Phase 1 must complete before Phase 2 to avoid transient name overlap; Phase 4 must come last so cross-references resolve.

## Consequences

### Positive
- Resolves name collision at the root — agents have unambiguous routing between Augur's vault integration and kepano's format reference.
- Aligns naming with architectural classification (`x-augur-integration-type: vault`).
- Future-proof if the vault viewer changes (Logseq, plain markdown, etc.).
- Agents gain authoritative Obsidian format docs (28k-star, Obsidian-CEO-authored) without Augur maintaining that knowledge.
- Decentralized — Augur owns vault integration; kepano owns syntax/format reference; clear seam.

### Negative
- User-facing CLI break: `augur onboard --connect obsidian` becomes `augur onboard --connect vault`. No backwards-compat alias (project rule 14: no compatibility shims). External scripts/muscle memory need updating; documented in CHANGELOG.
- MCP tool name break: existing prompts/scripts that called `obsidian-read` etc. by name stop working. Acceptable — agents discover tools by current name.
- Submodule pinning adds a manual SHA-bump step for kepano updates.
- Copilot converter may produce low-quality output for format-heavy skills (Bases tables, Canvas JSON examples) — accepted as best-effort target.
- Wide rename surface (12 test files, generated registries, dashboard wiring) — risk of missing a hardcoded reference.

### Neutral
- The vault adapter file at `vault_adapters/obsidian.py` keeps its name (filename references the *flavor*, not the skill).
- Markdown flavor functions (`plain_to_obsidian` / `obsidian_to_plain`) keep their names.
- TS Obsidian plugin at `plugins/obsidian/` is untouched.
- `vault-scaffold` and `vault-convert` retain Obsidian-aware implementation behavior; only the tool name changes.

## Alternatives Considered

### Alternative 1: Keep `obsidian` skill name and namespace kepano under `kepano-obsidian-*`
Rejected. Forces every kepano upstream update to be re-namespaced; loses the "authoritative reference" framing; agents still face routing ambiguity ("which `obsidian-*` skill answers this?"). The clean fix is to free the namespace.

### Alternative 2: Add a backwards-compatibility alias for `--connect obsidian`
Rejected per project rule 14 (prefer canonical cleanup over compatibility shims). The CLI break is documented in CHANGELOG; users adjust once.

### Alternative 3: Fork kepano/obsidian-skills for Augur-specific extensions
Rejected. Forking creates a perpetual sync burden against an actively-maintained upstream by Obsidian's CEO. Vendored submodule + cross-reference is sufficient; Augur's vault skill body adds Augur-specific integration content separately.

### Alternative 4: Keep MCP tool names as `obsidian-*` (rename bundle/skill only, not tools)
Rejected. The skill is named `vault`; consistency outweighs the implementation detail that two tools happen to know about Obsidian-specific artifacts. Tool prefix should match skill name.

### Alternative 5: Decompose `vault` into smaller skills as part of the rename
Rejected as out of scope. Decomposition is a separate architectural decision; conflating it with the rename multiplies surface area and risk.

## References
- Spec: docs/superpowers/specs/2026-05-05-vault-skill-rename-and-kepano-obsidian-integration-design.md
- ADR-270 — Vault path contract
- ADR-563 — Vault-Owned User Skills
- ADR-567 — Bundle Architecture Phase 0 Cleanup
- ADR-569 — Framework Server Split
- ADR-570 — Visibility Filter Removal
- Upstream: https://github.com/kepano/obsidian-skills
