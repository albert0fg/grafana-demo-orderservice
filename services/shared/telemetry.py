"""
Shared OTEL telemetry setup for all grafana-demo services.

Key fixes vs naive setup:
- Injects k8s.pod.ip + k8s.pod.uid (Downward API) so k8sattributes processor
  can match by resource_attribute instead of connection IP — avoids SNAT drops
  when gRPC goes cross-node in AKS.
- Explicit W3C TraceContext propagator so traceparent headers flow between services.
- service.version = GIT_SHA from build arg for easy before/after comparison.
"""
import os
import logging

from opentelemetry import trace, metrics
from opentelemetry.propagate import set_global_textmap
from opentelemetry.propagators.composite import CompositePropagator
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from opentelemetry.baggage.propagation import W3CBaggagePropagator
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

logger = logging.getLogger(__name__)

OTEL_ENDPOINT = os.getenv(
    "OTEL_EXPORTER_OTLP_ENDPOINT",
    "http://grafana-k8s-monitoring-alloy-receiver.monitoring.svc.cluster.local:4317",
)


def setup_telemetry(service_name: str) -> None:
    # W3C TraceContext propagator — required for cross-service trace linking.
    # Without this, traceparent headers are not injected/extracted and each
    # service's spans appear as unconnected root traces in Tempo.
    set_global_textmap(CompositePropagator([
        TraceContextTextMapPropagator(),
        W3CBaggagePropagator(),
    ]))

    # Build resource attributes. k8s.pod.ip and k8s.pod.uid come from the
    # Downward API (set as env vars in each K8s manifest). They let the
    # k8sattributes processor match spans by resource attribute rather than
    # connection source IP, avoiding drops when gRPC routes cross-node.
    resource_attrs = {
        "service.name": service_name,
        "service.namespace": "grafana-demo",
        "service.version": os.getenv("SERVICE_VERSION", "dev"),
        "deployment.environment": "production",
    }
    pod_ip = os.getenv("K8S_POD_IP")
    pod_uid = os.getenv("K8S_POD_UID")
    if pod_ip:
        resource_attrs["k8s.pod.ip"] = pod_ip
    if pod_uid:
        resource_attrs["k8s.pod.uid"] = pod_uid

    resource = Resource.create(resource_attrs)

    # Traces
    span_exporter = OTLPSpanExporter(endpoint=OTEL_ENDPOINT, insecure=True)
    trace_provider = TracerProvider(resource=resource)
    trace_provider.add_span_processor(BatchSpanProcessor(span_exporter))
    trace.set_tracer_provider(trace_provider)

    # Metrics
    metric_exporter = OTLPMetricExporter(endpoint=OTEL_ENDPOINT, insecure=True)
    metric_reader = PeriodicExportingMetricReader(metric_exporter, export_interval_millis=15000)
    metrics.set_meter_provider(MeterProvider(resource=resource, metric_readers=[metric_reader]))

    # HTTP server + client instrumentation
    FastAPIInstrumentor().instrument()
    HTTPXClientInstrumentor().instrument()

    logger.info(
        "OTEL ready service=%s version=%s pod_ip=%s endpoint=%s",
        service_name, resource_attrs["service.version"], pod_ip or "unknown", OTEL_ENDPOINT,
    )
