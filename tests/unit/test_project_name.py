"""Tests for get_project_name() and get_project_port() from project.yaml."""

import yaml
from unittest.mock import patch


def test_get_project_name_reads_from_project_yaml(tmp_path):
    import src.config.paths as pm

    pm._project_name_cache = None
    (tmp_path / "project.yaml").write_text(yaml.dump({"name": "myapp", "port": 3001}))
    with patch.object(pm, "get_project_root", return_value=tmp_path):
        assert pm.get_project_name() == "myapp"
    pm._project_name_cache = None


def test_get_project_name_falls_back_to_augur(tmp_path):
    import src.config.paths as pm

    pm._project_name_cache = None
    with patch.object(pm, "get_project_root", return_value=tmp_path):
        assert pm.get_project_name() == "Augur"
    pm._project_name_cache = None


def test_get_project_name_caches_result(tmp_path):
    import src.config.paths as pm

    pm._project_name_cache = None
    (tmp_path / "project.yaml").write_text(yaml.dump({"name": "cached-app", "port": 3002}))
    with patch.object(pm, "get_project_root", return_value=tmp_path):
        r1 = pm.get_project_name()
        (tmp_path / "project.yaml").unlink()
        r2 = pm.get_project_name()
        assert r1 == r2 == "cached-app"
    pm._project_name_cache = None


def test_get_project_port_reads_from_yaml(tmp_path):
    import src.config.paths as pm

    pm._project_port_cache = None
    (tmp_path / "project.yaml").write_text(yaml.dump({"name": "myapp", "port": 3001}))
    with patch.object(pm, "get_project_root", return_value=tmp_path):
        assert pm.get_project_port() == 3001
    pm._project_port_cache = None


def test_get_project_port_defaults_to_3000(tmp_path):
    import src.config.paths as pm

    pm._project_port_cache = None
    with patch.object(pm, "get_project_root", return_value=tmp_path):
        assert pm.get_project_port() == 3000
    pm._project_port_cache = None
