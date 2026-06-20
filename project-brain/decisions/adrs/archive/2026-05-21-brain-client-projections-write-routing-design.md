# Brain Client Projections And Write Routing Design

Date: 2026-05-21

## Context

After project-brain physical migration, Augur needs to stop treating
client-native files as canonical. Different AI clients consume different files,
and some clients manage their own memory internally. Augur should own the
brain-level instructions, capabilities, and routing policy, then generate
ignored projections for each detected client.

This phase also wires write operations through explicit brain destination
rules. Writes should not silently follow a dashboard filter or hidden session
state.

## Goals

- Make brain-owned instructions and capabilities canonical.
- Generate client-native files from the active brain and attached project.
- Add explicit write destination routing to capture/save/ingest/ask-retain
  surfaces.
- Preserve `/note` as note capture, not memory capture by default.
- Preserve `/ask` as read/answer by default; retention must be explicit.
- Keep client-native memory controlled by the client, with Augur review/import
  handled in ADR-772.

## Canonical Sources

```text
<brain-root>/instructions/
<brain-root>/capabilities/skills/
<brain-root>/capabilities/agents/
<brain-root>/policies/
<brain-root>/workflows/
```

Generated projections include, depending on installed clients:

```text
AGENTS.md
CLAUDE.md
CODEX.md
.gemini/GEMINI.md
.cursor/rules/*
.github/copilot-instructions.md
.opencode/AGENTS.md
.codex/skills/*
.gemini/skills/*
.opencode/skills/*
```

Generated projections are ignored outputs. They must include provenance that
points back to the source brain files.

## Context Envelope

Every generated client projection should expose the same compact Augur context:

```yaml
augur:
  active_brain:
    id: project-augur
    type: project
    root: project-brain
  attached_project:
    root: .
    has_adrs: true
    has_runtime: true
  generated_projection: true
```

## Write Routing

Write routing order:

1. Explicit destination: `--to <brain-id>`.
2. Active project brain from cwd/attached project.
3. Default personal brain.

Dashboard write actions must show a destination selector. Read filters do not
imply write destination.

Team brains default to packet-based write policy unless explicitly configured
for direct writes. Project and personal brains default to direct writes.

## Command Policy

- `/note`: captures a note/source into the selected destination brain. It does
  not create memory entries unless the user explicitly asks for memory.
- `/ask`: reads context and answers. It does not retain answers unless the user
  explicitly uses retention.
- `/save` and `/ingest`: accept `--to <brain-id>` and use active context when no
  explicit target is provided.

## Verification

- Generated projections for at least Codex, Claude, Gemini, and Copilot are
  produced from brain-owned canonical sources where those clients are detected.
- `sync_agents check` catches stale generated projections.
- Write-routing tests prove explicit destination wins, project cwd wins next,
  and personal fallback wins last.
- Real-data proof captures a note into a project brain and a personal brain and
  shows the files land in different roots.
