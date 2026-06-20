from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.config.paths import get_project_root, get_runtime_dir
from src.lib.agent_cli_config import (
    AgentCliConfig as PassiveAgentConfig,
    build_agent_command,
    resolve_agent_cli_config,
    resolve_cli_path,
)

PASSIVE_OCR_ACTION_ID = "document-ocr-cloud"


@dataclass(frozen=True)
class CloudVisionResult:
    success: bool
    results: dict[str, str]
    provider: str
    model: str | None
    error: str | None = None


def _resolve_passive_agent_config() -> PassiveAgentConfig:
    return resolve_agent_cli_config(
        PASSIVE_OCR_ACTION_ID,
        command_fields=("passive_cmd", "print_cmd"),
    )


def _preferred_agent_cli() -> str:
    return _resolve_passive_agent_config().cli_id


def _resolve_cli_path(cli_name: str) -> str | None:
    return resolve_cli_path(cli_name)


def get_passive_agent_status() -> dict[str, Any]:
    agent = _resolve_passive_agent_config()
    cli = agent.command[0] if agent.command else agent.cli_id
    if agent.error:
        return {
            "available": False,
            "cli": agent.cli_id,
            "mode": "oneshot",
            "source": agent.source,
            "config_path": agent.config_path,
            "error": agent.error,
        }
    cli_path = _resolve_cli_path(cli)
    if not cli_path:
        return {
            "available": False,
            "cli": agent.cli_id,
            "mode": "oneshot",
            "source": agent.source,
            "config_path": agent.config_path,
            "error": f"CLI '{cli}' not found",
        }
    return {
        "available": True,
        "cli": agent.cli_id,
        "cli_path": cli_path,
        "mode": "oneshot",
        "source": agent.source,
        "config_path": agent.config_path,
    }


def _agent_command(
    cli_path: str,
    cli_name: str,
    prompt: str,
    job_dir: Path,
    *,
    configured_command: list[str] | None = None,
) -> list[str]:
    return build_agent_command(
        cli_path,
        cli_name,
        prompt,
        configured_command=configured_command,
        job_dir=job_dir,
    )


def _safe_request_id(value: Any, fallback: str) -> str:
    raw = str(value or fallback)
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", raw)[:80] or fallback


def _extract_json_object(text: str) -> dict[str, Any] | None:
    stripped = text.strip()
    if not stripped:
        return None
    try:
        parsed = json.loads(stripped)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        parsed = json.loads(stripped[start : end + 1])
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _load_agent_payload(result_path: Path, stdout: str) -> dict[str, Any] | None:
    if result_path.exists():
        try:
            parsed = json.loads(result_path.read_text(encoding="utf-8"))
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
    return _extract_json_object(stdout)


def _run_passive_agent_job(
    requests: list[dict[str, str]],
    *,
    reason: str,
) -> CloudVisionResult:
    agent = _resolve_passive_agent_config()
    cli_name = agent.cli_id
    if agent.error:
        return CloudVisionResult(
            success=False,
            results={},
            provider=f"passive-agent:{cli_name}",
            model=cli_name,
            error=agent.error,
        )

    command_cli = agent.command[0] if agent.command else cli_name
    cli_path = _resolve_cli_path(command_cli)
    if not cli_path:
        return CloudVisionResult(
            success=False,
            results={},
            provider=f"passive-agent:{cli_name}",
            model=cli_name,
            error=f"CLI '{cli_name}' not found",
        )

    job_dir = get_runtime_dir() / "document-extractor" / "passive-agent-ocr" / uuid.uuid4().hex
    job_dir.mkdir(parents=True, exist_ok=True)
    result_path = job_dir / "result.json"
    request_path = job_dir / "request.json"

    request_items: list[dict[str, str]] = []
    for idx, request in enumerate(requests):
        request_id = _safe_request_id(request.get("request_id"), str(idx))
        image_path = job_dir / f"request-{request_id}.png"
        try:
            image_path.write_bytes(base64.b64decode(request["image_b64"]))
        except Exception as exc:
            return CloudVisionResult(
                success=False,
                results={},
                provider=f"passive-agent:{cli_name}",
                model=cli_name,
                error=f"failed to prepare passive OCR request {request_id}: {exc}",
            )
        request_items.append(
            {
                "request_id": request_id,
                "image_path": str(image_path),
                "prompt": request.get("prompt", "Extract all visible text from this image."),
            }
        )

    request_path.write_text(
        json.dumps(
            {
                "reason": reason,
                "requests": request_items,
                "result_path": str(result_path),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    prompt = (
        "You are completing an Augur passive OCR escalation job. "
        "Read the local image file paths in the request JSON and write OCR text "
        "to the result JSON path. Do not move, rename, or delete files.\n\n"
        f"Request path: {request_path.as_posix()}\n"
        f"Result path: {result_path.as_posix()}\n\n"
        "Write exactly this JSON shape to the result path:\n"
        '{"success": true, "results": {"<request_id>": "<extracted text>"}, "error": ""}\n'
        "If OCR is impossible, write success false with a short error. "
        "After writing the file, print a brief completion message only."
    )

    env = os.environ.copy()
    env.update(agent.env)
    env["AUGUR_AGENT_SESSION"] = "1"
    env["AUGUR_PASSIVE_AGENT_REQUEST"] = str(request_path)
    env["AUGUR_PASSIVE_AGENT_RESULT"] = str(result_path)
    env.setdefault("PYTHONIOENCODING", "utf-8")
    cmd = _agent_command(
        cli_path,
        cli_name,
        prompt,
        job_dir,
        configured_command=agent.command,
    )

    try:
        completed = subprocess.run(  # nosec B603
            cmd,
            cwd=str(get_project_root()),
            capture_output=True,
            check=False,
            encoding="utf-8",
            env=env,
            stdin=subprocess.DEVNULL,
            text=True,
            timeout=180,
        )
    except subprocess.TimeoutExpired:
        return CloudVisionResult(
            success=False,
            results={},
            provider=f"passive-agent:{cli_name}",
            model=cli_name,
            error="passive agent OCR timed out",
        )
    except Exception as exc:
        return CloudVisionResult(
            success=False,
            results={},
            provider=f"passive-agent:{cli_name}",
            model=cli_name,
            error=f"passive agent OCR failed to start: {exc}",
        )

    try:
        (job_dir / "stdout.txt").write_text(completed.stdout or "", encoding="utf-8")
        (job_dir / "stderr.txt").write_text(completed.stderr or "", encoding="utf-8")
    except Exception:
        pass

    payload = _load_agent_payload(result_path, completed.stdout or "")
    if payload is None:
        error_text = (completed.stderr or completed.stdout or "").strip()
        if completed.returncode != 0:
            error_text = error_text or f"passive agent exited with {completed.returncode}"
        return CloudVisionResult(
            success=False,
            results={},
            provider=f"passive-agent:{cli_name}",
            model=cli_name,
            error=error_text or "passive agent did not produce result JSON",
        )

    raw_results = payload.get("results")
    if payload.get("success") is not True or not isinstance(raw_results, dict):
        error = payload.get("error")
        return CloudVisionResult(
            success=False,
            results={},
            provider=f"passive-agent:{cli_name}",
            model=cli_name,
            error=str(error or "passive agent OCR returned unsuccessful result"),
        )

    results = {
        str(key): str(value).strip() for key, value in raw_results.items() if isinstance(value, str) and value.strip()
    }
    return CloudVisionResult(
        success=bool(results),
        results=results,
        provider=f"passive-agent:{cli_name}",
        model=cli_name,
        error=None if results else "passive agent OCR returned no text",
    )


def _is_unusable_ocr_text(text: str, *, reason: str) -> bool:
    normalized = " ".join(text.strip().lower().split())
    if not normalized:
        return True

    reason_text = " ".join(reason.strip().lower().split())
    if normalized in {reason_text, f"escalation reason: {reason_text}"}:
        return True

    unusable_markers = (
        "no visible text",
        "cannot see images",
        "can't see images",
        "do not see any document",
        "don't see any document",
        "no document attached",
        "please upload the image",
        "please upload the document",
    )
    return any(marker in normalized for marker in unusable_markers)


def run_cloud_vision_ocr(
    requests: list[dict[str, str]],
    *,
    reason: str,
) -> CloudVisionResult:
    passive = _run_passive_agent_job(requests, reason=reason)
    if not passive.success:
        return passive

    for request in requests:
        request_id = request.get("request_id", "")
        text = passive.results.get(request_id, "").strip()
        if _is_unusable_ocr_text(text, reason=reason):
            return CloudVisionResult(
                success=False,
                results=passive.results,
                provider=passive.provider,
                model=passive.model,
                error=f"cloud vision returned unusable OCR text for request {request_id}",
            )

    return CloudVisionResult(
        success=True,
        results=passive.results,
        provider=passive.provider,
        model=passive.model,
    )
