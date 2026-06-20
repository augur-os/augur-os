# Career-Ops Import & Hub Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Import santifer/career-ops as an Augur skill owning the career hub, port MCP tools to read career-ops data format, rewire dashboard pages, create a new business hub, and delete superseded skills.

**Architecture:** Clone career-ops repo content into `skills/career-ops/` following Augur's Agent Skills standard. Career-ops modes become Claude Code commands. Python MCP tools are ported from the existing career skill but rewired to read career-ops' markdown tracker format (`data/applications.md`) instead of per-file YAML. Node.js scripts stay as-is. Dashboard pages are copied from the old career skill with data source adjustments. A new `business` hub is created to absorb non-job-search skills.

**Tech Stack:** Python (MCP tools), TypeScript/React (dashboard pages), Node.js (career-ops scripts), pnpm, git

**Spec:** `docs/superpowers/specs/2026-04-06-career-ops-import-design.md`

---

## File Map

### New files (skills/career-ops/)

| File | Responsibility |
|------|----------------|
| `skills/career-ops/SKILL.md` | Skill metadata, hub config, MCP tool list, dashboard pages, modals, actions |
| `skills/career-ops/README.md` | Skill overview |
| `skills/career-ops/commands/career-ops.md` | Router command (from `.claude/skills/career-ops/SKILL.md` in source repo) |
| `skills/career-ops/commands/_shared.md` | Shared context for all modes (from `modes/_shared.md`) |
| `skills/career-ops/commands/*.md` (13 files) | Individual mode files (from `modes/*.md`) |
| `skills/career-ops/scripts/generate-pdf.mjs` | PDF generation (from source repo) |
| `skills/career-ops/scripts/cv-sync-check.mjs` | CV sync checker (from source repo) |
| `skills/career-ops/scripts/verify-pipeline.mjs` | Pipeline verification (from source repo) |
| `skills/career-ops/scripts/dedup-tracker.mjs` | Dedup tracker (from source repo) |
| `skills/career-ops/scripts/merge-tracker.mjs` | Merge tracker (from source repo) |
| `skills/career-ops/scripts/normalize-statuses.mjs` | Status normalizer (from source repo) |
| `skills/career-ops/scripts/package.json` | Node.js deps for scripts (from source repo root) |
| `skills/career-ops/scripts/mcp/__init__.py` | MCP tool registration entry point |
| `skills/career-ops/scripts/mcp/_shared.py` | Shared helpers, path resolution, utilities |
| `skills/career-ops/scripts/mcp/tools_jobs.py` | Job pipeline CRUD — reads `data/applications.md` |
| `skills/career-ops/scripts/mcp/tools_companies.py` | Company data reads — reads `companies/` dir |
| `skills/career-ops/scripts/mcp/tools_star.py` | STAR stories — reads `interview-prep/story-bank.md` |
| `skills/career-ops/scripts/mcp/tools_resume.py` | CV management — reads `output/` + `cv.md` |
| `skills/career-ops/scripts/mcp/tools_stats.py` | Job counts for dashboard stat tiles |
| `skills/career-ops/scripts/mcp/tools_reports.py` | Evaluation reports — reads `reports/` dir |
| `skills/career-ops/templates/cv-template.html` | HTML CV template (from source repo) |
| `skills/career-ops/templates/portals.example.yml` | Portal scanner config template (from source repo) |
| `skills/career-ops/templates/states.yml` | Application states config (from source repo) |
| `skills/career-ops/config/profile.example.yml` | Profile template (from source repo) |
| `skills/career-ops/references/workflow-interview-prep.md` | Migrated from old career skill |
| `skills/career-ops/assets/seeds/_seed.yaml` | Seed data manifest |
| `skills/career-ops/assets/actions/*.md` | Action prompt templates migrated from old career skill |
| `skills/career-ops/augur/dashboard/pipeline/page.tsx` | Pipeline table (adapted from old career skill) |
| `skills/career-ops/augur/dashboard/companies/page.tsx` | Company cards (adapted from old career skill) |
| `skills/career-ops/augur/dashboard/star/page.tsx` | STAR stories table (new) |
| `skills/career-ops/augur/dashboard/resume/page.tsx` | CV variants list (new) |
| `skills/career-ops/augur/dashboard/reports/page.tsx` | Evaluation reports viewer (new) |
| `skills/career-ops/augur/dashboard/tsconfig.json` | Dashboard TypeScript config |
| `skills/career-ops/evals/rank.json` | Skill quality ranking |

### Modified files

| File | Change |
|------|--------|
| `skills/venture-augur/SKILL.md` | Add business hub owner config |
| `skills/enterprise/SKILL.md` | Change `x-augur-hub: career` → `x-augur-hub: business` |
| `skills/consulting-template/SKILL.md` | Change `x-augur-hub: career` → `x-augur-hub: business` |
| `skills/content/SKILL.md` | Change `x-augur-hub: career` → `x-augur-hub: business` |
| `skills/linkedin-writer/SKILL.md` | Change `x-augur-hub: career` → `x-augur-hub: business` |
| `skills/post/SKILL.md` | Change `x-augur-hub: career` → `x-augur-hub: business` |
| `skills/design-content-pipeline/SKILL.md` | Change `x-augur-hub: career` → `x-augur-hub: business` |
| `skills/project-dev/SKILL.md` | Change `x-augur-hub: career` → `x-augur-hub: business` |
| `skills/growth/SKILL.md` | Change `x-augur-hub: brain` → `x-augur-hub: business` |
| `apps/dashboard/app/career/layout.tsx` | Update if hub metadata references change |

### Deleted files (Phase 11)

| Directory | Reason |
|-----------|--------|
| `skills/career/` | Superseded by career-ops |
| `skills/coach/` | Absorbed into career-ops interview modes |
| `skills/interview-coach/` | Absorbed into career-ops |
| `skills/auto-career-hub-coverage/` | Maintenance skill for old hub structure |

### Vault changes

| Path | Action |
|------|--------|
| `Au-vault/career-ops/` | Create new vault dir with career-ops layout |
| `Au-vault/career/` | Keep as backup — NOT deleted |

---

## Task 1: Clone career-ops content into skill structure

**Files:**
- Create: `skills/career-ops/commands/career-ops.md`
- Create: `skills/career-ops/commands/_shared.md`
- Create: `skills/career-ops/commands/auto-pipeline.md`
- Create: `skills/career-ops/commands/scan.md`
- Create: `skills/career-ops/commands/pdf.md`
- Create: `skills/career-ops/commands/batch.md`
- Create: `skills/career-ops/commands/tracker.md`
- Create: `skills/career-ops/commands/pipeline.md`
- Create: `skills/career-ops/commands/apply.md`
- Create: `skills/career-ops/commands/contacto.md`
- Create: `skills/career-ops/commands/deep.md`
- Create: `skills/career-ops/commands/oferta.md`
- Create: `skills/career-ops/commands/ofertas.md`
- Create: `skills/career-ops/commands/training.md`
- Create: `skills/career-ops/commands/project.md`
- Create: `skills/career-ops/scripts/generate-pdf.mjs`
- Create: `skills/career-ops/scripts/cv-sync-check.mjs`
- Create: `skills/career-ops/scripts/verify-pipeline.mjs`
- Create: `skills/career-ops/scripts/dedup-tracker.mjs`
- Create: `skills/career-ops/scripts/merge-tracker.mjs`
- Create: `skills/career-ops/scripts/normalize-statuses.mjs`
- Create: `skills/career-ops/scripts/package.json`
- Create: `skills/career-ops/templates/cv-template.html`
- Create: `skills/career-ops/templates/portals.example.yml`
- Create: `skills/career-ops/templates/states.yml`
- Create: `skills/career-ops/config/profile.example.yml`
- Create: `skills/career-ops/README.md`

- [ ] **Step 1: Clone career-ops repo to a temp directory**

```bash
git clone --depth 1 https://github.com/santifer/career-ops.git /tmp/career-ops-import
```

- [ ] **Step 2: Create skill directory structure**

```bash
mkdir -p skills/career-ops/{commands,scripts,templates,config,references,assets/{seeds,actions},augur/{dashboard,pages,tests},evals}
```

- [ ] **Step 3: Copy mode files to commands/**

Copy the router SKILL.md and all mode markdown files:

```bash
cp /tmp/career-ops-import/.claude/skills/career-ops/SKILL.md skills/career-ops/commands/career-ops.md
cp /tmp/career-ops-import/modes/_shared.md skills/career-ops/commands/_shared.md
for f in auto-pipeline scan pdf batch tracker pipeline apply contacto deep oferta ofertas training project; do
  cp /tmp/career-ops-import/modes/$f.md skills/career-ops/commands/$f.md
done
```

- [ ] **Step 4: Patch the router command to use new paths**

The router at `commands/career-ops.md` references `modes/_shared.md` and `modes/{mode}.md`. Update all path references to `commands/_shared.md` and `commands/{mode}.md`.

Open `skills/career-ops/commands/career-ops.md` and replace:
- `modes/_shared.md` → `commands/_shared.md`
- `modes/{mode}.md` → `commands/{mode}.md`

- [ ] **Step 5: Patch _shared.md vault paths**

The `_shared.md` file references `cv.md`, `config/profile.yml`, `article-digest.md` at project root. These now live in the vault. Update the "Sources of Truth" table:
- `cv.md` → Read from vault data dir (resolved at runtime by skill)
- `config/profile.yml` → Read from vault data dir
- `article-digest.md` → Read from vault data dir

Also update report output paths: `reports/` → vault data dir `reports/`
And tracker path: `data/applications.md` → vault data dir `data/applications.md`

- [ ] **Step 6: Copy Node.js scripts**

```bash
cp /tmp/career-ops-import/generate-pdf.mjs skills/career-ops/scripts/
cp /tmp/career-ops-import/cv-sync-check.mjs skills/career-ops/scripts/
cp /tmp/career-ops-import/verify-pipeline.mjs skills/career-ops/scripts/
cp /tmp/career-ops-import/dedup-tracker.mjs skills/career-ops/scripts/
cp /tmp/career-ops-import/merge-tracker.mjs skills/career-ops/scripts/
cp /tmp/career-ops-import/normalize-statuses.mjs skills/career-ops/scripts/
cp /tmp/career-ops-import/package.json skills/career-ops/scripts/package.json
```

- [ ] **Step 7: Copy templates and config**

```bash
cp /tmp/career-ops-import/templates/cv-template.html skills/career-ops/templates/
cp /tmp/career-ops-import/templates/portals.example.yml skills/career-ops/templates/
cp /tmp/career-ops-import/templates/states.yml skills/career-ops/templates/
cp /tmp/career-ops-import/config/profile.example.yml skills/career-ops/config/
```

- [ ] **Step 8: Create README.md**

```markdown
# Career-Ops

AI-powered job search command center — evaluate offers, generate CVs, scan portals, track applications.

Imported from [santifer/career-ops](https://github.com/santifer/career-ops) and adapted to Augur skill conventions.

## Usage

```
/career-ops              → Discovery menu
/career-ops {JD}         → Auto-pipeline (evaluate + PDF + tracker)
/career-ops scan         → Portal scanner
/career-ops pdf          → ATS CV generation
/career-ops batch        → Parallel evaluation
/career-ops tracker      → Status overview
```

See `commands/career-ops.md` for the full mode list.

## Node.js Scripts

Scripts in `scripts/` require Node.js dependencies:

```bash
cd skills/career-ops/scripts && npm install
npx playwright install chromium  # For PDF + scanning
```

## Data

Runtime data lives in the vault at `get_skill_data_dir("career-ops")`.
```

- [ ] **Step 9: Commit**

```bash
git add skills/career-ops/commands/ skills/career-ops/scripts/ skills/career-ops/templates/ skills/career-ops/config/ skills/career-ops/README.md
git commit -m "feat(career-ops): import career-ops repo content into Augur skill structure"
```

---

## Task 2: Write SKILL.md with hub config and metadata

**Files:**
- Create: `skills/career-ops/SKILL.md`
- Create: `skills/career-ops/evals/rank.json`

- [ ] **Step 1: Write SKILL.md**

Create `skills/career-ops/SKILL.md` with full hub config. This is the largest metadata file — it defines the hub, pages, blocks, actions, and modals. Base it on the existing `skills/career/SKILL.md` structure but with career-ops branding and updated tool names.

```yaml
---
name: career-ops
x-augur-type: domain
x-augur-tags: [jobs, interview, companies, pipeline, resume, evaluation, cv, portal-scanner]
description: >
  AI-powered job search command center — evaluate offers, generate CVs, scan portals, track applications.
  Use when managing job applications, evaluating offers, generating tailored CVs, scanning job portals,
  preparing for interviews, or tracking career pipeline activity.
x-augur-hub: career
x-augur-tab: pipeline
x-augur-dependencies:
  required: []
  optional:
    - knowledge
    - ai
    - channels
    - apple
    - google-workspace
x-augur-license: MIT
x-augur-metadata:
  version: 1.0.0
  author: Augur (imported from santifer/career-ops)
  mcp-server: augur
  source: https://github.com/santifer/career-ops
x-augur-requires-platform: true
x-augur-mcp-tools:
  - get-career-jobs
  - add-career-job
  - update-career-job
  - delete-career-job
  - get-career-companies
  - get-career-job-counts
  - list-career-star
  - list-career-resumes
  - get-career-reports
  - get-career-report
x-augur-dashboard-pages:
  - /career/pipeline
  - /career/companies
  - /career/star
  - /career/resume
  - /career/reports
x-augur-data-dir: career-ops
x-augur-portable: true
x-augur-upgrade-hook: "your career pipeline connects to interview prep, calendar, Apple Reminders, and your knowledge base"
x-augur-config:
  hub:
    id: career
    owner: true
    title: Career
    nav_order: 20
    subtitle: AI-powered job search command center
    icon: Briefcase
    category: career
    iconBg: bg-cyan-500/20
    iconColor: text-cyan-400
    overview:
      search: true
      layout: masonry
  contributions:
    pages:
      - id: pipeline
        title: Pipeline
        icon: Briefcase
        order: 10
        purpose: Track job applications with scores, status, and inline actions.
        keywords: [jobs, pipeline, applications, career, tracker]
      - id: reports
        title: Reports
        icon: FileText
        order: 20
        purpose: Browse evaluation reports with A-F scoring breakdowns.
        keywords: [reports, evaluations, scoring]
      - id: companies
        title: Companies
        icon: Building2
        order: 30
        purpose: Research profiles for target companies.
        keywords: [companies, research, profiles]
      - id: star
        title: STAR Stories
        icon: Star
        order: 40
        purpose: Behavioral interview stories in STAR+R format.
        keywords: [star, stories, interview, behavioral]
      - id: resume
        title: Resumes
        icon: FileText
        order: 50
        purpose: CV variants and generated PDFs.
        keywords: [resume, cv, pdf]
    blocks:
      - id: pipeline
        type: data-table
        title: Job Pipeline
        icon: Briefcase
        expandTo: /career/pipeline
        data_source:
          mcp_tool: get-career-jobs
        search:
          enabled: true
          fields: [title, company, status]
          placeholder: Search jobs...
        filters:
          - field: status
            type: pills
            values: [inbox, active, offer, rejected, archive]
      - id: companies
        type: card-grid
        title: Companies
        icon: Building2
        data_source:
          mcp_tool: get-career-companies
        search:
          enabled: true
          fields: [name]
          placeholder: Search companies...
      - id: scoring
        type: stat-grid
        title: Pipeline Stats
        icon: Target
        data_source:
          mcp_tool: get-career-job-counts
      - id: star
        type: data-table
        title: STAR Stories
        icon: Star
        expandTo: /career/star
        data_source:
          mcp_tool: list-career-star
        search:
          enabled: true
          fields: [title, category]
          placeholder: Search stories...
      - id: reports
        type: data-table
        title: Evaluation Reports
        icon: FileText
        expandTo: /career/reports
        data_source:
          mcp_tool: get-career-reports
        search:
          enabled: true
          fields: [company, title]
          placeholder: Search reports...
    actions:
      - id: add-job
        label: Add Job
        icon: Plus
        type: modal
        modal: add-job
      - id: evaluate-job
        label: Evaluate Job
        description: Paste a JD for full A-F evaluation + PDF + tracker
        icon: Sparkles
        dispatch: ide
        context: Run /career-ops with the provided JD text
      - id: scan-portals
        label: Scan Portals
        description: Scan configured job portals for new offers
        icon: Search
        dispatch: ide
        context: Run /career-ops scan
      - id: generate-pdf
        label: Generate PDF
        description: Generate ATS-optimized CV for a specific job
        icon: FileText
        dispatch: ide
        context: Run /career-ops pdf
      - id: prep-interview
        label: Prep Interview
        description: Generate interview preparation materials
        icon: MessageSquare
        dispatch: ide
      - id: batch-evaluate
        label: Batch Evaluate
        description: Evaluate multiple offers in parallel
        icon: Layers
        dispatch: ide
        context: Run /career-ops batch
  modals:
    add-job:
      title: Add Job
      description: Add a job URL to your inbox for analysis
      submitTool: mcp://augur/add-career-job
      submitLabel: Add to Inbox
      fields:
        - name: url
          label: Job URL
          type: text
          required: true
          placeholder: https://linkedin.com/jobs/... or https://company.com/careers/...
x-augur-file-intake:
  accepts: [resumes, cover letters, offer letters, contracts, certifications]
  folder: career-ops
  subfolders: [resumes, contracts, certifications, applications]
---
# Career-Ops

AI-powered job search command center — evaluate offers, generate CVs, scan portals, track applications.

Imported from [santifer/career-ops](https://github.com/santifer/career-ops).

## Capabilities

- **Auto-Pipeline:** Paste a URL, get a full A-F evaluation + tailored PDF + tracker entry
- **Portal Scanner:** Scan 45+ preconfigured companies (Playwright-based)
- **ATS PDF Generation:** Keyword-injected CVs with custom design
- **Batch Processing:** Parallel evaluation with sub-agents
- **Interview Story Bank:** STAR+R stories accumulated across evaluations
- **Application Tracker:** Markdown-based tracker with status flow

## Data Structure

```
get_skill_data_dir("career-ops")
├── cv.md                      # Master CV
├── article-digest.md          # Proof points (optional)
├── config/
│   └── profile.yml            # Candidate profile
├── portals.yml                # Portal scanner config
├── data/
│   ├── applications.md        # Application tracker
│   ├── pipeline.md            # Inbox of pending URLs
│   └── scan-history.tsv       # Scanner dedup
├── reports/                   # Evaluation reports
├── output/                    # Generated PDFs
├── interview-prep/
│   └── story-bank.md          # STAR+R stories
├── companies/                 # Company research profiles
└── notes/
    ├── hard-skills/
    └── learning/
```

## MCP Tools

- `get-career-jobs` — List all jobs from tracker
- `add-career-job` — Add job URL to inbox
- `update-career-job` — Update job status/stage
- `delete-career-job` — Remove a job entry
- `get-career-companies` — List researched companies
- `get-career-job-counts` — Get counts by status
- `list-career-star` — List STAR+R stories
- `list-career-resumes` — List CV variants
- `get-career-reports` — List evaluation reports
- `get-career-report` — Get single report detail

## Slash Commands

See `commands/career-ops.md` for the full router.
```

- [ ] **Step 2: Create evals/rank.json**

```json
{
  "skill": "career-ops",
  "rank": "B",
  "dimensions": {
    "instruction": "B",
    "product": "B",
    "ui": "C",
    "wiring": "C"
  },
  "notes": "Imported from external repo. MCP tools and dashboard pages need validation."
}
```

- [ ] **Step 3: Commit**

```bash
git add skills/career-ops/SKILL.md skills/career-ops/evals/
git commit -m "feat(career-ops): add SKILL.md with hub config and metadata"
```

---

## Task 3: Port MCP tools — shared helpers

**Files:**
- Create: `skills/career-ops/scripts/mcp/__init__.py`
- Create: `skills/career-ops/scripts/mcp/_shared.py`

- [ ] **Step 1: Write _shared.py**

This file provides path resolution, logger, and utility functions for all MCP tool modules. It mirrors the pattern in `skills/career/scripts/mcp/_shared.py` but all paths point to career-ops vault layout.

```python
"""Shared helpers for career-ops MCP tool modules.

Path resolution, logger, and utility functions used across tool groups.
All data paths resolve to the career-ops vault directory via get_own_data_dir.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Optional

import yaml

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

try:
    from src.lib.frontmatter_utils import load_collection, write_frontmatter, parse_frontmatter
except ImportError:
    def load_collection(directory):  # type: ignore[misc]
        return []

    def write_frontmatter(path, metadata, body):  # type: ignore[misc]
        pass

    def parse_frontmatter(path):  # type: ignore[misc]
        return {}, ""

from src.lib.skill_paths import get_own_data_dir

try:
    from augur_mcp.logging import get_entity_logger
    from augur_mcp.annotations import tool_annotations
except ImportError:
    import importlib

    def get_entity_logger(name: str):
        logging_module = importlib.import_module("logging")
        return logging_module.getLogger(name)

    def tool_annotations(annotations: dict) -> dict:
        return annotations


logger = get_entity_logger("mcp.career-ops")

SKILL_ROOT = Path(__file__).resolve().parents[2]


# ============================================================================
# Data Directory Helpers — all relative to vault/career-ops/
# ============================================================================


def _get_data_dir() -> Path:
    """Get the career-ops vault data directory."""
    return get_own_data_dir(__file__)


def _get_tracker_path() -> Path:
    """Get the applications tracker file."""
    return _get_data_dir() / "data" / "applications.md"


def _get_pipeline_path() -> Path:
    """Get the pipeline inbox file."""
    return _get_data_dir() / "data" / "pipeline.md"


def _get_reports_dir() -> Path:
    """Get the evaluation reports directory."""
    return _get_data_dir() / "reports"


def _get_companies_dir() -> Path:
    """Get the company research profiles directory."""
    return _get_data_dir() / "companies"


def _get_output_dir() -> Path:
    """Get the generated PDFs directory."""
    return _get_data_dir() / "output"


def _get_cv_path() -> Path:
    """Get the master CV file."""
    return _get_data_dir() / "cv.md"


def _get_story_bank_path() -> Path:
    """Get the STAR+R story bank file."""
    return _get_data_dir() / "interview-prep" / "story-bank.md"


def _get_profile_path() -> Path:
    """Get the candidate profile file."""
    return _get_data_dir() / "config" / "profile.yml"


# ============================================================================
# Tracker Parsing — applications.md is a markdown table
# ============================================================================


def parse_tracker(path: Path) -> list[dict]:
    """Parse the applications.md markdown table into a list of job dicts.

    Expected format:
    | # | Date | Company | Role | Score | Status | PDF | Report | Notes |
    |---|------|---------|------|-------|--------|-----|--------|-------|
    | 1 | 2025-12-18 | Phoenix | Head AI | 4.2 | Evaluada | ✅ | ✅ | ... |
    """
    if not path.exists():
        return []

    content = path.read_text(encoding="utf-8")
    lines = content.strip().split("\n")

    # Find header row
    header_idx = -1
    for i, line in enumerate(lines):
        if line.strip().startswith("|") and "Company" in line and "Role" in line:
            header_idx = i
            break

    if header_idx < 0:
        return []

    # Parse header
    header_cells = [c.strip() for c in lines[header_idx].strip().strip("|").split("|")]
    header_map = {h.lower().replace(" ", "_").replace("#", "num"): i for i, h in enumerate(header_cells)}

    jobs = []
    # Skip header + separator
    for line in lines[header_idx + 2:]:
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < len(header_cells):
            continue

        def cell(key: str, default: str = "") -> str:
            idx = header_map.get(key, -1)
            return cells[idx] if 0 <= idx < len(cells) else default

        num = cell("num", "0")
        score_raw = cell("score", "0")
        try:
            score = float(score_raw)
        except (ValueError, TypeError):
            score = 0.0

        job_id = f"tracker-{num}" if num != "0" else hashlib.sha1(
            f"{cell('company')}|{cell('role')}".encode(), usedforsecurity=False
        ).hexdigest()[:12]

        jobs.append({
            "id": job_id,
            "num": num,
            "title": cell("role", cell("rol", "Unknown Role")),
            "company": cell("company", cell("empresa", "Unknown")),
            "status": cell("status", cell("estado", "unknown")),
            "score": score,
            "added_at": cell("date", cell("fecha", "")),
            "has_pdf": "✅" in cell("pdf", ""),
            "has_report": "✅" in cell("report", ""),
            "notes": cell("notes", cell("notas", "")),
        })

    return jobs


def append_tracker_row(path: Path, row: dict) -> None:
    """Append a row to the applications.md tracker table."""
    path.parent.mkdir(parents=True, exist_ok=True)

    if not path.exists():
        # Create tracker with header
        header = "# Applications Tracker\n\n"
        header += "| # | Date | Company | Role | Score | Status | PDF | Report | Notes |\n"
        header += "|---|------|---------|------|-------|--------|-----|--------|-------|\n"
        path.write_text(header, encoding="utf-8")

    content = path.read_text(encoding="utf-8")
    existing = parse_tracker(path)
    next_num = len(existing) + 1

    new_row = (
        f"| {next_num} "
        f"| {row.get('date', datetime.now().strftime('%Y-%m-%d'))} "
        f"| {row.get('company', 'Unknown')} "
        f"| {row.get('role', 'Unknown')} "
        f"| {row.get('score', '')} "
        f"| {row.get('status', 'Evaluada')} "
        f"| {row.get('pdf', '')} "
        f"| {row.get('report', '')} "
        f"| {row.get('notes', '')} |"
    )

    path.write_text(content.rstrip() + "\n" + new_row + "\n", encoding="utf-8")


# ============================================================================
# General Utilities
# ============================================================================


def _normalize_url(raw: str) -> str:
    """Normalize URL by trimming and removing trailing slashes."""
    if not raw:
        return ""
    return raw.strip().rstrip("/")


def _stable_id_from_url(url: str) -> str:
    """Generate stable ID from URL using SHA1."""
    return hashlib.sha1(url.encode(), usedforsecurity=False).hexdigest()[:12]
```

- [ ] **Step 2: Write __init__.py**

```python
"""Career-Ops MCP Tool Implementations.

Tools for the career-ops skill — job tracking, companies, STAR stories,
resumes, evaluation reports. Data lives in the career-ops vault directory.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

from .tools_jobs import register_jobs_tools
from .tools_companies import register_companies_tools
from .tools_star import register_star_tools
from .tools_resume import register_resume_tools
from .tools_reports import register_reports_tools
from .tools_stats import register_stats_tools


def register_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable[..., Any],
    metrics: Any,
) -> None:
    """Register all career-ops tools with the MCP server."""
    register_jobs_tools(mcp, mcp_tool_interceptor, metrics)
    register_companies_tools(mcp, mcp_tool_interceptor, metrics)
    register_star_tools(mcp, mcp_tool_interceptor, metrics)
    register_resume_tools(mcp, mcp_tool_interceptor, metrics)
    register_reports_tools(mcp, mcp_tool_interceptor, metrics)
    register_stats_tools(mcp, mcp_tool_interceptor, metrics)


__all__ = ["register_tools"]
```

- [ ] **Step 3: Commit**

```bash
git add skills/career-ops/scripts/mcp/__init__.py skills/career-ops/scripts/mcp/_shared.py
git commit -m "feat(career-ops): add MCP shared helpers and registration entry point"
```

---

## Task 4: Port MCP tools — jobs CRUD

**Files:**
- Create: `skills/career-ops/scripts/mcp/tools_jobs.py`

- [ ] **Step 1: Write tools_jobs.py**

Port `get-career-jobs`, `add-career-job`, `update-career-job`, `delete-career-job` from `skills/career/scripts/mcp/tools_jobs.py`. The key change: instead of reading per-file YAML from `job-analyzer/jobs/` dirs, read from `data/applications.md` markdown tracker using `parse_tracker()`.

```python
"""Job pipeline CRUD MCP tools.

Tools: get-career-jobs, add-career-job, update-career-job, delete-career-job

Data source: vault/career-ops/data/applications.md (markdown table)
"""

from __future__ import annotations

import json
from typing import Any, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

from ._shared import (
    logger,
    tool_annotations,
    parse_tracker,
    append_tracker_row,
    _get_tracker_path,
    _get_reports_dir,
    _normalize_url,
    _stable_id_from_url,
)


def get_jobs() -> list[dict]:
    """Get all jobs from the applications tracker."""
    tracker_path = _get_tracker_path()
    jobs = parse_tracker(tracker_path)

    # Also check reports dir for evaluated jobs not yet in tracker
    reports_dir = _get_reports_dir()
    if reports_dir.exists():
        tracker_companies = {j["company"].lower() for j in jobs}
        for entry in sorted(reports_dir.iterdir()):
            if not entry.is_file() or not entry.name.endswith(".md"):
                continue
            # Report format: ###-company-slug-YYYY-MM-DD.md
            parts = entry.stem.split("-", 1)
            if len(parts) < 2:
                continue
            # Check if this report's company is already tracked
            slug = parts[1].rsplit("-", 3)[0] if len(parts[1].split("-")) > 3 else parts[1]
            if slug.lower().replace("-", " ") not in tracker_companies:
                jobs.append({
                    "id": f"report-{entry.stem}",
                    "title": slug.replace("-", " ").title(),
                    "company": slug.replace("-", " ").title(),
                    "status": "evaluated",
                    "score": 0,
                    "added_at": "",
                    "has_pdf": False,
                    "has_report": True,
                    "notes": f"Report: {entry.name}",
                })

    return jobs


_SEED_JOBS: list[dict] = [
    {
        "id": "seed-senior-eng",
        "title": "Senior Software Engineer",
        "company": "Acme Corp",
        "status": "Evaluada",
        "score": 4.2,
        "added_at": "2026-03-15",
        "has_pdf": True,
        "has_report": True,
        "notes": "",
    },
    {
        "id": "seed-staff-eng",
        "title": "Staff Engineer, Platform",
        "company": "TechStart Inc",
        "status": "Aplicado",
        "score": 3.8,
        "added_at": "2026-03-10",
        "has_pdf": True,
        "has_report": True,
        "notes": "",
    },
]


def register_jobs_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable[..., Any],
    metrics: Any,
) -> None:
    """Register job pipeline CRUD tools."""

    @mcp.tool(
        name="get-career-jobs",
        annotations=tool_annotations({
            "title": "Get Career Jobs",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        }),
    )
    @mcp_tool_interceptor
    async def get_career_jobs_tool() -> str:
        """Get all career jobs from the application tracker.

        Returns:
            str: JSON with {success, data} where data is array of job objects.
        """
        metrics.track_tool("get_career_jobs", skill="career-ops")
        try:
            jobs = get_jobs()
            source = "vault"
            if not jobs:
                jobs = _SEED_JOBS
                source = "seed"
            return json.dumps({"success": True, "data": jobs, "source": source}, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to get career jobs: {e}", exc_info=True)
            return json.dumps({"error": str(e), "message": str(e)})

    @mcp.tool(
        name="add-career-job",
        annotations=tool_annotations({
            "title": "Add Career Job",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        }),
    )
    @mcp_tool_interceptor
    async def add_career_job_tool(url: str) -> str:
        """Add a job URL to the tracker inbox.

        Args:
            url: Job posting URL

        Returns:
            str: JSON with success status
        """
        metrics.track_tool("add_career_job", skill="career-ops")
        try:
            url = _normalize_url(url)
            if not url or not url.startswith("http"):
                return json.dumps({"success": False, "error": "Invalid URL"})

            tracker_path = _get_tracker_path()
            existing = parse_tracker(tracker_path)
            # Dedup by URL in notes
            for job in existing:
                if url in job.get("notes", ""):
                    return json.dumps({"success": False, "error": "Job already exists"})

            append_tracker_row(tracker_path, {
                "company": "Pending",
                "role": "Pending Analysis",
                "status": "inbox",
                "notes": url,
            })
            return json.dumps({"success": True})
        except Exception as e:
            logger.error(f"Failed to add career job: {e}", exc_info=True)
            return json.dumps({"error": str(e), "message": str(e)})

    @mcp.tool(
        name="update-career-job",
        annotations=tool_annotations({
            "title": "Update Career Job",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        }),
    )
    @mcp_tool_interceptor
    async def update_career_job_tool(id: str, status: str = "", stage: str = "") -> str:
        """Update status of a career job in the tracker.

        Args:
            id: Job ID (tracker-N format)
            status: New status value
            stage: Alias for status

        Returns:
            str: JSON with success status
        """
        metrics.track_tool("update_career_job", skill="career-ops")
        effective_status = status or stage
        if not effective_status:
            return json.dumps({"error": "status or stage is required"})
        try:
            tracker_path = _get_tracker_path()
            if not tracker_path.exists():
                return json.dumps({"success": False, "error": "Tracker not found"})

            content = tracker_path.read_text(encoding="utf-8")
            lines = content.split("\n")
            updated = False

            # Find the row with matching ID (tracker-N where N is the row number)
            target_num = id.replace("tracker-", "") if id.startswith("tracker-") else id

            for i, line in enumerate(lines):
                if not line.strip().startswith("|"):
                    continue
                cells = [c.strip() for c in line.strip().strip("|").split("|")]
                if len(cells) < 6:
                    continue
                if cells[0] == target_num:
                    cells[5] = effective_status
                    lines[i] = "| " + " | ".join(cells) + " |"
                    updated = True
                    break

            if updated:
                tracker_path.write_text("\n".join(lines), encoding="utf-8")
                return json.dumps({"success": True, "id": id, "updated": ["status"]})
            return json.dumps({"success": False, "error": f"Job '{id}' not found"})
        except Exception as e:
            logger.error(f"Failed to update career job: {e}", exc_info=True)
            return json.dumps({"error": str(e), "message": str(e)})

    @mcp.tool(
        name="delete-career-job",
        annotations=tool_annotations({
            "title": "Delete Career Job",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": False,
        }),
    )
    @mcp_tool_interceptor
    async def delete_career_job_tool(id: str) -> str:
        """Delete a job row from the tracker.

        Args:
            id: Job ID (tracker-N format)

        Returns:
            str: JSON with success status
        """
        metrics.track_tool("delete_career_job", skill="career-ops")
        try:
            tracker_path = _get_tracker_path()
            if not tracker_path.exists():
                return json.dumps({"success": False, "error": "Tracker not found"})

            content = tracker_path.read_text(encoding="utf-8")
            lines = content.split("\n")
            target_num = id.replace("tracker-", "") if id.startswith("tracker-") else id

            new_lines = []
            deleted = False
            for line in lines:
                if line.strip().startswith("|"):
                    cells = [c.strip() for c in line.strip().strip("|").split("|")]
                    if len(cells) >= 1 and cells[0] == target_num:
                        deleted = True
                        continue
                new_lines.append(line)

            if deleted:
                tracker_path.write_text("\n".join(new_lines), encoding="utf-8")
                return json.dumps({"success": True})
            return json.dumps({"success": False, "error": f"Job '{id}' not found"})
        except Exception as e:
            logger.error(f"Failed to delete career job: {e}", exc_info=True)
            return json.dumps({"error": str(e), "message": str(e)})
```

- [ ] **Step 2: Commit**

```bash
git add skills/career-ops/scripts/mcp/tools_jobs.py
git commit -m "feat(career-ops): add job pipeline CRUD MCP tools reading applications.md"
```

---

## Task 5: Port MCP tools — companies, STAR, resumes, reports, stats

**Files:**
- Create: `skills/career-ops/scripts/mcp/tools_companies.py`
- Create: `skills/career-ops/scripts/mcp/tools_star.py`
- Create: `skills/career-ops/scripts/mcp/tools_resume.py`
- Create: `skills/career-ops/scripts/mcp/tools_reports.py`
- Create: `skills/career-ops/scripts/mcp/tools_stats.py`

- [ ] **Step 1: Write tools_companies.py**

```python
"""Company research MCP tools.

Tool: get-career-companies
Data source: vault/career-ops/companies/ (directory of .md files)
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

from ._shared import logger, tool_annotations, _get_companies_dir


def get_companies() -> list[dict]:
    """Get list of company research profiles."""
    companies_dir = _get_companies_dir()
    if not companies_dir.exists():
        return []

    companies = []
    for entry in os.listdir(companies_dir):
        if entry.startswith(".") or entry == "README.md":
            continue
        file_path = companies_dir / entry
        if not file_path.is_file() or not entry.endswith(".md"):
            continue

        slug = entry.replace(".md", "")
        stat = file_path.stat()
        last_updated = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d")

        name = slug
        try:
            content = file_path.read_text(encoding="utf-8")
            first_line = content.split("\n")[0]
            if first_line.startswith("# "):
                name = first_line[2:].strip()
        except Exception:
            pass

        if name == slug:
            name = " ".join(
                word.upper() if len(word) <= 3 else word.title()
                for word in slug.replace("-", " ").replace("_", " ").split()
            )

        companies.append({
            "name": name,
            "slug": slug,
            "lastUpdated": last_updated,
        })

    companies.sort(key=lambda c: c["name"].lower())
    return companies


def register_companies_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable[..., Any],
    metrics: Any,
) -> None:
    """Register company research tools."""

    @mcp.tool(
        name="get-career-companies",
        annotations=tool_annotations({
            "title": "Get Career Companies",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        }),
    )
    @mcp_tool_interceptor
    async def get_career_companies_tool() -> str:
        """Get list of researched companies."""
        metrics.track_tool("get_career_companies", skill="career-ops")
        try:
            companies = get_companies()
            return json.dumps({"success": True, "data": companies}, indent=2)
        except Exception as e:
            logger.error(f"Failed to get companies: {e}", exc_info=True)
            return json.dumps({"error": str(e), "message": str(e)})
```

- [ ] **Step 2: Write tools_star.py**

```python
"""STAR story bank MCP tools.

Tool: list-career-star
Data source: vault/career-ops/interview-prep/story-bank.md
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

from ._shared import logger, tool_annotations, _get_story_bank_path


def list_star_stories() -> list[dict]:
    """Parse STAR+R stories from the story bank markdown file.

    Expected format: H2 sections with Situation/Task/Action/Result/Reflection subsections.
    """
    path = _get_story_bank_path()
    if not path.exists():
        return []

    content = path.read_text(encoding="utf-8")
    stories = []

    # Split by H2 headers
    sections = re.split(r'^## ', content, flags=re.MULTILINE)
    for i, section in enumerate(sections[1:], 1):  # Skip preamble
        lines = section.strip().split("\n")
        title = lines[0].strip()

        # Extract category from tags if present (e.g., [leadership] or **Category:** leadership)
        category = "general"
        for line in lines:
            cat_match = re.search(r'\[(\w+)\]|\*\*Category:\*\*\s*(\w+)', line)
            if cat_match:
                category = (cat_match.group(1) or cat_match.group(2)).lower()
                break

        body = "\n".join(lines[1:]).strip()
        stories.append({
            "id": f"star-{i}",
            "title": title,
            "category": category,
            "body": body[:200] + "..." if len(body) > 200 else body,
        })

    return stories


def register_star_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable[..., Any],
    metrics: Any,
) -> None:
    """Register STAR story tools."""

    @mcp.tool(
        name="list-career-star",
        annotations=tool_annotations({
            "title": "List STAR Stories",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        }),
    )
    @mcp_tool_interceptor
    async def list_career_star_tool() -> str:
        """List all STAR+R stories from the story bank."""
        metrics.track_tool("list_career_star", skill="career-ops")
        try:
            stories = list_star_stories()
            return json.dumps({"success": True, "data": stories}, indent=2)
        except Exception as e:
            logger.error(f"Failed to list STAR stories: {e}", exc_info=True)
            return json.dumps({"error": str(e), "message": str(e)})
```

- [ ] **Step 3: Write tools_resume.py**

```python
"""Resume/CV management MCP tools.

Tool: list-career-resumes
Data source: vault/career-ops/cv.md + vault/career-ops/output/
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

from ._shared import logger, tool_annotations, _get_cv_path, _get_output_dir


def list_resumes() -> list[dict]:
    """List master CV and generated CV variants/PDFs."""
    resumes = []

    # Master CV
    cv_path = _get_cv_path()
    if cv_path.exists():
        stat = cv_path.stat()
        resumes.append({
            "id": "master",
            "name": "Master CV",
            "type": "markdown",
            "path": str(cv_path),
            "lastModified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d"),
        })

    # Generated PDFs and variants in output/
    output_dir = _get_output_dir()
    if output_dir.exists():
        for entry in sorted(os.listdir(output_dir)):
            file_path = output_dir / entry
            if not file_path.is_file():
                continue
            ext = file_path.suffix.lower()
            if ext not in (".pdf", ".md", ".html"):
                continue
            stat = file_path.stat()
            resumes.append({
                "id": entry.rsplit(".", 1)[0],
                "name": entry,
                "type": ext.lstrip("."),
                "path": str(file_path),
                "lastModified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d"),
            })

    return resumes


def register_resume_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable[..., Any],
    metrics: Any,
) -> None:
    """Register resume/CV tools."""

    @mcp.tool(
        name="list-career-resumes",
        annotations=tool_annotations({
            "title": "List Career Resumes",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        }),
    )
    @mcp_tool_interceptor
    async def list_career_resumes_tool() -> str:
        """List master CV and generated CV variants."""
        metrics.track_tool("list_career_resumes", skill="career-ops")
        try:
            resumes = list_resumes()
            return json.dumps({"success": True, "data": resumes}, indent=2)
        except Exception as e:
            logger.error(f"Failed to list resumes: {e}", exc_info=True)
            return json.dumps({"error": str(e), "message": str(e)})
```

- [ ] **Step 4: Write tools_reports.py**

```python
"""Evaluation report MCP tools.

Tools: get-career-reports, get-career-report
Data source: vault/career-ops/reports/ (directory of .md files)
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from typing import Any, Callable, TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

from ._shared import logger, tool_annotations, _get_reports_dir


def _parse_report_filename(name: str) -> dict:
    """Parse report filename: ###-company-slug-YYYY-MM-DD.md"""
    stem = name.replace(".md", "")
    parts = stem.split("-", 1)
    num = parts[0] if parts[0].isdigit() else "0"
    rest = parts[1] if len(parts) > 1 else stem

    # Try to extract date from end
    date_match = re.search(r'(\d{4}-\d{2}-\d{2})$', rest)
    date = date_match.group(1) if date_match else ""
    company_slug = rest[:date_match.start()].rstrip("-") if date_match else rest

    return {
        "num": num,
        "company_slug": company_slug,
        "date": date,
    }


def list_reports() -> list[dict]:
    """List all evaluation reports."""
    reports_dir = _get_reports_dir()
    if not reports_dir.exists():
        return []

    reports = []
    for entry in sorted(os.listdir(reports_dir), reverse=True):
        if not entry.endswith(".md") or entry.startswith("."):
            continue
        file_path = reports_dir / entry
        if not file_path.is_file():
            continue

        parsed = _parse_report_filename(entry)
        stat = file_path.stat()

        # Try to extract score from file content (look for "Score:" or "Nota:" pattern)
        score = 0.0
        company = parsed["company_slug"].replace("-", " ").title()
        title = ""
        try:
            content = file_path.read_text(encoding="utf-8")
            # Check frontmatter
            if content.startswith("---"):
                fm_parts = content.split("---", 2)
                if len(fm_parts) >= 3:
                    fm = yaml.safe_load(fm_parts[1]) or {}
                    score = fm.get("score", fm.get("nota", 0.0))
                    company = fm.get("company", company)
                    title = fm.get("title", fm.get("role", ""))

            # Fallback: scan for score in content
            if not score:
                score_match = re.search(r'(?:Score|Nota)[:\s]+(\d+\.?\d*)', content)
                if score_match:
                    score = float(score_match.group(1))

            # Extract title from first H1
            if not title:
                h1_match = re.search(r'^# (.+)$', content, re.MULTILINE)
                if h1_match:
                    title = h1_match.group(1).strip()
        except Exception:
            pass

        reports.append({
            "id": entry.replace(".md", ""),
            "filename": entry,
            "company": company,
            "title": title or f"{company} Evaluation",
            "score": score,
            "date": parsed["date"] or datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d"),
        })

    return reports


def get_report(report_id: str) -> dict:
    """Get full content of a single evaluation report."""
    reports_dir = _get_reports_dir()
    path = reports_dir / f"{report_id}.md"
    if not path.exists():
        return {"success": False, "error": f"Report '{report_id}' not found"}

    content = path.read_text(encoding="utf-8")
    return {"success": True, "id": report_id, "content": content}


def register_reports_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable[..., Any],
    metrics: Any,
) -> None:
    """Register evaluation report tools."""

    @mcp.tool(
        name="get-career-reports",
        annotations=tool_annotations({
            "title": "Get Career Reports",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        }),
    )
    @mcp_tool_interceptor
    async def get_career_reports_tool() -> str:
        """List all evaluation reports."""
        metrics.track_tool("get_career_reports", skill="career-ops")
        try:
            reports = list_reports()
            return json.dumps({"success": True, "data": reports}, indent=2)
        except Exception as e:
            logger.error(f"Failed to list reports: {e}", exc_info=True)
            return json.dumps({"error": str(e), "message": str(e)})

    @mcp.tool(
        name="get-career-report",
        annotations=tool_annotations({
            "title": "Get Career Report",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        }),
    )
    @mcp_tool_interceptor
    async def get_career_report_tool(id: str) -> str:
        """Get full content of a single evaluation report.

        Args:
            id: Report ID (filename without .md extension)

        Returns:
            str: JSON with {success, id, content}
        """
        metrics.track_tool("get_career_report", skill="career-ops")
        try:
            result = get_report(id)
            return json.dumps(result, indent=2)
        except Exception as e:
            logger.error(f"Failed to get report: {e}", exc_info=True)
            return json.dumps({"error": str(e), "message": str(e)})
```

- [ ] **Step 5: Write tools_stats.py**

```python
"""Job statistics MCP tools.

Tool: get-career-job-counts
Data source: vault/career-ops/data/applications.md
"""

from __future__ import annotations

import json
from typing import Any, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

from ._shared import (
    logger,
    tool_annotations,
    parse_tracker,
    _get_tracker_path,
    _get_story_bank_path,
    _get_reports_dir,
)
from .tools_star import list_star_stories


def get_job_counts() -> dict:
    """Get job counts by status category."""
    jobs = parse_tracker(_get_tracker_path())

    inbox_statuses = {"inbox", "new", "pending"}
    active_statuses = {"evaluada", "aplicado", "respondido", "contacto", "entrevista", "active", "applied", "analyzing", "analyzed", "interviewing"}
    offer_statuses = {"oferta", "offer", "offered"}
    rejected_statuses = {"rechazada", "no aplicar", "descartada", "rejected"}
    archive_statuses = {"archived", "closed", "withdrawn"}

    counts = {"inbox": 0, "active": 0, "offer": 0, "rejected": 0, "archive": 0}
    for job in jobs:
        s = job.get("status", "").lower()
        if s in inbox_statuses:
            counts["inbox"] += 1
        elif s in active_statuses:
            counts["active"] += 1
        elif s in offer_statuses:
            counts["offer"] += 1
        elif s in rejected_statuses:
            counts["rejected"] += 1
        elif s in archive_statuses:
            counts["archive"] += 1
        else:
            counts["active"] += 1  # Default to active

    counts["total"] = len(jobs)

    # Also count STAR stories and reports
    stories = list_star_stories()
    counts["star_stories"] = len(stories)

    reports_dir = _get_reports_dir()
    counts["reports"] = len([f for f in reports_dir.iterdir() if f.suffix == ".md"]) if reports_dir.exists() else 0

    return counts


def register_stats_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable[..., Any],
    metrics: Any,
) -> None:
    """Register stats tools."""

    @mcp.tool(
        name="get-career-job-counts",
        annotations=tool_annotations({
            "title": "Get Career Job Counts",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        }),
    )
    @mcp_tool_interceptor
    async def get_career_job_counts_tool() -> str:
        """Get job counts by status category."""
        metrics.track_tool("get_career_job_counts", skill="career-ops")
        try:
            counts = get_job_counts()
            return json.dumps({
                "success": True,
                "data": {
                    "active_jobs": counts.get("active", 0) + counts.get("offer", 0),
                    "star_stories": counts.get("star_stories", 0),
                    "reports": counts.get("reports", 0),
                    "total": counts.get("total", 0),
                    "inbox": counts.get("inbox", 0),
                    "rejected": counts.get("rejected", 0),
                },
            }, indent=2)
        except Exception as e:
            logger.error(f"Failed to get job counts: {e}", exc_info=True)
            return json.dumps({"error": str(e), "message": str(e)})
```

- [ ] **Step 6: Commit**

```bash
git add skills/career-ops/scripts/mcp/tools_companies.py skills/career-ops/scripts/mcp/tools_star.py skills/career-ops/scripts/mcp/tools_resume.py skills/career-ops/scripts/mcp/tools_reports.py skills/career-ops/scripts/mcp/tools_stats.py
git commit -m "feat(career-ops): add companies, STAR, resume, reports, stats MCP tools"
```

---

## Task 6: Create vault directory with seed data

**Files:**
- Create: `Au-vault/career-ops/` directory structure
- Create: `skills/career-ops/assets/seeds/_seed.yaml`

- [ ] **Step 1: Create vault directory structure**

```bash
vault_dir=$(python3 -c "from src.config.paths import get_skill_data_dir; print(get_skill_data_dir('career-ops'))")
mkdir -p "$vault_dir"/{config,data,reports,output,interview-prep,companies,notes/{hard-skills,learning}}
```

- [ ] **Step 2: Create empty tracker file**

Write `$vault_dir/data/applications.md`:

```markdown
# Applications Tracker

| # | Date | Company | Role | Score | Status | PDF | Report | Notes |
|---|------|---------|------|-------|--------|-----|--------|-------|
```

- [ ] **Step 3: Create empty story bank**

Write `$vault_dir/interview-prep/story-bank.md`:

```markdown
# Interview Story Bank

Stories accumulated across job evaluations. Each H2 section is one STAR+R story.

<!-- New stories are appended by /career-ops evaluations -->
```

- [ ] **Step 4: Create empty pipeline inbox**

Write `$vault_dir/data/pipeline.md`:

```markdown
# Pipeline Inbox

Add job URLs here (one per line) for batch processing with `/career-ops pipeline`.

<!-- URLs below this line will be processed -->
```

- [ ] **Step 5: Copy profile template**

```bash
cp skills/career-ops/config/profile.example.yml "$vault_dir/config/profile.yml"
```

- [ ] **Step 6: Write seed manifest**

Create `skills/career-ops/assets/seeds/_seed.yaml`:

```yaml
# Seed data manifest for career-ops
# These files are copied to the vault on first run if no vault data exists
seeds:
  - source: config/profile.example.yml
    target: config/profile.yml
  - source: templates/portals.example.yml
    target: portals.yml
```

- [ ] **Step 7: Commit skill-side seed file only**

```bash
git add skills/career-ops/assets/seeds/_seed.yaml
git commit -m "feat(career-ops): add seed data manifest and vault structure"
```

Note: vault files are not git-tracked (they live outside the project).

---

## Task 7: Migrate vault data from old to new layout

**Files:**
- Read: `Au-vault/career/` (old vault)
- Write: `Au-vault/career-ops/` (new vault)

- [ ] **Step 1: Write migration script**

Create a one-time Python migration script at `/tmp/migrate-career-vault.py`:

```python
"""One-time migration: Au-vault/career/ → Au-vault/career-ops/

Converts:
- Per-file jobs → tracker rows in applications.md
- Individual STAR YAML → story-bank.md
- CVs → cv.md + output/
- Companies, notes, reports → direct move
"""

import os
import shutil
import yaml
from pathlib import Path
from datetime import datetime

OLD = Path(os.path.expanduser("~/Projects/Au-vault/career"))
NEW = Path(os.path.expanduser("~/Projects/Au-vault/career-ops"))

def migrate_jobs():
    """Convert per-file jobs to applications.md tracker rows."""
    tracker = NEW / "data" / "applications.md"
    if not tracker.exists():
        return

    rows = []
    num = 0
    for queue in ["inbox", "active", "archive"]:
        queue_dir = OLD / "job-analyzer" / "jobs" / queue
        if not queue_dir.exists():
            continue
        for f in sorted(queue_dir.iterdir()):
            if not f.is_file() or f.suffix not in (".md", ".yaml", ".yml"):
                continue
            num += 1
            content = f.read_text(encoding="utf-8")

            # Parse frontmatter
            company = "Unknown"
            role = "Unknown"
            score = ""
            date = datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d")

            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    fm = yaml.safe_load(parts[1]) or {}
                    company = fm.get("company", fm.get("company_name", "Unknown"))
                    role = fm.get("position_title", fm.get("title", "Unknown"))
                    score = str(fm.get("scores", {}).get("total", fm.get("score", "")))
                    date = str(fm.get("added_at", fm.get("date_analyzed", date)))[:10]

            status_map = {"inbox": "inbox", "active": "Aplicado", "archive": "Descartada"}
            rows.append(
                f"| {num} | {date} | {company} | {role} | {score} | {status_map.get(queue, queue)} |  |  |  |"
            )

    # Also migrate analyzed jobs
    analyzed_dir = OLD / "job-analyzer" / "jobs" / "analyzed"
    if analyzed_dir.exists():
        for f in sorted(analyzed_dir.iterdir()):
            if not f.is_file() or not f.name.endswith(".md"):
                continue
            num += 1
            content = f.read_text(encoding="utf-8")
            company = "Unknown"
            role = "Unknown"
            score = ""
            date = ""
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    fm = yaml.safe_load(parts[1]) or {}
                    company = fm.get("company", "Unknown")
                    role = fm.get("position_title", fm.get("title", "Unknown"))
                    score = str(fm.get("scores", {}).get("total", fm.get("score", "")))
                    date = str(fm.get("date_analyzed", ""))[:10]
            rows.append(f"| {num} | {date} | {company} | {role} | {score} | Evaluada | | ✅ |  |")
            # Copy analyzed report to reports/
            shutil.copy2(f, NEW / "reports" / f.name)

    if rows:
        existing = tracker.read_text(encoding="utf-8")
        tracker.write_text(existing + "\n".join(rows) + "\n", encoding="utf-8")
    print(f"Migrated {num} jobs to tracker")


def migrate_star_stories():
    """Convert individual STAR YAML files to story-bank.md."""
    star_dir = OLD / "interview-prep" / "interviews" / "star-stories"
    if not star_dir.exists():
        return

    bank = NEW / "interview-prep" / "story-bank.md"
    entries = []
    for f in sorted(star_dir.iterdir()):
        if f.name in ("index.yaml", ".gitkeep") or f.is_dir():
            continue
        content = f.read_text(encoding="utf-8")
        if f.suffix in (".yaml", ".yml"):
            data = yaml.safe_load(content) or {}
            title = data.get("title", f.stem.replace("-", " ").title())
            situation = data.get("situation", "")
            task = data.get("task", "")
            action = data.get("action", "")
            result = data.get("result", "")
            reflection = data.get("reflection", "")
            entry = f"## {title}\n\n"
            if situation: entry += f"**Situation:** {situation}\n\n"
            if task: entry += f"**Task:** {task}\n\n"
            if action: entry += f"**Action:** {action}\n\n"
            if result: entry += f"**Result:** {result}\n\n"
            if reflection: entry += f"**Reflection:** {reflection}\n\n"
            entries.append(entry)
        elif f.suffix == ".md":
            entries.append(content + "\n\n")

    if entries:
        existing = bank.read_text(encoding="utf-8")
        bank.write_text(existing + "\n" + "\n".join(entries), encoding="utf-8")
    print(f"Migrated {len(entries)} STAR stories")


def migrate_cvs():
    """Migrate CV variants."""
    cvs_dir = OLD / "interview-prep" / "profile" / "cvs"
    if not cvs_dir.exists():
        return

    cvs = sorted(cvs_dir.iterdir())
    if cvs:
        # First CV becomes master
        first = cvs[0]
        shutil.copy2(first, NEW / "cv.md")
        print(f"Master CV: {first.name}")
        # Rest go to output/
        for cv in cvs[1:]:
            shutil.copy2(cv, NEW / "output" / cv.name)
            print(f"CV variant: {cv.name}")

    # Also copy candidate.md into profile
    candidate = OLD / "interview-prep" / "profile" / "candidate.md"
    if candidate.exists():
        # Merge candidate info into profile.yml
        print(f"Note: candidate.md at {candidate} should be merged into config/profile.yml manually")


def migrate_direct():
    """Direct copy for directories that need no transformation."""
    mappings = [
        (OLD / "job-analyzer" / "companies", NEW / "companies"),
        (OLD / "notes" / "hard-skills", NEW / "notes" / "hard-skills"),
        (OLD / "learning", NEW / "notes" / "learning"),
        (OLD / "reports", NEW / "reports"),
    ]
    for src, dst in mappings:
        if not src.exists():
            continue
        dst.mkdir(parents=True, exist_ok=True)
        for item in src.iterdir():
            if item.is_file():
                shutil.copy2(item, dst / item.name)
        print(f"Copied {src} → {dst}")


if __name__ == "__main__":
    print(f"Migrating {OLD} → {NEW}")
    print(f"Old vault exists: {OLD.exists()}")
    print(f"New vault exists: {NEW.exists()}")

    if not OLD.exists():
        print("Old vault not found, nothing to migrate")
        exit(0)

    migrate_jobs()
    migrate_star_stories()
    migrate_cvs()
    migrate_direct()
    print("\nMigration complete. Old vault preserved at:", OLD)
    print("Review new vault at:", NEW)
```

- [ ] **Step 2: Run migration script**

```bash
python3 /tmp/migrate-career-vault.py
```

- [ ] **Step 3: Verify migration output**

```bash
# Check new vault structure
find ~/Projects/Au-vault/career-ops/ -type f | head -30

# Check tracker has rows
head -20 ~/Projects/Au-vault/career-ops/data/applications.md

# Check story bank
head -20 ~/Projects/Au-vault/career-ops/interview-prep/story-bank.md

# Verify old vault still exists
ls ~/Projects/Au-vault/career/
```

- [ ] **Step 4: No git commit needed** (vault is outside project tree)

---

## Task 8: Create dashboard pages

**Files:**
- Create: `skills/career-ops/augur/dashboard/pipeline/page.tsx`
- Create: `skills/career-ops/augur/dashboard/companies/page.tsx`
- Create: `skills/career-ops/augur/dashboard/star/page.tsx`
- Create: `skills/career-ops/augur/dashboard/resume/page.tsx`
- Create: `skills/career-ops/augur/dashboard/reports/page.tsx`
- Create: `skills/career-ops/augur/dashboard/tsconfig.json`

- [ ] **Step 1: Copy and adapt pipeline page**

Copy `skills/career/augur/dashboard/pipeline/page.tsx` to `skills/career-ops/augur/dashboard/pipeline/page.tsx`.

Changes needed:
1. Update `StatsSection` to show `active_jobs`, `star_stories`, `reports` (not `hardening_reports`)
2. Update stat tile label from "Hardening Reports" to "Eval Reports"
3. The `JobPipelineTable` component stays largely the same — same tool names, same data shape

- [ ] **Step 2: Create companies page**

Create `skills/career-ops/augur/dashboard/companies/page.tsx` — a card grid showing company research profiles. Use `useMcpQuery` with `get-career-companies`. Follow the same pattern as the pipeline page: `'use client'` directive, `useMcpQuery` hook, `GlassCard` wrapper, search input, card grid layout.

- [ ] **Step 3: Create STAR stories page**

Create `skills/career-ops/augur/dashboard/star/page.tsx` — a table of STAR+R stories with category filters. Use `useMcpQuery` with `list-career-star`. Include pill filters for categories (leadership, teamwork, problem-solving, conflict, failure, achievement, general).

- [ ] **Step 4: Create resumes page**

Create `skills/career-ops/augur/dashboard/resume/page.tsx` — list of CV variants. Use `useMcpQuery` with `list-career-resumes`. Show name, type badge (md/pdf/html), last modified date.

- [ ] **Step 5: Create reports page**

Create `skills/career-ops/augur/dashboard/reports/page.tsx` — evaluation reports table. Use `useMcpQuery` with `get-career-reports`. Show company, title, score, date. Clicking a row can expand to show full report content via `get-career-report`.

- [ ] **Step 6: Create tsconfig.json**

```json
{
  "extends": "../../../../apps/dashboard/tsconfig.json",
  "compilerOptions": {
    "paths": {
      "@/*": ["../../../../apps/dashboard/*"],
      "@/features/*": ["../../../../apps/dashboard/features/*"]
    }
  },
  "include": ["./**/*.ts", "./**/*.tsx"]
}
```

- [ ] **Step 7: Commit**

```bash
git add skills/career-ops/augur/dashboard/
git commit -m "feat(career-ops): add dashboard pages for pipeline, companies, STAR, resume, reports"
```

---

## Task 9: Migrate references and action prompts from old skill

**Files:**
- Copy: `skills/career/references/workflow-interview-prep.md` → `skills/career-ops/references/`
- Copy: `skills/career/assets/actions/*.md` → `skills/career-ops/assets/actions/`

- [ ] **Step 1: Copy references**

```bash
cp skills/career/references/workflow-interview-prep.md skills/career-ops/references/
```

- [ ] **Step 2: Copy action prompts**

```bash
cp skills/career/assets/actions/*.md skills/career-ops/assets/actions/ 2>/dev/null || echo "No action files to copy"
# Also check commands/ dir for action prompts
for f in skills/career/commands/*.md; do
  cp "$f" skills/career-ops/assets/actions/
done
```

- [ ] **Step 3: Commit**

```bash
git add skills/career-ops/references/ skills/career-ops/assets/actions/
git commit -m "feat(career-ops): migrate references and action prompts from career skill"
```

---

## Task 10: Re-hub business skills

**Files:**
- Modify: `skills/venture-augur/SKILL.md` — add business hub owner config
- Modify: `skills/enterprise/SKILL.md` — change hub to business
- Modify: `skills/consulting-template/SKILL.md` — change hub to business
- Modify: `skills/content/SKILL.md` — change hub to business
- Modify: `skills/linkedin-writer/SKILL.md` — change hub to business
- Modify: `skills/post/SKILL.md` — change hub to business
- Modify: `skills/design-content-pipeline/SKILL.md` — change hub to business
- Modify: `skills/project-dev/SKILL.md` — change hub to business
- Modify: `skills/growth/SKILL.md` — change hub from brain to business

- [ ] **Step 1: Add business hub config to venture-augur**

In `skills/venture-augur/SKILL.md`, update the `x-augur-config` section to add hub owner config:

```yaml
x-augur-hub: business
x-augur-config:
  hub:
    id: business
    owner: true
    title: Business
    nav_order: 25
    subtitle: Content, consulting, enterprise, and growth
    icon: Building2
    category: business
    iconBg: bg-amber-500/20
    iconColor: text-amber-400
    overview:
      search: true
      layout: masonry
```

- [ ] **Step 2: Update each skill's x-augur-hub**

For each of these 8 skills, change `x-augur-hub: career` (or `brain` for growth) to `x-augur-hub: business`:

- `skills/enterprise/SKILL.md`
- `skills/consulting-template/SKILL.md`
- `skills/content/SKILL.md`
- `skills/linkedin-writer/SKILL.md`
- `skills/post/SKILL.md`
- `skills/design-content-pipeline/SKILL.md`
- `skills/project-dev/SKILL.md`
- `skills/growth/SKILL.md`

- [ ] **Step 3: Commit**

```bash
git add skills/venture-augur/SKILL.md skills/enterprise/SKILL.md skills/consulting-template/SKILL.md skills/content/SKILL.md skills/linkedin-writer/SKILL.md skills/post/SKILL.md skills/design-content-pipeline/SKILL.md skills/project-dev/SKILL.md skills/growth/SKILL.md
git commit -m "feat: create business hub, re-hub 9 skills from career/brain to business"
```

---

## Task 11: Wire hub layout for career

**Files:**
- Modify: `apps/dashboard/app/career/layout.tsx` (if hub metadata is hardcoded)

- [ ] **Step 1: Check if career layout needs changes**

Read `apps/dashboard/app/career/layout.tsx`. If it references old career skill metadata, update to match new career-ops hub config. Most likely it uses dynamic hub resolution from SKILL.md, in which case no changes are needed since career-ops took over the `career` hub id.

- [ ] **Step 2: Create business hub layout if needed**

Check if `apps/dashboard/app/business/` exists. If not, it may need to be created or the dynamic hub system will auto-generate it. Check how other hubs are generated (likely via catch-all routes).

- [ ] **Step 3: Run mount-plugins or equivalent to regenerate**

```bash
# The dashboard mount system should pick up the new hub config automatically
# Verify by checking generated files
ls apps/dashboard/app/career/
ls apps/dashboard/app/business/ 2>/dev/null || echo "Business hub dir doesn't exist yet"
```

- [ ] **Step 4: Commit if changes were made**

```bash
git add apps/dashboard/app/
git commit -m "feat: wire career and business hub layouts"
```

---

## Task 12: Browser-verify dashboard pages

**No files changed in this task — verification only.**

- [ ] **Step 1: Restart MCP server**

Use the dashboard lifecycle gate to restart:

```bash
python3 -m src.scripts.dashboard_lifecycle request-action restart-mcp
```

Wait 8 seconds for MCP to initialize.

- [ ] **Step 2: Start dashboard if not running**

```bash
# Use /dev-build or lifecycle gate
python3 -m src.scripts.dashboard_lifecycle request-action start
```

- [ ] **Step 3: Navigate to each page in Chrome and verify**

Open each URL and wait 6+ seconds for data load:

1. `http://localhost:3000/career/pipeline` — verify job table shows data (from tracker or seed)
2. `http://localhost:3000/career/companies` — verify company cards appear
3. `http://localhost:3000/career/star` — verify STAR stories table
4. `http://localhost:3000/career/resume` — verify CV list
5. `http://localhost:3000/career/reports` — verify reports table

For each page, confirm:
- Real data values appear (not just headings or skeletons)
- No console errors
- Filters and search work

- [ ] **Step 4: If any page fails, debug and fix before proceeding**

Do NOT proceed to skill deletion if any page shows "No data" or errors.

---

## Task 13: Delete superseded skills (with approval)

**Files:**
- Delete: `skills/career/` (entire directory)
- Delete: `skills/coach/` (entire directory)
- Delete: `skills/interview-coach/` (entire directory)
- Delete: `skills/auto-career-hub-coverage/` (entire directory)

- [ ] **Step 1: Present functionality diff for user approval**

List capabilities being lost that need explicit approval:

| Capability | Location | Career-ops equivalent | Verdict |
|---|---|---|---|
| `career-hardening-quiz` | `skills/career/scripts/career_hardening.py` | No equivalent | **USER DECIDES** |
| `career-hardening-reading` | `skills/career/scripts/hardening_reading.py` | No equivalent | **USER DECIDES** |
| `career-hardening-report` | `skills/career/scripts/hardening_report.py` | No equivalent | **USER DECIDES** |
| `career-hardening-attach` | `skills/career/scripts/hardening_attachments.py` | No equivalent | **USER DECIDES** |
| `career-hardening-collectors` | `skills/career/scripts/hardening_collectors.py` | No equivalent | **USER DECIDES** |
| `manage-career-habits` | `skills/career/scripts/mcp/tools.py` | No equivalent | **USER DECIDES** |
| Hard skills page | `skills/career/augur/dashboard/` | Notes in vault only | **USER DECIDES** |

**Wait for user to approve or request ports before deleting.**

- [ ] **Step 2: Delete approved skills**

```bash
rm -rf skills/career/
rm -rf skills/coach/
rm -rf skills/interview-coach/
rm -rf skills/auto-career-hub-coverage/
```

- [ ] **Step 3: Commit**

```bash
git add -A skills/career/ skills/coach/ skills/interview-coach/ skills/auto-career-hub-coverage/
git commit -m "chore: delete career, coach, interview-coach, auto-career-hub-coverage (superseded by career-ops)"
```

---

## Task 14: Clean up stale references

**Files:**
- Various files across the codebase that reference deleted skills

- [ ] **Step 1: Search for stale references with system grep**

```bash
grep -rn 'skills/career/' --include='*.py' --include='*.ts' --include='*.tsx' --include='*.yaml' --include='*.yml' --include='*.md' . | grep -v node_modules | grep -v '.git/' | grep -v 'career-ops'
```

Also search for split-segment patterns:

```bash
grep -rn '"career"' --include='*.py' . | grep -v career-ops | grep -v node_modules
```

- [ ] **Step 2: Search for old hub references**

```bash
grep -rn 'x-augur-hub: career' skills/*/SKILL.md | grep -v career-ops
```

All results should be zero — if not, those skills need to be re-hubbed.

- [ ] **Step 3: Search for deleted skill references in config files**

```bash
grep -rn 'coach\|interview-coach\|auto-career-hub-coverage' config/ apps/ --include='*.yaml' --include='*.ts' --include='*.json' | grep -v node_modules | grep -v '.git/'
```

- [ ] **Step 4: Fix any stale references found**

Update or remove each reference to point to `career-ops` or remove entirely.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore: clean up stale references to deleted career skills"
```

---

## Task 15: Install Node.js dependencies for scripts

- [ ] **Step 1: Install career-ops script dependencies**

```bash
cd skills/career-ops/scripts && npm install
```

- [ ] **Step 2: Install Playwright chromium (if not already installed)**

```bash
npx playwright install chromium
```

- [ ] **Step 3: Verify PDF generation works**

```bash
# Quick smoke test — this should error about missing cv.md if deps are correct
node skills/career-ops/scripts/generate-pdf.mjs --help 2>&1 || echo "Script loaded OK"
```

- [ ] **Step 4: No commit needed** (node_modules is gitignored)

---

## Task 16: Final verification and summary

- [ ] **Step 1: Verify skill structure**

```bash
ls -la skills/career-ops/
ls skills/career-ops/commands/
ls skills/career-ops/scripts/mcp/
ls skills/career-ops/augur/dashboard/
```

- [ ] **Step 2: Verify hub assignments**

```bash
grep 'x-augur-hub:' skills/*/SKILL.md | sort
```

Expected: career-ops → career, venture-augur + 8 others → business

- [ ] **Step 3: Verify old skills deleted**

```bash
ls skills/career/ 2>/dev/null && echo "FAIL: career still exists" || echo "OK: career deleted"
ls skills/coach/ 2>/dev/null && echo "FAIL: coach still exists" || echo "OK: coach deleted"
ls skills/interview-coach/ 2>/dev/null && echo "FAIL: interview-coach still exists" || echo "OK: interview-coach deleted"
```

- [ ] **Step 4: Verify vault state**

```bash
ls ~/Projects/Au-vault/career-ops/
ls ~/Projects/Au-vault/career/  # Should still exist as backup
```

- [ ] **Step 5: Run dashboard build to check for errors**

```bash
pnpm --filter dashboard build
```

- [ ] **Step 6: Final browser check of all 5 career pages**

Navigate to each page and verify data loads correctly in the browser.
