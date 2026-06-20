from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from skills.demo.scripts import demo_run_acceptance
from src.lib.frontmatter_utils import parse_frontmatter


def _patch_demo_eval_documents(monkeypatch, tmp_path: Path) -> None:
    from skills.evals.scripts import demo_case_records

    monkeypatch.setattr(
        demo_case_records,
        "get_documents_dir",
        lambda: tmp_path / "documents",
    )
    monkeypatch.setattr(
        demo_case_records,
        "get_documents_machine_dir",
        lambda name: tmp_path / "documents" / "_augur" / name,
    )


def test_ensure_demo_run_note_creates_pinned_acceptance_note(
    tmp_path: Path,
) -> None:
    note_path = demo_run_acceptance.ensure_demo_run_note(vault_dir=tmp_path)

    metadata, body = parse_frontmatter(note_path)
    text = note_path.read_text(encoding="utf-8")

    assert note_path == tmp_path / "notes" / "examples" / "workflow-example-run.md"
    assert text.startswith("---\n")
    assert metadata["title"] == "Workflow Example Run"
    assert metadata["type"] == "workflow-example-acceptance"
    assert metadata["pinned"] is True
    assert metadata["demo_cases"] == ["meeting-transcript", "deck-slide-critique"]
    assert "# Workflow Example Run" in body
    assert "meeting-transcript" in body
    assert "deck-slide-critique" in body
    assert "Workflow example actions stay on real Browse cards." in body


def test_write_demo_evidence_creates_browse_visible_card(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        demo_run_acceptance,
        "_utc_stamp",
        lambda: "20260525T091011Z",
    )
    source_file = tmp_path / "source" / "meeting-transcript.md"
    source_file.parent.mkdir(parents=True)
    source_file.write_text("Transcript source", encoding="utf-8")

    evidence = demo_run_acceptance.write_demo_evidence(
        case_id="meeting-transcript",
        command="inbox-scan folder",
        status="fail",
        backend="local-whisper",
        client="codex",
        duration_seconds=12.5,
        output_path=tmp_path / "notes" / "meetings" / "summary.md",
        failure_reason="No accepted Browse card rendered.",
        missing_prerequisite="Local backend was not running.",
        eval_link="vault://evals/demo/meeting-transcript",
        source_file=source_file,
        useful_snippet="Detected meeting actions and decisions.",
        vault_dir=tmp_path,
    )

    metadata, body = parse_frontmatter(evidence.path)
    text = evidence.path.read_text(encoding="utf-8")

    assert evidence.case_id == "meeting-transcript"
    assert evidence.command == "inbox-scan folder"
    assert evidence.status == "fail"
    assert evidence.backend == "local-whisper"
    assert evidence.client == "codex"
    assert evidence.duration_seconds == 12.5
    assert evidence.output_path == tmp_path / "notes" / "meetings" / "summary.md"
    assert evidence.failure_reason == "No accepted Browse card rendered."
    assert evidence.missing_prerequisite == "Local backend was not running."
    assert evidence.eval_link == "vault://evals/demo/meeting-transcript"
    assert evidence.source_file == source_file
    assert evidence.path == (
        tmp_path
        / "notes"
        / "examples"
        / "evidence"
        / "meeting-transcript-inbox-scan-folder-20260525T091011Z.md"
    )
    assert text.startswith("---\n")
    assert metadata["title"] == "Workflow example evidence: meeting-transcript"
    assert metadata["x-augur-note-type"] == "file"
    assert metadata["demo_case_id"] == "meeting-transcript"
    assert metadata["demo_command"] == "inbox-scan folder"
    assert metadata["demo_status"] == "fail"
    assert metadata["backend"] == "local-whisper"
    assert metadata["client"] == "codex"
    assert metadata["duration_seconds"] == 12.5
    assert metadata["output_path"] == str(
        tmp_path / "notes" / "meetings" / "summary.md"
    )
    assert metadata["failure_reason"] == "No accepted Browse card rendered."
    assert metadata["missing_prerequisite"] == "Local backend was not running."
    assert metadata["eval_link"] == "vault://evals/demo/meeting-transcript"
    assert metadata["source_file_name"] == "meeting-transcript.md"
    assert f"Source path: `{source_file}`" in body
    assert "Client: `codex`" in body
    assert "Backend: `local-whisper`" in body
    assert "Duration: `12.5s`" in body
    assert "Output: `" in body
    assert "Status: `fail`" in body
    assert "Failure reason: No accepted Browse card rendered." in body
    assert "Missing prerequisite: Local backend was not running." in body
    assert "Eval: vault://evals/demo/meeting-transcript" in body
    assert "## Useful Snippet" in body
    assert "Detected meeting actions and decisions." in body


def test_write_demo_evidence_uses_collision_safe_paths(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        demo_run_acceptance,
        "_utc_stamp",
        lambda: "20260525T091011Z",
    )
    source_file = tmp_path / "source" / "meeting-transcript.md"
    source_file.parent.mkdir(parents=True)
    source_file.write_text("Transcript source", encoding="utf-8")

    first = demo_run_acceptance.write_demo_evidence(
        case_id="meeting-transcript",
        command="inbox-scan folder",
        status="pass",
        backend="local-whisper",
        source_file=source_file,
        useful_snippet="First run.",
        vault_dir=tmp_path,
    )
    second = demo_run_acceptance.write_demo_evidence(
        case_id="meeting-transcript",
        command="inbox-scan folder",
        status="pass",
        backend="local-whisper",
        source_file=source_file,
        useful_snippet="Second run.",
        vault_dir=tmp_path,
    )

    assert first.path != second.path
    assert first.path.name == (
        "meeting-transcript-inbox-scan-folder-20260525T091011Z.md"
    )
    assert second.path.name == (
        "meeting-transcript-inbox-scan-folder-20260525T091011Z-2.md"
    )
    assert first.path.exists()
    assert second.path.exists()
    assert "First run." in first.path.read_text(encoding="utf-8")
    assert "Second run." in second.path.read_text(encoding="utf-8")


def test_write_demo_evidence_omits_absent_optional_frontmatter(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        demo_run_acceptance,
        "_utc_stamp",
        lambda: "20260525T091011Z",
    )
    source_file = tmp_path / "source" / "meeting-transcript.md"
    source_file.parent.mkdir(parents=True)
    source_file.write_text("Transcript source", encoding="utf-8")

    evidence = demo_run_acceptance.write_demo_evidence(
        case_id="meeting-transcript",
        command="inbox-scan folder",
        status="blocked",
        backend="local-whisper",
        source_file=source_file,
        useful_snippet="Blocked before capture.",
        vault_dir=tmp_path,
    )

    metadata, body = parse_frontmatter(evidence.path)

    assert "client" not in metadata
    assert "output_path" not in metadata
    assert "failure_reason" not in metadata
    assert "missing_prerequisite" not in metadata
    assert "eval_link" not in metadata
    assert "duration_seconds" not in metadata
    assert "Client: `None`" in body
    assert "Duration: `unknown`" in body
    assert "Output: `None`" in body
    assert "Failure reason: None" in body
    assert "Missing prerequisite: None" in body
    assert "Eval: None" in body


def test_write_demo_evidence_attaches_eval_to_same_card(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        demo_run_acceptance,
        "_utc_stamp",
        lambda: "20260525T091011Z",
    )
    source_file = tmp_path / "source" / "Augur Demo Deck.md"
    source_file.parent.mkdir(parents=True)
    source_file.write_text("Slide critique source", encoding="utf-8")
    record_path = tmp_path / "documents" / "_augur" / "evals" / "demo-runs" / "deck-run.json"
    calls: list[Path] = []

    def fake_eval_runner(**kwargs):
        evidence_path = kwargs["evidence_path"]
        assert evidence_path.exists()
        calls.append(evidence_path)
        return {
            "status": "pass",
            "run_id": "deck-slide-critique-20260525T091011Z",
            "record_path": str(record_path),
            "scores": {
                "grounding": 5,
                "specificity": 4,
                "judge_readiness": 4,
                "speed": 3,
            },
            "findings": ["Concrete slide critique terms found."],
        }

    evidence = demo_run_acceptance.write_demo_evidence(
        case_id="deck-slide-critique",
        command="demo-run-record-evidence",
        status="pass",
        backend="local-critique",
        duration_seconds=4.2,
        source_file=source_file,
        useful_snippet=(
            "Augur Demo Deck names Claude, Gemini, offline OpenVINO, metadata, "
            "and slide transcript risks."
        ),
        run_eval=True,
        eval_runner=fake_eval_runner,
        vault_dir=tmp_path,
    )

    metadata, body = parse_frontmatter(evidence.path)
    evidence_files = sorted((tmp_path / "notes" / "examples" / "evidence").glob("*.md"))

    assert calls == [evidence.path]
    assert evidence_files == [evidence.path]
    assert evidence.eval_run_id == "deck-slide-critique-20260525T091011Z"
    assert evidence.eval_link == str(record_path)
    assert metadata["eval_run_id"] == "deck-slide-critique-20260525T091011Z"
    assert metadata["eval_link"] == str(record_path)
    assert metadata["eval_status"] == "pass"
    assert "## Workflow Example Eval" in body
    assert "Run ID: `deck-slide-critique-20260525T091011Z`" in body
    assert "Record: `" in body
    assert "- grounding: 5" in body
    assert "- Concrete slide critique terms found." in body


def test_write_demo_evidence_uses_display_title_for_eval(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from skills.evals.scripts import demo_case_records

    monkeypatch.setattr(
        demo_run_acceptance,
        "_utc_stamp",
        lambda: "20260525T091011Z",
    )
    monkeypatch.setattr(
        demo_case_records,
        "get_documents_dir",
        lambda: tmp_path / "documents",
    )
    monkeypatch.setattr(
        demo_case_records,
        "get_documents_machine_dir",
        lambda name: tmp_path / "documents" / "_augur" / name,
    )
    source_file = tmp_path / "source" / "deck-export.pdf"
    source_file.parent.mkdir(parents=True)
    source_file.write_bytes(b"%PDF-1.7")

    evidence = demo_run_acceptance.write_demo_evidence(
        case_id="deck-slide-critique",
        command="demo-run-record-evidence",
        status="pass",
        backend="local-critique",
        duration_seconds=4.2,
        source_file=source_file,
        source_title="Q2 Launch Deck Review",
        useful_snippet=(
            "Q2 Launch Deck Review names Claude, Gemini, offline OpenVINO, "
            "metadata, and slide transcript risks for Browse."
        ),
        run_eval=True,
        vault_dir=tmp_path,
    )

    metadata, body = parse_frontmatter(evidence.path)

    assert evidence.eval_success is True
    assert evidence.eval_status == "pass"
    assert evidence.source_title == "Q2 Launch Deck Review"
    assert metadata["source_title"] == "Q2 Launch Deck Review"
    assert "- Title: `Q2 Launch Deck Review`" in body


def test_write_demo_evidence_marks_eval_fail_as_partial(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        demo_run_acceptance,
        "_utc_stamp",
        lambda: "20260525T091011Z",
    )
    source_file = tmp_path / "source" / "Augur Demo Deck.md"
    source_file.parent.mkdir(parents=True)
    source_file.write_text("Slide critique source", encoding="utf-8")

    def fake_eval_runner(**kwargs):
        return {
            "status": "fail",
            "run_id": "deck-fail-run",
            "record_path": str(tmp_path / "documents" / "_augur" / "evals" / "deck-fail.json"),
            "scores": {
                "grounding": 2,
                "specificity": 4,
                "judge_readiness": 2,
                "speed": 3,
            },
            "findings": ["Output did not name the source title: Augur Demo Deck.md."],
        }

    evidence = demo_run_acceptance.write_demo_evidence(
        case_id="deck-slide-critique",
        command="demo-run-record-evidence",
        status="pass",
        backend="local-critique",
        source_file=source_file,
        useful_snippet="The critique mentions Claude and metadata but not the deck.",
        run_eval=True,
        eval_runner=fake_eval_runner,
        vault_dir=tmp_path,
    )

    metadata, body = parse_frontmatter(evidence.path)
    evidence_files = sorted((tmp_path / "notes" / "examples" / "evidence").glob("*.md"))

    assert evidence_files == [evidence.path]
    assert evidence.path.exists()
    assert evidence.status == "fail"
    assert evidence.command_status == "pass"
    assert evidence.eval_success is False
    assert evidence.partial is True
    assert metadata["demo_status"] == "fail"
    assert metadata["command_status"] == "pass"
    assert metadata["eval_status"] == "fail"
    assert metadata["eval_success"] is False
    assert metadata["partial"] is True
    assert "- Status: `fail`" in body
    assert "- Status: `pass`" not in body
    assert "- Command outcome: `pass`" in body
    assert "Output did not name the source title" in body


def test_write_demo_evidence_marks_eval_exception_as_partial(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        demo_run_acceptance,
        "_utc_stamp",
        lambda: "20260525T091011Z",
    )
    source_file = tmp_path / "source" / "Augur Demo Deck.md"
    source_file.parent.mkdir(parents=True)
    source_file.write_text("Slide critique source", encoding="utf-8")

    def fake_eval_runner(**kwargs):
        raise RuntimeError("eval record store unavailable")

    evidence = demo_run_acceptance.write_demo_evidence(
        case_id="deck-slide-critique",
        command="demo-run-record-evidence",
        status="pass",
        backend="local-critique",
        source_file=source_file,
        useful_snippet="Augur Demo Deck names Claude and metadata.",
        run_eval=True,
        eval_runner=fake_eval_runner,
        vault_dir=tmp_path,
    )

    metadata, body = parse_frontmatter(evidence.path)
    evidence_files = sorted((tmp_path / "notes" / "examples" / "evidence").glob("*.md"))

    assert evidence_files == [evidence.path]
    assert evidence.path.exists()
    assert evidence.status == "fail"
    assert evidence.command_status == "pass"
    assert evidence.eval_success is False
    assert evidence.partial is True
    assert metadata["demo_status"] == "fail"
    assert metadata["command_status"] == "pass"
    assert metadata["eval_status"] == "error"
    assert metadata["eval_success"] is False
    assert metadata["partial"] is True
    assert metadata["eval_error"] == "eval record store unavailable"
    assert "- Status: `fail`" in body
    assert "- Status: `pass`" not in body
    assert "- Command outcome: `pass`" in body
    assert "- Error: eval record store unavailable" in body


def test_reset_demo_run_state_updates_note_and_preserves_evidence(
    tmp_path: Path,
) -> None:
    demo_run_acceptance.ensure_demo_run_note(vault_dir=tmp_path)
    evidence_dir = tmp_path / "notes" / "examples" / "evidence"
    evidence_dir.mkdir(parents=True)
    existing_evidence = evidence_dir / "meeting-transcript-existing.md"
    existing_evidence.write_text("existing evidence", encoding="utf-8")

    note_path = demo_run_acceptance.reset_demo_run_state(
        reason="practice-loop",
        vault_dir=tmp_path,
    )

    _, body = parse_frontmatter(note_path)

    assert "Current rehearsal state: reset" in body
    assert "Reset reason: practice-loop" in body
    assert existing_evidence.exists()
    assert existing_evidence.read_text(encoding="utf-8") == "existing evidence"


def test_run_transcript_case_writes_transcript_and_evidence(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        demo_run_acceptance,
        "_utc_stamp",
        lambda: "20260525T091011Z",
    )
    perf_counter_values = iter([100.0, 103.5])
    monkeypatch.setattr(
        demo_run_acceptance.time,
        "perf_counter",
        lambda: next(perf_counter_values),
    )
    source_file = tmp_path / "media" / "launch sync.m4a"
    source_file.parent.mkdir(parents=True)
    source_file.write_bytes(b"audio")

    def fake_transcribe(path: Path):
        assert path == source_file
        return SimpleNamespace(
            success=True,
            transcript="Decision: ship transcript actions. Action: Dana follows up.",
            method="offline-whisper",
            backend="mlx",
            duration_s=42.25,
            error=None,
        )

    result = demo_run_acceptance.run_transcript_case(
        source_file,
        transcribe=fake_transcribe,
        vault_dir=tmp_path,
    )

    transcript_path = Path(result["transcript_path"])
    evidence_path = Path(result["evidence_path"])
    metadata, body = parse_frontmatter(transcript_path)
    evidence_metadata, evidence_body = parse_frontmatter(evidence_path)

    assert result["status"] == "pass"
    assert result["backend"] == "mlx"
    assert transcript_path == (
        tmp_path / "notes" / "examples" / "transcripts" / "launch-sync-20260525T091011Z.md"
    )
    assert metadata["type"] == "workflow-example-transcript"
    assert metadata["source_file_path"] == str(source_file)
    assert metadata["backend"] == "mlx"
    assert metadata["method"] == "offline-whisper"
    assert metadata["duration_seconds"] == 3.5
    assert metadata["media_duration_seconds"] == 42.25
    assert result["duration_seconds"] == 3.5
    assert result["media_duration_seconds"] == 42.25
    assert "Decision: ship transcript actions." in body
    assert evidence_metadata["demo_command"] == "Transcript"
    assert evidence_metadata["demo_status"] == "pass"
    assert evidence_metadata["backend"] == "mlx"
    assert evidence_metadata["output_path"] == str(transcript_path)
    assert "Decision: ship transcript actions." in evidence_body


def test_run_transcript_case_replace_existing_removes_previous_source_cards(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        demo_run_acceptance,
        "_utc_stamp",
        lambda: "20260525T091011Z",
    )
    perf_counter_values = iter([100.0, 101.0])
    monkeypatch.setattr(
        demo_run_acceptance.time,
        "perf_counter",
        lambda: next(perf_counter_values),
    )
    source_file = tmp_path / "media" / "launch sync.m4a"
    source_file.parent.mkdir(parents=True)
    source_file.write_bytes(b"audio")
    old_transcript = (
        tmp_path / "notes" / "examples" / "transcripts" / "launch-sync-20260524T010101Z.md"
    )
    old_transcript.parent.mkdir(parents=True)
    old_transcript.write_text("old transcript", encoding="utf-8")
    old_evidence = (
        tmp_path
        / "notes"
        / "examples"
        / "evidence"
        / "meeting-transcript-transcript-20260524T010101Z.md"
    )
    demo_run_acceptance.write_vault_frontmatter(
        old_evidence,
        {
            "title": "Old Evidence",
            "type": "workflow-example-evidence",
            "source_file_path": str(source_file),
            "output_path": str(old_transcript),
        },
        "old evidence",
    )

    def fake_transcribe(path: Path):
        assert path == source_file
        return SimpleNamespace(
            success=True,
            transcript="Decision: keep only the current transcript card.",
            method="offline-whisper",
            backend="mlx",
            duration_s=12.0,
            error=None,
        )

    result = demo_run_acceptance.run_transcript_case(
        source_file,
        transcribe=fake_transcribe,
        vault_dir=tmp_path,
        replace_existing=True,
    )

    transcript_dir = tmp_path / "notes" / "examples" / "transcripts"
    evidence_dir = tmp_path / "notes" / "examples" / "evidence"
    assert result["status"] == "pass"
    assert not old_transcript.exists()
    assert not old_evidence.exists()
    assert sorted(path.name for path in transcript_dir.glob("launch-sync-*.md")) == [
        "launch-sync-20260525T091011Z.md"
    ]
    assert len(list(evidence_dir.glob("meeting-transcript-transcript-*.md"))) == 1


def test_run_transcript_case_real_eval_uses_display_title_in_snippet(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _patch_demo_eval_documents(monkeypatch, tmp_path)
    monkeypatch.setattr(
        demo_run_acceptance,
        "_utc_stamp",
        lambda: "20260525T091011Z",
    )
    source_file = tmp_path / "media" / "call-001.m4a"
    source_file.parent.mkdir(parents=True)
    source_file.write_bytes(b"audio")

    def fake_transcribe(path: Path):
        assert path == source_file
        return SimpleNamespace(
            success=True,
            transcript=(
                "Transcript records offline OpenVINO meeting decisions and "
                "actions for Browse."
            ),
            method="offline-whisper",
            backend="mlx",
            duration_s=4.2,
            error=None,
        )

    result = demo_run_acceptance.run_transcript_case(
        source_file,
        transcribe=fake_transcribe,
        source_title="Customer Call",
        run_eval=True,
        vault_dir=tmp_path,
    )

    _, evidence_body = parse_frontmatter(Path(result["evidence_path"]))

    assert source_file.name != "Customer Call"
    assert result["success"] is True
    assert result["status"] == "pass"
    assert result["eval_success"] is True
    assert result["eval_status"] == "pass"
    assert result["source_title"] == "Customer Call"
    assert "Source: Customer Call." in evidence_body
    assert "Transcript records offline OpenVINO meeting decisions" in evidence_body


def test_run_transcript_case_missing_source_writes_blocked_evidence(
    tmp_path: Path,
) -> None:
    missing_source = tmp_path / "media" / "missing.m4a"

    result = demo_run_acceptance.run_transcript_case(
        missing_source,
        transcribe=lambda path: None,
        vault_dir=tmp_path,
    )

    evidence_path = Path(result["evidence_path"])
    metadata, body = parse_frontmatter(evidence_path)

    assert result["success"] is False
    assert result["status"] == "blocked"
    assert "missing" in str(result["missing_prerequisite"]).lower()
    assert metadata["demo_command"] == "Transcript"
    assert metadata["demo_status"] == "blocked"
    assert metadata["missing_prerequisite"]
    assert f"Source path: `{missing_source}`" in body


def test_default_transcribe_does_not_force_offline(
    monkeypatch,
    tmp_path: Path,
) -> None:
    import src.lib.routing as routing

    source_file = tmp_path / "media" / "call.m4a"
    source_file.parent.mkdir(parents=True)
    source_file.write_bytes(b"audio")
    captured = {}

    def fake_transcribe(path: str, **kwargs):
        captured["path"] = path
        captured["kwargs"] = kwargs
        return SimpleNamespace(
            success=True,
            transcript="hello",
            method="gemini-transcribe",
            backend="gemini",
            route_mode="regular",
            route_engine_id="gemini-transcribe",
            fallback_engine_id=None,
            cloud_used=True,
            needs_review=False,
            note=None,
        )

    monkeypatch.setattr(routing, "transcribe", fake_transcribe)

    result = demo_run_acceptance._default_transcribe(source_file)

    assert result.method == "gemini-transcribe"
    assert captured["path"] == str(source_file)
    assert captured["kwargs"] == {}


def test_run_transcript_case_persists_route_disclosure(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        demo_run_acceptance,
        "_utc_stamp",
        lambda: "20260601T010203Z",
    )
    perf_counter_values = iter([10.0, 12.0])
    monkeypatch.setattr(
        demo_run_acceptance.time,
        "perf_counter",
        lambda: next(perf_counter_values),
    )
    source_file = tmp_path / "media" / "offload-demo.m4a"
    source_file.parent.mkdir(parents=True)
    source_file.write_bytes(b"audio")

    def fake_transcribe(path: Path):
        assert path == source_file
        return SimpleNamespace(
            success=True,
            transcript="Augur routes offline audio locally.",
            method="faster-whisper",
            backend="faster-whisper-small",
            duration_s=111.72,
            error=None,
            route_mode="offline",
            route_engine_id="faster-whisper",
            fallback_engine_id=None,
            cloud_used=False,
            needs_review=False,
            note=(
                "Airplane mode ON: using local faster-whisper on macOS; "
                "cloud transcription disabled."
            ),
        )

    result = demo_run_acceptance.run_transcript_case(
        source_file,
        transcribe=fake_transcribe,
        vault_dir=tmp_path,
    )

    transcript_metadata, transcript_body = parse_frontmatter(
        Path(result["transcript_path"])
    )
    evidence_metadata, evidence_body = parse_frontmatter(Path(result["evidence_path"]))

    assert result["route_mode"] == "offline"
    assert result["route_engine_id"] == "faster-whisper"
    assert result["cloud_used"] is False
    assert result["needs_review"] is False
    assert transcript_metadata["route_mode"] == "offline"
    assert transcript_metadata["route_engine_id"] == "faster-whisper"
    assert transcript_metadata["cloud_used"] is False
    assert transcript_metadata["route_note"].startswith("Airplane mode ON")
    assert "## Routing" in transcript_body
    assert "- Mode: `offline`" in transcript_body
    assert "- Selected engine: `faster-whisper`" in transcript_body
    assert "- Cloud used: `false`" in transcript_body
    assert evidence_metadata["route_mode"] == "offline"
    assert evidence_metadata["route_engine_id"] == "faster-whisper"
    assert evidence_metadata["cloud_used"] is False
    assert "## Routing" in evidence_body
    assert "Mode: `offline`" in evidence_body


def test_run_transcript_case_real_eval_accepts_offload_route_evidence(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _patch_demo_eval_documents(monkeypatch, tmp_path)
    monkeypatch.setattr(
        demo_run_acceptance,
        "_utc_stamp",
        lambda: "20260601T020304Z",
    )
    perf_counter_values = iter([30.0, 46.0])
    monkeypatch.setattr(
        demo_run_acceptance.time,
        "perf_counter",
        lambda: next(perf_counter_values),
    )
    source_file = tmp_path / "media" / "offload-demo.m4a"
    source_file.parent.mkdir(parents=True)
    source_file.write_bytes(b"audio")

    def fake_transcribe(path: Path):
        assert path == source_file
        return SimpleNamespace(
            success=True,
            transcript=(
                "Okay, I am recording a demo from the transcript. "
                "This demo shows Augur offload behavior on the laptop."
            ),
            method="faster-whisper",
            backend="faster-whisper-small",
            duration_s=111.72,
            error=None,
            route_mode="offline",
            route_engine_id="faster-whisper",
            fallback_engine_id=None,
            cloud_used=False,
            needs_review=False,
            note=(
                "Airplane mode ON: using local faster-whisper; "
                "cloud transcription disabled."
            ),
        )

    result = demo_run_acceptance.run_transcript_case(
        source_file,
        transcribe=fake_transcribe,
        source_title="Offload Demo Offline",
        run_eval=True,
        vault_dir=tmp_path,
    )

    _, evidence_body = parse_frontmatter(Path(result["evidence_path"]))

    assert result["success"] is True
    assert result["status"] == "pass"
    assert result["eval_success"] is True
    assert result["eval_status"] == "pass"
    assert result["route_mode"] == "offline"
    assert result["route_engine_id"] == "faster-whisper"
    assert result["cloud_used"] is False
    assert "Airplane mode ON" in evidence_body


def test_run_transcript_case_marks_regular_fallback_route(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        demo_run_acceptance,
        "_utc_stamp",
        lambda: "20260601T040506Z",
    )
    perf_counter_values = iter([20.0, 24.0])
    monkeypatch.setattr(
        demo_run_acceptance.time,
        "perf_counter",
        lambda: next(perf_counter_values),
    )
    source_file = tmp_path / "media" / "offload-demo.m4a"
    source_file.parent.mkdir(parents=True)
    source_file.write_bytes(b"audio")

    def fake_transcribe(path: Path):
        return SimpleNamespace(
            success=True,
            transcript="Gemini was unavailable, local fallback transcribed this.",
            method="faster-whisper",
            backend="faster-whisper-small",
            duration_s=111.72,
            error=None,
            route_mode="regular",
            route_engine_id="gemini-transcribe",
            fallback_engine_id="faster-whisper",
            cloud_used=False,
            needs_review=True,
            note=(
                "used local fallback (faster-whisper); gemini unavailable: "
                "Gemini CLI not found"
            ),
        )

    result = demo_run_acceptance.run_transcript_case(
        source_file,
        transcribe=fake_transcribe,
        vault_dir=tmp_path,
    )

    transcript_metadata, transcript_body = parse_frontmatter(
        Path(result["transcript_path"])
    )
    evidence_metadata, evidence_body = parse_frontmatter(Path(result["evidence_path"]))

    assert result["route_mode"] == "regular"
    assert result["route_engine_id"] == "gemini-transcribe"
    assert result["fallback_engine_id"] == "faster-whisper"
    assert result["needs_review"] is True
    assert result["partial"] is True
    assert transcript_metadata["fallback_engine_id"] == "faster-whisper"
    assert transcript_metadata["needs_review"] is True
    assert "Fallback engine: `faster-whisper`" in transcript_body
    assert evidence_metadata["fallback_engine_id"] == "faster-whisper"
    assert evidence_metadata["needs_review"] is True
    assert evidence_metadata["partial"] is True
    assert "fallback" in evidence_body.lower()


def test_run_transcript_case_keeps_fallback_partial_when_eval_passes(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        demo_run_acceptance,
        "_utc_stamp",
        lambda: "20260601T050607Z",
    )
    perf_counter_values = iter([40.0, 44.0])
    monkeypatch.setattr(
        demo_run_acceptance.time,
        "perf_counter",
        lambda: next(perf_counter_values),
    )
    source_file = tmp_path / "media" / "offload-demo.m4a"
    source_file.parent.mkdir(parents=True)
    source_file.write_bytes(b"audio")

    def fake_transcribe(path: Path):
        return SimpleNamespace(
            success=True,
            transcript="Gemini was unavailable, local fallback transcribed this.",
            method="faster-whisper",
            backend="faster-whisper-small",
            duration_s=111.72,
            error=None,
            route_mode="regular",
            route_engine_id="gemini-transcribe",
            fallback_engine_id="faster-whisper",
            cloud_used=False,
            needs_review=True,
            note=(
                "used local fallback (faster-whisper); gemini unavailable: "
                "Gemini CLI not found"
            ),
        )

    def fake_eval_runner(**kwargs):
        return {
            "status": "pass",
            "run_id": "meeting-transcript-fallback-pass",
            "record_path": str(tmp_path / "documents" / "_augur" / "evals" / "fallback.json"),
            "scores": {"grounding": 4, "specificity": 4},
            "findings": ["Fallback route disclosed."],
        }

    result = demo_run_acceptance.run_transcript_case(
        source_file,
        transcribe=fake_transcribe,
        run_eval=True,
        eval_runner=fake_eval_runner,
        vault_dir=tmp_path,
    )

    evidence_metadata, evidence_body = parse_frontmatter(Path(result["evidence_path"]))

    assert result["status"] == "pass"
    assert result["eval_success"] is True
    assert result["partial"] is True
    assert result["fallback_engine_id"] == "faster-whisper"
    assert evidence_metadata["eval_success"] is True
    assert evidence_metadata["partial"] is True
    assert "Fallback engine: `faster-whisper`" in evidence_body


def test_run_meeting_memory_case_finds_latest_transcript_and_writes_artifact(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        demo_run_acceptance,
        "_utc_stamp",
        lambda: "20260525T111213Z",
    )
    source_file = tmp_path / "media" / "planning.m4a"
    source_file.parent.mkdir(parents=True)
    source_file.write_bytes(b"audio")
    transcripts = tmp_path / "notes" / "examples" / "transcripts"
    old_transcript = transcripts / "planning-20260525T090000Z.md"
    new_transcript = transcripts / "planning-20260525T100000Z.md"
    old_transcript.parent.mkdir(parents=True)
    write_body = (
        "Decision: use Browse cards. Action: Sam prepares the demo. "
        "Follow-up: Riley validates evidence."
    )
    for path in (old_transcript, new_transcript):
        demo_run_acceptance.write_vault_frontmatter(
            path,
            {
                "title": path.stem,
                "type": "workflow-example-transcript",
                "source_file_path": str(source_file),
                "backend": "mlx",
            },
            write_body,
        )

    result = demo_run_acceptance.run_meeting_memory_case(
        source_path=source_file,
        vault_dir=tmp_path,
    )

    memory_path = Path(result["memory_path"])
    evidence_path = Path(result["evidence_path"])
    metadata, body = parse_frontmatter(memory_path)
    evidence_metadata, _ = parse_frontmatter(evidence_path)

    assert result["status"] == "pass"
    assert result["transcript_path"] == str(new_transcript)
    assert metadata["type"] == "workflow-example-meeting-memory"
    assert metadata["source_file_path"] == str(source_file)
    assert metadata["transcript_path"] == str(new_transcript)
    assert "## Summary" in body
    assert "Decision: use Browse cards." in body
    assert "Sam prepares the demo." in body
    assert "Riley validates evidence." in body
    assert evidence_metadata["demo_command"] == "Meeting Memory"
    assert evidence_metadata["output_path"] == str(memory_path)


def test_run_meeting_memory_case_real_eval_uses_display_title_in_snippet(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _patch_demo_eval_documents(monkeypatch, tmp_path)
    monkeypatch.setattr(
        demo_run_acceptance,
        "_utc_stamp",
        lambda: "20260525T111213Z",
    )
    source_file = tmp_path / "media" / "call-001.m4a"
    source_file.parent.mkdir(parents=True)
    source_file.write_bytes(b"audio")
    transcript_path = tmp_path / "notes" / "examples" / "transcripts" / "call.md"
    demo_run_acceptance.write_vault_frontmatter(
        transcript_path,
        {
            "title": "Call Transcript",
            "type": "workflow-example-transcript",
            "source_file_path": str(source_file),
            "backend": "mlx",
        },
        (
            "Transcript records offline OpenVINO meeting context. "
            "Decision: keep Browse evidence visible. "
            "Action: Lena sends the checklist."
        ),
    )

    result = demo_run_acceptance.run_meeting_memory_case(
        source_path=source_file,
        transcript_path=transcript_path,
        source_title="Customer Call",
        run_eval=True,
        vault_dir=tmp_path,
    )

    _, evidence_body = parse_frontmatter(Path(result["evidence_path"]))

    assert source_file.name != "Customer Call"
    assert result["success"] is True
    assert result["status"] == "pass"
    assert result["eval_success"] is True
    assert result["eval_status"] == "pass"
    assert result["source_title"] == "Customer Call"
    assert "Source: Customer Call." in evidence_body
    assert "Transcript records offline OpenVINO meeting context" in evidence_body


def test_run_meeting_memory_case_real_eval_fails_without_captured_content(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _patch_demo_eval_documents(monkeypatch, tmp_path)
    monkeypatch.setattr(
        demo_run_acceptance,
        "_utc_stamp",
        lambda: "20260525T111213Z",
    )
    source_file = tmp_path / "media" / "empty-call.m4a"
    source_file.parent.mkdir(parents=True)
    source_file.write_bytes(b"audio")
    transcript_path = tmp_path / "notes" / "examples" / "transcripts" / "empty-call.md"
    demo_run_acceptance.write_vault_frontmatter(
        transcript_path,
        {
            "title": "Empty Call Transcript",
            "type": "workflow-example-transcript",
            "source_file_path": str(source_file),
            "backend": "mlx",
        },
        "",
    )

    result = demo_run_acceptance.run_meeting_memory_case(
        source_path=source_file,
        transcript_path=transcript_path,
        source_title="Empty Customer Call",
        run_eval=True,
        vault_dir=tmp_path,
    )

    metadata, evidence_body = parse_frontmatter(Path(result["evidence_path"]))

    assert result["success"] is False
    assert result["status"] == "fail"
    assert result["eval_success"] is False
    assert result["eval_status"] == "fail"
    assert result["partial"] is True
    assert metadata["demo_status"] == "fail"
    assert metadata["command_status"] == "pass"
    assert "Source: Empty Customer Call." in evidence_body
    assert "No meeting memory content was captured." in evidence_body
    assert "No transcript summary was captured." not in evidence_body
    assert "None captured." not in evidence_body


def test_run_meeting_memory_case_real_eval_fails_on_generated_transcript_scaffold(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _patch_demo_eval_documents(monkeypatch, tmp_path)
    monkeypatch.setattr(
        demo_run_acceptance,
        "_utc_stamp",
        lambda: "20260525T111213Z",
    )
    source_file = tmp_path / "media" / "scaffold-call.m4a"
    source_file.parent.mkdir(parents=True)
    source_file.write_bytes(b"audio")
    transcript_path = tmp_path / "notes" / "examples" / "transcripts" / "scaffold-call.md"
    display_title = "Customer Call Transcript Decision Action Offline OpenVINO Browse"
    demo_run_acceptance.write_vault_frontmatter(
        transcript_path,
        {
            "title": "Generated Transcript",
            "type": "workflow-example-transcript",
            "source_file_path": str(source_file),
            "backend": "offline OpenVINO Browse",
        },
        demo_run_acceptance._transcript_body(
            source_path=source_file,
            transcript="",
            method="offline OpenVINO",
            backend="Browse",
            duration_seconds=3.5,
        ),
    )

    result = demo_run_acceptance.run_meeting_memory_case(
        source_path=source_file,
        transcript_path=transcript_path,
        source_title=display_title,
        run_eval=True,
        vault_dir=tmp_path,
    )

    metadata, evidence_body = parse_frontmatter(Path(result["evidence_path"]))

    assert result["success"] is False
    assert result["status"] == "fail"
    assert result["eval_success"] is False
    assert result["eval_status"] == "fail"
    assert result["partial"] is True
    assert metadata["demo_status"] == "fail"
    assert metadata["command_status"] == "pass"
    assert "No meeting memory content was captured." in evidence_body
    assert "offline OpenVINO" not in evidence_body
    assert "Backend: `Browse`" not in evidence_body


def test_run_meeting_memory_case_blocks_non_transcript_markdown(
    tmp_path: Path,
) -> None:
    transcript_path = tmp_path / "notes" / "examples" / "transcripts" / "note.md"
    demo_run_acceptance.write_vault_frontmatter(
        transcript_path,
        {
            "title": "Not a transcript",
            "type": "demo-note",
        },
        "Decision: this should not be accepted.",
    )

    result = demo_run_acceptance.run_meeting_memory_case(
        transcript_path=transcript_path,
        vault_dir=tmp_path,
    )

    evidence_path = Path(result["evidence_path"])
    evidence_metadata, evidence_body = parse_frontmatter(evidence_path)

    assert result["success"] is False
    assert result["status"] == "blocked"
    assert "workflow-example-transcript" in str(result["failure_reason"])
    assert result["transcript_path"] == str(transcript_path)
    assert "memory_path" not in result
    assert evidence_metadata["demo_command"] == "Meeting Memory"
    assert evidence_metadata["demo_status"] == "blocked"
    assert "workflow-example-transcript" in evidence_body


def test_run_meeting_memory_case_blocks_explicit_source_mismatch(
    tmp_path: Path,
) -> None:
    original_source = tmp_path / "media" / "original.m4a"
    requested_source = tmp_path / "media" / "requested.m4a"
    original_source.parent.mkdir(parents=True)
    original_source.write_bytes(b"audio")
    requested_source.write_bytes(b"audio")
    transcript_path = tmp_path / "notes" / "examples" / "transcripts" / "original.md"
    demo_run_acceptance.write_vault_frontmatter(
        transcript_path,
        {
            "title": "Original Transcript",
            "type": "workflow-example-transcript",
            "source_file_path": str(original_source),
        },
        "Decision: keep source identity.",
    )

    result = demo_run_acceptance.run_meeting_memory_case(
        source_path=requested_source,
        transcript_path=transcript_path,
        vault_dir=tmp_path,
    )

    evidence_metadata, evidence_body = parse_frontmatter(Path(result["evidence_path"]))

    assert result["success"] is False
    assert result["status"] == "blocked"
    assert "does not match" in str(result["failure_reason"])
    assert str(requested_source) in str(result["failure_reason"])
    assert str(original_source) in str(result["failure_reason"])
    assert evidence_metadata["demo_status"] == "blocked"
    assert "does not match" in evidence_body


def test_run_meeting_memory_case_blocks_transcript_parse_failure(
    tmp_path: Path,
    monkeypatch,
) -> None:
    transcript_path = tmp_path / "notes" / "examples" / "transcripts" / "broken.md"
    transcript_path.parent.mkdir(parents=True)
    transcript_path.write_bytes(b"\xff\xfe")

    def fake_parse_frontmatter(path: Path, *args, **kwargs):
        if path == transcript_path:
            raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte")
        return parse_frontmatter(path, *args, **kwargs)

    monkeypatch.setattr(
        demo_run_acceptance,
        "parse_frontmatter",
        fake_parse_frontmatter,
    )

    result = demo_run_acceptance.run_meeting_memory_case(
        transcript_path=transcript_path,
        vault_dir=tmp_path,
    )

    evidence_metadata, evidence_body = parse_frontmatter(Path(result["evidence_path"]))

    assert result["success"] is False
    assert result["status"] == "blocked"
    assert str(transcript_path) in str(result["failure_reason"])
    assert "invalid start byte" in str(result["failure_reason"])
    assert evidence_metadata["demo_status"] == "blocked"
    assert str(transcript_path) in evidence_body
    assert "invalid start byte" in evidence_body


def test_run_ask_transcript_case_returns_grounded_answer_and_writes_artifact(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        demo_run_acceptance,
        "_utc_stamp",
        lambda: "20260525T141516Z",
    )
    source_file = tmp_path / "media" / "customer call.m4a"
    source_file.parent.mkdir(parents=True)
    source_file.write_bytes(b"audio")
    transcript_path = tmp_path / "notes" / "examples" / "transcripts" / "customer-call.md"
    demo_run_acceptance.write_vault_frontmatter(
        transcript_path,
        {
            "title": "Customer Call",
            "type": "workflow-example-transcript",
            "source_file_path": str(source_file),
            "backend": "mlx",
        },
        (
            "The customer approved the Atlas rollout. "
            "Decision: prepare onboarding by Friday. "
            "Action: Lena sends the migration checklist."
        ),
    )

    result = demo_run_acceptance.run_ask_transcript_case(
        source_path=source_file,
        question="What Atlas actions were agreed?",
        vault_dir=tmp_path,
    )

    answer_path = Path(result["answer_path"])
    evidence_path = Path(result["evidence_path"])
    metadata, body = parse_frontmatter(answer_path)
    evidence_metadata, evidence_body = parse_frontmatter(evidence_path)

    assert result["status"] == "pass"
    assert "Atlas" in result["answer"]
    assert "onboarding" in result["answer"] or "migration checklist" in result["answer"]
    assert metadata["type"] == "workflow-example-transcript-answer"
    assert metadata["question"] == "What Atlas actions were agreed?"
    assert metadata["transcript_path"] == str(transcript_path)
    assert str(transcript_path) in body
    assert "Atlas" in body
    assert evidence_metadata["demo_command"] == "Ask From Transcript"
    assert evidence_metadata["output_path"] == str(answer_path)
    assert "Atlas" in evidence_body


def test_run_ask_transcript_case_real_eval_uses_display_title_in_snippet(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _patch_demo_eval_documents(monkeypatch, tmp_path)
    monkeypatch.setattr(
        demo_run_acceptance,
        "_utc_stamp",
        lambda: "20260525T141516Z",
    )
    source_file = tmp_path / "media" / "call-001.m4a"
    source_file.parent.mkdir(parents=True)
    source_file.write_bytes(b"audio")
    transcript_path = tmp_path / "notes" / "examples" / "transcripts" / "call.md"
    demo_run_acceptance.write_vault_frontmatter(
        transcript_path,
        {
            "title": "Call Transcript",
            "type": "workflow-example-transcript",
            "source_file_path": str(source_file),
            "backend": "mlx",
        },
        (
            "Transcript records offline OpenVINO meeting context. "
            "Decision: keep Browse evidence visible. "
            "Action: Lena sends the checklist."
        ),
    )

    result = demo_run_acceptance.run_ask_transcript_case(
        source_path=source_file,
        transcript_path=transcript_path,
        question="What Browse action was agreed?",
        source_title="Customer Call",
        run_eval=True,
        vault_dir=tmp_path,
    )

    _, evidence_body = parse_frontmatter(Path(result["evidence_path"]))

    assert source_file.name != "Customer Call"
    assert result["success"] is True
    assert result["status"] == "pass"
    assert result["eval_success"] is True
    assert result["eval_status"] == "pass"
    assert result["source_title"] == "Customer Call"
    assert "Source: Customer Call." in evidence_body
    assert "Browse evidence visible" in evidence_body


def test_run_ask_transcript_case_blocks_when_no_question_evidence(
    tmp_path: Path,
) -> None:
    transcript_path = tmp_path / "notes" / "examples" / "transcripts" / "roadmap.md"
    demo_run_acceptance.write_vault_frontmatter(
        transcript_path,
        {
            "title": "Roadmap Transcript",
            "type": "workflow-example-transcript",
        },
        "The team discussed pricing and launch dates.",
    )

    result = demo_run_acceptance.run_ask_transcript_case(
        transcript_path=transcript_path,
        question="What did Atlas decide?",
        vault_dir=tmp_path,
    )

    evidence_metadata, evidence_body = parse_frontmatter(Path(result["evidence_path"]))

    assert result["success"] is False
    assert result["status"] == "blocked"
    assert "answer_path" not in result
    assert "No transcript evidence matched" in str(result["failure_reason"])
    assert evidence_metadata["demo_command"] == "Ask From Transcript"
    assert evidence_metadata["demo_status"] == "blocked"
    assert "No transcript evidence matched" in evidence_body


def test_run_ask_transcript_case_blocks_substring_false_positive(
    tmp_path: Path,
) -> None:
    transcript_path = tmp_path / "notes" / "examples" / "transcripts" / "atlas.md"
    demo_run_acceptance.write_vault_frontmatter(
        transcript_path,
        {
            "title": "Atlas Transcript",
            "type": "workflow-example-transcript",
        },
        "The catlastic rollout was mentioned without naming the project.",
    )

    result = demo_run_acceptance.run_ask_transcript_case(
        transcript_path=transcript_path,
        question="What did Atlas decide?",
        vault_dir=tmp_path,
    )

    evidence_metadata, evidence_body = parse_frontmatter(Path(result["evidence_path"]))

    assert result["success"] is False
    assert result["status"] == "blocked"
    assert "answer_path" not in result
    assert "No transcript evidence matched" in str(result["failure_reason"])
    assert evidence_metadata["demo_status"] == "blocked"
    assert "catlastic" in evidence_body
