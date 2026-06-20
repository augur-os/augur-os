# Vault Dashboard Wiring — TSX Pages Plan (Plan B)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build 5 custom TSX dashboard pages for the highest-value vault skills.

**Architecture:** Each page is a standalone TSX file in `skills/{skill}/augur/dashboard/`. Pages use `useMcpQuery` for data fetching and existing MCP tools. All pages follow existing dashboard component patterns (shadcn/ui, CSS variables, BlockShell).

**Tech Stack:** TypeScript, React, shadcn/ui, useMcpQuery/useMcpMutation hooks

**Prerequisite:** Plan A (infrastructure) must be complete — provides `vault-file-read`, `vault-file-write`, and enhanced `list-skill-vault-notes`.

---

## Verified MCP Tools

| Page | Available Tools |
|------|----------------|
| Career Pipeline | get-career-job-counts, add-career-job, list-skill-vault-notes |
| Career Profile | career-read-cv, career-create-cv, list-skill-vault-notes, vault-file-read |
| Venture Content | get-venture-gtm, get-market-competition, list-skill-vault-notes, vault-file-read, vault-file-write |
| Growth Dashboard | career-learning, career-knowledge, career-hardening-report, manage-career-habits, list-skill-vault-notes |
| Growth Knowledge | list-skill-vault-notes, vault-file-read |

---

### Task 1: Career Pipeline Tracker

**File:** Create `skills/career/augur/dashboard/pipeline.tsx`

Page layout:
- Stat bar: job counts by status via `get-career-job-counts`
- Data table: jobs list via `add-career-job` (which returns job list), with pill filters for status (inbox/active/offer/rejected/archive), search on title+company
- Action bar: analyze-job, sync-jobs actions via `list-skill-actions`

Reference: old `pipeline.yaml` from git commit `fd4113260^`

- [ ] Read existing career dashboard files to understand patterns
- [ ] Read the `get-career-job-counts` and `add-career-job` tool implementations to understand response shapes
- [ ] Create the TSX page with stat bar + data table + action bar
- [ ] Verify build passes
- [ ] Commit

---

### Task 2: Career Profile Hub

**File:** Create `skills/career/augur/dashboard/profile.tsx`

Page layout:
- Profile summary card from candidate.md frontmatter (name, target roles, salary) via `vault-file-read`
- Tab navigation across vault subdirs: interview-prep, job-analyzer, learning, notes, reports
- Each tab renders files from that subdir via `list-skill-vault-notes` with the enhanced directory grouping
- CV cards in interview-prep tab showing CVs from `career-read-cv`

- [ ] Read career vault structure and career-read-cv tool response shape
- [ ] Create the TSX page with profile card + tabbed vault browsing
- [ ] Verify build passes
- [ ] Commit

---

### Task 3: Venture-augur Content Workspace

**File:** Create `skills/venture-augur/augur/dashboard/content.tsx`

Page layout:
- Sidebar navigation by vault subdirs (14 dirs: brand, competition, content, financials, gtm, ideas, marketing, notes, outreach, overview, planning, sales, strategy)
- Main area: selected subdir's files as markdown preview cards via `list-skill-vault-notes` groups
- Click to expand full content via `vault-file-read`
- Quick stats bar: total docs, last updated per category
- "New doc" button using `vault-file-write`

- [ ] Read venture-augur vault structure
- [ ] Create the TSX page with sidebar + content area + new doc action
- [ ] Verify build passes
- [ ] Commit

---

### Task 4: Growth Learning Dashboard

**File:** Create `skills/growth/augur/dashboard/dashboard.tsx`

Page layout:
- Progress cards: courses (career-learning), knowledge areas (career-knowledge), hardening status (career-hardening-report)
- Guided prompts: "Growth check-in", "Add habit", "Review knowledge" — dispatch to IDE
- Recent activity feed: last 10 files from growth/ via `list-skill-vault-notes`

Reference: old `skills/growth/augur/dashboard/page.tsx` (293 lines, glass cards) from git commit `cb36b5dc1^`

- [ ] Read old growth TSX from git history for design patterns
- [ ] Read career-learning, career-knowledge, career-hardening-report response shapes
- [ ] Create the TSX page with progress cards + prompts + activity feed
- [ ] Verify build passes
- [ ] Commit

---

### Task 5: Growth Knowledge Browser

**File:** Create `skills/growth/augur/dashboard/knowledge.tsx`

Page layout:
- File listing organized by frontmatter `topic`/`category`, falling back to directory grouping via `list-skill-vault-notes` groups
- Expandable notes: click to read full content via `vault-file-read`
- Spaced repetition: files with `review_date` frontmatter get "due for review" badge
- Search + filter by topic

- [ ] Read growth vault files to understand frontmatter patterns
- [ ] Create the TSX page with topic grouping + expandable content + review badges
- [ ] Verify build passes
- [ ] Commit
