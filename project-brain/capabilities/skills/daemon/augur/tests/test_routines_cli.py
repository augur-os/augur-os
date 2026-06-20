"""Tests for the ADR-758 unified routines CLI surface."""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import yaml
from src.config import paths as config_paths


TESTS_DIR = Path(__file__).resolve().parent
DAEMON_DIR = TESTS_DIR.parents[1]
PROJECT_ROOT = next(
    (
        p
        for p in Path(__file__).resolve().parents
        if (p / "pyproject.toml").exists() and (p / ".git").exists()
    ),
    Path(__file__).resolve().parents[-1],
)
SCRIPTS_DIR = DAEMON_DIR / "scripts"
MCP_INIT = SCRIPTS_DIR / "mcp" / "__init__.py"
REGISTRY_PATH = SCRIPTS_DIR / "routine_orchestrator" / "registry.py"


def _load_mcp_module():
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))
    module_name = "daemon_mcp_routines_cli_tests"
    spec = importlib.util.spec_from_file_location(module_name, MCP_INIT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _load_registry_module():
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))
    module_name = "routine_registry_cli_tests"
    spec = importlib.util.spec_from_file_location(module_name, REGISTRY_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _parser_for(module):
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="cmd")
    module.register_subcommands(subparsers)
    return parser


def _routine(**overrides):
    values = {
        "id": "testing",
        "execution": "tiered",
        "policy": "adaptive",
        "skill_name": "routine-codebase",
        "skill_root": Path("/repo/project-brain/capabilities/skills/routine-codebase"),
        "callable": "scripts/routine_orchestrator/orchestrator.py",
        "callable_path": Path("/repo/project-brain/capabilities/skills/routine-codebase/scripts/routine_orchestrator/orchestrator.py"),
        "loop": "testing",
        "hub": "dev",
        "description": "Run tests.",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_aug_routine_unified_verbs_parse() -> None:
    module = _load_mcp_module()
    parser = _parser_for(module)

    assert parser.parse_args(["routine", "list"]).routine_verb == "list"
    status_args = parser.parse_args(["routine", "status", "testing", "--limit", "3"])
    assert status_args.routine_verb == "status"
    assert status_args.routine_id == "testing"
    assert status_args.limit == 3
    run_args = parser.parse_args(["routine", "run", "dream"])
    assert run_args.routine_verb == "run"
    assert run_args.routine_id == "dream"
    assert parser.parse_args(["routine", "report", "dream"]).routine_verb == "report"
    assert parser.parse_args(["routine", "schedule", "testing"]).routine_verb == "schedule"


def test_aug_routine_list_returns_registered_routines(monkeypatch, capsys) -> None:
    module = _load_mcp_module()
    routines = [
        _routine(id="dream", execution="inline-session", policy="oneshot", skill_name="dream", loop=None),
        _routine(id="testing"),
    ]
    monkeypatch.setattr(
        module,
        "_load_routine_registry",
        lambda: SimpleNamespace(list_routines=lambda: routines),
    )

    parser = _parser_for(module)
    args = parser.parse_args(["routine", "list"])
    assert args.func(args, []) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["success"] is True
    assert [routine["id"] for routine in payload["routines"]] == ["dream", "testing"]
    assert payload["routines"][0]["execution"] == "inline-session"


def test_aug_routine_run_delegates_to_registry_dispatch(monkeypatch, capsys) -> None:
    module = _load_mcp_module()
    calls: list[tuple[str, dict]] = []

    def dispatch(routine_id: str, **kwargs):
        calls.append((routine_id, kwargs))
        return {"routine_id": routine_id, "render_prompt": "Dream prompt"}

    monkeypatch.setattr(
        module,
        "_load_routine_registry",
        lambda: SimpleNamespace(
            get_routine=lambda routine_id: _routine(
                id=routine_id,
                execution="inline-session",
                policy="oneshot",
                skill_name="dream",
                loop=None,
            ),
            dispatch=dispatch,
        ),
    )

    parser = _parser_for(module)
    args = parser.parse_args(["routine", "run", "dream"])
    assert args.func(args, []) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["routine_id"] == "dream"
    assert payload["render_prompt"] == "Dream prompt"
    assert calls == [("dream", {})]


def test_aug_routine_run_wraps_tiered_results_as_json(monkeypatch, capsys) -> None:
    module = _load_mcp_module()

    class Result:
        loop_name = "duplication"
        counts = {"findings": 0}
        findings = []
        mechanical_applied = []
        mechanical_failed = []
        deferred = []
        design_gate_findings = []
        dispatched = []
        enqueued = []
        events = [{"phase": "complete"}]

    monkeypatch.setattr(
        module,
        "_load_routine_registry",
        lambda: SimpleNamespace(
            get_routine=lambda routine_id: _routine(id=routine_id, loop="duplication"),
            dispatch=lambda routine_id, **kwargs: Result(),
        ),
    )
    monkeypatch.setattr(module, "_detect_routine_session", lambda: object())
    monkeypatch.setattr(module, "_routine_session_surface", lambda session: "codex")

    parser = _parser_for(module)
    args = parser.parse_args(["routine", "run", "duplication"])
    assert args.func(args, []) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["loop_name"] == "duplication"
    assert payload["counts"]["findings"] == 0
    assert payload["events"] == [{"phase": "complete"}]


def test_aug_routine_status_uses_unified_status_view(monkeypatch, capsys) -> None:
    module = _load_mcp_module()
    status_calls: list[dict] = []

    def routine_status_payload(**kwargs):
        status_calls.append(kwargs)
        return {
            "success": True,
            "routines": [
                {
                    "id": "testing",
                    "last_run": {
                        "loop": "testing",
                        "action": "run",
                        "category": "engine",
                        "result": "success",
                        "timestamp": "2026-05-16T10:00:00+00:00",
                    },
                }
            ],
        }

    monkeypatch.setattr(
        module,
        "_load_routine_status_view",
        lambda: SimpleNamespace(routine_status_payload=routine_status_payload),
    )

    parser = _parser_for(module)
    args = parser.parse_args(["routine", "status", "testing", "--limit", "1"])
    assert args.func(args, []) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["success"] is True
    assert payload["routines"][0]["id"] == "testing"
    assert payload["routines"][0]["last_run"]["result"] == "success"
    assert status_calls == [{"routine_id": "testing", "limit": 1}]


def test_aug_routine_report_includes_runtime_reports_when_documents_dir_is_empty(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    module = _load_mcp_module()
    docs_dir = tmp_path / "docs-home"
    runtime_dir = tmp_path / "runtime"
    runtime_reports = runtime_dir / "reports"
    runtime_reports.mkdir(parents=True)
    runtime_report = runtime_reports / "duplication-latest.json"
    runtime_report.write_text('{"fixed_groups": 0, "remaining_groups": 0}', encoding="utf-8")

    monkeypatch.setattr(config_paths, "get_documents_dir", lambda: docs_dir)
    monkeypatch.setattr(config_paths, "get_runtime_dir", lambda: runtime_dir)
    monkeypatch.setattr(
        module,
        "_load_routine_registry",
        lambda: SimpleNamespace(get_routine=lambda routine_id: _routine(id=routine_id, loop="duplication")),
    )

    parser = _parser_for(module)
    args = parser.parse_args(["routine", "report", "duplication"])
    assert args.func(args, []) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["count"] == 1
    assert payload["reports"][0]["path"] == str(runtime_report)


def test_registry_dispatch_tiered_delegates_to_orchestrator(monkeypatch, tmp_path: Path) -> None:
    registry = _load_registry_module()
    skill = tmp_path / "routine-codebase"
    skill.mkdir()
    (skill / "SKILL.md").write_text(
        """---
name: routine-codebase
x-augur-routine:
  id: testing
  execution: tiered
  policy: adaptive
  callable: scripts/routine_orchestrator/orchestrator.py
  loop: testing
---
""",
        encoding="utf-8",
    )
    calls: list[tuple[str, dict]] = []

    def orchestrate(routine, kwargs):
        calls.append((routine.loop, kwargs))
        return {"loop_name": routine.loop, "ok": True}

    monkeypatch.setattr(registry, "_orchestrate_tiered_routine", orchestrate)

    result = registry.dispatch("testing", skills_root=tmp_path, session="codex-session")

    assert result == {"loop_name": "testing", "ok": True}
    assert calls == [("testing", {"session": "codex-session"})]


def test_registry_dispatch_inline_session_renders_prompt(tmp_path: Path) -> None:
    registry = _load_registry_module()
    skill = tmp_path / "dream"
    commands = skill / "commands"
    commands.mkdir(parents=True)
    (commands / "dream.md").write_text("# Dream\n\nRun the dream cycle.\n", encoding="utf-8")
    (skill / "SKILL.md").write_text(
        """---
name: dream
x-augur-routine:
  id: dream
  execution: inline-session
  policy: oneshot
  callable: commands/dream.md
---
""",
        encoding="utf-8",
    )

    result = registry.dispatch("dream", skills_root=tmp_path)

    assert result["routine_id"] == "dream"
    assert result["execution"] == "inline-session"
    assert result["render_prompt"].startswith("# Dream")


def test_capability_policy_exports_routines_and_deprecates_aliases() -> None:
    policy_path = PROJECT_ROOT / "config" / "system" / "capability_exposure.yaml"
    policy = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
    capabilities = policy["capabilities"]

    routines = capabilities["command:routines"]
    assert routines["classification_status"] == "approved"
    assert {"cli", "agents-md", "browse", "claude", "codex"}.issubset(
        set(routines["export_to"])
    )

    # /dev-loops was fully removed in the consolidation; /dream is retained as a
    # deprecated alias that routes to /routines (design line 115).
    for command_id in ("command:dream",):
        capability = capabilities[command_id]
        assert capability["classification_status"] == "approved"
        assert capability["status"] == "deprecated"
        assert capability["replacement"] == "command:routines"
        assert capability["deprecation_release"] == "adr-758-transition"
