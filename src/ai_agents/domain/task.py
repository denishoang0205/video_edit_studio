import uuid
from typing import Any, List, Optional
from pydantic import BaseModel, Field, ConfigDict
from src.ai_agents.domain.agent import AgentEntity


class TaskEntity(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    description: str
    expected_output: str
    assigned_agent: Optional[AgentEntity] = None
    context_task_ids: List[str] = Field(default_factory=list)

    model_config = ConfigDict(arbitrary_types_allowed=True)
