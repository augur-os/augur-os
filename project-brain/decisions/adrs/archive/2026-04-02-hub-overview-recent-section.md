# Hub Overview Recent Section Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Recent" section to each hub's overview page showing the latest notes and documents across all skills in the hub.

**Architecture:** New Python MCP tool (`list-hub-recent-files`) aggregates vault files across all skills belonging to a hub, sorted by modification time with per-skill capping. New `RecentSection` React component in `HubOverviewPage.tsx` consumes this tool via `useMcpQuery`.

**Tech Stack:** Python (MCP tool), TypeScript/React (dashboard component), `useMcpQuery` hook, `discover_all_skills()` for hub-to-skill resolution.

---

### Task 1: MCP Tool — `list_hub_recent_files_impl`

**Files:**
- Create: `src/mcp/augur_mcp/core/hub_recent.py`
- Test: `tests/mcp/test_hub_recent.py`

This task implements the Python function that scans vault directories for all skills in a hub and returns a sorted, per-skill-capped list of recent files.

- [ ] **Step 1: Write the failing test**

Create `tests/mcp/test_hub_recent.py`:

```python
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest


@pytest.mark.asyncio
async def test_list_hub_recent_files_returns_sorted_files(tmp_path: Path):
    """Files are returned sorted by modification time, newest first."""
    from augur_mcp.core.hub_recent import list_hub_recent_files_impl

    # Create mock vault with two skills
    career_dir = tmp_path / "career"
    career_dir.mkdir()
    coach_dir = tmp_path / "coach"
    coach_dir.mkdir()

    # Create files with different mtimes
    old_file = career_dir / "old-note.md"
    old_file.write_text("---\ntitle: Old\n---\nOld content here")
    import os
    os.utime(old_file, (1000000, 1000000))

    new_file = coach_dir / "new-note.md"
    new_file.write_text("---\ntitle: New\n---\nNew content here")
    os.utime(new_file, (2000000, 2000000))

    mid_file = career_dir / "mid-doc.md"
    mid_file.write_text("Mid content no frontmatter")
    os.utime(mid_file, (1500000, 1500000))

    result = json.loads(
        await list_hub_recent_files_impl(
            hub_id="career",
            skill_names=["career", "coach"],
            vault_dir=tmp_path,
            limit=10,
            per_skill_limit=2,
        )
    )

    assert result["success"] is True
    assert result["count"] == 3
    names = [f["name"] for f in result["files"]]
    assert names == ["new-note.md", "mid-doc.md", "old-note.md"]
    assert result["files"][0]["skill"] == "coach"
    assert result["files"][1]["skill"] == "career"


@pytest.mark.asyncio
async def test_per_skill_limit_caps_items(tmp_path: Path):
    """No more than per_skill_limit files from any single skill."""
    from augur_mcp.core.hub_recent import list_hub_recent_files_impl

    import os

    skill_dir = tmp_path / "career"
    skill_dir.mkdir()
    for i in range(5):
        f = skill_dir / f"note-{i}.md"
        f.write_text(f"Content {i}")
        os.utime(f, (1000000 + i * 1000, 1000000 + i * 1000))

    result = json.loads(
        await list_hub_recent_files_impl(
            hub_id="career",
            skill_names=["career"],
            vault_dir=tmp_path,
            limit=10,
            per_skill_limit=2,
        )
    )

    assert result["count"] == 2
    # Should be the 2 newest
    assert result["files"][0]["name"] == "note-4.md"
    assert result["files"][1]["name"] == "note-3.md"


@pytest.mark.asyncio
async def test_empty_vault_returns_empty(tmp_path: Path):
    """Hub with no vault files returns empty list."""
    from augur_mcp.core.hub_recent import list_hub_recent_files_impl

    result = json.loads(
        await list_hub_recent_files_impl(
            hub_id="career",
            skill_names=["nonexistent"],
            vault_dir=tmp_path,
            limit=10,
            per_skill_limit=2,
        )
    )

    assert result["success"] is True
    assert result["count"] == 0
    assert result["files"] == []


@pytest.mark.asyncio
async def test_file_type_classification(tmp_path: Path):
    """Markdown files are 'note', other files are 'doc'."""
    from augur_mcp.core.hub_recent import list_hub_recent_files_impl

    skill_dir = tmp_path / "career"
    skill_dir.mkdir()
    (skill_dir / "my-note.md").write_text("# Note")
    (skill_dir / "report.pdf").write_text("fake pdf")
    (skill_dir / "data.csv").write_text("a,b,c")

    result = json.loads(
        await list_hub_recent_files_impl(
            hub_id="career",
            skill_names=["career"],
            vault_dir=tmp_path,
            limit=10,
            per_skill_limit=5,
        )
    )

    types_by_name = {f["name"]: f["type"] for f in result["files"]}
    assert types_by_name["my-note.md"] == "note"
    assert types_by_name["report.pdf"] == "doc"
    assert types_by_name["data.csv"] == "doc"


@pytest.mark.asyncio
async def test_preview_strips_frontmatter(tmp_path: Path):
    """Preview text should not include YAML frontmatter."""
    from augur_mcp.core.hub_recent import list_hub_recent_files_impl

    skill_dir = tmp_path / "career"
    skill_dir.mkdir()
    (skill_dir / "note.md").write_text("---\ntitle: Test\n---\nActual body content here")

    result = json.loads(
        await list_hub_recent_files_impl(
            hub_id="career",
            skill_names=["career"],
            vault_dir=tmp_path,
            limit=10,
            per_skill_limit=2,
        )
    )

    assert result["files"][0]["preview"] == "Actual body content here"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Projects/Augur && python -m pytest tests/mcp/test_hub_recent.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'augur_mcp.core.hub_recent'`

- [ ] **Step 3: Implement `list_hub_recent_files_impl`**

Create `src/mcp/augur_mcp/core/hub_recent.py`:

```python
"""List recent files across all skills in a hub."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


async def list_hub_recent_files_impl(
    hub_id: str,
    skill_names: list[str],
    vault_dir: Path,
    limit: int = 10,
    per_skill_limit: int = 2,
) -> str:
    """List recent vault files across all skills belonging to a hub.

    Scans vault directories for each skill, collects files, sorts by
    modification time, and caps per-skill to prevent domination.

    Args:
        hub_id: Hub identifier (e.g., "career").
        skill_names: List of skill names belonging to this hub.
        vault_dir: Root vault directory.
        limit: Maximum total files to return.
        per_skill_limit: Maximum files per skill.

    Returns:
        JSON string with {success, files, count}.
    """
    all_files: list[dict] = []

    for skill_name in skill_names:
        skill_vault = vault_dir / skill_name
        if not skill_vault.is_dir():
            continue

        skill_files: list[dict] = []
        # Collect files up to 2 levels deep
        seen: set[Path] = set()
        for pattern in ("*", "*/*", "*/*/*"):
            for p in skill_vault.glob(pattern):
                if not p.is_file() or p in seen:
                    continue
                # Skip hidden files and directories
                if any(part.startswith(".") for part in p.relative_to(skill_vault).parts):
                    continue
                seen.add(p)

                stat = p.stat()
                is_markdown = p.suffix.lower() in (".md", ".markdown")
                file_type = "note" if is_markdown else "doc"

                # Build preview for markdown files
                preview = ""
                if is_markdown:
                    try:
                        content = p.read_text(encoding="utf-8", errors="replace")
                        body = content
                        if content.startswith("---"):
                            end = content.find("\n---", 4)
                            if end != -1:
                                body = content[end + 4 :].lstrip("\n")
                        preview = body[:200].strip()
                    except OSError:
                        pass

                skill_files.append(
                    {
                        "name": p.name,
                        "path": str(p.relative_to(vault_dir)),
                        "type": file_type,
                        "skill": skill_name,
                        "modified": datetime.fromtimestamp(
                            stat.st_mtime, tz=timezone.utc
                        ).isoformat(),
                        "preview": preview,
                        "_mtime": stat.st_mtime,
                    }
                )

        # Sort skill files by mtime descending, cap per skill
        skill_files.sort(key=lambda f: f["_mtime"], reverse=True)
        all_files.extend(skill_files[:per_skill_limit])

    # Sort all collected files by mtime descending, cap total
    all_files.sort(key=lambda f: f["_mtime"], reverse=True)
    result_files = all_files[:limit]

    # Remove internal _mtime key before returning
    for f in result_files:
        del f["_mtime"]

    return json.dumps(
        {"success": True, "files": result_files, "count": len(result_files)}
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Projects/Augur && python -m pytest tests/mcp/test_hub_recent.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/mcp/augur_mcp/core/hub_recent.py tests/mcp/test_hub_recent.py
git commit -m "feat: add list_hub_recent_files_impl for cross-skill vault file listing"
```

---

### Task 2: Register MCP Tool

**Files:**
- Modify: `src/mcp/augur_mcp/core/__init__.py` (after `list-skill-vault-notes` registration, around line 356)
- Modify: `src/mcp/augur_mcp/client_surface.py` (add to dashboard tool list, around line 52)

This task wires the implementation into the MCP server so the dashboard can call it.

- [ ] **Step 1: Add tool registration in `__init__.py`**

In `src/mcp/augur_mcp/core/__init__.py`, after the `list-skill-vault-notes` block (after line 356), add:

```python
    @mcp.tool(
        name="list-hub-recent-files",
        annotations=tool_annotations(
            {
                "title": "List Hub Recent Files",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    async def list_hub_recent_files(
        hub_id: str = "",
        hubId: str = "",
        limit: int = 10,
        per_skill_limit: int = 2,
    ) -> str:
        """List recent vault files across all skills in a hub."""
        from augur_mcp.config import get_skill_data_dir
        from augur_mcp.core.hub_recent import list_hub_recent_files_impl
        from src.plugins.skill_discovery import discover_all_skills

        resolved_hub = hub_id or hubId
        if not resolved_hub:
            return json.dumps({"success": True, "files": [], "count": 0})

        # Find all skills belonging to this hub
        try:
            all_skills = discover_all_skills(tiers=(0,))
            skill_names = [s.name for s in all_skills if s.hub == resolved_hub]
        except Exception:
            skill_names = []

        if not skill_names:
            return json.dumps({"success": True, "files": [], "count": 0})

        # Get vault root from the first skill's data dir parent
        vault_dir = get_skill_data_dir(skill_names[0]).parent

        return await list_hub_recent_files_impl(
            hub_id=resolved_hub,
            skill_names=skill_names,
            vault_dir=vault_dir,
            limit=limit,
            per_skill_limit=per_skill_limit,
        )

    if mcp_tool_interceptor:
        list_hub_recent_files = mcp_tool_interceptor(list_hub_recent_files)
```

You will also need to add `import json` at the top of the function or confirm it's already imported at module level. Check the existing imports at the top of `__init__.py`.

- [ ] **Step 2: Add to dashboard client surface**

In `src/mcp/augur_mcp/client_surface.py`, add `"list-hub-recent-files"` to the dashboard tools list, after the existing `"list-skill-vault-notes"` entry (around line 52):

```python
        "list-skill-vault-notes",
        "list-hub-recent-files",
```

- [ ] **Step 3: Verify MCP server starts without errors**

Run: `cd ~/Projects/Augur && python -c "from augur_mcp.core import register_core_tools; print('OK')"`
Expected: `OK` (no import errors)

- [ ] **Step 4: Commit**

```bash
git add src/mcp/augur_mcp/core/__init__.py src/mcp/augur_mcp/client_surface.py
git commit -m "feat: register list-hub-recent-files MCP tool for dashboard"
```

---

### Task 3: RecentSection Component

**Files:**
- Modify: `apps/dashboard/components/plugin/HubOverviewPage.tsx`

This task adds the `RecentSection` component and integrates it into the hub overview render order.

- [ ] **Step 1: Add `RecentFile` type**

In `apps/dashboard/components/plugin/HubOverviewPage.tsx`, after the existing `VaultNote` interface (after line 53), add:

```typescript
interface RecentFile {
  name: string;
  path: string;
  type: 'note' | 'doc';
  skill: string;
  modified: string;
  preview?: string;
}
```

- [ ] **Step 2: Add the `RecentSection` component**

After the `QuickNotesSection` component (after line 211), add the new component. Import `Clock` from lucide-react by adding it to the existing import on line 6:

Update line 6 from:
```typescript
import { ChevronDown, ChevronRight, FileText, Loader2, Plus, Search } from 'lucide-react';
```
to:
```typescript
import { ChevronDown, ChevronRight, Clock, FileText, Loader2, Plus, Search } from 'lucide-react';
```

Then add the component after `QuickNotesSection`:

```typescript
// ── Recent Section ─────────────────────────────────────────────────────

function RecentSection({ hubId }: { hubId: string }) {
  const { data: files, loading, error } = useMcpQuery<RecentFile[]>(
    ['hub-recent-files', hubId],
    'list-hub-recent-files',
    'user-data',
    {
      args: { hub_id: hubId, limit: 10, per_skill_limit: 2 },
      select: (raw) => {
        const d = unwrap(raw);
        if (d && typeof d === 'object' && !Array.isArray(d) && 'files' in d) {
          return (d as Record<string, unknown>).files as RecentFile[];
        }
        return Array.isArray(d) ? d : [];
      },
    },
  );

  const recentFiles = useMemo(() => (Array.isArray(files) ? files : []), [files]);

  if (!loading && recentFiles.length === 0 && !error) return null;

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <SectionHeader title="Recent" count={recentFiles.length} />
        {recentFiles.length > 0 && (
          <a
            href={`/browse?hub=${hubId}`}
            className="text-xs text-[var(--text-muted)] hover:text-[var(--text-secondary)] transition-colors"
          >
            View all →
          </a>
        )}
      </div>

      {/* Loading */}
      {loading && (
        <div className="space-y-2">
          {Array.from({ length: 3 }, (_, i) => (
            <div key={i} className="h-12 rounded-lg bg-[var(--bg-hover)]/50 animate-pulse" />
          ))}
        </div>
      )}

      {/* Error */}
      {!loading && error && (
        <div className="rounded-xl bg-red-500/5 border border-red-500/20 p-4 text-center">
          <p className="text-sm text-red-400">Failed to load recent files</p>
        </div>
      )}

      {/* File list */}
      {!loading && recentFiles.length > 0 && (
        <div className="rounded-xl border border-[var(--border-color)]/30 overflow-hidden">
          {recentFiles.map((file, i) => {
            const isNote = file.type === 'note';
            return (
              <div
                key={`${file.skill}-${file.name}`}
                className={`flex items-center gap-3 px-4 py-2.5 ${
                  i > 0 ? 'border-t border-[var(--border-color)]/20' : ''
                } hover:bg-[var(--bg-hover)]/30 transition-colors`}
              >
                <div
                  className={`w-7 h-7 rounded-md flex items-center justify-center flex-shrink-0 ${
                    isNote ? 'bg-purple-500/10' : 'bg-blue-500/10'
                  }`}
                >
                  {isNote ? (
                    <FileText className="w-3.5 h-3.5 text-purple-400" />
                  ) : (
                    <Clock className="w-3.5 h-3.5 text-blue-400" />
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-[13px] font-medium text-[var(--text-primary)] truncate">
                    {stripMdExtension(file.name)}
                  </p>
                  <p className="text-[11px] text-[var(--text-muted)]">
                    {file.type} · {file.skill}
                  </p>
                </div>
                <span className="text-[11px] text-[var(--text-muted)] flex-shrink-0">
                  {formatTimeAgo(file.modified)}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Add `RecentSection` to the render tree**

In the `HubOverviewPage` component's return JSX (around line 268), add `<RecentSection>` between the Tools section and the Notes section. Find this block:

```tsx
      {/* Vault Notes */}
      <QuickNotesSection hubId={hubId} skillId={primarySkillId} />
```

Add before it:

```tsx
      {/* Recent files across hub */}
      <RecentSection hubId={hubId} />
```

The final render order in the JSX should be:
1. Hub header
2. Apps section
3. Tools section
4. **RecentSection** (new)
5. QuickNotesSection
6. UserBlocksSection

- [ ] **Step 4: Verify build compiles**

Run: `cd ~/Projects/Augur && pnpm --filter dashboard exec tsc --noEmit --pretty 2>&1 | head -20`
Expected: No errors related to `HubOverviewPage.tsx`

- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/components/plugin/HubOverviewPage.tsx
git commit -m "feat: add RecentSection to hub overview pages"
```

---

### Task 4: Browser Verification

**Files:** None (verification only)

This task verifies the feature works end-to-end in the browser per CLAUDE.md rule 24.

- [ ] **Step 1: Restart MCP server**

The Python MCP tool was added, so the MCP server needs a restart. Use the dashboard lifecycle gate:

Run: `cd ~/Projects/Augur && python -m src.scripts.dashboard_lifecycle request-action restart-mcp`

Wait 8 seconds for the server to reinitialize.

- [ ] **Step 2: Verify MCP tool returns data**

Test the tool via the API to confirm wiring works before checking the browser:

Run: `cd ~/Projects/Augur && curl -s -X POST http://localhost:3000/api/mcp/tool -H 'Content-Type: application/json' -d '{"tool":"list-hub-recent-files","args":{"hub_id":"career","limit":5}}' | python3 -m json.tool | head -30`

Expected: JSON with `"success": true` and a `"files"` array (may be empty if the career vault has no files, but the structure should be correct).

- [ ] **Step 3: Open hub overview in Chrome**

Navigate to a hub that has vault data (e.g., `http://localhost:3000/career` or `http://localhost:3000/brain`). Wait 6+ seconds for data to load.

Verify:
- The "Recent" section appears between Tools and Notes
- Items show: name, type badge (note/doc), skill name, relative time
- The section is hidden on hubs with no vault data
- "View all →" link points to `/browse?hub={hubId}`

- [ ] **Step 4: Check a second hub**

Navigate to a different hub (e.g., `http://localhost:3000/life`). Verify:
- If the hub has vault data: Recent section shows items
- If the hub has no vault data: Recent section is not rendered (no empty state, just absent)

- [ ] **Step 5: Commit verification note**

No code to commit. Mark this task complete once browser verification passes.
