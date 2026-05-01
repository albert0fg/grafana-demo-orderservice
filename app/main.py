import asyncio
import os
import random
import logging
import json
import time
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

from telemetry import setup_telemetry

BUG_ENABLED = os.getenv("BUG_ENABLED", "true").lower() == "true"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("orderservice")

setup_telemetry()
app = FastAPI(title="OrderService", version="1.0.0")
tracer = trace.get_tracer("orderservice")

REQUEST_COUNT = Counter(
    "orderservice_requests_total",
    "Total requests",
    ["method", "endpoint", "status_code"]
)
REQUEST_LATENCY = Histogram(
    "orderservice_request_duration_seconds",
    "Request latency in seconds",
    ["method", "endpoint"],
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0]
)
DB_QUERY_COUNT = Counter(
    "orderservice_db_queries_total",
    "Total DB queries",
    ["query_type"]
)
DB_QUERY_LATENCY = Histogram(
    "orderservice_db_query_duration_seconds",
    "DB query latency",
    ["query_type"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0]
)

ORDERS = {
    str(i): {
        "id": str(i),
        "customer": f"customer_{i % 20}",
        "status": random.choice(["pending", "processing", "shipped"]),
        "item_ids": [str((i * j) % 50 + 1) for j in range(1, 9)]
    }
    for i in range(1, 101)
}
ITEMS = {
    str(i): {
        "id": str(i),
        "name": f"Product {i}",
        "sku": f"SKU-{i:04d}",
        "price": round((i * 7.77) % 90 + 9.99, 2),
        "stock": random.randint(0, 100)
    }
    for i in range(1, 101)
}


async def db_query_single_item(item_id: str) -> dict:
    """Simulates a single-row DB query (~200ms each)."""
    with tracer.start_as_current_span("db.query") as span:
        span.set_attribute("db.system", "postgresql")
        span.set_attribute("db.operation", "SELECT")
        span.set_attribute("db.statement", f"SELECT * FROM items WHERE id = '{item_id}'")
        span.set_attribute("db.sql.table", "items")
        DB_QUERY_COUNT.labels(query_type="single").inc()
        start = time.time()
        await asyncio.sleep(0.2 + random.uniform(0, 0.05))
        DB_QUERY_LATENCY.labels(query_type="single").observe(time.time() - start)
        return ITEMS.get(item_id, {"id": item_id, "error": "not found"})


async def db_query_items_batch(item_ids: list) -> list:
    """Simulates an IN-clause batch query (same cost as 1 single query)."""
    ids_str = ", ".join(f"'{i}'" for i in item_ids)
    with tracer.start_as_current_span("db.query") as span:
        span.set_attribute("db.system", "postgresql")
        span.set_attribute("db.operation", "SELECT")
        span.set_attribute("db.statement", f"SELECT * FROM items WHERE id IN ({ids_str})")
        span.set_attribute("db.sql.table", "items")
        span.set_attribute("db.rows_fetched", len(item_ids))
        DB_QUERY_COUNT.labels(query_type="batch").inc()
        start = time.time()
        await asyncio.sleep(0.2 + random.uniform(0, 0.05))
        DB_QUERY_LATENCY.labels(query_type="batch").observe(time.time() - start)
        return [ITEMS.get(iid, {"id": iid, "error": "not found"}) for iid in item_ids]


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start
    endpoint = request.url.path.split("/")[1] if len(request.url.path.split("/")) > 1 else "root"
    REQUEST_LATENCY.labels(method=request.method, endpoint=f"/{endpoint}").observe(duration)
    REQUEST_COUNT.labels(method=request.method, endpoint=f"/{endpoint}", status_code=response.status_code).inc()
    return response


@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/healthz")
async def health():
    return {"status": "ok", "bug_enabled": BUG_ENABLED}


@app.get("/orders/{order_id}")
async def get_order(order_id: str):
    with tracer.start_as_current_span("orderservice.get_order") as span:
        span.set_attribute("order.id", order_id)
        span.set_attribute("bug.n_plus_one_enabled", BUG_ENABLED)

        order = ORDERS.get(order_id)
        if not order:
            span.set_status(Status(StatusCode.ERROR, "Order not found"))
            raise HTTPException(status_code=404, detail=f"Order {order_id} not found")

        items = []
        item_ids = order["item_ids"]

        if BUG_ENABLED:
            # BUG: N+1 query problem — one DB call per item
            logger.info(json.dumps({
                "event": "fetch_order_start",
                "order_id": order_id,
                "item_count": len(item_ids),
                "query_mode": "n+1",
                "msg": f"Fetching order {order_id} — will execute {len(item_ids)} individual DB queries"
            }))
            for idx, item_id in enumerate(item_ids):
                logger.info(json.dumps({
                    "event": "fetch_item",
                    "order_id": order_id,
                    "item_id": item_id,
                    "progress": f"{idx + 1}/{len(item_ids)}",
                    "msg": f"Fetching item {idx + 1} of {len(item_ids)}: item_id={item_id}"
                }))
                item = await db_query_single_item(item_id)
                items.append(item)
        else:
            # FIX: single batch query
            logger.info(json.dumps({
                "event": "fetch_order_start",
                "order_id": order_id,
                "item_count": len(item_ids),
                "query_mode": "batch",
                "msg": f"Fetching order {order_id} — executing 1 batch DB query for {len(item_ids)} items"
            }))
            items = await db_query_items_batch(item_ids)

        span.set_attribute("order.item_count", len(items))
        logger.info(json.dumps({
            "event": "fetch_order_complete",
            "order_id": order_id,
            "items_returned": len(items),
            "query_mode": "n+1" if BUG_ENABLED else "batch"
        }))
        return {"order": order, "items": items, "total": sum(i.get("price", 0) for i in items)}
