# Skillify Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: `superpowers:executing-plans`. This plan implements ADR-745 per the design spec. The implementation is **one markdown command file** plus optional command-surface registration.

**Goal:** Ship a `/skillify` slash command that walks an AI client through 10 canonical steps converting an incident into a durable skill.

**Architecture:** Pure markdown command body under `shared-vault/skills/auto-skill-quality/commands/`. No MCP tool, no Python module, no dashboard surface. Dispatch mode `ide` (multi-step judgment work in the client's session).

**Tech Stack:** Markdown + YAML frontmatter. No code.

**Spec:** `docs/superpowers/specs/2026-05-13-skillify-workflow-design.md`
**ADR:** `docs/adrs/ADR-745-skillify-bug-to-skill-workflow.md`
**Slate plan:** `docs/superpowers/plans/2026-05-13-gbrain-borrow-slate.md`

---

## Boundary Rules

- Touch only the command file and (optionally) the skill's `SKILL.md` if it enumerates commands.
- No Python, no test code, no MCP tool registration.
- Step 9 (check-resolvable) should reference ADR-741's MCP tool by name but degrade gracefully if ADR-741 hasn't shipped yet.
- `--help` must stop execution per Critical Rule #15.
- Verification uses `/auto-skill-quality`, `/commands`, and `sync commands all` (per `feedback_sync_agents_artifact_scope` memory) — never raw shell.

## File Structure

### Source

- Create `shared-vault/skills/auto-skill-quality/commands/skillify.md`
  - Frontmatter per spec §4.2 (name, description, dispatch, visibility, x-augur-tags)
  - Body: 10-step workflow per spec §4.3, with the framing preamble from §4.4

### Skill manifest

- Modify `shared-vault/skills/auto-skill-quality/SKILL.md` (if it enumerates owned commands)
  - Append `skillify` to the commands list in frontmatter or the command-section enumeration.

### Generated artifacts

- `sync commands all` (per `feedback_sync_agents_artifact_scope`) regenerates the per-client command surfaces so `/skillify` shows up in Claude Code's slash-command palette, Codex's command set, etc.

### Tests

- No code tests. Verification is **manual end-to-end** per spec §7.
- Optional: add a single sync_agents test that asserts the `skillify` command file is enumerated in the command-surface generator output. Defer unless we discover surface drift later.

### Docs

- No new docs. The ADR + spec carry the design rationale.

---

## Tasks

### Authoring

- [ ] Read `shared-vault/skills/auto-skill-quality/SKILL.md` to confirm command-enumeration shape (frontmatter list? body section?).
- [ ] Read one existing command in `commands/` for the local convention (e.g. another `auto-*` command body).
- [ ] Author `skillify.md` frontmatter per spec.
- [ ] Author the framing preamble per spec §4.4.
- [ ] Author Step 1 (capture incident) — title, intent, do, look, exit.
- [ ] Author Step 2 (define durable behavior).
- [ ] Author Step 3 (hub assignment) — link to `architecture-overview.md` hub list.
- [ ] Author Step 4 (scaffold) — point to an existing skill as template.
- [ ] Author Step 5 (SKILL.md frontmatter) — call out the `x-augur-config.hub` object form and the skill-vs-hub naming gotcha.
- [ ] Author Step 6 (logic) — reference `agent-vs-mcp-checklist.md`.
- [ ] Author Step 7 (tests) — pin the `importlib.util.spec_from_file_location` import idiom (matches `feedback_skill_test_convention`).
- [ ] Author Step 8 (capability) — point to `surface-decision-matrix.md` and `capability_exposure.yaml`; default CLI-only.
- [ ] Author Step 9 (check-resolvable) — call ADR-741's MCP tool by name; include fallback wording for pre-741 environments.
- [ ] Author Step 10 (audit + changelog).
- [ ] Add a closing "Done" section: "If all 10 steps are checked, run `/auto-skill-quality` once more and merge."

### Skill manifest

- [ ] Update `auto-skill-quality/SKILL.md` to enumerate the new command (if applicable per local convention).

### Sync + verify

- [ ] Run `sync commands all` per `feedback_sync_agents_artifact_scope` so per-client command surfaces regenerate.
- [ ] Confirm `/commands` listing shows `/skillify`.
- [ ] Confirm `/skillify --help` returns usage and does not execute.
- [ ] Confirm the command body renders correctly in at least one client (Claude Code preferred; Codex if available).

### End-to-end manual walkthrough

- [ ] Pick a tiny invented incident (e.g. "Augur lacks a `/hello-world` command").
- [ ] Walk steps 1–10 manually, producing a dummy skill named `hello-world-test`.
- [ ] Confirm the dummy skill passes `/auto-skill-quality`.
- [ ] **Delete** the dummy skill (it was for verification only).

### Closeout

- [ ] `/auto-lint` reports green.
- [ ] Update ADR-745 status from Accepted → Implemented in JSON index via upsert helper.
- [ ] Re-run `.github/scripts/generate_adr_index.py`.
- [ ] Re-run `sync_agents sync agents` so CLAUDE.md ADR footer refreshes.
- [ ] Update slate plan Phase 1 checkbox (`ADR-745 Implemented`).

---

## Rollback

- [ ] Delete `commands/skillify.md`.
- [ ] Revert `SKILL.md` enumeration change.
- [ ] Run `sync commands all` to regenerate per-client command surfaces without the command.
- [ ] Flip ADR-745 back to Proposed in JSON index.

Trivial rollback — no schema changes, no runtime state.

---

## Verification commands (Augur-canonical)

```bash
# Refresh command surfaces after authoring
sync commands all

# Lint
/auto-lint

# Audit
/auto-skill-quality

# Browse the command listing
/commands
```

Never invoke `pnpm dev`, raw shell, or per-client sync scripts directly.
