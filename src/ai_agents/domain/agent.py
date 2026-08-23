import uuid
from typing import Any, List, Optional
from pydantic import BaseModel, Field, ConfigDict


class AgentEntity(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    role: str
    goal: str
    backstory: str
    temperature: float = 0.7
    verbose: bool = True

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def build_system_prompt(self) -> str:
        return (
            f"You are {self.name}, {self.role}.\n"
            f"Goal: {self.goal}\n"
            f"Persona & Context: {self.backstory}\n"
            f"Deliver professional, concise and high-impact results."
        )
