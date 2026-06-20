# Local Mode: Ollama Integration & Airplane Mode — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable users to run their existing CLI agents (Claude Code, Codex) against a local Ollama model server, with airplane mode that auto-switches to local when offline.

**Architecture:** Ollama is an infrastructure backend tracked via preferences and a new MCP tool. Two new skills (`/airplane`, `/local`) provide user-facing commands. The existing OllamaAdapter gets extended with model inventory and launch logic. A lightweight connectivity watchdog script powers auto-detect.

**Tech Stack:** Python (MCP tools, connectivity watchdog, adapter extensions), YAML (preferences), Markdown (SKILL.md for commands)

---

### Task 1: Local Backend MCP Tool — Implementation

**Files:**
- Create: `src/mcp/augur_mcp/infrastructure/local_backends.py`
- Modify: `src/mcp/augur_mcp/infrastructure/__init__.py`
- Modify: `src/mcp/augur_mcp/client_surface.py:18-92`
- Create: `tests/packages/augur-mcp/tools/test_local_backends.py`

- [ ] **Step 1: Write the failing test for `get_local_backend_status`**

```python
# tests/packages/augur-mcp/tools/test_local_backends.py
"""
Local Backend MCP Tool Contract Tests.

User Need: Check local backend (Ollama) health and airplane mode status.

Run with: cd packages/augur-mcp && uv run pytest tests/tools/test_local_backends.py -v
"""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import yaml

from augur_mcp.infrastructure.local_backends import (
    get_local_backend_status_impl,
    GetLocalBackendStatusInput,
)


@pytest.fixture
def temp_prefs_dir(tmp_path, monkeypatch):
    """Create isolated preferences directory."""
    config_dir = tmp_path / "config-data"
    config_dir.mkdir()
    monkeypatch.setattr(
        "augur_mcp.infrastructure.local_backends._get_preferences_path",
        lambda: config_dir / "preferences.yaml",
    )
    return config_dir


@pytest.fixture
def prefs_with_local(temp_prefs_dir):
    """Create preferences with local backend config."""
    prefs_file = temp_prefs_dir / "preferences.yaml"
    prefs = {
        "local_backends": {
            "default": "ollama",
            "ollama": {
                "binary": "/opt/homebrew/bin/ollama",
                "model": "qwen3.5:9b",
                "agent": "claude",
                "context_length": 32768,
                "extra_args": [],
            },
        },
        "airplane_mode": {
            "enabled": False,
            "auto_detect": True,
            "fallback_tools": ["web-search", "web-fetch", "knowledge-summarize-url"],
        },
    }
    prefs_file.write_text(yaml.dump(prefs))
    return prefs_file


@pytest.mark.contract
class TestGetLocalBackendStatusContract:
    """
    User Need: See if local backend is ready for offline use.
    """

    @pytest.mark.asyncio
    async def test_returns_ollama_status(self, prefs_with_local):
        """User story: I can see if Ollama is installed and what models I have."""
        with patch(
            "augur_mcp.infrastructure.local_backends._detect_ollama"
        ) as mock_detect:
            mock_detect.return_value = {
                "installed": True,
                "version": "0.17.6",
                "binary": "/opt/homebrew/bin/ollama",
                "server_running": True,
                "models": [{"name": "qwen3.5:9b", "size": "6.6 GB"}],
            }

            result = await get_local_backend_status_impl(
                GetLocalBackendStatusInput()
            )
            data = json.loads(result)

            assert "ollama" in data
            assert data["ollama"]["installed"] is True
            assert data["ollama"]["ready"] is True
            assert data["ollama"]["configured_model"] == "qwen3.5:9b"

    @pytest.mark.asyncio
    async def test_returns_airplane_mode_status(self, prefs_with_local):
        """User story: I can see if airplane mode is on."""
        with patch(
            "augur_mcp.infrastructure.local_backends._detect_ollama"
        ) as mock_detect:
            mock_detect.return_value = {
                "installed": True,
                "version": "0.17.6",
                "binary": "/opt/homebrew/bin/ollama",
                "server_running": True,
                "models": [],
            }

            result = await get_local_backend_status_impl(
                GetLocalBackendStatusInput()
            )
            data = json.loads(result)

            assert "airplane_mode" in data
            assert data["airplane_mode"]["enabled"] is False

    @pytest.mark.asyncio
    async def test_not_ready_when_no_models(self, prefs_with_local):
        """User story: I see not-ready when no models are pulled."""
        with patch(
            "augur_mcp.infrastructure.local_backends._detect_ollama"
        ) as mock_detect:
            mock_detect.return_value = {
                "installed": True,
                "version": "0.17.6",
                "binary": "/opt/homebrew/bin/ollama",
                "server_running": True,
                "models": [],
            }

            result = await get_local_backend_status_impl(
                GetLocalBackendStatusInput()
            )
            data = json.loads(result)
            assert data["ollama"]["ready"] is False

    @pytest.mark.asyncio
    async def test_not_ready_when_not_installed(self, temp_prefs_dir):
        """User story: I see not-ready when Ollama is not installed."""
        # No prefs file — defaults kick in
        with patch(
            "augur_mcp.infrastructure.local_backends._detect_ollama"
        ) as mock_detect:
            mock_detect.return_value = {
                "installed": False,
                "version": None,
                "binary": None,
                "server_running": False,
                "models": [],
            }

            result = await get_local_backend_status_impl(
                GetLocalBackendStatusInput()
            )
            data = json.loads(result)
            assert data["ollama"]["installed"] is False
            assert data["ollama"]["ready"] is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Projects/Augur && uv run pytest tests/packages/augur-mcp/tools/test_local_backends.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'augur_mcp.infrastructure.local_backends'`

- [ ] **Step 3: Write the implementation**

```python
# src/mcp/augur_mcp/infrastructure/local_backends.py
"""
Local backend status tool implementation.

Detects Ollama installation, running status, available models,
and airplane mode configuration.
"""

import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field


class GetLocalBackendStatusInput(BaseModel):
    """Input for getting local backend status."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="allow")


_AIRPLANE_MODE_DEFAULTS: dict[str, Any] = {
    "enabled": False,
    "forced": False,
    "auto_detect": True,
    "fallback_tools": ["web-search", "web-fetch", "knowledge-summarize-url"],
}

_OLLAMA_DEFAULTS: dict[str, Any] = {
    "binary": None,
    "model": "qwen3.5:9b",
    "agent": "claude",
    "context_length": 32768,
    "extra_args": [],
}


def _get_preferences_path() -> Path:
    """Get the path to preferences.yaml."""
    from augur_mcp.config import get_config_dir

    return get_config_dir() / "preferences.yaml"


def _load_local_prefs() -> dict[str, Any]:
    """Load local_backends and airplane_mode from preferences."""
    path = _get_preferences_path()
    if not path.exists():
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def _detect_ollama() -> dict[str, Any]:
    """Detect Ollama installation and running status."""
    result: dict[str, Any] = {
        "installed": False,
        "version": None,
        "binary": None,
        "server_running": False,
        "models": [],
    }

    binary = shutil.which("ollama")
    if not binary:
        return result

    result["installed"] = True
    result["binary"] = binary

    # Get version
    try:
        out = subprocess.run(
            [binary, "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if out.returncode == 0:
            # "ollama version is 0.17.6"
            version_text = out.stdout.strip()
            result["version"] = version_text.split()[-1] if version_text else None
    except Exception:
        pass

    # Check server and list models
    try:
        out = subprocess.run(
            [binary, "list"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if out.returncode == 0:
            result["server_running"] = True
            lines = out.stdout.strip().split("\n")
            # Skip header line ("NAME  ID  SIZE  MODIFIED")
            for line in lines[1:]:
                parts = line.split()
                if len(parts) >= 3:
                    result["models"].append({
                        "name": parts[0],
                        "size": f"{parts[2]} {parts[3]}" if len(parts) >= 4 else parts[2],
                    })
    except Exception:
        result["server_running"] = False

    return result


async def get_local_backend_status_impl(
    params: GetLocalBackendStatusInput,
) -> str:
    """Get local backend status including Ollama health and airplane mode.

    Returns:
        JSON string with ollama status and airplane_mode status.
    """
    prefs = _load_local_prefs()
    backends_cfg = prefs.get("local_backends", {})
    airplane_cfg = prefs.get("airplane_mode", {})
    ollama_cfg = backends_cfg.get("ollama", {})

    # Merge defaults
    ollama_prefs = {**_OLLAMA_DEFAULTS, **ollama_cfg}
    airplane_prefs = {**_AIRPLANE_MODE_DEFAULTS, **airplane_cfg}

    # Detect Ollama
    detection = _detect_ollama()

    # Determine readiness
    has_configured_model = any(
        m["name"] == ollama_prefs["model"] for m in detection["models"]
    )
    ready = (
        detection["installed"]
        and detection["server_running"]
        and len(detection["models"]) > 0
    )

    return json.dumps(
        {
            "ollama": {
                "installed": detection["installed"],
                "version": detection["version"],
                "binary": detection["binary"],
                "server_running": detection["server_running"],
                "models": detection["models"],
                "configured_model": ollama_prefs["model"],
                "configured_agent": ollama_prefs["agent"],
                "has_configured_model": has_configured_model,
                "ready": ready,
            },
            "airplane_mode": {
                "enabled": airplane_prefs["enabled"],
                "forced": airplane_prefs.get("forced", False),
                "auto_detect": airplane_prefs["auto_detect"],
                "fallback_tools": airplane_prefs["fallback_tools"],
                "last_check": datetime.now().isoformat(),
            },
            "launch_command": (
                f"ollama launch {ollama_prefs['agent']} --model {ollama_prefs['model']}"
                if ready
                else None
            ),
        },
        indent=2,
    )


__all__ = [
    "get_local_backend_status_impl",
    "GetLocalBackendStatusInput",
]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Projects/Augur && uv run pytest tests/packages/augur-mcp/tools/test_local_backends.py -v`
Expected: all 4 tests PASS

- [ ] **Step 5: Register the MCP tool and add to visible tools**

In `src/mcp/augur_mcp/infrastructure/__init__.py`, add inside `register_infrastructure_tools()`:

```python
from augur_mcp.infrastructure.local_backends import (
    get_local_backend_status_impl,
    GetLocalBackendStatusInput,
)

@mcp.tool(
    name="get-local-backend-status",
    annotations=tool_annotations(
        {
            "title": "Get Local Backend Status",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        }
    ),
)
async def get_local_backend_status(params: GetLocalBackendStatusInput) -> str:
    """Get local backend (Ollama) health and airplane mode status."""
    return await get_local_backend_status_impl(params)
```

In `src/mcp/augur_mcp/client_surface.py`, add `"get-local-backend-status"` to the `CURATED_VISIBLE_TOOLS` frozenset (after `"get-job-status"`):

```python
        "get-local-backend-status",
```

- [ ] **Step 6: Commit**

```bash
git add src/mcp/augur_mcp/infrastructure/local_backends.py \
        src/mcp/augur_mcp/infrastructure/__init__.py \
        src/mcp/augur_mcp/client_surface.py \
        tests/packages/augur-mcp/tools/test_local_backends.py
git commit -m "feat(local-mode): add get-local-backend-status MCP tool

Detects Ollama installation, running status, available models,
and airplane mode preferences. Registered in CURATED_VISIBLE_TOOLS."
```

---

### Task 2: Connectivity Watchdog Script

**Files:**
- Create: `src/mcp/augur_mcp/infrastructure/connectivity.py`
- Create: `tests/packages/augur-mcp/tools/test_connectivity.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/packages/augur-mcp/tools/test_connectivity.py
"""
Connectivity watchdog tests.

Run with: cd packages/augur-mcp && uv run pytest tests/tools/test_connectivity.py -v
"""

import json
from unittest.mock import patch

import pytest

from augur_mcp.infrastructure.connectivity import check_connectivity


class TestConnectivity:
    def test_online_when_dns_resolves(self):
        """DNS resolution succeeds → online."""
        with patch("socket.getaddrinfo") as mock_dns:
            mock_dns.return_value = [("family", "type", "proto", "canon", ("1.2.3.4", 443))]
            result = check_connectivity()
            assert result["online"] is True

    def test_offline_when_dns_fails(self):
        """DNS resolution fails → offline."""
        with patch("socket.getaddrinfo") as mock_dns:
            mock_dns.side_effect = OSError("Name resolution failed")
            result = check_connectivity()
            assert result["online"] is False

    def test_returns_timestamp(self):
        """Result includes a timestamp."""
        with patch("socket.getaddrinfo") as mock_dns:
            mock_dns.return_value = [("family", "type", "proto", "canon", ("1.2.3.4", 443))]
            result = check_connectivity()
            assert "checked_at" in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Projects/Augur && uv run pytest tests/packages/augur-mcp/tools/test_connectivity.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

```python
# src/mcp/augur_mcp/infrastructure/connectivity.py
"""
Connectivity detection for airplane mode auto-switching.

Uses DNS resolution (fast, low overhead) to determine if cloud APIs are reachable.
"""

import socket
from datetime import datetime


_CHECK_HOST = "api.anthropic.com"
_CHECK_PORT = 443
_TIMEOUT_S = 3


def check_connectivity(host: str = _CHECK_HOST, port: int = _CHECK_PORT) -> dict:
    """Check if the cloud API endpoint is reachable via DNS.

    Returns:
        dict with keys: online (bool), host (str), checked_at (str)
    """
    try:
        socket.getaddrinfo(host, port, socket.AF_UNSPEC, socket.SOCK_STREAM)
        return {
            "online": True,
            "host": host,
            "checked_at": datetime.now().isoformat(),
        }
    except (socket.gaierror, OSError):
        return {
            "online": False,
            "host": host,
            "checked_at": datetime.now().isoformat(),
        }


__all__ = ["check_connectivity"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Projects/Augur && uv run pytest tests/packages/augur-mcp/tools/test_connectivity.py -v`
Expected: all 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/mcp/augur_mcp/infrastructure/connectivity.py \
        tests/packages/augur-mcp/tools/test_connectivity.py
git commit -m "feat(local-mode): add connectivity watchdog for airplane mode auto-detect

DNS-based check against api.anthropic.com. Returns online/offline status."
```

---

### Task 3: Airplane Mode Toggle MCP Tool

**Files:**
- Modify: `src/mcp/augur_mcp/infrastructure/local_backends.py`
- Modify: `src/mcp/augur_mcp/infrastructure/__init__.py`
- Modify: `src/mcp/augur_mcp/client_surface.py`
- Create: `tests/packages/augur-mcp/tools/test_airplane_mode.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/packages/augur-mcp/tools/test_airplane_mode.py
"""
Airplane Mode MCP Tool Contract Tests.

Run with: cd packages/augur-mcp && uv run pytest tests/tools/test_airplane_mode.py -v
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from augur_mcp.infrastructure.local_backends import (
    toggle_airplane_mode_impl,
    ToggleAirplaneModeInput,
)


@pytest.fixture
def temp_prefs_dir(tmp_path, monkeypatch):
    config_dir = tmp_path / "config-data"
    config_dir.mkdir()
    monkeypatch.setattr(
        "augur_mcp.infrastructure.local_backends._get_preferences_path",
        lambda: config_dir / "preferences.yaml",
    )
    return config_dir


@pytest.fixture
def prefs_airplane_off(temp_prefs_dir):
    prefs_file = temp_prefs_dir / "preferences.yaml"
    prefs = {
        "airplane_mode": {
            "enabled": False,
            "forced": False,
            "auto_detect": True,
            "fallback_tools": ["web-search", "web-fetch", "knowledge-summarize-url"],
        },
        "local_backends": {
            "default": "ollama",
            "ollama": {"model": "qwen3.5:9b", "agent": "claude"},
        },
    }
    prefs_file.write_text(yaml.dump(prefs))
    return prefs_file


@pytest.mark.contract
class TestToggleAirplaneModeContract:
    @pytest.mark.asyncio
    async def test_enable_airplane_mode(self, prefs_airplane_off, temp_prefs_dir):
        """User can turn on airplane mode."""
        params = ToggleAirplaneModeInput(action="on")
        result = await toggle_airplane_mode_impl(params)
        data = json.loads(result)

        assert data["success"] is True
        assert data["airplane_mode"]["enabled"] is True
        assert data["airplane_mode"]["forced"] is True

        # Verify persisted
        saved = yaml.safe_load((temp_prefs_dir / "preferences.yaml").read_text())
        assert saved["airplane_mode"]["enabled"] is True

    @pytest.mark.asyncio
    async def test_disable_airplane_mode(self, prefs_airplane_off, temp_prefs_dir):
        """User can turn off airplane mode."""
        # First enable
        await toggle_airplane_mode_impl(ToggleAirplaneModeInput(action="on"))
        # Then disable
        result = await toggle_airplane_mode_impl(ToggleAirplaneModeInput(action="off"))
        data = json.loads(result)

        assert data["success"] is True
        assert data["airplane_mode"]["enabled"] is False
        assert data["airplane_mode"]["forced"] is False

    @pytest.mark.asyncio
    async def test_status_returns_current_state(self, prefs_airplane_off):
        """User can check airplane mode status."""
        params = ToggleAirplaneModeInput(action="status")
        result = await toggle_airplane_mode_impl(params)
        data = json.loads(result)

        assert "airplane_mode" in data
        assert "connectivity" in data

    @pytest.mark.asyncio
    async def test_toggle_flips_state(self, prefs_airplane_off):
        """No-arg toggles the current state."""
        params = ToggleAirplaneModeInput(action="toggle")
        result = await toggle_airplane_mode_impl(params)
        data = json.loads(result)

        assert data["success"] is True
        assert data["airplane_mode"]["enabled"] is True  # was False, now True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Projects/Augur && uv run pytest tests/packages/augur-mcp/tools/test_airplane_mode.py -v`
Expected: FAIL — `ImportError: cannot import name 'toggle_airplane_mode_impl'`

- [ ] **Step 3: Add toggle implementation to `local_backends.py`**

Append to `src/mcp/augur_mcp/infrastructure/local_backends.py`:

```python
class ToggleAirplaneModeInput(BaseModel):
    """Input for toggling airplane mode."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="allow")

    action: str = Field(
        default="toggle",
        description="Action: 'on', 'off', 'toggle', or 'status'",
    )


def _save_prefs_key(key: str, value: Any) -> None:
    """Update a single top-level key in preferences.yaml."""
    path = _get_preferences_path()
    prefs: dict[str, Any] = {}
    if path.exists():
        try:
            with open(path, encoding="utf-8") as f:
                prefs = yaml.safe_load(f) or {}
        except Exception:
            prefs = {}
    prefs[key] = value
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(prefs, f, default_flow_style=False, sort_keys=True)


async def toggle_airplane_mode_impl(params: ToggleAirplaneModeInput) -> str:
    """Toggle or query airplane mode.

    Actions:
        on     — enable airplane mode (forced, ignores auto-detect)
        off    — disable airplane mode, re-enable auto-detect
        toggle — flip current state
        status — return current state + connectivity
    """
    from augur_mcp.infrastructure.connectivity import check_connectivity

    prefs = _load_local_prefs()
    airplane = {**_AIRPLANE_MODE_DEFAULTS, **prefs.get("airplane_mode", {})}

    action = params.action.lower()

    if action == "status":
        conn = check_connectivity()
        return json.dumps({
            "airplane_mode": airplane,
            "connectivity": conn,
        }, indent=2)

    if action == "on":
        airplane["enabled"] = True
        airplane["forced"] = True
    elif action == "off":
        airplane["enabled"] = False
        airplane["forced"] = False
    elif action == "toggle":
        airplane["enabled"] = not airplane["enabled"]
        airplane["forced"] = airplane["enabled"]
    else:
        return json.dumps({"success": False, "error": f"Unknown action: {action}"})

    _save_prefs_key("airplane_mode", airplane)

    return json.dumps({
        "success": True,
        "airplane_mode": airplane,
    }, indent=2)
```

Update `__all__` in `local_backends.py`:

```python
__all__ = [
    "get_local_backend_status_impl",
    "GetLocalBackendStatusInput",
    "toggle_airplane_mode_impl",
    "ToggleAirplaneModeInput",
]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Projects/Augur && uv run pytest tests/packages/augur-mcp/tools/test_airplane_mode.py -v`
Expected: all 4 tests PASS

- [ ] **Step 5: Register the MCP tool**

In `src/mcp/augur_mcp/infrastructure/__init__.py`, add alongside the earlier registration:

```python
from augur_mcp.infrastructure.local_backends import (
    toggle_airplane_mode_impl,
    ToggleAirplaneModeInput,
)

@mcp.tool(
    name="toggle-airplane-mode",
    annotations=tool_annotations(
        {
            "title": "Toggle Airplane Mode",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        }
    ),
)
async def toggle_airplane_mode(params: ToggleAirplaneModeInput) -> str:
    """Toggle airplane mode for offline local-model operation."""
    return await toggle_airplane_mode_impl(params)
```

In `src/mcp/augur_mcp/client_surface.py`, add `"toggle-airplane-mode"` to `CURATED_VISIBLE_TOOLS`.

- [ ] **Step 6: Commit**

```bash
git add src/mcp/augur_mcp/infrastructure/local_backends.py \
        src/mcp/augur_mcp/infrastructure/__init__.py \
        src/mcp/augur_mcp/client_surface.py \
        tests/packages/augur-mcp/tools/test_airplane_mode.py
git commit -m "feat(local-mode): add toggle-airplane-mode MCP tool

Supports on/off/toggle/status actions. Persists to preferences.yaml.
Uses connectivity watchdog for status checks."
```

---

### Task 4: `/airplane` Skill

**Files:**
- Create: `skills/airplane/SKILL.md`

- [ ] **Step 1: Create the skill directory**

```bash
mkdir -p ~/Projects/Augur/skills/airplane
```

- [ ] **Step 2: Write SKILL.md**

```markdown
---
name: airplane
description: Toggle airplane mode — routes all commands through local Ollama backend when offline or manually forced
x-augur-type: command
x-augur-hub: command
x-augur-tags: [local, offline, ollama]
x-augur-mcp-tools:
  - toggle-airplane-mode
  - get-local-backend-status
---

# Airplane Mode

<!-- AUGUR_ARGUMENT_CONTRACT_V1 -->
## Argument Handling (Auto)

1. Parse runtime arguments from `$ARGUMENTS`.
2. If `$ARGUMENTS` is empty, parse text after `/airplane` in the user request.
3. Preserve argument tokens exactly (including flags and order).
4. If arguments are present, execute the matching sub-command/flag path in this command.
5. Only use the command's default behavior when arguments are truly empty.
6. If arguments are unrecognized, return valid usage instead of silently defaulting.

Toggle airplane mode to route all agent commands through a local Ollama backend instead of cloud APIs.

## Usage

- `/airplane on` — Force airplane mode on (stays on until `/airplane off`)
- `/airplane off` — Disable airplane mode, re-enable auto-detect
- `/airplane status` — Show current mode, connectivity, and backend health
- `/airplane` (no args) — Toggle current state

## Execution

### `on`

1. Call MCP tool:
   ```
   Tool: toggle-airplane-mode
   Args: { "action": "on" }
   ```
2. Call MCP tool to verify backend readiness:
   ```
   Tool: get-local-backend-status
   Args: {}
   ```
3. If Ollama is ready, display:
   ```
   Airplane mode ON — using local model qwen3.5:9b via ollama launch claude
   Filtered external tools: web-search, web-fetch, knowledge-summarize-url
   ```
4. If Ollama is NOT ready, display warning:
   ```
   Airplane mode ON — but local backend is not ready:
   - Ollama not installed: brew install ollama
   - Server not running: ollama serve
   - No models: ollama pull qwen3.5:9b
   ```

### `off`

1. Call MCP tool:
   ```
   Tool: toggle-airplane-mode
   Args: { "action": "off" }
   ```
2. Display: `Airplane mode OFF — using cloud API. Auto-detect re-enabled.`

### `status`

1. Call MCP tool:
   ```
   Tool: toggle-airplane-mode
   Args: { "action": "status" }
   ```
2. Call MCP tool:
   ```
   Tool: get-local-backend-status
   Args: {}
   ```
3. Display a status table:

| Field | Value |
|-------|-------|
| Airplane mode | on/off |
| Forced | yes/no |
| Auto-detect | enabled/disabled |
| Connectivity | online/offline |
| Ollama | installed/not installed |
| Server | running/stopped |
| Model | qwen3.5:9b (6.6 GB) |
| Agent | claude |
| Launch command | `ollama launch claude --model qwen3.5:9b` |

### Toggle (no args)

1. Call MCP tool:
   ```
   Tool: toggle-airplane-mode
   Args: { "action": "toggle" }
   ```
2. Display new state using the same format as `on` or `off` above.

## Global Flags

- `--help` — Show this usage information and stop
- `--evolve` — Emit execution telemetry after running
```

- [ ] **Step 3: Commit**

```bash
git add skills/airplane/SKILL.md
git commit -m "feat(local-mode): add /airplane slash command skill

Toggle airplane mode on/off/toggle/status via MCP tools."
```

---

### Task 5: `/local` Skill

**Files:**
- Create: `skills/local/SKILL.md`

- [ ] **Step 1: Create the skill directory**

```bash
mkdir -p ~/Projects/Augur/skills/local
```

- [ ] **Step 2: Write SKILL.md**

```markdown
---
name: local
description: Manage local Ollama backend — launch agents, check status, pull models, configure preferences
x-augur-type: command
x-augur-hub: command
x-augur-tags: [local, ollama, models]
x-augur-mcp-tools:
  - get-local-backend-status
  - get-preferences
  - update-preference
---

# Local Mode

<!-- AUGUR_ARGUMENT_CONTRACT_V1 -->
## Argument Handling (Auto)

1. Parse runtime arguments from `$ARGUMENTS`.
2. If `$ARGUMENTS` is empty, parse text after `/local` in the user request.
3. Preserve argument tokens exactly (including flags and order).
4. If arguments are present, execute the matching sub-command/flag path in this command.
5. Only use the command's default behavior when arguments are truly empty.
6. If arguments are unrecognized, return valid usage instead of silently defaulting.

Manage the local Ollama backend for running CLI agents with local models.

## Usage

- `/local` or `/local launch` — Launch the configured agent with Ollama
- `/local status` — Show Ollama health, installed models, current config
- `/local pull <model>` — Pull a model and optionally set as default
- `/local config` — Show/edit local backend preferences
- `/local models` — List installed Ollama models

## Execution

### `launch` (default)

1. Call MCP tool:
   ```
   Tool: get-local-backend-status
   Args: {}
   ```
2. If not ready, show what's missing and how to fix it.
3. If ready, display the launch command and run it:
   ```bash
   ollama launch claude --model qwen3.5:9b
   ```
   Use Bash tool to execute. Pass any `extra_args` from preferences after `--`.

### `status`

1. Call MCP tool:
   ```
   Tool: get-local-backend-status
   Args: {}
   ```
2. Display a status report:

| Field | Value |
|-------|-------|
| Ollama | v0.17.6 at /opt/homebrew/bin/ollama |
| Server | running |
| Models | qwen3.5:9b (6.6 GB) |
| Default model | qwen3.5:9b |
| Default agent | claude |
| Launch command | `ollama launch claude --model qwen3.5:9b` |
| Airplane mode | off |

### `pull <model>`

1. Run via Bash tool:
   ```bash
   ollama pull <model>
   ```
2. After successful pull, ask if user wants to set this as the default model.
3. If yes, call MCP tool:
   ```
   Tool: update-preference
   Args: { "key": "local_backends", "value": { ...current config with updated model... } }
   ```

### `config`

1. Call MCP tool:
   ```
   Tool: get-preferences
   Args: { "key": "local_backends" }
   ```
2. Display current configuration in a readable format.
3. Ask what the user wants to change:
   - Default model
   - Default agent (claude, codex, opencode, cline, droid, openclaw, pi)
   - Context length
   - Extra args
4. Apply changes via:
   ```
   Tool: update-preference
   Args: { "key": "local_backends", "value": { ...updated config... } }
   ```

### `models`

1. Run via Bash tool:
   ```bash
   ollama list
   ```
2. Display as a formatted table with name, size, and last modified.

## First-Time Setup

If no `local_backends` preference exists when any subcommand runs:

1. Detect Ollama binary (`which ollama`)
2. List available models (`ollama list`)
3. Set defaults:
   ```
   Tool: update-preference
   Args: {
     "key": "local_backends",
     "value": {
       "default": "ollama",
       "ollama": {
         "binary": "<detected path>",
         "model": "<first available model or 'qwen3.5:9b'>",
         "agent": "claude",
         "context_length": 32768,
         "extra_args": []
       }
     }
   }
   ```
4. Confirm: "Local mode configured. Run `/local launch` to start."

## Supported Ollama Agents

| Agent | Launch |
|-------|--------|
| Claude Code | `ollama launch claude --model <model>` |
| Codex | `ollama launch codex --model <model>` |
| OpenCode | `ollama launch opencode --model <model>` |
| Cline | `ollama launch cline --model <model>` |
| Droid | `ollama launch droid --model <model>` |
| OpenClaw | `ollama launch openclaw --model <model>` |
| Pi | `ollama launch pi --model <model>` |

## Global Flags

- `--help` — Show this usage information and stop
- `--evolve` — Emit execution telemetry after running
```

- [ ] **Step 3: Commit**

```bash
git add skills/local/SKILL.md
git commit -m "feat(local-mode): add /local slash command skill

Manage Ollama backend: launch, status, pull, config, models."
```

---

### Task 6: Update Integration Config and OllamaAdapter

**Files:**
- Modify: `config/agents/ide_integrations.yaml`
- Modify: `skills/ai/augur/adapters/ollama.py`

- [ ] **Step 1: Read current integration config for Ollama**

```bash
grep -A 20 'ollama:' ~/Projects/Augur/config/agents/ide_integrations.yaml
```

- [ ] **Step 2: Update Ollama entry in `ide_integrations.yaml`**

Update the existing `ollama` entry to include local backend health checks and the `launch` capability:

```yaml
  ollama:
    enabled: true
    config_paths: []
    last_applied: null
    desired_capabilities:
      - local_inference
      - model_serving
      - agent_launch
    last_health: null
    last_error: null
    installed: true
    managed_files: []
    health_checks:
      binary_present: "which ollama"
      server_running: "ollama list"
      models_available: "ollama list"
    managed_by: augur
```

- [ ] **Step 3: Extend OllamaAdapter with launch command support**

In `skills/ai/augur/adapters/ollama.py`, add a `get_launch_command` method after `get_supported_fallbacks`:

```python
def get_launch_command(self, agent: str = "claude", model: str = "qwen3.5:9b", extra_args: list[str] | None = None) -> list[str]:
    """Build the ollama launch command for a given agent and model.

    Args:
        agent: Agent integration name (claude, codex, opencode, etc.)
        model: Ollama model name
        extra_args: Additional args passed after -- to the agent CLI

    Returns:
        Command as a list of strings suitable for subprocess.
    """
    cmd = ["ollama", "launch", agent, "--model", model]
    if extra_args:
        cmd.append("--")
        cmd.extend(extra_args)
    return cmd
```

- [ ] **Step 4: Commit**

```bash
git add config/agents/ide_integrations.yaml \
        skills/ai/augur/adapters/ollama.py
git commit -m "feat(local-mode): update Ollama integration config and adapter

Add agent_launch capability, health check commands, and
get_launch_command method to OllamaAdapter."
```

---

### Task 7: Seed Default Preferences

**Files:**
- Modify: `config/defaults/config/system/preferences.yaml`

- [ ] **Step 1: Read current defaults**

```bash
cat ~/Projects/Augur/config/defaults/config/system/preferences.yaml
```

- [ ] **Step 2: Add local backend defaults to the defaults file**

Append to `config/defaults/config/system/preferences.yaml`:

```yaml
local_backends:
  default: ollama
  ollama:
    binary: null
    model: qwen3.5:9b
    agent: claude
    context_length: 32768
    extra_args: []

airplane_mode:
  enabled: false
  forced: false
  auto_detect: true
  fallback_tools:
    - web-search
    - web-fetch
    - knowledge-summarize-url
```

- [ ] **Step 3: Commit**

```bash
git add config/defaults/config/system/preferences.yaml
git commit -m "feat(local-mode): seed default preferences for local backends and airplane mode"
```

---

### Task 8: Update `/onboard` Skill with Local Mode Step

**Files:**
- Modify: `skills/onboard/SKILL.md`

- [ ] **Step 1: Read the current onboard skill**

```bash
head -100 ~/Projects/Augur/skills/onboard/SKILL.md
```

- [ ] **Step 2: Add a "Local Mode Setup" section**

Add after the existing platform connection steps in the SKILL.md:

```markdown
### Local Mode Setup (Optional)

Detect and configure Ollama for offline operation.

1. Check if Ollama is installed: `which ollama`
2. If installed:
   - Check server status: `ollama list`
   - Show available models
   - Ask user which model to use as default
   - Ask which agent to use (claude recommended)
   - Save preferences via:
     ```
     Tool: update-preference
     Args: { "key": "local_backends", "value": { "default": "ollama", "ollama": { "binary": "<path>", "model": "<chosen>", "agent": "<chosen>", "context_length": 32768, "extra_args": [] } } }
     ```
   - Display: "Local mode configured. Use `/local launch` to start, `/airplane on` for offline mode."
3. If not installed:
   - Display: "Ollama not found. Install with `brew install ollama` for local model support. Skip for now? (y/n)"
   - If skip, continue onboarding. If install, run `brew install ollama` and repeat from step 2.
```

- [ ] **Step 3: Add `x-augur-mcp-tools` entries if not already present**

Ensure the onboard SKILL.md frontmatter includes:
```yaml
x-augur-mcp-tools:
  - get-local-backend-status
  - update-preference
```

(Append to existing list if one exists.)

- [ ] **Step 4: Commit**

```bash
git add skills/onboard/SKILL.md
git commit -m "feat(local-mode): add local mode setup step to /onboard

Detects Ollama, configures default model and agent preferences."
```

---

### Task 9: Run Full Test Suite and Verify

**Files:** None (verification only)

- [ ] **Step 1: Run all new tests**

```bash
cd ~/Projects/Augur && uv run pytest \
    tests/packages/augur-mcp/tools/test_local_backends.py \
    tests/packages/augur-mcp/tools/test_connectivity.py \
    tests/packages/augur-mcp/tools/test_airplane_mode.py \
    -v
```

Expected: all tests PASS

- [ ] **Step 2: Run existing preference tests to verify no regressions**

```bash
cd ~/Projects/Augur && uv run pytest \
    tests/packages/augur-mcp/tools/test_preferences_tools.py \
    -v
```

Expected: all existing tests PASS

- [ ] **Step 3: Verify MCP tool registration**

```bash
cd ~/Projects/Augur && uv run python -c "
from augur_mcp.client_surface import CURATED_VISIBLE_TOOLS
assert 'get-local-backend-status' in CURATED_VISIBLE_TOOLS
assert 'toggle-airplane-mode' in CURATED_VISIBLE_TOOLS
print('Both tools in CURATED_VISIBLE_TOOLS')
"
```

Expected: prints confirmation

- [ ] **Step 4: Verify Ollama detection works end-to-end**

```bash
cd ~/Projects/Augur && uv run python -c "
from augur_mcp.infrastructure.local_backends import _detect_ollama
result = _detect_ollama()
print(f'Installed: {result[\"installed\"]}')
print(f'Version: {result[\"version\"]}')
print(f'Server: {result[\"server_running\"]}')
print(f'Models: {result[\"models\"]}')
"
```

Expected: shows actual Ollama status with qwen3.5:9b

- [ ] **Step 5: Verify skill files are discoverable**

```bash
ls -la ~/Projects/Augur/skills/airplane/SKILL.md
ls -la ~/Projects/Augur/skills/local/SKILL.md
```

Expected: both files exist

- [ ] **Step 6: Final commit if any fixes were needed**

Only if previous steps required fixes. Otherwise skip.
