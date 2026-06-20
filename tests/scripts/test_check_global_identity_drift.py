from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace


def _load_check_script():
    script = Path("scripts/check_global_identity_drift.py").resolve()
    spec = importlib.util.spec_from_file_location("check_global_identity_drift", script)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_check_global_identity_drift_json_reports_fixture_issue(tmp_path: Path) -> None:
    authority = tmp_path / "Augur"
    worktree = tmp_path / "augur-wt-feature"
    site_packages = tmp_path / "site-packages"
    authority.mkdir()
    worktree.mkdir()
    site_packages.mkdir()
    (authority / "project.yaml").write_text("name: augur\n", encoding="utf-8")
    (site_packages / "_editable_impl_augur_mcp.pth").write_text(
        f"{worktree}\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "scripts/check_global_identity_drift.py",
            "--root",
            str(authority),
            "--site-packages",
            str(site_packages),
            "--json",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["issues"][0]["surface"] == "pth"
    assert payload["issues"][0]["path"] == str(worktree.resolve())


def test_repair_reports_fresh_recheck_result(
    monkeypatch,
    capsys,
    tmp_path: Path,
) -> None:
    module = _load_check_script()
    authority = tmp_path / "Augur"
    current = tmp_path / ".worktrees" / "feature"
    site_packages = tmp_path / "site-packages"
    python = tmp_path / ".venv" / "bin" / "python"
    captured: list[list[str]] = []

    monkeypatch.setattr(
        module,
        "resolve_runtime_identity",
        lambda root: SimpleNamespace(authority_root=authority, current_root=current),
    )
    monkeypatch.setattr(module, "scan_global_identity_drift", lambda **kwargs: [object()])
    monkeypatch.setattr(
        module,
        "repair_editable_identity",
        lambda **kwargs: subprocess.CompletedProcess([], 0, "", ""),
    )

    def fake_run(
        command: list[str],
        *,
        check: bool,
        capture_output: bool,
        text: bool,
        timeout: int,
    ) -> subprocess.CompletedProcess[str]:
        captured.append(command)
        return subprocess.CompletedProcess(command, 0, '{"ok": true}\n', "")

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    monkeypatch.setattr(
        module.sys,
        "argv",
        [
            "check_global_identity_drift.py",
            "--root",
            str(current),
            "--python",
            str(python),
            "--site-packages",
            str(site_packages),
            "--repair",
            "--json",
        ],
    )

    assert module.main() == 0

    out = capsys.readouterr()
    configure_command = captured[0]
    command = captured[1]
    assert out.out == '{"ok": true}\n'
    assert configure_command[:2] == [
        sys.executable,
        str(Path("scripts/configure_mcp.py").resolve()),
    ]
    assert configure_command[configure_command.index("--repo-root") + 1] == str(authority)
    assert configure_command[configure_command.index("--python") + 1] == str(python)
    assert "--apply" in configure_command
    assert "--no-external" in configure_command
    assert "--repair" not in command
    assert command[:2] == [sys.executable, str(Path("scripts/check_global_identity_drift.py").resolve())]
    assert command[command.index("--root") + 1] == str(current)
    assert command[command.index("--python") + 1] == str(python)
    assert command[command.index("--site-packages") + 1] == str(site_packages)
    assert "--json" in command
