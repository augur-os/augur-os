"""Cron-callable entry point for the daily priority wiki update."""
from __future__ import annotations

import asyncio
import json
import sys

from skills.wiki.scripts.mcp import wiki_tools


async def _run() -> int:
    result_text = await wiki_tools._run_wiki_update(limit=20, tier="")
    print(result_text)
    payload = json.loads(result_text)
    return 0 if payload.get("success") else 2


def main() -> int:
    return asyncio.run(_run())


if __name__ == "__main__":
    sys.exit(main())
