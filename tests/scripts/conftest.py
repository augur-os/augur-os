"""Keep repo-root ``scripts`` imports stable for script tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ROOT_SCRIPTS = PROJECT_ROOT / "scripts" / "__init__.py"


def _prefer_repo_root_scripts_package() -> None:
    if str(PROJECT_ROOT) in sys.path:
        sys.path.remove(str(PROJECT_ROOT))
    sys.path.insert(0, str(PROJECT_ROOT))

    loaded = sys.modules.get("scripts")
    if loaded is not None and Path(getattr(loaded, "__file__", "")).resolve() != ROOT_SCRIPTS:
        sys.modules.pop("scripts", None)


_prefer_repo_root_scripts_package()


@pytest.fixture(autouse=True)
def _restore_repo_root_scripts_package():
    _prefer_repo_root_scripts_package()
