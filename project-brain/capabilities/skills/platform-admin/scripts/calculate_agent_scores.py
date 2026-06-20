#!/usr/bin/env python3
"""
Calculate Agent Scores for Smart Refresh.

Recalculates agent health scores and metrics:
- Skill completeness (SKILL.md, modules, references, scripts)
- Backlog status (open items, completed items)
- Activity (recent commits, last run time)
"""


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
import logging
import os
import sys
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from src.config.paths import get_project_root, get_runtime_dir

logger = logging.getLogger(__name__)


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))


def get_repo_root() -> Path:
    current = Path(__file__).resolve()
    for parent in [current] + list(current.parents):
        if (parent / ".git").exists():
            return parent
    return Path.cwd()


def get_data_dir() -> Path:
    env_data = os.environ.get("AUGUR_ROOT")
    if env_data:
        return Path(env_data).expanduser().resolve()

    paths = [
        get_project_root(),
        get_project_root(),
    ]
    for p in paths:
        if p.exists():
            return p
    return paths[0]


def analyze_skill(skill_path: Path) -> dict[str, Any]:
    """Analyze a skill directory for completeness."""
    skill_md = skill_path / "SKILL.md"

    if not skill_md.exists():
        return {"name": skill_path.name, "score": 0, "tier": "needs-attention"}

    # Check for components
    has_modules = (skill_path / "modules").exists() and any((skill_path / "modules").iterdir())
    has_references = (skill_path / "references").exists() and any((skill_path / "references").iterdir())
    has_scripts = (skill_path / "scripts").exists() and any((skill_path / "scripts").iterdir())
    has_tests = (skill_path / "tests").exists() and any((skill_path / "tests").iterdir())
    has_version = (skill_path / "augur" / "version.yaml").exists()

    # Calculate line count
    try:
        line_count = len(skill_md.read_text(encoding="utf-8").split("\n"))
    except Exception:
        line_count = 0

    # Calculate score (0-100)
    score = 20  # Base score for having SKILL.md
    if has_modules:
        score += 20
    if has_references:
        score += 15
    if has_scripts:
        score += 25
    if has_tests:
        score += 10
    if has_version:
        score += 5
    if line_count > 50:
        score += 5

    # Determine tier
    if score >= 85:
        tier = "production"
    elif score >= 60:
        tier = "functional"
    else:
        tier = "needs-attention"

    return {
        "name": skill_path.name,
        "score": score,
        "tier": tier,
        "lineCount": line_count,
        "hasModules": has_modules,
        "hasReferences": has_references,
        "hasScripts": has_scripts,
        "hasTests": has_tests,
        "hasVersion": has_version,
    }


def get_backlog_stats(data_dir: Path, agent_name: str) -> dict[str, Any]:
    """Get backlog statistics for an agent."""
    backlog_paths = [
        data_dir / "plugins" / "dev" / "skills" / agent_name / "data" / "backlog.md",
        data_dir / "plugins" / "dev" / "skills" / agent_name / "data" / "backlogs" / "backlog.md",
        data_dir / "plugins" / "dev" / "skills" / agent_name / "data" / "backlog.md",
        data_dir / "plugins" / "core" / "skills" / agent_name / "backlog.md",
    ]

    for backlog_path in backlog_paths:
        if backlog_path.exists():
            try:
                content = backlog_path.read_text(encoding="utf-8")
                completed = content.count("[x]")
                open_items = content.count("[ ]")
                return {"completed": completed, "open": open_items}
            except (OSError, UnicodeDecodeError) as exc:
                logger.debug("Failed to read backlog file %s: %s", backlog_path, exc)

    return {"completed": 0, "open": 0}


def get_growth_stats(data_dir: Path) -> dict[str, Any]:
    """Get global adaptive growth backlog statistics."""
    growth_dirs = [
        data_dir / "plugins" / "dev" / "skills" / "platform-admin" / "data" / "setup-manager" / "adaptive-growth",
        data_dir / "plugins" / "dev" / "skills" / "platform-admin" / "data" / "config" / "adaptive-growth",
    ]

    stats = {"suggested_tasks": 0, "completed_tasks": 0, "backlogs_generated": 0}

    found_dirs = [d for d in growth_dirs if d.exists()]
    if not found_dirs:
        return stats

    for growth_dir in found_dirs:
        # Use rglob to find backlogs recursively (some might be in date-subfolders)
        for backlog_file in growth_dir.rglob("growth-backlog-*.md"):
            stats["backlogs_generated"] += 1
            try:
                content = backlog_file.read_text(encoding="utf-8")
                # Use regex to be more robust about task formats (matches "- [ ]", "* [ ]", etc.)
                all_tasks = len(re.findall(r"[-*+] \[([ xX])\]", content))
                completed = len(re.findall(r"[-*+] \[([xX])\]", content))

                stats["suggested_tasks"] += all_tasks
                stats["completed_tasks"] += completed
            except (OSError, UnicodeDecodeError) as exc:
                logger.debug("Failed to parse growth backlog %s: %s", backlog_file, exc)

    return stats


def get_retrospective_stats(data_dir: Path, agent_name: str, layer: str) -> dict[str, Any]:
    """Analyze retrospectives for sentiment and feedback."""
    retro_dir = data_dir / layer / agent_name / "retrospectives"
    stats = {"interaction_count": 0, "success_rate": 0.0, "feedback_score": 0.0}

    if not retro_dir.exists():
        return stats

    successes = 0
    feedback_total = 0.0

    for retro_file in retro_dir.glob("*.yaml"):
        stats["interaction_count"] += 1
        try:
            # Simple line-based parse to avoid heavy yaml dep and handle partial files
            content = retro_file.read_text()
            if "outcome: success" in content:
                successes += 1

            # Check for feedback if present (future improvement)
            if "feedback_score:" in content:
                match = re.search(r"feedback_score:\s*([\d\.]+)", content)
                if match:
                    feedback_total += float(match.group(1))
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            logger.debug("Failed to parse retrospective %s: %s", retro_file, exc)

    if stats["interaction_count"] > 0:
        stats["success_rate"] = successes / stats["interaction_count"]
        # Default feedback score is success_rate if no explicit feedback
        stats["feedback_score"] = (
            feedback_total / stats["interaction_count"] if feedback_total > 0 else stats["success_rate"]
        )

    return stats


def get_performance_stats(data_dir: Path, agent_name: str, mcp_metrics: dict[str, Any] = None) -> dict[str, Any]:
    """Calculate performance metrics from execution logs and MCP metrics."""
    del data_dir
    executions_dir = get_runtime_dir() / "chain-executions"

    stats = {"usage_count": 0, "success_count": 0, "success_rate": 1.0, "last_active": None, "chains_participated": 0}

    # Base usage from MCP tool metrics (individual tool calls)
    if mcp_metrics:
        # Total tool calls for this skill/agent
        stats["usage_count"] = mcp_metrics.get("skill_usage", {}).get(agent_name, 0)

    if not executions_dir.exists():
        return stats

    # Participation in chains
    participation_found = False
    for execution_file in executions_dir.glob("*.json"):
        try:
            data = json.loads(execution_file.read_text())
            chain_start_time = data.get("started_at") or data.get("timestamp")

            agent_in_this_chain = False
            for step in data.get("steps", []):
                if step.get("agent") == agent_name:
                    participation_found = True
                    agent_in_this_chain = True

                    # Tool calls within chains are also counted if not already in mcp_metrics
                    # For now, we increment usage_count for each step participation too
                    stats["usage_count"] += 1

                    if step.get("status") == "completed":
                        stats["success_count"] += 1

                    # Update last active
                    step_time = (
                        step.get("completed_at") or step.get("started_at") or step.get("timestamp") or chain_start_time
                    )
                    if step_time:
                        if not stats["last_active"] or step_time > stats["last_active"]:
                            stats["last_active"] = step_time

            if agent_in_this_chain:
                stats["chains_participated"] += 1

        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError) as exc:
            logger.debug("Failed to parse execution file %s: %s", execution_file, exc)

    if stats["usage_count"] > 0:
        stats["success_rate"] = stats["success_count"] / stats["usage_count"]
    elif participation_found:
        stats["success_rate"] = 1.0

    return stats


def load_mcp_metrics(data_dir: Path) -> dict[str, Any]:
    """Load MCP metrics from the metrics file."""
    del data_dir
    # Try runtime path first (standard)
    metrics_path = get_runtime_dir() / "metrics" / "mcp" / "mcp-metrics.json"
    if not metrics_path.exists():
        # Fallback to platform/mcp location
        metrics_path = get_project_root() / "platform" / "mcp" / "mcp-metrics.json"

    if metrics_path.exists():
        try:
            return json.loads(metrics_path.read_text())
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            logger.debug("Failed to load MCP metrics from %s: %s", metrics_path, exc)
    return {}


def get_retro_learning_weight(data_dir: Path) -> float:
    """Read retro_learning_investment from agent_weights.yaml."""
    config_path = data_dir / "config" / "agents" / "agent_weights.yaml"
    if not config_path.exists():
        return 0.5  # Default

    try:
        content = config_path.read_text(encoding="utf-8")
        match = re.search(r"retro_learning_investment:\s*([\d\.]+)", content)
        if match:
            return float(match.group(1))
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        logger.debug("Failed to read retro learning weight from %s: %s", config_path, exc)
    return 0.5


def calculate_all_scores(repo: Path, data_dir: Path) -> dict[str, Any]:
    """Calculate scores for all agents."""
    agents = []
    tier_breakdown = {"production": 0, "functional": 0, "needsAttention": 0}
    retro_learning_weight = get_retro_learning_weight(data_dir)
    mcp_metrics = load_mcp_metrics(data_dir)

    for layer in ["factory", "horizontal", "vertical"]:
        layer_path = repo / "plugins" / layer
        if not layer_path.exists():
            continue

        for skill_path in layer_path.iterdir():
            if not skill_path.is_dir():
                continue
            if not (skill_path / "SKILL.md").exists():
                continue

            analysis = analyze_skill(skill_path)
            backlog = get_backlog_stats(data_dir, skill_path.name)
            performance = get_performance_stats(data_dir, skill_path.name, mcp_metrics)
            retrospectives = get_retrospective_stats(data_dir, skill_path.name, layer)

            analysis["backlog"] = backlog
            analysis["performance"] = performance
            analysis["retrospectives"] = retrospectives
            analysis["layer"] = layer

            # Flatten performance metrics for easier dashboard consumption
            analysis["usage_count"] = performance["usage_count"]
            analysis["success_rate"] = performance["success_rate"]
            analysis["last_active"] = performance["last_active"]
            analysis["chains_participated"] = performance["chains_participated"]

            # Incorporate performance and sentiment into final score
            # Base score + performance modifier + sentiment modifier
            final_score = analysis["score"]

            # --- SELF-LEARNING LOGIC ---
            # High investment (>= 0.7) means we are stricter about quality
            if retro_learning_weight >= 0.7:
                # Penalty for missing tests/scripts becomes severe
                if not analysis["hasTests"]:
                    final_score -= 15  # Stricter penalty
                if not analysis["hasReferences"]:
                    final_score -= 10

                # Retrospective feedback matters MORE
                if retrospectives["interaction_count"] > 0:
                    bonus = (retrospectives["feedback_score"] - 0.9) * 40  # Higher bar (0.9), higher impact
                    final_score += bonus

            # Low investment (<= 0.3) means we just want output
            elif retro_learning_weight <= 0.3:
                # Ignore structure rules, focus on output
                # Bonus for simply having completed items
                if backlog["completed"] > 5:
                    final_score += 10

            # Standard logic for mid-range (preserved)
            if performance["usage_count"] > 0:
                # Performance acts as a ±10 point modifier
                bonus = (performance["success_rate"] - 0.8) * 50
                final_score += bonus

            if retrospectives["interaction_count"] > 0 and retro_learning_weight < 0.7:
                # Retrospective sentiment acts as a ±5 point modifier
                bonus = (retrospectives["feedback_score"] - 0.8) * 25
                final_score += bonus

            analysis["score"] = max(0, min(100, int(final_score)))

            # Update Tier based on new score
            if analysis["score"] >= 85:
                analysis["tier"] = "production"
            elif analysis["score"] >= 60:
                analysis["tier"] = "functional"
            else:
                analysis["tier"] = "needs-attention"

            agents.append(analysis)

            # Update tier breakdown
            if analysis["tier"] == "production":
                tier_breakdown["production"] += 1
            elif analysis["tier"] == "functional":
                tier_breakdown["functional"] += 1
            else:
                tier_breakdown["needsAttention"] += 1

    # Sort by score descending
    agents.sort(key=lambda a: a["score"], reverse=True)

    # Calculate overall health
    if agents:
        health_score = sum(a["score"] for a in agents) // len(agents)
    else:
        health_score = 0

    growth_stats = get_growth_stats(data_dir)

    return {
        "timestamp": datetime.now().isoformat(),
        "healthScore": health_score,
        "tierBreakdown": tier_breakdown,
        "growthMetrics": growth_stats,
        "agents": agents,
        "totalAgents": len(agents),
        "retroLearningInvestment": retro_learning_weight,
    }


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Calculate Agent Scores")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--save", action="store_true", help="Save to data dir")
    args = parser.parse_args()

    repo = get_repo_root()
    data_dir = get_data_dir()

    _out("🔄 Calculating agent scores...\n", file=sys.stderr)

    results = calculate_all_scores(repo, data_dir)

    _out(f"   Health Score: {results['healthScore']}", file=sys.stderr)
    _out(f"   Agents: {results['totalAgents']}", file=sys.stderr)
    _out(
        f"   Growth Tasks: {results['growthMetrics']['completed_tasks']}/{results['growthMetrics']['suggested_tasks']}",
        file=sys.stderr,
    )
    _out(f"   Production: {results['tierBreakdown']['production']}", file=sys.stderr)
    _out(f"   Functional: {results['tierBreakdown']['functional']}", file=sys.stderr)
    _out(f"   Needs Attention: {results['tierBreakdown']['needsAttention']}", file=sys.stderr)

    if args.save:
        output_path = data_dir / "cache" / "agent-scores.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
        _out(f"\n   Saved to: {output_path}", file=sys.stderr)

    # Output JSON to stdout for API consumption
    if args.json:
        _out(json.dumps(results))

    return 0


if __name__ == "__main__":
    sys.exit(main())
