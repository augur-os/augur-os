"""
Tests for Daemon skill - Nightly Executor, Service Healer, Check Expirations.

Tests core scheduling and automation logic:
- ROI scoring for task prioritization
- Time window checks for nightly execution
- Task candidate selection and claiming
- Duration parsing for data expiration
- Service healer plist path detection
"""
# TODO_CLEANUP: This file is 928 lines — consider splitting into smaller modules

from datetime import datetime, time, timedelta
import importlib
import importlib.util
from pathlib import Path
import sys
from unittest.mock import MagicMock, patch

REPO_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
SHARED_VAULT_ROOT = REPO_ROOT / "project-brain"
PLATFORM_ADMIN_SCRIPTS_DIR = SHARED_VAULT_ROOT / "capabilities" / "skills" / "platform-admin" / "scripts"
for _path in (REPO_ROOT, SHARED_VAULT_ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

if str(PLATFORM_ADMIN_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(PLATFORM_ADMIN_SCRIPTS_DIR))

DAEMON_SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(DAEMON_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(DAEMON_SCRIPTS_DIR))

# ---------------------------------------------------------------------------
# Nightly Executor tests
# ---------------------------------------------------------------------------


class TestNightlyExecutorHelpers:
    """Tests for pure functions in nightly_executor.py."""

    def _import_module(self):
        """Import nightly_executor with mocked dependencies."""
        # Mock the task_utils module that nightly_executor imports
        mock_task_utils = MagicMock()
        mock_task_utils.all_backlog_dirs.return_value = [Path("/tmp/test-backlog")]
        mock_task_utils.backlog_dir.return_value = Path("/tmp/test-backlog")
        mock_task_utils.priority_score.side_effect = lambda p: {
            "P0": 0,
            "P1": 1,
            "P2": 2,
            "P3": 3,
        }.get(p, 4)
        mock_task_utils.parse_created.side_effect = lambda d: datetime(2026, 1, 1)
        mock_task_utils.task_title.side_effect = lambda body, stem: stem
        mock_task_utils.is_task_available.return_value = True
        mock_task_utils.read_task.return_value = ({}, "")
        mock_task_utils.write_task.return_value = None
        mock_task_utils.resolve_user_data_base.return_value = Path("/tmp/test-data")

        sys.modules["task_utils"] = mock_task_utils
        module_name = "test_nightly_executor_module"
        sys.modules.pop(module_name, None)
        module_path = (
            SHARED_VAULT_ROOT
            / "capabilities"
            / "skills"
            / "platform-admin"
            / "scripts"
            / "nightly_executor.py"
        )
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        assert spec is not None and spec.loader is not None
        mod = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = mod
        spec.loader.exec_module(mod)
        return mod

    def test_deep_merge_basic(self):
        mod = self._import_module()
        base = {"a": 1, "b": {"c": 2, "d": 3}}
        override = {"b": {"c": 99}, "e": 5}
        result = mod.deep_merge(base, override)
        assert result["a"] == 1
        assert result["b"]["c"] == 99
        assert result["b"]["d"] == 3
        assert result["e"] == 5

    def test_deep_merge_nested(self):
        mod = self._import_module()
        base = {"x": {"y": {"z": 1}}}
        override = {"x": {"y": {"z": 2, "w": 3}}}
        result = mod.deep_merge(base, override)
        assert result["x"]["y"]["z"] == 2
        assert result["x"]["y"]["w"] == 3

    def test_deep_merge_non_dict_override(self):
        mod = self._import_module()
        base = {"a": {"nested": True}}
        override = {"a": "replaced"}
        result = mod.deep_merge(base, override)
        assert result["a"] == "replaced"

    def test_parse_time(self):
        mod = self._import_module()
        result = mod.parse_time("02:30")
        assert result == time(2, 30)

    def test_parse_time_midnight(self):
        mod = self._import_module()
        result = mod.parse_time("00:00")
        assert result == time(0, 0)

    def test_within_window_normal_range(self):
        mod = self._import_module()
        # Window: 02:00 to 08:00
        assert mod.within_window(time(3, 0), time(2, 0), time(8, 0)) is True
        assert mod.within_window(time(1, 0), time(2, 0), time(8, 0)) is False
        assert mod.within_window(time(9, 0), time(2, 0), time(8, 0)) is False

    def test_within_window_overnight(self):
        mod = self._import_module()
        # Window: 22:00 to 06:00 (overnight)
        assert mod.within_window(time(23, 0), time(22, 0), time(6, 0)) is True
        assert mod.within_window(time(3, 0), time(22, 0), time(6, 0)) is True
        assert mod.within_window(time(12, 0), time(22, 0), time(6, 0)) is False

    def test_within_window_exact_boundaries(self):
        mod = self._import_module()
        assert mod.within_window(time(2, 0), time(2, 0), time(8, 0)) is True
        assert mod.within_window(time(8, 0), time(2, 0), time(8, 0)) is True

    def test_count_checklist_items(self):
        mod = self._import_module()
        body = """
# Task
Some description

- [ ] First item
- [x] Second item (done)
- [ ] Third item
* [ ] Fourth item

Regular list:
- not a checklist
"""
        assert mod.count_checklist_items(body) == 4

    def test_count_checklist_items_empty(self):
        mod = self._import_module()
        assert mod.count_checklist_items("No checklist here") == 0

    def test_execution_mode_non_feature(self):
        mod = self._import_module()
        assert mod.execution_mode("bugfix", "body", {}) == "execute"
        assert mod.execution_mode("refactor", "body", {}) == "execute"

    def test_execution_mode_feature_default(self):
        mod = self._import_module()
        assert (
            mod.execution_mode("feature", "body", {"feature_breakdown": True})
            == "breakdown"
        )

    def test_execution_mode_feature_breakdown_disabled(self):
        mod = self._import_module()
        assert (
            mod.execution_mode("feature", "body", {"feature_breakdown": False})
            == "execute"
        )

    def test_execution_mode_feature_requires_checklist(self):
        mod = self._import_module()
        config = {
            "feature_breakdown": True,
            "feature_breakdown_requires_checklist": True,
        }
        body_with = "Some text\n- [ ] User-Stories\nMore text"
        body_without = "No stories here"
        assert mod.execution_mode("feature", body_with, config) == "breakdown"
        assert mod.execution_mode("feature", body_without, config) == "execute"

    def test_scope_score_basic(self):
        mod = self._import_module()
        config = {"scope_items_per_point": 5, "scope_max_score": 3}
        assert mod.scope_score(0, config) == 0
        assert mod.scope_score(4, config) == 0
        assert mod.scope_score(5, config) == 1
        assert mod.scope_score(10, config) == 2
        assert mod.scope_score(100, config) == 3  # Capped at max

    def test_scope_score_zero_per_point(self):
        mod = self._import_module()
        config = {"scope_items_per_point": 0, "scope_max_score": 3}
        assert mod.scope_score(10, config) == 0

    def test_risk_score_no_risk(self):
        mod = self._import_module()
        fm = {}
        body = "Simple task"
        config = {"dependency_penalty": 2, "epic_penalty": 1, "phase_penalty": 1}
        assert mod.risk_score(fm, body, config) == 0

    def test_risk_score_with_dependencies(self):
        mod = self._import_module()
        fm = {"depends_on": "other-task"}
        body = "Task body"
        config = {"dependency_penalty": 2, "epic_penalty": 1, "phase_penalty": 1}
        assert mod.risk_score(fm, body, config) == 2

    def test_risk_score_with_epic(self):
        mod = self._import_module()
        fm = {"parent_epic": "big-project"}
        body = "Task body"
        config = {"dependency_penalty": 2, "epic_penalty": 1, "phase_penalty": 1}
        assert mod.risk_score(fm, body, config) == 1

    def test_risk_score_with_phases(self):
        mod = self._import_module()
        fm = {}
        body = "Phased implementation\n## Phase 1\nDo stuff"
        config = {"dependency_penalty": 2, "epic_penalty": 1, "phase_penalty": 1}
        assert mod.risk_score(fm, body, config) == 1

    def test_risk_score_cumulative(self):
        mod = self._import_module()
        fm = {"depends_on": "x", "epic": "big"}
        body = "Phased implementation plan"
        config = {"dependency_penalty": 2, "epic_penalty": 1, "phase_penalty": 1}
        assert mod.risk_score(fm, body, config) == 4  # 2 + 1 + 1

    def test_roi_score_basic(self):
        mod = self._import_module()
        config = {
            "priority_weight": 3,
            "type_weight": 2,
            "scope_weight": 1,
            "type_weights": {"bugfix": 0, "feature": 3},
            "scope_items_per_point": 5,
            "scope_max_score": 3,
            "feature_breakdown_bonus": 1,
        }
        score, components = mod.roi_score(
            priority=1,
            task_type="bugfix",
            execution="execute",
            scope_items=0,
            risk=0,
            roi_config=config,
        )
        # priority(1) * weight(3) + type(0) * weight(2) + scope(0) * weight(1) + risk(0) = 3
        assert score == 3
        assert components["priority"] == 1
        assert components["type"] == 0

    def test_roi_score_feature_with_breakdown(self):
        mod = self._import_module()
        config = {
            "priority_weight": 3,
            "type_weight": 2,
            "scope_weight": 1,
            "type_weights": {"feature": 3},
            "scope_items_per_point": 5,
            "scope_max_score": 3,
            "feature_breakdown_bonus": 1,
        }
        score, components = mod.roi_score(
            priority=0,
            task_type="feature",
            execution="breakdown",
            scope_items=0,
            risk=0,
            roi_config=config,
        )
        # type_score = 3 - 1 (bonus) = 2
        assert components["type"] == 2

    def test_truncate_short(self):
        mod = self._import_module()
        assert mod.truncate("hello", 10) == "hello"

    def test_truncate_long(self):
        mod = self._import_module()
        result = mod.truncate("a" * 100, 20)
        assert len(result) == 20
        assert result.endswith("...")

    def test_load_config_default(self):
        mod = self._import_module()
        config = mod.load_config(Path("/nonexistent/config.yaml"))
        assert config["enabled"] is True
        assert config["window"]["start"] == "02:00"

    def test_check_preconditions_disabled(self):
        mod = self._import_module()
        assert mod._check_preconditions({"enabled": False}) == "disabled by config"

    def test_select_runner_command_default(self):
        mod = self._import_module()
        task = MagicMock()
        task.execution_mode = "execute"
        config = {
            "runner_command": "default_cmd",
            "runner_command_execute": "",
            "runner_command_breakdown": "",
        }
        assert mod._select_runner_command(task, config) == "default_cmd"

    def test_select_runner_command_execute_specific(self):
        mod = self._import_module()
        task = MagicMock()
        task.execution_mode = "execute"
        config = {
            "runner_command": "default_cmd",
            "runner_command_execute": "execute_cmd",
            "runner_command_breakdown": "",
        }
        assert mod._select_runner_command(task, config) == "execute_cmd"

    def test_select_runner_command_breakdown_specific(self):
        mod = self._import_module()
        task = MagicMock()
        task.execution_mode = "breakdown"
        config = {
            "runner_command": "default_cmd",
            "runner_command_execute": "",
            "runner_command_breakdown": "breakdown_cmd",
        }
        assert mod._select_runner_command(task, config) == "breakdown_cmd"


# ---------------------------------------------------------------------------
# Check Expirations tests
# ---------------------------------------------------------------------------


class TestCheckExpirations:
    """Tests for check_expirations.py functions."""

    def test_parse_duration_days(self):
        from check_expirations import parse_duration

        result = parse_duration("5d")
        assert result == timedelta(days=5)

    def test_parse_duration_weeks(self):
        from check_expirations import parse_duration

        result = parse_duration("2w")
        assert result == timedelta(days=14)

    def test_parse_duration_months(self):
        from check_expirations import parse_duration

        result = parse_duration("3m")
        assert result == timedelta(days=90)

    def test_parse_duration_never(self):
        from check_expirations import parse_duration

        assert parse_duration("never") is None

    def test_parse_duration_invalid_falls_back(self):
        from check_expirations import parse_duration

        result = parse_duration("invalid")
        assert result == timedelta(days=30)

    def test_get_item_added_date_iso(self):
        from check_expirations import get_item_added_date

        item = {"added": "2026-01-15T10:30:00"}
        result = get_item_added_date(item)
        assert result is not None
        assert result.year == 2026
        assert result.month == 1

    def test_get_item_added_date_simple(self):
        from check_expirations import get_item_added_date

        item = {"created_at": "2026-01-15"}
        result = get_item_added_date(item)
        assert result is not None
        assert result.day == 15

    def test_get_item_added_date_datetime_obj(self):
        from check_expirations import get_item_added_date

        dt = datetime(2026, 3, 20)
        item = {"added": dt}
        result = get_item_added_date(item)
        assert result == dt

    def test_get_item_added_date_missing(self):
        from check_expirations import get_item_added_date

        assert get_item_added_date({}) is None

    def test_calculate_expiry_date_explicit(self):
        from check_expirations import calculate_expiry_date

        item = {"expires_at": "2026-06-01"}
        result = calculate_expiry_date(item)
        assert result is not None
        assert result.month == 6

    def test_calculate_expiry_date_from_policy(self):
        from check_expirations import calculate_expiry_date

        item = {"added": "2026-01-01", "expiry_policy": "1m"}
        result = calculate_expiry_date(item)
        assert result is not None
        assert result == datetime(2026, 1, 1) + timedelta(days=30)

    def test_calculate_expiry_date_never(self):
        from check_expirations import calculate_expiry_date

        item = {"added": "2026-01-01", "expiry_policy": "never"}
        assert calculate_expiry_date(item) is None

    def test_is_expired_true(self):
        from check_expirations import is_expired

        item = {"added": "2025-01-01", "expiry_policy": "1m"}
        assert is_expired(item, now=datetime(2026, 1, 15)) is True

    def test_is_expired_false(self):
        from check_expirations import is_expired

        item = {"added": "2026-01-01", "expiry_policy": "1m"}
        assert is_expired(item, now=datetime(2026, 1, 15)) is False

    def test_is_expired_never_policy(self):
        from check_expirations import is_expired

        item = {"added": "2020-01-01", "expiry_policy": "never"}
        assert is_expired(item, now=datetime(2026, 1, 15)) is False

    def test_get_item_identifier_with_title(self):
        from check_expirations import get_item_identifier

        item = {"title": "My Task", "id": "123"}
        assert (
            get_item_identifier(item, 0) == "123"
        )  # id comes before title in field order

    def test_get_item_identifier_fallback(self):
        from check_expirations import get_item_identifier

        item = {"random_field": "value"}
        assert get_item_identifier(item, 5) == "Item #6"

    def test_get_item_identifier_truncated(self):
        from check_expirations import get_item_identifier

        item = {"title": "A" * 100}
        result = get_item_identifier(item, 0)
        assert len(result) <= 50

    def test_extract_items_from_file_list(self, tmp_path):
        from check_expirations import extract_items_from_file
        import yaml

        data = [
            {"title": "Item 1", "added": "2026-01-01"},
            {"title": "Item 2", "added": "2026-01-02"},
        ]
        f = tmp_path / "test.yaml"
        f.write_text(yaml.dump(data))

        items = extract_items_from_file(f)
        assert len(items) == 2
        assert items[0][0]["title"] == "Item 1"
        assert items[0][1] == ""  # Root list has no key

    def test_extract_items_from_file_dict(self, tmp_path):
        from check_expirations import extract_items_from_file
        import yaml

        data = {"jobs": [{"title": "Job 1"}, {"title": "Job 2"}]}
        f = tmp_path / "test.yaml"
        f.write_text(yaml.dump(data))

        items = extract_items_from_file(f)
        assert len(items) == 2
        assert items[0][1] == "jobs"

    def test_extract_items_from_file_nonexistent(self, tmp_path):
        from check_expirations import extract_items_from_file

        items = extract_items_from_file(tmp_path / "nonexistent.yaml")
        assert items == []

    def test_extract_items_from_file_empty(self, tmp_path):
        from check_expirations import extract_items_from_file

        f = tmp_path / "empty.yaml"
        f.write_text("")
        items = extract_items_from_file(f)
        assert items == []

    def test_check_file_expirations(self, tmp_path):
        from check_expirations import check_file_expirations
        import yaml

        data = [
            {"title": "Old item", "added": "2025-01-01", "expiry_policy": "1m"},
            {"title": "New item", "added": "2026-01-20", "expiry_policy": "1m"},
        ]
        f = tmp_path / "test.yaml"
        f.write_text(yaml.dump(data))

        expired = check_file_expirations(f, now=datetime(2026, 1, 25))
        assert len(expired) == 1
        assert expired[0]["identifier"] == "Old item"

    def test_create_review_items(self):
        from check_expirations import create_review_items

        expired_items = [
            {
                "file": "/test/file.yaml",
                "list_key": "jobs",
                "index": 0,
                "identifier": "Test Job",
                "added": "2025-01-01T00:00:00",
                "expired_at": "2025-02-01T00:00:00",
                "days_expired": 60,
                "policy": "1m",
                "suggested_action": "review",
                "item_preview": {"title": "Test Job"},
            }
        ]
        reviews = create_review_items(expired_items)
        assert len(reviews) == 1
        assert reviews[0]["skill"] == "data-expiration"
        assert reviews[0]["priority"] == "high"  # 60 days > 30
        assert "Test Job" in reviews[0]["title"]

    def test_create_review_items_priority_levels(self):
        from check_expirations import create_review_items

        items = [
            {
                "file": "/f.yaml",
                "list_key": "",
                "index": 0,
                "identifier": "A",
                "added": None,
                "expired_at": None,
                "days_expired": 5,
                "policy": "1m",
                "suggested_action": "review",
                "item_preview": {},
            },
            {
                "file": "/f.yaml",
                "list_key": "",
                "index": 1,
                "identifier": "B",
                "added": None,
                "expired_at": None,
                "days_expired": 20,
                "policy": "1m",
                "suggested_action": "review",
                "item_preview": {},
            },
            {
                "file": "/f.yaml",
                "list_key": "",
                "index": 2,
                "identifier": "C",
                "added": None,
                "expired_at": None,
                "days_expired": 45,
                "policy": "1m",
                "suggested_action": "review",
                "item_preview": {},
            },
        ]
        reviews = create_review_items(items)
        assert reviews[0]["priority"] == "low"
        assert reviews[1]["priority"] == "medium"
        assert reviews[2]["priority"] == "high"


# ---------------------------------------------------------------------------
# Service Healer tests
# ---------------------------------------------------------------------------


class TestServiceHealer:
    """Tests for service_healer.py functions."""

    def test_services_dict_structure(self):
        from service_healer import SERVICES

        assert "daemon" in SERVICES
        assert "log_monitor" not in SERVICES  # Moved to legacy
        assert "nightly" not in SERVICES  # Moved to legacy
        assert "plist_name" in SERVICES["daemon"]
        assert "executable" in SERVICES["daemon"]

    def test_legacy_services_dict_structure(self):
        from service_healer import LEGACY_SERVICES

        assert "log_monitor" in LEGACY_SERVICES
        assert "nightly" in LEGACY_SERVICES
        assert "continuous_executor" in LEGACY_SERVICES

    def test_read_plist_paths_nonexistent(self, tmp_path):
        from service_healer import _read_plist_paths

        result = _read_plist_paths(tmp_path / "nonexistent.plist")
        assert result == {}

    def test_read_plist_paths_with_content(self, tmp_path):
        from service_healer import _read_plist_paths

        plist = tmp_path / "test.plist"
        plist.write_text(
            '<?xml version="1.0"?>\n<plist>\n<dict>\n'
            "<key>WorkingDirectory</key>\n<string>/Users/test/Projects/augur</string>\n"
            "<key>ProgramArguments</key>\n<array>\n"
            "<string>/path/to/augur-daemon</string>\n</array>\n"
            "</dict>\n</plist>"
        )
        result = _read_plist_paths(plist)
        assert result["working_dir"] == "/Users/test/Projects/augur"
        assert result["executable"] == "/path/to/augur-daemon"

    def test_generate_plist_content_unified_daemon(self, tmp_path):
        from service_healer import _generate_plist_content

        daemon_root = tmp_path / "project-brain" / "capabilities" / "skills" / "daemon"
        template_dir = daemon_root / "assets" / "plists"
        template_dir.mkdir(parents=True)
        bundle_executable = (
            daemon_root
            / "assets"
            / "bundle"
            / "Augur Daemon.app"
            / "Contents"
            / "MacOS"
            / "Augur"
        )
        bundle_executable.parent.mkdir(parents=True)
        bundle_executable.write_text("", encoding="utf-8")
        (template_dir / "daemon.plist.template").write_text(
            "\n".join(
                [
                    "<plist>",
                    "<key>Label</key><string>__LABEL__</string>",
                    "<key>ProgramArguments</key><array><string>__EXECUTABLE__</string></array>",
                    "<key>WorkingDirectory</key><string>__WORKING_DIRECTORY__</string>",
                    "<key>StandardOutPath</key><string>__STDOUT__</string>",
                    "<key>StandardErrorPath</key><string>__STDERR__</string>",
                    "<key>KeepAlive</key><true/>",
                    "</plist>",
                ]
            ),
            encoding="utf-8",
        )

        content = _generate_plist_content("daemon", tmp_path)
        assert content is not None
        assert "<key>KeepAlive</key>" in content
        assert "Augur Daemon.app" in content
        assert str(tmp_path) in content
        # Should NOT have python3 in ProgramArguments
        assert ".venv/bin/python3" not in content

    def test_generate_plist_content_unknown_service(self):
        from service_healer import _generate_plist_content

        assert _generate_plist_content("nonexistent", Path("/test")) is None

    def test_generate_plist_content_falls_back_to_supervisor_when_bundle_assets_are_missing(
        self, tmp_path, monkeypatch
    ):
        import service_healer

        logs_dir = tmp_path / "logs"
        fake_python = tmp_path / ".venv" / "bin" / "python3"
        fake_python.parent.mkdir(parents=True)
        fake_python.write_text("", encoding="utf-8")

        monkeypatch.setattr(service_healer, "get_logs_dir", lambda: logs_dir)
        monkeypatch.setattr(
            service_healer, "get_python_executable", lambda: fake_python
        )
        monkeypatch.setattr(service_healer, "get_vault_dir", lambda: tmp_path / "vault")
        monkeypatch.setattr(
            service_healer, "get_documents_dir", lambda: tmp_path / "documents"
        )

        content = service_healer._generate_plist_content("daemon", tmp_path)

        assert content is not None
        assert str(fake_python) in content
        assert (
            str(
                tmp_path
                / "project-brain"
                / "capabilities"
                / "skills"
                / "daemon"
                / "scripts"
                / "daemon_supervisor.py"
            )
            in content
        )
        assert "AUGUR_VAULT" in content
        assert "AUGUR_DOCUMENTS" in content

    @patch("sys.platform", "darwin")
    def test_install_services_repairs_existing_broken_plist(
        self, tmp_path, monkeypatch
    ):
        import service_healer

        launch_agents_dir = tmp_path / "LaunchAgents"
        launch_agents_dir.mkdir()
        plist_path = launch_agents_dir / service_healer.SERVICES["daemon"]["plist_name"]
        plist_path.write_text("<plist/>", encoding="utf-8")

        monkeypatch.setattr(service_healer, "get_project_root", lambda: tmp_path)
        monkeypatch.setattr(
            service_healer, "get_launch_agents_dir", lambda: launch_agents_dir
        )

        regenerated: list[tuple[str, Path]] = []

        def _fake_regenerate(name: str, project_root: Path) -> bool:
            regenerated.append((name, project_root))
            return True

        monkeypatch.setattr(service_healer, "_regenerate_macos_plist", _fake_regenerate)

        result = service_healer.install_services()

        assert result["daemon"] == "healed"
        assert regenerated == [("daemon", tmp_path)]

    @patch("sys.platform", "linux")
    def test_heal_service_non_darwin(self):
        from service_healer import heal_service_if_needed

        assert heal_service_if_needed("daemon") is False

    @patch("sys.platform", "win32")
    def test_heal_service_windows(self):
        from service_healer import heal_service_if_needed

        with patch("service_healer._heal_windows_service", return_value=True) as heal:
            assert heal_service_if_needed("daemon") is True

        heal.assert_called_once_with("daemon")

    @patch("sys.platform", "linux")
    def test_install_services_non_darwin(self):
        from service_healer import install_services

        result = install_services()
        assert "error" in result

    @patch("sys.platform", "linux")
    def test_uninstall_services_non_darwin(self):
        from service_healer import uninstall_services

        result = uninstall_services()
        assert "error" in result

    @patch("sys.platform", "linux")
    def test_cleanup_legacy_non_darwin(self):
        from service_healer import cleanup_legacy_services

        result = cleanup_legacy_services()
        assert "error" in result


# ---------------------------------------------------------------------------
# Unified Daemon tests
# ---------------------------------------------------------------------------


class TestUnifiedDaemon:
    @staticmethod
    def _load_unified_daemon_module():
        module_path = (
            Path(__file__).resolve().parents[2] / "scripts" / "unified_daemon.py"
        )
        spec = importlib.util.spec_from_file_location(
            "test_unified_daemon_module", module_path
        )
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module

    """Tests for unified_daemon.py."""

    def test_child_services_registry(self):
        from unified_daemon import CHILD_SERVICES

        required_services = {
            "log_monitor",
            "continuous_executor",
            "dashboard_monitor",
            "mcp_health_monitor",
            "insight_scanner",
            "adaptive_loop_engine",
            "plugin_watcher",
            "schedule_executor",
            "notification_processor",
            "rag_watcher",
        }
        assert required_services <= set(CHILD_SERVICES)

        # Absorbed services should be gone (ADR-180)
        assert "nightly_maintainer" not in CHILD_SERVICES
        assert "runtime_marker_scanner" not in CHILD_SERVICES
        assert "ai_self_healer" not in CHILD_SERVICES

        # Check modes
        assert CHILD_SERVICES["log_monitor"]["mode"] == "persistent"
        assert CHILD_SERVICES["continuous_executor"]["mode"] == "persistent"
        assert CHILD_SERVICES["adaptive_loop_engine"]["mode"] == "persistent"

        # Apple note services are optional and appear only when the apple skill
        # is installed with its service scripts.
        optional_apple_services = {"note_watcher", "note_ingest"} & set(CHILD_SERVICES)
        assert optional_apple_services in (set(), {"note_watcher", "note_ingest"})
        assert len(CHILD_SERVICES) == len(required_services) + len(optional_apple_services)

    def test_child_services_scripts_exist(self):
        from unified_daemon import CHILD_SERVICES

        for name, config in CHILD_SERVICES.items():
            script = Path(config["script"])
            assert script.exists(), f"Script not found for {name}: {script}"

    def test_subprocess_manager_init(self):
        from unified_daemon import SubprocessManager

        config = {
            "script": "/tmp/test.py",
            "mode": "persistent",
            "restart_delay_seconds": 5,
            "max_restarts_per_hour": 10,
        }
        mgr = SubprocessManager("test", config)
        assert mgr.name == "test"
        assert mgr.mode == "persistent"
        assert mgr.state == "stopped"
        assert mgr.process is None
        assert mgr.total_restarts == 0

    def test_subprocess_manager_circuit_breaker(self):
        from unified_daemon import SubprocessManager
        import time as t

        config = {
            "script": "/tmp/test.py",
            "mode": "persistent",
            "restart_delay_seconds": 0,
            "max_restarts_per_hour": 3,
        }
        mgr = SubprocessManager("test", config)
        # Simulate restarts
        now = t.time()
        mgr.restart_timestamps = [now - 10, now - 5, now - 1]
        # Should be blocked (3 restarts in last hour, limit is 3)
        assert mgr._check_circuit_breaker() is False

    def test_subprocess_manager_circuit_breaker_allows_after_cooldown(self):
        from unified_daemon import SubprocessManager
        import time as t

        config = {
            "script": "/tmp/test.py",
            "mode": "persistent",
            "restart_delay_seconds": 0,
            "max_restarts_per_hour": 3,
        }
        mgr = SubprocessManager("test", config)
        # All restarts happened >1 hour ago
        now = t.time()
        mgr.restart_timestamps = [now - 7200, now - 7100, now - 7000]
        assert mgr._check_circuit_breaker() is True

    def test_subprocess_manager_status_dict(self):
        from unified_daemon import SubprocessManager

        config = {
            "script": "/tmp/test.py",
            "mode": "persistent",
            "restart_delay_seconds": 5,
            "max_restarts_per_hour": 10,
        }
        mgr = SubprocessManager("test", config)
        status = mgr._status_dict()
        assert status["state"] == "stopped"
        assert status["pid"] is None
        assert status["total_restarts"] == 0

    def test_subprocess_manager_persistent_exit_becomes_scheduled(self, monkeypatch):
        mod = self._load_unified_daemon_module()

        class DeadProcess:
            pid = 4242

            def poll(self):
                return 1

        config = {
            "script": __file__,
            "mode": "persistent",
            "restart_delay_seconds": 0,
            "max_restarts_per_hour": 10,
        }
        mgr = mod.SubprocessManager("test", config)
        mgr.process = DeadProcess()
        mgr.state = "running"
        mgr._stderr_file = open(__file__)  # noqa: SIM115
        monkeypatch.setattr(mod, "_shutdown", False)

        status = mgr.check_health()

        assert status["state"] == "scheduled"
        assert status["pid"] is None
        assert mgr.process is None
        assert mgr._stderr_file is None
        assert mgr.total_restarts == 1
        assert mgr.consecutive_failures == 1

    def test_subprocess_manager_scheduled_restart_runs_after_backoff(self, monkeypatch):
        mod = self._load_unified_daemon_module()

        config = {
            "script": __file__,
            "mode": "persistent",
            "restart_delay_seconds": 5,
            "max_restarts_per_hour": 10,
        }
        mgr = mod.SubprocessManager("test", config)
        mgr.state = "scheduled"
        mgr.next_restart_at = 0
        mgr.total_restarts = 1
        mgr.restart_timestamps = []
        monkeypatch.setattr(mod, "_shutdown", False)
        monkeypatch.setattr(mgr, "_check_circuit_breaker", lambda: True)
        started = {"called": 0}

        def fake_start():
            started["called"] += 1
            mgr.state = "running"
            return True

        monkeypatch.setattr(mgr, "start", fake_start)

        status = mgr.check_health()

        assert started["called"] == 1
        assert mgr.total_restarts == 2
        assert status["state"] == "running"

    def test_start_clears_stale_critical_item(self, monkeypatch, tmp_path):
        mod = self._load_unified_daemon_module()

        critical_dir = tmp_path / "critical"
        critical_dir.mkdir()
        monkeypatch.setattr(mod, "CRITICAL_DIR", critical_dir)
        monkeypatch.setattr(mod, "PYTHON", Path(sys.executable))

        launched = {}

        class FakeProc:
            def __init__(self):
                self.pid = 999

            def poll(self):
                return None

        def fake_popen(command, **kwargs):
            launched["command"] = command
            return FakeProc()

        monkeypatch.setattr(mod, "_popen_command", fake_popen)

        script_path = tmp_path / "service.py"
        script_path.write_text("print('ok')\n", encoding="utf-8")
        stale_item = critical_dir / "service_test.md"
        stale_item.write_text("stale", encoding="utf-8")

        mgr = mod.SubprocessManager(
            "test",
            {
                "script": str(script_path),
                "mode": "persistent",
                "restart_delay_seconds": 5,
                "max_restarts_per_hour": 10,
            },
        )

        assert mgr.start() is True
        assert launched["command"][1] == str(script_path)
        assert stale_item.exists() is False

    def test_apply_no_window_injects_flag_when_set(self, monkeypatch):
        mod = self._load_unified_daemon_module()
        create_no_window = 0x08000000  # subprocess.CREATE_NO_WINDOW
        monkeypatch.setattr(mod, "_NO_WINDOW_CREATIONFLAGS", create_no_window)

        assert mod._apply_no_window({})["creationflags"] == create_no_window
        # Existing caller flags are preserved, not clobbered.
        merged = mod._apply_no_window({"creationflags": 0x00000200})
        assert merged["creationflags"] == (0x00000200 | create_no_window)

    def test_apply_no_window_noop_when_unset(self, monkeypatch):
        mod = self._load_unified_daemon_module()
        monkeypatch.setattr(mod, "_NO_WINDOW_CREATIONFLAGS", 0)
        assert "creationflags" not in mod._apply_no_window({})

    def test_popen_command_applies_no_window(self, monkeypatch):
        mod = self._load_unified_daemon_module()
        create_no_window = 0x08000000
        monkeypatch.setattr(mod, "_NO_WINDOW_CREATIONFLAGS", create_no_window)
        captured = {}

        def fake_popen(cmd, **kwargs):
            captured["kwargs"] = kwargs
            return object()

        monkeypatch.setattr(mod, "Popen", fake_popen)
        monkeypatch.setattr(mod, "_resolve_command", lambda c: c)
        mod._popen_command(["anything"])
        assert captured["kwargs"]["creationflags"] == create_no_window

    def test_critical_item_uses_runtime_log_path(self, monkeypatch, tmp_path):
        mod = self._load_unified_daemon_module()

        critical_dir = tmp_path / "critical"
        critical_dir.mkdir()
        monkeypatch.setattr(mod, "CRITICAL_DIR", critical_dir)
        monkeypatch.setattr(
            mod, "_STDERR_LOGS_DIR", tmp_path / "runtime-logs" / "daemon" / "stderr"
        )

        mgr = mod.SubprocessManager(
            "test",
            {
                "script": "/tmp/test.py",
                "mode": "persistent",
                "restart_delay_seconds": 5,
                "max_restarts_per_hour": 10,
            },
        )
        mgr.consecutive_failures = 3
        mgr.total_restarts = 7

        mgr._create_critical_item()

        content = (critical_dir / "service_test.md").read_text(encoding="utf-8")
        assert "logs/test/" not in content
        assert (
            str(tmp_path / "runtime-logs" / "daemon" / "stderr" / "test.stderr.log")
            in content
        )

    def test_critical_notification_uses_runtime_log_path(self, monkeypatch, tmp_path):
        mod = self._load_unified_daemon_module()
        monkeypatch.setattr(
            mod, "_STDERR_LOGS_DIR", tmp_path / "runtime-logs" / "daemon" / "stderr"
        )

        captured: dict[str, str] = {}

        class FakeNotificationService:
            def notify(self, message, **kwargs):
                captured["message"] = message
                captured["copy_text"] = kwargs["copy_text"]

        monkeypatch.setattr(mod, "_notification_service", FakeNotificationService)

        mgr = mod.SubprocessManager(
            "test",
            {
                "script": "/tmp/test.py",
                "mode": "persistent",
                "restart_delay_seconds": 5,
                "max_restarts_per_hour": 10,
            },
        )
        mgr.consecutive_failures = 3
        mgr.total_restarts = 7

        mgr._notify_critical("daemon failed")

        assert captured["message"] == "daemon failed"
        assert "logs/test/" not in captured["copy_text"]
        assert (
            str(tmp_path / "runtime-logs" / "daemon" / "stderr" / "test.stderr.log")
            in captured["copy_text"]
        )


class _DummyStuckProcess:
    """poll() says running forever; records kill()."""

    pid = 99999

    def __init__(self) -> None:
        self.killed = False

    def poll(self):
        return None

    def kill(self) -> None:
        self.killed = True


class TestHeartbeatSelfHeal:
    """Heartbeat supervision: stuck-but-alive children get killed for restart."""

    @staticmethod
    def _make_manager(tmp_path, heartbeat_age_seconds):
        import json as _json
        import time as _time
        from datetime import datetime as _dt, timedelta as _td, timezone as _tz

        from unified_daemon import SubprocessManager

        hb_file = tmp_path / "state.json"
        hb_at = _dt.now(_tz.utc) - _td(seconds=heartbeat_age_seconds)
        hb_file.write_text(
            _json.dumps({"heartbeat_at": hb_at.isoformat()}), encoding="utf-8"
        )
        script = tmp_path / "svc.py"
        script.write_text("print('x')", encoding="utf-8")
        mgr = SubprocessManager(
            "rag_watcher_test",
            {
                "script": str(script),
                "mode": "persistent",
                "heartbeat_file": str(hb_file),
                "heartbeat_timeout_seconds": 45,
            },
        )
        mgr.process = _DummyStuckProcess()
        # Started long ago -> grace period passed
        mgr.last_started = _dt.fromtimestamp(_time.time() - 600).isoformat()
        return mgr

    def test_stale_heartbeat_kills_stuck_process(self, tmp_path):
        mgr = self._make_manager(tmp_path, heartbeat_age_seconds=300)
        mgr.check_health()
        assert mgr.process.killed is True

    def test_fresh_heartbeat_leaves_process_alone(self, tmp_path):
        mgr = self._make_manager(tmp_path, heartbeat_age_seconds=5)
        mgr.check_health()
        assert mgr.process.killed is False

    def test_no_heartbeat_config_means_no_kill(self, tmp_path):
        mgr = self._make_manager(tmp_path, heartbeat_age_seconds=300)
        mgr.heartbeat_file = None
        mgr.check_health()
        assert mgr.process.killed is False

    def test_within_grace_period_no_kill(self, tmp_path):
        import time as _time
        from datetime import datetime as _dt

        mgr = self._make_manager(tmp_path, heartbeat_age_seconds=300)
        mgr.last_started = _dt.fromtimestamp(_time.time() - 10).isoformat()
        mgr.check_health()
        assert mgr.process.killed is False

    def test_rag_watcher_service_declares_heartbeat(self):
        from unified_daemon import CHILD_SERVICES

        config = CHILD_SERVICES["rag_watcher"]
        assert config["heartbeat_timeout_seconds"] == 45
        assert config["heartbeat_file"].endswith("rag_watcher_state.json")


class TestSupervisorRagWatcherRegistration:
    """ADR-787 migration gap: rag_watcher must run under the in-process supervisor."""

    def test_rag_watcher_is_a_prod_singleton_daemon(self):
        import daemon_supervisor

        assert "rag_watcher" in daemon_supervisor.PROD_DAEMONS
        assert "rag_watcher" in daemon_supervisor.SINGLETON_DAEMONS
        assert "rag_watcher" in daemon_supervisor.ALL_DAEMONS

    def test_build_registry_maps_rag_watcher_to_run_loop(self):
        import daemon_supervisor

        registry = daemon_supervisor._build_registry({"rag_watcher"})
        assert "rag_watcher" in registry
        assert callable(registry["rag_watcher"])
