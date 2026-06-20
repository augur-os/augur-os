"""Audit report formatting and CLI entry point.

Split from audit.py for module size management.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List

from audit import (
    PluginAudit,
    _out,
    detect_profile,
    discover_plugins,
    load_spec,
    audit_plugin,
    audit_all_plugins,
)


def format_audit_report(audits: List[PluginAudit], show_profiles: bool = True) -> str:
    """Format audit results as a report (ADR-040: includes profile info)."""
    lines = []
    lines.append("=" * 60)
    lines.append("Plugin Compliance Audit Report (ADR-040)")
    lines.append("=" * 60)
    lines.append("")

    # Summary
    total_plugins = len(audits)
    passing = sum(1 for a in audits if a.status == "pass")
    warning = sum(1 for a in audits if a.status == "warn")
    failing = sum(1 for a in audits if a.status == "fail")

    lines.append(f"Total plugins: {total_plugins}")
    lines.append(f"Passing (90%+): {passing}")
    lines.append(f"Warning (70-90%): {warning}")
    lines.append(f"Failing (<70%): {failing}")

    if show_profiles:
        # Count profiles
        profile_counts: dict[str, int] = {}
        for audit in audits:
            profile = detect_profile(Path(audit.plugin_path))
            profile_counts[profile] = profile_counts.get(profile, 0) + 1
        lines.append("")
        lines.append("Profiles:")
        for prof in ["minimal", "standard", "full"]:
            count = profile_counts.get(prof, 0)
            lines.append(f"  {prof}: {count}")

    lines.append("")

    # Per-plugin details
    for audit in sorted(audits, key=lambda a: a.score, reverse=True):
        status_icon = {"pass": "✅", "warn": "⚠️", "fail": "❌"}[audit.status]
        profile = detect_profile(Path(audit.plugin_path))
        lines.append(f"{status_icon} {audit.plugin_name} ({audit.bundle}) " f"[{profile}]: {audit.score:.1f}%")

        if audit.failed > 0:
            failed_results = [r for r in audit.results if not r.passed]
            for r in failed_results[:5]:
                lines.append(f"   ⛔ {r.message}")
                if r.file_path:
                    lines.append(f"      {r.file_path}")
            if len(failed_results) > 5:
                lines.append(f"   ... and {len(failed_results) - 5} more issues")

        lines.append("")

    return "\n".join(lines)


def cli():
    """CLI entry point (ADR-040: profile-aware auditing)."""
    parser = argparse.ArgumentParser(
        description="Audit Augur plugins for compliance (ADR-040 profile-aware)",
    )
    parser.add_argument(
        "--name",
        "-n",
        default=None,
        help="Plugin name to audit (default: all)",
    )
    parser.add_argument(
        "--profile",
        "-p",
        default=None,
        choices=["minimal", "standard", "full"],
        help="Only audit plugins matching this profile",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Auto-fix simple issues (not implemented)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )

    args = parser.parse_args()

    try:
        spec = load_spec()
    except FileNotFoundError as e:
        _out(f"❌ Error: {e}")
        sys.exit(1)

    if args.name:
        # Audit specific plugin
        plugins = discover_plugins()
        found = [(b, n, p, prof) for b, n, p, prof in plugins if n == args.name]
        if not found:
            _out(f"❌ Plugin not found: {args.name}")
            sys.exit(1)
        bundle, plugin_name, plugin_path, profile = found[0]
        audit = audit_plugin(plugin_path, plugin_name, bundle, spec, profile)
        audits = [audit]
    else:
        # Audit all (optionally filtered by profile)
        audits = audit_all_plugins(spec, args.profile)

    if args.json:
        output = []
        for audit in audits:
            profile = detect_profile(Path(audit.plugin_path))
            output.append(
                {
                    "plugin_name": audit.plugin_name,
                    "plugin_path": audit.plugin_path,
                    "bundle": audit.bundle,
                    "profile": profile,
                    "score": audit.score,
                    "status": audit.status,
                    "passed": audit.passed,
                    "failed": audit.failed,
                    "results": [
                        {
                            "rule": r.rule,
                            "passed": r.passed,
                            "message": r.message,
                            "file_path": r.file_path,
                            "line_number": r.line_number,
                        }
                        for r in audit.results
                    ],
                }
            )
        _out(json.dumps(output, indent=2))
    else:
        report = format_audit_report(audits)
        _out(report)

    # Exit with error if any failing
    if any(a.status == "fail" for a in audits):
        sys.exit(1)
