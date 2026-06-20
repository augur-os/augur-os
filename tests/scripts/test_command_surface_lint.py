from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    PROJECT_ROOT
    / "project-brain"
    / "capabilities"
    / "skills"
    / "platform-admin"
    / "scripts"
    / "command_surface_lint.py"
)
SPEC = importlib.util.spec_from_file_location("command_surface_lint", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
lint = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = lint
SPEC.loader.exec_module(lint)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_cross_platform_surface_requires_windows_and_posix_adapters(tmp_path: Path) -> None:
    manifest = tmp_path / "config" / "system" / "command_surfaces.yaml"
    write(
        manifest,
        """
version: 1
surfaces:
  xa:
    description: Launch Codex.
    platforms: [windows, posix]
    canonical_engine:
      type: python
      module: src.scripts.agent_launch
      mode: codex
    adapters:
      posix: scripts/xa-launch.sh
    installers:
      windows: scripts/install.ps1
      posix: scripts/install.sh
shell_inventory:
  declared_posix_only: []
  declared_internal: []
""".lstrip(),
    )
    write(tmp_path / "scripts" / "xa-launch.sh", "#!/usr/bin/env bash\n")

    issues = lint.lint_manifest(tmp_path, manifest)

    assert any(issue.code == "missing-windows-adapter" and issue.surface == "xa" for issue in issues)


def test_cross_platform_surface_requires_test_markers(tmp_path: Path) -> None:
    manifest = tmp_path / "config" / "system" / "command_surfaces.yaml"
    write(
        manifest,
        """
version: 1
surfaces:
  xa:
    description: Launch Codex.
    platforms: [windows, posix]
    canonical_engine:
      type: python
      module: src.scripts.agent_launch
      mode: codex
    adapters:
      windows: scripts/xa-launch.ps1
      posix: scripts/xa-launch.sh
    installers:
      windows: scripts/install.ps1
      posix: scripts/install.sh
shell_inventory:
  declared_posix_only: []
  declared_internal: []
""".lstrip(),
    )
    write(tmp_path / "scripts" / "xa-launch.ps1", "param()\n")
    write(tmp_path / "scripts" / "xa-launch.sh", "#!/usr/bin/env bash\n")

    issues = lint.lint_manifest(tmp_path, manifest)

    assert any(issue.code == "missing-surface-tests" and issue.surface == "xa" for issue in issues)


def test_cross_platform_surface_validates_test_files(tmp_path: Path) -> None:
    manifest = tmp_path / "config" / "system" / "command_surfaces.yaml"
    write(
        manifest,
        """
version: 1
surfaces:
  xa:
    description: Launch Codex.
    platforms: [windows, posix]
    canonical_engine:
      type: python
      module: src.scripts.agent_launch
      mode: codex
    adapters:
      windows: scripts/xa-launch.ps1
      posix: scripts/xa-launch.sh
    installers:
      windows: scripts/install.ps1
      posix: scripts/install.sh
    tests:
      - tests/scripts/test_xa_launch.py
shell_inventory:
  declared_posix_only: []
  declared_internal: []
""".lstrip(),
    )
    write(tmp_path / "scripts" / "xa-launch.ps1", "param()\n")
    write(tmp_path / "scripts" / "xa-launch.sh", "#!/usr/bin/env bash\n")

    issues = lint.lint_manifest(tmp_path, manifest)

    assert any(issue.code == "missing-surface-test-file" for issue in issues)


def test_cross_platform_surface_rejects_stale_installer_block(tmp_path: Path) -> None:
    manifest = tmp_path / "config" / "system" / "command_surfaces.yaml"
    write(
        manifest,
        """
version: 1
surfaces:
  xa:
    description: Launch Codex.
    platforms: [windows, posix]
    canonical_engine:
      type: python
      module: src.scripts.agent_launch
      mode: codex
    adapters:
      windows: scripts/xa-launch.ps1
      posix: scripts/xa-launch.sh
    installers:
      windows: scripts/install.ps1
    tests:
      - tests/scripts/test_xa_launch.py
shell_inventory:
  declared_posix_only: []
  declared_internal: []
""".lstrip(),
    )
    write(tmp_path / "scripts" / "xa-launch.ps1", "param()\n")
    write(tmp_path / "scripts" / "xa-launch.sh", "#!/usr/bin/env bash\n")
    write(tmp_path / "tests" / "scripts" / "test_xa_launch.py", "def test_xa(): pass\n")
    write(
        tmp_path / "scripts" / "install.ps1",
        """
# === augur CLI shortcuts (ca/xa/ga) ===
function xa { codex --dangerously-bypass-approvals-and-sandbox @args }
# === end augur CLI shortcuts ===
""".lstrip(),
    )

    issues = lint.lint_manifest(tmp_path, manifest)

    assert any(issue.code == "installer-direct-client-command" for issue in issues)


def test_cross_platform_surface_rejects_shell_canonical_engine(tmp_path: Path) -> None:
    manifest = tmp_path / "config" / "system" / "command_surfaces.yaml"
    write(
        manifest,
        """
version: 1
surfaces:
  xa:
    description: Launch Codex.
    platforms: [windows, posix]
    canonical_engine:
      type: shell
      path: scripts/xa-launch.sh
    adapters:
      windows: scripts/xa-launch.ps1
      posix: scripts/xa-launch.sh
    installers:
      windows: scripts/install.ps1
      posix: scripts/install.sh
shell_inventory:
  declared_posix_only: []
  declared_internal: []
""".lstrip(),
    )
    write(tmp_path / "scripts" / "xa-launch.ps1", "param()\n")
    write(tmp_path / "scripts" / "xa-launch.sh", "#!/usr/bin/env bash\n")

    issues = lint.lint_manifest(tmp_path, manifest)

    assert any(issue.code == "cross-platform-shell-engine" for issue in issues)


def test_shell_script_inventory_must_be_declared(tmp_path: Path) -> None:
    manifest = tmp_path / "config" / "system" / "command_surfaces.yaml"
    write(
        manifest,
        """
version: 1
surfaces: {}
shell_inventory:
  declared_posix_only: []
  declared_internal: []
""".lstrip(),
    )
    write(tmp_path / "scripts" / "new-tool.sh", "#!/usr/bin/env bash\n")

    issues = lint.lint_manifest(tmp_path, manifest, tracked_files=["scripts/new-tool.sh"])

    assert any(issue.code == "unclassified-shell-script" and issue.path == "scripts/new-tool.sh" for issue in issues)


def test_declared_posix_only_script_is_allowed(tmp_path: Path) -> None:
    manifest = tmp_path / "config" / "system" / "command_surfaces.yaml"
    write(
        manifest,
        """
version: 1
surfaces: {}
shell_inventory:
  declared_posix_only:
    - path: scripts/install.sh
      reason: POSIX installer; Windows equivalent is scripts/install.ps1.
  declared_internal: []
""".lstrip(),
    )
    write(tmp_path / "scripts" / "install.sh", "#!/bin/bash\n")

    issues = lint.lint_manifest(tmp_path, manifest, tracked_files=["scripts/install.sh"])

    assert not issues


def test_missing_adapter_file_can_be_required(tmp_path: Path) -> None:
    manifest = tmp_path / "config" / "system" / "command_surfaces.yaml"
    write(
        manifest,
        """
version: 1
surfaces:
  xa:
    description: Launch Codex.
    platforms: [windows, posix]
    canonical_engine:
      type: python
      module: src.scripts.agent_launch
      mode: codex
    adapters:
      windows: scripts/xa-launch.ps1
      posix: scripts/xa-launch.sh
shell_inventory:
  declared_posix_only: []
  declared_internal: []
""".lstrip(),
    )
    write(tmp_path / "scripts" / "xa-launch.sh", "#!/usr/bin/env bash\n")

    issues = lint.lint_manifest(tmp_path, manifest, require_adapter_files=True)

    assert any(issue.code == "missing-adapter-file" and issue.path == "scripts/xa-launch.ps1" for issue in issues)


def test_missing_adapter_file_can_be_ignored_for_staged_manifest(tmp_path: Path) -> None:
    manifest = tmp_path / "config" / "system" / "command_surfaces.yaml"
    write(
        manifest,
        """
version: 1
surfaces:
  xa:
    description: Launch Codex.
    platforms: [windows, posix]
    canonical_engine:
      type: python
      module: src.scripts.agent_launch
      mode: codex
    adapters:
      windows: scripts/xa-launch.ps1
      posix: scripts/xa-launch.sh
shell_inventory:
  declared_posix_only: []
  declared_internal: []
""".lstrip(),
    )
    write(tmp_path / "scripts" / "xa-launch.sh", "#!/usr/bin/env bash\n")

    issues = lint.lint_manifest(tmp_path, manifest, require_adapter_files=False)

    assert not any(issue.code == "missing-adapter-file" for issue in issues)


def test_adapter_extensions_are_validated(tmp_path: Path) -> None:
    manifest = tmp_path / "config" / "system" / "command_surfaces.yaml"
    write(
        manifest,
        """
version: 1
surfaces:
  xa:
    description: Launch Codex.
    platforms: [windows, posix]
    canonical_engine:
      type: python
      module: src.scripts.agent_launch
      mode: codex
    adapters:
      windows: scripts/xa-launch.sh
      posix: scripts/xa-launch.ps1
shell_inventory:
  declared_posix_only: []
  declared_internal: []
""".lstrip(),
    )
    write(tmp_path / "scripts" / "xa-launch.sh", "#!/usr/bin/env bash\n")
    write(tmp_path / "scripts" / "xa-launch.ps1", "param()\n")

    issues = lint.lint_manifest(tmp_path, manifest)

    assert any(issue.code == "windows-adapter-not-powershell" for issue in issues)
    assert any(issue.code == "posix-adapter-not-shell" for issue in issues)


def test_extensionless_shell_shebang_must_be_declared(tmp_path: Path) -> None:
    manifest = tmp_path / "config" / "system" / "command_surfaces.yaml"
    write(
        manifest,
        """
version: 1
surfaces: {}
shell_inventory:
  declared_posix_only: []
  declared_internal: []
""".lstrip(),
    )
    write(tmp_path / "scripts" / "helper", "#!/bin/bash\n")

    issues = lint.lint_manifest(tmp_path, manifest, tracked_files=["scripts/helper"])

    assert any(issue.code == "unclassified-shell-script" and issue.path == "scripts/helper" for issue in issues)


def test_cli_reports_missing_manifest_as_issue(tmp_path: Path, capsys) -> None:
    result = lint.main(["--root", str(tmp_path), "--manifest", str(tmp_path / "missing.yaml")])

    captured = capsys.readouterr()
    assert result == 1
    assert "missing-manifest" in captured.out


def test_cli_reports_git_ls_files_failure_as_issue(tmp_path: Path, monkeypatch, capsys) -> None:
    manifest = tmp_path / "config" / "system" / "command_surfaces.yaml"
    write(
        manifest,
        """
version: 1
surfaces: {}
shell_inventory:
  declared_posix_only: []
  declared_internal: []
""".lstrip(),
    )

    def fake_run(*args, **kwargs):
        return lint.subprocess.CompletedProcess(args=args[0], returncode=128, stdout="", stderr="fatal: nope")

    monkeypatch.setattr(lint.subprocess, "run", fake_run)

    result = lint.main(["--root", str(tmp_path), "--manifest", str(manifest)])

    captured = capsys.readouterr()
    assert result == 1
    assert "tracked-files-unavailable" in captured.out
