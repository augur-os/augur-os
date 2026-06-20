"""Tests for shared path primitives used by both monorepo and standalone resolvers."""

import os
from pathlib import Path
from unittest.mock import patch


from src.config.path_primitives import (
    expand_path,
    env_path,
    is_macos,
    is_windows,
    windows_local_dir,
    windows_roaming_dir,
    xdg_data_home,
    xdg_state_home,
    xdg_cache_home,
    application_support_dir,
    state_home_dir,
    logs_home_dir,
    cache_home_dir,
    vault_home_dir,
    documents_home_dir,
)


def test_expand_path_resolves_home():
    result = expand_path("~/test")
    assert not str(result).startswith("~")
    assert result.is_absolute()


def test_expand_path_resolves_relative():
    result = expand_path("relative/path")
    assert result.is_absolute()


def test_env_path_returns_none_for_missing_var():
    result = env_path("AUGUR_NONEXISTENT_TEST_VAR_12345")
    assert result is None


def test_env_path_returns_path_for_set_var():
    with patch.dict(os.environ, {"AUGUR_TEST_PATH": "/tmp/test"}):
        result = env_path("AUGUR_TEST_PATH")
        assert result == Path("/tmp/test").resolve()


def test_env_path_strips_whitespace():
    with patch.dict(os.environ, {"AUGUR_TEST_PATH": "  /tmp/test  "}):
        result = env_path("AUGUR_TEST_PATH")
        assert result == Path("/tmp/test").resolve()


def test_env_path_ignores_whitespace_only():
    with patch.dict(os.environ, {"AUGUR_TEST_PATH": "   "}):
        result = env_path("AUGUR_TEST_PATH")
        assert result is None


def test_env_path_checks_multiple_names():
    with patch.dict(os.environ, {"SECOND_VAR": "/tmp/second"}, clear=False):
        # First var doesn't exist, second does
        result = env_path("AUGUR_NONEXISTENT_12345", "SECOND_VAR")
        assert result == Path("/tmp/second").resolve()


def test_env_path_returns_first_match():
    with patch.dict(os.environ, {"FIRST_VAR": "/tmp/first", "SECOND_VAR": "/tmp/second"}):
        result = env_path("FIRST_VAR", "SECOND_VAR")
        assert result == Path("/tmp/first").resolve()


def test_is_macos_returns_bool():
    result = is_macos()
    assert isinstance(result, bool)


def test_is_windows_returns_bool():
    result = is_windows()
    assert isinstance(result, bool)


def test_xdg_data_home_returns_absolute():
    result = xdg_data_home()
    assert result.is_absolute()


def test_xdg_state_home_returns_absolute():
    result = xdg_state_home()
    assert result.is_absolute()


def test_xdg_cache_home_returns_absolute():
    result = xdg_cache_home()
    assert result.is_absolute()


def test_application_support_dir_uses_project_name():
    result = application_support_dir("TestProject")
    if is_macos():
        assert "TestProject" in str(result)
    else:
        assert "testproject" in str(result).lower()


def test_state_home_dir_uses_project_name():
    result = state_home_dir("TestProject")
    if is_macos():
        assert "TestProject" in str(result)
    else:
        assert "testproject" in str(result).lower()


def test_logs_home_dir_uses_project_name():
    result = logs_home_dir("TestProject")
    if is_macos():
        assert "TestProject" in str(result)
    else:
        assert "testproject" in str(result).lower()


def test_cache_home_dir_uses_project_name():
    result = cache_home_dir("TestProject")
    if is_macos():
        assert "TestProject" in str(result)
    else:
        assert "testproject" in str(result).lower()


def test_windows_dirs_use_appdata_environment(monkeypatch, tmp_path):
    roaming = tmp_path / "AppData" / "Roaming"
    local = tmp_path / "AppData" / "Local"
    monkeypatch.setenv("APPDATA", str(roaming))
    monkeypatch.setenv("LOCALAPPDATA", str(local))

    with patch("platform.system", return_value="Windows"):
        assert windows_roaming_dir() == roaming.resolve()
        assert windows_local_dir() == local.resolve()
        assert application_support_dir("Augur") == roaming.resolve() / "Augur"
        assert state_home_dir("Augur") == local.resolve() / "Augur" / "state"
        assert logs_home_dir("Augur") == local.resolve() / "Augur" / "logs"
        assert cache_home_dir("Augur") == local.resolve() / "Augur" / "Caches"


def test_vault_home_dir_uses_project_name():
    result = vault_home_dir("TestProject")
    assert "TestProject" in str(result)


def test_documents_home_dir_uses_project_name():
    result = documents_home_dir("TestProject")
    assert "TestProject" in str(result)


def test_all_dir_functions_return_absolute_paths():
    name = "Augur"
    for fn in [
        application_support_dir,
        state_home_dir,
        logs_home_dir,
        cache_home_dir,
        vault_home_dir,
        documents_home_dir,
    ]:
        result = fn(name)
        assert result.is_absolute(), f"{fn.__name__} returned relative path"


def test_primitives_have_no_augur_imports():
    """path_primitives.py must have zero imports from other Augur modules."""
    import inspect
    import src.config.path_primitives as mod

    source = inspect.getsource(mod)
    # Should not import from src.*, augur_mcp.*, etc.
    assert "from src." not in source, "path_primitives must not import from src.*"
    assert "from src.mcp.augur" not in source, "path_primitives must not import from src.mcp.* namespaces"
    assert "import src." not in source, "path_primitives must not import src.*"
    assert "import augur_mcp" not in source, "path_primitives must not import augur_mcp.*"
