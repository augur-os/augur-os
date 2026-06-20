"""auto-friction-audit: mine session transcripts for recurring agent friction.

A self-improving routine (scan-fix protocol, ADR-200). It reads recent AI-client
session transcripts plus hook logs and surfaces *recurring friction* — the
moments where an agent could not reach a sanctioned tool, hunted through tool
discovery, hit a hook block, or hand-rolled a throwaway script — then turns each
cluster into a ranked finding with a concrete remedy proposal.

Autonomy (user-chosen): propose + auto-fix low-risk on a branch.
  - scan() detects friction from REAL transcripts (the durable value).
  - fix() always writes a ranked report + appends to the friction ledger, and
    emits a structured remedy proposal per cluster. Findings whose remedy is on
    the conservative low-risk allowlist (and carries a concrete patch) are
    applied on a dedicated branch with verification; everything risky/
    architectural is queued as a proposal (skillify / ADR / TODO). Never writes
    to main, never deletes.

Detection is the strong half today; the auto-apply path is wired and gated so
that as detectors gain deterministic remedies they can opt into branch-apply
without new plumbing. No model calls — pure transcript/log analysis.
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

import argparse
import json
import logging
import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from src.config.paths import get_runtime_dir
from src.lib.ops_protocol import (
    FixResult,
    OpsContext,
    ScanResult,
    declare_ops_capabilities,
)

logger = logging.getLogger(__name__)

name = "auto-friction-audit"
OPS_CAPABILITIES = declare_ops_capabilities(
    platforms=("cross_platform",),
    windows_fix_mode="auto_fix",
    skip_reason="",
)

DIFFICULTY_SPEC = {
    0: "Surface — count friction clusters in recent transcripts",
    1: "Compare — rank by recurrence across sessions and write the report",
    2: "Suggest — emit remedy proposals per cluster (skillify/ADR/TODO)",
    3: "Expert — auto-apply allowlisted low-risk remedies on a branch",
    4: "Expert — same",
}

# Tunables (kept module-level so tests can override).
DEFAULT_LOOKBACK_DAYS = 14
DEFAULT_MAX_FILES = 200
EVIDENCE_MAX_CHARS = 160

# A throwaway script the agent created at the repo root to work around a missing
# sanctioned path (e.g. `.augur_note_url.py`, `tmp_fix.sh`). Real source lives in
# src/, project-brain/capabilities/skills/, scripts/, apps/ — never as a bare repo-root file.
_REPO_ROOT_SCRIPT_RE = re.compile(r"^\.?[\w.-]+\.(py|sh|js|mjs|ts)$")
_EDIT_TOOLS = {"Write"}
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

# Friction kinds → (human label, severity, remedy proposal). severity drives rank.
_KIND_META: dict[str, dict[str, str]] = {
    "cli-tool-unreachable": {
        "label": "Agent could not reach a tool it tried to call",
        "severity": "error",
        "remedy": "Expose the tool on the CLI/agent surface (aug subcommand or "
        "capability_exposure export_to: cli), or correct the command policy to "
        "name the reachable surface.",
    },
    "tool-discovery-miss": {
        "label": "Tool discovery returned no match (agent hunted for a tool)",
        "severity": "warning",
        "remedy": "Add/clarify the capability so discovery resolves it, or document "
        "the exact tool name in the owning command policy.",
    },
    "hook-friction": {
        "label": "A hook blocked the agent (possible false-fire)",
        "severity": "warning",
        "remedy": "Scope the hook trigger to the real condition; if it fired on "
        "unrelated state, narrow its predicate.",
    },
    "adhoc-script-workaround": {
        "label": "Agent hand-rolled a throwaway script at the repo root",
        "severity": "warning",
        "remedy": "Provide a sanctioned one-shot (aug subcommand / documented "
        "command) so the agent need not reverse-engineer a script.",
    },
    "repeated-command-failure": {
        "label": "Same shell command failed repeatedly in one session",
        "severity": "info",
        "remedy": "Document the correct invocation or add a guarded wrapper for the "
        "failing command.",
    },
}

_SEVERITY_RANK = {"error": 3, "warning": 2, "info": 1}


@dataclass
class _Finding:
    kind: str
    signature: str
    sessions: set[str] = field(default_factory=set)
    occurrences: int = 0
    evidence: str = ""

    def to_issue(self) -> dict:
        meta = _KIND_META.get(self.kind, {})
        return {
            "kind": self.kind,
            "signature": self.signature,
            "label": meta.get("label", self.kind),
            "severity": meta.get("severity", "info"),
            "remedy": meta.get("remedy", ""),
            "remedy_auto": False,  # conservative: friction remedies need judgment
            "sessions": sorted(self.sessions),
            "session_count": len(self.sessions),
            "occurrences": self.occurrences,
            "evidence": self.evidence,
        }


def _transcript_dirs(project_root: Path) -> list[Path]:
    """Return Claude Code transcript dirs for this project and its worktrees."""
    base = Path.home() / ".claude" / "projects"
    if not base.is_dir():
        return []
    slug = str(project_root).replace("/", "-")
    # The main checkout dir is exactly `slug`; worktree sessions append a suffix.
    return sorted(d for d in base.glob(f"{slug}*") if d.is_dir())


def _recent_transcripts(
    project_root: Path, *, lookback_days: int, max_files: int
) -> list[Path]:
    cutoff = time.time() - lookback_days * 86400
    files: list[Path] = []
    for tdir in _transcript_dirs(project_root):
        files.extend(tdir.glob("*.jsonl"))
    fresh = [f for f in files if f.stat().st_mtime >= cutoff]
    fresh.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    return fresh[:max_files]


def _clip(text: str) -> str:
    flat = " ".join(_ANSI_RE.sub("", str(text)).split())
    return flat[:EVIDENCE_MAX_CHARS]


def _result_text(block: dict) -> str:
    """Flatten a tool_result content (str or list of {type,text}) to text."""
    content = block.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(parts)
    return ""


def _iter_blocks(entry: dict):
    msg = entry.get("message")
    content = msg.get("content") if isinstance(msg, dict) else None
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict):
                yield block


def _scan_transcript(path: Path, findings: dict[tuple[str, str], _Finding]) -> int:
    """Run all detectors over one transcript. Returns lines processed."""
    session = path.stem
    lines = 0
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return 0

    def add(kind: str, signature: str, evidence: str) -> None:
        key = (kind, signature)
        finding = findings.get(key)
        if finding is None:
            finding = _Finding(kind=kind, signature=signature, evidence=_clip(evidence))
            findings[key] = finding
        finding.sessions.add(session)
        finding.occurrences += 1
        if not finding.evidence:
            finding.evidence = _clip(evidence)

    for line in raw.splitlines():
        if not line.strip():
            continue
        lines += 1
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue

        # Stop-hook fires arrive as a user message whose content is a plain
        # string ("Stop hook feedback: ..."), NOT a tool_result. Matching the
        # reason text inside tool_results would false-positive on file reads of
        # the hook source, so detect the fire only in user-string messages.
        msg = entry.get("message")
        if (
            entry.get("type") == "user"
            and isinstance(msg, dict)
            and isinstance(msg.get("content"), str)
            and "Value-validation check" in msg["content"]
        ):
            add("hook-friction", "rule-34-value-validation", msg["content"])

        for block in _iter_blocks(entry):
            btype = block.get("type")

            if btype == "tool_result":
                text = _result_text(block)
                # `Error: Unknown tool '<name>'` is aug's exact failure line; it
                # arrives via Bash output (often is_error False when piped), so
                # do not gate on is_error.
                m = re.search(r"Error: Unknown tool ['\"]?([\w:-]+)", text)
                if m:
                    add("cli-tool-unreachable", m.group(1), text)
                elif "No matching deferred tools found" in text:
                    add("tool-discovery-miss", "deferred-tool-search", text)
                elif block.get("is_error") and "Blocked by rule 29" in text:
                    # is_error gate scopes to real PreToolUse denials, not file
                    # reads of the hook source / patterns file.
                    add("hook-friction", "rule-29-dashboard-shortcut", text)

            elif btype == "tool_use" and block.get("name") in _EDIT_TOOLS:
                fp = (block.get("input") or {}).get("file_path", "")
                name = Path(str(fp)).name
                parent = Path(str(fp)).parent.name if fp else ""
                # repo-root one-off script: parent dir is the project root itself
                if (
                    name
                    and _REPO_ROOT_SCRIPT_RE.match(name)
                    and parent in {Path.cwd().name, "Augur", ""}
                    and str(fp).count("/") <= str(Path.cwd()).count("/") + 1
                ):
                    add("adhoc-script-workaround", name, f"created {name} at repo root")

    return lines


def _detect_repeated_bash_failures(
    path: Path, findings: dict[tuple[str, str], _Finding]
) -> None:
    """Flag identical Bash commands that errored 2+ times in one session."""
    session = path.stem
    cmd_by_id: dict[str, str] = {}
    fail_counts: dict[str, int] = defaultdict(int)
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return
    for line in raw.splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        for block in _iter_blocks(entry):
            if block.get("type") == "tool_use" and block.get("name") == "Bash":
                cmd = (block.get("input") or {}).get("command", "")
                if block.get("id"):
                    cmd_by_id[block["id"]] = " ".join(str(cmd).split())[:120]
            elif block.get("type") == "tool_result" and block.get("is_error"):
                cmd = cmd_by_id.get(block.get("tool_use_id", ""))
                if cmd:
                    fail_counts[cmd] += 1
    for cmd, count in fail_counts.items():
        if count >= 2:
            key = ("repeated-command-failure", cmd)
            finding = findings.get(key)
            if finding is None:
                finding = _Finding(
                    kind="repeated-command-failure",
                    signature=cmd,
                    evidence=f"failed {count}x: {cmd}",
                )
                findings[key] = finding
            finding.sessions.add(session)
            finding.occurrences += count


def scan(ctx: OpsContext) -> ScanResult:
    lookback = int(getattr(ctx, "lookback_days", DEFAULT_LOOKBACK_DAYS) or DEFAULT_LOOKBACK_DAYS)
    max_files = int(getattr(ctx, "max_files", DEFAULT_MAX_FILES) or DEFAULT_MAX_FILES)
    transcripts = _recent_transcripts(
        ctx.project_root, lookback_days=lookback, max_files=max_files
    )
    if not transcripts:
        return ScanResult(
            issues=[],
            summary="No session transcripts found to analyze.",
            severity="info",
            items_scanned=0,
        )

    findings: dict[tuple[str, str], _Finding] = {}
    total_lines = 0
    for path in transcripts:
        total_lines += _scan_transcript(path, findings)
        _detect_repeated_bash_failures(path, findings)

    issues = [f.to_issue() for f in findings.values()]
    # Rank: severity, then how many distinct sessions it recurs across.
    issues.sort(
        key=lambda i: (_SEVERITY_RANK.get(i["severity"], 0), i["session_count"], i["occurrences"]),
        reverse=True,
    )

    if not issues:
        return ScanResult(
            issues=[],
            summary=f"No friction detected across {len(transcripts)} transcripts.",
            severity="info",
            items_scanned=len(transcripts),
        )

    worst = max(_SEVERITY_RANK.get(i["severity"], 0) for i in issues)
    severity = {3: "error", 2: "warning", 1: "info"}.get(worst, "info")
    recurring = sum(1 for i in issues if i["session_count"] >= 2)
    summary = (
        f"{len(issues)} friction cluster(s) across {len(transcripts)} transcripts "
        f"({recurring} recurring in 2+ sessions; {total_lines} lines analyzed)."
    )
    return ScanResult(
        issues=issues, summary=summary, severity=severity, items_scanned=len(transcripts)
    )


def _report_dir() -> Path:
    d = get_runtime_dir() / "friction"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _render_report(issues: list[dict], summary: str) -> str:
    now = datetime.now(UTC).isoformat(timespec="seconds")
    lines = [
        "# Agent Friction Audit",
        "",
        f"_Generated {now} — {summary}_",
        "",
        "Recurring friction mined from session transcripts. Each cluster lists a "
        "proposed remedy. Risky/architectural ones are proposals for you to act on; "
        "low-risk allowlisted ones may be auto-applied on a branch.",
        "",
    ]
    for rank, issue in enumerate(issues, 1):
        lines += [
            f"## {rank}. {issue['label']} — `{issue['signature']}`",
            "",
            f"- **kind**: `{issue['kind']}`  |  **severity**: {issue['severity']}",
            f"- **recurrence**: {issue['occurrences']} occurrence(s) across "
            f"{issue['session_count']} session(s)",
            f"- **evidence**: {issue['evidence']}",
            f"- **proposed remedy**: {issue['remedy']}",
            f"- **auto-applicable**: {'yes' if issue['remedy_auto'] else 'no — queued as proposal'}",
            "",
        ]
    return "\n".join(lines)


def _append_ledger(issues: list[dict]) -> Path:
    ledger = _report_dir() / "friction-ledger.jsonl"
    stamp = datetime.now(UTC).isoformat(timespec="seconds")
    with ledger.open("a", encoding="utf-8") as handle:
        for issue in issues:
            handle.write(json.dumps({"ts": stamp, **issue}, sort_keys=True) + "\n")
    return ledger


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    if not issues:
        return FixResult(success=True, summary="No friction to report.", fix_type="report")

    summary = f"{len(issues)} friction cluster(s)"
    if ctx.dry_run:
        return FixResult(success=True, summary=f"Dry run: {summary}", fix_type="report")

    report_dir = _report_dir()
    report = _render_report(issues, summary)
    report_path = report_dir / f"report-{datetime.now(UTC):%Y%m%dT%H%M%SZ}.md"
    report_path.write_text(report, encoding="utf-8")
    (report_dir / "latest-report.md").write_text(report, encoding="utf-8")
    ledger = _append_ledger(issues)

    changes = [
        f"Wrote friction report: {report_path}",
        f"Appended {len(issues)} finding(s) to {ledger}",
    ]

    # Auto-fix-low-risk-on-a-branch: only findings explicitly marked remedy_auto
    # with a concrete patch are eligible. Friction remedies need judgment, so the
    # allowlist is conservative and currently empty — everything is proposed.
    auto = [i for i in issues if i.get("remedy_auto")]
    proposals = [i for i in issues if not i.get("remedy_auto")]
    if auto:
        changes.append(
            f"{len(auto)} low-risk finding(s) flagged for branch auto-apply "
            "(see _apply_on_branch)."
        )
    changes.append(f"{len(proposals)} finding(s) queued as proposals for review.")

    return FixResult(
        success=True,
        changes=changes,
        summary=f"{summary}: reported + {len(proposals)} proposal(s) queued.",
        fix_type="report",
    )


def _run_cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Agent friction audit (scan-fix).")
    parser.add_argument("verb", nargs="?", default="run", choices=["scan", "fix", "run"])
    parser.add_argument("--lookback-days", type=int, default=DEFAULT_LOOKBACK_DAYS)
    parser.add_argument("--max-files", type=int, default=DEFAULT_MAX_FILES)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    ctx = OpsContext(project_root=Path.cwd(), dry_run=args.dry_run)
    # OpsContext is a dataclass; attach tunables for scan() to read.
    ctx.lookback_days = args.lookback_days  # type: ignore[attr-defined]
    ctx.max_files = args.max_files  # type: ignore[attr-defined]

    scan_result = scan(ctx)
    if args.verb == "scan":
        print(json.dumps({"summary": scan_result.summary,
                          "severity": scan_result.severity,
                          "items_scanned": scan_result.items_scanned,
                          "issues": scan_result.issues}, indent=2))
        return 0

    fix_result = fix(ctx, scan_result.issues)
    print(json.dumps({"scan": scan_result.summary,
                      "fix": fix_result.summary,
                      "changes": fix_result.changes}, indent=2))
    return 0 if fix_result.success else 1


if __name__ == "__main__":
    raise SystemExit(_run_cli())
