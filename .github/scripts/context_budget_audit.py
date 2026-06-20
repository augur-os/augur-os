#!/usr/bin/env python3
"""
Context Budget Audit

Measures every consumer of the Claude Code session context budget at startup
and flags regressions against configurable thresholds.

Usage:
    python3 .github/scripts/context_budget_audit.py [--json] [--save] [--strict]

Options:
    --json    Output as JSON (for CI integration)
    --save    Save report to state/metrics/context_budget_audit.json
    --strict  Exit code 1 if any threshold exceeded (for nightly CI)

Consumers measured:
    1. MEMORY.md          — persistent auto-memory loaded every session
    2. CLAUDE.md          — project instructions
    3. Skill registry     — project-brain/capabilities/skills/*/SKILL.md files
    4. MCP tool schemas   — tool definitions from .mcp.json servers
    5. Git status         — dirty working tree snapshot
    6. Memory topic files — decisions.md, patterns.md, etc.

Token estimation: ~4 chars per token (matches token_estimator.py convention).
"""

import json
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


def get_project_root() -> Path:
    """Get the project root directory."""
    script_dir = Path(__file__).resolve().parent
    return script_dir.parent.parent


def get_state_dir(root: Path) -> Path:
    """Resolve canonical state directory."""
    try:
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from src.config.paths import get_state_dir as resolve_state_dir

        return resolve_state_dir()
    except Exception:
        return Path.home() / "Library" / "Application Support" / "Augur" / "state"


# ─── Thresholds ──────────────────────────────────────────────────────────────
# Each consumer has a max_bytes threshold. Exceeding it triggers a warning
# (or exit 1 in --strict mode).

THRESHOLDS = {
    "memory_md": {
        "label": "MEMORY.md",
        "max_bytes": 15_000,
        "max_lines": 200,
        "description": "Persistent auto-memory loaded every session",
    },
    "claude_md": {
        "label": "CLAUDE.md",
        "max_bytes": 8_000,
        "description": "Project instructions",
    },
    "skill_registry": {
        "label": "Skill registry",
        "max_count": 50,
        "max_total_bytes": 200_000,
        "description": "project-brain/capabilities/skills/*/SKILL.md — names/descriptions loaded, full content on-demand",
    },
    "mcp_tools": {
        "label": "MCP tool schemas",
        "max_count": 60,
        "description": "Tool definitions from MCP servers",
    },
    "git_status": {
        "label": "Git status",
        "max_bytes": 5_000,
        "description": "Dirty working tree snapshot",
    },
    "memory_topic_files": {
        "label": "Memory topic files",
        "max_bytes": 80_000,
        "description": "decisions.md, patterns.md, etc. (not auto-loaded but referenced)",
    },
}

TOKEN_BUDGET = 200_000


# ─── Data ────────────────────────────────────────────────────────────────────

@dataclass
class ConsumerMeasurement:
    key: str
    label: str
    description: str
    bytes: int = 0
    lines: int = 0
    count: int = 0
    est_tokens: int = 0
    threshold_exceeded: bool = False
    warnings: list[str] = field(default_factory=list)

    @property
    def pct_of_budget(self) -> float:
        return (self.est_tokens / TOKEN_BUDGET) * 100 if TOKEN_BUDGET else 0


def estimate_tokens(byte_count: int) -> int:
    """Estimate tokens from byte count (~4 chars per token)."""
    return byte_count // 4


# ─── Measurement functions ───────────────────────────────────────────────────

def measure_memory_md(root: Path) -> ConsumerMeasurement:
    """Measure MEMORY.md — the biggest offender."""
    m = ConsumerMeasurement(
        key="memory_md",
        label=THRESHOLDS["memory_md"]["label"],
        description=THRESHOLDS["memory_md"]["description"],
    )

    # Check both possible locations
    candidates = [
        root / ".claude" / "memory" / "MEMORY.md",
    ]
    # Also check the home-dir project memory path
    home_project_path = Path.home() / ".claude" / "projects"
    if home_project_path.exists():
        for project_dir in home_project_path.iterdir():
            candidate = project_dir / "memory" / "MEMORY.md"
            if candidate.exists():
                candidates.append(candidate)

    # Use the largest one found
    for candidate in candidates:
        if candidate.exists():
            size = candidate.stat().st_size
            if size > m.bytes:
                m.bytes = size
                m.lines = sum(1 for _ in open(candidate, encoding="utf-8", errors="ignore"))

    m.est_tokens = estimate_tokens(m.bytes)

    threshold = THRESHOLDS["memory_md"]
    if m.bytes > threshold["max_bytes"]:
        m.threshold_exceeded = True
        m.warnings.append(
            f"MEMORY.md is {m.bytes:,} bytes (threshold: {threshold['max_bytes']:,}). "
            f"Run `memory_sync.py --sync` to curate."
        )
    if m.lines >= threshold["max_lines"]:
        m.warnings.append(
            f"MEMORY.md has {m.lines} lines (max: {threshold['max_lines']}). "
            f"Lines after 200 are truncated by Claude Code."
        )

    return m


def measure_claude_md(root: Path) -> ConsumerMeasurement:
    """Measure CLAUDE.md project instructions."""
    m = ConsumerMeasurement(
        key="claude_md",
        label=THRESHOLDS["claude_md"]["label"],
        description=THRESHOLDS["claude_md"]["description"],
    )

    claude_md = root / "CLAUDE.md"
    if claude_md.exists():
        m.bytes = claude_md.stat().st_size
        m.lines = sum(1 for _ in open(claude_md, encoding="utf-8", errors="ignore"))

    m.est_tokens = estimate_tokens(m.bytes)

    threshold = THRESHOLDS["claude_md"]
    if m.bytes > threshold["max_bytes"]:
        m.threshold_exceeded = True
        m.warnings.append(
            f"CLAUDE.md is {m.bytes:,} bytes (threshold: {threshold['max_bytes']:,}). "
            f"Move verbose sections to on-demand topic docs."
        )

    return m


def measure_skill_registry(root: Path) -> ConsumerMeasurement:
    """Measure project-brain/capabilities/skills/*/SKILL.md files.

    Claude Code loads skill names and YAML frontmatter (description, visibility,
    context, agent) at startup for the registry. Full SKILL.md content is loaded
    on-demand when a skill is invoked. We estimate the startup cost as
    ~80 bytes per skill (name + frontmatter fields).
    """
    m = ConsumerMeasurement(
        key="skill_registry",
        label=THRESHOLDS["skill_registry"]["label"],
        description=THRESHOLDS["skill_registry"]["description"],
    )

    total_content_bytes = 0
    skills_dir = root / "project-brain" / "capabilities" / "skills"
    if skills_dir.exists():
        for skill_dir in sorted(skills_dir.iterdir()):
            skill_md = skill_dir / "SKILL.md"
            if skill_md.exists():
                m.count += 1
                total_content_bytes += skill_md.stat().st_size

    # Startup cost: only metadata (~80 bytes per skill for name + frontmatter)
    m.bytes = m.count * 80
    m.est_tokens = estimate_tokens(m.bytes)
    # Store full content size for reference
    m.lines = total_content_bytes  # repurpose lines field for total content bytes

    threshold = THRESHOLDS["skill_registry"]
    if m.count > threshold["max_count"]:
        m.threshold_exceeded = True
        m.warnings.append(
            f"{m.count} skills registered (threshold: {threshold['max_count']}). "
            f"Archive rarely-used skills."
        )
    if total_content_bytes > threshold["max_total_bytes"]:
        m.warnings.append(
            f"Skills total {total_content_bytes:,} bytes on-demand content "
            f"(threshold: {threshold['max_total_bytes']:,}). "
            f"Trim verbose SKILL.md files."
        )

    return m


def measure_mcp_tools(root: Path) -> ConsumerMeasurement:
    """Count MCP tools from all MCP config locations."""
    m = ConsumerMeasurement(
        key="mcp_tools",
        label=THRESHOLDS["mcp_tools"]["label"],
        description=THRESHOLDS["mcp_tools"]["description"],
    )

    servers: list[str] = []

    # Check all MCP config locations Claude Code reads
    mcp_configs = [
        root / ".claude" / "mcp.json",       # Project-level (primary)
        root / ".mcp.json",                    # Legacy project-level
        Path.home() / ".claude" / "mcp.json",  # Global user-level
    ]

    for mcp_config in mcp_configs:
        if mcp_config.exists():
            try:
                with open(mcp_config) as f:
                    config = json.load(f)
                for name in (config.get("mcpServers") or {}):
                    if name not in servers:
                        servers.append(name)
            except (json.JSONDecodeError, OSError):
                pass

    m.count = len(servers)

    # Known tool counts per server (update when servers change).
    # Can't introspect actual tools without starting the MCP servers.
    known_tool_counts = {
        "augur": 34,
        "claude-in-chrome": 18,
        "claude_ai_Gmail": 6,
        "claude_ai_Google_Calendar": 9,
        "context7": 2,
    }
    total_tools = 0
    for server in servers:
        # Match by prefix for servers with variable suffixes
        matched = False
        for known, count in known_tool_counts.items():
            if server.startswith(known) or known.startswith(server):
                total_tools += count
                matched = True
                break
        if not matched:
            total_tools += 8  # default estimate for unknown servers

    m.bytes = total_tools * 150  # ~150 bytes per tool name+description in deferred list
    m.est_tokens = estimate_tokens(m.bytes)

    threshold = THRESHOLDS["mcp_tools"]
    if total_tools > threshold["max_count"]:
        m.threshold_exceeded = True
        m.warnings.append(
            f"~{total_tools} MCP tools across {m.count} servers (threshold: {threshold['max_count']}). "
            f"Disable unused servers in .claude/mcp.json."
        )

    return m


def measure_git_status(root: Path) -> ConsumerMeasurement:
    """Measure git status output size."""
    m = ConsumerMeasurement(
        key="git_status",
        label=THRESHOLDS["git_status"]["label"],
        description=THRESHOLDS["git_status"]["description"],
    )

    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, cwd=root, timeout=10,
        )
        output = result.stdout
        m.bytes = len(output.encode("utf-8"))
        m.lines = len(output.strip().splitlines()) if output.strip() else 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    m.est_tokens = estimate_tokens(m.bytes)

    threshold = THRESHOLDS["git_status"]
    if m.bytes > threshold["max_bytes"]:
        m.threshold_exceeded = True
        m.warnings.append(
            f"Git status is {m.bytes:,} bytes / {m.lines} dirty files "
            f"(threshold: {threshold['max_bytes']:,} bytes). "
            f"Commit or stash dirty files."
        )

    return m


def measure_memory_topic_files(root: Path) -> ConsumerMeasurement:
    """Measure memory topic files (decisions.md, patterns.md, etc.)."""
    m = ConsumerMeasurement(
        key="memory_topic_files",
        label=THRESHOLDS["memory_topic_files"]["label"],
        description=THRESHOLDS["memory_topic_files"]["description"],
    )

    # Check home-dir project memory
    home_project_path = Path.home() / ".claude" / "projects"
    if home_project_path.exists():
        for project_dir in home_project_path.iterdir():
            memory_dir = project_dir / "memory"
            if memory_dir.exists():
                for f in sorted(memory_dir.iterdir()):
                    if f.suffix == ".md" and f.name != "MEMORY.md":
                        m.count += 1
                        m.bytes += f.stat().st_size

    m.est_tokens = estimate_tokens(m.bytes)

    threshold = THRESHOLDS["memory_topic_files"]
    if m.bytes > threshold["max_bytes"]:
        m.threshold_exceeded = True
        m.warnings.append(
            f"Memory topic files total {m.bytes:,} bytes across {m.count} files "
            f"(threshold: {threshold['max_bytes']:,}). "
            f"These are loaded on-demand but contribute when referenced."
        )

    return m


# ─── Report ──────────────────────────────────────────────────────────────────

def run_audit(root: Path) -> dict:
    """Run the full audit and return structured results."""
    measurements = [
        measure_memory_md(root),
        measure_claude_md(root),
        measure_skill_registry(root),
        measure_mcp_tools(root),
        measure_git_status(root),
        measure_memory_topic_files(root),
    ]

    total_bytes = sum(m.bytes for m in measurements)
    total_tokens = sum(m.est_tokens for m in measurements)
    any_exceeded = any(m.threshold_exceeded for m in measurements)
    all_warnings = []
    for m in measurements:
        all_warnings.extend(m.warnings)

    return {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "token_budget": TOKEN_BUDGET,
        "total_bytes": total_bytes,
        "total_est_tokens": total_tokens,
        "total_pct_of_budget": round((total_tokens / TOKEN_BUDGET) * 100, 1),
        "any_threshold_exceeded": any_exceeded,
        "consumers": [
            {
                "key": m.key,
                "label": m.label,
                "description": m.description,
                "bytes": m.bytes,
                "lines": m.lines,
                "count": m.count,
                "est_tokens": m.est_tokens,
                "pct_of_budget": round(m.pct_of_budget, 2),
                "threshold_exceeded": m.threshold_exceeded,
                "warnings": m.warnings,
            }
            for m in measurements
        ],
        "warnings": all_warnings,
    }


def print_table(report: dict) -> None:
    """Print a human-readable audit table."""
    print("\n" + "=" * 80)
    print("CONTEXT BUDGET AUDIT")
    print(f"Generated: {report['timestamp']}")
    print(f"Token Budget: {report['token_budget']:,}")
    print("=" * 80)

    # Header
    print(f"\n{'#':<3} {'Consumer':<25} {'Bytes':>10} {'Tokens':>10} {'% Budget':>10} {'Status':>10}")
    print("-" * 72)

    for i, c in enumerate(report["consumers"], 1):
        status = "WARN" if c["threshold_exceeded"] else "OK"
        if c["warnings"]:
            status = "WARN"

        print(
            f"{i:<3} {c['label']:<25} {c['bytes']:>10,} {c['est_tokens']:>10,} "
            f"{c['pct_of_budget']:>9.1f}% {status:>10}"
        )
        # Extra detail line
        details = []
        if c["count"]:
            details.append(f"{c['count']} items")
        if c["lines"] and c["key"] != "skill_registry":
            details.append(f"{c['lines']} lines")
        elif c["key"] == "skill_registry" and c["lines"]:
            details.append(f"{c['lines']:,} bytes on-demand content")
        if details:
            print(f"    ({', '.join(details)})")

    # Total
    print("-" * 72)
    print(
        f"{'':>3} {'TOTAL':<25} {report['total_bytes']:>10,} {report['total_est_tokens']:>10,} "
        f"{report['total_pct_of_budget']:>9.1f}%"
    )

    # Warnings
    if report["warnings"]:
        print(f"\n{'WARNINGS':}")
        for w in report["warnings"]:
            print(f"  - {w}")

    # Verdict
    if report["any_threshold_exceeded"]:
        print(f"\n{'RESULT: THRESHOLD(S) EXCEEDED':}")
    else:
        print("\nRESULT: All consumers within thresholds")

    print()


def main() -> int:
    """Main entry point."""
    root = get_project_root()
    state_dir = get_state_dir(root)

    output_json = "--json" in sys.argv
    save = "--save" in sys.argv
    strict = "--strict" in sys.argv

    report = run_audit(root)

    if output_json:
        print(json.dumps(report, indent=2))
    else:
        print_table(report)

    if save:
        metrics_dir = state_dir / "metrics"
        metrics_dir.mkdir(parents=True, exist_ok=True)
        out_file = metrics_dir / "context_budget_audit.json"
        with open(out_file, "w") as f:
            json.dump(report, f, indent=2)
        if not output_json:
            print(f"Report saved to: {out_file}")

    if strict and report["any_threshold_exceeded"]:
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
