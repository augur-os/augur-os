---
id: ADR-517
status: Implemented
date: 2026-03-25
deciders:
  - Gur Sannikov
supersedes:
  - ADR-111
  - ADR-220
hub: life
tags:
  - file-manager
  - organizer
  - consolidation
  - rules-engine
  - autoloop
superseded_by: null
---

# ADR-517: File Manager Consolidation — Rules Engine, Autoloop, and Skill Discovery

## Context

Three overlapping skills handle file-related tasks: `file-manager` (D tier, 28.8), `organizer` (D tier, 34.2), and `system-cleanup` (C tier, 38.5). The first two share the same hub (life), same tab (home), and overlapping concerns. Neither is functional. ADR-111 defines an aspirational vision for organizer that was never implemented. `system-cleanup` stays separate — it handles disk hygiene, a fundamentally different intent.

## Decision

### 1. Skill Consolidation

`file-manager` absorbs organizer's vision and assets. `organizer` is deleted entirely (no backward-compat stubs per rule 14). Supersedes ADR-111 and ADR-220.

### 2. Rules Engine — Triage-First Decision Tree

Core intelligence shared by dashboard, autoloop, and external clients. The AI client makes triage decisions using MCP tool data. Decision tree: input assessment, triage (valuable vs low-value), domain routing via decentralized `x-augur-file-intake` skill frontmatter, sub-folder mapping, archive fallback, action detection (reminders, tasks).

Domain map assembled at runtime from skill SKILL.md `x-augur-file-intake` declarations — no centralized registry.

### 3. MCP Tools (8)

`scan-folder`, `get-domain-map`, `get-rules`, `update-rules`, `apply-file-actions`, `get-pending`, `get-archive`, `get-file-history`. Tools provide rules + file ops; the AI client makes decisions.

### 4. Autoloop (d0-d4)

Nightly autoloop with trust-aware approval escalation:
- d0: scan and report
- d1: high-confidence renames (auto-apply if trusted)
- d2: rename + move to skill domains
- d3: full triage with archive routing and action detection
- d4: skill discovery suggestions (always needs human)

Attention inbox integration as pilot pattern for universal autoloop-to-inbox callbacks.

### 5. Dashboard

Two tabs in life hub: Browse (refactored FileTree/FileEditor + intelligence panel) and Organize (watched folders, rules editor, pending queue, archive browser).

### 6. Skill Discovery Pipeline

When triage finds valuable content with no matching skill: files parked in pending, attention inbox notifies user, who can create skill via `/evolve`, route to existing skill, archive, or ignore. Autoloop polls for new skill intake declarations to resolve pending topics.

## Consequences

### Positive

- Two D-tier dead skills consolidated into one functional skill
- Decentralized domain routing via `x-augur-file-intake` follows rule 2
- Trust-aware autoloop enables progressive automation
- Skill discovery pipeline creates a growth loop for the vault

### Negative

- Large implementation scope (8 MCP tools, autoloop, dashboard, attention integration)
- Attention inbox extension is a pilot pattern — may need iteration

### Neutral

- `system-cleanup` unchanged — separate concern
- External clients (Cowork, Codex, Gemini) get full capability via MCP tools

## Alternatives Considered

### Alternative 1: Keep Both Skills, Add Wiring

Wire organizer and file-manager together without consolidation. Rejected because two D-tier skills with overlapping scope is the problem — merging eliminates the confusion.

### Alternative 2: Cloud-Based File Intelligence

Use cloud APIs for file classification. Rejected — local-first principle, and the AI client already has classification capability.

## References

- Design spec: `docs/superpowers/specs/2026-03-25-file-manager-consolidation-design.md`
- ADR-111: Organizer Hub Hardening (superseded)
- ADR-220: Files Hardening (superseded)

## Impact Manifest

```yaml
impact:
  paths_renamed: []
  apis_changed: []
  patterns_deprecated:
    - "skills/organizer/ — entire skill deleted"
    - "skills/dashboard/pages/life/organizer/ — generated pages deleted"
  files_affected:
    - "skills/file-manager/SKILL.md"
    - "skills/file-manager/scripts/mcp/__init__.py"
    - "skills/attention/ (source_type extension)"
```
