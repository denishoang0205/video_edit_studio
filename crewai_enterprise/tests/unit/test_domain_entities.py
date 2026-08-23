import pytest
from src.crewai_core.domain.entities.agent import AgentEntity
from src.crewai_core.domain.entities.task import TaskEntity
from src.crewai_core.domain.entities.crew import CrewEntity
from src.crewai_core.domain.entities.process import ProcessType


def test_agent_system_prompt_generation():
    agent = AgentEntity(
        name="Data Analyst",
        role="Senior BI Analyst",
        goal="Extract actionable insights from raw data",
        backstory="Veteran analytics professional with 10 years of SQL & Python experience.",
    )
    prompt = agent.build_system_prompt()
    assert "Data Analyst" in prompt
    assert "Senior BI Analyst" in prompt
    assert "Extract actionable insights" in prompt


def test_task_validation():
    task = TaskEntity(
        description="Analyze revenue growth",
        expected_output="A summary table with growth rate",
    )
    assert task.description == "Analyze revenue growth"
    task.validate_task_definition()

    with pytest.raises(ValueError):
        invalid_task = TaskEntity(description="", expected_output="None")
        invalid_task.validate_task_definition()


def test_crew_invariants_validation():
    agent = AgentEntity(name="A1", role="R1", goal="G1", backstory="B1")
    task = TaskEntity(description="T1", expected_output="O1", assigned_agent=agent)

    # Valid crew
    crew = CrewEntity(name="Test Crew", agents=[agent], tasks=[task])
    crew.validate_invariants()
    assert crew.process == ProcessType.SEQUENTIAL

    # Empty crew
    with pytest.raises(ValueError):
        empty_crew = CrewEntity(name="Empty", agents=[], tasks=[])
        empty_crew.validate_invariants()
