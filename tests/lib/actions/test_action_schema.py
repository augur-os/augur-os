from pathlib import Path
from src.lib.actions.action_schema import load_actions_yaml, ActionSchemaError


def test_loads_valid_mcp_fire_action(tmp_path: Path):
    f = tmp_path / "actions.yaml"
    f.write_text(
        "actions:\n"
        "  - id: rag-reindex\n"
        "    label: Reindex\n"
        "    kind: mcp\n"
        "    mcp_tool: reindex-browse-category\n"
        "    dispatch: fire\n"
        "    surfaces: [page]\n"
    )
    actions = load_actions_yaml(f)
    assert actions[0].id == "rag-reindex"
    assert actions[0].kind == "mcp"
    assert actions[0].surfaces == ["page"]


def test_fire_without_mcp_tool_is_rejected(tmp_path: Path):
    f = tmp_path / "actions.yaml"
    f.write_text("actions:\n  - id: x\n    label: X\n    kind: ai\n    dispatch: fire\n    template: hi\n")
    try:
        load_actions_yaml(f)
        assert False, "expected ActionSchemaError"
    except ActionSchemaError as e:
        assert "fire" in str(e)


def test_card_surface_requires_categories(tmp_path: Path):
    f = tmp_path / "actions.yaml"
    f.write_text("actions:\n  - id: y\n    label: Y\n    kind: ai\n    template: t\n    surfaces: [card]\n")
    try:
        load_actions_yaml(f)
        assert False
    except ActionSchemaError as e:
        assert "categories" in str(e)


def test_scheduled_action_requires_fire_mcp(tmp_path: Path):
    f = tmp_path / "actions.yaml"
    f.write_text(
        "actions:\n  - id: nightly\n    label: Nightly\n    kind: ai\n    template: hi\n"
        "    surfaces: [page]\n    schedule: {enabled: true, frequency: daily, time: '03:00'}\n"
    )
    try:
        load_actions_yaml(f)
        assert False, "expected ActionSchemaError"
    except ActionSchemaError as e:
        assert "schedule" in str(e)


def test_scheduled_fire_mcp_action_loads(tmp_path: Path):
    f = tmp_path / "actions.yaml"
    f.write_text(
        "actions:\n  - id: nightly\n    label: Nightly\n    kind: mcp\n    mcp_tool: reindex-browse-category\n"
        "    dispatch: fire\n    surfaces: [page]\n    schedule: {enabled: true, frequency: daily, time: '03:00'}\n"
    )
    actions = load_actions_yaml(f)
    assert actions[0].schedule["frequency"] == "daily"
