# LLM CLI Dispatch by Default — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Auto-detect the user's preferred CLI at config load time and use subprocess dispatch by default, so `get_llm_client()` returns a `CommandLLMClient` backed by `claude --print` (or equivalent) without requiring HTTP endpoint configuration.

**Architecture:** Extract CLI detection from `llm_retry.py` into a shared helper. Call it from `load_llm_config()` to inject a synthetic `cli` profile. Update airplane mode to use `ollama run` CLI instead of HTTP `local` profile. Remove hardcoded `active_profile: local` from config.

**Tech Stack:** Python, `shutil.which`, YAML config, existing `CommandLLMClient`

---

### Task 1: Extract CLI Detection into Shared Helper

**Files:**
- Create: `skills/ai/augur/lib/cli_detect.py`
- Test: `skills/ai/augur/tests/test_cli_detect.py`

The CLI detection logic currently lives in `src/lib/llm_retry.py` (`_get_cli_candidates` + `resolve_cli`). Extract a lightweight, non-raising version into `skills/ai/augur/lib/cli_detect.py` that `config.py` can import.

- [ ] **Step 1: Write tests**

Create `skills/ai/augur/tests/test_cli_detect.py`:

```python
"""Tests for CLI auto-detection."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from skills.ai.augur.lib.cli_detect import detect_cli, cli_command


class TestDetectCli:
    def test_finds_claude_on_path(self):
        with patch("shutil.which", side_effect=lambda name: "/usr/local/bin/claude" if name == "claude" else None):
            with patch("skills.ai.augur.lib.cli_detect._get_preferred_cli", return_value=None):
                with patch("skills.ai.augur.lib.cli_detect._get_candidate_clis", return_value=["claude", "codex"]):
                    result = detect_cli()
        assert result == "/usr/local/bin/claude"

    def test_preferred_cli_takes_priority(self):
        with patch("shutil.which", side_effect=lambda name: f"/usr/local/bin/{name}"):
            with patch("skills.ai.augur.lib.cli_detect._get_preferred_cli", return_value="codex"):
                with patch("skills.ai.augur.lib.cli_detect._get_candidate_clis", return_value=["claude", "codex"]):
                    result = detect_cli()
        assert result == "/usr/local/bin/codex"

    def test_returns_none_when_no_cli_found(self):
        with patch("shutil.which", return_value=None):
            with patch("skills.ai.augur.lib.cli_detect._get_preferred_cli", return_value=None):
                with patch("skills.ai.augur.lib.cli_detect._get_candidate_clis", return_value=["claude", "codex"]):
                    result = detect_cli()
        assert result is None

    def test_returns_none_on_exception(self):
        with patch("skills.ai.augur.lib.cli_detect._get_preferred_cli", side_effect=RuntimeError("boom")):
            result = detect_cli()
        assert result is None


class TestCliCommand:
    def test_claude_uses_print_flag(self):
        assert cli_command("/usr/local/bin/claude") == "/usr/local/bin/claude --print"

    def test_codex_uses_exec_subcommand(self):
        assert cli_command("/usr/local/bin/codex") == "/usr/local/bin/codex exec"

    def test_ollama_uses_run_with_model(self):
        result = cli_command("/usr/local/bin/ollama", model="qwen3.5:latest")
        assert result == "/usr/local/bin/ollama run qwen3.5:latest"

    def test_ollama_default_model(self):
        result = cli_command("/usr/local/bin/ollama")
        assert "ollama run" in result

    def test_unknown_cli_uses_bare_path(self):
        assert cli_command("/usr/local/bin/newcli") == "/usr/local/bin/newcli"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Projects/Augur && python -m pytest skills/ai/augur/tests/test_cli_detect.py -v`
Expected: FAIL — module doesn't exist

- [ ] **Step 3: Implement cli_detect.py**

Create `skills/ai/augur/lib/cli_detect.py`:

```python
"""CLI auto-detection for LLM dispatch.

Detects the user's preferred CLI binary for subprocess-based LLM calls.
Used by load_llm_config() to inject a synthetic 'cli' profile.
"""
from __future__ import annotations

import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

# CLI name → bare command format (no advanced flags)
_CLI_COMMANDS: dict[str, str] = {
    "claude": "{path} --print",
    "codex": "{path} exec",
    "ollama": "{path} run {model}",
}

_DEFAULT_OLLAMA_MODEL = "qwen3.5:latest"


def detect_cli() -> str | None:
    """Find the best available CLI binary for LLM dispatch.

    Priority:
    1. external.preferred_cli from config/system/llm.yaml
    2. cli_agents.yaml ordered list
    3. shutil.which() on each candidate

    Returns absolute path to CLI binary, or None if nothing found.
    Never raises.
    """
    try:
        preferred = _get_preferred_cli()
        if preferred:
            resolved = shutil.which(preferred)
            if resolved:
                return resolved

        for candidate in _get_candidate_clis():
            resolved = shutil.which(candidate)
            if resolved:
                return resolved
    except Exception as exc:
        logger.debug("CLI detection failed: %s", exc)

    return None


def cli_command(cli_path: str, *, model: str | None = None) -> str:
    """Build a bare command string for the given CLI binary.

    Returns e.g. '/usr/local/bin/claude --print' or '/usr/local/bin/ollama run qwen3.5:latest'.
    """
    name = Path(cli_path).stem
    template = _CLI_COMMANDS.get(name)
    if template is None:
        return cli_path

    effective_model = model or _DEFAULT_OLLAMA_MODEL
    return template.format(path=cli_path, model=effective_model)


def _get_preferred_cli() -> str | None:
    """Read external.preferred_cli from config/system/llm.yaml."""
    try:
        from src.config.paths import get_project_root
        import yaml

        llm_yaml = get_project_root() / "config" / "system" / "llm.yaml"
        if not llm_yaml.exists():
            return None
        data = yaml.safe_load(llm_yaml.read_text(encoding="utf-8")) or {}
        preferred = data.get("external", {}).get("preferred_cli")
        if isinstance(preferred, str) and preferred.strip() and preferred.strip() != "auto":
            return preferred.strip()
    except Exception:
        pass
    return None


def _get_candidate_clis() -> list[str]:
    """Read ordered CLI list from cli_agents.yaml."""
    try:
        from src.config.paths import get_skill_data_dir
        import yaml

        cli_agents_yaml = get_skill_data_dir("ai") / "cli_agents.yaml"
        if not cli_agents_yaml.exists():
            return []
        data = yaml.safe_load(cli_agents_yaml.read_text(encoding="utf-8")) or {}
        agents = data.get("agents", {})
        return [name for name, cfg in agents.items() if cfg.get("cmd")]
    except Exception:
        return []
```

- [ ] **Step 4: Run tests**

Run: `cd ~/Projects/Augur && python -m pytest skills/ai/augur/tests/test_cli_detect.py -v`
Expected: All 9 tests PASS

- [ ] **Step 5: Commit**

```bash
git add skills/ai/augur/lib/cli_detect.py skills/ai/augur/tests/test_cli_detect.py
git commit -m "feat(llm): extract CLI detection into shared helper"
```

---

### Task 2: Inject CLI Profile in `load_llm_config`

**Files:**
- Modify: `skills/ai/augur/lib/config.py:130-211` (load_llm_config function)
- Test: `skills/ai/augur/tests/test_cli_dispatch.py` (create)

- [ ] **Step 1: Write tests**

Create `skills/ai/augur/tests/test_cli_dispatch.py`:

```python
"""Tests for CLI profile auto-injection in load_llm_config."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from skills.ai.augur.lib.config import load_llm_config, LLMProfile


class TestCliProfileInjection:
    def _load_with_mock_cli(self, cli_path: str | None, existing_active: str | None = None):
        """Load config with mocked CLI detection and empty file config."""
        with patch("skills.ai.augur.lib.config._load_from_files", return_value=({
            "active_profile": existing_active,
            "profiles": {
                "local": {"provider": "openai_compatible", "base_url": "http://localhost:11434/v1", "model": "qwen3.5:latest"},
            },
        }, Path("/fake/llm.yaml"))):
            with patch("skills.ai.augur.lib.config.detect_cli", return_value=cli_path):
                with patch("skills.ai.augur.lib.config.cli_command", return_value=f"{cli_path} --print" if cli_path else None):
                    return load_llm_config()

    def test_injects_cli_profile_when_detected(self):
        config = self._load_with_mock_cli("/usr/local/bin/claude")
        assert "cli" in config.profiles
        assert config.profiles["cli"].provider == "command"
        assert config.profiles["cli"].command == "/usr/local/bin/claude --print"

    def test_sets_active_profile_to_cli_when_no_explicit(self):
        config = self._load_with_mock_cli("/usr/local/bin/claude")
        assert config.active_profile == "cli"

    def test_preserves_explicit_active_profile(self):
        config = self._load_with_mock_cli("/usr/local/bin/claude", existing_active="local")
        assert config.active_profile == "local"
        assert "cli" in config.profiles  # still injected, just not active

    def test_no_cli_detected_no_injection(self):
        config = self._load_with_mock_cli(None)
        assert "cli" not in config.profiles

    def test_no_cli_detected_keeps_existing_active(self):
        config = self._load_with_mock_cli(None, existing_active="local")
        assert config.active_profile == "local"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Projects/Augur && python -m pytest skills/ai/augur/tests/test_cli_dispatch.py -v`
Expected: FAIL — `detect_cli` not imported in config.py

- [ ] **Step 3: Add CLI injection to load_llm_config**

In `skills/ai/augur/lib/config.py`, add import at the top of `load_llm_config()` and inject the profile before returning. Insert after the env profile block (after line 193) and before `overrides = raw.get("overrides")` (line 195):

```python
    # Auto-detect CLI and inject synthetic "cli" profile
    try:
        from .cli_detect import detect_cli, cli_command

        cli_path = detect_cli()
        if cli_path:
            # Get model from local profile for ollama command
            local_model = None
            if "local" in profiles:
                local_model = profiles["local"].model
            cmd = cli_command(cli_path, model=local_model)
            profiles["cli"] = LLMProfile(
                name="cli",
                provider="command",
                command=cmd,
                timeout_s=120,
            )
            # Set as active if no explicit active_profile from config file
            file_active = raw.get("active_profile") or raw.get("profile")
            if not isinstance(file_active, str) or not file_active.strip():
                active_profile = "cli"
    except Exception as exc:
        logger.debug("CLI auto-detection failed: %s", exc)
```

- [ ] **Step 4: Run tests**

Run: `cd ~/Projects/Augur && python -m pytest skills/ai/augur/tests/test_cli_dispatch.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Run all existing tests for regressions**

Run: `cd ~/Projects/Augur && python -m pytest skills/ai/augur/tests/test_llm_client_extensions.py skills/ai/augur/tests/test_llm_config_airplane.py skills/ai/augur/tests/test_cli_detect.py skills/ai/augur/tests/test_cli_dispatch.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add skills/ai/augur/lib/config.py skills/ai/augur/tests/test_cli_dispatch.py
git commit -m "feat(llm): inject CLI profile in load_llm_config via auto-detection"
```

---

### Task 3: Update Airplane Mode to Use Ollama CLI

**Files:**
- Modify: `skills/ai/augur/lib/config.py:257-283` (resolve_llm_profile airplane block)
- Test: `skills/ai/augur/tests/test_cli_dispatch.py` (extend)

- [ ] **Step 1: Write tests**

Append to `skills/ai/augur/tests/test_cli_dispatch.py`:

```python
from skills.ai.augur.lib.config import resolve_llm_profile, LLMConfig


class TestAirplaneModeCliDispatch:
    def _make_config(self) -> LLMConfig:
        return LLMConfig(
            active_profile="cli",
            profiles={
                "cli": LLMProfile(name="cli", provider="command", command="claude --print"),
                "local": LLMProfile(name="local", provider="openai_compatible", base_url="http://localhost:11434/v1", model="qwen3.5:latest"),
            },
        )

    def test_airplane_returns_ollama_cli_when_available(self):
        config = self._make_config()
        with patch("skills.ai.augur.lib.config._is_airplane_mode", return_value=True):
            with patch("shutil.which", side_effect=lambda n: "/usr/local/bin/ollama" if n == "ollama" else None):
                profile = resolve_llm_profile(config)
        assert profile.provider == "command"
        assert "ollama run" in profile.command

    def test_airplane_falls_back_to_http_local_when_no_ollama_cli(self):
        config = self._make_config()
        with patch("skills.ai.augur.lib.config._is_airplane_mode", return_value=True):
            with patch("shutil.which", return_value=None):
                profile = resolve_llm_profile(config)
        assert profile.name == "local"

    def test_airplane_off_uses_cli_profile(self):
        config = self._make_config()
        with patch("skills.ai.augur.lib.config._is_airplane_mode", return_value=False):
            profile = resolve_llm_profile(config)
        assert profile.name == "cli"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Projects/Augur && python -m pytest skills/ai/augur/tests/test_cli_dispatch.py::TestAirplaneModeCliDispatch -v`
Expected: FAIL — airplane mode still returns HTTP `local` profile

- [ ] **Step 3: Update airplane mode override in resolve_llm_profile**

In `skills/ai/augur/lib/config.py`, replace the airplane mode block (lines 279-283):

```python
    # 1.5 Airplane mode override (before task/context resolution)
    if _is_airplane_mode():
        local = config.profiles.get("local")
        if local:
            return local
```

With:

```python
    # 1.5 Airplane mode override — prefer Ollama CLI, fall back to HTTP local
    if _is_airplane_mode():
        import shutil
        ollama_path = shutil.which("ollama")
        if ollama_path:
            local_model = None
            local_profile = config.profiles.get("local")
            if local_profile and local_profile.model:
                local_model = local_profile.model
            from .cli_detect import cli_command
            cmd = cli_command(ollama_path, model=local_model)
            return LLMProfile(
                name="cli-offline",
                provider="command",
                command=cmd,
                timeout_s=120,
            )
        local = config.profiles.get("local")
        if local:
            return local
```

- [ ] **Step 4: Run tests**

Run: `cd ~/Projects/Augur && python -m pytest skills/ai/augur/tests/test_cli_dispatch.py -v`
Expected: All 8 tests PASS (5 from Task 2 + 3 new)

- [ ] **Step 5: Run full test suite**

Run: `cd ~/Projects/Augur && python -m pytest skills/ai/augur/tests/test_llm_client_extensions.py skills/ai/augur/tests/test_llm_config_airplane.py skills/ai/augur/tests/test_cli_detect.py skills/ai/augur/tests/test_cli_dispatch.py skills/rag/augur/tests/test_contextualizer.py skills/rag/augur/tests/test_contextualizer_llm.py skills/document-extractor/augur/tests/test_ollama_client.py skills/advisor/augur/tests/test_action_evals_llm.py tests/test_llm_retry_config.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add skills/ai/augur/lib/config.py skills/ai/augur/tests/test_cli_dispatch.py
git commit -m "feat(llm): airplane mode uses Ollama CLI instead of HTTP"
```

---

### Task 4: Update Config and Verify End-to-End

**Files:**
- Modify: `config/system/llm.yaml`

- [ ] **Step 1: Update llm.yaml**

Remove `active_profile: local` — let auto-detection handle it. The file becomes:

```yaml
profiles:
  local:
    provider: openai_compatible
    base_url: http://localhost:11434/v1
    model: qwen3.5:latest
    timeout_s: 120
    disable_thinking: true
  remote:
    provider: openai_compatible
    base_url: https://api.groq.com/openai/v1
    api_key_env: GROQ_API_KEY
    model: llama-3.3-70b
  vision-local:
    provider: openai_compatible
    base_url: http://localhost:11434/v1
    model: llava-llama3
    timeout_s: 120

tasks: {}
```

No `active_profile` — the system auto-detects `claude` on PATH and injects a `cli` profile as default.

- [ ] **Step 2: Verify end-to-end**

```bash
python3 -c "
import sys; sys.path.insert(0, '.')
from skills.ai.augur.lib import load_llm_config, resolve_llm_profile, create_llm_client

config = load_llm_config()
print('active_profile:', config.active_profile)
print('profiles:', list(config.profiles.keys()))

profile = resolve_llm_profile(config, task='contextualizer')
print('resolved profile:', profile.name, profile.provider)
print('command:', profile.command)

client = create_llm_client(profile)
print('client type:', type(client).__name__)
"
```

Expected output:
```
active_profile: cli
profiles: ['local', 'remote', 'vision-local', 'cli']
resolved profile: cli command
command: /path/to/claude --print
client type: CommandLLMClient
```

- [ ] **Step 3: Test actual LLM call via CLI dispatch**

```bash
python3 -c "
import sys; sys.path.insert(0, '.')
from skills.ai.augur.lib import get_llm_client

client = get_llm_client('contextualizer')
result = client.generate_text(prompt='Say hello in one word.')
print('Result:', repr(result.strip()))
"
```

Expected: A response from Claude via `claude --print`.

- [ ] **Step 4: Commit**

```bash
git add config/system/llm.yaml
git commit -m "config(llm): remove active_profile, let CLI auto-detection handle it"
```

---

### Task 5: Final Verification

**Files:** None (verification only)

- [ ] **Step 1: Run all tests**

Run: `cd ~/Projects/Augur && python -m pytest skills/ai/augur/tests/ skills/rag/augur/tests/test_contextualizer.py skills/rag/augur/tests/test_contextualizer_llm.py skills/document-extractor/augur/tests/test_ollama_client.py skills/advisor/augur/tests/test_action_evals_llm.py tests/test_llm_retry_config.py -v --ignore=skills/ai/augur/tests/test_context_manager.py`
Expected: All PASS

- [ ] **Step 2: Verify invariants**

```bash
# No hardcoded active_profile in llm.yaml
grep "active_profile" config/system/llm.yaml  # should be empty

# CLI detection works
python3 -c "import sys; sys.path.insert(0,'.'); from skills.ai.augur.lib.cli_detect import detect_cli; print(detect_cli())"
# Expected: /path/to/claude

# get_llm_client returns CommandLLMClient by default
python3 -c "import sys; sys.path.insert(0,'.'); from skills.ai.augur.lib import get_llm_client; c = get_llm_client('contextualizer'); print(type(c).__name__)"
# Expected: CommandLLMClient
```

- [ ] **Step 3: Browser verification**

Navigate to `http://localhost:3000/brain/ai/providers` in Chrome. Verify the Providers page still renders with real data. Wait 6+ seconds for load.
