from __future__ import annotations

from types import SimpleNamespace

from src.mcp.augur_core.tools.core.skills import list_skill_actions_impl


def _make_resolver(skill_path):
    def _resolve(_name, **_kwargs):
        return SimpleNamespace(path=skill_path)

    return _resolve


def test_list_skill_actions_reads_actions_yaml_full_passthrough(tmp_path):
    skill_dir = tmp_path / "demo-skill"
    augur_dir = skill_dir / "augur"
    augur_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: demo-skill\n---\n", encoding="utf-8")
    (augur_dir / "actions.yaml").write_text(
        "actions:\n"
        "  - id: demo-health\n"
        "    label: Demo Health\n"
        "    icon: Activity\n"
        "    kind: mcp\n"
        "    mcp_tool: get-skill-health\n"
        "    dispatch: fire\n"
        "    surfaces: [page]\n",
        encoding="utf-8",
    )

    result = list_skill_actions_impl(skill_id="demo-skill", resolve_skill_entry=_make_resolver(skill_dir))

    assert "actions" in result
    assert len(result["actions"]) == 1
    action = result["actions"][0]
    assert action["id"] == "demo-health"
    assert action["label"] == "Demo Health"
    assert action["icon"] == "Activity"
    assert action["dispatch"] == "fire"
    # The current impl DROPS mcp_tool; this asserts the passthrough.
    assert action["mcp_tools"] == ["get-skill-health"]
    # description falls back to label
    assert action["description"] == "Demo Health"


def test_list_skill_actions_filters_to_page_surface(tmp_path):
    skill_dir = tmp_path / "demo-skill"
    augur_dir = skill_dir / "augur"
    augur_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: demo-skill\n---\n", encoding="utf-8")
    (augur_dir / "actions.yaml").write_text(
        "actions:\n"
        "  - id: page-action\n"
        "    label: Page Action\n"
        "    kind: mcp\n"
        "    mcp_tool: get-skill-health\n"
        "    dispatch: fire\n"
        "    surfaces: [page]\n"
        "  - id: card-only\n"
        "    label: Card Only\n"
        "    kind: mcp\n"
        "    mcp_tool: get-skill-health\n"
        "    dispatch: fire\n"
        "    surfaces: [card]\n"
        "    categories: [misc]\n",
        encoding="utf-8",
    )

    result = list_skill_actions_impl(skill_id="demo-skill", resolve_skill_entry=_make_resolver(skill_dir))

    ids = [a["id"] for a in result["actions"]]
    assert ids == ["page-action"]


def test_list_skill_actions_no_yaml_returns_empty(tmp_path):
    skill_dir = tmp_path / "demo-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: demo-skill\n---\n", encoding="utf-8")

    result = list_skill_actions_impl(skill_id="demo-skill", resolve_skill_entry=_make_resolver(skill_dir))

    assert result == {"actions": []}


def test_list_skill_actions_unknown_skill_returns_empty(tmp_path):
    def _resolve(_name, **_kwargs):
        return None

    result = list_skill_actions_impl(skill_id="nope", resolve_skill_entry=_resolve)
    assert result == {"actions": []}
