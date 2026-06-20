"""Tests for generated skill release matrix artifacts."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from src.lib.skill_release_matrix import build_skill_release_matrix


def _record(path: Path, **overrides):
    defaults = dict(
        name="knowledge",
        path=path,
        hub="brain",
        tier=0,
        group="brain",
        release="mvp",
        visibility="app",
        requires_platform=False,
        dependencies={},
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _load_generate_skill_release_matrix_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "generate-skill-release-matrix.py"
    spec = importlib.util.spec_from_file_location("generate_skill_release_matrix", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_skill_release_matrix_summarizes_release_targets(tmp_path: Path):
    records = [
        _record(tmp_path / "skills" / "knowledge", name="knowledge", release="mvp"),
        _record(
            tmp_path / "staging" / "r2" / "skills" / "content",
            name="content",
            hub="studio",
            group="business",
            release="r1",
            requires_platform=True,
            dependencies={"required": ["knowledge"]},
        ),
        _record(
            tmp_path / "staging" / "later" / "skills" / "consulting-template",
            name="consulting-template",
            hub="studio",
            group="templates",
            release="later",
        ),
        _record(
            tmp_path / "external" / "ignored",
            name="external-skill",
            tier=1,
            group="other",
            release="later",
        ),
    ]

    matrix = build_skill_release_matrix(records, tmp_path)

    assert matrix["count"] == 3
    assert matrix["release_counts"] == {
        "mvp": 1,
        "r1": 1,
        "r2": 0,
        "r3": 0,
        "r4": 0,
        "later": 1,
    }
    assert matrix["targets"]["mvp"] == {
        "enabled_releases": ["mvp"],
        "count": 1,
        "skills": ["knowledge"],
    }
    assert matrix["targets"]["r1"] == {
        "enabled_releases": ["mvp", "r1"],
        "count": 2,
        "skills": ["content", "knowledge"],
    }
    assert matrix["skills"][1] == {
        "name": "content",
        "path": "staging/r2/skills/content",
        "hub": "studio",
        "group": "business",
        "release": "r1",
        "visibility": "app",
        "requires_platform": True,
        "required_dependencies": ["knowledge"],
    }


def test_build_skill_release_matrix_normalizes_vault_paths(tmp_path: Path, monkeypatch):
    repo_root = tmp_path / "repo"
    vault_root = tmp_path / "vault"
    records = [
        _record(
            vault_root / "skills" / "career-ops",
            name="career-ops",
            hub="career",
            group="business",
            release="r4",
        ),
    ]

    monkeypatch.setattr("src.lib.skill_release_matrix.get_vault_dir", lambda: vault_root)

    matrix = build_skill_release_matrix(records, repo_root)

    assert matrix["skills"] == [
        {
            "name": "career-ops",
            "path": "vault/skills/career-ops",
            "hub": "career",
            "group": "business",
            "release": "r4",
            "visibility": "app",
            "requires_platform": False,
            "required_dependencies": [],
        },
    ]


def test_build_skill_release_matrix_excludes_inactive_vault_roots(tmp_path: Path, monkeypatch):
    repo_root = tmp_path / "repo"
    vault_root = tmp_path / "vault"
    records = [
        _record(
            vault_root / "drafts" / "staging" / "r2" / "skills" / "content",
            name="content",
            hub="studio",
            group="business",
            release="r1",
        ),
        _record(
            vault_root / "archive" / "skills" / "old-skill",
            name="old-skill",
            hub="studio",
            group="templates",
            release="later",
        ),
        _record(
            vault_root / "_drafts" / "staging" / "r1" / "skills" / "legacy",
            name="legacy",
            hub="studio",
            group="business",
            release="r1",
        ),
        _record(
            vault_root / "notes" / "client" / "drafts" / "research-skill",
            name="research-skill",
            hub="brain",
            group="brain",
            release="mvp",
        ),
        _record(
            repo_root / "scratch" / "drafts" / "repo-skill",
            name="repo-skill",
            hub="studio",
            group="templates",
            release="r2",
        ),
    ]

    monkeypatch.setattr("src.lib.skill_release_matrix.get_vault_dir", lambda: vault_root)

    matrix = build_skill_release_matrix(records, repo_root)

    assert matrix["skills"] == [
        {
            "name": "repo-skill",
            "path": "scratch/drafts/repo-skill",
            "hub": "studio",
            "group": "templates",
            "release": "r2",
            "visibility": "app",
            "requires_platform": False,
            "required_dependencies": [],
        },
        {
            "name": "research-skill",
            "path": "vault/notes/client/drafts/research-skill",
            "hub": "brain",
            "group": "brain",
            "release": "mvp",
            "visibility": "app",
            "requires_platform": False,
            "required_dependencies": [],
        },
    ]


def test_collect_release_records_uses_managed_live_skills_and_excludes_drafts(tmp_path: Path, monkeypatch):
    module = _load_generate_skill_release_matrix_module()
    repo_skill = tmp_path / "skills" / "knowledge"
    repo_skill.mkdir(parents=True)
    (repo_skill / "SKILL.md").write_text(
        "---\nname: knowledge\nx-augur-hub: brain\nx-augur-group: brain\nx-augur-release: mvp\n---\n",
        encoding="utf-8",
    )

    vault_skills = tmp_path / "vault" / "skills"
    vault_skill = vault_skills / "career-ops"
    vault_skill.mkdir(parents=True)
    (vault_skill / "SKILL.md").write_text(
        "---\nname: career-ops\nx-augur-hub: career\nx-augur-group: career\nx-augur-release: r4\n---\n",
        encoding="utf-8",
    )

    # Private vault drafts exist on disk but are not managed live skill roots.
    vault_draft = tmp_path / "vault" / "drafts" / "staging" / "r2" / "skills" / "content"
    vault_draft.mkdir(parents=True)
    (vault_draft / "SKILL.md").write_text(
        "---\nname: content\nx-augur-hub: studio\nx-augur-group: business\nx-augur-release: r1\n---\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        module, "get_managed_skill_source_dirs", lambda project_root: [project_root / "skills", vault_skills]
    )

    records = module.collect_release_records(tmp_path)

    assert [record.name for record in records] == ["career-ops", "knowledge"]
    assert [record.path for record in records] == [vault_skill, repo_skill]


def test_generate_skill_release_matrix_collects_managed_live_records(monkeypatch):
    module = _load_generate_skill_release_matrix_module()
    seen = {}

    def fake_collect_release_records(project_root):
        seen["project_root"] = project_root
        return ["record"]

    def fake_build_skill_release_matrix(records, project_root):
        seen["records"] = records
        seen["matrix_project_root"] = project_root
        return {"generated_at": "now", "count": 1, "skills": [{"name": "knowledge"}]}

    write_mock = MagicMock(return_value=True)

    monkeypatch.setattr(module, "collect_release_records", fake_collect_release_records)
    monkeypatch.setattr(module, "build_skill_release_matrix", fake_build_skill_release_matrix)
    monkeypatch.setattr(module, "write_stable_json", write_mock)

    module.main()

    assert seen["project_root"] == module.root
    assert seen["records"] == ["record"]
    assert seen["matrix_project_root"] == module.root
    write_mock.assert_called_once()
    args, kwargs = write_mock.call_args
    assert args[0] == module.root / "docs" / "generated" / "skill-release-matrix.json"
    assert args[1]["count"] == 1
    assert args[1]["skills"] == [{"name": "knowledge"}]
    assert kwargs == {"volatile_keys": ["generated_at"]}


def test_repo_ingest_skill_is_shared_vault_mvp_and_matrix_matches() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    legacy_repo_skill_md = repo_root / "skills" / "ingest" / "SKILL.md"
    shared_skill_md = repo_root / "project-brain" / "capabilities" / "skills" / "ingest" / "SKILL.md"
    staged_skill_dir = repo_root / "staging" / "r2" / "skills" / "ingest"

    assert (
        not legacy_repo_skill_md.exists()
    ), "skills/ingest/SKILL.md should not exist after the project-brain skill root migration."
    assert shared_skill_md.exists()
    assert not staged_skill_dir.exists()
    assert "x-augur-release: mvp" in shared_skill_md.read_text(encoding="utf-8")

    # Generate the matrix on the fly — skill-release-matrix.json is gitignored
    # (it bakes local absolute paths), so tests must build it from sources.
    module = _load_generate_skill_release_matrix_module()
    records = module.collect_release_records(repo_root)
    matrix = build_skill_release_matrix(records, repo_root)
    ingest_entry = next(skill for skill in matrix["skills"] if skill["name"] == "ingest")

    assert ingest_entry["path"] == "project-brain/capabilities/skills/ingest"
    assert ingest_entry["release"] == "mvp"


def test_repo_platform_admin_skill_is_live_mvp_and_matrix_matches() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    skill_md = repo_root / "project-brain" / "capabilities" / "skills" / "platform-admin" / "SKILL.md"
    staged_skill_dir = repo_root / "staging" / "r3" / "skills" / "platform-admin"

    assert skill_md.exists()
    assert not staged_skill_dir.exists()
    assert "x-augur-release: mvp" in skill_md.read_text(encoding="utf-8")

    # Generate the matrix on the fly — skill-release-matrix.json is gitignored
    # (it bakes local absolute paths), so tests must build it from sources.
    module = _load_generate_skill_release_matrix_module()
    records = module.collect_release_records(repo_root)
    matrix = build_skill_release_matrix(records, repo_root)
    platform_admin_entry = next(skill for skill in matrix["skills"] if skill["name"] == "platform-admin")

    assert platform_admin_entry["path"] == "project-brain/capabilities/skills/platform-admin"
    assert platform_admin_entry["release"] == "mvp"
