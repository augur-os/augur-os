# Delegation: Task Classes and Approval Gates

This runbook defines how Augur delegates work to agents safely.

## What is a delegated task class

A delegated task class is a repeatable unit of work with:
- explicit inputs and outputs
- a validation checklist
- known failure modes
- an approval model (what requires human review)

The goal is to make delegation reliable without turning the system into a black box.

## Task class 1: Dependency-aware documentation update

### Why this one first

This is high ROI because the repo already has a dependency tracker (`dependencies.yaml`) and a culture of keeping docs in sync.
It is also low risk because it is mostly deterministic and easy to review in git.

### Inputs

- A list of changed files (git diff, PR files, or a commit range)
- `dependencies.yaml`
- Existing docs templates and conventions (headings, link style)
- Constraints for the run:
  - allowed edit scope (docs only, or docs plus README)
  - whether to update marketing posts (default: no)
  - style constraints (no em-dashes, consistent headings)

### Outputs

- Updated documentation files that are downstream of the changed files
- Updated `README.md` links if the doc set moved or expanded
- Updated `dependencies.yaml` nodes for any new docs or moved files
- A short execution report:
  - what changed
  - why it changed (dependency path)
  - what was validated

### Validation checklist

- Links resolve (repo-relative links exist; no broken internal anchors)
- New docs are discoverable (linked from README or a docs index)
- Docs use consistent headings and naming
- No em-dashes were introduced in new or modified docs
- `dependencies.yaml` contains nodes for new docs and tools
- If code was touched, relevant tests/builds were run (or explicitly deferred)

### Failure modes and mitigations

| Failure mode | Symptom | Mitigation |
|---|---|---|
| Dependency graph drift | Unsure what docs to update | Run `python .github/scripts/dependency_tracker.py status` and follow the rebuild instructions |
| Conflicting guidance | Two docs disagree on behavior | Prefer the source of truth: code, then SKILL.md, then references, then docs |
| Overreach | Agent edits unrelated docs | Enforce an explicit edit scope and require review for wide diffs |
| Link rot | README points to missing files | Validate file existence and keep links relative |

### Approval gates

This task class is safe by default, but require explicit human approval when:
- touching any file under `src/config/` (paths, safety policies)
- changing allowlists, delete behavior, or any destructive defaults
- modifying scripts that run arbitrary shell commands
- changing release tooling or CI workflows

### Executor prompt template

Use this template when handing off to an execution agent (Codex CLI, Cursor, Claude Code):

1. Scope: update docs only (plus README if needed).
2. Inputs: provide the changed file list or a commit range.
3. Rules:
   - follow `dependencies.yaml` rebuild instructions
   - keep diffs minimal and reviewable
   - no em-dashes
4. Deliverables:
   - updated docs and dependency nodes
   - a short validation report (commands run, outcomes)

## Next task classes to add

After Task class 1 is stable, add:
- A constrained LinkedIn post formatter (inputs: draft, constraints; outputs: final copy; checklist: tone, length, hooks)
- A document summarizer with an accuracy checklist (inputs: source file; outputs: summary plus citations and uncertainty)

<!-- Reviewed: 2026-01-13 -->

