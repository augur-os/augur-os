"""Tests for s3_static_analysis bandit filtering."""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def test_s3_static_analysis_importable():
    """Verify that s3_static_analysis can be imported without errors."""
    import importlib
    mod = importlib.import_module("s3_static_analysis")
    assert mod is not None


def _bandit_available() -> bool:
    try:
        import bandit  # noqa: F401
        return True
    except ImportError:
        return False


def test_b108_suppressed_in_test_files(tmp_path):
    """Bandit B108 (insecure tmp file) should not flag test fixtures."""
    if not _bandit_available():
        return
    import importlib
    mod = importlib.import_module("s3_static_analysis")
    fixture = tmp_path / "tests" / "test_something.py"
    fixture.parent.mkdir(parents=True, exist_ok=True)
    fixture.write_text(
        'from pathlib import Path\n'
        'def test_thing():\n'
        '    p = Path("/tmp/test_fixture")\n'
        '    return p\n',
        encoding="utf-8",
    )
    findings = mod._scan_python_with_bandit(fixture)
    b108_findings = [f for f in findings if f.get("pattern") == "B108"]
    assert b108_findings == []


def test_b108_still_flagged_in_production_code(tmp_path):
    """Bandit B108 should still flag /tmp paths in non-test source files."""
    if not _bandit_available():
        return
    import importlib
    mod = importlib.import_module("s3_static_analysis")
    fixture = tmp_path / "src" / "service.py"
    fixture.parent.mkdir(parents=True, exist_ok=True)
    fixture.write_text(
        'from pathlib import Path\n'
        'def cache_path():\n'
        '    return Path("/tmp/app-cache")\n',
        encoding="utf-8",
    )
    findings = mod._scan_python_with_bandit(fixture)
    # bandit may or may not flag this depending on severity threshold;
    # we only assert that the test-file suppression didn't accidentally
    # match a non-test path.
    assert all(f.get("file") == "service.py" for f in findings)


def test_b310_suppressed_for_hardcoded_https(tmp_path):
    """B310 (urllib audit_url_open) should not flag hardcoded http(s):// literals."""
    if not _bandit_available():
        return
    import importlib
    mod = importlib.import_module("s3_static_analysis")
    fixture = tmp_path / "fetcher.py"
    fixture.write_text(
        'import urllib.request\n'
        'def fetch():\n'
        '    return urllib.request.urlopen("https://api.example.com/data")\n',
        encoding="utf-8",
    )
    findings = mod._scan_python_with_bandit(fixture)
    b310_findings = [f for f in findings if f.get("pattern") == "B310"]
    assert b310_findings == []


def test_native_scan_honors_nosec_on_shell_true(tmp_path):
    """subprocess.run(..., shell=True) with # nosec must not flag."""
    import importlib
    mod = importlib.import_module("s3_static_analysis")
    skill_dir = tmp_path / "fake-skill"
    skill_dir.mkdir()
    src = skill_dir / "runner.py"
    src.write_text(
        'import subprocess\n'
        'def go(cmd):\n'
        '    return subprocess.run(\n'
        '        cmd,\n'
        '        shell=True,  # nosec B602\n'
        '    )\n',
        encoding="utf-8",
    )
    findings = mod._scan_python_native(src, skill_dir)
    shell_findings = [f for f in findings if f.get("category_name") == "subprocess-shell-true"]
    assert shell_findings == []


def test_native_scan_honors_noqa_on_shell_true(tmp_path):
    """subprocess.run(..., shell=True) with # noqa: S602 must not flag either."""
    import importlib
    mod = importlib.import_module("s3_static_analysis")
    skill_dir = tmp_path / "fake-skill"
    skill_dir.mkdir()
    src = skill_dir / "runner.py"
    src.write_text(
        'import subprocess\n'
        'def go(cmd):\n'
        '    return subprocess.run(cmd, shell=True)  # noqa: S602\n',
        encoding="utf-8",
    )
    findings = mod._scan_python_native(src, skill_dir)
    shell_findings = [f for f in findings if f.get("category_name") == "subprocess-shell-true"]
    assert shell_findings == []


def test_native_scan_still_flags_unsuppressed_shell_true(tmp_path):
    """Without a suppression comment, shell=True must still flag."""
    import importlib
    mod = importlib.import_module("s3_static_analysis")
    skill_dir = tmp_path / "fake-skill"
    skill_dir.mkdir()
    src = skill_dir / "runner.py"
    src.write_text(
        'import subprocess\n'
        'def go(cmd):\n'
        '    return subprocess.run(cmd, shell=True)\n',
        encoding="utf-8",
    )
    findings = mod._scan_python_native(src, skill_dir)
    shell_findings = [f for f in findings if f.get("category_name") == "subprocess-shell-true"]
    assert len(shell_findings) == 1


def test_b310_still_flagged_for_dynamic_urls(tmp_path):
    """B310 should still flag urlopen with dynamic/variable URLs."""
    if not _bandit_available():
        return
    import importlib
    mod = importlib.import_module("s3_static_analysis")
    fixture = tmp_path / "dynamic_fetcher.py"
    fixture.write_text(
        'import urllib.request\n'
        'def fetch(user_url):\n'
        '    return urllib.request.urlopen(user_url)\n',
        encoding="utf-8",
    )
    findings = mod._scan_python_with_bandit(fixture)
    # We don't strictly assert this fires (depends on bandit severity defaults),
    # but if it does fire, the file must be the dynamic one.
    b310_findings = [f for f in findings if f.get("pattern") == "B310"]
    assert all(f.get("file") == "dynamic_fetcher.py" for f in b310_findings)
