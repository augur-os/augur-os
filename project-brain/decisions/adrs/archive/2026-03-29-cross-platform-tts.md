# Cross-Platform TTS Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a cross-platform text-to-speech skill to Augur using OS-native engines (macOS `say`, Windows `pyttsx3`), exposed as an MCP tool and a dashboard ReadAloudButton component.

**Architecture:** A `tts` skill with a Python TTS engine script, an MCP tool registered via the plugin tool system, and a reusable React component. All speech uses OS defaults. New calls interrupt current speech.

**Tech Stack:** Python (subprocess, pyttsx3), FastMCP tool registration, React + useMcpMutation, lucide-react icons.

**Spec:** `docs/superpowers/specs/2026-03-29-cross-platform-tts-design.md`

---

## File Map

| Action | Path | Responsibility |
|--------|------|---------------|
| Create | `skills/tts/SKILL.md` | Skill metadata and frontmatter |
| Create | `skills/tts/scripts/tts_engine.py` | Cross-platform TTS wrapper |
| Create | `skills/tts/scripts/mcp/__init__.py` | MCP tool registration entry point |
| Create | `skills/tts/scripts/mcp/_helpers.py` | Shared imports and logger |
| Create | `skills/tts/scripts/mcp/tools_speak.py` | `speak` MCP tool handler |
| Create | `skills/tts/commands/speak.md` | `/speak` slash command documentation |
| Create | `skills/tts/augur/dashboard/components/ReadAloudButton.tsx` | Reusable TTS button component |
| Create | `skills/tts/assets/seeds/_seed.yaml` | Empty seed (convention) |
| Test | `skills/tts/augur/tests/test_tts_engine.py` | Unit tests for tts_engine.py |
| Test | `skills/tts/augur/tests/test_mcp_speak.py` | Unit tests for MCP tool handler |

---

### Task 1: Scaffold Skill Directory and SKILL.md

**Files:**
- Create: `skills/tts/SKILL.md`
- Create: `skills/tts/assets/seeds/_seed.yaml`

- [ ] **Step 1: Create skill directory structure**

```bash
mkdir -p skills/tts/{scripts/mcp,commands,augur/{dashboard/components,tests},assets/seeds}
```

- [ ] **Step 2: Write SKILL.md**

Create `skills/tts/SKILL.md`:

```markdown
---
name: tts
x-augur-type: service
x-augur-tags: []
description: Cross-platform text-to-speech using OS-native engines (macOS say, Windows pyttsx3)
x-augur-hub: command
x-augur-tab: workbench
x-augur-license: MIT
x-augur-metadata:
  version: 1.0.0
  author: Augur
  mcp-server: augur
x-augur-mcp-tools:
  - speak
---

# TTS

Cross-platform text-to-speech service for Augur. Uses OS-native TTS engines:

- **macOS**: `say` command (built-in)
- **Windows**: `pyttsx3` wrapping SAPI/OneCore

## Usage

### MCP Tool

```python
# Speak text
speak(text="Hello from Augur")

# Stop current speech
speak(stop=True)
```

### Slash Command

```
/speak Hello from Augur
```

### Dashboard

The `ReadAloudButton` component can be added to any text block.

## Interrupt Behavior

Any new `speak` call kills current speech before starting. No queue.
```

- [ ] **Step 3: Write empty seed file**

Create `skills/tts/assets/seeds/_seed.yaml`:

```yaml
# TTS skill has no seed data — it's a stateless service.
```

- [ ] **Step 4: Commit**

```bash
git add skills/tts/SKILL.md skills/tts/assets/seeds/_seed.yaml
git commit -m "feat(tts): scaffold skill directory and SKILL.md"
```

---

### Task 2: TTS Engine — Tests

**Files:**
- Create: `skills/tts/augur/tests/test_tts_engine.py`

- [ ] **Step 1: Write failing tests for tts_engine.py**

Create `skills/tts/augur/tests/test_tts_engine.py`:

```python
"""Tests for the cross-platform TTS engine."""

import sys
from unittest.mock import patch, MagicMock

import pytest


@pytest.fixture(autouse=True)
def _clean_module_cache():
    """Remove tts_engine from module cache so each test gets a fresh import."""
    sys.modules.pop("tts_engine", None)
    yield
    sys.modules.pop("tts_engine", None)


class TestSpeak:
    """Tests for the speak() function."""

    @patch("sys.platform", "darwin")
    @patch("subprocess.run")
    @patch("subprocess.Popen")
    def test_speak_macos_returns_speaking(self, mock_popen, mock_run, _clean_module_cache):
        """On macOS, speak() calls say and returns speaking status."""
        mock_process = MagicMock()
        mock_popen.return_value = mock_process

        from tts_engine import speak

        result = speak("hello world")

        assert result["status"] == "speaking"
        assert result["platform"] == "macos"
        assert result["length"] == 11
        mock_run.assert_called_once_with(
            ["killall", "say"], capture_output=True, check=False,
        )
        mock_popen.assert_called_once_with(["say", "hello world"])

    @patch("sys.platform", "darwin")
    @patch("subprocess.run")
    def test_stop_macos_kills_say(self, mock_run, _clean_module_cache):
        """stop=True kills current say process and returns stopped."""
        from tts_engine import speak

        result = speak("ignored", stop=True)

        assert result["status"] == "stopped"
        mock_run.assert_called_once_with(
            ["killall", "say"], capture_output=True, check=False,
        )

    @patch("sys.platform", "linux")
    def test_unsupported_platform_returns_error(self, _clean_module_cache):
        """Unsupported platforms return an error response."""
        from tts_engine import speak

        result = speak("hello")

        assert result["status"] == "error"
        assert "not available" in result["message"]

    @patch("sys.platform", "darwin")
    @patch("subprocess.run")
    @patch("subprocess.Popen")
    def test_speak_empty_string(self, mock_popen, mock_run, _clean_module_cache):
        """Empty string still calls say (OS handles it)."""
        mock_popen.return_value = MagicMock()

        from tts_engine import speak

        result = speak("")

        assert result["status"] == "speaking"
        assert result["length"] == 0


class TestSpeakWindows:
    """Tests for Windows TTS via pyttsx3."""

    @patch("sys.platform", "win32")
    def test_speak_windows_returns_speaking(self, _clean_module_cache):
        """On Windows, speak() uses pyttsx3 and returns speaking status."""
        mock_engine = MagicMock()
        mock_pyttsx3 = MagicMock()
        mock_pyttsx3.init.return_value = mock_engine

        with patch.dict("sys.modules", {"pyttsx3": mock_pyttsx3}):
            from tts_engine import speak

            result = speak("hello world")

        assert result["status"] == "speaking"
        assert result["platform"] == "windows"
        assert result["length"] == 11
        mock_engine.stop.assert_called_once()
        mock_engine.say.assert_called_once_with("hello world")
        mock_engine.runAndWait.assert_called_once()

    @patch("sys.platform", "win32")
    def test_stop_windows(self, _clean_module_cache):
        """stop=True on Windows calls engine.stop() and returns."""
        mock_engine = MagicMock()
        mock_pyttsx3 = MagicMock()
        mock_pyttsx3.init.return_value = mock_engine

        with patch.dict("sys.modules", {"pyttsx3": mock_pyttsx3}):
            from tts_engine import speak

            result = speak("ignored", stop=True)

        assert result["status"] == "stopped"
        mock_engine.stop.assert_called_once()

    @patch("sys.platform", "win32")
    def test_windows_no_pyttsx3_returns_error(self, _clean_module_cache):
        """If pyttsx3 is not installed on Windows, return error."""
        with patch.dict("sys.modules", {"pyttsx3": None}):
            # Force ImportError by making pyttsx3 None in sys.modules
            from tts_engine import speak

            result = speak("hello")

        assert result["status"] == "error"
        assert "pyttsx3" in result["message"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd ~/Projects/Augur
python -m pytest skills/tts/augur/tests/test_tts_engine.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'tts_engine'`

- [ ] **Step 3: Commit failing tests**

```bash
git add skills/tts/augur/tests/test_tts_engine.py
git commit -m "test(tts): add failing tests for tts_engine"
```

---

### Task 3: TTS Engine — Implementation

**Files:**
- Create: `skills/tts/scripts/tts_engine.py`

- [ ] **Step 1: Implement tts_engine.py**

Create `skills/tts/scripts/tts_engine.py`:

```python
"""Cross-platform text-to-speech engine.

Uses OS-native TTS:
- macOS: `say` command (built-in)
- Windows: `pyttsx3` wrapping SAPI/OneCore

All speech uses OS default voice, rate, and volume.
New speak() calls interrupt any currently playing speech.
"""

from __future__ import annotations

import subprocess  # nosec B404
import sys
from typing import Any


def speak(text: str = "", stop: bool = False) -> dict[str, Any]:
    """Speak text aloud using the OS native TTS engine.

    Args:
        text: Text to speak.
        stop: If True, kill current speech and return without speaking.

    Returns:
        dict with status, platform, and length (or error message).
    """
    platform = sys.platform

    if platform == "darwin":
        return _speak_macos(text, stop)
    elif platform == "win32":
        return _speak_windows(text, stop)
    else:
        return {"status": "error", "message": f"TTS not available on this platform ({platform})"}


def _speak_macos(text: str, stop: bool) -> dict[str, Any]:
    """macOS TTS via the built-in `say` command."""
    # Kill any currently playing speech
    subprocess.run(["killall", "say"], capture_output=True, check=False)  # nosec B603, B607

    if stop:
        return {"status": "stopped"}

    subprocess.Popen(["say", text])  # nosec B603, B607
    return {"status": "speaking", "platform": "macos", "length": len(text)}


def _speak_windows(text: str, stop: bool) -> dict[str, Any]:
    """Windows TTS via pyttsx3 (wraps SAPI/OneCore)."""
    try:
        import pyttsx3
    except (ImportError, TypeError):
        return {
            "status": "error",
            "message": "pyttsx3 not installed. Install with: pip install pyttsx3",
        }

    engine = pyttsx3.init()
    engine.stop()

    if stop:
        return {"status": "stopped"}

    engine.say(text)
    engine.runAndWait()
    return {"status": "speaking", "platform": "windows", "length": len(text)}
```

- [ ] **Step 2: Run tests to verify they pass**

```bash
cd ~/Projects/Augur
PYTHONPATH=skills/tts/scripts:$PYTHONPATH python -m pytest skills/tts/augur/tests/test_tts_engine.py -v
```

Expected: All 7 tests PASS.

Note: The `test_windows_no_pyttsx3_returns_error` test patches `sys.modules` to make `pyttsx3` unavailable. The `tts_engine.py` implementation handles this with a try/except around the `import pyttsx3` inside `_speak_windows`, so the import fails at call time (not module load time).

- [ ] **Step 3: Commit**

```bash
git add skills/tts/scripts/tts_engine.py
git commit -m "feat(tts): implement cross-platform TTS engine"
```

---

### Task 4: MCP Tool — Tests

**Files:**
- Create: `skills/tts/augur/tests/test_mcp_speak.py`

- [ ] **Step 1: Write failing tests for the MCP tool handler**

Create `skills/tts/augur/tests/test_mcp_speak.py`:

```python
"""Tests for the speak MCP tool handler."""

import json
import sys
from unittest.mock import MagicMock, patch, AsyncMock

import pytest


@pytest.fixture
def mock_mcp():
    """Create a mock FastMCP instance that captures tool registrations."""
    mcp = MagicMock()
    registered_tools = {}

    def tool_decorator(**kwargs):
        def wrapper(func):
            registered_tools[kwargs.get("name", func.__name__)] = func
            return func
        return wrapper

    mcp.tool = tool_decorator
    mcp._registered_tools = registered_tools
    return mcp


@pytest.fixture
def mock_interceptor():
    """Identity interceptor for testing."""
    def interceptor(func):
        return func
    return interceptor


@pytest.fixture
def mock_metrics():
    return MagicMock()


@pytest.fixture
def registered_tools(mock_mcp, mock_interceptor, mock_metrics):
    """Register tools and return the registry."""
    # Add tts scripts to path so the mcp module can import tts_engine
    scripts_dir = str(
        __import__("pathlib").Path(__file__).parent.parent.parent / "scripts"
    )
    mcp_dir = str(
        __import__("pathlib").Path(__file__).parent.parent.parent / "scripts" / "mcp"
    )
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    if mcp_dir not in sys.path:
        sys.path.insert(0, mcp_dir)

    # Import the register_tools function via importlib to avoid package path issues
    import importlib.util
    init_path = __import__("pathlib").Path(__file__).parent.parent.parent / "scripts" / "mcp" / "__init__.py"
    spec = importlib.util.spec_from_file_location("tts_mcp", str(init_path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    mod.register_tools(mock_mcp, mock_interceptor, mock_metrics)
    return mock_mcp._registered_tools


class TestSpeakToolRegistration:
    """Verify the speak tool is registered correctly."""

    def test_speak_tool_is_registered(self, registered_tools):
        assert "speak" in registered_tools

    @patch("tts_engine.speak", return_value={"status": "speaking", "platform": "macos", "length": 5})
    @pytest.mark.asyncio
    async def test_speak_tool_calls_engine(self, mock_speak, registered_tools):
        tool_fn = registered_tools["speak"]
        result_json = await tool_fn(text="hello")
        result = json.loads(result_json)

        assert result["status"] == "speaking"
        mock_speak.assert_called_once_with("hello", False)

    @patch("tts_engine.speak", return_value={"status": "stopped"})
    @pytest.mark.asyncio
    async def test_speak_tool_stop(self, mock_speak, registered_tools):
        tool_fn = registered_tools["speak"]
        result_json = await tool_fn(text="", stop=True)
        result = json.loads(result_json)

        assert result["status"] == "stopped"
        mock_speak.assert_called_once_with("", True)

    @patch("tts_engine.speak", side_effect=Exception("engine crashed"))
    @pytest.mark.asyncio
    async def test_speak_tool_handles_exception(self, mock_speak, registered_tools):
        tool_fn = registered_tools["speak"]
        result_json = await tool_fn(text="hello")
        result = json.loads(result_json)

        assert result["status"] == "error"
        assert "engine crashed" in result["message"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd ~/Projects/Augur
PYTHONPATH=skills/tts/scripts:$PYTHONPATH python -m pytest skills/tts/augur/tests/test_mcp_speak.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'skills.tts.scripts.mcp'`

- [ ] **Step 3: Commit failing tests**

```bash
git add skills/tts/augur/tests/test_mcp_speak.py
git commit -m "test(tts): add failing tests for speak MCP tool"
```

---

### Task 5: MCP Tool — Implementation

**Files:**
- Create: `skills/tts/scripts/mcp/__init__.py`
- Create: `skills/tts/scripts/mcp/_helpers.py`
- Create: `skills/tts/scripts/mcp/tools_speak.py`

- [ ] **Step 1: Create _helpers.py**

Create `skills/tts/scripts/mcp/_helpers.py`:

```python
"""Shared helpers for TTS MCP tool modules."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

# Setup paths for script imports
try:
    from src.config.paths import get_skill_root
    PLUGIN_ROOT = get_skill_root("tts")
except ImportError:
    PLUGIN_ROOT = Path(__file__).parent.parent.parent  # fallback
SCRIPTS_DIR = PLUGIN_ROOT / "scripts"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

# augur_mcp imports (with fallbacks for standalone mode)
try:
    from augur_mcp.logging import get_entity_logger
    from augur_mcp.annotations import tool_annotations
except ImportError:

    def get_entity_logger(name: str):  # type: ignore[misc]
        return importlib.import_module("logging").getLogger(name)

    def tool_annotations(annotations: dict) -> dict:  # type: ignore[misc]
        return annotations

# Domain-specific script imports
try:
    from tts_engine import speak as tts_speak
except ImportError:
    tts_speak = None  # type: ignore[assignment]

logger = get_entity_logger("mcp.tts")
```

- [ ] **Step 2: Create tools_speak.py**

Create `skills/tts/scripts/mcp/tools_speak.py`:

```python
"""MCP tool handler for text-to-speech."""

from __future__ import annotations

import json
from typing import Any, Callable, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

from ._helpers import logger, tool_annotations, tts_speak


def register_speak_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable[..., Any],
    metrics: Any,
) -> None:
    """Register the speak MCP tool."""

    @mcp.tool(
        name="speak",
        annotations=tool_annotations(
            {
                "title": "Speak Text Aloud",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def speak_tool(text: str = "", stop: bool = False) -> str:
        """Speak text aloud using the OS native TTS engine.

        If stop=True, kills any current speech and returns without speaking.
        If speech is already playing, interrupts it before starting new text.

        Args:
            text: Text to speak aloud.
            stop: If True, stop current speech without starting new speech.

        Returns:
            str: JSON with status, platform, and length (or error).
        """
        metrics.track_tool("speak", skill="tts")

        if not tts_speak:
            return json.dumps({"status": "error", "message": "TTS engine not available"})

        try:
            result = tts_speak(text, stop)
            return json.dumps(result)
        except Exception as e:
            logger.error(f"TTS failed: {e}", exc_info=True)
            return json.dumps({"status": "error", "message": str(e)})
```

- [ ] **Step 3: Create __init__.py**

Create `skills/tts/scripts/mcp/__init__.py`:

```python
"""TTS MCP Tools.

Cross-platform text-to-speech using OS-native engines.

This module is loaded dynamically by the Augur MCP server
via the plugin tool loading system.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

from ._helpers import logger
from .tools_speak import register_speak_tools


def register_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable[..., Any],
    metrics: Any,
) -> None:
    """Register TTS MCP tools."""
    logger.info("Registering TTS MCP tools...")
    register_speak_tools(mcp, mcp_tool_interceptor, metrics)
    logger.info("TTS MCP tools registered successfully")


__all__ = ["register_tools"]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd ~/Projects/Augur
PYTHONPATH=skills/tts/scripts:$PYTHONPATH python -m pytest skills/tts/augur/tests/test_mcp_speak.py -v
```

Expected: All 4 tests PASS.

- [ ] **Step 5: Run all TTS tests together**

```bash
cd ~/Projects/Augur
PYTHONPATH=skills/tts/scripts:$PYTHONPATH python -m pytest skills/tts/augur/tests/ -v
```

Expected: All 11 tests PASS (7 engine + 4 MCP).

- [ ] **Step 6: Commit**

```bash
git add skills/tts/scripts/
git commit -m "feat(tts): implement speak MCP tool with plugin registration"
```

---

### Task 6: Dashboard ReadAloudButton Component

**Files:**
- Create: `skills/tts/augur/dashboard/components/ReadAloudButton.tsx`

- [ ] **Step 1: Create ReadAloudButton component**

Create `skills/tts/augur/dashboard/components/ReadAloudButton.tsx`:

```tsx
"use client";

import { useState } from "react";
import { Volume2, VolumeX } from "lucide-react";
import { useMcpMutation } from "@/lib/mcp/useMcpMutation";

interface ReadAloudButtonProps {
  /** The text content to speak aloud */
  text: string;
  /** Optional className for the button wrapper */
  className?: string;
}

/**
 * A reusable button that speaks text aloud via the OS-native TTS engine.
 *
 * - Idle state: speaker icon
 * - Speaking state: stop icon — click to interrupt
 * - Uses the `speak` MCP tool under the hood
 */
export function ReadAloudButton({ text, className }: ReadAloudButtonProps) {
  const [speaking, setSpeaking] = useState(false);
  const { mutate: speak } = useMcpMutation<{ status: string }>("speak");

  const handleClick = async () => {
    if (speaking) {
      await speak({ stop: true } as Record<string, unknown>);
      setSpeaking(false);
    } else {
      setSpeaking(true);
      try {
        await speak({ text } as Record<string, unknown>);
      } finally {
        // Estimate speech duration: ~150ms per character, min 1s
        // Reset state after estimated duration
        const estimatedMs = Math.max(1000, text.length * 150);
        setTimeout(() => setSpeaking(false), estimatedMs);
      }
    }
  };

  const Icon = speaking ? VolumeX : Volume2;

  return (
    <button
      onClick={handleClick}
      title={speaking ? "Stop speaking" : "Read aloud"}
      className={`p-1 rounded transition-colors hover:bg-[var(--bg-hover)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] ${className ?? ""}`}
    >
      <Icon className="h-3.5 w-3.5" />
    </button>
  );
}
```

- [ ] **Step 2: Verify dashboard build passes**

```bash
cd ~/Projects/Augur/apps/dashboard && pnpm run build
```

Expected: Build passes. The component is created but not yet imported by any page, so it just needs to compile without type errors.

- [ ] **Step 3: Commit**

```bash
git add skills/tts/augur/dashboard/components/ReadAloudButton.tsx
git commit -m "feat(tts): add ReadAloudButton dashboard component"
```

---

### Task 7: Slash Command Documentation

**Files:**
- Create: `skills/tts/commands/speak.md`

- [ ] **Step 1: Write /speak command docs**

Create `skills/tts/commands/speak.md`:

```markdown
---
name: speak
description: Speak text aloud using the OS native TTS engine
---

# /speak

Speak text aloud using the OS-native TTS engine.

## Usage

```
/speak <text>
/speak --stop
```

## Arguments

| Argument | Description |
|----------|-------------|
| `text` | The text to speak aloud |
| `--stop` | Stop any currently playing speech |

## Examples

```
/speak Hello from Augur
/speak --stop
```

## Platform Support

| Platform | Engine | Dependencies |
|----------|--------|-------------|
| macOS | `say` command | None (built-in) |
| Windows | pyttsx3 (SAPI/OneCore) | `pip install pyttsx3` |
| Linux | Not supported | — |

## Behavior

- Uses OS default voice, rate, and volume
- New `/speak` calls interrupt any currently playing speech
- `--stop` silences current speech without starting new speech
```

- [ ] **Step 2: Commit**

```bash
git add skills/tts/commands/speak.md
git commit -m "docs(tts): add /speak slash command documentation"
```

---

### Task 8: Integration Verification

- [ ] **Step 1: Run all TTS tests**

```bash
cd ~/Projects/Augur
PYTHONPATH=skills/tts/scripts:$PYTHONPATH python -m pytest skills/tts/augur/tests/ -v
```

Expected: All 11 tests PASS.

- [ ] **Step 2: Verify dashboard build**

```bash
cd ~/Projects/Augur/apps/dashboard && pnpm run build
```

Expected: Build passes with no errors.

- [ ] **Step 3: Verify MCP tool listing**

```bash
cd ~/Projects/Augur
python -c "
import sys
sys.path.insert(0, 'src')
sys.path.insert(0, 'skills/tts/scripts')
from skills.tts.scripts.mcp import register_tools
print('register_tools callable:', callable(register_tools))
"
```

Expected: `register_tools callable: True`

- [ ] **Step 4: Smoke test the speak function on macOS**

```bash
cd ~/Projects/Augur
python -c "
import sys
sys.path.insert(0, 'skills/tts/scripts')
from tts_engine import speak
result = speak('TTS integration test')
print(result)
"
```

Expected: You hear "TTS integration test" spoken aloud, and output shows `{'status': 'speaking', 'platform': 'macos', 'length': 20}`.

- [ ] **Step 5: Final commit (if any fixes were needed)**

```bash
git add -A skills/tts/
git commit -m "feat(tts): integration verification pass"
```
