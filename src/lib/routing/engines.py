"""Thin engine adapters over already-working extraction internals + registries.

Wraps; never rewrites. The proven internals live in src/lib/extraction; this
module only adapts them to a uniform per-activity interface and registers them
under the engine ids used by the routing matrix.
"""

from __future__ import annotations

import json
import os as _os
import re
import signal
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from src.lib.extraction.cloud_vision import (
    CloudVisionResult,
    run_cloud_vision_ocr as _run_cloud_vision_ocr,
)
from src.lib.extraction.local_backend_config import get_local_ocr_settings
from src.lib.extraction.transcription import (
    TranscriptResult,
    transcribe_audio as _transcribe_audio,
)


@dataclass
class EngineAvailability:
    available: bool
    engine_id: str
    detail: str = ""
    setup_hint: str | None = None


@dataclass
class OcrResult:
    success: bool
    results: dict[str, str]  # request_id -> extracted text
    engine_id: str
    error: str | None = None
    needs_handoff: bool = False  # in-session AI client should run handoff_requests
    handoff_requests: list[dict] | None = None  # each request dict: {type, request_id, image_b64, prompt}


@dataclass
class ChatLaunchSpec:
    engine_id: str
    use_local_ollama: bool
    launch_argv: list[str] | None = None
    model: str | None = None
    ready: bool = True
    setup_hint: str | None = None
    error: str | None = None


class OcrEngine(Protocol):
    engine_id: str

    def run(self, requests: list[dict]) -> OcrResult: ...
    def available(self) -> EngineAvailability: ...


class TranscriptEngine(Protocol):
    engine_id: str

    def run(
        self,
        audio_path: str,
        *,
        model_dir: str | None = None,
        timeout_s: float | None = None,
    ) -> TranscriptResult: ...
    def available(self) -> EngineAvailability: ...


_OLLAMA_SIZE_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*([KMGT]?B)\s*$", re.IGNORECASE)
_GIB = 1024**3
_OLLAMA_LAUNCH_MEMORY_MULTIPLIER = 1.25
_OLLAMA_LAUNCH_MEMORY_RESERVE_BYTES = 2 * _GIB
_OLLAMA_OCR_NUM_CTX = 4096
_OLLAMA_OCR_NUM_PREDICT = 1024
_GEMINI_TRANSCRIBE_TIMEOUT_ENV = "AUGUR_GEMINI_TRANSCRIBE_TIMEOUT_SECONDS"
_GEMINI_TRANSCRIBE_TIMEOUT_SECONDS = 120


def _parse_ollama_size_bytes(size: object) -> int | None:
    if not isinstance(size, str):
        return None
    match = _OLLAMA_SIZE_RE.match(size)
    if not match:
        return None
    amount = float(match.group(1))
    unit = match.group(2).upper()
    multiplier = {
        "B": 1,
        "KB": 1024,
        "MB": 1024**2,
        "GB": _GIB,
        "TB": 1024**4,
    }.get(unit)
    return int(amount * multiplier) if multiplier else None


def _available_memory_bytes() -> int | None:
    if sys.platform == "darwin":
        try:
            proc = subprocess.run(
                ["vm_stat"],
                capture_output=True,
                check=False,
                stdin=subprocess.DEVNULL,
                text=True,
                timeout=2,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        if proc.returncode != 0:
            return None
        page_size = 4096
        first_line = proc.stdout.splitlines()[0] if proc.stdout else ""
        match = re.search(r"page size of (\d+) bytes", first_line)
        if match:
            page_size = int(match.group(1))
        pages: dict[str, int] = {}
        for line in proc.stdout.splitlines():
            if ":" not in line:
                continue
            label, raw_value = line.split(":", 1)
            normalized = label.strip().lower()
            value_text = raw_value.strip().rstrip(".").replace(".", "")
            try:
                pages[normalized] = int(value_text)
            except ValueError:
                continue
        reclaimable = pages.get("pages free", 0) + pages.get("pages speculative", 0) + pages.get("pages purgeable", 0)
        return reclaimable * page_size

    if sys.platform.startswith("linux"):
        try:
            lines = Path("/proc/meminfo").read_text(encoding="utf-8").splitlines()
        except OSError:
            return None
        for line in lines:
            if not line.startswith("MemAvailable:"):
                continue
            parts = line.split()
            if len(parts) >= 2:
                return int(parts[1]) * 1024
    return None


def _ollama_model_size_bytes(detection: dict[str, object], model: str) -> int | None:
    models = detection.get("models")
    if not isinstance(models, list):
        return None
    for item in models:
        if not isinstance(item, dict):
            continue
        if item.get("name") != model:
            continue
        return _parse_ollama_size_bytes(item.get("size"))
    return None


def _ollama_memory_setup_hint(
    *,
    model: str,
    model_size: int,
    available: int,
    required: int,
) -> str:
    model_gib = model_size / _GIB
    available_gib = available / _GIB
    required_gib = required / _GIB
    return (
        f"Refusing airplane chat launch for {model}: model size is "
        f"{model_gib:.1f} GiB, but only {available_gib:.1f} GiB free memory "
        f"is available; Augur requires {required_gib:.1f} GiB before starting "
        "this local model. Free memory or choose a smaller Ollama model."
    )


def _ollama_launch_memory_blocker(
    detection: dict[str, object],
    model: str,
) -> str | None:
    model_size = _ollama_model_size_bytes(detection, model)
    available = _available_memory_bytes()
    if model_size is None or available is None:
        return None
    required = int(model_size * _OLLAMA_LAUNCH_MEMORY_MULTIPLIER) + _OLLAMA_LAUNCH_MEMORY_RESERVE_BYTES
    if available >= required:
        return None
    return _ollama_memory_setup_hint(
        model=model,
        model_size=model_size,
        available=available,
        required=required,
    )


# ---------------------------------------------------------------------------
# OCR helper functions
# ---------------------------------------------------------------------------


def _is_ai_client_context() -> bool:
    from src.lib.extraction.extractor import is_ai_client_context

    return is_ai_client_context()


def _run_ollama_ocr(image_b64: str, prompt: str) -> str:
    """Run a single OCR request through the local Ollama vision model.

    Moved verbatim from extractor.py so the routing layer owns the offline OCR
    engine and extractor no longer imports back into routing.
    """
    settings = get_local_ocr_settings()
    options: dict[str, int | float] = {
        "temperature": 0,
        "num_ctx": _OLLAMA_OCR_NUM_CTX,
        "num_predict": _OLLAMA_OCR_NUM_PREDICT,
    }
    if sys.platform == "win32":
        options["num_gpu"] = 1

    payload = json.dumps(
        {
            "model": settings.model,
            "prompt": prompt,
            "images": [image_b64],
            "stream": False,
            "keep_alive": "0",
            "options": options,
        }
    ).encode()

    if not settings.generate_url.lower().startswith(("http://", "https://")):
        raise RuntimeError(f"Refusing non-HTTP URL scheme: {settings.generate_url!r}")
    req = urllib.request.Request(
        settings.generate_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(
            req, timeout=settings.timeout_s
        ) as resp:  # nosec B310  # generate_url scheme-validated above
            body = json.loads(resp.read())
            return str(body.get("response", "")).strip()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace").strip()
        raise RuntimeError(f"Ollama GLM-OCR request failed with HTTP {exc.code}: {detail or exc.reason}") from exc


# ---------------------------------------------------------------------------
# OCR engine implementations
# ---------------------------------------------------------------------------


class OllamaGlmOcrEngine:
    engine_id = "ollama-glm-ocr"

    def run(self, requests: list[dict]) -> OcrResult:
        results: dict[str, str] = {}
        try:
            for idx, request in enumerate(requests):
                request_id = str(request.get("request_id", idx))
                text = _run_ollama_ocr(request["image_b64"], request["prompt"])
                if not text:
                    return OcrResult(
                        success=False,
                        results=results,
                        engine_id=self.engine_id,
                        error=f"Ollama GLM-OCR returned no text for request {request_id}",
                    )
                results[request_id] = text
        except Exception as exc:  # noqa: BLE001
            return OcrResult(success=False, results=results, engine_id=self.engine_id, error=str(exc))
        return OcrResult(success=bool(results), results=results, engine_id=self.engine_id)

    def available(self) -> EngineAvailability:
        try:
            req = urllib.request.Request("http://localhost:11434/api/tags", method="GET")
            with urllib.request.urlopen(
                req, timeout=2
            ) as resp:  # nosec B310  # hardcoded localhost URL in Request above
                ok = resp.status == 200
        except Exception:
            ok = False
        if ok:
            return EngineAvailability(True, self.engine_id, "Ollama reachable")
        return EngineAvailability(
            False,
            self.engine_id,
            "Ollama not reachable",
            "Start Ollama and run: ollama pull glm-ocr",
        )


class AgentVisionEngine:
    engine_id = "agent-vision"

    def run(self, requests: list[dict]) -> OcrResult:
        if _is_ai_client_context():
            return OcrResult(
                success=True,
                results={},
                engine_id=self.engine_id,
                needs_handoff=True,
                handoff_requests=requests,
            )
        cloud: CloudVisionResult = _run_cloud_vision_ocr(requests, reason="regular-mode OCR")
        if cloud.success:
            return OcrResult(success=True, results=cloud.results, engine_id=self.engine_id)
        return OcrResult(success=False, results=cloud.results or {}, engine_id=self.engine_id, error=cloud.error)

    def available(self) -> EngineAvailability:
        from src.lib.extraction.cloud_vision import get_passive_agent_status

        if _is_ai_client_context():
            return EngineAvailability(True, self.engine_id, "in AI client session")
        status = get_passive_agent_status()
        if status.get("available"):
            return EngineAvailability(True, self.engine_id, f"passive agent {status.get('cli')}")
        return EngineAvailability(False, self.engine_id, str(status.get("error") or "no passive agent"))


OCR_ENGINES: dict[str, OcrEngine] = {
    "ollama-glm-ocr": OllamaGlmOcrEngine(),
    "agent-vision": AgentVisionEngine(),
}


# ---------------------------------------------------------------------------
# Transcript engine implementations
# ---------------------------------------------------------------------------


class LocalWhisperEngine:
    """Wraps transcribe_audio, which already selects OpenVINO/faster-whisper by OS."""

    def __init__(self, engine_id: str) -> None:
        self.engine_id = engine_id

    def run(
        self,
        audio_path: str,
        *,
        model_dir: str | None = None,
        timeout_s: float | None = None,
    ) -> TranscriptResult:
        del timeout_s
        return _transcribe_audio(audio_path, model_dir=model_dir)

    def available(self) -> EngineAvailability:
        from src.lib.extraction.transcription import can_transcribe_audio

        if can_transcribe_audio():
            return EngineAvailability(True, self.engine_id, "local whisper model present")
        return EngineAvailability(
            False,
            self.engine_id,
            "local whisper model/backend missing",
            "Install the OpenVINO/faster-whisper model per docs/guides/offline-backends-verification.md",
        )


def _gemini_cli_path() -> str | None:
    from src.lib.agent_cli_config import resolve_cli_path

    return resolve_cli_path("gemini")


def _gemini_transcribe_timeout_seconds(timeout_s: float | None = None) -> int:
    if timeout_s is not None:
        try:
            explicit_timeout = int(timeout_s)
        except (TypeError, ValueError):
            explicit_timeout = 0
        if explicit_timeout > 0:
            return explicit_timeout
    raw_timeout = _os.environ.get(_GEMINI_TRANSCRIBE_TIMEOUT_ENV)
    if raw_timeout:
        try:
            timeout = int(raw_timeout)
        except ValueError:
            timeout = _GEMINI_TRANSCRIBE_TIMEOUT_SECONDS
        else:
            if timeout >= 30:
                return timeout
    return _GEMINI_TRANSCRIBE_TIMEOUT_SECONDS


# Lines the Gemini CLI prints around the actual answer on Windows headless runs.
_GEMINI_NOISE = (
    "256-color",
    "ripgrep",
    "mcp issues",
    "skill conflict",
    "yolo mode is enabled",
    "attachconsole",
    "node.js v",
    "consoleprocesslist",
    "loaded cached credentials",
    "deprecationwarning",
    "experimentalwarning",
    "data collection",
)


def _clean_gemini_transcript(stdout: str) -> str:
    """Strip Gemini CLI banner/warning/stack-trace noise, leaving the transcript."""
    out: list[str] = []
    for line in (stdout or "").splitlines():
        s = line.strip()
        if not s:
            continue
        low = s.lower()
        if any(tok in low for tok in _GEMINI_NOISE):
            continue
        if low.startswith(("error:", "at ", "var ", "warning:")) or low == "^" or low.endswith(".js:11"):
            continue
        out.append(s)
    return "\n".join(out).strip()


def _kill_process_tree(proc: "subprocess.Popen") -> None:
    """Terminate a Gemini node process tree (subprocess.run cannot reap grandchildren)."""
    if proc.poll() is not None:
        return
    if sys.platform == "win32":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                timeout=10,
            )
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
    else:
        try:
            _os.killpg(proc.pid, signal.SIGTERM)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
    try:
        proc.wait(timeout=2)
    except Exception:
        if sys.platform != "win32":
            try:
                _os.killpg(proc.pid, signal.SIGKILL)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
            try:
                proc.wait(timeout=2)
            except Exception:
                pass


def _run_gemini_capture(cmd: list[str], *, cwd: str, env: dict, timeout_s: float) -> tuple[str, bool]:
    """Run a Gemini CLI command, returning (stdout, timed_out) with tree-safe kill."""
    creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) if sys.platform == "win32" else 0
    popen_kwargs: dict[str, object] = {"creationflags": creationflags}
    if sys.platform != "win32":
        popen_kwargs["start_new_session"] = True
    try:
        proc = subprocess.Popen(  # nosec B603
            cmd,
            cwd=cwd,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            **popen_kwargs,
        )
    except Exception:
        return "", False
    try:
        out, _err = proc.communicate(timeout=timeout_s)
        return out or "", False
    except subprocess.TimeoutExpired:
        _kill_process_tree(proc)
        try:
            out, _err = proc.communicate(timeout=1)
        except Exception:
            out = ""
        return out or "", True


class GeminiTranscribeEngine:
    """Regular-mode transcription via a Gemini-CLI passive-agent (no SDK).

    model_dir is accepted for interface symmetry but unused: Gemini selects its own model.
    """

    engine_id = "gemini-transcribe"

    def run(
        self,
        audio_path: str,
        *,
        model_dir: str | None = None,
        timeout_s: float | None = None,
    ) -> TranscriptResult:
        del model_dir
        from src.config.paths import get_project_root

        cli_path = _gemini_cli_path()
        if not cli_path:
            return TranscriptResult(
                success=False,
                transcript="",
                method="gemini-transcribe",
                backend="gemini",
                needs_review=True,
                error="Gemini CLI not found",
            )

        audio = Path(audio_path)
        if not audio.exists():
            return TranscriptResult(
                success=False,
                transcript="",
                method="gemini-transcribe",
                backend="gemini",
                needs_review=True,
                error=f"audio not found: {audio_path}",
            )

        # @<path> attaches the file as multimodal audio input — this bypasses the
        # Gemini read_file workspace sandbox and lets the model transcribe directly.
        # --yolo auto-approves tool actions so headless (-p) mode does not hang.
        # The transcript comes back on stdout; we do NOT ask Gemini to write a file
        # (its file tools are sandboxed to the workspace).
        prompt = (
            f"Transcribe the audio file @{audio} and reply with ONLY the verbatim " "transcript text, nothing else."
        )
        cmd = [cli_path, "--yolo", "-p", prompt]
        env = _os.environ.copy()
        env["AUGUR_AGENT_SESSION"] = "1"
        env.setdefault("PYTHONIOENCODING", "utf-8")

        stdout, timed_out = _run_gemini_capture(
            cmd,
            cwd=str(get_project_root()),
            env=env,
            timeout_s=_gemini_transcribe_timeout_seconds(timeout_s),
        )
        if timed_out:
            return TranscriptResult(
                success=False,
                transcript="",
                method="gemini-transcribe",
                backend="gemini",
                needs_review=True,
                error="gemini transcription timed out",
            )

        transcript = _clean_gemini_transcript(stdout)
        if transcript:
            return TranscriptResult(
                success=True,
                transcript=transcript,
                method="gemini-transcribe",
                backend="gemini",
                confidence="medium",
                cloud_used=True,
            )
        return TranscriptResult(
            success=False,
            transcript="",
            method="gemini-transcribe",
            backend="gemini",
            needs_review=True,
            error="gemini returned no transcript",
        )

    def available(self) -> EngineAvailability:
        if _gemini_cli_path():
            return EngineAvailability(True, self.engine_id, "gemini CLI present")
        return EngineAvailability(
            False,
            self.engine_id,
            "gemini CLI not found",
            "Install the Gemini CLI to enable agent-based transcription (regular mode).",
        )


# Two ids share LocalWhisperEngine: the matrix picks openvino-whisper (win32/linux)
# or faster-whisper (darwin); transcribe_audio already selects the right backend.
TRANSCRIPT_ENGINES: dict[str, TranscriptEngine] = {
    "openvino-whisper": LocalWhisperEngine("openvino-whisper"),
    "faster-whisper": LocalWhisperEngine("faster-whisper"),
    "gemini-transcribe": GeminiTranscribeEngine(),
}


# ---------------------------------------------------------------------------
# Chat engine
# ---------------------------------------------------------------------------


def build_ollama_launch_spec(agent_id: str = "claude") -> ChatLaunchSpec:
    """Offline chat launch argv from Ollama detection — NO smoke probing.

    Reuses the lightweight detection helpers in local_backends but drops the
    deleted probe ladders.
    """
    from src.mcp.augur_framework.tools.infrastructure.local_backends import (
        _detect_ollama,
        _integration_launch_args,
        _load_local_prefs,
        _load_ollama_config,
        _model_for_agent,
        _setup_hint,
    )

    detection = _detect_ollama()
    if not detection["installed"]:
        return ChatLaunchSpec("ollama-llm", True, ready=False, setup_hint=_setup_hint("binary_missing"))
    if not detection["server_running"]:
        return ChatLaunchSpec("ollama-llm", True, ready=False, setup_hint=_setup_hint("ollama_not_running"))

    config = _load_ollama_config(_load_local_prefs())
    model = _model_for_agent(config, agent_id)
    model_names = {m.get("name") for m in detection["models"] if isinstance(m, dict)}
    if model not in model_names:
        return ChatLaunchSpec(
            "ollama-llm",
            True,
            model=model,
            ready=False,
            setup_hint=_setup_hint("model_missing", model=model),
        )
    memory_blocker = _ollama_launch_memory_blocker(detection, model)
    if memory_blocker:
        return ChatLaunchSpec(
            "ollama-llm",
            True,
            model=model,
            ready=False,
            setup_hint=memory_blocker,
            error="insufficient_memory",
        )

    # Mirrors local_backends.get_airplane_launch_overrides_impl (ADR-640):
    # `ollama launch <agent> --model <m> -- ...` runs an agent integration (e.g. Claude
    # Code / Codex) backed by a local Ollama model. NOT `ollama run` (interactive REPL).
    argv = [detection["binary"], "launch", agent_id, "--model", model, "--", *_integration_launch_args(agent_id)]
    return ChatLaunchSpec("ollama-llm", True, launch_argv=argv, model=model, ready=True)
