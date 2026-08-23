# CrewAI Enterprise - Clean Architecture & Production Deployment Standard

A decoupled, scalable, and domain-driven implementation of **CrewAI** built to international enterprise software engineering standards.

---

## 🏛️ System Architecture

The architecture adheres strictly to **Clean Architecture** and **Ports & Adapters (Hexagonal Architecture)**:

```
src/crewai_core/
├── domain/            # Layer 1: Core Domain Entities & Interfaces (Pure Python, Zero External Libs)
│   ├── entities/      # AgentEntity, TaskEntity, CrewEntity, ProcessType
│   ├── interfaces/    # ILLMProvider, IMemoryStore, ITool, ITelemetryTracer
│   └── exceptions/    # Domain-specific error hierarchies
│
├── application/       # Layer 2: Application Use Cases & Orchestration
│   ├── services/      # CrewRunnerService (Sequential & Hierarchical pipelines)
│   ├── dto/           # Pydantic v2 Request/Response Data Transfer Objects
│   └── events/        # In-Memory EventBus & Domain Event Triggers
│
├── infrastructure/    # Layer 3: Adapters & Concrete Implementations
│   ├── llm_providers/ # OpenAI, Google Gemini, and Mock LLM adapters
│   ├── memory_stores/ # In-Memory & Qdrant vector memory storage
│   ├── tools/         # Calculator, Web Search, and Extensible Custom Tools
│   └── telemetry/     # OpenTelemetry Tracing & Observability
│
└── interfaces/        # Layer 4: Delivery & Ingress Endpoints
    ├── api/           # FastAPI REST endpoints (/healthz, /v1/crews/execute, /v1/crews/dispatch)
    ├── worker/        # Celery background worker for async queueing via Redis
    └── cli/           # Interactive Typer/Rich Command Line Interface
```

---

## 🚀 Quick Start Guide

### 1. Prerequisites & Environment Setup
```bash
cd crewai_enterprise

# Create Virtual Environment
python -m venv .venv
.venv\Scripts\activate  # On Windows (.venv/bin/activate on Linux/macOS)

# Install Dependencies
pip install -r <(pip install -e .)
# or install directly:
pip install pydantic pydantic-settings fastapi uvicorn celery redis httpx typer rich pytest pytest-asyncio
```

### 2. Run CLI Demo
```bash
python -m src.crewai_core.interfaces.cli.cli_app --help
python -m src.crewai_core.interfaces.cli.cli_app run-demo --topic "Clean Architecture for Microservices"
```

### 3. Run FastAPI Server
```bash
python run_local.py
```
Open **Swagger Documentation**: `http://localhost:8000/docs`

### 4. Run Automated Test Suite
```bash
pytest tests/ -v
```

---

## 🐳 Docker & Kubernetes Deployment

### Run Full Stack (API + Celery Worker + Redis + Qdrant) via Docker Compose:
```bash
docker-compose -f deployments/docker/docker-compose.yml up -d --build
```

### Deploy to Kubernetes Cluster:
```bash
kubectl apply -f deployments/k8s/api-deployment.yaml
kubectl apply -f deployments/k8s/worker-deployment.yaml
```
