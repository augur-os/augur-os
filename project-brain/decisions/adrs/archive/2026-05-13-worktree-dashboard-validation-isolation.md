# Worktree Dashboard Validation Isolation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Implements:** ADR-737 - Worktree Dashboard Validation Isolation

**Goal:** Make worktree dashboard validation fully scoped to the current worktree so it can run build, MCP, browser, and merge checks without moving the main visible browser or mutating main lifecycle state.

**Architecture:** Add a shared Python `AugurDashboardInstance` resolver, propagate its metadata through preflight, and require lifecycle/build/heal/browser paths to resolve an instance before mutating state. Main remains the repair-capable visible control plane; worktrees default to headless validation-only behavior with explicit opt-in interactive debug.

**Tech Stack:** Python 3.12, PowerShell-safe repo scripts, Next.js 16 dashboard, Jest/jsdom, existing Augur slash-command and auto-loop verification surfaces.

---

## File Structure

Create:

- `src/lib/dashboard_instance.py` - shared resolver and path helpers for main/worktree/isolated dashboard instances.
- `scripts/dashboard_instance.py` - JSON CLI wrapper for Node scripts and diagnostics.
- `tests/src/test_dashboard_instance.py` - resolver unit tests.
- `tests/scripts/test_dashboard_lifecycle_instances.py` - lifecycle state isolation tests.
- `apps/dashboard/lib/visible-surface-policy.ts` - browser/IDE surface guard for dashboard client code.
- `tests/dashboard/lib/visible-surface-policy.test.ts` - policy unit tests.
- `tests/daemon/test_self_heal_worktree_policy.py` - worktree self-heal validation-only tests.

Modify:

- `scripts/worktree_preflight.py` - append instance metadata to the preflight JSON contract.
- `tests/scripts/test_worktree_preflight.py` - assert preflight instance fields.
- `apps/dashboard/lib/mcp/preflight.ts` - type instance fields for dashboard MCP bridge callers.
- `tests/dashboard/lib/mcp-preflight.test.ts` - assert parsed preflight preserves instance metadata.
- `apps/dashboard/scripts/start-dev.mjs` - export `AUGUR_INSTANCE_*` and `NEXT_PUBLIC_AUGUR_*` policy env values.
- `tests/scripts/test_dashboard_start_dev.py` - text regression tests for env propagation.
- `shared-vault/skills/daemon/scripts/dashboard_lifecycle.py` - scope state, gates, logs, crash tracking, and CLI commands by resolved instance.
- `apps/dashboard/scripts/build-lock.mjs` - resolve instance, scope build lock path, and pass instance target to lifecycle.
- `shared-vault/skills/daemon/scripts/monitor/process.py` - call lifecycle with explicit instance/main target for production monitor.
- `shared-vault/skills/daemon/scripts/cleanup_processes.py` - pass explicit instance/main target to lifecycle gate.
- `apps/dashboard/hooks/useMcpHealth.ts` - remove visible navigation and IDE prompt actions when policy denies them.
- `tests/dashboard/hooks/useMcpHealth.test.ts` - extend tests around toast action suppression.
- `shared-vault/skills/daemon/scripts/ops/self_heal.py` - replace worktree skip with detect-and-report validation-only behavior.
- `shared-vault/skills/platform-admin/commands/dev-build.md` - document `--target current-worktree` and scoped artifact reporting.
- `shared-vault/skills/platform-admin/commands/dev-debug.md` - document explicit worktree repair/interactive debug behavior.
- `shared-vault/skills/platform-admin/commands/dev-merge.md` - require source-worktree validation before merge and main validation after merge.
- Generated agent exports after sync: `.codex/skills/*`, `.agents/skills/*`, and `docs/generated/adr-index.md` may update via the required ADR/sync hooks.

Verification commands in this plan are expressed through Augur slash/auto-loop surfaces. Do not run raw `pytest`, `pnpm test`, `pnpm dev`, or manual dashboard restarts during execution.

---

### Task 1: Dashboard Instance Resolver

**Files:**
- Create: `src/lib/dashboard_instance.py`
- Create: `scripts/dashboard_instance.py`
- Create: `tests/src/test_dashboard_instance.py`

- [ ] **Step 1: Write the failing resolver tests**

Add `tests/src/test_dashboard_instance.py`:

```python
from pathlib import Path

from src.lib.dashboard_instance import (
    DEFAULT_DASHBOARD_PORT,
    DEFAULT_MCP_PORT,
    AugurDashboardInstance,
    resolve_dashboard_instance,
)


def test_main_checkout_resolves_to_visible_main(tmp_path, monkeypatch):
    repo = tmp_path / "Augur"
    repo.mkdir()
    runtime = tmp_path / "runtime"
    runtime.mkdir()

    monkeypatch.setattr(
        "src.lib.dashboard_instance.resolve_main_repo",
        lambda project_root, marker: project_root,
    )

    instance = resolve_dashboard_instance(repo, runtime_dir=runtime)

    assert instance.instance_id == "main"
    assert instance.kind == "main"
    assert instance.dashboard_port == DEFAULT_DASHBOARD_PORT
    assert instance.mcp_port == DEFAULT_MCP_PORT
    assert instance.browser_mode == "visible_allowed"
    assert instance.heal_policy == "enabled"
    assert instance.visibility_policy == "visible_allowed"
    assert instance.lifecycle_dir == runtime / "daemon" / "dashboard" / "main"
    assert instance.build_lock_dir == runtime / "locks" / "dashboard" / "main"


def test_marker_worktree_resolves_to_validation_instance(tmp_path):
    main_repo = tmp_path / "Augur"
    worktree = tmp_path / "Augur-adr-737"
    runtime = tmp_path / "runtime"
    main_repo.mkdir()
    worktree.mkdir()
    (worktree / ".augur-worktree.yaml").write_text(
        "\n".join(
            [
                "worktree: true",
                "name: adr-737",
                f"main_repo: {main_repo}",
                "dashboard_port: 3004",
                "mcp_port: 8084",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    instance = resolve_dashboard_instance(worktree, runtime_dir=runtime)

    assert instance.instance_id == "worktree:adr-737"
    assert instance.kind == "worktree"
    assert instance.name == "adr-737"
    assert instance.project_root == worktree.resolve()
    assert instance.main_repo == main_repo.resolve()
    assert instance.dashboard_port == 3004
    assert instance.mcp_port == 8084
    assert instance.browser_mode == "headless_only"
    assert instance.heal_policy == "validation_only"
    assert instance.visibility_policy == "no_visible_mutation"
    assert instance.lifecycle_dir == runtime / "daemon" / "dashboard" / "worktrees" / "adr-737"
    assert instance.build_lock_dir == runtime / "locks" / "dashboard" / "worktrees" / "adr-737"


def test_registry_worktree_resolves_when_marker_has_no_ports(tmp_path, monkeypatch):
    main_repo = tmp_path / "Augur"
    worktree = tmp_path / "Augur-adr-737"
    runtime = tmp_path / "runtime"
    main_repo.mkdir()
    worktree.mkdir()
    (runtime / "worktree_registry.yaml").parent.mkdir(parents=True)
    (runtime / "worktree_registry.yaml").write_text(
        "\n".join(
            [
                "worktrees:",
                f"  '{worktree.resolve()}':",
                "    name: adr-737",
                "    dashboard_port: 3005",
                "    mcp_port: 8085",
                "    branch: adr-737",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (worktree / ".augur-worktree.yaml").write_text(
        f"worktree: true\nmain_repo: {main_repo}\n",
        encoding="utf-8",
    )

    instance = resolve_dashboard_instance(worktree, runtime_dir=runtime)

    assert instance.instance_id == "worktree:adr-737"
    assert instance.dashboard_port == 3005
    assert instance.mcp_port == 8085
    assert instance.branch == "adr-737"


def test_unregistered_non_main_checkout_fails_closed_as_isolated(tmp_path, monkeypatch):
    repo = tmp_path / "Augur-detached"
    main_repo = tmp_path / "Augur"
    runtime = tmp_path / "runtime"
    repo.mkdir()
    main_repo.mkdir()

    monkeypatch.setattr(
        "src.lib.dashboard_instance.resolve_main_repo",
        lambda project_root, marker: main_repo,
    )

    instance = resolve_dashboard_instance(repo, runtime_dir=runtime)

    assert instance.kind == "isolated"
    assert instance.instance_id.startswith("isolated:")
    assert instance.dashboard_port == DEFAULT_DASHBOARD_PORT
    assert instance.mcp_port == DEFAULT_MCP_PORT
    assert instance.browser_mode == "headless_only"
    assert instance.heal_policy == "disabled"
    assert instance.visibility_policy == "no_visible_mutation"
```

- [ ] **Step 2: Verify the new tests fail through the Python auto-loop surface**

Run:

```text
/auto-test-pytest tests/src/test_dashboard_instance.py
```

Expected:

```text
FAIL: ModuleNotFoundError: No module named 'src.lib.dashboard_instance'
```

- [ ] **Step 3: Implement the resolver**

Create `src/lib/dashboard_instance.py`:

```python
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from src.config.paths import get_runtime_dir

DEFAULT_DASHBOARD_PORT = 3000
DEFAULT_MCP_PORT = 8080

InstanceKind = Literal["main", "worktree", "isolated"]
BrowserMode = Literal["visible_allowed", "headless_only", "isolated_visible"]
HealPolicy = Literal["enabled", "validation_only", "disabled"]
VisibilityPolicy = Literal["visible_allowed", "no_visible_mutation"]


@dataclass(frozen=True)
class AugurDashboardInstance:
    instance_id: str
    kind: InstanceKind
    name: str
    project_root: Path
    main_repo: Path
    branch: str
    dashboard_port: int
    mcp_port: int
    runtime_dir: Path
    lifecycle_dir: Path
    build_lock_dir: Path
    browser_artifact_dir: Path
    browser_mode: BrowserMode
    heal_policy: HealPolicy
    visibility_policy: VisibilityPolicy

    def to_json_dict(self) -> dict[str, object]:
        data = asdict(self)
        for key in ("project_root", "main_repo", "runtime_dir", "lifecycle_dir", "build_lock_dir", "browser_artifact_dir"):
            data[key] = str(data[key])
        return data


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def load_worktree_marker(project_root: Path) -> dict[str, str]:
    marker_path = project_root / ".augur-worktree.yaml"
    if not marker_path.exists():
        return {}
    marker: dict[str, str] = {}
    for raw_line in marker_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        marker[key.strip()] = _strip_quotes(value)
    return marker


def _registry_key(path: str | Path) -> str:
    resolved = str(Path(path).expanduser().resolve())
    return resolved.lower() if os.name == "nt" else resolved


def load_worktree_registry(runtime_dir: Path) -> dict[str, dict[str, object]]:
    registry_path = runtime_dir / "worktree_registry.yaml"
    if not registry_path.exists():
        return {}
    try:
        import yaml

        raw = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    if isinstance(raw, dict) and isinstance(raw.get("worktrees"), dict):
        raw = raw["worktrees"]
    if not isinstance(raw, dict):
        return {}
    return {
        _registry_key(path): entry
        for path, entry in raw.items()
        if isinstance(path, str) and isinstance(entry, dict)
    }


def resolve_main_repo(project_root: Path, marker: dict[str, str]) -> Path:
    if marker.get("main_repo"):
        return Path(marker["main_repo"]).expanduser().resolve()
    try:
        common_dir = subprocess.check_output(
            ["git", "-C", str(project_root), "rev-parse", "--git-common-dir"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return project_root
    common_path = (project_root / common_dir).resolve() if not os.path.isabs(common_dir) else Path(common_dir).resolve()
    return common_path.parent if common_path.name == ".git" else project_root


def _branch(project_root: Path, registry_entry: dict[str, object]) -> str:
    if isinstance(registry_entry.get("branch"), str) and registry_entry["branch"]:
        return str(registry_entry["branch"])
    try:
        result = subprocess.run(
            ["git", "-C", str(project_root), "rev-parse", "--abbrev-ref", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
        )
    except Exception:
        return "unknown"
    return result.stdout.strip() or "unknown"


def _safe_name(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in value.strip())
    return cleaned.strip("-_") or "unnamed"


def _instance_dirs(runtime_dir: Path, kind: InstanceKind, name: str) -> tuple[Path, Path, Path]:
    if kind == "main":
        suffix = Path("main")
    elif kind == "worktree":
        suffix = Path("worktrees") / _safe_name(name)
    else:
        suffix = Path("isolated") / _safe_name(name)
    return (
        runtime_dir / "daemon" / "dashboard" / suffix,
        runtime_dir / "locks" / "dashboard" / suffix,
        runtime_dir / "browser-verification" / suffix,
    )


def resolve_dashboard_instance(
    project_root: Path,
    *,
    runtime_dir: Path | None = None,
    explicit_instance: str | None = None,
    interactive: bool = False,
) -> AugurDashboardInstance:
    project_root = project_root.expanduser().resolve()
    runtime_dir = (runtime_dir or get_runtime_dir()).expanduser().resolve()
    marker = load_worktree_marker(project_root)
    main_repo = resolve_main_repo(project_root, marker).expanduser().resolve()
    registry_entry = load_worktree_registry(runtime_dir).get(_registry_key(project_root), {})
    marker_says_worktree = marker.get("worktree", "").lower() == "true"
    is_worktree = marker_says_worktree or project_root != main_repo

    if explicit_instance:
        instance_id = explicit_instance
    elif not is_worktree:
        instance_id = "main"
    elif marker.get("name") or registry_entry.get("name"):
        instance_id = f"worktree:{_safe_name(str(marker.get('name') or registry_entry.get('name')))}"
    else:
        digest = hashlib.sha1(str(project_root).encode("utf-8")).hexdigest()[:10]
        instance_id = f"isolated:{digest}"

    if instance_id == "main":
        kind: InstanceKind = "main"
        name = "main"
    elif instance_id.startswith("worktree:"):
        kind = "worktree"
        name = _safe_name(instance_id.split(":", 1)[1])
    else:
        kind = "isolated"
        name = _safe_name(instance_id.split(":", 1)[-1])

    dashboard_port = int(marker.get("dashboard_port") or registry_entry.get("dashboard_port") or DEFAULT_DASHBOARD_PORT)
    mcp_port = int(marker.get("mcp_port") or registry_entry.get("mcp_port") or DEFAULT_MCP_PORT)
    lifecycle_dir, build_lock_dir, browser_artifact_dir = _instance_dirs(runtime_dir, kind, name)

    if kind == "main":
        browser_mode: BrowserMode = "visible_allowed"
        heal_policy: HealPolicy = "enabled"
        visibility_policy: VisibilityPolicy = "visible_allowed"
    elif kind == "worktree":
        browser_mode = "isolated_visible" if interactive else "headless_only"
        heal_policy = "validation_only"
        visibility_policy = "no_visible_mutation"
    else:
        browser_mode = "headless_only"
        heal_policy = "disabled"
        visibility_policy = "no_visible_mutation"

    return AugurDashboardInstance(
        instance_id=instance_id,
        kind=kind,
        name=name,
        project_root=project_root,
        main_repo=main_repo,
        branch=_branch(project_root, registry_entry),
        dashboard_port=dashboard_port,
        mcp_port=mcp_port,
        runtime_dir=runtime_dir,
        lifecycle_dir=lifecycle_dir,
        build_lock_dir=build_lock_dir,
        browser_artifact_dir=browser_artifact_dir,
        browser_mode=browser_mode,
        heal_policy=heal_policy,
        visibility_policy=visibility_policy,
    )
```

- [ ] **Step 4: Add the CLI wrapper**

Create `scripts/dashboard_instance.py`:

```python
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.lib.dashboard_instance import resolve_dashboard_instance


def main() -> int:
    parser = argparse.ArgumentParser(description="Resolve the Augur dashboard instance for a checkout.")
    parser.add_argument("--root", default=os.getcwd())
    parser.add_argument("--runtime-dir")
    parser.add_argument("--instance")
    parser.add_argument("--interactive", action="store_true")
    args = parser.parse_args()

    instance = resolve_dashboard_instance(
        Path(args.root),
        runtime_dir=Path(args.runtime_dir) if args.runtime_dir else None,
        explicit_instance=args.instance,
        interactive=args.interactive,
    )
    print(json.dumps(instance.to_json_dict(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Verify resolver tests pass**

Run:

```text
/auto-test-pytest tests/src/test_dashboard_instance.py
```

Expected:

```text
PASS tests/src/test_dashboard_instance.py
```

- [ ] **Step 6: Commit Task 1**

Commit:

```text
git add src/lib/dashboard_instance.py scripts/dashboard_instance.py tests/src/test_dashboard_instance.py
git commit -m "feat(dashboard): resolve scoped dashboard instances"
```

---

### Task 2: Preflight Propagation

**Files:**
- Modify: `scripts/worktree_preflight.py`
- Modify: `tests/scripts/test_worktree_preflight.py`
- Modify: `apps/dashboard/lib/mcp/preflight.ts`
- Modify: `tests/dashboard/lib/mcp-preflight.test.ts`
- Modify: `apps/dashboard/scripts/start-dev.mjs`
- Modify: `tests/scripts/test_dashboard_start_dev.py`

- [ ] **Step 1: Add failing Python preflight assertions**

Append to `tests/scripts/test_worktree_preflight.py`:

```python
def test_build_contract_includes_instance_metadata_for_worktree(tmp_path, monkeypatch):
    worktree_root = tmp_path / "Augur-adr-737"
    main_repo = tmp_path / "Augur"
    runtime_dir = tmp_path / "runtime"
    worktree_root.mkdir()
    main_repo.mkdir()
    (worktree_root / ".augur-worktree.yaml").write_text(
        f"worktree: true\nname: adr-737\nmain_repo: {main_repo}\ndashboard_port: 3006\nmcp_port: 8086\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(worktree_preflight, "_resolve_python_path", lambda _root: worktree_root / ".venv" / "Scripts" / "python.exe")
    monkeypatch.setattr(worktree_preflight, "_resolve_dev_hubs", lambda *_args: None)
    monkeypatch.setattr(worktree_preflight, "_ensure_dashboard_dependencies", lambda *_args: True)
    monkeypatch.setattr(worktree_preflight, "_repo_local_sync_output_paths", lambda _root: [])
    monkeypatch.setattr(worktree_preflight, "_verify_worktree_sync_outputs", lambda *_args: (True, "ok"))
    monkeypatch.setattr(worktree_preflight, "_run_sync_bootstrap", lambda *_args: True)
    monkeypatch.setattr(worktree_preflight, "_ensure_symlink", lambda target, source, *_args: target.parent.mkdir(parents=True, exist_ok=True) or target.write_text("", encoding="utf-8") or True)
    monkeypatch.setattr("src.config.paths.get_runtime_dir", lambda: runtime_dir)
    monkeypatch.setattr(worktree_preflight, "get_runtime_dir", lambda: runtime_dir, raising=False)

    (worktree_root / ".venv" / "Scripts").mkdir(parents=True)
    (worktree_root / ".venv" / "Scripts" / "python.exe").write_text("", encoding="utf-8")
    (worktree_root / ".venv" / "Scripts" / "ruff.exe").write_text("", encoding="utf-8")
    (worktree_root / "apps" / "dashboard" / "node_modules" / ".bin").mkdir(parents=True)
    (worktree_root / "apps" / "dashboard" / "node_modules" / ".bin" / "next").write_text("", encoding="utf-8")

    report = worktree_preflight.build_contract(worktree_root, "worktree", repair=False)

    assert report["instance_id"] == "worktree:adr-737"
    assert report["instance_kind"] == "worktree"
    assert report["browser_mode"] == "headless_only"
    assert report["heal_policy"] == "validation_only"
    assert report["visibility_policy"] == "no_visible_mutation"
    assert report["lifecycle_dir"].endswith("daemon/dashboard/worktrees/adr-737")
    assert report["build_lock_dir"].endswith("locks/dashboard/worktrees/adr-737")
```

- [ ] **Step 2: Add failing dashboard preflight type assertions**

Append to `tests/dashboard/lib/mcp-preflight.test.ts`:

```typescript
it("preserves instance metadata from worktree preflight", () => {
  (spawnSync as jest.Mock).mockReturnValue({
    stdout: JSON.stringify({
      verify_passed: true,
      instance_id: "worktree:adr-737",
      instance_kind: "worktree",
      browser_mode: "headless_only",
      heal_policy: "validation_only",
      visibility_policy: "no_visible_mutation",
      lifecycle_dir: "/runtime/daemon/dashboard/worktrees/adr-737",
      build_lock_dir: "/runtime/locks/dashboard/worktrees/adr-737",
      browser_artifact_dir: "/runtime/browser-verification/worktrees/adr-737",
    }),
    stderr: "",
  });

  expect(resolvePreflightContract()).toEqual(
    expect.objectContaining({
      instance_id: "worktree:adr-737",
      instance_kind: "worktree",
      browser_mode: "headless_only",
      heal_policy: "validation_only",
      visibility_policy: "no_visible_mutation",
    }),
  );
});
```

- [ ] **Step 3: Verify failures**

Run:

```text
/auto-test-pytest tests/scripts/test_worktree_preflight.py
/auto-test-dashboard tests/dashboard/lib/mcp-preflight.test.ts
```

Expected:

```text
FAIL: missing instance metadata fields
```

- [ ] **Step 4: Extend `worktree_preflight.py`**

Add near imports:

```python
from src.lib.dashboard_instance import resolve_dashboard_instance
```

Add after `ports = _resolve_ports(...)` in `build_contract`:

```python
instance = resolve_dashboard_instance(project_root, runtime_dir=runtime_dir)
```

Add to `report`:

```python
"instance_id": instance.instance_id,
"instance_kind": instance.kind,
"browser_mode": instance.browser_mode,
"heal_policy": instance.heal_policy,
"visibility_policy": instance.visibility_policy,
"lifecycle_dir": str(instance.lifecycle_dir),
"build_lock_dir": str(instance.build_lock_dir),
"browser_artifact_dir": str(instance.browser_artifact_dir),
```

- [ ] **Step 5: Extend dashboard TypeScript contract**

In `apps/dashboard/lib/mcp/preflight.ts`, extend `PreflightContract`:

```typescript
  instance_id?: string;
  instance_kind?: "main" | "worktree" | "isolated";
  browser_mode?: "visible_allowed" | "headless_only" | "isolated_visible";
  heal_policy?: "enabled" | "validation_only" | "disabled";
  visibility_policy?: "visible_allowed" | "no_visible_mutation";
  lifecycle_dir?: string;
  build_lock_dir?: string;
  browser_artifact_dir?: string;
```

- [ ] **Step 6: Propagate env from `start-dev.mjs`**

In `apps/dashboard/scripts/start-dev.mjs`, after `env.AUGUR_MCP_CLIENT_ID = ...`, add:

```javascript
  env.AUGUR_INSTANCE_ID = String(preflight.instance_id ?? (preflight.worktree ? "worktree" : "main"));
  env.AUGUR_INSTANCE_KIND = String(preflight.instance_kind ?? (preflight.worktree ? "worktree" : "main"));
  env.AUGUR_BROWSER_MODE = String(preflight.browser_mode ?? (preflight.worktree ? "headless_only" : "visible_allowed"));
  env.AUGUR_HEAL_POLICY = String(preflight.heal_policy ?? (preflight.worktree ? "validation_only" : "enabled"));
  env.AUGUR_VISIBILITY_POLICY = String(preflight.visibility_policy ?? (preflight.worktree ? "no_visible_mutation" : "visible_allowed"));
  env.NEXT_PUBLIC_AUGUR_INSTANCE_ID = env.AUGUR_INSTANCE_ID;
  env.NEXT_PUBLIC_AUGUR_INSTANCE_KIND = env.AUGUR_INSTANCE_KIND;
  env.NEXT_PUBLIC_AUGUR_VISIBILITY_POLICY = env.AUGUR_VISIBILITY_POLICY;
```

- [ ] **Step 7: Add text regression for env propagation**

Add to `tests/scripts/test_dashboard_start_dev.py`:

```python
def test_start_dev_exports_instance_visibility_policy_to_dashboard():
    text = _start_dev_mjs_text()

    assert "env.AUGUR_INSTANCE_ID" in text
    assert "env.AUGUR_INSTANCE_KIND" in text
    assert "env.AUGUR_VISIBILITY_POLICY" in text
    assert "env.NEXT_PUBLIC_AUGUR_INSTANCE_ID" in text
    assert "env.NEXT_PUBLIC_AUGUR_VISIBILITY_POLICY" in text
```

- [ ] **Step 8: Verify Task 2**

Run:

```text
/auto-test-pytest tests/scripts/test_worktree_preflight.py tests/scripts/test_dashboard_start_dev.py
/auto-test-dashboard tests/dashboard/lib/mcp-preflight.test.ts
```

Expected:

```text
PASS selected preflight and dashboard tests
```

- [ ] **Step 9: Commit Task 2**

Commit:

```text
git add scripts/worktree_preflight.py tests/scripts/test_worktree_preflight.py apps/dashboard/lib/mcp/preflight.ts tests/dashboard/lib/mcp-preflight.test.ts apps/dashboard/scripts/start-dev.mjs tests/scripts/test_dashboard_start_dev.py
git commit -m "feat(dashboard): propagate instance metadata through preflight"
```

---

### Task 3: Scoped Lifecycle State

**Files:**
- Modify: `shared-vault/skills/daemon/scripts/dashboard_lifecycle.py`
- Create: `tests/scripts/test_dashboard_lifecycle_instances.py`

- [ ] **Step 1: Write failing lifecycle isolation tests**

Create `tests/scripts/test_dashboard_lifecycle_instances.py`:

```python
import importlib.util
import sys
from pathlib import Path

from src.lib.dashboard_instance import resolve_dashboard_instance


PROJECT_ROOT = Path(__file__).resolve().parents[2]
LIFECYCLE_PATH = PROJECT_ROOT / "shared-vault" / "skills" / "daemon" / "scripts" / "dashboard_lifecycle.py"


def load_lifecycle():
    spec = importlib.util.spec_from_file_location("dashboard_lifecycle_test", LIFECYCLE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_lifecycle_state_is_scoped_by_instance(tmp_path, monkeypatch):
    lifecycle = load_lifecycle()
    runtime = tmp_path / "runtime"
    repo = tmp_path / "Augur"
    worktree = tmp_path / "Augur-adr-737"
    repo.mkdir()
    worktree.mkdir()
    (worktree / ".augur-worktree.yaml").write_text(
        f"worktree: true\nname: adr-737\nmain_repo: {repo}\ndashboard_port: 3007\nmcp_port: 8087\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(lifecycle, "get_runtime_dir", lambda: runtime)

    main = resolve_dashboard_instance(repo, runtime_dir=runtime)
    wt = resolve_dashboard_instance(worktree, runtime_dir=runtime)

    lifecycle.log_event("dashboard_monitor", "recovery_success", "main ok", instance=main)
    lifecycle.record_crash("dashboard_monitor", "worktree broke", instance=wt)

    assert lifecycle.get_state(instance=main)["state"] == "healthy"
    assert lifecycle.get_state(instance=wt)["state"] == "crashed"
    assert (runtime / "daemon" / "dashboard" / "main" / "state.json").exists()
    assert (runtime / "daemon" / "dashboard" / "worktrees" / "adr-737" / "state.json").exists()


def test_mutating_cli_without_resolvable_instance_fails_closed(tmp_path, monkeypatch, capsys):
    lifecycle = load_lifecycle()
    runtime = tmp_path / "runtime"
    monkeypatch.setattr(lifecycle, "get_runtime_dir", lambda: runtime)
    monkeypatch.chdir(tmp_path)

    exit_code = lifecycle.main(["request-action", "--actor", "build_lock", "--action", "restart", "--reason", "test"])

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "could not resolve dashboard instance" in captured.out.lower()
```

- [ ] **Step 2: Verify failures**

Run:

```text
/auto-test-pytest tests/scripts/test_dashboard_lifecycle_instances.py
```

Expected:

```text
FAIL: dashboard_lifecycle functions do not accept instance targets
```

- [ ] **Step 3: Add instance targeting to lifecycle public functions**

In `dashboard_lifecycle.py`:

1. Add project root scripts path and import:

```python
if str(PROJECT_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from src.lib.dashboard_instance import AugurDashboardInstance, resolve_dashboard_instance
```

2. Replace `_state_file()` and `_gate_lock_file()` with target-aware versions:

```python
def _resolve_instance(
    instance: AugurDashboardInstance | None = None,
    project_root: Path | None = None,
    instance_id: str | None = None,
) -> AugurDashboardInstance:
    if instance is not None:
        return instance
    root = (project_root or Path.cwd()).expanduser().resolve()
    resolved = resolve_dashboard_instance(root, explicit_instance=instance_id)
    if resolved.kind == "isolated" and instance_id is None:
        raise RuntimeError(f"could not resolve dashboard instance for {root}")
    return resolved


def _state_file(instance: AugurDashboardInstance | None = None) -> Path:
    target = instance or _resolve_instance()
    target.lifecycle_dir.mkdir(parents=True, exist_ok=True)
    return target.lifecycle_dir / "state.json"


def _gate_lock_file(instance: AugurDashboardInstance | None = None) -> Path:
    target = instance or _resolve_instance()
    target.lifecycle_dir.mkdir(parents=True, exist_ok=True)
    return target.lifecycle_dir / "gate.lock"
```

3. Thread `instance` through `_read_state`, `_write_state`, `get_state`, `log_event`, `request_action`, `record_crash`, `is_crash_loop`, and `record_healthy_poll`.

Required signatures:

```python
def get_state(*, instance: AugurDashboardInstance | None = None, project_root: Path | None = None, instance_id: str | None = None) -> dict:
def log_event(actor: str, action: str, reason: str, *, instance: AugurDashboardInstance | None = None, project_root: Path | None = None, instance_id: str | None = None, **extra: Any) -> None:
def request_action(actor: str, action: str, reason: str, force: bool = False, *, instance: AugurDashboardInstance | None = None, project_root: Path | None = None, instance_id: str | None = None) -> dict:
def record_crash(actor: str, reason: str, *, instance: AugurDashboardInstance | None = None, project_root: Path | None = None, instance_id: str | None = None) -> dict:
def is_crash_loop(*, instance: AugurDashboardInstance | None = None, project_root: Path | None = None, instance_id: str | None = None) -> bool:
def record_healthy_poll(*, instance: AugurDashboardInstance | None = None, project_root: Path | None = None, instance_id: str | None = None) -> str:
```

Each public function resolves once at entry and passes the resolved instance to private reads/writes/logs.

- [ ] **Step 4: Extend CLI arguments**

Change `main()` to accept an optional argv and add global target flags to each subcommand:

```python
def _add_target_args(command_parser: argparse.ArgumentParser) -> None:
    command_parser.add_argument("--instance")
    command_parser.add_argument("--project-root")


def main(argv: list[str] | None = None) -> int:
    ...
    _add_target_args(ra)
    _add_target_args(le)
    state_parser = sub.add_parser("state", help="Print current state as JSON")
    _add_target_args(state_parser)
    args = parser.parse_args(argv)
```

Before mutating:

```python
try:
    target = _resolve_instance(
        project_root=Path(args.project_root) if getattr(args, "project_root", None) else None,
        instance_id=getattr(args, "instance", None),
    )
except RuntimeError as exc:
    print(json.dumps({"decision": "denied", "reason": str(exc)}))
    return 1
```

- [ ] **Step 5: Verify Task 3**

Run:

```text
/auto-test-pytest tests/scripts/test_dashboard_lifecycle_instances.py
```

Expected:

```text
PASS tests/scripts/test_dashboard_lifecycle_instances.py
```

- [ ] **Step 6: Commit Task 3**

Commit:

```text
git add shared-vault/skills/daemon/scripts/dashboard_lifecycle.py tests/scripts/test_dashboard_lifecycle_instances.py
git commit -m "feat(dashboard): scope lifecycle state by instance"
```

---

### Task 4: Scoped Build Lock and Monitor Calls

**Files:**
- Modify: `apps/dashboard/scripts/build-lock.mjs`
- Modify: `tests/scripts/test_dashboard_start_dev.py`
- Modify: `shared-vault/skills/daemon/scripts/monitor/process.py`
- Modify: `shared-vault/skills/daemon/scripts/cleanup_processes.py`

- [ ] **Step 1: Add failing build-lock text regression**

Append to `tests/scripts/test_dashboard_start_dev.py`:

```python
def test_build_lock_uses_scoped_instance_lock_and_lifecycle_target():
    text = BUILD_LOCK_MJS.read_text(encoding="utf-8")

    assert "resolveDashboardInstance(python)" in text
    assert "instance.build_lock_dir" in text
    assert '"--instance", instance.instance_id' in text
    assert "dashboard_build.lock" in text
```

- [ ] **Step 2: Verify failure**

Run:

```text
/auto-test-pytest tests/scripts/test_dashboard_start_dev.py
```

Expected:

```text
FAIL: scoped build-lock strings are missing
```

- [ ] **Step 3: Update build-lock resolver and lock paths**

In `apps/dashboard/scripts/build-lock.mjs`, after `runtimeDir`:

```javascript
const instance = resolveDashboardInstance(python);
const lockDir = instance.build_lock_dir || path.join(runtimeDir, "locks", "dashboard", "main");
fs.mkdirSync(lockDir, { recursive: true });

const lockFile = path.join(lockDir, "dashboard_build.lock");
const metaFile = path.join(lockDir, "dashboard_build.lock.meta");
```

Add helper:

```javascript
function resolveDashboardInstance(pythonConfig) {
  const resolver = path.join(projectRoot, "scripts", "dashboard_instance.py");
  const result = spawnSync(
    pythonConfig.command,
    [
      ...pythonConfig.args,
      resolver,
      "--root",
      projectRoot,
      "--runtime-dir",
      runtimeDir,
    ],
    {
      cwd: projectRoot,
      env: process.env,
      encoding: "utf8",
    },
  );
  if (result.status !== 0 || !result.stdout.trim()) {
    return { instance_id: "main", build_lock_dir: path.join(runtimeDir, "locks", "dashboard", "main") };
  }
  return JSON.parse(result.stdout);
}
```

Change lifecycle calls:

```javascript
const lifecycleBeforeGate = readLifecycleState(python, instance);
runLifecycleGate(python, command, lifecycleActionFor(lifecycleBeforeGate), instance);
...
restoreLifecycleState(python, lifecycleBeforeGate, instance);
```

Add `--instance` to `runLifecycleGate`, `readLifecycleState`, and the restore inline Python call:

```javascript
"--instance",
instance.instance_id,
```

Inside restore code:

```python
target_instance = sys.argv[3]
current = dashboard_lifecycle.get_state(instance_id=target_instance)
...
dashboard_lifecycle._write_state(restored, instance=dashboard_lifecycle._resolve_instance(instance_id=target_instance))
dashboard_lifecycle.log_event(..., instance_id=target_instance)
```

- [ ] **Step 4: Make monitor and cleanup explicit-main callers**

In `shared-vault/skills/daemon/scripts/monitor/process.py`, replace lifecycle calls without target with main target calls:

```python
dashboard_lifecycle.get_state(instance_id="main")
dashboard_lifecycle.record_healthy_poll(instance_id="main")
dashboard_lifecycle.record_crash("dashboard_monitor", "process gone", instance_id="main")
dashboard_lifecycle.is_crash_loop(instance_id="main")
dashboard_lifecycle.request_action("dashboard_monitor", "restart", "auto-recovery", instance_id="main")
dashboard_lifecycle.log_event("dashboard_monitor", "recovery_success", "...", instance_id="main")
```

In `shared-vault/skills/daemon/scripts/cleanup_processes.py`, pass `instance_id="main"` for production dashboard cleanup gates because this script manages the main dashboard process unless future callers explicitly add worktree target support.

- [ ] **Step 5: Verify Task 4**

Run:

```text
/auto-test-pytest tests/scripts/test_dashboard_start_dev.py
```

Expected:

```text
PASS tests/scripts/test_dashboard_start_dev.py
```

- [ ] **Step 6: Commit Task 4**

Commit:

```text
git add apps/dashboard/scripts/build-lock.mjs tests/scripts/test_dashboard_start_dev.py shared-vault/skills/daemon/scripts/monitor/process.py shared-vault/skills/daemon/scripts/cleanup_processes.py
git commit -m "feat(dashboard): scope build locks to dashboard instances"
```

---

### Task 5: Visible Surface Policy

**Files:**
- Create: `apps/dashboard/lib/visible-surface-policy.ts`
- Create: `tests/dashboard/lib/visible-surface-policy.test.ts`
- Modify: `apps/dashboard/hooks/useMcpHealth.ts`
- Modify: `tests/dashboard/hooks/useMcpHealth.test.ts`

- [ ] **Step 1: Write failing policy tests**

Create `tests/dashboard/lib/visible-surface-policy.test.ts`:

```typescript
import {
  mayUseVisibleSurface,
  resolveVisibleSurfacePolicy,
} from "@/lib/visible-surface-policy";

describe("visible surface policy", () => {
  const originalEnv = process.env.NEXT_PUBLIC_AUGUR_VISIBILITY_POLICY;

  afterEach(() => {
    if (originalEnv === undefined) delete process.env.NEXT_PUBLIC_AUGUR_VISIBILITY_POLICY;
    else process.env.NEXT_PUBLIC_AUGUR_VISIBILITY_POLICY = originalEnv;
  });

  it("allows user-triggered visible actions for main by default", () => {
    delete process.env.NEXT_PUBLIC_AUGUR_VISIBILITY_POLICY;

    expect(mayUseVisibleSurface("navigate", "user-triggered")).toBe(true);
    expect(mayUseVisibleSurface("send-ide-prompt", "user-triggered")).toBe(true);
  });

  it("denies all visible mutations when worktree policy is active", () => {
    process.env.NEXT_PUBLIC_AUGUR_VISIBILITY_POLICY = "no_visible_mutation";

    expect(resolveVisibleSurfacePolicy()).toBe("no_visible_mutation");
    expect(mayUseVisibleSurface("navigate", "validation")).toBe(false);
    expect(mayUseVisibleSurface("send-ide-prompt", "user-triggered")).toBe(false);
  });
});
```

- [ ] **Step 2: Verify failure**

Run:

```text
/auto-test-dashboard tests/dashboard/lib/visible-surface-policy.test.ts
```

Expected:

```text
FAIL: Cannot find module '@/lib/visible-surface-policy'
```

- [ ] **Step 3: Implement policy helper**

Create `apps/dashboard/lib/visible-surface-policy.ts`:

```typescript
export type VisibleSurfacePolicy = "visible_allowed" | "no_visible_mutation";
export type VisibleSurfaceAction = "navigate" | "send-ide-prompt" | "open-window";
export type VisibleSurfaceReason = "user-triggered" | "validation" | "self-heal";

export function resolveVisibleSurfacePolicy(): VisibleSurfacePolicy {
  const raw = process.env.NEXT_PUBLIC_AUGUR_VISIBILITY_POLICY;
  return raw === "no_visible_mutation" ? "no_visible_mutation" : "visible_allowed";
}

export function mayUseVisibleSurface(
  _action: VisibleSurfaceAction,
  reason: VisibleSurfaceReason,
  policy: VisibleSurfacePolicy = resolveVisibleSurfacePolicy(),
): boolean {
  if (policy === "no_visible_mutation") {
    return false;
  }
  return reason === "user-triggered";
}
```

- [ ] **Step 4: Gate MCP health toast actions**

In `apps/dashboard/hooks/useMcpHealth.ts`, import:

```typescript
import { mayUseVisibleSurface } from "@/lib/visible-surface-policy";
```

Build actions before `toast.error`:

```typescript
        const viewAction = mayUseVisibleSurface("navigate", "user-triggered")
          ? {
              label: "View",
              onClick: () => {
                window.location.href = "/brain?tab=mcp";
              },
            }
          : undefined;
        const fixAction = mayUseVisibleSurface("send-ide-prompt", "user-triggered")
          ? {
              label: "Fix Now",
              onClick: async () => {
                try {
                  let promptText = "";
                  let serverContext = { root: "Unknown", home: "Unknown" };
                  try {
                    const tplJson = await mcpCall<{ ok?: boolean; template?: string; context?: { root: string; home: string } }>(
                      "file-read",
                      { promptId: "ide-config-debug" },
                      { fallback: {} },
                    );
                    if (tplJson.ok) {
                      if (tplJson.template) promptText = tplJson.template;
                      if (tplJson.context) serverContext = tplJson.context;
                    }
                  } catch {}
                  const fileSystemPaths = `- Project Root: ${serverContext.root}\n- Home: ${serverContext.home}`;
                  if (promptText) {
                    promptText = promptText
                      .replace(/{{ide_name}}/g, firstIssue.client)
                      .replace("{{config_path}}", firstIssue.server === "(config)" ? "Configuration File" : firstIssue.server)
                      .replace("{{issue_count}}", String(issues.length))
                      .replace(/{{#each issues}}([\s\S]*?){{\/each}}/, (_, block) =>
                        firstIssue.problems.map((p: string) => block.replace("{{this}}", p)).join(""))
                      .replace("{{file_system_paths}}", fileSystemPaths);
                  } else {
                    promptText = `Fix MCP config for ${firstIssue.client}. Errors: ${firstIssue.problems.join(", ")}`;
                  }
                  const result = await mcpCall<{ success?: boolean; ide?: string; error?: string }>(
                    "send-ide-prompt",
                    { prompt: promptText },
                  );
                  if (result.success) toast.success(`Sent to ${result.ide || "IDE"}`);
                  else toast.error(`Failed: ${result.error || "Unknown error"}`);
                } catch {
                  toast.error("Failed to send to IDE");
                }
              },
            }
          : undefined;
```

Pass these into toast:

```typescript
          action: viewAction,
          cancel: fixAction,
```

- [ ] **Step 5: Extend MCP hook test coverage**

Add to `tests/dashboard/hooks/useMcpHealth.test.ts`:

```typescript
import { mayUseVisibleSurface } from "@/lib/visible-surface-policy";

describe("visible surface policy integration", () => {
  it("denies worktree navigation and IDE prompt actions", () => {
    expect(mayUseVisibleSurface("navigate", "validation", "no_visible_mutation")).toBe(false);
    expect(mayUseVisibleSurface("send-ide-prompt", "user-triggered", "no_visible_mutation")).toBe(false);
  });
});
```

- [ ] **Step 6: Verify Task 5**

Run:

```text
/auto-test-dashboard tests/dashboard/lib/visible-surface-policy.test.ts tests/dashboard/hooks/useMcpHealth.test.ts
```

Expected:

```text
PASS selected dashboard tests
```

- [ ] **Step 7: Commit Task 5**

Commit:

```text
git add apps/dashboard/lib/visible-surface-policy.ts tests/dashboard/lib/visible-surface-policy.test.ts apps/dashboard/hooks/useMcpHealth.ts tests/dashboard/hooks/useMcpHealth.test.ts
git commit -m "feat(dashboard): guard visible surface mutations"
```

---

### Task 6: Validation-Only Self-Heal

**Files:**
- Modify: `shared-vault/skills/daemon/scripts/ops/self_heal.py`
- Create: `tests/daemon/test_self_heal_worktree_policy.py`

- [ ] **Step 1: Write failing self-heal policy tests**

Create `tests/daemon/test_self_heal_worktree_policy.py`:

```python
from pathlib import Path
from types import SimpleNamespace

from src.lib.ops_protocol import OpsContext

import importlib.util
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SELF_HEAL_PATH = PROJECT_ROOT / "shared-vault" / "skills" / "daemon" / "scripts" / "ops" / "self_heal.py"


def load_self_heal():
    spec = importlib.util.spec_from_file_location("ops_self_heal_test", SELF_HEAL_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_worktree_scan_reports_validation_only_issue(tmp_path, monkeypatch):
    self_heal = load_self_heal()
    project_root = tmp_path / "Augur-adr-737"
    main_repo = tmp_path / "Augur"
    project_root.mkdir()
    main_repo.mkdir()
    (project_root / ".augur-worktree.yaml").write_text(
        f"worktree: true\nname: adr-737\nmain_repo: {main_repo}\ndashboard_port: 3008\nmcp_port: 8088\n",
        encoding="utf-8",
    )
    finding = SimpleNamespace(
        dedup_key="abc123",
        severity="high",
        message="dashboard error",
        file="apps/dashboard/app/page.tsx",
    )
    monkeypatch.setattr(self_heal, "_is_inside_worktree", lambda _root: True)
    self_heal.healer = SimpleNamespace(scan_for_errors=lambda: [finding])

    result = self_heal.scan(OpsContext(project_root=project_root, config={}, dry_run=False))

    assert result.issues
    assert result.issues[0]["worktree_validation_only"] is True
    assert result.summary == "1 runtime error(s) found in validation-only worktree mode"


def test_worktree_fix_refuses_mutation(tmp_path, monkeypatch):
    self_heal = load_self_heal()
    project_root = tmp_path / "Augur-adr-737"
    project_root.mkdir()
    monkeypatch.setattr(self_heal, "_is_inside_worktree", lambda _root: True)

    result = self_heal.fix(
        OpsContext(project_root=project_root, config={}, dry_run=False),
        [{"entry_key": "abc123", "worktree_validation_only": True}],
    )

    assert result.success is False
    assert "validation-only" in result.summary
    assert result.changes == []
```

- [ ] **Step 2: Verify failure**

Run:

```text
/auto-test-pytest tests/daemon/test_self_heal_worktree_policy.py
```

Expected:

```text
FAIL: current worktree self-heal skips scan and returns success on fix
```

- [ ] **Step 3: Replace worktree skip with validation-only scan**

In `shared-vault/skills/daemon/scripts/ops/self_heal.py`, change `scan()` worktree branch from early skip to:

```python
    worktree_validation_only = _is_inside_worktree(ctx.project_root)
```

Keep scanning when `worktree_validation_only` is true. When building each issue, add:

```python
            "worktree_validation_only": worktree_validation_only,
```

Change the no-issue summary for worktrees:

```python
    if not issues:
        if worktree_validation_only:
            return ScanResult(issues=[], summary="No runtime errors found in validation-only worktree mode", severity="info")
        return ScanResult(issues=[], summary="No runtime errors found", severity="info")
```

Change issue summary for worktrees:

```python
        summary=(
            f"{len(issues)} runtime error(s) found in validation-only worktree mode"
            if worktree_validation_only
            else f"{len(issues)} runtime error(s) found"
        ),
```

- [ ] **Step 4: Refuse mutation in worktree fix**

At the top of `fix()`:

```python
    if _is_inside_worktree(ctx.project_root):
        return FixResult(
            success=False,
            actions=[
                {
                    "entry_key": issue.get("entry_key"),
                    "skipped": True,
                    "reason": "validation-only worktree mode",
                }
                for issue in issues
            ],
            changes=[],
            summary=(
                f"Worktree self-heal is validation-only; reported {len(issues)} issue(s) without mutation"
            ),
        )
```

- [ ] **Step 5: Verify Task 6**

Run:

```text
/auto-test-pytest tests/daemon/test_self_heal_worktree_policy.py
```

Expected:

```text
PASS tests/daemon/test_self_heal_worktree_policy.py
```

- [ ] **Step 6: Commit Task 6**

Commit:

```text
git add shared-vault/skills/daemon/scripts/ops/self_heal.py tests/daemon/test_self_heal_worktree_policy.py
git commit -m "feat(daemon): report worktree self-heal in validation-only mode"
```

---

### Task 7: Command Workflow Contract Updates

**Files:**
- Modify: `shared-vault/skills/platform-admin/commands/dev-build.md`
- Modify: `shared-vault/skills/platform-admin/commands/dev-debug.md`
- Modify: `shared-vault/skills/platform-admin/commands/dev-merge.md`
- Modify generated exports after sync.

- [ ] **Step 1: Update `/dev-build` contract**

Add this section to `shared-vault/skills/platform-admin/commands/dev-build.md`:

```markdown
## Worktree Targeting

When invoked from a registered Augur worktree, `/dev-build` targets the current
worktree instance by default:

- dashboard port comes from `.augur-worktree.yaml` or `worktree_registry.yaml`
- MCP port comes from the same instance record
- lifecycle state and build lock are scoped to `worktree:<name>`
- browser verification uses isolated/headless automation
- the current main browser tab must remain untouched

Use `--target main` only when the user explicitly asks to validate the main
checkout. Use `--interactive` only when the user explicitly wants a separate
visible worktree debug surface.
```

- [ ] **Step 2: Update `/dev-debug` contract**

Add this section to `shared-vault/skills/platform-admin/commands/dev-debug.md`:

```markdown
## Worktree Repair Policy

Worktree debugging is diagnosis-first. A worktree target may collect logs,
console errors, screenshots, MCP debug state, and lifecycle state. It must not
repair main, navigate the main browser, or send IDE update prompts.

Use `--repair` to allow target-scoped repair of the current worktree instance.
Even with `--repair`, the operation may only restart or mutate the resolved
worktree instance.
```

- [ ] **Step 3: Update `/dev-merge` contract**

Add this under the full-mode contract in `shared-vault/skills/platform-admin/commands/dev-merge.md`:

```markdown
## Worktree Dashboard Validation Gate

When `/dev-merge full` starts from an Augur worktree, validate the source
worktree instance before merging:

1. Resolve the source instance from `.augur-worktree.yaml` and
   `worktree_registry.yaml`.
2. Run scoped dashboard/MCP/browser validation against the worktree dashboard
   port and MCP port.
3. Save screenshot, console, lifecycle, and MCP evidence under the worktree
   artifact directory.
4. Do not navigate the main browser tab and do not send IDE update prompts.
5. Block merge on validation failure unless the user explicitly accepts the
   failure with the evidence in view.
6. After merge, validate `main` separately and report a separate main artifact
   set.
```

- [ ] **Step 4: Sync generated command exports**

Run the repo sync surface that regenerates agent command exports:

```text
/dev-sync
```

Expected:

```text
Generated command exports include the new worktree targeting sections.
```

- [ ] **Step 5: Commit Task 7**

Commit:

```text
git add shared-vault/skills/platform-admin/commands/dev-build.md shared-vault/skills/platform-admin/commands/dev-debug.md shared-vault/skills/platform-admin/commands/dev-merge.md .codex/skills .agents/skills docs/generated/skill-manifest.json
git commit -m "docs(workflows): require scoped worktree dashboard validation"
```

---

### Task 8: Full Verification and Browser Proof

**Files:**
- No new source files.
- Verification artifacts under runtime state.

- [ ] **Step 1: Run focused Python auto-loop checks**

Run:

```text
/auto-test-pytest tests/src/test_dashboard_instance.py tests/scripts/test_worktree_preflight.py tests/scripts/test_dashboard_lifecycle_instances.py tests/scripts/test_dashboard_start_dev.py tests/daemon/test_self_heal_worktree_policy.py
```

Expected:

```text
PASS selected Python tests
```

- [ ] **Step 2: Run focused dashboard auto-loop checks**

Run:

```text
/auto-test-dashboard tests/dashboard/lib/mcp-preflight.test.ts tests/dashboard/lib/visible-surface-policy.test.ts tests/dashboard/hooks/useMcpHealth.test.ts
```

Expected:

```text
PASS selected dashboard tests
```

- [ ] **Step 3: Run `/dev-build` for main**

Run:

```text
/dev-build --pages /browse/platform-admin
```

Expected:

```text
main instance resolves to port 3000, lifecycle state becomes healthy, browser verification reaches interactive state
```

- [ ] **Step 4: Create or reuse a test worktree**

Use the existing launcher/worktree flow, not a manual ad-hoc checkout:

```text
xa -> 2) new worktree
```

Expected:

```text
.augur-worktree.yaml exists
worktree_registry.yaml contains the worktree
dashboard port is in 3001-3010
MCP port is in 8081-8090
```

- [ ] **Step 5: Validate worktree without moving main browser**

Keep the visible app browser on:

```text
http://127.0.0.1:3000/browse/platform-admin
```

From the worktree, run:

```text
/dev-build --target current-worktree --pages /browse/platform-admin
```

Expected:

```text
worktree validation targets its allocated port
browser mode is headless_only
main visible URL remains http://127.0.0.1:3000/browse/platform-admin
artifacts are written under runtime/browser-verification/worktrees/<name>
```

- [ ] **Step 6: Force and prove a worktree-only failure**

Introduce a temporary broken dashboard import in the worktree only, run worktree validation, then revert the temporary edit through normal editing tools.

Expected failure report:

```text
instance_id=worktree:<name>
dashboard_port=<worktree port>
mcp_port=<worktree mcp port>
lifecycle_state=crashed or degraded
screenshot=<runtime>/browser-verification/worktrees/<name>/...
console_errors=[...]
main lifecycle remains healthy
main browser URL unchanged
```

- [ ] **Step 7: Restore worktree and verify pass**

Run:

```text
/dev-build --target current-worktree --pages /browse/platform-admin
```

Expected:

```text
worktree validation passes
main lifecycle remains healthy
main browser URL unchanged
```

- [ ] **Step 8: Run full merge gate from worktree**

When implementation changes are committed on the worktree branch, run:

```text
/dev-merge full
```

Expected:

```text
pre-merge validation targets source worktree
post-merge validation targets main
remote main is verified
vault repo handling is included when configured
worktree cleanup obeys live AI/client process ownership
```

- [ ] **Step 9: Mark ADR implemented after merge**

After the implementation is merged and verified:

```text
/adr set 737 Implemented
```

Expected:

```text
ADR-737 status becomes Implemented and generated indexes/instructions are regenerated
```

---

## Self-Review

Spec coverage:

- Instance model: Tasks 1 and 2.
- Scoped lifecycle and locks: Tasks 3 and 4.
- Strict invisible worktree validation: Tasks 2, 5, and 8.
- Validation-only heal policy: Task 6.
- `/dev-merge full` worktree gate: Task 7 and Task 8.
- Browser proof that main does not jump: Task 8.

Placeholder scan:

- The plan contains no unresolved placeholder file paths and no open-ended validation or error-handling steps.

Type consistency:

- Python uses `instance_id`, `kind`, `browser_mode`, `heal_policy`, and `visibility_policy`.
- Preflight JSON exposes `instance_kind` for TypeScript and keeps `instance_id` exact.
- Client policy uses `visible_allowed` and `no_visible_mutation`, matching Python.
