"""Focused tests for the adaptive engine context collector."""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from skills.daemon.scripts.adaptive.engine_context import collect_context


def test_collect_context_skips_wiki_and_adr_for_mechanical_issue(tmp_path: Path, monkeypatch) -> None:
    """Mechanical issues should return immediately without touching context paths."""

    def _fail(*_args, **_kwargs):
        raise AssertionError("context helpers should not be called for mechanical issues")

    monkeypatch.setattr(
        "skills.daemon.scripts.adaptive.engine_context.get_adr_dir",
        _fail,
    )
    monkeypatch.setattr(
        "skills.daemon.scripts.adaptive.engine_context.get_compiled_wiki_dir",
        _fail,
    )

    issue = {"path": "apps/dashboard/page.tsx", "tool_name_mismatch": True}

    context = collect_context(issue=issue, project_root=tmp_path, loop_name="testing")

    assert context["finding_band"] == "mechanical"
    assert context["sources"] == []


def test_collect_context_follows_priority_order_for_structural_issue(tmp_path: Path) -> None:
    """Structural issues should gather local, loop, ADR/wiki, then runtime context."""

    target_dir = tmp_path / "src" / "scheduler"
    target_dir.mkdir(parents=True)
    (target_dir / "ownership.py").write_text(
        "def reassign_scheduler():\n    return 'codex owns schedules'\n",
        encoding="utf-8",
    )
    (target_dir / "README.md").write_text(
        "---\ntitle: Scheduler Notes\n---\nOwnership boundaries live here.\n",
        encoding="utf-8",
    )

    loop_ref_dir = tmp_path / "project-brain" / "capabilities" / "skills" / "daemon" / "references"
    loop_ref_dir.mkdir(parents=True)
    (loop_ref_dir / "routines-implementation.md").write_text(
        "---\ntitle: Dev Loops\n---\nObservability and ownership guidance.\n",
        encoding="utf-8",
    )
    commands_dir = tmp_path / "project-brain" / "capabilities" / "skills" / "daemon" / "commands"
    commands_dir.mkdir(parents=True)
    (commands_dir / "dev-loops.md").write_text(
        "---\ntitle: Dev Loops Command\n---\nRun the loops.\n",
        encoding="utf-8",
    )

    adr_dir = tmp_path / "docs" / "adrs"
    adr_dir.mkdir(parents=True)
    (adr_dir / "ADR-999-test.md").write_text(
        "---\nstatus: proposed\ntitle: Ownership change\n---\nCodex owns execution boundaries.\n",
        encoding="utf-8",
    )

    wiki_dir = tmp_path / "wiki"
    wiki_dir.mkdir(parents=True)
    (wiki_dir / "dev-boundaries.md").write_text(
        "---\ntitle: Boundaries\n---\nUse wiki context when ownership is ambiguous.\n",
        encoding="utf-8",
    )

    runtime_dir = tmp_path / "runtime" / "adaptive"
    (runtime_dir / "reports").mkdir(parents=True)
    (runtime_dir / "reports" / "observability-latest.json").write_text(
        '{"summary": "ownership review", "next_actions": ["verify scheduler owner"]}',
        encoding="utf-8",
    )

    issue = {
        "path": "src/scheduler/ownership.py",
        "ownership_change": True,
        "design_ambiguous": True,
        "detail": "Move scheduler ownership to codex",
    }
    context = collect_context(
        issue=issue,
        project_root=tmp_path,
        loop_name="observability",
        adr_dir=adr_dir,
        wiki_dir=wiki_dir,
        runtime_dir=runtime_dir,
    )

    assert context["finding_band"] == "structural"
    assert [item["kind"] for item in context["sources"]] == [
        "local-code",
        "local-doc",
        "loop-reference",
        "adr",
        "wiki",
        "recent-report",
        "recent-ledger",
    ]


def test_collect_context_keeps_local_semantic_issues_local(tmp_path: Path) -> None:
    """Local semantic issues should stop at nearby code/docs."""

    target_dir = tmp_path / "src" / "reporting"
    target_dir.mkdir(parents=True)
    (target_dir / "formatter.py").write_text("def format_summary():\n    return 'ok'\n", encoding="utf-8")
    (target_dir / "README.md").write_text(
        "---\ntitle: Reporting Notes\n---\nLocal reporting guidance.\n",
        encoding="utf-8",
    )
    loop_ref_dir = tmp_path / "project-brain" / "capabilities" / "skills" / "daemon" / "references"
    loop_ref_dir.mkdir(parents=True)
    (loop_ref_dir / "routines-implementation.md").write_text(
        "---\ntitle: Dev Loops\n---\nReporting loop guidance.\n",
        encoding="utf-8",
    )

    issue = {
        "path": "src/reporting/formatter.py",
        "detail": "Reporting summary does not match expected intent",
        "design_ambiguous": True,
    }
    context = collect_context(issue=issue, project_root=tmp_path, loop_name="reporting")

    assert context["finding_band"] == "local-semantic"
    assert [item["kind"] for item in context["sources"]] == ["local-code", "local-doc", "loop-reference"]
