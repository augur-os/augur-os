"""Tests for coverage_tracker.py script."""

import json
import sys
from unittest.mock import patch

import pytest

from src.config.paths import get_project_root

# Add project root to path
sys.path.insert(0, str(get_project_root()))


# Import the script as a module
spec_path = get_project_root() / ".github" / "scripts" / "coverage_tracker.py"


@pytest.fixture
def coverage_tracker():
    """Import coverage_tracker module."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("coverage_tracker", spec_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def tmp_root(tmp_path):
    """Create a temporary project root with test structure."""
    # Create test files to count
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_foo.py").write_text("# test file")
    (tests_dir / "test_bar.py").write_text("# test file")

    plugins_dir = tmp_path / "plugins" / "core" / "skills" / "dev" / "tests"
    plugins_dir.mkdir(parents=True)
    (plugins_dir / "test_core.py").write_text("# test file")

    ts_tests_dir = tmp_path / "tests" / "dashboard"
    ts_tests_dir.mkdir(parents=True)
    (ts_tests_dir / "App.test.tsx").write_text("// test")
    (ts_tests_dir / "utils.test.ts").write_text("// test")

    return tmp_path


@pytest.fixture
def jest_coverage_data():
    """Sample Jest coverage-summary.json data."""
    return {
        "total": {
            "statements": {"total": 100, "covered": 80, "skipped": 0, "pct": 80.0},
            "branches": {"total": 50, "covered": 30, "skipped": 0, "pct": 60.0},
            "functions": {"total": 40, "covered": 35, "skipped": 0, "pct": 87.5},
            "lines": {"total": 100, "covered": 75, "skipped": 0, "pct": 75.0},
        }
    }


@pytest.fixture
def python_coverage_data():
    """Sample coverage.json data."""
    return {
        "totals": {
            "percent_covered": 72.5,
            "covered_lines": 290,
            "missing_lines": 110,
            "num_statements": 400,
        }
    }


class TestReadJestCoverage:
    def test_reads_from_runtime_path(self, coverage_tracker, tmp_root, jest_coverage_data):
        coverage_dir = tmp_root / "data" / "runtime" / "coverage"
        coverage_dir.mkdir(parents=True)
        (coverage_dir / "coverage-summary.json").write_text(json.dumps(jest_coverage_data))

        result = coverage_tracker.read_jest_coverage(tmp_root)
        assert result is not None
        assert result["statements"] == 80.0
        assert result["branches"] == 60.0
        assert result["functions"] == 87.5
        assert result["lines"] == 75.0

    def test_reads_from_dashboard_fallback(self, coverage_tracker, tmp_root, jest_coverage_data):
        dashboard_cov = tmp_root / "apps" / "dashboard" / "coverage"
        dashboard_cov.mkdir(parents=True)
        (dashboard_cov / "coverage-summary.json").write_text(json.dumps(jest_coverage_data))

        result = coverage_tracker.read_jest_coverage(tmp_root)
        assert result is not None
        assert result["lines"] == 75.0

    def test_returns_none_when_no_file(self, coverage_tracker, tmp_root):
        result = coverage_tracker.read_jest_coverage(tmp_root)
        assert result is None

    def test_returns_none_on_invalid_json(self, coverage_tracker, tmp_root):
        coverage_dir = tmp_root / "data" / "runtime" / "coverage"
        coverage_dir.mkdir(parents=True)
        (coverage_dir / "coverage-summary.json").write_text("not json")

        result = coverage_tracker.read_jest_coverage(tmp_root)
        assert result is None


class TestReadPythonCoverage:
    def test_reads_coverage_json(self, coverage_tracker, tmp_root, python_coverage_data):
        (tmp_root / "coverage.json").write_text(json.dumps(python_coverage_data))

        result = coverage_tracker.read_python_coverage(tmp_root)
        assert result is not None
        assert result["statements"] == 72.5
        assert result["covered"] == 290
        assert result["missing"] == 110

    def test_returns_none_when_no_file(self, coverage_tracker, tmp_root):
        result = coverage_tracker.read_python_coverage(tmp_root)
        assert result is None

    def test_returns_none_on_invalid_json(self, coverage_tracker, tmp_root):
        (tmp_root / "coverage.json").write_text("{{{")
        result = coverage_tracker.read_python_coverage(tmp_root)
        assert result is None


class TestCountTestFiles:
    def test_counts_python_and_typescript(self, coverage_tracker, tmp_root):
        result = coverage_tracker.count_test_files(tmp_root)
        assert result["python"] >= 2  # test_foo.py, test_bar.py at minimum
        assert result["typescript"] >= 2  # App.test.tsx, utils.test.ts
        assert result["total"] == result["python"] + result["typescript"]

    def test_empty_directory(self, coverage_tracker, tmp_path):
        result = coverage_tracker.count_test_files(tmp_path)
        assert result["python"] == 0
        assert result["typescript"] == 0
        assert result["total"] == 0


class TestCollectCoverageSnapshot:
    def test_returns_timestamp_and_structure(self, coverage_tracker, tmp_root):
        snapshot = coverage_tracker.collect_coverage_snapshot(tmp_root)
        assert "timestamp" in snapshot
        assert "jest" in snapshot
        assert "python" in snapshot
        assert "test_counts" in snapshot
        assert snapshot["timestamp"].endswith("Z")

    def test_handles_no_coverage_data(self, coverage_tracker, tmp_root):
        snapshot = coverage_tracker.collect_coverage_snapshot(tmp_root)
        assert snapshot["jest"] is None
        assert snapshot["python"] is None
        assert snapshot["test_counts"]["total"] > 0


class TestHistory:
    def test_load_nonexistent_file(self, coverage_tracker, tmp_path):
        result = coverage_tracker.load_history(tmp_path / "nope.json")
        assert result == []

    def test_load_invalid_json(self, coverage_tracker, tmp_path):
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("not json")
        result = coverage_tracker.load_history(bad_file)
        assert result == []

    def test_load_valid_history(self, coverage_tracker, tmp_path):
        history_file = tmp_path / "history.json"
        entries = [
            {
                "timestamp": "2025-01-01T00:00:00Z",
                "jest": None,
                "python": None,
                "test_counts": {"total": 5},
            }
        ]
        history_file.write_text(json.dumps(entries))

        result = coverage_tracker.load_history(history_file)
        assert len(result) == 1
        assert result[0]["test_counts"]["total"] == 5

    def test_save_creates_parent_dirs(self, coverage_tracker, tmp_path):
        history_file = tmp_path / "deep" / "nested" / "history.json"
        entries = [{"timestamp": "2025-01-01T00:00:00Z"}]
        coverage_tracker.save_history(entries, history_file)
        assert history_file.exists()

    def test_save_truncates_to_90_entries(self, coverage_tracker, tmp_path):
        history_file = tmp_path / "history.json"
        entries = [{"timestamp": f"2025-01-{i:02d}T00:00:00Z"} for i in range(1, 32)] * 4  # 124 entries
        coverage_tracker.save_history(entries, history_file)

        loaded = json.loads(history_file.read_text())
        assert len(loaded) == 90


class TestCalculateTrend:
    def test_too_few_entries(self, coverage_tracker):
        history = [{"jest": {"lines": 50}}]
        assert coverage_tracker.calculate_trend(history, ["jest", "lines"]) == "stable"

    def test_stable_trend(self, coverage_tracker):
        history = [
            {"jest": {"lines": 50.0}},
            {"jest": {"lines": 50.2}},
            {"jest": {"lines": 50.1}},
            {"jest": {"lines": 50.3}},
        ]
        assert coverage_tracker.calculate_trend(history, ["jest", "lines"]) == "stable"

    def test_upward_trend(self, coverage_tracker):
        history = [
            {"jest": {"lines": 50.0}},
            {"jest": {"lines": 51.0}},
            {"jest": {"lines": 55.0}},
            {"jest": {"lines": 58.0}},
        ]
        assert coverage_tracker.calculate_trend(history, ["jest", "lines"]) == "up"

    def test_downward_trend(self, coverage_tracker):
        history = [
            {"jest": {"lines": 80.0}},
            {"jest": {"lines": 78.0}},
            {"jest": {"lines": 72.0}},
            {"jest": {"lines": 70.0}},
        ]
        assert coverage_tracker.calculate_trend(history, ["jest", "lines"]) == "down"

    def test_handles_none_values(self, coverage_tracker):
        history = [
            {"jest": None},
            {"jest": None},
            {"jest": {"lines": 50.0}},
        ]
        assert coverage_tracker.calculate_trend(history, ["jest", "lines"]) == "stable"

    def test_handles_missing_keys(self, coverage_tracker):
        history = [
            {"python": {"statements": 50}},
            {"python": {"statements": 55}},
        ]
        assert coverage_tracker.calculate_trend(history, ["jest", "lines"]) == "stable"


class TestMain:
    def test_main_json_output(self, coverage_tracker, tmp_root, capsys):
        with patch.object(coverage_tracker, "get_project_root", return_value=tmp_root):
            with patch.dict("os.environ", {"AUGUR_ROOT": str(tmp_root)}):
                with patch("sys.argv", ["coverage_tracker.py", "--json"]):
                    ret = coverage_tracker.main()

        assert ret == 0
        output = json.loads(capsys.readouterr().out)
        assert "current" in output
        assert "trends" in output

    def test_main_save_mode(self, coverage_tracker, tmp_root):
        history_dir = tmp_root / "runtime" / "metrics"
        history_dir.mkdir(parents=True, exist_ok=True)

        with patch.object(coverage_tracker, "get_project_root", return_value=tmp_root):
            with patch.dict("os.environ", {"AUGUR_ROOT": str(tmp_root)}):
                with patch("sys.argv", ["coverage_tracker.py", "--save"]):
                    ret = coverage_tracker.main()

        assert ret == 0
        history_file = history_dir / "coverage_history.json"
        assert history_file.exists()
        data = json.loads(history_file.read_text())
        assert len(data) == 1
        assert "timestamp" in data[0]
