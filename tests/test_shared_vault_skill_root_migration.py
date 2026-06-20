from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]


def load_guard_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "check_skill_root_migration",
        ROOT / "scripts" / "check_skill_root_migration.py",
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


GUARD = load_guard_module()


def run_guard(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python", "scripts/check_skill_root_migration.py", *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_guard_inventory_outputs_root_skills_before_migration():
    result = run_guard("--inventory")
    assert result.returncode == 0
    assert "root_skill_dirs:" in result.stdout
    assert "shared_vault_skill_dirs:" in result.stdout


def test_guard_final_contract_passes_after_repo_root_skills_removed():
    result = run_guard("--final-contract")
    assert result.returncode == 0
    assert "skill root migration contract passed" in result.stdout


def test_guard_test_contract_passes_with_allowlisted_residue():
    result = run_guard("--test-contract")
    assert result.returncode == 0
    assert "test skill root migration contract passed" in result.stdout


def test_test_contract_reports_unexpected_test_root_reference(tmp_path, monkeypatch, capsys):
    test = tmp_path / "tests" / "test_bad.py"
    test.parent.mkdir(parents=True)
    test.write_text('skill_root = repo_root / "skills"\n', encoding="utf-8")

    monkeypatch.setattr(GUARD, "ROOT", tmp_path)
    monkeypatch.setattr(GUARD, "ALLOWED_TEST_RESIDUE_FILES", set())
    monkeypatch.setattr(GUARD, "_iter_test_scan_files", lambda: [test])

    assert GUARD.test_contract() == 1
    assert "test skill root migration contract failed" in capsys.readouterr().out


def test_scan_globs_include_github_yaml_workflows():
    assert ".github/**/*.yaml" in GUARD.SCAN_GLOBS
    assert ".github/**/*.yml" in GUARD.SCAN_GLOBS


def test_scan_globs_include_shell_files():
    assert "scripts/**/*.sh" in GUARD.SCAN_GLOBS
    assert "scripts/**/*.bash" in GUARD.SCAN_GLOBS
    assert "scripts/**/*.zsh" in GUARD.SCAN_GLOBS
    assert ".github/**/*.sh" in GUARD.SCAN_GLOBS
    assert ".github/**/*.bash" in GUARD.SCAN_GLOBS
    assert ".github/**/*.zsh" in GUARD.SCAN_GLOBS
    assert "src/**/*.sh" in GUARD.SCAN_GLOBS
    assert "src/**/*.bash" in GUARD.SCAN_GLOBS
    assert "src/**/*.zsh" in GUARD.SCAN_GLOBS
    assert "apps/dashboard/**/*.sh" in GUARD.SCAN_GLOBS
    assert "apps/dashboard/**/*.bash" in GUARD.SCAN_GLOBS
    assert "apps/dashboard/**/*.zsh" in GUARD.SCAN_GLOBS


def test_scan_globs_include_shared_vault_skill_runtime_files():
    assert "project-brain/capabilities/skills/**/*.py" in GUARD.SCAN_GLOBS


def test_iter_scan_files_excludes_shared_vault_skill_tests(tmp_path, monkeypatch):
    runtime_file = tmp_path / "project-brain" / "capabilities" / "skills" / "demo" / "scripts" / "ops.py"
    runtime_file.parent.mkdir(parents=True)
    runtime_file.write_text("ok = True\n", encoding="utf-8")
    test_file = tmp_path / "project-brain" / "capabilities" / "skills" / "demo" / "augur" / "tests" / "test_ops.py"
    test_file.parent.mkdir(parents=True)
    test_file.write_text('skill_root = PROJECT_ROOT / "skills"\n', encoding="utf-8")

    monkeypatch.setattr(GUARD, "ROOT", tmp_path)
    monkeypatch.setattr(GUARD, "SCAN_GLOBS", ["project-brain/capabilities/skills/**/*.py"])

    assert GUARD._iter_scan_files() == [runtime_file]


def test_scanner_detects_get_project_root_skill_reference(tmp_path):
    source = tmp_path / "source.py"
    source.write_text('skill_root = get_project_root() / "skills"\n', encoding="utf-8")

    issues = GUARD._scan_file_for_issues(source, "src/source.py")

    assert any("forbidden root-skill repo-root helper" in issue for issue in issues)


def test_scanner_detects_parenthesized_get_project_root_glob(tmp_path):
    source = tmp_path / "source.py"
    source.write_text('for path in (get_project_root() / "skills").glob("*"):\n    pass\n', encoding="utf-8")

    issues = GUARD._scan_file_for_issues(source, "src/source.py")

    assert any("forbidden root-skill repo-root helper" in issue for issue in issues)


def test_scanner_detects_root_constant_skill_reference(tmp_path):
    source = tmp_path / "source.py"
    source.write_text('skill_root = ROOT / "skills"\n', encoding="utf-8")

    issues = GUARD._scan_file_for_issues(source, "src/source.py")

    assert any("forbidden root-skill" in issue for issue in issues)


def test_scanner_detects_project_root_constant_skill_reference(tmp_path):
    source = tmp_path / "source.py"
    source.write_text('skill_root = PROJECT_ROOT / "skills"\n', encoding="utf-8")

    issues = GUARD._scan_file_for_issues(source, "src/source.py")

    assert any("forbidden root-skill repo-root variable" in issue for issue in issues)


def test_scanner_detects_project_root_variable_skill_reference(tmp_path):
    source = tmp_path / "source.py"
    source.write_text('skill_root = project_root / "skills"\n', encoding="utf-8")

    issues = GUARD._scan_file_for_issues(source, "src/source.py")

    assert any("forbidden root-skill repo-root variable" in issue for issue in issues)


def test_scanner_detects_repo_root_variable_skill_reference(tmp_path):
    source = tmp_path / "source.py"
    source.write_text('skill_root = repo_root / "skills"\n', encoding="utf-8")

    issues = GUARD._scan_file_for_issues(source, "src/source.py")

    assert any("forbidden root-skill repo-root variable" in issue for issue in issues)


def test_scanner_detects_file_parent_skill_reference(tmp_path):
    source = tmp_path / "source.py"
    source.write_text('skill_root = Path(__file__).resolve().parents[5] / "skills"\n', encoding="utf-8")

    issues = GUARD._scan_file_for_issues(source, "src/source.py")

    assert any("forbidden root-skill file-parent helper" in issue for issue in issues)


def test_scanner_detects_project_root_attribute_skill_reference(tmp_path):
    source = tmp_path / "source.py"
    source.write_text('skills_dir = self._project_root / "skills"\n', encoding="utf-8")

    issues = GUARD._scan_file_for_issues(source, "src/source.py")

    assert any("forbidden root-skill repo-root attribute" in issue for issue in issues)


def test_scanner_detects_root_variable_skill_reference(tmp_path):
    source = tmp_path / "source.py"
    source.write_text('skill_root = root / "skills"\n', encoding="utf-8")

    issues = GUARD._scan_file_for_issues(source, "src/source.py")

    assert any("forbidden root-skill repo-root variable" in issue for issue in issues)


def test_scanner_detects_path_cwd_skill_reference(tmp_path):
    source = tmp_path / "source.py"
    source.write_text('skill_root = Path.cwd() / "skills"\n', encoding="utf-8")

    issues = GUARD._scan_file_for_issues(source, "src/source.py")

    assert any("forbidden root-skill cwd root helper" in issue for issue in issues)


def test_scanner_detects_standalone_path_skills_reference(tmp_path):
    source = tmp_path / "source.py"
    source.write_text('skill_root = Path("skills")\n', encoding="utf-8")

    issues = GUARD._scan_file_for_issues(source, "src/source.py")

    assert any("forbidden root-skill root-relative Path" in issue for issue in issues)


def test_scanner_detects_yaml_shell_python_skills_reference(tmp_path):
    workflow = tmp_path / "workflow.yml"
    workflow.write_text("steps:\n  - run: python skills/example/script.py\n", encoding="utf-8")

    issues = GUARD._scan_file_for_issues(workflow, ".github/workflows/example.yml")

    assert any("forbidden root-skill root-relative shell command" in issue for issue in issues)


def test_scanner_detects_python_dot_slash_skills_reference(tmp_path):
    workflow = tmp_path / "workflow.yml"
    workflow.write_text("steps:\n  - run: python ./skills/example/script.py\n", encoding="utf-8")

    issues = GUARD._scan_file_for_issues(workflow, ".github/workflows/example.yml")

    assert any("forbidden root-skill root-relative shell command" in issue for issue in issues)


def test_scanner_allows_private_vault_skill_reference(tmp_path):
    source = tmp_path / "source.py"
    source.write_text('skill_root = get_private_vault_dir() / "skills"\n', encoding="utf-8")

    assert GUARD._scan_file_for_issues(source, "src/source.py") == []


def test_scanner_allows_configured_vault_skill_reference(tmp_path):
    source = tmp_path / "source.py"
    source.write_text('skill_root = get_configured_vault_dir(root) / "skills"\n', encoding="utf-8")

    assert GUARD._scan_file_for_issues(source, "src/source.py") == []


def test_scanner_allows_vault_root_skill_reference(tmp_path):
    source = tmp_path / "source.py"
    source.write_text('skill_root = vault_root / "skills"\n', encoding="utf-8")

    assert GUARD._scan_file_for_issues(source, "src/source.py") == []


def test_scanner_allows_private_vault_root_skill_reference(tmp_path):
    source = tmp_path / "source.py"
    source.write_text('skill_root = private_vault_root / "skills"\n', encoding="utf-8")

    assert GUARD._scan_file_for_issues(source, "src/source.py") == []


def test_scanner_allows_shared_vault_root_skill_reference(tmp_path):
    source = tmp_path / "source.py"
    source.write_text('skill_root = shared_vault_root / "capabilities" / "skills"\n', encoding="utf-8")

    assert GUARD._scan_file_for_issues(source, "src/source.py") == []


def test_scanner_allows_attribute_named_root_skill_reference(tmp_path):
    source = tmp_path / "source.py"
    source.write_text('skill_root = settings.root / "skills"\n', encoding="utf-8")

    assert GUARD._scan_file_for_issues(source, "src/source.py") == []


def test_scanner_allows_plugin_cache_skill_reference(tmp_path):
    source = tmp_path / "source.py"
    source.write_text('skill_root = cache_dir / publisher / plugin / version / "skills"\n', encoding="utf-8")

    assert GUARD._scan_file_for_issues(source, "src/source.py") == []


def test_scanner_allows_generated_client_skill_roots(tmp_path):
    source = tmp_path / "source.py"
    source.write_text(
        "\n".join(
            [
                'gemini = project_root / ".gemini" / "skills"',
                'codex = project_root / ".codex" / "skills"',
                'opencode = project_root / ".opencode" / "skills"',
            ]
        ),
        encoding="utf-8",
    )

    assert GUARD._scan_file_for_issues(source, "src/source.py") == []


def test_scanner_allows_generated_client_path_constructor_root(tmp_path):
    source = tmp_path / "source.py"
    source.write_text('gemini = Path(".gemini") / Path("skills")\n', encoding="utf-8")

    assert GUARD._scan_file_for_issues(source, "src/source.py") == []


def test_scanner_allows_shared_vault_skill_literal(tmp_path):
    source = tmp_path / "source.py"
    source.write_text('docs = "project-brain/capabilities/skills contains shared skill data"\n', encoding="utf-8")

    assert GUARD._scan_file_for_issues(source, "src/source.py") == []


def test_final_contract_ignores_allowed_guard_references(tmp_path, monkeypatch):
    script = tmp_path / "scripts" / "check_skill_root_migration.py"
    script.parent.mkdir(parents=True)
    script.write_text('skill_root = get_project_root() / "skills"\n', encoding="utf-8")
    test = tmp_path / "tests" / "test_shared_vault_skill_root_migration.py"
    test.parent.mkdir(parents=True)
    test.write_text('skill_root = Path.cwd() / "skills"\n', encoding="utf-8")

    monkeypatch.setattr(GUARD, "ROOT", tmp_path)
    monkeypatch.setattr(GUARD, "ROOT_SKILLS", tmp_path / "missing-skills")
    monkeypatch.setattr(GUARD, "_iter_scan_files", lambda: [script, test])

    assert GUARD.final_contract() == 0


def test_scanner_handles_non_utf_input_without_crashing(tmp_path):
    source = tmp_path / "source.py"
    source.write_bytes(b"\xff\xfe\x00python skills/example/script.py\n")

    issues = GUARD._scan_file_for_issues(source, "src/source.py")

    assert any("forbidden root-skill root-relative shell command" in issue for issue in issues)


def test_scanner_reports_read_errors_without_crashing(tmp_path):
    missing = tmp_path / "missing.py"

    issues = GUARD._scan_file_for_issues(missing, "src/missing.py")

    assert len(issues) == 1
    assert "could not read file" in issues[0]


def test_final_contract_reports_read_errors(tmp_path, monkeypatch, capsys):
    missing = tmp_path / "src" / "missing.py"

    monkeypatch.setattr(GUARD, "ROOT", tmp_path)
    monkeypatch.setattr(GUARD, "ROOT_SKILLS", tmp_path / "missing-skills")
    monkeypatch.setattr(GUARD, "_iter_scan_files", lambda: [missing])

    assert GUARD.final_contract() == 1
    assert "could not read file" in capsys.readouterr().out
