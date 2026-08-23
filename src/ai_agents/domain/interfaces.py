from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class LLMMessage(BaseModel):
    role: str  # "system" | "user" | "assistant"
    content: str


class LLMResponse(BaseModel):
    content: str
    token_usage: Dict[str, int] = Field(default_factory=dict)
    finish_reason: Optional[str] = "stop"


class ILLMProvider(ABC):
    @abstractmethod
    async def generate(self, messages: List[LLMMessage], **kwargs: Any) -> LLMResponse:
        pass
