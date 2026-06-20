from pathlib import Path

import json
import pytest

from src.mcp.augur_core.tools.core.ask_retention import (
    build_retention_footer,
    classify_ask_outcome,
    retain_ask_outcome_impl,
    route_ask_retention,
)


def test_ask_command_mentions_second_brain_and_no_footer_by_default():
    command_path = Path(__file__).resolve().parents[2] / "commands" / "ask.md"
    text = command_path.read_text(encoding="utf-8")
    assert "Ask your second brain" in text
    assert "--retain" in text
    assert "--private" in text
    assert "--no-retain" in text
    assert "ask-retain" in text
    assert "Footer policy" in text
    assert "No retention footer and no" in text
    assert "answers without persisting anything unless you opt in" in text
    assert "If `ask-retain` returns a footer, append it verbatim" not in text
    assert "Keep retention silent by default" not in text
    assert "If retention is allowed" not in text
    assert "stronger bias toward retaining high-signal outcomes" not in text
    assert "conversation_summary" in text


def test_ask_command_does_not_retain_by_default():
    command_path = Path(__file__).resolve().parents[2] / "commands" / "ask.md"
    text = command_path.read_text(encoding="utf-8")
    assert "/ask" in text
    assert "Retention is **off by default**" in text
    assert "/ask --retain" in text
    assert "remember this" in text


def test_classify_explicit_preference():
    result = classify_ask_outcome(
        question="How do I work best?",
        answer="You work best with long uninterrupted blocks in the morning.",
        explicit_signals=["I prefer deep work before noon"],
        inferred_signals=[],
    )
    assert "preference" in result["kinds"]
    assert result["should_retain"] is True


def test_classify_inferred_pattern_with_confidence():
    result = classify_ask_outcome(
        question="What pattern keeps showing up?",
        answer="You consistently trade novelty for long-horizon leverage.",
        explicit_signals=[],
        inferred_signals=["long-horizon leverage pattern"],
    )
    assert "inferred-pattern" in result["kinds"]
    assert result["confidence"] == "medium"


def test_classify_decision_from_answer_language():
    result = classify_ask_outcome(
        question="What should I prioritize next?",
        answer="You decided to prioritize Augur and defer consulting until after the launch.",
        explicit_signals=[],
        inferred_signals=[],
    )
    assert "decision" in result["kinds"]
    assert result["should_retain"] is True


def test_classify_contradiction_from_tension_language():
    result = classify_ask_outcome(
        question="What tension keeps showing up in how I position Augur?",
        answer="There is a real contradiction here: you want sharper product focus, but you also keep preserving consulting credibility.",
        explicit_signals=[],
        inferred_signals=[],
    )
    assert "contradiction" in result["kinds"]
    assert result["should_retain"] is True


def test_classify_open_question_from_unresolved_language():
    result = classify_ask_outcome(
        question="What is still unresolved in the wiki direction?",
        answer="The open question is whether the wiki should learn from git history directly or only from interpreted deltas.",
        explicit_signals=[],
        inferred_signals=[],
    )
    assert "open-question" in result["kinds"]
    assert result["should_retain"] is True


def test_retention_footer_is_minimal():
    footer = build_retention_footer(["preference", "inferred-pattern"])
    assert footer == "retained: preference + inferred pattern"


def test_retention_footer_normalizes_synthesis_bound_kinds():
    footer = build_retention_footer(["insight", "inferred-pattern"])
    assert footer == "retained: synthesis + inferred pattern"


def test_retention_footer_marks_open_question_as_deferred():
    footer = build_retention_footer(["open-question"])
    assert footer == "retained: deferred"


@pytest.mark.asyncio
async def test_retain_ask_outcome_hides_footer_by_default(monkeypatch):
    class FakeDailyLogger:
        def log_decision(self, *args, **kwargs):
            raise AssertionError("log_decision should not be called in this test")

        def log_user_preference(self, preference, value, source=None):
            return None

    monkeypatch.setattr(
        "src.lib.knowledge.DailyLogger",
        FakeDailyLogger,
    )

    monkeypatch.setattr(
        "src.mcp.augur_core.tools.core.ask_retention._flag_wiki_update_needed",
        lambda: "/tmp/wiki.flag",
    )

    raw = await retain_ask_outcome_impl(
        question="How do I work best?",
        answer="You work best with long uninterrupted blocks in the morning.",
        explicit_signals=["I prefer deep work before noon"],
        inferred_signals=[],
    )

    payload = json.loads(raw)
    assert payload["retained"] is True
    assert payload["footer"] is None


@pytest.mark.asyncio
async def test_retain_ask_outcome_surfaces_footer_when_requested(monkeypatch):
    class FakeDailyLogger:
        def log_decision(self, *args, **kwargs):
            raise AssertionError("log_decision should not be called in this test")

        def log_user_preference(self, preference, value, source=None):
            return None

    monkeypatch.setattr(
        "src.lib.knowledge.DailyLogger",
        FakeDailyLogger,
    )

    monkeypatch.setattr(
        "src.mcp.augur_core.tools.core.ask_retention._flag_wiki_update_needed",
        lambda: "/tmp/wiki.flag",
    )

    raw = await retain_ask_outcome_impl(
        question="How do I work best?",
        answer="You work best with long uninterrupted blocks in the morning.",
        explicit_signals=["I prefer deep work before noon"],
        inferred_signals=[],
        surface_footer=True,
    )

    payload = json.loads(raw)
    assert payload["retained"] is True
    assert payload["footer"] == "retained: preference"


@pytest.mark.asyncio
async def test_retain_ask_outcome_routes_inferred_decision_without_explicit_kinds(monkeypatch):
    logged: list[dict] = []

    class FakeDailyLogger:
        def log_decision(self, topic, decision, reasoning=None, confidence="medium", category="Ask"):
            logged.append(
                {
                    "topic": topic,
                    "decision": decision,
                    "reasoning": reasoning,
                    "confidence": confidence,
                    "category": category,
                }
            )

        def log_user_preference(self, preference, value, source=None):
            raise AssertionError("log_user_preference should not be called in this test")

    monkeypatch.setattr(
        "src.lib.knowledge.DailyLogger",
        FakeDailyLogger,
    )

    monkeypatch.setattr(
        "src.mcp.augur_core.tools.core.ask_retention._flag_wiki_update_needed",
        lambda: "/tmp/wiki.flag",
    )

    raw = await retain_ask_outcome_impl(
        question="What should I prioritize next?",
        answer="You decided to prioritize Augur and defer consulting until after the launch.",
        explicit_signals=[],
        inferred_signals=[],
    )

    payload = json.loads(raw)
    assert payload["retained"] is True
    assert payload["kinds"] == ["decision"]
    assert payload["persistence"]["decisions_logged"] == 1
    assert payload["persistence"]["preferences_logged"] == 0
    assert logged == [
        {
            "topic": "What should I prioritize next?",
            "decision": "You decided to prioritize Augur and defer consulting until after the launch.",
            "reasoning": None,
            "confidence": "medium",
            "category": "Ask",
        }
    ]


def test_route_decision_and_preference_are_distinct():
    routed = route_ask_retention(
        {
            "kinds": ["decision", "preference"],
            "question": "What should I prioritize?",
            "answer": "You decided to prioritize the launch, and you prefer long uninterrupted blocks.",
            "should_retain": True,
            "confidence": "high",
        }
    )
    assert routed["payload"] == {
        "question": "What should I prioritize?",
        "answer": "You decided to prioritize the launch, and you prefer long uninterrupted blocks.",
        "should_retain": True,
        "confidence": "high",
    }
    assert routed["decision"] == [
        {
            "kind": "decision",
            "question": "What should I prioritize?",
            "answer": "You decided to prioritize the launch, and you prefer long uninterrupted blocks.",
            "should_retain": True,
            "confidence": "high",
        }
    ]
    assert routed["preference"] == [
        {
            "kind": "preference",
            "question": "What should I prioritize?",
            "answer": "You decided to prioritize the launch, and you prefer long uninterrupted blocks.",
            "should_retain": True,
            "confidence": "high",
        }
    ]
    assert routed["decision"] != routed["preference"]


def test_route_preference_and_insight():
    routed = route_ask_retention(
        {
            "kinds": ["preference", "insight"],
            "question": "How should I structure my mornings?",
            "answer": "You work best before noon and prefer long uninterrupted blocks.",
            "should_retain": True,
            "confidence": "high",
        }
    )
    assert routed["payload"] == {
        "question": "How should I structure my mornings?",
        "answer": "You work best before noon and prefer long uninterrupted blocks.",
        "should_retain": True,
        "confidence": "high",
    }
    assert routed["preference"] == [
        {
            "kind": "preference",
            "question": "How should I structure my mornings?",
            "answer": "You work best before noon and prefer long uninterrupted blocks.",
            "should_retain": True,
            "confidence": "high",
        }
    ]
    assert routed["synthesis"] == [
        {
            "kind": "insight",
            "question": "How should I structure my mornings?",
            "answer": "You work best before noon and prefer long uninterrupted blocks.",
            "should_retain": True,
            "confidence": "high",
        }
    ]
    assert set(routed) == {
        "payload",
        "kinds",
        "decision",
        "preference",
        "synthesis",
        "contradictions",
        "deferred",
    }


def test_route_synthesis_kind_lands_in_synthesis_bucket():
    routed = route_ask_retention(
        {
            "kinds": ["synthesis"],
            "question": "q",
            "answer": "a",
            "should_retain": True,
            "confidence": "high",
        }
    )
    assert routed["synthesis"] == [
        {
            "kind": "synthesis",
            "question": "q",
            "answer": "a",
            "should_retain": True,
            "confidence": "high",
        }
    ]


def test_route_unknown_durable_kind_falls_back_to_synthesis():
    routed = route_ask_retention(
        {
            "kinds": ["outcome", "synthesis"],
            "question": "q",
            "answer": "a",
            "should_retain": True,
            "confidence": "high",
        }
    )
    assert [entry["kind"] for entry in routed["synthesis"]] == ["outcome", "synthesis"]
    assert routed["decision"] == []
    assert routed["preference"] == []


def test_route_ephemeral_kind_is_not_routed():
    routed = route_ask_retention(
        {
            "kinds": ["ephemeral"],
            "question": "q",
            "answer": "a",
            "should_retain": False,
            "confidence": "low",
        }
    )
    assert routed["synthesis"] == []
    assert routed["decision"] == []
    assert routed["preference"] == []
    assert routed["contradictions"] == []
    assert routed["deferred"] == []


@pytest.mark.asyncio
async def test_retain_explicit_free_text_kinds_persist_via_synthesis(monkeypatch):
    saved_calls: list[dict] = []

    async def fake_save_synthesis_impl(*, query, synthesis, sources=None, tags=None, knowledge_dir=None):
        saved_calls.append({"query": query, "synthesis": synthesis, "tags": tags})
        return json.dumps({"success": True, "path": "/tmp/synth.md"})

    class FakeDailyLogger:
        def log_decision(self, *args, **kwargs):
            raise AssertionError("log_decision should not be called in this test")

        def log_user_preference(self, *args, **kwargs):
            raise AssertionError("log_user_preference should not be called in this test")

    monkeypatch.setattr(
        "src.mcp.augur_core.tools.core.ask_retention.save_synthesis_impl",
        fake_save_synthesis_impl,
    )
    monkeypatch.setattr("src.lib.knowledge.DailyLogger", FakeDailyLogger)
    monkeypatch.setattr(
        "src.mcp.augur_core.tools.core.ask_retention._flag_wiki_update_needed",
        lambda: "/tmp/wiki.flag",
    )

    raw = await retain_ask_outcome_impl(
        question="Nuvoton deck structure",
        answer="Final 16-slide structure with Part 1 framing and Part 2 practical review.",
        kinds=["outcome", "synthesis"],
    )

    payload = json.loads(raw)
    assert payload["success"] is True
    assert payload["retained"] is True
    assert payload["persistence"]["syntheses_saved"] == ["/tmp/synth.md"]
    assert payload["classification"]["confidence"] == "high"
    assert len(saved_calls) == 1


@pytest.mark.asyncio
async def test_retain_reports_failure_when_nothing_persists(monkeypatch):
    async def failing_save_synthesis_impl(**kwargs):
        return json.dumps({"success": False, "error": "disk full"})

    class FakeDailyLogger:
        def log_decision(self, *args, **kwargs):
            raise AssertionError("log_decision should not be called in this test")

        def log_user_preference(self, *args, **kwargs):
            raise AssertionError("log_user_preference should not be called in this test")

    monkeypatch.setattr(
        "src.mcp.augur_core.tools.core.ask_retention.save_synthesis_impl",
        failing_save_synthesis_impl,
    )
    monkeypatch.setattr("src.lib.knowledge.DailyLogger", FakeDailyLogger)
    monkeypatch.setattr(
        "src.mcp.augur_core.tools.core.ask_retention._flag_wiki_update_needed",
        lambda: "/tmp/wiki.flag",
    )

    raw = await retain_ask_outcome_impl(
        question="q",
        answer="a durable answer",
        kinds=["synthesis"],
    )

    payload = json.loads(raw)
    assert payload["success"] is False
    assert payload["retained"] is False
    assert payload["persistence"]["syntheses_saved"] == []
    assert "disk full" in json.dumps(payload)


def _ingest_bundle_root() -> Path | None:
    """Locate the ingest bundle in private-vault or project-brain skill roots."""
    shared_vault_root = Path(__file__).resolve().parents[4]
    candidates = [
        Path.home() / "Projects" / "Au-vault" / "skills" / "ingest",
        shared_vault_root / "capabilities" / "skills" / "ingest",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def _repo_root() -> Path:
    return next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])


def test_wiki_update_mentions_retained_ask_outcomes():
    text = (_repo_root() / "docs" / "guides" / "wiki-llm-release-gate.md").read_text(encoding="utf-8")
    assert "Include retained `/ask` outcomes when they are durable" in text
    assert "ask-sync-data" in text
    assert "ask-sync-clusters" in text


def test_wiki_topic_mentions_retained_ask_outcomes():
    text = _repo_root() / "docs" / "agent-topics" / "WIKI.md"
    text = text.read_text(encoding="utf-8")
    assert (
        "Retained `/ask` outcomes after retention routing are part of session-end "
        "compounding and should be considered wiki inputs."
    ) in text


def test_ask_sync_guidance_mentions_retained_ask_outcomes():
    bundle = _ingest_bundle_root()
    if bundle is None:
        pytest.skip("ingest bundle not present (Au-vault missing)")
    text = (bundle / "scripts" / "mcp" / "wiki_tools.py").read_text(encoding="utf-8")
    assert 'name="ask-sync-data"' in text
    assert "Gather recent retained `/ask` outcomes from synthesis and memory layers." in text
    assert 'name="ask-sync-clusters"' in text
    assert "Cluster recent retained `/ask` outcomes for wiki compounding." in text


def test_wiki_builder_mentions_ask_sync_data_for_incremental_updates():
    bundle = _ingest_bundle_root()
    if bundle is None:
        pytest.skip("ingest bundle not present (Au-vault missing)")
    sync_text = (bundle / "scripts" / "ask_sync.py").read_text(encoding="utf-8")
    cluster_text = (bundle / "scripts" / "ask_sync_clusters.py").read_text(encoding="utf-8")
    wiki_text = (_repo_root() / "docs" / "agent-topics" / "WIKI.md").read_text(encoding="utf-8")
    assert "Return recent retained `/ask` outcomes for compounding flows." in sync_text
    assert "priority_score" in cluster_text
    assert "reverse=True" in cluster_text
    assert "Retained `/ask` outcomes after retention routing are part of session-end compounding" in wiki_text
