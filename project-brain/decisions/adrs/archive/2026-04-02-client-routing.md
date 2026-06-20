# Client Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add per-action AI client routing with a unified ClientResolver, per-action overrides in preferences, Browse page dropdown, `/local config` CLI, autoloop `--local` flag, and airplane mode integration.

**Architecture:** A single `ClientResolver` Python module resolves which AI client handles each action by walking a priority chain: airplane mode > `--local` flag > per-action override > global default > implicit. Three new MCP tools expose this to the dashboard and CLI. The dashboard's `useActionRunner` calls `resolve-client` before dispatch. Autoloops get a `--local` CLI flag that sets `ctx.client` on `OpsContext`.

**Tech Stack:** Python (MCP tools, ClientResolver, OpsContext), TypeScript/React (useActionRunner, BrowseDetailActions), YAML (preferences schema)

---

### Task 1: ClientResolver Module + Tests

**Files:**
- Create: `src/mcp/augur_mcp/infrastructure/client_resolver.py`
- Create: `tests/mcp/infrastructure/test_client_resolver.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/mcp/infrastructure/test_client_resolver.py
"""Tests for ClientResolver — per-action AI client routing."""
import pytest
from unittest.mock import patch
from augur_mcp.infrastructure.client_resolver import ClientResolver, ResolvedClient


@pytest.fixture
def resolver():
    return ClientResolver()


def _prefs(
    *,
    airplane_enabled=False,
    default_client=None,
    overrides=None,
    integrations=None,
):
    """Build a mock preferences dict."""
    return {
        "airplane_mode": {"enabled": airplane_enabled},
        "client_routing": {
            "default_client": default_client,
            "overrides": overrides or {},
        },
    }


class TestResolutionChain:
    """Priority: airplane > local_flag > override > global > implicit."""

    def test_implicit_default_when_no_config(self, resolver):
        with patch.object(resolver, "_load_prefs", return_value=_prefs()):
            result = resolver.resolve("some-action")
        assert result.source == "implicit"

    def test_global_default(self, resolver):
        prefs = _prefs(default_client="codex")
        with patch.object(resolver, "_load_prefs", return_value=prefs):
            result = resolver.resolve("some-action")
        assert result.client_id == "codex"
        assert result.source == "global"

    def test_override_beats_global(self, resolver):
        prefs = _prefs(default_client="claude-code", overrides={"job-search": "codex"})
        with patch.object(resolver, "_load_prefs", return_value=prefs):
            result = resolver.resolve("job-search")
        assert result.client_id == "codex"
        assert result.source == "override"

    def test_local_flag_beats_override(self, resolver):
        prefs = _prefs(overrides={"job-search": "codex"})
        with patch.object(resolver, "_load_prefs", return_value=prefs):
            result = resolver.resolve("job-search", local_flag=True)
        assert result.client_id == "ollama"
        assert result.source == "local_flag"

    def test_airplane_beats_everything(self, resolver):
        prefs = _prefs(
            airplane_enabled=True,
            default_client="claude-code",
            overrides={"job-search": "codex"},
        )
        with patch.object(resolver, "_load_prefs", return_value=prefs):
            result = resolver.resolve("job-search")
        assert result.client_id == "ollama"
        assert result.source == "airplane"

    def test_action_without_override_falls_through(self, resolver):
        prefs = _prefs(default_client="claude-code", overrides={"other": "codex"})
        with patch.object(resolver, "_load_prefs", return_value=prefs):
            result = resolver.resolve("unrelated-action")
        assert result.client_id == "claude-code"
        assert result.source == "global"


class TestResolvedClient:
    def test_dataclass_fields(self):
        rc = ResolvedClient(
            client_id="ollama",
            client_type="local",
            model="qwen3.5:9b",
            source="airplane",
        )
        assert rc.client_id == "ollama"
        assert rc.client_type == "local"
        assert rc.model == "qwen3.5:9b"
        assert rc.source == "airplane"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Projects/Augur && python -m pytest tests/mcp/infrastructure/test_client_resolver.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'augur_mcp.infrastructure.client_resolver'`

- [ ] **Step 3: Write the ClientResolver implementation**

```python
# src/mcp/augur_mcp/infrastructure/client_resolver.py
"""Unified AI client resolver for per-action routing.

Resolves which AI client (Claude Code, Codex, Ollama, etc.) handles
a given action by walking a priority chain:

  1. Airplane mode → Ollama (absolute override)
  2. --local flag  → Ollama (autoloop mode)
  3. Per-action override → user preference for this action
  4. Global default → user's default client
  5. Implicit → whatever IDE agent is connected
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass
class ResolvedClient:
    """Result of client resolution."""

    client_id: str
    client_type: str  # "ide" | "local" | "api"
    model: str | None = None
    source: str = "implicit"  # "airplane" | "local_flag" | "override" | "global" | "implicit"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# Known client type mappings
_CLIENT_TYPES: dict[str, str] = {
    "ollama": "local",
    "claude-code": "ide",
    "antigravity": "ide",
    "codex": "ide",
    "cursor": "ide",
    "cline": "ide",
    "gemini": "ide",
    "windsurf": "ide",
    "opencode": "ide",
    "claude-desktop": "ide",
    "cowork": "ide",
}


def _client_type_for(client_id: str) -> str:
    """Infer client_type from client_id."""
    return _CLIENT_TYPES.get(client_id, "ide")


class ClientResolver:
    """Resolves which AI client should handle a given action."""

    def __init__(self, prefs_path: Path | None = None):
        self._prefs_path = prefs_path

    def _get_prefs_path(self) -> Path:
        if self._prefs_path:
            return self._prefs_path
        from augur_mcp.config import get_config_dir
        return get_config_dir() / "preferences.yaml"

    def _load_prefs(self) -> dict[str, Any]:
        path = self._get_prefs_path()
        if not path.exists():
            return {}
        try:
            with open(path, encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception:
            return {}

    def _get_ollama_model(self, prefs: dict[str, Any]) -> str | None:
        return (
            prefs.get("local_backends", {})
            .get("ollama", {})
            .get("model", "qwen3.5:9b")
        )

    def resolve(
        self,
        action_id: str,
        *,
        local_flag: bool = False,
    ) -> ResolvedClient:
        """Resolve which client should handle the given action.

        Priority: airplane > local_flag > override > global > implicit.
        """
        prefs = self._load_prefs()
        airplane = prefs.get("airplane_mode", {})
        routing = prefs.get("client_routing", {})
        overrides = routing.get("overrides", {})
        default_client = routing.get("default_client")

        # Priority 1: Airplane mode
        if airplane.get("enabled"):
            return ResolvedClient(
                client_id="ollama",
                client_type="local",
                model=self._get_ollama_model(prefs),
                source="airplane",
            )

        # Priority 2: --local flag
        if local_flag:
            return ResolvedClient(
                client_id="ollama",
                client_type="local",
                model=self._get_ollama_model(prefs),
                source="local_flag",
            )

        # Priority 3: Per-action override
        if action_id in overrides:
            cid = overrides[action_id]
            return ResolvedClient(
                client_id=cid,
                client_type=_client_type_for(cid),
                model=self._get_ollama_model(prefs) if cid == "ollama" else None,
                source="override",
            )

        # Priority 4: Global default
        if default_client:
            return ResolvedClient(
                client_id=default_client,
                client_type=_client_type_for(default_client),
                model=self._get_ollama_model(prefs) if default_client == "ollama" else None,
                source="global",
            )

        # Priority 5: Implicit (no routing configured)
        return ResolvedClient(
            client_id="",
            client_type="ide",
            source="implicit",
        )

    def set_override(self, action_id: str, client_id: str) -> None:
        """Set a per-action client override."""
        prefs = self._load_prefs()
        routing = prefs.setdefault("client_routing", {})
        overrides = routing.setdefault("overrides", {})
        overrides[action_id] = client_id
        self._save_prefs(prefs)

    def clear_override(self, action_id: str) -> bool:
        """Clear a per-action override. Returns True if it existed."""
        prefs = self._load_prefs()
        overrides = prefs.get("client_routing", {}).get("overrides", {})
        if action_id not in overrides:
            return False
        del overrides[action_id]
        self._save_prefs(prefs)
        return True

    def set_default(self, client_id: str | None) -> None:
        """Set or clear the global default client."""
        prefs = self._load_prefs()
        routing = prefs.setdefault("client_routing", {})
        routing["default_client"] = client_id
        self._save_prefs(prefs)

    def list_overrides(self) -> dict[str, str]:
        """Return all per-action overrides."""
        prefs = self._load_prefs()
        return dict(prefs.get("client_routing", {}).get("overrides", {}))

    def _save_prefs(self, prefs: dict[str, Any]) -> None:
        path = self._get_prefs_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(prefs, f, default_flow_style=False)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Projects/Augur && python -m pytest tests/mcp/infrastructure/test_client_resolver.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/mcp/augur_mcp/infrastructure/client_resolver.py tests/mcp/infrastructure/test_client_resolver.py
git commit -m "feat(client-routing): add ClientResolver with resolution priority chain"
```

---

### Task 2: Preferences YAML Default + MCP Tools

**Files:**
- Modify: `config/defaults/config/system/preferences.yaml`
- Modify: `src/mcp/augur_mcp/infrastructure/local_backends.py`
- Create: `tests/mcp/infrastructure/test_client_routing_tools.py`

- [ ] **Step 1: Write failing tests for MCP tools**

```python
# tests/mcp/infrastructure/test_client_routing_tools.py
"""Tests for client routing MCP tools."""
import json
import pytest
from unittest.mock import patch, MagicMock
from augur_mcp.infrastructure.client_resolver import ClientResolver
from augur_mcp.infrastructure.local_backends import (
    resolve_client_impl,
    set_client_override_impl,
    list_available_clients_impl,
    ResolveClientInput,
    SetClientOverrideInput,
)


@pytest.fixture
def mock_resolver():
    return MagicMock(spec=ClientResolver)


class TestResolveClientTool:
    @pytest.mark.asyncio
    async def test_returns_resolved_client(self):
        result = await resolve_client_impl(ResolveClientInput(action_id="test-action"))
        data = json.loads(result)
        assert "client_id" in data
        assert "source" in data


class TestSetClientOverrideTool:
    @pytest.mark.asyncio
    async def test_set_override(self):
        params = SetClientOverrideInput(action_id="test-action", client_id="codex")
        result = await set_client_override_impl(params)
        data = json.loads(result)
        assert data["success"] is True

    @pytest.mark.asyncio
    async def test_clear_override(self):
        params = SetClientOverrideInput(action_id="test-action", clear=True)
        result = await set_client_override_impl(params)
        data = json.loads(result)
        assert "success" in data


class TestListAvailableClientsTool:
    @pytest.mark.asyncio
    async def test_returns_clients_list(self):
        result = await list_available_clients_impl()
        data = json.loads(result)
        assert "clients" in data
        assert isinstance(data["clients"], list)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Projects/Augur && python -m pytest tests/mcp/infrastructure/test_client_routing_tools.py -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Add `client_routing` section to preferences defaults**

Add to `config/defaults/config/system/preferences.yaml` after the `airplane_mode` section:

```yaml
client_routing:
  default_client: null
  overrides: {}
```

- [ ] **Step 4: Add Pydantic input models and tool implementations to `local_backends.py`**

Add these imports at the top of `src/mcp/augur_mcp/infrastructure/local_backends.py`:

```python
from augur_mcp.infrastructure.client_resolver import ClientResolver
```

Add these input models after `ToggleAirplaneModeInput`:

```python
class ResolveClientInput(BaseModel):
    """Input for resolve-client."""

    action_id: str = Field(..., description="Action ID to resolve client for")
    model_config = ConfigDict(str_strip_whitespace=True, extra="allow")


class SetClientOverrideInput(BaseModel):
    """Input for set-client-override."""

    action_id: str = Field(..., description="Action ID to set override for")
    client_id: str | None = Field(default=None, description="Client ID to route to")
    clear: bool = Field(default=False, description="Clear the override for this action")
    model_config = ConfigDict(str_strip_whitespace=True, extra="allow")
```

Add these implementation functions after `toggle_airplane_mode_impl`:

```python
# ── Client routing ────────────────────────────────────────────────────


async def resolve_client_impl(params: ResolveClientInput) -> str:
    """Resolve which AI client should handle the given action."""
    resolver = ClientResolver()
    result = resolver.resolve(params.action_id)
    return json.dumps(result.to_dict(), indent=2)


async def set_client_override_impl(params: SetClientOverrideInput) -> str:
    """Set or clear a per-action client override."""
    resolver = ClientResolver()
    if params.clear:
        existed = resolver.clear_override(params.action_id)
        return json.dumps({
            "success": True,
            "action": "cleared" if existed else "no_override_existed",
            "action_id": params.action_id,
        }, indent=2)
    if not params.client_id:
        return json.dumps({"success": False, "error": "client_id required when not clearing"}, indent=2)
    resolver.set_override(params.action_id, params.client_id)
    return json.dumps({
        "success": True,
        "action": "set",
        "action_id": params.action_id,
        "client_id": params.client_id,
    }, indent=2)


async def list_available_clients_impl() -> str:
    """List available AI clients from the integrations registry."""
    from pathlib import Path
    import yaml as _yaml

    from augur_mcp.config import get_config_dir

    integrations_path = get_config_dir() / ".." / "agents" / "ide_integrations.yaml"
    clients: list[dict[str, Any]] = []

    if integrations_path.exists():
        try:
            with open(integrations_path, encoding="utf-8") as f:
                data = _yaml.safe_load(f) or {}
            for key, entry in data.get("integrations", {}).items():
                if not entry.get("enabled"):
                    continue
                client_type = "local" if key == "ollama" else "ide"
                clients.append({
                    "client_id": key,
                    "client_type": client_type,
                    "installed": entry.get("installed", False),
                    "healthy": entry.get("last_health", {}).get("healthy", False),
                })
        except Exception:
            pass

    # Always include Ollama if not already present
    if not any(c["client_id"] == "ollama" for c in clients):
        ollama = _detect_ollama()
        clients.append({
            "client_id": "ollama",
            "client_type": "local",
            "installed": ollama["installed"],
            "healthy": ollama["server_running"],
        })

    return json.dumps({"clients": clients, "count": len(clients)}, indent=2)
```

Update `__all__` at the bottom of `local_backends.py`:

```python
__all__ = [
    "GetLocalBackendStatusInput",
    "ToggleAirplaneModeInput",
    "ResolveClientInput",
    "SetClientOverrideInput",
    "get_local_backend_status_impl",
    "toggle_airplane_mode_impl",
    "resolve_client_impl",
    "set_client_override_impl",
    "list_available_clients_impl",
]
```

- [ ] **Step 5: Register MCP tools in `src/mcp/augur_mcp/infrastructure/__init__.py`**

In `src/mcp/augur_mcp/infrastructure/__init__.py`, after the `toggle-airplane-mode` tool registration (line ~217), add three new tool registrations. Also add the imports at the top alongside the existing ones:

```python
from augur_mcp.infrastructure.local_backends import (
    ResolveClientInput,
    SetClientOverrideInput,
    resolve_client_impl,
    set_client_override_impl,
    list_available_clients_impl,
)
```

Then register the tools:

```python
    # Register client routing tools
    @mcp.tool(
        name="resolve-client",
        annotations=tool_annotations(
            {
                "title": "Resolve AI Client",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def resolve_client(
        action_id: str,
    ) -> str:
        """Resolve which AI client should handle the given action.

        Walks the priority chain: airplane > local_flag > override > global > implicit.
        Returns client_id, client_type, model, and source.
        """
        params = ResolveClientInput(action_id=action_id)
        return await resolve_client_impl(params)

    @mcp.tool(
        name="set-client-override",
        annotations=tool_annotations(
            {
                "title": "Set Client Override",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def set_client_override(
        action_id: str,
        client_id: str | None = None,
        clear: bool = False,
    ) -> str:
        """Set or clear a per-action AI client override.

        Persists to client_routing.overrides in preferences.yaml.
        """
        params = SetClientOverrideInput(action_id=action_id, client_id=client_id, clear=clear)
        return await set_client_override_impl(params)

    @mcp.tool(
        name="list-available-clients",
        annotations=tool_annotations(
            {
                "title": "List Available Clients",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def list_available_clients() -> str:
        """List available AI clients from the integrations registry.

        Returns installed and healthy clients that can be used for action routing.
        """
        return await list_available_clients_impl()
```

Also add the three new tool names to `src/mcp/augur_mcp/client_surface.py` alongside the existing `get-local-backend-status` and `toggle-airplane-mode` entries (around line 87).

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd ~/Projects/Augur && python -m pytest tests/mcp/infrastructure/test_client_routing_tools.py -v`
Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add config/defaults/config/system/preferences.yaml src/mcp/augur_mcp/infrastructure/local_backends.py tests/mcp/infrastructure/test_client_routing_tools.py
git commit -m "feat(client-routing): add MCP tools and preferences schema for client routing"
```

---

### Task 3: OpsContext `client` Field + Autoloop `--local` Flag

**Files:**
- Modify: `src/lib/ops_protocol.py:88-99` — add `client` field to `OpsContext`
- Modify: `skills/daemon/scripts/adaptive_loop_executor.py:128-173` — add `--local` parser arg and propagate
- Modify: `skills/daemon/scripts/adaptive/engine.py:135-163` — set `ctx.client` from `OpsContext`
- Create: `tests/daemon/test_local_flag.py`

- [ ] **Step 1: Write failing test for `--local` flag**

```python
# tests/daemon/test_local_flag.py
"""Tests for --local flag in adaptive loop executor."""
import pytest
from src.lib.ops_protocol import OpsContext


class TestOpsContextClient:
    def test_default_client_is_none(self):
        ctx = OpsContext()
        assert ctx.client is None

    def test_client_can_be_set(self):
        ctx = OpsContext(client="ollama")
        assert ctx.client == "ollama"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Projects/Augur && python -m pytest tests/daemon/test_local_flag.py -v`
Expected: FAIL with `TypeError: __init__() got an unexpected keyword argument 'client'`

- [ ] **Step 3: Add `client` field to `OpsContext`**

In `src/lib/ops_protocol.py`, add `client` field to the `OpsContext` dataclass after `session`:

```python
@dataclass
class OpsContext:
    """Context passed to every scan/fix call."""

    project_root: Path = field(default_factory=lambda: Path.cwd())
    difficulty: int = 0
    dry_run: bool = False
    verbose: bool = False
    evolve: bool = False
    config: dict = field(default_factory=dict)
    loop_config: dict = field(default_factory=dict)
    shared_snapshot: dict = field(default_factory=dict)
    session: SessionContext = field(default_factory=SessionContext)
    client: str | None = None  # AI client override: "ollama" for --local, None for default
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/Projects/Augur && python -m pytest tests/daemon/test_local_flag.py -v`
Expected: All tests PASS

- [ ] **Step 5: Add `--local` flag to `adaptive_loop_executor.py`**

In `skills/daemon/scripts/adaptive_loop_executor.py`, add after the `--force` argument (line ~168):

```python
    parser.add_argument(
        "--local",
        action="store_true",
        help="Run with local Ollama backend instead of cloud AI client",
    )
```

Then in the `_run_single_loop` function and the `main()` dispatches, propagate the local flag. In the engine initialization section (around line 190), after `engine = AdaptiveLoopEngine(...)`:

```python
    # Propagate --local flag to engine for OpsContext injection
    if args.local:
        engine._local_client = "ollama"
    else:
        engine._local_client = None
```

- [ ] **Step 6: Propagate `client` through engine to OpsContext**

In `skills/daemon/scripts/adaptive/engine.py`, find where `OpsContext` is constructed (search for `OpsContext(`). Add `client=self._local_client` to each constructor call. Initialize `self._local_client = None` in `AdaptiveLoopEngine.__init__`.

The exact lines to modify are where `OpsContext` is constructed in `engine_entry_runner.py` and `loop_reporter.py`. The `client` field passes through the `OpsContext` dataclass unchanged — scan/fix functions can read `ctx.client` to decide their backend.

- [ ] **Step 7: Run full test suite for daemon**

Run: `cd ~/Projects/Augur && python -m pytest tests/daemon/ -v --timeout=30`
Expected: All existing tests still pass, new test passes

- [ ] **Step 8: Commit**

```bash
git add src/lib/ops_protocol.py skills/daemon/scripts/adaptive_loop_executor.py skills/daemon/scripts/adaptive/engine.py tests/daemon/test_local_flag.py
git commit -m "feat(client-routing): add --local flag to autoloops with OpsContext.client field"
```

---

### Task 4: `/local config` CLI Command

**Files:**
- Create: `skills/local/commands/config.md`
- Modify: `skills/local/SKILL.md` — add `config` subcommand documentation

- [ ] **Step 1: Create the command definition**

```markdown
---
name: config
description: Configure per-action AI client routing
dispatch: fire
mcp_tool: resolve-client
---

Manage per-action AI client routing. Set which client (Claude Code, Codex, Ollama, etc.) handles specific actions.

## Usage

```
/local config <action-id> <client-id>   # Set override
/local config <action-id> --clear        # Remove override
/local config --list                     # Show all overrides
/local config --default <client-id>      # Set global default
```

## Prompt

When invoked as `/local config`:

1. Parse the arguments:
   - `<action-id> <client-id>` → call `set-client-override` with `{action_id, client_id}`
   - `<action-id> --clear` → call `set-client-override` with `{action_id, clear: true}`
   - `--list` → call `resolve-client` for each action, then display as table
   - `--default <client-id>` → call `set-client-override` with `{action_id: "__global__", client_id}`
2. Show confirmation of the action taken
3. If `--list`, display table: Action ID | Client | Source
```

- [ ] **Step 2: Update SKILL.md with config subcommand**

In `skills/local/SKILL.md`, add to the commands section:

```markdown
### /local config

Configure per-action AI client routing.

| Syntax | Effect |
|--------|--------|
| `/local config <action> <client>` | Set override for action |
| `/local config <action> --clear` | Clear override |
| `/local config --list` | Show all overrides |
| `/local config --default <client>` | Set global default |
```

- [ ] **Step 3: Commit**

```bash
git add skills/local/commands/config.md skills/local/SKILL.md
git commit -m "feat(client-routing): add /local config CLI command for client overrides"
```

---

### Task 5: Dashboard — `useActionRunner` Integration

**Files:**
- Modify: `apps/dashboard/hooks/useActionRunner.ts:639-704` — call `resolve-client` before dispatch

- [ ] **Step 1: Add `resolveClient` helper to `useActionRunner.ts`**

Add this function before the `useActionRunner` export (around line 629):

```typescript
/**
 * Resolve which AI client should handle this action.
 * Returns the resolved client info, or null if using implicit default.
 */
async function resolveClient(
  actionId: string,
): Promise<{ client_id: string; client_type: string; source: string } | null> {
  try {
    const data = await mcpCall("resolve-client", {
      action_id: actionId,
    }) as { client_id: string; client_type: string; source: string };
    if (data.source === "implicit") return null;
    return data;
  } catch {
    return null;
  }
}
```

- [ ] **Step 2: Wire `resolveClient` into `runAction`**

In the `runAction` function (line ~639), after the confirmation/concurrency checks and before the switch statement, add client resolution:

```typescript
    // Resolve AI client routing
    const resolvedClient = await resolveClient(action.id);

    // If client is "local" type (Ollama), adjust dispatch:
    // IDE/chat/api actions with Ollama should show in action dialog
    // so user can copy prompt to local agent.
    // Fire actions proceed as-is (MCP tools work regardless of client).
    let effectiveAction = action;
    if (resolvedClient && resolvedClient.client_type === "local" && action.dispatch !== "fire") {
      // For local clients, route IDE/chat/api through action dialog
      // with the resolved client info attached
      effectiveAction = {
        ...action,
        recommended_agent: resolvedClient.client_id,
      };
    }
```

Then update the switch to use `effectiveAction` instead of `action` for `runIde`, `runChat`, `runOneshot`, `runApi` calls.

- [ ] **Step 3: Verify dashboard builds**

Run: `cd ~/Projects/Augur/apps/dashboard && npx next build`
Expected: Build succeeds with no type errors

- [ ] **Step 4: Commit**

```bash
git add apps/dashboard/hooks/useActionRunner.ts
git commit -m "feat(client-routing): resolve AI client before action dispatch in useActionRunner"
```

---

### Task 6: Dashboard — Browse Page Client Dropdown

**Files:**
- Modify: `apps/dashboard/components/shared/BrowseDetailActions.tsx`

- [ ] **Step 1: Add client selector to `BrowseDetailActions`**

Replace the content of `apps/dashboard/components/shared/BrowseDetailActions.tsx` with an updated version that includes a client dropdown per action:

```tsx
'use client';

import { useState, useEffect } from 'react';
import * as LucideIcons from 'lucide-react';
import { useActionRunner } from '@/hooks/useActionRunner';
import { mcpCall } from '@/lib/mcp/client';
import type { SkillAction } from '@/lib/browse/types';

function resolveIcon(name?: string): React.ElementType {
  if (!name) return LucideIcons.Zap;
  const Icon = (LucideIcons as unknown as Record<string, React.ElementType>)[name];
  return Icon ?? LucideIcons.Zap;
}

interface AvailableClient {
  client_id: string;
  client_type: string;
  installed: boolean;
  healthy: boolean;
}

interface BrowseDetailActionsProps {
  actions: SkillAction[];
  skillId: string;
}

function ClientSelector({ actionId }: { actionId: string }) {
  const [clients, setClients] = useState<AvailableClient[]>([]);
  const [currentClient, setCurrentClient] = useState<string>('');
  const [source, setSource] = useState<string>('implicit');
  const [isAirplane, setIsAirplane] = useState(false);
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    // Load current resolution and available clients
    Promise.all([
      mcpCall('resolve-client', { action_id: actionId }) as Promise<{
        client_id: string;
        source: string;
      }>,
      mcpCall('list-available-clients', {}) as Promise<{
        clients: AvailableClient[];
      }>,
    ]).then(([resolved, available]) => {
      setCurrentClient(resolved.client_id);
      setSource(resolved.source);
      setIsAirplane(resolved.source === 'airplane');
      setClients(available.clients || []);
    }).catch(() => {});
  }, [actionId]);

  const handleSelect = async (clientId: string) => {
    if (clientId === '') {
      await mcpCall('set-client-override', { action_id: actionId, clear: true });
      setCurrentClient('');
      setSource('implicit');
    } else {
      await mcpCall('set-client-override', { action_id: actionId, client_id: clientId });
      setCurrentClient(clientId);
      setSource('override');
    }
    setIsOpen(false);
  };

  const displayLabel = isAirplane
    ? 'Ollama (airplane)'
    : source === 'implicit' || source === 'global'
      ? `Default${currentClient ? ` (${currentClient})` : ''}`
      : currentClient;

  return (
    <div className="relative">
      <button
        onClick={() => !isAirplane && setIsOpen(!isOpen)}
        disabled={isAirplane}
        className={`text-xs px-2 py-0.5 rounded border transition-colors ${
          isAirplane
            ? 'border-amber-500/30 text-amber-400 cursor-not-allowed'
            : source === 'override'
              ? 'border-[var(--accent-primary)]/30 text-[var(--accent-primary)]'
              : 'border-[var(--border-secondary)] text-[var(--text-tertiary)]'
        }`}
      >
        {displayLabel}
        {source === 'override' && !isAirplane && (
          <span
            className="ml-1 cursor-pointer hover:text-red-400"
            onClick={(e) => {
              e.stopPropagation();
              handleSelect('');
            }}
          >
            x
          </span>
        )}
      </button>
      {isOpen && (
        <div className="absolute z-50 mt-1 right-0 bg-[var(--bg-secondary)] border border-[var(--border-secondary)] rounded-lg shadow-lg py-1 min-w-[160px]">
          <button
            onClick={() => handleSelect('')}
            className="w-full px-3 py-1.5 text-left text-xs hover:bg-[var(--bg-tertiary)] text-[var(--text-secondary)]"
          >
            Use default
          </button>
          {clients.filter(c => c.installed).map((client) => (
            <button
              key={client.client_id}
              onClick={() => handleSelect(client.client_id)}
              className={`w-full px-3 py-1.5 text-left text-xs hover:bg-[var(--bg-tertiary)] ${
                client.client_id === currentClient ? 'text-[var(--accent-primary)]' : 'text-[var(--text-secondary)]'
              }`}
            >
              {client.client_id}
              {!client.healthy && (
                <span className="ml-1 text-amber-400">(offline)</span>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export function BrowseDetailActions({ actions, skillId }: BrowseDetailActionsProps) {
  const { runAction, isExecuting } = useActionRunner();

  if (actions.length === 0) return null;

  return (
    <div className="space-y-2">
      {actions.map((action) => {
        const Icon = resolveIcon(action.icon);
        return (
          <div key={action.id} className="flex items-center gap-2">
            <button
              onClick={() =>
                runAction({
                  id: action.id,
                  label: action.label,
                  description: action.description ?? action.label,
                  dispatch: action.dispatch as 'fire' | 'ide' | 'modal',
                  page: `/browse?skill=${skillId}`,
                  mcp_tools: action.mcp_tools,
                })
              }
              disabled={isExecuting}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-lg bg-[var(--accent-primary)]/10 text-[var(--accent-primary)] hover:bg-[var(--accent-primary)]/20 transition-colors disabled:opacity-50"
              title={action.description}
            >
              <Icon className="w-3.5 h-3.5" />
              {action.label}
            </button>
            <ClientSelector actionId={action.id} />
          </div>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 2: Verify dashboard builds**

Run: `cd ~/Projects/Augur/apps/dashboard && npx next build`
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
git add apps/dashboard/components/shared/BrowseDetailActions.tsx
git commit -m "feat(client-routing): add client selector dropdown to Browse page action buttons"
```

---

### Task 7: Integration Test — End-to-End Flow

**Files:**
- Create: `tests/integration/test_client_routing_e2e.py`

- [ ] **Step 1: Write integration test**

```python
# tests/integration/test_client_routing_e2e.py
"""Integration test for client routing end-to-end flow."""
import json
import pytest
import tempfile
from pathlib import Path

import yaml

from augur_mcp.infrastructure.client_resolver import ClientResolver
from augur_mcp.infrastructure.local_backends import (
    resolve_client_impl,
    set_client_override_impl,
    ResolveClientInput,
    SetClientOverrideInput,
)


@pytest.fixture
def temp_prefs(tmp_path):
    """Create a temporary preferences file."""
    prefs_path = tmp_path / "preferences.yaml"
    prefs_path.write_text(yaml.dump({
        "airplane_mode": {"enabled": False},
        "local_backends": {"ollama": {"model": "qwen3.5:9b"}},
        "client_routing": {
            "default_client": "claude-code",
            "overrides": {},
        },
    }))
    return prefs_path


class TestEndToEndRouting:
    def test_full_override_lifecycle(self, temp_prefs):
        resolver = ClientResolver(prefs_path=temp_prefs)

        # Initially: global default
        result = resolver.resolve("career-search")
        assert result.client_id == "claude-code"
        assert result.source == "global"

        # Set override
        resolver.set_override("career-search", "codex")
        result = resolver.resolve("career-search")
        assert result.client_id == "codex"
        assert result.source == "override"

        # Other actions unaffected
        result = resolver.resolve("health-track")
        assert result.client_id == "claude-code"
        assert result.source == "global"

        # Clear override
        resolver.clear_override("career-search")
        result = resolver.resolve("career-search")
        assert result.client_id == "claude-code"
        assert result.source == "global"

    def test_airplane_overrides_all(self, temp_prefs):
        resolver = ClientResolver(prefs_path=temp_prefs)
        resolver.set_override("career-search", "codex")

        # Enable airplane
        prefs = yaml.safe_load(temp_prefs.read_text())
        prefs["airplane_mode"]["enabled"] = True
        temp_prefs.write_text(yaml.dump(prefs))

        result = resolver.resolve("career-search")
        assert result.client_id == "ollama"
        assert result.source == "airplane"
        assert result.model == "qwen3.5:9b"

    def test_local_flag_overrides_override(self, temp_prefs):
        resolver = ClientResolver(prefs_path=temp_prefs)
        resolver.set_override("career-search", "codex")

        result = resolver.resolve("career-search", local_flag=True)
        assert result.client_id == "ollama"
        assert result.source == "local_flag"

    def test_list_overrides(self, temp_prefs):
        resolver = ClientResolver(prefs_path=temp_prefs)
        resolver.set_override("a", "codex")
        resolver.set_override("b", "ollama")

        overrides = resolver.list_overrides()
        assert overrides == {"a": "codex", "b": "ollama"}

    def test_set_default(self, temp_prefs):
        resolver = ClientResolver(prefs_path=temp_prefs)
        resolver.set_default("antigravity")

        result = resolver.resolve("any-action")
        assert result.client_id == "antigravity"
        assert result.source == "global"
```

- [ ] **Step 2: Run integration test**

Run: `cd ~/Projects/Augur && python -m pytest tests/integration/test_client_routing_e2e.py -v`
Expected: All tests PASS (these test against the real ClientResolver with temp files)

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_client_routing_e2e.py
git commit -m "test(client-routing): add integration tests for end-to-end routing flow"
```

---

### Task 8: Verify Build + Browser Check

**Files:** No new files — verification only.

- [ ] **Step 1: Run full Python test suite**

Run: `cd ~/Projects/Augur && python -m pytest tests/mcp/infrastructure/test_client_resolver.py tests/mcp/infrastructure/test_client_routing_tools.py tests/daemon/test_local_flag.py tests/integration/test_client_routing_e2e.py -v`
Expected: All tests pass

- [ ] **Step 2: Run dashboard build**

Run: `cd ~/Projects/Augur/apps/dashboard && npx next build`
Expected: Build succeeds with no errors

- [ ] **Step 3: Start dev server and verify Browse page**

Run dashboard dev server, navigate to Browse page, click on an action to see the client dropdown. Verify:
- Default shows "Default (claude-code)" or similar
- Dropdown lists installed clients from integrations
- Selecting a client shows the override
- Clicking "x" clears the override back to default

- [ ] **Step 4: Test `/local config` CLI**

In Claude Code or terminal:
```bash
/local config --list
/local config career-job-search codex
/local config --list
/local config career-job-search --clear
```

- [ ] **Step 5: Test `--local` flag**

```bash
cd ~/Projects/Augur
python skills/daemon/scripts/adaptive_loop_executor.py run auto-code-health --local
```
Verify it runs without errors and logs indicate Ollama client context.
