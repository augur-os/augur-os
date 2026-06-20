import argparse
import asyncio
import json
from pathlib import Path

import sys


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))


try:
    from playwright.async_api import TimeoutError as PlaywrightTimeoutError, async_playwright
except Exception as exc:  # pragma: no cover - runtime environment dependency
    async_playwright = None
    PlaywrightTimeoutError = RuntimeError
    _PLAYWRIGHT_ERROR = str(exc)


async def capture_ui(url: str, output_path: str):
    """
    Captures a screenshot and basic metadata for UI review.
    """
    if not url:
        return {"status": "skipped", "error": "No URL provided", "url": url}
    if async_playwright is None:
        return {
            "status": "skipped",
            "error": f"Playwright unavailable: {_PLAYWRIGHT_ERROR}",
            "url": url,
        }
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        _out(f"📸 Capturing {url}...")
        try:
            await page.goto(url, wait_until="networkidle")
        except PlaywrightTimeoutError:
            # Fallback for pages with background network activity that never become idle.
            await page.goto(url, wait_until="domcontentloaded")

        # Take high-res screenshot
        await page.screenshot(path=output_path, full_page=True)

        # Capture basic DOM info/metrics
        metrics = await page.evaluate("""() => {
            return {
                title: document.title,
                url: window.location.href,
                viewport: {
                    width: window.innerWidth,
                    height: window.innerHeight
                },
                nodeCount: document.querySelectorAll('*').length
            }
        }""")

        # Extract semantic blocks for layout analysis
        blocks = await page.evaluate("""() => {
            const blocks = [];
            const candidates = document.querySelectorAll('header, main, footer, section, nav, div[role="main"], div[class*="grid"], .card, .container');
            
            candidates.forEach((el, index) => {
                const rect = el.getBoundingClientRect();
                if (rect.width > 50 && rect.height > 50 && window.getComputedStyle(el).display !== 'none') {
                    // Try to generate a meaningful ID/Title
                    let title = el.getAttribute('aria-label') || el.getAttribute('title') || el.id || el.className;
                    // Look for heading inside
                    const heading = el.querySelector('h1, h2, h3, h4, h5, h6');
                    if (heading) title = heading.innerText;
                    
                    blocks.push({
                        id: el.id || `block-${index}`,
                        title: title ? title.substring(0, 50) : `Block ${index}`,
                        purpose: el.tagName.toLowerCase(),
                        layout: el.className.includes('grid') ? 'grid' : 'flow',
                        width: rect.width,
                        height: rect.height,
                        top: rect.top,
                        left: rect.left
                    });
                }
            });
            return blocks;
        }""")

        await browser.close()
        return {"screenshot_path": str(Path(output_path).absolute()), "url": url, "metrics": metrics, "blocks": blocks}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="", help="URL to capture")
    parser.add_argument("--output", default="ui_screenshot.png", help="Output path for screenshot")

    args = parser.parse_args()

    try:
        result = asyncio.run(capture_ui(args.url, args.output))
        _out(json.dumps(result, indent=2))
    except Exception as e:
        error_result = {"status": "error", "error": str(e), "url": args.url}
        _out(json.dumps(error_result, indent=2))
