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


setup_telemetry("frontend-api")

app = FastAPI(title="frontend-api")

ORDERS_URL = os.getenv("ORDER_SERVICE_URL", "http://order-service:8080")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "frontend-api"}


@app.get("/checkout/{order_id}")
async def checkout(order_id: str):
    logger.info("checkout request for order_id=%s", order_id)
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(f"{ORDERS_URL}/orders/{order_id}", timeout=15.0)
            r.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=str(e))
        except httpx.RequestError as e:
            raise HTTPException(status_code=503, detail=f"order-service unavailable: {e}")
    return r.json()
