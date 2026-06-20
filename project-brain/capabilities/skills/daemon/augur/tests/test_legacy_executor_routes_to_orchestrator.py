"""ADR-755 routing tests for the legacy adaptive-loop executor."""
from __future__ import annotations

import sys
from pathlib import Path

from src.lib.ops_protocol import ScanResult


TESTS_DIR = Path(__file__).resolve().parent
DAEMON_DIR = TESTS_DIR.parents[1]
DAEMON_SCRIPTS_DIR = DAEMON_DIR / "scripts"

if str(DAEMON_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(DAEMON_SCRIPTS_DIR))

import adaptive.engine_entry_runner as entry_runner  # noqa: E402
from adaptive.discovery import AutoCommandEntry  # noqa: E402
from adaptive.loops.base_loop import LoopResult  # noqa: E402
from adaptive.reporting import CategoryReport  # noqa: E402
import adaptive_loop_executor  # noqa: E402
from routine_orchestrator import orchestrator  # noqa: E402


class _ScanModule:
    def __init__(self, name: str) -> None:
        self.name = name

    def scan(self, _ctx) -> ScanResult:
        return ScanResult(
            issues=[
                {
                    "kind": "actionable",
                    "finding_band": "mechanical",
                    "detail": f"{self.name} needs a fix",
                }
            ],
            summary="1 issue",
        )

    def fix(self, _ctx, _issues):  # pragma: no cover - patched routing should intercept.
        raise AssertionError("test patches the fix boundary")


def _write_command_doc(skill_dir: Path, command_name: str, *, runner: str | None = None) -> None:
    command_dir = skill_dir / "commands"
    command_dir.mkdir(parents=True)
    if runner is None:
        content = f"# {command_name}\n"
    else:
        content = f"---\nx-augur-runner: {runner}\n---\n# {command_name}\n"
    (command_dir / f"{command_name}.md").write_text(content, encoding="utf-8")


def test_marked_command_routes_fix_phase_to_orchestrator(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "repo"
    project_root.mkdir()
    (project_root / "project.yaml").write_text("name: route-fixture\n", encoding="utf-8")
    runtime_dir = tmp_path / "runtime"

    orchestrator_skill = project_root / "project-brain" / "capabilities" / "skills" / "route-orchestrator"
    legacy_skill = project_root / "project-brain" / "capabilities" / "skills" / "route-legacy"
    _write_command_doc(orchestrator_skill, "auto-orch", runner="orchestrator")
    _write_command_doc(legacy_skill, "auto-legacy")

    config = {
        "engine": {"enabled": True, "verify_command": ""},
        "loops": {
            "route-test": {
                "enabled": True,
                "trigger": "manual",
                "budget": 4,
                "budget_growth_rate": 1,
                "categories": {
                    "auto-orch": {"enabled": True, "trust": 0.5, "tier": 0},
                    "auto-legacy": {"enabled": True, "trust": 0.5, "tier": 1},
                },
            }
        },
    }
    registry = {
        "auto-orch": AutoCommandEntry(
            name="auto-orch",
            module=_ScanModule("auto-orch"),
            loop_name="route-test",
            tier=0,
            plugin_root=orchestrator_skill,
        ),
        "auto-legacy": AutoCommandEntry(
            name="auto-legacy",
            module=_ScanModule("auto-legacy"),
            loop_name="route-test",
            tier=1,
            plugin_root=legacy_skill,
        ),
    }

    legacy_calls: list[str] = []
    orchestrator_calls: list[str] = []

    def fake_legacy_fix_phase(**kwargs):
        entry = kwargs["entry"]
        legacy_calls.append(entry.name)
        kwargs["results"].append(
            LoopResult(success=True, action="fix", category=entry.name)
        )
        kwargs["cat_reports"].append(
            CategoryReport(
                name=entry.name,
                trust_before=kwargs["trust_before"],
                trust_after=kwargs["trust_before"],
                difficulty_before=kwargs["diff_before"],
                difficulty_after=kwargs["diff_before"],
                status="ok",
                outcome="auto-fixed",
                issue_count=len(kwargs["issues"]),
            )
        )
        return True

    def fake_orchestrator_fix_one_command(loop_name, *, command, findings, **_kwargs):
        orchestrator_calls.append(command.name)
        assert loop_name == "route-test"
        assert [finding["auto_command"] for finding in findings] == ["auto-orch"]
        return orchestrator.OrchestrateResult(
            loop_name=loop_name,
            findings=list(findings),
        )

    monkeypatch.setattr(adaptive_loop_executor, "load_config", lambda: config)
    monkeypatch.setattr(adaptive_loop_executor, "get_runtime_dir", lambda: runtime_dir)
    monkeypatch.setattr(
        adaptive_loop_executor,
        "_resolve_execution_project_root",
        lambda _args, cwd=None: project_root,
    )
    monkeypatch.setattr(
        adaptive_loop_executor,
        "discover_auto_commands",
        lambda _project_root: registry,
    )
    monkeypatch.setattr(entry_runner, "run_fix_phase", fake_legacy_fix_phase)
    monkeypatch.setattr(orchestrator, "fix_one_command", fake_orchestrator_fix_one_command)

    adaptive_loop_executor.main(["run", "route-test"])

    assert orchestrator_calls == ["auto-orch"]
    assert legacy_calls == ["auto-legacy"]
