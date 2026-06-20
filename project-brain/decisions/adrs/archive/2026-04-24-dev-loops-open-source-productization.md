# Dev-Loops Open Source Productization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `/dev-loops` safe, quiet, truthful, and verifiable for a fresh open-source install that must maintain both the Augur project repo and the configured user vault.

**Architecture:** Keep the adaptive loop engine as the orchestrator, but narrow loop discovery to canonical source skill directories, make scheduler ownership derived from install state, route repo/vault paths through `src.config.paths`, and replace destructive automated rollback with owned-path rollback. Public `/dev-loops` commands must either execute real ledger operations or be removed from help text.

**Tech Stack:** Python 3.11, pytest, PyYAML, TOML via `tomllib`, git CLI, Augur `src.config.paths`, adaptive loop engine modules, generated command markdown.

---

## Design Inputs

- Primary design: `docs/superpowers/specs/2026-04-24-dev-loops-open-source-productization-design.md`
- Command surface: `skills/daemon/commands/dev-loops.md`
- Core CLI: `skills/daemon/scripts/adaptive_loop_executor.py`
- Discovery and scheduler metadata: `skills/daemon/scripts/adaptive/discovery.py`
- Manifest: `skills/daemon/scripts/adaptive/codex_schedule_manifest.py`
- Fix orchestration: `skills/daemon/scripts/adaptive/engine_fix_phase.py`
- Repo and vault maintenance: `skills/loop-observability/scripts/repo_sync.py`, `skills/loop-repo/scripts/vault_hygiene_ops.py`
- Path contract: `src/config/paths.py`, `project.yaml`, `config/system/vault.yaml`

## Implementation Tasks

### 1. Add a Canonical Loop Skill Directory Helper

- [ ] Read local placement rules before editing:

```bash
test -f src/config/README.md && sed -n '1,220p' src/config/README.md || true
test -f skills/daemon/README.md && sed -n '1,220p' skills/daemon/README.md || true
```

- [ ] Add this helper to `src/config/paths.py` near the existing skill directory helpers:

```python
def get_configured_vault_dir(project_root: Path | None = None) -> Path:
    """Return the vault path configured for a project without discovery fallback."""
    root = (project_root or get_project_root()).resolve()
    project_file = root / "project.yaml"
    if project_file.exists():
        try:
            data = _load_yaml_file(project_file)
        except Exception:
            data = {}
        paths = data.get("paths") if isinstance(data, dict) else {}
        configured = paths.get("vault") if isinstance(paths, dict) else None
        if isinstance(configured, str) and configured.strip():
            return Path(os.path.expanduser(configured)).resolve()

    return (Path.home() / "Vault" / "Augur").resolve()


def get_configured_vault_skills_dir(project_root: Path | None = None) -> Path:
    """Return the configured vault skills directory without probing alternate vaults."""
    return get_configured_vault_dir(project_root) / "skills"


def get_adaptive_loop_skill_dirs(project_root: Path | None = None) -> list[Path]:
    """Return canonical skill source directories that can own adaptive loop callables."""
    root = (project_root or get_project_root()).resolve()
    dirs: list[Path] = []

    repo_skills = root / "skills"
    if repo_skills.exists():
        dirs.append(repo_skills)

    vault_skills = get_configured_vault_skills_dir(root)
    if vault_skills.exists():
        dirs.append(vault_skills)

    return dirs
```

- [ ] If `src/config/paths.py` already has a YAML loading helper with a different name, use that helper instead of duplicating YAML parsing. Import `os` only if the module does not already import it.

- [ ] Add path tests to `tests/src/test_paths.py`:

```python
def test_get_adaptive_loop_skill_dirs_excludes_generated_client_exports(tmp_path, monkeypatch):
    from src.config.paths import get_adaptive_loop_skill_dirs

    project = tmp_path / "Augur"
    (project / "skills").mkdir(parents=True)
    (project / ".gemini" / "skills").mkdir(parents=True)
    (project / ".opencode" / "skills").mkdir(parents=True)
    (project / ".codex" / "skills").mkdir(parents=True)
    (project / "project.yaml").write_text(
        "name: Augur\npaths:\n  vault: ~/Vault/Augur\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("HOME", str(tmp_path))

    dirs = get_adaptive_loop_skill_dirs(project)

    assert dirs == [project / "skills"]
```

```python
def test_get_adaptive_loop_skill_dirs_includes_configured_vault_skills(tmp_path, monkeypatch):
    from src.config.paths import get_adaptive_loop_skill_dirs

    project = tmp_path / "Augur"
    vault = tmp_path / "CustomVault"
    (project / "skills").mkdir(parents=True)
    (vault / "skills").mkdir(parents=True)
    (project / "project.yaml").write_text(
        f"name: Augur\npaths:\n  vault: {vault}\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("HOME", str(tmp_path))

    dirs = get_adaptive_loop_skill_dirs(project)

    assert dirs == [project / "skills", vault / "skills"]
```

- [ ] Run the focused path tests:

```bash
uv run pytest tests/src/test_paths.py -q
```

### 2. Restrict Adaptive Loop Discovery to Canonical Sources

- [ ] Change `skills/daemon/scripts/adaptive/discovery.py` to import `get_adaptive_loop_skill_dirs` instead of `get_all_client_skill_dirs`.

- [ ] Replace directory enumeration in `discover_auto_commands()` with:

```python
for skill_dir in get_adaptive_loop_skill_dirs(project_root):
    if not skill_dir.exists():
        continue
    for skill_path in sorted(skill_dir.iterdir()):
        if not skill_path.is_dir():
            continue
        _discover_skill_auto_commands(skill_path, registry, warnings)
```

- [ ] Preserve the existing warning behavior for real source skills. Generated exports must no longer produce warnings such as `Module file not found` from `.gemini/skills`, `.opencode/skills`, or `.codex/skills`.

- [ ] Add this test to `skills/daemon/augur/tests/test_adaptive_discovery.py`:

```python
def test_discovery_ignores_generated_client_exports(tmp_path, caplog):
    from skills.daemon.scripts.adaptive.discovery import discover_auto_commands

    project = tmp_path / "Augur"
    skill = project / "skills" / "loop-source"
    generated = project / ".gemini" / "skills" / "loop-source"
    module = skill / "augur" / "loop_source" / "auto.py"

    module.parent.mkdir(parents=True)
    generated.mkdir(parents=True)
    module.write_text(
        "def run(ctx):\n"
        "    return {'status': 'ok'}\n",
        encoding="utf-8",
    )
    (skill / "SKILL.md").write_text(
        "---\n"
        "auto:\n"
        "  enabled: true\n"
        "  trigger: nightly\n"
        "  callable: augur.loop_source.auto:run\n"
        "---\n"
        "# Loop Source\n",
        encoding="utf-8",
    )
    (generated / "SKILL.md").write_text(
        "---\n"
        "auto:\n"
        "  enabled: true\n"
        "  trigger: nightly\n"
        "  callable: missing.module:run\n"
        "---\n"
        "# Generated Export\n",
        encoding="utf-8",
    )
    (project / "project.yaml").write_text("name: Augur\npaths:\n  vault: ~/Vault/Augur\n", encoding="utf-8")

    registry = discover_auto_commands(project_root=project)

    assert "loop-source" in registry.commands
    assert ".gemini/skills" not in caplog.text
    assert "Module file not found" not in caplog.text
```

- [ ] Run discovery tests:

```bash
uv run pytest skills/daemon/augur/tests/test_adaptive_discovery.py -q
```

### 3. Make Scheduler Ownership Truthful

- [ ] Add scheduler helper functions to `skills/daemon/scripts/adaptive/discovery.py`:

```python
def default_scheduler_for_trigger(trigger: str) -> str:
    normalized = str(trigger or "").strip().lower()
    return "daemon" if normalized == "continuous" else "codex"


def resolve_scheduler(loop_config: dict[str, Any], fallback_config: dict[str, Any] | None = None) -> str:
    for source in (loop_config, fallback_config or {}):
        value = source.get("scheduler")
        if isinstance(value, str) and value.strip():
            return value.strip().lower()

    trigger = loop_config.get("trigger")
    if not trigger and fallback_config:
        trigger = fallback_config.get("trigger")
    return default_scheduler_for_trigger(str(trigger or "nightly"))
```

- [ ] Use `resolve_scheduler()` everywhere discovery assigns `scheduler` for an auto command. The fallback config is the parent loop config when the command is nested under a loop.

- [ ] Update test expectations so continuous loops default to `daemon`, while `hourly`, `daily`, `nightly`, `weekly`, and `monthly` default to `codex` unless explicit `scheduler` metadata overrides them.

- [ ] Add manifest state detection to `skills/daemon/scripts/adaptive/codex_schedule_manifest.py`:

```python
def detect_codex_schedule_states(schedule_ids: Iterable[str], *, home: Path | None = None) -> dict[str, str]:
    codex_home = Path(home or Path.home() / ".codex")
    states: dict[str, str] = {}
    for schedule_id in schedule_ids:
        automation_file = codex_home / "automations" / schedule_id / "automation.toml"
        if not automation_file.exists():
            states[schedule_id] = "not-installed"
            continue
        try:
            data = tomllib.loads(automation_file.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError:
            states[schedule_id] = "invalid"
            continue
        if data.get("managed_by") != "augur":
            states[schedule_id] = "not-installed"
            continue
        status = str(data.get("status", "")).upper()
        states[schedule_id] = "active" if status == "ACTIVE" else "disabled"
    return states
```

- [ ] Add `schedule_states: Mapping[str, str] | None = None` to the manifest builder. Set each row's `cutover_state` from `schedule_states.get(unit_id, "not-installed")`. Keep `planned` only for rows that explicitly carry a future `target_owner` change and no install artifact.

- [ ] Update the CLI manifest command in `skills/daemon/scripts/adaptive_loop_executor.py` to pass detected states:

```python
rows = build_codex_schedule_manifest(project_root=project_root, schedule_states=None)
states = detect_codex_schedule_states(row["unit_id"] for row in rows)
rows = build_codex_schedule_manifest(project_root=project_root, schedule_states=states)
```

- [ ] Add tests to `skills/daemon/augur/tests/test_codex_schedule_manifest.py`:

```python
def test_detect_codex_schedule_states_reports_not_installed(tmp_path):
    from skills.daemon.scripts.adaptive.codex_schedule_manifest import detect_codex_schedule_states

    assert detect_codex_schedule_states(["augur-loop-nightly"], home=tmp_path) == {
        "augur-loop-nightly": "not-installed"
    }
```

```python
def test_detect_codex_schedule_states_reports_active(tmp_path):
    from skills.daemon.scripts.adaptive.codex_schedule_manifest import detect_codex_schedule_states

    automation = tmp_path / ".codex" / "automations" / "augur-loop-nightly"
    automation.mkdir(parents=True)
    (automation / "automation.toml").write_text(
        'managed_by = "augur"\nstatus = "ACTIVE"\n',
        encoding="utf-8",
    )

    assert detect_codex_schedule_states(["augur-loop-nightly"], home=tmp_path / ".codex") == {
        "augur-loop-nightly": "active"
    }
```

- [ ] Update status reporting in `skills/daemon/scripts/adaptive/loop_reporter.py` so owner labels match discovered scheduler values. Nightly and other non-continuous rows must no longer display `daemon` unless metadata explicitly sets `scheduler: daemon`.

- [ ] Run scheduler tests:

```bash
uv run pytest skills/daemon/augur/tests/test_adaptive_discovery.py skills/daemon/augur/tests/test_codex_schedule_manifest.py -q
```

### 4. Replace Public Stub Commands with Real Ledger Operations

- [ ] Inspect the trust ledger API before editing:

```bash
sed -n '1,260p' skills/daemon/scripts/adaptive/trust_ledger.py
sed -n '1,260p' skills/daemon/scripts/adaptive/trust_state.py
sed -n '1,260p' skills/daemon/scripts/adaptive/trust_persistence.py
```

- [ ] In `skills/daemon/scripts/adaptive_loop_executor.py`, replace stub branches for `enable`, `disable`, `configure`, `promote`, `diagnose`, `history`, and `reset` with direct engine/ledger calls. Add helpers near the existing command handlers:

```python
def _known_loop_names(engine: AdaptiveLoopEngine) -> list[str]:
    names = set(engine.loops.keys())
    names.update(getattr(engine, "_auto_loop_names", set()))
    return sorted(names)


def _require_loop(engine: AdaptiveLoopEngine, loop_name: str) -> None:
    if loop_name not in _known_loop_names(engine):
        valid = ", ".join(_known_loop_names(engine))
        raise SystemExit(f"Unknown loop '{loop_name}'. Valid loops: {valid}")
```

- [ ] Implement behavior:

```python
if args.enable:
    _require_loop(engine, args.enable)
    engine.ledger.set_loop_enabled(args.enable, True)
    print(f"Enabled loop: {args.enable}")
    return 0

if args.disable:
    _require_loop(engine, args.disable)
    engine.ledger.set_loop_enabled(args.disable, False)
    print(f"Disabled loop: {args.disable}")
    return 0

if args.configure:
    _require_loop(engine, args.configure)
    if args.budget is not None:
        if args.budget <= 0:
            raise SystemExit("--budget must be a positive integer")
        engine.ledger.set_loop_budget(args.configure, args.budget)
        print(f"Updated {args.configure} budget to {args.budget}")
    else:
        raise SystemExit("configure requires --budget")
    return 0

if args.promote:
    if len(args.promote) != 2:
        raise SystemExit("promote requires LOOP and CATEGORY")
    loop_name, category = args.promote
    _require_loop(engine, loop_name)
    engine.ledger.promote_category(loop_name, category)
    print(f"Promoted {category} in {loop_name}")
    return 0

if args.reset:
    _require_loop(engine, args.reset)
    engine.ledger.reset_loop(args.reset)
    print(f"Reset loop state: {args.reset}")
    return 0
```

- [ ] Match method names to the actual ledger API discovered in the inspection step. If a setter does not exist, add it to `trust_ledger.py` and persist through the same storage path already used by the ledger.

- [ ] Implement `history` with the existing journal reader. Use `--loop` to filter when supplied and `--limit` with the current default:

```python
if args.history:
    events = engine.journal_reader.read_all(limit=args.limit)
    if args.loop:
        events = [event for event in events if event.get("loop") == args.loop]
    for event in events[-args.limit:]:
        print(json.dumps(event, sort_keys=True))
    return 0
```

- [ ] Implement `diagnose` with a concise text output using existing ledger or engine diagnostics. When `--fix` is provided without `--heal`, return a clear error because fix execution belongs to the heal path:

```python
if args.diagnose:
    if args.fix:
        raise SystemExit("--fix is only supported with --heal")
    diagnostics = engine.diagnose_loop(args.diagnose)
    print(format_diagnostics(diagnostics))
    return 0
```

- [ ] If `diagnose_loop()` and `format_diagnostics()` do not exist, add small pure helpers that inspect loop state, enabled state, budget, last run, consecutive failures, and current ownership. Do not invoke mutation from diagnose.

- [ ] Update `skills/daemon/commands/dev-loops.md` so every listed command executes. Remove any command example that is not backed by code. In particular, do not list `diagnose --fix` unless a tested implementation exists.

- [ ] Add tests to `skills/daemon/augur/tests/test_adaptive_loop_executor.py`:

```python
def test_dev_loops_enable_updates_ledger(monkeypatch, capsys):
    calls = []
    engine = make_engine_with_loops(["auto-tidy"])
    monkeypatch.setattr(engine.ledger, "set_loop_enabled", lambda loop, enabled: calls.append((loop, enabled)))

    code = run_cli_with_engine(["--enable", "auto-tidy"], engine)

    assert code == 0
    assert calls == [("auto-tidy", True)]
    assert "Enabled loop: auto-tidy" in capsys.readouterr().out
```

```python
def test_dev_loops_disable_updates_ledger(monkeypatch, capsys):
    calls = []
    engine = make_engine_with_loops(["auto-tidy"])
    monkeypatch.setattr(engine.ledger, "set_loop_enabled", lambda loop, enabled: calls.append((loop, enabled)))

    code = run_cli_with_engine(["--disable", "auto-tidy"], engine)

    assert code == 0
    assert calls == [("auto-tidy", False)]
```

```python
def test_dev_loops_configure_requires_positive_budget(monkeypatch):
    engine = make_engine_with_loops(["auto-tidy"])

    with pytest.raises(SystemExit, match="positive integer"):
        run_cli_with_engine(["--configure", "auto-tidy", "--budget", "0"], engine)
```

```python
def test_dev_loops_unknown_loop_exits_cleanly(monkeypatch):
    engine = make_engine_with_loops(["auto-tidy"])

    with pytest.raises(SystemExit, match="Unknown loop 'missing'"):
        run_cli_with_engine(["--enable", "missing"], engine)
```

- [ ] Use the existing test harness helpers if present. If they are absent, add local fixtures in the test file that patch engine creation and keep CLI parsing in process.

- [ ] Run CLI tests:

```bash
uv run pytest skills/daemon/augur/tests/test_adaptive_loop_executor.py -q
```

### 5. Replace Destructive Rollback with Owned-Path Rollback

- [ ] In `skills/daemon/scripts/adaptive/engine_fix_phase.py`, isolate git status parsing into pure helpers:

```python
def _parse_porcelain_paths(output: str) -> dict[str, str]:
    paths: dict[str, str] = {}
    for line in output.splitlines():
        if not line:
            continue
        status = line[:2]
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        paths[path] = status
    return paths
```

```python
def _status_paths(project_root: Path) -> dict[str, str]:
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=project_root,
        text=True,
        capture_output=True,
        check=True,
    )
    return _parse_porcelain_paths(result.stdout)
```

```python
def _changed_paths_since(project_root: Path, base_ref: str, head_ref: str = "HEAD") -> set[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", f"{base_ref}..{head_ref}"],
        cwd=project_root,
        text=True,
        capture_output=True,
        check=True,
    )
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}
```

- [ ] Before LLM dispatch starts, capture both `head_before` and `status_before = _status_paths(project_root)`.

- [ ] Replace every automated failure branch that currently calls broad reset or checkout with `_rollback_llm_owned_changes()`:

```python
def _rollback_llm_owned_changes(project_root: Path, head_before: str, status_before: dict[str, str]) -> list[str]:
    status_after = _status_paths(project_root)
    dirty_before = set(status_before)
    dirty_after = set(status_after)
    head_changed_paths = _changed_paths_since(project_root, head_before)

    protected = head_changed_paths & dirty_before
    if protected:
        raise RuntimeError(
            "LLM rollback blocked because these paths were dirty before dispatch: "
            + ", ".join(sorted(protected))
        )

    reverted: list[str] = []
    for path in sorted(head_changed_paths):
        subprocess.run(["git", "checkout", head_before, "--", path], cwd=project_root, check=True)
        reverted.append(path)

    untracked_status = "?" * 2
    new_dirty_paths = dirty_after - dirty_before - head_changed_paths
    for path in sorted(new_dirty_paths):
        full_path = project_root / path
        if status_after.get(path) == untracked_status and full_path.exists():
            if full_path.is_dir():
                shutil.rmtree(full_path)
            else:
                full_path.unlink()
            reverted.append(path)

    return reverted
```

- [ ] If the LLM created commits, do not use `git reset --hard`. Restore the owned changed files from `head_before`, then leave the working tree dirty for review or create a narrowly named rollback commit only if the existing engine already commits automated fix attempts. Preserve user-dirty files and abort rollback if overlap is detected.

- [ ] Log rollback results in the existing result object:

```python
result.rollback = {
    "mode": "owned-path",
    "paths": reverted_paths,
}
```

- [ ] Add tests to `skills/daemon/augur/tests/test_engine_fix_phase.py`:

```python
def test_parse_porcelain_paths_handles_rename_and_untracked():
    from skills.daemon.scripts.adaptive.engine_fix_phase import _parse_porcelain_paths

    untracked_status = "?" * 2
    parsed = _parse_porcelain_paths(
        " M src/a.py\n"
        "R  src/old.py -> src/new.py\n"
        f"{untracked_status} scratch.txt\n"
    )

    assert parsed["src/a.py"] == " M"
    assert parsed["src/new.py"] == "R "
    assert parsed["scratch.txt"] == untracked_status
```

```python
def test_rollback_blocks_overlap_with_user_dirty_file(tmp_path):
    from skills.daemon.scripts.adaptive.engine_fix_phase import _rollback_llm_owned_changes

    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    path = tmp_path / "file.txt"
    path.write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "add", "file.txt"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "base"], cwd=tmp_path, check=True)
    head_before = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=tmp_path, text=True).strip()
    path.write_text("user change\n", encoding="utf-8")
    status_before = {"file.txt": " M"}
    subprocess.run(["git", "add", "file.txt"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "llm change"], cwd=tmp_path, check=True)

    with pytest.raises(RuntimeError, match="dirty before dispatch"):
        _rollback_llm_owned_changes(tmp_path, head_before, status_before)
```

- [ ] Add a static safety test:

```python
def test_engine_fix_phase_does_not_use_destructive_reset():
    path = Path("skills/daemon/scripts/adaptive/engine_fix_phase.py")
    source = path.read_text(encoding="utf-8")

    assert "git\", \"reset\", \"--hard" not in source
    assert "git reset --hard" not in source
    assert "git\", \"checkout\", \"--\", \".\"" not in source
```

- [ ] Run fix-phase tests:

```bash
uv run pytest skills/daemon/augur/tests/test_engine_fix_phase.py -q
```

### 6. Fix Repo and Vault Path Resolution

- [ ] Replace the upward directory-name search in `skills/loop-observability/scripts/repo_sync.py` with `get_configured_vault_dir(project_root)`.

```python
from src.config.paths import get_configured_vault_dir


def _get_vault_path(project_root: Path | None = None) -> Path:
    return get_configured_vault_dir(project_root)
```

- [ ] Pass the context project root from scan/fix entrypoints:

```python
vault_path = _get_vault_path(ctx.project_root)
```

- [ ] Keep first-run behavior non-fatal: if the configured vault path does not exist, report one clear issue with `status="missing"` and remediation text that tells the user to run onboarding or create the configured vault. Do not scan alternate private paths.

- [ ] Add tests to `skills/loop-observability/augur/tests/test_repo_sync.py`:

```python
def test_get_vault_path_uses_project_yaml(tmp_path, monkeypatch):
    from skills.loop_observability.scripts.repo_sync import _get_vault_path

    project = tmp_path / "Augur"
    vault = tmp_path / "VaultForProject"
    project.mkdir()
    (project / "project.yaml").write_text(
        f"name: Augur\npaths:\n  vault: {vault}\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("HOME", str(tmp_path / "home"))

    assert _get_vault_path(project) == vault.resolve()
```

```python
def test_repo_sync_missing_vault_reports_configured_path(tmp_path, monkeypatch):
    from skills.loop_observability.scripts.repo_sync import scan

    project = tmp_path / "Augur"
    vault = tmp_path / "missing-vault"
    project.mkdir()
    (project / "project.yaml").write_text(
        f"name: Augur\npaths:\n  vault: {vault}\n",
        encoding="utf-8",
    )
    ctx = make_scan_context(project_root=project)

    result = scan(ctx)

    assert str(vault) in result.summary or any(str(vault) in issue.message for issue in result.issues)
```

- [ ] If `make_scan_context` does not exist, use the context fixture style already present in `test_repo_sync.py`.

- [ ] Audit `skills/loop-repo/scripts/vault_hygiene_ops.py` for direct `Path.home()` or private vault discovery. Replace project-specific vault resolution with `get_configured_vault_dir(project_root)` where the operation is tied to a repo context.

- [ ] Run repo/vault tests:

```bash
uv run pytest skills/loop-observability/augur/tests/test_repo_sync.py tests/src/test_paths.py -q
```

### 7. Add a Fresh-Install Dev-Loops Smoke Test

- [ ] Create `skills/daemon/augur/tests/test_dev_loops_open_source_smoke.py`.

- [ ] Add a helper that runs the real CLI from the current repo with isolated home/cache/runtime paths:

```python
def run_dev_loops(repo_root: Path, args: list[str], tmp_path: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(
        {
            "HOME": str(tmp_path / "home"),
            "AUGUR_RUNTIME_DIR": str(tmp_path / "runtime"),
            "AUGUR_CACHE_DIR": str(tmp_path / "cache"),
            "AUGUR_LOGS_DIR": str(tmp_path / "logs"),
            "AUGUR_VAULT": str(tmp_path / "vault"),
            "PYTHONPATH": f"{repo_root}:{repo_root / 'src'}:{env.get('PYTHONPATH', '')}",
        }
    )
    return subprocess.run(
        [sys.executable, "skills/daemon/scripts/adaptive_loop_executor.py", *args],
        cwd=repo_root,
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
```

- [ ] Add smoke assertions:

```python
@pytest.mark.parametrize("args", [["registry"], ["status"], ["manifest"], ["report", "--days", "1"]])
def test_dev_loops_fresh_install_commands_are_quiet(repo_root, tmp_path, args):
    result = run_dev_loops(repo_root, args, tmp_path)
    output = result.stdout + result.stderr

    assert result.returncode == 0
    assert "Module file not found" not in output
    assert ".gemini/skills" not in output
    assert ".opencode/skills" not in output
    assert "~" not in output
    assert "Traceback" not in output
```

- [ ] If `report --days 1` currently requires persisted history, update the report command to return an empty but valid report for a new install.

- [ ] Run the smoke test:

```bash
uv run pytest skills/daemon/augur/tests/test_dev_loops_open_source_smoke.py -q
```

### 8. Update Public Dev-Loops Documentation

- [ ] Update `skills/daemon/commands/dev-loops.md`:
  - Explain that `/dev-loops` maintains both the project repo and configured vault when the vault exists.
  - State that discovery reads canonical source skills only, not generated client exports.
  - State default scheduler ownership: continuous loops run under the daemon; scheduled loops install into Codex automations after sync.
  - Remove any command listed without tested CLI behavior.
  - Add first-run remediation for a missing configured vault.

- [ ] Update `skills/daemon/references/dev-loops-implementation.md` with the release-gate architecture:
  - canonical source discovery
  - truthful scheduler/cutover state
  - command operation coverage
  - owned-path rollback
  - configured vault resolution
  - smoke-test contract

- [ ] Run a docs surface check:

```bash
rg -n "Not yet implemented|diagnose --fix|planned.*daemon|generated client export" skills/daemon/commands/dev-loops.md skills/daemon/references/dev-loops-implementation.md
```

The command should return only intentional explanatory matches. If it returns stale command examples or daemon ownership claims, edit the docs and rerun.

### 9. Full Verification

- [ ] Run the full focused test set:

```bash
uv run pytest \
  tests/src/test_paths.py \
  skills/daemon/augur/tests/test_adaptive_discovery.py \
  skills/daemon/augur/tests/test_codex_schedule_manifest.py \
  skills/daemon/augur/tests/test_adaptive_loop_executor.py \
  skills/daemon/augur/tests/test_engine_fix_phase.py \
  skills/loop-observability/augur/tests/test_repo_sync.py \
  skills/daemon/augur/tests/test_dev_loops_open_source_smoke.py \
  -q
```

- [ ] Run the current CLI commands:

```bash
python skills/daemon/scripts/adaptive_loop_executor.py registry
python skills/daemon/scripts/adaptive_loop_executor.py status
python skills/daemon/scripts/adaptive_loop_executor.py manifest
python skills/daemon/scripts/adaptive_loop_executor.py report --days 1
```

- [ ] Verify generated client exports and local private paths do not leak into fresh-install command output:

```bash
set -o pipefail
python skills/daemon/scripts/adaptive_loop_executor.py registry 2>&1 | tee /tmp/augur-dev-loops-registry.log
! rg -n "Module file not found|\\.gemini/skills|\\.opencode/skills|~" /tmp/augur-dev-loops-registry.log
python skills/daemon/scripts/adaptive_loop_executor.py status 2>&1 | tee /tmp/augur-dev-loops-status.log
! rg -n "Module file not found|\\.gemini/skills|\\.opencode/skills|~" /tmp/augur-dev-loops-status.log
```

- [ ] Verify docs and source have no public stub text:

```bash
! rg -n "Not yet implemented|diagnose --fix|git reset --hard" \
  skills/daemon/scripts/adaptive_loop_executor.py \
  skills/daemon/scripts/adaptive/engine_fix_phase.py \
  skills/daemon/commands/dev-loops.md \
  skills/daemon/references/dev-loops-implementation.md
```

- [ ] Check formatting and whitespace:

```bash
git diff --check
```

- [ ] Check final worktree state:

```bash
git status --short --branch
```

## Commit Plan

- [ ] Commit canonical discovery and scheduler truthfulness after Tasks 1-3 pass.
- [ ] Commit CLI command operations after Task 4 passes.
- [ ] Commit safe rollback and repo/vault path resolution after Tasks 5-6 pass.
- [ ] Commit smoke test and docs after Tasks 7-9 pass.

Each commit should include only the files for its checkpoint and the tests that prove that checkpoint.

## Acceptance Criteria

- `/dev-loops registry` and `/dev-loops status` do not warn about `.gemini/skills`, `.opencode/skills`, `.codex/skills`, or missing generated callable modules.
- Scheduler ownership is truthful: continuous loops default to daemon; scheduled loops default to Codex unless explicit metadata overrides them.
- Public command docs list only implemented, tested command behavior.
- Missing configured vault is a first-run state with clear remediation, not a private-path fallback.
- Automated LLM fix rollback never runs broad destructive git reset or checkout operations.
- Fresh-install smoke tests cover registry, status, manifest, and report.
- Focused pytest suite and CLI checks pass.
