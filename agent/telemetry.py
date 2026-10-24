"""OpenTelemetry setup: spans go to traces/spans.jsonl, and to OTLP (e.g. Jaeger) if configured."""

import json
import threading

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult

from agent.config import settings


class JsonlSpanExporter(SpanExporter):
    def __init__(self, path):
        self.path = path
        self._lock = threading.Lock()
        path.parent.mkdir(parents=True, exist_ok=True)

    def export(self, spans):
        with self._lock, self.path.open("a", encoding="utf-8") as f:
            for s in spans:
                f.write(json.dumps({
                    "name": s.name,
                    "trace_id": f"{s.context.trace_id:032x}",
                    "span_id": f"{s.context.span_id:016x}",
                    "parent_id": f"{s.parent.span_id:016x}" if s.parent else None,
                    "start_ns": s.start_time,
                    "duration_ms": round((s.end_time - s.start_time) / 1e6, 2),
                    "status": s.status.status_code.name,
                    "attributes": dict(s.attributes or {}),
                }, default=str) + "\n")
        return SpanExportResult.SUCCESS


def _setup() -> trace.Tracer:
    provider = TracerProvider(resource=Resource.create({"service.name": "agent-workflow"}))
    provider.add_span_processor(SimpleSpanProcessor(JsonlSpanExporter(settings.traces_dir / "spans.jsonl")))
    if settings.otlp_endpoint:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{settings.otlp_endpoint}/v1/traces")))
    trace.set_tracer_provider(provider)
    return trace.get_tracer("agent-workflow")


tracer = _setup()
