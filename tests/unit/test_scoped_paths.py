"""Tests that external paths are scoped by project name."""

import yaml
from unittest.mock import patch


def _setup(tmp_path, name="testproject"):
    import src.config.paths as pm

    pm.invalidate_project_cache()
    (tmp_path / "project.yaml").write_text(yaml.dump({"name": name, "port": 3000}))
    return pm


def test_vault_scoped(tmp_path):
    pm = _setup(tmp_path)
    with (
        patch.object(pm, "get_project_root", return_value=tmp_path),
        patch.object(pm, "_resolve_with_discovery", side_effect=lambda _path_type, resolved: resolved),
    ):
        assert pm.get_vault_dir().name == "testproject"
    pm.invalidate_project_cache()


def test_documents_scoped(tmp_path):
    pm = _setup(tmp_path)
    with (
        patch.object(pm, "get_project_root", return_value=tmp_path),
        patch.object(pm, "_resolve_with_discovery", side_effect=lambda _path_type, resolved: resolved),
    ):
        assert pm.get_documents_dir().name == "testproject"
    pm.invalidate_project_cache()


def test_logs_scoped(tmp_path):
    pm = _setup(tmp_path)
    with patch.object(pm, "get_project_root", return_value=tmp_path):
        assert "testproject" in str(pm.get_logs_dir())
    pm.invalidate_project_cache()


def test_cache_scoped(tmp_path):
    pm = _setup(tmp_path)
    with patch.object(pm, "get_project_root", return_value=tmp_path):
        assert "testproject" in str(pm.get_cache_dir())
    pm.invalidate_project_cache()


def test_fallback_uses_augur(tmp_path):
    import src.config.paths as pm

    pm.invalidate_project_cache()
    with (
        patch.object(pm, "get_project_root", return_value=tmp_path),
        patch.object(pm, "_resolve_with_discovery", side_effect=lambda _path_type, resolved: resolved),
    ):
        assert pm.get_vault_dir().name == "Augur"
    pm.invalidate_project_cache()


def test_env_override_precedence(tmp_path, monkeypatch):
    pm = _setup(tmp_path)
    monkeypatch.setenv("AUGUR_VAULT", str(tmp_path / "custom-vault"))
    with (
        patch.object(pm, "get_project_root", return_value=tmp_path),
        patch.object(pm, "_resolve_with_discovery", side_effect=lambda _path_type, resolved: resolved),
    ):
        assert pm.get_vault_dir() == (tmp_path / "custom-vault").resolve()
    pm.invalidate_project_cache()
