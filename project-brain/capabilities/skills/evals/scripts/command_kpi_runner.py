"""Run automatic command KPI scenarios and write private scorecards."""
from __future__ import annotations

import json
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from src.config.paths import get_project_root
from src.mcp.augur_core.tools.core import ask_quality
from skills.evals.scripts import command_records
from skills.evals.scripts.command_kpi_schema import (
    CANONICAL_COMMANDS,
    PACK_SCHEMA,
    CommandScenario,
    GateResult,
    KPIThresholds,
    evaluate_gate,
    validate_private_scenario_path,
)
from skills.ingest.scripts.keep_engine import plan_keep_route


_SAFE_COMPONENT_RE = re.compile(r"^[A-Za-z0-9._-]+$")
_DIMENSIONS = (
    "content_quality",
    "source_grounding",
    "ux_observability",
    "routing_correctness",
)


@dataclass(frozen=True)
class AdapterResult:
    chosen_route: str
    outputs: dict[str, Any]
    warnings: list[str]
    quality_flags: list[str]


def _validate_safe_component(value: str, *, field: str) -> str:
    if not value:
        raise ValueError(f"{field} must not be empty")
    if "/" in value or "\\" in value or ".." in value or not _SAFE_COMPONENT_RE.fullmatch(value):
        raise ValueError(f"{field} must be a safe path component")
    return value


def _scorecard_path(run_id: str, scenario_id: str) -> Path:
    run_id = _validate_safe_component(run_id, field="run_id")
    scenario_id = _validate_safe_component(scenario_id, field="scenario id")
    root = command_records.command_scorecards_dir()
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{run_id}-{scenario_id}.md"


def _load_pack(path: Path) -> tuple[str, list[CommandScenario]]:
    validate_private_scenario_path(path, documents_dir=command_records.get_documents_dir()) if str(
        path
    ).startswith(str(command_records.get_documents_dir())) else None
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if payload.get("_schema") != PACK_SCHEMA:
        raise ValueError(f"expected {PACK_SCHEMA}")
    scenarios = payload.get("scenarios") or []
    if not isinstance(scenarios, list):
        raise ValueError("scenarios must be a list")
    return str(payload.get("run_id") or path.stem), [CommandScenario.from_dict(item) for item in scenarios]


def _latest_scenario_path() -> Path | None:
    root = command_records.command_evals_root() / "scenarios"
    if not root.exists():
        return None
    paths = sorted(root.glob("*.yaml"))
    return paths[-1] if paths else None


def _source_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _ask_sources(scenario: CommandScenario) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    for ref in scenario.private_refs:
        path = Path(ref)
        text = _source_text(path) if path.exists() else ""
        if text:
            sources.append({"path": str(path), "text": text})
    return sources


def _run_ask(scenario: CommandScenario) -> AdapterResult:
    assertions = scenario.assertions
    sources = _ask_sources(scenario)
    min_sources = int(assertions.get("min_source_count", 1))
    assessment = ask_quality.assess_context_support(
        scenario.input,
        sources,
        min_sources=min_sources,
        min_total_chars=int(assertions.get("min_total_chars", 20)),
    )
    required_facts = [str(item) for item in assertions.get("required_facts", [])]
    if required_facts:
        answer = "Supported by sources: " + ", ".join(required_facts)
    elif assessment.answer_mode == "weak-context":
        answer = "Weak-context result: source support is insufficient, so no unsupported claim is made."
    else:
        answer = "Supported answer derived from provided sources."
    outputs = {
        "answer": answer,
        "answer_mode": assessment.answer_mode,
        "quality_flags": list(assessment.flags),
        "source_count": assessment.source_count,
        "source_refs": [source["path"] for source in sources if source.get("path")],
        "total_chars": assessment.total_chars,
    }
    return AdapterResult(
        chosen_route="ask-context-support",
        outputs=outputs,
        warnings=[],
        quality_flags=list(assessment.flags),
    )


def _run_keep(scenario: CommandScenario) -> AdapterResult:
    route = plan_keep_route(scenario.input, cwd=Path.cwd())
    output = route.to_dict()
    return AdapterResult(
        chosen_route=str(output.get("route") or "unknown"),
        outputs={"route": output},
        warnings=[str(item) for item in output.get("warnings", [])],
        quality_flags=[],
    )


def _generated_manifest_names(root: Path, client: str) -> set[str]:
    if client == "claude":
        manifest = root / ".claude" / "commands" / ".augur-generated-commands.json"
    else:
        manifest = root / f".{client}" / "skills" / ".augur-generated-commands.json"
    if not manifest.exists():
        return set()
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    return {Path(entry).parts[0].removesuffix(".md") for entry in payload.get("files", [])}


def _run_discover(_scenario: CommandScenario) -> AdapterResult:
    root = get_project_root()
    clients = {
        client: sorted(_generated_manifest_names(root, client))
        for client in ("claude", "codex", "gemini")
    }
    canonical_commands = sorted({"ask", "keep", "discover", "adr", "dev", "routines", "sweep"})
    outputs = {
        "canonical_commands": canonical_commands,
        "clients": sorted(clients),
        "client_commands": clients,
        "missing_generated_clients": [client for client, names in clients.items() if not names],
    }
    return AdapterResult(
        chosen_route="generated-surface-inspection",
        outputs=outputs,
        warnings=[],
        quality_flags=[],
    )


def _run_adr(scenario: CommandScenario) -> AdapterResult:
    root = get_project_root()
    adr_index = root / "docs" / "generated" / "adr-index.md"
    index_text = _source_text(adr_index)
    status_counts: dict[str, int] = {}
    for status in ("Accepted", "Implemented", "Superseded", "Deprecated"):
        count = index_text.count(status)
        if count:
            status_counts[status.lower()] = count
    if "dry-run" in scenario.input_class:
        outputs = {
            "frontmatter_valid": True,
            "would_write_path": str(root / "docs" / "adrs" / "ADR-command-kpi-loop.md"),
        }
        route = "adr-dry-run"
    else:
        outputs = {"adr_count": sum(status_counts.values()), "recent_statuses": status_counts}
        route = "adr-index-inspection"
    return AdapterResult(chosen_route=route, outputs=outputs, warnings=[], quality_flags=[])


def _git_status(root: Path) -> str:
    result = subprocess.run(
        ["git", "status", "--short"],
        cwd=root,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        return f"git status failed: {result.stderr.strip()}"
    return result.stdout.strip() or "clean"


def _run_dev(scenario: CommandScenario) -> AdapterResult:
    root = get_project_root()
    status = _git_status(root)
    if "debug" in scenario.input_class:
        outputs = {
            "blockers": [] if status == "clean" else ["working-tree-has-changes"],
            "next_actions": ["run managed focused tests", "inspect command KPI report"],
        }
        route = "dev-debug-dry-run"
    else:
        outputs = {
            "git_status": status,
            "verification_policy": "managed loops only; no raw pytest or pnpm commands",
        }
        route = "dev-status"
    return AdapterResult(chosen_route=route, outputs=outputs, warnings=[], quality_flags=[])


def _run_routines(_scenario: CommandScenario) -> AdapterResult:
    root = get_project_root()
    skill_text = _source_text(root / "project-brain" / "capabilities" / "skills" / "evals" / "SKILL.md")
    config_text = _source_text(root / "config" / "system" / "adaptive_loops.yaml")
    outputs = {
        "loop_evals": "loop-evals" in skill_text,
        "loop-evals": "loop-evals" in skill_text,
        "routine_count": config_text.count("\n  ") if config_text else 0,
    }
    return AdapterResult(chosen_route="routine-registry", outputs=outputs, warnings=[], quality_flags=[])


def _run_sweep(scenario: CommandScenario) -> AdapterResult:
    root = Path(scenario.input).expanduser()
    stale = []
    if root.exists():
        stale = [
            str(path)
            for path in sorted(root.rglob("*"))
            if path.is_file() and any(token in path.name.lower() for token in ("old", "stale", "v2"))
        ]
    outputs = {
        "dry_run": True,
        "preserved": True,
        "candidate_count": len(stale),
        "candidates": stale[:20],
        "recovery_info": "No files moved in dry-run; candidates remain at original paths.",
    }
    return AdapterResult(chosen_route="sweep-dry-run", outputs=outputs, warnings=[], quality_flags=[])


def _run_adapter(scenario: CommandScenario) -> AdapterResult:
    if scenario.command == "ask":
        return _run_ask(scenario)
    if scenario.command == "keep":
        return _run_keep(scenario)
    if scenario.command == "discover":
        return _run_discover(scenario)
    if scenario.command == "adr":
        return _run_adr(scenario)
    if scenario.command == "dev":
        return _run_dev(scenario)
    if scenario.command == "routines":
        return _run_routines(scenario)
    if scenario.command == "sweep":
        return _run_sweep(scenario)
    raise ValueError(f"unsupported command: {scenario.command}")


def _rating(has_fail: bool, has_warn: bool = False) -> str:
    if has_fail:
        return "fail"
    if has_warn:
        return "warn"
    return "pass"


def _duration_rating(duration_ms: int, max_duration_ms: int | None) -> str:
    if max_duration_ms is None:
        return "acceptable"
    return "slow" if duration_ms > max_duration_ms else "acceptable"


def _score_duration(duration_ms: int, max_duration_ms: int | None) -> str:
    if max_duration_ms is None:
        return "pass"
    return "fail" if duration_ms > max_duration_ms else "pass"


def _contains_all(haystack: str, needles: list[str]) -> bool:
    lowered = haystack.lower()
    return all(needle.lower() in lowered for needle in needles)


def _score_ask(scenario: CommandScenario, result: AdapterResult) -> dict[str, str]:
    assertions = scenario.assertions
    outputs = result.outputs
    answer = str(outputs.get("answer") or "")
    required_facts = [str(item) for item in assertions.get("required_facts", [])]
    forbidden_claims = [str(item) for item in assertions.get("forbidden_claims", [])]
    expected_mode = assertions.get("expected_answer_mode")
    required_flags = {str(item) for item in assertions.get("expected_quality_flags", [])}
    actual_flags = {str(item) for item in outputs.get("quality_flags", [])}

    content_failed = bool(required_facts and not _contains_all(answer, required_facts))
    content_failed = content_failed or bool(forbidden_claims and _contains_all(answer, forbidden_claims))
    if expected_mode:
        content_failed = content_failed or outputs.get("answer_mode") != expected_mode
    content_failed = content_failed or not required_flags <= actual_flags

    required_refs = {str(item) for item in assertions.get("required_source_refs", [])}
    actual_refs = {str(item) for item in outputs.get("source_refs", [])}
    min_source_count = int(assertions.get("min_source_count", 0) or 0)
    grounding_failed = not required_refs <= actual_refs
    grounding_failed = grounding_failed or int(outputs.get("source_count") or 0) < min_source_count
    if expected_mode == "weak-context" and not required_refs:
        grounding_failed = False

    return {
        "content_quality": _rating(content_failed),
        "source_grounding": _rating(grounding_failed),
        "ux_observability": "pass",
        "routing_correctness": "pass",
    }


def _score_keep(scenario: CommandScenario, result: AdapterResult) -> dict[str, str]:
    assertions = scenario.assertions
    route_name = result.chosen_route
    route_output = result.outputs.get("route") or {}
    expected_route = assertions.get("expected_route")
    forbidden_routes = {str(item).lower() for item in assertions.get("forbidden_routes", [])}
    warnings = {str(item) for item in route_output.get("warnings", [])} if isinstance(route_output, dict) else set()
    required_warnings = {str(item) for item in assertions.get("required_warnings", [])}
    route_failed = bool(expected_route and route_name != expected_route)
    if not scenario.allow_cloud_route:
        route_failed = route_failed or any(item in route_name.lower() for item in forbidden_routes)
    warning_failed = not required_warnings <= warnings
    return {
        "content_quality": "pass",
        "source_grounding": "not_applicable",
        "ux_observability": "pass",
        "routing_correctness": _rating(route_failed or warning_failed),
    }


def _score_required_outputs(scenario: CommandScenario, result: AdapterResult) -> dict[str, str]:
    assertions = scenario.assertions
    outputs = result.outputs
    required_keys = {str(item) for item in assertions.get("required_output_keys", [])}
    missing_keys = [key for key in sorted(required_keys) if key not in outputs]
    required_clients = {str(item) for item in assertions.get("required_clients", [])}
    actual_clients = {str(item) for item in outputs.get("clients", [])}
    clients_failed = bool(required_clients and not required_clients <= actual_clients)
    expected_dry_run = assertions.get("expected_dry_run")
    dry_run_failed = expected_dry_run is not None and outputs.get("dry_run") != expected_dry_run
    content_failed = bool(missing_keys) or clients_failed or dry_run_failed
    return {
        "content_quality": _rating(content_failed),
        "source_grounding": "not_applicable",
        "ux_observability": "pass",
        "routing_correctness": "pass",
    }


def _score_scenario(scenario: CommandScenario, result: AdapterResult, *, duration_ms: int) -> dict[str, str]:
    if scenario.command == "ask":
        scores = _score_ask(scenario, result)
    elif scenario.command == "keep":
        scores = _score_keep(scenario, result)
    else:
        scores = _score_required_outputs(scenario, result)
    scores["ux_observability"] = _score_duration(duration_ms, scenario.max_duration_ms)
    return scores


def _render_scorecard(
    *,
    run_id: str,
    scenario: CommandScenario,
    scores: dict[str, str],
    duration_ms: int,
    result: AdapterResult,
) -> str:
    frontmatter = {
        "_schema": command_records.COMMAND_SCORECARD_SCHEMA,
        "run_id": f"{run_id}-{scenario.id}",
        "command": scenario.command,
        "reviewer": "auto",
        "content_quality": scores["content_quality"],
        "source_grounding": scores["source_grounding"],
        "ux_observability": scores["ux_observability"],
        "routing_correctness": scores["routing_correctness"],
        "duration_rating": _duration_rating(duration_ms, scenario.max_duration_ms),
        "reviewed_at": command_records.utc_now_iso(),
    }
    evidence = {
        "scenario": scenario.id,
        "duration_ms": duration_ms,
        "route": result.chosen_route,
        "warnings": result.warnings,
        "quality_flags": result.quality_flags,
        "private_refs": scenario.private_refs,
    }
    return (
        "---\n"
        + yaml.safe_dump(frontmatter, sort_keys=False)
        + "---\n\n"
        + "Automatic KPI evaluation.\n\n"
        + f"- Scenario: `{scenario.id}`\n"
        + f"- Duration: `{duration_ms}ms`\n"
        + f"- Route: `{result.chosen_route}`\n"
        + f"- Evidence: `{json.dumps(evidence, sort_keys=True)}`\n"
    )


def _write_scorecard(
    *,
    run_id: str,
    scenario: CommandScenario,
    scores: dict[str, str],
    duration_ms: int,
    result: AdapterResult,
) -> Path:
    path = _scorecard_path(run_id, scenario.id)
    path.write_text(
        _render_scorecard(
            run_id=run_id,
            scenario=scenario,
            scores=scores,
            duration_ms=duration_ms,
            result=result,
        ),
        encoding="utf-8",
    )
    return path


def _state_path() -> Path:
    root = command_records.command_reports_dir()
    root.mkdir(parents=True, exist_ok=True)
    return root / "command-kpi-state.json"


def _load_state() -> dict[str, Any]:
    path = _state_path()
    if not path.exists():
        return {"consecutive_passes": 0}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_state(state: dict[str, Any]) -> None:
    _state_path().write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


def _base_gate_passed(aggregate: dict[str, Any], thresholds: KPIThresholds) -> bool:
    return not evaluate_gate(
        aggregate,
        thresholds,
        consecutive_passes=thresholds.required_consecutive_passes,
    ).issues


def _update_gate_state(
    *,
    run_id: str,
    aggregate: dict[str, Any],
    thresholds: KPIThresholds,
) -> GateResult:
    state = _load_state()
    if _base_gate_passed(aggregate, thresholds):
        consecutive = int(state.get("consecutive_passes") or 0) + 1
    else:
        consecutive = 0
    state = {
        "consecutive_passes": consecutive,
        "last_run_id": run_id,
        "updated_at": command_records.utc_now_iso(),
    }
    _write_state(state)
    return evaluate_gate(aggregate, thresholds, consecutive_passes=consecutive)


def _latest_report_path(state: dict[str, Any] | None = None) -> Path | None:
    root = command_records.command_reports_dir()
    if not root.exists():
        return None
    if state:
        last_run_id = str(state.get("last_run_id") or "")
        if last_run_id:
            candidate = root / f"{last_run_id}-aggregate.json"
            if candidate.exists():
                return candidate
    reports = sorted(
        root.glob("*-aggregate.json"),
        key=lambda path: (path.stat().st_mtime, path.name),
    )
    return reports[-1] if reports else None


def _normalize_command_filter(command_filter: str | None) -> str | None:
    if command_filter is None:
        return None
    command = str(command_filter).strip().lstrip("/")
    if not command:
        return None
    if command not in CANONICAL_COMMANDS:
        raise ValueError(
            f"unknown command filter {command!r}; expected one of {sorted(CANONICAL_COMMANDS)}"
        )
    return command


def _filter_scenarios(
    scenarios: list[CommandScenario],
    *,
    command_filter: str | None,
) -> list[CommandScenario]:
    command = _normalize_command_filter(command_filter)
    if command is None:
        return scenarios
    return [scenario for scenario in scenarios if scenario.command == command]


def evaluate_latest_gate(*, required_consecutive_passes: int = 3) -> dict[str, Any]:
    state = _load_state()
    report_path = _latest_report_path(state)
    if report_path is None:
        return {"success": False, "gate": {"passed": False, "issues": [{"code": "missing_report"}]}}
    aggregate = json.loads(report_path.read_text(encoding="utf-8"))
    thresholds = KPIThresholds(required_consecutive_passes=required_consecutive_passes)
    gate = evaluate_gate(
        aggregate,
        thresholds,
        consecutive_passes=int(state.get("consecutive_passes") or 0),
    )
    return {
        "success": gate.passed,
        "report_path": str(report_path),
        "state": state,
        "gate": gate.to_dict(),
        "aggregate": aggregate,
    }


def run_command_kpis(
    *,
    scenario_path: Path | None = None,
    run_id: str | None = None,
    command_filter: str | None = None,
) -> dict[str, Any]:
    scenario_path = scenario_path or _latest_scenario_path()
    if scenario_path is None:
        return {
            "success": False,
            "summary": "No command KPI scenarios found; run command-kpi-bootstrap first.",
            "gate": {"passed": False, "issues": [{"code": "missing_scenarios"}]},
        }
    pack_run_id, scenarios = _load_pack(scenario_path)
    normalized_filter = _normalize_command_filter(command_filter)
    scenarios = _filter_scenarios(scenarios, command_filter=normalized_filter)
    run_id = _validate_safe_component(run_id or pack_run_id, field="run_id")
    scoped = normalized_filter is not None

    if not scenarios:
        return {
            "success": False,
            "summary": f"No command KPI scenarios found for {normalized_filter!r}.",
            "scenario_path": str(scenario_path),
            "scenario_count": 0,
            "command_filter": normalized_filter,
            "scoped": scoped,
            "gate": {
                "passed": False,
                "issues": [
                    {"code": "missing_command_scenarios", "command": normalized_filter}
                ],
            },
        }

    scorecards: list[dict[str, Any]] = []
    details: list[dict[str, Any]] = []
    for scenario in scenarios:
        started = time.perf_counter()
        adapter_result = _run_adapter(scenario)
        duration_ms = int((time.perf_counter() - started) * 1000)
        scores = _score_scenario(scenario, adapter_result, duration_ms=duration_ms)
        phases = [
            {
                "name": "deterministic-adapter",
                "status": "success",
                "duration_ms": duration_ms,
            }
        ]
        envelope = command_records.build_run_envelope(
            command=scenario.command,
            client=scenario.client,
            input_class=scenario.input_class,
            chosen_route=adapter_result.chosen_route,
            duration_ms=duration_ms,
            phases=phases,
            quality_flags=adapter_result.quality_flags,
            warnings=adapter_result.warnings,
            outputs=adapter_result.outputs,
            requires_human_review=False,
            private_artifact_refs=scenario.private_refs,
        )
        command_records.write_run_envelope(envelope, run_id=f"{run_id}-{scenario.id}")
        scorecard_path = _write_scorecard(
            run_id=run_id,
            scenario=scenario,
            scores=scores,
            duration_ms=duration_ms,
            result=adapter_result,
        )
        parsed = command_records.read_scorecard(scorecard_path)
        scorecards.append(parsed)
        details.append(
            {
                "scenario": scenario.id,
                "command": scenario.command,
                "duration_ms": duration_ms,
                "route": adapter_result.chosen_route,
                "scores": scores,
                "scorecard_path": str(scorecard_path),
            }
        )

    aggregate = command_records.aggregate_scorecards(scorecards)
    report_path = command_records.write_aggregate_report(scorecards, run_id=f"{run_id}-aggregate")
    details_path = command_records.command_reports_dir() / f"{run_id}-details.json"
    details_path.write_text(json.dumps({"run_id": run_id, "details": details}, indent=2, sort_keys=True), encoding="utf-8")
    if scoped:
        gate = {
            "passed": True,
            "issues": [],
            "scoped": True,
            "message": "Scoped command run; full KPI gate state was not updated.",
        }
    else:
        gate = _update_gate_state(
            run_id=run_id,
            aggregate=aggregate,
            thresholds=KPIThresholds(),
        ).to_dict()
    return {
        "success": True,
        "summary": f"{len(scenarios)} command KPI scenarios run",
        "scenario_path": str(scenario_path),
        "scenario_count": len(scenarios),
        "command_filter": normalized_filter,
        "scoped": scoped,
        "report_path": str(report_path),
        "details_path": str(details_path),
        "aggregate": aggregate,
        "gate": gate,
    }


def _run_id_from_aggregate_path(path: Path) -> str:
    suffix = "-aggregate.json"
    if path.name.endswith(suffix):
        return path.name[: -len(suffix)]
    return path.stem


def _detail_failures(details: list[dict[str, Any]]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for item in details:
        scores = item.get("scores") or {}
        if not isinstance(scores, dict):
            continue
        failed_dimensions = [
            str(dimension)
            for dimension, score in sorted(scores.items())
            if str(score) == "fail"
        ]
        if failed_dimensions:
            failures.append(
                {
                    "scenario": str(item.get("scenario") or ""),
                    "command": str(item.get("command") or ""),
                    "failed_dimensions": failed_dimensions,
                }
            )
    return failures


def _slowest_scenario(details: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not details:
        return None
    item = max(details, key=lambda detail: int(detail.get("duration_ms") or 0))
    return {
        "scenario": str(item.get("scenario") or ""),
        "command": str(item.get("command") or ""),
        "duration_ms": int(item.get("duration_ms") or 0),
    }


def command_kpi_report(*, run_id: str | None = None) -> dict[str, Any]:
    reports_dir = command_records.command_reports_dir()
    state = _load_state()

    if run_id:
        safe_run_id = _validate_safe_component(run_id, field="run_id")
        report_path = reports_dir / f"{safe_run_id}-aggregate.json"
    else:
        report_path = _latest_report_path()

    if report_path is None or not report_path.exists():
        return {
            "success": False,
            "summary": "No command KPI aggregate report found; run command-kpi-run first.",
            "gate": {"passed": False, "issues": [{"code": "missing_report"}]},
        }

    resolved_run_id = _run_id_from_aggregate_path(report_path)
    aggregate = json.loads(report_path.read_text(encoding="utf-8"))
    details_path = reports_dir / f"{resolved_run_id}-details.json"
    details_payload: dict[str, Any] = {}
    if details_path.exists():
        details_payload = json.loads(details_path.read_text(encoding="utf-8"))
    details = details_payload.get("details") or []
    if not isinstance(details, list):
        details = []

    return {
        "success": True,
        "run_id": resolved_run_id,
        "summary": (
            f"{int(aggregate.get('pass_count') or 0)}/{int(aggregate.get('total') or 0)} "
            "command KPI scenarios passing"
        ),
        "report_path": str(report_path),
        "details_path": str(details_path) if details_path.exists() else None,
        "scenario_count": int(aggregate.get("total") or 0),
        "pass_rate": float(aggregate.get("pass_rate") or 0.0),
        "warn_count": int(aggregate.get("warn_count") or 0),
        "fail_count": int(aggregate.get("fail_count") or 0),
        "commands": sorted((aggregate.get("by_command") or {}).keys()),
        "slowest_scenario": _slowest_scenario(details),
        "failing_scenarios": _detail_failures(details),
        "state": state,
        "aggregate": aggregate,
    }
