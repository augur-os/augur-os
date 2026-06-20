"""Tests for apps/dashboard/scripts/skill-scripts/scaffold.py — plugin scaffolding."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Load module via importlib (directory has hyphens). File lives at
# apps/dashboard/scripts/skill-scripts/scaffold.py — this test sits at
# tests/dashboard/python/test_scaffold.py so parents[3] is the project root.
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[3]
_MODULE_PATH = _REPO_ROOT / "apps" / "dashboard" / "scripts" / "skill-scripts" / "scaffold.py"

if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

_spec = importlib.util.spec_from_file_location("scaffold", _MODULE_PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

to_kebab_case = _mod.to_kebab_case
to_title_case = _mod.to_title_case
to_snake_case = _mod.to_snake_case
replace_placeholders = _mod.replace_placeholders
get_default_variables = _mod.get_default_variables
create_directory_structure = _mod.create_directory_structure
CATEGORY_ICONS = _mod.CATEGORY_ICONS
VALID_CATEGORIES = _mod.VALID_CATEGORIES
VALID_FEATURES = _mod.VALID_FEATURES


# ---------------------------------------------------------------------------
# Case conversion
# ---------------------------------------------------------------------------


class TestCaseConversion:
    def test_kebab_from_spaces(self):
        assert to_kebab_case("My Plugin") == "my-plugin"

    def test_kebab_from_underscores(self):
        assert to_kebab_case("my_plugin") == "my-plugin"

    def test_kebab_from_camel(self):
        assert to_kebab_case("myPlugin") == "my-plugin"

    def test_kebab_already_correct(self):
        assert to_kebab_case("my-plugin") == "my-plugin"

    def test_title_case(self):
        assert to_title_case("my-plugin") == "My Plugin"

    def test_title_single_word(self):
        assert to_title_case("plugin") == "Plugin"

    def test_snake_case(self):
        assert to_snake_case("my-plugin") == "my_plugin"


# ---------------------------------------------------------------------------
# replace_placeholders
# ---------------------------------------------------------------------------


class TestReplacePlaceholders:
    def test_replaces_single(self):
        assert replace_placeholders("Hello {NAME}", {"NAME": "World"}) == "Hello World"

    def test_replaces_multiple(self):
        result = replace_placeholders("{A} and {B}", {"A": "X", "B": "Y"})
        assert result == "X and Y"

    def test_leaves_unknown_placeholders(self):
        result = replace_placeholders("{A} and {UNKNOWN}", {"A": "X"})
        assert result == "X and {UNKNOWN}"

    def test_empty_content(self):
        assert replace_placeholders("", {"A": "X"}) == ""


# ---------------------------------------------------------------------------
# get_default_variables
# ---------------------------------------------------------------------------


class TestGetDefaultVariables:
    def test_required_keys_present(self):
        variables = get_default_variables("test-plugin", "business", "Test desc", [])
        assert variables["PLUGIN_NAME"] == "test-plugin"
        assert variables["PLUGIN_TITLE"] == "Test Plugin"
        assert variables["CATEGORY"] == "business"
        assert variables["PLUGIN_DESCRIPTION"] == "Test desc"

    def test_icon_for_category(self):
        for category, icon in CATEGORY_ICONS.items():
            variables = get_default_variables("x", category, "d", [])
            assert variables["LUCIDE_ICON"] == icon

    def test_tool_name_uses_snake_case(self):
        variables = get_default_variables("my-cool-plugin", "system", "d", [])
        assert variables["TOOL_NAME"] == "get_my_cool_plugin_data"


# ---------------------------------------------------------------------------
# create_directory_structure
# ---------------------------------------------------------------------------


class TestCreateDirectoryStructure:
    def test_creates_root_and_scripts(self, tmp_path):
        plugin_path = tmp_path / "my-plugin"
        created = create_directory_structure(plugin_path, [])
        assert plugin_path.exists()
        assert (plugin_path / "scripts").exists()
        assert str(plugin_path) in created

    def test_dashboard_feature(self, tmp_path):
        plugin_path = tmp_path / "p"
        create_directory_structure(plugin_path, ["dashboard"])
        assert (plugin_path / "dashboard" / "tabs").is_dir()

    def test_api_feature(self, tmp_path):
        plugin_path = tmp_path / "p"
        create_directory_structure(plugin_path, ["api"])
        assert (plugin_path / "api" / "health").is_dir()
        assert (plugin_path / "api" / "data").is_dir()

    def test_mcp_feature(self, tmp_path):
        plugin_path = tmp_path / "p"
        create_directory_structure(plugin_path, ["mcp"])
        assert (plugin_path / "mcp").is_dir()

    def test_tests_feature(self, tmp_path):
        plugin_path = tmp_path / "p"
        create_directory_structure(plugin_path, ["tests"])
        assert (plugin_path / "tests").is_dir()

    def test_all_features(self, tmp_path):
        plugin_path = tmp_path / "p"
        create_directory_structure(plugin_path, list(VALID_FEATURES))
        for d in ["dashboard", "api", "mcp", "chains", "schemas", "backlog", "tests", "scripts"]:
            assert (plugin_path / d).is_dir(), f"Missing directory: {d}"


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


def test_valid_categories():
    assert "system" in VALID_CATEGORIES
    assert "business" in VALID_CATEGORIES
    assert len(VALID_CATEGORIES) >= 4


def test_valid_features():
    assert "mcp" in VALID_FEATURES
    assert "dashboard" in VALID_FEATURES
    assert "tests" in VALID_FEATURES
