# Sync Output Classification And Worktree Bootstrap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Classify sync-managed client outputs into explicit git policy buckets, ignore the repo-local bootstrap outputs, and make worktree bootstrap regenerate those outputs automatically.

**Architecture:** Keep `sync_agents` as the canonical producer of repo-local client exports, but stop treating those exports as ad hoc repo files. `.gitignore` becomes the policy layer for `ignored-bootstrap`, while `scripts/worktree_preflight.py` becomes the enforcement layer that repairs missing sync outputs in worktrees by running the canonical `python3 -m skills.ai.scripts.sync_agents sync all` entrypoint. `scripts/worktree-launch.sh` continues to delegate bootstrap readiness to preflight and only needs verification-oriented contract coverage.

**Tech Stack:** Python 3.11, shell (`bash`), pytest, git, existing `sync_agents` package

---

### Task 1: Lock The Git Policy In Tests Before Changing Ignore Rules

**Files:**
- Create: `tests/scripts/test_sync_output_policy.py`
- Reference: `.gitignore`
- Reference: `skills/ai/scripts/sync_agents/engine.py`

- [ ] **Step 1: Write the failing git-policy test file**

```python
from __future__ import annotations

import subprocess
from pathlib import Path

from skills.ai.scripts.sync_agents.engine import _get_all_adapters
from skills.ai.scripts.sync_agents.constants import PROJECT_ROOT


def _repo_local_managed_paths() -> set[str]:
    paths: set[str] = set()
    for adapter in _get_all_adapters():
        for raw in adapter.get_managed_files():
            path = Path(raw)
            if path.is_absolute():
                try:
                    rel = path.resolve().relative_to(PROJECT_ROOT.resolve())
                except ValueError:
                    continue
                paths.add(rel.as_posix())
            else:
                paths.add(path.as_posix())
    return paths


def _is_ignored(path: str) -> bool:
    return (
        subprocess.run(
            ["git", "check-ignore", path],
            cwd=PROJECT_ROOT,
            check=False,
            capture_output=True,
            text=True,
        ).returncode
        == 0
    )


def test_repo_local_sync_outputs_are_explicitly_classified() -> None:
    repo_local = _repo_local_managed_paths()
    expected_ignored = {
        "CLAUDE.md",
        "CODEX.md",
        "AGENTS.md",
        ".claude/mcp.json",
        ".claude/agents",
        ".claude/commands",
        ".clinerules/augur-rules.md",
        ".cursorrules",
        ".cursor/rules",
        ".cursor/agents",
        ".cursor/mcp.json",
        ".cursor/memory",
        ".windsurfrules",
        ".windsurf/rules",
        ".windsurf/skills",
        ".windsurf/mcp.json",
        ".gemini/GEMINI.md",
        ".gemini/skills",
        ".gemini/settings.json",
        ".gemini/unignore",
        ".gemini/workflows",
        ".gemini/topics",
        ".gemini/memory",
        ".gemini/agents",
        ".opencode/AGENTS.md",
        ".opencode/skills",
        ".antigravity",
        ".codex/config.toml",
        ".codex/agents",
        ".codex/prompts",
        ".codex/skills",
        "plugins/augur",
        ".agents/plugins/marketplace.json",
        "build/cowork",
        "build/codex",
    }

    missing = sorted(path for path in expected_ignored if path in repo_local and not _is_ignored(path))
    assert missing == []
```

- [ ] **Step 2: Run the new test and verify it fails**

Run:

```bash
pytest tests/scripts/test_sync_output_policy.py -q
```

Expected: `FAIL` because many current sync-managed repo-local paths are not explicitly ignored yet.

- [ ] **Step 3: Commit the failing-test checkpoint**

```bash
git add tests/scripts/test_sync_output_policy.py
git commit -m "test(sync): lock repo-local sync output policy"
```

### Task 2: Make Ignored-Bootstrap Outputs Explicit In `.gitignore`

**Files:**
- Modify: `.gitignore`
- Test: `tests/scripts/test_sync_output_policy.py`

- [ ] **Step 1: Add a dedicated ignore section for sync bootstrap outputs**

Insert a new section near the existing IDE/generated-file rules:

```gitignore
# Sync-managed local bootstrap outputs (regenerate via sync_agents; never commit)
CLAUDE.md
CODEX.md
AGENTS.md
.claude/mcp.json
.claude/agents/
.claude/commands/
.clinerules/
.cursorrules
.cursor/agents/
.cursor/mcp.json
.cursor/memory/
.windsurfrules
.windsurf/rules/
.windsurf/skills/
.windsurf/mcp.json
.gemini/GEMINI.md
.gemini/skills/
.gemini/settings.json
.gemini/unignore
.gemini/workflows/
.gemini/topics/
.gemini/memory/
.gemini/agents/
.opencode/AGENTS.md
.opencode/skills/
.antigravity/
.codex/config.toml
.codex/agents/
.codex/prompts/
.codex/skills/
.codex/plugins/cache/
.agents/plugins/marketplace.json
plugins/augur/
build/cowork/
build/codex/
```

Keep the existing tracked exceptions such as `!.cursor/rules/augur.mdc` intact and below the new broad ignore rules if needed.

- [ ] **Step 2: Re-run the git-policy test and verify it passes**

Run:

```bash
pytest tests/scripts/test_sync_output_policy.py -q
```

Expected: `1 passed`.

- [ ] **Step 3: Check git classification directly**

Run:

```bash
git check-ignore CLAUDE.md .claude/agents .cursor/agents .gemini/skills plugins/augur .agents/plugins/marketplace.json
```

Expected: each path is printed by `git check-ignore`, confirming the ignore rules are active.

- [ ] **Step 4: Commit the ignore policy**

```bash
git add .gitignore tests/scripts/test_sync_output_policy.py
git commit -m "chore(sync): ignore repo-local sync bootstrap outputs"
```

### Task 3: Teach Worktree Preflight To Repair Missing Sync Outputs

**Files:**
- Modify: `scripts/worktree_preflight.py`
- Modify: `tests/scripts/test_worktree_preflight.py`
- Reference: `skills/ai/scripts/sync_agents/tests/test_runtime_sync_entrypoints.py`

- [ ] **Step 1: Add the failing preflight tests for sync bootstrap repair**

Append tests like these to `tests/scripts/test_worktree_preflight.py`:

```python
def test_build_contract_repairs_missing_sync_outputs_for_worktree(tmp_path: Path, monkeypatch):
    worktree_root = tmp_path / "worktree"
    worktree_root.mkdir()
    (worktree_root / "src").mkdir()
    (worktree_root / "config").mkdir()
    (worktree_root / ".git").write_text("gitdir: /tmp/fake\n", encoding="utf-8")
    (worktree_root / ".augur-worktree.yaml").write_text("worktree: true\n", encoding="utf-8")
    (worktree_root / ".venv").mkdir()
    (worktree_root / ".venv-test").mkdir()
    next_bin = worktree_root / "apps" / "dashboard" / "node_modules" / ".bin"
    next_bin.mkdir(parents=True, exist_ok=True)
    (next_bin / "next").write_text("", encoding="utf-8")

    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()

    monkeypatch.setattr(worktree_preflight, "_resolve_main_repo", lambda *_args: worktree_root)
    monkeypatch.setattr(worktree_preflight, "_resolve_ports", lambda *_args: {"dashboard_port": 3000, "mcp_port": 8080})
    monkeypatch.setattr(worktree_preflight, "_resolve_dev_hubs", lambda *_args: None)
    monkeypatch.setattr(worktree_preflight, "_ensure_runtime", lambda *args, **kwargs: None)
    monkeypatch.setattr(worktree_preflight, "_ensure_dashboard_dependencies", lambda *args, **kwargs: True)

    class _Paths:
        @staticmethod
        def get_runtime_dir() -> Path:
            return runtime_dir

    monkeypatch.setitem(sys.modules, "src.config.paths", _Paths)

    calls: list[tuple[Path, list[worktree_preflight.Repair], list[worktree_preflight.Incident]]] = []

    def _fake_sync(project_root: Path, repairs, incidents):
        calls.append((project_root, repairs, incidents))
        repairs.append(worktree_preflight.Repair(type="sync", path=str(project_root / "CLAUDE.md")))

    monkeypatch.setattr(worktree_preflight, "_ensure_sync_outputs", _fake_sync)

    report = worktree_preflight.build_contract(worktree_root, "worktree", repair=True)

    assert calls and calls[0][0] == worktree_root
    assert any(repair["type"] == "sync" for repair in report["repairs_applied"])


def test_build_contract_records_incident_when_sync_bootstrap_fails(tmp_path: Path, monkeypatch):
    worktree_root = tmp_path / "worktree"
    worktree_root.mkdir()
    (worktree_root / "src").mkdir()
    (worktree_root / "config").mkdir()
    (worktree_root / ".git").write_text("gitdir: /tmp/fake\n", encoding="utf-8")
    (worktree_root / ".augur-worktree.yaml").write_text("worktree: true\n", encoding="utf-8")
    (worktree_root / ".venv").mkdir()
    (worktree_root / ".venv-test").mkdir()
    next_bin = worktree_root / "apps" / "dashboard" / "node_modules" / ".bin"
    next_bin.mkdir(parents=True, exist_ok=True)
    (next_bin / "next").write_text("", encoding="utf-8")

    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()

    monkeypatch.setattr(worktree_preflight, "_resolve_main_repo", lambda *_args: worktree_root)
    monkeypatch.setattr(worktree_preflight, "_resolve_ports", lambda *_args: {"dashboard_port": 3000, "mcp_port": 8080})
    monkeypatch.setattr(worktree_preflight, "_resolve_dev_hubs", lambda *_args: None)
    monkeypatch.setattr(worktree_preflight, "_ensure_runtime", lambda *args, **kwargs: None)
    monkeypatch.setattr(worktree_preflight, "_ensure_dashboard_dependencies", lambda *args, **kwargs: True)

    class _Paths:
        @staticmethod
        def get_runtime_dir() -> Path:
            return runtime_dir

    monkeypatch.setitem(sys.modules, "src.config.paths", _Paths)

    def _fake_sync(project_root: Path, repairs, incidents):
        incidents.append(
            worktree_preflight.Incident(
                fingerprint="worktree/bootstrap/missing-sync-outputs",
                severity="high",
                message="sync bootstrap failed",
                owner_path=str(project_root / "scripts" / "worktree_preflight.py"),
                safe_to_repair=True,
                repaired=False,
            )
        )

    monkeypatch.setattr(worktree_preflight, "_ensure_sync_outputs", _fake_sync)

    report = worktree_preflight.build_contract(worktree_root, "worktree", repair=True)

    fingerprints = {incident["fingerprint"] for incident in report["incidents_detected"]}
    assert "worktree/bootstrap/missing-sync-outputs" in fingerprints
```

- [ ] **Step 2: Run the preflight tests and verify they fail**

Run:

```bash
pytest tests/scripts/test_worktree_preflight.py -q
```

Expected: `FAIL` because `_ensure_sync_outputs` does not exist and the worktree repair flow does not invoke sync bootstrap yet.

- [ ] **Step 3: Add a dedicated sync bootstrap helper to `scripts/worktree_preflight.py`**

Add a helper near the other repair helpers:

```python
def _ensure_sync_outputs(
    project_root: Path,
    repairs: list[Repair],
    incidents: list[Incident],
) -> None:
    command = ["python3", "-m", "skills.ai.scripts.sync_agents", "sync", "all"]
    result = subprocess.run(
        command,
        cwd=project_root,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        repairs.append(Repair(type="sync", path=str(project_root), target=" ".join(command)))
        return

    stderr = (result.stderr or "").strip()
    stdout = (result.stdout or "").strip()
    detail = stderr or stdout or f"exit {result.returncode}"
    incidents.append(
        Incident(
            fingerprint="worktree/bootstrap/missing-sync-outputs",
            severity="high",
            message=f"sync bootstrap failed: {detail}",
            owner_path=str(project_root / "scripts" / "worktree_preflight.py"),
            safe_to_repair=True,
            repaired=False,
        )
    )
```

- [ ] **Step 4: Invoke the sync bootstrap helper from the worktree repair path**

Inside `build_contract(...)`, after runtime/venv/dashboard dependency repair and only when `is_worktree and repair`:

```python
        _ensure_sync_outputs(
            project_root,
            repairs,
            incidents,
        )
```

Keep the invocation inside the worktree branch so the main checkout does not start auto-regenerating repo-local client exports on unrelated shell/mcp profiles.

- [ ] **Step 5: Re-run the preflight tests and verify they pass**

Run:

```bash
pytest tests/scripts/test_worktree_preflight.py -q
```

Expected: all tests pass, including the new sync-bootstrap coverage.

- [ ] **Step 6: Commit the preflight repair behavior**

```bash
git add scripts/worktree_preflight.py tests/scripts/test_worktree_preflight.py
git commit -m "feat(worktree): bootstrap sync outputs during preflight"
```

### Task 4: Lock The Launcher Contract And Sync Command References

**Files:**
- Modify: `tests/scripts/test_worktree_launch.py`
- Modify: `skills/ai/commands/sync-agents.md`
- Verify: `skills/ai/scripts/sync_agents/tests/test_runtime_sync_entrypoints.py`

- [ ] **Step 1: Add a launcher contract test that expects worktree bootstrap to report sync repairs**

Extend `tests/scripts/test_worktree_launch.py` with a focused contract test:

```python
def test_bootstrap_worktree_reports_preflight_repairs() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert "worktree_preflight.py" in text
    assert "--profile worktree --repair" in text
    assert 'json.load(sys.stdin)["repairs_applied"]' in text
```

This keeps the shell contract locked without forcing a brittle end-to-end shell mock harness.

- [ ] **Step 2: Update the sync command doc to explain worktree-local regeneration**

Add a short note in `skills/ai/commands/sync-agents.md` after the Fix section:

```md
In worktrees, repo-local client exports are local bootstrap artifacts. They are regenerated by worktree bootstrap and should not be committed unless they are part of the intentionally versioned tracked-generated set.
```

- [ ] **Step 3: Run the focused contract tests**

Run:

```bash
pytest tests/scripts/test_worktree_launch.py tests/scripts/test_worktree_preflight.py skills/ai/scripts/sync_agents/tests/test_runtime_sync_entrypoints.py -q
```

Expected: all selected tests pass.

- [ ] **Step 4: Commit the launcher/doc contract**

```bash
git add tests/scripts/test_worktree_launch.py skills/ai/commands/sync-agents.md
git commit -m "docs(worktree): document sync bootstrap contract"
```

### Task 5: Verify The End-To-End Policy Locally

**Files:**
- Verify only: `.gitignore`
- Verify only: `scripts/worktree_preflight.py`
- Verify only: `scripts/worktree-launch.sh`
- Verify only: `tests/scripts/test_sync_output_policy.py`
- Verify only: `tests/scripts/test_worktree_preflight.py`
- Verify only: `tests/scripts/test_worktree_launch.py`

- [ ] **Step 1: Run the full focused verification set**

Run:

```bash
pytest \
  tests/scripts/test_sync_output_policy.py \
  tests/scripts/test_worktree_preflight.py \
  tests/scripts/test_worktree_launch.py \
  skills/ai/scripts/sync_agents/tests/test_runtime_sync_entrypoints.py \
  -q
```

Expected: all tests pass.

- [ ] **Step 2: Verify the new ignore policy with git**

Run:

```bash
git check-ignore CLAUDE.md .claude/agents .cursor/agents .gemini/skills .codex/agents plugins/augur .agents/plugins/marketplace.json
```

Expected: every listed path is reported as ignored.

- [ ] **Step 3: Verify preflight can emit a worktree report**

Run:

```bash
python3 scripts/worktree_preflight.py --root . --profile shell
```

Expected: JSON output with `profile`, `checks`, and `verify_passed` fields. This is a sanity check that the script still runs after the helper changes.

- [ ] **Step 4: Review git status for accidental churn**

Run:

```bash
git status --short
```

Expected: only the intentionally edited files from this plan appear. No surprise sync-managed untracked files should remain.

- [ ] **Step 5: Final commit if any verification fixups were needed**

```bash
git add .gitignore scripts/worktree_preflight.py scripts/worktree-launch.sh tests/scripts/test_sync_output_policy.py tests/scripts/test_worktree_preflight.py tests/scripts/test_worktree_launch.py skills/ai/commands/sync-agents.md
git commit -m "fix(sync): finish sync bootstrap classification verification"
```

