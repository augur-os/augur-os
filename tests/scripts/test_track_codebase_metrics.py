"""Tests for track_codebase_metrics.py script."""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from src.config.paths import get_project_root

sys.path.insert(0, str(get_project_root()))

spec_path = get_project_root() / ".github" / "scripts" / "track_codebase_metrics.py"


@pytest.fixture
def metrics_tracker():
    """Import track_codebase_metrics module."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("track_codebase_metrics", spec_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def project_tree(tmp_path):
    """Create a realistic project tree for testing."""
    # apps/dashboard files
    dashboard = tmp_path / "apps" / "dashboard"
    dashboard.mkdir(parents=True)
    (dashboard / "page.tsx").write_text("export default function Home() { return <div /> }\n")
    (dashboard / "layout.tsx").write_text("export default function Layout({ children }) { return children }\n")

    # src/config files
    config = tmp_path / "src" / "config"
    config.mkdir(parents=True)
    (config / "paths.py").write_text("def get_root():\n    return '/'\n")

    # src/lib files
    src_lib = tmp_path / "src/lib"
    src_lib.mkdir()
    (src_lib / "utils.py").write_text("def helper():\n    pass\n")

    # docs
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "README.md").write_text("# Docs\n\nSome documentation.\n")

    # tests
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_example.py").write_text("def test_thing():\n    assert True\n")
    ts_tests = tests / "dashboard"
    ts_tests.mkdir()
    (ts_tests / "App.test.tsx").write_text("test('renders', () => {})\n")

    # .github
    gh = tmp_path / ".github" / "scripts"
    gh.mkdir(parents=True)
    (gh / "ci_check.sh").write_text("#!/bin/bash\necho hello\n")

    # Root files
    (tmp_path / "Makefile").write_text("all:\n\t@echo done\n")
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")

    # Excluded dirs (should be ignored)
    node_modules = tmp_path / "apps" / "dashboard" / "node_modules"
    node_modules.mkdir(parents=True)
    (node_modules / "big_lib.js").write_text("x" * 10000)

    pycache = tmp_path / "src" / "config" / "__pycache__"
    pycache.mkdir()
    (pycache / "paths.cpython-311.pyc").write_bytes(b"\x00" * 100)

    # plugins (excluded from core metrics)
    plugins = tmp_path / "plugins" / "core" / "skills" / "dev" / "tests"
    plugins.mkdir(parents=True)
    (plugins / "test_dev.py").write_text("def test_dev(): pass\n")

    return tmp_path


class TestShouldExcludeDir:
    def test_excludes_known_dirs(self, metrics_tracker):
        for d in ['.git', 'node_modules', '__pycache__', '.next', 'plugins', 'data']:
            assert metrics_tracker.should_exclude_dir(d), f"Expected {d} to be excluded"

    def test_excludes_dotdirs(self, metrics_tracker):
        assert metrics_tracker.should_exclude_dir('.hidden')

    def test_allows_regular_dirs(self, metrics_tracker):
        assert not metrics_tracker.should_exclude_dir('src')
        assert not metrics_tracker.should_exclude_dir('lib')
        assert not metrics_tracker.should_exclude_dir('components')


class TestShouldExcludeFile:
    def test_excludes_generated_files(self, metrics_tracker):
        assert metrics_tracker.should_exclude_file(Path("generated-registry.ts"))
        assert metrics_tracker.should_exclude_file(Path("next-env.d.ts"))
        assert metrics_tracker.should_exclude_file(Path("lists.ts"))

    def test_excludes_binary_patterns(self, metrics_tracker):
        assert metrics_tracker.should_exclude_file(Path("module.pyc"))
        assert metrics_tracker.should_exclude_file(Path("package-lock.json"))
        assert metrics_tracker.should_exclude_file(Path(".DS_Store"))

    def test_allows_regular_files(self, metrics_tracker):
        assert not metrics_tracker.should_exclude_file(Path("page.tsx"))
        assert not metrics_tracker.should_exclude_file(Path("utils.py"))
        assert not metrics_tracker.should_exclude_file(Path("README.md"))


class TestCountLines:
    def test_counts_lines(self, metrics_tracker, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("line1\nline2\nline3\n")
        assert metrics_tracker.count_lines(f) == 3

    def test_empty_file(self, metrics_tracker, tmp_path):
        f = tmp_path / "empty.py"
        f.write_text("")
        assert metrics_tracker.count_lines(f) == 0

    def test_nonexistent_file(self, metrics_tracker, tmp_path):
        assert metrics_tracker.count_lines(tmp_path / "nope.py") == 0


class TestCollectMetrics:
    def test_collects_dashboard_metrics(self, metrics_tracker, project_tree):
        result = metrics_tracker.collect_metrics(project_tree, "apps/dashboard")
        assert result["files"] >= 2  # page.tsx, layout.tsx
        assert result["lines"] > 0

    def test_collects_root_files(self, metrics_tracker, project_tree):
        result = metrics_tracker.collect_metrics(project_tree, None)
        assert result["files"] >= 2  # Makefile, pyproject.toml
        assert result["folders"] == 0  # root files only

    def test_nonexistent_category(self, metrics_tracker, project_tree):
        result = metrics_tracker.collect_metrics(project_tree, "nonexistent/path")
        assert result == {"files": 0, "folders": 0, "lines": 0}

    def test_excludes_node_modules(self, metrics_tracker, project_tree):
        result = metrics_tracker.collect_metrics(project_tree, "apps/dashboard")
        # node_modules/big_lib.js should NOT be counted
        assert result["files"] == 2  # Only page.tsx and layout.tsx


class TestCountTestFiles:
    def test_counts_python_tests(self, metrics_tracker, project_tree):
        result = metrics_tracker.count_test_files(project_tree)
        assert result["python"] >= 1  # test_example.py

    def test_counts_typescript_tests(self, metrics_tracker, project_tree):
        result = metrics_tracker.count_test_files(project_tree)
        assert result["typescript"] >= 1  # App.test.tsx

    def test_total_is_sum(self, metrics_tracker, project_tree):
        result = metrics_tracker.count_test_files(project_tree)
        assert result["total"] == result["python"] + result["typescript"]


class TestCollectAllMetrics:
    def test_returns_complete_structure(self, metrics_tracker, project_tree):
        with patch.object(metrics_tracker, 'get_project_root', return_value=project_tree):
            result = metrics_tracker.collect_all_metrics(project_tree)

        assert "timestamp" in result
        assert "total" in result
        assert "categories" in result
        assert result["total"]["files"] > 0
        assert result["total"]["lines"] > 0

    def test_categories_match_config(self, metrics_tracker, project_tree):
        with patch.object(metrics_tracker, 'get_project_root', return_value=project_tree):
            result = metrics_tracker.collect_all_metrics(project_tree)

        for category_name in metrics_tracker.CATEGORIES:
            assert category_name in result["categories"]

    def test_includes_test_counts(self, metrics_tracker, project_tree):
        with patch.object(metrics_tracker, 'get_project_root', return_value=project_tree):
            result = metrics_tracker.collect_all_metrics(project_tree)

        assert "test_counts" in result
        assert result["test_counts"]["total"] >= 0


class TestSaveAndLoadMetrics:
    def test_save_creates_file(self, metrics_tracker, tmp_path):
        metrics_file = tmp_path / "metrics" / "codebase_metrics.json"
        data = {
            "timestamp": "2025-01-01T00:00:00Z",
            "total": {"files": 10, "folders": 5, "lines": 500},
            "categories": {},
        }
        metrics_tracker.save_metrics(data, metrics_file)
        assert metrics_file.exists()

    def test_load_returns_none_for_missing_file(self, metrics_tracker, tmp_path):
        result = metrics_tracker.load_previous_metrics(tmp_path / "nope.json")
        assert result is None

    def test_load_returns_none_for_invalid_json(self, metrics_tracker, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text("not json")
        result = metrics_tracker.load_previous_metrics(bad)
        assert result is None

    def test_round_trip(self, metrics_tracker, tmp_path):
        metrics_file = tmp_path / "metrics.json"
        data = {
            "timestamp": "2025-01-01T00:00:00Z",
            "total": {"files": 10, "folders": 5, "lines": 500},
            "categories": {"src/config": {"files": 2, "folders": 1, "lines": 100}},
        }
        metrics_tracker.save_metrics(data, metrics_file)
        loaded = metrics_tracker.load_previous_metrics(metrics_file)
        assert loaded["total"]["files"] == 10
        assert loaded["categories"]["src/config"]["lines"] == 100


class TestFormatDelta:
    def test_no_previous(self, metrics_tracker):
        assert metrics_tracker.format_delta(10, None) == ""

    def test_no_change(self, metrics_tracker):
        assert metrics_tracker.format_delta(10, 10) == ""

    def test_increase(self, metrics_tracker):
        result = metrics_tracker.format_delta(15, 10)
        assert "+5" in result

    def test_decrease(self, metrics_tracker):
        result = metrics_tracker.format_delta(8, 10)
        assert "-2" in result


class TestMain:
    def test_json_output(self, metrics_tracker, project_tree, capsys):
        with patch.object(metrics_tracker, 'get_project_root', return_value=project_tree):
            with patch('sys.argv', ['track_codebase_metrics.py', '--json']):
                ret = metrics_tracker.main()

        assert ret == 0
        output = json.loads(capsys.readouterr().out)
        assert "total" in output
        assert "categories" in output

    def test_save_creates_metrics_file(self, metrics_tracker, project_tree):
        runtime_dir = project_tree / "data" / "runtime"
        metrics_file = runtime_dir / "metrics" / "codebase_metrics.json"

        with patch.object(metrics_tracker, 'get_project_root', return_value=project_tree):
            with patch.object(metrics_tracker, 'get_runtime_dir', return_value=runtime_dir):
                with patch('sys.argv', ['track_codebase_metrics.py', '--save']):
                    ret = metrics_tracker.main()

        assert ret == 0
        assert metrics_file.exists()

    def test_table_output(self, metrics_tracker, project_tree, capsys):
        with patch.object(metrics_tracker, 'get_project_root', return_value=project_tree):
            with patch('sys.argv', ['track_codebase_metrics.py']):
                ret = metrics_tracker.main()

        assert ret == 0
        output = capsys.readouterr().out
        assert "CODEBASE METRICS" in output
        assert "TOTAL" in output
