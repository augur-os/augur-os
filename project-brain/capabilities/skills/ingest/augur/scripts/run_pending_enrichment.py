"""Drain the ADR-753 pending-enrichment queue."""
from __future__ import annotations

import argparse
import json
import os
import subprocess  # nosec B404
import sys
import uuid
from pathlib import Path
from typing import Any, Callable


def _ensure_project_paths(start: Path) -> Path:
    for candidate in (start.parent, *start.parents):
        if (
            (candidate / "pyproject.toml").is_file()
            and (candidate / "src" / "config" / "paths.py").is_file()
        ):
            for path in (candidate, candidate / "project-brain", candidate / "src" / "mcp"):
                path_text = str(path)
                if path_text not in sys.path:
                    sys.path.insert(0, path_text)
            return candidate
    raise RuntimeError(f"Unable to locate Augur project root from {start}")


_PROJECT_ROOT = _ensure_project_paths(Path(__file__).resolve())

from src.config.paths import get_pending_enrichment_queue_path, get_runtime_dir  # noqa: E402
from src.lib.ingest.pending_enrichment_queue import drain, read_pending  # noqa: E402


def _stderr(message: str) -> None:
    print(f"[run_pending_enrichment] {message}", file=sys.stderr, flush=True)


def _load_json_object(text: str) -> dict[str, Any] | None:
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
        except Exception as exc:  # noqa: BLE001
            _stderr(f"failed to read agent result JSON {result_path}: {exc}")
    return _load_json_object(stdout)


def _note_has_enrichment_marker(note_path: Path) -> bool:
    try:
        text = note_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    return "x-augur-enrichment-status: enriched" in text


def _resolve_dispatch_helpers() -> tuple[
    Callable[..., Any],
    Callable[[str], str | None],
    Callable[..., list[str]],
] | None:
    try:
        from src.lib.agent_cli_config import (  # type: ignore
            build_agent_command,
            resolve_agent_cli_config,
            resolve_cli_path,
        )
    except Exception as exc:  # noqa: BLE001
        _stderr(f"CLI dispatch helper not available; skipping queue entries: {exc}")
        return None
    return resolve_agent_cli_config, resolve_cli_path, build_agent_command


def _dispatch_enrichment_via_cli(note_path: Path, timeout_seconds: int = 240) -> bool:
    """Run the LLM-Assisted MCP Pattern Mode 2 round trip through a CLI agent."""
    helpers = _resolve_dispatch_helpers()
    if helpers is None:
        return False
    resolve_agent_cli_config, resolve_cli_path, build_agent_command = helpers

    agent = resolve_agent_cli_config(
        "run-pending-enrichment",
        command_fields=("passive_cmd", "oneshot_cmd", "print_cmd"),
    )
    if getattr(agent, "error", None):
        _stderr(f"CLI dispatch unavailable for {note_path}: {agent.error}")
        return False

    cli_name = str(getattr(agent, "cli_id", "") or "")
    configured_command = getattr(agent, "command", None)
    command_cli = configured_command[0] if configured_command else cli_name
    cli_path = resolve_cli_path(command_cli)
    if not cli_path:
        _stderr(f"CLI '{command_cli}' not found; skipping {note_path}")
        return False

    job_dir = get_runtime_dir() / "ingest" / "pending-enrichment" / uuid.uuid4().hex
    job_dir.mkdir(parents=True, exist_ok=True)
    result_path = job_dir / "result.json"
    request_path = job_dir / "request.json"
    request_path.write_text(
        json.dumps(
            {
                "note_path": str(note_path),
                "result_path": str(result_path),
                "tool": "enrich-article",
                "submit_tool": "submit-enrich-article-result",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    prompt = (
        "You are completing an Augur ADR-753 pending article-enrichment job. "
        "Do not call any vendor API directly. Use Augur MCP tools only.\n\n"
        f"Request JSON: {request_path}\n"
        f"Result JSON to write: {result_path}\n"
        f"Note path: {note_path}\n\n"
        "Call MCP tool `enrich-article` with the note path. If it returns "
        "`success: true` and `skipped: true`, write "
        '{"success": true, "status": "skipped"} to the result JSON. '
        "If it returns `needs_llm: true`, use the returned instructions and "
        "raw content preview to produce executive_summary, key_insights, "
        "why_it_matters, verbatim_quotes, and cross_references_json. Then call "
        "`submit-enrich-article-result` with those fields and the same note_path. "
        "Write exactly this JSON shape to the result path after the submit call: "
        '{"success": true, "status": "enriched"} or '
        '{"success": false, "error": "<short exact failure>"}.'
    )

    env = os.environ.copy()
    env.update(getattr(agent, "env", {}) or {})
    env["AUGUR_AGENT_SESSION"] = "1"
    env["AUGUR_PENDING_ENRICHMENT_REQUEST"] = str(request_path)
    env["AUGUR_PENDING_ENRICHMENT_RESULT"] = str(result_path)
    env.setdefault("PYTHONIOENCODING", "utf-8")

    cmd = build_agent_command(
        cli_path,
        cli_name,
        prompt,
        configured_command=configured_command,
        job_dir=_PROJECT_ROOT,
    )

    try:
        completed = subprocess.run(  # nosec B603
            cmd,
            cwd=str(_PROJECT_ROOT),
            capture_output=True,
            check=False,
            encoding="utf-8",
            env=env,
            stdin=subprocess.DEVNULL,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        _stderr(f"dispatch timed out after {timeout_seconds}s for {note_path}")
        return False
    except Exception as exc:  # noqa: BLE001
        _stderr(f"dispatch failed to start for {note_path}: {exc}")
        return False

    try:
        (job_dir / "stdout.txt").write_text(completed.stdout or "", encoding="utf-8")
        (job_dir / "stderr.txt").write_text(completed.stderr or "", encoding="utf-8")
    except Exception:
        pass

    payload = _load_agent_payload(result_path, completed.stdout or "")
    if payload and payload.get("success") is True:
        return True
    if _note_has_enrichment_marker(note_path):
        return True

    error_text = ""
    if payload and payload.get("error"):
        error_text = str(payload.get("error"))
    else:
        error_text = (completed.stderr or completed.stdout or "").strip()
    if completed.returncode != 0 and not error_text:
        error_text = f"CLI exited with {completed.returncode}"
    _stderr(f"dispatch did not enrich {note_path}: {error_text or 'no result JSON produced'}")
    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Drain pending-enrichment queue")
    parser.add_argument("--max-per-run", type=int, default=10, help="Maximum notes to enrich in one pass")
    parser.add_argument("--timeout-seconds", type=int, default=240, help="Timeout for each CLI enrichment round trip")
    args = parser.parse_args(argv)

    queue_path = get_pending_enrichment_queue_path()
    pending = read_pending(queue_path)
    if not pending:
        print("[run_pending_enrichment] queue empty.")
        return 0

    limit = max(0, args.max_per_run)
    selected = pending[:limit]
    drained_paths: list[Path] = []
    processed = 0
    stale = 0
    failed = 0

    for entry in selected:
        raw_note_path = entry.get("note_path")
        if not isinstance(raw_note_path, str) or not raw_note_path.strip():
            failed += 1
            _stderr(f"invalid queue entry without note_path: {entry!r}")
            continue

        note_path = Path(raw_note_path)
        if not note_path.exists():
            stale += 1
            drained_paths.append(note_path)
            continue

        if _dispatch_enrichment_via_cli(note_path, timeout_seconds=args.timeout_seconds):
            processed += 1
            drained_paths.append(note_path)
        else:
            failed += 1

    removed = drain(queue_path, drained_paths)
    remaining = len(read_pending(queue_path))
    print(
        "[run_pending_enrichment] "
        f"processed={processed} stale={stale} failed={failed} drained={removed} remaining={remaining}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
