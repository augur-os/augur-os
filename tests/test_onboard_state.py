# tests/test_onboard_state.py
import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

_scripts_dir = Path(__file__).resolve().parent.parent / "src" / "scripts"
_spec = importlib.util.spec_from_file_location("onboard_state", _scripts_dir / "onboard_state.py")
_mod = importlib.util.module_from_spec(_spec)
# Use patch.dict so the mock is scoped and does not leak to other modules.
# The mock is installed permanently for this module (loaded once) but does NOT
# poison sys.modules for subsequent imports in other test files.
_paths_mock = MagicMock()
with patch.dict(sys.modules, {"src.config.paths": _paths_mock}):
    sys.modules["onboard_state"] = _mod
    _spec.loader.exec_module(_mod)


def test_read_state_returns_none_when_missing(tmp_path):
    """Returns None when state file does not exist."""
    _mod._state_path = lambda: tmp_path / _mod.STATE_FILENAME
    assert _mod.read_state() is None


def test_write_state_creates_file(tmp_path):
    """write_state creates JSON with correct structure."""
    state_file = tmp_path / _mod.STATE_FILENAME
    _mod._state_path = lambda: state_file
    _mod.write_state(install_source="vault", configured_clients=["vault"])
    assert state_file.exists()
    data = json.loads(state_file.read_text())
    assert data["install_source"] == "vault"
    assert data["configured_clients"] == ["vault"]
    assert "installed_at" in data
    assert data["vault_scaffolded"] is False
    assert data["dashboard_started"] is False


def test_add_configured_client_appends(tmp_path):
    """add_configured_client adds without duplicates."""
    state_file = tmp_path / _mod.STATE_FILENAME
    _mod._state_path = lambda: state_file
    _mod.write_state(install_source="claude-code", configured_clients=["claude-code"])
    _mod.add_configured_client("cursor")
    state = _mod.read_state()
    assert "cursor" in state["configured_clients"]
    assert "claude-code" in state["configured_clients"]
    # No duplicate on re-add
    _mod.add_configured_client("cursor")
    state = _mod.read_state()
    assert state["configured_clients"].count("cursor") == 1


def test_mark_vault_scaffolded(tmp_path):
    """mark_vault_scaffolded sets flag to True."""
    state_file = tmp_path / _mod.STATE_FILENAME
    _mod._state_path = lambda: state_file
    _mod.write_state()
    _mod.mark_vault_scaffolded()
    state = _mod.read_state()
    assert state["vault_scaffolded"] is True
