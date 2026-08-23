from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AgentDTO(BaseModel):
    name: str
    role: str
    goal: str
    backstory: str
    allow_delegation: bool = False
    max_iter: int = 10
    temperature: float = 0.7


class TaskDTO(BaseModel):
    id: Optional[str] = None
    description: str
    expected_output: str
    agent_name: str
    context_task_ids: List[str] = Field(default_factory=list)


class CrewExecutionRequestDTO(BaseModel):
    crew_name: str = "Enterprise Crew"
    process: str = "sequential"  # 'sequential' | 'hierarchical'
    agents: List[AgentDTO]
    tasks: List[TaskDTO]
    inputs: Dict[str, Any] = Field(default_factory=dict)
    manager_agent_name: Optional[str] = None


class TaskResultDTO(BaseModel):
    task_id: str
    agent_name: str
    status: str
    output: str
    token_usage: Dict[str, int] = Field(default_factory=dict)
    execution_time_seconds: float = 0.0


class CrewExecutionResponseDTO(BaseModel):
    job_id: str
    crew_name: str
    status: str  # "COMPLETED" | "FAILED" | "QUEUED"
    final_output: str
    task_results: List[TaskResultDTO]
    total_token_usage: Dict[str, int]
    total_execution_time_seconds: float
    error: Optional[str] = None
