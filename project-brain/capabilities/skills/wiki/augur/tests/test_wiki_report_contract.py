"""Unit tests for the wiki report agent-step contract."""
from __future__ import annotations

from skills.wiki.scripts.wiki_report_contract import (
    ALLOWED_SEVERITIES,
    HUB_SUMMARY_MAX_LEN,
    HUB_SUMMARY_MIN_LEN,
    SCHEMA_VERSION,
    SYNTHESIS_MAX_LEN,
    SYNTHESIS_MIN_LEN,
    SYNTHESIS_SCHEMA,
    hub_sections_skeleton,
    validate_rich_dict,
)


def _minimal_valid() -> dict:
    """Smallest dict that passes validation."""
    return {
        "synthesis": "A" * SYNTHESIS_MIN_LEN,
        "hub_sections": [
            {
                "name": "brain",
                "source_count": 136,
                "summary": "B" * HUB_SUMMARY_MIN_LEN,
            },
        ],
    }


def test_schema_version_is_one():
    assert SYNTHESIS_SCHEMA["version"] == 1
    assert SCHEMA_VERSION == 1


def test_schema_lists_required_and_optional_paths():
    required_paths = [item["path"] for item in SYNTHESIS_SCHEMA["required"]]
    assert "synthesis" in required_paths
    assert "hub_sections[*].summary" in required_paths

    optional_paths = [item["path"] for item in SYNTHESIS_SCHEMA["optional"]]
    assert "who_you_are.what_you_do" in optional_paths
    assert "who_you_are.how_you_think" in optional_paths
    assert "expertise[*]" in optional_paths
    assert "patterns[*]" in optional_paths
    assert "blind_spots[*]" in optional_paths


def test_allowed_severities_is_frozenset_of_three():
    assert ALLOWED_SEVERITIES == frozenset({"low", "medium", "high"})


def test_minimal_valid_dict_passes():
    result = validate_rich_dict(_minimal_valid())
    assert result.success
    assert result.missing_required == []


def test_all_optional_fields_present_and_valid_passes():
    report = _minimal_valid()
    report["who_you_are"] = {
        "what_you_do": "Building Augur, local-first AI infrastructure.",
        "how_you_think": "Decision-first; every architectural move gets an ADR.",
    }
    report["expertise"] = [
        {"domain": "Cross-Client AI Harness", "level": "Expert", "percentage": 95, "color": "#6366f1"},
    ]
    report["patterns"] = [
        {"title": "Discipline beats velocity", "description": "100% quality-passing wiki pages."},
    ]
    report["blind_spots"] = [
        {"title": "Life hub thin", "description": "Only 8 pages; work dominates.", "severity": "medium"},
    ]

    result = validate_rich_dict(report)

    assert result.success
    assert result.missing_required == []


def test_missing_synthesis_fails():
    report = _minimal_valid()
    del report["synthesis"]

    result = validate_rich_dict(report)

    assert not result.success
    assert "synthesis" in result.missing_required


def test_synthesis_too_short_fails():
    report = _minimal_valid()
    report["synthesis"] = "x" * (SYNTHESIS_MIN_LEN - 1)

    result = validate_rich_dict(report)

    assert not result.success
    assert "synthesis" in result.missing_required


def test_synthesis_too_long_fails():
    report = _minimal_valid()
    report["synthesis"] = "x" * (SYNTHESIS_MAX_LEN + 1)

    result = validate_rich_dict(report)

    assert not result.success
    assert "synthesis" in result.missing_required


def test_synthesis_wrong_type_fails():
    report = _minimal_valid()
    report["synthesis"] = 42

    result = validate_rich_dict(report)

    assert not result.success
    assert "synthesis" in result.missing_required


def test_missing_hub_sections_fails():
    report = _minimal_valid()
    del report["hub_sections"]

    result = validate_rich_dict(report)

    assert not result.success
    assert "hub_sections" in result.missing_required


def test_empty_hub_sections_fails():
    report = _minimal_valid()
    report["hub_sections"] = []

    result = validate_rich_dict(report)

    assert not result.success
    assert "hub_sections" in result.missing_required


def test_hub_section_missing_summary_fails():
    report = _minimal_valid()
    report["hub_sections"] = [{"name": "brain", "source_count": 136}]

    result = validate_rich_dict(report)

    assert not result.success
    assert "hub_sections[0].summary" in result.missing_required


def test_hub_section_summary_too_short_fails():
    report = _minimal_valid()
    report["hub_sections"][0]["summary"] = "x" * (HUB_SUMMARY_MIN_LEN - 1)

    result = validate_rich_dict(report)

    assert not result.success
    assert "hub_sections[0].summary" in result.missing_required


def test_hub_section_summary_too_long_fails():
    report = _minimal_valid()
    report["hub_sections"][0]["summary"] = "x" * (HUB_SUMMARY_MAX_LEN + 1)

    result = validate_rich_dict(report)

    assert not result.success
    assert "hub_sections[0].summary" in result.missing_required


def test_hub_section_at_index_not_a_dict_fails():
    report = _minimal_valid()
    report["hub_sections"] = ["not a dict"]

    result = validate_rich_dict(report)

    assert not result.success
    assert "hub_sections[0]" in result.missing_required


def test_bad_severity_fails():
    report = _minimal_valid()
    report["blind_spots"] = [{"title": "x", "description": "y", "severity": "critical"}]

    result = validate_rich_dict(report)

    assert not result.success
    assert "blind_spots[0].severity" in result.missing_required


def test_bad_percentage_above_100_fails():
    report = _minimal_valid()
    report["expertise"] = [{"domain": "AI", "level": "Expert", "percentage": 150, "color": "#fff"}]

    result = validate_rich_dict(report)

    assert not result.success
    assert "expertise[0].percentage" in result.missing_required


def test_bad_percentage_negative_fails():
    report = _minimal_valid()
    report["expertise"] = [{"domain": "AI", "level": "Expert", "percentage": -5, "color": "#fff"}]

    result = validate_rich_dict(report)

    assert not result.success
    assert "expertise[0].percentage" in result.missing_required


def test_bad_expertise_level_fails():
    report = _minimal_valid()
    report["expertise"] = [{"domain": "AI", "level": "Wizard", "percentage": 50, "color": "#fff"}]

    result = validate_rich_dict(report)

    assert not result.success
    assert "expertise[0].level" in result.missing_required


def test_multiple_failures_collected_not_short_circuit():
    report = {
        "synthesis": "short",
        "hub_sections": [
            {"name": "brain"},
            {"name": "career", "summary": "x" * 30},
        ],
    }

    result = validate_rich_dict(report)

    assert not result.success
    assert "synthesis" in result.missing_required
    assert "hub_sections[0].summary" in result.missing_required
    assert "hub_sections[1].summary" in result.missing_required
    assert len(result.missing_required) == 3


def test_hub_sections_skeleton_sorts_by_source_count_desc():
    hubs = {
        "general": {"source_count": 16},
        "brain": {"source_count": 136},
        "career": {"source_count": 119},
    }

    result = hub_sections_skeleton(hubs)

    assert [h["name"] for h in result] == ["brain", "career", "general"]
    assert [h["source_count"] for h in result] == [136, 119, 16]
    for hub in result:
        assert "summary" not in hub
        assert "icon" not in hub
        assert "color" not in hub


def test_hub_sections_skeleton_handles_missing_source_count():
    assert hub_sections_skeleton({"empty_hub": {}}) == [{"name": "empty_hub", "source_count": 0}]


def test_hub_sections_skeleton_handles_empty_input():
    assert hub_sections_skeleton({}) == []
