import pytest
from fastapi.testclient import TestClient
from src.crewai_core.interfaces.api.main import app

client = TestClient(app)


def test_healthz_endpoint():
    response = client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "uptime_seconds" in data


def test_execute_crew_endpoint():
    payload = {
        "crew_name": "API Integration Crew",
        "process": "sequential",
        "agents": [
            {
                "name": "Planner",
                "role": "Strategic Planner",
                "goal": "Create a 3-step action plan",
                "backstory": "Experienced project manager.",
            }
        ],
        "tasks": [
            {
                "id": "plan_task",
                "description": "Create plan for {project_name}",
                "expected_output": "3 numbered action items",
                "agent_name": "Planner",
            }
        ],
        "inputs": {"project_name": "Cloud Migration"},
    }

    response = client.post("/v1/crews/execute", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "COMPLETED"
    assert data["crew_name"] == "API Integration Crew"
    assert len(data["task_results"]) == 1
    assert "MockLLMAdapter" in data["final_output"] or len(data["final_output"]) > 0


def test_dispatch_async_endpoint():
    payload = {
        "crew_name": "Async Task Crew",
        "process": "sequential",
        "agents": [
            {
                "name": "Worker",
                "role": "Task Executor",
                "goal": "Execute background jobs",
                "backstory": "Worker agent.",
            }
        ],
        "tasks": [
            {
                "id": "bg_task",
                "description": "Process data",
                "expected_output": "Processed",
                "agent_name": "Worker",
            }
        ],
        "inputs": {},
    }

    response = client.post("/v1/crews/dispatch", json=payload)
    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "QUEUED"
    assert "job_id" in data
