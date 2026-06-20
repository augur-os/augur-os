from __future__ import annotations

import json
from pathlib import Path

from src.lib.brain_context import ActiveBrainContext
from src.lib.brain_registry_models import (
    Brain,
    BrainType,
    GitArrangement,
    GitConfig,
)
from src.lib.brain_stack import BrainStack, resolve_global_brain


def _brain(brain_id: str, brain_type: BrainType, root: Path, project: Path | None = None) -> Brain:
    git = (
        GitConfig(arrangement=GitArrangement.BUNDLED, host_repo=project)
        if brain_type is BrainType.PROJECT and project is not None
        else GitConfig(arrangement=GitArrangement.UNTRACKED)
    )
    return Brain(
        id=brain_id,
        type=brain_type,
        data_root=root,
        git=git,
        auto_activate_cwd_under=(project,) if project is not None else (),
    )


def _write_profile_yaml(root: Path, content: str) -> None:
    profile_dir = root / "profile"
    profile_dir.mkdir(parents=True)
    (profile_dir / "profile.yaml").write_text(content, encoding="utf-8")


def test_resolve_profile_overlay_deep_merges_tiers_most_specific_wins(
    tmp_path: Path,
) -> None:
    from src.lib.brain_profile_overlay import resolve_profile_overlay

    core = tmp_path / "core"
    _write_profile_yaml(
        core,
        """
identity:
  name: Augur
  locale: en
preferences:
  timezone: UTC
  notifications:
    digest: weekly
    channels:
      email: true
global_only:
  retained: true
""",
    )

    vault = tmp_path / "vault"
    _write_profile_yaml(
        vault,
        """
identity:
  name: Guri
preferences:
  timezone: Asia/Jerusalem
  notifications:
    channels:
      sms: false
user_only: present
""",
    )

    project = tmp_path / "repo"
    project_brain = project / "project-brain"
    _write_profile_yaml(
        project_brain,
        """
preferences:
  notifications:
    digest: daily
project:
  role: maintainer
""",
    )

    stack = BrainStack(
        global_brain=resolve_global_brain(core_root=core),
        user_brain=_brain("personal", BrainType.PERSONAL, vault),
        project=ActiveBrainContext(
            active_brain=_brain("project-augur", BrainType.PROJECT, project_brain, project),
            attached_project=project,
            source="nearest-project-brain",
        ),
    )

    assert resolve_profile_overlay(stack) == {
        "identity": {
            "name": "Guri",
            "locale": "en",
        },
        "preferences": {
            "timezone": "Asia/Jerusalem",
            "notifications": {
                "digest": "daily",
                "channels": {
                    "email": True,
                    "sms": False,
                },
            },
        },
        "global_only": {"retained": True},
        "user_only": "present",
        "project": {"role": "maintainer"},
    }


def test_resolve_profile_overlay_reads_json_and_markdown_frontmatter(
    tmp_path: Path,
) -> None:
    from src.lib.brain_profile_overlay import resolve_profile_overlay

    core = tmp_path / "core"
    profile_dir = core / "profile"
    profile_dir.mkdir(parents=True)
    (profile_dir / "profile.json").write_text(
        json.dumps({"identity": {"name": "Augur"}, "source": "json"}),
        encoding="utf-8",
    )
    (profile_dir / "persona.md").write_text(
        "---\nidentity:\n  tone: direct\nsource: markdown\n---\n\nBody.\n",
        encoding="utf-8",
    )

    stack = BrainStack(
        global_brain=resolve_global_brain(core_root=core),
        user_brain=None,
        project=None,
    )

    assert resolve_profile_overlay(stack) == {
        "identity": {
            "name": "Augur",
            "tone": "direct",
        },
        "source": "markdown",
    }


def test_resolve_profile_overlay_reads_root_standard_file_frontmatter_then_profile_dir(
    tmp_path: Path,
) -> None:
    from src.lib.brain_profile_overlay import resolve_profile_overlay

    core = tmp_path / "core"
    core.mkdir()
    (core / "IDENTITY.md").write_text(
        "---\nidentity:\n  name: Root Identity\n  public: true\n---\n\n# Identity\n",
        encoding="utf-8",
    )
    _write_profile_yaml(
        core,
        """
identity:
  name: Structured Identity
preferences:
  timezone: UTC
""",
    )

    stack = BrainStack(
        global_brain=resolve_global_brain(core_root=core),
        user_brain=None,
        project=None,
    )

    assert resolve_profile_overlay(stack) == {
        "identity": {
            "name": "Structured Identity",
            "public": True,
        },
        "preferences": {
            "timezone": "UTC",
        },
    }


def test_resolve_profile_overlay_ignores_standard_file_document_metadata(
    tmp_path: Path,
) -> None:
    from src.lib.brain_manifest import ensure_brain_skeleton
    from src.lib.brain_profile_overlay import resolve_profile_overlay

    core = tmp_path / "core"
    ensure_brain_skeleton(core)

    stack = BrainStack(
        global_brain=resolve_global_brain(core_root=core),
        user_brain=None,
        project=None,
    )

    assert resolve_profile_overlay(stack) == {}


def test_resolve_profile_overlay_dedupes_coincident_brain_roots(
    tmp_path: Path,
) -> None:
    from src.lib.brain_profile_overlay import resolve_profile_overlay

    project = tmp_path / "repo"
    project_brain = project / "project-brain"
    project_brain.mkdir(parents=True)
    (project_brain / "IDENTITY.md").write_text(
        "---\nidentity:\n  name: Shared Root\n---\n\n# Identity\n",
        encoding="utf-8",
    )

    stack = BrainStack(
        global_brain=resolve_global_brain(core_root=project_brain),
        user_brain=None,
        project=ActiveBrainContext(
            active_brain=_brain(
                "project-repo",
                BrainType.PROJECT,
                project_brain,
                project,
            ),
            attached_project=project,
            source="nearest-project-brain",
        ),
    )

    assert resolve_profile_overlay(stack) == {
        "identity": {
            "name": "Shared Root",
        },
    }
