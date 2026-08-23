import pytest
from src.crewai_core.domain.entities.agent import AgentEntity
from src.crewai_core.domain.entities.task import TaskEntity
from src.crewai_core.domain.entities.crew import CrewEntity
from src.crewai_core.infrastructure.llm_providers.mock_adapter import MockLLMAdapter
from src.crewai_core.application.services.crew_runner import CrewRunnerService


@pytest.mark.asyncio
async def test_sequential_crew_execution():
    agent1 = AgentEntity(
        name="Researcher",
        role="Research Specialist",
        goal="Discover facts",
        backstory="Researcher with high analytical skills.",
    )
    agent2 = AgentEntity(
        name="Writer",
        role="Technical Writer",
        goal="Write clear documentation",
        backstory="Expert author.",
    )

    task1 = TaskEntity(
        id="t1",
        description="Research topic: {topic}",
        expected_output="Bullet points",
        assigned_agent=agent1,
    )
    task2 = TaskEntity(
        id="t2",
        description="Write article based on research",
        expected_output="Final article",
        assigned_agent=agent2,
        context_task_ids=["t1"],
    )

    crew = CrewEntity(
        name="Publishing Crew",
        agents=[agent1, agent2],
        tasks=[task1, task2],
    )

    mock_llm = MockLLMAdapter(predefined_response="Synthesized Mock Output.")
    runner = CrewRunnerService(llm_provider=mock_llm)

    result = await runner.run_crew(crew, inputs={"topic": "Microservices"})

    assert result.status == "COMPLETED"
    assert len(result.task_results) == 2
    assert result.task_results[0].task_id == "t1"
    assert result.task_results[1].task_id == "t2"
    assert result.total_token_usage["total_tokens"] > 0
    assert result.total_execution_time_seconds >= 0.0
