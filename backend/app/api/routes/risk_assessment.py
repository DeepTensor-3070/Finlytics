from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.services.case_risk_assessment_service import (
    build_case_risk_assessment,
)

router = APIRouter(
    prefix="/api/v1/cases",
    tags=["Risk Assessment"],
)

DbSession = Annotated[Session, Depends(get_db)]


@router.post(
    "/{case_id}/risk-assessment",
    status_code=status.HTTP_200_OK,
)
def get_case_risk_assessment(
    case_id: str,
    db: DbSession,
    current_period: str | None = None,
    previous_period: str | None = None,
):
    """Generate a preliminary financial risk assessment for a case."""

    try:
        return build_case_risk_assessment(
            db,
            case_id,
            current_period=current_period,
            previous_period=previous_period,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc