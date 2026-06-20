"""d3-d4 visual analysis — Playwright screenshots + LLM prompt assembly."""
from __future__ import annotations

import subprocess
import urllib.request
from pathlib import Path
from datetime import datetime, timezone

def check_dashboard_available(url: str = "http://localhost:3000") -> bool:
    """Quick HTTP probe to check if dashboard dev server is running."""
    try:
        if not url.lower().startswith(("http://", "https://")):
            raise ValueError(f"Non-HTTP URL rejected: {url!r}")
        req = urllib.request.Request(url, method="HEAD")
        urllib.request.urlopen(req, timeout=3)  # nosec B310  # url scheme-validated above (http/https only)
        return True
    except Exception:
        return False


def take_screenshot(
    page_url: str,
    output_path: Path,
    viewport_width: int = 1440,
    viewport_height: int = 900,
) -> bool:
    """Take a Playwright screenshot of a dashboard page.

    Returns True on success, False if Playwright unavailable or page fails.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    script = f"""
const {{ chromium }} = require('playwright');
(async () => {{
    const browser = await chromium.launch({{ headless: true }});
    const page = await browser.newPage({{
        viewport: {{ width: {viewport_width}, height: {viewport_height} }}
    }});
    await page.goto('{page_url}', {{ waitUntil: 'networkidle', timeout: 15000 }});
    await page.screenshot({{ path: '{output_path}', fullPage: true }});
    await browser.close();
}})();
"""
    try:
        result = subprocess.run(
            ["node", "-e", script],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode == 0 and output_path.exists()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


def build_llm_prompt(
    page_path: str,
    page_source: str,
    score_breakdown: dict,
    issues: list[dict],
    design_recommendations: str,
    screenshot_path: Path | None = None,
) -> str:
    """Assemble the LLM escalation prompt for d3-d4 visual analysis."""
    prompt_parts = [
        f"# UI Quality Improvement: {page_path}\n",
        "## Current Score Breakdown",
        f"Overall: {score_breakdown.get('score', 0):.0f}/100\n",
    ]

    for dim, score in score_breakdown.get("dimension_scores", {}).items():
        prompt_parts.append(f"- {dim}: {score:.0f}/100")

    prompt_parts.append(f"\n## Issues Found ({len(issues)})")
    for issue in issues[:20]:  # cap to avoid prompt bloat
        prompt_parts.append(
            f"- [{issue.get('check_id', '?')}] line {issue.get('line', '?')}: "
            f"{issue.get('detail', '')}"
        )

    prompt_parts.append("\n## Design Recommendations (from ui-ux-pro-max)")
    prompt_parts.append(design_recommendations or "No specific recommendations available.")

    prompt_parts.append("\n## Page Source Code")
    prompt_parts.append(f"```tsx\n{page_source}\n```")

    if screenshot_path and screenshot_path.exists():
        prompt_parts.append(f"\n## Screenshot available at: {screenshot_path}")

    prompt_parts.append(
        "\n## Task"
        "\nImprove this page's UI quality. Focus on:"
        "\n1. Fix all identified issues"
        "\n2. Improve information hierarchy and grouping"
        "\n3. Use existing design system components (GlassCard, CSS vars, Lucide icons)"
        "\n4. Ensure accessibility (aria-labels, focus states, touch targets)"
        "\n5. Add responsive breakpoints where missing"
        "\n\nOutput the complete fixed page.tsx file."
    )

    return "\n".join(prompt_parts)


def get_design_recommendations(
    page_context: str,
    search_script: Path,
) -> str:
    """Call ui-ux-pro-max search.py for design recommendations."""
    try:
        result = subprocess.run(
            ["python3", str(search_script), page_context, "--domain", "ux"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return result.stdout if result.returncode == 0 else ""
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return ""


def get_screenshot_dir(runtime_dir: Path) -> Path:
    """Get the screenshots directory path."""
    return runtime_dir / "adaptive" / "ui-quality" / "screenshots"


def screenshot_page(
    page_path: str,
    runtime_dir: Path,
    base_url: str = "http://localhost:3000",
    label: str = "current",
) -> Path | None:
    """Take a screenshot of a page and save to the screenshots dir.

    Returns the screenshot path, or None if failed.
    """
    screenshot_dir = get_screenshot_dir(runtime_dir)
    safe_name = page_path.replace("/", "__")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    filename = f"{safe_name}_{label}_{timestamp}.png"
    output = screenshot_dir / filename

    url = f"{base_url}/{page_path}"
    if take_screenshot(url, output):
        return output
    return None
