from __future__ import annotations

from pathlib import Path

import pytest

from src.lib.brain_manifest import (
    BRAIN_MANIFEST_NAME,
    PROJECT_BRAIN_DIRNAME,
    STANDARD_BRAIN_FILES,
    BrainManifest,
    ensure_brain_skeleton,
    find_project_brain_root,
    read_brain_manifest,
    write_brain_manifest,
)
from src.lib.brain_registry_models import BrainType
from src.lib.frontmatter_utils import parse_frontmatter

EXPECTED_STANDARD_BRAIN_FILES = (
    "IDENTITY.md",
    "SOUL.md",
    "USER.md",
    "AGENTS.md",
    "MEMORY.md",
    "TOOLS.md",
    "HEARTBEAT.md",
)


def test_write_and_read_brain_manifest(tmp_path: Path) -> None:
    root = tmp_path / "project-brain"
    manifest = BrainManifest(
        schema_version=1,
        id="project-demo",
        type=BrainType.PROJECT,
        root=str(root),
        attached_project=str(tmp_path),
    )

    write_brain_manifest(root, manifest)

    loaded = read_brain_manifest(root / BRAIN_MANIFEST_NAME)
    assert loaded == manifest


def test_ensure_brain_skeleton_creates_expected_dirs(tmp_path: Path) -> None:
    root = tmp_path / PROJECT_BRAIN_DIRNAME
    ensure_brain_skeleton(root)

    for rel in (
        "capabilities/skills",
        "capabilities/agents",
        "knowledge/memory/entries",
        "knowledge/notes",
        "knowledge/sources",
        "knowledge/wiki",
        "decisions/adrs",
        "config",
    ):
        assert (root / rel).is_dir(), rel


def test_ensure_brain_skeleton_creates_standard_root_files(tmp_path: Path) -> None:
    root = tmp_path / PROJECT_BRAIN_DIRNAME

    ensure_brain_skeleton(root)

    assert STANDARD_BRAIN_FILES == EXPECTED_STANDARD_BRAIN_FILES
    for filename in EXPECTED_STANDARD_BRAIN_FILES:
        path = root / filename
        assert path.is_file(), filename
        metadata, body = parse_frontmatter(path, include_sidecar_config=False)
        text = path.read_text(encoding="utf-8")
        assert text.startswith("---\n"), filename
        assert "\n---\n\n" in text, filename
        assert metadata["title"], filename
        assert metadata["brain_scope"] == "unknown", filename
        assert metadata["status"] == "active", filename
        assert metadata["owner"] == "unknown", filename
        assert f"# {path.stem.title().replace('-', ' ')}" in body or filename == "AGENTS.md"


@pytest.mark.parametrize("filename", EXPECTED_STANDARD_BRAIN_FILES)
def test_ensure_brain_skeleton_does_not_overwrite_standard_root_files(
    tmp_path: Path,
    filename: str,
) -> None:
    root = tmp_path / PROJECT_BRAIN_DIRNAME
    root.mkdir()
    path = root / filename
    path.write_text("---\ntitle: Custom\n---\n\n# Custom\n", encoding="utf-8")

    ensure_brain_skeleton(root)

    assert path.read_text(encoding="utf-8") == "---\ntitle: Custom\n---\n\n# Custom\n"


def test_find_project_brain_root_walks_up_from_nested_dir(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    nested = project / "src" / "firmware"
    nested.mkdir(parents=True)
    brain = project / PROJECT_BRAIN_DIRNAME
    ensure_brain_skeleton(brain)
    write_brain_manifest(
        brain,
        BrainManifest(
            schema_version=1,
            id="project-repo",
            type=BrainType.PROJECT,
            root=str(brain),
            attached_project=str(project),
        ),
    )

    assert find_project_brain_root(nested) == brain


def test_read_brain_manifest_rejects_unknown_type(tmp_path: Path) -> None:
    manifest = tmp_path / BRAIN_MANIFEST_NAME
    manifest.write_text(
        "schema_version: 1\nid: x\ntype: work\nroot: /tmp/x\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="invalid brain type"):
        read_brain_manifest(manifest)


@pytest.mark.parametrize(
    ("content", "field"),
    (
        ("schema_version: 1\ntype: project\nroot: /tmp/x\n", "id"),
        ("schema_version: 1\nid: x\nroot: /tmp/x\n", "type"),
        ("schema_version: 1\nid: x\ntype: project\n", "root"),
        ("schema_version: 1\nid: null\ntype: project\nroot: /tmp/x\n", "id"),
        ("schema_version: 1\nid: x\ntype: null\nroot: /tmp/x\n", "type"),
        ("schema_version: 1\nid: x\ntype: project\nroot: null\n", "root"),
        ('schema_version: 1\nid: " "\ntype: project\nroot: /tmp/x\n', "id"),
        ('schema_version: 1\nid: x\ntype: " "\nroot: /tmp/x\n', "type"),
        ('schema_version: 1\nid: x\ntype: project\nroot: ""\n', "root"),
    ),
)
def test_read_brain_manifest_rejects_missing_required_fields(
    tmp_path: Path,
    content: str,
    field: str,
) -> None:
    manifest = tmp_path / BRAIN_MANIFEST_NAME
    manifest.write_text(content, encoding="utf-8")

    with pytest.raises(ValueError, match=f"missing required BRAIN.yaml field: {field}"):
        read_brain_manifest(manifest)


def test_read_brain_manifest_rejects_non_dict_content(tmp_path: Path) -> None:
    manifest = tmp_path / BRAIN_MANIFEST_NAME
    manifest.write_text("[]\n", encoding="utf-8")

    with pytest.raises(ValueError, match="invalid BRAIN.yaml content"):
        read_brain_manifest(manifest)
