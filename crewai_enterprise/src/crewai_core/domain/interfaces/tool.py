from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class ToolResult(BaseModel):
    """Result returned from a tool execution."""
    success: bool
    output: Any
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ITool(ABC):
    """Abstract Port for Agent Tools."""

    name: str
    description: str
    parameters_schema: Dict[str, Any] = {}

    @abstractmethod
    async def run(self, **kwargs: Any) -> ToolResult:
        """Execute the tool with given arguments asynchronously."""
        pass
