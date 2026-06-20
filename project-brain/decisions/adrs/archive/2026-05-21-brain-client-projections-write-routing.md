# Brain Client Projections And Write Routing Plan

## Goal

Make brain-owned instructions/capabilities canonical for client sync and route
write operations through explicit brain context.

## Tasks

### Task 1: Projection Source Abstraction

- Introduce a resolver that returns canonical instruction, skill, agent,
  policy, and workflow roots for a brain.
- Add tests for personal and project brains.

### Task 2: Update Client Sync Adapters

- Update `sync_agents` adapters to read from brain canonical roots.
- Keep generated client files ignored and provenance-marked.
- Update stale-check logic so `sync_agents check` compares generated outputs
  with brain sources.

### Task 3: Add Context Envelope Generation

- Generate the compact `augur:` context envelope for every supported client.
- Include active brain and attached project.
- Add tests for Codex, Claude, Gemini, Copilot, Cursor, and OpenCode formats
  where adapters exist.

### Task 4: Wire Write Routing

- Add a shared write-target resolver with explicit `--to`, cwd project brain,
  and personal fallback order.
- Wire `/note`, `/save`, `/ingest`, and `/ask retain` policy surfaces through
  the resolver.
- Ensure `/note` and `/ask` do not write memory by default.

### Task 5: Propagation Packets

- Generalize existing promotion packets to `<source-brain> -> <target-brain>`.
- Keep team-brain writes packet-first by default.
- Add source-containment checks for every packet.

### Task 6: Real-Data Verification

- Generate projections on the real machine.
- Capture one project note and one personal note.
- Show the concrete files and roots.
- Run focused tests plus `sync_agents check`.

## Acceptance Criteria

- Client projections come from brain-owned sources, not from ad hoc
  client-native files.
- Write routing is deterministic and visible.
- `/note` and `/ask` default behavior is not memory-writing.
- Cross-brain packet motion is explicit and source-contained.
