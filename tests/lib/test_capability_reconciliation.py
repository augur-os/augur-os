from typing import cast

from src.lib.capabilities.exposure_policy import (
    CapabilityRecord,
    CapabilityType,
    ClassificationStatus,
    Management,
    OwnerKind,
)
from src.lib.capabilities.reconciliation import build_capability_report


def _record(
    capability_id: str,
    *,
    capability_type: str = "skill",
    owner_kind: str = "augur",
    management: str = "generated",
    classification_status: str = "approved",
    current_exposure: tuple[str, ...] = (),
    drift: tuple[str, ...] = (),
    metadata: dict[str, str] | None = None,
    primary_surface: str | None = None,
) -> CapabilityRecord:
    return CapabilityRecord(
        id=capability_id,
        type=cast(CapabilityType, capability_type),  # type: ignore[arg-type]
        owner_kind=cast(OwnerKind, owner_kind),  # type: ignore[arg-type]
        management=cast(Management, management),  # type: ignore[arg-type]
        scope="project",
        primary_surface=primary_surface or capability_type,
        preferred_client="codex",
        export_to=("codex",),
        classification_status=cast(ClassificationStatus, classification_status),  # type: ignore[arg-type]
        source_paths=("project-brain/capabilities/skills/example/SKILL.md",),
        current_exposure=current_exposure,
        drift=drift,
        metadata=metadata or {},
    )


def test_report_counts_by_fields_and_client_exposure() -> None:
    report = build_capability_report(
        [
            _record(
                "skill:alpha",
                owner_kind="external",
                management="unmanaged",
                classification_status="unclassified",
                current_exposure=("gemini", "opencode"),
                drift=("duplicate", "unclassified_export"),
            ),
            _record(
                "mcp-tool:ask",
                capability_type="mcp-tool",
                current_exposure=("gemini",),
                drift=("unexpected_client",),
            ),
            _record(
                "command:dev-build",
                capability_type="command",
                classification_status="deprecated",
                current_exposure=("codex",),
            ),
        ]
    )

    assert report["counts"] == {
        "total": 3,
        "by_type": {"command": 1, "mcp-tool": 1, "skill": 1},
        "by_owner": {"augur": 2, "external": 1},
        "by_management": {"generated": 2, "unmanaged": 1},
        "by_status": {"approved": 1, "deprecated": 1, "unclassified": 1},
        "by_drift": {"duplicate": 1, "unexpected_client": 1, "unclassified_export": 1},
        "gemini_exposed": 2,
        "opencode_exposed": 1,
    }


def test_duplicate_clusters_are_serialized_and_sorted_by_id() -> None:
    report = build_capability_report(
        [
            _record(
                "skill:zeta",
                owner_kind="external",
                current_exposure=("claude", "codex"),
                drift=("duplicate",),
            ),
            _record("skill:middle", current_exposure=("codex",), drift=()),
            _record(
                "mcp-server:alpha",
                capability_type="mcp-server",
                current_exposure=("gemini", "opencode"),
                drift=("duplicate", "unexpected_client"),
            ),
        ]
    )

    assert report["duplicate_clusters"] == [
        {
            "id": "mcp-server:alpha",
            "type": "mcp-server",
            "owner_kind": "augur",
            "current_exposure": ["gemini", "opencode"],
        },
        {
            "id": "skill:zeta",
            "type": "skill",
            "owner_kind": "external",
            "current_exposure": ["claude", "codex"],
        },
    ]


def test_external_geo_duplicate_skill_recommends_claude_only() -> None:
    report = build_capability_report(
        [
            _record(
                "skill:geo-audit",
                owner_kind="external",
                management="unmanaged",
                current_exposure=("claude", "codex"),
                drift=("duplicate",),
            )
        ]
    )

    assert report["records"][0]["recommended_action"] == {
        "id": "keep_only_in_client",
        "label": "Keep only in Claude",
        "params": {"target_client": "claude"},
    }


def test_augur_generated_mcp_tool_recommends_cli_only() -> None:
    report = build_capability_report(
        [
            _record(
                "mcp-tool:ask",
                capability_type="mcp-tool",
                owner_kind="augur",
                management="generated",
                primary_surface="mcp",
                current_exposure=("gemini",),
            )
        ]
    )

    assert report["records"][0]["recommended_action"] == {
        "id": "move_to_cli_only",
        "label": "Move to CLI only",
        "params": {},
    }


def test_records_are_full_serialized_sorted_and_review_unclassified_exposure() -> None:
    report = build_capability_report(
        [
            _record("skill:zeta", metadata={"display_name": "Zeta"}),
            _record(
                "skill:alpha",
                classification_status="unclassified",
                current_exposure=("codex",),
                drift=("unclassified_export",),
                metadata={"display_name": "Alpha"},
            ),
        ]
    )

    assert [record["id"] for record in report["records"]] == [
        "skill:alpha",
        "skill:zeta",
    ]
    assert report["records"][0]["source_paths"] == ["project-brain/capabilities/skills/example/SKILL.md"]
    assert report["records"][0]["current_exposure"] == ["codex"]
    assert report["records"][0]["recommended_action"] == {
        "id": "review_policy",
        "label": "Review exposure policy",
        "params": {},
    }
    assert report["records"][1]["metadata"] == {"display_name": "Zeta"}
    assert "recommended_action" not in report["records"][1]
