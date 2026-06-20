import asyncio
import sys

import aiohttp

from src.logging import get_entity_logger

logger = get_entity_logger("dashboard.validate_pages")

BASE_URL = "http://localhost:3000"
PAGES = [
    "/",
    "/career",
    "/brain",
    "/inbox",
    "/settings/debug",
    "/venture",
    "/venture/gtm",
    "/life/health",
    "/productivity/voice",
]


async def check_page(session, page):
    try:
        async with session.get(f"{BASE_URL}{page}") as response:
            status = response.status
            if status == 200:
                logger.info(f"{page}: 200 OK")
                return True
            logger.warning(f"{page}: {status}")
            return False
    except Exception as e:
        logger.error(f"{page}: Error {e}")
        return False


async def main():
    # trust_env=False completely ignores HTTP_PROXY/HTTPS_PROXY environment variables
    # This is essential for localhost checks to avoid corporate proxies
    async with aiohttp.ClientSession(trust_env=False) as session:
        # Wait for server to be ready
        logger.info("Waiting for server to be ready (max 30s)...")
        for i in range(30):
            try:
                async with session.get(BASE_URL) as response:
                    if response.status == 200:
                        logger.info("Server is ready!")
                        break
            except Exception:
                await asyncio.sleep(1)
        else:
            logger.error("Server failed to start in time (port 3000)")
            sys.exit(1)

        logger.info("Checking pages...")
        results = await asyncio.gather(*[check_page(session, page) for page in PAGES])

        if all(results):
            logger.info("All pages validated successfully!")
            sys.exit(0)
        logger.error("Some pages failed validation.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
