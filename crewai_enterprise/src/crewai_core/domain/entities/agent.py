import uuid
from typing import Any, List, Optional
from pydantic import BaseModel, Field, ConfigDict


class AgentEntity(BaseModel):
    """Core Agent Domain Entity encapsulating personality, tools, and execution rules."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    role: str
    goal: str
    backstory: str
    tools: List[Any] = Field(default_factory=list)
    memory: Optional[Any] = None
    verbose: bool = True
    allow_delegation: bool = False
    max_iter: int = 15
    temperature: float = 0.7

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def build_system_prompt(self) -> str:
        """Constructs rich persona system prompt for this agent."""
        tool_descriptions = ""
        if self.tools:
            tool_descriptions = "\nAvailable Tools:\n" + "\n".join(
                [f"- {t.name}: {t.description}" for t in self.tools if hasattr(t, 'name')]
            )

        return (
            f"You are {self.name}, an expert {self.role}.\n"
            f"Your Ultimate Goal: {self.goal}\n"
            f"Your Persona Context: {self.backstory}\n"
            f"{tool_descriptions}\n\n"
            f"Execution Guidelines: Deliver concise, accurate, and actionable results based on your expertise."
        )
