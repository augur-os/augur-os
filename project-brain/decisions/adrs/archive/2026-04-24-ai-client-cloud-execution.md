# AI Client Cloud Execution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build review-first cloud execution support for Codex, Claude, Gemini, and GitHub Copilot, with explicit opt-in for write/fix/PR modes.

**Architecture:** Add a shared cloud execution profile and status library, then wire that status into onboarding and client packaging. Copilot becomes a first-class local and cloud target, while Claude/Codex/Gemini gain normalized cloud-readiness status and Gemini gets a review-first GitHub Actions workflow.

**Tech Stack:** Python 3.11+, YAML config, pytest, GitHub Actions YAML, existing Augur plugin-pack and sync_agents Python modules

**Spec:** `docs/superpowers/specs/2026-04-24-ai-client-cloud-execution-design.md`

---

## File Structure

### New Files

| File | Responsibility |
| --- | --- |
| `config/agents/cloud_execution.yaml` | Declarative cloud execution profiles for Codex, Claude, Gemini, and Copilot |
| `skills/ai/augur/lib/cloud_execution.py` | Load profiles and classify local/cloud/mutation readiness |
| `skills/ai/augur/tests/test_cloud_execution.py` | Unit tests for profile parsing and status classification |
| `skills/onboard/scripts/cloud_status.py` | Read-only CLI used by `/onboard --cloud` to print the cloud matrix |
| `skills/onboard/tests/test_cloud_status.py` | Unit tests for cloud status CLI output |
| `skills/plugin-pack/scripts/formatters/copilot.py` | Copilot-native plugin-pack formatter writing `.github` assets |
| `skills/plugin-pack/augur/tests/test_copilot_formatter.py` | Formatter tests for `.github/skills`, prompts, agents, and project-first install |
| `.github/workflows/gemini.yml` | Review-first Gemini CLI cloud execution workflow |
| `tests/test_ai_client_cloud_workflows.py` | Workflow/config regression tests for cloud mode separation |

### Modified Files

| File | What Changes |
| --- | --- |
| `skills/plugin-pack/scripts/profiles.py` | Add `COPILOT_PROFILE` |
| `skills/plugin-pack/scripts/formatters/__init__.py` | Export `CopilotFormatter` |
| `skills/plugin-pack/scripts/plugin_assembler.py` | Register `copilot` target |
| `skills/plugin-pack/SKILL.md` | Document `--target copilot` |
| `skills/plugin-pack/augur/tests/test_profiles.py` | Include Copilot in profile tests |
| `skills/plugin-pack/augur/tests/test_assembler.py` | Add assemble and CLI tests for Copilot |
| `skills/ai/scripts/sync_agents/adapters/copilot.py` | Track `.github/skills`, `.github/prompts`, `.github/agents`, and detect Copilot CLI |
| `skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py` | Update Copilot managed-file and cleanup assertions |
| `config/agents/ide_integrations.yaml` | Enable Copilot and list current managed files |
| `config/agents/ide_mcp_configs.yaml` | Add Copilot CLI and VS Code Copilot MCP targets |
| `scripts/configure_mcp.py` | Map Copilot IDE names to `--client-id copilot` |
| `tests/packages/augur-mcp/tools/test_sync_agents_mcp_config.py` | Assert Copilot MCP runtime args use client id `copilot` |
| `skills/onboard/SKILL.md` | Add `/onboard --cloud` usage |
| `skills/onboard/references/mode-status.md` | Add cloud execution matrix fields |
| `skills/onboard/references/mode-connect.md` | Add `copilot` and cloud setup notes |
| `skills/onboard/references/platform-detection.md` | Add Copilot CLI/cloud detection rows |
| `skills/onboard/augur/data/platforms.yaml` | Add Copilot platform and cloud metadata |

---

## Task 1: Cloud Profile Foundation

**Files:**
- Create: `config/agents/cloud_execution.yaml`
- Create: `skills/ai/augur/lib/cloud_execution.py`
- Create: `skills/ai/augur/tests/test_cloud_execution.py`

- [ ] **Step 1: Write failing tests for profile loading and status classification**

Create `skills/ai/augur/tests/test_cloud_execution.py`:

```python
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_load_cloud_profiles_has_four_primary_clients():
    from skills.ai.augur.lib.cloud_execution import load_cloud_profiles

    profiles = load_cloud_profiles(PROJECT_ROOT / "config" / "agents" / "cloud_execution.yaml")

    assert set(profiles) == {"codex", "claude", "gemini", "copilot"}
    assert profiles["copilot"].cloud.vendor_surface == "copilot-cloud-agent"
    assert profiles["copilot"].cloud.default_modes == ("read", "review", "plan")
    assert profiles["copilot"].cloud.mutation_modes == ("fix", "commit", "pr")


def test_status_reports_ready_for_review_when_workflow_and_secret_exist(tmp_path):
    from skills.ai.augur.lib.cloud_execution import classify_cloud_status, load_cloud_profiles

    workflow = tmp_path / ".github" / "workflows" / "claude.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text("name: Claude\n", encoding="utf-8")

    profiles = load_cloud_profiles(PROJECT_ROOT / "config" / "agents" / "cloud_execution.yaml")
    status = classify_cloud_status(
        profiles["claude"],
        repo_root=tmp_path,
        env={"CLAUDE_CODE_OAUTH_TOKEN": "present"},
        command_exists=lambda command: f"/usr/bin/{command}",
    )

    assert status.status == "ready"
    assert status.cloud_review_ready is True
    assert status.cloud_mutation_enabled is False
    assert "mutation mode requires explicit opt-in" in status.mutation_blockers


def test_status_reports_missing_secret_without_exposing_values(tmp_path):
    from skills.ai.augur.lib.cloud_execution import classify_cloud_status, load_cloud_profiles

    workflow = tmp_path / ".github" / "workflows" / "claude.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text("name: Claude\n", encoding="utf-8")

    profiles = load_cloud_profiles(PROJECT_ROOT / "config" / "agents" / "cloud_execution.yaml")
    status = classify_cloud_status(
        profiles["claude"],
        repo_root=tmp_path,
        env={},
        command_exists=lambda command: f"/usr/bin/{command}",
    )

    assert status.status == "missing-secret"
    assert status.cloud_review_ready is False
    assert status.blockers == ("missing secret: CLAUDE_CODE_OAUTH_TOKEN",)
    assert "present" not in repr(status)


def test_copilot_without_github_app_is_needs_github_app(tmp_path):
    from skills.ai.augur.lib.cloud_execution import classify_cloud_status, load_cloud_profiles

    profiles = load_cloud_profiles(PROJECT_ROOT / "config" / "agents" / "cloud_execution.yaml")
    status = classify_cloud_status(
        profiles["copilot"],
        repo_root=tmp_path,
        env={},
        command_exists=lambda command: "/opt/homebrew/bin/copilot" if command == "copilot" else None,
    )

    assert status.status == "needs-github-app"
    assert status.local_cli_present is True
    assert "needs app or connector: copilot_cloud_agent_enabled" in status.blockers


def test_explicit_mutation_opt_in_enables_mutation_when_review_is_ready(tmp_path):
    from skills.ai.augur.lib.cloud_execution import classify_cloud_status, load_cloud_profiles

    workflow = tmp_path / ".github" / "workflows" / "gemini.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text("name: Gemini\n", encoding="utf-8")

    profiles = load_cloud_profiles(PROJECT_ROOT / "config" / "agents" / "cloud_execution.yaml")
    status = classify_cloud_status(
        profiles["gemini"],
        repo_root=tmp_path,
        env={"GEMINI_API_KEY": "present"},
        command_exists=lambda command: f"/usr/bin/{command}",
        enabled_mutation_clients={"gemini"},
    )

    assert status.status == "ready"
    assert status.cloud_mutation_enabled is True
    assert status.mutation_blockers == ()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
python -m pytest skills/ai/augur/tests/test_cloud_execution.py -v
```

Expected: FAIL with `ModuleNotFoundError` for `skills.ai.augur.lib.cloud_execution`.

- [ ] **Step 3: Add the cloud execution profile config**

Create `config/agents/cloud_execution.yaml`:

```yaml
schema_version: 1
default_safe_modes:
  - read
  - review
  - plan
mutation_modes:
  - fix
  - commit
  - pr
clients:
  codex:
    display_name: OpenAI Codex
    local:
      cli: codex
      plugin_pack: codex
      mcp_client_id: codex
      config_paths:
        - ~/.codex/config.toml
    cloud:
      vendor_surface: codex-cloud
      execution_kind: hosted
      github_workflow: .github/workflows/codex.yml
      default_modes: [read, review, plan]
      mutation_modes: [fix, commit, pr]
      triggers:
        read: ["@codex-ask"]
        review: ["@codex-review"]
        fix: ["@codex-fix"]
      required_secrets: []
      required_apps:
        - chatgpt_github_connector
      enterprise_notes:
        - Codex cloud may require ChatGPT workspace admin setup.
  claude:
    display_name: Claude Code
    local:
      cli: claude
      plugin_pack: cowork
      mcp_client_id: claude-code
      config_paths:
        - ~/.claude/
    cloud:
      vendor_surface: claude-code-action
      execution_kind: github-action
      github_workflow: .github/workflows/claude.yml
      default_modes: [read, review, plan]
      mutation_modes: [fix, commit, pr]
      triggers:
        read: ["@claude-ask"]
        review: ["@claude-review"]
        fix: ["@claude-fix", "@claude-review-fix"]
      required_secrets:
        - CLAUDE_CODE_OAUTH_TOKEN
      required_apps: []
      enterprise_notes: []
  gemini:
    display_name: Gemini
    local:
      cli: gemini
      plugin_pack: gemini
      mcp_client_id: gemini
      config_paths:
        - ~/.gemini/
    cloud:
      vendor_surface: gemini-code-assist
      execution_kind: mixed
      github_workflow: .github/workflows/gemini.yml
      default_modes: [read, review, plan]
      mutation_modes: [fix, commit, pr]
      triggers:
        read: ["/gemini"]
        review: ["/gemini review", "@gemini-cli /review"]
        fix: ["@gemini-cli /fix"]
      required_secrets:
        - GEMINI_API_KEY
      required_apps: []
      enterprise_notes:
        - Gemini Code Assist Enterprise setup may require Google Cloud IAM and Developer Connect.
  copilot:
    display_name: GitHub Copilot
    local:
      cli: copilot
      plugin_pack: copilot
      mcp_client_id: copilot
      config_paths:
        - ~/.copilot/
        - .github/
    cloud:
      vendor_surface: copilot-cloud-agent
      execution_kind: hosted
      github_workflow: null
      default_modes: [read, review, plan]
      mutation_modes: [fix, commit, pr]
      triggers:
        read: ["@copilot"]
        review: ["@copilot review"]
        fix: ["@copilot", "assign issue to Copilot"]
      required_secrets: []
      required_apps:
        - copilot_cloud_agent_enabled
      enterprise_notes:
        - Copilot cloud agent availability depends on GitHub plan, organization policy, and repository enablement.
```

- [ ] **Step 4: Implement the cloud execution loader and classifier**

Create `skills/ai/augur/lib/cloud_execution.py`:

```python
"""Cloud execution profiles and readiness classification for AI clients."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Sequence
import os
import shutil

import yaml

from src.config.paths import get_config_dir, get_project_root

SAFE_MODES = frozenset({"read", "review", "plan"})
MUTATION_MODES = frozenset({"fix", "commit", "pr"})
STATUS_PRIORITY = (
    "disabled-by-policy",
    "missing-secret",
    "needs-github-app",
    "needs-enterprise-admin",
    "local-only",
    "unsupported",
    "unknown",
)


@dataclass(frozen=True)
class LocalProfile:
    cli: str
    plugin_pack: str
    mcp_client_id: str
    config_paths: tuple[str, ...]


@dataclass(frozen=True)
class CloudProfile:
    vendor_surface: str
    execution_kind: str
    github_workflow: str | None
    default_modes: tuple[str, ...]
    mutation_modes: tuple[str, ...]
    triggers: dict[str, tuple[str, ...]]
    required_secrets: tuple[str, ...]
    required_apps: tuple[str, ...]
    enterprise_notes: tuple[str, ...]


@dataclass(frozen=True)
class ClientCloudProfile:
    client_id: str
    display_name: str
    local: LocalProfile
    cloud: CloudProfile
    enabled: bool = True


@dataclass(frozen=True)
class CloudClientStatus:
    client_id: str
    display_name: str
    status: str
    local_cli_present: bool
    workflow_present: bool | None
    cloud_review_ready: bool
    cloud_mutation_enabled: bool
    blockers: tuple[str, ...]
    mutation_blockers: tuple[str, ...]
    default_modes: tuple[str, ...]
    mutation_modes: tuple[str, ...]


def _tuple(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, Sequence):
        return tuple(str(item) for item in value)
    return (str(value),)


def _load_path(path: Path | None) -> Path:
    if path is not None:
        return path
    return get_config_dir() / "agents" / "cloud_execution.yaml"


def load_cloud_profiles(path: Path | None = None) -> dict[str, ClientCloudProfile]:
    """Load cloud execution profiles keyed by client id."""
    config_path = _load_path(path)
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    clients = data.get("clients", {})
    profiles: dict[str, ClientCloudProfile] = {}

    for client_id, raw in clients.items():
        local_raw = raw.get("local", {})
        cloud_raw = raw.get("cloud", {})
        triggers = {
            str(mode): _tuple(values)
            for mode, values in (cloud_raw.get("triggers") or {}).items()
        }
        profile = ClientCloudProfile(
            client_id=str(client_id),
            display_name=str(raw.get("display_name") or client_id),
            enabled=bool(raw.get("enabled", True)),
            local=LocalProfile(
                cli=str(local_raw.get("cli") or client_id),
                plugin_pack=str(local_raw.get("plugin_pack") or client_id),
                mcp_client_id=str(local_raw.get("mcp_client_id") or client_id),
                config_paths=_tuple(local_raw.get("config_paths")),
            ),
            cloud=CloudProfile(
                vendor_surface=str(cloud_raw.get("vendor_surface") or client_id),
                execution_kind=str(cloud_raw.get("execution_kind") or "unknown"),
                github_workflow=cloud_raw.get("github_workflow"),
                default_modes=_tuple(cloud_raw.get("default_modes")),
                mutation_modes=_tuple(cloud_raw.get("mutation_modes")),
                triggers=triggers,
                required_secrets=_tuple(cloud_raw.get("required_secrets")),
                required_apps=_tuple(cloud_raw.get("required_apps")),
                enterprise_notes=_tuple(cloud_raw.get("enterprise_notes")),
            ),
        )
        _validate_profile(profile)
        profiles[profile.client_id] = profile

    return profiles


def _validate_profile(profile: ClientCloudProfile) -> None:
    default_modes = set(profile.cloud.default_modes)
    mutation_modes = set(profile.cloud.mutation_modes)
    unsafe_defaults = default_modes & MUTATION_MODES
    unknown_modes = (default_modes | mutation_modes) - (SAFE_MODES | MUTATION_MODES)
    if unsafe_defaults:
        raise ValueError(f"{profile.client_id} default modes include mutation modes: {sorted(unsafe_defaults)}")
    if unknown_modes:
        raise ValueError(f"{profile.client_id} has unknown modes: {sorted(unknown_modes)}")


def classify_cloud_status(
    profile: ClientCloudProfile,
    *,
    repo_root: Path | None = None,
    env: Mapping[str, str] | None = None,
    command_exists: Callable[[str], str | None] | None = None,
    app_enabled: Mapping[str, bool] | None = None,
    enabled_mutation_clients: set[str] | None = None,
) -> CloudClientStatus:
    """Classify one client's local/cloud readiness without mutating the system."""
    root = repo_root or get_project_root()
    env_map = env if env is not None else os.environ
    command_checker = command_exists or shutil.which
    apps = app_enabled or {}
    mutation_enabled_clients = enabled_mutation_clients or set()

    local_cli_present = command_checker(profile.local.cli) is not None
    blockers: list[str] = []

    if not profile.enabled:
        blockers.append("disabled by Augur policy")

    workflow_present: bool | None
    if profile.cloud.github_workflow:
        workflow_present = (root / profile.cloud.github_workflow).exists()
        if not workflow_present:
            blockers.append(f"missing workflow: {profile.cloud.github_workflow}")
    else:
        workflow_present = None

    for secret in profile.cloud.required_secrets:
        if not env_map.get(secret):
            blockers.append(f"missing secret: {secret}")

    for app in profile.cloud.required_apps:
        if apps.get(app) is not True:
            blockers.append(f"needs app or connector: {app}")

    status = _status_from_blockers(blockers)
    cloud_review_ready = status == "ready"

    mutation_blockers: list[str] = []
    if profile.client_id not in mutation_enabled_clients:
        mutation_blockers.append("mutation mode requires explicit opt-in")
    if not cloud_review_ready:
        mutation_blockers.append("cloud review mode is not ready")

    return CloudClientStatus(
        client_id=profile.client_id,
        display_name=profile.display_name,
        status=status,
        local_cli_present=local_cli_present,
        workflow_present=workflow_present,
        cloud_review_ready=cloud_review_ready,
        cloud_mutation_enabled=not mutation_blockers,
        blockers=tuple(blockers),
        mutation_blockers=tuple(mutation_blockers),
        default_modes=profile.cloud.default_modes,
        mutation_modes=profile.cloud.mutation_modes,
    )


def _status_from_blockers(blockers: list[str]) -> str:
    if not blockers:
        return "ready"
    joined = "\n".join(blockers)
    if "disabled by Augur policy" in joined:
        return "disabled-by-policy"
    if "missing secret:" in joined:
        return "missing-secret"
    if "needs app or connector:" in joined:
        return "needs-github-app"
    if "missing workflow:" in joined:
        return "local-only"
    for status in STATUS_PRIORITY:
        if status in joined:
            return status
    return "unknown"
```

- [ ] **Step 5: Run the cloud profile tests**

Run:

```bash
python -m pytest skills/ai/augur/tests/test_cloud_execution.py -v
```

Expected: PASS for all tests.

- [ ] **Step 6: Commit the foundation**

Run:

```bash
git add config/agents/cloud_execution.yaml skills/ai/augur/lib/cloud_execution.py skills/ai/augur/tests/test_cloud_execution.py
git commit -m "feat(ai): add cloud execution profiles"
```

Expected: commit succeeds.

---

## Task 2: Onboarding Cloud Matrix

**Files:**
- Create: `skills/onboard/scripts/cloud_status.py`
- Create: `skills/onboard/tests/test_cloud_status.py`
- Modify: `skills/onboard/SKILL.md`
- Modify: `skills/onboard/references/mode-status.md`
- Modify: `skills/onboard/references/mode-connect.md`
- Modify: `skills/onboard/references/platform-detection.md`
- Modify: `skills/onboard/augur/data/platforms.yaml`

- [ ] **Step 1: Write failing tests for the cloud status CLI**

Create `skills/onboard/tests/test_cloud_status.py`:

```python
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_cloud_status_script_outputs_all_primary_clients():
    result = subprocess.run(
        [
            sys.executable,
            "skills/onboard/scripts/cloud_status.py",
            "--repo-root",
            str(PROJECT_ROOT),
            "--no-env",
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        timeout=10,
    )

    assert result.returncode == 0, result.stderr
    assert "Client" in result.stdout
    assert "Codex" in result.stdout
    assert "Claude" in result.stdout
    assert "Gemini" in result.stdout
    assert "Copilot" in result.stdout
    assert "Write" in result.stdout
    assert "disabled" in result.stdout
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
python -m pytest skills/onboard/tests/test_cloud_status.py -v
```

Expected: FAIL because `skills/onboard/scripts/cloud_status.py` does not exist.

- [ ] **Step 3: Implement the read-only cloud status CLI**

Create `skills/onboard/scripts/cloud_status.py`:

```python
#!/usr/bin/env python3
"""Print Augur AI-client cloud execution readiness."""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from skills.ai.augur.lib.cloud_execution import classify_cloud_status, load_cloud_profiles


def _yes_no(value: bool | None) -> str:
    if value is None:
        return "n/a"
    return "yes" if value else "no"


def _row(values: list[str], widths: list[int]) -> str:
    return "  ".join(value.ljust(width) for value, width in zip(values, widths))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Show Augur AI-client cloud execution status")
    parser.add_argument("--repo-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--profiles", type=Path, default=None)
    parser.add_argument("--no-env", action="store_true", help="Ignore process environment when checking secrets")
    parser.add_argument(
        "--enable-mutation",
        action="append",
        default=[],
        metavar="CLIENT",
        help="Mark a client as write/fix/PR enabled for this read-only status report",
    )
    args = parser.parse_args(argv)

    env = {} if args.no_env else os.environ
    profiles = load_cloud_profiles(args.profiles)
    statuses = [
        classify_cloud_status(
            profile,
            repo_root=args.repo_root,
            env=env,
            command_exists=shutil.which,
            enabled_mutation_clients=set(args.enable_mutation),
        )
        for profile in profiles.values()
    ]

    headers = ["Client", "CLI", "Workflow", "Review", "Write", "Status", "Blockers"]
    widths = [16, 5, 8, 8, 8, 18, 40]
    print(_row(headers, widths))
    print(_row(["-" * len(header) for header in headers], widths))
    for status in statuses:
        blockers = "; ".join(status.blockers) if status.blockers else "-"
        print(
            _row(
                [
                    status.display_name,
                    _yes_no(status.local_cli_present),
                    _yes_no(status.workflow_present),
                    _yes_no(status.cloud_review_ready),
                    "enabled" if status.cloud_mutation_enabled else "disabled",
                    status.status,
                    blockers,
                ],
                widths,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Update onboarding docs and data**

Edit `skills/onboard/SKILL.md`:

```markdown
| `--cloud` | Show read-only cloud execution readiness for Codex, Claude, Gemini, and Copilot |
| `--cloud --client copilot` | Show setup guidance for one cloud execution client |
| `--cloud --mode review` | Check read/review/plan readiness without enabling writes |
| `--cloud --mode write` | Check write/fix/PR prerequisites; does not store secrets |
```

Edit `skills/onboard/references/mode-status.md` and add these rows to the status table:

```markdown
| AI cloud clients | Run `python skills/onboard/scripts/cloud_status.py --repo-root ~/Projects/Augur` |
| Cloud review mode | Ready when profile, workflow/app, and required credentials are present |
| Cloud write mode | Disabled unless the client is explicitly opted in |
```

Edit `skills/onboard/references/mode-connect.md` and change the supported platform sentence to:

```markdown
Add a new platform to an existing Augur installation. Supported platforms: `obsidian`, `vscode`, `cursor`, `claude-code`, `codex`, `gemini`, `copilot`.
```

Edit `skills/onboard/references/platform-detection.md` and add:

```markdown
| `copilot --version` succeeds or `~/.copilot/` exists | copilot |
| GitHub suggested actors include `copilot-swe-agent` | copilot cloud agent ready |
```

Edit `skills/onboard/augur/data/platforms.yaml` and add:

```yaml
  copilot:
    detection:
      - "~/.copilot/"
      - "copilot --version"
      - "VS Code GitHub Copilot extension"
    mcp_config:
      - "~/.copilot/mcp-config.json"
      - ".vscode/mcp.json"
    cloud:
      profile: copilot
      default_mode: review
      mutation_default: false
    getting_started: >
      Augur is installed for GitHub Copilot. Review mode is the default.
      Cloud write/PR creation requires explicit Copilot cloud agent enablement.
```

- [ ] **Step 5: Run onboarding tests**

Run:

```bash
python -m pytest skills/onboard/tests/test_cloud_status.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit the onboarding matrix**

Run:

```bash
git add skills/onboard
git commit -m "feat(onboard): add cloud execution status"
```

Expected: commit succeeds.

---

## Task 3: Copilot Plugin-Pack Target

**Files:**
- Create: `skills/plugin-pack/scripts/formatters/copilot.py`
- Create: `skills/plugin-pack/augur/tests/test_copilot_formatter.py`
- Modify: `skills/plugin-pack/scripts/profiles.py`
- Modify: `skills/plugin-pack/scripts/formatters/__init__.py`
- Modify: `skills/plugin-pack/scripts/plugin_assembler.py`
- Modify: `skills/plugin-pack/SKILL.md`
- Modify: `skills/plugin-pack/augur/tests/test_profiles.py`
- Modify: `skills/plugin-pack/augur/tests/test_assembler.py`

- [ ] **Step 1: Write failing formatter tests**

Create `skills/plugin-pack/augur/tests/test_copilot_formatter.py`:

```python
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPTS_DIR = PROJECT_ROOT / "skills" / "plugin-pack" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def test_plugin_dir_uses_github_layout(tmp_path):
    from formatters.copilot import CopilotFormatter

    assert CopilotFormatter().plugin_dir(tmp_path / "build") == tmp_path / "build" / ".github"


def test_write_manifest_creates_copilot_instruction_files(tmp_path):
    from formatters.copilot import CopilotFormatter

    plugin_dir = tmp_path / ".github"
    plugin_dir.mkdir()
    CopilotFormatter().write_manifest(plugin_dir, "1.2.3")

    instructions = (plugin_dir / "copilot-instructions.md").read_text(encoding="utf-8")
    agent = (plugin_dir / "agents" / "augur.agent.md").read_text(encoding="utf-8")

    assert "AUGUR-GENERATED" in instructions
    assert "review-first" in instructions
    assert agent.startswith("---\n")
    assert "name: augur" in agent


def test_write_skills_creates_github_agent_skills(tmp_path):
    from formatters.copilot import CopilotFormatter

    plugin_dir = tmp_path / ".github"
    plugin_dir.mkdir()
    CopilotFormatter().write_skills(plugin_dir, {"ask": "---\nname: ask\n---\nAsk body\n"})

    assert (plugin_dir / "skills" / "ask" / "SKILL.md").exists()
    assert "Ask body" in (plugin_dir / "skills" / "ask" / "SKILL.md").read_text(encoding="utf-8")


def test_write_commands_creates_prompt_files(tmp_path):
    from formatters.copilot import CopilotFormatter

    plugin_dir = tmp_path / ".github"
    plugin_dir.mkdir()
    CopilotFormatter().write_commands(
        plugin_dir,
        {"ask": {"description": "Ask Augur", "body": "Use Augur ask."}},
    )

    prompt = plugin_dir / "prompts" / "augur-ask.prompt.md"
    content = prompt.read_text(encoding="utf-8")

    assert content.startswith("---\n")
    assert "description: Ask Augur" in content
    assert "Use Augur ask." in content


def test_install_copies_only_github_assets(tmp_path):
    from formatters.copilot import CopilotFormatter

    output = tmp_path / "build"
    source = output / ".github"
    source.mkdir(parents=True)
    (source / "copilot-instructions.md").write_text("generated\n", encoding="utf-8")
    (source / "prompts").mkdir()
    (source / "prompts" / "augur-ask.prompt.md").write_text("ask\n", encoding="utf-8")

    repo = tmp_path / "repo"
    (repo / ".github").mkdir(parents=True)
    (repo / ".github" / "user-owned.md").write_text("keep\n", encoding="utf-8")
    (repo / ".github" / "prompts").mkdir()
    (repo / ".github" / "prompts" / "user.prompt.md").write_text("keep prompt\n", encoding="utf-8")

    ok = CopilotFormatter().install(output, "1.0.0", install_root=repo)

    assert ok is True
    assert (repo / ".github" / "copilot-instructions.md").read_text(encoding="utf-8") == "generated\n"
    assert (repo / ".github" / "prompts" / "augur-ask.prompt.md").read_text(encoding="utf-8") == "ask\n"
    assert (repo / ".github" / "user-owned.md").read_text(encoding="utf-8") == "keep\n"
    assert (repo / ".github" / "prompts" / "user.prompt.md").read_text(encoding="utf-8") == "keep prompt\n"
```

- [ ] **Step 2: Run the Copilot formatter tests to verify they fail**

Run:

```bash
python -m pytest skills/plugin-pack/augur/tests/test_copilot_formatter.py -v
```

Expected: FAIL because `formatters.copilot` is missing.

- [ ] **Step 3: Implement the Copilot formatter**

Create `skills/plugin-pack/scripts/formatters/copilot.py`:

```python
"""Copilot formatter - produces GitHub Copilot repository assets."""
from __future__ import annotations

import logging
import shutil
from pathlib import Path

from .base import BaseFormatter

logger = logging.getLogger(__name__)
GENERATED_MARKER = "<!-- AUGUR-GENERATED source=plugin-pack/copilot -->"


class CopilotFormatter(BaseFormatter):
    """Format assembled plugin output as Copilot-native .github assets."""

    def plugin_dir(self, output_dir: Path) -> Path:
        return output_dir / ".github"

    def write_manifest(self, plugin_dir: Path, version: str) -> None:
        (plugin_dir / "agents").mkdir(parents=True, exist_ok=True)
        instructions = f"""{GENERATED_MARKER}
# Augur for GitHub Copilot

Augur is a local-first second brain and automation system.

Use Augur in review-first mode by default:
- answer questions about repository context
- review pull requests
- prepare implementation plans
- avoid write, commit, push, or pull request creation unless the user explicitly asks for a mutation mode

Prefer Augur MCP tools when available. Use repository skills under `.github/skills/` when they match the task.
"""
        (plugin_dir / "copilot-instructions.md").write_text(instructions, encoding="utf-8")

        agent = f"""---
name: augur
description: Augur review-first cloud agent for repository planning, review, and second-brain context.
---
{GENERATED_MARKER}

# Augur Agent

Default to read, review, and plan modes.

Before writing files, committing, pushing, or creating pull requests, require explicit user intent for fix, commit, or PR mode.
"""
        (plugin_dir / "agents" / "augur.agent.md").write_text(agent, encoding="utf-8")

    def write_mcp_config(self, plugin_dir: Path, project_root: Path, python_path: str) -> None:
        setup = f"""{GENERATED_MARKER}
# Augur MCP for Copilot

Project root: `{project_root}`

Use this MCP server entry when configuring Copilot CLI or VS Code Copilot MCP:

```json
{{
  "mcpServers": {{
    "augur": {{
      "command": "{python_path}",
      "args": ["-m", "augur_mcp", "--client-id", "copilot"],
      "cwd": "{project_root}",
      "env": {{
        "AUGUR_ROOT": "{project_root}",
        "PYTHONUNBUFFERED": "1",
        "PYTHONPATH": "{project_root}:{project_root}/src/mcp"
      }}
    }}
  }}
}}
```
"""
        (plugin_dir / "copilot-mcp.md").write_text(setup, encoding="utf-8")

    def write_marketplace(self, output_dir: Path, version: str) -> None:
        return None

    def write_skills(self, plugin_dir: Path, skills: dict[str, str]) -> None:
        for name, content in skills.items():
            skill_dir = plugin_dir / "skills" / name
            skill_dir.mkdir(parents=True, exist_ok=True)
            (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")

    def write_commands(self, plugin_dir: Path, commands: dict[str, dict]) -> None:
        prompts_dir = plugin_dir / "prompts"
        prompts_dir.mkdir(parents=True, exist_ok=True)
        for name, cmd in commands.items():
            content = f"""---
description: {cmd["description"]}
---
{GENERATED_MARKER}

{cmd["body"]}

User arguments:
{{{{input}}}}
"""
            (prompts_dir / f"augur-{name}.prompt.md").write_text(content, encoding="utf-8")

    def install(self, output_dir: Path, version: str, *, install_root: Path | None = None) -> bool:
        source = output_dir / ".github"
        if not source.exists():
            logger.warning("Copilot .github source not found at %s", source)
            return False

        if install_root is None:
            from src.config.paths import get_project_root

            install_root = get_project_root()

        target = install_root / ".github"
        target.mkdir(parents=True, exist_ok=True)
        for item in source.iterdir():
            destination = target / item.name
            if item.is_dir():
                shutil.copytree(item, destination, dirs_exist_ok=True)
            else:
                shutil.copy2(item, destination)
        logger.info("  Installed Copilot assets into %s", target)
        return True
```

- [ ] **Step 4: Register the Copilot target**

Edit `skills/plugin-pack/scripts/profiles.py`:

```python
COPILOT_PROFILE = FilterProfile(
    name="copilot",
    hubs=CODEX_PROFILE.hubs,
    excluded_prefixes=CODEX_PROFILE.excluded_prefixes,
    excluded_skills=CODEX_PROFILE.excluded_skills,
    commands=CODEX_PROFILE.commands,
)

_PROFILES = {
    "cowork": COWORK_PROFILE,
    "codex": CODEX_PROFILE,
    "gemini": GEMINI_PROFILE,
    "copilot": COPILOT_PROFILE,
}
```

Edit `skills/plugin-pack/scripts/formatters/__init__.py`:

```python
from .copilot import CopilotFormatter

__all__ = ["BaseFormatter", "CodexFormatter", "CoworkFormatter", "GeminiFormatter", "CopilotFormatter"]
```

Edit `skills/plugin-pack/scripts/plugin_assembler.py`:

```python
from formatters import CopilotFormatter, CoworkFormatter, CodexFormatter, GeminiFormatter

_FORMATTERS: dict[str, type[BaseFormatter]] = {
    "cowork": CoworkFormatter,
    "codex": CodexFormatter,
    "gemini": GeminiFormatter,
    "copilot": CopilotFormatter,
}
```

Edit help text in `skills/plugin-pack/SKILL.md` so the supported targets table includes:

```markdown
| `copilot` | GitHub Copilot | `.github/copilot-instructions.md` + `.github/skills` + `.github/prompts` |
```

- [ ] **Step 5: Update plugin-pack tests**

Add to `skills/plugin-pack/augur/tests/test_profiles.py`:

```python
def test_copilot_profile_matches_codex_initial_scope():
    from profiles import COPILOT_PROFILE, CODEX_PROFILE
    assert COPILOT_PROFILE.hubs == CODEX_PROFILE.hubs
    assert COPILOT_PROFILE.excluded_prefixes == CODEX_PROFILE.excluded_prefixes
    assert COPILOT_PROFILE.excluded_skills == CODEX_PROFILE.excluded_skills
    assert COPILOT_PROFILE.commands == CODEX_PROFILE.commands
```

Add to `test_get_profile_by_name()`:

```python
    assert get_profile("copilot").name == "copilot"
```

Add to `skills/plugin-pack/augur/tests/test_assembler.py`:

```python
def test_assemble_copilot(tmp_path):
    from plugin_assembler import assemble

    output, version = assemble("copilot", tmp_path / "copilot-out")

    assert isinstance(version, str)
    assert (output / ".github" / "copilot-instructions.md").exists()
    assert (output / ".github" / "agents" / "augur.agent.md").exists()
    assert (output / ".github" / "prompts" / "augur-ask.prompt.md").exists()
    assert (output / ".github" / "skills" / "knowledge" / "SKILL.md").exists()


def test_cli_assemble_copilot_from_script_path(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS_DIR / "plugin_assembler.py"),
            "--target",
            "copilot",
            "--output",
            str(tmp_path / "copilot-cli-out"),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "copilot-cli-out" / ".github" / "copilot-instructions.md").exists()
```

- [ ] **Step 6: Run plugin-pack tests**

Run:

```bash
python -m pytest skills/plugin-pack/augur/tests/test_profiles.py skills/plugin-pack/augur/tests/test_copilot_formatter.py skills/plugin-pack/augur/tests/test_assembler.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit Copilot plugin-pack support**

Run:

```bash
git add skills/plugin-pack
git commit -m "feat(plugin-pack): add copilot target"
```

Expected: commit succeeds.

---

## Task 4: Copilot Sync, Detection, and MCP Config

**Files:**
- Modify: `skills/ai/scripts/sync_agents/adapters/copilot.py`
- Modify: `skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py`
- Modify: `config/agents/ide_integrations.yaml`
- Modify: `config/agents/ide_mcp_configs.yaml`
- Modify: `scripts/configure_mcp.py`
- Modify: `tests/packages/augur-mcp/tools/test_sync_agents_mcp_config.py`

- [ ] **Step 1: Update failing tests for Copilot managed files**

Edit `skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py`:

```python
    def test_copilot_managed_files_track_generated_cloud_dirs(self):
        files = CopilotAdapter().get_managed_files()
        assert ".github/instructions/" in files
        assert ".github/prompts/" in files
        assert ".github/agents/" in files
        assert ".github/skills/" in files
        assert ".github/copilot/" in files
```

Update the cleanup test to create and assert the new directories:

```python
    def test_copilot_cleanup_removes_augur_generated_files_and_legacy_dir(self, tmp_path):
        instructions_dir = tmp_path / ".github" / "instructions"
        prompts_dir = tmp_path / ".github" / "prompts"
        agents_dir = tmp_path / ".github" / "agents"
        skills_dir = tmp_path / ".github" / "skills"
        legacy_dir = tmp_path / ".github" / "copilot"
        for directory in (instructions_dir, prompts_dir, agents_dir, skills_dir, legacy_dir):
            directory.mkdir(parents=True)
            (directory / "managed.md").write_text("generated\n", encoding="utf-8")

        with patch("sync_agents.constants.PROJECT_ROOT", tmp_path):
            deleted = CopilotAdapter().cleanup()

        assert ".github/instructions/managed.md" in deleted
        assert ".github/prompts/managed.md" in deleted
        assert ".github/agents/managed.md" in deleted
        assert ".github/skills/managed.md" in deleted
        assert ".github/copilot/" in deleted
        for directory in (instructions_dir, prompts_dir, agents_dir, skills_dir):
            assert directory.exists()
        assert not legacy_dir.exists()
```

- [ ] **Step 2: Add MCP runtime arg test for Copilot**

Add to `tests/packages/augur-mcp/tools/test_sync_agents_mcp_config.py` in `TestConfigureMcpRuntimeArgs`:

```python
    def test_copilot_cli_config_uses_copilot_client_id(self, project_root):
        from scripts.configure_mcp import _build_augur_server_entry_for_ide

        entry = _build_augur_server_entry_for_ide("copilot_cli", Path("python3"), project_root)

        assert entry["args"] == ["-m", "augur_mcp", "--client-id", "copilot"]
        assert entry["cwd"] == str(project_root)
```

- [ ] **Step 3: Run tests to verify failure**

Run:

```bash
python -m pytest skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py::TestAdapterLifecycle::test_copilot_managed_files_track_generated_cloud_dirs tests/packages/augur-mcp/tools/test_sync_agents_mcp_config.py::TestConfigureMcpRuntimeArgs::test_copilot_cli_config_uses_copilot_client_id -v
```

Expected: FAIL because Copilot managed files and MCP client id are not updated.

- [ ] **Step 4: Update the Copilot sync adapter**

Edit `skills/ai/scripts/sync_agents/adapters/copilot.py`:

```python
    def get_managed_files(self) -> list[str]:
        return [
            ".github/copilot-instructions.md",
            ".github/instructions/",
            ".github/prompts/",
            ".github/agents/",
            ".github/skills/",
            ".github/copilot/",
            ".github/copilot-memory.md",
        ]

    def detect_installed(self) -> bool:
        import glob as _glob
        import shutil as _shutil

        if _shutil.which("copilot"):
            return True

        copilot_extensions = _glob.glob(
            str(Path.home() / ".vscode" / "extensions" / "github.copilot-*")
        )
        return bool(copilot_extensions)
```

- [ ] **Step 5: Enable Copilot in config and MCP registries**

Edit `config/agents/ide_integrations.yaml` under `integrations.copilot`:

```yaml
    enabled: true
    skill_scope: project
    config_paths:
    - ~/.copilot/mcp-config.json
    - .vscode/mcp.json
    managed_files:
    - .github/copilot-instructions.md
    - .github/instructions/
    - .github/prompts/
    - .github/agents/
    - .github/skills/
    - .github/copilot-memory.md
```

Edit `config/agents/ide_mcp_configs.yaml` and add entries under `ides`:

```yaml
  copilot_cli:
    enabled: true
    display_name: GitHub Copilot CLI
    config_format: json
    config_structure: flat
    config_path:
      all: ~/.copilot/mcp-config.json
    server_key: mcpServers
    cli_arg: --copilot-config
    notes: GitHub Copilot CLI MCP config
  vscode_copilot:
    enabled: true
    display_name: VS Code Copilot
    config_format: json
    config_structure: flat
    config_path:
      all: .vscode/mcp.json
    server_key: servers
    cli_arg: --vscode-copilot-config
    notes: Workspace MCP config consumed by VS Code Copilot
```

Edit `scripts/configure_mcp.py`:

```python
_IDE_CLIENT_IDS: dict[str, str] = {
    "claude_desktop": "cowork",
    "claude_code": "claude",
    "cursor": "cursor",
    "windsurf": "windsurf",
    "codex_cli": "codex",
    "copilot_cli": "copilot",
    "vscode_copilot": "copilot",
    "opencode": "opencode",
    "gemini": "gemini",
    "antigravity": "antigravity",
    "cline": "cline",
}
```

- [ ] **Step 6: Run Copilot sync/MCP tests**

Run:

```bash
python -m pytest skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py::TestAdapterLifecycle::test_copilot_managed_files_track_generated_cloud_dirs tests/packages/augur-mcp/tools/test_sync_agents_mcp_config.py::TestConfigureMcpRuntimeArgs::test_copilot_cli_config_uses_copilot_client_id -v
```

Expected: PASS.

- [ ] **Step 7: Commit Copilot sync/MCP support**

Run:

```bash
git add config/agents/ide_integrations.yaml config/agents/ide_mcp_configs.yaml scripts/configure_mcp.py skills/ai/scripts/sync_agents/adapters/copilot.py skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py tests/packages/augur-mcp/tools/test_sync_agents_mcp_config.py
git commit -m "feat(ai): enable copilot sync and mcp"
```

Expected: commit succeeds.

---

## Task 5: Gemini Review-First Cloud Workflow

**Files:**
- Create: `.github/workflows/gemini.yml`
- Create: `tests/test_ai_client_cloud_workflows.py`
- Modify: `config/agents/cloud_execution.yaml`

- [ ] **Step 1: Write workflow regression tests**

Create `tests/test_ai_client_cloud_workflows.py`:

```python
from __future__ import annotations

from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_gemini_workflow_is_review_first():
    workflow = yaml.safe_load((PROJECT_ROOT / ".github" / "workflows" / "gemini.yml").read_text(encoding="utf-8"))

    assert workflow["name"] == "Gemini Review"
    assert "pull_request" in workflow[True]
    assert "issue_comment" in workflow[True]
    permissions = workflow["permissions"]
    assert permissions["contents"] == "read"
    assert permissions["pull-requests"] == "write"
    assert permissions["issues"] == "write"
    assert "push" not in workflow[True]


def test_cloud_profile_points_to_existing_workflows():
    profile = yaml.safe_load((PROJECT_ROOT / "config" / "agents" / "cloud_execution.yaml").read_text(encoding="utf-8"))
    clients = profile["clients"]

    for client in ("codex", "claude", "gemini"):
        workflow = clients[client]["cloud"]["github_workflow"]
        assert (PROJECT_ROOT / workflow).exists(), f"{client} workflow missing: {workflow}"


def test_cloud_profile_keeps_mutation_out_of_default_modes():
    profile = yaml.safe_load((PROJECT_ROOT / "config" / "agents" / "cloud_execution.yaml").read_text(encoding="utf-8"))
    mutation = set(profile["mutation_modes"])

    for client_id, client in profile["clients"].items():
        default_modes = set(client["cloud"]["default_modes"])
        assert not default_modes & mutation, client_id
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
python -m pytest tests/test_ai_client_cloud_workflows.py -v
```

Expected: FAIL because `.github/workflows/gemini.yml` is missing.

- [ ] **Step 3: Add the Gemini review workflow**

Create `.github/workflows/gemini.yml`:

```yaml
name: Gemini Review

on:
  pull_request:
    types: [opened, synchronize, reopened]
  issue_comment:
    types: [created]

permissions:
  contents: read
  pull-requests: write
  issues: write

jobs:
  gemini-review:
    name: Review with Gemini
    if: >-
      github.event_name == 'pull_request' ||
      (
        github.event_name == 'issue_comment' &&
        github.event.issue.pull_request &&
        contains(github.event.comment.body, '@gemini-cli /review')
      )
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Build review prompt
        id: prompt
        uses: actions/github-script@v7
        with:
          script: |
            const body = context.payload.comment?.body || "";
            const extra = body.replace("@gemini-cli /review", "").trim();
            const prompt = [
              "You are reviewing this Augur pull request in read/review mode.",
              "Do not commit, push, create branches, or create pull requests.",
              "Focus on bugs, regressions, missing tests, and unsafe cloud-execution changes.",
              extra ? `Additional user context: ${extra}` : ""
            ].filter(Boolean).join("\n");
            core.setOutput("text", prompt);

      - name: Run Gemini CLI review
        id: gemini
        uses: google-github-actions/run-gemini-cli@v0
        with:
          gemini_api_key: ${{ secrets.GEMINI_API_KEY }}
          prompt: ${{ steps.prompt.outputs.text }}
          settings: |
            {
              "tools": {
                "core": ["read_file", "grep_search", "glob", "list_directory"]
              }
            }

      - name: Publish Gemini review comment
        if: ${{ always() && steps.pr.outputs.number != '' }}
        uses: actions/github-script@v7
        env:
          PR_NUMBER: ${{ steps.pr.outputs.number }}
          GEMINI_SUMMARY: ${{ steps.gemini.outputs.summary }}
          GEMINI_ERROR: ${{ steps.gemini.outputs.error }}
        with:
          script: |
            await github.rest.issues.createComment({
              owner: context.repo.owner,
              repo: context.repo.repo,
              issue_number: Number(process.env.PR_NUMBER),
              body: ["## Gemini Review", process.env.GEMINI_SUMMARY || "See workflow run for details."].join("\n\n"),
            });
```

- [ ] **Step 4: Run workflow regression tests**

Run:

```bash
python -m pytest tests/test_ai_client_cloud_workflows.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit Gemini workflow**

Run:

```bash
git add .github/workflows/gemini.yml tests/test_ai_client_cloud_workflows.py config/agents/cloud_execution.yaml
git commit -m "feat(gemini): add review cloud workflow"
```

Expected: commit succeeds.

---

## Task 6: Final Verification and Surface Checks

**Files:**
- No new files unless a previous task exposes a verified regression.

- [ ] **Step 1: Run focused Python tests**

Run:

```bash
python -m pytest \
  skills/ai/augur/tests/test_cloud_execution.py \
  skills/onboard/tests/test_cloud_status.py \
  skills/plugin-pack/augur/tests/test_profiles.py \
  skills/plugin-pack/augur/tests/test_copilot_formatter.py \
  skills/plugin-pack/augur/tests/test_assembler.py \
  tests/test_ai_client_cloud_workflows.py \
  -v
```

Expected: PASS.

- [ ] **Step 2: Run focused MCP/config tests**

Run:

```bash
python -m pytest \
  tests/packages/augur-mcp/tools/test_sync_agents_mcp_config.py::TestConfigureMcpRuntimeArgs \
  tests/scripts/test_configure_mcp_cli.py \
  -v
```

Expected: PASS.

- [ ] **Step 3: Verify plugin assembly for all four clients**

Run:

```bash
python skills/plugin-pack/scripts/plugin_assembler.py --target codex --output /tmp/augur-codex-cloud-check
python skills/plugin-pack/scripts/plugin_assembler.py --target gemini --output /tmp/augur-gemini-cloud-check
python skills/plugin-pack/scripts/plugin_assembler.py --target copilot --output /tmp/augur-copilot-cloud-check
```

Expected:

```text
Assembled codex plugin
Assembled gemini plugin
Assembled copilot plugin
```

The version text may differ, but each command must exit 0 and write its output directory.

- [ ] **Step 4: Verify cloud status output**

Run:

```bash
python skills/onboard/scripts/cloud_status.py --repo-root "$(pwd)" --no-env
```

Expected:

```text
Client            CLI    Workflow  Review    Write     Status
```

The rows should include OpenAI Codex, Claude Code, Gemini, and GitHub Copilot. Missing secrets or GitHub Apps should be reported as blockers, not hidden.

- [ ] **Step 5: Check generated paths without installing**

Run:

```bash
test -f /tmp/augur-copilot-cloud-check/.github/copilot-instructions.md
test -f /tmp/augur-copilot-cloud-check/.github/agents/augur.agent.md
test -f /tmp/augur-copilot-cloud-check/.github/prompts/augur-ask.prompt.md
test -f /tmp/augur-copilot-cloud-check/.github/skills/knowledge/SKILL.md
```

Expected: all `test -f` commands exit 0.

- [ ] **Step 6: Commit any verification fixes**

If verification required a code or test fix, commit the focused fix:

```bash
git status --short
git add config/agents/cloud_execution.yaml skills/ai/augur/lib/cloud_execution.py
git commit -m "fix(ai): harden cloud execution support"
```

Expected: commit succeeds when files changed. If no files changed, skip the commit.

---

## Self-Review Checklist

- Spec coverage: This plan covers the shared cloud profile, read/review default, mutation opt-in, all four clients, Copilot first-class packaging/sync/MCP, onboarding status, Gemini cloud workflow, and status normalization for Claude/Codex/Gemini.
- Deliberate exclusions: Dashboard/Browse UI is excluded from phase 1 because the spec framed it as eventual visibility and this phase creates the MCP/library-shaped status contract first.
- Work-laptop safety: No task stores secrets in the repo. Mutation stays disabled unless a client is explicitly opted in.
- Path policy: Config lives under `config/agents`, code under `skills/ai` and `skills/onboard`, GitHub workflows under `.github/workflows`, and generated Copilot surfaces under `.github`.
- Verification: Each implementation task has failing tests before code and a focused commit after passing tests.
