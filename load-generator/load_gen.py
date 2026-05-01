"""
Load generator for orderservice demo.
Sends realistic traffic: mix of valid requests, repeated hot orders, and some 404s.
"""
import asyncio
import httpx
import os
import random
import time
import logging
import signal
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("load-generator")

TARGET_URL = os.getenv("TARGET_URL", "http://localhost:8080")
RPS = float(os.getenv("REQUESTS_PER_SECOND", "5"))
CONCURRENCY = int(os.getenv("CONCURRENCY", "3"))

# Simulate hot orders (like a flash sale on certain products)
HOT_ORDERS = ["1", "2", "3", "5", "10"]
ALL_ORDERS = [str(i) for i in range(1, 101)]
MISSING_ORDERS = ["999", "9999"]

running = True


def signal_handler(sig, frame):
    global running
    logger.info("Shutting down load generator...")
    running = False


signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)


def pick_order_id() -> str:
    r = random.random()
    if r < 0.6:
        return random.choice(HOT_ORDERS)
    elif r < 0.95:
        return random.choice(ALL_ORDERS)
    else:
        return random.choice(MISSING_ORDERS)


async def make_request(client: httpx.AsyncClient, order_id: str) -> None:
    url = f"{TARGET_URL}/orders/{order_id}"
    start = time.time()
    try:
        response = await client.get(url, timeout=15.0)
        duration = time.time() - start
        logger.info(
            f"GET /orders/{order_id} -> {response.status_code} ({duration:.3f}s)"
        )
    except httpx.TimeoutException:
        duration = time.time() - start
        logger.warning(f"GET /orders/{order_id} -> TIMEOUT ({duration:.3f}s)")
    except Exception as e:
        duration = time.time() - start
        logger.error(f"GET /orders/{order_id} -> ERROR {e} ({duration:.3f}s)")


async def worker(client: httpx.AsyncClient, interval: float) -> None:
    while running:
        order_id = pick_order_id()
        await make_request(client, order_id)
        await asyncio.sleep(interval + random.uniform(-interval * 0.2, interval * 0.2))


async def main():
    interval = CONCURRENCY / RPS
    logger.info(f"Starting load generator: target={TARGET_URL} rps={RPS} concurrency={CONCURRENCY}")

    # Health check first
    async with httpx.AsyncClient() as client:
        for attempt in range(30):
            try:
                r = await client.get(f"{TARGET_URL}/healthz", timeout=5.0)
                if r.status_code == 200:
                    data = r.json()
                    logger.info(f"Service healthy — bug_enabled={data.get('bug_enabled')}")
                    break
            except Exception:
                pass
            logger.info(f"Waiting for service... (attempt {attempt + 1}/30)")
            await asyncio.sleep(2)

    async with httpx.AsyncClient() as client:
        tasks = [asyncio.create_task(worker(client, interval)) for _ in range(CONCURRENCY)]
        await asyncio.gather(*tasks, return_exceptions=True)


if __name__ == "__main__":
    asyncio.run(main())
