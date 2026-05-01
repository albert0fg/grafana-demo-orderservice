import os
import logging

from telemetry import setup_telemetry

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

setup_telemetry("frontend-api")

from fastapi import FastAPI, HTTPException
import httpx

app = FastAPI(title="frontend-api")

ORDERS_URL = os.getenv("ORDER_SERVICE_URL", "http://order-service:8080")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "frontend-api"}


@app.get("/checkout/{order_id}")
async def checkout(order_id: str):
    logger.info("checkout order_id=%s", order_id)
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(f"{ORDERS_URL}/orders/{order_id}", timeout=15.0)
            r.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=str(e))
        except httpx.RequestError as e:
            raise HTTPException(status_code=503, detail=f"order-service unavailable: {e}")
    return r.json()
