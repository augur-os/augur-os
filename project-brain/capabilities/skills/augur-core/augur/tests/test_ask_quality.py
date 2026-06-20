from __future__ import annotations

import pytest


def test_assessment_flags_empty_context() -> None:
    from src.mcp.augur_core.tools.core import ask_quality

    result = ask_quality.assess_context_support("What should I remember?", [])

    assert result.supported is False
    assert "no-sources" in result.flags
    assert result.answer_mode == "weak-context"


def test_assessment_accepts_multiple_substantial_sources() -> None:
    from src.mcp.augur_core.tools.core import ask_quality

    sources = [
        {"title": "Memory", "text": "A" * 260, "updated_at": "2026-05-23T00:00:00Z"},
        {"title": "ADR", "text": "B" * 240, "updated_at": "2026-05-22T00:00:00Z"},
    ]

    result = ask_quality.assess_context_support(
        "How should the demo work?",
        sources,
        current_date="2026-05-23",
    )

    assert result.supported is True
    assert result.answer_mode == "supported"
    assert result.flags == []


def test_assessment_flags_short_context() -> None:
    from src.mcp.augur_core.tools.core import ask_quality

    sources = [{"title": "Tiny", "text": "too short"}]

    result = ask_quality.assess_context_support("What changed?", sources)

    assert result.supported is False
    assert "low-context-volume" in result.flags


def test_assessment_flags_stale_context() -> None:
    from src.mcp.augur_core.tools.core import ask_quality

    sources = [{"title": "Old", "text": "A" * 500, "updated_at": "2024-01-01T00:00:00Z"}]

    result = ask_quality.assess_context_support(
        "What is current?",
        sources,
        current_date="2026-05-23",
        stale_after_days=180,
    )

    assert result.supported is False
    assert "stale-sources" in result.flags


def test_assessment_flags_mixed_stale_context() -> None:
    from src.mcp.augur_core.tools.core import ask_quality

    sources = [
        {"title": "Old", "text": "A" * 260, "updated_at": "2024-01-01T00:00:00Z"},
        {"title": "Fresh", "text": "B" * 240, "updated_at": "2026-05-22T00:00:00Z"},
    ]

    result = ask_quality.assess_context_support(
        "What is current?",
        sources,
        current_date="2026-05-23",
        stale_after_days=180,
    )

    assert result.supported is False
    assert result.answer_mode == "weak-context"
    assert "stale-sources" in result.flags


def test_current_focus_query_flags_absent_fresh_sources() -> None:
    from src.mcp.augur_core.tools.core import ask_quality

    sources = [
        {
            "title": "Old memory",
            "text": "stale focus evidence",
            "source_type": "codex_memory",
            "updated_at": "2024-01-01T00:00:00Z",
            "stale": True,
        }
    ]

    result = ask_quality.assess_context_support(
        "What am I working on now?",
        sources,
        current_date="2026-05-28",
        min_sources=1,
        min_total_chars=10,
    )

    assert result.supported is False
    assert result.answer_mode == "weak-context"
    assert "no-fresh-sources" in result.flags
    assert "stale-primary-source" in result.flags


def test_current_focus_query_accepts_fresh_quality_sources() -> None:
    from src.mcp.augur_core.tools.core import ask_quality

    sources = [
        {
            "title": "Live memory",
            "text": "fresh memory evidence",
            "source_type": "codex_memory",
            "updated_at": "2026-05-28T09:00:00Z",
            "stale": False,
        },
        {
            "title": "Repo evidence",
            "text": "fresh repository evidence",
            "source_type": "repo_evidence",
            "modified_at": "2026-05-28T08:00:00Z",
            "stale": False,
        },
    ]

    result = ask_quality.assess_context_support(
        "What is my current focus today?",
        sources,
        current_date="2026-05-28",
        min_sources=1,
        min_total_chars=10,
    )

    assert result.supported is True
    assert result.answer_mode == "supported"
    assert "no-fresh-sources" not in result.flags
    assert result.flags == []


def test_current_focus_query_flags_missing_client_memory() -> None:
    from src.mcp.augur_core.tools.core import ask_quality

    sources = [
        {
            "title": "Repo evidence",
            "text": "fresh repository evidence",
            "source_family": "repo_evidence",
            "updated_at": "2026-05-28T08:00:00Z",
            "stale": False,
        }
    ]

    result = ask_quality.assess_context_support(
        "What am I working on now?",
        sources,
        current_date="2026-05-28",
        min_sources=1,
        min_total_chars=10,
    )

    assert result.supported is False
    assert "client-memory-unavailable" in result.flags


def test_generic_query_with_quality_metadata_flags_low_signal_terms() -> None:
    from src.mcp.augur_core.tools.core import ask_quality

    sources = [
        {
            "title": "Wiki",
            "text": "A" * 500,
            "source_family": "augur_wiki",
            "match_terms": [],
        }
    ]

    result = ask_quality.assess_context_support(
        "What about this?",
        sources,
        min_sources=1,
        min_total_chars=10,
    )

    assert result.supported is False
    assert "generic-query-low-signal" in result.flags


def test_generic_query_without_quality_metadata_preserves_legacy_support() -> None:
    from src.mcp.augur_core.tools.core import ask_quality

    result = ask_quality.assess_context_support(
        "What about this?",
        [{"title": "Legacy", "text": "A" * 500}],
        min_sources=1,
        min_total_chars=10,
    )

    assert result.supported is True
    assert "generic-query-low-signal" not in result.flags


def test_troubleshooting_query_with_working_is_not_current_focus() -> None:
    from src.mcp.augur_core.tools.core import ask_quality

    sources = [
        {"title": "Trace", "text": "A" * 260},
        {"title": "Config", "text": "B" * 240},
    ]

    result = ask_quality.assess_context_support(
        "Why is retention not working?",
        sources,
        min_sources=2,
        min_total_chars=400,
    )

    assert result.supported is True
    assert "no-fresh-sources" not in result.flags


def test_current_focus_uses_latest_parseable_source_date_consistently() -> None:
    from src.mcp.augur_core.tools.core import ask_quality

    result = ask_quality.assess_context_support(
        "What am I working on now?",
        [
            {
                "title": "Repo evidence",
                "text": "fresh repository evidence",
                "updated_at": "2024-01-01T00:00:00Z",
                "modified_at": "2026-05-28T08:00:00Z",
            }
        ],
        current_date="2026-05-28",
        min_sources=1,
        min_total_chars=10,
        stale_after_days=7,
    )

    assert result.supported is True
    assert "stale-sources" not in result.flags
    assert "no-fresh-sources" not in result.flags


def test_focused_on_query_flags_absent_fresh_sources() -> None:
    from src.mcp.augur_core.tools.core import ask_quality

    result = ask_quality.assess_context_support(
        "What am I focused on?",
        [{"title": "Old memory", "text": "stale focus evidence", "stale": True}],
        current_date="2026-05-28",
        min_sources=1,
        min_total_chars=10,
    )

    assert result.supported is False
    assert "no-fresh-sources" in result.flags


@pytest.mark.parametrize(
    ("metadata", "expected_supported"),
    [
        ({"stale": False, "updated_at": "2024-01-01T00:00:00Z"}, True),
        ({"updated_at": "2026-05-27T09:00:00Z"}, True),
        ({"modified_at": "2026-05-27T09:00:00Z"}, True),
        ({"updated_at": "2024-01-01T00:00:00Z"}, False),
        ({"updated_at": "not-a-date", "modified_at": "2026-05-27T09:00:00Z"}, True),
    ],
)
def test_current_focus_freshness_uses_metadata_deterministically(
    metadata: dict[str, object],
    expected_supported: bool,
) -> None:
    from src.mcp.augur_core.tools.core import ask_quality

    result = ask_quality.assess_context_support(
        "What am I working on now?",
        [{"title": "Evidence", "text": "freshness evidence", **metadata}],
        current_date="2026-05-28",
        min_sources=1,
        min_total_chars=10,
        stale_after_days=7,
    )

    assert result.supported is expected_supported
    assert ("no-fresh-sources" in result.flags) is not expected_supported


def test_quality_flags_dedupe_preserves_first_seen_order() -> None:
    from src.mcp.augur_core.tools.core import ask_quality

    assert ask_quality._dedupe_flags(["stale-sources", "no-fresh-sources", "stale-sources"]) == [
        "stale-sources",
        "no-fresh-sources",
    ]


def test_assessment_to_dict_exposes_copied_quality_flags() -> None:
    from src.mcp.augur_core.tools.core import ask_quality

    result = ask_quality.assess_context_support("What changed?", [])

    payload = result.to_dict()

    assert payload["flags"] == result.flags
    assert payload["quality_flags"] == result.flags
    assert payload["flags"] is not result.flags
    assert payload["quality_flags"] is not result.flags
    assert payload["quality_flags"] is not payload["flags"]


def test_assessment_ignores_malformed_sources() -> None:
    from src.mcp.augur_core.tools.core import ask_quality

    # None entries and non-dict items in the sources list must not crash the gate.
    result = ask_quality.assess_context_support(
        "What should I remember?",
        [None, {"text": ""}, 42],
        min_sources=1,
        min_total_chars=20,
    )

    assert result.answer_mode == "weak-context"
    assert "no-sources" in result.flags


def test_vault_heavy_pack_is_supported() -> None:
    """Regression lock: personal_vault-family packs pass the weak-context gate."""
    from src.mcp.augur_core.tools.core import ask_quality

    sources = [
        {
            "text": "Interview prep: STAR stories for salary negotiation." * 10,
            "source_family": "personal_vault",
            "updated_at": "2026-06-01T00:00:00+00:00",
            "stale": False,
            "match_terms": ["interview", "salary", "negotiation"],
        },
        {
            "text": "CV: AI Transformation Leader, 150-engineer transformation." * 10,
            "source_family": "personal_vault",
            "updated_at": "2026-04-23T00:00:00+00:00",
            "stale": False,
            "match_terms": ["transformation"],
        },
    ]
    result = ask_quality.assess_context_support(
        "top interview questions for an AI champion role",
        sources,
        current_date="2026-06-12",
    )
    assert result.answer_mode == "supported"
    assert result.flags == []


def test_low_relevance_context_flags_marginal_matches() -> None:
    """Sources matching ~1 of several content terms must not present confidently."""
    from src.mcp.augur_core.tools.core import ask_quality

    sources = [
        {
            "text": "Competitor research for a personal AI OS, market segments." * 10,
            "source_family": "personal_vault",
            "updated_at": "2026-06-01T00:00:00+00:00",
            "stale": False,
            "match_terms": ["health"],
        },
        {
            "text": "Terms and conditions draft for the website." * 10,
            "source_family": "personal_vault",
            "updated_at": "2026-06-01T00:00:00+00:00",
            "stale": False,
            "match_terms": ["goals"],
        },
    ]
    result = ask_quality.assess_context_support(
        "what are my health and fitness goals",
        sources,
        current_date="2026-06-12",
    )
    assert "low-relevance-context" in result.flags
    assert result.answer_mode == "weak-context"


def test_low_relevance_does_not_fire_on_strong_matches() -> None:
    from src.mcp.augur_core.tools.core import ask_quality

    sources = [
        {
            "text": "Interview prep: salary negotiation stories and questions." * 10,
            "source_family": "personal_vault",
            "updated_at": "2026-06-01T00:00:00+00:00",
            "stale": False,
            "match_terms": ["interview", "questions", "salary"],
        },
        {
            "text": "STAR story bank with negotiation outcomes." * 10,
            "source_family": "personal_vault",
            "updated_at": "2026-06-01T00:00:00+00:00",
            "stale": False,
            "match_terms": ["negotiation"],
        },
    ]
    result = ask_quality.assess_context_support(
        "top interview questions for salary negotiation",
        sources,
        current_date="2026-06-12",
    )
    assert "low-relevance-context" not in result.flags
    assert result.answer_mode == "supported"


def test_low_relevance_skips_single_term_queries() -> None:
    from src.mcp.augur_core.tools.core import ask_quality

    sources = [
        {
            "text": "A note that mentions running once." * 20,
            "match_terms": ["running"],
            "updated_at": "2026-06-01T00:00:00+00:00",
            "stale": False,
        },
        {
            "text": "Another note." * 40,
            "match_terms": [],
            "updated_at": "2026-06-01T00:00:00+00:00",
            "stale": False,
        },
    ]
    result = ask_quality.assess_context_support(
        "running", sources, current_date="2026-06-12"
    )
    assert "low-relevance-context" not in result.flags
