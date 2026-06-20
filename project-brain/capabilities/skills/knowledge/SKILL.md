---
name: knowledge
x-augur-type: domain
x-augur-group: brain
x-augur-release: mvp
x-augur-tags:
- memory
- search
- rag
- documents
- indexing
description: Use when searching memory, documents, or project knowledge, curating
  daily logs into persistent memory, rebuilding search indexes, or managing the RAG
  knowledge base.
x-augur-tab: memory
x-augur-license: MIT
x-augur-metadata:
  version: 0.5.0
  author: Augur
  mcp-server: augur
x-augur-requires-platform: true
x-augur-mcp-tools:
- knowledge-memory-daily-logs
- knowledge-memory-daily-logs-open
- knowledge-memory-daily-logs-read
- knowledge-memory-profile
- knowledge-memory-read
- knowledge-memory-workspace-open
- knowledge-project-index-rebuild
- knowledge-summarize-file
- knowledge-summarize-url
- memory-search
- unified-search
x-augur-dashboard-pages:
- route: /workspace/memory
  title: Memory
  icon: Brain
  order: 10
  keywords:
  - memory
  - decisions
  - patterns
  - preferences
- route: /workspace/memory-review
  title: Review
  icon: ClipboardCheck
  order: 17
  keywords:
  - memory
  - review
  - approve
  - promote
  - candidates
  - federation
- route: /workspace/daily-logs
  title: Daily Logs
  icon: Calendar
  order: 12
  keywords:
  - daily
  - logs
  - memory
- route: /workspace/profile
  title: Profile
  icon: User
  order: 13
  keywords:
  - profile
  - human-api
  - memory
- route: /workspace/harness
  title: Harness
  icon: Activity
  order: 16
  keywords:
  - capability
  - diagnostics
  - provenance
  - repair
- route: /workspace/settings
  title: Brains
  icon: Layers
  order: 15
  keywords:
  - brain
  - federation
  - projection
  - registry
  - init
x-augur-data-dir: knowledge
x-augur-config:
  contributions:
    blocks:
    - id: search
      type: action-bar
      title: Knowledge Search
      icon: Search
      config_schema:
        mode:
          type: enum
          options:
          - memory
          - documents
          - projects
          - all
          default: all
      data_source:
        mcp_tool: knowledge-search-status
    - id: index
      type: ops-board
      title: Knowledge Index
      icon: Database
      expandTo: /workspace/memory
      search: true
      config_schema:
        show_project_index:
          type: boolean
          default: true
      data_source:
        mcp_tool: knowledge-project-index-rebuild
    - id: memory
      type: data-list
      title: Memory
      icon: Brain
      expandTo: /workspace/memory
      search: true
      filters:
      - field: category
        type: pills
        label: Category
        values:
        - decisions
        - patterns
        - preferences
      config_schema:
        category:
          type: enum
          options:
          - all
          - decisions
          - patterns
          - preferences
          default: all
      data_source:
        mcp_tool: memory-stats
    - id: documents
      type: data-table
      title: Documents
      icon: FileText
      expandTo: /browse?category=documents
      search: true
      filters:
      - field: type
        type: pills
        label: Type
        values:
        - pdf
        - markdown
        - text
        - image
      - field: hub
        type: pills
        label: Hub
        values:
        - ai
        - dev
        - admin
        - core
        - finance
        - health
        - home
        - career
      export_enabled: true
      config_schema:
        sort_by:
          type: enum
          options:
          - name
          - hub
          - date
          default: date
      data_source:
        mcp_tool: list-knowledge-documents
    - id: ocr
      type: action-bar
      title: OCR Scanner
      icon: ScanLine
      config_schema: {}
      data_source:
        mcp_tool: list-knowledge-ocr-queue
  modals:
    ocr-scan:
      title: OCR Scan
      description: Upload an image or PDF to extract text via OCR (beta)
      submitTool: /api/knowledge/ocr
      submitLabel: Scan Document
      fields:
      - name: file
        label: File
        type: file
        required: true
        accept: image/*,.pdf
        placeholder: Upload image or PDF
      - name: language
        label: Language
        type: select
        options:
        - value: eng
          label: English
        - value: deu
          label: German
        - value: fra
          label: French
        - value: spa
          label: Spanish
        - value: rus
          label: Russian
        - value: auto
          label: Auto-detect
    summarize-url:
      title: Summarize URL
      description: Fetch and summarize a web page or article
      submitTool: mcp://augur/knowledge-summarize-url
      submitLabel: Summarize
      fields:
      - name: url
        label: URL
        type: text
        required: true
        placeholder: https://example.com/article
---














# Knowledge Skill

## Gotchas

### 1. RAG index goes stale after large changes -- rebuild explicitly
The project index (`~/Library/Application Support/Augur/rag/project-index.yaml`) is not automatically rebuilt when skills, ADRs, or documents change. After major refactors or skill additions, run `knowledge-project-index-rebuild` or the dashboard "Rebuild Project Index" action. Stale indexes silently return outdated or missing results.

### 2. Memory and vault are distinct data stores with different paths
Memory lives at `get_memory_dir()/MEMORY.md` and `daily/*.md` (external vault, user-editable). The project index lives at `~/Library/Application Support/Augur/rag/` (platform state dir). Confusing these paths -- e.g., searching vault memory via project-index tools -- returns nothing because they are separate search scopes with separate indexes.

### 3. Search scope must be explicit -- "all" searches three separate backends
The `unified-search` tool queries memory, documents, and project index in parallel. Each backend may return zero results independently. When debugging "search returns nothing," check which scope is empty: memory may be populated while the project index is stale, or vice versa.

### 4. OCR ingestion is beta -- do not treat it as production
The OCR scan feature (`/api/knowledge/ocr`) currently returns a beta response. API routes exist and the modal works, but backend text extraction is not fully wired. Do not build workflows that depend on OCR output -- it will return placeholder data.

## Problem Statement

Users need one place to:
1. Search prior decisions and preferences from external vault memory (`get_memory_dir()`)
2. Search project knowledge (skills, ADRs, RAG docs, indexed artifacts)
3. Curate daily logs into persistent memory with cross-session persistence
4. Rebuild searchable indexes when the knowledge base changes

Memory persistence across sessions is the core value — decisions, preferences, and patterns survive conversation boundaries. Without this skill, retrieval is fragmented and maintenance actions are manual.

## Implementation Details

> See [references/implementation-details.md](references/implementation-details.md) for API routes, dashboard pages, action map, core user journeys, architecture constraints, and data inputs.

## Document Source Roots

The document index scans the configured documents directory plus approved user source roots:

- `get_documents_dir()` / Au-docs,
- `~/Desktop` when present,
- `~/Downloads` when present.

Desktop and Downloads are indexed in place. Indexing writes RAG metadata and media stubs only; it does not move, rename, delete, transcribe, or OCR files. Browse `Sweep` is the explicit lifecycle action that can move a file into Au-docs.

## Known Gaps

1. OCR backend extraction is still beta and not production-ready.

## References

- `skills/knowledge/SKILL.md`
- `skills/knowledge/scripts/mcp/__init__.py`
- `docs/agent-topics/ARCHITECTURE.md`
- `docs/agent-topics/DASHBOARD.md`

## Additional resources
- [commands/curate-memory.md](commands/curate-memory.md)
- [commands/regenerate-memory-report.md](commands/regenerate-memory-report.md)
- [references/documentation-standards.md](references/documentation-standards.md)
- [references/knowledge-workflow.md](references/knowledge-workflow.md)
- [references/docs/ACCEPTANCE_CRITERIA.md](references/docs/ACCEPTANCE_CRITERIA.md)
- [evals/rank.json](evals/rank.json)
- [assets/seeds/_seed.yaml](assets/seeds/_seed.yaml)
- [assets/seeds/rag-projects.yaml](assets/seeds/rag-projects.yaml)
