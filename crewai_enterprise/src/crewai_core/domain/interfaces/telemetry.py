from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from contextlib import asynccontextmanager


class ITelemetryTracer(ABC):
    """Abstract Port for Distributed Tracing and Observability."""

    @abstractmethod
    def start_span(self, name: str, attributes: Optional[Dict[str, Any]] = None):
        """Start a new trace span."""
        pass

    @abstractmethod
    def log_event(self, name: str, payload: Dict[str, Any]) -> None:
        """Log a telemetry event (e.g. token usage, execution time)."""
        pass
