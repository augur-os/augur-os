from __future__ import annotations

import os
import json
from pathlib import Path
from types import SimpleNamespace


def _write_artifact(path: Path, text: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return str(path)


def _fake_result(
    tmp_path: Path,
    source_name: str,
    *,
    content_type: str = "document",
    status: str = "success",
    cloud_used: bool = False,
) -> SimpleNamespace:
    stem = Path(source_name).stem
    body = (
        "Augur investor demo meeting. Decision, use airplane mode first. "
        "Action, prepare the fixture pack. Follow up, verify cloud escalation evidence."
        if content_type == "audio"
        else "Northwind Labs invoice total 1842.25 due 2026-05-20."
    )
    extracted = (
        _write_artifact(tmp_path / "vault" / "sources" / "extracted" / f"{stem}.md", body)
        if status == "success"
        else None
    )
    card = (
        _write_artifact(
            tmp_path / "vault" / "sources" / "files" / f"{stem}.md",
            f"## Meeting Memory\n\n{body}\n\n### Action Items\n\n- [ ] prepare the fixture pack.\n\n## Processing Evidence\n",
        )
        if status == "success"
        else ""
    )
    return SimpleNamespace(
        source_path=f"C:/Desktop/{source_name}",
        final_path=f"C:/Vault/{source_name}" if status == "success" else "",
        source_card_path=card,
        extracted_path=extracted,
        content_type=content_type,
        status=status,
        rag_indexed=status == "success",
        cloud_used=cloud_used,
        cloud_provider="FakeVisionClient" if cloud_used else None,
        cloud_model="vision-demo" if cloud_used else None,
        escalation_reason=(
            "local OCR and local vision did not produce usable text"
            if cloud_used
            else None
        ),
        hardware_backend="cloud-vision" if cloud_used else "local",
    )


def _fake_demo_record(
    tmp_path: Path,
    *,
    airplane: bool,
    cloud: bool,
) -> SimpleNamespace:
    hard_photo_status = "needs_review" if airplane and not cloud else "success"
    hard_photo = _fake_result(
        tmp_path,
        "demo-hard-photo.png",
        content_type="image",
        status=hard_photo_status,
        cloud_used=cloud,
    )
    results = [
        hard_photo,
        _fake_result(tmp_path, "demo-invoice.txt"),
        _fake_result(tmp_path, "demo-medical-note.txt"),
        _fake_result(tmp_path, "demo-meeting.mp3", content_type="audio"),
    ]
    return SimpleNamespace(
        id="run_demo",
        status="partial_success" if hard_photo_status == "needs_review" else "success",
        cloud_calls=1 if cloud else 0,
        files_indexed=sum(1 for item in results if item.rag_indexed),
        files_needing_review=sum(1 for item in results if item.status == "needs_review"),
        file_results=results,
    )


def test_prepare_demo_state_creates_seeded_desktop_and_folder(tmp_path: Path, monkeypatch) -> None:
    from skills.demo.scripts import demo_ready
    from src.lib.ingest.inbox_store import InboxStore

    monkeypatch.setattr(demo_ready, "_write_demo_mp3", lambda path: path.write_bytes(b"ID3 fake demo mp3"))

    desktop = tmp_path / "Desktop" / "Augur Demo Inbox"
    store_root = tmp_path / "state"
    vault = tmp_path / "vault"
    preferences = tmp_path / "preferences.yaml"

    state = demo_ready.prepare_demo_state(
        desktop=desktop,
        store_root=store_root,
        vault_dir=vault,
        preferences_path=preferences,
        airplane_mode=True,
    )

    assert state["success"] is True
    assert state["desktop"] == str(desktop)
    assert sorted(Path(item).name for item in state["files"]) == [
        "demo-hard-photo.png",
        "demo-invoice.txt",
        "demo-medical-note.txt",
        "demo-meeting.mp3",
    ]
    assert (desktop / "demo-invoice.txt").read_text(encoding="utf-8").strip()
    assert (desktop / "demo-medical-note.txt").read_text(encoding="utf-8").strip()
    assert (desktop / "demo-hard-photo.png").read_bytes().startswith(b"\x89PNG")
    assert (desktop / "demo-hard-photo.png").stat().st_size > 10_000
    assert (desktop / "demo-meeting.mp3").read_bytes().startswith(b"ID3")
    assert "enabled: true" in preferences.read_text(encoding="utf-8")

    folders = InboxStore(store_root).list_folders()
    assert len(folders) == 1
    assert folders[0].id == "demo-desktop"
    assert folders[0].name == "Demo Desktop"
    assert folders[0].path == str(desktop.resolve(strict=False))


def test_prepare_demo_state_can_disable_airplane_mode(tmp_path: Path, monkeypatch) -> None:
    from skills.demo.scripts import demo_ready

    monkeypatch.setattr(demo_ready, "_write_demo_mp3", lambda path: path.write_bytes(b"ID3 fake demo mp3"))
    preferences = tmp_path / "preferences.yaml"

    state = demo_ready.prepare_demo_state(
        desktop=tmp_path / "Desktop",
        store_root=tmp_path / "state",
        vault_dir=tmp_path / "vault",
        preferences_path=preferences,
        airplane_mode=False,
    )

    assert state["success"] is True
    assert "enabled: false" in preferences.read_text(encoding="utf-8")


def test_write_demo_mp3_prefers_generated_speech(monkeypatch, tmp_path: Path) -> None:
    from skills.demo.scripts import demo_ready

    calls: list[str] = []

    def fake_synthesize(path, text):
        calls.append(f"synth:{path.name}:{'investor demo' in text}")
        path.write_bytes(b"RIFF demo wav")
        return True

    def fake_convert(wav_path, mp3_path):
        calls.append(f"convert:{wav_path.name}:{mp3_path.name}")
        mp3_path.write_bytes(b"ID3 generated speech")
        return True

    monkeypatch.setattr(demo_ready, "_synthesize_demo_wav", fake_synthesize)
    monkeypatch.setattr(demo_ready, "_convert_wav_to_mp3", fake_convert)

    target = tmp_path / "demo-meeting.mp3"
    demo_ready._write_demo_mp3(target)

    assert target.read_bytes() == b"ID3 generated speech"
    assert calls == [
        "synth:demo-meeting.wav:True",
        "convert:demo-meeting.wav:demo-meeting.mp3",
    ]


def test_write_demo_mp3_fails_when_speech_generation_fails(
    monkeypatch,
    tmp_path: Path,
) -> None:
    import pytest

    from skills.demo.scripts import demo_ready

    monkeypatch.setattr(demo_ready, "_synthesize_demo_wav", lambda *_args: False)

    with pytest.raises(RuntimeError, match="Could not generate demo meeting MP3"):
        demo_ready._write_demo_mp3(tmp_path / "demo-meeting.mp3")


def test_write_demo_photo_scan_creates_visible_document(tmp_path: Path) -> None:
    from PIL import Image

    from skills.demo.scripts import demo_ready

    image_path = tmp_path / "demo-hard-photo.png"
    demo_ready._write_demo_photo_scan(image_path)

    image = Image.open(image_path)
    assert image.size[0] >= 900
    assert image.size[1] >= 600
    assert len(image.getcolors(maxcolors=1_000_000) or []) > 20


def test_prepare_demo_state_clears_stale_files_in_named_demo_folder(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from skills.demo.scripts import demo_ready

    monkeypatch.setattr(demo_ready, "_write_demo_mp3", lambda path: path.write_bytes(b"ID3 fake demo mp3"))
    desktop = tmp_path / "Desktop" / "Augur Demo Inbox"
    desktop.mkdir(parents=True)
    (desktop / "stale-demo-file.txt").write_text("old", encoding="utf-8")

    demo_ready.prepare_demo_state(
        desktop=desktop,
        store_root=tmp_path / "state",
        vault_dir=tmp_path / "vault",
        preferences_path=tmp_path / "preferences.yaml",
        airplane_mode=True,
    )

    assert not (desktop / "stale-demo-file.txt").exists()


def test_readiness_uses_fresh_capability_probe_and_reports_missing_passive_agent(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from skills.demo.scripts import demo_ready

    calls: list[dict[str, object]] = []

    def fake_detect(*, use_cache: bool, probe_timeout_s: int) -> dict[str, object]:
        calls.append({"use_cache": use_cache, "probe_timeout_s": probe_timeout_s})
        return {
            "packages": {"markitdown": {"installed": True}},
            "commands": {"ffmpeg": "ffmpeg.exe", "ollama": "ollama.exe"},
            "transcription_ready": True,
            "local_agent_ready": True,
            "ollama": {"glm_ocr_available": True, "models": ["glm-ocr:latest"]},
            "policy": {
                "airplane_mode_enabled": False,
                "cloud_escalation_allowed": True,
            },
        }

    monkeypatch.setattr(demo_ready, "detect_extraction_capabilities", fake_detect)
    monkeypatch.setattr(
        demo_ready,
        "get_passive_agent_status",
        lambda: {"available": False, "error": "CLI 'claude' not found"},
    )

    result = demo_ready.check_demo_readiness(desktop=tmp_path, require_cloud=True)

    assert result["ready"] is False
    assert "passive cloud agent is not available: CLI 'claude' not found" in result["failures"]
    assert calls == [{"use_cache": False, "probe_timeout_s": 5}]


def test_readiness_fails_when_local_demo_requirements_are_missing(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from skills.demo.scripts import demo_ready

    monkeypatch.setattr(
        demo_ready,
        "detect_extraction_capabilities",
        lambda *, use_cache, probe_timeout_s: {
            "packages": {"markitdown": {"installed": False}},
            "commands": {},
            "transcription_ready": False,
            "local_agent_ready": False,
            "ollama": {"glm_ocr_available": False, "models": []},
            "policy": {
                "airplane_mode_enabled": True,
                "cloud_escalation_allowed": False,
            },
        },
    )

    result = demo_ready.check_demo_readiness(desktop=tmp_path, require_cloud=False)

    assert result["ready"] is False
    assert "markitdown is not installed" in result["failures"]
    assert "local transcription is not ready" in result["failures"]
    assert "local vision or local agent backend is not ready" in result["failures"]


def test_readiness_requires_passive_agent_even_when_airplane_enabled(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from skills.demo.scripts import demo_ready

    monkeypatch.setattr(
        demo_ready,
        "detect_extraction_capabilities",
        lambda *, use_cache, probe_timeout_s: {
            "packages": {"markitdown": {"installed": True}},
            "commands": {"ffmpeg": "ffmpeg.exe", "ollama": "ollama.exe"},
            "transcription_ready": True,
            "local_agent_ready": True,
            "ollama": {"glm_ocr_available": True, "models": ["glm-ocr:latest"]},
            "policy": {
                "airplane_mode_enabled": True,
                "cloud_escalation_allowed": False,
            },
        },
    )
    monkeypatch.setattr(
        demo_ready,
        "get_passive_agent_status",
        lambda: {"available": False, "error": "CLI 'claude' not found"},
    )

    result = demo_ready.check_demo_readiness(desktop=tmp_path, require_cloud=True)

    assert result["ready"] is False
    assert "passive cloud agent is not available: CLI 'claude' not found" in result["failures"]
    assert "airplane mode must be off for cloud demo" in result["failures"]


def test_readiness_accepts_passive_agent_without_provider_api_key(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from skills.demo.scripts import demo_ready

    monkeypatch.setattr(
        demo_ready,
        "detect_extraction_capabilities",
        lambda *, use_cache, probe_timeout_s: {
            "packages": {"markitdown": {"installed": True}},
            "commands": {"ffmpeg": "ffmpeg.exe", "ollama": "ollama.exe"},
            "transcription_ready": True,
            "local_agent_ready": True,
            "ollama": {"glm_ocr_available": True, "models": ["glm-ocr:latest"]},
            "policy": {
                "airplane_mode_enabled": False,
                "cloud_escalation_allowed": True,
            },
        },
    )
    monkeypatch.setattr(
        demo_ready,
        "get_passive_agent_status",
        lambda: {"available": True, "cli": "claude", "mode": "oneshot"},
    )

    result = demo_ready.check_demo_readiness(desktop=tmp_path, require_cloud=True)

    assert result["ready"] is True
    assert result["failures"] == []


def test_demo_smoke_requires_no_cloud_calls_when_airplane_on(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from skills.demo.scripts import demo_ready

    monkeypatch.setattr(
        demo_ready,
        "prepare_demo_state",
        lambda **kwargs: {"success": True, "files": [], "desktop": str(kwargs["desktop"])},
    )
    monkeypatch.setattr(
        demo_ready,
        "check_demo_readiness",
        lambda **kwargs: {"ready": True, "failures": []},
    )

    record = _fake_demo_record(tmp_path, airplane=True, cloud=False)

    monkeypatch.setattr(demo_ready, "consume_folder", lambda **kwargs: record)
    monkeypatch.setattr(
        demo_ready,
        "verify_demo_rag",
        lambda query, expected_files=None: {
            "query": query,
            "hit_count": 1,
            "hits": [{"file": str(expected_files[0]), "content": query}],
            "ready": True,
        },
    )
    monkeypatch.setattr(
        demo_ready,
        "_pin_demo_evidence_card",
        lambda source_card_path: {"added": True},
    )

    result = demo_ready.run_demo_smoke(
        desktop=tmp_path / "Desktop",
        airplane="on",
        require_cloud=False,
    )

    assert result["success"] is True
    assert result["cloud_calls"] == 0
    assert result["artifact_verification"]["ready"] is True


def test_demo_smoke_pins_latest_meeting_evidence_card(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from skills.demo.scripts import demo_ready

    pinned: list[Path] = []
    monkeypatch.setattr(
        demo_ready,
        "prepare_demo_state",
        lambda **kwargs: {"success": True, "files": [], "desktop": str(kwargs["desktop"])},
    )
    monkeypatch.setattr(
        demo_ready,
        "check_demo_readiness",
        lambda **kwargs: {"ready": True, "failures": []},
    )
    monkeypatch.setattr(
        demo_ready,
        "consume_folder",
        lambda **kwargs: _fake_demo_record(tmp_path, airplane=True, cloud=False),
    )
    monkeypatch.setattr(
        demo_ready,
        "verify_demo_rag",
        lambda query, expected_files=None: {
            "query": query,
            "hit_count": 1,
            "hits": [{"file": str(expected_files[0]), "content": query}],
            "ready": True,
        },
    )
    monkeypatch.setattr(
        demo_ready,
        "_pin_demo_evidence_card",
        lambda source_card_path: pinned.append(source_card_path) or {"added": True},
    )

    result = demo_ready.run_demo_smoke(
        desktop=tmp_path / "Desktop",
        airplane="on",
        require_cloud=False,
    )

    assert result["success"] is True
    assert result["evidence_pin"]["added"] is True
    assert pinned == [tmp_path / "vault" / "sources" / "files" / "demo-meeting.md"]


def test_demo_smoke_allows_local_escalation_reason_without_cloud_in_airplane(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from skills.demo.scripts import demo_ready

    monkeypatch.setattr(
        demo_ready,
        "prepare_demo_state",
        lambda **kwargs: {"success": True, "files": [], "desktop": str(kwargs["desktop"])},
    )
    monkeypatch.setattr(
        demo_ready,
        "check_demo_readiness",
        lambda **kwargs: {"ready": True, "failures": []},
    )

    record = _fake_demo_record(tmp_path, airplane=True, cloud=False)
    hard_photo = next(item for item in record.file_results if item.source_path.endswith("demo-hard-photo.png"))
    hard_photo.escalation_reason = "ocr failed"

    monkeypatch.setattr(demo_ready, "consume_folder", lambda **kwargs: record)
    monkeypatch.setattr(
        demo_ready,
        "verify_demo_rag",
        lambda query, expected_files=None: {
            "query": query,
            "hit_count": 1,
            "hits": [{"file": str(expected_files[0]), "content": query}],
            "ready": True,
        },
    )
    monkeypatch.setattr(
        demo_ready,
        "_pin_demo_evidence_card",
        lambda source_card_path: {"added": True},
    )

    result = demo_ready.run_demo_smoke(
        desktop=tmp_path / "Desktop",
        airplane="on",
        require_cloud=False,
    )

    assert result["success"] is True
    assert "airplane mode result contains cloud evidence" not in result["failure_reason"]


def test_demo_smoke_waits_for_seed_files_before_consuming(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from skills.demo.scripts import demo_ready

    seeded_files = [str(tmp_path / "Desktop" / "demo-meeting.mp3")]
    calls: list[list[str]] = []
    monkeypatch.setattr(
        demo_ready,
        "prepare_demo_state",
        lambda **kwargs: {
            "success": True,
            "files": seeded_files,
            "desktop": str(kwargs["desktop"]),
        },
    )
    monkeypatch.setattr(
        demo_ready,
        "check_demo_readiness",
        lambda **kwargs: {"ready": True, "failures": []},
    )
    monkeypatch.setattr(
        demo_ready,
        "_wait_for_demo_files_stable",
        lambda paths: calls.append([str(path) for path in paths]),
        raising=False,
    )
    monkeypatch.setattr(
        demo_ready,
        "consume_folder",
        lambda **kwargs: _fake_demo_record(tmp_path, airplane=True, cloud=False),
    )
    monkeypatch.setattr(
        demo_ready,
        "verify_demo_rag",
        lambda query, expected_files=None: {
            "query": query,
            "hit_count": 1,
            "hits": [{"file": str(expected_files[0]), "content": query}],
            "ready": True,
        },
    )

    demo_ready.run_demo_smoke(
        desktop=tmp_path / "Desktop",
        airplane="on",
        require_cloud=False,
    )

    assert calls == [seeded_files]


def test_demo_smoke_restores_existing_airplane_preference(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from skills.demo.scripts import demo_ready
    from src.config.preferences import load_preferences, save_preferences

    preferences = tmp_path / "preferences.yaml"
    original = {
        "airplane_mode": {
            "enabled": False,
            "forced": False,
            "auto_detect": True,
            "fallback_tools": ["web-search"],
        },
        "local_backends": {"ollama": {"model": "qwen3.5:latest"}},
    }
    save_preferences(original, path=preferences)

    monkeypatch.setattr(demo_ready, "get_preferences_path", lambda: preferences)
    monkeypatch.setattr(demo_ready, "get_vault_dir", lambda: tmp_path / "vault")
    monkeypatch.setattr(
        demo_ready,
        "_write_demo_mp3",
        lambda path: path.write_bytes(b"ID3 fake demo mp3"),
    )
    monkeypatch.setattr(
        demo_ready,
        "check_demo_readiness",
        lambda **kwargs: {"ready": True, "failures": []},
    )
    monkeypatch.setattr(demo_ready, "_wait_for_demo_files_stable", lambda paths: None)
    monkeypatch.setattr(
        demo_ready,
        "consume_folder",
        lambda **kwargs: _fake_demo_record(tmp_path, airplane=True, cloud=False),
    )
    monkeypatch.setattr(
        demo_ready,
        "verify_demo_rag",
        lambda query, expected_files=None: {
            "query": query,
            "hit_count": 1,
            "hits": [{"file": str(expected_files[0]), "content": query}],
            "ready": True,
        },
    )
    monkeypatch.setattr(
        demo_ready,
        "_pin_demo_evidence_card",
        lambda source_card_path: {"added": True},
    )

    result = demo_ready.run_demo_smoke(
        desktop=tmp_path / "Desktop",
        airplane="on",
        require_cloud=False,
    )

    assert result["success"] is True
    assert result["reset"]["airplane_mode"] is True
    assert load_preferences(path=preferences, migrate_legacy=False) == original


def test_wait_for_demo_files_stable_matches_scanner_age_rule(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from skills.demo.scripts import demo_ready

    target = tmp_path / "demo-meeting.mp3"
    target.write_bytes(b"ID3 demo audio")
    os.utime(target, (101.0, 101.0))

    clock = {"monotonic": 0.0, "wall": 101.0}

    def fake_sleep(seconds: float) -> None:
        clock["monotonic"] += seconds
        clock["wall"] += seconds

    monkeypatch.setattr(demo_ready.time, "monotonic", lambda: clock["monotonic"])
    monkeypatch.setattr(demo_ready.time, "time", lambda: clock["wall"])
    monkeypatch.setattr(demo_ready.time, "sleep", fake_sleep)

    demo_ready._wait_for_demo_files_stable([target])

    assert clock["wall"] >= 103.0


def test_demo_smoke_requires_cloud_run_when_airplane_off(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from skills.demo.scripts import demo_ready

    calls: list[str] = []
    monkeypatch.setattr(
        demo_ready,
        "prepare_demo_state",
        lambda **kwargs: {"success": True, "files": [], "desktop": str(kwargs["desktop"])},
    )
    monkeypatch.setattr(
        demo_ready,
        "check_demo_readiness",
        lambda **kwargs: {"ready": True, "failures": []},
    )

    record = _fake_demo_record(tmp_path, airplane=False, cloud=True)

    monkeypatch.setattr(
        demo_ready,
        "consume_folder",
        lambda **kwargs: calls.append(kwargs["folder_id"]) or record,
    )
    monkeypatch.setattr(
        demo_ready,
        "verify_demo_rag",
        lambda query, expected_files=None: {
            "query": query,
            "hit_count": 1,
            "hits": [{"file": str(expected_files[0]), "content": query}],
            "ready": True,
        },
    )
    monkeypatch.setattr(
        demo_ready,
        "_pin_demo_evidence_card",
        lambda source_card_path: {"added": True},
    )

    result = demo_ready.run_demo_smoke(
        desktop=tmp_path / "Desktop",
        airplane="off",
        require_cloud=True,
    )

    assert result["success"] is True
    assert result["cloud_calls"] == 1
    assert result["files_indexed"] == 4
    assert calls == ["demo-desktop"]


def test_demo_smoke_fails_when_required_cloud_call_is_missing(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from skills.demo.scripts import demo_ready

    monkeypatch.setattr(
        demo_ready,
        "prepare_demo_state",
        lambda **kwargs: {"success": True, "files": [], "desktop": str(kwargs["desktop"])},
    )
    monkeypatch.setattr(
        demo_ready,
        "check_demo_readiness",
        lambda **kwargs: {"ready": True, "failures": []},
    )

    record = _fake_demo_record(tmp_path, airplane=False, cloud=False)

    monkeypatch.setattr(demo_ready, "consume_folder", lambda **kwargs: record)
    monkeypatch.setattr(
        demo_ready,
        "verify_demo_rag",
        lambda query, expected_files=None: {
            "query": query,
            "hit_count": 1,
            "hits": [{"file": str(expected_files[0]), "content": query}],
            "ready": True,
        },
    )

    result = demo_ready.run_demo_smoke(
        desktop=tmp_path / "Desktop",
        airplane="off",
        require_cloud=True,
    )

    assert result["success"] is False
    assert result["cloud_calls"] == 0


def test_demo_smoke_fails_without_meeting_artifacts(monkeypatch, tmp_path: Path) -> None:
    from skills.demo.scripts import demo_ready

    record = _fake_demo_record(tmp_path, airplane=False, cloud=True)
    record.file_results = [
        item for item in record.file_results if item.source_path.endswith("demo-meeting.mp3") is False
    ]

    monkeypatch.setattr(
        demo_ready,
        "prepare_demo_state",
        lambda **kwargs: {"success": True, "files": [], "desktop": str(kwargs["desktop"])},
    )
    monkeypatch.setattr(
        demo_ready,
        "check_demo_readiness",
        lambda **kwargs: {"ready": True, "failures": []},
    )
    monkeypatch.setattr(demo_ready, "consume_folder", lambda **kwargs: record)

    result = demo_ready.run_demo_smoke(
        desktop=tmp_path / "Desktop",
        airplane="off",
        require_cloud=True,
    )

    assert result["success"] is False
    assert "missing demo result: demo-meeting.mp3" in result["artifact_verification"]["failures"]


def test_main_prints_json(monkeypatch, tmp_path: Path, capsys) -> None:
    from skills.demo.scripts import demo_ready

    monkeypatch.setattr(
        demo_ready,
        "prepare_demo_state",
        lambda **kwargs: {"success": True, "desktop": str(kwargs["desktop"]), "files": []},
    )

    code = demo_ready.main(["reset", "--desktop", str(tmp_path / "Desktop")])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["success"] is True
