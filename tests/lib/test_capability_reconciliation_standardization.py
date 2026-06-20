from __future__ import annotations

from src.lib.capabilities.exposure_policy import CapabilityRecord
from src.lib.capabilities.reconciliation import build_capability_report


def _record(**overrides) -> CapabilityRecord:
    defaults = dict(
        id="mcp-tool:get-pending",
        type="mcp-tool",
        owner_kind="user",
        management="generated",
        scope="project",
        primary_surface="mcp",
        preferred_client="shell",
        export_to=(),
        classification_status="unclassified",
        source_paths=("/Users/example/Au-vault/skills/file-manager/SKILL.md",),
        current_exposure=("mcp", "browse"),
        drift=("direct_mcp_exposure",),
        metadata={"skill": "file-manager"},
    )
    defaults.update(overrides)
    return CapabilityRecord(**defaults)


def test_private_unclassified_mcp_tool_recommends_review_not_auto_move() -> None:
    report = build_capability_report([_record()])

    recommended = report["records"][0]["recommended_action"]

    assert recommended == {
        "id": "review_private_skill_policy",
        "label": "Review private skill policy",
        "params": {
            "suggested_primary_surface": "cli",
            "requires_approval": True,
        },
    }


def test_invalid_primary_surface_recommends_canonical_surface() -> None:
    report = build_capability_report(
        [
            _record(
                owner_kind="augur",
                primary_surface="mcp-tool",
            )
        ]
    )

    recommended = report["records"][0]["recommended_action"]

    assert recommended["id"] == "fix_primary_surface"
    assert recommended["params"]["allowed"] == [
        "cli",
        "mcp",
        "mcp via dashboard",
    ]


def test_augur_generated_valid_mcp_tool_still_recommends_cli_only() -> None:
    report = build_capability_report(
        [
            _record(
                owner_kind="augur",
                classification_status="approved",
                current_exposure=("mcp",),
            )
        ]
    )

    assert report["records"][0]["recommended_action"] == {
        "id": "move_to_cli_only",
        "label": "Move to CLI only",
        "params": {},
    }
