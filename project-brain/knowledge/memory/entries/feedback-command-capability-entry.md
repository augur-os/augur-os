---
title: feedback-command-capability-entry
name: feedback-command-capability-entry
description: New slash commands need a `command:<name>:` entry in `config/system/capability_exposure.yaml`
  to project to client surfaces — not just MCP tools require an exposure entry
brain_scope: personal
type: feedback
status: active
source_client: claude-code
source_file: feedback_command_capability_entry.md
source_hash: 1822656ee2f09ca4
_mentions:
- '[[feedback-sync-agents-artifact-scope]]'
- '[[project-gbrain-borrow-slate]]'
---



When adding a new slash command in `shared-vault/skills/<skill>/commands/<name>.md`, edit **both**:

1. The command file itself (with frontmatter: `name`, `description`, `dispatch`, `visibility`, `x-augur-tags`).
2. `config/system/capability_exposure.yaml` — add a `command:<name>:` entry, e.g.:
   ```yaml
   command:<name>:
     classification_status: approved
     export_to: [cli, agents-md, browse, claude, codex]
     management: generated
     owner_kind: augur
     preferred_client: shell
     primary_surface: cli
     scope: project
   ```

Without that capability entry, `sync_agents` will NOT project the command into `.claude/commands/`, `.codex/skills/`, or any other client surface. The command exists in `shared-vault/skills/...` but is invisible to every AI client. The skill's `SKILL.md` enumeration of the command is necessary but not sufficient.

**Why:** Discovered during [[project-gbrain-borrow-slate]] Phase 1 (ADR-745, `/skillify` command, May 2026). The spec only documented the MCP-tool capability entry pattern; the subagent caught the gap when the first `sync commands all` run failed to make the new command appear in `/commands` listings. After adding the `command:skillify:` entry, `sync_agents` projected the command and it became visible across clients.

**How to apply:**

- Step 8 of `/skillify` (the canonical "incident → durable skill" workflow) covers MCP-tool entries explicitly; mentally extend the same step to slash commands too.
- When reviewing a plan/spec that adds a new command, check that **both** the command file and the capability entry are listed in the File Structure section. If the capability entry is missing, flag the plan as incomplete.
- The entry's `primary_surface` is typically `cli` (default), but `agents-md` and `browse` should be in `export_to` so the command appears in slash-command listings and the dashboard browse-commands surface.
- After editing capability_exposure.yaml, run `sync commands all` (per [[feedback-sync-agents-artifact-scope]]) to regenerate per-client surfaces.

Related: the user's `/skillify` command body explicitly cites this gotcha so future agents using the 10-step workflow won't miss it.
