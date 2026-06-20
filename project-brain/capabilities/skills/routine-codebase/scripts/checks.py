"""d0-d1 UI quality check functions — static TSX analysis."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

_REGISTRY: list[dict] | None = None
_CONFIDENCE_WEIGHTS: dict[str, float] = {"high": 1.0, "medium": 0.75, "low": 0.5}
_DIMENSION_WEIGHTS: dict[str, float] = {
    "accessibility": 0.30,
    "interaction": 0.25,
    "design_system": 0.25,
    "responsiveness": 0.20,
}


def _load_registry() -> list[dict]:
    global _REGISTRY
    if _REGISTRY is not None:
        return _REGISTRY
    registry_path = Path(__file__).parent.parent / "assets" / "seeds" / "check_registry.yaml"
    with open(registry_path) as f:
        data = yaml.safe_load(f)
    _REGISTRY = data.get("checks", [])
    if "dimensions" in data:
        _DIMENSION_WEIGHTS.update({k: v["weight"] for k, v in data["dimensions"].items()})
    if "confidence_weights" in data:
        _CONFIDENCE_WEIGHTS.update(data["confidence_weights"])
    return _REGISTRY


# ── Check functions ──────────────────────────────────────────────
# Assignment to d0/d1 is at the bottom of this file (_D0_CHECKS, _D1_CHECKS).
# d0 = accessibility errors only; d1 = design-system + interaction quality.


def check_cursor_pointer_on_click(content: str) -> list[dict]:
    """onClick handlers must have cursor-pointer."""
    issues = []
    for i, line in enumerate(content.splitlines(), 1):
        if re.search(r"onClick\s*=", line) and "cursor-pointer" not in line:
            # Check if it's a disabled element (acceptable)
            if "disabled" in line and "cursor-not-allowed" in line:
                continue
            issues.append({
                "check_id": "cursor-pointer-on-click",
                "line": i,
                "detail": "onClick handler without cursor-pointer",
                "confidence": "high",
                "dimension": "interaction",
            })
    return issues


def check_hardcoded_colors(content: str) -> list[dict]:
    """Detect hardcoded hex/rgb colors in className strings."""
    issues = []
    hex_pattern = re.compile(r'(?:className|style)[^"]*"[^"]*(?:#[0-9a-fA-F]{3,8}|rgb\(|rgba\()')
    gradient_pattern = re.compile(r"(?:bg-gradient|from-|to-|via-)")
    for i, line in enumerate(content.splitlines(), 1):
        if hex_pattern.search(line) and not gradient_pattern.search(line):
            issues.append({
                "check_id": "hardcoded-hex-color",
                "line": i,
                "detail": "Hardcoded color — use CSS var(--*) instead",
                "confidence": "high",
                "dimension": "design_system",
            })
    return issues


def check_emoji_in_jsx(content: str) -> list[dict]:
    """Detect emoji characters in JSX."""
    issues = []
    emoji_pattern = re.compile(
        "[\U0001F300-\U0001F9FF\U00002600-\U000027BF"
        "\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF"
        "\U0000FE00-\U0000FE0F\U0000200D]"
    )
    for i, line in enumerate(content.splitlines(), 1):
        # Skip comments
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("*") or stripped.startswith("/*"):
            continue
        if emoji_pattern.search(line):
            issues.append({
                "check_id": "emoji-in-jsx",
                "line": i,
                "detail": "Emoji character in JSX — use Lucide SVG icon",
                "confidence": "high",
                "dimension": "design_system",
            })
    return issues


def check_aria_label_icon_button(content: str) -> list[dict]:
    """Icon-only buttons need aria-label."""
    issues = []
    # Match button elements — use negative lookbehind for => to handle arrow fns
    button_pattern = re.compile(
        r"<button\b(.*?)(?<!=)>(.*?)</button>", re.DOTALL
    )
    icon_only_pattern = re.compile(r"^\s*<[\w]+\s[^>]*/>\s*$", re.DOTALL)
    for m in button_pattern.finditer(content):
        attrs = m.group(1)
        children = m.group(2)
        if icon_only_pattern.match(children) and "aria-label" not in attrs:
            line = content[: m.start()].count("\n") + 1
            issues.append({
                "check_id": "aria-label-icon-button",
                "line": line,
                "detail": "Icon-only button missing aria-label",
                "confidence": "high",
                "dimension": "accessibility",
            })
    return issues


def check_transition_duration(content: str) -> list[dict]:
    """Transition durations should be 150-300ms."""
    issues = []
    dur_pattern = re.compile(r"duration-(\d+)")
    for i, line in enumerate(content.splitlines(), 1):
        for m in dur_pattern.finditer(line):
            ms = int(m.group(1))
            if ms == 0:
                continue  # intentional disable
            if ms < 150 or ms > 300:
                issues.append({
                    "check_id": "transition-duration-range",
                    "line": i,
                    "detail": f"duration-{ms} outside 150-300ms range",
                    "confidence": "medium",
                    "dimension": "interaction",
                })
    return issues


def check_non_lucide_import(content: str) -> list[dict]:
    """Icon imports should come from lucide-react."""
    issues = []
    # Match imports with Icon/Icons in name OR from known non-lucide icon packages
    pattern = re.compile(
        r"import\s+.*(?:Icon|Icons).*from\s+['\"](?!lucide-react)"
        r"|import\s+.*from\s+['\"](?:react-icons|@heroicons|@fortawesome|@ant-design/icons)"
    )
    for i, line in enumerate(content.splitlines(), 1):
        if pattern.search(line):
            issues.append({
                "check_id": "non-lucide-icon-import",
                "line": i,
                "detail": "Icon import not from lucide-react",
                "confidence": "medium",
                "dimension": "design_system",
            })
    return issues


def check_responsive_breakpoints(content: str) -> list[dict]:
    """Grid/flex containers should have responsive classes."""
    issues = []
    grid_pattern = re.compile(r"grid[\s-]cols-\d+")
    responsive_pattern = re.compile(r"(?:sm:|md:|lg:|xl:)")
    for i, line in enumerate(content.splitlines(), 1):
        if grid_pattern.search(line) and not responsive_pattern.search(line):
            issues.append({
                "check_id": "missing-responsive-breakpoint",
                "line": i,
                "detail": "Grid without responsive breakpoint classes",
                "confidence": "medium",
                "dimension": "responsiveness",
            })
    return issues


def check_animate_without_motion_reduce(content: str) -> list[dict]:
    """animate-* should have motion-reduce variant."""
    issues = []
    has_animation = bool(re.search(r"animate-(?!none)", content))
    has_motion_reduce = "motion-reduce" in content or "prefers-reduced-motion" in content
    if has_animation and not has_motion_reduce:
        issues.append({
            "check_id": "animate-without-motion-reduce",
            "line": 0,
            "detail": "File uses animate-* but lacks motion-reduce variant",
            "confidence": "medium",
            "dimension": "interaction",
        })
    return issues


# ── Aggregator ───────────────────────────────────────────────────

# Check functions by difficulty level
# d0: only genuine errors (accessibility violations)
_D0_CHECKS = [
    check_aria_label_icon_button,
]

# d1: design-system and interaction quality (aspirational, not errors)
_D1_CHECKS = [
    check_cursor_pointer_on_click,
    check_hardcoded_colors,
    check_emoji_in_jsx,
    check_transition_duration,
    check_non_lucide_import,
    check_responsive_breakpoints,
    check_animate_without_motion_reduce,
]


def run_all_checks(
    content: str,
    page_path: str,
    difficulty: int = 1,
) -> dict[str, Any]:
    """Run all checks up to the given difficulty level.

    Returns dict with: issues, applicable, passing, dimension_scores.
    """
    all_issues: list[dict] = []
    checks_run = 0

    # d0 checks
    for check_fn in _D0_CHECKS:
        checks_run += 1
        issues = check_fn(content)
        for issue in issues:
            issue["page"] = page_path
        all_issues.extend(issues)

    # d1 checks
    if difficulty >= 1:
        for check_fn in _D1_CHECKS:
            checks_run += 1
            issues = check_fn(content)
            for issue in issues:
                issue["page"] = page_path
            all_issues.extend(issues)

    # Calculate dimension scores
    dimension_scores = _calculate_dimension_scores(all_issues, checks_run)

    return {
        "issues": all_issues,
        "applicable": checks_run,
        "passing": checks_run - len(set(i["check_id"] for i in all_issues)),
        "dimension_scores": dimension_scores,
    }


def _calculate_dimension_scores(
    issues: list[dict], checks_run: int
) -> dict[str, float]:
    """Calculate weighted scores per dimension."""
    # Count failing checks per dimension
    failing_by_dim: dict[str, set[str]] = {}
    for issue in issues:
        dim = issue.get("dimension", "")
        check_id = issue.get("check_id", "")
        if dim:
            failing_by_dim.setdefault(dim, set()).add(check_id)

    # Checks per dimension (from registry or inferred)
    checks_per_dim: dict[str, int] = {}
    for fn in _D0_CHECKS + _D1_CHECKS:
        # Infer dimension from first issue or function name
        dim = _infer_dimension(fn)
        checks_per_dim[dim] = checks_per_dim.get(dim, 0) + 1

    scores: dict[str, float] = {}
    for dim, total in checks_per_dim.items():
        failing = len(failing_by_dim.get(dim, set()))
        scores[dim] = max(0, (total - failing) / total * 100) if total > 0 else 100.0

    return scores


def _infer_dimension(fn) -> str:
    """Infer dimension from function name convention."""
    name = fn.__name__
    if "aria" in name or "alt" in name:
        return "accessibility"
    if "cursor" in name or "transition" in name or "animate" in name or "touch" in name:
        return "interaction"
    if "color" in name or "emoji" in name or "lucide" in name or "icon" in name:
        return "design_system"
    if "responsive" in name or "breakpoint" in name or "motion" in name:
        return "responsiveness"
    return "design_system"
