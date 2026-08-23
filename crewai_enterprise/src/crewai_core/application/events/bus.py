import logging
from typing import Any, Callable, Dict, List
from datetime import datetime, timezone
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class DomainEvent(BaseModel):
    event_type: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    payload: Dict[str, Any] = Field(default_factory=dict)


class EventBus:
    """Pub/Sub in-memory event bus for decoupling domain events from consumers."""

    def __init__(self):
        self._subscribers: Dict[str, List[Callable[[DomainEvent], Any]]] = {}

    def subscribe(self, event_type: str, handler: Callable[[DomainEvent], Any]) -> None:
        """Register a handler for a specific event type."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)

    async def publish(self, event: DomainEvent) -> None:
        """Broadcast event to all registered handlers asynchronously."""
        handlers = self._subscribers.get(event.event_type, [])
        for handler in handlers:
            try:
                if callable(handler):
                    import inspect
                    if inspect.iscoroutinefunction(handler):
                        await handler(event)
                    else:
                        handler(event)
            except Exception as e:
                logger.error(f"Error handling event {event.event_type}: {str(e)}")


# Global Event Bus Singleton
event_bus = EventBus()
