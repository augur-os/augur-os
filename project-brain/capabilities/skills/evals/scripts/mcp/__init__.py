"""MCP tools + CLI subcommands for the evals skill (ADR-742).

Exposes two registration entry points the Augur loader / CLI discover:

- `register_tools(mcp, mcp_tool_interceptor, metrics)` -- the 4 read-only MCP
  tools: eval-replay, eval-export, eval-stats, eval-capture-status. CLI-primary
  per the surface-decision-matrix; no dashboard exposure in v1.
- `register_subcommands(subparsers)` -- the `aug eval <verb>` CLI surface
  (ADR-260): replay, export, stats, capture-status, capture-consent,
  import-longmemeval, seed-baseline.

No model calls. Every tool is read-only with respect to retrieval -- they only
read/replay captured queries and write report artifacts under
get_documents_dir()/evals/.
"""
from __future__ import annotations


import importlib.util as _augur_importlib_util
import sys as _augur_sys
from pathlib import Path as _AugurPath

_augur_bootstrap_start = _AugurPath(__file__).resolve()
for _augur_bootstrap_parent in (_augur_bootstrap_start.parent, *_augur_bootstrap_start.parents):
    _augur_bootstrap_path = _augur_bootstrap_parent / "daemon" / "scripts" / "bootstrap_paths.py"
    if _augur_bootstrap_path.is_file():
        break
else:
    raise RuntimeError(f"Unable to locate shared skill bootstrap from {_augur_bootstrap_start}")

_augur_bootstrap_spec = _augur_importlib_util.spec_from_file_location(
    "_augur_shared_bootstrap_paths", _augur_bootstrap_path
)
if _augur_bootstrap_spec is None or _augur_bootstrap_spec.loader is None:
    raise RuntimeError(f"Unable to load shared skill bootstrap from {_augur_bootstrap_path}")
_augur_bootstrap_module = _augur_importlib_util.module_from_spec(_augur_bootstrap_spec)
_augur_sys.modules[_augur_bootstrap_spec.name] = _augur_bootstrap_module
_augur_bootstrap_spec.loader.exec_module(_augur_bootstrap_module)
_augur_bootstrap_module.ensure_project_paths(__file__)

# The MCP server registration path installs a custom importer so `scripts/mcp/*`
# can import sibling `scripts/*` modules; the CLI subcommand discovery path
# (src/cli_plugins.py) does not. Put this skill's own `scripts/` dir on sys.path
# so `import eval_ops` / `import records` resolve under BOTH entry points.
_augur_scripts_dir = str(_AugurPath(__file__).resolve().parent.parent)
if _augur_scripts_dir not in _augur_sys.path:
    _augur_sys.path.insert(0, _augur_scripts_dir)

import json
from typing import TYPE_CHECKING, Any, Callable

from command_kpi_schema import CANONICAL_COMMANDS

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

try:
    from src.mcp.augur_shared.annotations import tool_annotations
    from src.mcp.augur_shared.logging import get_entity_logger
except ImportError:  # pragma: no cover - fallback for early init / CLI
    import logging as _logging

    def get_entity_logger(name: str):
        return _logging.getLogger(name)

    def tool_annotations(annotations: dict) -> dict:
        return annotations


logger = get_entity_logger("mcp.dev.evals")

# Read-only annotation block shared by all 4 tools.
_READ_ONLY = {
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": False,
    "readOnlyHint": True,
}


def _load_eval_ops():
    """Import the sibling eval_ops module (scripts/ is on sys.path via bootstrap)."""
    import eval_ops  # type: ignore[import-not-found]

    return eval_ops


# --------------------------------------------------------------------------
# MCP tools
# --------------------------------------------------------------------------


def register_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable[..., Any],
    metrics: Any,
) -> None:
    """Register the 4 read-only eval MCP tools with the MCP server."""
    logger.info("Registering evals MCP tools...")

    @mcp.tool(
        name="eval-capture-status",
        annotations=tool_annotations({"title": "Eval Capture Status", **_READ_ONLY}),
    )
    @mcp_tool_interceptor
    async def eval_capture_status_tool() -> str:
        """Report retrieval-query capture state: contributor mode, consent, counts.

        Returns: {enabled, consent, queries_captured_total, queries_today,
        last_capture_ts}.
        """
        metrics.track_tool("eval_capture_status", skill="evals")
        import capture  # type: ignore[import-not-found]

        return json.dumps(capture.capture_status(), indent=2, default=str)

    @mcp.tool(
        name="eval-export",
        annotations=tool_annotations({"title": "Eval Export", **_READ_ONLY}),
    )
    @mcp_tool_interceptor
    async def eval_export_tool(
        since: str | None = None,
        until: str | None = None,
    ) -> str:
        """Bundle a date range of captured queries + judgments into a portable zip.

        Args:
            since: ISO-8601 lower bound on capture timestamp (inclusive).
            until: ISO-8601 upper bound on capture timestamp (inclusive).

        Returns: {export_path, query_count, judgment_count}.
        """
        metrics.track_tool("eval_export", skill="evals")
        eval_ops = _load_eval_ops()
        result = eval_ops.export_range(since=since, until=until)
        return json.dumps(result, indent=2, default=str)

    @mcp.tool(
        name="eval-replay",
        annotations=tool_annotations({"title": "Eval Replay", **_READ_ONLY}),
    )
    @mcp_tool_interceptor
    async def eval_replay_tool(
        config: str | None = None,
        corpus: str = "all",
        since: str | None = None,
    ) -> str:
        """Rerun captured queries against current retrieval and score them.

        Args:
            config: Optional path to a YAML config that overrides recorded
                retrieval params (for A/B testing a tuning change).
            corpus: "captured" | "external" | "all" (default "all").
            since: Optional ISO-8601 lower bound on capture timestamp.

        Returns: {run_id, summary_path, scores: {P_at_5_mean, ...}, ...}.
        """
        metrics.track_tool("eval_replay", skill="evals")
        import replay as replay_mod  # type: ignore[import-not-found]
        import report as report_mod  # type: ignore[import-not-found]

        eval_ops = _load_eval_ops()
        result = replay_mod.replay(config_path=config, corpus=corpus, since=since)
        written = report_mod.write_report(
            result, thresholds=eval_ops._alert_thresholds(), compare_baseline=True
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
        return json.dumps(
            {
                "run_id": written["run_id"],
                "summary_path": written["summary_path"],
                "raw_path": written["raw_path"],
                "manifest_path": written["manifest_path"],
                "counts": result.get("counts", {}),
                "index_drift": result.get("index_drift", False),
                "alerts": written.get("alerts", []),
                "scores": scores,
            },
            indent=2,
            default=str,
        )

    @mcp.tool(
        name="eval-stats",
        annotations=tool_annotations({"title": "Eval Stats", **_READ_ONLY}),
    )
    @mcp_tool_interceptor
    async def eval_stats_tool(run_id: str | None = None) -> str:
        """Return parsed numbers for a replay run (default: the most recent run).

        Args:
            run_id: Optional run id; defaults to the most recent report dir.

        Returns: parsed summary numbers -- run_id, commit, counts, scores, alerts.
        """
        metrics.track_tool("eval_stats", skill="evals")
        import report as report_mod  # type: ignore[import-not-found]

        return json.dumps(
            report_mod.parse_summary_numbers(run_id), indent=2, default=str
        )

    logger.info("evals MCP tools registered (4 tools)")


# --------------------------------------------------------------------------
# CLI subcommands -- `aug eval <verb>`
# --------------------------------------------------------------------------


def register_subcommands(subparsers) -> None:
    """Register the `aug eval` subcommand with its sub-verbs (ADR-260)."""
    parser = subparsers.add_parser(
        "eval",
        allow_abbrev=False,
        help="Retrieval eval harness -- capture, replay, score (ADR-742)",
    )
    eval_sub = parser.add_subparsers(dest="eval_verb")

    p_replay = eval_sub.add_parser(
        "replay",
        allow_abbrev=False,
        help="Rerun captured queries, score, write report",
    )
    p_replay.add_argument("--config", help="YAML config overriding recorded retrieval params")
    p_replay.add_argument(
        "--corpus",
        choices=["captured", "external", "all"],
        default="all",
        help="Which corpus to replay (default: all)",
    )
    p_replay.add_argument("--since", help="ISO-8601 lower bound on capture timestamp")
    p_replay.add_argument(
        "--with-ci",
        action="store_true",
        dest="with_ci",
        help="Compute bootstrap 95%% CI on the summary",
    )

    p_export = eval_sub.add_parser(
        "export",
        allow_abbrev=False,
        help="Bundle a date range into a portable zip",
    )
    p_export.add_argument("--since", help="ISO-8601 lower bound on capture timestamp")
    p_export.add_argument("--until", help="ISO-8601 upper bound on capture timestamp")

    p_stats = eval_sub.add_parser(
        "stats",
        allow_abbrev=False,
        help="Print parsed numbers for a run",
    )
    p_stats.add_argument("--run-id", dest="run_id", help="Run id (default: most recent)")

    eval_sub.add_parser(
        "capture-status",
        allow_abbrev=False,
        help="Show capture mode / consent / counts",
    )
    eval_sub.add_parser(
        "capture-consent",
        allow_abbrev=False,
        help="Write consent.md to opt in to capture",
    )

    p_import = eval_sub.add_parser(
        "import-longmemeval",
        allow_abbrev=False,
        help="Convert a LongMemEval JSONL into the v1 corpus shape",
    )
    p_import.add_argument("--path", required=True, help="Path to the LongMemEval JSONL")
    p_import.add_argument(
        "--corpus-id", dest="corpus_id", help="Corpus id (default: input file stem)"
    )

    p_command_record = eval_sub.add_parser(
        "command-record",
        allow_abbrev=False,
        help="Append a command.run.v1 envelope to private eval storage",
    )
    p_command_record.add_argument("--command", required=True)
    p_command_record.add_argument("--client", required=True)
    p_command_record.add_argument("--input-class", dest="input_class", required=True)
    p_command_record.add_argument("--chosen-route", dest="chosen_route", required=True)
    p_command_record.add_argument(
        "--duration-ms", dest="duration_ms", type=int, default=0
    )
    p_command_record.add_argument("--phases", default="[]")
    p_command_record.add_argument("--quality-flags", dest="quality_flags", default="[]")
    p_command_record.add_argument("--warnings", default="[]")
    p_command_record.add_argument("--outputs", default="{}")
    p_command_record.add_argument("--run-id", dest="run_id")

    p_command_aggregate = eval_sub.add_parser(
        "command-aggregate",
        allow_abbrev=False,
        help="Aggregate human command scorecards",
    )
    p_command_aggregate.add_argument("--run-id", dest="run_id")

    eval_sub.add_parser(
        "command-template",
        allow_abbrev=False,
        help="Print the private human scorecard template path",
    )

    p_command_kpi_bootstrap = eval_sub.add_parser(
        "command-kpi-bootstrap",
        allow_abbrev=False,
        help="Create private actual-data command KPI scenarios",
    )
    p_command_kpi_bootstrap.add_argument("--run-id", dest="run_id")

    p_command_kpi_run = eval_sub.add_parser(
        "command-kpi-run",
        allow_abbrev=False,
        help="Run automatic command KPI scenarios and write scorecards",
    )
    p_command_kpi_run.add_argument("--scenario-path", dest="scenario_path")
    p_command_kpi_run.add_argument("--run-id", dest="run_id")
    p_command_kpi_run.add_argument(
        "--command",
        choices=sorted(CANONICAL_COMMANDS),
        help="Run only scenarios for one canonical command",
    )

    p_command_kpi_gate = eval_sub.add_parser(
        "command-kpi-gate",
        allow_abbrev=False,
        help="Evaluate latest command KPI aggregate against demo thresholds",
    )
    p_command_kpi_gate.add_argument(
        "--required-consecutive-passes",
        dest="required_consecutive_passes",
        type=int,
        default=3,
    )

    p_command_kpi_report = eval_sub.add_parser(
        "command-kpi-report",
        allow_abbrev=False,
        help="Summarize the latest command KPI aggregate and details",
    )
    p_command_kpi_report.add_argument("--run-id", dest="run_id")

    eval_sub.add_parser(
        "seed-baseline",
        allow_abbrev=False,
        help="Run the hand-authored seed query set through retrieval once",
    )

    parser.set_defaults(func=_run_eval_cli)


def _run_eval_cli(args, remaining) -> int:
    """Execute an `aug eval <verb>` invocation."""
    if remaining:
        print(
            json.dumps(
                {"error": "unknown arguments", "unknown_args": remaining},
                indent=2,
            )
        )
        return 2
    verb = getattr(args, "eval_verb", None)
    if not verb:
        print(
            json.dumps(
                {
                    "error": "no verb given",
                    "verbs": [
                        "replay",
                        "export",
                        "stats",
                        "capture-status",
                        "capture-consent",
                        "import-longmemeval",
                        "command-record",
                        "command-aggregate",
                        "command-template",
                        "command-kpi-bootstrap",
                        "command-kpi-run",
                        "command-kpi-gate",
                        "command-kpi-report",
                        "seed-baseline",
                    ],
                },
                indent=2,
            )
        )
        return 2
    eval_ops = _load_eval_ops()
    return eval_ops.run_cli(verb, args)


__all__ = ["register_tools", "register_subcommands"]
