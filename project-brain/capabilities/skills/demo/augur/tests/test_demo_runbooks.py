from __future__ import annotations

from pathlib import Path

from src.lib.frontmatter_utils import parse_frontmatter


DEMO_DIR = Path(__file__).resolve().parents[2] / "demos"

EXPECTED_DEMOS = [
    "demo_01_wiki_llm_cross_agent_ask.md",
    "demo_02_discover_gui_web_capture.md",
    "demo_03_offload_transcription_airplane.md",
    "demo_04_compound_dry_run.md",
    "demo_05_airplane_safety_evidence.md",
    "demo_06_brain_manifest_architecture.md",
]

EXPECTED_BOUNDED_COMMANDS = {
    "demo_01_wiki_llm_cross_agent_ask.md": "uv run aug demo-run-wiki-ask --days-back 90 --limit 5",
    "demo_02_discover_gui_web_capture.md": "uv run aug demo-run-discover-capture",
    "demo_03_offload_transcription_airplane.md": (
        "uv run aug demo-run-transcription-offload "
        "--source-path ~/Projects/Au-vault/voice-memos/2026-06-01-offload-demo-short.m4a"
    ),
    "demo_04_compound_dry_run.md": "uv run aug demo-run-compound-preview --days-back 90 --limit 5",
    "demo_05_airplane_safety_evidence.md": "uv run aug demo-run-airplane-safety",
    "demo_06_brain_manifest_architecture.md": "uv run aug demo-run-brain-manifest",
}


def test_ingest_demo_runbooks_exist_and_are_agent_ready() -> None:
    assert DEMO_DIR.is_dir()

    for file_name in EXPECTED_DEMOS:
        path = DEMO_DIR / file_name
        assert path.exists(), file_name
        metadata, body = parse_frontmatter(path)

        assert metadata["type"] == "demo-runbook"
        assert metadata["pinned"] is True
        assert metadata["x-augur-note-type"] == "file"
        assert metadata["demo_id"] == file_name.removesuffix(".md")
        assert "example" in metadata["tags"]
        assert "workflow-example" in metadata["tags"]
        assert "## Agent Prompt" in body
        assert "## Expected Visible Output" in body
        assert "## Automatic Reset / Idempotency" in body
        assert "## Live Flow" in body
        assert "## Success Criteria" in body
        assert "## Stop Conditions" in body
        assert "## Judge Talking Points" in body
        assert "demo-run-reset" in body
        assert "Reset proof:" in body
        assert "Human artifact:" in body
        assert "## Bounded Live Command" in body
        assert EXPECTED_BOUNDED_COMMANDS[file_name] in body
        assert "Return only the final workflow example output block" in body


def test_ingest_demo_runbooks_define_repeatable_live_start() -> None:
    expected_markers = {
        "demo_01_wiki_llm_cross_agent_ask.md": [
            "before-demo_01_wiki_llm_cross_agent_ask",
            "uv run aug demo-run-wiki-ask --days-back 90 --limit 5",
            "Do not run ad hoc Python",
            "Return only the final workflow example output block",
            "skip the retained seed unless fresh retention is explicitly needed",
        ],
        "demo_02_discover_gui_web_capture.md": [
            "before-demo_02_discover_gui_web_capture",
            "uv run aug demo-run-discover-capture",
            "https://www.iana.org/domains/reserved",
            "IANA-managed Reserved Domains",
            "dedupe or refresh the existing source card",
        ],
        "demo_03_offload_transcription_airplane.md": [
            "before-demo_03_offload_transcription_airplane",
            "uv run aug demo-run-transcription-offload",
            "Use the Augur-owned short clip as the canonical input",
            "10-second workflow example budget",
        ],
        "demo_04_compound_dry_run.md": [
            "before-demo_04_compound_dry_run",
            "Default to dry-run inspection only",
            "uv run aug demo-run-compound-preview --days-back 90 --limit 5",
            "Do not write ad hoc Python",
        ],
        "demo_05_airplane_safety_evidence.md": [
            "before-demo_05_airplane_safety_evidence",
            "uv run aug demo-run-airplane-safety",
            "snapshot the current airplane preference",
            "uv run aug demo-smoke --airplane on --require-cloud false",
            "Do not discover tool names",
            "--action status",
        ],
        "demo_06_brain_manifest_architecture.md": [
            "before-demo_06_brain_manifest_architecture",
            "uv run aug demo-run-brain-manifest",
            "read-only after preflight",
        ],
    }

    for file_name, markers in expected_markers.items():
        text = (DEMO_DIR / file_name).read_text(encoding="utf-8")
        for marker in markers:
            assert marker in text


def test_demo_three_keeps_audio_before_transcription() -> None:
    path = DEMO_DIR / "demo_03_offload_transcription_airplane.md"
    metadata, body = parse_frontmatter(path)

    assert metadata["demo_id"] == "demo_03_offload_transcription_airplane"
    assert "/keep ~/Downloads/Offload Demo.m4a" in body
    assert "Use the returned Augur-owned path" in body
    assert "Do not run transcription against Downloads" in body
    assert "consume_source=true" in body
    assert "Workflow Example 03 proof card" in body
    assert "Transcript preview:" in body
    assert "Search Browse for `Workflow Example 03 Offline Online Transcription Offload`" in body
    assert "Stop if the workflow example output does not show a proof card and readable transcript preview." in body


def test_non_audio_demos_do_not_reference_downloads_audio() -> None:
    for file_name in EXPECTED_DEMOS:
        if file_name == "demo_03_offload_transcription_airplane.md":
            continue
        text = (DEMO_DIR / file_name).read_text(encoding="utf-8")
        assert "~/Downloads/Offload Demo.m4a" not in text


def test_demo_six_explains_brain_manifest_architecture() -> None:
    path = DEMO_DIR / "demo_06_brain_manifest_architecture.md"
    metadata, body = parse_frontmatter(path)

    assert metadata["demo_id"] == "demo_06_brain_manifest_architecture"
    assert "project-brain/BRAIN.yaml" in body
    assert "attached_project" in body
    assert "capabilities/skills" in body
    assert "knowledge" in body
    assert "instructions" in body
    assert "decisions/adrs" in body
    assert "personal brain" in body.lower()
    assert "project brain" in body.lower()


def test_demo_four_uses_bounded_compound_preview_command() -> None:
    path = DEMO_DIR / "demo_04_compound_dry_run.md"
    metadata, body = parse_frontmatter(path)

    assert metadata["demo_id"] == "demo_04_compound_dry_run"
    assert "## Bounded Live Command" in body
    assert "uv run aug demo-run-compound-preview --days-back 90 --limit 5" in body
    assert "Do not write ad hoc Python" in body
    assert "wiki-apply-concept-batch" in body


def test_demo_five_uses_bounded_airplane_safety_command() -> None:
    path = DEMO_DIR / "demo_05_airplane_safety_evidence.md"
    metadata, body = parse_frontmatter(path)

    assert metadata["demo_id"] == "demo_05_airplane_safety_evidence"
    assert "## Bounded Live Command" in body
    assert "uv run aug demo-run-airplane-safety" in body
    assert "uv run aug toggle-airplane-mode --action status" in body
    assert "uv run aug demo-smoke --airplane on --require-cloud false" in body
    assert "Do not discover tool names" in body
    assert "--action query" in body
