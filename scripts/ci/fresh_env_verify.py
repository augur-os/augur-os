"""Fresh-env verify harness (M4).

Run after `aug onboard run --non-interactive` on a clean CI runner: poll the
dashboard until ready, then run the Playwright client-load spec. Exit codes:
0 ok, 1 Playwright assertion failed, 2 server never became ready.
See docs/superpowers/specs/2026-06-16-fresh-env-onboarding-gate-m4-design.md.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Callable

PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DASHBOARD = PROJECT_ROOT / "apps" / "dashboard"
# Playwright treats the positional `test <arg>` as a REGEX matched against the
# resolved ABSOLUTE test path; a "../../"-prefixed path matches 0 tests. Pass the
# bare filename so it matches. CI-only config has no webServer block so Playwright
# does NOT manage the server (the workflow's backgrounded server + harness poll do).
_CONFIG = "playwright.fresh-env.config.ts"
_SPEC = "fresh-env-browse.spec.ts"


def _probe_once(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            return resp.status == 200
    except Exception:
        return False


def _run_playwright() -> int:
    proc = subprocess.run(
        ["pnpm", "exec", "playwright", "test", "--config", _CONFIG, _SPEC],
        cwd=str(_DASHBOARD),
    )
    return proc.returncode


def run(
    base_url: str = "http://localhost:3000",
    attempts: int = 60,
    delay: float = 2.0,
    playwright: Callable[[], int] | None = None,
) -> int:
    """Poll base_url/browse until ready (or give up), then run Playwright."""
    runner = playwright or _run_playwright
    probe_url = base_url.rstrip("/") + "/browse"
    for _ in range(attempts):
        if _probe_once(probe_url):
            break
        time.sleep(delay)
    else:
        print(f"fresh-env verify: dashboard never became ready at {probe_url}", file=sys.stderr)
        return 2
    return runner()


def main() -> int:
    parser = argparse.ArgumentParser(description="Fresh-env onboarding verify harness.")
    parser.add_argument("--base-url", default="http://localhost:3000")
    parser.add_argument("--attempts", type=int, default=60)
    parser.add_argument("--delay", type=float, default=2.0)
    args = parser.parse_args()
    return run(base_url=args.base_url, attempts=args.attempts, delay=args.delay)


if __name__ == "__main__":
    raise SystemExit(main())
