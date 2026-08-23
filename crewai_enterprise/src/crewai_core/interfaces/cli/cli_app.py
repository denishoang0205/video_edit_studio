import asyncio
import typer
import uvicorn
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from src.crewai_core.domain.entities.agent import AgentEntity
from src.crewai_core.domain.entities.task import TaskEntity
from src.crewai_core.domain.entities.crew import CrewEntity
from src.crewai_core.domain.entities.process import ProcessType
from src.crewai_core.infrastructure.llm_providers.mock_adapter import MockLLMAdapter
from src.crewai_core.application.services.crew_runner import CrewRunnerService
from configs.settings import get_settings

app = typer.Typer(help="CrewAI Enterprise Production CLI Tool", no_args_is_help=True)
console = Console()


@app.command("run-demo")
def run_demo(
    topic: str = typer.Option("Clean Architecture for AI Multi-Agent Systems", help="Topic for Crew execution"),
):
    """Executes a sample 2-Agent Crew to demonstrate Clean Architecture."""
    console.print(Panel.fit(f"[bold green]Running Enterprise Crew Demo on topic:[/bold green] '{topic}'"))

    # Define Agents
    researcher = AgentEntity(
        name="Senior Researcher",
        role="Technology & Architecture Analyst",
        goal=f"Research technical facts, architecture patterns and scalability principles for {topic}",
        backstory="Veteran software engineer and systems architect specializing in distributed multi-agent systems.",
    )

    writer = AgentEntity(
        name="Lead Technical Writer",
        role="Senior Technical Author",
        goal=f"Synthesize the research findings into an actionable, executive architectural blueprint for {topic}",
        backstory="Experienced engineering author capable of turning complex software designs into clean markdown documentation.",
    )

    # Define Tasks
    task_research = TaskEntity(
        id="task_research",
        description=f"Conduct thorough architectural research on: '{topic}'. Identify layers, boundaries, and best practices.",
        expected_output="A bullet-point summary of core architecture layers and key engineering trade-offs.",
        assigned_agent=researcher,
    )

    task_write = TaskEntity(
        id="task_write",
        description=f"Using the research output, write a production-ready architectural summary and deployment checklist.",
        expected_output="A well-formatted Markdown report ready for engineering leadership.",
        assigned_agent=writer,
        context_task_ids=["task_research"],
    )

    # Define Crew
    crew = CrewEntity(
        name="Enterprise Demo Crew",
        agents=[researcher, writer],
        tasks=[task_research, task_write],
        process=ProcessType.SEQUENTIAL,
    )

    # Execution
    runner = CrewRunnerService(llm_provider=MockLLMAdapter())
    result = asyncio.run(runner.run_crew(crew, inputs={"topic": topic}))

    # Display Results
    table = Table(title="Task Execution Summary")
    table.add_column("Task ID", style="cyan")
    table.add_column("Agent", style="magenta")
    table.add_column("Status", style="green")
    table.add_column("Duration (s)", style="yellow")

    for t in result.task_results:
        table.add_row(t.task_id, t.agent_name, t.status, str(t.execution_time_seconds))

    console.print(table)
    console.print("\n[bold cyan]=== Final Executive Output ===[/bold cyan]\n")
    console.print(result.final_output)


@app.command("serve")
def serve(
    host: str = typer.Option("0.0.0.0", help="Host address to bind"),
    port: int = typer.Option(8000, help="Port to bind"),
    reload: bool = typer.Option(True, help="Enable auto-reload in development"),
):
    """Starts the FastAPI Web and API Gateway server."""
    console.print(f"[bold green]Starting CrewAI Enterprise API Server on http://{host}:{port}[/bold green]")
    console.print(f"[bold cyan]Swagger API Docs:[/bold cyan] http://localhost:{port}/docs")
    uvicorn.run("src.crewai_core.interfaces.api.main:app", host=host, port=port, reload=reload)


@app.command("version")
def version():
    """Displays current CrewAI Enterprise version."""
    from src.crewai_core import __version__
    console.print(f"CrewAI Enterprise Version: [bold green]{__version__}[/bold green]")


def main():
    app()


if __name__ == "__main__":
    main()
