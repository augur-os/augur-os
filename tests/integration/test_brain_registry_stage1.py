from __future__ import annotations

from pathlib import Path

import pytest
import yaml

import src.config.paths as paths
from src.config.paths import (
    get_brain_dir,
    get_brain_registry_path,
    get_vault_dir,
    list_brain_ids,
)
from src.lib.brain_mount import ensure_mount
from src.lib.brain_registry import clear_cache, get_registry


@pytest.fixture
def fake_project_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("AUGUR_STATE_DIR", str(tmp_path / ".augur"))
    # vault.yaml describes a local fixture path; bootstrap should not require
    # any user data beyond the configured path value.
    config_dir = tmp_path / "config" / "system"
    config_dir.mkdir(parents=True)
    (config_dir / "vault.yaml").write_text(
        "vault:\n"
        f"  path: {tmp_path / 'fake-au-vault'}\n"
        "  git:\n"
        "    auto_commit: true\n"
        "    auto_push: true\n"
        "    remote: origin\n"
        "    branch: main\n"
        "  remote: \"https://example.com/fake.git\"\n",
        encoding="utf-8",
    )
    (tmp_path / "fake-au-vault").mkdir()
    brain_root = tmp_path / "project-brain"
    brain_root.mkdir()
    (brain_root / "BRAIN.yaml").write_text(
        "schema_version: 1\n"
        "id: project-augur\n"
        "type: project\n"
        f"root: {brain_root}\n"
        f"attached_project: {tmp_path}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("AUGUR_VAULT", str(tmp_path / "fake-au-vault"))
    monkeypatch.chdir(tmp_path)
    clear_cache()
    paths.invalidate_project_cache()
    yield tmp_path
    clear_cache()
    paths.invalidate_project_cache()


def test_fresh_setup_creates_registry_and_mounts(fake_project_root: Path):
    # On first call, brains.yaml does not exist.
    registry_path = get_brain_registry_path()
    assert not registry_path.is_file()

    registry = get_registry(project_root=fake_project_root)

    # Registry file now exists with both expected brains.
    assert registry_path.is_file()
    assert sorted(registry.ids()) == ["personal", "project-augur"]

    # get_brain_dir resolves to the same paths as the legacy helpers.
    assert get_brain_dir("personal") == get_vault_dir()
    assert get_brain_dir("project-augur") == fake_project_root / "project-brain"
    assert sorted(list_brain_ids()) == ["personal", "project-augur"]

    # Root BRAIN.yaml manifests exist after ensure_mount runs for each.
    for brain_id in registry.ids():
        brain = registry.get(brain_id)
        assert brain is not None
        ensure_mount(brain)
        manifest = brain.data_root / "BRAIN.yaml"
        assert manifest.is_file()
        assert not (brain.data_root / ".augur" / "BRAIN.yaml").exists()
        parsed = yaml.safe_load(manifest.read_text(encoding="utf-8"))
        assert parsed["id"] == brain_id
        assert parsed["type"] == brain.type.value
        assert parsed["schema_version"] == 1
        assert parsed["root"] == str(brain.data_root)
        if brain.git.host_repo is not None:
            assert parsed["attached_project"] == str(brain.git.host_repo)
        else:
            assert "attached_project" not in parsed


def test_subsequent_calls_reuse_registry(fake_project_root: Path):
    first_registry = get_registry(project_root=fake_project_root)
    registry_path = get_brain_registry_path()
    first_mtime = registry_path.stat().st_mtime
    # No bootstrap should re-run.
    clear_cache()  # force re-read but NOT regenerate
    second_registry = get_registry(project_root=fake_project_root)
    assert second_registry.ids() == first_registry.ids()
    assert registry_path.stat().st_mtime == first_mtime
