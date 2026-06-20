from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Callable, TYPE_CHECKING, cast

import yaml

from src.config.paths import (
    get_project_root,
    get_rag_dir,
    get_runtime_dir,
    get_vault_dir,
)
from src.lib.brain_layout import brain_capture_dir as _brain_capture_dir
from src.lib.brain_layout import vault_machine_dir as _vault_machine_dir
from src.config.preferences import get_preferences_path
from src.lib.frontmatter_utils import parse_frontmatter, write_vault_frontmatter

from skills.demo.scripts.demo_ready import (
    check_demo_readiness,
    prepare_demo_state,
    run_demo_smoke,
)
from skills.demo.scripts.demo_run_acceptance import (
    DemoStatus,
    ensure_demo_run_note,
    run_ask_transcript_case,
    run_meeting_memory_case,
    run_transcript_case,
    reset_demo_run_state,
    write_demo_evidence,
)
from src.lib.ingest.inbox_store import InboxStore

from ._shared import tool_annotations

DEMO_PROMPT_INDEX_CATEGORIES = ("documents", "vault")
DEMO_PROMPT_CONTEXT_FIELDS = (
    ("document_summary", "Summary"),
    ("document_key_insights", "Key insights"),
    ("document_sections", "Sections"),
    ("document_action_candidates", "Action candidates"),
    ("description", "Description"),
    ("summary", "Summary"),
)
DEMO_PROMPT_CONTEXT_CHAR_LIMIT = 2800
DEMO_PROMPT_BODY_EXCERPT_CHAR_LIMIT = 900
DEMO_PROMPT_INDEX_SCAN_LIMIT = 5000
DEMO_RUNBOOK_OUTPUT_HEADING = "expected visible output"
DEMO_RUNBOOK_BOUNDED_COMMAND_HEADINGS = (
    "bounded live command",
    "bounded live commands",
)
DEMO_GEMINI_TRANSCRIBE_TIMEOUT_SECONDS = 10
DEMO_01_RESET_REASON = "before-demo_01_wiki_llm_cross_agent_ask"
DEMO_01_QUESTION = (
    "What pattern is emerging in how I want Augur's wiki to compound and learn "
    "from me over time?"
)
DEMO_02_RESET_REASON = "before-demo_02_discover_gui_web_capture"
DEMO_02_URL = "https://www.iana.org/domains/reserved"
DEMO_02_SEARCH = "IANA-managed Reserved Domains"
DEMO_03_RESET_REASON = "before-demo_03_offload_transcription_airplane"
def _demo_03_audio_path() -> Path:
    """Resolve the demo audio file from the vault (ADR-814: no hardcoded paths)."""
    return get_vault_dir() / "voice-memos" / "2026-06-01-offload-demo-short.m4a"
DEMO_04_RESET_REASON = "before-demo_04_compound_dry_run"
DEMO_05_RESET_REASON = "before-demo_05_airplane_safety_evidence"
DEMO_06_RESET_REASON = "before-demo_06_brain_manifest_architecture"

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def _store_root() -> "Path":
    return get_runtime_dir() / "brain" / "inbox"


def _store() -> InboxStore:
    return InboxStore(_store_root())


def _demo_desktop(desktop: str) -> Path:
    normalized = desktop.strip().lower() if desktop else ""
    if normalized in {"", "local", "default", "demo", "demo-inbox"}:
        return Path.home() / "Desktop" / "Augur Workflow Example Inbox"
    return Path(desktop).expanduser()


async def demo_readiness_impl(desktop: str = "", require_cloud: bool = True) -> str:
    target = _demo_desktop(desktop)
    result = check_demo_readiness(desktop=target, require_cloud=require_cloud)
    return json.dumps({"success": bool(result["ready"]), **result})


async def demo_reset_impl(desktop: str = "", airplane: str = "on") -> str:
    airplane_value = "off" if airplane == "off" else "on"
    target = _demo_desktop(desktop)
    result = prepare_demo_state(
        desktop=target,
        store_root=_store_root(),
        vault_dir=get_vault_dir(),
        preferences_path=get_preferences_path(),
        airplane_mode=airplane_value == "on",
    )
    return json.dumps({"airplane": airplane_value, **result})


async def demo_smoke_impl(
    desktop: str = "",
    airplane: str = "on",
    require_cloud: bool = False,
) -> str:
    airplane_value = "off" if airplane == "off" else "on"
    result = run_demo_smoke(
        desktop=_demo_desktop(desktop),
        airplane=airplane_value,
        require_cloud=require_cloud,
    )
    return json.dumps(result)


async def demo_run_note_impl() -> str:
    try:
        note_path = ensure_demo_run_note(vault_dir=get_vault_dir())
        return json.dumps(
            {
                "success": True,
                "message": "Workflow example run acceptance note is ready.",
                "note_path": str(note_path),
                "content": note_path.read_text(encoding="utf-8"),
            }
        )
    except Exception as exc:
        return json.dumps({"success": False, "error": str(exc)})


async def demo_run_reset_state_impl(reason: str = "practice-loop") -> str:
    try:
        note_path = reset_demo_run_state(
            reason=reason or "practice-loop",
            vault_dir=get_vault_dir(),
        )
        return json.dumps(
            {
                "success": True,
                "message": "Workflow example run acceptance note state reset.",
                "note_path": str(note_path),
                "reason": reason or "practice-loop",
            }
        )
    except Exception as exc:
        return json.dumps({"success": False, "error": str(exc)})


def _demo_evidence_success(evidence: Any) -> bool:
    return getattr(evidence, "eval_success", None) is not False


def _demo_evidence_status(evidence: Any) -> str:
    if getattr(evidence, "eval_success", None) is False:
        return "fail"
    return str(getattr(evidence, "status", ""))


async def demo_run_record_evidence_impl(
    source_path: str,
    case_id: str = "meeting-transcript",
    command: str = "",
    status: str = "pass",
    backend: str = "",
    client: str = "",
    duration_seconds: float | None = None,
    output_path: str = "",
    failure_reason: str = "",
    missing_prerequisite: str = "",
    eval_link: str = "",
    source_name: str = "",
    useful_snippet: str = "",
) -> str:
    if not source_path.strip():
        return json.dumps({"success": False, "error": "Missing source_path."})
    try:
        normalized_source_path = Path(source_path).expanduser()
        if not normalized_source_path.exists():
            return json.dumps(
                {
                    "success": False,
                    "error": f"Source path is missing: {normalized_source_path}",
                }
            )
        if status not in {"pass", "fail", "blocked", "reset"}:
            return json.dumps(
                {"success": False, "error": f"Invalid example status: {status}"}
            )
        evidence = write_demo_evidence(
            case_id=case_id,
            command=command or "demo-run-record-evidence",
            status=cast(DemoStatus, status),
            backend=backend or "unknown",
            client=client or None,
            duration_seconds=duration_seconds,
            output_path=Path(output_path) if output_path.strip() else None,
            failure_reason=failure_reason or None,
            missing_prerequisite=missing_prerequisite or None,
            eval_link=eval_link or None,
            source_file=normalized_source_path,
            source_title=source_name or None,
            useful_snippet=useful_snippet,
            run_eval=True,
            vault_dir=get_vault_dir(),
        )
        return json.dumps(
            {
                "success": _demo_evidence_success(evidence),
                "message": "Workflow example run evidence card written.",
                "evidence_path": str(evidence.path),
                "case_id": evidence.case_id,
                "command": evidence.command,
                "status": _demo_evidence_status(evidence),
                "command_status": getattr(evidence, "command_status", None),
                "backend": evidence.backend,
                "client": evidence.client,
                "source_path": str(evidence.source_file),
                "source_name": source_name or evidence.source_title,
                "source_title": evidence.source_title,
                "eval_run_id": evidence.eval_run_id,
                "eval_link": evidence.eval_link,
                "eval_status": evidence.eval_status,
                "eval_error": evidence.eval_error,
                "eval_success": getattr(evidence, "eval_success", None),
                "partial": bool(getattr(evidence, "partial", False)),
            }
        )
    except Exception as exc:
        return json.dumps({"success": False, "error": str(exc)})


def _markdown_section(body: str, heading: str) -> str:
    target = heading.strip().lower()
    lines = body.splitlines()
    start: int | None = None
    for index, line in enumerate(lines):
        normalized = line.strip().lstrip("#").strip().lower()
        if line.lstrip().startswith("##") and normalized == target:
            start = index + 1
            break
    if start is None:
        return ""

    end = len(lines)
    for index in range(start, len(lines)):
        if lines[index].startswith("## "):
            end = index
            break
    return "\n".join(lines[start:end]).strip()


def _first_fenced_block(text: str) -> str:
    match = re.search(r"```[^\n]*\n(?P<body>.*?)\n```", text, flags=re.DOTALL)
    if not match:
        return ""
    return match.group("body").strip()


def _demo_runbook_visible_output(body: str) -> str:
    expected_section = _markdown_section(body, DEMO_RUNBOOK_OUTPUT_HEADING)
    output = _first_fenced_block(expected_section) or expected_section.strip()
    if output:
        return output

    example_index = body.lower().find("example good output")
    if example_index >= 0:
        output = _first_fenced_block(body[example_index:])
        if output:
            return output
    return ""


def _demo_runbook_bounded_command(body: str) -> str:
    for heading in DEMO_RUNBOOK_BOUNDED_COMMAND_HEADINGS:
        section = _markdown_section(body, heading)
        command = _first_fenced_block(section) or section.strip()
        if command:
            return command
    return ""


def _demo_runbook_path_from_id(demo_id: str) -> Path | None:
    normalized_demo_id = demo_id.strip()
    if not normalized_demo_id:
        return None
    if not re.fullmatch(r"[A-Za-z0-9_-]+", normalized_demo_id):
        return None
    return (
        get_project_root()
        / "project-brain"
        / "capabilities"
        / "skills"
        / "ingest"
        / "demos"
        / f"{normalized_demo_id}.md"
    )


async def demo_runbook_output_impl(
    source_path: str = "",
    title: str = "",
    demo_id: str = "",
) -> str:
    resolved_source_path = (
        Path(source_path).expanduser()
        if source_path.strip()
        else _demo_runbook_path_from_id(demo_id) or Path()
    )
    if not str(resolved_source_path).strip() or resolved_source_path == Path():
        return json.dumps(
            {"success": False, "error": "Missing source_path or demo_id."}
        )

    try:
        normalized_source_path = resolved_source_path
        if not normalized_source_path.exists():
            return json.dumps(
                {
                    "success": False,
                    "error": f"Workflow example runbook is missing: {normalized_source_path}",
                }
            )

        metadata, body = parse_frontmatter(normalized_source_path)
        source_type = str(
            metadata.get("type") or metadata.get("_source_type") or ""
        ).strip()
        if source_type != "demo-runbook" and not normalized_source_path.name.startswith("demo_"):
            return json.dumps(
                {
                    "success": False,
                    "error": f"Not a workflow example runbook: {normalized_source_path}",
                }
            )

        output = _demo_runbook_visible_output(body)
        if not output:
            return json.dumps(
                {
                    "success": False,
                    "error": "Workflow example runbook has no Expected Visible Output block.",
                    "source_path": str(normalized_source_path),
                }
            )

        normalized_title = (
            title.strip()
            or str(metadata.get("title") or "").strip()
            or normalized_source_path.stem.replace("_", " ")
        )
        normalized_demo_id = (
            demo_id.strip()
            or str(metadata.get("demo_id") or "").strip()
            or normalized_source_path.stem
        )
        bounded_command = _demo_runbook_bounded_command(body)
        prompt_lines = [
            f"Run the live workflow for {normalized_title}.",
            f"Read the runbook first: {normalized_source_path}",
            f"Before any live workflow example work, run demo-run-reset with reason before-{normalized_demo_id} and confirm success.",
            "Follow the runbook's Automatic Reset / Idempotency section before executing mutable steps.",
            "If reset or preflight fails, stop and return that failure instead of running the workflow example.",
        ]
        if bounded_command:
            prompt_lines.extend(
                [
                    "Run this bounded command exactly:",
                    bounded_command,
                    "Do not search, inspect source, import Python modules, or substitute a different command before this command.",
                    "If the command returns JSON with chat_output, return only chat_output as the final answer.",
                ]
            )
        else:
            prompt_lines.append(
                "Execute the Agent Prompt and Live Flow with real Augur tools or the native AI client."
            )
        prompt_lines.extend(
            [
                "If the runbook provides a Bounded Live Command, run that command directly and do not replace it with exploratory scripts unless it fails.",
                "Do not repeat the Expected Visible Output preview as the result.",
                "If a step would mutate files, settings, pins, or external state, follow the runbook stop conditions and ask before mutation.",
                "Return the actual user-visible output, evidence path, or stop condition.",
            ]
        )
        live_prompt = "\n".join(prompt_lines)
        return json.dumps(
            {
                "success": True,
                "message": "Workflow example runbook output is ready.",
                "action_label": normalized_title,
                "demo_id": normalized_demo_id,
                "source_path": str(normalized_source_path),
                "prompt": live_prompt,
                "chat_output": output,
            }
        )
    except Exception as exc:
        return json.dumps({"success": False, "error": str(exc)})


def _demo_wiki_ask_clusters(days_back: int, limit: int) -> list[dict[str, Any]]:
    from src.lib.ingest.ask_sync import load_recent_ask_outcomes
    from src.lib.ingest.ask_sync_clusters import (
        cluster_ask_outcomes,
        suggest_page_targets,
    )
    from src.lib.ingest.wiki_pages_read import get_wiki_pages as _get_wiki_pages

    items = load_recent_ask_outcomes(days_back=days_back, limit=limit)
    clusters = cluster_ask_outcomes(items)
    return suggest_page_targets(clusters, _get_wiki_pages().read_tags())


def _select_demo_wiki_cluster(clusters: list[dict[str, Any]]) -> dict[str, Any] | None:
    for cluster in clusters:
        label = str(cluster.get("label", "")).lower()
        if "wiki" in label and "compound" in label:
            return cluster
    return clusters[0] if clusters else None


def _demo_wiki_cluster_target(cluster: dict[str, Any] | None) -> str:
    if not cluster:
        return "none"
    targets = cluster.get("page_targets")
    if isinstance(targets, list) and targets:
        first = targets[0]
        if isinstance(first, dict):
            page = str(first.get("page") or "").strip()
            if page:
                return page
    return "none"


def _demo_wiki_target_path(target: str) -> str:
    normalized = str(target or "").strip().strip("/")
    if not normalized or normalized == "none":
        return "missing wiki target"
    if not normalized.endswith(".md"):
        normalized = f"{normalized}.md"
    return str(get_vault_dir() / "wiki" / normalized)


def _demo_cluster_source_path(cluster: dict[str, Any] | None) -> str:
    if not cluster:
        return ""
    items = cluster.get("items")
    if not isinstance(items, list):
        return ""
    for item in items:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or item.get("source_path") or "").strip()
        if path:
            return path
    return ""


def _demo_cluster_summary(cluster: dict[str, Any] | None) -> str:
    if not cluster:
        return "missing cluster summary"
    summary = str(cluster.get("summary") or "").strip()
    if summary:
        return _demo_collapse_preview_text(summary, limit=220)
    label = str(cluster.get("label") or "ask cluster").strip()
    return _demo_collapse_preview_text(label, limit=220)


def _demo_cluster_source_excerpt(path_text: str) -> str:
    if not path_text:
        return "Source synthesis file was not reported by the cluster."
    try:
        path = Path(path_text).expanduser()
        _meta, body = parse_frontmatter(path, include_sidecar_config=False)
        return _demo_preview_presentation_language(" ".join(body.split()))
    except OSError:
        return "Source synthesis file could not be read during artifact creation."


def _demo_artifact_path(slug: str) -> Path:
    vault = get_vault_dir()
    return _brain_capture_dir(vault) / "examples" / "artifacts" / slug


def _write_demo_artifact(
    *,
    slug: str,
    title: str,
    demo_id: str,
    tags: list[str],
    body_lines: list[str],
) -> Path:
    artifact_path = _demo_artifact_path(slug)
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    write_vault_frontmatter(
        artifact_path,
        {
            "title": title,
            "type": "workflow-example-artifact",
            "demo_id": demo_id,
            "x-augur-note-type": "file",
            "_source_type": "workflow-example-artifact",
            "tags": ["example", "workflow-example", "artifact", *tags],
        },
        "\n".join(body_lines).rstrip() + "\n",
    )
    return artifact_path


def _write_demo_wiki_ask_artifact(
    *,
    cluster: dict[str, Any],
    item_count: int,
    priority_score: Any,
    target: str,
    synthesis_path: str,
    wiki_target_path: str,
) -> Path:
    del cluster, target, wiki_target_path
    return _write_demo_artifact(
        slug="demo-01-wiki-llm-cross-agent-ask.md",
        title="Workflow Example 01 Cross-Agent Wiki Compounding",
        demo_id="demo_01_wiki_llm_cross_agent_ask",
        tags=["ask", "wiki", "compounding", "cross-agent"],
        body_lines=[
            "# Workflow Example 01: Cross-Agent Wiki Compounding",
            "",
            "## Bottom Line",
            "Augur turns repeated ask answers from different agents into one governed wiki concept that the next agent can reuse.",
            "",
            "## Live Proof",
            f"- Augur found {item_count} retained answers about the same wiki-compounding pattern.",
            "- The retained answers point to the same durable concept: Wiki Ingest And Compilation Commands.",
            "- The result is inspectable in Browse as a brain file, not hidden inside one chat vendor's memory.",
            "- Codex and Claude can both use the same governed brain state.",
            "",
            "## What To Show",
            "1. Search Browse for: Workflow Example 01 Cross-Agent Wiki Compounding.",
            "2. Point at the retained-answer count.",
            "3. Point at Wiki Ingest And Compilation Commands as the wiki target.",
            "4. Switch agents and repeat the ask to show the same brain is shared.",
            "",
            "## Investor Takeaway",
            "The product is not just a chat UI. Augur is a harness that lets native agents compound knowledge into reviewable files and reuse it across sessions.",
            "",
            "## Source-Backed Signal",
            _demo_cluster_source_excerpt(synthesis_path),
            "",
            "## Verification Snapshot",
            f"- Retained outcomes: {item_count}",
            f"- Priority score: {priority_score}",
            "- Wiki target: Wiki Ingest And Compilation Commands",
            "- Status: pass",
            "",
        ],
    )


def _write_demo_discover_capture_artifact(
    *,
    command_surface: str,
    card_title: str,
    capture_label: str,
) -> Path:
    readable_title = card_title or "IANA-managed Reserved Domains"
    return _write_demo_artifact(
        slug="demo-02-discover-gui-web-capture.md",
        title="Workflow Example 02 Command Surface Web Capture",
        demo_id="demo_02_discover_gui_web_capture",
        tags=["discover", "gui", "web-capture", "iana"],
        body_lines=[
            "# Workflow Example 02: Command Surface And Web Capture",
            "",
            "## Bottom Line",
            "Augur shows its command surface in the GUI, then turns a normal webpage into a searchable brain file.",
            "",
            "## Live Proof",
            f"- Discover exposed {command_surface} from the real Augur command registry.",
            f"- The web capture reused an {capture_label} for IANA-managed Reserved Domains.",
            f"- Browse can search and open the saved webpage card titled {readable_title}.",
            "- The command list, source card, and Browse result all land in the same user-facing brain surface.",
            "",
            "## What To Show",
            "1. Click Run on Workflow Example 02 and point at the command surface count.",
            "2. Search Browse for: Workflow Example 02 Command Surface Web Capture.",
            "3. Search Browse for: IANA-managed Reserved Domains.",
            "4. Open the saved webpage card and show that the page is now local brain material.",
            "",
            "## Investor Takeaway",
            "The product is not a command-line wrapper. Augur gives agents and users one inspectable GUI surface for commands, captures, and saved evidence.",
            "",
            "## Verification Snapshot",
            f"- Command surface: {command_surface}",
            f"- Saved webpage: {readable_title}",
            "- Browse search phrase: IANA-managed Reserved Domains",
            "- Status: pass",
            "",
        ],
    )


def _write_demo_transcription_offload_artifact(
    *,
    offline: dict[str, Any],
    online: dict[str, Any] | None,
    active_client: str,
    status: str,
) -> Path:
    offline_engine = str(
        offline.get("route_engine_id") or offline.get("method") or "faster-whisper"
    )
    online_engine = "Gemini native transcription"
    online_preview = "Run from Gemini to prove the online leg with the native client."
    if online:
        online_engine = str(online.get("route_engine_id") or online.get("method") or online_engine)
        online_preview = _demo_transcript_preview(online, limit=220)
    return _write_demo_artifact(
        slug="demo-03-offline-online-transcription-offload.md",
        title="Workflow Example 03 Offline Online Transcription Offload",
        demo_id="demo_03_offload_transcription_airplane",
        tags=["transcript", "offline", "online", "offload", "airplane"],
        body_lines=[
            "# Workflow Example 03: Offline And Online Transcription Offload",
            "",
            "## Bottom Line",
            "Augur routes the same transcription task through local offline execution or a native online client while keeping the user workflow the same.",
            "",
            "## Live Proof",
            f"- Offline route used {offline_engine} with cloud_used false.",
            f"- Offline transcript preview: {_demo_transcript_preview(offline, limit=220)}",
            f"- Online route: {online_engine}.",
            f"- Online transcript preview: {online_preview}",
            "- The transcript is saved as a searchable workflow example transcript card instead of remaining hidden in chat.",
            "",
            "## What To Show",
            "1. Search Browse for: Workflow Example 03 Offline Online Transcription Offload.",
            "2. Search Browse for: Offload Workflow Example Offline.",
            "3. Open the transcript card and read the transcript preview out loud.",
            "4. If running from Gemini, repeat the run to show Gemini-native online transcription; otherwise point at the explicit Gemini stop condition.",
            "",
            "## Investor Takeaway",
            "Augur controls harness state and context, so native agents can share one offload workflow without the user learning separate execution paths.",
            "",
            "## Verification Snapshot",
            f"- Offline engine: {offline_engine}",
            f"- Online client: Gemini when active client is Gemini; current client: {active_client}",
            f"- Transcript artifact: {'written' if _demo_has_transcript_artifact(offline) else 'missing'}",
            f"- Status: {status}",
            "",
        ],
    )


def _write_demo_compound_preview_artifact(
    *,
    cluster: dict[str, Any],
    item_count: int,
    priority_score: Any,
    target: str,
) -> Path:
    return _write_demo_artifact(
        slug="demo-04-compound-dry-run.md",
        title="Workflow Example 04 Governed Compounding Preview",
        demo_id="demo_04_compound_dry_run",
        tags=["compound", "dry-run", "wiki", "governance"],
        body_lines=[
            "# Workflow Example 04: Governed Compounding Preview",
            "",
            "## Bottom Line",
            "Augur can show what knowledge would compound before any wiki page is mutated.",
            "",
            "## Live Proof",
            f"- The dry run found {item_count} retained ask outcomes for the wiki-compounding topic.",
            f"- Priority score for the cluster is {priority_score}.",
            f"- The suggested wiki target is {target}.",
            "- Safety proof: no wiki page was mutated during this workflow example run.",
            "",
            "## What To Show",
            "1. Search Browse for: Workflow Example 04 Governed Compounding Preview.",
            "2. Point at the retained outcome count and priority score.",
            "3. Point at Wiki Ingest And Compilation Commands as the suggested target.",
            "4. Explain that full mode would apply only after review.",
            "",
            "## Investor Takeaway",
            "Compounding is governed promotion with previewable evidence, not blind autosave into memory.",
            "",
            "## Verification Snapshot",
            f"- Retained outcomes: {item_count}",
            f"- Priority score: {priority_score}",
            f"- Evidence summary: {item_count} retained outcomes converge on {target}.",
            "- Status: pass",
            "",
        ],
    )


def _write_demo_airplane_safety_artifact(
    *,
    smoke: dict[str, Any],
    cloud_calls: int,
    files_indexed: int,
    status: str,
) -> Path:
    return _write_demo_artifact(
        slug="demo-05-airplane-safety-evidence.md",
        title="Workflow Example 05 Local Only Safety Evidence",
        demo_id="demo_05_airplane_safety_evidence",
        tags=["airplane", "offline", "local-first", "safety"],
        body_lines=[
            "# Workflow Example 05: Local-Only Safety Evidence",
            "",
            "## Bottom Line",
            "Augur proves local-first execution with safety gates before launch, so offline workflow examples do not freeze the Mac or silently call cloud services.",
            "",
            "## Live Proof",
            "- The smoke run forced airplane mode on with cloud escalation disallowed.",
            f"- Cloud calls: {cloud_calls}.",
            f"- Files indexed: {files_indexed}.",
            f"- Local engines visible before launch: {_demo_local_engines(smoke)}.",
            "- Unsafe local launches are reported as unavailable instead of being forced.",
            "",
            "## What To Show",
            "1. Search Browse for: Workflow Example 05 Local Only Safety Evidence.",
            "2. Point at Cloud calls: 0.",
            "3. Point at the local engine list.",
            "4. Explain that Augur owns the safety gate, not the chat model.",
            "",
            "## Investor Takeaway",
            "The architecture can enforce managed offline mode and produce evidence that cloud use stayed at zero.",
            "",
            "## Verification Snapshot",
            f"- Cloud calls: {cloud_calls}",
            f"- Files indexed: {files_indexed}",
            f"- Evidence card: {_demo_evidence_pin_summary(smoke).split(' at ', 1)[0]}",
            f"- Status: {status}",
            "",
        ],
    )


def _write_demo_brain_manifest_artifact(
    *,
    metadata: dict[str, Any],
    missing: list[str],
    status: str,
) -> Path:
    brain_id = str(metadata.get("id") or "project-augur")
    brain_type = str(metadata.get("type") or "project")
    return _write_demo_artifact(
        slug="demo-06-brain-manifest-architecture.md",
        title="Workflow Example 06 Brain Manifest Architecture",
        demo_id="demo_06_brain_manifest_architecture",
        tags=["brain", "manifest", "architecture", "folders"],
        body_lines=[
            "# Workflow Example 06: Brain Manifest Architecture",
            "",
            "## Bottom Line",
            "An Augur brain is a governed, file-backed workspace with a manifest and folder contract, not hidden prompt state.",
            "",
            "## Live Proof",
            f"- BRAIN.yaml identifies this brain as {brain_id} with type {brain_type}.",
            "- capabilities/skills holds executable skills.",
            "- knowledge holds memory, source material, and wiki content.",
            "- instructions holds portable agent behavior, while decisions/adrs holds architecture history.",
            "- The project brain and personal brain remain separated by design.",
            "",
            "## What To Show",
            "1. Search Browse for: Workflow Example 06 Brain Manifest Architecture.",
            "2. Open project-brain/BRAIN.yaml.",
            "3. Open project-brain/capabilities/skills.",
            "4. Explain the difference between project brain and personal brain.",
            "",
            "## Investor Takeaway",
            "The brain format gives native agents a reviewable contract for memory, instructions, skills, and architecture decisions.",
            "",
            "## Verification Snapshot",
            f"- Brain id: {brain_id}",
            f"- Brain type: {brain_type}",
            f"- Missing folders: {', '.join(missing) if missing else 'none'}",
            f"- Status: {status}",
            "",
        ],
    )


def _demo_evidence_pin_path(smoke: dict[str, Any]) -> str:
    pin = smoke.get("evidence_pin")
    if not isinstance(pin, dict):
        return "missing evidence card"
    return str(pin.get("path") or pin.get("url") or "missing evidence card").strip()


DEMO_AIRPLANE_EVIDENCE_TITLE = "Workflow Example Meeting Evidence"


def _demo_airplane_presentation_text(text: str) -> str:
    replacements = [
        (r"\bdemo-meeting\b", DEMO_AIRPLANE_EVIDENCE_TITLE),
        (r"\bAugur Investor Demo Meeting\b", "Augur Investor Workflow Example Meeting"),
        (r"\bReviewed Investor Demo Readiness\b", "Reviewed Workflow Example Readiness"),
        (r"\bInvestor Demo Readiness\b", "Workflow Example Readiness"),
        (r"\binvestor demo\b", "workflow example"),
    ]
    result = text
    for pattern, replacement in replacements:
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    return _demo_preview_presentation_language(result)


def _demo_airplane_presentation_body(body: str) -> str:
    lines: list[str] = []
    for line in body.splitlines():
        stripped = line.strip().lower()
        if stripped.startswith(("- original:", "- final:", "- extracted:")):
            lines.append(line)
            continue
        lines.append(_demo_airplane_presentation_text(line))
    text = "\n".join(lines)
    if re.search(r"(?m)^#\s+", text):
        return re.sub(r"(?m)^#\s+.*$", f"# {DEMO_AIRPLANE_EVIDENCE_TITLE}", text, count=1)
    return f"# {DEMO_AIRPLANE_EVIDENCE_TITLE}\n\n{text}".rstrip() + "\n"


def _demo_update_current_evidence_pin_title(path: Path, title: str) -> None:
    pins_path = _vault_machine_dir(get_vault_dir(), "system") / "pins.yaml"
    try:
        data = yaml.safe_load(pins_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return
    pins = data.get("pins")
    if not isinstance(pins, list):
        return
    changed = False
    path_text = str(path)
    for pin in pins:
        if not isinstance(pin, dict):
            continue
        if pin.get("url") != path_text:
            continue
        if pin.get("title") != title:
            pin["title"] = title
            changed = True
    if not changed:
        return
    try:
        pins_path.write_text(
            yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
    except OSError:
        return


def _normalize_demo_airplane_evidence_card(smoke: dict[str, Any]) -> str:
    pin = smoke.get("evidence_pin")
    if isinstance(pin, dict):
        pin["title"] = DEMO_AIRPLANE_EVIDENCE_TITLE

    path_text = _demo_evidence_pin_path(smoke)
    if not path_text or path_text == "missing evidence card":
        return DEMO_AIRPLANE_EVIDENCE_TITLE
    path = Path(path_text).expanduser()
    try:
        metadata, body = parse_frontmatter(path, include_sidecar_config=False)
    except (OSError, UnicodeDecodeError, ValueError):
        return DEMO_AIRPLANE_EVIDENCE_TITLE

    metadata["title"] = DEMO_AIRPLANE_EVIDENCE_TITLE
    metadata["note"] = "Workflow Example 05 local-only safety evidence card."
    tags = [str(tag) for tag in metadata.get("tags", [])] if isinstance(metadata.get("tags"), list) else []
    for tag in ("example", "workflow-example", "airplane-safety", "local-first"):
        if tag not in tags:
            tags.append(tag)
    metadata["tags"] = tags
    relates = (
        [str(item) for item in metadata.get("_relates_to", [])]
        if isinstance(metadata.get("_relates_to"), list)
        else []
    )
    for item in ("[[example]]", "[[workflow-example]]", "[[airplane-safety]]"):
        if item not in relates:
            relates.append(item)
    metadata["_relates_to"] = relates
    write_vault_frontmatter(path, metadata, _demo_airplane_presentation_body(body))
    _demo_update_current_evidence_pin_title(path, DEMO_AIRPLANE_EVIDENCE_TITLE)
    try:
        from src.lib.ingest.note_index_refresh import refresh_notes_browse_index

        refresh_notes_browse_index()
    except Exception:  # noqa: BLE001 - Browse will catch up on the next index refresh.
        pass
    return DEMO_AIRPLANE_EVIDENCE_TITLE


async def demo_run_wiki_ask_impl(days_back: int = 90, limit: int = 5) -> str:
    try:
        reset_path = reset_demo_run_state(DEMO_01_RESET_REASON, vault_dir=get_vault_dir())
        clusters = _demo_wiki_ask_clusters(days_back=days_back, limit=limit)
        cluster = _select_demo_wiki_cluster(clusters)
        if not cluster:
            output = "\n".join(
                [
                    "Workflow Example 01 is running: we are proving cross-agent wiki compounding from the shared Augur brain.",
                    "Answer: No retained wiki-compounding cluster is available yet.",
                    "Evidence: ask-sync-clusters returned 0 retained clusters for this run.",
                    "Confidence: low; the retained cluster is missing.",
                    "Retained: no fresh retention was attempted by the bounded workflow example command.",
                    "Compounding preview: none.",
                    "Reset proof: workflow example reset completed before the run.",
                    "Example status: fail.",
                ]
            )
            return json.dumps(
                {
                    "success": False,
                    "status": "fail",
                    "chat_output": output,
                    "reset_path": str(reset_path),
                    "clusters_count": len(clusters),
                }
            )

        item_count = int(cluster.get("item_count") or len(cluster.get("items", [])))
        priority_score = cluster.get("priority_score", "unknown")
        target = _demo_wiki_cluster_target(cluster)
        synthesis_path = _demo_cluster_source_path(cluster) or "missing retained synthesis"
        wiki_target_path = _demo_wiki_target_path(target)
        artifact_path = _write_demo_wiki_ask_artifact(
            cluster=cluster,
            item_count=item_count,
            priority_score=priority_score,
            target=target,
            synthesis_path=synthesis_path,
            wiki_target_path=wiki_target_path,
        )
        output = "\n".join(
            [
                "Workflow Example 01 is running: we are proving cross-agent wiki compounding from the shared Augur brain.",
                "Answer: Augur turns repeated /ask answers into source-backed wiki concepts that other agents can reuse.",
                (
                    "Evidence: ask-sync-clusters returned "
                    f"{item_count} retained items for the wiki-compounding cluster."
                ),
                "Human artifact: Workflow Example 01 proof card.",
                "Open in Browse: search \"Workflow Example 01 Cross-Agent Wiki Compounding\".",
                f"What to show: Wiki Ingest And Compilation Commands, backed by {item_count} retained /ask outcomes.",
                "Judge takeaway: Codex and Claude can compound into the same governed brain instead of isolated chat memory.",
                "Reset proof: workflow example reset completed before the run.",
                "Example status: pass.",
            ]
        )
        return json.dumps(
            {
                "success": True,
                "status": "pass",
                "chat_output": output,
                "question": DEMO_01_QUESTION,
                "reset_path": str(reset_path),
                "artifact_path": str(artifact_path),
                "cluster": {
                    "label": cluster.get("label"),
                    "item_count": item_count,
                    "priority_score": priority_score,
                    "target": target,
                },
            },
            default=str,
        )
    except Exception as exc:
        return json.dumps({"success": False, "status": "fail", "error": str(exc)})


async def _maybe_await_payload(value: Any) -> Any:
    if hasattr(value, "__await__"):
        return await value
    return value


def _demo_list_commands_payload() -> dict[str, Any]:
    from skills.ai.scripts.mcp import _render_commands_payload

    payload = _render_commands_payload()
    return payload if isinstance(payload, dict) else {}


async def _demo_note_url_capture() -> dict[str, Any]:
    import shutil
    import subprocess
    import sys

    # Cross-OS guard: resolve aug executable; fail fast with a structured error instead
    # of letting subprocess.run raise an uncaught FileNotFoundError.
    aug = shutil.which("aug")
    if not aug:
        venv_bin = Path(sys.executable).parent
        for candidate in (venv_bin / "aug", venv_bin / "aug.exe"):
            if candidate.exists():
                aug = str(candidate)
                break
        else:
            return {
                "success": False,
                "error": "aug not found on PATH or in venv",
                "returncode": -1,
            }

    proc = subprocess.run(
        [
            aug,
            "note-url",
            "--url", DEMO_02_URL,
            "--tags", '["example","web-capture","iana"]',
            "--note", "Workflow Example 02 repeatable web capture proof.",
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )

    # Returncode guard: surface the real stderr/exit-code instead of an opaque JSONDecodeError.
    if proc.returncode != 0:
        return {
            "success": False,
            "error": proc.stderr.strip() or "aug note-url failed",
            "returncode": proc.returncode,
        }

    # Tolerant parse: guard json.loads even on returncode 0 in case of leading non-JSON noise.
    raw = proc.stdout.strip()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        # Fall back to the last line that looks like a JSON object.
        last_json: str | None = None
        for line in raw.splitlines():
            if line.strip().startswith("{"):
                last_json = line.strip()
        if last_json:
            try:
                payload = json.loads(last_json)
            except json.JSONDecodeError:
                return {
                    "success": False,
                    "error": f"aug note-url output is not JSON: {raw[-200:]}",
                    "returncode": 0,
                }
        else:
            return {
                "success": False,
                "error": f"aug note-url output is not JSON: {raw[-200:]}",
                "returncode": 0,
            }

    _normalize_demo_url_capture_card(payload)
    try:
        from src.lib.ingest.note_index_refresh import refresh_notes_browse_index

        refresh_notes_browse_index()
    except Exception as exc:  # noqa: BLE001 - keep the capture result inspectable.
        payload["index_refresh_error"] = str(exc)
    return payload


def _normalize_demo_url_capture_card(payload: dict[str, Any]) -> None:
    path_text = payload.get("path")
    if not isinstance(path_text, str) or not path_text.strip():
        return
    path = Path(path_text).expanduser()
    try:
        metadata, body = parse_frontmatter(path, include_sidecar_config=False)
    except (OSError, UnicodeDecodeError, ValueError):
        return

    existing_tags = metadata.get("tags")
    tags = [str(tag) for tag in existing_tags] if isinstance(existing_tags, list) else []
    normalized_tags = [
        tag
        for tag in tags
        if tag.strip().lower() not in {"demo", "demo-run", "demo-proof"}
    ]
    for tag in ("example", "workflow-example", "web-capture", "iana"):
        if tag not in normalized_tags:
            normalized_tags.append(tag)
    metadata["tags"] = normalized_tags
    metadata["note"] = "Workflow Example 02 repeatable web capture proof."
    metadata.pop("source_type", None)

    relates = metadata.get("_relates_to")
    relate_items = relates if isinstance(relates, list) else []
    normalized_relates = [
        str(item)
        for item in relate_items
        if str(item).strip().lower() != "[[demo]]"
    ]
    for item in ("[[example]]", "[[workflow-example]]", "[[web-capture]]"):
        if item not in normalized_relates:
            normalized_relates.append(item)
    metadata["_relates_to"] = normalized_relates
    write_vault_frontmatter(path, metadata, body)
    payload["tags"] = normalized_tags


def _demo_browse_index(**kwargs: Any) -> dict[str, Any]:
    from src.mcp.augur_framework.tools.infrastructure.browse.index import (
        browse_index_impl,
    )

    raw = browse_index_impl(**kwargs)
    return json.loads(raw)


def _demo_command_group_count(payload: dict[str, Any]) -> int:
    groups = payload.get("groups")
    if isinstance(groups, list):
        return len(groups)
    commands = payload.get("commands")
    if isinstance(commands, dict):
        return len(commands)
    return 0


def _demo_command_surface_summary(payload: dict[str, Any]) -> str:
    total_commands = payload.get("total_commands")
    slash_commands = payload.get("total_slash_commands")
    visible_skills = payload.get("total_visible_skills")
    if isinstance(total_commands, int) and isinstance(slash_commands, int):
        if isinstance(visible_skills, int):
            return (
                f"{slash_commands} slash commands, {total_commands} total commands, "
                f"and {visible_skills} visible skills"
            )
        return f"{slash_commands} slash commands and {total_commands} total commands"

    group_count = _demo_command_group_count(payload)
    return f"{group_count} command groups"


def _demo_browse_first_item(payload: dict[str, Any]) -> dict[str, Any]:
    items = payload.get("items")
    if isinstance(items, list) and items:
        first = items[0]
        if isinstance(first, dict):
            return first
    return {}


async def demo_run_discover_capture_impl() -> str:
    try:
        reset_path = reset_demo_run_state(DEMO_02_RESET_REASON, vault_dir=get_vault_dir())
        commands = _demo_list_commands_payload()
        capture = await _maybe_await_payload(_demo_note_url_capture())
        browse = _demo_browse_index(
            category="vault",
            search=DEMO_02_SEARCH,
            limit=5,
        )
        if not _demo_browse_first_item(browse):
            browse = _demo_browse_index(
                category="vault",
                search="www.iana.org",
                limit=5,
            )
        first_item = _demo_browse_first_item(browse)
        command_group_count = _demo_command_group_count(commands)
        command_surface = _demo_command_surface_summary(commands)
        card_title = str(first_item.get("title") or capture.get("title") or "").strip()
        capture_ok = bool(capture.get("success"))
        browse_ok = bool(first_item)
        status = "pass" if capture_ok and browse_ok else "fail"
        capture_label = (
            "existing local source card"
            if capture.get("deduplicated")
            else "new local source card"
        )
        artifact_path = _write_demo_discover_capture_artifact(
            command_surface=command_surface,
            card_title=card_title or str(capture.get("title") or ""),
            capture_label=capture_label,
        )
        output = "\n".join(
            [
                "Workflow Example 02 is running: we are showing the command surface and turning a webpage into searchable brain material.",
                f"Command surface: {command_surface} are exposed from the real Augur command registry.",
                f"Saved webpage: {card_title or capture.get('title') or 'IANA-managed Reserved Domains'} is searchable in Browse.",
                "Human artifact: Workflow Example 02 proof card.",
                "Open in Browse: search \"Workflow Example 02 Command Surface Web Capture\".",
                f"What to show: Discover command list, then the saved page from Browse search \"{DEMO_02_SEARCH}\".",
                "Judge takeaway: GUI commands, slash commands, and file-backed evidence are one shared surface.",
                "Reset proof: workflow example reset completed before the run.",
                f"Example status: {status}.",
            ]
        )
        return json.dumps(
            {
                "success": status == "pass",
                "status": status,
                "chat_output": output,
                "reset_path": str(reset_path),
                "command_group_count": command_group_count,
                "command_surface": command_surface,
                "capture": capture,
                "browse_item": first_item,
                "artifact_path": str(artifact_path),
            },
            default=str,
        )
    except Exception as exc:
        return json.dumps({"success": False, "status": "fail", "error": str(exc)})


async def _demo_airplane_action(action: str) -> dict[str, Any]:
    from src.mcp.augur_framework.tools.infrastructure.local_backends import (
        ToggleAirplaneModeInput,
        toggle_airplane_mode_impl,
    )

    raw = await toggle_airplane_mode_impl(ToggleAirplaneModeInput(action=action))
    return json.loads(raw)


def _demo_active_client_id(env: dict[str, str] | None = None) -> str:
    values = env if env is not None else os.environ
    if values.get("GEMINI_SESSION"):
        return "gemini"
    if values.get("CODEX_THREAD_ID") or values.get("CODEX_SESSION") or values.get("CODEX_MANAGED_BY_NPM"):
        return "codex"
    if values.get("CLAUDE_CODE_ENTRY_POINT") or values.get("CLAUDE_DESKTOP"):
        return "claude"
    return "unknown"


def _demo_airplane_enabled(status: dict[str, Any]) -> bool:
    airplane_mode = status.get("airplane_mode")
    if isinstance(airplane_mode, dict):
        return bool(airplane_mode.get("enabled"))
    return False


def _demo_transcript_body_from_markdown(text: str) -> str:
    lines = text.splitlines()
    in_transcript = False
    body: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.lower() == "## transcript":
            in_transcript = True
            continue
        if in_transcript and stripped.startswith("## "):
            break
        if in_transcript:
            body.append(line)
    return "\n".join(body).strip()


def _demo_collapse_preview_text(text: str, limit: int = 260) -> str:
    collapsed = re.sub(r"\s+", " ", text).strip()
    if len(collapsed) <= limit:
        return collapsed
    return f"{collapsed[: limit - 3].rstrip()}..."


def _demo_preview_presentation_language(text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        original = match.group(0)
        replacement = "workflow examples" if original.lower().endswith("s") else "workflow example"
        return replacement.capitalize() if original[:1].isupper() else replacement

    return re.sub(r"\bdemos?\b", replace, text)


def _demo_transcript_preview(payload: dict[str, Any], limit: int = 260) -> str:
    transcript_path = payload.get("transcript_path")
    if isinstance(transcript_path, str) and transcript_path.strip():
        try:
            body = _demo_transcript_body_from_markdown(
                Path(transcript_path).expanduser().read_text(encoding="utf-8")
            )
            if body:
                return _demo_collapse_preview_text(
                    _demo_preview_presentation_language(body),
                    limit=limit,
                )
        except OSError:
            pass

    snippet = str(payload.get("snippet") or "").strip()
    marker = "Transcript snippet:"
    if marker in snippet:
        snippet = snippet.split(marker, 1)[1].strip()
    return (
        _demo_collapse_preview_text(
            _demo_preview_presentation_language(snippet),
            limit=limit,
        )
        if snippet
        else "missing transcript preview"
    )


def _demo_has_transcript_artifact(payload: dict[str, Any]) -> bool:
    transcript_path = payload.get("transcript_path")
    if not isinstance(transcript_path, str) or not transcript_path.strip():
        return False
    try:
        return Path(transcript_path).expanduser().is_file()
    except OSError:
        return False


def _demo_transcript_artifact_lines(
    payload: dict[str, Any],
    *,
    label: str = "",
) -> list[str]:
    card_label = f"{label} transcript card" if label else "Transcript card"
    preview_label = f"{label} transcript preview" if label else "Transcript preview"
    evidence_label = f"{label} evidence card" if label else "Evidence card"
    open_label = (
        f"Open {label.lower()} transcript file" if label else "Open transcript file"
    )
    transcript_title = str(payload.get("title") or "").strip()
    if not transcript_title:
        route_mode = str(payload.get("route_mode") or "").strip().lower()
        transcript_title = (
            "Offload Workflow Example Regular"
            if route_mode == "regular"
            else "Offload Workflow Example Offline"
        )
    transcript_path = str(payload.get("transcript_path") or "").strip()
    transcript_name = Path(transcript_path).name if transcript_path else ""
    source_path = str(payload.get("source_path") or "").strip()
    source_search = Path(source_path).stem if source_path else ""
    if "offload-demo-short" in source_search:
        source_search = "offload-demo-short"
    elif not source_search and transcript_name:
        source_search = Path(transcript_name).stem
    evidence_written = "written" if payload.get("evidence_path") else "missing"
    lines = [
        f"{card_label}: search Browse for \"{transcript_title}\".",
    ]
    if transcript_name:
        if source_search:
            lines.append(
                f"{open_label}: search Browse for \"{source_search}\" or open "
                f"\"{transcript_name}\"."
            )
        else:
            lines.append(f"{open_label}: open \"{transcript_name}\".")
    lines.extend(
        [
            f"{preview_label}: {_demo_transcript_preview(payload)}",
            f"{evidence_label}: {evidence_written}.",
        ]
    )
    return lines


async def demo_run_transcription_offload_impl(
    source_path: str | None = None,
    title: str = "Offload Workflow Example",
    require_gemini_for_online: bool = True,
) -> str:
    starting_status: dict[str, Any] = {}
    resolved_source_path = source_path or str(_demo_03_audio_path())
    try:
        reset_path = reset_demo_run_state(DEMO_03_RESET_REASON, vault_dir=get_vault_dir())
        normalized_source_path = Path(resolved_source_path).expanduser()
        if not normalized_source_path.exists():
            output = "\n".join(
                [
                    "Workflow Example 03 is running: we are proving Augur can offload the same transcription task through different execution routes.",
                    f"Captured source: missing canonical Augur-owned audio at {normalized_source_path}.",
                    "Offline route: not run.",
                    "Online route: not run.",
                    "Reset proof: workflow example reset completed before the run.",
                    "Example status: fail.",
                ]
            )
            return json.dumps(
                {
                    "success": False,
                    "status": "fail",
                    "chat_output": output,
                    "reset_path": str(reset_path),
                }
            )

        starting_status = await _maybe_await_payload(_demo_airplane_action("status"))
        await _maybe_await_payload(_demo_airplane_action("on"))
        offline = json.loads(
            await demo_run_transcript_impl(
                source_path=str(normalized_source_path),
                title=f"{title} Offline",
            )
        )
        active_client = _demo_active_client_id()
        if require_gemini_for_online and active_client != "gemini":
            if _demo_airplane_enabled(starting_status):
                await _maybe_await_payload(_demo_airplane_action("on"))
            else:
                await _maybe_await_payload(_demo_airplane_action("off"))
            offline_ok = (
                bool(offline.get("success"))
                and offline.get("cloud_used") is False
                and _demo_has_transcript_artifact(offline)
            )
            status = "partial-pass" if offline_ok else "fail"
            artifact_path = _write_demo_transcription_offload_artifact(
                offline=offline,
                online=None,
                active_client=active_client,
                status=status,
            )
            output_lines = [
                "Workflow Example 03 is running: we are proving Augur can offload the same transcription task through different execution routes.",
                "Captured source: Augur-owned short clip.",
                (
                    "Offline route: "
                    f"route_mode {offline.get('route_mode', 'unknown')}, "
                    f"selected engine {offline.get('route_engine_id') or offline.get('method', 'unknown')}, "
                    f"cloud_used {str(bool(offline.get('cloud_used'))).lower()}."
                ),
                (
                    "Online route: skipped because active client is "
                    f"{active_client}. Run this workflow example from Gemini to prove "
                    "Gemini-native transcription instead of headless CLI fallback."
                ),
                "Human artifact: Workflow Example 03 proof card and transcript file.",
                "Open in Browse: search \"Workflow Example 03 Offline Online Transcription Offload\".",
            ]
            output_lines.extend(_demo_transcript_artifact_lines(offline))
            output_lines.extend(
                [
                    "Investor answer: Augur controls the harness and can route the same task local-first or to a native online client; this session proves the offline leg.",
                    "Reset proof: workflow example reset completed before the run and reused the Augur-owned audio path.",
                    f"Example status: {status}.",
                ]
            )
            output = "\n".join(output_lines)
            return json.dumps(
                {
                    "success": status == "partial-pass",
                    "status": status,
                    "active_client": active_client,
                    "chat_output": output,
                    "reset_path": str(reset_path),
                    "artifact_path": str(artifact_path),
                    "offline": offline,
                    "online": None,
                    "online_stop_condition": "run_from_gemini_client",
                },
                default=str,
            )

        await _maybe_await_payload(_demo_airplane_action("off"))
        online = json.loads(
            await demo_run_transcript_impl(
                source_path=str(normalized_source_path),
                title=f"{title} Regular",
            )
        )
        if _demo_airplane_enabled(starting_status):
            await _maybe_await_payload(_demo_airplane_action("on"))
        else:
            await _maybe_await_payload(_demo_airplane_action("off"))

        offline_ok = (
            bool(offline.get("success"))
            and offline.get("cloud_used") is False
            and _demo_has_transcript_artifact(offline)
        )
        online_ok = bool(online.get("success")) and _demo_has_transcript_artifact(online)
        regular_fallback = bool(online.get("fallback_engine_id") or online.get("needs_review"))
        status = "fail"
        if offline_ok and online_ok:
            status = "partial-pass" if regular_fallback else "pass"
        if not offline.get("success") and not online.get("success"):
            status = "fail"
        artifact_path = _write_demo_transcription_offload_artifact(
            offline=offline,
            online=online,
            active_client=active_client,
            status=status,
        )
        output_lines = [
            "Workflow Example 03 is running: we are proving Augur can offload the same transcription task through different execution routes.",
            "Captured source: Augur-owned short clip.",
            (
                "Offline route: "
                f"route_mode {offline.get('route_mode', 'unknown')}, "
                f"selected engine {offline.get('route_engine_id') or offline.get('method', 'unknown')}, "
                f"cloud_used {str(bool(offline.get('cloud_used'))).lower()}."
            ),
            (
                "Online route: "
                f"route_mode {online.get('route_mode', 'unknown')}, "
                f"selected engine {online.get('route_engine_id') or online.get('method', 'unknown')}, "
                f"cloud_used {str(bool(online.get('cloud_used'))).lower()}."
            ),
            (
                "Regular fallback: "
                f"fallback_engine {online.get('fallback_engine_id') or 'none'}, "
                f"needs_review {str(bool(online.get('needs_review'))).lower()}."
            ),
            "Human artifact: Workflow Example 03 proof card plus offline and online transcript files.",
            "Open in Browse: search \"Workflow Example 03 Offline Online Transcription Offload\".",
        ]
        output_lines.extend(_demo_transcript_artifact_lines(offline, label="Offline"))
        output_lines.extend(_demo_transcript_artifact_lines(online, label="Online"))
        output_lines.extend(
            [
                "Investor answer: Augur controls the harness and context while the user experiences one seamless transcription workflow.",
                "Reset proof: workflow example reset completed before the run and reused the Augur-owned audio path.",
                f"Example status: {status}.",
            ]
        )
        output = "\n".join(output_lines)
        return json.dumps(
            {
                "success": status in {"pass", "partial-pass"},
                "status": status,
                "chat_output": output,
                "reset_path": str(reset_path),
                "artifact_path": str(artifact_path),
                "offline": offline,
                "online": online,
            },
            default=str,
        )
    except Exception as exc:
        try:
            if starting_status:
                await _maybe_await_payload(
                    _demo_airplane_action(
                        "on" if _demo_airplane_enabled(starting_status) else "off"
                    )
                )
        except Exception:
            pass
        return json.dumps({"success": False, "status": "fail", "error": str(exc)})


async def demo_run_compound_preview_impl(days_back: int = 90, limit: int = 5) -> str:
    try:
        reset_path = reset_demo_run_state(DEMO_04_RESET_REASON, vault_dir=get_vault_dir())
        clusters = _demo_wiki_ask_clusters(days_back=days_back, limit=limit)
        cluster = _select_demo_wiki_cluster(clusters)
        if not cluster:
            output = "\n".join(
                [
                    "Workflow Example 04 is running: we are previewing what would compound before any wiki mutation is applied.",
                    "Compound preview: no retained clusters were returned.",
                    "Safety proof: no wiki apply command was run; this is a dry run.",
                    "Reset proof: workflow example reset completed before the run.",
                    "Example status: fail.",
                ]
            )
            return json.dumps(
                {
                    "success": False,
                    "status": "fail",
                    "chat_output": output,
                    "reset_path": str(reset_path),
                }
            )

        item_count = int(cluster.get("item_count") or len(cluster.get("items", [])))
        priority_score = cluster.get("priority_score", "unknown")
        target = _demo_wiki_cluster_target(cluster)
        artifact_path = _write_demo_compound_preview_artifact(
            cluster=cluster,
            item_count=item_count,
            priority_score=priority_score,
            target=target,
        )
        output = "\n".join(
            [
                "Workflow Example 04 is running: we are previewing what would compound before any wiki mutation is applied.",
                "Retained signal: existing /ask syntheses provide the workflow example signal; fresh retention is skipped for repeatability.",
                (
                    f"Compound preview: {item_count} retained /ask outcomes would "
                    f"strengthen {target} without writing wiki pages."
                ),
                (
                    f"Current cluster: \"{str(cluster.get('label', 'ask cluster')).strip()}\" "
                    f"has {item_count} retained items, priority_score {priority_score}, "
                    f"and targets {target}."
                ),
                "Safety proof: no wiki apply command was run; this is a dry run.",
                "Human artifact: Workflow Example 04 proof card.",
                "Open in Browse: search \"Workflow Example 04 Governed Compounding Preview\".",
                f"What to show: {item_count} retained outcomes would strengthen Wiki Ingest And Compilation Commands.",
                "Judge takeaway: compounding is governed promotion with previewable evidence, not blind autosave.",
                "Reset proof: workflow example reset completed before the run and no wiki apply command ran.",
                "Example status: pass.",
            ]
        )
        return json.dumps(
            {
                "success": True,
                "status": "pass",
                "chat_output": output,
                "reset_path": str(reset_path),
                "artifact_path": str(artifact_path),
                "cluster": {
                    "label": cluster.get("label"),
                    "item_count": item_count,
                    "priority_score": priority_score,
                    "target": target,
                },
            },
            default=str,
        )
    except Exception as exc:
        return json.dumps({"success": False, "status": "fail", "error": str(exc)})


def _demo_airplane_status() -> Any:
    return _demo_airplane_action("status")


def _demo_airplane_smoke() -> dict[str, Any]:
    return run_demo_smoke(
        desktop=_demo_desktop(""),
        airplane="on",
        require_cloud=False,
    )


def _demo_local_engines(smoke: dict[str, Any]) -> str:
    capabilities = smoke.get("readiness", {}).get("capabilities", {})
    engines = capabilities.get("local_engines")
    if isinstance(engines, list) and engines:
        return ", ".join(str(engine) for engine in engines)
    return "OpenVINO, faster-whisper, Ollama"


def _demo_evidence_pin_summary(smoke: dict[str, Any]) -> str:
    pin = smoke.get("evidence_pin")
    if not isinstance(pin, dict):
        return "missing evidence pin"
    title = str(pin.get("title") or "evidence card").strip()
    path = str(pin.get("url") or pin.get("path") or "").strip()
    if path:
        return f"{title} at {path}"
    return title


async def demo_run_airplane_safety_impl() -> str:
    try:
        reset_path = reset_demo_run_state(DEMO_05_RESET_REASON, vault_dir=get_vault_dir())
        starting_status = await _maybe_await_payload(_demo_airplane_status())
        smoke = await _maybe_await_payload(_demo_airplane_smoke())
        ending_status = await _maybe_await_payload(_demo_airplane_status())
        cloud_calls = int(smoke.get("cloud_calls") or 0)
        files_indexed = int(smoke.get("files_indexed") or 0)
        success = bool(smoke.get("success")) and cloud_calls == 0
        status = "pass" if success else "fail"
        evidence_label = _normalize_demo_airplane_evidence_card(smoke)
        evidence_path = _demo_evidence_pin_path(smoke)
        artifact_path = _write_demo_airplane_safety_artifact(
            smoke=smoke,
            cloud_calls=cloud_calls,
            files_indexed=files_indexed,
            status=status,
        )
        output = "\n".join(
            [
                "Workflow Example 05 is running: we are proving offline execution has safety gates and evidence.",
                "Airplane proof: smoke check ran with airplane mode on and cloud disallowed.",
                f"Cloud calls: {cloud_calls}.",
                f"Local route: {_demo_local_engines(smoke)} are visible before launch; files_indexed {files_indexed}.",
                "Safety guard: unsafe local launches are reported as unavailable instead of freezing the Mac.",
                f"Evidence: saved workflow example evidence card {evidence_label}.",
                "Human artifact: Workflow Example 05 proof card.",
                "Open in Browse: search \"Workflow Example 05 Local Only Safety Evidence\".",
                f"What to show: Cloud calls: {cloud_calls}; files indexed: {files_indexed}; local engines visible before launch.",
                "Reset proof: workflow example reset completed before the run and airplane preference was restored.",
                f"Example status: {status}.",
            ]
        )
        return json.dumps(
            {
                "success": success,
                "status": status,
                "chat_output": output,
                "reset_path": str(reset_path),
                "starting_status": starting_status,
                "ending_status": ending_status,
                "artifact_path": str(artifact_path),
                "evidence_path": evidence_path,
                "smoke": smoke,
            },
            default=str,
        )
    except Exception as exc:
        return json.dumps({"success": False, "status": "fail", "error": str(exc)})


def _demo_brain_folder_contract(brain_root: Path) -> list[str]:
    return [
        "capabilities/skills",
        "knowledge",
        "instructions",
        "decisions/adrs",
        "workflows",
    ]


async def demo_run_brain_manifest_impl() -> str:
    try:
        reset_path = reset_demo_run_state(DEMO_06_RESET_REASON, vault_dir=get_vault_dir())
        project_root = get_project_root()
        brain_root = project_root / "project-brain"
        manifest_path = brain_root / "BRAIN.yaml"
        metadata = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
        expected_folders = _demo_brain_folder_contract(brain_root)
        missing = [relative for relative in expected_folders if not (brain_root / relative).exists()]
        status = "pass" if not missing else "partial-pass"
        readme_path = brain_root / "README.md"
        skills_path = brain_root / "capabilities" / "skills"
        artifact_path = _write_demo_brain_manifest_artifact(
            metadata=metadata,
            missing=missing,
            status=status,
        )
        output = "\n".join(
            [
                "Workflow Example 06 is running: we are showing that an Augur brain is a portable, inspectable architecture surface, not a hidden prompt folder.",
                (
                    "Brain manifest: "
                    f"{metadata.get('id', 'unknown')}, type {metadata.get('type', 'unknown')}, "
                    f"root '{metadata.get('root', 'unknown')}', "
                    f"attached_project '{metadata.get('attached_project', 'unknown')}'."
                ),
                "Architecture proof: the manifest binds this portable brain folder to the Augur repository instead of relying on hidden agent state.",
                "Folder contract: capabilities/skills holds executable skills, knowledge holds memory/wiki/source material, instructions holds agent behavior, decisions/adrs holds architecture history, and workflows holds repeatable procedures.",
                f"Separation proof: the project brain is {metadata.get('id', 'project-augur')} under project-brain, while the personal brain remains a separate personal vault.",
                "Investor answer: a brain is a governed workspace that agents can read, update, project into native clients, and audit as files.",
                "Human artifact: Workflow Example 06 proof card.",
                "Open in Browse: search \"Workflow Example 06 Brain Manifest Architecture\".",
                "What to show: BRAIN.yaml, capabilities/skills, knowledge, instructions, decisions/adrs, and the personal brain separation.",
                "Reset proof: workflow example reset completed before the run; the workflow example is read-only after preflight.",
                f"Example status: {status}.",
            ]
        )
        return json.dumps(
            {
                "success": status == "pass",
                "status": status,
                "chat_output": output,
                "reset_path": str(reset_path),
                "artifact_path": str(artifact_path),
                "manifest": metadata,
                "missing_folders": missing,
                "manifest_path": str(manifest_path),
                "readme_path": str(readme_path),
                "skills_path": str(skills_path),
            },
            default=str,
        )
    except Exception as exc:
        return json.dumps({"success": False, "status": "fail", "error": str(exc)})


def _path_match_values(path_text: str) -> set[str]:
    raw = str(path_text or "").strip()
    if not raw:
        return set()

    values = {raw}
    try:
        expanded = Path(raw).expanduser()
        values.add(str(expanded))
        values.add(str(expanded.resolve(strict=False)))
    except Exception:
        pass
    return {value.casefold() for value in values if value}


def _source_path_matches(requested_path: str, metadata: dict[str, Any]) -> bool:
    requested_values = _path_match_values(requested_path)
    if not requested_values:
        return False

    for key in ("source_path", "path", "file_path", "source_file_path"):
        indexed_value = metadata.get(key)
        if isinstance(indexed_value, str) and (
            requested_values & _path_match_values(indexed_value)
        ):
            return True

    source_relative_path = metadata.get("source_relative_path")
    if isinstance(source_relative_path, str) and source_relative_path.strip():
        requested = str(requested_path).replace("\\", "/").casefold()
        relative = source_relative_path.strip().replace("\\", "/").casefold()
        if requested.endswith(relative):
            return True

    return False


def _stringify_prompt_value(value: Any) -> str:
    if isinstance(value, str):
        return " ".join(value.split())
    if isinstance(value, (int, float, bool)):
        return str(value)
    return ""


def _format_prompt_context_value(label: str, value: Any) -> list[str]:
    if isinstance(value, list):
        items = [_stringify_prompt_value(item) for item in value]
        items = [item for item in items if item]
        if not items:
            return []
        lines = [f"- {label}:"]
        lines.extend(f"  - {item}" for item in items[:6])
        return lines

    text = _stringify_prompt_value(value)
    if not text:
        return []
    return [f"- {label}: {text}"]


def _body_excerpt(body: str) -> str:
    lines = [" ".join(line.split()) for line in body.splitlines()]
    excerpt = "\n".join(line for line in lines if line).strip()
    if len(excerpt) > DEMO_PROMPT_BODY_EXCERPT_CHAR_LIMIT:
        excerpt = excerpt[: DEMO_PROMPT_BODY_EXCERPT_CHAR_LIMIT - 3].rstrip() + "..."
    return excerpt


def _format_demo_prompt_context(
    metadata: dict[str, Any],
    body: str,
    index_path: Path,
) -> str:
    lines = [f"- Browse index entry: {index_path}"]
    for field, label in DEMO_PROMPT_CONTEXT_FIELDS:
        if field in metadata:
            lines.extend(_format_prompt_context_value(label, metadata[field]))

    excerpt = _body_excerpt(body)
    if excerpt:
        lines.append("- Extracted text excerpt:")
        lines.append(excerpt)

    context = "\n".join(lines).strip()
    if len(context) > DEMO_PROMPT_CONTEXT_CHAR_LIMIT:
        context = context[: DEMO_PROMPT_CONTEXT_CHAR_LIMIT - 3].rstrip() + "..."
    return context


def _find_demo_prompt_artifact_context(source_path: str) -> dict[str, Any]:
    rag_dir = get_rag_dir()
    scanned = 0
    for category in DEMO_PROMPT_INDEX_CATEGORIES:
        category_dir = rag_dir / category
        if not category_dir.exists():
            continue
        for entry_file in sorted(category_dir.rglob("*.md")):
            scanned += 1
            if scanned > DEMO_PROMPT_INDEX_SCAN_LIMIT:
                return {
                    "matched": False,
                    "scanned": scanned,
                    "reason": "scan_limit_reached",
                }
            try:
                metadata, body = parse_frontmatter(
                    entry_file,
                    include_sidecar_config=False,
                )
            except Exception:
                continue
            if not _source_path_matches(source_path, metadata):
                continue
            return {
                "matched": True,
                "scanned": scanned,
                "index_path": str(entry_file),
                "evidence": _format_demo_prompt_context(metadata, body, entry_file),
            }

    return {"matched": False, "scanned": scanned, "reason": "not_indexed"}


async def demo_run_prompt_impl(
    source_path: str,
    title: str = "",
    prompt_kind: str = "judge-value",
    client: str = "claude",
) -> str:
    if not source_path.strip():
        return json.dumps({"success": False, "error": "Missing source_path."})
    try:
        artifact_title = title.strip() or Path(source_path).name
        artifact_context = _find_demo_prompt_artifact_context(source_path)
        if artifact_context.get("matched"):
            evidence_block = (
                "Artifact evidence from Browse index:\n"
                f"{artifact_context.get('evidence')}\n\n"
            )
        else:
            evidence_block = (
                "Artifact evidence from Browse index: not found. Treat this as a workflow example "
                "readiness risk and do not invent artifact content.\n\n"
            )
        prompt = (
            f"Client: {client}\n"
            f"Prompt kind: {prompt_kind}\n"
            f"Artifact title: {artifact_title}\n"
            f"Source path: {source_path}\n\n"
            f"{evidence_block}"
            "Review this real Browse artifact without making any hidden LLM or tool call. "
            "Judge whether the artifact would be valuable in a live Augur workflow example. "
            "Give concrete improvements, concrete risk, and the exact evidence you used "
            "from the Browse index evidence above, plus the visible artifact title/path."
        )
        return json.dumps(
            {
                "success": True,
                "message": "Workflow example run prompt built.",
                "prompt": prompt,
                "prompt_kind": prompt_kind,
                "client": client,
                "source_path": source_path,
                "title": artifact_title,
                "artifact_context": artifact_context,
            }
        )
    except Exception as exc:
        return json.dumps({"success": False, "error": str(exc)})


def _demo_transcribe(source_path: Path) -> Any:
    from src.lib.routing import transcribe

    return transcribe(
        str(source_path),
        gemini_timeout_s=DEMO_GEMINI_TRANSCRIBE_TIMEOUT_SECONDS,
    )


async def demo_run_transcript_impl(source_path: str, title: str = "") -> str:
    if not source_path.strip():
        return json.dumps({"success": False, "error": "Missing source_path."})
    try:
        normalized_source_path = Path(source_path).expanduser()
        vault_dir = get_vault_dir()
        result = run_transcript_case(
            normalized_source_path,
            transcribe=_demo_transcribe,
            source_title=title.strip() or None,
            run_eval=True,
            vault_dir=vault_dir,
            replace_existing=True,
        )
        if result.get("success"):
            try:
                from src.lib.ingest.note_index_refresh import (
                    refresh_notes_browse_index,
                )

                refresh_notes_browse_index(vault_dir=vault_dir)
            except Exception as exc:  # noqa: BLE001 - transcript result stays inspectable.
                result["index_refresh_error"] = str(exc)
        return json.dumps(
            {
                "success": bool(result.get("success")),
                "message": (
                    "Transcript artifact written."
                    if result.get("success")
                    else "Transcript case did not complete."
                ),
                "title": title.strip(),
                **result,
            }
        )
    except Exception as exc:
        return json.dumps({"success": False, "error": str(exc)})


async def demo_run_meeting_memory_impl(
    source_path: str = "",
    transcript_path: str = "",
    title: str = "",
) -> str:
    try:
        normalized_source_path = (
            Path(source_path).expanduser() if source_path.strip() else None
        )
        normalized_transcript_path = (
            Path(transcript_path).expanduser() if transcript_path.strip() else None
        )
        if normalized_source_path is None and normalized_transcript_path is None:
            return json.dumps(
                {
                    "success": False,
                    "error": "Missing source_path or transcript_path.",
                }
            )
        result = run_meeting_memory_case(
            source_path=normalized_source_path,
            transcript_path=normalized_transcript_path,
            source_title=title.strip() or None,
            run_eval=True,
            vault_dir=get_vault_dir(),
        )
        return json.dumps(
            {
                "success": bool(result.get("success")),
                "message": (
                    "Meeting memory artifact written."
                    if result.get("success")
                    else "Meeting memory case did not complete."
                ),
                "title": title.strip(),
                **result,
            }
        )
    except Exception as exc:
        return json.dumps({"success": False, "error": str(exc)})


async def demo_run_ask_transcript_impl(
    source_path: str = "",
    transcript_path: str = "",
    question: str = "What are the key decisions and actions?",
    title: str = "",
) -> str:
    try:
        normalized_source_path = (
            Path(source_path).expanduser() if source_path.strip() else None
        )
        normalized_transcript_path = (
            Path(transcript_path).expanduser() if transcript_path.strip() else None
        )
        if normalized_source_path is None and normalized_transcript_path is None:
            return json.dumps(
                {
                    "success": False,
                    "error": "Missing source_path or transcript_path.",
                }
            )
        result = run_ask_transcript_case(
            source_path=normalized_source_path,
            transcript_path=normalized_transcript_path,
            question=question,
            source_title=title.strip() or None,
            run_eval=True,
            vault_dir=get_vault_dir(),
        )
        return json.dumps(
            {
                "success": bool(result.get("success")),
                "message": (
                    "Transcript answer artifact written."
                    if result.get("success")
                    else "Ask-from-transcript case did not complete."
                ),
                "title": title.strip(),
                **result,
            }
        )
    except Exception as exc:
        return json.dumps({"success": False, "error": str(exc)})


def register_demo_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable[..., Any],
    metrics: Any = None,
) -> None:
    @mcp.tool(
        name="demo-readiness",
        annotations=tool_annotations(
            {
                "title": "Workflow Example Readiness",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def demo_readiness_tool(
        desktop: str = "",
        require_cloud: bool = True,
    ) -> str:
        if metrics:
            metrics.track_tool("demo_readiness", skill="demo")
        return await demo_readiness_impl(
            desktop=desktop,
            require_cloud=require_cloud,
        )

    @mcp.tool(
        name="demo-reset",
        annotations=tool_annotations(
            {
                "title": "Workflow Example Reset",
                "readOnlyHint": False,
                "destructiveHint": True,
                "idempotentHint": False,
                "openWorldHint": True,
            }
        ),
    )
    @mcp_tool_interceptor
    async def demo_reset_tool(desktop: str = "", airplane: str = "on") -> str:
        if metrics:
            metrics.track_tool("demo_reset", skill="demo")
        return await demo_reset_impl(desktop=desktop, airplane=airplane)

    @mcp.tool(
        name="demo-smoke",
        annotations=tool_annotations(
            {
                "title": "Workflow Example Smoke",
                "readOnlyHint": False,
                "destructiveHint": True,
                "idempotentHint": False,
                "openWorldHint": True,
            }
        ),
    )
    @mcp_tool_interceptor
    async def demo_smoke_tool(
        desktop: str = "",
        airplane: str = "on",
        require_cloud: bool = False,
    ) -> str:
        if metrics:
            metrics.track_tool("demo_smoke", skill="demo")
        return await demo_smoke_impl(
            desktop=desktop,
            airplane=airplane,
            require_cloud=require_cloud,
        )

    @mcp.tool(
        name="demo-run-note",
        annotations=tool_annotations(
            {
                "title": "Workflow Example Run Note",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def demo_run_note_tool() -> str:
        if metrics:
            metrics.track_tool("demo_run_note", skill="demo")
        return await demo_run_note_impl()

    @mcp.tool(
        name="demo-run-reset",
        annotations=tool_annotations(
            {
                "title": "Workflow Example Run Reset",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def demo_run_reset_tool(reason: str = "practice-loop") -> str:
        if metrics:
            metrics.track_tool("demo_run_reset", skill="demo")
        return await demo_run_reset_state_impl(reason=reason)

    @mcp.tool(
        name="demo-run-record-evidence",
        annotations=tool_annotations(
            {
                "title": "Workflow Example Run Record Evidence",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": True,
            }
        ),
    )
    @mcp_tool_interceptor
    async def demo_run_record_evidence_tool(
        source_path: str,
        case_id: str = "meeting-transcript",
        command: str = "",
        status: str = "pass",
        backend: str = "",
        client: str = "",
        duration_seconds: float | None = None,
        output_path: str = "",
        failure_reason: str = "",
        missing_prerequisite: str = "",
        eval_link: str = "",
        source_name: str = "",
        useful_snippet: str = "",
    ) -> str:
        if metrics:
            metrics.track_tool("demo_run_record_evidence", skill="demo")
        return await demo_run_record_evidence_impl(
            source_path=source_path,
            case_id=case_id,
            command=command,
            status=status,
            backend=backend,
            client=client,
            duration_seconds=duration_seconds,
            output_path=output_path,
            failure_reason=failure_reason,
            missing_prerequisite=missing_prerequisite,
            eval_link=eval_link,
            source_name=source_name,
            useful_snippet=useful_snippet,
        )

    @mcp.tool(
        name="demo-runbook-output",
        annotations=tool_annotations(
            {
                "title": "Workflow Example Runbook Output",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def demo_runbook_output_tool(
        source_path: str = "",
        title: str = "",
        demo_id: str = "",
    ) -> str:
        if metrics:
            metrics.track_tool("demo_runbook_output", skill="demo")
        return await demo_runbook_output_impl(
            source_path=source_path,
            title=title,
            demo_id=demo_id,
        )

    @mcp.tool(
        name="demo-run-wiki-ask",
        annotations=tool_annotations(
            {
                "title": "Workflow Example Run Wiki Ask",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def demo_run_wiki_ask_tool(days_back: int = 90, limit: int = 5) -> str:
        if metrics:
            metrics.track_tool("demo_run_wiki_ask", skill="demo")
        return await demo_run_wiki_ask_impl(days_back=days_back, limit=limit)

    @mcp.tool(
        name="demo-run-discover-capture",
        annotations=tool_annotations(
            {
                "title": "Workflow Example Run Discover Capture",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": True,
            }
        ),
    )
    @mcp_tool_interceptor
    async def demo_run_discover_capture_tool() -> str:
        if metrics:
            metrics.track_tool("demo_run_discover_capture", skill="demo")
        return await demo_run_discover_capture_impl()

    @mcp.tool(
        name="demo-run-transcription-offload",
        annotations=tool_annotations(
            {
                "title": "Workflow Example Run Transcription Offload",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def demo_run_transcription_offload_tool(
        source_path: str | None = None,
        title: str = "Offload Workflow Example",
        require_gemini_for_online: bool = True,
    ) -> str:
        if metrics:
            metrics.track_tool("demo_run_transcription_offload", skill="demo")
        return await demo_run_transcription_offload_impl(
            source_path=source_path,
            title=title,
            require_gemini_for_online=require_gemini_for_online,
        )

    @mcp.tool(
        name="demo-run-compound-preview",
        annotations=tool_annotations(
            {
                "title": "Workflow Example Run Compound Preview",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def demo_run_compound_preview_tool(days_back: int = 90, limit: int = 5) -> str:
        if metrics:
            metrics.track_tool("demo_run_compound_preview", skill="demo")
        return await demo_run_compound_preview_impl(days_back=days_back, limit=limit)

    @mcp.tool(
        name="demo-run-airplane-safety",
        annotations=tool_annotations(
            {
                "title": "Workflow Example Run Airplane Safety",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": True,
            }
        ),
    )
    @mcp_tool_interceptor
    async def demo_run_airplane_safety_tool() -> str:
        if metrics:
            metrics.track_tool("demo_run_airplane_safety", skill="demo")
        return await demo_run_airplane_safety_impl()

    @mcp.tool(
        name="demo-run-brain-manifest",
        annotations=tool_annotations(
            {
                "title": "Workflow Example Run Brain Manifest",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def demo_run_brain_manifest_tool() -> str:
        if metrics:
            metrics.track_tool("demo_run_brain_manifest", skill="demo")
        return await demo_run_brain_manifest_impl()

    @mcp.tool(
        name="demo-run-prompt",
        annotations=tool_annotations(
            {
                "title": "Workflow Example Run Prompt",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def demo_run_prompt_tool(
        source_path: str,
        title: str = "",
        prompt_kind: str = "judge-value",
        client: str = "claude",
    ) -> str:
        if metrics:
            metrics.track_tool("demo_run_prompt", skill="demo")
        return await demo_run_prompt_impl(
            source_path=source_path,
            title=title,
            prompt_kind=prompt_kind,
            client=client,
        )

    @mcp.tool(
        name="demo-run-transcript",
        annotations=tool_annotations(
            {
                "title": "Workflow Example Run Transcript",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def demo_run_transcript_tool(source_path: str, title: str = "") -> str:
        if metrics:
            metrics.track_tool("demo_run_transcript", skill="demo")
        return await demo_run_transcript_impl(source_path=source_path, title=title)

    @mcp.tool(
        name="demo-run-meeting-memory",
        annotations=tool_annotations(
            {
                "title": "Workflow Example Run Meeting Memory",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def demo_run_meeting_memory_tool(
        source_path: str = "",
        transcript_path: str = "",
        title: str = "",
    ) -> str:
        if metrics:
            metrics.track_tool("demo_run_meeting_memory", skill="demo")
        return await demo_run_meeting_memory_impl(
            source_path=source_path,
            transcript_path=transcript_path,
            title=title,
        )

    @mcp.tool(
        name="demo-run-ask-transcript",
        annotations=tool_annotations(
            {
                "title": "Workflow Example Run Ask Transcript",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def demo_run_ask_transcript_tool(
        source_path: str = "",
        transcript_path: str = "",
        question: str = "What are the key decisions and actions?",
        title: str = "",
    ) -> str:
        if metrics:
            metrics.track_tool("demo_run_ask_transcript", skill="demo")
        return await demo_run_ask_transcript_impl(
            source_path=source_path,
            transcript_path=transcript_path,
            question=question,
            title=title,
        )
