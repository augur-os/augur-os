# Multi-Brain Project Brain Design

Date: 2026-05-20

## Context

ADR-754 introduced the first multi-brain registry shape, but the product model
needs a cleaner scope before implementation continues. Augur should support
three brain types: personal, team, and project. The first concrete example is
the Augur repository itself as a project with an attached project brain.

The current `shared-vault/` folder mostly represents Augur project knowledge,
capabilities, decisions, wiki, inbox, and lifecycle material. It should be
treated as the Augur project brain unless a specific exception is found. A
team brain is a cross-project shared operating context, not the default home
for Augur repo material.

## Goals

- Use one brain infrastructure and one folder contract for personal, team, and
  project brains.
- Make project brain the primary v1 migration target for the Augur monorepo.
- Keep personal brain real and linked as personal context.
- Keep team brain supported but optional in v1.
- Preserve the split between durable tracked brain content, OS runtime state,
  OS cache, and OS logs.
- Support cross-AI-client sync through generated ignored projections, not by
  making any client-native file canonical.
- Make `augur` runnable from any folder as part of onboarding.

## Non-Goals

- Do not implement multi-repo project brains in v1.
- Do not make team brain central to onboarding in v1.
- Do not store cache, indexes, runtime state, or logs inside a brain folder.
- Do not preserve old `shared-vault` paths as a long-term compatibility layer.
- Do not make `AGENTS.md`, `CLAUDE.md`, `CODEX.md`, or any client-native
  memory file canonical.
- Do not turn `/note` into a memory-writing command by default.
- Do not retain `/ask` results by default.

## Brain Contract

Every brain root should use the same structure as much as possible:

```text
<brain-root>/
  BRAIN.yaml
  profile/
  instructions/
    topics/
  capabilities/
    skills/
    agents/
  knowledge/
    memory/
      MEMORY.md
      entries/
    notes/
    sources/
    wiki/
  decisions/
    adrs/
  specs/
  plans/
  workflows/
  policies/
  activity/
    daily/
  reports/
  inbox/
  archive/
```

The brain type changes the attachment, not the base structure:

```text
personal brain = brain attached to the person
team brain    = brain attached to a shared operating context
project brain = brain attached to a repo/project
```

For Augur v1:

```text
Augur/
  project-brain/
    BRAIN.yaml
    ...
  src/
  apps/
  tests/
  scripts/
```

`src/`, `apps/`, `tests/`, and `scripts/` are code. They are not brain content,
but the project brain can describe, govern, index, and reason about them.

## Project Attachment

An AI client or CLI session should always know two separate things:

```text
active brain
attached project
```

Examples:

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

```yaml
augur:
  active_brain:
    id: personal
    type: personal
    root: ~/...
  attached_project: null
  generated_projection: true
```

Project ADRs, project logs, project specs, and project workflows are available
only when a project is attached. Personal and team brains may have decisions,
but those are personal/team operating decisions, not repo ADRs.

## AI Client Context Model

AI clients start with their own native context, then Augur adds compact
generated projections and on-demand brain access:

```text
client internal/session memory
+ generated instruction projection
+ generated skills/commands
+ MCP/search access to active brain
```

Canonical instruction and capability sources live in the active brain:

```text
<brain-root>/instructions/
<brain-root>/capabilities/skills/
<brain-root>/capabilities/agents/
```

Client-native files are generated ignored projections:

```text
AGENTS.md
CODEX.md
CLAUDE.md
.gemini/GEMINI.md
.cursor/rules/*
.github/copilot-instructions.md
.opencode/AGENTS.md
.codex/skills/*
.gemini/skills/*
.opencode/skills/*
```

`AGENTS.md` is not universal. Different clients consume different native
files, so the canonical source must be brain-owned instructions and capability
files.

`augur init` should sync projections for all supported AI clients detected on
the device.

## Discovery And Init

`augur` must run from any folder.

Resolution order:

```text
1. Explicit CLI override
   --brain <id|path>
   --project <path>

2. Nearest project brain
   walk upward from cwd until project-brain/BRAIN.yaml is found

3. Registered project brain
   if cwd is inside a known registered project path

4. Default personal brain
   if no project attachment is found
```

`augur init` is idempotent.

If run in a fresh repo:

```text
create project-brain/
create project-brain/BRAIN.yaml
register project brain locally
generate ignored AI-client projections for all detected clients
prepare local runtime/cache/index state
```

If run in a cloned repo that already contains `project-brain/BRAIN.yaml`:

```text
validate BRAIN.yaml
register this local clone locally
generate ignored AI-client projections
prepare local runtime/cache/index state
```

The tracked `project-brain/BRAIN.yaml` is the canonical project brain identity.
The local registry is machine state that records where known brains live on
this machine.

The UI should discover from both:

```text
local brain registry
filesystem discovery of folders containing project-brain/BRAIN.yaml
```

The UI should show:

```text
Known brains
Discovered project brains
Current active brain
Current attached project
Projection status
Index/runtime status
```

Clicking a discovered project should attach/register it locally, not create a
new brain.

## Memory And Knowledge

Memory-like artifacts are split by role and authority:

```text
profile       = identity and preferences of the active brain
memory        = curated remembered context
notes         = captured material
sources       = source cards and provenance
wiki          = synthesized knowledge
activity      = retained daily activity worth keeping
logs          = operational evidence outside the brain
client memory = AI-client-owned native memory, not canonical
```

Profile is brain-scoped:

```text
personal-brain/profile/ = personal profile
team-brain/profile/     = team identity and shared norms
project-brain/profile/  = project identity, principles, style, assumptions
```

Durable brain-owned content lives under the brain root:

```text
<brain-root>/
  profile/
  knowledge/
    memory/
    notes/
    sources/
    wiki/
  activity/
    daily/
```

Runtime state, logs, caches, indexes, and generated projection state remain
outside the brain in OS-appropriate locations. Augur does not need a
`client-memory-imports/` content store. AI clients own their native memory.
Augur may read client memory during sync or review and may store minimal
bookkeeping such as hashes, timestamps, and projection status.

Command behavior:

```text
/note
  creates notes/sources
  does not create memory by default

/ask
  reads active brain context
  does not retain by default

/ask --retain
remember this
promote to memory
curate memory
  explicit paths that may write canonical memory
```

Canonical memory changes only through explicit retention, promotion, curation,
profile flows, or direct memory-writing commands. Passive client-native memory
must not automatically become canonical brain memory.

## ADRs, Logs, And Lifecycle

For project brain:

```text
project-brain/
  decisions/
    adrs/
  specs/
  plans/
  workflows/
  reports/
  activity/
```

These describe the project lifecycle and should be tracked when they are
human- or agent-reviewed durable artifacts.

Logs stay outside the brain:

```text
OS logs/
  augur/
  daemon/
  mcp/
  clients/
```

Runtime state stays outside the brain:

```text
OS runtime/
  brains/<brain_id>/
    indexes/
    sessions/
    projection-state/
```

Generated reports split by authority:

```text
project-brain/reports/
  reviewed durable reports, release notes, eval summaries worth keeping

OS runtime/cache/
  transient generated diagnostics, raw scan output, rebuildable reports
```

The project brain owns lifecycle knowledge. OS runtime, logs, and cache own
machine state and transient evidence.

## V1 Scope

V1 uses the same infrastructure for all three brain types, but defaults to
project plus personal:

```text
project brain = auto-created or attached by augur init in a repo
personal brain = existing/default personal context
team brain = optional/manual, supported by the same contract
```

`augur init` in a repo:

```text
creates or attaches project-brain/
links existing personal brain for personal context
does not auto-create team brain
syncs all supported AI clients detected on the device
```

Team brain is not removed. It is deferred as a first-class product surface
until there is a clear cross-project shared operating context.

## Augur Monorepo Migration

The Augur repo should migrate current project-brain material into
`project-brain/`.

Initial mapping:

```text
shared-vault/skills        -> project-brain/capabilities/skills
plugins/agents             -> project-brain/capabilities/agents
docs/adrs                  -> project-brain/decisions/adrs
docs/superpowers/specs     -> project-brain/specs
docs/superpowers/plans     -> project-brain/plans
docs/agent-topics          -> project-brain/instructions/topics
shared-vault/notes         -> project-brain/knowledge/notes
shared-vault/sources       -> project-brain/knowledge/sources
shared-vault/wiki          -> project-brain/knowledge/wiki
shared-vault/inbox         -> project-brain/inbox
```

After migration:

```text
docs/
  public/user/developer product docs only

project-brain/
  operational/project lifecycle/agent knowledge
```

Generated machine-readable inventories should live next to the domain they
index:

```text
project-brain/decisions/adrs/index.json
project-brain/capabilities/skills/manifest.json
project-brain/capabilities/tools/verification.json
```

Markdown convenience views should be regenerated unless they are reviewed
human artifacts.

## Open Implementation Questions

- Exact `BRAIN.yaml` schema fields and validation rules.
- Exact local registry location and conflict policy when the same brain is
  cloned multiple times.
- Exact migration sequence for path helpers and existing hardcoded
  `shared-vault` references.
- Exact cleanup guard for old `shared-vault` paths after the clean-break
  migration, including how to detect missed references before removal.
- The first UI screen for known/discovered brains and projection health.

## Success Criteria

- A cloned project with `project-brain/BRAIN.yaml` can be attached by running
  `augur init`.
- Running `augur` from any subfolder resolves the correct active brain and
  attached project.
- Running `augur` outside a project falls back to the default personal brain.
- AI-client projections are generated for all supported clients detected on
  the device and remain ignored/local-only.
- `/note` creates notes/sources, not canonical memory, unless the user invokes
  an explicit memory flow.
- `/ask` does not retain by default.
- Project ADRs, specs, plans, workflows, wiki, and project skills live under
  `project-brain/` after migration.
- Runtime, logs, caches, indexes, and transient diagnostic outputs remain in
  OS-appropriate locations outside the brain.
