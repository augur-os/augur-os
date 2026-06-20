from __future__ import annotations

from pathlib import Path

import pytest

from src.config.global_identity_drift import scan_editable_install_locations, scan_pth_files
from src.config.runtime_identity import (
    GlobalIdentityError,
    GlobalMutationGuard,
    build_worktree_overlay_env,
    resolve_runtime_identity,
)


def _linked_worktree(tmp_path: Path, name: str) -> tuple[Path, Path]:
    main_root = tmp_path / "Augur"
    worktree_root = tmp_path / ".worktrees" / name
    gitdir = main_root / ".git" / "worktrees" / name
    gitdir.mkdir(parents=True, exist_ok=True)
    main_root.mkdir(parents=True, exist_ok=True)
    worktree_root.mkdir(parents=True, exist_ok=True)
    (main_root / "project.yaml").write_text("name: augur\n", encoding="utf-8")
    (worktree_root / "project.yaml").write_text("name: augur\n", encoding="utf-8")
    (worktree_root / ".git").write_text(f"gitdir: {gitdir}\n", encoding="utf-8")
    return main_root, worktree_root


def test_two_worktrees_can_overlay_but_not_mutate_global_identity(tmp_path: Path) -> None:
    main_root, worktree_a = _linked_worktree(tmp_path, "feature-a")
    _same_main, worktree_b = _linked_worktree(tmp_path, "feature-b")
    identity_a = resolve_runtime_identity(worktree_a)
    identity_b = resolve_runtime_identity(worktree_b)

    env_a = build_worktree_overlay_env(identity_a, {})
    env_b = build_worktree_overlay_env(identity_b, {})

    assert env_a["AUGUR_PROJECT_ROOT"] == str(worktree_a.resolve())
    assert env_b["AUGUR_PROJECT_ROOT"] == str(worktree_b.resolve())
    for identity, worktree in ((identity_a, worktree_a), (identity_b, worktree_b)):
        with pytest.raises(GlobalIdentityError):
            with GlobalMutationGuard(identity, target_root=worktree, operation="install"):
                raise AssertionError("guard did not block")
        with GlobalMutationGuard(
            identity,
            target_root=main_root,
            operation="client-sync",
            allow_delegated=True,
        ):
            delegated = True
        assert delegated is True


def test_fixture_drift_scanners_catch_shared_worktree_identity(tmp_path: Path) -> None:
    main_root, worktree = _linked_worktree(tmp_path, "feature-a")
    site_packages = tmp_path / "site-packages"
    site_packages.mkdir()
    (site_packages / "_editable_impl_augur_cli.pth").write_text(
        f"{worktree}\n",
        encoding="utf-8",
    )
    pip_json = '[{"name": "augur-cli", "editable_project_location": "' + str(worktree) + '"}]'

    editable_issues = scan_editable_install_locations(
        pip_json=pip_json,
        authority_root=main_root,
    )
    pth_issues = scan_pth_files(
        site_package_dirs=[site_packages],
        authority_root=main_root,
    )

    assert editable_issues
    assert pth_issues


def test_precommit_skill_placement_guard_does_not_uv_sync_worktree() -> None:
    hook = Path(".githooks/pre-commit").read_text(encoding="utf-8")

    assert "uv run python scripts/check_skill_test_placement.py" not in hook
    assert "scripts/check_skill_test_placement.py" in hook
