"""auto-agent-config-parity: detect Claude-only enforcement gaps across agent clients.

Augur ships configuration to multiple agent clients (Claude, Codex, Gemini,
OpenCode, Copilot). When a behavior gate (PreToolUse Bash blocker, permission
rule, hook script) lands in `.claude/settings.json` only, other agents bypass
it silently. This scanner builds a per-client × per-rule enforcement matrix,
flagging behaviors that have a Claude-side gate but no cross-agent peer
(`.githooks/`, `.pre-commit-config.yaml`) and no equivalent in other client
config dirs.

Difficulty:
  0: surface — list Claude PreToolUse Bash hooks and whether each maps to a
     cross-agent gate or sibling client config
  1: + report missing client adapters when an enforcement keyword (kill, rm
     -rf .next, pnpm dev, etc.) is gated only in Claude
  2+: report-only with evolution gap — auto-stub adapters is out of v1 scope

See ADR-200 for the scan-fix protocol.
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
import json
import re
from pathlib import Path

from src.lib.ops_protocol import (
    FixResult,
    OpsContext,
    ScanResult,
    declare_ops_capabilities,
    evolution_gap,
    make_issue,
    write_report,
)

name = "auto-agent-config-parity"
OPS_CAPABILITIES = declare_ops_capabilities(
    platforms=("cross_platform",),
    windows_fix_mode="report_only",
    skip_reason="report-only configuration parity scanner",
)

DIFFICULTY_SPEC = {
    0: "Surface — enumerate Claude PreToolUse Bash hooks and cross-agent gate presence",
    1: "Compare — flag Claude-only enforcement keywords without cross-agent peer",
    2: "Suggest — emit evolution gap recommending shared gate location",
    3: "Expert — adapter stubs for every connected client (out of scope v1)",
    4: "Expert — same",
}

# Directories that hold per-client agent configuration. Order matters for
# reporting (Claude first because it is the most-customized surface today).
_CLIENT_CONFIG_DIRS: list[tuple[str, str]] = [
    ("claude", ".claude"),
    ("codex", ".codex"),
    ("gemini", ".gemini"),
    ("opencode", ".opencode"),
    ("copilot", ".github/instructions"),
]

# Cross-agent enforcement layers. When a Claude-only gate has a peer here,
# the rule is already cross-agent (anyone committing through this checkout
# triggers the same gate). When neither layer carries the keyword, the rule
# is Claude-only.
_CROSS_AGENT_LAYERS: tuple[str, ...] = (
    ".githooks",
    ".pre-commit-config.yaml",
    ".github/scripts",
)

# Keywords that imply a behavior gate when found in a hook script. These are
# the patterns a Bash blocker typically targets — kill, rm -rf .next,
# pnpm/npm dev, next dev. Extend conservatively: each token is matched as a
# whole word against the hook script body.
_GATE_KEYWORDS: dict[str, str] = {
    r"\.next\b": "next-build-cache",
    r"\bpnpm[[:space:]]+(--filter[[:space:]]+\S+[[:space:]]+)?(run[[:space:]]+)?dev\b": "pnpm-dev",
    r"\bnpm[[:space:]]+run[[:space:]]+dev\b": "npm-run-dev",
    r"\bnext[[:space:]]+dev\b": "next-dev",
    r"\bnext-server\b": "next-server",
    r"\bkill\b": "process-kill",
    r"\bpkill\b": "process-pkill",
}


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _list_pretooluse_bash_scripts(claude_settings: dict) -> list[Path]:
    """Extract script paths referenced from Claude PreToolUse Bash hooks."""
    scripts: list[Path] = []
    hooks_root = claude_settings.get("hooks") or {}
    for entry in hooks_root.get("PreToolUse", []) or []:
        matcher = entry.get("matcher") or ""
        if "Bash" not in matcher.split("|"):
            continue
        for hook in entry.get("hooks", []) or []:
            if hook.get("type") != "command":
                continue
            cmd = (hook.get("command") or "").strip()
            if not cmd:
                continue
            # Heuristic: take the first whitespace-separated token; if it
            # points at a file in the repo, treat as a script path. Inline
            # commands (jq | grep | echo …) are kept as raw command bodies
            # via the literal command string itself.
            first = cmd.split()[0]
            scripts.append(Path(first))
    return scripts


def _gate_keyword_hits(text: str) -> set[str]:
    hits: set[str] = set()
    if not text:
        return hits
    for pattern, label in _GATE_KEYWORDS.items():
        # POSIX-class shortcut [[:space:]] is not Python-regex syntax; map to \s.
        py_pattern = pattern.replace("[[:space:]]", r"\s")
        if re.search(py_pattern, text):
            hits.add(label)
    return hits


def _scan_client_dir(client_dir: Path) -> set[str]:
    """Return the union of gate keywords found anywhere under a client config dir."""
    if not client_dir.is_dir():
        return set()
    hits: set[str] = set()
    for path in client_dir.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix in {".png", ".jpg", ".jpeg", ".gif", ".pdf"}:
            continue
        hits |= _gate_keyword_hits(_read_text(path))
    return hits


def _scan_path(path: Path) -> set[str]:
    """Return gate keywords found in a single file or directory tree."""
    if path.is_file():
        return _gate_keyword_hits(_read_text(path))
    if path.is_dir():
        return _scan_client_dir(path)
    return set()


def scan(ctx: OpsContext) -> ScanResult:
    project_root = ctx.project_root
    claude_settings_path = project_root / ".claude" / "settings.json"
    if not claude_settings_path.is_file():
        return ScanResult(
            issues=[],
            summary="No .claude/settings.json — nothing to compare",
            severity="info",
            items_scanned=0,
        )

    try:
        claude_settings = json.loads(_read_text(claude_settings_path))
    except json.JSONDecodeError:
        return ScanResult(
            issues=[
                make_issue(
                    category=name,
                    detail="Could not parse .claude/settings.json",
                    kind="broken",
                    root_cause_type="repo_bug",
                    fixability="manual",
                )
            ],
            summary="Malformed .claude/settings.json blocks parity scan",
            severity="error",
            health="broken",
        )

    scripts = _list_pretooluse_bash_scripts(claude_settings)
    claude_gate_keywords: set[str] = set()
    for script_path in scripts:
        absolute = project_root / script_path
        claude_gate_keywords |= _scan_path(absolute)
    claude_gate_keywords |= _gate_keyword_hits(json.dumps(claude_settings))

    cross_agent_keywords: set[str] = set()
    for layer in _CROSS_AGENT_LAYERS:
        cross_agent_keywords |= _scan_path(project_root / layer)

    other_clients: dict[str, set[str]] = {}
    for client_name, dir_name in _CLIENT_CONFIG_DIRS:
        if client_name == "claude":
            continue
        other_clients[client_name] = _scan_client_dir(project_root / dir_name)

    issues: list[dict] = []
    items_scanned = len(_GATE_KEYWORDS)

    for keyword in sorted(claude_gate_keywords):
        if keyword in cross_agent_keywords:
            continue  # gate is cross-agent already
        peers = sorted(
            client
            for client, hits in other_clients.items()
            if keyword in hits
        )
        if peers:
            # Some other client also enforces it — partial parity, but at
            # least not Claude-exclusive. Still report so we can decide
            # whether to lift to a single shared layer.
            severity = "warning"
            kind = "actionable"
        else:
            severity = "warning"
            kind = "actionable"
        issues.append(
            make_issue(
                category=name,
                detail=(
                    f"Gate keyword '{keyword}' enforced in Claude only"
                    + (f" (also: {', '.join(peers)})" if peers else "")
                    + " — no peer in cross-agent layer (.githooks/, .pre-commit-config.yaml)"
                ),
                kind=kind,
                root_cause_type="config_drift",
                fixability="manual",
                gate_keyword=keyword,
                claude_only=not peers,
                peers=peers,
            )
        )

    if ctx.difficulty >= 1 and issues:
        # At d1+ also emit an evolution gap if no cross-agent layer carries
        # ANY of the gate keywords — a sign that cross-agent enforcement is
        # underbuilt as a category, not just a per-keyword miss.
        if not cross_agent_keywords and claude_gate_keywords:
            issues.append(
                evolution_gap(
                    "No cross-agent enforcement layer carries any of the Claude "
                    "Bash gate keywords. Consider lifting at least one shared "
                    "rule (e.g. dashboard-shortcut-blocker) into .githooks/ or "
                    ".pre-commit-config.yaml so non-Claude clients are gated too."
                )
            )

    if not issues:
        return ScanResult(
            issues=[],
            summary=(
                f"All {len(claude_gate_keywords)} Claude gate keywords have a "
                "cross-agent peer."
            ),
            severity="info",
            items_scanned=items_scanned,
        )

    return ScanResult(
        issues=issues,
        summary=f"{len(issues)} gate keyword(s) enforced in Claude only",
        severity="warning",
        items_scanned=items_scanned,
    )


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    """Report-only: parity gaps need human design judgement."""
    if not issues:
        return FixResult(success=True, summary="No parity gaps to report", fix_type="report")

    if ctx.dry_run:
        return FixResult(
            success=True,
            summary=f"Dry run: would write parity report with {len(issues)} gap(s)",
            fix_type="report",
        )

    actionable = [issue for issue in issues if issue.get("kind") == "actionable"]
    report_path = write_report(
        ctx,
        "agent-config-parity-latest.json",
        {
            "issues": issues,
            "actionable_count": len(actionable),
        },
    )
    return FixResult(
        success=True,
        summary=(
            f"{len(actionable)} parity gap(s) require manual cross-agent generalization "
            f"(report: {report_path})"
        ),
        fix_type="report",
        actions=[{"report": str(report_path)}],
    )
