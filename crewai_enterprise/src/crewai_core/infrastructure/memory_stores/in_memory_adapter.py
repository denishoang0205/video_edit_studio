import uuid
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from src.crewai_core.domain.interfaces.memory import IMemoryStore, MemoryEntry


class InMemoryStoreAdapter(IMemoryStore):
    """In-memory Vector/Keyword store adapter for ephemeral memory and unit tests."""

    def __init__(self):
        self._entries: List[MemoryEntry] = []

    async def save(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        entry_id = str(uuid.uuid4())
        entry = MemoryEntry(
            id=entry_id,
            content=content,
            metadata=metadata or {},
            timestamp=datetime.now(timezone.utc),
        )
        self._entries.append(entry)
        return entry_id

    async def search(self, query: str, limit: int = 5) -> List[MemoryEntry]:
        query_words = set(query.lower().split())
        scored_entries = []

        for entry in self._entries:
            entry_words = set(entry.content.lower().split())
            intersection = query_words.intersection(entry_words)
            score = len(intersection) / max(len(query_words), 1)
            if score > 0:
                entry.score = score
                scored_entries.append(entry)

        # Sort by relevance score descending
        scored_entries.sort(key=lambda x: x.score or 0.0, reverse=True)
        return scored_entries[:limit]

    async def clear(self) -> None:
        self._entries.clear()
