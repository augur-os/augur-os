# Augur Harness Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Implements**: ADR-552 - Brain Harness Control Plane

**Goal:** Build `/brain/harness`, a Brain hub control plane that shows Augur's harness map, starter diagnostics, provenance, and safe action triggers.

**Architecture:** A Python MCP infrastructure module assembles a generated snapshot from decentralized sources and stores it in Augur runtime/cache state. The dashboard page reads that snapshot via MCP hooks, runs safe direct triggers with MCP calls, and routes repair work through IDE-dispatched actions.

**Tech Stack:** Python 3.11, MCP FastMCP, `src.config.paths`, `src.lib.frontmatter_utils`, Next.js 15, React, TypeScript, Tailwind, Jest, React Testing Library.

---

## File Structure

- Create `src/mcp/augur_mcp/infrastructure/harness.py`
  - Owns snapshot types, source scanners, diagnostic classification, read/write helpers, and MCP tool registration.
- Modify `src/mcp/augur_mcp/infrastructure/__init__.py`
  - Registers Brain Harness MCP tools with the existing infrastructure registry.
- Create `src/mcp/augur_mcp/tests/test_harness.py`
  - Tests snapshot assembly, diagnostic output, persistence, and MCP response helpers.
- Create `apps/dashboard/features/pages/brain/harness/page.tsx`
  - Brain hub control-plane page.
- Create `tests/dashboard/features/pages/brain/harness-page.test.tsx`
  - Tests loading, empty, stale, diagnostics, safe trigger, and IDE repair states.
- Modify `skills/knowledge/SKILL.md`
  - Adds `/brain/harness` to decentralized Brain hub page metadata and MCP tool declarations.

## Task 1: Snapshot Assembly Contract

**Files:**
- Create: `src/mcp/augur_mcp/infrastructure/harness.py`
- Create: `src/mcp/augur_mcp/tests/test_harness.py`

- [ ] **Step 1: Write failing tests for snapshot assembly**

Create `src/mcp/augur_mcp/tests/test_harness.py` with:

```python
from __future__ import annotations

import json
from pathlib import Path

from augur_mcp.infrastructure.harness import (
    CAPABILITY_TYPES,
    build_harness_snapshot,
    read_harness_snapshot_file,
    write_harness_snapshot_file,
)


def write_skill(root: Path, name: str, body: str) -> Path:
    skill_dir = root / "skills" / name
    skill_dir.mkdir(parents=True)
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(body, encoding="utf-8")
    return skill_md


def test_capability_type_contract_is_small_and_explicit() -> None:
    assert CAPABILITY_TYPES == {
        "memory",
        "skill",
        "mcp_tool",
        "dashboard_page",
        "command",
        "protocol",
        "loop",
        "document_surface",
    }


def test_build_snapshot_maps_skill_tools_pages_and_relationships(tmp_path: Path) -> None:
    write_skill(
        tmp_path,
        "knowledge",
        """---
name: knowledge
description: Search and curate Augur memory.
x-augur-hub: brain
x-augur-mcp-tools:
  - memory-stats
x-augur-dashboard-pages:
  - /brain/knowledge
x-augur-commands:
  - id: memory-curate
    type: workflow
    visibility: core
    description: Curate memory
---
# Knowledge
""",
    )
    tool_file = tmp_path / "src" / "mcp" / "tools.py"
    tool_file.parent.mkdir(parents=True)
    tool_file.write_text('@mcp.tool(name="memory-stats")\\ndef tool():\\n    pass\\n', encoding="utf-8")

    snapshot = build_harness_snapshot(tmp_path, generated_at="2026-04-19T10:00:00Z")

    assert snapshot["generated_at"] == "2026-04-19T10:00:00Z"
    capability_ids = {item["id"] for item in snapshot["capabilities"]}
    assert "skill:knowledge" in capability_ids
    assert "mcp_tool:memory-stats" in capability_ids
    assert "dashboard_page:/brain/knowledge" in capability_ids
    assert "command:knowledge:memory-curate" in capability_ids
    assert {
        "from_id": "skill:knowledge",
        "to_id": "mcp_tool:memory-stats",
        "kind": "skill_declares_tool",
        "source_path": "skills/knowledge/SKILL.md",
        "confidence": "high",
    } in snapshot["relationships"]


def test_missing_declared_mcp_tool_emits_wiring_diagnostic(tmp_path: Path) -> None:
    write_skill(
        tmp_path,
        "ai",
        """---
name: ai
description: AI integration layer.
x-augur-hub: brain
x-augur-mcp-tools:
  - missing-tool
---
# AI
""",
    )

    snapshot = build_harness_snapshot(tmp_path, generated_at="2026-04-19T10:00:00Z")

    diagnostics = snapshot["diagnostics"]
    assert diagnostics == [
        {
            "id": "diagnostic:missing-mcp-tool:missing-tool",
            "severity": "warning",
            "family": "dashboard_mcp_wiring",
            "reason": "Skill declares MCP tool 'missing-tool' but no @mcp.tool registration was found.",
            "affected_capability_ids": ["mcp_tool:missing-tool"],
            "source_path": "skills/ai/SKILL.md",
            "recommended_action": {
                "kind": "dispatch_ide_repair",
                "label": "Ask IDE agent to repair missing MCP tool wiring",
            },
        }
    ]


def test_snapshot_persistence_round_trips_json(tmp_path: Path) -> None:
    snapshot = build_harness_snapshot(tmp_path, generated_at="2026-04-19T10:00:00Z")
    snapshot_path = tmp_path / "harness" / "brain-harness-snapshot.json"

    write_harness_snapshot_file(snapshot_path, snapshot)

    assert json.loads(snapshot_path.read_text(encoding="utf-8"))["generated_at"] == "2026-04-19T10:00:00Z"
    assert read_harness_snapshot_file(snapshot_path)["capabilities"] == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest src/mcp/augur_mcp/tests/test_harness.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'augur_mcp.infrastructure.harness'`.

- [ ] **Step 3: Implement minimal snapshot assembler**

Create `src/mcp/augur_mcp/infrastructure/harness.py` with:

```python
"""Brain Harness snapshot assembly and MCP tools.

The snapshot is generated runtime/cache state. Canonical facts remain in
decentralized sources such as SKILL.md frontmatter, MCP registrations, page
discovery, docs, and runtime scanner outputs.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from augur_mcp.annotations import tool_annotations
from src.config.paths import get_cache_dir, get_project_root
from src.lib.frontmatter_utils import parse_frontmatter

CAPABILITY_TYPES = {
    "memory",
    "skill",
    "mcp_tool",
    "dashboard_page",
    "command",
    "protocol",
    "loop",
    "document_surface",
}

SNAPSHOT_VERSION = "1.0"
SNAPSHOT_FILENAME = "brain-harness-snapshot.json"
TOOL_NAME_RE = re.compile(r"""@mcp\\.tool\\(\\s*name\\s*=\\s*"'["']""")


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _iter_skill_files(project_root: Path) -> list[Path]:
    skills_dir = project_root / "skills"
    if not skills_dir.is_dir():
        return []
    return sorted(skills_dir.glob("*/SKILL.md"))


def _scan_mcp_tool_registrations(project_root: Path) -> dict[str, str]:
    registrations: dict[str, str] = {}
    for search_dir in (project_root / "src" / "mcp", project_root / "skills"):
        if not search_dir.is_dir():
            continue
        for py_file in sorted(search_dir.rglob("*.py")):
            try:
                content = py_file.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for match in TOOL_NAME_RE.finditer(content):
                registrations.setdefault(match.group(1), _rel(py_file, project_root))
    return registrations


def _capability(
    *,
    capability_id: str,
    capability_type: str,
    label: str,
    source_path: str,
    hub: str | None = None,
    owner_skill: str | None = None,
    summary: str = "",
    status: str = "mapped",
    tags: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": capability_id,
        "type": capability_type,
        "label": label,
        "hub": hub,
        "owner_skill": owner_skill,
        "source_path": source_path,
        "summary": summary,
        "tags": tags or [],
        "status": status,
    }


def _relationship(
    *,
    from_id: str,
    to_id: str,
    kind: str,
    source_path: str,
    confidence: str = "high",
) -> dict[str, str]:
    return {
        "from_id": from_id,
        "to_id": to_id,
        "kind": kind,
        "source_path": source_path,
        "confidence": confidence,
    }


def _missing_tool_diagnostic(tool_name: str, source_path: str) -> dict[str, Any]:
    return {
        "id": f"diagnostic:missing-mcp-tool:{tool_name}",
        "severity": "warning",
        "family": "dashboard_mcp_wiring",
        "reason": f"Skill declares MCP tool '{tool_name}' but no @mcp.tool registration was found.",
        "affected_capability_ids": [f"mcp_tool:{tool_name}"],
        "source_path": source_path,
        "recommended_action": {
            "kind": "dispatch_ide_repair",
            "label": "Ask IDE agent to repair missing MCP tool wiring",
        },
    }


def build_harness_snapshot(project_root: Path | None = None, *, generated_at: str | None = None) -> dict[str, Any]:
    root = (project_root or get_project_root()).resolve()
    generated = generated_at or _utc_now()
    tool_registrations = _scan_mcp_tool_registrations(root)
    capabilities: list[dict[str, Any]] = []
    relationships: list[dict[str, str]] = []
    diagnostics: list[dict[str, Any]] = []

    for skill_md in _iter_skill_files(root):
        source_path = _rel(skill_md, root)
        frontmatter, _body = parse_frontmatter(skill_md)
        skill_name = str(frontmatter.get("name") or skill_md.parent.name)
        hub = frontmatter.get("x-augur-hub")
        hub = hub if isinstance(hub, str) and hub else None
        description = frontmatter.get("description")
        summary = description if isinstance(description, str) else ""
        skill_id = f"skill:{skill_name}"

        capabilities.append(
            _capability(
                capability_id=skill_id,
                capability_type="skill",
                label=skill_name,
                hub=hub,
                owner_skill=skill_name,
                source_path=source_path,
                summary=summary,
            )
        )

        for tool_name in frontmatter.get("x-augur-mcp-tools") or []:
            if not isinstance(tool_name, str) or not tool_name:
                continue
            tool_id = f"mcp_tool:{tool_name}"
            capabilities.append(
                _capability(
                    capability_id=tool_id,
                    capability_type="mcp_tool",
                    label=tool_name,
                    hub=hub,
                    owner_skill=skill_name,
                    source_path=tool_registrations.get(tool_name, source_path),
                    status="registered" if tool_name in tool_registrations else "declared_missing_registration",
                )
            )
            relationships.append(
                _relationship(
                    from_id=skill_id,
                    to_id=tool_id,
                    kind="skill_declares_tool",
                    source_path=source_path,
                )
            )
            if tool_name not in tool_registrations:
                diagnostics.append(_missing_tool_diagnostic(tool_name, source_path))

        for page_path in frontmatter.get("x-augur-dashboard-pages") or []:
            if not isinstance(page_path, str) or not page_path:
                continue
            page_id = f"dashboard_page:{page_path}"
            capabilities.append(
                _capability(
                    capability_id=page_id,
                    capability_type="dashboard_page",
                    label=page_path,
                    hub=hub,
                    owner_skill=skill_name,
                    source_path=source_path,
                )
            )
            relationships.append(
                _relationship(
                    from_id=skill_id,
                    to_id=page_id,
                    kind="skill_owns_page",
                    source_path=source_path,
                )
            )

        for command in frontmatter.get("x-augur-commands") or []:
            if not isinstance(command, dict) or not command.get("id"):
                continue
            command_id = f"command:{skill_name}:{command['id']}"
            capabilities.append(
                _capability(
                    capability_id=command_id,
                    capability_type="command",
                    label=str(command["id"]),
                    hub=hub,
                    owner_skill=skill_name,
                    source_path=source_path,
                    summary=str(command.get("description") or ""),
                )
            )
            relationships.append(
                _relationship(
                    from_id=skill_id,
                    to_id=command_id,
                    kind="skill_declares_command",
                    source_path=source_path,
                )
            )

    return {
        "version": SNAPSHOT_VERSION,
        "generated_at": generated,
        "capabilities": capabilities,
        "relationships": relationships,
        "diagnostics": diagnostics,
        "actions": [
            {"kind": "refresh_snapshot", "label": "Refresh snapshot", "direct": True},
            {"kind": "dispatch_ide_repair", "label": "Ask IDE agent to repair", "direct": False},
        ],
        "provenance": {
            "project_root": str(root),
            "source_counts": {
                "skills": len(_iter_skill_files(root)),
                "mcp_tool_registrations": len(tool_registrations),
            },
            "partial_failures": [],
        },
    }


def harness_snapshot_path(cache_dir: Path | None = None) -> Path:
    return (cache_dir or get_cache_dir()) / "harness" / SNAPSHOT_FILENAME


def write_harness_snapshot_file(path: Path, snapshot: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\\n", encoding="utf-8")


def read_harness_snapshot_file(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
```

- [ ] **Step 4: Run tests to verify Task 1 passes**

Run:

```bash
pytest src/mcp/augur_mcp/tests/test_harness.py -v
```

Expected: all 4 tests PASS.

- [ ] **Step 5: Commit Task 1**

```bash
git add src/mcp/augur_mcp/infrastructure/harness.py src/mcp/augur_mcp/tests/test_harness.py
git commit -m "feat: add brain harness snapshot assembly"
```

## Task 2: MCP Tools for Snapshot Read and Refresh

**Files:**
- Modify: `src/mcp/augur_mcp/infrastructure/harness.py`
- Modify: `src/mcp/augur_mcp/infrastructure/__init__.py`
- Modify: `src/mcp/augur_mcp/tests/test_harness.py`

- [ ] **Step 1: Add failing tests for snapshot response helpers**

Append to `src/mcp/augur_mcp/tests/test_harness.py`:

```python
from augur_mcp.infrastructure.harness import (
    get_brain_harness_snapshot_impl,
    refresh_brain_harness_snapshot_impl,
)


def test_get_snapshot_impl_returns_empty_state_when_missing(tmp_path: Path) -> None:
    result = get_brain_harness_snapshot_impl(snapshot_path=tmp_path / "missing.json")

    assert result["success"] is True
    assert result["snapshot"] is None
    assert result["state"] == "missing"
    assert result["actions"][0]["kind"] == "refresh_snapshot"


def test_refresh_snapshot_impl_writes_and_returns_snapshot(tmp_path: Path) -> None:
    write_skill(
        tmp_path,
        "knowledge",
        """---
name: knowledge
description: Search and curate Augur memory.
x-augur-hub: brain
---
# Knowledge
""",
    )
    snapshot_path = tmp_path / "cache" / "harness" / "brain-harness-snapshot.json"

    result = refresh_brain_harness_snapshot_impl(project_root=tmp_path, snapshot_path=snapshot_path)

    assert result["success"] is True
    assert result["state"] == "ready"
    assert snapshot_path.exists()
    assert result["snapshot"]["capabilities"][0]["id"] == "skill:knowledge"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest src/mcp/augur_mcp/tests/test_harness.py -v
```

Expected: FAIL because `get_brain_harness_snapshot_impl` and `refresh_brain_harness_snapshot_impl` are missing.

- [ ] **Step 3: Add response helpers and MCP registration**

Append to `src/mcp/augur_mcp/infrastructure/harness.py`:

```python
def _safe_actions() -> list[dict[str, Any]]:
    return [
        {"kind": "refresh_snapshot", "label": "Refresh snapshot", "direct": True},
        {"kind": "reindex_knowledge", "label": "Rebuild memory index", "direct": True, "mcp_tool": "memory-rebuild-index"},
        {"kind": "reindex_browse", "label": "Reindex Browse category", "direct": True, "mcp_tool": "reindex-browse-category"},
        {"kind": "dispatch_ide_repair", "label": "Ask IDE agent to repair", "direct": False},
    ]


def get_brain_harness_snapshot_impl(*, snapshot_path: Path | None = None) -> dict[str, Any]:
    path = snapshot_path or harness_snapshot_path()
    if not path.exists():
        return {
            "success": True,
            "state": "missing",
            "snapshot": None,
            "actions": _safe_actions(),
        }
    return {
        "success": True,
        "state": "ready",
        "snapshot": read_harness_snapshot_file(path),
        "actions": _safe_actions(),
    }


def refresh_brain_harness_snapshot_impl(
    *,
    project_root: Path | None = None,
    snapshot_path: Path | None = None,
) -> dict[str, Any]:
    snapshot = build_harness_snapshot(project_root)
    path = snapshot_path or harness_snapshot_path()
    write_harness_snapshot_file(path, snapshot)
    return {
        "success": True,
        "state": "ready",
        "snapshot": snapshot,
        "actions": _safe_actions(),
    }


def register_harness_tools(mcp, mcp_tool_interceptor, metrics) -> None:
    @mcp.tool(
        name="get-brain-harness-snapshot",
        annotations=tool_annotations(
            {
                "title": "Get Brain Harness Snapshot",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def get_brain_harness_snapshot() -> str:
        return json.dumps(get_brain_harness_snapshot_impl())

    @mcp.tool(
        name="refresh-brain-harness-snapshot",
        annotations=tool_annotations(
            {
                "title": "Refresh Brain Harness Snapshot",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def refresh_brain_harness_snapshot() -> str:
        return json.dumps(refresh_brain_harness_snapshot_impl())
```

Modify `src/mcp/augur_mcp/infrastructure/__init__.py`:

```python
    from .harness import register_harness_tools
```

Add this call after `register_browse_tools(...)`:

```python
    # Register Brain Harness control-plane tools (ADR-552)
    register_harness_tools(mcp, mcp_tool_interceptor, metrics)
```

- [ ] **Step 4: Run Python tests**

Run:

```bash
pytest src/mcp/augur_mcp/tests/test_harness.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit Task 2**

```bash
git add src/mcp/augur_mcp/infrastructure/harness.py src/mcp/augur_mcp/infrastructure/__init__.py src/mcp/augur_mcp/tests/test_harness.py
git commit -m "feat: expose brain harness MCP tools"
```

## Task 3: Dashboard Page Rendering and Action Wiring

**Files:**
- Create: `apps/dashboard/features/pages/brain/harness/page.tsx`
- Create: `tests/dashboard/features/pages/brain/harness-page.test.tsx`

- [ ] **Step 1: Write failing dashboard tests**

Create `tests/dashboard/features/pages/brain/harness-page.test.tsx`:

```tsx
/**
 * @jest-environment jsdom
 */
import "@testing-library/jest-dom";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mockUseMcpQuery = jest.fn();
const mockMcpCall = jest.fn();
const mockRunAction = jest.fn();

jest.mock("@/lib/mcp/useMcpQuery", () => ({
  useMcpQuery: (...args: unknown[]) => mockUseMcpQuery(...args),
}));

jest.mock("@/lib/mcp/client", () => ({
  mcpCall: (...args: unknown[]) => mockMcpCall(...args),
}));

jest.mock("@/hooks/useActionRunner", () => ({
  useActionRunner: () => ({
    runAction: mockRunAction,
    isExecuting: false,
  }),
}));

const readyPayload = {
  success: true,
  state: "ready",
  snapshot: {
    generated_at: "2026-04-19T10:00:00Z",
    capabilities: [
      {
        id: "skill:knowledge",
        type: "skill",
        label: "knowledge",
        hub: "brain",
        owner_skill: "knowledge",
        source_path: "skills/knowledge/SKILL.md",
        summary: "Search and curate Augur memory.",
        tags: [],
        status: "mapped",
      },
    ],
    relationships: [],
    diagnostics: [
      {
        id: "diagnostic:missing-mcp-tool:missing-tool",
        severity: "warning",
        family: "dashboard_mcp_wiring",
        reason: "Skill declares MCP tool 'missing-tool' but no @mcp.tool registration was found.",
        affected_capability_ids: ["mcp_tool:missing-tool"],
        source_path: "skills/ai/SKILL.md",
        recommended_action: {
          kind: "dispatch_ide_repair",
          label: "Ask IDE agent to repair missing MCP tool wiring",
        },
      },
    ],
    actions: [],
    provenance: {
      source_counts: { skills: 1, mcp_tool_registrations: 0 },
      partial_failures: [],
    },
  },
  actions: [
    { kind: "refresh_snapshot", label: "Refresh snapshot", direct: true },
    { kind: "dispatch_ide_repair", label: "Ask IDE agent to repair", direct: false },
  ],
};

describe("BrainHarnessPage", () => {
  beforeEach(() => {
    mockUseMcpQuery.mockReset();
    mockMcpCall.mockReset();
    mockRunAction.mockReset();
  });

  it("renders readiness, capabilities, diagnostics, and provenance", async () => {
    mockUseMcpQuery.mockReturnValue({ data: readyPayload, loading: false, error: null, refetch: jest.fn() });
    const Page = (await import("@/features/pages/brain/harness/page")).default;

    render(<Page />);

    expect(screen.getByText("Harness readiness")).toBeInTheDocument();
    expect(screen.getByText("1 mapped")).toBeInTheDocument();
    expect(screen.getByText("knowledge")).toBeInTheDocument();
    expect(screen.getByText(/missing-tool/)).toBeInTheDocument();
    expect(screen.getByText("skills/knowledge/SKILL.md")).toBeInTheDocument();
  });

  it("shows generate action when no snapshot exists", async () => {
    mockUseMcpQuery.mockReturnValue({
      data: { success: true, state: "missing", snapshot: null, actions: [{ kind: "refresh_snapshot", label: "Refresh snapshot", direct: true }] },
      loading: false,
      error: null,
      refetch: jest.fn(),
    });
    const Page = (await import("@/features/pages/brain/harness/page")).default;

    render(<Page />);

    expect(screen.getByText("Harness snapshot has not been generated yet.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Generate snapshot" })).toBeInTheDocument();
  });

  it("refreshes snapshot through MCP instead of an IDE action", async () => {
    const refetch = jest.fn();
    mockUseMcpQuery.mockReturnValue({ data: readyPayload, loading: false, error: null, refetch });
    mockMcpCall.mockResolvedValue({ success: true });
    const Page = (await import("@/features/pages/brain/harness/page")).default;
    const user = userEvent.setup();

    render(<Page />);
    await user.click(screen.getByRole("button", { name: "Refresh snapshot" }));

    await waitFor(() => expect(mockMcpCall).toHaveBeenCalledWith("refresh-brain-harness-snapshot", {}));
    expect(mockRunAction).not.toHaveBeenCalled();
    expect(refetch).toHaveBeenCalled();
  });

  it("dispatches repair work through IDE action runner", async () => {
    mockUseMcpQuery.mockReturnValue({ data: readyPayload, loading: false, error: null, refetch: jest.fn() });
    const Page = (await import("@/features/pages/brain/harness/page")).default;
    const user = userEvent.setup();

    render(<Page />);
    await user.click(screen.getByRole("button", { name: "Ask IDE agent to repair" }));

    expect(mockRunAction).toHaveBeenCalledWith(
      expect.objectContaining({
        id: "brain-harness-repair",
        dispatch: "ide",
      }),
    );
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd apps/dashboard && pnpm test -- harness-page.test.tsx --runInBand
```

Expected: FAIL because `@/features/pages/brain/harness/page` does not exist.

- [ ] **Step 3: Implement the Brain Harness page**

Create `apps/dashboard/features/pages/brain/harness/page.tsx`:

```tsx
"use client";

import { useMemo } from "react";
import { Activity, AlertTriangle, Brain, FileText, RefreshCw, Wrench } from "lucide-react";
import { useActionRunner } from "@/hooks/useActionRunner";
import { mcpCall } from "@/lib/mcp/client";
import { useMcpQuery } from "@/lib/mcp/useMcpQuery";

type Capability = {
  id: string;
  type: string;
  label: string;
  hub: string | null;
  owner_skill: string | null;
  source_path: string;
  summary: string;
  tags: string[];
  status: string;
};

type Diagnostic = {
  id: string;
  severity: "info" | "warning" | "error";
  family: string;
  reason: string;
  affected_capability_ids: string[];
  source_path: string;
  recommended_action: { kind: string; label: string };
};

type HarnessSnapshot = {
  generated_at: string;
  capabilities: Capability[];
  relationships: unknown[];
  diagnostics: Diagnostic[];
  provenance: {
    source_counts?: Record<string, number>;
    partial_failures?: unknown[];
  };
};

type HarnessResponse = {
  success: boolean;
  state: "missing" | "ready";
  snapshot: HarnessSnapshot | null;
  actions: { kind: string; label: string; direct: boolean }[];
};

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
      <div className="text-2xl font-semibold text-[var(--text-primary)]">{value}</div>
      <div className="mt-1 text-xs uppercase text-[var(--text-muted)]">{label}</div>
    </div>
  );
}

export default function BrainHarnessPage() {
  const { runAction, isExecuting } = useActionRunner();
  const { data, loading, error, refetch } = useMcpQuery<HarnessResponse>(
    ["brain-harness-snapshot"],
    "get-brain-harness-snapshot",
    "config",
  );

  const snapshot = data?.snapshot ?? null;
  const grouped = useMemo(() => {
    const groups: Record<string, Capability[]> = {};
    for (const capability of snapshot?.capabilities ?? []) {
      groups[capability.type] = [...(groups[capability.type] ?? []), capability];
    }
    return groups;
  }, [snapshot]);

  const refreshSnapshot = async () => {
    await mcpCall("refresh-brain-harness-snapshot", {});
    await refetch?.();
  };

  const dispatchRepair = () => {
    runAction({
      id: "brain-harness-repair",
      label: "Ask IDE agent to repair",
      description: "Repair Brain Harness diagnostics using the current snapshot.",
      icon: "Wrench",
      dispatch: "ide",
      prompt: [
        "Use ADR-552 and /brain/harness diagnostics to repair the selected Augur harness issue.",
        "Do not edit dashboard files directly from the browser.",
        "Preserve plugin decentralization and verify with tests before reporting success.",
      ].join("\\n"),
    });
  };

  if (loading) {
    return <div className="p-6 text-sm text-[var(--text-muted)]">Loading Brain Harness...</div>;
  }

  if (error) {
    return <div className="p-6 text-sm text-[var(--accent-danger)]">Brain Harness snapshot could not be loaded.</div>;
  }

  if (!snapshot) {
    return (
      <div className="space-y-4 p-6">
        <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-5">
          <div className="flex items-center gap-3">
            <Brain className="h-5 w-5 text-[var(--text-secondary)]" aria-hidden="true" />
            <div>
              <h2 className="text-base font-semibold text-[var(--text-primary)]">Harness snapshot has not been generated yet.</h2>
              <p className="mt-1 text-sm text-[var(--text-muted)]">Generate the first snapshot to map Augur's second-brain harness.</p>
            </div>
          </div>
          <button className="mt-4 inline-flex items-center gap-2 rounded-md border px-3 py-2 text-sm" onClick={refreshSnapshot}>
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
            Generate snapshot
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6">
      <section>
        <div className="mb-3 flex items-center gap-2">
          <Activity className="h-5 w-5 text-[var(--text-secondary)]" aria-hidden="true" />
          <h2 className="text-base font-semibold text-[var(--text-primary)]">Harness readiness</h2>
        </div>
        <div className="grid gap-3 md:grid-cols-4">
          <StatCard label="Capabilities" value={`${snapshot.capabilities.length} mapped`} />
          <StatCard label="Diagnostics" value={`${snapshot.diagnostics.length}`} />
          <StatCard label="Skills" value={`${snapshot.provenance.source_counts?.skills ?? 0}`} />
          <StatCard label="Generated" value={snapshot.generated_at.slice(0, 10)} />
        </div>
      </section>

      <section className="grid gap-4 lg:grid-cols-[1.3fr_0.7fr]">
        <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
          <h3 className="mb-3 text-sm font-semibold text-[var(--text-primary)]">Capability map</h3>
          <div className="space-y-4">
            {Object.entries(grouped).map(([type, items]) => (
              <div key={type}>
                <div className="mb-2 text-xs uppercase text-[var(--text-muted)]">{type}</div>
                <div className="grid gap-2">
                  {items.map((item) => (
                    <div key={item.id} className="rounded-md border border-[var(--border-color)] p-3">
                      <div className="font-medium text-[var(--text-primary)]">{item.label}</div>
                      <div className="mt-1 text-xs text-[var(--text-muted)]">{item.source_path}</div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
          <h3 className="mb-3 text-sm font-semibold text-[var(--text-primary)]">Trigger panel</h3>
          <div className="space-y-2">
            <button className="inline-flex w-full items-center gap-2 rounded-md border px-3 py-2 text-sm" onClick={refreshSnapshot}>
              <RefreshCw className="h-4 w-4" aria-hidden="true" />
              Refresh snapshot
            </button>
            <button className="inline-flex w-full items-center gap-2 rounded-md border px-3 py-2 text-sm" onClick={dispatchRepair} disabled={isExecuting}>
              <Wrench className="h-4 w-4" aria-hidden="true" />
              Ask IDE agent to repair
            </button>
          </div>
        </div>
      </section>

      <section className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
        <div className="mb-3 flex items-center gap-2">
          <AlertTriangle className="h-5 w-5 text-[var(--accent-warning)]" aria-hidden="true" />
          <h3 className="text-sm font-semibold text-[var(--text-primary)]">Diagnostics</h3>
        </div>
        <div className="space-y-2">
          {snapshot.diagnostics.map((diagnostic) => (
            <div key={diagnostic.id} className="rounded-md border border-[var(--border-color)] p-3">
              <div className="text-sm text-[var(--text-primary)]">{diagnostic.reason}</div>
              <div className="mt-1 text-xs text-[var(--text-muted)]">{diagnostic.source_path}</div>
            </div>
          ))}
        </div>
      </section>

      <section className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
        <div className="mb-2 flex items-center gap-2">
          <FileText className="h-4 w-4 text-[var(--text-secondary)]" aria-hidden="true" />
          <h3 className="text-sm font-semibold text-[var(--text-primary)]">Provenance</h3>
        </div>
        <pre className="overflow-auto text-xs text-[var(--text-muted)]">
          {JSON.stringify(snapshot.provenance, null, 2)}
        </pre>
      </section>
    </div>
  );
}
```

- [ ] **Step 4: Run dashboard page tests**

Run:

```bash
cd apps/dashboard && pnpm test -- harness-page.test.tsx --runInBand
```

Expected: all 4 tests PASS.

- [ ] **Step 5: Commit Task 3**

```bash
git add apps/dashboard/features/pages/brain/harness/page.tsx tests/dashboard/features/pages/brain/harness-page.test.tsx
git commit -m "feat: add brain harness dashboard page"
```

## Task 4: Brain Hub Metadata and Mount Verification

**Files:**
- Modify: `skills/knowledge/SKILL.md`

- [ ] **Step 1: Add failing metadata expectation**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
from src.lib.frontmatter_utils import parse_frontmatter
fm, _ = parse_frontmatter(Path("skills/knowledge/SKILL.md"))
assert "/brain/harness" in fm["x-augur-dashboard-pages"]
pages = fm["x-augur-config"]["contributions"]["pages"]
assert any(page["id"] == "harness" and page["title"] == "Harness" for page in pages)
assert "get-brain-harness-snapshot" in fm["x-augur-mcp-tools"]
assert "refresh-brain-harness-snapshot" in fm["x-augur-mcp-tools"]
PY
```

Expected: FAIL because the new page and MCP tools are not declared yet.

- [ ] **Step 2: Update `skills/knowledge/SKILL.md` frontmatter**

Edit the frontmatter only:

```yaml
x-augur-mcp-tools:
  - get-brain-harness-snapshot
  - refresh-brain-harness-snapshot
```

Add `/brain/harness` under `x-augur-dashboard-pages`.

Add this page entry under `x-augur-config.contributions.pages`:

```yaml
    - id: harness
      title: Harness
      icon: Activity
      order: 30
      purpose: Inspect the second-brain harness map, diagnostics, provenance, and safe repair routing.
      keywords:
        - harness
        - control-plane
        - diagnostics
        - provenance
        - second-brain
```

- [ ] **Step 3: Re-run metadata expectation**

Run the same Python assertion from Step 1.

Expected: PASS.

- [ ] **Step 4: Run mount generation**

Run:

```bash
cd apps/dashboard && pnpm run mount-plugins
```

Expected: command succeeds and reports no orphan page issues.

- [ ] **Step 5: Commit Task 4**

```bash
git add skills/knowledge/SKILL.md apps/dashboard/app/brain/[[...slug]]/registry.ts apps/dashboard/lib/tabs/generated-registry.ts
git commit -m "feat: register brain harness page"
```

## Task 5: Integration Verification

**Files:**
- Verify only unless failures require fixes.

- [ ] **Step 1: Run focused Python tests**

Run:

```bash
pytest src/mcp/augur_mcp/tests/test_harness.py -v
```

Expected: PASS.

- [ ] **Step 2: Run focused dashboard tests**

Run:

```bash
cd apps/dashboard && pnpm test -- harness-page.test.tsx --runInBand
```

Expected: PASS.

- [ ] **Step 3: Run dashboard build through approved lifecycle**

Run the project-approved build command:

```bash
/dev-build
```

Expected: build completes successfully. Use `/dev-build` rather than direct `npm run build` so the dashboard lifecycle gate remains authoritative.

- [ ] **Step 4: Browser verify `/brain/harness`**

Use the dashboard lifecycle gate to ensure the dev server is running, verify the process cwd/branch serving the dashboard, then open `/brain/harness` in Chrome.

Expected visual checks:

- page loads on the `codex/harness-layer-design` checkout
- readiness summary shows nonzero capability data
- capability map shows at least the `knowledge` and `ai` skills
- diagnostics section renders real data or an honest empty state
- Refresh snapshot calls `refresh-brain-harness-snapshot`
- Ask IDE agent to repair opens an IDE-dispatched action path

- [ ] **Step 5: Confirm no uncommitted verification drift**

Run:

```bash
git status --short
```

Expected: no output. If this command shows modified files, return to the task that owns those files, add a focused failing test for the defect, fix it there, rerun that task's verification command, and commit with that task's file list.

## Task 6: Completion Notes

**Files:**
- Modify: `~/Projects/Au-docs/adrs/ADR-552-brain-harness-control-plane.md`

- [ ] **Step 1: Update ADR status after implementation passes**

Use `write_frontmatter()` from `src.lib.frontmatter_utils` to change ADR-552 frontmatter:

```yaml
status: Implemented
```

Only do this after Task 5 browser verification passes.

- [ ] **Step 2: Summarize final evidence**

Final implementation handoff must include:

- commits created
- tests run
- browser verification URL and checkout/branch verified
- any residual diagnostics intentionally left for later
- confirmation that dashboard repair actions dispatch IDE work rather than editing files directly
