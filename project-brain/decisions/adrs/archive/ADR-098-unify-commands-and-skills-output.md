---
status: Implemented
date: '2026-02-13'
deciders:
- Project team
related:
- ADR-053 (slash command framework)
- ADR-096 (progressive disclosure)
- ADR-097 (command consolidation)
hub: null
tags:
- unify
- commands
- skills
- output
superseded_by: null
---

# ADR-098: Unify Commands and Skills Output

## Context

### The Problem

`sync_agents.py` maintains **two parallel output systems** and **no IDE sees all 46 commands**:

1. **`.claude/commands/`** — 46 flat markdown files (40 from `agent-workflows/` + 5 duplicated from `skills/` + `chain.md`)
2. **`.claude/skills/`** — 5 structured directories (`auto-fix/`, `harden/`, `implement-adr/`, `import/`, `write-adr/`)

As of **Claude Code v2.1.3**, `SlashCommand` was merged into `Skill` — both directories use the same tool. The dual output is redundant.

Worse, every other IDE has gaps:

### Current State — What Each IDE Can See

| IDE | Workflows (40) | Skills (5) | Chain/Swarm | Total | Missing |
|-----|:--------------:|:----------:|:-----------:|:-----:|:-------:|
| Claude Code | 40 | 5 (x2) | 2 | 47 | 0 (but 5 duplicated) |
| Cursor | 34 | 5 | 0 | 39 | 7 hidden + 2 meta |
| Windsurf | 0 | 5 | 2 orchestration | 7 | **39** |
| OpenCode | 34 | 0 | 2 orchestration | 36 | **5 skills + 5 hidden** |
| Copilot | 0 | 5 | 0 | 5 | **41** |
| Kimi | 0 | 5 (reads `.claude/skills/`) | 0 | 5 | **41** |
| Antigravity | 34 (x2 dirs) | 0 | 0 | 34 | **5 skills + 7 hidden** |
| Codex | 40+ | 0 | 0 | 40 | **5 skills** |
| Gemini | 0 | 0 | 1 combined | 1 | **45** |

**Goal**: Every IDE sees all 46 commands in its native format. One unified `sync_all_commands()` method per adapter, replacing the split `sync_workflows()` + `sync_skills()`.

## Decision

### 1. Principle: Every Adapter Outputs All 46

Each adapter gets a single method that processes **both** source directories:
- `plugins/ai/skills/ai_bridge/augur/agent-workflows/*.md` (40 workflow definitions)
- `plugins/ai/skills/ai_bridge/augur/skills/*/SKILL.md` (5 rich skill definitions)
- Plus `chain.md` and `swarm.md` meta-commands (generated)

Output goes to each IDE's **native format** in a **single directory** per IDE.

### 2. Per-IDE Changes

| IDE | Before | After | Output Dir | Format |
|-----|--------|-------|-----------|--------|
| **Claude Code** | `commands/` (46) + `skills/` (5) | `skills/` only (48) | `.claude/skills/{name}/SKILL.md` | Directory per command |
| **Cursor** | `workflows/` (34) + `skills/` (5) | `skills/` only (39) | `.cursor/skills/{name}.md` | Flat file per command |
| **Windsurf** | `workflows/` (7) | `workflows/` (46) | `.windsurf/workflows/{name}.md` | Flat file per command |
| **OpenCode** | `commands/` (34) | `commands/` (46) | `.opencode/commands/{name}.md` | Flat file per command |
| **Copilot** | `skills/` (5) | `skills/` (46) | `.github/skills/{name}.md` | Flat file per command |
| **Kimi** | reads `.claude/skills/` | reads `.claude/skills/` (48) | — (piggybacks on Claude Code) | — |
| **Antigravity** | `workflows/` (34 x2) | `workflows/` (46 x2) | `.antigravity/workflows/` + `.agent/workflows/` | Flat file per command |
| **Codex** | `prompts/` (40) | `prompts/` (46) | `~/.codex/prompts/{name}.md` | Flat file per command |
| **Gemini** | 0 commands | `skills/` (46) | `.gemini/skills/{name}.md` | Flat file per command |

**Hidden commands** (`_` prefix, ADR-053): included for Claude Code (visibility filtering built-in), excluded for other IDEs (no hidden command support).

### 3. Delete Legacy Directories

After consolidation:

**Delete from repo**:
- `.claude/commands/` — entire directory (replaced by `.claude/skills/`)
- `.cursor/workflows/` — entire directory (replaced by `.cursor/skills/`)

**No deletion** (still the canonical output for their IDE):
- `.windsurf/workflows/` — Windsurf's native format (now expanded to 46)
- `.opencode/commands/` — OpenCode's native format (now expanded to 46)
- `.antigravity/workflows/` + `.agent/workflows/` — Antigravity (now expanded to 46)
- `~/.codex/prompts/` — Codex (now expanded to 46, outside repo)

### 4. Code Changes in `sync_agents.py`

#### New src/lib helper

Extract common logic into a src/lib helper that all adapters use:

```python
def _iter_all_commands(skills_dir: Path) -> Iterator[tuple[str, str, str]]:
    """Yield (name, content, source_ref) for all commands (skills + workflows).

    Processes both:
    - skills_dir/*/SKILL.md  (rich skills)
    - SOURCE_WORKFLOWS/*.md  (workflow definitions)

    Applies ADR-053 naming: alias resolution, hidden prefix.
    """
    # 1. Rich skills
    if skills_dir.exists():
        for skill_dir in sorted(skills_dir.iterdir()):
            ...
            yield (skill_dir.name, content, source_ref)

    # 2. Workflows (skip names that collide with skills)
    wf_metadata = scan_workflows(SOURCE_WORKFLOWS)
    metadata_map = {w["name"]: w for w in wf_metadata}
    seen = set()  # prevent duplicates if skill and workflow share a name

    for wf_path in sorted(SOURCE_WORKFLOWS.glob("*.md")):
        meta = metadata_map.get(wf_path.stem, ...)
        target_name = _get_skill_target_name(meta)
        if target_name in seen:
            continue
        seen.add(target_name)
        content = resolve_placeholders(wf_path.read_text())
        yield (target_name, content, source_ref)
```

#### ClaudeCodeAdapter

**Replace** `sync_workflows()` + `sync_skills()` with single `sync_all_commands()`:
- Iterates `_iter_all_commands()`
- Writes each to `.claude/skills/{name}/SKILL.md` (directory format)
- Includes hidden commands (Claude Code supports `_` prefix visibility)
- Also writes `chain/SKILL.md` and `swarm/SKILL.md` (absorbs `sync_chain_commands()` and `sync_swarm_commands()`)

#### CursorAdapter

**Replace** `sync_workflows()` + `sync_skills()` with single `sync_all_commands()`:
- Iterates `_iter_all_commands()`, skipping hidden
- Writes each to `.cursor/skills/{name}.md` (flat, frontmatter stripped)
- Absorbs orchestration output (currently in `sync_external_orchestration()` as separate files)

#### WindsurfAdapter

**Replace** `sync_skills()` with `sync_all_commands()`:
- Iterates `_iter_all_commands()`, skipping hidden
- Writes each to `.windsurf/workflows/{name}.md` (flat, frontmatter stripped)
- Keeps orchestration files (`augur-swarm.md`, `augur-chain.md`) as before

#### OpenCodeAdapter

**Replace** `sync_workflows()` with `sync_all_commands()`:
- Iterates `_iter_all_commands()`, skipping hidden
- Writes each to `.opencode/commands/{name}.md` (flat)
- Absorbs orchestration output

#### CopilotAdapter

**Expand** `sync_skills()` → `sync_all_commands()`:
- Iterates `_iter_all_commands()`, skipping hidden
- Writes each to `.github/skills/{name}.md` (flat, frontmatter stripped)

#### AntigravityAdapter

**Expand** `sync_workflows()` → `sync_all_commands()`:
- Iterates `_iter_all_commands()`, skipping hidden
- Writes each to `.antigravity/workflows/{name}.md` AND `.agent/workflows/{name}.md`
- Preserves underscore alias generation for parser compatibility

#### CodexAdapter

**Expand** `sync_workflows()` → `sync_all_commands()`:
- Iterates `_iter_all_commands()`, skipping hidden (or including — Codex may support)
- Writes each to `~/.codex/prompts/{name}.md`
- Preserves existing alias generation

#### GeminiAdapter

**Add** `sync_all_commands()` (currently has no workflow/skill sync):
- Iterates `_iter_all_commands()`, skipping hidden
- Writes each to `.gemini/skills/{name}.md` (flat, frontmatter stripped)

#### KimiAdapter

**No code change** — Kimi reads `.claude/skills/` directly. The Claude Code adapter change gives Kimi all 48 commands for free.

### 5. Update Manifest File

`.agent/ide-manifest.json` is auto-generated from `GENERATED_FILES` list in `sync_agents.py`. After the code change and a `--skills` run, the manifest will reflect the new paths automatically.

**Removed paths**: all `.claude/commands/*.md`, `.cursor/workflows/*.md`
**Added paths**: `.claude/skills/*/SKILL.md` (48 entries), `.gemini/skills/*.md` (46), expanded `.github/skills/*.md` (46), etc.

### 6. BaseAdapter Interface Update

Replace the two abstract methods:
```python
# Before
def sync_workflows(self, workflows: list[Path]) -> None: ...
def sync_skills(self, skills_dir: Path) -> None: ...

# After
def sync_all_commands(self, skills_dir: Path) -> None: ...
```

The dispatcher (`sync()` function) calls `adapter.sync_all_commands(SOURCE_SKILLS)` once instead of calling `sync_workflows()` and `sync_skills()` separately.

## Consequences

### Positive
- **Every IDE sees all 46 commands** — no more gaps. Kimi: 5→48, Windsurf: 7→46, Copilot: 5→46, Gemini: 0→46.
- **No duplicate files** — Claude Code skills written once instead of twice.
- **Simpler adapter interface** — one method (`sync_all_commands`) replaces two (`sync_workflows` + `sync_skills`).
- **Shared iteration logic** — `_iter_all_commands()` removes duplicated loops across adapters.
- **Manifest cleaned** — no dual-path entries.

### Negative
- **One-time cleanup** — must delete `.claude/commands/` and `.cursor/workflows/` from repo.
- **`.claude/skills/` grows** — from 5 to ~48 subdirectories.
- **All adapters touched** — 9 adapters modified in one change. Risk of regression per-IDE.
- **Pre-v2.1.3 Claude Code** — `skills/` won't work as slash commands on older versions. Acceptable since we target latest.

### Neutral
- Source files unchanged — `agent-workflows/*.md` and `skills/*/SKILL.md` stay canonical.
- Orchestration files (`augur-swarm.md`, `augur-chain.md`) continue to exist for IDEs that use external execution (Windsurf, OpenCode).

## Implementation Order

```
Phase 1: Core refactor in sync_agents.py
├── Step 1.1: Create _iter_all_commands() src/lib helper
├── Step 1.2: Rename _get_workflow_target_filename → _get_skill_target_name
├── Step 1.3: Update BaseAdapter interface (sync_all_commands replaces two methods)
├── Step 1.4: Rewrite ClaudeCodeAdapter (merge sync_workflows + sync_skills + chain + swarm)
└── Step 1.5: Update sync() dispatcher to call sync_all_commands()

Phase 2: Update all other adapters (PARALLEL)
├── Step 2.1: CursorAdapter — merge workflows + skills into .cursor/skills/
├── Step 2.2: WindsurfAdapter — expand to all 46 in .windsurf/workflows/
├── Step 2.3: OpenCodeAdapter — expand to all 46 in .opencode/commands/
├── Step 2.4: CopilotAdapter — expand to all 46 in .github/skills/
├── Step 2.5: AntigravityAdapter — expand to all 46 in both workflow dirs
├── Step 2.6: CodexAdapter — expand to all 46 in ~/.codex/prompts/
└── Step 2.7: GeminiAdapter — add sync_all_commands() writing to .gemini/skills/

Phase 3: Regenerate and delete legacy (PIPELINE after Phase 1+2)
├── Step 3.1: Run sync_agents.py --skills to regenerate all outputs
├── Step 3.2: Verify each IDE output dir has expected count
├── Step 3.3: git rm -r .claude/commands/
├── Step 3.4: git rm -r .cursor/workflows/
├── Step 3.5: Verify manifest has no legacy paths
├── Step 3.6: Update .gitignore if needed
└── Step 3.7: Update docstrings and comments referencing old paths

Phase 4: Verification (PIPELINE after Phase 3)
├── Step 4.1: Run sync_agents.py --check
├── Step 4.2: Run pytest for sync_agents tests
├── Step 4.3: Verify Claude Code autocomplete shows all entries
└── Step 4.4: Verify Kimi discovers all commands via .claude/skills/
```

## Alternatives Considered

### A. Keep dual output, add workflows to `.claude/skills/` too

Write workflows to BOTH `.claude/commands/` AND `.claude/skills/`.

**Rejected**: Triples the duplication. Doesn't solve the gap for other IDEs.

### B. Move everything to `.claude/commands/` instead

Consolidate to the simpler flat format.

**Rejected**: `.claude/skills/` is richer (directory structure, frontmatter). Kimi and Cursor read `skills/` natively.

### C. Only fix Claude Code and Kimi, leave other IDEs as-is

Consolidate Claude Code, let other IDEs stay incomplete.

**Rejected**: Same gap exists everywhere. If we're doing the refactor, do it once for all 9 adapters.

## References

- ADR-053: Slash Command Framework (hidden commands, aliases)
- ADR-096: Progressive Disclosure Agent Instructions
- ADR-097: Command Consolidation (rename table)
- Claude Code v2.1.3 changelog: SlashCommand merged into Skill tool
- `plugins/ai/skills/ai_bridge/scripts/sync_agents.py` — main implementation file

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

You are implementing **ADR-098: Unify Commands and Skills Output**.

Read the full ADR: `docs/decisions/ADR-098-unify-commands-and-skills-output.md`

### Offload Protocol (ADR-054)

Before dispatching each step, check if it can be offloaded to a cheap CLI:

1. Read offload config: `cat config/system/llm.yaml` → look for `offload:` section
2. If `offload.enabled: true` AND the step's tier is `low`:
   ```bash
   python3 plugins/orchestration/skills/executor/scripts/offload_dispatcher.py \
     --task "STEP DESCRIPTION" \
     --files "TARGET_FILE_1,TARGET_FILE_2" \
     --context-files "REFERENCE_FILE_FOR_PATTERNS" \
     --work-dir $(pwd)
   ```
3. Review the JSON output — check `success`, `files_changed`, and `diff` fields
4. Record the verdict:
   - Accept (diff is correct): `python3 plugins/orchestration/skills/executor/scripts/offload_dispatcher.py --record-verdict accept`
   - Fix (you patched the output): `python3 plugins/orchestration/skills/executor/scripts/offload_dispatcher.py --record-verdict fix`
   - Escalate (offload failed, you did it yourself): `python3 plugins/orchestration/skills/executor/scripts/offload_dispatcher.py --record-verdict escalate`
5. If `offload.enabled: false` OR tier is `medium`/`high` → do the step yourself as normal

### Team Orchestration

Create a team and spawn teammates to execute the plan below:

1. **Create team**: `TeamCreate(team_name="adr-098-unify-skills", description="Implementing ADR-098: Unify Commands and Skills Output")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role in the Execution Plan, spawn a teammate:
   ```
   Task(subagent_type="general-purpose", team_name="adr-098-unify-skills", name="{role}",
        prompt="You are '{role}' on the adr-098-unify-skills team.
        Read your profile: .claude/agents/{role}.md
        Check TaskList for your assigned tasks. After each task: TaskUpdate to complete,
        SendMessage to team lead. If blocked, move to next available task.")
   ```
4. **Profile loading**: Each teammate MUST read `.claude/agents/{name}.md` for iron laws and constraints
5. **Communication**: Teammates use `SendMessage` to report completion, request reviews, and debate
6. **Dependencies**: PARALLEL phases -> spawn all at once. PIPELINE phases -> use task blocking
7. **Review cycle**: After implementation, validator reviews changes and debates with developer via `SendMessage`
8. **Shutdown**: When all phases pass, send `shutdown_request` to all teammates, then `TeamDelete()`

**Model mapping**: `low` -> haiku, `medium` -> sonnet, `high` -> opus

### Execution Plan

**Team name**: `adr-098-unify-skills`

#### Phase 1: Core Refactor
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | medium | Create `_iter_all_commands(skills_dir)` src/lib iterator that yields `(name, content, source_ref)` for all 46 commands (skills + workflows). Apply ADR-053 naming (alias, hidden prefix). | `plugins/ai/skills/ai_bridge/scripts/sync_agents.py` |
| 1.2 | developer | low | Rename `_get_workflow_target_filename()` → `_get_skill_target_name()`, return directory name (no `.md` extension), update all callers | `plugins/ai/skills/ai_bridge/scripts/sync_agents.py` |
| 1.3 | developer | medium | Update `BaseAdapter`: replace `sync_workflows()` + `sync_skills()` with single `sync_all_commands(skills_dir)`. Update `sync()` dispatcher. | `plugins/ai/skills/ai_bridge/scripts/sync_agents.py` |
| 1.4 | developer | medium | Rewrite `ClaudeCodeAdapter.sync_all_commands()`: iterate `_iter_all_commands()`, write `.claude/skills/{name}/SKILL.md`. Absorb `sync_chain_commands()` and `sync_swarm_commands()` output into this method. Delete old `sync_workflows()` and `sync_skills()`. | `plugins/ai/skills/ai_bridge/scripts/sync_agents.py` |

#### Phase 2: Update All Other Adapters
**Strategy**: PARALLEL
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | medium | `CursorAdapter.sync_all_commands()`: iterate all commands, skip hidden, write `.cursor/skills/{name}.md` (flat, frontmatter stripped). Delete old `sync_workflows()` + `sync_skills()`. | `plugins/ai/skills/ai_bridge/scripts/sync_agents.py` |
| 2.2 | developer | medium | `WindsurfAdapter.sync_all_commands()`: iterate all commands, skip hidden, write `.windsurf/workflows/{name}.md` (flat, frontmatter stripped). Replace old `sync_skills()`. | `plugins/ai/skills/ai_bridge/scripts/sync_agents.py` |
| 2.3 | developer | medium | `OpenCodeAdapter.sync_all_commands()`: iterate all commands, skip hidden, write `.opencode/commands/{name}.md` (flat). Replace old `sync_workflows()`. | `plugins/ai/skills/ai_bridge/scripts/sync_agents.py` |
| 2.4 | developer | medium | `CopilotAdapter.sync_all_commands()`: iterate all commands, skip hidden, write `.github/skills/{name}.md` (flat, frontmatter stripped). Expand from 5 to 46. | `plugins/ai/skills/ai_bridge/scripts/sync_agents.py` |
| 2.5 | developer | medium | `AntigravityAdapter.sync_all_commands()`: iterate all commands, skip hidden, write to `.antigravity/workflows/` + `.agent/workflows/` (both dirs, with underscore aliases). Expand from 34 to 46. Replace old `sync_workflows()`. | `plugins/ai/skills/ai_bridge/scripts/sync_agents.py` |
| 2.6 | developer | medium | `CodexAdapter.sync_all_commands()`: iterate all commands, write `~/.codex/prompts/{name}.md` (with alias generation). Expand from 40 to 46. Replace old `sync_workflows()`. | `plugins/ai/skills/ai_bridge/scripts/sync_agents.py` |
| 2.7 | developer | medium | `GeminiAdapter.sync_all_commands()`: new method. Iterate all commands, skip hidden, write `.gemini/skills/{name}.md` (flat, frontmatter stripped). | `plugins/ai/skills/ai_bridge/scripts/sync_agents.py` |

#### Phase 3: Regenerate and Delete Legacy
**Strategy**: PIPELINE (after Phase 1+2)
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | devops | low | Run `python3 plugins/ai/skills/ai_bridge/scripts/sync_agents.py --skills` to regenerate all outputs | — |
| 3.2 | devops | low | Verify output counts: `.claude/skills/` ~48, `.cursor/skills/` ~39, `.windsurf/workflows/` ~46, `.opencode/commands/` ~46, `.github/skills/` ~46, `.gemini/skills/` ~46 | all output dirs |
| 3.3 | devops | low | `git rm -r .claude/commands/` | `.claude/commands/` |
| 3.4 | devops | low | `git rm -r .cursor/workflows/` | `.cursor/workflows/` |
| 3.5 | devops | low | Verify `.agent/ide-manifest.json` has no `.claude/commands/` or `.cursor/workflows/` references | `.agent/ide-manifest.json` |
| 3.6 | devops | low | Check and update `.gitignore` if it references deleted paths | `.gitignore` |
| 3.7 | devops | low | Update all docstrings and comments in sync_agents.py referencing old paths | `plugins/ai/skills/ai_bridge/scripts/sync_agents.py` |

#### Phase 4: Verification
**Strategy**: PIPELINE (after Phase 3)
**Agents**:

| Step | Agent | Tier | Task |
|------|-------|------|------|
| 4.1 | validator | low | Run `python3 sync_agents.py --check` to validate all targets exist |
| 4.2 | validator | low | Run `pytest tests/` for any sync_agents tests |
| 4.3 | validator | low | Verify Claude Code Skill tool shows all 46+ entries in autocomplete |
| 4.4 | validator | low | Verify Kimi discovers all commands via `.claude/skills/` |

### Completion Criteria
- [ ] All phases executed
- [ ] `.claude/commands/` directory deleted from repo
- [ ] `.cursor/workflows/` directory deleted from repo
- [ ] `.claude/skills/` contains ~48 entries (46 + chain + swarm)
- [ ] `.cursor/skills/` contains ~39 entries (visible commands)
- [ ] `.windsurf/workflows/` contains ~46 entries
- [ ] `.opencode/commands/` contains ~46 entries
- [ ] `.github/skills/` contains ~46 entries
- [ ] `.gemini/skills/` contains ~46 entries
- [ ] `~/.codex/prompts/` contains ~46 entries
- [ ] `.antigravity/workflows/` + `.agent/workflows/` contain ~46 entries each
- [ ] Manifest file has no legacy `commands/` or `workflows/` references for Claude/Cursor
- [ ] `sync_agents.py --check` passes
- [ ] ADR status updated to "Accepted"

### How to Run
```
# Option 1: Use /implement-adr (handles team orchestration automatically)
/implement-adr docs/decisions/ADR-098-unify-commands-and-skills-output.md

# Option 2: Paste this prompt into Claude Code
# The agent will create the team, spawn teammates, and coordinate
```
