"""Fresh-install smoke tests for the public dev-loops CLI."""

from __future__ import annotations

import os
import subprocess
import sys
import importlib.util
from pathlib import Path

import yaml


SHARED_CAPABILITIES_ROOT = Path(__file__).resolve().parents[4]
SHARED_SKILLS_ROOT = SHARED_CAPABILITIES_ROOT / "skills"
DAEMON_ROOT = Path(__file__).resolve().parents[2]
EXECUTOR = DAEMON_ROOT / "scripts" / "adaptive_loop_executor.py"

FORBIDDEN_OUTPUT = (
    "Module file not found",
    ".gemini/skills",
    ".opencode/skills",
    ".codex/skills",
    "/Users/",
    "Traceback",
)


def _python_executable() -> str:
    repo_python = DAEMON_ROOT.parents[2] / ".venv" / "bin" / "python3"
    return str(repo_python if repo_python.is_file() else Path(sys.executable))


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def _write_fresh_project(project: Path, vault: Path) -> None:
    shared_skills_root = project / "project-brain" / "capabilities" / "skills"
    (project / "config" / "system").mkdir(parents=True)
    (shared_skills_root / "daemon").mkdir(parents=True)
    (shared_skills_root / "smoke-check" / "scripts").mkdir(parents=True)
    (project / ".gemini" / "skills" / "generated-smoke").mkdir(parents=True)
    (project / ".opencode" / "skills" / "generated-smoke").mkdir(parents=True)
    (project / ".codex" / "skills" / "generated-smoke").mkdir(parents=True)

    (project / "project.yaml").write_text(
        yaml.safe_dump(
            {
                "name": "FreshAugur",
                "paths": {"vault": str(vault)},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (project / "config" / "system" / "adaptive_loops.yaml").write_text(
        yaml.safe_dump(
            {
                "engine": {
                    "enabled": True,
                    "verify_command": "",
                    "nightly_time": "03:00",
                },
                "loops": {
                    "smoke": {
                        "enabled": True,
                        "trigger": "nightly",
                        "budget": 1,
                        "budget_growth_rate": 1,
                        "categories": {
                            "smoke-check": {
                                "enabled": True,
                                "trust": 0.0,
                                "tier": 0,
                            },
                        },
                    },
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (shared_skills_root / "smoke-check" / "SKILL.md").write_text(
        "---\n"
        "name: smoke-check\n"
        "x-augur-commands:\n"
        "  - id: smoke-check\n"
        "    protocol: scan-fix\n"
        "    callable: scripts/smoke.py\n"
        "    loop:\n"
        "      name: smoke\n"
        "      trigger: nightly\n"
        "      tier: 0\n"
        "      trust: 0.0\n"
        "---\n"
        "# Smoke Check\n",
        encoding="utf-8",
    )
    (shared_skills_root / "smoke-check" / "scripts" / "smoke.py").write_text(
        "from types import SimpleNamespace\n\n"
        "name = 'smoke-check'\n\n"
        "def scan(ctx):\n"
        "    return SimpleNamespace(issues=[], summary='clean')\n\n"
        "def fix(ctx, issues):\n"
        "    return SimpleNamespace(success=True, changes=[], summary='clean')\n",
        encoding="utf-8",
    )

    generated_skill = (
        "---\n"
        "name: generated-smoke\n"
        "x-augur-commands:\n"
        "  - id: generated-smoke\n"
        "    protocol: scan-fix\n"
        "    callable: missing/generated.py\n"
        "    loop:\n"
        "      name: generated\n"
        "      trigger: nightly\n"
        "---\n"
        "# Generated Smoke\n"
    )
    for client_dir in (".gemini", ".opencode", ".codex"):
        (project / client_dir / "skills" / "generated-smoke" / "SKILL.md").write_text(
            generated_skill,
            encoding="utf-8",
        )

    _git(project, "init")


def _run_dev_loops(
    project: Path, env: dict[str, str], *args: str
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [_python_executable(), str(EXECUTOR), *args],
        cwd=project,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_dev_loops_fresh_install_lifecycle_is_quiet_and_private_path_free(
    tmp_path: Path,
) -> None:
    project = tmp_path / "fresh-project"
    vault = tmp_path / "missing-vault"
    project.mkdir()
    _write_fresh_project(project, vault)

    env = os.environ.copy()
    env.update(
        {
            "AUGUR_ROOT": str(project),
            "AUGUR_STATE": str(tmp_path / "state"),
            "AUGUR_LOGS": str(tmp_path / "logs"),
            "AUGUR_CACHE_DIR": str(tmp_path / "cache"),
            "AUGUR_VAULT": str(vault),
            "AUGUR_DOCUMENTS": str(tmp_path / "documents"),
            "AUGUR_APP_SUPPORT": str(tmp_path / "app-support"),
            "HOME": str(tmp_path / "home"),
            "PYTHONPATH": str(SHARED_CAPABILITIES_ROOT),
        }
    )

    commands = (
        ("registry",),
        ("status",),
        ("manifest",),
        ("report", "--days", "1"),
    )
    combined_output: list[str] = []
    for command in commands:
        result = _run_dev_loops(project, env, *command)
        output = result.stdout + result.stderr
        combined_output.append(output)
        assert result.returncode == 0, output

    output = "\n".join(combined_output)
    assert "smoke" in output
    assert "smoke-check" in output
    assert "not-installed" in output
    for forbidden in FORBIDDEN_OUTPUT:
        assert forbidden not in output


def test_shipped_loop_modules_do_not_resolve_legacy_vault_paths_at_import(
    monkeypatch,
) -> None:
    import src.lib.skill_paths as skill_paths

    def fail_import_time_vault_lookup(*_args, **_kwargs):
        raise AssertionError("legacy vault path lookup happened at import time")

    monkeypatch.setattr(skill_paths, "get_peer_data_dir", fail_import_time_vault_lookup)

    module_path = SHARED_SKILLS_ROOT / "routine-vault" / "scripts" / "claude_md_audit.py"
    module_name = "test_claude_md_audit_import"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)

    sys.modules.pop(module_name, None)
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(module_name, None)
