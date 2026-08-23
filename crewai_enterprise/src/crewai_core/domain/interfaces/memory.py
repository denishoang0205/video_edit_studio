from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field


class MemoryEntry(BaseModel):
    """Memory entry unit for short-term and long-term storage."""
    id: str
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    score: Optional[float] = None


class IMemoryStore(ABC):
    """Abstract Port for Agent Memory (Vector DB / Key-Value Store)."""

    @abstractmethod
    async def save(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Save a new memory entry and return its ID."""
        pass

    @abstractmethod
    async def search(self, query: str, limit: int = 5) -> List[MemoryEntry]:
        """Search memory entries by semantic similarity or keyword."""
        pass

    @abstractmethod
    async def clear(self) -> None:
        """Clear all stored memories for the session."""
        pass
