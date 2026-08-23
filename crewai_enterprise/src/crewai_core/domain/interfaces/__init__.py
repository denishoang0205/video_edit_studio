"""Domain Interfaces (Ports) for external providers."""
from src.crewai_core.domain.interfaces.llm import ILLMProvider, LLMMessage, LLMResponse
from src.crewai_core.domain.interfaces.tool import ITool, ToolResult
from src.crewai_core.domain.interfaces.memory import IMemoryStore, MemoryEntry
from src.crewai_core.domain.interfaces.telemetry import ITelemetryTracer

__all__ = [
    "ILLMProvider",
    "LLMMessage",
    "LLMResponse",
    "ITool",
    "ToolResult",
    "IMemoryStore",
    "MemoryEntry",
    "ITelemetryTracer",
]
