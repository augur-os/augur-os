#!/usr/bin/env python3
"""
UI QA Tool - Generic web application testing with Playwright.

Supports:
- Hydration error detection (React/Next.js)
- Layout alignment validation
- Interactive element testing

Configurable via CLI args or YAML config file.
"""

import asyncio
import json
import sys
import argparse
from datetime import datetime
from pathlib import Path
from playwright.async_api import TimeoutError as PlaywrightTimeoutError, async_playwright, Page
import yaml


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))


# Screenshots go to an external archive, never the repo tree.
from src.lib.skill_paths import get_peer_data_dir  # noqa: E402


def _resolve_screenshot_dir() -> Path:
    try:
        return get_peer_data_dir(__file__, "frontend") / "screenshots"
    except ValueError:
        # TODO_BUG fixed here: this engine lives under
        # apps/dashboard/scripts/skill-scripts/, which derive_skill_name
        # rejects, so the old module-level get_peer_data_dir call raised
        # ValueError on every invocation. Fall back to the logs archive.
        from src.config.paths import get_logs_dir  # noqa: E402

        return get_logs_dir() / "browser-verification" / "frontend" / "screenshots"


SCREENSHOT_DIR = _resolve_screenshot_dir()

# Default selectors (can be overridden via --config)
DEFAULT_SELECTORS = {
    "card": ".glass-pane, .card, [data-testid='card']",
    "card_container": ".glass-panel, .card-container",
    "action_button": "button:has-text('Actions'), [data-testid='action-button']",
    "dropdown_menu": "div.absolute.z-50, [role='menu'], .dropdown-content",
    "card_title": "h3, [data-testid='card-title']",
}

DEFAULT_CONFIG = {
    "url": "http://localhost:3000",
    "selectors": DEFAULT_SELECTORS,
    "thresholds": {
        "min_card_width": 50,
        "min_card_height": 50,
        "animation_wait": 1.0,
        "hydration_wait": 3.0,
    },
    "interactivity": {
        "expect_menu": True,
        "require_buttons": False,
    },
}


def load_config(config_path: str = None) -> dict:
    """Load config from YAML file or return defaults."""
    config = {
        **DEFAULT_CONFIG,
        "selectors": {**DEFAULT_CONFIG["selectors"]},
        "thresholds": {**DEFAULT_CONFIG["thresholds"]},
        "interactivity": {**DEFAULT_CONFIG["interactivity"]},
    }

    if config_path:
        path = Path(config_path)
        if path.exists():
            with open(path) as f:
                user_config = yaml.safe_load(f)
                if user_config:
                    # Deep merge selectors
                    if "selectors" in user_config:
                        config["selectors"] = {**config["selectors"], **user_config["selectors"]}
                        del user_config["selectors"]
                    if "thresholds" in user_config:
                        config["thresholds"] = {**config["thresholds"], **user_config["thresholds"]}
                        del user_config["thresholds"]
                    if "interactivity" in user_config:
                        config["interactivity"] = {**config["interactivity"], **user_config["interactivity"]}
                        del user_config["interactivity"]
                    config.update(user_config)

    return config


async def check_hydration(page: Page, results: dict, config: dict):
    """Monitor console for hydration errors."""
    errors = []

    def handle_console(msg):
        text = msg.text.lower()
        if "hydration" in text or "mismatch" in text or "did not match" in text:
            errors.append({"type": msg.type, "text": msg.text, "location": msg.location})

    page.on("console", handle_console)
    page.on("pageerror", lambda err: errors.append({"type": "pageerror", "text": str(err)}))

    # Wait and scroll to trigger lazy loading/hydration
    await page.evaluate("window.scrollTo(0, 500)")
    await asyncio.sleep(config["thresholds"]["hydration_wait"])
    await page.evaluate("window.scrollTo(0, 0)")

    results["hydration_errors"] = errors
    results["hydration_status"] = "PASSED" if not errors else "FAILED"


async def check_alignment(page: Page, results: dict, config: dict):
    """Check for overlapping elements or hidden cards."""
    aligned_status = "PASSED"
    issues = []

    card_selector = config["selectors"]["card"]
    min_width = config["thresholds"]["min_card_width"]
    min_height = config["thresholds"]["min_card_height"]

    cards = await page.query_selector_all(card_selector)
    results["cards_found"] = len(cards)

    for i, card in enumerate(cards):
        is_visible = await card.is_visible()
        if not is_visible:
            issues.append(f"Card {i} is not visible")
            aligned_status = "FAILED"
            continue

        bbox = await card.bounding_box()
        if not bbox:
            continue

        if bbox['width'] < min_width or bbox['height'] < min_height:
            issues.append(f"Card {i} has suspicious dimensions: {bbox['width']}x{bbox['height']}")
            aligned_status = "FAILED"

    results["alignment_issues"] = issues
    results["alignment_status"] = aligned_status


async def check_interactivity(page: Page, results: dict, config: dict, custom_selector: str = None):
    """Test interactive elements (buttons, dropdowns)."""
    interactive_status = "PASSED"
    results["button_tests"] = []

    animation_wait = config["thresholds"]["animation_wait"]
    button_selector = custom_selector or config["selectors"]["action_button"]
    menu_selector = config["selectors"]["dropdown_menu"]
    container_selector = config["selectors"]["card_container"]
    title_selector = config["selectors"]["card_title"]
    expect_menu = bool(config.get("interactivity", {}).get("expect_menu", True))
    require_buttons = bool(config.get("interactivity", {}).get("require_buttons", False))

    action_btns = await page.query_selector_all(button_selector)
    _out(f"DEBUG: Found {len(action_btns)} action buttons", file=sys.stderr)
    if require_buttons and not action_btns:
        interactive_status = "FAILED"
        results["button_tests"].append(
            {
                "index": -1,
                "status": "FAILED",
                "issue": f"No buttons matched selector: {button_selector}",
            }
        )

    for i, btn in enumerate(action_btns):
        btn_results = {"index": i}
        try:
            # Try to get context from parent container
            card = await btn.evaluate_handle(f"el => el.closest('{container_selector}')")
            context_name = "Unknown"
            card_el = card.as_element() if card else None
            if card_el:
                name_el = await card_el.query_selector(title_selector)
                if name_el:
                    context_name = await name_el.inner_text()

            btn_results["context"] = context_name
            await btn.scroll_into_view_if_needed()
            await btn.click()
            await asyncio.sleep(animation_wait)

            if expect_menu:
                # Check for menu visibility
                menu = await page.query_selector(menu_selector)
                if not menu or not await menu.is_visible():
                    btn_results["status"] = "FAILED"
                    btn_results["issue"] = "Menu not visible after click"
                    interactive_status = "FAILED"
                    # Save screenshot to data repo
                    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
                    screenshot_path = SCREENSHOT_DIR / f"fail_button_{i}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                    await page.screenshot(path=str(screenshot_path))
                else:
                    btn_results["status"] = "PASSED"
                    # Close menu
                    await btn.click()
                    await asyncio.sleep(0.5)
            else:
                btn_results["status"] = "PASSED"
                btn_results["mode"] = "click-only"

        except Exception as e:
            btn_results["status"] = "ERROR"
            btn_results["error"] = str(e)
            interactive_status = "FAILED"

        results["button_tests"].append(btn_results)

    results["interactivity_status"] = interactive_status


async def main():
    parser = argparse.ArgumentParser(
        description="UI QA Tool - Generic web application testing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test any URL with default selectors
  python ui_qa.py --url http://localhost:3000/my-page

  # Use custom config file
  python ui_qa.py --url http://localhost:8080 --config my_app.yaml

  # Run only hydration check
  python ui_qa.py --url http://localhost:3000 --action hydration

  # Custom button selector
  python ui_qa.py --url http://localhost:3000 --selector "button.my-btn"
""",
    )
    parser.add_argument("--url", help="URL to test (default: from config or localhost:3000)")
    parser.add_argument("--config", help="Path to YAML config file with selectors and thresholds")
    parser.add_argument(
        "--action",
        choices=["hydration", "alignment", "interactivity", "full"],
        default="full",
        help="Test action to run",
    )
    parser.add_argument("--selector", help="Custom selector for interactivity test")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    parser.add_argument("--headless", action="store_true", default=True, help="Run browser headless")
    parser.add_argument("--no-headless", dest="headless", action="store_false", help="Show browser window")

    args = parser.parse_args()

    # Load config
    config = load_config(args.config)

    # CLI args override config
    url = args.url or config.get("url", "http://localhost:3000")

    results = {
        "timestamp": datetime.now().isoformat(),
        "url": url,
        "action": args.action,
        "config_file": args.config,
    }

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=args.headless)
        context = await browser.new_context()
        page = await context.new_page()

        try:
            _out(f"🚀 Navigating to {url}...", file=sys.stderr)
            try:
                await page.goto(url, wait_until="networkidle")
            except PlaywrightTimeoutError:
                # Some pages keep network requests alive (polling/streaming) and never reach "networkidle".
                await page.goto(url, wait_until="domcontentloaded")

            if args.action in ["hydration", "full"]:
                await check_hydration(page, results, config)

            if args.action in ["alignment", "full"]:
                await check_alignment(page, results, config)

            if args.action in ["interactivity", "full"]:
                await check_interactivity(page, results, config, args.selector)

            # Final result rollup
            statuses = [results.get(k) for k in results if k.endswith("_status")]
            results["overall_status"] = "PASSED" if all(s == "PASSED" for s in statuses) else "FAILED"

        except Exception as e:
            results["overall_status"] = "ERROR"
            results["error"] = str(e)
        finally:
            await browser.close()

    if args.json:
        _out(json.dumps(results, indent=2))
    else:
        _out(f"\n{'='*40}")
        _out(f"📊 UI QA RESULTS: {results['overall_status']}")
        _out(f"{'='*40}")
        for k, v in results.items():
            if k.endswith("_status"):
                icon = "✅" if v == "PASSED" else "❌"
                _out(f"{icon} {k.replace('_status', '').upper()}: {v}")

        if results.get("cards_found"):
            _out(f"📦 Cards found: {results['cards_found']}")

        if results.get("hydration_errors"):
            _out("\n🚨 HYDRATION ERRORS FOUND:")
            for err in results["hydration_errors"]:
                _out(f"  - {err['text']}")

        if results.get("alignment_issues"):
            _out("\n📏 ALIGNMENT ISSUES:")
            for issue in results["alignment_issues"]:
                _out(f"  - {issue}")


if __name__ == "__main__":
    asyncio.run(main())
