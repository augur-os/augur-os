"""auto-mcp-health-audit: End-to-end MCP health audit with 4 phases."""

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
import difflib
import json
import re
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from src.config.paths import get_project_root, get_runtime_dir
from src.lib.mcp_client_config_audit import Finding as ClientConfigFinding
from src.lib.mcp_client_config_audit import audit_all as audit_client_configs
from src.lib.mcp_client_config_audit import repair_all as repair_client_configs
from src.lib.path_migrations import reconcile_migrations as reconcile_root_migrations
from src.lib.ops_protocol import (
    FixClassification,
    FixResult,
    OpsContext,
    ScanResult,
    classify_fix,
    evolution_gap,
    make_issue,
    write_report,
)

name = "auto-mcp-health-audit"

DIFFICULTY_SPEC = {
    0: "Static wiring cross-reference only",
    1: "Static + runtime probe via HTTP",
    2: "Static + runtime + auto-fix safe cases",
    3: "d2 + transformResponse field validation",
    4: "d3 + scaffolded-args invocation for needs-args tools",
}

_TOOL_NAME_RE = re.compile(r'toolName:\s*["\']([^"\']+)["\']')

_PROXY_DIR = Path("apps/dashboard/app/api/[...proxy]")

# Top-level route keys are indented at exactly 2 spaces in the route files.
# Deeper-indented keys (fallback objects, nested configs) are skipped.
_ROUTE_PATH_RE = re.compile(r'^  "([^"]+)":\s*\{', re.MULTILINE)

_MCP_TOOL_RE = re.compile(
    r"@mcp\.tool\((?:[^()]|\([^()]*\))*?name\s*=\s*[\"']([^\"']+)[\"']",
    re.DOTALL,
)

_MCP_GLOBS = [
    "src/mcp/augur_core/**/*.py",
    "src/mcp/augur_framework/**/*.py",
    "src/mcp/augur_shared/**/*.py",
    "project-brain/capabilities/skills/*/scripts/mcp/**/*.py",
    ".claude/skills/*/scripts/mcp/**/*.py",
    "plugins/*/skills/*/scripts/mcp/**/*.py",
]

_ORPHAN_SUMMARY_LIMIT = 5


def extract_route_tool_names(project_root: Path) -> dict[str, list[str]]:
    """Extract all toolName values from proxy route config files.

    Returns: dict mapping toolName -> list of route paths that reference it.
    """
    proxy_dir = project_root / _PROXY_DIR
    result: dict[str, list[str]] = {}

    for filepath in sorted(proxy_dir.glob("_routes-*.ts")):
        content = filepath.read_text()

        # Find top-level route paths (exactly 2-space indent) and their toolNames
        lines = content.split("\n")
        current_route = ""
        for line in lines:
            route_match = _ROUTE_PATH_RE.match(line)
            if route_match:
                current_route = route_match.group(1)

            tool_match = _TOOL_NAME_RE.search(line)
            if tool_match and current_route:
                tool_name = tool_match.group(1)
                result.setdefault(tool_name, [])
                if current_route not in result[tool_name]:
                    result[tool_name].append(current_route)

    return result


def extract_mcp_registrations(project_root: Path) -> dict[str, str]:
    """Extract all @mcp.tool(name=...) registrations from Python files.

    Returns: dict mapping tool_name -> relative file path.
    """
    result: dict[str, str] = {}

    for glob_pattern in _MCP_GLOBS:
        for py_file in project_root.glob(glob_pattern):
            if py_file.name.startswith("test_"):
                continue
            try:
                content = py_file.read_text()
            except (OSError, UnicodeDecodeError):
                continue

            for name_match in _MCP_TOOL_RE.finditer(content):
                tool_name = name_match.group(1)
                rel_path = str(py_file.relative_to(project_root))
                result[tool_name] = rel_path

    return result


def cross_reference(
    route_tools: dict[str, list[str]],
    mcp_tools: dict[str, str],
) -> dict[str, list[dict]]:
    """Cross-reference route toolNames against MCP registrations.

    Returns dict with keys: mismatches, wired, orphans.
    """
    registered_names = set(mcp_tools.keys())
    route_names = set(route_tools.keys())

    wired = route_names & registered_names
    mismatch_names = route_names - registered_names
    orphan_names = registered_names - route_names

    mismatches = []
    for tool_name in sorted(mismatch_names):
        entry: dict = {
            "tool_name": tool_name,
            "routes": route_tools[tool_name],
            "closest_match": None,
            "distance": None,
        }
        # Fuzzy match
        close = difflib.get_close_matches(tool_name, registered_names, n=1, cutoff=0.7)
        if close:
            candidate = close[0]
            ratio = difflib.SequenceMatcher(None, tool_name, candidate).ratio()
            approx_dist = round(max(len(tool_name), len(candidate)) * (1 - ratio))
            if approx_dist <= 2:
                entry["closest_match"] = candidate
                entry["distance"] = approx_dist

        mismatches.append(entry)

    orphans = [
        {"tool_name": t, "file": mcp_tools[t]} for t in sorted(orphan_names)
    ]

    return {
        "mismatches": mismatches,
        "wired": sorted(wired),
        "orphans": orphans,
    }


def summarize_orphans(orphans: list[dict], limit: int = _ORPHAN_SUMMARY_LIMIT) -> str:
    """Summarize orphan MCP tools by owning area for bounded evolution reporting."""
    if not orphans:
        return "no uncovered groups"

    groups: Counter[str] = Counter()
    for orphan in orphans:
        file = orphan.get("file", "")
        if file.startswith("project-brain/capabilities/skills/"):
            parts = file.split("/")
            group = "/".join(parts[:3])
        elif file.startswith("skills/"):
            parts = file.split("/")
            group = "/".join(parts[:2])
        elif file.startswith("plugins/"):
            parts = file.split("/")
            group = "/".join(parts[:4])
        elif file.startswith("src/mcp/augur_core/"):
            group = "src/mcp/augur_core"
        elif file.startswith("src/mcp/augur_framework/"):
            group = "src/mcp/augur_framework"
        elif file.startswith("src/mcp/augur_shared/"):
            group = "src/mcp/augur_shared"
        else:
            group = file.split("/")[0] if file else "unknown"
        groups[group] += 1

    top_groups = ", ".join(
        f"{group} ({count})" for group, count in groups.most_common(limit)
    )
    remaining = len(groups) - min(len(groups), limit)
    if remaining > 0:
        top_groups += f", +{remaining} more"
    return top_groups


# ── Phase 2: Runtime probe ──


def classify_probe_response(status_code: int, body: dict) -> dict:
    """Classify an MCP tool probe response."""
    if status_code == 200:
        if body.get("_fallback"):
            return {
                "status": "fallback-masked",
                "reason": body.get("_reason", "unknown"),
                "error_message": body.get("_error", ""),
            }
        if "error" in body and body["error"]:
            return {
                "status": "app-error",
                "error_message": str(body["error"]),
                "error_type": fingerprint_error(str(body["error"])),
            }
        return {"status": "healthy"}
    error_msg = str(body.get("error", "Unknown error"))
    return {
        "status": "runtime-error",
        "error_message": error_msg,
        "error_type": fingerprint_error(error_msg),
    }


def fingerprint_error(error_msg: str) -> str:
    """Classify error message into a fingerprint category."""
    msg = error_msg.lower()
    if "importerror" in msg or "modulenotfounderror" in msg or "no module named" in msg:
        return "import-error"
    if "filenotfounderror" in msg or "no such file" in msg:
        return "missing-file"
    if "typeerror" in msg and "required" in msg and "argument" in msg:
        return "needs-args"
    if "field required" in msg or "validation error" in msg:
        return "needs-args"
    if "keyerror" in msg:
        return "key-error"
    if "attributeerror" in msg:
        return "attribute-error"
    if "syntaxerror" in msg:
        return "syntax-error"
    return "unknown"


def probe_tool(tool_name: str, base_url: str = "http://localhost:3000") -> dict:
    """Probe a single MCP tool via HTTP POST."""
    if not base_url.lower().startswith(("http://", "https://")):
        raise ValueError(f"Non-HTTP URL rejected: {base_url!r}")
    url = f"{base_url}/api/mcp/tool"
    payload = json.dumps({"tool": tool_name, "args": {}}).encode()
    req = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:  # nosec B310  # base_url scheme-validated above
            body = json.loads(resp.read())
            result = classify_probe_response(resp.status, body)
            result["tool_name"] = tool_name
            return result
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read())
        except Exception:
            body = {"error": str(e)}
        result = classify_probe_response(e.code, body)
        result["tool_name"] = tool_name
        return result
    except urllib.error.URLError as e:
        # URLError with ConnectionRefusedError = server truly down
        if isinstance(e.reason, ConnectionRefusedError):
            return {"tool_name": tool_name, "status": "server-down", "error_message": str(e.reason)}
        return {"tool_name": tool_name, "status": "connection-error", "error_message": str(e.reason)}
    except (TimeoutError, ConnectionError, OSError) as e:
        # Per-tool disconnect (e.g., RemoteDisconnected) — not a full server outage
        return {"tool_name": tool_name, "status": "runtime-error", "error_message": str(e), "error_type": "connection-reset"}


def probe_all_tools(wired_tools: list[str], base_url: str = "http://localhost:3000") -> list[dict]:
    """Probe all wired tools. Only abort on server-down (connection refused)."""
    results = []
    for tool_name in wired_tools:
        result = probe_tool(tool_name, base_url)
        results.append(result)
        if result["status"] == "server-down":
            break
    return results


# ── Phase 3: Auto-fix ──


def fix_toolname_typo(project_root: Path, wrong_name: str, correct_name: str) -> list[str]:
    """Replace a toolName typo in proxy route files."""
    changed = []
    proxy_dir = project_root / _PROXY_DIR
    for filepath in sorted(proxy_dir.glob("_routes-*.ts")):
        content = filepath.read_text()
        if wrong_name not in content:
            continue
        classification, _ = classify_fix("code-fix", str(filepath), project_root)
        if classification == FixClassification.REVERTING:
            continue
        new_content = content.replace(f'toolName: "{wrong_name}"', f'toolName: "{correct_name}"')
        if new_content != content:
            filepath.write_text(new_content)
            changed.append(str(filepath.relative_to(project_root)))
    return changed


def fix_missing_dir(dir_path: str) -> list[str]:
    """Create a missing directory."""
    p = Path(dir_path)
    if not p.exists():
        p.mkdir(parents=True, exist_ok=True)
        return [str(p)]
    return []


def apply_safe_fixes(project_root: Path, fixable_issues: list[dict]) -> dict[str, int]:
    """Apply all safe fixes. Returns counts of applied/skipped."""
    applied = 0
    skipped = 0
    all_changes: list[str] = []
    for issue in fixable_issues:
        fix_type = issue.get("fix_type", "")
        affected = issue.get("affected_files", [])
        if len(affected) > 3:
            skipped += 1
            continue
        if fix_type == "toolname-typo":
            changes = fix_toolname_typo(project_root, issue["wrong_name"], issue["correct_name"])
            all_changes.extend(changes)
            applied += 1 if changes else 0
        elif fix_type == "missing-dir":
            changes = fix_missing_dir(issue["dir_path"])
            all_changes.extend(changes)
            applied += 1 if changes else 0
        else:
            skipped += 1
    return {"applied": applied, "skipped": skipped, "changes": all_changes}


# ── Phase 4: Report generation ──


def generate_report(audit_data: dict) -> str:
    """Generate structured markdown report from audit data."""
    p0 = audit_data.get("phase0", {})
    p1 = audit_data.get("phase1", {})
    p2 = audit_data.get("phase2", {})
    p3 = audit_data.get("phase3", {})
    client_findings = p0.get("client_config_findings", [])
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    mismatches = p1.get("mismatches", [])
    failures = p2.get("failures", [])
    fallback_masked = p2.get("fallback_masked", [])
    healthy = p2.get("healthy", [])
    orphans = p1.get("orphans", [])

    lines = [
        "---", f"generated: {now}",
        f"phase1_routes: {p1.get('route_count', 0)}",
        f"phase1_registered: {p1.get('registered_count', 0)}",
        f"phase1_mismatches: {len(mismatches)}",
        f"phase2_healthy: {len(healthy)}",
        f"phase2_fallback_masked: {len(fallback_masked)}",
        f"phase2_errors: {len(failures)}",
        f"phase3_auto_fixed: {p3.get('applied', 0)}",
        f"phase3_needs_human: {p3.get('skipped', 0)}",
        f"phase0_client_configs_scanned: {p0.get('sources_scanned', 0)}",
        f"phase0_client_config_dangling: {len(client_findings)}",
        "---", "",
    ]

    lines.append("## Client Config Integrity")
    if client_findings:
        lines.append("| Client | Config | Location | Dangling Path | Repair |")
        lines.append("|--------|--------|----------|---------------|--------|")
        for f in client_findings:
            if f.get("repairable"):
                repair = f"auto -> {f.get('successor')}"
            elif f.get("generated"):
                repair = "run `aug config sync`"
            else:
                repair = "manual (no known successor)"
            lines.append(
                f"| {f.get('client', '?')} | {Path(f.get('config_path', '')).name} | "
                f"{f.get('location', '?')} | {f.get('raw', '?')} | {repair} |"
            )
    else:
        scanned = p0.get("sources_scanned", 0)
        lines.append(f"None found ({scanned} client config(s) scanned).")
    lines.append("")

    lines.append("## Critical: Wiring Mismatches")
    if mismatches:
        lines.append("| Route Path | toolName in Route | Closest Registration | Distance | Auto-Fixed? |")
        lines.append("|------------|-------------------|---------------------|----------|-------------|")
        for m in mismatches:
            routes = ", ".join(m.get("routes", []))
            closest = m.get("closest_match") or "—"
            dist = m.get("distance") if m.get("distance") is not None else "—"
            fixed = "Yes" if m.get("auto_fixed") else "No"
            lines.append(f"| {routes} | {m['tool_name']} | {closest} | {dist} | {fixed} |")
    else:
        lines.append("None found.")
    lines.append("")

    lines.append("## Runtime Failures")
    if failures:
        lines.append("| Tool Name | Error Type | Error Message | Status |")
        lines.append("|-----------|-----------|---------------|--------|")
        for f in failures:
            lines.append(f"| {f.get('tool_name', '?')} | {f.get('error_type', '?')} | {f.get('error_message', '?')[:80]} | {f.get('status', '?')} |")
    else:
        lines.append("None found.")
    lines.append("")

    lines.append("## Fallback-Masked")
    if fallback_masked:
        lines.append("| Tool Name | Reason | Error |")
        lines.append("|-----------|--------|-------|")
        for f in fallback_masked:
            lines.append(f"| {f.get('tool_name', '?')} | {f.get('reason', '?')} | {f.get('error_message', '')[:80]} |")
    else:
        lines.append("None found.")
    lines.append("")

    lines.append("## Healthy")
    if healthy:
        tool_list = ", ".join(h["tool_name"] for h in healthy[:20])
        lines.append(f"{len(healthy)} tools healthy: {tool_list}")
        if len(healthy) > 20:
            lines.append(f"... and {len(healthy) - 20} more")
    else:
        lines.append("No tools probed.")
    lines.append("")

    lines.append("## Orphan Tools")
    if orphans:
        lines.append("| Tool Name | File |")
        lines.append("|-----------|------|")
        for o in orphans:
            lines.append(f"| {o['tool_name']} | {o['file']} |")
    else:
        lines.append("None found.")

    return "\n".join(lines)


# ── OpsCommand protocol: scan() and fix() ──


def _make_issue(*, category: str, **kwargs: object) -> dict:
    """Wrap make_issue and inject category into the returned dict."""
    issue = make_issue(category=category, **kwargs)  # type: ignore[arg-type]
    issue["category"] = category
    return issue


def scan(ctx: OpsContext) -> ScanResult:
    """Run MCP health audit scan at the given difficulty level."""
    project_root = ctx.project_root
    difficulty = ctx.difficulty
    issues: list[dict] = []

    # ── Phase 1: Static wiring audit (always) ──
    route_tools = extract_route_tool_names(project_root)
    mcp_tools = extract_mcp_registrations(project_root)

    # ADR-465 / commit a688ad5ca: the catch-all proxy route layer was deleted
    # and dashboard pages now call MCP directly. The legacy [...proxy] dir
    # never reappears, so route extraction now always returns 0 routes — and
    # the original `orphans = registered - routes` calculation flagged every
    # registered MCP tool as orphaned, every single run.
    proxy_dir = project_root / _PROXY_DIR
    proxy_present = proxy_dir.is_dir() and any(proxy_dir.glob("_routes-*.ts"))
    if not proxy_present:
        # Skip cross-reference entirely; nothing to wire against. Phase 2 has
        # no wired tools to probe, so the audit becomes inventory-only.
        xref = {"mismatches": [], "wired": [], "orphans": []}
    else:
        xref = cross_reference(route_tools, mcp_tools)

    route_count = sum(len(v) for v in route_tools.values())
    registered_count = len(mcp_tools)

    for m in xref["mismatches"]:
        detail = f'{m["tool_name"]} referenced in routes [{", ".join(m["routes"])}] but not registered'
        if m.get("closest_match"):
            detail += f' (closest: {m["closest_match"]}, distance: {m["distance"]})'
        issues.append(
            _make_issue(
                category="wiring-mismatch",
                detail=detail,
                path=", ".join(m["routes"]),
                kind="actionable",
                root_cause_type="repo_bug",
                fixability="auto" if m.get("closest_match") else "manual",
                closest_match=m.get("closest_match"),
                distance=m.get("distance"),
                wrong_name=m["tool_name"],
            )
        )

    audit_data: dict = {
        "phase1": {
            "route_count": route_count,
            "registered_count": registered_count,
            "mismatches": xref["mismatches"],
            "wired": xref["wired"],
            "orphans": xref["orphans"],
            "orphan_summary": summarize_orphans(xref["orphans"]),
            "proxy_present": proxy_present,
        },
        "phase2": {"healthy": [], "failures": [], "fallback_masked": []},
        "phase3": {"applied": 0, "skipped": 0, "changes": []},
        "phase0": {"client_config_findings": [], "sources_scanned": 0},
    }

    # ── Phase 0: client MCP config integrity (always) ──
    # External, client-owned MCP configs (Claude Desktop config + DXT extension
    # settings, project .mcp.json, Codex, Gemini) can reference directories that
    # no longer exist after an Augur root moves — a class invisible to the
    # wiring/probe phases, which only inspect Augur's own tools. A dangling path
    # crash-loops the client's MCP server silently. See
    # src/lib/mcp_client_config_audit.py.
    #
    # Migration hook: on real runs, first reconcile canonical roots — if a root
    # (documents/vault/…) moved since the last run it is auto-recorded in
    # path_migrations.yaml, so the detection below finds and the fixer heals the
    # now-dangling client refs with no manual map entry.
    if not ctx.dry_run:
        try:
            reconcile_root_migrations()
        except Exception:  # noqa: BLE001 — reconcile must never break the audit
            pass
    client_outcome = audit_client_configs()
    audit_data["phase0"]["sources_scanned"] = client_outcome.sources_scanned
    for cf in client_outcome.findings:
        audit_data["phase0"]["client_config_findings"].append(
            {
                "client": cf.client,
                "config_path": cf.config_path,
                "location": cf.location,
                "raw": cf.raw,
                "successor": cf.successor,
                "generated": cf.generated,
                "repairable": cf.repairable,
            }
        )
        issues.append(
            _make_issue(
                category="client-config-dangling-path",
                detail=cf.detail,
                path=cf.config_path,
                kind="environment",
                root_cause_type="env_runtime",
                fixability="auto" if cf.repairable else "manual",
                client=cf.client,
                location=cf.location,
                raw=cf.raw,
                successor=cf.successor,
                generated=cf.generated,
            )
        )

    # ── Phase 2: Runtime probe (d >= 1) ──
    if difficulty >= 1 and xref["wired"]:
        probe_results = probe_all_tools(xref["wired"])
        for pr in probe_results:
            status = pr.get("status", "unknown")
            if status == "healthy":
                audit_data["phase2"]["healthy"].append(pr)
            elif status == "fallback-masked":
                audit_data["phase2"]["fallback_masked"].append(pr)
                issues.append(
                    _make_issue(
                        category="fallback-masked",
                        detail=f'{pr["tool_name"]} returns fallback data: {pr.get("reason", "unknown")}',
                        kind="actionable",
                        root_cause_type="env_runtime",
                        error_message=pr.get("error_message", ""),
                    )
                )
            elif status == "needs-args":
                audit_data["phase2"].setdefault("needs_args", []).append(pr)
            elif status == "server-down":
                issues.append(
                    _make_issue(
                        category="server-down",
                        detail=f'MCP server unreachable: {pr.get("error_message", "")}',
                        kind="environment",
                    )
                )
                break
            elif status != "healthy":
                error_type = pr.get("error_type", fingerprint_error(pr.get("error_message", "")))
                # Tools that fail due to missing required args are not broken
                if error_type == "needs-args":
                    audit_data["phase2"].setdefault("needs_args", []).append(pr)
                    continue
                audit_data["phase2"]["failures"].append(pr)
                fixability = "auto" if error_type == "missing-file" else "manual"
                issues.append(
                    _make_issue(
                        category="runtime-failure",
                        detail=f'{pr["tool_name"]}: {pr.get("error_message", "unknown error")}',
                        kind="actionable",
                        root_cause_type="env_runtime",
                        fixability=fixability,
                        error_type=error_type,
                        tool_name=pr["tool_name"],
                    )
                )

    # ── Phase 4: Report (always) ──
    report_md = generate_report(audit_data)
    if not ctx.dry_run:
        try:
            write_report(ctx, "mcp-health-report.json", audit_data)
            report_dir = get_runtime_dir() / "reports"
            report_dir.mkdir(parents=True, exist_ok=True)
            (report_dir / "mcp-health-report.md").write_text(report_md)
        except OSError:
            pass

    # Evolution gaps
    if not issues and difficulty >= 2:
        needs_args_count = len(audit_data["phase2"].get("needs_args", []))
        if not proxy_present:
            # Proxy route layer was retired (ADR-465 / commit a688ad5ca).
            # Phase 1 cross-reference is moot until the audit is rewritten
            # against the direct-MCP wiring used by current dashboard pages.
            gap_detail = (
                f"{registered_count} MCP tools registered. The [...proxy] route layer "
                "was retired, so legacy proxy-vs-MCP cross-referencing is skipped. "
                "Next: rewrite Phase 1 to walk dashboard pages and verify each direct "
                "MCP call resolves to a registered tool."
            )
        else:
            gap_detail = f"{len(xref['wired'])} tools wired and healthy."
            if needs_args_count:
                gap_detail += f" {needs_args_count} tools skipped (need args)."
            orphan_count = len(xref["orphans"])
            if orphan_count:
                gap_detail += (
                    f" {orphan_count} MCP tools are outside dashboard proxy coverage"
                    f" ({audit_data['phase1']['orphan_summary']})."
                    " Next: audit whether any should expose dashboard routes or move them into an agent-only MCP coverage loop."
                )
            else:
                gap_detail += " Next: validate transformResponse field names match MCP output keys (d3)."
        issues.append(evolution_gap(gap_detail, category="evolution"))

    # Determine health
    mismatch_count = len([i for i in issues if i.get("category") == "wiring-mismatch"])
    failure_count = len([i for i in issues if i.get("category") in ("runtime-failure", "fallback-masked")])
    client_config_count = len([i for i in issues if i.get("category") == "client-config-dangling-path"])

    if mismatch_count > 0 or failure_count > 5:
        health = "broken"
        severity = "error"
    elif failure_count > 0 or client_config_count > 0:
        health = "degraded"
        severity = "warning"
    else:
        health = "verified"
        severity = "info"

    summary = (
        f"Routes: {route_count}, Registered: {registered_count}, "
        f"Mismatches: {mismatch_count}, "
        f"Runtime failures: {failure_count}, "
        f"Client-config dangling: {client_config_count}, "
        f"Healthy: {len(audit_data['phase2']['healthy'])}"
    )

    return ScanResult(
        issues=issues,
        summary=summary,
        severity=severity,
        health=health,
        items_scanned=route_count,
    )


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    """Apply safe fixes for issues found by scan(). Only at d >= 2."""
    if ctx.difficulty < 2:
        return FixResult(
            success=True, actions=[], changes=[],
            summary="Auto-fix requires difficulty >= 2",
            fix_type="report",
        )

    fixable: list[dict] = []
    for issue in issues:
        cat = issue.get("category", "")
        if cat == "wiring-mismatch" and issue.get("closest_match"):
            proxy_dir = ctx.project_root / _PROXY_DIR
            affected = [f.name for f in proxy_dir.glob("_routes-*.ts")]
            fixable.append({
                "fix_type": "toolname-typo",
                "wrong_name": issue["wrong_name"],
                "correct_name": issue["closest_match"],
                "affected_files": affected,
            })
        elif cat == "runtime-failure" and issue.get("error_type") == "missing-file":
            fixable.append({
                "fix_type": "missing-dir",
                "dir_path": "",
                "affected_files": [],
            })

    result = apply_safe_fixes(ctx.project_root, fixable)

    # Repair dangling client-config paths (e.g. a moved documents root) by
    # rewriting them to their unambiguous successor. User-owned configs only;
    # generated .mcp.json was already flagged manual by scan().
    client_changes: list[str] = []
    repairable_client = [
        i
        for i in issues
        if i.get("category") == "client-config-dangling-path"
        and i.get("fixability") == "auto"
    ]
    if not ctx.dry_run and repairable_client:
        rebuilt = [
            ClientConfigFinding(
                client=i.get("client", ""),
                config_path=i.get("path", ""),
                location=i.get("location", ""),
                raw=i.get("raw", ""),
                expanded="",
                generated=bool(i.get("generated", False)),
                successor=i.get("successor"),
            )
            for i in repairable_client
        ]
        applied = repair_client_configs(rebuilt)
        client_changes = [
            f"{a['client']}: {a['location']} {a['old']} -> {a['new']}" for a in applied
        ]

    all_changes = result.get("changes", []) + client_changes
    total_applied = result.get("applied", 0) + len(client_changes)

    return FixResult(
        success=True, actions=[],
        changes=all_changes,
        summary=(
            f"Applied {total_applied} fixes "
            f"({len(client_changes)} client-config), skipped {result.get('skipped', 0)}"
        ),
        fix_type="code-fix" if total_applied > 0 else "report",
    )
