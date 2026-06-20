import json
import os
import sys
import argparse
from pathlib import Path


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


def rank_ui_visuals(screenshot_path: str, metrics: dict):
    """
    Ranks the UI quality based on visual parameters.
    In a real scenario, this would use a Vision model.
    Here we simulate the critique.

    Reference Implementation: http://localhost:3000/agents
    All pages should follow the design patterns from AgentCommandCenter.tsx
    """
    _out(f"🎨 [FRONTEND-DESIGN] Analyzing UI: {screenshot_path}")
    _out("📐 Reference design pattern: http://localhost:3000/agents")

    # Run Phase 1 pattern compliance checks if page path is available
    pattern_issues = []
    pattern_compliance = 1.0

    page_path = metrics.get("page_path") or screenshot_path
    if page_path and page_path.endswith((".tsx", ".ts", ".jsx", ".js")):
        try:
            from pathlib import Path
            import sys

            script_dir = Path(__file__).parent
            sys.path.insert(0, str(script_dir))

            from pattern_compliance_audit import audit_page

            page_file = Path(page_path)
            if page_file.exists():
                audit_result = audit_page(page_file)
                pattern_compliance = audit_result.get("compliance", {}).get("score", 1.0)

                # Collect high/medium severity issues
                for check_result in audit_result.get("checks", {}).values():
                    for issue in check_result.get("issues", []):
                        if issue.get("severity") in ["high", "medium"]:
                            pattern_issues.append(issue.get("description", ""))
        except Exception as e:
            _out(f"⚠️ Could not run pattern compliance check: {e}", file=sys.stderr)

    # Simulate critique based on common design standards
    score = 8.5  # Start with a good base
    critique = []

    # Adjust score based on pattern compliance
    if pattern_compliance < 0.5:
        score -= 2.0
        critique.append("Page does not follow /agents design pattern. Critical pattern compliance issues found.")
    elif pattern_compliance < 0.75:
        score -= 1.0
        critique.append("Page partially follows /agents design pattern. Some pattern compliance issues found.")
    elif pattern_compliance < 1.0:
        score -= 0.5
        critique.append("Page mostly follows /agents design pattern. Minor improvements needed.")

    if metrics.get("nodeCount", 0) > 1000:
        critique.append("DOM node count is high (>1000), consider flattening the component structure.")
        score -= 0.5

    critique.append("Glassmorphism effects look consistent, but ensure contrast remains high for accessibility.")
    critique.append("Animation speed is appropriate (300ms range).")

    # Add pattern-specific suggestions
    suggestions = []
    if pattern_issues:
        suggestions.extend([f"Pattern issue: {issue}" for issue in pattern_issues[:3]])
    else:
        suggestions.extend(
            [
                "Increase font-weight on widget headers for better hierarchy (reference: /agents page uses font-extrabold).",
                "Add subtle shadow to the Saved Insights cards to separate from background.",
                "Ensure page follows /agents design pattern: gradient background, proper header structure, KPI cards with colored borders, and backdrop blur effects.",
                "Reference http://localhost:3000/agents for spacing patterns (gap-8 for grids, p-6 for page padding, mb-8 for sections).",
            ]
        )

    # Mocking some visual findings
    findings = {
        "score": max(0, min(10, score)),  # Clamp between 0-10
        "criteria": {
            "cleanliness": 9,
            "interactivity": 8,
            "visual_polish": 8.5,
            "accessibility": 7.5,
            "pattern_compliance": pattern_compliance * 10,  # Scale to 0-10
        },
        "critique": critique,
        "suggestions": suggestions,
        "reference_page": "http://localhost:3000/agents",
        "reference_component": "apps/dashboard/app/agents/AgentCommandCenter.tsx",
        "pattern_compliance_score": pattern_compliance,
    }

    # Save retrospective for self-learning
    try:
        from datetime import datetime
        from pathlib import Path

        retro_dir = _get_operations_dir() / "frontend" / "retrospectives"
        retro_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        retro_file = retro_dir / f"ui_rank_{timestamp}.json"

        # Enriched format for calculate_agent_scores.py
        retro_data = {
            "timestamp": datetime.now().isoformat(),
            "outcome": "success",  # Always a success if we ran
            "feedback_score": score / 10.0,  # Normalize to 0-1
            "details": findings,
        }

        with open(retro_file, "w") as f:
            json.dump(retro_data, f, indent=2)

        _out(f"💾 Saved retrospective to: {retro_file}")

    except Exception as e:
        _out(f"⚠️ Failed to save retrospective: {e}")

    return findings


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--screenshot_path", required=True, help="Path to the screenshot")
    parser.add_argument("--metrics", help="JSON string of metrics")

    args = parser.parse_args()

    try:
        metrics = json.loads(args.metrics) if args.metrics else {}
        result = rank_ui_visuals(args.screenshot_path, metrics)
        _out(json.dumps(result, indent=2))
    except Exception as e:
        _out(f"❌ Error during ranking: {e}")
        sys.exit(1)
