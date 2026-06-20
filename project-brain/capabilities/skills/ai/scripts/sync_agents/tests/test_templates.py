import sys
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch


scripts_dir = Path(__file__).resolve().parents[2]
if str(scripts_dir) not in sys.path:
    sys.path.insert(0, str(scripts_dir))


def test_capability_policy_placeholder_summarizes_agents_md_exports() -> None:
    from sync_agents import templates

    record = SimpleNamespace(
        id="mcp-tool:act-on-attention-item",
        type="mcp-tool",
        primary_surface="cli",
        preferred_client="shell",
        export_to=("agents-md", "browse"),
        classification_status="approved",
        metadata={"skill": "attention"},
    )

    with (
        patch("src.lib.capabilities.discovery.discover_capabilities", return_value=[]),
        patch(
            "src.lib.capabilities.exposure_policy.resolve_capability_records",
            return_value=[record],
        ),
    ):
        rendered = templates.resolve_placeholders("{{CAPABILITY_POLICY_TABLE}}")
        full_doc = templates.build_capability_exposure_doc()

    # The inline projection carries only the policy paragraph plus a pointer to
    # the externalized full table — not the per-tool rows.
    assert "## Capability Policy Exports" in rendered
    assert templates.CAPABILITY_EXPOSURE_REF in rendered
    assert "(1 capabilities)" in rendered
    assert "`mcp-tool:act-on-attention-item`" not in rendered

    # The full per-tool surface map lives in the externalized reference doc.
    assert full_doc is not None
    assert "`mcp-tool:act-on-attention-item`" in full_doc
    assert "cli via shell" in full_doc
    assert "attention" in full_doc


def test_capability_policy_placeholder_omits_command_catalog_exports() -> None:
    from sync_agents import templates

    command_record = SimpleNamespace(
        id="command:dev-build",
        type="command",
        primary_surface="cli",
        preferred_client="shell",
        export_to=("agents-md", "browse"),
        classification_status="approved",
        metadata={"skill": "daemon"},
    )
    workflow_record = SimpleNamespace(
        id="workflow:auto-lint",
        type="workflow",
        primary_surface="cli",
        preferred_client="shell",
        export_to=("agents-md", "browse"),
        classification_status="approved",
        metadata={"skill": "daemon"},
    )

    with (
        patch("src.lib.capabilities.discovery.discover_capabilities", return_value=[]),
        patch(
            "src.lib.capabilities.exposure_policy.resolve_capability_records",
            return_value=[command_record, workflow_record],
        ),
    ):
        rendered = templates.resolve_placeholders("{{CAPABILITY_POLICY_TABLE}}")

    assert rendered == ""


def test_render_rules_projection_includes_stack_envelope() -> None:
    from sync_agents import templates
    from src.lib.brain_context import ActiveBrainContext
    from src.lib.brain_registry_models import (
        Brain,
        BrainType,
        GitArrangement,
        GitConfig,
    )
    from src.lib.brain_stack import BrainStack, resolve_global_brain

    project = Path("/tmp/repo")
    stack = BrainStack(
        global_brain=resolve_global_brain(core_root=Path("/opt/augur")),
        user_brain=Brain(
            id="personal",
            type=BrainType.PERSONAL,
            data_root=Path("/data/personal"),
            git=GitConfig(arrangement=GitArrangement.UNTRACKED),
        ),
        project=ActiveBrainContext(
            active_brain=Brain(
                id="project-repo",
                type=BrainType.PROJECT,
                data_root=project / "project-brain",
                git=GitConfig(arrangement=GitArrangement.BUNDLED, host_repo=project),
                auto_activate_cwd_under=(project,),
            ),
            attached_project=project,
            source="nearest-project-brain",
        ),
    )

    with patch("src.config.paths.get_active_brain_stack", return_value=stack):
        rendered = templates.render_rules_projection("# Body Marker\n")

    assert "## Augur Context" in rendered
    assert "stack:" in rendered
    assert "augur-core" in rendered
    assert "project-repo" in rendered
    assert "# Body Marker" in rendered


def test_render_rules_projection_includes_standard_brain_files(tmp_path: Path) -> None:
    from sync_agents import templates
    from src.lib.brain_context import ActiveBrainContext
    from src.lib.brain_registry_models import (
        Brain,
        BrainType,
        GitArrangement,
        GitConfig,
    )
    from src.lib.brain_stack import BrainStack, resolve_global_brain

    project = tmp_path / "repo"
    project_brain = project / "project-brain"
    project_brain.mkdir(parents=True)
    (project_brain / "SOUL.md").write_text(
        "---\ntitle: Project Soul\n---\n\n# Project Soul\n\nProject values.\n",
        encoding="utf-8",
    )

    stack = BrainStack(
        global_brain=resolve_global_brain(core_root=tmp_path / "core"),
        user_brain=None,
        project=ActiveBrainContext(
            active_brain=Brain(
                id="project-repo",
                type=BrainType.PROJECT,
                data_root=project_brain,
                git=GitConfig(arrangement=GitArrangement.BUNDLED, host_repo=project),
                auto_activate_cwd_under=(project,),
            ),
            attached_project=project,
            source="nearest-project-brain",
        ),
    )

    with (
        patch("src.config.paths.get_active_brain_stack", return_value=stack),
        patch.object(templates, "PROJECT_ROOT", project),
    ):
        rendered = templates.render_rules_projection("# Body Marker\n")

    assert "## Augur Context" in rendered
    assert "## Standard Brain Files" in rendered
    assert "- Project / SOUL.md — `project-brain/SOUL.md`" in rendered
    assert "Project values." not in rendered  # pointer-only: body is not embedded
    assert "# Body Marker" in rendered
    assert rendered.index("## Augur Context") < rendered.index("## Standard Brain Files")
    assert rendered.index("## Standard Brain Files") < rendered.index("# Body Marker")


def test_render_rules_projection_omits_failed_standard_brain_files_context() -> None:
    from sync_agents import templates
    from src.lib.brain_context import ActiveBrainContext
    from src.lib.brain_registry_models import (
        Brain,
        BrainType,
        GitArrangement,
        GitConfig,
    )
    from src.lib.brain_stack import BrainStack, resolve_global_brain

    project = Path("/tmp/repo")
    stack = BrainStack(
        global_brain=resolve_global_brain(core_root=Path("/opt/augur")),
        user_brain=None,
        project=ActiveBrainContext(
            active_brain=Brain(
                id="project-repo",
                type=BrainType.PROJECT,
                data_root=project / "project-brain",
                git=GitConfig(arrangement=GitArrangement.BUNDLED, host_repo=project),
                auto_activate_cwd_under=(project,),
            ),
            attached_project=project,
            source="nearest-project-brain",
        ),
    )

    with (
        patch("src.config.paths.get_active_brain_stack", return_value=stack),
        patch(
            "src.lib.brain_projection.render_standard_brain_files_context",
            side_effect=RuntimeError("boom"),
        ),
    ):
        rendered = templates.render_rules_projection("# Body Marker\n")

    assert "## Augur Context" in rendered
    assert "## Standard Brain Files" not in rendered
    assert "# Body Marker" in rendered
