"""Auto-generated importability test for security_scan."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def test_security_scan_importable():
    """Verify that security_scan can be imported without errors."""
    import importlib
    mod = importlib.import_module("skills.daemon.scripts.ops.security_scan")
    assert mod is not None


def test_security_scan_declares_windows_report_only_capabilities():
    import importlib
    mod = importlib.import_module("skills.daemon.scripts.ops.security_scan")
    assert mod.OPS_CAPABILITIES.platforms == ("cross_platform",)
    assert mod.OPS_CAPABILITIES.windows_fix_mode == "report_only"


def test_security_scan_skips_frontend_test_fixtures(tmp_path):
    import importlib

    from src.lib.ops_protocol import OpsContext

    mod = importlib.import_module("skills.daemon.scripts.ops.security_scan")
    fixture = (
        tmp_path
        / "apps"
        / "dashboard"
        / "features"
        / "pages"
        / "brain"
        / "ai"
        / "agents"
        / "control-state.test.ts"
    )
    fixture.parent.mkdir(parents=True, exist_ok=True)
    fixture.write_text("const provider = { api_key: 'anthropic-secret' };\n", encoding="utf-8")

    result = mod.scan(OpsContext(project_root=tmp_path, difficulty=2, dry_run=True))
    assert result.issues == []


def test_security_scan_honors_pragma_allowlist_secret(tmp_path):
    import importlib

    from src.lib.ops_protocol import OpsContext

    mod = importlib.import_module("skills.daemon.scripts.ops.security_scan")
    fixture = tmp_path / "manifest.py"
    fixture.write_text(
        'WORKSPACE_TOKEN = "__PROJECT_ROOT__"  # pragma: allowlist secret\n',
        encoding="utf-8",
    )

    result = mod.scan(OpsContext(project_root=tmp_path, difficulty=2, dry_run=True))
    assert result.issues == []


def test_security_scan_flags_token_without_pragma(tmp_path):
    import importlib

    from src.lib.ops_protocol import OpsContext

    mod = importlib.import_module("skills.daemon.scripts.ops.security_scan")
    fixture = tmp_path / "leaky.py"
    fixture.write_text(
        'WORKSPACE_TOKEN = "__PROJECT_ROOT__"\n',
        encoding="utf-8",
    )

    result = mod.scan(OpsContext(project_root=tmp_path, difficulty=2, dry_run=True))
    assert len(result.issues) == 1
    assert result.issues[0]["action"] == "potential-secret"


def test_security_scan_skips_sequential_alphabet_placeholder(tmp_path):
    """A sequential-alphabet sk- placeholder (e.g. inside another tool's own
    secret-pattern list) is not flagged, even though it has max entropy."""
    import importlib

    from src.lib.ops_protocol import OpsContext

    mod = importlib.import_module("skills.daemon.scripts.ops.security_scan")
    fixture = tmp_path / "guard.py"
    fixture.write_text(
        'FORBIDDEN_MARKER = "sk-abcdefghijklmnopqrstuvwxyz"\n',
        encoding="utf-8",
    )

    result = mod.scan(OpsContext(project_root=tmp_path, difficulty=2, dry_run=True))
    assert result.issues == []


def test_security_scan_flags_realistic_high_entropy_sk_token(tmp_path):
    """A realistic high-entropy sk- key is still flagged (no path exclusion)."""
    import importlib

    from src.lib.ops_protocol import OpsContext

    mod = importlib.import_module("skills.daemon.scripts.ops.security_scan")
    # Same filename a real leak might hide in; structure (not path) decides.
    fixture = tmp_path / "guard.py"
    fixture.write_text(
        'CONFIG_SECRET = "sk-Xa9Kf2Lp7Qz4Rb8Nc1Dt6Vy3Mw5Hg0Jo7"\n',
        encoding="utf-8",
    )

    result = mod.scan(OpsContext(project_root=tmp_path, difficulty=2, dry_run=True))
    assert len(result.issues) == 1
    assert result.issues[0]["action"] == "potential-secret"


def test_security_scan_skips_worktrees_dir(tmp_path):
    import importlib

    from src.lib.ops_protocol import OpsContext

    mod = importlib.import_module("skills.daemon.scripts.ops.security_scan")
    fixture = tmp_path / ".worktrees" / "feature-x" / "manifest.py"
    fixture.parent.mkdir(parents=True, exist_ok=True)
    fixture.write_text(
        'WORKSPACE_TOKEN = "__PROJECT_ROOT__"\n',
        encoding="utf-8",
    )

    result = mod.scan(OpsContext(project_root=tmp_path, difficulty=2, dry_run=True))
    assert result.issues == []


def test_security_scan_classifies_breaking_npm_fix_as_external_manual(tmp_path):
    import importlib
    import json

    from src.lib.ops_protocol import OpsContext

    mod = importlib.import_module("skills.daemon.scripts.ops.security_scan")
    dashboard_dir = tmp_path / "apps" / "dashboard"
    dashboard_dir.mkdir(parents=True)
    (dashboard_dir / "package.json").write_text("{}", encoding="utf-8")
    audit_payload = {
        "vulnerabilities": {
            "next": {
                "severity": "moderate",
                "fixAvailable": {
                    "name": "next",
                    "version": "9.3.3",
                    "isSemVerMajor": True,
                },
            }
        }
    }

    with patch.object(
        mod.subprocess,
        "run",
        return_value=SimpleNamespace(
            returncode=1,
            stdout=json.dumps(audit_payload),
            stderr="",
        ),
    ):
        result = mod.scan(OpsContext(project_root=tmp_path, difficulty=1, dry_run=True))

    assert len(result.issues) == 1
    issue = result.issues[0]
    assert issue["action"] == "npm-vulnerability"
    assert issue["kind"] == "external"
    assert issue["fixability"] == "manual"
    assert issue["root_cause_type"] == "external_dependency"


def test_security_scan_npm_audit_does_not_generate_package_lock(tmp_path):
    import importlib
    import json

    mod = importlib.import_module("skills.daemon.scripts.ops.security_scan")
    dashboard_dir = tmp_path / "apps" / "dashboard"
    dashboard_dir.mkdir(parents=True)
    (dashboard_dir / "package.json").write_text("{}", encoding="utf-8")

    with patch.object(
        mod.subprocess,
        "run",
        return_value=SimpleNamespace(
            returncode=1,
            stdout=json.dumps({"vulnerabilities": {}}),
            stderr="",
        ),
    ) as run:
        result = mod._scan_npm_audit(tmp_path)

    assert result == []
    assert "--package-lock=false" in run.call_args.args[0]


def test_security_scan_resolves_npm_executable_for_subprocess(tmp_path):
    import importlib
    import json

    mod = importlib.import_module("skills.daemon.scripts.ops.security_scan")
    dashboard_dir = tmp_path / "apps" / "dashboard"
    dashboard_dir.mkdir(parents=True)
    (dashboard_dir / "package.json").write_text("{}", encoding="utf-8")

    with (
        patch.object(mod, "_npm_command", return_value="C:/Program Files/nodejs/npm.cmd"),
        patch.object(
            mod.subprocess,
            "run",
            return_value=SimpleNamespace(
                returncode=1,
                stdout=json.dumps({"vulnerabilities": {}}),
                stderr="",
            ),
        ) as run,
    ):
        result = mod._scan_npm_audit(tmp_path)

    assert result == []
    assert run.call_args.args[0][0] == "C:/Program Files/nodejs/npm.cmd"
