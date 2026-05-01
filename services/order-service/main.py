import os
import logging

from fastapi import FastAPI, HTTPException
import httpx

from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

OTEL_ENDPOINT = os.getenv(
    "OTEL_EXPORTER_OTLP_ENDPOINT",
    "http://grafana-k8s-monitoring-alloy-receiver.monitoring.svc.cluster.local:4317",
)


def setup_telemetry(service_name: str):
    resource = Resource.create({
        "service.name": service_name,
        "service.namespace": "grafana-demo",
        "service.version": "1.0.0",
        "deployment.environment": "production",
    })
    exporter = OTLPSpanExporter(endpoint=OTEL_ENDPOINT, insecure=True)
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    metric_exporter = OTLPMetricExporter(endpoint=OTEL_ENDPOINT, insecure=True)
    reader = PeriodicExportingMetricReader(metric_exporter, export_interval_millis=15000)
    metrics.set_meter_provider(MeterProvider(resource=resource, metric_readers=[reader]))

    FastAPIInstrumentor().instrument()
    HTTPXClientInstrumentor().instrument()


setup_telemetry("order-service")

app = FastAPI(title="order-service")

BUG_ENABLED = os.getenv("BUG_ENABLED", "true").lower() == "true"
INVENTORY_URL = os.getenv("INVENTORY_SERVICE_URL", "http://inventory-service:8080")

# Sample order data — each order references 3-5 item IDs
ORDERS = {
    "order-1": {"id": "order-1", "customer": "Alice",   "item_ids": ["item-1", "item-2", "item-3"]},
    "order-2": {"id": "order-2", "customer": "Bob",     "item_ids": ["item-2", "item-4", "item-5"]},
    "order-3": {"id": "order-3", "customer": "Charlie", "item_ids": ["item-1", "item-3", "item-4", "item-5"]},
    "order-4": {"id": "order-4", "customer": "Diana",   "item_ids": ["item-1", "item-2", "item-3", "item-4", "item-5"]},
    "order-5": {"id": "order-5", "customer": "Eve",     "item_ids": ["item-3", "item-5"]},
}


@app.get("/health")
async def health():
    return {"status": "ok", "service": "order-service", "bug_enabled": BUG_ENABLED}


@app.get("/orders/{order_id}")
async def get_order(order_id: str):
    logger.info("get_order order_id=%s bug_enabled=%s", order_id, BUG_ENABLED)
    order = ORDERS.get(order_id)
    if not order:
        raise HTTPException(status_code=404, detail=f"Order {order_id} not found")

    items = []
    if BUG_ENABLED:
        # BUG: N+1 — one HTTP call per item
        async with httpx.AsyncClient() as client:
            for item_id in order["item_ids"]:
                r = await client.get(f"{INVENTORY_URL}/items/{item_id}")
                items.append(r.json())
    else:
        # FIX: single batch call
        ids = ",".join(order["item_ids"])
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{INVENTORY_URL}/items/batch?ids={ids}")
            items = r.json()

    return {"order": order, "items": items}
