#!/usr/bin/env python3
"""
Layout Organization Analysis Script
Analyzes page layouts and suggests block/page reorganizations for better
information architecture, visual balance, and user experience.

Usage:
    python layout_organization_analysis.py --page /agents/workforce --context "Agent management and monitoring"
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List
from datetime import datetime


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))


def _get_operations_dir() -> Path:
    env_base = os.environ.get("AUGUR_ROOT")
    if env_base:
        base = Path(os.path.expanduser(env_base)).expanduser().resolve()
        return base.parent / "plugins" / "dev" / "skills"

    try:
        repo_root = Path(__file__).resolve().parents[3]
        if str(repo_root) not in sys.path:
            sys.path.insert(0, str(repo_root))
        from src.config.paths import get_operations_dir, get_project_root  # type: ignore

        return get_operations_dir()
    except Exception:
        return get_project_root() / "plugins" / "dev" / "skills"


def analyze_page_structure(page_path: str, blocks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Analyze the structure of a page and identify layout issues.

    Reference Implementation: http://localhost:3000/agents
    All pages should follow the design patterns from AgentCommandCenter.tsx

    Args:
        page_path: Path to the page (e.g., "/agents/workforce")
        blocks: List of block/widget information

    Returns:
        Analysis results with suggestions
    """
    analysis = {
        "page": page_path,
        "blocks": blocks,
        "issues": [],
        "suggestions": [],
        "metrics": {},
        "reference_page": "http://localhost:3000/agents",
        "design_pattern_notes": [],
    }

    # Calculate layout metrics
    total_blocks = len(blocks)
    grid_blocks = [b for b in blocks if b.get("layout") == "grid"]
    full_width_blocks = [b for b in blocks if b.get("layout") == "full"]

    analysis["metrics"] = {
        "total_blocks": total_blocks,
        "grid_blocks": len(grid_blocks),
        "full_width_blocks": len(full_width_blocks),
        "content_density": "high" if total_blocks > 3 else "medium" if total_blocks > 1 else "low",
    }

    # Identify issues
    if len(grid_blocks) > 0 and total_blocks > 2:
        analysis["issues"].append(
            {
                "type": "grid_cramping",
                "severity": "medium",
                "description": f"Grid layout with {len(grid_blocks)} blocks may cramp primary content",
                "suggestion": "Consider moving secondary content to related pages. Reference: http://localhost:3000/agents for proper spacing patterns.",
            }
        )

    # Check against reference design pattern
    analysis["design_pattern_notes"] = [
        "Reference implementation: http://localhost:3000/agents",
        "Ensure page follows AgentCommandCenter.tsx patterns:",
        "- Gradient background: bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-indigo-950 via-slate-950 to-black",
        "- Header with icon container, title (text-2xl font-bold), subtitle (text-sm text-slate-400)",
        "- KPI cards with colored borders (border-{color}-500/20) and backdrop-blur-sm",
        "- Grid layouts with gap-8 spacing",
        "- Card components with hover states (hover:bg-white/5)",
        "- Proper typography hierarchy and color coding",
    ]

    # Analyze block purposes
    primary_content = []
    secondary_content = []
    infrastructure_content = []

    for block in blocks:
        block.get("id", "")
        title = block.get("title", "").lower()
        purpose = block.get("purpose", "")

        # Categorize blocks
        if any(keyword in title or keyword in purpose for keyword in ["workforce", "agents", "status", "health"]):
            primary_content.append(block)
        elif any(
            keyword in title or keyword in purpose
            for keyword in ["pipeline", "ci/cd", "github", "workflow", "specialist"]
        ):
            infrastructure_content.append(block)
        else:
            secondary_content.append(block)

    # Generate suggestions based on semantic analysis
    if infrastructure_content and page_path == "/agents/workforce":
        for block in infrastructure_content:
            analysis["suggestions"].append(
                {
                    "type": "move_block",
                    "block_id": block.get("id"),
                    "block_title": block.get("title"),
                    "from_page": page_path,
                    "to_page": "/agents/devops",
                    "reason": "Semantic alignment: Pipeline/CI-CD content belongs in infrastructure/devops section",
                    "benefits": [
                        f"Primary content ({len(primary_content)} blocks) gets full width",
                        "Devops page becomes more complete infrastructure hub",
                        "Better information architecture grouping",
                    ],
                    "priority": "high",
                    "effort": "low",
                    "impact": "high",
                }
            )

    return analysis


def suggest_cross_page_organization(pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Analyze relationships between pages and suggest cross-page reorganizations.

    Args:
        pages: List of page analyses

    Returns:
        List of cross-page suggestions
    """
    suggestions = []

    # Map blocks by purpose/domain
    domain_map = {"infrastructure": [], "monitoring": [], "management": [], "configuration": []}

    for page in pages:
        page_path = page.get("page", "")
        blocks = page.get("blocks", [])

        for block in blocks:
            block_id = block.get("id", "")
            title = block.get("title", "").lower()

            # Categorize
            if any(kw in title for kw in ["pipeline", "ci/cd", "github", "workflow"]):
                domain_map["infrastructure"].append({"block": block_id, "page": page_path, "title": block.get("title")})
            elif any(kw in title for kw in ["status", "health", "telemetry", "monitor"]):
                domain_map["monitoring"].append({"block": block_id, "page": page_path, "title": block.get("title")})

    # Suggest moves based on domain alignment
    for domain, blocks in domain_map.items():
        if domain == "infrastructure":
            # Infrastructure blocks should be on devops page
            for block_info in blocks:
                if block_info["page"] != "/agents/devops":
                    suggestions.append(
                        {
                            "type": "move_block",
                            "block_id": block_info["block"],
                            "block_title": block_info["title"],
                            "from_page": block_info["page"],
                            "to_page": "/agents/devops",
                            "reason": f"Infrastructure content ({domain}) belongs in devops section",
                            "priority": "high",
                        }
                    )

    return suggestions


def main():
    parser = argparse.ArgumentParser(description="Analyze page layouts and suggest reorganizations")
    parser.add_argument("--page", help="Page path to analyze (e.g., /agents/workforce)")
    parser.add_argument("--blocks", help="JSON string of blocks on the page")
    parser.add_argument("--context", help="Context about the page purpose")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    status = "ok"
    status_note = None
    blocks: List[Dict[str, Any]] = []

    if args.blocks:
        try:
            blocks = json.loads(args.blocks)
        except json.JSONDecodeError as e:
            status = "skipped"
            status_note = f"Invalid JSON for blocks: {e}"
    else:
        status = "skipped"
        status_note = "No blocks provided for analysis"

    page_path = args.page or "/agents/workforce"

    # Analyze page
    analysis = analyze_page_structure(page_path, blocks)

    if status != "ok":
        analysis["status"] = status
        analysis["note"] = status_note

    # Add context
    if args.context:
        analysis["context"] = args.context

    # Save retrospective
    if status == "ok":
        try:
            data_dir = _get_operations_dir() / "frontend" / "retrospectives"
            data_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            retro_file = data_dir / f"layout_analysis_{timestamp}.json"

            retro_data = {
                "timestamp": datetime.now().isoformat(),
                "task_type": "layout_analysis",
                "page": page_path,
                "analysis": analysis,
                "learnings": [
                    f"Analyzed {len(blocks)} blocks on {page_path}",
                    f"Found {len(analysis['suggestions'])} reorganization suggestions",
                ],
            }

            retro_file.write_text(json.dumps(retro_data, indent=2))
        except Exception as e:
            _out(f"⚠️ Failed to save retrospective: {e}", file=sys.stderr)

    # Output results
    if args.json:
        _out(json.dumps(analysis, indent=2))
    else:
        if status != "ok":
            _out(f"ℹ️ Layout analysis skipped: {status_note}")
            return
        _out(f"📊 Layout Analysis: {page_path}")
        _out(f"   Blocks: {analysis['metrics']['total_blocks']}")
        _out(f"   Issues: {len(analysis['issues'])}")
        _out(f"   Suggestions: {len(analysis['suggestions'])}")

        if analysis['suggestions']:
            _out("\n💡 Suggestions:")
            for suggestion in analysis['suggestions']:
                _out(f"   - {suggestion['type']}: Move '{suggestion['block_title']}'")
                _out(f"     From: {suggestion['from_page']}")
                _out(f"     To: {suggestion['to_page']}")
                _out(f"     Reason: {suggestion['reason']}")


if __name__ == "__main__":
    main()
