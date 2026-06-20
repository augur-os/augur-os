---
status: Implemented
date: 2026-04-06
deciders:
  - gsannikov
related:
  - ADR-491
  - ADR-490
  - ADR-479
hub: career
tags: [career, hub-migration, import, business-hub]
superseded_by: null
---

# ADR-538: Career-Ops Import & Career Hub Migration

## Context

The existing career hub had 13 skills (career, coach, interview-coach, content, linkedin-writer, venture-augur, enterprise, consulting-template, post, design-content-pipeline, project-dev, growth, auto-career-hub-coverage) but weak job search capabilities. The external open-source project [santifer/career-ops](https://github.com/santifer/career-ops) provides a battle-tested AI-powered job search system with 14 modes, A-F evaluation scoring, ATS PDF generation, portal scanning, and batch processing — capabilities the existing career skill lacked.

The career hub also conflated job search skills with unrelated business development skills (content creation, consulting, enterprise, LinkedIn writing). These belong in a separate hub.

**Problems solved:**
- Career hub lacked evaluation scoring, PDF generation, portal scanning, batch processing
- Job search skills mixed with business development skills in one hub
- No structured evaluation report system for job analysis
- No portal scanner for automated job discovery

## Decision

### 1. Import career-ops as standalone Augur skill

Clone `santifer/career-ops` into `skills/career-ops/` following the Agent Skills standard (ADR-479). Career-ops modes become Claude Code commands in `commands/`. Node.js scripts (PDF generation, Playwright scanning) stay in `scripts/`. Python MCP tools ported from the old career skill read career-ops' markdown tracker format.

### 2. Career-ops owns the career hub

`skills/career-ops/SKILL.md` declares `hub.owner: true` for hub id `career`. The hub subtitle changes to "AI-powered job search command center". Five dashboard pages: pipeline, reports, companies, star, resume.

### 3. Create business hub

Non-job-search skills re-hubbed to a new `business` hub owned by `venture-augur`: enterprise, consulting-template, content, linkedin-writer, post, design-content-pipeline, project-dev, growth (moved from brain).

### 4. Vault data migration

Vault reorganizes from `Au-vault/career/` to `Au-vault/career-ops/` using career-ops conventions:
- Per-file jobs converted to markdown tracker (`data/applications.md`)
- STAR YAML files converted to `interview-prep/story-bank.md`
- CVs moved to `cv.md` (master) + `output/` (variants)
- Companies, notes, reports directly moved
- Old vault preserved as backup

### 5. Port hardening system

The career hardening system (7 scripts, 3 MCP tools, ~1,250 LOC) provides unique cross-session knowledge retention not covered by career-ops. Ported to `skills/career-ops/scripts/`.

### 6. Delete superseded skills

Deleted after migration: `career`, `coach`, `interview-coach`, `auto-career-hub-coverage`. `manage-career-habits` dropped (never used, no vault data).

### 7. MCP tools

10 tools ported/created reading from career-ops vault layout: `get-career-jobs`, `add-career-job`, `update-career-job`, `delete-career-job`, `get-career-companies`, `get-career-job-counts`, `list-career-star`, `list-career-resumes`, `get-career-reports`, `get-career-report`. Plus 3 hardening tools.

## Consequences

### Positive

- Career hub gains 14 specialized job search modes (evaluation, scanning, PDF, batch)
- Clear separation between job search (career) and business development (business)
- Vault data migrated to simpler markdown tracker format
- Hardening system preserved with unique knowledge retention capabilities
- Dashboard pages show real job data from vault

### Negative

- Career-ops modes are in Spanish (inherited from source repo) — needs localization
- Node.js dependency added for PDF generation and portal scanning (Playwright)
- Business hub growth/venture-augur pages need dashboard directories created (pre-existing gap)
- Consulting-template, linkedin-writer, smb-client-template YAML pages still route under career hub labels in mount-plugins naming (cosmetic)

### Neutral

- Old vault preserved as backup at `Au-vault/career/`
- Career-ops' Go TUI dashboard not imported (replaced by Next.js pages)
- `manage-career-habits` dropped — zero usage, trivially rebuildable

## Alternatives Considered

### Alternative 1: Submodule + Bridge

Add career-ops as git submodule, bridge data between it and Augur. Rejected: two data layouts coexist, bridge fragility, separate install concerns.

### Alternative 2: Fork + Full Rewrite

Rewrite everything into Augur-native Python/TypeScript. Rejected: massive effort, loses ability to pull upstream improvements, PDF/Playwright needs Python equivalents.

## References

- Design spec: `docs/superpowers/specs/2026-04-06-career-ops-import-design.md`
- Implementation plan: `docs/superpowers/plans/2026-04-06-career-ops-import.md`
- Source repo: https://github.com/santifer/career-ops
- ADR-479: Agent Skills standard
- ADR-491: Unified config-driven pages
- ADR-490: Framework migration dual-alias architecture

## Impact Manifest

```yaml
impact:
  paths_renamed:
    - old: skills/career/
      new: skills/career-ops/
    - old: Au-vault/career/
      new: Au-vault/career-ops/
  apis_changed:
    - tool: get-career-jobs
      change: Now reads markdown tracker instead of per-file YAML
    - tool: list-career-star
      change: Now reads story-bank.md instead of individual YAML files
  patterns_deprecated:
    - pattern: Per-file job YAML (jobs-inbox.yaml, jobs-active.yaml)
      replacement: Markdown tracker table (data/applications.md)
    - pattern: Individual STAR story YAML files
      replacement: Single story-bank.md with H2 sections
  files_affected:
    - skills/career-ops/ (new, 50+ files)
    - skills/career/ (deleted, 86 files)
    - skills/coach/ (deleted)
    - skills/interview-coach/ (deleted)
    - skills/auto-career-hub-coverage/ (deleted)
    - skills/venture-augur/SKILL.md (hub owner for business)
    - skills/{enterprise,consulting-template,content,linkedin-writer,post,design-content-pipeline,project-dev,growth}/SKILL.md (re-hubbed to business)
    - apps/dashboard/features/pages/career/career-ops/ (5 new pages)
    - apps/dashboard/app/career/ (registry regenerated)
    - apps/dashboard/app/business/ (new hub layout + registry)
```
