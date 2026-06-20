"""eval_ops -- CLI dispatch + the /loop-evals auto-loop entry (ADR-742).

Two execution paths reach this module:

1. **CLI** (`aug eval <verb>`): `register_subcommands` in `scripts/mcp/__init__.py`
   parses argv and calls `run_cli(verb, args)`. Sub-verbs: replay, export, stats,
   capture-status, capture-consent, import-longmemeval, seed-baseline.

2. **Auto-loop** (`/loop-evals`): the adaptive engine discovers `scan()` /
   `fix()` (the `scan-fix` ops protocol). `scan()` runs a nightly replay against
   the captured + external corpora, computes a delta vs. baseline, and surfaces
   metric drops > threshold as issues. `fix()` is report-only -- the loop result
   stays GREEN in v1 regardless of alert severity (CI-blocking is a v2 evolution,
   mirroring the ADR-741 report-only-then-blocking lineage).

No model calls anywhere in this module.
"""

from __future__ import annotations

import importlib.util as _augur_importlib_util
import sys as _augur_sys
from pathlib import Path as _AugurPath

_augur_bootstrap_start = _AugurPath(__file__).resolve()
for _augur_bootstrap_parent in (
    _augur_bootstrap_start.parent,
    *_augur_bootstrap_start.parents,
):
    _augur_bootstrap_path = (
        _augur_bootstrap_parent / "daemon" / "scripts" / "bootstrap_paths.py"
    )
    if _augur_bootstrap_path.is_file():
        break
else:
    raise RuntimeError(
        f"Unable to locate shared skill bootstrap from {_augur_bootstrap_start}"
    )

_augur_bootstrap_spec = _augur_importlib_util.spec_from_file_location(
    "_augur_shared_bootstrap_paths", _augur_bootstrap_path
)
if _augur_bootstrap_spec is None or _augur_bootstrap_spec.loader is None:
    raise RuntimeError(
        f"Unable to load shared skill bootstrap from {_augur_bootstrap_path}"
    )
_augur_bootstrap_module = _augur_importlib_util.module_from_spec(_augur_bootstrap_spec)
_augur_sys.modules[_augur_bootstrap_spec.name] = _augur_bootstrap_module
_augur_bootstrap_spec.loader.exec_module(_augur_bootstrap_module)
_augur_bootstrap_module.ensure_project_paths(__file__)
_augur_scripts_dir = str(_AugurPath(__file__).resolve().parent)
if _augur_scripts_dir not in _augur_sys.path:
    _augur_sys.path.insert(0, _augur_scripts_dir)

import json
import logging
import zipfile
from pathlib import Path
from typing import Any

import yaml

import capture
import command_records
import longmemeval
import records
import replay as replay_mod
import report as report_mod
import seed_baseline as seed_mod

from skills.evals.scripts import demo_case_eval, demo_case_records
from src.lib.ops_protocol import OpsContext, ScanResult, report_only_fix

logger = logging.getLogger("evals.eval_ops")

name = "loop-evals"

DIFFICULTY_SPEC = {
    0: "Surface check -- confirm captured queries + judgments exist",
    1: "Run replay against captured + external corpora, compute delta vs. baseline",
    2: "Replay with bootstrap CI on the summary",
}


# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------


def _skill_config() -> dict[str, Any]:
    """Load the skill's config.yaml (loop alert thresholds + bootstrap settings)."""
    config_path = Path(__file__).resolve().parent.parent / "config.yaml"
    if not config_path.is_file():
        return {}
    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        logger.warning("config.yaml parse failed: %s", exc)
        return {}
    return data if isinstance(data, dict) else {}


def _alert_thresholds() -> dict[str, float]:
    cfg = _skill_config()
    raw = cfg.get("alert_thresholds", {})
    out: dict[str, float] = {}
    for key in ("P_at_5", "R_at_5", "MRR", "nDCG_at_10"):
        try:
            out[key] = float(raw.get(key, 5.0))
        except (TypeError, ValueError):
            out[key] = 5.0
    return out


# --------------------------------------------------------------------------
# Auto-loop: scan / fix (scan-fix ops protocol)
# --------------------------------------------------------------------------


def scan(ctx: OpsContext) -> ScanResult:
    """Nightly replay -- surfaces metric drops > threshold as issues. Report-only.

    The loop result stays GREEN regardless of alert severity (v1). Alerts are
    `warning` severity at most so the loop never goes red; CI-blocking is a v2
    evolution.
    """
    queries = records.read_query_records(include_external=True)
    judgments = records.read_judgments(include_external=True)

    if not queries:
        return ScanResult(
            issues=[],
            summary="No captured eval queries yet -- run `aug eval seed-baseline`.",
            severity="info",
            health="verified",
        )

    labeled = sum(
        1 for q in queries if judgments.get(q.get("id", ""), {}).get("relevant_doc_ids")
    )

    # d0: surface check only -- confirm corpus + judgments exist, no replay.
    if ctx.difficulty < 1:
        return ScanResult(
            issues=[],
            summary=(
                f"{len(queries)} captured queries, {labeled} with judgments "
                f"(d0 surface only)"
            ),
            severity="info",
            health="verified",
        )

    with_ci = ctx.difficulty >= 2
    try:
        result = replay_mod.replay(corpus="all", with_ci=with_ci)
    except Exception as exc:  # noqa: BLE001 - a replay crash is a scanner defect, not red loop
        return ScanResult(
            issues=[{"error": f"replay raised: {exc}"}],
            summary=f"replay failed: {exc}",
            severity="warning",
            health="degraded",
        )

    written = report_mod.write_report(
        result, thresholds=_alert_thresholds(), compare_baseline=True
    )
    alerts = written.get("alerts", [])
    counts = result.get("counts", {})

    issues = [
        {
            "metric": a["metric"],
            "baseline": a["baseline"],
            "current": a["current"],
            "drop_points": a["drop_points"],
            "threshold": a["threshold"],
            "severity": a["severity"],
            "report": written["summary_path"],
        }
        for a in alerts
    ]

    summary = (
        f"replay {written['run_id']}: {counts.get('scored', 0)} scored, "
        f"{counts.get('unlabeled', 0)} unlabeled, {len(alerts)} alert(s)"
    )
    # Alerts are at most `warning` so the loop stays green (report-only v1).
    severity = "warning" if alerts else "info"
    return ScanResult(
        issues=issues,
        summary=summary,
        severity=severity,
        health="verified",
        items_scanned=counts.get("total_queries", 0),
    )


def fix(ctx: OpsContext, issues: list[dict]) -> Any:
    """Report-only fix -- writes the alert report artifact, never mutates retrieval."""
    return report_only_fix(ctx, "loop-evals-latest.json", issues, noun="eval alert")


# --------------------------------------------------------------------------
# Demo-case evals
# --------------------------------------------------------------------------


def run_demo_case_eval(
    case_id: str,
    source_title: str,
    evidence_path: Path,
    duration_ms: int | None,
    *,
    source_path: Path | None = None,
) -> dict[str, Any]:
    """Score a real demo evidence card and write a private eval record.

    This is deterministic local scoring only: it reads the markdown evidence,
    calls the demo-case scorer, and persists the score envelope under the private
    documents dir.
    """
    normalized_evidence_path = Path(evidence_path)
    output_text = _demo_case_score_text(
        normalized_evidence_path.read_text(encoding="utf-8")
    )
    score = demo_case_eval.score_demo_output(
        case_id=case_id,
        source_title=source_title,
        output_text=output_text,
        duration_ms=duration_ms,
    )
    record = demo_case_records.write_demo_case_eval_record(
        case_id=case_id,
        evidence_path=normalized_evidence_path,
        source_path=Path(source_path)
        if source_path is not None
        else normalized_evidence_path,
        scores=score.scores,
        findings=score.findings,
    )
    return {
        "status": score.pass_status,
        "run_id": record.run_id,
        "record_path": str(record.path),
        "scores": score.scores,
        "findings": score.findings,
    }


def _demo_case_score_text(evidence_markdown: str) -> str:
    """Return the user-value portion of a demo evidence card for scoring."""
    lines = evidence_markdown.splitlines()
    for index, line in enumerate(lines):
        if line.strip().lower() != "## useful snippet":
            continue
        end = len(lines)
        for candidate in range(index + 1, len(lines)):
            if lines[candidate].strip().startswith("## "):
                end = candidate
                break
        return "\n".join(lines[index + 1 : end]).strip()
    if _is_demo_evidence_markdown(evidence_markdown):
        return ""
    return evidence_markdown


def _is_demo_evidence_markdown(markdown: str) -> bool:
    lowered = markdown.lower()
    return (
        "# demo evidence:" in lowered
        or "type: demo-evidence" in lowered
        or "demo_case_id:" in lowered
    )


# --------------------------------------------------------------------------
# CLI verb implementations
# --------------------------------------------------------------------------


def cmd_replay(args: Any) -> dict[str, Any]:
    """`aug eval replay [--config X] [--corpus C] [--since T]`."""
    config_path = getattr(args, "config", None)
    corpus = getattr(args, "corpus", None) or "all"
    since = getattr(args, "since", None)
    with_ci = bool(getattr(args, "with_ci", False))
    result = replay_mod.replay(
        config_path=config_path, corpus=corpus, since=since, with_ci=with_ci
    )
    written = report_mod.write_report(
        result, thresholds=_alert_thresholds(), compare_baseline=True
    )
    overall = result.get("aggregates", {}).get("overall", {})
    scores = {
        f"{m}_mean": overall.get(m, {}).get("mean")
        for m in (
            "P_at_1",
            "P_at_5",
            "P_at_10",
            "R_at_1",
            "R_at_5",
            "R_at_10",
            "MRR",
            "nDCG_at_10",
        )
        if m in overall
    }
    return {
        "run_id": written["run_id"],
        "summary_path": written["summary_path"],
        "raw_path": written["raw_path"],
        "manifest_path": written["manifest_path"],
        "counts": result.get("counts", {}),
        "index_drift": result.get("index_drift", False),
        "alerts": written.get("alerts", []),
        "scores": scores,
    }


def cmd_stats(args: Any) -> dict[str, Any]:
    """`aug eval stats [--run-id R]` -- parsed numbers for a run (default: latest)."""
    run_id = getattr(args, "run_id", None)
    return report_mod.parse_summary_numbers(run_id)


def cmd_capture_status(_args: Any) -> dict[str, Any]:
    """`aug eval capture-status` -- capture mode / consent / counts."""
    return capture.capture_status()


def cmd_capture_consent(_args: Any) -> dict[str, Any]:
    """`aug eval capture-consent` -- write consent.md to opt in to capture."""
    path = capture.write_consent()
    return {
        "consent_path": str(path),
        "consent": capture.has_consent(),
        "message": (
            "Consent recorded. Capture proceeds when AUGUR_CONTRIBUTOR_MODE=1. "
            "Delete this file to opt out."
        ),
    }


def cmd_import_longmemeval(args: Any) -> dict[str, Any]:
    """`aug eval import-longmemeval --path P --corpus-id C`."""
    path = getattr(args, "path", None)
    corpus_id = getattr(args, "corpus_id", None)
    if not path:
        return {"error": "--path is required"}
    if not corpus_id:
        # Default the corpus id to the input file stem.
        corpus_id = Path(path).stem
    return longmemeval.import_corpus(Path(path), corpus_id)


def cmd_seed_baseline(_args: Any) -> dict[str, Any]:
    """`aug eval seed-baseline` -- run the seed query set through retrieval once."""
    return seed_mod.seed_baseline()


def cmd_export(args: Any) -> dict[str, Any]:
    """`aug eval export [--since T] [--until T]` -- bundle a date range into a zip."""
    since = getattr(args, "since", None)
    until = getattr(args, "until", None)
    return export_range(since=since, until=until)


def _json_arg(value: str | None, default: Any) -> Any:
    if value is None or value == "":
        return default
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON for value: {exc}") from exc
    return parsed


def _json_list_of_objects_arg(flag: str, value: str | None) -> list[dict[str, Any]]:
    try:
        parsed = _json_arg(value, [])
    except ValueError as exc:
        raise ValueError(str(exc).replace("value", flag, 1)) from exc
    if not isinstance(parsed, list) or not all(
        isinstance(item, dict) for item in parsed
    ):
        raise ValueError(f"{flag} must be a list of objects")
    return parsed


def _json_list_of_strings_arg(flag: str, value: str | None) -> list[str]:
    try:
        parsed = _json_arg(value, [])
    except ValueError as exc:
        raise ValueError(str(exc).replace("value", flag, 1)) from exc
    if not isinstance(parsed, list) or not all(
        isinstance(item, str) for item in parsed
    ):
        raise ValueError(f"{flag} must be a list of strings")
    return parsed


def _json_object_arg(flag: str, value: str | None) -> dict[str, Any]:
    try:
        parsed = _json_arg(value, {})
    except ValueError as exc:
        raise ValueError(str(exc).replace("value", flag, 1)) from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"{flag} must be an object")
    return parsed


def cmd_command_record(args: Any) -> dict[str, Any]:
    envelope = command_records.build_run_envelope(
        command=getattr(args, "command", ""),
        client=getattr(args, "client", ""),
        input_class=getattr(args, "input_class", ""),
        chosen_route=getattr(args, "chosen_route", ""),
        duration_ms=int(getattr(args, "duration_ms", 0) or 0),
        phases=_json_list_of_objects_arg("--phases", getattr(args, "phases", "[]")),
        quality_flags=_json_list_of_strings_arg(
            "--quality-flags",
            getattr(args, "quality_flags", "[]"),
        ),
        warnings=_json_list_of_strings_arg(
            "--warnings",
            getattr(args, "warnings", "[]"),
        ),
        outputs=_json_object_arg("--outputs", getattr(args, "outputs", "{}")),
    )
    path = command_records.write_run_envelope(
        envelope,
        run_id=getattr(args, "run_id", None),
    )
    return {
        "success": True,
        "path": str(path),
        "run_id": getattr(args, "run_id", None),
        "command": envelope["command"],
        "client": envelope["client"],
    }


def cmd_command_aggregate(args: Any) -> dict[str, Any]:
    scorecards = command_records.read_scorecards()
    aggregate = command_records.aggregate_scorecards(scorecards)
    path = command_records.write_aggregate_report(
        scorecards,
        run_id=getattr(args, "run_id", None),
    )
    return {"success": True, "report_path": str(path), "aggregate": aggregate}


def cmd_command_template(_args: Any) -> dict[str, Any]:
    template_path = (
        Path(__file__).resolve().parent.parent
        / "references"
        / "command-scorecard-template.md"
    )
    return {"success": True, "template_path": str(template_path)}


def cmd_command_kpi_bootstrap(args: Any) -> dict[str, Any]:
    import command_kpi_bootstrap

    run_id = getattr(args, "run_id", None) or command_records.utc_now_iso().replace(
        ":", "-"
    )
    return command_kpi_bootstrap.bootstrap_private_scenarios(run_id=run_id)


def cmd_command_kpi_run(args: Any) -> dict[str, Any]:
    import command_kpi_runner

    scenario_path = getattr(args, "scenario_path", None)
    return command_kpi_runner.run_command_kpis(
        scenario_path=Path(scenario_path) if scenario_path else None,
        run_id=getattr(args, "run_id", None),
        command_filter=getattr(args, "command", None),
    )


def cmd_command_kpi_gate(args: Any) -> dict[str, Any]:
    import command_kpi_runner

    return command_kpi_runner.evaluate_latest_gate(
        required_consecutive_passes=int(
            getattr(args, "required_consecutive_passes", 3) or 3
        )
    )


def cmd_command_kpi_report(args: Any) -> dict[str, Any]:
    import command_kpi_runner

    return command_kpi_runner.command_kpi_report(run_id=getattr(args, "run_id", None))


# --------------------------------------------------------------------------
# Export -- shared by the CLI verb and the eval-export MCP tool
# --------------------------------------------------------------------------


def export_range(since: str | None = None, until: str | None = None) -> dict[str, Any]:
    """Bundle a date range of queries + judgments into a portable zip.

    Output: get_documents_dir()/evals/exports/<run-id>.zip. The zip holds the
    matching `eval.query.v1` records and every `eval.judgment.v1` file whose
    query id appears in that range -- a portable, `cat`-able archive.
    """
    queries = records.read_query_records(
        since=since, until=until, include_external=True
    )
    judgments = records.read_judgments(include_external=True)

    run_id = report_mod.make_run_id(records.augur_commit())
    exports = records.exports_dir()
    exports.mkdir(parents=True, exist_ok=True)
    zip_path = exports / f"{run_id}.zip"

    query_ids = {q.get("id") for q in queries if q.get("id")}
    included_judgments = {qid: judgments[qid] for qid in query_ids if qid in judgments}

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        # Queries as a single JSONL.
        query_lines = "\n".join(
            json.dumps(q, ensure_ascii=False, sort_keys=True, default=str)
            for q in queries
        )
        zf.writestr("queries.jsonl", query_lines + ("\n" if query_lines else ""))
        # One markdown file per judgment.
        for qid, front in sorted(included_judgments.items()):
            record = dict(front)
            record.setdefault("query_id", qid)
            content = records._render_frontmatter(record) + "\n"  # noqa: SLF001
            zf.writestr(f"judgments/{qid}.md", content)
        # A small manifest so the archive is self-describing.
        zf.writestr(
            "export-manifest.json",
            json.dumps(
                {
                    "_schema": "eval.export.v1",
                    "run_id": run_id,
                    "since": since,
                    "until": until,
                    "query_count": len(queries),
                    "judgment_count": len(included_judgments),
                    "exported_at": records.utc_now_iso(),
                },
                indent=2,
                sort_keys=True,
            ),
        )

    return {
        "export_path": str(zip_path),
        "query_count": len(queries),
        "judgment_count": len(included_judgments),
    }


# --------------------------------------------------------------------------
# CLI dispatch
# --------------------------------------------------------------------------

_CLI_VERBS = {
    "replay": cmd_replay,
    "export": cmd_export,
    "stats": cmd_stats,
    "capture-status": cmd_capture_status,
    "capture-consent": cmd_capture_consent,
    "import-longmemeval": cmd_import_longmemeval,
    "seed-baseline": cmd_seed_baseline,
    "command-record": cmd_command_record,
    "command-aggregate": cmd_command_aggregate,
    "command-template": cmd_command_template,
    "command-kpi-bootstrap": cmd_command_kpi_bootstrap,
    "command-kpi-run": cmd_command_kpi_run,
    "command-kpi-gate": cmd_command_kpi_gate,
    "command-kpi-report": cmd_command_kpi_report,
}


def run_cli(verb: str, args: Any) -> int:
    """Dispatch a `aug eval <verb>` invocation. Prints JSON to stdout, returns exit code."""
    handler = _CLI_VERBS.get(verb)
    if handler is None:
        print(
            json.dumps(
                {"error": f"unknown verb {verb!r}", "verbs": sorted(_CLI_VERBS)},
                indent=2,
            )
        )
        return 2
    try:
        result = handler(args)
    except Exception as exc:  # noqa: BLE001 - surface the error as JSON, exit non-zero
        logger.error("eval %s failed: %s", verb, exc, exc_info=True)
        print(json.dumps({"error": str(exc), "verb": verb}, indent=2))
        return 1
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    is_error = isinstance(result, dict) and (
        "error" in result or result.get("success") is False
    )
    return 1 if is_error else 0
