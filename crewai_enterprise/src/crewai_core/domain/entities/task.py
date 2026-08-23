import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict
from src.crewai_core.domain.entities.agent import AgentEntity


class TaskEntity(BaseModel):
    """Domain Entity defining an actionable unit of work for an agent."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    description: str
    expected_output: str
    assigned_agent: Optional[AgentEntity] = None
    tools: List[Any] = Field(default_factory=list)
    context_task_ids: List[str] = Field(default_factory=list)
    async_execution: bool = False
    output_json_schema: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def validate_task_definition(self) -> None:
        """Domain invariant validation for task."""
        if not self.description.strip():
            raise ValueError(f"Task {self.id} must have a non-empty description.")
        if not self.expected_output.strip():
            raise ValueError(f"Task {self.id} must define an expected output.")
