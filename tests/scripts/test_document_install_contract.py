import tomllib

from src.config.paths import get_project_root

PROJECT_ROOT = get_project_root()
PYPROJECT = PROJECT_ROOT / "pyproject.toml"


def test_pyproject_promotes_pymupdf_to_base_dependency_without_legacy_mlx_vlm():
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))

    dependencies = data["project"]["dependencies"]
    optional = data["project"]["optional-dependencies"]

    assert any(dep.startswith("pymupdf>=") for dep in dependencies)
    assert all(not dep.startswith("pymupdf>=") for dep in optional["ocr"])
    assert all("mlx-vlm" not in dep for dep in optional["ocr"])


def test_pyproject_includes_ruff_in_default_dev_dependency_group():
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))

    dev_group = data["dependency-groups"]["dev"]

    assert any(dep.startswith("ruff>=") for dep in dev_group)
