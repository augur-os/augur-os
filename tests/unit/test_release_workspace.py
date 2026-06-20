from __future__ import annotations

from pathlib import Path
from subprocess import run
import sys

import pytest

from src.lib.release_workspace import prune_release_workspace


def test_prune_release_workspace_removes_disabled_skill(tmp_path: Path):
    skills = tmp_path / "project-brain" / "capabilities" / "skills"
    keep = skills / "knowledge"
    drop = skills / "content"
    for skill in (keep, drop):
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(
            (
                "---\n"
                f"name: {skill.name}\n"
                "description: test\n"
                f"x-augur-group: {'brain' if skill.name == 'knowledge' else 'business'}\n"
                f"x-augur-release: {'mvp' if skill.name == 'knowledge' else 'r1'}\n"
                "---\n"
            ),
            encoding="utf-8",
        )

    report = prune_release_workspace(tmp_path, "mvp")

    assert report["enabled"] == ["knowledge"]
    assert report["removed"] == ["content"]
    assert keep.exists()
    assert not drop.exists()


def test_prune_release_workspace_removes_private_mvp_artifacts(tmp_path: Path):
    skills = tmp_path / "project-brain" / "capabilities" / "skills"
    keep = skills / "knowledge"
    keep.mkdir(parents=True)
    (keep / "SKILL.md").write_text(
        ("---\n" "name: knowledge\n" "description: test\n" "x-augur-group: brain\n" "x-augur-release: mvp\n" "---\n"),
        encoding="utf-8",
    )
    (tmp_path / "docs" / "superpowers").mkdir(parents=True)
    (tmp_path / "docs" / "superpowers" / "plan.md").write_text("private plan\n", encoding="utf-8")
    (tmp_path / "docs" / "generated").mkdir(parents=True)
    (tmp_path / "docs" / "generated" / "vault-cleanup-report.md").write_text(
        "local vault report\n",
        encoding="utf-8",
    )
    references = keep / "references"
    references.mkdir()
    (references / "additional-resources.md").write_text("local repair traces\n", encoding="utf-8")

    report = prune_release_workspace(tmp_path, "mvp")

    assert report["removed_artifacts"] == [
        "docs/generated/vault-cleanup-report.md",
        "docs/superpowers",
        "project-brain/capabilities/skills/knowledge/references/additional-resources.md",
    ]
    assert not (tmp_path / "docs" / "superpowers").exists()
    assert not (tmp_path / "docs" / "generated" / "vault-cleanup-report.md").exists()
    assert not (references / "additional-resources.md").exists()


def test_prune_release_workspace_fails_on_disabled_dependency(tmp_path: Path):
    skills = tmp_path / "project-brain" / "capabilities" / "skills"
    knowledge = skills / "knowledge"
    rag = skills / "rag"
    for skill in (knowledge, rag):
        skill.mkdir(parents=True)

    (knowledge / "SKILL.md").write_text(
        (
            "---\n"
            "name: knowledge\n"
            "description: test\n"
            "x-augur-group: brain\n"
            "x-augur-release: mvp\n"
            "x-augur-dependencies:\n"
            "  rag:\n"
            "    kind: required\n"
            "---\n"
        ),
        encoding="utf-8",
    )
    (rag / "SKILL.md").write_text(
        ("---\n" "name: rag\n" "description: test\n" "x-augur-group: brain\n" "x-augur-release: r2\n" "---\n"),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="knowledge -> rag"):
        prune_release_workspace(tmp_path, "mvp")


def test_prune_release_workspace_reads_sidecar_config_dependencies(tmp_path: Path):
    skills = tmp_path / "project-brain" / "capabilities" / "skills"
    knowledge = skills / "knowledge"
    rag = skills / "rag"
    for skill in (knowledge, rag):
        skill.mkdir(parents=True)

    (knowledge / "SKILL.md").write_text(
        (
            "---\n"
            "name: knowledge\n"
            "description: test\n"
            "x-augur-group: brain\n"
            "x-augur-release: mvp\n"
            "x-augur-config-file: config.yaml\n"
            "---\n"
        ),
        encoding="utf-8",
    )
    (knowledge / "config.yaml").write_text(
        "dependencies:\n  rag:\n    kind: required\n",
        encoding="utf-8",
    )
    (rag / "SKILL.md").write_text(
        ("---\n" "name: rag\n" "description: test\n" "x-augur-group: brain\n" "x-augur-release: r2\n" "---\n"),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="knowledge -> rag"):
        prune_release_workspace(tmp_path, "mvp")


def test_prune_release_workspace_removes_owner_private_memory_layer(tmp_path: Path):
    """ADR-814: project-brain/knowledge/memory and MEMORY.md are pruned on mvp release."""
    skills = tmp_path / "project-brain" / "capabilities" / "skills"
    keep = skills / "knowledge"
    keep.mkdir(parents=True)
    (keep / "SKILL.md").write_text(
        ("---\n" "name: knowledge\n" "description: test\n" "x-augur-group: brain\n" "x-augur-release: mvp\n" "---\n"),
        encoding="utf-8",
    )

    # Create the owner-private memory layer
    memory_entries = tmp_path / "project-brain" / "knowledge" / "memory" / "entries"
    memory_entries.mkdir(parents=True)
    entry_file = memory_entries / "private-fact.md"
    entry_file.write_text("---\ntitle: private\n---\nOwner secret.\n", encoding="utf-8")
    memory_index = tmp_path / "project-brain" / "MEMORY.md"
    memory_index.write_text("# Memory\n\n- private-fact\n", encoding="utf-8")

    report = prune_release_workspace(tmp_path, "mvp")

    assert "project-brain/knowledge/memory" in report["removed_artifacts"]
    assert "project-brain/MEMORY.md" in report["removed_artifacts"]
    assert not (tmp_path / "project-brain" / "knowledge" / "memory").exists()
    assert not memory_index.exists()


def test_prepare_release_workspace_cli_accepts_r4(tmp_path: Path) -> None:
    result = run(
        [
            sys.executable,
            "scripts/prepare_release_workspace.py",
            "--project-root",
            str(tmp_path),
            "--release-target",
            "r4",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
