# Native Windows Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Windows a first-class Augur runtime for baseline user workflows: native paths, native MCP wiring, native AI client config generation, and accurate Windows onboarding.

**Architecture:** Keep Augur core logic cross-platform, but move Windows-sensitive behavior behind shared helpers instead of letting each installer, adapter, and setup script invent its own path and runtime rules. Lock the native-Windows contract with focused tests first, then converge client config writers on the shared MCP configuration path, refresh Windows bootstrap behavior, and harden CI/docs around the new support boundary.

**Tech Stack:** Python, PowerShell, pytest, GitHub Actions YAML, MCP config JSON/TOML, existing `src.config.paths` and `scripts/configure_mcp.py` helpers

**Spec:** `docs/superpowers/specs/2026-04-13-windows-support-strategy-design.md`

---

### Task 1: Lock The Native Windows Contract With Tests

**Files:**
- Modify: `skills/ai/augur/tests/test_paths_client.py`
- Modify: `tests/scripts/test_mcp_ide_config.py`
- Modify: `tests/packages/augur-mcp/tools/test_sync_agents_mcp_config.py`
- Reference: `src/config/paths.py`
- Reference: `scripts/mcp_ide_config.py`
- Reference: `scripts/configure_mcp.py`

- [ ] **Step 1: Add failing path and config expansion tests**

```python
# skills/ai/augur/tests/test_paths_client.py
from unittest.mock import patch
from pathlib import Path


def test_claude_desktop_runtime_dir_windows_prefers_appdata():
    from src.config.paths import get_client_runtime_dir

    with patch("src.config.paths.sys.platform", "win32"), patch.dict(
        "os.environ",
        {"APPDATA": r"C:\Users\tester\AppData\Roaming"},
        clear=False,
    ):
        result = get_client_runtime_dir("claude-desktop")

    assert result == Path(r"C:\Users\tester\AppData\Roaming") / "Claude"


def test_get_python_executable_prefers_windows_venv(tmp_path):
    from src.config import paths

    venv_python = tmp_path / ".venv" / "Scripts" / "python.exe"
    venv_python.parent.mkdir(parents=True)
    venv_python.write_text("", encoding="utf-8")

    with patch("src.config.paths.get_project_root", return_value=tmp_path), patch(
        "src.config.paths.os.name", "nt"
    ):
        result = paths.get_python_executable()

    assert result == venv_python
```

```python
# tests/scripts/test_mcp_ide_config.py
from pathlib import Path
from unittest.mock import patch


def test_windows_config_path_expands_appdata_for_cursor():
    from scripts.mcp_ide_config import _get_config_path_for_platform

    ide_config = {
        "config_path": {
            "windows": "%APPDATA%/Cursor/User/globalStorage/cursor.mcp/mcp.json",
        }
    }

    with patch("platform.system", return_value="Windows"), patch.dict(
        "os.environ",
        {"APPDATA": r"C:\Users\tester\AppData\Roaming"},
        clear=False,
    ):
        result = _get_config_path_for_platform(ide_config, Path("/repo"))

    assert result == Path(r"C:\Users\tester\AppData\Roaming\Cursor\User\globalStorage\cursor.mcp\mcp.json")
```

```python
# tests/packages/augur-mcp/tools/test_sync_agents_mcp_config.py
def test_cursor_runtime_entry_stays_native_on_windows(project_root):
    from scripts.configure_mcp import _build_server_entry

    entry = _build_server_entry(
        Path(r"C:\Users\tester\augur\.venv\Scripts\python.exe"),
        project_root,
        ["-m", "augur_mcp"],
        project_root,
    )

    assert entry["command"].endswith("python.exe")
    assert "wsl.exe" not in entry["command"].lower()
    assert entry["args"] == ["-m", "augur_mcp"]
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run:

```bash
pytest skills/ai/augur/tests/test_paths_client.py tests/scripts/test_mcp_ide_config.py tests/packages/augur-mcp/tools/test_sync_agents_mcp_config.py -q
```

Expected:

```text
FAIL ... windows ...
```

- [ ] **Step 3: Commit the red tests**

```bash
git add skills/ai/augur/tests/test_paths_client.py tests/scripts/test_mcp_ide_config.py tests/packages/augur-mcp/tools/test_sync_agents_mcp_config.py
git commit -m "test: define native windows runtime contract"
```

### Task 2: Centralize Windows Runtime And Path Resolution

**Files:**
- Modify: `src/config/paths.py`
- Modify: `scripts/mcp_ide_config.py`
- Modify: `scripts/configure_mcp.py`
- Modify: `tests/src/test_paths.py`
- Modify: `skills/ai/augur/tests/test_paths_client.py`
- Modify: `tests/scripts/test_mcp_ide_config.py`

- [ ] **Step 1: Add shared Windows directory helpers in `src.config.paths`**

```python
# src/config/paths.py
def _windows_roaming_dir() -> Path:
    app_data = os.environ.get("APPDATA")
    if app_data:
        return Path(app_data)
    return Path.home() / "AppData" / "Roaming"


def _windows_local_dir() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data)
    return Path.home() / "AppData" / "Local"


def _get_claude_desktop_runtime_dir() -> Path:
    home = Path.home()
    if sys.platform == "win32":
        return _windows_roaming_dir() / "Claude"
    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / "Claude"
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "Claude"
    return home / ".config" / "Claude"
```

- [ ] **Step 2: Teach MCP IDE config path expansion to understand Windows-style env vars**

```python
# scripts/mcp_ide_config.py
_WINDOWS_ENV_RE = re.compile(r"%([^%]+)%")


def _expand_path(p: str, repo_root: Path | None = None) -> Path:
    raw = p
    if repo_root and "{repo_root}" in raw:
        raw = raw.replace("{repo_root}", str(repo_root))

    raw = os.path.expanduser(raw)
    raw = _WINDOWS_ENV_RE.sub(lambda match: os.environ.get(match.group(1), match.group(0)), raw)
    raw = os.path.expandvars(raw)
    return Path(raw).resolve()
```

- [ ] **Step 3: Remove duplicate Python resolution in `configure_mcp.py`**

```python
# scripts/configure_mcp.py
def _resolve_python(repo_root: Path, arg: str | None) -> Path:
    if arg and arg.strip():
        return _expand_path(arg.strip())

    try:
        if str(repo_root) not in sys.path:
            sys.path.insert(0, str(repo_root))
        from src.config.paths import get_python_executable

        return get_python_executable()
    except Exception:
        return Path(os.path.realpath(sys.executable))
```

- [ ] **Step 4: Extend path tests to cover the new helper behavior**

```python
# tests/src/test_paths.py
from unittest.mock import patch
from pathlib import Path


def test_get_client_runtime_dir_windows_claude_uses_roaming_appdata():
    from src.config.paths import get_client_runtime_dir

    with patch("src.config.paths.sys.platform", "win32"), patch.dict(
        "os.environ",
        {"APPDATA": r"C:\Users\tester\AppData\Roaming"},
        clear=False,
    ):
        result = get_client_runtime_dir("claude-desktop")

    assert result == Path(r"C:\Users\tester\AppData\Roaming") / "Claude"
```

```python
# tests/scripts/test_mcp_ide_config.py
def test_windows_config_path_expands_appdata_for_cursor():
    from scripts.mcp_ide_config import _get_config_path_for_platform

    ide_config = {
        "config_path": {
            "windows": r"%APPDATA%/Cursor/User/globalStorage/cursor.mcp/mcp.json",
        }
    }

    with patch("platform.system", return_value="Windows"), patch.dict(
        os.environ,
        {"APPDATA": r"C:\Users\tester\AppData\Roaming"},
        clear=False,
    ):
        result = _get_config_path_for_platform(ide_config, Path("/repo"))

    assert result == Path(r"C:\Users\tester\AppData\Roaming") / "Cursor" / "User" / "globalStorage" / "cursor.mcp" / "mcp.json"
```

- [ ] **Step 5: Run the focused tests to verify green**

Run:

```bash
uv run pytest tests/src/test_paths.py skills/ai/augur/tests/test_paths_client.py tests/scripts/test_mcp_ide_config.py tests/packages/augur-mcp/tools/test_sync_agents_mcp_config.py -q
```

Expected:

```text
passed
```

- [ ] **Step 6: Commit the shared helper changes**

```bash
git add src/config/paths.py scripts/mcp_ide_config.py scripts/configure_mcp.py tests/src/test_paths.py skills/ai/augur/tests/test_paths_client.py tests/scripts/test_mcp_ide_config.py tests/packages/augur-mcp/tools/test_sync_agents_mcp_config.py
git commit -m "refactor: centralize windows runtime helpers"
```

### Task 3: Converge Client Config Writers On Native MCP Wiring

**Files:**
- Modify: `skills/ai/scripts/setup_cursor_mcp.py`
- Modify: `skills/ai/augur/adapters/claude_desktop.py`
- Modify: `skills/ai/augur/adapters/cowork.py`
- Modify: `skills/ai/augur/tests/test_setup_cursor_mcp.py`
- Create: `skills/ai/augur/tests/test_windows_client_config.py`
- Reference: `scripts/configure_mcp.py`
- Reference: `config/agents/ide_mcp_configs.yaml`

- [ ] **Step 1: Turn `setup_cursor_mcp.py` into a thin wrapper over `configure_mcp.py`**

```python
# skills/ai/scripts/setup_cursor_mcp.py
import subprocess
import sys
from pathlib import Path

from src.config.paths import get_project_root, get_python_executable


def setup_cursor_mcp() -> int:
    repo_root = get_project_root()
    configure_script = repo_root / "scripts" / "configure_mcp.py"
    cmd = [
        str(get_python_executable()),
        str(configure_script),
        "--client",
        "cursor",
        "--auto",
    ]
    completed = subprocess.run(cmd, check=False)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(setup_cursor_mcp())
```

- [ ] **Step 2: Make Claude Desktop adapters use shared runtime paths**

```python
# skills/ai/augur/adapters/claude_desktop.py
from src.config.paths import get_client_runtime_dir, get_project_root, get_python_executable


def _find_project_root(self) -> Path:
    return get_project_root()


def _find_python(self) -> str:
    return str(get_python_executable())


def ensure_config(self, intent: Optional[Intent] = None) -> dict[str, Any]:
    config_path = get_client_runtime_dir("claude-desktop") / "claude_desktop_config.json"
    ...
```

```python
# skills/ai/augur/adapters/cowork.py
from src.config.paths import get_client_runtime_dir


def _get_claude_desktop_config_path(self) -> Path:
    return get_client_runtime_dir("claude-desktop") / "claude_desktop_config.json"
```

- [ ] **Step 3: Add adapter and wrapper tests**

```python
# skills/ai/augur/tests/test_windows_client_config.py
from pathlib import Path
from unittest.mock import patch


def test_claude_desktop_adapter_uses_shared_runtime_dir():
    from skills.ai.augur.adapters.claude_desktop import ClaudeDesktopAdapter

    adapter = ClaudeDesktopAdapter()

    with patch(
        "skills.ai.augur.adapters.claude_desktop.get_client_runtime_dir",
        return_value=Path(r"C:\Users\tester\AppData\Roaming\Claude"),
    ):
        result = adapter.ensure_config()

    assert result["config_paths"] == [r"C:\Users\tester\AppData\Roaming\Claude\claude_desktop_config.json"]
```

```python
# skills/ai/augur/tests/test_setup_cursor_mcp.py
from unittest.mock import patch


def test_setup_cursor_mcp_delegates_to_configure_mcp():
    import setup_cursor_mcp

    with patch("setup_cursor_mcp.subprocess.run") as run_mock:
        run_mock.return_value.returncode = 0
        rc = setup_cursor_mcp.setup_cursor_mcp()

    assert rc == 0
    command = run_mock.call_args.args[0]
    assert command[-3:] == ["--client", "cursor", "--auto"]
```

- [ ] **Step 4: Run the client wiring tests to verify green**

Run:

```bash
uv run pytest skills/ai/augur/tests/test_setup_cursor_mcp.py skills/ai/augur/tests/test_windows_client_config.py -q
```

Expected:

```text
passed
```

- [ ] **Step 5: Commit the native client wiring changes**

```bash
git add skills/ai/scripts/setup_cursor_mcp.py skills/ai/augur/adapters/claude_desktop.py skills/ai/augur/adapters/cowork.py skills/ai/augur/tests/test_setup_cursor_mcp.py skills/ai/augur/tests/test_windows_client_config.py
git commit -m "feat: unify windows client config wiring"
```

### Task 4: Harden Native Windows Bootstrap And CI Smoke Coverage

**Files:**
- Modify: `scripts/install.ps1`
- Create: `tests/scripts/test_install_ps1.py`
- Modify: `.github/workflows/ci-cross-platform.yml`
- Reference: `scripts/install.sh`

- [ ] **Step 1: Align the PowerShell installer with the native runtime contract**

```powershell
# scripts/install.ps1
function Invoke-Tests {
    ...
    $testPath = Join-Path $INSTALL_DIR "skills\knowledge\tests"
    ...
}

function Show-Completion {
    ...
Write-Step "Configuring Augur MCP for requested clients..."
$ConfigureClients = @("cursor")
foreach ($client in $ConfigureClients) {
    & $python.Command "scripts/configure_mcp.py" "--client" $client "--auto"
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to configure MCP for $client"
    }
}

Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Restart your AI client after MCP configuration"
Write-Host "  2. Run: python scripts/configure_mcp.py --list-ides"
Write-Host "  3. Start the dashboard:"
Write-Host "     cd $INSTALL_DIR"
Write-Host "     corepack enable"
Write-Host "     pnpm install"
Write-Host "     pnpm --filter dashboard dev"
Write-Host "Skills live in: $INSTALL_DIR\skills\"
}
```

- [ ] **Step 2: Add static tests for `install.ps1`**

```python
# tests/scripts/test_install_ps1.py
from pathlib import Path

from src.config.paths import get_project_root


PROJECT_ROOT = get_project_root()
INSTALL_PS1 = PROJECT_ROOT / "scripts" / "install.ps1"


def test_install_ps1_references_configure_mcp_script():
    content = INSTALL_PS1.read_text(encoding="utf-8")
    assert "scripts/configure_mcp.py" in content


def test_install_ps1_no_legacy_src_lib_dashboard_path():
    content = INSTALL_PS1.read_text(encoding="utf-8")
    assert "src/lib/dashboard" not in content
    assert "src/lib/scripts/configure_mcp.py" not in content
    assert ".claude\\skills" not in content
    assert ".claude\\skills\\knowledge\\tests" not in content
```

- [ ] **Step 3: Replace stale cross-platform smoke checks with real native checks**

```yaml
# .github/workflows/ci-cross-platform.yml
- name: Test path resolution (Windows)
  if: runner.os == 'Windows'
  run: |
    .\.venv\Scripts\Activate.ps1
    python -c "from src.config.paths import get_project_root, get_python_executable; print(get_project_root()); print(get_python_executable())"

- name: Test configure_mcp dry-run (Windows)
  if: runner.os == 'Windows'
  run: |
    .\.venv\Scripts\Activate.ps1
    python scripts/configure_mcp.py --client cursor --check --verbose
```

- [ ] **Step 4: Run the installer and CI smoke tests locally**

Run:

```bash
uv run pytest tests/scripts/test_install_ps1.py tests/scripts/test_mcp_ide_config.py -q
```

Expected:

```text
passed
```

- [ ] **Step 5: Commit the bootstrap and CI hardening**

```bash
git add scripts/install.ps1 tests/scripts/test_install_ps1.py .github/workflows/ci-cross-platform.yml
git commit -m "test: harden native windows bootstrap coverage"
```

### Task 5: Refresh Windows Documentation And Onboarding

**Files:**
- Modify: `docs/guides/installation-windows.md`
- Modify: `README.md`
- Modify: `skills/onboard/references/mode-default.md`
- Modify: `skills/onboard/references/mode-connect.md`
- Reference: `scripts/install.ps1`
- Reference: `scripts/configure_mcp.py`

- [ ] **Step 1: Rewrite the Windows guide around the native support contract**

````md
# docs/guides/installation-windows.md
## Installation

### Quick Install

```powershell
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/augur-os/augur-os/main/scripts/install.ps1" -OutFile "install.ps1"
.\install.ps1
```

### Dashboard

```powershell
cd $env:AUGUR_DIR
corepack enable
pnpm install
pnpm --filter dashboard dev
```

### Configure AI Clients

```powershell
python scripts/configure_mcp.py --list-ides
python scripts/configure_mcp.py --client cursor --auto
```
````

- [ ] **Step 2: Update top-level README install messaging**

````md
# README.md
### Windows

```powershell
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/augur-os/augur-os/main/scripts/install.ps1" -OutFile "install.ps1"
.\install.ps1
python scripts/configure_mcp.py --client cursor --auto
```

Windows support is native-first. WSL is optional and only needed for feature-specific fallbacks documented separately.
````

- [ ] **Step 3: Update onboard references to the canonical script locations**

```md
# skills/onboard/references/mode-default.md
python scripts/configure_mcp.py --apply
```

```md
# skills/onboard/references/mode-connect.md
Run `scripts/configure_mcp.py --client <platform> --auto` after installation.
```

- [ ] **Step 4: Verify the docs no longer point to stale paths**

Run:

```bash
rg -n "src/lib/dashboard|src/lib/scripts/configure_mcp.py|install.ps1\" -OutFile \"install.ps1\"" README.md docs skills/onboard
```

Expected:

```text
docs/guides/installation-windows.md:...
README.md:...
skills/onboard/references/mode-default.md:...
skills/onboard/references/mode-connect.md:...
```

- [ ] **Step 5: Commit the documentation refresh**

```bash
git add docs/guides/installation-windows.md README.md skills/onboard/references/mode-default.md skills/onboard/references/mode-connect.md
git commit -m "docs: refresh native windows onboarding"
```

## Self-Review Checklist

- Spec coverage:
  - native Windows as official path: Tasks 2-5
  - native MCP/client wiring: Tasks 1-4
  - native bootstrap path: Task 4
  - CI and regression protection: Tasks 1, 2, 4
  - refreshed docs and onboarding: Task 5
- Placeholder scan:
  - no unresolved markers or deferred-test language remain
- Type consistency:
  - shared helpers flow through `src.config.paths`
  - MCP config generation stays routed through `scripts/configure_mcp.py`
  - client adapters consume the shared runtime helpers instead of bespoke Windows path logic
