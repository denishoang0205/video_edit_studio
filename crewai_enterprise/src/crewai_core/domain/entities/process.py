from enum import Enum


class ProcessType(str, Enum):
    """Execution workflows supported by CrewAI Enterprise."""
    SEQUENTIAL = "sequential"
    HIERARCHICAL = "hierarchical"
    CONSENSUS = "consensus"
    PARALLEL = "parallel"
