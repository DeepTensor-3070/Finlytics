
from contextlib import asynccontextmanager
from logging import basicConfig, getLogger

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.routes.cases import router as cases_router
from backend.app.api.routes.documents import router as documents_router
from backend.app.api.routes.health import router as health_router
from backend.app.api.routes import evidence
from backend.app.api.routes.risk_assessment import (
    router as risk_assessment_router,
)
from backend.app.core.config import get_settings


settings = get_settings()

basicConfig(
    level=settings.LOG_LEVEL.upper(),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = getLogger("finlytics")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Prepare local application directories on startup.

    Database tables remain managed by Alembic migrations.
    """
    settings.upload_path.mkdir(parents=True, exist_ok=True)

    database_path = settings.database_path
    if database_path is not None:
        database_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info(
        "Starting %s v%s in %s mode",
        settings.APP_NAME,
        settings.APP_VERSION,
        settings.ENVIRONMENT,
    )

    yield

    logger.info("Shutting down %s", settings.APP_NAME)


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=(
            "Finlytics: financial investigation, document processing, "
            "external evidence verification, and risk analysis."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    origins = [
        origin.strip()
        for origin in __import__("os").getenv(
            "CORS_ORIGINS",
            "http://localhost:8501,http://127.0.0.1:8501",
        ).split(",")
        if origin.strip()
    ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=[
            "GET",
            "POST",
            "PATCH",
            "DELETE",
            "OPTIONS",
        ],
        allow_headers=["Content-Type", "Authorization"],
    )

    # Register API routers.
    app.include_router(health_router)
    app.include_router(cases_router)
    app.include_router(documents_router)
    app.include_router(evidence.router)
    app.include_router(risk_assessment_router)

    return app


app = create_app()
