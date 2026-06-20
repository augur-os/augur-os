#!/usr/bin/env python3
"""
Pattern Compliance Audit Script
Checks pages against the /agents design pattern reference.

Phase 1 Checks:
1. Gradient Background Check
2. Header Structure Compliance
3. Typography Hierarchy Check
4. Spacing System Compliance

Reference: http://localhost:3000/agents
Component: apps/dashboard/app/agents/AgentCommandCenter.tsx
"""
# TODO_CLEANUP: This file is 917 lines — consider splitting into smaller modules

import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, Any
from datetime import datetime
from subprocess import CompletedProcess, TimeoutExpired, run  # nosec B404


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))


def _run_command(command: list[str], **kwargs: Any) -> CompletedProcess[str]:
    return run(command, **kwargs)  # nosec B603


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


def check_gradient_background(content: str, file_path: str) -> Dict[str, Any]:
    """
    Check if page has gradient background pattern from /agents.

    Pattern: bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-indigo-950 via-slate-950 to-black
    """
    issues = []
    suggestions = []

    # Check for gradient background
    has_gradient = "bg-[radial-gradient(ellipse_at_top" in content
    has_colors = "from-indigo-950 via-slate-950 to-black" in content
    has_text_white = 'text-white' in content or '"text-white"' in content

    if not has_gradient:
        issues.append(
            {
                "type": "missing_gradient_background",
                "severity": "high",
                "description": "Page missing gradient background pattern",
                "file": file_path,
                "fix": {
                    "action": "add_wrapper",
                    "pattern": 'className="min-h-screen bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-indigo-950 via-slate-950 to-black text-white p-6 font-sans selection:bg-cyan-500/30"',
                    "example": '<div className="min-h-screen bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-indigo-950 via-slate-950 to-black text-white p-6 font-sans selection:bg-cyan-500/30">',
                },
            }
        )
        suggestions.append("Add gradient background wrapper matching /agents pattern")
    elif not has_colors:
        issues.append(
            {
                "type": "incorrect_gradient_colors",
                "severity": "medium",
                "description": "Gradient background has incorrect color stops",
                "file": file_path,
                "fix": {"action": "update_colors", "pattern": "from-indigo-950 via-slate-950 to-black"},
            }
        )
        suggestions.append("Update gradient colors to match /agents pattern")

    return {
        "check": "gradient_background",
        "compliant": has_gradient and has_colors and has_text_white,
        "issues": issues,
        "suggestions": suggestions,
    }


def check_header_structure(content: str, file_path: str) -> Dict[str, Any]:
    """
    Check if page has proper header structure from /agents.

    Pattern:
    <header className="flex items-center justify-between mb-8 border-b border-white/10 pb-4">
      <div className="flex items-center gap-3">
        <div className="p-2 bg-blue-500/20 rounded-lg border border-blue-500/50">
          <Icon className="w-6 h-6 text-blue-400" />
        </div>
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white">Title</h1>
          <p className="text-sm text-slate-400">Subtitle</p>
        </div>
      </div>
    </header>
    """
    issues = []
    suggestions = []

    has_header = "<header" in content or 'header className' in content
    has_icon_container = (
        "bg-blue-500/20 rounded-lg border border-blue-500/50" in content
        or "bg-{color}-500/20 rounded-lg border border-{color}-500/50" in content
    )
    has_title = re.search(r'text-2xl font-bold tracking-tight', content) is not None
    has_subtitle = re.search(r'text-sm text-slate-400', content) is not None
    has_header_border = "border-b border-white/10" in content

    if not has_header:
        issues.append(
            {
                "type": "missing_header",
                "severity": "high",
                "description": "Page missing header structure",
                "file": file_path,
                "fix": {
                    "action": "add_header",
                    "pattern": """<header className="flex items-center justify-between mb-8 border-b border-white/10 pb-4">
  <div className="flex items-center gap-3">
    <div className="p-2 bg-blue-500/20 rounded-lg border border-blue-500/50">
      <Icon className="w-6 h-6 text-blue-400" />
    </div>
    <div>
      <h1 className="text-2xl font-bold tracking-tight text-white">Page Title</h1>
      <p className="text-sm text-slate-400">Page subtitle</p>
    </div>
  </div>
</header>""",
                },
            }
        )
        suggestions.append("Add header structure matching /agents pattern")
    else:
        if not has_icon_container:
            issues.append(
                {
                    "type": "missing_icon_container",
                    "severity": "medium",
                    "description": "Header missing icon container",
                    "file": file_path,
                }
            )
        if not has_title:
            issues.append(
                {
                    "type": "missing_title_style",
                    "severity": "medium",
                    "description": "Header title missing proper styling (text-2xl font-bold tracking-tight)",
                    "file": file_path,
                }
            )
        if not has_subtitle:
            issues.append(
                {
                    "type": "missing_subtitle",
                    "severity": "low",
                    "description": "Header missing subtitle (text-sm text-slate-400)",
                    "file": file_path,
                }
            )
        if not has_header_border:
            issues.append(
                {
                    "type": "missing_header_border",
                    "severity": "low",
                    "description": "Header missing border separator (border-b border-white/10)",
                    "file": file_path,
                }
            )

    return {
        "check": "header_structure",
        "compliant": has_header and has_icon_container and has_title and has_header_border,
        "issues": issues,
        "suggestions": suggestions,
    }


def check_typography_hierarchy(content: str, file_path: str) -> Dict[str, Any]:
    """
    Check typography hierarchy matches /agents pattern.

    Patterns:
    - Page titles: text-2xl font-bold or font-extrabold
    - Section headers: text-sm font-bold uppercase tracking-widest
    - Card titles: text-sm font-semibold or font-medium
    """
    issues = []
    suggestions = []

    # Check for page titles
    h1_elements = re.findall(r'<h1[^>]*>(.*?)</h1>', content, re.DOTALL)
    for h1 in h1_elements:
        if 'text-2xl font-bold' not in h1 and 'text-2xl font-extrabold' not in h1:
            issues.append(
                {
                    "type": "incorrect_h1_style",
                    "severity": "medium",
                    "description": f"H1 element missing proper styling: {h1[:50]}",
                    "file": file_path,
                    "fix": {"action": "update_class", "from": "text-2xl", "to": "text-2xl font-bold tracking-tight"},
                }
            )

    # Check for section headers (h2)
    h2_elements = re.findall(r'<h2[^>]*>(.*?)</h2>', content, re.DOTALL)
    section_headers = [h2 for h2 in h2_elements if 'uppercase' in h2 or 'tracking-widest' in h2]
    if len(h2_elements) > 0 and len(section_headers) == 0:
        issues.append(
            {
                "type": "missing_section_header_style",
                "severity": "low",
                "description": "Section headers should use: text-sm font-bold uppercase tracking-widest",
                "file": file_path,
            }
        )

    # Check for widget headers (should be font-extrabold now)
    widget_titles = re.findall(r'title="([^"]*)"', content)
    if len(widget_titles) > 0:
        # Check DashboardWidget usage
        if 'font-extrabold' not in content and 'font-bold' in content:
            issues.append(
                {
                    "type": "widget_header_weight",
                    "severity": "low",
                    "description": "Widget headers should use font-extrabold (already fixed globally in DashboardWidget)",
                    "file": file_path,
                    "note": "This is handled globally in DashboardWidget.tsx",
                }
            )

    return {
        "check": "typography_hierarchy",
        "compliant": len([i for i in issues if i["severity"] == "high"]) == 0,
        "issues": issues,
        "suggestions": suggestions,
    }


def check_spacing_system(content: str, file_path: str) -> Dict[str, Any]:
    """
    Check spacing system matches /agents pattern.

    Patterns:
    - Page padding: p-6
    - Section separation: mb-8 or gap-8
    - Card spacing: gap-3 or space-y-3
    - Grid gaps: gap-8 for large grids
    """
    issues = []
    suggestions = []

    # Check page padding
    page_container = re.search(r'<div[^>]*className="[^"]*min-h-screen[^"]*"', content)
    if page_container:
        if 'p-6' not in page_container.group(0):
            issues.append(
                {
                    "type": "incorrect_page_padding",
                    "severity": "medium",
                    "description": "Page container should use p-6 padding",
                    "file": file_path,
                    "fix": {"action": "update_class", "add": "p-6"},
                }
            )

    # Check section spacing
    # Look for common section patterns
    sections = re.findall(r'(?:mb-|gap-)(\d+)', content)
    inconsistent_spacing = [s for s in sections if s not in ['6', '8']]
    if inconsistent_spacing:
        issues.append(
            {
                "type": "inconsistent_section_spacing",
                "severity": "low",
                "description": f"Found inconsistent spacing values: {set(inconsistent_spacing)}. Should use mb-8 or gap-8 for sections",
                "file": file_path,
            }
        )

    # Check grid gaps
    grid_patterns = re.findall(r'grid[^>]*gap-(\d+)', content)
    if grid_patterns:
        for gap in grid_patterns:
            if gap not in ['4', '8']:
                issues.append(
                    {
                        "type": "incorrect_grid_gap",
                        "severity": "low",
                        "description": f"Grid gap-{gap} should be gap-8 for large grids or gap-4 for smaller",
                        "file": file_path,
                    }
                )

    # Check for space-y-6 wrapper (recent improvement)
    has_space_y_wrapper = 'space-y-6' in content or 'space-y-8' in content
    if not has_space_y_wrapper and 'EditableMasonryGrid' in content:
        issues.append(
            {
                "type": "missing_spacing_wrapper",
                "severity": "low",
                "description": "Consider adding space-y-6 wrapper for better content breathing room",
                "file": file_path,
                "fix": {"action": "add_wrapper", "pattern": '<div className="space-y-6">'},
            }
        )

    return {
        "check": "spacing_system",
        "compliant": len([i for i in issues if i["severity"] == "high"]) == 0,
        "issues": issues,
        "suggestions": suggestions,
    }


def check_card_component_pattern(content: str, file_path: str) -> Dict[str, Any]:
    """
    Check if card components follow /agents pattern.

    Pattern:
    - Colored borders: border-{color}-500/20
    - Colored backgrounds: bg-{color}-950/10 or /20
    - Backdrop blur: backdrop-blur-sm
    - Hover states: hover:bg-white/5
    - Transitions: transition-all
    - Rounded corners: rounded-lg or rounded-xl
    """
    issues = []
    suggestions = []

    # Find card-like divs (common patterns)
    card_patterns = [
        r'<div[^>]*className="[^"]*glass-panel[^"]*"',
        r'<div[^>]*className="[^"]*rounded-lg[^"]*border[^"]*"',
        r'<div[^>]*className="[^"]*rounded-xl[^"]*border[^"]*"',
    ]

    cards_found = []
    for pattern in card_patterns:
        matches = re.findall(pattern, content)
        cards_found.extend(matches)

    if not cards_found:
        # No cards found - might be using DashboardWidget which is fine
        return {
            "check": "card_component_pattern",
            "compliant": True,
            "issues": [],
            "suggestions": [],
            "note": "No card components found (may be using DashboardWidget)",
        }

    # Check each card for pattern compliance
    for card in cards_found[:5]:  # Limit to first 5 to avoid too many issues
        has_colored_border = re.search(r'border-\w+-\d+/\d+', card) is not None
        has_backdrop_blur = 'backdrop-blur' in card
        has_hover = 'hover:' in card
        has_transition = 'transition' in card

        if not has_colored_border:
            issues.append(
                {
                    "type": "missing_colored_border",
                    "severity": "medium",
                    "description": "Card missing colored border pattern (border-{color}-500/20)",
                    "file": file_path,
                    "fix": {"action": "add_border", "pattern": "border border-blue-500/20"},
                }
            )

        if not has_backdrop_blur:
            issues.append(
                {
                    "type": "missing_backdrop_blur",
                    "severity": "medium",
                    "description": "Card missing backdrop blur (backdrop-blur-sm)",
                    "file": file_path,
                    "fix": {"action": "add_class", "pattern": "backdrop-blur-sm"},
                }
            )

        if not has_hover:
            issues.append(
                {
                    "type": "missing_hover_state",
                    "severity": "medium",
                    "description": "Card missing hover state (hover:bg-white/5)",
                    "file": file_path,
                    "fix": {"action": "add_hover", "pattern": "hover:bg-white/5"},
                }
            )

        if not has_transition:
            issues.append(
                {
                    "type": "missing_transition",
                    "severity": "low",
                    "description": "Card missing transition (transition-all)",
                    "file": file_path,
                    "fix": {"action": "add_class", "pattern": "transition-all"},
                }
            )

    return {
        "check": "card_component_pattern",
        "compliant": len([i for i in issues if i["severity"] == "high"]) == 0,
        "issues": issues[:10],  # Limit issues reported
        "suggestions": suggestions,
    }


def check_interactive_states(content: str, file_path: str) -> Dict[str, Any]:
    """
    Check if interactive elements have proper states.

    Checks:
    - Hover states on clickable elements
    - Focus states for keyboard navigation
    - Active states for buttons
    - Disabled states with proper styling
    - Transition classes
    """
    issues = []
    suggestions = []

    # Find interactive elements
    buttons = re.findall(r'<button[^>]*>', content)
    links = re.findall(r'<a[^>]*>', content)
    clickable_divs = re.findall(r'<div[^>]*onClick[^>]*>', content)

    interactive_elements = buttons + links + clickable_divs

    if not interactive_elements:
        return {
            "check": "interactive_states",
            "compliant": True,
            "issues": [],
            "suggestions": [],
            "note": "No interactive elements found",
        }

    elements_without_hover = []
    elements_without_focus = []
    elements_without_transition = []

    for element in interactive_elements[:10]:  # Limit check
        has_hover = 'hover:' in element
        has_focus = 'focus:' in element or 'focus-visible:' in element
        has_transition = 'transition' in element

        if not has_hover:
            elements_without_hover.append(element[:50])
        if not has_focus:
            elements_without_focus.append(element[:50])
        if not has_transition:
            elements_without_transition.append(element[:50])

    if elements_without_hover:
        issues.append(
            {
                "type": "missing_hover_states",
                "severity": "medium",
                "description": f"{len(elements_without_hover)} interactive elements missing hover states",
                "file": file_path,
                "fix": {"action": "add_hover", "pattern": "hover:bg-white/5 or hover:text-white"},
            }
        )

    if elements_without_focus:
        issues.append(
            {
                "type": "missing_focus_states",
                "severity": "high",
                "description": f"{len(elements_without_focus)} interactive elements missing focus states (accessibility issue)",
                "file": file_path,
                "fix": {"action": "add_focus", "pattern": "focus:outline-none focus:ring-2 focus:ring-{color}-400"},
            }
        )

    if elements_without_transition:
        issues.append(
            {
                "type": "missing_transitions",
                "severity": "low",
                "description": f"{len(elements_without_transition)} interactive elements missing transitions",
                "file": file_path,
                "fix": {"action": "add_transition", "pattern": "transition-colors or transition-all"},
            }
        )

    return {
        "check": "interactive_states",
        "compliant": len([i for i in issues if i["severity"] == "high"]) == 0,
        "issues": issues,
        "suggestions": suggestions,
    }


def check_color_coding_system(content: str, file_path: str) -> Dict[str, Any]:
    """
    Check if color usage matches semantic color coding system.

    Expected colors:
    - Purple (purple-500, purple-950): Factory/Infrastructure
    - Amber (amber-500, amber-950): Vertical Domains
    - Cyan (cyan-500, cyan-950): Horizontal Services
    - Blue (blue-500, blue-950): Primary actions, KPIs
    - Red (red-500, red-950): Critical/Errors
    - Emerald (emerald-500, emerald-950): Success/Active
    """
    issues = []
    suggestions = []

    # Find all color classes
    color_pattern = r'(?:bg|text|border)-\w+-\d+'
    color_classes = re.findall(color_pattern, content)

    # Define semantic colors
    semantic_colors = {
        'purple': ['purple-400', 'purple-500', 'purple-950', 'purple-200', 'purple-300'],
        'amber': ['amber-400', 'amber-500', 'amber-950', 'amber-200', 'amber-300'],
        'cyan': ['cyan-400', 'cyan-500', 'cyan-950', 'cyan-200', 'cyan-300'],
        'blue': ['blue-400', 'blue-500', 'blue-950', 'blue-200', 'blue-300', 'blue-600'],
        'red': ['red-400', 'red-500', 'red-950', 'red-200', 'red-300'],
        'emerald': ['emerald-400', 'emerald-500', 'emerald-950', 'emerald-200', 'emerald-300'],
    }

    # Check for hardcoded colors (non-semantic)
    non_semantic_colors = []
    for color_class in set(color_classes):
        color_name = color_class.split('-')[1] if '-' in color_class else None
        if color_name and color_name not in semantic_colors:
            # Check if it's a neutral color (acceptable)
            if color_name not in ['neutral', 'slate', 'gray', 'zinc', 'white', 'black']:
                non_semantic_colors.append(color_class)

    if non_semantic_colors:
        unique_colors = list(set(non_semantic_colors))[:5]
        issues.append(
            {
                "type": "non_semantic_colors",
                "severity": "low",
                "description": f"Found non-semantic colors: {', '.join(unique_colors)}. Consider using semantic color system (purple/amber/cyan/blue/red/emerald)",
                "file": file_path,
                "fix": {
                    "action": "replace_colors",
                    "pattern": "Use semantic colors: purple (factory), amber (vertical), cyan (horizontal), blue (primary), red (error), emerald (success)",
                },
            }
        )

    # Check for hardcoded hex colors (bad practice)
    hex_colors = re.findall(r'#[0-9a-fA-F]{3,6}', content)
    if hex_colors:
        issues.append(
            {
                "type": "hardcoded_hex_colors",
                "severity": "medium",
                "description": f"Found {len(hex_colors)} hardcoded hex colors. Use Tailwind color classes instead.",
                "file": file_path,
                "fix": {"action": "replace_hex", "pattern": "Replace hex colors with Tailwind classes"},
            }
        )

    # Check for proper color opacity usage (should use /20, /50, etc.)
    color_with_opacity = re.findall(r'(?:bg|text|border)-\w+-\d+/\d+', content)
    if len(color_classes) > 10 and len(color_with_opacity) < len(color_classes) * 0.5:
        issues.append(
            {
                "type": "missing_color_opacity",
                "severity": "low",
                "description": "Many colors missing opacity modifiers. Pattern uses /20, /50 for transparency.",
                "file": file_path,
                "fix": {"action": "add_opacity", "pattern": "Add opacity modifiers like /20, /50 to color classes"},
            }
        )

    return {
        "check": "color_coding_system",
        "compliant": len([i for i in issues if i["severity"] == "high"]) == 0,
        "issues": issues,
        "suggestions": suggestions,
    }


def audit_page(file_path: Path) -> Dict[str, Any]:
    """Run all Phase 1 and Phase 2 checks on a page."""
    try:
        content = file_path.read_text()
    except Exception as e:
        return {"file": str(file_path), "error": str(e), "checks": {}}

    # Determine which checks to run based on phase
    # Get phase from args if available, otherwise default to 'all'
    phase = 'all'
    if 'args' in globals():
        try:
            phase = globals()['args'].phase
        except Exception as exc:
            _out(f"Warning: failed to read audit phase from args, using default 'all': {exc}", file=sys.stderr)

    checks = {}

    if phase in ["1", "all"]:
        checks.update(
            {
                "gradient_background": check_gradient_background(content, str(file_path)),
                "header_structure": check_header_structure(content, str(file_path)),
                "typography_hierarchy": check_typography_hierarchy(content, str(file_path)),
                "spacing_system": check_spacing_system(content, str(file_path)),
            }
        )

    if phase in ["2", "all"]:
        checks.update(
            {
                "card_component_pattern": check_card_component_pattern(content, str(file_path)),
                "interactive_states": check_interactive_states(content, str(file_path)),
                "color_coding_system": check_color_coding_system(content, str(file_path)),
            }
        )

    results = {"file": str(file_path), "timestamp": datetime.now().isoformat(), "phase": phase, "checks": checks}

    # Calculate overall compliance
    all_checks = results["checks"].values()
    compliant_count = sum(1 for c in all_checks if c.get("compliant", False))
    total_checks = len(all_checks)

    results["compliance"] = {
        "score": compliant_count / total_checks if total_checks > 0 else 0,
        "compliant_checks": compliant_count,
        "total_checks": total_checks,
    }

    # Collect all issues
    all_issues = []
    for check in all_checks:
        all_issues.extend(check.get("issues", []))

    results["summary"] = {
        "total_issues": len(all_issues),
        "high_severity": len([i for i in all_issues if i.get("severity") == "high"]),
        "medium_severity": len([i for i in all_issues if i.get("severity") == "medium"]),
        "low_severity": len([i for i in all_issues if i.get("severity") == "low"]),
    }

    return results


def _resolve_page_path(page_arg: str, dashboard_root: Path, project_root: Path) -> Path:
    """Resolve a page argument to an absolute path."""
    page_path = Path(page_arg)
    if page_path.is_absolute():
        return page_path

    if (dashboard_root / page_arg).exists():
        return dashboard_root / page_arg
    if page_arg.startswith("src/"):
        return project_root / page_arg
    return dashboard_root / page_arg.lstrip("/")


def _run_auto_fix(
    script_dir: Path,
    project_root: Path,
    page_path: Path | None,
    report_file: Path | None,
    fixes: list,
    fix_limit: int = 5,
) -> None:
    """Run auto-fix script on pages with issues."""
    auto_fix_script = script_dir / "auto_fix_pattern_issues.py"
    if not auto_fix_script.exists():
        _out(f"⚠️  Auto-fix script not found: {auto_fix_script}", file=sys.stderr)
        return

    fixes_list = ["gradient", "spacing", "focus", "cards"] if fixes == ["all"] else fixes

    if page_path:
        cmd = [sys.executable, str(auto_fix_script), "--page", str(page_path)]
        timeout = 300
    else:
        cmd = [sys.executable, str(auto_fix_script), "--audit-report", str(report_file)]
        cmd.extend(["--limit", str(fix_limit)])
        timeout = 600

    cmd.extend(["--fixes"] + fixes_list)

    try:
        proc = _run_command(cmd, capture_output=True, text=True, timeout=timeout, cwd=project_root, check=False)
        if proc.returncode == 0:
            _out("✅ Auto-fix completed successfully")
            for line in proc.stdout.split('\n'):
                if any(s in line for s in ["Fixed:", "✅", "Summary:", "📊"]):
                    _out(f"   {line}")
        else:
            _out(f"⚠️  Auto-fix had issues (exit code {proc.returncode})")
            if proc.stderr:
                _out(f"   Error: {proc.stderr[:300]}")
    except TimeoutExpired:
        _out(f"⚠️  Auto-fix timed out (exceeded {timeout // 60} minutes)", file=sys.stderr)
    except Exception as e:
        _out(f"⚠️  Auto-fix failed: {e}", file=sys.stderr)


def _save_audit_report(results: list | dict, single_page: bool = False) -> Path | None:
    """Save audit results to a JSON report file."""
    try:
        data_dir = _get_operations_dir() / "frontend" / "audits"
        data_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        report_file = data_dir / f"pattern_compliance_audit_{timestamp}.json"

        if single_page:
            report_data = {
                "timestamp": datetime.now().isoformat(),
                "summary": {
                    "total_pages": 1,
                    "fully_compliant": 1 if results["compliance"]["score"] == 1.0 else 0,
                    "total_issues": results["summary"]["total_issues"],
                    "high_severity_issues": results["summary"]["high_severity"],
                },
                "results": [results],
            }
        else:
            total_pages = len(results)
            fully_compliant = sum(1 for r in results if r["compliance"]["score"] == 1.0)
            total_issues = sum(r["summary"]["total_issues"] for r in results)
            high_issues = sum(r["summary"]["high_severity"] for r in results)
            report_data = {
                "timestamp": datetime.now().isoformat(),
                "summary": {
                    "total_pages": total_pages,
                    "fully_compliant": fully_compliant,
                    "total_issues": total_issues,
                    "high_severity_issues": high_issues,
                },
                "results": results,
            }

        report_file.write_text(json.dumps(report_data, indent=2))
        return report_file
    except Exception as e:
        _out(f"⚠️ Failed to save report: {e}", file=sys.stderr)
        return None


def _print_single_page_results(results: dict, args) -> None:
    """Print audit results for a single page."""
    if args.json:
        _out(json.dumps(results, indent=2))
        return

    if args.summary:
        _out(f"📊 {results['file']}")
        _out(
            f"   Compliance: {results['compliance']['score']:.0%} ({results['compliance']['compliant_checks']}/{results['compliance']['total_checks']})"
        )
        _out(
            f"   Issues: {results['summary']['total_issues']} (H:{results['summary']['high_severity']} M:{results['summary']['medium_severity']} L:{results['summary']['low_severity']})"
        )
        return

    _out(f"📊 Pattern Compliance Audit: {results['file']}")
    _out(f"   Compliance Score: {results['compliance']['score']:.0%}")
    _out(
        f"   Issues: {results['summary']['total_issues']} (High: {results['summary']['high_severity']}, Medium: {results['summary']['medium_severity']}, Low: {results['summary']['low_severity']})"
    )
    _out()

    for check_name, check_result in results["checks"].items():
        status = "✅" if check_result.get("compliant") else "❌"
        _out(f"{status} {check_name.replace('_', ' ').title()}")
        for issue in check_result.get("issues", []):
            _out(f"   [{issue['severity'].upper()}] {issue['description']}")


def _print_directory_summary(all_results: list, dashboard_root: Path) -> dict:
    """Print directory audit summary and return report data."""
    total_pages = len(all_results)
    fully_compliant = sum(1 for r in all_results if r["compliance"]["score"] == 1.0)
    total_issues = sum(r["summary"]["total_issues"] for r in all_results)
    high_issues = sum(r["summary"]["high_severity"] for r in all_results)

    _out()
    _out("=" * 60)
    _out("📊 Audit Summary")
    _out(f"   Pages Audited: {total_pages}")
    _out(f"   Fully Compliant: {fully_compliant} ({fully_compliant/total_pages:.0%})")
    _out(f"   Total Issues: {total_issues} (High: {high_issues})")

    return {
        "total_pages": total_pages,
        "fully_compliant": fully_compliant,
        "total_issues": total_issues,
        "high_issues": high_issues,
    }


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Audit pages for /agents pattern compliance")
    parser.add_argument("--page", help="Specific page file to audit")
    parser.add_argument("--directory", help="Directory to audit (default: apps/dashboard/app)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--summary", action="store_true", help="Show summary only")
    parser.add_argument(
        "--phase",
        choices=["1", "2", "all"],
        default="all",
        help="Audit phase: 1 (pattern compliance), 2 (component quality), all (default)",
    )
    parser.add_argument(
        "--auto-fix", action="store_true", help="Automatically fix issues after audit (runs auto_fix_pattern_issues.py)"
    )
    parser.add_argument(
        "--fix-limit", type=int, default=5, help="Maximum pages to fix when --auto-fix is used (default: 5)"
    )
    parser.add_argument(
        "--fixes",
        nargs="+",
        choices=["gradient", "spacing", "focus", "cards", "all"],
        default=["all"],
        help="Which fixes to apply when --auto-fix is used",
    )

    args = parser.parse_args()
    globals()['args'] = args

    script_dir = Path(__file__).parent
    project_root = script_dir.parents[3]
    dashboard_root = project_root / "apps" / "dashboard" / "app"

    if args.page:
        page_path = _resolve_page_path(args.page, dashboard_root, project_root)
        if not page_path.exists():
            _out(f"❌ Page not found: {page_path}", file=sys.stderr)
            sys.exit(1)

        results = audit_page(page_path)
        _print_single_page_results(results, args)

        if args.auto_fix:
            report_file = _save_audit_report(results, single_page=True)
            if report_file:
                _out()
                _out("=" * 60)
                _out("🔧 Running auto-fix...")
                _out("=" * 60)
                _run_auto_fix(script_dir, project_root, page_path, None, args.fixes)
    else:
        audit_dir = Path(args.directory) if args.directory else dashboard_root
        page_files = list(audit_dir.rglob("page.tsx"))

        _out(f"🔍 Auditing {len(page_files)} pages in {audit_dir}")
        _out("=" * 60)

        all_results = []
        for page_file in page_files:
            results = audit_page(page_file)
            all_results.append(results)

            if not args.json and not args.summary:
                status = "✅" if results["compliance"]["score"] == 1.0 else "⚠️"
                _out(
                    f"{status} {page_file.relative_to(dashboard_root)} - {results['compliance']['score']:.0%} compliant"
                )

        _print_directory_summary(all_results, dashboard_root)
        report_file = _save_audit_report(all_results, single_page=False)

        if report_file:
            _out(f"💾 Report saved to: {report_file}")

            if args.auto_fix:
                _out()
                _out("=" * 60)
                _out("🔧 Running auto-fix on pages with issues...")
                _out("=" * 60)
                _run_auto_fix(script_dir, project_root, None, report_file, args.fixes, args.fix_limit)

        if args.json and all_results:
            report_data = {
                "timestamp": datetime.now().isoformat(),
                "results": all_results,
            }
            _out(json.dumps(report_data, indent=2))


if __name__ == "__main__":
    main()
