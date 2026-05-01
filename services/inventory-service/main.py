import os
import logging

from fastapi import FastAPI

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


setup_telemetry("inventory-service")

app = FastAPI(title="inventory-service")

# Sample inventory catalogue
ITEMS = {
    "item-1": {"id": "item-1", "name": "Laptop Pro 16",    "price": 1999.99, "stock": 42},
    "item-2": {"id": "item-2", "name": "Wireless Mouse",   "price":   29.99, "stock": 200},
    "item-3": {"id": "item-3", "name": "USB-C Hub",        "price":   49.99, "stock": 135},
    "item-4": {"id": "item-4", "name": "Mechanical Keyboard", "price": 149.99, "stock": 75},
    "item-5": {"id": "item-5", "name": "27\" Monitor",     "price":  399.99, "stock": 30},
}


@app.get("/health")
async def health():
    return {"status": "ok", "service": "inventory-service"}


@app.get("/items/batch")
async def get_items_batch(ids: str):
    """Return multiple items in a single call. ids is a comma-separated list of item IDs."""
    logger.info("batch request ids=%s", ids)
    return [ITEMS.get(i, {"error": "not found"}) for i in ids.split(",")]


@app.get("/items/{item_id}")
async def get_item(item_id: str):
    """Return a single item by ID."""
    logger.info("single item request item_id=%s", item_id)
    return ITEMS.get(item_id, {"error": "not found"})
