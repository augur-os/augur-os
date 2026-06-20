---
status: Implemented
date: '2026-02-18'
deciders: []
related: []
hub: null
tags:
- centralized
- editor
- settings
superseded_by: null
---

# ADR-114: Centralized Editor Settings

**Category**: UX / System
**Supersedes**: None

## Context

Augur manages thousands of files across many types — markdown (1,420), Python (7,472), TypeScript (1,777), YAML (385), JSON (3,300+), shell scripts, HTML, and more. When users want to open a file from the dashboard (e.g., daily logs, notes, configs), the system currently uses `open <file>` which delegates to macOS's default app handler. This works but:

1. **No per-type control**: A user might want markdown in iA Writer, YAML in VS Code, and Python in PyCharm — macOS only supports one default per extension.
2. **Scattered implementation**: The daily-logs/open route hardcodes `markdown_editor` preference lookup. Every new "open in editor" feature would need to duplicate this logic.
3. **No discovery**: Users can't see or configure editor preferences from the dashboard.

## Decision

Implement a centralized `file_editors` preference map in `config/system/preferences.yaml` with:

1. **Per-extension editor mapping** stored under `file_editors`:
   ```yaml
   file_editors:
     md: "iA Writer"
     yaml: "Visual Studio Code"
     py: "PyCharm"
     ts: "Cursor"
   ```
2. **Fallback chain**: extension-specific editor → system default (`open <file>`)
3. **Centralized resolution** via:
   - MCP: `system-open` tool gains optional `app` parameter
   - Dashboard API: new `/api/system/open-with` route that resolves editor from preferences
   - Shared utility: `resolveEditorForExtension(ext)` used by all routes
4. **Settings UI**: Editor preferences card in Settings > General, showing the top file types with editable app names
5. **Backward compatibility**: Existing `markdown_editor` key migrated to `file_editors.md`

## Top File Types (by count in codebase)

| Extension | Count | Default Use Case |
|-----------|-------|-----------------|
| `.py`     | 7,472 | Python automation scripts |
| `.md`     | 1,420 | Docs, ADRs, notes, memory logs |
| `.tsx`    | 1,060 | Dashboard React components |
| `.ts`     | 717   | TypeScript modules |
| `.yaml`   | 385   | Config, manifests, chains |
| `.json`   | 3,300 | Data files, package configs |
| `.sh`     | 23    | Shell scripts |
| `.html`   | 24    | Templates |

## Implementation

### Phase 1 (this ADR)
- Add `file_editors` map to `preferences.yaml`
- Create `/api/system/open-with` route with editor resolution
- Enhance `system-open` MCP tool with optional `app` parameter
- Add editor preferences UI to Settings > General
- Refactor daily-logs/open to use centralized resolution

### Phase 2 (future)
- "Open in Editor" buttons across all file-viewing pages
- App detection: scan `/Applications` for known editors
- Per-file override (right-click → "Open with...")

## Consequences

- **Positive**: Single place to configure editors, consistent behavior across all "open" actions, respects user sovereignty
- **Negative**: Slight complexity in preferences.yaml schema
- **Risk**: App name must match exactly what macOS expects (e.g., "Visual Studio Code" not "vscode")
