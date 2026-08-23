import logging
from typing import Any, Dict, Optional
from contextlib import contextmanager
from src.crewai_core.domain.interfaces.telemetry import ITelemetryTracer

logger = logging.getLogger(__name__)


class OpenTelemetryTracer(ITelemetryTracer):
    """OpenTelemetry Distributed Tracing Adapter."""

    def __init__(self, service_name: str = "crewai-enterprise"):
        self.service_name = service_name
        self._tracer = None

    def _get_tracer(self):
        if self._tracer is None:
            try:
                from opentelemetry import trace
                self._tracer = trace.get_tracer(self.service_name)
            except ImportError:
                self._tracer = None
        return self._tracer

    @contextmanager
    def start_span(self, name: str, attributes: Optional[Dict[str, Any]] = None):
        tracer = self._get_tracer()
        if tracer:
            with tracer.start_as_current_span(name, attributes=attributes or {}) as span:
                yield span
        else:
            logger.debug(f"[TraceSpan: {name}] Attributes: {attributes}")
            yield None

    def log_event(self, name: str, payload: Dict[str, Any]) -> None:
        logger.info(f"[TelemetryEvent: {name}] Payload: {payload}")
