import logging
import time
import uuid
from typing import Any, Dict, List, Optional

from src.crewai_core.domain.entities.crew import CrewEntity
from src.crewai_core.domain.entities.task import TaskEntity
from src.crewai_core.domain.entities.agent import AgentEntity
from src.crewai_core.domain.entities.process import ProcessType
from src.crewai_core.domain.interfaces.llm import ILLMProvider, LLMMessage
from src.crewai_core.domain.exceptions import AgentExecutionError
from src.crewai_core.application.dto.crew_dto import (
    CrewExecutionResponseDTO,
    TaskResultDTO,
)
from src.crewai_core.application.events.bus import event_bus, DomainEvent

logger = logging.getLogger(__name__)


class CrewRunnerService:
    """Core Application Orchestrator for executing AI Agent Workflows."""

    def __init__(self, llm_provider: ILLMProvider):
        self._llm = llm_provider

    async def run_crew(
        self,
        crew: CrewEntity,
        inputs: Optional[Dict[str, Any]] = None,
    ) -> CrewExecutionResponseDTO:
        """Executes a Crew based on its defined ProcessType."""
        inputs = inputs or {}
        crew.validate_invariants()
        job_id = str(uuid.uuid4())
        start_time = time.time()

        logger.info(f"Starting Crew execution: '{crew.name}' (Job ID: {job_id})")
        await event_bus.publish(
            DomainEvent(
                event_type="crew.started",
                payload={"job_id": job_id, "crew_name": crew.name, "process": crew.process.value},
            )
        )

        try:
            if crew.process == ProcessType.SEQUENTIAL:
                result = await self._execute_sequential(job_id, crew, inputs)
            elif crew.process == ProcessType.HIERARCHICAL:
                result = await self._execute_hierarchical(job_id, crew, inputs)
            else:
                result = await self._execute_sequential(job_id, crew, inputs)

            total_duration = time.time() - start_time
            result.total_execution_time_seconds = round(total_duration, 3)

            await event_bus.publish(
                DomainEvent(
                    event_type="crew.completed",
                    payload={"job_id": job_id, "status": "COMPLETED", "duration": total_duration},
                )
            )
            return result

        except Exception as e:
            logger.error(f"Crew execution failed: {str(e)}", exc_info=True)
            total_duration = time.time() - start_time
            await event_bus.publish(
                DomainEvent(
                    event_type="crew.failed",
                    payload={"job_id": job_id, "error": str(e), "duration": total_duration},
                )
            )
            return CrewExecutionResponseDTO(
                job_id=job_id,
                crew_name=crew.name,
                status="FAILED",
                final_output="",
                task_results=[],
                total_token_usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                total_execution_time_seconds=round(total_duration, 3),
                error=str(e),
            )

    async def _execute_sequential(
        self, job_id: str, crew: CrewEntity, inputs: Dict[str, Any]
    ) -> CrewExecutionResponseDTO:
        """Executes tasks sequentially, passing outputs forward as context."""
        context_outputs: Dict[str, str] = {}
        task_results: List[TaskResultDTO] = []
        aggregated_tokens = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

        for task in crew.tasks:
            agent = task.assigned_agent or crew.agents[0]
            task_start = time.time()

            logger.info(f"Executing Task: '{task.description[:60]}...' with Agent: '{agent.name}'")

            # Collect context from specified prior tasks or all prior tasks
            relevant_contexts = []
            if task.context_task_ids:
                for ctx_id in task.context_task_ids:
                    if ctx_id in context_outputs:
                        relevant_contexts.append(f"Context from task {ctx_id}:\n{context_outputs[ctx_id]}")
            else:
                for ctx_id, out in context_outputs.items():
                    relevant_contexts.append(f"Output of previous task:\n{out}")

            combined_context = "\n---\n".join(relevant_contexts) if relevant_contexts else "None."

            # Interpolate inputs into description
            interpolated_desc = task.description
            for k, v in inputs.items():
                interpolated_desc = interpolated_desc.replace(f"{{{k}}}", str(v))

            # Prompt composition
            system_prompt = agent.build_system_prompt()
            user_prompt = (
                f"TASK ASSIGNMENT:\n{interpolated_desc}\n\n"
                f"EXPECTED OUTPUT CRITERIA:\n{task.expected_output}\n\n"
                f"PREVIOUS WORK CONTEXT:\n{combined_context}\n\n"
                f"GLOBAL INPUTS:\n{inputs}\n\n"
                f"Execute the task directly and provide the final output conforming to the expected output criteria."
            )

            messages = [
                LLMMessage(role="system", content=system_prompt),
                LLMMessage(role="user", content=user_prompt),
            ]

            # LLM invocation
            resp = await self._llm.generate(messages, temperature=agent.temperature)
            output_text = resp.content.strip()

            # Handle tools if agent has tools and needs tool calling (can be expanded)
            if agent.tools:
                for tool in agent.tools:
                    # Execute tool if relevant
                    pass

            duration = round(time.time() - task_start, 3)
            context_outputs[task.id] = output_text

            # Accumulate tokens
            for k in aggregated_tokens:
                aggregated_tokens[k] += resp.token_usage.get(k, 0)

            task_results.append(
                TaskResultDTO(
                    task_id=task.id,
                    agent_name=agent.name,
                    status="COMPLETED",
                    output=output_text,
                    token_usage=resp.token_usage,
                    execution_time_seconds=duration,
                )
            )

        final_output = task_results[-1].output if task_results else ""

        return CrewExecutionResponseDTO(
            job_id=job_id,
            crew_name=crew.name,
            status="COMPLETED",
            final_output=final_output,
            task_results=task_results,
            total_token_usage=aggregated_tokens,
            total_execution_time_seconds=0.0,
        )

    async def _execute_hierarchical(
        self, job_id: str, crew: CrewEntity, inputs: Dict[str, Any]
    ) -> CrewExecutionResponseDTO:
        """Executes tasks using a manager agent who reviews and delegates."""
        manager = crew.manager_agent or crew.agents[0]
        # First execute tasks sequentially, then manager synthesizes/reviews
        base_result = await self._execute_sequential(job_id, crew, inputs)
        if base_result.status == "FAILED":
            return base_result

        # Manager review step
        manager_prompt = (
            f"As the Manager ({manager.name}), review the combined work completed by your team:\n\n"
            f"{base_result.final_output}\n\n"
            f"Provide the final executive synthesis and approval."
        )

        review_messages = [
            LLMMessage(role="system", content=manager.build_system_prompt()),
            LLMMessage(role="user", content=manager_prompt),
        ]
        review_resp = await self._llm.generate(review_messages, temperature=manager.temperature)

        base_result.final_output = review_resp.content.strip()
        for k in base_result.total_token_usage:
            base_result.total_token_usage[k] += review_resp.token_usage.get(k, 0)

        return base_result
