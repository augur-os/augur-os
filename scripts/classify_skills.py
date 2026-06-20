#!/usr/bin/env python3
"""Skill classification scanner (ADR-463, Task 6).

Iterates all skill directories in skills/, parses SKILL.md frontmatter,
checks directory structure, and classifies each skill into one of 7 types:
  template, autoloop, domain, runbook, command, meta

Outputs a markdown report to stdout.
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

import yaml


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills"

VALID_TYPES = ("template", "autoloop", "domain", "runbook", "command", "meta")

# Skills classified as "meta" by name (system orchestration / skills-about-skills)
META_NAMES = frozenset({
    "advisor",
    "platform-admin",
    "developer",
    "evolve",
    "discovery",
    "workflows",
    "mcp-app-factory",
    "page-builder",
    "executor",
    "ai",
    "renderer",
    "focus",
})


# ---------------------------------------------------------------------------
# Frontmatter parser
# ---------------------------------------------------------------------------

def parse_frontmatter(skill_md: Path) -> dict:
    """Parse YAML frontmatter from SKILL.md.

    Handles the <!-- AUGUR-ADAPTED-COPY --> comment that may appear
    before the opening '---' fence.
    """
    if not skill_md.exists():
        return {}

    text = skill_md.read_text(encoding="utf-8")

    # Strip leading HTML comments (e.g. <!-- AUGUR-ADAPTED-COPY ... -->)
    text = re.sub(r"^<!--.*?-->\s*", "", text, flags=re.DOTALL)

    # Match YAML frontmatter between --- fences
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return {}

    try:
        data = yaml.safe_load(m.group(1))
        return data if isinstance(data, dict) else {}
    except yaml.YAMLError:
        return {}


# ---------------------------------------------------------------------------
# Directory structure checks
# ---------------------------------------------------------------------------

def has_augur_api(skill_dir: Path) -> bool:
    return (skill_dir / "augur" / "api").is_dir()


def has_augur_dashboard(skill_dir: Path) -> bool:
    return (skill_dir / "augur" / "dashboard").is_dir()


def has_ops_scripts(skill_dir: Path) -> bool:
    scripts_dir = skill_dir / "scripts"
    if not scripts_dir.is_dir():
        return False
    return any(scripts_dir.glob("*_ops.py"))


# ---------------------------------------------------------------------------
# Frontmatter field helpers
# ---------------------------------------------------------------------------

def has_dashboard_pages(fm: dict) -> bool:
    """True if x-augur-dashboard-pages has >0 entries."""
    val = fm.get("x-augur-dashboard-pages")
    if isinstance(val, list) and len(val) > 0:
        return True
    return False


def has_mcp_tools(fm: dict) -> bool:
    """True if x-augur-mcp-tools has >0 entries."""
    val = fm.get("x-augur-mcp-tools")
    if isinstance(val, list) and len(val) > 0:
        return True
    return False


def has_loop(fm: dict) -> bool:
    return "x-augur-loop" in fm


# ---------------------------------------------------------------------------
# Classification engine
# ---------------------------------------------------------------------------

def classify(name: str, skill_dir: Path, fm: dict) -> str:
    """Apply classification rules in priority order. First match wins."""
    # 1. template
    if name.endswith("-template"):
        return "template"

    # 2. autoloop
    if name.startswith("auto-") or has_loop(fm):
        return "autoloop"

    # 3. domain
    if (has_augur_api(skill_dir)
            or has_augur_dashboard(skill_dir)
            or has_dashboard_pages(fm)
            or has_mcp_tools(fm)):
        return "domain"

    # 4. runbook
    if name.startswith("runbook-") or name == "debug-protocol":
        return "runbook"

    # 5. meta
    if name in META_NAMES:
        return "meta"

    # 7. fallback
    return "command"


# ---------------------------------------------------------------------------
# Anomaly detection
# ---------------------------------------------------------------------------

def detect_anomalies(
    name: str,
    skill_type: str,
    skill_dir: Path,
    fm: dict,
    all_descriptions: dict[str, str],
) -> list[tuple[str, str]]:
    """Return list of (anomaly_type, detail) tuples."""
    anomalies: list[tuple[str, str]] = []

    # type-straddler: classified as autoloop but also has domain signals
    if skill_type == "autoloop":
        domain_signals = []
        if has_augur_api(skill_dir):
            domain_signals.append("augur/api/")
        if has_augur_dashboard(skill_dir):
            domain_signals.append("augur/dashboard/")
        if has_dashboard_pages(fm):
            domain_signals.append("x-augur-dashboard-pages")
        if domain_signals:
            anomalies.append((
                "type-straddler",
                f"autoloop with domain signals: {', '.join(domain_signals)}"
            ))

    # underpowered-domain: classified as domain but no actual dirs
    if skill_type == "domain":
        if not has_augur_api(skill_dir) and not has_augur_dashboard(skill_dir):
            # Only flagged if classification came from frontmatter alone
            anomalies.append((
                "underpowered-domain",
                "domain via frontmatter only — no augur/api/ or augur/dashboard/ dirs"
            ))

    # duplicate-trigger: near-duplicate descriptions (exact substring >=40 chars)
    desc = fm.get("description", "")
    if isinstance(desc, str) and len(desc) >= 40:
        for other_name, other_desc in all_descriptions.items():
            if other_name == name:
                continue
            if not isinstance(other_desc, str) or len(other_desc) < 40:
                continue
            # Check exact substring match (longer of min 40 chars)
            if desc in other_desc or other_desc in desc:
                anomalies.append((
                    "duplicate-trigger",
                    f"description overlaps with '{other_name}'"
                ))
                break  # only flag once per skill

    return anomalies


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def generate_report(
    classifications: list[dict],
    flagged: list[dict],
) -> str:
    """Generate markdown report."""
    lines: list[str] = []

    # Header
    lines.append("# Skill Classification Report (ADR-463)")
    lines.append("")
    lines.append(f"Generated by `scripts/classify_skills.py`")
    lines.append("")

    # Summary stats
    type_counts: dict[str, int] = defaultdict(int)
    for c in classifications:
        type_counts[c["type"]] += 1

    lines.append("## Summary")
    lines.append("")
    lines.append(f"| Metric | Count |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Total skills scanned | {len(classifications)} |")
    for t in VALID_TYPES:
        lines.append(f"| {t} | {type_counts.get(t, 0)} |")
    lines.append(f"| Flagged for review | {len(flagged)} |")
    lines.append("")

    # Clean classifications table
    lines.append("## Clean Classifications")
    lines.append("")
    lines.append("| Skill | Type | Signal |")
    lines.append("|-------|------|--------|")

    clean = [c for c in classifications if not c.get("anomalies")]
    clean.sort(key=lambda c: (VALID_TYPES.index(c["type"]), c["name"]))
    for c in clean:
        lines.append(f"| {c['name']} | {c['type']} | {c['signal']} |")
    lines.append("")

    # Flagged for review
    if flagged:
        lines.append("## Flagged for Review")
        lines.append("")
        lines.append("| Skill | Type | Anomaly | Detail |")
        lines.append("|-------|------|---------|--------|")
        flagged.sort(key=lambda f: (f["anomaly_type"], f["name"]))
        for f in flagged:
            lines.append(
                f"| {f['name']} | {f['type']} | {f['anomaly_type']} | {f['detail']} |"
            )
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if not SKILLS_DIR.is_dir():
        print(f"ERROR: skills directory not found: {SKILLS_DIR}", file=sys.stderr)
        sys.exit(1)

    # Collect all skill directories (skip non-directories and README files)
    skill_dirs = sorted(
        d for d in SKILLS_DIR.iterdir()
        if d.is_dir() and not d.name.startswith(".")
    )

    # First pass: collect all descriptions for duplicate detection
    all_descriptions: dict[str, str] = {}
    skill_data: list[tuple[str, Path, dict]] = []

    for skill_dir in skill_dirs:
        name = skill_dir.name
        skill_md = skill_dir / "SKILL.md"
        fm = parse_frontmatter(skill_md)
        skill_data.append((name, skill_dir, fm))
        desc = fm.get("description", "")
        if isinstance(desc, str):
            all_descriptions[name] = desc

    # Second pass: classify and detect anomalies
    classifications: list[dict] = []
    flagged: list[dict] = []

    for name, skill_dir, fm in skill_data:
        skill_type = classify(name, skill_dir, fm)

        # Build signal string for the report
        signal = _classification_signal(name, skill_type, skill_dir, fm)

        anomalies = detect_anomalies(name, skill_type, skill_dir, fm, all_descriptions)

        entry = {
            "name": name,
            "type": skill_type,
            "signal": signal,
            "anomalies": anomalies,
        }
        classifications.append(entry)

        for anomaly_type, detail in anomalies:
            flagged.append({
                "name": name,
                "type": skill_type,
                "anomaly_type": anomaly_type,
                "detail": detail,
            })

    report = generate_report(classifications, flagged)
    print(report)

    # Also print summary to stderr for quick reading
    type_counts: dict[str, int] = defaultdict(int)
    for c in classifications:
        type_counts[c["type"]] += 1

    print("\n--- Classification Summary ---", file=sys.stderr)
    print(f"Total: {len(classifications)}", file=sys.stderr)
    for t in VALID_TYPES:
        print(f"  {t}: {type_counts.get(t, 0)}", file=sys.stderr)
    print(f"Flagged: {len(flagged)}", file=sys.stderr)
    if flagged:
        for f in flagged:
            print(f"  [{f['anomaly_type']}] {f['name']}: {f['detail']}", file=sys.stderr)


def _classification_signal(
    name: str,
    skill_type: str,
    skill_dir: Path,
    fm: dict,
) -> str:
    """Human-readable explanation of why this type was chosen."""
    if skill_type == "template":
        return "name ends with -template"

    if skill_type == "autoloop":
        reasons = []
        if name.startswith("auto-"):
            reasons.append("name starts with auto-")
        if has_loop(fm):
            reasons.append("has x-augur-loop")
        return " + ".join(reasons) if reasons else "autoloop rule"

    if skill_type == "domain":
        reasons = []
        if has_augur_api(skill_dir):
            reasons.append("has augur/api/")
        if has_augur_dashboard(skill_dir):
            reasons.append("has augur/dashboard/")
        if has_dashboard_pages(fm):
            reasons.append("has x-augur-dashboard-pages")
        if has_mcp_tools(fm):
            reasons.append("has x-augur-mcp-tools")
        return " + ".join(reasons) if reasons else "domain rule"

    if skill_type == "runbook":
        if name.startswith("runbook-"):
            return "name starts with runbook-"
        if name == "debug-protocol":
            return "name is debug-protocol"
        return "runbook rule"

    if skill_type == "command":
        return "fallback (no strong signal)"

    if skill_type == "meta":
        return f"name in meta list"

    return "unknown"


if __name__ == "__main__":
    main()
