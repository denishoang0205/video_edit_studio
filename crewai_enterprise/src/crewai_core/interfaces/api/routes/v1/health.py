import time
from fastapi import APIRouter
from configs.settings import get_settings

router = APIRouter()
START_TIME = time.time()


@router.get("/healthz", summary="Liveness & Readiness Health Probe")
async def health_check():
    """Health check endpoint for Kubernetes probes and load balancers."""
    settings = get_settings()
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "environment": settings.ENVIRONMENT,
        "uptime_seconds": round(time.time() - START_TIME, 2),
        "llm_provider": settings.DEFAULT_LLM_PROVIDER,
    }
