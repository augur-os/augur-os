import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


def _load_run_inspection_module():
    module_name = "test_run_inspection_module"
    module_path = Path(__file__).resolve().parents[2] / "scripts" / "adaptive" / "run_inspection.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _write_skill(
    repo_root: Path,
    bundle: str,
    skill: str,
    action_id: str,
    *,
    asset_prompt: bool = False,
) -> Path:
    skill_dir = repo_root / "project-brain" / "capabilities" / "skills" / skill
    dashboard_dir = skill_dir / "augur" / "dashboard"
    dashboard_dir.mkdir(parents=True, exist_ok=True)
    (dashboard_dir / "ActionCard.tsx").write_text(
        f"export function ActionCard() {{ return runAction({{ id: '{action_id}' }}); }}\n"
    )
    if asset_prompt:
        prompts_dir = skill_dir / "assets" / "prompts"
        prompts_dir.mkdir(parents=True, exist_ok=True)
        (prompts_dir / f"{action_id}.md").write_text("# prompt\n")
    return skill_dir


@pytest.fixture(autouse=True)
def reset_skill_cache():
    from src.config import paths

    paths._skill_to_bundle_cache = None
    yield
    paths._skill_to_bundle_cache = None


def test_count_contextless_actions_uses_vault_prompts(monkeypatch, tmp_path):
    repo_root = tmp_path / "repo"
    vault_root = tmp_path / "vault"
    monkeypatch.setenv("AUGUR_ROOT", str(repo_root))
    monkeypatch.setenv("AUGUR_VAULT", str(vault_root))
    module = _load_run_inspection_module()
    _write_skill(repo_root, "observability", "demo", "sync-notes")

    prompts_dir = vault_root / "observability" / "demo" / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    (prompts_dir / "sync-notes.md").write_text("# prompt\n")
    monkeypatch.setattr(module, "get_skill_data_dir", lambda _skill: vault_root / "observability" / "demo")
    monkeypatch.setattr(
        module,
        "get_skill_assets_dir",
        lambda _skill: repo_root / "project-brain" / "capabilities" / "skills" / "demo" / "assets",
    )

    assert module._count_contextless_actions(repo_root) == 0


def test_count_contextless_actions_falls_back_to_assets(monkeypatch, tmp_path):
    repo_root = tmp_path / "repo"
    vault_root = tmp_path / "vault"
    monkeypatch.setenv("AUGUR_ROOT", str(repo_root))
    monkeypatch.setenv("AUGUR_VAULT", str(vault_root))
    module = _load_run_inspection_module()
    _write_skill(repo_root, "observability", "demo", "sync-notes", asset_prompt=True)
    monkeypatch.setattr(module, "get_skill_data_dir", lambda _skill: vault_root / "observability" / "demo")
    monkeypatch.setattr(
        module,
        "get_skill_assets_dir",
        lambda _skill: repo_root / "project-brain" / "capabilities" / "skills" / "demo" / "assets",
    )

    assert module._count_contextless_actions(repo_root) == 0


def test_count_contextless_actions_reports_missing_prompt(monkeypatch, tmp_path):
    repo_root = tmp_path / "repo"
    vault_root = tmp_path / "vault"
    monkeypatch.setenv("AUGUR_ROOT", str(repo_root))
    monkeypatch.setenv("AUGUR_VAULT", str(vault_root))
    module = _load_run_inspection_module()
    _write_skill(repo_root, "observability", "demo", "sync-notes")
    monkeypatch.setattr(module, "get_skill_data_dir", lambda _skill: vault_root / "observability" / "demo")
    monkeypatch.setattr(
        module,
        "get_skill_assets_dir",
        lambda _skill: repo_root / "project-brain" / "capabilities" / "skills" / "demo" / "assets",
    )

    assert module._count_contextless_actions(repo_root) == 1


def _category(**overrides):
    data = {
        "name": "demo-category",
        "issue_count": 1,
        "outcome": "report-only",
        "action_summary": "summary",
        "actionable_count": 0,
        "scanner_defect_count": 0,
        "broken_count": 0,
        "manual_count": 0,
        "environment_count": 0,
        "maintenance_count": 0,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_generate_evolve_analysis_excludes_manual_only_categories_from_upgrade_advice(tmp_path):
    module = _load_run_inspection_module()
    inspection = module.RunInspection()
    report = SimpleNamespace(
        loop_name="knowledge-enrichment",
        categories=[
            _category(
                name="auto-adr-lifecycle",
                issue_count=7,
                manual_count=7,
                action_summary="Report generated with 7 orphan plans",
            ),
        ],
    )

    analysis = module.generate_evolve_analysis(inspection, [report], tmp_path)

    assert "Manual follow-up by design" in analysis
    assert "auto-adr-lifecycle" in analysis
    assert "These are user or ADR decisions" in analysis
    assert "Upgrade fix() from report-only to actual code changes" not in analysis


def test_generate_evolve_analysis_excludes_environment_only_categories_from_upgrade_advice(tmp_path):
    module = _load_run_inspection_module()
    inspection = module.RunInspection()
    report = SimpleNamespace(
        loop_name="testing",
        categories=[
            _category(
                name="auto-test-webmcp",
                issue_count=1,
                environment_count=1,
                action_summary="1 environment issue(s) (not actionable)",
            ),
        ],
    )

    analysis = module.generate_evolve_analysis(inspection, [report], tmp_path)

    assert "Environment-gated" in analysis
    assert "auto-test-webmcp" in analysis
    assert "require environment repair or setup" in analysis
    assert "Upgrade fix() from report-only to actual code changes" not in analysis


def test_generate_evolve_analysis_excludes_maintenance_only_categories_from_upgrade_advice(tmp_path):
    module = _load_run_inspection_module()
    inspection = module.RunInspection()
    report = SimpleNamespace(
        loop_name="knowledge-enrichment",
        categories=[
            _category(
                name="reindex-rag",
                issue_count=216,
                maintenance_count=216,
                action_summary="Unified reindex complete: 6952 entries across 16 categories",
            ),
        ],
    )

    analysis = module.generate_evolve_analysis(inspection, [report], tmp_path)

    assert "Maintenance / evolution output" in analysis
    assert "reindex-rag" in analysis
    assert "no fix() upgrade is required" in analysis
    assert "Prioritized improvements" not in analysis


def test_generate_evolve_analysis_calls_out_design_gated_blockers(tmp_path):
    module = _load_run_inspection_module()
    inspection = module.RunInspection()
    report = SimpleNamespace(
        loop_name="observability",
        categories=[
            _category(
                name="ownership-shift",
                outcome="blocked-needs-design",
                issue_count=2,
                actionable_count=2,
                action_summary="Design gate written before ownership can move",
            ),
        ],
    )

    analysis = module.generate_evolve_analysis(inspection, [report], tmp_path)

    assert "Structural findings blocked until a design gate exists" in analysis
    assert "ownership-shift" in analysis
    assert "governing ADR/runtime design note" in analysis


def test_generate_evolve_analysis_surfaces_design_written_follow_up(tmp_path):
    module = _load_run_inspection_module()
    inspection = module.RunInspection()
    report = SimpleNamespace(
        loop_name="observability",
        categories=[
            _category(
                name="ownership-shift",
                outcome="design-written",
                issue_count=2,
                actionable_count=2,
                action_summary="Design gate written at project-brain/decisions/adrs/ADR-999.md",
            ),
        ],
    )

    analysis = module.generate_evolve_analysis(inspection, [report], tmp_path)

    assert "Structural findings that produced a design gate artifact" in analysis
    assert "ownership-shift" in analysis
    assert "rerun the loop at higher difficulty" in analysis


def test_inspect_run_counts_design_gated_fixes_as_real_fixes(tmp_path, monkeypatch):
    module = _load_run_inspection_module()
    monkeypatch.setattr(module.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=""))

    report = SimpleNamespace(
        loop_name="skill-quality",
        categories=[
            _category(
                name="cross-skill-boundary",
                outcome="design-gated-fixed",
                issue_count=1,
            ),
        ],
    )

    inspection = module.inspect_run(tmp_path, "2026-04-12T00:00:00+00:00", [report])

    assert inspection.categories_that_fixed == 1
