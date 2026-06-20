---
status: Implemented
date: '2026-02-28'
deciders: []
related: []
hub: null
tags:
- import
- notion
- home
- stuff
- export
superseded_by: null
---

# ADR-179: Import Notion "Home Stuff" Export into Lifestyle Hub

**Category**: Data Import

## Context

A Notion export titled "Home Stuff" contains personal/family data organized into 7 categories:
- **Recipes**: 16 recipes (CSV + markdown) — already imported to `recipe-manager/`
- **Travel Plans**: 6 trips (CSV + markdown) with detailed packing lists and notes
- **Kids**: 4 pages — growth tracking, learning resources, AI education article, gifted program course
- **Movie List**: 2 movies (want-to-watch / watched)
- **Shopping List**: Checklist with links
- **Notes**: Notion template links, Hebrew-English translations, misc links
- **ScreenTech**: Warranty certificate with image

The lifestyle hub already declares `travel`, `movies`, `shopping` data_paths in augur.yaml but these directories don't exist. Recipes are fully imported.

## Decision

Import all new content into the existing `plugins/lifestyle/skills/lifestyle/augur/data/` structure:

| Source | Target Path | Format |
|--------|-------------|--------|
| Travel Plans CSV + 6 markdown | `travel/` | One YAML per trip |
| Movie List markdown | `movies/` | `watchlist.yaml` |
| Shopping List markdown | `shopping/` | `list.yaml` |
| Kids (4 pages) | `knowledge/kids/` | Markdown files (cleaned) |
| Notes | `notes/` | Merge into existing notes dir |
| ScreenTech | `knowledge/` | Markdown + asset |

### Data Format Decisions

**Travel**: YAML files per trip following pattern:
```yaml
id: cyprus-protaras-2025
title: "Cyprus Protaras"
date: "2025-08-27"
status: booked  # booked | idea | completed
order_tickets_by: null
notes: []
packing: []
```

**Movies**: Single watchlist YAML:
```yaml
movies:
  - title: "Foundation"
    status: want-to-watch
    rating_imdb: 7.6
    type: TV Series
    year: 2021
    url: "https://www.imdb.com/title/tt0804484/"
  - title: "The White Lotus"
    status: watched
    ...
```

**Shopping**: Single YAML checklist:
```yaml
items:
  - name: "BUG-A-SALT salt gun"
    checked: false
    url: "https://ksp.co.il/link/BUG-A-SALT"
  ...
```

**Kids knowledge**: Clean markdown files with Notion hashes removed from filenames.

### Files to Create

```
plugins/lifestyle/skills/lifestyle/augur/data/
├── travel/
│   ├── cyprus-protaras-2025.yaml
│   ├── winter-holiday-2025.yaml
│   ├── camping-2026.yaml
│   ├── thailand-vietnam-2026.yaml
│   ├── japan-bar-mitzvah-2027.yaml
│   └── olympics-2028.yaml
├── movies/
│   └── watchlist.yaml
├── shopping/
│   └── list.yaml
├── knowledge/
│   ├── kids/
│   │   ├── eitan-growth.md
│   │   ├── noga-growth.md
│   │   ├── ai-for-kids.md
│   │   └── gifted-program-grade-6.md
│   └── screentech-warranty.md
└── notes/
    └── notion-notes.md
```

### What's NOT Imported
- Recipe CSV/markdown (already imported)
- Notion hash IDs in filenames (stripped)
- Swedish Meatballs screenshot images (recipe already has full YAML data)

## Impact Manifest

```yaml
paths_created:
  - plugins/lifestyle/skills/lifestyle/augur/data/travel/
  - plugins/lifestyle/skills/lifestyle/augur/data/movies/
  - plugins/lifestyle/skills/lifestyle/augur/data/shopping/
  - plugins/lifestyle/skills/lifestyle/augur/data/knowledge/
  - plugins/lifestyle/skills/lifestyle/augur/data/knowledge/kids/
apis_changed: []
patterns_deprecated: []
files_affected: 13
```
