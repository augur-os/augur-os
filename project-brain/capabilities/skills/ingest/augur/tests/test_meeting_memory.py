from __future__ import annotations


def test_build_meeting_memory_extracts_summary_and_actions() -> None:
    from src.lib.ingest.meeting_memory import build_meeting_memory

    memory = build_meeting_memory(
        "Discussed investor demo readiness. "
        "Decision: use airplane mode first. "
        "Action: Gur will prepare fixture pack. "
        "Follow-up: verify cloud escalation evidence."
    )

    assert memory["summary"].startswith("Discussed investor demo readiness")
    assert memory["decisions"] == ["use airplane mode first."]
    assert memory["next_actions"] == [
        "Gur will prepare fixture pack.",
        "verify cloud escalation evidence.",
    ]


def test_build_meeting_memory_handles_transcribed_label_commas() -> None:
    from src.lib.ingest.meeting_memory import build_meeting_memory

    memory = build_meeting_memory(
        "Discussed investor demo readiness, decision, use airplane mode first, "
        "action, prepare the fixture pack, follow up, verify cloud escalation evidence."
    )

    assert memory["decisions"] == ["use airplane mode first."]
    assert memory["next_actions"] == [
        "prepare the fixture pack.",
        "verify cloud escalation evidence.",
    ]
