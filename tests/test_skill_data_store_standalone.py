# tests/test_skill_data_store_standalone.py
import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Dynamic import to avoid src.config dependency issues
_utils_path = Path(__file__).resolve().parent.parent / "src" / "mcp" / "plugin_utils.py"
_spec = importlib.util.spec_from_file_location("plugin_utils", _utils_path)
_mod = importlib.util.module_from_spec(_spec)

# Stub canonical MCP helpers so plugin_utils falls back to stdlib logging.getLogger,
# avoiding a cascade import of src.logging.config that permanently binds
# get_logs_dir to a MagicMock (the from-import caches it at module level).
# Also stub src.config.paths for the lazy import in _resolve_data_dir.
_stubs = {
    "src.config.paths": MagicMock(),
    "src.mcp.augur_shared.logging": MagicMock(),
    "src.mcp.augur_shared.annotations": MagicMock(),
}
with patch.dict(sys.modules, _stubs):
    _spec.loader.exec_module(_mod)

SkillDataStore = _mod.SkillDataStore


def test_resolve_data_dir_falls_back_to_seeds_when_no_vault(tmp_path):
    """When get_skill_data_dir raises (no vault configured), use assets/seeds/."""
    skill_dir = tmp_path / "my-skill"
    skill_dir.mkdir()
    seeds_dir = skill_dir / "assets" / "seeds"
    seeds_dir.mkdir(parents=True)

    mock = MagicMock()
    mock.get_skill_data_dir = MagicMock(side_effect=Exception("no vault"))
    with patch.dict(sys.modules, {"src.config.paths": mock}):
        store = SkillDataStore(skill_dir)
    assert store.data_dir == seeds_dir


def test_resolve_data_dir_uses_vault_when_available(tmp_path):
    """When vault is configured, use the vault path."""
    skill_dir = tmp_path / "my-skill"
    skill_dir.mkdir()
    vault_data = tmp_path / "vault" / "my-skill"
    vault_data.mkdir(parents=True)

    mock = MagicMock()
    mock.get_skill_data_dir = MagicMock(return_value=vault_data)
    with patch.dict(sys.modules, {"src.config.paths": mock}):
        store = SkillDataStore(skill_dir)
    assert store.data_dir == vault_data
