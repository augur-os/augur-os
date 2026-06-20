from __future__ import annotations


def test_score_demo_output_rewards_grounded_specific_content() -> None:
    from skills.evals.scripts import demo_case_eval as mod

    result = mod.score_demo_output(
        case_id="deck-slide-critique",
        source_title="Augur Demo Deck",
        output_text=(
            "The Augur Demo Deck critique names Claude and Gemini, cites the offline "
            "OpenVINO proof, and flags empty metadata fields on the slide transcript."
        ),
        duration_ms=1800,
    )

    assert result.case_id == "deck-slide-critique"
    assert result.grounding == result.scores["grounding"]
    assert result.specificity == result.scores["specificity"]
    assert result.judge_readiness == result.scores["judge_readiness"]
    assert result.speed == result.scores["speed"]
    assert result.scores["grounding"] >= 4
    assert result.scores["specificity"] >= 4
    assert result.scores["judge_readiness"] >= 4
    assert result.pass_status == "pass"


def test_score_demo_output_accepts_missing_duration() -> None:
    from skills.evals.scripts import demo_case_eval as mod

    result = mod.score_demo_output(
        case_id="deck-slide-critique",
        source_title="Augur Demo Deck",
        output_text=(
            "Augur Demo Deck output cites Claude, Gemini, offline OpenVINO, "
            "metadata, and the slide transcript."
        ),
        duration_ms=None,
    )

    assert result.speed == 3
    assert result.scores["speed"] == 3
    assert result.pass_status == "pass"


def test_score_demo_output_fails_blank_source_title() -> None:
    from skills.evals.scripts import demo_case_eval as mod

    result = mod.score_demo_output(
        case_id="deck-slide-critique",
        source_title="   ",
        output_text=(
            "This output cites Claude, Gemini, offline OpenVINO, metadata, "
            "and the slide transcript."
        ),
        duration_ms=1800,
    )

    assert result.scores["specificity"] >= 4
    assert result.pass_status == "fail"
    assert any("source title" in finding.lower() for finding in result.findings)


def test_score_demo_output_fails_when_source_title_is_missing() -> None:
    from skills.evals.scripts import demo_case_eval as mod

    result = mod.score_demo_output(
        case_id="deck-slide-critique",
        source_title="Augur Demo Deck",
        output_text=(
            "The output cites Claude, Gemini, offline OpenVINO, metadata, "
            "and the slide transcript."
        ),
        duration_ms=1800,
    )

    assert result.scores["specificity"] >= 4
    assert result.pass_status == "fail"
    assert any("source title" in finding.lower() for finding in result.findings)


def test_score_demo_output_fails_when_duration_is_too_slow() -> None:
    from skills.evals.scripts import demo_case_eval as mod

    result = mod.score_demo_output(
        case_id="deck-slide-critique",
        source_title="Augur Demo Deck",
        output_text=(
            "Augur Demo Deck output cites Claude, Gemini, offline OpenVINO, "
            "metadata, and the slide transcript."
        ),
        duration_ms=60_000,
    )

    assert result.speed == 1
    assert result.scores["speed"] == 1
    assert result.pass_status == "fail"


def test_score_demo_output_passes_deck_at_15s_and_fails_at_20s() -> None:
    from skills.evals.scripts import demo_case_eval as mod

    common = {
        "case_id": "deck-slide-critique",
        "source_title": "Augur Demo Deck",
        "output_text": (
            "Augur Demo Deck output cites Claude, Gemini, offline OpenVINO, "
            "metadata, and the slide transcript."
        ),
    }

    at_bar = mod.score_demo_output(**common, duration_ms=15_000)
    too_slow = mod.score_demo_output(**common, duration_ms=20_000)

    assert at_bar.speed == 3
    assert at_bar.pass_status == "pass"
    assert too_slow.speed < 3
    assert too_slow.pass_status == "fail"
    assert any("too slow" in finding.lower() for finding in too_slow.findings)


def test_score_demo_output_handles_negative_duration_deterministically() -> None:
    from skills.evals.scripts import demo_case_eval as mod

    result = mod.score_demo_output(
        case_id="deck-slide-critique",
        source_title="Augur Demo Deck",
        output_text=(
            "Augur Demo Deck output cites Claude, Gemini, offline OpenVINO, "
            "metadata, and the slide transcript."
        ),
        duration_ms=-1,
    )

    assert result.speed == 1
    assert result.scores["speed"] == 1
    assert result.pass_status == "fail"
    assert any("duration" in finding.lower() for finding in result.findings)


def test_score_demo_output_rewards_grounded_meeting_transcript() -> None:
    from skills.evals.scripts import demo_case_eval as mod

    result = mod.score_demo_output(
        case_id="meeting-transcript",
        source_title="Weekly Planning Transcript",
        output_text=(
            "Weekly Planning Transcript captures the meeting source, transcript, "
            "decisions, and actions for meeting memory."
        ),
        duration_ms=9_000,
    )

    assert result.scores["grounding"] >= 4
    assert result.scores["specificity"] >= 3
    assert result.scores["judge_readiness"] >= 3
    assert result.speed == 3
    assert result.pass_status == "pass"


def test_score_demo_output_allows_local_offload_transcript_runtime() -> None:
    from skills.evals.scripts import demo_case_eval as mod

    result = mod.score_demo_output(
        case_id="meeting-transcript",
        source_title="Offload Demo Offline",
        output_text=(
            "Source: Offload Demo Offline. Route mode: offline. "
            "Selected engine: faster-whisper. Cloud used: false. "
            "Airplane mode ON: using local faster-whisper; cloud transcription "
            "disabled. The transcript shows Augur offload behavior."
        ),
        duration_ms=25_000,
    )

    assert result.scores["grounding"] >= 4
    assert result.scores["specificity"] >= 4
    assert result.scores["judge_readiness"] >= 4
    assert result.speed == 3
    assert result.pass_status == "pass"


def test_score_demo_output_allows_regular_cloud_transcript_overhead() -> None:
    from skills.evals.scripts import demo_case_eval as mod

    result = mod.score_demo_output(
        case_id="meeting-transcript",
        source_title="Offload Demo Online Short",
        output_text=(
            "Source: Offload Demo Online Short. Route mode: regular. "
            "Selected engine: gemini-transcribe. Cloud used: true. "
            "Airplane mode OFF: using gemini-transcribe; local Whisper is not "
            "the selected route. The transcript shows Augur offload behavior."
        ),
        duration_ms=55_000,
    )

    assert result.scores["grounding"] >= 4
    assert result.scores["specificity"] >= 4
    assert result.scores["judge_readiness"] >= 4
    assert result.speed == 3
    assert result.pass_status == "pass"


def test_score_demo_output_allows_real_gemini_transcript_runtime() -> None:
    from skills.evals.scripts import demo_case_eval as mod

    result = mod.score_demo_output(
        case_id="meeting-transcript",
        source_title="Demo 03 online transcription",
        output_text=(
            "Source: Demo 03 online transcription. Route mode: regular. "
            "Selected engine: gemini-transcribe. Cloud used: true. "
            "Airplane mode OFF: using gemini-transcribe; local Whisper is not "
            "the selected route. The transcript shows Augur offload behavior."
        ),
        duration_ms=75_000,
    )

    assert result.speed == 3
    assert result.pass_status == "pass"


def test_score_demo_output_does_not_count_source_title_as_specificity() -> None:
    from skills.evals.scripts import demo_case_eval as mod

    source_title = "Customer Call Transcript Decision Action Offline OpenVINO Browse"
    result = mod.score_demo_output(
        case_id="meeting-transcript",
        source_title=source_title,
        output_text=f"Source: {source_title}. No meeting memory content was captured.",
        duration_ms=3_500,
    )

    assert result.scores["specificity"] < 3
    assert result.pass_status == "fail"


def test_score_demo_output_fails_unsupported_case_id() -> None:
    from skills.evals.scripts import demo_case_eval as mod

    result = mod.score_demo_output(
        case_id="unknown-demo-case",
        source_title="Augur Demo Deck",
        output_text=(
            "Augur Demo Deck output cites Claude, Gemini, offline OpenVINO, "
            "metadata, and the slide transcript."
        ),
        duration_ms=1800,
    )

    assert result.pass_status == "fail"
    assert any("unsupported" in finding.lower() for finding in result.findings)


def test_concrete_term_rewards_are_limited_to_spec_terms() -> None:
    from skills.evals.scripts import demo_case_eval as mod

    assert mod.CONCRETE_TERMS == (
        "openvino",
        "offline",
        "claude",
        "gemini",
        "browse",
        "slide",
        "metadata",
        "transcript",
    )

    result = mod.score_demo_output(
        case_id="deck-slide-critique",
        source_title="",
        output_text="Augur demo deck.",
        duration_ms=1800,
    )

    assert result.scores["specificity"] == 1
    assert not any(
        "concrete demo terms" in finding.lower() for finding in result.findings
    )


def test_score_demo_output_fails_generic_ai_fluff() -> None:
    from skills.evals.scripts import demo_case_eval as mod

    result = mod.score_demo_output(
        case_id="deck-slide-critique",
        source_title="Augur Demo Deck",
        output_text=(
            "This innovative AI solution has many benefits, creates great opportunities, "
            "streamlines workflows, and unlocks value for everyone."
        ),
        duration_ms=1800,
    )

    assert result.scores["grounding"] <= 2
    assert result.pass_status == "fail"
    assert any("generic" in finding.lower() for finding in result.findings)
