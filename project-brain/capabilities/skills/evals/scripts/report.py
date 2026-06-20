"""Report writers -- summary.md + raw.jsonl + manifest.json (spec section 4.3.3).

A replay run produces a directory:

    get_documents_dir()/evals/reports/<run-id>/
    |-- summary.md      human-readable: overall + per-bucket + delta vs. baseline
    |-- raw.jsonl       one scored-query row per line -- recompute aggregates w/o rerun
    |-- manifest.json   run metadata: timestamp, commit, config, query-set hash

`<run-id> = <YYYY-MM-DD-HHMMSS>-<commit[:7]>`. The directory
`get_documents_dir()/evals/reports/baseline/` is reserved -- a stable symlink the
user creates pointing at the chosen baseline run.

Markdown is rendered deterministically (sorted keys, fixed float precision) so
the `cat` test is stable and a rerun produces byte-identical output for the same
inputs.
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

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import records

logger = logging.getLogger("evals.report")

# The headline metrics shown in the overall table and used for delta alerts.
HEADLINE_METRICS = ("P_at_5", "R_at_5", "MRR", "nDCG_at_10")
# Full metric set for the detailed table.
ALL_METRICS = (
    "P_at_1",
    "P_at_5",
    "P_at_10",
    "R_at_1",
    "R_at_5",
    "R_at_10",
    "MRR",
    "nDCG_at_10",
)


# --------------------------------------------------------------------------
# Run id + paths
# --------------------------------------------------------------------------


def make_run_id(commit: str | None = None, when: datetime | None = None) -> str:
    """`<YYYY-MM-DD-HHMMSS>-<commit[:7]>` (spec section 4.3.3)."""
    when = when or datetime.now(timezone.utc)
    stamp = when.strftime("%Y-%m-%d-%H%M%S")
    short = (commit or "")[:7] or "nocommit"
    return f"{stamp}-{short}"


def report_dir(run_id: str) -> Path:
    return records.reports_dir() / run_id


def baseline_dir() -> Path:
    """The reserved baseline symlink target."""
    return records.reports_dir() / "baseline"


# --------------------------------------------------------------------------
# Query-set hash -- pins the exact set of scored queries for a run
# --------------------------------------------------------------------------


def query_set_hash(scored_rows: list[dict[str, Any]]) -> str:
    """`sha256` of the sorted scored query ids, `[:12]`. Identifies the query set."""
    ids = sorted(str(r.get("id", "")) for r in scored_rows)
    return hashlib.sha256("\n".join(ids).encode("utf-8")).hexdigest()[:12]


# --------------------------------------------------------------------------
# Markdown rendering helpers
# --------------------------------------------------------------------------


def _fmt(value: float | None) -> str:
    """Fixed 4-decimal float rendering so summary.md is byte-stable across reruns."""
    if value is None:
        return "n/a"
    return f"{value:.4f}"


def _metric_table(title: str, agg: dict[str, Any], metrics_list: tuple[str, ...]) -> list[str]:
    """Render one aggregate dict as a markdown table block."""
    lines = [f"### {title}", ""]
    if not agg:
        lines.append("_no scored queries_")
        lines.append("")
        return lines
    n = next(iter(agg.values())).get("n", 0) if agg else 0
    lines.append(f"_n = {n} scored queries_")
    lines.append("")
    lines.append("| Metric | Mean | StdErr | 95% CI |")
    lines.append("|---|---|---|---|")
    for metric in metrics_list:
        entry = agg.get(metric)
        if not entry:
            continue
        mean = _fmt(entry.get("mean"))
        stderr = _fmt(entry.get("stderr"))
        ci = entry.get("bootstrap_ci_95")
        ci_str = f"({_fmt(ci[0])}, {_fmt(ci[1])})" if ci else "-"
        lines.append(f"| {metric} | {mean} | {stderr} | {ci_str} |")
    lines.append("")
    return lines


def _delta_table(
    current: dict[str, Any], baseline: dict[str, Any]
) -> list[str]:
    """Render a headline-metric delta table vs. a prior/baseline run."""
    lines = ["### Delta vs. baseline", ""]
    cur_overall = current.get("overall", {})
    base_overall = baseline.get("overall", {})
    if not cur_overall or not base_overall:
        lines.append("_baseline has no comparable overall numbers_")
        lines.append("")
        return lines
    lines.append("| Metric | Baseline | Current | Delta |")
    lines.append("|---|---|---|---|")
    for metric in HEADLINE_METRICS:
        cur = cur_overall.get(metric, {}).get("mean")
        base = base_overall.get(metric, {}).get("mean")
        if cur is None or base is None:
            continue
        delta = cur - base
        sign = "+" if delta >= 0 else ""
        lines.append(
            f"| {metric} | {_fmt(base)} | {_fmt(cur)} | {sign}{delta:.4f} |"
        )
    lines.append("")
    return lines


def compute_alerts(
    current: dict[str, Any],
    baseline: dict[str, Any],
    thresholds: dict[str, float],
) -> list[dict[str, Any]]:
    """Return alert rows for headline metrics that dropped MORE than threshold.

    Threshold is in absolute percentage points (config default 5.0 == a 0.05
    absolute drop). A drop EQUAL to the threshold does not alert -- strictly
    greater (spec section 4.7: "drops by more than").
    """
    alerts: list[dict[str, Any]] = []
    cur_overall = current.get("overall", {})
    base_overall = baseline.get("overall", {})
    for metric in HEADLINE_METRICS:
        cur = cur_overall.get(metric, {}).get("mean")
        base = base_overall.get(metric, {}).get("mean")
        if cur is None or base is None:
            continue
        # Round before comparing so float error (e.g. 0.80 - 0.75 -> 5.0000004)
        # does not trip a threshold the drop only equals.
        drop_points = round((base - cur) * 100.0, 6)
        threshold = float(thresholds.get(metric, 5.0))
        if drop_points > threshold:
            alerts.append(
                {
                    "metric": metric,
                    "baseline": base,
                    "current": cur,
                    "drop_points": round(drop_points, 4),
                    "threshold": threshold,
                    "severity": "WARN",
                }
            )
    return alerts


# --------------------------------------------------------------------------
# summary.md
# --------------------------------------------------------------------------


def render_summary(
    replay_result: dict[str, Any],
    run_id: str,
    *,
    baseline_aggregates: dict[str, Any] | None = None,
    alerts: list[dict[str, Any]] | None = None,
) -> str:
    """Render the full summary.md content for a replay run."""
    counts = replay_result.get("counts", {})
    aggregates = replay_result.get("aggregates", {})
    lines: list[str] = []
    lines.append(f"# Eval Replay Report -- {run_id}")
    lines.append("")
    lines.append(f"- **Started:** {replay_result.get('started_at', '')}")
    lines.append(f"- **Finished:** {replay_result.get('finished_at', '')}")
    lines.append(f"- **Commit:** {replay_result.get('live_commit', '')}")
    lines.append(
        f"- **Vault manifest hash:** {replay_result.get('live_vault_manifest_hash', '')}"
    )
    lines.append(f"- **Corpus:** {replay_result.get('corpus', 'all')}")
    lines.append(
        f"- **Queries:** {counts.get('scored', 0)} scored, "
        f"{counts.get('unlabeled', 0)} unlabeled (skipped), "
        f"{counts.get('total_queries', 0)} total"
    )
    override = replay_result.get("config_override") or {}
    if override:
        lines.append(f"- **Config override:** `{json.dumps(override, sort_keys=True)}`")
    if replay_result.get("index_drift"):
        detail = replay_result.get("drift_detail") or {}
        lines.append(
            f"- **WARNING -- index drift:** {detail.get('queries_with_drift', '?')} of "
            f"{detail.get('total_queries', '?')} queries were captured against a "
            f"different vault manifest. Baseline numbers may not be comparable."
        )
    lines.append("")

    # Overall table.
    lines.extend(_metric_table("Overall", aggregates.get("overall", {}), ALL_METRICS))

    # Delta vs. baseline.
    if baseline_aggregates:
        lines.extend(_delta_table(aggregates, baseline_aggregates))

    # Alerts.
    if alerts:
        lines.append("### Alerts")
        lines.append("")
        lines.append("| Metric | Baseline | Current | Drop (pts) | Threshold | Severity |")
        lines.append("|---|---|---|---|---|---|")
        for alert in alerts:
            lines.append(
                f"| {alert['metric']} | {_fmt(alert['baseline'])} | "
                f"{_fmt(alert['current'])} | {alert['drop_points']:.4f} | "
                f"{alert['threshold']:.1f} | {alert['severity']} |"
            )
        lines.append("")
        lines.append(
            "_Report-only in v1 -- the loop result stays green regardless._"
        )
        lines.append("")

    # Per-bucket breakdowns (spec section 4.4.6).
    for dim_label, dim_key in (
        ("By source", "by_source"),
        ("By tool", "by_tool"),
        ("By mode", "by_mode"),
        ("By corpus", "by_corpus"),
    ):
        bucket = aggregates.get(dim_key)
        if not bucket:
            continue
        lines.append(f"## {dim_label}")
        lines.append("")
        for key in sorted(bucket):
            lines.extend(
                _metric_table(f"{key or '(empty)'}", bucket[key], HEADLINE_METRICS)
            )

    # Unlabeled queries (labeling gap, surfaced separately per spec section 4.4).
    unlabeled = replay_result.get("unlabeled_queries", [])
    lines.append("## Unlabeled queries (skipped)")
    lines.append("")
    if not unlabeled:
        lines.append("_none -- every query has at least one labeled relevant doc_")
        lines.append("")
    else:
        lines.append(
            f"{len(unlabeled)} queries were skipped because they have no judgment "
            f"or zero labeled relevant docs. They measure a labeling gap, not "
            f"retrieval quality."
        )
        lines.append("")
        lines.append("| Query id | Source | Reason |")
        lines.append("|---|---|---|")
        for row in sorted(unlabeled, key=lambda r: str(r.get("id", ""))):
            lines.append(
                f"| {row.get('id', '')} | {row.get('source', '')} | "
                f"{row.get('reason', '')} |"
            )
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


# --------------------------------------------------------------------------
# raw.jsonl + manifest.json
# --------------------------------------------------------------------------


def render_raw_jsonl(replay_result: dict[str, Any]) -> str:
    """One JSON line per scored query -- enough to recompute aggregates w/o rerun.

    Rows are emitted in the deterministic (ts, id) order replay produced them,
    so two consecutive replays of the same query set yield byte-identical output.
    """
    lines: list[str] = []
    for row in replay_result.get("queries", []):
        out = {
            "id": row.get("id"),
            "query": row.get("query"),
            "source": row.get("source"),
            "tool": row.get("tool"),
            "mode": row.get("mode"),
            "corpus": row.get("corpus"),
            "retrieved": row.get("retrieved", []),
            "relevant_doc_ids": row.get("relevant_doc_ids", []),
            "index_drift": row.get("index_drift", False),
            "scores": row.get("scores", {}),
        }
        lines.append(json.dumps(out, ensure_ascii=False, sort_keys=True, default=str))
    return "\n".join(lines) + ("\n" if lines else "")


def render_manifest(
    replay_result: dict[str, Any],
    run_id: str,
    *,
    baseline_run_id: str | None = None,
    alerts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Run metadata: timestamp, commit, config, query-set hash (spec section 4.3.3)."""
    scored = replay_result.get("queries", [])
    return {
        "_schema": "eval.report.manifest.v1",
        "run_id": run_id,
        "started_at": replay_result.get("started_at"),
        "finished_at": replay_result.get("finished_at"),
        "augur_commit": replay_result.get("live_commit"),
        "vault_manifest_hash": replay_result.get("live_vault_manifest_hash"),
        "corpus": replay_result.get("corpus"),
        "since": replay_result.get("since"),
        "config_override": replay_result.get("config_override") or {},
        "query_set_hash": query_set_hash(scored),
        "counts": replay_result.get("counts", {}),
        "index_drift": replay_result.get("index_drift", False),
        "drift_detail": replay_result.get("drift_detail"),
        "baseline_run_id": baseline_run_id,
        "alerts": alerts or [],
    }


# --------------------------------------------------------------------------
# Baseline lookup -- for delta rendering + loop alerts
# --------------------------------------------------------------------------


def load_baseline_aggregates(
    exclude_run_id: str | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    """Load aggregates for the delta baseline.

    Priority: the `reports/baseline/` symlink if present, otherwise the most
    recent prior run directory. `exclude_run_id` skips a specific run dir (the
    run currently being written) so it is never picked as its own baseline.
    Returns (aggregates, run_id) or (None, None).
    """
    bdir = baseline_dir()
    candidate: Path | None = None
    if bdir.exists():
        candidate = bdir
    else:
        rdir = records.reports_dir()
        if rdir.exists():
            runs = sorted(
                (
                    d
                    for d in rdir.iterdir()
                    if d.is_dir()
                    and d.name != "baseline"
                    and d.name != exclude_run_id
                ),
                key=lambda d: d.name,
            )
            if runs:
                candidate = runs[-1]
    if candidate is None:
        return None, None
    raw_path = candidate / "raw.jsonl"
    manifest_path = candidate / "manifest.json"
    if not raw_path.is_file():
        return None, None
    # Recompute aggregates from raw.jsonl so we never depend on a stale summary.
    import metrics as _metrics

    rows: list[dict[str, Any]] = []
    for line in raw_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    overall = _metrics.aggregate(
        [r.get("scores", {}) for r in rows], with_ci=False
    )
    run_id = None
    if manifest_path.is_file():
        try:
            run_id = json.loads(manifest_path.read_text(encoding="utf-8")).get("run_id")
        except (OSError, json.JSONDecodeError):
            run_id = None
    if run_id is None:
        run_id = candidate.name if candidate.name != "baseline" else "baseline"
    return {"overall": overall}, run_id


# --------------------------------------------------------------------------
# write_report -- the public entry point
# --------------------------------------------------------------------------


def write_report(
    replay_result: dict[str, Any],
    run_id: str | None = None,
    *,
    thresholds: dict[str, float] | None = None,
    compare_baseline: bool = True,
) -> dict[str, Any]:
    """Write summary.md + raw.jsonl + manifest.json for a replay run.

    Returns a dict: {run_id, report_dir, summary_path, raw_path, manifest_path,
    alerts, baseline_run_id}.
    """
    commit = replay_result.get("live_commit", "")
    run_id = run_id or make_run_id(commit)
    rdir = report_dir(run_id)

    # Resolve the baseline BEFORE creating this run's directory, and exclude
    # this run id explicitly — otherwise the just-created (empty) run dir would
    # be picked as "the most recent prior run".
    baseline_aggregates: dict[str, Any] | None = None
    baseline_run_id: str | None = None
    if compare_baseline:
        baseline_aggregates, baseline_run_id = load_baseline_aggregates(
            exclude_run_id=run_id
        )

    rdir.mkdir(parents=True, exist_ok=True)

    alerts: list[dict[str, Any]] = []
    if baseline_aggregates and thresholds:
        alerts = compute_alerts(
            replay_result.get("aggregates", {}), baseline_aggregates, thresholds
        )

    summary = render_summary(
        replay_result,
        run_id,
        baseline_aggregates=baseline_aggregates,
        alerts=alerts,
    )
    raw = render_raw_jsonl(replay_result)
    manifest = render_manifest(
        replay_result, run_id, baseline_run_id=baseline_run_id, alerts=alerts
    )

    summary_path = rdir / "summary.md"
    raw_path = rdir / "raw.jsonl"
    manifest_path = rdir / "manifest.json"
    summary_path.write_text(summary, encoding="utf-8")
    raw_path.write_text(raw, encoding="utf-8")
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )

    return {
        "run_id": run_id,
        "report_dir": str(rdir),
        "summary_path": str(summary_path),
        "raw_path": str(raw_path),
        "manifest_path": str(manifest_path),
        "alerts": alerts,
        "baseline_run_id": baseline_run_id,
    }


def parse_summary_numbers(run_id: str | None = None) -> dict[str, Any]:
    """Parse a run's manifest + raw.jsonl into the numbers `eval stats` returns.

    Defaults to the most recent run. Recomputes aggregates from raw.jsonl so the
    numbers never depend on a stale summary.md render.
    """
    import metrics as _metrics

    rdir = records.reports_dir()
    target: Path | None = None
    if run_id:
        target = rdir / run_id
    else:
        if rdir.exists():
            runs = sorted(
                (d for d in rdir.iterdir() if d.is_dir() and d.name != "baseline"),
                key=lambda d: d.name,
            )
            if runs:
                target = runs[-1]
    if target is None or not target.is_dir():
        return {"error": "no report found", "run_id": run_id}

    manifest_path = target / "manifest.json"
    raw_path = target / "raw.jsonl"
    manifest: dict[str, Any] = {}
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            manifest = {}
    rows: list[dict[str, Any]] = []
    if raw_path.is_file():
        for line in raw_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    overall = _metrics.aggregate([r.get("scores", {}) for r in rows], with_ci=False)
    scores = {
        f"{metric}_mean": overall.get(metric, {}).get("mean")
        for metric in ALL_METRICS
        if metric in overall
    }
    return {
        "run_id": manifest.get("run_id", target.name),
        "augur_commit": manifest.get("augur_commit"),
        "vault_manifest_hash": manifest.get("vault_manifest_hash"),
        "corpus": manifest.get("corpus"),
        "counts": manifest.get("counts", {}),
        "index_drift": manifest.get("index_drift", False),
        "alerts": manifest.get("alerts", []),
        "scores": scores,
    }
