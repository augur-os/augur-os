from pathlib import Path

import pytest

from skills.daemon.scripts.ops import flow_optimizer, stale_actions
from src.lib.ops_protocol import OpsContext


def _write_skill(repo_root: Path, skill_name: str, *, hub: str = "observability") -> Path:
    skill_dir = repo_root / "project-brain" / "capabilities" / "skills" / skill_name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {skill_name}\ndescription: Test skill\nx-augur-hub: {hub}\n---\n"
    )
    return skill_dir


def _write_action(path: Path, *, action_id: str, description: str = "", dispatch: str = "fire", page: str | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"id: {action_id}", f"dispatch: {dispatch}"]
    if description:
        lines.append(f"description: {description}")
    if page is not None:
        lines.append(f"page: {page}")
    path.write_text("\n".join(lines) + "\n")


@pytest.fixture(autouse=True)
def reset_skill_cache():
    from src.config import paths

    paths._skill_to_bundle_cache = None
    yield
    paths._skill_to_bundle_cache = None


def test_flow_optimizer_uses_asset_action_fallback(monkeypatch, tmp_path):
    repo_root = tmp_path / "repo"
    vault_root = tmp_path / "vault"
    skill_dir = _write_skill(repo_root, "demo")
    _write_action(
        skill_dir / "assets" / "actions" / "summarize.yaml",
        action_id="summarize",
        dispatch="fire",
        description="Analyze recent errors and summarize trends",
    )

    monkeypatch.setenv("AUGUR_ROOT", str(repo_root))
    monkeypatch.setenv("AUGUR_VAULT", str(vault_root))

    result = flow_optimizer.scan(OpsContext(project_root=repo_root))

    assert [issue["action_id"] for issue in result.issues] == ["summarize"]


def test_flow_optimizer_prefers_vault_override(monkeypatch, tmp_path):
    repo_root = tmp_path / "repo"
    vault_root = tmp_path / "vault"
    skill_dir = _write_skill(repo_root, "demo")
    _write_action(
        skill_dir / "assets" / "actions" / "status.yaml",
        action_id="status",
        dispatch="fire",
        description="List current jobs",
    )
    vault_action = vault_root / "observability" / "demo" / "actions" / "status.yaml"
    _write_action(
        vault_action,
        action_id="status",
        dispatch="fire",
        description="Generate an AI summary of recent jobs",
    )

    monkeypatch.setenv("AUGUR_ROOT", str(repo_root))
    monkeypatch.setenv("AUGUR_VAULT", str(vault_root))

    result = flow_optimizer.scan(OpsContext(project_root=repo_root))

    assert len(result.issues) == 1
    assert result.issues[0]["file"] == str(vault_action)


def test_stale_actions_scans_asset_action_fallback(monkeypatch, tmp_path):
    repo_root = tmp_path / "repo"
    vault_root = tmp_path / "vault"
    skill_dir = _write_skill(repo_root, "demo")
    _write_action(
        skill_dir / "assets" / "actions" / "notes.yaml",
        action_id="notes",
        page="notes",
    )

    route_file = repo_root / "apps" / "dashboard" / "app" / "observability" / "notes" / "page.tsx"
    route_file.parent.mkdir(parents=True, exist_ok=True)
    route_file.write_text("export default function Page() { return null; }\n")

    monkeypatch.setenv("AUGUR_ROOT", str(repo_root))
    monkeypatch.setenv("AUGUR_VAULT", str(vault_root))

    result = stale_actions.scan(OpsContext(project_root=repo_root))

    assert len(result.issues) == 1
    assert result.issues[0]["correct_page"] == "/observability/notes"


def test_stale_actions_uses_shared_snapshot_routes(monkeypatch, tmp_path):
    repo_root = tmp_path / "repo"
    vault_root = tmp_path / "vault"
    skill_dir = _write_skill(repo_root, "demo")
    _write_action(
        skill_dir / "assets" / "actions" / "notes.yaml",
        action_id="notes",
        page="notes",
    )

    monkeypatch.setenv("AUGUR_ROOT", str(repo_root))
    monkeypatch.setenv("AUGUR_VAULT", str(vault_root))

    result = stale_actions.scan(
        OpsContext(
            project_root=repo_root,
            shared_snapshot={"page_routes": ["/observability/notes"]},
        )
    )

    assert len(result.issues) == 1
    assert result.issues[0]["correct_page"] == "/observability/notes"


def test_stale_actions_fix_updates_vault_override(monkeypatch, tmp_path):
    repo_root = tmp_path / "repo"
    vault_root = tmp_path / "vault"
    skill_dir = _write_skill(repo_root, "demo")
    asset_action = skill_dir / "assets" / "actions" / "notes.yaml"
    vault_action = vault_root / "observability" / "demo" / "actions" / "notes.yaml"
    _write_action(asset_action, action_id="notes", page="/observability/notes")
    _write_action(vault_action, action_id="notes", page="notes")

    route_file = repo_root / "apps" / "dashboard" / "app" / "observability" / "notes" / "page.tsx"
    route_file.parent.mkdir(parents=True, exist_ok=True)
    route_file.write_text("export default function Page() { return null; }\n")

    monkeypatch.setenv("AUGUR_ROOT", str(repo_root))
    monkeypatch.setenv("AUGUR_VAULT", str(vault_root))

    ctx = OpsContext(project_root=repo_root)
    issues = stale_actions.scan(ctx).issues
    fix_result = stale_actions.fix(ctx, issues)

    assert fix_result.success is True
    assert "page: /observability/notes" in vault_action.read_text()
    assert "page: /observability/notes" in asset_action.read_text()
