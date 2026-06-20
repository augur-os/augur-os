"""Tests for the ADR-270 path configuration model."""

from src.config.path_config import PathCategory, PathConfig
from src.config.paths import (
    get_cache_dir,
    get_documents_dir,
    get_ipc_dir,
    get_logs_dir,
    get_project_root,
    get_rag_dir,
    get_runtime_dir,
    get_skills_dir,
    get_vault_dir,
)


def test_defaults_use_split_storage_layout():
    config = PathConfig.defaults()

    assert config.core.path == get_project_root()
    assert config.data.path == get_vault_dir()
    assert config.plugins.path == get_skills_dir()
    assert config.runtime.path == get_runtime_dir()
    assert config.data.subdirs == [str(get_documents_dir()), str(get_rag_dir())]
    assert config.runtime.subdirs == [
        str(get_logs_dir()),
        str(get_cache_dir()),
        str(get_ipc_dir()),
    ]


def test_refresh_sizes_aggregates_subdirs(tmp_path):
    data_root = tmp_path / "vault"
    docs_root = tmp_path / "documents"
    state_root = tmp_path / "state"
    logs_root = tmp_path / "logs"
    cache_root = tmp_path / "cache"

    data_root.mkdir()
    docs_root.mkdir()
    state_root.mkdir()
    logs_root.mkdir()
    cache_root.mkdir()

    (data_root / "a.bin").write_bytes(b"a" * 1024)
    (docs_root / "b.bin").write_bytes(b"b" * 2048)
    (state_root / "c.bin").write_bytes(b"c" * 1024)
    (logs_root / "d.bin").write_bytes(b"d" * 3072)
    (cache_root / "e.bin").write_bytes(b"e" * 4096)

    config = PathConfig(
        core=PathConfig.defaults().core,
        data=PathCategory(
            id="data",
            path=data_root,
            subdirs=[str(docs_root)],
        ),
        plugins=PathConfig.defaults().plugins,
        runtime=PathCategory(
            id="runtime",
            path=state_root,
            subdirs=[str(logs_root), str(cache_root)],
        ),
    )

    config.refresh_sizes()

    assert config.data.size_mb > 0
    assert config.runtime.size_mb > config.data.size_mb
