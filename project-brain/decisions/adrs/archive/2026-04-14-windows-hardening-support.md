# Windows Hardening Support Implementation Plan

> **Implements**: ADR-550 — Windows Hardening Support
>
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the hardening process run honestly on Windows in both local execution and GitHub CI by adding per-check capability metadata, shared runner gating, and an initial Windows-safe check subset.

**Architecture:** Keep capability metadata owned by each scan-fix module, but centralize platform resolution in `src/lib/ops_protocol.py`. Thread that contract through adaptive discovery and execution, then expose one shared Windows verification entrypoint for CI and local use so workflow YAML stops duplicating platform logic.

**Tech Stack:** Python 3.11, pytest, GitHub Actions YAML, adaptive loop engine, `src.lib.ops_protocol`

---

## File Map

- `src/lib/ops_protocol.py`
  - Add capability dataclasses/literals and the platform decision helper used by all scan-fix runners.
- `skills/daemon/scripts/adaptive/discovery.py`
  - Capture capability metadata from discovered modules and store it on `AutoCommandEntry`.
- `skills/daemon/scripts/adaptive/engine_entry_runner.py`
  - Apply platform-aware skip/report/fix decisions before scan/fix execution.
- `skills/daemon/scripts/adaptive/reporting.py`
  - Surface `skipped_platform` and `skipped_unsupported` outcomes cleanly in cycle reporting.
- `skills/daemon/scripts/ops/stale_paths.py`
  - Mark as cross-platform with Windows `auto_fix`.
- `skills/daemon/scripts/ops/mcp_hygiene.py`
  - Mark as cross-platform with Windows `auto_fix`.
- `skills/daemon/scripts/ops/page_mounts.py`
  - Mark as cross-platform with Windows `report_only`.
- `skills/daemon/scripts/ops/build_health.py`
  - Mark as cross-platform with Windows `report_only`.
- `skills/daemon/scripts/ops/security_scan.py`
  - Mark as cross-platform with Windows `report_only`.
- `skills/loop-ops/scripts/dependency_audit.py`
  - Mark initial Windows mode as `report_only`.
- `skills/loop-ops/scripts/fs_bypass.py`
  - Mark initial Windows mode as `report_only`.
- `skills/loop-ops/scripts/plugin_lint.py`
  - Mark initial Windows mode as `report_only`.
- `skills/daemon/scripts/adaptive/platform_verify.py`
  - New shared CLI for local/CI Windows verification of a loop using the same capability-aware runner logic.
- `.github/workflows/ci-cross-platform.yml`
  - Replace ad hoc Windows hardening logic with `platform_verify.py`.
- `.github/workflows/README.md`
  - Document the new hardening verification path and remove outdated workflow assumptions while touching this area.
- `skills/daemon/commands/dev-loops.md`
  - Document Windows hardening semantics: `auto_fix`, `report_only`, `skipped_unsupported`.
- `tests/unit/test_ops_protocol_capabilities.py`
  - New focused tests for platform capability resolution.
- `skills/daemon/augur/tests/test_adaptive_discovery.py`
  - Verify discovered entries carry capability metadata.
- `skills/daemon/augur/tests/test_engine_entry_runner.py`
  - Verify skip/report-only behavior at runner level.
- `skills/daemon/augur/tests/test_stale_paths.py`
  - Add Windows capability assertions for stale paths.
- `skills/daemon/augur/tests/test_ops_mcp_hygiene.py`
  - Add Windows capability assertions for MCP hygiene.
- `skills/daemon/augur/tests/test_ops_page_mounts.py`
  - Add Windows capability assertions for page mounts.
- `skills/daemon/augur/tests/test_build_health.py`
  - Add Windows report-only capability assertions.
- `skills/daemon/augur/tests/test_security_scan.py`
  - Add Windows report-only capability assertions.
- `skills/loop-ops/augur/tests/test_dependency_audit.py`
  - Add Windows report-only capability assertions.
- `skills/loop-ops/augur/tests/test_fs_bypass.py`
  - Add Windows report-only capability assertions.
- `skills/loop-ops/augur/tests/test_plugin_lint.py`
  - Add Windows report-only capability assertions.
- `skills/daemon/augur/tests/test_platform_verify.py`
  - New integration-style tests for the new shared verify CLI.

### Task 1: Add Shared Capability Plumbing

**Files:**
- Modify: `src/lib/ops_protocol.py`
- Modify: `skills/daemon/scripts/adaptive/discovery.py`
- Modify: `skills/daemon/scripts/adaptive/engine_entry_runner.py`
- Modify: `skills/daemon/scripts/adaptive/reporting.py`
- Create: `tests/unit/test_ops_protocol_capabilities.py`
- Modify: `skills/daemon/augur/tests/test_adaptive_discovery.py`
- Modify: `skills/daemon/augur/tests/test_engine_entry_runner.py`

- [ ] **Step 1: Write the failing protocol and runner tests**

```python
# tests/unit/test_ops_protocol_capabilities.py
from src.lib.ops_protocol import declare_ops_capabilities, resolve_ops_execution


def test_windows_auto_fix_check_runs_and_keeps_fix_enabled():
    caps = declare_ops_capabilities(
        platforms=("cross_platform",),
        windows_fix_mode="auto_fix",
    )

    decision = resolve_ops_execution(
        caps,
        platform_name="windows",
        allow_fix=True,
    )

    assert decision.run_scan is True
    assert decision.allow_fix is True
    assert decision.outcome == "ran"


def test_windows_unsupported_check_skips_with_explicit_reason():
    caps = declare_ops_capabilities(
        platforms=("macos",),
        windows_fix_mode="unsupported",
        skip_reason="launchd-only check",
    )

    decision = resolve_ops_execution(
        caps,
        platform_name="windows",
        allow_fix=True,
    )

    assert decision.run_scan is False
    assert decision.allow_fix is False
    assert decision.outcome == "skipped_unsupported"
    assert decision.skip_reason == "launchd-only check"
```

```python
# skills/daemon/augur/tests/test_adaptive_discovery.py
def test_discovers_module_capabilities_from_ops_module(self, tmp_path):
    skill_dir = _write_skill(
        tmp_path,
        "daemon",
        commands=[{
            "id": "auto-lint",
            "protocol": "scan-fix",
            "callable": "scripts/ops/lint.py",
            "loop": {"name": "hardening", "tier": 1},
        }],
    )
    (skill_dir / "scripts" / "ops").mkdir(parents=True, exist_ok=True)
    (skill_dir / "scripts" / "ops" / "lint.py").write_text(
        "from src.lib.ops_protocol import declare_ops_capabilities\\n"
        "name = 'auto-lint'\\n"
        "OPS_CAPABILITIES = declare_ops_capabilities(platforms=('cross_platform',), windows_fix_mode='auto_fix')\\n"
        "def scan(ctx): return type('R', (), {'issues': [], 'summary': 'clean', 'severity': 'info', 'health': 'verified'})()\\n"
        "def fix(ctx, issues): return type('F', (), {'success': True, 'actions': [], 'changes': [], 'summary': 'fixed'})()\\n",
        encoding='utf-8',
    )

    entry = discover_auto_commands(tmp_path)["auto-lint"]
    assert entry.capabilities.windows_fix_mode == "auto_fix"
```

```python
# skills/daemon/augur/tests/test_engine_entry_runner.py
from src.lib.ops_protocol import OpsExecutionDecision


def test_build_platform_skip_report_marks_unsupported_outcome():
    decision = OpsExecutionDecision(
        run_scan=False,
        allow_fix=False,
        outcome="skipped_unsupported",
        fix_mode="unsupported",
        skip_reason="launchd-only check",
    )

    report = build_platform_category_report(
        entry_name="auto-test",
        trust_before=0.2,
        difficulty=1,
        decision=decision,
    )

    assert report.name == "auto-test"
    assert report.status == "skipped"
    assert report.outcome == "skipped_unsupported"
    assert report.action_summary == "launchd-only check"
```

- [ ] **Step 2: Run the targeted tests to confirm the missing contract**

Run:

```bash
uv run pytest tests/unit/test_ops_protocol_capabilities.py skills/daemon/augur/tests/test_adaptive_discovery.py skills/daemon/augur/tests/test_engine_entry_runner.py -q
```

Expected:

```text
FAIL tests/unit/test_ops_protocol_capabilities.py
E   ImportError: cannot import name 'declare_ops_capabilities'
```

- [ ] **Step 3: Implement the shared capability contract and runner gating**

```python
# src/lib/ops_protocol.py
SupportedPlatform = Literal["cross_platform", "windows", "macos", "linux"]
WindowsFixMode = Literal["auto_fix", "report_only", "unsupported"]


@dataclass(frozen=True)
class OpsCapabilities:
    platforms: tuple[SupportedPlatform, ...] = ("cross_platform",)
    windows_fix_mode: WindowsFixMode = "auto_fix"
    skip_reason: str = ""


@dataclass(frozen=True)
class OpsExecutionDecision:
    run_scan: bool
    allow_fix: bool
    outcome: str
    fix_mode: WindowsFixMode
    skip_reason: str = ""


def declare_ops_capabilities(
    *,
    platforms: tuple[SupportedPlatform, ...] = ("cross_platform",),
    windows_fix_mode: WindowsFixMode = "auto_fix",
    skip_reason: str = "",
) -> OpsCapabilities:
    return OpsCapabilities(
        platforms=platforms,
        windows_fix_mode=windows_fix_mode,
        skip_reason=skip_reason,
    )


def resolve_ops_execution(
    capabilities: OpsCapabilities | None,
    *,
    platform_name: str,
    allow_fix: bool,
) -> OpsExecutionDecision:
    caps = capabilities or declare_ops_capabilities()
    normalized = platform_name.lower()
    if normalized.startswith("win"):
        if "windows" not in caps.platforms and "cross_platform" not in caps.platforms:
            return OpsExecutionDecision(
                run_scan=False,
                allow_fix=False,
                outcome="skipped_unsupported",
                fix_mode="unsupported",
                skip_reason=caps.skip_reason,
            )
        return OpsExecutionDecision(
            run_scan=True,
            allow_fix=allow_fix and caps.windows_fix_mode == "auto_fix",
            outcome="ran" if caps.windows_fix_mode == "auto_fix" else "report_only",
            fix_mode=caps.windows_fix_mode,
            skip_reason=caps.skip_reason,
        )
    return OpsExecutionDecision(
        run_scan=True,
        allow_fix=allow_fix,
        outcome="ran",
        fix_mode="auto_fix",
    )
```

```python
# skills/daemon/scripts/adaptive/discovery.py
registry[cmd_id] = AutoCommandEntry(
    name=cmd_id,
    module=module,
    capabilities=getattr(module, "OPS_CAPABILITIES", declare_ops_capabilities()),
    loop_name=loop_name,
    tier=loop_config.get("tier", rec["loop_config"].get("tier", 0)),
    trigger=loop_config.get("trigger", rec["loop_config"].get("trigger", "nightly")),
    scheduler=loop_config.get("scheduler", rec["loop_config"].get("scheduler", "daemon")),
    plugin_root=plugin_root,
    config=module_config,
    initial_trust=float(loop_config.get("trust", rec["loop_config"].get("trust", 0.0))),
)
```

```python
# skills/daemon/scripts/adaptive/engine_entry_runner.py
def build_platform_category_report(
    *,
    entry_name: str,
    trust_before: float,
    difficulty: int,
    decision: OpsExecutionDecision,
) -> CategoryReport:
    return CategoryReport(
        name=entry_name,
        trust_before=trust_before,
        trust_after=trust_before,
        difficulty_before=difficulty,
        difficulty_after=difficulty,
        status="skipped",
        outcome=decision.outcome,
        action_summary=decision.skip_reason or "platform unsupported",
    )


decision = resolve_ops_execution(
    getattr(entry, "capabilities", None),
    platform_name=sys.platform,
    allow_fix=not ctx.dry_run,
)
if not decision.run_scan:
    cat_reports.append(build_platform_category_report(
        entry_name=entry.name,
        trust_before=trust_before,
        difficulty=diff_before,
        decision=decision,
    ))
    return True
ctx.config = {**entry_config, "_ops_fix_mode": decision.fix_mode}
```

```python
# skills/daemon/scripts/adaptive/reporting.py
n_skipped = sum(
    1 for c in self.categories
    if c.outcome in {"skipped_platform", "skipped_unsupported"}
)
if n_skipped:
    tags.append(f"{n_skipped} skipped")
```

- [ ] **Step 4: Re-run the focused protocol and engine tests**

Run:

```bash
uv run pytest tests/unit/test_ops_protocol_capabilities.py skills/daemon/augur/tests/test_adaptive_discovery.py skills/daemon/augur/tests/test_engine_entry_runner.py -q
```

Expected:

```text
3 passed in 0.05s
```

- [ ] **Step 5: Commit the capability plumbing**

```bash
git add src/lib/ops_protocol.py \
  skills/daemon/scripts/adaptive/discovery.py \
  skills/daemon/scripts/adaptive/engine_entry_runner.py \
  skills/daemon/scripts/adaptive/reporting.py \
  tests/unit/test_ops_protocol_capabilities.py \
  skills/daemon/augur/tests/test_adaptive_discovery.py \
  skills/daemon/augur/tests/test_engine_entry_runner.py
git commit -m "feat(hardening): add platform capability gating"
```

### Task 2: Annotate The Initial Windows-Safe Check Set

**Files:**
- Modify: `skills/daemon/scripts/ops/stale_paths.py`
- Modify: `skills/daemon/scripts/ops/mcp_hygiene.py`
- Modify: `skills/daemon/scripts/ops/page_mounts.py`
- Modify: `skills/daemon/scripts/ops/build_health.py`
- Modify: `skills/daemon/scripts/ops/security_scan.py`
- Modify: `skills/daemon/augur/tests/test_stale_paths.py`
- Modify: `skills/daemon/augur/tests/test_ops_mcp_hygiene.py`
- Modify: `skills/daemon/augur/tests/test_ops_page_mounts.py`
- Modify: `skills/daemon/augur/tests/test_build_health.py`
- Modify: `skills/daemon/augur/tests/test_security_scan.py`

- [ ] **Step 1: Write failing capability tests for the first Windows rollout**

```python
# skills/daemon/augur/tests/test_stale_paths.py
def test_stale_paths_declares_windows_auto_fix():
    assert stale_paths.OPS_CAPABILITIES.platforms == ("cross_platform",)
    assert stale_paths.OPS_CAPABILITIES.windows_fix_mode == "auto_fix"
```

```python
# skills/daemon/augur/tests/test_ops_mcp_hygiene.py
def test_mcp_hygiene_declares_windows_auto_fix():
    from skills.daemon.scripts.ops import mcp_hygiene
    assert mcp_hygiene.OPS_CAPABILITIES.windows_fix_mode == "auto_fix"
```

```python
# skills/daemon/augur/tests/test_ops_page_mounts.py
def test_page_mounts_declares_windows_report_only():
    from skills.daemon.scripts.ops import page_mounts
    assert page_mounts.OPS_CAPABILITIES.windows_fix_mode == "report_only"
```

```python
# skills/daemon/augur/tests/test_build_health.py
def test_build_health_declares_windows_report_only():
    assert build_health.OPS_CAPABILITIES.windows_fix_mode == "report_only"
```

```python
# skills/daemon/augur/tests/test_security_scan.py
def test_security_scan_declares_windows_report_only():
    from skills.daemon.scripts.ops import security_scan
    assert security_scan.OPS_CAPABILITIES.windows_fix_mode == "report_only"
```

- [ ] **Step 2: Run the daemon hardening check tests and confirm the new assertions fail**

Run:

```bash
uv run pytest skills/daemon/augur/tests/test_stale_paths.py skills/daemon/augur/tests/test_ops_mcp_hygiene.py skills/daemon/augur/tests/test_ops_page_mounts.py skills/daemon/augur/tests/test_build_health.py skills/daemon/augur/tests/test_security_scan.py -q
```

Expected:

```text
FAIL skills/daemon/augur/tests/test_stale_paths.py
E   AttributeError: module 'stale_paths' has no attribute 'OPS_CAPABILITIES'
```

- [ ] **Step 3: Add explicit capability declarations to the first check set**

```python
# skills/daemon/scripts/ops/stale_paths.py
from src.lib.ops_protocol import declare_ops_capabilities

OPS_CAPABILITIES = declare_ops_capabilities(
    platforms=("cross_platform",),
    windows_fix_mode="auto_fix",
)
```

```python
# skills/daemon/scripts/ops/mcp_hygiene.py
OPS_CAPABILITIES = declare_ops_capabilities(
    platforms=("cross_platform",),
    windows_fix_mode="auto_fix",
)
```

```python
# skills/daemon/scripts/ops/page_mounts.py
OPS_CAPABILITIES = declare_ops_capabilities(
    platforms=("cross_platform",),
    windows_fix_mode="report_only",
)
```

```python
# skills/daemon/scripts/ops/build_health.py
OPS_CAPABILITIES = declare_ops_capabilities(
    platforms=("cross_platform",),
    windows_fix_mode="report_only",
    skip_reason="TypeScript auto-fix stays non-mutating on Windows until the verify path is proven end-to-end",
)
```

```python
# skills/daemon/scripts/ops/security_scan.py
OPS_CAPABILITIES = declare_ops_capabilities(
    platforms=("cross_platform",),
    windows_fix_mode="report_only",
    skip_reason="npm audit fix remains report-only on Windows in v1",
)
```

- [ ] **Step 4: Re-run the daemon hardening tests**

Run:

```bash
uv run pytest skills/daemon/augur/tests/test_stale_paths.py skills/daemon/augur/tests/test_ops_mcp_hygiene.py skills/daemon/augur/tests/test_ops_page_mounts.py skills/daemon/augur/tests/test_build_health.py skills/daemon/augur/tests/test_security_scan.py -q
```

Expected:

```text
5 passed in 0.07s
```

- [ ] **Step 5: Commit the initial daemon-owned Windows rollout**

```bash
git add skills/daemon/scripts/ops/stale_paths.py \
  skills/daemon/scripts/ops/mcp_hygiene.py \
  skills/daemon/scripts/ops/page_mounts.py \
  skills/daemon/scripts/ops/build_health.py \
  skills/daemon/scripts/ops/security_scan.py \
  skills/daemon/augur/tests/test_stale_paths.py \
  skills/daemon/augur/tests/test_ops_mcp_hygiene.py \
  skills/daemon/augur/tests/test_ops_page_mounts.py \
  skills/daemon/augur/tests/test_build_health.py \
  skills/daemon/augur/tests/test_security_scan.py
git commit -m "feat(hardening): classify initial windows-safe checks"
```

### Task 3: Add The Shared Verify Runner, Cover Loop-Ops Checks, And Wire CI

**Files:**
- Create: `skills/daemon/scripts/adaptive/platform_verify.py`
- Modify: `skills/loop-ops/scripts/dependency_audit.py`
- Modify: `skills/loop-ops/scripts/fs_bypass.py`
- Modify: `skills/loop-ops/scripts/plugin_lint.py`
- Modify: `.github/workflows/ci-cross-platform.yml`
- Modify: `.github/workflows/README.md`
- Modify: `skills/daemon/commands/dev-loops.md`
- Modify: `skills/loop-ops/augur/tests/test_dependency_audit.py`
- Modify: `skills/loop-ops/augur/tests/test_fs_bypass.py`
- Modify: `skills/loop-ops/augur/tests/test_plugin_lint.py`
- Create: `skills/daemon/augur/tests/test_platform_verify.py`

- [ ] **Step 1: Write failing tests for the shared verify runner and loop-ops rollout**

```python
# skills/loop-ops/augur/tests/test_dependency_audit.py
def test_dependency_audit_declares_windows_report_only():
    assert mod.OPS_CAPABILITIES.windows_fix_mode == "report_only"
```

```python
# skills/loop-ops/augur/tests/test_fs_bypass.py
import importlib


def test_fs_bypass_declares_windows_report_only():
    mod = importlib.import_module("fs_bypass")
    assert mod.OPS_CAPABILITIES.windows_fix_mode == "report_only"
```

```python
# skills/loop-ops/augur/tests/test_plugin_lint.py
def test_plugin_lint_declares_windows_report_only():
    assert mod.OPS_CAPABILITIES.windows_fix_mode == "report_only"
```

```python
# skills/daemon/augur/tests/test_platform_verify.py
from skills.daemon.scripts.adaptive.platform_verify import main


def test_platform_verify_summarizes_report_only_and_skipped_categories(tmp_path, capsys):
    result = main([
        "--loop", "hardening",
        "--platform", "windows",
        "--mode", "verify",
        "--project-root", str(tmp_path),
    ])

    captured = capsys.readouterr()
    assert result == 0
    assert "report_only" in captured.out
```

- [ ] **Step 2: Run the loop-ops and verify-runner tests to confirm they fail first**

Run:

```bash
uv run pytest skills/loop-ops/augur/tests/test_dependency_audit.py skills/loop-ops/augur/tests/test_fs_bypass.py skills/loop-ops/augur/tests/test_plugin_lint.py skills/daemon/augur/tests/test_platform_verify.py -q
```

Expected:

```text
FAIL skills/loop-ops/augur/tests/test_dependency_audit.py
E   AttributeError: module 'dependency_audit_under_test' has no attribute 'OPS_CAPABILITIES'
```

- [ ] **Step 3: Implement the loop-ops capability declarations, verify CLI, and CI/docs wiring**

```python
# skills/loop-ops/scripts/dependency_audit.py
OPS_CAPABILITIES = declare_ops_capabilities(
    platforms=("cross_platform",),
    windows_fix_mode="report_only",
    skip_reason="dependency autofix stays report-only on Windows in v1",
)

# skills/loop-ops/scripts/fs_bypass.py
OPS_CAPABILITIES = declare_ops_capabilities(
    platforms=("cross_platform",),
    windows_fix_mode="report_only",
)

# skills/loop-ops/scripts/plugin_lint.py
OPS_CAPABILITIES = declare_ops_capabilities(
    platforms=("cross_platform",),
    windows_fix_mode="report_only",
)
```

```python
# skills/daemon/scripts/adaptive/platform_verify.py
def main(argv: list[str] | None = None) -> int:
    args = parser.parse_args(argv)
    registry = group_by_loop(discover_auto_commands(project_root))
    entries = registry.get(args.loop, [])
    lines: list[str] = []
    exit_code = 0
    for entry in entries:
        decision = resolve_ops_execution(
            getattr(entry, "capabilities", None),
            platform_name=args.platform,
            allow_fix=args.mode == "fix",
        )
        lines.append(f"{entry.name}: {decision.outcome}")
        if decision.run_scan:
            result = entry.module.scan(OpsContext(project_root=project_root, dry_run=args.mode != 'fix'))
            if result.health == "broken":
                exit_code = 1
    print("\\n".join(lines))
    return exit_code
```

```yaml
# .github/workflows/ci-cross-platform.yml
- name: Verify hardening support (Windows)
  if: runner.os == 'Windows'
  run: |
    .\.venv\Scripts\Activate.ps1
    python skills/daemon/scripts/adaptive/platform_verify.py --loop hardening --platform windows --mode verify
```

```md
# skills/daemon/commands/dev-loops.md
- Windows categories may now report `report_only`, `skipped_platform`, or `skipped_unsupported`.
- `report_only` means the scanner ran and findings are real, but fix mode was intentionally disabled on Windows.
- Use `python skills/daemon/scripts/adaptive/platform_verify.py --loop hardening --platform windows --mode verify` for the shared local smoke path.
```

- [ ] **Step 4: Run the full Windows hardening verification set**

Run:

```bash
uv run pytest skills/loop-ops/augur/tests/test_dependency_audit.py skills/loop-ops/augur/tests/test_fs_bypass.py skills/loop-ops/augur/tests/test_plugin_lint.py skills/daemon/augur/tests/test_platform_verify.py -q
python skills/daemon/scripts/adaptive/platform_verify.py --loop hardening --platform windows --mode verify
```

Expected:

```text
4 passed in 0.06s
auto-stale-paths: ran
auto-code-health: report_only
auto-security-scan: report_only
```

- [ ] **Step 5: Commit the verify runner, loop-ops rollout, and CI/docs updates**

```bash
git add skills/daemon/scripts/adaptive/platform_verify.py \
  skills/loop-ops/scripts/dependency_audit.py \
  skills/loop-ops/scripts/fs_bypass.py \
  skills/loop-ops/scripts/plugin_lint.py \
  .github/workflows/ci-cross-platform.yml \
  .github/workflows/README.md \
  skills/daemon/commands/dev-loops.md \
  skills/loop-ops/augur/tests/test_dependency_audit.py \
  skills/loop-ops/augur/tests/test_fs_bypass.py \
  skills/loop-ops/augur/tests/test_plugin_lint.py \
  skills/daemon/augur/tests/test_platform_verify.py
git commit -m "build(hardening): add windows verify runner"
```
