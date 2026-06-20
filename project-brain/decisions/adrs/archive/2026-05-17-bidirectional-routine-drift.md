# Bidirectional Routine Drift — Phase D Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the two explicit conflict-resolution actions (`Adopt cloud version`, `Push my version`) per ADR-763, with matching MCP tools, CLI verbs, and dashboard kebab wiring, plus the cache-freshness indicator on `claude-remote` Browse cards.

**Architecture:** Adopt rewrites the seed YAML to match the surface; Push force-syncs the seed over the surface. Both are scoped to a single routine_id. Codex push uses the existing `sync_codex_automations(force=True)`; Claude-remote push spawns `claude --print` to call `RemoteTrigger action=update`, matching the same OAuth boundary as refresh. Dashboard wires both as `mcp-tool` BrowseCardActions on drifted cards — `executeBrowseAction` already dispatches that type generically (see `apps/dashboard/lib/browse/executeAction.ts:84`).

**Tech Stack:** Python (server impls, MCP tools, CLI), pytest (TDD), TypeScript/React (dashboard), `ruamel.yaml` or stdlib `yaml` (seed editing).

**Spec:** `docs/superpowers/specs/2026-05-17-bidirectional-routine-drift-design.md`

**ADR:** `docs/adrs/ADR-763-bidirectional-routine-drift.md`

---

## File map

**Create:**
- `src/lib/runtime/seed_yaml_editor.py` — single-responsibility utility for updating one schedule entry inside a `routine-schedule.yaml`. Preserves other entries verbatim.
- `src/mcp/augur_framework/tools/infrastructure/browse/scheduled_conflict.py` — module owning `adopt_cloud_impl` and `push_local_impl`. Keeps `scheduled_executions.py` focused on listing.
- `shared-vault/skills/daemon/augur/tests/test_seed_yaml_editor.py`
- `shared-vault/skills/daemon/augur/tests/test_routine_adopt_cloud.py`
- `shared-vault/skills/daemon/augur/tests/test_routine_push_local.py`
- `shared-vault/skills/daemon/augur/tests/test_routine_drift_cli_verbs.py`

**Modify:**
- `src/mcp/augur_framework/tools/infrastructure/browse/__init__.py` — register `routine-adopt-cloud` + `routine-push-local`.
- `src/mcp/augur_framework/tools/infrastructure/browse/scheduled_sources/claude_remote.py` — copy `fetched_at` into each emitted record.
- `src/mcp/augur_framework/tools/infrastructure/browse/scheduled_executions.py` — propagate `cache_fetched_at` into `metadata`.
- `shared-vault/skills/daemon/scripts/mcp/__init__.py` — add `adopt` + `push` verbs.
- `apps/dashboard/lib/browse/cardModel.ts` — emit `Adopt cloud` / `Push my version` overflow actions for drifted entries; render freshness label.

---

## Task 1: seed YAML editor utility

**Files:**
- Create: `src/lib/runtime/seed_yaml_editor.py`
- Test: `shared-vault/skills/daemon/augur/tests/test_seed_yaml_editor.py`

- [ ] **Step 1: Write the failing tests**

```python
# shared-vault/skills/daemon/augur/tests/test_seed_yaml_editor.py
"""Tests for seed_yaml_editor surgical YAML updates."""
from __future__ import annotations

import yaml


def test_update_existing_entry_changes_named_fields(tmp_path) -> None:
    from src.lib.runtime.seed_yaml_editor import update_seed_entry

    seed = tmp_path / "routine-schedule.yaml"
    seed.write_text(
        "schedules:\n"
        "  - id: codex-dev-loop-testing\n"
        "    title: Testing\n"
        "    loop: testing\n"
        "    source: codex\n"
        '    rrule: "RRULE:FREQ=WEEKLY;BYDAY=SU;BYHOUR=3;BYMINUTE=0"\n'
        '    prompt: "/dev-loops run testing"\n'
        '    workspace: "__PROJECT_ROOT__"\n'
        '    model: "gpt-5.4"\n'
        '    reasoning_effort: "high"\n'
        "    runs_in: local\n",
        encoding="utf-8",
    )

    changed = update_seed_entry(
        seed,
        schedule_id="codex-dev-loop-testing",
        new_fields={"rrule": "RRULE:FREQ=WEEKLY;BYDAY=WE;BYHOUR=14;BYMINUTE=30"},
    )

    assert changed is True
    payload = yaml.safe_load(seed.read_text(encoding="utf-8"))
    entry = payload["schedules"][0]
    assert entry["rrule"] == "RRULE:FREQ=WEEKLY;BYDAY=WE;BYHOUR=14;BYMINUTE=30"
    assert entry["prompt"] == "/dev-loops run testing"
    assert entry["model"] == "gpt-5.4"


def test_update_missing_id_returns_false(tmp_path) -> None:
    from src.lib.runtime.seed_yaml_editor import update_seed_entry

    seed = tmp_path / "routine-schedule.yaml"
    seed.write_text("schedules: []\n", encoding="utf-8")

    changed = update_seed_entry(seed, schedule_id="nope", new_fields={"rrule": "x"})

    assert changed is False
    assert seed.read_text(encoding="utf-8") == "schedules: []\n"


def test_update_preserves_other_entries(tmp_path) -> None:
    from src.lib.runtime.seed_yaml_editor import update_seed_entry

    seed = tmp_path / "routine-schedule.yaml"
    seed.write_text(
        "schedules:\n"
        "  - id: a\n"
        '    rrule: "RRULE:a"\n'
        "  - id: b\n"
        '    rrule: "RRULE:b"\n',
        encoding="utf-8",
    )

    update_seed_entry(seed, schedule_id="a", new_fields={"rrule": "RRULE:a-new"})

    payload = yaml.safe_load(seed.read_text(encoding="utf-8"))
    by_id = {row["id"]: row for row in payload["schedules"]}
    assert by_id["a"]["rrule"] == "RRULE:a-new"
    assert by_id["b"]["rrule"] == "RRULE:b"
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd ~/Projects/Augur
uv run pytest shared-vault/skills/daemon/augur/tests/test_seed_yaml_editor.py -v
```

Expected: ImportError or ModuleNotFoundError on `src.lib.runtime.seed_yaml_editor`.

- [ ] **Step 3: Write the minimal implementation**

```python
# src/lib/runtime/seed_yaml_editor.py
"""Surgical updates to a single entry in a routine-schedule.yaml seed file.

The editor uses round-trip YAML (load → mutate → dump) and intentionally
accepts the formatting changes PyYAML produces on re-serialization. Seed
files are tracked in git, so cosmetic diff churn on the touched entry is
acceptable; preserving SEMANTICS across other entries is what matters.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def update_seed_entry(
    seed_path: Path,
    *,
    schedule_id: str,
    new_fields: dict[str, Any],
) -> bool:
    """Update one schedule entry in a routine-schedule.yaml.

    Returns True if a matching entry was found and rewritten, False otherwise.
    Other entries pass through untouched (semantically; serialization may
    normalize whitespace and quoting).
    """
    raw = yaml.safe_load(seed_path.read_text(encoding="utf-8")) or {}
    schedules = raw.get("schedules") if isinstance(raw, dict) else None
    if not isinstance(schedules, list):
        return False

    target_index = next(
        (
            index
            for index, entry in enumerate(schedules)
            if isinstance(entry, dict) and str(entry.get("id", "")) == schedule_id
        ),
        None,
    )
    if target_index is None:
        return False

    schedules[target_index].update(new_fields)
    seed_path.write_text(
        yaml.safe_dump(raw, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    return True
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
uv run pytest shared-vault/skills/daemon/augur/tests/test_seed_yaml_editor.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/lib/runtime/seed_yaml_editor.py shared-vault/skills/daemon/augur/tests/test_seed_yaml_editor.py
git commit -m "feat(routines): seed-yaml-editor utility for surgical schedule updates"
```

---

## Task 2: scheduled_conflict module with Codex adopt impl

**Files:**
- Create: `src/mcp/augur_framework/tools/infrastructure/browse/scheduled_conflict.py`
- Test: `shared-vault/skills/daemon/augur/tests/test_routine_adopt_cloud.py`

- [ ] **Step 1: Write the failing test**

```python
# shared-vault/skills/daemon/augur/tests/test_routine_adopt_cloud.py
"""Tests for routine_adopt_cloud_impl."""
from __future__ import annotations

import json
from pathlib import Path


def _seed_skill(tmp_path: Path) -> Path:
    skill_root = tmp_path / "shared-vault" / "skills" / "routine-codebase"
    seeds_dir = skill_root / "assets" / "seeds"
    seeds_dir.mkdir(parents=True)
    seed = seeds_dir / "routine-schedule.yaml"
    seed.write_text(
        "schedules:\n"
        "  - id: codex-dev-loop-testing\n"
        "    title: Testing\n"
        "    loop: testing\n"
        "    source: codex\n"
        '    rrule: "RRULE:FREQ=WEEKLY;BYDAY=SU;BYHOUR=3;BYMINUTE=0"\n'
        '    prompt: "/dev-loops run testing"\n'
        '    workspace: "__PROJECT_ROOT__"\n'
        '    model: "gpt-5.4"\n'
        '    reasoning_effort: "high"\n'
        "    runs_in: local\n",
        encoding="utf-8",
    )
    return seed


def test_adopt_codex_rewrites_seed_to_match_installed_toml(tmp_path, monkeypatch) -> None:
    from src.lib.runtime.codex_automations import sync_codex_automations
    from src.mcp.augur_framework.tools.infrastructure.browse.scheduled_conflict import (
        adopt_cloud_impl,
    )

    monkeypatch.setenv("HOME", str(tmp_path))
    seed = _seed_skill(tmp_path)
    schedules = [
        {
            "id": "codex-dev-loop-testing",
            "title": "Testing",
            "rrule": "RRULE:FREQ=WEEKLY;BYDAY=SU;BYHOUR=3;BYMINUTE=0",
            "prompt": "/dev-loops run testing",
            "workspace": str(tmp_path),
            "model": "gpt-5.4",
            "reasoning_effort": "high",
            "runs_in": "local",
        }
    ]
    sync_codex_automations(schedules, apply=True, prune=False)
    toml_path = tmp_path / ".codex" / "automations" / "codex-dev-loop-testing" / "automation.toml"
    body = toml_path.read_text(encoding="utf-8")
    body = body.replace(
        'rrule = "RRULE:FREQ=WEEKLY;BYDAY=SU;BYHOUR=3;BYMINUTE=0"',
        'rrule = "RRULE:FREQ=WEEKLY;BYDAY=WE;BYHOUR=14;BYMINUTE=30"',
    )
    toml_path.write_text(body, encoding="utf-8")

    result = adopt_cloud_impl(
        routine_id="codex:codex-dev-loop-testing",
        seed_search_roots=[tmp_path / "shared-vault" / "skills"],
    )

    payload = json.loads(result)
    assert payload["success"] is True
    import yaml

    seed_after = yaml.safe_load(seed.read_text(encoding="utf-8"))
    entry = seed_after["schedules"][0]
    assert entry["rrule"] == "RRULE:FREQ=WEEKLY;BYDAY=WE;BYHOUR=14;BYMINUTE=30"


def test_adopt_claude_remote_is_noop_success(tmp_path) -> None:
    from src.mcp.augur_framework.tools.infrastructure.browse.scheduled_conflict import (
        adopt_cloud_impl,
    )

    result = adopt_cloud_impl(
        routine_id="claude-remote:trig_abc",
        seed_search_roots=[tmp_path],
    )
    payload = json.loads(result)
    assert payload["success"] is True
    assert "no-op" in payload["message"].lower() or "no seed" in payload["message"].lower()


def test_adopt_unknown_routine_returns_error(tmp_path) -> None:
    from src.mcp.augur_framework.tools.infrastructure.browse.scheduled_conflict import (
        adopt_cloud_impl,
    )

    result = adopt_cloud_impl(
        routine_id="codex:does-not-exist",
        seed_search_roots=[tmp_path],
    )
    payload = json.loads(result)
    assert payload["success"] is False
    assert "not found" in payload["error"].lower()
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
uv run pytest shared-vault/skills/daemon/augur/tests/test_routine_adopt_cloud.py -v
```

Expected: ModuleNotFoundError on `scheduled_conflict`.

- [ ] **Step 3: Write the minimal implementation**

```python
# src/mcp/augur_framework/tools/infrastructure/browse/scheduled_conflict.py
"""Per-routine conflict resolution impls: Adopt cloud / Push my version.

Owned by ADR-763. Kept separate from scheduled_executions.py so the listing
aggregator stays read-only and these mutators stay easy to find.
"""
from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import Iterable


def _source_and_native_id(routine_id: str) -> tuple[str, str]:
    """Split a Browse routine id like ``codex:codex-dev-loop-testing``."""
    if ":" not in routine_id:
        return ("", routine_id)
    source, _, native = routine_id.partition(":")
    return (source, native)


def _find_seed_owning_id(
    schedule_id: str, search_roots: Iterable[Path]
) -> Path | None:
    """Locate the routine-schedule.yaml seed whose schedules[].id matches."""
    import yaml

    for root in search_roots:
        if not root.is_dir():
            continue
        for seed_path in root.glob("*/assets/seeds/routine-schedule.yaml"):
            try:
                raw = yaml.safe_load(seed_path.read_text(encoding="utf-8")) or {}
            except Exception:
                continue
            schedules = raw.get("schedules") if isinstance(raw, dict) else None
            if not isinstance(schedules, list):
                continue
            for entry in schedules:
                if isinstance(entry, dict) and str(entry.get("id", "")) == schedule_id:
                    return seed_path
    return None


def _default_seed_search_roots() -> list[Path]:
    """Project + private vault skill roots used when caller passes None."""
    try:
        from src.config.paths import (
            get_managed_skill_source_dirs,
            get_project_root,
        )
    except Exception:
        return []

    roots: list[Path] = []
    try:
        roots.extend(Path(r) for r in get_managed_skill_source_dirs())
    except Exception:
        pass
    shared = get_project_root() / "shared-vault" / "skills"
    if shared.is_dir() and shared not in roots:
        roots.append(shared)
    return roots


def adopt_cloud_impl(
    routine_id: str,
    *,
    seed_search_roots: Iterable[Path] | None = None,
) -> str:
    """Pull installed-surface state into the seed file for one routine.

    Codex: reads ~/.codex/automations/<id>/automation.toml, finds the seed
    YAML that declares that id, rewrites that single entry to match the TOML
    fields. After adoption the next sync's drift check returns in-sync.

    Claude-remote: there is no seed file for cloud routines today. The action
    is a no-op success that acknowledges the cache as desired.
    """
    from src.lib.runtime.seed_yaml_editor import update_seed_entry

    source, native_id = _source_and_native_id(routine_id)

    if source == "claude-remote":
        return json.dumps(
            {
                "success": True,
                "message": "claude-remote has no seed file; adoption is a no-op (cache is the registry).",
            }
        )

    if source != "codex":
        return json.dumps(
            {"success": False, "error": f"adopt unsupported for source {source!r}"}
        )

    toml_path = Path.home() / ".codex" / "automations" / native_id / "automation.toml"
    if not toml_path.is_file():
        return json.dumps(
            {"success": False, "error": f"installed TOML not found for {native_id!r}"}
        )

    try:
        data = tomllib.loads(toml_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return json.dumps({"success": False, "error": f"parse failed: {exc}"})

    cwds = data.get("cwds") or [""]
    workspace = str(cwds[0]) if isinstance(cwds, list) and cwds else ""
    new_fields = {
        "rrule": str(data.get("rrule", "")),
        "prompt": str(data.get("prompt", "")),
        "model": str(data.get("model", "")),
        "reasoning_effort": str(data.get("reasoning_effort", "")),
        "workspace": workspace,
    }

    search_roots = (
        list(seed_search_roots) if seed_search_roots is not None else _default_seed_search_roots()
    )
    seed_path = _find_seed_owning_id(native_id, search_roots)
    if seed_path is None:
        return json.dumps(
            {"success": False, "error": f"no seed file owns id {native_id!r} (entry may be external)"}
        )

    updated = update_seed_entry(seed_path, schedule_id=native_id, new_fields=new_fields)
    if not updated:
        return json.dumps(
            {"success": False, "error": "seed update failed unexpectedly"}
        )

    return json.dumps(
        {
            "success": True,
            "message": f"adopted surface state for {native_id!r}",
            "seed_path": str(seed_path),
            "applied_fields": new_fields,
        }
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
uv run pytest shared-vault/skills/daemon/augur/tests/test_routine_adopt_cloud.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/mcp/augur_framework/tools/infrastructure/browse/scheduled_conflict.py shared-vault/skills/daemon/augur/tests/test_routine_adopt_cloud.py
git commit -m "feat(routines): adopt_cloud_impl rewrites seed from installed Codex TOML"
```

---

## Task 3: Push impl for Codex source

**Files:**
- Modify: `src/mcp/augur_framework/tools/infrastructure/browse/scheduled_conflict.py`
- Test: `shared-vault/skills/daemon/augur/tests/test_routine_push_local.py`

- [ ] **Step 1: Write the failing test**

```python
# shared-vault/skills/daemon/augur/tests/test_routine_push_local.py
"""Tests for push_local_impl."""
from __future__ import annotations

import json
from pathlib import Path


def test_push_codex_overwrites_drifted_toml_with_seed_values(tmp_path, monkeypatch) -> None:
    from src.lib.runtime.codex_automations import sync_codex_automations
    from src.mcp.augur_framework.tools.infrastructure.browse.scheduled_conflict import (
        push_local_impl,
    )

    monkeypatch.setenv("HOME", str(tmp_path))
    schedules = [
        {
            "id": "codex-dev-loop-testing",
            "title": "Testing",
            "rrule": "RRULE:FREQ=WEEKLY;BYDAY=SU;BYHOUR=3;BYMINUTE=0",
            "prompt": "/dev-loops run testing",
            "workspace": str(tmp_path),
            "model": "gpt-5.4",
            "reasoning_effort": "high",
            "runs_in": "local",
        }
    ]
    sync_codex_automations(schedules, apply=True, prune=False)
    toml_path = tmp_path / ".codex" / "automations" / "codex-dev-loop-testing" / "automation.toml"
    body = toml_path.read_text(encoding="utf-8")
    body = body.replace(
        'rrule = "RRULE:FREQ=WEEKLY;BYDAY=SU;BYHOUR=3;BYMINUTE=0"',
        'rrule = "RRULE:FREQ=WEEKLY;BYDAY=WE;BYHOUR=14;BYMINUTE=30"',
    )
    toml_path.write_text(body, encoding="utf-8")

    result = push_local_impl(
        routine_id="codex:codex-dev-loop-testing",
        desired_schedules=schedules,
    )

    payload = json.loads(result)
    assert payload["success"] is True
    final = toml_path.read_text(encoding="utf-8")
    assert 'rrule = "RRULE:FREQ=WEEKLY;BYDAY=SU;BYHOUR=3;BYMINUTE=0"' in final
    assert "BYDAY=WE" not in final


def test_push_codex_unknown_id_returns_error(tmp_path, monkeypatch) -> None:
    from src.mcp.augur_framework.tools.infrastructure.browse.scheduled_conflict import (
        push_local_impl,
    )

    monkeypatch.setenv("HOME", str(tmp_path))
    result = push_local_impl(
        routine_id="codex:does-not-exist",
        desired_schedules=[],
    )
    payload = json.loads(result)
    assert payload["success"] is False
    assert "not in desired" in payload["error"].lower() or "not found" in payload["error"].lower()
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
uv run pytest shared-vault/skills/daemon/augur/tests/test_routine_push_local.py -v
```

Expected: ImportError on `push_local_impl`.

- [ ] **Step 3: Append push_local_impl to scheduled_conflict.py**

Open `src/mcp/augur_framework/tools/infrastructure/browse/scheduled_conflict.py` and add this function at the end of the file:

```python
def push_local_impl(
    routine_id: str,
    *,
    desired_schedules: list[dict] | None = None,
) -> str:
    """Force-sync seed state over the installed surface for one routine.

    Codex: invokes sync_codex_automations(force=True) scoped to this id.
    Claude-remote: not implemented in this commit — separate task spawns
    `claude --print` to call RemoteTrigger update.
    """
    from src.lib.runtime.codex_automations import sync_codex_automations

    source, native_id = _source_and_native_id(routine_id)

    if source != "codex":
        return json.dumps(
            {
                "success": False,
                "error": f"push not yet implemented for source {source!r}",
            }
        )

    if desired_schedules is None:
        desired_schedules = _load_all_desired_codex_schedules()

    target = next(
        (s for s in desired_schedules if str(s.get("id", "")) == native_id),
        None,
    )
    if target is None:
        return json.dumps(
            {
                "success": False,
                "error": f"routine {native_id!r} not in desired seeds; nothing to push",
            }
        )

    written = sync_codex_automations(
        [target], apply=True, prune=False, force=True
    )
    return json.dumps(
        {
            "success": True,
            "message": f"pushed seed for {native_id!r}",
            "written": [str(p) for p in written],
        }
    )


def _load_all_desired_codex_schedules() -> list[dict]:
    """Default seed loader; mirrors scheduled_sources/codex.py:_load_desired_seeds."""
    try:
        from src.lib.runtime.codex_automations import load_codex_schedule_seed
        from src.config.paths import get_project_root
    except Exception:
        return []

    project_root = get_project_root()
    schedules: list[dict] = []
    seen: set[str] = set()
    for root in _default_seed_search_roots():
        if not root.is_dir():
            continue
        for seed_path in root.glob("*/assets/seeds/routine-schedule.yaml"):
            try:
                rows = load_codex_schedule_seed(seed_path, project_root=project_root)
            except Exception:
                continue
            for row in rows:
                schedule_id = str(row.get("id", ""))
                if schedule_id and schedule_id not in seen:
                    seen.add(schedule_id)
                    schedules.append(row)
    return schedules
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
uv run pytest shared-vault/skills/daemon/augur/tests/test_routine_push_local.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/mcp/augur_framework/tools/infrastructure/browse/scheduled_conflict.py shared-vault/skills/daemon/augur/tests/test_routine_push_local.py
git commit -m "feat(routines): push_local_impl for Codex via scoped force-sync"
```

---

## Task 4: Push impl for Claude remote via claude --print subprocess

**Files:**
- Modify: `src/mcp/augur_framework/tools/infrastructure/browse/scheduled_conflict.py`
- Modify: `shared-vault/skills/daemon/augur/tests/test_routine_push_local.py`

- [ ] **Step 1: Add the failing test**

Append to `shared-vault/skills/daemon/augur/tests/test_routine_push_local.py`:

```python
def test_push_claude_remote_spawns_claude_print_with_update_prompt(tmp_path, monkeypatch) -> None:
    """When subprocess succeeds, the impl reports success and echoes the trigger id."""
    import json as _json
    from src.mcp.augur_framework.tools.infrastructure.browse import scheduled_conflict
    from src.config.paths import get_cache_dir

    cache_dir = get_cache_dir()
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / "claude-remote-routines.json"
    cache_path.write_text(
        _json.dumps(
            {
                "fetched_at": "2026-05-17T22:00:00Z",
                "routines": [
                    {
                        "id": "trig_abc123",
                        "name": "Augur Dream",
                        "cron_expression": "0 1 * * *",
                        "enabled": True,
                        "prompt_summary": "/routines run dream",
                        "model": "claude-sonnet-4-6",
                        "repo": "https://github.com/gsannikov/augur",
                        "last_run_at": None,
                        "next_run_at": "2026-05-18T01:00:00Z",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    captured: dict[str, object] = {}

    class _StubResult:
        returncode = 0
        stdout = "OK"
        stderr = ""

    def _fake_run(cmd, capture_output, timeout, text, check):
        captured["cmd"] = cmd
        return _StubResult()

    monkeypatch.setattr(scheduled_conflict.subprocess, "run", _fake_run)
    monkeypatch.setattr(scheduled_conflict.shutil, "which", lambda _: "/usr/local/bin/claude")

    result = scheduled_conflict.push_local_impl(routine_id="claude-remote:trig_abc123")
    payload = _json.loads(result)

    assert payload["success"] is True
    assert "trig_abc123" in payload["message"]
    cmd = captured["cmd"]
    assert cmd[0] == "/usr/local/bin/claude"
    assert "--print" in cmd
    prompt = cmd[-1]
    assert "trig_abc123" in prompt
    assert "RemoteTrigger" in prompt
    assert "update" in prompt
```

- [ ] **Step 2: Run the new test to verify it fails**

```bash
uv run pytest shared-vault/skills/daemon/augur/tests/test_routine_push_local.py::test_push_claude_remote_spawns_claude_print_with_update_prompt -v
```

Expected: AttributeError on `subprocess` / fall-through to "not yet implemented" error.

- [ ] **Step 3: Add subprocess + shutil imports and extend push_local_impl**

Edit `src/mcp/augur_framework/tools/infrastructure/browse/scheduled_conflict.py`:

Add at top (after existing imports):

```python
import shutil
import subprocess
```

Replace the early-return block in `push_local_impl`:

```python
    if source != "codex":
        return json.dumps(
            {
                "success": False,
                "error": f"push not yet implemented for source {source!r}",
            }
        )
```

with:

```python
    if source == "claude-remote":
        return _push_claude_remote(native_id)

    if source != "codex":
        return json.dumps(
            {
                "success": False,
                "error": f"push not supported for source {source!r}",
            }
        )
```

Then add this helper at the bottom of the file:

```python
def _push_claude_remote(trigger_id: str) -> str:
    """Push the cached cron/prompt for a claude-remote routine back to cloud.

    Spawns `claude --print` so the subprocess inherits OAuth via the Claude
    CLI. Server-side Python never sees the token directly. Matches the
    refresh path's auth boundary.
    """
    from src.config.paths import get_cache_dir

    claude_bin = shutil.which("claude")
    if not claude_bin:
        return json.dumps(
            {
                "success": False,
                "error": "claude CLI not on PATH; install Claude Code to enable cloud push.",
            }
        )

    cache_path = get_cache_dir() / "claude-remote-routines.json"
    if not cache_path.is_file():
        return json.dumps(
            {
                "success": False,
                "error": "claude-remote cache missing; refresh first.",
            }
        )

    try:
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return json.dumps({"success": False, "error": f"cache parse failed: {exc}"})

    routines = cache.get("routines") if isinstance(cache, dict) else None
    if not isinstance(routines, list):
        return json.dumps(
            {"success": False, "error": "cache missing routines array"}
        )

    target = next(
        (r for r in routines if isinstance(r, dict) and str(r.get("id", "")) == trigger_id),
        None,
    )
    if target is None:
        return json.dumps(
            {"success": False, "error": f"trigger {trigger_id!r} not in cache"}
        )

    prompt = (
        f"Call the RemoteTrigger tool with action='update', "
        f"trigger_id='{trigger_id}', and body={{'cron_expression': "
        f"'{target.get('cron_expression', '')}', 'enabled': "
        f"{str(bool(target.get('enabled', True))).lower()}}}. "
        'Reply with only the literal string "OK" on success or "ERR: <reason>" on failure.'
    )

    try:
        result = subprocess.run(
            [claude_bin, "--print", prompt],
            capture_output=True,
            timeout=120,
            text=True,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return json.dumps(
            {"success": False, "error": "claude --print timed out after 120s"}
        )

    if result.returncode != 0:
        return json.dumps(
            {
                "success": False,
                "error": f"claude --print exited {result.returncode}",
                "stderr": result.stderr[-500:],
            }
        )

    return json.dumps(
        {
            "success": True,
            "message": f"pushed claude-remote routine {trigger_id} to cloud",
            "stdout": result.stdout[-200:],
        }
    )
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
uv run pytest shared-vault/skills/daemon/augur/tests/test_routine_push_local.py -v
```

Expected: 3 passed (the new one plus the 2 existing codex ones).

- [ ] **Step 5: Commit**

```bash
git add src/mcp/augur_framework/tools/infrastructure/browse/scheduled_conflict.py shared-vault/skills/daemon/augur/tests/test_routine_push_local.py
git commit -m "feat(routines): push_local_impl for claude-remote via claude --print"
```

---

## Task 5: Register routine-adopt-cloud + routine-push-local MCP tools

**Files:**
- Modify: `src/mcp/augur_framework/tools/infrastructure/browse/__init__.py`

- [ ] **Step 1: Extend the import block**

Find the line near the top of `src/mcp/augur_framework/tools/infrastructure/browse/__init__.py`:

```python
from .scheduled_executions import (
    get_scheduled_execution_detail_impl,
    refresh_cloud_routines_impl,
    refresh_codex_routines_impl,
)
```

Add after it:

```python
from .scheduled_conflict import adopt_cloud_impl, push_local_impl
```

- [ ] **Step 2: Register the two new MCP tools**

Find the `routine-refresh-cloud` tool definition inside `register_browse_tools`. After its closing `async def routine_refresh_cloud(...)` block, insert:

```python
    @mcp.tool(
        name="routine-adopt-cloud",
        annotations=tool_annotations(
            {
                "title": "Adopt Surface State into Seed",
                "readOnlyHint": False,
                "destructiveHint": True,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    async def routine_adopt_cloud(routine_id: str) -> str:
        """Pull the installed surface state into the seed file for one routine.

        Args:
            routine_id: Browse id, e.g. "codex:codex-dev-loop-testing".
        """
        return adopt_cloud_impl(routine_id)

    @mcp.tool(
        name="routine-push-local",
        annotations=tool_annotations(
            {
                "title": "Push Seed over Installed Surface",
                "readOnlyHint": False,
                "destructiveHint": True,
                "idempotentHint": True,
                "openWorldHint": True,
            }
        ),
    )
    async def routine_push_local(routine_id: str) -> str:
        """Force-sync seed state over the installed surface for one routine.

        Args:
            routine_id: Browse id, e.g. "codex:codex-dev-loop-testing"
                or "claude-remote:trig_abc123".
        """
        return push_local_impl(routine_id)
```

- [ ] **Step 3: Verify the MCP server starts cleanly**

```bash
uv run python -c "
from src.mcp.augur_framework.tools.infrastructure.browse.scheduled_conflict import adopt_cloud_impl, push_local_impl
print('imports OK')
"
```

Expected: `imports OK`.

- [ ] **Step 4: Commit**

```bash
git add src/mcp/augur_framework/tools/infrastructure/browse/__init__.py
git commit -m "feat(routines): register routine-adopt-cloud + routine-push-local MCP tools"
```

---

## Task 6: CLI verbs `aug routine adopt` and `aug routine push`

**Files:**
- Modify: `shared-vault/skills/daemon/scripts/mcp/__init__.py`
- Create: `shared-vault/skills/daemon/augur/tests/test_routine_drift_cli_verbs.py`

- [ ] **Step 1: Write the failing test**

```python
# shared-vault/skills/daemon/augur/tests/test_routine_drift_cli_verbs.py
"""Tests for `aug routine adopt` and `aug routine push` CLI verbs."""
from __future__ import annotations

import json
import subprocess


def test_adopt_verb_dispatches_adopt_cloud_impl_with_routine_id() -> None:
    result = subprocess.run(
        ["scripts/augur", "routine", "adopt", "codex:does-not-exist"],
        capture_output=True,
        text=True,
        check=False,
        cwd="~/Projects/Augur",
    )
    assert result.returncode != 0, "missing id should surface as failure"
    start = result.stdout.find("{")
    payload = json.loads(result.stdout[start:])
    assert payload["success"] is False
    assert "not found" in payload["error"].lower()


def test_push_verb_dispatches_push_local_impl_with_routine_id() -> None:
    result = subprocess.run(
        ["scripts/augur", "routine", "push", "codex:does-not-exist"],
        capture_output=True,
        text=True,
        check=False,
        cwd="~/Projects/Augur",
    )
    assert result.returncode != 0
    start = result.stdout.find("{")
    payload = json.loads(result.stdout[start:])
    assert payload["success"] is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest shared-vault/skills/daemon/augur/tests/test_routine_drift_cli_verbs.py -v
```

Expected: failure — verbs not registered, CLI returns error about unknown verb.

- [ ] **Step 3: Extend the verb registry**

Edit `shared-vault/skills/daemon/scripts/mcp/__init__.py`.

Find `_ROUTINE_VERBS`:

```python
_ROUTINE_VERBS = [
    "list",
    "status",
    "run",
    "report",
    "schedule",
    "scan-only",
    "orchestrate",
    "pending-escalations",
    "drift",
]
```

Replace with:

```python
_ROUTINE_VERBS = [
    "list",
    "status",
    "run",
    "report",
    "schedule",
    "scan-only",
    "orchestrate",
    "pending-escalations",
    "drift",
    "adopt",
    "push",
]
```

- [ ] **Step 4: Register the two new subparsers**

In the same file, find the `p_drift = sub.add_parser("drift", ...)` block. After the line `parser.set_defaults(func=_run_routine_cli)`, walk back up and insert (before `parser.set_defaults`):

```python
    p_adopt = sub.add_parser(
        "adopt",
        help="adopt installed-surface state into the owning seed file",
    )
    p_adopt.add_argument("routine_id", help="Browse routine id, e.g. codex:codex-dev-loop-testing")

    p_push = sub.add_parser(
        "push",
        help="force-sync seed over installed surface for one routine",
    )
    p_push.add_argument("routine_id", help="Browse routine id")
```

- [ ] **Step 5: Add dispatch branches**

In the same file, find:

```python
        elif verb == "drift":
            payload = _routine_drift_payload(source=getattr(args, "source", "all"))
        else:
```

Replace with:

```python
        elif verb == "drift":
            payload = _routine_drift_payload(source=getattr(args, "source", "all"))
        elif verb == "adopt":
            payload = _routine_adopt_payload(routine_id=getattr(args, "routine_id"))
        elif verb == "push":
            payload = _routine_push_payload(routine_id=getattr(args, "routine_id"))
        else:
```

- [ ] **Step 6: Add the two payload helpers**

In the same file, near `_routine_drift_payload`, add:

```python
def _routine_adopt_payload(*, routine_id: str) -> dict[str, Any]:
    try:
        from src.mcp.augur_framework.tools.infrastructure.browse.scheduled_conflict import (
            adopt_cloud_impl,
        )
    except Exception as exc:  # noqa: BLE001
        return {"success": False, "error": f"could not load scheduled_conflict: {exc}"}
    import json as _json

    return _json.loads(adopt_cloud_impl(routine_id))


def _routine_push_payload(*, routine_id: str) -> dict[str, Any]:
    try:
        from src.mcp.augur_framework.tools.infrastructure.browse.scheduled_conflict import (
            push_local_impl,
        )
    except Exception as exc:  # noqa: BLE001
        return {"success": False, "error": f"could not load scheduled_conflict: {exc}"}
    import json as _json

    return _json.loads(push_local_impl(routine_id))
```

- [ ] **Step 7: Run the CLI tests to verify they pass**

```bash
uv run pytest shared-vault/skills/daemon/augur/tests/test_routine_drift_cli_verbs.py -v
```

Expected: 2 passed.

- [ ] **Step 8: Commit**

```bash
git add shared-vault/skills/daemon/scripts/mcp/__init__.py shared-vault/skills/daemon/augur/tests/test_routine_drift_cli_verbs.py
git commit -m "feat(routines): aug routine adopt + push CLI verbs"
```

---

## Task 7: Surface `fetched_at` on `claude-remote` Browse rows

**Files:**
- Modify: `src/mcp/augur_framework/tools/infrastructure/browse/scheduled_sources/claude_remote.py`
- Modify: `src/mcp/augur_framework/tools/infrastructure/browse/scheduled_executions.py`

- [ ] **Step 1: Write the failing test**

Create `shared-vault/skills/daemon/augur/tests/test_claude_remote_freshness.py`:

```python
"""Tests that the claude-remote cache fetched_at surfaces into Browse metadata."""
from __future__ import annotations

import json


def test_load_claude_remote_schedules_emits_cache_fetched_at(tmp_path, monkeypatch) -> None:
    from src.config import paths as _paths
    monkeypatch.setattr(_paths, "get_cache_dir", lambda: tmp_path)
    cache = tmp_path / "claude-remote-routines.json"
    cache.write_text(
        json.dumps(
            {
                "fetched_at": "2026-05-17T22:00:00Z",
                "routines": [
                    {
                        "id": "trig_x",
                        "name": "Test",
                        "cron_expression": "0 1 * * *",
                        "enabled": True,
                        "prompt_summary": "/r",
                        "model": "m",
                        "repo": "r",
                        "last_run_at": None,
                        "next_run_at": None,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    from src.mcp.augur_framework.tools.infrastructure.browse.scheduled_sources.claude_remote import (
        load_claude_remote_schedules,
    )
    rows = load_claude_remote_schedules()
    assert len(rows) == 1
    assert rows[0].get("cache_fetched_at") == "2026-05-17T22:00:00Z"


def test_scheduled_execution_items_propagate_cache_freshness(tmp_path, monkeypatch) -> None:
    from src.config import paths as _paths
    monkeypatch.setattr(_paths, "get_cache_dir", lambda: tmp_path)
    (tmp_path / "claude-remote-routines.json").write_text(
        json.dumps(
            {
                "fetched_at": "2026-05-17T22:00:00Z",
                "routines": [
                    {
                        "id": "trig_x",
                        "name": "Test",
                        "cron_expression": "0 1 * * *",
                        "enabled": True,
                        "prompt_summary": "/r",
                        "model": "m",
                        "repo": "r",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    from src.mcp.augur_framework.tools.infrastructure.browse.scheduled_executions import (
        list_scheduled_execution_items,
    )
    rows = list_scheduled_execution_items()
    cloud = [r for r in rows if r["metadata"].get("source") == "claude-remote"]
    assert cloud, "expected at least one claude-remote row"
    assert cloud[0]["metadata"].get("cacheFetchedAt") == "2026-05-17T22:00:00Z"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest shared-vault/skills/daemon/augur/tests/test_claude_remote_freshness.py -v
```

Expected: both assertions fail (`cache_fetched_at` not set, `cacheFetchedAt` not in metadata).

- [ ] **Step 3: Plumb fetched_at through load_claude_remote_schedules**

Edit `src/mcp/augur_framework/tools/infrastructure/browse/scheduled_sources/claude_remote.py`. Find the `for routine in payload.get("routines", []):` loop and at the start of each iteration capture the top-level fetched_at:

Replace this section:

```python
    rows: list[dict[str, Any]] = []
    for routine in payload.get("routines", []):
        if not isinstance(routine, dict):
            continue
        routine_id = str(routine.get("id", ""))
        if not routine_id:
            continue
        drift_status = str(routine.get("drift_status") or "in-sync")
        rows.append(
            {
                "id": f"claude-remote:{routine_id}",
```

with:

```python
    rows: list[dict[str, Any]] = []
    cache_fetched_at = str(payload.get("fetched_at") or "")
    for routine in payload.get("routines", []):
        if not isinstance(routine, dict):
            continue
        routine_id = str(routine.get("id", ""))
        if not routine_id:
            continue
        drift_status = str(routine.get("drift_status") or "in-sync")
        rows.append(
            {
                "id": f"claude-remote:{routine_id}",
                "cache_fetched_at": cache_fetched_at,
```

- [ ] **Step 4: Propagate it through scheduled_executions metadata**

Edit `src/mcp/augur_framework/tools/infrastructure/browse/scheduled_executions.py`. Find the metadata dict in `list_scheduled_execution_items`:

```python
                "metadata": {
                    "source": record.get("source", ""),
                    "kind": record.get("kind", ""),
                    "status": record.get("status", "unknown"),
                    "schedule": record.get("schedule_human", ""),
                    "workspace": record.get("workspace", ""),
                    "model": record.get("model", ""),
                    "lastRun": record.get("last_run_at"),
                    "nextRun": record.get("next_run_at"),
                    "managed_by": record.get("managed_by", "unknown"),
                    "drift_status": record.get("drift_status", "unknown"),
                },
```

Add one line:

```python
                "metadata": {
                    "source": record.get("source", ""),
                    "kind": record.get("kind", ""),
                    "status": record.get("status", "unknown"),
                    "schedule": record.get("schedule_human", ""),
                    "workspace": record.get("workspace", ""),
                    "model": record.get("model", ""),
                    "lastRun": record.get("last_run_at"),
                    "nextRun": record.get("next_run_at"),
                    "managed_by": record.get("managed_by", "unknown"),
                    "drift_status": record.get("drift_status", "unknown"),
                    "cacheFetchedAt": record.get("cache_fetched_at", ""),
                },
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest shared-vault/skills/daemon/augur/tests/test_claude_remote_freshness.py -v
```

Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add src/mcp/augur_framework/tools/infrastructure/browse/scheduled_sources/claude_remote.py src/mcp/augur_framework/tools/infrastructure/browse/scheduled_executions.py shared-vault/skills/daemon/augur/tests/test_claude_remote_freshness.py
git commit -m "feat(routines): surface claude-remote cache freshness in Browse metadata"
```

---

## Task 8: Server-side actions emission + dashboard freshness row

The dashboard's `buildBrowseCardModel` already merges `item.actions` from the server response into the card's overflow menu (`cardModel.ts:595`). The cleanest way to add `Adopt` / `Push` to the kebab is to emit them from `scheduled_executions.list_scheduled_execution_items` on drifted entries. The TypeScript change is then minimal: only add the freshness row to `routineSlots`.

**Files:**
- Modify: `src/mcp/augur_framework/tools/infrastructure/browse/scheduled_executions.py`
- Modify: `apps/dashboard/lib/browse/cardModel.ts`

- [ ] **Step 1: Write the failing test for server-side actions**

Create `shared-vault/skills/daemon/augur/tests/test_scheduled_executions_actions.py`:

```python
"""Tests that drifted routines emit Adopt/Push BrowseCardActions server-side."""
from __future__ import annotations

import json
from pathlib import Path


def test_drifted_codex_entry_emits_adopt_and_push_actions(tmp_path, monkeypatch) -> None:
    from src.lib.runtime.codex_automations import sync_codex_automations
    from src.mcp.augur_framework.tools.infrastructure.browse.scheduled_executions import (
        list_scheduled_execution_items,
    )

    monkeypatch.setenv("HOME", str(tmp_path))
    skill_root = tmp_path / "shared-vault" / "skills" / "routine-codebase"
    seeds_dir = skill_root / "assets" / "seeds"
    seeds_dir.mkdir(parents=True)
    (seeds_dir / "routine-schedule.yaml").write_text(
        "schedules:\n"
        "  - id: codex-dev-loop-testing\n"
        '    rrule: "RRULE:FREQ=WEEKLY;BYDAY=SU;BYHOUR=3;BYMINUTE=0"\n'
        '    prompt: "/dev-loops run testing"\n'
        '    workspace: "__PROJECT_ROOT__"\n'
        '    model: "gpt-5.4"\n'
        '    reasoning_effort: "high"\n'
        "    runs_in: local\n",
        encoding="utf-8",
    )
    schedules = [
        {
            "id": "codex-dev-loop-testing",
            "title": "Testing",
            "rrule": "RRULE:FREQ=WEEKLY;BYDAY=SU;BYHOUR=3;BYMINUTE=0",
            "prompt": "/dev-loops run testing",
            "workspace": str(tmp_path),
            "model": "gpt-5.4",
            "reasoning_effort": "high",
            "runs_in": "local",
        }
    ]
    sync_codex_automations(schedules, apply=True, prune=False)
    toml_path = tmp_path / ".codex" / "automations" / "codex-dev-loop-testing" / "automation.toml"
    body = toml_path.read_text(encoding="utf-8")
    body = body.replace(
        'rrule = "RRULE:FREQ=WEEKLY;BYDAY=SU;BYHOUR=3;BYMINUTE=0"',
        'rrule = "RRULE:FREQ=WEEKLY;BYDAY=WE;BYHOUR=14;BYMINUTE=30"',
    )
    toml_path.write_text(body, encoding="utf-8")

    items = list_scheduled_execution_items()
    testing = next(
        (it for it in items if it["id"] == "codex:codex-dev-loop-testing"), None
    )
    assert testing is not None, "expected the drifted codex entry"
    actions = testing.get("actions", [])
    labels = {str(a.get("label", "")) for a in actions}
    assert "Adopt surface version" in labels
    assert "Push my version" in labels
    adopt = next(a for a in actions if a["label"] == "Adopt surface version")
    assert adopt["type"] == "mcp-tool"
    assert adopt["target"] == "routine-adopt-cloud"
    assert adopt["args"] == {"routine_id": "codex:codex-dev-loop-testing"}


def test_in_sync_entry_emits_no_conflict_actions(tmp_path, monkeypatch) -> None:
    from src.lib.runtime.codex_automations import sync_codex_automations
    from src.mcp.augur_framework.tools.infrastructure.browse.scheduled_executions import (
        list_scheduled_execution_items,
    )

    monkeypatch.setenv("HOME", str(tmp_path))
    schedules = [
        {
            "id": "codex-dev-loop-testing",
            "title": "Testing",
            "rrule": "RRULE:FREQ=WEEKLY;BYDAY=SU;BYHOUR=3;BYMINUTE=0",
            "prompt": "/dev-loops run testing",
            "workspace": str(tmp_path),
            "model": "gpt-5.4",
            "reasoning_effort": "high",
            "runs_in": "local",
        }
    ]
    sync_codex_automations(schedules, apply=True, prune=False)

    items = list_scheduled_execution_items()
    testing = next(
        (it for it in items if it["id"] == "codex:codex-dev-loop-testing"), None
    )
    assert testing is not None
    actions = testing.get("actions", [])
    labels = {str(a.get("label", "")) for a in actions}
    assert "Adopt surface version" not in labels
    assert "Push my version" not in labels
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
uv run pytest shared-vault/skills/daemon/augur/tests/test_scheduled_executions_actions.py -v
```

Expected: KeyError or empty `actions` field — not yet emitted.

- [ ] **Step 3: Emit Adopt/Push actions from list_scheduled_execution_items**

Edit `src/mcp/augur_framework/tools/infrastructure/browse/scheduled_executions.py`. Replace the entire `list_scheduled_execution_items` function body:

```python
def list_scheduled_execution_items(search: str | None = None) -> list[dict[str, Any]]:
    """Return normalized browse rows for scheduled executions."""

    items: list[dict[str, Any]] = []
    for record in list_scheduled_execution_records(search):
        row_id = record["id"]
        drift_status = record.get("drift_status", "unknown")
        source = record.get("source", "")
        actions: list[dict[str, Any]] = []
        if drift_status in ("codex-edited", "cloud-edited") and source in (
            "codex",
            "claude-remote",
        ):
            actions.append(
                {
                    "id": f"adopt-{row_id}",
                    "label": "Adopt surface version",
                    "type": "mcp-tool",
                    "target": "routine-adopt-cloud",
                    "args": {"routine_id": row_id},
                }
            )
            actions.append(
                {
                    "id": f"push-{row_id}",
                    "label": "Push my version",
                    "type": "mcp-tool",
                    "target": "routine-push-local",
                    "args": {"routine_id": row_id},
                }
            )
        items.append(
            {
                "id": row_id,
                "title": record["title"],
                "description": record.get("prompt_summary", ""),
                "hub": "system",
                "type": "scheduled-executions",
                "source_path": record.get("source_path", ""),
                "actions": actions,
                "metadata": {
                    "source": source,
                    "kind": record.get("kind", ""),
                    "status": record.get("status", "unknown"),
                    "schedule": record.get("schedule_human", ""),
                    "workspace": record.get("workspace", ""),
                    "model": record.get("model", ""),
                    "lastRun": record.get("last_run_at"),
                    "nextRun": record.get("next_run_at"),
                    "managed_by": record.get("managed_by", "unknown"),
                    "drift_status": drift_status,
                    "cacheFetchedAt": record.get("cache_fetched_at", ""),
                },
            }
        )
    return items
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
uv run pytest shared-vault/skills/daemon/augur/tests/test_scheduled_executions_actions.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Add the freshness row to routineSlots (dashboard)**

Edit `apps/dashboard/lib/browse/cardModel.ts`. Find the `routineSlots` function. After the existing `addRow(rows, "Drift", drift);` line, insert:

```typescript
  const cacheFetchedAt = value(metadata, "cacheFetchedAt");
  addRow(rows, "Cache", cacheFetchedAt ? `fetched ${cacheFetchedAt}` : undefined);
```

This is the only dashboard change needed — the Adopt/Push actions ride through `item.actions` and `buildBrowseCardModel` merges them into `overflowActions` automatically (per `cardModel.ts:595`). `executeBrowseAction` already dispatches `mcp-tool` actions (per `executeAction.ts:84`).

- [ ] **Step 6: Dashboard typecheck**

```bash
cd apps/dashboard && pnpm tsc --noEmit
```

Expected: no errors.

- [ ] **Step 7: Browser verify per rule 28**

Restart the dashboard MCP child so the new server-side fields surface:

```bash
ps -ef | grep "augur_framework.*dashboard" | grep -v grep | awk '{print $2}' | xargs -I {} kill {}
```

In Chrome via the claude-in-chrome MCP:

1. Open `http://localhost:3000/browse?view=background-routines` in list view, tall viewport (e.g. 1440x2400).
2. Screenshot. Verify each `claude-remote` card shows a `Cache: fetched <iso>` row.
3. Manually edit `~/.codex/automations/codex-dev-loop-testing/automation.toml` to mutate the cron (e.g. SU → WE).
4. Click "Refresh Codex routines" in the Manage menu.
5. Screenshot. Verify the Testing card shows the orange `codex-edited` drift badge AND its kebab (`...`) now has "Adopt surface version" and "Push my version" entries.
6. Click "Push my version". Verify success toast and that the TOML cron flips back to SU.
7. Click "Refresh Codex routines" again. Verify the badge returns to `in sync` and the kebab no longer shows Adopt/Push.

If all 7 steps pass, the UI is verified per rule 28.

- [ ] **Step 8: Commit**

```bash
git add src/mcp/augur_framework/tools/infrastructure/browse/scheduled_executions.py apps/dashboard/lib/browse/cardModel.ts shared-vault/skills/daemon/augur/tests/test_scheduled_executions_actions.py
git commit -m "feat(routines): emit Adopt/Push actions server-side + render cache freshness row"
```

---

## Task 9: End-to-end real-data verification (rule 34)

This task is a manual checklist with screenshot evidence. No code changes.

- [ ] **Step 1: Reset to a clean baseline**

```bash
# Force-restore all 3 codex automations to seed-matching state
uv run python -c "
from src.lib.runtime.codex_automations import sync_codex_automations, load_codex_schedule_seeds
from pathlib import Path
seeds = []
for p in ['shared-vault/skills/routine-codebase/assets/seeds/routine-schedule.yaml',
          'shared-vault/skills/platform-admin/assets/seeds/routine-schedule.yaml']:
    seeds.extend(load_codex_schedule_seeds([Path(p)]))
sync_codex_automations(seeds, apply=True, prune=False, force=True)
print('reset done; installed:', len(seeds))
"
scripts/augur routine drift --source codex 2>&1 | grep counts_by_drift_status
```

Expected: `'in-sync': 3` for Codex side.

- [ ] **Step 2: Manually drift one routine**

```bash
sed -i.bak 's|RRULE:FREQ=WEEKLY;BYDAY=SU;BYHOUR=3;BYMINUTE=0|RRULE:FREQ=WEEKLY;BYDAY=TH;BYHOUR=9;BYMINUTE=0|' ~/.codex/automations/codex-dev-loop-testing/automation.toml
scripts/augur routine drift --source codex 2>&1 | grep counts_by_drift_status
```

Expected: `'codex-edited': 1, 'in-sync': 2`.

- [ ] **Step 3: Adopt via CLI**

```bash
scripts/augur routine adopt codex:codex-dev-loop-testing 2>&1 | tail -10
```

Expected: success message, seed_path printed, applied_fields show the new rrule.

- [ ] **Step 4: Verify the seed file changed**

```bash
grep -A 1 "id: codex-dev-loop-testing" shared-vault/skills/routine-codebase/assets/seeds/routine-schedule.yaml | head -5
```

Expected: the seed now contains the adopted RRULE (`BYDAY=TH;BYHOUR=9`).

- [ ] **Step 5: Re-run sync and confirm in-sync**

```bash
PYTHONPATH=shared-vault uv run python -m skills.ai.scripts.sync_agents sync agents codex 2>&1 | grep -E "skip|Synced.*Codex"
scripts/augur routine drift --source codex 2>&1 | grep counts_by_drift_status
```

Expected: no skip warnings, `'in-sync': 3`.

- [ ] **Step 6: Revert the seed for hygiene** (the adopted RRULE was a synthetic test value)

```bash
git checkout -- shared-vault/skills/routine-codebase/assets/seeds/routine-schedule.yaml
uv run python -c "
from src.lib.runtime.codex_automations import sync_codex_automations, load_codex_schedule_seeds
from pathlib import Path
seeds = load_codex_schedule_seeds([Path('shared-vault/skills/routine-codebase/assets/seeds/routine-schedule.yaml')])
sync_codex_automations(seeds, apply=True, prune=False, force=True)
"
scripts/augur routine drift --source codex 2>&1 | grep counts_by_drift_status
```

Expected: `'in-sync': 3` against the original seed values.

- [ ] **Step 7: Manual Push verification**

```bash
sed -i.bak2 's|RRULE:FREQ=WEEKLY;BYDAY=SU;BYHOUR=3;BYMINUTE=0|RRULE:FREQ=WEEKLY;BYDAY=FR;BYHOUR=10;BYMINUTE=0|' ~/.codex/automations/codex-dev-loop-testing/automation.toml
scripts/augur routine push codex:codex-dev-loop-testing 2>&1 | tail -5
grep rrule ~/.codex/automations/codex-dev-loop-testing/automation.toml
```

Expected: push reports success; rrule restored to the seed value `BYDAY=SU;BYHOUR=3;BYMINUTE=0`.

- [ ] **Step 8: Dashboard browser verification with screenshot**

Per CLAUDE.md rule 28: take a real screenshot (chrome MCP or local browser), tall viewport.

1. Open `http://localhost:3000/browse?view=background-routines`.
2. Switch to list view.
3. Confirm Code Quality / Duplication / Testing all show `augur` + `in sync` badges (after Step 7's push).
4. Confirm Augur Dream / Augur Skill Quality / Augur UI Quality show a `Cache: fetched <iso>` row.
5. Drift Testing again via `sed` and click "Refresh Codex routines" in the Manage menu.
6. Confirm the Testing card flips to orange `codex-edited` and its `...` menu shows "Adopt surface version" and "Push my version".
7. Click "Push my version", confirm toast and that the card returns to `in sync`.

- [ ] **Step 9: Final cleanup**

```bash
rm -f ~/.codex/automations/codex-dev-loop-testing/automation.toml.bak ~/.codex/automations/codex-dev-loop-testing/automation.toml.bak2
git status
```

Expected: 0 unintended modified files outside the planned source edits.

- [ ] **Step 10: Mark ADR-763 status Accepted**

```bash
sed -i.bak 's|^status: Proposed|status: Accepted|' docs/adrs/ADR-763-bidirectional-routine-drift.md
rm docs/adrs/ADR-763-bidirectional-routine-drift.md.bak
git add docs/adrs/ADR-763-bidirectional-routine-drift.md
git commit -m "chore(adr): mark ADR-763 Accepted after Phase D verification"
```

---

## Self-review checklist (run before handoff)

- [ ] Every step has either code, a command, or a clear human action — no "TBD" / "later".
- [ ] All file paths exist or are explicitly under `Create:`.
- [ ] Method/function names are consistent across tasks (`adopt_cloud_impl`, `push_local_impl`, `update_seed_entry`).
- [ ] Every server-side new symbol has at least one unit test.
- [ ] Dashboard task has a real-browser verification step, not just typecheck.
- [ ] Spec coverage: every "Phase D" item in the spec has a task — Adopt impl (Task 2, 5), Push impl (Tasks 3, 4, 5), MCP tools (Task 5), CLI verbs (Task 6), freshness label (Task 7), kebab actions (Task 8), real-data verify (Task 9). Done.
