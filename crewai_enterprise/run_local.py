"""Quick launcher for local execution and quick testing."""
import sys
import uvicorn
from configs.settings import get_settings

if __name__ == "__main__":
    settings = get_settings()
    print(f"==================================================")
    print(f"  Launching {settings.APP_NAME} on http://localhost:{settings.APP_PORT}")
    print(f"  Swagger Docs: http://localhost:{settings.APP_PORT}/docs")
    print(f"  Default LLM Provider: {settings.DEFAULT_LLM_PROVIDER}")
    print(f"==================================================")
    uvicorn.run(
        "src.crewai_core.interfaces.api.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=True,
    )
