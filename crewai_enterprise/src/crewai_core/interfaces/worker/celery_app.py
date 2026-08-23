"""Celery Task Worker for asynchronous Agent execution."""
import asyncio
from celery import Celery
from configs.settings import get_settings
from src.crewai_core.application.dto.crew_dto import CrewExecutionRequestDTO
from src.crewai_core.interfaces.api.routes.v1.crews import _build_crew_entity, _resolve_llm_provider
from src.crewai_core.application.services.crew_runner import CrewRunnerService

settings = get_settings()

celery_app = Celery(
    "crewai_tasks",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
)


@celery_app.task(name="tasks.run_crew_workflow", bind=True)
def run_crew_workflow(self, request_data: dict):
    """Executes asynchronous Crew in background worker process."""
    req_dto = CrewExecutionRequestDTO(**request_data)
    crew = _build_crew_entity(req_dto)
    llm = _resolve_llm_provider()
    runner = CrewRunnerService(llm_provider=llm)

    loop = asyncio.get_event_loop()
    if loop.is_closed():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    result = loop.run_until_complete(runner.run_crew(crew, inputs=req_dto.inputs))
    return result.dict()
