import os
import logging
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor

OTEL_ENDPOINT = os.getenv(
    "OTEL_EXPORTER_OTLP_ENDPOINT",
    "http://grafana-k8s-monitoring-alloy-receiver.monitoring.svc.cluster.local:4317"
)
SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "orderservice")
SERVICE_VERSION = os.getenv("SERVICE_VERSION", "1.0.0")
DEPLOYMENT_ENV = os.getenv("DEPLOYMENT_ENV", "production")


def setup_telemetry():
    resource = Resource.create({
        "service.name": SERVICE_NAME,
        "service.version": SERVICE_VERSION,
        "deployment.environment": DEPLOYMENT_ENV,
    })

    exporter = OTLPSpanExporter(endpoint=OTEL_ENDPOINT, insecure=True)
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    FastAPIInstrumentor().instrument()
    LoggingInstrumentor().instrument(set_logging_format=True)

    logging.getLogger("orderservice").info(
        f"Telemetry initialized — service={SERVICE_NAME} endpoint={OTEL_ENDPOINT}"
    )
