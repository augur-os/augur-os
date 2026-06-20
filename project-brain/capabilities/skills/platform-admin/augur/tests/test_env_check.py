"""Auto-generated importability test for env_check."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

from src.lib.ops_protocol import OpsContext

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts" / "ops"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def test_env_check_importable():
    """Verify that env_check can be imported without errors."""
    mod = importlib.import_module("skills.platform-admin.scripts.ops.env_check")
    assert mod is not None


def test_env_check_ignores_internal_runtime_vars(tmp_path):
    mod = importlib.import_module("skills.platform-admin.scripts.ops.env_check")

    dashboard = tmp_path / "apps" / "dashboard"
    dashboard.mkdir(parents=True)
    (dashboard / "runtime.ts").write_text(
        "\n".join(
            [
                "process.env.JEST_WORKER_ID;",
                "process.env.AUGUR_MCP_CLIENT_ID;",
                "process.env.PATHEXT;",
                "process.env.PYTHONPATH;",
                "process.env.PYTHONIOENCODING;",
                "process.env.PYTHONUTF8;",
                "process.env.USERPROFILE;",
                "process.env.XDG_STATE_HOME;",
            ]
        ),
        encoding="utf-8",
    )

    result = mod.scan(OpsContext(project_root=tmp_path, difficulty=0))
    details = [issue["detail"] for issue in result.issues]

    assert details == []


def test_env_check_respects_env_example_for_user_config(tmp_path):
    mod = importlib.import_module("skills.platform-admin.scripts.ops.env_check")

    dashboard = tmp_path / "apps" / "dashboard"
    dashboard.mkdir(parents=True)
    (tmp_path / ".env.example").write_text(
        "\n".join(
            [
                "AUGUR_ROOT=/path/to/repo",
                "AUGUR_PYTHON=python3",
                "NEXT_PUBLIC_BASE_URL=http://localhost:3000",
            ]
        ),
        encoding="utf-8",
    )
    (dashboard / "config.ts").write_text(
        "\n".join(
            [
                "process.env.AUGUR_ROOT;",
                "process.env.AUGUR_PYTHON;",
                "process.env.NEXT_PUBLIC_BASE_URL;",
                "process.env.UNDOCUMENTED_FLAG;",
            ]
        ),
        encoding="utf-8",
    )

    result = mod.scan(OpsContext(project_root=tmp_path, difficulty=0))
    details = [issue["detail"] for issue in result.issues]

    assert any("UNDOCUMENTED_FLAG" in detail for detail in details)
    assert all("AUGUR_ROOT" not in detail for detail in details)
    assert all("AUGUR_PYTHON" not in detail for detail in details)
    assert all("NEXT_PUBLIC_BASE_URL" not in detail for detail in details)


def test_env_check_scans_shared_vault_skill_python(tmp_path):
    """Difficulty 1 Python scan should include project-brain skills."""
    mod = importlib.import_module("skills.platform-admin.scripts.ops.env_check")
    script = tmp_path / "project-brain" / "capabilities" / "skills" / "demo" / "scripts" / "tool.py"
    script.parent.mkdir(parents=True)
    script.write_text("import os\nTOKEN = os.environ['MISSING_SHARED_SKILL_ENV']\n", encoding="utf-8")

    result = mod.scan(OpsContext(project_root=tmp_path, difficulty=1))

    assert any(
        issue["path"].replace("\\", "/") == "project-brain/capabilities/skills/demo/scripts/tool.py"
        and "MISSING_SHARED_SKILL_ENV" in issue["detail"]
        for issue in result.issues
    )


def test_env_check_ignores_test_fixture_env_vars(tmp_path):
    """Test-only env vars should not require production .env documentation."""
    mod = importlib.import_module("skills.platform-admin.scripts.ops.env_check")
    test_file = tmp_path / "project-brain" / "capabilities" / "skills" / "demo" / "augur" / "tests" / "test_tool.py"
    test_file.parent.mkdir(parents=True)
    test_file.write_text("import os\nTOKEN = os.environ['TEST_ONLY_FIXTURE_TOKEN']\n", encoding="utf-8")

    result = mod.scan(OpsContext(project_root=tmp_path, difficulty=1))

    assert result.issues == []
