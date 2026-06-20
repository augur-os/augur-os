"""Behavior tests for setup registry loader."""

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
SETUP_DIR = PROJECT_ROOT / "project-brain" / "capabilities" / "skills" / "onboard" / "scripts" / "setup"
REGISTRY_PATH = (
    PROJECT_ROOT / "project-brain" / "capabilities" / "skills" / "onboard" / "config" / "setup-items.yaml"
)

PKG = "onboard_setup_pkg"


def _ensure_package() -> None:
    if PKG in sys.modules:
        return
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    spec = importlib.util.spec_from_file_location(
        PKG,
        SETUP_DIR / "__init__.py",
        submodule_search_locations=[str(SETUP_DIR)],
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[PKG] = module
    spec.loader.exec_module(module)


_ensure_package()
registry = importlib.import_module(f"{PKG}.registry")
RegistryError = registry.RegistryError
load_registry = registry.load_registry


def test_load_registry_finds_12_items_in_3_phases() -> None:
    reg = load_registry(REGISTRY_PATH)

    assert reg.version == 1
    assert [phase.id for phase in reg.phases] == [
        "foundation",
        "knowledge",
        "personalization",
    ]
    assert sum(len(phase.items) for phase in reg.phases) == 12


def test_registry_item_ids_are_unique_and_actions_are_valid() -> None:
    reg = load_registry(REGISTRY_PATH)

    ids = [item.id for phase in reg.phases for item in phase.items]
    assert len(ids) == len(set(ids))
    for phase in reg.phases:
        for item in phase.items:
            assert item.label
            assert item.description
            assert "." in item.probe
            assert item.action.label
            if item.action.type == "route":
                assert item.action.route and item.action.route.startswith("/")
            elif item.action.type == "command":
                assert item.action.command and item.action.command.startswith("/")
            elif item.action.type == "mcp":
                assert item.action.mcp_tool
            else:
                raise AssertionError(f"unexpected action type {item.action.type}")


def test_load_registry_rejects_duplicate_ids(tmp_path: Path) -> None:
    registry_file = tmp_path / "setup-items.yaml"
    registry_file.write_text(
        """
version: 1
phases:
  - id: foundation
    label: Foundation
    items:
      - id: duplicate
        label: One
        description: First
        probe: foundation.vault
        action: {type: route, route: /settings, label: Open}
  - id: knowledge
    label: Knowledge
    items:
      - id: duplicate
        label: Two
        description: Second
        probe: knowledge.wiki_pages_5
        action: {type: command, command: /wiki-status, label: Check}
""",
        encoding="utf-8",
    )

    with pytest.raises(RegistryError, match="duplicate"):
        load_registry(registry_file)
