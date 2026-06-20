from __future__ import annotations

import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.mcp.plugin_utils import SkillDataStore  # noqa: E402
from src.lib.frontmatter_utils import write_frontmatter  # noqa: E402


def _write_yaml(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")


def _write_skill_md(path: Path, *, name: str, hub: str = "test", config: dict | None = None) -> None:
    metadata = {
        "name": name,
        "description": f"{name} skill",
        "x-augur-hub": hub,
    }
    if config is not None:
        metadata["x-augur-config"] = config
    write_frontmatter(path, metadata, f"# {name}\n")


def test_skill_data_store_reads_from_vault_before_assets(monkeypatch, tmp_path):
    repo_root = tmp_path / "repo"
    vault_root = tmp_path / "vault"
    skill_root = repo_root / "plugins" / "career" / "skills" / "career"
    skill_root.mkdir(parents=True)

    monkeypatch.setenv("AUGUR_ROOT", str(repo_root))
    monkeypatch.setenv("AUGUR_VAULT", str(vault_root))
    monkeypatch.setattr("src.config.paths.get_skill_data_dir", lambda name: vault_root / name)

    _write_skill_md(skill_root / "SKILL.md", name="career")
    _write_yaml(skill_root / "assets" / "seeds" / "jobs.yaml", {"jobs": [{"id": "asset"}]})
    _write_yaml(vault_root / "career" / "jobs.yaml", {"jobs": [{"id": "vault"}]})

    store = SkillDataStore(skill_root)

    assert store.config["name"] == "career"
    assert store.read("jobs.yaml") == {"jobs": [{"id": "vault"}]}


def test_skill_data_store_falls_back_to_seed_assets_and_writes_to_vault(monkeypatch, tmp_path):
    repo_root = tmp_path / "repo"
    vault_root = tmp_path / "vault"
    skill_root = repo_root / "plugins" / "health" / "skills" / "health"
    skill_root.mkdir(parents=True)

    monkeypatch.setenv("AUGUR_ROOT", str(repo_root))
    monkeypatch.setenv("AUGUR_VAULT", str(vault_root))
    monkeypatch.setattr("src.config.paths.get_skill_data_dir", lambda name: vault_root / name)

    _write_skill_md(skill_root / "SKILL.md", name="health")
    _write_yaml(skill_root / "assets" / "seeds" / "symptoms.yaml", {"symptoms": [{"id": "seed"}]})

    store = SkillDataStore(skill_root)

    assert store.read("symptoms.yaml") == {"symptoms": [{"id": "seed"}]}

    store.write("symptoms.yaml", {"symptoms": [{"id": "user"}]})

    written_path = vault_root / "health" / "symptoms.yaml"
    assert written_path.exists()
    assert yaml.safe_load(written_path.read_text(encoding="utf-8")) == {"symptoms": [{"id": "user"}]}
