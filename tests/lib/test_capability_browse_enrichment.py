from typing import cast

from src.lib.capabilities.browse_enrichment import capability_metadata_for_browse_entry
from src.lib.capabilities.exposure_policy import CapabilityRecord, CapabilityType
from src.mcp.augur_framework.tools.infrastructure.browse.index import (
    _apply_capability_metadata,
    _merge_capability_metadata,
)


def _record(
    capability_id: str,
    *,
    current_exposure: tuple[str, ...] = ("codex",),
    drift: tuple[str, ...] = ("missing_expected_export",),
) -> CapabilityRecord:
    return CapabilityRecord(
        id=capability_id,
        type=cast(CapabilityType, capability_id.split(":", 1)[0]),
        owner_kind="augur",
        management="generated",
        scope="project",
        primary_surface="skill",
        preferred_client="codex",
        export_to=("codex", "gemini"),
        classification_status="approved",
        source_paths=("skills/example/SKILL.md",),
        current_exposure=current_exposure,
        drift=drift,
    )


def test_skill_lookup_returns_policy_metadata(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.lib.capabilities.browse_enrichment._resolved_records_by_id",
        lambda: {"skill:geo-audit": _record("skill:geo-audit")},
    )

    metadata = capability_metadata_for_browse_entry(
        "skills",
        {"name": "Geo Audit", "title": "Geo Audit"},
    )

    assert metadata == {
        "capabilityId": "skill:geo-audit",
        "ownerKind": "augur",
        "management": "generated",
        "scope": "project",
        "sourcePaths": "skills/example/SKILL.md",
        "primarySurface": "skill",
        "preferredClient": "codex",
        "exportTo": "codex,gemini",
        "classificationStatus": "approved",
        "currentExposure": "codex",
        "drift": "missing_expected_export",
    }


def test_unknown_entry_or_category_returns_empty_metadata(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.lib.capabilities.browse_enrichment._resolved_records_by_id",
        lambda: {"skill:geo-audit": _record("skill:geo-audit")},
    )

    assert capability_metadata_for_browse_entry("skills", {"name": "unknown"}) == {}
    assert capability_metadata_for_browse_entry("documents", {"name": "Geo Audit"}) == {}


def test_command_lookup_strips_leading_slash(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.lib.capabilities.browse_enrichment._resolved_records_by_id",
        lambda: {
            "command:dev-build": _record(
                "command:dev-build",
                current_exposure=("agents-md", "browse"),
                drift=("unexpected_client",),
            )
        },
    )

    metadata = capability_metadata_for_browse_entry(
        "commands",
        {"name": "/dev-build"},
    )

    assert metadata["capabilityId"] == "command:dev-build"
    assert metadata["currentExposure"] == "agents-md,browse"
    assert metadata["drift"] == "unexpected_client"


def test_integration_lookup_uses_owning_skill_from_source_path(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.lib.capabilities.browse_enrichment._resolved_records_by_id",
        lambda: {"skill:loop-security": _record("skill:loop-security")},
    )

    metadata = capability_metadata_for_browse_entry(
        "integrations",
        {
            "id": "Loop Security",
            "name": "Loop Security",
            "source_path": "project-brain/capabilities/skills/loop-security/SKILL.md",
            "metadata": {"cli_tools": "tank"},
        },
    )

    assert metadata["capabilityId"] == "skill:loop-security"
    assert metadata["classificationStatus"] == "approved"


def test_browse_capability_merge_preserves_existing_metadata_keys() -> None:
    metadata = {
        "scope": "shared",
        "capabilityScope": "global",
        "management": "manual",
        "group": "geo",
    }
    capability_metadata = {
        "capabilityId": "skill:geo-audit",
        "classificationStatus": "approved",
        "scope": "project",
        "management": "generated",
    }

    _merge_capability_metadata(metadata, capability_metadata)

    assert metadata["scope"] == "shared"
    assert metadata["capabilityScope"] == "global"
    assert metadata["management"] == "manual"
    assert metadata["group"] == "geo"
    assert metadata["capabilityId"] == "skill:geo-audit"
    assert metadata["classificationStatus"] == "approved"
    assert metadata["capabilityManagement"] == "generated"


def test_browse_capability_merge_overrides_stale_owner_kind() -> None:
    metadata = {
        "ownerKind": "external",
        "ownership": "user",
    }
    capability_metadata = {
        "capabilityId": "skill:books",
        "ownerKind": "user",
        "classificationStatus": "approved",
    }

    _merge_capability_metadata(metadata, capability_metadata)

    assert metadata["ownerKind"] == "user"
    assert "capabilityOwnerKind" not in metadata


def test_browse_capability_enrichment_error_sets_inventory_error(monkeypatch) -> None:
    def _raise_inventory_error(category, entry):
        raise ImportError("capability inventory unavailable")

    monkeypatch.setattr(
        "src.mcp.augur_framework.tools.infrastructure.browse.index_metadata._capability_metadata_for_browse_entry",
        _raise_inventory_error,
    )
    metadata: dict[str, str] = {}

    _apply_capability_metadata("skills", {"name": "Geo Audit"}, metadata)

    assert metadata == {"capabilityStatus": "inventory_error"}


def test_capability_metadata_marks_draft_rows_with_is_draft(monkeypatch):
    """ADR-734 C5: draft leftovers surface isDraft=true on Browse entries."""
    from src.lib.capabilities import browse_enrichment

    monkeypatch.setattr(browse_enrichment, "_resolved_records_by_id", lambda: {})
    monkeypatch.setattr(
        browse_enrichment,
        "_draft_leftover_names",
        lambda: frozenset({"future-skill"}),
    )
    entry = {"name": "future-skill", "title": "Future Skill"}

    metadata = capability_metadata_for_browse_entry("skills", entry)

    assert metadata.get("isDraft") == "true"


def test_capability_metadata_quiet_when_not_a_draft(monkeypatch):
    from src.lib.capabilities import browse_enrichment

    monkeypatch.setattr(browse_enrichment, "_resolved_records_by_id", lambda: {})
    monkeypatch.setattr(browse_enrichment, "_draft_leftover_names", lambda: frozenset())
    entry = {"name": "production-skill", "title": "Production Skill"}

    metadata = capability_metadata_for_browse_entry("skills", entry)

    assert "isDraft" not in metadata


def test_capability_metadata_marks_draft_via_source_path(monkeypatch):
    from src.lib.capabilities import browse_enrichment

    monkeypatch.setattr(browse_enrichment, "_resolved_records_by_id", lambda: {})
    monkeypatch.setattr(
        browse_enrichment,
        "_draft_leftover_names",
        lambda: frozenset({"foo"}),
    )
    entry = {"source_path": "project-brain/capabilities/skills/foo/SKILL.draft.md", "name": "foo"}

    metadata = capability_metadata_for_browse_entry("skills", entry)

    assert metadata.get("isDraft") == "true"


def test_no_draft_leftover_is_present_as_a_generated_client_skill():
    """ADR-734 C5.3 regression guard — drafts must not leak into client skills/."""
    from src.config.paths import get_project_root
    from src.lib.capabilities.drift import detect_draft_leakage

    findings = detect_draft_leakage(get_project_root())
    assert findings == [], f"Draft leakage detected: {findings}"
