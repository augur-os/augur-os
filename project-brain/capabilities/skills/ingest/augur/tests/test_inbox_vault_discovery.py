from __future__ import annotations

from pathlib import Path

import yaml


def _write_defaults(repo: Path, body: str = "") -> None:
    config_dir = repo / "config" / "system"
    config_dir.mkdir(parents=True)
    (config_dir / "inbox.yaml").write_text(
        "version: 1\n"
        "default_sources: []\n"
        f"{body}",
        encoding="utf-8",
    )


def _patch_registry_paths(monkeypatch, tmp_path: Path, repo: Path) -> tuple[Path, Path, Path]:
    from skills.ingest.scripts import inbox_registry

    runtime = tmp_path / "runtime"
    docs = tmp_path / "docs"
    vault = tmp_path / "vault"

    monkeypatch.setattr(inbox_registry, "get_runtime_dir", lambda: runtime)
    monkeypatch.setattr(inbox_registry, "get_documents_dir", lambda: docs)
    monkeypatch.setattr(inbox_registry, "get_vault_dir", lambda: vault)
    monkeypatch.setattr(inbox_registry, "get_config_dir", lambda: repo / "config")
    return runtime, docs, vault


def _write_marker(
    project: Path,
    *,
    marker: str = ".augur/vault.yaml",
    candidate_id: str = "client-project",
    kind: str = "project",
    name: str = "Client Project",
    vault_root: str = "./vault",
    docs_root: str = "./docs",
) -> None:
    (project / Path(marker).parent).mkdir(parents=True)
    (project / "vault").mkdir(parents=True)
    (project / "docs").mkdir(parents=True)
    (project / marker).write_text(
        f"id: {candidate_id}\n"
        f"kind: {kind}\n"
        f"name: {name}\n"
        f"vault_root: {vault_root}\n"
        f"docs_root: {docs_root}\n",
        encoding="utf-8",
    )


def test_discover_project_vault_marker_records_read_only_candidate(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from skills.ingest.scripts.inbox_vault_discovery import discover_vault_candidates

    repo = tmp_path / "repo"
    _write_defaults(
        repo,
        "discovery:\n  marker_files: [.augur/vault.yaml]\n  max_depth: 3\n",
    )
    runtime, _, _ = _patch_registry_paths(monkeypatch, tmp_path, repo)
    project = tmp_path / "workspace" / "client-project"
    _write_marker(project)

    candidates = discover_vault_candidates(search_roots=[tmp_path / "workspace"])

    assert [item.candidate_id for item in candidates] == ["client-project"]
    assert candidates[0].status == "unapproved"
    assert candidates[0].writable is False
    assert candidates[0].docs_root == str(project / "docs")
    payload = yaml.safe_load(
        (runtime / "brain" / "inbox" / "config" / "discovered.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert payload["candidates"][0]["candidate_id"] == "client-project"
    assert payload["candidates"][0]["writable"] is False


def test_register_candidate_turns_candidate_into_writable_target(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from skills.ingest.scripts import inbox_registry
    from skills.ingest.scripts.inbox_vault_discovery import (
        discover_vault_candidates,
        register_discovered_vault,
    )

    repo = tmp_path / "repo"
    _write_defaults(repo)
    _patch_registry_paths(monkeypatch, tmp_path, repo)
    project = tmp_path / "workspace" / "project-alpha"
    _write_marker(
        project,
        candidate_id="project-alpha",
        kind="project",
        name="Project Alpha",
    )

    discover_vault_candidates(search_roots=[tmp_path / "workspace"])
    target = register_discovered_vault("project-alpha")
    registry = inbox_registry.load_inbox_registry()

    assert target.id == "project-alpha"
    assert target.writable is True
    assert registry.vault_by_id("project-alpha").kind == "project"
    assert registry.vault_by_id("project-alpha").docs_root == str(project / "docs")


def test_discovery_uses_configured_roots_and_marker_files(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from skills.ingest.scripts.inbox_vault_discovery import discover_vault_candidates

    repo = tmp_path / "repo"
    workspace = tmp_path / "configured-root"
    _write_defaults(
        repo,
        "discovery:\n"
        f"  approved_parent_roots: [{workspace}]\n"
        "  marker_files: [meta/augur-vault.yaml]\n"
        "  max_depth: 2\n",
    )
    _patch_registry_paths(monkeypatch, tmp_path, repo)
    _write_marker(
        workspace / "team-vault",
        marker="meta/augur-vault.yaml",
        candidate_id="team-vault",
        kind="team",
        name="Team Vault",
    )

    candidates = discover_vault_candidates()

    assert [item.candidate_id for item in candidates] == ["team-vault"]
    assert candidates[0].kind == "team"
    assert candidates[0].reason.startswith("found meta/augur-vault.yaml")


def test_discovery_accepts_explicit_marker_file_path(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from skills.ingest.scripts.inbox_vault_discovery import discover_vault_candidates

    repo = tmp_path / "repo"
    _write_defaults(
        repo,
        "discovery:\n  marker_files: [.augur/vault.yaml]\n  max_depth: 1\n",
    )
    _patch_registry_paths(monkeypatch, tmp_path, repo)
    project = tmp_path / "workspace" / "explicit-project"
    _write_marker(project, candidate_id="explicit-project", name="Explicit Project")

    candidates = discover_vault_candidates(
        explicit_paths=[project / ".augur" / "vault.yaml"]
    )

    assert [item.candidate_id for item in candidates] == ["explicit-project"]
    assert candidates[0].vault_root == str(project / "vault")
    assert candidates[0].docs_root == str(project / "docs")


def test_discovery_rejects_similarly_suffixed_marker_directory(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from skills.ingest.scripts.inbox_vault_discovery import discover_vault_candidates

    repo = tmp_path / "repo"
    _write_defaults(
        repo,
        "discovery:\n  marker_files: [.augur/vault.yaml]\n  max_depth: 2\n",
    )
    _patch_registry_paths(monkeypatch, tmp_path, repo)
    workspace = tmp_path / "workspace"
    _write_marker(
        workspace / "valid-project",
        candidate_id="valid-project",
        name="Valid Project",
    )
    _write_marker(
        workspace / "invalid-project",
        marker="not.augur/vault.yaml",
        candidate_id="invalid-project",
        name="Invalid Project",
    )

    candidates = discover_vault_candidates(search_roots=[workspace])

    assert [item.candidate_id for item in candidates] == ["valid-project"]


def test_discovery_keeps_same_candidate_seen_through_overlapping_inputs(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from skills.ingest.scripts import inbox_registry
    from skills.ingest.scripts.inbox_vault_discovery import (
        discover_vault_candidates,
        register_discovered_vault,
    )

    repo = tmp_path / "repo"
    _write_defaults(
        repo,
        "discovery:\n  marker_files: [.augur/vault.yaml]\n  max_depth: 2\n",
    )
    _patch_registry_paths(monkeypatch, tmp_path, repo)
    project = tmp_path / "workspace" / "overlap-project"
    marker = project / ".augur" / "vault.yaml"
    _write_marker(project, candidate_id="overlap-project", name="Overlap Project")

    candidates = discover_vault_candidates(
        search_roots=[tmp_path / "workspace"],
        explicit_paths=[marker],
    )
    target = register_discovered_vault("overlap-project")

    assert [item.candidate_id for item in candidates] == ["overlap-project"]
    assert target.id == "overlap-project"
    assert inbox_registry.load_inbox_registry().vault_by_id("overlap-project").writable


def test_discovery_rejects_absolute_roots_outside_marker_project(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from skills.ingest.scripts.inbox_vault_discovery import discover_vault_candidates

    repo = tmp_path / "repo"
    _write_defaults(repo)
    _patch_registry_paths(monkeypatch, tmp_path, repo)
    outside_docs = tmp_path / "outside-docs"
    outside_docs.mkdir()
    project = tmp_path / "workspace" / "absolute-escape"
    _write_marker(
        project,
        candidate_id="absolute-escape",
        docs_root=str(outside_docs),
    )

    assert discover_vault_candidates(search_roots=[tmp_path / "workspace"]) == []


def test_discovery_rejects_parent_traversal_roots_outside_marker_project(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from skills.ingest.scripts.inbox_vault_discovery import discover_vault_candidates

    repo = tmp_path / "repo"
    _write_defaults(repo)
    _patch_registry_paths(monkeypatch, tmp_path, repo)
    outside_docs = tmp_path / "workspace" / "outside-docs"
    outside_docs.mkdir(parents=True)
    project = tmp_path / "workspace" / "parent-escape"
    _write_marker(
        project,
        candidate_id="parent-escape",
        docs_root="../outside-docs",
    )

    assert discover_vault_candidates(search_roots=[tmp_path / "workspace"]) == []


def test_discovery_refuses_duplicate_candidate_ids(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from skills.ingest.scripts.inbox_vault_discovery import discover_vault_candidates

    repo = tmp_path / "repo"
    _write_defaults(repo)
    _patch_registry_paths(monkeypatch, tmp_path, repo)
    _write_marker(
        tmp_path / "workspace" / "first",
        candidate_id="duplicate-project",
        name="First Project",
    )
    _write_marker(
        tmp_path / "workspace" / "second",
        candidate_id="duplicate-project",
        name="Second Project",
    )
    _write_marker(
        tmp_path / "workspace" / "unique",
        candidate_id="unique-project",
        name="Unique Project",
    )

    candidates = discover_vault_candidates(search_roots=[tmp_path / "workspace"])

    assert [item.candidate_id for item in candidates] == ["unique-project"]


def test_discovery_keeps_registered_vaults_out_of_candidates(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from skills.ingest.scripts import inbox_registry
    from skills.ingest.scripts.inbox_unified_models import InboxVaultTarget
    from skills.ingest.scripts.inbox_vault_discovery import discover_vault_candidates

    repo = tmp_path / "repo"
    _write_defaults(repo)
    _patch_registry_paths(monkeypatch, tmp_path, repo)
    project = tmp_path / "workspace" / "project-alpha"
    _write_marker(project, candidate_id="project-alpha", name="Project Alpha")
    inbox_registry.register_vault_target(
        InboxVaultTarget(
            id="project-alpha",
            kind="project",
            name="Project Alpha",
            vault_root=str(project / "vault"),
            docs_root=str(project / "docs"),
        )
    )

    assert discover_vault_candidates(search_roots=[tmp_path / "workspace"]) == []


def test_discovery_respects_max_depth_and_ignores_bad_markers(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from skills.ingest.scripts.inbox_vault_discovery import discover_vault_candidates

    repo = tmp_path / "repo"
    _write_defaults(
        repo,
        "discovery:\n  marker_files: [.augur/vault.yaml]\n  max_depth: 1\n",
    )
    _patch_registry_paths(monkeypatch, tmp_path, repo)
    shallow = tmp_path / "workspace" / "shallow"
    _write_marker(shallow, candidate_id="shallow")
    _write_marker(tmp_path / "workspace" / "one" / "two" / "deep", candidate_id="deep")
    bad = tmp_path / "workspace" / "bad"
    (bad / ".augur").mkdir(parents=True)
    (bad / ".augur" / "vault.yaml").write_text("[not-a-mapping", encoding="utf-8")

    candidates = discover_vault_candidates(search_roots=[tmp_path / "workspace"])

    assert [item.candidate_id for item in candidates] == ["shallow"]
