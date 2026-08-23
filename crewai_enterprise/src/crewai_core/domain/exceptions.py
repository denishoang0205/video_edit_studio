"""Domain Specific Exceptions for CrewAI Enterprise."""


class CrewAIException(Exception):
    """Base exception for all CrewAI domain errors."""

    def __init__(self, message: str, details: dict = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class AgentExecutionError(CrewAIException):
    """Raised when an agent fails to execute a task or iteration."""
    pass


class TaskValidationError(CrewAIException):
    """Raised when task parameters or outputs violate constraints."""
    pass


class LLMProviderError(CrewAIException):
    """Raised when an external LLM call fails or times out."""
    pass


class ToolExecutionError(CrewAIException):
    """Raised when an agent tool fails execution."""
    pass


class MemoryStoreError(CrewAIException):
    """Raised when reading or writing to memory fails."""
    pass
