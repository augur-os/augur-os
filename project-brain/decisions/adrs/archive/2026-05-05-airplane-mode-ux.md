# Airplane Mode UX & Local-Backend Routing — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make airplane mode end-to-end functional — surface the toggle in the dashboard sidebar, mirror it in the chat header, and actually swap agent backends to local Ollama via `ollama launch <agent>` when ON.

**Architecture:** `preferences.yaml` is the single source of truth. A new MCP tool `get-airplane-launch-overrides` answers "is the configured agent runnable locally right now, and if so what's the argv?" The CLI start path consults it and either rewrites argv to use `ollama launch` or returns 409 with a platform-aware setup hint. Browser-side localStorage for airplane state is replaced by a thin React-Query hook so all UI surfaces re-render in lockstep.

**Tech Stack:** Python (MCP tools, subprocess detection), TypeScript / React (Next.js dashboard, Zustand → React-Query refactor), Pytest (Python contract tests), Vitest + React Testing Library (UI tests), Playwright (gated e2e smoke).

**Spec:** [`docs/superpowers/specs/2026-05-05-airplane-mode-ux-design.md`](../specs/2026-05-05-airplane-mode-ux-design.md)

---

## File map

| Layer | File | Action |
|---|---|---|
| MCP tool impl | `src/mcp/augur_mcp/infrastructure/local_backends.py` | extend |
| MCP registration | `src/mcp/augur_mcp/infrastructure/__init__.py` | modify |
| MCP visibility | `src/mcp/augur_mcp/client_surface.py` | modify |
| API route | `apps/dashboard/app/api/airplane/route.ts` | create |
| API route | `apps/dashboard/app/api/cli/actions.ts` | modify |
| Component | `apps/dashboard/components/shared/AirplanePill.tsx` | create |
| Layout mount | `apps/dashboard/app/layout.tsx` (sidebar `<aside>` near `BrainLogo`) | modify |
| Component | `apps/dashboard/features/components/chat/ChatHeader.tsx` | modify |
| Hook | `apps/dashboard/features/hooks/useCliChat.ts` | modify |
| Store refactor | `apps/dashboard/lib/stores/airplaneModeStore.ts` | refactor |
| Settings | `apps/dashboard/app/settings/tabs/SecurityTab.tsx` | modify |
| Test | `tests/packages/augur-mcp/tools/test_local_backends.py` | extend |
| Test | `tests/dashboard/api/airplane-route.test.ts` | create |
| Test | `tests/dashboard/api/cli-route-airplane.test.ts` | create |
| Test | `tests/dashboard/components/AirplanePill.test.tsx` | create |
| Test | `tests/dashboard/components/ChatHeader-airplane-chip.test.tsx` | create |
| Test | `tests/dashboard/features/hooks/useCliChat-airplane-transitions.test.ts` | create |
| Test | `tests/dashboard/settings/SecurityTab-local-backend.test.tsx` | create |
| Smoke (gated) | `tests/e2e/airplane-mode.spec.ts` | create |

---

## Task 1: Platform-aware Ollama binary detection

**Files:**
- Modify: `src/mcp/augur_mcp/infrastructure/local_backends.py`
- Test: `tests/packages/augur-mcp/tools/test_local_backends.py`

- [ ] **Step 1: Write the failing tests for Windows + macOS detection**

Append to `tests/packages/augur-mcp/tools/test_local_backends.py`:

```python
import sys
import os
from unittest.mock import patch
from pathlib import Path

class TestPlatformAwareDetection:
    def test_windows_localappdata_candidate(self, monkeypatch, tmp_path):
        """Windows: prefer %LOCALAPPDATA%/Programs/Ollama/ollama.exe when shutil.which fails."""
        fake = tmp_path / "Programs" / "Ollama" / "ollama.exe"
        fake.parent.mkdir(parents=True)
        fake.write_text("")  # touch
        monkeypatch.setattr(sys, "platform", "win32")
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
        with patch(
            "augur_mcp.infrastructure.local_backends.shutil.which",
            return_value=None,
        ):
            from augur_mcp.infrastructure.local_backends import _resolve_ollama_binary
            assert _resolve_ollama_binary() == str(fake)

    def test_macos_homebrew_candidate(self, monkeypatch):
        """macOS: prefer /opt/homebrew/bin/ollama when shutil.which fails."""
        monkeypatch.setattr(sys, "platform", "darwin")
        with patch(
            "augur_mcp.infrastructure.local_backends.shutil.which",
            return_value=None,
        ), patch(
            "augur_mcp.infrastructure.local_backends._candidate_exists",
            side_effect=lambda p: p == "/opt/homebrew/bin/ollama",
        ):
            from augur_mcp.infrastructure.local_backends import _resolve_ollama_binary
            assert _resolve_ollama_binary() == "/opt/homebrew/bin/ollama"

    def test_returns_none_when_all_candidates_missing(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "darwin")
        with patch(
            "augur_mcp.infrastructure.local_backends.shutil.which",
            return_value=None,
        ), patch(
            "augur_mcp.infrastructure.local_backends._candidate_exists",
            return_value=False,
        ):
            from augur_mcp.infrastructure.local_backends import _resolve_ollama_binary
            assert _resolve_ollama_binary() is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Projects/Augur && uv run pytest tests/packages/augur-mcp/tools/test_local_backends.py::TestPlatformAwareDetection -v`
Expected: FAIL — `ImportError: cannot import name '_resolve_ollama_binary'`.

- [ ] **Step 3: Add `_resolve_ollama_binary` to `local_backends.py`**

Insert near the top of `src/mcp/augur_mcp/infrastructure/local_backends.py` (before `_detect_ollama`):

```python
import os
import sys

def _candidate_exists(path: str) -> bool:
    """Wrapped for monkey-patching in tests."""
    return Path(path).exists()


def _platform_candidates() -> list[str]:
    """Return Ollama binary candidate paths in priority order for current platform."""
    if sys.platform == "win32":
        localappdata = os.environ.get("LOCALAPPDATA", "")
        programfiles = os.environ.get("PROGRAMFILES", "")
        userprofile = os.environ.get("USERPROFILE", "")
        out: list[str] = []
        if localappdata:
            out.append(str(Path(localappdata) / "Programs" / "Ollama" / "ollama.exe"))
        if programfiles:
            out.append(str(Path(programfiles) / "Ollama" / "ollama.exe"))
        if userprofile:
            out.append(
                str(
                    Path(userprofile)
                    / "AppData"
                    / "Local"
                    / "Programs"
                    / "Ollama"
                    / "ollama.exe"
                )
            )
        return out
    # darwin / linux share these
    home = Path.home()
    return [
        "/opt/homebrew/bin/ollama",
        "/usr/local/bin/ollama",
        str(home / ".local" / "bin" / "ollama"),
    ]


def _resolve_ollama_binary() -> str | None:
    """Find ollama binary via PATH first, then platform-specific candidates."""
    found = shutil.which("ollama")
    if found:
        return found
    for candidate in _platform_candidates():
        if _candidate_exists(candidate):
            return candidate
    return None
```

Then update `_detect_ollama()` to use it:

```python
def _detect_ollama() -> dict[str, Any]:
    result: dict[str, Any] = {
        "installed": False,
        "version": None,
        "binary": None,
        "server_running": False,
        "models": [],
    }

    binary = _resolve_ollama_binary()
    if not binary:
        return result

    result["installed"] = True
    result["binary"] = binary
    # ... rest of existing implementation unchanged ...
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Projects/Augur && uv run pytest tests/packages/augur-mcp/tools/test_local_backends.py::TestPlatformAwareDetection -v`
Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/mcp/augur_mcp/infrastructure/local_backends.py \
        tests/packages/augur-mcp/tools/test_local_backends.py
git commit -m "feat(airplane): platform-aware Ollama binary detection

Adds _resolve_ollama_binary that probes Windows (%LOCALAPPDATA%, %PROGRAMFILES%)
and macOS/Linux candidate paths after shutil.which falls through. Required for
Windows users whose installer doesn't update PATH until next shell."
```

---

## Task 2: `list-ollama-integrations` MCP tool

**Files:**
- Modify: `src/mcp/augur_mcp/infrastructure/local_backends.py`
- Modify: `src/mcp/augur_mcp/infrastructure/__init__.py`
- Modify: `src/mcp/augur_mcp/client_surface.py`
- Test: `tests/packages/augur-mcp/tools/test_local_backends.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/packages/augur-mcp/tools/test_local_backends.py`:

```python
HELP_OUTPUT_SAMPLE = """\
Launch the Ollama interactive menu, or directly launch a specific integration.

Without arguments, this is equivalent to running 'ollama' directly.
Flags and extra arguments require an integration name.

Supported integrations:
  claude    Claude Code
  cline     Cline
  codex     Codex
  copilot   Copilot CLI (aliases: copilot-cli)
  droid     Droid
  hermes    Hermes Agent
  kimi      Kimi Code CLI
  opencode  OpenCode
  openclaw  OpenClaw (aliases: clawdbot, moltbot)
  pi        Pi
  vscode    VS Code (aliases: code)

Examples:
  ollama launch claude
"""

class TestListOllamaIntegrations:
    @pytest.mark.asyncio
    async def test_parses_help_output(self):
        from augur_mcp.infrastructure.local_backends import (
            list_ollama_integrations_impl,
            ListOllamaIntegrationsInput,
        )
        with patch(
            "augur_mcp.infrastructure.local_backends._resolve_ollama_binary",
            return_value="/usr/local/bin/ollama",
        ), patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = HELP_OUTPUT_SAMPLE
            result = await list_ollama_integrations_impl(ListOllamaIntegrationsInput())
            data = json.loads(result)
            assert "claude" in data["integrations"]
            assert "codex" in data["integrations"]
            assert "copilot" in data["integrations"]
            # aliases collapsed to canonical id
            assert "copilot-cli" not in data["integrations"]
            assert len(data["integrations"]) == 11

    @pytest.mark.asyncio
    async def test_returns_empty_when_binary_missing(self):
        from augur_mcp.infrastructure.local_backends import (
            list_ollama_integrations_impl,
            ListOllamaIntegrationsInput,
        )
        with patch(
            "augur_mcp.infrastructure.local_backends._resolve_ollama_binary",
            return_value=None,
        ):
            result = await list_ollama_integrations_impl(ListOllamaIntegrationsInput())
            data = json.loads(result)
            assert data["integrations"] == []

    @pytest.mark.asyncio
    async def test_returns_empty_when_launch_unknown(self):
        """Older Ollama versions: 'launch' is not a known subcommand."""
        from augur_mcp.infrastructure.local_backends import (
            list_ollama_integrations_impl,
            ListOllamaIntegrationsInput,
            _reset_integrations_cache,
        )
        _reset_integrations_cache()
        with patch(
            "augur_mcp.infrastructure.local_backends._resolve_ollama_binary",
            return_value="/usr/local/bin/ollama",
        ), patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1
            mock_run.return_value.stderr = "Error: unknown command \"launch\""
            result = await list_ollama_integrations_impl(ListOllamaIntegrationsInput())
            data = json.loads(result)
            assert data["integrations"] == []

    @pytest.mark.asyncio
    async def test_caches_subsequent_calls(self):
        from augur_mcp.infrastructure.local_backends import (
            list_ollama_integrations_impl,
            ListOllamaIntegrationsInput,
            _reset_integrations_cache,
        )
        _reset_integrations_cache()
        with patch(
            "augur_mcp.infrastructure.local_backends._resolve_ollama_binary",
            return_value="/usr/local/bin/ollama",
        ), patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = HELP_OUTPUT_SAMPLE
            await list_ollama_integrations_impl(ListOllamaIntegrationsInput())
            await list_ollama_integrations_impl(ListOllamaIntegrationsInput())
            assert mock_run.call_count == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Projects/Augur && uv run pytest tests/packages/augur-mcp/tools/test_local_backends.py::TestListOllamaIntegrations -v`
Expected: FAIL — `ImportError: cannot import name 'list_ollama_integrations_impl'`.

- [ ] **Step 3: Add the implementation**

Append to `src/mcp/augur_mcp/infrastructure/local_backends.py`:

```python
import re
import time

_INTEGRATIONS_CACHE: dict[str, Any] = {"value": None, "fetched_at": 0.0}
_INTEGRATIONS_TTL_S = 60.0

_INTEGRATION_LINE_RE = re.compile(r"^\s+([a-z][a-z0-9_-]*)\s+\S")


def _reset_integrations_cache() -> None:
    """Test helper — clear the integrations cache."""
    _INTEGRATIONS_CACHE["value"] = None
    _INTEGRATIONS_CACHE["fetched_at"] = 0.0


def _parse_integrations_help(stdout: str) -> list[str]:
    """Parse `ollama launch --help` output for integration ids.

    Looks for lines under 'Supported integrations:' that match
    '  <id>   <description>'. Aliases in parentheses are ignored.
    """
    lines = stdout.splitlines()
    started = False
    out: list[str] = []
    for line in lines:
        if line.strip().lower().startswith("supported integrations"):
            started = True
            continue
        if started:
            if not line.strip():
                # blank line ends the section
                if out:
                    break
                else:
                    continue
            if line.strip().lower().startswith("example"):
                break
            m = _INTEGRATION_LINE_RE.match(line)
            if m:
                out.append(m.group(1))
    return out


class ListOllamaIntegrationsInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="allow")


async def list_ollama_integrations_impl(
    params: ListOllamaIntegrationsInput,
) -> str:
    """Return the agent integrations supported by `ollama launch`. Cached 60s.

    Returns:
        JSON string: { "integrations": ["claude", "codex", ...] }
    """
    now = time.monotonic()
    cached = _INTEGRATIONS_CACHE["value"]
    if (
        cached is not None
        and (now - _INTEGRATIONS_CACHE["fetched_at"]) < _INTEGRATIONS_TTL_S
    ):
        return json.dumps({"integrations": cached}, indent=2)

    binary = _resolve_ollama_binary()
    if not binary:
        _INTEGRATIONS_CACHE["value"] = []
        _INTEGRATIONS_CACHE["fetched_at"] = now
        return json.dumps({"integrations": []}, indent=2)

    try:
        result = subprocess.run(
            [binary, "launch", "--help"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            _INTEGRATIONS_CACHE["value"] = []
            _INTEGRATIONS_CACHE["fetched_at"] = now
            return json.dumps({"integrations": []}, indent=2)
        integrations = _parse_integrations_help(result.stdout)
    except Exception:
        integrations = []

    _INTEGRATIONS_CACHE["value"] = integrations
    _INTEGRATIONS_CACHE["fetched_at"] = now
    return json.dumps({"integrations": integrations}, indent=2)
```

Update `__all__`:

```python
__all__ = [
    "get_local_backend_status_impl",
    "GetLocalBackendStatusInput",
    "toggle_airplane_mode_impl",
    "ToggleAirplaneModeInput",
    "list_ollama_integrations_impl",
    "ListOllamaIntegrationsInput",
]
```

- [ ] **Step 4: Register the MCP tool**

In `src/mcp/augur_mcp/infrastructure/__init__.py`, alongside the existing `toggle-airplane-mode` registration, add:

```python
from augur_mcp.infrastructure.local_backends import (
    list_ollama_integrations_impl,
    ListOllamaIntegrationsInput,
)

@mcp.tool(
    name="list-ollama-integrations",
    annotations=tool_annotations(
        {
            "title": "List Ollama Integrations",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        }
    ),
)
async def list_ollama_integrations(params: ListOllamaIntegrationsInput) -> str:
    """List agent integrations Ollama can launch (claude, codex, opencode, ...)."""
    return await list_ollama_integrations_impl(params)
```

In `src/mcp/augur_mcp/client_surface.py`, add `"list-ollama-integrations"` to `CURATED_VISIBLE_TOOLS`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd ~/Projects/Augur && uv run pytest tests/packages/augur-mcp/tools/test_local_backends.py::TestListOllamaIntegrations -v`
Expected: 4 PASS.

- [ ] **Step 6: Verify registration**

Run:
```bash
cd ~/Projects/Augur && uv run python -c "
from augur_mcp.client_surface import CURATED_VISIBLE_TOOLS
assert 'list-ollama-integrations' in CURATED_VISIBLE_TOOLS, 'tool not registered'
print('ok')
"
```
Expected: `ok`.

- [ ] **Step 7: Commit**

```bash
git add src/mcp/augur_mcp/infrastructure/local_backends.py \
        src/mcp/augur_mcp/infrastructure/__init__.py \
        src/mcp/augur_mcp/client_surface.py \
        tests/packages/augur-mcp/tools/test_local_backends.py
git commit -m "feat(airplane): add list-ollama-integrations MCP tool

Parses 'ollama launch --help' to discover supported agent integrations.
Cached for 60s to avoid subprocess spawn on every UI render. Returns the
canonical id list (claude, cline, codex, copilot, droid, hermes, kimi,
opencode, openclaw, pi, vscode); aliases ignored."
```

---

## Task 3: `get-airplane-launch-overrides` MCP tool

**Files:**
- Modify: `src/mcp/augur_mcp/infrastructure/local_backends.py`
- Modify: `src/mcp/augur_mcp/infrastructure/__init__.py`
- Modify: `src/mcp/augur_mcp/client_surface.py`
- Test: `tests/packages/augur-mcp/tools/test_local_backends.py`

- [ ] **Step 1: Write the failing tests for all five reason cases**

Append to `tests/packages/augur-mcp/tools/test_local_backends.py`:

```python
class TestGetAirplaneLaunchOverrides:
    @pytest.fixture(autouse=True)
    def _reset_caches(self):
        from augur_mcp.infrastructure.local_backends import _reset_integrations_cache
        _reset_integrations_cache()
        yield

    @pytest.fixture
    def prefs_qwen(self, tmp_path, monkeypatch):
        prefs_file = tmp_path / "preferences.yaml"
        prefs = {
            "local_backends": {
                "default": "ollama",
                "ollama": {
                    "binary": None,
                    "model": "qwen3.5:9b",
                    "agent": "claude",
                    "context_length": 32768,
                    "extra_args": [],
                },
            },
        }
        prefs_file.write_text(yaml.dump(prefs))
        monkeypatch.setattr(
            "augur_mcp.infrastructure.local_backends._get_preferences_path",
            lambda: prefs_file,
        )
        return prefs_file

    @pytest.mark.asyncio
    async def test_ready_supported_agent(self, prefs_qwen, monkeypatch):
        """Ollama running, agent in integration list, model pulled → ready."""
        from augur_mcp.infrastructure.local_backends import (
            get_airplane_launch_overrides_impl,
            GetAirplaneLaunchOverridesInput,
        )
        monkeypatch.setattr(sys, "platform", "darwin")
        with patch(
            "augur_mcp.infrastructure.local_backends._detect_ollama",
            return_value={
                "installed": True,
                "version": "0.21.1",
                "binary": "/opt/homebrew/bin/ollama",
                "server_running": True,
                "models": [{"name": "qwen3.5:9b", "size": "6.6 GB"}],
            },
        ), patch(
            "augur_mcp.infrastructure.local_backends.list_ollama_integrations_impl",
            return_value=json.dumps({"integrations": ["claude", "codex", "opencode"]}),
        ):
            result = await get_airplane_launch_overrides_impl(
                GetAirplaneLaunchOverridesInput(agent_id="claude")
            )
            data = json.loads(result)
            assert data["ready"] is True
            assert data["integration_id"] == "claude"
            assert data["model"] == "qwen3.5:9b"
            assert data["launch_argv"] == [
                "/opt/homebrew/bin/ollama", "launch", "claude",
                "--model", "qwen3.5:9b", "--",
            ]

    @pytest.mark.asyncio
    async def test_unsupported_agent(self, prefs_qwen, monkeypatch):
        """gemini not in integration list → reason=unsupported."""
        from augur_mcp.infrastructure.local_backends import (
            get_airplane_launch_overrides_impl,
            GetAirplaneLaunchOverridesInput,
        )
        monkeypatch.setattr(sys, "platform", "darwin")
        with patch(
            "augur_mcp.infrastructure.local_backends._detect_ollama",
            return_value={
                "installed": True, "version": "0.21.1",
                "binary": "/opt/homebrew/bin/ollama",
                "server_running": True,
                "models": [{"name": "qwen3.5:9b", "size": "6.6 GB"}],
            },
        ), patch(
            "augur_mcp.infrastructure.local_backends.list_ollama_integrations_impl",
            return_value=json.dumps({"integrations": ["claude", "codex"]}),
        ):
            result = await get_airplane_launch_overrides_impl(
                GetAirplaneLaunchOverridesInput(agent_id="gemini")
            )
            data = json.loads(result)
            assert data["ready"] is False
            assert data["reason"] == "unsupported"
            assert "gemini" in data["setup_hint"].lower()

    @pytest.mark.asyncio
    async def test_binary_missing_macos(self, prefs_qwen, monkeypatch):
        from augur_mcp.infrastructure.local_backends import (
            get_airplane_launch_overrides_impl,
            GetAirplaneLaunchOverridesInput,
        )
        monkeypatch.setattr(sys, "platform", "darwin")
        with patch(
            "augur_mcp.infrastructure.local_backends._detect_ollama",
            return_value={
                "installed": False, "version": None, "binary": None,
                "server_running": False, "models": [],
            },
        ):
            result = await get_airplane_launch_overrides_impl(
                GetAirplaneLaunchOverridesInput(agent_id="claude")
            )
            data = json.loads(result)
            assert data["ready"] is False
            assert data["reason"] == "binary_missing"
            assert "brew install ollama" in data["setup_hint"]

    @pytest.mark.asyncio
    async def test_binary_missing_windows(self, prefs_qwen, monkeypatch):
        from augur_mcp.infrastructure.local_backends import (
            get_airplane_launch_overrides_impl,
            GetAirplaneLaunchOverridesInput,
        )
        monkeypatch.setattr(sys, "platform", "win32")
        with patch(
            "augur_mcp.infrastructure.local_backends._detect_ollama",
            return_value={
                "installed": False, "version": None, "binary": None,
                "server_running": False, "models": [],
            },
        ):
            result = await get_airplane_launch_overrides_impl(
                GetAirplaneLaunchOverridesInput(agent_id="claude")
            )
            data = json.loads(result)
            assert data["ready"] is False
            assert data["reason"] == "binary_missing"
            assert "ollama.com/download/windows" in data["setup_hint"]

    @pytest.mark.asyncio
    async def test_ollama_not_running(self, prefs_qwen, monkeypatch):
        from augur_mcp.infrastructure.local_backends import (
            get_airplane_launch_overrides_impl,
            GetAirplaneLaunchOverridesInput,
        )
        monkeypatch.setattr(sys, "platform", "darwin")
        with patch(
            "augur_mcp.infrastructure.local_backends._detect_ollama",
            return_value={
                "installed": True, "version": "0.21.1",
                "binary": "/opt/homebrew/bin/ollama",
                "server_running": False, "models": [],
            },
        ):
            result = await get_airplane_launch_overrides_impl(
                GetAirplaneLaunchOverridesInput(agent_id="claude")
            )
            data = json.loads(result)
            assert data["ready"] is False
            assert data["reason"] == "ollama_not_running"
            assert "ollama serve" in data["setup_hint"]

    @pytest.mark.asyncio
    async def test_model_missing(self, prefs_qwen, monkeypatch):
        from augur_mcp.infrastructure.local_backends import (
            get_airplane_launch_overrides_impl,
            GetAirplaneLaunchOverridesInput,
        )
        monkeypatch.setattr(sys, "platform", "darwin")
        with patch(
            "augur_mcp.infrastructure.local_backends._detect_ollama",
            return_value={
                "installed": True, "version": "0.21.1",
                "binary": "/opt/homebrew/bin/ollama",
                "server_running": True,
                "models": [{"name": "llama3.2:3b", "size": "2 GB"}],
            },
        ), patch(
            "augur_mcp.infrastructure.local_backends.list_ollama_integrations_impl",
            return_value=json.dumps({"integrations": ["claude"]}),
        ):
            result = await get_airplane_launch_overrides_impl(
                GetAirplaneLaunchOverridesInput(agent_id="claude")
            )
            data = json.loads(result)
            assert data["ready"] is False
            assert data["reason"] == "model_missing"
            assert "qwen3.5:9b" in data["setup_hint"]
            assert "ollama pull" in data["setup_hint"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Projects/Augur && uv run pytest tests/packages/augur-mcp/tools/test_local_backends.py::TestGetAirplaneLaunchOverrides -v`
Expected: FAIL — `ImportError: cannot import name 'get_airplane_launch_overrides_impl'`.

- [ ] **Step 3: Implement**

Append to `src/mcp/augur_mcp/infrastructure/local_backends.py`:

```python
class GetAirplaneLaunchOverridesInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="allow")
    agent_id: str = Field(..., description="The cliId for the agent (e.g. 'claude').")


def _setup_hint(reason: str, *, model: str | None = None) -> str:
    """Platform-aware setup hint for each failure reason."""
    is_windows = sys.platform == "win32"
    if reason == "binary_missing":
        if is_windows:
            return (
                "Install Ollama from https://ollama.com/download/windows "
                "or run: winget install Ollama.Ollama"
            )
        return "Install Ollama: brew install ollama"
    if reason == "ollama_not_running":
        if is_windows:
            return "Open the Ollama app from Start menu, or run in PowerShell: ollama serve"
        return "Start Ollama: ollama serve"
    if reason == "model_missing":
        cmd = f"ollama pull {model}" if model else "ollama pull <model>"
        if is_windows:
            return f"Pull the model in PowerShell: {cmd}"
        return f"Pull the model: {cmd}"
    return ""


async def get_airplane_launch_overrides_impl(
    params: GetAirplaneLaunchOverridesInput,
) -> str:
    """Determine whether agent_id can be launched locally right now,
    and return either the launch argv or a structured failure with hint.

    Returns one of (as JSON string):
        { "ready": true, "integration_id": str, "model": str,
          "launch_argv": [str, ...] }
        { "ready": false, "reason": "binary_missing"|"ollama_not_running"
                                   |"model_missing", "setup_hint": str }
        { "ready": false, "reason": "unsupported", "setup_hint": str }
    """
    prefs = _load_local_prefs()
    ollama_cfg = {**_OLLAMA_DEFAULTS, **prefs.get("local_backends", {}).get("ollama", {})}
    model = ollama_cfg.get("model") or _OLLAMA_DEFAULTS["model"]

    detection = _detect_ollama()

    if not detection["installed"]:
        return json.dumps(
            {
                "ready": False,
                "reason": "binary_missing",
                "setup_hint": _setup_hint("binary_missing"),
            },
            indent=2,
        )

    if not detection["server_running"]:
        return json.dumps(
            {
                "ready": False,
                "reason": "ollama_not_running",
                "setup_hint": _setup_hint("ollama_not_running"),
            },
            indent=2,
        )

    # Check integration list
    integrations_raw = await list_ollama_integrations_impl(ListOllamaIntegrationsInput())
    integrations: list[str] = json.loads(integrations_raw).get("integrations", [])
    if params.agent_id not in integrations:
        return json.dumps(
            {
                "ready": False,
                "reason": "unsupported",
                "setup_hint": (
                    f"Agent '{params.agent_id}' is not in Ollama's integration list. "
                    f"Switch to one of: {', '.join(integrations) or '(none — Ollama may be too old)'}."
                ),
            },
            indent=2,
        )

    # Check model is pulled
    has_model = any(m["name"] == model for m in detection["models"])
    if not has_model:
        return json.dumps(
            {
                "ready": False,
                "reason": "model_missing",
                "setup_hint": _setup_hint("model_missing", model=model),
            },
            indent=2,
        )

    return json.dumps(
        {
            "ready": True,
            "integration_id": params.agent_id,
            "model": model,
            "launch_argv": [
                detection["binary"], "launch", params.agent_id,
                "--model", model, "--",
            ],
        },
        indent=2,
    )
```

Update `__all__`:

```python
__all__ = [
    "get_local_backend_status_impl",
    "GetLocalBackendStatusInput",
    "toggle_airplane_mode_impl",
    "ToggleAirplaneModeInput",
    "list_ollama_integrations_impl",
    "ListOllamaIntegrationsInput",
    "get_airplane_launch_overrides_impl",
    "GetAirplaneLaunchOverridesInput",
]
```

- [ ] **Step 4: Register the MCP tool**

In `src/mcp/augur_mcp/infrastructure/__init__.py`:

```python
from augur_mcp.infrastructure.local_backends import (
    get_airplane_launch_overrides_impl,
    GetAirplaneLaunchOverridesInput,
)

@mcp.tool(
    name="get-airplane-launch-overrides",
    annotations=tool_annotations(
        {
            "title": "Get Airplane Launch Overrides",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        }
    ),
)
async def get_airplane_launch_overrides(params: GetAirplaneLaunchOverridesInput) -> str:
    """Return launch argv to wrap agent in Ollama, or 'not ready' with a setup hint."""
    return await get_airplane_launch_overrides_impl(params)
```

In `src/mcp/augur_mcp/client_surface.py`, add `"get-airplane-launch-overrides"` to `CURATED_VISIBLE_TOOLS`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd ~/Projects/Augur && uv run pytest tests/packages/augur-mcp/tools/test_local_backends.py::TestGetAirplaneLaunchOverrides -v`
Expected: 6 PASS.

- [ ] **Step 6: Commit**

```bash
git add src/mcp/augur_mcp/infrastructure/local_backends.py \
        src/mcp/augur_mcp/infrastructure/__init__.py \
        src/mcp/augur_mcp/client_surface.py \
        tests/packages/augur-mcp/tools/test_local_backends.py
git commit -m "feat(airplane): add get-airplane-launch-overrides MCP tool

Discriminated union return: ready+launch_argv on success, or
{reason, setup_hint} for binary_missing / ollama_not_running /
model_missing / unsupported. Hints are platform-aware (macOS vs Windows)."
```

---

## Task 4: `/api/airplane` POST endpoint

**Files:**
- Create: `apps/dashboard/app/api/airplane/route.ts`
- Create: `tests/dashboard/api/airplane-route.test.ts`

- [ ] **Step 1: Write the failing test**

Create `tests/dashboard/api/airplane-route.test.ts`:

```typescript
import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("@/lib/mcp/MCPBridge", () => ({
  callMCPTool: vi.fn(),
  extractContextFromRequest: vi.fn(() => ({})),
  MCPBridge: { extractText: (r: { _text?: string }) => r._text ?? "" },
}));

import { POST } from "@/app/api/airplane/route";
import { callMCPTool } from "@/lib/mcp/MCPBridge";

function makeReq(body: unknown): Request {
  return new Request("http://localhost/api/airplane", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

function okResult(payload: unknown) {
  return { isError: false, _text: JSON.stringify(payload) };
}

describe("POST /api/airplane", () => {
  beforeEach(() => {
    vi.mocked(callMCPTool).mockReset();
  });

  it("turns airplane on", async () => {
    vi.mocked(callMCPTool).mockResolvedValue(
      okResult({ success: true, airplane_mode: { enabled: true, forced: true } }) as never,
    );
    const res = await POST(makeReq({ action: "on" }));
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.airplane_mode.enabled).toBe(true);
    expect(callMCPTool).toHaveBeenCalledWith(
      "toggle-airplane-mode",
      { action: "on" },
      expect.anything(),
    );
  });

  it("turns airplane off", async () => {
    vi.mocked(callMCPTool).mockResolvedValue(
      okResult({ success: true, airplane_mode: { enabled: false, forced: false } }) as never,
    );
    const res = await POST(makeReq({ action: "off" }));
    expect(res.status).toBe(200);
  });

  it("toggles when action=toggle", async () => {
    vi.mocked(callMCPTool).mockResolvedValue(
      okResult({ success: true, airplane_mode: { enabled: true, forced: true } }) as never,
    );
    const res = await POST(makeReq({ action: "toggle" }));
    expect(res.status).toBe(200);
  });

  it("returns 400 on malformed action", async () => {
    const res = await POST(makeReq({ action: "INVALID" }));
    expect(res.status).toBe(400);
  });

  it("returns 500 if MCP tool errors", async () => {
    vi.mocked(callMCPTool).mockResolvedValue(
      { isError: true, _text: "prefs file unwritable" } as never,
    );
    const res = await POST(makeReq({ action: "on" }));
    expect(res.status).toBe(500);
    const body = await res.json();
    expect(body.error).toBeTruthy();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/dashboard && pnpm vitest run tests/dashboard/api/airplane-route.test.ts`
Expected: FAIL — `Cannot find module '@/app/api/airplane/route'`.

- [ ] **Step 3: Create the route**

Create `apps/dashboard/app/api/airplane/route.ts` — follows the existing server-side pattern from `apps/dashboard/app/api/mcp/tool/route.ts`:

```typescript
import { NextResponse } from "next/server";
import {
  callMCPTool,
  extractContextFromRequest,
  MCPBridge,
} from "@/lib/mcp/MCPBridge";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const ALLOWED_ACTIONS = new Set(["on", "off", "toggle"] as const);

export async function POST(req: Request): Promise<NextResponse> {
  let body: { action?: string };
  try {
    body = (await req.json()) as { action?: string };
  } catch {
    return NextResponse.json({ error: "invalid JSON body" }, { status: 400 });
  }

  const action = body.action;
  if (!action || !ALLOWED_ACTIONS.has(action as "on" | "off" | "toggle")) {
    return NextResponse.json(
      { error: `action must be one of: on, off, toggle` },
      { status: 400 },
    );
  }

  const ctx = extractContextFromRequest(req);
  const result = await callMCPTool("toggle-airplane-mode", { action }, ctx);
  if (result.isError) {
    const msg = MCPBridge.extractText(result) || "failed to toggle airplane mode";
    return NextResponse.json(
      { error: msg },
      { status: 500 },
    );
  }
  const raw = MCPBridge.extractText(result).trim();
  let payload: unknown = {};
  try { payload = raw ? JSON.parse(raw) : {}; } catch { payload = { raw }; }
  return NextResponse.json(payload);
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/dashboard && pnpm vitest run tests/dashboard/api/airplane-route.test.ts`
Expected: 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/app/api/airplane/route.ts \
        tests/dashboard/api/airplane-route.test.ts
git commit -m "feat(airplane): /api/airplane POST endpoint

Single call site for the dashboard airplane pill, chat-header chip, and
SecurityTab toggle. Wraps toggle-airplane-mode MCP. Validates action."
```

---

## Task 5: CLI start path uses `ollama launch` when airplane is ON

**Files:**
- Modify: `apps/dashboard/app/api/cli/actions.ts`
- Create: `tests/dashboard/api/cli-route-airplane.test.ts`

- [ ] **Step 1: Write the failing test**

Create `tests/dashboard/api/cli-route-airplane.test.ts`:

```typescript
import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("@/lib/mcp/MCPBridge", () => ({
  callMCPTool: vi.fn(),
  extractContextFromRequest: vi.fn(() => ({})),
  MCPBridge: { extractText: (r: { _text?: string }) => r._text ?? "" },
}));

const captured: { argv: string[] | null } = { argv: null };

vi.mock("node-pty", () => ({
  spawn: vi.fn((cmd: string, args: string[]) => {
    captured.argv = [cmd, ...args];
    return { pid: 12345, on: vi.fn(), write: vi.fn(), kill: vi.fn() };
  }),
}));

import { handleStartAction } from "@/app/api/cli/actions";
import { callMCPTool } from "@/lib/mcp/MCPBridge";

function okResult(payload: unknown) {
  return { isError: false, _text: JSON.stringify(payload) };
}

describe("handleStartAction with airplane mode", () => {
  beforeEach(() => {
    vi.mocked(callMCPTool).mockReset();
    captured.argv = null;
  });

  it("rewrites argv to ollama launch when airplane is on and override is ready", async () => {
    vi.mocked(callMCPTool)
      .mockResolvedValueOnce(okResult({ airplane_mode: { enabled: true } }) as never)
      .mockResolvedValueOnce(okResult({
        ready: true,
        integration_id: "claude",
        model: "qwen3.5:9b",
        launch_argv: [
          "/opt/homebrew/bin/ollama", "launch", "claude",
          "--model", "qwen3.5:9b", "--",
        ],
      }) as never);
    const res = await handleStartAction("claude", { airplaneMode: true } as never);
    expect(res.status).toBe(200);
    expect(captured.argv?.slice(0, 5)).toEqual([
      "/opt/homebrew/bin/ollama", "launch", "claude",
      "--model", "qwen3.5:9b",
    ]);
  });

  it("returns 409 with setup_hint when override is not ready", async () => {
    vi.mocked(callMCPTool)
      .mockResolvedValueOnce(okResult({ airplane_mode: { enabled: true } }) as never)
      .mockResolvedValueOnce(okResult({
        ready: false,
        reason: "ollama_not_running",
        setup_hint: "Start Ollama: ollama serve",
      }) as never);
    const res = await handleStartAction("claude", { airplaneMode: true } as never);
    expect(res.status).toBe(409);
    const body = await res.json();
    expect(body.setup_hint).toContain("ollama serve");
  });

  it("ignores body.airplaneMode when prefs say off", async () => {
    vi.mocked(callMCPTool).mockResolvedValueOnce(
      okResult({ airplane_mode: { enabled: false } }) as never,
    );
    const res = await handleStartAction("claude", { airplaneMode: true } as never);
    expect(res.status).toBe(200);
    expect(captured.argv?.[0]).not.toBe("/opt/homebrew/bin/ollama");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/dashboard && pnpm vitest run tests/dashboard/api/cli-route-airplane.test.ts`
Expected: FAIL — assertions fail because the existing handler doesn't call `get-airplane-launch-overrides`.

- [ ] **Step 3: Modify `handleStartAction` in `actions.ts`**

In `apps/dashboard/app/api/cli/actions.ts`, replace the `airplaneMode` handling inside `handleStartAction` (around line 196-232). Add the import at the top of the file:

```typescript
import {
  callMCPTool,
  extractContextFromRequest,
  MCPBridge,
} from "@/lib/mcp/MCPBridge";
```

Helper to parse MCP responses (place near the existing helpers):

```typescript
async function callMcpJson<T>(tool: string, args: Record<string, unknown>): Promise<T> {
  const result = await callMCPTool(tool, args, {});
  if (result.isError) {
    throw new Error(MCPBridge.extractText(result) || `MCP tool failed: ${tool}`);
  }
  const raw = MCPBridge.extractText(result).trim();
  return raw ? (JSON.parse(raw) as T) : ({} as T);
}
```

New flow inside `handleStartAction`:

```typescript
// Read canonical airplane state from preferences (server is source of truth).
let canonicalAirplane = false;
try {
  const status = await callMcpJson<{
    airplane_mode?: { enabled?: boolean };
  }>("get-local-backend-status", {});
  canonicalAirplane = status.airplane_mode?.enabled === true;
} catch {
  canonicalAirplane = body.airplaneMode === true; // fall back to body hint
}

if (canonicalAirplane) {
  type Override =
    | {
        ready: true;
        integration_id: string;
        model: string;
        launch_argv: string[];
      }
    | { ready: false; reason: string; setup_hint: string };
  const override = await callMcpJson<Override>("get-airplane-launch-overrides", {
    agent_id: cliId,
  });

  if (!override.ready) {
    return NextResponse.json(
      {
        error: `Cannot start ${cliId} in airplane mode: ${override.reason}`,
        setup_hint: override.setup_hint,
        reason: override.reason,
      },
      { status: 409 },
    );
  }

  const config = getCliConfigOrThrow(resolveConfigKey(cliId));
  const originalArgs = (config.cmd as string[]).slice(1);
  // Strip cloud-only flags as a safety net before wrapping with ollama launch.
  const filtered = originalArgs.filter(
    (arg: string) => !AUTO_APPROVE_FLAGS.has(arg),
  );
  const launchArgv = [...override.launch_argv, ...filtered];

  const cwd = config.cwd === "." ? AUGUR_ROOT : config.cwd || AUGUR_ROOT;
  const env = buildCliSpawnEnv(config, currentPage, themeMode);

  const ptyProcess = spawnPtyOrThrow(
    cliId,
    launchArgv[0],
    launchArgv.slice(1),
    cwd,
    env,
  );
  // continue to the same post-spawn handler-attach + JSON-return logic the
  // existing non-airplane branch uses (refactor those steps into a helper
  // so both branches share them)
}
// Else: existing non-airplane code path unchanged
```

Refactor so the post-spawn handler-attach and `NextResponse.json` are shared between the two branches (single helper, two argv computations).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/dashboard && pnpm vitest run tests/dashboard/api/cli-route-airplane.test.ts`
Expected: 3 PASS.

- [ ] **Step 5: Run existing CLI route tests for regressions**

Run: `cd apps/dashboard && pnpm vitest run tests/dashboard/api/cli`
Expected: previously-passing tests still PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/dashboard/app/api/cli/actions.ts \
        tests/dashboard/api/cli-route-airplane.test.ts
git commit -m "feat(airplane): rewrite spawn argv to 'ollama launch <agent>' when on

handleStartAction now reads canonical airplane state from preferences
(via get-local-backend-status), then calls get-airplane-launch-overrides.
On ready=true, the spawn argv becomes the ollama launch wrapper plus the
agent's original args. On ready=false, returns 409 with the setup_hint."
```

---

## Task 6: Refactor `airplaneModeStore` to React-Query backed hook

**Files:**
- Modify: `apps/dashboard/lib/stores/airplaneModeStore.ts`
- (consumers: `FloatingChat.tsx`, `SecurityTab.tsx` already use `useAirplaneModeStore` — interface stays compatible)

- [ ] **Step 1: Replace localStorage logic with `useMcpQuery`**

Replace the entire content of `apps/dashboard/lib/stores/airplaneModeStore.ts`:

```typescript
import { useCallback } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useMcpQuery } from "@/lib/mcp/useMcpQuery";

const CACHE_KEY = "airplane-status";

/**
 * Backwards-compatible hook for code that previously read the localStorage-
 * backed Zustand store. Source of truth is now preferences.yaml via the
 * get-local-backend-status MCP tool. All consumers share CACHE_KEY so a
 * single invalidation re-renders pill, chip, and SecurityTab.
 */
export function useAirplaneModeStore(): {
  airplaneMode: boolean;
  setAirplaneMode: (enabled: boolean) => Promise<void>;
  toggleAirplaneMode: () => Promise<void>;
} {
  const queryClient = useQueryClient();
  const { data } = useMcpQuery<{ airplane_mode?: { enabled?: boolean } }>(
    CACHE_KEY,
    "get-local-backend-status",
    "static",
    { refetchInterval: 5000 },
  );

  const airplaneMode = data?.airplane_mode?.enabled === true;

  const post = useCallback(
    async (action: "on" | "off" | "toggle") => {
      await fetch("/api/airplane", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action }),
      });
      await queryClient.invalidateQueries({ queryKey: [CACHE_KEY] });
    },
    [queryClient],
  );

  const setAirplaneMode = useCallback(
    async (enabled: boolean) => post(enabled ? "on" : "off"),
    [post],
  );

  const toggleAirplaneMode = useCallback(() => post("toggle"), [post]);

  return { airplaneMode, setAirplaneMode, toggleAirplaneMode };
}
```

- [ ] **Step 2: Run dashboard typecheck**

Run: `cd apps/dashboard && pnpm typecheck` (or `pnpm tsc --noEmit`)
Expected: PASS. If any consumer broke, update it. The interface (`airplaneMode`, `setAirplaneMode(boolean)`, `toggleAirplaneMode()`) is preserved — but `setAirplaneMode` and `toggleAirplaneMode` are now async. If a consumer chained `.then()`, that works; if it relied on synchronous return, the call site must `await`.

- [ ] **Step 3: Update FloatingChat airplane-restart effect**

In `apps/dashboard/features/components/FloatingChat.tsx` line 148-158, the existing effect runs `stopCli` then `startCli` when `airplaneMode` flips. No changes required — the hook still returns a boolean. Just verify it still triggers when the React-Query cache changes.

- [ ] **Step 4: Manual smoke check**

Run dashboard with `/dev-build`. Open Settings → Security. Click the existing airplane button (still mounted via `useAirplaneModeStore`). Verify:
- Toggle reflects `preferences.yaml` after page refresh (no localStorage cache leakage).
- POST to `/api/airplane` is sent (DevTools → Network).
- The state survives a hard refresh.

If the smoke check fails (state desyncs after refresh), STOP and debug — don't continue to UI tasks.

- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/lib/stores/airplaneModeStore.ts
git commit -m "refactor(airplane): replace localStorage Zustand store with React-Query hook

Single source of truth is preferences.yaml via get-local-backend-status MCP.
All consumers share cache key 'airplane-status' so one invalidation re-renders
pill, chip, and SecurityTab in lockstep. Setters now POST to /api/airplane."
```

---

## Task 7: `AirplanePill` component

**Files:**
- Create: `apps/dashboard/components/shared/AirplanePill.tsx`
- Modify: `apps/dashboard/app/layout.tsx` (mount in sidebar `<aside>`)
- Create: `tests/dashboard/components/AirplanePill.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `tests/dashboard/components/AirplanePill.test.tsx`:

```typescript
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

const mockData = vi.fn();
vi.mock("@/lib/mcp/useMcpQuery", () => ({
  useMcpQuery: () => ({ data: mockData() }),
}));
const mockInvalidate = vi.fn();
vi.mock("@tanstack/react-query", () => ({
  useQueryClient: () => ({ invalidateQueries: mockInvalidate }),
}));
global.fetch = vi.fn(() => Promise.resolve({ ok: true } as Response));

import AirplanePill from "@/components/shared/AirplanePill";

describe("AirplanePill", () => {
  beforeEach(() => {
    mockData.mockReset();
    mockInvalidate.mockReset();
    (global.fetch as any).mockClear();
  });

  it("renders OFF state", () => {
    mockData.mockReturnValue({
      airplane_mode: { enabled: false },
      ollama: { ready: true, configured_model: "qwen3.5:9b" },
    });
    render(<AirplanePill />);
    expect(screen.getByRole("button", { name: /airplane/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /off/i })).toBeInTheDocument();
  });

  it("renders ON-ready state with model name", () => {
    mockData.mockReturnValue({
      airplane_mode: { enabled: true },
      ollama: { ready: true, configured_model: "qwen3.5:9b" },
    });
    render(<AirplanePill />);
    expect(screen.getByText(/qwen3\.5:9b/i)).toBeInTheDocument();
  });

  it("renders ON-not-ready state when airplane on but ollama not ready", () => {
    mockData.mockReturnValue({
      airplane_mode: { enabled: true },
      ollama: { ready: false, configured_model: "qwen3.5:9b" },
    });
    render(<AirplanePill />);
    expect(screen.getByText(/setup needed/i)).toBeInTheDocument();
  });

  it("clicking POSTs to /api/airplane and invalidates cache", async () => {
    mockData.mockReturnValue({
      airplane_mode: { enabled: false },
      ollama: { ready: true, configured_model: "qwen3.5:9b" },
    });
    render(<AirplanePill />);
    fireEvent.click(screen.getByRole("button"));
    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        "/api/airplane",
        expect.objectContaining({ method: "POST" }),
      );
      expect(mockInvalidate).toHaveBeenCalledWith({ queryKey: ["airplane-status"] });
    });
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/dashboard && pnpm vitest run tests/dashboard/components/AirplanePill.test.tsx`
Expected: FAIL — `Cannot find module '@/components/shared/AirplanePill'`.

- [ ] **Step 3: Create the component**

Create `apps/dashboard/components/shared/AirplanePill.tsx`:

```typescript
"use client";

import { Plane, Cloud } from "lucide-react";
import { useCallback } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useMcpQuery } from "@/lib/mcp/useMcpQuery";

const CACHE_KEY = "airplane-status";

interface BackendStatus {
  airplane_mode?: { enabled?: boolean };
  ollama?: { ready?: boolean; configured_model?: string };
}

export default function AirplanePill() {
  const queryClient = useQueryClient();
  const { data } = useMcpQuery<BackendStatus>(
    CACHE_KEY,
    "get-local-backend-status",
    "static",
    { refetchInterval: 5000 },
  );

  const enabled = data?.airplane_mode?.enabled === true;
  const ready = data?.ollama?.ready === true;
  const model = data?.ollama?.configured_model ?? "";

  const onClick = useCallback(async () => {
    await fetch("/api/airplane", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "toggle" }),
    });
    await queryClient.invalidateQueries({ queryKey: [CACHE_KEY] });
  }, [queryClient]);

  // Visual state
  let label: string;
  let toneClass: string;
  if (!enabled) {
    label = "Airplane · OFF";
    toneClass =
      "border-[var(--border-color)] text-[var(--text-muted)] bg-[var(--bg-card)]";
  } else if (ready) {
    label = `✈ Airplane · ${model || "local"}`;
    toneClass =
      "border-[var(--accent-warning)]/40 text-[var(--accent-warning)] bg-[var(--accent-warning)]/10";
  } else {
    label = "✈ Airplane · setup needed";
    toneClass =
      "border-[var(--accent-danger)]/40 text-[var(--accent-danger)] bg-[var(--accent-danger)]/10";
  }

  const Icon = enabled ? Plane : Cloud;

  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={`Airplane mode is ${enabled ? "on" : "off"}. Click to toggle.`}
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-xs font-medium transition-colors hover:brightness-110 ${toneClass}`}
    >
      <Icon className="w-3.5 h-3.5" />
      <span className="truncate max-w-[10rem]">{label}</span>
    </button>
  );
}
```

- [ ] **Step 4: Mount in the sidebar**

In `apps/dashboard/app/layout.tsx`, near `<BrainLogo />` inside the desktop `<aside>` (line ~114):

```tsx
import AirplanePill from "../components/shared/AirplanePill";

// ... inside the desktop <aside>:
<aside className="hidden md:flex w-64 border-r border-[var(--border-color)] p-6 flex-col gap-4 bg-[var(--bg-sidebar)] backdrop-blur-md">
  <BrainLogo />
  <AirplanePill />
  <SidebarNav />
</aside>
```

Also mount it in `MobileSidebar` (look for the same `BrainLogo` placement and add `<AirplanePill />` next to it) so mobile users can toggle.

- [ ] **Step 5: Run test to verify it passes**

Run: `cd apps/dashboard && pnpm vitest run tests/dashboard/components/AirplanePill.test.tsx`
Expected: 4 PASS.

- [ ] **Step 6: Browser smoke**

Per project rule 28 (client-side verification): start `/dev-build`, open the dashboard, verify:
- Pill appears in sidebar above "Brain", "Career", etc.
- Click toggles state; verify the pill label changes after the React-Query refetch (5s).
- Hard refresh — state persists from `preferences.yaml`.
- No console errors.

If the pill flashes or never settles, STOP and inspect React-Query staleness/refetch settings.

- [ ] **Step 7: Commit**

```bash
git add apps/dashboard/components/shared/AirplanePill.tsx \
        apps/dashboard/app/layout.tsx \
        apps/dashboard/components/MobileSidebar.tsx \
        tests/dashboard/components/AirplanePill.test.tsx
git commit -m "feat(airplane): AirplanePill in sidebar (canonical toggle)

Three visual states: OFF (gray cloud), ON-ready (amber + model name),
ON-not-ready (red + setup-needed). Click POSTs /api/airplane toggle
and invalidates the shared 'airplane-status' query key."
```

---

## Task 8: ChatHeader mirror chip + transition system messages

**Files:**
- Modify: `apps/dashboard/features/components/chat/ChatHeader.tsx`
- Modify: `apps/dashboard/features/hooks/useCliChat.ts`
- Create: `tests/dashboard/components/ChatHeader-airplane-chip.test.tsx`
- Create: `tests/dashboard/features/hooks/useCliChat-airplane-transitions.test.ts`

- [ ] **Step 1: Write failing tests for the chip**

Create `tests/dashboard/components/ChatHeader-airplane-chip.test.tsx`:

```typescript
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";

const mockData = vi.fn();
vi.mock("@/lib/mcp/useMcpQuery", () => ({
  useMcpQuery: () => ({ data: mockData() }),
}));

import { ChatHeaderAirplaneChip } from "@/features/components/chat/ChatHeader";

describe("ChatHeaderAirplaneChip", () => {
  it("does not render when airplane is off", () => {
    mockData.mockReturnValue({ airplane_mode: { enabled: false } });
    const { container } = render(
      <ChatHeaderAirplaneChip cliId="claude" supportedAgents={["claude"]} />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("shows local label when airplane on and agent supported", () => {
    mockData.mockReturnValue({
      airplane_mode: { enabled: true },
      ollama: { ready: true, configured_model: "qwen3.5:9b" },
    });
    render(
      <ChatHeaderAirplaneChip cliId="claude" supportedAgents={["claude"]} />,
    );
    expect(screen.getByText(/local/i)).toBeInTheDocument();
  });

  it("shows unsupported warning when agent not in integration list", () => {
    mockData.mockReturnValue({
      airplane_mode: { enabled: true },
      ollama: { ready: true, configured_model: "qwen3.5:9b" },
    });
    render(
      <ChatHeaderAirplaneChip cliId="gemini" supportedAgents={["claude"]} />,
    );
    expect(screen.getByText(/not local-capable/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Write failing test for transition system messages**

Create `tests/dashboard/features/hooks/useCliChat-airplane-transitions.test.ts`:

```typescript
import { describe, it, expect, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";

const mockAirplane = { current: false };
vi.mock("@/lib/stores/airplaneModeStore", () => ({
  useAirplaneModeStore: () => ({
    airplaneMode: mockAirplane.current,
    setAirplaneMode: vi.fn(),
    toggleAirplaneMode: vi.fn(),
  }),
}));

import { useCliChat } from "@/features/hooks/useCliChat";

describe("useCliChat airplane transitions", () => {
  it("appends transition system message when airplane flips ON during running session", async () => {
    mockAirplane.current = false;
    const { result, rerender } = renderHook(() => useCliChat());
    // simulate running session with cliProcess.status === "running"
    act(() => {
      // expose helper or directly set via store — implementation can use
      // a useEffect that watches airplaneMode and pushes message
    });
    mockAirplane.current = true;
    rerender();
    const lastSystem = result.current.messages
      .filter((m) => m.role === "system")
      .slice(-1)[0];
    expect(lastSystem?.content).toMatch(/airplane mode on.*switching/i);
  });

  it("appends transition system message when airplane flips OFF", async () => {
    mockAirplane.current = true;
    const { result, rerender } = renderHook(() => useCliChat());
    mockAirplane.current = false;
    rerender();
    const lastSystem = result.current.messages
      .filter((m) => m.role === "system")
      .slice(-1)[0];
    expect(lastSystem?.content).toMatch(/airplane mode off.*switching/i);
  });

  it("renders 409 setup_hint as a monospaced inline system message", async () => {
    mockAirplane.current = true;
    const fetchSpy = vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          error: "Cannot start claude in airplane mode: ollama_not_running",
          setup_hint: "Start Ollama: ollama serve",
          reason: "ollama_not_running",
        }),
        { status: 409 },
      ),
    );
    const { result } = renderHook(() => useCliChat());
    await act(async () => {
      await result.current.startCli("claude" as any);
    });
    const lastSystem = result.current.messages
      .filter((m) => m.role === "system")
      .slice(-1)[0];
    expect(lastSystem?.content).toContain("ollama serve");
    fetchSpy.mockRestore();
  });
});
```

- [ ] **Step 3: Run tests to verify they fail**

Run:
```bash
cd apps/dashboard && pnpm vitest run \
  tests/dashboard/components/ChatHeader-airplane-chip.test.tsx \
  tests/dashboard/features/hooks/useCliChat-airplane-transitions.test.ts
```
Expected: FAIL — exports don't exist; transition logic is not implemented.

- [ ] **Step 4: Add `ChatHeaderAirplaneChip` export to `ChatHeader.tsx`**

In `apps/dashboard/features/components/chat/ChatHeader.tsx`, add:

```typescript
import { useMcpQuery } from "@/lib/mcp/useMcpQuery";
import { Plane } from "lucide-react";

export function ChatHeaderAirplaneChip(props: {
  cliId: string;
  supportedAgents: string[];
}) {
  const { data } = useMcpQuery<{
    airplane_mode?: { enabled?: boolean };
    ollama?: { ready?: boolean; configured_model?: string };
  }>("airplane-status", "get-local-backend-status", "static", {
    refetchInterval: 5000,
  });

  if (!data?.airplane_mode?.enabled) return null;

  const supported = props.supportedAgents.includes(props.cliId);
  if (!supported) {
    return (
      <span
        className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[10px] font-semibold border border-[var(--accent-danger)]/40 text-[var(--accent-danger)] bg-[var(--accent-danger)]/10"
        title={`${props.cliId} is not in Ollama's integration list`}
      >
        <Plane className="w-3 h-3" />
        <span>{props.cliId}: not local-capable</span>
      </span>
    );
  }

  const label = data?.ollama?.ready
    ? `local · ${data.ollama.configured_model ?? ""}`
    : "local · setup needed";
  const tone = data?.ollama?.ready
    ? "border-[var(--accent-warning)]/40 text-[var(--accent-warning)] bg-[var(--accent-warning)]/10"
    : "border-[var(--accent-danger)]/40 text-[var(--accent-danger)] bg-[var(--accent-danger)]/10";

  return (
    <span
      className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[10px] font-semibold border ${tone}`}
      title={`Airplane mode active. Backend: ${data?.ollama?.configured_model ?? "local"}.`}
    >
      <Plane className="w-3 h-3" />
      <span>{label}</span>
    </span>
  );
}
```

Mount it inside the existing header layout (next to the CLI label and online dot, around the place where `cliLabel` is rendered). Pass `supportedAgents` from a parent fetch:

```typescript
const { data: integrationsData } = useMcpQuery<{ integrations: string[] }>(
  "ollama-integrations",
  "list-ollama-integrations",
  "static",
  { refetchInterval: 60000 },
);
const supportedAgents = integrationsData?.integrations ?? [];
// ...
<ChatHeaderAirplaneChip cliId={cliProcess?.cliId ?? "claude"} supportedAgents={supportedAgents} />
```

- [ ] **Step 5: Add transition system messages in `useCliChat.ts`**

In `apps/dashboard/features/hooks/useCliChat.ts`, near where the hook reads from `useAirplaneModeStore` (or where messages are tracked), add a `useEffect` that watches `airplaneMode` and appends a system message **before** the FloatingChat's existing stop/start effect runs:

```typescript
import { useAirplaneModeStore } from "@/lib/stores/airplaneModeStore";

// inside useCliChat:
const { airplaneMode } = useAirplaneModeStore();
const prevAirplaneRef = useRef(airplaneMode);

useEffect(() => {
  if (prevAirplaneRef.current === airplaneMode) return;
  // Only emit when a session is running — silent toggle when no CLI active
  if (!cliProcess || cliProcess.status !== "running") {
    prevAirplaneRef.current = airplaneMode;
    return;
  }
  const cliId = cliProcess.cliId;
  const transitionMsg = {
    role: "system" as const,
    content: airplaneMode
      ? `✈ Airplane mode ON — switching ${cliId} → local model`
      : `✈ Airplane mode OFF — switching ${cliId} → cloud`,
    timestamp: Date.now(),
  };
  setMessages((prev) => [...prev, transitionMsg]);
  persistMessage(transitionMsg);
  prevAirplaneRef.current = airplaneMode;
}, [airplaneMode, cliProcess, persistMessage]);
```

This effect runs **before** `FloatingChat.tsx`'s line 148-158 effect because it's declared in the hook (parent in the data-flow chain). React runs effects in declaration order across components in the same render cycle, but to make ordering explicit we move the transition message into the hook (parent owns the message log).

In `useCliChat.startCli`, when `/api/cli` returns 409, render the `setup_hint`:

```typescript
if (res.status === 409) {
  const data = await safeJson<{ error?: string; setup_hint?: string; reason?: string }>(res);
  setCliProcess({ cliId, status: "error" });
  const hint = data?.setup_hint ?? "";
  const isShellHint = /^\s*(brew|ollama|winget|run)/i.test(hint);
  const errorMsg = {
    role: "system" as const,
    content: isShellHint
      ? `${data?.error ?? "Cannot start agent"}\n\n\`\`\`\n${hint}\n\`\`\``
      : `${data?.error ?? "Cannot start agent"}\n\n${hint}`,
    timestamp: Date.now(),
  };
  setMessages((prev) => [...prev, errorMsg]);
  persistMessage(errorMsg);
  return;
}
```

- [ ] **Step 6: Run tests to verify they pass**

Run:
```bash
cd apps/dashboard && pnpm vitest run \
  tests/dashboard/components/ChatHeader-airplane-chip.test.tsx \
  tests/dashboard/features/hooks/useCliChat-airplane-transitions.test.ts
```
Expected: 6 PASS.

- [ ] **Step 7: Browser smoke**

Open chat, start a CLI, click the AirplanePill to flip state. Verify:
- Chat history shows: prior message → "✈ Airplane mode ON — switching claude → local model" → CLI restart messages.
- Chat header shows the chip with model name when airplane is on.
- Stopping Ollama and clicking again shows the "setup needed" red chip.

- [ ] **Step 8: Commit**

```bash
git add apps/dashboard/features/components/chat/ChatHeader.tsx \
        apps/dashboard/features/hooks/useCliChat.ts \
        tests/dashboard/components/ChatHeader-airplane-chip.test.tsx \
        tests/dashboard/features/hooks/useCliChat-airplane-transitions.test.ts
git commit -m "feat(airplane): chat-header chip + transition system messages

ChatHeaderAirplaneChip mirrors AirplanePill state. Three visual states:
local-ready (amber + model), local-setup-needed (red), unsupported-agent
(red + agent name). Inline system message appended to chat history when
airplane flips during a running session, and 409 setup_hints are rendered
as monospace blocks for copy-paste."
```

---

## Task 9: Settings → Security "Local backend" subsection

**Files:**
- Modify: `apps/dashboard/app/settings/tabs/SecurityTab.tsx`
- Create: `tests/dashboard/settings/SecurityTab-local-backend.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `tests/dashboard/settings/SecurityTab-local-backend.test.tsx`:

```typescript
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

const mockData = vi.fn();
vi.mock("@/lib/mcp/useMcpQuery", () => ({
  useMcpQuery: () => ({ data: mockData(), loading: false, refetch: vi.fn() }),
}));
const mockMcpCall = vi.fn();
vi.mock("@/lib/mcp/client", () => ({ mcpCall: (...a: unknown[]) => mockMcpCall(...a) }));
vi.mock("@/hooks/useActionRunner", () => ({
  useActionRunner: () => ({ runAction: vi.fn(), isExecuting: false }),
}));

import SecurityTab from "@/app/settings/tabs/SecurityTab";

describe("SecurityTab — Local backend subsection", () => {
  beforeEach(() => {
    mockData.mockReset();
    mockMcpCall.mockReset();
  });

  it("renders detected ollama path and model dropdown", () => {
    mockData.mockReturnValue({
      airplane_mode: { enabled: false },
      ollama: {
        installed: true,
        binary: "/opt/homebrew/bin/ollama",
        configured_model: "qwen3.5:9b",
        models: [
          { name: "qwen3.5:9b", size: "6.6 GB" },
          { name: "llama3.2:3b", size: "2.0 GB" },
        ],
      },
    });
    render(<SecurityTab />);
    expect(screen.getByText("/opt/homebrew/bin/ollama")).toBeInTheDocument();
    const select = screen.getByLabelText(/local model/i) as HTMLSelectElement;
    expect(select.value).toBe("qwen3.5:9b");
    expect(within(select).getByText("llama3.2:3b")).toBeInTheDocument();
  });

  it("changing model dispatches update-preference", async () => {
    mockData.mockReturnValue({
      airplane_mode: { enabled: false },
      ollama: {
        installed: true,
        binary: "/opt/homebrew/bin/ollama",
        configured_model: "qwen3.5:9b",
        models: [
          { name: "qwen3.5:9b", size: "6.6 GB" },
          { name: "llama3.2:3b", size: "2.0 GB" },
        ],
      },
    });
    render(<SecurityTab />);
    const select = screen.getByLabelText(/local model/i);
    fireEvent.change(select, { target: { value: "llama3.2:3b" } });
    await waitFor(() => {
      expect(mockMcpCall).toHaveBeenCalledWith(
        "update-preference",
        expect.objectContaining({
          key: "local_backends.ollama.model",
          value: "llama3.2:3b",
        }),
      );
    });
  });

  it("agent compatibility matrix lists supported agents with checks", () => {
    mockData.mockReturnValue({
      airplane_mode: { enabled: false },
      ollama: { installed: true, binary: "/opt/homebrew/bin/ollama" },
      integrations: ["claude", "codex", "opencode", "copilot"],
    });
    render(<SecurityTab />);
    expect(screen.getByText("claude")).toBeInTheDocument();
    expect(screen.getByText("codex")).toBeInTheDocument();
    expect(screen.getByText(/gemini/i)).toBeInTheDocument(); // even if unsupported
  });
});
// note: import within from @testing-library/react at top
```

(Add `import { within } from "@testing-library/react";` at the top.)

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/dashboard && pnpm vitest run tests/dashboard/settings/SecurityTab-local-backend.test.tsx`
Expected: FAIL — the existing SecurityTab doesn't render the local backend dropdown or compatibility matrix.

- [ ] **Step 3: Replace the airplane block in `SecurityTab.tsx` with the Local backend subsection**

In `apps/dashboard/app/settings/tabs/SecurityTab.tsx`, replace the existing "Execution Safety / Airplane Mode" `<section>` (around lines 354-389) with:

```tsx
{/* Local Backend Section */}
<section>
  <div className="flex items-center gap-3 mb-4">
    <Plane className="w-5 h-5 text-[var(--accent-warning)]" />
    <div>
      <h2 className="text-lg font-semibold text-[var(--text-primary)]">
        Local Backend
      </h2>
      <p className="text-sm text-[var(--text-secondary)]">
        Configure the local Ollama model used in airplane mode.
      </p>
    </div>
  </div>

  <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl p-5 space-y-4">
    {/* Detected path */}
    <div>
      <label className="block text-xs font-medium text-[var(--text-secondary)] mb-1">
        Ollama binary
      </label>
      <div className="text-sm font-mono text-[var(--text-primary)]">
        {ollamaStatus?.installed
          ? ollamaStatus.binary
          : "Not detected. Install Ollama to enable airplane mode."}
      </div>
    </div>

    {/* Model dropdown */}
    {ollamaStatus?.installed && (
      <div>
        <label
          htmlFor="local-model-select"
          className="block text-xs font-medium text-[var(--text-secondary)] mb-1"
        >
          Local model
        </label>
        <select
          id="local-model-select"
          value={ollamaStatus.configured_model ?? ""}
          onChange={(e) => handleModelChange(e.target.value)}
          className="w-full px-3 py-2 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border-color)] text-sm"
        >
          {(ollamaStatus.models ?? []).map((m) => (
            <option key={m.name} value={m.name}>
              {m.name} ({m.size})
            </option>
          ))}
        </select>
      </div>
    )}

    {/* Test connection */}
    {ollamaStatus?.installed && (
      <button
        type="button"
        onClick={handleTestConnection}
        className="text-sm px-3 py-1.5 rounded-lg border border-[var(--border-color)] hover:bg-[var(--bg-hover)]"
      >
        Test connection
      </button>
    )}
    {testResult && (
      <div className="text-xs">
        {testResult.ok ? "✓ Ready" : `✗ ${testResult.error}`}
      </div>
    )}

    {/* Existing toggle preserved as redundant control */}
    <div className="flex items-center justify-between pt-2 border-t border-[var(--border-color)]">
      <span className="text-sm text-[var(--text-primary)]">
        Airplane mode (current: {airplaneMode ? "ON" : "OFF"})
      </span>
      <Button variant={airplaneMode ? "outline" : "default"} onClick={toggleAirplaneMode}>
        {airplaneMode ? "Turn OFF" : "Turn ON"}
      </Button>
    </div>
  </div>

  {/* Agent compatibility matrix */}
  <div className="mt-4 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl p-5">
    <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-2">
      Agent compatibility
    </h3>
    <p className="text-xs text-[var(--text-muted)] mb-3">
      Which CLI agents can run through Ollama in airplane mode.
    </p>
    <ul className="space-y-1 text-sm">
      {(integrationsData?.integrations ?? []).map((id) => (
        <li key={id} className="flex items-center gap-2 text-[var(--text-primary)]">
          <CheckCircle2 className="w-4 h-4 text-[var(--accent-success)]" />
          <span>{id}</span>
        </li>
      ))}
      {/* Show known unsupported agents with explanation */}
      {["gemini", "cursor-cli"].map((id) => (
        <li key={id} className="flex items-center gap-2 text-[var(--text-muted)]" title="Not in Ollama integration list">
          <AlertCircle className="w-4 h-4 text-[var(--text-muted)]" />
          <span>{id} <span className="text-xs">(not local-capable in v1)</span></span>
        </li>
      ))}
    </ul>
  </div>
</section>
```

Add the supporting state and handlers near the other `useState`/`useMcpQuery` declarations:

```typescript
const { data: ollamaStatus } = useMcpQuery<{
  airplane_mode?: { enabled?: boolean };
  ollama?: {
    installed: boolean;
    binary?: string;
    configured_model?: string;
    models?: Array<{ name: string; size: string }>;
  };
}>("airplane-status", "get-local-backend-status", "static", { refetchInterval: 5000 });

const { data: integrationsData } = useMcpQuery<{ integrations: string[] }>(
  "ollama-integrations",
  "list-ollama-integrations",
  "static",
  { refetchInterval: 60000 },
);

const [testResult, setTestResult] = useState<{ ok: boolean; error?: string } | null>(null);

const handleModelChange = useCallback(async (model: string) => {
  await mcpCall("update-preference", {
    key: "local_backends.ollama.model",
    value: model,
  });
  // status query will refetch on its interval
}, []);

const handleTestConnection = useCallback(async () => {
  try {
    const r = await mcpCall<{ ollama?: { ready?: boolean } }>(
      "get-local-backend-status",
      {},
    );
    setTestResult({ ok: r.ollama?.ready === true, error: r.ollama?.ready ? undefined : "not ready" });
  } catch (e) {
    setTestResult({ ok: false, error: e instanceof Error ? e.message : "unknown" });
  }
}, []);
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/dashboard && pnpm vitest run tests/dashboard/settings/SecurityTab-local-backend.test.tsx`
Expected: 3 PASS.

- [ ] **Step 5: Run existing SecurityTab tests for regressions**

Run: `cd apps/dashboard && pnpm vitest run tests/dashboard/settings/SecurityTab.test.tsx`
Expected: existing tests PASS.

- [ ] **Step 6: Browser smoke**

Open Settings → Security. Verify:
- Local Backend subsection appears with detected ollama path.
- Model dropdown lists pulled models; changing it persists across refresh.
- Test connection button shows ✓ Ready when Ollama is up, ✗ otherwise.
- Agent compatibility matrix shows the integration list with check marks; gemini/cursor-cli show as unsupported.

- [ ] **Step 7: Commit**

```bash
git add apps/dashboard/app/settings/tabs/SecurityTab.tsx \
        tests/dashboard/settings/SecurityTab-local-backend.test.tsx
git commit -m "feat(airplane): SecurityTab Local backend + compatibility matrix

Replaces lone airplane button with a Local Backend panel: detected ollama
path, model dropdown from get-local-backend-status, test-connection button,
and an agent compatibility matrix listing Ollama-supported integrations
plus known-unsupported agents (gemini, cursor-cli) with explanations.
Existing toggle preserved as a redundant control."
```

---

## Task 10: End-to-end smoke test (gated)

**Files:**
- Create: `tests/e2e/airplane-mode.spec.ts`

- [ ] **Step 1: Write the gated smoke test**

Create `tests/e2e/airplane-mode.spec.ts`:

```typescript
import { test, expect } from "@playwright/test";

const E2E_GATE = process.env.AUGUR_E2E_OLLAMA === "1";

test.describe("airplane mode end-to-end", () => {
  test.skip(!E2E_GATE, "Set AUGUR_E2E_OLLAMA=1 to run (requires running Ollama with model pulled)");

  test("happy path — toggle on, start claude, see model in chip", async ({ page }) => {
    await page.goto("http://localhost:3000");
    const pill = page.getByRole("button", { name: /airplane/i }).first();
    await pill.click();
    await expect(pill).toContainText(/qwen|llama|gpt-oss/i, { timeout: 8000 });

    // Open chat and start claude
    await page.getByRole("button", { name: /chat/i }).first().click();
    await page.getByText(/start claude|start cli/i).click({ trial: true }).catch(() => {});

    // Header chip should show local
    await expect(page.locator("text=/local/i").first()).toBeVisible({ timeout: 8000 });
  });

  test("setup-needed path — Ollama stopped, 409 surfaces in chat", async ({ page }) => {
    // This test assumes the user has stopped Ollama externally before running.
    await page.goto("http://localhost:3000");
    const pill = page.getByRole("button", { name: /airplane/i }).first();
    await pill.click();
    await page.getByRole("button", { name: /chat/i }).first().click();
    await page.getByText(/start/i).click({ trial: true }).catch(() => {});
    await expect(page.locator("text=/ollama serve|setup needed/i").first()).toBeVisible({
      timeout: 8000,
    });
  });
});
```

- [ ] **Step 2: Verify the gate**

Run: `cd apps/dashboard && pnpm playwright test tests/e2e/airplane-mode.spec.ts`
Expected: both tests SKIP with the message about `AUGUR_E2E_OLLAMA=1`.

- [ ] **Step 3: Optional — run the smoke test locally with Ollama running**

Run: `AUGUR_E2E_OLLAMA=1 pnpm playwright test tests/e2e/airplane-mode.spec.ts`
Expected: 2 PASS (when Ollama is up with the configured model pulled).

- [ ] **Step 4: Commit**

```bash
git add tests/e2e/airplane-mode.spec.ts
git commit -m "test(airplane): gated end-to-end smoke

Two scenarios — happy path (toggle on, chip shows model) and setup-needed
(Ollama stopped, 409 surfaces in chat). Gated by AUGUR_E2E_OLLAMA=1 to
keep CI fast while letting developers verify locally on demand."
```

---

## Task 11: Final verification

**Files:** none (verification only)

- [ ] **Step 1: Run full Python test suite for the new tools**

Run:
```bash
cd ~/Projects/Augur && uv run pytest \
  tests/packages/augur-mcp/tools/test_local_backends.py \
  tests/packages/augur-mcp/tools/test_airplane_mode.py \
  tests/packages/augur-mcp/tools/test_connectivity.py \
  -v
```
Expected: all PASS.

- [ ] **Step 2: Run full dashboard test suite**

Run: `cd apps/dashboard && pnpm vitest run`
Expected: previously-passing tests still PASS plus all new tests PASS.

- [ ] **Step 3: Typecheck**

Run: `cd apps/dashboard && pnpm tsc --noEmit`
Expected: 0 errors.

- [ ] **Step 4: Lint**

Run: `/auto-lint`
Expected: clean.

- [ ] **Step 5: Browser walk-through (project rule 28)**

Per CLAUDE.md rule 28 (Client-side verification for any browser-touching change):

`/dev-build`, then in the browser:
1. **Sidebar pill visible.** Toggle off → on; pill changes from gray → amber and shows model name within 5s.
2. **Chat header chip mirrors.** Open FloatingChat with claude selected. Chip shows `local · qwen3.5:9b` (or whichever model). Switch CLI to `gemini` (if configured); chip turns red with "not local-capable".
3. **Mid-session transition message.** Start claude with airplane off, send a message, get a cloud reply. Click pill to flip on. Chat shows: prior reply → `✈ Airplane mode ON — switching claude → local model` → CLI restart messages → next reply.
4. **Failure path.** Stop Ollama (`ollama stop` or close the app). Click pill → start CLI. Chat shows the 409 setup_hint as a monospace block.
5. **Settings page.** Open Settings → Security. Local backend panel shows detected path, model dropdown, working test button, compatibility matrix. Change the model. Reload. Persisted.
6. **Hard refresh** the dashboard. Pill, chip, and Settings stay in sync — no localStorage drift.

If any of these steps fail in the browser, do not declare done. Diagnose and fix.

- [ ] **Step 6: Update spec status if needed**

If something diverged from the spec during implementation, edit `docs/superpowers/specs/2026-05-05-airplane-mode-ux-design.md` to reflect reality before merging. Commit any spec edits separately.

- [ ] **Step 7: Final commit gate**

If steps 1–6 are all green, no further commit is needed; the per-task commits already capture the work. If a fix during step 5 required code changes, commit those:

```bash
git status
# Inspect; commit any genuine fixes with a focused message.
```

---

## Out of scope (deliberately deferred — do NOT implement under this plan)

- Auto-detect connectivity watchdog (decision 4 of the spec).
- Per-agent model overrides (decision 6).
- Non-Ollama local backends (vLLM, LM Studio, custom).
- Auto-fallback to cloud when local is unhealthy.
- Gemini-via-proxy (separate spec when justified).
- Model-pull progress UI.

If during execution a reviewer or implementer wants any of these, file a follow-up spec rather than expanding scope here.
