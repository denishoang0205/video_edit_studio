import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict
from src.crewai_core.domain.entities.agent import AgentEntity
from src.crewai_core.domain.entities.task import TaskEntity
from src.crewai_core.domain.entities.process import ProcessType


class CrewEntity(BaseModel):
    """Aggregate Root representing a collaborative team of AI Agents executing tasks."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "Enterprise Crew"
    agents: List[AgentEntity]
    tasks: List[TaskEntity]
    process: ProcessType = ProcessType.SEQUENTIAL
    manager_agent: Optional[AgentEntity] = None
    memory: bool = False
    verbose: bool = True
    max_rpm: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def validate_invariants(self) -> None:
        """Validates domain business rules for the crew aggregate."""
        if not self.agents:
            raise ValueError("Crew must have at least one Agent.")
        if not self.tasks:
            raise ValueError("Crew must have at least one Task to execute.")
        if self.process == ProcessType.HIERARCHICAL and not self.manager_agent:
            raise ValueError("Hierarchical process requires a designated manager_agent.")
