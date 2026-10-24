from fastapi import APIRouter

router = APIRouter(tags=["Health"])


@router.get("/health")
def health_check() -> dict[str, str]:
    """Confirm that the API process is responding."""
    return {
        "status": "ok",
        "service": "finlytics-api",
    }


@router.get("/ready")
def readiness_check() -> dict[str, str]:
    """Basic process readiness; dependency checks come later."""
    return {
        "status": "ready",
        "service": "finlytics-api",
    }