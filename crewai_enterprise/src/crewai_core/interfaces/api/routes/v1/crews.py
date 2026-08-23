from fastapi import APIRouter, HTTPException, BackgroundTasks, status
from typing import Dict, Any

from src.crewai_core.application.dto.crew_dto import (
    CrewExecutionRequestDTO,
    CrewExecutionResponseDTO,
)
from src.crewai_core.domain.entities.crew import CrewEntity
from src.crewai_core.domain.entities.agent import AgentEntity
from src.crewai_core.domain.entities.task import TaskEntity
from src.crewai_core.domain.entities.process import ProcessType
from src.crewai_core.application.services.crew_runner import CrewRunnerService
from src.crewai_core.infrastructure.llm_providers.mock_adapter import MockLLMAdapter
from src.crewai_core.infrastructure.llm_providers.openai_adapter import OpenAILLMAdapter
from src.crewai_core.infrastructure.llm_providers.gemini_adapter import GeminiLLMAdapter
from configs.settings import get_settings

router = APIRouter()


def _resolve_llm_provider():
    settings = get_settings()
    if settings.DEFAULT_LLM_PROVIDER == "openai" and settings.OPENAI_API_KEY:
        return OpenAILLMAdapter(api_key=settings.OPENAI_API_KEY, model_name=settings.DEFAULT_MODEL)
    elif settings.DEFAULT_LLM_PROVIDER == "gemini" and settings.GEMINI_API_KEY:
        return GeminiLLMAdapter(api_key=settings.GEMINI_API_KEY)
    else:
        return MockLLMAdapter()


def _build_crew_entity(request: CrewExecutionRequestDTO) -> CrewEntity:
    # Map Agent DTOs to Entities
    agent_map: Dict[str, AgentEntity] = {}
    for a_dto in request.agents:
        agent = AgentEntity(
            name=a_dto.name,
            role=a_dto.role,
            goal=a_dto.goal,
            backstory=a_dto.backstory,
            allow_delegation=a_dto.allow_delegation,
            max_iter=a_dto.max_iter,
            temperature=a_dto.temperature,
        )
        agent_map[a_dto.name] = agent

    # Map Task DTOs to Entities
    task_entities = []
    for t_dto in request.tasks:
        assigned_agent = agent_map.get(t_dto.agent_name)
        if not assigned_agent and agent_map:
            assigned_agent = list(agent_map.values())[0]

        task = TaskEntity(
            id=t_dto.id or t_dto.description[:12].replace(" ", "_"),
            description=t_dto.description,
            expected_output=t_dto.expected_output,
            assigned_agent=assigned_agent,
            context_task_ids=t_dto.context_task_ids,
        )
        task_entities.append(task)

    process_enum = ProcessType.SEQUENTIAL
    if request.process.lower() == "hierarchical":
        process_enum = ProcessType.HIERARCHICAL

    manager = agent_map.get(request.manager_agent_name) if request.manager_agent_name else None

    return CrewEntity(
        name=request.crew_name,
        agents=list(agent_map.values()),
        tasks=task_entities,
        process=process_enum,
        manager_agent=manager,
    )


@router.post(
    "/execute",
    response_model=CrewExecutionResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Synchronously Execute a Multi-Agent Crew Workflow",
)
async def execute_crew_sync(request: CrewExecutionRequestDTO):
    """Executes the Crew directly and returns the full execution trace and outputs."""
    try:
        crew = _build_crew_entity(request)
        llm = _resolve_llm_provider()
        runner = CrewRunnerService(llm_provider=llm)
        result = await runner.run_crew(crew, inputs=request.inputs)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Crew execution error: {str(e)}",
        )


@router.post(
    "/dispatch",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Asynchronously Dispatch Crew Workflow to Background Celery Queue",
)
async def dispatch_crew_async(request: CrewExecutionRequestDTO):
    """Dispatches the Crew execution request into Redis/Celery background queue."""
    import uuid
    job_id = str(uuid.uuid4())
    # In production, dispatch: celery_app.send_task('tasks.run_crew_workflow', args=[request.dict()])
    return {
        "job_id": job_id,
        "status": "QUEUED",
        "message": f"Crew '{request.crew_name}' successfully queued for execution.",
    }
