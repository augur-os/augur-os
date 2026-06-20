# ADR-766 v1 — Session-Ownership Registry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enforce at most one live process per CLI session id (per host) across the dashboard PTY and native-terminal handoff, via a file-backed ownership registry, eliminating MCP relay churn and concurrent-transcript corruption and making airplane switches preserve history.

**Architecture:** A single Python registry module under `src/mcp/augur_framework/tools/infrastructure/`, exposed as three MCP tools (`session-claim`, `session-release`, `session-status`). The native launcher (`src/scripts/agent_launch.py`) calls them via the `aug` generic MCP wrapper; the dashboard calls them via the MCP bridge. Liveness is host-scoped and PID-reuse-safe (PID alive + process start-time match). Conflicts are resolved non-destructively (refuse/redirect → "continue there" banner).

**Tech Stack:** Python (FastMCP tools, pydantic, psutil), TypeScript/Next.js (dashboard SessionManager + API routes + React banner), pytest, jest.

**Spec:** `docs/superpowers/specs/2026-05-20-adr-766-session-ownership-registry-design.md`
**ADR:** `docs/adrs/ADR-766-one-live-owner-per-session-model.md`

---

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `src/mcp/augur_framework/tools/infrastructure/session_owners.py` | Registry: load/save, liveness, claim/release/status impls + pydantic inputs | Create |
| `src/mcp/augur_framework/tools/infrastructure/__init__.py` | Register the 3 MCP tools | Modify |
| `tests/packages/augur-mcp/tools/test_session_owners.py` | Registry unit tests | Create |
| `config/system/capability_exposure.yaml` | Expose tools (cli + mcp) | Modify |
| `src/scripts/agent_launch.py` | Native-terminal claim after spawn + release on exit | Modify |
| `apps/dashboard/lib/session/SessionManager.ts` | Claim on initialize, release on exit/handoff | Modify |
| `apps/dashboard/app/api/cli/actions.ts` | Claim after `startCliProcess`; conflict → 409 redirect | Modify |
| `apps/dashboard/app/api/session/open-terminal/route.ts` | Conflict → redirect payload | Modify |
| `apps/dashboard/app/api/session/init/route.ts` | No direct change — prewarm conflict is recorded inside `SessionManager.initialize` (Task 5), not returned as a redirect (init is fire-and-forget) | — |
| `apps/dashboard/features/components/chat/ChatHeader.tsx` (or chat banner area) | "continue there" banner from redirect payload | Modify |
| `tests/dashboard/api/cli-route-session-owner.test.ts` | Dashboard conflict→redirect test | Create |

---

## Task 1: Registry core module (no MCP yet)

**Files:**
- Create: `src/mcp/augur_framework/tools/infrastructure/session_owners.py`
- Test: `tests/packages/augur-mcp/tools/test_session_owners.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/packages/augur-mcp/tools/test_session_owners.py
"""Session-ownership registry contract tests (ADR-766 v1)."""
import asyncio
import json

import pytest

import src.mcp.augur_framework.tools.infrastructure.session_owners as so
from src.mcp.augur_framework.tools.infrastructure.session_owners import (
    SessionClaimInput,
    SessionReleaseInput,
    SessionStatusInput,
    session_claim_impl,
    session_release_impl,
    session_status_impl,
)


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture
def reg(tmp_path, monkeypatch):
    path = tmp_path / "session-owners.json"
    monkeypatch.setattr(so, "_registry_path", lambda: path)
    monkeypatch.setattr(so, "_host_id", lambda: "host-A")
    # Deterministic liveness: pid 111 alive w/ start "S1", everything else dead.
    monkeypatch.setattr(so, "_pid_alive", lambda pid: pid == 111)
    monkeypatch.setattr(
        so, "_proc_start_time", lambda pid: "S1" if pid == 111 else None
    )
    return path


def test_claim_then_status_returns_owner(reg):
    res = _run(session_claim_impl(SessionClaimInput(
        session_id="sess1", surface="dashboard-pty", pid=111, cli_id="claude")))
    assert res["ok"] is True
    status = _run(session_status_impl(SessionStatusInput(session_id="sess1")))
    assert status["owner"]["pid"] == 111
    assert status["owner"]["surface"] == "dashboard-pty"


def test_cross_surface_live_owner_is_conflict(reg):
    _run(session_claim_impl(SessionClaimInput(
        session_id="sess1", surface="dashboard-pty", pid=111, cli_id="claude")))
    res = _run(session_claim_impl(SessionClaimInput(
        session_id="sess1", surface="native-terminal", pid=111, cli_id="claude")))
    assert res["ok"] is False
    assert res["conflict"]["surface"] == "dashboard-pty"
    assert res["conflict"]["pid"] == 111


def test_same_surface_reclaim_after_dead_pid(reg):
    # Owner recorded with a now-dead pid (222), same surface reclaims with live pid.
    so._atomic_save({"sess1": {"pid": 222, "surface": "dashboard-pty",
        "host": "host-A", "cli_id": "claude", "started_at": "t",
        "proc_start_time": "old", "last_seen": "t"}})
    res = _run(session_claim_impl(SessionClaimInput(
        session_id="sess1", surface="dashboard-pty", pid=111, cli_id="claude")))
    assert res["ok"] is True


def test_pid_reuse_detected_via_start_time(reg):
    # Entry's pid 111 is "alive" but its recorded start time differs -> stale.
    so._atomic_save({"sess1": {"pid": 111, "surface": "native-terminal",
        "host": "host-A", "cli_id": "claude", "started_at": "t",
        "proc_start_time": "OLD_DIFFERENT", "last_seen": "t"}})
    res = _run(session_claim_impl(SessionClaimInput(
        session_id="sess1", surface="dashboard-pty", pid=111, cli_id="claude")))
    assert res["ok"] is True  # prior entry stale (start-time mismatch) -> reclaimable


def test_other_host_entry_is_not_a_local_owner(reg):
    so._atomic_save({"sess1": {"pid": 111, "surface": "native-terminal",
        "host": "host-B", "cli_id": "claude", "started_at": "t",
        "proc_start_time": "S1", "last_seen": "t"}})
    res = _run(session_claim_impl(SessionClaimInput(
        session_id="sess1", surface="dashboard-pty", pid=111, cli_id="claude")))
    assert res["ok"] is True  # other-host owner ignored locally


def test_release_removes_owner(reg):
    _run(session_claim_impl(SessionClaimInput(
        session_id="sess1", surface="dashboard-pty", pid=111, cli_id="claude")))
    _run(session_release_impl(SessionReleaseInput(
        session_id="sess1", surface="dashboard-pty")))
    status = _run(session_status_impl(SessionStatusInput(session_id="sess1")))
    assert status["owner"] is None


def test_missing_registry_file_is_empty(reg):
    status = _run(session_status_impl(SessionStatusInput(session_id="nope")))
    assert status["owner"] is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/packages/augur-mcp/tools/test_session_owners.py -v`
Expected: FAIL — `ModuleNotFoundError: ... session_owners`.

- [ ] **Step 3: Write the registry module**

```python
# src/mcp/augur_framework/tools/infrastructure/session_owners.py
"""Session-ownership registry (ADR-766 v1).

One live process per CLI session id, per host, across the dashboard PTY and
native-terminal handoff. File-backed (ADR-270 runtime state, ADR-743 ledger
style), exposed as MCP tools. Liveness is host-scoped and PID-reuse-safe.
"""

from __future__ import annotations

import json
import os
import socket
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

_LOCK = threading.Lock()
_VALID_SURFACES = {"dashboard-pty", "native-terminal"}


class SessionClaimInput(BaseModel):
    session_id: str = Field(..., description="CLI session id being claimed")
    surface: str = Field(..., description="dashboard-pty | native-terminal")
    pid: int = Field(..., description="OS pid of the live CLI process")
    cli_id: str = Field(default="claude", description="claude | codex | gemini")
    model_config = ConfigDict(str_strip_whitespace=True, extra="allow")


class SessionReleaseInput(BaseModel):
    session_id: str = Field(..., description="CLI session id to release")
    surface: str = Field(..., description="surface releasing the claim")
    model_config = ConfigDict(str_strip_whitespace=True, extra="allow")


class SessionStatusInput(BaseModel):
    session_id: str | None = Field(default=None, description="Filter to one id")
    model_config = ConfigDict(str_strip_whitespace=True, extra="allow")


def _registry_path() -> Path:
    from src.config.paths import get_runtime_dir

    return get_runtime_dir() / "state" / "session-owners.json"


def _host_id() -> str:
    return socket.gethostname()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError, PermissionError):
        # PermissionError means the pid exists but is owned by another user.
        try:
            return isinstance(pid, int) and pid > 0 and _perm_means_alive()
        except Exception:
            return False
    except Exception:
        return False


def _perm_means_alive() -> bool:
    # os.kill raising PermissionError implies the process exists.
    return True


def _proc_start_time(pid: int) -> str | None:
    try:
        import psutil

        return str(psutil.Process(pid).create_time())
    except Exception:
        return None


def _is_live_local(entry: dict[str, Any]) -> bool:
    if entry.get("host") != _host_id():
        return False
    pid = entry.get("pid")
    if not isinstance(pid, int) or not _pid_alive(pid):
        return False
    recorded = entry.get("proc_start_time")
    if recorded is None:
        return True  # start time unavailable at claim time; PID-alive is best signal
    current = _proc_start_time(pid)
    if current is None:
        return True  # cannot read now; do not falsely reclaim a live pid
    return current == recorded


def _load() -> dict[str, Any]:
    path = _registry_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}  # never block a launch on a malformed registry


def _atomic_save(data: dict[str, Any]) -> None:
    path = _registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(tmp, path)


async def session_claim_impl(params: SessionClaimInput) -> str:
    if params.surface not in _VALID_SURFACES:
        return json.dumps({"ok": False, "error": f"bad surface {params.surface!r}"})
    with _LOCK:
        data = _load()
        existing = data.get(params.session_id)
        if existing and _is_live_local(existing) and existing.get("surface") != params.surface:
            return json.dumps({
                "ok": False,
                "conflict": {
                    "surface": existing.get("surface"),
                    "pid": existing.get("pid"),
                    "host": existing.get("host"),
                },
            })
        data[params.session_id] = {
            "pid": params.pid,
            "surface": params.surface,
            "host": _host_id(),
            "cli_id": params.cli_id,
            "started_at": _now(),
            "proc_start_time": _proc_start_time(params.pid),
            "last_seen": _now(),
        }
        _atomic_save(data)
    return json.dumps({"ok": True, "session_id": params.session_id})


async def session_release_impl(params: SessionReleaseInput) -> str:
    with _LOCK:
        data = _load()
        entry = data.get(params.session_id)
        if entry and entry.get("surface") == params.surface:
            del data[params.session_id]
            _atomic_save(data)
    return json.dumps({"ok": True})


async def session_status_impl(params: SessionStatusInput) -> str:
    with _LOCK:
        data = _load()
        changed = False
        # Reclaim stale entries (dead/foreign-pid) opportunistically.
        for sid in list(data.keys()):
            entry = data[sid]
            if entry.get("host") == _host_id() and not _is_live_local(entry):
                del data[sid]
                changed = True
        if changed:
            _atomic_save(data)
        if params.session_id is not None:
            entry = data.get(params.session_id)
            return json.dumps({"owner": entry if entry else None})
        return json.dumps({"owners": data})


__all__ = [
    "SessionClaimInput",
    "SessionReleaseInput",
    "SessionStatusInput",
    "session_claim_impl",
    "session_release_impl",
    "session_status_impl",
]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/packages/augur-mcp/tools/test_session_owners.py -v`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add src/mcp/augur_framework/tools/infrastructure/session_owners.py tests/packages/augur-mcp/tools/test_session_owners.py
git commit -m "feat(session-owners): file-backed ownership registry core (ADR-766)"
```

---

## Task 2: Expose registry as MCP tools

**Files:**
- Modify: `src/mcp/augur_framework/tools/infrastructure/__init__.py` (imports block ~line 88-106; registration after the airplane tools ~line 251)

- [ ] **Step 1: Add impls to the infrastructure import block**

In `__init__.py`, find the `from .local_backends import (` block (ends ~line 106) and add a sibling import immediately after it:

```python
    from .session_owners import (
        SessionClaimInput,
        SessionReleaseInput,
        SessionStatusInput,
        session_claim_impl,
        session_release_impl,
        session_status_impl,
    )
```

- [ ] **Step 2: Register the three tools**

After the `toggle_airplane_mode` registration block (immediately after its function body, ~line 251), insert:

```python
    @mcp.tool(
        name="session-claim",
        annotations=tool_annotations(
            {
                "title": "Claim Session Ownership",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def session_claim(
        session_id: str, surface: str, pid: int, cli_id: str = "claude"
    ) -> str:
        """Claim one-live-owner of a CLI session id (ADR-766). Returns {ok} or
        {ok:false, conflict:{surface,pid,host}} if another live local surface owns it."""
        return await session_claim_impl(
            SessionClaimInput(session_id=session_id, surface=surface, pid=pid, cli_id=cli_id)
        )

    @mcp.tool(
        name="session-release",
        annotations=tool_annotations(
            {
                "title": "Release Session Ownership",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def session_release(session_id: str, surface: str) -> str:
        """Release this surface's claim on a session id (ADR-766)."""
        return await session_release_impl(
            SessionReleaseInput(session_id=session_id, surface=surface)
        )

    @mcp.tool(
        name="session-status",
        annotations=tool_annotations(
            {
                "title": "Session Ownership Status",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def session_status(session_id: str | None = None) -> str:
        """Return the live owner of a session id, or all owners (ADR-766).
        Reclaims stale (dead-pid / start-time-mismatch) entries as a side effect."""
        return await session_status_impl(SessionStatusInput(session_id=session_id))
```

- [ ] **Step 3: Verify the tools load and are CLI-reachable (real-data check)**

Run: `./scripts/aug session-status --pretty`
Expected: JSON `{"owners": {...}}` (likely `{}`) — proves the tool registered and the `aug` generic wrapper reaches it. Then:
Run: `./scripts/aug session-claim --session-id smoke --surface dashboard-pty --pid $$ --pretty`
Expected: `{"ok": true, "session_id": "smoke"}`. Then `./scripts/aug session-release --session-id smoke --surface dashboard-pty` → `{"ok": true}`.

- [ ] **Step 4: Commit**

```bash
git add src/mcp/augur_framework/tools/infrastructure/__init__.py
git commit -m "feat(session-owners): register session-claim/release/status MCP tools (ADR-766)"
```

---

## Task 3: Capability exposure

**Files:**
- Modify: `config/system/capability_exposure.yaml`

- [ ] **Step 1: Add exposure entries**

Add three entries mirroring the existing infra-tool format (owner `platform-admin`, exported to both `cli` for the launcher and `mcp` for the dashboard). Match the YAML shape already used in the file:

```yaml
  mcp-tool:session-claim:
    type: mcp-tool
    owner: platform-admin
    preferred_surface: cli
    export_to: [cli, mcp]
  mcp-tool:session-release:
    type: mcp-tool
    owner: platform-admin
    preferred_surface: cli
    export_to: [cli, mcp]
  mcp-tool:session-status:
    type: mcp-tool
    owner: platform-admin
    preferred_surface: cli
    export_to: [cli, mcp]
```

(Read the file first and copy the exact key/field shape of a nearby `mcp-tool:` entry — field names must match the file's schema.)

- [ ] **Step 2: Verify capability parity**

Run: `./scripts/aug get-config --pretty 2>/dev/null | head -1` is not the check; instead run the repo's capability/agent-config parity check if present, otherwise re-run `./scripts/aug session-status` to confirm nothing broke.
Expected: no schema/parity error.

- [ ] **Step 3: Commit**

```bash
git add config/system/capability_exposure.yaml
git commit -m "chore(capability): expose session-claim/release/status (cli+mcp) (ADR-766)"
```

---

## Task 4: Native-terminal claim/release in agent_launch.py

**Files:**
- Modify: `src/scripts/agent_launch.py`

> Read `src/scripts/agent_launch.py` first to find (a) where the CLI subprocess is spawned and its PID/handle obtained, and (b) the resolved `--resume`/`--session-id`. Wire claim *after* spawn and release in a `finally`.

- [ ] **Step 1: Add a helper that calls the registry via the in-process impls**

`agent_launch.py` runs in the repo Python env, so call the impls directly (no subprocess to `aug`). Add near the top-level helpers:

```python
def _session_claim(session_id, pid, cli_id):
    import asyncio
    from src.mcp.augur_framework.tools.infrastructure.session_owners import (
        SessionClaimInput, session_claim_impl,
    )
    try:
        return asyncio.run(session_claim_impl(SessionClaimInput(
            session_id=session_id, surface="native-terminal", pid=pid, cli_id=cli_id)))
    except Exception:
        return None  # never block a launch on registry failure


def _session_release(session_id):
    import asyncio
    from src.mcp.augur_framework.tools.infrastructure.session_owners import (
        SessionReleaseInput, session_release_impl,
    )
    try:
        asyncio.run(session_release_impl(SessionReleaseInput(
            session_id=session_id, surface="native-terminal")))
    except Exception:
        pass
```

- [ ] **Step 2: Claim after spawn, release in finally**

At the spawn site (where the child CLI process object/PID exists and the session id is known), wrap the wait:

```python
    # ADR-766: register native-terminal ownership of this session id.
    if session_id:
        _session_claim(session_id, child.pid, cli_id)
    try:
        returncode = child.wait()
    finally:
        if session_id:
            _session_release(session_id)
```

(Adapt `child`, `cli_id`, `session_id` to the actual variable names in the file. If the launcher `exec`s/replaces the process rather than waiting, switch to a fork-and-wait or register before `exec` with the to-be PID and rely on liveness reclaim for release.)

- [ ] **Step 3: Smoke test the launcher path (real-data check)**

Run: `./scripts/aug session-status --pretty` before and after starting a short native session; confirm an entry with `surface: native-terminal` appears while it runs and is gone after exit. (If a full launch is impractical in CI, assert `_session_claim`/`_session_release` write/remove the entry in a unit test using the tmp-path registry fixture.)

- [ ] **Step 4: Commit**

```bash
git add src/scripts/agent_launch.py
git commit -m "feat(launcher): native terminal claims/releases session ownership (ADR-766)"
```

---

## Task 5: Dashboard claim/release in SessionManager

**Files:**
- Modify: `apps/dashboard/lib/session/SessionManager.ts` (`initialize` success path ~line 612-626; `clearRuntimeState` ~line 503-511; `exitForTerminalHandoff`)

> The dashboard reaches the registry through the MCP bridge. `airplane-routing.ts` already shows the pattern: `callMCPTool(tool, args, {})` + `MCPBridge.extractText`. Add a thin helper in a new `apps/dashboard/lib/session/sessionOwners.ts`.

- [ ] **Step 1: Add the dashboard registry helper**

```typescript
// apps/dashboard/lib/session/sessionOwners.ts
import { callMCPTool, MCPBridge } from "@/lib/mcp/MCPBridge";

type ClaimResult =
  | { ok: true }
  | { ok: false; conflict?: { surface: string; pid: number; host: string } };

async function call<T>(tool: string, args: Record<string, unknown>): Promise<T | null> {
  const res = await callMCPTool(tool, args, {});
  if (res.isError) return null;
  const raw = MCPBridge.extractText(res).trim();
  return raw ? (JSON.parse(raw) as T) : null;
}

export async function claimSession(
  sessionId: string, pid: number, cliId: string,
): Promise<ClaimResult> {
  const r = await call<ClaimResult>("session-claim", {
    session_id: sessionId, surface: "dashboard-pty", pid, cli_id: cliId,
  });
  return r ?? { ok: true }; // registry failure must not block the launch
}

export async function releaseSession(sessionId: string): Promise<void> {
  await call("session-release", { session_id: sessionId, surface: "dashboard-pty" });
}
```

- [ ] **Step 2: Release on exit/cleanup**

In `SessionManager.ts`, capture the session id before clearing and release. In the `this.proc.onExit(...)` callback inside `initialize` (~line 623) and in `exitForTerminalHandoff` (after the PTY exits), call:

```typescript
        const releasedId = this.lastSessionId;
        if (releasedId) void releaseSession(releasedId);
```

Add `import { claimSession, releaseSession } from "./sessionOwners";` at the top.

- [ ] **Step 3: Claim after a successful dashboard spawn**

In `initialize`, right after `processes.set(cliId, entry);` (~line 621) and once `this.lastSessionId` reflects the spawned session id, claim:

```typescript
      if (this.lastSessionId && this.proc?.pid) {
        const claim = await claimSession(this.lastSessionId, this.proc.pid, cliId);
        if (!claim.ok) {
          // Conflict: another surface owns this session. Surface via the session
          // file so the UI can show the "continue there" banner; do not kill.
          writeChatSession({
            isActive: true, status: "running",
            context: { cliId, sessionConflict: claim.conflict ?? null },
          });
        }
      }
```

(`initialize` is the prewarm path; the user-facing refuse/redirect for explicit Start lives in Task 6 on the `/api/cli` route. Here we only record the conflict, never kill.)

- [ ] **Step 4: Verify dashboard build compiles**

Run: `/dev-build` (rule 29) OR `cd apps/dashboard && npx tsc --noEmit`
Expected: no type errors.

- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/lib/session/sessionOwners.ts apps/dashboard/lib/session/SessionManager.ts
git commit -m "feat(dashboard): SessionManager claims/releases session ownership (ADR-766)"
```

---

## Task 6: Conflict → redirect from start/handoff routes + banner

**Files:**
- Modify: `apps/dashboard/app/api/cli/actions.ts` (`startCliProcess` / start handler — claim after spawn)
- Modify: `apps/dashboard/app/api/session/open-terminal/route.ts`
- Modify: `apps/dashboard/features/components/chat/ChatHeader.tsx` (banner)
- Test: `tests/dashboard/api/cli-route-session-owner.test.ts`

- [ ] **Step 1: Write the failing route test**

```typescript
// tests/dashboard/api/cli-route-session-owner.test.ts
import { handleStartConflict } from "@/app/api/cli/session-conflict";

describe("session-owner conflict → redirect", () => {
  it("maps a claim conflict to a 409 redirect payload", () => {
    const res = handleStartConflict({ surface: "native-terminal", pid: 42, host: "h" });
    expect(res.status).toBe(409);
    expect(res.body.code).toBe("SESSION_OWNED_ELSEWHERE");
    expect(res.body.conflict.surface).toBe("native-terminal");
  });
});
```

- [ ] **Step 2: Run it — expect FAIL** (`Cannot find module session-conflict`).
Run: `cd apps/dashboard && npx jest ../../tests/dashboard/api/cli-route-session-owner.test.ts`

- [ ] **Step 3: Add the conflict helper**

```typescript
// apps/dashboard/app/api/cli/session-conflict.ts
export interface SessionConflict { surface: string; pid: number; host: string; }
export function handleStartConflict(conflict: SessionConflict) {
  const where = conflict.surface === "native-terminal" ? "a native terminal" : "the dashboard";
  return {
    status: 409 as const,
    body: {
      code: "SESSION_OWNED_ELSEWHERE" as const,
      error: `This conversation is live in ${where} (pid ${conflict.pid}). Continue there.`,
      conflict,
    },
  };
}
```

- [ ] **Step 4: Wire it into the start path**

In `actions.ts`, after `startCliProcess` returns `{pid,...}` and ownership is claimed (call `session-claim` via the MCP bridge as in Task 5), if the claim returns `{ok:false, conflict}`: terminate the just-spawned duplicate PTY for that cliId (it must not coexist), then return `NextResponse.json(body, {status})` from `handleStartConflict(conflict)`. Mirror the same claim+conflict handling in `open-terminal/route.ts` before launching the native terminal.

```typescript
import { handleStartConflict } from "./session-conflict";
// after spawn + claim:
if (claim && claim.ok === false && claim.conflict) {
  processes.get(cliId)?.ptyProcess.kill(); // remove the duplicate we just made
  processes.delete(cliId);
  const { status, body } = handleStartConflict(claim.conflict);
  return NextResponse.json(body, { status });
}
```

(Killing the *duplicate we just spawned in this same call* is allowed — it is not a pre-existing user session. The pre-existing owner is never touched.)

- [ ] **Step 5: Run route test — expect PASS.**

- [ ] **Step 6: Add the "continue there" banner**

In `ChatHeader.tsx`, read the conflict from the session status / start response (the chip already polls `/api/cli`; extend the start-response handling in `useCliChat` to set a `sessionConflict` state). Render a non-blocking amber banner when present:

```tsx
{sessionConflict && (
  <div role="status" className="px-3 py-2 text-xs bg-amber-500/10 text-amber-500 border-b border-amber-500/30">
    This conversation is live in {sessionConflict.surface === "native-terminal" ? "a native terminal" : "the dashboard"} (pid {sessionConflict.pid}). Continue there.
  </div>
)}
```

- [ ] **Step 7: Verify build + run airplane/chip tests (no regression)**

Run: `cd apps/dashboard && npx jest ../../tests/dashboard/components/ChatHeader-airplane-chip.test.tsx ../../tests/dashboard/api/cli-route-airplane.test.ts ../../tests/dashboard/api/cli-route-session-owner.test.ts`
Expected: all PASS.

- [ ] **Step 8: Commit**

```bash
git add apps/dashboard/app/api/cli/session-conflict.ts apps/dashboard/app/api/cli/actions.ts apps/dashboard/app/api/session/open-terminal/route.ts apps/dashboard/features/components/chat/ChatHeader.tsx apps/dashboard/features/hooks/useCliChat.ts tests/dashboard/api/cli-route-session-owner.test.ts
git commit -m "feat(dashboard): refuse/redirect on session conflict + continue-there banner (ADR-766)"
```

---

## Task 7: Integration simulation + closeout

**Files:** none new (validation only)

- [ ] **Step 1: Two-claim simulation (real registry, no agents)**

Run:
```bash
./scripts/aug session-claim --session-id simX --surface dashboard-pty --pid $$ --pretty
./scripts/aug session-claim --session-id simX --surface native-terminal --pid $$ --pretty
```
Expected: first `{"ok": true}`; second `{"ok": false, "conflict": {"surface": "dashboard-pty", ...}}` (same pid `$$` is alive, so the first claim is a live local owner). Then release: `./scripts/aug session-release --session-id simX --surface dashboard-pty`.

- [ ] **Step 2: Run the full registry + dashboard test set**

Run: `uv run pytest tests/packages/augur-mcp/tools/test_session_owners.py -v`
Run: `cd apps/dashboard && npx jest ../../tests/dashboard/api/cli-route-session-owner.test.ts ../../tests/dashboard/api/cli-route-airplane.test.ts ../../tests/dashboard/components/ChatHeader-airplane-chip.test.tsx`
Expected: all PASS.

- [ ] **Step 3: ADR-766 status + manual verification note**

Set ADR-766 `status: Implemented` (front-matter) once Tasks 1-6 are merged, and append a short "v1 shipped; take-over deferred" note. Do NOT drive the live dashboard chat with browser automation to verify (it spawns real autonomous agents — see session memory); rely on the scripted sim + tests, and a manual human check that toggling airplane mid-conversation preserves history and shows the banner when the session is owned by a terminal.

- [ ] **Step 4: Commit**

```bash
git add docs/adrs/ADR-766-one-live-owner-per-session-model.md docs/adrs/adrs-index.json
git commit -m "docs(adr): mark ADR-766 v1 Implemented (registry + refuse/redirect)"
```

---

## Self-Review notes (for the implementer)

- **PID-reuse safety** relies on `proc_start_time`; if `psutil` is missing it degrades to PID-alive only — acceptable, logged. Do not hard-fail.
- **Never kill a pre-existing owner.** The only `kill` in this plan is the *duplicate PTY this same call just spawned* (Task 6 Step 4) — verify the kill targets exactly that and nothing else.
- **Registry-failure must never block a launch** — every dashboard/launcher call swallows registry errors and proceeds (single-owner is best-effort hardening, not a gate).
- **agent_launch.py spawn shape** must be confirmed by reading the file; the claim/release wrapper assumes a wait()-able child. If it `exec`s, adjust per Task 4 Step 2 note.
