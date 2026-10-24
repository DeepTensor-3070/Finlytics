from fastapi import FastAPI

from backend.app.api.routes.health import router as health_router
from backend.app.core.config import get_settings
from backend.app.api.routes.cases import router as cases_router

settings = get_settings()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="AI-powered financial investigation and risk analysis API.",
    )

    app.include_router(health_router)
    app.include_router(cases_router)

    return app


app = create_app()