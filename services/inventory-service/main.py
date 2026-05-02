import asyncio
import os
import logging
import random

from telemetry import setup_telemetry

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

setup_telemetry("inventory-service")

from fastapi import FastAPI

app = FastAPI(title="inventory-service")

ITEMS = {
    "item-1":  {"id": "item-1",  "name": "Laptop Pro 16",       "price": 1999.99, "stock": 42},
    "item-2":  {"id": "item-2",  "name": "Wireless Mouse",      "price":   29.99, "stock": 200},
    "item-3":  {"id": "item-3",  "name": "USB-C Hub",           "price":   49.99, "stock": 135},
    "item-4":  {"id": "item-4",  "name": "Mechanical Keyboard", "price":  149.99, "stock": 75},
    "item-5":  {"id": "item-5",  "name": "27\" Monitor",        "price":  399.99, "stock": 30},
    "item-6":  {"id": "item-6",  "name": "Webcam 4K",           "price":   79.99, "stock": 60},
    "item-7":  {"id": "item-7",  "name": "Desk Lamp LED",       "price":   39.99, "stock": 90},
    "item-8":  {"id": "item-8",  "name": "HDMI Cable 2m",       "price":   12.99, "stock": 300},
    "item-9":  {"id": "item-9",  "name": "SSD 1TB",             "price":  109.99, "stock": 45},
    "item-10": {"id": "item-10", "name": "USB-C Dock",          "price":  129.99, "stock": 55},
}


@app.get("/health")
async def health():
    return {"status": "ok", "service": "inventory-service"}


@app.get("/items/batch")
async def get_items_batch(ids: str):
    """Single DB-style query — one round-trip regardless of item count (~80ms)."""
    item_list = ids.split(",")
    await asyncio.sleep(0.08 + random.uniform(0, 0.02))
    logger.info("batch ids=%s count=%d", ids, len(item_list))
    return [ITEMS.get(i, {"error": "not found"}) for i in item_list]


@app.get("/items/{item_id}")
async def get_item(item_id: str):
    """Single-row query — ~80ms each, called N times in the buggy path."""
    await asyncio.sleep(0.08 + random.uniform(0, 0.02))
    logger.info("single item_id=%s", item_id)
    return ITEMS.get(item_id, {"error": "not found"})
