from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, Dict, List, Optional
from pydantic import BaseModel, Field


class LLMMessage(BaseModel):
    """Normalized message representation across all LLM providers."""
    role: str  # "system" | "user" | "assistant" | "tool"
    content: str
    name: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None


class LLMResponse(BaseModel):
    """Normalized completion response with metadata and token usage."""
    content: str
    token_usage: Dict[str, int] = Field(default_factory=lambda: {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})
    tool_calls: Optional[List[Dict[str, Any]]] = None
    finish_reason: Optional[str] = "stop"
    raw_response: Optional[Dict[str, Any]] = None


class ILLMProvider(ABC):
    """Abstract Port for Large Language Model Providers."""

    @abstractmethod
    async def generate(self, messages: List[LLMMessage], **kwargs: Any) -> LLMResponse:
        """Asynchronously send messages to LLM and return structured response."""
        pass

    @abstractmethod
    async def generate_stream(self, messages: List[LLMMessage], **kwargs: Any) -> AsyncGenerator[str, None]:
        """Stream chunks from LLM in real-time."""
        pass
