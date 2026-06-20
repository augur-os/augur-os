from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

import yaml

from src.config.paths import get_runtime_dir, get_vault_dir
from src.config.preferences import (
    get_preferences_path,
    load_preferences,
    save_preferences,
)
from src.lib.extraction import detect_extraction_capabilities
from src.lib.extraction.cloud_vision import get_passive_agent_status

from src.lib.ingest.inbox_consume import consume_folder
from src.lib.ingest.inbox_models import InboxFolder, to_dict
from src.lib.ingest.inbox_store import InboxStore
from src.lib.ingest.rag_demo_verify import verify_demo_rag

DEMO_FOLDER_ID = "demo-desktop"
DEMO_FOLDER_NAME = "Demo Desktop"
DEMO_FILE_NAMES = [
    "demo-invoice.txt",
    "demo-medical-note.txt",
    "demo-hard-photo.png",
    "demo-meeting.mp3",
]

DEMO_RAG_QUERY = "investor demo meeting"
_DEMO_MEETING_TEXT = (
    "Augur investor demo meeting. "
    "Reviewed investor demo readiness. "
    "Decision: use air plane mode first. "
    "Action: prepare the fixture pack. "
    "Follow-up: verify cloud escalation evidence."
)


def _default_desktop() -> Path:
    return Path.home() / "Desktop" / "Augur Demo Inbox"


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_demo_photo_scan(path: Path) -> None:
    try:
        from PIL import Image, ImageDraw, ImageFilter, ImageFont
    except Exception as exc:
        raise RuntimeError("Pillow is required to generate demo photo scan") from exc

    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (1100, 760), (218, 221, 214))
    draw = ImageDraw.Draw(image)

    for x in range(0, image.width, 18):
        shade = 218 + (x % 54)
        draw.line((x, 0, x, image.height), fill=(shade, shade, shade - 8), width=1)

    paper = Image.new("RGB", (880, 570), (245, 244, 234))
    paper_draw = ImageDraw.Draw(paper)
    font = ImageFont.load_default()
    paper_draw.rectangle((0, 0, 879, 569), outline=(140, 140, 132), width=3)
    paper_draw.text((54, 42), "NORTHWIND LABS PHOTO INVOICE", fill=(20, 24, 28), font=font)
    paper_draw.text((54, 92), "Invoice: AI-PC-1842", fill=(34, 34, 34), font=font)
    paper_draw.text((54, 132), "Total Due: $1,842.25", fill=(34, 34, 34), font=font)
    paper_draw.text((54, 172), "Due Date: 2026-05-20", fill=(34, 34, 34), font=font)
    paper_draw.text((54, 232), "Escalation Target: cloud vision recovers this scan", fill=(34, 34, 34), font=font)
    paper_draw.text((54, 272), "Action: approve payment before investor demo", fill=(34, 34, 34), font=font)
    for y in range(325, 500, 28):
        paper_draw.line((54, y, 790, y), fill=(180, 180, 172), width=2)

    paper = paper.rotate(-2.5, expand=True, fillcolor=(218, 221, 214))
    image.paste(paper, (96, 84))
    image = image.filter(ImageFilter.GaussianBlur(radius=0.45))
    image.save(path, format="PNG")


def _synthesize_demo_wav(path: Path, text: str) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    system = platform.system()
    if system == "Darwin":
        say = shutil.which("say")
        if not say:
            return False
        aiff_path = path.with_suffix(".aiff")
        try:
            result = subprocess.run(
                [say, "-o", str(aiff_path), text],
                capture_output=True,
                check=False,
                stdin=subprocess.DEVNULL,
                text=True,
                timeout=30,
            )
            if result.returncode != 0 or not aiff_path.exists() or aiff_path.stat().st_size == 0:
                return False
            ffmpeg = _ffmpeg_executable()
            if ffmpeg:
                convert = subprocess.run(
                    [
                        ffmpeg,
                        "-y",
                        "-loglevel",
                        "error",
                        "-i",
                        str(aiff_path),
                        str(path),
                    ],
                    capture_output=True,
                    check=False,
                    stdin=subprocess.DEVNULL,
                    text=True,
                    timeout=30,
                )
            else:
                afconvert = shutil.which("afconvert")
                if not afconvert:
                    return False
                convert = subprocess.run(
                    [afconvert, "-f", "WAVE", "-d", "LEI16", str(aiff_path), str(path)],
                    capture_output=True,
                    check=False,
                    stdin=subprocess.DEVNULL,
                    text=True,
                    timeout=30,
                )
        except (OSError, subprocess.TimeoutExpired):
            return False
        finally:
            if aiff_path.exists():
                aiff_path.unlink()
        return convert.returncode == 0 and path.exists() and path.stat().st_size > 0

    if system != "Windows":
        return False
    env = os.environ.copy()
    env["AUGUR_DEMO_TTS_PATH"] = str(path)
    env["AUGUR_DEMO_TTS_TEXT"] = text
    script = (
        "$ErrorActionPreference='Stop';"
        "Add-Type -AssemblyName System.Speech;"
        "$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer;"
        "$synth.SetOutputToWaveFile($env:AUGUR_DEMO_TTS_PATH);"
        "$synth.Speak($env:AUGUR_DEMO_TTS_TEXT);"
        "$synth.Dispose();"
    )
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            check=False,
            env=env,
            stdin=subprocess.DEVNULL,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0 and path.exists() and path.stat().st_size > 0


def _ffmpeg_executable() -> str | None:
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return shutil.which("ffmpeg")


def _convert_wav_to_mp3(wav_path: Path, mp3_path: Path) -> bool:
    ffmpeg = _ffmpeg_executable()
    if not ffmpeg:
        return False
    try:
        result = subprocess.run(
            [
                ffmpeg,
                "-y",
                "-loglevel",
                "error",
                "-i",
                str(wav_path),
                str(mp3_path),
            ],
            capture_output=True,
            check=False,
            stdin=subprocess.DEVNULL,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0 and mp3_path.exists() and mp3_path.stat().st_size > 0


def _write_demo_mp3(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    wav_path = path.with_suffix(".wav")
    try:
        if _synthesize_demo_wav(wav_path, _DEMO_MEETING_TEXT) and _convert_wav_to_mp3(
            wav_path,
            path,
        ):
            return
    finally:
        if wav_path.exists():
            wav_path.unlink()

    raise RuntimeError("Could not generate demo meeting MP3 with local speech synthesis")


def _reset_demo_files(desktop: Path) -> None:
    desktop.mkdir(parents=True, exist_ok=True)
    if desktop.name == "Augur Demo Inbox":
        targets = list(desktop.iterdir())
    else:
        targets = [desktop / name for name in DEMO_FILE_NAMES]
    for target in targets:
        if not target.exists():
            continue
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()


def _write_preferences(path: Path, *, airplane_mode: bool) -> None:
    prefs = load_preferences(path=path, migrate_legacy=False)
    airplane_config = prefs.get("airplane_mode", {})
    if not isinstance(airplane_config, dict):
        airplane_config = {}
    airplane_config["enabled"] = airplane_mode
    prefs["airplane_mode"] = airplane_config
    save_preferences(prefs, path=path)


def _restore_preferences_snapshot(
    path: Path,
    snapshot: dict[str, Any],
    *,
    existed: bool,
) -> None:
    if existed:
        save_preferences(snapshot, path=path)
        return
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def _upsert_demo_folder(store: InboxStore, desktop: Path) -> InboxFolder:
    demo_path = str(desktop.resolve(strict=False))
    existing = [
        folder
        for folder in store.list_folders()
        if folder.id != DEMO_FOLDER_ID
        and folder.name != DEMO_FOLDER_NAME
        and folder.path != demo_path
    ]
    folder = InboxFolder(id=DEMO_FOLDER_ID, name=DEMO_FOLDER_NAME, path=demo_path)
    store._write_json(store.folders_path, [to_dict(item) for item in [folder, *existing]])
    return folder


_DEMO_FIXTURE_FILENAMES = frozenset(DEMO_FILE_NAMES)


def _purge_demo_vault_artifacts(vault_dir: Path) -> dict[str, int]:
    """Remove demo-generated artifacts from the real vault so a demo never leaves
    permanent pollution. A card is a demo fixture iff its ``original_path`` basename is
    one of the generated demo inputs (``DEMO_FILE_NAMES``) — robust across every demo
    desktop folder variant ("Augur Demo Inbox", "Augur Workflow Example Inbox", custom
    ``--desktop``) while never touching genuine user notes (which have other origins).
    Each demo source card links its routed copy (``final_path``) and extracted text
    (``extracted_path``); all three are removed. Called on ``reset`` to clean up after
    a visible demo run.
    """
    removed = {"cards": 0, "final": 0, "extracted": 0}
    notes_dir = vault_dir / "notes"
    if not notes_dir.is_dir():
        return removed
    for card in sorted(notes_dir.glob("*.md")):
        try:
            text = card.read_text(encoding="utf-8")
        except OSError:
            continue
        if not text.startswith("---"):
            continue
        try:
            meta = yaml.safe_load(text.split("---", 2)[1]) or {}
        except Exception:  # noqa: BLE001 - skip unparseable cards, never crash reset
            continue
        if Path(str(meta.get("original_path", ""))).name not in _DEMO_FIXTURE_FILENAMES:
            continue
        for key, bucket in (("final_path", "final"), ("extracted_path", "extracted")):
            raw = meta.get(key)
            if raw:
                linked = Path(str(raw))
                if linked.is_file():
                    linked.unlink()
                    removed[bucket] += 1
        card.unlink()
        removed["cards"] += 1
    return removed


def prepare_demo_state(
    *,
    desktop: Path,
    store_root: Path,
    vault_dir: Path,
    preferences_path: Path,
    airplane_mode: bool,
) -> dict[str, Any]:
    _reset_demo_files(desktop)
    purged_demo_artifacts = _purge_demo_vault_artifacts(vault_dir)
    vault_dir.mkdir(parents=True, exist_ok=True)
    _write_preferences(preferences_path, airplane_mode=airplane_mode)

    invoice = desktop / "demo-invoice.txt"
    medical = desktop / "demo-medical-note.txt"
    hard_photo = desktop / "demo-hard-photo.png"
    meeting = desktop / "demo-meeting.mp3"

    _write_text(
        invoice,
        "\n".join(
            [
                "Invoice",
                "Vendor: Northwind Labs",
                "Amount: 1842.25",
                "Due: 2026-05-20",
                "Action: approve payment before the investor demo.",
                "",
            ]
        ),
    )
    _write_text(
        medical,
        "\n".join(
            [
                "Clinic visit note",
                "Provider: City Health Clinic",
                "Patient should upload the insurance form and schedule a follow-up.",
                "Sensitive content: keep local during airplane mode.",
                "",
            ]
        ),
    )
    _write_demo_photo_scan(hard_photo)
    _write_demo_mp3(meeting)

    store = InboxStore(store_root)
    folder = _upsert_demo_folder(store, desktop)

    return {
        "success": True,
        "desktop": str(desktop),
        "folder_id": folder.id,
        "store_root": str(store_root),
        "vault_dir": str(vault_dir),
        "airplane_mode": airplane_mode,
        "files": [str(invoice), str(medical), str(hard_photo), str(meeting)],
        "purged_demo_artifacts": purged_demo_artifacts,
    }


def check_demo_readiness(*, desktop: Path, require_cloud: bool) -> dict[str, Any]:
    inventory = detect_extraction_capabilities(use_cache=False, probe_timeout_s=5)
    failures: list[str] = []

    if not desktop.exists():
        failures.append(f"desktop inbox does not exist: {desktop}")
    if not inventory.get("packages", {}).get("markitdown", {}).get("installed"):
        failures.append("markitdown is not installed")
    if not inventory.get("transcription_ready"):
        failures.append("local transcription is not ready")
    if not inventory.get("local_agent_ready"):
        failures.append("local vision or local agent backend is not ready")

    policy = inventory.get("policy", {})
    airplane_enabled = bool(
        policy.get("airplane_mode_enabled") if isinstance(policy, dict) else False
    )
    if require_cloud:
        agent_status = get_passive_agent_status()
        if not agent_status.get("available"):
            error = agent_status.get("error")
            failures.append(
                f"passive cloud agent is not available: {error}"
                if error
                else "passive cloud agent is not available"
            )
        if airplane_enabled:
            failures.append("airplane mode must be off for cloud demo")

    return {
        "ready": not failures,
        "failures": failures,
        "desktop": str(desktop),
        "require_cloud": require_cloud,
        "capabilities": inventory,
    }


def _demo_store_root() -> Path:
    return get_runtime_dir() / "brain" / "inbox"


def _demo_folder_id(store: InboxStore, desktop: Path) -> str:
    demo_path = str(desktop.resolve(strict=False))
    for folder in store.list_folders():
        if folder.id == DEMO_FOLDER_ID or folder.path == demo_path:
            return folder.id
    return DEMO_FOLDER_ID


def _file_name(value: str | None) -> str:
    return Path(value or "").name


def _read_existing_text(path_text: str | None) -> str:
    if not path_text:
        return ""
    path = Path(path_text)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def _path_exists(path_text: str | None) -> bool:
    return bool(path_text and Path(path_text).exists())


def _wait_for_demo_files_stable(paths: list[str | Path]) -> None:
    files = [Path(path) for path in paths]
    if not files:
        return

    stable_age_seconds = 2.0
    deadline = time.monotonic() + 10.0
    previous: tuple[tuple[str, int, int], ...] | None = None
    stable_checks = 0
    while time.monotonic() < deadline:
        signatures: list[tuple[str, int, int]] = []
        newest_mtime = 0.0
        all_ready = True
        for path in files:
            try:
                stat = path.stat()
            except FileNotFoundError:
                all_ready = False
                break
            signatures.append((str(path), stat.st_size, stat.st_mtime_ns))
            newest_mtime = max(newest_mtime, stat.st_mtime)

        current = tuple(signatures)
        old_enough = all_ready and (time.time() - newest_mtime) >= stable_age_seconds
        if old_enough and current == previous:
            stable_checks += 1
            if stable_checks >= 2:
                return
        else:
            stable_checks = 0
            previous = current if all_ready else None

        time.sleep(0.5)

    raise TimeoutError("demo seed files did not settle before ingest")


def _verify_demo_run_artifacts(
    record: Any,
    *,
    airplane_mode: bool,
    require_cloud: bool,
) -> dict[str, Any]:
    failures: list[str] = []
    file_results = list(getattr(record, "file_results", []) or [])
    by_source = {_file_name(getattr(result, "source_path", "")): result for result in file_results}

    for name in DEMO_FILE_NAMES:
        if name not in by_source:
            failures.append(f"missing demo result: {name}")

    for name in ("demo-invoice.txt", "demo-medical-note.txt", "demo-meeting.mp3"):
        result = by_source.get(name)
        if result is None:
            continue
        if getattr(result, "status", "") != "success":
            failures.append(f"{name} did not complete successfully")
        if not getattr(result, "rag_indexed", False):
            failures.append(f"{name} was not indexed")
        if not _path_exists(getattr(result, "extracted_path", None)):
            failures.append(f"{name} missing extracted artifact")
        if not _path_exists(getattr(result, "source_card_path", None)):
            failures.append(f"{name} missing source card")

    meeting = by_source.get("demo-meeting.mp3")
    meeting_paths: list[str] = []
    if meeting is not None:
        meeting_paths = [
            path
            for path in [
                getattr(meeting, "source_card_path", None),
                getattr(meeting, "extracted_path", None),
            ]
            if path
        ]
        transcript = _read_existing_text(getattr(meeting, "extracted_path", None)).lower()
        card = _read_existing_text(getattr(meeting, "source_card_path", None)).lower()
        if "investor demo" not in transcript or "airplane mode" not in transcript:
            failures.append("demo meeting transcript missing expected demo terms")
        if "## meeting memory" not in card or "action items" not in card:
            failures.append("demo meeting source card missing meeting memory")

    cloud_results = [result for result in file_results if getattr(result, "cloud_used", False)]
    cloud_calls = int(getattr(record, "cloud_calls", 0))
    if airplane_mode:
        if cloud_calls != 0 or cloud_results:
            failures.append("airplane mode smoke must not use cloud calls")
        for result in file_results:
            if any(
                getattr(result, field, None)
                for field in ("cloud_provider", "cloud_model")
            ):
                failures.append("airplane mode result contains cloud evidence")
                break
        if int(getattr(record, "files_indexed", 0)) < 3:
            failures.append("airplane mode must index at least the local text and meeting files")
        if int(getattr(record, "files_needing_review", 0)) > 1:
            failures.append("airplane mode should leave at most the hard photo for review")
    else:
        if getattr(record, "status", "") != "success":
            failures.append("cloud demo run did not finish with success status")
        if int(getattr(record, "files_indexed", 0)) != len(DEMO_FILE_NAMES):
            failures.append("cloud demo must index all seeded files")
        if int(getattr(record, "files_needing_review", 0)) != 0:
            failures.append("cloud demo must not leave files needing review")

    if require_cloud and not airplane_mode:
        if cloud_calls != 1 or len(cloud_results) != 1:
            failures.append("cloud smoke must use exactly one cloud file call")
        cloud_result = cloud_results[0] if cloud_results else None
        if cloud_result is not None:
            if _file_name(getattr(cloud_result, "source_path", "")) != "demo-hard-photo.png":
                failures.append("cloud escalation must be for demo-hard-photo.png")
            if not getattr(cloud_result, "cloud_provider", None):
                failures.append("cloud result missing provider")
            if not getattr(cloud_result, "cloud_model", None):
                failures.append("cloud result missing model")
            if not getattr(cloud_result, "escalation_reason", None):
                failures.append("cloud result missing escalation reason")
            cloud_text = _read_existing_text(getattr(cloud_result, "extracted_path", None)).lower()
            if not any(term in cloud_text for term in ("northwind", "1842", "2026-05-20")):
                failures.append("cloud extracted artifact missing hard-photo fixture facts")

    rag = (
        verify_demo_rag(DEMO_RAG_QUERY, expected_files=meeting_paths)
        if meeting_paths
        else {"query": DEMO_RAG_QUERY, "hit_count": 0, "hits": [], "ready": False}
    )
    if not rag.get("ready"):
        failures.append("demo meeting RAG proof did not find current run artifacts")

    return {
        "ready": not failures,
        "failures": failures,
        "rag": rag,
        "checked_files": sorted(by_source),
    }


def _demo_meeting_source_card(record: Any) -> Path | None:
    for result in list(getattr(record, "file_results", []) or []):
        if _file_name(getattr(result, "source_path", "")) != "demo-meeting.mp3":
            continue
        source_card_path = getattr(result, "source_card_path", None)
        if source_card_path:
            return Path(source_card_path)
    return None


def _pin_demo_evidence_card(source_card_path: Path | None) -> dict[str, Any]:
    if source_card_path is None:
        return {"added": False, "error": "No demo meeting source card was produced."}
    try:
        from src.lib.brain_layout import vault_machine_dir
        from src.mcp.augur_framework.tools.infrastructure.pins import pin_card_impl

        return pin_card_impl(
            pins_path=vault_machine_dir(get_vault_dir(), "system") / "pins.yaml",
            category="vault",
            selector=str(source_card_path),
            hub="brain",
        )
    except Exception as exc:  # noqa: BLE001 - expose pin failure in smoke output
        return {"added": False, "error": str(exc), "selector": str(source_card_path)}


def run_demo_smoke(
    *,
    desktop: Path,
    airplane: str,
    require_cloud: bool,
) -> dict[str, Any]:
    airplane_mode = airplane == "on"
    store_root = _demo_store_root()
    preferences_path = get_preferences_path()
    preferences_existed = preferences_path.exists()
    preferences_snapshot = load_preferences(
        path=preferences_path,
        migrate_legacy=False,
    )
    try:
        reset = prepare_demo_state(
            desktop=desktop,
            store_root=store_root,
            vault_dir=get_vault_dir(),
            preferences_path=preferences_path,
            airplane_mode=airplane_mode,
        )
        if not reset.get("success"):
            return {"success": False, "stage": "reset", "reset": reset}

        readiness = check_demo_readiness(desktop=desktop, require_cloud=require_cloud)
        if not readiness["ready"]:
            return {"success": False, "stage": "readiness", "reset": reset, **readiness}

        try:
            _wait_for_demo_files_stable(list(reset.get("files", []) or []))
        except TimeoutError as exc:
            return {
                "success": False,
                "stage": "stability",
                "reset": reset,
                "readiness": readiness,
                "failure_reason": str(exc),
            }

        store = InboxStore(store_root)
        folder_id = _demo_folder_id(store, desktop)
        record = consume_folder(store=store, folder_id=folder_id)
        cloud_calls = int(getattr(record, "cloud_calls", 0))
        files_indexed = int(getattr(record, "files_indexed", 0))
        files_needing_review = int(getattr(record, "files_needing_review", 0))

        artifact_verification = _verify_demo_run_artifacts(
            record,
            airplane_mode=airplane_mode,
            require_cloud=require_cloud,
        )
        evidence_pin = _pin_demo_evidence_card(_demo_meeting_source_card(record))
        if evidence_pin.get("error"):
            artifact_verification["failures"].append(str(evidence_pin["error"]))
            artifact_verification["ready"] = False
        success = bool(artifact_verification["ready"])
        failure_reason = "; ".join(artifact_verification["failures"])

        return {
            "success": success,
            "stage": "consume",
            "reset": reset,
            "readiness": readiness,
            "run_id": getattr(record, "id", ""),
            "status": getattr(record, "status", ""),
            "airplane": airplane,
            "require_cloud": require_cloud,
            "cloud_calls": cloud_calls,
            "files_indexed": files_indexed,
            "files_needing_review": files_needing_review,
            "failure_reason": failure_reason,
            "artifact_verification": artifact_verification,
            "evidence_pin": evidence_pin,
        }
    finally:
        _restore_preferences_snapshot(
            preferences_path,
            preferences_snapshot,
            existed=preferences_existed,
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare or verify the AI PC demo.")
    sub = parser.add_subparsers(dest="command", required=True)

    reset = sub.add_parser("reset", help="Reset the demo desktop inbox.")
    reset.add_argument("--desktop", type=Path, default=_default_desktop())
    reset.add_argument("--airplane", choices=["on", "off"], default="on")

    ready = sub.add_parser("ready", help="Check demo readiness.")
    ready.add_argument("--desktop", type=Path, default=_default_desktop())
    ready.add_argument("--require-cloud", action="store_true")

    smoke = sub.add_parser("smoke", help="Run reset, readiness, and consume smoke.")
    smoke.add_argument("--desktop", type=Path, default=_default_desktop())
    smoke.add_argument("--airplane", choices=["on", "off"], default="on")
    smoke.add_argument("--require-cloud", action="store_true")

    args = parser.parse_args(argv)
    if args.command == "reset":
        payload = prepare_demo_state(
            desktop=args.desktop,
            store_root=_demo_store_root(),
            vault_dir=get_vault_dir(),
            preferences_path=get_preferences_path(),
            airplane_mode=args.airplane == "on",
        )
    elif args.command == "ready":
        payload = check_demo_readiness(
            desktop=args.desktop,
            require_cloud=bool(args.require_cloud),
        )
    else:
        payload = run_demo_smoke(
            desktop=args.desktop,
            airplane=args.airplane,
            require_cloud=bool(args.require_cloud),
        )

    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if payload.get("success", payload.get("ready", False)) else 1


if __name__ == "__main__":
    raise SystemExit(main())
