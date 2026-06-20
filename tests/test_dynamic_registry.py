"""Auto-generated importability test for dynamic_registry."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_dynamic_registry_importable():
    """Verify that dynamic_registry can be imported without errors."""
    import src.mcp.augur_shared.dynamic_registry

    assert src.mcp.augur_shared.dynamic_registry is not None


def test_command_skill_prompt_specs_are_deduplicated():
    """Slash and bare command triggers must not register duplicate MCP prompt names."""
    from src.mcp.augur_shared.dynamic_registry import _build_prompt_specs
    from src.plugins.skill_discovery import SkillMetadata

    commands_skill = SkillMetadata(
        id="commands",
        display_name="commands",
        description="Show all available slash commands",
        triggers=("/commands", "commands"),
        capabilities=(),
        token_estimate=0,
        has_modules=False,
        has_scripts=False,
        has_references=False,
        has_context=False,
        path=Path("/tmp/commands"),
        aliases=(),
    )

    specs = _build_prompt_specs(commands_skill)

    assert [spec.name for spec in specs] == ["commands"]
    assert [spec.trigger for spec in specs] == ["/commands"]
    assert [spec.title for spec in specs] == ["/commands"]
    assert [spec.description for spec in specs] == ["Show all available slash commands"]


def test_dynamic_registration_skips_tier2_client_skill_wrappers(tmp_path, monkeypatch):
    """Generated client command wrappers must not feed back into MCP prompts."""
    import src.mcp.augur_shared.dynamic_registry as registry

    prompts: list[str] = []
    resources: list[str] = []

    class FakeMCP:
        def resource(self, uri, **kwargs):
            resources.append(kwargs.get("name") or uri)

            def decorator(func):
                return func

            return decorator

        def prompt(self, **kwargs):
            prompts.append(kwargs["name"])

            def decorator(func):
                return func

            return decorator

    canonical_skill = SimpleNamespace(
        name="onboard",
        id="onboard",
        description="Set up Augur",
        triggers=("/onboard", "onboard"),
        path=tmp_path / "skills" / "onboard",
        tier=0,
    )
    client_wrapper = SimpleNamespace(
        name="dev-loops",
        id="dev-loops",
        description="Manage adaptive loops",
        triggers=("/dev-loops", "dev-loops"),
        path=tmp_path / ".codex" / "skills" / "dev-loops",
        origin="codex-local",
        tier=2,
    )

    monkeypatch.setattr(registry, "_dynamic_registered", False)
    monkeypatch.setattr(
        registry,
        "registry_list_skills",
        lambda **_kwargs: [canonical_skill, client_wrapper],
    )

    registry.register_dynamic_capabilities(
        mcp=FakeMCP(),
        skills_dir=tmp_path / "skills",
        metrics=None,
        logger=SimpleNamespace(info=lambda *_args, **_kwargs: None),
    )

    assert "onboard" in prompts
    assert "dev-loops" not in prompts
    assert "onboard/overview" in resources
    assert "dev-loops/overview" not in resources
