import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.crewai_core.interfaces.api.routes.v1.health import router as health_router
from src.crewai_core.interfaces.api.routes.v1.crews import router as crews_router
from configs.settings import get_settings

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s",
)
logger = logging.getLogger("crewai_api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup & graceful shutdown lifecycle."""
    settings = get_settings()
    logger.info(f"Starting CrewAI Enterprise Service in [{settings.ENVIRONMENT}] mode...")
    yield
    logger.info("Gracefully shutting down CrewAI Enterprise Service...")


def create_application() -> FastAPI:
    """Application Factory Pattern for FastAPI Server."""
    settings = get_settings()

    app = FastAPI(
        title="CrewAI Enterprise Orchestration API",
        version="2.0.0",
        description="Clean Architecture & Production-Grade Multi-Agent AI System",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routes Registration
    app.include_router(health_router, tags=["Health & Monitoring"])
    app.include_router(crews_router, prefix="/v1/crews", tags=["Crew Workflows"])

    return app


app = create_application()

if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run("src.crewai_core.interfaces.api.main:app", host=settings.APP_HOST, port=settings.APP_PORT, reload=True)
