---
status: Implemented
date: '2025-02-17'
deciders: []
related: []
hub: null
tags:
- organizer
- hub
- hardening
superseded_by: null
---

# ADR-111: Organizer Hub Hardening

**Hub**: `/organizer`  
**Composite Score**: 35/100 (critical-overhaul)

## Executive Summary

The Organizer hub requires a complete reimagining from a basic "system cleanup" tool to an **AI-powered smart file organization system**. The current implementation has non-functional mock data and missing APIs. The new vision: analyze files in common folders (Downloads, Desktop, Documents, Augur), use AI to understand content, and suggest intelligent moves/renames.

### Wow Effect: Auto-Organize Downloads

The headline demo will be **one-click intelligent file organization**:
1. User clicks "Analyze Downloads"
2. AI scans all files, reads content (for text-based files)
3. For each file, suggests: new name, destination folder, reasoning
4. User reviews batch suggestions and applies with one click
5. Example: `perplexity_tam_competition_research.md` → move to `~/Augur/data/venture/market-analysis/tam-competition.md`

## Audit Results

| # | Dimension | Score | Status | Phase | Priority |
|---|-----------|-------|--------|-------|----------|
| 1 | UI Compliance | 65 | needs-work | 3 | P3 |
| 2 | Page Coverage | 75 | needs-work | 2 | P2 |
| 3 | API Completeness | 20 | critical | 1 | P1 |
| 4 | MCP Tool Wiring | 0 | critical | 1 | P1 |
| 5 | Performance | 70 | needs-work | 2 | P2 |
| 6 | User Value | 35 | critical | 1 | P1 |
| 7 | Workflows | 10 | critical | 1 | P1 |
| 8 | Cross-Hub Connectivity | 30 | needs-work | 2 | P2 |
| 9 | Action Buttons | 25 | critical | 1 | P1 |
| 10 | Wow Effect | 20 | critical | 1 | P1 |

## User Notes

> The idea of this hub is less system cleanup but more of analyzing common folders like Downloads, Desktop, Documents and Augur - then for each file rename it by smart content analysis and move to the right place. Example: I have worked on TAM (Total Addressable Market) and competition investigation in Perplexity and then asked it to export in markdown so now I have a markdown file in my Downloads. I want from this dashboard to run a flow that analyzes the folder and suggests me to move this file to my venture data folder where it belongs.

## Implementation Phases

### Phase 1: Critical Infrastructure (P1) - Week 1

#### 1.1 Create API Routes

Create functional API endpoints:

```typescript
// app/api/organizer/analyze/route.ts
// POST - Analyze a folder and return file suggestions
// Body: { folder: string, options: { maxFiles?: number } }
// Returns: { files: FileAnalysis[], summary: FolderSummary }

interface FileAnalysis {
  path: string;
  name: string;
  size: number;
  mimeType: string;
  suggestedName?: string;
  suggestedDestination?: string;
  reasoning?: string;
  confidence: number;
}

// app/api/organizer/execute/route.ts
// POST - Execute approved moves/renames
// Body: { operations: FileOperation[] }
// Returns: { results: OperationResult[] }

// app/api/organizer/folders/route.ts
// GET - List watched/managed folders
// Returns: { folders: FolderConfig[] }
```

#### 1.2 MCP Tool Wiring

Wire the hub to MCP tools for AI-assisted analysis:

```yaml
# config/mcp/organizer.yaml
tools:
  - name: analyze_folder
    description: Analyze files in a folder and suggest organization
    mcp_ref: mcp://augur/organizer/analyze
    
  - name: execute_moves
    description: Execute approved file moves and renames
    mcp_ref: mcp://augur/organizer/execute
    
  - name: scan_content
    description: Read file content for AI analysis
    mcp_ref: mcp://augur/file-read
```

#### 1.3 Core Service Implementation

Create the organizer service:

```python
# plugins/productivity/skills/organizer/service/organizer_service.py

class OrganizerService:
    """
    Core service for intelligent file organization.
    
    Uses:
    - File system scanning (async)
    - Content analysis (text extraction, metadata)
    - AI classification (LLM-assisted categorization)
    - User folder mapping (personal knowledge structure)
    """
    
    async def analyze_folder(self, folder_path: str) -> FolderAnalysis:
        """Scan folder and generate suggestions for each file."""
        
    async def classify_file(self, file_path: str, content: str) -> FileClassification:
        """Use AI to classify file content and suggest destination."""
        
    async def execute_operations(self, operations: list[FileOperation]) -> list[OperationResult]:
        """Execute approved moves/renames with rollback support."""
```

#### 1.4 Replace Mock Data

Update all pages to use real API calls:

- `page.tsx`: Replace mock stats with real folder analysis
- `cleanup/page.tsx`: Remove cleanup focus, add folder analysis
- `duplicates/page.tsx`: Keep duplicate detection but wire to real API
- `organize/page.tsx`: Replace mock preview with AI-powered suggestions

### Phase 2: Completeness (P2) - Week 2

#### 2.1 Page Coverage

- Remove empty `/system-cleanup/` directory
- Create `/settings/` subpage for folder configuration
- Create `/history/` subpage for move history with undo

#### 2.2 Cross-Hub Connectivity

- Add link to `/capture/` for "Capture to Knowledge Base" action
- Add link to `/venture/` when files are classified as venture-related
- Add link to `/career/` when files are classified as career-related

#### 2.3 Performance Optimization

- Implement streaming analysis for large folders
- Add progress indicators during scan
- Cache analysis results with invalidation

### Phase 3: Polish (P3) - Week 3

#### 3.1 UI Compliance

- Migrate from `glass-panel` to `GlassCard` component
- Add consistent color scheme (amber/orange for organizer theme)
- Improve typography and spacing consistency

#### 3.2 Enhanced Features

- Batch undo/redo for operations
- Folder rules configuration UI
- Confidence score visualization
- File preview before moving

## Architecture Changes

### Current State
```
organizer/
├── page.tsx (mock stats, broken API call)
├── cleanup/page.tsx (mock cleanup categories)
├── duplicates/page.tsx (mock duplicate groups)
├── organize/page.tsx (mock file preview)
└── system-cleanup/ (empty)
```

### Proposed State
```
organizer/
├── page.tsx (folder overview, quick analysis)
├── analyze/page.tsx (detailed analysis with AI suggestions)
├── duplicates/page.tsx (real duplicate detection)
├── rules/page.tsx (folder rules configuration)
├── history/page.tsx (move history with undo)
└── layout.tsx (hub navigation tabs)

api/organizer/
├── analyze/route.ts (folder analysis)
├── execute/route.ts (file operations)
├── folders/route.ts (folder management)
├── rules/route.ts (rule CRUD)
└── history/route.ts (operation history)
```

## Team Split

| Track | Owner | Deliverables |
|-------|-------|--------------|
| Backend | Backend Dev | API routes, OrganizerService, MCP wiring |
| Frontend | Frontend Dev | Page updates, GlassCard migration, action buttons |
| AI/ML | AI Engineer | Content classification, folder suggestion logic |

## Implementation Prompt

Copy this prompt to a new session to execute the hardening:

```
Implement ADR-111: Organizer Hub Hardening

Context: The organizer hub needs to transform from a mock "system cleanup" tool to an AI-powered smart file organization system.

## Core Requirements

1. **API Routes** (Priority 1)
   - Create `/api/organizer/analyze/route.ts` - analyze folder, return suggestions
   - Create `/api/organizer/execute/route.ts` - execute approved moves/renames
   - Create `/api/organizer/folders/route.ts` - manage watched folders

2. **Service Layer** (Priority 1)
   - Create `plugins/productivity/skills/organizer/service/organizer_service.py`
   - Implement folder scanning with content extraction
   - Implement AI classification for destination suggestions
   - Implement move/execute operations with rollback support

3. **MCP Wiring** (Priority 1)
   - Wire organizer tools to MCP for IDE integration
   - Enable `analyze_folder` and `execute_moves` via MCP

4. **Page Updates** (Priority 1)
   - Update `page.tsx` to show real folder analysis
   - Update `organize/page.tsx` for AI-powered suggestions
   - Remove mock data from all pages

5. **Wow Effect Demo** (Priority 1)
   - "Analyze Downloads" button shows AI suggestions
   - Each file shows: current name, suggested name, destination, reasoning
   - One-click batch apply with progress indicator

## User Context

The hub should analyze Downloads, Desktop, Documents, and Augur folders, then suggest moves based on file content. Example: A Perplexity export about "TAM and competition investigation" should be suggested to move to the venture/market-analysis folder.

## Constraints

- Use existing Augur patterns (GlassCard, DashboardWidget)
- Follow `src/config/paths.py` for path resolution
- No hardcoded paths
- Create tests for API routes

Begin with the API routes and service layer, then update the UI.
```

## Success Criteria

- [ ] All API routes functional and tested
- [ ] MCP tools wired and accessible
- [ ] "Analyze Downloads" produces real AI suggestions
- [ ] Batch operations execute successfully with rollback
- [ ] Score >= 80 on all dimensions
- [ ] Composite score >= 85/100

## References

- ADR-108: Hub Rebalancing (organizer placement)
- ADR-102: Adaptive Improvement Protocol
- `docs/references/design-standards.md` - GlassCard usage
- `src/config/paths.py` - Path configuration
