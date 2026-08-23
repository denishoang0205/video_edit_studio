import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict
from src.ai_agents.domain.agent import AgentEntity
from src.ai_agents.domain.task import TaskEntity
from src.ai_agents.domain.process import ProcessType


class CrewEntity(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "TikTok Studio Crew"
    agents: List[AgentEntity]
    tasks: List[TaskEntity]
    process: ProcessType = ProcessType.SEQUENTIAL

    model_config = ConfigDict(arbitrary_types_allowed=True)
