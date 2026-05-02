"""
Load generator — continuously hits frontend-api at ~3 RPS.
"""
import asyncio
import logging
import os
import random
import time

import httpx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://frontend-api:8080")
TARGET_RPS = float(os.getenv("TARGET_RPS", "3"))
ORDER_IDS   = ["order-1", "order-2", "order-3", "order-4", "order-5", "order-6"]
ORDER_WEIGHTS = [       1,        1,        1,        2,        1,        5]
# order-6 (10 items, ~950ms buggy) gets 50% of traffic; order-4 (5 items) gets 20%

INTERVAL = 1.0 / TARGET_RPS  # seconds between requests


async def run():
    logger.info("Load generator starting — target %.1f RPS -> %s", TARGET_RPS, FRONTEND_URL)
    async with httpx.AsyncClient(timeout=20.0) as client:
        while True:
            start = time.monotonic()
            order_id = random.choices(ORDER_IDS, weights=ORDER_WEIGHTS, k=1)[0]
            url = f"{FRONTEND_URL}/checkout/{order_id}"
            try:
                r = await client.get(url)
                elapsed_ms = (time.monotonic() - start) * 1000
                logger.info("GET %s -> %d (%.0f ms)", url, r.status_code, elapsed_ms)
            except Exception as exc:
                logger.warning("Request failed: %s", exc)

            # Pace to TARGET_RPS — sleep the remaining time in this interval
            elapsed = time.monotonic() - start
            sleep_for = max(0.0, INTERVAL - elapsed)
            await asyncio.sleep(sleep_for)


if __name__ == "__main__":
    asyncio.run(run())
