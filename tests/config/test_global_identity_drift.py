from __future__ import annotations

import json
from pathlib import Path

from src.config.global_identity_drift import (
    IdentityIssue,
    scan_editable_install_locations,
    scan_import_specs,
    scan_pth_files,
)


def test_identity_issue_as_dict_serializes_paths(tmp_path: Path) -> None:
    issue = IdentityIssue(
        surface="pth",
        name="sample.pth",
        path=tmp_path / "augur-wt-feature",
        expected=tmp_path / "Augur",
        detail="sample detail",
    )

    assert issue.as_dict() == {
        "surface": "pth",
        "name": "sample.pth",
        "path": str(tmp_path / "augur-wt-feature"),
        "expected": str(tmp_path / "Augur"),
        "detail": "sample detail",
        "repairable": False,
    }


def test_scan_editable_install_locations_flags_worktree(tmp_path: Path) -> None:
    authority = tmp_path / "Augur"
    worktree = tmp_path / "augur-wt-feature"
    authority.mkdir()
    worktree.mkdir()
    pip_json = json.dumps(
        [
            {"name": "augur-cli", "editable_project_location": str(worktree)},
            {"name": "other", "editable_project_location": str(tmp_path / "other")},
        ]
    )

    issues = scan_editable_install_locations(
        pip_json=pip_json,
        authority_root=authority,
    )

    assert issues == [
        IdentityIssue(
            surface="editable-install",
            name="augur-cli",
            path=worktree.resolve(),
            expected=authority.resolve(),
            detail="editable install points at a worktree",
            repairable=True,
        )
    ]


def test_scan_editable_install_locations_flags_arbitrary_non_authority_checkout(
    tmp_path: Path,
) -> None:
    authority = tmp_path / "Augur"
    checkout = tmp_path / "feature-checkout"
    authority.mkdir()
    checkout.mkdir()
    pip_json = json.dumps([{"name": "augur-cli", "editable_project_location": str(checkout)}])

    issues = scan_editable_install_locations(
        pip_json=pip_json,
        authority_root=authority,
    )

    assert issues == [
        IdentityIssue(
            surface="editable-install",
            name="augur-cli",
            path=checkout.resolve(),
            expected=authority.resolve(),
            detail="editable install points at a non-authority Augur checkout",
            repairable=True,
        )
    ]


def test_scan_editable_install_locations_ignores_authority_root(tmp_path: Path) -> None:
    authority = tmp_path / "augur-wt-authority"
    authority.mkdir()
    pip_json = json.dumps([{"name": "augur-cli", "editable_project_location": str(authority)}])

    issues = scan_editable_install_locations(
        pip_json=pip_json,
        authority_root=authority,
    )

    assert issues == []


def test_scan_pth_files_flags_worktree_path(tmp_path: Path) -> None:
    authority = tmp_path / "Augur"
    worktree = tmp_path / "augur-wt-feature"
    site_packages = tmp_path / "site-packages"
    authority.mkdir()
    worktree.mkdir()
    site_packages.mkdir()
    pth = site_packages / "_editable_impl_augur_mcp.pth"
    pth.write_text(f"\nimport site\n{worktree}\n", encoding="utf-8")

    issues = scan_pth_files(
        site_package_dirs=[site_packages],
        authority_root=authority,
    )

    assert issues[0].surface == "pth"
    assert issues[0].name == str(pth)
    assert issues[0].path == worktree.resolve()
    assert issues[0].expected == authority.resolve()


def test_scan_augur_pth_files_flags_arbitrary_non_authority_checkout(
    tmp_path: Path,
) -> None:
    authority = tmp_path / "Augur"
    checkout = tmp_path / "feature-checkout"
    site_packages = tmp_path / "site-packages"
    authority.mkdir()
    checkout.mkdir()
    site_packages.mkdir()
    pth = site_packages / "_editable_impl_augur_cli.pth"
    pth.write_text(f"{checkout}\n", encoding="utf-8")

    issues = scan_pth_files(
        site_package_dirs=[site_packages],
        authority_root=authority,
    )

    assert issues == [
        IdentityIssue(
            surface="pth",
            name=str(pth),
            path=checkout.resolve(),
            expected=authority.resolve(),
            detail=".pth file points at a non-authority Augur checkout",
            repairable=True,
        )
    ]


def test_scan_pth_files_ignores_non_augur_arbitrary_checkout(tmp_path: Path) -> None:
    authority = tmp_path / "Augur"
    checkout = tmp_path / "feature-checkout"
    site_packages = tmp_path / "site-packages"
    authority.mkdir()
    checkout.mkdir()
    site_packages.mkdir()
    (site_packages / "other_package.pth").write_text(f"{checkout}\n", encoding="utf-8")

    issues = scan_pth_files(
        site_package_dirs=[site_packages],
        authority_root=authority,
    )

    assert issues == []


def test_scan_pth_files_ignores_authority_root_entries(tmp_path: Path) -> None:
    authority = tmp_path / "augur-wt-authority"
    site_packages = tmp_path / "site-packages"
    authority.mkdir()
    site_packages.mkdir()
    (site_packages / "_editable_impl_augur_mcp.pth").write_text(
        f"{authority}\n",
        encoding="utf-8",
    )

    issues = scan_pth_files(
        site_package_dirs=[site_packages],
        authority_root=authority,
    )

    assert issues == []


def test_scan_import_specs_flags_arbitrary_non_authority_origin(
    tmp_path: Path,
    monkeypatch,
) -> None:
    authority = tmp_path / "Augur"
    checkout = tmp_path / "feature-checkout"
    origin = checkout / "src" / "mcp" / "augur_core" / "__init__.py"
    authority.mkdir()
    origin.parent.mkdir(parents=True)
    origin.write_text("", encoding="utf-8")

    def fake_find_spec(module_name: str):
        if module_name == "augur_core":
            return type("Spec", (), {"origin": str(origin)})()
        return None

    monkeypatch.setattr("src.config.global_identity_drift.importlib.util.find_spec", fake_find_spec)

    issues = scan_import_specs(authority_root=authority)

    assert issues == [
        IdentityIssue(
            surface="import-spec",
            name="augur_core",
            path=origin.resolve(),
            expected=authority.resolve(),
            detail="import spec resolves outside the authority checkout",
            repairable=True,
        )
    ]
