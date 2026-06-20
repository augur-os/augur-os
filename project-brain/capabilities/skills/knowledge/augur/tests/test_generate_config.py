"""
Tests for generate_config — auto-generate config.yaml for the knowledge/RAG plugin.

Module: skills/knowledge/scripts/generate_config.py
"""

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml


# ---------------------------------------------------------------------------
# find_exo_root
# ---------------------------------------------------------------------------


class TestFindExoRoot:
    """Tests for find_exo_root project detection."""

    def test_finds_root_with_claude_md_and_plugins(self, tmp_path):
        from skills.knowledge.scripts.generate_config import find_exo_root

        (tmp_path / "CLAUDE.md").write_text("# Instructions")
        (tmp_path / "plugins").mkdir()

        with patch(
            "skills.knowledge.scripts.generate_config.get_plugin_dir",
            return_value=tmp_path / "plugins" / "ai" / "skills" / "knowledge",
        ):
            # Create the nested path so parents works
            plugin_dir = tmp_path / "plugins" / "ai" / "skills" / "knowledge"
            plugin_dir.mkdir(parents=True)
            result = find_exo_root()
        assert result == tmp_path

    def test_finds_root_with_apps_dashboard(self, tmp_path):
        from skills.knowledge.scripts.generate_config import find_exo_root

        (tmp_path / "apps" / "dashboard").mkdir(parents=True)

        plugin_dir = tmp_path / "plugins" / "ai" / "skills" / "knowledge"
        plugin_dir.mkdir(parents=True)

        with patch(
            "skills.knowledge.scripts.generate_config.get_plugin_dir",
            return_value=plugin_dir,
        ):
            result = find_exo_root()
        assert result == tmp_path

    def test_returns_none_when_no_markers(self, tmp_path):
        from skills.knowledge.scripts.generate_config import find_exo_root

        bare_dir = tmp_path / "empty"
        bare_dir.mkdir()

        with patch(
            "skills.knowledge.scripts.generate_config.get_plugin_dir",
            return_value=bare_dir,
        ):
            result = find_exo_root()
        assert result is None


# ---------------------------------------------------------------------------
# find_exo_data_dir
# ---------------------------------------------------------------------------


class TestFindExoDataDir:
    """Tests for find_exo_data_dir locating the data directory."""

    def test_finds_data_dir_in_monorepo(self, tmp_path):
        from skills.knowledge.scripts.generate_config import find_exo_data_dir

        (tmp_path / "data").mkdir()
        result = find_exo_data_dir(tmp_path)
        assert result == tmp_path / "data"

    def test_falls_back_to_env_var(self, tmp_path, monkeypatch):
        from skills.knowledge.scripts.generate_config import find_exo_data_dir

        monkeypatch.setenv("AUGUR_ROOT", str(tmp_path / "custom"))
        result = find_exo_data_dir(tmp_path)
        assert result == tmp_path / "custom"

    def test_returns_none_when_no_data(self, tmp_path, monkeypatch):
        from skills.knowledge.scripts.generate_config import find_exo_data_dir

        monkeypatch.delenv("AUGUR_ROOT", raising=False)
        result = find_exo_data_dir(tmp_path)
        assert result is None


# ---------------------------------------------------------------------------
# generate_config
# ---------------------------------------------------------------------------


class TestGenerateConfig:
    """Tests for generate_config writing config.yaml."""

    def test_generates_config_from_template(self, tmp_path):
        from skills.knowledge.scripts.generate_config import generate_config

        template = tmp_path / "config.template.yaml"
        template.write_text(yaml.dump({"version": "1.0", "paths": {}}))

        with patch(
            "skills.knowledge.scripts.generate_config.get_plugin_dir",
            return_value=tmp_path,
        ):
            result = generate_config(
                data_dir="/custom/data",
                project_root="/custom/root",
                force=True,
            )

        assert result.exists()
        config = yaml.safe_load(result.read_text().split("\n\n", 1)[1])
        assert config["paths"]["data_dir"] == "/custom/data"
        assert config["paths"]["project_root"] == "/custom/root"

    def test_skips_existing_without_force(self, tmp_path):
        from skills.knowledge.scripts.generate_config import generate_config

        template = tmp_path / "config.template.yaml"
        template.write_text(yaml.dump({"version": "1.0"}))
        existing = tmp_path / "config.yaml"
        existing.write_text("existing content")

        with patch(
            "skills.knowledge.scripts.generate_config.get_plugin_dir",
            return_value=tmp_path,
        ):
            result = generate_config(force=False)

        # Should return existing path without overwriting
        assert result == existing
        assert existing.read_text() == "existing content"

    def test_raises_when_template_missing(self, tmp_path):
        from skills.knowledge.scripts.generate_config import generate_config

        with patch(
            "skills.knowledge.scripts.generate_config.get_plugin_dir",
            return_value=tmp_path,
        ):
            with pytest.raises(FileNotFoundError, match="Template not found"):
                generate_config(force=True)
