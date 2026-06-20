"""Tests for devops/scripts/ops/coverage_check.py — test coverage gap analysis."""
from __future__ import annotations

import importlib.util
from pathlib import Path


from src.lib.ops_protocol import OpsContext

_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "ops" / "coverage_check.py"
_SPEC = importlib.util.spec_from_file_location("coverage_check_under_test", _MODULE_PATH)
assert _SPEC and _SPEC.loader
_mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_mod)

_collect_test_stems = _mod._collect_test_stems
_find_source_modules = _mod._find_source_modules
_find_test_files = _mod._find_test_files
_generate_test_stub = _mod._generate_test_stub
_max_stubs_for_difficulty = _mod._max_stubs_for_difficulty
fix = _mod.fix
name = _mod.name
scan = _mod.scan


# ---------------------------------------------------------------------------
# _find_source_modules
# ---------------------------------------------------------------------------

class TestFindSourceModules:
    def test_finds_py_files_in_src(self, tmp_path):
        src = tmp_path / "src" / "lib"
        src.mkdir(parents=True)
        (src / "helper.py").write_text("# code")
        (src / "__init__.py").write_text("")
        (src / "test_helper.py").write_text("# test")
        modules = _find_source_modules(tmp_path, difficulty=0)
        stems = [m.stem for m in modules]
        assert "helper" in stems
        assert "__init__" not in stems
        assert "test_helper" not in stems

    def test_d0_only_searches_src(self, tmp_path):
        (tmp_path / "src").mkdir(parents=True, exist_ok=True)
        (tmp_path / "src" / "a.py").write_text("x")
        skills = tmp_path / "project-brain" / "capabilities" / "skills" / "x" / "scripts"
        skills.mkdir(parents=True)
        (skills / "b.py").write_text("x")
        modules = _find_source_modules(tmp_path, difficulty=0)
        stems = [m.stem for m in modules]
        assert "a" in stems
        assert "b" not in stems

    def test_d1_includes_skills(self, tmp_path):
        (tmp_path / "src").mkdir(parents=True, exist_ok=True)
        skills = tmp_path / "project-brain" / "capabilities" / "skills" / "x" / "scripts"
        skills.mkdir(parents=True)
        (skills / "b.py").write_text("x")
        modules = _find_source_modules(tmp_path, difficulty=1)
        stems = [m.stem for m in modules]
        assert "b" in stems

    def test_skips_pycache_and_node_modules(self, tmp_path):
        cache_dir = tmp_path / "src" / "__pycache__"
        cache_dir.mkdir(parents=True)
        (cache_dir / "cached.py").write_text("x")
        node_dir = tmp_path / "src" / "node_modules" / "pkg"
        node_dir.mkdir(parents=True)
        (node_dir / "mod.py").write_text("x")
        modules = _find_source_modules(tmp_path, difficulty=0)
        assert len(modules) == 0

    def test_skips_fixture_modules(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_mod, "get_all_client_skill_dirs", lambda _root: [tmp_path / "project-brain" / "capabilities" / "skills"])
        fixtures = tmp_path / "project-brain" / "capabilities" / "skills" / "daemon" / "augur" / "tests" / "fixtures" / "toy_loop"
        fixtures.mkdir(parents=True)
        (fixtures / "auto_mech.py").write_text("x")
        modules = _find_source_modules(tmp_path, difficulty=1)
        assert modules == []

    def test_skips_skill_test_support_modules(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_mod, "get_all_client_skill_dirs", lambda _root: [tmp_path / "project-brain" / "capabilities" / "skills"])
        tests = tmp_path / "project-brain" / "capabilities" / "skills" / "daemon" / "augur" / "tests"
        tests.mkdir(parents=True)
        (tests / "conftest.py").write_text("x")
        (tests / "_fixtures.py").write_text("x")
        modules = _find_source_modules(tmp_path, difficulty=1)
        assert modules == []


# ---------------------------------------------------------------------------
# _collect_test_stems / _find_test_files
# ---------------------------------------------------------------------------

class TestCollectTestStems:
    def test_collects_test_prefix(self, tmp_path):
        test_dir = tmp_path / "tests"
        test_dir.mkdir()
        (test_dir / "test_foo.py").write_text("")
        stems: set[str] = set()
        _collect_test_stems(test_dir, stems)
        assert "foo" in stems

    def test_collects_test_suffix(self, tmp_path):
        test_dir = tmp_path / "tests"
        test_dir.mkdir()
        (test_dir / "bar_test.py").write_text("")
        stems: set[str] = set()
        _collect_test_stems(test_dir, stems)
        assert "bar" in stems

    def test_nonexistent_dir_is_noop(self, tmp_path):
        stems: set[str] = set()
        _collect_test_stems(tmp_path / "nonexistent", stems)
        assert stems == set()


class TestFindTestFiles:
    def test_aggregates_project_and_plugin_tests(self, tmp_path):
        # Project-root tests
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_alpha.py").write_text("")
        # Skill-local tests
        skill_tests = tmp_path / "project-brain" / "capabilities" / "skills" / "x" / "augur" / "tests"
        skill_tests.mkdir(parents=True)
        (skill_tests / "test_beta.py").write_text("")
        stems = _find_test_files(tmp_path)
        assert "alpha" in stems
        assert "beta" in stems


# ---------------------------------------------------------------------------
# scan
# ---------------------------------------------------------------------------

class TestScan:
    def test_all_covered(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "foo.py").write_text("x")
        tests = tmp_path / "tests"
        tests.mkdir()
        (tests / "test_foo.py").write_text("x")
        ctx = OpsContext(project_root=tmp_path, difficulty=0)
        result = scan(ctx)
        assert result.severity == "info"
        assert result.issues == []

    def test_untested_module_reported(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "uncovered.py").write_text("x")
        (tmp_path / "tests").mkdir()
        ctx = OpsContext(project_root=tmp_path, difficulty=0)
        result = scan(ctx)
        assert result.severity == "warning"
        assert len(result.issues) == 1
        assert result.issues[0]["module"] == "uncovered"

    def test_private_src_module_covered_by_import_reference(self, tmp_path):
        module_dir = tmp_path / "src" / "lib" / "knowledge"
        module_dir.mkdir(parents=True)
        (module_dir / "_index.py").write_text("VALUE = 1")
        tests = tmp_path / "tests"
        tests.mkdir()
        (tests / "test_knowledge_index.py").write_text(
            "import importlib\n\n"
            "def test_imports_private_module():\n"
            '    assert importlib.import_module("src.lib.knowledge._index")\n'
        )

        ctx = OpsContext(project_root=tmp_path, difficulty=0)
        result = scan(ctx)

        assert result.issues == []

    def test_src_module_covered_only_by_skill_side_patch_reference(self, tmp_path, monkeypatch):
        """A src/ module exercised only via mock.patch in a skill-local suite counts.

        Regression for the false-negative where ``src/lib/knowledge/_iterative.py``
        was reported untested despite knowledge skill suites patching into it
        (``patch("src.lib.knowledge._iterative.time.sleep")``) without importing
        it at module scope.
        """
        module_dir = tmp_path / "src" / "lib" / "knowledge"
        module_dir.mkdir(parents=True)
        (module_dir / "_iterative.py").write_text("import time\n\ndef go():\n    time.sleep(0)\n")
        # No project-root tests/ coverage at all.
        (tmp_path / "tests").mkdir()
        # Coverage lives ONLY in a skill-local augur/tests/ suite, via patch string.
        skills_root = tmp_path / "project-brain" / "capabilities" / "skills"
        skill_tests = skills_root / "knowledge" / "augur" / "tests"
        skill_tests.mkdir(parents=True)
        (skill_tests / "test_search_hardening.py").write_text(
            "from unittest.mock import patch\n\n"
            "def test_iterative_backoff():\n"
            '    with patch("src.lib.knowledge._iterative.time.sleep"):\n'
            "        pass\n"
        )
        monkeypatch.setattr(_mod, "get_all_client_skill_dirs", lambda _root: [skills_root])

        ctx = OpsContext(project_root=tmp_path, difficulty=0)
        result = scan(ctx)

        assert result.issues == []

    def test_genuinely_untested_module_still_flagged(self, tmp_path, monkeypatch):
        """The patch-string credit must not credit modules nothing references."""
        src = tmp_path / "src" / "lib"
        src.mkdir(parents=True)
        (src / "orphan.py").write_text("x = 1\n")
        (tmp_path / "tests").mkdir()
        skills_root = tmp_path / "project-brain" / "capabilities" / "skills"
        skill_tests = skills_root / "knowledge" / "augur" / "tests"
        skill_tests.mkdir(parents=True)
        # Patches a DIFFERENT module — orphan must stay flagged.
        (skill_tests / "test_other.py").write_text(
            "from unittest.mock import patch\n\n"
            "def test_other():\n"
            '    with patch("src.lib.elsewhere.thing"):\n'
            "        pass\n"
        )
        monkeypatch.setattr(_mod, "get_all_client_skill_dirs", lambda _root: [skills_root])

        ctx = OpsContext(project_root=tmp_path, difficulty=0)
        result = scan(ctx)

        assert [i["module"] for i in result.issues] == ["orphan"]

    def test_private_skill_module_covered_by_import_reference(self, tmp_path, monkeypatch):
        skills_root = tmp_path / "project-brain" / "capabilities" / "skills"
        module_dir = skills_root / "daemon" / "scripts" / "mcp"
        module_dir.mkdir(parents=True)
        (module_dir / "_plugin_events.py").write_text("VALUE = 1")
        tests = skills_root / "daemon" / "augur" / "tests"
        tests.mkdir(parents=True)
        (tests / "test_plugin_events.py").write_text(
            "import importlib\n\n"
            "def test_imports_private_module():\n"
            '    assert importlib.import_module("skills.daemon.scripts.mcp._plugin_events")\n'
        )
        monkeypatch.setattr(_mod, "get_all_client_skill_dirs", lambda _root: [skills_root])

        ctx = OpsContext(project_root=tmp_path, difficulty=1)
        result = scan(ctx)

        assert result.issues == []


# ---------------------------------------------------------------------------
# fix
# ---------------------------------------------------------------------------

class TestFix:
    def test_dry_run(self, tmp_path):
        ctx = OpsContext(project_root=tmp_path, difficulty=1, dry_run=True)
        result = fix(ctx, [{"module": "x", "file": "src/x.py"}])
        assert result.success is True
        assert "Dry run" in result.summary

    def test_d0_report_only(self, tmp_path):
        """d0 produces report only — no stubs generated."""
        ctx = OpsContext(project_root=tmp_path, difficulty=0)
        issues = [{"module": "x", "file": "src/x.py"}]
        result = fix(ctx, issues)
        assert result.success is True
        assert "Report only" in result.summary
        assert result.fix_type == "report"
        # No test file should be created
        assert not (tmp_path / "tests" / "test_x.py").exists()

    def test_d1_generates_stubs(self, tmp_path):
        """d1 generates test stubs (up to 10)."""
        ctx = OpsContext(project_root=tmp_path, difficulty=1)
        issues = [{"module": "x", "file": "src/x.py"}]
        result = fix(ctx, issues)
        assert result.success is True
        test_file = tmp_path / "tests" / "test_x.py"
        assert test_file.exists()
        content = test_file.read_text()
        assert "def test_x_importable" in content

    def test_d1_caps_at_10(self, tmp_path):
        """d1 caps stub generation at 10 modules."""
        ctx = OpsContext(project_root=tmp_path, difficulty=1)
        issues = [{"module": f"mod{i}", "file": f"src/mod{i}.py"} for i in range(15)]
        result = fix(ctx, issues)
        assert result.success is True
        created_count = sum(1 for i in range(15) if (tmp_path / "tests" / f"test_mod{i}.py").exists())
        assert created_count == 10

    def test_d3_unlimited_stubs(self, tmp_path):
        """d3+ generates stubs for all stubbable modules."""
        ctx = OpsContext(project_root=tmp_path, difficulty=3)
        issues = [{"module": f"mod{i}", "file": f"src/mod{i}.py"} for i in range(30)]
        result = fix(ctx, issues)
        assert result.success is True
        created_count = sum(1 for i in range(30) if (tmp_path / "tests" / f"test_mod{i}.py").exists())
        assert created_count == 30

    def test_generates_report_for_remainder(self, tmp_path):
        """Modules that exceed the cap go to the gap report."""
        ctx = OpsContext(project_root=tmp_path, difficulty=1)
        issues = [{"module": f"mod{i}", "file": f"src/mod{i}.py"} for i in range(15)]
        fix(ctx, issues)
        report = tmp_path / "docs" / "generated" / "coverage-gaps-report.md"
        assert report.exists()
        content = report.read_text()
        # 5 deferred modules should be in the report
        assert "mod10" in content

    def test_skips_private_modules(self, tmp_path):
        """Private modules (leading underscore) are report-only."""
        ctx = OpsContext(project_root=tmp_path, difficulty=1)
        issues = [{"module": "_private", "file": "src/_private.py"}]
        fix(ctx, issues)
        assert not (tmp_path / "tests" / "test__private.py").exists()

    def test_generates_package_import_stub_for_skill_mcp_modules(self):
        content = _generate_test_stub(
            "tools_action",
            "project-brain/capabilities/skills/platform-admin/scripts/mcp/tools_action.py",
        )

        assert "importlib.util" in content
        assert "platform_admin_mcp_testpkg" in content
        assert (
            'PROJECT_ROOT / "project-brain" / "capabilities" / "skills" / "platform-admin" / "scripts"'
            in content
        )
        assert 'import_module(f"{package_name}.tools_action")' in content
        assert "submodule_search_locations" in content


# ---------------------------------------------------------------------------
# _max_stubs_for_difficulty
# ---------------------------------------------------------------------------

class TestMaxStubsForDifficulty:
    def test_d0_returns_zero(self):
        assert _max_stubs_for_difficulty(0) == 0

    def test_d1_returns_10(self):
        assert _max_stubs_for_difficulty(1) == 10

    def test_d2_returns_25(self):
        assert _max_stubs_for_difficulty(2) == 25

    def test_d3_returns_none(self):
        assert _max_stubs_for_difficulty(3) is None

    def test_d4_returns_none(self):
        assert _max_stubs_for_difficulty(4) is None


# ---------------------------------------------------------------------------
# Module attrs
# ---------------------------------------------------------------------------

def test_module_name():
    assert name == "auto-coverage-check"
