---
status: Implemented
date: ''
deciders: []
related: []
hub: null
tags:
- import
- notion
- books
- database
- lifestyle
superseded_by: null
---

# ADR-184: Import Notion Books Database to Lifestyle Hub

**Date:** 2026-02-28
**Source:** `/import ~/Downloads/ExportBlock-804b5456-...`

## Context

A Notion export containing a "Books" database needs to be imported into the Augur dashboard. The export contains:

- **1 CSV** with 18 books (columns: Book (Author), Key Insights / Summary, Target Audience, Link, category)
- **18 markdown files** — thin Notion per-row exports (title + fields, no deep notes)
- **2 CSV variants** — standard and `_all` export

The lifestyle hub already has a `reading` tab, but it's designed for URL-based reading list items (articles, links). The books data has richer metadata (author, categories, target audience) that warrants a dedicated skill.

## Decision

Create a new `books` skill under the `lifestyle` bundle (`plugins/lifestyle/skills/books/`) that contributes 2 tabs to the lifestyle hub:

1. **Books Catalog** (`books`) — sortable/searchable data table with all book entries
2. **Book Notes** (`book-notes`) — knowledge browser for individual book pages (expandable with personal notes)

### Data Transformation

**CSV → YAML** (`books.yaml`):
```yaml
books:
  - id: principles-of-building-ai-agents
    title: "Principles of Building AI Agents"
    author: "Sam Bhagwat"
    summary: "Comprehensive guide to building AI agents"
    audience: "AI engineers, technical leaders"
    link: "https://a.co/d/aTSgr9W"
    categories: ["AI Development Framework", "Technical Guide"]
    status: unread
  # ... 17 more entries
```

**Markdown files → cleaned knowledge pages** with YAML frontmatter:
```markdown
---
title: "Principles of Building AI Agents"
author: "Sam Bhagwat"
tags: ["AI Development Framework", "Technical Guide"]
source: notion-import
imported: "2026-02-28"
---

Comprehensive guide to building AI agents

Target audience: AI engineers, technical leaders
```

### Generated Files

| File | Purpose |
|------|---------|
| `plugins/lifestyle/skills/books/augur.yaml` | Skill config, hub contributions |
| `plugins/lifestyle/skills/books/augur/data/books.yaml` | Book catalog data |
| `plugins/lifestyle/skills/books/augur/data/notes/*.md` | Individual book knowledge pages |
| `plugins/lifestyle/skills/books/augur/dashboard/books/page.tsx` | Catalog table tab |
| `plugins/lifestyle/skills/books/augur/dashboard/book-notes/page.tsx` | Knowledge browser tab |
| `plugins/lifestyle/skills/books/augur/api/books/route.ts` | Catalog API |
| `plugins/lifestyle/skills/books/augur/api/book-notes/route.ts` | Notes API |

### Tab Ordering

- `books` tab: order 70 (after travel at 60, before overflow)
- `book-notes` tab: order 80

## Consequences

- Books data is separated from the URL-based reading list
- Knowledge pages can be expanded with personal notes over time
- Both tabs contribute to the existing lifestyle hub via `contributes_to: lifestyle`
- No changes to existing reading tab or data
